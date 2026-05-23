"""Anthropic-Anbindung für MOVE/CHAT/COMMENTARY."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import AnthropicSettings, load_anthropic_settings

from .provider import (
    ChatRequest,
    ChatResponse,
    MoveGenerationProvider,
    MoveGenerationRequest,
    MoveGenerationResponse,
    ProviderConfig,
)


class AnthropicClient(MoveGenerationProvider):
    """Implementierung des Provider-Protokolls über Anthropic Messages API."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: AnthropicSettings | None = None,
    ) -> None:
        self._settings = settings or load_anthropic_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        payload = self._build_payload(request.system_prompt, request.user_prompt)
        response = self._post("/messages", payload)
        return MoveGenerationResponse(raw_text=self._extract_text(response))

    def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._build_payload(request.system_prompt, request.user_prompt)
        response = self._post("/messages", payload)
        return ChatResponse(raw_text=self._extract_text(response))

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "model": self.config.model,
            "max_tokens": self.config.max_output_tokens,
            "temperature": self.config.temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.base_url.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("x-api-key", self._settings.api_key)
        request.add_header("anthropic-version", "2023-06-01")
        request.add_header("content-type", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:  # pragma: no cover - Netzwerkpfad
            error_body = error.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(
                f"Anthropic request failed: HTTP {error.code} for model "
                f"'{payload.get('model', '?')}': {error_body}"
            ) from error
        except urllib.error.URLError as error:  # pragma: no cover - Netzwerkpfad
            raise RuntimeError(f"Anthropic request failed: {error}") from error

        return json.loads(body.decode("utf-8"))

    def _extract_text(self, response: dict[str, Any]) -> str:
        content = response.get("content", [])
        texts: list[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = str(part.get("text", "")).strip()
                if text:
                    texts.append(text)
        joined = "\n".join(texts).strip()
        if joined:
            return joined
        raise RuntimeError("Anthropic response could not be parsed.")


__all__ = ["AnthropicClient"]
