"""An acceptance gate that eliminates a config on a check that never ran.

``select_pareto_winner`` compares four measurements against thresholds. Every
one of the four reaches it as ``0.0`` when it was never measured, because
``step8_grade._rate`` divides by an empty denominator and publishes the
quotient. ``0.0`` is also the worst real value on each scale. The gate cannot
tell the two apart, so it rejects both alike -- and then reports only "no
variant satisfied all acceptance thresholds", which reads as a verdict on the
graders whether or not anything was ever measured.

This is live, not hypothetical. The committed plan sets
``precheck_pass_rate_min: 0.7``; the grade payloads in this repository
precheck **nothing** on twenty of the thirty-three runs that carry a ``wow``
block, including the 185-task gold-ceiling run (8,816 judged items, zero
prechecked, published as 0%). A variant that is perfect on every criterion
that actually ran is therefore eliminated by a criterion that did not.

Three separate absences fed the same gate:

* ``extract_metrics`` substituted ``0.0`` for a rate missing from the grade.
* A rate present but divided by zero items arrived as a real-looking ``0.0``.
* The dry-run and crash stubs wrote ``0.0`` for runs that never graded
  anything, and those rows were then printed in RESULTS.md as measurements.

What is pinned here is that an absence no longer rejects, that a *measured*
zero still does, and that either way the reason is written down.

Nothing in this file calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import grading_cost_sweep as sweep  # noqa: E402

PLAN_PATH = REPO_ROOT / "tasks" / "0523_saturday" / "grading_cost_sweep_plan.yaml"
GRADES_ROOT = REPO_ROOT / "data" / "grades"

#: The 185-task gold-ceiling run, located by the cohort fingerprint in its
#: payload rather than by path.
GOLD_CEILING_COHORT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)


@pytest.fixture
def plan() -> sweep.Plan:
    return sweep.load_plan(PLAN_PATH)


@pytest.fixture
def acceptance(plan: sweep.Plan) -> dict:
    """The thresholds as committed, not a fixture of convenience."""
    return plan.acceptance


def _metrics(**over) -> dict:
    """A variant that clears every threshold, before `over` is applied."""
    m = {
        "name": "candidate",
        "phase": "B",
        "avg_score_pct": 77.83,
        "critical_item_pass_rate": 1.0,
        "judge_error_rate": 0.0,
        "precheck_pass_rate": 0.85,
        "item_counts": {
            "rubric_items": 100,
            "critical_items": 20,
            "precheck_items": 40,
            "judge_items": 60,
        },
        "judge_call_count": 12,
        "judge_total_latency_sec": 800.0,
        "smoke_cost_usd": 0.85,
        "full_run_cost_usd": 62.0,
    }
    m.update(over)
    return m


def _verdicts(m: dict, acceptance: dict) -> dict[str, str]:
    return {v.criterion: v.verdict for v in sweep.evaluate_acceptance(m, acceptance)}


def _details(m: dict, acceptance: dict) -> dict[str, str]:
    return {v.criterion: v.detail for v in sweep.evaluate_acceptance(m, acceptance)}


# ── the defect, stated against the committed plan ────────────────────


def test_the_threshold_that_fires_on_an_absence_is_really_committed(
    acceptance: dict,
) -> None:
    """If this is ever relaxed to 0, the rest of this file is unnecessary.

    ``precheck_pass_rate_min`` is the criterion the corpus never measures, so
    it is the one that turns an absence into an elimination in practice.
    """
    assert acceptance["precheck_pass_rate_min"] > 0.0
    assert acceptance["critical_item_pass_rate_min"] > 0.0


def test_a_variant_perfect_on_everything_measured_is_no_longer_eliminated(
    acceptance: dict,
) -> None:
    """The defect itself.

    Critical pass 1.00, judge errors 0%, score exactly at baseline -- and
    prechecks that never ran. Before this change the last of those eliminated
    it, and the report attributed the elimination to "acceptance thresholds".
    """
    m = _metrics(
        precheck_pass_rate=None,
        item_counts={"precheck_items": 0, "judge_items": 8816},
    )

    winner = sweep.select_pareto_winner({"results": {"candidate": m}}, acceptance)

    assert winner is not None
    assert winner.name == "candidate"


def test_but_it_is_not_recorded_as_having_passed_that_check(
    acceptance: dict,
) -> None:
    """Not rejecting is not the same as verifying.

    The whole risk of loosening the gate is that a config gets promoted as
    though every threshold had been applied to it. The winner has to carry
    which ones were not.
    """
    m = _metrics(
        precheck_pass_rate=None,
        item_counts={"precheck_items": 0, "judge_items": 8816},
    )

    winner = sweep.select_pareto_winner({"results": {"candidate": m}}, acceptance)

    assert winner is not None
    assert winner.unmeasured == ["precheck_pass_rate"]
    assert "NOT VERIFIED" in winner.rationale
    assert "precheck_pass_rate" in winner.rationale
    assert _verdicts(m, acceptance)["precheck_pass_rate"] == sweep.UNMEASURED


def test_a_measured_zero_is_still_a_rejection(acceptance: dict) -> None:
    """The negative control, and the point of the whole exercise.

    Forty items prechecked, every one failed. Same ``0.0`` on the wire as the
    case above. If this stopped rejecting, the "fix" would just be *ignoring*
    the precheck criterion, which is a worse bug than the one being fixed.
    """
    m = _metrics(
        precheck_pass_rate=0.0,
        item_counts={"precheck_items": 40, "judge_items": 60},
    )

    assert sweep.select_pareto_winner({"results": {"c": m}}, acceptance) is None
    assert _verdicts(m, acceptance)["precheck_pass_rate"] == sweep.FAIL
    assert "0.0 is below the limit" in _details(m, acceptance)["precheck_pass_rate"]


@pytest.mark.parametrize(
    "over, criterion",
    [
        ({"critical_item_pass_rate": 0.5}, "critical_item_pass_rate"),
        ({"judge_error_rate": 0.5}, "judge_error_rate"),
        ({"avg_score_pct": 50.0}, "avg_score_pct"),
        ({"precheck_pass_rate": 0.1}, "precheck_pass_rate"),
    ],
)
def test_every_criterion_still_rejects_on_a_real_measurement(
    acceptance: dict, over: dict, criterion: str
) -> None:
    m = _metrics(**over)

    assert sweep.select_pareto_winner({"results": {"c": m}}, acceptance) is None
    assert _verdicts(m, acceptance)[criterion] == sweep.FAIL


# ── the reason is written down ───────────────────────────────────────


def test_no_winner_now_says_which_criterion_and_which_value(
    plan: sweep.Plan, tmp_path: Path
) -> None:
    """"No variant satisfied all acceptance thresholds" is not a diagnosis.

    An operator reading it cannot tell a fleet of bad graders from a check
    that never ran, and the two call for opposite responses.
    """
    progress = {
        "plan_name": plan.plan_name,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T01:00:00Z",
        "cumulative_cost_usd": 5.0,
        "completed": ["B_bad"],
        "results": {
            "B_bad": _metrics(name="B_bad", critical_item_pass_rate=0.42),
        },
        "winner": None,
    }
    target = tmp_path / "RESULTS.md"

    sweep.write_results_md(progress, None, plan, target)
    text = target.read_text(encoding="utf-8")

    assert "**No winner**" in text
    assert "B_bad" in text
    assert "critical_item_pass_rate" in text
    assert "0.42" in text


def test_no_winner_separates_what_failed_from_what_never_ran(
    plan: sweep.Plan, tmp_path: Path
) -> None:
    progress = {
        "plan_name": plan.plan_name,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T01:00:00Z",
        "cumulative_cost_usd": 5.0,
        "completed": ["B_bad"],
        "results": {
            "B_bad": _metrics(
                name="B_bad",
                critical_item_pass_rate=0.42,
                precheck_pass_rate=None,
                item_counts={"precheck_items": 0, "judge_items": 60},
            ),
        },
        "winner": None,
    }
    target = tmp_path / "RESULTS.md"

    sweep.write_results_md(progress, None, plan, target)
    text = target.read_text(encoding="utf-8")

    assert "not measured" in text
    assert "an absent measurement is not a failed one" in text


def test_a_winner_with_an_unmeasured_criterion_is_flagged_in_the_report(
    plan: sweep.Plan, tmp_path: Path
) -> None:
    m = _metrics(
        name="B_ok",
        precheck_pass_rate=None,
        item_counts={"precheck_items": 0, "judge_items": 8816},
    )
    progress = {
        "plan_name": plan.plan_name,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T01:00:00Z",
        "cumulative_cost_usd": 5.0,
        "completed": ["B_ok"],
        "results": {"B_ok": m},
        "winner": "B_ok",
    }
    winner = sweep.select_pareto_winner(progress, plan.acceptance)
    assert winner is not None
    target = tmp_path / "RESULTS.md"

    sweep.write_results_md(progress, winner, plan, target)
    text = target.read_text(encoding="utf-8")

    assert "NOT VERIFIED" in text
    assert "precheck_pass_rate" in text


def test_the_changelog_entry_carries_the_same_caveat(
    plan: sweep.Plan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CHANGELOG outlives the run directory; the caveat has to reach it.

    A line that says only "winner X, cost $Y" is the artifact somebody reads
    six months later when deciding whether X was validated.
    """
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- existing entry\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sweep, "CHANGELOG", changelog)
    winner = sweep.WinnerResult(
        name="B_ok",
        metrics=_metrics(
            name="B_ok",
            precheck_pass_rate=None,
            item_counts={"precheck_items": 0, "judge_items": 8816},
        ),
        rationale="test",
        unmeasured=["precheck_pass_rate"],
    )

    sweep.append_changelog_entry(winner, plan, REPO_ROOT / "runs" / "r1", 5.0)
    text = changelog.read_text(encoding="utf-8")

    assert "NOT VERIFIED" in text
    assert "precheck_pass_rate" in text
    assert "- existing entry" in text  # appended, not overwritten


