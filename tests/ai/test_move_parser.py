"""Tests für das Modul :mod:`ai.move_parser`."""

from __future__ import annotations

import json
from typing import Iterable

import pytest

from ai.move_parser import IllegalMoveError, parse_move
from engine import ChessGame


@pytest.fixture()
def pawn_game(chess_game: ChessGame) -> ChessGame:
    """Positioniert nur den weissen Königsbauern für einfachere Tests."""

    return chess_game


def _find_move(legal_moves: Iterable[str], notation: str) -> str:
    for move in legal_moves:
        if move == notation:
            return move
    raise AssertionError(f"{notation} nicht in legal_moves")


def test_parse_move_accepts_coordinate_string(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Verifiziert, dass eine legale Koordinatenangabe korrekt geparst wird."""

    move = _find_move(legal_move_notation, "e2e4")
    start, end = parse_move(pawn_game, move, legal_moves=tuple(legal_move_notation))
    assert start == (6, 4)
    assert end == (4, 4)


def test_parse_move_handles_json_payload(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Stellt sicher, dass verschachtelte JSON-Antworten verarbeitet werden."""

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


def test_parse_move_rejects_promotion(
    pawn_game: ChessGame, legal_move_notation: Iterable[str]
) -> None:
    """Bauernumwandlungen werden nicht unterstützt und müssen scheitern."""

    promotion_payload = {"move": "e7e8q"}
    with pytest.raises(IllegalMoveError):
        parse_move(pawn_game, promotion_payload, legal_moves=tuple(legal_move_notation))
