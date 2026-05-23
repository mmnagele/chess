"""Kommentator-Logik für LLM-basierte Stellungseinschätzungen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from telemetry import TelemetryLogger

from .prompt_pack import load_prompt, render_prompt
from .provider import ChatRequest, MoveGenerationProvider

CommentatorType = Literal[
    "Adult Coach",
    "Parent + 5-Year-Old Coach",
    "Tournament Commentator",
]

_SYSTEM_PROMPT_FILES: dict[str, str] = {
    "Adult Coach": "COMMENTATOR_SYSTEM_ADULT_COACH.md",
    "Parent + 5-Year-Old Coach": "COMMENTATOR_SYSTEM_PARENT_CHILD.md",
    "Tournament Commentator": "COMMENTATOR_SYSTEM_TOURNAMENT.md",
}


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
        recent_moves: Sequence[str] = (),
    ) -> Commentary:
        """Fordert eine strukturierte Kommentarantwort über den Provider an."""

        system_prompt = self._build_system_prompt(commentator_type)
        user_prompt = render_prompt(
            "COMMENTATOR_EVENT_USER_TEMPLATE.md",
            {
                "COMMENTATOR_TYPE": commentator_type,
                "ADULT_SIDE": adult_side,
                "FEN_BEFORE": fen_before,
                "FEN_AFTER": fen_after,
                "LAST_MOVE": last_move,
                "MOVE_NUMBER": move_number,
                "RECENT_MOVES": "\n".join(recent_moves) if recent_moves else "-",
            },
        )

        response = self._provider.chat(
            ChatRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        text = response.raw_text.strip()
        return Commentary(text=text or "Keine Einschätzung verfügbar.")

    def chat(self, commentator_type: CommentatorType, fen: str, user_message: str) -> Commentary:
        """Freier Nutzerchat mit dem Kommentator."""

        system_prompt = self._build_system_prompt(commentator_type)
        user_prompt = "MODE=CHAT\n" f"Current FEN: {fen}\n\n" f"User message:\n{user_message}"
        response = self._provider.chat(
            ChatRequest(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        text = response.raw_text.strip()
        return Commentary(text=text or "Keine Antwort erhalten.")

    def render(self, commentary: Commentary) -> str:
        """Render-Hook für UI-Kompatibilität."""

        return commentary.text

    @staticmethod
    def _build_system_prompt(commentator_type: CommentatorType) -> str:
        filename = _SYSTEM_PROMPT_FILES.get(commentator_type, "COMMENTATOR_SYSTEM_TOURNAMENT.md")
        role_prompt = load_prompt(filename)
        contract = load_prompt("FORMAT_CONTRACT_COMMENTARY.md")
        return "\n\n".join([role_prompt, contract])


__all__ = [
    "Commentator",
    "Commentary",
    "CommentatorType",
]
