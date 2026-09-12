"""Whether the loop finishes a manifest, resumes one, and stops when it must.

The runner is a stand-in, but everything it feeds is real: the real journal
writing a real file, the real collector writing real bytes, the real report
adapter. What is faked is the one thing that is still blocked — the model. So a
test that says "resumed and did not re-run the finished task" is a statement
about the code that will run the 220, not about a mock of it.
"""

from __future__ import annotations

import json

import pytest

from core.agentic_v2_deliverable_collection import DELIVERABLE_ROOT
from core.agentic_v2_preregistration import STOP_RULES
from core.agentic_v2_run_driver import (
    CONSECUTIVE_RUNNER_DEFECTS_THAT_STOP_A_RUN,
    RULES_A_CALLER_CAN_HAND_THIS_DRIVER,
    RULES_THIS_DRIVER_CANNOT_SEE,
    RULES_THIS_DRIVER_WATCHES,
    DriverRefused,
    StoppedEarly,
    TaskToRun,
    run_manifest,
)
from core.cost_receipts import STATUS_COMPLETE, STATUS_NOT_RUN, STATUS_PARTIAL


def _tasks(count=3):
    return [
        TaskToRun(
            task_id=f"task-{index:04d}",
            prompt=f"do thing {index}",
            occupation="Analyst",
            sector="Finance",
        )
        for index in range(1, count + 1)
    ]


def _success(task_id, *, calls=("exec_run", "finalize")):
    """A result shaped the way the runner shapes one, minus the hashes.

    The nesting is not decoration. A public event's payload is checked against
    an exact key set, and the tool name lives on the commitment inside it, two
    levels down -- so a stand-in with the name on the event is a shape no run
    can produce and no verifier would admit. It was, for a while, and the
    driver read the trace the same wrong way, which is how V2 came to report
    zero tool calls for every task of every run without a test going red.

    ``model_api_calls`` is not here for the same reason: the metadata is
    compared against an exact key set that does not include it. The count comes
    from the cost receipt, which is the only object that knows it.

    Kept honest by
    ``test_the_metrics_block_that_always_read_zero.py::test_the_drivers_stand_in_result_is_shaped_like_a_real_one``,
    which boots the real fixture backend and compares this shape against the
    record it writes.
    """
    return {
        "success": True,
        "deliverable_text": f"answer for {task_id}",
        "files": [{"filename": "report.xlsx", "content": b"payload"}],
        "agentic_v2": {
            "public_trace": {
                "events": [
                    {
                        "kind": "tool_result_public",
                        "payload": {
                            "result_commitment": {"tool_name": name},
                            "replayed": False,
                        },
                    }
                    for name in calls
                ]
            },
        },
    }


def _failure(error):
    return {"success": False, "error": error, "files": []}


class _Runner:
    """A runner that answers from a script, and records that it was closed."""

    def __init__(self, script, closed):
        self.script = script
        self.closed = closed

    def run(self, prompt, reference_files, occupation, **kwargs):
        task_id = kwargs["task_id"]
        answer = self.script(task_id)
        return answer

    def close(self):
        self.closed.append(id(self))


def _factory(script, closed=None):
    made = []
    closed = [] if closed is None else closed

    def build(task):
        runner = _Runner(script, closed)
        made.append(runner)
        return runner

    build.made = made  # type: ignore[attr-defined]
    build.closed = closed  # type: ignore[attr-defined]
    return build


def _run(tmp_path, tasks, script, **kwargs):
    factory = kwargs.pop("factory", None) or _factory(script)
    return (
        run_manifest(
            tasks,
            run_id=kwargs.pop("run_id", "run-a"),
            runner_factory=factory,
            journal_path=tmp_path / "journal.jsonl",
            collect_into=tmp_path,
            **kwargs,
        ),
        factory,
    )


# ── the stop rules this driver claims ────────────────────────────────────


def test_every_stop_rule_is_either_watched_or_accounted_for():
    watched = set(RULES_THIS_DRIVER_WATCHES)
    handed = set(RULES_A_CALLER_CAN_HAND_THIS_DRIVER)
    unseen = set(RULES_THIS_DRIVER_CANNOT_SEE)
    assert watched & unseen == set()
    assert watched & handed == set()
    assert handed & unseen == set()
    assert watched | handed | unseen == set(range(len(STOP_RULES)))


def test_the_driver_watches_only_two_of_the_eight_on_its_own():
    """Claiming all eight would be the easy and wrong thing to do."""
    assert len(RULES_THIS_DRIVER_WATCHES) == 2
    assert len(STOP_RULES) == 8


