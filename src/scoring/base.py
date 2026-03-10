"""Shared scoring strategy primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.models.artifact import Artifact
from src.models.profile import Profile


class BaseScoringStrategy(ABC):
    """Base class for scoring strategies."""

    @abstractmethod
    def calculate_score(self, artifact: Artifact, profile: Profile | None = None) -> float:
        """Return a normalized score in the range [0.0, 1.0]."""

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the unique strategy name used in logs and score breakdowns."""

    def get_weight(self) -> float:
        """Return the default weight for this strategy."""

        return 1.0

    def _clamp_score(self, score: float) -> float:
        """Clamp a score into the valid range and round for stable persistence."""

        return round(max(0.0, min(1.0, score)), 4)
