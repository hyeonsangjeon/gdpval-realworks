"""Bounded HTTP-429 retries around, never inside, the metered grading call."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
import math
import time
from typing import Any

# A longer server wait remains a refusal, never an earlier retry or an
# unbounded sleep that prevents the driver from publishing the refused item.
MAX_RETRY_WAIT_SECONDS = 600.0


@dataclass(frozen=True)
class Retry429Policy:
    max_retries: int = 0
    initial_backoff_sec: float = 2.0
    exponential_factor: float = 2.0

    @classmethod
    def from_config(cls, value: object) -> "Retry429Policy":
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ValueError("tpm_guard.retry_on_429 must be an object")
        enabled = value.get("enabled", True)
        retries = value.get("max_retries", 3)
        backoff = value.get("initial_backoff_sec", 2.0)
        factor = value.get("exponential_factor", 2.0)
        if type(enabled) is not bool or type(retries) is not int or retries < 0:
            raise ValueError("retry_on_429 requires a boolean enabled and nonnegative integer max_retries")
        for name, number, minimum in (("initial_backoff_sec", backoff, 0),
                                      ("exponential_factor", factor, 1)):
            if (type(number) not in (int, float) or not math.isfinite(number)
                    or number < minimum):
                raise ValueError(f"retry_on_429.{name} must be finite and >= {minimum}")
        return cls(retries if enabled else 0, float(backoff), float(factor))


@dataclass
class RetryCallStats:
    attempts: int = 0
    failed_attempts: int = 0
    latency_ms: float = 0.0


def _retry_after_seconds(error: Exception) -> float:
    headers = getattr(getattr(error, "response", None), "headers", None)
    if not isinstance(headers, Mapping):
        headers = getattr(error, "headers", None)
    if not isinstance(headers, Mapping):
        return 0.0
    hints = {key.lower(): value for key, value in headers.items() if isinstance(key, str)}
    delays = [0.0]
    for name, scale in (("retry-after", 1.0), ("retry-after-ms", 0.001),
                        ("x-ms-retry-after-ms", 0.001)):
        raw = hints.get(name)
        if not isinstance(raw, str):
            continue
        try:
            delay = float(raw) * scale
        except ValueError:
            if name != "retry-after":
                continue
            try:
                when = parsedate_to_datetime(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                delay = when.timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                continue
        if math.isinf(delay) and raw.strip().isdigit():
            return math.inf  # A valid but enormous delay must not become zero.
        if math.isfinite(delay):
            delays.append(max(0.0, delay))
    return max(delays)


def call_with_429_retry(
    call: Callable[[], Any], *, policy: Retry429Policy, stats: RetryCallStats,
    before_attempt: Callable[[], None] | None = None,
    can_retry: Callable[[], bool] | None = None,
) -> Any:
    """Every attempt re-enters the caller's existing client/receipt/USD guards.

    Only typed HTTP 429 responses are retried. Budget/deadline BaseExceptions
    escape unchanged. Backoff is not reported as provider latency, and failed
    attempts never acquire invented usage. Retry-After is a minimum wait, not
    permission to shorten the configured backoff or bypass a perception cap.
    """
    backoff = policy.initial_backoff_sec
    for attempt in range(policy.max_retries + 1):
        if before_attempt is not None:
            before_attempt()
        stats.attempts += 1
        started = time.perf_counter()
        try:
            return call()
        except Exception as error:
            stats.failed_attempts += 1
            status = getattr(error, "status_code", None)
            if status is None:
                status = getattr(getattr(error, "response", None), "status_code", None)
            if (not isinstance(status, int) or status != 429
                    or attempt >= policy.max_retries
                    or (can_retry is not None and not can_retry())):
                raise
            delay = max(backoff, _retry_after_seconds(error))
            if not math.isfinite(delay) or delay > MAX_RETRY_WAIT_SECONDS:
                raise  # Never shorten Retry-After or turn overflow into a retry.
        finally:
            stats.latency_ms += (time.perf_counter() - started) * 1000.0
        time.sleep(delay)
        backoff *= policy.exponential_factor
    raise AssertionError("unreachable retry state")
