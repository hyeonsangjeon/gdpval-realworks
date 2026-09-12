"""Every V2 task reported no tool calls and no model calls, in every run.

Not a bad run. A shape mismatch, in both directions, that no run could avoid.

**The tool breakdown.** ``_tool_calls_of`` filtered the public trace for events
with a ``tool_name`` on them. A public event has ``kind``, ``payload`` and the
chain fields, and its payload is exactly ``{"result_commitment", "replayed"}``
-- ``verify_trace_pair`` raises for any other key set. The tool name is two
levels in, on the commitment. So the filter matched nothing a verifier would
admit, and ``tool_calls`` and ``tool_calls_by_name`` were empty for every task
of every run.

**The model-call count.** ``_model_calls_of`` read
``result["agentic_v2"]["model_api_calls"]``. That block is checked against an
*exact* key set by ``verify_agentic_v2_metadata``, and ``model_api_calls`` is
not in it -- so a run that carried the field would be refused as invalid. The
reader was looking for a number the schema forbids, and got 0 every time.

**The tokens.** ``build_agentic_v2_metrics`` accepts ``input_tokens`` and
``output_tokens`` and omits the keys when they are ``None``. The driver never
passed either, so they were absent from every V2 metrics block ever written.

Why this survived review: the driver's own test builds a stand-in result in the
shape the reader was looking for, complete with a top-level ``tool_name`` and a
``model_api_calls`` field. Stand-in and reader agreed with each other and
neither agreed with the runner. So the tests below run the *real* runner against
the *real* fixture backend and read the record it actually produces. One of them
then checks the stand-in against that record, so the two cannot drift apart
again without something going red.

What the fix reads instead: the commitment, for tool names; and the cost
receipt, for the call count and the tokens -- the receipt being the only object
in the system that knows how many calls a task was billed for.

Nothing here calls a model, reaches a network or spends anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend  # noqa: E402
from core.agentic_v2_provenance import (  # noqa: E402
    EVENT_TOOL_PUBLIC,
    verify_agentic_v2_metadata,
    verify_agentic_v2_result,
)
from core.agentic_v2_run_driver import (  # noqa: E402
    _model_calls_of,
    _tokens_of,
    _tool_calls_of,
)
from core.agentic_v2_run_report import build_agentic_v2_metrics  # noqa: E402
from core.agentic_v2_runner import AgenticV2ScriptedRunner  # noqa: E402
from core.agentic_v2_task_journal import TaskStanding  # noqa: E402
from core.cost_receipts import STATUS_COMPLETE  # noqa: E402

PROFILE = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}

WRITE_THEN_FINALIZE = [
    {
        "call_id": "write-1",
        "name": "workspace_apply",
        "arguments": {
            "operation": "write",
            "path": "report.txt",
            "content": "done",
        },
    },
    {
        "call_id": "final-1",
        "name": "finalize",
        "arguments": {"deliverables": ["report.txt"], "summary": "done"},
    },
]


@pytest.fixture
def real_result(tmp_path):
    """A run record the verifier accepts, from the runner that writes them."""
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=list(WRITE_THEN_FINALIZE),
        profile=PROFILE,
    ).run("task", task_id="task-1")
    verify_agentic_v2_result(result)
    return result


def a_receipt(**changes):
    receipt = {
        "status": STATUS_COMPLETE,
        "model_calls": 4,
        "usage": {
            "input_tokens": 17_775,
            "cached_input_tokens": 0,
            "output_tokens": 292,
            "reasoning_tokens": 0,
        },
        "estimated_cost_usd": 0.24249,
        "missing_reasons": [],
    }
    receipt.update(changes)
    return receipt


def a_standing(*, fully_accounted=True):
    """A journal standing, made unaccounted the way a real one becomes so.

    ``cost_is_fully_accounted`` is derived, not stored -- it is false when an
    attempt was opened and never closed. So the unaccounted case here is an
    abandoned attempt rather than a flag, which is the state a run actually
    reaches when a task dies mid-call.
    """
    return TaskStanding(
        task_id="task-1",
        attempts=1 if fully_accounted else 2,
        abandoned_attempts=0 if fully_accounted else 1,
        last_closed=None,
        decision="run",
        reason="",
    )


# ---------------------------------------------------------------------------
# The measurement: what the old filters found in a real record
# ---------------------------------------------------------------------------


def test_the_real_record_has_no_tool_name_where_the_old_filter_looked(real_result):
    """The defect, as a property of a record the verifier accepted."""
    events = real_result["agentic_v2"]["public_trace"]["events"]

    assert events, "the fixture produced no public events at all"
    assert [event for event in events if event.get("tool_name")] == []


def test_the_real_record_has_no_model_api_calls_field(real_result):
    assert "model_api_calls" not in real_result["agentic_v2"]


def test_a_record_carrying_that_field_would_be_refused(real_result):
    """So the old reader could not have been satisfied by any valid run.

    This is the part that makes it a schema mismatch rather than an omission.
    Writing the field the reader wanted is not a fix available to anyone: the
    metadata is compared against an exact key set, and the record stops
    verifying the moment the field is there.
    """
    metadata = dict(real_result["agentic_v2"])
    verify_agentic_v2_metadata(metadata)

    metadata["model_api_calls"] = 2
    with pytest.raises(ValueError, match="metadata is invalid"):
        verify_agentic_v2_metadata(metadata)


# ---------------------------------------------------------------------------
# What the fixed readers find in the same record
# ---------------------------------------------------------------------------


def test_the_tool_calls_are_found_where_the_runner_writes_them(real_result):
    calls = _tool_calls_of(real_result)

    assert [call["tool_name"] for call in calls] == ["workspace_apply", "finalize"]


def test_the_calls_come_from_public_events_and_carry_no_arguments(real_result):
    """The public trace is the one a report may be built from.

    Each returned item is the redacted commitment -- hashes and a verdict, no
    request body. A reader that reached into the private audit for a nicer
    field would be putting unredacted material into a public artefact.
    """
    events = real_result["agentic_v2"]["public_trace"]["events"]
    public = [event for event in events if event.get("kind") == EVENT_TOOL_PUBLIC]

    assert len(public) == len(_tool_calls_of(real_result))
    for call in _tool_calls_of(real_result):
        assert "arguments" not in call
        assert "data" not in call
        assert set(call) == {
            "call_id",
            "tool_name",
            "request_sha256",
            "result_sha256",
            "ok",
            "error_type",
            "usage_delta",
            "state_before_sha256",
            "state_after_sha256",
        }


def test_the_started_event_is_not_counted_as_a_tool_call(real_result):
    """Filtering by kind rather than by "has a name" is the point.

    The chain opens with a ``started`` event and may close with a ``failure``
    one. Neither is a call, and a looser filter that happened to work today
    would count them the first time either grew a name-shaped field.
    """
    events = real_result["agentic_v2"]["public_trace"]["events"]

    assert events[0]["kind"] == "started"
    assert len(_tool_calls_of(real_result)) == len(events) - 1


def test_the_metrics_block_now_names_the_tools_that_ran(real_result):
    metrics = build_agentic_v2_metrics(
        real_result,
        standing=a_standing(),
        tool_calls=_tool_calls_of(real_result),
        model_api_calls=_model_calls_of(a_receipt()),
        task_wall_time_ms=1234.0,
        receipt=a_receipt(),
    )

    assert metrics["tool_calls"] == 2
    assert metrics["tool_calls_by_name"]["workspace_apply"] == 1
    assert metrics["tool_calls_by_name"]["finalize"] == 1
    assert metrics["tool_calls_by_name"]["browser_run"] == 0


# ---------------------------------------------------------------------------
# The count and the tokens, read off the only thing that knows them
# ---------------------------------------------------------------------------


def test_the_model_call_count_comes_from_the_receipt():
    assert _model_calls_of(a_receipt(model_calls=6)) == 6


def test_no_receipt_is_a_floor_and_the_row_says_so(real_result):
    """Zero with no receipt, and two other fields that stop it reading as a fact.

    There is no better answer available -- nothing else in the system counts
    model calls -- so the honest handling is the one the cost fields already
    use: report what is known and mark it as not the whole story.
    """
    assert _model_calls_of(None) == 0

    metrics = build_agentic_v2_metrics(
        real_result,
        standing=a_standing(fully_accounted=False),
        tool_calls=_tool_calls_of(real_result),
        model_api_calls=_model_calls_of(None),
        task_wall_time_ms=1234.0,
        receipt=None,
    )

    assert metrics["model_api_calls"] == 0
    assert metrics["usage_complete"] is False
    assert metrics["agentic_v2_cost_receipt_status"] == "not_run"


def test_a_receipt_with_no_usable_count_is_not_read_as_none_made():
    for broken in (a_receipt(model_calls=None), a_receipt(model_calls=-1)):
        assert _model_calls_of(broken) == 0


def test_the_tokens_come_from_the_receipts_usage():
    assert _tokens_of(a_receipt()) == (17_775, 292)


def test_missing_tokens_stay_missing_rather_than_becoming_zero():
    """``None`` and ``0`` are different claims and only one of them is true.

    No V2 call has ever carried zero input tokens -- the task prompt alone is
    thousands -- so a zero written here would say the model read nothing, which
    is never what happened. The builder omits the key for ``None``.
    """
    assert _tokens_of(None) == (None, None)
    assert _tokens_of({"status": STATUS_COMPLETE}) == (None, None)
    assert _tokens_of(a_receipt(usage={"output_tokens": 292})) == (None, 292)


@pytest.mark.parametrize(
    "receipt, present",
    [
        (a_receipt(), True),
        (None, False),
    ],
)
def test_the_token_keys_are_written_only_when_they_are_known(
    real_result, receipt, present
):
    input_tokens, output_tokens = _tokens_of(receipt)
    metrics = build_agentic_v2_metrics(
        real_result,
        standing=a_standing(fully_accounted=present),
        tool_calls=_tool_calls_of(real_result),
        model_api_calls=_model_calls_of(receipt),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        task_wall_time_ms=1234.0,
        receipt=receipt,
    )

    assert ("input_tokens" in metrics) is present
    assert ("output_tokens" in metrics) is present


# ---------------------------------------------------------------------------
# The stand-in that agreed with the reader instead of with the runner
# ---------------------------------------------------------------------------


def test_the_drivers_stand_in_result_is_shaped_like_a_real_one(real_result):
    """The guard that would have caught this, and now does.

    ``tests/test_agentic_v2_run_driver.py`` fabricates a result rather than
    booting a backend, which is the right trade for what it tests. What made
    the defect invisible is that the fabrication was written from the reader
    rather than from the writer, so reader and stand-in matched and the runner
    matched neither.

    Checked structurally, not by equality: the stand-in has one tool call and
    no chain hashes, and demanding a byte-identical record would mean booting a
    backend in every driver test.
    """
    from tests import test_agentic_v2_run_driver as driver_test

    stand_in = driver_test._success("task-0001")["agentic_v2"]
    real = real_result["agentic_v2"]

    assert "model_api_calls" not in stand_in, (
        "the stand-in carries a field the metadata verifier forbids; a run "
        "record cannot look like this"
    )
    for event in stand_in["public_trace"]["events"]:
        assert event["kind"] == EVENT_TOOL_PUBLIC
        assert set(event["payload"]) == {"result_commitment", "replayed"}
        assert "tool_name" not in event

    real_event = next(
        event
        for event in real["public_trace"]["events"]
        if event["kind"] == EVENT_TOOL_PUBLIC
    )
    stand_in_event = stand_in["public_trace"]["events"][0]
    assert set(stand_in_event["payload"]) == set(real_event["payload"])