# ── where the zeros came from ────────────────────────────────────────


def test_a_rate_over_zero_items_is_read_as_unmeasured() -> None:
    wow = {"precheck_pass_rate": 0.0, "item_counts": {"precheck_items": 0}}

    assert sweep._measured_rate(wow, "precheck_pass_rate") is None


def test_a_rate_over_real_items_is_read_as_measured() -> None:
    wow = {"precheck_pass_rate": 0.0, "item_counts": {"precheck_items": 40}}

    assert sweep._measured_rate(wow, "precheck_pass_rate") == 0.0


def test_a_grade_without_item_counts_keeps_its_rate() -> None:
    """Unknown is not zero -- the same substitution, pointed the other way.

    Payloads written before ``item_counts`` existed carry no denominator.
    Treating that as "measured over nothing" would silently stop applying
    every threshold to every historical grade.
    """
    assert sweep._measured_rate({"precheck_pass_rate": 0.83}, "precheck_pass_rate") == 0.83
    assert sweep._measured_rate({"judge_error_rate": 0.0}, "judge_error_rate") == 0.0


def test_a_rate_absent_from_the_grade_is_not_invented_as_zero() -> None:
    assert sweep._measured_rate({}, "precheck_pass_rate") is None
    assert sweep._measured_rate(None, "precheck_pass_rate") is None
    assert sweep._measured_rate({"precheck_pass_rate": "0.8"}, "precheck_pass_rate") is None
    assert sweep._measured_rate({"precheck_pass_rate": True}, "precheck_pass_rate") is None


