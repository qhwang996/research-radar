"""Recency scoring strategy."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.artifact import Artifact
from src.models.enums import SourceType
from src.models.profile import Profile
from src.scoring.base import BaseScoringStrategy


class RecencyStrategy(BaseScoringStrategy):
    """Score artifacts by freshness using source-aware decay curves."""

    def __init__(self, *, now: datetime | None = None) -> None:
        """Initialize the strategy with an optional fixed clock for tests."""

        self.now = self._normalize_datetime(now or datetime.now(timezone.utc))

    def calculate_score(self, artifact: Artifact, profile: Profile | None = None) -> float:
        """Return a recency score using source-specific decay rules."""

        reference_time = self._resolve_reference_time(artifact)
        if reference_time is None:
            return 0.5

        age_days = max(0.0, (self.now - reference_time).total_seconds() / 86400)
        source_name = (artifact.source_name or "").lower()
        source_tier = (artifact.source_tier or "").lower()

        if artifact.source_type == SourceType.BLOGS or "blog" in source_tier:
            score = self._score_by_days(age_days, [30, 90, 180, 365], [1.0, 0.95, 0.90, 0.80, 0.60])
        elif artifact.source_type == SourceType.ADVISORIES:
            score = self._score_by_days(age_days, [7, 28, 90, 180], [1.0, 0.95, 0.90, 0.80, 0.70])
        elif "arxiv" in source_name:
            score = self._score_by_days(age_days, [30, 90, 180], [1.0, 0.80, 0.60, 0.40])
        elif any(name in source_name for name in ["icse", "fse", "ase"]):
            score = self._score_by_days(age_days, [365, 730, 1095], [1.0, 0.90, 0.80, 0.60])
        else:
            score = self._score_by_days(age_days, [365, 730, 1095, 1825], [1.0, 0.95, 0.90, 0.80, 0.60])

        return self._clamp_score(score)

    def get_strategy_name(self) -> str:
        """Return the strategy name."""

        return "recency"

    def _resolve_reference_time(self, artifact: Artifact) -> datetime | None:
        """Resolve the best available timestamp for recency scoring."""

        if artifact.published_at is not None:
            return self._normalize_datetime(artifact.published_at)
        if artifact.fetched_at is not None:
            return self._normalize_datetime(artifact.fetched_at)
        if artifact.year is not None:
            # Mid-year fallback avoids biasing unknown dates too early or too late.
            return datetime(artifact.year, 7, 1, tzinfo=timezone.utc)
        return None

    def _normalize_datetime(self, value: datetime) -> datetime:
        """Normalize naive and aware datetimes into UTC-aware values."""

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _score_by_days(
        self,
        age_days: float,
        thresholds: list[int],
        scores: list[float],
    ) -> float:
        """Map age in days to a score using monotonically increasing thresholds."""

        for threshold, score in zip(thresholds, scores):
            if age_days <= threshold:
                return score
        return scores[-1]
