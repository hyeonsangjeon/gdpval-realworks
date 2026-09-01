"""The judge's second attempt is billed to the same line as its first.

A receipt line is one model identity at one stage at one retry kind, and the
solving side honours that: ``step2_run_inference.py`` opens the Self-QA loop's
second attempt under ``RETRY_SEMANTIC``, so "what did generating cost" and
"what did retrying cost" are two rows a reader can tell apart.

The grading side never sets a retry kind at all. Its one billed retry is the
judge's finalization retry — the first attempt came back with no final text, or
with text that is not the envelope, so the judge spends a second call asking for
the envelope alone. ``core/grader.py`` opens exactly one scope for the whole
task (``attributed(task_id=..., stage=STAGE_GRADING)``) and its own comment says
so: "judge turns, retries inside the judge, and the perception reads it
delegates" all land in that one window. The perception reads escape it through
their own metered wrapper. The retry does not.

So a task that retried shows one ``grading`` row with two calls in it, and the
question the card has been carrying as unproven — what does retrying cost —
cannot be answered from the receipt, because the number is inside a bigger one.
Measured on ``main`` before the fix: one line, ``retry_kind='none'``, two calls,
one amount.

The fix is a third metered wrapper on the same connection, pinned to
``RETRY_SEMANTIC``, handed to the judge as ``retry_client``. The judge spends it
for the finalization retry and the main client for everything else, so the pair
becomes two rows carrying the same total. Priced at the fixture table below that
is $4.00 for the attempt that failed and $2.00 for the one that worked: both
real money, and only one of them bought a verdict.

No provider is contacted. The judge is driven by a scripted client and every
amount here comes from the fixture price table.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core.cost_metering import CostRecorder
from core.cost_receipts import (
    BUCKET_GRADING,
    RETRY_KINDS,
    RETRY_NONE,
    RETRY_SEMANTIC,
    STAGE_GRADING,
    STATUS_COMPLETE,
    CostReceiptLedger,
    load_receipt_price_table,
)
from core.rubric_loader import RubricItem, TaskRubric
from core.tool_calling_judge import ToolCallingJudge

from tests.test_tool_calling_judge import (
    PROMPT_TEMPLATE,
    FakeClient,
    ScriptedResponses,
    _final,
    _response,
)


#: One deployment, one rate. The point of these tests is which row an amount
#: lands in, so the table stays small enough that every figure below can be
#: checked by hand: 100 input tokens at $10/M plus 30 output at $20/M is
#: $0.0010 + $0.0006 = $0.0016 for the default reply shape.
FIXTURE_RATE = {
    "input_usd_per_million": "10",
    "cached_input_usd_per_million": "10",
    "output_usd_per_million": "20",
    "reasoning_billed_as": "output",
    "source": "fixture",
    "last_reviewed": "2026-08-28",
    "currency": "USD",
    "unit": "per 1,000,000 tokens",
}


def price_table(*deployments: str) -> dict:
    """The same rate for every deployment named.

    The last test prices whatever deployment the committed marking settings
    name rather than a fixed string, so renaming the judge deployment moves
    the test with it instead of turning the receipt unpriced underneath it.
    """
    return {
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": {f"azure:{name}": dict(FIXTURE_RATE) for name in deployments},
        "runtime": {},
    }


PRICE_TABLE = price_table("judge-deployment")

#: Input/output token counts chosen so the two calls cannot be confused: the
#: failed attempt costs exactly twice the one that recovered.
FAILED_ATTEMPT = {"in_tok": 200_000, "out_tok": 100_000}   # $2.00 + $2.00
RECOVERY = {"in_tok": 100_000, "out_tok": 50_000}          # $1.00 + $1.00

FAILED_ATTEMPT_USD = Decimal("4.00")
RECOVERY_USD = Decimal("2.00")


def make_recorder(tmp_path, table: dict) -> CostReceiptLedger:
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(table), encoding="utf-8")
    return CostReceiptLedger(
        tmp_path / "cost.sqlite3",
        run_id="run-1",
        price_table=load_receipt_price_table(path),
    )


@pytest.fixture
def recorder(tmp_path):
    with make_recorder(tmp_path, PRICE_TABLE) as ledger:
        yield CostRecorder(ledger)


@pytest.fixture
def deliverable_dir(tmp_path) -> Path:
    """A one-cell workbook, because the read tool opens the file for real."""
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "alpha"
    workbook.save(tmp_path / "report.xlsx")
    return tmp_path


@pytest.fixture
def task_and_item() -> tuple[TaskRubric, RubricItem]:
    item = RubricItem(
        rubric_item_id="r1",
        criterion="The deliverable contains an 'alpha' label in column A",
        score=5,
        required=None,
    )
    task = TaskRubric(
        task_id="task-a",
        sector="Information",
        occupation="Analyst",
        prompt="Make a report",
        rubric_items=[item],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    return task, item


def _retrying_client() -> FakeClient:
    """A judge call that fails its envelope, then succeeds on the retry.

    ``{}`` parses but is not the envelope, which is
    ``_finalization_retry_reason``'s ``invalid_final_envelope`` — the plain
    case, with none of the reasoning-effort special handling that
    ``empty_final_text:max_output_tokens`` brings with it.
    """
    verdict = json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "the report states a number",
        "confidence": 0.9,
        "reasoning": "recovered on the finalization retry",
    })
    return FakeClient(ScriptedResponses([
        _response(output=[_final("{}")], **FAILED_ATTEMPT),
        _response(output=[_final(verdict)], **RECOVERY),
    ]))


def _judge(client: FakeClient, **kwargs) -> ToolCallingJudge:
    return ToolCallingJudge(
        client=client,
        model="judge-deployment",
        prompt_template=PROMPT_TEMPLATE,
        max_iterations=1,
        finalization_retries=1,
        **kwargs,
    )


def _lines(receipt) -> dict[str, tuple[int, Decimal]]:
    """``retry_kind -> (calls, amount)``, for a receipt of one stage."""
    return {
        line.retry_kind: (line.model_calls, line.known_cost_usd)
        for line in receipt.components
    }


def test_the_judge_retry_is_billed_to_the_line_it_belongs_to(
    recorder, deliverable_dir, task_and_item
):
    """Two attempts, two rows: the failed one and the one that recovered."""
    task, item = task_and_item
    client = _retrying_client()
    judge = _judge(
        recorder.meter(client, provider="azure", model="judge-deployment"),
        retry_client=recorder.meter(
            client,
            provider="azure",
            model="judge-deployment",
            retry_kind=RETRY_SEMANTIC,
        ),
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
        result = judge.judge_item(
            task=task,
            item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=["report.xlsx"],
        )

    # The retry did happen and did recover, so both calls are real money.
    assert result.verdict == "pass"
    assert result.main_api_call_count == 2

    receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 2
    assert _lines(receipt) == {
        RETRY_NONE: (1, FAILED_ATTEMPT_USD),
        RETRY_SEMANTIC: (1, RECOVERY_USD),
    }
    # The task's bill is unchanged by the split — the same money, told apart.
    assert receipt.known_cost_usd == FAILED_ATTEMPT_USD + RECOVERY_USD


def test_a_judge_that_never_retried_still_files_one_line(
    recorder, deliverable_dir, task_and_item
):
    """Negative control: the split must not invent a row nobody spent.

    A `retry` row reading $0.0000 on every task that went right would be the
    same lie in the other direction — the reader would learn that retrying is
    free, from tasks that never retried.
    """
    task, item = task_and_item
    verdict = json.dumps({
        "verdict": "pass",
        "partial_score": 1.0,
        "evidence": "the report states a number",
        "confidence": 0.9,
        "reasoning": "first attempt was fine",
    })
    client = FakeClient(ScriptedResponses([
        _response(output=[_final(verdict)], **RECOVERY),
    ]))
    judge = _judge(
        recorder.meter(client, provider="azure", model="judge-deployment"),
        retry_client=recorder.meter(
            client,
            provider="azure",
            model="judge-deployment",
            retry_kind=RETRY_SEMANTIC,
        ),
    )

    with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
        result = judge.judge_item(
            task=task,
            item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=["report.xlsx"],
        )

    assert result.main_api_call_count == 1
    receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
    assert _lines(receipt) == {RETRY_NONE: (1, RECOVERY_USD)}


def test_an_unmetered_judge_keeps_working_without_a_retry_client(
    recorder, deliverable_dir, task_and_item
):
    """Negative control: metering stays opt-in.

    Grading runs without a recorder hand the judge a bare client and no retry
    client at all. The retry has to fall back to the one client it has, or
    turning metering off would stop the judge from retrying.
    """
    task, item = task_and_item
    client = _retrying_client()
    judge = _judge(client)

    result = judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )

    assert result.verdict == "pass"
    assert result.main_api_call_count == 2


def test_the_judge_the_grader_really_builds_bills_its_retry_apart(tmp_path):
    """The wiring, on the settings a real marking run loads.

    The three tests above hand ``ToolCallingJudge`` a retry client directly, so
    they prove the judge spends it correctly and prove nothing about whether
    anything gives the judge one. Deleting the single line in ``core/grader.py``
    that passes ``retry_client=`` leaves all three green and puts production
    straight back to one merged line — checked, and it does.

    So this one builds the grader from a committed marking settings file, takes
    the judge that grader built, and drives it through the same retry.
    """
    from core.grader import Grader

    config_path = Path("grading_configs/default_v2.yaml")
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    deployment = document["judge"]["model"]

    task = TaskRubric(
        task_id="task-a",
        sector="Information",
        occupation="Analyst",
        prompt="Make a report",
        rubric_items=[],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    item = RubricItem(
        rubric_item_id="r1",
        criterion="The deliverable contains an 'alpha' label in column A",
        score=5,
        required=None,
    )
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "alpha"
    deliverables = tmp_path / "deliverables"
    deliverables.mkdir()
    workbook.save(deliverables / "report.xlsx")

    client = _retrying_client()
    with make_recorder(tmp_path, price_table(deployment)) as ledger:
        recorder = CostRecorder(ledger)
        grader = Grader(
            document,
            rubric_loader=None,
            client=client,
            cost_recorder=recorder,
        )
        judge = grader._tool_judge
        assert judge is not None, "the committed settings built no judge"

        with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
            result = judge.judge_item(
                task=task,
                item=item,
                deliverable_dir=str(deliverables),
                file_names=["report.xlsx"],
            )

        assert result.main_api_call_count == 2
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert _lines(receipt) == {
        RETRY_NONE: (1, FAILED_ATTEMPT_USD),
        RETRY_SEMANTIC: (1, RECOVERY_USD),
    }


def test_a_retry_kind_the_ledger_does_not_know_is_refused_at_the_wrapper(
    recorder,
):
    """A misspelled pin fails where it is written, not on the receipt.

    ``_component_key`` groups on the retry kind verbatim, so a typo would not
    error — it would quietly open a line of its own, and the reader would see a
    row for ``semanitc`` beside the one for ``semantic`` and have no way to
    know they are the same spend. Mirrors the ``stage`` check beside it.
    """
    with pytest.raises(ValueError, match="unknown retry kind"):
        recorder.meter(object(), provider="azure", retry_kind="semanitc")

    # Negative control: every kind the ledger does know is still accepted.
    for kind in RETRY_KINDS:
        recorder.meter(object(), provider="azure", retry_kind=kind)
