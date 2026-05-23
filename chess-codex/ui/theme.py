"""Centralized UI theme configuration for PySide6 widgets."""

from __future__ import annotations

BASE_FONT_FAMILY = "JetBrains Mono"
BASE_FONT_SIZE = 12

APP_STYLE_SHEET = """
QMainWindow {
  background-color: #0b0f14;
}
#RootPanel {
  background-color: transparent;
}
#TopBar {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #101826, stop:1 #0f172a);
  border: 1px solid #1f2a3a;
  border-radius: 10px;
}
#Card {
  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #101826, stop:1 #0f172a);
  border: 1px solid #1f2a3a;
  border-radius: 12px;
}
#CardTitle {
  color: #22d3ee;
  font-size: 14px;
  font-weight: 700;
}
#StatusLabel {
  color: #a3e635;
  font-size: 14px;
  font-weight: 600;
}
#TurnBadge {
  color: #e6edf3;
  background: #1e293b;
  border: 1px solid #1f2a3a;
  border-radius: 10px;
  padding: 4px 8px;
  font-size: 13px;
  font-weight: 600;
}
#TurnBadge[side="white"] {
  background: #e2e8f0;
  color: #0f172a;
  border: 1px solid #93a4b8;
}
#TurnBadge[side="black"] {
  background: #1e293b;
  color: #f8fafc;
  border: 1px solid #334155;
}
QLineEdit, QComboBox, QTextEdit, QTextBrowser, QPlainTextEdit, QTabWidget::pane {
  background: #0f172a;
  color: #e6edf3;
  border: 1px solid #1f2a3a;
  border-radius: 8px;
  selection-background-color: #22d3ee;
  selection-color: #0b0f14;
}
QTextBrowser {
  padding: 6px;
}
QPlainTextEdit {
  padding: 6px;
}
QComboBox::drop-down {
  border: 0px;
  width: 20px;
}
QPushButton, QToolButton {
  background-color: rgba(16, 24, 38, 225);
  color: #f1f6ff;
  border: 1px solid #2c3a50;
  border-radius: 8px;
  padding: 7px 12px;
  font-weight: 600;
}
QPushButton:hover, QToolButton:hover {
  background-color: rgba(24, 38, 56, 240);
  color: #ffffff;
  border: 1px solid #22d3ee;
}
QPushButton:pressed, QToolButton:pressed,
QPushButton:checked, QToolButton:checked {
  background-color: rgba(8, 17, 30, 250);
  color: #f8fffb;
  border: 1px solid #a3e635;
}
QPushButton:disabled, QToolButton:disabled {
  background-color: rgba(10, 16, 28, 190);
  color: #9caec2;
  border: 1px solid #253449;
}
QPushButton[variant="ghost"], QToolButton[variant="ghost"] {
  background-color: rgba(8, 13, 24, 120);
  border: 1px solid rgba(49, 67, 89, 165);
  color: #e8f2ff;
}
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover {
  background-color: rgba(9, 18, 32, 235);
  border: 1px solid #22d3ee;
  color: #ffffff;
}
QPushButton[variant="ghost"]:pressed, QToolButton[variant="ghost"]:pressed,
QPushButton[variant="ghost"]:checked, QToolButton[variant="ghost"]:checked {
  background-color: rgba(13, 24, 39, 228);
  border: 1px solid #a3e635;
  color: #fbfffe;
}
QPushButton[variant="ghost"]:disabled, QToolButton[variant="ghost"]:disabled {
  background-color: rgba(9, 15, 26, 200);
  border: 1px solid rgba(49, 67, 89, 240);
  color: #b0c4d8;
}
QTabBar::tab {
  background: #0f172a;
  color: #9fb0c0;
  border: 1px solid #1f2a3a;
  border-bottom: none;
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  padding: 7px 11px;
  margin-right: 2px;
}
QTabBar::tab:selected {
  color: #22d3ee;
  background: #172a3a;
  border-bottom: 2px solid #22d3ee;
}
QScrollBar:vertical {
  background: #0b0f14;
  width: 10px;
  margin: 2px;
  border: none;
}
QScrollBar::handle:vertical {
  background: #2d4a5c;
  border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
  background: #22d3ee;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
  height: 0px;
}
"""

__all__ = ["APP_STYLE_SHEET", "BASE_FONT_FAMILY", "BASE_FONT_SIZE"]
