"""An item the judge never answered must say which kind of silence it was.

On the 185-task gold run thirteen items across ten tasks came back with an
empty verdict. Each cost 60-85 seconds of grading, and each was written down
as the bare string ``empty_final_text`` -- the same six words for a model that
exhausted its output budget, a model whose reply was filtered, and a model
that simply returned nothing. Afterwards there was no way to tell them apart
without paying to grade them again, and they need opposite responses: the
first is fixed by a bigger budget, the second by a different prompt, the third
by neither.

Nothing was broken. ``_finalization_retry_reason`` already works the answer
out -- it has to, because whether to retry depends on it -- and the value was
read once, used for that decision, and then dropped on the floor. These tests
pin it to the record instead.

The one thing this change must NOT do is move a score: an unanswered item is
excluded from the denominator today, and it is still excluded now. Making the
label honest is a separate job from deciding what an unanswered item is worth.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Optional

import pytest

from core.rubric_loader import RubricItem, TaskRubric
from core.tool_calling_judge import ToolCallingJudge
import core.tool_calling_judge as tcj


PROMPT_TEMPLATE = (
    Path(__file__).resolve().parent.parent / "prompts" / "grader_judge_v2.md"
).read_text(encoding="utf-8")


# ── the smallest client that can return a scripted reply ─────────────

def _response(
    *,
    output: Optional[list] = None,
    out_tok: int = 2400,
    status: Optional[str] = None,
    incomplete_reason: Optional[str] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        output=output or [],
        output_text="",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=out_tok,
            input_tokens_details=SimpleNamespace(cached_tokens=7),
        ),
        incomplete_details=(
            SimpleNamespace(reason=incomplete_reason)
            if incomplete_reason is not None
            else None
        ),
        status=status,
    )


def _envelope() -> dict:
    return {
        "type": "message",
        "content": [{
            "type": "output_text",
            "text": json.dumps({
                "verdict": "pass",
                "partial_score": 1.0,
                "evidence": "column A carries the alpha label",
                "confidence": 0.9,
                "reasoning": "read the sheet",
            }),
        }],
    }


class _Responses:
    def __init__(self, script: list):
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("scripted client ran out of responses")
        nxt = self.script.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


class _Client:
    def __init__(self, script: list):
        self.responses = _Responses(script)


@pytest.fixture
def deliverable_dir(tmp_path: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = "alpha"
    workbook.save(tmp_path / "report.xlsx")
    return tmp_path


@pytest.fixture
def task_and_item() -> tuple:
    item = RubricItem(
        rubric_item_id="r1",
        criterion="The deliverable contains an 'alpha' label in column A",
        score=5,
        required=None,
    )
    task = TaskRubric(
        task_id="t1",
        sector="Information",
        occupation="Analyst",
        prompt="Make a report",
        rubric_items=[item],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    return task, item


def _judge(script: list, **kwargs: Any) -> tuple:
    client = _Client(script)
    return ToolCallingJudge(
        client=client,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_TEMPLATE,
        finalization_retries=kwargs.pop("finalization_retries", 1),
        **kwargs,
    ), client


def _run(judge, deliverable_dir, task_and_item):
    task, item = task_and_item
    return judge.judge_item(
        task=task,
        item=item,
        deliverable_dir=str(deliverable_dir),
        file_names=["report.xlsx"],
    )


# ── the three kinds of nothing are told apart ────────────────────────

@pytest.mark.parametrize("incomplete_reason, status, expected, why", [
    (
        "max_output_tokens", "incomplete", "empty_final_text:max_output_tokens",
        "the budget ran out -- a bigger cap would have produced a verdict",
    ),
    (
        "content_filter", "incomplete", "empty_final_text:content_filter",
        "the reply was filtered -- a bigger cap changes nothing here, and "
        "reading this as a budget problem sends the fix in the wrong direction",
    ),
    (
        None, "failed", "empty_final_text:failed",
        "the provider named a status and nothing else; it is still more than "
        "the bare string said",
    ),
])
def test_the_kind_of_silence_is_recorded(
    deliverable_dir, task_and_item, incomplete_reason, status, expected, why
):
    empty = _response(
        status=status, incomplete_reason=incomplete_reason, out_tok=10
    )
    judge, _ = _judge([empty, empty])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.verdict == "judge_error"
    assert result.judge_error == expected, why


def test_a_silence_nothing_explains_still_beats_the_bare_string(
    deliverable_dir, task_and_item
):
    """No status, no incomplete reason, tokens under the cap: ``unknown``.

    Worth its own test because ``unknown`` is the least informative value the
    reason can take, and it is exactly where the temptation to fall back to
    the bare string is strongest. It is still better: the bare string cannot
    distinguish "we asked and nothing explains it" from "we never asked".
    """
    empty = _response(out_tok=10)
    judge, _ = _judge([empty, empty])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.judge_error == "empty_final_text:unknown"


# ── a recovered item must not be filed under the failure it recovered from ──

def test_a_retry_that_answers_clears_the_reason(deliverable_dir, task_and_item):
    """The first attempt ran out of room; the second wrote the envelope.

    The reason is overwritten on every attempt rather than remembered from the
    first, so an item that ended well carries nothing from how it started. If
    it accumulated instead, every successful retry would look like a failure
    in the record -- and retries are the common case, not the rare one.
    """
    empty = _response(status="incomplete", incomplete_reason="max_output_tokens")
    judge, client = _judge([empty, _response(output=[_envelope()], out_tok=40)])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.verdict == "pass"
    assert result.judge_error is None
    assert len(client.responses.calls) == 2


def test_the_attempt_that_is_recorded_is_the_last_one(
    deliverable_dir, task_and_item
):
    """Ran out of room, then got filtered. It is filed under the filter.

    The overwrite matters most when the two attempts fail differently. Keeping
    the first reason instead would tell an operator to raise the output cap --
    which is exactly what the first attempt already did, and it did not help;
    the second attempt failed for a reason no budget can fix.
    """
    judge, _ = _judge([
        _response(status="incomplete", incomplete_reason="max_output_tokens"),
        _response(status="incomplete", incomplete_reason="content_filter",
                  out_tok=10),
    ])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.judge_error == "empty_final_text:content_filter"


# ── a failure that happened earlier is the more specific cause ───────

def test_an_upstream_error_is_not_relabelled_as_silence(
    deliverable_dir, task_and_item
):
    """The call never returned, so there is no reply to call empty.

    ``final_text`` is "" on this path too, which is why the empty-text branch
    catches it -- but "the provider raised" is what happened, and overwriting
    it with a finish reason would describe a response that does not exist.
    """
    judge, _ = _judge([RuntimeError("upstream exploded"), RuntimeError("again")])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.verdict == "judge_error"
    assert not result.judge_error.startswith("empty_final_text")
    assert result.judge_error is not None


def test_a_tool_call_during_finalization_keeps_its_own_name(
    deliverable_dir, task_and_item
):
    """Same rule, a case the harness rather than the provider decides."""
    empty = _response(status="incomplete", incomplete_reason="max_output_tokens")
    calling = _response(output=[{
        "type": "function_call",
        "call_id": "c1",
        "name": "read_deliverable",
        "arguments": json.dumps({"op": "read_content", "path": "report.xlsx"}),
    }])
    judge, _ = _judge([empty, calling])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.judge_error == "unexpected_tool_call_during_finalization"


# ── the label moved; the score did not ───────────────────────────────

def test_an_unanswered_item_is_still_excluded_from_the_score(
    deliverable_dir, task_and_item
):
    """Naming the failure is not the same as deciding what it costs.

    Whether an unanswered item should sit outside the denominator is a live
    question on its own card. This change must not answer it by accident, in
    either direction.
    """
    empty = _response(status="incomplete", incomplete_reason="content_filter")
    judge, _ = _judge([empty, empty])

    result = _run(judge, deliverable_dir, task_and_item)

    assert result.score_excluded is True
    assert result.awarded_score == 0.0
    assert result.partial_score == 0.0


# ── the helper, exercised directly ───────────────────────────────────

def test_an_explicit_error_outranks_the_finish_reason():
    assert tcj._empty_text_reason(
        "max_iterations_exceeded", "empty_final_text:max_output_tokens"
    ) == "max_iterations_exceeded"


def test_a_reason_about_something_else_is_not_filed_under_silence():
    """``final_json_parse_failed`` means the model DID speak, and got the
    shape wrong. Recording it here would put a talkative failure in the bucket
    named for a silent one, and the breakdown that reads these strings would
    report a cause that did not happen.
    """
    assert tcj._empty_text_reason(None, "final_json_parse_failed") == (
        "empty_final_text"
    )
    assert tcj._empty_text_reason(None, "invalid_final_envelope") == (
        "empty_final_text"
    )


def test_no_reason_at_all_falls_back_rather_than_crashes():
    """The visual prepass calls ``_build_result`` before any reason exists."""
    assert tcj._empty_text_reason(None, None) == "empty_final_text"


def test_the_recorded_reason_and_the_retry_trigger_share_one_spelling():
    """These two strings are compared to each other, one indirectly.

    ``_finalization_effort`` holds the retry's reasoning down only when the
    reason is exactly ``_OUT_OF_ROOM_RETRY_REASON``. That value is built from
    the same constant the recorded reason is built from, so the two cannot
    drift apart into a silent no-op where the retry quietly stops being
    cheap.
    """
    assert tcj._OUT_OF_ROOM_RETRY_REASON.startswith(f"{tcj._EMPTY_FINAL_TEXT}:")
    assert tcj._finalization_effort("max", tcj._OUT_OF_ROOM_RETRY_REASON) == "low"
