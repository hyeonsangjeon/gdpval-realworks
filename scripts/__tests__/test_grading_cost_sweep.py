"""Unit tests for scripts/grading_cost_sweep.py (Track 2 dispatcher).

All tests are fully mocked — no real Azure API calls, no real step8_grade
invocation. Subprocess execution is patched to return a fabricated
grade.json shaped like the real schema v1.0 output.
"""

from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from unittest import mock

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Importing module under test.
from scripts import grading_cost_sweep as sweep  # noqa: E402

PLAN_PATH = REPO_ROOT / "tasks" / "0523_saturday" / "grading_cost_sweep_plan.yaml"


# ---------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------

def _fake_grade_json(
    variant_name: str,
    avg_pct: float = 78.0,
    critical: float = 1.0,
    err: float = 0.03,
    precheck: float = 0.85,
    calls: int = 14,
    in_tok: int = 20000,
    out_tok: int = 15000,
    latency: float = 1200.0,
) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "exp998_smoke_baseline_sample",
        "tasks": [],
        "summary": {
            "total_tasks": 3,
            "graded_tasks": 3,
            "error_tasks": 0,
            "openai_compat": {
                "avg_score_pct": avg_pct,
                "ci_pct": 5.0,
                "perfect_count": 0,
                "zero_count": 0,
                "partial_count": 3,
                "inconsistent_count": 0,
            },
            "wow": {
                "rubric_item_coverage_avg": 0.6,
                "critical_item_pass_rate": critical,
                "precheck_pass_rate": precheck,
                "judge_pass_rate": 0.6,
                "judge_error_rate": err,
                "by_sector": {},
                "by_rubric_category": {},
                "score_density_histogram": [],
                "rubric_severity_curve": [],
            },
            "cost": {
                "total_judge_calls": calls,
                "total_input_tokens": in_tok,
                "total_output_tokens": out_tok,
                "estimated_cost_usd": 0.0,
                "total_judge_latency_sec": latency,
            },
        },
    }


@pytest.fixture
def plan() -> sweep.Plan:
    return sweep.load_plan(PLAN_PATH)


# ---------------------------------------------------------------------
# 1. Plan loading
# ---------------------------------------------------------------------

def test_plan_loading_basic(plan):
    assert plan.schema_version == "1.0"
    assert plan.plan_name == "cost_opt_sweep_v1"
    assert len(plan.phase_a) == 15  # A1×4 + A2×3 + A3×4 + A4×4
    assert len(plan.phase_b) == 5
    assert plan.diversity is not None
    assert plan.fixed_benchmark["task_limit"] == 3


# ---------------------------------------------------------------------
# 2. Validation: unknown model
# ---------------------------------------------------------------------

def test_validate_models_unknown_rejects(plan):
    bogus = deepcopy(plan)
    bogus.phase_a[0].raw["judge"]["model"] = "gpt-9999"
    with pytest.raises(sweep.SweepValidationError, match="unknown model"):
        sweep.validate_models_available(bogus)


# ---------------------------------------------------------------------
# 3. TPM cap enforcement
# ---------------------------------------------------------------------

def test_validate_tpm_caps_70pct_enforced(plan):
    p = deepcopy(plan)
    # Force a violation: huge concurrency on gpt-5.4-pro (100k TPM, cap 70k).
    p.phase_a[0].raw.setdefault("tpm_guard", {})["max_concurrent"] = 500
    with pytest.raises(sweep.SweepValidationError, match="peak"):
        sweep.validate_tpm_caps(p)


# ---------------------------------------------------------------------
# 4. Cost estimator calibration vs exp998 baseline
# ---------------------------------------------------------------------

def test_estimate_cost_calibration(plan):
    # Baseline: gpt-5.4-pro, effort=high, batch=1, extract=4000 → ~$7.42 measured.
    baseline_variant = sweep.Variant(
        name="baseline_calibration",
        phase="A",
        raw={
            "name": "baseline_calibration",
            "judge": {
                "model": "gpt-5.4-pro",
                "deployment": "gpt-5.4-pro",
                "reasoning_effort": "high",
            },
            "grader": {"deliverable_extract_max_chars": 4000, "batch_size": 1},
        },
    )
    cost = sweep.estimate_variant_cost(baseline_variant, plan.fixed_benchmark)
    # ±30% tolerance: $5.18 - $9.65
    assert 5.18 <= cost <= 9.65, f"estimator out of band: ${cost:.2f}"


# ---------------------------------------------------------------------
# 5. render_temp_config enforces reproducibility guards
# ---------------------------------------------------------------------

def test_default_sweep_template_is_the_tracked_v1_archive():
    expected = (
        REPO_ROOT
        / "batch-runner"
        / "grading_configs"
        / "_archive_v1"
        / "_sweep_template.yaml"
    )

    assert sweep.SWEEP_TEMPLATE == expected
    assert expected.is_file()
    assert not (expected.parent.parent / "_sweep_template.yaml").exists()
    assert yaml.safe_load(expected.read_text(encoding="utf-8"))[
        "schema_version"
    ] == "1.0"


