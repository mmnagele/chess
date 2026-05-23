"""Tests für :mod:`ai.commentator`."""

from __future__ import annotations

from ai.commentator import Commentary, Commentator
from ai.provider import ChatRequest, ChatResponse
from telemetry import TelemetryLogger


class RecordingProvider:
    """Provider-Attrappe, die Anfragen speichert und Text zurückliefert."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.requests: list[ChatRequest] = []

    def generate_move(self, request):  # pragma: no cover - not used in this test
        raise NotImplementedError

    def chat(self, request: ChatRequest) -> ChatResponse:
        self.requests.append(request)
        return ChatResponse(raw_text=self.response_text)


def test_commentary_dataclass() -> None:
    """Commentary kapselt reinen Text."""

    commentary = Commentary(text="SUMMARY: Good move")
    assert commentary.text.startswith("SUMMARY")


def test_commentator_provides_commentary() -> None:
    """Automatische Commentary-Nachricht wird über den Provider geladen."""

    provider = RecordingProvider("SUMMARY: Solid move")
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())

    result = commentator.provide_commentary(
        commentator_type="Adult Coach",
        adult_side="White",
        fen_before="fen-before",
        fen_after="fen-after",
        last_move="e2e4",
        move_number=1,
        recent_moves=("White: P e2 -> e4",),
    )

    assert result.text == "SUMMARY: Solid move"
    assert provider.requests
    assert "MODE=COMMENTARY" in provider.requests[0].user_prompt
    assert "White: P e2 -> e4" in provider.requests[0].user_prompt


def test_commentator_chat() -> None:
    """Freier Chat nutzt MODE=CHAT-Kontext."""

    provider = RecordingProvider("Try developing your knight.")
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())

    result = commentator.chat(
        commentator_type="Tournament Commentator",
        fen="fen-state",
        user_message="What is the key idea?",
    )

    assert result.text == "Try developing your knight."
    assert "MODE=CHAT" in provider.requests[-1].user_prompt


def test_commentator_render_passthrough() -> None:
    """Render liefert den Kommentartext direkt."""

    provider = RecordingProvider("A")
    commentator = Commentator(provider=provider, telemetry=TelemetryLogger())
    assert commentator.render(Commentary(text="abc")) == "abc"
