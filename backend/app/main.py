"""
InternAI - FastAPI application entry point.

Run (from ``backend``):
    uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs

If the React app has been built (frontend/dist, or the folder in
INTERNAI_FRONTEND_DIST), it is served from "/" too, so a single process can
host the whole website.
"""
from __future__ import annotations

import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import BACKEND_DIR, CORS_ORIGINS
from app.database import init_db
from app.routes.api import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("internai")

FRONTEND_DIST = Path(os.getenv("INTERNAI_FRONTEND_DIST", BACKEND_DIR.parent / "frontend" / "dist"))


def _warm_up() -> None:
    """Load models in the background so the first upload is fast."""
    try:
        from app.services.recommender import get_recommender
        from app.services.skill_extractor import get_extractor

        get_extractor()
        rec = get_recommender()
        log.info("Models ready (trained=%s, embeddings=%s)", rec.models.trained,
                 rec.models.metadata.get("embedding_backend_in_use"))
    except Exception:  # pragma: no cover
        log.exception("Model warm-up failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    threading.Thread(target=_warm_up, daemon=True).start()
    yield


app = FastAPI(
    title="InternAI API",
    version="1.0.0",
    description=(
        "Upload a resume and get the top-5 matching jobs/internships with match %, skill-gap explanations, "
        "course recommendations, a what-if simulator, a resume quality score and a 4-week roadmap. "
        "Matches are estimates from models trained on synthetic data."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if "*" not in CORS_ORIGINS else ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


# ---- optional: serve the built React app ---------------------------------- #
if (FRONTEND_DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": "InternAI API is running. Open /docs for the API documentation."}
