"""Tests für das Modul :mod:`ai.move_parser`."""

from __future__ import annotations

import json
from typing import Iterable

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


def test_parse_move_accepts_promotion_suffix_if_base_move_legal(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Promotion-Suffix ist erlaubt, sobald der Basismove legal ist."""

    move = _find_move(legal_move_notation, "e2e4")
    start, end = parse_move(pawn_game, f"{move}q", legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_accepts_nested_list_and_mapping_payload(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    payload = [
        {"noise": "skip"},
        {"result": {"output": [{"candidate": "invalid"}, {"move": "MOVE: e2e4"}]}},
    ]
    start, end = parse_move(pawn_game, payload, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_accepts_uppercase_move_prefix(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    text = "move: E2E4\nReasonable center move."
    start, end = parse_move(pawn_game, text, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_rejects_non_queen_promotion_suffix(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    with pytest.raises(IllegalMoveError, match="Nur Damenumwandlung"):
        parse_move(pawn_game, "e2e4n", legal_moves=tuple(legal_move_notation))


def test_parse_move_reports_depth_limit(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    nested = "e2e4"
    for _ in range(12):
        nested = {"output": nested}

    with pytest.raises(IllegalMoveError, match="zu tief verschachtelt"):
        parse_move(pawn_game, nested, legal_moves=tuple(legal_move_notation))
