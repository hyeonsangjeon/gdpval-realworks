"""HuggingFace Repo Bootstrapper -- Step 0

Duplicates a pinned openai/gdpval revision into a user-owned
SUBMISSION_REPO_ID on HuggingFace, but **strips deliverable columns and excludes
deliverable_files/** so only the user's own experiment results are uploaded
later.

Also generates ``step0_needs_files_manifest.json`` from the SOURCE dataset --
a task-level map that records which tasks require file output.

Lifecycle:
    1. Create SUBMISSION_REPO_ID, reuse a 409 target with data, reject partials
    2. Prepare the pinned openai/gdpval revision in a temporary directory
    3. Generate step0_needs_files_manifest.json (BEFORE stripping)
    4. Strip deliverable columns + remove deliverable_files/
    5. Upload cleaned content to SUBMISSION_REPO_ID
    6. Stage the submission repo's exact HEAD
    7. Verify target semantics and reference bytes against pinned source identities
    8. Install the verified target snapshot, then validate it again

Usage:
    from core.repo_bootstrapper import RepoBootstrapper

    bs = RepoBootstrapper(submission_repo_id="HyeonSang/exp001_smoke_baseline")
    bs.bootstrap()
"""

import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import List, Optional

try:
    from huggingface_hub import HfApi, snapshot_download
    from huggingface_hub.utils import HfHubHTTPError
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from core.config import (
    DATASET_ID,
    DEFAULT_LOCAL_PATH,
    EXPECTED_TASK_COUNT,
    NEEDS_FILES_POLICIES_KNOWN,
    NEEDS_FILES_POLICY,
    WORKSPACE_DIR,
)
from core.needs_files import resolve_needs_files
from core.prompt_classifier import classify_prompt
from core.reference_integrity import (
    ReferenceIntegrityError,
    reference_manifest_record,
    validate_reference_record,
    validate_reference_relative_path,
)

# -- Columns that belong to the submitter (must be cleared) ----------------
_SUBMITTER_COLUMNS_TEXT = ["deliverable_text"]
_SUBMITTER_COLUMNS_LIST = [
    "deliverable_files",
    "deliverable_file_urls",
    "deliverable_file_hf_uris",
]

# -- Critical columns for validation --------------------------------------
_CRITICAL_COLUMNS = {
    "rubric_json", "rubric_pretty",
    "task_id", "prompt", "sector", "occupation", "reference_files",
}
MANIFEST_FILENAME = "step0_needs_files_manifest.json"
SOURCE_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
CANONICAL_ORDERED_TASK_IDS_SHA256 = (
    "df1fcd6415c55a17e4f39a254aaf0f0f9f2f55c751189f74d2713a873373aa3c"
)
CANONICAL_MANIFEST_SHA256_BY_POLICY = {
    "deliverable_only": "b8e17c8afa5d3cc8a1575ea728e2c86fef5eeb58cdb48cebd36e53fb88581546",
    "explicit_boost": "bc59a99036f5910ba31409bb971e45e4ee7e1e31d27545532d5c7435eded9146",
    "union": "c258914ff86a648da075ee6f485cad39d99c7b22b51e23f3a2d6f47e4bf37af9",
    "intersection": "d20667783f3ef5939ff90b54c170eb0974172be7d8d88ab41e0ebca9c124c714",
}
CANONICAL_SOURCE_COLUMNS = (
    "task_id",
    "sector",
    "occupation",
    "prompt",
    "reference_files",
    "reference_file_urls",
    "reference_file_hf_uris",
    "deliverable_files",
    "deliverable_file_urls",
    "deliverable_file_hf_uris",
    "rubric_pretty",
    "rubric_json",
)
CANONICAL_SOURCE_INPUT_COLUMNS = (
    "task_id",
    "sector",
    "occupation",
    "prompt",
    "reference_files",
    "reference_file_urls",
    "reference_file_hf_uris",
    "rubric_pretty",
    "rubric_json",
)
CANONICAL_SOURCE_INPUT_SHA256 = (
    "95f14ade3efbdac030226a67fbbc174ebeaae4a958f1982cab93ee057658faf5"
)

_MANIFEST_TOP_LEVEL_KEYS = {
    "_description",
    "_schema_version",
    "_source",
    "_source_revision",
    "_total_tasks",
    "_ordered_task_ids_sha256",
    "reference_files",
    "tasks",
    "_summary",
}
_MANIFEST_TASK_KEYS = {
    "needs_files",
    "original_file_count",
    "original_files",
    "has_deliverable_files",
    "prompt_classification",
    "policy_results",
}
_PROMPT_CLASSIFICATION_KEYS = {
    "requires_file",
    "explicit_exts",
    "inferred_exts",
    "confidence",
}
_CONFIDENCE_VALUES = ("explicit", "inferred", "ambiguous", "text_only")
_SUMMARY_KEYS = {
    "needs_files",
    "text_only",
    "active_policy",
    "policy_counts",
    "confidence_distribution",
}


def _compact_json_sha256(value) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalize_source_input_value(value):
    """Normalize one source value into a deterministic JSON-safe value."""
    converted_with_tolist = False
    converted_value = None
    if hasattr(value, "tolist"):
        try:
            converted_value = value.tolist()
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(
                f"Unable to convert {type(value).__name__} with tolist()"
            ) from exc
        if converted_value is value:
            raise TypeError(f"tolist() returned itself for {type(value).__name__}")
        converted_with_tolist = True
        if isinstance(converted_value, (list, tuple)):
            return _normalize_source_input_value(converted_value)

    if hasattr(value, "item"):
        try:
            scalar_value = value.item()
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(
                f"Unable to convert {type(value).__name__} with item()"
            ) from exc
        if scalar_value is value:
            raise TypeError(f"item() returned itself for {type(value).__name__}")
        return _normalize_source_input_value(scalar_value)

    if converted_with_tolist:
        return _normalize_source_input_value(converted_value)

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if not math.isfinite(value):
            raise ValueError("Source input projection contains a nonfinite float")
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_source_input_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("Source input projection dict keys must be strings")
        return {
            key: _normalize_source_input_value(item)
            for key, item in value.items()
        }
    raise TypeError(
        "Unsupported source input projection value type: "
        f"{type(value).__name__}"
    )


def _source_input_projection_sha256(dataframe) -> str:
    """Hash the canonical source-input projection of a dataframe."""
    projection = []
    input_dataframe = dataframe.loc[:, list(CANONICAL_SOURCE_INPUT_COLUMNS)]
    for values in input_dataframe.itertuples(index=False, name=None):
        projection.append(
            {
                column: _normalize_source_input_value(value)
                for column, value in zip(CANONICAL_SOURCE_INPUT_COLUMNS, values)
            }
        )
    encoded = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_manifest_digest_error(raw_manifest: bytes) -> Optional[str]:
    expected = CANONICAL_MANIFEST_SHA256_BY_POLICY.get(NEEDS_FILES_POLICY)
    actual = hashlib.sha256(raw_manifest).hexdigest()
    if expected is None:
        return (
            "No canonical digest is configured for active policy "
            f"{NEEDS_FILES_POLICY!r}"
        )
    if actual != expected:
        return (
            f"Manifest canonical digest for policy {NEEDS_FILES_POLICY!r} must "
            f"be {expected}, got {actual}"
        )
    return None


def _reject_symlink_components(path: Path) -> None:
    """Reject symlinks in every existing component without resolving them."""
    candidate = Path(path)
    if ".." in candidate.parts:
        raise RuntimeError(f"Path must not contain '..': {candidate}")
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    current = Path(candidate.anchor)
    components = candidate.parts[1:]
    for index, component in enumerate(components):
        current /= component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        except OSError as exc:
            raise RuntimeError(f"Unable to inspect path component {current}: {exc}") from exc

        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError(f"Path component is a symlink: {current}")
        if index < len(components) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError(f"Path ancestor is not a directory: {current}")


