"""Unit tests for scripts/backfill_sign_aware.py.

Synthesize a minimal v1 grade JSON, run backfill, verify the resulting
v2sm payload has correct sign-aware fields and recomputed summary.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "backfill_sign_aware.py"


def _v1_grade(tasks: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "exp_test",
        "experiment_yaml_name": "exp_test",
        "tasks": tasks,
        "summary": {
            "total_tasks": len(tasks),
            "graded_tasks": len(tasks),
            "error_tasks": 0,
            "openai_compat": {"avg_score_pct": 0.0},
            "wow": {"critical_item_pass_rate": 0.0},
        },
    }


def _task(tid: str, items: list[dict], **kwargs) -> dict:
    total_max = sum(i.get("max_score", 0) for i in items)  # legacy arithmetic sum
    return {
        "task_id": tid,
        "sector": "s",
        "occupation": "o",
        "items": items,
        "total_awarded": sum(i.get("awarded_score", 0) for i in items),
        "total_max": total_max,
        "pct": 0.0,
        "critical_fail": False,
        "gold_referenced": False,
        "judge_call_count": 0,
        "precheck_count": 0,
        "judge_total_latency_ms": 0,
        "judge_input_tokens": 0,
        "judge_output_tokens": 0,
        "error": None,
        "graded_at": "2026-05-29T00:00:00Z",
        **kwargs,
    }


def _item(rid: str, ms: int, awarded: float, verdict: str = "pass") -> dict:
    return {
        "rubric_item_id": rid,
        "criterion": "c",
        "max_score": ms,
        "awarded_score": awarded,
        "verdict": verdict,
        "decided_by": "judge",
        "required": None,
        "evidence": "e",
        "judge_confidence": None,
        "judge_latency_ms": None,
        "precheck_pattern_id": None,
        "judge_raw_response": None,
    }


def _run(tmp_path: Path, payload: dict) -> dict:
    p = tmp_path / "grade.json"
    p.write_text(json.dumps(payload))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(p)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    out = p.with_name(p.stem + "__v2sm.json")
    return json.loads(out.read_text())


def test_backfill_sets_model_did_right_per_item(tmp_path: Path):
    payload = _v1_grade([
        _task("t1", [
            _item("r1", 5, 5, "pass"),     # positive pass → right
            _item("r2", 5, 0, "fail"),     # positive fail → wrong
            _item("r3", -85, -85, "pass"), # negative pass → violated, wrong
            _item("r4", -20, 0, "fail"),   # negative fail → no violation, right
            _item("r5", 4, 0, "judge_error"),  # error → conservative wrong
        ]),
    ])
    out = _run(tmp_path, payload)
    items = out["tasks"][0]["items"]
    assert items[0]["model_did_right"] is True
    assert items[1]["model_did_right"] is False
    assert items[2]["model_did_right"] is False
    assert items[3]["model_did_right"] is True
    assert items[4]["model_did_right"] is False


def test_backfill_uses_positive_only_denominator(tmp_path: Path):
    """When v1 stored total_max as positive+negative sum, v2sm should
    recompute it as positive only."""
    payload = _v1_grade([
        _task("t1", [
            _item("r1", 10, 10, "pass"),
            _item("r2", -85, 0, "fail"),
        ]),
    ])
    out = _run(tmp_path, payload)
    t = out["tasks"][0]
    assert t["total_max"] == 10  # was -75 under legacy sum
    assert t["pct"] == 100.0
    assert t["pct_raw"] == 100.0


def test_backfill_floors_pct_when_penalty_dominates(tmp_path: Path):
    payload = _v1_grade([
        _task("t1", [
            _item("r1", 10, 10, "pass"),
            _item("r2", -85, -85, "pass"),  # penalty applied
        ]),
    ])
    out = _run(tmp_path, payload)
    t = out["tasks"][0]
    assert t["total_max"] == 10
    assert t["total_awarded"] == -75.0
    assert t["pct"] == 0.0       # clamped
    assert t["pct_raw"] == -750.0  # raw exposes the magnitude
    assert t["critical_fail"] is True


def test_backfill_recomputes_summary_critical_pass(tmp_path: Path):
    payload = _v1_grade([
        _task("t1", [
            _item("r1", 5, 5, "pass"),     # critical, right
            _item("r2", 5, 0, "fail"),     # critical, wrong
            _item("r3", 2, 2, "pass"),     # NOT critical (below threshold)
        ]),
        _task("t2", [
            _item("r4", -85, 0, "fail"),   # critical (magnitude), right
        ]),
    ])
    out = _run(tmp_path, payload)
    wow = out["summary"]["wow"]
    # critical items: r1, r2, r4 (r3 below threshold)
    assert wow["_v2sm_critical_items"] == 3
    # right: r1 (pos pass), r4 (neg fail = no violation) → 2 of 3
    assert wow["_v2sm_critical_right"] == 2
    assert wow["critical_item_pass_rate"] == 0.6667


def test_backfill_bumps_schema_version_to_1_1(tmp_path: Path):
    payload = _v1_grade([_task("t1", [_item("r1", 4, 4, "pass")])])
    out = _run(tmp_path, payload)
    assert out["schema_version"] == "1.1"


def test_backfill_preserves_input_file(tmp_path: Path):
    """v2sm output must be a NEW file; v1 input untouched."""
    p = tmp_path / "grade.json"
    p.write_text(json.dumps(_v1_grade([_task("t1", [_item("r1", 4, 4, "pass")])])))
    before = p.read_text()
    subprocess.run(
        [sys.executable, str(SCRIPT), str(p)],
        capture_output=True, text=True, check=True,
    )
    after = p.read_text()
    assert before == after, "input v1 file must NOT be modified"
    assert (tmp_path / "grade__v2sm.json").exists()


def test_backfill_rejects_schema_1_3_instead_of_downgrading_null_score(
    tmp_path: Path,
):
    payload = _v1_grade([
        _task(
            "t1",
            [_item("r1", 4, 0, "judge_error")],
            error="all_items_score_excluded",
        )
    ])
    payload["schema_version"] = "1.3"
    payload["summary"]["graded_tasks"] = 0
    payload["summary"]["error_tasks"] = 1
    payload["summary"]["openai_compat"]["avg_score_pct"] = None
    source = tmp_path / "grade.json"
    source.write_text(json.dumps(payload))

    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(source)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "schema 1.0" in result.stderr
    assert not (tmp_path / "grade__v2sm.json").exists()
