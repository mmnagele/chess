"""Anthropic provider client using the official Anthropic SDK."""

from __future__ import annotations

from typing import Any

from config import AnthropicSettings, load_anthropic_settings

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
    from anthropic import Anthropic
except Exception:  # pragma: no cover - optional dependency in local dev
    Anthropic = None  # type: ignore[assignment]


class AnthropicClient(MoveGenerationProvider):
    """Provider implementation using Anthropic Messages API via SDK."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: AnthropicSettings | None = None,
        retries: int = 2,
        backoff_initial: float = 0.4,
        backoff_factor: float = 2.0,
    ) -> None:
        if Anthropic is None:
            raise RuntimeError(
                "anthropic package not installed. Install with: pip install anthropic"
            )

        self._settings = settings or load_anthropic_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )
        self._retries = retries
        self._backoff_initial = backoff_initial
        self._backoff_factor = backoff_factor

        self._client = Anthropic(
            api_key=self._settings.api_key,
            base_url=self._settings.base_url,
            timeout=self.config.timeout,
        )

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        text = self._complete(request.system_prompt, request.user_prompt)
        return MoveGenerationResponse(raw_text=text)

    def chat(self, request: ChatRequest) -> ChatResponse:
        text = self._complete(request.system_prompt, request.user_prompt)
        return ChatResponse(raw_text=text)

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        def _operation() -> str:
            response = self._client.messages.create(
                model=self.config.model,
                system=system_prompt,
                max_tokens=self.config.max_output_tokens,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return self._extract_text(response)

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
            raise RuntimeError(f"Anthropic request failed: {message}") from exc

    def _extract_text(self, response: Any) -> str:
        content = getattr(response, "content", None)
        if not content:
            raise RuntimeError("Anthropic response contained no content.")

        texts: list[str] = []
        for part in content:
            block_type = getattr(part, "type", "")
            text = getattr(part, "text", "")
            if block_type == "text" and isinstance(text, str) and text.strip():
                texts.append(text.strip())

        if texts:
            return "\n".join(texts)

        raise RuntimeError("Anthropic response could not be interpreted.")


__all__ = ["AnthropicClient"]
