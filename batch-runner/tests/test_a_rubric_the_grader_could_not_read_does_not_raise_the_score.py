"""An item the judge failed on must not make the task score higher.

A rubric item the judge could not decide is marked ``score_excluded``, and
``Grader._aggregate`` then drops it from the numerator *and* the denominator::

    scored_items = [it for it in items if not it.score_excluded]
    total_max = sum(max(0, it.max_score) for it in scored_items)

So the task is scored out of less than its rubric is worth, and the percentage
goes **up** when grading fails. Two tasks that earned identical points report
different scores, and the one whose grading broke reports the better of them.

This is not hypothetical. On the published gold-ceiling cohort, task
``a328feea`` earned 18.6 points against a 24-point rubric. One 2-point item
came back ``judge_error``, so it was scored out of 22 and published **84.55%**
-- where the same 18.6 points out of the whole 24 is **77.50%**. Seven points
of headline, from an item nobody ever read. Across the 185-task corpus,
fourteen tasks carry a denominator that moved this way, and the run summary
said only that ``judge_error_rate`` was nonzero: never that the average had
been lifted by it.

The fix here is *reporting*, not rescoring. Which figure is published is a
decision about the benchmark, not about this function, and it is not made
here. What is made here is the guarantee that the movement is on the record:
``pct_full_denominator`` beside ``pct`` on the task, and
``summary.score_exclusions`` beside the headline on the run. The two
percentages bracket what is actually known -- ``pct`` divides by what was
read, which assumes an unread item would have scored like the rest;
``pct_full_denominator`` divides by the whole rubric, which assumes it would
have scored nothing -- and they are equal whenever the grader got all the way
through, which is what makes a nonzero gap worth looking at.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER))

from core.grader import Grader, ItemGrade
from core.rubric_loader import RubricItem, TaskRubric
from step8_grade import _compute_summary, _score_exclusion_stats


def _rubric(*items: ItemGrade) -> TaskRubric:
    return TaskRubric(
        task_id="t1",
        sector="Retail Trade",
        occupation="Buyer",
        prompt="prompt",
        rubric_items=[
            RubricItem(it.rubric_item_id, it.criterion, it.max_score, None)
            for it in items
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


def _item(item_id, max_score, awarded, verdict="partial") -> ItemGrade:
    return ItemGrade(
        rubric_item_id=item_id,
        criterion=f"criterion {item_id}",
        max_score=max_score,
        awarded_score=awarded,
        verdict=verdict,
        decided_by="judge",
        required=None,
        evidence="e",
    )


def _judge_error(item_id, max_score) -> ItemGrade:
    """An item the judge was asked about and could not answer.

    ``awarded_score`` is 0 because nothing was earned, and ``_aggregate`` is
    what sets ``score_excluded`` -- exactly as it does in the run, where every
    producer of a ``judge_error`` verdict leaves the exclusion to aggregation.
    """
    return _item(item_id, max_score, 0.0, verdict="judge_error")


def _grade(*items: ItemGrade):
    return Grader._aggregate(list(items), _rubric(*items))


# ── the defect, on the task that published it ─────────────────────────────


def test_the_same_points_do_not_become_a_better_score(tmp_path):
    """``a328feea``: 18.6 of 24, one 2-point item unread, published 84.55%.

    Both halves are asserted. ``pct`` still reports what it has always
    reported, because changing it is the owner's call and a silent rescoring
    would be the same failure in the other direction. What is new is that the
    task now also carries the number that says what the 84.55% was measured
    against.
    """
    read = [_item("r1", 22, 18.6)]
    unread = _judge_error("r2", 2)

    complete = _grade(*read, _item("r2", 2, 0.0, verdict="fail"))
    broken = _grade(*read, unread)

    # Identical work, identical points.
    assert complete.total_awarded == broken.total_awarded == 18.6

    # And the one whose grading broke reports the better score.
    assert broken.pct == 84.55
    assert complete.pct == 77.5
    assert broken.pct > complete.pct

    # That is what the new field is for: it puts the honest denominator back.
    assert broken.pct_full_denominator == 77.5
    assert broken.pct_full_denominator == complete.pct
    assert broken.score_excluded_items == 1
    assert broken.score_excluded_max == 2


def test_a_rubric_that_was_read_to_the_end_reports_one_number(tmp_path):
    """No exclusions, no gap -- so a gap always means something happened.

    The metric is only useful if it is silent on a clean task. If
    ``pct_full_denominator`` drifted from ``pct`` by a rounding artefact, a
    reader could not use "these differ" as the signal.
    """
    grade = _grade(_item("r1", 63, 42), _item("r2", 7, 7))
    assert grade.score_excluded_items == 0
    assert grade.score_excluded_max == 0
    assert grade.pct == grade.pct_full_denominator == 70.0


def test_the_vanished_weight_is_the_size_of_what_was_not_read(tmp_path):
    """``score_excluded_max`` is the movement itself, not a count.

    Three unread items worth one point each cost a task far less than one
    unread item worth thirty, and a count cannot tell those apart. On the real
    corpus this matters: task ``f1be6436`` lost 29 points of rubric to
    exclusions against 45 that were read, and reported 54.22% where the full
    74 gives 32.97%.
    """
    grade = _grade(
        _item("r1", 45, 24.4),
        _judge_error("r2", 20),
        _judge_error("r3", 9),
    )
    assert grade.score_excluded_items == 2
    assert grade.score_excluded_max == 29
    assert grade.total_max == 45
    assert grade.pct == 54.22
    assert grade.pct_full_denominator == 32.97


# ── the cases where an exclusion is not an inflation ──────────────────────


def test_a_task_that_earned_nothing_is_not_flattered_by_an_exclusion(tmp_path):
    """Zero over a smaller denominator is still zero.

    Worth pinning because it is the common case in the published data and the
    reason two whole grade files show a lift of exactly 0.00 despite twelve
    excluded items each: every task that lost an item had also scored nothing.
    A metric that reported inflation there would be crying wolf on the runs
    that need it least.
    """
    grade = _grade(_item("r1", 54, 0.0, verdict="fail"), _judge_error("r2", 5))
    assert grade.score_excluded_max == 5
    assert grade.pct == 0.0
    assert grade.pct_full_denominator == 0.0


def test_a_penalty_item_adds_nothing_to_the_denominator(tmp_path):
    """Negative-weight rubric items are floored, as they are in ``total_max``.

    GDPVal rubrics carry anti-criteria with negative ``max_score``. They have
    never contributed to the denominator, so an unread one must not start
    contributing to it now -- a negative addend would *shrink* the full
    denominator and invent inflation that never happened.
    """
    grade = _grade(
        _item("r1", 20, 15.0),
        _judge_error("r2", -6),
    )
    assert grade.score_excluded_items == 1
    assert grade.score_excluded_max == 0
    assert grade.pct == grade.pct_full_denominator == 75.0


def test_a_task_the_grader_never_got_into_is_still_an_error(tmp_path):
    """Every item excluded is a task that leaves the average, as before.

    The new fields must not turn an ungradeable task into a 0% one: that would
    move it back into the corpus mean under a score nobody measured.
    """
    grade = _grade(_judge_error("r1", 10), _judge_error("r2", 5))
    assert grade.error == "all_items_score_excluded"
    assert grade.total_max == 0
    assert grade.score_excluded_items == 2
    assert grade.score_excluded_max == 15
    # No positive weight was read, so there is no ratio to report.
    assert grade.pct == 0.0


def test_a_degenerate_rubric_does_not_divide_by_zero(tmp_path):
    """No positive weight anywhere, read or unread."""
    grade = _grade(_judge_error("r1", 0), _item("r2", 0, 0.0, verdict="fail"))
    assert grade.pct_full_denominator == 0.0


def test_a_task_that_went_below_zero_is_not_reported_as_negative(tmp_path):
    """Real: ``6074bba3`` earned **-5.5** of 50, with a -10 item unread.

    Penalties can take a task below zero, and ``pct`` has always clamped that
    to 0.0 -- which is what the corpus published for this task. The
    full-denominator figure has to clamp with it. Unclamped the same numbers
    give **-11.0%**, a percentage no rubric can produce and no reader could
    place beside a 0.0%; it would also read as "the exclusion cost this task
    11 points" when the exclusion cost it nothing at all.
    """
    grade = _grade(_item("r1", 50, -5.5, verdict="fail"), _judge_error("r2", -10))
    assert grade.total_max == 50
    assert grade.total_awarded == -5.5
    assert grade.score_excluded_items == 1
    assert grade.score_excluded_max == 0  # a penalty adds no weight to read
    assert grade.pct == 0.0
    assert grade.pct_full_denominator == 0.0

    # And the same clamp on the summary side, which sees payload dicts.
    stats = _score_exclusion_stats(
        [_task_dict("6074bba3", -5.5, 50,
                    [_payload_item(50), _payload_item(-10, excluded=True)])],
        avg_pct=0.0,
    )
    assert stats["avg_score_pct_full_denominator"] == 0.0
    assert stats["avg_score_pct_lift"] == 0.0


# ── the run summary ───────────────────────────────────────────────────────


def _task_dict(task_id, awarded, total_max, items, *, error=None):
    """One task as the grade payload carries it, not as a dataclass.

    ``_score_exclusion_stats`` reads published payloads -- including ones
    written before any of these fields existed -- so it is exercised through
    the shape it actually receives.
    """
    pct = max(0.0, min(100.0, (awarded / total_max * 100.0) if total_max else 0.0))
    return {
        "task_id": task_id,
        "sector": "Retail Trade",
        "pct": round(pct, 2),
        "total_awarded": awarded,
        "total_max": total_max,
        "error": error,
        "items": items,
    }


def _payload_item(max_score, *, excluded=False):
    return {
        "max_score": max_score,
        "score_excluded": excluded,
        "verdict": "judge_error" if excluded else "pass",
        "decided_by": "judge",
    }


def test_a_clean_run_reports_a_lift_of_exactly_zero():
    """The headline needs no caveat, and the run says so in as many words."""
    stats = _score_exclusion_stats(
        [
            _task_dict("a", 42, 84, [_payload_item(84)]),
            _task_dict("b", 10, 10, [_payload_item(10)]),
        ],
        avg_pct=75.0,
    )
    assert stats["tasks_with_excluded_items"] == 0
    assert stats["excluded_items"] == 0
    assert stats["excluded_max_score"] == 0
    assert stats["avg_score_pct_lift"] == 0.0
    assert stats["avg_score_pct_full_denominator"] == 75.0


def test_the_run_says_how_much_of_its_headline_was_never_read():
    """One inflated task among two, and the average carries half its lift.

    ``a328feea`` at 84.55% averaged with a clean 50.00% reports 67.28%; on the
    full denominator the pair is 63.75%. The 3.53-point gap is the number that
    had nowhere to live before this.
    """
    stats = _score_exclusion_stats(
        [
            _task_dict(
                "a328feea", 18.6, 22,
                [_payload_item(22), _payload_item(2, excluded=True)],
            ),
            _task_dict("clean", 5, 10, [_payload_item(10)]),
        ],
        avg_pct=67.28,
    )
    assert stats["tasks_with_excluded_items"] == 1
    assert stats["excluded_items"] == 1
    assert stats["excluded_max_score"] == 2
    assert stats["avg_score_pct_full_denominator"] == 63.75
    assert stats["avg_score_pct_lift"] == 3.53


def test_the_summary_recomputes_from_items_not_from_the_new_field():
    """A grade file written before this change must report the same numbers.

    Every published grade predates the per-task ``pct_full_denominator``, and
    they are re-summarised on every shard merge. Reading the field instead of
    the items would make the merged summary of an old run silently claim the
    run was clean.
    """
    legacy = _task_dict(
        "a328feea", 18.6, 22,
        [_payload_item(22), _payload_item(2, excluded=True)],
    )
    assert "pct_full_denominator" not in legacy
    stats = _score_exclusion_stats([legacy], avg_pct=84.55)
    assert stats["avg_score_pct_full_denominator"] == 77.5
    assert stats["avg_score_pct_lift"] == 7.05


def test_the_block_reaches_the_published_summary():
    """Through ``_compute_summary``, which is what shard merges rebuild.

    Also pins that the block sits beside ``openai_compat`` rather than inside
    it: that object is a fixed compatibility shape, and a caveat on its
    headline is not another field of it.
    """
    summary = _compute_summary([
        _task_dict(
            "a328feea", 18.6, 22,
            [_payload_item(22), _payload_item(2, excluded=True)],
        ),
        _task_dict("clean", 5, 10, [_payload_item(10)]),
    ])
    assert summary["openai_compat"]["avg_score_pct"] == 67.28
    assert "score_exclusions" not in summary["openai_compat"]
    block = summary["score_exclusions"]
    assert block["avg_score_pct_full_denominator"] == 63.75
    assert block["avg_score_pct_lift"] == 3.53


def test_a_task_that_lost_every_item_is_not_counted_twice():
    """It already left the average; it must not also be an inflated member.

    ``_compute_summary`` averages the tasks without an ``error``, and an
    all-excluded task carries ``all_items_score_excluded``. Counting its
    exclusions among the ones that moved a published denominator would inflate
    the caveat instead of the score.
    """
    summary = _compute_summary([
        _task_dict("clean", 5, 10, [_payload_item(10)]),
        _task_dict(
            "gone", 0, 0,
            [_payload_item(30, excluded=True)],
            error="all_items_score_excluded",
        ),
    ])
    assert summary["graded_tasks"] == 1
    assert summary["error_tasks"] == 1
    block = summary["score_exclusions"]
    assert block["tasks_with_excluded_items"] == 0
    assert block["excluded_max_score"] == 0
    assert block["avg_score_pct_lift"] == 0.0


def test_a_run_with_no_scored_tasks_reports_nothing_rather_than_zero():
    """An empty average is ``None``, not 0.0.

    0.0 here would read as "this run scored zero on the full denominator",
    which is a measurement nobody took.
    """
    summary = _compute_summary([
        _task_dict("gone", 0, 0, [_payload_item(5, excluded=True)],
                   error="all_items_score_excluded"),
    ])
    assert summary["openai_compat"]["avg_score_pct"] is None
    block = summary["score_exclusions"]
    assert block["avg_score_pct_full_denominator"] is None
    assert block["avg_score_pct_lift"] is None


# ── the schema ────────────────────────────────────────────────────────────


def test_the_published_shape_documents_all_of_it():
    """Both objects are ``additionalProperties: true``, so nothing here is
    enforced by validation -- which is exactly why it is asserted.

    A field that validates whatever it is given is a field whose meaning lives
    only in its description. If the description goes, the number becomes
    unreadable while every test still passes.
    """
    import json

    schema = json.loads(
        (BATCH_RUNNER / "schemas" / "grade.schema.json").read_text("utf-8")
    )
    task_props = schema["properties"]["tasks"]["items"]["properties"]
    for field_name in (
        "score_excluded_items", "score_excluded_max", "pct_full_denominator"
    ):
        assert field_name in task_props, field_name
        assert task_props[field_name].get("description"), field_name

    block = schema["properties"]["summary"]["properties"]["score_exclusions"]
    assert block.get("description")
    for field_name in (
        "tasks_with_excluded_items",
        "excluded_items",
        "excluded_max_score",
        "avg_score_pct_full_denominator",
        "avg_score_pct_lift",
    ):
        assert block["properties"][field_name].get("description"), field_name
