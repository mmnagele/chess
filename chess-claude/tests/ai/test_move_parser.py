"""Tests für das Modul :mod:`ai.move_parser`."""

from __future__ import annotations

import json
from collections.abc import Iterable

import pytest

from ai.move_parser import IllegalMoveError, parse_move
from engine import ChessGame


@pytest.fixture()
def pawn_game(chess_game: ChessGame) -> ChessGame:
    """Verwendet die Startposition für Parser-Tests."""

    return chess_game


def _find_move(legal_moves: Iterable[str], notation: str) -> str:
    for move in legal_moves:
        if move == notation:
            return move
    raise AssertionError(f"{notation} nicht in legal_moves")


def test_parse_move_accepts_coordinate_string(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Eine legale Koordinatenangabe wird korrekt geparst."""

    move = _find_move(legal_move_notation, "e2e4")
    start, end = parse_move(pawn_game, move, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_accepts_move_prefix_line(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Antworten im Contract-Format mit `MOVE:` werden erkannt."""

    text = "MOVE: e2e4\n\nSimple development move."
    start, end = parse_move(pawn_game, text, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_handles_json_payload(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Verschachtelte JSON-Antworten werden verarbeitet."""

    payload = json.dumps({"best_move": {"from": "e2", "to": "e4"}})
    start, end = parse_move(pawn_game, payload, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_rejects_illegal_suggestion(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Ein Zug ausserhalb der legalen Liste löst :class:`IllegalMoveError` aus."""

    with pytest.raises(IllegalMoveError):
        parse_move(pawn_game, "a1a3", legal_moves=tuple(legal_move_notation))


def test_parse_move_rejects_empty_string(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """An empty string raises IllegalMoveError."""

    with pytest.raises(IllegalMoveError):
        parse_move(pawn_game, "", legal_moves=tuple(legal_move_notation))


def test_parse_move_extracts_move_from_multiline_response(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """A multiline response with a MOVE: line is parsed correctly."""

    text = "Here is my analysis.\n\nMOVE: e2e4\n\nThis develops the center."
    start, end = parse_move(pawn_game, text, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_accepts_promotion_suffix_if_base_move_legal(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Promotion-Suffix ist erlaubt, sobald der Basismove legal ist."""

    move = _find_move(legal_move_notation, "e2e4")
    start, end = parse_move(pawn_game, f"{move}q", legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)
