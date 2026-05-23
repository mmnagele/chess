"""Kommentator-Logik für LLM-basierte Stellungseinschätzungen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from telemetry import TelemetryLogger

from .prompt_pack import load_prompt, render_prompt
from .provider import ChatRequest, MoveGenerationProvider

CommentatorType = Literal[
    "Adult Coach",
    "Parent + 5-Year-Old Coach",
    "Tournament Commentator",
]


@dataclass(frozen=True)
class Commentary:
    """Normalisierte Kommentator-Ausgabe."""

    text: str


class Commentator:
    """Verwaltet Prompt-Erstellung und Provider-Aufruf für Kommentartexte."""

    def __init__(
        self,
        provider: MoveGenerationProvider,
        *,
        telemetry: TelemetryLogger | None = None,
    ) -> None:
        self._provider = provider
        self.telemetry = telemetry or TelemetryLogger()

    def provide_commentary(
        self,
        *,
        commentator_type: CommentatorType,
        adult_side: str,
        fen_before: str,
        fen_after: str,
        last_move: str,
        move_number: int,
    ) -> Commentary:
        """Fordert eine strukturierte Kommentarantwort über den Provider an."""
        system_prompt = self._build_system_prompt(commentator_type, mode="COMMENTARY")
        user_prompt = render_prompt(
            "COMMENTATOR_EVENT_USER_TEMPLATE.md",
            {
                "COMMENTATOR_TYPE": commentator_type,
                "ADULT_SIDE": adult_side,
                "FEN_BEFORE": fen_before,
                "FEN_AFTER": fen_after,
                "LAST_MOVE": last_move,
                "MOVE_NUMBER": move_number,
            },
        )

        response = self._provider.chat(
            ChatRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        text = response.raw_text.strip()
        return Commentary(text=text or "Keine Einschätzung verfügbar.")

    def chat(self, commentator_type: CommentatorType, fen: str, user_message: str) -> Commentary:
        """Freier Nutzerchat mit dem Kommentator."""
        system_prompt = self._build_system_prompt(commentator_type, mode="CHAT")
        user_prompt = render_prompt(
            "COMMENTATOR_CHAT_USER_TEMPLATE.md",
            {
                "COMMENTATOR_TYPE": commentator_type,
                "FEN": fen,
                "USER_MESSAGE": user_message,
            },
        )
        response = self._provider.chat(
            ChatRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        text = response.raw_text.strip()
        return Commentary(text=text or "Keine Antwort erhalten.")

    @staticmethod
    def _system_template_for_type(commentator_type: CommentatorType) -> str:
        if commentator_type == "Adult Coach":
            return load_prompt("COMMENTATOR_SYSTEM_ADULT_COACH.md")
        if commentator_type == "Parent + 5-Year-Old Coach":
            return load_prompt("COMMENTATOR_SYSTEM_PARENT_CHILD.md")
        return load_prompt("COMMENTATOR_SYSTEM_TOURNAMENT.md")

    def _build_system_prompt(self, commentator_type: CommentatorType, *, mode: str) -> str:
        system = self._system_template_for_type(commentator_type)
        mode_hint = f"Current mode: {mode}. Follow the Output Contract for MODE={mode}."
        return "\n\n".join([system, mode_hint, load_prompt("FORMAT_CONTRACT.md")])

    def render(self, commentary: Commentary) -> str:
        """Render-Hook für UI-Kompatibilität."""

        return commentary.text


__all__ = [
    "Commentator",
    "Commentary",
    "CommentatorType",
]
