"""A task that could not afford its pictures has to leave a number behind.

The visual call cap is per task. A task that wants more renders than it may
spend first gives up the escalation that exists only for unreadable files,
and if that still does not fit, every item that wanted a picture is excluded.
A task with nothing left to score is then *dropped*: ``_aggregate`` sets
``all_items_score_excluded``, ``_compute_summary`` averages only tasks
without an ``error``, and the corpus quietly becomes 184 tasks. A corpus of
184 looks exactly like a corpus. That is how Stage 3 lost task ``43dc9778``,
a 67-item task scoring 87%, to 134 renders against a cap of 72.

Two things were already true before this file and neither was enough. The
grader recorded the shortfall per item, truncated into ``evidence``, which is
not somewhere anybody reads a run off; and it recorded
``visual_budget_fallback`` on the tasks it *rescued*, so the case that cost
the most was the one that said the least. Nothing rolled either up. A run
that had silently dropped a task was byte-indistinguishable from a clean one
without opening every task object by hand.

So the claim under test is narrow and it is about the summary:
``summary.visual_budget`` reports what the cap cost this run, counted over
every task rather than the scored ones -- because the task worth counting is
precisely the one that is no longer scored.

What this file does not cover: that ``grade_task`` sets the task-level
fields at all. That is behaviour, it needs the grader harness, and it lives
in ``test_grader_selector_integration.py`` beside the four scenarios that
already build each budget state. Hand-built task dicts here would happily
agree with a grader that never set the field. Read a green run of this file
as "the rollup is right", not "the source is".
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft7Validator

from core.grader import Grader, _RuntimeCriterionPlan
from step8_grade import _compute_summary, _visual_budget_figures


BATCH_RUNNER = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (BATCH_RUNNER / "schemas" / "grade.schema.json").read_text(encoding="utf-8")
)


def _marker(required: int, cap: int) -> str:
    """The real shortfall string, from the code that writes it in production.

    Deliberately not a literal. ``_visual_budget_stats`` reads its figures
    back out with a regex, and a regex over another module's wording fails
    *quietly*: reword the producer and ``max_required_calls`` becomes ``None``
    while ``tasks_over_cap`` keeps counting, so the summary under-reports
    without a single test going red. Generating the input from the producer
    is what converts that silence into a failure.

    Only ``supported_visual_call_count`` is read off the plans, so the rest of
    the plan is left unfilled rather than faked into something plausible.
    """
    grader = Grader.__new__(Grader)
    grader._tool_judge = SimpleNamespace(
        vision_perception=SimpleNamespace(call_cap=cap)
    )
    plans = [
        _RuntimeCriterionPlan(
            target_plan=None,
            item_decision=None,
            target_decisions={},
            visual_paths=(),
            visual_preflight_error=None,
            supported_visual_call_count=required,
            requires_visual=True,
        )
    ]
    marker = grader._task_visual_budget_error(plans)
    assert marker is not None, (
        f"Grader._task_visual_budget_error no longer reports {required} "
        f"renders against a cap of {cap} as over budget. If the rule moved, "
        "move this helper with it -- every count below is built on it."
    )
    return marker


def _task(
    task_id: str,
    *,
    pct: float = 80.0,
    error: str | None = None,
    fallback: str | None = None,
    unmet: str | None = None,
    items_downgraded: int = 0,
    items_plain: int = 0,
) -> dict:
    """One task row carrying only what the summary reads off it."""
    return {
        "task_id": task_id,
        "sector": "Finance and Insurance",
        "pct": pct,
        "error": error,
        "visual_budget_fallback": fallback,
        "visual_budget_unmet": unmet,
        "items": (
            [{"visual_budget_downgraded": True} for _ in range(items_downgraded)]
            + [{"visual_budget_downgraded": False} for _ in range(items_plain)]
        ),
        "usage_complete": True,
    }


def test_the_shortfall_the_summary_parses_is_the_one_the_grader_writes():
    """The seam between the two modules, checked at the seam.

    ``134`` and ``72`` are task 43dc9778's real figures.
    """
    assert _visual_budget_figures(_marker(134, 72)) == (134, 72)


def test_a_figureless_marker_is_not_read_as_zero():
    """An unparseable marker must yield nothing, never a number.

    A cap silently reported as 0 renders is worse than a cap reported as
    unknown: it reads as a run that was configured to render nothing.
    """
    assert _visual_budget_figures("task_visual_budget_exceeded") is None
    assert _visual_budget_figures(None) is None
    assert _visual_budget_figures(True) is None


def test_a_dropped_task_is_counted_where_no_other_summary_field_can_see_it():
    """The whole point, stated as a contrast.

    One task of three is over budget with nothing to give up, so it excludes
    every item and leaves the average. Every other part of the summary either
    cannot see it or files it under something else -- `error_tasks` puts it
    beside tasks that broke for unrelated reasons, and `score_exclusions`
    counts only tasks the headline averages, which this one no longer is.
    """
    summary = _compute_summary([
        _task("clean-a", pct=90.0, items_plain=3),
        _task("clean-b", pct=70.0, items_plain=3),
        _task(
            "dropped",
            pct=0.0,
            error="all_items_score_excluded",
            unmet=_marker(134, 72),
        ),
    ])

    assert summary["graded_tasks"] == 2, "the dropped task is out of the mean"
    assert summary["error_tasks"] == 1
    assert summary["score_exclusions"]["tasks_with_excluded_items"] == 0, (
        "`score_exclusions` reports on tasks the headline averages, so it is "
        "blind to this one by construction -- which is why the count below "
        "cannot be folded into it"
    )

    budget = summary["visual_budget"]
    assert budget["tasks_unmet"] == 1
    assert budget["tasks_over_cap"] == 1
    assert budget["max_required_calls"] == 134
    assert budget["call_cap"] == 72


def test_a_task_graded_without_the_pictures_it_asked_for_is_counted_too():
    """The other half: the cost that *is* absorbed into the average.

    This task scores and its score enters the headline like any other. What
    the headline cannot say is that two of its verdicts were reached on text
    where a picture was wanted. The count says it.
    """
    summary = _compute_summary([
        _task("clean", pct=90.0, items_plain=2),
        _task(
            "rescued",
            pct=85.0,
            fallback=_marker(4, 1),
            items_downgraded=2,
            items_plain=1,
        ),
    ])

    assert summary["graded_tasks"] == 2, (
        "the rescued task scores -- that is the point of rescuing it, and the "
        "reason its cost needs saying out loud somewhere else"
    )
    budget = summary["visual_budget"]
    assert budget["tasks_downgraded"] == 1
    assert budget["tasks_unmet"] == 0
    assert budget["tasks_over_cap"] == 1
    assert budget["items_downgraded"] == 2


def test_a_task_narrowed_but_still_short_is_in_both_counts_and_one_total():
    """The overlap is deliberate, so pin it.

    ``_relax_to_fit_visual_budget`` returns the original shortfall *and* the
    one that still stands when giving up pictures helped without being
    enough. Both fields are set on such a task. It is one task over the cap,
    counted once there and once in each of the two things that happened to
    it, so the two do not sum to the total and must not be made to.
    """
    summary = _compute_summary([
        _task(
            "narrowed-still-short",
            pct=60.0,
            fallback=_marker(4, 1),
            unmet=_marker(2, 1),
            items_downgraded=2,
            items_plain=1,
        ),
    ])

    budget = summary["visual_budget"]
    assert budget["tasks_over_cap"] == 1
    assert budget["tasks_downgraded"] == 1
    assert budget["tasks_unmet"] == 1
    assert budget["tasks_downgraded"] + budget["tasks_unmet"] == 2, (
        "these overlap on one task, so their sum exceeding `tasks_over_cap` "
        "is correct -- do not reconcile it by making them exclusive"
    )


def test_a_run_that_never_came_near_the_cap_says_zero_rather_than_nothing():
    """The ordinary case has to be readable as ordinary.

    Zero is a claim. Absent figures are not a claim, and this is exactly the
    condition under which they are absent: a demand that was met is recorded
    nowhere, so there is no ``max_required_calls`` to report and pretending
    otherwise would be inventing one.
    """
    summary = _compute_summary([
        _task("clean-a", pct=90.0, items_plain=3),
        _task("clean-b", pct=70.0, items_plain=2),
    ])

    assert summary["visual_budget"] == {
        "tasks_over_cap": 0,
        "tasks_downgraded": 0,
        "tasks_unmet": 0,
        "items_downgraded": 0,
        "max_required_calls": None,
        "call_cap": None,
    }


def test_the_headroom_reported_is_the_worst_demand_in_the_run():
    """One task at the cap tells you nothing; the worst one tells you how far.

    Three tasks over budget at different demands. The figure that matters for
    deciding whether the cap is the right number is the largest, not the last
    one written.
    """
    summary = _compute_summary([
        _task("over-a", error="all_items_score_excluded", unmet=_marker(80, 72)),
        _task("over-b", error="all_items_score_excluded", unmet=_marker(134, 72)),
        _task("over-c", error="all_items_score_excluded", unmet=_marker(95, 72)),
    ])

    budget = summary["visual_budget"]
    assert budget["tasks_over_cap"] == 3
    assert budget["max_required_calls"] == 134
    assert budget["call_cap"] == 72


def test_an_older_grade_file_re_summarises_without_the_new_fields():
    """Tasks graded before these fields existed carry neither.

    ``step9_merge_shards`` recomputes the summary from the merged task list,
    so this is the shape a resumed or re-summarised historical run presents.
    It must read as "no budget trouble recorded", not raise.
    """
    legacy = {
        "task_id": "graded-last-month",
        "sector": "Finance and Insurance",
        "pct": 88.0,
        "items": [{}, {}],
        "usage_complete": True,
    }

    budget = _compute_summary([legacy])["visual_budget"]

    assert budget["tasks_over_cap"] == 0
    assert budget["max_required_calls"] is None


@pytest.mark.parametrize(
    "field",
    ["tasks_over_cap", "tasks_downgraded", "tasks_unmet", "items_downgraded",
     "max_required_calls", "call_cap"],
)
def test_the_schema_documents_every_field_the_summary_emits(field):
    """A number nobody can interpret is not much better than no number."""
    properties = SCHEMA["properties"]["summary"]["properties"]["visual_budget"][
        "properties"
    ]
    assert field in properties, f"grade.schema.json documents no {field}"
    assert properties[field].get("description"), (
        f"grade.schema.json declares {field} without saying what it means"
    )


def test_the_schema_accepts_a_grade_file_carrying_the_new_fields():
    """Emitting a field the schema rejects fails the run at validation."""
    summary = _compute_summary([
        _task("clean", pct=90.0, items_plain=2),
        _task(
            "narrowed-still-short",
            pct=60.0,
            fallback=_marker(4, 1),
            unmet=_marker(2, 1),
            items_downgraded=2,
        ),
    ])
    validator = Draft7Validator(SCHEMA)

    errors = [
        error
        for error in validator.iter_errors({"summary": summary})
        if "visual_budget" in list(error.absolute_path)
    ]

    assert errors == [], f"schema rejects its own summary: {errors}"
