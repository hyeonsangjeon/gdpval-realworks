"""A run that measured nothing is not a run that did nothing.

``summarize_cost_receipts`` derived the run's state from ``amounts`` -- the list
of per-task figures that survived ``_measured_amount``. That list is empty
whenever every receipt sits at a $0 floor, which ``_measured_amount`` nulls on
purpose and documents in as many words: "under ``partial`` a zero means nothing
was confirmed yet, which is absence, not a floor of zero". It is also the
ordinary case, not an edge one: any run whose calls went to a model the price
table has no entry for lands there.

So a run of real paid calls, with real tokens on every one of them, fell past
``partial`` all the way to ``not_run`` -- the status whose own constructor says
"This pipeline did not run. Not free -- it did not happen."

The same expression carried a second error. ``counts["complete"] ==
len(receipts)`` counted a task that genuinely never ran against the run, so a
run of two priced tasks and one that made no call at all withheld
``estimated_cost_usd`` although every receipt under it was whole.

None of this is a new rule. Both of the other summarisers over these same
receipts already read the receipts' own states:

* ``core.cost_receipts.summarise_receipts`` drops ``not_run`` into a
  ``contributing`` list and hands it to ``_summary_status``;
* ``scripts/cost-receipt.mjs`` does the same, and says why in a comment that
  describes this exact failure -- "telling the reader that a run of 17 graded
  tasks and 1784 calls had never happened".

That JS comment ends "Mirrors ``summarize_cost_receipts`` in
batch-runner/core/cost_projection.py". It did not, on this one expression, and
the receipts on disk are enough to show it: of the 21 real published receipt
sets under ``data/grades``, the dashboard's summariser calls 21 of them
``partial`` and the Python one called 20 of them ``not_run``.

Everything below is built through a real ``CostReceiptLedger`` priced by a real
``load_receipt_price_table``, or read off real published payloads, so the
arithmetic under test is the producer's.
"""

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cost_projection import (
    _receipt_amount,
    project_cost_receipt,
    summarize_cost_receipts,
)
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    REASON_PRICE_MISSING,
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    CallUsage,
    CostReceipt,
    CostReceiptLedger,
    load_receipt_price_table,
    make_call_id,
    summarise_receipts,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRADES = REPO_ROOT / "data" / "grades"

FIELD = "problem_solving_cost"

#: The one model the fixture price table knows about. Anything else is a model
#: the table has never heard of, which is what a partial receipt is made of.
PRICED = "priced"
UNPRICED = "unheard-of"


@pytest.fixture
def prices(tmp_path):
    """A price table with exactly one provider in it."""
    document = {
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": {
            f"azure:{PRICED}": {
                "input_usd_per_million": "10",
                "cached_input_usd_per_million": "10",
                "output_usd_per_million": "20",
                "reasoning_billed_as": "output",
                "source": "fixture",
                "last_reviewed": "2026-08-31",
                "currency": "USD",
                "unit": "per 1,000,000 tokens",
            }
        },
        "runtime": {},
    }
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(document), "utf-8")
    return load_receipt_price_table(path)


def _charge(ledger, task_id, model, sequence):
    """One settled call through the ledger's own reserve/settle pair."""
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage="generation",
        retry_kind="none",
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage="generation",
        retry_kind="none",
        provider="azure",
        requested_model=model,
    )
    ledger.settle(
        call_id, usage=CallUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    )


def _receipts(tmp_path, prices, models):
    """One receipt per model named, each off a real settled call."""
    path = tmp_path / f"ledger-{'-'.join(models)}.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=prices) as ledger:
        for index, model in enumerate(models):
            _charge(ledger, f"t-{index}", model, index)
        return [
            ledger.receipt_for(f"t-{index}", BUCKET_PROBLEM_SOLVING)
            for index in range(len(models))
        ]


def _row(receipt, task_id="t"):
    return {
        "task_id": task_id,
        "status": "success",
        "deliverable_files": ["a.txt"],
        FIELD: project_cost_receipt(
            receipt.as_dict() if isinstance(receipt, CostReceipt) else receipt
        ),
    }


def _summary(receipts, **kwargs):
    rows = [_row(receipt, f"t-{index}") for index, receipt in enumerate(receipts)]
    return summarize_cost_receipts(rows, FIELD, **kwargs)


# ── The run whose every call went to a model the table does not carry ─────


def test_two_paid_calls_are_not_a_run_that_never_happened(tmp_path, prices):
    receipts = _receipts(tmp_path, prices, [UNPRICED, UNPRICED])
    assert [r.status for r in receipts] == [STATUS_PARTIAL, STATUS_PARTIAL]
    assert _summary(receipts)["status"] == STATUS_PARTIAL


