"""Artifact ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, Float, Integer, JSON, String, Text
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampedModel
from src.models.enums import ArtifactStatus, SourceType


def _enum_values(enum_cls: type[ArtifactStatus] | type[SourceType]) -> list[str]:
    """Return enum values for SQLAlchemy enum storage."""

    return [item.value for item in enum_cls]


def _generate_uuid() -> str:
    """Return a string UUID for SQLite-friendly business keys."""

    return str(uuid.uuid4())


class Artifact(TimestampedModel, Base):
    """Normalized content entity used across scoring and reporting."""

    __tablename__ = "artifacts"

    canonical_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_generate_uuid,
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    authors: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    year: Mapped[int | None] = mapped_column(Integer, index=True)
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(
            SourceType,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    source_tier: Mapped[str | None] = mapped_column(String(50), index=True)
    source_name: Mapped[str | None] = mapped_column(String(100), index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    paper_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    abstract: Mapped[str | None] = mapped_column(Text)
    summary_l1: Mapped[str | None] = mapped_column(Text)
    summary_l2: Mapped[str | None] = mapped_column(Text)
    summary_l3: Mapped[str | None] = mapped_column(Text)

    raw_content_path: Mapped[str | None] = mapped_column(String(255))
    external_ids: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    tags: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    recency_score: Mapped[float | None] = mapped_column(Float)
    authority_score: Mapped[float | None] = mapped_column(Float)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    final_score: Mapped[float | None] = mapped_column(Float, index=True)

    status: Mapped[ArtifactStatus] = mapped_column(
        SAEnum(
            ArtifactStatus,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
        default=ArtifactStatus.ACTIVE,
    )
    normalize_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
