"""Tests for crash-safe agentic budget reservations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from core.agentic_budget import AgenticBudgetLedger, BudgetCaps, BudgetExceeded


def _caps(**overrides):
    values = {
        "attempts": 2,
        "input_tokens": 100,
        "output_tokens": 100,
        "cost_usd": Decimal("1.00"),
    }
    values.update(overrides)
    return BudgetCaps(**values)


def test_reservation_survives_reopen_and_timeout(tmp_path):
    path = tmp_path / "budget.sqlite3"
    ledger = AgenticBudgetLedger(path)
    ledger.reserve(
        scope="run/a/task", request_id="r1", input_tokens=40,
        output_tokens=50, cost_usd=Decimal("0.40"), caps=_caps(),
    )

    reopened = AgenticBudgetLedger(path)
    usage = reopened.usage("run/a/task")

    assert usage.attempts == 1
    assert usage.input_tokens == 40
    assert usage.output_tokens == 50
    assert usage.cost_usd == Decimal("0.40")


def test_reconcile_only_moves_reservation_downward(tmp_path):
    ledger = AgenticBudgetLedger(tmp_path / "budget.sqlite3")
    ledger.reserve(
        scope="scope", request_id="r1", input_tokens=40,
        output_tokens=50, cost_usd=Decimal("0.40"), caps=_caps(),
    )

    usage = ledger.reconcile(
        scope="scope", request_id="r1", actual_input_tokens=20,
        actual_output_tokens=10, actual_cost_usd=Decimal("0.12"),
    )

    assert usage.attempts == 1
    assert usage.input_tokens == 20
    assert usage.output_tokens == 10
    assert usage.cost_usd == Decimal("0.12")
    with pytest.raises(ValueError, match="already reconciled"):
        ledger.reconcile(
            scope="scope", request_id="r1", actual_input_tokens=20,
            actual_output_tokens=10, actual_cost_usd=Decimal("0.12"),
        )


def test_concurrent_reservations_cannot_cross_cap(tmp_path):
    path = tmp_path / "budget.sqlite3"

    def reserve(request_id):
        ledger = AgenticBudgetLedger(path)
        try:
            ledger.reserve(
                scope="paired", request_id=request_id, input_tokens=60,
                output_tokens=10, cost_usd=Decimal("0.10"),
                caps=_caps(attempts=10),
            )
            return "accepted"
        except BudgetExceeded:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, ["r1", "r2"]))

    assert sorted(outcomes) == ["accepted", "rejected"]
    assert AgenticBudgetLedger(path).usage("paired").input_tokens == 60


def test_multi_scope_reservation_rolls_back_all_scopes_on_one_cap(tmp_path):
    ledger = AgenticBudgetLedger(tmp_path / "budget.sqlite3")

    with pytest.raises(BudgetExceeded, match="input_token_cap"):
        ledger.reserve_many(
            scopes={
                "task": _caps(input_tokens=100),
                "condition": _caps(input_tokens=50),
                "paired": _caps(input_tokens=100),
            },
            request_id="r1",
            input_tokens=60,
            output_tokens=10,
            cost_usd=Decimal("0.10"),
        )

    for scope in ("task", "condition", "paired"):
        assert ledger.usage(scope).attempts == 0


def test_concurrent_tasks_share_one_atomic_paired_cap(tmp_path):
    path = tmp_path / "budget.sqlite3"

    def reserve(task_id):
        ledger = AgenticBudgetLedger(path)
        try:
            ledger.reserve_many(
                scopes={
                    f"task:{task_id}": _caps(attempts=10),
                    f"condition:{task_id}": _caps(attempts=10),
                    "paired": _caps(attempts=10, input_tokens=100),
                },
                request_id=f"request:{task_id}",
                input_tokens=60,
                output_tokens=10,
                cost_usd=Decimal("0.10"),
            )
            return "accepted"
        except BudgetExceeded:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, ["a", "b"]))

    assert sorted(outcomes) == ["accepted", "rejected"]
    assert AgenticBudgetLedger(path).usage("paired").input_tokens == 60