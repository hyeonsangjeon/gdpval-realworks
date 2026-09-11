"""What the task journal has to survive: a kill, a resume, and a second run.

The tests that matter here are the ones that produce a *file* and then read it
back with a different object, because an in-memory journal is not the thing
being built. Several of them truncate the file by hand: that is the interruption
the module exists for, and asserting on it is the only way to know the recovery
is real rather than described.
"""

from __future__ import annotations

import json

import pytest

from core.agentic_v2_task_journal import (
    DECISION_RUN,
    DECISION_SKIP_FINISHED,
    DECISION_SKIP_SETTLED_FAILURE,
    JOURNAL_SCHEMA_VERSION,
    MOST_ATTEMPTS_PER_TASK,
    OUTCOME_FAILED,
    OUTCOME_FINISHED,
    JournalCorrupt,
    JournalRefused,
    TaskJournal,
    manifest_digest,
    read_journal,
    workspace_name_for,
)
from core.cost_receipts import STATUS_COMPLETE, STATUS_PARTIAL


TASKS = ("task-one", "task-two", "task-three")

A_DELIVERABLE = {
    "path": "out/report.xlsx",
    "sha256": "a" * 64,
    "size": 4096,
}


class _Tick:
    """A clock that moves by one and never surprises an assertion."""

    def __init__(self) -> None:
        self.now = 1_700_000_000.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


def _journal(tmp_path, *, run_id="run-a", tasks=TASKS):
    return TaskJournal(
        tmp_path / "journal.jsonl",
        run_id=run_id,
        task_ids=tasks,
        clock=_Tick(),
    )


# ── names ────────────────────────────────────────────────────────────────


def test_manifest_digest_depends_on_order():
    assert manifest_digest(["a", "b"]) != manifest_digest(["b", "a"])


def test_manifest_digest_refuses_a_repeated_task():
    with pytest.raises(JournalRefused, match="same task twice"):
        manifest_digest(["a", "a"])


def test_manifest_digest_refuses_an_empty_manifest():
    with pytest.raises(JournalRefused, match="not a manifest"):
        manifest_digest([])


def test_long_task_ids_sharing_a_prefix_do_not_share_a_workspace():
    shared = "x" * 60
    first = workspace_name_for(shared + "-alpha", 1)
    second = workspace_name_for(shared + "-beta", 1)
    assert first != second


def test_a_workspace_name_carries_its_attempt():
    assert workspace_name_for("task-one", 2).endswith("-a02")


def test_attempt_numbering_starts_at_one():
    with pytest.raises(JournalRefused, match="starts at 1"):
        workspace_name_for("task-one", 0)


# ── the ordinary path ────────────────────────────────────────────────────


def test_a_fresh_journal_plans_every_task_to_run(tmp_path):
    journal = _journal(tmp_path)
    plan = journal.plan()
    assert plan.to_run() == TASKS
    assert plan.receipt_ceiling() == STATUS_COMPLETE
    assert all(standing.attempts == 0 for standing in plan.standings)


def test_the_header_is_the_first_line_on_disk(tmp_path):
    journal = _journal(tmp_path)
    first = json.loads(journal.path.read_text(encoding="utf-8").splitlines()[0])
    assert first["kind"] == "header"
    assert first["schema_version"] == JOURNAL_SCHEMA_VERSION
    assert first["task_count"] == len(TASKS)


def test_a_finished_task_is_skipped_on_resume(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=True,
    )
    standing = journal.standing("task-one")
    assert standing.decision == DECISION_SKIP_FINISHED
    assert standing.cost_is_fully_accounted
    assert journal.plan().to_run() == ("task-two", "task-three")


def test_the_deliverables_survive_the_round_trip(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=True,
    )
    reloaded = read_journal(journal.path)
    assert reloaded.closed[0].deliverables == (A_DELIVERABLE,)


def test_a_retryable_failure_is_run_again(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FAILED,
        error_type="compute_start_failed",
        cost_settled=True,
    )
    standing = journal.standing("task-one")
    assert standing.decision == DECISION_RUN
    assert standing.last_closed is not None
    assert standing.last_closed.disposition == "infrastructure"