def test_the_calls_really_were_made_and_really_were_unpriced(tmp_path, prices):
    """The premise, stated so a later reader can see the run was not empty."""
    receipts = _receipts(tmp_path, prices, [UNPRICED, UNPRICED])
    assert all(r.model_calls == 1 for r in receipts)
    assert all(r.usage["input_tokens"] == 1_000_000 for r in receipts)
    assert all(REASON_PRICE_MISSING in r.missing_reasons for r in receipts)


def test_no_amount_is_invented_to_go_with_the_new_status(tmp_path, prices):
    """The negative control that matters most: ``partial`` is a label, not a
    number. Nothing here was priced, so nothing here gets a figure."""
    summary = _summary(_receipts(tmp_path, prices, [UNPRICED, UNPRICED]))
    assert summary["measured_tasks"] == 0
    assert summary["known_cost_usd"] == 0.0
    assert summary["estimated_cost_usd"] is None
    assert summary["avg_cost_usd"] is None
    assert summary["max_cost_usd"] is None
    assert summary["missing_reasons"] == [REASON_PRICE_MISSING]


def test_the_run_that_genuinely_never_ran_still_says_so():
    """The status this fix has to leave alone. Three receipts, no calls behind
    any of them, and the run keeps saying it did not happen."""
    receipts = [CostReceipt.not_run() for _ in range(3)]
    assert _summary(receipts)["status"] == STATUS_NOT_RUN


def test_a_run_with_no_record_at_all_is_still_unavailable():
    receipts = [CostReceipt.unavailable() for _ in range(2)]
    assert _summary(receipts)["status"] == STATUS_UNAVAILABLE


def test_an_ordinary_priced_run_is_still_complete(tmp_path, prices):
    """The control. A run the table could price does not move."""
    receipts = _receipts(tmp_path, prices, [PRICED, PRICED])
    summary = _summary(receipts)
    assert summary["status"] == STATUS_COMPLETE
    assert summary["known_cost_usd"] == 60.0
    assert summary["estimated_cost_usd"] == 60.0


# ── A task that never ran contributed nothing, in both directions ─────────


def test_a_task_that_never_ran_no_longer_drags_a_priced_run_down(tmp_path, prices):
    receipts = [*_receipts(tmp_path, prices, [PRICED, PRICED]), CostReceipt.not_run()]
    assert _summary(receipts)["status"] == STATUS_COMPLETE


def test_and_the_total_every_receipt_supports_is_published_as_one(tmp_path, prices):
    """``estimated_cost_usd`` is the only field that claims to be a total.
    Two priced tasks and a third that made no call is $60, exactly."""
    receipts = [*_receipts(tmp_path, prices, [PRICED, PRICED]), CostReceipt.not_run()]
    summary = _summary(receipts, successful_deliverables=2)
    assert summary["known_cost_usd"] == 60.0
    assert summary["estimated_cost_usd"] == 60.0
    assert summary["cost_per_successful_deliverable_usd"] == 30.0


def test_a_task_that_never_ran_cannot_make_a_partial_run_whole(tmp_path, prices):
    """The other direction. Silence about work that did not happen adds no
    confidence to the work that did."""
    receipts = [
        *_receipts(tmp_path, prices, [PRICED, UNPRICED]),
        CostReceipt.not_run(),
    ]
    assert _summary(receipts)["status"] == STATUS_PARTIAL


def test_one_unpriced_task_still_holds_a_priced_run_to_partial(tmp_path, prices):
    """The control for the clause above: a receipt that *ran* and could not be
    priced is a hole in the total, and one is enough."""
    receipts = _receipts(tmp_path, prices, [PRICED, PRICED, UNPRICED])
    summary = _summary(receipts)
    assert summary["status"] == STATUS_PARTIAL
    # The floor is still published as a floor, never as the total.
    assert summary["known_cost_usd"] == 60.0
    assert summary["estimated_cost_usd"] is None


def test_a_task_that_never_ran_is_not_a_task_with_no_record(tmp_path, prices):
    """``unavailable`` ran and kept no record; ``not_run`` did not run. Only
    the second contributes nothing, and only the second is skipped."""
    receipts = [*_receipts(tmp_path, prices, [PRICED]), CostReceipt.unavailable()]
    assert _summary(receipts)["status"] == STATUS_PARTIAL


