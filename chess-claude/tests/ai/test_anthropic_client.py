"""Tests für :class:`ai.anthropic_client.AnthropicClient`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ai.anthropic_client import AnthropicClient
from ai.provider import ChatRequest, MoveGenerationRequest
from config import AnthropicSettings
from engine import ChessGame
from engine.fen import export_fen


@pytest.fixture()
def move_request(chess_game: ChessGame) -> MoveGenerationRequest:
    return MoveGenerationRequest(
        game=chess_game,
        fen=export_fen(chess_game),
        legal_moves=("e2e4",),
        system_prompt="sys",
        user_prompt="usr",
    )


def test_generate_move_reads_anthropic_text(
    move_request: MoveGenerationRequest,
    anthropic_settings: AnthropicSettings,
    monkeypatch,
) -> None:
    client = AnthropicClient(settings=anthropic_settings)
    monkeypatch.setattr(
        client,
        "_post",
        Mock(return_value={"content": [{"type": "text", "text": "MOVE: e2e4"}]}),
    )

    result = client.generate_move(move_request)
    assert result.raw_text == "MOVE: e2e4"


def test_chat_reads_anthropic_text(anthropic_settings: AnthropicSettings, monkeypatch) -> None:
    client = AnthropicClient(settings=anthropic_settings)
    monkeypatch.setattr(
        client,
        "_post",
        Mock(return_value={"content": [{"type": "text", "text": "Hi"}]}),
    )

    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hi"


def test_generate_move_raises_on_missing_content(
    move_request: MoveGenerationRequest,
    anthropic_settings: AnthropicSettings,
    monkeypatch,
) -> None:
    client = AnthropicClient(settings=anthropic_settings)
    monkeypatch.setattr(client, "_post", Mock(return_value={"content": []}))
    with pytest.raises(RuntimeError):
        client.generate_move(move_request)
