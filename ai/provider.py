"""Schnittstellen und Grundkonfiguration für KI-Zuganbieter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from engine.game import ChessGame, Position


@dataclass
class ProviderConfig:
    """Konfigurationsparameter für einen LLM-Zuganbieter."""

    model: str
    temperature: float = 0.2
    max_output_tokens: int = 1024
    timeout: float = 30.0
    top_p: float = 1.0


@dataclass
class MoveGenerationRequest:
    """Kontextinformationen für eine Zuganfrage an ein LLM."""

    game: ChessGame
    fen: str
    legal_moves: Sequence[str]
    history: Sequence[str] = ()
    instructions: str | None = None


class MoveGenerationProvider(Protocol):
    """Protokoll für KI-Anbieter, die Schachzüge generieren."""

    config: ProviderConfig

    def generate_move(self, request: MoveGenerationRequest) -> tuple[Position, Position]:
        """Erzeugt einen legalen Zug.

        Implementierende Klassen müssen sicherstellen, dass der zurückgegebene
        Zug gegen den `ChessGame`-Status validiert wurde und somit legal ist.
        """

