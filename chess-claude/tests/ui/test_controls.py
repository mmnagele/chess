"""Tests for ui_qt widget configuration logic (no Qt display needed)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

COMMENTATOR_CUSTOM_MODEL = "(Custom...)"


class _FakeCombo:
    def __init__(self, items: list[str] | None = None, current_index: int = 0) -> None:
        self._items = list(items or [])
        self._current_index = current_index if self._items else -1

    def blockSignals(self, _enabled: bool) -> None:  # noqa: N802 - Qt naming
        return

    def clear(self) -> None:
        self._items = []
        self._current_index = -1

    def addItem(self, item: str) -> None:
        self._items.append(item)
        if self._current_index < 0:
            self._current_index = 0

    def addItems(self, items: list[str]) -> None:
        for item in items:
            self.addItem(item)

    def count(self) -> int:
        return len(self._items)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 - Qt naming
        if not self._items:
            self._current_index = -1
            return
        self._current_index = max(0, min(index, len(self._items) - 1))

    def currentText(self) -> str:  # noqa: N802 - Qt naming
        if self._current_index < 0 or self._current_index >= len(self._items):
            return ""
        return self._items[self._current_index]


class _FakeLineEdit:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.visible = False

    def blockSignals(self, _enabled: bool) -> None:  # noqa: N802 - Qt naming
        return

    def setText(self, text: str) -> None:  # noqa: N802 - Qt naming
        self._text = text

    def text(self) -> str:
        return self._text

    def setVisible(self, visible: bool) -> None:  # noqa: N802 - Qt naming
        self.visible = visible


def test_player_config_get_set_type() -> None:
    """PlayerConfig correctly returns player type."""
    with patch("ui_qt.widgets.player_config.QWidget.__init__", return_value=None):
        from ui_qt.widgets.player_config import PlayerConfig

        pc = PlayerConfig.__new__(PlayerConfig)
        pc._colour = "white"
        pc._provider_display_to_key = {}
        pc._model_presets = {}

        # Simulate combo box
        pc._mode_combo = MagicMock()
        pc._mode_combo.currentText.return_value = "Human"
        assert pc.get_player_type() == "human"

        pc._mode_combo.currentText.return_value = "AI"
        assert pc.get_player_type() == "ai"


def test_player_config_get_model_custom() -> None:
    """PlayerConfig returns custom model text when Custom is selected."""
    with patch("ui_qt.widgets.player_config.QWidget.__init__", return_value=None):
        from ui_qt.widgets.player_config import CUSTOM_MODEL_OPTION, PlayerConfig

        pc = PlayerConfig.__new__(PlayerConfig)
        pc._colour = "white"
        pc._provider_display_to_key = {}
        pc._model_presets = {}

        pc._model_combo = MagicMock()
        pc._model_combo.currentText.return_value = CUSTOM_MODEL_OPTION
        pc._custom_entry = MagicMock()
        pc._custom_entry.text.return_value = "my-custom-model"

        assert pc.get_model() == "my-custom-model"


def test_player_config_get_model_preset() -> None:
    """PlayerConfig returns preset model when a preset is selected."""
    with patch("ui_qt.widgets.player_config.QWidget.__init__", return_value=None):
        from ui_qt.widgets.player_config import PlayerConfig

        pc = PlayerConfig.__new__(PlayerConfig)
        pc._colour = "white"
        pc._provider_display_to_key = {}
        pc._model_presets = {}

        pc._model_combo = MagicMock()
        pc._model_combo.currentText.return_value = "gpt-4o-mini"
        pc._custom_entry = MagicMock()

        assert pc.get_model() == "gpt-4o-mini"


def test_commentator_panel_get_enabled() -> None:
    """CommentatorPanel correctly reports enabled/disabled state."""
    with patch("ui_qt.widgets.commentator_panel.QWidget.__init__", return_value=None):
        from ui_qt.widgets.commentator_panel import CommentatorPanel

        cp = CommentatorPanel.__new__(CommentatorPanel)
        cp._toggle = MagicMock()

        cp._toggle.currentText.return_value = "Off"
        assert cp.get_enabled() is False

        cp._toggle.currentText.return_value = "On"
        assert cp.get_enabled() is True


def test_commentator_panel_get_type() -> None:
    """CommentatorPanel returns the selected commentator type."""
    with patch("ui_qt.widgets.commentator_panel.QWidget.__init__", return_value=None):
        from ui_qt.widgets.commentator_panel import CommentatorPanel

        cp = CommentatorPanel.__new__(CommentatorPanel)
        cp._type_combo = MagicMock()
        cp._type_combo.currentText.return_value = "Tournament Commentator"
        assert cp.get_type() == "Tournament Commentator"


def test_player_config_set_provider_metadata_preserves_model_selection() -> None:
    with patch("ui_qt.widgets.player_config.QWidget.__init__", return_value=None):
        from ui_qt.widgets.player_config import PlayerConfig

        pc = PlayerConfig.__new__(PlayerConfig)
        pc._colour = "white"
        pc._provider_display_to_key = {"OpenAI": "openai"}
        pc._model_presets = {"openai": ("old-a", "old-b")}
        pc._provider_combo = _FakeCombo(["OpenAI"], current_index=0)
        pc._model_combo = _FakeCombo(["old-a", "old-b"], current_index=1)
        pc._custom_entry = _FakeLineEdit("")

        pc.set_provider_metadata(
            provider_items=[("OpenAI", "openai"), ("Anthropic", "anthropic")],
            model_presets={"openai": ("new-a", "old-b"), "anthropic": ("claude",)},
            availability={"openai": True, "anthropic": True},
        )

        assert pc.get_provider() == "openai"
        assert pc.get_model() == "old-b"


def test_commentator_panel_set_provider_metadata_preserves_custom_model() -> None:
    with patch("ui_qt.widgets.commentator_panel.QWidget.__init__", return_value=None):
        from ui_qt.widgets.commentator_panel import CommentatorPanel

        cp = CommentatorPanel.__new__(CommentatorPanel)
        cp._provider_display_to_key = {"OpenAI": "openai"}
        cp._model_presets = {"openai": ("gpt-a",)}
        cp._provider_combo = _FakeCombo(["OpenAI"], current_index=0)
        cp._model_combo = _FakeCombo(["gpt-a", COMMENTATOR_CUSTOM_MODEL], current_index=1)
        cp._custom_entry = _FakeLineEdit("my-custom-model")

        cp.set_provider_metadata(
            provider_items=[("OpenAI", "openai"), ("Gemini", "gemini")],
            model_presets={"openai": ("gpt-a", "gpt-b"), "gemini": ("gemini-2.0-flash",)},
            availability={"openai": True, "gemini": True},
        )

        assert cp.get_provider() == "openai"
        assert cp.get_model() == "my-custom-model"
        assert cp._model_combo.currentText() == COMMENTATOR_CUSTOM_MODEL
