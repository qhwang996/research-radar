"""Batch scoring engine for persisted artifacts."""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus
from src.models.profile import Profile
from src.repositories.artifact_repository import ArtifactRepository
from src.repositories.profile_repository import ProfileRepository
from src.scoring.composite import CompositeStrategy

logger = logging.getLogger(__name__)


class ScoringEngine:
    """Apply scoring strategies to persisted artifacts and save the results."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        composite_strategy: CompositeStrategy | None = None,
    ) -> None:
        """Initialize the engine."""

        self.session_factory = session_factory or SessionLocal
        self.composite_strategy = composite_strategy or CompositeStrategy()

    def score_all(self, status: ArtifactStatus = ArtifactStatus.ACTIVE) -> list[Artifact]:
        """Score all artifacts matching the given lifecycle status."""

        session = self.session_factory()
        try:
            artifact_repository = ArtifactRepository(session)
            profile_repository = ProfileRepository(session)
            profile = profile_repository.get_latest_active() or profile_repository.get_latest()
            artifacts = artifact_repository.list_by_status(status)
            return self._score_and_persist(artifacts, artifact_repository, profile)
        finally:
            session.close()

    def score_artifacts(self, artifacts: Iterable[Artifact], profile: Profile | None = None) -> list[Artifact]:
        """Score a provided artifact iterable without loading them from the database."""

        session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            return self._score_and_persist(list(artifacts), repository, profile)
        finally:
            session.close()

    def _score_and_persist(
        self,
        artifacts: list[Artifact],
        repository: ArtifactRepository,
        profile: Profile | None,
    ) -> list[Artifact]:
        """Calculate and persist scores for the provided artifacts."""

        scored_artifacts: list[Artifact] = []
        for artifact in artifacts:
            breakdown = self.composite_strategy.calculate_breakdown(artifact, profile)
            existing_breakdown = dict(artifact.score_breakdown or {})
            existing_breakdown.update(breakdown)
            artifact.recency_score = float(breakdown["recency_score"])
            artifact.authority_score = float(breakdown["authority_score"])
            artifact.relevance_score = float(breakdown["relevance_score"])
            artifact.final_score = float(breakdown["final_score"])
            artifact.score_breakdown = existing_breakdown
            scored_artifacts.append(repository.save(artifact))

        scored_artifacts.sort(key=lambda item: (item.final_score or 0.0, item.id), reverse=True)
        logger.info("Scored %s artifacts", len(scored_artifacts))
        return scored_artifacts