def test_every_acceptance_rate_has_a_denominator_to_check() -> None:
    """The map from rate to denominator has to cover what the gate compares.

    A rate missing from ``RATE_DENOMINATORS`` silently keeps the old
    behaviour: its empty-denominator zero reaches the threshold as a real
    measurement and rejects.
    """
    assert set(sweep.RATE_DENOMINATORS) == {
        "critical_item_pass_rate",
        "judge_error_rate",
        "precheck_pass_rate",
    }


def test_extract_metrics_reads_a_real_grade_payload(tmp_path: Path) -> None:
    """Through the real function, on a payload shaped like the committed ones."""
    grade = {
        "summary": {
            "openai_compat": {"avg_score_pct": 79.53},
            "wow": {
                "critical_item_pass_rate": 0.64,
                "judge_error_rate": 0.0065,
                "precheck_pass_rate": 0.0,
                "item_counts": {"critical_items": 300, "judge_items": 8816,
                                "precheck_items": 0},
            },
            "cost": {"total_input_tokens": 100, "total_output_tokens": 50,
                     "total_judge_calls": 4, "total_judge_latency_sec": 12.0},
        }
    }
    path = tmp_path / "grade.json"
    path.write_text(json.dumps(grade), encoding="utf-8")
    variant = sweep.load_plan(PLAN_PATH).phase_b[0]

    m = sweep.extract_metrics(path, variant)

    assert m["precheck_pass_rate"] is None       # 0 items
    assert m["judge_error_rate"] == 0.0065       # 8,816 items
    assert m["critical_item_pass_rate"] == 0.64
    assert m["item_counts"]["precheck_items"] == 0


# ── runs that never graded anything ──────────────────────────────────


def test_a_crashed_variant_is_rejected_for_crashing(acceptance: dict) -> None:
    """Not by a stand-in error rate of 1.0.

    The old stub described a crash with ``judge_error_rate: 1.0`` and three
    zeros. It happened to be rejected, but by a fabricated number that a
    looser ``judge_error_rate_max`` would have let through -- with a
    fabricated 0.00 score printed beside it.
    """
    m = _metrics(
        name="boom",
        error="step8_grade.py exited 1",
        avg_score_pct=None,
        critical_item_pass_rate=None,
        judge_error_rate=None,
        precheck_pass_rate=None,
    )

    assert sweep.select_pareto_winner({"results": {"boom": m}}, acceptance) is None
    verdicts = _verdicts(m, acceptance)
    assert verdicts["graded"] == sweep.FAIL
    # ...and nothing else claims to have been checked.
    assert verdicts["avg_score_pct"] == sweep.UNMEASURED
    assert verdicts["critical_item_pass_rate"] == sweep.UNMEASURED


