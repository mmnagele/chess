"""PySide6-based chessboard widget with marble styling and neon highlights."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QSizePolicy, QWidget

Position = tuple[int, int]
Piece = tuple[str, str]
_FILES = "abcdefgh"
_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "pieces"


@dataclass(slots=True)
class _CaptureFx:
    position: Position
    progress: float
    animation: QVariantAnimation


@dataclass(slots=True)
class _MovePieceFx:
    piece: Piece
    start: Position
    end: Position
    progress: float


@dataclass(slots=True)
class _BoardLayout:
    board_rect: QRectF
    square_size: float
    coord_font: QFont
    top_margin: float
    bottom_margin: float
    left_margin: float
    right_margin: float


class BoardView(QWidget):
    """Visualizes the chessboard and emits square click callbacks."""

    move_animation_finished = Signal()

    LIGHT_COLOR = "#e7ebf3"
    DARK_COLOR = "#667181"
    MOVE_COLOR = "#d9ff1f"  # intense neon yellow-green beam tone
    SELECTION_COLOR = "#22d3ee"
    CHECK_COLOR = "#fb7185"
    SUGGESTED_FROM_COLOR = "#22d3ee"
    SUGGESTED_TO_COLOR = "#a3e635"
    LAST_MOVE_COLOR = "#ff2a2a"
    CAPTURE_RING_COLOR = "#2d8cff"

    def __init__(
        self,
        parent: QWidget | None = None,
        on_square_click: Callable[[Position], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_square_click = on_square_click
        self._interaction_enabled = True

        self._board: dict[Position, Piece | None] = {}
        self._square_rects: dict[Position, QRectF] = {}

        self._custom_highlights: dict[Position, QColor] = {}
        self._valid_moves: set[Position] = set()
        self._capture_targets: set[Position] = set()
        self._selection: Position | None = None
        self._suggested: tuple[Position, Position] | None = None
        self._last_move: tuple[Position, Position] | None = None
        self._hover: Position | None = None
        self._capture_fx: list[_CaptureFx] = []
        self._move_fx: list[_MovePieceFx] = []
        self._move_hidden_targets: set[Position] = set()
        self._move_animation: QVariantAnimation | None = None

        self._light_texture = self._make_marble_texture(QColor(self.LIGHT_COLOR), 220)
        self._dark_texture = self._make_marble_texture(QColor(self.DARK_COLOR), 200)
        self._piece_renderers = self._create_piece_renderers()

        self.setMouseTracking(True)
        self.setMinimumSize(480, 480)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        return QSize(760, 760)

    def set_click_handler(self, callback: Callable[[Position], None] | None) -> None:
        self._on_square_click = callback

    def render_board(
        self,
        board: dict[Position, Piece | None],
        _symbol_provider: Callable[[str, str], str],
    ) -> None:
        self._board = dict(board)
        self.update()

    def reset_colours(self) -> None:
        self._custom_highlights.clear()
        self._valid_moves.clear()
        self._capture_targets.clear()
        self._selection = None
        self._suggested = None
        self.update()

    def highlight_square(self, position: Position, colour: str) -> None:
        self._custom_highlights[position] = QColor(colour)
        self.update()

    def highlight_moves(
        self, moves: list[Position], *, capture_targets: list[Position] | None = None
    ) -> None:
        self._valid_moves = set(moves)
        self._capture_targets = set(capture_targets or [])
        self.update()

    def highlight_selection(self, position: Position | None) -> None:
        self._selection = position
        self.update()

    def highlight_suggested_move(self, start: Position, end: Position) -> None:
        self._suggested = (start, end)
        self.update()

    def set_last_move(self, start: Position, end: Position) -> None:
        self._last_move = (start, end)
        self.update()

    def clear_last_move(self) -> None:
        self._last_move = None
        self.update()

    def trigger_capture_animation(self, position: Position) -> None:
        animation = QVariantAnimation(self)
        animation.setDuration(320)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)

        fx = _CaptureFx(position=position, progress=0.0, animation=animation)
        self._capture_fx.append(fx)

        animation.valueChanged.connect(lambda value, item=fx: self._on_capture_value(item, value))
        animation.finished.connect(lambda item=fx: self._on_capture_finished(item))
        animation.start()

    def animate_move(
        self,
        board_after: dict[Position, Piece | None],
        pieces: list[tuple[Piece, Position, Position]],
        *,
        duration_ms: int = 250,
    ) -> bool:
        if not pieces:
            self._board = dict(board_after)
            self.update()
            return False

        self.stop_move_animation()
        self._board = dict(board_after)

        self._move_fx = [
            _MovePieceFx(piece=piece, start=start, end=end, progress=0.0)
            for piece, start, end in pieces
        ]
        self._move_hidden_targets = {end for _, _start, end in pieces}

        animation = QVariantAnimation(self)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setDuration(max(1, duration_ms))
        animation.setEasingCurve(QEasingCurve.Type.Linear)
        animation.valueChanged.connect(self._on_move_animation_value)
        animation.finished.connect(self._on_move_animation_finished)

        self._move_animation = animation
        animation.start()
        self.update()
        return True

    def stop_move_animation(self) -> None:
        if self._move_animation is not None:
            animation = self._move_animation
            self._move_animation = None
            animation.stop()
        self._move_fx.clear()
        self._move_hidden_targets.clear()
        self.update()

    def is_animating(self) -> bool:
        return self._move_animation is not None

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._interaction_enabled = enabled

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if not self._interaction_enabled or event.button() != Qt.MouseButton.LeftButton:
            return
        if self._on_square_click is None:
            return

        position = self._position_from_point(event.position())
        if position is not None:
            self._on_square_click(position)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        new_hover = self._position_from_point(event.position())
        if new_hover != self._hover:
            self._hover = new_hover
            self.update()

    def leaveEvent(self, _event) -> None:  # type: ignore[override]
        if self._hover is not None:
            self._hover = None
            self.update()

    def paintEvent(self, _event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )

        background = QLinearGradient(0, 0, float(self.width()), float(self.height()))
        background.setColorAt(0.0, QColor("#070b12"))
        background.setColorAt(1.0, QColor("#0f172a"))
        painter.fillRect(self.rect(), background)

        layout = self._calculate_layout()
        board_rect = layout.board_rect
        square_size = layout.square_size

        frame_path = QPainterPath()
        frame_path.addRoundedRect(board_rect.adjusted(-12, -12, 12, 12), 18, 18)
        frame = QLinearGradient(board_rect.topLeft(), board_rect.bottomRight())
        frame.setColorAt(0.0, QColor("#0f1b2d"))
        frame.setColorAt(1.0, QColor("#121a2b"))
        painter.fillPath(frame_path, frame)
        painter.setPen(QPen(QColor("#1f2a3a"), 2))
        painter.drawPath(frame_path)

        self._square_rects.clear()
        for row in range(8):
            for col in range(8):
                rect = QRectF(
                    board_rect.left() + col * square_size,
                    board_rect.top() + row * square_size,
                    square_size,
                    square_size,
                )
                self._square_rects[(row, col)] = rect
                self._draw_square(painter, row, col, rect)

        self._draw_move_hints(painter)
        self._draw_capture_fx(painter)
        self._draw_pieces(painter)
        self._draw_coordinates(painter, layout)

        vignette = QRadialGradient(board_rect.center(), board_rect.width() * 0.75)
        vignette.setColorAt(0.75, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 95))
        painter.fillRect(board_rect, vignette)

    def _draw_square(self, painter: QPainter, row: int, col: int, rect: QRectF) -> None:
        texture = self._light_texture if (row + col) % 2 == 0 else self._dark_texture
        painter.drawPixmap(rect.toRect(), texture)

        overlay = QColor(255, 255, 255, 18) if (row + col) % 2 == 0 else QColor(0, 0, 0, 24)
        painter.fillRect(rect, overlay)

        if self._last_move and (row, col) in self._last_move:
            red = QColor(self.LAST_MOVE_COLOR)
            red.setAlpha(132)
            painter.fillRect(rect, red)
            painter.setPen(QPen(QColor("#ff5959"), 2.8))
            painter.drawRect(rect.adjusted(1.7, 1.7, -1.7, -1.7))
            inner = QColor("#ffadad")
            inner.setAlpha(185)
            painter.setPen(QPen(inner, 1.5))
            painter.drawRect(rect.adjusted(4.3, 4.3, -4.3, -4.3))

        custom = self._custom_highlights.get((row, col))
        if custom is not None:
            glow = QColor(custom)
            glow.setAlpha(88)
            painter.fillRect(rect, glow)
            painter.setPen(QPen(custom, 2.2))
            painter.drawRect(rect.adjusted(1, 1, -1, -1))

        if self._suggested and (row, col) == self._suggested[0]:
            color = QColor(self.SUGGESTED_FROM_COLOR)
            color.setAlpha(96)
            painter.fillRect(rect, color)
            painter.setPen(QPen(QColor(self.SUGGESTED_FROM_COLOR), 2.4))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

        if self._suggested and (row, col) == self._suggested[1]:
            color = QColor(self.SUGGESTED_TO_COLOR)
            color.setAlpha(96)
            painter.fillRect(rect, color)
            painter.setPen(QPen(QColor(self.SUGGESTED_TO_COLOR), 2.4))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

        if self._selection == (row, col):
            painter.setPen(QPen(QColor(self.SELECTION_COLOR), 3.0))
            painter.drawRect(rect.adjusted(2, 2, -2, -2))

    def _draw_move_hints(self, painter: QPainter) -> None:
        for move in self._valid_moves:
            rect = self._square_rects.get(move)
            if rect is None:
                continue
            center = rect.center()
            if move in self._capture_targets:
                ring_outer = QColor(self.CAPTURE_RING_COLOR)
                ring_outer.setAlpha(220)
                ring_inner = QColor("#9fccff")
                ring_inner.setAlpha(242)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                outer_radius = rect.width() * 0.22
                painter.setPen(QPen(ring_outer, 3.6))
                painter.drawEllipse(center, outer_radius, outer_radius)
                painter.setPen(QPen(ring_inner, 1.8))
                painter.drawEllipse(center, outer_radius * 0.8, outer_radius * 0.8)
            else:
                glow = QColor(self.MOVE_COLOR)
                glow.setAlpha(145)
                core = QColor("#f6ff66")
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(glow)
                painter.drawEllipse(center, rect.width() * 0.17, rect.width() * 0.17)
                painter.setBrush(core)
                painter.drawEllipse(center, rect.width() * 0.095, rect.width() * 0.095)

    def _draw_capture_fx(self, painter: QPainter) -> None:
        for fx in self._capture_fx:
            rect = self._square_rects.get(fx.position)
            if rect is None:
                continue
            center = rect.center()
            radius, alpha = self._capture_ring_from_progress(rect.width(), fx.progress)
            if alpha <= 0 or radius <= 0:
                continue
            ring_color = QColor(self.CAPTURE_RING_COLOR)
            ring_color.setAlpha(alpha)
            painter.setPen(QPen(ring_color, 3.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius, radius)

    @staticmethod
    def _capture_ring_from_progress(square: float, progress: float) -> tuple[float, int]:
        if progress < 0.4:
            phase = progress / 0.4
            eased = 1 - (1 - phase) ** 3
            radius = square * (0.08 + 0.3 * eased)
            return radius, 240

        phase = (progress - 0.4) / 0.6
        eased = phase**2
        radius = square * (0.38 * (1 - eased))
        alpha = max(0, int(240 * (1 - eased)))
        return radius, alpha

    def _draw_pieces(self, painter: QPainter) -> None:
        for position, piece in self._board.items():
            if piece is None:
                continue
            if position in self._move_hidden_targets:
                continue
            rect = self._square_rects.get(position)
            if rect is None:
                continue

            self._draw_piece_at_rect(painter, piece, rect)

        for fx in self._move_fx:
            start_rect = self._square_rects.get(fx.start)
            end_rect = self._square_rects.get(fx.end)
            if start_rect is None or end_rect is None:
                continue

            start_center = start_rect.center()
            end_center = end_rect.center()
            current_center = QPointF(
                start_center.x() + (end_center.x() - start_center.x()) * fx.progress,
                start_center.y() + (end_center.y() - start_center.y()) * fx.progress,
            )
            current_rect = QRectF(
                current_center.x() - (start_rect.width() / 2.0),
                current_center.y() - (start_rect.height() / 2.0),
                start_rect.width(),
                start_rect.height(),
            )
            self._draw_piece_at_rect(painter, fx.piece, current_rect)

    def _draw_piece_at_rect(self, painter: QPainter, piece: Piece, rect: QRectF) -> None:
        inset = rect.adjusted(
            rect.width() * 0.08,
            rect.height() * 0.08,
            -rect.width() * 0.08,
            -rect.height() * 0.08,
        )
        shadow = inset.translated(0, rect.height() * 0.04)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(shadow.center(), shadow.width() * 0.32, shadow.height() * 0.13)

        renderer = self._piece_renderers[piece]
        renderer.render(painter, inset)

    def _draw_coordinates(self, painter: QPainter, layout: _BoardLayout) -> None:
        board_rect = layout.board_rect
        square_size = layout.square_size
        muted = QColor("#93a4b8")
        active = QColor("#22d3ee")

        painter.setFont(layout.coord_font)
        hover_row = self._hover[0] if self._hover else None
        hover_col = self._hover[1] if self._hover else None

        for col, file_char in enumerate(_FILES):
            color = active if hover_col == col else muted
            painter.setPen(color)

            top_rect = QRectF(
                board_rect.left() + col * square_size,
                board_rect.top() - layout.top_margin,
                square_size,
                layout.top_margin,
            )
            bottom_rect = QRectF(
                board_rect.left() + col * square_size,
                board_rect.bottom(),
                square_size,
                layout.bottom_margin,
            )
            painter.drawText(
                top_rect.adjusted(0, 2, 0, -2), Qt.AlignmentFlag.AlignCenter, file_char
            )
            painter.drawText(
                bottom_rect.adjusted(0, 2, 0, -2), Qt.AlignmentFlag.AlignCenter, file_char
            )

        for row in range(8):
            rank = str(8 - row)
            color = active if hover_row == row else muted
            painter.setPen(color)

            left_rect = QRectF(
                board_rect.left() - layout.left_margin,
                board_rect.top() + row * square_size,
                layout.left_margin,
                square_size,
            )
            right_rect = QRectF(
                board_rect.right(),
                board_rect.top() + row * square_size,
                layout.right_margin,
                square_size,
            )
            painter.drawText(left_rect.adjusted(0, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, rank)
            painter.drawText(right_rect.adjusted(4, 0, 0, 0), Qt.AlignmentFlag.AlignCenter, rank)

    def _calculate_layout(self) -> _BoardLayout:
        outer_margin = 16.0
        safety_padding = 8.0

        available_w = max(220.0, self.width() - outer_margin * 2)
        available_h = max(220.0, self.height() - outer_margin * 2)
        side_guess = min(available_w, available_h)
        square_guess = side_guess / 8.0

        coord_font = QFont("JetBrains Mono")
        coord_font.setBold(True)
        coord_font.setPointSizeF(self._clamp(square_guess * 0.2, 11.0, 34.0))

        metrics = QFontMetricsF(coord_font)
        top_margin, bottom_margin, left_margin, right_margin = self._coordinate_margins(
            metrics=metrics,
            safety_padding=safety_padding,
        )

        board_w = max(140.0, self.width() - (outer_margin * 2 + left_margin + right_margin))
        board_h = max(140.0, self.height() - (outer_margin * 2 + top_margin + bottom_margin))
        board_side = min(board_w, board_h)
        square_size = board_side / 8.0

        coord_font.setPointSizeF(self._clamp(square_size * 0.2, 11.0, 36.0))
        metrics = QFontMetricsF(coord_font)
        top_margin, bottom_margin, left_margin, right_margin = self._coordinate_margins(
            metrics=metrics,
            safety_padding=safety_padding,
        )

        board_w = max(140.0, self.width() - (outer_margin * 2 + left_margin + right_margin))
        board_h = max(140.0, self.height() - (outer_margin * 2 + top_margin + bottom_margin))
        board_side = min(board_w, board_h)
        square_size = board_side / 8.0

        total_w = board_side + left_margin + right_margin
        total_h = board_side + top_margin + bottom_margin

        start_x = max(outer_margin, (self.width() - total_w) / 2.0)
        start_y = max(outer_margin, (self.height() - total_h) / 2.0)
        origin_x = start_x + left_margin
        origin_y = start_y + top_margin

        return _BoardLayout(
            board_rect=QRectF(origin_x, origin_y, board_side, board_side),
            square_size=square_size,
            coord_font=coord_font,
            top_margin=top_margin,
            bottom_margin=bottom_margin,
            left_margin=left_margin,
            right_margin=right_margin,
        )

    @staticmethod
    def _coordinate_margins(
        *,
        metrics: QFontMetricsF,
        safety_padding: float,
    ) -> tuple[float, float, float, float]:
        sample = metrics.tightBoundingRect("h8")
        glyph_height = max(metrics.height(), sample.height())
        glyph_width = max(metrics.horizontalAdvance("8"), sample.width() * 0.55)

        top_margin = glyph_height + safety_padding + 2.0
        bottom_margin = glyph_height + safety_padding + 2.0
        side_margin = glyph_width + safety_padding + 6.0
        return top_margin, bottom_margin, side_margin, side_margin

    def _position_from_point(self, point: QPointF) -> Position | None:
        for position, rect in self._square_rects.items():
            if rect.contains(point):
                return position
        return None

    @staticmethod
    def _clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _on_capture_value(self, fx: _CaptureFx, value: float) -> None:
        fx.progress = float(value)
        self.update()

    def _on_capture_finished(self, fx: _CaptureFx) -> None:
        try:
            self._capture_fx.remove(fx)
        except ValueError:
            pass
        self.update()

    def _on_move_animation_value(self, value: float) -> None:
        progress = float(value)
        for fx in self._move_fx:
            fx.progress = progress
        self.update()

    def _on_move_animation_finished(self) -> None:
        self._move_animation = None
        self._move_fx.clear()
        self._move_hidden_targets.clear()
        self.update()
        self.move_animation_finished.emit()

    def _make_marble_texture(self, base: QColor, variance: int) -> QPixmap:
        size = 140
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(base)

        seed = 1337 + (0 if base.lightness() > 130 else 91)
        rnd = random.Random(seed)

        for y in range(size):
            for x in range(size):
                noise = rnd.randint(-variance // 12, variance // 12)
                vein = int(16 * (1 + math.sin((x * 0.11) + (y * 0.07))))
                color = QColor(base)
                color = color.lighter(max(65, min(145, 100 + noise + vein // 3)))
                image.setPixelColor(x, y, color)

        return QPixmap.fromImage(image)

    def _create_piece_renderers(self) -> dict[Piece, QSvgRenderer]:
        renderers: dict[Piece, QSvgRenderer] = {}
        for color in ("white", "black"):
            for piece in ("K", "Q", "R", "B", "N", "P"):
                renderer = self._load_piece_renderer(color=color, piece=piece)
                renderers[(color, piece)] = renderer
        return renderers

    def _load_piece_renderer(self, *, color: str, piece: str) -> QSvgRenderer:
        prefix = "w" if color == "white" else "b"
        path = _ASSET_DIR / f"{prefix}{piece}.svg"
        if path.exists():
            return QSvgRenderer(path.as_posix())

        fallback = self._fallback_piece_svg(piece=piece, color=color)
        return QSvgRenderer(QByteArray(fallback.encode("utf-8")))

    @staticmethod
    def _fallback_piece_svg(*, piece: str, color: str) -> str:
        if color == "white":
            body = "#f8fafc"
            stroke = "#1f2937"
            text = "#0f172a"
        else:
            body = "#0f172a"
            stroke = "#dbeafe"
            text = "#dbeafe"

        return (
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>"
            "<circle cx='50' cy='50' r='39' fill='"
            + body
            + "' stroke='"
            + stroke
            + "' stroke-width='4'/>"
            "<text x='50' y='63' text-anchor='middle' font-size='42' "
            "font-family='DejaVu Sans, Arial, sans-serif' fill='"
            + text
            + "'>"
            + piece
            + "</text></svg>"
        )


__all__ = ["BoardView"]
