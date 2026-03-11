"""Concrete HTTP adapters for supported LLM providers."""

from __future__ import annotations

import os
from typing import Any

import requests

from src.llm.base import LLMProvider, LLMProviderError, LLMResponse, LLMUsage, ModelTier, safe_int


OPENAI_RESPONSE_URL = "https://api.openai.com/v1/responses"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"


class OpenAIProvider(LLMProvider):
    """HTTP adapter for the OpenAI Responses API."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = OPENAI_RESPONSE_URL,
        session: requests.Session | Any | None = None,
    ) -> None:
        """Initialize the provider with optional overrides for tests."""

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.session = session or requests.Session()

    def default_model_map(self) -> dict[ModelTier, str]:
        """Return default OpenAI models for each tier."""

        return {
            ModelTier.FAST: "gpt-4o-mini",
            ModelTier.STANDARD: "gpt-4o",
            ModelTier.PREMIUM: "gpt-4.1",
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
        """Send one request to OpenAI and normalize the response payload."""

        self._require_api_key()
        payload = {
            "model": model,
            "input": prompt,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = self._post_json(headers=headers, payload=payload, timeout=timeout)
        text = str(data.get("output_text") or self._extract_openai_text(data))
        usage = self._parse_usage(data.get("usage"))
        return LLMResponse(text=text, model=str(data.get("model", model)), usage=usage)

    def _require_api_key(self) -> None:
        """Raise a provider error if the API key is missing."""

        if not self.api_key:
            raise LLMProviderError("Missing OPENAI_API_KEY", retryable=False)

    def _post_json(self, *, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        """POST JSON to OpenAI and return a parsed JSON object."""

        try:
            response = self.session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.Timeout as exc:
            raise LLMProviderError("OpenAI request timed out", retryable=True) from exc
        except requests.RequestException as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}", retryable=True) from exc

        return _handle_response(response, provider_name=self.provider_name)

    def _extract_openai_text(self, payload: dict[str, Any]) -> str:
        """Fallback parser for Responses API output blocks."""

        output = payload.get("output", [])
        if not isinstance(output, list):
            raise LLMProviderError("OpenAI response missing output text", retryable=False)

        texts: list[str] = []
        for item in output:
            for block in item.get("content", []):
                if block.get("type") == "output_text" and block.get("text"):
                    texts.append(str(block["text"]))
        if not texts:
            raise LLMProviderError("OpenAI response missing output text", retryable=False)
        return "".join(texts)

    def _parse_usage(self, usage_payload: Any) -> LLMUsage:
        """Normalize token usage fields from the OpenAI response."""

        if not isinstance(usage_payload, dict):
            return LLMUsage()
        input_tokens = safe_int(usage_payload.get("input_tokens"))
        output_tokens = safe_int(usage_payload.get("output_tokens"))
        total_tokens = safe_int(usage_payload.get("total_tokens"))
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


class AnthropicProvider(LLMProvider):
    """HTTP adapter for the Anthropic Messages API."""

    provider_name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = ANTHROPIC_MESSAGES_URL,
        session: requests.Session | Any | None = None,
    ) -> None:
        """Initialize the provider with optional overrides for tests."""

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = base_url
        self.session = session or requests.Session()

    def default_model_map(self) -> dict[ModelTier, str]:
        """Return default Anthropic models for each tier."""

        return {
            ModelTier.FAST: "claude-3-5-haiku-latest",
            ModelTier.STANDARD: "claude-3-5-sonnet-latest",
            ModelTier.PREMIUM: "claude-opus-4-6",
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
        """Send one request to Anthropic and normalize the response payload."""

        self._require_api_key()
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = self._post_json(headers=headers, payload=payload, timeout=timeout)
        text = self._extract_anthropic_text(data)
        usage = self._parse_usage(data.get("usage"))
        return LLMResponse(text=text, model=str(data.get("model", model)), usage=usage)

    def _require_api_key(self) -> None:
        """Raise a provider error if the API key is missing."""

        if not self.api_key:
            raise LLMProviderError("Missing ANTHROPIC_API_KEY", retryable=False)

    def _post_json(self, *, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        """POST JSON to Anthropic and return a parsed JSON object."""

        try:
            response = self.session.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.Timeout as exc:
            raise LLMProviderError("Anthropic request timed out", retryable=True) from exc
        except requests.RequestException as exc:
            raise LLMProviderError(f"Anthropic request failed: {exc}", retryable=True) from exc

        return _handle_response(response, provider_name=self.provider_name)

    def _extract_anthropic_text(self, payload: dict[str, Any]) -> str:
        """Extract concatenated text blocks from an Anthropic response."""

        content = payload.get("content", [])
        if not isinstance(content, list):
            raise LLMProviderError("Anthropic response missing content blocks", retryable=False)

        texts = [str(block.get("text", "")) for block in content if block.get("type") == "text"]
        text = "".join(texts).strip()
        if not text:
            raise LLMProviderError("Anthropic response missing text content", retryable=False)
        return text

    def _parse_usage(self, usage_payload: Any) -> LLMUsage:
        """Normalize token usage fields from the Anthropic response."""

        if not isinstance(usage_payload, dict):
            return LLMUsage()
        input_tokens = safe_int(usage_payload.get("input_tokens"))
        output_tokens = safe_int(usage_payload.get("output_tokens"))
        total_tokens = None
        if input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


def _handle_response(response: Any, *, provider_name: str) -> dict[str, Any]:
    """Normalize one provider HTTP response or raise a retry-aware error."""

    status_code = int(getattr(response, "status_code", 0))
    text = getattr(response, "text", "")

    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMProviderError(
            f"{provider_name} returned invalid JSON response: {text}",
            retryable=status_code >= 500,
        ) from exc

    if status_code in {429, 529}:
        raise LLMProviderError(f"{provider_name} rate limited the request", retryable=True)
    if status_code >= 500:
        raise LLMProviderError(
            f"{provider_name} server error ({status_code}): {_extract_error_message(payload, text)}",
            retryable=True,
        )
    if status_code >= 400:
        raise LLMProviderError(
            f"{provider_name} request failed ({status_code}): {_extract_error_message(payload, text)}",
            retryable=False,
        )
    if not isinstance(payload, dict):
        raise LLMProviderError(f"{provider_name} response must be a JSON object", retryable=False)
    return payload


def _extract_error_message(payload: Any, fallback: str) -> str:
    """Return a concise provider error message when available."""

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str):
            return error
        if payload.get("message"):
            return str(payload["message"])
    return fallback
