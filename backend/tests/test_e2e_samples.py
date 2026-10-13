"""
Step 8: end-to-end check with 5 real-style resumes (fresher, experienced,
non-tech, ML student, marketer) through the HTTP API.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"

CASES = [
    ("fresher_data_analyst.pdf", {"data_analyst"}),
    ("experienced_backend.docx", {"java_developer", "backend_developer"}),
    ("nontech_hr.pdf", {"hr_associate"}),
    ("ml_student.docx", {"nlp_engineer", "data_scientist", "ml_engineer"}),
    ("digital_marketer.pdf", {"digital_marketing_analyst"}),
]


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize("filename, expected", CASES)
def test_sample_resume_end_to_end(client, filename: str, expected: set[str]) -> None:
    with open(SAMPLES / filename, "rb") as fh:
        r = client.post("/api/upload", files={"file": (filename, fh, "application/octet-stream")})
    assert r.status_code == 201, r.text
    aid = r.json()["analysis_id"]
    a = client.get(f"/api/analysis/{aid}").json()
    top1 = a["top_roles"][0]
    assert top1["role_id"] in expected, [x["role_id"] for x in a["top_roles"]]
    assert top1["match"] >= 60
    assert 40 <= a["quality"]["score"] <= 100
    # what-if on the top role's first missing skill never lowers the score
    missing = [m["skill"] for m in top1["missing_required"]][:1]
    w = client.post("/api/whatif", json={"analysis_id": aid, "role": top1["role_id"], "extra_skills": missing}).json()
    assert w["new_match"] >= w["base_match"]
    rm = client.get(f"/api/roadmap/{aid}", params={"role": top1["role_id"]}).json()
    assert len(rm["weeks"]) == 4
