"""SQLAlchemy engine/session setup (SQLite by default)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import DATABASE_URL, DB_PATH

# URL.create handles Windows paths and spaces (e.g. "D:/intern ai/...") safely.
_url = make_url(DATABASE_URL) if DATABASE_URL else URL.create("sqlite", database=str(DB_PATH))
connect_args = {"check_same_thread": False} if _url.drivername.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    from app.models import db_models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
