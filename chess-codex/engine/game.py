"""Kernlogik für das Schachspiel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

Position = Tuple[int, int]
Piece = Tuple[str, str]  # (Farbe, Typ)

# Named constants for board geometry
_WHITE_BACK_RANK = 7
_BLACK_BACK_RANK = 0
_WHITE_PAWN_ROW = 6
_BLACK_PAWN_ROW = 1
_KING_COL = 4
_KS_ROOK_COL = 7  # kingside rook
_QS_ROOK_COL = 0  # queenside rook

_KNIGHT_OFFSETS: List[Tuple[int, int]] = [
    (2, 1),
    (2, -1),
    (-2, 1),
    (-2, -1),
    (1, 2),
    (1, -2),
    (-1, 2),
    (-1, -2),
]
_KING_OFFSETS: List[Tuple[int, int]] = [
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
]
_ROOK_DIRS: List[Tuple[int, int]] = [(1, 0), (-1, 0), (0, 1), (0, -1)]
_BISHOP_DIRS: List[Tuple[int, int]] = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
_QUEEN_DIRS: List[Tuple[int, int]] = _ROOK_DIRS + _BISHOP_DIRS


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
            self.board[(_BLACK_BACK_RANK, col)] = ("black", piece)
            self.board[(_WHITE_BACK_RANK, col)] = ("white", piece)
            self.board[(_BLACK_PAWN_ROW, col)] = ("black", "P")
            self.board[(_WHITE_PAWN_ROW, col)] = ("white", "P")

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
            "K": "\u2654" if color == "white" else "\u265a",
            "Q": "\u2655" if color == "white" else "\u265b",
            "R": "\u2656" if color == "white" else "\u265c",
            "B": "\u2657" if color == "white" else "\u265d",
            "N": "\u2658" if color == "white" else "\u265e",
            "P": "\u2659" if color == "white" else "\u265f",
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
        """Gibt alle legalen Züge für die Figur an (row, col) zurück."""

        piece = self.board.get((row, col))
        if not piece:
            return []

        color = piece[0]
        pseudo = self._pseudo_legal_moves(self.board, row, col, for_attacks=False)

        valid_moves: List[Position] = []
        for move in pseudo:
            board_copy = self._simulate_move(self.board, (row, col), move)
            if not self._is_in_check_for_board(board_copy, color):
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
                self.board[(row, 5)] = self.board[(row, _KS_ROOK_COL)]
                self.board[(row, _KS_ROOK_COL)] = None
            elif end[1] == 2:
                self.board[(row, 3)] = self.board[(row, _QS_ROOK_COL)]
                self.board[(row, _QS_ROOK_COL)] = None

        if p_type == "K":
            self.castling_rights[color]["K"] = False
            self.castling_rights[color]["Q"] = False
        elif p_type == "R":
            if start == (_WHITE_BACK_RANK, _KS_ROOK_COL):
                self.castling_rights["white"]["K"] = False
            elif start == (_WHITE_BACK_RANK, _QS_ROOK_COL):
                self.castling_rights["white"]["Q"] = False
            elif start == (_BLACK_BACK_RANK, _KS_ROOK_COL):
                self.castling_rights["black"]["K"] = False
            elif start == (_BLACK_BACK_RANK, _QS_ROOK_COL):
                self.castling_rights["black"]["Q"] = False

        if target_before and target_before[1] == "R":
            if end == (_WHITE_BACK_RANK, _KS_ROOK_COL):
                self.castling_rights["white"]["K"] = False
            elif end == (_WHITE_BACK_RANK, _QS_ROOK_COL):
                self.castling_rights["white"]["Q"] = False
            elif end == (_BLACK_BACK_RANK, _KS_ROOK_COL):
                self.castling_rights["black"]["K"] = False
            elif end == (_BLACK_BACK_RANK, _QS_ROOK_COL):
                self.castling_rights["black"]["Q"] = False

        if p_type == "P" and abs(end[0] - start[0]) == 2:
            self.en_passant_target = ((start[0] + end[0]) // 2, start[1])
            self.en_passant_expires = self.turn_counter + 1

        if p_type == "P" and (end[0] == _BLACK_BACK_RANK or end[0] == _WHITE_BACK_RANK):
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
        in_check = self._is_in_check_for_board(self.board, self.current_player)
        has_legal = self._has_any_legal_move(self.current_player)

        if in_check:
            if not has_legal:
                self.status = "checkmate"
                self.game_over = True
                self.winner = "white" if self.current_player == "black" else "black"
            else:
                self.status = "check"
        else:
            if not has_legal:
                self.status = "stalemate"
                self.game_over = True
            else:
                self.status = None

    # ----------------- Unified move generation ----------------------
    def _pseudo_legal_moves(
        self,
        board: Dict[Position, Optional[Piece]],
        row: int,
        col: int,
        *,
        for_attacks: bool,
    ) -> List[Position]:
        """Generate pseudo-legal moves for the piece at (row, col).

        When *for_attacks* is True, generates attack squares only (used for
        check detection — pawns emit diagonals unconditionally, pieces include
        squares occupied by friendly pieces).  When False, generates candidate
        moves for gameplay (pawns push forward, friendly-piece squares are
        excluded).
        """

        piece = board.get((row, col))
        if not piece:
            return []

        color, p_type = piece
        moves: List[Position] = []

        if p_type == "P":
            direction = -1 if color == "white" else 1
            if for_attacks:
                for dc in (-1, 1):
                    r, c = row + direction, col + dc
                    if 0 <= r < 8 and 0 <= c < 8:
                        moves.append((r, c))
            else:
                start_row = _WHITE_PAWN_ROW if color == "white" else _BLACK_PAWN_ROW
                forward_one = (row + direction, col)
                if _on_board(*forward_one) and board.get(forward_one) is None:
                    moves.append(forward_one)
                    forward_two = (row + 2 * direction, col)
                    if row == start_row and board.get(forward_two) is None:
                        moves.append(forward_two)
                for dc in (-1, 1):
                    tr, tc = row + direction, col + dc
                    if not _on_board(tr, tc):
                        continue
                    target_pos = (tr, tc)
                    target_piece = board.get(target_pos)
                    if target_piece is not None and target_piece[0] != color:
                        moves.append(target_pos)
                    if (
                        self.en_passant_target is not None
                        and self.en_passant_expires == self.turn_counter
                        and target_pos == self.en_passant_target
                    ):
                        moves.append(target_pos)

        elif p_type == "N":
            for dr, dc in _KNIGHT_OFFSETS:
                nr, nc = row + dr, col + dc
                if not _on_board(nr, nc):
                    continue
                target = (nr, nc)
                if for_attacks:
                    moves.append(target)
                else:
                    t = board.get(target)
                    if t is None or t[0] != color:
                        moves.append(target)

        elif p_type == "B":
            moves.extend(self._linear_moves(board, row, col, color, _BISHOP_DIRS, for_attacks))

        elif p_type == "R":
            moves.extend(self._linear_moves(board, row, col, color, _ROOK_DIRS, for_attacks))

        elif p_type == "Q":
            moves.extend(self._linear_moves(board, row, col, color, _QUEEN_DIRS, for_attacks))

        elif p_type == "K":
            for dr, dc in _KING_OFFSETS:
                nr, nc = row + dr, col + dc
                if not _on_board(nr, nc):
                    continue
                target = (nr, nc)
                if for_attacks:
                    moves.append(target)
                else:
                    t = board.get(target)
                    if t is None or t[0] != color:
                        moves.append(target)
            if not for_attacks:
                if self.can_castle_kingside(color):
                    moves.append((row, col + 2))
                if self.can_castle_queenside(color):
                    moves.append((row, col - 2))

        return moves

    def _linear_moves(
        self,
        board: Dict[Position, Optional[Piece]],
        row: int,
        col: int,
        color: str,
        directions: Iterable[Tuple[int, int]],
        for_attacks: bool,
    ) -> List[Position]:
        moves: List[Position] = []
        for dr, dc in directions:
            r, c = row + dr, col + dc
            while 0 <= r < 8 and 0 <= c < 8:
                target = (r, c)
                t = board.get(target)
                if t is None:
                    moves.append(target)
                else:
                    if for_attacks:
                        moves.append(target)
                    elif t[0] != color:
                        moves.append(target)
                    break
                r += dr
                c += dc
        return moves

    # ----------------- Check and mate detection ----------------------
    def _is_square_attacked(
        self, board: Dict[Position, Optional[Piece]], square: Position, by_color: str
    ) -> bool:
        for (row, col), piece in board.items():
            if piece and piece[0] == by_color:
                attacks = self._pseudo_legal_moves(board, row, col, for_attacks=True)
                if square in attacks:
                    return True
        return False

    def _is_in_check_for_board(self, board: Dict[Position, Optional[Piece]], color: str) -> bool:
        king_position = self._find_king(board, color)
        if king_position is None:
            return True
        opponent_color = "black" if color == "white" else "white"
        return self._is_square_attacked(board, king_position, opponent_color)

    def is_in_check(self, color: str) -> bool:
        return self._is_in_check_for_board(self.board, color)

    def is_checkmate(self, color: str) -> bool:
        if not self.is_in_check(color):
            return False
        return not self._has_any_legal_move(color)

    def is_stalemate(self, color: str) -> bool:
        if self.is_in_check(color):
            return False
        return not self._has_any_legal_move(color)

    def _has_any_legal_move(self, color: str) -> bool:
        """Return True as soon as any legal move is found (short-circuits)."""
        for (row, col), piece in self.board.items():
            if not piece or piece[0] != color:
                continue
            for move in self._pseudo_legal_moves(self.board, row, col, for_attacks=False):
                board_copy = self._simulate_move(self.board, (row, col), move)
                if not self._is_in_check_for_board(board_copy, color):
                    return True
        return False

    # ----------------- Simulation / helpers ----------------------
    def _simulate_move(
        self,
        board: Dict[Position, Optional[Piece]],
        start_pos: Position,
        end_pos: Position,
    ) -> Dict[Position, Optional[Piece]]:
        board_copy = board.copy()
        piece = board_copy[start_pos]
        if piece is None:
            return board_copy
        color, p_type = piece

        # En passant capture
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

        # Castling: also move the rook so king-safety check is accurate
        if p_type == "K" and abs(start_pos[1] - end_pos[1]) == 2:
            row = start_pos[0]
            if end_pos[1] == 6:  # kingside
                board_copy[(row, 5)] = board_copy.get((row, _KS_ROOK_COL))
                board_copy[(row, _KS_ROOK_COL)] = None
            elif end_pos[1] == 2:  # queenside
                board_copy[(row, 3)] = board_copy.get((row, _QS_ROOK_COL))
                board_copy[(row, _QS_ROOK_COL)] = None

        return board_copy

    @staticmethod
    def _find_king(board: Dict[Position, Optional[Piece]], color: str) -> Optional[Position]:
        for pos, piece in board.items():
            if piece == (color, "K"):
                return pos
        return None

    # ----------------- Castling ----------------------
    def can_castle_kingside(self, color: str) -> bool:
        if not self.castling_rights[color]["K"]:
            return False
        row = _WHITE_BACK_RANK if color == "white" else _BLACK_BACK_RANK
        if self.board[(row, _KING_COL)] != (color, "K") or self.board[(row, _KS_ROOK_COL)] != (
            color,
            "R",
        ):
            return False
        if not self._is_empty((row, 5)) or not self._is_empty((row, 6)):
            return False
        opponent = "black" if color == "white" else "white"
        for c in (_KING_COL, 5, 6):
            if self._is_square_attacked(self.board, (row, c), opponent):
                return False
        return True

    def can_castle_queenside(self, color: str) -> bool:
        if not self.castling_rights[color]["Q"]:
            return False
        row = _WHITE_BACK_RANK if color == "white" else _BLACK_BACK_RANK
        if self.board[(row, _KING_COL)] != (color, "K") or self.board[(row, _QS_ROOK_COL)] != (
            color,
            "R",
        ):
            return False
        if (
            not self._is_empty((row, 1))
            or not self._is_empty((row, 2))
            or not self._is_empty((row, 3))
        ):
            return False
        opponent = "black" if color == "white" else "white"
        for c in (_KING_COL, 3, 2):
            if self._is_square_attacked(self.board, (row, c), opponent):
                return False
        return True

    # ----------------- Utilities ----------------------
    def _is_empty(self, position: Position) -> bool:
        return self.board.get(position) is None

    # Legacy public aliases kept for external callers (ui, fen, tests)
    def is_empty(self, position: Position) -> bool:
        return self._is_empty(position)

    def is_enemy_piece(self, position: Position, player_color: str) -> bool:
        piece = self.board.get(position)
        return piece is not None and piece[0] != player_color

    def is_on_board(self, row: int, col: int) -> bool:
        return 0 <= row < 8 and 0 <= col < 8

    # Keep old public names working for callers that depend on them.
    def simulate_move(
        self, start_pos: Position, end_pos: Position
    ) -> Dict[Position, Optional[Piece]]:
        return self._simulate_move(self.board, start_pos, end_pos)

    def find_king_for_board(
        self, board: Dict[Position, Optional[Piece]], color: str
    ) -> Optional[Position]:
        return self._find_king(board, color)

    def is_square_attacked(
        self, board: Dict[Position, Optional[Piece]], square: Position, by_color: str
    ) -> bool:
        return self._is_square_attacked(board, square, by_color)

    def is_in_check_for_board(self, board: Dict[Position, Optional[Piece]], color: str) -> bool:
        return self._is_in_check_for_board(board, color)


def _on_board(row: int, col: int) -> bool:
    return 0 <= row < 8 and 0 <= col < 8
