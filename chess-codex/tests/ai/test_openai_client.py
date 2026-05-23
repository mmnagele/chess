"""Tests for :class:`ai.openai_client.OpenAIClient`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai.openai_client import OpenAIClient
from ai.provider import ChatRequest
from config import OpenAISettings


class FakeCompletions:
    def __init__(self, response) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if callable(self._response):
            return self._response(**kwargs)
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


class FakeOpenAI:
    response = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.completions = FakeCompletions(type(self).response)
        self.chat = SimpleNamespace(completions=self.completions)
        self.timeout = None

    def with_options(self, *, timeout):
        self.timeout = timeout
        return self


def test_generate_move_reads_text_from_response(
    move_request, openai_settings: OpenAISettings, monkeypatch
) -> None:
    FakeOpenAI.response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="MOVE: e2e4"))]
    )
    monkeypatch.setattr("ai.openai_client.OpenAI", FakeOpenAI)

    client = OpenAIClient(settings=openai_settings)
    result = client.generate_move(move_request)

    assert result.raw_text == "MOVE: e2e4"
    assert client._client.timeout == client.config.timeout  # pylint: disable=protected-access


def test_chat_reads_text_from_response(openai_settings: OpenAISettings, monkeypatch) -> None:
    FakeOpenAI.response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Hello"))]
    )
    monkeypatch.setattr("ai.openai_client.OpenAI", FakeOpenAI)

    client = OpenAIClient(settings=openai_settings)
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hello"


def test_generate_move_raises_on_unreadable_payload(
    move_request, openai_settings: OpenAISettings, monkeypatch
) -> None:
    FakeOpenAI.response = SimpleNamespace(choices=[])
    monkeypatch.setattr("ai.openai_client.OpenAI", FakeOpenAI)

    client = OpenAIClient(settings=openai_settings, retries=0)
    with pytest.raises(RuntimeError, match="OpenAI request failed"):
        client.generate_move(move_request)


def test_gpt5_uses_max_completion_tokens_without_temperature(
    openai_settings: OpenAISettings,
    monkeypatch,
) -> None:
    def _response(**kwargs):
        assert "max_completion_tokens" in kwargs
        assert "max_tokens" not in kwargs
        assert "temperature" not in kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hello from gpt-5"))]
        )

    FakeOpenAI.response = _response
    monkeypatch.setattr("ai.openai_client.OpenAI", FakeOpenAI)

    from ai.provider import ProviderConfig

    client = OpenAIClient(
        settings=openai_settings,
        config=ProviderConfig(model="gpt-5", temperature=0.2, max_output_tokens=64),
    )
    result = client.chat(ChatRequest(system_prompt="s", user_prompt="u"))
    assert result.raw_text == "Hello from gpt-5"
