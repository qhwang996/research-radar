"""CandidateDirection ORM model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum, Float, JSON, String, Text
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampedModel
from src.models.enums import DirectionStatus


def _enum_values(enum_cls: type[DirectionStatus]) -> list[str]:
    """Return enum values for SQLAlchemy enum storage."""

    return [item.value for item in enum_cls]


def _generate_uuid() -> str:
    """Return a string UUID for direction identifiers."""

    return str(uuid.uuid4())


class CandidateDirection(TimestampedModel, Base):
    """A candidate research direction synthesized from gap analysis."""

    __tablename__ = "candidate_directions"

    direction_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_generate_uuid,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    rationale: Mapped[str | None] = mapped_column(Text)
    why_now: Mapped[str | None] = mapped_column(Text)
    gap_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    gap_score: Mapped[float | None] = mapped_column(Float)
    related_theme_ids: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    supporting_artifact_ids: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    key_papers: Mapped[list[dict[str, Any]]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    open_questions: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    novelty_score: Mapped[float | None] = mapped_column(Float)
    impact_score: Mapped[float | None] = mapped_column(Float)
    feasibility_score: Mapped[float | None] = mapped_column(Float)
    barrier_score: Mapped[float | None] = mapped_column(Float)
    composite_direction_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[DirectionStatus] = mapped_column(
        SAEnum(
            DirectionStatus,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
        default=DirectionStatus.ACTIVE,
    )
    generation_version: Mapped[str] = mapped_column(String(50), nullable=False, index=True, default="v1")
    week_id: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
