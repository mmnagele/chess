"""Tkinter-Oberfläche für das Schachspiel."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Dict, List, Optional, Tuple

from engine import ChessGame, MoveResult

Position = Tuple[int, int]


class ChessApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Schachspiel")

        self.game = ChessGame()

        self.controls_frame = tk.Frame(root)
        self.controls_frame.pack()

        self.player_color = tk.Label(
            self.controls_frame, text="", width=10, height=2, bg="white"
        )
        self.player_color.grid(row=0, column=0)

        self.new_game_button = tk.Button(
            self.controls_frame, text="Neues Spiel", command=self.new_game
        )
        self.new_game_button.grid(row=0, column=1)

        self.status_text = tk.Label(self.controls_frame, text="", width=20, height=2)
        self.status_text.grid(row=0, column=2)

        self.board_frame = tk.Frame(root)
        self.board_frame.pack()

        self.squares: Dict[Position, tk.Label] = {}
        self.selected_piece: Optional[Position] = None
        self.valid_moves: List[Position] = []

        self.create_board()
        self.new_game()

    # ---------------- UI-Hilfen -----------------
    def create_board(self) -> None:
        for row in range(8):
            for col in range(8):
                color = "white" if (row + col) % 2 == 0 else "gray"
                square = tk.Label(
                    self.board_frame,
                    width=8,
                    height=4,
                    bg=color,
                    font=("Helvetica", 18),
                )
                square.grid(row=row, column=col)
                square.bind(
                    "<Button-1>",
                    lambda event, r=row, c=col: self.on_square_click(r, c),
                )
                self.squares[(row, col)] = square

    def new_game(self) -> None:
        self.game.reset()
        self.selected_piece = None
        self.valid_moves = []
        self.update_board()
        self.update_status()
        self.clear_highlight()

    def update_board(self) -> None:
        for (row, col), square in self.squares.items():
            piece = self.game.board[(row, col)]
            if piece:
                color, p_type = piece
                square.config(text=self.game.get_piece_symbol(p_type, color))
            else:
                square.config(text="")

    def on_square_click(self, row: int, col: int) -> None:
        if self.game.game_over:
            return

        position = (row, col)
        piece = self.game.board[position]

        if self.selected_piece is not None:
            if position in self.valid_moves:
                self.execute_move(self.selected_piece, position)
                self.selected_piece = None
                self.valid_moves = []
                self.clear_highlight()
            else:
                self.selected_piece = None
                self.valid_moves = []
                self.clear_highlight()
        elif piece and piece[0] == self.game.current_player:
            self.selected_piece = position
            self.valid_moves = self.game.get_valid_moves(row, col)
            self.highlight_moves(self.valid_moves)

    def execute_move(self, start: Position, end: Position) -> None:
        try:
            result = self.game.apply_move(start, end)
        except ValueError as exc:
            messagebox.showerror("Ungültiger Zug", str(exc))
            return

        self.update_board()
        self.update_status(result)

    # ----------------- UI-Status -----------------
    def update_status(self, result: Optional[MoveResult] = None) -> None:
        self.player_color.config(bg=self.game.current_player)

        status_map = {
            None: "",
            "check": "Schach",
            "checkmate": "Schachmatt",
            "stalemate": "Patt",
        }
        self.status_text.config(text=status_map.get(self.game.status, ""))

        if result and result.just_finished:
            if result.status == "checkmate":
                winner = "Weiss" if result.winner == "white" else "Schwarz"
                messagebox.showinfo("Spielende", f"Schachmatt – {winner} gewinnt.")
            elif result.status == "stalemate":
                messagebox.showinfo("Spielende", "Patt – Unentschieden.")

    # ----------------- Highlighting -----------------
    def highlight_moves(self, moves: List[Position]) -> None:
        for row, col in moves:
            self.squares[(row, col)].config(bg="yellow")

    def clear_highlight(self) -> None:
        for row in range(8):
            for col in range(8):
                color = "white" if (row + col) % 2 == 0 else "gray"
                self.squares[(row, col)].config(bg=color)


__all__ = ["ChessApp"]
