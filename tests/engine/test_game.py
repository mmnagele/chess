"""Tests für :mod:`engine.game`."""

from __future__ import annotations

import pytest

import pytest

from engine import ChessGame


@pytest.fixture()
def game() -> ChessGame:
    """Stellt eine neue Partie in der Grundstellung bereit."""

    return ChessGame()


def test_reset_restores_start_position(game: ChessGame) -> None:
    """Nach einem ausgeführten Zug setzt ``reset`` das Brett zurück."""

    game.apply_move((6, 4), (4, 4))
    game.reset()
    assert game.current_player == "white"
    assert game.board[(6, 4)] == ("white", "P")
    assert game.board[(4, 4)] is None


def test_get_piece_symbol_returns_unicode(game: ChessGame) -> None:
    """Die Symboltabelle liefert unterschiedliche Unicode-Zeichen."""

    assert game.get_piece_symbol("K", "white") == "♔"
    assert game.get_piece_symbol("K", "black") == "♚"


def test_apply_move_switches_player(game: ChessGame) -> None:
    """Ein legaler Zug wechselt den Spieler und aktualisiert die Zähler."""

    result = game.apply_move((6, 4), (4, 4))
    assert result.current_player == "black"
    assert game.fullmove_number == 1
    assert game.turn_counter == 1


def test_apply_move_rejects_illegal_target(game: ChessGame) -> None:
    """Ein Zug auf ein ungültiges Feld löst eine :class:`ValueError` aus."""

    with pytest.raises(ValueError):
        game.apply_move((6, 4), (2, 4))


def test_get_valid_moves_filters_check_scenarios(game: ChessGame) -> None:
    """Züge, die den König im Schach lassen, werden herausgefiltert."""

    # Erzeuge eine Stellung mit schnellem Mattversuch.
    game.apply_move((6, 5), (4, 5))  # f2f4
    game.apply_move((1, 4), (3, 4))  # e7e5
    game.apply_move((7, 6), (5, 5))  # g1f3
    game.apply_move((0, 3), (4, 7))  # Dd8h4
    moves = game.get_valid_moves(7, 4)
    assert (7, 5) not in moves  # Rochade verboten im Schach


def test_castling_rights_update_after_rook_move(game: ChessGame) -> None:
    """Das Ziehen eines Turms entfernt die entsprechende Rochaderechte."""

    game.board[(6, 0)] = None  # Weg freiräumen
    game.apply_move((7, 0), (5, 0))
    assert game.castling_rights["white"]["Q"] is False


def test_en_passant_capture(game: ChessGame) -> None:
    """Ein En-Passant-Schlag entfernt den geschlagenen Bauern."""

    game.apply_move((6, 4), (4, 4))
    game.apply_move((1, 0), (3, 0))
    game.apply_move((4, 4), (3, 4))
    game.apply_move((1, 3), (3, 3))
    assert (2, 3) in game.get_valid_moves(3, 4)
    game.apply_move((3, 4), (2, 3))
    assert game.board[(3, 3)] is None
    assert game.board[(2, 3)] == ("white", "P")


def test_kingside_castling(game: ChessGame) -> None:
    """Nach der kurzen Rochade stehen König und Turm auf den Ziel-Feldern."""

    game.apply_move((6, 4), (4, 4))
    game.apply_move((1, 0), (3, 0))
    game.apply_move((7, 6), (5, 5))
    game.apply_move((1, 7), (2, 7))
    game.apply_move((7, 5), (6, 4))
    game.apply_move((0, 1), (2, 0))
    assert (7, 6) in game.get_valid_moves(7, 4)
    game.apply_move((7, 4), (7, 6))
    assert game.board[(7, 6)] == ("white", "K")
    assert game.board[(7, 5)] == ("white", "R")


def test_fools_mate_results_in_checkmate(game: ChessGame) -> None:
    """Das Narrenschach führt zum erwarteten Matt für Schwarz."""

    game.apply_move((6, 5), (5, 5))
    game.apply_move((1, 4), (3, 4))
    game.apply_move((6, 6), (4, 6))
    game.apply_move((0, 3), (4, 7))
    assert game.game_over is True
    assert game.status == "checkmate"
    assert game.winner == "black"


def test_imported_stalemate_detected(game: ChessGame) -> None:
    """Eine Patt-Stellung aus der FEN wird korrekt erkannt."""

    from engine.fen import import_fen

    import_fen(game, "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert game.game_over is True
    assert game.status == "stalemate"
    assert game.winner is None
