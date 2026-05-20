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
import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import yaml
from huggingface_hub import hf_hub_download, snapshot_download
from huggingface_hub.errors import EntryNotFoundError


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


def _coerce_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    if hasattr(value, "tolist"):
        return [str(item) for item in value.tolist() if item is not None]
    try:
        if pd.isna(value):
            return []
    except Exception:
        pass
    return [str(value)] if value else []


def _build_inference_from_parquet(parquet_path: str, experiment: str, repo_id: str) -> dict:
    df = pd.read_parquet(parquet_path)
    results = []
    for row in df.to_dict("records"):
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        deliverable_files = _coerce_list(row.get("deliverable_files"))
        deliverable_text = str(row.get("deliverable_text") or "")
        results.append(
            {
                "task_id": task_id,
                "status": "success" if deliverable_files or deliverable_text else "error",
                "deliverable_text": deliverable_text,
                "deliverable_files": deliverable_files,
            }
        )

    return {
        "experiment_id": experiment,
        "source": repo_id,
        "model": "",
        "completed_at": None,
        "results": results,
    }


def _download_or_reconstruct_inference(experiment: str, repo_id: str, out: Path) -> None:
    try:
        step2_file = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename="step2_inference_results.json",
        )
        shutil.copy(step2_file, out)
        return
    except (EntryNotFoundError, FileNotFoundError):
        parquet_file = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename="data/train-00000-of-00001.parquet",
        )
        reconstructed = _build_inference_from_parquet(parquet_file, experiment, repo_id)
        out.write_text(json.dumps(reconstructed, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_id = resolve_repo_id(args.experiment)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    _download_or_reconstruct_inference(args.experiment, repo_id, out)

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
