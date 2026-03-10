"""Artifact-specific repository methods."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus
from src.repositories.base import BaseRepository


class ArtifactRepository(BaseRepository[Artifact]):
    """Repository for artifact persistence and lookup."""

    def __init__(self, session: Session) -> None:
        """Create an artifact repository."""

        super().__init__(session, Artifact)

    def get_by_canonical_id(self, canonical_id: str) -> Artifact | None:
        """Return an artifact by its business key."""

        statement = select(Artifact).where(Artifact.canonical_id == canonical_id)
        return self.session.scalar(statement)

    def list_by_status(self, status: ArtifactStatus = ArtifactStatus.ACTIVE) -> list[Artifact]:
        """Return artifacts filtered by lifecycle status."""

        statement = (
            select(Artifact)
            .where(Artifact.status == status)
            .order_by(Artifact.created_at.desc(), Artifact.id.desc())
        )
        return list(self.session.scalars(statement))

    def list_by_date_range(
        self,
        start: datetime,
        end: datetime,
        status: ArtifactStatus = ArtifactStatus.ACTIVE,
    ) -> list[Artifact]:
        """Return scored artifacts whose created_at falls within [start, end)."""

        statement = (
            select(Artifact)
            .where(Artifact.created_at >= start)
            .where(Artifact.created_at < end)
            .where(Artifact.status == status)
            .where(Artifact.final_score.is_not(None))
            .order_by(Artifact.final_score.desc(), Artifact.created_at.desc(), Artifact.id.desc())
        )
        return list(self.session.scalars(statement))