def test_the_rule_a_caller_can_hand_it_is_not_counted_as_watched():
    """A seam that a caller may decline to use is not the same as enforcement.

    Rule 0 moved out of "cannot see" when ``stop_when`` was added, and the
    temptation at that moment is to move it into "watches" — which would read
    as three rules enforced whatever the caller does. It is one rule enforced
    when the caller wires it, and the two dicts keep those apart.

    Rule 1 stays where it was. It is the neighbouring claim — a run switching
    model on its own — and the voice really does hold that one, raising when
    two replies in one conversation name two different models. Rule 0 is the
    comparison against the pinned name, which nothing held.
    """
    assert set(RULES_A_CALLER_CAN_HAND_THIS_DRIVER) == {0}
    assert 0 not in RULES_THIS_DRIVER_WATCHES
    assert 0 not in RULES_THIS_DRIVER_CANNOT_SEE
    assert 1 in RULES_THIS_DRIVER_CANNOT_SEE


# ── the ordinary run ─────────────────────────────────────────────────────


def test_a_whole_manifest_runs_and_every_task_gets_a_row(tmp_path):
    outcome, _ = _run(tmp_path, _tasks(3), _success)
    assert [row["task_id"] for row in outcome.rows] == [
        "task-0001",
        "task-0002",
        "task-0003",
    ]
    assert outcome.summary["executed"] == 3
    assert outcome.summary["succeeded"] == 3
    assert outcome.summary["not_reached"] == 0
    assert outcome.stopped is None


def test_each_task_gets_its_own_runner_and_all_are_closed(tmp_path):
    outcome, factory = _run(tmp_path, _tasks(3), _success)
    assert len(factory.made) == 3
    assert len(set(id(runner) for runner in factory.made)) == 3
    assert len(factory.closed) == 3


def test_a_runner_is_closed_even_when_it_raises(tmp_path):
    def explode(task_id):
        raise RuntimeError("the runner fell over")

    factory = _factory(explode)
    with pytest.raises(RuntimeError, match="fell over"):
        run_manifest(
            _tasks(1),
            run_id="run-a",
            runner_factory=factory,
            journal_path=tmp_path / "journal.jsonl",
            collect_into=tmp_path,
        )
    assert len(factory.closed) == 1


def test_the_files_reach_the_submission_layout(tmp_path):
    outcome, _ = _run(tmp_path, _tasks(1), _success)
    landed = tmp_path / DELIVERABLE_ROOT / "task-0001" / "report.xlsx"
    assert landed.read_bytes() == b"payload"
    assert outcome.rows[0]["deliverable_files"] == [
        f"{DELIVERABLE_ROOT}/task-0001/report.xlsx"
    ]


def test_v2_tool_calls_are_counted_from_the_public_trace(tmp_path):
    def receipt_for(task, attempt):
        return {"status": STATUS_COMPLETE, "model_calls": 2}

    outcome, _ = _run(tmp_path, _tasks(1), _success, receipt_for=receipt_for)
    metrics = outcome.rows[0]["observability"]["agentic_metrics"]
    assert metrics["tool_calls"] == 2
    assert metrics["tool_calls_by_name"]["exec_run"] == 1
    # From the receipt, not the result: the metadata verifier rejects a record
    # that carries a call count, so the result cannot be asked for one.
    assert metrics["model_api_calls"] == 2


def test_wall_time_is_measured_per_task(tmp_path):
    ticks = iter([0.0, 1.5, 10.0, 12.0])
    outcome, _ = _run(tmp_path, _tasks(2), _success, clock=lambda: next(ticks))
    metrics = [
        row["observability"]["agentic_metrics"]["task_wall_time_ms"]
        for row in outcome.rows
    ]
    assert metrics == [1500.0, 2000.0]


# ── money ────────────────────────────────────────────────────────────────


def test_a_run_with_no_ledger_is_not_run_rather_than_free(tmp_path):
    outcome, _ = _run(tmp_path, _tasks(1), _success)
    metrics = outcome.rows[0]["observability"]["agentic_metrics"]
    assert metrics["agentic_v2_cost_receipt_status"] == STATUS_NOT_RUN
    assert "conservative_cost_usd" not in metrics
    assert outcome.summary["cost_is_fully_accounted"] is False


