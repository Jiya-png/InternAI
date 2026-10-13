"""Step 6 tests: FastAPI endpoints (uses a temporary SQLite DB, see conftest.py)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import UPLOAD_DIR
from app.main import app

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def uploaded(client) -> dict:
    with open(SAMPLES / "fresher_data_analyst.pdf", "rb") as fh:
        r = client.post("/api/upload", files={"file": ("ananya.pdf", fh, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_roles(client) -> None:
    r = client.get("/api/roles")
    assert r.status_code == 200 and len(r.json()) >= 25


def test_skills_search(client) -> None:
    r = client.get("/api/skills", params={"q": "dock"})
    assert any(s["name"] == "Docker" for s in r.json())


def test_upload_returns_parsed(uploaded) -> None:
    assert uploaded["parsed"]["name"] == "Ananya Krishnan"
    assert "SQL" in uploaded["parsed"]["skills"]
    assert len(uploaded["top_roles"]) == 5
    assert "text" not in uploaded["parsed"]


def test_upload_file_is_deleted(uploaded) -> None:
    assert not any(UPLOAD_DIR.glob("*")) if UPLOAD_DIR.exists() else True


def test_upload_docx(client) -> None:
    with open(SAMPLES / "experienced_backend.docx", "rb") as fh:
        r = client.post("/api/upload", files={"file": ("rahul.docx", fh, "application/octet-stream")})
    assert r.status_code == 201
    assert r.json()["top_roles"][0]["role_id"] in {"java_developer", "backend_developer"}


def test_analysis(client, uploaded) -> None:
    r = client.get(f"/api/analysis/{uploaded['analysis_id']}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["top_roles"]) == 5 and "quality" in body and body["disclaimer"]


def test_whatif(client, uploaded) -> None:
    r = client.post("/api/whatif", json={"analysis_id": uploaded["analysis_id"], "role": "Data Scientist",
                                          "extra_skills": ["Machine Learning", "scikit-learn"]})
    assert r.status_code == 200, r.text
    assert r.json()["new_match"] >= r.json()["base_match"]


def test_roadmap(client, uploaded) -> None:
    r = client.get(f"/api/roadmap/{uploaded['analysis_id']}", params={"role": "data_scientist"})
    assert r.status_code == 200 and len(r.json()["weeks"]) == 4


def test_errors(client, uploaded) -> None:
    assert client.get("/api/analysis/nope").status_code == 404
    r = client.post("/api/upload", files={"file": ("x.png", b"\x89PNG....", "image/png")})
    assert r.status_code == 415
    r = client.post("/api/upload", files={"file": ("fake.pdf", b"hello world", "application/pdf")})
    assert r.status_code == 415
    big = b"%PDF" + b"0" * (5 * 1024 * 1024 + 10)
    r = client.post("/api/upload", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413
    r = client.get(f"/api/roadmap/{uploaded['analysis_id']}", params={"role": "astronaut"})
    assert r.status_code == 404


def test_delete(client) -> None:
    with open(SAMPLES / "nontech_hr.pdf", "rb") as fh:
        aid = client.post("/api/upload", files={"file": ("s.pdf", fh, "application/pdf")}).json()["analysis_id"]
    assert client.delete(f"/api/analysis/{aid}").status_code == 204
    assert client.get(f"/api/analysis/{aid}").status_code == 404
