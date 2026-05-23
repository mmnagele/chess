"""Zentrale Konfigurationswerte für externe Dienste."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, fields
from typing import Any, TypeVar

T = TypeVar("T")

PROVIDER_KEYS: tuple[str, ...] = ("openai", "anthropic", "gemini")
PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Gemini",
}

MODEL_PRESETS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-4o-mini", "gpt-4.1-mini", "gpt-5-mini"),
    "anthropic": (
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-6",
    ),
    "gemini": ("gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite"),
}

COMMENTATOR_TYPES: tuple[str, ...] = (
    "Adult Coach",
    "Parent + 5-Year-Old Coach",
    "Tournament Commentator",
)


@dataclass(frozen=True)
class OpenAISettings:
    """Konfigurationsdaten für den Zugriff auf die OpenAI-API."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4o-mini"
    request_timeout: float = 30.0
    max_output_tokens: int = 1024
    temperature: float = 0.2
    organization: str | None = None

    def __repr__(self) -> str:
        return (
            f"OpenAISettings(api_key='***', base_url={self.base_url!r}, "
            f"default_model={self.default_model!r})"
        )


@dataclass(frozen=True)
class AnthropicSettings:
    """Konfiguration für den Zugriff auf Anthropic Claude."""

    api_key: str
    base_url: str = "https://api.anthropic.com/v1"
    default_model: str = "claude-sonnet-4-5-20250929"
    request_timeout: float = 30.0
    max_output_tokens: int = 1024
    temperature: float = 0.2

    def __repr__(self) -> str:
        return (
            f"AnthropicSettings(api_key='***', base_url={self.base_url!r}, "
            f"default_model={self.default_model!r})"
        )


@dataclass(frozen=True)
class GeminiSettings:
    """Konfiguration für Google Gemini."""

    api_key: str
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    default_model: str = "gemini-2.0-flash"
    request_timeout: float = 60.0
    max_output_tokens: int = 1024
    temperature: float = 0.2

    def __repr__(self) -> str:
        return (
            f"GeminiSettings(api_key='***', base_url={self.base_url!r}, "
            f"default_model={self.default_model!r})"
        )


def _field_default(cls: type, name: str) -> Any:
    """Return the default value of a dataclass field by name."""

    for f in fields(cls):  # type: ignore[arg-type]
        if f.name == name:
            return f.default
    raise KeyError(name)


def _env(key: str, cls: type, field_name: str, cast: type[T] = str) -> T:  # type: ignore[assignment]
    """Read *key* from environment, falling back to the dataclass default."""

    raw = os.getenv(key, _field_default(cls, field_name))
    return cast(raw)  # type: ignore[return-value]


def load_openai_settings() -> OpenAISettings:
    """Liest OpenAI-Einstellungen ausschliesslich aus Umgebungsvariablen."""

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt. Bitte in der Umgebung setzen.")

    return OpenAISettings(
        api_key=api_key,
        base_url=_env("OPENAI_BASE_URL", OpenAISettings, "base_url"),
        default_model=_env("OPENAI_DEFAULT_MODEL", OpenAISettings, "default_model"),
        temperature=_env("OPENAI_TEMPERATURE", OpenAISettings, "temperature", float),
        max_output_tokens=_env(
            "OPENAI_MAX_OUTPUT_TOKENS", OpenAISettings, "max_output_tokens", int
        ),
        request_timeout=_env("OPENAI_REQUEST_TIMEOUT", OpenAISettings, "request_timeout", float),
        organization=os.getenv("OPENAI_ORGANIZATION"),
    )


def load_anthropic_settings() -> AnthropicSettings:
    """Liest Anthropic-Einstellungen ausschliesslich aus Umgebungsvariablen."""

    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt. Bitte in der Umgebung setzen.")

    return AnthropicSettings(
        api_key=api_key,
        base_url=_env("ANTHROPIC_BASE_URL", AnthropicSettings, "base_url"),
        default_model=_env("ANTHROPIC_DEFAULT_MODEL", AnthropicSettings, "default_model"),
        request_timeout=_env(
            "ANTHROPIC_REQUEST_TIMEOUT", AnthropicSettings, "request_timeout", float
        ),
        max_output_tokens=_env(
            "ANTHROPIC_MAX_OUTPUT_TOKENS", AnthropicSettings, "max_output_tokens", int
        ),
        temperature=_env("ANTHROPIC_TEMPERATURE", AnthropicSettings, "temperature", float),
    )


