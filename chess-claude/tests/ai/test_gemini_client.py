"""Tests für :class:`ai.gemini_client.GeminiClient`."""

from __future__ import annotations

from unittest.mock import Mock

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


def test_generate_move_reads_gemini_text(
    move_request: MoveGenerationRequest,
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    client = GeminiClient(settings=gemini_settings)
    monkeypatch.setattr(
        client,
        "_post",
        Mock(return_value={"candidates": [{"content": {"parts": [{"text": "MOVE: e2e4"}]}}]}),
    )

    result = client.generate_move(move_request)
    assert result.raw_text == "MOVE: e2e4"


def test_chat_reads_gemini_text(gemini_settings: GeminiSettings, monkeypatch) -> None:
    client = GeminiClient(settings=gemini_settings)
    monkeypatch.setattr(
        client,
        "_post",
        Mock(return_value={"candidates": [{"content": {"parts": [{"text": "Hi"}]}}]}),
    )

    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hi"


def test_generate_move_raises_on_missing_candidates(
    move_request: MoveGenerationRequest,
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    client = GeminiClient(settings=gemini_settings)
    monkeypatch.setattr(client, "_post", Mock(return_value={"candidates": []}))
    with pytest.raises(RuntimeError, match="no candidates"):
        client.generate_move(move_request)


def test_extract_text_reports_prompt_block_reason(
    move_request: MoveGenerationRequest,
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    """Blocked prompts surface the blockReason in the error message."""
    client = GeminiClient(settings=gemini_settings)
    blocked_response = {"promptFeedback": {"blockReason": "SAFETY"}}
    monkeypatch.setattr(client, "_post", Mock(return_value=blocked_response))
    with pytest.raises(RuntimeError, match="blocked the prompt.*SAFETY"):
        client.generate_move(move_request)


def test_extract_text_reports_finish_reason_on_empty_content(
    move_request: MoveGenerationRequest,
    gemini_settings: GeminiSettings,
    monkeypatch,
) -> None:
    """Candidates with no text surface the finishReason."""
    client = GeminiClient(settings=gemini_settings)
    empty_candidate = {"candidates": [{"finishReason": "RECITATION"}]}
    monkeypatch.setattr(client, "_post", Mock(return_value=empty_candidate))
    with pytest.raises(RuntimeError, match="finishReason: RECITATION"):
        client.generate_move(move_request)
