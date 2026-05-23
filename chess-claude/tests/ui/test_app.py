"""Tests for :mod:`ui_qt.app`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_chess_app_creates_window_and_controller(monkeypatch) -> None:
    """The app creates a MainWindow and ChessController."""

    mock_qapp = MagicMock()
    mock_qapp_class = MagicMock(return_value=mock_qapp)
    mock_qapp.instance = MagicMock(return_value=None)

    mock_window = MagicMock()
    mock_controller = MagicMock()

    with (
        patch("ui_qt.app.QApplication", mock_qapp_class),
        patch("ui_qt.app.MainWindow", return_value=mock_window),
        patch("ui_qt.app.ChessController", return_value=mock_controller),
    ):
        from ui_qt.app import ChessApp

        app = ChessApp()
        assert app.window is mock_window
        assert app.controller is mock_controller
        mock_window.show.assert_called_once()
