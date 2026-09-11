"""The matrix a paid stage fans out over, checked before it is dispatched.

`.github/workflows/agentic-v2-stage-run.yml` builds its matrix by running
`scripts/plan_agentic_v2_shards.py` and handing the result to ``fromJSON``. That
is one string, produced in a job, consumed by a job, and every way it can be
wrong is a way that costs money:

* a list that does not cover the cohort runs a stage that is missing tasks, and
  the run still finishes and still reports;
* a list that covers a task twice pays for it twice;
* a list sized against the wrong timeout produces jobs that are killed at six
  hours, losing the task each was in the middle of;
* a string ``fromJSON`` cannot read fails the dispatch, which is the *good*
  case and still wastes the setup.

So the properties are checked here, where finding out is free, rather than in
the first dispatch that uses them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_preregistration import ESCALATION, STAGE_SIZES  # noqa: E402
from core.agentic_v2_sharding import coverage_problems  # noqa: E402
from core.agentic_v2_sharding import parse as parse_shard  # noqa: E402

SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "plan_agentic_v2_shards.py"
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "agentic-v2-stage-run.yml"


def _plan(stage: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--stage", stage, *extra],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


# ── The string the workflow actually captures ─────────────────────────────


@pytest.mark.parametrize("stage", ESCALATION)
def test_the_matrix_is_one_line_of_json_that_fromjson_can_read(stage):
    """One line because a workflow output with a newline in it is a parse error.

    Not a hypothetical: ``echo "matrix=$(...)" >> $GITHUB_OUTPUT`` with a
    multi-line value writes a broken output file, and the failure surfaces two
    steps later as an empty matrix rather than as a bad value.
    """
    finished = _plan(stage)

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout.count("\n") == 1

    shards = json.loads(finished.stdout)
    assert isinstance(shards, list)
    assert all(isinstance(one, str) for one in shards)
    assert shards, "a stage with no shards would dispatch a matrix of no jobs"


@pytest.mark.parametrize("stage", ESCALATION)
def test_every_value_in_the_matrix_is_something_the_runner_accepts(stage):
    """The producer and the consumer agree, checked rather than assumed.

    These two are joined only by a string passed through a workflow input, which
    is the kind of seam where a format changes on one side and is noticed on the
    other by a paid job failing at its first argument parse.
    """
    ids = tuple(f"task-{n}" for n in range(STAGE_SIZES[stage]))

    for value in json.loads(_plan(stage).stdout):
        shard = parse_shard(value, ids)
        assert shard is None or shard.task_ids


@pytest.mark.parametrize("stage", ESCALATION)
def test_the_matrix_covers_the_cohort_exactly_once(stage):
    """The property the whole split exists to have, checked end to end.

    Run against the real stage sizes, through the real parser, using the same
    coverage check a finished set of shards is judged by. A matrix that passes
    here cannot leave a task unrun or run one twice.
    """
    ids = tuple(f"task-{n}" for n in range(STAGE_SIZES[stage]))
    values = json.loads(_plan(stage).stdout)

    pieces = [parse_shard(value, ids) for value in values]
    if pieces == [None]:
        # One shard of one: the unsharded run, which covers the cohort by
        # definition. `parse` returns None for it on purpose.
        assert len(values) == 1
        return

    assert coverage_problems(pieces, task_ids=ids) == []


@pytest.mark.parametrize("stage", ESCALATION)
def test_no_shard_can_outlast_the_job_it_runs_in(stage):
    """Worst case per shard, against the step timeout the workflow sets.

    This is the number the split is for. If the plan's per-task ceiling rises,
    or GitHub's limit falls, this is where it should be noticed -- not by a job
    being killed with four hours of paid conversation in it.
    """
    explained = json.loads(_plan(stage, "--explain").stdout)

    step_timeout_hours = 300 / 60
    assert explained["worst_case_hours_per_shard"] <= step_timeout_hours, explained


def test_the_five_task_stage_still_runs_as_one_job():
    """The smallest stage must not pick up a matrix it does not need.

    `advance_check_5` is the stage that has actually been approved for marking
    as well as running, so it is the one whose results will be quoted most. It
    should run the way it did before sharding existed.
    """
    assert json.loads(_plan("advance_check_5").stdout) == ["1/1"]


def test_a_stage_nobody_registered_is_refused_by_name():
    finished = _plan("full_500")

    assert finished.returncode != 0
    assert "invalid choice" in finished.stderr or "not a registered stage" in (
        finished.stderr + finished.stdout
    )


# ── The workflow is wired to the script it is documented to use ───────────


def test_the_paid_job_fans_out_over_what_the_free_job_worked_out(workflow):
    """Not written by hand into the matrix, where it would go stale silently."""
    free = workflow["jobs"]["free"]
    paid = workflow["jobs"]["paid"]

    assert free["outputs"]["shards"] == "${{ steps.shards.outputs.matrix }}"
    assert paid["strategy"]["matrix"]["shard"] == (
        "${{ fromJSON(needs.free.outputs.shards) }}"
    )
    assert any(
        step.get("id") == "shards" and "plan_agentic_v2_shards.py" in step.get("run", "")
        for step in free["steps"]
    )


def test_one_shard_failing_does_not_cancel_the_others(workflow):
    """Each of them has already been charged for the turns it made.

    ``fail-fast`` defaults to true, so this has to be written down. Left at the
    default, the first shard to hit a bad task would throw away the paid work of
    every shard still running.
    """
    assert workflow["jobs"]["paid"]["strategy"]["fail-fast"] is False


def test_the_matrix_is_throttled_because_it_all_talks_to_one_deployment(workflow):
    assert 1 <= workflow["jobs"]["paid"]["strategy"]["max-parallel"] <= 6


def test_the_run_step_stops_before_the_job_does_and_the_job_before_github_does(
    workflow,
):
    """Three limits, in an order that keeps the record.

    A failed *step* leaves the rest of the job to run, and the rest of the job is
    the upload. A job that hits its own limit, or GitHub's six hour kill, can
    take the artifact of an already-charged run with it.
    """
    paid = workflow["jobs"]["paid"]
    run_step = next(step for step in paid["steps"] if step.get("id") == "run")

    assert run_step["timeout-minutes"] < paid["timeout-minutes"] < 6 * 60


def test_the_artifact_of_each_shard_has_its_own_name(workflow):
    """Seventeen archives called the same thing is not a record of anything.

    Artifact names also have to be unique within a run, so this is both a
    readability point and a correctness one.
    """
    upload = next(
        step
        for step in workflow["jobs"]["paid"]["steps"]
        if "upload-artifact" in str(step.get("uses", ""))
    )

    assert "SHARD_SLUG" in upload["with"]["name"]
    assert upload["if"] == "${{ always() }}"
