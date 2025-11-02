"""Zentrale Konfigurationswerte für externe Dienste."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _load_env_file(path: Path) -> None:
    """Lädt eine einfache ``.env``-Datei und füllt fehlende Umgebungsvariablen."""

    if not path.exists():
        return

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class OpenAISettings:
    """Konfigurationsdaten für den Zugriff auf die OpenAI-API."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o-mini"
    request_timeout: float = 30.0
    max_output_tokens: int = 1024
    temperature: float = 0.2
    organization: Optional[str] = None


def load_openai_settings() -> OpenAISettings:
    """Liest OpenAI-Einstellungen aus Umgebungsvariablen oder ``.env``."""

    _load_env_file(_ENV_FILE)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY fehlt. Bitte in der Umgebung oder .env setzen."
        )

    base_url = os.getenv("OPENAI_BASE_URL", OpenAISettings.__dataclass_fields__["base_url"].default)  # type: ignore[index]
    default_model = os.getenv(
        "OPENAI_DEFAULT_MODEL",
        OpenAISettings.__dataclass_fields__["default_model"].default,  # type: ignore[index]
    )
    temperature = float(
        os.getenv(
            "OPENAI_TEMPERATURE",
            OpenAISettings.__dataclass_fields__["temperature"].default,  # type: ignore[index]
        )
    )
    max_output_tokens = int(
        os.getenv(
            "OPENAI_MAX_OUTPUT_TOKENS",
            OpenAISettings.__dataclass_fields__["max_output_tokens"].default,  # type: ignore[index]
        )
    )
    request_timeout = float(
        os.getenv(
            "OPENAI_REQUEST_TIMEOUT",
            OpenAISettings.__dataclass_fields__["request_timeout"].default,  # type: ignore[index]
        )
    )
    organization = os.getenv("OPENAI_ORGANIZATION")

    return OpenAISettings(
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        request_timeout=request_timeout,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        organization=organization,
    )

