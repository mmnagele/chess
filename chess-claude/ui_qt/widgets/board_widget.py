"""Custom-painted chessboard with marble squares, SVG pieces, and neon highlights."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPainter,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from ui_qt.theme.palette import (
    BOARD_BORDER,
    BOARD_DARK,
    BOARD_LIGHT,
    HIGHLIGHT_CAPTURE,
    HIGHLIGHT_CHECK,
    HIGHLIGHT_LAST_MOVE,
    HIGHLIGHT_LEGAL_MOVE,
    HIGHLIGHT_SELECTED,
    HIGHLIGHT_SUGGESTED_FROM,
    HIGHLIGHT_SUGGESTED_TO,
    NEON_CYAN,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

Position = tuple[int, int]
Piece = tuple[str, str]

_FILES = "abcdefgh"


@dataclass
class _MovingPiece:
    """Tracks a piece being animated from one square to another."""

    piece: Piece
    start: Position
    end: Position


_ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "pieces"


class BoardWidget(QWidget):
    """Custom-painted chessboard widget with marble texture and neon highlights."""

    square_clicked = Signal(int, int)
    move_animation_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        self.setMouseTracking(True)

        self._board: dict[Position, Piece | None] = {}
        self._symbol_provider: Callable[[str, str], str] | None = None
        self._interaction_enabled = True
        self._hover_square: Position | None = None

        # Highlight state
        self._selected_square: Position | None = None
        self._legal_moves: list[Position] = []
        self._capture_squares: list[Position] = []
        self._last_move: tuple[Position, Position] | None = None
        self._check_square: Position | None = None
        self._suggested_from: Position | None = None
        self._suggested_to: Position | None = None

        # Cache marble textures
        self._light_marble: QPixmap | None = None
        self._dark_marble: QPixmap | None = None
        self._marble_size = 0

        # SVG piece renderers
        self._piece_renderers: dict[str, QSvgRenderer] = {}
        self._load_piece_svgs()

        # Animation counter for check pulse
        self._check_pulse = 0.0

        # Capture animation state
        self._capture_anim: QVariantAnimation | None = None
        self._capture_anim_pos: Position | None = None
        self._capture_anim_progress: float = 0.0

        # Move animation state
        self._move_anim: QVariantAnimation | None = None
        self._move_anim_progress: float = 0.0
        self._move_anim_pieces: list[_MovingPiece] = []
        self._animating_move = False

    def _load_piece_svgs(self) -> None:
        """Load SVG piece files from assets directory."""
        piece_map = {
            ("white", "K"): "wK",
            ("white", "Q"): "wQ",
            ("white", "R"): "wR",
            ("white", "B"): "wB",
            ("white", "N"): "wN",
            ("white", "P"): "wP",
            ("black", "K"): "bK",
            ("black", "Q"): "bQ",
            ("black", "R"): "bR",
            ("black", "B"): "bB",
            ("black", "N"): "bN",
            ("black", "P"): "bP",
        }
        for key, filename in piece_map.items():
            svg_path = _ASSETS_DIR / f"{filename}.svg"
            if svg_path.exists():
                renderer = QSvgRenderer(str(svg_path))
                if renderer.isValid():
                    self._piece_renderers[key] = renderer

    def _generate_marble_texture(self, base_color: str, size: int) -> QPixmap:
        """Generate a procedural marble texture."""
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        base = QColor(base_color)
        rng = random.Random(hash(base_color))

        for y in range(size):
            for x in range(size):
                # Marble veining effect using sine waves
                noise = (
                    math.sin(x * 0.05 + y * 0.03) * 15
                    + math.sin(x * 0.02 - y * 0.04) * 10
                    + math.sin((x + y) * 0.08) * 8
                    + rng.gauss(0, 3)
                )
                r = max(0, min(255, base.red() + int(noise)))
                g = max(0, min(255, base.green() + int(noise)))
                b = max(0, min(255, base.blue() + int(noise)))
                img.setPixelColor(x, y, QColor(r, g, b))

        return QPixmap.fromImage(img)

    def _ensure_marble_textures(self, square_size: int) -> None:
        """Regenerate marble textures if size changed."""
        if self._marble_size != square_size:
            self._marble_size = square_size
            self._light_marble = self._generate_marble_texture(BOARD_LIGHT, square_size)
            self._dark_marble = self._generate_marble_texture(BOARD_DARK, square_size)

    # Coordinate font size limits (pixels)
    _COORD_FONT_MIN = 9
    _COORD_FONT_MAX = 28
    _COORD_FONT_RATIO = 0.22  # fraction of square size

    def _board_geometry(self) -> tuple[int, int, int]:
        """Return (margin, square_size, board_pixel_size).

        Margin is computed dynamically so coordinate labels never clip,
        even at 4K fullscreen.
        """
        w, h = self.width(), self.height()
        # First pass: estimate square size to derive font metrics
        rough_sq = max((min(w, h) - 60) // 8, 20)
        font_px = self._clamped_coord_font_px(rough_sq)
        font = QFont("Segoe UI", font_px, QFont.Weight.Bold)
        fm = QFontMetricsF(font)
        # Reserve enough room for ascent + descent + padding
        label_space = fm.height() + 10
        margin = max(int(label_space), 26)
        available = min(w, h) - 2 * margin
        square_size = max(available // 8, 20)
        board_px = square_size * 8
        return margin, square_size, board_px

    def _clamped_coord_font_px(self, square_size: int) -> int:
        """Compute a clamped font size for coordinate labels."""
        return max(
            self._COORD_FONT_MIN,
            min(self._COORD_FONT_MAX, int(square_size * self._COORD_FONT_RATIO)),
        )

    def _square_rect(self, row: int, col: int) -> QRectF:
        margin, sq, _ = self._board_geometry()
        x = margin + col * sq
        y = margin + row * sq
        return QRectF(x, y, sq, sq)

    def _pos_from_pixel(self, px: float, py: float) -> Position | None:
        margin, sq, board_px = self._board_geometry()
        col = int((px - margin) / sq) if sq > 0 else -1
        row = int((py - margin) / sq) if sq > 0 else -1
        if 0 <= row < 8 and 0 <= col < 8:
            return (row, col)
        return None

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin, sq, board_px = self._board_geometry()
        self._ensure_marble_textures(sq)

        # Board background / border frame
        board_rect = QRectF(margin - 3, margin - 3, board_px + 6, board_px + 6)
        painter.setPen(QPen(QColor(BOARD_BORDER), 3))
        painter.setBrush(QColor(BOARD_BORDER))
        painter.drawRoundedRect(board_rect, 4, 4)

        # Draw squares
        for row in range(8):
            for col in range(8):
                rect = self._square_rect(row, col)
                is_light = (row + col) % 2 == 0
                marble = self._light_marble if is_light else self._dark_marble
                if marble:
                    painter.drawPixmap(rect.toRect(), marble)
                else:
                    painter.fillRect(rect, QColor(BOARD_LIGHT if is_light else BOARD_DARK))

        # Overlays
        self._draw_highlights(painter)
        self._draw_pieces(painter, sq)
        self._draw_coordinates(painter, margin, sq, board_px)

        # Vignette
        self._draw_vignette(painter, margin, board_px)

        painter.end()

    def _draw_highlights(self, painter: QPainter) -> None:
        """Draw neon overlays for selection, legal moves, last move, check."""

        # Last move highlight (strong red tint + glow border)
        if self._last_move:
            for pos in self._last_move:
                rect = self._square_rect(*pos)
                painter.fillRect(rect, QColor(HIGHLIGHT_LAST_MOVE + "55"))
                painter.setPen(QPen(QColor(HIGHLIGHT_LAST_MOVE + "A0"), 2.5))
                painter.drawRect(rect)

        # Check highlight (pulsing pink)
        if self._check_square:
            rect = self._square_rect(*self._check_square)
            painter.fillRect(rect, QColor(HIGHLIGHT_CHECK + "40"))
            painter.setPen(QPen(QColor(HIGHLIGHT_CHECK), 3))
            painter.drawRect(rect)

        # Suggested move highlight
        if self._suggested_from:
            rect = self._square_rect(*self._suggested_from)
            painter.fillRect(rect, QColor(HIGHLIGHT_SUGGESTED_FROM + "35"))
            painter.setPen(QPen(QColor(HIGHLIGHT_SUGGESTED_FROM), 2))
            painter.drawRect(rect)
        if self._suggested_to:
            rect = self._square_rect(*self._suggested_to)
            painter.fillRect(rect, QColor(HIGHLIGHT_SUGGESTED_TO + "35"))
            painter.setPen(QPen(QColor(HIGHLIGHT_SUGGESTED_TO), 2))
            painter.drawRect(rect)

        # Selected square (neon cyan outline + glow)
        if self._selected_square:
            rect = self._square_rect(*self._selected_square)
            painter.fillRect(rect, QColor(HIGHLIGHT_SELECTED + "30"))
            painter.setPen(QPen(QColor(HIGHLIGHT_SELECTED), 3))
            painter.drawRect(rect)

        # Legal moves
        _, sq, _ = self._board_geometry()
        for pos in self._legal_moves:
            rect = self._square_rect(*pos)
            center_x = rect.center().x()
            center_y = rect.center().y()

            if pos in self._capture_squares:
                # Capture: neon magenta ring
                painter.setPen(QPen(QColor(HIGHLIGHT_CAPTURE), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                radius = sq * 0.35
                painter.drawEllipse(
                    QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
                )
            else:
                # Non-capture: small neon cyan dot
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(HIGHLIGHT_LEGAL_MOVE + "80"))
                radius = sq * 0.15
                painter.drawEllipse(
                    QRectF(center_x - radius, center_y - radius, radius * 2, radius * 2)
                )

        # Capture animation overlay (inflate then implode blue ring)
        if self._capture_anim_pos is not None and self._capture_anim_progress > 0:
            rect = self._square_rect(*self._capture_anim_pos)
            cx = rect.center().x()
            cy = rect.center().y()
            p = self._capture_anim_progress
            # Two-phase: 0..0.5 inflate (OutCubic feel), 0.5..1.0 implode
            if p <= 0.5:
                t = p / 0.5
                scale = t
            else:
                t = (p - 0.5) / 0.5
                scale = 1.0 - t
            radius = sq * 0.42 * scale
            alpha = int(255 * min(1.0, scale * 1.5))
            ring_color = QColor(HIGHLIGHT_CAPTURE)
            ring_color.setAlpha(alpha)
            painter.setPen(QPen(ring_color, max(2, sq * 0.06)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(cx - radius, cy - radius, radius * 2, radius * 2))

        # Hover highlight
        if self._hover_square and self._interaction_enabled:
            rect = self._square_rect(*self._hover_square)
            painter.fillRect(rect, QColor(NEON_CYAN + "15"))

    def _draw_pieces(self, painter: QPainter, sq: int) -> None:
        """Draw chess pieces using SVG renderers or Unicode fallback.

        Pieces that are currently being animated are skipped from their static
        position and drawn at their interpolated position instead.
        """
        # Collect positions that should not render statically during animation
        anim_skip: set[Position] = set()
        if self._animating_move:
            for mp in self._move_anim_pieces:
                # Skip the destination square (engine already moved the piece there)
                anim_skip.add(mp.end)

        for (row, col), piece in self._board.items():
            if piece is None:
                continue
            if (row, col) in anim_skip:
                continue

            self._draw_piece_at_rect(painter, piece, self._square_rect(row, col), sq)

        # Draw animated pieces at their interpolated position
        if self._animating_move and self._move_anim_pieces:
            t = self._move_anim_progress
            margin, sq_size, _ = self._board_geometry()
            for mp in self._move_anim_pieces:
                sr = self._square_rect(*mp.start)
                er = self._square_rect(*mp.end)
                # Interpolate position
                x = sr.x() + (er.x() - sr.x()) * t
                y = sr.y() + (er.y() - sr.y()) * t
                interp_rect = QRectF(x, y, sr.width(), sr.height())
                self._draw_piece_at_rect(painter, mp.piece, interp_rect, sq)

    def _draw_piece_at_rect(self, painter: QPainter, piece: Piece, rect: QRectF, sq: int) -> None:
        """Draw a single piece at the given rect."""
        color, p_type = piece
        inset = sq * 0.08
        piece_rect = QRectF(
            rect.x() + inset,
            rect.y() + inset,
            rect.width() - 2 * inset,
            rect.height() - 2 * inset,
        )

        renderer = self._piece_renderers.get((color, p_type))
        if renderer:
            renderer.render(painter, piece_rect)
        elif self._symbol_provider:
            symbol = self._symbol_provider(p_type, color)
            font = QFont("Segoe UI Symbol", int(sq * 0.55))
            painter.setFont(font)
            painter.setPen(QColor(TEXT_PRIMARY))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, symbol)

    def _draw_coordinates(self, painter: QPainter, margin: int, sq: int, board_px: int) -> None:
        """Draw file letters and rank numbers around the board.

        Font size is clamped so labels stay readable at tiny sizes and
        never clip at 4K.  Rectangles are derived from QFontMetrics so
        ascenders / descenders are always contained.
        """
        font_px = self._clamped_coord_font_px(sq)
        font = QFont("Segoe UI", font_px, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetricsF(font)
        label_h = fm.height() + 4  # padding
        label_w = max(fm.horizontalAdvance("W") + 6, 20)

        for col in range(8):
            file_char = _FILES[col]
            cx = margin + col * sq + sq / 2.0
            is_hovered = self._hover_square and self._hover_square[1] == col
            color = QColor(NEON_CYAN) if is_hovered else QColor(TEXT_MUTED)
            painter.setPen(color)

            # Top
            painter.drawText(
                QRectF(cx - label_w / 2, max(2, margin - label_h), label_w, label_h),
                Qt.AlignmentFlag.AlignCenter,
                file_char,
            )
            # Bottom
            painter.drawText(
                QRectF(cx - label_w / 2, margin + board_px + 2, label_w, label_h),
                Qt.AlignmentFlag.AlignCenter,
                file_char,
            )

        for row in range(8):
            rank = str(8 - row)
            cy = margin + row * sq + sq / 2.0
            is_hovered = self._hover_square and self._hover_square[0] == row
            color = QColor(NEON_CYAN) if is_hovered else QColor(TEXT_MUTED)
            painter.setPen(color)

            # Left
            painter.drawText(
                QRectF(max(2, margin - label_w - 2), cy - label_h / 2, label_w, label_h),
                Qt.AlignmentFlag.AlignCenter,
                rank,
            )
            # Right
            painter.drawText(
                QRectF(margin + board_px + 2, cy - label_h / 2, label_w, label_h),
                Qt.AlignmentFlag.AlignCenter,
                rank,
            )

    def _draw_vignette(self, painter: QPainter, margin: int, board_px: int) -> None:
        """Subtle vignette overlay to focus the eye on the center."""
        center_x = margin + board_px / 2
        center_y = margin + board_px / 2
        radius = board_px * 0.75

        gradient = QRadialGradient(center_x, center_y, radius)
        gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
        gradient.setColorAt(0.7, QColor(0, 0, 0, 0))
        gradient.setColorAt(1.0, QColor(0, 0, 0, 40))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRect(QRectF(margin, margin, board_px, board_px))

    def mousePressEvent(self, event: object) -> None:
        if not self._interaction_enabled:
            return
        pos = self._pos_from_pixel(event.position().x(), event.position().y())
        if pos:
            self.square_clicked.emit(pos[0], pos[1])

    def mouseMoveEvent(self, event: object) -> None:
        pos = self._pos_from_pixel(event.position().x(), event.position().y())
        if pos != self._hover_square:
            self._hover_square = pos
            self.update()

    def leaveEvent(self, event: object) -> None:
        self._hover_square = None
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(600, 600)

    # -- Public API --

    def render_board(
        self,
        board: dict[Position, Piece | None],
        symbol_provider: Callable[[str, str], str] | None = None,
    ) -> None:
        self._board = dict(board)
        self._symbol_provider = symbol_provider
        self.update()

    def reset_highlights(self) -> None:
        self._selected_square = None
        self._legal_moves = []
        self._capture_squares = []
        self._last_move = None
        self._check_square = None
        self._suggested_from = None
        self._suggested_to = None
        self.update()

    def highlight_selection(self, position: Position | None) -> None:
        self._selected_square = position
        self.update()

    def highlight_moves(self, moves: Iterable[Position], captures: Iterable[Position] = ()) -> None:
        self._legal_moves = list(moves)
        self._capture_squares = list(captures)
        self.update()

    def highlight_last_move(self, start: Position, end: Position) -> None:
        self._last_move = (start, end)
        self.update()

    def highlight_check(self, position: Position | None) -> None:
        self._check_square = position
        self.update()

    def highlight_suggested_move(self, start: Position, end: Position) -> None:
        self._suggested_from = start
        self._suggested_to = end
        self.update()

    def clear_suggested_move(self) -> None:
        self._suggested_from = None
        self._suggested_to = None
        self.update()

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._interaction_enabled = enabled

    def play_capture_animation(self, position: Position) -> None:
        """Play an inflate-then-implode blue ring animation on *position*."""
        # Stop any running animation
        if self._capture_anim is not None:
            self._capture_anim.stop()

        self._capture_anim_pos = position
        self._capture_anim_progress = 0.0

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(350)  # 350 ms total
        anim.setEasingCurve(QEasingCurve.Type.Linear)

        def _on_value(value: object) -> None:
            self._capture_anim_progress = float(value)  # type: ignore[arg-type]
            self.update()

        def _on_finished() -> None:
            self._capture_anim_pos = None
            self._capture_anim_progress = 0.0
            self._capture_anim = None
            self.update()

        anim.valueChanged.connect(_on_value)
        anim.finished.connect(_on_finished)
        self._capture_anim = anim
        anim.start()

    def play_move_animation(
        self,
        moving_pieces: list[tuple[Piece, Position, Position]],
    ) -> None:
        """Animate one or more pieces moving simultaneously (250ms linear).

        Args:
            moving_pieces: List of (piece, start_pos, end_pos) tuples.
                For normal moves: one entry.
                For castling: two entries (king + rook).

        The engine state should already be applied before calling this.
        The animation visually interpolates from start to end, then emits
        ``move_animation_finished`` when done.
        """
        # Stop any running move animation
        if self._move_anim is not None:
            self._move_anim.stop()
            self._on_move_anim_finished()

        self._move_anim_pieces = [
            _MovingPiece(piece=p, start=s, end=e) for p, s, e in moving_pieces
        ]
        self._move_anim_progress = 0.0
        self._animating_move = True

        anim = QVariantAnimation(self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.Linear)

        def _on_value(value: object) -> None:
            self._move_anim_progress = float(value)  # type: ignore[arg-type]
            self.update()

        anim.valueChanged.connect(_on_value)
        anim.finished.connect(self._on_move_anim_finished)
        self._move_anim = anim
        anim.start()

    def _on_move_anim_finished(self) -> None:
        """Clean up move animation state and emit finished signal."""
        self._animating_move = False
        self._move_anim_pieces = []
        self._move_anim_progress = 0.0
        self._move_anim = None
        self.update()
        self.move_animation_finished.emit()

    @property
    def is_animating(self) -> bool:
        """True if a move animation is currently in progress."""
        return self._animating_move


__all__ = ["BoardWidget"]