def test_render_temp_config_enforces_seed_temp(plan, tmp_path):
    variant = plan.phase_a[2]  # A1_pro_medium
    # Try to inject hostile overrides.
    variant.raw["judge"]["generation"] = {"temperature": 0.7, "seed": 999}
    cfg_path = sweep.render_temp_config(variant, tmp_path)
    rendered = yaml.safe_load(cfg_path.read_text())
    expected_variant_dir = (tmp_path / "runs" / variant.name).resolve()

    assert cfg_path.resolve() == expected_variant_dir / "config.yaml"
    assert rendered["config_name"] == f"sweep__{variant.name}"
    assert Path(rendered["output"]["directory"]) == expected_variant_dir
    assert rendered["judge"]["generation"]["temperature"] == 0
    assert rendered["judge"]["generation"]["seed"] == 42


# ---------------------------------------------------------------------
# 6. Pareto frontier
# ---------------------------------------------------------------------

def test_pareto_frontier_basic():
    pts = [
        {"name": "p1", "full_run_cost_usd": 100, "judge_error_rate": 0.01, "judge_total_latency_sec": 100},
        {"name": "p2", "full_run_cost_usd":  50, "judge_error_rate": 0.05, "judge_total_latency_sec":  50},
        {"name": "p3", "full_run_cost_usd": 200, "judge_error_rate": 0.10, "judge_total_latency_sec": 300},  # dominated by p1
        {"name": "p4", "full_run_cost_usd":  30, "judge_error_rate": 0.20, "judge_total_latency_sec":  40},
        {"name": "p5", "full_run_cost_usd": 150, "judge_error_rate": 0.005, "judge_total_latency_sec":  80},
    ]
    frontier = sweep.pareto_frontier(
        pts, axes=["full_run_cost_usd", "judge_error_rate", "judge_total_latency_sec"]
    )
    names = {p["name"] for p in frontier}
    assert names == {"p1", "p2", "p4", "p5"}
    assert "p3" not in names


# ---------------------------------------------------------------------
# 7. Winner selection: hard filter rejects below-threshold variant
# ---------------------------------------------------------------------

def test_select_winner_hard_filter():
    progress = {
        "results": {
            "v_cheap_bad_critical": {
                "name": "v_cheap_bad_critical", "phase": "B",
                "avg_score_pct": 77.5, "critical_item_pass_rate": 0.5,  # violates min
                "judge_error_rate": 0.02, "precheck_pass_rate": 0.85,
                "full_run_cost_usd": 20.0, "judge_total_latency_sec": 100,
            },
            "v_ok": {
                "name": "v_ok", "phase": "B",
                "avg_score_pct": 78.0, "critical_item_pass_rate": 1.0,
                "judge_error_rate": 0.03, "precheck_pass_rate": 0.85,
                "full_run_cost_usd": 100.0, "judge_total_latency_sec": 500,
            },
        }
    }
    acceptance = {
        "baseline_avg_score_pct": 77.83,
        "avg_score_delta_pp": 2.0,
        "critical_item_pass_rate_min": 1.0,
        "judge_error_rate_max": 0.05,
        "precheck_pass_rate_min": 0.7,
    }
    winner = sweep.select_pareto_winner(progress, acceptance)
    assert winner is not None
    assert winner.name == "v_ok"


# ---------------------------------------------------------------------
# 8. No eligible -> None, exit code 1
# ---------------------------------------------------------------------

def test_select_winner_no_eligible_returns_none():
    progress = {
        "results": {
            "v_bad": {
                "name": "v_bad", "phase": "B",
                "avg_score_pct": 50.0,  # too far from baseline
                "critical_item_pass_rate": 1.0,
                "judge_error_rate": 0.02,
                "precheck_pass_rate": 0.85,
                "full_run_cost_usd": 20.0,
                "judge_total_latency_sec": 100,
            },
        }
    }
    acceptance = {
        "baseline_avg_score_pct": 77.83,
        "avg_score_delta_pp": 2.0,
        "critical_item_pass_rate_min": 1.0,
        "judge_error_rate_max": 0.05,
        "precheck_pass_rate_min": 0.7,
    }
    assert sweep.select_pareto_winner(progress, acceptance) is None


# ---------------------------------------------------------------------
# 9. Resume skips completed
# ---------------------------------------------------------------------