def _ensure_secure_directory(path: Path) -> None:
    _reject_symlink_components(path)
    Path(path).mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(path)
    try:
        metadata = Path(path).lstat()
    except OSError as exc:
        raise RuntimeError(f"Unable to inspect directory {path}: {exc}") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise RuntimeError(f"Path is not a directory: {path}")


def _validate_regular_tree(root: Path) -> None:
    """Require a tree containing only real directories and regular files."""
    root = Path(root)
    _reject_symlink_components(root)
    try:
        root_metadata = root.lstat()
    except OSError as exc:
        raise RuntimeError(f"Unable to inspect snapshot staging tree {root}: {exc}") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError(f"Snapshot staging root is not a directory: {root}")

    pending = [root]
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    entry_path = Path(entry.path)
                    metadata = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(metadata.st_mode):
                        raise RuntimeError(
                            f"Snapshot staging tree contains a symlink: {entry_path}"
                        )
                    if stat.S_ISDIR(metadata.st_mode):
                        pending.append(entry_path)
                    elif not stat.S_ISREG(metadata.st_mode):
                        raise RuntimeError(
                            "Snapshot staging tree contains a special file: "
                            f"{entry_path}"
                        )
        except OSError as exc:
            raise RuntimeError(
                f"Unable to inspect snapshot staging directory {directory}: {exc}"
            ) from exc


def _streaming_sha256(path: Path) -> str:
    """Hash one stable regular file without following symlinks."""
    candidate = Path(path)
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise RuntimeError(f"Unable to inspect input file {candidate}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise RuntimeError(f"Input file is a symlink: {candidate}")
    if not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError(f"Input path is not a regular file: {candidate}")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise RuntimeError(f"Unable to open input file {candidate}: {exc}") from exc

    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"Input path is not a regular file: {candidate}")
        digest = hashlib.sha256()
        bytes_read = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            bytes_read += len(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or bytes_read != after.st_size:
            raise RuntimeError(f"Input file changed while being read: {candidate}")
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _input_file_records(root: Path) -> List[dict[str, object]]:
    """Return identities for the exact runtime input surface of a snapshot."""
    snapshot_root = Path(root)
    _reject_symlink_components(snapshot_root)
    try:
        root_metadata = snapshot_root.lstat()
    except OSError as exc:
        raise RuntimeError(f"Unable to inspect input snapshot {snapshot_root}: {exc}") from exc
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError(f"Input snapshot root is not a directory: {snapshot_root}")

    records: List[dict[str, object]] = []

    def add_file(path: Path, relative_path: str) -> None:
        try:
            before = path.lstat()
        except OSError as exc:
            raise RuntimeError(f"Unable to inspect input file {path}: {exc}") from exc
        if stat.S_ISLNK(before.st_mode):
            raise RuntimeError(f"Input file is a symlink: {path}")
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"Input path is not a regular file: {path}")
        sha256 = _streaming_sha256(path)
        try:
            after = path.lstat()
        except OSError as exc:
            raise RuntimeError(f"Unable to re-inspect input file {path}: {exc}") from exc
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise RuntimeError(f"Input file changed while being hashed: {path}")
        records.append(
            {"path": relative_path, "sha256": sha256, "size": after.st_size}
        )

    for top_level_name in ("data", "reference_files"):
        top_level_path = snapshot_root / top_level_name
        try:
            top_level_metadata = top_level_path.lstat()
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Input snapshot directory is missing: {top_level_path}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Unable to inspect input snapshot directory {top_level_path}: {exc}"
            ) from exc
        if stat.S_ISLNK(top_level_metadata.st_mode):
            raise RuntimeError(f"Input snapshot directory is a symlink: {top_level_path}")
        if not stat.S_ISDIR(top_level_metadata.st_mode):
            raise RuntimeError(
                f"Input snapshot path is not a directory: {top_level_path}"
            )

        pending = [(top_level_path, (top_level_name,))]
        while pending:
            directory, relative_parts = pending.pop()
            try:
                with os.scandir(directory) as entries:
                    directory_entries = list(entries)
            except OSError as exc:
                raise RuntimeError(
                    f"Unable to scan input snapshot directory {directory}: {exc}"
                ) from exc

            for entry in directory_entries:
                entry_path = Path(entry.path)
                try:
                    entry_metadata = entry_path.lstat()
                except OSError as exc:
                    raise RuntimeError(
                        f"Unable to inspect input snapshot path {entry_path}: {exc}"
                    ) from exc
                if stat.S_ISLNK(entry_metadata.st_mode):
                    raise RuntimeError(f"Input snapshot path is a symlink: {entry_path}")
                entry_relative_parts = (*relative_parts, entry.name)
                if stat.S_ISDIR(entry_metadata.st_mode):
                    pending.append((entry_path, entry_relative_parts))
                elif stat.S_ISREG(entry_metadata.st_mode):
                    add_file(
                        entry_path,
                        PurePosixPath(*entry_relative_parts).as_posix(),
                    )
                else:
                    raise RuntimeError(
                        f"Input snapshot path is a special file: {entry_path}"
                    )

    manifest_path = snapshot_root / MANIFEST_FILENAME
    add_file(manifest_path, MANIFEST_FILENAME)
    records.sort(key=lambda record: str(record["path"]))
    return records


def _nonempty_submitter_list_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except (TypeError, ValueError):
            return True
    if isinstance(value, (list, tuple)):
        return bool(value)
    try:
        missing = pd.isna(value)
        return not bool(missing)
    except (TypeError, ValueError):
        return True