def test_a_row_carrying_no_receipt_at_all_still_demotes_the_run(tmp_path, prices):
    """The guard PR #315 added must survive this one. A *missing* receipt is a
    hole in the record -- nothing was skipped, something was never written --
    and it still stops the run calling itself whole."""
    rows = [_row(receipt, f"t-{i}") for i, receipt in enumerate(
        [*_receipts(tmp_path, prices, [PRICED, PRICED]), CostReceipt.not_run()]
    )]
    rows.append({"task_id": "t-unwritten", "status": "success",
                 "deliverable_files": ["a.txt"]})
    summary = summarize_cost_receipts(rows, FIELD, successful_deliverables=3)
    assert summary["status"] == STATUS_PARTIAL
    assert summary["estimated_cost_usd"] is None
    assert summary["cost_per_successful_deliverable_usd"] is None


def test_a_run_that_really_cost_nothing_by_rule_still_says_complete():
    """``CostReceipt.free`` is the one honest $0 the contract admits. It is
    ``complete``, it carries an amount of zero, and it must not be confused
    with the $0 floor that ``_measured_amount`` nulls."""
    receipts = [CostReceipt.free(), CostReceipt.free()]
    summary = _summary(receipts)
    assert summary["status"] == STATUS_COMPLETE
    assert summary["known_cost_usd"] == 0.0
    assert summary["estimated_cost_usd"] == 0.0


# ── Negative control: the label moves, the arithmetic does not ────────────


def _old_status(rows, field=FIELD):
    """The rule as it stood, so a diff can be taken against it."""
    projected = [row[field] for row in rows if isinstance(row.get(field), dict)]
    counts = {status: 0 for status in
              (STATUS_COMPLETE, STATUS_PARTIAL, STATUS_UNAVAILABLE, STATUS_NOT_RUN)}
    for receipt in projected:
        counts[receipt["status"]] += 1
    amounts = [a for r in projected if (a := _receipt_amount(r)) is not None]
    if counts[STATUS_COMPLETE] == len(projected):
        return STATUS_COMPLETE
    if amounts:
        return STATUS_PARTIAL
    if counts[STATUS_UNAVAILABLE]:
        return STATUS_UNAVAILABLE
    return STATUS_NOT_RUN


def test_the_unpriced_run_gains_a_label_and_not_a_number(tmp_path, prices):
    """Every counter and every amount is what it always was; one string moved.

    Both the old status and the new one withhold the total, so on this run even
    the two fields defined as "populated when the run is complete" are
    untouched. The whole delta is the claim itself.
    """
    receipts = _receipts(tmp_path, prices, [UNPRICED, UNPRICED])
    rows = [_row(r, f"t-{i}") for i, r in enumerate(receipts)]
    summary = summarize_cost_receipts(rows, FIELD, successful_deliverables=2)
    assert _old_status(rows) == STATUS_NOT_RUN
    assert summary["status"] == STATUS_PARTIAL
    assert summary["estimated_cost_usd"] is None
    assert summary["cost_per_successful_deliverable_usd"] is None
    assert summary["total_tasks"] == 2
    assert summary["receipt_tasks"] == 2
    assert summary["measured_tasks"] == 0
    assert summary["partial_tasks"] == 2
    assert summary["not_run_tasks"] == 0
    assert summary["coverage_pct"] == 100.0
    assert summary["failed_task_count"] == 0


def test_a_task_that_never_ran_adds_nothing_to_any_number(tmp_path, prices):
    """The same two priced tasks, with and without an idle third beside them.

    Only the three fields that count tasks move. No money figure changes, no
    reason code appears, and the status stays where it was -- which is what
    "it contributed nothing" has to mean if it is to be worth saying.
    """
    priced = _receipts(tmp_path, prices, [PRICED, PRICED])
    rows = [_row(r, f"t-{i}") for i, r in enumerate(priced)]
    without = summarize_cost_receipts(rows, FIELD, successful_deliverables=2)
    beside = summarize_cost_receipts(
        [*rows, _row(CostReceipt.not_run(), "t-idle")],
        FIELD,
        successful_deliverables=2,
    )
    moved = {key for key in without if without[key] != beside[key]}
    assert moved == {"total_tasks", "receipt_tasks", "not_run_tasks"}
    assert (without["status"], beside["status"]) == (STATUS_COMPLETE, STATUS_COMPLETE)
    assert without["estimated_cost_usd"] == beside["estimated_cost_usd"] == 60.0


def test_the_pre_instrumentation_run_still_reads_as_no_record():
    """A run from before any of this existed carries no receipts at all, and
    the function still returns ``None`` rather than inventing a status."""
    rows = [{"task_id": "t-0", "status": "success", "deliverable_files": ["a.txt"]}]
    assert summarize_cost_receipts(rows, FIELD) is None


