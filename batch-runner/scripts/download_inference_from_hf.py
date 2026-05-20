#!/usr/bin/env python3
"""Download inference outputs from HF submission dataset.

Downloads:
- step2_inference_results.json
- deliverable_files/**

Usage:
  python scripts/download_inference_from_hf.py --experiment exp998_smoke_baseline_sample --output workspace/step2_inference_results.json
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

import yaml
from huggingface_hub import hf_hub_download, snapshot_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download step2 inference outputs from HF")
    parser.add_argument("--experiment", required=True, help="Experiment yaml name without .yaml")
    parser.add_argument("--output", required=True, help="Local output path for step2_inference_results.json")
    return parser.parse_args()


def resolve_repo_id(experiment: str) -> str:
    exp_path = Path("experiments") / f"{experiment}.yaml"
    data = yaml.safe_load(exp_path.read_text(encoding="utf-8"))
    source = str((data or {}).get("data", {}).get("source", "")).strip()
    if not source:
        raise ValueError("data.source is missing in experiment yaml")
    if "/" not in source:
        raise ValueError("data.source must be owner/name")
    return source


def main() -> int:
    args = parse_args()
    repo_id = resolve_repo_id(args.experiment)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    step2_file = hf_hub_download(
        repo_id=repo_id,
        repo_type="dataset",
        filename="step2_inference_results.json",
    )
    shutil.copy(step2_file, out)

    with tempfile.TemporaryDirectory() as tmp:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=tmp,
            allow_patterns=["deliverable_files/**"],
        )
        src = Path(tmp) / "deliverable_files"
        dst = Path("workspace") / "upload" / "deliverable_files"
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, dirs_exist_ok=True)

    print(f"Downloaded inference from {repo_id} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
