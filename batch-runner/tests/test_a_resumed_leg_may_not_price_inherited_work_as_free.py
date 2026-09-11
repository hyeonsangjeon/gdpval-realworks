"""A relay leg that resumed must not report its predecessor's work as free.

The exp035 relay hands a leg its predecessor's **progress** and an **empty
ledger**. So a resumed leg's artifact holds the whole lineage's outcomes and
only its own calls, and every task it inherited looks — to the only ledger it
has — exactly like a task nobody ever called.

Those two states are opposites, and the record has a name for only one of them.
``no_call_made`` means never reached, and carries ``0.0`` because that really is
what a task nobody attempted cost. Reaching for it to describe an inherited task
prints ``$0.00`` over work an earlier leg paid for. Run 34631861765's record was
built that way once: 58 attempted tasks, each with a status, a file count and a
stream-item count, all filed as ``no_call_made`` at ``$0.00`` — while leg 3's
ledger held their settled ``gpt-5.4`` calls.

`test_a_derived_cost_is_never_a_billed_cost.py` already states the rule those
rows broke: ``no_call_made`` asserts ``not row["attempted"]``. It could not
catch this, because it reads leg 0's record — the one leg that inherited
nothing. The defect only exists on a leg that resumed, so this file builds one.

Both ledgers here are written through `CostReceiptLedger` rather than hand-rolled
SQL, so a schema change breaks this test instead of leaving it asserting over a
shape the runner no longer produces. Nothing here contacts a provider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from core.cost_receipts import (
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_partial_run_record import build  # noqa: E402

MODEL = "gpt-5.4"

#: Three tasks: one the earlier leg paid for, one this leg paid for, one the
#: relay never reached. Only the third is free, and only it may say so.
INHERITED, OWN, UNREACHED = "task-inherited", "task-own", "task-unreached"


def _settle(ledger: CostReceiptLedger, call_id: str, task_id: str) -> None:
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage="generation",
        retry_kind="none",
        provider="azure",
        requested_model=MODEL,
        deployment=MODEL,
        api_version="v1",
        note="one Codex turn",
    )
    ledger.settle(
        call_id=call_id,
        resolved_model=MODEL,
        usage=CallUsage(
            input_tokens=50_000,
            cached_input_tokens=0,
            output_tokens=2_000,
            reasoning_tokens=0,
            audio_input_tokens=0,
            audio_output_tokens=0,
        ),
        extra_reasons=["call_reachability_unknown"],
    )


@pytest.fixture()
def relay(tmp_path: Path) -> tuple[Path, Path]:
    """A resumed leg's artifact, plus the earlier leg's ledger beside it.

    The artifact's own ledger covers `OWN` only — which is the whole point.
    `INHERITED` is settled in the earlier leg's ledger and appears in this
    leg's progress file as a finished task, exactly as the relay leaves it.
    """
    artifact = tmp_path / "batch-results-2"
    workspace = artifact / "workspace"
    workspace.mkdir(parents=True)

    table = load_receipt_price_table()
    earlier = tmp_path / "leg1_cost_ledger_condition_a.sqlite3"
    _settle(CostReceiptLedger(earlier, run_id="leg1", price_table=table), "c1", INHERITED)
    _settle(
        CostReceiptLedger(
            workspace / "cost_ledger_condition_a.sqlite3", run_id="leg2", price_table=table
        ),
        "c2",
        OWN,
    )

    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"task_id": t, "sector": "Sector", "occupation": "Occupation"}
                    for t in (INHERITED, OWN, UNREACHED)
                ]
            }
        ),
        encoding="utf-8",
    )
    (workspace / "step2_inference_progress_condition_a.json").write_text(
        json.dumps(
            {
                "ordered_task_ids": [INHERITED, OWN, UNREACHED],
                "results": [
                    # Restored from leg 1's checkpoint: a finished task this
                    # leg never called, and whose calls it therefore cannot see.
                    {
                        "task_id": INHERITED,
                        "status": "success",
                        "observability": {"codex": {"items_seen": 12}},
                    },
                    {
                        "task_id": OWN,
                        "status": "success",
                        "observability": {"codex": {"items_seen": 40}},
                    },
                    # The checkpoint fills `error` for untried tasks too.
                    {
                        "task_id": UNREACHED,
                        "status": "pending",
                        "error": "task_execution_error:TaskExecutionError",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return artifact, earlier


def _by_task(rows: list[dict]) -> dict[str, dict]:
    return {row["task_id"]: row for row in rows}


def test_an_inherited_task_is_not_priced_as_never_called(relay) -> None:
    """The defect itself: without the earlier ledger, and with it.

    Neither answer is ``no_call_made``. Without the predecessor's ledger the
    honest report is that the amount cannot be seen from here; with it, the
    amount is simply the amount.
    """
    artifact, earlier = relay

    alone, _, _ = build(artifact, log=None)
    inherited = _by_task(alone)[INHERITED]
    assert inherited["attempted"] is True
    assert inherited["derived_cost_basis"] == "absent_from_supplied_ledgers"
    assert inherited["derived_cost_usd_from_measured_tokens"] is None, (
        "an inherited task was priced at a number this leg's ledger cannot "
        "support; $0.00 here is the bug this file exists for"
    )

    both, _, _ = build(artifact, log=None, extra_ledgers=[earlier])
    inherited = _by_task(both)[INHERITED]
    assert inherited["derived_cost_basis"] == "all_calls_measured"
    assert inherited["derived_cost_usd_from_measured_tokens"] > 0
    assert inherited["resolved_model"] == MODEL
    assert inherited["input_tokens"] == 50_000


def test_no_attempted_task_anywhere_claims_a_true_zero(relay) -> None:
    """The invariant, stated once and checked both ways round.

    ``no_call_made`` is the one basis that carries ``0.0``, so it is the one
    basis an attempted task may never hold. Pinned separately from the case
    above because it is the property that matters: a future basis added for
    some third reason must not quietly become another way to say free.
    """
    artifact, earlier = relay
    for extra in ([], [earlier]):
        rows, _, _ = build(artifact, log=None, extra_ledgers=extra)
        zeroed = [
            row["task_id"]
            for row in rows
            if row["attempted"] and row["derived_cost_basis"] == "no_call_made"
        ]
        assert zeroed == [], f"attempted, yet recorded as never called: {zeroed}"


def test_the_task_the_relay_never_reached_still_reads_as_a_true_zero(relay) -> None:
    """The fix must not cost the record the one zero it is entitled to.

    Widening ``absent_from_supplied_ledgers`` over every unledgered row would
    turn 118 never-started tasks into 118 unknowns and lose the distinction in
    the other direction.
    """
    artifact, earlier = relay
    rows, _, _ = build(artifact, log=None, extra_ledgers=[earlier])
    unreached = _by_task(rows)[UNREACHED]
    assert unreached["attempted"] is False
    assert unreached["outcome"] == "never_started"
    assert unreached["derived_cost_basis"] == "no_call_made"
    assert unreached["derived_cost_usd_from_measured_tokens"] == 0.0
    assert unreached["checkpoint_error_field_is_placeholder"] is True


def test_the_two_ledgers_are_summed_not_replaced(relay) -> None:
    """Each leg's calls land in the same record, once each."""
    artifact, earlier = relay
    rows, _, derived = build(artifact, log=None, extra_ledgers=[earlier])
    assert derived["calls_total"] == 2
    assert derived["calls_measured"] == 2
    assert derived["tasks_with_a_call"] == 2

    priced = {
        row["task_id"]: row["derived_cost_usd_from_measured_tokens"]
        for row in rows
        if row["attempted"]
    }
    assert set(priced) == {INHERITED, OWN}
    # Same tokens, same model, same table: the two legs must price alike.
    assert priced[INHERITED] == priced[OWN]
    assert derived["derived_total_usd"] == pytest.approx(
        priced[INHERITED] + priced[OWN], abs=1e-6
    )
