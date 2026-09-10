"""A turn that was refused part-way still ran up a bill, and still said so.

Run ``34500590783`` wrote nine ledger rows and settled two of them. The other
seven — the two refused tasks, their four retries, and the content-filtered
one — carry null tokens, and the reason is one line of the SDK:
``openai_codex._run._collect_turn_result`` accumulates the running
``ThreadTokenUsage`` and the thread items while it walks the stream, then calls
``_raise_for_failed_turn`` *before* it returns. Everything it had collected
leaves with the exception. ``turn_handle.run()`` therefore hands a caller a
result or nothing at all, and a turn that was cut off fifty seconds in — after
several model requests had been served and billed — reaches the ledger looking
exactly like a turn that never started.

So the stream is read on the way past instead of only at the end. Three things
come out of it, and each answers a question that had no answer before:

* the running token usage, which turns "a cost may exist here" into "at least
  this much was spent, and there may be more" — the reservation stays open in
  the second case too, so the receipt is ``partial`` either way;
* how many items completed, which distinguishes a turn refused after forty
  tool calls from one refused after two, and only the first is evidence that
  the limit is reached by what a single turn *spends* rather than by how fast
  turns arrive;
* the ``http_status_code`` the SDK's own error object carries, which is the
  provider's answer rather than our reading of an English sentence.

The fourth thing here is unrelated to the stream and was found while reading
those nine rows: every one of them says ``retry_kind: none``, including the
four that were retries, because ``_reserve_call`` wrote the literal instead of
reading the attribution scope the caller had already opened.

Nothing in this file starts a runtime or reaches any network. The SDK's own
collector is exercised where it is installed and skipped where it is not.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codex_cost import CodexTokenTotals  # noqa: E402
from core.codex_runner import (  # noqa: E402
    CodexAgentRunner,
    TurnObservation,
    _http_status_from_turn_error,
    _load_turn_collector,
    _recording_stream,
    _turn_failure_category,
)
from core.codex_runtime_config import LoopbackCodexProvider  # noqa: E402
from core.cost_metering import CostRecorder  # noqa: E402
from core.cost_receipts import (  # noqa: E402
    RETRY_INFRASTRUCTURE,
    RETRY_INTERNAL_RECOVERY,
    RETRY_NONE,
    RETRY_RESUME,
    RETRY_SEMANTIC,
    STAGE_GENERATION,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    CostReceiptLedger,
)
from core.execution_environment_readiness import (  # noqa: E402
    REQUIRED_RUN_RECORD_FIELDS,
    RETRY_COUNT_UNMAPPED_KEY,
    RETRY_INFRASTRUCTURE_ERROR,
    RETRY_MODEL_SELF_REVIEW,
    RETRY_REASONS,
    RETRY_TOOL_LOOP_INTERNAL_RECOVERY,
    check_run_record_fields,
    retry_counts_by_reason,
)


# ── Stand-ins for the SDK's notification shapes ─────────────────────────────
#
# Built by hand rather than imported, for the same reason `core.codex_cost`
# reads usage by attribute: these tests have to run on a machine where the
# Codex binary cannot start. The field names are the SDK's own and are checked
# against it in `test_the_stand_ins_match_the_sdk`.


@dataclass
class _Breakdown:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_output_tokens: int | None = None


@dataclass
class _ThreadTokenUsage:
    total: _Breakdown
    last: _Breakdown | None = None
    model_context_window: int | None = None


@dataclass
class _Notification:
    method: str
    payload: Any


def _usage_event(**counts: int) -> _Notification:
    return _Notification(
        method="thread/tokenUsage/updated",
        payload=types.SimpleNamespace(
            token_usage=_ThreadTokenUsage(total=_Breakdown(**counts))
        ),
    )


def _item_event() -> _Notification:
    return _Notification(
        method="item/completed", payload=types.SimpleNamespace(item=object())
    )


def _turn_event(turn: Any) -> _Notification:
    return _Notification(
        method="turn/completed", payload=types.SimpleNamespace(turn=turn)
    )


def _error_carrying(variant: str, status: int | None) -> Any:
    """A ``TurnError`` shaped like the one variant that names a status code."""
    detail = types.SimpleNamespace(http_status_code=status)
    info = types.SimpleNamespace(root=types.SimpleNamespace(**{variant: detail}))
    return types.SimpleNamespace(
        message="stream disconnected", codex_error_info=info
    )


def _failed_turn(variant: str = "response_stream_disconnected", status=429) -> Any:
    return types.SimpleNamespace(
        id="turn-1", status="failed", error=_error_carrying(variant, status)
    )


# ── What the stream said ────────────────────────────────────────────────────


def test_the_recording_stream_hands_every_event_on_unchanged():
    """It is a tee, not a filter. A dropped event is a lost deliverable."""
    observed = TurnObservation()
    events = [
        _usage_event(input_tokens=10),
        _item_event(),
        _Notification(method="item/started", payload=None),
        _turn_event(_failed_turn()),
    ]

    seen = list(_recording_stream(iter(events), observed))

    assert seen == events


def test_the_stream_reports_the_last_usage_the_items_and_the_turn():
    observed = TurnObservation()

    list(
        _recording_stream(
            iter(
                [
                    _usage_event(input_tokens=10, output_tokens=1),
                    _item_event(),
                    _usage_event(input_tokens=53_647, output_tokens=2_110),
                    _item_event(),
                    _item_event(),
                    _turn_event(_failed_turn()),
                ]
            ),
            observed,
        )
    )

    # Cumulative, so the last one is the answer, not the sum of them.
    assert observed.usage.total.input_tokens == 53_647
    assert observed.usage.total.output_tokens == 2_110
    assert observed.items_seen == 3
    assert observed.turn is not None
    assert observed.http_status_code == 429


def test_a_turn_that_reported_nothing_observes_nothing():
    """Silence reads as unknown, never as zero."""
    observed = TurnObservation()

    list(_recording_stream(iter([_Notification("item/started", None)]), observed))

    assert observed.usage is None
    assert observed.items_seen == 0
    assert observed.turn is None
    assert observed.http_status_code is None


# ── What the provider answered with ─────────────────────────────────────────


@pytest.mark.parametrize(
    "variant",
    [
        "response_stream_disconnected",
        "response_stream_connection_failed",
        "response_too_many_failed_attempts",
    ],
)
def test_each_error_variant_that_names_a_status_is_read(variant: str):
    assert _http_status_from_turn_error(_error_carrying(variant, 429)) == 429


def test_an_error_with_no_status_code_reports_none():
    """Absent, unknown-shaped and status-less all read the same: no answer."""
    assert _http_status_from_turn_error(None) is None
    assert _http_status_from_turn_error(types.SimpleNamespace()) is None
    assert (
        _http_status_from_turn_error(_error_carrying("some_new_variant", 429))
        is None
    )
    assert (
        _http_status_from_turn_error(
            _error_carrying("response_stream_disconnected", None)
        )
        is None
    )


def test_a_status_code_of_429_settles_the_category_whatever_the_prose_says():
    """The field beats the sentence.

    Reading a bare ``429`` out of prose is the mistake
    ``core.execution_errors`` is careful not to make — a traceback names line
    numbers — but a status code *field* holding 429 means one thing only, and
    it does not depend on the wording surviving a runtime version or a change
    of region.
    """
    assert (
        _turn_failure_category("anything at all", http_status_code=429)
        == "rate_limited"
    )


def test_another_status_code_does_not_become_a_rate_limit():
    assert (
        _turn_failure_category("the gateway gave up", http_status_code=500)
        == "turn_failed"
    )


def test_without_a_status_code_the_text_is_still_read():
    """The old path is intact; it is now the second question, not the only one."""
    assert _turn_failure_category("HTTP 429 Too Many Requests") == "rate_limited"
    assert _turn_failure_category("a plain failure") == "turn_failed"


# ── The bill a refused turn leaves behind ───────────────────────────────────


class _FakeTurnHandle:
    """A turn whose stream ends the way run ``34500590783``'s two did."""

    id = "turn-1"

    def __init__(self, events: list[_Notification], *, failure: str | None):
        self._events = events
        self._failure = failure
        self.closed = False

    def stream(self) -> Any:
        handle = self

        class _Stream:
            def __iter__(self):
                yield from handle._events
                if handle._failure is not None:
                    raise RuntimeError(handle._failure)

            def close(self):
                handle.closed = True

        return _Stream()

    def run(self) -> Any:  # pragma: no cover - only the no-collector path
        for _ in self.stream():
            pass
        return types.SimpleNamespace(id=self.id, usage=None, final_response="")


