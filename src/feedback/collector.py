"""Feedback collection service."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.exceptions import FeedbackError
from src.models.enums import FeedbackTargetType, FeedbackType
from src.models.feedback import FeedbackEvent
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.feedback_repository import FeedbackRepository


class FeedbackCollector:
    """Create append-only feedback events for persisted artifacts."""

    def __init__(self, *, session_factory: sessionmaker[Session] | None = None) -> None:
        """Initialize the collector with a session factory."""

        self.session_factory = session_factory or SessionLocal

    def collect_artifact_feedback(
        self,
        artifact_id: int,
        feedback_type: FeedbackType,
        note: str | None = None,
    ) -> FeedbackEvent:
        """Persist one feedback event for an artifact."""

        session = self.session_factory()
        try:
            artifact = ArtifactRepository(session).get_by_id(artifact_id)
            if artifact is None:
                raise FeedbackError(f"Artifact not found: {artifact_id}")

            content = {"type": feedback_type.value}
            cleaned_note = (note or "").strip()
            if cleaned_note:
                content["note"] = cleaned_note

            event = FeedbackEvent(
                target_type=FeedbackTargetType.ARTIFACT,
                target_id=str(artifact.id),
                feedback_type=feedback_type,
                content=content,
            )
            return FeedbackRepository(session).save(event)
        finally:
            session.close()
