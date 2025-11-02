"""Kommentator-Logik für LLM-basierte Stellungseinschätzungen."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, MutableSequence, Protocol, Sequence

from engine.fen import export_fen
from engine.game import ChessGame
from telemetry import TelemetryLogger


@dataclass(frozen=True)
class CommentaryContext:
    """Kontextdaten, die in den Prompt einfliessen."""

    fen: str
    history: tuple[str, ...]
    evaluation: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class CommentaryPrompt:
    """Strukturierter Prompt für den Kommentator."""

    system_message: str
    user_message: str
    response_schema: Mapping[str, Any]
    context: CommentaryContext

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system_message,
            "user": self.user_message,
            "schema": self.response_schema,
            "context": {
                "fen": self.context.fen,
                "history": list(self.context.history),
                "evaluation": dict(self.context.evaluation) if self.context.evaluation else None,
            },
        }


class CommentaryProvider(Protocol):
    """Protokoll für Anbieter, die Stellungskommentare erzeugen."""

    def generate_commentary(self, prompt: CommentaryPrompt) -> Mapping[str, Any]:
        """Liefert Rohdaten entsprechend dem Schema im Prompt."""


@dataclass(frozen=True)
class Commentary:
    """Normalisierte Kommentator-Ausgabe."""

    variant_hint: str | None = None
    eval_trend: str | None = None
    key_ideas: tuple[str, ...] = ()
    blunders_last_moves: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_hint": self.variant_hint,
            "eval_trend": self.eval_trend,
            "key_ideas": list(self.key_ideas),
            "blunders_last_moves": list(self.blunders_last_moves),
        }


class LocalCommentaryProvider(CommentaryProvider):
    """Heuristische Fallback-Implementierung ohne LLM-Aufruf."""

    def generate_commentary(self, prompt: CommentaryPrompt) -> Mapping[str, Any]:
        context = prompt.context
        history = context.history
        last_move = history[-1] if history else "Noch kein Zug"
        eval_hint = context.evaluation or {}
        score = eval_hint.get("material", 0)
        if isinstance(score, (int, float)):
            if score > 0:
                trend = "Weiss hat Materialvorteil"
            elif score < 0:
                trend = "Schwarz liegt materiell vorne"
            else:
                trend = "Material ausgeglichen"
        else:
            trend = "Ausgleichliche Stellung"

        ideas: MutableSequence[str] = []
        if "K" in context.fen.split()[0]:
            ideas.append("Königssicherheit beobachten")
        if len(history) >= 6:
            ideas.append("Mittespiel mit mehreren Figurenentwicklungen")
        elif len(history) >= 2:
            ideas.append("Entwicklung und Zentrumskontrolle im Fokus")
        else:
            ideas.append("Partie beginnt – Figuren entwickeln")

        blunders: list[str] = []
        if eval_hint.get("last_blunder"):
            blunders.append(str(eval_hint["last_blunder"]))

        return {
            "variant_hint": last_move,
            "eval_trend": trend,
            "key_ideas": ideas,
            "blunders_last_moves": blunders,
        }


class Commentator:
    """Verwaltet Prompt-Erstellung, Provider-Aufruf und Validierung."""

    def __init__(
        self,
        provider: CommentaryProvider | None = None,
        *,
        telemetry: TelemetryLogger | None = None,
        max_history: int = 6,
    ) -> None:
        self._provider = provider or LocalCommentaryProvider()
        self.telemetry = telemetry or TelemetryLogger()
        self.max_history = max_history

    # ------------------------------------------------------------------
    # Öffentliche API
    def build_prompt(
        self,
        game: ChessGame,
        *,
        history: Sequence[str] = (),
        evaluation: Mapping[str, Any] | None = None,
    ) -> CommentaryPrompt:
        context = CommentaryContext(
            fen=export_fen(game),
            history=tuple(history[-self.max_history :]),
            evaluation=evaluation,
        )
        system_message = (
            "Du bist ein deutschsprachiger Schachkommentator. "
            "Analysiere kurz und strukturiert die Stellung."
        )
        history_text = "\n".join(f"- {entry}" for entry in context.history)
        if history_text:
            history_text = f"Letzte Züge:\n{history_text}\n\n"
        evaluation_text = ""
        if evaluation:
            eval_lines = [f"{key}: {value}" for key, value in evaluation.items()]
            evaluation_text = "Bewertungen:\n" + "\n".join(f"- {line}" for line in eval_lines) + "\n\n"
        user_message = (
            f"FEN: {context.fen}\n"
            f"{history_text}"
            f"{evaluation_text}"
            "Gib eine knappe JSON-Zusammenfassung der Stellung zurück."
        ).strip()
        schema = {
            "type": "object",
            "properties": {
                "variant_hint": {"type": ["string", "null"], "maxLength": 160},
                "eval_trend": {"type": ["string", "null"], "maxLength": 160},
                "key_ideas": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 160},
                },
                "blunders_last_moves": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": 160},
                },
            },
            "required": ["key_ideas", "blunders_last_moves"],
            "additionalProperties": False,
        }
        return CommentaryPrompt(
            system_message=system_message,
            user_message=user_message,
            response_schema=schema,
            context=context,
        )

    def provide_commentary(
        self,
        game: ChessGame,
        *,
        history: Sequence[str] = (),
        evaluation: Mapping[str, Any] | None = None,
    ) -> Commentary:
        prompt = self.build_prompt(game, history=history, evaluation=evaluation)
        start = time.perf_counter()
        raw = self._provider.generate_commentary(prompt)
        duration = (time.perf_counter() - start) * 1000
        commentary = self._normalise_response(raw)
        self.telemetry.record(
            phase="commentary",
            message="Kommentar erzeugt",
            duration_ms=duration,
            metadata={
                "history_length": len(prompt.context.history),
                "raw_response": json.dumps(raw, ensure_ascii=False, default=str),
            },
        )
        return commentary

    def render(self, commentary: Commentary) -> str:
        lines: list[str] = []
        if commentary.variant_hint:
            lines.append(f"Letzter Impuls: {commentary.variant_hint}")
        if commentary.eval_trend:
            lines.append(f"Bewertung: {commentary.eval_trend}")
        if commentary.key_ideas:
            lines.append("Ideen:")
            lines.extend(f" • {idea}" for idea in commentary.key_ideas)
        if commentary.blunders_last_moves:
            lines.append("Fehler zuletzt:")
            lines.extend(f" • {entry}" for entry in commentary.blunders_last_moves)
        if not lines:
            lines.append("Keine Einschätzung verfügbar.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Interne Helfer
    def _normalise_response(self, payload: Mapping[str, Any]) -> Commentary:
        if not isinstance(payload, Mapping):
            raise ValueError("Kommentator-Antwort muss ein Mapping sein.")

        def _optional_str(value: Any) -> str | None:
            if value is None:
                return None
            if not isinstance(value, str):
                raise ValueError("Erwartete Zeichenkette in Kommentator-Antwort.")
            stripped = value.strip()
            return stripped or None

        def _string_list(name: str, value: Any) -> tuple[str, ...]:
            if value is None:
                return ()
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                raise ValueError(f"Feld '{name}' muss eine Liste von Strings sein.")
            result: list[str] = []
            for item in value:
                if not isinstance(item, str):
                    raise ValueError(f"Feld '{name}' muss Strings enthalten.")
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
            return tuple(result)

        try:
            variant_hint = _optional_str(payload.get("variant_hint"))
            eval_trend = _optional_str(payload.get("eval_trend"))
            key_ideas = _string_list("key_ideas", payload.get("key_ideas", ()))
            blunders = _string_list(
                "blunders_last_moves", payload.get("blunders_last_moves", ())
            )
        except AttributeError as exc:  # pragma: no cover - defensive
            raise ValueError("Ungültige Kommentator-Antwort.") from exc

        return Commentary(
            variant_hint=variant_hint,
            eval_trend=eval_trend,
            key_ideas=key_ideas,
            blunders_last_moves=blunders,
        )


__all__ = [
    "Commentator",
    "Commentary",
    "CommentaryPrompt",
    "CommentaryProvider",
    "CommentaryContext",
    "LocalCommentaryProvider",
]
