"""Shared helper utilities for provider clients."""

from __future__ import annotations

import time
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def run_with_retries(
    operation: Callable[[], T],
    *,
    retries: int,
    backoff_initial: float,
    backoff_factor: float,
    is_retryable: Callable[[Exception], bool],
) -> T:
    """Execute ``operation`` with bounded retry/backoff behavior."""

    delay = backoff_initial
    attempt = 0
    while True:
        try:
            return operation()
        except Exception as exc:
            attempt += 1
            if attempt > retries:
                raise
            if not is_retryable(exc):
                raise
            time.sleep(delay)
            delay *= backoff_factor


def is_transient_error(exc: Exception) -> bool:
    """Best-effort detection for transient provider failures."""

    transient_names = {
        "RateLimitError",
        "APITimeoutError",
        "APIConnectionError",
        "ConnectError",
        "ConnectionError",
        "ReadTimeout",
        "ConnectTimeout",
        "Timeout",
        "TimeoutError",
        "SSLError",
        "ServiceUnavailableError",
        "InternalServerError",
    }
    if type(exc).__name__ in transient_names:
        return True

    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)

    return isinstance(status_code, int) and status_code >= 500


def sanitize_error_message(message: str, *, secrets: Iterable[str]) -> str:
    """Redact secret substrings from an error message."""

    sanitized = message
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "***")
    return sanitized


__all__ = ["run_with_retries", "is_transient_error", "sanitize_error_message"]
