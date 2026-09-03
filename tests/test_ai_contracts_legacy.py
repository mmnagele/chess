"""Contract-Tests für AI-Komponenten mit Golden-Files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pytest

from ai.commentator import Commentator, CommentaryPrompt
from engine import ChessGame
from engine.fen import export_fen
from telemetry import TelemetryLogger


class RecordingProvider:
    """Hilfsprovider, der ein Golden-Resultat zurückliefert."""

    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.last_prompt: CommentaryPrompt | None = None

    def generate_commentary(self, prompt: CommentaryPrompt) -> Mapping[str, object]:
        self.last_prompt = prompt
        return self.response


@pytest.fixture()
def sample_game() -> ChessGame:
    game = ChessGame()
    game.apply_move((6, 4), (4, 4))  # e2e4
    game.apply_move((1, 4), (3, 4))  # e7e5
    return game


@pytest.fixture()
def golden_dir() -> Path:
    return Path(__file__).parent / "golden"


def test_commentator_prompt_contains_fen(sample_game: ChessGame) -> None:
    commentator = Commentator(telemetry=TelemetryLogger())
    prompt = commentator.build_prompt(sample_game, history=("Weiss: B e2 → e4", "Schwarz: B e7 → e5"))
    fen = export_fen(sample_game)
    assert fen in prompt.user_message
    assert prompt.response_schema["type"] == "object"


def test_commentator_parses_golden_response(sample_game: ChessGame, golden_dir: Path) -> None:
    payload = json.loads((golden_dir / "commentary_response_valid.json").read_text(encoding="utf-8"))
    provider = RecordingProvider(payload)
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())
    commentary = commentator.provide_commentary(sample_game, history=("Weiss: B e2 → e4", "Schwarz: B e7 → e5"))
    assert commentary.variant_hint == payload["variant_hint"]
    assert commentary.eval_trend == payload["eval_trend"]
    assert commentary.key_ideas == tuple(payload["key_ideas"])
    assert commentary.blunders_last_moves == tuple(payload["blunders_last_moves"])


def test_commentator_rejects_invalid_response(sample_game: ChessGame, golden_dir: Path) -> None:
    payload = json.loads((golden_dir / "commentary_response_invalid.json").read_text(encoding="utf-8"))
    provider = RecordingProvider(payload)
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())
    with pytest.raises(ValueError):
        commentator.provide_commentary(sample_game, history=("Weiss: B e2 → e4",))
