"""Tests for HTTP LLM provider adapters."""

from __future__ import annotations

import unittest

from src.llm.base import ModelTier
from src.llm.providers import AnthropicProvider, OpenAIProvider


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
        provider = OpenAIProvider(api_key="test-key", session=session)

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

        provider = OpenAIProvider(api_key="test-key", session=FakeSession([]))
        model_map = provider.default_model_map()

        self.assertIn(ModelTier.FAST, model_map)
        self.assertIn(ModelTier.STANDARD, model_map)
        self.assertIn(ModelTier.PREMIUM, model_map)


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
        provider = AnthropicProvider(api_key="anthropic-key", session=session)

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
