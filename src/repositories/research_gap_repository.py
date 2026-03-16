"""ResearchGap repository methods."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.research_gap import ResearchGap
from src.repositories.base import BaseRepository


class ResearchGapRepository(BaseRepository[ResearchGap]):
    """Repository for research gap persistence and lookup."""

    def __init__(self, session: Session) -> None:
        """Create a research gap repository."""

        super().__init__(session, ResearchGap)

    def get_by_gap_id(self, gap_id: str) -> ResearchGap | None:
        """Return a gap by its stable business id."""

        statement = select(ResearchGap).where(ResearchGap.gap_id == gap_id)
        return self.session.scalar(statement)

    def list_by_week(self, week_id: str) -> list[ResearchGap]:
        """Return gaps detected in the target ISO week."""

        statement = (
            select(ResearchGap)
            .where(ResearchGap.week_id == week_id)
            .order_by(ResearchGap.gap_score.desc())
        )
        return list(self.session.scalars(statement))

    def list_active(self) -> list[ResearchGap]:
        """Return all active gaps ordered by score."""

        statement = (
            select(ResearchGap)
            .where(ResearchGap.status == "active")
            .order_by(ResearchGap.gap_score.desc())
        )
        return list(self.session.scalars(statement))

    def delete_by_version(self, generation_version: str) -> int:
        """Delete gaps for one generation version and return the row count."""

        statement = select(ResearchGap).where(
            ResearchGap.generation_version == generation_version,
        )
        records = list(self.session.scalars(statement))
        for record in records:
            self.session.delete(record)
        self.session.commit()
        return len(records)
