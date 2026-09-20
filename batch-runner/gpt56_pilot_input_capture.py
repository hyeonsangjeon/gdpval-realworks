"""Bind prepared Foundry request intent offline, not wire bytes or permission.

Private paths are explicit library arguments, never serialized controls. This
module does not resolve a provider, discover credentials or create a command.
Step 1 publishes its real prepared bytes first and the capture last. Failed
partial pairs are left in place and cannot be adopted or overwritten.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import gpt56_pilot_deployment_binding as deployment
import gpt56_pilot_input_bundle as inputs
import gpt56_sol_codex_pilot_preflight as pilot
from core.experiment_config import ExperimentConfig, PilotInputCapture
from core.prepared_fingerprint import validate_prepared_fingerprint
from core.publication_generation import validate_publication_generation
from core.source_identity import source_task_projection_sha256
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_comparison_preflight import _canonical_json
from gpt54_prepared_input_attestation import _dataset_tasks, _prepared_condition, _reference_snapshot
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

PREPARED_PATH = "step1_tasks_prepared.json"
CAPTURE_PATH = "pilot-pre-execution-input.json"
BOUNDARY = "prepared_request_intent_not_wire_or_served_identity"


class PilotInputCaptureRefused(ValueError):
    """Static codes only: no private paths, evidence, resource IDs or causes."""


@dataclass(frozen=True, repr=False)
class PilotCaptureSources:
    """Private runtime-only inputs; not an experiment-config or output schema."""

    evidence_bundle: Path
    identity_bundle: Path
    config_bundle: Path
    input_bundle: Path
    deployment_binding: Path
    reviewed_source_sha: str
    as_of: str
    account_resource_id_file: Path
    project_resource_id_file: Path
    deployment_resource_id_file: Path

    def _options(self) -> dict[str, Any]:
        return {name: value for name, value in vars(self).items() if name != "deployment_binding"}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PilotInputCaptureRefused(code)


def _bytes(value: Any) -> bytes:
    return _canonical_json(value).encode("utf-8")


def _digest(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _sources(sources: PilotCaptureSources, dataset_root: Path, config_path: Path | None, plan: dict | None):
    _require(type(sources) is PilotCaptureSources, "pilot_capture_sources_required")
    _require(not os.getenv("GDPVAL_RELAY_LINEAGE_ID", ""), "pilot_relay_refused")
    # These are local role checks, never host-path identity in a public record.
    _require(_root(dataset_root) == _root(sources.input_bundle), "pilot_dataset_role_mismatch")
    candidate_path = _path(_root(sources.deployment_binding), deployment.CANDIDATE_PATH)
    if config_path is not None:
        _require(inputs._absolute(config_path) == candidate_path, "pilot_candidate_role_mismatch")
    plan_data = _read_bytes(pilot.PLAN)
    current_plan = yaml.safe_load(plan_data)
    if plan is not None:
        _require(_bytes(plan) == _bytes(current_plan), "pilot_active_plan_mismatch")
    # This verifier explicitly invokes all four preceding real verifiers and
    # checks their current files, reservations, source closure and evidence time.
    bound = deployment.verify_pilot_deployment_binding(
        current_plan, bundle_root=sources.deployment_binding, **sources._options(),
    )
    candidate = _read_bytes(candidate_path)
    _require(candidate == dict(bound.files)[deployment.CANDIDATE_PATH], "pilot_candidate_bytes_mismatch")
    config = ExperimentConfig.from_dict(json.loads(candidate))
    _require(not config.validate() and config.execution.pilot_input_capture == PilotInputCapture(pilot.RUN_ID),
             "pilot_control_required")
    parquet = _read_bytes(_path(dataset_root, inputs.PARQUET_PATH),
                          sha256=current_plan["dataset"]["parquet_sha256"])
    projections, needs_files = _dataset_tasks(parquet, tuple(config.data_filter.task_ids))
    references = _reference_snapshot(dataset_root, inputs._reference_versions(current_plan), reference_subtree=True)
    return current_plan, plan_data, bound, config, candidate, parquet, projections, needs_files, references


def prepare_pilot_inputs(sources: PilotCaptureSources, *, dataset_root: Path, config_path: Path):
    """Read verified local rows without the general loader's host-path logging."""
    try:
        from prepare_dataset import GDPValTask

        _, _, _, config, _, _, projections, _, _ = _sources(sources, dataset_root, config_path, None)
        return config, [GDPValTask(**row, deliverable_text="", deliverable_files=[]) for row in projections]
    except Exception:
        raise PilotInputCaptureRefused("pilot_preparation_inputs_refused") from None


