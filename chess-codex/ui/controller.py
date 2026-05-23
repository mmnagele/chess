"""Controller that wires chess engine, AI providers, and PySide6 controls."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

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
from config import resolve_model_for
from engine import ChessGame, MoveResult
from engine.fen import export_fen, square_to_notation
from telemetry import SessionLogger, TelemetryEvent, TelemetryLogger

from .board_view import BoardView
from .controls import ChessControls

Position = Tuple[int, int]


@dataclass(slots=True)
class _PostMoveActions:
    result: MoveResult
    fen_before: str
    coordinate_move: str
    move_number: int


class _UiBridge(QObject):
    """Thread-safe bridge for marshaling worker results to the UI thread."""

    invoke = Signal(object, object)


class ChessController:
    """Coordinates UI interactions with game state and provider calls."""

    CHAT_WORKER_LIMIT = 6

    STATUS_MAP: Dict[Optional[str], str] = {
        None: "Ready",
        "check": "Check",
        "checkmate": "Checkmate",
        "stalemate": "Stalemate",
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
        self._telemetry_logger = telemetry or TelemetryLogger()
        self._detach_telemetry: Callable[[], None] | None = self._telemetry_logger.add_sink(
            self._on_telemetry_event
        )

        self._ui_bridge = _UiBridge()
        self._ui_bridge.invoke.connect(self._invoke_slot)

        self._player_types: Dict[str, str] = {}
        self._active_ai_colour: Optional[str] = None
        self._active_ai_player: AIPlayer | None = None
        self._ai_thinking = False
        self._animation_in_progress = False
        self._game_generation: int = 0

        self._pending_post_move: _PostMoveActions | None = None

        self._move_history: list[str] = []
        self._session_logger = SessionLogger()
        self._chat_worker_semaphore = threading.BoundedSemaphore(self.CHAT_WORKER_LIMIT)

        self.selected_square: Optional[Position] = None
        self.valid_moves: list[Position] = []

        self.board_view.set_click_handler(self.on_square_clicked)
        self.board_view.move_animation_finished.connect(self._on_move_animation_finished)
        self.controls.set_new_game_callback(self.new_game)
        self.controls.set_player_mode_callback(self._on_player_mode_changed)
        self.controls.set_player_provider_callback(self._on_player_provider_changed)
        self.controls.set_player_model_callback(self._on_player_model_changed)
        self.controls.set_commentator_changed_callback(self._on_commentator_changed)
        self.controls.set_chat_send_callback(self._on_chat_send)

        self._log_session("app_start", {"fen": export_fen(self.game)})
        self.new_game()

    def new_game(self) -> None:
        self._cancel_ai_task()
        self._animation_in_progress = False
        self._pending_post_move = None
        self.board_view.stop_move_animation()
        self._game_generation += 1
        self.game.reset()
        self._session_logger = SessionLogger()
        self._move_history = []
        self.board_view.clear_last_move()

        self.selected_square = None
        self.valid_moves = []

        self._player_types = {
            "white": self.controls.get_player_type("white"),
            "black": self.controls.get_player_type("black"),
        }

        self.controls.clear_log()
        self.controls.clear_chat("commentator")
        self.controls.clear_chat("white")
        self.controls.clear_chat("black")

        self._log_session(
            "game_start",
            {
                "fen": export_fen(self.game),
                "white_mode": self._player_types["white"],
                "black_mode": self._player_types["black"],
            },
        )

        self._refresh_ui()
        self._maybe_trigger_ai_turn()

    def shutdown(self) -> None:
        self._cancel_ai_task()
        self._animation_in_progress = False
        self._pending_post_move = None
        self.board_view.stop_move_animation()
        try:
            self.board_view.move_animation_finished.disconnect(self._on_move_animation_finished)
        except (RuntimeError, TypeError):
            pass
        try:
            self._ui_bridge.invoke.disconnect(self._invoke_slot)
        except (RuntimeError, TypeError):
            pass
        if self._detach_telemetry:
            self._detach_telemetry()
            self._detach_telemetry = None

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

    def _execute_move(self, start: Position, end: Position) -> None:
        piece = self.game.board.get(start)
        if piece is None:
            return

        board_before_move = dict(self.game.board)
        target_before_move = board_before_move.get(end)
        en_passant_capture = (
            piece[1] == "P"
            and target_before_move is None
            and self.game.en_passant_target is not None
            and end == self.game.en_passant_target
            and self.game.en_passant_expires == self.game.turn_counter
        )
        did_capture = target_before_move is not None or en_passant_capture
        fen_before = export_fen(self.game)
        move_notation = self._format_move(piece, start, end)
        coordinate_move = f"{square_to_notation(start)}{square_to_notation(end)}"

        try:
            result = self.game.apply_move(start, end)
        except ValueError as exc:
            self._show_error("Invalid move", str(exc))
            self._log_session("ui_error", {"message": str(exc), "type": "invalid_move"})
            self.selected_square = None
            self.valid_moves = []
            self._refresh_ui()
            return

        self.controls.append_log_entry(move_notation)
        self._move_history.append(move_notation)
        self._log_session(
            "move_played",
            {
                "move": coordinate_move,
                "move_verbose": move_notation,
                "fen_after": export_fen(self.game),
                "history_len": len(self._move_history),
            },
        )

        self.board_view.set_last_move(start, end)
        if did_capture:
            self.board_view.trigger_capture_animation(end)

        self.selected_square = None
        self.valid_moves = []
        self._refresh_ui(result)

        self._pending_post_move = _PostMoveActions(
            result=result,
            fen_before=fen_before,
            coordinate_move=coordinate_move,
            move_number=len(self._move_history),
        )
        move_pieces = self._build_animation_pieces(
            board_before_move=board_before_move,
            start=start,
            end=end,
            moving_piece=piece,
        )
        self._animation_in_progress = self.board_view.animate_move(
            self.game.board,
            move_pieces,
            duration_ms=250,
        )
        self._update_board_interaction()
        if not self._animation_in_progress:
            self._finalize_pending_post_move()

    def _on_telemetry_event(self, event: TelemetryEvent) -> None:
        duration = f" ({event.duration_ms:.0f} ms)" if event.duration_ms is not None else ""
        status = "" if event.status == "info" else f"[{event.status}] "
        entry = f"[{event.phase}] {status}{event.message}{duration}"
        self._schedule_on_ui(self.controls.append_log_entry, entry)

    def _handle_game_end(self, result: MoveResult) -> None:
        if not result.game_over or not result.just_finished:
            return

        if result.status == "checkmate":
            winner = "White" if result.winner == "white" else "Black"
            self._show_info("Game Over", f"Checkmate - {winner} wins.")
        elif result.status == "stalemate":
            self._show_info("Game Over", "Stalemate - draw.")

    def _build_animation_pieces(
        self,
        *,
        board_before_move: dict[Position, tuple[str, str] | None],
        start: Position,
        end: Position,
        moving_piece: tuple[str, str],
    ) -> list[tuple[tuple[str, str], Position, Position]]:
        pieces: list[tuple[tuple[str, str], Position, Position]] = [(moving_piece, start, end)]
        if moving_piece[1] != "K" or abs(start[1] - end[1]) != 2:
            return pieces

        row = start[0]
        if end[1] == 6:
            rook_start, rook_end = (row, 7), (row, 5)
        else:
            rook_start, rook_end = (row, 0), (row, 3)

        rook_piece = board_before_move.get(rook_start)
        if rook_piece is not None:
            pieces.append((rook_piece, rook_start, rook_end))
        return pieces

    def _on_move_animation_finished(self) -> None:
        if not self._animation_in_progress:
            return
        self._animation_in_progress = False
        self._update_board_interaction()
        self._finalize_pending_post_move()

    def _finalize_pending_post_move(self) -> None:
        pending = self._pending_post_move
        if pending is None:
            return
        self._pending_post_move = None

        self._handle_game_end(pending.result)
        self._maybe_request_commentary(
            fen_before=pending.fen_before,
            fen_after=export_fen(self.game),
            last_move=pending.coordinate_move,
            move_number=pending.move_number,
        )

        if not self.game.game_over:
            self._maybe_trigger_ai_turn()

    def _refresh_ui(self, result: Optional[MoveResult] = None) -> None:
        self.board_view.render_board(self.game.board, self.game.get_piece_symbol)
        self.board_view.reset_colours()

        if result and result.in_check:
            king_position = self._find_king(self.game.current_player)
            if king_position:
                self.board_view.highlight_square(king_position, self.board_view.CHECK_COLOR)

        if self.selected_square:
            capture_targets = self._capture_targets_for_selection(self.selected_square)
            self.board_view.highlight_selection(self.selected_square)
            self.board_view.highlight_moves(self.valid_moves, capture_targets=capture_targets)

        status_text = self.STATUS_MAP.get(self.game.status, "Ready")
        self.controls.set_status(status_text)
        self.controls.set_current_player(self.game.current_player)
        self._update_board_interaction()

    def _find_king(self, colour: str) -> Optional[Position]:
        for position, piece in self.game.board.items():
            if piece and piece == (colour, "K"):
                return position
        return None

    def _build_provider(self, provider_key: str, model: str) -> MoveGenerationProvider:
        if not model:
            raise RuntimeError("No model selected.")

        resolved_model = resolve_model_for(provider_key, model)
        if resolved_model != model:
            self.controls.append_log_entry(
                f"[model] normalized {provider_key}: '{model}' -> '{resolved_model}'"
            )

        config = ProviderConfig(model=resolved_model)
        if provider_key == "openai":
            return OpenAIClient(config=config)
        if provider_key == "anthropic":
            return AnthropicClient(config=config)
        if provider_key == "gemini":
            return GeminiClient(config=config)
        raise RuntimeError(f"Unknown provider: {provider_key}")

    def _provider_for_side(self, colour: str) -> MoveGenerationProvider:
        provider_key = self.controls.get_player_provider(colour)
        model = self.controls.get_player_model(colour)
        if not provider_key:
            raise RuntimeError("No provider selected.")
        if not self.controls.is_provider_available(provider_key):
            raise RuntimeError(f"Missing API key for provider '{provider_key}'.")
        return self._build_provider(provider_key, model)

    def _provider_for_commentator(self) -> MoveGenerationProvider:
        provider_key = self.controls.get_commentator_provider()
        model = self.controls.get_commentator_model()
        if not provider_key:
            raise RuntimeError("No commentator provider selected.")
        if not self.controls.is_provider_available(provider_key):
            raise RuntimeError(f"Missing API key for provider '{provider_key}'.")
        return self._build_provider(provider_key, model)

    def _on_player_mode_changed(self, colour: str, mode: str) -> None:
        self._player_types[colour] = mode
        if mode != "ai" and colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._update_board_interaction()
        self._refresh_ui()
        self._maybe_trigger_ai_turn()

    def _on_player_provider_changed(self, colour: str, provider_key: str) -> None:
        _ = provider_key
        if colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._maybe_trigger_ai_turn()

    def _on_player_model_changed(self, colour: str, _model: str) -> None:
        if colour == self._active_ai_colour:
            self._cancel_ai_task()
        self._maybe_trigger_ai_turn()

    def _on_commentator_changed(self) -> None:
        return None

    def _maybe_trigger_ai_turn(self) -> None:
        if self.game.game_over:
            return
        if self._ai_thinking or self._animation_in_progress:
            return

        current = self.game.current_player
        current_mode = self._player_types.get(current, "human")
        if current_mode != "ai":
            self._cancel_ai_task()
            self._set_ai_thinking(False)
            self._update_board_interaction()
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
        self.controls.set_status("AI is thinking...")

        chat_id = "white" if colour == "white" else "black"
        self.controls.append_chat_entry(
            chat_id,
            "System MOVE prompt: state dispatched to provider.",
            role="system",
            source="[System]",
        )

        self._log_session(
            "prompt_sent",
            {
                "mode": "move",
                "actor": colour,
                "provider": self.controls.get_player_provider(colour),
                "model": self.controls.get_player_model(colour),
                "fen": export_fen(self.game),
                "history": list(self._move_history),
                "template": "PLAYER_MOVE_USER_TEMPLATE.md",
            },
        )

        def on_complete(suggestion: MoveSuggestion) -> None:
            self._schedule_on_ui(self._on_ai_move_ready, colour, generation, suggestion)

        def on_error(exc: Exception) -> None:
            self._schedule_on_ui(self._on_ai_error, colour, generation, exc)

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

    def _on_ai_move_ready(
        self,
        colour: str,
        generation: int,
        suggestion: MoveSuggestion,
    ) -> None:
        if generation != self._game_generation:
            return
        if colour != self._active_ai_colour:
            return

        self._active_ai_colour = None
        self._active_ai_player = None
        self._set_ai_thinking(False)

        chat_id = "white" if colour == "white" else "black"
        self.controls.append_chat_entry(
            chat_id,
            f"MOVE: {suggestion.move_text}",
            role="ai",
            source="[AI]",
        )
        if (
            suggestion.raw_response.strip()
            and suggestion.raw_response.strip() != suggestion.move_text
        ):
            self.controls.append_chat_entry(
                chat_id,
                suggestion.raw_response,
                role="ai",
                source="[AI raw]",
            )

        self._log_session(
            "response_received",
            {
                "mode": "move",
                "actor": colour,
                "move": suggestion.move_text,
                "raw": suggestion.raw_response,
            },
        )

        self.controls.set_status(f"Applying AI move: {suggestion.move_text}")
        self._execute_move(suggestion.start, suggestion.end)

    def _on_ai_error(self, colour: str, generation: int, exc: Exception) -> None:
        if generation != self._game_generation:
            return
        if colour != self._active_ai_colour:
            return

        self._active_ai_colour = None
        self._active_ai_player = None
        self._set_ai_thinking(False)
        chat_id = "white" if colour == "white" else "black"
        self.controls.append_chat_entry(
            chat_id,
            str(exc),
            role="error",
            source="[AI error]",
        )
        self._show_error("AI error", str(exc))
        self._update_board_interaction()

        self._log_session(
            "errors",
            {
                "type": "ai_move",
                "side": colour,
                "message": str(exc),
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
        self.controls.set_controls_enabled(not thinking)
        self._update_board_interaction()

    def _update_board_interaction(self) -> None:
        allow_human = (
            not self.game.game_over
            and not self._ai_thinking
            and not self._animation_in_progress
        )
        self.board_view.set_interaction_enabled(allow_human)

    def _on_chat_send(self, chat_id: str, message: str) -> None:
        if chat_id == "commentator":
            self._send_commentator_chat(message)
            return
        if chat_id in {"white", "black"}:
            self._send_side_chat(chat_id, message)
            return

    def _send_side_chat(self, side: str, message: str) -> None:
        colour = "white" if side == "white" else "black"
        if self._player_types.get(colour, "human") != "ai":
            self.controls.append_chat_entry(
                side,
                "This side is not configured as AI.",
                role="system",
                source="[System]",
            )
            return

        try:
            provider = self._provider_for_side(colour)
        except Exception as exc:
            self.controls.append_chat_entry(
                side,
                str(exc),
                role="error",
                source="[System error]",
            )
            self._log_session("errors", {"type": "side_chat", "message": str(exc)})
            return

        self.controls.append_chat_entry(side, message, role="user", source="[User]")
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

        self.controls.append_chat_entry(
            side,
            user_prompt,
            role="system",
            source="[System prompt]",
        )

        self._log_session(
            "prompt_sent",
            {
                "mode": "chat",
                "actor": colour,
                "provider": self.controls.get_player_provider(colour),
                "model": self.controls.get_player_model(colour),
                "message": message,
                "template": "PLAYER_CHAT_USER_TEMPLATE.md",
            },
        )

        def _worker() -> None:
            try:
                response = provider.chat(
                    ChatRequest(system_prompt=system_prompt, user_prompt=user_prompt)
                )
                text = response.raw_text.strip() or "(empty response)"
                self._schedule_on_ui(
                    lambda side_id=side, payload=text: self.controls.append_chat_entry(
                        side_id,
                        payload,
                        role="ai",
                        source="[AI]",
                    )
                )
                self._log_session(
                    "response_received",
                    {
                        "mode": "chat",
                        "actor": colour,
                        "response": text,
                    },
                )
            except Exception as exc:
                self._schedule_on_ui(
                    lambda side_id=side, error_text=str(exc): self.controls.append_chat_entry(
                        side_id,
                        error_text,
                        role="error",
                        source="[AI error]",
                    )
                )
                self._log_session(
                    "errors",
                    {
                        "type": "side_chat",
                        "side": colour,
                        "message": str(exc),
                    },
                )

        self._start_background_worker(
            name=f"{side}-chat",
            chat_id=side,
            error_type="side_chat",
            worker=_worker,
        )

    def _maybe_request_commentary(
        self,
        *,
        fen_before: str,
        fen_after: str,
        last_move: str,
        move_number: int,
    ) -> None:
        if not self.controls.get_commentator_enabled():
            return

        try:
            provider = self._provider_for_commentator()
        except Exception as exc:
            self.controls.append_chat_entry(
                "commentator",
                str(exc),
                role="error",
                source="[Commentator error]",
            )
            self._log_session(
                "errors",
                {
                    "type": "commentary_provider",
                    "message": str(exc),
                },
            )
            return

        commentator_type = self.controls.get_commentator_type()
        adult_side = self.controls.get_adult_side()

        self.controls.append_chat_entry(
            "commentator",
            f"System commentary prompt: move {move_number}, {last_move}",
            role="system",
            source="[System]",
        )

        self._log_session(
            "prompt_sent",
            {
                "mode": "commentary",
                "actor": "commentator",
                "provider": self.controls.get_commentator_provider(),
                "model": self.controls.get_commentator_model(),
                "commentator_type": commentator_type,
                "last_move": last_move,
                "template": "COMMENTATOR_EVENT_USER_TEMPLATE.md",
            },
        )

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
                    recent_moves=tuple(self._move_history[-5:]),
                )
                rendered = commentator.render(commentary)
                self._schedule_on_ui(
                    lambda payload=rendered: self.controls.append_chat_entry(
                        "commentator",
                        payload,
                        role="ai",
                        source="[Commentator]",
                    )
                )
                self._log_session(
                    "response_received",
                    {
                        "mode": "commentary",
                        "text": rendered,
                        "commentator_type": commentator_type,
                    },
                )
            except Exception as exc:
                self._schedule_on_ui(
                    lambda error_text=str(exc): self.controls.append_chat_entry(
                        "commentator",
                        error_text,
                        role="error",
                        source="[Commentator error]",
                    )
                )
                self._log_session(
                    "errors",
                    {
                        "type": "commentary",
                        "message": str(exc),
                    },
                )

        self._start_background_worker(
            name="commentary",
            chat_id="commentator",
            error_type="commentary",
            worker=_worker,
        )

    def _send_commentator_chat(self, message: str) -> None:
        self.controls.append_chat_entry("commentator", message, role="user", source="[User]")
        if not self.controls.get_commentator_enabled():
            self.controls.append_chat_entry(
                "commentator",
                "Commentator is currently Off.",
                role="system",
                source="[System]",
            )
            return

        try:
            provider = self._provider_for_commentator()
        except Exception as exc:
            self.controls.append_chat_entry(
                "commentator",
                str(exc),
                role="error",
                source="[System error]",
            )
            self._log_session("errors", {"type": "commentator_chat", "message": str(exc)})
            return

        commentator_type = self.controls.get_commentator_type()
        fen = export_fen(self.game)

        self._log_session(
            "prompt_sent",
            {
                "mode": "commentator_chat",
                "actor": "commentator",
                "message": message,
                "commentator_type": commentator_type,
            },
        )

        def _worker() -> None:
            try:
                commentator = Commentator(provider, telemetry=self._telemetry_logger)
                response = commentator.chat(
                    commentator_type=commentator_type,  # type: ignore[arg-type]
                    fen=fen,
                    user_message=message,
                )
                rendered = commentator.render(response)
                self._schedule_on_ui(
                    lambda payload=rendered: self.controls.append_chat_entry(
                        "commentator",
                        payload,
                        role="ai",
                        source="[Commentator]",
                    )
                )
                self._log_session(
                    "response_received",
                    {
                        "mode": "commentator_chat",
                        "text": rendered,
                    },
                )
            except Exception as exc:
                self._schedule_on_ui(
                    lambda error_text=str(exc): self.controls.append_chat_entry(
                        "commentator",
                        error_text,
                        role="error",
                        source="[Commentator error]",
                    )
                )
                self._log_session(
                    "errors",
                    {
                        "type": "commentator_chat",
                        "message": str(exc),
                    },
                )

        self._start_background_worker(
            name="commentator-chat",
            chat_id="commentator",
            error_type="commentator_chat",
            worker=_worker,
        )

    def _start_background_worker(
        self,
        *,
        name: str,
        chat_id: str,
        error_type: str,
        worker: Callable[[], None],
    ) -> None:
        if not self._chat_worker_semaphore.acquire(blocking=False):
            self.controls.append_chat_entry(
                chat_id,
                "Too many concurrent background requests. Please wait a moment.",
                role="system",
                source="[System]",
            )
            self._log_session(
                "errors",
                {
                    "type": f"{error_type}_queue_full",
                    "message": "background worker limit reached",
                    "limit": self.CHAT_WORKER_LIMIT,
                },
            )
            return

        def _wrapped() -> None:
            try:
                worker()
            finally:
                self._chat_worker_semaphore.release()

        try:
            threading.Thread(target=_wrapped, name=name, daemon=True).start()
        except Exception:
            self._chat_worker_semaphore.release()
            raise

    def _schedule_on_ui(self, callback: Callable[..., None], *args: object) -> None:
        self._ui_bridge.invoke.emit(callback, args)

    @Slot(object, object)
    def _invoke_slot(self, callback: object, args: object) -> None:
        if not callable(callback):
            return
        if isinstance(args, tuple):
            callback(*args)
        else:
            callback(args)

    @staticmethod
    def _format_move(piece: Tuple[str, str], start: Position, end: Position) -> str:
        symbol_map = {
            "K": "K",
            "Q": "Q",
            "R": "R",
            "B": "B",
            "N": "N",
            "P": "P",
        }
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

    def _capture_targets_for_selection(self, start: Position) -> list[Position]:
        piece = self.game.board.get(start)
        if piece is None:
            return []

        targets: list[Position] = []
        for target in self.valid_moves:
            occupant = self.game.board.get(target)
            if occupant is not None and occupant[0] != piece[0]:
                targets.append(target)
                continue

            if (
                piece[1] == "P"
                and occupant is None
                and self.game.en_passant_target is not None
                and target == self.game.en_passant_target
                and self.game.en_passant_expires == self.game.turn_counter
            ):
                targets.append(target)

        return targets

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
