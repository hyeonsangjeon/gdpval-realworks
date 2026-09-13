"""The checker, exercised end to end on a bundle nothing hand-wrote.

``test_verify_cost_ledger.py`` plants defects in a receipt assembled by the
test itself. That proves the checks, but it cannot prove the path: if
``CostReceiptLedger`` or ``CostReceipt.as_dict`` stopped emitting a token kind
tomorrow, a hand-built fixture would go on stating it and every check would go
on passing. The gap this file closes is exactly the one the audio repair
exposed -- the ledger held 11,399 audio tokens for months while the published
receipt said nothing, because no test ever made the real serializer produce the
thing the real checker reads.

So every bundle here is built the way a run builds one:

    CostReceiptLedger.reserve/settle  ->  the real priced rows
    Ledger.receipt_for / summarise    ->  the real CostReceipt
    CostReceipt.as_dict               ->  the real serialization
    Ledger.export_jsonl               ->  the real sidecar and its hash
    schemas/grade.schema.json         ->  the real published contract
    scripts/verify_cost_ledger.verify ->  the real checker

Only then is a defect planted, one at a time, and the check that must notice is
named in the assertion. A planted defect that changes ledger bytes re-hashes
the sidecar first (see ``_replant``); otherwise every test below would stop at
``sidecar`` and prove nothing about the check it claims to exercise.

No model is called. Nothing outside ``tmp_path`` is read or written.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.cost_receipts import (  # noqa: E402
    AUDIO_BILLED_SEPARATELY,
    BUCKET_GRADING,
    CallUsage,
    CostReceiptLedger,
    RETRY_NONE,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    ledger_reference,
    load_receipt_price_table,
    make_call_id,
    summarise_receipts,
)
from scripts.verify_cost_ledger import verify  # noqa: E402

jsonschema = pytest.importorskip("jsonschema")

GRADE_SCHEMA = json.loads(
    (BATCH_RUNNER_ROOT / "schemas" / "grade.schema.json").read_text(encoding="utf-8")
)

SOURCE_HASH = "a" * 64
RUN_ID = f"exp_audio|cfg0123456789abcd|{SOURCE_HASH}"

#: One task that was graded partly by ear, one graded only from text, and one
#: whose model has no published rate. The third is not decoration: the 1.4
#: contract requires a published grade to name at least one unpriced model, and
#: a bundle with nothing unpriced could not be schema-valid at all.
TASK_SPOKEN = "4b894ae3-1a1f-4cf1-9b4e-7f0d1c2b3a45"
TASK_WRITTEN = "ff85ee58-2b2f-4d02-8c5a-6e1f2d3c4b56"
TASK_UNPRICED = "38889c3b-3c3f-4e13-7d6b-5f2e3d4c5b67"

TEXT_RATES = {
    "input_usd_per_million": "2.50",
    "cached_input_usd_per_million": "0.25",
    "output_usd_per_million": "15.00",
    "reasoning_billed_as": "output",
    "source": "https://example.invalid/prices",
    "last_reviewed": "2026-09-13",
    "currency": "USD",
    "unit": "per 1,000,000 tokens",
}
AUDIO_RATES = {
    **TEXT_RATES,
    "audio_billed_as": AUDIO_BILLED_SEPARATELY,
    "audio_input_usd_per_million": "40.00",
    "audio_output_usd_per_million": "80.00",
}


# ---------------------------------------------------------------------------
# 진짜 경로로 한 벌 만들기 -- 원장에서 영수증, 영수증에서 발행본까지
# ---------------------------------------------------------------------------


def _price_table(tmp_path: Path):
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(
            {
                "cost_receipt_schema_version": "cost-receipt-price-table-v1",
                "providers": {
                    "azure:judge-model": TEXT_RATES,
                    "azure:speech-model": AUDIO_RATES,
                },
            }
        ),
        encoding="utf-8",
    )
    return load_receipt_price_table(path)


def _settle(ledger, *, task_id, stage, model, usage, sequence):
    """One call, reserved and settled exactly as a grading run does it."""
    call_id = make_call_id(
        run_id=RUN_ID,
        task_id=task_id,
        stage=stage,
        retry_kind=RETRY_NONE,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=stage,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model=model,
    )
    ledger.settle(call_id, usage=usage, resolved_model=model)
    return call_id


def _task_entry(task_id: str, receipt: dict, *, judge_calls: int, perception_calls: int) -> dict:
    """A ``tasks[]`` row carrying the fields the 1.4 contract requires."""
    return {
        "task_id": task_id,
        "sector": "Health Care and Social Assistance",
        "occupation": "Audio and Video Technicians",
        "items": [
            {
                "rubric_item_id": "8184c2b3-0000-4000-8000-000000000001",
                "criterion": "Delivers the requested artefact in the requested format",
                "max_score": 2,
                "awarded_score": 2.0,
                "verdict": "pass",
                "decided_by": "judge",
                "required": None,
                "evidence": "## S: Subjective",
                "precheck_pattern_id": None,
            }
        ],
        "total_awarded": 2.0,
        "total_max": 2,
        "pct": 100.0,
        "critical_fail": False,
        "gold_referenced": False,
        "judge_call_count": judge_calls,
        "perception_call_count": perception_calls,
        "precheck_count": 0,
        "judge_total_latency_ms": 1200.0,
        "judge_input_tokens": 0,
        "judge_output_tokens": 0,
        "graded_at": "2026-09-13T00:00:00Z",
        "grading_cost": receipt,
    }


def _legacy_cost_block(rows: list[dict]) -> dict:
    """The pre-receipt ``summary.cost`` block, counted off the same calls.

    Audio is deliberately absent here. Audio tokens are a share *of* the input
    the provider already reported, so a legacy counter that added them would
    bill the same tokens twice. The receipt records the share; this block
    records the total. They are two views of one number, not two numbers.
    """
    grading = [r for r in rows if r["stage"] == STAGE_GRADING]
    perception = [r for r in rows if r["stage"] == STAGE_PERCEPTION]

    def _sum(subset, key):
        return sum(int(row.get(key) or 0) for row in subset)

    return {
        "estimated_cost_usd": None,
        "pricing_complete": False,
        "unpriced_models": ["no-rate-model"],
        "usage_complete": True,
        "total_judge_calls": len(rows),
        "total_main_judge_calls": len(grading),
        "total_perception_calls": len(perception),
        "total_input_tokens": _sum(rows, "input_tokens"),
        "total_output_tokens": _sum(rows, "output_tokens"),
        "total_cached_tokens": _sum(rows, "cached_input_tokens"),
        "main_input_tokens": _sum(grading, "input_tokens"),
        "main_output_tokens": _sum(grading, "output_tokens"),
        "main_cached_tokens": _sum(grading, "cached_input_tokens"),
        "perception_input_tokens": _sum(perception, "input_tokens"),
        "perception_output_tokens": _sum(perception, "output_tokens"),
        "perception_cached_tokens": _sum(perception, "cached_input_tokens"),
    }


class Bundle:
    """A published grade file, its ledger sidecar, and the rows behind both."""

    def __init__(self, grade_path: Path, ledger_path: Path, grade: dict, rows: list[dict]):
        self.grade_path = grade_path
        self.ledger_path = ledger_path
        self.grade = grade
        self.rows = rows

    def verdict(self) -> dict[str, bool]:
        findings, _ = verify(self.grade_path)
        return {finding.check: finding.ok for finding in findings}

    def finding(self, check: str):
        findings, _ = verify(self.grade_path)
        return next(f for f in findings if f.check == check)


@pytest.fixture
def bundle(tmp_path: Path) -> Bundle:
    """A run that reconciles, produced entirely by the shipping code."""
    table = _price_table(tmp_path)
    with CostReceiptLedger(tmp_path / "cost.sqlite3", run_id=RUN_ID, price_table=table) as ledger:
        _settle(
            ledger,
            task_id=TASK_SPOKEN,
            stage=STAGE_GRADING,
            model="judge-model",
            usage=CallUsage(
                input_tokens=1000,
                cached_input_tokens=200,
                output_tokens=300,
                reasoning_tokens=50,
            ),
            sequence=0,
        )
        # The call that the old contract could not express: audio tokens sit
        # inside the input the provider reported, and are priced separately.
        _settle(
            ledger,
            task_id=TASK_SPOKEN,
            stage=STAGE_PERCEPTION,
            model="speech-model",
            usage=CallUsage(
                input_tokens=415,
                cached_input_tokens=0,
                output_tokens=67,
                reasoning_tokens=0,
                audio_input_tokens=30,
                audio_output_tokens=0,
            ),
            sequence=1,
        )
        for sequence in (2, 3):
            _settle(
                ledger,
                task_id=TASK_WRITTEN,
                stage=STAGE_GRADING,
                model="judge-model",
                usage=CallUsage(
                    input_tokens=1000,
                    cached_input_tokens=200,
                    output_tokens=300,
                    reasoning_tokens=50,
                ),
                sequence=sequence,
            )
        # No rate exists for this model. The call is fully recorded and its
        # dollar figure stays unknown -- an honest partial, not a zero.
        _settle(
            ledger,
            task_id=TASK_UNPRICED,
            stage=STAGE_GRADING,
            model="no-rate-model",
            usage=CallUsage(
                input_tokens=800,
                cached_input_tokens=0,
                output_tokens=120,
                reasoning_tokens=0,
            ),
            sequence=4,
        )

        receipts = {
            task: ledger.receipt_for(task, BUCKET_GRADING)
            for task in (TASK_SPOKEN, TASK_WRITTEN, TASK_UNPRICED)
        }
        summary_receipt = summarise_receipts(list(receipts.values()))
        rows = [
            row
            for task in (TASK_SPOKEN, TASK_WRITTEN, TASK_UNPRICED)
            for row in ledger.calls_for(task)
        ]
        ledger_path = tmp_path / "run__src_aaaaaaaaaaaaaaaa__v2.2.cost_ledger.jsonl"
        sidecar_sha = ledger.export_jsonl(ledger_path)

    grade = {
        "schema_version": "1.4",
        "run_status": "diagnostic",
        "experiment_id": "exp_audio",
        "experiment_yaml_name": "exp_audio",
        "expected_task_count": 3,
        "expected_ordered_task_ids_sha256": "c" * 64,
        "azure_ai_routes": [
            {
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": "d" * 64,
                "workload": "grader",
            }
        ],
        "azure_ai_runtime_fingerprint": "d" * 64,
        "graded_at": "2026-09-13T00:00:00Z",
        "graded_by": "step8_grade.py",
        "grader_source_hash": SOURCE_HASH,
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "judge-model",
            "deployment": "judge-model",
            "api_version": "2025-04-01-preview",
            "reasoning_effort": "max",
            "temperature": 0,
            "seed": 42,
            "config_name": "default",
            "config_hash": "cfg0123456789abcd",
        },
        "rubric": {
            "source": "huggingface",
            "repo_id": "openai/gdpval",
            "revision": "e" * 40,
            "commit_sha": "e" * 40,
            "short_sha": "e" * 7,
        },
        "prompt": {"template": "prompts/grader_judge.md", "version": "v2.2"},
        "cost_ledger": ledger_reference(ledger_path.name, sidecar_sha),
        "tasks": [
            _task_entry(TASK_SPOKEN, receipts[TASK_SPOKEN].as_dict(),
                        judge_calls=1, perception_calls=1),
            _task_entry(TASK_WRITTEN, receipts[TASK_WRITTEN].as_dict(),
                        judge_calls=2, perception_calls=0),
            _task_entry(TASK_UNPRICED, receipts[TASK_UNPRICED].as_dict(),
                        judge_calls=1, perception_calls=0),
        ],
        "summary": {
            "total_tasks": 3,
            "graded_tasks": 3,
            "error_tasks": 0,
            "openai_compat": {
                "avg_score_pct": 100.0,
                "ci_pct": 0.0,
                "perfect_count": 3,
                "zero_count": 0,
                "partial_count": 0,
                "inconsistent_count": 0,
            },
            "wow": {"judge_error_rate": 0.0},
            "cost": _legacy_cost_block(rows),
            "grading_cost": summary_receipt.as_dict(),
        },
    }
    grade_path = tmp_path / "run__src_aaaaaaaaaaaaaaaa__v2.2.json"
    grade_path.write_text(json.dumps(grade, indent=2), encoding="utf-8")
    return Bundle(grade_path, ledger_path, grade, rows)


def _replant(bundle: Bundle, *, rows: list[dict] | None = None, grade: dict | None = None) -> Bundle:
    """Rewrite the bundle with a planted defect, re-hashing the sidecar.

    This is load-bearing. ``check_sidecar`` compares the ledger's bytes against
    the hash the grade file declares and stops the whole verification if they
    differ. Every defect below that touches the ledger would therefore fail at
    ``sidecar`` and never reach the check it is meant to exercise -- proving
    only that a hash works. Re-hashing forges nothing: it reproduces the state
    a defective *publisher* would have produced, which is the state worth
    catching.
    """
    new_rows = bundle.rows if rows is None else rows
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in new_rows
    )
    bundle.ledger_path.write_text(payload, encoding="utf-8")

    new_grade = deepcopy(bundle.grade) if grade is None else grade
    new_grade["cost_ledger"]["sha256"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bundle.grade_path.write_text(json.dumps(new_grade, indent=2), encoding="utf-8")
    return Bundle(bundle.grade_path, bundle.ledger_path, new_grade, new_rows)


def _validate(grade: dict) -> None:
    jsonschema.validate(instance=grade, schema=GRADE_SCHEMA)


def _summary_usage(grade: dict) -> dict:
    return grade["summary"]["grading_cost"]["usage"]


# ---------------------------------------------------------------------------
# 1. 진짜 직렬화기가 오디오를 싣고, 진짜 스키마가 그것을 받는가
# ---------------------------------------------------------------------------


def test_the_real_serializer_carries_audio_through_to_the_published_file(bundle):
    """The whole point: nobody hand-wrote this number into the receipt."""
    usage = _summary_usage(bundle.grade)
    assert usage["audio_input_tokens"] == 30
    assert usage["audio_output_tokens"] == 0
    assert usage["input_tokens"] == 1000 + 415 + 1000 + 1000 + 800


def test_the_published_schema_accepts_the_bundle_the_serializer_produced(bundle):
    _validate(bundle.grade)


def test_a_bundle_built_by_the_shipping_code_passes_every_check(bundle):
    verdict = bundle.verdict()
    assert all(verdict.values()), f"an honest bundle must be clean: {verdict}"


def test_audio_sits_inside_the_reported_input_rather_than_beside_it(bundle):
    """The 415-token speech call reported 30 of those tokens as audio.

    If audio were added to input instead of being a share of it, the totals
    would be 30 higher. ``usage_reconciles`` would still pass -- receipt and
    ledger would agree on the inflated figure -- which is why this is asserted
    against the call the test itself made, not against the checker.
    """
    speech = next(r for r in bundle.rows if r["stage"] == STAGE_PERCEPTION)
    assert speech["input_tokens"] == 415
    assert speech["audio_input_tokens"] == 30
    assert speech["audio_input_tokens"] < speech["input_tokens"]


def test_the_speech_call_is_not_charged_at_the_price_of_prose(bundle):
    """30 audio tokens at $40/M, 385 text tokens at $2.50/M, output at $15/M."""
    speech = next(r for r in bundle.rows if r["stage"] == STAGE_PERCEPTION)
    expected = (
        (415 - 30) * 2.50 / 1_000_000 + 30 * 40.00 / 1_000_000 + 67 * 15.00 / 1_000_000
    )
    assert float(speech["model_cost_usd"]) == pytest.approx(expected, rel=1e-9)
    prose = (415 * 2.50 + 67 * 15.00) / 1_000_000
    assert float(speech["model_cost_usd"]) > prose


# ---------------------------------------------------------------------------
# 2. 심어 둔 결함 -- 누락, 거짓 0, 무효값
# ---------------------------------------------------------------------------


def test_a_receipt_that_drops_the_audio_count_is_caught(bundle):
    """The defect this repair exists to catch, reproduced deliberately."""
    grade = deepcopy(bundle.grade)
    del grade["summary"]["grading_cost"]["usage"]["audio_input_tokens"]
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["usage_reconciles"] is False
    detail = planted.finding("usage_reconciles").data
    assert detail["audio_input_tokens"] == {"receipt": None, "ledger": 30}


def test_a_receipt_claiming_zero_audio_over_a_ledger_that_measured_some_is_caught(bundle):
    """Silence and a measured zero must not arrive as the same integer."""
    grade = deepcopy(bundle.grade)
    grade["summary"]["grading_cost"]["usage"]["audio_input_tokens"] = 0
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["usage_reconciles"] is False
    assert planted.finding("usage_reconciles").data["audio_input_tokens"] == {
        "receipt": 0,
        "ledger": 30,
    }


def test_a_ledger_that_measured_nothing_still_refuses_a_stated_zero(bundle):
    """The asymmetry, stated as a test rather than left to a comment.

    ``audio_output_tokens`` is a measured 0 across this run, so a receipt that
    says nothing about it is *not* equivalent. Letting silence agree with a
    measured zero would let a serializer that dropped a whole token kind pass
    on every run where that kind happened to total nothing.
    """
    grade = deepcopy(bundle.grade)
    del grade["summary"]["grading_cost"]["usage"]["audio_output_tokens"]
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["usage_reconciles"] is False


def test_a_negative_audio_count_is_rejected_by_both_the_schema_and_the_checker(bundle):
    grade = deepcopy(bundle.grade)
    grade["summary"]["grading_cost"]["usage"]["audio_input_tokens"] = -5
    with pytest.raises(jsonschema.ValidationError):
        _validate(grade)
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["usage_reconciles"] is False
    assert "problem" in planted.finding("usage_reconciles").data["audio_input_tokens"]


@pytest.mark.parametrize("value", ["30", 30.5, True])
def test_an_audio_count_that_is_not_a_whole_number_is_rejected(bundle, value):
    """A string, a fraction, and a boolean are three ways to look like 30."""
    grade = deepcopy(bundle.grade)
    grade["summary"]["grading_cost"]["usage"]["audio_input_tokens"] = value
    with pytest.raises(jsonschema.ValidationError):
        _validate(grade)
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["usage_reconciles"] is False


def test_a_negative_audio_count_in_the_ledger_stops_the_sum_rather_than_passing_it_on(bundle):
    rows = deepcopy(bundle.rows)
    next(r for r in rows if r["stage"] == STAGE_PERCEPTION)["audio_input_tokens"] = -30
    planted = _replant(bundle, rows=rows)
    assert planted.verdict()["usage_reconciles"] is False
    assert "cannot be summed" in planted.finding("usage_reconciles").detail


# ---------------------------------------------------------------------------
# 3. 심어 둔 결함 -- 이중 계상, 중복 호출, 미지 양식
# ---------------------------------------------------------------------------


def test_audio_added_to_the_input_total_instead_of_being_a_share_of_it_is_caught(bundle):
    """The double count the contract had to be written to forbid."""
    grade = deepcopy(bundle.grade)
    usage = grade["summary"]["grading_cost"]["usage"]
    usage["input_tokens"] = usage["input_tokens"] + usage["audio_input_tokens"]
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["usage_reconciles"] is False
    assert planted.finding("usage_reconciles").data["input_tokens"] == {
        "receipt": 4245,
        "ledger": 4215,
    }


def test_the_same_call_appearing_twice_in_the_ledger_is_caught(bundle):
    rows = deepcopy(bundle.rows)
    rows.append(deepcopy(rows[0]))
    planted = _replant(bundle, rows=rows)
    assert planted.verdict()["no_double_billing"] is False


def test_a_token_kind_the_receipt_cannot_express_is_reported_not_swallowed(bundle):
    """``cache_write_input_tokens`` is real and ``cost-receipt-v1`` has no field for it.

    Closing the audio gap must not turn ``usage_containment`` into a check that
    only ever knew about audio. It asks the same question of whatever the
    ledger carries today, so a kind nobody has modelled yet still surfaces.
    """
    rows = deepcopy(bundle.rows)
    rows[0]["cache_write_input_tokens"] = 900
    planted = _replant(bundle, rows=rows)
    assert planted.verdict()["usage_containment"] is False
    data = planted.finding("usage_containment").data
    assert data["unexpressible_keys"] == ["cache_write_input_tokens"]
    assert data["totals"]["cache_write_input_tokens"] == 900


def test_an_unmodelled_kind_that_is_present_but_zero_is_not_reported_as_loss(bundle):
    rows = deepcopy(bundle.rows)
    rows[0]["cache_write_input_tokens"] = 0
    planted = _replant(bundle, rows=rows)
    assert planted.verdict()["usage_containment"] is True


def test_an_unmodelled_kind_cannot_be_smuggled_into_the_receipt_itself(bundle):
    """``additionalProperties: false`` is what makes the new fields a contract.

    Permitting arbitrary extra keys would have "fixed" audio without deciding
    anything: two runs could spell the same quantity differently and both
    validate.
    """
    grade = deepcopy(bundle.grade)
    grade["summary"]["grading_cost"]["usage"]["cache_write_input_tokens"] = 900
    with pytest.raises(jsonschema.ValidationError):
        _validate(grade)


# ---------------------------------------------------------------------------
# 4. 심어 둔 결함 -- 잘못된 요청/과제 신원
# ---------------------------------------------------------------------------


def test_a_ledger_holding_two_runs_worth_of_calls_is_caught(bundle):
    rows = deepcopy(bundle.rows)
    rows[-1]["run_id"] = RUN_ID.replace("exp_audio", "exp_other")
    planted = _replant(bundle, rows=rows)
    assert planted.verdict()["identity"] is False


def test_a_ledger_written_by_a_different_grader_than_the_grade_claims_is_caught(bundle):
    grade = deepcopy(bundle.grade)
    grade["grader_source_hash"] = "f" * 64
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["identity"] is False


def test_a_call_refiled_under_another_task_is_caught(bundle):
    """The tokens are all still there; only the task they are billed to moved."""
    rows = deepcopy(bundle.rows)
    next(r for r in rows if r["stage"] == STAGE_PERCEPTION)["task_id"] = TASK_WRITTEN
    planted = _replant(bundle, rows=rows)
    verdict = planted.verdict()
    assert verdict["task_coverage"] is False
    assert verdict["usage_reconciles"] is True, "the run-wide totals did not move"


def test_a_call_refiled_under_a_task_the_grade_never_names_is_caught(bundle):
    """Caught through the task it was taken from, not the one it landed on.

    A 1.4 payload makes every task state its own call counts, so an orphaned
    call leaves a task declaring more than the ledger holds. The check reads
    the shortfall there; nothing has to recognise the invented task id.
    """
    orphan = "00000000-0000-4000-8000-000000000000"
    rows = deepcopy(bundle.rows)
    rows[0]["task_id"] = orphan
    planted = _replant(bundle, rows=rows)

    assert planted.verdict()["task_coverage"] is False
    disputed = planted.finding("task_coverage").data["disputed"]
    assert [d["task_id"] for d in disputed] == [TASK_SPOKEN]
    assert disputed[0]["declared_calls"] == 2
    assert disputed[0]["ledger_calls"] == 1
    assert orphan not in {task["task_id"] for task in planted.grade["tasks"]}


def test_a_component_line_that_omits_a_kind_its_own_calls_reported_is_caught(bundle):
    """Per line, not only in the grand total, where two errors could cancel."""
    grade = deepcopy(bundle.grade)
    for component in grade["summary"]["grading_cost"]["components"]:
        if component.get("stage") == STAGE_PERCEPTION:
            component["usage"]["audio_input_tokens"] = None
    planted = _replant(bundle, grade=grade)
    assert planted.verdict()["components_reconcile"] is False


# ---------------------------------------------------------------------------
# 5. 옛 기록과 옛 독자 보존
# ---------------------------------------------------------------------------


def test_a_receipt_written_before_audio_existed_still_validates(bundle):
    """The four-key usage block every published grade currently carries."""
    grade = deepcopy(bundle.grade)
    grade["summary"]["grading_cost"]["usage"] = {
        "input_tokens": 345524,
        "cached_input_tokens": 233918,
        "output_tokens": 15513,
        "reasoning_tokens": 9383,
    }
    _validate(grade)


def test_a_run_that_never_touched_audio_is_clean_from_end_to_end(tmp_path):
    """No audio anywhere: the new fields stay absent and nothing goes red."""
    table = _price_table(tmp_path)
    with CostReceiptLedger(tmp_path / "cost.sqlite3", run_id=RUN_ID, price_table=table) as ledger:
        _settle(
            ledger,
            task_id=TASK_WRITTEN,
            stage=STAGE_GRADING,
            model="judge-model",
            usage=CallUsage(
                input_tokens=1000,
                cached_input_tokens=200,
                output_tokens=300,
                reasoning_tokens=50,
            ),
            sequence=0,
        )
        receipt = ledger.receipt_for(TASK_WRITTEN, BUCKET_GRADING).as_dict()

    assert receipt["usage"]["audio_input_tokens"] is None
    assert receipt["usage"]["audio_output_tokens"] is None
    assert receipt["usage"]["input_tokens"] == 1000


def test_absent_and_zero_are_both_valid_to_the_schema_and_different_to_the_checker(bundle):
    """The schema cannot tell them apart; that is the verifier's job, not its own."""
    absent = deepcopy(bundle.grade)
    absent["summary"]["grading_cost"]["usage"]["audio_input_tokens"] = None
    _validate(absent)

    stated = deepcopy(bundle.grade)
    stated["summary"]["grading_cost"]["usage"]["audio_input_tokens"] = 0
    _validate(stated)

    assert _replant(bundle, grade=absent).verdict()["usage_reconciles"] is False
    assert _replant(bundle, grade=stated).verdict()["usage_reconciles"] is False


# ---------------------------------------------------------------------------
# 6. 없는 가격은 정직한 부분 비용으로 남는다
# ---------------------------------------------------------------------------


def test_a_model_with_no_published_rate_stays_unknown_rather_than_zero(bundle):
    unpriced = next(r for r in bundle.rows if r["resolved_model"] == "no-rate-model")
    assert unpriced["model_cost_usd"] is None
    assert unpriced["input_tokens"] == 800, "usage is fully recorded; only the price is missing"

    receipt = bundle.grade["summary"]["grading_cost"]
    assert receipt["status"] == "partial"
    assert receipt["estimated_cost_usd"] is None
    assert receipt["known_cost_usd"] > 0

    verdict = bundle.verdict()
    assert verdict["partial_cause"] is True
    assert verdict["price_table"] is True
