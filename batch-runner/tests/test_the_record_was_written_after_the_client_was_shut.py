"""The run record was written after the client it describes had been shut.

`main` closes the Azure client in a ``finally``, and then builds the run record
below it. One field of that record was ``managed.runtime_fingerprint`` -- a
property that calls ``_require_open()`` first and raises on a closed client::

    RuntimeError: managed Azure AI client is closed

So a paid run that got all the way through its cohort would die while writing
the record of it, and `run_record.json` would not be written at all.

How bad that is, stated exactly rather than dramatically. Three things are
written during the run and survive: the journal, the collected deliverables and
the cost ledger. So the outcome of every task, its files and their digests, and
what each call is known to have cost are all still there, and the binding and
the approved amounts are deterministic and can be worked out again. What exists
nowhere else is what the record alone holds: `reference_files` -- which files
each task was actually handed, per attempt, which the record's own comment says
a result is read against -- and `conversations`, the per-task budget and turn
state. Those two are gone, and the assembled account has to be rebuilt by hand
from three files for a run that had already succeeded.

Nothing had ever executed the line. A rehearsal substitutes a disclaimer for it,
the dry run returns several hundred lines earlier, and the two paid runs so far
died before their tasks were done -- one on a constructor keyword, one on a
receipt shape. The first run this would have hit is the first run that
*finishes*, which is the most expensive moment available to fail at: the whole
cohort paid for and no record of it.

The fix reads the fingerprint while the client is open, immediately after the
route it describes has been checked. It is fixed when the lease is built and
cannot change during the run, so early and late are the same value -- the
difference is only that one of them is readable.

Nothing here opens a client, reaches Azure or spends anything.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.llm_client import ManagedAzureAIClient  # noqa: E402

RUNNER_PATH = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"
STAGE_SOURCE = RUNNER_PATH.read_text()


def _load_runner():
    """Import the script by path; it is not in a package.

    Registered in ``sys.modules`` before execution for the same reason the
    sibling stage test gives: a dataclass field's type is resolved by looking
    the defining module up there.
    """
    spec = importlib.util.spec_from_file_location("run_agentic_v2_stage", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()


class _Lease:
    """Enough of a lease to build the real adapter around."""

    runtime_fingerprint = "route:whatever-the-lease-was-built-with"
    client = object()

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


# ── the property, against the real class ────────────────────────────────────


def test_the_fingerprint_is_readable_while_the_client_is_open():
    managed = ManagedAzureAIClient(_Lease())

    assert managed.runtime_fingerprint == "route:whatever-the-lease-was-built-with"

    managed.close()


def test_the_fingerprint_raises_once_the_client_is_closed():
    """The whole defect in three lines, against the real adapter.

    Not a double: a stand-in with a forgiving property is exactly how this
    passed review. The refusal is deliberate and correct -- a closed client
    should not answer questions about itself -- so the fix belongs at the call
    site, not here.
    """
    managed = ManagedAzureAIClient(_Lease())
    managed.close()

    with pytest.raises(RuntimeError) as refused:
        managed.runtime_fingerprint

    assert "closed" in str(refused.value)


def test_closing_twice_does_not_reopen_anything():
    """`close` is idempotent, so nothing recovers by calling it again.

    Worth pinning: "just close it later" and "close it twice" are both natural
    guesses at a fix, and neither makes the property readable again.
    """
    lease = _Lease()
    managed = ManagedAzureAIClient(lease)
    managed.close()
    managed.close()

    assert lease.closed is True
    with pytest.raises(RuntimeError):
        managed.runtime_fingerprint


# ── the call site, which is where the fix is ────────────────────────────────


def test_the_fingerprint_is_read_before_the_client_is_closed():
    """Order is the invariant, so order is what is asserted.

    There is no cheap runtime test for this: reaching the record means an Azure
    identity, a bound cohort and a finished run. The order of two lines in one
    function is checkable for nothing, and it is the whole defect.
    """
    read = "route_fingerprint = managed.runtime_fingerprint"
    assert read in STAGE_SOURCE, "the fingerprint is not captured anywhere"

    assert STAGE_SOURCE.index(read) < STAGE_SOURCE.index("managed.close()")


def test_the_record_does_not_reach_for_the_client():
    """Everything after the record starts being built must be already-read data.

    The record is assembled after the ``finally``, so any attribute read on the
    client from there is the same defect under another name.
    """
    after_the_run = STAGE_SOURCE[STAGE_SOURCE.index("\n    record = {") :]

    assert "managed." not in after_the_run


def test_the_record_still_carries_the_fingerprint():
    """Not reading it is not the fix; reading it earlier is.

    A field quietly dropped to ``None`` would make the record claim the route
    was unknown for a run that checked it.
    """
    after_the_run = STAGE_SOURCE[STAGE_SOURCE.index("\n    record = {") :]

    assert '"route_fingerprint": (' in after_the_run
    assert "else route_fingerprint" in after_the_run


def test_a_rehearsal_still_refuses_to_name_a_route():
    """The rehearsal branch is untouched and must stay that way.

    A rehearsal asks nothing, so it has no route to fingerprint, and the record
    it writes says so rather than carrying a plausible-looking string.
    """
    after_the_run = STAGE_SOURCE[STAGE_SOURCE.index("\n    record = {") :]

    assert "rehearsal_is_not_a_run()" in after_the_run


# ── the ledger the same block leaves open ───────────────────────────────────


def test_the_ledger_is_closed_where_the_client_is():
    """Found looking for siblings of the defect above, in the same `finally`.

    The ledger is sqlite in WAL mode, so committed rows sit in a `-wal` sidecar
    until something checkpoints them, and closing the connection is what does
    it. A process that exits normally checkpoints anyway; a shard killed by its
    own `timeout-minutes` does not.

    Not data loss today -- the artifact upload takes the whole directory, so
    the sidecar goes with it -- and stated that way in the comment rather than
    dressed up. It is fixed because the rehearsal that certifies this path has
    always closed its ledger and this path did not, which is the asymmetry the
    rehearsal exists to prevent.
    """
    closing = STAGE_SOURCE[STAGE_SOURCE.index("\n    finally:") :]
    closing = closing[: closing.index("\n    record = {")]

    assert "managed.close()" in closing
    assert "ledger.close()" in closing


def test_the_ledger_exists_before_the_try_that_closes_it():
    """Otherwise the `finally` raises `NameError` on every refused run.

    The ledger is opened inside the `try` and only on the paid branch, so a run
    refused before that line reaches the `finally` with the name unbound.

    Scoped to `main`, because the dry-run rehearsal above it opens a ledger of
    its own and an unscoped search finds that one first.
    """
    body = STAGE_SOURCE[STAGE_SOURCE.index("\ndef main()") :]

    assert "\n    ledger = None\n" in body
    assert body.index("\n    ledger = None\n") < body.index("ledger = open_the_ledger")


# ── the price list, which the paid path reads and the free job now does ─────


def test_the_free_job_reads_the_price_list_the_paid_run_will():
    """Runs for real here, because unlike the route it needs no identity.

    A price list that has stopped parsing is worth finding before a deployment
    is leased rather than after.
    """
    assert runner.the_paid_setup_a_dry_run_can_reach("advance_check_5") == []


def test_a_price_list_that_will_not_load_is_reported_and_not_raised(monkeypatch):
    """The dry run returns problems; it does not crash on them."""

    def refuse(*_args, **_kwargs):
        raise ValueError("the price list is not yaml any more")

    monkeypatch.setattr(runner, "load_price_table", refuse)
    problems = runner.the_paid_setup_a_dry_run_can_reach("advance_check_5")

    assert len(problems) == 1
    assert "price list" in problems[0]


def test_the_missing_price_for_this_model_is_not_what_that_check_fails_on():
    """The pinned model is priced, and the free job now proves it end to end.

    This is the correction to a belief that had been carried for two days: the
    null amounts seen from the ledger were read as "`gpt-5.4` is absent from the
    price table". It is not absent. ``azure:gpt-5.4`` is in the committed list
    at $2.50 and $15.00 per million, sourced from the Azure retail price API and
    last reviewed 2026-08-29. The nulls came from the ledger being opened with
    no price table at all, which made every call in every paid run settle
    `price_missing` regardless of what the file said.
    """
    from core.cost_receipts import load_receipt_price_table

    pinned = str(
        (runner.load_stage_one_plan(runner.STAGE_ONE_PLAN_PATH).get("model") or {}).get(
            "resolved_model"
        )
        or ""
    )

    assert pinned, "the plan pins no model name"
    assert load_receipt_price_table().lookup("azure", pinned) is not None


def test_the_ledger_is_opened_with_the_price_list():
    """A ledger without one prices nothing, and says so on every receipt.

    Checked on the object rather than in the source, because the argument being
    present is not the claim -- the claim is that the ledger this function
    returns can price a call.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        ledger = runner.open_the_ledger(Path(scratch), run_id="a-test")
        try:
            assert ledger.price_table is not None
        finally:
            ledger.close()


