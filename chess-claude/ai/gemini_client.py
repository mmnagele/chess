"""Gemini-Anbindung für MOVE/CHAT/COMMENTARY."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from config import GeminiSettings, load_gemini_settings

from .provider import (
    ChatRequest,
    ChatResponse,
    MoveGenerationProvider,
    MoveGenerationRequest,
    MoveGenerationResponse,
    ProviderConfig,
)


class GeminiClient(MoveGenerationProvider):
    """Implementierung des Provider-Protokolls über Gemini generateContent."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: GeminiSettings | None = None,
    ) -> None:
        self._settings = settings or load_gemini_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        payload = self._build_payload(request.system_prompt, request.user_prompt)
        response = self._post(payload)
        return MoveGenerationResponse(raw_text=self._extract_text(response))

    def chat(self, request: ChatRequest) -> ChatResponse:
        payload = self._build_payload(request.system_prompt, request.user_prompt)
        response = self._post(payload)
        return ChatResponse(raw_text=self._extract_text(response))

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": self.config.max_output_tokens,
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            ],
        }

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        model = urllib.parse.quote(self.config.model, safe="")
        base = self._settings.base_url.rstrip("/")
        api_key = urllib.parse.quote(self._settings.api_key)
        url = f"{base}/models/{model}:generateContent?key={api_key}"
        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("content-type", "application/json")

        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:  # pragma: no cover - Netzwerkpfad
            error_body = error.read().decode("utf-8", errors="replace")[:2000]
            raise RuntimeError(f"Gemini request failed: HTTP {error.code}: {error_body}") from error
        except urllib.error.URLError as error:  # pragma: no cover - Netzwerkpfad
            reason = str(error.reason) if hasattr(error, "reason") else str(error)
            if "handshake" in reason.lower() or "ssl" in reason.lower():
                raise RuntimeError(
                    f"Gemini request failed: SSL/TLS error ({reason}). "
                    f"Check network connectivity to generativelanguage.googleapis.com."
                ) from error
            if "timed out" in reason.lower():
                raise RuntimeError(
                    f"Gemini request failed: Connection timed out ({self.config.timeout}s). "
                    f"Check network connectivity or increase GEMINI_REQUEST_TIMEOUT."
                ) from error
            raise RuntimeError(f"Gemini request failed: {error}") from error

        return json.loads(body.decode("utf-8"))

    def _extract_text(self, response: dict[str, Any]) -> str:
        # Check for prompt-level blocking first
        feedback = response.get("promptFeedback", {})
        block_reason = feedback.get("blockReason")
        if block_reason:
            raise RuntimeError(
                f"Gemini blocked the prompt (reason: {block_reason}). "
                f"This is a safety filter issue, not a code bug."
            )

        candidates = response.get("candidates", [])
        if not candidates:
            raise RuntimeError(
                "Gemini returned no candidates. Response keys: " f"{list(response.keys())}"
            )

        for candidate in candidates:
            content = candidate.get("content", {})
            parts = content.get("parts", [])
            texts: list[str] = []
            for part in parts:
                text = part.get("text") if isinstance(part, dict) else None
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
            if texts:
                return "\n".join(texts)

        # No text found — extract diagnostic info from candidate
        first = candidates[0]
        finish = first.get("finishReason", "UNKNOWN")
        raise RuntimeError(
            f"Gemini returned empty content (finishReason: {finish}). "
            f"Model may have blocked this response."
        )


__all__ = ["GeminiClient"]
