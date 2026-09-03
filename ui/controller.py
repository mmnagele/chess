"""Steuerlogik zwischen Engine und Tkinter-Bedienelementen."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

from engine import ChessGame, MoveResult
from engine.fen import export_fen

from ai.commentator import Commentator, Commentary
from ai.openai_client import OpenAIClient
from ai.player import AIPlayer
from ai.provider import MoveGenerationProvider
from ai.strategist import Strategist

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
        ai_provider_factory: Callable[[], MoveGenerationProvider] | None = None,
        commentator_factory: Callable[[], Commentator] | None = None,
    ) -> None:
        self.controls = controls
        self.board_view = board_view
        self.game = game or ChessGame()
        self._telemetry_logger = telemetry
        self._detach_telemetry: Callable[[], None] | None = None

        self._ai_provider_factory = ai_provider_factory or self._create_default_provider
        self._player_types: Dict[str, str] = {}
        self._ai_players: Dict[str, AIPlayer] = {}
        self._active_ai_colour: Optional[str] = None
        self._ai_thinking = False
        self._commentator = (
            commentator_factory() if commentator_factory else Commentator(telemetry=telemetry)
        )
        self._commentary_log: List[Dict[str, object]] = []
        self._commentary_log_path = Path("telemetry/commentary_log.jsonl")
        self._move_history: List[str] = []

        self.selected_square: Optional[Position] = None
        self.valid_moves: List[Position] = []

        self.board_view.set_click_handler(self.on_square_clicked)
        self.controls.set_new_game_callback(self.new_game)
        self.controls.set_player_mode_callback(self._on_player_mode_changed)

        if telemetry:
            self._detach_telemetry = telemetry.add_sink(self._on_telemetry_event)

        self.new_game()

    # ------------------------------------------------------------------
    # Grundlegende Steuerung
    def new_game(self) -> None:
        self._cancel_ai_task()
        self.game.reset()
        self.selected_square = None
        self.valid_moves = []
        self._move_history = []
        self._player_types = {
            "white": self.controls.get_player_type("white"),
            "black": self.controls.get_player_type("black"),
        }
        self._commentary_log = []
        self._flush_commentary_log()
        self._update_board_interaction()
        self.controls.clear_log()
        self.controls.set_commentary("Hier könnte ein Kommentator sprechen…")
        self._refresh_ui()
        self._maybe_trigger_ai_turn()

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
        self._move_history.append(move_notation)
        self.selected_square = None
        self.valid_moves = []
        self._update_commentary()
        self._refresh_ui(result)
        self._handle_game_end(result)
        if not self.game.game_over:
            self._maybe_trigger_ai_turn()

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
        self._update_board_interaction()

    def _find_king(self, colour: str) -> Optional[Position]:
        for position, piece in self.game.board.items():
            if piece and piece == (colour, "K"):
                return position
        return None

    # ------------------------------------------------------------------
    # Spieler- und KI-Verwaltung
    def _create_default_provider(self) -> MoveGenerationProvider:
        return OpenAIClient()

    def _ensure_ai_player(self, colour: str) -> AIPlayer:
        player = self._ai_players.get(colour)
        if player is None:
            provider = self._ai_provider_factory()
            strategist = Strategist(provider, telemetry=self._telemetry_logger)
            player = AIPlayer(strategist)
            self._ai_players[colour] = player
        return player

    def _on_player_mode_changed(self, colour: str, mode: str) -> None:
        self._player_types[colour] = mode
        if mode != "ai" and colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._update_board_interaction()
        self._maybe_trigger_ai_turn()

    def _maybe_trigger_ai_turn(self) -> None:
        if self.game.game_over:
            return
        current_mode = self._player_types.get(self.game.current_player, "human")
        if current_mode != "ai":
            self._cancel_ai_task()
            self._set_ai_thinking(False)
            self._update_board_interaction()
            return
        self._start_ai_turn(self.game.current_player)

    def _start_ai_turn(self, colour: str) -> None:
        try:
            player = self._ensure_ai_player(colour)
        except Exception as exc:
            messagebox.showerror("KI-Initialisierung fehlgeschlagen", str(exc))
            self._player_types[colour] = "human"
            self.controls.set_player_type(colour, "human")
            self._update_board_interaction()
            return

        self._active_ai_colour = colour
        self._set_ai_thinking(True)
        self.controls.set_status("KI denkt…")

        def on_complete(move: Tuple[Position, Position]) -> None:
            self._schedule_on_ui(self._on_ai_move_ready, colour, move)

        def on_error(exc: Exception) -> None:
            self._schedule_on_ui(self._on_ai_error, colour, exc)

        try:
            player.request_move(
                self.game,
                history=tuple(self._move_history),
                on_complete=on_complete,
                on_error=on_error,
            )
        except RuntimeError as exc:
            messagebox.showerror("KI beschäftigt", str(exc))
            self._set_ai_thinking(False)
            self._active_ai_colour = None
            self._update_board_interaction()

    def _on_ai_move_ready(
        self, colour: str, move: Tuple[Position, Position]
    ) -> None:
        if colour != self._active_ai_colour:
            return
        self._active_ai_colour = None
        self._set_ai_thinking(False)
        start, end = move
        self._execute_move(start, end)

    def _on_ai_error(self, colour: str, exc: Exception) -> None:
        if colour != self._active_ai_colour:
            return
        self._active_ai_colour = None
        self._set_ai_thinking(False)
        messagebox.showerror("KI-Fehler", str(exc))
        self._update_board_interaction()

    def _cancel_ai_task(self) -> None:
        if self._active_ai_colour:
            player = self._ai_players.get(self._active_ai_colour)
            if player:
                player.cancel()
        self._active_ai_colour = None
        self._set_ai_thinking(False)

    def _set_ai_thinking(self, thinking: bool) -> None:
        self._ai_thinking = thinking
        self.controls.set_controls_enabled(not thinking)
        self._update_board_interaction()

    def _update_board_interaction(self) -> None:
        allow_human = (
            not self.game.game_over
            and not self._ai_thinking
            and self._player_types.get(self.game.current_player, "human") == "human"
        )
        self.board_view.set_interaction_enabled(allow_human)

    def _schedule_on_ui(self, callback: Callable[..., None], *args: object) -> None:
        self.controls.after(0, lambda: callback(*args))

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

    # ------------------------------------------------------------------
    # Kommentator
    def _update_commentary(self) -> None:
        if not self._commentator:
            return
        try:
            commentary = self._commentator.provide_commentary(
                self.game, history=tuple(self._move_history)
            )
        except Exception as exc:
            self.controls.set_commentary(f"Kommentatorfehler: {exc}")
            self._record_commentary_error(str(exc))
            return

        rendered = self._commentator.render(commentary)
        self.controls.set_commentary(rendered)
        self._record_commentary_entry(commentary)

    def _record_commentary_entry(self, commentary: Commentary) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fen": export_fen(self.game),
            "history": list(self._move_history),
            "commentary": commentary.as_dict(),
        }
        self._commentary_log.append(entry)
        self._flush_commentary_log()

    def _record_commentary_error(self, message: str) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fen": export_fen(self.game),
            "history": list(self._move_history),
            "error": message,
        }
        self._commentary_log.append(entry)
        self._flush_commentary_log()

    def _flush_commentary_log(self) -> None:
        path = self._commentary_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for entry in self._commentary_log:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


__all__ = ["ChessController"]

