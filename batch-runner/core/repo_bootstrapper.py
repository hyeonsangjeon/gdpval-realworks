"""HuggingFace Repo Bootstrapper -- Step 0

Duplicates a pinned openai/gdpval revision into a user-owned
SUBMISSION_REPO_ID on HuggingFace, but **strips deliverable columns and excludes
deliverable_files/** so only the user's own experiment results are uploaded
later.

Also generates ``step0_needs_files_manifest.json`` from the SOURCE dataset --
a task-level map that records which tasks require file output.

Lifecycle:
    1. Authenticate and classify SUBMISSION_REPO_ID read-only
    2. Reuse a target with data/ or reject a partial target without deletion
    3. For an absent target, prepare and validate the pinned source in a temp dir
    4. Create once and upload the exact frozen snapshot once
    5. On a create race, reclassify read-only without overwrite or deletion
    6. Download the target's exact current HEAD to a fresh snapshot and validate

Usage:
    from core.repo_bootstrapper import RepoBootstrapper

    bs = RepoBootstrapper(submission_repo_id="HyeonSang/exp001_smoke_baseline")
    bs.bootstrap()
"""

import hashlib
import json
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
from core.inference_manifest import (
    canonical_deliverable_path,
    canonical_task_id,
    validate_inference_provenance,
)
from core.needs_files import resolve_needs_files
from core.prompt_classifier import classify_prompt
from core.reference_integrity import (
    ReferenceIntegrityError,
    reference_manifest_record,
    validate_reference_record,
    validate_reference_relative_path,
)
from core.source_identity import (
    SOURCE_PROJECTION_FIELDS,
    ordered_source_projection_sha256,
    source_task_projection_sha256,
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
    "reference_file_urls", "reference_file_hf_uris",
}
MANIFEST_FILENAME = "step0_needs_files_manifest.json"
TARGET_HEAD_FILENAME = "step0_target_head.json"
CANONICAL_PARQUET_FILENAME = "train-00000-of-00001.parquet"
SOURCE_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
CANONICAL_ORDERED_TASK_IDS_SHA256 = (
    "df1fcd6415c55a17e4f39a254aaf0f0f9f2f55c751189f74d2713a873373aa3c"
)
CANONICAL_SOURCE_PROJECTION_SHA256 = (
    "ed8f68a4af63a1094d9bbe0fe0e83398941634a9994b4b2124dc6d0d6fbc5d4a"
)
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
CANONICAL_TARGET_COLUMNS = (*CANONICAL_SOURCE_COLUMNS, "deliverable_text")
CANONICAL_MANIFEST_SHA256_BY_POLICY = {
    "deliverable_only": (
        "463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512"
    ),
    "explicit_boost": (
        "3e8b5974fa151573e4fc33b12f6dbcd62aa82aeb6a5f0593f7eabd1d80e0e1b6"
    ),
    "union": "c118a6b138faf56e6325ee17d075215e0759a979637ba22eef0046c7e99c77ee",
    "intersection": (
        "ddb5324bf1902c04fbd37358ef1527b3ab017004799b66b31bcdd0fe7728567e"
    ),
}

