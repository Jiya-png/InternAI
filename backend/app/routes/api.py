"""
Step 6 - REST API.

    POST   /api/upload               parse resume -> parsed JSON + analysis_id
    GET    /api/analysis/{id}        top roles, match %, explanations, quality score
    POST   /api/whatif               {analysis_id, role, extra_skills[]} -> new match %
    GET    /api/roadmap/{id}?role=   4-week roadmap
    GET    /api/roles                list of roles
    GET    /api/skills?q=            skill search (for the what-if picker)
    DELETE /api/analysis/{id}        delete stored data (privacy)
    GET    /api/health               service + model status
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_MB, UPLOAD_DIR
from app.database import get_db
from app.models.db_models import Analysis
from app.models.schemas import (
    AnalysisResponse,
    HealthResponse,
    RoleInfo,
    UploadResponse,
    WhatIfRequest,
    WhatIfResponse,
)
from app.services.catalog import get_role, load_roles, load_skills
from app.services.parser import ResumeParseError, parse_resume
from app.services.recommender import get_recommender

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["InternAI"])

MAX_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAGIC = {".pdf": b"%PDF", ".docx": b"PK"}  # DOCX is a zip archive


def _public_profile(parsed: dict[str, Any]) -> dict[str, Any]:
    """Parsed data without the raw text / internal fields."""
    return {k: v for k, v in parsed.items() if k not in ("text", "bullets")}


def _get_analysis(db: Session, analysis_id: str) -> Analysis:
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found. Please upload your resume again.")
    return row


def _resolve_role(role: str) -> str:
    r = get_role(role)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown role '{role}'. See GET /api/roles.")
    return r.id


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED,
             summary="Upload a resume (PDF/DOCX, max 5 MB)")
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    filename = Path(file.filename or "resume").name
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            "Unsupported file type. Please upload a PDF or DOCX resume.")

    # read with a hard size limit (never trust Content-Length)
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                f"File is larger than {MAX_UPLOAD_MB} MB. Please upload a smaller file.")
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file is empty.")
    if not bytes(data[:4]).startswith(MAGIC[ext]):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                            f"This file does not look like a real {ext[1:].upper()} document.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    tmp = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    try:
        tmp.write_bytes(bytes(data))
        parsed = parse_resume(tmp)
    except ResumeParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    finally:
        tmp.unlink(missing_ok=True)  # privacy: never keep the original file

    result = get_recommender().analyze(parsed)
    analysis_id = str(uuid.uuid4())
    db.add(Analysis(id=analysis_id, filename=filename, parsed=parsed, result=result))
    db.commit()
    log.info("Analysis %s created (%d skills)", analysis_id, len(parsed["skills"]))
    return {
        "analysis_id": analysis_id,
        "filename": filename,
        "parsed": _public_profile(parsed),
        "top_roles": [{k: r[k] for k in ("role_id", "title", "domain", "match")} for r in result["top_roles"]],
    }


@router.get("/analysis/{analysis_id}", response_model=AnalysisResponse,
            summary="Top roles, match %, explanations and resume quality")
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get_analysis(db, analysis_id)
    return {
        "analysis_id": row.id,
        "created_at": row.created_at,
        "filename": row.filename,
        "profile": _public_profile(row.parsed),
        **row.result,
    }


@router.delete("/analysis/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Delete a stored analysis")
def delete_analysis(analysis_id: str, db: Session = Depends(get_db)) -> None:
    row = _get_analysis(db, analysis_id)
    db.delete(row)
    db.commit()


@router.post("/whatif", response_model=WhatIfResponse, summary="Recalculate match % with extra skills")
def what_if(req: WhatIfRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get_analysis(db, req.analysis_id)
    return get_recommender().what_if(row.parsed, _resolve_role(req.role), req.extra_skills)


@router.get("/roadmap/{analysis_id}", summary="4-week learning roadmap for a target role")
def roadmap(analysis_id: str, role: str = Query(..., description="Role id or title"),
            db: Session = Depends(get_db)) -> dict[str, Any]:
    row = _get_analysis(db, analysis_id)
    return get_recommender().roadmap(row.parsed, _resolve_role(role))


@router.get("/roles", response_model=list[RoleInfo], summary="List all roles")
def roles() -> list[dict[str, Any]]:
    return [{
        "id": r.id, "title": r.title, "domain": r.domain, "experience_level": r.experience_level,
        "description": r.description,
        "required_skills": [{"skill": rs.skill, "weight": rs.weight} for rs in r.required_skills],
        "nice_to_have": list(r.nice_to_have),
    } for r in load_roles().values()]


@router.get("/skills", summary="Search the skills taxonomy")
def skills(q: str = Query("", max_length=50), limit: int = Query(20, ge=1, le=100)) -> list[dict[str, str]]:
    ql = q.strip().lower()
    out = []
    for s in load_skills().values():
        if not ql or ql in s.name.lower() or any(ql in a.lower() for a in s.aliases):
            out.append({"name": s.name, "category": s.category_label})
            if len(out) >= limit:
                break
    return out


@router.get("/health", response_model=HealthResponse, summary="Service status")
def health() -> dict[str, Any]:
    rec = get_recommender()
    return {
        "status": "ok",
        "trained_models": rec.models.trained,
        "embedding_backend": rec.models.metadata.get("embedding_backend_in_use"),
        "n_roles": len(load_roles()),
        "n_skills": len(load_skills()),
    }
