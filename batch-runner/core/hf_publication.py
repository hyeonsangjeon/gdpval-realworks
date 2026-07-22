"""CAS-protected publication of a validated GDPVal result dataset."""

from __future__ import annotations

import json
import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import CommitOperationAdd, CommitOperationDelete, HfApi

from core.inference_manifest import (
    canonical_deliverable_uris,
    canonicalize_inference_results,
)
from core.prepared_fingerprint import FINGERPRINT_RE, validate_prepared_fingerprint
from core.publication_generation import validate_publication_generation
from core.result_fingerprint import (
    RESULT_FINGERPRINT_RE,
    validate_inference_result_fingerprint,
)
from core.repository_identity import validate_hf_dataset_repo_id
from core.repository_identity import validate_experiment_id


INCLUDE_PATTERNS = [
    "README.md",
    "data/train-*.parquet",
    "deliverable_files/**",
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
    "data/**",
    "deliverable_files/**",
    "self_report.json",
]


@dataclass(frozen=True)
class PublicationTaskResult:
    task_id: str
    deliverable_text: str
    deliverable_files: tuple[str, ...]
    deliverable_file_urls: tuple[str, ...]
    deliverable_file_hf_uris: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
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

    def submitter_rows(self) -> list[dict]:
        return [result.as_dict() for result in self.results]


@dataclass(frozen=True)
class PublicationResult:
    oid: str
    plan_sha256: str
    reconciled: bool


@dataclass(frozen=True)
class _PublicationFile:
    path: str
    local_path: Path
    size: int
    sha256: str


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


def load_publication_identity(
    prepared_path: Path,
    inference_path: Path,
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
    publication_results = []
    for result in normalized_results:
        text = result.get("deliverable_text")
        if text is None:
            text = ""
        if not isinstance(text, str):
            raise ValueError("inference deliverable_text must be a string or null")
        files = result["deliverable_files"]
        urls, uris = canonical_deliverable_uris(files, repo_id)
        publication_results.append(PublicationTaskResult(
            task_id=result["task_id"],
            deliverable_text=text,
            deliverable_files=tuple(files),
            deliverable_file_urls=tuple(urls),
            deliverable_file_hf_uris=tuple(uris),
        ))

    return PublicationIdentity(
        experiment_id=experiment_id,
        repo_id=repo_id,
        publication_generation=publication_generation,
        prepared_fingerprint=fingerprint,
        result_fingerprint=result_fingerprint,
        ordered_task_ids=task_ids,
        results=tuple(publication_results),
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


def _publication_additions(root: Path) -> list[CommitOperationAdd]:
    data_root = root / "data"
    try:
        data_metadata = data_root.lstat()
    except FileNotFoundError as exc:
        raise ValueError("publication data directory is missing") from exc
    if stat.S_ISLNK(data_metadata.st_mode) or not stat.S_ISDIR(data_metadata.st_mode):
        raise ValueError("publication data directory is not a regular directory")
    paths = [data_root / "train-00000-of-00001.parquet", root / "self_report.json"]
    if _regular_file(root / "README.md", required=False):
        paths.append(root / "README.md")
    for path in paths[:2]:
        _regular_file(path, required=True)

    deliverable_root = root / "deliverable_files"
    if deliverable_root.exists() or deliverable_root.is_symlink():
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
                child_metadata = child.lstat()
                if stat.S_ISLNK(child_metadata.st_mode) or not stat.S_ISDIR(
                    child_metadata.st_mode
                ):
                    raise ValueError(f"publication deliverable path is not regular: {child}")
            for name in filenames:
                child = directory_path / name
                _regular_file(child, required=True)
                paths.append(child)

    return [
        CommitOperationAdd(
            path_in_repo=path.relative_to(root).as_posix(),
            path_or_fileobj=path,
        )
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
    ]


def _publication_deletions(
    remote_paths: list[str],
    addition_paths: set[str],
) -> list[CommitOperationDelete]:
    stale = sorted(
        path
        for path in remote_paths
        if path == "self_report.json"
        or path.startswith("data/")
        or path.startswith("deliverable_files/")
        if path not in addition_paths
    )
    return [
        CommitOperationDelete(path_in_repo=path, is_folder=False)
        for path in stale
    ]


def _publication_files(
    additions: list[CommitOperationAdd],
) -> tuple[_PublicationFile, ...]:
    records = []
    for operation in additions:
        local_path = Path(operation.path_or_fileobj)
        _regular_file(local_path, required=True)
        size, sha256 = _sha256_file(local_path)
        records.append(_PublicationFile(
            path=operation.path_in_repo,
            local_path=local_path,
            size=size,
            sha256=sha256,
        ))
    return tuple(sorted(records, key=lambda record: record.path))


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
    if _ordered_task_ids(
        meta.get("ordered_task_ids"), "self-report scope"
    ) != identity.ordered_task_ids:
        raise ValueError("self_report.json task order mismatch")
    if _result_task_ids(
        payload, "task_results", "self-report result"
    ) != identity.ordered_task_ids:
        raise ValueError("self_report.json result task set mismatch")


def _validate_self_report(
    upload_root: Path,
    identity: PublicationIdentity,
) -> None:
    _validate_self_report_path(upload_root / "self_report.json", identity)


def _is_managed_publication_path(path: str) -> bool:
    return (
        path == "self_report.json"
        or path.startswith("data/")
        or path.startswith("deliverable_files/")
    )


def _verify_publication(
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
        or marker not in str(getattr(commits[0], "message", ""))
    ):
        raise ValueError("publication commit lineage or plan marker mismatch")

    tree_files = {}
    for entry in client.list_repo_tree(
        repo_id=repo_id,
        repo_type="dataset",
        revision=candidate,
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

    for record in files:
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
            revision=candidate,
            token=token,
        )))
        if _sha256_file(downloaded) != (record.size, record.sha256):
            raise ValueError(f"publication remote file hash mismatch: {record.path}")
        if record.path == "self_report.json":
            _validate_self_report_path(downloaded, identity)

    final_head = getattr(client.repo_info(
        repo_id=repo_id,
        repo_type="dataset",
        revision="main",
        token=token,
    ), "sha", None)
    if final_head != candidate:
        raise ValueError("publication target HEAD advanced during verification")


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
    if not isinstance(identity, PublicationIdentity):
        raise ValueError("expected publication identity is invalid")
    if repo_id != identity.repo_id:
        raise ValueError("publication repository identity mismatch")
    if FINGERPRINT_RE.fullmatch(identity.prepared_fingerprint) is None:
        raise ValueError("expected publication fingerprint is invalid")
    if RESULT_FINGERPRINT_RE.fullmatch(identity.result_fingerprint) is None:
        raise ValueError("expected publication result fingerprint is invalid")
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
    root = Path(upload_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("publication upload root is not a regular directory")
    _validate_self_report(root, identity)

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
    additions = _publication_additions(root)
    addition_paths = {operation.path_in_repo for operation in additions}
    deletions = _publication_deletions(remote_paths, addition_paths)
    files = _publication_files(additions)
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
        _verify_publication(
            client,
            repo_id=repo_id,
            token=token,
            expected_head=expected_head,
            candidate=candidate,
            plan_sha256=plan_sha256,
            files=files,
            identity=identity,
        )
    except Exception as exc:
        raise RuntimeError("publication outcome is unverified") from exc
    return PublicationResult(
        oid=candidate,
        plan_sha256=plan_sha256,
        reconciled=create_error is not None or not response_valid,
    )