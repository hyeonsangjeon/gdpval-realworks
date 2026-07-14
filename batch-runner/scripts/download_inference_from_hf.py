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
import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import yaml
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from huggingface_hub.errors import EntryNotFoundError

from core.inference_manifest import (
    canonicalize_inference_payload,
    validate_local_deliverables,
)


FULL_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")


def _hf_token() -> str | None:
    """Resolve the HF auth token from the standard env vars.

    The workflow injects ``HF_TOKEN`` for the download step, but the
    huggingface_hub auto-pickup does not always fire, so we pass it
    explicitly. Without it the requests go out anonymous (low rate
    limit) and the sequential relay trips HTTP 429 on repeated chunks.
    """
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download step2 inference outputs from HF")
    parser.add_argument("--experiment", required=True, help="Experiment yaml name without .yaml")
    parser.add_argument("--output", required=True, help="Local output path for step2_inference_results.json")
    parser.add_argument(
        "--revision",
        default="",
        help="HF dataset revision; blank resolves main once, full commit SHAs are used directly",
    )
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


def resolve_immutable_revision(repo_id: str, revision: str = "") -> str:
    requested = revision
    if FULL_SHA_RE.fullmatch(requested):
        return requested.lower()

    resolved = HfApi().dataset_info(repo_id, revision=requested or "main").sha
    if not isinstance(resolved, str) or not FULL_SHA_RE.fullmatch(resolved):
        raise ValueError(f"HF dataset revision did not resolve to a full commit SHA: {repo_id}")
    return resolved.lower()


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


def _canonicalize_inference_payload(payload: object, repo_id: str, revision: str) -> dict:
    normalized = canonicalize_inference_payload(payload)
    normalized["source_repo_id"] = repo_id
    normalized["source_revision"] = revision
    normalized.setdefault("source", repo_id)
    return normalized


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _download_or_reconstruct_inference(
    experiment: str,
    repo_id: str,
    revision: str,
    out: Path,
) -> None:
    token = _hf_token()
    try:
        step2_file = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename="step2_inference_results.json",
            revision=revision,
            token=token,
        )
        payload = json.loads(Path(step2_file).read_text(encoding="utf-8"))
    except (EntryNotFoundError, FileNotFoundError):
        parquet_file = hf_hub_download(
            repo_id=repo_id,
            repo_type="dataset",
            filename="data/train-00000-of-00001.parquet",
            revision=revision,
            token=token,
        )
        payload = _build_inference_from_parquet(parquet_file, experiment, repo_id)

    canonical = _canonicalize_inference_payload(payload, repo_id, revision)
    _atomic_write_json(out, canonical)


def _remove_owned_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _download_and_replace_deliverables(
    repo_id: str, revision: str, results: list[dict]
) -> None:
    destination = Path("workspace") / "upload" / "deliverable_files"
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.staging-", dir=destination.parent)
    )
    backup = destination.with_name(f".{destination.name}.backup-{uuid.uuid4().hex}")
    backup_created = False

    try:
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            local_dir=staging_root,
            allow_patterns=["deliverable_files/**"],
            revision=revision,
            token=_hf_token(),
        )
        staged_deliverables = staging_root / "deliverable_files"
        staged_deliverables.mkdir(parents=True, exist_ok=True)
        validate_local_deliverables(results, staging_root)

        if destination.exists() or destination.is_symlink():
            os.replace(destination, backup)
            backup_created = True
        try:
            os.replace(staged_deliverables, destination)
        except BaseException:
            if backup_created:
                _remove_owned_path(destination)
                os.replace(backup, destination)
                backup_created = False
            raise

        if backup_created:
            _remove_owned_path(backup)
            backup_created = False
    finally:
        _remove_owned_path(staging_root)


def main() -> int:
    args = parse_args()
    repo_id = resolve_repo_id(args.experiment)
    revision = resolve_immutable_revision(repo_id, args.revision)
    print(f"Resolved inference revision: {revision}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    _download_or_reconstruct_inference(args.experiment, repo_id, revision, out)
    payload = json.loads(out.read_text(encoding="utf-8"))
    canonical = _canonicalize_inference_payload(payload, repo_id, revision)
    _download_and_replace_deliverables(repo_id, revision, canonical["results"])

    print(f"Downloaded inference from {repo_id} at {revision}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