def test_resume_skips_completed(plan, tmp_path):
    output_dir = tmp_path / "resume_test"
    output_dir.mkdir()
    progress_path = output_dir / "progress.json"
    progress = sweep.load_or_init_progress(progress_path, plan.plan_name)
    progress["completed"] = [
        plan.phase_a[0].name,
        plan.phase_a[1].name,
        plan.phase_a[2].name,
    ]
    sweep.save_progress(progress, progress_path)

    # Patch _run_variant to track which variants got executed.
    invoked: list[str] = []

    def fake_run_variant(variant, *args, **kwargs):
        invoked.append(variant.name)

    with mock.patch.object(sweep, "_run_variant", side_effect=fake_run_variant), \
         mock.patch.object(sweep, "_finalize"), \
         mock.patch.object(sweep, "_snapshot_plan"):
        rc = sweep.main([
            "--plan", str(PLAN_PATH),
            "--resume", str(output_dir),
            "--dry-run",
            "--phases", "A",
        ])

    skipped = {p.name for p in plan.phase_a[:3]}
    assert all(n not in invoked for n in skipped)
    assert plan.phase_a[3].name in invoked
    # rc may be 0 or 1 (no winner from skipped dry-run); we only care about skip logic.
    assert rc in (0, 1)


# ---------------------------------------------------------------------
# 10. Cost cap abort emits partial RESULTS.md, exit code 2
# ---------------------------------------------------------------------

def test_cost_cap_abort(plan, tmp_path, monkeypatch):
    output_dir = tmp_path / "abort_test"

    # Force estimate to be huge so the first variant trips the cap.
    monkeypatch.setattr(sweep, "estimate_variant_cost", lambda v, b: 999.0)

    with mock.patch.object(sweep, "_snapshot_plan"):
        rc = sweep.main([
            "--plan", str(PLAN_PATH),
            "--output-dir", str(output_dir),
            "--dry-run",
            "--max-cost", "5",
            "--phases", "A",
        ])

    assert rc == 2
    results_md = output_dir / "RESULTS.md"
    assert results_md.exists()
    text = results_md.read_text()
    assert "ABORTED" in text


# ---------------------------------------------------------------------
# 11. RESULTS.md skeleton sections present
# ---------------------------------------------------------------------

def test_results_md_skeleton_present(plan, tmp_path):
    output_dir = tmp_path / "skeleton_test"
    output_dir.mkdir()
    progress = {
        "plan_name": plan.plan_name,
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T01:00:00Z",
        "cumulative_cost_usd": 5.0,
        "completed": ["B2_std_med_b8"],
        "results": {
            "A1_pro_high": {
                "name": "A1_pro_high", "phase": "A",
                "avg_score_pct": 77.83, "critical_item_pass_rate": 1.0,
                "judge_error_rate": 0.05, "precheck_pass_rate": 0.85,
                "judge_call_count": 84, "judge_total_latency_sec": 8530,
                "judge_input_tokens": 137000, "judge_output_tokens": 89000,
                "smoke_cost_usd": 7.40, "full_run_cost_usd": 540.0,
            },
            "B2_std_med_b8": {
                "name": "B2_std_med_b8", "phase": "B",
                "avg_score_pct": 78.0, "critical_item_pass_rate": 1.0,
                "judge_error_rate": 0.03, "precheck_pass_rate": 0.85,
                "judge_call_count": 12, "judge_total_latency_sec": 800,
                "judge_input_tokens": 20000, "judge_output_tokens": 15000,
                "smoke_cost_usd": 0.85, "full_run_cost_usd": 62.0,
            },
            "B2_std_med_b8__rep0": {
                "name": "B2_std_med_b8__rep0", "phase": "C",
                "avg_score_pct": 77.9, "critical_item_pass_rate": 1.0,
                "judge_error_rate": 0.03, "precheck_pass_rate": 0.85,
                "judge_call_count": 12, "judge_total_latency_sec": 800,
                "smoke_cost_usd": 0.85, "full_run_cost_usd": 62.0,
            },
        },
        "winner": "B2_std_med_b8",
    }
    winner = sweep.WinnerResult(
        name="B2_std_med_b8",
        metrics=progress["results"]["B2_std_med_b8"],
        rationale="test",
    )
    sweep.write_results_md(progress, winner, plan, output_dir / "RESULTS.md")
    text = (output_dir / "RESULTS.md").read_text()
    for needed in ("TL;DR", "Phase A", "Phase B", "Phase C", "Winner Config"):
        assert needed in text, f"missing section: {needed}"


# ---------------------------------------------------------------------
# 12. winner_config.yaml has comment banner
# ---------------------------------------------------------------------

def test_winner_config_has_comment_banner(plan, tmp_path):
    output_dir = tmp_path / "winner_banner_test"
    variant = plan.phase_b[1]  # B2_std_med_b8
    sweep.render_temp_config(variant, output_dir)

    winner = sweep.WinnerResult(
        name=variant.name,
        metrics={"full_run_cost_usd": 60.0, "avg_score_pct": 78.0},
        rationale="test",
    )
    target = output_dir / "winner_config.yaml"
    sweep.write_winner_config(winner, output_dir, target)

    text = target.read_text()
    first_line = text.splitlines()[0]
    assert first_line.startswith("# Auto-generated winner")
    # Ensure the body config is still a valid YAML grading config below the banner.
    cfg = yaml.safe_load(text)
    assert cfg["schema_version"] == "1.0"
    assert cfg["judge"]["generation"]["temperature"] == 0
    assert cfg["judge"]["generation"]["seed"] == 42
