"""Phase 1 helper: enumerate gold_candidates for owner hand-grading.

Selects rubric items most relevant to the perception thesis:
  - critical-tier (|max_score| >= 4) regressed items from Phase 0(a)
  - visual / audio criteria from exp003 v2-mini grades (perception's target)
  - mini-vs-standard flip items in non-text modality from Phase 0(b)

Read-only. Writes a markdown candidate list. Owner hand-grades these.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "batch-runner"))

from core.grader_routing import classify_criterion  # type: ignore  # noqa: E402

GRADES = ROOT / "data" / "grades"
STD = GRADES / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json"
MINI = GRADES / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json"
V1 = GRADES / "exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json"
OUT = ROOT / "tasks" / "0531_sunday" / "gold_candidates.md"

VERDICT_RANK = {"fail": 0, "partial": 1, "pass": 2}


def _mod(s: str) -> str:
    m = classify_criterion(s).modality
    return getattr(m, "value", str(m))


def _short(s, n=120):
    if not s: return ""
    s = str(s).replace("\n", " ").replace("|", "/")
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> int:
    std = json.loads(STD.read_text())
    mini = json.loads(MINI.read_text())
    v1 = json.loads(V1.read_text())
    std_tasks = {t["task_id"]: t for t in std["tasks"]}
    mini_tasks = {t["task_id"]: t for t in mini["tasks"]}
    v1_tasks = {t["task_id"]: t for t in v1["tasks"]}
    shared = sorted(set(std_tasks) & set(mini_tasks) & set(v1_tasks))

    candidates: dict[tuple[str, str], dict] = {}

    def add(task, item_mini, item_v1, item_std, reason):
        key = (task, item_mini["rubric_item_id"])
        if key in candidates:
            candidates[key]["reasons"].add(reason)
            return
        crit = item_mini.get("criterion", "")
        candidates[key] = {
            "task": task,
            "rid": item_mini["rubric_item_id"],
            "criterion": crit,
            "modality": _mod(crit),
            "max_score": item_mini.get("max_score"),
            "v_mini": item_mini.get("verdict"),
            "v_std": item_std.get("verdict") if item_std else None,
            "v_v1": item_v1.get("verdict") if item_v1 else None,
            "reasons": {reason},
        }

    for tid in shared:
        std_items = {it["rubric_item_id"]: it for it in std_tasks[tid]["items"]}
        v1_items = {it["rubric_item_id"]: it for it in v1_tasks[tid]["items"]}
        for it_m in mini_tasks[tid]["items"]:
            rid = it_m["rubric_item_id"]
            it_s = std_items.get(rid)
            it_v1 = v1_items.get(rid)
            crit = it_m.get("criterion", "")
            modality = _mod(crit)
            max_score = int(it_m.get("max_score") or 0)
            v_m = str(it_m.get("verdict", "")).lower()
            v_v1 = str(it_v1.get("verdict", "")).lower() if it_v1 else ""

            # (1) visual or audio items — perception's direct target.
            if modality in ("visual", "audio"):
                add(tid, it_m, it_v1, it_s, f"modality:{modality}")

            # (2) critical regression: v1 right, v2-mini wrong, |max|>=4.
            if (abs(max_score) >= 4
                    and v_v1 in VERDICT_RANK and v_m in VERDICT_RANK
                    and VERDICT_RANK[v_v1] > VERDICT_RANK[v_m]):
                add(tid, it_m, it_v1, it_s, "critical_regression")

            # (3) mini-vs-standard flip in non-text modality.
            if it_s is not None:
                v_s = str(it_s.get("verdict", "")).lower()
                if (v_s in VERDICT_RANK and v_m in VERDICT_RANK
                        and VERDICT_RANK[v_m] > VERDICT_RANK[v_s]
                        and modality != "text"):
                    add(tid, it_m, it_v1, it_s, f"flip_nontext:{v_s}->{v_m}")

    items = list(candidates.values())
    by_mod = defaultdict(int)
    for c in items:
        by_mod[c["modality"]] += 1

    lines: list[str] = []
    lines.append("# Gold candidates — owner hand-grading list (Phase 1)")
    lines.append("")
    lines.append("GDPVal's `rubric_json` provides only `score` + `criterion` + optional "
                 "`gold_deliverable_files` — **no per-item expected verdict** "
                 "(pass/partial/fail) exists. Therefore the thesis (Phase 4) cannot be "
                 "judged against dataset gold. This file lists the rubric items the owner "
                 "must hand-grade to produce a gold set.")
    lines.append("")
    lines.append(f"Total candidates: **{len(items)}** "
                 f"(by modality: {dict(by_mod)})")
    lines.append("")
    lines.append("Selection rules:")
    lines.append("- (1) every `visual` / `audio` criterion in the 10 shared exp003 tasks — perception's direct target")
    lines.append("- (2) `critical_regression` (|max_score| >= 4 and v1-mini > v2-mini verdict)")
    lines.append("- (3) `flip_nontext` (mini > standard verdict on non-text modality)")
    lines.append("")
    lines.append("Hand-grading guide:")
    lines.append("- Open the deliverable at `batch-runner/results/exp003*/<task>/...` "
                 "(or HF parquet if not local).")
    lines.append("- Decide the verdict **only** from the criterion text + the deliverable, "
                 "without looking at any judge's verdict/evidence.")
    lines.append("- Allowed verdicts: `pass`, `partial`, `fail`, or `unsure` "
                 "(`unsure` is dropped from the gold set, not counted as judge_error).")
    lines.append("- Record verdicts in a sibling file `gold_verdicts.json` keyed by `(task, rid)`.")
    lines.append("")
    lines.append("## Candidates")
    lines.append("")
    lines.append("| task | rid | modality | max | v_v1 | v_std | v_mini | reasons | criterion |")
    lines.append("|---|---|---|---:|---|---|---|---|---|")
    items.sort(key=lambda c: (c["modality"], c["task"]))
    for c in items:
        lines.append(
            f"| {c['task'][:8]} | {c['rid'][:8]} | {c['modality']} | {c['max_score']} "
            f"| {c['v_v1'] or ''} | {c['v_std'] or ''} | {c['v_mini'] or ''} "
            f"| {','.join(sorted(c['reasons']))} | {_short(c['criterion'], 90)} |"
        )
    lines.append("")
    OUT.write_text("\n".join(lines))
    print(f"Wrote {OUT}: {len(items)} candidates, modalities={dict(by_mod)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
