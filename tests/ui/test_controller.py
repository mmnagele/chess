"""Tests für :class:`ui.controller.ChessController`."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Tuple

import pytest

from engine import ChessGame
from telemetry import TelemetryLogger
from ui.controller import ChessController

Position = Tuple[int, int]


class DummyBoardView:
    """Vereinfachte Brettansicht für Controller-Tests."""

    def __init__(self) -> None:
        self.click_handler: Callable[[Position], None] | None = None
        self.render_calls: List[Dict[str, object]] = []
        self.interaction_enabled: bool = True
        self.highlights: Dict[str, List[Position]] = {"moves": []}

    def set_click_handler(self, handler: Callable[[Position], None]) -> None:
        self.click_handler = handler

    def render_board(self, board, symbol_provider) -> None:
        self.render_calls.append({"board": board, "provider": symbol_provider})

    def reset_colours(self) -> None:
        return None

    def highlight_square(self, position: Position, colour: str) -> None:
        self.highlights.setdefault("squares", []).append(position)

    def highlight_moves(self, moves) -> None:
        self.highlights["moves"] = list(moves)

    def highlight_selection(self, position: Optional[Position]) -> None:
        self.highlights["selection"] = [position] if position else []

    def set_interaction_enabled(self, enabled: bool) -> None:
        self.interaction_enabled = enabled


class DummyControls:
    """Nachbild der Steuerkomponenten mit Protokollierung."""

    def __init__(self) -> None:
        self.new_game_callback: Callable[[], None] | None = None
        self.player_mode_callback: Callable[[str, str], None] | None = None
        self.player_types: Dict[str, str] = {"white": "human", "black": "human"}
        self.log_entries: List[str] = []
        self.status: str | None = None
        self.commentary: str | None = None
        self.current_player: str | None = None

    def create_board_view(self) -> DummyBoardView:
        return DummyBoardView()

    def set_new_game_callback(self, callback: Callable[[], None]) -> None:
        self.new_game_callback = callback

    def set_player_mode_callback(self, callback: Callable[[str, str], None]) -> None:
        self.player_mode_callback = callback

    def get_player_type(self, colour: str) -> str:
        return self.player_types[colour]

    def set_player_type(self, colour: str, player_type: str) -> None:
        self.player_types[colour] = player_type

    def set_status(self, status: str) -> None:
        self.status = status

    def set_current_player(self, colour: str) -> None:
        self.current_player = colour

    def clear_log(self) -> None:
        self.log_entries.clear()

    def append_log_entry(self, entry: str) -> None:
        self.log_entries.append(entry)

    def set_commentary(self, text: str) -> None:
        self.commentary = text

    def set_controls_enabled(self, enabled: bool) -> None:
        self.controls_enabled = enabled

    def after(self, _delay: int, callback: Callable[[], None]) -> None:
        callback()


@pytest.fixture()
def controller(tmp_path, monkeypatch) -> ChessController:
    """Erzeugt einen Controller mit Dummy-Komponenten."""

    controls = DummyControls()
    board = controls.create_board_view()
    log_path = tmp_path / "commentary_log.jsonl"
    real_path = Path

    def fake_path(*args, **kwargs):
        if args and args[0] == "telemetry/commentary_log.jsonl":
            return log_path
        return real_path(*args, **kwargs)

    monkeypatch.setattr("ui.controller.Path", fake_path)
    monkeypatch.setattr(
        "ui.controller.messagebox",
        SimpleNamespace(showerror=lambda *a, **k: None, showinfo=lambda *a, **k: None),
    )
    controller = ChessController(
        controls,
        board,
        game=ChessGame(),
        telemetry=TelemetryLogger(),
        ai_provider_factory=lambda: SimpleNamespace(generate_move=lambda req: ((6, 4), (4, 4))),
        commentator_factory=lambda: SimpleNamespace(
            provide_commentary=lambda game, history=(): SimpleNamespace(
                as_dict=lambda: {},
                blunders_last_moves=(),
                key_ideas=(),
                variant_hint=None,
                eval_trend=None,
            ),
            render=lambda commentary: "",  # type: ignore[arg-type]
        ),
    )
    controller._commentary_log_path = log_path
    return controller


def test_new_game_resets_state(controller: ChessController) -> None:
    """Ein Neustart leert das Log und setzt die Interaktion zurück."""

    controller.controls.append_log_entry("Dummy")
    controller.new_game()
    assert controller.controls.log_entries == []
    assert controller.selected_square is None
    assert controller.board_view.interaction_enabled is True
    assert controller.controls.status is not None


def test_on_square_clicked_executes_move(controller: ChessController) -> None:
    """Das Anklicken eines gültigen Ziel-Felds führt den Zug aus."""

    controller.new_game()
    controller.on_square_clicked((6, 4))  # Bauer e2 auswählen
    assert controller.selected_square == (6, 4)
    controller.on_square_clicked((4, 4))  # Zug ausführen
    assert controller.selected_square is None
    assert controller.controls.log_entries
    assert controller.game.current_player == "black"
    assert controller._move_history  # pylint: disable=protected-access
