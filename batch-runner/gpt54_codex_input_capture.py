"""Comparison-only local input capture; no provider, approval or dispatch.

Paths name fixed roles relative to one run checkout. Only prepared JSON and its
capture are written. The capture digest can later match an attestation's binding_file;
this module neither invents that attestation nor issues an inference identity.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

from core.agentic_v2_manifest_binding import ManifestRefused
from core.experiment_config import CodexComparisonCapture
from core.inference_manifest import _assert_no_symlink_ancestors
from gpt54_comparison_preflight import ENVELOPE, _canonical_json, compile_grading_plan
from gpt54_prepared_input_attestation import (
    _check_prepared, _expected_binding, _identity, _json_object, _same, _source_snapshot,
)
from gpt54_v2_grading_input import _read_bytes

CONFIG_PATH = "batch-runner/comparison-run.json"
COMBINED_PLAN_PATH = "comparison-plan.json"
CAPTURE_PATH = "batch-runner/workspace/pre-execution-input.json"
PREPARED_PATH = "batch-runner/workspace/step1_tasks_prepared.json"
DATASET_ROOT = "data/gdpval-local"
PARQUET_NAME = "train-00000-of-00001.parquet"
MANIFEST_PATH = ENVELOPE + "gpt54_sandboxv2_codex_comparison.yaml"


class CodexInputCaptureRefused(ValueError):
    """Local comparison inputs cannot cross the provider-construction gate."""


def read_codex_prepared(path: Path) -> dict[str, Any]:
    """The explicit CLI route must not follow links even for its first read."""
    try:
        return _json_object(_read_bytes(path))
    except (OSError, ValueError, TypeError) as error:
        raise CodexInputCaptureRefused("Codex prepared input read refused") from error


def _absolute(path: Path) -> Path:
    path = Path(path)
    if ".." in path.parts:
        raise CodexInputCaptureRefused("parent traversal is not a run-relative role")
    return Path(os.path.abspath(path))


def _binding(
    control: CodexComparisonCapture, *, workspace: Path, dataset_root: Path,
    config_path: Path | None = None, prepared: dict | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Read and validate the exact files consumed by Step 1 and Step 2."""
    if type(control) is not CodexComparisonCapture:
        raise CodexInputCaptureRefused("typed comparison capture control required")
    workspace, dataset_root = _absolute(workspace), _absolute(dataset_root)
    root = workspace.parent.parent
    _same("workspace role", workspace.as_posix(), (root / "batch-runner/workspace").as_posix())
    _same("dataset role", dataset_root.as_posix(), (root / DATASET_ROOT).as_posix())
    if config_path is not None:
        _same("config role", _absolute(config_path).as_posix(), (root / CONFIG_PATH).as_posix())
    from gpt54_run_input_bundle import verify_run_input_bundle

    verify_run_input_bundle(checkout=root, run_id=control.run_id, condition="codex")
    for path in (root, workspace, dataset_root, dataset_root / "data"):
        _assert_no_symlink_ancestors(path)
    _same("dataset parquet file set", sorted(path.name for path in (dataset_root / "data").iterdir()), [PARQUET_NAME])
    manifest = yaml.safe_load(_read_bytes(root / MANIFEST_PATH))
    plan = compile_grading_plan(manifest)
    combined = _read_bytes(root / COMBINED_PLAN_PATH)
    if combined != plan.canonical_bytes():
        raise CodexInputCaptureRefused("combined plan bytes mismatch")
    run = next(run for run in plan.dispatch.runs if run.run_id == control.run_id)
    _same("Codex condition", run.condition, "codex")
    config_data = _read_bytes(root / CONFIG_PATH)
    expected_control = _json_object(config_data)["execution"].get("comparison_input_capture")
    _same("config capture control", expected_control, control.as_dict())
    prepared_data = _read_bytes(root / PREPARED_PATH)
    held = _json_object(prepared_data)
    if prepared is not None:
        _same("held prepared input", held, prepared)
    _same("prepared config role", held.get("config_path"), "comparison-run.json")
    snapshot = _source_snapshot(
        plan, dataset_root / "data" / PARQUET_NAME, dataset_root, reference_subtree=True,
    )
    consumer = _check_prepared(
        prepared_data, run, snapshot.projections, snapshot.references, snapshot.needs_files,
    )
    return root / CAPTURE_PATH, _expected_binding(snapshot, run, config_data, consumer)


def _write_no_clobber(path: Path, data: bytes) -> None:
    """Publish complete bytes with an atomic, no-replace link in a held parent.

    This is a single-file primitive, not the materializers' native directory
    RENAME_NOREPLACE gate. There is no rename/replace or in-place-write fallback.
    The private temporary link is always removed, leaving one link on success.
    """
    parent = path.parent
    _assert_no_symlink_ancestors(parent)
    descriptor = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary: str | None = None
    try:
        opened = os.fstat(descriptor)

        def check_parent():
            _assert_no_symlink_ancestors(parent)
            current = parent.stat()
            if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                raise CodexInputCaptureRefused("capture parent changed")

        check_parent()
        handle, name = tempfile.mkstemp(prefix=".input-capture-", dir=f"/proc/self/fd/{descriptor}")
        temporary = Path(name).name
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        check_parent()
        os.link(temporary, path.name, src_dir_fd=descriptor, dst_dir_fd=descriptor, follow_symlinks=False)
    finally:
        try:
            if temporary is not None:
                os.unlink(temporary, dir_fd=descriptor)
        finally:
            os.close(descriptor)