# ── The two summarisers this is being brought into line with ──────────────


def _one_of(status, tmp_path, prices):
    if status == STATUS_COMPLETE:
        return _receipts(tmp_path, prices, [PRICED])[0]
    if status == STATUS_PARTIAL:
        return _receipts(tmp_path, prices, [UNPRICED])[0]
    if status == STATUS_UNAVAILABLE:
        return CostReceipt.unavailable()
    return CostReceipt.not_run()


@pytest.mark.parametrize(
    "mix",
    [
        mix
        for size in (1, 2, 3)
        for mix in itertools.combinations_with_replacement(
            (STATUS_COMPLETE, STATUS_PARTIAL, STATUS_UNAVAILABLE, STATUS_NOT_RUN),
            size,
        )
    ],
)
def test_both_python_summarisers_answer_alike_for_every_mix(tmp_path, prices, mix):
    """Thirty-four combinations of up to three receipts, each built through the
    producer, put through both layers. One set of receipts, one answer.

    ``summarise_receipts`` rolls ``CostReceipt`` objects; ``summarize_cost_receipts``
    rolls the projected dicts a published payload carries. Before, they parted
    company on any mix with no measurable amount in it, and on any mix holding a
    task that never ran.
    """
    receipts = [_one_of(status, tmp_path, prices) for status in mix]
    assert _summary(receipts)["status"] == summarise_receipts(receipts).status


# ── Measured on the receipts that are actually published ──────────────────


def _published_receipt_sets():
    """Every real per-task receipt set under ``data/grades``, projected.

    Yields ``(path, field, receipts)``. These are the receipts the grading
    pipeline writes today; the shape they have in production is the shape this
    function has to read correctly.
    """
    for path in sorted(GRADES.rglob("*.json")):
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        rows = doc.get("tasks")
        if not isinstance(rows, list) or not rows:
            continue
        for field in (BUCKET_PROBLEM_SOLVING, "grading_cost"):
            receipts = [
                CostReceipt.from_dict(row[field])
                for row in rows
                if isinstance(row, dict) and isinstance(row.get(field), dict)
            ]
            if receipts:
                yield path, field, receipts


def test_the_published_receipts_are_the_shape_that_used_to_disappear():
    """Blast radius, measured rather than asserted.

    Every published receipt set is folded both ways. The old rule called 20 of
    the 21 ``not_run`` -- twenty real graded shards, thousands of judge calls
    between them, reported as work that never happened. The new rule agrees
    with ``summarise_receipts`` on all 21.

    This is the check that has to keep passing. If a future edit makes the two
    layers disagree about a payload that is actually on disk, this fails with
    the path in hand.
    """
    seen = moved = 0
    for path, field, receipts in _published_receipt_sets():
        seen += 1
        rows = [
            {"task_id": f"t-{index}", "status": "success",
             "deliverable_files": ["a.txt"], field: project_cost_receipt(r.as_dict())}
            for index, r in enumerate(receipts)
        ]
        summary = summarize_cost_receipts(rows, field)
        assert summary["status"] == summarise_receipts(receipts).status, path
        if summary["status"] != _old_status(rows, field):
            moved += 1
    assert seen >= 21, f"expected the published receipt sets to still be there, saw {seen}"
    assert moved, "expected the published receipts to include the shape this fixes"


def test_no_payload_on_disk_carries_a_summary_this_function_wrote():
    """So no published file changes what it says.

    ``summarize_cost_receipts`` is reached only from ``step3_format_results``
    and ``step6_report``, both on the inference side, and their output lands in
    ``results/`` on the runner rather than in this repository. The grade
    payloads that *are* committed carry a summary written by
    ``core.cost_receipts.summarise_receipts``, which has always applied the
    rule this change ports. The receipts above are therefore real evidence of
    the shape, and the blast radius on committed files is still zero.

    Committed means tracked, not present. This walked the directory tree, which
    also reaches build output: ``public/generated/reports-index.json`` carries
    three run summaries fetched from HuggingFace, and ``dist/`` carries a copy
    of the same file. Both are ignored, neither is in a clone, and running
    ``npm run build`` before ``pytest`` was enough to fail this on a claim about
    what a clone contains. ``git ls-files`` is the set the sentence is about.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.json"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.split("\0")

    found = []
    for name in tracked:
        if not name:
            continue
        path = REPO_ROOT / name
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeDecodeError, OSError):
            continue
        stack = [doc]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if "receipt_tasks" in node and "coverage_pct" in node:
                    found.append(path)
                    break
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    assert found == [], f"a committed payload now carries a run-level summary: {found}"
