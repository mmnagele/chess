"""Commentator configuration and chat panel."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config import COMMENTATOR_TYPES, get_provider_statuses
from ui_qt.theme.palette import NEON_CYAN, TEXT_MUTED

from .chat_panel import ChatPanel

CUSTOM_MODEL_OPTION = "(Custom...)"


class CommentatorPanel(QWidget):
    """Commentator config + transcript + input."""

    config_changed = Signal()
    chat_message_sent = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._provider_display_to_key: dict[str, str] = {}
        self._model_presets: dict[str, tuple[str, ...]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Header
        header = QLabel("Commentator")
        header.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {NEON_CYAN};")
        layout.addWidget(header)

        # On/Off toggle
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        toggle_label = QLabel("State:")
        toggle_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        toggle_row.addWidget(toggle_label)
        self._toggle = QComboBox()
        self._toggle.addItems(["Off", "On"])
        self._toggle.currentTextChanged.connect(lambda _: self.config_changed.emit())
        toggle_row.addWidget(self._toggle, stretch=1)
        layout.addLayout(toggle_row)

        # Type
        type_row = QHBoxLayout()
        type_row.setSpacing(6)
        type_label = QLabel("Type:")
        type_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        type_row.addWidget(type_label)
        self._type_combo = QComboBox()
        self._type_combo.addItems(list(COMMENTATOR_TYPES))
        self._type_combo.currentTextChanged.connect(lambda _: self.config_changed.emit())
        type_row.addWidget(self._type_combo, stretch=1)
        layout.addLayout(type_row)

        # Provider
        provider_row = QHBoxLayout()
        provider_row.setSpacing(6)
        provider_label = QLabel("Provider:")
        provider_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        provider_row.addWidget(provider_label)
        self._provider_combo = QComboBox()
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._provider_combo, stretch=1)
        layout.addLayout(provider_row)

        # Model
        model_row = QHBoxLayout()
        model_row.setSpacing(6)
        model_label = QLabel("Model:")
        model_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        model_row.addWidget(model_label)
        self._model_combo = QComboBox()
        self._model_combo.currentTextChanged.connect(self._on_model_selected)
        model_row.addWidget(self._model_combo, stretch=1)
        layout.addLayout(model_row)

        # Custom model entry
        self._custom_entry = QLineEdit()
        self._custom_entry.setPlaceholderText("Enter custom model ID...")
        self._custom_entry.setVisible(False)
        self._custom_entry.textChanged.connect(lambda _: self.config_changed.emit())
        layout.addWidget(self._custom_entry)

        # Adult plays side
        side_row = QHBoxLayout()
        side_row.setSpacing(6)
        side_label = QLabel("Adult plays:")
        side_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        side_row.addWidget(side_label)
        self._adult_side = QComboBox()
        self._adult_side.addItems(["White", "Black"])
        self._adult_side.currentTextChanged.connect(lambda _: self.config_changed.emit())
        side_row.addWidget(self._adult_side, stretch=1)
        layout.addLayout(side_row)

        # Chat panel
        self._chat = ChatPanel("Commentator Chat")
        self._chat.message_sent.connect(self.chat_message_sent.emit)
        layout.addWidget(self._chat, stretch=1)

    def _on_provider_changed(self, display_text: str) -> None:
        key = self._provider_display_to_key.get(display_text, "")
        self._sync_model_options(key)
        self.config_changed.emit()

    def _on_model_selected(self, text: str) -> None:
        self._custom_entry.setVisible(text == CUSTOM_MODEL_OPTION)
        self.config_changed.emit()

    def _sync_model_options(self, provider_key: str, *, preferred_model: str = "") -> None:
        presets = self._model_presets.get(provider_key, ())
        preferred = preferred_model.strip()
        selected_index = 0
        custom_text = ""
        if preferred:
            if preferred in presets:
                selected_index = presets.index(preferred)
            else:
                selected_index = len(presets)
                custom_text = preferred

        self._model_combo.blockSignals(True)
        self._model_combo.clear()
        self._model_combo.addItems(list(presets) + [CUSTOM_MODEL_OPTION])
        if self._model_combo.count():
            self._model_combo.setCurrentIndex(min(selected_index, self._model_combo.count() - 1))
        self._model_combo.blockSignals(False)

        self._custom_entry.blockSignals(True)
        self._custom_entry.setText(custom_text)
        self._custom_entry.blockSignals(False)
        self._custom_entry.setVisible(self._model_combo.currentText() == CUSTOM_MODEL_OPTION)

    def set_provider_metadata(
        self,
        *,
        provider_items: list[tuple[str, str]],
        model_presets: dict[str, tuple[str, ...]],
        availability: dict[str, bool],
    ) -> None:
        self._model_presets = dict(model_presets)

        # Preserve current selection so a refresh doesn't lose the user's choice
        prev_key = self.get_provider()
        prev_model = self.get_model()

        self._provider_display_to_key = {}
        self._provider_combo.blockSignals(True)
        self._provider_combo.clear()
        restore_idx = 0
        for label, key in provider_items:
            is_available = bool(availability.get(key))
            display = label if is_available else f"{label} (missing key)"
            self._provider_display_to_key[display] = key
            self._provider_combo.addItem(display)
            if key == prev_key:
                restore_idx = self._provider_combo.count() - 1

        if self._provider_combo.count() > 0:
            self._provider_combo.setCurrentIndex(restore_idx)
        self._provider_combo.blockSignals(False)

        current_key = self._provider_display_to_key.get(self._provider_combo.currentText(), "")
        preferred_model = prev_model if current_key == prev_key else ""
        self._sync_model_options(current_key, preferred_model=preferred_model)

    def get_enabled(self) -> bool:
        return self._toggle.currentText() == "On"

    def get_type(self) -> str:
        return self._type_combo.currentText()

    def get_provider(self) -> str:
        return self._provider_display_to_key.get(self._provider_combo.currentText(), "")

    def get_model(self) -> str:
        selected = self._model_combo.currentText()
        if selected == CUSTOM_MODEL_OPTION:
            return self._custom_entry.text().strip()
        return selected.strip() if selected else ""

    def get_adult_side(self) -> str:
        return self._adult_side.currentText()

    def is_provider_available(self, provider_key: str) -> bool:
        """Check live from os.environ whether the provider's API key is set."""
        statuses = get_provider_statuses()
        return statuses.get(provider_key, False)

    def append_chat(self, text: str) -> None:
        self._chat.append_message(text)

    def clear_chat(self) -> None:
        self._chat.clear()

    def set_controls_enabled(self, enabled: bool) -> None:
        self._toggle.setEnabled(enabled)
        self._type_combo.setEnabled(enabled)
        self._provider_combo.setEnabled(enabled)
        self._model_combo.setEnabled(enabled)
        self._custom_entry.setEnabled(enabled)
        self._adult_side.setEnabled(enabled)
        self._chat.set_input_enabled(enabled)


__all__ = ["CommentatorPanel"]
