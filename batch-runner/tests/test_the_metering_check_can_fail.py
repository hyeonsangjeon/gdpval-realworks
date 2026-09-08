"""The metering check has to be able to fail, or it is decoration.

`verify_audio_metering_run.py` judges 340 §6.2's nine conditions. It was
written before the run it will judge, which is the only way the conditions are
the plan's and not the result's -- and it means nothing has ever made it say
no. A checker that has only ever passed is indistinguishable from a checker
that cannot fail.

So this file builds a run that should pass, confirms it does, and then breaks
it in the four ways 340 §2 says a cost record actually goes wrong:

* a perception call filed under the wrong task, which moves money between two
  receipts that both still add up;
* the same call on the ledger twice;
* a call that went out and was never settled;
* a report claiming its prices are complete when a settled call names a model
  no table prices -- the defect 340 §2.2 measured in the original script,
  where ``pricing_complete`` was written from whether the run was paid for.

Each break has to be caught by the condition that claims to cover it, not
merely by *some* condition. A duplicate reported as "one request went
unrecorded" sends the reader looking for a missing call that does not exist.

Everything here runs offline against the real ledger and the committed price
table. No model is called.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = REPO_ROOT / "batch-runner"
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

from core.cost_receipts import (  # noqa: E402
    BUCKET_GRADING,
    RETRY_NONE,
    STAGE_PERCEPTION,
    STATE_RESERVED,
    STATE_SETTLED,
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
    ledger_reference,
    make_call_id,
)

SCRIPT_PATH = BATCH_RUNNER / "scripts" / "verify_audio_metering_run.py"


def _load_checker():
    """Import the script by path -- ``scripts/`` is not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "verify_audio_metering_run", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

RUN_ID = "audio-metering-rehearsal"
TASK_ID = "audio_metering_probe"
DEPLOYMENT = "gpt-audio-1.5"

#: What each of the two calls reported. Shaped after 337's real per-call
#: figures -- around 30 audio tokens for a clip of that length, inside an
#: input of a few hundred -- so the numbers the checker adds up are the size
#: the paid run will actually produce.
CALL_USAGE = (
    {"input_tokens": 412, "output_tokens": 55, "audio_input_tokens": 31},
    {"input_tokens": 409, "output_tokens": 61, "audio_input_tokens": 33},
)


def _build_ledger(tmp_path: Path, *, task_ids=None, settle=(True, True)):
    """Two perception calls through the real ledger, exported as JSONL.

    ``task_ids`` and ``settle`` exist so a caller can build a *wrong* ledger
    the same way the right one is built -- through ``reserve``/``settle``
    rather than by writing rows by hand, so the defect being tested is a
    defect in what was recorded and not in how the test spelt a row.
    """
    task_ids = task_ids or (TASK_ID, TASK_ID)
    table = load_receipt_price_table()
    database = tmp_path / "cost_ledger.sqlite3"
    with CostReceiptLedger(database, run_id=RUN_ID, price_table=table) as ledger:
        for index, (usage, task, should_settle) in enumerate(
            zip(CALL_USAGE, task_ids, settle)
        ):
            call_id = make_call_id(
                run_id=RUN_ID,
                task_id=task,
                stage=STAGE_PERCEPTION,
                retry_kind=RETRY_NONE,
                attempt_index=0,
                sequence=index,
            )
            ledger.reserve(
                call_id=call_id,
                task_id=task,
                stage=STAGE_PERCEPTION,
                retry_kind=RETRY_NONE,
                provider="azure",
                requested_model=DEPLOYMENT,
                deployment=DEPLOYMENT,
                api_version="2025-04-01-preview",
                request_sha256=hashlib.sha256(
                    f"request-{index}".encode("utf-8")
                ).hexdigest(),
            )
            if should_settle:
                ledger.settle(
                    call_id,
                    usage=CallUsage(**usage),
                    resolved_model=DEPLOYMENT,
                )
        export = tmp_path / "cost_ledger.jsonl"
        digest = ledger.export_jsonl(export)
        receipt = ledger.receipt_for(TASK_ID, BUCKET_GRADING)
    return export, digest, receipt, table


