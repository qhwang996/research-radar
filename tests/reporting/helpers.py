"""Shared test helpers for report generation tests."""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus, SourceType


def make_artifact(
    title: str = "Test Paper",
    source_type: SourceType = SourceType.PAPERS,
    source_name: str = "IEEE S&P",
    source_tier: str = "top-tier",
    final_score: float = 0.9,
    recency_score: float = 0.8,
    authority_score: float = 1.0,
    year: int = 2026,
    created_at: datetime | None = None,
    **kwargs,
) -> Artifact:
    """Build an artifact with sensible defaults for reporting tests."""

    created = created_at or datetime(2026, 3, 10, 9, 0, tzinfo=timezone.utc)
    published_at = kwargs.pop("published_at", created)

    return Artifact(
        title=title,
        authors=kwargs.pop("authors", ["Alice Example"]),
        year=year,
        source_type=source_type,
        source_tier=source_tier,
        source_name=source_name,
        source_url=kwargs.pop("source_url", f"https://example.com/{title.lower().replace(' ', '-')}"),
        paper_url=kwargs.pop("paper_url", None),
        published_at=published_at,
        created_at=created,
        abstract=kwargs.pop("abstract", "Useful abstract text for report generation."),
        final_score=final_score,
        recency_score=recency_score,
        authority_score=authority_score,
        status=kwargs.pop("status", ArtifactStatus.ACTIVE),
        **kwargs,
    )