class _FakeThread:
    id = "thread-1"

    def __init__(self, handle: _FakeTurnHandle):
        self._handle = handle

    def turn(self, _text: str) -> _FakeTurnHandle:
        return self._handle


def _runner_over(handle: _FakeTurnHandle, ledger: CostReceiptLedger):
    runner = CodexAgentRunner(
        LoopbackCodexProvider(port=1),
        timeout=30,
        cost_ledger=ledger,
        run_id="refused-turn",
        condition_name="condition_a",
        verify_runtime=False,
        preflight_auth=False,
    )
    runner.open_runtime = lambda _workspace: types.SimpleNamespace(  # type: ignore[method-assign]
        close=lambda: None
    )
    runner.start_thread = (  # type: ignore[method-assign]
        lambda _codex, _workspace, **_kwargs: _FakeThread(handle)
    )
    return runner


@pytest.fixture
def ledger(tmp_path: Path):
    with CostReceiptLedger(
        tmp_path / "receipts.sqlite3", run_id="refused-turn"
    ) as opened:
        yield opened


def _run_the_task(runner: CodexAgentRunner, task_id: str = "task-1") -> dict:
    return runner.run("do the work", task_id=task_id)


def test_a_refused_turn_settles_for_the_tokens_the_stream_reported(
    ledger: CostReceiptLedger,
):
    """The change this file is named for.

    Before, this row read ``reserved`` with five nulls. The turn had spent
    53,647 input and 2,110 output tokens and the stream had said so twice.
    """
    if _load_turn_collector() is None:  # pragma: no cover - SDK absent
        pytest.skip("the pinned Codex SDK is not installed here")

    handle = _FakeTurnHandle(
        [
            _usage_event(input_tokens=53_647, output_tokens=2_110),
            _item_event(),
            _item_event(),
            _turn_event(_failed_turn()),
        ],
        failure="stream disconnected before completion",
    )
    result = _run_the_task(_runner_over(handle, ledger))

    assert result["success"] is False
    assert result["error_category"] == "rate_limited"

    (row,) = ledger.calls_for("task-1")
    assert row["state"] == "settled"
    assert row["input_tokens"] == 53_647
    assert row["output_tokens"] == 2_110
    # Settled, and still honest about not being the whole bill: the turn's
    # individual model requests were never enumerable.
    assert "call_reachability_unknown" in row["missing_reasons"]
    assert handle.closed is True


