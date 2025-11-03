"""Tests für :mod:`engine.fen`."""

from __future__ import annotations

from engine import ChessGame
from engine.fen import export_fen, import_fen


def test_start_position_roundtrip() -> None:
    """Die Startstellung lässt sich verlustfrei exportieren und importieren."""

    game = ChessGame()
    fen = export_fen(game)
    restored = ChessGame()
    import_fen(restored, fen)
    assert restored.board == game.board
    assert restored.current_player == game.current_player
    assert restored.castling_rights == game.castling_rights
    assert export_fen(restored) == fen


def test_en_passant_roundtrip() -> None:
    """En-Passant-Rechte werden in der FEN korrekt kodiert."""

    game = ChessGame()
    game.apply_move((6, 4), (4, 4))  # e2 -> e4
    fen = export_fen(game)
    assert fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    restored = ChessGame()
    import_fen(restored, fen)
    assert restored.current_player == "black"
    assert restored.en_passant_target == (5, 4)
    assert restored.en_passant_expires == restored.turn_counter
    assert export_fen(restored) == fen
