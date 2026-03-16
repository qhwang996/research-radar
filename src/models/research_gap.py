"""ResearchGap ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, Integer, JSON, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampedModel


def _generate_uuid() -> str:
    """Return a string UUID for gap identifiers."""

    return str(uuid.uuid4())


class ResearchGap(TimestampedModel, Base):
    """A detected gap between academic coverage and industry demand."""

    __tablename__ = "research_gaps"

    gap_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_generate_uuid,
    )
    topic: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    demand_signals: Mapped[list[dict]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    demand_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    academic_coverage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gap_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, index=True)
    related_theme_ids: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    related_artifact_ids: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    generation_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="v1")
    week_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
