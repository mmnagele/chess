"""Tkinter-Anwendung für das Schachspiel."""

from __future__ import annotations

import tkinter as tk

from .controller import ChessController
from .controls import ChessControls
from telemetry import TelemetryLogger


class ChessApp:
    """Bootstrapper für die Tkinter-Oberfläche."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Schachspiel")

        self.controls = ChessControls(root)
        self.controls.pack(fill="both", expand=True)

        board_view = self.controls.create_board_view()

        telemetry = TelemetryLogger()

        self.controller = ChessController(
            self.controls,
            board_view,
            telemetry=telemetry,
        )

        self.telemetry = telemetry


__all__ = ["ChessApp"]

