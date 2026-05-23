"""Tests for :class:`ui_qt.widgets.board_widget.BoardWidget` logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _make_board_widget():
    """Create a bare BoardWidget without a real QWidget init."""
    with patch("ui_qt.widgets.board_widget.QWidget.__init__", return_value=None):
        from ui_qt.widgets.board_widget import BoardWidget

        bw = BoardWidget.__new__(BoardWidget)
        bw._board = {}
        bw._symbol_provider = None
        bw._interaction_enabled = True
        bw._hover_square = None
        bw._selected_square = None
        bw._legal_moves = []
        bw._capture_squares = []
        bw._last_move = None
        bw._check_square = None
        bw._suggested_from = None
        bw._suggested_to = None
        bw._light_marble = None
        bw._dark_marble = None
        bw._marble_size = 0
        bw._piece_renderers = {}
        bw._check_pulse = 0.0
        bw._capture_anim = None
        bw._capture_anim_pos = None
        bw._capture_anim_progress = 0.0
        # Move animation state
        bw._move_anim = None
        bw._move_anim_progress = 0.0
        bw._move_anim_pieces = []
        bw._animating_move = False
        bw.width = lambda: 600
        bw.height = lambda: 600
        bw.update = MagicMock()
        return bw


def test_board_geometry_calculation() -> None:
    """Board geometry returns sensible margin, square size, and pixel size."""
    bw = _make_board_widget()

    # Mock QFontMetricsF to avoid needing a real QApplication
    mock_fm = MagicMock()
    mock_fm.height.return_value = 14.0
    mock_fm.horizontalAdvance.return_value = 12.0

    with patch("ui_qt.widgets.board_widget.QFontMetricsF", return_value=mock_fm):
        margin, sq, board_px = bw._board_geometry()
        # With mocked font metrics height=14, label_space = 14+10 = 24, margin = max(24, 26) = 26
        assert margin == 26
        assert sq == (600 - 52) // 8  # (600 - 2*26) // 8 = 68
        assert board_px == sq * 8


def test_pos_from_pixel() -> None:
    """Mouse position correctly maps to board square."""
    bw = _make_board_widget()

    mock_fm = MagicMock()
    mock_fm.height.return_value = 14.0
    mock_fm.horizontalAdvance.return_value = 12.0

    with patch("ui_qt.widgets.board_widget.QFontMetricsF", return_value=mock_fm):
        margin, sq, _ = bw._board_geometry()

        # Inside square (0, 0)
        pos = bw._pos_from_pixel(margin + 5, margin + 5)
        assert pos == (0, 0)

        # Inside square (7, 7)
        pos = bw._pos_from_pixel(margin + 7 * sq + 5, margin + 7 * sq + 5)
        assert pos == (7, 7)

        # Outside board
        pos = bw._pos_from_pixel(margin + 8 * sq + 20, margin + 8 * sq + 20)
        assert pos is None


def test_highlight_selection_and_reset() -> None:
    """Highlight methods set and reset internal state."""
    bw = _make_board_widget()

    bw.highlight_selection((3, 3))
    assert bw._selected_square == (3, 3)

    bw.highlight_moves([(4, 4), (5, 5)], [(5, 5)])
    assert bw._legal_moves == [(4, 4), (5, 5)]
    assert bw._capture_squares == [(5, 5)]

    bw.highlight_check((0, 4))
    assert bw._check_square == (0, 4)

    bw.highlight_suggested_move((6, 4), (4, 4))
    assert bw._suggested_from == (6, 4)
    assert bw._suggested_to == (4, 4)

    bw.reset_highlights()
    assert bw._selected_square is None
    assert bw._legal_moves == []
    assert bw._check_square is None
    assert bw._suggested_from is None


def test_interaction_toggle() -> None:
    """Interaction flag controls click handling."""
    bw = _make_board_widget()

    bw.set_interaction_enabled(False)
    assert bw._interaction_enabled is False
    bw.set_interaction_enabled(True)
    assert bw._interaction_enabled is True


def test_clamped_coord_font_px() -> None:
    """Coordinate font size is clamped between min and max."""
    bw = _make_board_widget()

    # Very small square -> min font
    assert bw._clamped_coord_font_px(20) == 9  # 20 * 0.22 = 4.4 -> clamped to 9

    # Normal square -> proportional
    assert bw._clamped_coord_font_px(70) == 15  # 70 * 0.22 = 15.4 -> 15

    # Very large square -> max font
    assert bw._clamped_coord_font_px(200) == 28  # 200 * 0.22 = 44 -> clamped to 28


def test_is_animating_property() -> None:
    """is_animating reflects the move animation state."""
    bw = _make_board_widget()

    assert bw.is_animating is False

    bw._animating_move = True
    assert bw.is_animating is True

    bw._animating_move = False
    assert bw.is_animating is False


def test_on_move_anim_finished_clears_state() -> None:
    """_on_move_anim_finished resets all animation state."""
    from ui_qt.widgets.board_widget import _MovingPiece

    bw = _make_board_widget()
    bw.move_animation_finished = MagicMock()

    bw._animating_move = True
    bw._move_anim_progress = 0.75
    bw._move_anim_pieces = [_MovingPiece(piece=("white", "P"), start=(6, 4), end=(4, 4))]

    bw._on_move_anim_finished()

    assert bw._animating_move is False
    assert bw._move_anim_progress == 0.0
    assert bw._move_anim_pieces == []
    assert bw._move_anim is None
    bw.move_animation_finished.emit.assert_called_once()
