"""Tests für das Startskript ``chess_fixed-GPT5-pro.py``."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MODULE_PATH = Path(__file__).resolve().parents[2] / "chess_fixed-GPT5-pro.py"


def load_module() -> Any:
    """Lädt das Startskript als Modul."""

    spec = importlib.util.spec_from_file_location("chess_main", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_main_initialises_tkinter(monkeypatch) -> None:
    """Der Einstiegspunkt erstellt das Tk-Hauptfenster und startet die App."""

    module = load_module()
    root = SimpleNamespace(mainloop=lambda: setattr(root, "loop_called", True))  # type: ignore[name-defined]
    monkeypatch.setattr(module.tk, "Tk", lambda: root)
    created: dict[str, object] = {}
    monkeypatch.setattr(module, "ChessApp", lambda tk_root: created.setdefault("root", tk_root))

    module.main()

    assert created["root"] is root
    assert getattr(root, "loop_called", False) is True
