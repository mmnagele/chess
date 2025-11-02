"""Einfache Telemetrieprotokollierung für UI- und Debug-Events."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, MutableMapping, Optional


@dataclass(slots=True)
class TelemetryEvent:
    """Repräsentiert einen protokollierten Agenten- oder Systemschritt."""

    phase: str
    message: str
    status: str = "info"
    timestamp: float = field(default_factory=lambda: time.time())
    duration_ms: Optional[float] = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)


Sink = Callable[[TelemetryEvent], None]


class TelemetryLogger:
    """Sammelt Telemetrieereignisse und verteilt sie an optionale Senken."""

    def __init__(self) -> None:
        self._events: List[TelemetryEvent] = []
        self._sinks: List[Sink] = []

    @property
    def events(self) -> List[TelemetryEvent]:
        """Gibt eine Liste der bisher aufgezeichneten Ereignisse zurück."""

        return list(self._events)

    def record(
        self,
        *,
        phase: str,
        message: str,
        status: str = "info",
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
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


__all__ = ["TelemetryEvent", "TelemetryLogger", "Sink"]
