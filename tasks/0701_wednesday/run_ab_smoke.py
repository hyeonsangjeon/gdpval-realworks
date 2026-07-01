#!/usr/bin/env python3
"""Bounded A/B sandbox smoke — prepared-JSON builder (PR #57).

Writes ``workspace/step1_tasks_prepared.json`` for a *pinned* subset of GDPVal
tasks so ``step2_run_inference.py`` runs only those tasks in sandbox mode.

Why a bespoke builder instead of step1_prepare_tasks.py:
  * step1 samples randomly and, more importantly, ``ExperimentConfig`` drops the
    ``execution.sandbox`` block, so the sandbox output-control-loop settings
    (repair / output_qa / manifest / cache) would never reach the runner.
    This builder reads the raw YAML and preserves the full ``execution`` block.

Two variants from one base YAML (the HYBRID/condition-B definition):
  * ``hybrid``      — keep condition_a.preprocessors (audio_analyzer +
                      video_analyzer GPT perception).
  * ``skills_only`` — strip preprocessors entirely (provider-agnostic:
                      main solving model + local skills only).

Both variants disable the legacy LLM self-QA (condition.qa) so the smoke
isolates the NEW output-control loop, and both keep output_qa.vision disabled.

This is a smoke/test harness artifact — it does not modify any core module.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

BATCH_RUNNER = Path(__file__).resolve().parents[2] / "batch-runner"
sys.path.insert(0, str(BATCH_RUNNER))

from core.config import WORKSPACE_DIR  # noqa: E402
from core.data_loader import GDPValDataLoader  # noqa: E402


def _load_tasks_by_id(ids: list[str]) -> dict:
    loader = GDPValDataLoader(auto_download=False)
    by_id = {t.task_id: t for t in loader.load()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"Task ids not found in snapshot: {missing}")
    return {i: by_id[i] for i in ids}


def _strip_qa(cond: dict) -> None:
    """Disable the legacy LLM self-QA so the smoke isolates the new loop."""
    if isinstance(cond.get("qa"), dict):
        cond["qa"]["enabled"] = False


def build_prepared(yaml_path: str, variant: str, ids: list[str]) -> dict:
    raw = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))

    execution = dict(raw.get("execution", {}))
    # Bound the OUTER step2 resume/retry loop; the sandbox runner has its own
    # bounded internal repair loop (execution.sandbox.repair.max_attempts).
    execution["max_retries"] = 1
    execution["resume_max_rounds"] = 1

    cond_a = json.loads(json.dumps(raw["condition_a"]))  # deep copy
    _strip_qa(cond_a)
    if variant == "skills_only":
        cond_a.pop("preprocessors", None)
    elif variant != "hybrid":
        raise SystemExit(f"unknown variant: {variant}")

    tasks = _load_tasks_by_id(ids)
    task_list = []
    for tid, t in tasks.items():
        task_list.append({
            "task_id": t.task_id,
            "sector": t.sector,
            "occupation": t.occupation,
            "instruction": t.prompt,
            "reference_files": list(getattr(t, "reference_files", []) or []),
            "reference_file_urls": list(getattr(t, "reference_file_urls", []) or []),
            # Rely on manifest.final_status for pass/fail; keep step2 from adding
            # outer resume rounds for "no files".
            "needs_files": False,
        })

    return {
        "experiment_id": f"{raw['experiment']['id']}__{variant}",
        "experiment_name": f"{raw['experiment'].get('name','')} [{variant}]",
        "description": f"Bounded A/B sandbox smoke ({variant}) — PR #57",
        "config_path": str(yaml_path),
        "source": raw.get("data", {}).get("source", ""),
        "execution": execution,
        "total_tasks": len(task_list),
        "needs_files_count": 0,
        "text_only_count": len(task_list),
        "condition_a": cond_a,
        "condition_b": None,
        "tasks": task_list,
        "_smoke": {"variant": variant, "task_ids": ids},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build prepared JSON for the A/B sandbox smoke")
    ap.add_argument("--yaml", required=True, help="Base smoke YAML (hybrid/condition-B definition)")
    ap.add_argument("--variant", required=True, choices=["hybrid", "skills_only"])
    ap.add_argument("--task-ids-file", required=True, help="File with one task_id per line")
    args = ap.parse_args()

    ids = []
    for ln in Path(args.task_ids_file).read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        ids.append(ln.split("#", 1)[0].strip())  # drop inline comment
    prepared = build_prepared(args.yaml, args.variant, ids)

    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    out = WORKSPACE_DIR / "step1_tasks_prepared.json"
    out.write_text(json.dumps(prepared, indent=2, ensure_ascii=False), encoding="utf-8")

    pp = "preprocessors" in prepared["condition_a"]
    print(f"✅ wrote {out}")
    print(f"   variant={args.variant}  tasks={len(ids)}  preprocessors={'ON' if pp else 'OFF'}  "
          f"mode={prepared['execution'].get('mode')}  "
          f"sandbox.use_docker={prepared['execution'].get('sandbox',{}).get('use_docker')}")


if __name__ == "__main__":
    main()
