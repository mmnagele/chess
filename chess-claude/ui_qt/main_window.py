"""Main application window with 3-column splitter layout."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import (
    MODEL_PRESETS,
    PROVIDER_KEYS,
    PROVIDER_LABELS,
    get_model_presets,
    get_provider_diagnostics,
    get_provider_statuses,
)
from ui_qt.theme.palette import BG_DARKEST, BG_PANEL, NEON_CYAN, TEXT_MUTED, TEXT_PRIMARY

from .widgets.board_widget import BoardWidget
from .widgets.chat_panel import ChatPanel
from .widgets.commentator_panel import CommentatorPanel
from .widgets.key_diagnostics_dialog import KeyDiagnosticsDialog
from .widgets.log_panel import LogPanel
from .widgets.player_config import PlayerConfig

_STYLE_PATH = Path(__file__).resolve().parent / "theme" / "style.qss"


class MainWindow(QMainWindow):
    """Main chess application window with dark neon theme."""

    model_presets_ready = Signal(int, object)  # generation, presets

    def __init__(self) -> None:
        super().__init__()
        self._model_presets: dict[str, tuple[str, ...]] = dict(MODEL_PRESETS)
        self._model_refresh_inflight = False
        self._model_refresh_generation = 0
        self._last_model_refresh_ts = 0.0
        self.model_presets_ready.connect(self._on_model_presets_ready)

        self.setWindowTitle("Chess: Human + AI + Commentator")
        self.setMinimumSize(1200, 750)
        self.resize(1440, 850)

        self._apply_theme()
        self._create_ui()
        self.refresh_provider_metadata(force_model_refresh=True)

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_DARKEST}; }}")
        if _STYLE_PATH.exists():
            qss = _STYLE_PATH.read_text(encoding="utf-8")
            self.setStyleSheet(qss)

    def _create_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # -- Top toolbar --
        toolbar = self._create_toolbar()
        main_layout.addWidget(toolbar)

        # -- 3-column splitter --
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Left: Commentator
        self.commentator_panel = CommentatorPanel()
        splitter.addWidget(self.commentator_panel)

        # Center: Board
        board_container = QWidget()
        board_layout = QVBoxLayout(board_container)
        board_layout.setContentsMargins(0, 0, 0, 0)

        self.board_widget = BoardWidget()
        board_layout.addWidget(self.board_widget, stretch=1)
        splitter.addWidget(board_container)

        # Right: Player config + move log + player chats
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(6)

        # Player configs
        self.white_config = PlayerConfig("white")
        self.black_config = PlayerConfig("black")
        right_layout.addWidget(self.white_config)
        right_layout.addWidget(self.black_config)

        # Move log
        self.log_panel = LogPanel("Move Log")
        right_layout.addWidget(self.log_panel, stretch=1)

        # Player chat tabs
        self.player_chat_tabs = QTabWidget()
        self.white_chat = ChatPanel("White AI Chat")
        self.black_chat = ChatPanel("Black AI Chat")
        self.player_chat_tabs.addTab(self.white_chat, "White AI")
        self.player_chat_tabs.addTab(self.black_chat, "Black AI")
        right_layout.addWidget(self.player_chat_tabs, stretch=2)

        splitter.addWidget(right_panel)

        # Set splitter proportions
        splitter.setStretchFactor(0, 2)  # commentator
        splitter.setStretchFactor(1, 5)  # board
        splitter.setStretchFactor(2, 3)  # right panel

        main_layout.addWidget(splitter, stretch=1)

        # -- Status bar --
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {TEXT_MUTED};")
        self.status_bar.addWidget(self.status_label, stretch=1)

        self.player_indicator = QLabel("")
        self.player_indicator.setStyleSheet(
            f"font-weight: bold; padding: 2px 12px; color: {TEXT_PRIMARY};"
        )
        self.status_bar.addPermanentWidget(self.player_indicator)

    def _create_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setStyleSheet(
            f"background-color: {BG_PANEL}; border-radius: 8px; " f"border: 1px solid #1F2A3A;"
        )
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        self.new_game_btn = QPushButton("New Game")
        self.new_game_btn.setProperty("role", "primary")
        layout.addWidget(self.new_game_btn)

        self.reload_keys_btn = QPushButton("Reload Keys")
        self.reload_keys_btn.clicked.connect(self._on_reload_keys)
        layout.addWidget(self.reload_keys_btn)

        self.key_diag_btn = QPushButton("Key Diagnostics")
        self.key_diag_btn.clicked.connect(self._on_key_diagnostics)
        layout.addWidget(self.key_diag_btn)

        layout.addStretch(1)

        self.toolbar_status = QLabel("Ready")
        self.toolbar_status.setStyleSheet(
            f"color: {NEON_CYAN}; font-size: 15px; font-weight: bold;"
        )
        layout.addWidget(self.toolbar_status)

        layout.addStretch(1)

        return toolbar

    def _populate_provider_metadata(
        self,
        *,
        model_presets: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        provider_items = [(PROVIDER_LABELS[key], key) for key in PROVIDER_KEYS]
        availability = get_provider_statuses()
        presets = model_presets or self._model_presets

        self.white_config.set_provider_metadata(
            provider_items=provider_items,
            model_presets=presets,
            availability=availability,
        )
        self.black_config.set_provider_metadata(
            provider_items=provider_items,
            model_presets=presets,
            availability=availability,
        )
        self.commentator_panel.set_provider_metadata(
            provider_items=provider_items,
            model_presets=presets,
            availability=availability,
        )

    def _on_key_diagnostics(self) -> None:
        """Open the API Key Diagnostics dialog."""
        dialog = KeyDiagnosticsDialog(self)
        dialog.exec()

    def _on_reload_keys(self) -> None:
        """Re-read API keys from the environment and refresh provider lists."""
        self.refresh_provider_metadata(force_model_refresh=True)
        diag = get_provider_diagnostics()
        for line in diag:
            self.log_panel.append_line(f"[keys] {line}")
        self.set_status("API keys reloaded")

    def refresh_provider_metadata(self, *, force_model_refresh: bool = False) -> None:
        """Re-read provider availability from environment and update all widgets."""
        self._populate_provider_metadata()

        stale = (time.monotonic() - self._last_model_refresh_ts) > 600
        if force_model_refresh or stale:
            self._refresh_model_presets_async()

    def _refresh_model_presets_async(self) -> None:
        if self._model_refresh_inflight:
            return

        self._model_refresh_inflight = True
        self._model_refresh_generation += 1
        generation = self._model_refresh_generation

        def _worker() -> None:
            try:
                presets = get_model_presets(timeout=8.0)
            except Exception:
                presets = dict(self._model_presets)
            self.model_presets_ready.emit(generation, presets)

        threading.Thread(target=_worker, name="model-presets-refresh", daemon=True).start()

    @Slot(int, object)
    def _on_model_presets_ready(self, generation: int, payload: object) -> None:
        if generation != self._model_refresh_generation:
            return

        self._model_refresh_inflight = False
        self._last_model_refresh_ts = time.monotonic()
        if not isinstance(payload, dict):
            return

        normalized: dict[str, tuple[str, ...]] = {}
        for provider_key in PROVIDER_KEYS:
            raw_models = payload.get(provider_key, self._model_presets.get(provider_key, ()))
            if not isinstance(raw_models, (list, tuple)):
                raw_models = self._model_presets.get(provider_key, ())
            models = tuple(str(model).strip() for model in raw_models if str(model).strip())
            normalized[provider_key] = models or self._model_presets.get(provider_key, ())

        if normalized != self._model_presets:
            self._model_presets = normalized
            self._populate_provider_metadata(model_presets=self._model_presets)
            self.log_panel.append_line("[models] Refreshed model presets from provider APIs")

    # -- Public convenience methods --

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.toolbar_status.setText(text)

    def set_current_player(self, colour: str) -> None:
        colour_name = "White" if colour == "white" else "Black"
        if colour == "white":
            style = (
                "font-weight: bold; padding: 2px 12px; "
                "background-color: #E6EDF3; color: #0B0F14; border-radius: 4px;"
            )
        else:
            style = (
                "font-weight: bold; padding: 2px 12px; "
                "background-color: #2A2A2A; color: #E6EDF3; border-radius: 4px;"
            )
        self.player_indicator.setStyleSheet(style)
        self.player_indicator.setText(f"Turn: {colour_name}")

    def append_log_entry(self, text: str) -> None:
        self.log_panel.append_line(text)

    def clear_log(self) -> None:
        self.log_panel.clear()

    def append_chat_entry(self, chat_id: str, text: str) -> None:
        if chat_id == "commentator":
            self.commentator_panel.append_chat(text)
        elif chat_id == "white":
            self.white_chat.append_message(text)
        elif chat_id == "black":
            self.black_chat.append_message(text)

    def clear_chat(self, chat_id: str) -> None:
        if chat_id == "commentator":
            self.commentator_panel.clear_chat()
        elif chat_id == "white":
            self.white_chat.clear()
        elif chat_id == "black":
            self.black_chat.clear()

    def get_player_type(self, colour: str) -> str:
        config = self.white_config if colour == "white" else self.black_config
        return config.get_player_type()

    def get_player_provider(self, colour: str) -> str:
        config = self.white_config if colour == "white" else self.black_config
        return config.get_provider()

    def get_player_model(self, colour: str) -> str:
        config = self.white_config if colour == "white" else self.black_config
        return config.get_model()

    def is_provider_available(self, provider_key: str) -> bool:
        return self.white_config.is_provider_available(provider_key)

    def get_commentator_enabled(self) -> bool:
        return self.commentator_panel.get_enabled()

    def get_commentator_type(self) -> str:
        return self.commentator_panel.get_type()

    def get_commentator_provider(self) -> str:
        return self.commentator_panel.get_provider()

    def get_commentator_model(self) -> str:
        return self.commentator_panel.get_model()

    def get_adult_side(self) -> str:
        return self.commentator_panel.get_adult_side()

    def set_controls_enabled(self, enabled: bool) -> None:
        self.new_game_btn.setEnabled(enabled)
        self.white_config.set_controls_enabled(enabled)
        self.black_config.set_controls_enabled(enabled)
        self.commentator_panel.set_controls_enabled(enabled)
        self.white_chat.set_input_enabled(enabled)
        self.black_chat.set_input_enabled(enabled)


__all__ = ["MainWindow"]
