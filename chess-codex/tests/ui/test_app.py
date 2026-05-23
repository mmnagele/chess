"""Tests for :mod:`ui.app`."""

from __future__ import annotations

from dataclasses import dataclass

from ui.app import ChessApp
from ui.theme import APP_STYLE_SHEET


class RecordingController:
    """Controller stub storing constructor arguments."""

    def __init__(self, controls, board_view, *, telemetry) -> None:
        self.controls = controls
        self.board_view = board_view
        self.telemetry = telemetry
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True


@dataclass(frozen=True)
class FakeDiagnostic:
    provider: str
    env_key: str
    present: bool
    length: int


class FakeResolver:
    def import_missing_from_login_shell(
        self,
        *,
        timeout_seconds=1.5,
        enabled=False,
        log_diagnostics=False,
    ):
        _ = timeout_seconds
        _ = enabled
        _ = log_diagnostics
        return {"openai": False, "anthropic": False, "gemini": False}

    def statuses(self, *, log_diagnostics=False):
        _ = log_diagnostics
        return {"openai": True, "anthropic": False, "gemini": True}

    def diagnostics(self, *, log_diagnostics=False):
        _ = log_diagnostics
        return {
            "openai": FakeDiagnostic("openai", "OPENAI_API_KEY", True, 24),
            "anthropic": FakeDiagnostic("anthropic", "ANTHROPIC_API_KEY", False, 0),
            "gemini": FakeDiagnostic("gemini", "GEMINI_API_KEY", True, 39),
        }


def test_chess_app_initialises_controller(monkeypatch, qapp) -> None:
    monkeypatch.setattr("ui.app.ChessController", RecordingController)
    monkeypatch.setattr("ui.app.ProviderKeyResolver", FakeResolver)

    app = ChessApp()

    assert app.windowTitle() == "Chess: Human + AI + Commentator"
    assert isinstance(app.controller, RecordingController)
    assert app.controller.controls is app.controls
    assert app.controller.board_view is not None
    assert "Provider key detection refreshed" in app.controls.status_label.text()

    log_text = app.controls.log_panel._text.toPlainText()  # pylint: disable=protected-access
    assert "[key-check] shell_probe_opt_in=False" in log_text
    assert "[key-check] OpenAI env=OPENAI_API_KEY present=True length=24" in log_text

    app.show_key_diagnostics()
    dialog = app.controls._key_diagnostics_dialog  # pylint: disable=protected-access
    assert dialog is not None
    assert "Troubleshooting:" in dialog._text.toPlainText()  # pylint: disable=protected-access

    app.close()
    qapp.processEvents()
    assert app.controller.shutdown_called is True


def test_theme_defines_button_states() -> None:
    assert "QPushButton, QToolButton" in APP_STYLE_SHEET
    assert "QPushButton:hover, QToolButton:hover" in APP_STYLE_SHEET
    assert "QPushButton:pressed, QToolButton:pressed" in APP_STYLE_SHEET
    assert "QPushButton:checked, QToolButton:checked" in APP_STYLE_SHEET
    assert "QPushButton:disabled, QToolButton:disabled" in APP_STYLE_SHEET
    assert 'QPushButton[variant="ghost"], QToolButton[variant="ghost"]' in APP_STYLE_SHEET
    assert "QTextBrowser" in APP_STYLE_SHEET
    assert "QPlainTextEdit" in APP_STYLE_SHEET
    assert '#TurnBadge[side="white"]' in APP_STYLE_SHEET
    assert '#TurnBadge[side="black"]' in APP_STYLE_SHEET
