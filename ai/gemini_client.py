"""Google Gemini basierter Heuristik-Adapter."""

from __future__ import annotations

from config import GeminiSettings, load_gemini_settings
from engine.game import Position

from .move_parser import parse_move
from .provider import MoveGenerationProvider, MoveGenerationRequest, ProviderConfig

PIECE_VALUES: dict[str, float] = {"K": 0.0, "Q": 9.0, "R": 5.0, "B": 3.0, "N": 3.0, "P": 1.0}


class GeminiClient(MoveGenerationProvider):
    """Heuristische Gemini-Implementierung für lokale Tests."""

    def __init__(
        self,
        *,
        config: ProviderConfig | None = None,
        settings: GeminiSettings | None = None,
    ) -> None:
        self._settings = settings or load_gemini_settings()
        self.config = config or ProviderConfig(
            model=self._settings.default_model,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
            timeout=self._settings.request_timeout,
        )

    def generate_move(self, request: MoveGenerationRequest) -> tuple[Position, Position]:
        if not request.legal_moves:
            raise RuntimeError("Es stehen keine legalen Züge zur Verfügung.")

        scored = [self._score_candidate(move, request) for move in request.legal_moves]
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

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

        score += 0.1 * len(game.get_valid_moves(*start))

        target = game.board.get(end)
        if target is not None:
            score += 1.8 + PIECE_VALUES.get(target[1], 0.0)
        elif (
            p_type == "P"
            and game.en_passant_target == end
            and game.en_passant_expires == game.turn_counter
        ):
            score += 1.0

        score += self._centrality_bonus(end) * 0.4
        score += self._progress_bonus(color, start, end)
        score += self._phase_bonus(len(request.history), p_type)
        score -= self._king_safety_penalty(color, p_type, start)

        return score

    def _centrality_bonus(self, position: Position) -> float:
        row, col = position
        return max(0.0, 1.0 - (abs(row - 3.5) + abs(col - 3.5)) / 6.0)

    def _progress_bonus(self, color: str, start: Position, end: Position) -> float:
        direction = -1 if color == "white" else 1
        return 0.2 * direction * (start[0] - end[0])

    def _phase_bonus(self, history_length: int, piece: str) -> float:
        if history_length < 6 and piece in {"N", "B"}:
            return 0.4
        if history_length > 30 and piece == "Q":
            return 0.2
        return 0.0

    def _king_safety_penalty(self, color: str, piece: str, start: Position) -> float:
        if piece != "P":
            return 0.0
        king_file = 4
        if color == "white" and start[0] >= 5 and abs(start[1] - king_file) <= 1:
            return 0.3
        if color == "black" and start[0] <= 2 and abs(start[1] - king_file) <= 1:
            return 0.3
        return 0.0


__all__ = ["GeminiClient"]
