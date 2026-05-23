"""Entry point for the PySide6 chess application."""

import sys

from ui_qt.app import ChessApp


def main() -> None:
    app = ChessApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
