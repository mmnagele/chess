"""Tests für :class:`ai.gemini_client.GeminiClient`."""

from __future__ import annotations

import pytest

from ai.gemini_client import GeminiClient
from ai.provider import MoveGenerationRequest, ProviderConfig
from config import GeminiSettings
from engine import ChessGame
from engine.fen import export_fen


@pytest.fixture()
def capture_request(chess_game: ChessGame) -> MoveGenerationRequest:
    """Baut eine Stellung, in der ein einfacher Schlagzug attraktiv ist."""

    # Stelle sicher, dass Weiss eine Figur schlagen kann.
    game = chess_game
    game.apply_move((6, 4), (4, 4))  # e2e4
    game.apply_move((1, 3), (3, 3))  # d7d5
    legal_moves = ("e4d5", "g2g3")
    return MoveGenerationRequest(
        game=game,
        fen=export_fen(game),
        legal_moves=legal_moves,
        history=("Weiss: B e2 → e4", "Schwarz: B d7 → d5"),
    )


def test_generate_move_prefers_capture(
    capture_request: MoveGenerationRequest, gemini_settings: GeminiSettings
) -> None:
    """Der heuristische Client wählt bevorzugt den Schlagzug aus."""

    client = GeminiClient(
        settings=gemini_settings,
        config=ProviderConfig(model="gemini-test", temperature=0.0),
    )
    start, end = client.generate_move(capture_request)
    assert (start, end) == ((4, 4), (3, 3))


def test_generate_move_rejects_missing_moves(
    chess_game: ChessGame, gemini_settings: GeminiSettings
) -> None:
    """Ohne Kandidaten muss eine verständliche Ausnahme entstehen."""

    request = MoveGenerationRequest(
        game=chess_game,
        fen=export_fen(chess_game),
        legal_moves=(),
    )
    client = GeminiClient(settings=gemini_settings)
    with pytest.raises(RuntimeError):
        client.generate_move(request)
