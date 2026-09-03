"""Tests für :class:`ai.player.AIPlayer`."""

from __future__ import annotations

import threading
from typing import Sequence

import pytest

from ai.player import AIPlayer
from ai.strategist import Strategist


class ImmediateStrategist(Strategist):
    """Strategist-Attrappe, die sofort einen Zug liefert."""

    def __init__(self, move: tuple[tuple[int, int], tuple[int, int]]) -> None:
        super().__init__(provider=None)  # type: ignore[arg-type]
        self._move = move

    def choose_move(self, game, *, history: Sequence[str] = (), instructions: str | None = None):
        return self._move


class BlockingStrategist(Strategist):
    """Strategist-Attrappe, die bis zur Freigabe blockiert."""

    def __init__(self, move: tuple[tuple[int, int], tuple[int, int]]) -> None:
        super().__init__(provider=None)  # type: ignore[arg-type]
        self._move = move
        self.started = threading.Event()
        self.release = threading.Event()

    def choose_move(self, game, *, history: Sequence[str] = (), instructions: str | None = None):
        self.started.set()
        self.release.wait(timeout=1.0)
        return self._move


@pytest.fixture()
def sample_move() -> tuple[tuple[int, int], tuple[int, int]]:
    """Stellt ein deterministisches Zugpaar bereit."""

    return ((6, 4), (4, 4))


def test_request_move_runs_in_background(chess_game, sample_move) -> None:
    """Der KI-Spieler führt den Callback nach Abschluss des Threads aus."""

    strategist = ImmediateStrategist(sample_move)
    player = AIPlayer(strategist)
    completion = threading.Event()
    result: list[tuple[tuple[int, int], tuple[int, int]]] = []

    player.request_move(
        chess_game,
        on_complete=lambda move: (result.append(move), completion.set()),
    )

    assert completion.wait(timeout=1.0)
    assert result == [sample_move]
    for _ in range(10):
        if not player.is_thinking():
            break
        threading.Event().wait(0.05)
    assert player.is_thinking() is False


def test_cancel_prevents_callback(chess_game, sample_move) -> None:
    """Ein Abbruch unterbindet den Erfolgs-Callback zuverlässig."""

    strategist = BlockingStrategist(sample_move)
    player = AIPlayer(strategist)
    called = threading.Event()

    player.request_move(chess_game, on_complete=lambda _move: called.set())
    assert strategist.started.wait(timeout=1.0)
    player.cancel()
    strategist.release.set()

    assert not called.wait(timeout=0.2)
    assert player.is_thinking() is False


def test_request_move_raises_when_busy(chess_game, sample_move) -> None:
    """Parallele Anfragen lösen eine :class:`RuntimeError` aus."""

    strategist = BlockingStrategist(sample_move)
    player = AIPlayer(strategist)

    player.request_move(chess_game)
    assert strategist.started.wait(timeout=1.0)

    with pytest.raises(RuntimeError):
        player.request_move(chess_game)

    strategist.release.set()
