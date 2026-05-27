#!/usr/bin/env python3
"""Pair-wise compare two grade JSONs over the intersection of task_ids.

Designed for C′ validation: compare a partial hybrid grade against a mini
default grade computed over the same first-N tasks. Emits a markdown
report + a JSON decision file consumed by validate-and-decide.yml.

Decision rule (autonomous, no human-in-the-loop):

  If hybrid_critical_pass < mini_critical_pass * STRICT_RATIO  → ABORT
      (hybrid is too harsh; pro-tier likely over-rejecting critical items
       that mini and standard reviewers accept. A 30h / $200 full run is
       not justified until the pro prompt is recalibrated.)

  Else                                                          → PROCEED
      (hybrid agrees with mini on critical-item pass rate within tolerance,
       or only marginally stricter; full run carries real signal.)

The script is non-interactive: exit 0 with a JSON decision artifact.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STRICT_RATIO = 0.7  # hybrid must keep at least 70% of mini's critical pass rate


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def _by_task(grade: dict) -> dict[str, dict]:
    return {t["task_id"]: t for t in grade.get("tasks", [])}


def _critical_summary(task: dict) -> dict:
    items = task.get("items", [])
    crit_items = [i for i in items if i.get("required") is True or (i.get("max_score") or 0) >= 4]
    n = len(crit_items)
    passed = sum(1 for i in crit_items if i.get("verdict") == "pass")
    return {
        "n_critical": n,
        "passed": passed,
        "pass_rate": (passed / n) if n else None,
        "fails": [
            {
                "rubric_item_id": i.get("rubric_item_id"),
                "criterion": (i.get("criterion") or "")[:120],
                "verdict": i.get("verdict"),
                "awarded": i.get("awarded_score"),
                "max_score": i.get("max_score"),
                "evidence": (i.get("evidence") or "")[:200],
                "decided_by": i.get("decided_by"),
            }
            for i in crit_items if i.get("verdict") != "pass"
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("hybrid_json", type=Path, help="hybrid (partial or full) grade JSON")
    ap.add_argument("mini_json", type=Path, help="mini default grade JSON (same tasks)")
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--out-decision", type=Path, required=True)
    args = ap.parse_args()

    H = _load(args.hybrid_json)
    M = _load(args.mini_json)
    Hb = _by_task(H)
    Mb = _by_task(M)
    common = sorted(set(Hb) & set(Mb))

    h_cp = H["summary"]["wow"]["critical_item_pass_rate"]
    m_cp = M["summary"]["wow"]["critical_item_pass_rate"]
    h_avg = H["summary"]["openai_compat"]["avg_score_pct"]
    m_avg = M["summary"]["openai_compat"]["avg_score_pct"]

    # Per-task pair-wise critical comparison
    rows = []
    h_strict_when_mini_pass = 0  # hybrid fails critical that mini passed
    h_agrees_on_fail = 0          # both flag fails
    for tid in common:
        ht = Hb[tid]
        mt = Mb[tid]
        hc = _critical_summary(ht)
        mc = _critical_summary(mt)
        rows.append({
            "task_id": tid,
            "hybrid_pct": ht.get("pct"),
            "mini_pct": mt.get("pct"),
            "hybrid_crit_pass": hc["pass_rate"],
            "mini_crit_pass": mc["pass_rate"],
            "delta_pct": (ht.get("pct") or 0) - (mt.get("pct") or 0),
            "hybrid_crit_fails": hc["fails"][:3],  # top-3 only for report size
        })
        if (mc["pass_rate"] or 0) == 1.0 and (hc["pass_rate"] or 0) < 1.0:
            h_strict_when_mini_pass += 1
        if (hc["pass_rate"] or 0) < 1.0 and (mc["pass_rate"] or 0) < 1.0:
            h_agrees_on_fail += 1

    n_pairs = len(common)
    strict_overhead = (h_strict_when_mini_pass / n_pairs) if n_pairs else 0
    agreement_on_fail = (h_agrees_on_fail / n_pairs) if n_pairs else 0

    # Decision rule
    ratio = (h_cp / m_cp) if m_cp else 0
    if ratio < STRICT_RATIO:
        decision = "ABORT"
        rationale = (
            f"hybrid critical_pass {h_cp:.3f} / mini critical_pass {m_cp:.3f} "
            f"= {ratio:.2f} < {STRICT_RATIO} (STRICT_RATIO). Hybrid pro-tier "
            f"is over-rejecting critical items. Full run not justified."
        )
    else:
        decision = "PROCEED"
        rationale = (
            f"hybrid critical_pass {h_cp:.3f} / mini critical_pass {m_cp:.3f} "
            f"= {ratio:.2f} ≥ {STRICT_RATIO}. Hybrid stays within tolerance; "
            f"full run carries usable signal."
        )

    # ---- emit markdown ----
    md = []
    md.append("# Hybrid vs Mini Default — Pair-wise Validation (C′)\n")
    md.append(f"- hybrid_json: `{args.hybrid_json.name}`")
    md.append(f"- mini_json  : `{args.mini_json.name}`")
    md.append(f"- task pairs : {n_pairs}\n")
    md.append("## Decision")
    md.append(f"- **{decision}**")
    md.append(f"- rule  : ratio = hybrid/mini critical_pass; threshold = {STRICT_RATIO}")
    md.append(f"- ratio : **{ratio:.3f}**")
    md.append(f"- {rationale}\n")
    md.append("## Aggregate")
    md.append("| metric | hybrid | mini | Δ |")
    md.append("|---|--:|--:|--:|")
    md.append(f"| critical_item_pass_rate | {h_cp:.3f} | {m_cp:.3f} | {h_cp - m_cp:+.3f} |")
    md.append(f"| avg_score_pct | {h_avg:.2f} | {m_avg:.2f} | {h_avg - m_avg:+.2f} |")
    md.append(f"| hybrid stricter than mini on critical (tasks) | {h_strict_when_mini_pass}/{n_pairs} ({strict_overhead*100:.1f}%) |  |  |")
    md.append(f"| both flagged critical fails (agreement) | {h_agrees_on_fail}/{n_pairs} ({agreement_on_fail*100:.1f}%) |  |  |\n")

    md.append("## Per-task")
    md.append("| task_id | hybrid pct | mini pct | Δ | hybrid crit pass | mini crit pass |")
    md.append("|---|--:|--:|--:|--:|--:|")
    for r in rows:
        md.append(
            f"| `{r['task_id'][:18]}…` | {r['hybrid_pct']} | {r['mini_pct']} | "
            f"{r['delta_pct']:+.1f} | {r['hybrid_crit_pass']} | {r['mini_crit_pass']} |"
        )

    md.append("\n## Sample hybrid critical FAILs (top 3 per task, first 5 tasks)")
    sample = [r for r in rows if r["hybrid_crit_fails"]][:5]
    for r in sample:
        md.append(f"\n### task `{r['task_id'][:24]}…`  (mini_crit_pass={r['mini_crit_pass']})")
        for f in r["hybrid_crit_fails"]:
            md.append(
                f"- **{f['verdict']}** ({f['decided_by']}, {f['awarded']}/{f['max_score']}) "
                f"`{f['criterion']}` — evidence: _{f['evidence']}_"
            )

    args.out_md.write_text("\n".join(md) + "\n")

    # ---- emit decision JSON ----
    args.out_decision.write_text(json.dumps({
        "decision": decision,
        "ratio": ratio,
        "threshold": STRICT_RATIO,
        "hybrid_critical_pass": h_cp,
        "mini_critical_pass": m_cp,
        "hybrid_avg": h_avg,
        "mini_avg": m_avg,
        "task_pairs": n_pairs,
        "rationale": rationale,
    }, indent=2))

    print(f"DECISION={decision}  ratio={ratio:.3f}  threshold={STRICT_RATIO}", flush=True)
    print(f"wrote {args.out_md}", flush=True)
    print(f"wrote {args.out_decision}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
