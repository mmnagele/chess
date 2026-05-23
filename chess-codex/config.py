"""Zentrale Konfigurationswerte für externe Dienste."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, fields
from typing import Any, Mapping, TypeVar

T = TypeVar("T")

PROVIDER_KEYS: tuple[str, ...] = ("openai", "anthropic", "gemini")
PROVIDER_LABELS: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Gemini",
}

MODEL_PRESETS: dict[str, tuple[str, ...]] = {
    "openai": ("gpt-4.1-nano", "gpt-4.1-mini", "gpt-4.1"),
    "anthropic": (
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-6",
    ),
    "gemini": ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"),
}

MODEL_ALIASES: dict[str, dict[str, str]] = {
    "openai": {
        "gpt5": "gpt-5",
        "gpt 5": "gpt-5",
        "gpt-5-chat": "gpt-5-chat-latest",
    },
    "anthropic": {
        "claude-3-5-haiku-latest": "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-202": "claude-sonnet-4-5-20250929",
        "claude sonnet 4.5": "claude-sonnet-4-5-20250929",
        "sonnet 4.5": "claude-sonnet-4-5-20250929",
        "claude-opus-4.6": "claude-opus-4-6",
        "claude opus 4.6": "claude-opus-4-6",
        "opus 4.6": "claude-opus-4-6",
    },
    "gemini": {
        "gemini 2.5 flash": "gemini-2.5-flash",
        "gemini 2.5 pro": "gemini-2.5-pro",
        "gemini 2.0 flash": "gemini-2.0-flash",
    },
}

COMMENTATOR_TYPES: tuple[str, ...] = (
    "Adult Coach",
    "Parent + 5-Year-Old Coach",
    "Tournament Commentator",
)
PROVIDER_ENV_KEYS: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderKeyDiagnostic:
    """Debug-sichere Diagnoseinformation für einen Provider-Key."""

    provider: str
    env_key: str
    present: bool
    length: int


def provider_key_diagnostics(
    *,
    environ: Mapping[str, str] | None = None,
    log_diagnostics: bool = False,
) -> dict[str, ProviderKeyDiagnostic]:
    """Single source of truth for live provider key diagnostics."""

    active_environ = os.environ if environ is None else environ
    result: dict[str, ProviderKeyDiagnostic] = {}
    for provider in PROVIDER_KEYS:
        env_key = PROVIDER_ENV_KEYS[provider]
        value = active_environ.get(env_key, "").strip()
        result[provider] = ProviderKeyDiagnostic(
            provider=provider,
            env_key=env_key,
            present=bool(value),
            length=len(value),
        )

    if log_diagnostics:
        ProviderKeyResolver._log_diagnostics(result)
    return result


class ProviderKeyResolver:
    """Liest und bewertet Provider-API-Keys aus Umgebungsvariablen."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ

    def read(self, env_key: str) -> str:
        """Liest einen Key-Wert und entfernt führende/trailing Whitespaces."""

        active_environ = os.environ if self._environ is None else self._environ
        return active_environ.get(env_key, "").strip()

    def statuses(self, *, log_diagnostics: bool = False) -> dict[str, bool]:
        """Gibt für jeden Provider zurück, ob ein gültiger Key vorliegt."""

        diagnostics = self.diagnostics(log_diagnostics=log_diagnostics)
        return {provider: info.present for provider, info in diagnostics.items()}

    def diagnostics(self, *, log_diagnostics: bool = False) -> dict[str, ProviderKeyDiagnostic]:
        """Liefert debug-sichere Diagnosen (kein Secret-Inhalt)."""

        return provider_key_diagnostics(environ=self._environ, log_diagnostics=log_diagnostics)

    def key_for_provider(self, provider_key: str) -> str:
        """Liest den Key-Wert für einen bekannten Provider."""

        env_key = PROVIDER_ENV_KEYS.get(provider_key)
        if env_key is None:
            raise ValueError(f"Unbekannter Provider: {provider_key}")
        return self.read(env_key)

    def import_missing_from_login_shell(
        self,
        *,
        timeout_seconds: float = 1.5,
        enabled: bool = False,
        log_diagnostics: bool = False,
    ) -> dict[str, bool]:
        """Importiert fehlende Provider-Keys aus einer Login-Shell-Umgebung."""

        imported = {provider: False for provider in PROVIDER_KEYS}
        if not enabled:
            return imported
        if sys.platform not in {"linux", "darwin"}:
            return imported

        shell_values = self._read_from_login_shell(timeout_seconds=timeout_seconds)
        if shell_values is None:
            return imported

        for provider in PROVIDER_KEYS:
            env_key = PROVIDER_ENV_KEYS[provider]
            if self.read(env_key):
                continue

            candidate = shell_values.get(provider, "")
            if not candidate:
                continue

            os.environ[env_key] = candidate
            imported[provider] = True

        if log_diagnostics:
            diagnostics = self.diagnostics()
            for provider in PROVIDER_KEYS:
                if not imported[provider]:
                    continue
                info = diagnostics[provider]
                _LOG.info(
                    "[key-resolver] shell-import provider=%s env=%s present=%s length=%d",
                    provider,
                    info.env_key,
                    info.present,
                    info.length,
                )

        return imported

    @staticmethod
    def _log_diagnostics(diagnostics: dict[str, ProviderKeyDiagnostic]) -> None:
        for _provider, info in diagnostics.items():
            _LOG.info(
                "[key-resolver] provider=%s env=%s present=%s length=%d",
                info.provider,
                info.env_key,
                info.present,
                info.length,
            )

    @staticmethod
    def _read_from_login_shell(*, timeout_seconds: float) -> dict[str, str] | None:
        command = (
            "printf '%s\\0%s\\0%s\\0' " '"$OPENAI_API_KEY" "$ANTHROPIC_API_KEY" "$GEMINI_API_KEY"'
        )
        shell_candidates = [
            os.environ.get("SHELL", ""),
            "/bin/bash",
            "bash",
            "/bin/sh",
            "sh",
        ]

        seen: set[str] = set()
        for shell_path in shell_candidates:
            if not shell_path or shell_path in seen:
                continue
            seen.add(shell_path)
            for mode_flag in ("-lc", "-ic"):
                try:
                    completed = subprocess.run(
                        [shell_path, mode_flag, command],
                        capture_output=True,
                        check=False,
                        timeout=timeout_seconds,
                    )
                except (OSError, subprocess.SubprocessError):
                    continue

                if completed.returncode != 0:
                    continue

                chunks = completed.stdout.split(b"\0")
                decoded = [chunk.decode("utf-8", errors="ignore").strip() for chunk in chunks]

                values: dict[str, str] = {}
                for index, provider in enumerate(PROVIDER_KEYS):
                    values[provider] = decoded[index] if index < len(decoded) else ""
                return values

        return None