def test_a_terminal_failure_is_not_run_again(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FAILED,
        error_type="runner_internal_error",
        cost_settled=True,
    )
    standing = journal.standing("task-one")
    assert standing.decision == DECISION_SKIP_SETTLED_FAILURE
    assert standing.last_closed is not None
    assert standing.last_closed.disposition == "runner_defect"


def test_attempts_are_numbered_and_never_share_a_workspace(tmp_path):
    journal = _journal(tmp_path)
    seen = set()
    for _ in range(MOST_ATTEMPTS_PER_TASK):
        opened = journal.open_task("task-one")
        assert opened.workspace_name not in seen
        seen.add(opened.workspace_name)
        journal.close_task(
            outcome=OUTCOME_FAILED,
            error_type="compute_start_failed",
            cost_settled=True,
        )
    assert len(seen) == MOST_ATTEMPTS_PER_TASK
    assert journal.standing("task-one").decision == DECISION_SKIP_SETTLED_FAILURE


def test_a_task_may_not_exceed_the_attempt_ceiling(tmp_path):
    journal = _journal(tmp_path)
    for _ in range(MOST_ATTEMPTS_PER_TASK):
        journal.open_task("task-one")
        journal.close_task(
            outcome=OUTCOME_FAILED,
            error_type="compute_start_failed",
            cost_settled=True,
        )
    with pytest.raises(JournalRefused, match="ceiling"):
        journal.open_task("task-one")


# ── the interruption ─────────────────────────────────────────────────────


def test_an_abandoned_attempt_is_run_again_and_never_fully_accounted(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")  # and then the process dies

    resumed = _journal(tmp_path)
    standing = resumed.standing("task-one")
    assert standing.decision == DECISION_RUN
    assert standing.abandoned_attempts == 1
    assert not standing.cost_is_fully_accounted
    assert "interrupted" in standing.reason
    assert resumed.plan().receipt_ceiling() == STATUS_PARTIAL


def test_a_resumed_attempt_gets_a_new_workspace(tmp_path):
    journal = _journal(tmp_path)
    first = journal.open_task("task-one")

    resumed = _journal(tmp_path)
    second = resumed.open_task("task-one")
    assert second.attempt_index == first.attempt_index + 1
    assert second.workspace_name != first.workspace_name


def test_a_later_success_does_not_undo_an_abandoned_attempt(tmp_path):
    """The spend that vanished stays vanished, however well the retry goes."""
    journal = _journal(tmp_path)
    journal.open_task("task-one")

    resumed = _journal(tmp_path)
    resumed.open_task("task-one")
    resumed.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=True,
    )
    standing = resumed.standing("task-one")
    assert standing.decision == DECISION_SKIP_FINISHED
    assert standing.abandoned_attempts == 1
    assert not standing.cost_is_fully_accounted
    assert resumed.plan().receipt_ceiling() == STATUS_PARTIAL
    assert resumed.plan().unaccounted_tasks() == ("task-one",)


def test_an_unsettled_cost_lowers_the_ceiling_too(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=False,
    )
    assert not journal.standing("task-one").cost_is_fully_accounted
    assert journal.plan().receipt_ceiling() == STATUS_PARTIAL


def test_a_torn_final_line_is_dropped_and_the_rest_survives(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=True,
    )
    journal.open_task("task-two")

    raw = journal.path.read_text(encoding="utf-8")
    journal.path.write_text(raw[: len(raw) - 20], encoding="utf-8")

    state = read_journal(journal.path)
    assert state.dropped_torn_tail
    assert [record.task_id for record in state.opened] == ["task-one"]
    assert [record.task_id for record in state.closed] == ["task-one"]

    resumed = _journal(tmp_path)
    assert resumed.plan().to_run() == ("task-two", "task-three")


def test_a_torn_line_in_the_middle_is_refused(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=True,
    )
    lines = journal.path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1][:-9]
    journal.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(JournalCorrupt, match="corruption rather than"):
        read_journal(journal.path)


def test_a_zero_length_journal_is_started_again_rather_than_refused(tmp_path):
    where = tmp_path / "journal.jsonl"
    where.write_bytes(b"")
    journal = TaskJournal(
        where, run_id="run-a", task_ids=TASKS, clock=_Tick()
    )
    assert journal.plan().to_run() == TASKS


