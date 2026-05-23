"""Tests für das Modul :mod:`config`."""

from __future__ import annotations

import pytest

import config as config_module
from config import (
    MODEL_PRESETS,
    default_model_for,
    get_available_providers,
    get_model_presets,
    get_provider_statuses,
    load_anthropic_settings,
    load_gemini_settings,
    load_openai_settings,
)


@pytest.mark.parametrize(
    "loader,key,env_prefix",
    [
        (load_openai_settings, "OPENAI_API_KEY", "OPENAI"),
        (load_anthropic_settings, "ANTHROPIC_API_KEY", "ANTHROPIC"),
        (load_gemini_settings, "GEMINI_API_KEY", "GEMINI"),
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
        (load_gemini_settings, "GEMINI_API_KEY"),
    ],
)
def test_settings_loader_requires_api_key(monkeypatch, loader, key) -> None:
    """Fehlende API-Schlüssel führen zu einer klaren Ausnahme."""

    monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError):
        loader()


def test_gemini_does_not_accept_google_api_key(monkeypatch) -> None:
    """Gemini akzeptiert nur GEMINI_API_KEY."""

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LEGACY_GEMINI_KEY", "google-token")
    with pytest.raises(RuntimeError):
        load_gemini_settings()


def test_get_provider_statuses(monkeypatch) -> None:
    """Providerstatus spiegelt gesetzte API-Keys wider."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    statuses = get_provider_statuses()
    assert statuses == {"openai": False, "anthropic": False, "gemini": False}

    monkeypatch.setenv("OPENAI_API_KEY", "k1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k2")
    statuses = get_provider_statuses()
    assert statuses["openai"] is True
    assert statuses["anthropic"] is True
    assert statuses["gemini"] is False


def test_get_available_providers(monkeypatch) -> None:
    """Es werden nur Provider mit gesetztem Key zurückgegeben."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert get_available_providers() == []

    monkeypatch.setenv("OPENAI_API_KEY", "k1")
    monkeypatch.setenv("GEMINI_API_KEY", "k3")
    providers = get_available_providers()
    assert providers == [("OpenAI", "openai"), ("Gemini", "gemini")]


def test_default_model_for_all_providers() -> None:
    """Jeder Provider liefert ein Default-Modell aus den Presets."""

    for provider in ("openai", "anthropic", "gemini"):
        assert default_model_for(provider) == MODEL_PRESETS[provider][0]

    with pytest.raises(ValueError):
        default_model_for("unknown")


def test_get_model_presets_returns_fallback_without_keys(monkeypatch) -> None:
    """Without API keys, live discovery is skipped and fallback presets are used."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert get_model_presets(timeout=0.01) == MODEL_PRESETS


def test_get_model_presets_merges_live_models(monkeypatch) -> None:
    """Live models are prepended and deduplicated against fallback presets."""

    monkeypatch.setenv("OPENAI_API_KEY", "k-openai")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    monkeypatch.setattr(
        config_module,
        "_MODEL_FETCHERS",
        {
            "openai": lambda _key, _timeout: ["gpt-live", MODEL_PRESETS["openai"][0]],
            "anthropic": lambda _key, _timeout: [],
            "gemini": lambda _key, _timeout: [],
        },
    )

    presets = get_model_presets(timeout=0.01)
    assert presets["openai"][0] == "gpt-live"
    assert presets["openai"].count(MODEL_PRESETS["openai"][0]) == 1


def test_get_model_presets_keeps_fallback_on_fetch_error(monkeypatch) -> None:
    """Fetcher errors must never crash or erase fallback model presets."""

    monkeypatch.setenv("OPENAI_API_KEY", "k-openai")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _boom(_key: str, _timeout: float) -> list[str]:
        raise OSError("network down")

    monkeypatch.setattr(
        config_module,
        "_MODEL_FETCHERS",
        {
            "openai": _boom,
            "anthropic": lambda _key, _timeout: [],
            "gemini": lambda _key, _timeout: [],
        },
    )

    presets = get_model_presets(timeout=0.01)
    assert presets["openai"] == MODEL_PRESETS["openai"]
