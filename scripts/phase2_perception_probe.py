#!/usr/bin/env python3
"""PHASE 2 — LIVE perception-firing probe (real Azure, low cost).

Why a synthetic probe and not the exp003 re-smoke: the exp003 modality
deliverable BINARIES that the existing perception-off v2-mini grades ran
on are not staged locally (only the exp997 2-task smoke is), and cannot be
faithfully reconstructed (inference is non-deterministic). So we cannot
re-grade the SAME exp003 files perception-on locally. This probe instead
PROVES the wired path fires end-to-end against real Azure:

  visual criterion -> routing=VISUAL -> render_to_image -> vision_judge
  (gpt-5.4 vision) -> verdict, with the PHASE-1 instrumentation recording
  perception_called=True and tools_used containing 'vision_judge'.

Acceptance (spec PHASE 2): perception call > 0 AND judge_error < 2%.

Run:  GRADER_ALLOW_API_KEY_FALLBACK=1 python scripts/phase2_perception_probe.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BR = ROOT / "batch-runner"
sys.path.insert(0, str(BR))
os.chdir(BR)

# Load .env (AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY) for local run.
# Strip inline `# comment` suffixes — .env in this repo has Korean comments
# trailing the values; otherwise the secret becomes non-ASCII and Azure's
# HTTP layer ASCII-encodes the api-key header and raises UnicodeEncodeError.
for line in (BR / ".env").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    # cut at first ' #' (space-hash) so values can still contain '#'
    i = v.find(" #")
    if i != -1:
        v = v[:i]
    os.environ.setdefault(k.strip(), v.strip())
os.environ["GRADER_ALLOW_API_KEY_FALLBACK"] = "1"

import yaml  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from core.grader import Grader  # noqa: E402
from core.rubric_loader import RubricItem, TaskRubric  # noqa: E402


def make_chart_png(path: Path, *, with_title: bool) -> None:
    """Draw a simple bar chart. with_title=False omits the title (a
    defect a vision judge should catch)."""
    img = Image.new("RGB", (640, 420), "white")
    d = ImageDraw.Draw(img)
    bars = [120, 200, 90, 260, 170]
    x = 60
    for h in bars:
        d.rectangle([x, 360 - h, x + 70, 360], fill=(70, 110, 200))
        x += 100
    d.line([50, 360, 600, 360], fill="black", width=2)   # x axis
    d.line([50, 40, 50, 360], fill="black", width=2)     # y axis
    if with_title:
        d.text((220, 12), "Quarterly Revenue by Region", fill="black")
    d.text((55, 365), "Q1   Q2   Q3   Q4   Q5", fill="black")
    img.save(path, format="PNG")


def main() -> int:
    cfg = yaml.safe_load(open("grading_configs/default_v2_mini.yaml"))

    grader = Grader(cfg, rubric_loader=None)
    tj = grader._tool_judge
    print(f"tool_judge active: {tj is not None}")
    print(f"vision_perception wired: {tj.vision_perception is not None}")
    print(f"audio_perception wired:  {tj.audio_perception is not None}")
    print(f"judge model: {grader.model} | vision model: "
          f"{tj.vision_perception.deployment if tj.vision_perception else None}")

    tmp = Path(tempfile.mkdtemp(prefix="phase2_probe_"))
    chart = tmp / "revenue_chart.png"
    make_chart_png(chart, with_title=True)
    print(f"deliverable: {chart} ({chart.stat().st_size} bytes)")

    visual_item = RubricItem(
        rubric_item_id="vis-1",
        criterion=("The chart image has a clear descriptive title and the "
                   "axes are visible. Judge the visual appearance of the "
                   "rendered chart."),
        score=5, required=None,
    )
    text_item = RubricItem(
        rubric_item_id="txt-1",
        criterion="The deliverable contains five quarterly bars of data.",
        score=3, required=None,
    )
    task = TaskRubric(
        task_id="probe-task", sector="Finance", occupation="Analyst",
        prompt="Produce a quarterly revenue chart.",
        rubric_items=[visual_item, text_item],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )

    grade = grader.grade_task(task, str(tmp))

    print("\n=== per-item instrumentation ===")
    out = []
    for ig in grade.items:
        row = {
            "rid": ig.rubric_item_id,
            "verdict": ig.verdict,
            "decided_by": ig.decided_by,
            "routing_modality": getattr(ig, "routing_modality", None),
            "perception_called": getattr(ig, "perception_called", None),
            "tools_used": getattr(ig, "tools_used", None),
            "evidence": (ig.evidence or "")[:120],
        }
        out.append(row)
        print(json.dumps(row, ensure_ascii=False))

    n_judge = sum(1 for ig in grade.items if ig.decided_by == "judge")
    n_err = sum(1 for ig in grade.items if ig.verdict == "judge_error")
    n_perc = sum(1 for ig in grade.items
                 if getattr(ig, "perception_called", False))
    print("\n=== PHASE 2 acceptance ===")
    print(f"judged items: {n_judge}")
    print(f"perception calls (>0 required): {n_perc}")
    print(f"judge_error items: {n_err} "
          f"(rate {n_err / max(1, n_judge):.1%}, <2% required)")
    ok = n_perc > 0 and (n_err / max(1, n_judge)) < 0.02
    print(f"ACCEPTANCE: {'PASS' if ok else 'FAIL'}")

    json.dump(out, open(ROOT / "tasks/0531_sunday/phase2_probe_raw.json", "w"),
              ensure_ascii=False, indent=2)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
