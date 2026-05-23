"""OpenAI provider client using the official OpenAI SDK."""

from __future__ import annotations

from typing import Any

from config import OpenAISettings, load_openai_settings

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
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency in local dev
    OpenAI = None  # type: ignore[assignment]


class OpenAIClient(MoveGenerationProvider):
    """Provider implementation using OpenAI chat completions."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: OpenAISettings | None = None,
        retries: int = 2,
        backoff_initial: float = 0.4,
        backoff_factor: float = 2.0,
    ) -> None:
        if OpenAI is None:
            raise RuntimeError("openai package not installed. Install with: pip install openai")

        self._settings = settings or load_openai_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )
        self._retries = retries
        self._backoff_initial = backoff_initial
        self._backoff_factor = backoff_factor

        kwargs: dict[str, Any] = {
            "api_key": self._settings.api_key,
            "base_url": self._settings.base_url,
            "timeout": self.config.timeout,
        }
        if self._settings.organization:
            kwargs["organization"] = self._settings.organization
        self._client = OpenAI(**kwargs)

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        text = self._complete(request.system_prompt, request.user_prompt)
        return MoveGenerationResponse(raw_text=text)

    def chat(self, request: ChatRequest) -> ChatResponse:
        text = self._complete(request.system_prompt, request.user_prompt)
        return ChatResponse(raw_text=text)

    def _complete(self, system_prompt: str, user_prompt: str) -> str:
        def _operation() -> str:
            return self._complete_with_compatibility_fallback(system_prompt, user_prompt)

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
            raise RuntimeError(f"OpenAI request failed: {message}") from exc

    def _complete_with_compatibility_fallback(self, system_prompt: str, user_prompt: str) -> str:
        token_params = self._token_parameter_order()
        include_temperature = not self._model_requires_default_temperature()
        temperature_modes = [include_temperature, False]

        attempted: set[tuple[str, bool]] = set()
        last_compat_error: Exception | None = None

        for token_param in token_params:
            for with_temperature in temperature_modes:
                key = (token_param, with_temperature)
                if key in attempted:
                    continue
                attempted.add(key)

                payload: dict[str, Any] = {
                    "model": self.config.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    token_param: self.config.max_output_tokens,
                }
                if with_temperature:
                    payload["temperature"] = self.config.temperature

                try:
                    response = self._client.with_options(
                        timeout=self.config.timeout
                    ).chat.completions.create(**payload)
                    return self._extract_text(response)
                except Exception as exc:  # pragma: no cover - exercised via tests with fakes
                    if self._is_param_compatibility_error(exc):
                        last_compat_error = exc
                        continue
                    raise

        if last_compat_error is not None:
            raise last_compat_error
        raise RuntimeError("OpenAI completion failed due incompatible request parameters.")

    def _token_parameter_order(self) -> tuple[str, str]:
        if self.config.model.lower().startswith("gpt-5"):
            return ("max_completion_tokens", "max_tokens")
        return ("max_tokens", "max_completion_tokens")

    def _model_requires_default_temperature(self) -> bool:
        return self.config.model.lower().startswith("gpt-5")

    @staticmethod
    def _is_param_compatibility_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "unsupported parameter" in message
            and ("max_tokens" in message or "max_completion_tokens" in message)
        ) or ("temperature" in message and "does not support" in message)

    def _extract_text(self, response: Any) -> str:
        choices = getattr(response, "choices", None)
        if not choices:
            raise RuntimeError("OpenAI response contained no choices.")

        message = choices[0].message
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            if parts:
                return "\n".join(parts)

        raise RuntimeError("OpenAI response could not be interpreted.")


__all__ = ["OpenAIClient"]
