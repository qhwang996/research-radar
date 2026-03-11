"""Shared types and provider interface for LLM integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    """Supported model tiers used across enrichment workflows."""

    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


@dataclass(slots=True, frozen=True)
class LLMUsage:
    """Token usage metadata returned by an LLM provider."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True, frozen=True)
class LLMResponse:
    """Normalized provider response consumed by the top-level client."""

    text: str
    model: str
    usage: LLMUsage


class LLMProviderError(Exception):
    """Provider-specific error with retry semantics."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        """Store the error message and retryability flag."""

        super().__init__(message)
        self.retryable = retryable


class LLMProvider(ABC):
    """Abstract interface implemented by concrete LLM providers."""

    provider_name: str

    @abstractmethod
    def default_model_map(self) -> dict[ModelTier, str]:
        """Return default model names for each supported tier."""

    @abstractmethod
    def generate(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> LLMResponse:
        """Send one generation request and return normalized text output."""


def safe_int(value: object) -> int | None:
    """Best-effort integer parsing shared by client and provider layers."""

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
