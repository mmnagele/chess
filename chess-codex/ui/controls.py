"""PySide6 control surface for the chess application."""

from __future__ import annotations

import re
from html import escape
from typing import Callable, Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config import COMMENTATOR_TYPES

from .board_view import BoardView

CUSTOM_MODEL_OPTION = "(Custom...)"
ChatRole = Literal["system", "user", "ai", "error"]
_MOVE_LINE_RE = re.compile(r"^\s*MOVE\s*:\s*([a-h][1-8][a-h][1-8](?:[qrbn])?)\s*$", re.IGNORECASE)

_TRANSCRIPT_DOCUMENT_STYLE = """
h1, h2, h3 {
  color: #22d3ee;
  margin-top: 6px;
  margin-bottom: 4px;
  font-weight: 700;
}
strong {
  color: #f8fbff;
}
em {
  color: #a7b4c6;
}
code {
  color: #a3e635;
  background-color: #0b1220;
  border: 1px solid #1f2a3a;
  border-radius: 5px;
  padding: 1px 3px;
  font-family: "JetBrains Mono";
}
pre {
  color: #dbe5f3;
  background-color: #0b1220;
  border: 1px solid #2c3a50;
  border-radius: 8px;
  padding: 8px;
}
ul, ol {
  margin-top: 2px;
  margin-bottom: 4px;
}
li {
  margin-bottom: 3px;
}
a {
  color: #22d3ee;
}
.entry {
  margin: 0 0 10px 0;
}
.entry-label {
  font-size: 11px;
  letter-spacing: 0.5px;
  font-weight: 700;
  margin-bottom: 3px;
}
.entry-system .entry-label {
  color: #94a3b8;
}
.entry-user .entry-label {
  color: #22d3ee;
}
.entry-ai .entry-label {
  color: #c8d5e8;
}
.entry-error .entry-label {
  color: #fb7185;
}
.entry-system .plain-body {
  color: #98a8bc;
  font-size: 11px;
}
.entry-user .plain-body {
  color: #e6edf3;
}
.entry-error .plain-body {
  color: #fb7185;
}
.move-pill {
  color: #a3e635;
  background-color: #0b1220;
  border: 1px solid #3c4b66;
  border-radius: 8px;
  font-family: "JetBrains Mono";
  padding: 4px 7px;
  margin: 4px 0;
  font-weight: 600;
}
"""


def _escape_markdown_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _extract_body_html(html: str) -> str:
    body_start = html.find("<body")
    if body_start == -1:
        return html
    open_tag_end = html.find(">", body_start)
    if open_tag_end == -1:
        return html
    close_tag = html.rfind("</body>")
    if close_tag == -1:
        close_tag = len(html)
    return html[open_tag_end + 1 : close_tag]


def _markdown_block_to_html(markdown: str) -> str:
    if not markdown.strip():
        return ""
    document = QTextDocument()
    document.setMarkdown(_escape_markdown_html(markdown))
    return _extract_body_html(document.toHtml())


def _markdown_with_move_lines_to_html(content: str) -> str:
    lines = content.splitlines()
    if not lines:
        return ""

    html_parts: list[str] = []
    buffer: list[str] = []

    for line in lines:
        match = _MOVE_LINE_RE.match(line)
        if match:
            block_html = _markdown_block_to_html("\n".join(buffer))
            if block_html:
                html_parts.append(block_html)
            buffer = []

            move_text = match.group(1).lower()
            html_parts.append(
                f'<div class="move-pill">MOVE: {escape(move_text, quote=False)}</div>'
            )
            continue
        buffer.append(line)

    trailing_html = _markdown_block_to_html("\n".join(buffer))
    if trailing_html:
        html_parts.append(trailing_html)

    return "".join(html_parts)


