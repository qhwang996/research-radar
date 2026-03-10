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


class SourceType(str, Enum):
    """Supported artifact source types."""

    PAPERS = "papers"
    BLOGS = "blogs"
    ADVISORIES = "advisories"
    BOOKMARKS = "bookmarks"


class RawFetchStatus(str, Enum):
    """Lifecycle states for raw fetch tracking records."""

    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
