"""The zero that means "nobody looked", published where "they agreed" is read.

``summary.openai_compat.inconsistent_count`` is a required integer and it is
the literal ``0`` in ``step8_grade.py``. All ninety-four committed payloads
carry it. The dashboard turns it into ``inconsistent_grades`` and captions it
*"Multiple graders scored the same task differently"*, rendering ``0`` and
``0.0%``.

There has never been a second grader. Each task is graded once, and
``step9_merge_shards`` refuses shards that are not disjoint, so a payload
cannot even hold one task twice. The number was not measured to be zero; there
was nothing to measure.

What makes that worth a test rather than a comment is the direction. This
repository has already graded the same thirty answers three times at one
fingerprint, and the three runs are committed. Pool them and **29 of the 30
tasks scored differently**, the widest single task swinging 7.05 points -- and
each of those three payloads reports ``inconsistent_count: 0`` about itself.
So the published zero is not an unexamined guess that happens to be harmless.
It is the reassuring answer to a question whose real answer is known, sitting
in the field a reader would check to find out whether to trust the grader.

The integer stays. Ninety-four payloads carry it, and both
``core/grade_payload.py`` and ``scripts/aggregate-grades.mjs`` recognise a stub
payload by ``inconsistent_count != 0``; moving it would invalidate the record
to fix a caption. What this file pins is the basis published beside it --
``summary.grader_agreement`` -- and above all that ``tasks_that_moved`` is
``None`` and never ``0`` when nothing was compared.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from step8_grade import _compute_summary, _grader_agreement_stats


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = Path(__file__).resolve().parents[1]
GRADES_ROOT = REPO_ROOT / "data/grades"
SCHEMA = BATCH_RUNNER / "schemas/grade.schema.json"

#: The thirty-task cohort graded three times at one grader fingerprint, found
#: by the corpus fingerprint its payloads carry rather than by path -- the
#: three live in different directories and their filenames encode hashes.
REPEAT_COHORT_FINGERPRINT = (
    "82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b"
)

#: ...and at ONE grader source hash. A fourth payload of the same thirty tasks
#: sits in ``_superseded`` at ``8513975c...``, and pooling it in would measure
#: the distance between two graders rather than one grader's distance from
#: itself. That is the comparison the repeat preregistration exists to keep
#: apart, and it shows: adding it moves the widest swing from 7.05 to 79.29.
GRADER_SOURCE_HASH = (
    "c33d9d55703fbf5de5f988d427e34efd44d7a73306412caac88a753bad16ff4e"
)

# ── measured across those three runs, pinned ─────────────────────────
REPEAT_RUNS = 3
COHORT_TASKS = 30
TASKS_THAT_MOVED = 29
WIDEST_SWING_PP = 7.05


def _task(task_id: str, pct: float | None) -> dict:
    return {"task_id": task_id, "pct": pct, "items": []}


# ── nothing was compared ─────────────────────────────────────────────


def test_an_ordinary_run_says_it_compared_nothing() -> None:
    """One grading per task is no basis for a disagreement count.

    ``gradings_per_task: 1`` is the whole of it: there is no pair of verdicts
    anywhere in such a payload, so the ``0`` beside it cannot be a finding
    about whether verdicts agree.
    """
    stats = _grader_agreement_stats([_task("a", 50.0), _task("b", 60.0)])

    assert stats["compared"] is False
    assert stats["gradings_per_task"] == 1
    assert stats["tasks_compared"] == 0


def test_nothing_compared_reports_none_and_not_zero() -> None:
    """The load-bearing line of this file.

    A ``0`` here would say "we compared and found no disagreement" about a run
    that compared nothing -- the same substitution the neighbouring
    ``inconsistent_count`` already makes, and in the same reassuring
    direction. Reproducing it in the field added to explain it would leave the
    record no better off than before.
    """
    stats = _grader_agreement_stats([_task("a", 50.0)])

    assert stats["tasks_that_moved"] is None
    assert stats["max_spread_pp"] is None
    assert stats["tasks_that_moved"] != 0  # None is not 0; that is the point


def test_an_empty_run_has_not_compared_anything_either() -> None:
    stats = _grader_agreement_stats([])

    assert stats["compared"] is False
    assert stats["gradings_per_task"] == 0
    assert stats["tasks_that_moved"] is None


# ── something was compared ───────────────────────────────────────────


def test_two_gradings_of_one_task_are_actually_compared() -> None:
    """The branch that is not reachable through today's pipeline, and is not
    therefore hypothetical: it is what makes the ``False`` above a finding
    about the pipeline rather than an assumption baked into the summariser.
    """
    stats = _grader_agreement_stats(
        [_task("a", 50.0), _task("a", 52.5), _task("b", 60.0), _task("b", 60.0)]
    )

    assert stats["compared"] is True
    assert stats["gradings_per_task"] == 2
    assert stats["tasks_compared"] == 2
    assert stats["tasks_that_moved"] == 1  # `b` was graded twice and held still
    assert stats["max_spread_pp"] == pytest.approx(2.5)


def test_a_task_that_held_still_is_a_measured_zero() -> None:
    """Once two verdicts have been put side by side, ``0`` is a real answer.

    This is the mirror of the ``None`` above and the reason it is not just
    squeamishness: agreement that was actually observed is worth publishing,
    and the two cases have to be told apart.
    """
    stats = _grader_agreement_stats([_task("a", 77.0), _task("a", 77.0)])

    assert stats["compared"] is True
    assert stats["tasks_that_moved"] == 0
    assert stats["max_spread_pp"] == 0.0


def test_the_spread_is_the_widest_gap_and_not_the_last_one() -> None:
    stats = _grader_agreement_stats(
        [_task("a", 10.0), _task("a", 90.0), _task("a", 50.0)]
    )

    assert stats["gradings_per_task"] == 3
    assert stats["max_spread_pp"] == pytest.approx(80.0)


def test_an_errored_grading_brings_no_score_to_compare() -> None:
    """A task graded once and failed once was not graded twice.

    Counting it as compared would put a task into ``tasks_compared`` on the
    strength of a single verdict, and then report it as agreeing.
    """
    stats = _grader_agreement_stats([_task("a", 50.0), _task("a", None)])

    assert stats["gradings_per_task"] == 2  # it was attempted twice
    assert stats["tasks_compared"] == 0  # ...and scored once
    assert stats["compared"] is False
    assert stats["tasks_that_moved"] is None


def test_a_task_without_an_id_cannot_be_matched_to_its_other_grading() -> None:
    """Two gradings can only be paired by task id.

    Pooling id-less rows under one bucket would invent comparisons between
    different tasks, which reports movement that no grader produced.
    """
    stats = _grader_agreement_stats(
        [{"pct": 10.0, "items": []}, {"task_id": "", "pct": 90.0, "items": []}]
    )

    assert stats["compared"] is False
    assert stats["gradings_per_task"] == 0


def test_a_boolean_pct_is_not_a_score() -> None:
    """``True`` is an ``int`` in Python and would compare as ``1.0``."""
    stats = _grader_agreement_stats([_task("a", True), _task("a", False)])  # type: ignore[arg-type]

    assert stats["tasks_compared"] == 0
    assert stats["tasks_that_moved"] is None


# ── against the runs that measured it ────────────────────────────────


@pytest.fixture(scope="module")
def repeat_cohort() -> list[dict]:
    """The same thirty answers, graded three times at one fingerprint."""
    found: dict[str, dict] = {}
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        if "_shards" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("expected_ordered_task_ids_sha256")
            == REPEAT_COHORT_FINGERPRINT
            and payload.get("grader_source_hash") == GRADER_SOURCE_HASH
            and payload.get("run_status") == "final"
            and len(payload.get("tasks") or []) == COHORT_TASKS
        ):
            # Keyed by grading time so that one run found twice on disk is one
            # run: three copies of a single grading agree perfectly and would
            # report stability having compared nothing.
            found[str(payload.get("graded_at"))] = payload
    if len(found) < REPEAT_RUNS:
        pytest.skip("the three repeat gradings are not in this checkout")
    return [found[stamp] for stamp in sorted(found)]


def test_each_repeat_run_publishes_a_zero_it_did_not_measure(
    repeat_cohort: list[dict],
) -> None:
    """The three runs that prove the grader moves all report perfect agreement.

    Not a reconstruction: these are the committed payloads, and this is the
    number the dashboard reads out of each of them.
    """
    for payload in repeat_cohort:
        assert payload["summary"]["openai_compat"]["inconsistent_count"] == 0

        alone = _grader_agreement_stats(payload["tasks"])
        assert alone["compared"] is False
        assert alone["tasks_that_moved"] is None


def test_the_three_runs_together_say_the_grader_moved(
    repeat_cohort: list[dict],
) -> None:
    """29 of 30, and 7.05 points at the widest.

    Pooling the three gradings is the comparison none of them could make
    alone. Pinned rather than re-derived: this is the evidence that the zero
    published beside it points the wrong way, and a checkout where it stopped
    reproducing would be one where that claim quietly lost its basis.
    """
    pooled = [task for payload in repeat_cohort for task in payload["tasks"]]
    stats = _grader_agreement_stats(pooled)

    assert stats["compared"] is True
    assert stats["gradings_per_task"] == REPEAT_RUNS
    assert stats["tasks_compared"] == COHORT_TASKS
    assert stats["tasks_that_moved"] == TASKS_THAT_MOVED
    assert stats["max_spread_pp"] == pytest.approx(WIDEST_SWING_PP)

    # Which is to say: the field that reads as "graders agreed" says 0 about
    # runs in which all but one task disagreed with itself.
    assert stats["tasks_that_moved"] > 0
    for payload in repeat_cohort:
        assert payload["summary"]["openai_compat"]["inconsistent_count"] == 0


# ── what the run publishes ───────────────────────────────────────────


def test_the_summary_carries_the_basis_beside_the_number(
    ) -> None:
    summary = _compute_summary([_task("a", 50.0)])

    assert summary["openai_compat"]["inconsistent_count"] == 0
    assert summary["grader_agreement"]["compared"] is False
    assert summary["grader_agreement"]["tasks_that_moved"] is None
    # Beside its siblings, which are also caveats on the headline rather than
    # parts of the fixed compatibility shape.
    assert {"grader_agreement", "score_exclusions", "routing"} <= set(summary)


def test_the_number_it_explains_is_still_the_zero_everything_depends_on() -> None:
    """Deliberately unchanged.

    ``core/grade_payload.py`` and ``scripts/aggregate-grades.mjs`` both detect
    a stub payload by ``inconsistent_count != 0``, and ninety-four committed
    payloads carry the ``0``. Fixing the caption is not worth invalidating the
    record, so the fix is the basis published beside it.
    """
    for tasks in ([], [_task("a", 50.0)], [_task("a", 50.0), _task("a", 90.0)]):
        assert _compute_summary(tasks)["openai_compat"]["inconsistent_count"] == 0


def test_a_grade_written_before_this_field_existed_still_validates() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    summary_schema = schema["properties"]["summary"]

    assert "grader_agreement" in summary_schema["properties"]
    assert "grader_agreement" not in summary_schema.get("required", [])


def test_the_schema_warns_against_reading_the_zero_as_agreement() -> None:
    """The required integer cannot be renamed, so it has to say what it is.

    Same remedy ``perfect_count`` got when its name outlived its threshold:
    the field stays, and its description carries the correction.
    """
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    described = schema["properties"]["summary"]["properties"]["openai_compat"][
        "properties"
    ]["inconsistent_count"]["description"]

    assert "grader_agreement" in described
    assert "29 of the 30" in described


def test_the_published_shape_is_what_the_schema_describes() -> None:
    jsonschema = pytest.importorskip("jsonschema")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    agreement_schema = schema["properties"]["summary"]["properties"][
        "grader_agreement"
    ]

    for stats in (
        _grader_agreement_stats([]),
        _grader_agreement_stats([_task("a", 50.0)]),
        _grader_agreement_stats([_task("a", 50.0), _task("a", 52.5)]),
    ):
        jsonschema.validate(stats, agreement_schema)
        assert set(agreement_schema["required"]) <= set(stats)