def test_a_refused_turn_that_reported_no_usage_leaves_the_reservation_open(
    ledger: CostReceiptLedger,
):
    """No measurement is not a measurement of zero.

    An open reservation is what turns the task's receipt ``partial``. Settling
    it at zero would read as a free turn.
    """
    if _load_turn_collector() is None:  # pragma: no cover - SDK absent
        pytest.skip("the pinned Codex SDK is not installed here")

    handle = _FakeTurnHandle(
        [_turn_event(_failed_turn())], failure="refused before any usage arrived"
    )
    _run_the_task(_runner_over(handle, ledger))

    (row,) = ledger.calls_for("task-1")
    assert row["state"] == "reserved"
    assert row["input_tokens"] is None
    assert row["output_tokens"] is None


def test_the_run_record_carries_how_far_the_turn_got_and_what_refused_it(
    ledger: CostReceiptLedger,
):
    if _load_turn_collector() is None:  # pragma: no cover - SDK absent
        pytest.skip("the pinned Codex SDK is not installed here")

    handle = _FakeTurnHandle(
        [
            _item_event(),
            _item_event(),
            _item_event(),
            _usage_event(input_tokens=101, output_tokens=7),
            _turn_event(_failed_turn()),
        ],
        failure="stream disconnected before completion",
    )
    runner = _runner_over(handle, ledger)
    _run_the_task(runner)

    diagnostics = runner.last_run_diagnostics
    assert diagnostics is not None
    assert diagnostics["items_seen"] == 3
    assert diagnostics["http_status_code"] == 429
    assert diagnostics["usage_delta"]["input_tokens"] == 101
    assert diagnostics["usage_delta"]["output_tokens"] == 7


