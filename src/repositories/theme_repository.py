"""Theme repository methods."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models.enums import ThemeStatus
from src.models.theme import Theme
from src.repositories.base import BaseRepository


class ThemeRepository(BaseRepository[Theme]):
    """Repository for theme persistence and lookup."""

    def __init__(self, session: Session) -> None:
        """Create a theme repository."""

        super().__init__(session, Theme)

    def get_by_theme_id(self, theme_id: str) -> Theme | None:
        """Return a theme by its stable business id."""

        statement = select(Theme).where(Theme.theme_id == theme_id)
        return self.session.scalar(statement)

    def list_by_status(self, status: ThemeStatus) -> list[Theme]:
        """Return themes filtered by lifecycle status."""

        statement = (
            select(Theme)
            .where(Theme.status == status)
            .order_by(Theme.created_at.desc(), Theme.id.desc())
        )
        return list(self.session.scalars(statement))

    def list_by_week(self, week_id: str) -> list[Theme]:
        """Return themes generated in the target ISO week."""

        statement = (
            select(Theme)
            .where(Theme.week_id == week_id)
            .order_by(Theme.created_at.desc(), Theme.id.desc())
        )
        return list(self.session.scalars(statement))

    def list_active_or_core(self) -> list[Theme]:
        """Return active candidate/core themes."""

        statement = (
            select(Theme)
            .where(or_(Theme.status == ThemeStatus.CANDIDATE, Theme.status == ThemeStatus.CORE))
            .order_by(Theme.created_at.desc(), Theme.id.desc())
        )
        return list(self.session.scalars(statement))

    def delete_candidates_by_version(self, generation_version: str) -> int:
        """Delete candidate themes for one generation version and return the row count."""

        statement = select(Theme).where(
            Theme.generation_version == generation_version,
            Theme.status == ThemeStatus.CANDIDATE,
        )
        records = list(self.session.scalars(statement))
        for record in records:
            self.session.delete(record)
        self.session.commit()
        return len(records)
