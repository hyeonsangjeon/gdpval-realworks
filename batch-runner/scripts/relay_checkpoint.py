#!/usr/bin/env python3
"""Fail-closed Hugging Face checkpoint transport for batch relay legs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable

from huggingface_hub import (
    CommitOperationDelete,
    HfApi,
    hf_hub_download,
    snapshot_download,
)
from huggingface_hub.utils import HfHubHTTPError

from core.repository_identity import validate_hf_dataset_repo_id


CHECKPOINT_SCHEMA = "relay-checkpoint-v2"
REMOTE_LINEAGES = "_checkpoint/lineages"
LOCAL_PROGRESS = Path("workspace/step2_inference_progress.json")
LOCAL_UPLOAD = Path("workspace/upload")
SANDBOX_IMAGE_PATTERN = re.compile(
    r"ghcr\.io/hyeonsangjeon/gdpval-sandbox@sha256:[0-9a-f]{64}"
)


def _validate_sandbox_image_digest(value: str) -> str:
    if not isinstance(value, str) or (
        value and SANDBOX_IMAGE_PATTERN.fullmatch(value) is None
    ):
        raise ValueError("relay sandbox image digest is invalid")
    return value


def _lineage_root(source_sha: str, lineage_id: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("relay checkpoint source SHA is invalid")
    if not isinstance(lineage_id, str) or not lineage_id:
        raise ValueError("relay checkpoint lineage is invalid")
    key = hashlib.sha256(f"{source_sha}\0{lineage_id}".encode("utf-8")).hexdigest()
    return f"{REMOTE_LINEAGES}/{key}"


def _marker_path(source_sha: str, lineage_id: str) -> str:
    return f"{_lineage_root(source_sha, lineage_id)}/current.json"


def _generation_root(source_sha: str, lineage_id: str, generation: str) -> str:
    return f"{_lineage_root(source_sha, lineage_id)}/generations/{generation}"


def _load_progress(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("relay progress checkpoint is malformed")
    return payload


def _validate_complete_task_set(payload: dict) -> None:
    ordered_task_ids = payload.get("ordered_task_ids")
    if (
        not isinstance(ordered_task_ids, list)
        or not ordered_task_ids
        or any(not isinstance(task_id, str) or not task_id for task_id in ordered_task_ids)
        or len(ordered_task_ids) != len(set(ordered_task_ids))
    ):
        raise ValueError("relay checkpoint ordered task identity is invalid")
    result_ids = []
    for result in payload["results"]:
        if not isinstance(result, dict) or not isinstance(result.get("task_id"), str):
            raise ValueError("relay checkpoint result task identity is invalid")
        result_ids.append(result["task_id"])
    if result_ids != ordered_task_ids:
        raise ValueError("relay checkpoint result task IDs differ from ordered task set")


def _required_deliverables(payload: dict) -> tuple[PurePosixPath, ...]:
    required: set[PurePosixPath] = set()
    for result in payload["results"]:
        if not isinstance(result, dict):
            raise ValueError("relay progress result is malformed")
        files = result.get("deliverable_files", [])
        if files is None:
            files = []
        if not isinstance(files, list):
            raise ValueError("relay deliverable manifest is malformed")
        for value in files:
            if not isinstance(value, str) or not value:
                raise ValueError("relay deliverable path is malformed")
            path = PurePosixPath(value)
            if (
                path.is_absolute()
                or not path.parts
                or path.parts[0] != "deliverable_files"
                or any(part in {"", ".", ".."} for part in path.parts)
            ):
                raise ValueError("relay deliverable path escapes upload root")
            if path in required:
                raise ValueError("relay deliverable path is duplicated")
            required.add(path)
    return tuple(sorted(required, key=str))


def _regular_file(upload_root: Path, relative: PurePosixPath) -> Path:
    resolved_root = upload_root.resolve()
    candidate = upload_root.joinpath(*relative.parts)
    current = upload_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"relay deliverable path is a symlink: {relative}")
    if not candidate.resolve().is_relative_to(resolved_root):
        raise ValueError("relay deliverable path escapes upload root")
    if not candidate.is_file():
        raise FileNotFoundError(f"relay deliverable is missing: {relative}")
    return candidate


def _validate_exact_local_deliverables(
    upload_root: Path,
    required: Iterable[PurePosixPath],
) -> tuple[Path, ...]:
    expected = tuple(required)
    expected_set = set(expected)
    deliverable_root = upload_root / "deliverable_files"
    actual: set[PurePosixPath] = set()
    if deliverable_root.exists():
        if deliverable_root.is_symlink() or not deliverable_root.is_dir():
            raise ValueError("relay deliverable root is not a regular directory")
        for candidate in deliverable_root.rglob("*"):
            relative = PurePosixPath(candidate.relative_to(upload_root).as_posix())
            if candidate.is_symlink():
                raise ValueError(f"relay deliverable path is a symlink: {relative}")
            if candidate.is_file():
                actual.add(relative)
    if actual != expected_set:
        missing = sorted(map(str, expected_set - actual))
        extra = sorted(map(str, actual - expected_set))
        raise ValueError(
            f"relay deliverable tree mismatch: missing={missing}, extra={extra}"
        )
    return tuple(_regular_file(upload_root, path) for path in expected)


def _file_record(path: Path, relative: PurePosixPath) -> dict:
    content = path.read_bytes()
    return {
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }


def _generation(
    progress: bytes,
    records: list[dict],
    sandbox_image_digest: str = "",
) -> str:
    identity = {
        "progress_sha256": hashlib.sha256(progress).hexdigest(),
        "deliverables": records,
        "sandbox_image_digest": _validate_sandbox_image_digest(
            sandbox_image_digest
        ),
    }
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _commit_oid(info: object) -> str:
    oid = getattr(info, "oid", None)
    if not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{40}", oid):
        raise ValueError("HF checkpoint commit did not return a full revision")
    return oid


def _marker(data: bytes) -> dict:
    payload = json.loads(data)
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "generation",
        "payload_revision",
        "source_sha",
        "lineage_id",
        "sandbox_image_digest",
        "progress",
        "deliverables",
    }:
        raise ValueError("relay checkpoint marker is malformed")
    if payload["schema_version"] != CHECKPOINT_SCHEMA:
        raise ValueError("relay checkpoint marker schema is unsupported")
    if not re.fullmatch(r"[0-9a-f]{64}", payload.get("generation", "")):
        raise ValueError("relay checkpoint generation is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", payload.get("payload_revision", "")):
        raise ValueError("relay checkpoint revision is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", payload.get("source_sha", "")):
        raise ValueError("relay checkpoint source SHA is invalid")
    if not isinstance(payload.get("lineage_id"), str) or not payload["lineage_id"]:
        raise ValueError("relay checkpoint lineage is invalid")
    _validate_sandbox_image_digest(payload.get("sandbox_image_digest"))
    progress = payload.get("progress")
    deliverables = payload.get("deliverables")
    if not isinstance(progress, dict) or not isinstance(deliverables, list):
        raise ValueError("relay checkpoint marker manifest is malformed")
    for record in [progress, *deliverables]:
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "size"}:
            raise ValueError("relay checkpoint file record is malformed")
        if (
            not isinstance(record["path"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
            or not isinstance(record["size"], int)
            or record["size"] < 0
        ):
            raise ValueError("relay checkpoint file record is invalid")
    if progress["path"] != "progress.json":
        raise ValueError("relay checkpoint progress path is invalid")
    deliverable_paths = [record["path"] for record in deliverables]
    if deliverable_paths != sorted(deliverable_paths) or len(deliverable_paths) != len(
        set(deliverable_paths)
    ):
        raise ValueError("relay checkpoint deliverable records are unordered or duplicated")
    _required_deliverables(
        {"results": [{"deliverable_files": deliverable_paths}]}
    )
    return payload


def _verify_marker_identity(
    marker: dict,
    *,
    source_sha: str,
    lineage_id: str,
    sandbox_image_digest: str,
) -> None:
    if marker["source_sha"] != source_sha or marker["lineage_id"] != lineage_id:
        raise ValueError("relay checkpoint source or lineage mismatch")
    if marker["sandbox_image_digest"] != _validate_sandbox_image_digest(
        sandbox_image_digest
    ):
        raise ValueError("relay checkpoint sandbox image digest mismatch")


def _verify_record(path: Path, record: dict) -> None:
    content = path.read_bytes()
    if len(content) != record["size"] or hashlib.sha256(content).hexdigest() != record["sha256"]:
        raise ValueError(f"relay checkpoint file hash mismatch: {record['path']}")


def _verify_remote_records(
    client: HfApi,
    *,
    repo_id: str,
    token: str,
    revision: str,
    remote_root: str,
    records: list[dict],
) -> Path:
    remote_paths = [f"{remote_root}/{record['path']}" for record in records]
    actual_remote = sorted(
        path
        for path in client.list_repo_files(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
            token=token,
        )
        if path.startswith(f"{remote_root}/")
    )
    if actual_remote != sorted(remote_paths):
        raise ValueError(
            "relay checkpoint payload commit is incomplete or contains extras"
        )
    snapshot = Path(
        snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            revision=revision,
            allow_patterns=remote_paths,
            token=token,
        )
    )
    verified_root = snapshot / remote_root
    for record in records:
        _verify_record(verified_root / record["path"], record)
    return verified_root


def verify_write_access(repo_id: str, *, token: str, api: HfApi | None = None) -> None:
    repo_id = validate_hf_dataset_repo_id(repo_id)
    (api or HfApi(token=token)).auth_check(
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
        write=True,
    )
    print(f"Relay target is writable: {repo_id}")


def restore_checkpoint(
    repo_id: str,
    *,
    token: str,
    source_sha: str,
    lineage_id: str,
    sandbox_image_digest: str = "",
    progress_path: Path = LOCAL_PROGRESS,
    upload_root: Path = LOCAL_UPLOAD,
    api: HfApi | None = None,
) -> None:
    repo_id = validate_hf_dataset_repo_id(repo_id)
    marker_remote = _marker_path(source_sha, lineage_id)
    with tempfile.TemporaryDirectory(prefix="gdpval-relay-") as temp_dir:
        staging = Path(temp_dir)
        marker_path = Path(
            hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=marker_remote,
                token=token,
            )
        )
        marker = _marker(marker_path.read_bytes())
        _verify_marker_identity(
            marker,
            source_sha=source_sha,
            lineage_id=lineage_id,
            sandbox_image_digest=sandbox_image_digest,
        )
        records = [marker["progress"], *marker["deliverables"]]
        generation_remote = _generation_root(
            source_sha, lineage_id, marker["generation"]
        )
        remote_paths = [f"{generation_remote}/{record['path']}" for record in records]
        client = api or HfApi(token=token)
        generation_prefix = f"{generation_remote}/"
        actual_remote = sorted(
            path
            for path in client.list_repo_files(
                repo_id=repo_id,
                repo_type="dataset",
                revision=marker["payload_revision"],
                token=token,
            )
            if path.startswith(generation_prefix)
        )
        if actual_remote != sorted(remote_paths):
            raise ValueError("relay checkpoint remote generation tree mismatch")
        snapshot = Path(
            snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                revision=marker["payload_revision"],
                allow_patterns=remote_paths,
                token=token,
            )
        )
        generation_root = snapshot / generation_remote
        staged_progress = generation_root / marker["progress"]["path"]
        _verify_record(staged_progress, marker["progress"])
        payload = _load_progress(staged_progress)
        _validate_complete_task_set(payload)
        required = _required_deliverables(payload)
        if [path.as_posix() for path in required] != [
            record["path"] for record in marker["deliverables"]
        ]:
            raise ValueError("relay checkpoint marker differs from progress manifest")
        staged_upload = staging / "upload"
        for relative, record in zip(required, marker["deliverables"], strict=True):
            source = generation_root / record["path"]
            _verify_record(source, record)
            destination = staged_upload.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        _validate_exact_local_deliverables(staged_upload, required)
        records_without_remote = [
            {key: record[key] for key in ("path", "sha256", "size")}
            for record in marker["deliverables"]
        ]
        if _generation(
            staged_progress.read_bytes(),
            records_without_remote,
            marker["sandbox_image_digest"],
        ) != marker["generation"]:
            raise ValueError("relay checkpoint generation hash mismatch")

        destination = upload_root / "deliverable_files"
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise ValueError("relay deliverable destination is not a directory")
            shutil.rmtree(destination)
        if required:
            shutil.copytree(staged_upload / "deliverable_files", destination)
        _validate_exact_local_deliverables(upload_root, required)
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        progress_tmp = progress_path.with_suffix(".json.tmp")
        shutil.copy2(staged_progress, progress_tmp)
        progress_tmp.replace(progress_path)
    print(f"Relay checkpoint restored from {repo_id}")


def upload_checkpoint(
    repo_id: str,
    *,
    token: str,
    source_sha: str,
    sandbox_image_digest: str = "",
    progress_path: Path = LOCAL_PROGRESS,
    upload_root: Path = LOCAL_UPLOAD,
    api: HfApi | None = None,
) -> None:
    repo_id = validate_hf_dataset_repo_id(repo_id)
    payload = _load_progress(progress_path)
    _validate_complete_task_set(payload)
    lineage_id = payload.get("run_id")
    if not isinstance(lineage_id, str) or not lineage_id:
        raise ValueError("relay progress lineage is missing")
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("relay checkpoint source SHA is invalid")
    sandbox_image_digest = _validate_sandbox_image_digest(sandbox_image_digest)
    required = _required_deliverables(payload)
    local_files = _validate_exact_local_deliverables(upload_root, required)
    records = [
        _file_record(path, relative)
        for path, relative in zip(local_files, required, strict=True)
    ]
    progress = progress_path.read_bytes()
    generation = _generation(progress, records, sandbox_image_digest)
    marker_remote = _marker_path(source_sha, lineage_id)
    generation_root = _generation_root(source_sha, lineage_id, generation)
    client = api or HfApi(token=token)
    with tempfile.TemporaryDirectory(prefix="gdpval-relay-upload-") as temp_dir:
        staging = Path(temp_dir)
        (staging / "progress.json").write_bytes(progress)
        for source, relative in zip(local_files, required, strict=True):
            destination = staging.joinpath(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        payload_commit = client.upload_folder(
            folder_path=str(staging),
            path_in_repo=generation_root,
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
            commit_message=f"Upload relay checkpoint generation {generation[:12]}",
        )
    payload_revision = _commit_oid(payload_commit)
    progress_record = {
        "path": "progress.json",
        "sha256": hashlib.sha256(progress).hexdigest(),
        "size": len(progress),
    }
    marker_payload = {
        "schema_version": CHECKPOINT_SCHEMA,
        "generation": generation,
        "payload_revision": payload_revision,
        "source_sha": source_sha,
        "lineage_id": lineage_id,
        "sandbox_image_digest": sandbox_image_digest,
        "progress": progress_record,
        "deliverables": records,
    }
    marker = json.dumps(
        marker_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    verified_root = _verify_remote_records(
        client,
        repo_id=repo_id,
        token=token,
        revision=payload_revision,
        remote_root=generation_root,
        records=[progress_record, *records],
    )
    if _generation(
        (verified_root / "progress.json").read_bytes(),
        records,
        sandbox_image_digest,
    ) != generation:
        raise ValueError("relay checkpoint uploaded generation hash mismatch")
    client.upload_file(
        path_or_fileobj=marker,
        path_in_repo=marker_remote,
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
        parent_commit=payload_revision,
        commit_message=f"Advance relay checkpoint to {generation[:12]}",
    )
    print(f"Relay checkpoint {generation[:12]} uploaded to {repo_id}")


def _repo_head(client: HfApi, *, repo_id: str, token: str) -> str:
    head = client.repo_info(
        repo_id=repo_id,
        repo_type="dataset",
        token=token,
    ).sha
    if not isinstance(head, str) or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("HF checkpoint cleanup did not resolve a full HEAD")
    return head


def _marker_at_head_or_confirm_absent(
    client: HfApi,
    *,
    repo_id: str,
    token: str,
    lineage_root: str,
    marker_remote: str,
    head: str,
) -> Path | None:
    try:
        return Path(
            hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=marker_remote,
                revision=head,
                token=token,
            )
        )
    except HfHubHTTPError as exc:
        response = getattr(exc, "response", None)
        if getattr(response, "status_code", None) != 404:
            raise
        files = client.list_repo_files(
            repo_id=repo_id,
            repo_type="dataset",
            revision=head,
            token=token,
        )
        remaining = [
            path
            for path in files
            if path == lineage_root or path.startswith(f"{lineage_root}/")
        ]
        if remaining:
            raise RuntimeError(
                "Relay checkpoint marker is missing while lineage files remain"
            ) from exc
        return None


def cleanup_checkpoint(
    repo_id: str,
    *,
    token: str,
    source_sha: str,
    lineage_id: str,
    sandbox_image_digest: str = "",
    api: HfApi | None = None,
) -> None:
    repo_id = validate_hf_dataset_repo_id(repo_id)
    client = api or HfApi(token=token)
    lineage_root = _lineage_root(source_sha, lineage_id)
    marker_remote = f"{lineage_root}/current.json"
    head = _repo_head(client, repo_id=repo_id, token=token)
    marker_path = _marker_at_head_or_confirm_absent(
        client,
        repo_id=repo_id,
        token=token,
        lineage_root=lineage_root,
        marker_remote=marker_remote,
        head=head,
    )
    if marker_path is None:
        print(f"Relay checkpoint already cleaned from {repo_id}")
        return
    marker = _marker(marker_path.read_bytes())
    _verify_marker_identity(
        marker,
        source_sha=source_sha,
        lineage_id=lineage_id,
        sandbox_image_digest=sandbox_image_digest,
    )
    try:
        client.create_commit(
            repo_id=repo_id,
            operations=[
                CommitOperationDelete(
                    path_in_repo=lineage_root,
                    is_folder=True,
                ),
            ],
            commit_message=f"Clean relay checkpoint {marker['generation'][:12]}",
            repo_type="dataset",
            token=token,
            parent_commit=head,
        )
    except Exception:
        confirmed_head = _repo_head(client, repo_id=repo_id, token=token)
        if _marker_at_head_or_confirm_absent(
            client,
            repo_id=repo_id,
            token=token,
            lineage_root=lineage_root,
            marker_remote=marker_remote,
            head=confirmed_head,
        ) is None:
            print(f"Relay checkpoint cleaned from {repo_id}")
            return
        raise
    print(f"Relay checkpoint cleaned from {repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation", choices=("verify-write", "restore", "upload", "cleanup")
    )
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--source-sha")
    parser.add_argument("--lineage-id")
    parser.add_argument("--sandbox-image-digest", default="")
    args = parser.parse_args()
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required")
    if args.operation == "verify-write":
        verify_write_access(args.repo_id, token=token)
    elif args.operation == "upload":
        if not args.source_sha:
            raise SystemExit("--source-sha is required for upload")
        upload_checkpoint(
            args.repo_id,
            token=token,
            source_sha=args.source_sha,
            sandbox_image_digest=args.sandbox_image_digest,
        )
    else:
        if not args.source_sha or not args.lineage_id:
            raise SystemExit("--source-sha and --lineage-id are required")
        operation = restore_checkpoint if args.operation == "restore" else cleanup_checkpoint
        operation(
            args.repo_id,
            token=token,
            source_sha=args.source_sha,
            lineage_id=args.lineage_id,
            sandbox_image_digest=args.sandbox_image_digest,
        )


if __name__ == "__main__":
    main()