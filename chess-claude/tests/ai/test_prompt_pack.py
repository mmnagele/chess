"""Tests for :mod:`ai.prompt_pack` template loading and rendering."""

from __future__ import annotations

import pytest

from ai.prompt_pack import load_prompt, render_prompt

# All prompt template files
_ALL_TEMPLATES = [
    "PLAYER_SYSTEM.md",
    "FORMAT_CONTRACT.md",
    "PLAYER_MOVE_USER_TEMPLATE.md",
    "PLAYER_CHAT_USER_TEMPLATE.md",
    "COMMENTATOR_SYSTEM_TOURNAMENT.md",
    "COMMENTATOR_SYSTEM_ADULT_COACH.md",
    "COMMENTATOR_SYSTEM_PARENT_CHILD.md",
    "COMMENTATOR_EVENT_USER_TEMPLATE.md",
    "COMMENTATOR_CHAT_USER_TEMPLATE.md",
    "RETRY_ILLEGAL_MOVE.md",
]


@pytest.mark.parametrize("name", _ALL_TEMPLATES)
def test_load_prompt_returns_non_empty_string(name: str) -> None:
    """Every prompt template loads as a non-empty string."""
    content = load_prompt(name)
    assert isinstance(content, str)
    assert len(content) > 0


def test_render_prompt_substitutes_all_placeholders() -> None:
    """render_prompt replaces all placeholders — no raw ``{`` left in output."""
    values = {
        "SIDE_TO_MOVE": "white",
        "FEN": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "MOVE_HISTORY": "1. e4 e5",
        "LAST_MOVE": "e7e5",
        "IN_CHECK": "no",
        "IS_CHECKMATE": "no",
        "IS_STALEMATE": "no",
        "LEGAL_MOVES": "d2d3, d2d4, e2e3, e2e4",
    }
    rendered = render_prompt("PLAYER_MOVE_USER_TEMPLATE.md", values)
    assert "{" not in rendered


def test_render_commentator_template() -> None:
    """Commentator event template renders correctly with all values."""
    values = {
        "COMMENTATOR_TYPE": "Adult Coach",
        "ADULT_SIDE": "White",
        "FEN_BEFORE": "start",
        "FEN_AFTER": "after",
        "LAST_MOVE": "e2e4",
        "MOVE_NUMBER": "1",
    }
    rendered = render_prompt("COMMENTATOR_EVENT_USER_TEMPLATE.md", values)
    assert "Adult Coach" in rendered
    assert "{" not in rendered


def test_load_prompt_missing_file_raises() -> None:
    """Loading a non-existent template raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_prompt("DOES_NOT_EXIST.md")
