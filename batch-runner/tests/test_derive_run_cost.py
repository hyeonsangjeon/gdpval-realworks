"""`derive_run_cost` must produce a figure without producing a claim.

The tool exists because a Codex run's ledger prices every call and then throws
the number away: `settle` keeps a cost only when no reason is attached, and the
Codex path attaches `call_reachability_unknown` to every turn unconditionally.
Deriving the amount afterwards is legitimate — token billing is additive, so a
turn's total prices to one figure however many requests made it up.

What is not legitimate is letting that figure drift into the place where a
billed amount belongs, or letting a send nobody measured quietly count as free.
Both are single-line mistakes for whoever next touches this, and neither would
look wrong in a diff. So they are pinned here.

The ledgers below are built through `CostReceiptLedger` itself rather than by
hand-writing rows, so a schema change breaks these tests instead of silently
making them test a shape the runner no longer produces.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from core.cost_receipts import (
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
)
from derive_run_cost import (
    DerivationRefused,
    derive,
    uncalled_row,
    unledgered_row,
)

MODEL = "gpt-5.4"


def _usage(inp: int, cached: int, out: int) -> CallUsage:
    return CallUsage(
        input_tokens=inp, cached_input_tokens=cached, output_tokens=out,
        reasoning_tokens=0, audio_input_tokens=0, audio_output_tokens=0,
    )


def _ledger(tmp_path: Path, name: str = "led.sqlite3") -> CostReceiptLedger:
    return CostReceiptLedger(
        tmp_path / name, run_id="r", price_table=load_receipt_price_table()
    )


def _reserve(ledger: CostReceiptLedger, call_id: str, task: str) -> None:
    ledger.reserve(
        call_id=call_id, task_id=task, stage="generation", retry_kind="none",
        provider="azure", requested_model=MODEL, deployment=MODEL,
        api_version="v1", note="one Codex turn",
    )


@pytest.fixture()
def one_settled_one_open(tmp_path: Path) -> Path:
    """Two tasks: one fully measured, one with a send nobody measured."""
    ledger = _ledger(tmp_path)
    _reserve(ledger, "c1", "task-whole")
    ledger.settle("c1", usage=_usage(1_000_000, 0, 100_000), resolved_model=MODEL)
    _reserve(ledger, "c2", "task-floor")
    ledger.settle("c2", usage=_usage(1_000_000, 0, 0), resolved_model=MODEL)
    _reserve(ledger, "c3", "task-floor")  # left open on purpose
    return ledger.path


def test_the_amount_is_the_repositorys_own_arithmetic(one_settled_one_open):
    """$2.50/M in and $15.00/M out, applied by `price_call`, not by this test."""
    result = derive([one_settled_one_open])
    whole = result["per_task"]["task-whole"]
    # 1M input at $2.50 + 100k output at $15.00 = $2.50 + $1.50
    assert whole["derived_cost_usd_from_measured_tokens"] == pytest.approx(4.00)
    assert whole["derived_cost_basis"] == "all_calls_measured"
    assert result["derived_total_usd"] == pytest.approx(6.50)


def test_an_unmeasured_send_is_not_free(one_settled_one_open):
    """An open reservation means the request left and nobody counted it.

    Rolling it into the total as zero would read as "that attempt cost
    nothing", which is a stronger claim than the ledger is able to make.
    """
    result = derive([one_settled_one_open])
    floor = result["per_task"]["task-floor"]
    assert floor["derived_cost_basis"] == "floor_unmeasured_sends_excluded"
    assert floor["derived_cost_calls_unmeasured"] == 1
    assert floor["derived_cost_usd_from_measured_tokens"] == pytest.approx(2.50)
    assert result["derived_total_is_a_floor"] is True
    assert result["calls_unmeasured"] == 1


def test_a_task_with_nothing_measured_gets_no_figure(tmp_path):
    ledger = _ledger(tmp_path)
    _reserve(ledger, "c1", "task-dark")
    result = derive([ledger.path])
    dark = result["per_task"]["task-dark"]
    assert dark["derived_cost_basis"] == "no_measured_call"
    assert dark["derived_cost_usd_from_measured_tokens"] is None
    assert result["derived_total_usd"] == pytest.approx(0.0)


def test_a_task_never_called_is_a_true_zero():
    """The one case where zero is the honest answer, and it is named as such."""
    row = uncalled_row("method")
    assert row["derived_cost_basis"] == "no_call_made"
    assert row["derived_cost_usd_from_measured_tokens"] == 0.0
    assert row["derived_cost_calls_unmeasured"] == 0


def test_a_task_no_supplied_ledger_covers_is_not_a_zero_at_all():
    """The look-alike of the case above, and its opposite.

    A relay leg inherits its predecessor's finished tasks and starts an empty
    ledger, so those tasks reach this module looking exactly like tasks nobody
    ever called. They were called; the calls are in a ledger this caller was
    not given. The amount is therefore `None` — unknown — and never `0.0`,
    because the row above is the only row entitled to that number.

    The two are asserted against each other rather than separately: every
    other field is identical, and a one-line edit that made the amount `0.0`
    would leave a test checking only the basis string perfectly green.
    """
    unknown = unledgered_row("method")
    zero = uncalled_row("method")

    assert unknown["derived_cost_basis"] == "absent_from_supplied_ledgers"
    assert unknown["derived_cost_usd_from_measured_tokens"] is None
    assert unknown["derived_cost_is_provider_billed"] is False
    assert unknown["derived_cost_method"] == "method"

    assert unknown != zero
    differing = {k for k in unknown if unknown[k] != zero[k]}
    assert differing == {
        "derived_cost_basis",
        "derived_cost_usd_from_measured_tokens",
    }


def test_no_output_ever_carries_a_billed_cost_field(one_settled_one_open):
    """The derived figure must not be able to land in a billed column."""
    result = derive([one_settled_one_open])
    blob = json.dumps(result)
    assert "model_cost_usd" not in blob
    for row in result["per_task"].values():
        assert row["derived_cost_is_provider_billed"] is False
        assert "price_call" in row["derived_cost_method"]
    assert result["derived_total_is_provider_billed"] is False


def test_it_refuses_a_run_priced_against_a_table_it_never_saw(tmp_path):
    """Rates the run did not see would produce a figure for a different run."""
    ledger = _ledger(tmp_path)
    _reserve(ledger, "c1", "t")
    ledger.settle("c1", usage=_usage(10, 0, 10), resolved_model=MODEL)
    del ledger

    conn = sqlite3.connect(tmp_path / "led.sqlite3")
    conn.execute("update cost_calls set price_table_sha256 = 'deadbeef'")
    conn.commit()
    conn.close()

    with pytest.raises(DerivationRefused, match="never saw|recorded price table"):
        derive([tmp_path / "led.sqlite3"])


def test_it_refuses_to_pool_legs_priced_differently(tmp_path):
    """A relayed run leaves one ledger per leg; mixing rate sets is not a sum."""
    for name, sha in (("a.sqlite3", "aaa"), ("b.sqlite3", "bbb")):
        ledger = _ledger(tmp_path, name)
        _reserve(ledger, "c1", "t")
        ledger.settle("c1", usage=_usage(10, 0, 10), resolved_model=MODEL)
        del ledger
        conn = sqlite3.connect(tmp_path / name)
        conn.execute("update cost_calls set price_table_sha256 = ?", (sha,))
        conn.commit()
        conn.close()

    with pytest.raises(DerivationRefused, match="different price tables"):
        derive([tmp_path / "a.sqlite3", tmp_path / "b.sqlite3"])


def test_it_pools_the_legs_of_one_relayed_run(tmp_path):
    """A task's calls can straddle a handover, so per-task totals must join."""
    for name, call in (("a.sqlite3", "c1"), ("b.sqlite3", "c2")):
        ledger = _ledger(tmp_path, name)
        _reserve(ledger, call, "same-task")
        ledger.settle(call, usage=_usage(1_000_000, 0, 0), resolved_model=MODEL)
        del ledger

    result = derive([tmp_path / "a.sqlite3", tmp_path / "b.sqlite3"])
    assert result["tasks_with_a_call"] == 1
    joined = result["per_task"]["same-task"]
    assert joined["derived_cost_calls_measured"] == 2
    assert joined["derived_cost_usd_from_measured_tokens"] == pytest.approx(5.00)
    assert joined["derived_cost_basis"] == "all_calls_measured"


def test_the_ledger_is_not_written_to(one_settled_one_open):
    before = one_settled_one_open.read_bytes()
    derive([one_settled_one_open])
    assert one_settled_one_open.read_bytes() == before


def test_a_missing_ledger_is_refused_not_counted_as_empty(tmp_path):
    """An unreadable input must not price out as a run that cost nothing."""
    with pytest.raises(DerivationRefused, match="no ledger at"):
        derive([tmp_path / "absent.sqlite3"])
