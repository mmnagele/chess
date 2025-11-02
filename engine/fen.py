"""FEN-Import/-Export für den Schachmotor."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .game import ChessGame, Piece, Position

FILES = "abcdefgh"
PIECE_TO_CHAR = {
    ("white", "P"): "P",
    ("white", "N"): "N",
    ("white", "B"): "B",
    ("white", "R"): "R",
    ("white", "Q"): "Q",
    ("white", "K"): "K",
    ("black", "P"): "p",
    ("black", "N"): "n",
    ("black", "B"): "b",
    ("black", "R"): "r",
    ("black", "Q"): "q",
    ("black", "K"): "k",
}
CHAR_TO_PIECE: Dict[str, Piece] = {v: k for k, v in PIECE_TO_CHAR.items()}


def square_to_notation(position: Position) -> str:
    row, col = position
    return f"{FILES[col]}{8 - row}"


def notation_to_square(square: str) -> Position:
    if len(square) != 2 or square[0] not in FILES or square[1] not in "12345678":
        raise ValueError(f"Ungültiges Feld: {square}")
    col = FILES.index(square[0])
    row = 8 - int(square[1])
    return row, col


def export_fen(game: ChessGame) -> str:
    """Gibt die aktuelle Stellung des Spiels als FEN zurück."""

    ranks = []
    for row in range(8):
        empty = 0
        rank_parts = []
        for col in range(8):
            piece = game.board[(row, col)]
            if piece is None:
                empty += 1
            else:
                if empty:
                    rank_parts.append(str(empty))
                    empty = 0
                rank_parts.append(PIECE_TO_CHAR[piece])
        if empty:
            rank_parts.append(str(empty))
        ranks.append("".join(rank_parts))

    placement = "/".join(ranks)
    active_color = "w" if game.current_player == "white" else "b"

    castling = ""
    if game.castling_rights["white"]["K"]:
        castling += "K"
    if game.castling_rights["white"]["Q"]:
        castling += "Q"
    if game.castling_rights["black"]["K"]:
        castling += "k"
    if game.castling_rights["black"]["Q"]:
        castling += "q"
    castling = castling or "-"

    if (
        game.en_passant_target is not None
        and game.en_passant_expires is not None
        and game.en_passant_expires == game.turn_counter
    ):
        en_passant = square_to_notation(game.en_passant_target)
    else:
        en_passant = "-"

    return " ".join(
        [
            placement,
            active_color,
            castling,
            en_passant,
            str(game.halfmove_clock),
            str(game.fullmove_number),
        ]
    )


def import_fen(game: ChessGame, fen: str) -> None:
    """Lädt eine FEN in das bestehende Spielobjekt."""

    parts = fen.strip().split()
    if len(parts) != 6:
        raise ValueError("Eine FEN muss aus sechs Teilen bestehen.")

    placement, active_color, castling, en_passant, halfmove, fullmove = parts

    ranks = placement.split("/")
    if len(ranks) != 8:
        raise ValueError("Die Figurenaufstellung muss acht Reihen enthalten.")

    board: Dict[Position, Optional[Piece]] = {(row, col): None for row in range(8) for col in range(8)}

    for row, rank in enumerate(ranks):
        col = 0
        for char in rank:
            if char.isdigit():
                col += int(char)
                continue
            piece = CHAR_TO_PIECE.get(char)
            if piece is None:
                raise ValueError(f"Unbekanntes FEN-Zeichen: {char}")
            if col >= 8:
                raise ValueError("Zu viele Spalten in einer Reihe der FEN.")
            board[(row, col)] = piece
            col += 1
        if col != 8:
            raise ValueError("Eine Reihe der FEN enthält zu wenige Felder.")

    game.board = board

    game.current_player = "white" if active_color == "w" else "black"
    game.castling_rights = {
        "white": {"K": "K" in castling, "Q": "Q" in castling},
        "black": {"K": "k" in castling, "Q": "q" in castling},
    }

    game.fullmove_number = int(fullmove)
    game.halfmove_clock = int(halfmove)
    game.turn_counter = 2 * (game.fullmove_number - 1)
    if game.current_player == "black":
        game.turn_counter += 1

    if en_passant != "-":
        target = notation_to_square(en_passant)
        game.en_passant_target = target
        game.en_passant_expires = game.turn_counter
    else:
        game.en_passant_target = None
        game.en_passant_expires = None

    game.game_over = False
    game.status = None
    game.winner = None

    game._update_status()