def _write_pair(
    tmp_path: Path,
    *,
    measured=True,
    task_ids=None,
    settle=(True, True),
    judge_errors=(None, None),
):
    """A report and the ledger beside it, as a passing run would leave them."""
    export, digest, receipt, table = _build_ledger(
        tmp_path, task_ids=task_ids, settle=settle
    )
    unpriced = [DEPLOYMENT] if table.lookup("azure", DEPLOYMENT) is None else []
    report = {
        "measured": measured,
        "calls": [
            {
                "claim_id": f"claim-{index}",
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "judge_error": judge_errors[index],
                "wire": {"requests": 1, "requests_with_audio": 1},
            }
            for index, usage in enumerate(CALL_USAGE)
        ],
        "cost": {
            "record_kind": "measured" if measured else "rehearsal",
            "task_id": TASK_ID,
            "model_calls": 2,
            "billable_calls": 2 if measured else 0,
            "models": [DEPLOYMENT],
            "price_table": {
                "path": str(
                    (BATCH_RUNNER / "experiments" / "execution_envelope"
                     / "model_price_table.json")
                ),
                "sha256": table.sha256,
            },
            "pricing_complete": not unpriced,
            "unpriced_models": unpriced,
            "estimated_cost_usd": (
                None
                if receipt.estimated_cost_usd is None
                else float(receipt.estimated_cost_usd)
            ),
            "receipt": receipt.as_dict(),
            "ledger": {
                **ledger_reference(export, digest),
                "rows": len(export.read_text(encoding="utf-8").splitlines()),
            },
        },
    }
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report_path, export


def _condition(outcome, number):
    for entry in outcome["conditions"]:
        if entry["condition"] == number:
            return entry
    raise AssertionError(f"no condition {number} in {outcome['conditions']}")


