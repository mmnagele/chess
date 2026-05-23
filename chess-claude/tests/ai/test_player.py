"""Tests für :class:`ai.player.AIPlayer`."""

from __future__ import annotations

import threading

import pytest

from ai.player import AIPlayer
from ai.provider import MoveSuggestion
from ai.strategist import Strategist


class ImmediateStrategist(Strategist):
    """Strategist-Attrappe, die sofort einen Zug liefert."""

    def __init__(self, suggestion: MoveSuggestion) -> None:
        super().__init__(provider=None)  # type: ignore[arg-type]
        self._suggestion = suggestion

    def choose_move(self, game, *, history=()):
        return self._suggestion


class BlockingStrategist(Strategist):
    """Strategist-Attrappe, die bis zur Freigabe blockiert."""

    def __init__(self, suggestion: MoveSuggestion) -> None:
        super().__init__(provider=None)  # type: ignore[arg-type]
        self._suggestion = suggestion
        self.started = threading.Event()
        self.release = threading.Event()

    def choose_move(self, game, *, history=()):
        self.started.set()
        self.release.wait(timeout=1.0)
        return self._suggestion


@pytest.fixture()
def sample_suggestion() -> MoveSuggestion:
    """Stellt einen deterministischen Zugvorschlag bereit."""

    return MoveSuggestion(
        start=(6, 4),
        end=(4, 4),
        move_text="e2e4",
        raw_response="MOVE: e2e4",
    )


def test_request_move_runs_in_background(chess_game, sample_suggestion: MoveSuggestion) -> None:
    """Der KI-Spieler führt den Callback nach Abschluss des Threads aus."""

    strategist = ImmediateStrategist(sample_suggestion)
    player = AIPlayer(strategist)
    completion = threading.Event()
    result: list[MoveSuggestion] = []

    player.request_move(
        chess_game,
        on_complete=lambda suggestion: (result.append(suggestion), completion.set()),
    )

    assert completion.wait(timeout=1.0)
    assert result[0].move_text == "e2e4"
    for _ in range(10):
        if not player.is_thinking():
            break
        threading.Event().wait(0.05)
    assert player.is_thinking() is False


def test_cancel_prevents_callback(chess_game, sample_suggestion: MoveSuggestion) -> None:
    """Ein Abbruch unterbindet den Erfolgs-Callback zuverlässig."""

    strategist = BlockingStrategist(sample_suggestion)
    player = AIPlayer(strategist)
    called = threading.Event()

    player.request_move(chess_game, on_complete=lambda _suggestion: called.set())
    assert strategist.started.wait(timeout=1.0)
    player.cancel()
    strategist.release.set()

    assert not called.wait(timeout=0.2)
    assert player.is_thinking() is False


def test_request_move_raises_when_busy(chess_game, sample_suggestion: MoveSuggestion) -> None:
    """Parallele Anfragen lösen eine :class:`RuntimeError` aus."""

    strategist = BlockingStrategist(sample_suggestion)
    player = AIPlayer(strategist)

    player.request_move(chess_game)
    assert strategist.started.wait(timeout=1.0)

    with pytest.raises(RuntimeError):
        player.request_move(chess_game)

    strategist.release.set()
