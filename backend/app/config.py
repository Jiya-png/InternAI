"""Central configuration (paths, limits, model names). Override via env vars."""
from __future__ import annotations

import os
from pathlib import Path

APP_DIR: Path = Path(__file__).resolve().parent            # backend/app
BACKEND_DIR: Path = APP_DIR.parent                         # backend
DATA_DIR: Path = APP_DIR / "data"
ARTIFACTS_DIR: Path = APP_DIR / "ml" / "artifacts"
UPLOAD_DIR: Path = Path(os.getenv("INTERNAI_UPLOAD_DIR", BACKEND_DIR / "uploads"))

DB_PATH: Path = BACKEND_DIR / "internai.db"
DATABASE_URL: str | None = os.getenv("INTERNAI_DB_URL")  # default: SQLite file at DB_PATH

MAX_UPLOAD_MB: int = int(os.getenv("INTERNAI_MAX_UPLOAD_MB", "5"))
ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx"}

# Comma separated list; "*" allows everything (fine for local use).
CORS_ORIGINS: list[str] = [o.strip() for o in os.getenv(
    "INTERNAI_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:8080"
).split(",") if o.strip()]

EMBEDDING_MODEL: str = os.getenv("INTERNAI_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
# Set INTERNAI_EMBEDDINGS=tfidf to skip sentence-transformers entirely (offline / low RAM).
EMBEDDINGS_BACKEND: str = os.getenv("INTERNAI_EMBEDDINGS", "auto")

RANDOM_SEED: int = 42
TOP_K_ROLES: int = 5

DISCLAIMER: str = (
    "Match percentages are estimates from a model trained on synthetic (computer-generated) resumes "
    "and a hand-built skills catalog. Use them as guidance, not as a hiring decision."
)
