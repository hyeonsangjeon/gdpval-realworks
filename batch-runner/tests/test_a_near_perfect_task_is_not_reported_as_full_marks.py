"""The two headline counts have to be reported with the cut-off they used.

``perfect_count`` counts scored tasks at **99% or above** and ``zero_count``
counts those at **1% or below**. Both names promise something stricter than
that, and for a long time every place that printed them repeated the promise
instead of the rule -- the narrative prompt handed a model
``Perfect tasks (100%)`` and ``Zero tasks (0%)``.

Nothing caught it, and nothing could have: the *values* were always right. A
check that recomputes a count agrees with a wrong caption as readily as with a
right one, because the caption is not part of what it compares. It surfaced
only when a person filling in a table opened the source file and found that the
run with ``perfect_count: 3`` contained exactly one task at 100.00% -- the other
two were 99.26% and 99.14%.

The cost of that is not an off-by-two in a log. The narrative section is the
prompt a model reads to write the published report, so ``Perfect tasks (100%):
3/185`` is an instruction to write that three tasks were flawless. The number
came from a real file and the sentence reads well, which is exactly why nobody
downstream would question it.

So the tests below hold the caption and the cut-off together:

* the counters really do take a task that dropped a point, which is what makes
  the old caption false rather than merely imprecise;
* every backend surface that reports the counts states the threshold it used,
  in the same breath, and none of them still claims 100% or 0%;
* and the thresholds each surface quotes are read out of ``step8_grade.py``
  rather than written down here, so moving the cut-off without moving the words
  fails instead of silently recreating the same defect at a new number.

The last one is the guard. The first two would both pass again if someone
changed ``>= 99.0`` to ``>= 100.0`` and left the wording alone.

**Backend only, and deliberately.** The dashboard renames these to
``perfect_score``/``zero_score`` in ``scripts/aggregate-grades.mjs`` and
captions them in ``GradingAnalysisView.tsx``, ``GradesSummary.tsx`` and
``GradeDetail.tsx``; ``src/data/tooltipTexts.ts`` states the defect outright,
in prose, as "Tasks scored 100% ... fully met all rubric criteria". All of that
is still wrong and is owned elsewhere. A green run of this file means the
grade file, its schema and the report prose are honest -- not the screen. Do
not read the name of the test below as wider than it is.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.narrative_analyzer import _build_grading_results_section
from step8_grade import _compute_summary


BATCH_RUNNER = Path(__file__).resolve().parents[1]
STEP8_SRC = (BATCH_RUNNER / "step8_grade.py").read_text(encoding="utf-8")
SCHEMA = json.loads(
    (BATCH_RUNNER / "schemas" / "grade.schema.json").read_text(encoding="utf-8")
)


def _threshold(name: str) -> tuple[str, str]:
    """``('>=', '99')`` -- the rule ``step8_grade`` actually applies.

    Read from source rather than imported, because the counting happens inline
    inside ``_compute_summary`` and there is no constant to import. Reading it
    is the point: these tests are about words agreeing with a number, so the
    number has to come from where the number lives.
    """
    match = re.search(
        rf"^\s*{name}\s*=\s*sum\(1 for x in pcts if x (>=|<=) ([\d.]+)\)$",
        STEP8_SRC,
        re.MULTILINE,
    )
    assert match, (
        f"step8_grade.py no longer computes `{name}` as a one-line threshold "
        "over `pcts`. That is fine, but these tests read the cut-off out of "
        "that line to check the captions quote it -- point them at the new "
        "code in the same change."
    )
    operator, number = match.group(1), match.group(2)
    return operator, f"{float(number):g}"


PERFECT_OP, PERFECT_PCT = _threshold("perfect")
ZERO_OP, ZERO_PCT = _threshold("zero")


def _task(task_id: str, pct: float) -> dict:
    """One scored row, carrying only what the summary reads off it."""
    return {
        "task_id": task_id,
        "pct": pct,
        "sector": "Retail Trade",
        "items": [],
        "usage_complete": True,
    }


@pytest.fixture(scope="module")
def summary() -> dict:
    """A run whose two headline counts are each right for the wrong caption.

    Two tasks land in ``perfect_count`` and only one of them is full marks;
    two land in ``zero_count`` and only one of them is nothing. Both captions
    that name 100% and 0% are therefore false about this run by exactly one
    task each -- the same shape as the 185-task regrade that surfaced this.
    """
    return _compute_summary([
        _task("full-marks", 100.0),
        _task("dropped-a-point", 99.2),
        _task("halfway", 50.0),
        _task("almost-nothing", 0.6),
        _task("nothing", 0.0),
    ])


def test_the_counters_take_a_task_that_did_not_score_full_marks(summary):
    """The premise: these are populations, not exact-value counts.

    If this ever failed, the captions the other tests check would be honest and
    there would be nothing here to guard. It fails first, and loudly, because
    every claim below depends on it.
    """
    compat = summary["openai_compat"]

    assert compat["perfect_count"] == 2, (
        "a 99.2% task is inside `perfect_count`, which is what makes "
        "'Perfect tasks (100%)' a false statement rather than a loose one"
    )
    assert compat["zero_count"] == 2, (
        "a 0.6% task is inside `zero_count` for the same reason"
    )
    assert compat["partial_count"] == 1
    assert (
        compat["perfect_count"] + compat["zero_count"] + compat["partial_count"]
        == summary["graded_tasks"]
    )


def test_the_prompt_hands_the_model_the_rule_and_not_the_name(summary):
    """What a model is told about those two numbers.

    ``_build_grading_results_section`` is rendered straight into the prompt for
    the published report, so whatever it says here is what gets written up.
    """
    section = _build_grading_results_section({"summary": summary})

    perfect_line = next(
        line for line in section.splitlines() if "perfect" in line.lower()
    )
    zero_line = next(
        line for line in section.splitlines()
        if "zero" in line.lower() and "perfect" not in line.lower()
    )

    # The count is still handed over...
    assert "2/5" in perfect_line and "2/5" in zero_line

    # ...with the cut-off that produced it, on the same line, so there is no
    # way to read the number without reading the rule.
    assert f"{PERFECT_OP} {PERFECT_PCT}%" in perfect_line, (
        f"the prompt states a near-perfect count without saying "
        f"'{PERFECT_OP} {PERFECT_PCT}%': {perfect_line!r}"
    )
    assert f"{ZERO_OP} {ZERO_PCT}%" in zero_line, (
        f"the prompt states a near-zero count without saying "
        f"'{ZERO_OP} {ZERO_PCT}%': {zero_line!r}"
    )

    # And the two claims it used to make, which this run disproves by one task
    # each, are gone rather than merely joined by a truthful one.
    assert "(100%)" not in section, (
        "the prompt tells the model 100%, and one of the two tasks it is "
        "counting scored 99.2%"
    )
    assert "Zero tasks (0%)" not in section


@pytest.mark.parametrize(
    "surface",
    ["core/narrative_analyzer.py", "scripts/analyze_gold_ceiling.py"],
)
def test_every_backend_surface_that_prints_the_counts_prints_the_cut_off(surface):
    """Move the threshold and the words have to move with it.

    Both numbers below come from ``step8_grade.py``. Changing ``>= 99.0`` to
    ``>= 100.0`` -- the other fix this defect could have taken -- turns these
    into a demand that the captions say ``100``, so the pair cannot drift apart
    again in either direction.

    The two files parametrized here are every Python surface that prints these
    counts; ``core/grade_payload.py`` also reads them but only by name, with no
    caption to be wrong. The dashboard is a third surface and is not covered --
    see the module docstring.
    """
    source = (BATCH_RUNNER / surface).read_text(encoding="utf-8")

    for field, operator, pct in (
        ("perfect_count", PERFECT_OP, PERFECT_PCT),
        ("zero_count", ZERO_OP, ZERO_PCT),
    ):
        assert field in source, f"{surface} no longer reports {field}"
        # Compared with spaces stripped so `>= 99%` and `>=99%` both count;
        # the surfaces are one prose line and one console column and they
        # format differently on purpose.
        spelled = f"{operator}{pct}%"
        assert spelled in source.replace(" ", ""), (
            f"{surface} reports {field} without stating '{operator} {pct}%'. "
            "The name promises a stricter population than the code counts, so "
            "the threshold has to be printed beside the number."
        )


def test_the_schema_says_what_the_field_holds():
    """The contract, not just the printouts.

    Anyone reading these fields off a grade file reads this description first,
    and it is where a consumer that has not been written yet will look.
    """
    props = SCHEMA["properties"]["summary"]["properties"]["openai_compat"][
        "properties"
    ]

    for field, operator, pct in (
        ("perfect_count", PERFECT_OP, PERFECT_PCT),
        ("zero_count", ZERO_OP, ZERO_PCT),
    ):
        description = props[field].get("description", "")
        assert description, f"grade.schema.json documents no {field}"
        assert f"{operator} {pct}%" in description, (
            f"grade.schema.json describes {field} without its '{operator} "
            f"{pct}%' cut-off, so the file's own contract still implies the "
            "stricter population its name suggests"
        )
