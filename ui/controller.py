"""Steuerlogik zwischen Engine und Tkinter-Bedienelementen."""

from __future__ import annotations

from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

from engine import ChessGame, MoveResult

from .board_view import BoardView
from .controls import ChessControls
from telemetry import TelemetryEvent, TelemetryLogger

Position = Tuple[int, int]


class ChessController:
    """Kapselt die Interaktion zwischen Engine und UI."""

    STATUS_MAP: Dict[Optional[str], str] = {
        None: "Bereit",
        "check": "Schach",
        "checkmate": "Schachmatt",
        "stalemate": "Patt",
    }

    def __init__(
        self,
        controls: ChessControls,
        board_view: BoardView,
        *,
        game: Optional[ChessGame] = None,
        telemetry: TelemetryLogger | None = None,
    ) -> None:
        self.controls = controls
        self.board_view = board_view
        self.game = game or ChessGame()
        self._telemetry_logger = telemetry
        self._detach_telemetry: Callable[[], None] | None = None

        self.selected_square: Optional[Position] = None
        self.valid_moves: List[Position] = []

        self.board_view.set_click_handler(self.on_square_clicked)
        self.controls.set_new_game_callback(self.new_game)

        if telemetry:
            self._detach_telemetry = telemetry.add_sink(self._on_telemetry_event)

        self.new_game()

    # ------------------------------------------------------------------
    # Grundlegende Steuerung
    def new_game(self) -> None:
        self.game.reset()
        self.selected_square = None
        self.valid_moves = []
        self.controls.clear_log()
        self.controls.set_commentary("Hier könnte ein Kommentator sprechen…")
        self._refresh_ui()

    def on_square_clicked(self, position: Position) -> None:
        if self.game.game_over:
            return

        piece = self.game.board.get(position)

        if self.selected_square and position in self.valid_moves:
            self._execute_move(self.selected_square, position)
            return

        if piece and piece[0] == self.game.current_player:
            self.selected_square = position
            self.valid_moves = self.game.get_valid_moves(*position)
        else:
            self.selected_square = None
            self.valid_moves = []

        self._refresh_ui()

    # ------------------------------------------------------------------
    # Hilfsmethoden
    def _execute_move(self, start: Position, end: Position) -> None:
        piece = self.game.board.get(start)
        if piece is None:
            return

        move_notation = self._format_move(piece, start, end)

        try:
            result = self.game.apply_move(start, end)
        except ValueError as exc:
            messagebox.showerror("Ungültiger Zug", str(exc))
            self.selected_square = None
            self.valid_moves = []
            self._refresh_ui()
            return

        self.controls.append_log_entry(move_notation)
        self.selected_square = None
        self.valid_moves = []
        self._refresh_ui(result)
        self._handle_game_end(result)

    def _on_telemetry_event(self, event: TelemetryEvent) -> None:
        duration = (
            f" ({event.duration_ms:.0f} ms)" if event.duration_ms is not None else ""
        )
        status = "" if event.status == "info" else f"[{event.status}] "
        entry = f"[{event.phase}] {status}{event.message}{duration}"
        self.controls.append_log_entry(entry)

    def _handle_game_end(self, result: MoveResult) -> None:
        if not result.game_over or not result.just_finished:
            return

        if result.status == "checkmate":
            winner = "Weiss" if result.winner == "white" else "Schwarz"
            messagebox.showinfo("Spielende", f"Schachmatt – {winner} gewinnt.")
        elif result.status == "stalemate":
            messagebox.showinfo("Spielende", "Patt – Unentschieden.")

    def _refresh_ui(self, result: Optional[MoveResult] = None) -> None:
        self.board_view.render_board(self.game.board, self.game.get_piece_symbol)
        self.board_view.reset_colours()

        if result and result.in_check:
            king_position = self._find_king(self.game.current_player)
            if king_position:
                self.board_view.highlight_square(king_position, self.board_view.CHECK_COLOR)

        if self.selected_square:
            self.board_view.highlight_selection(self.selected_square)
            self.board_view.highlight_moves(self.valid_moves)

        status_text = self.STATUS_MAP.get(self.game.status, "Bereit")
        self.controls.set_status(status_text)
        self.controls.set_current_player(self.game.current_player)

    def _find_king(self, colour: str) -> Optional[Position]:
        for position, piece in self.game.board.items():
            if piece and piece == (colour, "K"):
                return position
        return None

    @staticmethod
    def _format_move(piece: Tuple[str, str], start: Position, end: Position) -> str:
        symbol_map = {
            "K": "K",
            "Q": "D",
            "R": "T",
            "B": "L",
            "N": "S",
            "P": "B",
        }
        colour, p_type = piece
        start_notation = ChessController._algebraic(start)
        end_notation = ChessController._algebraic(end)
        name = symbol_map.get(p_type, p_type)
        player = "Weiss" if colour == "white" else "Schwarz"
        return f"{player}: {name} {start_notation} → {end_notation}"

    @staticmethod
    def _algebraic(position: Position) -> str:
        file = chr(ord("a") + position[1])
        rank = str(8 - position[0])
        return f"{file}{rank}"


__all__ = ["ChessController"]

