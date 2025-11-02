
import tkinter as tk
from tkinter import messagebox

# ------------------------------------------------------------
# Schachspiel mit stabiler En-Passant- und Schachmatt-Erkennung
# - Behält bestehende UI (gelbe Markierung, Rochade-Logik)
# - Fixes:
#   * En Passant nur im direkt folgenden Halbzug möglich (beidseitig)
#   * Keine "König schlagen"-Züge mehr (regelkonform)
#   * Schach/Schachmatt/Patt korrekt erkannt
#   * Rochaderechte pro Seite (kurz/lang) korrekt gepflegt
#   * Prüfungen auf Schach verwenden das Brett (kein veralteter King-Cache)
# ------------------------------------------------------------

class SchachSpiel:
    def __init__(self, root):
        self.root = root
        self.root.title("Schachspiel")
        
        self.controls_frame = tk.Frame(root)
        self.controls_frame.pack()

        self.player_color = tk.Label(self.controls_frame, text="", width=10, height=2, bg="white")
        self.player_color.grid(row=0, column=0)

        self.new_game_button = tk.Button(self.controls_frame, text="Neues Spiel", command=self.neues_spiel)
        self.new_game_button.grid(row=0, column=1)

        self.status_text = tk.Label(self.controls_frame, text="", width=20, height=2)
        self.status_text.grid(row=0, column=2)

        self.board_frame = tk.Frame(root)
        self.board_frame.pack()

        self.squares = {}
        self.create_board()
        self.neues_spiel()

        self.selected_piece = None
        self.valid_moves = []

    # ---------------- UI / Initialisierung --------------------
    def create_board(self):
        for row in range(8):
            for col in range(8):
                color = "white" if (row + col) % 2 == 0 else "gray"
                square = tk.Label(self.board_frame, width=8, height=4, bg=color, font=("Helvetica", 18))
                square.grid(row=row, column=col)
                square.bind("<Button-1>", lambda event, r=row, c=col: self.on_square_click(r, c))
                self.squares[(row, col)] = square

    def neues_spiel(self):
        self.current_player = "white"
        self.player_color.config(bg=self.current_player)
        self.initialize_pieces()
        self.status_text.config(text="")
        # Spielzustand
        self.game_over = False
        # En Passant: Ziel-Square + Ablauf (Halbzugnummer, nur im direkt folgenden Halbzug erlaubt)
        self.en_passant_target = None
        self.en_passant_expires = None
        # Halbzugzähler (0,1,2,...) — wird nach jedem Zug erhöht
        self.halfmove_clock = 0
        self.clear_highlight()

    def initialize_pieces(self):
        self.board = {}
        # Rochaderechte getrennt nach kurz (K) und lang (Q)
        self.castling_rights = {
            'white': {'K': True, 'Q': True},
            'black': {'K': True, 'Q': True}
        }

        for row in range(8):
            for col in range(8):
                self.board[(row, col)] = None

        piece_order = ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        for col, piece in enumerate(piece_order):
            self.board[(0, col)] = ('black', piece)
            self.board[(7, col)] = ('white', piece)
            self.board[(1, col)] = ('black', 'P')
            self.board[(6, col)] = ('white', 'P')

        self.update_board()

    def update_board(self):
        for (row, col), piece in self.board.items():
            square = self.squares[(row, col)]
            if piece:
                color, p_type = piece
                piece_symbol = self.get_piece_symbol(p_type, color)
                square.config(text=piece_symbol)
            else:
                square.config(text="")

    def get_piece_symbol(self, p_type, color):
        symbols = {
            'K': '♔' if color == 'white' else '♚',
            'Q': '♕' if color == 'white' else '♛',
            'R': '♖' if color == 'white' else '♜',
            'B': '♗' if color == 'white' else '♝',
            'N': '♘' if color == 'white' else '♞',
            'P': '♙' if color == 'white' else '♟'
        }
        return symbols[p_type]

    # ----------------- Eingabe-Handling -----------------------
    def on_square_click(self, row, col):
        if self.game_over:
            return

        piece = self.board[(row, col)]
        if self.selected_piece:
            if (row, col) in self.valid_moves:
                self.move_piece(self.selected_piece, (row, col))
                self.selected_piece = None
                self.clear_highlight()
                # Nach erfolgtem Zug Spieler wechseln und Status prüfen
                self.change_player()
            else:
                self.selected_piece = None
                self.clear_highlight()
        elif piece and piece[0] == self.current_player:
            self.selected_piece = (row, col)
            self.valid_moves = self.get_valid_moves(row, col)
            self.highlight_moves(self.valid_moves)

    # ----------------- Spielregeln / Züge ---------------------
    def move_piece(self, start, end):
        """Führt einen bereits als legal geprüften Zug aus."""
        piece = self.board[start]
        color, p_type = piece

        # Zielinhalt für Rochade-/Rechte- und KO-Logik merken
        target_before = self.board[end]

        # En Passant schlagen?
        en_passant_capture = False
        if p_type == 'P' and self.en_passant_target is not None and end == self.en_passant_target \
           and self.en_passant_expires == self.halfmove_clock:
            en_passant_capture = True

        # Ausführen
        self.board[start] = None
        self.board[end] = piece

        # En Passant: geschlagenen Bauern entfernen
        if en_passant_capture:
            captured_pos = (start[0], end[1])  # Bauer, der übersprungen wurde
            self.board[captured_pos] = None

        # Rochade-Zug? (König bewegt sich zwei Felder)
        if p_type == 'K' and abs(start[1] - end[1]) == 2:
            row = start[0]
            if end[1] == 6:  # kurze Rochade
                # Turm von H nach F
                self.board[(row, 5)] = self.board[(row, 7)]
                self.board[(row, 7)] = None
            elif end[1] == 2:  # lange Rochade
                # Turm von A nach D
                self.board[(row, 3)] = self.board[(row, 0)]
                self.board[(row, 0)] = None

        # Rochaderechte aktualisieren
        if p_type == 'K':
            # König gezogen -> beide Rechte weg
            self.castling_rights[color]['K'] = False
            self.castling_rights[color]['Q'] = False
        elif p_type == 'R':
            # Turm von Startfeld gezogen -> entsprechendes Recht weg
            if start == (7, 7):   # weisser H-Turm
                self.castling_rights['white']['K'] = False
            elif start == (7, 0): # weisser A-Turm
                self.castling_rights['white']['Q'] = False
            elif start == (0, 7): # schwarzer H-Turm
                self.castling_rights['black']['K'] = False
            elif start == (0, 0): # schwarzer A-Turm
                self.castling_rights['black']['Q'] = False

        # Falls ein Turm auf seinem Startfeld geschlagen wurde -> Recht der Gegenseite entfernen
        if target_before and target_before[1] == 'R':
            t_color = target_before[0]
            if end == (7, 7):
                self.castling_rights['white']['K'] = False
            elif end == (7, 0):
                self.castling_rights['white']['Q'] = False
            elif end == (0, 7):
                self.castling_rights['black']['K'] = False
            elif end == (0, 0):
                self.castling_rights['black']['Q'] = False

        # En Passant Ziel/Frist setzen oder löschen
        if p_type == 'P' and abs(end[0] - start[0]) == 2:
            # Zwischenfeld als Ziel, im nächsten Halbzug (jetzt: +1) gültig
            self.en_passant_target = ((start[0] + end[0]) // 2, start[1])
            self.en_passant_expires = self.halfmove_clock + 1
        else:
            # Wird nach dem Spielerwechsel formal bereinigt
            pass

        # Umwandlung (immer zur Dame, wie im Original)
        if p_type == 'P':
            if end[0] == 0 or end[0] == 7:
                self.board[end] = (color, 'Q')

        self.update_board()

    def get_valid_moves(self, row, col):
        piece = self.board[(row, col)]
        if not piece:
            return []

        color, p_type = piece
        moves = []

        if p_type == 'P':
            direction = -1 if color == 'white' else 1
            start_row = 6 if color == 'white' else 1

            # Vorwärts 1
            f1 = (row + direction, col)
            if self.is_on_board(*f1) and self.is_empty(f1):
                moves.append(f1)
                # Vorwärts 2 vom Start
                f2 = (row + 2 * direction, col)
                if row == start_row and self.is_empty(f2):
                    moves.append(f2)

            # Schlagen diagonal + En Passant
            for dc in [-1, 1]:
                target_row, target_col = row + direction, col + dc
                if self.is_on_board(target_row, target_col):
                    target_pos = (target_row, target_col)
                    # normales Schlagen (aber niemals König schlagen)
                    if self.is_enemy_piece(target_pos, color):
                        if self.board[target_pos][1] != 'K':
                            moves.append(target_pos)
                    # En Passant nur im direkt folgenden Halbzug
                    if (self.en_passant_target is not None and
                        self.en_passant_expires == self.halfmove_clock and
                        target_pos == self.en_passant_target):
                        moves.append(target_pos)

        elif p_type == 'R':
            moves += self.get_linear_moves(row, col, color, [(1, 0), (-1, 0), (0, 1), (0, -1)])
        
        elif p_type == 'N':
            knight_moves = [(2, 1), (2, -1), (-2, 1), (-2, -1),
                            (1, 2), (1, -2), (-1, 2), (-1, -2)]
            for dr, dc in knight_moves:
                new_row, new_col = row + dr, col + dc
                if self.is_on_board(new_row, new_col):
                    if self.is_empty((new_row, new_col)):
                        moves.append((new_row, new_col))
                    elif self.is_enemy_piece((new_row, new_col), color) and self.board[(new_row, new_col)][1] != 'K':
                        moves.append((new_row, new_col))

        elif p_type == 'B':
            moves += self.get_linear_moves(row, col, color, [(1, 1), (1, -1), (-1, 1), (-1, -1)])
        
        elif p_type == 'Q':
            moves += self.get_linear_moves(row, col, color, [(1, 0), (-1, 0), (0, 1), (0, -1),
                                                             (1, 1), (1, -1), (-1, 1), (-1, -1)])
        
        elif p_type == 'K':
            king_moves = [(1, 0), (-1, 0), (0, 1), (0, -1),
                          (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dr, dc in king_moves:
                new_row, new_col = row + dr, col + dc
                if self.is_on_board(new_row, new_col):
                    if self.is_empty((new_row, new_col)):
                        moves.append((new_row, new_col))
                    elif self.is_enemy_piece((new_row, new_col), color) and self.board[(new_row, new_col)][1] != 'K':
                        moves.append((new_row, new_col))
            # Rochade
            if self.can_castle_kingside(color):
                moves.append((row, col + 2))
            if self.can_castle_queenside(color):
                moves.append((row, col - 2))

        # Nur Züge behalten, die den eigenen König nicht im Schach lassen
        valid_moves = []
        for move in moves:
            board_copy = self.simulate_move((row, col), move)
            if not self.is_in_check_for_board(board_copy, color):
                valid_moves.append(move)

        return valid_moves

    def can_castle_kingside(self, color):
        # Rechte vorhanden?
        if not self.castling_rights[color]['K']:
            return False
        row = 7 if color == 'white' else 0
        # König und Turm vorhanden?
        if self.board[(row, 4)] != (color, 'K') or self.board[(row, 7)] != (color, 'R'):
            return False
        # Felder frei?
        if not self.is_empty((row, 5)) or not self.is_empty((row, 6)):
            return False
        # Felder nicht angegriffen (e,f,g)
        opponent = 'black' if color == 'white' else 'white'
        if self.is_square_attacked(self.board, (row, 4), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 5), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 6), opponent):
            return False
        return True

    def can_castle_queenside(self, color):
        # Rechte vorhanden?
        if not self.castling_rights[color]['Q']:
            return False
        row = 7 if color == 'white' else 0
        # König und Turm vorhanden?
        if self.board[(row, 4)] != (color, 'K') or self.board[(row, 0)] != (color, 'R'):
            return False
        # Felder frei?
        if not self.is_empty((row, 1)) or not self.is_empty((row, 2)) or not self.is_empty((row, 3)):
            return False
        # Felder nicht angegriffen (e,d,c)
        opponent = 'black' if color == 'white' else 'white'
        if self.is_square_attacked(self.board, (row, 4), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 3), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 2), opponent):
            return False
        return True

    def simulate_move(self, start_pos, end_pos):
        """Simuliert einen Zug auf einer flachen Kopie des Bretts (inkl. En Passant & Rochade-Königszug).
        Wichtig: Diese Funktion dient der Schachprüfung (keine Statusänderungen)."""
        board_copy = self.board.copy()
        piece = board_copy[start_pos]
        color, p_type = piece

        # En Passant in der Simulation berücksichtigen
        if p_type == 'P' and self.en_passant_target is not None and end_pos == self.en_passant_target \
           and self.en_passant_expires == self.halfmove_clock:
            # entferne den geschlagenen Bauern
            captured_pos = (start_pos[0], end_pos[1])
            board_copy[captured_pos] = None

        board_copy[end_pos] = piece
        board_copy[start_pos] = None

        # Rochade: Für Checkprüfung reicht es, nur den König zu bewegen
        # (die Unangreifbarkeit wird über Felder e/d/f/g geprüft)
        return board_copy

    def get_linear_moves(self, row, col, color, directions):
        moves = []
        for dr, dc in directions:
            r, c = row + dr, col + dc
            while self.is_on_board(r, c):
                if self.is_empty((r, c)):
                    moves.append((r, c))
                elif self.is_enemy_piece((r, c), color):
                    # König nie direkt schlagen
                    if self.board[(r, c)][1] != 'K':
                        moves.append((r, c))
                    break
                else:
                    break
                r += dr
                c += dc
        return moves

    # ----------------- Utilities ------------------------------
    def is_empty(self, position):
        return self.board.get(position) is None

    def is_enemy_piece(self, position, player_color):
        piece = self.board.get(position)
        return piece is not None and piece[0] != player_color

    def is_on_board(self, row, col):
        return 0 <= row < 8 and 0 <= col < 8

    def highlight_moves(self, moves):
        for row, col in moves:
            self.squares[(row, col)].config(bg="yellow")

    def clear_highlight(self):
        for row in range(8):
            for col in range(8):
                color = "white" if (row + col) % 2 == 0 else "gray"
                self.squares[(row, col)].config(bg=color)

    def change_player(self):
        # En-Passant-Ablauf prüfen/aufräumen (nach jedem abgeschlossenen Zug)
        self.halfmove_clock += 1
        if self.en_passant_expires is not None and self.en_passant_expires < self.halfmove_clock:
            self.en_passant_target = None
            self.en_passant_expires = None

        self.current_player = "black" if self.current_player == "white" else "white"
        self.player_color.config(bg=self.current_player)

        # Nach Seitenwechsel prüfen, ob die Seite am Zug im Schach/Matt/Patt ist
        if self.is_in_check(self.current_player):
            if self.is_checkmate(self.current_player):
                self.status_text.config(text="Schachmatt")
                self.game_over = True
                messagebox.showinfo("Spielende", f"Schachmatt – {('Weiss' if self.current_player=='white' else 'Schwarz')} ist matt.")
            else:
                self.status_text.config(text="Schach")
        else:
            if self.is_stalemate(self.current_player):
                self.status_text.config(text="Patt")
                self.game_over = True
                messagebox.showinfo("Spielende", "Patt – Unentschieden.")
            else:
                self.status_text.config(text="")

    # ----------------- Schach-/Matt-/Patt-Prüfungen -----------
    def find_king_for_board(self, board, color):
        for pos, piece in board.items():
            if piece == (color, 'K'):
                return pos
        return None

    def is_square_attacked(self, board, square, by_color):
        """Ist 'square' von 'by_color' angegriffen?"""
        for (row, col), piece in board.items():
            if piece and piece[0] == by_color:
                moves = self.get_valid_moves_for_board(board, row, col)
                if square in moves:
                    return True
        return False

    def is_in_check(self, color):
        return self.is_in_check_for_board(self.board, color)

    def is_in_check_for_board(self, board, color):
        king_position = self.find_king_for_board(board, color)
        if king_position is None:
            # Kein König gefunden: Zustand inkonsistent -> als "im Schach" behandeln,
            # damit solcher Zustand niemals als legal akzep­tiert wird.
            return True
        opponent_color = 'black' if color == 'white' else 'white'
        return self.is_square_attacked(board, king_position, opponent_color)

    def is_checkmate(self, color):
        if not self.is_in_check(color):
            return False
        # Hat die Seite am Zug irgendeinen legalen Zug?
        for (row, col), piece in self.board.items():
            if piece and piece[0] == color:
                for move in self.get_valid_moves(row, col):
                    # Mind. ein legaler Zug -> kein Matt
                    return False
        return True

    def is_stalemate(self, color):
        if self.is_in_check(color):
            return False
        # Keine legalen Züge -> Patt
        for (row, col), piece in self.board.items():
            if piece and piece[0] == color:
                if self.get_valid_moves(row, col):
                    return False
        return True

    # ----------------- Pseudo-legal (für Angriffe) ------------
    def get_valid_moves_for_board(self, board, row, col):
        """Pseudo-legale Züge (ohne eigene Schachprüfung).
        Wird ausschliesslich für Angriffsbestimmung verwendet (Check-Erkennung)."""
        piece = board[(row, col)]
        if not piece:
            return []

        color, p_type = piece
        moves = []

        if p_type == 'P':
            direction = -1 if color == 'white' else 1
            # Für Angriffe zählen nur Diagonalen
            for dc in [-1, 1]:
                r, c = row + direction, col + dc
                if 0 <= r < 8 and 0 <= c < 8:
                    # ein Bauer "bedroht" diese Diagonalen immer, egal ob belegt
                    moves.append((r, c))

        elif p_type == 'R':
            moves += self.get_linear_moves_for_board(board, row, col, color, [(1, 0), (-1, 0), (0, 1), (0, -1)])
        
        elif p_type == 'N':
            knight_moves = [(2, 1), (2, -1), (-2, 1), (-2, -1),
                            (1, 2), (1, -2), (-1, 2), (-1, -2)]
            for dr, dc in knight_moves:
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    moves.append((new_row, new_col))

        elif p_type == 'B':
            moves += self.get_linear_moves_for_board(board, row, col, color, [(1, 1), (1, -1), (-1, 1), (-1, -1)])

        elif p_type == 'Q':
            moves += self.get_linear_moves_for_board(board, row, col, color, [(1, 0), (-1, 0), (0, 1), (0, -1),
                                                                              (1, 1), (1, -1), (-1, 1), (-1, -1)])
        
        elif p_type == 'K':
            king_moves = [(1, 0), (-1, 0), (0, 1), (0, -1),
                          (1, 1), (1, -1), (-1, 1), (-1, -1)]
            for dr, dc in king_moves:
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    moves.append((new_row, new_col))
            
        return moves

    def get_linear_moves_for_board(self, board, row, col, color, directions):
        moves = []
        for dr, dc in directions:
            r, c = row + dr, col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                moves.append((r, c))
                if board.get((r, c)) is not None:
                    break  # blockiert
                r += dr
                c += dc
        return moves


if __name__ == "__main__":
    root = tk.Tk()
    game = SchachSpiel(root)
    root.mainloop()
