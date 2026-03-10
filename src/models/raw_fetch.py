"""Raw fetch tracking ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampedModel
from src.models.enums import RawFetchStatus, SourceType


def _enum_values(enum_cls: type[RawFetchStatus] | type[SourceType]) -> list[str]:
    """Return enum values for SQLAlchemy enum storage."""

    return [item.value for item in enum_cls]


class RawFetch(TimestampedModel, Base):
    """Track raw JSON files processed by the normalization pipeline."""

    __tablename__ = "raw_fetches"

    file_path: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_type: Mapped[SourceType | None] = mapped_column(
        SAEnum(
            SourceType,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    source_name: Mapped[str | None] = mapped_column(String(100), index=True)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[RawFetchStatus] = mapped_column(
        SAEnum(
            RawFetchStatus,
            values_callable=_enum_values,
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
        default=RawFetchStatus.PENDING,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    normalize_version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1")