def _rewrite_ledger(report_path: Path, export: Path, rows):
    """Put mutated rows back, and re-stamp the report so the pair still match.

    Without the re-stamp every mutation below would be caught by the digest
    check instead of by the condition under test, and this file would prove
    only that sha256 works.
    """
    body = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    export.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(export.read_bytes()).hexdigest()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cost"]["ledger"]["sha256"] = digest
    report["cost"]["ledger"]["rows"] = len(rows)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _rows(export: Path):
    return [
        json.loads(line)
        for line in export.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ── the run that should pass ─────────────────────────────────────────────


def test_a_correctly_metered_run_passes_all_nine(tmp_path):
    report_path, _ = _write_pair(tmp_path)
    outcome = checker.check(report_path)

    assert outcome["counts"]["failed"] == 0, [
        entry for entry in outcome["conditions"] if entry["result"] == "fail"
    ]
    assert outcome["counts"]["passed"] == 9
    assert outcome["verdict"] == checker.VERDICT_MEASURED_OK


def test_the_unpriced_model_is_reported_as_unknown_and_never_as_zero(tmp_path):
    """gpt-audio-1.5 has no rate. Partial and null is the pass, not $0."""
    report_path, _ = _write_pair(tmp_path)
    outcome = checker.check(report_path)

    assert outcome["receipt_status"] == "partial"
    assert outcome["missing"]["price"] == ["price_missing"]
    assert outcome["missing"]["usage"] == []
    fourth = _condition(outcome, 4)
    assert fourth["result"] == "pass"
    assert fourth["data"]["estimated_cost_usd"] is None
    assert [entry["model"] for entry in fourth["data"]["unpriced_rows"]] == [
        DEPLOYMENT,
        DEPLOYMENT,
    ]


def test_a_run_whose_verdicts_all_broke_still_passes(tmp_path):
    """337's replies mostly failed to parse. That is not a metering failure.

    Condition 7 exists because a metering path that settles after parsing
    would have lost exactly those calls, and 340 §6.1 says the grading is not
    this test's question.
    """
    report_path, _ = _write_pair(
        tmp_path,
        judge_errors=("format_error:unparseable_json", "sub_judge_declined"),
    )
    outcome = checker.check(report_path)

    seventh = _condition(outcome, 7)
    assert seventh["result"] == "pass"
    assert seventh["data"]["calls_with_judge_error"] == 2
    assert outcome["verdict"] == checker.VERDICT_MEASURED_OK


# ── the four deliberate defects ──────────────────────────────────────────


def test_a_call_filed_under_another_task_is_caught_as_attribution(tmp_path):
    """Wrong task attribution. Both receipts still add up; the money moved."""
    report_path, export = _write_pair(tmp_path, task_ids=(TASK_ID, "some_other_task"))
    outcome = checker.check(report_path)

    fifth = _condition(outcome, 5)
    assert fifth["result"] == "fail"
    assert fifth["data"]["perception_rows_under_other_tasks"] == ["some_other_task"]
    assert "some_other_task" in fifth["detail"]
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_the_same_call_twice_is_named_a_duplicate_not_a_missing_request(tmp_path):
    """A duplicate reported as a count mismatch sends the reader the wrong way."""
    report_path, export = _write_pair(tmp_path)
    rows = _rows(export)
    _rewrite_ledger(report_path, export, rows + [dict(rows[0])])

    outcome = checker.check(report_path)
    first = _condition(outcome, 1)
    assert first["result"] == "fail"
    assert first["data"]["duplicate_call_ids"] == [rows[0]["call_id"]]
    assert "twice" in first["detail"]
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_an_unsettled_call_is_caught_by_the_token_comparison(tmp_path):
    """A settle that never happened. The request went out; the usage did not land."""
    report_path, _ = _write_pair(tmp_path, settle=(True, False))
    outcome = checker.check(report_path)

    third = _condition(outcome, 3)
    assert third["result"] == "fail"
    assert third["data"]["adapter_input_tokens"] == 412 + 409
    assert third["data"]["ledger_input_tokens"] == 412
    assert len(third["data"]["rows_left_reserved"]) == 1
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_a_reserved_row_keeps_the_receipt_from_claiming_completeness(tmp_path):
    """The same defect seen from the receipt: a call that may have been billed."""
    report_path, export = _write_pair(tmp_path, settle=(True, False))
    rows = _rows(export)
    states = {row["call_id"]: row["state"] for row in rows}
    assert sorted(states.values()) == [STATE_RESERVED, STATE_SETTLED]

    outcome = checker.check(report_path)
    assert "call_reachability_unknown" in outcome["missing"]["other"]


def test_a_report_claiming_complete_prices_for_an_unpriced_model_fails(tmp_path):
    """340 §2.2 exactly: the field was written from whether the run was paid for."""
    report_path, _ = _write_pair(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cost"]["pricing_complete"] = True
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    outcome = checker.check(report_path)
    eighth = _condition(outcome, 8)
    assert eighth["result"] == "fail"
    assert "complete" in eighth["detail"]
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_a_report_printing_zero_for_an_unpriced_run_fails(tmp_path):
    """The other half of the same mistake: an unknown amount shown as $0."""
    report_path, _ = _write_pair(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cost"]["estimated_cost_usd"] = 0.0
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    outcome = checker.check(report_path)
    eighth = _condition(outcome, 8)
    assert eighth["result"] == "fail"
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_an_unpriced_row_that_does_not_admit_it_fails_condition_four(tmp_path):
    """Inflated completeness at the row level: no rate, and no reason recorded.

    Only one of the two rows is stripped, so the receipt stays ``partial``
    from the other one. Otherwise this would pass through whichever branch
    fired first and prove nothing about the branch it names.
    """
    report_path, export = _write_pair(tmp_path)
    rows = _rows(export)
    rows[0]["missing_reasons"] = []
    _rewrite_ledger(report_path, export, rows)

    outcome = checker.check(report_path)
    fourth = _condition(outcome, 4)
    assert fourth["result"] == "fail"
    assert "price_missing" in fourth["detail"]
    assert outcome["receipt_status"] == "partial"
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_an_unpriced_row_carrying_an_amount_fails_condition_four(tmp_path):
    """The other row-level shape: a number that no published rate produced."""
    report_path, export = _write_pair(tmp_path)
    rows = _rows(export)
    assert "price_missing" in rows[0]["missing_reasons"]
    rows[0]["model_cost_usd"] = 0.0123
    _rewrite_ledger(report_path, export, rows)

    outcome = checker.check(report_path)
    fourth = _condition(outcome, 4)
    assert fourth["result"] == "fail"
    assert "still carry an amount" in fourth["detail"]
    assert outcome["verdict"] == checker.VERDICT_FAILED


# ── the rehearsal must not read as a measurement ─────────────────────────


def test_a_rehearsal_cannot_reach_measured_ok(tmp_path):
    """The stub reports no audio tokens, so condition 2 has no answer here."""
    report_path, export = _write_pair(tmp_path, measured=False)
    rows = _rows(export)
    for row in rows:
        row["audio_input_tokens"] = None
    _rewrite_ledger(report_path, export, rows)

    outcome = checker.check(report_path)
    second = _condition(outcome, 2)
    assert second["result"] == checker.RESULT_UNANSWERABLE
    assert second["unanswerable_because"] == checker.UNANSWERABLE_REHEARSAL
    assert outcome["counts"]["failed"] == 0
    assert outcome["verdict"] == checker.VERDICT_REHEARSAL_OK
    assert outcome["record_kind"] == "rehearsal"


def test_a_paid_run_that_lost_its_audio_tokens_fails_rather_than_abstains(tmp_path):
    """Unanswerable is for the rehearsal only. A paid run owes an answer."""
    report_path, export = _write_pair(tmp_path, measured=True)
    rows = _rows(export)
    for row in rows:
        row["audio_input_tokens"] = None
    _rewrite_ledger(report_path, export, rows)

    outcome = checker.check(report_path)
    second = _condition(outcome, 2)
    assert second["result"] == checker.RESULT_FAIL
    assert outcome["verdict"] == checker.VERDICT_FAILED


def test_the_rendered_output_says_a_rehearsal_is_not_evidence(tmp_path):
    report_path, export = _write_pair(tmp_path, measured=False)
    rows = _rows(export)
    for row in rows:
        row["audio_input_tokens"] = None
    _rewrite_ledger(report_path, export, rows)

    text = checker.render(checker.check(report_path))
    assert "rehearsal_ok" in text
    assert "NOT evidence" in text


# ── refusals ─────────────────────────────────────────────────────────────


def test_a_ledger_that_is_not_the_reports_ledger_is_refused(tmp_path):
    report_path, export = _write_pair(tmp_path)
    export.write_text(export.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(checker.ReportUnreadable) as raised:
        checker.check(report_path)
    assert "do not describe each other" in str(raised.value)


def test_a_price_table_that_moved_fails_rather_than_repricing(tmp_path):
    report_path, _ = _write_pair(tmp_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cost"]["price_table"]["sha256"] = "0" * 64
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    outcome = checker.check(report_path)
    fourth = _condition(outcome, 4)
    assert fourth["result"] == "fail"
    assert "--price-table" in fourth["detail"]


def test_337s_own_artifact_is_refused_because_it_was_never_metered(tmp_path):
    """The historical file, unchanged, cannot pass -- which is 340's finding.

    Read-only. 337's artifact is the record of ten paid calls and is not
    edited to suit a checker written afterwards.
    """
    artifact = (
        REPO_ROOT
        / "tasks"
        / "rebuilding_grading_task"
        / "337-audio-accuracy-measured.json"
    )
    if not artifact.is_file():  # pragma: no cover - the file is committed
        pytest.skip("337's artifact is not in this checkout")

    with pytest.raises(checker.ReportUnreadable) as raised:
        checker.check(artifact)
    message = str(raised.value)
    assert "no cost task id" in message or "ledger" in message


def test_the_exit_code_separates_a_failure_from_an_unreadable_pair(tmp_path, capsys):
    report_path, _ = _write_pair(tmp_path)
    assert checker.main([str(report_path)]) == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["cost"]["pricing_complete"] = True
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert checker.main([str(report_path)]) == 1

    report["cost"].pop("task_id")
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    assert checker.main([str(report_path)]) == 2


def test_the_json_output_carries_no_prompt_or_credential(tmp_path):
    """Digests and counts only. The ledger holds no prompt and this adds none."""
    report_path, _ = _write_pair(tmp_path)
    body = json.dumps(checker.check(report_path))

    for forbidden in ("api_key", "Authorization", "messages", "prompt_text"):
        assert forbidden not in body
