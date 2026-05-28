"""Unit tests for scripts/analyze_grade_run.py — sanity that key metrics
(wall-clock, latency, token totals, cost-estimate mode) are computed
correctly from a synthetic grade JSON.

These are not full-coverage tests; they exercise the happy paths for
the two cost modes (single judge model vs hybrid routing) and the
top-5-slowest selection.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "analyze_grade_run.py"


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


def test_markdown_contains_key_sections(tmp_path: Path):
    text = _run(tmp_path, _grade_json(n_tasks=3), as_json=False)
    assert "## Quality" in text
    assert "## Wall-clock & latency" in text
    assert "## Cost estimate" in text
    assert "## Top-5 slowest tasks" in text
