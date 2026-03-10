"""RawFetch-specific repository methods."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.enums import RawFetchStatus
from src.models.raw_fetch import RawFetch
from src.repositories.base import BaseRepository


class RawFetchRepository(BaseRepository[RawFetch]):
    """Repository for raw fetch tracking records."""

    def __init__(self, session: Session) -> None:
        """Create a raw fetch repository."""

        super().__init__(session, RawFetch)

    def get_by_file_path(self, file_path: str) -> RawFetch | None:
        """Return a raw fetch by its tracked file path."""

        statement = select(RawFetch).where(RawFetch.file_path == file_path)
        return self.session.scalar(statement)

    def list_by_status(self, status: RawFetchStatus) -> list[RawFetch]:
        """Return raw fetch records filtered by processing status."""

        statement = (
            select(RawFetch)
            .where(RawFetch.status == status)
            .order_by(RawFetch.updated_at.desc(), RawFetch.id.desc())
        )
        return list(self.session.scalars(statement))