def test_the_collector_borrowed_from_the_sdk_is_the_sdk_s_own():
    """Borrowed, not reimplemented.

    ``_collect_turn_result`` decides which agent message is the final answer,
    and that answer is the deliverable text step 4 fills into the parquet. A
    local copy of that rule is a way to lose a deliverable to a version bump.
    """
    collector = _load_turn_collector()
    if collector is None:  # pragma: no cover - SDK absent
        pytest.skip("the pinned Codex SDK is not installed here")
    assert collector.__module__ == "openai_codex._run"
    assert collector.__name__ == "_collect_turn_result"


def test_the_stand_ins_match_the_sdk():
    """The hand-built notifications above name the SDK's own fields."""
    try:
        from openai_codex.generated.v2_all import ThreadTokenUsage
    except Exception:  # pragma: no cover - SDK absent
        pytest.skip("the pinned Codex SDK is not installed here")

    assert set(ThreadTokenUsage.model_fields) == {
        "last",
        "total",
        "model_context_window",
    }


# ── Which attempt the row belongs to ────────────────────────────────────────


def test_a_reserved_call_takes_the_retry_kind_from_the_open_scope(
    ledger: CostReceiptLedger,
):
    """Defect ⑤. All nine rows of run ``34500590783`` said ``none``.

    Four of them were infrastructure retries. ``_reserve_call`` wrote the
    literal ``RETRY_NONE`` rather than reading the attribution scope
    ``step2_run_inference`` opens immediately around the call, on this thread —
    so the retry accounting the run was supposed to produce was flat.
    """
    runner = CodexAgentRunner(
        LoopbackCodexProvider(port=1),
        cost_ledger=ledger,
        run_id="refused-turn",
        verify_runtime=False,
        preflight_auth=False,
    )
    recorder = CostRecorder(ledger, run_id="refused-turn")

    with recorder.attributed(
        task_id="task-1", stage=STAGE_GENERATION, retry_kind=RETRY_INFRASTRUCTURE
    ):
        runner._reserve_call("task-1")

    (row,) = ledger.calls_for("task-1")
    assert row["retry_kind"] == RETRY_INFRASTRUCTURE


def test_with_no_scope_open_a_reserved_call_is_a_first_attempt(
    ledger: CostReceiptLedger,
):
    """The old behaviour, kept for the callers that genuinely have no scope."""
    runner = CodexAgentRunner(
        LoopbackCodexProvider(port=1),
        cost_ledger=ledger,
        run_id="refused-turn",
        verify_runtime=False,
        preflight_auth=False,
    )

    runner._reserve_call("task-1")

    (row,) = ledger.calls_for("task-1")
    assert row["retry_kind"] == RETRY_NONE


def test_two_attempts_at_one_task_open_two_rows(ledger: CostReceiptLedger):
    """A retry must open a second receipt, not settle onto the first one's."""
    runner = CodexAgentRunner(
        LoopbackCodexProvider(port=1),
        cost_ledger=ledger,
        run_id="refused-turn",
        verify_runtime=False,
        preflight_auth=False,
    )
    recorder = CostRecorder(ledger, run_id="refused-turn")

    first = runner._reserve_call("task-1")
    with recorder.attributed(
        task_id="task-1", stage=STAGE_GENERATION, retry_kind=RETRY_INFRASTRUCTURE
    ):
        second = runner._reserve_call("task-1")

    assert first != second
    kinds = [row["retry_kind"] for row in ledger.calls_for("task-1")]
    assert sorted(kinds) == sorted([RETRY_NONE, RETRY_INFRASTRUCTURE])


# ── The reading itself ──────────────────────────────────────────────────────


def test_an_empty_measurement_is_not_settled():
    """``turn_usage_delta`` of nothing is empty, and empty is left alone."""
    assert CodexTokenTotals().is_empty is True
    assert CodexTokenTotals(input_tokens=0).is_empty is False


