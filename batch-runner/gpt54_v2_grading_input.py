"""Materialize one externally bound V2 run for step8, without executing it.

The caller must supply the independently approved digest of an inference
identity document. Matching that document is an offline check, not discovery
of a live publication revision. Issuing the document remains an external gate.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.agentic_v2_cost_binding import describe_run_outcome
from core.agentic_v2_manifest_binding import ManifestRefused, bind_stage, binding_record
from core.agentic_v2_run_report import summarise_v2_run
from core.execution_envelope_tasks import load_task_catalog
from core.inference_manifest import (
    _assert_no_symlink_ancestors,
    bind_deliverable_file_records,
    canonicalize_inference_payload,
    canonicalize_inference_results,
)
from core.reference_integrity import open_verified_reference, validate_reference_record
from core.result_fingerprint import inference_result_fingerprint
from core.result_projection import project_result_row
from gpt54_comparison_preflight import (
    ComparisonGradingRunSpec,
    _canonical_json,
    compile_grading_plan,
)


class V2GradingInputRefused(ValueError):
    """The inputs do not describe the exact, independently bound V2 run."""


def _same(label: str, actual: Any, expected: Any) -> None:
    # JSON equality keeps bool/int, missing/null and list order distinct.
    if _canonical_json(actual) != _canonical_json(expected):
        raise V2GradingInputRefused(f"{label} mismatch")


def _read_bytes(path: Path, *, sha256: str | None = None, size: int | None = None) -> bytes:
    _assert_no_symlink_ancestors(path)
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise V2GradingInputRefused("input must be a single-link regular file")
    with open_verified_reference(path, expected_sha256=sha256, expected_size=size) as (stream, verified):
        if os.fstat(stream.fileno()).st_nlink != 1:
            raise V2GradingInputRefused("input gained another link")
        data = stream.read()
        _same("read size", len(data), verified.size)
        _same("read digest", hashlib.sha256(data).hexdigest(), verified.sha256)
    return data


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise V2GradingInputRefused("duplicate JSON key")
        result[key] = value
    return result


def _read_object(path: Path, *, sha256: str) -> dict[str, Any]:
    validate_reference_record({"sha256": sha256, "size": 0})
    value = json.loads(_read_bytes(path, sha256=sha256), object_pairs_hook=_object)
    if not isinstance(value, dict):
        raise V2GradingInputRefused("input document must be an object")
    _canonical_json(value)  # Reject NaN and infinity before any output is written.
    return value


def _project_rows(record: dict[str, Any], run: ComparisonGradingRunSpec) -> list[dict]:
    raw_rows = record["run"]["results"]
    rows = canonicalize_inference_results(raw_rows)
    _same("canonical producer rows", raw_rows, rows)
    _same("ordered task scope", [row["task_id"] for row in rows], list(run.task_ids))
    projected = []
    for row in rows:
        status = row.get("status")
        if status not in ("success", "error"):
            raise V2GradingInputRefused("a producer row is not terminal")
        files = row["deliverable_files"]
        _same("deliverable count", row.get("deliverable_files_count"), len(files))
        if (status == "success") != bool(files):
            raise V2GradingInputRefused("status contradicts collected deliverables")
        _same("retried", row.get("retried"), False)
        if row.get("resume_round") is not None:
            raise V2GradingInputRefused("resumed rows are outside this comparison")
        metrics = row["observability"]["agentic_metrics"]
        _same("attempt count", metrics.get("agentic_v2_attempts"), 1)
        _same("abandoned attempts", metrics.get("agentic_v2_abandoned_attempts"), 0)
        if status == "success" and row.get("error") is not None:
            raise V2GradingInputRefused("success row carries a terminal error")
        outcome = describe_run_outcome({"success": status == "success", "error": row.get("error")})
        _same("terminal error", metrics.get("terminal_error_category"), outcome["error_type"] or "")
        _same("disposition", metrics.get("agentic_v2_disposition"), outcome["disposition"])
        # Reuse receipt validation/normalization and preserve V2's other fields,
        # including retry evidence and present-null costs. The report projection
        # alone deliberately omits those null receipts.
        projection = project_result_row(row, row)
        result = {**projection, **row}
        for key in ("problem_solving_cost", "grading_cost"):
            if key in projection:
                result[key] = projection[key]
        projected.append(result)

    # Bind actual prompt text and metadata with the producer's existing helper.
    # The row does not carry reference names; those come from the pinned catalog.
    # This checks declarations, not the still-unverified live input-file bytes.
    catalog = load_task_catalog().by_task_id()
    bound = bind_stage("advance_check_5", dataset_tasks=[
        SimpleNamespace(
            task_id=row["task_id"], prompt=row["instruction"],
            sector=row["sector"], occupation=row["occupation"],
            reference_files=catalog[row["task_id"]].reference_file_paths,
        ) for row in rows
    ])
    _same("producer manifest binding", record["binding"], binding_record(bound))
    summary = record["run"]["summary"]
    # With exactly one closed attempt and no abandoned attempt, the driver's
    # journal settles cost only when that row has a complete receipt.
    unaccounted = [row["task_id"] for row in rows if (row.get("problem_solving_cost") or {}).get("status") != "complete"]
    ceiling = "partial" if unaccounted else "complete"
    expected_summary = summarise_v2_run(rows, manifest_size=5, receipt_ceiling=ceiling)
    expected_summary.update(skipped_on_resume=0, stopped_early=None, unaccounted_tasks=unaccounted)
    _same("terminal run summary", summary, expected_summary)
    return projected


def _snapshot_deliverables(rows: list[dict], root: Path) -> tuple[list[dict], dict[str, bytes]]:
    _assert_no_symlink_ancestors(root)
    if not root.is_dir() or {path.name for path in root.iterdir()} - {"deliverable_files"}:
        raise V2GradingInputRefused("source root must contain only deliverable_files")
    tree = root / "deliverable_files"
    _assert_no_symlink_ancestors(tree)
    if not tree.is_dir() and any(row["deliverable_files"] for row in rows):
        raise V2GradingInputRefused("source deliverable tree is missing")
    task_ids = {row["task_id"] for row in rows}
    for child in tree.iterdir() if tree.exists() else ():
        if child.name not in task_ids or child.is_symlink() or not child.is_dir():
            raise V2GradingInputRefused("source contains an extra or unsafe task tree")
    bound = bind_deliverable_file_records(rows, root)
    snapshot = {}
    for original, row in zip(rows, bound):
        records = row["deliverable_file_records"]
        if "deliverable_file_records" in original:
            _same("producer file records", original["deliverable_file_records"], records)
        for item in records:
            digest, size = validate_reference_record({key: item[key] for key in ("sha256", "size")})
            if size == 0:
                raise V2GradingInputRefused("a successful deliverable is empty")
            snapshot[item["path"]] = _read_bytes(root / item["path"], sha256=digest, size=size)
    return bound, snapshot


def _no_replace_rename():
    # Python's directory rename can replace an empty destination after a race.
    # Linux RENAME_NOREPLACE is atomic even then; unsupported hosts fail closed.
    try:
        rename = ctypes.CDLL(None, use_errno=True).renameat2
    except AttributeError as error:
        raise V2GradingInputRefused("atomic no-clobber directory rename is unavailable") from error
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    return rename


def _write_file(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _install(destination: Path, payload: dict, files: dict[str, bytes], run: ComparisonGradingRunSpec) -> Path:
    rename = _no_replace_rename()  # Capability check before creating a temp tree.
    parent = destination.parent
    _assert_no_symlink_ancestors(parent)
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    staging: Path | None = None
    try:
        opened = os.fstat(descriptor)

        def check_parent() -> None:
            _assert_no_symlink_ancestors(parent)
            current = parent.stat()
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise V2GradingInputRefused("destination parent changed")

        check_parent()
        staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=parent))
        check_parent()
        upload = staging / Path(run.staged_deliverables_directory).parent
        (upload / "deliverable_files").mkdir(parents=True)
        for relative, data in files.items():
            _write_file(upload / relative, data)
        _write_file(staging / run.inference_results_path, (_canonical_json(payload) + "\n").encode("utf-8"))
        _same("staged deliverables", bind_deliverable_file_records(payload["results"], upload), payload["results"])
        check_parent()
        if rename(descriptor, os.fsencode(staging.name), descriptor, os.fsencode(destination.name), 1) != 0:
            number = ctypes.get_errno()
            raise OSError(number, os.strerror(number))
        staging = None
        return destination / run.inference_results_path
    finally:
        try:
            if staging is not None:
                # Only the private tree created by this call; never the destination.
                shutil.rmtree(staging.name, dir_fd=descriptor)
        finally:
            os.close(descriptor)


def materialize_v2_grading_input(
    run_spec: ComparisonGradingRunSpec,
    *,
    manifest: dict[str, Any],
    run_record: Path,
    source_deliverables: Path,
    inference_identity: Path,
    approved_identity_sha256: str,
    destination: Path,
) -> Path:
    """Install only canonical input/upload files in a new isolated bundle root.

    ``source_deliverables`` is V2's ``workspace/deliverables`` (the parent of
    ``deliverable_files``). ``destination`` must not exist and its parent must
    already exist. The returned JSON is under ``batch-runner/workspace``; the
    real step8 local loader reads it from ``destination / 'batch-runner'``.
    This does not populate a source checkout/config or authorize grading.

    ``approved_identity_sha256`` must come from the external reviewer/issuer,
    not from the untrusted run or identity document. No offline checksum can
    establish that a publication revision exists or was served by a provider.
    """
    try:
        if type(run_spec) is not ComparisonGradingRunSpec or run_spec.condition != "sandbox_v2":
            raise V2GradingInputRefused("an exact V2 grading run spec is required")
        plan = compile_grading_plan(manifest)
        canonical = next((run for run in plan.runs if run.run_id == run_spec.run_id), None)
        if canonical is None:
            raise V2GradingInputRefused("unknown comparison run")
        _same("grading run spec", run_spec.as_dict(), canonical.as_dict())
        dispatch = next(run for run in plan.dispatch.runs if run.run_id == run_spec.run_id)
        config = json.loads(dispatch.config_json)
        paths = [Path(path) for path in (run_record, source_deliverables, inference_identity, destination)]
        if any(".." in path.parts for path in paths):
            raise V2GradingInputRefused("parent traversal is not allowed")
        run_record, source_deliverables, inference_identity, destination = [
            Path(os.path.abspath(path)) for path in paths
        ]
        for path in paths:
            _assert_no_symlink_ancestors(path)
        if os.path.lexists(destination) or not destination.parent.is_dir():
            raise V2GradingInputRefused("destination exists or its parent is missing")
        for source in (run_record, source_deliverables, inference_identity):
            if destination.is_relative_to(source) or source.is_relative_to(destination):
                raise V2GradingInputRefused("source and destination overlap")
        identity = _read_object(inference_identity, sha256=approved_identity_sha256)
        # Use the real step8 Track-2 identity rules, without accepting its
        # whitespace normalization or substituting any known dataset/Git base.
        from step8_grade import resolve_source_inference_identity

        repo_id, revision = resolve_source_inference_identity(identity, "2.0")
        _same("inference repository", identity["source_repo_id"], repo_id)
        _same("inference revision", identity["source_revision"], revision)
        shared = manifest["shared"]
        if repo_id == shared["dataset"]["repo_id"] or revision in {
            shared["dataset"]["revision"], manifest["base_sha"], shared["grading"]["source_sha"],
        }:
            raise V2GradingInputRefused("dataset/Git provenance is not inference identity")
        record = _read_object(run_record, sha256=identity["run_record_sha256"])
        if "rehearsal" in record:
            raise V2GradingInputRefused("rehearsal is not an inference run")
        _same("record run id", record["run_id"], run_spec.run_id)
        _same("outcome run id", record["run"]["run_id"], run_spec.run_id)
        _same("producer stage", record["stage"], dispatch.cohort)
        _same("producer dataset", record["dataset_revision"], shared["dataset"]["revision"])
        _same("stopped run", record["run"]["stopped_early"], None)
        _same("resumed run", record["run"]["skipped_on_resume"], [])
        _same("producer shard", record["shard"], {
            "index": 1, "of": 1, "task_count": 5, "cohort_size": 5,
            "task_ids": list(run_spec.task_ids), "covers_whole_stage": True,
            "what_this_run_is": "the whole stage, in one run",
        })
        config_digest = hashlib.sha256(dispatch.config_json.encode("utf-8")).hexdigest()
        _same("producer config", record["request_conditions"]["plan_file"], {
            "path": Path(dispatch.config_path).relative_to(dispatch.working_directory).as_posix(),
            "sha256": config_digest,
        })
        _same("replay format", record["request_conditions"]["replay_format"], config["fixed_settings"]["replay_format"])
        for key, value in config["cost"]["chosen_settings"].items():
            _same(f"chosen {key}", record["chosen_settings"][key], value)
        rows, files = _snapshot_deliverables(_project_rows(record, run_spec), source_deliverables)
        expected_identity = {
            "source_repo_id": repo_id, "source_revision": revision,
            "run_id": run_spec.run_id, "condition": run_spec.condition, "repeat": run_spec.repeat,
            "task_ids": list(run_spec.task_ids),
            "producer_results_path": run_spec.producer_results_path,
            "producer_rows_pointer": run_spec.producer_rows_pointer,
            "manifest_sha256": plan.dispatch.manifest_sha256,
            "grading_plan_sha256": hashlib.sha256(plan.canonical_bytes()).hexdigest(),
            "config_sha256": config_digest,
            "source_pins_sha256": hashlib.sha256(plan.dispatch.source_pins_json.encode("utf-8")).hexdigest(),
            "run_record_sha256": identity["run_record_sha256"],
            "deliverables": [{"task_id": row["task_id"], "files": row["deliverable_file_records"]} for row in rows],
        }
        _same("approved inference binding", identity, expected_identity)
        payload = canonicalize_inference_payload({
            "experiment_id": run_spec.run_id,
            "source_repo_id": repo_id, "source_revision": revision,
            "source_identity_document_sha256": approved_identity_sha256,
            "results": rows,
        })
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
        return _install(destination, payload, files, run_spec)
    except V2GradingInputRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ManifestRefused) as error:
        raise V2GradingInputRefused(f"V2 grading input refused: {error}") from error
