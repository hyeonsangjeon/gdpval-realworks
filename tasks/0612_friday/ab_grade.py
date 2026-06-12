#!/usr/bin/env python3
"""PART 1c — gold-20 "Overall style" A/B: current prompt vs tuned prompt (1b).

2-arm *isolated* setting (pre-gathered read_deliverable observations, single-shot
judge — same harness family as vv.py that produced the 0.852 baseline). Only the
judge `instructions=` differ between arms; observations are gathered once per unit
and shared. Measures owner-gold MAE/bias + regression. NOT committed.

Run: .venv/bin/python tasks/0612_friday/ab_grade.py
"""
import base64, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path("/Users/hsjeon/git/gdpval-realworks")
BR = ROOT / "batch-runner"
DELI = BR / "workspace" / "upload" / "deliverable_files"
GOLD = ROOT / "docs" / "human-in-the-loop" / "overall-style-gold.json"
GRADE54 = ROOT / "data" / "grades" / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json"
PROMPT = BR / "prompts" / "grader_judge_v2.md"
CRIT = "Overall formatting and style of the deliverable"
MAXSCORE = 5.0
MODEL = "gpt-5.4"
sys.path.insert(0, str(BR))


def prep_env():
    if not os.environ.get("AZURE_OPENAI_ENDPOINT") and (BR / ".env").exists():
        for line in (BR / ".env").read_text().splitlines():
            line = line.strip()
            if line.startswith("AZURE_OPENAI_ENDPOINT="):
                v = line.split("=", 1)[1]
                i = v.find(" #")
                if i != -1:
                    v = v[:i]
                os.environ["AZURE_OPENAI_ENDPOINT"] = v.strip().strip('"')
    for k in ("AZURE_OPENAI_API_KEY", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID"):
        os.environ.pop(k, None)


def build_client():
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI
    cred = DefaultAzureCredential()
    tp = get_bearer_token_provider(cred, "https://cognitiveservices.azure.com/.default")
    _ = tp()
    return AzureOpenAI(azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                       api_version="2025-04-01-preview", azure_ad_token_provider=tp, timeout=600)


def instructions_from(text):
    return text.split("<!-- ===SPLIT=== -->")[0].strip()


def resolve_file(task_id, path_or_name):
    base = DELI / task_id
    if not path_or_name:
        return None
    bn = Path(path_or_name).name
    direct = base / bn
    if direct.exists():
        return direct
    if base.exists():
        for p in base.rglob("*"):
            if p.is_file() and p.name == bn:
                return p
    return None


def gather_meta(abspath):
    from core.tools import read_deliverable
    src = Path(abspath)
    base, rel = src.parent, src.name
    out = {}
    for op in ("inspect_structure", "inspect_formatting"):
        r = read_deliverable(op, rel, base_dir=str(base))
        out[op] = r.get("data") if r.get("ok") else {"error": r.get("error")}
    rc = read_deliverable("read_content", rel, base_dir=str(base))
    out["read_content_excerpt"] = rc["data"].get("text", "")[:4000] if rc.get("ok") else ""
    return out


def make_input_text(filename, meta):
    obs = json.dumps(meta, ensure_ascii=False, indent=1)[:9000]
    return "\n\n".join([
        "## Routing hint\n- modality: formatting",
        "## Rubric item to grade",
        f"- max_score: {int(MAXSCORE)}\n- required: null\n- criterion:\n  {CRIT}",
        "## Selected candidate deliverable file",
        f"- path: `{filename}`",
        "## Pre-gathered read_deliverable observations",
        "The harness already called read_deliverable for you. Treat the JSON below "
        "as authoritative tool results; you do NOT need to (and cannot) call tools. "
        "Your `evidence` MUST quote something visible here.",
        "```json\n" + obs + "\n```",
        "## No image\nJudge from the observations above only.",
        "Return ONLY the JSON envelope now (no prose, no code fence).",
    ])


def parse_env(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[4:].strip() if t[:4].lower() == "json" else t.strip()
    try:
        p = json.loads(t)
    except Exception:
        i, j = t.find("{"), t.rfind("}")
        if i == -1 or j == -1:
            return {"_error": "no_json", "verdict": "fail", "partial": 0.0}
        try:
            p = json.loads(t[i:j + 1])
        except Exception:
            return {"_error": "json_parse", "verdict": "fail", "partial": 0.0}
    v = str(p.get("verdict", "fail")).lower()
    if v not in {"pass", "partial", "fail"}:
        v = "fail"
    ps = max(0.0, min(1.0, float(p.get("partial_score", 0.0) or 0.0)))
    if v == "pass":
        ps = 1.0
    elif v == "fail":
        ps = 0.0
    elif ps <= 0 or ps >= 1:
        v, ps = "fail", 0.0
    return {"verdict": v, "partial": ps}


def judge(client, instructions, text):
    last = None
    for attempt in range(4):
        try:
            r = client.responses.create(
                model=MODEL, instructions=instructions,
                input=[{"role": "user", "content": [{"type": "input_text", "text": text}]}],
                reasoning={"effort": "medium"}, max_output_tokens=2400)
            return parse_env(getattr(r, "output_text", "") or "")
        except Exception as e:
            last = e
            if any(k in str(e).lower() for k in ("429", "rate", "timeout")):
                time.sleep(3 * (attempt + 1)); continue
            raise
    raise last


def aggregate(units):
    if not units:
        return 0.0
    partials = [u["partial"] for u in units]
    p = min(partials) if any(u["verdict"] == "fail" for u in units) else sum(partials) / len(partials)
    return MAXSCORE * p


def overall_item(task):
    for x in (task.get("items") or []):
        if x.get("criterion") == CRIT:
            return x
    return None


def main():
    prep_env()
    client = build_client()
    promptA = instructions_from(subprocess.run(
        ["git", "-C", str(ROOT), "show", "HEAD:batch-runner/prompts/grader_judge_v2.md"],
        capture_output=True, text=True).stdout)          # original (committed)
    promptB = instructions_from(PROMPT.read_text())        # tuned (working tree, 1b)
    assert "No hallucination" in promptA and "Judge within what you observed" in promptB

    gold = json.load(open(GOLD))["items"]
    g54 = {t["task_id"]: t for t in json.load(open(GRADE54))["tasks"]}

    rows = []
    calls = 0
    for g in gold:
        tid = g["task_id"]; owner = float(g["owner_score"]); kind = g["kind"]
        item = overall_item(g54.get(tid, {}))
        unit_files = []
        if item and item.get("target_scope") == "split_children" and item.get("child_grades"):
            for c in item["child_grades"]:
                sp = c.get("selected_paths") or []
                unit_files.append(sp[0] if sp else None)
        else:
            sp = (item or {}).get("selected_paths") or []
            unit_files.append(sp[0] if sp else g.get("deliverable_path"))
        units_meta = []
        for uf in unit_files:
            ap = resolve_file(tid, uf)
            units_meta.append((ap.name, gather_meta(str(ap))) if ap else (uf, None))

        def grade_arm(instr):
            nonlocal calls
            us = []
            for name, meta in units_meta:
                if meta is None:
                    us.append({"verdict": "fail", "partial": 0.0}); continue
                res = judge(client, instr, make_input_text(name, meta)); calls += 1
                us.append(res)
            return aggregate(us)

        awA = grade_arm(promptA)
        awB = grade_arm(promptB)
        rows.append({"id": tid[:8], "kind": kind, "owner": owner,
                     "A": round(awA, 2), "B": round(awB, 2),
                     "dA": round(awA - owner, 2), "dB": round(awB - owner, 2)})
        print(f"  {tid[:8]} {kind:5} owner={owner:.1f} A={awA:.2f}(d{awA-owner:+.2f}) B={awB:.2f}(d{awB-owner:+.2f})", flush=True)

    import statistics as st
    def mae(k): return round(st.mean(abs(r[k]) for r in rows), 3)
    def bias(k): return round(st.mean(r[k] for r in rows), 3)
    out = {"n": len(rows), "calls": calls,
           "A": {"MAE": mae("dA"), "bias": bias("dA")},
           "B": {"MAE": mae("dB"), "bias": bias("dB")},
           "by_kind": {}, "rows": rows}
    for kd in ("pdf", "xlsx", "docx", "pptx"):
        kr = [r for r in rows if r["kind"] == kd]
        if kr:
            out["by_kind"][kd] = {"n": len(kr),
                                  "A_MAE": round(st.mean(abs(r["dA"]) for r in kr), 3),
                                  "B_MAE": round(st.mean(abs(r["dB"]) for r in kr), 3),
                                  "A_bias": round(st.mean(r["dA"] for r in kr), 3),
                                  "B_bias": round(st.mean(r["dB"] for r in kr), 3)}
    out["improved"] = [r["id"] for r in rows if abs(r["dB"]) < abs(r["dA"]) - 1e-9]
    out["worsened"] = [r["id"] for r in rows if abs(r["dB"]) > abs(r["dA"]) + 1e-9]
    out["unchanged"] = [r["id"] for r in rows if abs(abs(r["dB"]) - abs(r["dA"])) <= 1e-9]
    json.dump(out, open(ROOT / "tasks/0612_friday/ab_result.json", "w"), ensure_ascii=False, indent=2)
    print("\n=== SUMMARY ===")
    print(f"calls={calls}  n={out['n']}")
    print(f"A (current): MAE={out['A']['MAE']}  bias={out['A']['bias']}")
    print(f"B (tuned)  : MAE={out['B']['MAE']}  bias={out['B']['bias']}")
    print("by_kind:", json.dumps(out["by_kind"], ensure_ascii=False))
    print(f"improved={out['improved']}\nworsened={out['worsened']}\nunchanged={out['unchanged']}")


if __name__ == "__main__":
    main()
