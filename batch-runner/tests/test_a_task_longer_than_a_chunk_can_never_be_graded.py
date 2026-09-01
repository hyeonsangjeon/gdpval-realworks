"""Resume granularity is one whole task, so the chunk has to outlast one task.

``--resume`` harvests *completed* ``task_id``s from the partial on disk. A task
that is abandoned part-way leaves nothing behind, so the next chunk starts it
from zero. That makes the chunk budget a hard floor rather than a preference:
if a single task cannot be graded inside one chunk, no number of chunks will
ever grade it, and each attempt pays the full price of the attempt.

Gold shard 4 of 11 found the floor, and then four attempts found the ceiling.
Task ``9e39df84`` is 57 rubric items of a Manufacturing deliverable. Eleven of
its grading calls exhaust the config's 2400-token per-item output budget
without returning parseable final text (``empty_final_text:max_output_tokens``)
and the retry-without-tools cycles that follow are most of its runtime. Every
attempt ended the same way: the guard fired at a rubric-item boundary inside
the task, no task completed, and the chunk exited 5 rather than 7 -- a chunk
that finished nothing declines to buy another one on identical terms. That
refusal is correct and is not what this file is about.

    attempt  run           budget  grading ran  items done  stopped starting
    1        33273207562   240     261.3        45          46
    2        33286656393   300     310.4        54          55  feb54fa4
    3        33301041542   336     348.0        54          55  feb54fa4
    4        33316285562   338     346.0        55          56  b0e21451

Three raises bought nine items, and the third bought none at all: attempts 2
and 3 stopped at the same item having done the same 54, 37.6 min apart. The
pace is what moves, not the work -- 5.75, 5.81, 6.29 and 6.44 min an item
across the four. So the honest quantity is not "how long the task takes" but
"how long a full pass costs at each pace that has actually been observed",
which is what ``MEASURED_FULL_PASS_MINUTES`` holds.

Two of those four passes fit in the window the platform allows. The two most
recent do not, by 7 and 15 min, and no budget can buy that back: the window is
the 360 min runner kill less setup and less the save at the end, and it is
already fully spent. That is the conclusion the previous revision of this file
pre-registered as the reading it would accept -- "if a third attempt also falls
short, the honest reading is that this task cannot be graded under the
pre-registered settings, not that some number here needs nudging again".

What could have changed is the subject of the first tests, and none of it
helps. ``compute_grader_source_hash`` covers ``batch-runner`` and the grading
config; ``.github/workflows`` is in neither, so the clock could move without
orphaning the ten shards already paid for. The per-item token cap that causes
the retries lives in the grading config, so raising *that* refingerprints the
grader. Skipping the task or moving it down the order is refused by the pinned
rerun identity. The clock was the only lever, and it is now at its stop.

The cost of stopping here is not one task. ``9e39df84`` is 7th of 17 in its
shard, so the ten after it have never been reached at all.

Nothing here calls a model or a network.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

import step8_grade as s8
from tests.test_full_gold_corpus_contract import (
    PLATFORM_HARD_KILL_MINUTES,
    SAVE_AND_COMMIT_MINUTES,
    SETUP_MINUTES_BEFORE_GRADING,
)

BATCH_ROOT = Path(s8.__file__).resolve().parent
REPO_ROOT = BATCH_ROOT.parent
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"
FULL_CONFIG_PATH = BATCH_ROOT / "grading_configs/gold_ceiling_185_v2_sol_max.yaml"

#: The task that stalled shard 4, and where it sits in that shard's slice.
STALLED_TASK_ID = "9e39df84-ac57-4c9b-a2e3-12b8abf2c797"
STALLED_TASK_RUBRIC_ITEMS = 57
SHARD_COUNT = 11
STALLED_TASK_SHARD_INDEX = 4

#: The longest a single task has been watched to run without finishing --
#: attempt 3, which spent 348.0 min to complete the same 54 items attempt 2
#: completed in 310.4. A budget at or under this figure is known to have bought
#: nothing, because an abandoned task leaves no partial behind and restarts
#: from item 1.
OBSERVED_LONGEST_TASK_MINUTES = 348

#: What one complete pass at all 57 items costs, at each pace measured, in
#: attempt order. Each entry is (minutes watched / items completed) * 57 --
#: a measured rate extended over the whole task, not a guess about it:
#:
#:     1  261.3 / 45 = 5.81 -> 331
#:     2  310.4 / 54 = 5.75 -> 328
#:     3  348.0 / 54 = 6.44 -> 367
#:     4  346.0 / 55 = 6.29 -> 359
#:
#: They are kept in order because the order is the finding: the two that fit
#: are the two oldest.
MEASURED_FULL_PASS_MINUTES = (331, 328, 367, 359)


def _workflow_budget_minutes() -> int:
    text = WORKFLOW.read_text(encoding="utf-8")
    budget = re.search(r'GRADER_TIME_BUDGET_SEC:\s*"(\d+)"', text)
    assert budget, "grade-run.yml no longer states its chunk budget"
    return int(budget.group(1)) // 60


def _grading_window_minutes() -> float:
    """The most grading time the platform can ever allow, whatever the budget.

    The job dies at 360 min no matter what is asked for. Setup happens before
    grading opens and the partial save happens after it closes, so neither is
    time the grader can spend. What is left is the whole of the lever.
    """
    return (
        PLATFORM_HARD_KILL_MINUTES
        - SETUP_MINUTES_BEFORE_GRADING
        - SAVE_AND_COMMIT_MINUTES
    )


def test_a_workflow_file_cannot_enter_the_grader_source_hash():
    """The invariant that made the three raises possible at all.

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


