"""Tests für :mod:`ui.app`."""

from __future__ import annotations

from types import SimpleNamespace

from ui.app import ChessApp


class DummyControls:
    """Minimal-Implementation der benötigten Methoden von ``ChessControls``."""

    def __init__(self, master) -> None:
        self.master = master
        self.packed = False

    def pack(self, **kwargs) -> None:  # noqa: D401 - einfache Delegation
        self.packed = True

    def create_board_view(self):
        return SimpleNamespace()


class RecordingController:
    """Controller-Attrappe, die ihre Initialisierungsargumente speichert."""

    def __init__(self, controls, board_view, *, telemetry) -> None:
        self.controls = controls
        self.board_view = board_view
        self.telemetry = telemetry


class DummyRoot:
    """Ersatz für ``tk.Tk`` mit minimaler API."""

    def __init__(self) -> None:
        self.window_title: str | None = None

    def title(self, value: str) -> None:
        self.window_title = value


def test_chess_app_initialises_controller(monkeypatch) -> None:
    """Die App erstellt Steuerungs- und Telemetrieobjekte."""

    monkeypatch.setattr("ui.app.ChessControls", DummyControls)
    monkeypatch.setattr("ui.app.ChessController", RecordingController)
    root = DummyRoot()
    app = ChessApp(root)
    assert root.window_title == "Schachspiel"
    assert isinstance(app.controller, RecordingController)
    assert app.controller.controls.packed is True
    assert app.telemetry is app.controller.telemetry
