"""Tests für :class:`ai.openai_client.OpenAIClient`."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from ai.openai_client import OpenAIClient
from config import OpenAISettings


def test_generate_move_parses_json_response(
    move_request, openai_settings: OpenAISettings, monkeypatch
) -> None:
    """Der Client extrahiert gültige Koordinaten aus einer JSON-Antwort."""

    client = OpenAIClient(settings=openai_settings)
    response = {
        "output": [
            {
                "content": [
                    {
                        "text": json.dumps({"move": "e2e4"}),
                    }
                ]
            }
        ]
    }
    mocked_post = Mock(return_value=response)
    monkeypatch.setattr(client, "_post", mocked_post)

    start, end = client.generate_move(move_request)

    assert (start, end) == ((6, 4), (4, 4))
    mocked_post.assert_called_once()


def test_generate_move_raises_on_unreadable_payload(
    move_request, openai_settings: OpenAISettings, monkeypatch
) -> None:
    """Ein fehlendes Ergebnis führt zu einer klaren Ausnahme."""

    client = OpenAIClient(settings=openai_settings)
    monkeypatch.setattr(client, "_post", Mock(return_value={}))

    with pytest.raises(RuntimeError):
        client.generate_move(move_request)
