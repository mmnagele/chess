"""Prompt-Paket-Lader für die Chess-KI."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Lädt ein Prompt-Template aus ``prompts/``."""

    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8").strip()


def render_prompt(name: str, values: Mapping[str, object]) -> str:
    """Rendert ein Prompt-Template mit ``str.format``."""

    template = load_prompt(name)
    return template.format(**values)


__all__ = ["load_prompt", "render_prompt", "PROMPT_DIR"]
