#!/usr/bin/env python3
"""Paired quality comparison v2 vs v1 baselines for PR3 Step 3.

Loads three grade JSONs (v2, v1_hybrid, v1_mini), takes the task_id
intersection, and computes:

  - per-task paired delta tables (avg_pct, critical_item_pass)
  - sign test (deltas with non-zero direction)
  - Wilcoxon signed-rank statistic (no scipy: bootstrap CI fallback)
  - bootstrap 95% CI on mean delta (10k resamples)
  - critical_item_pass non-inferiority verdict

Emits markdown to stdout. Designed for Step 3 of TASK_grading_v2_cost_decision.md.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Tuple


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def _task_map(grade: dict) -> dict[str, dict]:
    return {t["task_id"]: t for t in grade.get("tasks", [])}


def _crit_pass_rate(task: dict) -> float:
    """Per-task critical-item pass rate based on |max_score|>=4 + sign-aware."""
    items = task.get("items", [])
    crit = [it for it in items if abs(it.get("max_score", 0) or 0) >= 4]
    if not crit:
        return 1.0  # no critical items -> trivially perfect
    # model_did_right field present from PR1 backfill; fallback to verdict==pass
    rights = []
    for it in crit:
        if "model_did_right" in it:
            rights.append(1 if it["model_did_right"] else 0)
        else:
            v = it.get("verdict", "fail")
            mx = it.get("max_score", 0) or 0
            rights.append(1 if (v == "pass") == (mx >= 0) else 0)
    return sum(rights) / len(rights)


def _sign_test(deltas: list[float]) -> dict:
    pos = sum(1 for d in deltas if d > 1e-9)
    neg = sum(1 for d in deltas if d < -1e-9)
    n_nonzero = pos + neg
    # two-sided binomial test exact for n<=20
    from math import comb
    if n_nonzero == 0:
        return {"positive": 0, "negative": 0, "p_value": 1.0}
    k = min(pos, neg)
    pval = sum(comb(n_nonzero, i) for i in range(k + 1)) / (2 ** n_nonzero) * 2
    pval = min(1.0, pval)
    return {"positive": pos, "negative": neg, "n_nonzero": n_nonzero, "p_value": pval}


def _wilcoxon_W(deltas: list[float]) -> dict:
    """Wilcoxon signed-rank test statistic. Without scipy we report W and
    leave significance to the bootstrap CI."""
    nonzero = [d for d in deltas if abs(d) > 1e-9]
    if not nonzero:
        return {"W_plus": 0.0, "W_minus": 0.0, "n": 0}
    abs_d = [abs(d) for d in nonzero]
    # rank assignment with ties at midpoint
    order = sorted(range(len(abs_d)), key=lambda i: abs_d[i])
    ranks = [0.0] * len(abs_d)
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and abs_d[order[j]] == abs_d[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg_rank
        i = j
    Wp = sum(ranks[i] for i, d in enumerate(nonzero) if d > 0)
    Wm = sum(ranks[i] for i, d in enumerate(nonzero) if d < 0)
    return {"W_plus": Wp, "W_minus": Wm, "n": len(nonzero)}


def _bootstrap_ci(deltas: list[float], n_resample: int = 10000,
                  alpha: float = 0.05, seed: int = 42) -> tuple[float, float, float]:
    rng = random.Random(seed)
    means = []
    n = len(deltas)
    for _ in range(n_resample):
        sample = [deltas[rng.randint(0, n - 1)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(n_resample * alpha / 2)]
    hi = means[int(n_resample * (1 - alpha / 2))]
    return (statistics.mean(deltas), lo, hi)


def compare(v2_path: Path, v1h_path: Path, v1m_path: Path) -> str:
    v2 = _load(v2_path)
    v1h = _load(v1h_path)
    v1m = _load(v1m_path)
    v2m = _task_map(v2)
    v1hm = _task_map(v1h)
    v1mm = _task_map(v1m)
    shared = sorted(set(v2m) & set(v1hm) & set(v1mm))
    n = len(shared)

    rows = []
    for tid in shared:
        a = v2m[tid]
        b = v1hm[tid]
        c = v1mm[tid]
        rows.append({
            "task_id": tid,
            "v2_pct": a.get("pct"),
            "v1h_pct": b.get("pct"),
            "v1m_pct": c.get("pct"),
            "delta_v2_vs_h": a.get("pct", 0) - b.get("pct", 0),
            "delta_v2_vs_m": a.get("pct", 0) - c.get("pct", 0),
            "v2_crit": _crit_pass_rate(a),
            "v1h_crit": _crit_pass_rate(b),
            "v1m_crit": _crit_pass_rate(c),
        })

    d_h = [r["delta_v2_vs_h"] for r in rows]
    d_m = [r["delta_v2_vs_m"] for r in rows]

    sign_h = _sign_test(d_h)
    sign_m = _sign_test(d_m)
    wilcox_h = _wilcoxon_W(d_h)
    wilcox_m = _wilcoxon_W(d_m)
    mean_h, lo_h, hi_h = _bootstrap_ci(d_h)
    mean_m, lo_m, hi_m = _bootstrap_ci(d_m)

    # critical_item non-inferiority: v2 mean crit >= max(v1h,v1m) crit - 5pp margin
    v2_crit_mean = statistics.mean(r["v2_crit"] for r in rows)
    v1h_crit_mean = statistics.mean(r["v1h_crit"] for r in rows)
    v1m_crit_mean = statistics.mean(r["v1m_crit"] for r in rows)
    crit_noninferior_h = v2_crit_mean >= v1h_crit_mean - 0.05
    crit_noninferior_m = v2_crit_mean >= v1m_crit_mean - 0.05

    # verdict
    significant_h = (sign_h["p_value"] < 0.10) and (lo_h > 0)
    significant_m = (sign_m["p_value"] < 0.10) and (lo_m > 0)
    if significant_h or significant_m:
        verdict = "lift_directionally_significant"
    else:
        verdict = "inconclusive"

    out = []
    out.append(f"# PR3 Step 3 — Paired quality v2 vs v1 (N={n})")
    out.append("")
    out.append("## Per-task pct table")
    out.append("")
    out.append("| task_id | v2 | v1h | v1m | Δ v2-h | Δ v2-m | crit v2 | crit v1h |")
    out.append("|---|--:|--:|--:|--:|--:|--:|--:|")
    for r in rows:
        out.append(
            f"| `{r['task_id'][:8]}` | {r['v2_pct']:.1f} | {r['v1h_pct']:.1f} | "
            f"{r['v1m_pct']:.1f} | {r['delta_v2_vs_h']:+.2f} | {r['delta_v2_vs_m']:+.2f} | "
            f"{r['v2_crit']:.3f} | {r['v1h_crit']:.3f} |"
        )
    out.append("")
    out.append("## Aggregate")
    out.append("")
    out.append("|  | mean Δ | 95% CI (bootstrap) | sign test (pos/neg) | sign p-value | Wilcoxon W+ |")
    out.append("|---|--:|---|--:|--:|--:|")
    out.append(
        f"| v2 − v1 hybrid | {mean_h:+.2f} | [{lo_h:+.2f}, {hi_h:+.2f}] | "
        f"{sign_h['positive']}/{sign_h['negative']} | {sign_h['p_value']:.3f} | "
        f"{wilcox_h['W_plus']:.1f} |"
    )
    out.append(
        f"| v2 − v1 mini   | {mean_m:+.2f} | [{lo_m:+.2f}, {hi_m:+.2f}] | "
        f"{sign_m['positive']}/{sign_m['negative']} | {sign_m['p_value']:.3f} | "
        f"{wilcox_m['W_plus']:.1f} |"
    )
    out.append("")
    out.append("## Critical-item non-inferiority")
    out.append("")
    out.append(f"- v2 mean crit pass rate: **{v2_crit_mean:.3f}**")
    out.append(f"- v1 hybrid mean crit pass rate: {v1h_crit_mean:.3f}  → non-inferior (margin 5pp): **{crit_noninferior_h}**")
    out.append(f"- v1 mini mean crit pass rate: {v1m_crit_mean:.3f}  → non-inferior (margin 5pp): **{crit_noninferior_m}**")
    out.append("")
    out.append("## Verdict")
    out.append("")
    out.append(f"- **lift verdict: `{verdict}`**")
    out.append(f"- **critical_item_noninferior** (vs v1h): `{crit_noninferior_h}`")
    out.append(f"- **critical_item_noninferior** (vs v1m): `{crit_noninferior_m}`")
    out.append("")
    out.append("Significance rule: `sign_p < 0.10 AND bootstrap_lower_CI > 0`.")
    out.append("Non-inferiority margin: 5pp absolute.")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v2", required=True, type=Path)
    ap.add_argument("--v1-hybrid", required=True, type=Path)
    ap.add_argument("--v1-mini", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    md = compare(args.v2, args.v1_hybrid, args.v1_mini)
    if args.out:
        args.out.write_text(md)
        print(f"wrote {args.out}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
