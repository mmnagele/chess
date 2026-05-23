"""Einfache Telemetrieprotokollierung für UI- und Debug-Events."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TelemetryEvent:
    """Repräsentiert einen protokollierten Agenten- oder Systemschritt."""

    phase: str
    message: str
    status: str = "info"
    timestamp: float = field(default_factory=time.monotonic)
    duration_ms: float | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)


Sink = Callable[[TelemetryEvent], None]


class TelemetryLogger:
    """Sammelt Telemetrieereignisse und verteilt sie an optionale Senken."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[TelemetryEvent] = []
        self._sinks: list[Sink] = []

    @property
    def events(self) -> list[TelemetryEvent]:
        """Gibt eine Kopie der bisher aufgezeichneten Ereignisse zurück."""

        with self._lock:
            return list(self._events)

    def record(
        self,
        *,
        phase: str,
        message: str,
        status: str = "info",
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TelemetryEvent:
        """Speichert ein Ereignis und informiert registrierte Senken."""

        event = TelemetryEvent(
            phase=phase,
            message=message,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )
        with self._lock:
            self._events.append(event)
            sinks = list(self._sinks)

        for sink in sinks:
            try:
                sink(event)
            except Exception:
                pass  # A broken sink must never crash the caller.
        return event

    def add_sink(self, sink: Sink) -> Callable[[], None]:
        """Registriert eine Senke und liefert einen Entferner zurück."""

        with self._lock:
            self._sinks.append(sink)

        def _remove() -> None:
            with self._lock:
                try:
                    self._sinks.remove(sink)
                except ValueError:
                    pass

        return _remove


_GLOBAL_LOCK = threading.Lock()
_GLOBAL_LOGGER: TelemetryLogger | None = None


def get_telemetry_logger(*, reset: bool = False) -> TelemetryLogger:
    """Liefert einen wiederverwendbaren :class:`TelemetryLogger`."""

    global _GLOBAL_LOGGER
    with _GLOBAL_LOCK:
        if reset or _GLOBAL_LOGGER is None:
            _GLOBAL_LOGGER = TelemetryLogger()
        return _GLOBAL_LOGGER


__all__ = ["TelemetryEvent", "TelemetryLogger", "Sink", "get_telemetry_logger"]
