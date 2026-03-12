"""Tests for the LLM client cache and retry behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.exceptions import LLMError
from src.llm.base import LLMProvider, LLMProviderError, LLMResponse, LLMUsage, ModelTier
from src.llm.client import LLMClient


class StubProvider(LLMProvider):
    """Small provider stub with queued responses or failures."""

    provider_name = "stub"

    def __init__(self, outcomes: list[object] | None = None) -> None:
        """Initialize the stub provider with a deterministic outcome queue."""

        self.outcomes = list(outcomes or [])
        self.calls: list[dict[str, object]] = []

    def default_model_map(self) -> dict[ModelTier, str]:
        """Return fixed model names for all tiers."""

        return {
            ModelTier.FAST: "stub-fast",
            ModelTier.STANDARD: "stub-standard",
            ModelTier.PREMIUM: "stub-premium",
        }

    def generate(
        self,
        *,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout: float,
    ) -> LLMResponse:
        """Return the next queued response or raise the next queued error."""

        self.calls.append(
            {
                "prompt": prompt,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "timeout": timeout,
            }
        )
        if not self.outcomes:
            raise AssertionError("No queued outcome for stub provider")

        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class LLMClientTestCase(unittest.TestCase):
    """Unit tests for the top-level LLM client."""

    def setUp(self) -> None:
        """Create an isolated cache directory for each test."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name) / "cache"

    def tearDown(self) -> None:
        """Dispose test resources."""

        self.temp_dir.cleanup()

    def test_generate_uses_file_cache_across_client_instances(self) -> None:
        """A repeated cache_key should return the cached response without calling the provider again."""

        first_provider = StubProvider(
            [
                LLMResponse(
                    text="cached text",
                    model="stub-standard",
                    usage=LLMUsage(input_tokens=10, output_tokens=3, total_tokens=13),
                )
            ]
        )
        first_client = LLMClient(provider=first_provider, cache_dir=self.cache_dir)

        first_result = first_client.generate("hello world", cache_key="greeting")

        second_provider = StubProvider(
            [
                LLMResponse(
                    text="provider should not be used",
                    model="stub-standard",
                    usage=LLMUsage(input_tokens=99, output_tokens=99, total_tokens=198),
                )
            ]
        )
        second_client = LLMClient(provider=second_provider, cache_dir=self.cache_dir)

        second_result = second_client.generate("different prompt", cache_key="greeting")

        self.assertEqual(first_result, "cached text")
        self.assertEqual(second_result, "cached text")
        self.assertEqual(len(first_provider.calls), 1)
        self.assertEqual(second_provider.calls, [])

    def test_generate_retries_retryable_errors_then_succeeds(self) -> None:
        """Retryable provider errors should be retried with backoff before succeeding."""

        provider = StubProvider(
            [
                LLMProviderError("temporary outage", retryable=True),
                LLMProviderError("rate limit", retryable=True),
                LLMResponse(
                    text="eventual success",
                    model="stub-standard",
                    usage=LLMUsage(input_tokens=12, output_tokens=4, total_tokens=16),
                ),
            ]
        )
        sleeps: list[float] = []
        client = LLMClient(
            provider=provider,
            cache_dir=self.cache_dir,
            max_retries=3,
            backoff_base_seconds=0.25,
            sleep_fn=sleeps.append,
        )

        result = client.generate("retry please")

        self.assertEqual(result, "eventual success")
        self.assertEqual(len(provider.calls), 3)
        self.assertEqual(sleeps, [0.25, 0.5])
        self.assertEqual(client.last_usage.total_tokens, 16)

    def test_generate_raises_after_retry_exhaustion(self) -> None:
        """Retry exhaustion should surface an LLMError to callers."""

        provider = StubProvider(
            [
                LLMProviderError("temporary outage", retryable=True),
                LLMProviderError("still broken", retryable=True),
                LLMProviderError("failed again", retryable=True),
            ]
        )
        client = LLMClient(
            provider=provider,
            cache_dir=self.cache_dir,
            max_retries=2,
            sleep_fn=lambda _: None,
        )

        with self.assertRaises(LLMError):
            client.generate("this will fail")

        self.assertEqual(len(provider.calls), 3)

    def test_generate_raises_for_non_retryable_error_without_retry(self) -> None:
        """Non-retryable provider failures should fail immediately."""

        provider = StubProvider([LLMProviderError("bad request", retryable=False)])
        client = LLMClient(provider=provider, cache_dir=self.cache_dir, sleep_fn=lambda _: None)

        with self.assertRaises(LLMError):
            client.generate("bad input")

        self.assertEqual(len(provider.calls), 1)

    def test_generate_supports_gemini_provider_identifier(self) -> None:
        """The gemini provider string should resolve through the top-level client."""

        provider = StubProvider(
            [
                LLMResponse(
                    text="gemini text",
                    model="gemini-2.5-pro",
                    usage=LLMUsage(input_tokens=8, output_tokens=3, total_tokens=11),
                )
            ]
        )

        with patch("src.llm.client.GeminiProvider", return_value=provider):
            client = LLMClient(provider="gemini", cache_dir=self.cache_dir)
            result = client.generate("use gemini")

        self.assertEqual(result, "gemini text")
        self.assertEqual(len(provider.calls), 1)
