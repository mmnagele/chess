"""Tests für :mod:`ai.provider`."""

from __future__ import annotations

from ai.provider import (
    ChatRequest,
    MoveGenerationRequest,
    MoveGenerationResponse,
    MoveSuggestion,
    ProviderConfig,
)
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
        history=("White: P e2 -> e4",),
        side_to_move="white",
        last_move="-",
        system_prompt="sys",
        user_prompt="usr",
    )
    assert request.fen == fen
    assert request.history == ("White: P e2 -> e4",)
    assert request.side_to_move == "white"


def test_basic_response_dataclasses() -> None:
    """Response-Helfer enthalten erwartete Felder."""

    response = MoveGenerationResponse(raw_text="MOVE: e2e4")
    chat = ChatRequest(system_prompt="s", user_prompt="u")
    suggestion = MoveSuggestion(
        start=(6, 4), end=(4, 4), move_text="e2e4", raw_response="MOVE: e2e4"
    )

    assert response.raw_text.startswith("MOVE:")
    assert chat.system_prompt == "s"
    assert suggestion.move_text == "e2e4"
