"""Feedback event ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum as SAEnum, JSON, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampedModel
from src.models.enums import FeedbackTargetType, FeedbackType


def _enum_values(
    enum_cls: type[FeedbackTargetType] | type[FeedbackType],
) -> list[str]:
    """Return enum values for SQLAlchemy enum storage."""

    return [item.value for item in enum_cls]


def _generate_uuid() -> str:
    """Return a string UUID for event identifiers."""

    return str(uuid.uuid4())


class FeedbackEvent(TimestampedModel, Base):
    """Append-oriented record of user feedback."""

    __tablename__ = "feedback_events"

    event_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        default=_generate_uuid,
    )
    target_type: Mapped[FeedbackTargetType] = mapped_column(
        SAEnum(
            FeedbackTargetType,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feedback_type: Mapped[FeedbackType] = mapped_column(
        SAEnum(
            FeedbackType,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    content: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        default=datetime.utcnow,
    )