def load_gemini_settings() -> GeminiSettings:
    """Liest Gemini-Einstellungen ausschliesslich aus Umgebungsvariablen."""

    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY fehlt. Bitte in der Umgebung setzen.")

    return GeminiSettings(
        api_key=api_key,
        base_url=_env("GEMINI_BASE_URL", GeminiSettings, "base_url"),
        default_model=_env("GEMINI_DEFAULT_MODEL", GeminiSettings, "default_model"),
        request_timeout=_env("GEMINI_REQUEST_TIMEOUT", GeminiSettings, "request_timeout", float),
        max_output_tokens=_env(
            "GEMINI_MAX_OUTPUT_TOKENS", GeminiSettings, "max_output_tokens", int
        ),
        temperature=_env("GEMINI_TEMPERATURE", GeminiSettings, "temperature", float),
    )


_PROVIDER_ENV_VARS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _dedupe_keep_order(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _order_by_preference(candidates: Sequence[str], preferred: Sequence[str]) -> list[str]:
    candidate_set = set(candidates)
    ordered: list[str] = [model for model in preferred if model in candidate_set]
    seen = set(ordered)
    ordered.extend(model for model in candidates if model not in seen)
    return _dedupe_keep_order(ordered)


def _http_get_json(resource: str | urllib.request.Request, timeout: float) -> dict[str, Any]:
    with urllib.request.urlopen(resource, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


_OPENAI_MODEL_EXCLUDE_TOKENS: tuple[str, ...] = (
    "audio",
    "image",
    "realtime",
    "transcribe",
    "tts",
    "search",
    "embedding",
    "moderation",
)

_OPENAI_MODEL_PREFERRED: tuple[str, ...] = (
    "gpt-5.2-chat-latest",
    "gpt-5.2",
    "gpt-5.1-chat-latest",
    "gpt-5.1",
    "gpt-5-chat-latest",
    "gpt-5",
    "gpt-5-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "chatgpt-4o-latest",
)


def _fetch_openai_models(api_key: str, timeout: float) -> list[str]:
    request = urllib.request.Request("https://api.openai.com/v1/models")
    request.add_header("Authorization", f"Bearer {api_key}")
    payload = _http_get_json(request, timeout)
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []

    models: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id:
            continue
        lower = model_id.lower()
        if not (lower.startswith("gpt-") or lower.startswith("chatgpt-")):
            continue
        if lower.endswith("-instruct"):
            continue
        if any(token in lower for token in _OPENAI_MODEL_EXCLUDE_TOKENS):
            continue
        models.append(model_id)

    ordered = _order_by_preference(models, _OPENAI_MODEL_PREFERRED)
    return ordered[:12]


_ANTHROPIC_MODEL_PREFERRED: tuple[str, ...] = (
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",
    "claude-sonnet-4-5",
    "claude-haiku-4-5",
    "claude-sonnet-4-20250514",
    "claude-3-7-sonnet-latest",
)


def _fetch_anthropic_models(api_key: str, timeout: float) -> list[str]:
    request = urllib.request.Request("https://api.anthropic.com/v1/models")
    request.add_header("x-api-key", api_key)
    request.add_header("anthropic-version", "2023-06-01")
    payload = _http_get_json(request, timeout)
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []

    models: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if model_id.startswith("claude-"):
            models.append(model_id)
    ordered = _order_by_preference(models, _ANTHROPIC_MODEL_PREFERRED)
    return ordered[:12]


_GEMINI_MODEL_EXCLUDE_TOKENS: tuple[str, ...] = (
    "audio",
    "tts",
    "embedding",
    "aqa",
    "imagen",
    "veo",
    "robotics",
    "computer-use",
    "deep-research",
    "image",
)

_GEMINI_MODEL_PREFERRED: tuple[str, ...] = (
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
)


def _fetch_gemini_models(api_key: str, timeout: float) -> list[str]:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models?key="
        f"{urllib.parse.quote(api_key, safe='')}"
    )
    payload = _http_get_json(url, timeout)
    data = payload.get("models", [])
    if not isinstance(data, list):
        return []

    models: list[str] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        methods = item.get("supportedGenerationMethods", [])
        if not isinstance(methods, list) or "generateContent" not in methods:
            continue
        name = str(item.get("name", "")).strip()
        if not name.startswith("models/"):
            continue
        model_id = name.removeprefix("models/")
        lower = model_id.lower()
        if not lower.startswith("gemini-"):
            continue
        if any(token in lower for token in _GEMINI_MODEL_EXCLUDE_TOKENS):
            continue
        models.append(model_id)

    ordered = _order_by_preference(models, _GEMINI_MODEL_PREFERRED)
    return ordered[:12]


_MODEL_FETCHERS = {
    "openai": _fetch_openai_models,
    "anthropic": _fetch_anthropic_models,
    "gemini": _fetch_gemini_models,
}


def get_model_presets(timeout: float = 8.0) -> dict[str, tuple[str, ...]]:
    """Return provider model presets, enriched with live provider catalogs.

    The function never raises for discovery failures. If a provider lookup fails,
    fallback presets are kept.
    """

    resolved = {key: tuple(models) for key, models in MODEL_PRESETS.items()}

    for provider in PROVIDER_KEYS:
        env_var = _PROVIDER_ENV_VARS[provider]
        api_key = (os.getenv(env_var) or "").strip()
        if not api_key:
            continue

        fetcher = _MODEL_FETCHERS.get(provider)
        if fetcher is None:
            continue

        try:
            live_models = fetcher(api_key, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            continue

        if not live_models:
            continue

        merged = _dedupe_keep_order([*live_models, *resolved[provider]])
        resolved[provider] = tuple(merged[:12])

    return resolved


def _is_key_present(env_var: str) -> bool:
    """Check if an API key is set and non-empty after stripping whitespace."""
    raw = os.environ.get(env_var, "")
    return len(raw.strip()) > 0


def get_provider_statuses() -> dict[str, bool]:
    """Gibt die Verfügbarkeit der Provider anhand gesetzter API-Keys zurück.

    Reads directly from ``os.environ`` each time (never cached).
    Strips whitespace before checking.
    """
    return {key: _is_key_present(env_var) for key, env_var in _PROVIDER_ENV_VARS.items()}


def get_provider_diagnostics() -> list[str]:
    """Return debug-safe diagnostic lines (no secrets) for each provider key."""
    lines: list[str] = []
    for provider_name, env_var in _PROVIDER_ENV_VARS.items():
        raw = os.environ.get(env_var, "")
        present = len(raw.strip()) > 0
        length_info = f", length={len(raw.strip())}" if present else ""
        lines.append(f"{env_var} ({provider_name}): present={present}{length_info}")
    return lines


def get_key_diagnostics_detail() -> list[dict[str, object]]:
    """Return detailed diagnostics for each provider key plus platform info.

    Each entry has: provider, env_var, present, and (if present) length + prefix.
    The last entry is ``_platform`` with system and user info.
    """
    import getpass
    import platform

    entries: list[dict[str, object]] = []
    for provider_name, env_var in _PROVIDER_ENV_VARS.items():
        raw = os.environ.get(env_var, "")
        stripped = raw.strip()
        entry: dict[str, object] = {
            "provider": PROVIDER_LABELS.get(provider_name, provider_name),
            "env_var": env_var,
            "present": len(stripped) > 0,
        }
        if stripped:
            entry["length"] = len(stripped)
            entry["prefix"] = stripped[:4] + "..."
        entries.append(entry)

    entries.append(
        {
            "provider": "_platform",
            "system": platform.system(),
            "user": getpass.getuser(),
        }
    )
    return entries


def get_available_providers() -> list[tuple[str, str]]:
    """Gibt verfügbare Provider als ``(Anzeigename, Schlüssel)`` zurück."""

    statuses = get_provider_statuses()
    available: list[tuple[str, str]] = []
    for key in PROVIDER_KEYS:
        if statuses.get(key):
            available.append((PROVIDER_LABELS[key], key))
    return available


def default_model_for(provider_key: str) -> str:
    """Liefert das erste Preset als Default-Modell."""

    presets = MODEL_PRESETS.get(provider_key, ())
    if not presets:
        raise ValueError(f"Unbekannter Provider: {provider_key}")
    return presets[0]


__all__ = [
    "OpenAISettings",
    "load_openai_settings",
    "AnthropicSettings",
    "load_anthropic_settings",
    "GeminiSettings",
    "load_gemini_settings",
    "get_available_providers",
    "get_provider_statuses",
    "get_provider_diagnostics",
    "get_key_diagnostics_detail",
    "get_model_presets",
    "PROVIDER_KEYS",
    "PROVIDER_LABELS",
    "MODEL_PRESETS",
    "COMMENTATOR_TYPES",
    "default_model_for",
]
