#!/usr/bin/env python3
"""text-criterion mini-vs-5.4 reliability probe (0609_tuesday). UNCOMMITTED.

Re-grade a small stratified sample of TEXT-routed judge items with gpt-5.4 and
compare against the existing mini grades (from the 220 mini JSON). Text criteria
are objective (numeric/existence/value), so disagreements can be adjudicated by
opening the file. NO render (text is render-irrelevant). NO 220 re-grade.

Reuses the vv.py judge/client/auth path. Writes text_grades.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/Users/hsjeon/git/gdpval-realworks")
BR = ROOT / "batch-runner"
DELI = BR / "workspace" / "upload" / "deliverable_files"
T09 = ROOT / "tasks" / "0609_tuesday"
VV = ROOT / "tasks" / "0607_sunday" / "vision_validation"
PROMPT = BR / "prompts" / "grader_judge_v2.md"
MODEL = "gpt-5.4"

sys.path.insert(0, str(BR))
sys.path.insert(0, str(VV))
import vv  # reuse build_client, gather_meta, load_instructions, judge, prep_env  # noqa: E402


def gather_text_meta(abspath: str) -> dict:
    """Like vv.gather_meta but with a larger read_content window — text
    criteria need enough content for the fact to actually appear. Both arms
    are judged from this same observation block, so the comparison is fair;
    a too-small window would make BOTH miss the fact, not just one."""
    from core.tools import read_deliverable
    src = Path(abspath)
    base = src.parent
    rel = src.name
    out = {}
    for op in ("inspect_structure", "inspect_formatting"):
        r = read_deliverable(op, rel, base_dir=str(base))
        out[op] = r.get("data") if r.get("ok") else {"error": r.get("error")}
    rc = read_deliverable("read_content", rel, base_dir=str(base))
    text = rc["data"].get("text", "") if rc.get("ok") else ""
    out["read_content"] = text[:60000]
    out["read_content_truncated"] = len(text) > 60000
    return out


def make_text_input(filename, sector, occ, prompt, criterion, max_score, meta):
    obs = json.dumps(meta, ensure_ascii=False, indent=1)[:50000]
    blocks = [
        "## Routing hint",
        "- modality: text",
        "## Task context (for context only - do not grade)",
        f"- Sector: {sector}\n- Occupation: {occ}\n- Original task prompt:\n  {prompt[:500]}",
        "## Rubric item to grade",
        f"- max_score: {max_score}\n- required: null\n- criterion:\n  {criterion}",
        "## Selected candidate deliverable file",
        f"- path: `{filename}`",
        "## Pre-gathered read_deliverable observations",
        "The harness already called read_deliverable for you. Treat the JSON "
        "below as authoritative tool results; you do NOT need to (and cannot) "
        "call tools. Your `evidence` MUST quote something visible here.",
        "```json\n" + obs + "\n```",
        "## No image\nThis is a text/factual criterion. Judge whether the "
        "deliverable content satisfies the criterion, grounded in the "
        "observations above.",
        "Return ONLY the JSON envelope now (no prose, no code fence).",
    ]
    return "\n\n".join(blocks)


def main():
    vv.prep_env()
    client = vv.build_client()
    instr = vv.load_instructions()
    sample = json.load(open(T09 / "_text_sample.json"))
    prompts = vv._load_task_prompts()
    # task sector/occupation from 220 mini JSON
    mini = json.load(open(ROOT / "data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json"))
    meta_by_task = {t["task_id"]: (t.get("sector", ""), t.get("occupation", "")) for t in mini["tasks"]}

    results = []
    for i, c in enumerate(sample, 1):
        tid = c["task_id"]
        ap = DELI / tid / c["file"]
        sector, occ = meta_by_task.get(tid, ("", ""))
        prompt = prompts.get(tid, "")
        meta = gather_text_meta(str(ap))
        txt = make_text_input(c["file"], sector, occ, prompt, c["criterion"],
                              c["max"], meta)
        r = vv.judge(client, instr, txt, None)
        row = dict(c)
        row.update({
            "g54_award": round(r["awarded"], 3),
            "g54_verdict": r["verdict"],
            "g54_partial": r["partial"],
            "g54_evidence": r.get("evidence", ""),
            "g54_reasoning": r.get("reasoning", ""),
        })
        results.append(row)
        agree = "✓" if r["verdict"] == c["mini_verdict"] else "✗DIFF"
        print(f"{i:2}/{len(sample)} {c['task']} {c['type']:9} "
              f"mini={c['mini_verdict']:7}:{c['mini_award']}/{c['max']}  "
              f"5.4={r['verdict']:7}:{r['awarded']:.2f}  {agree}")
        json.dump(results, open(T09 / "text_grades.json", "w"),
                  ensure_ascii=False, indent=1)
    # summary
    n = len(results)
    agree = sum(1 for r in results if r["g54_verdict"] == r["mini_verdict"])
    # normalize award to fraction of max for score-diff
    def frac(r, key):
        return (r[key] / r["max"]) if r["max"] else 0.0
    diffs = [abs(frac(r, "g54_award") - frac(r, "mini_award")) for r in results]
    print("\n" + "=" * 60)
    print(f"verdict agreement: {agree}/{n} = {agree/n*100:.1f}%")
    print(f"|score diff| (frac of max): mean {sum(diffs)/n:.3f} max {max(diffs):.3f}")
    print(f"disagreements: {n-agree}")


if __name__ == "__main__":
    main()
