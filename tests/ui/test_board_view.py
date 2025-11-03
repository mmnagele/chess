"""Tests für :class:`ui.board_view.BoardView`."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace

import pytest


class FakeLabel:
    """Einfaches Label mit speicherbarem Zustand."""

    def __init__(self, master, **kwargs) -> None:
        self.master = master
        self.state = dict(kwargs)
        self.bindings: dict[str, object] = {}

    def grid(self, **_kwargs) -> None:
        return None

    def bind(self, event: str, handler) -> None:
        self.bindings[event] = handler

    def config(self, **kwargs) -> None:
        self.state.update(kwargs)

    def cget(self, key: str):
        return self.state.get(key)


class FakeFrame:
    """Einfache Rahmen-Attrappe mit Konfigurationsmöglichkeiten."""

    def __init__(self, master, **_kwargs) -> None:
        self.master = master
        self.columns: dict[int, dict[str, int]] = {}
        self.rows: dict[int, dict[str, int]] = {}

    def columnconfigure(self, index: int, weight: int) -> None:
        self.columns[index] = {"weight": weight}

    def rowconfigure(self, index: int, weight: int) -> None:
        self.rows[index] = {"weight": weight}


@pytest.fixture()
def board_module(monkeypatch):
    """Lädt das Modul mit einer ersetzten ``tkinter``-Implementierung."""

    fake_tk = SimpleNamespace(Frame=FakeFrame, Label=FakeLabel)
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    module = importlib.import_module("ui.board_view")
    importlib.reload(module)
    monkeypatch.setattr(module, "tk", fake_tk, raising=False)
    return module


def test_render_board_updates_labels(board_module) -> None:
    """Die Brettdarstellung spiegelt den Engine-Zustand wider."""

    board = board_module.BoardView(master=SimpleNamespace(), square_size=20)
    board.render_board({(7, 4): ("white", "K")}, lambda p, c: "K")
    label = board._squares[(7, 4)]
    assert label.cget("text") == "K"


def test_click_handler_invoked(board_module) -> None:
    """Ein gesetzter Callback wird bei Klick ausgelöst."""

    triggered: list[tuple[int, int]] = []
    board = board_module.BoardView(master=SimpleNamespace(), square_size=20)
    board.set_click_handler(lambda pos: triggered.append(pos))
    label = board._squares[(0, 0)]
    handler = label.bindings["<Button-1>"]
    handler(None)
    assert triggered == [(0, 0)]


def test_highlighting_functions(board_module) -> None:
    """Markierungen verändern die gespeicherten Farben."""

    board = board_module.BoardView(master=SimpleNamespace(), square_size=20)
    board.highlight_square((0, 0), "#ffffff")
    assert board._squares[(0, 0)].cget("bg") == "#ffffff"
    board.highlight_moves([(0, 1)])
    assert board._squares[(0, 1)].cget("bg") == board.MOVE_COLOR
    board.highlight_selection((0, 2))
    assert board._squares[(0, 2)].cget("bg") == board.SELECTION_COLOR
    board.reset_colours()
    assert board._squares[(0, 0)].cget("bg") == board._base_colors[(0, 0)]


def test_interaction_toggle(board_module) -> None:
    """Die Interaktionsflagge beeinflusst den Klick-Handler."""

    board = board_module.BoardView(master=SimpleNamespace(), square_size=20)
    called: list[tuple[int, int]] = []
    board.set_click_handler(lambda pos: called.append(pos))
    board.set_interaction_enabled(False)
    handler = board._squares[(0, 0)].bindings["<Button-1>"]
    handler(None)
    assert not called
    board.set_interaction_enabled(True)
    handler(None)
    assert called == [(0, 0)]
