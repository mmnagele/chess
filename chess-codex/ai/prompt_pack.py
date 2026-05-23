"""Prompt-Paket-Lader für die Chess-KI."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Mapping

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Lädt ein Prompt-Template aus ``prompts/`` (cached)."""

    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8").strip()


def render_prompt(name: str, values: Mapping[str, object]) -> str:
    """Rendert ein Prompt-Template mit ``str.format``."""

    template = load_prompt(name)
    return template.format(**values)


__all__ = ["load_prompt", "render_prompt", "PROMPT_DIR"]