class _Card(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(8)
        layout.addLayout(self.body)


class _ChatPanel(_Card):
    """Scrollable transcript panel with input and action buttons."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self._text = QTextBrowser(self)
        self._text.setObjectName("ChatTranscript")
        self._text.setMinimumHeight(160)
        self._text.setOpenExternalLinks(True)
        self._text.document().setDefaultStyleSheet(_TRANSCRIPT_DOCUMENT_STYLE)
        self.body.addWidget(self._text)

        row = QHBoxLayout()
        row.setSpacing(6)
        self._entry = QLineEdit(self)
        self._entry.setPlaceholderText("Message...")
        row.addWidget(self._entry, 1)

        self._send_btn = QPushButton("Send", self)
        row.addWidget(self._send_btn)

        self._clear_btn = QPushButton("Clear", self)
        row.addWidget(self._clear_btn)
        self.body.addLayout(row)

        self._send_btn.clicked.connect(self._emit_send)
        self._entry.returnPressed.connect(self._emit_send)
        self._clear_btn.clicked.connect(self.clear)

        self._send_callback: Callable[[str], None] | None = None

    def set_send_callback(self, callback: Callable[[str], None]) -> None:
        self._send_callback = callback

    def _emit_send(self) -> None:
        value = self._entry.text().strip()
        if not value:
            return
        self._entry.clear()
        if self._send_callback:
            self._send_callback(value)

    def set_text(self, content: str, *, role: ChatRole = "system") -> None:
        self._text.clear()
        if content.strip():
            self.append_line(content, role=role)

    def append_line(
        self,
        content: str,
        *,
        role: ChatRole = "ai",
        source: str | None = None,
    ) -> None:
        scrollbar = self._text.verticalScrollBar()
        follow_output = (scrollbar.maximum() - scrollbar.value()) <= 24

        label = source if source else self._role_label(role)
        body_html = self._format_body(content, role=role)
        if not body_html:
            body_html = '<div class="plain-body"></div>'

        entry_html = (
            f'<div class="entry entry-{role}">'
            f'<div class="entry-label">{escape(label, quote=False)}</div>'
            f"{body_html}"
            "</div>"
        )

        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)
        self._text.insertHtml(entry_html)
        self._text.insertHtml("<br/>")

        if follow_output:
            scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self._text.clear()

    def set_input_enabled(self, enabled: bool) -> None:
        self._entry.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        self._clear_btn.setEnabled(enabled)

    @staticmethod
    def _role_label(role: ChatRole) -> str:
        labels: dict[ChatRole, str] = {
            "system": "[System]",
            "user": "[User]",
            "ai": "[AI]",
            "error": "[Error]",
        }
        return labels[role]

    @staticmethod
    def _format_body(content: str, *, role: ChatRole) -> str:
        if role == "ai":
            return _markdown_with_move_lines_to_html(content)
        plain = escape(content, quote=False).replace("\n", "<br/>")
        return f'<div class="plain-body">{plain}</div>'


class _LogPanel(_Card):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self._text = QTextBrowser(self)
        self._text.setObjectName("LogTranscript")
        self._text.setMinimumHeight(180)
        self.body.addWidget(self._text)

    def append_line(self, content: str) -> None:
        scrollbar = self._text.verticalScrollBar()
        follow_output = (scrollbar.maximum() - scrollbar.value()) <= 24
        entry = escape(content, quote=False).replace("\n", "<br/>")
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._text.setTextCursor(cursor)
        self._text.insertHtml(f"<div>{entry}</div><br/>")
        if follow_output:
            scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self._text.clear()


class _KeyDiagnosticsDialog(QDialog):
    """Non-modal diagnostics dialog for provider key visibility checks."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Key Diagnostics")
        self.resize(760, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self._text = QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self._text.setObjectName("KeyDiagnosticsText")
        self._text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._text, 1)

        row = QHBoxLayout()
        row.addStretch(1)
        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.close)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def set_content(self, text: str) -> None:
        self._text.setPlainText(text)
        self._text.verticalScrollBar().setValue(0)


