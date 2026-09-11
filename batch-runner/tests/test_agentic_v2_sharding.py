"""Running one stage in several pieces, without the pieces becoming the stage.

The split itself is four lines of arithmetic and would not be worth a test file.
What is worth one is everything around it, because each of these failures is
silent — a sharded run that is wrong still finishes, still writes results, and
still prints a number:

* a piece that is empty, or that does not exist, and reports success anyway;
* pieces that were cut from different splits and are then added together;
* a task that two pieces both ran, which is a task paid for twice;
* a task no piece ran, in a set that otherwise looks complete;
* a caller that passes ``--shard`` without meaning to shard anything, and gets
  different behaviour for it.

The last one is why ``1/1`` is ``None`` rather than a one-of-one shard: a
workflow should be able to always pass the argument.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_sharding import (  # noqa: E402
    Shard,
    ShardRefused,
    coverage_problems,
    how_many_shards_fit,
    parse,
    shard_of,
    split,
)

#: Short enough to check by eye, which matters for the stride tests — a stride
#: split is easy to assert vacuously against ids you cannot hold in your head.
COHORT = ("a", "b", "c", "d", "e", "f", "g")


# ── The split ─────────────────────────────────────────────────────────────


def test_the_split_deals_the_cohort_out_rather_than_cutting_it_into_blocks():
    """Stride, not block. Which tasks land together is the whole difference.

    The cohort is ordered by a selection rule that puts related work next to
    each other, so a block shard is a run of one kind of task. Lose it and what
    is missing from the partial result is a category; lose a stride shard and
    what is missing is a thin slice of everything.
    """
    assert split(COHORT, 3) == (("a", "d", "g"), ("b", "e"), ("c", "f"))


def test_every_task_lands_in_exactly_one_piece():
    for pieces in range(1, len(COHORT) + 1):
        dealt = [task for piece in split(COHORT, pieces) for task in piece]
        assert sorted(dealt) == sorted(COHORT), pieces
        assert len(dealt) == len(set(dealt)), pieces


def test_a_split_that_would_leave_a_piece_empty_is_refused():
    """An empty run that reports success is worse than one that will not start.

    It is worse because it is counted. A shard that ran nothing and exited zero
    is indistinguishable, in every summary above it, from a shard that ran its
    tasks and they all passed.
    """
    with pytest.raises(ShardRefused) as refused:
        split(COHORT, len(COHORT) + 1)

    assert "without leaving some piece empty" in str(refused.value)


def test_fewer_than_one_piece_is_refused():
    with pytest.raises(ShardRefused):
        split(COHORT, 0)


def test_a_piece_is_reproducible_from_the_cohort_and_its_two_numbers():
    """Nothing about a split is stored, so nothing about it can go stale.

    A shard that had to be looked up somewhere would be one more record that can
    disagree with the cohort it came from.
    """
    assert shard_of(COHORT, 2, 3).task_ids == ("b", "e")
    assert shard_of(COHORT, 2, 3).task_ids == split(COHORT, 3)[1]


def test_a_shard_that_does_not_exist_is_refused_by_number():
    for index in (0, 4, -1):
        with pytest.raises(ShardRefused) as refused:
            shard_of(COHORT, index, 3)
        assert "shards are numbered 1 to 3" in str(refused.value)


# ── What a shard admits to being ──────────────────────────────────────────


def test_the_record_carries_the_whole_it_is_a_piece_of():
    """Task ids with no denominator read as a small experiment, not a fragment."""
    written = shard_of(COHORT, 1, 3).as_dict()

    assert written["task_count"] == 3
    assert written["cohort_size"] == 7
    assert written["covers_whole_stage"] is False
    assert "The stage has not run until all 3 shards have" in written["what_this_run_is"]


def test_a_single_piece_says_it_is_the_whole_stage():
    written = Shard(index=1, of=1, task_ids=COHORT, cohort_size=7).as_dict()

    assert written["covers_whole_stage"] is True
    assert written["what_this_run_is"] == "the whole stage, in one run"


# ── Parsing what a person typed into a workflow input ─────────────────────


@pytest.mark.parametrize("text", [None, "", "   ", "all", "1/1"])
def test_not_sharding_gives_back_nothing_rather_than_a_trivial_shard(text):
    """So a workflow may always pass --shard without changing what happens.

    ``None`` rather than a one-of-one shard because the alternative is a second
    code path that only runs in production: every unsharded run would start
    going through shard handling on the day the option was added.
    """
    assert parse(text, COHORT) is None


def test_a_total_of_one_is_the_unsharded_run_however_it_is_written():
    assert parse("1/1", COHORT) is None


@pytest.mark.parametrize("text", ["3", "3 of 20", "three/twenty", "3/", "/20"])
def test_something_that_is_not_a_shard_is_refused_with_the_shape_to_use(text):
    with pytest.raises(ShardRefused) as refused:
        parse(text, COHORT)

    assert "Write it as index/total" in str(refused.value)


def test_whitespace_around_the_numbers_is_not_a_refusal():
    """People paste these. A trailing space is not a reason to lose a paid run."""
    assert parse(" 2 / 3 ", COHORT).task_ids == ("b", "e")


# ── How many pieces the place this runs will actually hold ────────────────


def test_the_count_is_sized_against_the_worst_case_and_not_the_usual_one():
    """Every task assumed to take its full timeout.

    Sizing against what most tasks do is how a job gets killed at hour six with
    nothing collected — the tail is exactly where the long tasks are.
    """
    # Six hours × 0.75 = 16200s of usable time, 13 tasks of 1200s each.
    assert how_many_shards_fit(
        cohort_size=13, per_task_timeout_seconds=1200, job_limit_seconds=21600
    ) == 1
    assert how_many_shards_fit(
        cohort_size=14, per_task_timeout_seconds=1200, job_limit_seconds=21600
    ) == 2


def test_the_three_real_stages_get_the_counts_the_workflow_is_built_around():
    """These are the numbers in the workflow matrix, so they are held here.

    If the timeout or the job limit moves, this is where it should be noticed —
    not in a run that gets killed.
    """
    fits = lambda size: how_many_shards_fit(
        cohort_size=size, per_task_timeout_seconds=1200, job_limit_seconds=21600
    )
    assert fits(5) == 1
    assert fits(30) == 3
    assert fits(220) == 17


def test_a_task_that_cannot_fit_in_a_job_at_all_is_refused_rather_than_rounded():
    """No number of pieces fixes one task that outlasts the job it runs in.

    Returning a very large count would be arithmetically fine and practically a
    lie: each of those pieces would still be killed.
    """
    with pytest.raises(ShardRefused) as refused:
        how_many_shards_fit(
            cohort_size=10, per_task_timeout_seconds=1200, job_limit_seconds=1000
        )

    assert "no split makes this fit" in str(refused.value)


def test_a_cohort_with_no_tasks_is_refused():
    with pytest.raises(ShardRefused):
        how_many_shards_fit(
            cohort_size=0, per_task_timeout_seconds=1200, job_limit_seconds=21600
        )


# ── Earning the sentence "the stage ran" ──────────────────────────────────


def test_a_complete_set_of_pieces_has_nothing_wrong_with_it():
    whole = [shard_of(COHORT, index, 3) for index in (1, 2, 3)]

    assert coverage_problems(whole, task_ids=COHORT) == []


def test_no_shard_at_all_is_reported_rather_than_passing_as_complete():
    """The empty set satisfies "every shard that ran covered its tasks"."""
    assert coverage_problems([], task_ids=COHORT) == [
        "no shard ran, so the stage did not run"
    ]


def test_a_missing_piece_is_named_by_number():
    assert "did not run: 2" in " ".join(
        coverage_problems(
            [shard_of(COHORT, 1, 3), shard_of(COHORT, 3, 3)], task_ids=COHORT
        )
    )


def test_pieces_cut_from_different_splits_are_refused_before_being_added_up():
    """Seventeen-way and twenty-way shards are not pieces of the same thing.

    Reported and then stopped, because every later check compares against a
    total that does not exist. This is the shape a re-dispatch takes after
    somebody changes the matrix size mid-stage.
    """
    problems = coverage_problems(
        [shard_of(COHORT, 1, 3), shard_of(COHORT, 1, 2)], task_ids=COHORT
    )

    assert len(problems) == 1
    assert "disagree about how many there are" in problems[0]
    assert "cannot be added up" in problems[0]


def test_a_task_two_pieces_both_ran_is_reported_as_paid_for_twice():
    """Counting would not catch it. This is why coverage is checked by identity.

    Two overlapping shards can report the right total number of tasks between
    them while one task ran twice and another never ran.
    """
    overlapping = [
        Shard(index=1, of=2, task_ids=("a", "b", "c", "d"), cohort_size=7),
        Shard(index=2, of=2, task_ids=("d", "e", "f", "g"), cohort_size=7),
    ]

    trouble = " ".join(coverage_problems(overlapping, task_ids=COHORT))

    assert "1 tasks were covered by more than one shard" in trouble
    assert "paid for twice" in trouble


def test_a_task_no_piece_ran_is_reported_even_when_every_piece_did():
    short = [
        Shard(index=1, of=2, task_ids=("a", "b", "c"), cohort_size=7),
        Shard(index=2, of=2, task_ids=("d", "e", "f"), cohort_size=7),
    ]

    trouble = " ".join(coverage_problems(short, task_ids=COHORT))

    assert "1 of the 7 tasks in this stage were covered by no shard: g" in trouble


def test_a_task_from_outside_the_stage_is_reported_rather_than_counted_in():
    """A result set that silently gained a task is not this stage's result.

    The count would be right, and the cohort seal it is quoted under would not
    describe what ran.
    """
    strayed = [
        Shard(index=1, of=1, task_ids=COHORT + ("z",), cohort_size=7),
    ]

    trouble = " ".join(coverage_problems(strayed, task_ids=COHORT))

    assert "1 tasks were run that are not in this stage: z" in trouble
