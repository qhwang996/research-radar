"""Pure markdown formatting helpers for report generation."""

from __future__ import annotations

from datetime import date, datetime

from src.models.artifact import Artifact


SOURCE_TYPE_LABELS = {
    "papers": "Papers",
    "blogs": "Blogs",
    "advisories": "Advisories",
    "bookmarks": "Bookmarks",
}


def truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length, appending suffix when needed."""

    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[: max_length - len(suffix)].rstrip() + suffix


def format_score(
    final: float,
    recency: float | None,
    authority: float | None,
    relevance: float | None = None,
) -> str:
    """Format a score plus its component breakdown."""

    parts: list[str] = []
    if recency is not None:
        parts.append(f"recency: {recency:.2f}")
    if authority is not None:
        parts.append(f"authority: {authority:.2f}")
    if relevance is not None:
        parts.append(f"relevance: {relevance:.2f}")
    if not parts:
        return f"{final:.2f}"
    return f"{final:.2f} ({', '.join(parts)})"


def format_date(d: date | datetime | None, year: int | None = None) -> str:
    """Format a date value for report display."""

    if d is None:
        return str(year) if year is not None else "N/A"
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()


def format_source_type_label(source_type: object | None) -> str:
    """Return a friendly source-type label."""

    if source_type is None:
        return "Unknown"
    value = getattr(source_type, "value", str(source_type))
    return SOURCE_TYPE_LABELS.get(value, str(value).replace("_", " ").title())


def format_artifact_entry(
    artifact: Artifact,
    *,
    rank: int | None = None,
    show_abstract: bool = False,
    abstract_max_length: int = 200,
) -> str:
    """Render one artifact as a markdown block."""

    heading = f"### {rank}. [{artifact.title}]" if rank is not None else f"### [{artifact.title}]"
    lines = [
        heading,
        f"- **Source**: {artifact.source_name or 'Unknown'} ({format_source_type_label(artifact.source_type)})",
        f"- **Published**: {format_date(artifact.published_at, artifact.year)}",
        f"- **Score**: {format_score(artifact.final_score or 0.0, artifact.recency_score, artifact.authority_score, artifact.relevance_score)}",
        f"- **URL**: {artifact.source_url}",
    ]
    if show_abstract and artifact.abstract:
        lines.append(f"- **Abstract**: {truncate(artifact.abstract, abstract_max_length)}")
    return "\n".join(lines)