class ChessControls(QWidget):
    """Top-level controls and layout used by the Qt controller."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._new_game_callback: Optional[Callable[[], None]] = None
        self._player_mode_callback: Optional[Callable[[str, str], None]] = None
        self._player_provider_callback: Optional[Callable[[str, str], None]] = None
        self._player_model_callback: Optional[Callable[[str, str], None]] = None
        self._commentator_changed_callback: Optional[Callable[[], None]] = None
        self._reload_keys_callback: Optional[Callable[[], None]] = None
        self._key_diagnostics_callback: Optional[Callable[[], None]] = None

        self._provider_display_to_key: dict[str, str] = {}
        self._provider_available: dict[str, bool] = {}
        self._model_presets: dict[str, tuple[str, ...]] = {}

        self._player_type_selectors: dict[str, QComboBox] = {}
        self._player_provider_selectors: dict[str, QComboBox] = {}
        self._player_model_selectors: dict[str, QComboBox] = {}
        self._key_diagnostics_dialog: _KeyDiagnosticsDialog | None = None

        self._build_layout()

    def _build_layout(self) -> None:
        self.setObjectName("RootPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        toolbar = self._build_toolbar()
        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(7)

        left = self._build_left_column()
        center = self._build_center_column()
        right = self._build_right_column()

        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 3)

        root.addWidget(splitter, 1)

    def _build_toolbar(self) -> QWidget:
        bar = QFrame(self)
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.new_game_button = QPushButton("New Game", bar)
        self.new_game_button.clicked.connect(self._on_new_game)
        layout.addWidget(self.new_game_button)

        self.reset_button = QPushButton("Reset", bar)
        self._set_variant(self.reset_button, "ghost")
        self.reset_button.clicked.connect(self._on_new_game)
        layout.addWidget(self.reset_button)

        self.reload_keys_button = QToolButton(bar)
        self.reload_keys_button.setText("Reload Keys")
        self._set_variant(self.reload_keys_button, "ghost")
        self.reload_keys_button.clicked.connect(self._on_reload_keys)
        layout.addWidget(self.reload_keys_button)

        self.key_diagnostics_button = QToolButton(bar)
        self.key_diagnostics_button.setText("Key Diagnostics")
        self._set_variant(self.key_diagnostics_button, "ghost")
        self.key_diagnostics_button.clicked.connect(self._on_key_diagnostics)
        layout.addWidget(self.key_diagnostics_button)

        self.player_indicator = QLabel("Turn: White", bar)
        self.player_indicator.setObjectName("TurnBadge")
        self.player_indicator.setProperty("side", "white")
        self.player_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.player_indicator.setMinimumWidth(120)
        layout.addWidget(self.player_indicator)

        layout.addStretch(1)

        self.status_label = QLabel("Ready", bar)
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.status_label, 2)

        return bar

    def _build_left_column(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        config = _Card("Commentator", container)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("State", config), 0, 0)
        self._commentator_toggle = QComboBox(config)
        self._commentator_toggle.addItems(["Off", "On"])
        self._commentator_toggle.currentIndexChanged.connect(
            lambda _i: self._on_commentator_changed()
        )
        grid.addWidget(self._commentator_toggle, 0, 1)

        grid.addWidget(QLabel("Type", config), 1, 0)
        self._commentator_type = QComboBox(config)
        self._commentator_type.addItems(list(COMMENTATOR_TYPES))
        self._commentator_type.currentIndexChanged.connect(
            lambda _i: self._on_commentator_changed()
        )
        grid.addWidget(self._commentator_type, 1, 1)

        grid.addWidget(QLabel("Provider", config), 2, 0)
        self._commentator_provider = QComboBox(config)
        self._commentator_provider.currentIndexChanged.connect(
            self._on_commentator_provider_changed
        )
        grid.addWidget(self._commentator_provider, 2, 1)

        grid.addWidget(QLabel("Model", config), 3, 0)
        self._commentator_model = QComboBox(config)
        self._commentator_model.setEditable(True)
        self._commentator_model.currentIndexChanged.connect(self._on_commentator_model_changed)
        self._commentator_model.lineEdit().editingFinished.connect(self._on_commentator_changed)
        grid.addWidget(self._commentator_model, 3, 1)

        grid.addWidget(QLabel("Adult plays", config), 4, 0)
        self._adult_side = QComboBox(config)
        self._adult_side.addItems(["White", "Black"])
        self._adult_side.currentIndexChanged.connect(lambda _i: self._on_commentator_changed())
        grid.addWidget(self._adult_side, 4, 1)

        config.body.addLayout(grid)
        layout.addWidget(config)

        self.commentary_chat = _ChatPanel("Commentator Chat", container)
        layout.addWidget(self.commentary_chat, 1)

        return container

    def _build_center_column(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        board_card = _Card("Board", container)
        board_card.body.setSpacing(0)
        self.board_container = QWidget(board_card)
        self.board_container.setObjectName("BoardContainer")
        self.board_container_layout = QVBoxLayout(self.board_container)
        self.board_container_layout.setContentsMargins(0, 0, 0, 0)
        board_card.body.addWidget(self.board_container, 1)
        layout.addWidget(board_card, 1)

        return container

    def _build_right_column(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        players = _Card("Players", container)
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        self._create_player_row(players, grid, "white", 0)
        self._create_player_row(players, grid, "black", 1)

        players.body.addLayout(grid)
        layout.addWidget(players)

        self.log_panel = _LogPanel("Move / Event Log", container)
        layout.addWidget(self.log_panel, 1)

        tabs_card = _Card("AI Chats", container)
        tabs_card.body.setContentsMargins(0, 0, 0, 0)
        tabs = QTabWidget(tabs_card)
        self.white_chat = _ChatPanel("White AI Chat", tabs)
        self.black_chat = _ChatPanel("Black AI Chat", tabs)
        tabs.addTab(self.white_chat, "White AI")
        tabs.addTab(self.black_chat, "Black AI")
        tabs_card.body.addWidget(tabs)
        layout.addWidget(tabs_card, 1)

        return container

    def _create_player_row(
        self,
        parent: QWidget,
        grid: QGridLayout,
        colour: str,
        row: int,
    ) -> None:
        label = "White" if colour == "white" else "Black"
        grid.addWidget(QLabel(label, parent), row, 0)

        mode = QComboBox(parent)
        mode.addItems(["Human", "AI"])
        mode.currentIndexChanged.connect(lambda _i, c=colour: self._on_player_mode_changed(c))
        grid.addWidget(mode, row, 1)

        provider = QComboBox(parent)
        provider.currentIndexChanged.connect(
            lambda _i, c=colour: self._on_player_provider_changed(c)
        )
        grid.addWidget(provider, row, 2)

        model = QComboBox(parent)
        model.setEditable(True)
        model.currentIndexChanged.connect(lambda _i, c=colour: self._on_player_model_selected(c))
        model.lineEdit().editingFinished.connect(lambda c=colour: self._on_player_model_selected(c))
        grid.addWidget(model, row, 3)

        self._player_type_selectors[colour] = mode
        self._player_provider_selectors[colour] = provider
        self._player_model_selectors[colour] = model

        self._sync_player_row_state(colour)

    def create_board_view(self) -> BoardView:
        board = BoardView(self.board_container)
        self.board_container_layout.addWidget(board)
        return board

    def set_new_game_callback(self, callback: Callable[[], None]) -> None:
        self._new_game_callback = callback

    def set_player_mode_callback(self, callback: Callable[[str, str], None]) -> None:
        self._player_mode_callback = callback

    def set_player_provider_callback(self, callback: Callable[[str, str], None]) -> None:
        self._player_provider_callback = callback

    def set_player_model_callback(self, callback: Callable[[str, str], None]) -> None:
        self._player_model_callback = callback

    def set_commentator_changed_callback(self, callback: Callable[[], None]) -> None:
        self._commentator_changed_callback = callback

    def set_reload_keys_callback(self, callback: Callable[[], None]) -> None:
        self._reload_keys_callback = callback

    def set_key_diagnostics_callback(self, callback: Callable[[], None]) -> None:
        self._key_diagnostics_callback = callback

    def set_chat_send_callback(self, callback: Callable[[str, str], None]) -> None:
        self.commentary_chat.set_send_callback(lambda message: callback("commentator", message))
        self.white_chat.set_send_callback(lambda message: callback("white", message))
        self.black_chat.set_send_callback(lambda message: callback("black", message))

    def _on_new_game(self) -> None:
        if self._new_game_callback:
            self._new_game_callback()

    def _on_reload_keys(self) -> None:
        if self._reload_keys_callback:
            self._reload_keys_callback()

    def _on_key_diagnostics(self) -> None:
        if self._key_diagnostics_callback:
            self._key_diagnostics_callback()

    def _on_player_mode_changed(self, colour: str) -> None:
        self._sync_player_row_state(colour)
        if self._player_mode_callback:
            self._player_mode_callback(colour, self.get_player_type(colour))

    def _on_player_provider_changed(self, colour: str) -> None:
        self._sync_player_model_options(colour)
        if self._player_provider_callback:
            self._player_provider_callback(colour, self.get_player_provider(colour))

    def _on_player_model_selected(self, colour: str) -> None:
        combo = self._player_model_selectors[colour]
        if combo.currentText().strip() == CUSTOM_MODEL_OPTION:
            combo.setEditText("")
            combo.lineEdit().setFocus()
        if self._player_model_callback:
            self._player_model_callback(colour, self.get_player_model(colour))

    def _on_commentator_provider_changed(self) -> None:
        self._sync_commentator_model_options()
        self._on_commentator_changed()

    def _on_commentator_model_changed(self) -> None:
        if self._commentator_model.currentText().strip() == CUSTOM_MODEL_OPTION:
            self._commentator_model.setEditText("")
            self._commentator_model.lineEdit().setFocus()
        self._on_commentator_changed()

    def _on_commentator_changed(self) -> None:
        if self._commentator_changed_callback:
            self._commentator_changed_callback()

    @staticmethod
    def _set_variant(widget: QWidget, variant: str) -> None:
        widget.setProperty("variant", variant)
        style = widget.style()
        if style is None:
            return
        style.unpolish(widget)
        style.polish(widget)

    def _sync_player_row_state(self, colour: str) -> None:
        ai_enabled = self.get_player_type(colour) == "ai"
        self._player_provider_selectors[colour].setEnabled(ai_enabled)
        self._player_model_selectors[colour].setEnabled(ai_enabled)

    def _sync_player_model_options(self, colour: str) -> None:
        combo = self._player_model_selectors[colour]
        current = combo.currentText().strip()
        key = self.get_player_provider(colour)
        presets = self._model_presets.get(key, ())

        combo.blockSignals(True)
        combo.clear()
        for model in presets:
            combo.addItem(model)
        combo.addItem(CUSTOM_MODEL_OPTION)

        if current and current != CUSTOM_MODEL_OPTION:
            combo.setEditText(current)
        elif presets:
            combo.setCurrentIndex(0)
        else:
            combo.setCurrentText(CUSTOM_MODEL_OPTION)
        combo.blockSignals(False)

    def _sync_commentator_model_options(self) -> None:
        combo = self._commentator_model
        current = combo.currentText().strip()
        key = self.get_commentator_provider()
        presets = self._model_presets.get(key, ())

        combo.blockSignals(True)
        combo.clear()
        for model in presets:
            combo.addItem(model)
        combo.addItem(CUSTOM_MODEL_OPTION)

        if current and current != CUSTOM_MODEL_OPTION:
            combo.setEditText(current)
        elif presets:
            combo.setCurrentIndex(0)
        else:
            combo.setCurrentText(CUSTOM_MODEL_OPTION)
        combo.blockSignals(False)

    def set_provider_metadata(
        self,
        *,
        provider_items: list[tuple[str, str]],
        model_presets: dict[str, tuple[str, ...]],
        availability: dict[str, bool],
    ) -> None:
        self._provider_display_to_key = {}
        self._provider_available = dict(availability)
        self._model_presets = dict(model_presets)

        displays: list[str] = []
        for label, key in provider_items:
            available = bool(availability.get(key))
            display = label if available else f"{label} (missing key)"
            self._provider_display_to_key[display] = key
            displays.append(display)

        for colour in ("white", "black"):
            combo = self._player_provider_selectors[colour]
            current = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(displays)
            if current in displays:
                combo.setCurrentText(current)
            elif displays:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)
            self._sync_player_model_options(colour)
            self._sync_player_row_state(colour)

        current = self._commentator_provider.currentText().strip()
        self._commentator_provider.blockSignals(True)
        self._commentator_provider.clear()
        self._commentator_provider.addItems(displays)
        if current in displays:
            self._commentator_provider.setCurrentText(current)
        elif displays:
            self._commentator_provider.setCurrentIndex(0)
        self._commentator_provider.blockSignals(False)

        self._sync_commentator_model_options()

    def get_player_type(self, colour: str) -> str:
        return "ai" if self._player_type_selectors[colour].currentText() == "AI" else "human"

    def set_player_type(self, colour: str, player_type: str) -> None:
        combo = self._player_type_selectors[colour]
        combo.setCurrentText("AI" if player_type == "ai" else "Human")
        self._sync_player_row_state(colour)

    def get_player_provider(self, colour: str) -> str:
        text = self._player_provider_selectors[colour].currentText().strip()
        return self._provider_display_to_key.get(text, "")

    def get_player_model(self, colour: str) -> str:
        text = self._player_model_selectors[colour].currentText().strip()
        if text == CUSTOM_MODEL_OPTION:
            return ""
        return text

    def is_provider_available(self, provider_key: str) -> bool:
        return bool(self._provider_available.get(provider_key))

    def get_commentator_enabled(self) -> bool:
        return self._commentator_toggle.currentText() == "On"

    def get_commentator_type(self) -> str:
        return self._commentator_type.currentText()

    def get_commentator_provider(self) -> str:
        text = self._commentator_provider.currentText().strip()
        return self._provider_display_to_key.get(text, "")

    def get_commentator_model(self) -> str:
        text = self._commentator_model.currentText().strip()
        if text == CUSTOM_MODEL_OPTION:
            return ""
        return text

    def get_adult_side(self) -> str:
        return self._adult_side.currentText()

    def set_current_player(self, colour: str) -> None:
        colour_name = "White" if colour == "white" else "Black"
        self.player_indicator.setProperty("side", colour)
        style = self.player_indicator.style()
        if style is not None:
            style.unpolish(self.player_indicator)
            style.polish(self.player_indicator)
        self.player_indicator.setText(f"Turn: {colour_name}")

    def set_status(self, status: str) -> None:
        self.status_label.setText(status if status else "Ready")

    def show_key_diagnostics(self, text: str) -> None:
        if self._key_diagnostics_dialog is None:
            self._key_diagnostics_dialog = _KeyDiagnosticsDialog(self)
        self._key_diagnostics_dialog.set_content(text)
        self._key_diagnostics_dialog.show()
        self._key_diagnostics_dialog.raise_()
        self._key_diagnostics_dialog.activateWindow()

    def clear_log(self) -> None:
        self.log_panel.clear()

    def append_log_entry(self, text: str) -> None:
        self.log_panel.append_line(text)

    def append_chat_entry(
        self,
        chat_id: str,
        text: str,
        *,
        role: ChatRole = "ai",
        source: str | None = None,
    ) -> None:
        if chat_id == "commentator":
            self.commentary_chat.append_line(text, role=role, source=source)
            return
        if chat_id == "white":
            self.white_chat.append_line(text, role=role, source=source)
            return
        if chat_id == "black":
            self.black_chat.append_line(text, role=role, source=source)
            return
        raise ValueError(f"Unknown chat id: {chat_id}")

    def clear_chat(self, chat_id: str) -> None:
        if chat_id == "commentator":
            self.commentary_chat.clear()
            return
        if chat_id == "white":
            self.white_chat.clear()
            return
        if chat_id == "black":
            self.black_chat.clear()
            return
        raise ValueError(f"Unknown chat id: {chat_id}")

    def set_commentary(self, text: str) -> None:
        self.commentary_chat.set_text(text, role="system")

    def set_controls_enabled(self, enabled: bool) -> None:
        self.new_game_button.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)
        self.reload_keys_button.setEnabled(enabled)
        self.key_diagnostics_button.setEnabled(enabled)

        self._commentator_toggle.setEnabled(enabled)
        self._commentator_type.setEnabled(enabled)
        self._commentator_provider.setEnabled(enabled)
        self._commentator_model.setEnabled(enabled)
        self._adult_side.setEnabled(enabled)

        for colour in ("white", "black"):
            self._player_type_selectors[colour].setEnabled(enabled)
            ai_enabled = enabled and self.get_player_type(colour) == "ai"
            self._player_provider_selectors[colour].setEnabled(ai_enabled)
            self._player_model_selectors[colour].setEnabled(ai_enabled)

        self.commentary_chat.set_input_enabled(enabled)
        self.white_chat.set_input_enabled(enabled)
        self.black_chat.set_input_enabled(enabled)


__all__ = ["ChessControls", "CUSTOM_MODEL_OPTION"]
