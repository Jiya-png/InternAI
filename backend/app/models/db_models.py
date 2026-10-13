"""Database tables."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Analysis(Base):
    """
    One analysed resume. The uploaded file itself is deleted right after
    parsing; only the extracted data and the results are stored.
    """

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    filename: Mapped[str] = mapped_column(String(255))
    parsed: Mapped[dict] = mapped_column(JSON)   # parser output (incl. text, needed for what-if)
    result: Mapped[dict] = mapped_column(JSON)   # recommender output
