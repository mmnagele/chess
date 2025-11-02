"""Kernlogik für das Schachspiel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

Position = Tuple[int, int]
Piece = Tuple[str, str]  # (Farbe, Typ)


@dataclass
class MoveResult:
    """Repräsentiert das Ergebnis eines ausgeführten Zugs."""

    status: Optional[str]
    game_over: bool
    current_player: str
    winner: Optional[str]
    in_check: bool
    just_finished: bool


class ChessGame:
    """Verwaltet die Spielregeln und den Spielzustand."""

    def __init__(self) -> None:
        self.board: Dict[Position, Optional[Piece]] = {}
        self.castling_rights: Dict[str, Dict[str, bool]] = {}
        self.current_player: str = "white"
        self.en_passant_target: Optional[Position] = None
        self.en_passant_expires: Optional[int] = None
        self.turn_counter: int = 0
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self.game_over: bool = False
        self.status: Optional[str] = None
        self.winner: Optional[str] = None
        self.reset()

    # ---------------- Initialisierung -----------------
    def reset(self) -> None:
        """Setzt das Spiel auf die Anfangsposition zurück."""

        self.board = {(row, col): None for row in range(8) for col in range(8)}
        piece_order = ["R", "N", "B", "Q", "K", "B", "N", "R"]
        for col, piece in enumerate(piece_order):
            self.board[(0, col)] = ("black", piece)
            self.board[(7, col)] = ("white", piece)
            self.board[(1, col)] = ("black", "P")
            self.board[(6, col)] = ("white", "P")

        self.castling_rights = {
            "white": {"K": True, "Q": True},
            "black": {"K": True, "Q": True},
        }
        self.current_player = "white"
        self.en_passant_target = None
        self.en_passant_expires = None
        self.turn_counter = 0
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self.game_over = False
        self.status = None
        self.winner = None

    # ---------------- Öffentliche API -----------------
    def get_piece_symbol(self, p_type: str, color: str) -> str:
        symbols = {
            "K": "♔" if color == "white" else "♚",
            "Q": "♕" if color == "white" else "♛",
            "R": "♖" if color == "white" else "♜",
            "B": "♗" if color == "white" else "♝",
            "N": "♘" if color == "white" else "♞",
            "P": "♙" if color == "white" else "♟",
        }
        return symbols[p_type]

    def apply_move(self, start: Position, end: Position) -> MoveResult:
        """Prüft und führt einen Zug aus."""

        if self.game_over:
            raise ValueError("Das Spiel ist bereits beendet.")

        piece = self.board.get(start)
        if piece is None:
            raise ValueError("Am Startfeld befindet sich keine Figur.")
        color, p_type = piece
        if color != self.current_player:
            raise ValueError("Die ausgewählte Figur gehört nicht dem Spieler am Zug.")

        valid_moves = self.get_valid_moves(*start)
        if end not in valid_moves:
            raise ValueError("Der Zug ist nicht legal.")

        capture = self.board.get(end) is not None
        en_passant_capture = (
            p_type == "P"
            and self.en_passant_target is not None
            and end == self.en_passant_target
            and self.en_passant_expires == self.turn_counter
        )
        if en_passant_capture:
            capture = True

        self._move_piece(start, end)

        if p_type == "P" or capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        previous_game_over = self.game_over
        self._switch_player()
        self._update_status()

        return MoveResult(
            status=self.status,
            game_over=self.game_over,
            current_player=self.current_player,
            winner=self.winner,
            in_check=self.status == "check",
            just_finished=self.game_over and not previous_game_over,
        )

    def get_valid_moves(self, row: int, col: int) -> List[Position]:
        piece = self.board.get((row, col))
        if not piece:
            return []

        color, p_type = piece
        moves: List[Position] = []

        if p_type == "P":
            direction = -1 if color == "white" else 1
            start_row = 6 if color == "white" else 1

            forward_one = (row + direction, col)
            if self.is_on_board(*forward_one) and self.is_empty(forward_one):
                moves.append(forward_one)
                forward_two = (row + 2 * direction, col)
                if row == start_row and self.is_empty(forward_two):
                    moves.append(forward_two)

            for dc in (-1, 1):
                target_row, target_col = row + direction, col + dc
                if not self.is_on_board(target_row, target_col):
                    continue
                target_pos = (target_row, target_col)
                if self.is_enemy_piece(target_pos, color):
                    if self.board[target_pos][1] != "K":
                        moves.append(target_pos)
                if (
                    self.en_passant_target is not None
                    and self.en_passant_expires == self.turn_counter
                    and target_pos == self.en_passant_target
                ):
                    moves.append(target_pos)

        elif p_type == "R":
            moves.extend(
                self.get_linear_moves(row, col, color, [(1, 0), (-1, 0), (0, 1), (0, -1)])
            )

        elif p_type == "N":
            knight_moves = [
                (2, 1),
                (2, -1),
                (-2, 1),
                (-2, -1),
                (1, 2),
                (1, -2),
                (-1, 2),
                (-1, -2),
            ]
            for dr, dc in knight_moves:
                new_row, new_col = row + dr, col + dc
                if not self.is_on_board(new_row, new_col):
                    continue
                target = (new_row, new_col)
                if self.is_empty(target):
                    moves.append(target)
                elif self.is_enemy_piece(target, color) and self.board[target][1] != "K":
                    moves.append(target)

        elif p_type == "B":
            moves.extend(
                self.get_linear_moves(
                    row, col, color, [(1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            )

        elif p_type == "Q":
            moves.extend(
                self.get_linear_moves(
                    row,
                    col,
                    color,
                    [
                        (1, 0),
                        (-1, 0),
                        (0, 1),
                        (0, -1),
                        (1, 1),
                        (1, -1),
                        (-1, 1),
                        (-1, -1),
                    ],
                )
            )

        elif p_type == "K":
            king_moves = [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]
            for dr, dc in king_moves:
                new_row, new_col = row + dr, col + dc
                if not self.is_on_board(new_row, new_col):
                    continue
                target = (new_row, new_col)
                if self.is_empty(target):
                    moves.append(target)
                elif self.is_enemy_piece(target, color) and self.board[target][1] != "K":
                    moves.append(target)
            if self.can_castle_kingside(color):
                moves.append((row, col + 2))
            if self.can_castle_queenside(color):
                moves.append((row, col - 2))

        valid_moves: List[Position] = []
        for move in moves:
            board_copy = self.simulate_move((row, col), move)
            if not self.is_in_check_for_board(board_copy, color):
                valid_moves.append(move)

        return valid_moves

    # ---------------- Zugausführung --------------------
    def _move_piece(self, start: Position, end: Position) -> None:
        piece = self.board[start]
        if piece is None:
            raise ValueError("Ungültiger Startzug.")
        color, p_type = piece
        target_before = self.board[end]

        en_passant_capture = (
            p_type == "P"
            and self.en_passant_target is not None
            and end == self.en_passant_target
            and self.en_passant_expires == self.turn_counter
        )

        self.board[start] = None
        self.board[end] = piece

        if en_passant_capture:
            captured_pos = (start[0], end[1])
            self.board[captured_pos] = None

        if p_type == "K" and abs(start[1] - end[1]) == 2:
            row = start[0]
            if end[1] == 6:
                self.board[(row, 5)] = self.board[(row, 7)]
                self.board[(row, 7)] = None
            elif end[1] == 2:
                self.board[(row, 3)] = self.board[(row, 0)]
                self.board[(row, 0)] = None

        if p_type == "K":
            self.castling_rights[color]["K"] = False
            self.castling_rights[color]["Q"] = False
        elif p_type == "R":
            if start == (7, 7):
                self.castling_rights["white"]["K"] = False
            elif start == (7, 0):
                self.castling_rights["white"]["Q"] = False
            elif start == (0, 7):
                self.castling_rights["black"]["K"] = False
            elif start == (0, 0):
                self.castling_rights["black"]["Q"] = False

        if target_before and target_before[1] == "R":
            t_color = target_before[0]
            if end == (7, 7):
                self.castling_rights["white"]["K"] = False
            elif end == (7, 0):
                self.castling_rights["white"]["Q"] = False
            elif end == (0, 7):
                self.castling_rights["black"]["K"] = False
            elif end == (0, 0):
                self.castling_rights["black"]["Q"] = False

        if p_type == "P" and abs(end[0] - start[0]) == 2:
            self.en_passant_target = ((start[0] + end[0]) // 2, start[1])
            self.en_passant_expires = self.turn_counter + 1
        else:
            # En-Passant-Rechte bleiben bestehen, bis sie ablaufen
            pass

        if p_type == "P" and (end[0] == 0 or end[0] == 7):
            self.board[end] = (color, "Q")

    def _switch_player(self) -> None:
        self.turn_counter += 1
        if self.en_passant_expires is not None and self.en_passant_expires < self.turn_counter:
            self.en_passant_target = None
            self.en_passant_expires = None

        if self.current_player == "white":
            self.current_player = "black"
        else:
            self.current_player = "white"
            self.fullmove_number += 1

    def _update_status(self) -> None:
        self.game_over = False
        self.winner = None
        if self.is_in_check(self.current_player):
            if self.is_checkmate(self.current_player):
                self.status = "checkmate"
                self.game_over = True
                self.winner = "white" if self.current_player == "black" else "black"
            else:
                self.status = "check"
        else:
            if self.is_stalemate(self.current_player):
                self.status = "stalemate"
                self.game_over = True
            else:
                self.status = None

    # ----------------- Utilities ----------------------
    def is_empty(self, position: Position) -> bool:
        return self.board.get(position) is None

    def is_enemy_piece(self, position: Position, player_color: str) -> bool:
        piece = self.board.get(position)
        return piece is not None and piece[0] != player_color

    def is_on_board(self, row: int, col: int) -> bool:
        return 0 <= row < 8 and 0 <= col < 8

    def get_linear_moves(
        self,
        row: int,
        col: int,
        color: str,
        directions: Iterable[Tuple[int, int]],
    ) -> List[Position]:
        moves: List[Position] = []
        for dr, dc in directions:
            r, c = row + dr, col + dc
            while self.is_on_board(r, c):
                target = (r, c)
                if self.is_empty(target):
                    moves.append(target)
                elif self.is_enemy_piece(target, color):
                    if self.board[target][1] != "K":
                        moves.append(target)
                    break
                else:
                    break
                r += dr
                c += dc
        return moves

    def can_castle_kingside(self, color: str) -> bool:
        if not self.castling_rights[color]["K"]:
            return False
        row = 7 if color == "white" else 0
        if self.board[(row, 4)] != (color, "K") or self.board[(row, 7)] != (color, "R"):
            return False
        if not self.is_empty((row, 5)) or not self.is_empty((row, 6)):
            return False
        opponent = "black" if color == "white" else "white"
        if self.is_square_attacked(self.board, (row, 4), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 5), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 6), opponent):
            return False
        return True

    def can_castle_queenside(self, color: str) -> bool:
        if not self.castling_rights[color]["Q"]:
            return False
        row = 7 if color == "white" else 0
        if self.board[(row, 4)] != (color, "K") or self.board[(row, 0)] != (color, "R"):
            return False
        if not self.is_empty((row, 1)) or not self.is_empty((row, 2)) or not self.is_empty((row, 3)):
            return False
        opponent = "black" if color == "white" else "white"
        if self.is_square_attacked(self.board, (row, 4), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 3), opponent):
            return False
        if self.is_square_attacked(self.board, (row, 2), opponent):
            return False
        return True

    def simulate_move(self, start_pos: Position, end_pos: Position) -> Dict[Position, Optional[Piece]]:
        board_copy = self.board.copy()
        piece = board_copy[start_pos]
        if piece is None:
            return board_copy
        color, p_type = piece

        if (
            p_type == "P"
            and self.en_passant_target is not None
            and end_pos == self.en_passant_target
            and self.en_passant_expires == self.turn_counter
        ):
            captured_pos = (start_pos[0], end_pos[1])
            board_copy[captured_pos] = None

        board_copy[end_pos] = piece
        board_copy[start_pos] = None
        return board_copy

    def find_king_for_board(self, board: Dict[Position, Optional[Piece]], color: str) -> Optional[Position]:
        for pos, piece in board.items():
            if piece == (color, "K"):
                return pos
        return None

    def is_square_attacked(
        self, board: Dict[Position, Optional[Piece]], square: Position, by_color: str
    ) -> bool:
        for (row, col), piece in board.items():
            if piece and piece[0] == by_color:
                moves = self.get_valid_moves_for_board(board, row, col)
                if square in moves:
                    return True
        return False

    def is_in_check(self, color: str) -> bool:
        return self.is_in_check_for_board(self.board, color)

    def is_in_check_for_board(
        self, board: Dict[Position, Optional[Piece]], color: str
    ) -> bool:
        king_position = self.find_king_for_board(board, color)
        if king_position is None:
            return True
        opponent_color = "black" if color == "white" else "white"
        return self.is_square_attacked(board, king_position, opponent_color)

    def is_checkmate(self, color: str) -> bool:
        if not self.is_in_check(color):
            return False
        for (row, col), piece in self.board.items():
            if piece and piece[0] == color:
                for move in self.get_valid_moves(row, col):
                    return False
        return True

    def is_stalemate(self, color: str) -> bool:
        if self.is_in_check(color):
            return False
        for (row, col), piece in self.board.items():
            if piece and piece[0] == color and self.get_valid_moves(row, col):
                return False
        return True

    def get_valid_moves_for_board(
        self, board: Dict[Position, Optional[Piece]], row: int, col: int
    ) -> List[Position]:
        piece = board[(row, col)]
        if not piece:
            return []

        color, p_type = piece
        moves: List[Position] = []

        if p_type == "P":
            direction = -1 if color == "white" else 1
            for dc in (-1, 1):
                r, c = row + direction, col + dc
                if 0 <= r < 8 and 0 <= c < 8:
                    moves.append((r, c))

        elif p_type == "R":
            moves.extend(
                self.get_linear_moves_for_board(
                    board, row, col, [(1, 0), (-1, 0), (0, 1), (0, -1)]
                )
            )

        elif p_type == "N":
            knight_moves = [
                (2, 1),
                (2, -1),
                (-2, 1),
                (-2, -1),
                (1, 2),
                (1, -2),
                (-1, 2),
                (-1, -2),
            ]
            for dr, dc in knight_moves:
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    moves.append((new_row, new_col))

        elif p_type == "B":
            moves.extend(
                self.get_linear_moves_for_board(
                    board, row, col, [(1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            )

        elif p_type == "Q":
            moves.extend(
                self.get_linear_moves_for_board(
                    board,
                    row,
                    col,
                    [
                        (1, 0),
                        (-1, 0),
                        (0, 1),
                        (0, -1),
                        (1, 1),
                        (1, -1),
                        (-1, 1),
                        (-1, -1),
                    ],
                )
            )

        elif p_type == "K":
            king_moves = [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]
            for dr, dc in king_moves:
                new_row, new_col = row + dr, col + dc
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    moves.append((new_row, new_col))

        return moves

    def get_linear_moves_for_board(
        self,
        board: Dict[Position, Optional[Piece]],
        row: int,
        col: int,
        directions: Iterable[Tuple[int, int]],
    ) -> List[Position]:
        moves: List[Position] = []
        for dr, dc in directions:
            r, c = row + dr, col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                moves.append((r, c))
                if board.get((r, c)) is not None:
                    break
                r += dr
                c += dc
        return moves