# ── refusals ─────────────────────────────────────────────────────────────


def test_a_second_run_may_not_share_a_journal(tmp_path):
    _journal(tmp_path)
    with pytest.raises(JournalRefused, match="must not share a journal"):
        _journal(tmp_path, run_id="run-b")


def test_a_different_manifest_is_refused(tmp_path):
    _journal(tmp_path)
    with pytest.raises(JournalRefused, match="different task manifest"):
        _journal(tmp_path, tasks=("task-one", "task-two"))


def test_a_task_outside_the_manifest_is_refused(tmp_path):
    journal = _journal(tmp_path)
    with pytest.raises(JournalRefused, match="fixed manifest"):
        journal.open_task("task-nine")


def test_two_tasks_may_not_be_open_at_once(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    with pytest.raises(JournalRefused, match="one task at a time"):
        journal.open_task("task-two")


def test_a_finished_task_may_not_be_reopened(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    journal.close_task(
        outcome=OUTCOME_FINISHED,
        deliverables=[A_DELIVERABLE],
        cost_settled=True,
    )
    with pytest.raises(JournalRefused, match="already finished"):
        journal.open_task("task-one")


def test_closing_nothing_is_refused(tmp_path):
    journal = _journal(tmp_path)
    with pytest.raises(JournalRefused, match="nothing to close"):
        journal.close_task(outcome=OUTCOME_FINISHED, cost_settled=True)


def test_finishing_with_no_deliverables_is_refused(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    with pytest.raises(JournalRefused, match="nothing left to collect"):
        journal.close_task(
            outcome=OUTCOME_FINISHED, deliverables=[], cost_settled=True
        )


def test_a_deliverable_without_a_digest_is_refused(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    with pytest.raises(JournalRefused, match="claim rather than a record"):
        journal.close_task(
            outcome=OUTCOME_FINISHED,
            deliverables=[{"path": "out/report.xlsx"}],
            cost_settled=True,
        )


def test_finishing_with_an_error_type_is_refused(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    with pytest.raises(JournalRefused, match="does not also carry an error"):
        journal.close_task(
            outcome=OUTCOME_FINISHED,
            error_type="compute_start_failed",
            deliverables=[A_DELIVERABLE],
            cost_settled=True,
        )


def test_an_error_the_contract_does_not_name_is_refused(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    with pytest.raises(JournalRefused, match="no recorded disposition"):
        journal.close_task(
            outcome=OUTCOME_FAILED,
            error_type="the_vibes_were_off",
            cost_settled=True,
        )


def test_an_outcome_the_journal_does_not_name_is_refused(tmp_path):
    journal = _journal(tmp_path)
    journal.open_task("task-one")
    with pytest.raises(JournalRefused, match="is not an outcome"):
        journal.close_task(outcome="sort_of_worked", cost_settled=True)


def test_a_journal_from_another_schema_version_is_refused(tmp_path):
    journal = _journal(tmp_path)
    lines = journal.path.read_text(encoding="utf-8").splitlines()
    head = json.loads(lines[0])
    head["schema_version"] = "agentic-v2-task-journal-v0"
    lines[0] = json.dumps(head, sort_keys=True)
    journal.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(JournalCorrupt, match="was written under"):
        read_journal(journal.path)


def test_a_file_that_does_not_start_with_a_header_is_refused(tmp_path):
    where = tmp_path / "journal.jsonl"
    where.write_text(json.dumps({"kind": "opened"}) + "\n", encoding="utf-8")
    with pytest.raises(JournalCorrupt, match="does not begin with a header"):
        read_journal(where)


def test_a_missing_journal_is_refused_rather_than_invented(tmp_path):
    with pytest.raises(JournalRefused, match="there is no journal"):
        read_journal(tmp_path / "absent.jsonl")


def test_planning_against_a_different_manifest_is_refused(tmp_path):
    journal = _journal(tmp_path)
    state = read_journal(journal.path)
    from core.agentic_v2_task_journal import plan_resume

    with pytest.raises(JournalRefused, match="different task manifest"):
        plan_resume(state, ("task-one", "task-two"))