def read_pilot_prepared(path: Path) -> dict:
    try:
        result = json.loads(_read_bytes(inputs._absolute(path)))
        _require(type(result) is dict, "pilot_prepared_object_required")
        return result
    except Exception:
        raise PilotInputCaptureRefused("pilot_prepared_read_refused") from None


def _workspace(workspace: Path, sources: PilotCaptureSources) -> Path:
    _require(type(sources) is PilotCaptureSources, "pilot_capture_sources_required")
    root = _root(workspace)
    for name, value in vars(sources).items():
        if name not in ("reviewed_source_sha", "as_of"):
            _require(not inputs._overlap(root, inputs._absolute(value)), "pilot_capture_source_overlap")
    return root


def _capture(data: bytes, *, sources: PilotCaptureSources, dataset_root: Path,
             config_path: Path | None = None, plan: dict | None = None) -> bytes:
    from step1_prepare_tasks import _public_codex_config

    (plan, plan_data, bound, config, candidate, parquet, projections,
     needs_files, references) = _sources(sources, dataset_root, config_path, plan)
    prepared = json.loads(data)
    _require(type(prepared) is dict
             and data == json.dumps(prepared, indent=2, ensure_ascii=False).encode("utf-8"),
             "pilot_prepared_serialization_mismatch")
    fingerprint = validate_prepared_fingerprint(prepared)
    generation = validate_publication_generation(prepared.get("publication_generation"))
    tasks = [{
        "task_id": row["task_id"], "sector": row["sector"], "occupation": row["occupation"],
        "instruction": row["prompt"], "reference_files": row["reference_files"],
        "reference_file_records": [{"path": role, **references[role]} for role in row["reference_files"]],
        "reference_file_urls": row["reference_file_urls"], "needs_files": needs_files[row["task_id"]],
        "source_projection_sha256": source_task_projection_sha256(**row),
    } for row in projections]
    execution = {key: config.to_dict()["execution"][key] for key in (
        "mode", "max_retries", "resume_max_rounds", "tokens", "timeout", "sandbox",
    )}
    execution.update(codex=_public_codex_config(config.execution.codex),
                     pilot_input_capture=config.execution.pilot_input_capture.as_dict())
    expected = {
        "experiment_id": config.experiment_id, "publication_generation": generation,
        "experiment_name": config.name, "description": config.description,
        "config_path": deployment.CANDIDATE_PATH, "source": config.data_filter.source,
        "task_scope": {"mode": "explicit_ids", "expected_count": 5, "task_ids": config.data_filter.task_ids},
        "execution": execution, "total_tasks": 5, "needs_files_count": sum(needs_files.values()),
        "text_only_count": 5 - sum(needs_files.values()),
        "condition_a": _prepared_condition(config.condition_a), "condition_b": None, "tasks": tasks,
        "prepared_fingerprint": fingerprint,
    }
    _require(_bytes(prepared) == _bytes(expected), "pilot_prepared_projection_mismatch")
    binding = bound.as_dict()
    result = _bytes({
        **config.execution.pilot_input_capture.as_dict(), "evidence_boundary": BOUNDARY,
        "condition": "codex_foundry", "repeat": 1, "task_ids": config.data_filter.task_ids,
        "prepared": {"path": PREPARED_PATH, **_digest(data),
                     "canonical_sha256": _digest(_bytes(prepared))["sha256"], "fingerprint": fingerprint},
        "tasks": [{"task_id": row["task_id"], "canonical_sha256": _digest(_bytes(row))["sha256"],
                   "prompt": _digest(row["instruction"].encode("utf-8")),
                   "source_projection_sha256": row["source_projection_sha256"],
                   "reference_files": row["reference_file_records"]} for row in tasks],
        "dataset": {"repo_id": plan["dataset"]["repo_id"], "revision": plan["dataset"]["revision"],
                    "parquet": {"path": inputs.PARQUET_PATH, **_digest(parquet)}},
        "requested": {"provider": "azure", "provider_id": config.execution.codex["provider_id"],
                      "model": plan["identity"]["model"], "deployment": config.condition_a.model.deployment,
                      "reasoning_effort": "max", "context_tokens": 1_000_000},
        "candidate_config": {"path": deployment.CANDIDATE_PATH, **_digest(candidate)},
        "active_plan": _digest(plan_data), "contract_sha256": binding["contract_sha256"],
        "upstream_bundles": {**binding["upstream_bundles"], "deployment": {
            "ready": _digest(bound.canonical_bytes()), "reservation": _digest(deployment._reservation(bound)),
        }},
        "reviewed_source_sha": sources.reviewed_source_sha,
    })
    # Projection work must not leave a window in which a now-stale upstream
    # bundle or private ID can be accepted using only the earlier verdict.
    _require(deployment.verify_pilot_deployment_binding(
        plan, bundle_root=sources.deployment_binding, **sources._options(),
    ) == bound, "pilot_upstream_changed_during_capture")
    _read_bytes(pilot.PLAN, **_digest(plan_data))
    return result


