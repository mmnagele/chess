"""Tests für :class:`ai.strategist.Strategist`."""

from __future__ import annotations

from collections import deque

import pytest

from ai.provider import MoveGenerationResponse, MoveSuggestion, ProviderConfig
from ai.strategist import Strategist
from telemetry import TelemetryLogger


class SequenceProvider:
    """Einfacher Provider, der vorbereitete Antworten zurückliefert."""

    def __init__(self, responses) -> None:
        self.responses = deque(responses)
        self.requests = []

    def generate_move(self, request):
        self.requests.append(request)
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
        return strategist, provider

    return factory


def test_choose_move_returns_first_valid(strategist_factory, move_request) -> None:
    """Der Stratege akzeptiert die erste legale MOVE-Antwort."""

    strategist, _provider = strategist_factory(["MOVE: e2e4"])
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
    strategist, _provider = strategist_factory(["MOVE: a1a1", "MOVE: e2e4"], max_retries=1)
    suggestion = strategist.choose_move(move_request.game)
    assert suggestion.move_text == "e2e4"


def test_choose_move_raises_after_exhausted_retries(
    strategist_factory, move_request, monkeypatch
) -> None:
    """Sind alle Versuche ungültig, folgt eine RuntimeError-Ausnahme."""

    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    strategist, _provider = strategist_factory(["MOVE: a1a1"], max_retries=0)
    with pytest.raises(RuntimeError):
        strategist.choose_move(move_request.game)


def test_retry_prompt_includes_move_history(strategist_factory, move_request, monkeypatch) -> None:
    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    strategist, provider = strategist_factory(["MOVE: a1a1", "MOVE: e2e4"], max_retries=1)
    history = ("White: P e2 -> e4", "Black: P e7 -> e5")
    strategist.choose_move(move_request.game, history=history)

    assert len(provider.requests) == 2
    retry_prompt = provider.requests[1].user_prompt
    assert "Recent move history" in retry_prompt
    assert "White: P e2 -> e4" in retry_prompt
    assert "Last move" in retry_prompt


def test_choose_move_respects_total_timeout(strategist_factory, move_request, monkeypatch) -> None:
    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    clock = {"value": 0.0}

    def _fake_monotonic() -> float:
        clock["value"] += 0.1
        return clock["value"]

    monkeypatch.setattr("ai.strategist.time.monotonic", _fake_monotonic)

    strategist, _provider = strategist_factory(
        ["MOVE: a1a1", "MOVE: a1a1", "MOVE: a1a1"],
        max_retries=5,
        total_timeout_seconds=0.35,
    )

    with pytest.raises(RuntimeError, match="timed out"):
        strategist.choose_move(move_request.game)


def test_strategist_temporarily_clamps_provider_timeout(monkeypatch, move_request) -> None:
    monkeypatch.setattr("ai.strategist.time.sleep", lambda _seconds: None)
    clock = {"value": 0.0}

    def _fake_monotonic() -> float:
        clock["value"] += 0.1
        return clock["value"]

    monkeypatch.setattr("ai.strategist.time.monotonic", _fake_monotonic)

    class TimeoutAwareProvider:
        def __init__(self) -> None:
            self.config = ProviderConfig(model="dummy", timeout=30.0)
            self.seen_timeouts: list[float] = []

        def generate_move(self, request):
            _ = request
            self.seen_timeouts.append(self.config.timeout)
            return MoveGenerationResponse(raw_text="MOVE: a1a1")

        def chat(self, request):
            raise NotImplementedError

    provider = TimeoutAwareProvider()
    strategist = Strategist(
        provider,
        telemetry=TelemetryLogger(),
        max_retries=2,
        total_timeout_seconds=0.35,
    )
    monkeypatch.setattr(strategist, "_log", lambda *a, **k: None)

    with pytest.raises(RuntimeError):
        strategist.choose_move(move_request.game)

    assert provider.seen_timeouts
    assert provider.seen_timeouts[0] < 30.0
    assert provider.config.timeout == 30.0
