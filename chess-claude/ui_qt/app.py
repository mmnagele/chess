"""PySide6 application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from telemetry import TelemetryLogger

from .controller import ChessController
from .main_window import MainWindow


class ChessApp:
    """Bootstrapper for the PySide6 chess application."""

    def __init__(self) -> None:
        self.qt_app = QApplication.instance() or QApplication(sys.argv)
        self.qt_app.setStyle("Fusion")

        # Set global font one step larger than default (Qt default is ~9pt)
        base_font = QFont("Segoe UI", 12)
        self.qt_app.setFont(base_font)

        self.window = MainWindow()
        telemetry = TelemetryLogger()
        self.controller = ChessController(self.window, telemetry=telemetry)

        self.window.show()

    def run(self) -> int:
        return self.qt_app.exec()


__all__ = ["ChessApp"]
