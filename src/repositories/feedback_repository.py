"""Feedback event repository methods."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.enums import FeedbackTargetType
from src.models.feedback import FeedbackEvent
from src.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[FeedbackEvent]):
    """Repository for feedback event persistence."""

    def __init__(self, session: Session) -> None:
        """Create a feedback repository."""

        super().__init__(session, FeedbackEvent)

    def get_by_event_id(self, event_id: str) -> FeedbackEvent | None:
        """Return a feedback event by its stable event id."""

        statement = select(FeedbackEvent).where(FeedbackEvent.event_id == event_id)
        return self.session.scalar(statement)

    def list_for_target(
        self,
        target_type: FeedbackTargetType,
        target_id: str,
    ) -> list[FeedbackEvent]:
        """Return all feedback events for a target ordered by time."""

        statement = (
            select(FeedbackEvent)
            .where(
                FeedbackEvent.target_type == target_type,
                FeedbackEvent.target_id == target_id,
            )
            .order_by(FeedbackEvent.timestamp.asc(), FeedbackEvent.id.asc())
        )
        return list(self.session.scalars(statement))