@dataclass(frozen=True)
class OpenAISettings:
    """Konfigurationsdaten für den Zugriff auf die OpenAI-API."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    default_model: str = "gpt-4.1-nano"
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
    base_url: str = "https://api.anthropic.com"
    default_model: str = "claude-haiku-4-5-20251001"
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
    default_model: str = "gemini-2.5-flash"
    request_timeout: float = 30.0
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


def _normalize_base_url(provider_key: str, base_url: str) -> str:
    """Normalisiert Base-URLs und entfernt bekannte Stolperfallen."""

    normalized = base_url.strip().rstrip("/")
    if provider_key == "anthropic" and normalized.endswith("/v1"):
        return normalized[: -len("/v1")]
    return normalized


def _normalize_model_token(value: str) -> str:
    """Normalisiert Modellnamen für fuzzy matching."""

    lowered = value.strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")


def resolve_model_for(provider_key: str, model: str) -> str:
    """Normalisiert Modellnamen auf bekannte Presets/Aliase."""

    candidate = model.strip()
    if not candidate:
        return candidate

    presets = MODEL_PRESETS.get(provider_key, ())
    if not presets:
        return candidate

    if candidate in presets:
        return candidate

    lower_candidate = candidate.lower()
    normalized_candidate = _normalize_model_token(candidate)

    presets_by_lower = {preset.lower(): preset for preset in presets}
    if lower_candidate in presets_by_lower:
        return presets_by_lower[lower_candidate]

    presets_by_norm = {_normalize_model_token(preset): preset for preset in presets}
    if normalized_candidate in presets_by_norm:
        return presets_by_norm[normalized_candidate]

    aliases = MODEL_ALIASES.get(provider_key, {})
    aliases_by_lower = {key.lower(): value for key, value in aliases.items()}
    if lower_candidate in aliases_by_lower:
        return aliases_by_lower[lower_candidate]

    aliases_by_norm = {_normalize_model_token(key): value for key, value in aliases.items()}
    if normalized_candidate in aliases_by_norm:
        return aliases_by_norm[normalized_candidate]

    lower_prefix_matches = [
        preset for preset in presets if preset.lower().startswith(lower_candidate)
    ]
    if len(lower_prefix_matches) == 1:
        return lower_prefix_matches[0]

    norm_prefix_matches = [
        preset
        for preset in presets
        if _normalize_model_token(preset).startswith(normalized_candidate)
    ]
    if len(norm_prefix_matches) == 1:
        return norm_prefix_matches[0]

    return candidate


def load_openai_settings() -> OpenAISettings:
    """Liest OpenAI-Einstellungen ausschliesslich aus Umgebungsvariablen."""

    resolver = ProviderKeyResolver()
    api_key = resolver.key_for_provider("openai")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY fehlt. Bitte in der Umgebung setzen.")

    return OpenAISettings(
        api_key=api_key,
        base_url=_normalize_base_url(
            "openai",
            _env("OPENAI_BASE_URL", OpenAISettings, "base_url"),
        ),
        default_model=resolve_model_for(
            "openai",
            _env("OPENAI_DEFAULT_MODEL", OpenAISettings, "default_model"),
        ),
        temperature=_env("OPENAI_TEMPERATURE", OpenAISettings, "temperature", float),
        max_output_tokens=_env(
            "OPENAI_MAX_OUTPUT_TOKENS", OpenAISettings, "max_output_tokens", int
        ),
        request_timeout=_env("OPENAI_REQUEST_TIMEOUT", OpenAISettings, "request_timeout", float),
        organization=os.getenv("OPENAI_ORGANIZATION"),
    )


def load_anthropic_settings() -> AnthropicSettings:
    """Liest Anthropic-Einstellungen ausschliesslich aus Umgebungsvariablen."""

    resolver = ProviderKeyResolver()
    api_key = resolver.key_for_provider("anthropic")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt. Bitte in der Umgebung setzen.")

    return AnthropicSettings(
        api_key=api_key,
        base_url=_normalize_base_url(
            "anthropic",
            _env("ANTHROPIC_BASE_URL", AnthropicSettings, "base_url"),
        ),
        default_model=resolve_model_for(
            "anthropic",
            _env("ANTHROPIC_DEFAULT_MODEL", AnthropicSettings, "default_model"),
        ),
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

    resolver = ProviderKeyResolver()
    api_key = resolver.key_for_provider("gemini")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY fehlt. Bitte in der Umgebung setzen.")

    return GeminiSettings(
        api_key=api_key,
        base_url=_normalize_base_url(
            "gemini",
            _env("GEMINI_BASE_URL", GeminiSettings, "base_url"),
        ),
        default_model=resolve_model_for(
            "gemini",
            _env("GEMINI_DEFAULT_MODEL", GeminiSettings, "default_model"),
        ),
        request_timeout=_env("GEMINI_REQUEST_TIMEOUT", GeminiSettings, "request_timeout", float),
        max_output_tokens=_env(
            "GEMINI_MAX_OUTPUT_TOKENS", GeminiSettings, "max_output_tokens", int
        ),
        temperature=_env("GEMINI_TEMPERATURE", GeminiSettings, "temperature", float),
    )


def get_provider_statuses(
    *,
    resolver: ProviderKeyResolver | None = None,
    log_diagnostics: bool = False,
) -> dict[str, bool]:
    """Gibt die Verfügbarkeit der Provider anhand gesetzter API-Keys zurück."""

    active_resolver = resolver or ProviderKeyResolver()
    return active_resolver.statuses(log_diagnostics=log_diagnostics)


def get_available_providers(
    *, resolver: ProviderKeyResolver | None = None
) -> list[tuple[str, str]]:
    """Gibt verfügbare Provider als ``(Anzeigename, Schlüssel)`` zurück."""

    statuses = get_provider_statuses(resolver=resolver)
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
    "PROVIDER_KEYS",
    "PROVIDER_LABELS",
    "MODEL_PRESETS",
    "COMMENTATOR_TYPES",
    "PROVIDER_ENV_KEYS",
    "provider_key_diagnostics",
    "ProviderKeyDiagnostic",
    "ProviderKeyResolver",
    "default_model_for",
    "resolve_model_for",
]
