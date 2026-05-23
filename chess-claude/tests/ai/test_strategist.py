"""Tests für :class:`ai.strategist.Strategist`."""

from __future__ import annotations

from collections import deque

import pytest

from ai.provider import MoveGenerationResponse, MoveSuggestion
from ai.strategist import Strategist
from telemetry import TelemetryLogger


class SequenceProvider:
    """Einfacher Provider, der vorbereitete Antworten zurückliefert."""

    def __init__(self, responses) -> None:
        self.responses = deque(responses)

    def generate_move(self, request):
        if not self.responses:
            raise RuntimeError("Keine weiteren Antworten vorbereitet.")
        return MoveGenerationResponse(raw_text=self.responses.popleft())

    def chat(self, request):
        raise NotImplementedError


@pytest.fixture()
def strategist_factory(monkeypatch):
    """Hilfsfunktion zur Erzeugung konfigurierter Strategen."""

    def factory(responses, **kwargs):
        provider = SequenceProvider(responses)
        strategist = Strategist(provider, telemetry=TelemetryLogger(), **kwargs)
        monkeypatch.setattr(strategist, "_log", lambda *a, **k: None)
        return strategist

    return factory


def test_choose_move_returns_first_valid(strategist_factory, move_request) -> None:
    """Der Stratege akzeptiert die erste legale MOVE-Antwort."""

    strategist = strategist_factory(["MOVE: e2e4"])
    suggestion = strategist.choose_move(move_request.game)
    assert isinstance(suggestion, MoveSuggestion)
    assert suggestion.move_text == "e2e4"
    assert suggestion.start == (6, 4)
    assert suggestion.end == (4, 4)


def test_choose_move_retries_after_illegal_candidate(
    strategist_factory, move_request, monkeypatch
) -> None:
    """Ungültige Vorschläge werden verworfen und erneut angefragt."""

    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    strategist = strategist_factory(["MOVE: a1a1", "MOVE: e2e4"], max_retries=1)
    suggestion = strategist.choose_move(move_request.game)
    assert suggestion.move_text == "e2e4"


def test_choose_move_raises_after_exhausted_retries(
    strategist_factory, move_request, monkeypatch
) -> None:
    """Sind alle Versuche ungültig, folgt eine RuntimeError-Ausnahme."""

    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    strategist = strategist_factory(["MOVE: a1a1"], max_retries=0)
    with pytest.raises(RuntimeError):
        strategist.choose_move(move_request.game)
