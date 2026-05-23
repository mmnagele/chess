"""Schnittstellen und Grundkonfiguration für KI-Zuganbieter."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from engine.game import ChessGame, Position


@dataclass
class ProviderConfig:
    """Konfigurationsparameter für einen LLM-Zuganbieter."""

    model: str
    temperature: float = 0.2
    max_output_tokens: int = 2048
    timeout: float = 30.0


@dataclass
class MoveGenerationRequest:
    """Kontextinformationen für eine Zuganfrage an ein LLM."""

    game: ChessGame
    fen: str
    legal_moves: Sequence[str]
    history: Sequence[str] = ()
    side_to_move: str = "white"
    last_move: str = "-"
    system_prompt: str = ""
    user_prompt: str = ""


@dataclass
class MoveGenerationResponse:
    """Normalisierte Antwort einer MOVE-Anfrage."""

    raw_text: str


@dataclass
class ChatRequest:
    """Kontext für freie Chat-Nachrichten."""

    system_prompt: str
    user_prompt: str


@dataclass
class ChatResponse:
    """Normalisierte Antwort einer CHAT/COMMENTARY-Anfrage."""

    raw_text: str


class MoveGenerationProvider(Protocol):
    """Protokoll für KI-Anbieter, die Schachzüge generieren und chatten."""

    config: ProviderConfig

    def generate_move(self, request: MoveGenerationRequest) -> MoveGenerationResponse:
        """Erzeugt einen Zug als Rohtext."""

    def chat(self, request: ChatRequest) -> ChatResponse:
        """Erzeugt freie Textantworten (Chat oder Commentary)."""


@dataclass
class MoveSuggestion:
    """Durch den Strategen validierter Zugvorschlag."""

    start: Position
    end: Position
    move_text: str
    raw_response: str


__all__ = [
    "ProviderConfig",
    "MoveGenerationRequest",
    "MoveGenerationResponse",
    "ChatRequest",
    "ChatResponse",
    "MoveGenerationProvider",
    "MoveSuggestion",
]
