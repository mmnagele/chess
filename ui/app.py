"""Tkinter-Anwendung für das Schachspiel."""

from __future__ import annotations

import tkinter as tk

from .controller import ChessController
from .controls import ChessControls


class ChessApp:
    """Bootstrapper für die Tkinter-Oberfläche."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Schachspiel")

        self.controls = ChessControls(root)
        self.controls.pack(fill="both", expand=True)

        board_view = self.controls.create_board_view()

        self.controller = ChessController(self.controls, board_view)


__all__ = ["ChessApp"]

