"""Tests for :class:`ui.controller.ChessController`."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ai.provider import ChatResponse, MoveSuggestion
from engine import ChessGame
from telemetry import TelemetryLogger
from ui.controller import ChessController
from ui.controls import ChessControls


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


class ImmediateThread:
    def __init__(self, target=None, name=None, daemon=None) -> None:
        self._target = target
        self._alive = False

    def start(self) -> None:
        self._alive = True
        if self._target:
            self._target()
        self._alive = False

    def is_alive(self) -> bool:
        return self._alive


@pytest.fixture()
def controller(monkeypatch, qapp) -> ChessController:
    session_events: list[tuple[str, dict]] = []
    monkeypatch.setattr("ui.controller.SessionLogger", lambda: DummySessionLogger(session_events))
    monkeypatch.setattr("ui.controller.threading.Thread", ImmediateThread)

    monkeypatch.setattr("ui.controller.QMessageBox.critical", lambda *a, **k: None)
    monkeypatch.setattr("ui.controller.QMessageBox.warning", lambda *a, **k: None)
    monkeypatch.setattr("ui.controller.QMessageBox.information", lambda *a, **k: None)

    def immediate_request(self, game, *, history=(), on_complete=None, on_error=None):
        _ = (self, game, history, on_error)
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

    controls = ChessControls()
    controls.set_provider_metadata(
        provider_items=[("OpenAI", "openai"), ("Anthropic", "anthropic"), ("Gemini", "gemini")],
        model_presets={
            "openai": ("gpt-4o-mini",),
            "anthropic": ("claude-3-5-haiku-latest",),
            "gemini": ("gemini-2.0-flash",),
        },
        availability={"openai": True, "anthropic": False, "gemini": False},
    )
    board = controls.create_board_view()

    ctl = ChessController(
        controls,
        board,
        game=ChessGame(),
        telemetry=TelemetryLogger(),
    )

    monkeypatch.setattr(ctl, "_provider_for_side", lambda _c: DummyProvider())
    monkeypatch.setattr(
        ctl, "_provider_for_commentator", lambda: DummyProvider(chat_text="SUMMARY: ...")
    )

    ctl._test_session_events = session_events  # type: ignore[attr-defined]
    return ctl


def test_new_game_resets_state(controller: ChessController) -> None:
    controller.controls.append_log_entry("Dummy")
    controller.new_game()

    assert controller.selected_square is None
    assert controller.controls.status_label.text()


def test_on_square_clicked_executes_move(controller: ChessController) -> None:
    controller.new_game()
    controller.on_square_clicked((6, 4))
    assert controller.selected_square == (6, 4)

    controller.on_square_clicked((4, 4))
    assert controller.selected_square is None
    assert controller.game.current_player == "black"
    assert controller._move_history
    assert controller.board_view._last_move == ((6, 4), (4, 4))  # pylint: disable=protected-access


def test_ai_turn_autoplays_move(
    controller: ChessController,
) -> None:
    controller.controls.set_player_type("white", "ai")

    controller.new_game()

    assert controller.game.current_player == "black"
    assert controller.game.board[(4, 4)] == ("white", "P")
    assert controller.board_view._last_move == ((6, 4), (4, 4))  # pylint: disable=protected-access


def test_chat_send_routes_to_side_chat(controller: ChessController) -> None:
    controller.controls.set_player_type("white", "ai")
    controller._player_types["white"] = "ai"  # pylint: disable=protected-access
    controller._on_chat_send("white", "hello")

    transcript = (
        controller.controls.white_chat._text.toPlainText()
    )  # pylint: disable=protected-access
    assert "[User]" in transcript
    assert "hello" in transcript


def test_commentary_request_writes_commentary_chat(controller: ChessController) -> None:
    controller.controls._commentator_toggle.setCurrentText("On")  # pylint: disable=protected-access
    controller._maybe_request_commentary(
        fen_before="before",
        fen_after="after",
        last_move="e2e4",
        move_number=1,
    )

    transcript = (
        controller.controls.commentary_chat._text.toPlainText()
    )  # pylint: disable=protected-access
    assert "[Commentator]" in transcript
    assert "SUMMARY: ..." in transcript


def test_capture_targets_and_animation(controller: ChessController, monkeypatch) -> None:
    animations: list[tuple[int, int]] = []
    monkeypatch.setattr(
        controller.board_view,
        "trigger_capture_animation",
        lambda pos: animations.append(pos),
    )

    controller.new_game()
    controller.on_square_clicked((6, 4))
    controller.on_square_clicked((4, 4))  # e2e4
    controller.on_square_clicked((1, 3))
    controller.on_square_clicked((3, 3))  # d7d5

    controller.on_square_clicked((4, 4))  # select e4 pawn
    assert (3, 3) in controller.board_view._capture_targets  # pylint: disable=protected-access

    controller.on_square_clicked((3, 3))  # e4xd5
    assert animations == [(3, 3)]
    assert controller.board_view._last_move == ((4, 4), (3, 3))  # pylint: disable=protected-access


def test_en_passant_capture_targets_and_animation(controller: ChessController, monkeypatch) -> None:
    animations: list[tuple[int, int]] = []
    monkeypatch.setattr(
        controller.board_view,
        "trigger_capture_animation",
        lambda pos: animations.append(pos),
    )

    controller.new_game()
    controller.on_square_clicked((6, 4))
    controller.on_square_clicked((4, 4))  # e2e4
    controller.on_square_clicked((1, 0))
    controller.on_square_clicked((2, 0))  # a7a6
    controller.on_square_clicked((4, 4))
    controller.on_square_clicked((3, 4))  # e4e5
    controller.on_square_clicked((1, 3))
    controller.on_square_clicked((3, 3))  # d7d5

    controller.on_square_clicked((3, 4))  # select e5 pawn
    assert (2, 3) in controller.board_view._capture_targets  # pylint: disable=protected-access

    controller.on_square_clicked((2, 3))  # e5xd6 en passant
    assert animations == [(2, 3)]


def test_build_provider_normalizes_model_alias(
    controller: ChessController,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeAnthropicClient:
        def __init__(self, *, config):
            captured["model"] = config.model

    monkeypatch.setattr("ui.controller.AnthropicClient", FakeAnthropicClient)
    controller._build_provider("anthropic", "opus 4.6")
    assert captured["model"] == "claude-opus-4-6"


def test_side_chat_rejects_when_worker_queue_is_full(controller: ChessController) -> None:
    class _QueueFullSemaphore:
        def acquire(self, blocking=False):  # noqa: ARG002 - signature parity
            return False

    controller.controls.set_player_type("white", "ai")
    controller._player_types["white"] = "ai"  # pylint: disable=protected-access
    controller._chat_worker_semaphore = _QueueFullSemaphore()  # type: ignore[attr-defined]

    controller._on_chat_send("white", "hello")
    transcript = controller.controls.white_chat._text.toPlainText()  # pylint: disable=protected-access
    assert "Too many concurrent background requests" in transcript


def test_castling_animation_plan_includes_rook(controller: ChessController) -> None:
    pieces = controller._build_animation_pieces(  # pylint: disable=protected-access
        board_before_move={(7, 4): ("white", "K"), (7, 7): ("white", "R")},
        start=(7, 4),
        end=(7, 6),
        moving_piece=("white", "K"),
    )
    assert pieces == [
        (("white", "K"), (7, 4), (7, 6)),
        (("white", "R"), (7, 7), (7, 5)),
    ]


def test_ai_turn_waits_for_animation_completion(
    controller: ChessController,
    monkeypatch,
) -> None:
    triggered: list[str] = []
    monkeypatch.setattr(controller, "_start_ai_turn", lambda colour: triggered.append(colour))

    controller._animation_in_progress = True  # pylint: disable=protected-access
    controller._player_types["white"] = "ai"  # pylint: disable=protected-access
    controller.game.current_player = "white"
    controller._maybe_trigger_ai_turn()  # pylint: disable=protected-access

    assert triggered == []
