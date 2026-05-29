#!/usr/bin/env python3
"""Stratify hybrid vs mini critical-item disagreement by rubric criterion.

Answers Opus's probe Y(1): is the −10pp critical_pass gap dominated by
'formatting/style' criteria (extraction artifact, B-scenario evidence) or
spread across substantive content criteria (real catches, A-scenario)?

Strategy
--------
1. Collect every critical rubric item from both grade JSONs (intersection
   of task_ids).
2. Bucket each item by criterion text:
   - 'formatting' bucket if the criterion text matches FORMATTING_PATTERNS
     (case-insensitive); covers items the deliverable extractor likely
     strips (style, layout, structure, presentation, formatting).
   - 'content' bucket otherwise (completeness, accuracy, includes column X,
     references gold file, etc.).
3. For each bucket, compute hybrid and mini critical_pass rates and the
   four-cell agreement matrix:
       (hybrid_pass, mini_pass)
       (hybrid_pass, mini_fail)  ← hybrid leniency wins (rare)
       (hybrid_fail, mini_pass)  ← hybrid stricter than mini (the gap)
       (hybrid_fail, mini_fail)
4. Within each bucket, identify the top-K disagreement criteria — those
   where (hybrid_fail, mini_pass) count is highest — so a human can spot
   whether pro is right or pedantic.

Definition of 'critical'
------------------------
Matches the routing rule used by validation_hybrid.yaml: rubric items
where max_score >= 4 OR required is True. This is what tier_pro graded
in the hybrid run, so it's the right subset for the A-vs-B question.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Case-insensitive substring patterns. Order is informational only.
# The intent: catch criteria whose evaluation depends on visible
# formatting of the deliverable — exactly what a flattened extraction
# would erase. Adjust if false-positives appear.
FORMATTING_PATTERNS = re.compile(
    r"format|style|layout|structur|presentation|appearance|visual|"
    r"organi[sz]ation of the deliverable|overall.*deliverable|"
    r"properly formatted|well[- ]formatted|professional.*look|"
    r"clean.*format|clear.*layout|readable|legibl",
    re.IGNORECASE,
)


def _is_critical(item: dict) -> bool:
    """Items the validation_hybrid config routes to tier_pro / treats as critical.

    Note: GDPVal rubric `required` field is ALWAYS null in practice
    (verified across all 10,453 items in exp003); the rubric authors did
    not use it. So the only effective rule is the score-weight heuristic.
    """
    if item.get("required") is True:
        return True
    try:
        return (item.get("max_score") or 0) >= 4
    except Exception:
        return False


def _is_penalty(item: dict) -> bool:
    """Negative-score items act as disqualifiers (e.g. -85 'faces identifiable',
    -60 'recognizable people present'). They are NOT routed to tier_pro by the
    current hybrid config (because score<0 fails the score>=4 critical test)
    yet they functionally express critical violations. Tracked as a separate
    bucket so the report shows the gap our default critical-rule MISSES.
    """
    try:
        return (item.get("max_score") or 0) < 0
    except Exception:
        return False


def _bucket(criterion: str) -> str:
    if criterion and FORMATTING_PATTERNS.search(criterion):
        return "formatting"
    return "content"


def _by_task(grade: dict) -> dict[str, dict]:
    return {t["task_id"]: t for t in grade.get("tasks", [])}


def _verdict_pass(item: dict) -> bool:
    return item.get("verdict") == "pass"


def stratify(hybrid_path: Path, mini_path: Path) -> dict:
    H = json.loads(hybrid_path.read_text())
    M = json.loads(mini_path.read_text())
    Hb = _by_task(H)
    Mb = _by_task(M)
    common = sorted(set(Hb) & set(Mb))

    # Two-key index: (task_id, rubric_item_id) → (hybrid_item, mini_item)
    pairs: dict[tuple[str, str], tuple[dict, dict]] = {}
    for tid in common:
        h_items = {i["rubric_item_id"]: i for i in Hb[tid].get("items", [])}
        m_items = {i["rubric_item_id"]: i for i in Mb[tid].get("items", [])}
        for rid in set(h_items) & set(m_items):
            hi, mi = h_items[rid], m_items[rid]
            if _is_critical(hi) or _is_critical(mi):
                pairs[(tid, rid)] = (hi, mi)

    # Bucket aggregation
    buckets: dict[str, dict] = {
        b: {
            "n_pairs": 0,
            "hybrid_pass": 0,
            "mini_pass": 0,
            "hp_mp": 0,   # both pass
            "hp_mf": 0,   # hybrid pass, mini fail (mini stricter — rare)
            "hf_mp": 0,   # hybrid fail, mini pass (THE GAP)
            "hf_mf": 0,   # both fail (agree on fail)
            "top_disagreements": Counter(),  # criterion text → hf_mp count
            "by_decided_by": Counter(),       # which tier decided hybrid fails
            "examples_hf_mp": [],            # up to N samples for inspection
        }
        for b in ("formatting", "content")
    }
    EXAMPLES_PER_BUCKET = 12

    for (tid, rid), (hi, mi) in pairs.items():
        criterion = hi.get("criterion") or mi.get("criterion") or ""
        b = _bucket(criterion)
        bucket = buckets[b]
        bucket["n_pairs"] += 1
        hp, mp = _verdict_pass(hi), _verdict_pass(mi)
        if hp: bucket["hybrid_pass"] += 1
        if mp: bucket["mini_pass"] += 1
        if hp and mp:
            bucket["hp_mp"] += 1
        elif hp and not mp:
            bucket["hp_mf"] += 1
        elif not hp and mp:
            bucket["hf_mp"] += 1
            # short key for grouping near-identical criteria across tasks
            key = (criterion or "").strip().lower()[:120]
            bucket["top_disagreements"][key] += 1
            bucket["by_decided_by"][hi.get("decided_by") or "?"] += 1
            if len(bucket["examples_hf_mp"]) < EXAMPLES_PER_BUCKET:
                bucket["examples_hf_mp"].append({
                    "task_id": tid,
                    "rubric_item_id": rid,
                    "criterion": (criterion or "")[:160],
                    "hybrid_awarded": hi.get("awarded_score"),
                    "mini_awarded": mi.get("awarded_score"),
                    "max_score": hi.get("max_score") or mi.get("max_score"),
                    "hybrid_decided_by": hi.get("decided_by"),
                    "mini_decided_by": mi.get("decided_by"),
                    "hybrid_evidence": (hi.get("evidence") or "")[:240],
                    "mini_evidence": (mi.get("evidence") or "")[:240],
                })
        else:
            bucket["hf_mf"] += 1

    # Pass rates per bucket
    for b in buckets.values():
        n = max(1, b["n_pairs"])
        b["hybrid_pass_rate"] = round(b["hybrid_pass"] / n, 4)
        b["mini_pass_rate"] = round(b["mini_pass"] / n, 4)
        b["gap_pp"] = round((b["hybrid_pass_rate"] - b["mini_pass_rate"]) * 100, 2)
        b["hf_mp_share_of_pairs"] = round(b["hf_mp"] / n, 4)

    # Total picture
    total_hf_mp = sum(b["hf_mp"] for b in buckets.values())
    overall = {
        "total_critical_pairs": sum(b["n_pairs"] for b in buckets.values()),
        "total_hf_mp": total_hf_mp,
        "formatting_share_of_hf_mp": round(
            buckets["formatting"]["hf_mp"] / max(1, total_hf_mp), 4
        ),
        "content_share_of_hf_mp": round(
            buckets["content"]["hf_mp"] / max(1, total_hf_mp), 4
        ),
    }

    return {
        "hybrid_path": str(hybrid_path),
        "mini_path": str(mini_path),
        "task_pairs": len(common),
        "buckets": buckets,
        "overall": overall,
    }


def render_markdown(s: dict) -> str:
    lines = []
    lines.append("# Critical-Item Disagreement Stratification (Probe Y₁)\n")
    lines.append(f"- hybrid: `{Path(s['hybrid_path']).name}`")
    lines.append(f"- mini  : `{Path(s['mini_path']).name}`")
    lines.append(f"- task pairs: {s['task_pairs']}")
    lines.append(f"- total critical (rubric item) pairs: {s['overall']['total_critical_pairs']}")
    lines.append("")
    o = s["overall"]
    lines.append("## Headline split of the −10pp gap")
    lines.append(f"- total hybrid-fail / mini-pass disagreements (the gap): **{o['total_hf_mp']}**")
    lines.append(f"- of which **formatting bucket**: {s['buckets']['formatting']['hf_mp']} "
                 f"({o['formatting_share_of_hf_mp']*100:.1f}%)")
    lines.append(f"- of which **content bucket**:    {s['buckets']['content']['hf_mp']} "
                 f"({o['content_share_of_hf_mp']*100:.1f}%)")
    lines.append("")
    lines.append("> Interpretation:")
    lines.append("> - **formatting >> content** → Scenario B (hybrid penalizes flattened extraction; mini is closer to truth)")
    lines.append("> - **content >> formatting** → Scenario A (pro tier catching real critical fails; mini too lenient)")
    lines.append("> - **roughly equal** → both effects present; need probe Y₂ to disentangle")
    lines.append("")
    for name, b in s["buckets"].items():
        lines.append(f"## Bucket: `{name}`")
        lines.append(f"- pairs: {b['n_pairs']}  | hybrid_pass: {b['hybrid_pass_rate']:.3f}  | mini_pass: {b['mini_pass_rate']:.3f}  | gap: **{b['gap_pp']:+.1f}pp**")
        lines.append(f"- agreement: both_pass={b['hp_mp']}  both_fail={b['hf_mf']}  hybrid_fail_only={b['hf_mp']}  mini_fail_only={b['hp_mf']}")
        lines.append(f"- hybrid fails decided by tier (precheck vs judge): {dict(b['by_decided_by'])}")
        lines.append("")
        lines.append("### Top disagreement criteria (hybrid fail / mini pass)")
        top = b["top_disagreements"].most_common(10)
        if not top:
            lines.append("- _(none)_")
        else:
            lines.append("| count | criterion (first 120 chars) |")
            lines.append("|---:|---|")
            for crit, cnt in top:
                lines.append(f"| {cnt} | `{crit}` |")
        lines.append("")
        lines.append("### Sample disagreements (top 12 for inspection)")
        if not b["examples_hf_mp"]:
            lines.append("- _(none)_")
        for ex in b["examples_hf_mp"]:
            lines.append(
                f"- task `{ex['task_id'][:8]}…` rubric `{ex['rubric_item_id'][:8]}…`  "
                f"`{ex['criterion']}`"
            )
            lines.append(
                f"  - hybrid: **{ex['hybrid_awarded']}/{ex['max_score']}** ({ex['hybrid_decided_by']})  "
                f"vs mini: **{ex['mini_awarded']}/{ex['max_score']}** ({ex['mini_decided_by']})"
            )
            lines.append(f"  - hybrid evidence: _{ex['hybrid_evidence']}_")
            if ex['mini_evidence'] and ex['mini_evidence'] != ex['hybrid_evidence']:
                lines.append(f"  - mini evidence  : _{ex['mini_evidence']}_")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("hybrid_json", type=Path)
    ap.add_argument("mini_json", type=Path)
    ap.add_argument("--out-md", type=Path, required=True)
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()
    s = stratify(args.hybrid_json, args.mini_json)
    args.out_md.write_text(render_markdown(s))
    if args.out_json:
        # examples include possibly-unicode evidence; ensure utf-8 dump
        args.out_json.write_text(json.dumps(s, indent=2, ensure_ascii=False))
    o = s["overall"]
    fp = s["buckets"]["formatting"]
    cp = s["buckets"]["content"]
    print(
        f"OK  total_pairs={o['total_critical_pairs']}  "
        f"hybrid_fail_mini_pass total={o['total_hf_mp']}  "
        f"format_share={o['formatting_share_of_hf_mp']*100:.1f}%  "
        f"content_share={o['content_share_of_hf_mp']*100:.1f}%  "
        f"format_gap={fp['gap_pp']:+.1f}pp  content_gap={cp['gap_pp']:+.1f}pp",
        flush=True,
    )
    print(f"wrote {args.out_md}", flush=True)
    if args.out_json:
        print(f"wrote {args.out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
