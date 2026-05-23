"""Gemini provider client using the official google-genai SDK."""

from __future__ import annotations

import json
from typing import Any
from urllib import request as urllib_request

from config import GeminiSettings, load_gemini_settings

from .client_utils import is_transient_error, run_with_retries, sanitize_error_message
from .provider import (
    ChatRequest,
    ChatResponse,
    MoveGenerationProvider,
    MoveGenerationRequest,
    MoveGenerationResponse,
    ProviderConfig,
)

try:  # pragma: no cover - optional dependency in local dev
    from google import genai
except Exception:  # pragma: no cover - optional dependency in local dev
    genai = None  # type: ignore[assignment]


class GeminiClient(MoveGenerationProvider):
    """Provider implementation using Gemini generate_content via SDK."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: GeminiSettings | None = None,
        retries: int = 2,
        backoff_initial: float = 0.4,
        backoff_factor: float = 2.0,
    ) -> None:
        if genai is None:
            raise RuntimeError(
                "google-genai package not installed. Install with: pip install google-genai"
            )

        self._settings = settings or load_gemini_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )
        self._retries = retries
        self._backoff_initial = backoff_initial
        self._backoff_factor = backoff_factor

        http_opts = {"timeout": self.config.timeout}
        self._client = genai.Client(
            api_key=self._settings.api_key,
            http_options=http_opts,
        )

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        text = self._complete(request.system_prompt, request.user_prompt)
        return MoveGenerationResponse(raw_text=text)

    def chat(self, request: ChatRequest) -> ChatResponse:
        text = self._complete(request.system_prompt, request.user_prompt)
        return ChatResponse(raw_text=text)

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        def _operation() -> str:
            try:
                response = self._client.models.generate_content(
                    model=self.config.model,
                    contents=user_prompt,
                    config={
                        "system_instruction": system_prompt,
                        "temperature": self.config.temperature,
                        "max_output_tokens": self.config.max_output_tokens,
                    },
                )
                return self._extract_text(response)
            except Exception as exc:
                if not self._is_sdk_transport_error(exc):
                    raise
                return self._complete_via_rest(system_prompt, user_prompt)

        try:
            return run_with_retries(
                _operation,
                retries=self._retries,
                backoff_initial=self._backoff_initial,
                backoff_factor=self._backoff_factor,
                is_retryable=is_transient_error,
            )
        except Exception as exc:
            message = sanitize_error_message(str(exc), secrets=[self._settings.api_key])
            raise RuntimeError(f"Gemini request failed: {message}") from exc

    def _complete_via_rest(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_output_tokens,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        endpoint = (
            f"{self._rest_api_root()}/models/{self.config.model}:generateContent"
            f"?key={self._settings.api_key}"
        )
        request = urllib_request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(request, timeout=self.config.timeout) as response:
            raw = response.read().decode("utf-8")
        parsed = json.loads(raw)
        return self._extract_text_from_rest_payload(parsed)

    def _rest_api_root(self) -> str:
        base_url = self._settings.base_url.rstrip("/")
        if base_url.endswith("/v1beta"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}beta"
        return f"{base_url}/v1beta"

    @staticmethod
    def _is_sdk_transport_error(exc: Exception) -> bool:
        name = type(exc).__name__
        message = str(exc).lower()
        transient_names = {
            "connecterror",
            "connectionerror",
            "readtimeout",
            "timeout",
            "timeouterror",
            "sslerror",
        }
        if name.lower() in transient_names:
            return True
        return (
            "network is unreachable" in message
            or "handshake operation timed out" in message
            or "timed out" in message
        )

    def _extract_text_from_rest_payload(self, payload: dict[str, Any]) -> str:
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise RuntimeError("Gemini REST response contained no candidates.")

        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            texts: list[str] = []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
            if texts:
                return "\n".join(texts)

        raise RuntimeError("Gemini REST response could not be interpreted.")

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()

        candidates = getattr(response, "candidates", None)
        if candidates:
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", None)
                if not parts:
                    continue
                texts: list[str] = []
                for part in parts:
                    value = getattr(part, "text", None)
                    if isinstance(value, str) and value.strip():
                        texts.append(value.strip())
                if texts:
                    return "\n".join(texts)

        raise RuntimeError("Gemini response could not be interpreted.")


__all__ = ["GeminiClient"]
