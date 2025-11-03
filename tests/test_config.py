"""Tests für das Modul :mod:`config`."""

from __future__ import annotations

import pytest

from config import (
    load_anthropic_settings,
    load_gemini_settings,
    load_openai_settings,
)


@pytest.mark.parametrize(
    "loader,key,env_prefix",
    [
        (load_openai_settings, "OPENAI_API_KEY", "OPENAI"),
        (load_anthropic_settings, "ANTHROPIC_API_KEY", "ANTHROPIC"),
        (load_gemini_settings, "GOOGLE_API_KEY", "GEMINI"),
    ],
)
def test_settings_loader_reads_environment(monkeypatch, loader, key, env_prefix) -> None:
    """Die Loader übernehmen Werte aus der Umgebung."""

    monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(key, "token")
    monkeypatch.setenv(f"{env_prefix}_REQUEST_TIMEOUT", "12")
    settings = loader()
    assert settings.api_key == "token"
    assert settings.request_timeout == 12.0


@pytest.mark.parametrize(
    "loader,key",
    [
        (load_openai_settings, "OPENAI_API_KEY"),
        (load_anthropic_settings, "ANTHROPIC_API_KEY"),
        (load_gemini_settings, "GOOGLE_API_KEY"),
    ],
)
def test_settings_loader_requires_api_key(monkeypatch, loader, key) -> None:
    """Fehlende API-Schlüssel führen zu einer klaren Ausnahme."""

    monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError):
        loader()
