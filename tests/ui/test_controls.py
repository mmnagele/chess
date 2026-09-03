"""Tests für :class:`ui.controls.ChessControls`."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


class Widget:
    """Gemeinsame Basisklasse für Widget-Stubs."""

    def __init__(self, master=None, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.children: list[Widget] = []
        self.state = kwargs.copy()
        self.bindings: dict[str, object] = {}

    def grid(self, **_kwargs) -> None:
        return None

    def pack(self, **_kwargs) -> None:
        return None

    def config(self, **kwargs) -> None:
        self.state.update(kwargs)

    def bind(self, event: str, handler) -> None:
        self.bindings[event] = handler


class Frame(Widget):
    def columnconfigure(self, index: int, weight: int) -> None:
        self.state.setdefault("columns", {})[index] = weight

    def rowconfigure(self, index: int, weight: int) -> None:
        self.state.setdefault("rows", {})[index] = weight


class Label(Widget):
    pass


class LabelFrame(Frame):
    pass


class Text(Widget):
    def __init__(self, master=None, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.buffer = ""

    def delete(self, start: str, end: str) -> None:
        self.buffer = ""

    def insert(self, index: str, content: str) -> None:
        if index == "end":
            self.buffer += content
        else:
            self.buffer = content + self.buffer

    def see(self, _index: str) -> None:
        return None

    def index(self, _index: str) -> str:
        return "end-1c" if self.buffer else "1.0"

    def yview(self, *args, **kwargs):
        return (0.0, 1.0)


class Scrollbar(Widget):
    def config(self, **kwargs) -> None:
        super().config(**kwargs)
        self.command = kwargs.get("command")

    def set(self, *args, **kwargs) -> None:
        self.state["last_set"] = (args, kwargs)


class StringVar:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def get(self) -> str:
        return self._value

    def set(self, value: str) -> None:
        self._value = value


class Combobox(Widget):
    def __init__(self, master=None, textvariable=None, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.variable = textvariable


class Button(Widget):
    pass


class DummyBoardView:
    def __init__(self, master) -> None:
        self.master = master
        self.packed = False

    def pack(self, **_kwargs) -> None:
        self.packed = True


@pytest.fixture()
def controls_module(monkeypatch):
    """Lädt das Modul mit Stub-Implementierungen von ``tkinter``."""

    fake_tk = SimpleNamespace(Frame=Frame, Label=Label, Text=Text, StringVar=StringVar)
    fake_ttk = SimpleNamespace(Scrollbar=Scrollbar, Combobox=Combobox, Button=Button, LabelFrame=LabelFrame)
    fake_tk.ttk = fake_ttk
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    monkeypatch.setitem(sys.modules, "tkinter.ttk", fake_ttk)
    module = importlib.import_module("ui.controls")
    importlib.reload(module)
    monkeypatch.setattr(module, "BoardView", DummyBoardView, raising=False)
    return module


def test_create_board_view_returns_instance(controls_module) -> None:
    """Der Hilfsaufruf erzeugt genau eine Brettansicht."""

    controls = controls_module.ChessControls(SimpleNamespace())
    board = controls.create_board_view()
    assert isinstance(board, DummyBoardView)
    assert board.packed is True


def test_player_type_conversion(controls_module) -> None:
    """Die Auswahlfelder werden korrekt zwischen Anzeige und Interna übersetzt."""

    controls = controls_module.ChessControls(SimpleNamespace())
    assert controls.get_player_type("white") == "human"
    controls.set_player_type("white", "ai")
    assert controls.get_player_type("white") == "ai"


def test_logging_and_commentary_updates(controls_module) -> None:
    """Kommentarfeld und Log reagieren auf neue Einträge."""

    controls = controls_module.ChessControls(SimpleNamespace())
    controls.append_log_entry("Zug 1")
    controls.set_commentary("Hallo")
    controls.clear_log()
    assert controls.commentary_panel._text.buffer.strip() == "Hallo"
    assert controls.log_panel._text.buffer.strip() == ""
