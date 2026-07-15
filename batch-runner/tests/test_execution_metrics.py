"""Numeric contract tests for opt-in execution performance metrics."""

import math

import pytest

from core.execution_metrics import (
    MAX_COUNT,
    MAX_DURATION_MS,
    add_counts,
    add_durations_ms,
    bounded_count,
    bounded_duration_ms,
)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        "1",
        -1,
        math.nan,
        math.inf,
        -math.inf,
        MAX_DURATION_MS + 1,
        10**400,
    ],
)
def test_bounded_duration_rejects_invalid_values(value):
    assert bounded_duration_ms(value) is None


def test_bounded_duration_accepts_schema_boundary():
    assert bounded_duration_ms(0) == 0
    assert bounded_duration_ms(MAX_DURATION_MS) == MAX_DURATION_MS


@pytest.mark.parametrize(
    "value",
    [None, True, False, "1", 1.0, -1, MAX_COUNT + 1],
)
def test_bounded_count_requires_strict_bounded_integer(value):
    assert bounded_count(value) is None


def test_add_helpers_reject_cumulative_bound_escape():
    assert add_durations_ms(MAX_DURATION_MS, 1) is None
    assert add_counts(MAX_COUNT, 1) is None
