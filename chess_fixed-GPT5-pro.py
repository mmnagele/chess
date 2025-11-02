"""Startpunkt für die Tkinter-Schachanwendung."""

import tkinter as tk

from ui.app import ChessApp


def main() -> None:
    root = tk.Tk()
    ChessApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
