"""Persistente Session-Logs im JSONL-Format."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SessionLogger:
    """Schreibt Session-Ereignisse als JSONL nach ``logs/``."""

    def __init__(self, directory: Path | None = None) -> None:
        base_dir = directory or Path("logs")
        base_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = base_dir / f"chess_session_{stamp}.jsonl"

    def log(self, event: str, payload: dict[str, Any] | None = None) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload or {},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


__all__ = ["SessionLogger"]
