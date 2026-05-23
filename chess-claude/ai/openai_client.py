"""OpenAI-Anbindung für MOVE/CHAT/COMMENTARY."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import OpenAISettings, load_openai_settings

from .provider import (
    ChatRequest,
    ChatResponse,
    MoveGenerationProvider,
    MoveGenerationRequest,
    MoveGenerationResponse,
    ProviderConfig,
)


class OpenAIClient(MoveGenerationProvider):
    """Implementierung des Provider-Protokolls über die OpenAI Responses API."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: OpenAISettings | None = None,
    ) -> None:
        self._settings = settings or load_openai_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        payload = self._build_payload(request.system_prompt, request.user_prompt)
        response = self._post_with_model_compatibility_fallback(payload)
        text = self._extract_text(response)
        return MoveGenerationResponse(raw_text=text)

    def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._build_payload(request.system_prompt, request.user_prompt)
        response = self._post_with_model_compatibility_fallback(payload)
        text = self._extract_text(response)
        return ChatResponse(raw_text=text)

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
            "input": [
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.base_url.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Authorization", f"Bearer {self._settings.api_key}")
        request.add_header("Content-Type", "application/json")
        if self._settings.organization:
            request.add_header("OpenAI-Organization", self._settings.organization)

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:  # pragma: no cover - Netzwerkpfad
            error_body = error.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(f"OpenAI request failed: HTTP {error.code}: {error_body}") from error
        except urllib.error.URLError as error:  # pragma: no cover - Netzwerkpfad
            raise RuntimeError(f"OpenAI request failed: {error}") from error

        return json.loads(body.decode("utf-8"))

    def _post_with_model_compatibility_fallback(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Retry request stripping unsupported parameters for stricter models."""

        try:
            return self._post("/responses", payload)
        except RuntimeError as exc:
            err = str(exc)
            if "Unsupported parameter" not in err:
                raise

            retry_payload = dict(payload)
            if "'temperature'" in err:
                retry_payload.pop("temperature", None)
            if "'max_tokens'" in err or "'max_output_tokens'" in err:
                retry_payload.pop("max_output_tokens", None)

            return self._post("/responses", retry_payload)

    def _extract_text(self, response: dict[str, Any]) -> str:
        output = response.get("output", [])
        for item in output:
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("text"):
                    return str(content["text"]).strip()

        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

        raise RuntimeError("OpenAI response could not be parsed.")


__all__ = ["OpenAIClient"]
