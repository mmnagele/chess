"""Tests for ``__main__.py``."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

MODULE_PATH = Path(__file__).resolve().parents[2] / "__main__.py"


def load_module() -> Any:
    spec = importlib.util.spec_from_file_location("chess_main", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[assignment]
    return module


def test_main_initialises_qapplication(monkeypatch) -> None:
    module = load_module()

    class DummyApp:
        def __init__(self, args=None) -> None:
            self.args = args
            self.exec_called = False

        def exec(self) -> int:
            self.exec_called = True
            return 7

    app_instance = DummyApp([])

    class DummyQApplication:
        @staticmethod
        def instance():
            return app_instance

        def __call__(self, *args, **kwargs):
            return app_instance

    created: dict[str, object] = {}

    class DummyWindow:
        def show(self) -> None:
            created["shown"] = True

    monkeypatch.setattr(module, "QApplication", DummyQApplication())
    monkeypatch.setattr(module, "ChessApp", lambda: created.setdefault("window", DummyWindow()))

    result = module.main()

    assert result == 7
    assert created["shown"] is True
