"""GUI-Bedienelemente für das Schachspiel."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .board_view import BoardView


class _ScrollablePanel(tk.Frame):
    """Hilfsklasse für eine Textanzeige mit Scrollbar."""

    def __init__(self, master: tk.Misc, title: str) -> None:
        super().__init__(master, borderwidth=1, relief="groove")

        header = tk.Label(self, text=title, anchor="w", font=("Helvetica", 12, "bold"))
        header.pack(fill="x", padx=4, pady=2)

        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        scrollbar = ttk.Scrollbar(body, orient="vertical")
        text_widget = tk.Text(
            body,
            wrap="word",
            state="disabled",
            height=12,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=text_widget.yview)

        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._text = text_widget

    def set_text(self, content: str) -> None:
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("end", content)
        self._text.config(state="disabled")
        self._text.see("end")

    def append_line(self, content: str) -> None:
        self._text.config(state="normal")
        if self._text.index("end-1c") != "1.0":
            self._text.insert("end", "\n")
        self._text.insert("end", content)
        self._text.config(state="disabled")
        self._text.see("end")

    def clear(self) -> None:
        self.set_text("")


class ChessControls(tk.Frame):
    """Container für die Steuerleiste und die Seitenpanels."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)
        self.columnconfigure(2, weight=1)
        self.rowconfigure(1, weight=1)

        self._new_game_callback: Optional[Callable[[], None]] = None
        self._player_mode_callback: Optional[Callable[[str, str], None]] = None
        self._player_type_vars: dict[str, tk.StringVar] = {}
        self._player_selectors: dict[str, ttk.Combobox] = {}

        self._create_toolbar()
        self._create_side_panels()

        self.board_container = tk.Frame(self)
        self.board_container.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

    # ------------------------------------------------------------------
    # Aufbau der UI
    def _create_toolbar(self) -> None:
        toolbar = tk.Frame(self, borderwidth=1, relief="ridge")
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=5, pady=5)

        toolbar.columnconfigure(1, weight=1)

        self.player_indicator = tk.Label(toolbar, text="", width=12, relief="sunken")
        self.player_indicator.grid(row=0, column=0, padx=5, pady=5)

        self.status_label = tk.Label(toolbar, text="Bereit", anchor="center")
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.new_game_button = ttk.Button(toolbar, text="Neues Spiel", command=self._on_new_game)
        self.new_game_button.grid(row=0, column=2, padx=5, pady=5)

        player_frame = ttk.LabelFrame(toolbar, text="Spieler")
        player_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=(0, 5), sticky="ew")
        player_frame.columnconfigure(1, weight=1)
        player_frame.columnconfigure(3, weight=1)

        self._create_player_selector(player_frame, "white", 0)
        self._create_player_selector(player_frame, "black", 2)

    def _create_player_selector(self, frame: tk.Misc, colour: str, column: int) -> None:
        label_text = "Weiss" if colour == "white" else "Schwarz"
        label = tk.Label(frame, text=f"{label_text}:")
        label.grid(row=0, column=column, padx=5, pady=5, sticky="w")

        var = tk.StringVar(value="Mensch")
        selector = ttk.Combobox(
            frame,
            textvariable=var,
            state="readonly",
            values=("Mensch", "KI"),
            width=10,
        )
        selector.grid(row=0, column=column + 1, padx=5, pady=5, sticky="ew")
        selector.bind("<<ComboboxSelected>>", lambda _event, c=colour: self._on_player_mode_changed(c))

        self._player_type_vars[colour] = var
        self._player_selectors[colour] = selector

    def _create_side_panels(self) -> None:
        self.commentary_panel = _ScrollablePanel(self, "Kommentator")
        self.commentary_panel.set_text("Hier könnte ein Kommentator sprechen…")
        self.commentary_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.log_panel = _ScrollablePanel(self, "Zug-Log")
        self.log_panel.grid(row=1, column=2, sticky="nsew", padx=5, pady=5)

    # ------------------------------------------------------------------
    # Öffentliche API
    def create_board_view(self) -> BoardView:
        board = BoardView(self.board_container)
        board.pack(fill="both", expand=True)
        return board

    def set_new_game_callback(self, callback: Callable[[], None]) -> None:
        self._new_game_callback = callback

    def _on_new_game(self) -> None:
        if self._new_game_callback:
            self._new_game_callback()

    def set_player_mode_callback(self, callback: Callable[[str, str], None]) -> None:
        """Registriert einen Callback für Änderungen an den Spieler-Typen."""

        self._player_mode_callback = callback

    def _on_player_mode_changed(self, colour: str) -> None:
        if not self._player_mode_callback:
            return

        self._player_mode_callback(colour, self.get_player_type(colour))

    def get_player_type(self, colour: str) -> str:
        value = self._player_type_vars[colour].get()
        return "ai" if value == "KI" else "human"

    def set_player_type(self, colour: str, player_type: str) -> None:
        label = "KI" if player_type == "ai" else "Mensch"
        self._player_type_vars[colour].set(label)

    def set_current_player(self, colour: str) -> None:
        colour_name = "Weiss" if colour == "white" else "Schwarz"
        self.player_indicator.config(text=f"Am Zug: {colour_name}", bg=colour)

    def set_status(self, status: str) -> None:
        self.status_label.config(text=status if status else "Bereit")

    def clear_log(self) -> None:
        self.log_panel.clear()

    def append_log_entry(self, text: str) -> None:
        self.log_panel.append_line(text)

    def set_commentary(self, text: str) -> None:
        self.commentary_panel.set_text(text)

    def set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.new_game_button.config(state=state)
        selector_state = "readonly" if enabled else "disabled"
        for selector in self._player_selectors.values():
            selector.config(state=selector_state)


__all__ = ["ChessControls"]

