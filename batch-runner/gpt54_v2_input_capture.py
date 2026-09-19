"""Opt-in V2 comparison capture, before even the free voice-safety probes.

This binds local source bytes and the held TaskToRun objects. It does not prove
served capability, later wire prompt equality, publication identity or approval.
The Codex atomic single-file writer is reused unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.agentic_v2_manifest_binding import BoundManifest, ManifestRefused
from core.inference_manifest import _assert_no_symlink_ancestors


class V2InputCaptureRefused(ManifestRefused):
    """Local comparison inputs cannot cross the voice/provider/auth gate."""


@dataclass(frozen=True)
class V2ComparisonCapture:
    """Same config for both repeats; the explicit CLI run id selects the run."""

    binding_version: str = "gpt54-pre-execution-input-v1"

    RUN_IDS = ("gpt54_v2_codex_v1_v2_r1", "gpt54_v2_codex_v1_v2_r2")

    def __post_init__(self):
        if type(self.binding_version) is not str or self.binding_version != "gpt54-pre-execution-input-v1":
            raise V2InputCaptureRefused("unsupported V2 comparison capture contract")

    @classmethod
    def from_dict(cls, value):
        if value is None:
            return None
        if type(value) is not dict or set(value) != {"binding_version"}:
            raise V2InputCaptureRefused("V2 comparison capture requires the exact typed control")
        return cls(**value)

    def as_dict(self):
        return {"binding_version": self.binding_version}


def _role(path: Path, root: Path, role: str, relative: str) -> Path:
    """Allow the compiled argv or its exact absolute location, never an alias."""
    path = Path(path)
    expected = root / role
    if path.is_absolute():
        if path != expected:
            raise V2InputCaptureRefused("comparison path role mismatch")
    elif path.as_posix() != relative or Path.cwd() != root / "batch-runner":
        raise V2InputCaptureRefused("comparison relative path role mismatch")
    _assert_no_symlink_ancestors(expected)
    return expected


def _binding(
    root: Path, run_id: str, held_plan: dict, *, held_bound: BoundManifest | None = None,
) -> tuple[BoundManifest, dict[str, Any]]:
    # These modules are unnecessary for every legacy V2 plan. In particular,
    # no dataset/prepared reader or provider is imported by the no-op branch.
    from gpt54_codex_input_capture import (
        COMBINED_PLAN_PATH, CONFIG_PATH, DATASET_ROOT, MANIFEST_PATH, PARQUET_NAME,
    )
    from gpt54_comparison_preflight import compile_grading_plan
    from gpt54_prepared_input_attestation import (
        _expected_binding, _json_object, _same, _source_snapshot, _v2_consumer,
    )
    from gpt54_v2_grading_input import _read_bytes
    from gpt54_run_input_bundle import verify_run_input_bundle

    verify_run_input_bundle(checkout=root, run_id=run_id, condition="sandbox_v2")
    dataset_root = root / DATASET_ROOT
    _assert_no_symlink_ancestors(dataset_root / "data")
    _same("dataset parquet file set", sorted(path.name for path in (dataset_root / "data").iterdir()), [PARQUET_NAME])
    manifest = yaml.safe_load(_read_bytes(root / MANIFEST_PATH))
    plan = compile_grading_plan(manifest)
    if _read_bytes(root / COMBINED_PLAN_PATH) != plan.canonical_bytes():
        raise V2InputCaptureRefused("combined plan bytes mismatch")
    run = next(run for run in plan.dispatch.runs if run.run_id == run_id)
    _same("V2 condition", run.condition, "sandbox_v2")
    config_data = _read_bytes(root / CONFIG_PATH)
    _same("held V2 plan", held_plan, _json_object(config_data))
    snapshot = _source_snapshot(
        plan, dataset_root / "data" / PARQUET_NAME, dataset_root, reference_subtree=True,
    )
    bound = snapshot.bound if held_bound is None else held_bound
    return bound, _expected_binding(snapshot, run, config_data, _v2_consumer(snapshot, bound))


def capture_v2_pre_execution_input(
    plan: dict, *, run_id: str | None, stage: str, config_path: Path, parquet_path: Path,
    dataset_root: Path | None, workspace: Path | None, shard: str | None,
    dry_run: bool, rehearse: bool, isolated_approval: Path | None,
) -> tuple[BoundManifest, dict[str, Any]] | None:
    """Publish and immediately recompute the capture, returning the actual tasks.

    Absent/null controls are a no-op unless the reserved run id requires one.
    A failed post-publication verification may leave a complete capture, never
    a partial file; retry/resume must not overwrite it or adopt an old workspace.
    """
    if plan.get("comparison_input_capture") is None and run_id not in (
        *V2ComparisonCapture.RUN_IDS,
        "gpt54_v2_codex_v1_codex_r1", "gpt54_v2_codex_v1_codex_r2",
    ):
        return None

    from gpt54_codex_input_capture import (
        CAPTURE_PATH, CONFIG_PATH, DATASET_ROOT, PARQUET_NAME, _write_no_clobber,
    )
    from gpt54_comparison_preflight import _canonical_json
    from gpt54_prepared_input_attestation import _identity, _same
    from gpt54_v2_grading_input import _read_bytes

    try:
        control = V2ComparisonCapture.from_dict(plan.get("comparison_input_capture"))
        if control is None or type(run_id) is not str or run_id not in V2ComparisonCapture.RUN_IDS:
            raise V2InputCaptureRefused("explicit V2 capture control and registered --run-id required")
        _same("comparison runtime options", {
            "stage": stage, "shard": shard, "dry_run": dry_run,
            "rehearse": rehearse, "isolated_approval": isolated_approval,
        }, {
            "stage": "advance_check_5", "shard": None, "dry_run": False,
            "rehearse": False, "isolated_approval": None,
        })
        if dataset_root is None or workspace is None or ".." in Path(config_path).parts:
            raise V2InputCaptureRefused("explicit comparison path roles required")
        root = Path(os.path.abspath(config_path)).parent.parent
        _role(config_path, root, CONFIG_PATH, "comparison-run.json")
        _role(dataset_root, root, DATASET_ROOT, "../data/gdpval-local")
        _role(parquet_path, root, DATASET_ROOT + "/data/" + PARQUET_NAME,
              "../data/gdpval-local/data/" + PARQUET_NAME)
        workspace = _role(workspace, root, "batch-runner/workspace", "workspace")
        if workspace.exists() and (not workspace.is_dir() or any(workspace.iterdir())):
            raise V2InputCaptureRefused("comparison workspace must be new or empty; no resume")

        from gpt54_disposable_checkout import verify_runtime_checkout

        verify_runtime_checkout(checkout=root, run_id=run_id, condition="sandbox_v2")
        bound, binding = _binding(root, run_id, plan)
        expected = _canonical_json(binding).encode("utf-8")
        identity = _identity(expected)
        workspace.mkdir(exist_ok=True)
        _write_no_clobber(root / CAPTURE_PATH, expected)
        # Re-read every source/config byte and compare the same held objects
        # that main will hand to run_manifest, not a replacement task sequence.
        _, current = _binding(root, run_id, plan, held_bound=bound)
        if _canonical_json(current).encode("utf-8") != expected:
            raise V2InputCaptureRefused("V2 source changed during capture publication")
        if _read_bytes(root / CAPTURE_PATH, **identity) != expected:
            raise V2InputCaptureRefused("V2 capture bytes mismatch")
        _same("pristine capture workspace", sorted(path.name for path in workspace.iterdir()), ["pre-execution-input.json"])
        return bound, {
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
    except (OSError, ValueError, TypeError, KeyError, StopIteration, ManifestRefused, yaml.YAMLError) as error:
        raise V2InputCaptureRefused("V2 pre-execution input capture refused") from error