def test_the_platform_cannot_give_this_task_the_time_its_recent_pace_needs():
    """The conclusion, as arithmetic rather than as a judgement call.

    Not "the budget is too small" -- the budget is already every minute the
    runner leaves over. At the pace of either recent attempt a full pass wants
    more grading time than the runner exists for, so there is no value of
    ``GRADER_TIME_BUDGET_SEC`` that finishes the task and still saves. Raising
    it further would only move where inside the task the money is lost.

    If this test ever goes red it means a pass got cheaper -- the per-item cap
    was raised, the retries stopped, or the judge got faster -- and the whole
    conclusion should be re-derived rather than patched.
    """
    window = _grading_window_minutes()
    recent = MEASURED_FULL_PASS_MINUTES[-2:]

    assert min(recent) > window, (
        f"a full pass at the recent pace costs {min(recent)}-{max(recent)} min "
        f"of grading, and the runner can only ever offer {window:.1f} min "
        f"({PLATFORM_HARD_KILL_MINUTES} less {SETUP_MINUTES_BEFORE_GRADING} "
        f"setup less {SAVE_AND_COMMIT_MINUTES} save); no budget closes that gap"
    )


def test_the_two_earliest_paces_would_have_fitted_so_this_is_a_lottery():
    """The other half, so the conclusion is not overstated.

    The task is not intrinsically too big. At the pace of the first two
    attempts a full pass fits inside the window with room over, and a fifth
    attempt that happened to draw that pace would finish. What is being
    recorded is that the pace is not ours to choose and that half the observed
    draws lose, at roughly six hours of paid judging a draw.

    Kept as a test rather than a comment because if the early figures are ever
    revised the claim "half the draws would have won" stops holding, and the
    decision that rests on it should be revisited.
    """
    window = _grading_window_minutes()
    early = MEASURED_FULL_PASS_MINUTES[:2]

    assert max(early) < window, (
        f"a full pass at the early pace cost {min(early)}-{max(early)} min, "
        f"inside the {window:.1f} min window; if that is no longer true then "
        "the task never fitted and this file should say so plainly"
    )


def test_the_budget_is_at_its_stop_and_is_not_what_failed():
    """Guards the number in both directions at once.

    Below: the budget must stay under what a full pass most recently cost, so
    nobody can read the current setting as sufficient and conclude the task
    merely needs one more run.

    Above: it must stay inside the window, so a later raise that would push the
    job past the platform kill -- and take the ``always()`` cost-ledger upload
    with it -- fails here instead of in production.
    """
    budget = _workflow_budget_minutes()
    window = _grading_window_minutes()

    assert budget < MEASURED_FULL_PASS_MINUTES[-1], (
        f"a {budget} min budget is being presented as enough for a pass last "
        f"measured at {MEASURED_FULL_PASS_MINUTES[-1]} min"
    )
    assert budget <= window, (
        f"a {budget} min budget exceeds the {window:.1f} min the runner can "
        "offer; the chunk would be killed mid-save and the ledger lost"
    )