def test_a_complete_receipt_reaches_the_row_and_the_summary(tmp_path):
    def receipt_for(task, attempt):
        return {
            "status": STATUS_COMPLETE,
            "estimated_cost_usd": 0.5,
            "known_cost_usd": 0.5,
        }

    outcome, _ = _run(tmp_path, _tasks(2), _success, receipt_for=receipt_for)
    for row in outcome.rows:
        metrics = row["observability"]["agentic_metrics"]
        assert metrics["conservative_cost_usd"] == 0.5
        assert row["problem_solving_cost"]["status"] == STATUS_COMPLETE
    assert outcome.summary["cost_is_fully_accounted"] is True


def test_the_attempt_index_reaches_the_pricing_callback(tmp_path):
    seen = []

    def receipt_for(task, attempt):
        seen.append((task.task_id, attempt))
        return None

    attempts = {"n": 0}

    def flaky(task_id):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _failure("compute_start_failed")
        return _success(task_id)

    _run(tmp_path, _tasks(1), flaky, receipt_for=receipt_for)
    assert seen == [("task-0001", 1), ("task-0001", 2)]


# ── retries ──────────────────────────────────────────────────────────────


def test_an_infrastructure_failure_is_retried_and_can_succeed(tmp_path):
    attempts = {"n": 0}

    def flaky(task_id):
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _failure("compute_start_failed")
        return _success(task_id)

    outcome, factory = _run(tmp_path, _tasks(1), flaky)
    assert len(outcome.rows) == 1
    assert outcome.rows[0]["status"] == "success"
    assert outcome.rows[0]["retried"] is True
    assert len(factory.made) == 2


def test_only_the_last_attempt_becomes_the_row(tmp_path):
    attempts = {"n": 0}

    def flaky(task_id):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return _failure("compute_start_failed")
        return _success(task_id)

    outcome, _ = _run(tmp_path, _tasks(1), flaky)
    assert len(outcome.rows) == 1
    assert outcome.rows[0]["status"] == "success"


def test_a_task_that_never_recovers_stops_at_the_attempt_ceiling(tmp_path):
    outcome, factory = _run(
        tmp_path, _tasks(1), lambda task_id: _failure("compute_start_failed")
    )
    assert len(factory.made) == 3
    assert outcome.rows[0]["status"] == "error"
    assert outcome.rows[0]["error"] == "compute_start_failed"


def test_a_terminal_failure_is_not_retried(tmp_path):
    outcome, factory = _run(
        tmp_path, _tasks(1), lambda task_id: _failure("capability_unavailable")
    )
    assert len(factory.made) == 1
    assert outcome.rows[0]["status"] == "error"
    assert (
        outcome.rows[0]["observability"]["agentic_metrics"]["agentic_v2_disposition"]
        == "terminal_capability_absent"
    )


def test_a_capability_absence_does_not_stop_the_run(tmp_path):
    """The pre-registration records this as a result, not a fault."""
    script = lambda task_id: (  # noqa: E731
        _failure("capability_unavailable")
        if task_id == "task-0002"
        else _success(task_id)
    )
    outcome, _ = _run(tmp_path, _tasks(3), script)
    assert outcome.stopped is None
    assert len(outcome.rows) == 3
    assert outcome.summary["failed"] == 1


# ── stopping ─────────────────────────────────────────────────────────────


def test_three_runner_defects_running_stop_the_run(tmp_path):
    outcome, _ = _run(
        tmp_path, _tasks(5), lambda task_id: _failure("invalid_backend_state")
    )
    assert outcome.stopped is not None
    assert outcome.stopped.rule_index == 6
    assert outcome.stopped.rule == STOP_RULES[6]
    assert len(outcome.rows) == CONSECUTIVE_RUNNER_DEFECTS_THAT_STOP_A_RUN
    assert outcome.summary["not_reached"] == 2


def test_a_good_task_between_defects_resets_the_count(tmp_path):
    """Two defects, a good task, two more defects: four in the run, no stop."""
    script = lambda task_id: (  # noqa: E731
        _success(task_id)
        if task_id == "task-0003"
        else _failure("invalid_backend_state")
    )
    outcome, _ = _run(tmp_path, _tasks(5), script)
    assert outcome.stopped is None
    assert len(outcome.rows) == 5
    assert outcome.summary["failed"] == 4


def test_the_reset_only_delays_a_run_that_keeps_failing(tmp_path):
    """Same script, one task longer, and the tail of three lands."""
    script = lambda task_id: (  # noqa: E731
        _success(task_id)
        if task_id == "task-0003"
        else _failure("invalid_backend_state")
    )
    outcome, _ = _run(tmp_path, _tasks(6), script)
    assert outcome.stopped is not None
    assert outcome.stopped.rule_index == 6
    assert outcome.stopped.after_task == "task-0006"


