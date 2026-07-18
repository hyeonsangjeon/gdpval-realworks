"""Build approved input identities on the exact compute-runner filesystem."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
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
    _open_regular_beneath_nofollow,
    _sha256_descriptor,
    _source_identity,
)


SELECTION_FIELDS = {
    "schema_version", "seed", "eligible_frame_count", "strata",
    "canary_task_ids", "diagnostic_task_ids", "selected_tasks",
    "selection_domains", "tie_break", "selected_before_outcomes",
    "dataset", "rubric", "selector", "inclusion_validation",
    "exclusion_validation", "recomputation_sha256",
}
SELECTION_DOMAINS = {
    "select": "agentic-select-v1",
    "canary": "agentic-canary-v1",
    "order_canary": "agentic-order-canary-v1",
    "order_diagnostic": "agentic-order-diagnostic-v1",
}
FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}/"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"
)


def build_input_manifest(
    *,
    selection_manifest: Mapping[str, Any],
    dataset_root: str | Path,
    staging_parent: str | Path,
    provider_classification: str,
) -> dict:
    selection = validate_selection_manifest(selection_manifest)
    raw_root = Path(dataset_root)
    if raw_root.is_symlink():
        raise ValueError("dataset root must not be a symlink")
    root = raw_root.resolve()
    staging_parent = Path(staging_parent).resolve()
    if not root.is_dir() or not staging_parent.is_dir():
        raise ValueError("dataset root and staging parent must exist")
    if not provider_classification:
        raise ValueError("provider classification is required")
    selected = selection["selected_tasks"]

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
            if (
                task_id in {".", ".."}
                or task_id.startswith(".")
                or "/" in task_id
                or "\\" in task_id
                or len(task_id.encode("utf-8")) > MAX_PATH_BYTES
                or any(ord(character) < 32 for character in task_id)
            ):
                raise ValueError("selected task ID is not a canonical component")
            if len(paths) > MAX_INPUT_FILES:
                raise ValueError("selected task exceeds input file count")
            task_staging = temporary_root / hashlib.sha256(
                task_id.encode("utf-8")
            ).hexdigest()
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
                destination = task_staging / relative
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest = hashlib.sha256()
                try:
                    descriptor = _open_regular_beneath_nofollow(
                        root, relative
                    )
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
        "selection_recomputation_sha256": selection[
            "recomputation_sha256"
        ],
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


def validate_selection_manifest(
    selection_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(selection_manifest, Mapping):
        raise ValueError("selection manifest must be an object")
    document = dict(selection_manifest)
    if set(document) != SELECTION_FIELDS:
        raise ValueError("selection manifest fields are invalid")
    if (
        document["schema_version"] != "agentic-task-subset-v1"
        or document["seed"] != "20260717"
        or document["selection_domains"] != SELECTION_DOMAINS
        or document["tie_break"] != "ascending UTF-8 bytes"
        or document["selected_before_outcomes"] is not True
        or document["inclusion_validation"]
        != "all structural checks passed"
        or document["exclusion_validation"]
        != "outcome fields were not accepted by selector"
    ):
        raise ValueError("selection manifest frozen identity is invalid")
    expected_hash = document["recomputation_sha256"]
    if (
        not isinstance(expected_hash, str)
        or SHA256_RE.fullmatch(expected_hash) is None
    ):
        raise ValueError("selection recomputation hash is invalid")
    canonical = {
        key: value
        for key, value in document.items()
        if key != "recomputation_sha256"
    }
    actual_hash = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("selection recomputation hash mismatch")

    canary_ids = _task_id_list(document["canary_task_ids"], 5)
    diagnostic_ids = _task_id_list(document["diagnostic_task_ids"], 20)
    ordered_ids = canary_ids + diagnostic_ids
    if len(set(ordered_ids)) != 25:
        raise ValueError("selection cohorts overlap or contain duplicates")
    selected = document["selected_tasks"]
    if not isinstance(selected, list) or len(selected) != 25:
        raise ValueError("selection manifest must contain exactly 25 tasks")
    selected_ids = [
        _validate_selected_task(task)
        for task in selected
    ]
    if selected_ids != ordered_ids:
        raise ValueError("selection task order differs from 5/20 cohorts")

    eligible_count = document["eligible_frame_count"]
    strata = document["strata"]
    if type(eligible_count) is not int or eligible_count < 25:
        raise ValueError("selection eligible frame count is invalid")
    if not isinstance(strata, list) or not strata:
        raise ValueError("selection strata are invalid")
    seen_strata = set()
    eligible_total = selected_total = canary_total = 0
    for item in strata:
        required = {
            "sector", "input_class", "eligible_count",
            "selected_quota", "canary_quota",
        }
        if not isinstance(item, Mapping) or set(item) != required:
            raise ValueError("selection stratum fields are invalid")
        identity = (item["sector"], item["input_class"])
        if (
            any(not isinstance(value, str) or not value for value in identity)
            or identity in seen_strata
        ):
            raise ValueError("selection stratum identity is invalid")
        seen_strata.add(identity)
        counts = (
            item["eligible_count"], item["selected_quota"],
            item["canary_quota"],
        )
        if (
            any(type(value) is not int or value < 0 for value in counts)
            or counts[0] < counts[1]
            or counts[1] < counts[2]
        ):
            raise ValueError("selection stratum quota is invalid")
        eligible_total += counts[0]
        selected_total += counts[1]
        canary_total += counts[2]
    if (
        eligible_total != eligible_count
        or selected_total != 25
        or canary_total != 5
    ):
        raise ValueError("selection stratum totals are invalid")

    for label in ("dataset", "rubric"):
        provenance = document[label]
        if not isinstance(provenance, Mapping) or set(provenance) != {
            "repository", "revision", "source_path", "sha256"
        }:
            raise ValueError(f"selection {label} provenance is invalid")
        if (
            not isinstance(provenance["repository"], str)
            or REPOSITORY_RE.fullmatch(provenance["repository"]) is None
            or not isinstance(provenance["revision"], str)
            or FULL_COMMIT_RE.fullmatch(provenance["revision"]) is None
            or not _canonical_relative_path(provenance["source_path"])
            or not isinstance(provenance["sha256"], str)
            or SHA256_RE.fullmatch(provenance["sha256"]) is None
        ):
            raise ValueError(f"selection {label} provenance is invalid")
    selector = document["selector"]
    if not isinstance(selector, Mapping) or set(selector) != {
        "path", "source_commit", "sha256"
    }:
        raise ValueError("selection selector provenance is invalid")
    if (
        not _canonical_relative_path(selector["path"])
        or not isinstance(selector["source_commit"], str)
        or FULL_COMMIT_RE.fullmatch(selector["source_commit"]) is None
        or not isinstance(selector["sha256"], str)
        or SHA256_RE.fullmatch(selector["sha256"]) is None
    ):
        raise ValueError("selection selector provenance is invalid")
    return document


def _task_id_list(value: Any, count: int) -> list[str]:
    if (
        not isinstance(value, list)
        or len(value) != count
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise ValueError("selection cohort task IDs are invalid")
    return list(value)


def _validate_selected_task(value: Any) -> str:
    required = {
        "task_id", "sector", "occupation", "input_class",
        "reference_paths", "reference_suffixes", "reference_sizes",
        "positive_rubric_max",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise ValueError("selected task fields are invalid")
    for field in ("task_id", "sector", "occupation", "input_class"):
        if not isinstance(value[field], str) or not value[field]:
            raise ValueError("selected task text identity is invalid")
    paths = value["reference_paths"]
    suffixes = value["reference_suffixes"]
    sizes = value["reference_sizes"]
    if (
        not isinstance(paths, list)
        or not isinstance(suffixes, list)
        or not isinstance(sizes, list)
        or len(paths) != len(suffixes)
        or len(paths) != len(sizes)
        or len(paths) > MAX_INPUT_FILES
    ):
        raise ValueError("selected task reference metadata is invalid")
    total = 0
    for path, suffix, size in zip(paths, suffixes, sizes):
        if (
            not _canonical_relative_path(path)
            or not isinstance(suffix, str)
            or suffix != Path(path).suffix.lower().lstrip(".")
            or type(size) is not int
            or not 0 <= size <= MAX_INPUT_SINGLE
        ):
            raise ValueError("selected task reference identity is invalid")
        total += size
    if total > MAX_INPUT_TOTAL:
        raise ValueError("selected task references exceed input limit")
    maximum = value["positive_rubric_max"]
    if (
        isinstance(maximum, bool)
        or not isinstance(maximum, (int, float))
        or not math.isfinite(float(maximum))
        or maximum <= 0
    ):
        raise ValueError("selected task rubric denominator is invalid")
    return value["task_id"]


def _canonical_relative_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = Path(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and ".." not in path.parts
        and all(part not in {"", "."} and not part.startswith(".") for part in path.parts)
        and len(path.parts) <= MAX_DEPTH
        and len(value.encode("utf-8")) <= MAX_PATH_BYTES
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()