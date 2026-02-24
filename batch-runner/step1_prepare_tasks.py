#!/usr/bin/env python3
"""Step 1: Prepare Tasks — Load dataset, apply filters, save task list to workspace.

Input:
  - data/gdpval-local/  (local HF snapshot, from Step 0)
  - experiments/*.yaml   (experiment config)
  - workspace/step0_needs_files_manifest.json (from Step 0)

Output:
  - workspace/step1_tasks_prepared.json

Usage:
    python step1_prepare_tasks.py --config experiments/exp001_smoke_baseline.yaml
"""

import argparse
import json
import random
import sys
from pathlib import Path

from core.config import WORKSPACE_DIR
from core.data_loader import GDPValDataLoader
from core.experiment_config import ExperimentConfig
from core.needs_files import NeedsFilesManifest


def prepare_tasks(config_path: str) -> dict:
    """Load data, apply filters, enrich with needs_files, save to workspace."""

    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load experiment config
    config = ExperimentConfig.from_yaml(config_path)
    print(f"📋 Experiment: {config.experiment_id} — {config.name}")
    print(f"   Description: {config.description}")

    # 2. Load dataset (auto_download=False: Step 0에서 이미 다운로드 완료)
    loader = GDPValDataLoader(auto_download=False)
    tasks = loader.load()
    print(f"📦 Loaded {len(tasks)} tasks from local snapshot")

    # 3. Apply filters
    flt = config.data_filter
    if flt.sector:
        tasks = [t for t in tasks if t.sector.lower() == flt.sector.lower()]
        print(f"🔍 Filtered by sector '{flt.sector}': {len(tasks)} tasks")

    if flt.occupation:
        tasks = [t for t in tasks if t.occupation.lower() == flt.occupation.lower()]
        print(f"🔍 Filtered by occupation '{flt.occupation}': {len(tasks)} tasks")

    if flt.sample_size and flt.sample_size < len(tasks):
        random.seed(42)
        tasks = random.sample(tasks, flt.sample_size)
        print(f"🎲 Sampled {flt.sample_size} tasks")

    # 4. Load needs_files manifest
    manifest = None
    try:
        manifest = NeedsFilesManifest.load()
        print(f"📋 Manifest loaded: {manifest}")
    except FileNotFoundError:
        print("⚠️  step0_needs_files_manifest.json not found — skipping file checks")

    # 5. Build task list with metadata
    task_list = []
    for t in tasks:
        entry = {
            "task_id": t.task_id,
            "sector": t.sector,
            "occupation": t.occupation,
            "instruction": t.prompt,
            "reference_files": t.reference_files,
            "needs_files": manifest.needs_files(t.task_id) if manifest else False,
        }
        task_list.append(entry)

    # 6. Build condition dicts
    def _condition_dict(cond):
        d = {
            "name": cond.name,
            "model": {
                "provider": cond.model.provider,
                "deployment": cond.model.deployment,
                "temperature": cond.model.temperature,
                "seed": cond.model.seed,
            },
            "prompt": {
                "system": cond.prompt.system,
                "prefix": cond.prompt.prefix,
                "body": cond.prompt.body if hasattr(cond.prompt, 'body') else None,
                "suffix": cond.prompt.suffix,
            },
        }
        if cond.qa and cond.qa.enabled:
            d["qa"] = {
                "enabled": cond.qa.enabled,
                "max_retries": cond.qa.max_retries,
                "model": cond.qa.model,
                "min_score": cond.qa.min_score,
                "prompt": cond.qa.prompt,
            }
        return d

    output = {
        "experiment_id": config.experiment_id,
        "experiment_name": config.name,
        "description": config.description,
        "config_path": str(config_path),
        "source": config.data_filter.source,
        "execution": {
            "mode": config.execution.mode,
            "max_retries": config.execution.max_retries,
            "resume_max_rounds": config.execution.resume_max_rounds,
        },
        "total_tasks": len(task_list),
        "needs_files_count": sum(1 for t in task_list if t["needs_files"]),
        "text_only_count": sum(1 for t in task_list if not t["needs_files"]),
        "condition_a": _condition_dict(config.condition_a),
        "condition_b": _condition_dict(config.condition_b) if config.condition_b else None,
        "tasks": task_list,
    }

    # 7. Save
    output_path = WORKSPACE_DIR / "step1_tasks_prepared.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Step 1 complete: {len(task_list)} tasks → {output_path}")
    print(f"   needs_files: {output['needs_files_count']} | text_only: {output['text_only_count']}")
    return output


def main():
    parser = argparse.ArgumentParser(description="Step 1: Prepare tasks")
    parser.add_argument("--config", required=True, help="Path to experiment YAML config")
    args = parser.parse_args()

    prepare_tasks(args.config)


if __name__ == "__main__":
    main()
