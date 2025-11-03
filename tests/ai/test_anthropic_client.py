"""Tests für :class:`ai.anthropic_client.AnthropicClient`."""

from __future__ import annotations

import pytest

from ai.anthropic_client import AnthropicClient
from ai.provider import MoveGenerationRequest, ProviderConfig
from config import AnthropicSettings
from engine import ChessGame
from engine.fen import export_fen


@pytest.fixture()
def single_move_request(chess_game: ChessGame) -> MoveGenerationRequest:
    """Erzeugt eine Anfrage mit genau einem legalen Zug."""

    legal_moves = ("e2e4",)
    return MoveGenerationRequest(
        game=chess_game,
        fen=export_fen(chess_game),
        legal_moves=legal_moves,
    )


def test_generate_move_returns_single_option(
    single_move_request: MoveGenerationRequest, anthropic_settings: AnthropicSettings
) -> None:
    """Mit nur einem Kandidaten muss der Zug unverändert zurückkommen."""

    client = AnthropicClient(
        settings=anthropic_settings,
        config=ProviderConfig(model="claude-test", temperature=0.0),
    )
    start, end = client.generate_move(single_move_request)
    assert (start, end) == ((6, 4), (4, 4))


def test_generate_move_requires_legal_moves(
    anthropic_settings: AnthropicSettings, chess_game: ChessGame
) -> None:
    """Ohne legale Züge wird eine verständliche Fehlermeldung geworfen."""

    request = MoveGenerationRequest(
        game=chess_game,
        fen=export_fen(chess_game),
        legal_moves=(),
    )
    client = AnthropicClient(settings=anthropic_settings)
    with pytest.raises(RuntimeError):
        client.generate_move(request)