def test_the_wall_clock_is_the_only_lever_outside_the_hash():
    """Why no cheaper answer was reached for, kept checkable.

    If a later change gives the grading code a second environment variable
    that shapes cost, the reasoning above -- that the only dial outside the
    fingerprint is the clock -- stops holding, and a stalled shard should be
    answered with that dial instead of by buying more hours.
    """
    levers = set()
    for path in sorted(BATCH_ROOT.glob("core/**/*.py")) + [BATCH_ROOT / "step8_grade.py"]:
        levers.update(
            re.findall(
                r'os\.(?:getenv|environ\.get)\(\s*"(GRADER_[A-Z_0-9]+)"',
                path.read_text(encoding="utf-8"),
            )
        )

    assert levers == {"GRADER_TIME_BUDGET_SEC"}, (
        f"grading now reads {sorted(levers)} from the environment; a lever "
        "that is not the clock may be the better answer to a stalled shard"
    )


def test_the_per_item_cap_still_lives_where_it_refingerprints_the_grader():
    """Why the token cap was not the lever, kept honest against drift.

    ``2400`` is the budget those eleven calls exhausted. It sits in the
    grading config, which the hash *does* cover -- so if a later change moves
    it out of the config and into the workflow, the trade-off recorded above
    stops being true and this test should be revisited rather than deleted.
    """
    config = FULL_CONFIG_PATH.read_text(encoding="utf-8")

    assert "per_item_max_output_tokens: 2400" in config
    assert "per_item_max_output_tokens" not in WORKFLOW.read_text(encoding="utf-8")


def test_the_pinned_list_refuses_both_ways_round_the_stalled_task():
    """The two escape routes that do not exist, checked against the code.

    Dropping the task shortens the list and trips the count; moving it to the
    end keeps the count and trips the identity. Either would have turned a
    loss of eleven tasks into a loss of one, and the pin is deliberately
    stricter than that -- a run that graded a different set, or the same set in
    a different order, is a different measurement wearing this one's name.

    Both are asserted here so that a later loosening of the pin shows up as a
    decision rather than as a shard that quietly grades fifteen of seventeen.
    """
    config = yaml.safe_load(FULL_CONFIG_PATH.read_text(encoding="utf-8"))
    identity = config["rerun_identity"]
    pinned = list(identity["task_ids"])
    assert STALLED_TASK_ID in pinned

    common = dict(
        experiment_id=identity["experiment_id"],
        rubric_commit_sha=identity["rubric_commit_sha"],
        inference_revision=identity["inference_revision"],
    )

    s8._validate_pinned_rerun_identity(config, task_ids=pinned, **common)

    without = [task_id for task_id in pinned if task_id != STALLED_TASK_ID]
    with pytest.raises(ValueError, match="pinned rerun identity mismatch"):
        s8._validate_pinned_rerun_identity(config, task_ids=without, **common)

    moved_last = without + [STALLED_TASK_ID]
    assert len(moved_last) == len(pinned)
    with pytest.raises(ValueError, match="mismatch for task_ids"):
        s8._validate_pinned_rerun_identity(config, task_ids=moved_last, **common)


def test_losing_this_task_strands_the_ten_behind_it():
    """Why the loss is eleven tasks and not one.

    The shard is a stride of the pinned list and is graded in that order, so
    every resume meets ``9e39df84`` before anything after it. Six tasks ahead
    of it are done and banked; the ten behind it have never been started.

    This is the number that decides whether the shard is worth another attempt,
    so it is derived from the committed config rather than quoted from a run
    log -- if the stride or the pin ever changes, the figure changes with it.
    """
    config = yaml.safe_load(FULL_CONFIG_PATH.read_text(encoding="utf-8"))
    pinned = list(config["rerun_identity"]["task_ids"])

    shard = pinned[STALLED_TASK_SHARD_INDEX::SHARD_COUNT]
    position = shard.index(STALLED_TASK_ID)

    assert position == 6, (
        f"{STALLED_TASK_ID[:8]} is no longer 7th in shard "
        f"{STALLED_TASK_SHARD_INDEX}; the count of stranded tasks below is stale"
    )
    assert len(shard) - position - 1 == 10, (
        "the number of tasks stranded behind the stalled one has changed"
    )
