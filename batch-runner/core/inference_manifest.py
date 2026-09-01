"""Validation for inference manifests and their local deliverable tree."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote


TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")
FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
INFERENCE_PROVENANCE_SCHEMA = "azure-ai-inference-provenance-v2"
INFERENCE_EXECUTION_MODES = frozenset({
    "legacy",
    "code_interpreter",
    "subprocess",
    "json_renderer",
    "sandbox",
    "agentic_sandbox",
})
STEP2_PROGRESS_SCHEMA = "step2-progress-v2"
STEP2_RESULT_STATUSES = frozenset({
    "success", "error", "qa_failed", "pending"
})
#: What ``azure_ai_provenance_status`` says when the graded files are the
#: benchmark's own expert answers rather than any model's output. It is not a
#: missing record: no inference ran, so there is no route that could have been
#: recorded. Grading these answers measures how high the grader can score at
#: all, which only reads as a ceiling if it is never mistaken for a model's
#: result -- so ``step8_grade.py`` keeps every such run out of the published
#: path. The matching entry in ``schemas/grade.schema.json`` is what the
#: written grade is validated against; ``tests/test_step8_grade.py`` proves the
#: two still agree.
GOLD_PROVENANCE_STATUS = "gold-corpus"
#: The three values Step 3 can reach on its own. The other two in the schema
#: are written elsewhere: ``gold-corpus`` above, and ``legacy-missing`` or
#: ``verified-sidecar`` by ``scripts/download_inference_from_hf.py`` when an
#: already-published run is pulled back down.
RUNTIME_VERIFIED_PROVENANCE_STATUS = "runtime-verified"
RUNTIME_UNVERIFIED_PROVENANCE_STATUS = "runtime-unverified"
LOCAL_RUNTIME_PROVENANCE_STATUS = "local-runtime"
_ROUTE_KEYS = {
    "endpoint_kind",
    "profile",
    "runtime_fingerprint",
    "workload",
}


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


def validate_step2_progress_results(
    results: Any,
    *,
    schema_version: Any,
) -> None:
    if schema_version != STEP2_PROGRESS_SCHEMA:
        raise ValueError("Step 2 progress schema version is unsupported")
    if not isinstance(results, list):
        raise ValueError("Step 2 progress results must be an array")

    terminal_fields = {
        "content",
        "deliverable_text",
        "deliverable_files",
        "model",
        "usage",
        "observability",
        "latency_ms",
        "timestamp",
    }
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            raise ValueError(
                f"Step 2 progress result {index} must be an object"
            )
        task_id = canonical_task_id(result.get("task_id"))
        status = result.get("status")
        if status not in STEP2_RESULT_STATUSES:
            raise ValueError("Step 2 progress result status is invalid")
        timestamp = result.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError("Step 2 progress result timestamp is invalid")

        if status == "pending":
            error = result.get("error")
            if not isinstance(error, str) or not error:
                raise ValueError("Step 2 pending result error is invalid")
            continue

        if not terminal_fields <= result.keys():
            raise ValueError("Step 2 terminal result fields are incomplete")
        if result["content"] is not None and not isinstance(
            result["content"], str
        ):
            raise ValueError("Step 2 result content is invalid")
        if result["deliverable_text"] is not None and not isinstance(
            result["deliverable_text"], str
        ):
            raise ValueError("Step 2 result deliverable text is invalid")
        files = result["deliverable_files"]
        if not isinstance(files, list):
            raise ValueError("Step 2 result deliverable files are invalid")
        canonical_files = [
            canonical_deliverable_path(task_id, path) for path in files
        ]
        if len(canonical_files) != len(set(canonical_files)):
            raise ValueError("Step 2 result deliverable files are duplicated")
        if not isinstance(result["model"], str) or not result["model"]:
            raise ValueError("Step 2 result model is invalid")
        if result["usage"] is not None and not isinstance(
            result["usage"], dict
        ):
            raise ValueError("Step 2 result usage is invalid")
        if not isinstance(result["observability"], dict):
            raise ValueError("Step 2 result observability is invalid")
        latency_ms = result["latency_ms"]
        if latency_ms is not None and (
            isinstance(latency_ms, bool)
            or not isinstance(latency_ms, (int, float))
            or not math.isfinite(latency_ms)
            or latency_ms < 0
        ):
            raise ValueError("Step 2 result latency is invalid")

        if status == "error":
            error = result.get("error")
            if not isinstance(error, str) or not error:
                raise ValueError("Step 2 error result error is invalid")
        elif not any((
            bool(result["content"]),
            bool(result["deliverable_text"]),
            bool(canonical_files),
        )):
            raise ValueError("Step 2 successful result has no output")


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


def canonicalize_azure_ai_routes(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ValueError("azure_ai_routes must be an array")
    routes: list[dict[str, str]] = []
    fingerprints: set[str] = set()
    for index, route in enumerate(value):
        if not isinstance(route, dict) or set(route) != _ROUTE_KEYS:
            raise ValueError(f"Azure AI route {index} has invalid fields")
        endpoint_kind = route.get("endpoint_kind")
        profile = route.get("profile")
        fingerprint = route.get("runtime_fingerprint")
        workload = route.get("workload")
        if endpoint_kind not in {"direct-v1", "project", "legacy-dated"}:
            raise ValueError(f"Azure AI route {index} endpoint kind is invalid")
        if profile not in {"direct-v1", "project-ci", "legacy-rollback"}:
            raise ValueError(f"Azure AI route {index} profile is invalid")
        if not isinstance(fingerprint, str) or not FULL_SHA256_RE.fullmatch(
            fingerprint
        ):
            raise ValueError(f"Azure AI route {index} fingerprint is invalid")
        if workload not in {
            "inference",
            "code-interpreter",
            "narrative",
            "grader",
        }:
            raise ValueError(f"Azure AI route {index} workload is invalid")
        expected_endpoint_kind = {
            "direct-v1": "direct-v1",
            "legacy-rollback": "legacy-dated",
            "project-ci": (
                "project" if workload == "code-interpreter" else "direct-v1"
            ),
        }[profile]
        if (
            endpoint_kind != expected_endpoint_kind
            or workload == "code-interpreter" and profile != "project-ci"
        ):
            raise ValueError(
                f"Azure AI route {index} profile, endpoint, and workload disagree"
            )
        if fingerprint in fingerprints:
            raise ValueError("Azure AI route fingerprints must be unique")
        fingerprints.add(fingerprint)
        routes.append(dict(route))
    return routes


def canonical_execution_mode(value: Any) -> str:
    if value not in INFERENCE_EXECUTION_MODES:
        raise ValueError("inference execution mode is invalid")
    return value


def validate_execution_route_binding(
    execution_mode: Any,
    routes: list[dict[str, str]],
) -> str:
    mode = canonical_execution_mode(execution_mode)
    code_interpreter_routes = [
        route
        for route in routes
        if route["workload"] == "code-interpreter"
    ]
    if mode == "code_interpreter":
        if (
            len(code_interpreter_routes) != 1
            or code_interpreter_routes[0]["profile"] != "project-ci"
            or code_interpreter_routes[0]["endpoint_kind"] != "project"
            or any(route["profile"] != "project-ci" for route in routes)
        ):
            raise ValueError(
                "Code Interpreter provenance requires one project-ci route"
            )
    elif code_interpreter_routes:
        raise ValueError(
            "non-Code-Interpreter provenance contains a Code Interpreter route"
        )
    return mode


def azure_ai_provenance_status(routes: Any, summary: Any) -> str:
    """Report whether an Azure AI route was shown to answer, rather than assume it.

    Step 3 used to write ``runtime-verified`` as a literal, so every run said
    its Azure routes had been verified at runtime -- including the runs where
    no route ever answered. exp032 is the case that proves it: all five of its
    tasks came back ``PermissionDeniedError (http 403)`` from the
    project-scoped Code Interpreter route, and the ``result.json`` it wrote
    still called that route runtime-verified.

    ``azure_ai_routes`` cannot fix this by itself. Those records are built from
    resolved settings in ``core/azure_ai_clients.py``, so they describe the
    route that was *selected* and never the one that replied; a run with a
    perfect route list and five refusals produces exactly the same array as a
    run with five successes. Only the outcome separates them, which is why the
    outcome is what this reads.

    A completed task is the evidence, because no task completes without a
    served response. Note the limit of that: it covers the *execution* route
    only. The narrative route is exercised later, in Step 6, which has not run
    when this is written, so this value says nothing about it.

    Fail closed on anything unrecognised. A false ``runtime-verified`` is a
    provenance record that lies; a false ``runtime-unverified`` is a cautious
    label on a good run, and the two are not the same size of mistake.
    """
    # A run with no typed routes is not an unverified Azure run, it is a run
    # that made no typed Azure claim at all -- which is the same thing
    # step8_grade.py already assumes when the key is missing entirely.
    if routes is None or routes == []:
        return LOCAL_RUNTIME_PROVENANCE_STATUS
    if not isinstance(routes, list) or not isinstance(summary, dict):
        return RUNTIME_UNVERIFIED_PROVENANCE_STATUS
    success = summary.get("success")
    # ``isinstance(True, int)`` is True in Python, and a summary carrying
    # ``success: true`` is a malformed summary, not one successful task.
    if isinstance(success, bool) or not isinstance(success, int) or success <= 0:
        return RUNTIME_UNVERIFIED_PROVENANCE_STATUS
    return RUNTIME_VERIFIED_PROVENANCE_STATUS


def _ordered_task_ids_sha256(task_ids: list[str]) -> str:
    encoded = json.dumps(
        task_ids,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_inference_provenance(payload: Any) -> dict:
    normalized = canonicalize_inference_payload(payload)
    experiment_id = normalized.get("experiment_id")
    source_repo_id = normalized.get("source_repo_id")
    prepared_fingerprint = normalized.get("prepared_fingerprint")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise ValueError("inference provenance experiment_id is invalid")
    if not isinstance(source_repo_id, str) or "/" not in source_repo_id:
        raise ValueError("inference provenance source_repo_id is invalid")
    if (
        not isinstance(prepared_fingerprint, str)
        or not FULL_SHA256_RE.fullmatch(prepared_fingerprint)
    ):
        raise ValueError("inference provenance prepared_fingerprint is invalid")
    task_ids = [row["task_id"] for row in normalized["results"]]
    routes = canonicalize_azure_ai_routes(
        normalized.get("azure_ai_routes", [])
    )
    execution_mode = validate_execution_route_binding(
        normalized.get("execution_mode"), routes
    )
    return {
        "schema_version": INFERENCE_PROVENANCE_SCHEMA,
        "experiment_id": experiment_id,
        "source_repo_id": source_repo_id,
        "prepared_fingerprint": prepared_fingerprint,
        "execution_mode": execution_mode,
        "task_count": len(task_ids),
        "ordered_task_ids_sha256": _ordered_task_ids_sha256(task_ids),
        "azure_ai_routes": routes,
    }


def validate_inference_provenance(
    payload: Any,
    *,
    experiment_id: str,
    source_repo_id: str,
    task_ids: list[str],
    prepared_fingerprint: str | None = None,
    azure_ai_routes: list[dict[str, str]] | None = None,
    execution_mode: str | None = None,
) -> dict:
    expected_keys = {
        "schema_version",
        "experiment_id",
        "source_repo_id",
        "prepared_fingerprint",
        "execution_mode",
        "task_count",
        "ordered_task_ids_sha256",
        "azure_ai_routes",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise ValueError("inference provenance fields are invalid")
    if payload.get("schema_version") != INFERENCE_PROVENANCE_SCHEMA:
        raise ValueError("inference provenance schema is invalid")
    if payload.get("experiment_id") != experiment_id:
        raise ValueError("inference provenance experiment identity mismatch")
    if payload.get("source_repo_id") != source_repo_id:
        raise ValueError("inference provenance repository identity mismatch")
    claimed_execution_mode = canonical_execution_mode(
        payload.get("execution_mode")
    )
    if (
        execution_mode is not None
        and claimed_execution_mode != canonical_execution_mode(execution_mode)
    ):
        raise ValueError("inference provenance execution mode mismatch")
    claimed_prepared_fingerprint = payload.get("prepared_fingerprint")
    if (
        not isinstance(claimed_prepared_fingerprint, str)
        or not FULL_SHA256_RE.fullmatch(claimed_prepared_fingerprint)
    ):
        raise ValueError("inference provenance prepared fingerprint is invalid")
    if (
        prepared_fingerprint is not None
        and claimed_prepared_fingerprint != prepared_fingerprint
    ):
        raise ValueError("inference provenance prepared fingerprint mismatch")
    canonical_task_ids = [canonical_task_id(value) for value in task_ids]
    if payload.get("task_count") != len(canonical_task_ids):
        raise ValueError("inference provenance task count mismatch")
    if payload.get("ordered_task_ids_sha256") != _ordered_task_ids_sha256(
        canonical_task_ids
    ):
        raise ValueError("inference provenance task order mismatch")
    normalized = dict(payload)
    normalized["azure_ai_routes"] = canonicalize_azure_ai_routes(
        payload.get("azure_ai_routes")
    )
    validate_execution_route_binding(
        claimed_execution_mode,
        normalized["azure_ai_routes"],
    )
    if azure_ai_routes is not None:
        expected_routes = canonicalize_azure_ai_routes(azure_ai_routes)
        if normalized["azure_ai_routes"] != expected_routes:
            raise ValueError("inference provenance Azure AI routes mismatch")
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