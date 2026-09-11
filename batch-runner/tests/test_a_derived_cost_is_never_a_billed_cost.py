"""The run-34571840967 record carries two figures for money, and they must not merge.

The ledger that run uploaded holds a dollar figure for none of its 88 calls.
Not because the price was unknown -- the price table is committed, and the run
recorded the very fingerprint of it -- but because ``settle`` discards a
computed cost the moment any reason is attached, and the Codex path attaches
``call_reachability_unknown`` to every turn unconditionally.

Neither figure is an invoice. ``model_cost_usd`` never was one either: the
summary built over these receipts stamps itself
``estimate_basis: usage_estimate_not_azure_invoice``, and the provider's actual
charge for this subscription is not visible from here at all. So the split this
file defends is *not* billed-versus-derived. Both numbers are ``price_call``
over reported tokens; they differ in who computed them and when.

``model_cost_usd`` is the run pricing its own call as it settled it, against
the table it had loaded at that moment. The derived column is that same
arithmetic redone afterwards, by a tool a later reader points at a ledger.
The second is weaker evidence -- it is only sound because the derivation
refuses to run unless the committed table's fingerprint matches the one the
run recorded for itself, and a reader of the finished record cannot see that
that check happened. Writing the recomputation into the run's own column would
erase the distinction between a figure the run stood behind and one produced
later, which is the thing that makes the first auditable.

This file makes that promotion fail loudly. It also pins the four-way split
that keeps the figure honest: a task whose every call reported usage has a
complete figure, a task with an unmeasured send has a floor, a task with sends
but no measurement has none at all, and a task never reached has a true zero.
Collapsing those into one column is how "we don't know" turns into "it was
free".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RECORD = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "run_records"
    / "exp035_run34571840967_partial"
    / "outcomes.json"
)

DERIVED = "derived_cost_usd_from_measured_tokens"
BASIS = "derived_cost_basis"
MEASURED = "derived_cost_calls_measured"
UNMEASURED = "derived_cost_calls_unmeasured"


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_the_record_still_covers_all_220_tasks(rows):
    assert len(rows) == 220
    assert len({row["task_id"] for row in rows}) == 220
    assert sum(1 for row in rows if row.get("attempted")) == 45


def test_no_attempted_task_claims_the_runs_own_figure(rows):
    """The recomputation must never be written into the ledger's own column.

    ``model_cost_usd`` is what the run priced as it settled the call. For this
    run it settled nothing, and a number appearing there later would claim a
    provenance the record cannot support -- indistinguishable, to anyone
    reading the finished file, from a figure the run itself stood behind.
    """
    attempted = [row for row in rows if row.get("attempted")]
    billed = [row for row in attempted if row.get("model_cost_usd") is not None]
    assert billed == [], (
        f"{len(billed)} attempted task(s) carry a settled cost. This run "
        "settled no call with an amount; if this is the recomputed figure, it "
        f"belongs in {DERIVED!r}."
    )
    assert all(row["cost_state"] == "undetermined" for row in attempted)
    assert all(row["derived_cost_is_provider_billed"] is False for row in rows)


def test_a_derived_figure_says_which_kind_it_is(rows):
    """Complete, floor, absent, and never-spent are four different states."""
    seen = {}
    for row in rows:
        basis = row[BASIS]
        seen[basis] = seen.get(basis, 0) + 1
        measured, unmeasured = row[MEASURED], row[UNMEASURED]

        if basis == "no_call_made":
            assert not row.get("attempted")
            assert (measured, unmeasured) == (0, 0)
            # A task that was never reached really did cost nothing.
            assert row[DERIVED] == 0.0
        elif basis == "no_measured_call":
            # Sends happened; not one of them reported usage. No figure exists.
            assert measured == 0 and unmeasured > 0
            assert row[DERIVED] is None
        elif basis == "all_calls_measured":
            assert measured > 0 and unmeasured == 0
            assert row[DERIVED] > 0
        elif basis == "floor_unmeasured_sends_excluded":
            assert measured > 0 and unmeasured > 0
            assert row[DERIVED] > 0
        else:  # pragma: no cover - a new basis must be described here first
            raise AssertionError(f"undescribed basis {basis!r}")

    assert seen == {
        "all_calls_measured": 32,
        "floor_unmeasured_sends_excluded": 11,
        "no_measured_call": 2,
        "no_call_made": 175,
    }


def test_the_derived_calls_add_up_to_the_ledger_the_run_uploaded(rows):
    """88 calls, 75 of them measured -- the same split the report states."""
    attempted = [row for row in rows if row.get("attempted")]
    measured = sum(row[MEASURED] for row in attempted)
    unmeasured = sum(row[UNMEASURED] for row in attempted)
    assert measured == 75
    assert unmeasured == 13
    assert measured + unmeasured == 88
    assert measured + unmeasured == sum(row["calls"] for row in attempted)


def test_the_total_is_a_floor_and_the_report_says_the_same_number(rows):
    total = sum(
        row[DERIVED] for row in rows if row.get("attempted") and row[DERIVED] is not None
    )
    assert total == pytest.approx(14.3866, abs=5e-4)

    # The prose must not drift away from the data sitting next to it.
    report = (RECORD.parent / "report.md").read_text(encoding="utf-8")
    assert "$14.3866" in report
    assert "$3.0306" in report  # what the rate-refused tasks spent for nothing
    assert "derived_cost_is_provider_billed" in report


def test_every_row_names_how_the_figure_was_produced(rows):
    """A bare number invites re-derivation with a different table."""
    methods = {row["derived_cost_method"] for row in rows}
    assert len(methods) == 1
    method = methods.pop()
    assert "price_call" in method
    # The price table this run recorded for itself, so the basis is not a guess.
    assert "b01b384c532b1457804e3a77713d2b079b06b363a5ff3b8b939fe65a4cb30b4e" in method
    assert all(
        row["price_table_sha256"].startswith("b01b384c")
        for row in rows
        if row.get("attempted")
    )
