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

    if flt.task_ids is not None:
        if not isinstance(flt.task_ids, list) or not flt.task_ids or not all(
            isinstance(task_id, str) and task_id.strip() for task_id in flt.task_ids
        ):
            raise ValueError(
                "data.filter.task_ids must be a non-empty list of non-empty strings"
            )
        if len(flt.task_ids) != len(set(flt.task_ids)):
            raise ValueError("data.filter.task_ids must not contain duplicates")
        if flt.sample_size is not None:
            raise ValueError("data.filter.task_ids and sample_size are mutually exclusive")

        task_by_id = {task.task_id: task for task in tasks}
        missing_ids = [task_id for task_id in flt.task_ids if task_id not in task_by_id]
        if missing_ids:
            preview = ", ".join(missing_ids[:5])
            suffix = "..." if len(missing_ids) > 5 else ""
            raise ValueError(f"data.filter.task_ids contains unknown task IDs: {preview}{suffix}")
        tasks = [task_by_id[task_id] for task_id in flt.task_ids]
        print(f"🎯 Selected {len(tasks)} explicit task IDs")

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
            "reference_file_urls": t.reference_file_urls,
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
                "reasoning_effort": cond.model.reasoning_effort,
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
        if cond.preprocessors:
            d["preprocessors"] = cond.preprocessors
        return d

    output = {
        "experiment_id": config.experiment_id,
        "experiment_name": config.name,
        "description": config.description,
        "config_path": str(config_path),
        "source": config.data_filter.source,
        "task_scope": {
            "mode": (
                "explicit_ids" if config.data_filter.task_ids is not None
                else "filtered" if any((
                    config.data_filter.sector,
                    config.data_filter.occupation,
                    config.data_filter.sample_size is not None,
                ))
                else "full"
            ),
            "expected_count": len(task_list),
            "task_ids": [task["task_id"] for task in task_list],
        },
        "execution": {
            "mode": config.execution.mode,
            "max_retries": config.execution.max_retries,
            "resume_max_rounds": config.execution.resume_max_rounds,
            "tokens": dict(config.execution.tokens),
            "timeout": config.execution.timeout,
            "sandbox": config.execution.sandbox,
            **({"metrics": config.execution.metrics} if config.execution.metrics is not None else {}),
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