_MANIFEST_TOP_LEVEL_KEYS = {
    "_description",
    "_schema_version",
    "_source",
    "_source_revision",
    "_total_tasks",
    "_ordered_task_ids_sha256",
    "_source_projection_sha256",
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
    "source_projection_sha256",
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


def _column_value(dataframe, field: str, index: int):
    column = dataframe[field]
    return column.iloc[index] if hasattr(column, "iloc") else column[index]


def source_projection_hashes(dataframe) -> List[str]:
    """Hash the ordered source semantics consumed by preparation/evaluation."""
    task_count = len(dataframe["task_id"])
    return [
        source_task_projection_sha256(**{
            field: _column_value(dataframe, field, index)
            for field in SOURCE_PROJECTION_FIELDS
        })
        for index in range(task_count)
    ]


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


def require_canonical_manifest_bytes(raw_manifest: bytes) -> None:
    """Require exact canonical manifest bytes for the active policy."""
    error = _canonical_manifest_digest_error(raw_manifest)
    if error is not None:
        raise ValueError(error)


def load_target_head_identity(path: Path, expected_repo: str) -> str:
    """Load the exact target HEAD proven by Step 0."""
    identity_path = Path(path)
    try:
        metadata = identity_path.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError("Step 0 target HEAD identity is missing") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("Step 0 target HEAD identity is not a regular file")
    try:
        payload = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Step 0 target HEAD identity is malformed") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "repo_id",
        "head",
    }:
        raise RuntimeError("Step 0 target HEAD identity is malformed")
    if payload["schema_version"] != "step0-target-head-v1":
        raise RuntimeError("Step 0 target HEAD identity schema is unsupported")
    if payload["repo_id"] != expected_repo:
        raise RuntimeError("Step 0 target HEAD repository identity mismatch")
    head = payload["head"]
    if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise RuntimeError("Step 0 target HEAD is invalid")
    return head


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
            raise RuntimeError(
                f"Unable to inspect path component {current}: {exc}"
            ) from exc

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
        raise RuntimeError(
            f"Unable to inspect snapshot staging tree {root}: {exc}"
        ) from exc
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
    if type(schema_version) is not int or schema_version != 4:
        errors.append(
            f"Manifest _schema_version must be 4, got {schema_version!r}"
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

    try:
        task_projection_hashes = source_projection_hashes(dataframe)
        computed_source_projection = ordered_source_projection_sha256(
            task_projection_hashes
        )
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"Unable to compute source task projection: {exc}")
        task_projection_hashes = []
        computed_source_projection = None
    if computed_source_projection != CANONICAL_SOURCE_PROJECTION_SHA256:
        errors.append(
            "Snapshot source projection digest must be canonical "
            f"{CANONICAL_SOURCE_PROJECTION_SHA256}, got "
            f"{computed_source_projection!r}"
        )
    if manifest.get("_source_projection_sha256") != (
        CANONICAL_SOURCE_PROJECTION_SHA256
    ):
        errors.append(
            "Manifest _source_projection_sha256 must be "
            f"{CANONICAL_SOURCE_PROJECTION_SHA256}, got "
            f"{manifest.get('_source_projection_sha256')!r}"
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

        task_index = task_ids.index(task_id) if task_id in expected_task_ids else None
        expected_projection = (
            task_projection_hashes[task_index]
            if task_index is not None and task_index < len(task_projection_hashes)
            else None
        )
        if entry.get("source_projection_sha256") != expected_projection:
            errors.append(
                f"Manifest task {task_id!r} source projection differs from snapshot"
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


def validate_cleared_submitter_state(dataframe, local_path: Path) -> List[str]:
    """Reject stale text, file manifests, URLs, URIs, and physical outputs."""
    errors: List[str] = []
    for column in _SUBMITTER_COLUMNS_TEXT:
        if column not in dataframe.columns:
            errors.append(f"Missing cleared submitter column: {column}")
            continue
        invalid = sum(
            not isinstance(value, str) or value != ""
            for value in dataframe[column]
        )
        if invalid:
            errors.append(
                f"{column} must be exact empty strings in all rows; "
                f"invalid={invalid}"
            )
    for column in _SUBMITTER_COLUMNS_LIST:
        if column not in dataframe.columns:
            errors.append(f"Missing cleared submitter column: {column}")
            continue
        invalid = sum(
            value is None
            or isinstance(value, (str, bytes))
            or not hasattr(value, "__len__")
            or len(value) != 0
            for value in dataframe[column]
        )
        if invalid:
            errors.append(
                f"{column} must be empty list-like values in all rows; "
                f"invalid={invalid}"
            )

    deliverable_dir = Path(local_path) / "deliverable_files"
    if deliverable_dir.exists() or deliverable_dir.is_symlink():
        if deliverable_dir.is_symlink() or not deliverable_dir.is_dir():
            errors.append("deliverable_files/ must not be a symlink or file")
        elif any(deliverable_dir.rglob("*")):
            errors.append("deliverable_files/ contains stale submitter output")
    return errors


class RepoBootstrapper:
    """Bootstrap a submission HF dataset repo from a pinned openai/gdpval.

    Steps:
        0. Classify the target read-only; reuse data or reject partial data
        1. For an absent target, prepare and validate the pinned source locally
        2. Create the target once and upload the exact prepared snapshot once
        3. Download the target's exact current HEAD into a fresh local snapshot
        4. Validate the snapshot and manifest
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

        # 3. Restore the source-derived manifest persisted in the snapshot
        self._restore_manifest_from_snapshot()

        # 4. Validate
        self._validate_snapshot()

        print("\n   Bootstrap complete!")
        print(f"      Local snapshot : {self.local_path}")
        print(f"      Manifest       : {self.manifest_path}")
        print(f"{'='*60}")
        return self.local_path

    # -- Remote Repo -------------------------------------------------------

    @staticmethod
    def _is_exact_not_found(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None) == 404

    def _classify_target_read_only(self) -> str:
        """Return absent, data, or partial without mutating the target."""
        try:
            files = self.api.list_repo_files(
                repo_id=self.submission_repo_id,
                repo_type="dataset",
                token=self.token,
            )
        except HfHubHTTPError as exc:
            if self._is_exact_not_found(exc):
                return "absent"
            raise
        return "data" if any(path.startswith("data/") for path in files) else "partial"

    @staticmethod
    def _snapshot_payload_sha256(root: Path) -> str:
        """Hash one regular upload tree by canonical relative path and bytes."""
        source_root = Path(root)
        _validate_regular_tree(source_root)
        digest = hashlib.sha256(b"gdpval-step0-upload-v1\0")
        files = sorted(
            path for path in source_root.rglob("*") if path.is_file()
        )
        for path in files:
            relative = path.relative_to(source_root).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            size = path.stat().st_size
            digest.update(size.to_bytes(8, "big"))
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _remove_sdk_metadata(root: Path) -> None:
        cache = Path(root) / ".cache"
        try:
            metadata = cache.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RuntimeError("Prepared source cache metadata is not a directory")
        shutil.rmtree(cache)

    def _ensure_remote_repo(self) -> None:
        """Reuse a valid target or publish one locally validated snapshot once."""
        self.api.whoami(token=self.token)
        state = self._classify_target_read_only()
        if state == "data":
            print(f"\n   ✅ Repo already exists with data: {self.submission_repo_id}")
            print("   Reusing existing repo (idempotent).")
            return
        if state == "partial":
            raise RuntimeError(
                "Target dataset exists without a data/ snapshot; refusing "
                "automatic repository deletion. Use a new disposable target "
                "or remove the partial repository explicitly."
            )

        print(f"\n   Duplicating {self.SOURCE_REPO} -> {self.submission_repo_id}")
        print("      (deliverable columns cleared, deliverable_files/ excluded)")
        with tempfile.TemporaryDirectory() as tmpdir:
            source_root = Path(tmpdir)
            self._prepare_pinned_source_snapshot(source_root)
            self._remove_sdk_metadata(source_root)
            prepared_digest = self._snapshot_payload_sha256(source_root)
            print("   Downloaded, prepared, and validated in temp dir")

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
                if getattr(response, "status_code", None) != 409:
                    raise
                raced_state = self._classify_target_read_only()
                if raced_state == "data":
                    print("   Concurrent creator published data; reusing target.")
                    return
                if raced_state == "partial":
                    raise RuntimeError(
                        "Target dataset was concurrently created without a data/ "
                        "snapshot; refusing automatic deletion or overwrite."
                    ) from exc
                raise RuntimeError(
                    "Target creation conflict could not be reconciled read-only."
                ) from exc

            print(f"   Repo created: {self.submission_repo_id}")
            if self._snapshot_payload_sha256(source_root) != prepared_digest:
                raise RuntimeError(
                    "Prepared source snapshot changed after validation; target may "
                    "be empty and must not be retried or deleted automatically."
                )
            try:
                self.api.upload_folder(
                    folder_path=source_root,
                    repo_id=self.submission_repo_id,
                    repo_type="dataset",
                    token=self.token,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Target {self.submission_repo_id} was created but its upload "
                    "is incomplete or unverified; do not retry or delete it "
                    "automatically. Use a new disposable target after review."
                ) from exc

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

            for col in _SUBMITTER_COLUMNS_TEXT:
                df[col] = ""

            for col in _SUBMITTER_COLUMNS_LIST:
                df[col] = [[] for _ in range(len(df))]

            df.to_parquet(pq_path, index=False)

        print(f"   Stripped deliverable columns from {len(parquets)} parquet file(s)")

    def _prepare_pinned_source_snapshot(self, root: Path) -> Path:
        """Download only canonical source inputs, then prepare a validated target."""
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
        if [path.name for path in parquets] != [CANONICAL_PARQUET_FILENAME]:
            raise RuntimeError(
                "Pinned source must contain exactly the canonical parquet shard "
                f"{CANONICAL_PARQUET_FILENAME!r}, got "
                f"{[path.name for path in parquets]!r}"
            )
        try:
            dataframe = pd.read_parquet(parquets[0])
        except (ImportError, OSError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Unable to read pinned source parquet: {exc}") from exc

        if tuple(dataframe.columns) != CANONICAL_SOURCE_COLUMNS:
            raise ValueError(
                "Pinned source columns must exactly match the canonical schema: "
                f"expected {CANONICAL_SOURCE_COLUMNS!r}, "
                f"got {tuple(dataframe.columns)!r}"
            )

        declared_reference_paths, declaration_errors = _declared_reference_paths(
            dataframe
        )
        if declaration_errors:
            raise ValueError(
                "Pinned source reference declarations are invalid:\n      "
                + "\n      ".join(declaration_errors)
            )
        snapshot_download(
            repo_id=self.SOURCE_REPO,
            repo_type="dataset",
            revision=SOURCE_REVISION,
            local_dir=source_root,
            token=self.token,
            allow_patterns=declared_reference_paths,
        )
        _validate_regular_tree(source_root)

        physical_reference_paths = _physical_reference_paths(source_root)
        if physical_reference_paths != sorted(declared_reference_paths):
            raise ValueError(
                "Pinned source physical references differ from declarations"
            )

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
        validation_errors = self._snapshot_validation_errors(
            source_root,
            manifest_path,
        )
        if validation_errors:
            raise ValueError(
                "Prepared source snapshot validation failed:\n      "
                + "\n      ".join(validation_errors)
            )
        return manifest_path

    # -- Generate step0_needs_files_manifest.json ---------------------------

    def _generate_manifest_from_dir(
        self,
        dir_path,
        *,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Generate step0_needs_files_manifest.json (V4 schema) from SOURCE parquet.

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
            "_schema_version": 4,
            "_source": self.SOURCE_REPO,
            "_source_revision": SOURCE_REVISION,
            "_total_tasks": len(df),
            "_ordered_task_ids_sha256": ordered_task_ids_digest,
            "_source_projection_sha256": "",
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
        task_projection_hashes = source_projection_hashes(df)
        source_projection_digest = ordered_source_projection_sha256(
            task_projection_hashes
        )
        if source_projection_digest != CANONICAL_SOURCE_PROJECTION_SHA256:
            raise ValueError(
                "Source task projection does not match canonical digest "
                f"{CANONICAL_SOURCE_PROJECTION_SHA256}: "
                f"{source_projection_digest}"
            )
        manifest["_source_projection_sha256"] = source_projection_digest

        policy_counts = {p: 0 for p in NEEDS_FILES_POLICIES_KNOWN}
        confidence_distribution = {
            "explicit": 0,
            "inferred": 0,
            "ambiguous": 0,
            "text_only": 0,
        }

        for row_index, (_, row) in enumerate(df.iterrows()):
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
                "source_projection_sha256": task_projection_hashes[row_index],
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
            with os.fdopen(descriptor, "wb") as destination_file:
                descriptor = -1
                destination_file.write(encoded_manifest)
                destination_file.flush()
                os.fsync(destination_file.fileno())
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
        """Atomically restore the canonical manifest persisted in the snapshot."""
        source = self.local_path / MANIFEST_FILENAME
        _reject_symlink_components(source)
        try:
            metadata = source.lstat()
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise RuntimeError(
                "Downloaded snapshot has no canonical needs-files manifest. "
                "Use a new disposable target instead of regenerating from "
                "stripped data."
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                f"Unable to inspect canonical needs-files manifest: {exc}"
            ) from exc

        if stat.S_ISLNK(metadata.st_mode):
            raise RuntimeError(
                "Canonical needs-files manifest in snapshot must not be a symlink"
            )
        if not stat.S_ISREG(metadata.st_mode):
            raise RuntimeError(
                "Canonical needs-files manifest in snapshot must be a regular file"
            )

        try:
            manifest_bytes = source.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"Unable to read canonical needs-files manifest: {exc}"
            ) from exc
        if digest_error := _canonical_manifest_digest_error(manifest_bytes):
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
                temporary_file.write(manifest_bytes)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary, destination)
        except OSError as exc:
            raise RuntimeError(
                f"Unable to restore canonical needs-files manifest: {exc}"
            ) from exc
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _download_snapshot(self, force: bool = False) -> None:
        """Always download the target's exact current HEAD into fresh staging."""
        del force  # Retained for API compatibility; every call refreshes.

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
            staging = Path(temporary_root) / "snapshot"
            staging.mkdir()

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
                        local_dir=staging,
                        token=self.token,
                        allow_patterns=[
                            ".gitattributes",
                            "README.md",
                            "data/**",
                            "reference_files/**",
                            "deliverable_files/**",
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

            staged_manifest = staging / MANIFEST_FILENAME
            _validate_regular_tree(staging)
            validation_errors = [
                f"target: {error}"
                for error in self._snapshot_validation_errors(
                    staging,
                    staged_manifest,
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
                    os.replace(staging, self.local_path)
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
        identity_path = self.local_path / TARGET_HEAD_FILENAME
        identity_bytes = json.dumps(
            {
                "schema_version": "step0-target-head-v1",
                "repo_id": self.submission_repo_id,
                "head": head,
            },
            sort_keys=True,
        ).encode("utf-8")
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{TARGET_HEAD_FILENAME}.",
            suffix=".tmp",
            dir=self.local_path,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as identity_file:
                descriptor = -1
                identity_file.write(identity_bytes)
                identity_file.flush()
                os.fsync(identity_file.fileno())
            os.replace(temporary, identity_path)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        load_target_head_identity(identity_path, self.submission_repo_id)

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

                parquet_names = [path.name for path in parquets]
                if parquet_names != [CANONICAL_PARQUET_FILENAME]:
                    errors.append(
                        "Snapshot must contain exactly the canonical parquet shard "
                        f"{CANONICAL_PARQUET_FILENAME!r}, got {parquet_names!r}"
                    )
                elif PANDAS_AVAILABLE:
                    try:
                        dataframe = pd.read_parquet(parquets[0])
                    except (ImportError, OSError, TypeError, ValueError) as exc:
                        errors.append(f"Unable to read snapshot parquet: {exc}")

        if dataframe is not None:
            if len(dataframe) != EXPECTED_TASK_COUNT:
                errors.append(
                    f"Row count: expected {EXPECTED_TASK_COUNT}, got {len(dataframe)}"
                )
            if tuple(dataframe.columns) != CANONICAL_TARGET_COLUMNS:
                errors.append(
                    "Snapshot columns must exactly match canonical target columns: "
                    f"expected {CANONICAL_TARGET_COLUMNS!r}, "
                    f"got {tuple(dataframe.columns)!r}"
                )

            missing_columns = _CRITICAL_COLUMNS - set(dataframe.columns)
            if missing_columns:
                errors.append(f"Missing critical columns: {missing_columns}")
            else:
                errors.extend(validate_reference_snapshot(dataframe, root))
                errors.extend(
                    validate_needs_files_manifest(
                        dataframe,
                        Path(manifest_path),
                        source_repo=self.SOURCE_REPO,
                        snapshot_root=root,
                    )
                )
            errors.extend(validate_cleared_submitter_state(dataframe, root))

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


def _list_cell(value, *, column: str, task_id: str) -> tuple[List[str], List[str]]:
    errors: List[str] = []
    if hasattr(value, "tolist"):
        value = value.tolist()
    if value is None:
        return [], errors
    if isinstance(value, (str, bytes)):
        return [], [f"task {task_id}: {column} must be a list"]
    try:
        items = list(value)
    except TypeError:
        return [], [f"task {task_id}: {column} must be a list"]
    if any(not isinstance(item, str) or not item for item in items):
        errors.append(f"task {task_id}: {column} contains an invalid path")
    return items, errors


def validate_deliverable_tree(
    dataframe,
    root: Path,
    *,
    submission_repo_id: Optional[str] = None,
) -> List[str]:
    """Require parquet file declarations to exactly match local upload bytes."""
    errors: List[str] = []
    required_columns = (
        "task_id",
        "deliverable_files",
        "deliverable_file_urls",
        "deliverable_file_hf_uris",
    )
    missing = [column for column in required_columns if column not in dataframe]
    if missing:
        return [f"Missing deliverable manifest columns: {missing}"]

    declared: set[PurePosixPath] = set()
    for _, row in dataframe.iterrows():
        task_id = row["task_id"]
        files, file_errors = _list_cell(
            row["deliverable_files"],
            column="deliverable_files",
            task_id=task_id,
        )
        urls, url_errors = _list_cell(
            row["deliverable_file_urls"],
            column="deliverable_file_urls",
            task_id=task_id,
        )
        uris, uri_errors = _list_cell(
            row["deliverable_file_hf_uris"],
            column="deliverable_file_hf_uris",
            task_id=task_id,
        )
        errors.extend(file_errors + url_errors + uri_errors)
        if len(files) != len(urls) or len(files) != len(uris):
            errors.append(
                f"task {task_id}: deliverable file/URL/URI counts differ"
            )
        for value in files:
            try:
                canonical = canonical_deliverable_path(task_id, value)
            except ValueError as exc:
                errors.append(f"task {task_id}: {exc}")
                continue
            path = PurePosixPath(canonical)
            if path in declared:
                errors.append(f"Duplicate deliverable path: {value}")
                continue
            declared.add(path)
        if submission_repo_id and files:
            from fill_parquet import _build_deliverable_uris

            expected_urls, expected_uris = _build_deliverable_uris(
                files, submission_repo_id
            )
            if urls != expected_urls or uris != expected_uris:
                errors.append(
                    f"task {task_id}: deliverable URL/URI identity mismatch"
                )

    actual: set[PurePosixPath] = set()
    deliverable_root = Path(root) / "deliverable_files"
    if deliverable_root.exists() or deliverable_root.is_symlink():
        if deliverable_root.is_symlink() or not deliverable_root.is_dir():
            errors.append("deliverable_files root is not a regular directory")
            return errors
        for candidate in deliverable_root.rglob("*"):
            relative = PurePosixPath(candidate.relative_to(root).as_posix())
            if candidate.is_symlink():
                errors.append(f"deliverable path is a symlink: {relative}")
            elif candidate.is_file():
                actual.add(relative)
            elif not candidate.is_dir():
                errors.append(f"deliverable path is not regular: {relative}")

    if actual != declared:
        errors.append(
            "deliverable tree differs from parquet manifest: "
            f"missing={sorted(map(str, declared - actual))}, "
            f"extra={sorted(map(str, actual - declared))}"
        )
    return errors


def validate_source_projection_rows(
    dataframe,
    manifest_path: Path,
    *,
    snapshot_root: Optional[Path] = None,
    require_complete: bool = False,
) -> List[str]:
    """Bind rows read for fill/publication to the canonical source manifest."""
    expected_columns = CANONICAL_TARGET_COLUMNS
    if tuple(dataframe.columns) != expected_columns:
        return [
            "Source rows must exactly match canonical columns: "
            f"expected {expected_columns!r}, "
            f"got {tuple(dataframe.columns)!r}"
        ]
    if require_complete:
        return validate_needs_files_manifest(
            dataframe,
            manifest_path,
            source_repo=DATASET_ID,
            snapshot_root=snapshot_root,
        )

    path = Path(manifest_path)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return [f"Canonical needs-files manifest not found: {path}"]
    except OSError as exc:
        return [f"Unable to inspect needs-files manifest {path}: {exc}"]
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        return [f"Needs-files manifest is not a regular file: {path}"]
    try:
        raw_manifest = path.read_bytes()
        manifest = json.loads(raw_manifest)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"Unable to read needs-files manifest {path}: {exc}"]

    errors: List[str] = []
    if digest_error := _canonical_manifest_digest_error(raw_manifest):
        errors.append(digest_error)
    if not isinstance(manifest, dict):
        return [*errors, "Needs-files manifest must be a JSON object"]
    if manifest.get("_schema_version") != 4:
        errors.append("Manifest _schema_version must be 4")
    if manifest.get("_source") != DATASET_ID:
        errors.append(f"Manifest _source must be {DATASET_ID!r}")
    if manifest.get("_source_revision") != SOURCE_REVISION:
        errors.append(f"Manifest _source_revision must be {SOURCE_REVISION!r}")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, dict):
        return [*errors, "Manifest tasks must be an object"]

    try:
        task_ids = [canonical_task_id(value) for value in dataframe["task_id"]]
        projections = source_projection_hashes(dataframe)
    except (KeyError, TypeError, ValueError) as exc:
        return [*errors, f"Unable to compute source task projection: {exc}"]
    if len(task_ids) != len(set(task_ids)):
        errors.append("Source projection rows contain duplicate task IDs")
    for task_id, projection in zip(task_ids, projections, strict=True):
        entry = tasks.get(task_id)
        if not isinstance(entry, dict):
            errors.append(f"task {task_id}: absent from canonical source manifest")
        elif entry.get("source_projection_sha256") != projection:
            errors.append(f"task {task_id}: source projection differs from manifest")
    return errors


def validate_publication_provenance(
    root: Path,
    dataframe,
    *,
    submission_repo_id: str,
    experiment_id: str,
) -> List[str]:
    path = Path(root) / "inference_provenance.json"
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return ["inference_provenance.json not found"]
    except OSError as exc:
        return [f"Unable to inspect inference provenance: {exc}"]
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        return ["inference_provenance.json is not a regular file"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        task_ids = list(dataframe["task_id"])
        validate_inference_provenance(
            payload,
            experiment_id=experiment_id,
            source_repo_id=submission_repo_id,
            task_ids=task_ids,
        )
    except (KeyError, OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"Inference provenance validation failed: {exc}"]
    return []


def validate_pre_upload(
    local_path: Optional[str] = None,
    submission_repo_id: Optional[str] = None,
    expected_rows: Optional[int] = None,
    expected_task_ids: Optional[List[str]] = None,
    expected_submitter_rows: Optional[List[dict]] = None,
    expected_experiment_id: Optional[str] = None,
) -> List[str]:
    """Pre-upload validation -- call before step6 upload.

    Uses step0_needs_files_manifest.json to check which tasks need files.
    Only tasks with needs_files=true are required to have deliverable_files.

    Args:
        expected_rows: Expected row count. If None, uses the prepared task scope
                   when provided, otherwise EXPECTED_TASK_COUNT (220).
        expected_task_ids: Exact ordered task IDs from the validated Step 1/2 scope.
        expected_submitter_rows: Exact task-level submitter projection derived
                     from the validated Step 2 result.
        expected_experiment_id: Exact experiment ID bound to the publication
                 provenance sidecar.

    Returns:
        List of error strings (empty = all good)
    """
    if not PANDAS_AVAILABLE:
        return ["pandas is required for validation"]

    root = Path(local_path) if local_path else DEFAULT_LOCAL_PATH
    errors: List[str] = []
    prepared_task_ids: Optional[List[str]] = None
    if expected_task_ids is not None:
        try:
            prepared_task_ids = [canonical_task_id(value) for value in expected_task_ids]
        except (TypeError, ValueError) as exc:
            errors.append(f"Prepared publication task identity is invalid: {exc}")
        else:
            if not prepared_task_ids or len(prepared_task_ids) != len(
                set(prepared_task_ids)
            ):
                errors.append("Prepared publication task identity is invalid")
                prepared_task_ids = None
    scope_count = len(prepared_task_ids) if prepared_task_ids is not None else None
    expected = (
        expected_rows
        if expected_rows is not None
        else scope_count if scope_count is not None
        else EXPECTED_TASK_COUNT
    )
    if scope_count is not None and expected != scope_count:
        errors.append(
            "Expected row count differs from prepared publication task count: "
            f"rows={expected}, prepared={scope_count}"
        )
    compact_mode = expected != EXPECTED_TASK_COUNT

    # Find parquet
    data_dir = root / "data"
    parquets = sorted(data_dir.glob("train-*.parquet")) if data_dir.exists() else []
    if not parquets:
        errors.append("No train-*.parquet found")
        return errors

    parquet_names = [path.name for path in parquets]
    if parquet_names != [CANONICAL_PARQUET_FILENAME]:
        errors.append(
            "Upload parquet shard set must be exactly "
            f"[{CANONICAL_PARQUET_FILENAME!r}], got {parquet_names!r}"
        )

    df = pd.concat(
        [pd.read_parquet(path) for path in parquets],
        ignore_index=True,
    )

    # 1. Row count
    if len(df) != expected:
        errors.append(f"Row count: expected {expected}, got {len(df)}")
    if prepared_task_ids is not None and "task_id" in df.columns:
        try:
            parquet_task_ids = [canonical_task_id(value) for value in df["task_id"]]
        except (TypeError, ValueError) as exc:
            errors.append(f"Upload parquet task identity is invalid: {exc}")
        else:
            if parquet_task_ids != prepared_task_ids:
                missing = sorted(set(prepared_task_ids) - set(parquet_task_ids))
                unexpected = sorted(set(parquet_task_ids) - set(prepared_task_ids))
                errors.append(
                    "Upload parquet task IDs must exactly match prepared order "
                    f"(missing={missing}, unexpected={unexpected})"
                )

    if expected_submitter_rows is not None:
        if not isinstance(expected_submitter_rows, list):
            errors.append("Expected submitter projection must be a list")
        elif len(expected_submitter_rows) != len(df):
            errors.append(
                "Upload parquet row count differs from result projection: "
                f"parquet={len(df)}, results={len(expected_submitter_rows)}"
            )
        else:
            list_columns = (
                "deliverable_files",
                "deliverable_file_urls",
                "deliverable_file_hf_uris",
            )
            for index, expected_row in enumerate(expected_submitter_rows):
                if not isinstance(expected_row, dict):
                    errors.append(f"Result projection row {index} must be an object")
                    continue
                try:
                    expected_task_id = canonical_task_id(expected_row.get("task_id"))
                except ValueError as exc:
                    errors.append(f"Result projection row {index} is invalid: {exc}")
                    continue
                actual_row = df.iloc[index]
                actual_task_id = actual_row.get("task_id")
                if actual_task_id != expected_task_id:
                    errors.append(
                        f"task {expected_task_id}: parquet result order mismatch"
                    )
                    continue
                expected_text = expected_row.get("deliverable_text")
                if not isinstance(expected_text, str):
                    errors.append(
                        f"task {expected_task_id}: expected deliverable_text is invalid"
                    )
                elif actual_row.get("deliverable_text") != expected_text:
                    errors.append(
                        f"task {expected_task_id}: deliverable_text differs from Step 2"
                    )
                for column in list_columns:
                    expected_values = expected_row.get(column)
                    if not isinstance(expected_values, list) or any(
                        not isinstance(value, str) for value in expected_values
                    ):
                        errors.append(
                            f"task {expected_task_id}: expected {column} is invalid"
                        )
                        continue
                    actual_values, cell_errors = _list_cell(
                        actual_row.get(column),
                        column=column,
                        task_id=expected_task_id,
                    )
                    errors.extend(cell_errors)
                    if not cell_errors and actual_values != expected_values:
                        errors.append(
                            f"task {expected_task_id}: {column} differs from Step 2"
                        )

    # 2. Column set
    for col in ("rubric_json", "rubric_pretty", "task_id", "sector",
                "occupation", "prompt", "deliverable_text", "deliverable_files"):
        if col not in df.columns:
            errors.append(f"Missing column: {col}")

    # 3. Manifest-based deliverable_files check
    #    compact_mode: only validate tasks present in parquet (others intentionally excluded)
    manifest_path = WORKSPACE_DIR / MANIFEST_FILENAME
    errors.extend(validate_source_projection_rows(df, manifest_path))
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
            expected_status = None
            if expected_submitter_rows is not None:
                expected_row = next(
                    (
                        row for row in expected_submitter_rows
                        if isinstance(row, dict) and row.get("task_id") == task_id
                    ),
                    None,
                )
                expected_status = (
                    expected_row.get("status")
                    if isinstance(expected_row, dict)
                    else None
                )
            if (
                expected_status in (None, "success")
                and (
                    files is None
                    or (hasattr(files, '__len__') and len(files) == 0)
                )
            ):
                errors.append(
                    f"task {task_id}: needs_files=true but deliverable_files is empty"
                )
    elif not manifest_path.exists():
        errors.append("needs_files_manifest.json not found -- cannot validate files")

    errors.extend(
        validate_deliverable_tree(
            df,
            root,
            submission_repo_id=submission_repo_id,
        )
    )

    # 4. task_id unique count
    if "task_id" in df.columns:
        ids = set(df["task_id"])
        if len(ids) != expected:
            errors.append(
                f"Unique task_id count: expected {expected}, got {len(ids)}"
            )

    if submission_repo_id and expected_experiment_id and "task_id" in df.columns:
        errors.extend(
            validate_publication_provenance(
                root,
                df,
                submission_repo_id=submission_repo_id,
                experiment_id=expected_experiment_id,
            )
        )
    else:
        errors.append(
            "submission_repo_id and expected_experiment_id are required for provenance validation"
        )

    return errors
