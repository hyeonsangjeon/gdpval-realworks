"""Resume granularity is one whole task, so the chunk has to outlast one task.

``--resume`` harvests *completed* ``task_id``s from the partial on disk. A task
that is abandoned part-way leaves nothing behind, so the next chunk starts it
from zero. That makes the chunk budget a hard floor rather than a preference:
if a single task cannot be graded inside one chunk, no number of chunks will
ever grade it, and each attempt pays the full price of the attempt.

Gold shard 4 of 11 found the floor. Task ``9e39df84`` -- 57 rubric items of a
Manufacturing deliverable -- ran for 4h21m of a 4h budget and completed
nothing. Eleven of its grading calls exhausted the config's 2400-token
per-item output budget without returning parseable final text
(``empty_final_text:max_output_tokens``); the retry-without-tools cycles that
followed accounted for 4h18m of the 4h21m. The chunk exited 5, not 7 --
a chunk that finished no task declines to buy another one on identical terms.
That refusal is correct and is not what this file changes.

What had to change was the wall clock, and the reason it *could* change is the
subject of the first test: ``compute_grader_source_hash`` covers
``batch-runner`` and the grading config, and ``.github/workflows`` is in
neither. The per-item token cap lives in the grading config, so raising *that*
would have refingerprinted the grader and orphaned the ten shards already paid
for and committed. The workflow's timing dials are the only ones that can move
without invalidating a run in progress.

Nothing here calls a model or a network.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import step8_grade as s8

BATCH_ROOT = Path(s8.__file__).resolve().parent
REPO_ROOT = BATCH_ROOT.parent
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"

#: What task ``9e39df84`` spent in one chunk without finishing, measured from
#: the timestamps of run ``33273207562``: grading opened at 20:35:14Z and the
#: deadline fired at 00:56:34Z. A budget at or under this figure reproduces the
#: stall exactly, because the task restarts from nothing each time.
OBSERVED_LONGEST_TASK_MINUTES = 261


def _workflow_budget_minutes() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    budget = re.search(r'GRADER_TIME_BUDGET_SEC:\s*"(\d+)"', text)
    assert budget, "grade-run.yml no longer states its chunk budget"
    return int(budget.group(1)) // 60


def test_a_workflow_file_cannot_enter_the_grader_source_hash():
    """The invariant that made this fix possible at all.

    Every path the hash digests is resolved against ``batch-runner`` and
    rejected if it escapes. ``.github/workflows/grade-run.yml`` escapes, so no
    edit to the workflow can move the fingerprint that ties a shard to its
    siblings. If this ever stops being true, changing a timeout mid-run would
    silently orphan the shards already on disk.
    """
    with pytest.raises(ValueError, match="outside batch-runner"):
        s8._checked_grader_source_file(BATCH_ROOT, WORKFLOW)


def test_the_grader_hash_is_blind_to_the_workflows_directory():
    """The same claim end to end, rather than through one helper.

    The hash is taken twice with the workflow rewritten in between. Anything
    that started digesting ``.github`` would show up as two different digests.
    The file is restored in ``finally`` so a failure here cannot leave the
    working tree dirty.
    """
    config_path = "grading_configs/gold_ceiling_185_v2_sol_max.yaml"
    import yaml

    config = yaml.safe_load((BATCH_ROOT / config_path).read_text(encoding="utf-8"))

    original = WORKFLOW.read_bytes()
    before = s8.compute_grader_source_hash(config_path, config)
    try:
        WORKFLOW.write_bytes(original + b"\n# touched by a test\n")
        after = s8.compute_grader_source_hash(config_path, config)
    finally:
        WORKFLOW.write_bytes(original)

    assert before == after, (
        "the grader source hash moved when only the workflow changed; a "
        "timing edit would now orphan every shard already committed"
    )
    assert WORKFLOW.read_bytes() == original


def test_the_chunk_budget_outlasts_the_longest_task_a_shard_has_needed():
    """The floor, stated as a number that a revert would trip over.

    Not a performance target -- a correctness one. Below this line the task
    that stalled shard 4 is ungradeable rather than slow, and every retry
    spends a chunk's worth of judging to learn nothing.
    """
    budget = _workflow_budget_minutes()

    assert budget > OBSERVED_LONGEST_TASK_MINUTES, (
        f"a {budget} min chunk cannot finish a task already measured at "
        f"{OBSERVED_LONGEST_TASK_MINUTES} min; --resume restarts an "
        "unfinished task from nothing, so it would stall here forever"
    )


def test_the_per_item_cap_still_lives_where_it_refingerprints_the_grader():
    """Why the token cap was not the lever, kept honest against drift.

    ``2400`` is the budget those eleven calls exhausted. It sits in the
    grading config, which the hash *does* cover -- so if a later change moves
    it out of the config and into the workflow, the trade-off recorded above
    stops being true and this test should be revisited rather than deleted.
    """
    config = (BATCH_ROOT / "grading_configs/gold_ceiling_185_v2_sol_max.yaml").read_text(
        encoding="utf-8"
    )

    assert "per_item_max_output_tokens: 2400" in config
    assert "per_item_max_output_tokens" not in WORKFLOW.read_text(encoding="utf-8")
