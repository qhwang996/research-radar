"""Project-wide exception types."""


class ResearchRadarError(Exception):
    """Base exception for Research Radar."""


class CrawlerError(ResearchRadarError):
    """Raised when a crawler fails."""


class PipelineError(ResearchRadarError):
    """Raised when a pipeline fails."""


class LLMError(ResearchRadarError):
    """Raised when an LLM call fails."""


class DatabaseError(ResearchRadarError):
    """Raised when a database operation fails."""
