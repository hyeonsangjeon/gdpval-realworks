"""Phase 0(b): fail->pass / partial->pass flip decomposition by modality.

Compare v2-mini vs v2-standard (rubric_v2_tools_mini vs rubric_v2_tools)
on the same exp003 shared tasks. For items where mini is more lenient
(higher verdict than standard), classify the criterion via
grader_routing.classify_criterion and break down by modality. Also
inspect whether mini's evidence is similar to standard's (same evidence,
different verdict = pure leniency) or different (different reading).

Read-only. Writes a markdown report to tasks/0531_sunday/.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "batch-runner"))

from core.grader_routing import classify_criterion  # type: ignore  # noqa: E402

GRADES = ROOT / "data" / "grades"
STANDARD = GRADES / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json"
MINI = GRADES / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json"
OUT = ROOT / "tasks" / "0531_sunday" / "phase0b_flip_decomp.md"

VERDICT_RANK = {"fail": 0, "partial": 1, "pass": 2}


def _short(s: str | None, n: int = 100) -> str:
    if not s:
        return ""
    s = str(s).replace("\n", " ").replace("|", "/")
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    std = json.loads(STANDARD.read_text())
    mini = json.loads(MINI.read_text())
    std_tasks = {t["task_id"]: t for t in std["tasks"]}
    mini_tasks = {t["task_id"]: t for t in mini["tasks"]}
    shared = sorted(set(std_tasks) & set(mini_tasks))

    flips: list[dict] = []
    for tid in shared:
        std_items = {it["rubric_item_id"]: it for it in std_tasks[tid]["items"]}
        for it_m in mini_tasks[tid]["items"]:
            rid = it_m["rubric_item_id"]
            it_s = std_items.get(rid)
            if it_s is None:
                continue
            v_s = str(it_s.get("verdict", "")).lower()
            v_m = str(it_m.get("verdict", "")).lower()
            if v_s not in VERDICT_RANK or v_m not in VERDICT_RANK:
                continue
            if VERDICT_RANK[v_m] <= VERDICT_RANK[v_s]:
                continue
            criterion = it_m.get("criterion", "")
            _mod = classify_criterion(criterion).modality
            modality = getattr(_mod, "value", str(_mod))
            flips.append({
                "task": tid[:8],
                "rid": rid,
                "criterion": criterion,
                "modality": modality,
                "max": it_m.get("max_score"),
                "v_std": v_s,
                "v_mini": v_m,
                "type": f"{v_s}->{v_m}",
                "ev_std": it_s.get("evidence") or "",
                "ev_mini": it_m.get("evidence") or "",
                "decided_by_std": it_s.get("decided_by"),
                "decided_by_mini": it_m.get("decided_by"),
            })

    flips_judge = [
        f for f in flips
        if (f["decided_by_std"] or "").lower() == "judge"
        or (f["decided_by_mini"] or "").lower() == "judge"
    ]

    type_counts = Counter(f["type"] for f in flips)
    mod_by_type: dict[str, Counter] = defaultdict(Counter)
    for f in flips:
        mod_by_type[f["type"]][f["modality"]] += 1
    mod_total = Counter(f["modality"] for f in flips)

    # Evidence similarity (very loose): "same" if normalized strings share >=70% chars.
    def same_evidence(a: str, b: str) -> bool:
        if not a or not b:
            return False
        a2 = "".join(a.lower().split())
        b2 = "".join(b.lower().split())
        if not a2 or not b2:
            return False
        short, long_ = (a2, b2) if len(a2) <= len(b2) else (b2, a2)
        # contiguous substring containment OR high overlap of char-bag
        if short in long_:
            return True
        common = sum((Counter(short) & Counter(long_)).values())
        return common / max(len(short), 1) >= 0.7

    same_ev = sum(1 for f in flips if same_evidence(f["ev_std"], f["ev_mini"]))

    lines: list[str] = []
    lines.append("# PHASE 0(b) — fail->pass / partial->pass flip decomposition (mini vs standard)")
    lines.append("")
    lines.append(f"Shared exp003 tasks: {len(shared)}")
    lines.append(f"Total leniency flips (mini > standard): {len(flips)}")
    lines.append(f"  judge-decided side (either): {len(flips_judge)} (rest involve precheck)")
    lines.append(f"  type counts: {dict(type_counts)}")
    lines.append(f"  modality totals: {dict(mod_total)}")
    lines.append("")
    lines.append("## Modality breakdown by flip type")
    lines.append("")
    lines.append("| type | total | visual | audio | formatting | text |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for tp, c in sorted(type_counts.items(), key=lambda kv: -kv[1]):
        m = mod_by_type[tp]
        lines.append(
            f"| {tp} | {c} | {m.get('visual',0)} | {m.get('audio',0)} "
            f"| {m.get('formatting',0)} | {m.get('text',0)} |"
        )
    lines.append("")
    lines.append(f"Evidence similarity (loose char-overlap >=70% or substring): "
                 f"{same_ev}/{len(flips)} flips look like *same evidence, different verdict* "
                 "(consistent with leniency rather than mini reading differently).")
    lines.append("")
    lines.append("## All flips (detailed)")
    lines.append("")
    lines.append("| task | type | modality | max | criterion | std evidence | mini evidence |")
    lines.append("|---|---|---|---:|---|---|---|")
    for f in flips:
        lines.append(
            f"| {f['task']} | {f['type']} | {f['modality']} | {f['max']} "
            f"| {_short(f['criterion'], 70)} | {_short(f['ev_std'], 70)} "
            f"| {_short(f['ev_mini'], 70)} |"
        )
    lines.append("")
    lines.append("## Hypothesis verdict (Phase 0b)")
    lines.append("")
    visual_audio_form = (
        mod_total.get("visual", 0)
        + mod_total.get("audio", 0)
        + mod_total.get("formatting", 0)
    )
    text = mod_total.get("text", 0)
    if len(flips) == 0:
        verdict = "NO FLIPS — cannot evaluate."
    elif visual_audio_form > text:
        verdict = (
            f"SUPPORTED (weak): {visual_audio_form}/{len(flips)} flips are "
            f"non-text modality (visual+audio+formatting). Consistent with "
            f"text judge's modality blindness being part of the leniency. "
            f"But only visual+audio flips can be addressed by perception "
            f"wiring (formatting routes to inspect_formatting tool, not a "
            f"sub-judge). visual+audio flip count = "
            f"{mod_total.get('visual',0) + mod_total.get('audio',0)}."
        )
    else:
        verdict = (
            f"REJECTED: {text}/{len(flips)} flips are pure text criteria. "
            "Leniency is not a modality-blindness symptom; perception wiring "
            "is unlikely to recover these. Investigate judge strictness drift "
            "independently."
        )
    lines.append(verdict)
    lines.append("")
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}")
    print(f"flips={len(flips)} types={dict(type_counts)} modalities={dict(mod_total)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
