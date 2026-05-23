"""PySide6 application bootstrap for the chess UI."""

from __future__ import annotations

import os
import platform

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow

from config import (
    MODEL_PRESETS,
    PROVIDER_ENV_KEYS,
    PROVIDER_KEYS,
    PROVIDER_LABELS,
    ProviderKeyDiagnostic,
    ProviderKeyResolver,
)
from telemetry import TelemetryLogger

from .controller import ChessController
from .controls import ChessControls
from .theme import APP_STYLE_SHEET, BASE_FONT_FAMILY, BASE_FONT_SIZE


class ChessApp(QMainWindow):
    """Main window hosting the chess controls and controller."""

    SHELL_PROBE_OPT_IN_ENV = "CHESS_IMPORT_KEYS_FROM_LOGIN_SHELL"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Chess: Human + AI + Commentator")
        self.resize(1560, 980)
        self._last_key_diagnostics_text = ""
        self._shell_probe_enabled = self._env_flag(self.SHELL_PROBE_OPT_IN_ENV)

        self._apply_theme()

        self.controls = ChessControls(self)
        self.setCentralWidget(self.controls)
        board_view = self.controls.create_board_view()
        self.controls.set_reload_keys_callback(self.reload_provider_keys)
        self.controls.set_key_diagnostics_callback(self.show_key_diagnostics)

        self._provider_items = [(PROVIDER_LABELS[key], key) for key in PROVIDER_KEYS]

        telemetry = TelemetryLogger()
        self.controller = ChessController(
            self.controls,
            board_view,
            telemetry=telemetry,
        )
        self.reload_provider_keys()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.controller.shutdown()
        super().closeEvent(event)

    def reload_provider_keys(self) -> None:
        self._refresh_provider_keys(append_log=True)
        self.controls.set_status("Provider key detection refreshed")

    def show_key_diagnostics(self) -> None:
        self._refresh_provider_keys(append_log=False)
        self.controls.show_key_diagnostics(self._last_key_diagnostics_text)

    def _refresh_provider_keys(self, *, append_log: bool) -> None:
        resolver = ProviderKeyResolver()
        imported = resolver.import_missing_from_login_shell(
            enabled=self._shell_probe_enabled,
            log_diagnostics=append_log,
        )
        diagnostics = resolver.diagnostics(log_diagnostics=append_log)
        availability = {provider: diagnostics[provider].present for provider in PROVIDER_KEYS}

        self.controls.set_provider_metadata(
            provider_items=self._provider_items,
            model_presets=MODEL_PRESETS,
            availability=availability,
        )

        missing_labels = [
            PROVIDER_LABELS[key] for key in PROVIDER_KEYS if not availability.get(key)
        ]
        imported_labels = [PROVIDER_LABELS[key] for key in PROVIDER_KEYS if imported[key]]

        self._last_key_diagnostics_text = self._build_key_diagnostics_report(
            diagnostics=diagnostics,
            missing_labels=missing_labels,
            imported_labels=imported_labels,
        )

        if not append_log:
            return

        if self._shell_probe_enabled and imported_labels:
            imported_text = ", ".join(imported_labels)
            self.controls.append_log_entry(
                f"[key-check] imported from login shell: {imported_text}"
            )

        if missing_labels:
            missing_text = ", ".join(missing_labels)
            if self._shell_probe_enabled:
                self.controls.append_log_entry(
                    f"[key-check] login shell probe found no key for: {missing_text}"
                )
            else:
                self.controls.append_log_entry(
                    f"[key-check] missing in current process env: {missing_text}"
                )

        context_lines = self._context_lines()
        for line in context_lines:
            self.controls.append_log_entry(f"[key-check] {line}")

        for provider_key in PROVIDER_KEYS:
            info = diagnostics[provider_key]
            self.controls.append_log_entry(
                "[key-check] "
                f"{PROVIDER_LABELS[provider_key]} "
                f"env={PROVIDER_ENV_KEYS[provider_key]} "
                f"present={info.present} "
                f"length={info.length}"
            )

    def _build_key_diagnostics_report(
        self,
        *,
        diagnostics: dict[str, ProviderKeyDiagnostic],
        missing_labels: list[str],
        imported_labels: list[str],
    ) -> str:
        lines = [
            "Provider Key Diagnostics",
            "",
            "Provider visibility in this running process:",
        ]
        for provider_key in PROVIDER_KEYS:
            info = diagnostics[provider_key]
            lines.append(
                f"- {PROVIDER_LABELS[provider_key]} "
                f"(provider={info.provider}, env={info.env_key}): "
                f"present={info.present}, length={info.length}"
            )

        lines.extend(["", "Safe process context hints:"])
        lines.extend(f"- {line}" for line in self._context_lines())

        if self._shell_probe_enabled:
            if imported_labels:
                lines.append(f"- login-shell import (opt-in): {', '.join(imported_labels)}")
            else:
                lines.append("- login-shell import (opt-in): no keys imported")
        else:
            lines.append(
                f"- login-shell import (opt-in via {self.SHELL_PROBE_OPT_IN_ENV}=1): disabled"
            )

        if missing_labels:
            lines.append(f"- currently missing: {', '.join(missing_labels)}")
        else:
            lines.append("- currently missing: none")

        lines.extend(
            [
                "",
                "Troubleshooting:",
                "1) Verify keys in the same environment that starts the app:",
                "   env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'",
                "2) If launching from an IDE/GUI:",
                "   - Start the IDE from a terminal with the exports, or",
                "   - Add the env vars to the IDE run configuration.",
                "3) Avoid launching via sudo (sudo strips env by default).",
            ]
        )
        return "\n".join(lines)

    def _context_lines(self) -> list[str]:
        lines = [
            f"platform={platform.system()} ({os.name})",
            f"SUDO_USER set={bool(os.getenv('SUDO_USER'))}",
            f"shell_probe_opt_in={self._shell_probe_enabled}",
        ]
        if hasattr(os, "getuid"):
            lines.append(f"uid={os.getuid()} euid={os.geteuid()}")
        return lines

    @staticmethod
    def _env_flag(name: str) -> bool:
        raw = os.getenv(name, "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return

        app.setStyle("Fusion")

        font = QFont(BASE_FONT_FAMILY, BASE_FONT_SIZE)
        app.setFont(font)

        app.setStyleSheet(APP_STYLE_SHEET)


__all__ = ["ChessApp"]
