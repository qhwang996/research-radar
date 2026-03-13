"""Tests for HTTP LLM provider adapters."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.llm.base import ModelTier
from src.llm.providers import AnthropicProvider, GeminiProvider, OpenAIProvider


class FakeResponse:
    """Small response stub that mimics requests.Response."""

    def __init__(self, status_code: int, payload: dict) -> None:
        """Store the response status code and JSON payload."""

        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> dict:
        """Return the configured JSON payload."""

        return self._payload


class FakeSession:
    """Session stub that captures POST requests."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        """Initialize the stub with queued responses."""

        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: float) -> FakeResponse:
        """Capture one POST call and return the next queued response."""

        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("No queued fake response")
        return self.responses.pop(0)


class OpenAIProviderTestCase(unittest.TestCase):
    """Tests for the OpenAI HTTP adapter."""

    def test_generate_posts_responses_api_payload_and_parses_output(self) -> None:
        """The OpenAI provider should speak the Responses API contract."""

        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "model": "gpt-4o",
                        "output_text": "openai reply",
                        "usage": {
                            "input_tokens": 15,
                            "output_tokens": 4,
                            "total_tokens": 19,
                        },
                    },
                )
            ]
        )
        provider = OpenAIProvider(api_key="test-key", base_url="https://api.openai.com/v1/responses", session=session)

        response = provider.generate(
            prompt="Summarize this paper",
            model="gpt-4o",
            max_tokens=256,
            temperature=0.2,
            timeout=42.0,
        )

        self.assertEqual(response.text, "openai reply")
        self.assertEqual(response.usage.total_tokens, 19)
        self.assertEqual(session.calls[0]["url"], "https://api.openai.com/v1/responses")
        self.assertEqual(session.calls[0]["json"]["input"], "Summarize this paper")
        self.assertEqual(session.calls[0]["json"]["max_output_tokens"], 256)
        self.assertEqual(session.calls[0]["timeout"], 42.0)

    def test_default_model_map_exposes_all_tiers(self) -> None:
        """The OpenAI provider should provide a model for each tier."""

        with patch.dict(os.environ, {}, clear=True):
            provider = OpenAIProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1/responses",
                session=FakeSession([]),
            )
            model_map = provider.default_model_map()

        self.assertIn(ModelTier.FAST, model_map)
        self.assertIn(ModelTier.STANDARD, model_map)
        self.assertIn(ModelTier.PREMIUM, model_map)
        self.assertEqual(model_map[ModelTier.PREMIUM], "gpt-5.4")

    def test_default_model_map_allows_env_overrides(self) -> None:
        """OpenAI model defaults should be overridable via env vars."""

        with patch.dict(
            os.environ,
            {
                "OPENAI_MODEL_FAST": "thirdparty-fast",
                "OPENAI_MODEL_STANDARD": "thirdparty-standard",
                "OPENAI_MODEL_PREMIUM": "thirdparty-premium",
            },
            clear=False,
        ):
            provider = OpenAIProvider(
                api_key="test-key",
                base_url="https://api.openai.com/v1/responses",
                session=FakeSession([]),
            )
            self.assertEqual(
                provider.default_model_map(),
                {
                    ModelTier.FAST: "thirdparty-fast",
                    ModelTier.STANDARD: "thirdparty-standard",
                    ModelTier.PREMIUM: "thirdparty-premium",
                },
            )


class AnthropicProviderTestCase(unittest.TestCase):
    """Tests for the Anthropic HTTP adapter."""

    def test_generate_posts_messages_payload_and_parses_text_blocks(self) -> None:
        """The Anthropic provider should parse text from message content blocks."""

        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "model": "claude-3-5-sonnet-latest",
                        "content": [
                            {"type": "text", "text": "first part"},
                            {"type": "text", "text": " second part"},
                        ],
                        "usage": {
                            "input_tokens": 20,
                            "output_tokens": 6,
                        },
                    },
                )
            ]
        )
        provider = AnthropicProvider(api_key="anthropic-key", base_url="https://api.anthropic.com/v1/messages", session=session)

        response = provider.generate(
            prompt="Explain the significance",
            model="claude-3-5-sonnet-latest",
            max_tokens=300,
            temperature=0.1,
            timeout=15.0,
        )

        self.assertEqual(response.text, "first part second part")
        self.assertEqual(response.usage.total_tokens, 26)
        self.assertEqual(session.calls[0]["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(
            session.calls[0]["json"]["messages"],
            [{"role": "user", "content": "Explain the significance"}],
        )
        self.assertEqual(session.calls[0]["json"]["max_tokens"], 300)
        self.assertEqual(session.calls[0]["timeout"], 15.0)

    def test_default_model_map_uses_latest_premium_alias(self) -> None:
        """The Anthropic provider should default PREMIUM to the latest alias."""

        with patch.dict(os.environ, {}, clear=True):
            provider = AnthropicProvider(
                api_key="anthropic-key",
                base_url="https://api.anthropic.com/v1/messages",
                session=FakeSession([]),
            )
            self.assertEqual(provider.default_model_map()[ModelTier.PREMIUM], "claude-opus-4-6")

    def test_default_model_map_allows_env_overrides(self) -> None:
        """Anthropic model defaults should be overridable via env vars."""

        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_MODEL_FAST": "thirdparty-haiku",
                "ANTHROPIC_MODEL_STANDARD": "thirdparty-sonnet",
                "ANTHROPIC_MODEL_PREMIUM": "thirdparty-opus",
            },
            clear=False,
        ):
            provider = AnthropicProvider(
                api_key="anthropic-key",
                base_url="https://api.anthropic.com/v1/messages",
                session=FakeSession([]),
            )
            self.assertEqual(
                provider.default_model_map(),
                {
                    ModelTier.FAST: "thirdparty-haiku",
                    ModelTier.STANDARD: "thirdparty-sonnet",
                    ModelTier.PREMIUM: "thirdparty-opus",
                },
            )


class GeminiProviderTestCase(unittest.TestCase):
    """Tests for the Gemini HTTP adapter."""

    def test_generate_posts_generate_content_payload_and_parses_text(self) -> None:
        """The Gemini provider should speak the generateContent API contract."""

        session = FakeSession(
            [
                FakeResponse(
                    200,
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {"text": "gemini reply"},
                                    ],
                                    "role": "model",
                                }
                            }
                        ],
                        "usageMetadata": {
                            "promptTokenCount": 10,
                            "candidatesTokenCount": 5,
                            "totalTokenCount": 15,
                        },
                    },
                )
            ]
        )
        provider = GeminiProvider(
            api_key="gemini-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/models",
            session=session,
        )

        response = provider.generate(
            prompt="Score this artifact",
            model="gemini-2.5-pro",
            max_tokens=128,
            temperature=0.1,
            timeout=12.0,
        )

        self.assertEqual(response.text, "gemini reply")
        self.assertEqual(response.usage.total_tokens, 15)
        self.assertEqual(
            session.calls[0]["url"],
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
        )
        self.assertEqual(
            session.calls[0]["json"]["contents"],
            [{"role": "user", "parts": [{"text": "Score this artifact"}]}],
        )
        self.assertEqual(session.calls[0]["json"]["generationConfig"]["maxOutputTokens"], 128)
        self.assertEqual(session.calls[0]["json"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(session.calls[0]["json"]["generationConfig"]["thinkingConfig"], {"thinkingBudget": 0})
        self.assertEqual(session.calls[0]["timeout"], 12.0)

    def test_default_model_map_prefers_more_capable_standard_model(self) -> None:
        """Gemini STANDARD should default to a more capable model than flash."""

        with patch.dict(os.environ, {}, clear=True):
            provider = GeminiProvider(
                api_key="gemini-key",
                base_url="https://generativelanguage.googleapis.com/v1beta/models",
                session=FakeSession([]),
            )
            self.assertEqual(provider.default_model_map()[ModelTier.FAST], "gemini-2.5-flash")
            self.assertEqual(provider.default_model_map()[ModelTier.STANDARD], "gemini-2.5-pro")
            self.assertEqual(provider.default_model_map()[ModelTier.PREMIUM], "gemini-3-pro-preview")

    def test_default_model_map_allows_env_overrides(self) -> None:
        """Gemini model defaults should be overridable via env vars."""

        with patch.dict(
            os.environ,
            {
                "GEMINI_MODEL_FAST": "thirdparty-flash",
                "GEMINI_MODEL_STANDARD": "thirdparty-pro",
                "GEMINI_MODEL_PREMIUM": "thirdparty-ultra",
            },
            clear=False,
        ):
            provider = GeminiProvider(
                api_key="gemini-key",
                base_url="https://generativelanguage.googleapis.com/v1beta/models",
                session=FakeSession([]),
            )
            self.assertEqual(
                provider.default_model_map(),
                {
                    ModelTier.FAST: "thirdparty-flash",
                    ModelTier.STANDARD: "thirdparty-pro",
                    ModelTier.PREMIUM: "thirdparty-ultra",
                },
            )
