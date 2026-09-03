"""Regeltests für spezielle Schachsituationen."""

from engine import ChessGame
from engine.fen import import_fen


def test_en_passant_capture() -> None:
    game = ChessGame()
    game.apply_move((6, 4), (4, 4))  # e2 -> e4
    game.apply_move((1, 0), (3, 0))  # a7 -> a5
    game.apply_move((4, 4), (3, 4))  # e4 -> e5
    game.apply_move((1, 3), (3, 3))  # d7 -> d5 (Doppelschritt)

    legal_moves = game.get_valid_moves(3, 4)
    assert (2, 3) in legal_moves  # en passant verfügbar

    game.apply_move((3, 4), (2, 3))  # en passant schlagen

    assert game.board[(3, 3)] is None
    assert game.board[(2, 3)] == ("white", "P")


def test_white_kingside_castling() -> None:
    game = ChessGame()
    game.apply_move((6, 4), (4, 4))  # e2 -> e4
    game.apply_move((1, 0), (3, 0))  # a7 -> a5
    game.apply_move((7, 6), (5, 5))  # g1 -> f3
    game.apply_move((1, 7), (2, 7))  # h7 -> h6
    game.apply_move((7, 5), (6, 4))  # f1 -> e2
    game.apply_move((0, 1), (2, 0))  # b8 -> a6 (freier Zug)

    legal_moves = game.get_valid_moves(7, 4)
    assert (7, 6) in legal_moves  # kurze Rochade erlaubt

    game.apply_move((7, 4), (7, 6))  # kurze Rochade

    assert game.board[(7, 6)] == ("white", "K")
    assert game.board[(7, 5)] == ("white", "R")
    assert game.castling_rights["white"] == {"K": False, "Q": False}


def test_fools_mate_checkmate() -> None:
    game = ChessGame()
    game.apply_move((6, 5), (5, 5))  # f2 -> f3
    game.apply_move((1, 4), (3, 4))  # e7 -> e5
    game.apply_move((6, 6), (4, 6))  # g2 -> g4
    game.apply_move((0, 3), (4, 7))  # Dame d8 -> h4 (Matt)

    assert game.game_over is True
    assert game.status == "checkmate"
    assert game.winner == "black"


def test_import_stalemate() -> None:
    game = ChessGame()
    import_fen(game, "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")

    assert game.game_over is True
    assert game.status == "stalemate"
    assert game.winner is None
