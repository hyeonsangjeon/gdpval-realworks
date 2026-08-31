"""CAS-protected publication of a validated GDPVal result dataset."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

from core.inference_manifest import (
    canonical_execution_mode,
    canonical_deliverable_uris,
    canonicalize_azure_ai_routes,
    canonicalize_inference_results,
    validate_execution_route_binding,
    validate_inference_provenance,
)
from core.prepared_fingerprint import FINGERPRINT_RE, validate_prepared_fingerprint
from core.public_error import public_task_error
from core.publication_generation import validate_publication_generation
from core.result_fingerprint import (
    RESULT_FINGERPRINT_RE,
    validate_inference_result_fingerprint,
)
from core.result_projection import project_result_row
from core.cost_projection import COST_LEDGER_PUBLICATION_PATH
from core.cost_projection import project_cost_ledger_reference
from core.repository_identity import validate_hf_dataset_repo_id
from core.repository_identity import validate_experiment_id


INCLUDE_PATTERNS = [
    "README.md",
    "cost_ledger.jsonl",
    "data/train-*.parquet",
    "deliverable_files/**",
    "inference_provenance.json",
    "self_report.json",
]
IGNORE_PATTERNS = [
    ".cache/**",
    "train/**",
    "dataset_dict.json",
    "*.arrow",
    "*.lock",
    "__pycache__/**",
    "state.json",
    "dataset_info.json",
]
DELETE_PATTERNS = [
    "cost_ledger.jsonl",
    "data/**",
    "deliverable_files/**",
    "inference_provenance.json",
    "self_report.json",
    "step2_inference_results.json",
]
#: The audit sidecar publishes under one fixed name. ``self_report.json``
#: declares the path, but the declaration is payload — and managed paths drive
#: remote deletion, so a payload that could name its own managed path could
#: name someone else's file. The name is pinned at the projection layer, where
#: the step that stages the file reads it from too.
COST_LEDGER_PATH = COST_LEDGER_PUBLICATION_PATH
DEFAULT_PUBLICATION_RECEIPT_PATH = Path("workspace/publication_receipt.json")
_PUBLICATION_RECEIPT_FIELDS = frozenset({
    "repo_id",
    "parent_head",
    "publication_revision",
    "plan_sha256",
    "prepared_fingerprint",
    "result_fingerprint",
    "publication_generation",
    "ordered_task_ids",
})
_CLEANUP_COMMIT_TITLE_PREFIX = "Clean relay checkpoint "
_CLEANUP_GENERATION_MARKER_PREFIX = "relay-cleanup-generation: "


@dataclass(frozen=True)
class PublicationFileRecord:
    path: str
    sha256: str
    size: int


_DEFAULT_FILES_COUNT = object()


@dataclass(frozen=True)
class PublicationTaskResult:
    task_id: str
    deliverable_text: str
    deliverable_files: tuple[str, ...]
    deliverable_file_urls: tuple[str, ...]
    deliverable_file_hf_uris: tuple[str, ...]
    deliverable_file_records: tuple[PublicationFileRecord, ...] = ()
    status: str = "success"
    sector: object = ""
    occupation: object = ""
    retried: bool = False
    files_count: object = _DEFAULT_FILES_COUNT
    qa_score: object = None
    qa_passed: object = None
    qa_issues: object = field(default_factory=list)
    qa_suggestion: object = ""
    latency_ms: object = 0
    observability: object = field(default_factory=dict)
    instruction: object = ""
    reference_file_urls: object = field(default_factory=list)
    error: object = None

    def __post_init__(self) -> None:
        if self.files_count is _DEFAULT_FILES_COUNT:
            object.__setattr__(self, "files_count", len(self.deliverable_files))

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "deliverable_text": self.deliverable_text,
            "deliverable_files": list(self.deliverable_files),
            "deliverable_file_urls": list(self.deliverable_file_urls),
            "deliverable_file_hf_uris": list(self.deliverable_file_hf_uris),
        }


@dataclass(frozen=True)
class PublicationIdentity:
    experiment_id: str
    repo_id: str
    publication_generation: str
    prepared_fingerprint: str
    result_fingerprint: str
    ordered_task_ids: tuple[str, ...]
    results: tuple[PublicationTaskResult, ...]
    azure_ai_routes: tuple[dict[str, str], ...] = ()
    execution_mode: str = "subprocess"
    expected_narrative_model: str | None = None
    expected_narrative_reasoning_effort: str | None = None
    expected_narrative_runtime_fingerprint: str | None = None

    def submitter_rows(self) -> list[dict]:
        return [result.as_dict() for result in self.results]


@dataclass(frozen=True)
class PublicationResult:
    oid: str
    plan_sha256: str
    reconciled: bool


@dataclass(frozen=True)
class PublicationReceipt:
    repo_id: str
    parent_head: str
    publication_revision: str
    plan_sha256: str
    prepared_fingerprint: str
    result_fingerprint: str
    publication_generation: str
    ordered_task_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "repo_id": self.repo_id,
            "parent_head": self.parent_head,
            "publication_revision": self.publication_revision,
            "plan_sha256": self.plan_sha256,
            "prepared_fingerprint": self.prepared_fingerprint,
            "result_fingerprint": self.result_fingerprint,
            "publication_generation": self.publication_generation,
            "ordered_task_ids": list(self.ordered_task_ids),
        }


@dataclass(frozen=True)
class _PublicationFile:
    path: str
    stream: BinaryIO
    size: int
    sha256: str


def _assert_no_symlink_ancestors(path: Path) -> Path:
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(
                f"publication path contains a symlink component: {current}"
            )
    return absolute


def _load_json_object(path: Path, label: str) -> dict:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label} is missing: {path}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"{label} must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _load_private_json_object(path: Path, label: str) -> dict:
    absolute = _assert_no_symlink_ancestors(Path(path))
    try:
        path_metadata = absolute.lstat()
    except FileNotFoundError as exc:
        raise ValueError(f"{label} is missing: {absolute}") from exc
    if (
        stat.S_ISLNK(path_metadata.st_mode)
        or not stat.S_ISREG(path_metadata.st_mode)
    ):
        raise ValueError(f"{label} must be a regular file")

    def reject_duplicate_keys(pairs):
        payload = {}
        for key, value in pairs:
            if key in payload:
                raise ValueError(f"{label} contains duplicate JSON keys")
            payload[key] = value
        return payload

    descriptor = None
    try:
        descriptor = os.open(
            absolute,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        metadata = os.fstat(descriptor)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"{label} must be a regular file")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = None
            payload = json.load(stream, object_pairs_hook=reject_duplicate_keys)
    except FileNotFoundError as exc:
        raise ValueError(f"{label} is missing: {absolute}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_private_json(path: Path, payload: dict) -> None:
    absolute = _assert_no_symlink_ancestors(Path(path))
    absolute.parent.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink_ancestors(absolute)
    try:
        metadata = absolute.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("publication receipt path must be a regular file")

    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    descriptor = None
    temporary = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=absolute.parent,
            prefix=f".{absolute.name}.",
        )
        temporary = Path(temporary_name)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            if stream.write(encoded) != len(encoded):
                raise OSError("short write while saving publication receipt")
            stream.flush()
            os.fsync(stream.fileno())
        _assert_no_symlink_ancestors(absolute)
        os.replace(temporary, absolute)
        temporary = None
        _fsync_directory(absolute.parent)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def clear_publication_receipt(
    path: Path = DEFAULT_PUBLICATION_RECEIPT_PATH,
) -> None:
    """Remove a prior receipt without following symlinks."""
    absolute = _assert_no_symlink_ancestors(Path(path))
    try:
        metadata = absolute.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("publication receipt path must be a regular file")
    absolute.unlink()
    _fsync_directory(absolute.parent)


def _ordered_task_ids(value, label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(task_id, str) or not task_id for task_id in value)
        or len(value) != len(set(value))
    ):
        raise ValueError(f"{label} task identity is invalid")
    return tuple(value)


def _result_task_ids(payload: dict, key: str, label: str) -> tuple[str, ...]:
    results = payload.get(key)
    if not isinstance(results, list):
        raise ValueError(f"{label} task set is missing")
    task_ids = [
        result.get("task_id") if isinstance(result, dict) else None
        for result in results
    ]
    return _ordered_task_ids(task_ids, label)


def _validate_publication_receipt_payload(
    payload: dict,
    identity: PublicationIdentity,
) -> PublicationReceipt:
    if set(payload) != _PUBLICATION_RECEIPT_FIELDS:
        raise ValueError("publication receipt schema is invalid")
    try:
        repo_id = validate_hf_dataset_repo_id(payload["repo_id"])
        publication_generation = validate_publication_generation(
            payload["publication_generation"]
        )
    except ValueError as exc:
        raise ValueError("publication receipt identity is invalid") from exc
    parent_head = payload["parent_head"]
    publication_revision = payload["publication_revision"]
    plan_sha256 = payload["plan_sha256"]
    prepared_fingerprint = payload["prepared_fingerprint"]
    result_fingerprint = payload["result_fingerprint"]
    if (
        not isinstance(parent_head, str)
        or re.fullmatch(r"[0-9a-f]{40}", parent_head) is None
        or not isinstance(publication_revision, str)
        or re.fullmatch(r"[0-9a-f]{40}", publication_revision) is None
        or publication_revision == parent_head
        or not isinstance(plan_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", plan_sha256) is None
        or not isinstance(prepared_fingerprint, str)
        or FINGERPRINT_RE.fullmatch(prepared_fingerprint) is None
        or not isinstance(result_fingerprint, str)
        or RESULT_FINGERPRINT_RE.fullmatch(result_fingerprint) is None
    ):
        raise ValueError("publication receipt values are invalid")
    ordered_task_ids = _ordered_task_ids(
        payload["ordered_task_ids"], "publication receipt"
    )
    if (
        repo_id != identity.repo_id
        or prepared_fingerprint != identity.prepared_fingerprint
        or result_fingerprint != identity.result_fingerprint
        or publication_generation != identity.publication_generation
        or ordered_task_ids != identity.ordered_task_ids
    ):
        raise ValueError("publication receipt differs from publication identity")
    return PublicationReceipt(
        repo_id=repo_id,
        parent_head=parent_head,
        publication_revision=publication_revision,
        plan_sha256=plan_sha256,
        prepared_fingerprint=prepared_fingerprint,
        result_fingerprint=result_fingerprint,
        publication_generation=publication_generation,
        ordered_task_ids=ordered_task_ids,
    )


def load_publication_receipt(
    identity: PublicationIdentity,
    path: Path = DEFAULT_PUBLICATION_RECEIPT_PATH,
) -> PublicationReceipt:
    """Load one strict receipt bound to the supplied Step 1/2 identity."""
    if not isinstance(identity, PublicationIdentity):
        raise ValueError("expected publication identity is invalid")
    _validate_publication_identity(identity.repo_id, identity)
    payload = _load_private_json_object(Path(path), "publication receipt")
    return _validate_publication_receipt_payload(payload, identity)


def write_publication_receipt(
    publication: PublicationResult,
    *,
    expected_head: str,
    identity: PublicationIdentity,
    path: Path = DEFAULT_PUBLICATION_RECEIPT_PATH,
) -> PublicationReceipt:
    """Atomically persist a private receipt for one verified publication."""
    if not isinstance(publication, PublicationResult):
        raise ValueError("verified publication result is invalid")
    if not isinstance(identity, PublicationIdentity):
        raise ValueError("expected publication identity is invalid")
    _validate_publication_identity(identity.repo_id, identity)
    payload = {
        "repo_id": identity.repo_id,
        "parent_head": expected_head,
        "publication_revision": publication.oid,
        "plan_sha256": publication.plan_sha256,
        "prepared_fingerprint": identity.prepared_fingerprint,
        "result_fingerprint": identity.result_fingerprint,
        "publication_generation": identity.publication_generation,
        "ordered_task_ids": list(identity.ordered_task_ids),
    }
    receipt = _validate_publication_receipt_payload(payload, identity)
    _write_private_json(Path(path), receipt.as_dict())
    return receipt


def load_publication_identity(
    prepared_path: Path,
    inference_path: Path,
    *,
    expected_narrative_model: str | None = None,
    expected_narrative_reasoning_effort: str | None = None,
    expected_narrative_runtime_fingerprint: str | None = None,
) -> PublicationIdentity:
    """Load one exact Step 1/2 identity or fail before publication."""
    prepared = _load_json_object(Path(prepared_path), "prepared task payload")
    inference = _load_json_object(Path(inference_path), "inference result payload")

    try:
        experiment_id = validate_experiment_id(prepared.get("experiment_id"))
        repo_id = validate_hf_dataset_repo_id(prepared.get("source"))
    except ValueError as exc:
        raise ValueError("prepared publication identity is invalid") from exc
    fingerprint = validate_prepared_fingerprint(prepared)
    publication_generation = validate_publication_generation(
        prepared.get("publication_generation")
    )

    task_scope = prepared.get("task_scope")
    if not isinstance(task_scope, dict):
        raise ValueError("prepared publication task scope is missing")
    task_ids = _ordered_task_ids(task_scope.get("task_ids"), "prepared scope")
    if task_scope.get("expected_count") != len(task_ids):
        raise ValueError("prepared publication task count is invalid")
    if _result_task_ids(prepared, "tasks", "prepared result") != task_ids:
        raise ValueError("prepared publication task set differs from scope")

    try:
        inference_experiment = validate_experiment_id(inference.get("experiment_id"))
        inference_repo = validate_hf_dataset_repo_id(inference.get("source"))
    except ValueError as exc:
        raise ValueError("inference publication identity is invalid") from exc
    if inference_experiment != experiment_id:
        raise ValueError("inference publication experiment identity mismatch")
    if inference_repo != repo_id:
        raise ValueError("inference publication repository identity mismatch")
    if inference.get("prepared_fingerprint") != fingerprint:
        raise ValueError("inference publication fingerprint mismatch")
    if validate_publication_generation(
        inference.get("publication_generation")
    ) != publication_generation:
        raise ValueError("inference publication generation mismatch")
    if _ordered_task_ids(
        inference.get("ordered_task_ids"), "inference scope"
    ) != task_ids:
        raise ValueError("inference publication task order mismatch")
    if _result_task_ids(inference, "results", "inference result") != task_ids:
        raise ValueError("inference publication result task set mismatch")
    result_fingerprint = validate_inference_result_fingerprint(inference)
    normalized_results = canonicalize_inference_results(inference["results"])
    azure_ai_routes = tuple(
        canonicalize_azure_ai_routes(inference.get("azure_ai_routes", []))
    )
    execution_mode = canonical_execution_mode(inference.get("execution_mode"))
    validate_execution_route_binding(execution_mode, list(azure_ai_routes))
    prepared_task_map = {
        task["task_id"]: task
        for task in prepared["tasks"]
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }
    if tuple(prepared_task_map) != task_ids:
        raise ValueError("prepared publication task metadata differs from scope")
    publication_results = []
    for result in normalized_results:
        projected = project_result_row(prepared_task_map[result["task_id"]], result)
        text = result.get("deliverable_text")
        if text is None:
            text = ""
        if not isinstance(text, str):
            raise ValueError("inference deliverable_text must be a string or null")
        status_value = result.get("status")
        if status_value not in {"success", "error", "qa_failed"}:
            raise ValueError("inference publication status is invalid")
        files = result["deliverable_files"]
        raw_records = result.get("deliverable_file_records")
        if not isinstance(raw_records, list) or len(raw_records) != len(files):
            raise ValueError("inference deliverable file records are missing")
        records = []
        for path, record in zip(files, raw_records, strict=True):
            if (
                not isinstance(record, dict)
                or record.get("path") != path
                or not isinstance(record.get("sha256"), str)
                or re.fullmatch(r"[0-9a-f]{64}", record["sha256"]) is None
                or type(record.get("size")) is not int
                or record["size"] < 0
            ):
                raise ValueError("inference deliverable file record is invalid")
            records.append(PublicationFileRecord(
                path=path,
                sha256=record["sha256"],
                size=record["size"],
            ))
        urls, uris = canonical_deliverable_uris(files, repo_id)
        publication_results.append(PublicationTaskResult(
            task_id=result["task_id"],
            status=status_value,
            deliverable_text=text,
            deliverable_files=tuple(files),
            deliverable_file_urls=tuple(urls),
            deliverable_file_hf_uris=tuple(uris),
            deliverable_file_records=tuple(records),
            sector=projected["sector"],
            occupation=projected["occupation"],
            retried=projected["retried"],
            files_count=projected["deliverable_files_count"],
            qa_score=projected["qa_score"],
            qa_passed=projected["qa_passed"],
            qa_issues=projected["qa_issues"],
            qa_suggestion=projected["qa_suggestion"],
            latency_ms=projected["latency_ms"],
            observability=projected["observability"],
            instruction=(projected["instruction"] or "")[:2000],
            reference_file_urls=projected["reference_file_urls"],
            error=projected["error"],
        ))

    return PublicationIdentity(
        experiment_id=experiment_id,
        repo_id=repo_id,
        publication_generation=publication_generation,
        prepared_fingerprint=fingerprint,
        result_fingerprint=result_fingerprint,
        ordered_task_ids=task_ids,
        results=tuple(publication_results),
        azure_ai_routes=azure_ai_routes,
        execution_mode=execution_mode,
        expected_narrative_model=expected_narrative_model,
        expected_narrative_reasoning_effort=expected_narrative_reasoning_effort,
        expected_narrative_runtime_fingerprint=(
            expected_narrative_runtime_fingerprint
        ),
    )


def _regular_file(path: Path, *, required: bool) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        if required:
            raise ValueError(f"required publication file is missing: {path}")
        return False
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"publication file is not regular: {path}")
    return True


def _remote_download_file(path: Path) -> Path:
    """Resolve an HF cache link and require its target to be one regular file."""
    try:
        resolved = path.resolve(strict=True)
        metadata = resolved.stat()
    except (FileNotFoundError, OSError) as exc:
        raise ValueError("publication remote download is unavailable") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("publication remote download target is not a regular file")
    return resolved


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _publication_source_paths(root: Path) -> list[Path]:
    self_report_path = root / "self_report.json"
    try:
        report_metadata = self_report_path.lstat()
    except FileNotFoundError as exc:
        raise ValueError("self_report.json is required for publication") from exc
    if (
        stat.S_ISLNK(report_metadata.st_mode)
        or not stat.S_ISREG(report_metadata.st_mode)
    ):
        raise ValueError("self_report.json must be a regular file")

    provenance_path = root / "inference_provenance.json"
    try:
        provenance_metadata = provenance_path.lstat()
    except FileNotFoundError as exc:
        raise ValueError(
            "inference_provenance.json is required for publication"
        ) from exc
    if (
        stat.S_ISLNK(provenance_metadata.st_mode)
        or not stat.S_ISREG(provenance_metadata.st_mode)
    ):
        raise ValueError("inference_provenance.json must be a regular file")

    data_root = root / "data"
    _assert_no_symlink_ancestors(data_root)
    try:
        data_metadata = data_root.lstat()
    except FileNotFoundError as exc:
        raise ValueError("publication data directory is missing") from exc
    if stat.S_ISLNK(data_metadata.st_mode) or not stat.S_ISDIR(data_metadata.st_mode):
        raise ValueError("publication data directory is not a regular directory")
    paths = [
        data_root / "train-00000-of-00001.parquet",
        provenance_path,
        self_report_path,
    ]
    if _regular_file(root / "README.md", required=False):
        paths.append(root / "README.md")
    if _regular_file(root / COST_LEDGER_PATH, required=False):
        paths.append(root / COST_LEDGER_PATH)
    _regular_file(paths[0], required=True)

    deliverable_root = root / "deliverable_files"
    if deliverable_root.exists() or deliverable_root.is_symlink():
        _assert_no_symlink_ancestors(deliverable_root)
        metadata = deliverable_root.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("publication deliverable root is not a regular directory")
        for directory, dirnames, filenames in os.walk(
            deliverable_root,
            followlinks=False,
        ):
            directory_path = Path(directory)
            for name in dirnames:
                child = directory_path / name
                _assert_no_symlink_ancestors(child)
                child_metadata = child.lstat()
                if stat.S_ISLNK(child_metadata.st_mode) or not stat.S_ISDIR(
                    child_metadata.st_mode
                ):
                    raise ValueError(f"publication deliverable path is not regular: {child}")
            for name in filenames:
                child = directory_path / name
                _assert_no_symlink_ancestors(child)
                _regular_file(child, required=True)
                paths.append(child)

    return sorted(paths, key=lambda item: item.relative_to(root).as_posix())


def _source_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_uid,
        metadata.st_gid,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _stage_publication_file(root: Path, path: Path) -> _PublicationFile:
    _assert_no_symlink_ancestors(path)
    descriptor = None
    held_stream = None
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ValueError(
                f"publication file is not a single-link regular file: {path}"
            )

        held_stream = tempfile.TemporaryFile(mode="w+b")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            if held_stream.write(chunk) != len(chunk):
                raise OSError("short write while staging publication file")
            digest.update(chunk)
            size += len(chunk)

        after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(after.st_mode)
            or after.st_nlink != 1
            or _source_identity(after) != _source_identity(before)
        ):
            raise ValueError(f"publication file changed while staging: {path}")
        held_stream.seek(0)
        return _PublicationFile(
            path=path.relative_to(root).as_posix(),
            stream=held_stream,
            size=size,
            sha256=digest.hexdigest(),
        )
    except OSError as exc:
        if held_stream is not None:
            held_stream.close()
        raise ValueError(f"publication file could not be staged: {path}") from exc
    except Exception:
        if held_stream is not None:
            held_stream.close()
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _publication_additions(
    files: tuple[_PublicationFile, ...],
) -> list[CommitOperationAdd]:
    additions = []
    for record in files:
        record.stream.seek(0)
        additions.append(CommitOperationAdd(
            path_in_repo=record.path,
            path_or_fileobj=record.stream,
        ))
        record.stream.seek(0)
    return additions


def _publication_deletions(
    remote_paths: list[str],
    addition_paths: set[str],
) -> list[CommitOperationDelete]:
    stale = sorted(
        path
        for path in remote_paths
        if _is_managed_publication_path(path)
        if path not in addition_paths
    )
    return [
        CommitOperationDelete(path_in_repo=path, is_folder=False)
        for path in stale
    ]


def _publication_files(root: Path) -> tuple[_PublicationFile, ...]:
    records = []
    try:
        for path in _publication_source_paths(root):
            records.append(_stage_publication_file(root, path))
    except Exception:
        for record in records:
            record.stream.close()
        raise
    return tuple(records)


def _publication_plan_sha256(
    *,
    repo_id: str,
    expected_head: str,
    identity: PublicationIdentity,
    files: tuple[_PublicationFile, ...],
    deletions: list[CommitOperationDelete],
) -> str:
    payload = {
        "repo_id": repo_id,
        "parent_head": expected_head,
        "experiment_id": identity.experiment_id,
        "prepared_fingerprint": identity.prepared_fingerprint,
        "result_fingerprint": identity.result_fingerprint,
        "ordered_task_ids": list(identity.ordered_task_ids),
        "expected_narrative_model": identity.expected_narrative_model,
        "expected_narrative_reasoning_effort": (
            identity.expected_narrative_reasoning_effort
        ),
        "expected_narrative_runtime_fingerprint": (
            identity.expected_narrative_runtime_fingerprint
        ),
        "additions": [
            {"path": record.path, "size": record.size, "sha256": record.sha256}
            for record in files
        ],
        "deletions": sorted(operation.path_in_repo for operation in deletions),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _json_values_equal(left: object, right: object) -> bool:
    try:
        return json.dumps(
            left,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) == json.dumps(
            right,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return False


def _task_report_projection(result: PublicationTaskResult) -> dict:
    return {
        "task_id": result.task_id,
        "sector": result.sector,
        "occupation": result.occupation,
        "status": result.status,
        "retried": result.retried,
        "files_count": result.files_count,
        "qa_score": result.qa_score,
        "qa_passed": result.qa_passed,
        "qa_issues": result.qa_issues,
        "qa_suggestion": result.qa_suggestion,
        "latency_ms": result.latency_ms,
        "observability": result.observability,
        "deliverable_summary": result.deliverable_text[:300],
        "instruction": result.instruction,
        "reference_file_urls": result.reference_file_urls,
        "deliverable_files": list(result.deliverable_files),
    }


def _publication_summary(results: tuple[PublicationTaskResult, ...]) -> dict:
    try:
        total = len(results)
        success_count = sum(result.status == "success" for result in results)
        error_count = sum(result.status == "error" for result in results)
        retried_count = sum(result.retried for result in results)
        scores = [
            result.qa_score for result in results if result.qa_score is not None
        ]
        latencies = [result.latency_ms for result in results if result.latency_ms]
        # Kept identical to ``step6_report._compute_summary`` on purpose: the
        # caller below compares this against the summary block step 6 wrote and
        # refuses to publish on any difference. Nothing scored and nothing timed
        # are absences here for the same reason they are there -- and if only
        # one of the two producers said so, a run where every task errored would
        # stop being publishable rather than start being described honestly.
        return {
            "total_tasks": total,
            "success_count": success_count,
            "success_rate_pct": (
                round(success_count / total * 100, 1) if total else 0.0
            ),
            "error_count": error_count,
            "retried_count": retried_count,
            "avg_qa_score": round(sum(scores) / len(scores), 2) if scores else None,
            "min_qa_score": min(scores) if scores else None,
            "max_qa_score": max(scores) if scores else None,
            "avg_latency_ms": (
                round(sum(latencies) / len(latencies)) if latencies else None
            ),
            "max_latency_ms": round(max(latencies)) if latencies else None,
            "total_latency_ms": round(sum(latencies)) if latencies else None,
        }
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("inference report summary values are invalid") from exc


def _validate_self_report_payload(
    payload: object,
    identity: PublicationIdentity,
) -> None:
    meta = payload.get("meta") if isinstance(payload, dict) else None
    if not isinstance(meta, dict):
        raise ValueError("self_report.json metadata is missing")
    if meta.get("experiment_id") != identity.experiment_id:
        raise ValueError("self_report.json experiment identity mismatch")
    if meta.get("source_repo_id") != identity.repo_id:
        raise ValueError("self_report.json repository identity mismatch")
    if meta.get("publication_generation") != identity.publication_generation:
        raise ValueError("self_report.json publication generation mismatch")
    if meta.get("prepared_fingerprint") != identity.prepared_fingerprint:
        raise ValueError("self_report.json prepared fingerprint mismatch")
    if meta.get("result_fingerprint") != identity.result_fingerprint:
        raise ValueError("self_report.json result fingerprint mismatch")
    if meta.get("publication_plan") != "step7_upload_requested":
        raise ValueError("self_report.json publication plan is not publishable")
    narrative_identity_fields = (
        "narrative_model",
        "narrative_reasoning_effort",
        "narrative_runtime_fingerprint",
    )
    if any(field not in meta for field in narrative_identity_fields):
        raise ValueError("self_report.json narrative identity is incomplete")
    actual_narrative = tuple(meta[field] for field in narrative_identity_fields)
    narrative_fields = (
        "overview",
        "quality_analysis",
        "failure_patterns",
        "recommendations",
    )
    narrative = payload.get("narrative")
    if actual_narrative == (None, None, None):
        if not isinstance(narrative, dict) or any(
            narrative.get(field) != "" for field in narrative_fields
        ):
            raise ValueError("self_report.json model-free narrative is invalid")
    else:
        if any(value is None for value in actual_narrative):
            raise ValueError("self_report.json narrative identity is incomplete")
        expected_narrative = (
            identity.expected_narrative_model,
            identity.expected_narrative_reasoning_effort,
            identity.expected_narrative_runtime_fingerprint,
        )
        if any(value is None for value in expected_narrative):
            raise ValueError("expected publication narrative identity is missing")
        if actual_narrative[0] != expected_narrative[0]:
            raise ValueError("self_report.json narrative model mismatch")
        if actual_narrative[1] != expected_narrative[1]:
            raise ValueError("self_report.json narrative reasoning mismatch")
        if actual_narrative[2] != expected_narrative[2]:
            raise ValueError("self_report.json narrative fingerprint mismatch")
        if not isinstance(narrative, dict) or any(
            not isinstance(narrative.get(field), str)
            or not narrative[field].strip()
            for field in narrative_fields
        ):
            raise ValueError("self_report.json model-backed narrative is invalid")
    if _ordered_task_ids(
        meta.get("ordered_task_ids"), "self-report scope"
    ) != identity.ordered_task_ids:
        raise ValueError("self_report.json task order mismatch")
    if _result_task_ids(
        payload, "task_results", "self-report result"
    ) != identity.ordered_task_ids:
        raise ValueError("self_report.json result task set mismatch")
    if not _json_values_equal(
        payload.get("summary"),
        _publication_summary(identity.results),
    ):
        raise ValueError("self_report.json summary mismatch")
    task_results = payload["task_results"]
    for report_row, expected in zip(
        task_results,
        identity.results,
        strict=True,
    ):
        if not isinstance(report_row, dict):
            raise ValueError("self_report.json result row is invalid")
        for key, value in _task_report_projection(expected).items():
            if key in report_row and _json_values_equal(report_row[key], value):
                continue
            if key == "status":
                raise ValueError("self_report.json result status mismatch")
            if key == "deliverable_summary":
                raise ValueError("self_report.json deliverable summary mismatch")
            if key == "deliverable_files":
                raise ValueError("self_report.json deliverable files mismatch")
            raise ValueError(
                f"self_report.json task result projection mismatch: {key}"
            )

    expected_errors = [
        {
            "task_id": result.task_id,
            "sector": result.sector,
            "occupation": result.occupation,
            **public_task_error(result.error),
        }
        for result in identity.results
        if result.error
    ]
    if not _json_values_equal(payload.get("error_tasks"), expected_errors):
        raise ValueError("self_report.json error task projection mismatch")


def _validate_self_report_path(
    path: Path,
    identity: PublicationIdentity,
) -> None:
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise ValueError("self_report.json is required for publication") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError("self_report.json must be a regular file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("self_report.json must be valid JSON") from exc
    _validate_self_report_payload(payload, identity)


def _validate_self_report(
    files: tuple[_PublicationFile, ...],
    identity: PublicationIdentity,
) -> dict:
    report = next((record for record in files if record.path == "self_report.json"), None)
    if report is None:
        raise ValueError("self_report.json is required for publication")
    try:
        report.stream.seek(0)
        payload = json.load(report.stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("self_report.json must be valid JSON") from exc
    finally:
        report.stream.seek(0)
    _validate_self_report_payload(payload, identity)
    return payload


def _validate_cost_ledger(
    files: tuple[_PublicationFile, ...],
    payload: dict,
) -> None:
    """Match the staged audit sidecar against the digest self_report declares.

    The two must agree in both directions. A declaration with no file leaves
    readers chasing a receipt that was never published; a file with no
    declaration is a payload nobody vouched for, and it would be published
    under a digest nobody checked.
    """
    reference = project_cost_ledger_reference(payload.get("cost_ledger"))
    staged = next(
        (record for record in files if record.path == COST_LEDGER_PATH),
        None,
    )
    if reference is None:
        if staged is not None:
            raise ValueError("cost ledger is present but self_report.json declares none")
        return
    if reference["path"] != COST_LEDGER_PATH:
        raise ValueError(f"cost ledger must be published as {COST_LEDGER_PATH}")
    if staged is None:
        raise ValueError("self_report.json declares a cost ledger that is missing")
    if staged.sha256 != reference["sha256"]:
        raise ValueError("cost ledger digest does not match self_report.json")


def _validate_publication_files(
    files: tuple[_PublicationFile, ...],
    identity: PublicationIdentity,
) -> None:
    _validate_cost_ledger(files, _validate_self_report(files, identity))
    provenance_records = [
        record
        for record in files
        if record.path == "inference_provenance.json"
    ]
    if len(provenance_records) != 1:
        raise ValueError(
            "inference_provenance.json is required for publication"
        )
    provenance = provenance_records[0]
    try:
        provenance.stream.seek(0)
        payload = json.load(provenance.stream)
        validate_inference_provenance(
            payload,
            experiment_id=identity.experiment_id,
            source_repo_id=identity.repo_id,
            task_ids=list(identity.ordered_task_ids),
            prepared_fingerprint=identity.prepared_fingerprint,
            azure_ai_routes=list(identity.azure_ai_routes),
            execution_mode=identity.execution_mode,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("publication inference provenance is invalid") from exc
    finally:
        provenance.stream.seek(0)
    expected_deliverables = {
        record.path: (record.size, record.sha256)
        for result in identity.results
        for record in result.deliverable_file_records
    }
    actual_deliverables = {
        record.path: (record.size, record.sha256)
        for record in files
        if record.path.startswith("deliverable_files/")
    }
    if actual_deliverables != expected_deliverables:
        raise ValueError("publication deliverable bytes differ from Step 2 result")


def _is_managed_publication_path(path: str) -> bool:
    return (
        path in {
            COST_LEDGER_PATH,
            "inference_provenance.json",
            "self_report.json",
            "step2_inference_results.json",
        }
        or path.startswith("data/")
        or path.startswith("deliverable_files/")
    )


def _verify_remote_publication_files(
    client: HfApi,
    *,
    repo_id: str,
    token: str,
    revision: str,
    files: tuple[_PublicationFile, ...],
    identity: PublicationIdentity,
    managed_only: bool,
) -> None:
    tree_files = {}
    for entry in client.list_repo_tree(
        repo_id=repo_id,
        repo_type="dataset",
        revision=revision,
        recursive=True,
        expand=True,
        token=token,
    ):
        path = getattr(entry, "path", None)
        size = getattr(entry, "size", None)
        if not isinstance(path, str) or not isinstance(size, int):
            continue
        if path in tree_files:
            raise ValueError("publication remote tree contains duplicate paths")
        tree_files[path] = entry

    expected_managed = {
        record.path for record in files if _is_managed_publication_path(record.path)
    }
    actual_managed = {
        path for path in tree_files if _is_managed_publication_path(path)
    }
    if actual_managed != expected_managed:
        raise ValueError("publication managed tree differs from local plan")

    records = (
        tuple(record for record in files if _is_managed_publication_path(record.path))
        if managed_only
        else files
    )
    for record in records:
        entry = tree_files.get(record.path)
        if entry is None or getattr(entry, "size", None) != record.size:
            raise ValueError(f"publication remote file size mismatch: {record.path}")
        lfs = getattr(entry, "lfs", None)
        if lfs is not None:
            if (
                getattr(lfs, "size", None) != record.size
                or getattr(lfs, "sha256", None) != record.sha256
            ):
                raise ValueError(f"publication remote LFS hash mismatch: {record.path}")
            if record.path != "self_report.json":
                continue
        downloaded = _remote_download_file(Path(client.hf_hub_download(
            repo_id=repo_id,
            filename=record.path,
            repo_type="dataset",
            revision=revision,
            token=token,
        )))
        if _sha256_file(downloaded) != (record.size, record.sha256):
            raise ValueError(f"publication remote file hash mismatch: {record.path}")
        if record.path == "self_report.json":
            _validate_self_report_path(downloaded, identity)


def _verify_publication_revision(
    client: HfApi,
    *,
    repo_id: str,
    token: str,
    expected_head: str,
    candidate: str,
    plan_sha256: str,
    files: tuple[_PublicationFile, ...],
    identity: PublicationIdentity,
) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", candidate) is None:
        raise ValueError("publication candidate revision is invalid")
    commits = client.list_repo_commits(
        repo_id=repo_id,
        repo_type="dataset",
        revision=candidate,
        token=token,
    )
    marker = f"publication-plan-sha256: {plan_sha256}"
    if (
        len(commits) < 2
        or getattr(commits[0], "commit_id", None) != candidate
        or getattr(commits[1], "commit_id", None) != expected_head
        or marker not in str(getattr(commits[0], "message", "")).splitlines()
    ):
        raise ValueError("publication commit lineage or plan marker mismatch")
    _verify_remote_publication_files(
        client,
        repo_id=repo_id,
        token=token,
        revision=candidate,
        files=files,
        identity=identity,
        managed_only=False,
    )


def _validate_publication_identity(
    repo_id: str,
    identity: PublicationIdentity,
) -> None:
    if not isinstance(identity, PublicationIdentity):
        raise ValueError("expected publication identity is invalid")
    if repo_id != identity.repo_id:
        raise ValueError("publication repository identity mismatch")
    try:
        validate_experiment_id(identity.experiment_id)
        validate_publication_generation(identity.publication_generation)
    except ValueError as exc:
        raise ValueError("expected publication identity is invalid") from exc
    if FINGERPRINT_RE.fullmatch(identity.prepared_fingerprint) is None:
        raise ValueError("expected publication fingerprint is invalid")
    if RESULT_FINGERPRINT_RE.fullmatch(identity.result_fingerprint) is None:
        raise ValueError("expected publication result fingerprint is invalid")
    validate_execution_route_binding(
        identity.execution_mode,
        list(identity.azure_ai_routes),
    )
    narrative_identity = (
        identity.expected_narrative_model,
        identity.expected_narrative_reasoning_effort,
        identity.expected_narrative_runtime_fingerprint,
    )
    if narrative_identity != (None, None, None):
        if (
            not isinstance(narrative_identity[0], str)
            or not narrative_identity[0]
            or not isinstance(narrative_identity[1], str)
            or not narrative_identity[1]
            or not isinstance(narrative_identity[2], str)
            or re.fullmatch(r"[0-9a-f]{64}", narrative_identity[2]) is None
        ):
            raise ValueError("expected publication narrative identity is invalid")
    if (
        not isinstance(identity.results, tuple)
        or any(
            not isinstance(result, PublicationTaskResult)
            for result in identity.results
        )
        or tuple(result.task_id for result in identity.results)
        != identity.ordered_task_ids
    ):
        raise ValueError("expected publication result projection is invalid")


def publish_dataset(
    repo_id: str,
    upload_root: Path,
    *,
    token: str,
    expected_head: str,
    identity: PublicationIdentity,
    api: HfApi | None = None,
):
    """Publish against the exact Step 0 HEAD or fail without mutation."""
    repo_id = validate_hf_dataset_repo_id(repo_id)
    if not isinstance(expected_head, str) or re.fullmatch(
        r"[0-9a-f]{40}", expected_head
    ) is None:
        raise ValueError("expected publication parent HEAD is invalid")
    _validate_publication_identity(repo_id, identity)
    root = _assert_no_symlink_ancestors(Path(upload_root))
    if not root.is_dir():
        raise ValueError("publication upload root is not a regular directory")
    files = _publication_files(root)
    try:
        _validate_publication_files(files, identity)
        additions = _publication_additions(files)

        client = api or HfApi(token=token)
        remote = client.repo_info(
            repo_id=repo_id,
            repo_type="dataset",
            revision="main",
            token=token,
        )
        current_head = getattr(remote, "sha", None)
        if current_head != expected_head:
            raise RuntimeError(
                "publication target HEAD changed since Step 0 validation"
            )
        remote_paths = client.list_repo_files(
            repo_id=repo_id,
            repo_type="dataset",
            revision=expected_head,
            token=token,
        )
        addition_paths = {operation.path_in_repo for operation in additions}
        deletions = _publication_deletions(remote_paths, addition_paths)
        plan_sha256 = _publication_plan_sha256(
            repo_id=repo_id,
            expected_head=expected_head,
            identity=identity,
            files=files,
            deletions=deletions,
        )
        marker = f"publication-plan-sha256: {plan_sha256}"
        response = None
        create_error = None
        try:
            response = client.create_commit(
                repo_id=repo_id,
                repo_type="dataset",
                revision="main",
                parent_commit=expected_head,
                token=token,
                operations=[*deletions, *additions],
                commit_message="Update dataset with experiment results",
                commit_description=marker,
            )
        except Exception as exc:
            create_error = exc
    finally:
        for record in files:
            record.stream.close()

    response_oid = getattr(response, "oid", None)
    response_valid = (
        isinstance(response_oid, str)
        and re.fullmatch(r"[0-9a-f]{40}", response_oid) is not None
    )
    try:
        observed_head = getattr(client.repo_info(
            repo_id=repo_id,
            repo_type="dataset",
            revision="main",
            token=token,
        ), "sha", None)
    except Exception as exc:
        raise RuntimeError("publication outcome is unverified") from exc
    if observed_head == expected_head:
        if create_error is not None:
            raise create_error
        raise RuntimeError("publication commit response is invalid")
    candidate = response_oid if response_valid else observed_head
    try:
        _verify_publication_revision(
            client,
            repo_id=repo_id,
            token=token,
            expected_head=expected_head,
            candidate=candidate,
            plan_sha256=plan_sha256,
            files=files,
            identity=identity,
        )
        final_head = getattr(client.repo_info(
            repo_id=repo_id,
            repo_type="dataset",
            revision="main",
            token=token,
        ), "sha", None)
        if final_head != candidate:
            raise ValueError("publication target HEAD advanced during verification")
    except Exception as exc:
        raise RuntimeError("publication outcome is unverified") from exc
    return PublicationResult(
        oid=candidate,
        plan_sha256=plan_sha256,
        reconciled=create_error is not None or not response_valid,
    )


def publish_dataset_with_receipt(
    repo_id: str,
    upload_root: Path,
    *,
    token: str,
    expected_head: str,
    identity: PublicationIdentity,
    receipt_path: Path = DEFAULT_PUBLICATION_RECEIPT_PATH,
    api: HfApi | None = None,
) -> PublicationResult:
    """Publish once and persist a receipt only after remote verification."""
    clear_publication_receipt(Path(receipt_path))
    publication = publish_dataset(
        repo_id,
        upload_root,
        token=token,
        expected_head=expected_head,
        identity=identity,
        api=api,
    )
    write_publication_receipt(
        publication,
        expected_head=expected_head,
        identity=identity,
        path=receipt_path,
    )
    return publication


def verify_publication_finality(
    repo_id: str,
    upload_root: Path,
    *,
    token: str,
    identity: PublicationIdentity,
    expected_generation: str | None = None,
    receipt_path: Path = DEFAULT_PUBLICATION_RECEIPT_PATH,
    api: HfApi | None = None,
) -> str:
    """Verify immutable publication bytes and the exact final main HEAD."""
    repo_id = validate_hf_dataset_repo_id(repo_id)
    _validate_publication_identity(repo_id, identity)
    if expected_generation is not None and (
        not isinstance(expected_generation, str)
        or re.fullmatch(r"[0-9a-f]{64}", expected_generation) is None
    ):
        raise ValueError("relay cleanup generation is invalid")
    receipt = load_publication_receipt(identity, Path(receipt_path))
    if receipt.repo_id != repo_id:
        raise ValueError("publication receipt repository mismatch")
    root = _assert_no_symlink_ancestors(Path(upload_root))
    if not root.is_dir():
        raise ValueError("publication upload root is not a regular directory")
    files = _publication_files(root)
    try:
        _validate_publication_files(files, identity)
        client = api or HfApi(token=token)
        try:
            remote_paths = client.list_repo_files(
                repo_id=repo_id,
                repo_type="dataset",
                revision=receipt.parent_head,
                token=token,
            )
            if (
                not isinstance(remote_paths, list)
                or any(not isinstance(path, str) for path in remote_paths)
                or len(remote_paths) != len(set(remote_paths))
            ):
                raise ValueError("publication parent tree is invalid")
            addition_paths = {record.path for record in files}
            deletions = _publication_deletions(remote_paths, addition_paths)
            plan_sha256 = _publication_plan_sha256(
                repo_id=repo_id,
                expected_head=receipt.parent_head,
                identity=identity,
                files=files,
                deletions=deletions,
            )
            if plan_sha256 != receipt.plan_sha256:
                raise ValueError("publication receipt plan differs from local bytes")
            _verify_publication_revision(
                client,
                repo_id=repo_id,
                token=token,
                expected_head=receipt.parent_head,
                candidate=receipt.publication_revision,
                plan_sha256=receipt.plan_sha256,
                files=files,
                identity=identity,
            )

            final_head = getattr(client.repo_info(
                repo_id=repo_id,
                repo_type="dataset",
                revision="main",
                token=token,
            ), "sha", None)
            if not isinstance(final_head, str) or re.fullmatch(
                r"[0-9a-f]{40}", final_head
            ) is None:
                raise ValueError("publication final HEAD is invalid")
            if expected_generation is None:
                if final_head != receipt.publication_revision:
                    raise ValueError("publication final HEAD is not the publication")
            else:
                commits = list(client.list_repo_commits(
                    repo_id=repo_id,
                    repo_type="dataset",
                    revision=final_head,
                    token=token,
                ))
                cleanup_title = (
                    f"{_CLEANUP_COMMIT_TITLE_PREFIX}"
                    f"{expected_generation[:12]}"
                )
                cleanup_description = (
                    f"{_CLEANUP_GENERATION_MARKER_PREFIX}"
                    f"{expected_generation}"
                )
                if (
                    len(commits) < 2
                    or getattr(commits[0], "commit_id", None) != final_head
                    or getattr(commits[1], "commit_id", None)
                    != receipt.publication_revision
                    or getattr(commits[0], "title", None) != cleanup_title
                    or getattr(commits[0], "message", None)
                    != cleanup_description
                ):
                    raise ValueError(
                        "relay cleanup commit lineage or generation mismatch"
                    )

            if expected_generation is not None:
                _verify_remote_publication_files(
                    client,
                    repo_id=repo_id,
                    token=token,
                    revision=final_head,
                    files=files,
                    identity=identity,
                    managed_only=False,
                )
            confirmed_head = getattr(client.repo_info(
                repo_id=repo_id,
                repo_type="dataset",
                revision="main",
                token=token,
            ), "sha", None)
            if confirmed_head != final_head:
                raise ValueError(
                    "publication final HEAD advanced during verification"
                )
        except Exception as exc:
            raise RuntimeError("publication finality is unverified") from exc
    finally:
        for record in files:
            record.stream.close()
    return final_head