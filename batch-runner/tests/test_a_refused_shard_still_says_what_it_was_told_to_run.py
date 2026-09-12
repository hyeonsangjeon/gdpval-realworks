"""What a shard leaves behind when its driver will not carry on.

Three files come out of a paid V2 shard and the artifact upload takes all of
them: ``journal.jsonl`` as the tasks finish, the sqlite ledger as the calls
settle, and ``run_record.json`` at the very end. Only the third says which
tasks *this* shard was told to run.

``DriverRefused`` is raised in three places and one of them is mid-run:
:mod:`core.agentic_v2_run_driver` refuses a backend that hands back something
that is not a result envelope, and it does that *after* ``runner.run`` has
returned — that is, after the model was asked and the provider billed. The
stage script caught it, printed it and returned, and the ``record = {...}``
block sits below that return. So a shard that refused on task seven of ten
uploaded a journal, a ledger and no record.

What that costs, precisely, because it is not the money:

* :func:`~core.agentic_v2_shard_collection.stage_problems` reads
  ``shard.task_ids`` out of the record to decide coverage. With no record the
  shard's tasks read as *nobody was assigned these*, which is a different
  sentence from *these were assigned and not reached*.
* :func:`scripts.roll_up_agentic_v2_cost.read_records` reads the same field for
  the same reason, and says so in its own docstring: losing a record costs the
  cohort list, not the amounts.
* :func:`~core.agentic_v2_shard_collection.siblings_that_stopped_the_run` reads
  ``run.stopped_early`` so that a shard which has not started yet can decline
  to. A refusal that wrote nothing was invisible to it, and the waves after it
  started and spent.

So the refusal writes the record too, and this module pins both halves: that
the handler does not return before it, and that what it writes is a record the
existing readers understand.

Nothing here spends anything.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

from core.agentic_v2_run_driver import (
    DRIVER_REFUSED_RULE,
    DriverRefused,
    RunOutcome,
    the_run_was_refused,
)
from core.agentic_v2_shard_collection import (
    RUN_RECORD_NAME,
    read_shard_records,
    siblings_that_stopped_the_run,
    stage_problems,
)


BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
STAGE_SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"
for _path in (BATCH_RUNNER_ROOT, BATCH_RUNNER_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

RUN_ID = "run-refused-1"
THE_SHARD_RAN = ("task-a", "task-b", "task-c")
THE_OTHER_SHARD_RAN = ("task-d", "task-e")


# ── the block the record is built from ───────────────────────────────────


def test_the_refusal_block_is_the_shape_every_reader_already_knows():
    """One shape for the ``run`` slot, or every reader needs a type check first."""
    refused = the_run_was_refused(DriverRefused("the backend returned str"),
                                  run_id=RUN_ID)
    finished = RunOutcome(run_id=RUN_ID).as_dict()

    assert set(refused) == set(finished)
    assert refused["run_id"] == RUN_ID


def test_what_was_not_measured_is_none_and_not_an_empty_list():
    """``[]`` would be a claim. The journal beside it is the real answer.

    The driver was part-way through the manifest, so some tasks ran and their
    rows went with the exception. An empty ``results`` published beside a
    journal full of rows is the reassuring reading of a disagreement, which is
    the one that must not be written.
    """
    refused = the_run_was_refused(DriverRefused("mid-manifest"), run_id=RUN_ID)

    assert refused["results"] is None
    assert refused["summary"] is None
    assert refused["skipped_on_resume"] is None
    # And the finished path still says the opposite, so the difference means
    # something rather than being two ways of writing the same silence.
    assert RunOutcome(run_id=RUN_ID).as_dict()["results"] == []


def test_the_refusal_carries_the_reason_rather_than_only_the_fact():
    refused = the_run_was_refused(
        DriverRefused("the runner returned str for 'task-b'"), run_id=RUN_ID
    )
    halt = refused["stopped_early"]

    assert halt["rule"] == DRIVER_REFUSED_RULE
    assert "task-b" in halt["detail"]


def test_a_refusal_with_nothing_to_say_still_halts():
    """``None`` in, a halt out. A missing reason must not read as no halt."""
    halt = the_run_was_refused(None, run_id=RUN_ID)["stopped_early"]

    assert halt["rule"] == DRIVER_REFUSED_RULE
    assert halt["detail"] == ""


# ── what the readers do with it ──────────────────────────────────────────


def a_record(*, task_ids, index, of, run) -> dict:
    """A shard record with the fields the collection code actually reads."""
    return {
        "stage": "trial_30",
        "run_id": RUN_ID,
        "binding": {"task_ids": list(THE_SHARD_RAN + THE_OTHER_SHARD_RAN)},
        "shard": {
            "index": index,
            "of": of,
            "task_count": len(task_ids),
            "cohort_size": len(THE_SHARD_RAN + THE_OTHER_SHARD_RAN),
            "task_ids": list(task_ids),
        },
        "run": run,
    }


def written(tmp_path: Path, name: str, record: dict) -> Path:
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / RUN_RECORD_NAME).write_text(json.dumps(record), encoding="utf-8")
    return folder


@pytest.fixture()
def one_refused_one_finished(tmp_path: Path) -> Path:
    written(
        tmp_path,
        "agentic-v2-trial_30-shard-1-of-2",
        a_record(
            task_ids=THE_SHARD_RAN,
            index=1,
            of=2,
            run=the_run_was_refused(
                DriverRefused("the runner returned str for 'task-b'"),
                run_id=RUN_ID,
            ),
        ),
    )
    written(
        tmp_path,
        "agentic-v2-trial_30-shard-2-of-2",
        a_record(
            task_ids=THE_OTHER_SHARD_RAN,
            index=2,
            of=2,
            run=RunOutcome(run_id=RUN_ID).as_dict(),
        ),
    )
    return tmp_path


def test_the_refused_shards_tasks_are_still_known_to_have_been_assigned(
    one_refused_one_finished,
):
    """The whole point of writing the file. Coverage can see the cohort again."""
    records = read_shard_records(one_refused_one_finished)
    assert len(records) == 2

    assigned = [
        task_id
        for _, record in records
        for task_id in record["shard"]["task_ids"]
    ]
    assert sorted(assigned) == sorted(THE_SHARD_RAN + THE_OTHER_SHARD_RAN)


def test_the_stage_is_not_called_run_and_the_refusal_is_the_reason(
    one_refused_one_finished,
):
    """Named, not merely missing. Both are failures; only one is diagnosable."""
    records = read_shard_records(one_refused_one_finished)
    problems = stage_problems(
        records, task_ids=list(THE_SHARD_RAN + THE_OTHER_SHARD_RAN)
    )

    assert problems
    joined = " ".join(problems)
    assert DRIVER_REFUSED_RULE in joined
    assert "task-b" in joined


def test_a_shard_that_has_not_started_declines_to(one_refused_one_finished):
    """The saving, and the reason the rule is deliberately unplaceable.

    A driver refuses on the shape of what a backend returned, and the backend
    is the same checked-out code in every job. ``_rule_index_of`` cannot place
    this rule, and an unplaceable rule is treated as a fact about the whole
    run — so the next wave does not start.
    """
    records = read_shard_records(one_refused_one_finished)
    reasons = siblings_that_stopped_the_run(records)

    assert len(reasons) == 1
    assert "cannot place" in reasons[0]
    assert "task-b" in reasons[0]


def test_a_stage_where_nothing_refused_lets_the_next_wave_start(tmp_path):
    """The control. Otherwise the test above passes on a function that always halts."""
    written(
        tmp_path,
        "agentic-v2-trial_30-shard-1-of-1",
        a_record(
            task_ids=THE_SHARD_RAN + THE_OTHER_SHARD_RAN,
            index=1,
            of=1,
            run=RunOutcome(run_id=RUN_ID).as_dict(),
        ),
    )
    records = read_shard_records(tmp_path)

    assert siblings_that_stopped_the_run(records) == []
    assert (
        stage_problems(records, task_ids=list(THE_SHARD_RAN + THE_OTHER_SHARD_RAN))
        == []
    )


# ── the regression this module exists to stop ────────────────────────────


def the_driver_refused_handler() -> ast.ExceptHandler:
    """The ``except DriverRefused`` block in the stage script, as parsed.

    Read off the syntax rather than by running ``main``: reaching this handler
    for real needs a dataset snapshot, a bound cohort, a staged workspace and a
    backend that misbehaves, and a test that heavy would be skipped long before
    it was fixed. What can go wrong here is one line — a ``return`` put back
    above the record — and that is a fact about the tree.
    """
    tree = ast.parse(STAGE_SCRIPT.read_text(encoding="utf-8"))
    handlers = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler)
        and isinstance(node.type, ast.Name)
        and node.type.id == "DriverRefused"
    ]
    assert len(handlers) == 1, (
        f"{len(handlers)} `except DriverRefused` handlers in {STAGE_SCRIPT.name}; "
        "this check names one and would silently cover only the first"
    )
    return handlers[0]


def test_the_refusal_handler_does_not_return_before_the_record_is_written():
    """The defect itself, stated as the one line that brings it back.

    ``print(...); return 1`` is what the handler used to be, and the
    ``record = {...}`` block is below it. Everything else in this module tests
    what the record says; this tests that there is one.
    """
    handler = the_driver_refused_handler()
    returns = [node for node in ast.walk(handler) if isinstance(node, ast.Return)]

    assert returns == [], (
        "the `except DriverRefused` handler returns, so the record block below "
        "it is skipped and a refused shard uploads a journal and a ledger with "
        "nothing that says which tasks it was told to run"
    )


def test_the_handler_keeps_the_refusal_for_the_record_to_use():
    """A handler that swallowed it would write a halt with an empty reason."""
    handler = the_driver_refused_handler()
    assigned = {
        target.id
        for node in ast.walk(handler)
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }

    assert handler.name, "the exception is not bound to a name"
    assert assigned, "the handler binds nothing, so the reason cannot reach the record"
