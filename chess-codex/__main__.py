"""Entrypoint for the PySide6 chess application."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui.app import ChessApp


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = ChessApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