def _physical_reference_paths(snapshot_root: Path) -> List[str]:
    """Return every physical regular file under reference_files/."""
    root = Path(snapshot_root)
    _reject_symlink_components(root)
    reference_root = root / "reference_files"
    try:
        root_metadata = reference_root.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Snapshot reference_files directory not found: {reference_root}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Unable to inspect snapshot reference_files directory: {exc}"
        ) from exc
    if stat.S_ISLNK(root_metadata.st_mode):
        raise RuntimeError(
            f"Snapshot reference_files directory is a symlink: {reference_root}"
        )
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise RuntimeError(
            f"Snapshot reference_files path is not a directory: {reference_root}"
        )

    paths: List[str] = []
    pending = [(reference_root, ("reference_files",))]
    while pending:
        directory, relative_parts = pending.pop()
        try:
            with os.scandir(directory) as entries:
                directory_entries = list(entries)
        except OSError as exc:
            raise RuntimeError(
                f"Unable to scan snapshot reference directory {directory}: {exc}"
            ) from exc

        for entry in directory_entries:
            entry_path = Path(entry.path)
            try:
                metadata = entry_path.lstat()
            except OSError as exc:
                raise RuntimeError(
                    f"Unable to inspect snapshot reference path {entry_path}: {exc}"
                ) from exc
            entry_relative_parts = (*relative_parts, entry.name)
            if stat.S_ISLNK(metadata.st_mode):
                raise RuntimeError(
                    f"Snapshot reference path is a symlink: {entry_path}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                pending.append((entry_path, entry_relative_parts))
            elif stat.S_ISREG(metadata.st_mode):
                paths.append(PurePosixPath(*entry_relative_parts).as_posix())
            else:
                raise RuntimeError(
                    f"Snapshot reference path is a special file: {entry_path}"
                )

    return sorted(paths)


def validate_needs_files_manifest(
    dataframe,
    manifest_path: Path,
    *,
    source_repo: str = DATASET_ID,
    snapshot_root: Optional[Path] = None,
) -> List[str]:
    """Validate a canonical needs-files manifest against snapshot tasks."""
    errors: List[str] = []
    task_ids = list(dataframe["task_id"])
    expected_task_ids: set[str] = set()
    task_ids_valid = True

    for row_index, task_id in enumerate(task_ids):
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"task_id row {row_index} must be a nonempty string")
            task_ids_valid = False
            continue
        if task_id in expected_task_ids:
            errors.append(f"Duplicate task_id in snapshot: {task_id}")
            task_ids_valid = False
            continue
        expected_task_ids.add(task_id)

    path = Path(manifest_path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        errors.append(f"Canonical needs-files manifest not found: {path}")
        return errors
    except OSError as exc:
        errors.append(f"Unable to inspect needs-files manifest {path}: {exc}")
        return errors

    if stat.S_ISLNK(metadata.st_mode):
        errors.append(f"Needs-files manifest is a symlink: {path}")
        return errors
    if not stat.S_ISREG(metadata.st_mode):
        errors.append(f"Needs-files manifest is not a regular file: {path}")
        return errors

    try:
        raw_manifest = path.read_bytes()
        manifest = json.loads(raw_manifest)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"Unable to read needs-files manifest {path}: {exc}")
        return errors

    if digest_error := _canonical_manifest_digest_error(raw_manifest):
        errors.append(digest_error)

    if not isinstance(manifest, dict):
        errors.append("Needs-files manifest must be a JSON object")
        return errors

    if set(manifest) != _MANIFEST_TOP_LEVEL_KEYS:
        errors.append(
            "Manifest top-level keys must exactly match "
            f"{sorted(_MANIFEST_TOP_LEVEL_KEYS)}"
        )

    description = manifest.get("_description")
    if not isinstance(description, str) or not description:
        errors.append("Manifest _description must be a nonempty string")

    schema_version = manifest.get("_schema_version")
    if type(schema_version) is not int or schema_version != 3:
        errors.append(
            f"Manifest _schema_version must be 3, got {schema_version!r}"
        )

    if manifest.get("_source") != source_repo:
        errors.append(
            f"Manifest _source must be {source_repo!r}, "
            f"got {manifest.get('_source')!r}"
        )

    if manifest.get("_source_revision") != SOURCE_REVISION:
        errors.append(
            f"Manifest _source_revision must be {SOURCE_REVISION!r}, "
            f"got {manifest.get('_source_revision')!r}"
        )

    total_tasks = manifest.get("_total_tasks")
    if type(total_tasks) is not int or total_tasks != len(task_ids):
        errors.append(
            f"Manifest _total_tasks must be {len(task_ids)}, "
            f"got {total_tasks!r}"
        )

    if task_ids_valid:
        computed_ordered_digest = _compact_json_sha256(task_ids)
        if computed_ordered_digest != CANONICAL_ORDERED_TASK_IDS_SHA256:
            errors.append(
                "Snapshot ordered task_ids digest must be canonical "
                f"{CANONICAL_ORDERED_TASK_IDS_SHA256}, got "
                f"{computed_ordered_digest}"
            )

    manifest_ordered_digest = manifest.get("_ordered_task_ids_sha256")
    if manifest_ordered_digest != CANONICAL_ORDERED_TASK_IDS_SHA256:
        errors.append(
            "Manifest _ordered_task_ids_sha256 must be "
            f"{CANONICAL_ORDERED_TASK_IDS_SHA256}, got "
            f"{manifest_ordered_digest!r}"
        )

    reference_manifest = manifest.get("reference_files")
    if not isinstance(reference_manifest, dict):
        errors.append("Manifest reference_files must be an object")
        reference_manifest = {}
    declared_reference_paths, declaration_errors = _declared_reference_paths(
        dataframe
    )
    errors.extend(declaration_errors)
    if list(reference_manifest) != declared_reference_paths:
        errors.append(
            "Manifest reference_files must exactly match declared paths in order"
        )
    if snapshot_root is not None:
        try:
            physical_reference_paths = _physical_reference_paths(snapshot_root)
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            manifest_reference_paths = sorted(reference_manifest)
            if physical_reference_paths != manifest_reference_paths:
                physical_path_set = set(physical_reference_paths)
                manifest_path_set = set(manifest_reference_paths)
                missing = sorted(manifest_path_set - physical_path_set)
                extra = sorted(physical_path_set - manifest_path_set)
                errors.append(
                    "Snapshot reference paths differ from manifest "
                    f"(missing={missing}, extra={extra})"
                )
    for relative_path, record in reference_manifest.items():
        try:
            validate_reference_relative_path(relative_path)
            sha256, size = validate_reference_record(record)
            if snapshot_root is not None:
                actual = reference_manifest_record(snapshot_root, relative_path)
                if actual != {"sha256": sha256, "size": size}:
                    errors.append(
                        f"Reference identity differs from manifest: {relative_path}"
                    )
        except ReferenceIntegrityError as exc:
            errors.append(str(exc))

    tasks = manifest.get("tasks")
    if not isinstance(tasks, dict):
        errors.append("Manifest tasks must be an object")
        tasks = {}
    else:
        manifest_task_ids = list(tasks)
        invalid_manifest_task_ids = [
            task_id
            for task_id in manifest_task_ids
            if not isinstance(task_id, str) or not task_id
        ]
        if invalid_manifest_task_ids:
            errors.append(
                "Manifest task_ids must be nonempty strings, got "
                f"{invalid_manifest_task_ids!r}"
            )
        if len(manifest_task_ids) != len(set(manifest_task_ids)):
            errors.append("Manifest task_ids must be unique")
        if manifest_task_ids != task_ids:
            manifest_task_id_set = set(manifest_task_ids)
            missing = sorted(expected_task_ids - manifest_task_id_set)
            unexpected = sorted(manifest_task_id_set - expected_task_ids)
            errors.append(
                "Manifest tasks must exactly match snapshot task_ids in order "
                f"(missing={missing}, unexpected={unexpected})"
            )

    summary = manifest.get("_summary")
    if not isinstance(summary, dict):
        errors.append("Manifest _summary must be an object")
        summary = {}
    elif set(summary) != _SUMMARY_KEYS:
        errors.append(
            "Manifest _summary keys must exactly match "
            f"{sorted(_SUMMARY_KEYS)}"
        )

    known_policies = tuple(NEEDS_FILES_POLICIES_KNOWN)
    known_policy_keys = set(known_policies)
    active_policy = summary.get("active_policy")
    active_policy_valid = (
        isinstance(active_policy, str)
        and active_policy == NEEDS_FILES_POLICY
        and active_policy in known_policy_keys
    )
    if not active_policy_valid:
        errors.append(
            "Manifest _summary.active_policy must equal current "
            f"NEEDS_FILES_POLICY {NEEDS_FILES_POLICY!r}, got {active_policy!r}"
        )

    computed_needs_files = 0
    needs_files_complete = True
    computed_policy_counts = {policy: 0 for policy in known_policies}
    policy_counts_complete = {policy: True for policy in known_policies}
    computed_confidence_distribution = {
        confidence: 0 for confidence in _CONFIDENCE_VALUES
    }
    confidence_distribution_complete = True

    for task_id, entry in tasks.items():
        if not isinstance(entry, dict):
            errors.append(f"Manifest task {task_id!r} must be an object")
            needs_files_complete = False
            confidence_distribution_complete = False
            for policy in known_policies:
                policy_counts_complete[policy] = False
            continue

        if set(entry) != _MANIFEST_TASK_KEYS:
            errors.append(
                f"Manifest task {task_id!r} keys must exactly match "
                f"{sorted(_MANIFEST_TASK_KEYS)}"
            )

        needs_files = entry.get("needs_files")
        if type(needs_files) is not bool:
            errors.append(
                f"Manifest task {task_id!r} needs_files must be a bool"
            )
            needs_files_complete = False
        elif needs_files:
            computed_needs_files += 1

        original_file_count = entry.get("original_file_count")
        count_valid = (
            type(original_file_count) is int and original_file_count >= 0
        )
        if not count_valid:
            errors.append(
                f"Manifest task {task_id!r} original_file_count must be a "
                "nonnegative int"
            )

        original_files = entry.get("original_files")
        files_valid = isinstance(original_files, list) and all(
            isinstance(filename, str) for filename in original_files
        )
        if not files_valid:
            errors.append(
                f"Manifest task {task_id!r} original_files must be a list[str]"
            )
        elif count_valid and len(original_files) != original_file_count:
            errors.append(
                f"Manifest task {task_id!r} original_files length must match "
                "original_file_count"
            )

        has_deliverable_files = entry.get("has_deliverable_files")
        if type(has_deliverable_files) is not bool:
            errors.append(
                f"Manifest task {task_id!r} has_deliverable_files must be a bool"
            )
        elif count_valid and has_deliverable_files != (original_file_count > 0):
            errors.append(
                f"Manifest task {task_id!r} has_deliverable_files must match "
                "original_file_count > 0"
            )

        prompt_classification = entry.get("prompt_classification")
        if not isinstance(prompt_classification, dict):
            errors.append(
                f"Manifest task {task_id!r} prompt_classification must be an object"
            )
            confidence_distribution_complete = False
        else:
            if set(prompt_classification) != _PROMPT_CLASSIFICATION_KEYS:
                errors.append(
                    f"Manifest task {task_id!r} prompt_classification keys must "
                    f"exactly match {sorted(_PROMPT_CLASSIFICATION_KEYS)}"
                )

            requires_file = prompt_classification.get("requires_file")
            if type(requires_file) is not bool:
                errors.append(
                    f"Manifest task {task_id!r} prompt_classification.requires_file "
                    "must be a bool"
                )

            for extension_field in ("explicit_exts", "inferred_exts"):
                extensions = prompt_classification.get(extension_field)
                if not isinstance(extensions, list) or not all(
                    isinstance(extension, str) for extension in extensions
                ):
                    errors.append(
                        f"Manifest task {task_id!r} prompt_classification."
                        f"{extension_field} must be a list[str]"
                    )

            confidence = prompt_classification.get("confidence")
            if not isinstance(confidence, str) or confidence not in _CONFIDENCE_VALUES:
                errors.append(
                    f"Manifest task {task_id!r} prompt_classification.confidence "
                    f"must be one of {list(_CONFIDENCE_VALUES)}, got {confidence!r}"
                )
                confidence_distribution_complete = False
            else:
                computed_confidence_distribution[confidence] += 1
                if (
                    type(requires_file) is bool
                    and requires_file != (confidence != "text_only")
                ):
                    errors.append(
                        f"Manifest task {task_id!r} prompt_classification."
                        "requires_file must match confidence"
                    )

        policy_results = entry.get("policy_results")
        if not isinstance(policy_results, dict):
            errors.append(
                f"Manifest task {task_id!r} policy_results must be an object"
            )
            for policy in known_policies:
                policy_counts_complete[policy] = False
            continue

        if set(policy_results) != known_policy_keys:
            errors.append(
                f"Manifest task {task_id!r} policy_results keys must exactly "
                f"match {sorted(known_policy_keys)}"
            )

        for policy in known_policies:
            policy_value = policy_results.get(policy)
            if type(policy_value) is not bool:
                errors.append(
                    f"Manifest task {task_id!r} policy_results[{policy!r}] "
                    "must be a bool"
                )
                policy_counts_complete[policy] = False
            elif policy_value:
                computed_policy_counts[policy] += 1

        if (
            active_policy_valid
            and type(needs_files) is bool
            and type(policy_results.get(active_policy)) is bool
            and needs_files != policy_results[active_policy]
        ):
            errors.append(
                f"Manifest task {task_id!r} needs_files must match active "
                f"policy {active_policy!r}"
            )

    summary_needs_files = summary.get("needs_files")
    if type(summary_needs_files) is not int:
        errors.append("Manifest _summary.needs_files must be an int")
    elif needs_files_complete and summary_needs_files != computed_needs_files:
        errors.append(
            "Manifest _summary.needs_files does not match computed count "
            f"{computed_needs_files}"
        )

    summary_text_only = summary.get("text_only")
    computed_text_only = len(tasks) - computed_needs_files
    if type(summary_text_only) is not int:
        errors.append("Manifest _summary.text_only must be an int")
    elif needs_files_complete and summary_text_only != computed_text_only:
        errors.append(
            "Manifest _summary.text_only does not match computed count "
            f"{computed_text_only}"
        )

    summary_policy_counts = summary.get("policy_counts")
    if not isinstance(summary_policy_counts, dict):
        errors.append("Manifest _summary.policy_counts must be an object")
    else:
        if set(summary_policy_counts) != known_policy_keys:
            errors.append(
                "Manifest _summary.policy_counts keys must exactly match "
                f"{sorted(known_policy_keys)}"
            )
        for policy in known_policies:
            summary_count = summary_policy_counts.get(policy)
            if type(summary_count) is not int:
                errors.append(
                    f"Manifest _summary.policy_counts[{policy!r}] must be an int"
                )
            elif (
                policy_counts_complete[policy]
                and summary_count != computed_policy_counts[policy]
            ):
                errors.append(
                    f"Manifest _summary.policy_counts[{policy!r}] does not "
                    f"match computed count {computed_policy_counts[policy]}"
                )

    summary_confidence_distribution = summary.get("confidence_distribution")
    confidence_keys = set(_CONFIDENCE_VALUES)
    if not isinstance(summary_confidence_distribution, dict):
        errors.append(
            "Manifest _summary.confidence_distribution must be an object"
        )
    else:
        if set(summary_confidence_distribution) != confidence_keys:
            errors.append(
                "Manifest _summary.confidence_distribution keys must exactly "
                f"match {sorted(confidence_keys)}"
            )
        for confidence in _CONFIDENCE_VALUES:
            summary_count = summary_confidence_distribution.get(confidence)
            if type(summary_count) is not int:
                errors.append(
                    "Manifest _summary.confidence_distribution"
                    f"[{confidence!r}] must be an int"
                )
            elif (
                confidence_distribution_complete
                and summary_count != computed_confidence_distribution[confidence]
            ):
                errors.append(
                    "Manifest _summary.confidence_distribution"
                    f"[{confidence!r}] does not match computed count "
                    f"{computed_confidence_distribution[confidence]}"
                )

    return errors


