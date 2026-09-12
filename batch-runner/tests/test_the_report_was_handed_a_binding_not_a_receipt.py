"""The report was handed a binding where a receipt was wanted.

On 2026-09-11 the second paid ``advance_check_5`` dispatch became the first V2
run ever to reach the model. It asked, was answered, and both calls settled into
the ledger. Then it died on task one of five::

    core.agentic_v2_run_report.ReportRowRefused: None is not a receipt status

``receipt_for`` -- the callback the driver asks for each finished task's cost --
returned :func:`~core.agentic_v2_cost_binding.bind_run_to_ledger`'s value. That
is a note of what was written: task id, bucket, the call ids settled. It is not
a receipt and has no ``status``. The report asks for one and refuses a row it
cannot state a cost standing for, which is the right refusal; the value handed
to it was simply the wrong object.

The damage is where the two defects differ. The ledger defect a day earlier was
a ``TypeError`` before anything was asked, and cost nothing. This one waited
until after the calls had been made and charged for, then threw away the run
record and the deliverables with it. Same shape both times -- a paid-only line
that no free job executes -- and that shape is what these tests are about more
than the one-line fix.

Two things are held here beyond "it works now":

* the paid path and the dry run go through **one** function, so the certifying
  path cannot drift from the certified one, and
* a call this repo has no price for settles ``partial``, never a real ``$0``.
  A receipt that rounded an unknown amount to zero would be the one number in
  the record that reads as a measurement.

The second point was first written here with a wrong premise attached: that the
pinned deployment was not in the committed price table, so every V2 call was
unpriced by necessity. It is in the table. The nulls came from
``open_the_ledger`` building the ledger without handing it that table, which
marks every call ``price_missing`` whatever the file says. Corrected, with the
fix and its own test, in the same change that added
``test_the_pinned_model_is_priced_and_settles_complete`` below.

Nothing here calls a model or reaches the network. The ledger is real and
sqlite-backed in a temporary directory; the turns are fabricated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

SCRIPTS = BATCH_RUNNER_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_agentic_v2_stage as stage  # noqa: E402
from core.agentic_v2_cost_binding import ModelTurn, bind_run_to_ledger  # noqa: E402
from core.agentic_v2_run_report import (  # noqa: E402
    ReportRowRefused,
    build_agentic_v2_metrics,
    build_result_row,
)
from core.agentic_v2_task_journal import TaskStanding  # noqa: E402
from core.cost_receipts import (  # noqa: E402
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    CallUsage,
)

STAGE_SOURCE = (SCRIPTS / "run_agentic_v2_stage.py").read_text()


def _turn(task_id: str, call: str = "call-1", model: str = "gpt-5.4", **usage: int) -> ModelTurn:
    """One model call, named the way the real run names them.

    ``model`` defaults to the pinned name, which the committed price list
    covers. Pass a name it does not cover to build a genuinely unpriced call.
    """
    return ModelTurn(
        call_id=f"a-run:{task_id}:1:{call}",
        usage=CallUsage(
            input_tokens=usage.get("input_tokens", 2322),
            output_tokens=usage.get("output_tokens", 22),
        ),
        provider="azure",
        requested_model=model,
        deployment="gpt-5.4",
        resolved_model=model,
    )


def _standing(task_id: str, attempts: int = 1) -> TaskStanding:
    return TaskStanding(
        task_id=task_id,
        attempts=attempts,
        abandoned_attempts=0,
        last_closed=None,
        decision="ran",
        reason="test",
    )


# ── what the run died of ────────────────────────────────────────────────────


def test_the_binding_has_no_status_and_the_report_says_so(tmp_path):
    """The defect itself, reproduced against the real functions.

    Not a regression test for a typo: it pins *why* the report refused, so a
    later change that gives the binding a ``status`` key does not quietly make
    this pass while still filing call ids in the row's cost field.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        binding = bind_run_to_ledger(
            ledger, task_id="t1", model_turns=(_turn("t1"),)
        )
    finally:
        ledger.close()

    assert "status" not in binding
    assert set(binding) == {
        "task_id",
        "bucket",
        "settled_call_ids",
        "runtime_entry_id",
        "grading_bucket_untouched",
    }

    with pytest.raises(ReportRowRefused) as refused:
        build_agentic_v2_metrics(
            {"success": True},
            standing=_standing("t1"),
            task_wall_time_ms=1.0,
            receipt=binding,
        )
    assert "not a receipt status" in str(refused.value)


