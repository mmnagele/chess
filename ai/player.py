"""Spielerimplementierungen für KI-basierte Züge."""

from __future__ import annotations

import copy
import threading
from typing import Callable, Sequence, Tuple

from engine.game import ChessGame, Position

from .strategist import Strategist

MoveCallback = Callable[[Tuple[Position, Position]], None]
ErrorCallback = Callable[[Exception], None]


class AIPlayer:
    """Steuert eine KI, die Züge im Hintergrund berechnet."""

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
        instructions: str | None = None,
        on_complete: MoveCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        """Startet die Berechnung eines KI-Zugs in einem Hintergrund-Thread."""

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("KI berechnet bereits einen Zug.")

            self._cancel_event = threading.Event()

            game_snapshot = copy.deepcopy(game)

            def _worker() -> None:
                try:
                    move = self._strategist.choose_move(
                        game_snapshot,
                        history=history,
                        instructions=instructions,
                    )
                except Exception as exc:  # pragma: no cover - Fehlerpfad
                    if not self._cancel_event.is_set() and on_error:
                        on_error(exc)
                    with self._lock:
                        self._thread = None
                    return

                if self._cancel_event.is_set():
                    with self._lock:
                        self._thread = None
                    return

                if on_complete:
                    on_complete(move)

                with self._lock:
                    self._thread = None

            thread = threading.Thread(target=_worker, name="AIPlayer", daemon=True)
            self._thread = thread
            thread.start()


__all__ = ["AIPlayer"]
