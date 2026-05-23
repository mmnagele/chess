"""Tests for :mod:`ai.prompt_pack`."""

from __future__ import annotations

import pytest

from ai.prompt_pack import load_prompt, render_prompt


def test_load_prompt_reads_known_template() -> None:
    content = load_prompt("PLAYER_SYSTEM.md")
    assert "You are a chess grandmaster" in content


@pytest.mark.parametrize(
    "template,values,expected_fragment",
    [
        (
            "PLAYER_MOVE_USER_TEMPLATE.md",
            {
                "SIDE_TO_MOVE": "White",
                "FEN": "startpos-fen",
                "MOVE_HISTORY": "[]",
                "LAST_MOVE": "none",
                "IN_CHECK": False,
                "IS_CHECKMATE": False,
                "IS_STALEMATE": False,
                "LEGAL_MOVES": "e2e4 g1f3",
            },
            "MODE=MOVE",
        ),
        (
            "PLAYER_CHAT_USER_TEMPLATE.md",
            {
                "SIDE_NAME": "White",
                "FEN": "startpos-fen",
                "USER_MESSAGE": "What is the plan?",
            },
            "MODE=CHAT",
        ),
        (
            "COMMENTATOR_EVENT_USER_TEMPLATE.md",
            {
                "COMMENTATOR_TYPE": "Adult Coach",
                "ADULT_SIDE": "White",
                "FEN_BEFORE": "fen-before",
                "FEN_AFTER": "fen-after",
                "LAST_MOVE": "e2e4",
                "MOVE_NUMBER": 1,
                "RECENT_MOVES": "White: P e2 -> e4",
            },
            "MODE=COMMENTARY",
        ),
        (
            "RETRY_ILLEGAL_MOVE.md",
            {
                "SIDE_TO_MOVE": "White",
                "ERROR_REASON": "not legal",
                "FEN": "fen",
                "MOVE_HISTORY": "White: P e2 -> e4",
                "LAST_MOVE": "e2e4",
                "LEGAL_MOVES": "e2e4",
            },
            "Your previous move was invalid",
        ),
    ],
)
def test_render_prompt_handles_typical_inputs(
    template: str,
    values: dict[str, object],
    expected_fragment: str,
) -> None:
    rendered = render_prompt(template, values)
    assert expected_fragment in rendered
    assert rendered.strip()
