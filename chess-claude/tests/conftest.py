"""Gemeinsame Pytest-Fixtures und Hilfsfunktionen für die Test-Suite."""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from ai.provider import MoveGenerationRequest  # noqa: E402
from config import AnthropicSettings, GeminiSettings, OpenAISettings  # noqa: E402
from engine import ChessGame  # noqa: E402
from engine.fen import export_fen, square_to_notation  # noqa: E402


@pytest.fixture()
def chess_game() -> ChessGame:
    """Gibt eine frische :class:`~engine.game.ChessGame`-Instanz zurück."""

    return ChessGame()


def collect_legal_moves(game: ChessGame) -> tuple[str, ...]:
    """Erzeugt eine sortierte Liste aller legalen Züge im Koordinatenformat."""

    legal_moves: list[str] = []
    for (row, col), piece in game.board.items():
        if not piece or piece[0] != game.current_player:
            continue
        start_notation = square_to_notation((row, col))
        for target in game.get_valid_moves(row, col):
            legal_moves.append(f"{start_notation}{square_to_notation(target)}")
    return tuple(sorted(legal_moves))


@pytest.fixture()
def move_request(chess_game: ChessGame) -> MoveGenerationRequest:
    """Bereitet eine :class:`MoveGenerationRequest` für die Anfangsstellung vor."""

    legal_moves = collect_legal_moves(chess_game)
    return MoveGenerationRequest(
        game=chess_game,
        fen=export_fen(chess_game),
        legal_moves=legal_moves,
        history=(),
        side_to_move="white",
        last_move="-",
        system_prompt="sys",
        user_prompt="usr",
    )


@pytest.fixture()
def anthropic_settings() -> AnthropicSettings:
    """Stellt Dummy-Einstellungen für Anthropic bereit."""

    return AnthropicSettings(api_key="test-key")


@pytest.fixture()
def gemini_settings() -> GeminiSettings:
    """Stellt Dummy-Einstellungen für Gemini bereit."""

    return GeminiSettings(api_key="test-key")


@pytest.fixture()
def openai_settings() -> OpenAISettings:
    """Stellt Dummy-Einstellungen für OpenAI bereit."""

    return OpenAISettings(api_key="test-key")


@pytest.fixture()
def legal_move_notation(chess_game: ChessGame) -> Sequence[str]:
    """Gibt eine Liste legaler Ausgangszüge für Weiss zurück."""

    return collect_legal_moves(chess_game)


@pytest.fixture()
def simple_history() -> Iterable[str]:
    """Stellt einen kurzen Zugverlauf für Kommentartests bereit."""

    return ("White: P e2 -> e4", "Black: P e7 -> e5")