def test_a_priced_call_settles_complete_with_an_amount():
    """The whole point of the price list, asserted as money.

    Run against the real ledger and the real committed prices, on a fabricated
    turn. 1,000,000 input and 1,000,000 output tokens against $2.50 and $15.00
    per million is $17.50, so the arithmetic is checkable by eye and a silently
    swapped rate would not survive it.
    """
    import tempfile

    from core.agentic_v2_cost_binding import ModelTurn
    from core.cost_receipts import CallUsage

    pinned = str(
        (runner.load_stage_one_plan(runner.STAGE_ONE_PLAN_PATH).get("model") or {}).get(
            "resolved_model"
        )
        or ""
    )

    with tempfile.TemporaryDirectory() as scratch:
        ledger = runner.open_the_ledger(Path(scratch), run_id="a-test")
        try:
            receipt = runner.settle_into_a_receipt(
                ledger,
                task_id="a-task",
                model_turns=(
                    ModelTurn(
                        call_id="a-test:a-task:1:call-1",
                        usage=CallUsage(input_tokens=1_000_000, output_tokens=1_000_000),
                        provider="azure",
                        requested_model=pinned,
                        deployment="a-deployment",
                        resolved_model=pinned,
                    ),
                ),
            )
        finally:
            ledger.close()

    assert receipt["status"] == "complete"
    assert receipt["missing_reasons"] == []
    assert receipt["estimated_cost_usd"] == pytest.approx(17.50)
    assert receipt["price_table_sha256"] is not None


