"""Tests for :class:`ai.anthropic_client.AnthropicClient`."""

from __future__ import annotations

from types import SimpleNamespace

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


class FakeMessages:
    def __init__(self, response) -> None:
        self._response = response

    def create(self, **kwargs):
        _ = kwargs
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeAnthropic:
    response = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.messages = FakeMessages(self.response)


def test_generate_move_reads_anthropic_text(
    move_request: MoveGenerationRequest,
    anthropic_settings: AnthropicSettings,
    monkeypatch,
) -> None:
    FakeAnthropic.response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="MOVE: e2e4")]
    )
    monkeypatch.setattr("ai.anthropic_client.Anthropic", FakeAnthropic)

    client = AnthropicClient(settings=anthropic_settings)
    result = client.generate_move(move_request)
    assert result.raw_text == "MOVE: e2e4"


def test_chat_reads_anthropic_text(anthropic_settings: AnthropicSettings, monkeypatch) -> None:
    FakeAnthropic.response = SimpleNamespace(content=[SimpleNamespace(type="text", text="Hi")])
    monkeypatch.setattr("ai.anthropic_client.Anthropic", FakeAnthropic)

    client = AnthropicClient(settings=anthropic_settings)
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hi"


def test_generate_move_raises_on_missing_content(
    move_request: MoveGenerationRequest,
    anthropic_settings: AnthropicSettings,
    monkeypatch,
) -> None:
    FakeAnthropic.response = SimpleNamespace(content=[])
    monkeypatch.setattr("ai.anthropic_client.Anthropic", FakeAnthropic)

    client = AnthropicClient(settings=anthropic_settings, retries=0)
    with pytest.raises(RuntimeError, match="Anthropic request failed"):
        client.generate_move(move_request)