def _declared_reference_paths(dataframe) -> tuple[List[str], List[str]]:
    """Return unique canonical reference paths in dataframe order."""
    errors: List[str] = []
    if "reference_files" not in dataframe.columns:
        return [], ["Missing critical column: reference_files"]

    declared_paths: List[str] = []
    seen_paths: set[str] = set()

    for row_index, value in enumerate(dataframe["reference_files"]):
        if hasattr(value, "tolist"):
            try:
                value = value.tolist()
            except (TypeError, ValueError):
                errors.append(
                    f"reference_files row {row_index} is not list-like"
                )
                continue

        if value is None or isinstance(value, (str, bytes)):
            errors.append(f"reference_files row {row_index} is not list-like")
            continue

        try:
            items = list(value)
        except TypeError:
            errors.append(f"reference_files row {row_index} is not iterable")
            continue

        for item in items:
            if not isinstance(item, str):
                errors.append(
                    f"reference_files row {row_index} contains a non-string path"
                )
                continue

            try:
                validate_reference_relative_path(item)
            except ReferenceIntegrityError:
                errors.append(
                    f"reference_files row {row_index} has an unsafe path: {item!r}"
                )
                continue

            if item in seen_paths:
                errors.append(f"Duplicate reference file path: {item}")
                continue

            seen_paths.add(item)
            declared_paths.append(item)

    return declared_paths, errors


