"""Orchestrierung der Zugauswahl mit Prompt-Pack und Retry-Logik."""

from __future__ import annotations

import time
from typing import Sequence

from engine.fen import export_fen, square_to_notation
from engine.game import ChessGame
from telemetry import TelemetryLogger

from .move_parser import IllegalMoveError, parse_move
from .prompt_pack import load_prompt, render_prompt
from .provider import MoveGenerationProvider, MoveGenerationRequest, MoveSuggestion


class Strategist:
    """Kapselt Prompt-Erstellung, Provider-Aufruf und Legalitätsprüfung."""

    def __init__(
        self,
        provider: MoveGenerationProvider,
        *,
        telemetry: TelemetryLogger | None = None,
        max_retries: int = 2,
        backoff_initial: float = 0.4,
        backoff_factor: float = 2.0,
        total_timeout_seconds: float = 60.0,
    ) -> None:
        self._provider = provider
        self.telemetry = telemetry or TelemetryLogger()
        self.max_retries = max_retries
        self.backoff_initial = backoff_initial
        self.backoff_factor = backoff_factor
        self.total_timeout_seconds = max(0.1, float(total_timeout_seconds))

    def choose_move(
        self,
        game: ChessGame,
        *,
        history: Sequence[str] = (),
    ) -> MoveSuggestion:
        """Ermittelt einen legalen Zug und liefert den validierten Vorschlag zurück."""

        legal_moves = tuple(self._collect_legal_moves(game))
        if not legal_moves:
            raise RuntimeError("Es stehen keine legalen Züge zur Verfügung.")

        side_to_move = "White" if game.current_player == "white" else "Black"
        last_move = history[-1] if history else "-"
        fen = export_fen(game)

        system_prompt = "\n\n".join(
            [load_prompt("PLAYER_SYSTEM.md"), load_prompt("FORMAT_CONTRACT.md")]
        )

        last_error: Exception | None = None
        start_time = time.monotonic()
        backoff = self.backoff_initial
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            remaining = self._remaining_seconds(start_time)
            if remaining <= 0:
                message = (
                    f"Strategist timed out after {self.total_timeout_seconds:.1f}s "
                    f"while searching for a legal move."
                )
                self._log(
                    "decision",
                    message,
                    status="error",
                    metadata={"attempt": attempt - 1},
                )
                raise RuntimeError(message) from last_error

            if attempt == 1:
                user_prompt = render_prompt(
                    "PLAYER_MOVE_USER_TEMPLATE.md",
                    {
                        "SIDE_TO_MOVE": side_to_move,
                        "FEN": fen,
                        "MOVE_HISTORY": "\n".join(history) if history else "-",
                        "LAST_MOVE": last_move,
                        "IN_CHECK": str(game.status == "check"),
                        "IS_CHECKMATE": str(game.status == "checkmate"),
                        "IS_STALEMATE": str(game.status == "stalemate"),
                        "LEGAL_MOVES": ", ".join(legal_moves),
                    },
                )
            else:
                user_prompt = render_prompt(
                    "RETRY_ILLEGAL_MOVE.md",
                    {
                        "SIDE_TO_MOVE": side_to_move,
                        "ERROR_REASON": str(last_error) if last_error else "illegal move",
                        "FEN": fen,
                        "MOVE_HISTORY": "\n".join(history) if history else "-",
                        "LAST_MOVE": last_move,
                        "LEGAL_MOVES": ", ".join(legal_moves),
                    },
                )

            request = MoveGenerationRequest(
                game=game,
                fen=fen,
                legal_moves=legal_moves,
                history=tuple(history),
                side_to_move=game.current_player,
                last_move=last_move,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            self._log(
                "analysis",
                f"MOVE Prompt gesendet (Versuch {attempt}/{attempts})",
                metadata={
                    "legal_moves": len(legal_moves),
                    "remaining_s": round(remaining, 3),
                },
            )

            original_timeout = self._override_provider_timeout(remaining)
            try:
                response = self._provider.generate_move(request)
                start, end = parse_move(
                    game,
                    response.raw_text,
                    legal_moves=legal_moves,
                )
                move_text = f"{square_to_notation(start)}{square_to_notation(end)}"
                self._log(
                    "decision",
                    f"Legaler Zug gewählt: {move_text}",
                    metadata={"attempt": attempt},
                )
                return MoveSuggestion(
                    start=start,
                    end=end,
                    move_text=move_text,
                    raw_response=response.raw_text,
                )
            except (IllegalMoveError, RuntimeError) as exc:
                last_error = exc
                self._log(
                    "decision",
                    f"Ungültiger Kandidat in Versuch {attempt}: {exc}",
                    status="error",
                    metadata={"attempt": attempt},
                )
                if attempt < attempts:
                    remaining_after_error = self._remaining_seconds(start_time)
                    if remaining_after_error <= 0:
                        continue
                    sleep_seconds = min(backoff, remaining_after_error)
                    time.sleep(sleep_seconds)
                    backoff *= self.backoff_factor
            finally:
                self._restore_provider_timeout(original_timeout)

        if self._remaining_seconds(start_time) <= 0:
            message = (
                f"Strategist timed out after {self.total_timeout_seconds:.1f}s "
                f"while searching for a legal move."
            )
            raise RuntimeError(message) from last_error

        raise RuntimeError("Strategist konnte keinen gültigen Zug bestimmen.") from last_error

    def _remaining_seconds(self, start_time: float) -> float:
        elapsed = time.monotonic() - start_time
        return self.total_timeout_seconds - elapsed

    def _override_provider_timeout(self, remaining_seconds: float) -> float | None:
        provider_config = getattr(self._provider, "config", None)
        if provider_config is None:
            return None
        timeout = getattr(provider_config, "timeout", None)
        if not isinstance(timeout, (int, float)):
            return None

        current_timeout = float(timeout)
        target_timeout = max(0.1, min(current_timeout, remaining_seconds))
        if target_timeout == current_timeout:
            return None

        provider_config.timeout = target_timeout
        return current_timeout

    def _restore_provider_timeout(self, original_timeout: float | None) -> None:
        if original_timeout is None:
            return
        provider_config = getattr(self._provider, "config", None)
        if provider_config is None:
            return
        provider_config.timeout = original_timeout

    def _collect_legal_moves(self, game: ChessGame) -> list[str]:
        legal_moves: list[str] = []
        for position, piece in game.board.items():
            if not piece:
                continue
            colour, _ = piece
            if colour != game.current_player:
                continue
            for target in game.get_valid_moves(*position):
                legal_moves.append(f"{square_to_notation(position)}{square_to_notation(target)}")
        return legal_moves

    def _log(
        self,
        phase: str,
        message: str,
        *,
        status: str = "info",
        duration_ms: float | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.telemetry.record(
            phase=phase,
            message=message,
            status=status,
            duration_ms=duration_ms,
            metadata=metadata,
        )


__all__ = ["Strategist"]
