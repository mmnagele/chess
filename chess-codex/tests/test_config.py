"""Tests für das Modul :mod:`config`."""

from __future__ import annotations

import os

import pytest

from config import (
    MODEL_PRESETS,
    PROVIDER_ENV_KEYS,
    ProviderKeyResolver,
    default_model_for,
    get_available_providers,
    get_provider_statuses,
    load_anthropic_settings,
    load_gemini_settings,
    load_openai_settings,
    provider_key_diagnostics,
    resolve_model_for,
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


def test_provider_key_resolver_strips_whitespace(monkeypatch) -> None:
    """Leerzeichen-only Werte gelten als fehlend."""

    monkeypatch.setenv("OPENAI_API_KEY", "   ")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  key-anth  ")
    monkeypatch.setenv("GEMINI_API_KEY", "\n")

    resolver = ProviderKeyResolver()
    statuses = resolver.statuses()
    assert statuses == {"openai": False, "anthropic": True, "gemini": False}

    diagnostics = resolver.diagnostics()
    assert diagnostics["openai"].provider == "openai"
    assert diagnostics["openai"].length == 0
    assert diagnostics["anthropic"].length == len("key-anth")
    assert diagnostics["gemini"].length == 0


def test_provider_key_diagnostics_reads_live_environment(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    diagnostics = provider_key_diagnostics()
    assert diagnostics["openai"].present is False

    monkeypatch.setenv("OPENAI_API_KEY", "live-key")
    diagnostics = provider_key_diagnostics()
    assert diagnostics["openai"].present is True
    assert diagnostics["openai"].length == len("live-key")


def test_provider_env_key_mapping_is_strict() -> None:
    """Nur die drei erlaubten Env-Variablen sind gemappt."""

    assert PROVIDER_ENV_KEYS == {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }


def test_provider_key_resolver_imports_missing_from_login_shell(monkeypatch) -> None:
    """Fehlende Keys können aus Login-Shell-Umgebung übernommen werden."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class _Completed:
        returncode = 0
        stdout = b"key-openai\x00\x00 key-gemini \x00"

    def _fake_run(*_args, **_kwargs):
        return _Completed()

    monkeypatch.setattr("config.subprocess.run", _fake_run)
    monkeypatch.setattr("config.sys.platform", "linux")

    resolver = ProviderKeyResolver()
    imported = resolver.import_missing_from_login_shell(enabled=True)

    assert imported == {"openai": True, "anthropic": False, "gemini": True}
    assert os.environ["OPENAI_API_KEY"] == "key-openai"
    assert os.environ["GEMINI_API_KEY"] == "key-gemini"
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_provider_key_resolver_does_not_override_existing_key(monkeypatch) -> None:
    """Bereits gesetzte Process-Keys werden nicht überschrieben."""

    monkeypatch.setenv("OPENAI_API_KEY", "existing-openai")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    class _Completed:
        returncode = 0
        stdout = b"shell-openai\x00shell-anthropic\x00shell-gemini\x00"

    def _fake_run(*_args, **_kwargs):
        return _Completed()

    monkeypatch.setattr("config.subprocess.run", _fake_run)
    monkeypatch.setattr("config.sys.platform", "linux")

    resolver = ProviderKeyResolver()
    imported = resolver.import_missing_from_login_shell(enabled=True)

    assert imported == {"openai": False, "anthropic": True, "gemini": True}
    assert os.environ["OPENAI_API_KEY"] == "existing-openai"
    assert os.environ["ANTHROPIC_API_KEY"] == "shell-anthropic"
    assert os.environ["GEMINI_API_KEY"] == "shell-gemini"


def test_provider_key_resolver_shell_import_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    called = {"value": False}

    def _fake_run(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("subprocess should not run when shell import is disabled")

    monkeypatch.setattr("config.subprocess.run", _fake_run)

    resolver = ProviderKeyResolver()
    imported = resolver.import_missing_from_login_shell()

    assert imported == {"openai": False, "anthropic": False, "gemini": False}
    assert called["value"] is False


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


def test_anthropic_base_url_v1_is_normalized(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "token")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1/")
    settings = load_anthropic_settings()
    assert settings.base_url == "https://api.anthropic.com"


@pytest.mark.parametrize(
    "provider,raw,expected",
    [
        ("anthropic", "claude-sonnet-4-5-202", "claude-sonnet-4-5-20250929"),
        ("anthropic", "opus 4.6", "claude-opus-4-6"),
        ("openai", "gpt5", "gpt-5"),
        ("gemini", "gemini 2.5 flash", "gemini-2.5-flash"),
        ("openai", "my-custom-model", "my-custom-model"),
    ],
)
def test_resolve_model_for_aliases(provider: str, raw: str, expected: str) -> None:
    assert resolve_model_for(provider, raw) == expected
