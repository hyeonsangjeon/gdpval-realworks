"""A pass rate divided by nothing, published where a failure rate is read.

``step8_grade._rate`` returns ``0.0`` when its denominator is empty. That is
also, exactly, what "every single item failed" returns -- the worst score the
scale can express. The denominator that would tell the two apart is discarded.

This is not a hypothetical collision. Measured over the grade payloads
committed to this repository: **twenty of the thirty-three that carry a ``wow``
block report ``precheck_pass_rate: 0.0``, and every one of the twenty
prechecked nothing at all.** Not one is a run where prechecks ran and failed.
Per sector it is fifty-six of eighty-three rows, with no real zero among those
either. The 185-task gold-ceiling run is in that set: 8,816 judged items, zero
prechecked ones, published as a 0% structural pass rate.

Three things read it and none of them can tell:

* ``core/narrative_analyzer.py`` hands the **paid** narrative model
  ``Precheck pass rate: 0%`` directly above "Precheck failures dominate:
  deliverable structure issues (file naming, format)".
* ``src/components/wow/StructureVsReasoning.tsx`` subtracts judge from
  precheck and renders "Strong on reasoning, weak on structure" below −0.15;
  on the gold-ceiling run that is ``0.0 - 0.3329``.
* ``scripts/grading_cost_sweep.py`` rejects a config whose
  ``precheck_pass_rate`` is under a threshold -- an acceptance gate firing on
  an absence.

``step8_grade`` already argues this case against itself. The
``rubric_severity_curve`` comment refuses to publish an all-zero shape from
missing verdicts because "every point on the curve would read 0.0 and the chart
would assert a total failure that never happened. A single rate can absorb
that; a curve cannot, because its shape is the claim." The corpus above is the
measurement of whether the single rate absorbed it. It did not. And that same
curve already publishes ``n_items`` beside each ``pass_rate``, which is the
whole of the remedy here.

The rates are unchanged. They are ``number`` on both sides of the wire,
thirty-three payloads carry them, and a threshold gate compares them. What is
pinned here is the denominator published beside them, and that the paid prompt
stops rendering a percentage it has no basis for.

Nothing in this file calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.narrative_analyzer import (
    _build_grading_guard_clause,
    _build_grading_results_section,
    _failure_pattern_hint,
    _format_rate,
    _measured_over,
)
from step8_grade import _compute_summary, _rate, _wow_item_counts

REPO_ROOT = Path(__file__).resolve().parents[2]
GRADES_ROOT = REPO_ROOT / "data/grades"
SCHEMA = Path(__file__).resolve().parents[1] / "schemas/grade.schema.json"

#: The 185-task gold-ceiling run, found by the cohort fingerprint its payload
#: carries rather than by path: it lives under a hash directory and its
#: filename encodes four more.
GOLD_CEILING_COHORT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)
GOLD_CEILING_TASKS = 185
GOLD_CEILING_JUDGE_ITEMS = 8816
GOLD_CEILING_PRECHECK_ITEMS = 0

#: Floors, not equalities. The corpus grows; what must not change is that no
#: published ``precheck_pass_rate`` of 0.0 has ever been a real one, and these
#: keep that claim from passing over an empty corpus.
PAYLOADS_WITH_AN_EMPTY_PRECHECK_ZERO = 20
SECTOR_ROWS_WITH_AN_EMPTY_PRECHECK_ZERO = 56


def _item(*, passed: bool, precheck: bool = False, critical: bool = False) -> dict:
    """One graded rubric item, decided by precheck or by the judge.

    The keys are the ones ``_tally_item`` actually reads: ``verdict``, a
    ``max_score`` whose magnitude clears ``MAGNITUDE_THRESHOLD`` for critical
    items, and ``model_did_right`` (criticality is scored sign-aware, not by
    the verdict).
    """
    return {
        "verdict": "pass" if passed else "fail",
        "model_did_right": passed,
        "max_score": 4 if critical else 1,
        "decided_by": "precheck" if precheck else "judge",
    }


def _task(sector: str, items: list[dict], pct: float = 50.0) -> dict:
    return {"task_id": f"t{len(items)}-{sector}", "sector": sector, "pct": pct,
            "items": items}


# ── the collision itself ─────────────────────────────────────────────


def test_a_rate_over_nothing_and_a_total_failure_are_the_same_number() -> None:
    """The premise, stated as an assertion so it cannot quietly stop being true.

    If these two ever diverge, everything below is unnecessary.
    """
    nothing_was_checked = _rate(0, 0)
    everything_failed = _rate(0, 4000)

    assert nothing_was_checked == everything_failed == 0.0


def test_the_counts_that_tell_them_apart_are_published() -> None:
    counters = {"all_items": 10, "critical_items": 2, "pre_items": 0,
                "judge_items": 10}

    assert _wow_item_counts(counters) == {
        "rubric_items": 10,
        "critical_items": 2,
        "precheck_items": 0,
        "judge_items": 10,
    }


def test_a_run_that_prechecked_nothing_says_so_in_the_summary() -> None:
    """The rate stays 0.0. The zero beside it is what changes the reading."""
    wow = _compute_summary(
        [_task("Information", [_item(passed=True), _item(passed=False)])]
    )["wow"]

    assert wow["precheck_pass_rate"] == 0.0
    assert wow["item_counts"]["precheck_items"] == 0
    assert wow["item_counts"]["judge_items"] == 2


def test_a_run_where_prechecks_ran_and_all_failed_reads_differently() -> None:
    """Same 0.0, non-empty denominator: here it is a finding.

    Without this case the fix would be indistinguishable from suppressing the
    number whenever it is zero, which would hide the failure it exists to
    report.
    """
    wow = _compute_summary(
        [_task("Information", [_item(passed=False, precheck=True)] * 3)]
    )["wow"]

    assert wow["precheck_pass_rate"] == 0.0
    assert wow["item_counts"]["precheck_items"] == 3


def test_the_counts_are_published_per_sector_too() -> None:
    summary = _compute_summary(
        [
            _task("Information", [_item(passed=True, precheck=True)]),
            _task("Retail Trade", [_item(passed=False, critical=True)]),
        ]
    )
    by_sector = summary["wow"]["by_sector"]

    assert by_sector["Information"]["item_counts"]["precheck_items"] == 1
    assert by_sector["Retail Trade"]["item_counts"]["precheck_items"] == 0
    assert by_sector["Retail Trade"]["item_counts"]["critical_items"] == 1
    # ...and the run-wide counts are the sum, not a separate measurement.
    assert summary["wow"]["item_counts"]["judge_items"] == 1


def test_an_empty_run_counts_nothing_rather_than_claiming_zero_passes() -> None:
    wow = _compute_summary([])["wow"]

    assert wow["item_counts"] == {
        "rubric_items": 0,
        "critical_items": 0,
        "precheck_items": 0,
        "judge_items": 0,
    }


# ── reading the counts back ──────────────────────────────────────────


def test_a_grade_written_before_the_counts_existed_says_unknown() -> None:
    """``None``, not ``0``.

    Ninety-odd payloads predate ``item_counts``. Treating a missing count as
    zero would relabel every one of their rates "not measured", which is the
    same substitution in the other direction.
    """
    assert _measured_over({"precheck_pass_rate": 0.0}, "precheck_items") is None
    assert _measured_over({"item_counts": None}, "precheck_items") is None
    assert _measured_over({"item_counts": {}}, "precheck_items") is None


def test_a_count_that_is_not_a_count_is_not_believed() -> None:
    for bad in (True, False, "12", 3.5, -1, None):
        assert _measured_over({"item_counts": {"precheck_items": bad}},
                              "precheck_items") is None
    assert _measured_over({"item_counts": {"precheck_items": 0}},
                          "precheck_items") == 0


# ── what the paid model is told ──────────────────────────────────────


def test_the_paid_prompt_does_not_render_a_percentage_it_cannot_support() -> None:
    metrics = {"precheck_pass_rate": 0.0, "item_counts": {"precheck_items": 0}}

    rendered = _format_rate(metrics, "precheck_pass_rate", "precheck_items")

    assert rendered == "not measured (0 items)"
    assert "%" not in rendered


def test_a_measured_rate_is_rendered_with_what_it_was_measured_over() -> None:
    metrics = {"judge_pass_rate": 0.7113, "item_counts": {"judge_items": 8816}}

    assert _format_rate(metrics, "judge_pass_rate", "judge_items") == "71% of 8816"


def test_a_measured_zero_is_still_reported_as_zero() -> None:
    metrics = {"precheck_pass_rate": 0.0, "item_counts": {"precheck_items": 40}}

    assert _format_rate(metrics, "precheck_pass_rate", "precheck_items") == "0% of 40"


def test_an_older_grade_keeps_its_bare_percentage() -> None:
    """No counts to attach, and no licence to call it unmeasured either."""
    assert _format_rate({"judge_pass_rate": 0.5}, "judge_pass_rate",
                        "judge_items") == "50%"


def test_the_failure_pattern_hint_withdraws_the_comparison_it_cannot_make() -> None:
    unmeasured = _failure_pattern_hint({"item_counts": {"precheck_items": 0}})

    assert "UNAVAILABLE" in unmeasured
    assert "Do NOT report weak deliverable" in unmeasured
    # The instruction that invited the conclusion is gone, not merely qualified.
    assert "Precheck failures dominate" not in unmeasured


def test_the_hint_stands_when_there_is_a_precheck_to_compare() -> None:
    measured = _failure_pattern_hint({"item_counts": {"precheck_items": 40}})

    assert "Precheck failures dominate" in measured
    assert "Judge failures dominate" in measured
    assert "UNAVAILABLE" not in measured


def test_the_hint_no_longer_points_at_a_breakdown_that_is_always_empty() -> None:
    """``by_rubric_category`` is ``{}`` on every run this repository produces.

    ``step8_grade`` says why in a comment: the GDPVal rubrics carry no category
    taxonomy. The prompt has never included the field, so "Mixed: see
    by_rubric_category" directed the model to consult something it could not
    see -- and a model that cannot find a breakdown reasons from what it can,
    which is the 0% above.
    """
    for counts in ({"precheck_items": 0}, {"precheck_items": 40}):
        assert "by_rubric_category" not in _failure_pattern_hint(
            {"item_counts": counts}
        )


def test_the_guard_clause_stops_asking_for_the_breakdown() -> None:
    """The instruction and the numbers have to agree.

    Withdrawing the hint while still ordering the model to "Highlight: precheck
    vs judge breakdown" leaves it required to produce a comparison and given
    only a 0% to build it from.
    """
    grade = {"summary": {"wow": {"item_counts": {"precheck_items": 0}}}}

    assert "precheck vs judge breakdown" not in _build_grading_guard_clause(grade)
    # ...and only that one was withdrawn. The rest of the line survives.
    # `critical_item_pass_rate` used to be asserted here too; it left the
    # highlight list by owner decision, pinned in
    # `test_the_report_prompt_retires_the_required_item_name.py`.
    assert "weakest sector, strongest sector" in _build_grading_guard_clause(grade)


def test_the_guard_clause_still_asks_for_it_when_it_exists() -> None:
    for wow in ({"item_counts": {"precheck_items": 40}}, {}, None):
        grade = {"summary": {"wow": wow}}
        assert "precheck vs judge breakdown" in _build_grading_guard_clause(grade)


def test_the_pre_grading_guard_is_untouched() -> None:
    assert "do NOT exist yet" in _build_grading_guard_clause(None)


# ── against the run it was measured on ───────────────────────────────


@pytest.fixture(scope="module")
def gold_ceiling() -> dict:
    """The 185-task run, as committed."""
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        if "_shards" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and payload.get("expected_ordered_task_ids_sha256") == GOLD_CEILING_COHORT
            and payload.get("run_status") == "final"
            and len(payload.get("tasks") or []) == GOLD_CEILING_TASKS
        ):
            return payload
    pytest.skip("the gold-ceiling run is not in this checkout")


def test_the_gold_ceiling_run_published_a_zero_it_never_measured(
    gold_ceiling: dict,
) -> None:
    """8,816 items judged, none prechecked, 0% published. As committed."""
    published = gold_ceiling["summary"]["wow"]

    assert published["precheck_pass_rate"] == 0.0
    assert published["judge_pass_rate"] > 0.0

    counts = _compute_summary(gold_ceiling["tasks"])["wow"]["item_counts"]
    assert counts["judge_items"] == GOLD_CEILING_JUDGE_ITEMS
    assert counts["precheck_items"] == GOLD_CEILING_PRECHECK_ITEMS


def test_that_run_stops_telling_the_paid_model_structure_collapsed(
    gold_ceiling: dict,
) -> None:
    """Before and after, on the payload itself rather than a fixture."""
    before = _build_grading_results_section(gold_ceiling)
    assert "Precheck pass rate: 0%" in before
    assert "Precheck failures dominate" in before

    resummarised = dict(gold_ceiling)
    resummarised["summary"] = _compute_summary(gold_ceiling["tasks"])
    after = _build_grading_results_section(resummarised)

    assert "Precheck pass rate: not measured (0 items)" in after
    assert "Precheck pass rate: 0%" not in after
    assert "Precheck failures dominate" not in after
    assert f"Judge pass rate: 71% of {GOLD_CEILING_JUDGE_ITEMS}" in after
    # Every sector line, too -- the run-wide caveat does not reach those.
    assert "pre=0%" not in after
    assert "pre=not measured (0 items)" in after


@pytest.fixture(scope="module")
def published_wow_blocks() -> list[tuple[str, dict, dict]]:
    """Every committed payload that carries a ``wow`` block, re-summarised.

    Shards are excluded: they are intermediate halves of a run, and their rates
    are not published anywhere.
    """
    out: list[tuple[str, dict, dict]] = []
    for path in sorted(GRADES_ROOT.rglob("*.json")):
        if "_shards" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        wow = (payload.get("summary") or {}).get("wow")
        if not isinstance(wow, dict) or not wow:
            continue
        out.append((path.name, wow, _compute_summary(payload.get("tasks") or [])["wow"]))
    if not out:
        pytest.skip("no committed grade payloads in this checkout")
    return out


def test_no_published_precheck_zero_has_ever_been_a_real_one(
    published_wow_blocks: list[tuple[str, dict, dict]],
) -> None:
    """The measurement this whole change rests on.

    Stated as an invariant plus a floor rather than an equality, so that adding
    a payload cannot break it -- but an empty corpus, or a checkout where the
    zeros stopped being absences, cannot let it pass either.
    """
    empty = [
        name
        for name, published, fresh in published_wow_blocks
        if published.get("precheck_pass_rate") == 0.0
        and fresh["item_counts"]["precheck_items"] == 0
    ]
    real = [
        name
        for name, published, fresh in published_wow_blocks
        if published.get("precheck_pass_rate") == 0.0
        and fresh["item_counts"]["precheck_items"] > 0
    ]

    assert real == []
    assert len(empty) >= PAYLOADS_WITH_AN_EMPTY_PRECHECK_ZERO


def test_the_same_holds_row_by_row_across_sectors(
    published_wow_blocks: list[tuple[str, dict, dict]],
) -> None:
    empty = real = 0
    for _name, published, fresh in published_wow_blocks:
        for sector, row in (published.get("by_sector") or {}).items():
            if row.get("precheck_pass_rate") != 0.0:
                continue
            fresh_row = (fresh.get("by_sector") or {}).get(sector)
            if fresh_row is None:
                continue
            if fresh_row["item_counts"]["precheck_items"] == 0:
                empty += 1
            else:
                real += 1

    assert real == 0
    assert empty >= SECTOR_ROWS_WITH_AN_EMPTY_PRECHECK_ZERO


def test_the_rates_themselves_did_not_move(
    published_wow_blocks: list[tuple[str, dict, dict]],
) -> None:
    """Re-summarising a committed payload reproduces its published rates.

    The remedy is additive on purpose: an acceptance gate in
    ``scripts/grading_cost_sweep.py`` compares these against thresholds and
    thirty-three payloads carry them, so nulling them to fix a caption would
    break more than it repairs.

    The two rates checked here are the two that re-summarise faithfully across
    the whole corpus. The other two do not, for reasons older than this change
    -- see the test below, which pins that rather than leaving it as an
    unexplained gap in this one.
    """
    for name, published, fresh in published_wow_blocks:
        for key in ("precheck_pass_rate", "judge_pass_rate"):
            if key in published:
                assert published[key] == pytest.approx(fresh[key]), f"{name}:{key}"


def test_two_other_rates_no_longer_re_summarise_from_older_payloads() -> None:
    """Not caused here, and not fixed here -- but not silently skipped either.

    Six of the thirty-three payloads publish a ``critical_item_pass_rate`` that
    recomputing from their own ``tasks`` returns ``0.0`` for, and two do the
    same for ``rubric_item_coverage_avg``. The cause is field drift in the
    stored items, not arithmetic: criticality is now scored from
    ``model_did_right`` and sized by ``|max_score| >= 4``, and payloads written
    before those fields existed have nothing for the counter to read.

    It is worth pinning because it is the same failure mode one layer down. A
    rate recomputed over items that no longer carry the field it needs comes
    back ``0.0``, and ``0.0`` is a plausible-looking score. The count published
    beside it is what shows the difference -- ``critical_items`` is in the
    hundreds on those very payloads while the rate reads zero.
    """
    stale = {"verdict": "pass", "max_score": 4}  # pre-`model_did_right`
    wow = _compute_summary([_task("Information", [stale, stale, stale])])["wow"]

    assert wow["critical_item_pass_rate"] == 0.0
    assert wow["item_counts"]["critical_items"] == 3  # ...over three of them


# ── the shape on the wire ────────────────────────────────────────────


def test_the_new_key_needs_no_schema_change() -> None:
    """``summary.wow`` is an open object, so nothing already published breaks."""
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    wow_schema = schema["properties"]["summary"]["properties"]["wow"]

    assert wow_schema.get("type") == "object"
    assert "properties" not in wow_schema
    assert not wow_schema.get("additionalProperties") is False


def test_the_drift_check_still_compares_what_it_always_did() -> None:
    """``summary_wow_drift.py`` diffs five named rates; a new key is not one."""
    drift = (Path(__file__).resolve().parents[1] / "scripts/summary_wow_drift.py")
    source = drift.read_text(encoding="utf-8")

    assert "item_counts" not in source
    assert "WOW_RATES" in source
