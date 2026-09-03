"""Anthropic Claude basierter Heuristik-Adapter."""

from __future__ import annotations

from random import Random

from config import AnthropicSettings, load_anthropic_settings
from engine.game import Position

from .move_parser import parse_move
from .provider import MoveGenerationProvider, MoveGenerationRequest, ProviderConfig

PIECE_VALUES: dict[str, float] = {"K": 0.0, "Q": 9.0, "R": 5.0, "B": 3.0, "N": 3.0, "P": 1.0}


class AnthropicClient(MoveGenerationProvider):
    """Einfache Implementierung des :class:`MoveGenerationProvider` für Anthropic."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: AnthropicSettings | None = None,
        rng_seed: int | None = None,
    ) -> None:
        self._settings = settings or load_anthropic_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )
        seed = rng_seed if rng_seed is not None else hash(self.config.model) & 0xFFFFFFFF
        self._random = Random(seed)

    def generate_move(self, request: MoveGenerationRequest) -> tuple[Position, Position]:
        if not request.legal_moves:
            raise RuntimeError("Es stehen keine legalen Züge zur Verfügung.")

        scored = [self._score_candidate(move, request) for move in request.legal_moves]
        scored.sort(key=lambda item: item[0], reverse=True)

        best_score = scored[0][0]
        threshold = best_score - max(0.05, self.config.temperature * 0.3)
        pool = [move for score, move in scored if score >= threshold]

        if len(pool) == 1 or self.config.temperature <= 0.01:
            return pool[0]
        return self._random.choice(pool)

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    def _score_candidate(
        self, notation: str, request: MoveGenerationRequest
    ) -> tuple[float, tuple[Position, Position]]:
        start, end = parse_move(request.game, notation, legal_moves=request.legal_moves)
        score = self._score_move(request, start, end)
        return score, (start, end)

    def _score_move(self, request: MoveGenerationRequest, start: Position, end: Position) -> float:
        game = request.game
        piece = game.board.get(start)
        if piece is None:
            return float("-inf")

        color, p_type = piece
        score = 1.0

        target = game.board.get(end)
        if target is not None:
            score += 2.0 + PIECE_VALUES.get(target[1], 0.0)
        elif (
            p_type == "P"
            and game.en_passant_target == end
            and game.en_passant_expires == game.turn_counter
        ):
            score += 1.5

        score += self._centrality_bonus(end) * 0.6
        score += self._progress_bonus(color, start, end)
        score += self._development_bonus(color, p_type, start)

        if p_type == "P":
            score += self._pawn_structure_bonus(color, end)

        if request.instructions:
            score += min(0.5, len(request.instructions) / 200.0)

        return score

    def _centrality_bonus(self, position: Position) -> float:
        row, col = position
        return max(0.0, 1.0 - (abs(row - 3.5) + abs(col - 3.5)) / 6.0)

    def _progress_bonus(self, color: str, start: Position, end: Position) -> float:
        direction = -1 if color == "white" else 1
        return 0.3 * direction * (start[0] - end[0])

    def _development_bonus(self, color: str, piece: str, start: Position) -> float:
        if piece not in {"N", "B"}:
            return 0.0
        home_row = 7 if color == "white" else 0
        if start[0] == home_row:
            return 0.5
        return 0.0

    def _pawn_structure_bonus(self, color: str, end: Position) -> float:
        row, col = end
        central = 0.2 if col in (3, 4) else 0.0
        if color == "white":
            progress = max(0, 6 - row)
        else:
            progress = max(0, row - 1)
        return central + 0.04 * progress


__all__ = ["AnthropicClient"]