def test_a_semantic_failure_also_resets_the_count(tmp_path):
    """The rule counts this code misbehaving, not tasks going badly."""
    script = lambda task_id: (  # noqa: E731
        _failure("finalize_not_called")
        if task_id == "task-0003"
        else _failure("invalid_backend_state")
    )
    outcome, _ = _run(tmp_path, _tasks(5), script)
    assert outcome.stopped is None
    assert len(outcome.rows) == 5


def test_a_failed_cleanup_stops_the_run_immediately(tmp_path):
    script = lambda task_id: (  # noqa: E731
        _failure("compute_cleanup_failed")
        if task_id == "task-0002"
        else _success(task_id)
    )
    outcome, _ = _run(tmp_path, _tasks(4), script)
    assert outcome.stopped is not None
    assert outcome.stopped.rule_index == 7
    assert outcome.stopped.after_task == "task-0002"
    assert len(outcome.rows) == 2
    assert outcome.summary["not_reached"] == 2


def test_a_stopped_run_says_so_in_its_summary(tmp_path):
    outcome, _ = _run(
        tmp_path, _tasks(4), lambda task_id: _failure("invalid_backend_state")
    )
    assert outcome.summary["stopped_early"]["rule_index"] == 6
    assert outcome.as_dict()["stopped_early"]["after_task"] == "task-0003"


# ── collection failures ──────────────────────────────────────────────────


def test_a_deliverable_the_collector_refuses_fails_the_task(tmp_path):
    def bad_path(task_id):
        answer = _success(task_id)
        answer["files"] = [{"filename": "../escape.txt", "content": b"x"}]
        return answer

    outcome, _ = _run(tmp_path, _tasks(1), bad_path)
    assert outcome.rows[0]["status"] == "error"
    assert outcome.rows[0]["error"] == "invalid_backend_result"
    assert outcome.rows[0]["deliverable_files"] == []
    assert not (tmp_path / DELIVERABLE_ROOT / "task-0001").exists()


def test_three_collection_failures_running_stop_the_run(tmp_path):
    """Because the contract and the collector disagreeing is this code's fault."""

    def bad_path(task_id):
        answer = _success(task_id)
        answer["files"] = [{"filename": "../escape.txt", "content": b"x"}]
        return answer

    outcome, _ = _run(tmp_path, _tasks(6), bad_path)
    assert outcome.stopped is not None
    assert outcome.stopped.rule_index == 6
    assert len(outcome.rows) == 3


# ── resume ───────────────────────────────────────────────────────────────


def test_a_second_run_skips_what_the_first_finished(tmp_path):
    tasks = _tasks(3)
    script = lambda task_id: (  # noqa: E731
        _failure("invalid_backend_state")
        if task_id == "task-0003"
        else _success(task_id)
    )
    first, _ = _run(tmp_path, tasks, script)
    assert len(first.rows) == 3

    second, factory = _run(tmp_path, tasks, _success)
    assert second.skipped_on_resume == ("task-0001", "task-0002", "task-0003")
    assert factory.made == []
    assert second.rows == []


def test_a_resumed_run_finishes_what_was_left(tmp_path):
    tasks = _tasks(3)
    attempts = {"n": 0}

    def two_then_stop(task_id):
        attempts["n"] += 1
        if attempts["n"] > 2:
            raise KeyboardInterrupt
        return _success(task_id)

    with pytest.raises(KeyboardInterrupt):
        _run(tmp_path, tasks, two_then_stop)

    second, factory = _run(tmp_path, tasks, _success)
    assert second.skipped_on_resume == ("task-0001", "task-0002")
    assert [row["task_id"] for row in second.rows] == ["task-0003"]
    assert len(factory.made) == 1


def test_an_interrupted_task_keeps_the_run_s_cost_partial_forever(tmp_path):
    """The attempt that vanished was charged and nobody can price it."""
    tasks = _tasks(2)

    def receipt_for(task, attempt):
        return {
            "status": STATUS_COMPLETE,
            "estimated_cost_usd": 1.0,
            "known_cost_usd": 1.0,
        }

    def die_on_the_second(task_id):
        if task_id == "task-0002":
            raise KeyboardInterrupt
        return _success(task_id)

    with pytest.raises(KeyboardInterrupt):
        _run(tmp_path, tasks, die_on_the_second, receipt_for=receipt_for)

    second, _ = _run(tmp_path, tasks, _success, receipt_for=receipt_for)
    # task-0001 was settled in the first run and is skipped here, so the only
    # task left unpriced is the one whose first attempt disappeared.
    assert second.skipped_on_resume == ("task-0001",)
    assert second.summary["receipt_ceiling"] == STATUS_PARTIAL
    assert second.summary["cost_is_fully_accounted"] is False
    assert second.summary["unaccounted_tasks"] == ["task-0002"]
    metrics = second.rows[0]["observability"]["agentic_metrics"]
    assert "conservative_cost_usd" not in metrics
    assert metrics["agentic_v2_abandoned_attempts"] == 1


