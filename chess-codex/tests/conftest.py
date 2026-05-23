"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Sequence

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from PySide6.QtWidgets import QApplication

from ai.provider import MoveGenerationRequest
from config import AnthropicSettings, GeminiSettings, OpenAISettings
from engine import ChessGame
from engine.fen import export_fen, square_to_notation


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Provide a singleton QApplication for all Qt tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def chess_game() -> ChessGame:
    """Return a fresh chess game instance."""

    return ChessGame()


def collect_legal_moves(game: ChessGame) -> tuple[str, ...]:
    """Collect all legal moves in coordinate notation."""

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
    """Prepare a move generation request for the initial position."""

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
    return AnthropicSettings(api_key="test-key")


@pytest.fixture()
def gemini_settings() -> GeminiSettings:
    return GeminiSettings(api_key="test-key")


@pytest.fixture()
def openai_settings() -> OpenAISettings:
    return OpenAISettings(api_key="test-key")


@pytest.fixture()
def legal_move_notation(chess_game: ChessGame) -> Sequence[str]:
    return collect_legal_moves(chess_game)


@pytest.fixture()
def simple_history() -> Iterable[str]:
    return ("White: P e2 -> e4", "Black: P e7 -> e5")
