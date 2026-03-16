"""Route artifacts into academic or industry processing tracks."""

from __future__ import annotations

from src.models.artifact import Artifact
from src.models.enums import InformationTrack, SourceTier, TIER_TO_TRACK


def resolve_track(artifact: Artifact) -> InformationTrack | None:
    """Determine the information track for one artifact from its source_tier."""

    source_tier = (artifact.source_tier or "").strip()
    try:
        tier_enum = SourceTier(source_tier)
        return TIER_TO_TRACK.get(tier_enum)
    except ValueError:
        return None


def split_by_track(
    artifacts: list[Artifact],
) -> tuple[list[Artifact], list[Artifact]]:
    """Split artifacts into (academic, industry) lists.

    Artifacts with unrecognized tiers go into academic by default.
    """

    academic: list[Artifact] = []
    industry: list[Artifact] = []
    for artifact in artifacts:
        track = resolve_track(artifact)
        if track == InformationTrack.INDUSTRY:
            industry.append(artifact)
        else:
            academic.append(artifact)
    return academic, industry
