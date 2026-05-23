"""Tests for :func:`config.get_key_diagnostics_detail`."""

from __future__ import annotations

from config import get_key_diagnostics_detail


def test_all_providers_present_in_diagnostics() -> None:
    """All 3 providers appear in the diagnostics output."""
    entries = get_key_diagnostics_detail()
    providers = [e.get("provider") for e in entries if e.get("provider") != "_platform"]
    assert "OpenAI" in providers
    assert "Anthropic" in providers
    assert "Gemini" in providers


def test_set_key_shows_present_with_length(monkeypatch) -> None:
    """A set key reports present=True with correct length and prefix."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test1234567890")
    entries = get_key_diagnostics_detail()
    openai_entry = next(e for e in entries if e.get("env_var") == "OPENAI_API_KEY")
    assert openai_entry["present"] is True
    assert openai_entry["length"] == len("sk-test1234567890")
    assert openai_entry["prefix"] == "sk-t..."


def test_missing_key_shows_not_present(monkeypatch) -> None:
    """A missing key reports present=False with no length field."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    entries = get_key_diagnostics_detail()
    anthropic_entry = next(e for e in entries if e.get("env_var") == "ANTHROPIC_API_KEY")
    assert anthropic_entry["present"] is False
    assert "length" not in anthropic_entry


def test_platform_info_included() -> None:
    """Platform info entry is present in diagnostics."""
    entries = get_key_diagnostics_detail()
    platform_entry = next(e for e in entries if e.get("provider") == "_platform")
    assert "system" in platform_entry
    assert "user" in platform_entry
