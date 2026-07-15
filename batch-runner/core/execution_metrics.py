"""Validation helpers for opt-in execution performance metrics."""

from __future__ import annotations

import math
from typing import Optional

MAX_DURATION_MS = 30 * 24 * 60 * 60 * 1000
MAX_COUNT = 1_000_000


def bounded_duration_ms(value) -> Optional[float]:
    """Return a finite 0..30-day duration, rejecting coercion from strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int) and not 0 <= value <= MAX_DURATION_MS:
        return None
    try:
        parsed = float(value)
    except OverflowError:
        return None
    if not math.isfinite(parsed) or not 0 <= parsed <= MAX_DURATION_MS:
        return None
    return round(parsed, 2)


def bounded_count(value) -> Optional[int]:
    """Return a strict non-negative integer count within the schema bound."""
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        return None
    return value


def add_durations_ms(*values) -> Optional[float]:
    """Add per-task durations without allowing overflow or bound escape."""
    parsed = [bounded_duration_ms(value) for value in values]
    if any(value is None for value in parsed):
        return None
    return bounded_duration_ms(math.fsum(parsed))


def add_counts(*values) -> Optional[int]:
    """Add strict counts without allowing the cumulative bound to escape."""
    parsed = [bounded_count(value) for value in values]
    if any(value is None for value in parsed):
        return None
    return bounded_count(sum(parsed))
