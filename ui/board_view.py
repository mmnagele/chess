"""Darstellung des Schachbretts und Benutzerinteraktionen."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Iterable, Optional, Tuple

Position = Tuple[int, int]
Piece = Tuple[str, str]


class BoardView(tk.Frame):
    """Visualisiert das Schachbrett und verwaltet Klickinteraktionen."""

    LIGHT_COLOR = "#f0d9b5"
    DARK_COLOR = "#b58863"
    MOVE_COLOR = "#f6f669"
    SELECTION_COLOR = "#f9fca7"
    CHECK_COLOR = "#ff9d9d"

    def __init__(
        self,
        master: tk.Misc,
        on_square_click: Optional[Callable[[Position], None]] = None,
        *,
        square_size: int = 70,
    ) -> None:
        super().__init__(master, borderwidth=2, relief="groove")
        self._on_square_click = on_square_click
        self._square_size = square_size

        self._squares: Dict[Position, tk.Label] = {}
        self._base_colors: Dict[Position, str] = {}

        self._create_squares()

    # ------------------------------------------------------------------
    # Initialisierung
    def _create_squares(self) -> None:
        """Erzeugt alle 64 Brettfelder."""

        for row in range(8):
            for col in range(8):
                base_color = self.LIGHT_COLOR if (row + col) % 2 == 0 else self.DARK_COLOR
                square = tk.Label(
                    self,
                    width=self._square_size // 10,
                    height=self._square_size // 20,
                    bg=base_color,
                    font=("Helvetica", self._square_size // 2),
                    anchor="center",
                )
                square.grid(row=row, column=col, sticky="nsew")
                square.bind(
                    "<Button-1>",
                    lambda _event, position=(row, col): self._handle_click(position),
                )
                self._squares[(row, col)] = square
                self._base_colors[(row, col)] = base_color

        for index in range(8):
            self.columnconfigure(index, weight=1)
            self.rowconfigure(index, weight=1)

    # ------------------------------------------------------------------
    # Callback-Verwaltung
    def set_click_handler(self, callback: Optional[Callable[[Position], None]]) -> None:
        """Setzt den Callback für Brettklicks."""

        self._on_square_click = callback

    def _handle_click(self, position: Position) -> None:
        if self._on_square_click:
            self._on_square_click(position)

    # ------------------------------------------------------------------
    # Darstellung
    def render_board(
        self,
        board: Dict[Position, Optional[Piece]],
        symbol_provider: Callable[[str, str], str],
    ) -> None:
        """Aktualisiert die Brettanzeige anhand des Engine-Zustands."""

        for position, square in self._squares.items():
            piece = board.get(position)
            if piece:
                color, p_type = piece
                square.config(
                    text=symbol_provider(p_type, color),
                    fg="black" if color == "white" else "white",
                )
            else:
                square.config(text="")

    def reset_colours(self) -> None:
        """Setzt die Feldfarben auf die Ausgangswerte zurück."""

        for position, square in self._squares.items():
            square.config(bg=self._base_colors[position])

    def highlight_square(self, position: Position, colour: str) -> None:
        """Färbt ein einzelnes Feld ein."""

        square = self._squares.get(position)
        if square is not None:
            square.config(bg=colour)

    def highlight_moves(self, moves: Iterable[Position]) -> None:
        for move in moves:
            self.highlight_square(move, self.MOVE_COLOR)

    def highlight_selection(self, position: Optional[Position]) -> None:
        if position is not None:
            self.highlight_square(position, self.SELECTION_COLOR)


__all__ = ["BoardView"]

