"""Qt controller bridging Engine, AI providers, and PySide6 UI via signals/slots."""

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from ai.anthropic_client import AnthropicClient
from ai.commentator import Commentator
from ai.gemini_client import GeminiClient
from ai.openai_client import OpenAIClient
from ai.player import AIPlayer
from ai.prompt_pack import load_prompt, render_prompt
from ai.provider import ChatRequest, MoveGenerationProvider, MoveSuggestion, ProviderConfig
from ai.strategist import Strategist
from config import get_provider_diagnostics
from engine import ChessGame, MoveResult
from engine.fen import export_fen, square_to_notation
from telemetry import SessionLogger, TelemetryEvent, TelemetryLogger

from .main_window import MainWindow

Position = tuple[int, int]


class _SignalBridge(QObject):
    """Bridge for marshalling background thread results to the UI thread."""

    ai_move_ready = Signal(str, int, object)  # colour, generation, suggestion
    ai_error = Signal(str, int, str)  # colour, generation, error_msg
    chat_response = Signal(str, int, str)  # chat_id, generation, text
    commentary_response = Signal(int, str)  # generation, text
    telemetry_event = Signal(str)  # formatted entry


class ChessController:
    """Orchestrates the chess game, AI interaction, and UI updates."""

    STATUS_MAP: dict[str | None, str] = {
        None: "Ready",
        "check": "Check",
        "checkmate": "Checkmate",
        "stalemate": "Stalemate",
    }

    def __init__(
        self,
        window: MainWindow,
        *,
        game: ChessGame | None = None,
        telemetry: TelemetryLogger | None = None,
    ) -> None:
        self.window = window
        self.game = game or ChessGame()
        self._telemetry_logger = telemetry or TelemetryLogger()

        self._signals = _SignalBridge()
        self._detach_telemetry: Callable[[], None] | None = self._telemetry_logger.add_sink(
            self._on_telemetry_event
        )

        self._player_types: dict[str, str] = {}
        self._active_ai_colour: str | None = None
        self._active_ai_player: AIPlayer | None = None
        self._ai_thinking = False
        self._game_generation: int = 0

        self._move_history: list[str] = []
        self._last_move_positions: tuple[Position, Position] | None = None
        self._session_logger = SessionLogger()

        self.selected_square: Position | None = None
        self.valid_moves: list[Position] = []

        # Animation state: deferred post-animation actions
        self._anim_pending_result: MoveResult | None = None
        self._anim_pending_fen_before: str | None = None
        self._anim_pending_coordinate_move: str | None = None

        self._connect_signals()
        self.new_game()

    def _connect_signals(self) -> None:
        # Board clicks
        self.window.board_widget.square_clicked.connect(self._on_square_clicked)

        # Move animation finished -> trigger post-move actions
        self.window.board_widget.move_animation_finished.connect(self._on_move_animation_finished)

        # Toolbar
        self.window.new_game_btn.clicked.connect(self.new_game)

        # Player config signals
        self.window.white_config.mode_changed.connect(self._on_player_mode_changed)
        self.window.white_config.provider_changed.connect(self._on_player_provider_changed)
        self.window.white_config.model_changed.connect(self._on_player_model_changed)

        self.window.black_config.mode_changed.connect(self._on_player_mode_changed)
        self.window.black_config.provider_changed.connect(self._on_player_provider_changed)
        self.window.black_config.model_changed.connect(self._on_player_model_changed)

        # Commentator signals
        self.window.commentator_panel.config_changed.connect(self._on_commentator_changed)
        self.window.commentator_panel.chat_message_sent.connect(
            lambda msg: self._on_chat_send("commentator", msg)
        )

        # Chat signals
        self.window.white_chat.message_sent.connect(lambda msg: self._on_chat_send("white", msg))
        self.window.black_chat.message_sent.connect(lambda msg: self._on_chat_send("black", msg))

        # Bridge signals (background thread -> UI thread)
        self._signals.ai_move_ready.connect(self._handle_ai_move_ready)
        self._signals.ai_error.connect(self._handle_ai_error)
        self._signals.chat_response.connect(self._handle_chat_response)
        self._signals.commentary_response.connect(self._handle_commentary_response)
        self._signals.telemetry_event.connect(self._handle_telemetry_event)

    @Slot()
    def new_game(self) -> None:
        self._cancel_ai_task()
        self._game_generation += 1
        self.game.reset()
        self._session_logger = SessionLogger()
        self._move_history = []
        self._last_move_positions = None
        self._anim_pending_result = None
        self._anim_pending_fen_before = None
        self._anim_pending_coordinate_move = None

        self.selected_square = None
        self.valid_moves = []

        self._player_types = {
            "white": self.window.get_player_type("white"),
            "black": self.window.get_player_type("black"),
        }

        self.window.clear_log()
        self.window.clear_chat("commentator")
        self.window.clear_chat("white")
        self.window.clear_chat("black")

        self._log_session(
            "game_start",
            {
                "fen": export_fen(self.game),
                "white_mode": self._player_types["white"],
                "black_mode": self._player_types["black"],
            },
        )

        # Refresh provider availability from live environment variables
        self.window.refresh_provider_metadata()

        # Log diagnostic info about API key availability (no secrets)
        for line in get_provider_diagnostics():
            self.window.append_log_entry(f"[keys] {line}")

        self._refresh_ui()
        self._maybe_trigger_ai_turn()

    def shutdown(self) -> None:
        self._cancel_ai_task()
        if self._detach_telemetry:
            self._detach_telemetry()
            self._detach_telemetry = None

    @Slot(int, int)
    def _on_square_clicked(self, row: int, col: int) -> None:
        position = (row, col)
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

    def _execute_move(self, start: Position, end: Position) -> None:
        """Execute a move: apply to engine, animate, then trigger post-move actions."""
        piece = self.game.board.get(start)
        if piece is None:
            return

        moving_colour = piece[0]
        fen_before = export_fen(self.game)
        move_notation = self._format_move(piece, start, end)
        coordinate_move = f"{square_to_notation(start)}{square_to_notation(end)}"

        # Detect capture before applying the move
        target_piece = self.game.board.get(end)
        is_capture = target_piece is not None and target_piece[0] != moving_colour

        # En passant capture: captured pawn is not on the target square
        is_en_passant = (
            piece[1] == "P"
            and self.game.en_passant_target is not None
            and end == self.game.en_passant_target
            and self.game.en_passant_expires == self.game.turn_counter
        )
        if is_en_passant:
            is_capture = True

        # Detect castling before applying
        is_castling = piece[1] == "K" and abs(start[1] - end[1]) == 2

        # Build animation pieces list BEFORE applying the move (original positions)
        anim_pieces: list[tuple[tuple[str, str], Position, Position]] = []
        anim_pieces.append((piece, start, end))

        if is_castling:
            row = start[0]
            if end[1] == 6:  # kingside
                rook_piece = self.game.board.get((row, 7))
                if rook_piece:
                    anim_pieces.append((rook_piece, (row, 7), (row, 5)))
            elif end[1] == 2:  # queenside
                rook_piece = self.game.board.get((row, 0))
                if rook_piece:
                    anim_pieces.append((rook_piece, (row, 0), (row, 3)))

        try:
            result = self.game.apply_move(start, end)
        except ValueError as exc:
            self._show_error("Invalid move", str(exc))
            self._log_session("ui_error", {"message": str(exc), "type": "invalid_move"})
            self.selected_square = None
            self.valid_moves = []
            self._refresh_ui()
            return

        self._last_move_positions = (start, end)

        # Trigger capture animation if a piece was captured
        if is_capture:
            self.window.board_widget.play_capture_animation(end)

        self.window.append_log_entry(move_notation)
        self._move_history.append(move_notation)
        self._log_session(
            "move_made",
            {
                "move": coordinate_move,
                "move_verbose": move_notation,
                "fen_after": export_fen(self.game),
            },
        )

        self.selected_square = None
        self.valid_moves = []

        # Lock input during animation
        self.window.board_widget.set_interaction_enabled(False)

        # Update board state (engine already applied) so animation draws correctly
        self.window.board_widget.render_board(self.game.board, self.game.get_piece_symbol)

        # Store deferred post-animation data
        self._anim_pending_result = result
        self._anim_pending_fen_before = fen_before
        self._anim_pending_coordinate_move = coordinate_move

        # Start the 250ms move animation
        self.window.board_widget.play_move_animation(anim_pieces)

    @Slot()
    def _on_move_animation_finished(self) -> None:
        """Called when move animation completes. Trigger post-move actions."""
        result = self._anim_pending_result
        fen_before = self._anim_pending_fen_before
        coordinate_move = self._anim_pending_coordinate_move

        # Clear pending animation state
        self._anim_pending_result = None
        self._anim_pending_fen_before = None
        self._anim_pending_coordinate_move = None

        # Refresh UI with final state
        self._refresh_ui(result)

        if result:
            self._handle_game_end(result)

        # Request commentary after animation completes
        if fen_before and coordinate_move:
            self._maybe_request_commentary(
                fen_before=fen_before,
                fen_after=export_fen(self.game),
                last_move=coordinate_move,
                move_number=len(self._move_history),
            )

        # Trigger next AI turn after animation completes (sequential safety)
        if not self.game.game_over:
            self._maybe_trigger_ai_turn()

    def _on_telemetry_event(self, event: TelemetryEvent) -> None:
        duration = f" ({event.duration_ms:.0f} ms)" if event.duration_ms is not None else ""
        status = "" if event.status == "info" else f"[{event.status}] "
        entry = f"[{event.phase}] {status}{event.message}{duration}"
        self._signals.telemetry_event.emit(entry)

    @Slot(str)
    def _handle_telemetry_event(self, entry: str) -> None:
        self.window.append_log_entry(entry)

    def _handle_game_end(self, result: MoveResult) -> None:
        if not result.game_over or not result.just_finished:
            return

        if result.status == "checkmate":
            winner = "White" if result.winner == "white" else "Black"
            self._show_info("Game Over", f"Checkmate - {winner} wins.")
        elif result.status == "stalemate":
            self._show_info("Game Over", "Stalemate - draw.")

    def _refresh_ui(self, result: MoveResult | None = None) -> None:
        board = self.window.board_widget
        board.render_board(self.game.board, self.game.get_piece_symbol)
        board.reset_highlights()

        # Last move highlight
        if self._last_move_positions:
            board.highlight_last_move(*self._last_move_positions)

        # Check highlight
        if result and result.in_check:
            king_pos = self._find_king(self.game.current_player)
            if king_pos:
                board.highlight_check(king_pos)

        # Selection and legal moves
        if self.selected_square:
            board.highlight_selection(self.selected_square)
            captures = [m for m in self.valid_moves if self.game.board.get(m) is not None]
            board.highlight_moves(self.valid_moves, captures)

        status_text = self.STATUS_MAP.get(self.game.status, "Ready")
        self.window.set_status(status_text)
        self.window.set_current_player(self.game.current_player)
        self._update_board_interaction()

    def _find_king(self, colour: str) -> Position | None:
        for position, piece in self.game.board.items():
            if piece and piece == (colour, "K"):
                return position
        return None

    def _build_provider(self, provider_key: str, model: str) -> MoveGenerationProvider:
        if not model:
            raise RuntimeError("No model selected.")

        if provider_key == "openai":
            return OpenAIClient(config=ProviderConfig(model=model))
        if provider_key == "anthropic":
            return AnthropicClient(config=ProviderConfig(model=model))
        if provider_key == "gemini":
            return GeminiClient(config=ProviderConfig(model=model))
        raise RuntimeError(f"Unknown provider: {provider_key}")

    def _provider_for_side(self, colour: str) -> MoveGenerationProvider:
        provider_key = self.window.get_player_provider(colour)
        model = self.window.get_player_model(colour)
        if not provider_key:
            raise RuntimeError("No provider selected.")
        if not self.window.is_provider_available(provider_key):
            raise RuntimeError(f"Missing API key for provider '{provider_key}'.")
        return self._build_provider(provider_key, model)

    def _provider_for_commentator(self) -> MoveGenerationProvider:
        provider_key = self.window.get_commentator_provider()
        model = self.window.get_commentator_model()
        if not provider_key:
            raise RuntimeError("No commentator provider selected.")
        if not self.window.is_provider_available(provider_key):
            raise RuntimeError(f"Missing API key for provider '{provider_key}'.")
        return self._build_provider(provider_key, model)

    @Slot(str, str)
    def _on_player_mode_changed(self, colour: str, mode: str) -> None:
        self._player_types[colour] = mode
        if mode != "ai" and colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._update_board_interaction()
        self._refresh_ui()
        self._maybe_trigger_ai_turn()

    @Slot(str, str)
    def _on_player_provider_changed(self, colour: str, provider_key: str) -> None:
        if colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._maybe_trigger_ai_turn()

    @Slot(str, str)
    def _on_player_model_changed(self, colour: str, _model: str) -> None:
        if colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._maybe_trigger_ai_turn()

    @Slot()
    def _on_commentator_changed(self) -> None:
        pass

    def _maybe_trigger_ai_turn(self) -> None:
        if self.game.game_over:
            return
        # Don't start AI while animation is running (sequential safety)
        if self.window.board_widget.is_animating:
            return
        current = self.game.current_player
        current_mode = self._player_types.get(current, "human")
        if current_mode != "ai":
            self._cancel_ai_task()
            self._set_ai_thinking(False)
            self._update_board_interaction()
            return

        if self._ai_thinking and self._active_ai_colour == current:
            return

        self._start_ai_turn(current)

    def _start_ai_turn(self, colour: str) -> None:
        try:
            provider = self._provider_for_side(colour)
        except Exception as exc:
            self._show_warning("AI unavailable", str(exc))
            self._log_session("ui_error", {"type": "provider", "message": str(exc)})
            return

        strategist = Strategist(provider, telemetry=self._telemetry_logger)
        player = AIPlayer(strategist)

        self._active_ai_player = player
        self._active_ai_colour = colour
        generation = self._game_generation
        self._set_ai_thinking(True)
        self.window.set_status("AI is thinking...")

        self._log_session(
            "ai_prompt_sent",
            {
                "mode": "move",
                "side": colour,
                "provider": self.window.get_player_provider(colour),
                "model": self.window.get_player_model(colour),
                "fen": export_fen(self.game),
            },
        )

        def on_complete(suggestion: MoveSuggestion) -> None:
            self._signals.ai_move_ready.emit(colour, generation, suggestion)

        def on_error(exc: Exception) -> None:
            self._signals.ai_error.emit(colour, generation, str(exc))

        try:
            player.request_move(
                self.game,
                history=tuple(self._move_history),
                on_complete=on_complete,
                on_error=on_error,
            )
        except RuntimeError as exc:
            self._show_error("AI busy", str(exc))
            self._set_ai_thinking(False)
            self._active_ai_colour = None
            self._active_ai_player = None
            self._update_board_interaction()

    @Slot(str, int, object)
    def _handle_ai_move_ready(
        self,
        colour: str,
        generation: int,
        suggestion: object,
    ) -> None:
        if generation != self._game_generation:
            return
        if colour != self._active_ai_colour:
            return

        assert isinstance(suggestion, MoveSuggestion)
        self._active_ai_colour = None
        self._active_ai_player = None
        self._set_ai_thinking(False)

        chat_id = "white" if colour == "white" else "black"
        self.window.append_chat_entry(chat_id, f"AI suggested MOVE: {suggestion.move_text}")
        if (
            suggestion.raw_response.strip()
            and suggestion.raw_response.strip() != suggestion.move_text
        ):
            self.window.append_chat_entry(chat_id, f"AI raw response:\n{suggestion.raw_response}")

        self._log_session(
            "ai_response_received",
            {
                "mode": "move",
                "side": colour,
                "move": suggestion.move_text,
                "raw": suggestion.raw_response,
            },
        )

        # Auto-apply the AI move immediately
        self._execute_move(suggestion.start, suggestion.end)

    @Slot(str, int, str)
    def _handle_ai_error(self, colour: str, generation: int, error_msg: str) -> None:
        if generation != self._game_generation:
            return
        if colour != self._active_ai_colour:
            return

        self._active_ai_colour = None
        self._active_ai_player = None
        self._set_ai_thinking(False)
        self._show_error("AI error", error_msg)
        self._update_board_interaction()

        self._log_session(
            "ui_error",
            {
                "type": "ai_move",
                "side": colour,
                "message": error_msg,
            },
        )

    def _cancel_ai_task(self) -> None:
        if self._active_ai_player:
            self._active_ai_player.cancel()
        self._active_ai_colour = None
        self._active_ai_player = None
        self._set_ai_thinking(False)

    def _set_ai_thinking(self, thinking: bool) -> None:
        self._ai_thinking = thinking
        self.window.set_controls_enabled(not thinking)
        self._update_board_interaction()

    def _update_board_interaction(self) -> None:
        animating = self.window.board_widget.is_animating
        allow_human = not self.game.game_over and not self._ai_thinking and not animating
        self.window.board_widget.set_interaction_enabled(allow_human)

    def _on_chat_send(self, chat_id: str, message: str) -> None:
        if chat_id == "commentator":
            self._send_commentator_chat(message)
            return
        if chat_id in {"white", "black"}:
            self._send_side_chat(chat_id, message)
            return

    def _send_side_chat(self, side: str, message: str) -> None:
        colour = side
        if self._player_types.get(colour, "human") != "ai":
            self.window.append_chat_entry(side, "System: This side is not configured as AI.")
            return

        try:
            provider = self._provider_for_side(colour)
        except Exception as exc:
            self.window.append_chat_entry(side, f"System error: {exc}")
            self._log_session("ui_error", {"type": "side_chat", "message": str(exc)})
            return

        self.window.append_chat_entry(side, f"You: {message}")
        fen = export_fen(self.game)

        system_prompt = "\n\n".join(
            [load_prompt("PLAYER_SYSTEM.md"), load_prompt("FORMAT_CONTRACT.md")]
        )
        user_prompt = render_prompt(
            "PLAYER_CHAT_USER_TEMPLATE.md",
            {
                "SIDE_NAME": "White" if colour == "white" else "Black",
                "FEN": fen,
                "USER_MESSAGE": message,
            },
        )

        self._log_session(
            "ai_prompt_sent",
            {
                "mode": "chat",
                "side": colour,
                "provider": self.window.get_player_provider(colour),
                "model": self.window.get_player_model(colour),
                "message": message,
            },
        )
        generation = self._game_generation

        def _worker() -> None:
            try:
                response = provider.chat(
                    ChatRequest(system_prompt=system_prompt, user_prompt=user_prompt)
                )
                text = response.raw_text.strip() or "(empty response)"
                self._signals.chat_response.emit(side, generation, f"AI: {text}")
                self._log_session(
                    "ai_response_received",
                    {"mode": "chat", "side": colour, "response": text},
                )
            except Exception as exc:
                self._signals.chat_response.emit(side, generation, f"AI error: {exc}")
                self._log_session(
                    "ui_error",
                    {"type": "side_chat", "side": colour, "message": str(exc)},
                )

        threading.Thread(target=_worker, name=f"{side}-chat", daemon=True).start()

    @Slot(str, int, str)
    def _handle_chat_response(self, chat_id: str, generation: int, text: str) -> None:
        if generation != self._game_generation:
            return
        self.window.append_chat_entry(chat_id, text)

    def _maybe_request_commentary(
        self,
        *,
        fen_before: str,
        fen_after: str,
        last_move: str,
        move_number: int,
    ) -> None:
        if not self.window.get_commentator_enabled():
            return

        try:
            provider = self._provider_for_commentator()
        except Exception as exc:
            self.window.append_chat_entry("commentator", f"Commentator error: {exc}")
            self._log_session(
                "ui_error",
                {"type": "commentary_provider", "message": str(exc)},
            )
            return

        commentator_type = self.window.get_commentator_type()
        adult_side = self.window.get_adult_side()

        self._log_session(
            "ai_prompt_sent",
            {
                "mode": "commentary",
                "provider": self.window.get_commentator_provider(),
                "model": self.window.get_commentator_model(),
                "commentator_type": commentator_type,
                "last_move": last_move,
            },
        )
        generation = self._game_generation

        def _worker() -> None:
            try:
                commentator = Commentator(provider, telemetry=self._telemetry_logger)
                commentary = commentator.provide_commentary(
                    commentator_type=commentator_type,  # type: ignore[arg-type]
                    adult_side=adult_side,
                    fen_before=fen_before,
                    fen_after=fen_after,
                    last_move=last_move,
                    move_number=move_number,
                )
                rendered = commentator.render(commentary)
                self._signals.commentary_response.emit(generation, f"Commentary: {rendered}")
                self._log_session(
                    "commentary_received",
                    {"text": rendered, "commentator_type": commentator_type},
                )
            except Exception as exc:
                self._signals.commentary_response.emit(generation, f"Commentator error: {exc}")
                self._log_session(
                    "ui_error",
                    {"type": "commentary", "message": str(exc)},
                )

        threading.Thread(target=_worker, name="commentary", daemon=True).start()

    @Slot(int, str)
    def _handle_commentary_response(self, generation: int, text: str) -> None:
        if generation != self._game_generation:
            return
        self.window.append_chat_entry("commentator", text)

    def _send_commentator_chat(self, message: str) -> None:
        self.window.append_chat_entry("commentator", f"You: {message}")
        if not self.window.get_commentator_enabled():
            self.window.append_chat_entry("commentator", "System: Commentator is currently Off.")
            return

        try:
            provider = self._provider_for_commentator()
        except Exception as exc:
            self.window.append_chat_entry("commentator", f"System error: {exc}")
            self._log_session("ui_error", {"type": "commentator_chat", "message": str(exc)})
            return

        commentator_type = self.window.get_commentator_type()
        fen = export_fen(self.game)

        self._log_session(
            "ai_prompt_sent",
            {
                "mode": "commentator_chat",
                "message": message,
                "commentator_type": commentator_type,
            },
        )
        generation = self._game_generation

        def _worker() -> None:
            try:
                commentator = Commentator(provider, telemetry=self._telemetry_logger)
                response = commentator.chat(
                    commentator_type=commentator_type,  # type: ignore[arg-type]
                    fen=fen,
                    user_message=message,
                )
                rendered = commentator.render(response)
                self._signals.commentary_response.emit(generation, f"Commentator: {rendered}")
                self._log_session(
                    "commentary_received",
                    {"mode": "commentator_chat", "text": rendered},
                )
            except Exception as exc:
                self._signals.commentary_response.emit(generation, f"Commentator error: {exc}")
                self._log_session(
                    "ui_error",
                    {"type": "commentator_chat", "message": str(exc)},
                )

        threading.Thread(target=_worker, name="commentator-chat", daemon=True).start()

    @staticmethod
    def _format_move(piece: tuple[str, str], start: Position, end: Position) -> str:
        symbol_map = {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N", "P": "P"}
        colour, p_type = piece
        start_notation = ChessController._algebraic(start)
        end_notation = ChessController._algebraic(end)
        name = symbol_map.get(p_type, p_type)
        player = "White" if colour == "white" else "Black"
        return f"{player}: {name} {start_notation} -> {end_notation}"

    @staticmethod
    def _algebraic(position: Position) -> str:
        file = chr(ord("a") + position[1])
        rank = str(8 - position[0])
        return f"{file}{rank}"

    def _log_session(self, event: str, payload: dict[str, object]) -> None:
        try:
            self._session_logger.log(event, payload)
        except OSError:
            pass

    @staticmethod
    def _show_error(title: str, message: str) -> None:
        QMessageBox.critical(None, title, message)

    @staticmethod
    def _show_warning(title: str, message: str) -> None:
        QMessageBox.warning(None, title, message)

    @staticmethod
    def _show_info(title: str, message: str) -> None:
        QMessageBox.information(None, title, message)


__all__ = ["ChessController"]
