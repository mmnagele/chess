"""Hilfsfunktionen zur Validierung von LLM-Zügen."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Mapping, Sequence, Tuple

from engine.game import ChessGame, Position

_FILES = "abcdefgh"
_MOVE_RE = re.compile(r"^[a-h][1-8][a-h][1-8](?:[qrbn])?$")
_MOVE_LINE_RE = re.compile(r"^\s*MOVE\s*:\s*([a-h][1-8][a-h][1-8](?:[qrbn])?)\s*$", re.IGNORECASE)
_FREE_MOVE_RE = re.compile(r"([a-h][1-8][a-h][1-8](?:[qrbn])?)", re.IGNORECASE)


class IllegalMoveError(ValueError):
    """Wird ausgelöst, wenn ein Vorschlag keinen legalen Zug darstellt."""


class _SuggestionDepthLimitError(ValueError):
    """Interner Fehler bei zu tiefer Verschachtelung."""


def parse_move(
    game: ChessGame,
    suggestion: Any,
    *,
    legal_moves: Sequence[str],
) -> Tuple[Position, Position]:
    """Parst einen LLM-Vorschlag und liefert ein legales Engine-Zugpaar zurück."""

    try:
        move_str = _normalise_suggestion(suggestion)
    except _SuggestionDepthLimitError as exc:
        raise IllegalMoveError(
            "Der Vorschlag ist zu tief verschachtelt und konnte nicht analysiert werden."
        ) from exc

    if not move_str:
        raise IllegalMoveError("Der Vorschlag enthält keinen Zug.")

    move_str = move_str.lower()
    normalised_candidates = {move.lower() for move in legal_moves}

    # Strip promotion suffix for validation since the engine auto-promotes.
    base_move = move_str[:4]
    if normalised_candidates and base_move not in normalised_candidates:
        raise IllegalMoveError(f"'{move_str}' ist kein zulässiger Zug.")

    start, end, _promotion = _split_move(move_str)
    if _promotion and _promotion != "q":
        raise IllegalMoveError(
            "Nur Damenumwandlung wird unterstützt. Verwende ein MOVE mit oder ohne 'q'."
        )

    start_pos = _algebraic_to_position(start)
    end_pos = _algebraic_to_position(end)

    valid_targets = game.get_valid_moves(*start_pos)
    if end_pos not in valid_targets:
        raise IllegalMoveError("Der vorgeschlagene Zug ist nicht legal im aktuellen Zustand.")

    return start_pos, end_pos


def _normalise_suggestion(suggestion: Any, _depth: int = 0) -> str:
    if _depth > 10:
        raise _SuggestionDepthLimitError

    if suggestion is None:
        return ""

    if isinstance(suggestion, str):
        text = suggestion.strip()
        if _MOVE_RE.match(text.lower()):
            return text

        for line in text.splitlines():
            match = _MOVE_LINE_RE.match(line)
            if match:
                return match.group(1)

        free_match = _FREE_MOVE_RE.search(text)
        if free_match:
            return free_match.group(1)

        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            return ""
        return _normalise_suggestion(candidate, _depth + 1)

    if isinstance(suggestion, Mapping):
        for key in ("move", "candidate", "best_move", "result", "output"):
            if key in suggestion:
                return _normalise_suggestion(suggestion[key], _depth + 1)
        from_square = suggestion.get("from") or suggestion.get("start")
        to_square = suggestion.get("to") or suggestion.get("end")
        if isinstance(from_square, str) and isinstance(to_square, str):
            candidate = f"{from_square}{to_square}"
            promotion = suggestion.get("promotion")
            if isinstance(promotion, str):
                candidate = f"{candidate}{promotion}"
            return candidate

    if isinstance(suggestion, Iterable) and not isinstance(suggestion, (str, bytes)):
        for item in suggestion:
            candidate = _normalise_suggestion(item, _depth + 1)
            if candidate:
                return candidate

    return ""


def _split_move(move: str) -> tuple[str, str, str | None]:
    if not _MOVE_RE.match(move):
        raise IllegalMoveError(f"'{move}' ist kein gültiges Koordinatenformat.")

    start, end = move[:2], move[2:4]
    promotion = move[4:] or None
    return start, end, promotion


def _algebraic_to_position(square: str) -> Position:
    file_char, rank_char = square[0], square[1]
    col = _FILES.index(file_char)
    row = 8 - int(rank_char)
    return (row, col)
