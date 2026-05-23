"""Tests for :class:`ui.board_view.BoardView`."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFontMetricsF
from PySide6.QtTest import QTest

from ui.board_view import BoardView


def test_render_board_updates_internal_state(qapp) -> None:
    board = BoardView()
    board.resize(640, 640)
    board.show()
    qapp.processEvents()

    board.render_board({(7, 4): ("white", "K")}, lambda _p, _c: "K")

    assert board._board[(7, 4)] == ("white", "K")  # pylint: disable=protected-access


def test_click_handler_invoked(qapp) -> None:
    triggered: list[tuple[int, int]] = []
    board = BoardView(on_square_click=lambda pos: triggered.append(pos))
    board.resize(640, 640)
    board.show()
    qapp.processEvents()

    board.render_board({}, lambda _p, _c: "")
    qapp.processEvents()

    rect = board._square_rects[(0, 0)]  # pylint: disable=protected-access
    point = rect.center().toPoint()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=QPoint(point.x(), point.y()))

    assert triggered == [(0, 0)]


def test_highlighting_functions(qapp) -> None:
    board = BoardView()
    board.resize(640, 640)
    board.show()
    qapp.processEvents()

    board.highlight_square((0, 0), "#ffffff")
    board.highlight_moves([(0, 1), (1, 2)], capture_targets=[(1, 2)])
    board.highlight_selection((0, 2))
    board.highlight_suggested_move((6, 4), (4, 4))
    board.set_last_move((6, 4), (4, 4))

    assert (0, 0) in board._custom_highlights  # pylint: disable=protected-access
    assert (0, 1) in board._valid_moves  # pylint: disable=protected-access
    assert (1, 2) in board._capture_targets  # pylint: disable=protected-access
    assert board._selection == (0, 2)  # pylint: disable=protected-access
    assert board._suggested == ((6, 4), (4, 4))  # pylint: disable=protected-access
    assert board._last_move == ((6, 4), (4, 4))  # pylint: disable=protected-access

    board.reset_colours()
    assert not board._custom_highlights  # pylint: disable=protected-access
    assert not board._valid_moves  # pylint: disable=protected-access
    assert board._last_move == ((6, 4), (4, 4))  # pylint: disable=protected-access


def test_interaction_toggle(qapp) -> None:
    called: list[tuple[int, int]] = []
    board = BoardView(on_square_click=lambda pos: called.append(pos))
    board.resize(640, 640)
    board.show()
    qapp.processEvents()

    board.render_board({}, lambda _p, _c: "")
    rect = board._square_rects[(0, 0)]  # pylint: disable=protected-access
    point = rect.center().toPoint()

    board.set_interaction_enabled(False)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=QPoint(point.x(), point.y()))
    assert called == []

    board.set_interaction_enabled(True)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=QPoint(point.x(), point.y()))
    assert called == [(0, 0)]


def test_capture_animation_lifecycle(qapp) -> None:
    board = BoardView()
    board.resize(640, 640)
    board.show()
    qapp.processEvents()
    board.render_board({}, lambda _p, _c: "")
    qapp.processEvents()

    board.trigger_capture_animation((4, 4))
    assert board._capture_fx  # pylint: disable=protected-access

    QTest.qWait(420)
    qapp.processEvents()
    assert not board._capture_fx  # pylint: disable=protected-access


def test_move_animation_lifecycle(qapp) -> None:
    board = BoardView()
    board.resize(640, 640)
    board.show()
    qapp.processEvents()
    board.render_board({(4, 4): ("white", "P")}, lambda _p, _c: "")
    qapp.processEvents()

    finished: list[str] = []
    board.move_animation_finished.connect(lambda: finished.append("done"))
    started = board.animate_move(
        {(4, 4): ("white", "P")},
        [(("white", "P"), (6, 4), (4, 4))],
        duration_ms=70,
    )

    assert started is True
    assert board.is_animating() is True
    assert (4, 4) in board._move_hidden_targets  # pylint: disable=protected-access

    QTest.qWait(140)
    qapp.processEvents()
    assert board.is_animating() is False
    assert not board._move_fx  # pylint: disable=protected-access
    assert not board._move_hidden_targets  # pylint: disable=protected-access
    assert finished == ["done"]


def test_move_animation_returns_false_without_pieces(qapp) -> None:
    board = BoardView()
    board.resize(640, 640)
    board.show()
    qapp.processEvents()

    started = board.animate_move({}, [], duration_ms=50)
    assert started is False
    assert board.is_animating() is False


@pytest.mark.parametrize("size", [(520, 520), (1200, 900), (3840, 2160)])
def test_coordinate_layout_uses_safe_margins(qapp, size) -> None:
    board = BoardView()
    board.resize(*size)
    board.show()
    qapp.processEvents()

    layout = board._calculate_layout()  # pylint: disable=protected-access
    metrics = QFontMetricsF(layout.coord_font)

    assert layout.top_margin >= metrics.height()
    assert layout.bottom_margin >= metrics.height()
    assert layout.left_margin >= metrics.horizontalAdvance("8")
    assert layout.right_margin >= metrics.horizontalAdvance("8")
    assert layout.board_rect.top() - layout.top_margin >= -1.0
    assert layout.board_rect.bottom() + layout.bottom_margin <= board.height() + 1.0
