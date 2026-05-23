"""Player configuration card (Human/AI, provider, model selection)."""

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

from config import get_provider_statuses
from ui_qt.theme.palette import NEON_CYAN, TEXT_MUTED

CUSTOM_MODEL_OPTION = "(Custom...)"


class PlayerConfig(QWidget):
    """Configuration panel for a single player (White or Black)."""

    mode_changed = Signal(str, str)  # colour, mode
    provider_changed = Signal(str, str)  # colour, provider_key
    model_changed = Signal(str, str)  # colour, model

    def __init__(self, colour: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colour = colour
        self._provider_display_to_key: dict[str, str] = {}
        self._model_presets: dict[str, tuple[str, ...]] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        label_text = "White" if self._colour == "white" else "Black"
        header = QLabel(label_text)
        header.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {NEON_CYAN};")
        layout.addWidget(header)

        # Mode row
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_label = QLabel("Player:")
        mode_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        mode_row.addWidget(mode_label)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Human", "AI"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo, stretch=1)
        layout.addLayout(mode_row)

        # Provider row
        provider_row = QHBoxLayout()
        provider_row.setSpacing(6)
        provider_label = QLabel("Provider:")
        provider_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        provider_row.addWidget(provider_label)

        self._provider_combo = QComboBox()
        self._provider_combo.setEnabled(False)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._provider_combo, stretch=1)
        layout.addLayout(provider_row)

        # Model row
        model_row = QHBoxLayout()
        model_row.setSpacing(6)
        model_label = QLabel("Model:")
        model_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        model_row.addWidget(model_label)

        self._model_combo = QComboBox()
        self._model_combo.setEnabled(False)
        self._model_combo.currentTextChanged.connect(self._on_model_selected)
        model_row.addWidget(self._model_combo, stretch=1)
        layout.addLayout(model_row)

        # Custom model entry
        self._custom_entry = QLineEdit()
        self._custom_entry.setPlaceholderText("Enter custom model ID...")
        self._custom_entry.setVisible(False)
        self._custom_entry.textChanged.connect(
            lambda _: self.model_changed.emit(self._colour, self.get_model())
        )
        layout.addWidget(self._custom_entry)

    def _on_mode_changed(self, text: str) -> None:
        is_ai = text == "AI"
        self._provider_combo.setEnabled(is_ai)
        self._model_combo.setEnabled(is_ai)
        if not is_ai:
            self._custom_entry.setVisible(False)
        mode = "ai" if is_ai else "human"
        self.mode_changed.emit(self._colour, mode)

    def _on_provider_changed(self, display_text: str) -> None:
        key = self._provider_display_to_key.get(display_text, "")
        self._sync_model_options(key)
        self.provider_changed.emit(self._colour, key)

    def _on_model_selected(self, text: str) -> None:
        self._custom_entry.setVisible(text == CUSTOM_MODEL_OPTION)
        self.model_changed.emit(self._colour, self.get_model())

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

    def get_player_type(self) -> str:
        return "ai" if self._mode_combo.currentText() == "AI" else "human"

    def set_player_type(self, player_type: str) -> None:
        self._mode_combo.setCurrentText("AI" if player_type == "ai" else "Human")

    def get_provider(self) -> str:
        return self._provider_display_to_key.get(self._provider_combo.currentText(), "")

    def get_model(self) -> str:
        selected = self._model_combo.currentText()
        if selected == CUSTOM_MODEL_OPTION:
            return self._custom_entry.text().strip()
        return selected.strip() if selected else ""

    def is_provider_available(self, provider_key: str) -> bool:
        """Check live from os.environ whether the provider's API key is set."""
        statuses = get_provider_statuses()
        return statuses.get(provider_key, False)

    def set_controls_enabled(self, enabled: bool) -> None:
        is_ai = self.get_player_type() == "ai"
        self._mode_combo.setEnabled(enabled)
        self._provider_combo.setEnabled(enabled and is_ai)
        self._model_combo.setEnabled(enabled and is_ai)
        self._custom_entry.setEnabled(enabled and is_ai)


__all__ = ["PlayerConfig", "CUSTOM_MODEL_OPTION"]