def write_pilot_prepared_and_capture(
    sources: PilotCaptureSources, *, workspace: Path, dataset_root: Path,
    config_path: Path, prepared_data: bytes,
) -> None:
    """Exclusive real Step 1 bytes, revalidation, then atomic capture last."""
    try:
        root = _workspace(workspace, sources)
        with _held_parents(root, (PREPARED_PATH, CAPTURE_PATH)) as check:
            _require(not any(os.path.lexists(root / name) for name in (PREPARED_PATH, CAPTURE_PATH)),
                     "pilot_capture_or_partial_exists")
            expected = _capture(prepared_data, sources=sources, dataset_root=dataset_root, config_path=config_path)
            check()
            _write_no_clobber(root / PREPARED_PATH, prepared_data)
            observed = _read_bytes(root / PREPARED_PATH, **_digest(prepared_data))
            _require(_capture(observed, sources=sources, dataset_root=dataset_root, config_path=config_path) == expected,
                     "pilot_inputs_changed_before_capture")
            check()
            _write_no_clobber(root / CAPTURE_PATH, expected)
            _read_bytes(root / PREPARED_PATH, **_digest(prepared_data))
            _read_bytes(root / CAPTURE_PATH, **_digest(expected))
            check()
    except Exception:
        raise PilotInputCaptureRefused("pilot_capture_publication_refused_no_reuse") from None


def verify_pilot_input_capture(
    sources: PilotCaptureSources, *, workspace: Path, dataset_root: Path,
    prepared: dict | None = None, plan: dict | None = None,
    condition_key: str = "condition_a", execution_mode: str | None = None,
    max_retries: int | None = None, resume_max_rounds: int | None = None,
    resume: bool = False, wall_timeout: int | None = None,
) -> dict:
    """Recompute before any runtime construction; return only safe linkage."""
    try:
        _require(condition_key == "condition_a" and resume is False and wall_timeout is None
                 and (execution_mode is None or type(execution_mode) is str and execution_mode == "codex_foundry")
                 and (max_retries is None or type(max_retries) is int and max_retries == 3)
                 and (resume_max_rounds is None or type(resume_max_rounds) is int and resume_max_rounds == 0),
                 "pilot_runtime_override_refused")
        root = _workspace(workspace, sources)
        with _held_parents(root, (PREPARED_PATH, CAPTURE_PATH)) as check:
            data = _read_bytes(root / PREPARED_PATH)
            observed = _read_bytes(root / CAPTURE_PATH)
            if prepared is not None:
                _require(_bytes(prepared) == _bytes(json.loads(data)), "pilot_held_prepared_mismatch")
            expected = _capture(data, sources=sources, dataset_root=dataset_root, plan=plan)
            _require(observed == expected and _digest(observed) == _digest(expected), "pilot_capture_bytes_mismatch")
            _read_bytes(root / PREPARED_PATH, **_digest(data))
            _read_bytes(root / CAPTURE_PATH, **_digest(expected))
            check()
            document = json.loads(expected)
            return {"path": CAPTURE_PATH, **_digest(expected), "binding_version": document["binding_version"],
                    "run_id": pilot.RUN_ID, "prepared_sha256": _digest(data)["sha256"],
                    "reviewed_source_sha": sources.reviewed_source_sha,
                    "upstream_bundles": document["upstream_bundles"], "evidence_boundary": BOUNDARY,
                    "launch_allowed": False, "full_220_allowed": False}
    except Exception:
        raise PilotInputCaptureRefused("pilot_capture_verification_refused") from None
