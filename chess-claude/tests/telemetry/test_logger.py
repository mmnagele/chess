"""Tests für :mod:`telemetry.logger`."""

from __future__ import annotations

from telemetry import TelemetryEvent, TelemetryLogger, get_telemetry_logger


def test_record_creates_event() -> None:
    """Ein aufgezeichnetes Ereignis wird im internen Speicher abgelegt."""

    logger = TelemetryLogger()
    event = logger.record(phase="test", message="Nachricht", metadata={"foo": "bar"})
    assert isinstance(event, TelemetryEvent)
    assert logger.events == [event]
    assert event.metadata["foo"] == "bar"


def test_add_and_remove_sink() -> None:
    """Registrierte Senken werden beim Aufzeichnen benachrichtigt."""

    logger = TelemetryLogger()
    received: list[str] = []

    def sink(event: TelemetryEvent) -> None:
        received.append(event.message)

    remover = logger.add_sink(sink)
    logger.record(phase="phase", message="eins")
    remover()
    logger.record(phase="phase", message="zwei")

    assert received == ["eins"]


def test_get_telemetry_logger_reuses_instance() -> None:
    """Die Helferfunktion liefert einen Singleton und respektiert Reset."""

    logger = get_telemetry_logger(reset=True)
    logger.record(phase="phase", message="eins")
    same = get_telemetry_logger()
    assert same.events
    other = get_telemetry_logger(reset=True)
    assert other is not logger
    assert not other.events
