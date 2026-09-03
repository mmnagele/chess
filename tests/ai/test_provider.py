"""Tests für :mod:`ai.provider`."""

from __future__ import annotations

from ai.provider import MoveGenerationRequest, ProviderConfig
from engine import ChessGame
from engine.fen import export_fen


def test_provider_config_defaults() -> None:
    """Die Standardwerte entsprechen den dokumentierten Vorgaben."""

    config = ProviderConfig(model="test")
    assert config.temperature == 0.2
    assert config.max_output_tokens == 1024
    assert config.timeout == 30.0


def test_move_generation_request_holds_context(chess_game: ChessGame) -> None:
    """Die Anfrage speichert Engine-Referenz und Metadaten."""

    fen = export_fen(chess_game)
    request = MoveGenerationRequest(
        game=chess_game,
        fen=fen,
        legal_moves=("e2e4",),
        history=("Weiss: B e2 → e4",),
        instructions="Bevorzuge Zentrum",
    )
    assert request.fen == fen
    assert request.history == ("Weiss: B e2 → e4",)
