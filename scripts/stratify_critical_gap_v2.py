#!/usr/bin/env python3
"""Stratify hybrid vs mini critical-item disagreement, sign-aware.

This is the v2 stratifier; supersedes the first cut of
`stratify_critical_gap.py` (which assumed all critical items are positive
and treated `verdict == 'pass'` as the universal "good" signal).

Key changes
-----------
1. Critical set redefined as `|max_score| >= MAGNITUDE_THRESHOLD` (default 4)
   to include both high-positive (must satisfy) and high-negative (must
   not violate) rubric items. The previous `score >= 4` rule excluded
   94 negative-magnitude penalty items, several of which are the largest
   single-item stakes in the entire rubric (-85, -60, -20×2).

2. Sign-aware semantics. The judge emits `verdict == "pass"` with very
   different meaning depending on the sign of the rubric item:

       positive items:  pass  = deliverable satisfied the criterion (good)
                        fail  = it didn't satisfy (bad)
       negative items:  pass  = the bad thing happened (penalty applied, bad)
                        fail  = the bad thing did not happen (good)

   We normalize this to a single `model_did_right(item)` boolean before
   computing pass-rate, gap, and disagreement direction. Without this,
   aggregating positive + negative items with the same `verdict=='pass'`
   filter produces gibberish.

3. Three buckets instead of two: `formatting`, `content`, and
   `penalty` (anti-criteria, score < 0). Formatting/content split is
   only applied within the positive subset; penalty items always go to
   the penalty bucket regardless of their criterion text.

4. Reports both directional disagreement counts:
       hybrid_stricter_count : hybrid says "model did wrong", mini says "right"
       mini_stricter_count   : mini says "model did wrong", hybrid says "right"
   With sign normalization these have a single consistent meaning across
   all buckets.

The script also still emits a 'criterion'-text top-N table per bucket
so the human reviewer can see which specific rubric items drive each
bucket's gap.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

MAGNITUDE_THRESHOLD = 4  # |max_score| >= 4 → "critical"

# Same patterns as v1, kept stable so report diff vs v1 is purely the
# sign-handling fix.
FORMATTING_PATTERNS = re.compile(
    r"format|style|layout|structur|presentation|appearance|visual|"
    r"organi[sz]ation of the deliverable|overall.*deliverable|"
    r"properly formatted|well[- ]formatted|professional.*look|"
    r"clean.*format|clear.*layout|readable|legibl",
    re.IGNORECASE,
)


# ---------- sign-aware item primitives ----------

def _is_critical(item: dict) -> bool:
    try:
        return abs(item.get("max_score") or 0) >= MAGNITUDE_THRESHOLD
    except Exception:
        return False


def _is_penalty(item: dict) -> bool:
    try:
        return (item.get("max_score") or 0) < 0
    except Exception:
        return False


def _model_did_right(item: dict) -> bool:
    """Returns True when the deliverable was judged favorably for this item,
    independent of item sign.

    - positive item: verdict == 'pass'
    - negative item: verdict != 'pass' (i.e., the bad thing did NOT happen)

    'judge_error' and unknown verdicts count as "did wrong" (conservative).
    """
    verdict = item.get("verdict")
    ms = item.get("max_score") or 0
    if ms < 0:
        return verdict != "pass"
    return verdict == "pass"


def _bucket(item: dict) -> str:
    if _is_penalty(item):
        return "penalty"
    criterion = item.get("criterion") or ""
    if FORMATTING_PATTERNS.search(criterion):
        return "formatting"
    return "content"


# ---------- aggregation ----------

def _by_task(grade: dict) -> dict[str, dict]:
    return {t["task_id"]: t for t in grade.get("tasks", [])}


def stratify(hybrid_path: Path, mini_path: Path) -> dict:
    H = json.loads(hybrid_path.read_text())
    M = json.loads(mini_path.read_text())
    Hb = _by_task(H)
    Mb = _by_task(M)
    common = sorted(set(Hb) & set(Mb))

    pairs: list[tuple[str, str, dict, dict]] = []  # (tid, rid, hi, mi)
    for tid in common:
        h_items = {i["rubric_item_id"]: i for i in Hb[tid].get("items", [])}
        m_items = {i["rubric_item_id"]: i for i in Mb[tid].get("items", [])}
        for rid in set(h_items) & set(m_items):
            hi, mi = h_items[rid], m_items[rid]
            if _is_critical(hi) or _is_critical(mi):
                pairs.append((tid, rid, hi, mi))

    EXAMPLES_PER_BUCKET = 12

    buckets: dict[str, dict] = {
        b: {
            "n_pairs": 0,
            "hybrid_right": 0,           # sign-aware "model did right" count
            "mini_right": 0,
            "both_right": 0,
            "both_wrong": 0,
            "hybrid_stricter": 0,        # hybrid=wrong, mini=right
            "mini_stricter": 0,          # mini=wrong, hybrid=right
            "top_disagree_h_stricter": Counter(),
            "top_disagree_m_stricter": Counter(),
            "by_decided_by_h_stricter": Counter(),
            "examples_h_stricter": [],
            "examples_m_stricter": [],
        }
        for b in ("formatting", "content", "penalty")
    }

    for (tid, rid, hi, mi) in pairs:
        b = buckets[_bucket(hi)]
        b["n_pairs"] += 1
        h_right = _model_did_right(hi)
        m_right = _model_did_right(mi)
        if h_right: b["hybrid_right"] += 1
        if m_right: b["mini_right"] += 1
        if h_right and m_right:
            b["both_right"] += 1
        elif (not h_right) and (not m_right):
            b["both_wrong"] += 1
        elif (not h_right) and m_right:
            # hybrid says wrong, mini says right → hybrid stricter
            b["hybrid_stricter"] += 1
            key = ((hi.get("criterion") or "")).strip().lower()[:120]
            b["top_disagree_h_stricter"][key] += 1
            b["by_decided_by_h_stricter"][hi.get("decided_by") or "?"] += 1
            if len(b["examples_h_stricter"]) < EXAMPLES_PER_BUCKET:
                b["examples_h_stricter"].append(_make_example(tid, rid, hi, mi))
        else:
            # h_right and not m_right → mini stricter
            b["mini_stricter"] += 1
            key = ((hi.get("criterion") or "")).strip().lower()[:120]
            b["top_disagree_m_stricter"][key] += 1
            if len(b["examples_m_stricter"]) < EXAMPLES_PER_BUCKET:
                b["examples_m_stricter"].append(_make_example(tid, rid, hi, mi))

    for b in buckets.values():
        n = max(1, b["n_pairs"])
        b["hybrid_right_rate"] = round(b["hybrid_right"] / n, 4)
        b["mini_right_rate"] = round(b["mini_right"] / n, 4)
        b["gap_pp"] = round((b["hybrid_right_rate"] - b["mini_right_rate"]) * 100, 2)
        b["hybrid_stricter_share"] = round(b["hybrid_stricter"] / n, 4)
        b["mini_stricter_share"] = round(b["mini_stricter"] / n, 4)
        b["net_directional_disagreement"] = b["hybrid_stricter"] - b["mini_stricter"]

    total_pairs = sum(b["n_pairs"] for b in buckets.values())
    total_h_stricter = sum(b["hybrid_stricter"] for b in buckets.values())
    total_m_stricter = sum(b["mini_stricter"] for b in buckets.values())
    overall = {
        "total_critical_pairs": total_pairs,
        "total_hybrid_stricter": total_h_stricter,
        "total_mini_stricter": total_m_stricter,
        "net_directional_disagreement": total_h_stricter - total_m_stricter,
        "share_of_h_stricter_by_bucket": {
            name: round(b["hybrid_stricter"] / max(1, total_h_stricter), 4)
            for name, b in buckets.items()
        },
        "share_of_m_stricter_by_bucket": {
            name: round(b["mini_stricter"] / max(1, total_m_stricter), 4)
            for name, b in buckets.items()
        },
    }

    # Sign-aware overall pass rate (= "model did right" across all critical items)
    all_h_right = sum(b["hybrid_right"] for b in buckets.values())
    all_m_right = sum(b["mini_right"] for b in buckets.values())
    if total_pairs > 0:
        overall["overall_hybrid_right_rate"] = round(all_h_right / total_pairs, 4)
        overall["overall_mini_right_rate"] = round(all_m_right / total_pairs, 4)
        overall["overall_gap_pp"] = round(
            (overall["overall_hybrid_right_rate"] - overall["overall_mini_right_rate"]) * 100, 2
        )

    return {
        "hybrid_path": str(hybrid_path),
        "mini_path": str(mini_path),
        "task_pairs": len(common),
        "buckets": buckets,
        "overall": overall,
        "magnitude_threshold": MAGNITUDE_THRESHOLD,
    }


def _make_example(tid: str, rid: str, hi: dict, mi: dict) -> dict:
    return {
        "task_id": tid,
        "rubric_item_id": rid,
        "criterion": (hi.get("criterion") or "")[:160],
        "max_score": hi.get("max_score") or mi.get("max_score"),
        "hybrid_verdict": hi.get("verdict"),
        "hybrid_awarded": hi.get("awarded_score"),
        "hybrid_decided_by": hi.get("decided_by"),
        "mini_verdict": mi.get("verdict"),
        "mini_awarded": mi.get("awarded_score"),
        "mini_decided_by": mi.get("decided_by"),
        "hybrid_evidence": (hi.get("evidence") or "")[:240],
        "mini_evidence": (mi.get("evidence") or "")[:240],
    }


def render_markdown(s: dict) -> str:
    L = []
    L.append("# Critical-Item Disagreement Stratification — Sign-Aware (Probe Y₁ v2)\n")
    L.append(f"- hybrid: `{Path(s['hybrid_path']).name}`")
    L.append(f"- mini  : `{Path(s['mini_path']).name}`")
    L.append(f"- task pairs: {s['task_pairs']}")
    L.append(f"- critical definition: `|max_score| >= {s['magnitude_threshold']}` (covers high-positive AND high-negative items)")
    L.append(f"- 'model_did_right' = `verdict=='pass'` for positive items, `verdict!='pass'` for negative items")
    L.append("")
    o = s["overall"]
    L.append("## Headline (sign-aware)")
    L.append(f"- total critical (rubric item) pairs: **{o['total_critical_pairs']}**")
    L.append(f"- overall hybrid_right_rate: **{o['overall_hybrid_right_rate']:.3f}**")
    L.append(f"- overall mini_right_rate  : **{o['overall_mini_right_rate']:.3f}**")
    L.append(f"- overall gap: **{o['overall_gap_pp']:+.2f}pp**  (positive = hybrid more lenient overall; negative = hybrid stricter overall)")
    L.append("")
    L.append("## Where does the disagreement come from?")
    L.append(f"- total hybrid-stricter pairs (hybrid=wrong, mini=right): **{o['total_hybrid_stricter']}**")
    L.append(f"- total mini-stricter   pairs (mini=wrong, hybrid=right): **{o['total_mini_stricter']}**")
    L.append(f"- net directional gap: **{o['net_directional_disagreement']:+d}**  (positive = hybrid strict more often)")
    L.append("")
    L.append("### Share of hybrid-stricter pairs by bucket")
    for name, share in o["share_of_h_stricter_by_bucket"].items():
        L.append(f"- {name:<10}: {share*100:5.1f}%")
    L.append("")
    L.append("### Share of mini-stricter pairs by bucket")
    for name, share in o["share_of_m_stricter_by_bucket"].items():
        L.append(f"- {name:<10}: {share*100:5.1f}%")
    L.append("")
    L.append("> Interpretation:")
    L.append("> - **hybrid-stricter ≫ mini-stricter, concentrated in formatting** → Scenario B (hybrid over-rejects, extraction artifact)")
    L.append("> - **hybrid-stricter ≫ mini-stricter, concentrated in content/penalty** → Scenario A (hybrid catches real failures)")
    L.append("> - **mini-stricter > hybrid-stricter in penalty** → mini catches anti-criteria hybrid misses (a separate, opposite signal)")
    L.append("> - **roughly balanced everywhere** → noise; neither is meaningfully better")
    L.append("")

    for name, b in s["buckets"].items():
        L.append(f"## Bucket: `{name}`  (pairs: {b['n_pairs']})")
        if b["n_pairs"] == 0:
            L.append("- _(empty)_")
            L.append("")
            continue
        L.append(f"- hybrid_right_rate: {b['hybrid_right_rate']:.3f}  |  mini_right_rate: {b['mini_right_rate']:.3f}  |  gap: **{b['gap_pp']:+.1f}pp**")
        L.append(f"- agreement: both_right={b['both_right']}  both_wrong={b['both_wrong']}  "
                 f"hybrid_stricter={b['hybrid_stricter']}  mini_stricter={b['mini_stricter']}")
        L.append(f"- net directional (h - m): **{b['net_directional_disagreement']:+d}**")
        L.append(f"- hybrid-stricter decided by tier: {dict(b['by_decided_by_h_stricter'])}")
        L.append("")
        L.append("### Top hybrid-stricter criteria (hybrid wrong / mini right)")
        top = b["top_disagree_h_stricter"].most_common(10)
        if not top:
            L.append("- _(none)_")
        else:
            L.append("| count | criterion (first 120 chars) |")
            L.append("|---:|---|")
            for crit, cnt in top:
                L.append(f"| {cnt} | `{crit}` |")
        L.append("")
        if b["mini_stricter"]:
            L.append("### Top mini-stricter criteria (mini wrong / hybrid right)")
            top = b["top_disagree_m_stricter"].most_common(10)
            L.append("| count | criterion (first 120 chars) |")
            L.append("|---:|---|")
            for crit, cnt in top:
                L.append(f"| {cnt} | `{crit}` |")
            L.append("")

        L.append("### Sample hybrid-stricter (top 12)")
        for ex in b["examples_h_stricter"]:
            L.append(
                f"- task `{ex['task_id'][:8]}…` rubric `{ex['rubric_item_id'][:8]}…`  "
                f"(max_score={ex['max_score']})  `{ex['criterion']}`"
            )
            L.append(
                f"  - hybrid: verdict=**{ex['hybrid_verdict']}** awarded={ex['hybrid_awarded']} ({ex['hybrid_decided_by']})  "
                f"vs mini: verdict=**{ex['mini_verdict']}** awarded={ex['mini_awarded']} ({ex['mini_decided_by']})"
            )
            L.append(f"  - hybrid evidence: _{ex['hybrid_evidence']}_")
        if b["examples_m_stricter"]:
            L.append("")
            L.append("### Sample mini-stricter (top 12)")
            for ex in b["examples_m_stricter"]:
                L.append(
                    f"- task `{ex['task_id'][:8]}…` rubric `{ex['rubric_item_id'][:8]}…`  "
                    f"(max_score={ex['max_score']})  `{ex['criterion']}`"
                )
                L.append(
                    f"  - hybrid: verdict=**{ex['hybrid_verdict']}** awarded={ex['hybrid_awarded']}  "
                    f"vs mini: verdict=**{ex['mini_verdict']}** awarded={ex['mini_awarded']}"
                )
                L.append(f"  - mini evidence: _{ex['mini_evidence']}_")
        L.append("")
    return "\n".join(L) + "\n"


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
        args.out_json.write_text(json.dumps(s, indent=2, ensure_ascii=False))
    o = s["overall"]
    print(
        f"OK  pairs={o['total_critical_pairs']}  "
        f"h_right={o['overall_hybrid_right_rate']:.3f}  m_right={o['overall_mini_right_rate']:.3f}  "
        f"gap={o['overall_gap_pp']:+.2f}pp  "
        f"h_stricter={o['total_hybrid_stricter']}  m_stricter={o['total_mini_stricter']}  "
        f"net={o['net_directional_disagreement']:+d}",
        flush=True,
    )
    for name, share in o["share_of_h_stricter_by_bucket"].items():
        print(f"  bucket {name:<10} h_stricter_share={share*100:5.1f}%", flush=True)
    print(f"wrote {args.out_md}", flush=True)
    if args.out_json:
        print(f"wrote {args.out_json}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
