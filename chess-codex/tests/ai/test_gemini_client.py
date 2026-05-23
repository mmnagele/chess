"""Tests for :class:`ai.gemini_client.GeminiClient`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.gemini_client import GeminiClient
from ai.provider import ChatRequest, MoveGenerationRequest
from config import GeminiSettings
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


class FakeModels:
    def __init__(self, response) -> None:
        self._response = response

    def generate_content(self, **kwargs):
        _ = kwargs
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeGenAIClient:
    response = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.models = FakeModels(self.response)


class FakeGenAI:
    Client = FakeGenAIClient


def test_generate_move_reads_gemini_text(
    move_request: MoveGenerationRequest,
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    FakeGenAIClient.response = SimpleNamespace(text="MOVE: e2e4")
    monkeypatch.setattr("ai.gemini_client.genai", FakeGenAI)

    client = GeminiClient(settings=gemini_settings)
    result = client.generate_move(move_request)
    assert result.raw_text == "MOVE: e2e4"


def test_chat_reads_gemini_text(gemini_settings: GeminiSettings, monkeypatch) -> None:
    FakeGenAIClient.response = SimpleNamespace(text="Hi")
    monkeypatch.setattr("ai.gemini_client.genai", FakeGenAI)

    client = GeminiClient(settings=gemini_settings)
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hi"


def test_generate_move_raises_on_missing_candidates(
    move_request: MoveGenerationRequest,
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    FakeGenAIClient.response = SimpleNamespace(text="", candidates=[])
    monkeypatch.setattr("ai.gemini_client.genai", FakeGenAI)

    client = GeminiClient(settings=gemini_settings, retries=0)
    with pytest.raises(RuntimeError, match="Gemini request failed"):
        client.generate_move(move_request)


def test_transport_error_uses_rest_fallback(
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    class ConnectError(Exception):
        pass

    class DummyHTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> bool:
            return False

        def read(self) -> bytes:
            return (
                b'{"candidates":[{"content":{"parts":[{"text":"Hi from REST fallback"}]}}]}'
            )

    FakeGenAIClient.response = ConnectError("Network is unreachable")
    monkeypatch.setattr("ai.gemini_client.genai", FakeGenAI)
    monkeypatch.setattr(
        "ai.gemini_client.urllib_request.urlopen",
        lambda _request, timeout: DummyHTTPResponse(),
    )

    client = GeminiClient(settings=gemini_settings, retries=0)
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hi from REST fallback"