def test_a_settled_task_now_reaches_a_report_row(tmp_path):
    """The whole stretch the paid run died in, end to end.

    Ledger, binding, receipt, metrics, row. Every one of these is the real
    function the run calls; a double anywhere in this chain would have let the
    original defect through, because every part of it worked in isolation.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        receipt = stage.settle_into_a_receipt(
            ledger, task_id="t1", model_turns=(_turn("t1"),)
        )
    finally:
        ledger.close()

    metrics = build_agentic_v2_metrics(
        {"success": True},
        standing=_standing("t1"),
        task_wall_time_ms=1.0,
        receipt=receipt,
    )
    row = build_result_row(
        {"success": True},
        task_id="t1",
        standing=_standing("t1"),
        deliverable_files=("deliverables/t1/answer.md",),
        latency_ms=1.0,
        metrics=metrics,
        receipt=receipt,
    )

    assert row["problem_solving_cost"]["status"] == receipt["status"]
    assert metrics["agentic_v2_cost_receipt_status"] == receipt["status"]


def test_the_failed_task_the_run_actually_had_also_builds_a_row(tmp_path):
    """Task one ended ``capability_unavailable`` and still needed a row.

    A run whose first task fails must be able to say so. The crash took the
    failure with it, so the artifact carried no record of the ending at all --
    the reason had to be read out of a job log.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        receipt = stage.settle_into_a_receipt(
            ledger, task_id="t1", model_turns=(_turn("t1"),)
        )
    finally:
        ledger.close()

    record = {"success": False, "error": "capability_unavailable"}
    metrics = build_agentic_v2_metrics(
        record, standing=_standing("t1"), task_wall_time_ms=1.0, receipt=receipt
    )
    row = build_result_row(
        record,
        task_id="t1",
        standing=_standing("t1"),
        latency_ms=1.0,
        metrics=metrics,
        receipt=receipt,
    )

    assert row["status"] == "error"
    assert row["error"] == "capability_unavailable"
    assert row["problem_solving_cost"]["status"] == receipt["status"]


# ── what the amount is allowed to say ───────────────────────────────────────


def test_an_unpriced_call_is_partial_and_not_a_zero(tmp_path):
    """An amount that is not known must not be published as a zero.

    Written first in the belief that this was the state of *every* V2 call --
    that ``gpt-5.4`` had no entry in the committed price table. That was wrong
    and the correction is in the test below: the entry exists, and the nulls
    came from the ledger being opened without the table. The rule this test
    holds is unchanged and still worth holding, so it is exercised here on a
    model that genuinely has no price: the tokens are known, the amount is not,
    and ``partial`` with a null estimate is the true sentence. A ``0.0`` would
    be indistinguishable from a task that really cost nothing.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        receipt = stage.settle_into_a_receipt(
            ledger,
            task_id="t1",
            model_turns=(_turn("t1", model="a-model-nobody-priced"),),
        )
    finally:
        ledger.close()

    assert receipt["status"] == STATUS_PARTIAL
    assert receipt["estimated_cost_usd"] is None
    assert "price_missing" in receipt["missing_reasons"]
    assert receipt["model_calls"] == 1
    assert receipt["usage"]["input_tokens"] == 2322
    assert receipt["usage"]["output_tokens"] == 22


def test_the_pinned_model_is_priced_and_settles_complete(tmp_path):
    """The correction, asserted rather than described.

    ``azure:gpt-5.4`` is in the committed price list. Every V2 receipt read
    ``partial`` anyway because ``open_the_ledger`` built the ledger without
    handing it that list, and a ledger with no list marks every call
    ``price_missing`` whatever the file says. Fixed in the same change as this
    test; without this line the fix is silent and reversible.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        receipt = stage.settle_into_a_receipt(
            ledger, task_id="t1", model_turns=(_turn("t1"),)
        )
    finally:
        ledger.close()

    assert receipt["status"] == STATUS_COMPLETE
    assert receipt["missing_reasons"] == []
    assert receipt["estimated_cost_usd"] is not None
    assert receipt["estimated_cost_usd"] > 0


def test_a_partial_receipt_does_not_mark_the_task_cost_accounted(tmp_path):
    """``usage_complete`` must stay false while the amount is unknown.

    This is the field a reader would take as "this task's cost is known", and
    the driver settles the journal's ``cost_settled`` on the same test.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        receipt = stage.settle_into_a_receipt(
            ledger,
            task_id="t1",
            model_turns=(_turn("t1", model="a-model-nobody-priced"),),
        )
    finally:
        ledger.close()

    metrics = build_agentic_v2_metrics(
        {"success": True},
        standing=_standing("t1"),
        task_wall_time_ms=1.0,
        receipt=receipt,
    )

    assert receipt["status"] != STATUS_COMPLETE
    assert metrics["usage_complete"] is False


def test_a_task_that_called_nothing_is_unavailable_rather_than_free(tmp_path):
    """Silence is not a measured zero.

    ``receipt_for``'s ``when_empty`` offers three readings of an empty ledger
    and only one of them is true here. ``not_run`` would be false -- reaching
    this callback means the task ran. ``complete`` would state a real ``$0``
    for a task whose guest was up and whose host bill this process cannot read.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        receipt = stage.settle_into_a_receipt(
            ledger, task_id="t-silent", model_turns=()
        )
    finally:
        ledger.close()

    assert receipt["status"] == STATUS_UNAVAILABLE
    assert receipt["estimated_cost_usd"] is None
    assert receipt["model_calls"] == 0


