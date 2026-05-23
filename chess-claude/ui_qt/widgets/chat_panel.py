"""Reusable chat panel with rich-text transcript and input."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui_qt.theme.palette import NEON_CYAN, TEXT_MUTED
from ui_qt.widgets.markdown_renderer import format_role_message, markdown_to_html


class ChatPanel(QWidget):
    """Scrollable chat transcript with rich Markdown rendering."""

    message_sent = Signal(str)

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui(title)

    def _setup_ui(self, title: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QLabel(title)
        header.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {NEON_CYAN}; padding: 2px 0;"
        )
        layout.addWidget(header)

        self._transcript = QTextBrowser()
        self._transcript.setReadOnly(True)
        self._transcript.setOpenExternalLinks(False)
        self._transcript.setPlaceholderText("Chat messages will appear here...")
        layout.addWidget(self._transcript, stretch=1)

        input_row = QHBoxLayout()
        input_row.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message...")
        self._input.returnPressed.connect(self._on_send)
        input_row.addWidget(self._input, stretch=1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedWidth(60)
        self._send_btn.clicked.connect(self._on_send)
        input_row.addWidget(self._send_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(60)
        self._clear_btn.clicked.connect(self.clear)
        input_row.addWidget(self._clear_btn)

        layout.addLayout(input_row)

    def _is_near_bottom(self) -> bool:
        """Check if the scrollbar is near the bottom (within 30px)."""
        sb = self._transcript.verticalScrollBar()
        return sb.value() >= sb.maximum() - 30

    def _scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the transcript."""
        sb = self._transcript.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.message_sent.emit(text)

    def append_message(self, text: str) -> None:
        """Append a plain text message, auto-detecting role from prefix."""
        was_at_bottom = self._is_near_bottom()
        html_content = self._detect_and_render(text)
        self._transcript.append(html_content)
        if was_at_bottom:
            self._scroll_to_bottom()

    def append_role_message(self, role: str, text: str) -> None:
        """Append a message with explicit role styling."""
        was_at_bottom = self._is_near_bottom()
        html_content = format_role_message(role, text)
        self._transcript.append(html_content)
        if was_at_bottom:
            self._scroll_to_bottom()

    def set_text(self, content: str) -> None:
        self._transcript.setHtml(markdown_to_html(content))

    def clear(self) -> None:
        self._transcript.clear()

    def set_input_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)

    def set_muted_style(self, muted: bool) -> None:
        color = TEXT_MUTED if muted else NEON_CYAN
        self._transcript.setStyleSheet(f"color: {color};")

    @staticmethod
    def _detect_and_render(text: str) -> str:
        """Auto-detect role from message prefix and render accordingly."""
        if text.startswith("You: "):
            return format_role_message("user", text[5:])
        if text.startswith("AI: "):
            return format_role_message("ai", text[4:])
        if text.startswith("AI suggested MOVE: "):
            return format_role_message("move", text)
        if text.startswith("AI raw response:"):
            return format_role_message("ai", text[len("AI raw response:\n") :])
        if text.startswith("System:") or text.startswith("[System]"):
            return format_role_message("system", text)
        if text.startswith("Commentator error:") or text.startswith("AI error:"):
            return format_role_message("error", text)
        if text.startswith("Commentary: ") or text.startswith("Commentator: "):
            # Extract the content after the prefix for AI rendering
            prefix_end = text.index(": ") + 2
            return format_role_message("ai", text[prefix_end:])
        # Default: render as markdown
        return markdown_to_html(text)


__all__ = ["ChatPanel"]
