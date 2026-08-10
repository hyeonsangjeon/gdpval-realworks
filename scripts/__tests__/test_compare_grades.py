"""Unit tests for scripts/compare_grades.py — pair-wise hybrid vs mini decision.

Synthesize minimal grade JSON shapes (only fields the script reads) and
verify the autonomous PROCEED/ABORT rule fires at the expected threshold.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "compare_grades.py"


def _grade(
    task_ids: list[str],
    *,
    critical_pass: float,
    avg_score: float,
    task_critical_pass: float | None = None,
) -> dict:
    """Build a minimal grade JSON dict the comparator can read."""
    per_task_cp = task_critical_pass if task_critical_pass is not None else critical_pass
    tasks = []
    for tid in task_ids:
        # one critical item per task; verdict based on pass rate
        verdict = "pass" if per_task_cp >= 1.0 else "fail"
        awarded = 4 if verdict == "pass" else 0
        tasks.append({
            "task_id": tid,
            "pct": avg_score,
            "items": [
                {
                    "rubric_item_id": f"{tid}-crit",
                    "criterion": "critical item",
                    "max_score": 4,
                    "awarded_score": awarded,
                    "verdict": verdict,
                    "required": True,
                    "decided_by": "judge",
                    "evidence": "test evidence",
                }
            ],
        })
    return {
        "tasks": tasks,
        "summary": {
            "openai_compat": {"avg_score_pct": avg_score},
            "wow": {"critical_item_pass_rate": critical_pass},
        },
    }


def _run(tmp_path: Path, hybrid: dict, mini: dict) -> tuple[int, dict, str]:
    h_p = tmp_path / "h.json"
    m_p = tmp_path / "m.json"
    md = tmp_path / "out.md"
    dec = tmp_path / "dec.json"
    h_p.write_text(json.dumps(hybrid))
    m_p.write_text(json.dumps(mini))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(h_p), str(m_p),
         "--out-md", str(md), "--out-decision", str(dec)],
        capture_output=True, text=True,
    )
    decision = json.loads(dec.read_text())
    return result.returncode, decision, md.read_text()


def test_proceed_when_hybrid_matches_mini(tmp_path: Path):
    tids = [f"t{i:02d}" for i in range(10)]
    rc, dec, md = _run(
        tmp_path,
        _grade(tids, critical_pass=1.0, avg_score=80.0),
        _grade(tids, critical_pass=1.0, avg_score=80.0),
    )
    assert rc == 0
    assert dec["decision"] == "PROCEED"
    assert dec["ratio"] == pytest.approx(1.0)
    assert "PROCEED" in md


def test_abort_when_hybrid_much_stricter(tmp_path: Path):
    tids = [f"t{i:02d}" for i in range(10)]
    rc, dec, md = _run(
        tmp_path,
        _grade(tids, critical_pass=0.41, avg_score=45.0),   # the real hybrid signal
        _grade(tids, critical_pass=1.0, avg_score=78.0),     # mini default
    )
    assert rc == 0
    assert dec["decision"] == "ABORT"
    assert dec["ratio"] == pytest.approx(0.41, abs=0.01)
    assert dec["ratio"] < dec["threshold"]
    assert "ABORT" in md


def test_proceed_at_threshold_boundary(tmp_path: Path):
    """ratio = 0.7 exactly → PROCEED (>= threshold)."""
    tids = [f"t{i:02d}" for i in range(10)]
    rc, dec, _ = _run(
        tmp_path,
        _grade(tids, critical_pass=0.7, avg_score=60.0),
        _grade(tids, critical_pass=1.0, avg_score=80.0),
    )
    assert rc == 0
    assert dec["decision"] == "PROCEED"


def test_abort_just_below_threshold(tmp_path: Path):
    tids = [f"t{i:02d}" for i in range(10)]
    rc, dec, _ = _run(
        tmp_path,
        _grade(tids, critical_pass=0.69, avg_score=55.0),
        _grade(tids, critical_pass=1.0, avg_score=80.0),
    )
    assert rc == 0
    assert dec["decision"] == "ABORT"


def test_only_compares_task_id_intersection(tmp_path: Path):
    """Tasks present in only one grade JSON must not affect ratio."""
    hybrid = _grade([f"t{i:02d}" for i in range(10)], critical_pass=1.0, avg_score=80.0)
    mini = _grade([f"t{i:02d}" for i in range(5, 15)], critical_pass=1.0, avg_score=80.0)
    rc, dec, md = _run(tmp_path, hybrid, mini)
    assert rc == 0
    # intersection = t05..t09 → 5 pairs
    assert dec["task_pairs"] == 5
    assert dec["decision"] == "PROCEED"


def test_handles_zero_mini_critical_pass(tmp_path: Path):
    """Division-by-zero guard: mini critical_pass=0 → ratio=0 → ABORT, no crash."""
    tids = [f"t{i:02d}" for i in range(5)]
    rc, dec, _ = _run(
        tmp_path,
        _grade(tids, critical_pass=0.0, avg_score=10.0),
        _grade(tids, critical_pass=0.0, avg_score=10.0),
    )
    assert rc == 0
    assert dec["decision"] == "ABORT"
    assert dec["ratio"] == 0


@pytest.mark.parametrize("unscored_side", ["hybrid", "mini"])
def test_null_headline_is_unscored_and_has_no_delta(
    tmp_path: Path, unscored_side: str
):
    tids = ["t01"]
    hybrid = _grade(tids, critical_pass=1.0, avg_score=80.0)
    mini = _grade(tids, critical_pass=1.0, avg_score=80.0)
    target = hybrid if unscored_side == "hybrid" else mini
    target["summary"]["openai_compat"]["avg_score_pct"] = None

    rc, dec, md = _run(tmp_path, hybrid, mini)

    assert rc == 0
    assert dec[f"{unscored_side}_avg"] is None
    assert "| avg_score_pct | unscored | 80.00 | — |" in md or (
        "| avg_score_pct | 80.00 | unscored | — |" in md
    )
    assert "None" not in md


def test_unscored_task_has_no_pairwise_delta(tmp_path: Path):
    hybrid = _grade(["t01"], critical_pass=1.0, avg_score=80.0)
    mini = _grade(["t01"], critical_pass=1.0, avg_score=60.32)
    hybrid["tasks"][0]["pct"] = 0
    hybrid["tasks"][0]["error"] = "all_items_score_excluded"

    _, _, md = _run(tmp_path, hybrid, mini)

    assert "| `t01…` | unscored | 60.32 | — |" in md
    assert "-60.3" not in md
