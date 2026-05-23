"""Tests for the entry point ``__main__.py``."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "__main__.py"


def load_module():
    """Load the entry point module."""
    spec = importlib.util.spec_from_file_location("chess_main", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_main_function_exists() -> None:
    """The entry point module has a main() function."""
    module = load_module()
    assert hasattr(module, "main")
    assert callable(module.main)


def test_main_imports_pyside6_app() -> None:
    """The entry point imports from ui_qt.app."""
    module = load_module()
    # Verify it references ChessApp from ui_qt
    import inspect

    source = inspect.getsource(module.main)
    assert "ChessApp" in source
