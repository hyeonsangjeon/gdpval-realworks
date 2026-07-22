"""Validation for inference manifests and their local deliverable tree."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote


TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def canonical_task_id(value: Any) -> str:
    if not isinstance(value, str) or not TASK_ID_RE.fullmatch(value):
        raise ValueError(
            "task_id must be 1-128 ASCII letters, digits, dot, underscore, or hyphen"
        )
    if value in {".", ".."}:
        raise ValueError("task_id must not be a dot path segment")
    return value


def canonical_deliverable_path(task_id: str, value: Any) -> str:
    task_id = canonical_task_id(task_id)
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or any(char in value for char in ("\x00", "\r", "\n"))
        or value.startswith("/")
        or WINDOWS_DRIVE_RE.match(value)
    ):
        raise ValueError(f"invalid deliverable path for task {task_id!r}")

    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError(f"deliverable path is not canonical for task {task_id!r}")
    path = PurePosixPath(value)
    if (
        len(path.parts) < 3
        or path.parts[0] != "deliverable_files"
        or path.parts[1] != task_id
        or path.as_posix() != value
    ):
        raise ValueError(
            f"deliverable path must stay under deliverable_files/{task_id}/"
        )
    return value


def canonical_deliverable_uris(
    file_list: list[str],
    submission_repo_id: str,
) -> tuple[list[str], list[str]]:
    base_url = (
        f"https://huggingface.co/datasets/{submission_repo_id}/resolve/main"
    )
    hf_prefix = f"hf://datasets/{submission_repo_id}@main"
    urls = [f"{base_url}/{quote(path, safe='/')}" for path in file_list]
    uris = [f"{hf_prefix}/{quote(path, safe='/')}" for path in file_list]
    return urls, uris


def canonicalize_inference_results(results: Any) -> list[dict]:
    if not isinstance(results, list):
        raise ValueError("inference results must be an array")

    normalized: list[dict] = []
    seen_task_ids: set[str] = set()
    for index, row in enumerate(results):
        if not isinstance(row, dict):
            raise ValueError(f"inference result at index {index} must be an object")
        task_id = canonical_task_id(row.get("task_id"))
        if task_id in seen_task_ids:
            raise ValueError(f"duplicate inference task_id: {task_id}")
        seen_task_ids.add(task_id)

        raw_files = row.get("deliverable_files")
        if raw_files is None:
            raw_files = []
        if not isinstance(raw_files, list):
            raise ValueError(
                f"deliverable_files for task {task_id!r} must be an array"
            )
        files = [canonical_deliverable_path(task_id, path) for path in raw_files]
        if len(files) != len(set(files)):
            raise ValueError(f"duplicate deliverable path for task {task_id!r}")

        normalized_row = dict(row)
        normalized_row["task_id"] = task_id
        normalized_row["deliverable_files"] = files
        normalized.append(normalized_row)
    return normalized


def canonicalize_inference_payload(payload: Any) -> dict:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("inference JSON must be an object with a results array")
    normalized = dict(payload)
    normalized["results"] = canonicalize_inference_results(payload["results"])
    return normalized


def task_deliverable_dir(upload_root: Path, task_id: str) -> Path:
    return upload_root / "deliverable_files" / canonical_task_id(task_id)


def _regular_directory(path: Path, label: str) -> Path:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        path.mkdir(mode=0o700)
        metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} is not a regular directory")
    return path


def _deliverable_root(upload_root: Path) -> Path:
    root = Path(os.path.abspath(upload_root))
    _assert_no_symlink_ancestors(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    _regular_directory(root, "upload root")
    return _regular_directory(root / "deliverable_files", "deliverable root")


def ensure_task_deliverable_dir(upload_root: Path, task_id: str) -> Path:
    """Return one canonical, regular task directory, creating it if absent."""
    deliverable_root = _deliverable_root(upload_root)
    task_root = task_deliverable_dir(deliverable_root.parent, task_id)
    return _regular_directory(task_root, "deliverable task path")


def reset_task_deliverable_dir(upload_root: Path, task_id: str) -> Path:
    """Replace only the canonical task-owned directory with an empty directory."""
    deliverable_root = _deliverable_root(upload_root)
    task_root = task_deliverable_dir(deliverable_root.parent, task_id)
    try:
        metadata = task_root.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("deliverable task path is not a regular directory")
        shutil.rmtree(task_root)
    task_root.mkdir(mode=0o700)
    return _regular_directory(task_root, "deliverable task path")


def _assert_no_symlink_components(path: Path, stop: Path) -> None:
    current = stop
    relative = path.relative_to(stop)
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"deliverable path contains a symlink: {relative}")


def _assert_no_symlink_ancestors(path: Path) -> None:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"deliverable path contains a symlink component: {current}")


def validate_local_deliverables(results: Any, upload_root: Path) -> list[dict]:
    """Validate exact files Grader may recursively inspect for selected tasks."""
    normalized = canonicalize_inference_results(results)
    upload_root = Path(os.path.abspath(upload_root))
    _assert_no_symlink_ancestors(upload_root)

    for row in normalized:
        task_id = row["task_id"]
        expected = set(row["deliverable_files"])
        task_root = task_deliverable_dir(upload_root, task_id)
        _assert_no_symlink_components(task_root, upload_root)

        if not task_root.exists():
            if expected:
                raise ValueError(f"deliverable directory is missing for task {task_id}")
            continue
        if task_root.is_symlink() or not task_root.is_dir():
            raise ValueError(f"deliverable directory is not regular for task {task_id}")

        actual: set[str] = set()
        for directory, dirnames, filenames in os.walk(task_root, followlinks=False):
            directory_path = Path(directory)
            for name in dirnames:
                child = directory_path / name
                if child.is_symlink():
                    raise ValueError(
                        f"deliverable tree contains a symlink for task {task_id}"
                    )
            for name in filenames:
                child = directory_path / name
                if child.is_symlink() or not child.is_file():
                    raise ValueError(
                        f"deliverable tree contains a non-regular file for task {task_id}"
                    )
                resolved = child.resolve()
                try:
                    resolved.relative_to(task_root.resolve())
                except ValueError as exc:
                    raise ValueError(
                        f"deliverable file escapes task directory for task {task_id}"
                    ) from exc
                relative = child.relative_to(upload_root).as_posix()
                canonical_deliverable_path(task_id, relative)
                actual.add(relative)

        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing or extra:
            raise ValueError(
                f"deliverable tree mismatch for task {task_id}: "
                f"missing={missing}, extra={extra}"
            )
    return normalized


def bind_deliverable_file_records(
    results: Any,
    upload_root: Path,
) -> list[dict]:
    """Bind every declared deliverable to bytes in its condition-owned tree."""
    normalized = validate_local_deliverables(results, upload_root)
    root = Path(os.path.abspath(upload_root))
    bound = []
    for row in normalized:
        records = []
        for relative in row["deliverable_files"]:
            path = root.joinpath(*PurePosixPath(relative).parts)
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError(
                        f"deliverable file is not a single-link regular file: {relative}"
                    )
                digest = hashlib.sha256()
                size = 0
                while chunk := os.read(descriptor, 1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
            finally:
                os.close(descriptor)
            records.append({
                "path": relative,
                "sha256": digest.hexdigest(),
                "size": size,
            })
        bound_row = dict(row)
        bound_row["deliverable_file_records"] = records
        bound.append(bound_row)
    return bound