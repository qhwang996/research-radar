"""Composite scoring strategy."""

from __future__ import annotations

from src.models.artifact import Artifact
from src.models.profile import Profile
from src.scoring.authority import AuthorityStrategy
from src.scoring.base import BaseScoringStrategy
from src.scoring.recency import RecencyStrategy


class CompositeStrategy(BaseScoringStrategy):
    """Combine multiple strategies into a final Phase 1 score."""

    def __init__(
        self,
        *,
        recency_strategy: BaseScoringStrategy | None = None,
        authority_strategy: BaseScoringStrategy | None = None,
        recency_weight: float = 0.5,
        authority_weight: float = 0.5,
    ) -> None:
        """Initialize the weighted composite strategy."""

        self.recency_strategy = recency_strategy or RecencyStrategy()
        self.authority_strategy = authority_strategy or AuthorityStrategy()
        self.recency_weight = recency_weight
        self.authority_weight = authority_weight

    def calculate_score(self, artifact: Artifact, profile: Profile | None = None) -> float:
        """Return the weighted Phase 1 final score."""

        return self._clamp_score(self.calculate_breakdown(artifact, profile)["final_score"])

    def calculate_breakdown(self, artifact: Artifact, profile: Profile | None = None) -> dict[str, float | str]:
        """Return the individual strategy scores and the final weighted score."""

        recency_score = self.recency_strategy.calculate_score(artifact, profile)
        authority_score = self.authority_strategy.calculate_score(artifact, profile)
        total_weight = self.recency_weight + self.authority_weight
        final_score = (
            (recency_score * self.recency_weight) + (authority_score * self.authority_weight)
        ) / total_weight

        return {
            "recency_score": recency_score,
            "authority_score": authority_score,
            "final_score": self._clamp_score(final_score),
            "weights": {
                "recency": self.recency_weight,
                "authority": self.authority_weight,
            },
            "formula": "final_score = recency_score * 0.5 + authority_score * 0.5",
            "version": "phase1-v1",
        }

    def get_strategy_name(self) -> str:
        """Return the strategy name."""

        return "composite"
