"""A cost-ledger check that only passes is not a check.

``scripts/verify_cost_ledger.py`` returned a clean verdict on the one real
receipt this repository has published. That is necessary and nowhere near
sufficient: a function that returns "pass" unconditionally would have done the
same. These tests take a receipt that reconciles, break it one way at a time,
and require the matching check to notice.

Each test names the billing mistake it simulates, because that -- not the
function name -- is what the check is for. The last two are the ones that
matter most: a run whose model has no published price must still pass, and a
run whose usage went missing must fail, even though both surface in the
receipt as the same word.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts.verify_cost_ledger import verify  # noqa: E402

RUN_ID = "exp_smoke|cfg0123456789abcd|" + "a" * 64
PRICE_TABLE = "b" * 64
TASK = "83d10b06-26d1-4636-a32c-23f92c57f30b"


def _call(
    call_id: str,
    *,
    stage: str = "grading",
    cost: str | None = "0.010000",
    tokens: tuple[int, int, int, int] = (1000, 500, 100, 50),
    state: str = "settled",
    retry_kind: str = "none",
    missing_reasons: list[str] | None = None,
    resolved_model: str | None = "gpt-5.4",
    task_id: str = TASK,
    extra: dict | None = None,
) -> dict:
    row = {
        "record_type": "call",
        "call_id": call_id,
        "run_id": RUN_ID,
        "task_id": task_id,
        "stage": stage,
        "retry_kind": retry_kind,
        "provider": "azure",
        "deployment": None,
        "requested_model": "gpt-5.4",
        "resolved_model": resolved_model,
        "api_version": None,
        "state": state,
        "input_tokens": tokens[0],
        "cached_input_tokens": tokens[1],
        "output_tokens": tokens[2],
        "reasoning_tokens": tokens[3],
        "model_cost_usd": cost,
        "missing_reasons": missing_reasons or [],
        "price_table_sha256": PRICE_TABLE if cost is not None else None,
        "request_sha256": None,
        "note": None,
    }
    if extra:
        row.update(extra)
    return row


#: The token kinds ``cost-receipt-v1``'s usage block is closed over. Spelled
#: out rather than imported from the verifier: a test that reads the list off
#: the thing it is checking would keep passing if the list itself went wrong.
USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "audio_input_tokens",
    "audio_output_tokens",
)


def _sum_usage(rows: list[dict]) -> dict[str, int | None]:
    """Sum the way the real builder sums: a kind nobody stated stays ``None``.

    Reimplemented here rather than called out of ``core`` so that the two
    agreeing is evidence rather than a tautology. The distinction it keeps is
    the one the whole repair rests on -- "nobody measured this" and "measured,
    and it was none" must not arrive at the verifier as the same integer.
    """
    totals: dict[str, int | None] = {key: None for key in USAGE_KEYS}
    for row in rows:
        for key in USAGE_KEYS:
            value = row.get(key)
            if value is None:
                continue
            totals[key] = (totals[key] or 0) + int(value)
    return totals


def _receipt_from(calls: list[dict]) -> dict:
    """Build the receipt those calls actually justify."""
    settled = [row for row in calls if row["state"] == "settled"]
    total = sum((Decimal(row["model_cost_usd"] or 0) for row in settled), Decimal(0))
    usage = _sum_usage(settled)
    components = {}
    for row in settled:
        key = (row["stage"], row["retry_kind"], row["provider"], row["deployment"],
               row["requested_model"], row["resolved_model"], row["api_version"])
        components.setdefault(key, []).append(row)

    unpriced = [row for row in settled if row["model_cost_usd"] is None]
    status = "partial" if unpriced else "complete"
    return {
        "schema_version": "cost-receipt-v1",
        "status": status,
        "currency": "USD",
        "estimated_cost_usd": None if unpriced else float(total),
        "known_cost_usd": float(total),
        "model_cost_usd": float(total),
        "runtime_cost_usd": 0.0,
        "model_calls": len(settled),
        "usage": usage,
        "components": [
            {
                "name": key[0],
                "stage": key[0],
                "retry_kind": key[1],
                "provider": key[2],
                "deployment": key[3],
                "requested_model": key[4],
                "resolved_model": key[5],
                "api_version": key[6],
                "status": "complete",
                "model_calls": len(rows),
                "known_cost_usd": float(
                    sum((Decimal(r["model_cost_usd"] or 0) for r in rows), Decimal(0))
                ),
                "usage": _sum_usage(rows),
                "missing_reasons": [],
            }
            for key, rows in components.items()
        ],
        "price_table_sha256": PRICE_TABLE,
        "missing_reasons": [],
    }


def _write(tmp_path: Path, calls: list[dict], receipt: dict | None = None,
           results: list[dict] | None = None) -> Path:
    """Lay a grade file and its ledger out the way a real run publishes them."""
    ledger_name = "run__src_aaaaaaaaaaaaaaaa__v2.2.cost_ledger.jsonl"
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in calls
    )
    (tmp_path / ledger_name).write_text(payload, encoding="utf-8")

    grade = {
        "schema_version": "1.4",
        "run_status": "diagnostic",
        "graded_at": "2026-09-07T00:00:00Z",
        "grader_source_hash": "a" * 64,
        "cost_ledger": {
            "path": ledger_name,
            "sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        },
        "results": results if results is not None else [{"task_id": TASK, "status": "ok"}],
        "summary": {"task_count": 1,
                    "grading_cost": receipt if receipt is not None else _receipt_from(calls)},
    }
    grade_path = tmp_path / "run__src_aaaaaaaaaaaaaaaa__v2.2.json"
    grade_path.write_text(json.dumps(grade, indent=2), encoding="utf-8")
    return grade_path


def _verdict(grade_path: Path) -> dict[str, bool]:
    findings, _ = verify(grade_path)
    return {finding.check: finding.ok for finding in findings}


def _good_calls() -> list[dict]:
    return [
        _call("c1"),
        _call("c2"),
        _call("c3", stage="perception", cost="0.005000", tokens=(200, 0, 40, 10)),
    ]


def test_a_receipt_that_adds_up_passes_every_check(tmp_path):
    verdict = _verdict(_write(tmp_path, _good_calls()))
    assert all(verdict.values()), f"clean fixture should pass: {verdict}"


def test_a_ledger_edited_after_publication_is_caught(tmp_path):
    """Someone changes a dollar figure in the ledger after the grade shipped."""
    grade_path = _write(tmp_path, _good_calls())
    ledger = next(tmp_path.glob("*.cost_ledger.jsonl"))
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("0.010000", "0.001000"),
                      encoding="utf-8")
    assert _verdict(grade_path)["sidecar"] is False


def test_a_missing_ledger_is_not_treated_as_a_zero_bill(tmp_path):
    grade_path = _write(tmp_path, _good_calls())
    next(tmp_path.glob("*.cost_ledger.jsonl")).unlink()
    findings, _ = verify(grade_path)
    assert findings[0].ok is False
    assert len(findings) == 1, "no reconciliation may be claimed without a ledger"


def test_the_same_call_billed_twice_is_caught(tmp_path):
    calls = _good_calls()
    duplicate = deepcopy(calls[0])
    calls.append(duplicate)
    receipt = _receipt_from(calls[:3])  # receipt built before the duplicate landed
    assert _verdict(_write(tmp_path, calls, receipt))["no_double_billing"] is False


def test_a_retry_is_counted_rather_than_folded_away(tmp_path):
    """A retried call was billed twice by the provider, so it counts twice."""
    calls = _good_calls() + [_call("c4", retry_kind="transport")]
    verdict = _verdict(_write(tmp_path, calls))
    assert all(verdict.values())
    findings, _ = verify(_write(tmp_path, calls))
    retry_finding = next(f for f in findings if f.check == "no_double_billing")
    assert retry_finding.data["retries_by_kind"] == {"transport": 1}


def test_a_call_that_never_came_back_is_surfaced(tmp_path):
    """Reserved-but-unsettled: sent, possibly billed, never recorded."""
    calls = _good_calls() + [
        _call("c9", state="reserved", cost=None, tokens=(0, 0, 0, 0), resolved_model=None)
    ]
    receipt = _receipt_from(calls)
    assert _verdict(_write(tmp_path, calls, receipt))["all_calls_settled"] is False


def test_tokens_that_do_not_add_up_are_caught(tmp_path):
    calls = _good_calls()
    receipt = _receipt_from(calls)
    receipt["usage"]["input_tokens"] += 5000
    assert _verdict(_write(tmp_path, calls, receipt))["usage_reconciles"] is False


def test_a_total_that_does_not_match_the_calls_is_caught(tmp_path):
    calls = _good_calls()
    receipt = _receipt_from(calls)
    receipt["model_cost_usd"] = 99.0
    receipt["known_cost_usd"] = 99.0
    receipt["estimated_cost_usd"] = 99.0
    assert _verdict(_write(tmp_path, calls, receipt))["cost_reconciles"] is False


def test_a_partial_receipt_may_not_state_a_total(tmp_path):
    calls = _good_calls()
    receipt = _receipt_from(calls)
    receipt["status"] = "partial"
    assert _verdict(_write(tmp_path, calls, receipt))["cost_reconciles"] is False


def test_calls_absent_from_every_line_of_the_bill_are_caught(tmp_path):
    calls = _good_calls()
    receipt = _receipt_from(calls)
    receipt["components"] = [c for c in receipt["components"] if c["stage"] != "perception"]
    assert _verdict(_write(tmp_path, calls, receipt))["components_reconcile"] is False


def test_two_rate_tables_in_one_run_are_caught(tmp_path):
    calls = _good_calls()
    calls[1]["price_table_sha256"] = "c" * 64
    assert _verdict(_write(tmp_path, calls))["price_table"] is False


def test_a_task_graded_for_free_is_caught(tmp_path):
    """A graded task with no call behind it did not cost nothing."""
    calls = _good_calls()
    results = [{"task_id": TASK, "status": "ok"},
               {"task_id": "ffffffff-0000-0000-0000-000000000000", "status": "ok"}]
    assert _verdict(_write(tmp_path, calls, results=results))["task_coverage"] is False


def test_a_failed_task_is_billed_and_reported_not_written_off(tmp_path):
    calls = _good_calls() + [_call("c5", task_id="dead-task", cost="0.020000")]
    results = [{"task_id": TASK, "status": "ok"},
               {"task_id": "dead-task", "status": "error", "error": "judge timeout"}]
    findings, _ = verify(_write(tmp_path, calls, results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is True
    assert coverage.data["failed_task_cost_usd"] == {"dead-task": "0.020000"}


# Being in the payload is not the same as having been graded. A task can stop
# before the first judge call -- no file to grade, or no way to choose among the
# files -- and then zero calls really did cost zero. The payload says so three
# times over: two call counters, a per-task receipt, and the rows it left in the
# ledger. These pin that the check reconciles those three rather than assuming
# any task named in the payload must have a bill. A task that says nothing at
# all is still covered by the old rule, which
# `test_a_task_graded_for_free_is_caught` above holds in place.


def _task_row(
    task_id: str,
    *,
    judge: int,
    perception: int = 0,
    model_calls: int | None = None,
    cost: float = 0.0,
    error: str | None = None,
) -> dict:
    """A task row shaped the way ``step8_grade.py`` writes one."""
    return {
        "task_id": task_id,
        "error": error,
        "judge_call_count": judge,
        "perception_call_count": perception,
        "render_call_count": 0,
        "grading_cost": {
            "schema_version": "cost-receipt-v1",
            "status": "complete",
            "currency": "USD",
            "estimated_cost_usd": cost,
            "known_cost_usd": cost,
            "model_calls": judge + perception if model_calls is None else model_calls,
            "usage": {},
            "components": [],
            "missing_reasons": [],
        },
    }


def _graded_task() -> dict:
    """The one task `_good_calls` bills: two grading calls and one perception."""
    return _task_row(TASK, judge=2, perception=1, cost=0.025)


def test_a_task_that_never_reached_the_judge_is_not_a_free_grade(tmp_path):
    """exp035 published 78 of these across nine shards. The model produced no
    file, or the selector refused to choose among the files it did produce, so
    grading stopped before the first judge call. Reading that as "graded for
    free" fails a run for being accurate about work it did not do."""
    results = [_graded_task(), _task_row("never-graded", judge=0, error="no_deliverables")]
    findings, _ = verify(_write(tmp_path, _good_calls(), results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is True
    assert coverage.data["tasks_never_graded"] == ["never-graded"]


def test_a_task_claiming_calls_it_cannot_show_is_still_caught(tmp_path):
    """The defect this check was written for, unchanged: the task says it was
    graded and no line of the bill agrees."""
    results = [_graded_task(), _task_row("billed-nowhere", judge=5, cost=0.05)]
    findings, _ = verify(_write(tmp_path, _good_calls(), results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is False
    assert "billed-nowhere" in str(coverage.data)


def test_calls_hidden_behind_a_zero_count_are_caught(tmp_path):
    """Why this is a reconciliation and not a skip. A task that declares
    nothing while the ledger holds its calls is consumption the receipt's
    per-task split disowns -- and it is exactly what a rule that simply ignored
    zero-call tasks would wave through."""
    calls = _good_calls() + [_call("c9", task_id="quiet-task", cost="0.030000")]
    results = [_graded_task(), _task_row("quiet-task", judge=0)]
    findings, _ = verify(_write(tmp_path, calls, results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is False
    assert "quiet-task" in str(coverage.data)


def test_a_task_that_undercounts_its_calls_is_caught(tmp_path):
    """Partial under-declaration, which the old rule could not see at all: one
    row in the ledger is enough for it, however many the task claims."""
    calls = _good_calls() + [
        _call("cA1", task_id="short-count", cost="0.030000"),
        _call("cA2", task_id="short-count", cost="0.030000"),
    ]
    results = [_graded_task(), _task_row("short-count", judge=1, cost=0.03)]
    findings, _ = verify(_write(tmp_path, calls, results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is False
    assert "short-count" in str(coverage.data)


def test_a_task_with_no_calls_and_a_bill_is_caught(tmp_path):
    """Zero calls and a dollar figure are not both true. This is the shape a
    real never-graded task must not be allowed to hide in."""
    results = [_graded_task(), _task_row("free-lunch", judge=0, cost=12.50)]
    findings, _ = verify(_write(tmp_path, _good_calls(), results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is False
    assert "free-lunch" in str(coverage.data)


def test_a_task_whose_two_self_declarations_disagree_is_caught(tmp_path):
    """The counters and the per-task receipt restate the same number. When
    they stop agreeing, the payload contradicts itself and neither figure can
    be quoted."""
    results = [_graded_task(), _task_row("two-stories", judge=0, model_calls=4)]
    findings, _ = verify(_write(tmp_path, _good_calls(), results=results))
    coverage = next(f for f in findings if f.check == "task_coverage")
    assert coverage.ok is False
    assert "two-stories" in str(coverage.data)


# The two that carry the whole point of the distinction.

def test_an_unpriced_model_is_honest_and_still_passes(tmp_path):
    """gpt-5.6-sol has no published rate. The call is fully recorded; the
    dollar figure is unknown rather than zero. That is not a defect."""
    calls = _good_calls() + [
        _call("c6", cost=None, resolved_model="gpt-5.6-sol",
              missing_reasons=["price_missing_for_model"])
    ]
    findings, _ = verify(_write(tmp_path, calls))
    partial = next(f for f in findings if f.check == "partial_cause")
    assert partial.ok is True
    assert partial.data["unpriced_models"] == ["gpt-5.6-sol"]
    assert partial.data["unpriced_calls"] == 1


def test_usage_that_went_missing_fails_even_though_it_looks_the_same(tmp_path):
    """Same word in the receipt -- 'partial' -- opposite meaning. A call with
    no price, no reason and no tokens is consumption the pipeline lost."""
    calls = _good_calls() + [_call("c7", cost=None, tokens=(0, 0, 0, 0))]
    findings, _ = verify(_write(tmp_path, calls))
    partial = next(f for f in findings if f.check == "partial_cause")
    assert partial.ok is False
    assert "usage was lost" in partial.detail


def test_a_complete_claim_over_an_unpriced_call_is_caught(tmp_path):
    calls = _good_calls() + [
        _call("c8", cost=None, resolved_model="gpt-5.6-sol",
              missing_reasons=["price_missing_for_model"])
    ]
    receipt = _receipt_from(calls)
    receipt["status"] = "complete"
    receipt["estimated_cost_usd"] = receipt["known_cost_usd"]
    assert _verdict(_write(tmp_path, calls, receipt))["partial_cause"] is False


# 오디오 — 영수증이 담게 된 뒤. 통과하는 경우 하나에 무효화 시도 여섯.

def test_audio_tokens_now_reconcile_like_every_other_kind(tmp_path):
    """``cost-receipt-v1`` closes usage over six kinds, audio among them.

    A run that used audio has a usage block that states it, so the ledger and
    the receipt simply agree and nothing is reported. This is the case the
    repair was for; the two after it are why widening the block did not make
    the checks weaker.
    """
    calls = _good_calls() + [
        _call("cA", stage="perception",
              extra={"audio_input_tokens": 4200, "audio_output_tokens": 0})
    ]
    verdict = _verdict(_write(tmp_path, calls))
    assert all(verdict.values()), verdict


def test_a_receipt_that_omits_the_audio_it_consumed_is_caught(tmp_path):
    """The planted omission: audio metered, receipt silent.

    This is the shape of every receipt published before the fields existed.
    It must fail, and it must fail while naming the measured number -- the
    point of the finding is the ledger's count, not that a key is missing.
    """
    calls = _good_calls() + [
        _call("cA", stage="perception",
              extra={"audio_input_tokens": 4200, "audio_output_tokens": 0})
    ]
    receipt = _receipt_from(calls)
    for key in ("audio_input_tokens", "audio_output_tokens"):
        receipt["usage"].pop(key)
        for component in receipt["components"]:
            component["usage"].pop(key)

    findings, _ = verify(_write(tmp_path, calls, receipt))
    verdict = {f.check: f.ok for f in findings}
    assert verdict["usage_reconciles"] is False
    assert verdict["components_reconcile"] is False

    reconciles = next(f for f in findings if f.check == "usage_reconciles")
    assert reconciles.data["audio_input_tokens"] == {"receipt": None, "ledger": 4200}
    assert reconciles.data["audio_output_tokens"] == {"receipt": None, "ledger": 0}


def test_a_receipt_claiming_zero_audio_over_a_run_that_used_it_is_caught(tmp_path):
    """The false zero: the failure a widened schema could have introduced.

    Declaring the fields makes it possible to write ``0`` into them. A zero
    that no call supports is worse than the old silence, because it reads as a
    measurement. The verifier compares against the ledger, so it fails.
    """
    calls = _good_calls() + [
        _call("cA", stage="perception",
              extra={"audio_input_tokens": 4200, "audio_output_tokens": 0})
    ]
    receipt = _receipt_from(calls)
    receipt["usage"]["audio_input_tokens"] = 0
    for component in receipt["components"]:
        if component["stage"] == "perception":
            component["usage"]["audio_input_tokens"] = 0

    verdict = _verdict(_write(tmp_path, calls, receipt))
    assert verdict["usage_reconciles"] is False
    assert verdict["components_reconcile"] is False


def test_a_receipt_predating_the_audio_fields_still_passes_on_a_text_run(tmp_path):
    """Old readers and old records survive. The change is additive.

    Every receipt published before this contract grew omits the two audio keys
    entirely. Over a ledger that never metered audio there is nothing to
    disagree with, and failing those records would condemn evidence that was
    honest under the contract it was written for.
    """
    calls = _good_calls()
    receipt = _receipt_from(calls)
    for key in ("audio_input_tokens", "audio_output_tokens"):
        receipt["usage"].pop(key)
        for component in receipt["components"]:
            component["usage"].pop(key)

    verdict = _verdict(_write(tmp_path, calls, receipt))
    assert all(verdict.values()), verdict


def test_a_zero_call_receipt_may_still_say_zero_rather_than_nothing(tmp_path):
    """The other legacy shape: literal zeros against a ledger with no rows.

    ``empty_usage`` seeds the four long-standing kinds at zero, so a receipt
    covering no calls states zero for them. A ledger with no rows measured
    nothing at all. Those two descriptions of the same emptiness agree, and a
    stricter rule would fail every such receipt already published.

    ``identity`` is excluded rather than asserted: a ledger with no rows names
    no run, which is a real thing to say about an empty ledger and has nothing
    to do with tokens. Excluding it here keeps this test about the one
    distinction it exists for.
    """
    receipt = _receipt_from([])
    receipt["usage"] = {key: 0 for key in USAGE_KEYS}

    verdict = _verdict(_write(tmp_path, [], receipt, results=[]))
    verdict.pop("identity")
    assert all(verdict.values()), verdict


def test_a_token_kind_the_receipt_still_cannot_express_is_reported(tmp_path):
    """The check that caught audio did not retire with it.

    ``usage_containment`` reads the kinds off the ledger rows rather than a
    list kept in the verifier, so the next thing metered is caught on the run
    it appears instead of the release someone remembers to widen a constant.
    ``cache_write_input_tokens`` is a real example: the Codex adapter meters it
    and neither ``CallUsage`` nor the price table has a place for it.
    """
    calls = _good_calls() + [
        _call("cA", extra={"cache_write_input_tokens": 777})
    ]
    findings, _ = verify(_write(tmp_path, calls))
    containment = next(f for f in findings if f.check == "usage_containment")
    assert containment.ok is False
    assert containment.data["totals"]["cache_write_input_tokens"] == 777
    assert containment.data["unexpressible_keys"] == ["cache_write_input_tokens"]


def test_a_negative_token_count_in_the_ledger_is_refused_not_summed(tmp_path):
    """Corrupt evidence stops the sum instead of being coerced past.

    A negative count is not a measurement. Reading it as zero, or adding it,
    would publish a number no provider reported; the check says the ledger
    cannot be summed and names the call.
    """
    calls = _good_calls() + [
        _call("cA", stage="perception", extra={"audio_input_tokens": -5})
    ]
    findings, _ = verify(_write(tmp_path, calls))
    reconciles = next(f for f in findings if f.check == "usage_reconciles")
    assert reconciles.ok is False
    assert "cA" in reconciles.data["ledger_error"]
    assert "negative" in reconciles.data["ledger_error"]


def test_a_token_count_that_is_not_an_integer_is_refused(tmp_path):
    """Same rule, the other way a column goes wrong.

    A string, a float, or a boolean in a token column means the writer is not
    what we think it is. ``True`` matters most: it is an ``int`` in Python and
    would otherwise be summed as one token.
    """
    for value in ("4200", 4200.5, True):
        calls = _good_calls() + [
            _call("cA", stage="perception", extra={"audio_input_tokens": value})
        ]
        findings, _ = verify(_write(tmp_path, calls))
        reconciles = next(f for f in findings if f.check == "usage_reconciles")
        assert reconciles.ok is False, f"{value!r} was accepted as a token count"
        assert "not an integer" in reconciles.data["ledger_error"]


def test_a_ledger_mixing_two_runs_is_caught(tmp_path):
    calls = _good_calls()
    calls[2]["run_id"] = "other_exp|cfgffffffffffffff|" + "d" * 64
    assert _verdict(_write(tmp_path, calls))["identity"] is False


def test_a_bad_score_is_not_a_billing_failure(tmp_path):
    """The separation this tool exists to keep: grading badly and accounting
    badly are different findings, and only one of them fails here."""
    calls = _good_calls()
    grade_path = _write(tmp_path, calls)
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    grade["summary"]["mean_score"] = 0.0
    grade_path.write_text(json.dumps(grade), encoding="utf-8")
    findings, context = verify(grade_path)
    assert all(f.ok for f in findings)
    assert context["quality"]["mean_score"] == 0.0


def test_the_command_line_exits_nonzero_on_a_broken_receipt(tmp_path):
    calls = _good_calls()
    receipt = _receipt_from(calls)
    receipt["model_cost_usd"] = 42.0
    grade_path = _write(tmp_path, calls, receipt)
    result = subprocess.run(
        [sys.executable, "scripts/verify_cost_ledger.py", str(grade_path), "--json"],
        cwd=BATCH_RUNNER_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout)["verdict"] == "fail"


def test_the_command_line_exits_zero_on_a_receipt_that_adds_up(tmp_path):
    grade_path = _write(tmp_path, _good_calls())
    result = subprocess.run(
        [sys.executable, "scripts/verify_cost_ledger.py", str(grade_path), "--json"],
        cwd=BATCH_RUNNER_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["verdict"] == "pass"


PUBLISHED_SMOKE = (
    BATCH_RUNNER_ROOT.parent
    / "data/grades/_diagnostic"
    / "17e2607b1a293be8802a36f1c1ca8e75b96e3437f99d707bfac13d9a9af247b1"
    / ("exp026c_cost_receipt_smoke__judge_gpt-5_4__cost_smoke_exp026c_v2_gpt54"
       "__cfg_c4348e8fa153ce8d__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf"
       "__inference_0d1d6df224d71aec23a0199ba1e7b272044b500b__src_7ca55f907056df2d__v2.2.json")
)


@pytest.mark.skipif(not PUBLISHED_SMOKE.exists(), reason="published smoke not in this checkout")
def test_the_receipt_this_repository_already_published_still_reconciles(tmp_path):
    """Guards the real artifact, not a fixture: if a later change breaks the
    reconciliation of a run already published, that is a regression."""
    findings, context = verify(PUBLISHED_SMOKE)
    failed = [f.check for f in findings if not f.ok]
    assert not failed, f"published receipt stopped reconciling: {failed}"
    assert context["receipt_status"] == "complete"
    assert context["settled_rows"] == 84


#: The same one task, graded again at the fingerprint the grader source moved to.
#: It sits *beside* the run above instead of replacing it, which is what the
#: _diagnostic fork is for, so both are recomputed here and neither stands in for
#: the other. Note its `cost_ledger.path` is repo-relative where the earlier run
#: wrote a bare filename: verify_cost_ledger.py:151 resolves by basename for
#: exactly that reason, and this is the artifact that shows it has to.
REPUBLISHED_SMOKE = (
    BATCH_RUNNER_ROOT.parent
    / "data/grades/_diagnostic"
    / "17e2607b1a293be8802a36f1c1ca8e75b96e3437f99d707bfac13d9a9af247b1"
    / ("exp026c_cost_receipt_smoke__judge_gpt-5_4__cost_smoke_exp026c_v2_gpt54"
       "__cfg_5b77131b1e1fc221__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf"
       "__inference_0d1d6df224d71aec23a0199ba1e7b272044b500b__src_f4931215d1ec316b__v2.2.json")
)


@pytest.mark.skipif(not REPUBLISHED_SMOKE.exists(), reason="re-run smoke not in this checkout")
def test_the_rerun_at_the_new_grader_fingerprint_also_reconciles():
    """The run this script was written to check. A receipt nobody recomputes is
    a receipt nobody knows is right."""
    findings, context = verify(REPUBLISHED_SMOKE)
    failed = [f.check for f in findings if not f.ok]
    assert not failed, f"the re-run receipt does not reconcile: {failed}"
    assert context["receipt_status"] == "complete"
    assert context["grader_source_hash"].startswith("f4931215d1ec316b"), (
        "this artifact is here because it was graded at the new fingerprint; if "
        "it is not, it is not the evidence the re-run was bought to produce"
    )
    assert context["settled_rows"] == context["call_rows"] == 112, (
        "every call must have come back and been recorded. A call sent whose "
        "reply was never written down is money that may have left and is not "
        "on the receipt -- the one gap a total cannot reveal on its own."
    )


def test_legacy_counters_that_drifted_from_the_ledger_are_caught(tmp_path):
    """The older summary.cost block counts the same calls; if it stops
    agreeing, one of the two is no longer describing this run."""
    calls = _good_calls()
    grade_path = _write(tmp_path, calls)
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    grade["summary"]["cost"] = {
        "total_judge_calls": 99,
        "total_input_tokens": 1,
        "estimated_cost_usd": None,
        "pricing_complete": False,
        "unpriced_models": ["gpt-5.4"],
    }
    grade_path.write_text(json.dumps(grade), encoding="utf-8")
    assert _verdict(grade_path)["legacy_counters"] is False


def test_a_pinned_null_price_beside_a_settled_receipt_is_not_a_disagreement(tmp_path):
    """core/grade_payload.py *requires* summary.cost to report null and to
    list configured models -- including ones never called. A settled receipt
    of real dollars beside it is the designed state, not a contradiction."""
    calls = _good_calls()
    grade_path = _write(tmp_path, calls)
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    grade["summary"]["cost"] = {
        "total_judge_calls": 3,
        "total_main_judge_calls": 2,
        "total_perception_calls": 1,
        "total_input_tokens": 2200,
        "total_output_tokens": 240,
        "total_cached_tokens": 1000,
        "estimated_cost_usd": None,
        "pricing_complete": False,
        "unpriced_models": ["gpt-5.4", "gpt-audio-1.5"],
    }
    grade_path.write_text(json.dumps(grade), encoding="utf-8")
    findings, _ = verify(grade_path)
    legacy = next(f for f in findings if f.check == "legacy_counters")
    assert legacy.ok is True
    assert legacy.data["legacy_estimated_cost_usd"] is None
    assert "gpt-audio-1.5" in legacy.data["legacy_unpriced_models"]
