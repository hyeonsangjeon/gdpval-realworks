"""Build approved input identities on the exact compute-runner filesystem."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from core.agentic_compute import (
    MAX_DEPTH,
    MAX_INPUT_FILES,
    MAX_INPUT_SINGLE,
    MAX_INPUT_TOTAL,
    MAX_PATH_BYTES,
    _open_regular_nofollow,
    _sha256_descriptor,
    _source_identity,
)


def build_input_manifest(
    *,
    selection_manifest: Mapping[str, Any],
    dataset_root: str | Path,
    staging_parent: str | Path,
    provider_classification: str,
) -> dict:
    root = Path(dataset_root).resolve()
    staging_parent = Path(staging_parent).resolve()
    if not root.is_dir() or not staging_parent.is_dir():
        raise ValueError("dataset root and staging parent must exist")
    if not provider_classification:
        raise ValueError("provider classification is required")
    selected = selection_manifest.get("selected_tasks")
    if not isinstance(selected, list) or len(selected) != 25:
        raise ValueError("selection manifest must contain exactly 25 tasks")

    tasks = {}
    with tempfile.TemporaryDirectory(
        prefix="agentic-input-manifest-", dir=staging_parent
    ) as temporary:
        temporary_root = Path(temporary)
        for task in selected:
            if not isinstance(task, Mapping):
                raise ValueError("selected task record is invalid")
            task_id = task.get("task_id")
            paths = task.get("reference_paths")
            sizes = task.get("reference_sizes")
            if (
                not isinstance(task_id, str)
                or task_id in tasks
                or not isinstance(paths, list)
                or not isinstance(sizes, list)
                or len(paths) != len(sizes)
            ):
                raise ValueError("selected task input metadata is invalid")
            if len(paths) > MAX_INPUT_FILES:
                raise ValueError("selected task exceeds input file count")
            task_staging = temporary_root / task_id
            task_staging.mkdir(mode=0o700)
            file_records: list[dict[str, Any]] = []
            merkle_records: list[dict[str, Any]] = []
            total = 0
            for relative_value, expected_size in zip(paths, sizes):
                relative = Path(relative_value)
                if (
                    relative.is_absolute()
                    or not relative.parts
                    or ".." in relative.parts
                    or any(part.startswith(".") for part in relative.parts)
                    or len(relative.parts) > MAX_DEPTH
                    or len(relative.as_posix().encode("utf-8")) > MAX_PATH_BYTES
                ):
                    raise ValueError("selected reference path is invalid")
                source = root / relative
                destination = task_staging / relative
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest = hashlib.sha256()
                try:
                    descriptor = _open_regular_nofollow(source)
                except OSError as exc:
                    raise ValueError(
                        "selected source path contains a link or invalid component"
                    ) from exc
                try:
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                        raise ValueError(
                            "selected source is not a single-link regular file"
                        )
                    if metadata.st_size != expected_size:
                        raise ValueError(
                            "selected source size differs from selection manifest"
                        )
                    if metadata.st_size > MAX_INPUT_SINGLE:
                        raise ValueError("selected source exceeds single-file limit")
                    total += metadata.st_size
                    if total > MAX_INPUT_TOTAL:
                        raise ValueError("selected sources exceed total input limit")
                    with os.fdopen(os.dup(descriptor), "rb") as input_stream, destination.open("xb") as output:
                        for chunk in iter(lambda: input_stream.read(65536), b""):
                            digest.update(chunk)
                            output.write(chunk)
                    after = os.fstat(descriptor)
                    source_hash = _sha256_descriptor(descriptor)
                    if _source_identity(after) != _source_identity(metadata):
                        raise ValueError("selected source changed during staging")
                    if source_hash != digest.hexdigest():
                        raise ValueError("selected source changed during staging")
                finally:
                    os.close(descriptor)
                staged = destination.lstat()
                staged_hash = _sha256_file(destination)
                if staged_hash != digest.hexdigest():
                    raise ValueError("staged input hash mismatch")
                relative_path = relative.as_posix()
                approved: dict[str, Any] = {
                    "path": relative_path,
                    "type": "regular",
                    "link_count": 1,
                    "size_bytes": metadata.st_size,
                    "source_allocated_bytes": metadata.st_blocks * 512,
                    "staged_allocated_bytes": staged.st_blocks * 512,
                    "sha256": staged_hash,
                    "provider_classification": provider_classification,
                }
                merkle_records.append({
                    **approved,
                    "model_path": f"inputs/{relative_path}",
                })
                file_records.append({
                    "reference_id": relative_path,
                    "source_path": relative_path,
                    "relative_path": relative_path,
                    **approved,
                })
            merkle_records.sort(
                key=lambda item: str(item["path"]).encode("utf-8")
            )
            input_root = hashlib.sha256(
                json.dumps(
                    merkle_records,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            ).hexdigest()
            tasks[task_id] = {
                "reference_ids": list(paths),
                "files": file_records,
                "input_merkle_root": input_root,
            }
    manifest = {
        "schema_version": "agentic-input-manifest-v1",
        "provider_classification": provider_classification,
        "staging_filesystem_device": staging_parent.stat().st_dev,
        "tasks": tasks,
    }
    manifest["sha256"] = hashlib.sha256(
        json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    return manifest


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()