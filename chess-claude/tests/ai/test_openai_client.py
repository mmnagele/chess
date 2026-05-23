"""Tests für :class:`ai.openai_client.OpenAIClient`."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ai.openai_client import OpenAIClient
from ai.provider import ChatRequest
from config import OpenAISettings


def test_generate_move_reads_text_from_response(
    move_request, openai_settings: OpenAISettings, monkeypatch
) -> None:
    """Der Client extrahiert Text aus Responses-Output."""

    client = OpenAIClient(settings=openai_settings)
    response = {
        "output": [
            {
                "content": [
                    {
                        "text": "MOVE: e2e4",
                    }
                ]
            }
        ]
    }
    mocked_post = Mock(return_value=response)
    monkeypatch.setattr(client, "_post", mocked_post)

    result = client.generate_move(move_request)

    assert result.raw_text == "MOVE: e2e4"
    mocked_post.assert_called_once()


def test_chat_reads_text_from_response(openai_settings: OpenAISettings, monkeypatch) -> None:
    """Chat nutzt den gleichen Extraktionspfad."""

    client = OpenAIClient(settings=openai_settings)
    monkeypatch.setattr(
        client,
        "_post",
        Mock(return_value={"output": [{"content": [{"text": "Hello"}]}]}),
    )

    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hello"


def test_generate_move_raises_on_unreadable_payload(
    move_request, openai_settings: OpenAISettings, monkeypatch
) -> None:
    """Ein fehlendes Ergebnis führt zu einer klaren Ausnahme."""

    client = OpenAIClient(settings=openai_settings)
    monkeypatch.setattr(client, "_post", Mock(return_value={}))

    with pytest.raises(RuntimeError):
        client.generate_move(move_request)


def test_build_payload_uses_input_text_for_all_inputs(openai_settings: OpenAISettings) -> None:
    """Responses payload must use ``input_text`` for all input message contents."""

    client = OpenAIClient(settings=openai_settings)
    payload = client._build_payload("sys", "usr")

    assert payload["input"][0]["content"][0]["type"] == "input_text"
    assert payload["input"][1]["content"][0]["type"] == "input_text"


def test_chat_retries_without_temperature_for_strict_models(
    openai_settings: OpenAISettings, monkeypatch
) -> None:
    """If model rejects ``temperature``, client retries once without it."""

    client = OpenAIClient(settings=openai_settings)
    calls: list[dict] = []

    def _fake_post(_path: str, payload: dict):
        calls.append(payload)
        if len(calls) == 1:
            raise RuntimeError(
                "OpenAI request failed: HTTP 400: " "Unsupported parameter: 'temperature'"
            )
        return {"output": [{"content": [{"text": "ok"}]}]}

    monkeypatch.setattr(client, "_post", _fake_post)
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))

    assert result.raw_text == "ok"
    assert len(calls) == 2
    assert "temperature" in calls[0]
    assert "temperature" not in calls[1]


def test_chat_retries_without_max_output_tokens_for_strict_models(
    openai_settings: OpenAISettings, monkeypatch
) -> None:
    """If model rejects ``max_tokens``/``max_output_tokens``, client retries without it."""

    client = OpenAIClient(settings=openai_settings)
    calls: list[dict] = []

    def _fake_post(_path: str, payload: dict):
        calls.append(payload)
        if len(calls) == 1:
            raise RuntimeError(
                "OpenAI request failed: HTTP 400: Unsupported parameter: 'max_tokens' "
                "is not supported with this model."
            )
        return {"output": [{"content": [{"text": "ok"}]}]}

    monkeypatch.setattr(client, "_post", _fake_post)
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))

    assert result.raw_text == "ok"
    assert len(calls) == 2
    assert "max_output_tokens" in calls[0]
    assert "max_output_tokens" not in calls[1]


def test_fallback_does_not_retry_for_unrelated_errors(
    openai_settings: OpenAISettings, monkeypatch
) -> None:
    """Non-parameter errors must not trigger the fallback retry."""

    client = OpenAIClient(settings=openai_settings)

    def _fake_post(_path: str, _payload: dict):
        raise RuntimeError("OpenAI request failed: HTTP 401: invalid api key")

    monkeypatch.setattr(client, "_post", _fake_post)

    with pytest.raises(RuntimeError, match="invalid api key"):
        client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
