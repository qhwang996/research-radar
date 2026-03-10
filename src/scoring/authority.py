"""Authority scoring strategy."""

from __future__ import annotations

from src.models.artifact import Artifact
from src.models.enums import SourceType
from src.models.profile import Profile
from src.scoring.base import BaseScoringStrategy


class AuthorityStrategy(BaseScoringStrategy):
    """Score artifacts by the authority of their source."""

    def calculate_score(self, artifact: Artifact, profile: Profile | None = None) -> float:
        """Return an authority score based on source metadata."""

        source_name = (artifact.source_name or "").lower()
        source_tier = (artifact.source_tier or "").lower()

        if source_tier == "top-tier":
            return 1.0
        if any(name in source_name for name in ["icse", "fse", "ase"]):
            return 0.8
        if artifact.source_type == SourceType.BLOGS or source_tier in {"high-quality-blog", "blog"}:
            return 0.7
        if artifact.source_type == SourceType.ADVISORIES:
            return self._clamp_score(self._advisory_score(artifact))
        if "arxiv" in source_name:
            return 0.5
        return 0.5

    def get_strategy_name(self) -> str:
        """Return the strategy name."""

        return "authority"

    def _advisory_score(self, artifact: Artifact) -> float:
        """Infer advisory authority from CVSS-like metadata when present."""

        for key in ["cvss_score", "cvss", "cvss_v3"]:
            raw_value = (artifact.external_ids or {}).get(key)
            if raw_value is None:
                continue
            try:
                score = float(raw_value)
            except (TypeError, ValueError):
                continue
            if score >= 7.0:
                return 0.9
            if score >= 4.0:
                return 0.7
            return 0.5
        return 0.5
