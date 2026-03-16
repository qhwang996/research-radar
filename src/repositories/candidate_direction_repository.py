"""CandidateDirection repository methods."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.candidate_direction import CandidateDirection
from src.models.enums import DirectionStatus
from src.repositories.base import BaseRepository


class CandidateDirectionRepository(BaseRepository[CandidateDirection]):
    """Repository for candidate direction persistence and lookup."""

    def __init__(self, session: Session) -> None:
        """Create a candidate direction repository."""

        super().__init__(session, CandidateDirection)

    def get_by_direction_id(self, direction_id: str) -> CandidateDirection | None:
        """Return a direction by its stable business id."""

        statement = select(CandidateDirection).where(CandidateDirection.direction_id == direction_id)
        return self.session.scalar(statement)

    def list_by_week(self, week_id: str) -> list[CandidateDirection]:
        """Return directions generated in the target ISO week."""

        statement = (
            select(CandidateDirection)
            .where(CandidateDirection.week_id == week_id)
            .order_by(CandidateDirection.composite_direction_score.desc().nullslast())
        )
        return list(self.session.scalars(statement))

    def list_by_status(self, status: DirectionStatus) -> list[CandidateDirection]:
        """Return directions filtered by status."""

        statement = (
            select(CandidateDirection)
            .where(CandidateDirection.status == status)
            .order_by(CandidateDirection.composite_direction_score.desc().nullslast())
        )
        return list(self.session.scalars(statement))

    def list_active(self) -> list[CandidateDirection]:
        """Return all active directions."""

        return self.list_by_status(DirectionStatus.ACTIVE)

    def delete_by_version(self, generation_version: str) -> int:
        """Delete directions for one generation version."""

        statement = select(CandidateDirection).where(
            CandidateDirection.generation_version == generation_version,
        )
        records = list(self.session.scalars(statement))
        for record in records:
            self.session.delete(record)
        self.session.commit()
        return len(records)
