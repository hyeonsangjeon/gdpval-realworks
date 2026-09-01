"""A run-summary row is one model's calls, not one label's.

``summarise_receipts`` was taught this in test_every_call_belonged_to_a_stage.py
and keys a merged line by the seven fields the producer groups on. The two
readers *downstream* of the same receipts were not: both
``core.cost_projection.summarize_cost_receipts`` and ``aggregateComponents`` in
``scripts/cost-receipt.mjs`` folded a run's lines by ``components[].name``, and
handed the result to ``report_data.json`` and to the dashboard.

``name`` cannot carry that weight. It is *derived*::

    return self.stage if self.retry_kind == RETRY_NONE else COMPONENT_RETRY

so every retry at every stage derives ``retry`` and both perception models
derive ``perception``. Folding by it is lossy by construction, and the loss is
published. On the run whose inference is at
``HyeonSang/exp026c_cost_receipt_smoke``, one task's four lines::

    generation      none      $0.089673   1 call
    generation      resume    $0.178985   2 calls
    self_qa         none      $0.005792   1 call
    self_qa         resume    $0.011062   2 calls

arrived in ``cost_summary`` as three, the middle one reading::

    {"name": "retry", "known_cost_usd": 0.190047, "model_calls": 4}

$0.178985 + $0.011062 over two different stages, in one row, under a label that
names neither. Under ``perception`` it is worse than untidy: a visual reader and
an audio reader are priced from different entries, so their summed tokens are a
figure no price table can reproduce.

Two more things went missing with the key. Identity -- provider, deployment,
requested and resolved model, API version -- was dropped, so a reader could not
tell which model a row was even when the receipt underneath it knew. And
``missing_reasons`` was dropped outright: the bucket had no such field, so "no
rate is published for this model" reached the run and never the row, leaving a
reader who could see that something was unpriced with no way to see *what*.

Everything below is built through a real ``CostReceiptLedger`` priced by a real
``load_receipt_price_table``, serialised the way a published payload is, and
read back through the real projection -- so the arithmetic under test is the
producer's, end to end.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

BATCH_RUNNER = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

from core.cost_projection import project_cost_receipt, summarize_cost_receipts
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_PRICE_MISSING,
    RETRY_NONE,
    RETRY_RESUME,
    STAGE_GENERATION,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STAGE_SELF_QA,
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
    make_call_id,
)

MIRROR = BATCH_RUNNER.parent / "scripts" / "cost-receipt.mjs"

#: Two models a run really does call under one stage, at rates far enough apart
#: that a summed row could not be mistaken for either of them.
VISION = "sees-things"
AUDIO = "hears-things"
#: A third the fixture table has no entry for, so a row can go unpriced beside
#: a row that did not.
UNPRICED = "unheard-of"

#: One million in, one million out.
CALL_TOKENS = 1_000_000
VISION_PER_CALL = 30  # $10 in + $20 out
AUDIO_PER_CALL = 300  # $100 in + $200 out


@pytest.fixture
def prices(tmp_path):
    def entry(input_rate, output_rate):
        return {
            "input_usd_per_million": str(input_rate),
            "cached_input_usd_per_million": str(input_rate),
            "output_usd_per_million": str(output_rate),
            "reasoning_billed_as": "output",
            "source": "fixture",
            "last_reviewed": "2026-09-01",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        }

    document = {
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": {
            f"azure:{VISION}": entry(10, 20),
            f"azure:{AUDIO}": entry(100, 200),
        },
        "runtime": {},
    }
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(document), "utf-8")
    return load_receipt_price_table(path)


def _summary(tmp_path, prices, plan, *, bucket=BUCKET_PROBLEM_SOLVING):
    """One run's summary, from the ledger through the published shape.

    ``plan`` is ``{task_id: [(stage, retry_kind, model), ...]}``. Each call is
    reserved and settled through the ledger's own pair, the receipt is written
    the way a payload carries it, and it is read back through the projection
    the dashboard and the report both read it through.
    """
    field = (
        "grading_cost" if bucket == BUCKET_GRADING else "problem_solving_cost"
    )
    path = tmp_path / "ledger.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=prices) as ledger:
        sequence = 0
        for task_id, calls in plan.items():
            for stage, retry_kind, model in calls:
                call_id = make_call_id(
                    run_id=ledger.run_id,
                    task_id=task_id,
                    stage=stage,
                    retry_kind=retry_kind,
                    attempt_index=0,
                    sequence=sequence,
                )
                sequence += 1
                ledger.reserve(
                    call_id=call_id,
                    task_id=task_id,
                    stage=stage,
                    retry_kind=retry_kind,
                    provider="azure",
                    requested_model=model,
                )
                ledger.settle(
                    call_id,
                    usage=CallUsage(
                        input_tokens=CALL_TOKENS, output_tokens=CALL_TOKENS
                    ),
                )
        receipts = {
            task_id: ledger.receipt_for(task_id, bucket) for task_id in plan
        }
    rows = [
        {
            "task_id": task_id,
            "status": "success",
            field: project_cost_receipt(receipt.as_dict()),
        }
        for task_id, receipt in receipts.items()
    ]
    return summarize_cost_receipts(rows, field)


def _row(summary, stage, retry_kind=RETRY_NONE, model=None):
    """The one row for this stage, retry kind and model."""
    found = [
        entry
        for entry in summary["components"]
        if entry["stage"] == stage
        and entry["retry_kind"] == retry_kind
        and (model is None or entry["requested_model"] == model)
    ]
    assert len(found) == 1, f"expected one row, got {found}"
    return found[0]


# ── two stages that both retried ──────────────────────────────────────────


def test_two_stages_that_both_retried_are_two_rows(tmp_path, prices):
    """The published defect, in the shape it was published in.

    One task redid its generation and redid its self-review. Both lines derive
    the name ``retry``, and the run summary used to add them together.
    """
    summary = _summary(tmp_path, prices, {
        "task-a": [
            (STAGE_GENERATION, RETRY_NONE, VISION),
            (STAGE_GENERATION, RETRY_RESUME, VISION),
            (STAGE_GENERATION, RETRY_RESUME, VISION),
            (STAGE_SELF_QA, RETRY_NONE, VISION),
            (STAGE_SELF_QA, RETRY_RESUME, VISION),
            (STAGE_SELF_QA, RETRY_RESUME, VISION),
        ],
    })

    retries = [
        entry for entry in summary["components"] if entry["name"] == "retry"
    ]
    assert len(retries) == 2
    assert {entry["stage"] for entry in retries} == {
        STAGE_GENERATION, STAGE_SELF_QA
    }
    for entry in retries:
        assert entry["known_cost_usd"] == 2 * VISION_PER_CALL
        assert entry["model_calls"] == 2

    # The whole run still adds up to what the ledger charged, so this splits a
    # row rather than inventing or dropping one.
    assert sum(e["known_cost_usd"] for e in summary["components"]) == (
        6 * VISION_PER_CALL
    )
    assert sum(e["model_calls"] for e in summary["components"]) == 6


def test_the_label_is_kept_beside_the_row_not_used_as_the_row(tmp_path, prices):
    """``name`` still travels -- it is what a reader shows.

    Dropping it would have been the other half of the same mistake: the fix is
    that the label stops *identifying* a row, not that it stops being written.
    """
    summary = _summary(tmp_path, prices, {
        "task-a": [
            (STAGE_GENERATION, RETRY_NONE, VISION),
            (STAGE_GENERATION, RETRY_RESUME, VISION),
        ],
    })
    assert [entry["name"] for entry in summary["components"]] == [
        "generation", "retry"
    ]


# ── two models under one stage ────────────────────────────────────────────


def test_two_models_under_one_stage_are_two_rows(tmp_path, prices):
    """Grading a deliverable with a picture and a recording in it.

    A visual reader and an audio reader both run under ``perception``. Their
    tokens are priced from different entries, so one row of their sum is a
    figure neither entry produces: here $330 against a table that can only make
    $30 and $300.
    """
    summary = _summary(
        tmp_path, prices,
        {
            "task-a": [
                (STAGE_GRADING, RETRY_NONE, VISION),
                (STAGE_PERCEPTION, RETRY_NONE, VISION),
                (STAGE_PERCEPTION, RETRY_NONE, AUDIO),
            ],
        },
        bucket=BUCKET_GRADING,
    )

    perception = [
        entry
        for entry in summary["components"]
        if entry["stage"] == STAGE_PERCEPTION
    ]
    assert len(perception) == 2
    assert {entry["requested_model"] for entry in perception} == {VISION, AUDIO}
    assert _row(summary, STAGE_PERCEPTION, model=VISION)["known_cost_usd"] == (
        VISION_PER_CALL
    )
    assert _row(summary, STAGE_PERCEPTION, model=AUDIO)["known_cost_usd"] == (
        AUDIO_PER_CALL
    )
    # Both rows carry the same label, which is exactly why the label cannot be
    # what tells them apart.
    assert {entry["name"] for entry in perception} == {"perception"}


def test_the_row_carries_the_identity_that_makes_it_priceable(tmp_path, prices):
    """Every field the receipt was keyed by reaches the summary row.

    Keeping the split while dropping the identity would leave a reader two rows
    they still cannot tell apart -- and ``requested_model`` alone does not do
    it, which is the reason the key is seven fields rather than three.
    """
    summary = _summary(
        tmp_path, prices,
        {"task-a": [(STAGE_PERCEPTION, RETRY_NONE, AUDIO)]},
        bucket=BUCKET_GRADING,
    )
    row = _row(summary, STAGE_PERCEPTION, model=AUDIO)
    assert row["provider"] == "azure"
    assert row["requested_model"] == AUDIO
    assert row["resolved_model"] == AUDIO
    # Not recorded by this run, and absent stays absent rather than defaulting
    # to a name nothing was called under.
    assert row["deployment"] is None
    assert row["api_version"] is None


# ── why a row could not be priced ─────────────────────────────────────────


def test_a_missing_reason_names_the_row_it_belongs_to(tmp_path, prices):
    """Two models under one stage, one of them unpriced.

    The run has always said *that* something went unpriced. Until now it could
    not say *which*, because the reason was kept only at the run level while
    the two models shared a row.
    """
    summary = _summary(
        tmp_path, prices,
        {
            "task-a": [
                (STAGE_PERCEPTION, RETRY_NONE, VISION),
                (STAGE_PERCEPTION, RETRY_NONE, UNPRICED),
            ],
        },
        bucket=BUCKET_GRADING,
    )

    priced = _row(summary, STAGE_PERCEPTION, model=VISION)
    unpriced = _row(summary, STAGE_PERCEPTION, model=UNPRICED)
    assert priced["missing_reasons"] == []
    assert priced["status"] == "complete"
    assert REASON_PRICE_MISSING in unpriced["missing_reasons"]
    assert unpriced["status"] == "partial"
    # The run still says it, too. The row is where to act on it; the run is
    # where a reader learns to look.
    assert REASON_PRICE_MISSING in summary["missing_reasons"]


def test_an_unpriced_row_is_not_a_free_row(tmp_path, prices):
    """A model with no published rate cost real money.

    ``0.0`` on a partial row is a floor, and it sits beside a reason that says
    so. What must never happen is that floor reading as a price.
    """
    summary = _summary(
        tmp_path, prices,
        {"task-a": [(STAGE_PERCEPTION, RETRY_NONE, UNPRICED)]},
        bucket=BUCKET_GRADING,
    )
    row = _row(summary, STAGE_PERCEPTION, model=UNPRICED)
    assert row["model_calls"] == 1
    assert row["status"] == "partial"
    assert row["missing_reasons"] != []
    assert summary["estimated_cost_usd"] is None


# ── what the split must not break ─────────────────────────────────────────


def test_one_task_is_one_task_in_every_row_it_paid(tmp_path, prices):
    """The guard the fold was written for, which the split must keep.

    ``tasks`` sits beside the amount as "how many tasks paid this". No row may
    claim more tasks than the run contains, however many lines a task carried.
    """
    summary = _summary(tmp_path, prices, {
        "task-a": [
            (STAGE_GENERATION, RETRY_NONE, VISION),
            (STAGE_GENERATION, RETRY_RESUME, VISION),
            (STAGE_GENERATION, RETRY_RESUME, VISION),
            (STAGE_SELF_QA, RETRY_RESUME, VISION),
        ],
        "task-b": [
            (STAGE_GENERATION, RETRY_NONE, VISION),
        ],
    })
    assert summary["receipt_tasks"] == 2
    for entry in summary["components"]:
        assert 1 <= entry["tasks"] <= 2
    assert _row(summary, STAGE_GENERATION)["tasks"] == 2
    assert _row(summary, STAGE_GENERATION, RETRY_RESUME)["tasks"] == 1


def test_a_receipt_that_recorded_no_identity_still_sorts(tmp_path, prices):
    """Every receipt published before call identity existed is in this state.

    ``None`` and ``str`` do not compare in Python 3, so the case this change
    exists to keep visible must not be the case that raises on the way out.
    """
    summary = _summary(tmp_path, prices, {
        "task-a": [(STAGE_GENERATION, RETRY_NONE, VISION)],
    })
    stripped = [
        {**entry, "provider": None, "resolved_model": None}
        for entry in summary["components"]
    ]
    receipt = {
        "schema_version": "cost-receipt-v1",
        "currency": "USD",
        "status": "complete",
        "estimated_cost_usd": VISION_PER_CALL,
        "known_cost_usd": VISION_PER_CALL,
        "model_cost_usd": VISION_PER_CALL,
        "runtime_cost_usd": None,
        "model_calls": 1,
        "usage": {"input_tokens": CALL_TOKENS},
        "components": [
            {
                "name": entry["name"],
                "stage": entry["stage"],
                "retry_kind": entry["retry_kind"],
                "status": "complete",
                "known_cost_usd": entry["known_cost_usd"],
                "model_calls": entry["model_calls"],
                "usage": {},
                "missing_reasons": [],
            }
            for entry in stripped
        ],
        "price_table_sha256": "a" * 64,
        "missing_reasons": [],
    }
    rebuilt = summarize_cost_receipts(
        [{
            "task_id": "task-a",
            "status": "success",
            "problem_solving_cost": project_cost_receipt(receipt),
        }],
        "problem_solving_cost",
    )
    row = _row(rebuilt, STAGE_GENERATION)
    assert row["provider"] is None
    assert row["known_cost_usd"] == VISION_PER_CALL


def test_the_row_count_stays_inside_what_a_receipt_may_carry(tmp_path, prices):
    """Identity is the axis that consumes the headroom, so it is checked.

    A published receipt may carry thirty-two lines. Splitting by identity makes
    the summary wider than splitting by label did, and the bound on how much
    wider is the run's own config -- the stages times the models named for
    them -- not the run's size. Two tasks over the same six identities are six
    rows, not twelve.
    """
    plan = [
        (STAGE_GENERATION, RETRY_NONE, VISION),
        (STAGE_GENERATION, RETRY_RESUME, VISION),
        (STAGE_GENERATION, RETRY_NONE, AUDIO),
        (STAGE_SELF_QA, RETRY_NONE, VISION),
        (STAGE_SELF_QA, RETRY_RESUME, VISION),
        (STAGE_SELF_QA, RETRY_NONE, AUDIO),
    ]
    summary = _summary(
        tmp_path, prices, {"task-a": plan, "task-b": plan, "task-c": plan}
    )
    assert len(summary["components"]) == len(plan)
    assert all(entry["tasks"] == 3 for entry in summary["components"])


# ── the reader on the other side ──────────────────────────────────────────


def test_the_javascript_mirror_keys_rows_the_same_way():
    """The dashboard reads these receipts too, and a drifted mirror is the
    same defect on the screen a reader actually looks at.

    Read as text rather than run, which is the convention the rest of this
    suite uses for the mirror: the backend suite has no Node. The behaviour is
    asserted next to the mirror itself, in
    ``scripts/__tests__/cost-receipt.test.mjs``.
    """
    source = MIRROR.read_text("utf-8")
    aggregator = re.search(
        r"function aggregateComponents\(receipts\) \{.*?\n\}", source, re.S
    )
    assert aggregator, "aggregateComponents is no longer where the mirror keeps it"
    body = aggregator.group(0)

    # The defect, in the exact shape it had: the displayed label used as the
    # key of the per-receipt roll and of the run totals.
    assert "rolled.has(component.name)" not in body
    assert "totals.has(name)" not in body

    # And the rule that replaced it.
    assert "summaryComponentKey(component)" in body
    assert "missing_reasons" in body

    key = re.search(
        r"function summaryComponentKey\(component\) \{.*?\n\}", source, re.S
    )
    assert key, "the mirror no longer names its key function"
    for field in ("stage", "retry_kind", "COMPONENT_IDENTITY"):
        assert field in key.group(0)
