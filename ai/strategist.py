"""Agentische Orchestrierung der Zugauswahl in drei Phasen."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Sequence, Tuple

from engine.fen import export_fen, square_to_notation
from engine.game import ChessGame, Position

from .move_parser import IllegalMoveError, parse_move
from .provider import MoveGenerationProvider, MoveGenerationRequest
from telemetry import TelemetryLogger


@dataclass(slots=True)
class Candidate:
    """Repräsentiert einen von der KI vorgeschlagenen Zug."""

    raw: Any
    score: float
    move: Tuple[Position, Position] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Strategist:
    """Kapselt Analyse-, Scoring- und Entscheidungsphasen mit Telemetrie."""

    def __init__(
        self,
        provider: MoveGenerationProvider,
        *,
        telemetry: TelemetryLogger | None = None,
        max_retries: int = 2,
        backoff_initial: float = 0.5,
        backoff_factor: float = 2.0,
    ) -> None:
        self._provider = provider
        self.telemetry = telemetry or TelemetryLogger()
        self.max_retries = max_retries
        self.backoff_initial = backoff_initial
        self.backoff_factor = backoff_factor

    # ------------------------------------------------------------------
    # Öffentliche API
    def choose_move(
        self,
        game: ChessGame,
        *,
        history: Sequence[str] = (),
        instructions: str | None = None,
    ) -> Tuple[Position, Position]:
        """Ermittelt einen legalen Zug unter Nutzung der Engine-Validierung."""

        last_error: Exception | None = None
        backoff = self.backoff_initial
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            request = self._analyse(game, history=history, instructions=instructions)
            try:
                candidates = self._score_candidates(request)
                move = self._decide(request, candidates)
                return move
            except IllegalMoveError as exc:
                last_error = exc
                self._log(
                    "decision",
                    f"Ungültiger Kandidat in Versuch {attempt}: {exc}",
                    status="error",
                    metadata={"attempt": attempt},
                )
            except Exception:
                # Unerwartete Fehler sofort weitergeben
                raise

            if attempt >= attempts:
                break

            time.sleep(backoff)
            backoff *= self.backoff_factor

        raise RuntimeError("Strategist konnte keinen gültigen Zug bestimmen.") from last_error

    # ------------------------------------------------------------------
    # Phasen
    def _analyse(
        self,
        game: ChessGame,
        *,
        history: Sequence[str],
        instructions: str | None,
    ) -> MoveGenerationRequest:
        start = time.perf_counter()
        legal_moves = tuple(self._collect_legal_moves(game))
        request = MoveGenerationRequest(
            game=game,
            fen=export_fen(game),
            legal_moves=legal_moves,
            history=tuple(history),
            instructions=instructions,
        )
        duration = (time.perf_counter() - start) * 1000
        self._log(
            "analysis",
            "Analyse abgeschlossen",
            duration_ms=duration,
            metadata={"legal_moves": len(legal_moves)},
        )
        return request

    def _score_candidates(self, request: MoveGenerationRequest) -> List[Candidate]:
        start = time.perf_counter()
        raw_output = self._provider.generate_move(request)
        suggestions = list(self._normalise_provider_output(raw_output))
        candidates: List[Candidate] = []
        invalid = 0

        for suggestion in suggestions:
            candidate = Candidate(raw=suggestion, score=0.0)
            try:
                move = self._interpret_suggestion(suggestion, request)
            except IllegalMoveError as exc:
                candidate.metadata["error"] = str(exc)
                candidate.score = -1.0
                invalid += 1
            else:
                candidate.move = move
                candidate.metadata["notation"] = self._format_move(move)
                candidate.score = self._score_move(request.game, move)
            candidates.append(candidate)

        duration = (time.perf_counter() - start) * 1000
        self._log(
            "candidate_scoring",
            f"{len(candidates)} Kandidaten bewertet",
            duration_ms=duration,
            metadata={"invalid_candidates": invalid},
        )

        if not candidates:
            raise IllegalMoveError("Der Anbieter lieferte keine Zugkandidaten.")

        return candidates

    def _decide(
        self,
        request: MoveGenerationRequest,
        candidates: Sequence[Candidate],
    ) -> Tuple[Position, Position]:
        start = time.perf_counter()
        best = max(candidates, key=lambda candidate: candidate.score)
        if best.move is None:
            raise IllegalMoveError("Kein gültiger Zug unter den Kandidaten gefunden.")

        duration = (time.perf_counter() - start) * 1000
        self._log(
            "decision",
            f"Zug ausgewählt: {self._format_move(best.move)}",
            duration_ms=duration,
            metadata={"score": best.score},
        )
        return best.move

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    def _collect_legal_moves(self, game: ChessGame) -> Iterable[str]:
        for position, piece in game.board.items():
            if not piece:
                continue
            colour, _ = piece
            if colour != game.current_player:
                continue
            for target in game.get_valid_moves(*position):
                yield f"{square_to_notation(position)}{square_to_notation(target)}"

    def _normalise_provider_output(self, raw: Any) -> Iterable[Any]:
        if self._looks_like_move(raw):
            return [raw]
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            # Verhindere, dass Positionspaare auseinandergezogen werden
            if raw and self._looks_like_move(raw):
                return [raw]
            return list(raw)
        return [raw]

    def _looks_like_move(self, candidate: Any) -> bool:
        if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)):
            return False
        if len(candidate) != 2:
            return False
        return all(
            isinstance(part, Sequence)
            and not isinstance(part, (str, bytes))
            and len(part) == 2
            and all(isinstance(coord, int) for coord in part)
            for part in candidate
        )

    def _interpret_suggestion(
        self, suggestion: Any, request: MoveGenerationRequest
    ) -> Tuple[Position, Position]:
        if self._looks_like_move(suggestion):
            start = (int(suggestion[0][0]), int(suggestion[0][1]))
            end = (int(suggestion[1][0]), int(suggestion[1][1]))
            valid_targets = request.game.get_valid_moves(*start)
            if end not in valid_targets:
                raise IllegalMoveError(
                    "Der vorgeschlagene Zug ist nicht legal im aktuellen Zustand."
                )
            return start, end

        start_pos, end_pos = parse_move(
            request.game,
            suggestion,
            legal_moves=request.legal_moves,
        )
        return start_pos, end_pos

    def _score_move(self, game: ChessGame, move: Tuple[Position, Position]) -> float:
        _, end = move
        score = 1.0
        target_piece = game.board.get(end)
        if target_piece:
            score += 0.5
        row, col = end
        if 2 <= row <= 5 and 2 <= col <= 5:
            score += 0.1
        return score

    def _format_move(self, move: Tuple[Position, Position]) -> str:
        start, end = move
        return f"{square_to_notation(start)}{square_to_notation(end)}"

    def _log(
        self,
        phase: str,
        message: str,
        *,
        status: str = "info",
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.telemetry.record(
            phase=phase,
            message=message,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata,
        )


__all__ = ["Strategist", "Candidate"]
