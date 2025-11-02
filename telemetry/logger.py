"""Einfache Telemetrieprotokollierung für UI- und Debug-Events."""

from __future__ import annotations

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
    timestamp: float = field(default_factory=lambda: time.time())
    duration_ms: float | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)


Sink = Callable[[TelemetryEvent], None]


class TelemetryLogger:
    """Sammelt Telemetrieereignisse und verteilt sie an optionale Senken."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []
        self._sinks: list[Sink] = []

    @property
    def events(self) -> list[TelemetryEvent]:
        """Gibt eine Liste der bisher aufgezeichneten Ereignisse zurück."""

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
        self._events.append(event)
        for sink in list(self._sinks):
            sink(event)
        return event

    def add_sink(self, sink: Sink) -> Callable[[], None]:
        """Registriert eine Senke und liefert einen Entferner zurück."""

        self._sinks.append(sink)

        def _remove() -> None:
            try:
                self._sinks.remove(sink)
            except ValueError:
                pass

        return _remove


_GLOBAL_LOGGER: TelemetryLogger | None = None


def get_telemetry_logger(*, reset: bool = False) -> TelemetryLogger:
    """Liefert einen wiederverwendbaren :class:`TelemetryLogger`."""

    global _GLOBAL_LOGGER
    if reset or _GLOBAL_LOGGER is None:
        _GLOBAL_LOGGER = TelemetryLogger()
    return _GLOBAL_LOGGER


__all__ = ["TelemetryEvent", "TelemetryLogger", "Sink", "get_telemetry_logger"]
