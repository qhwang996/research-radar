"""Shared enum definitions for ORM models."""

from __future__ import annotations

from enum import Enum


class ArtifactStatus(str, Enum):
    """Lifecycle states for an artifact."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class FeedbackTargetType(str, Enum):
    """Supported feedback targets."""

    ARTIFACT = "artifact"
    THEME = "theme"
    DIRECTION = "direction"


class FeedbackType(str, Enum):
    """Supported feedback categories."""

    LIKE = "like"
    DISLIKE = "dislike"
    PROS = "pros"
    CONS = "cons"
    NOTE = "note"
    READ = "read"


class SourceType(str, Enum):
    """Supported artifact source types."""

    PAPERS = "papers"
    BLOGS = "blogs"
    ADVISORIES = "advisories"
    BOOKMARKS = "bookmarks"


class ThemeStatus(str, Enum):
    """Lifecycle states for a research theme."""

    CANDIDATE = "candidate"
    CORE = "core"
    ARCHIVED = "archived"


class SourceTier(str, Enum):
    """Formalized source authority tiers aligned with dual-track architecture."""

    T1_CONFERENCE = "t1-conference"        # Top-4 security conferences
    T2_ARXIV = "t2-arxiv"                 # arXiv preprints
    T3_RESEARCH_BLOG = "t3-research-blog"  # Curated research blogs
    T4_PERSONAL = "t4-personal"            # Personal blogs, WeChat (future)


class InformationTrack(str, Enum):
    """Processing track assignment based on source tier."""

    ACADEMIC = "academic"    # T1 + T2
    INDUSTRY = "industry"    # T3 + T4


# Tier → Track mapping
TIER_TO_TRACK = {
    SourceTier.T1_CONFERENCE: InformationTrack.ACADEMIC,
    SourceTier.T2_ARXIV: InformationTrack.ACADEMIC,
    SourceTier.T3_RESEARCH_BLOG: InformationTrack.INDUSTRY,
    SourceTier.T4_PERSONAL: InformationTrack.INDUSTRY,
}


class DirectionStatus(str, Enum):
    """Lifecycle states for a candidate research direction."""

    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    ARCHIVED = "archived"


class RawFetchStatus(str, Enum):
    """Lifecycle states for raw fetch tracking records."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
