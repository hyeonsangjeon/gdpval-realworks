#!/usr/bin/env python3
"""Backfill existing v1 grade JSONs to sign-aware v2sm format.

For each input grade JSON:
1. Walks every task's items and computes `model_did_right` (PR1 task 100
   semantics: sign-aware right-outcome flag).
2. Recomputes per-task `total_max` as the sum of positive max_score only
   (PR1 task 102 — `TaskRubric.max_score` redefinition mirrored here).
3. Recomputes per-task `total_awarded` from items' awarded_score (unchanged
   semantics; just verifies consistency).
4. Recomputes per-task `pct` (clamped to [0,100]) AND `pct_raw` (unclamped).
5. Recomputes per-task `critical_fail` using magnitude + sign-aware
   (PR1 task 101 rule).
6. Recomputes `summary.wow.critical_item_pass_rate` using
   `_is_critical_item(max_score)` + `model_did_right`.
7. Bumps `schema_version` from "1.0" → "1.1" so callers can branch on
   the presence of the new fields.
8. Writes to `<basename>__v2sm.json` next to the input. v1 file is
   preserved untouched (back-fill policy (c) in 000-OVERVIEW.md).

Usage:
    python scripts/backfill_sign_aware.py data/grades/exp003*v1.json
    python scripts/backfill_sign_aware.py --all data/grades/
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

# Mirror constant from core.grader so this script stays self-contained
# (no batch-runner import gymnastics — scripts/ runs from repo root).
MAGNITUDE_THRESHOLD = 4
SCHEMA_VERSION_OUT = "1.1"


def _is_critical_item(max_score) -> bool:
    try:
        return abs(max_score or 0) >= MAGNITUDE_THRESHOLD
    except Exception:
        return False


def _model_did_right(item: dict) -> bool:
    verdict = item.get("verdict")
    if verdict == "judge_error":
        return False
    ms = item.get("max_score") or 0
    if ms < 0:
        return verdict != "pass"
    return verdict == "pass"


def _recompute_task(task: dict) -> dict:
    """Mutates a deepcopy of `task` in place and returns it."""
    items = task.get("items", [])
    pos_max = 0
    awarded = 0.0
    for it in items:
        ms = it.get("max_score") or 0
        if ms > 0:
            pos_max += ms
        try:
            awarded += float(it.get("awarded_score") or 0)
        except Exception:
            pass
        it["model_did_right"] = _model_did_right(it)

    if pos_max:
        pct_raw = awarded / pos_max * 100.0
    elif awarded != 0:
        pct_raw = float(awarded)  # degenerate task, surface anomaly
    else:
        pct_raw = 0.0

    pct_clamped = max(0.0, min(100.0, pct_raw))

    task["total_max"] = pos_max
    task["total_awarded"] = round(awarded, 4)
    task["pct"] = round(pct_clamped, 2)
    task["pct_raw"] = round(pct_raw, 2)
    task["critical_fail"] = any(
        _is_critical_item(it.get("max_score")) and not it.get("model_did_right", False)
        for it in items
    )
    return task


def _recompute_summary(payload: dict) -> dict:
    """Recomputes summary.wow.critical_item_pass_rate (sign-aware) and
    summary.openai_compat.avg_score_pct (uses new clamped pct). Leaves
    other summary fields alone — they're computed from raw verdicts and
    remain comparable to v1 for diff-checking."""
    tasks = payload.get("tasks", [])

    crit_items = 0
    crit_right = 0
    pcts = []

    for t in tasks:
        if not t.get("error"):
            pcts.append(float(t.get("pct") or 0))
        for it in t.get("items", []):
            if _is_critical_item(it.get("max_score")):
                crit_items += 1
                if bool(it.get("model_did_right", False)):
                    crit_right += 1

    summary = payload.setdefault("summary", {})
    oc = summary.setdefault("openai_compat", {})
    wow = summary.setdefault("wow", {})

    oc["avg_score_pct"] = round((sum(pcts) / len(pcts)) if pcts else 0.0, 2)
    wow["critical_item_pass_rate"] = round(
        (crit_right / crit_items) if crit_items else 0.0, 4
    )
    # Bookkeeping: also record raw counts so subsequent diffs are auditable.
    wow["_v2sm_critical_items"] = crit_items
    wow["_v2sm_critical_right"] = crit_right
    return payload


def backfill_file(in_path: Path) -> Path:
    raw = json.loads(in_path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "1.0":
        raise ValueError("backfill requires schema 1.0 input")
    out = deepcopy(raw)
    out["schema_version"] = SCHEMA_VERSION_OUT
    out["tasks"] = [_recompute_task(deepcopy(t)) for t in out.get("tasks", [])]
    _recompute_summary(out)
    out_path = in_path.with_name(in_path.stem + "__v2sm.json")
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return out_path


def _expand_targets(args) -> list[Path]:
    targets: list[Path] = []
    for a in args.paths:
        p = Path(a)
        if p.is_dir():
            for f in sorted(p.glob("*.json")):
                # skip already-backfilled outputs to avoid recursion
                if f.stem.endswith("__v2sm"):
                    continue
                # skip legacy demo data
                if f.name == "dummy_gpt5_baseline.json":
                    continue
                targets.append(f)
        else:
            targets.append(p)
    return targets


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="+", help="Grade JSON file(s) or a directory")
    ap.add_argument("--all", action="store_true",
                    help="When a directory is given, backfill every non-v2sm "
                         "non-dummy *.json under it")
    args = ap.parse_args()

    targets = _expand_targets(args)
    if not targets:
        print("No targets found", file=sys.stderr)
        return 1

    print(f"backfill {len(targets)} file(s):", flush=True)
    for t in targets:
        try:
            out = backfill_file(t)
            print(f"  ✓ {t.name} → {out.name}", flush=True)
        except Exception as exc:
            print(f"  ✗ {t.name}: {exc}", flush=True, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
