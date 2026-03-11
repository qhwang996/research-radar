"""Top-level LLM client with file cache and retry support."""

from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path
import time
from typing import Callable

from src.exceptions import LLMError
from src.llm.base import LLMProvider, LLMProviderError, LLMUsage, ModelTier
from src.llm.cache import FileLLMCache
from src.llm.providers import AnthropicProvider, OpenAIProvider

logger = logging.getLogger(__name__)


class LLMClient:
    """Tier-aware LLM client with filesystem cache and retry handling."""

    def __init__(
        self,
        *,
        provider: str | LLMProvider = "openai",
        cache_dir: Path | None = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        model_map: dict[ModelTier, str] | None = None,
    ) -> None:
        """Initialize the LLM client and resolve the provider."""

        self.provider = self._resolve_provider(provider)
        self.cache = FileLLMCache(cache_dir)
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.sleep_fn = sleep_fn
        self.model_map = model_map or self.provider.default_model_map()
        self.last_usage = LLMUsage()

    def generate(
        self,
        prompt: str,
        model_tier: ModelTier = ModelTier.STANDARD,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        cache_key: str | None = None,
    ) -> str:
        """Generate text from one prompt with optional cache and retries."""

        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                self.last_usage = LLMUsage(**_usage_from_metadata(cached.metadata))
                logger.info("LLM cache hit for key=%s provider=%s", cache_key, self.provider.provider_name)
                return cached.value

        model = self._resolve_model(model_tier)
        attempt = 0
        while True:
            try:
                response = self.provider.generate(
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=self.timeout,
                )
                self.last_usage = response.usage
                logger.info(
                    "LLM call succeeded provider=%s model=%s input_tokens=%s output_tokens=%s total_tokens=%s",
                    self.provider.provider_name,
                    response.model,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    response.usage.total_tokens,
                )
                if cache_key:
                    self.cache.set(
                        cache_key,
                        response.text,
                        metadata={
                            "provider": self.provider.provider_name,
                            "model": response.model,
                            "model_tier": model_tier.value,
                            "usage": asdict(response.usage),
                        },
                    )
                return response.text
            except LLMProviderError as exc:
                if exc.retryable and attempt < self.max_retries:
                    delay = self.backoff_base_seconds * (2**attempt)
                    attempt += 1
                    logger.warning(
                        "Retrying LLM call provider=%s attempt=%s/%s delay=%.2fs reason=%s",
                        self.provider.provider_name,
                        attempt,
                        self.max_retries,
                        delay,
                        exc,
                    )
                    self.sleep_fn(delay)
                    continue
                raise LLMError(str(exc)) from exc

    def _resolve_provider(self, provider: str | LLMProvider) -> LLMProvider:
        """Return a concrete provider instance from one identifier or object."""

        if isinstance(provider, LLMProvider):
            return provider

        normalized = provider.strip().lower()
        if normalized == "openai":
            return OpenAIProvider()
        if normalized == "anthropic":
            return AnthropicProvider()
        raise LLMError(f"Unsupported LLM provider: {provider}")

    def _resolve_model(self, model_tier: ModelTier) -> str:
        """Resolve one model tier into a concrete provider model name."""

        model = self.model_map.get(model_tier)
        if not model:
            raise LLMError(f"No model configured for tier: {model_tier.value}")
        return model


def _usage_from_metadata(metadata: dict[str, object]) -> dict[str, int | None]:
    """Return cached usage metadata in dataclass constructor shape."""

    usage_payload = metadata.get("usage", {})
    if not isinstance(usage_payload, dict):
        return {}
    return {
        "input_tokens": _safe_int(usage_payload.get("input_tokens")),
        "output_tokens": _safe_int(usage_payload.get("output_tokens")),
        "total_tokens": _safe_int(usage_payload.get("total_tokens")),
    }


def _safe_int(value: object) -> int | None:
    """Best-effort integer parsing for cached usage payloads."""

    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
