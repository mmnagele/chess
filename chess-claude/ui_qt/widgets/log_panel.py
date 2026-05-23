"""Move/event log panel (read-only scrollable log)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui_qt.theme.palette import NEON_CYAN


class LogPanel(QWidget):
    """Read-only scrollable event/move log."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QLabel(title)
        header.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {NEON_CYAN}; padding: 2px 0;"
        )
        layout.addWidget(header)

        self._text = QTextBrowser()
        self._text.setReadOnly(True)
        self._text.setOpenExternalLinks(False)
        self._text.setPlaceholderText("Moves and events will appear here...")
        layout.addWidget(self._text, stretch=1)

    def _is_near_bottom(self) -> bool:
        sb = self._text.verticalScrollBar()
        return sb.value() >= sb.maximum() - 30

    def append_line(self, content: str) -> None:
        was_at_bottom = self._is_near_bottom()
        self._text.append(content)
        if was_at_bottom:
            sb = self._text.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear(self) -> None:
        self._text.clear()


__all__ = ["LogPanel"]
