"""The paid report prompt was the last place still calling it "critical".

The owner ruled on 2026-09-03, in writing, that
``summary.wow.critical_item_pass_rate`` stops being published under a
required-item name and stops standing as a headline or a pass criterion. The
ruling is recorded verbatim in
``data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`` and turns on a
measurement: GDPVal v2 rubrics carry a ``required`` field and it is ``null`` on
all 10,453 items across all 220 tasks, so ``core/grader.py`` substitutes score
magnitude -- ``abs(max_score) >= MAGNITUDE_THRESHOLD`` -- for necessity. The
number is a high-magnitude diagnostic wearing a requirement's name.

PR #394 applied that ruling to the gold-ceiling gate and the dashboard and
named what it did not reach:

    Known residual: `core/narrative_analyzer.py` still writes "Critical item
    pass rate" into the report prompt. Correcting that string is a one-word
    edit, but `core/**/*.py` feeds `compute_grader_source_hash`, so it is
    deferred to the next fingerprint-moving PR rather than smuggled in beside
    a label change.

The residual was worse than the string. ``_build_grading_guard_clause`` also
ordered the paid narrative model to **highlight** ``critical_item_pass_rate``,
unconditionally, on the line immediately above a denominator-guarded highlight
for the precheck breakdown. One rate was protected from its own empty
denominator and the other was promoted regardless of what was behind it -- on
the one surface where a model is paid to turn these numbers into prose that a
person then reads.

Measured over the grade payloads committed to this repository: 83 published
sector rows carry the rate and 13 report exactly ``0.0``. Recomputing the count
settles all 13 -- four counted no high-magnitude item at all, nine counted
between 1 and 19, and none reached 20. The 61 shard payloads, whose rates are
published nowhere, say the same thing at scale: 364 rows, 155 zeros, split 41
and 114, and again not one at 20. There is no ``0.0`` on this metric, in either
population, that is a run where twenty or more high-magnitude items were scored
and failed.

(An earlier entry in ``CHANGELOG.md`` and point 6 of the decision document put
these at 447 rows and 168 zeros. That pair added the 364 shard rows into a count
it called published. Both are corrected in this change; the conclusion they
drew was right and is asserted below over each population separately.)

What this file pins is the reading, not the arithmetic. The JSON key keeps its
published name, the rate keeps its value, and not one byte under
``data/grades/`` changes.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from core.grader import MAGNITUDE_THRESHOLD
from core.narrative_analyzer import (
    HIGH_MAGNITUDE_PASS_REFERENCE,
    HIGH_MAGNITUDE_RATE_LABEL,
    MIN_READABLE_HIGH_MAGNITUDE_ITEMS,
    _build_grading_guard_clause,
    _build_grading_results_section,
    _format_high_magnitude_rate,
    _format_rate,
)
from step8_grade import _compute_summary

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER.parent
GRADES_ROOT = REPO_ROOT / "data/grades"
DECISION_DOC = GRADES_ROOT / "_validation/REQUIRED_ITEM_DEFINITION.md"
FRONTEND_READING = REPO_ROOT / "src/components/wow/highMagnitudeReading.ts"
GOLD_CEILING_ANALYSIS = BATCH_RUNNER / "scripts/analyze_gold_ceiling.py"

#: Words the ruling retired from anything a person reads. They are still legal
#: in a JSON key and in a comment explaining the history; they are not legal in
#: the text handed to the model that writes the report.
RETIRED_WORDS = ("critical", "required", "mandatory", "must-have")

#: Floors, not equalities -- the corpus grows. What must not become true is
#: that the measurement this change rests on stops holding. Kept apart by
#: population, because conflating the two is what produced the wrong figure the
#: module docstring corrects.
PUBLISHED_ROWS_WITH_AN_UNREADABLE_ZERO = 13
SHARD_ROWS_WITH_AN_UNREADABLE_ZERO = 155


def _item(*, passed: bool, critical: bool = False) -> dict:
    return {
        "verdict": "pass" if passed else "fail",
        "model_did_right": passed,
        "max_score": MAGNITUDE_THRESHOLD if critical else 1,
        "decided_by": "judge",
    }


def _grade(wow: dict) -> dict:
    return {
        "judge": {"model": "a-judge", "reasoning_effort": "max", "temperature": 0.0},
        "rubric": {"repo_id": "openai/gdpval", "short_sha": "abc1234"},
        "summary": {"openai_compat": {"total_tasks": 4}, "wow": wow},
    }


# ── the words ────────────────────────────────────────────────────────


def test_the_label_says_what_the_number_actually_measures() -> None:
    assert HIGH_MAGNITUDE_RATE_LABEL == (
        f"High-magnitude item pass rate (|max score| >= {MAGNITUDE_THRESHOLD}, "
        "diagnostic)"
    )
    for word in RETIRED_WORDS:
        assert word not in HIGH_MAGNITUDE_RATE_LABEL.lower()


def test_the_threshold_in_the_label_is_the_one_the_grader_applies() -> None:
    """A label that names a number has to name the number in force.

    The card the dashboard replaced said "weight >= 3" while the code compared
    magnitude against 4. Spelling the threshold into the prompt by hand would
    reintroduce exactly that: the label is built from ``MAGNITUDE_THRESHOLD``
    so it cannot drift from ``core/grader.py``, and this says so out loud.
    """
    assert f"|max score| >= {MAGNITUDE_THRESHOLD}" in HIGH_MAGNITUDE_RATE_LABEL
    assert MAGNITUDE_THRESHOLD == 4


def test_the_retired_words_are_gone_from_the_prompt_a_model_reads() -> None:
    """Every rendered line, not just the one that was named in the residual."""
    wow = {
        "critical_item_pass_rate": 0.0,
        "precheck_pass_rate": 0.4,
        "judge_pass_rate": 0.7,
        "item_counts": {"critical_items": 40, "precheck_items": 10, "judge_items": 90},
        "by_sector": {
            "Information": {
                "avg_pct": 62.0,
                "critical_item_pass_rate": 0.0,
                "precheck_pass_rate": 0.4,
                "judge_pass_rate": 0.5,
                "item_counts": {
                    "critical_items": 40,
                    "precheck_items": 10,
                    "judge_items": 90,
                },
            }
        },
    }
    rendered = _build_grading_results_section(_grade(wow))

    assert "Critical item pass rate" not in rendered
    assert "crit=" not in rendered
    assert HIGH_MAGNITUDE_RATE_LABEL in rendered
    assert "high_mag=" in rendered


def test_the_json_key_is_not_renamed() -> None:
    """Point 3 of the ruling stops at what is exposed.

    Renaming ``critical_item_pass_rate`` would break every reader of every
    payload written so far, which is why the ruling is about the prose. The
    producer is untouched here and still publishes the key.
    """
    wow = _compute_summary([{"task_id": "t", "sector": "Information", "pct": 50.0,
                             "items": [_item(passed=True, critical=True)]}])["wow"]

    assert "critical_item_pass_rate" in wow
    assert wow["item_counts"]["critical_items"] == 1


# ── the standing ─────────────────────────────────────────────────────


def test_the_paid_model_is_no_longer_told_to_highlight_it() -> None:
    """The defect the residual paragraph did not name.

    ``Highlight:`` is the line that decides what the report leads with. A
    diagnostic the owner removed from the dashboard headline and from the
    gold-ceiling gate was still being ordered into the report's headline.
    """
    clause = _build_grading_guard_clause(_grade({"item_counts": {"precheck_items": 40}}))
    highlight_line = next(
        line for line in clause.splitlines() if line.startswith("- Highlight:")
    )

    assert "critical_item_pass_rate" not in highlight_line
    for word in RETIRED_WORDS:
        assert word not in highlight_line.lower()


def test_removing_it_from_the_highlights_left_the_others_alone() -> None:
    """Surgical, not a deletion of the instruction.

    Without this, emptying the whole line would pass the test above.
    """
    measured = _grade({"item_counts": {"precheck_items": 40}})
    unmeasured = _grade({"item_counts": {"precheck_items": 0}})

    assert (
        "- Highlight: weakest sector, strongest sector, precheck vs judge breakdown."
        in _build_grading_guard_clause(measured)
    )
    # ...and the precheck guard added by the earlier change still fires.
    assert (
        "- Highlight: weakest sector, strongest sector."
        in _build_grading_guard_clause(unmeasured)
    )


def test_the_model_is_told_it_is_not_a_pass_criterion() -> None:
    """"합격 게이트로 더 이상 게시하지 마세요", on the surface that writes prose.

    Renaming the row without saying what it is would leave a model free to
    write "the run failed on high-magnitude items", which is the same claim
    under a new heading.

    Asserted against the clause with its line wrapping folded away. The prompt
    is wrapped to the file's column width, so "NOT a pass criterion" is split
    across two lines in the source and read as one sentence by the model. A
    substring test over the raw text would pin the wrapping rather than the
    instruction, and would fail the next time the paragraph is reflowed.
    """
    clause = " ".join(_build_grading_guard_clause(_grade({})).split())

    assert "NOT a pass criterion" in clause
    assert "NOT a measure of required items" in clause
    assert "supporting detail only" in clause
    assert "do not call it critical, required or mandatory" in clause


def test_the_pre_grading_guard_is_untouched() -> None:
    assert "do NOT exist yet" in _build_grading_guard_clause(None)


# ── the denominator, and how small is too small ──────────────────────


def test_the_readability_floor_is_derived_rather_than_chosen() -> None:
    assert HIGH_MAGNITUDE_PASS_REFERENCE == 0.95
    assert MIN_READABLE_HIGH_MAGNITUDE_ITEMS == math.ceil(
        1 / (1 - HIGH_MAGNITUDE_PASS_REFERENCE)
    )
    assert MIN_READABLE_HIGH_MAGNITUDE_ITEMS == 20


def test_the_three_copies_of_the_floor_agree() -> None:
    """The constant is duplicated on purpose; this is what makes that safe.

    ``batch-runner/scripts/`` is not a ``compute_grader_source_hash`` input, so
    importing the reference from ``analyze_gold_ceiling.py`` would let a file
    outside the fingerprint change the text of a grading-adjacent prompt --
    precisely what ``grade-run.yml`` warns against. The frontend cannot import
    Python at all. So there are three copies, and a drifting one fails here
    rather than in a report nobody re-reads.
    """
    analysis = GOLD_CEILING_ANALYSIS.read_text(encoding="utf-8")
    assert f"CRITICAL_ITEM_PASS_FLOOR = {HIGH_MAGNITUDE_PASS_REFERENCE}" in analysis

    frontend = FRONTEND_READING.read_text(encoding="utf-8")
    assert (
        f"MIN_READABLE_HIGH_MAGNITUDE_ITEMS = {MIN_READABLE_HIGH_MAGNITUDE_ITEMS}"
        in frontend
    )
    assert f"HIGH_MAGNITUDE_MIN_ABS_SCORE = {MAGNITUDE_THRESHOLD}" in frontend


@pytest.mark.parametrize(
    "counted, expected",
    [
        (0, "not measured (0 items)"),
        (1, "0% of 1 -- too few to read (< 20 items)"),
        (19, "0% of 19 -- too few to read (< 20 items)"),
        (20, "0% of 20"),
        (400, "0% of 400"),
    ],
)
def test_a_zero_reads_as_what_its_denominator_supports(counted: int, expected: str) -> None:
    metrics = {"critical_item_pass_rate": 0.0, "item_counts": {"critical_items": counted}}

    assert _format_high_magnitude_rate(metrics) == expected


def test_a_denominator_that_was_never_recorded_says_so() -> None:
    """21 of the 83 published sector rows are in exactly this state, and all
    364 shard rows.

    Older payloads predate ``item_counts``. "We do not know what this was
    divided by" is a different statement from "it was divided by nothing", and
    turning the first into the second would relabel most of the corpus.
    """
    assert (
        _format_high_magnitude_rate({"critical_item_pass_rate": 0.0})
        == "0% (denominator not recorded)"
    )
    assert (
        _format_high_magnitude_rate(
            {"critical_item_pass_rate": 0.83, "item_counts": {}}
        )
        == "83% (denominator not recorded)"
    )


def test_a_real_measurement_still_reads_as_one() -> None:
    """The guard has to leave the finding it exists to protect.

    A change that hid the number whenever it was low would suppress the very
    failures the metric is kept for.
    """
    metrics = {"critical_item_pass_rate": 0.33, "item_counts": {"critical_items": 400}}

    assert _format_high_magnitude_rate(metrics) == "33% of 400"


def test_the_other_two_rates_are_deliberately_left_alone() -> None:
    """Scope, pinned so it is a decision rather than an oversight.

    The ruling was about this metric. Inventing a readability floor for
    ``precheck_pass_rate`` and ``judge_pass_rate`` would be a new criterion
    applied to runs already published, which is the thing the owner forbade.
    """
    small = {"precheck_pass_rate": 0.0, "judge_pass_rate": 0.0,
             "item_counts": {"precheck_items": 3, "judge_items": 3}}

    assert _format_rate(small, "precheck_pass_rate", "precheck_items") == "0% of 3"
    assert _format_rate(small, "judge_pass_rate", "judge_items") == "0% of 3"
    assert "too few to read" not in _format_rate(small, "judge_pass_rate", "judge_items")


# ── against the corpus it was measured on ────────────────────────────


@pytest.fixture(scope="module")
def published_sector_rows() -> list[tuple[str, bool, dict, dict]]:
    """Every committed payload carrying a ``wow`` block, re-summarised.

    Shards are kept, flagged rather than dropped. They are intermediate halves
    of a run and their rates are published nowhere, so they must not be counted
    as published -- but they are four times the corpus, and the claim below is
    worth making about them too. Folding them in silently is what produced the
    447/168 pair the module docstring corrects.
    """
    out: list[tuple[str, bool, dict, dict]] = []
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        wow = (payload.get("summary") or {}).get("wow")
        if not isinstance(wow, dict) or not wow:
            continue
        out.append(
            (
                path.name,
                "_shards" in path.parts,
                wow,
                _compute_summary(payload.get("tasks") or [])["wow"],
            )
        )
    if not out:
        pytest.skip("no committed grade payloads in this checkout")
    return out


def test_no_published_zero_on_this_metric_is_a_readable_one(
    published_sector_rows: list[tuple[str, bool, dict, dict]],
) -> None:
    """The measurement the change rests on, asserted so it cannot lapse.

    Every ``0.0`` on this metric counted fewer than twenty items. If one ever
    counts twenty or more, that is a real finding and this test is where the
    claim in the module docstring stops being true.

    The floors are per population. A published row and a shard row are not the
    same evidence, and one number covering both is the error being corrected.
    """
    unreadable = {False: 0, True: 0}
    readable = {False: 0, True: 0}
    for _name, is_shard, published, fresh in published_sector_rows:
        for sector, row in (published.get("by_sector") or {}).items():
            if row.get("critical_item_pass_rate") != 0.0:
                continue
            fresh_row = (fresh.get("by_sector") or {}).get(sector)
            if fresh_row is None:
                continue
            counted = fresh_row["item_counts"]["critical_items"]
            bucket = unreadable if counted < MIN_READABLE_HIGH_MAGNITUDE_ITEMS else readable
            bucket[is_shard] += 1

    assert readable == {False: 0, True: 0}
    assert unreadable[False] >= PUBLISHED_ROWS_WITH_AN_UNREADABLE_ZERO
    assert unreadable[True] >= SHARD_ROWS_WITH_AN_UNREADABLE_ZERO


def test_not_one_published_rate_moved(
    published_sector_rows: list[tuple[str, bool, dict, dict]],
) -> None:
    """Point 2 of the ruling: no grade JSON is rewritten.

    Nothing in this change touches ``step8_grade``, ``core/grader.py`` or the
    schema, so re-summarising a committed payload has to return what that
    payload already publishes for the rates that re-summarise faithfully.
    """
    for name, _is_shard, published, fresh in published_sector_rows:
        for key in ("precheck_pass_rate", "judge_pass_rate"):
            if key in published:
                assert published[key] == pytest.approx(fresh[key]), f"{name}:{key}"


# ── the deferral, and why it was real ────────────────────────────────


def test_this_file_really_is_a_grader_fingerprint_input() -> None:
    """Why the one-word edit waited for a pull request of its own.

    ``compute_grader_source_hash`` walks every ``.py`` under
    ``batch-runner/core/``, so a prompt that has nothing to do with grading
    still moves the fingerprint every shard stamps and every merge compares.
    That is a cost worth naming, and this asserts it rather than trusting the
    paragraph that claimed it.
    """
    from step8_grade import compute_grader_source_hash

    source = (BATCH_RUNNER / "step8_grade.py").read_text(encoding="utf-8")
    body = source[source.index("def compute_grader_source_hash") :][:3000]

    assert "core" in body and "rglob" in body
    assert callable(compute_grader_source_hash)


def test_the_decision_document_no_longer_carries_this_as_open() -> None:
    """The residual paragraph and the code have to agree about what is left.

    A fix that lands while the document still calls it deferred leaves the next
    reader unable to tell which one is stale.
    """
    text = DECISION_DOC.read_text(encoding="utf-8")

    assert 'still writes "Critical item pass rate" into the' not in text
    assert "narrative_analyzer" in text  # it is discussed, just not as open


def test_the_changelog_records_that_the_fingerprint_moved() -> None:
    """Not a formality. A grade run started against the old fingerprint and
    merged against the new one is refused at ``step9_merge_shards``, hours
    after the money is spent, so the move belongs in the record."""
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # Anchored to the start of a line: the file's preamble names
    # "`## [Unreleased]` block" in prose, several hundred characters above the
    # heading it describes, and a plain substring search stops there.
    heading = re.search(r"^## \[Unreleased\]\s*$", changelog, re.MULTILINE)
    assert heading is not None
    rest = changelog[heading.end() :]
    next_heading = re.search(r"^## ", rest, re.MULTILINE)
    unreleased = rest if next_heading is None else rest[: next_heading.start()]

    assert re.search(r"grader source (fingerprint|hash)", unreleased, re.IGNORECASE)
    assert "narrative_analyzer" in unreleased
