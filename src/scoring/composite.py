"""Composite scoring strategy with track-aware weight branching."""

from __future__ import annotations

from src.models.artifact import Artifact
from src.models.enums import InformationTrack, SourceTier, TIER_TO_TRACK
from src.models.profile import Profile
from src.scoring.authority import AuthorityStrategy
from src.scoring.base import BaseScoringStrategy
from src.scoring.relevance import RelevanceStrategy
from src.scoring.recency import RecencyStrategy

# Track-specific weight configurations
ACADEMIC_WEIGHTS = {"recency": 0.3, "authority": 0.2, "relevance": 0.5}
INDUSTRY_WEIGHTS = {"recency": 0.5, "authority": 0.1, "relevance": 0.4}
LEGACY_WEIGHTS = {"recency": 0.4, "authority": 0.3, "relevance": 0.3}


def _resolve_track(artifact: Artifact) -> InformationTrack | None:
    """Determine the information track for one artifact from its source_tier."""

    source_tier = (artifact.source_tier or "").strip()
    try:
        tier_enum = SourceTier(source_tier)
        return TIER_TO_TRACK.get(tier_enum)
    except ValueError:
        return None


def _weights_for_track(track: InformationTrack | None) -> dict[str, float]:
    """Return the weight configuration for one track."""

    if track == InformationTrack.ACADEMIC:
        return ACADEMIC_WEIGHTS
    if track == InformationTrack.INDUSTRY:
        return INDUSTRY_WEIGHTS
    return LEGACY_WEIGHTS


class CompositeStrategy(BaseScoringStrategy):
    """Combine multiple strategies into a track-aware final score."""

    def __init__(
        self,
        *,
        recency_strategy: BaseScoringStrategy | None = None,
        authority_strategy: BaseScoringStrategy | None = None,
        relevance_strategy: BaseScoringStrategy | None = None,
    ) -> None:
        """Initialize the composite strategy with sub-strategies."""

        self.recency_strategy = recency_strategy or RecencyStrategy()
        self.authority_strategy = authority_strategy or AuthorityStrategy()
        self.relevance_strategy = relevance_strategy or RelevanceStrategy()

    def calculate_score(self, artifact: Artifact, profile: Profile | None = None) -> float:
        """Return the weighted final score."""

        return self._clamp_score(self.calculate_breakdown(artifact, profile)["final_score"])

    def calculate_breakdown(self, artifact: Artifact, profile: Profile | None = None) -> dict[str, float | str]:
        """Return the individual strategy scores and the track-aware weighted score."""

        recency_score = self.recency_strategy.calculate_score(artifact, profile)
        authority_score = self.authority_strategy.calculate_score(artifact, profile)
        relevance_score = self.relevance_strategy.calculate_score(artifact, profile)

        track = _resolve_track(artifact)
        weights = _weights_for_track(track)
        total_weight = weights["recency"] + weights["authority"] + weights["relevance"]
        final_score = (
            (recency_score * weights["recency"])
            + (authority_score * weights["authority"])
            + (relevance_score * weights["relevance"])
        ) / total_weight

        track_label = track.value if track is not None else "legacy"

        return {
            "recency_score": recency_score,
            "authority_score": authority_score,
            "relevance_score": relevance_score,
            "final_score": self._clamp_score(final_score),
            "track": track_label,
            "weights": weights,
            "formula": f"final_score = recency*{weights['recency']} + authority*{weights['authority']} + relevance*{weights['relevance']} ({track_label})",
            "version": "phase3-v2",
        }

    def get_strategy_name(self) -> str:
        """Return the strategy name."""

        return "composite"
