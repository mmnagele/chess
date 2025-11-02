"""OpenAI-Anbindung für die Zugerzeugung."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict

from config import OpenAISettings, load_openai_settings
from engine.game import Position

from .move_parser import IllegalMoveError, parse_move
from .provider import MoveGenerationProvider, MoveGenerationRequest, ProviderConfig


class OpenAIClient(MoveGenerationProvider):
    """Einfache Implementierung des :class:`MoveGenerationProvider` für OpenAI."""

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

    def generate_move(self, request: MoveGenerationRequest) -> tuple[Position, Position]:
        payload = self._build_payload(request)
        response = self._post("/responses", payload)
        candidate = self._extract_candidate(response)
        try:
            return parse_move(
                request.game,
                candidate,
                legal_moves=request.legal_moves,
            )
        except IllegalMoveError as exc:  # pragma: no cover - defensive fallback
            raise RuntimeError(f"OpenAI lieferte keinen legalen Zug: {exc}") from exc

    # ---------------- Private Helfer -----------------
    def _build_payload(self, request: MoveGenerationRequest) -> Dict[str, Any]:
        history_text = "\n".join(request.history)
        legal_moves = ", ".join(request.legal_moves)
        user_prompt = (
            f"FEN: {request.fen}\n"
            f"Erlaubte Züge (Koordinaten): {legal_moves}\n"
            "Gib genau einen Zug im Koordinatenformat (z.B. e2e4) zurück."
        )
        if history_text:
            user_prompt = f"Partieverlauf: {history_text}\n\n" + user_prompt

        instructions = request.instructions or (
            "Du bist ein Schach-Experte. Antworte ausschliesslich mit einem legalen Zug."
        )

        schema = {
            "name": "move_response",
            "schema": {
                "type": "object",
                "properties": {
                    "move": {
                        "type": "string",
                        "pattern": "^[a-h][1-8][a-h][1-8](?:[qrbn])?$",
                    }
                },
                "required": ["move"],
                "additionalProperties": False,
            },
        }

        return {
            "model": self.config.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": instructions,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": user_prompt,
                        }
                    ],
                },
            ],
            "temperature": self.config.temperature,
            "max_output_tokens": self.config.max_output_tokens,
            "response_format": {"type": "json_schema", "json_schema": schema},
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self._settings.api_key:
            raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt.")

        url = f"{self._settings.base_url.rstrip('/')}{path}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Authorization", f"Bearer {self._settings.api_key}")
        request.add_header("Content-Type", "application/json")
        if self._settings.organization:
            request.add_header("OpenAI-Organization", self._settings.organization)

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as error:  # pragma: no cover - Netzwerkpfad
            error_body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI-Fehler {error.code}: {error_body}") from error
        except urllib.error.URLError as error:  # pragma: no cover - Netzwerkpfad
            raise RuntimeError(f"OpenAI-Request fehlgeschlagen: {error}") from error
        finally:  # pragma: no cover - Telemetrie placeholder
            _ = time.perf_counter() - start

        return json.loads(body.decode("utf-8"))

    def _extract_candidate(self, response: Dict[str, Any]) -> Any:
        output = response.get("output", [])
        for item in output:
            for content in item.get("content", []):
                if "text" in content:
                    text = content["text"]
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
                tool_call = content.get("tool_call")
                if tool_call:
                    arguments = tool_call.get("arguments")
                    if isinstance(arguments, str):
                        try:
                            return json.loads(arguments)
                        except json.JSONDecodeError:
                            return arguments
                    return arguments

        # Fallback für ältere Chat-Completions-Antworten
        choices = response.get("choices")
        if choices:
            message = choices[0].get("message", {})
            if function_call := message.get("function_call"):
                arguments = function_call.get("arguments", "")
                try:
                    return json.loads(arguments)
                except json.JSONDecodeError:
                    return arguments
            if content := message.get("content"):
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content

        raise RuntimeError("Antwort konnte nicht interpretiert werden.")