def test_a_second_attempt_is_added_to_the_task_not_substituted_for_it(tmp_path):
    """A retried task's receipt covers what the whole task cost.

    The binding writes one attempt's turns. The receipt is built from every row
    standing against the task, which is why it has to come from the ledger
    rather than from what was just written -- a task retried once cost both
    attempts, and the driver asks for the receipt once.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        stage.settle_into_a_receipt(
            ledger, task_id="t1", model_turns=(_turn("t1", "call-1"),)
        )
        receipt = stage.settle_into_a_receipt(
            ledger, task_id="t1", model_turns=(_turn("t1", "call-2"),)
        )
    finally:
        ledger.close()

    assert receipt["model_calls"] == 2
    assert receipt["usage"]["input_tokens"] == 2322 * 2


def test_one_task_does_not_collect_another_task_s_calls(tmp_path):
    """The receipt is scoped to its task.

    Worth holding explicitly: the fix moved the amount from "what I just wrote"
    to "what the ledger holds", and the failure mode of that move is a receipt
    that quietly bills a task for the whole run.
    """
    ledger = stage.open_the_ledger(tmp_path, run_id="a-run")
    try:
        stage.settle_into_a_receipt(
            ledger, task_id="t1", model_turns=(_turn("t1"),)
        )
        second = stage.settle_into_a_receipt(
            ledger, task_id="t2", model_turns=(_turn("t2"),)
        )
    finally:
        ledger.close()

    assert second["model_calls"] == 1


# ── the free job now walks the paid path ────────────────────────────────────


def test_the_dry_run_settles_and_reports_a_fabricated_task():
    """The rehearsal the free job runs, against the real functions."""
    assert stage.the_paid_setup_a_dry_run_can_reach("advance_check_5") == []


def test_the_dry_run_would_have_caught_this_defect(monkeypatch):
    """The point of the rehearsal, stated as the defect it was built for.

    Put the old return value back -- the binding -- and the free job must fail.
    If this test can be made to pass with a broken paid path, the rehearsal is
    decoration and the next defect of this shape is paid for again.
    """
    ledger_holder = {}

    def hand_back_the_binding(ledger, *, task_id, model_turns):
        ledger_holder["seen"] = True
        return bind_run_to_ledger(
            ledger, task_id=task_id, model_turns=model_turns
        )

    monkeypatch.setattr(stage, "settle_into_a_receipt", hand_back_the_binding)
    broke = stage.the_paid_setup_a_dry_run_can_reach("advance_check_5")

    assert ledger_holder.get("seen") is True
    assert len(broke) == 1
    assert "report row" in broke[0]
    assert "not a receipt status" in broke[0]


def test_a_ledger_that_will_not_open_is_still_reported_first(monkeypatch):
    """The earlier defect's check is not lost to the newer one.

    Both live in the same helper now, and a failure to open must not be
    reported as a failure to build a row.
    """

    def refuse(*args, **kwargs):
        raise TypeError("missing 1 required keyword-only argument: 'run_id'")

    monkeypatch.setattr(stage, "open_the_ledger", refuse)
    broke = stage.the_paid_setup_a_dry_run_can_reach("advance_check_5")

    assert len(broke) == 1
    assert "cost ledger cannot be opened" in broke[0]


def test_the_paid_path_and_the_rehearsal_are_the_same_function():
    """Two call sites, one function -- the reason the rehearsal means anything.

    The same shape as ``open_the_ledger`` above it, and for the same reason:
    the first paid run was certified by a dry run that executed a different
    line.
    """
    assert STAGE_SOURCE.count("settle_into_a_receipt(") >= 3
    assert "return bind_run_to_ledger(" not in STAGE_SOURCE


def test_the_dry_run_says_it_reached_the_report_row():
    """What the sentence claims has to be what was executed.

    The sentence before this change named the ledger and stopped there, which
    was accurate then. It would now understate what the job checked, and an
    understated claim decays into an overstated one the next time the check
    grows.
    """
    claimed = STAGE_SOURCE.split("Every condition ")[1][:600]

    assert "receipt" in claimed
    assert "report " in claimed
    # And still says what it cannot reach, which is the larger half.
    assert "It cannot reach the model." in STAGE_SOURCE
