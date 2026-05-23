"""API Key Diagnostics dialog for troubleshooting missing/misconfigured keys."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from config import get_key_diagnostics_detail
from ui_qt.theme.palette import NEON_CYAN

_TROUBLESHOOTING = """\

--- Troubleshooting ---

1. GUI / IDE launch: If you launched the app from a desktop shortcut or IDE,
   your shell exports may not be inherited. Launch from a terminal where the
   keys are exported, or configure your IDE to pass environment variables.

2. sudo stripping env: Running with `sudo` strips most environment variables.
   Use `sudo -E` to preserve them, or avoid sudo entirely.

3. .env files are NOT loaded: This app reads keys only from os.environ.
   Make sure your shell profile (e.g. ~/.bashrc) exports the variables.

4. Whitespace-only keys: Keys that consist only of spaces are treated as
   missing. Check for accidental whitespace in your exports.

5. Reload at runtime: Use the "Reload Keys" toolbar button to re-read
   environment variables without restarting the app.

Verify with:
  env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'
"""


class KeyDiagnosticsDialog(QDialog):
    """Modal dialog showing per-provider key status and troubleshooting tips."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("API Key Diagnostics")
        self.setMinimumSize(520, 420)
        self.resize(580, 480)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel("API Key Diagnostics")
        header.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {NEON_CYAN}; padding: 4px 0;"
        )
        layout.addWidget(header)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        layout.addWidget(self._text, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)

        btn_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        entries = get_key_diagnostics_detail()
        lines: list[str] = []
        for entry in entries:
            if entry.get("provider") == "_platform":
                lines.append(
                    f"Platform: {entry.get('system', '?')}, " f"User: {entry.get('user', '?')}"
                )
                continue
            status = "SET" if entry.get("present") else "MISSING"
            detail = ""
            if entry.get("present"):
                detail = f"  (length={entry.get('length')}, prefix={entry.get('prefix')})"
            lines.append(f"{entry['env_var']} ({entry['provider']}): {status}{detail}")

        lines.append(_TROUBLESHOOTING)
        self._text.setPlainText("\n".join(lines))


__all__ = ["KeyDiagnosticsDialog"]