def test_a_run_with_no_ledger_leaves_every_task_unaccounted(tmp_path):
    """Not pricing at all is a partial run, not a cheap one."""
    outcome, _ = _run(tmp_path, _tasks(2), _success)
    assert outcome.summary["unaccounted_tasks"] == ["task-0001", "task-0002"]
    assert outcome.summary["cost_is_fully_accounted"] is False


def test_the_journal_on_disk_survives_the_run(tmp_path):
    _run(tmp_path, _tasks(2), _success)
    lines = (tmp_path / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    kinds = [json.loads(line)["kind"] for line in lines]
    assert kinds == ["header", "opened", "closed", "opened", "closed"]


# ── refusals ─────────────────────────────────────────────────────────────


def test_an_empty_manifest_is_refused(tmp_path):
    with pytest.raises(DriverRefused, match="is not one"):
        run_manifest(
            [],
            run_id="run-a",
            runner_factory=_factory(_success),
            journal_path=tmp_path / "journal.jsonl",
            collect_into=tmp_path,
        )


def test_a_repeated_task_in_the_manifest_is_refused(tmp_path):
    tasks = _tasks(1) * 2
    with pytest.raises(DriverRefused, match="appears twice"):
        run_manifest(
            tasks,
            run_id="run-a",
            runner_factory=_factory(_success),
            journal_path=tmp_path / "journal.jsonl",
            collect_into=tmp_path,
        )


def test_a_runner_that_returns_something_else_is_refused(tmp_path):
    with pytest.raises(DriverRefused, match="not a result envelope"):
        _run(tmp_path, _tasks(1), lambda task_id: "finished, probably")


def test_the_callback_sees_each_row_as_it_lands(tmp_path):
    seen = []
    _run(tmp_path, _tasks(3), _success, on_task=lambda tid, row: seen.append(tid))
    assert seen == ["task-0001", "task-0002", "task-0003"]


# ── the rule a caller hands it ───────────────────────────────────────────


def test_a_caller_can_stop_the_run_after_a_named_task(tmp_path):
    outcome, _ = _run(
        tmp_path,
        _tasks(4),
        _success,
        stop_when=lambda task_id: (
            StoppedEarly(
                rule_index=0,
                rule=STOP_RULES[0],
                detail="a reply named a model the plan did not pin",
                after_task=task_id,
            )
            if task_id == "task-0002"
            else None
        ),
    )
    assert outcome.stopped is not None
    assert outcome.stopped.rule_index == 0
    assert outcome.stopped.after_task == "task-0002"
    assert outcome.summary["stopped_early"] is not None


def test_the_task_that_tripped_it_is_still_in_the_record(tmp_path):
    """The halt must not swallow the evidence for the halt.

    Asked after the row is kept, so the run that stopped still shows what the
    last task did. A check placed before the append would leave a record whose
    final task is missing -- the one a reader would go looking for first.
    """
    seen: list[str] = []
    outcome, _ = _run(
        tmp_path,
        _tasks(4),
        _success,
        on_task=lambda tid, row: seen.append(tid),
        stop_when=lambda task_id: (
            StoppedEarly(
                rule_index=0,
                rule=STOP_RULES[0],
                detail="stopped here",
                after_task=task_id,
            )
            if task_id == "task-0002"
            else None
        ),
    )
    assert [row["task_id"] for row in outcome.rows] == ["task-0001", "task-0002"]
    assert seen == ["task-0001", "task-0002"]


def test_a_run_with_no_stop_when_behaves_exactly_as_before(tmp_path):
    outcome, _ = _run(tmp_path, _tasks(3), _success)
    assert outcome.stopped is None
    assert len(outcome.rows) == 3


def test_a_stop_when_that_never_fires_does_not_shorten_the_run(tmp_path):
    asked: list[str] = []

    def never(task_id):
        asked.append(task_id)
        return None

    outcome, _ = _run(tmp_path, _tasks(3), _success, stop_when=never)
    assert outcome.stopped is None
    assert len(outcome.rows) == 3
    assert asked == ["task-0001", "task-0002", "task-0003"]