def write_codex_input_capture(
    control: CodexComparisonCapture, *, workspace: Path, dataset_root: Path, config_path: Path,
) -> None:
    """Called only after the real Step 1 serializer has closed prepared JSON."""
    try:
        path, binding = _binding(control, workspace=workspace, dataset_root=dataset_root, config_path=config_path)
        _write_no_clobber(path, _canonical_json(binding).encode("utf-8"))
    except (OSError, ValueError, TypeError, KeyError, StopIteration, ManifestRefused) as error:
        raise CodexInputCaptureRefused("Codex input capture creation refused") from error


def write_codex_prepared_and_capture(
    control: CodexComparisonCapture, *, workspace: Path, dataset_root: Path,
    config_path: Path, prepared_data: bytes,
) -> None:
    """Keep any existing pair intact, including a fresh-generation rerun."""
    try:
        workspace = _absolute(workspace)
        _assert_no_symlink_ancestors(workspace)
        if type(control) is not CodexComparisonCapture:
            raise CodexInputCaptureRefused("typed comparison capture control required")
        root = workspace.parent.parent
        _same("workspace role", workspace.as_posix(), (root / "batch-runner/workspace").as_posix())
        _same("config role", _absolute(config_path).as_posix(), (root / CONFIG_PATH).as_posix())
        from gpt54_run_input_bundle import verify_run_input_bundle

        verify_run_input_bundle(checkout=root, run_id=control.run_id, condition="codex")
        if os.path.lexists(workspace / "pre-execution-input.json"):
            raise CodexInputCaptureRefused("comparison capture already exists")
        # Never truncate an old prepared file or follow its final symlink.
        # A later refusal can leave this complete prepared file without a
        # capture; it cannot cross Step 2's gate or be overwritten by a retry.
        _write_no_clobber(workspace / "step1_tasks_prepared.json", prepared_data)
        write_codex_input_capture(
            control, workspace=workspace, dataset_root=dataset_root, config_path=config_path,
        )
    except (OSError, ValueError, TypeError) as error:
        raise CodexInputCaptureRefused("Codex prepared/capture publication refused") from error


def verify_codex_input_capture(
    prepared: dict, *, workspace: Path, dataset_root: Path, comparison_run_id: str | None,
    condition_key: str, execution_mode: str | None, max_retries: int | None,
    resume_max_rounds: int | None, resume: bool, wall_timeout: int | None,
) -> dict[str, Any]:
    """Recompute from current local bytes before provider/auth/client creation."""
    try:
        control = CodexComparisonCapture.from_dict(prepared["execution"].get("comparison_input_capture"))
        if control is None:
            raise CodexInputCaptureRefused("required comparison capture control is absent")
        if comparison_run_id is not None:
            _same("CLI comparison run", comparison_run_id, control.run_id)
        _same("comparison runtime overrides", {
            "condition": condition_key, "mode": "codex_foundry" if execution_mode is None else execution_mode,
            "max_retries": 0 if max_retries is None else max_retries,
            "resume_max_rounds": 0 if resume_max_rounds is None else resume_max_rounds,
            "resume": resume, "wall_timeout": wall_timeout,
        }, {
            "condition": "condition_a", "mode": "codex_foundry", "max_retries": 0,
            "resume_max_rounds": 0, "resume": False, "wall_timeout": None,
        })
        path, binding = _binding(control, workspace=workspace, dataset_root=dataset_root, prepared=prepared)
        expected = _canonical_json(binding).encode("utf-8")
        identity = _identity(expected)
        actual = _read_bytes(path, **identity)
        if actual != expected:
            raise CodexInputCaptureRefused("capture bytes mismatch")
        # No overall attestation digest exists until all four captures have
        # been supplied. These fields link this file to that future check.
        return {
            "path": CAPTURE_PATH, **identity,
            "attestation_linkage": {
                "attestation_version": "gpt54-prepared-input-attestation-v1",
                **{key: binding[key] for key in (
                    "binding_version", "run_id", "condition", "repeat", "manifest_sha256",
                    "combined_plan_sha256", "source_pins_sha256", "config_sha256",
                    "ordered_source_projection_sha256",
                )},
            },
            "evidence_boundary": "local_pre_execution_snapshot_consistency",
        }
    except (OSError, ValueError, TypeError, KeyError, StopIteration, ManifestRefused) as error:
        raise CodexInputCaptureRefused("Codex pre-execution input verification refused") from error