def test_a_call_the_price_list_does_not_cover_is_still_partial_and_null():
    """The fix does not invent an amount for a model nobody priced.

    An unknown name settles `price_missing`, the receipt reads `partial`, and
    `estimated_cost_usd` stays null. That was the right behaviour before this
    change and it has to survive it -- otherwise the fix would have replaced
    one wrong number with another.
    """
    import tempfile

    from core.agentic_v2_cost_binding import ModelTurn
    from core.cost_receipts import CallUsage

    with tempfile.TemporaryDirectory() as scratch:
        ledger = runner.open_the_ledger(Path(scratch), run_id="a-test")
        try:
            receipt = runner.settle_into_a_receipt(
                ledger,
                task_id="a-task",
                model_turns=(
                    ModelTurn(
                        call_id="a-test:a-task:1:call-1",
                        usage=CallUsage(input_tokens=100, output_tokens=10),
                        provider="azure",
                        requested_model="a-model-nobody-priced",
                        deployment="a-deployment",
                        resolved_model="a-model-nobody-priced",
                    ),
                ),
            )
        finally:
            ledger.close()

    assert receipt["status"] == "partial"
    assert "price_missing" in receipt["missing_reasons"]
    assert receipt["estimated_cost_usd"] is None


def test_the_dry_run_would_have_caught_the_unpriced_ledger():
    """The free job fails when the ledger is opened without a price list.

    Proved by opening one that way, which is what the code did until this
    change. Without this the fix is a line nobody would notice going back.
    """
    import tempfile

    from core.cost_receipts import CostReceiptLedger

    def unpriced(into, *, run_id):
        return CostReceiptLedger(str(Path(into) / "cost_receipts.sqlite3"),
                                 run_id=run_id)

    with tempfile.TemporaryDirectory():
        original = runner.open_the_ledger
        runner.open_the_ledger = unpriced
        try:
            problems = runner.the_paid_setup_a_dry_run_can_reach("advance_check_5")
        finally:
            runner.open_the_ledger = original

    assert len(problems) == 1
    assert "unpriced" in problems[0]
    assert "price list" in problems[0]
