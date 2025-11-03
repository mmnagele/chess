"""Tests für :mod:`ai.commentator`."""

from __future__ import annotations

import json

import pytest

from ai.commentator import (
    Commentary,
    CommentaryContext,
    CommentaryPrompt,
    Commentator,
    LocalCommentaryProvider,
)
from engine import ChessGame
from telemetry import TelemetryLogger


class RecordingProvider(LocalCommentaryProvider):
    """Provider-Attrappe, die ein vorbereitetes Ergebnis liefert."""

    def __init__(self, response):
        super().__init__()
        self.response = response
        self.last_prompt: CommentaryPrompt | None = None

    def generate_commentary(self, prompt: CommentaryPrompt):  # type: ignore[override]
        self.last_prompt = prompt
        return self.response


def test_commentary_prompt_to_dict(simple_history) -> None:
    """Kontext und Schema werden vollständig serialisiert."""

    context = CommentaryContext(fen="fen-string", history=tuple(simple_history))
    prompt = CommentaryPrompt(
        system_message="system",
        user_message="user",
        response_schema={"type": "object"},
        context=context,
    )
    payload = prompt.to_dict()
    assert payload["context"]["fen"] == "fen-string"
    assert payload["context"]["history"] == list(simple_history)
    assert payload["schema"]["type"] == "object"


def test_commentary_as_dict_roundtrip() -> None:
    """Die Normalisierung in ein Wörterbuch ist verlustfrei."""

    commentary = Commentary(
        variant_hint="Kritischer Zug",
        eval_trend="Ausgeglichen",
        key_ideas=("Linie öffnen",),
        blunders_last_moves=("falscher Springerzug",),
    )
    data = commentary.as_dict()
    assert data["variant_hint"] == "Kritischer Zug"
    assert data["key_ideas"] == ["Linie öffnen"]


def test_local_provider_generates_basic_commentary(simple_history) -> None:
    """Der Fallback-Provider produziert sinnvolle Strings."""

    game = ChessGame()
    context = CommentaryContext(
        fen="dummy-fen",
        history=tuple(simple_history),
        evaluation={"material": 1},
    )
    prompt = CommentaryPrompt(
        system_message="system",
        user_message="user",
        response_schema={},
        context=context,
    )
    provider = LocalCommentaryProvider()
    result = provider.generate_commentary(prompt)
    assert "variant_hint" in result
    assert isinstance(result["key_ideas"], list)


def test_commentator_builds_prompt_with_history(simple_history) -> None:
    """Der Prompt enthält FEN, Verlauf und Bewertungshinweise."""

    game = ChessGame()
    commentator = Commentator(telemetry=TelemetryLogger())
    prompt = commentator.build_prompt(game, history=simple_history, evaluation={"material": 0})
    assert "FEN:" in prompt.user_message
    assert "Letzte Züge" in prompt.user_message
    assert prompt.response_schema["type"] == "object"


def test_commentator_provides_normalised_output(simple_history) -> None:
    """Ein gültiger Provider-Output wird zu :class:`Commentary` normalisiert."""

    response = {
        "variant_hint": "Sf3",
        "eval_trend": "Ausgeglichen",
        "key_ideas": ["Zentrum kontrollieren"],
        "blunders_last_moves": [],
    }
    provider = RecordingProvider(response)
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())
    game = ChessGame()
    commentary = commentator.provide_commentary(game, history=simple_history)
    assert commentary.key_ideas == ("Zentrum kontrollieren",)
    assert provider.last_prompt is not None


def test_commentator_rejects_invalid_response(simple_history) -> None:
    """Ungültige Datentypen führen zu einer klaren Ausnahme."""

    provider = RecordingProvider({"key_ideas": 42})
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())
    game = ChessGame()
    with pytest.raises(ValueError):
        commentator.provide_commentary(game, history=simple_history)


def test_commentator_render_formats_output() -> None:
    """Die gerenderte Darstellung ist mehrzeilig und menschenlesbar."""

    commentator = Commentator(telemetry=TelemetryLogger())
    commentary = Commentary(
        variant_hint="Sf3",
        eval_trend="Weiss steht gut",
        key_ideas=("Zentrum kontrollieren",),
        blunders_last_moves=("Läufer eingestellt",),
    )
    rendered = commentator.render(commentary)
    assert "Letzter Impuls" in rendered
    assert "Fehler zuletzt" in rendered