def build_reference_manifest(
    dataframe,
    local_path: Path,
) -> tuple[dict[str, dict[str, object]], List[str]]:
    """Build content identities for every parquet-declared reference file."""
    declared_paths, errors = _declared_reference_paths(dataframe)
    records: dict[str, dict[str, object]] = {}
    for relative_path in declared_paths:
        try:
            records[relative_path] = reference_manifest_record(
                Path(local_path), relative_path
            )
        except ReferenceIntegrityError as exc:
            errors.append(str(exc))
    return records, errors


def validate_reference_snapshot(dataframe, local_path: Path) -> List[str]:
    """Validate and hash reference files declared by the snapshot parquet."""
    _records, errors = build_reference_manifest(dataframe, local_path)
    return errors


class RepoBootstrapper:
    """Bootstrap a submission HF dataset repo from a pinned openai/gdpval.

    Steps:
        0. Abort if repo already has content
        1. Download the required pinned openai/gdpval inputs to temp dir
        2. Generate step0_needs_files_manifest.json (from ORIGINAL data)
        3. Strip deliverable columns + remove deliverable_files/
        4. Upload to submission repo (clean)
        5. Stage the exact current submission HEAD
        6. Verify target semantics and pinned source identities before installation
        7. Install to a fresh local_path and validate again
    """

    SOURCE_REPO = DATASET_ID  # "openai/gdpval"

    def __init__(
        self,
        submission_repo_id: str,
        local_path: Optional[str] = None,
        token: Optional[str] = None,
        private: bool = False,
    ):
        if not HF_HUB_AVAILABLE:
            raise ImportError("huggingface_hub is required.  pip install huggingface_hub")

        self.submission_repo_id = submission_repo_id
        self.local_path = Path(local_path) if local_path else DEFAULT_LOCAL_PATH
        self.token = token or os.getenv("HF_TOKEN")
        self.private = private
        self.api = HfApi(token=self.token)
        self.manifest_path = WORKSPACE_DIR / MANIFEST_FILENAME

    # -- Public API --------------------------------------------------------

    def bootstrap(self, force: bool = False) -> Path:
        """Run full bootstrap pipeline.

        Returns:
            Path to validated local snapshot directory.
        """
        print(f"\n{'='*60}")
        print("Step 0: Bootstrap -- Preparing Submission Dataset")
        print(f"{'='*60}")
        print(f"   Source repo : {self.SOURCE_REPO}")
        print(f"   Target repo : {self.submission_repo_id}")
        print(f"   Local path  : {self.local_path}")

        if not self.token:
            raise ValueError("HF_TOKEN is required.\n   export HF_TOKEN=hf_xxx")

        # 1. Ensure remote repo (skip if already bootstrapped)
        self._ensure_remote_repo()

        # 2. Download submission repo to local
        self._download_snapshot(force=force)

        # 3. Import the source-derived manifest persisted in the target.
        self._restore_manifest_from_snapshot()

        # 4. Validate
        self._validate_snapshot()

        print("\n   Bootstrap complete!")
        print(f"      Local snapshot : {self.local_path}")
        print(f"      Manifest       : {self.manifest_path}")
        print(f"{'='*60}")
        return self.local_path

    # -- Remote Repo -------------------------------------------------------

    def _repo_has_content(self) -> bool:
        files = self.api.list_repo_files(
            repo_id=self.submission_repo_id,
            repo_type="dataset",
            token=self.token,
        )
        return any(f.startswith("data/") for f in files)

    def _ensure_remote_repo(self) -> None:
        """Create submission repo from openai/gdpval with deliverables stripped."""
        self.api.whoami(token=self.token)

        try:
            self.api.create_repo(
                repo_id=self.submission_repo_id,
                repo_type="dataset",
                private=self.private,
                exist_ok=False,
                token=self.token,
            )
        except HfHubHTTPError as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            if status_code != 409:
                raise

            if self._repo_has_content():
                print(f"\n   \u2705 Repo already exists with data: {self.submission_repo_id}")
                print("   Reusing existing repo (idempotent).")
                return  # idempotent: already bootstrapped, skip

            raise RuntimeError(
                "Target dataset exists without a data/ snapshot; refusing "
                "automatic repository deletion. Use a new disposable target "
                "or remove the partial repository explicitly."
            ) from exc

        self._duplicate_stripped()

    def _duplicate_stripped(self) -> None:
        """Download pinned source, strip deliverables, generate manifest, upload."""
        print(f"\n   Duplicating {self.SOURCE_REPO} -> {self.submission_repo_id}")
        print("      (deliverable columns cleared, deliverable_files/ excluded)")

        old_timeout = os.environ.get("HF_HUB_DOWNLOAD_TIMEOUT")
        os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = str(
            max(int(old_timeout or "0"), 300)
        )

        print(f"   Repo created: {self.submission_repo_id}")

        # 1. Download + strip + upload (with retry)
        max_retries = 3
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        print(f"\n   Downloading {self.SOURCE_REPO} "
                              f"(attempt {attempt}/{max_retries}) ...")
                        source_root = Path(tmpdir)
                        self._prepare_pinned_source_snapshot(source_root)
                        print("   Downloaded and prepared in temp dir")

                        print(f"\n   Uploading to {self.submission_repo_id} ...")
                        self.api.upload_folder(
                            folder_path=source_root,
                            repo_id=self.submission_repo_id,
                            repo_type="dataset",
                            token=self.token,
                            ignore_patterns=[".git*", ".cache*"],
                        )
                    break  # success
                except Exception as e:
                    if attempt == max_retries:
                        raise RuntimeError(
                            f"Failed to duplicate {self.SOURCE_REPO} after "
                            f"{max_retries} attempts: {e}"
                        ) from e
                    wait = 30 * attempt
                    print(f"   Attempt {attempt} failed: {e}")
                    print(f"      Retrying in {wait}s ...")
                    time.sleep(wait)
        finally:
            if old_timeout is None:
                os.environ.pop("HF_HUB_DOWNLOAD_TIMEOUT", None)
            else:
                os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = old_timeout

        print(f"   Repo duplicated (clean): {self.submission_repo_id}")

    # -- Strip deliverable columns -----------------------------------------

    def _strip_deliverables_in_dir(self, dir_path: str) -> None:
        """Strip deliverable columns from all parquet files in a directory."""
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas is required to strip deliverable columns")

        data_dir = Path(dir_path) / "data"
        if not data_dir.exists():
            return

        parquets = sorted(data_dir.glob("train-*.parquet"))
        for pq_path in parquets:
            df = pd.read_parquet(pq_path)
            changed = False

            for col in _SUBMITTER_COLUMNS_TEXT:
                if col in df.columns:
                    df[col] = ""
                    changed = True

            for col in _SUBMITTER_COLUMNS_LIST:
                if col in df.columns:
                    df[col] = [[] for _ in range(len(df))]
                    changed = True

            if changed:
                df.to_parquet(pq_path, index=False)

        print(f"   Stripped deliverable columns from {len(parquets)} parquet file(s)")

    def _prepare_pinned_source_snapshot(self, root: Path) -> Path:
        """Download and prepare required files from the pinned source revision."""
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas is required to prepare the pinned source")

        source_root = Path(root)
        _ensure_secure_directory(source_root)
        snapshot_download(
            repo_id=self.SOURCE_REPO,
            repo_type="dataset",
            revision=SOURCE_REVISION,
            local_dir=source_root,
            token=self.token,
            allow_patterns=[".gitattributes", "README.md", "data/**"],
        )
        _validate_regular_tree(source_root)

        data_dir = source_root / "data"
        parquets = sorted(data_dir.glob("train-*.parquet"))
        if not parquets:
            raise RuntimeError(f"No train-*.parquet files found in {data_dir}")
        try:
            dataframe = pd.concat(
                [pd.read_parquet(path) for path in parquets],
                ignore_index=True,
            )
        except (ImportError, OSError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Unable to read pinned source parquet: {exc}") from exc

        declared_reference_paths, declaration_errors = _declared_reference_paths(
            dataframe
        )
        if declaration_errors:
            raise ValueError(
                "Pinned source reference declarations are invalid:\n      "
                + "\n      ".join(declaration_errors)
            )
        if declared_reference_paths:
            snapshot_download(
                repo_id=self.SOURCE_REPO,
                repo_type="dataset",
                revision=SOURCE_REVISION,
                local_dir=source_root,
                token=self.token,
                allow_patterns=declared_reference_paths,
            )
        _validate_regular_tree(source_root)

        manifest_path = self._generate_manifest_from_dir(
            source_root,
            output_path=source_root / MANIFEST_FILENAME,
        )
        self._strip_deliverables_in_dir(source_root)

        deliverable_dir = source_root / "deliverable_files"
        try:
            deliverable_metadata = deliverable_dir.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError(
                f"Unable to inspect source deliverable directory: {exc}"
            ) from exc
        else:
            if stat.S_ISLNK(deliverable_metadata.st_mode):
                raise RuntimeError(
                    f"Source deliverable directory is a symlink: {deliverable_dir}"
                )
            if not stat.S_ISDIR(deliverable_metadata.st_mode):
                raise RuntimeError(
                    "Source deliverable path is not a directory: "
                    f"{deliverable_dir}"
                )
            shutil.rmtree(deliverable_dir)
            print("   Removed deliverable_files/ from upload")

        _validate_regular_tree(source_root)
        return manifest_path

    # -- Generate step0_needs_files_manifest.json ---------------------------

    def _generate_manifest_from_dir(
        self,
        dir_path,
        *,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Generate step0_needs_files_manifest.json (V3 schema) from SOURCE parquet.

        Combines two signals per task:

        * **deliverable signal**: non-empty ``deliverable_files`` column from
          the original openai/gdpval dataset.
        * **prompt signal**: heuristic from
          :func:`core.prompt_classifier.classify_prompt` over the ``prompt``
          column (Appendix A of ``HF_PROMPT_ANALYSIS_REPORT``).

        Each task entry records the dual signals plus ``policy_results`` for
        every policy in ``NEEDS_FILES_POLICIES_KNOWN``.  The top-level
        ``needs_files`` flag is resolved using the active policy
        (``NEEDS_FILES_POLICY``, default ``"deliverable_only"``) so that
        downstream consumers using ``NeedsFilesManifest.needs_files(task_id)``
        observe no behavioural change from the V1 schema by default.
        """
        if not PANDAS_AVAILABLE:
            raise RuntimeError("pandas is required for manifest generation")

        data_dir = Path(dir_path) / "data"
        if not data_dir.exists():
            raise RuntimeError(f"Source data directory not found: {data_dir}")

        parquets = sorted(data_dir.glob("train-*.parquet"))
        if not parquets:
            raise RuntimeError(f"No train-*.parquet files found in {data_dir}")

        # Read all parquet shards
        dfs = [pd.read_parquet(p) for p in parquets]
        df = pd.concat(dfs, ignore_index=True)
        task_ids = list(df["task_id"])
        ordered_task_ids_digest = _compact_json_sha256(task_ids)
        if ordered_task_ids_digest != CANONICAL_ORDERED_TASK_IDS_SHA256:
            raise ValueError(
                "Source parquet ordered task_ids digest does not match canonical "
                f"digest {CANONICAL_ORDERED_TASK_IDS_SHA256}: "
                f"{ordered_task_ids_digest}"
            )

        active_policy = NEEDS_FILES_POLICY
        if active_policy not in NEEDS_FILES_POLICIES_KNOWN:
            raise ValueError(
                f"NEEDS_FILES_POLICY={active_policy!r} not in "
                f"{NEEDS_FILES_POLICIES_KNOWN}"
            )

        manifest = {
            "_description": (
                "Generated by Step 0 bootstrap from openai/gdpval. "
                "Dual-signal manifest: deliverable signal (HF dataset) + "
                "prompt signal (heuristic from prompt_classifier). "
                "needs_files is resolved by the active policy."
            ),
            "_schema_version": 3,
            "_source": self.SOURCE_REPO,
            "_source_revision": SOURCE_REVISION,
            "_total_tasks": len(df),
            "_ordered_task_ids_sha256": ordered_task_ids_digest,
            "reference_files": {},
            "tasks": {},
        }

        reference_manifest, reference_errors = build_reference_manifest(
            df, Path(dir_path)
        )
        if reference_errors:
            raise ValueError(
                "Source reference validation failed:\n      "
                + "\n      ".join(reference_errors)
            )
        manifest["reference_files"] = reference_manifest

        policy_counts = {p: 0 for p in NEEDS_FILES_POLICIES_KNOWN}
        confidence_distribution = {
            "explicit": 0,
            "inferred": 0,
            "ambiguous": 0,
            "text_only": 0,
        }

        for _, row in df.iterrows():
            task_id = row["task_id"]
            files = row.get("deliverable_files", [])
            if files is None:
                files = []
            if isinstance(files, str):
                files = [files] if files else []
            # numpy array -> list
            if hasattr(files, 'tolist'):
                files = files.tolist()

            has_deliverable = len(files) > 0

            prompt_text = row.get("prompt", "")
            if prompt_text is None:
                prompt_text = ""
            classification = classify_prompt(str(prompt_text))

            policy_results = {
                p: resolve_needs_files(has_deliverable, classification, p)
                for p in NEEDS_FILES_POLICIES_KNOWN
            }

            needs_files_val = policy_results[active_policy]

            manifest["tasks"][task_id] = {
                "needs_files": needs_files_val,
                "original_file_count": len(files),
                "original_files": list(files),
                "has_deliverable_files": has_deliverable,
                "prompt_classification": {
                    "requires_file": classification.requires_file,
                    "explicit_exts": list(classification.explicit_exts),
                    "inferred_exts": list(classification.inferred_exts),
                    "confidence": classification.confidence,
                },
                "policy_results": policy_results,
            }

            for p, v in policy_results.items():
                if v:
                    policy_counts[p] += 1
            confidence_distribution[classification.confidence] += 1

        needs_count = policy_counts[active_policy]
        text_only_count = len(df) - needs_count

        manifest["_summary"] = {
            "needs_files": needs_count,
            "text_only": text_only_count,
            "active_policy": active_policy,
            "policy_counts": policy_counts,
            "confidence_distribution": confidence_distribution,
        }

        destination = (
            Path(output_path) if output_path is not None else Path(self.manifest_path)
        )
        _ensure_secure_directory(destination.parent)
        try:
            destination_metadata = destination.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError(
                f"Unable to inspect manifest destination {destination}: {exc}"
            ) from exc
        else:
            if stat.S_ISLNK(destination_metadata.st_mode):
                raise RuntimeError(f"Manifest destination is a symlink: {destination}")
            if not stat.S_ISREG(destination_metadata.st_mode):
                raise RuntimeError(
                    f"Manifest destination is not a regular file: {destination}"
                )

        encoded_manifest = json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ).encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(
            os,
            "O_NOFOLLOW",
            0,
        )
        try:
            descriptor = os.open(destination, flags, 0o666)
        except OSError as exc:
            raise RuntimeError(
                f"Unable to open manifest destination {destination}: {exc}"
            ) from exc
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                descriptor = -1
                temporary_file.write(encoded_manifest)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)

        validation_errors = validate_needs_files_manifest(
            df,
            destination,
            source_repo=self.SOURCE_REPO,
            snapshot_root=Path(dir_path),
        )
        if validation_errors:
            raise ValueError(
                "Generated needs-files manifest validation failed:\n      "
                + "\n      ".join(validation_errors)
            )

        print(
            f"   Generated step0_needs_files_manifest.json "
            f"(policy={active_policy}, needs_files={needs_count}, "
            f"text_only={text_only_count})"
        )
        print(
            f"   [manifest] confidence_distribution={confidence_distribution}"
        )
        return destination

    # -- Download snapshot -------------------------------------------------

    def _restore_manifest_from_snapshot(self) -> None:
        source = self.local_path / MANIFEST_FILENAME
        _reject_symlink_components(source)
        try:
            metadata = source.lstat()
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Target dataset has no canonical needs-files manifest; use a "
                "new disposable target instead of regenerating from stripped data"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError("Target needs-files manifest is not a regular file")
        content = source.read_bytes()
        if digest_error := _canonical_manifest_digest_error(content):
            raise RuntimeError(digest_error)
        destination = Path(self.manifest_path)
        parent = destination.parent
        _ensure_secure_directory(parent)

        try:
            destination_metadata = destination.lstat()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise RuntimeError(
                f"Unable to inspect workspace manifest {destination}: {exc}"
            ) from exc
        else:
            if stat.S_ISLNK(destination_metadata.st_mode):
                raise RuntimeError(f"Workspace manifest is a symlink: {destination}")
            if not stat.S_ISREG(destination_metadata.st_mode):
                raise RuntimeError(
                    f"Workspace manifest is not a regular file: {destination}"
                )

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                descriptor = -1
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary, destination)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _download_snapshot(self, force: bool = False) -> None:
        """Install exact HEAD after validating pinned source identities."""
        del force  # Retained for API compatibility; every call refreshes the snapshot.

        repo_info = self.api.repo_info(
            repo_id=self.submission_repo_id,
            repo_type="dataset",
            token=self.token,
        )
        head = getattr(repo_info, "sha", None)
        if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None:
            raise RuntimeError(
                "Target dataset HEAD must be a full lowercase 40-character SHA, "
                f"got {head!r}"
            )

        print(
            f"\n   Downloading {self.submission_repo_id}@{head} "
            f"-> {self.local_path} ..."
        )
        parent = self.local_path.parent
        _ensure_secure_directory(parent)

        # Increase per-file read timeout (default is too low for large reference files)
        os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

        with tempfile.TemporaryDirectory(
            prefix=".gdpval-target-",
            dir=parent,
        ) as temporary_root:
            target_staging = Path(temporary_root) / "target"
            target_staging.mkdir()

            max_retries = 5
            for attempt in range(1, max_retries + 1):
                try:
                    print(
                        f"   Downloading snapshot (attempt {attempt}/{max_retries}) ..."
                    )
                    snapshot_download(
                        repo_id=self.submission_repo_id,
                        repo_type="dataset",
                        revision=head,
                        local_dir=target_staging,
                        token=self.token,
                        allow_patterns=[
                            ".gitattributes",
                            "README.md",
                            "data/**",
                            "reference_files/**",
                            MANIFEST_FILENAME,
                        ],
                    )
                    break
                except Exception as e:
                    if attempt == max_retries:
                        raise RuntimeError(
                            f"Failed to download {self.submission_repo_id}@{head} "
                            f"after {max_retries} attempts: {e}"
                        ) from e
                    wait = 30 * attempt
                    print(f"   Attempt {attempt} failed: {e}")
                    print(
                        f"      Retrying in {wait}s ... "
                        "(already-downloaded files are skipped)"
                    )
                    time.sleep(wait)

            target_manifest = target_staging / MANIFEST_FILENAME

            _validate_regular_tree(target_staging)

            validation_errors = [
                f"target: {error}"
                for error in self._snapshot_validation_errors(
                    target_staging,
                    target_manifest,
                )
            ]
            if validation_errors:
                raise ValueError(
                    "Staged snapshot validation failed:\n      "
                    + "\n      ".join(validation_errors)
                )

            _reject_symlink_components(parent)
            try:
                local_metadata = self.local_path.lstat()
            except FileNotFoundError:
                local_exists = False
            except OSError as exc:
                raise RuntimeError(
                    f"Unable to inspect local snapshot {self.local_path}: {exc}"
                ) from exc
            else:
                local_exists = True
                if stat.S_ISLNK(local_metadata.st_mode):
                    raise RuntimeError(
                        f"Local snapshot path is a symlink: {self.local_path}"
                    )
                if not stat.S_ISDIR(local_metadata.st_mode):
                    raise RuntimeError(
                        f"Local snapshot path is not a directory: {self.local_path}"
                    )

            backup_path: Optional[Path] = None
            preserve_backup = False
            try:
                if local_exists:
                    backup_path = Path(
                        tempfile.mkdtemp(prefix=".gdpval-backup-", dir=parent)
                    )
                    os.replace(self.local_path, backup_path)

                try:
                    os.replace(target_staging, self.local_path)
                except Exception as replacement_error:
                    if backup_path is not None:
                        try:
                            os.replace(backup_path, self.local_path)
                        except Exception as restore_error:
                            preserve_backup = True
                            raise RuntimeError(
                                "Failed to install downloaded snapshot and restore "
                                f"the previous snapshot; backup preserved at {backup_path}"
                            ) from restore_error
                    raise replacement_error
            finally:
                if backup_path is not None and not preserve_backup:
                    try:
                        backup_metadata = backup_path.lstat()
                    except FileNotFoundError:
                        pass
                    else:
                        if not stat.S_ISDIR(backup_metadata.st_mode):
                            raise RuntimeError(
                                f"Snapshot backup is not a directory: {backup_path}"
                            )
                        shutil.rmtree(backup_path)

        # Create empty deliverable_files/ for later experiment outputs
        (self.local_path / "deliverable_files").mkdir(parents=True, exist_ok=True)

        print(f"   Local snapshot ready: {self.local_path}")

    # -- Validate ----------------------------------------------------------

    def _snapshot_validation_errors(
        self,
        local_path: Path,
        manifest_path: Path,
    ) -> List[str]:
        """Return every semantic validation error for the supplied snapshot."""
        root = Path(local_path)
        errors: List[str] = []
        if not PANDAS_AVAILABLE:
            errors.append("pandas is required for snapshot validation")

        dataframe = None
        data_dir = root / "data"
        try:
            data_metadata = data_dir.lstat()
        except FileNotFoundError:
            errors.append("data/ directory not found")
        except OSError as exc:
            errors.append(f"Unable to inspect data/ directory: {exc}")
        else:
            if stat.S_ISLNK(data_metadata.st_mode):
                errors.append("data/ directory is a symlink")
            elif not stat.S_ISDIR(data_metadata.st_mode):
                errors.append("data/ path is not a directory")
            else:
                try:
                    with os.scandir(data_dir) as entries:
                        parquet_entries = [
                            Path(entry.path)
                            for entry in entries
                            if Path(entry.name).match("train-*.parquet")
                        ]
                except OSError as exc:
                    errors.append(f"Unable to scan data/ directory: {exc}")
                    parquet_entries = []

                parquets: List[Path] = []
                for parquet_path in sorted(parquet_entries):
                    try:
                        parquet_metadata = parquet_path.lstat()
                    except OSError as exc:
                        errors.append(
                            f"Unable to inspect parquet file {parquet_path.name}: {exc}"
                        )
                        continue
                    if stat.S_ISLNK(parquet_metadata.st_mode):
                        errors.append(f"Parquet file is a symlink: {parquet_path.name}")
                    elif not stat.S_ISREG(parquet_metadata.st_mode):
                        errors.append(
                            f"Parquet path is not a regular file: {parquet_path.name}"
                        )
                    else:
                        parquets.append(parquet_path)

                if not parquet_entries:
                    errors.append("No train-*.parquet files found in data/")
                elif PANDAS_AVAILABLE and parquets:
                    try:
                        dataframe = pd.concat(
                            [pd.read_parquet(path) for path in parquets],
                            ignore_index=True,
                        )
                    except (ImportError, OSError, TypeError, ValueError) as exc:
                        errors.append(f"Unable to read snapshot parquet: {exc}")

        if dataframe is not None:
            if len(dataframe) != EXPECTED_TASK_COUNT:
                errors.append(
                    f"Row count: expected {EXPECTED_TASK_COUNT}, got {len(dataframe)}"
                )
            columns_exact = tuple(dataframe.columns) == CANONICAL_SOURCE_COLUMNS
            if not columns_exact:
                errors.append(
                    "Snapshot columns must exactly match canonical source columns: "
                    f"expected {CANONICAL_SOURCE_COLUMNS!r}, "
                    f"got {tuple(dataframe.columns)!r}"
                )
            else:
                try:
                    projection_sha256 = _source_input_projection_sha256(dataframe)
                except Exception as exc:
                    errors.append(
                        f"Unable to normalize source input projection: {exc}"
                    )
                else:
                    if projection_sha256 != CANONICAL_SOURCE_INPUT_SHA256:
                        errors.append(
                            "source input projection differs from pinned source: "
                            f"expected {CANONICAL_SOURCE_INPUT_SHA256}, "
                            f"got {projection_sha256}"
                        )
            missing_columns = _CRITICAL_COLUMNS - set(dataframe.columns)
            if missing_columns:
                errors.append(f"Missing critical columns: {missing_columns}")
            elif PANDAS_AVAILABLE:
                errors.extend(validate_reference_snapshot(dataframe, root))
                errors.extend(
                    validate_needs_files_manifest(
                        dataframe,
                        Path(manifest_path),
                        source_repo=self.SOURCE_REPO,
                        snapshot_root=root,
                    )
                )

            for column in _SUBMITTER_COLUMNS_TEXT:
                if column not in dataframe.columns:
                    continue
                non_empty = sum(
                    isinstance(value, str) and bool(value)
                    for value in dataframe[column]
                )
                if non_empty:
                    errors.append(
                        f"{column} should be empty but {non_empty} rows have content"
                    )

            for column in _SUBMITTER_COLUMNS_LIST:
                if column not in dataframe.columns:
                    continue
                non_empty = sum(
                    _nonempty_submitter_list_value(value)
                    for value in dataframe[column]
                )
                if non_empty:
                    errors.append(
                        f"{column} should be empty but {non_empty} rows have content"
                    )

        reference_dir = root / "reference_files"
        try:
            reference_metadata = reference_dir.lstat()
        except FileNotFoundError:
            errors.append("reference_files/ directory not found")
        except OSError as exc:
            errors.append(f"Unable to inspect reference_files/ directory: {exc}")
        else:
            if stat.S_ISLNK(reference_metadata.st_mode):
                errors.append("reference_files/ directory is a symlink")
            elif not stat.S_ISDIR(reference_metadata.st_mode):
                errors.append("reference_files/ path is not a directory")

        return errors

    def _validate_snapshot(self) -> None:
        """Validate local snapshot integrity."""
        print("\n   Validating local snapshot ...")
        errors = self._snapshot_validation_errors(
            self.local_path,
            self.manifest_path,
        )

        if errors:
            err_str = "\n      ".join(errors)
            raise ValueError(f"Snapshot validation failed:\n      {err_str}")

        print("   Snapshot valid")
        print("   Deliverable columns: cleared")
        print(f"   Manifest: {self.manifest_path}")


# -- Standalone pre-upload validation --------------------------------------


def validate_pre_upload(
    local_path: Optional[str] = None,
    submission_repo_id: Optional[str] = None,
    expected_rows: Optional[int] = None,
) -> List[str]:
    """Pre-upload validation -- call before step6 upload.

    Uses step0_needs_files_manifest.json to check which tasks need files.
    Only tasks with needs_files=true are required to have deliverable_files.

    Args:
        expected_rows: Expected row count. If None, uses EXPECTED_TASK_COUNT (220).
                       Pass sample_size when running in compact/test mode so that
                       row count and deliverable_files checks cover only present tasks.

    Returns:
        List of error strings (empty = all good)
    """
    if not PANDAS_AVAILABLE:
        return ["pandas is required for validation"]

    root = Path(local_path) if local_path else DEFAULT_LOCAL_PATH
    errors: List[str] = []
    expected = expected_rows if expected_rows is not None else EXPECTED_TASK_COUNT
    compact_mode = expected != EXPECTED_TASK_COUNT

    # Find parquet
    data_dir = root / "data"
    parquets = sorted(data_dir.glob("train-*.parquet")) if data_dir.exists() else []
    if not parquets:
        errors.append("No train-*.parquet found")
        return errors

    df = pd.read_parquet(parquets[0])

    # 1. Row count
    if len(df) != expected:
        errors.append(f"Row count: expected {expected}, got {len(df)}")

    # 2. Column set
    for col in ("rubric_json", "rubric_pretty", "task_id", "sector",
                "occupation", "prompt", "deliverable_text", "deliverable_files"):
        if col not in df.columns:
            errors.append(f"Missing column: {col}")

    # 3. Manifest-based deliverable_files check
    #    compact_mode: only validate tasks present in parquet (others intentionally excluded)
    manifest_path = WORKSPACE_DIR / "step0_needs_files_manifest.json"
    if manifest_path.exists() and "deliverable_files" in df.columns:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        present_ids = set(df["task_id"]) if "task_id" in df.columns else set()

        for task_id, info in manifest.get("tasks", {}).items():
            if not info.get("needs_files"):
                continue  # text-only -- no file requirement

            if compact_mode and task_id not in present_ids:
                continue  # intentionally excluded in compact/test mode

            rows = df[df["task_id"] == task_id]
            if len(rows) == 0:
                errors.append(f"task {task_id}: missing from parquet")
                continue

            files = rows.iloc[0].get("deliverable_files")
            if files is None or (hasattr(files, '__len__') and len(files) == 0):
                errors.append(
                    f"task {task_id}: needs_files=true but deliverable_files is empty"
                )
    elif not manifest_path.exists():
        errors.append("needs_files_manifest.json not found -- cannot validate files")

    # 4. task_id unique count
    if "task_id" in df.columns:
        ids = set(df["task_id"])
        if len(ids) != expected:
            errors.append(
                f"Unique task_id count: expected {expected}, got {len(ids)}"
            )

    return errors
