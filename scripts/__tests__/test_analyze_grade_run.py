"""Unit tests for scripts/analyze_grade_run.py — sanity that key metrics
(wall-clock, latency, token totals, cost-estimate mode) are computed
correctly from a synthetic grade JSON.

These are not full-coverage tests; they exercise the happy paths for
the two cost modes (single judge model vs hybrid routing) and the
top-5-slowest selection.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "analyze_grade_run.py"
ANCHOR_PAYLOAD = (
    REPO_ROOT
    / "data/grades/_diagnostic/"
    "29d5623a5cec85eb38f21fb73a2f3b06c66ed6a5fd6fd95948b979cd70a70bc9/"
    "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_6-sol__"
    "validation_exp003_v2_sol_max_anchor4__cfg_7f3c7c2e542cf580__rubric_"
    "11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_"
    "9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_"
    "b00e83209ab6ca93__v2.2.json"
)
ANCHOR_ANALYSIS = ANCHOR_PAYLOAD.with_name(
    "grade__233124fc9c26e453b906d82429fc0f6387a14c70586639ad428685146e5b4da0."
    "analysis.md"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_grade_run", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _task(tid: str, lat_ms: int, in_tok: int, out_tok: int, calls: int = 5, pct: float = 80.0):
    return {
        "task_id": tid,
        "pct": pct,
        "critical_fail": False,
        "judge_call_count": calls,
        "precheck_count": 1,
        "judge_total_latency_ms": lat_ms,
        "judge_input_tokens": in_tok,
        "judge_output_tokens": out_tok,
        "graded_at": "2026-05-27T00:00:00Z",
        "items": [],
    }


def _grade_json(*, model: str = "gpt-5.4-mini", routing: dict | None = None, n_tasks: int = 3) -> dict:
    tasks = [
        _task(f"t{i:02d}", lat_ms=10000 + i * 1000, in_tok=10000, out_tok=2000) for i in range(n_tasks)
    ]
    # vary graded_at so wall-clock span is non-zero
    for i, t in enumerate(tasks):
        t["graded_at"] = f"2026-05-27T00:{i:02d}:00Z"
    judge_block = {"model": model, "config_name": "test", "reasoning_effort": "medium"}
    if routing:
        judge_block["routing"] = routing
    return {
        "experiment_yaml_name": "exp_test",
        "judge": judge_block,
        "tasks": tasks,
        "summary": {
            "total_tasks": n_tasks,
            "graded_tasks": n_tasks,
            "error_tasks": 0,
            "openai_compat": {"avg_score_pct": 80.0},
            "wow": {
                "critical_item_pass_rate": 1.0,
                "judge_pass_rate": 0.9,
                "judge_error_rate": 0.0,
                "precheck_pass_rate": 0.8,
            },
            "cost": {},
        },
    }


def _run(tmp_path: Path, grade: dict, *, as_json: bool = True) -> dict | str:
    p = tmp_path / "g.json"
    p.write_text(json.dumps(grade))
    args = [sys.executable, str(SCRIPT), str(p)]
    if as_json:
        args.append("--json")
        result = subprocess.run(args, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    else:
        out_md = tmp_path / "out.md"
        args += ["--out", str(out_md)]
        result = subprocess.run(args, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return out_md.read_text()


def test_single_model_cost_is_nonzero(tmp_path: Path):
    out = _run(tmp_path, _grade_json(model="gpt-5.4-mini", n_tasks=3))
    a = out["this"]
    assert a["graded_tasks"] == 3
    assert a["total_input_tokens"] == 30000
    assert a["total_output_tokens"] == 6000
    cost = a["cost_estimate"]
    assert cost["mode"] == "single"
    assert cost["model"] == "gpt-5.4-mini"
    # 30k in * $0.25/M + 6k out * $1.00/M = $0.0075 + $0.006 = $0.0135
    assert cost["cost_usd"] > 0.01
    assert cost["cost_usd"] < 0.02


def test_sol_max_and_audio_remain_explicitly_unpriced(tmp_path: Path):
    grade = _grade_json(model="gpt-5.6-sol", n_tasks=1)
    grade["judge"]["reasoning_effort"] = "max"
    grade["judge"]["perception"] = {
        "visual": {"model": "gpt-5.6-sol"},
        "audio": {"model": "gpt-audio-1.5"},
    }
    task = grade["tasks"][0]
    task.update({
        "judge_cached_tokens": 100,
        "perception_call_count": 1,
        "perception_input_tokens": 1_000,
        "perception_output_tokens": 100,
        "perception_cached_tokens": 10,
    })
    task["items"] = [{
        "routing_modality": "audio",
        "perception_input_tokens": 1_000,
        "perception_output_tokens": 100,
        "perception_cached_tokens": 10,
    }]

    analyzed = _run(tmp_path, grade)["this"]
    raw = analyzed["cost_estimate"]
    effective = analyzed["effective_cost"]

    assert raw["pricing_complete"] is False
    assert raw["cost_usd"] is None
    assert raw["unpriced_models"] == ["gpt-5.6-sol", "gpt-audio-1.5"]
    assert effective["pricing_complete"] is False
    assert effective["total_usd"] is None
    assert effective["unpriced_models"] == ["gpt-5.6-sol", "gpt-audio-1.5"]

    markdown = _run(tmp_path, grade, as_json=False)
    assert "$0.00" not in markdown
    assert "unpriced" in markdown


def test_perception_usage_is_included_and_reported_separately(tmp_path: Path):
    grade = _grade_json(model="gpt-5.4", n_tasks=1)
    task = grade["tasks"][0]
    task.update({
        "judge_call_count": 2,
        "judge_input_tokens": 100,
        "judge_output_tokens": 20,
        "judge_cached_tokens": 10,
        "judge_total_latency_ms": 40,
        "perception_call_count": 3,
        "perception_input_tokens": 60,
        "perception_output_tokens": 15,
        "perception_cached_tokens": 6,
        "perception_total_latency_ms": 30,
        "render_call_count": 3,
        "render_total_latency_ms": 12,
        "usage_complete": True,
    })

    analyzed = _run(tmp_path, grade)["this"]

    assert analyzed["total_judge_calls"] == 5
    assert analyzed["total_main_judge_calls"] == 2
    assert analyzed["total_perception_calls"] == 3
    assert analyzed["total_input_tokens"] == 160
    assert analyzed["total_output_tokens"] == 35
    assert analyzed["total_cached_tokens"] == 16
    assert analyzed["main_input_tokens"] == 100
    assert analyzed["perception_input_tokens"] == 60
    assert analyzed["top5_slowest"][0]["latency_sec"] == 0.07
    assert analyzed["total_render_calls"] == 3
    assert analyzed["usage_complete"] is True
    assert analyzed["cost_estimate"]["cost_usd"] is None
    assert analyzed["cost_estimate"]["pricing_complete"] is False
    assert "unknown_perception_model" in (
        analyzed["cost_estimate"]["unpriced_models"]
    )


def test_visual_perception_uses_its_own_model_price(tmp_path: Path):
    grade = _grade_json(model="gpt-5.4-mini", n_tasks=1)
    grade["judge"]["perception"] = {"visual": {"model": "gpt-5.4"}}
    task = grade["tasks"][0]
    task.update({
        "perception_call_count": 1,
        "perception_input_tokens": 1_000_000,
        "perception_output_tokens": 0,
        "perception_cached_tokens": 0,
        "perception_total_latency_ms": 10,
    })
    task["items"] = [{
        "routing_modality": "visual",
        "perception_input_tokens": 1_000_000,
        "perception_output_tokens": 0,
        "perception_cached_tokens": 0,
    }]

    cost = _run(tmp_path, grade)["this"]["cost_estimate"]

    assert cost["mode"] == "main_plus_perception"
    visual = cost["perception"][0]
    assert visual["model"] == "gpt-5.4"
    assert visual["input_usd"] == 1.25
    assert cost["pricing_complete"] is True


def test_mixed_parent_prices_visual_child_with_visual_model(tmp_path: Path):
    grade = _grade_json(model="gpt-5.4-mini", n_tasks=1)
    grade["judge"]["perception"] = {"visual": {"model": "gpt-5.4"}}
    task = grade["tasks"][0]
    task.update({
        "perception_call_count": 1,
        "perception_input_tokens": 1_000_000,
        "perception_output_tokens": 0,
        "perception_cached_tokens": 0,
        "perception_total_latency_ms": 10,
    })
    task["items"] = [{
        "routing_modality": "mixed",
        "perception_input_tokens": 1_000_000,
        "perception_output_tokens": 0,
        "perception_cached_tokens": 0,
        "child_grades": [
            {"routing_modality": "formatting"},
            {
                "routing_modality": "visual",
                "perception_input_tokens": 1_000_000,
                "perception_output_tokens": 0,
                "perception_cached_tokens": 0,
            },
        ],
    }]

    cost = _run(tmp_path, grade)["this"]["cost_estimate"]

    assert cost["mode"] == "main_plus_perception"
    assert len(cost["perception"]) == 1
    assert cost["perception"][0]["modality"] == "visual"
    assert cost["perception"][0]["model"] == "gpt-5.4"
    assert cost["perception"][0]["input_usd"] == 1.25


def test_unknown_perception_tokens_are_unpriced_and_visible(tmp_path: Path):
    grade = _grade_json(model="gpt-5.4-mini", n_tasks=1)
    task = grade["tasks"][0]
    task.update({
        "perception_call_count": 1,
        "perception_input_tokens": 1_000_000,
        "perception_output_tokens": 100,
        "perception_cached_tokens": 10,
        "perception_total_latency_ms": 5_000,
    })
    task["items"] = []

    analyzed = _run(tmp_path, grade)["this"]
    markdown = _run(tmp_path, grade, as_json=False)

    assert analyzed["cost_estimate"]["pricing_complete"] is False
    assert analyzed["cost_estimate"]["cost_usd"] is None
    assert "unknown_perception_model" in (
        analyzed["cost_estimate"]["unpriced_models"]
    )
    assert analyzed["effective_cost"]["pricing_complete"] is False
    assert analyzed["effective_cost"]["total_usd"] is None
    unknown = analyzed["task_anchors"][0]["unknown_perception"]
    assert unknown["call_count"] == 1
    assert unknown["input_tokens"] == 1_000_000
    assert unknown["latency_sec"] == 5.0
    assert "unknown perception calls/tokens/latency" in markdown
    assert "1 / 1000000,100,10 / 5.0s" in markdown


def test_routing_emits_blended_estimate(tmp_path: Path):
    routing = {
        "tier_pro": {"model": "gpt-5.4-pro"},
        "tier_standard": {"model": "gpt-5.4"},
        "tier_mini": {"model": "gpt-5.4-mini"},
    }
    out = _run(tmp_path, _grade_json(model="gpt-5.4-hybrid", routing=routing, n_tasks=3))
    cost = out["this"]["cost_estimate"]
    assert cost["mode"] == "routing_blended_estimate"
    # min (cheapest = mini) < max (most expensive = pro)
    assert cost["cost_usd_min"] < cost["cost_usd_max"]
    assert set(cost["tier_models"]) == {"gpt-5.4-pro", "gpt-5.4", "gpt-5.4-mini"}


def test_wall_clock_computed_from_graded_at_span(tmp_path: Path):
    # tasks at 00:00, 00:01, 00:02 → span 2 minutes
    out = _run(tmp_path, _grade_json(n_tasks=3))
    a = out["this"]
    assert a["wall_clock_min"] == 2.0


def test_top5_slowest_sorted_desc(tmp_path: Path):
    out = _run(tmp_path, _grade_json(n_tasks=3))
    top = out["this"]["top5_slowest"]
    # latencies were 10s, 11s, 12s → top is t02 (12s)
    assert top[0]["task_id"] == "t02"
    assert top[0]["latency_sec"] == 12.0
    assert top[-1]["latency_sec"] <= top[0]["latency_sec"]


def test_null_headline_remains_unscored_in_json_and_markdown(tmp_path: Path):
    grade = _grade_json(n_tasks=1)
    grade["summary"]["graded_tasks"] = 0
    grade["summary"]["error_tasks"] = 1
    grade["summary"]["openai_compat"]["avg_score_pct"] = None
    grade["tasks"][0]["error"] = "all_items_score_excluded"

    analyzed = _run(tmp_path, grade)["this"]
    markdown = _run(tmp_path, grade, as_json=False)

    assert analyzed["avg_score_pct"] is None
    assert "avg_score_pct: **unscored**" in markdown
    assert "avg_score_pct: **None**" not in markdown


def test_task_anchor_separates_main_visual_audio_and_error_types(tmp_path: Path):
    grade = _grade_json(model="gpt-5.6-sol", n_tasks=1)
    grade["judge"]["perception"] = {
        "visual": {"model": "gpt-5.6-sol"},
        "audio": {"model": "gpt-audio-1.5"},
    }
    task = grade["tasks"][0]
    task.update({
        "grading_wall_time_ms": 123_000,
        "judge_call_count": 2,
        "judge_input_tokens": 1_000,
        "judge_output_tokens": 100,
        "judge_cached_tokens": 400,
        "judge_total_latency_ms": 50_000,
        "perception_call_count": 3,
        "perception_input_tokens": 500,
        "perception_output_tokens": 50,
        "perception_cached_tokens": 20,
        "perception_total_latency_ms": 30_000,
        "render_call_count": 2,
        "render_total_latency_ms": 2_000,
        "usage_complete": True,
    })
    task["items"] = [
        {
            "routing_modality": "visual",
            "verdict": "pass",
            "perception_call_count": 2,
            "perception_input_tokens": 300,
            "perception_output_tokens": 30,
            "perception_cached_tokens": 10,
            "perception_total_latency_ms": 20_000,
        },
        {
            "routing_modality": "audio",
            "verdict": "judge_error",
            "evidence": "provider_error:RateLimitError",
            "score_excluded": True,
            "perception_call_count": 1,
            "perception_input_tokens": 200,
            "perception_output_tokens": 20,
            "perception_cached_tokens": 10,
            "perception_total_latency_ms": 10_000,
        },
        {
            "routing_modality": "mixed",
            "verdict": "judge_error",
            "evidence": "split_children: see child_grades",
            "score_excluded": True,
            "child_grades": [
                {
                    "verdict": "judge_error",
                    "evidence": "final_json_parse_failed",
                },
                {"verdict": "pass", "evidence": "verified"},
            ],
        },
    ]
    grade["summary"]["wow"]["judge_error_rate"] = 0.5

    analyzed = _run(tmp_path, grade)["this"]
    markdown = _run(tmp_path, grade, as_json=False)
    anchor = analyzed["task_anchors"][0]

    assert anchor["wall_clock_sec"] == 123.0
    assert anchor["main"] == {
        "call_count": 2,
        "input_tokens": 1_000,
        "output_tokens": 100,
        "cached_tokens": 400,
        "latency_sec": 50.0,
    }
    assert anchor["visual"]["call_count"] == 2
    assert anchor["visual"]["input_tokens"] == 300
    assert anchor["audio"]["call_count"] == 1
    assert anchor["audio"]["input_tokens"] == 200
    assert anchor["judge_error_types"] == {
        "RateLimitError": 1,
        "final_json_parse_failed": 1,
    }
    assert analyzed["judge_error_types"] == {
        "RateLimitError": 1,
        "final_json_parse_failed": 1,
    }
    assert analyzed["projected_220_wall_hours"] == 7.52
    assert analyzed["projection_status"] == "below_44h_envelope"
    assert "## Task anchors" in markdown
    assert "final_json_parse_failed:1" in markdown
    assert "RateLimitError:1" in markdown
    assert "50.0s" in markdown
    assert "20.0s" in markdown
    assert "10.0s" in markdown
    assert "projected_220_wall_hours: 7.52" in markdown


def _anchor4_projection_grade() -> dict:
    config_path = (
        REPO_ROOT
        / "batch-runner/grading_configs/validation_exp003_v2_sol_max_anchor4.yaml"
    )
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    identity = config["rerun_identity"]
    task_ids = identity["task_ids"]
    source_judge = config["judge"]
    grade = _grade_json(model="gpt-5.6-sol", n_tasks=4)
    for task, task_id in zip(grade["tasks"], task_ids, strict=True):
        task.update({
            "task_id": task_id,
            "sector": "test-sector",
            "occupation": "test-occupation",
            "total_awarded": 1,
            "total_max": 1,
            "pct": 100,
            "critical_fail": False,
            "gold_referenced": False,
            "grading_wall_time_ms": 100_000,
            "judge_call_count": 5,
            "precheck_count": 0,
            "judge_total_latency_ms": 50_000,
            "perception_call_count": 0,
            "perception_input_tokens": 0,
            "perception_output_tokens": 0,
            "perception_cached_tokens": 0,
            "perception_total_latency_ms": 0,
            "usage_complete": True,
            "error": None,
            "items": [],
        })
    task_hash = hashlib.sha256(
        json.dumps(task_ids, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    route_fingerprint = "f" * 64
    grade.update({
        "schema_version": "1.3",
        "run_status": "diagnostic",
        "expected_task_count": 4,
        "expected_ordered_task_ids_sha256": task_hash,
        "experiment_id": identity["experiment_id"],
        "experiment_yaml_name": identity["experiment_id"],
        "source_inference_experiment_id": identity["experiment_id"],
        "source_inference_repo_id": config["anchor_projection"][
            "anchor_source_inference_repo_id"
        ],
        "source_inference_revision": identity["inference_revision"],
        "azure_ai_routes": [{
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": route_fingerprint,
            "workload": "grader",
        }],
        "azure_ai_runtime_fingerprint": route_fingerprint,
        "grader_source_hash": "e" * 64,
        "anchor_projection": config["anchor_projection"],
        "rubric": {
            "source": config["rubric"]["source"],
            "repo_id": config["rubric"]["repo_id"],
            "revision": config["rubric"]["revision"],
            "commit_sha": identity["rubric_commit_sha"],
            "short_sha": identity["rubric_commit_sha"][:7],
        },
        "prompt": {
            "template": config["prompt"]["template"],
            "version": config["prompt"]["version"],
        },
        "graded_at": "2026-05-27T00:04:00Z",
        "graded_by": "step8_grade.py",
    })
    grade["judge"] = {
        "provider": source_judge["provider"],
        "api": source_judge["api"],
        "model": source_judge["model"],
        "deployment": source_judge["deployment"],
        "api_version": source_judge["api_version"],
        "reasoning_effort": source_judge["reasoning"]["effort"],
        "temperature": source_judge["generation"]["temperature"],
        "seed": source_judge["generation"]["seed"],
        "perception": source_judge["perception"],
        "config_name": config["config_name"],
        "config_hash": hashlib.sha256(config_bytes).hexdigest()[:16],
    }
    first = grade["tasks"][0]
    first.update({
        "perception_call_count": 3,
        "perception_input_tokens": 1_500,
        "perception_output_tokens": 150,
        "perception_cached_tokens": 30,
        "perception_total_latency_ms": 150_000,
    })
    first["items"] = [
        {
            "rubric_item_id": "visual-1",
            "criterion": "visual",
            "max_score": 1,
            "awarded_score": 1,
            "routing_modality": "visual",
            "verdict": "pass",
            "decided_by": "judge",
            "required": None,
            "evidence": "verified",
            "precheck_pattern_id": None,
            "perception_call_count": 2,
            "perception_input_tokens": 1_000,
            "perception_output_tokens": 100,
            "perception_cached_tokens": 20,
            "perception_total_latency_ms": 100_000,
            "usage_complete": True,
        },
        {
            "rubric_item_id": "audio-1",
            "criterion": "audio",
            "max_score": 1,
            "awarded_score": 1,
            "routing_modality": "audio",
            "verdict": "pass",
            "decided_by": "judge",
            "required": None,
            "evidence": "verified",
            "precheck_pattern_id": None,
            "perception_call_count": 1,
            "perception_input_tokens": 500,
            "perception_output_tokens": 50,
            "perception_cached_tokens": 10,
            "perception_total_latency_ms": 50_000,
            "usage_complete": True,
        },
        {
            "rubric_item_id": "text-1",
            "criterion": "text",
            "max_score": 1,
            "awarded_score": 0,
            "routing_modality": "text",
            "verdict": "judge_error",
            "decided_by": "judge",
            "required": None,
            "evidence": "final_json_parse_failed",
            "precheck_pattern_id": None,
            "score_excluded": True,
            "usage_complete": True,
        },
    ]
    grade["summary"] = {
        "total_tasks": 4,
        "graded_tasks": 4,
        "error_tasks": 0,
        "openai_compat": {
            "avg_score_pct": 100,
            "ci_pct": 0,
            "perfect_count": 4,
            "zero_count": 0,
            "partial_count": 0,
            "inconsistent_count": 0,
        },
        "wow": {
            "critical_item_pass_rate": 1.0,
            "judge_pass_rate": 0.6667,
            "judge_error_rate": 0.3333,
            "precheck_pass_rate": 0.0,
        },
        "cost": {
            "estimated_cost_usd": None,
            "pricing_complete": False,
            "unpriced_models": ["gpt-5.6-sol", "gpt-audio-1.5"],
            "usage_complete": True,
        },
    }
    return grade


def test_anchor4_projection_separates_modalities_and_preregistered_gates(
    tmp_path: Path,
):
    analyzed = _run(tmp_path, _anchor4_projection_grade())["this"]
    markdown = _run(tmp_path, _anchor4_projection_grade(), as_json=False)
    projection = analyzed["modality_projection"]

    assert analyzed["projection_method"] == "modality_normalized_v1"
    assert projection["baseline_is_like_for_like"] is False
    assert "main-judge-only reference" in projection["baseline_caveat"]
    assert projection["components"]["main"] == {
        "anchor_latency_sec": 250.0,
        "scale": 55.0,
        "projected_hours": 3.8194,
        "normalization": "task_count",
        "measurement": "max(main_latency, measured_wall_minus_perception)",
    }
    assert projection["components"]["visual"]["scale"] == pytest.approx(
        337 / 43,
        abs=1e-6,
    )
    assert projection["components"]["visual"]["projected_hours"] == 0.2177
    assert projection["components"]["audio"]["scale"] == pytest.approx(
        58 / 13,
        abs=1e-6,
    )
    assert projection["components"]["audio"]["projected_hours"] == 0.062
    assert projection["projected_220_hours"] == 4.0991
    assert projection["envelope_status"] == "below_44h_envelope"
    assert projection["audio_wiring"] == {"call_count": 1, "status": "passed"}
    assert projection["visual_budget"] == {
        "task_visual_budget_exceeded": 0,
        "status": "passed",
    }
    assert projection["diagnostic"] == {
        "baseline_targetable_errors": 22,
        "observed_targetable_errors": 1,
        "targetable_status": "improved",
        "non_targetable_errors": {},
        "status": "improved",
    }
    assert projection["full_run_gate"] == {
        "status": "eligible_for_owner_review",
        "blockers": [],
    }
    assert "not a Sol Max multiplier" in markdown
    assert "| visual | 100.0 |" in markdown
    assert "| audio | 50.0 |" in markdown


def test_anchor4_projection_blocks_dead_audio_and_visual_budget_error(
    tmp_path: Path,
):
    grade = _anchor4_projection_grade()
    first = grade["tasks"][0]
    first["perception_call_count"] = 2
    first["perception_input_tokens"] = 1_000
    first["perception_output_tokens"] = 100
    first["perception_cached_tokens"] = 20
    first["perception_total_latency_ms"] = 100_000
    first["items"] = [
        item for item in first["items"]
        if item.get("routing_modality") != "audio"
    ]
    first["items"].append({
        "rubric_item_id": "visual-budget-1",
        "criterion": "visual budget",
        "max_score": 1,
        "awarded_score": 0,
        "routing_modality": "visual",
        "verdict": "judge_error",
        "decided_by": "judge",
        "required": None,
        "evidence": "task_visual_budget_exceeded:required=73,cap=72",
        "precheck_pattern_id": None,
        "score_excluded": True,
        "usage_complete": True,
    })

    projection = _run(tmp_path, grade)["this"]["modality_projection"]

    assert projection["audio_wiring"] == {
        "call_count": 0,
        "status": "failed_no_audio_calls",
    }
    assert projection["visual_budget"] == {
        "task_visual_budget_exceeded": 1,
        "status": "failed",
    }
    assert projection["full_run_gate"] == {
        "status": "blocked",
        "blockers": [
            "non_targetable_judge_errors_present",
            "audio_wiring_not_exercised",
            "visual_budget_exceeded",
        ],
    }


def test_anchor4_projection_blocks_44h_or_unknown_perception(tmp_path: Path):
    over_time = _anchor4_projection_grade()
    for task in over_time["tasks"]:
        task["grading_wall_time_ms"] = 1_000_000
    projection = _run(tmp_path, over_time)["this"]["modality_projection"]
    assert projection["envelope_status"] == "at_or_above_44h_envelope"
    assert "at_or_above_44h_envelope" in projection["full_run_gate"]["blockers"]

    unknown = _anchor4_projection_grade()
    unknown_task = unknown["tasks"][1]
    unknown_task.update({
        "perception_call_count": 1,
        "perception_input_tokens": 100,
        "perception_output_tokens": 10,
        "perception_cached_tokens": 0,
        "perception_total_latency_ms": 5_000,
    })
    projection = _run(tmp_path, unknown)["this"]["modality_projection"]
    assert projection["envelope_status"] == "incomplete_unknown_perception"
    assert projection["full_run_gate"]["status"] == "blocked"
    assert "incomplete_unknown_perception" in projection["full_run_gate"]["blockers"]


@pytest.mark.parametrize(
    ("mutation", "blocker"),
    [
        (
            lambda grade: (
                grade.__setitem__("run_status", "partial"),
                grade.__setitem__("tasks", grade["tasks"][:2]),
            ),
            "anchor_run_not_complete_diagnostic",
        ),
        (
            lambda grade: grade.__setitem__(
                "expected_ordered_task_ids_sha256", "0" * 64
            ),
            "anchor_ordered_task_identity_mismatch",
        ),
        (
            lambda grade: grade["tasks"][1].__setitem__(
                "usage_complete", False
            ),
            "anchor_usage_incomplete",
        ),
        (
            lambda grade: grade["tasks"][1].__setitem__(
                "error", "provider_error"
            ),
            "anchor_task_errors",
        ),
        (
            lambda grade: grade["tasks"][0]["items"][0].__setitem__(
                "usage_complete", False
            ),
            "anchor_item_usage_incomplete",
        ),
        (
            lambda grade: grade["summary"]["cost"].__setitem__(
                "usage_complete", False
            ),
            "anchor_summary_usage_incomplete",
        ),
        (
            lambda grade: grade.pop("rubric"),
            "anchor_schema_invalid",
        ),
        (
            lambda grade: grade["anchor_projection"].__setitem__(
                "anchor_task_count", "4"
            ),
            "anchor_schema_invalid",
        ),
        (
            lambda grade: grade["anchor_projection"].__setitem__(
                "anchor_visual_criteria", 0
            ),
            "anchor_schema_invalid",
        ),
        (
            lambda grade: grade["anchor_projection"].pop(
                "anchor_task_count"
            ),
            "anchor_schema_invalid",
        ),
        (
            lambda grade: grade["judge"].__setitem__(
                "model", "gpt-5.4-mini"
            ),
            "anchor_runtime_identity_mismatch",
        ),
        (
            lambda grade: grade["judge"].__setitem__(
                "config_hash", "0" * 16
            ),
            "anchor_config_identity_mismatch",
        ),
        (
            lambda grade: grade["rubric"].__setitem__(
                "source", "local"
            ),
            "anchor_source_identity_mismatch",
        ),
        (
            lambda grade: grade["rubric"].__setitem__(
                "repo_id", "other/rubric"
            ),
            "anchor_source_identity_mismatch",
        ),
        (
            lambda grade: grade.__setitem__(
                "source_inference_experiment_id", "other_experiment"
            ),
            "anchor_source_identity_mismatch",
        ),
        (
            lambda grade: grade.__setitem__(
                "source_inference_repo_id", "other/repo"
            ),
            "anchor_source_identity_mismatch",
        ),
    ],
)
def test_anchor4_projection_requires_complete_clean_identity(
    tmp_path: Path,
    mutation,
    blocker: str,
):
    grade = _anchor4_projection_grade()
    mutation(grade)

    projection = _run(tmp_path, grade)["this"]["modality_projection"]

    assert projection["projected_220_hours"] is None
    assert projection["envelope_status"] == "incomplete_anchor_payload"
    assert projection["anchor_integrity"]["status"] == "failed"
    assert blocker in projection["full_run_gate"]["blockers"]
    assert projection["full_run_gate"]["status"] == "blocked"
    assert projection["diagnostic"]["targetable_status"] == (
        "inconclusive_invalid_anchor_payload"
    )
    assert projection["diagnostic"]["status"] == (
        "inconclusive_invalid_anchor_payload"
    )


def test_anchor4_projection_blocks_non_object_contract(tmp_path: Path):
    grade = _anchor4_projection_grade()
    grade["anchor_projection"] = "malformed"

    analyzed = _run(tmp_path, grade)["this"]
    projection = analyzed["modality_projection"]

    assert analyzed["projected_220_wall_hours"] is None
    assert analyzed["projection_status"] == "incomplete_anchor_payload"
    assert analyzed["projection_method"] is None
    assert projection["anchor_integrity"] == {
        "status": "failed",
        "blockers": ["anchor_schema_invalid"],
    }
    assert projection["diagnostic"]["status"] == (
        "inconclusive_invalid_anchor_payload"
    )
    assert projection["full_run_gate"] == {
        "status": "blocked",
        "blockers": ["anchor_schema_invalid"],
    }


@pytest.mark.parametrize("contract_state", ["missing", "null"])
def test_anchor4_projection_blocks_missing_or_null_contract(
    tmp_path: Path,
    contract_state: str,
):
    grade = _anchor4_projection_grade()
    if contract_state == "missing":
        grade.pop("anchor_projection")
    else:
        grade["anchor_projection"] = None

    analyzed = _run(tmp_path, grade)["this"]
    projection = analyzed["modality_projection"]

    assert analyzed["projected_220_wall_hours"] is None
    assert analyzed["projection_status"] == "incomplete_anchor_payload"
    assert analyzed["projection_method"] == "modality_normalized_v1"
    assert projection["diagnostic"]["status"] == (
        "inconclusive_invalid_anchor_payload"
    )
    assert "anchor_projection_missing_or_null" in (
        projection["full_run_gate"]["blockers"]
    )
    assert projection["full_run_gate"]["status"] == "blocked"


def test_anchor4_projection_hash_identity_blocks_missing_contract(
    tmp_path: Path,
):
    grade = _anchor4_projection_grade()
    grade.pop("anchor_projection")
    grade["judge"]["config_name"] = "renamed_anchor"

    projection = _run(tmp_path, grade)["this"]["modality_projection"]

    assert projection["projected_220_hours"] is None
    assert "anchor_projection_missing_or_null" in (
        projection["full_run_gate"]["blockers"]
    )
    assert "anchor_config_identity_mismatch" in (
        projection["full_run_gate"]["blockers"]
    )


@pytest.mark.parametrize("contract_state", ["missing", "null"])
def test_non_anchor_payload_keeps_task_count_fallback(
    tmp_path: Path,
    contract_state: str,
):
    grade = _grade_json(n_tasks=1)
    grade["tasks"][0]["grading_wall_time_ms"] = 1_000
    if contract_state == "null":
        grade["anchor_projection"] = None

    analyzed = _run(tmp_path, grade)["this"]

    assert analyzed["modality_projection"] is None
    assert analyzed["projection_method"] == "task_count_fallback"
    assert analyzed["projected_220_wall_hours"] is not None


@pytest.mark.parametrize("error_type", ["RateLimitError", "BadRequestError", "unknown"])
def test_anchor4_projection_blocks_non_targetable_judge_errors(
    tmp_path: Path,
    error_type: str,
):
    grade = _anchor4_projection_grade()
    grade["tasks"][0]["items"][2]["evidence"] = error_type

    projection = _run(tmp_path, grade)["this"]["modality_projection"]
    markdown = _run(tmp_path, grade, as_json=False)

    assert projection["diagnostic"]["observed_targetable_errors"] == 0
    assert projection["diagnostic"]["targetable_status"] == (
        "inconclusive_other_judge_errors"
    )
    assert projection["diagnostic"]["status"] == (
        "inconclusive_other_judge_errors"
    )
    assert projection["diagnostic"]["non_targetable_errors"] == {
        error_type: 1
    }
    assert "non_targetable_judge_errors_present" in (
        projection["full_run_gate"]["blockers"]
    )
    assert projection["full_run_gate"]["status"] == "blocked"
    assert "targetable_status=inconclusive_other_judge_errors" in markdown
    assert "targetable_status=eliminated" not in markdown


def test_anchor4_projection_rejects_reordered_tasks_with_recomputed_hash(
    tmp_path: Path,
):
    grade = _anchor4_projection_grade()
    grade["tasks"].reverse()
    grade["expected_ordered_task_ids_sha256"] = hashlib.sha256(
        json.dumps(
            [task["task_id"] for task in grade["tasks"]],
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    projection = _run(tmp_path, grade)["this"]["modality_projection"]

    assert projection["projected_220_hours"] is None
    assert projection["anchor_integrity"]["status"] == "failed"
    assert "anchor_ordered_task_identity_mismatch" in (
        projection["full_run_gate"]["blockers"]
    )
    assert projection["full_run_gate"]["status"] == "blocked"


def test_markdown_contains_key_sections(tmp_path: Path):
    text = _run(tmp_path, _grade_json(n_tasks=3), as_json=False)
    assert "## Quality" in text
    assert "## Wall-clock & latency" in text
    assert "## Cost estimate" in text
    assert "## Top-5 slowest tasks" in text


def test_analysis_output_path_preserves_legacy_name_at_255_bytes():
    module = _load_module()
    grade_path = Path(f"{'a' * 243}.json")

    output = module.resolve_analysis_output_path(grade_path)

    assert output.name == f"{'a' * 243}.analysis.md"
    assert len(output.name.encode("utf-8")) == 255


def test_analysis_output_path_falls_back_above_name_max_by_utf8_bytes():
    module = _load_module()
    grade_path = Path(f"{'é' * 122}.json")
    legacy_name = f"{'é' * 122}.analysis.md"
    assert len(legacy_name.encode("utf-8")) == 256

    output = module.resolve_analysis_output_path(grade_path)
    digest = hashlib.sha256(grade_path.name.encode("utf-8")).hexdigest()

    assert output.name == f"grade__{digest}.analysis.md"
    assert len(output.name.encode("utf-8")) == 83


def test_analysis_output_path_is_stable_and_distinct_for_long_basenames():
    module = _load_module()
    first = Path(f"{'a' * 244}.json")
    second = Path(f"{'a' * 243}b.json")

    first_output = module.resolve_analysis_output_path(first)

    assert first_output == module.resolve_analysis_output_path(first)
    assert first_output != module.resolve_analysis_output_path(second)
    assert first_output.parent == first.parent


def test_analysis_output_path_rejects_too_small_limit_and_controls():
    module = _load_module()
    with pytest.raises(ValueError, match="smaller than the bounded fallback"):
        module.resolve_analysis_output_path(
            Path(f"{'a' * 244}.json"),
            name_max=82,
        )
    with pytest.raises(ValueError, match="control characters"):
        module.resolve_analysis_output_path(Path("bad\nname.json"))


def test_auto_out_handles_exact_anchor_name_deterministically(tmp_path: Path):
    stem = "a" * 245
    grade_path = tmp_path / f"{stem}.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")
    expected_digest = hashlib.sha256(
        grade_path.name.encode("utf-8")
    ).hexdigest()
    expected = tmp_path / f"grade__{expected_digest}.analysis.md"

    first = subprocess.run(
        [sys.executable, str(SCRIPT), str(grade_path), "--auto-out"],
        capture_output=True,
        text=True,
        check=False,
    )
    first_bytes = expected.read_bytes()
    second = subprocess.run(
        [sys.executable, str(SCRIPT), str(grade_path), "--auto-out"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout == f"{expected}\n"
    assert first.stderr == second.stderr == ""
    assert expected.read_bytes() == first_bytes
    assert grade_path.read_text(encoding="utf-8") == json.dumps(
        _grade_json(n_tasks=1)
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--auto-out", "--json"],
        ["--auto-out", "--out", "out.md"],
    ],
)
def test_auto_out_rejects_incompatible_cli_modes(tmp_path: Path, arguments):
    grade_path = tmp_path / "grade.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(grade_path), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""


def test_explicit_overlong_out_fails_without_hash_fallback(tmp_path: Path):
    grade_path = tmp_path / "grade.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")
    output = tmp_path / ("x" * 256)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(grade_path),
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "exceeds 255 UTF-8 bytes" in completed.stderr


@pytest.mark.parametrize("dangling", [False, True])
def test_analysis_output_rejects_symlink_without_mutating_target(
    tmp_path: Path,
    dangling: bool,
):
    grade_path = tmp_path / "grade.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")
    target = tmp_path / "target.md"
    if not dangling:
        target.write_text("sentinel", encoding="utf-8")
    output = tmp_path / "output.md"
    output.symlink_to(target)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(grade_path),
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "must not be a symlink" in completed.stderr
    if dangling:
        assert not target.exists()
    else:
        assert target.read_text(encoding="utf-8") == "sentinel"


def test_analysis_output_rejects_symlink_parent(tmp_path: Path):
    module = _load_module()
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(ValueError, match="non-symlink directory"):
        module._write_analysis_output(linked_parent / "output.md", "content")

    assert list(real_parent.iterdir()) == []


def test_control_character_out_fails_without_stdout(tmp_path: Path):
    grade_path = tmp_path / "grade.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")
    output = tmp_path / "bad\noutput.md"

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(grade_path),
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert "must not contain control characters" in completed.stderr
    assert not output.exists()


def test_atomic_output_failure_preserves_existing_file_and_cleans_temp(
    monkeypatch,
    tmp_path: Path,
):
    module = _load_module()
    output = tmp_path / "output.md"
    output.write_text("sentinel", encoding="utf-8")

    def fail_replace(source, target, **kwargs):
        raise OSError("replace failed")

    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        module._write_analysis_output(output, "replacement")

    assert output.read_text(encoding="utf-8") == "sentinel"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["output.md"]


def test_pathconf_unlimited_uses_policy_limit(monkeypatch, tmp_path: Path):
    module = _load_module()
    output = tmp_path / "output.md"
    monkeypatch.setattr(module.os, "fpathconf", lambda fd, name: -1)

    module._write_analysis_output(output, "content")

    assert output.read_text(encoding="utf-8") == "content"


def test_small_name_limit_uses_short_temp_name(monkeypatch, tmp_path: Path):
    module = _load_module()
    output = tmp_path / "x.md"
    monkeypatch.setattr(module.os, "fpathconf", lambda fd, name: 8)

    module._write_analysis_output(output, "content")

    assert output.read_text(encoding="utf-8") == "content"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["x.md"]


def test_atomic_output_preserves_existing_mode(tmp_path: Path):
    module = _load_module()
    output = tmp_path / "output.md"
    output.write_text("sentinel", encoding="utf-8")
    output.chmod(0o644)

    module._write_analysis_output(output, "replacement")

    assert output.read_text(encoding="utf-8") == "replacement"
    assert stat.S_IMODE(output.stat().st_mode) == 0o644


def test_parent_swap_cannot_redirect_output(monkeypatch, tmp_path: Path):
    module = _load_module()
    monkeypatch.chdir(tmp_path)
    parent = Path("parent")
    parent.mkdir()
    moved = Path("moved")
    attacker = Path("attacker")
    attacker.mkdir()
    real_open = module.os.open
    swapped = False

    def swap_after_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        fd = real_open(path, flags, mode, dir_fd=dir_fd)
        if path == "parent" and flags & module.os.O_DIRECTORY and not swapped:
            parent.rename(moved)
            parent.symlink_to(attacker, target_is_directory=True)
            swapped = True
        return fd

    monkeypatch.setattr(module.os, "open", swap_after_open)

    with pytest.raises(ValueError, match="parent"):
        module._write_analysis_output(parent / "output.md", "content")

    assert list(moved.iterdir()) == []
    assert list(attacker.iterdir()) == []


@pytest.mark.parametrize("existing", [False, True])
def test_post_replace_parent_swap_rolls_back_output(
    monkeypatch,
    tmp_path: Path,
    existing: bool,
):
    module = _load_module()
    monkeypatch.chdir(tmp_path)
    parent = Path("parent")
    parent.mkdir()
    output = parent / "output.md"
    if existing:
        output.write_text("sentinel", encoding="utf-8")
    moved = Path("moved")
    attacker = Path("attacker")
    attacker.mkdir()
    real_replace = module.os.replace
    swapped = False

    def swap_after_replace(source, target, **kwargs):
        nonlocal swapped
        real_replace(source, target, **kwargs)
        if target == "output.md" and not swapped:
            parent.rename(moved)
            parent.symlink_to(attacker, target_is_directory=True)
            swapped = True

    monkeypatch.setattr(module.os, "replace", swap_after_replace)

    with pytest.raises(ValueError, match="parent"):
        module._write_analysis_output(output, "replacement")

    assert list(attacker.iterdir()) == []
    if existing:
        assert (moved / "output.md").read_text(encoding="utf-8") == "sentinel"
    else:
        assert list(moved.iterdir()) == []


def test_parent_directory_traversal_is_rejected_before_open(tmp_path: Path):
    module = _load_module()
    safe = tmp_path / "safe"
    pivot = safe / "pivot"
    destination = safe / "destination"
    pivot.mkdir(parents=True)
    destination.mkdir()
    output = pivot / ".." / "destination" / "output.md"

    with pytest.raises(ValueError, match="must not traverse parent"):
        module._write_analysis_output(output, "content")

    assert list(destination.iterdir()) == []


def test_dirfd_target_check_ignores_cwd_name_collision(
    monkeypatch,
    tmp_path: Path,
):
    module = _load_module()
    cwd = tmp_path / "cwd"
    destination = tmp_path / "destination"
    cwd.mkdir()
    destination.mkdir()
    sentinel = cwd / "sentinel.md"
    sentinel.write_text("sentinel", encoding="utf-8")
    (cwd / "output.md").symlink_to(sentinel)
    monkeypatch.chdir(cwd)

    module._write_analysis_output(destination / "output.md", "content")

    assert (destination / "output.md").read_text(encoding="utf-8") == "content"
    assert sentinel.read_text(encoding="utf-8") == "sentinel"


def test_auto_out_os_error_has_no_stdout(monkeypatch, tmp_path: Path, capsys):
    module = _load_module()
    grade_path = tmp_path / "grade.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "_write_auto_analysis_output",
        lambda grade, text: (_ for _ in ()).throw(OSError("write failed")),
    )
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(grade_path), "--auto-out"])

    with pytest.raises(SystemExit) as exc:
        module.main()

    captured = capsys.readouterr()
    assert exc.value.code == 2
    assert captured.out == ""
    assert "write failed" in captured.err


def test_json_with_explicit_out_remains_supported(tmp_path: Path):
    grade_path = tmp_path / "grade.json"
    output = tmp_path / "analysis.json"
    grade_path.write_text(json.dumps(_grade_json(n_tasks=1)), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(grade_path),
            "--json",
            "--out",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert json.loads(output.read_text(encoding="utf-8"))["this"][
        "graded_tasks"
    ] == 1


def test_committed_anchor_analysis_is_exactly_reproducible(monkeypatch):
    module = _load_module()
    relative_payload = ANCHOR_PAYLOAD.relative_to(REPO_ROOT)
    monkeypatch.chdir(REPO_ROOT)

    assert hashlib.sha256(ANCHOR_PAYLOAD.read_bytes()).hexdigest() == (
        "303a5e763e28bf06339877df62c8e2d0d022bc605aeeb3aee77e63ab411a41fb"
    )
    assert module.resolve_analysis_output_path(ANCHOR_PAYLOAD) == ANCHOR_ANALYSIS
    expected = module.render_markdown(module.analyze(relative_payload), None)

    assert ANCHOR_ANALYSIS.read_text(encoding="utf-8") == expected
    assert "tasks: 4/4 (errors=0)" in expected
    assert "full-run gate: blocked" in expected
    assert str(relative_payload) in expected
