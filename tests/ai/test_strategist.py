"""Tests für :class:`ai.strategist.Strategist`."""

from __future__ import annotations

from collections import deque

import pytest

from ai.provider import MoveGenerationRequest
from ai.strategist import Strategist
from telemetry import TelemetryLogger


class SequenceProvider:
    """Einfacher Provider, der vorbereitete Antworten zurückliefert."""

    def __init__(self, responses) -> None:
        self.responses = deque(responses)

    def generate_move(self, request: MoveGenerationRequest):
        if not self.responses:
            raise RuntimeError("Keine weiteren Antworten vorbereitet.")
        return self.responses.popleft()


@pytest.fixture()
def strategist_factory(monkeypatch):
    """Hilfsfunktion zur Erzeugung konfigurierter Strategen."""

    def factory(responses, **kwargs):
        provider = SequenceProvider(responses)
        strategist = Strategist(provider, telemetry=TelemetryLogger(), **kwargs)
        monkeypatch.setattr(strategist, "_log", lambda *a, **k: None)
        monkeypatch.setattr(strategist, "_score_move", lambda game, move: 1.0)
        return strategist

    return factory


def test_choose_move_returns_first_valid(strategist_factory, move_request) -> None:
    """Der Stratege akzeptiert das erste legale Kandidatenpaar."""

    strategist = strategist_factory([((6, 4), (4, 4))])
    move = strategist.choose_move(move_request.game)
    assert move == ((6, 4), (4, 4))


def test_choose_move_retries_after_illegal_candidate(
    strategist_factory, move_request, monkeypatch
) -> None:
    """Ungültige Vorschläge werden verworfen und ein zweiter Versuch gestartet."""

    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    strategist = strategist_factory(["a1a1", ((6, 4), (4, 4))], max_retries=1)
    move = strategist.choose_move(move_request.game)
    assert move == ((6, 4), (4, 4))


def test_choose_move_raises_after_exhausted_retries(
    strategist_factory, move_request, monkeypatch
) -> None:
    """Sind alle Versuche ungültig, folgt eine RuntimeError-Ausnahme."""

    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    strategist = strategist_factory(["a1a1"], max_retries=0)
    with pytest.raises(RuntimeError):
        strategist.choose_move(move_request.game)
