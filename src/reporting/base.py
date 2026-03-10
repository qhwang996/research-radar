"""Base primitives shared by daily and weekly report generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime, time, timedelta, timezone
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.db.session import SessionLocal
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus
from src.repositories.artifact_repository import ArtifactRepository

logger = logging.getLogger(__name__)


class BaseReportGenerator(ABC):
    """Base class for report generators."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None = None,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize shared generator dependencies."""

        self.session_factory = session_factory or SessionLocal
        self.output_dir = (output_dir or Path("data/reports")).resolve()

    @abstractmethod
    def generate(self, target_date: date) -> Path:
        """Generate a report for the given target date."""

    @abstractmethod
    def render(self, context: dict) -> str:
        """Render the report context into a markdown string."""

    def _current_time(self) -> datetime:
        """Return the current UTC time truncated to minutes for stable output."""

        return datetime.now(timezone.utc).replace(second=0, microsecond=0)

    def _day_range(self, target_date: date) -> tuple[datetime, datetime]:
        """Return the UTC range covering one calendar day."""

        start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
        return start, start + timedelta(days=1)

    def _week_range(self, target_date: date) -> tuple[datetime, datetime]:
        """Return the Monday-to-Monday UTC range for the ISO week."""

        start_date = target_date - timedelta(days=target_date.weekday())
        start = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        return start, start + timedelta(days=7)

    def _load_scored_artifacts(
        self,
        start: datetime,
        end: datetime,
        status: ArtifactStatus = ArtifactStatus.ACTIVE,
    ) -> list[Artifact]:
        """Load scored artifacts in the target date range and warn on missing scores."""

        session = self.session_factory()
        try:
            repository = ArtifactRepository(session)
            missing_score_count = self._count_missing_scores(session, start, end, status)
            if missing_score_count:
                logger.warning(
                    "Skipping %s artifacts without final_score in report window %s -> %s",
                    missing_score_count,
                    start.isoformat(),
                    end.isoformat(),
                )
            return repository.list_by_date_range(start, end, status)
        finally:
            session.close()

    def _count_missing_scores(
        self,
        session: Session,
        start: datetime,
        end: datetime,
        status: ArtifactStatus,
    ) -> int:
        """Count artifacts in the window that are not yet scored."""

        statement = (
            select(func.count(Artifact.id))
            .where(Artifact.created_at >= start)
            .where(Artifact.created_at < end)
            .where(Artifact.status == status)
            .where(Artifact.final_score.is_(None))
        )
        return int(session.scalar(statement) or 0)

    def _write_report(self, subdirectory: str, filename: str, content: str) -> Path:
        """Write a rendered report to disk and return its path."""

        directory = self.output_dir / subdirectory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_text(content, encoding="utf-8")
        logger.info("Wrote report to %s", path)
        return path