def test_an_absence_renders_as_absent_not_as_zero() -> None:
    """``0.00`` in the results table is a claim. It needs a measurement."""
    row = sweep._format_row(
        {"name": "dry", "avg_score_pct": None, "critical_item_pass_rate": None,
         "judge_error_rate": None, "judge_call_count": 0,
         "judge_total_latency_sec": 0.0, "smoke_cost_usd": 0.0,
         "full_run_cost_usd": 0.0}
    )

    assert "0.00 |" not in row.split("$")[0]
    assert row.count("n/a") == 3


def test_a_measured_zero_still_renders_as_zero() -> None:
    row = sweep._format_row(
        {"name": "real", "avg_score_pct": 0.0, "critical_item_pass_rate": 0.0,
         "judge_error_rate": 0.0, "judge_call_count": 3,
         "judge_total_latency_sec": 10.0, "smoke_cost_usd": 1.0,
         "full_run_cost_usd": 2.0}
    )

    assert "n/a" not in row
    assert "0.00" in row


# ── the second gate, and the frontier ────────────────────────────────


def test_phase_c_narrowing_does_not_drop_an_unmeasured_variant(
    acceptance: dict,
) -> None:
    """A silent elimination one step earlier than the winner gate.

    A variant dropped here is never repeated, never reaches the frontier, and
    never appears in the rejection table -- so the absence would disappear
    without leaving a trace anywhere.
    """
    unmeasured = _metrics(name="B_unmeasured", critical_item_pass_rate=None)
    genuinely_low = _metrics(name="B_low", critical_item_pass_rate=0.3)

    assert sweep._below_critical_min(unmeasured, acceptance) is False
    assert sweep._below_critical_min(genuinely_low, acceptance) is True


def test_an_unmeasured_axis_sorts_as_worst_not_best() -> None:
    """Otherwise "we never measured the error rate" would beat "0.1% errors".

    ``dict.get(ax, inf)`` returned ``None`` for a key that is present and
    null, which is neither the default nor comparable.
    """
    measured = {"name": "measured", "full_run_cost_usd": 100.0,
                "judge_error_rate": 0.001, "judge_total_latency_sec": 100.0}
    unmeasured = {"name": "unmeasured", "full_run_cost_usd": 100.0,
                  "judge_error_rate": None, "judge_total_latency_sec": 100.0}

    frontier = sweep.pareto_frontier(
        [measured, unmeasured],
        axes=["full_run_cost_usd", "judge_error_rate", "judge_total_latency_sec"],
    )

    assert [m["name"] for m in frontier] == ["measured"]


def test_the_stability_tiebreak_ignores_reps_that_never_scored() -> None:
    """Averaging a fabricated 0.0 into the spread invents instability.

    Three reps at ~78 plus one crashed rep recorded as 0.0 produce a standard
    deviation far over the 1.5 threshold, which would drop a stable winner.
    """
    acceptance = sweep.load_plan(PLAN_PATH).acceptance
    reps = {
        f"B_ok__rep{i}": _metrics(name="B_ok__rep" + str(i), phase="C",
                                  avg_score_pct=score)
        for i, score in enumerate((77.9, 78.0, 78.1))
    }
    reps["B_ok__rep3"] = _metrics(name="B_ok__rep3", phase="C",
                                  avg_score_pct=None, error="crashed")
    progress = {"results": {"B_ok": _metrics(name="B_ok"), **reps}}

    winner = sweep.select_pareto_winner(progress, acceptance)

    assert winner is not None
    assert winner.name == "B_ok"


# ── against the corpus the thresholds are applied to ─────────────────


@pytest.fixture(scope="module")
def gold_ceiling_wow() -> dict:
    """The 185-task run's published ``wow`` block, as committed."""
    if not GRADES_ROOT.exists():
        pytest.skip("no committed grades in this checkout")
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
            and len(payload.get("tasks") or []) == 185
        ):
            return payload["summary"]["wow"]
    pytest.skip("the gold-ceiling run is not in this checkout")


def test_the_real_run_the_gate_would_have_rejected(
    gold_ceiling_wow: dict, acceptance: dict
) -> None:
    """The committed payload, not a fixture.

    Its ``precheck_pass_rate`` is 0.0 and it is under the committed 0.7
    threshold. Whether that 0.0 is a measurement is exactly what the
    denominator decides, and this run judged 8,816 items and prechecked none.
    """
    assert gold_ceiling_wow["precheck_pass_rate"] == 0.0
    assert gold_ceiling_wow["precheck_pass_rate"] < acceptance["precheck_pass_rate_min"]
    assert gold_ceiling_wow["judge_pass_rate"] > 0.0
