"""Tests for :class:`ui_qt.controller.ChessController`."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from ai.provider import ChatResponse, MoveSuggestion
from engine import ChessGame
from telemetry import TelemetryLogger

Position = tuple[int, int]


@dataclass
class DummySessionLogger:
    events: list[tuple[str, dict]]

    def log(self, event: str, payload: dict) -> None:
        self.events.append((event, payload))


class DummyProvider:
    def __init__(self, move_text: str = "MOVE: e2e4", chat_text: str = "chat") -> None:
        self.move_text = move_text
        self.chat_text = chat_text

    def generate_move(self, request):
        from ai.provider import MoveGenerationResponse

        return MoveGenerationResponse(raw_text=self.move_text)

    def chat(self, request):
        return ChatResponse(raw_text=self.chat_text)


class DummyWindow:
    """Mock of MainWindow with the same API used by ChessController."""

    def __init__(self) -> None:
        self.player_types: dict[str, str] = {"white": "human", "black": "human"}
        self.player_providers: dict[str, str] = {"white": "openai", "black": "openai"}
        self.player_models: dict[str, str] = {"white": "gpt-4o-mini", "black": "gpt-4o-mini"}
        self.provider_available = {"openai": True, "anthropic": False, "gemini": False}

        self.commentator_enabled_val = False
        self.commentator_type_val = "Adult Coach"
        self.commentator_provider_val = "openai"
        self.commentator_model_val = "gpt-4o-mini"
        self.adult_side_val = "White"

        self.log_entries: list[str] = []
        self.chat_entries: dict[str, list[str]] = {"commentator": [], "white": [], "black": []}
        self.status: str | None = None
        self.current_player: str | None = None
        self.controls_enabled = True

        # Mock board widget with animation support
        self.board_widget = MagicMock()
        self.board_widget.square_clicked = MagicMock()
        self.board_widget.square_clicked.connect = MagicMock()
        self.board_widget.move_animation_finished = MagicMock()
        self.board_widget.move_animation_finished.connect = MagicMock()
        self.board_widget.is_animating = False

        # Make play_move_animation immediately call the finished callback
        def _instant_animation(pieces):
            """Simulate instant animation completion for tests."""
            pass  # Animation finished signal called manually in tests

        self.board_widget.play_move_animation = MagicMock(side_effect=_instant_animation)

        # Mock buttons/configs
        self.new_game_btn = MagicMock()
        self.white_config = MagicMock()
        self.white_config.mode_changed = MagicMock()
        self.white_config.mode_changed.connect = MagicMock()
        self.white_config.provider_changed = MagicMock()
        self.white_config.provider_changed.connect = MagicMock()
        self.white_config.model_changed = MagicMock()
        self.white_config.model_changed.connect = MagicMock()

        self.black_config = MagicMock()
        self.black_config.mode_changed = MagicMock()
        self.black_config.mode_changed.connect = MagicMock()
        self.black_config.provider_changed = MagicMock()
        self.black_config.provider_changed.connect = MagicMock()
        self.black_config.model_changed = MagicMock()
        self.black_config.model_changed.connect = MagicMock()

        self.commentator_panel = MagicMock()
        self.commentator_panel.config_changed = MagicMock()
        self.commentator_panel.config_changed.connect = MagicMock()
        self.commentator_panel.chat_message_sent = MagicMock()
        self.commentator_panel.chat_message_sent.connect = MagicMock()

        self.white_chat = MagicMock()
        self.white_chat.message_sent = MagicMock()
        self.white_chat.message_sent.connect = MagicMock()
        self.black_chat = MagicMock()
        self.black_chat.message_sent = MagicMock()
        self.black_chat.message_sent.connect = MagicMock()

    def get_player_type(self, colour: str) -> str:
        return self.player_types[colour]

    def get_player_provider(self, colour: str) -> str:
        return self.player_providers[colour]

    def get_player_model(self, colour: str) -> str:
        return self.player_models[colour]

    def is_provider_available(self, provider_key: str) -> bool:
        return self.provider_available.get(provider_key, False)

    def get_commentator_enabled(self) -> bool:
        return self.commentator_enabled_val

    def get_commentator_type(self) -> str:
        return self.commentator_type_val

    def get_commentator_provider(self) -> str:
        return self.commentator_provider_val

    def get_commentator_model(self) -> str:
        return self.commentator_model_val

    def get_adult_side(self) -> str:
        return self.adult_side_val

    def set_status(self, status: str) -> None:
        self.status = status

    def set_current_player(self, colour: str) -> None:
        self.current_player = colour

    def clear_log(self) -> None:
        self.log_entries.clear()

    def append_log_entry(self, entry: str) -> None:
        self.log_entries.append(entry)

    def clear_chat(self, chat_id: str) -> None:
        self.chat_entries[chat_id].clear()

    def append_chat_entry(self, chat_id: str, text: str) -> None:
        self.chat_entries[chat_id].append(text)

    def set_controls_enabled(self, enabled: bool) -> None:
        self.controls_enabled = enabled

    def refresh_provider_metadata(self) -> None:
        pass


@pytest.fixture()
def controller(monkeypatch):
    from ui_qt.controller import ChessController

    window = DummyWindow()
    session_events: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        "ui_qt.controller.SessionLogger", lambda: DummySessionLogger(session_events)
    )
    monkeypatch.setattr(
        "ui_qt.controller.QMessageBox",
        MagicMock(),
    )

    ctl = ChessController(
        window,
        game=ChessGame(),
        telemetry=TelemetryLogger(),
    )
    ctl._test_session_events = session_events  # type: ignore[attr-defined]

    monkeypatch.setattr(ctl, "_provider_for_side", lambda _c: DummyProvider())
    monkeypatch.setattr(
        ctl, "_provider_for_commentator", lambda: DummyProvider(chat_text="SUMMARY: ...")
    )

    return ctl


def _complete_animation(controller) -> None:
    """Simulate animation completion by calling the finished handler."""
    controller._on_move_animation_finished()


def test_new_game_resets_state(controller) -> None:
    controller.window.append_log_entry("Dummy")
    controller.new_game()

    # After new_game the old "Dummy" entry is gone; only diagnostic [keys] lines remain
    assert "Dummy" not in controller.window.log_entries
    assert all("[keys]" in e for e in controller.window.log_entries)
    assert controller.selected_square is None
    assert controller.window.status is not None


def test_on_square_clicked_executes_move_with_animation(controller) -> None:
    controller.new_game()
    controller._on_square_clicked(6, 4)
    assert controller.selected_square == (6, 4)

    controller._on_square_clicked(4, 4)
    # Move is applied to engine, animation is started
    assert controller.selected_square is None
    assert controller.window.board_widget.play_move_animation.called
    # Move applied to engine immediately
    assert controller.game.current_player == "black"
    assert controller._move_history

    # Complete the animation to trigger post-move actions
    _complete_animation(controller)


def test_ai_turn_auto_applies_move(controller, monkeypatch) -> None:
    """AI moves are auto-applied to the engine (not just suggested)."""
    controller.window.player_types["white"] = "ai"

    def immediate_request(self, game, *, history=(), on_complete=None, on_error=None):
        if on_complete:
            on_complete(
                MoveSuggestion(
                    start=(6, 4),
                    end=(4, 4),
                    move_text="e2e4",
                    raw_response="MOVE: e2e4",
                )
            )

    monkeypatch.setattr("ai.player.AIPlayer.request_move", immediate_request)

    controller.new_game()

    # Move was auto-applied: engine state updated
    assert controller.game.current_player == "black"
    # Animation was triggered
    assert controller.window.board_widget.play_move_animation.called
    # Chat entry shows the AI move
    assert any("MOVE: e2e4" in entry for entry in controller.window.chat_entries["white"])


def test_en_passant_triggers_capture_animation(controller) -> None:
    """En passant capture fires play_capture_animation on the e.p. target square."""
    controller.new_game()
    game = controller.game

    # Set up en passant: e2e4, a7a6, e4e5, d7d5 -> exd6 e.p.
    controller._on_square_clicked(6, 4)  # select e2
    controller._on_square_clicked(4, 4)  # move to e4
    _complete_animation(controller)

    controller._on_square_clicked(1, 0)  # select a7
    controller._on_square_clicked(2, 0)  # move to a6 (filler)
    _complete_animation(controller)

    controller._on_square_clicked(4, 4)  # select e5
    controller._on_square_clicked(3, 4)  # move to e5
    _complete_animation(controller)

    controller._on_square_clicked(1, 3)  # select d7
    controller._on_square_clicked(3, 3)  # move to d5
    _complete_animation(controller)

    # Now en passant is available: white pawn on e5 can capture d6 (e.p.)
    assert game.en_passant_target == (2, 3)  # d6
    controller.window.board_widget.play_capture_animation.reset_mock()

    controller._on_square_clicked(3, 4)  # select e5 pawn
    controller._on_square_clicked(2, 3)  # capture en passant to d6

    controller.window.board_widget.play_capture_animation.assert_called_once_with((2, 3))


def test_chat_send_routes_to_side_chat(controller) -> None:
    controller.window.player_types["white"] = "ai"
    controller._player_types["white"] = "ai"
    controller._on_chat_send("white", "hello")

    assert controller.window.chat_entries["white"]
    assert controller.window.chat_entries["white"][0] == "You: hello"


def test_handle_chat_response_ignores_stale_generation(controller) -> None:
    controller.window.chat_entries["white"].clear()
    controller._game_generation = 5

    controller._handle_chat_response("white", 4, "AI: stale")

    assert controller.window.chat_entries["white"] == []


def test_handle_commentary_response_ignores_stale_generation(controller) -> None:
    controller.window.chat_entries["commentator"].clear()
    controller._game_generation = 7

    controller._handle_commentary_response(6, "Commentary: stale")

    assert controller.window.chat_entries["commentator"] == []


def test_maybe_trigger_ai_turn_skips_duplicate_inflight(controller, monkeypatch) -> None:
    controller.game.current_player = "white"
    controller._player_types["white"] = "ai"
    controller._ai_thinking = True
    controller._active_ai_colour = "white"
    mocked_start = MagicMock()
    monkeypatch.setattr(controller, "_start_ai_turn", mocked_start)

    controller._maybe_trigger_ai_turn()

    mocked_start.assert_not_called()


def test_maybe_trigger_ai_turn_skips_during_animation(controller, monkeypatch) -> None:
    """AI turn is not started while animation is in progress."""
    controller.game.current_player = "white"
    controller._player_types["white"] = "ai"
    controller.window.board_widget.is_animating = True
    mocked_start = MagicMock()
    monkeypatch.setattr(controller, "_start_ai_turn", mocked_start)

    controller._maybe_trigger_ai_turn()

    mocked_start.assert_not_called()


def test_animation_triggers_post_move_actions(controller) -> None:
    """Post-move actions (commentary, next AI) run after animation completes."""
    controller.new_game()

    # Execute a move
    controller._on_square_clicked(6, 4)
    controller._on_square_clicked(4, 4)

    # Pending animation state should be set
    assert controller._anim_pending_result is not None

    # Complete animation
    _complete_animation(controller)

    # Pending state should be cleared
    assert controller._anim_pending_result is None
