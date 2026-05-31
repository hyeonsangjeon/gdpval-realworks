#!/usr/bin/env python3
"""PHASE 0 — V1<->V5 hypothesis test (read-only, free).

For the 10 shared exp003 tasks, find CRITICAL rubric items
(abs(max_score) >= 4) where v2-mini judged the model WRONG
(model_did_right == False) but v1-mini judged it RIGHT
(model_did_right == True) — i.e. the critical-pass regression
PR3_VERIFICATION measured.

Classify each regressed item by perception modality using the
production keyword classifier (core.grader_routing.classify_criterion).

Verdict:
  - regressed items mostly visual/audio/formatting -> HYPOTHESIS SUPPORTED
    (the V1 regression may be a symptom of unwired perception)
  - regressed items mostly text -> HYPOTHESIS REJECTED
    (regression is unrelated to perception)

No grade run, no network, no writes to grades.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Load the pure-functional classifier directly (avoid core/__init__ heavy deps).
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "grader_routing", ROOT / "batch-runner" / "core" / "grader_routing.py"
)
_gr = importlib.util.module_from_spec(_spec)
sys.modules["grader_routing"] = _gr
_spec.loader.exec_module(_gr)
classify_criterion = _gr.classify_criterion

GRADES = ROOT / "data" / "grades"
V2_MINI = GRADES / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json"
V1_MINI = GRADES / "exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1__v2sm.json"

CRIT_THRESHOLD = 4


def crit(item: dict) -> bool:
    return abs(int(item["max_score"])) >= CRIT_THRESHOLD


def right(item: dict) -> bool:
    # sign-aware: prefer model_did_right when present, else fall back.
    if "model_did_right" in item and item["model_did_right"] is not None:
        return bool(item["model_did_right"])
    v = str(item.get("verdict", "")).lower()
    return (v == "pass") == (int(item["max_score"]) >= 0)


def load_tasks(path: Path) -> dict[str, dict]:
    d = json.load(open(path))
    return {t["task_id"]: t for t in d["tasks"]}


def main() -> None:
    v2 = load_tasks(V2_MINI)
    v1 = load_tasks(V1_MINI)
    shared = sorted(set(v2) & set(v1))

    regressed: list[dict] = []   # crit items v1 right, v2 wrong
    recovered: list[dict] = []   # crit items v2 right, v1 wrong
    for tid in shared:
        v2items = {i["rubric_item_id"]: i for i in v2[tid]["items"]}
        v1items = {i["rubric_item_id"]: i for i in v1[tid]["items"]}
        for rid, v2i in v2items.items():
            if not crit(v2i):
                continue
            v1i = v1items.get(rid)
            if v1i is None:
                continue
            d2, d1 = right(v2i), right(v1i)
            if d1 and not d2:
                regressed.append({"task": tid, "rid": rid, "v2": v2i, "v1": v1i})
            elif d2 and not d1:
                recovered.append({"task": tid, "rid": rid, "v2": v2i, "v1": v1i})

    def classify(row: dict) -> str:
        return classify_criterion(row["v2"]["criterion"]).modality.value

    reg_modal = Counter(classify(r) for r in regressed)
    rec_modal = Counter(classify(r) for r in recovered)

    perception_modal = {"visual", "audio", "formatting"}
    reg_perception = sum(v for k, v in reg_modal.items() if k in perception_modal)
    reg_text = reg_modal.get("text", 0)

    print("# PHASE 0 — critical-item modality (v2-mini vs v1-mini)\n")
    print(f"Shared tasks: {len(shared)}")
    print(f"Critical = abs(max_score) >= {CRIT_THRESHOLD}\n")
    print(f"REGRESSED critical items (v1-mini RIGHT, v2-mini WRONG): {len(regressed)}")
    print(f"  modality breakdown: {dict(reg_modal)}")
    print(f"  perception (visual+audio+formatting): {reg_perception} | text: {reg_text}\n")
    print(f"RECOVERED critical items (v2-mini RIGHT, v1-mini WRONG): {len(recovered)}")
    print(f"  modality breakdown: {dict(rec_modal)}\n")

    print("## Regressed items detail\n")
    print("| task | modality | v2 verdict | v1 verdict | max | criterion |")
    print("|---|---|---|---|---|---|")
    for r in sorted(regressed, key=lambda x: classify(x)):
        c = r["v2"]["criterion"].replace("|", "\\|")[:90]
        print(f"| {r['task'][:8]} | {classify(r)} | {r['v2']['verdict']} | "
              f"{r['v1']['verdict']} | {r['v2']['max_score']} | {c} |")

    print("\n## Recovered items detail\n")
    print("| task | modality | v2 verdict | v1 verdict | max | criterion |")
    print("|---|---|---|---|---|---|")
    for r in sorted(recovered, key=lambda x: classify(x)):
        c = r["v2"]["criterion"].replace("|", "\\|")[:90]
        print(f"| {r['task'][:8]} | {classify(r)} | {r['v2']['verdict']} | "
              f"{r['v1']['verdict']} | {r['v2']['max_score']} | {c} |")

    # Verdict
    print("\n## Hypothesis verdict\n")
    if len(regressed) == 0:
        print("No regressed critical items found — re-check inputs.")
        return
    frac_perc = reg_perception / len(regressed)
    if frac_perc >= 0.5:
        print(f"SUPPORTED: {reg_perception}/{len(regressed)} "
              f"({frac_perc:.0%}) regressed critical items are "
              f"visual/audio/formatting. The V1 critical regression is "
              f"plausibly a symptom of unwired perception.")
    else:
        print(f"REJECTED: only {reg_perception}/{len(regressed)} "
              f"({frac_perc:.0%}) regressed critical items are "
              f"perception-modality; {reg_text} are TEXT. The V1 "
              f"regression is mostly unrelated to perception wiring.")


if __name__ == "__main__":
    main()