# ── Counting those attempts back out again ─────────────────────────────────


def _call(retry_kind: str, *, stage: str = STAGE_GENERATION) -> dict:
    return {"record_type": "call", "stage": stage, "retry_kind": retry_kind}


def test_each_ledger_kind_reaches_the_reason_it_means():
    counts = retry_counts_by_reason(
        [
            _call(RETRY_INFRASTRUCTURE),
            _call(RETRY_INFRASTRUCTURE),
            _call(RETRY_SEMANTIC),
            _call(RETRY_INTERNAL_RECOVERY),
        ]
    )

    assert counts[RETRY_INFRASTRUCTURE_ERROR] == 2
    assert counts[RETRY_MODEL_SELF_REVIEW] == 1
    assert counts[RETRY_TOOL_LOOP_INTERNAL_RECOVERY] == 1
    assert counts[RETRY_COUNT_UNMAPPED_KEY] == {}


def test_a_first_attempt_is_not_a_retry():
    counts = retry_counts_by_reason([_call(RETRY_NONE), _call(RETRY_NONE)])

    assert all(counts[reason] == 0 for reason in RETRY_REASONS)
    assert counts[RETRY_COUNT_UNMAPPED_KEY] == {}


def test_a_resumed_attempt_is_reported_rather_than_filed_under_the_nearest_reason():
    """The honest gap.

    A resumed round does re-attempt a task, but none of the three reasons says
    why: the model did not review itself, no tool loop corrected course, and
    the request did not fail to get through — the previous *process* stopped.
    ``infrastructure_error`` is the closest of three wrong answers, and folding
    it in there would inflate the single count this run exists to measure.
    """
    counts = retry_counts_by_reason([_call(RETRY_RESUME), _call(RETRY_RESUME)])

    assert counts[RETRY_INFRASTRUCTURE_ERROR] == 0
    assert counts[RETRY_COUNT_UNMAPPED_KEY] == {RETRY_RESUME: 2}


def test_grading_retries_stay_out_of_the_solving_run_s_record():
    counts = retry_counts_by_reason(
        [
            _call(RETRY_INFRASTRUCTURE, stage=STAGE_GENERATION),
            _call(RETRY_INFRASTRUCTURE, stage=STAGE_GRADING),
            _call(RETRY_INFRASTRUCTURE, stage=STAGE_PERCEPTION),
        ]
    )

    assert counts[RETRY_INFRASTRUCTURE_ERROR] == 1


def test_a_runtime_fee_is_not_a_call_and_is_not_counted():
    counts = retry_counts_by_reason(
        [{"record_type": "runtime", "retry_kind": RETRY_INFRASTRUCTURE}]
    )

    assert counts[RETRY_INFRASTRUCTURE_ERROR] == 0
    assert counts[RETRY_COUNT_UNMAPPED_KEY] == {}


def test_a_row_that_cannot_be_classified_is_said_to_be_unclassifiable():
    counts = retry_counts_by_reason(
        [
            {"record_type": "call", "stage": STAGE_GENERATION},
            {"record_type": "call", "stage": STAGE_GENERATION, "retry_kind": ""},
        ]
    )

    assert counts[RETRY_COUNT_UNMAPPED_KEY] == {"unreadable": 2}


def test_the_nine_rows_of_run_34500590783_count_no_retries_at_all():
    """The witness for defect ⑤, kept as the shape it actually had.

    Four of these nine were infrastructure retries. Every row says ``none``,
    so the count the run would have published is zero — which is why the fix
    is in ``_reserve_call`` and not in the counting.
    """
    counts = retry_counts_by_reason([_call(RETRY_NONE) for _ in range(9)])

    assert counts[RETRY_INFRASTRUCTURE_ERROR] == 0


def test_the_counts_satisfy_the_field_the_run_record_requires():
    """The round trip. The producer's output is what the checker asks for."""
    record = {name: "recorded" for name in REQUIRED_RUN_RECORD_FIELDS}
    record["retry_counts_by_reason"] = retry_counts_by_reason(
        [_call(RETRY_INFRASTRUCTURE), _call(RETRY_RESUME)]
    )

    assert check_run_record_fields(record) == []
