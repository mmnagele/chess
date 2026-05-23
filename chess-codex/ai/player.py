"""Spielerimplementierungen für KI-basierte Zugvorschläge."""

from __future__ import annotations

import copy
import threading
from typing import Callable, Sequence

from engine.game import ChessGame

from .provider import MoveSuggestion
from .strategist import Strategist

MoveCallback = Callable[[MoveSuggestion], None]
ErrorCallback = Callable[[Exception], None]


class AIPlayer:
    """Steuert eine KI, die Zugvorschläge im Hintergrund berechnet."""

    def __init__(self, strategist: Strategist) -> None:
        self._strategist = strategist
        self._thread: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._lock = threading.Lock()

    def is_thinking(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def cancel(self) -> None:
        """Bricht eine laufende Berechnung ab."""

        with self._lock:
            self._cancel_event.set()

    def request_move(
        self,
        game: ChessGame,
        *,
        history: Sequence[str] = (),
        on_complete: MoveCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        """Startet die Berechnung eines KI-Zugvorschlags in einem Hintergrund-Thread."""

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("KI berechnet bereits einen Zug.")

            cancel = threading.Event()
            self._cancel_event = cancel

            game_snapshot = copy.deepcopy(game)

            def _worker() -> None:
                try:
                    suggestion = self._strategist.choose_move(
                        game_snapshot,
                        history=history,
                    )
                except Exception as exc:
                    with self._lock:
                        self._thread = None
                    if not cancel.is_set() and on_error:
                        on_error(exc)
                    return

                with self._lock:
                    self._thread = None

                if cancel.is_set():
                    return

                if on_complete:
                    on_complete(suggestion)

            thread = threading.Thread(target=_worker, name="AIPlayer", daemon=True)
            self._thread = thread
            thread.start()


__all__ = ["AIPlayer"]
