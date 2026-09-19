"""Attest captured canonical inputs, offline and without issuing an identity.

The caller supplies all four pre-execution captures. The comparison-only Codex
and V2 paths emit and check their own captures. Matching a capture to a read-only
snapshot proves consistency, not when it was captured or what a later model
request consumed. Rubrics are source provenance, never model input here.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pyarrow.parquet as parquet

from core.agentic_v2_manifest_binding import BoundManifest, ManifestRefused, bind_stage, binding_record
from core.experiment_config import ExperimentConfig
from core.inference_manifest import _assert_no_symlink_ancestors
from core.needs_files import resolve_needs_files
from core.prepared_fingerprint import validate_prepared_fingerprint
from core.publication_generation import validate_publication_generation
from core.reference_integrity import validate_reference_record, validate_reference_relative_path
from core.source_identity import (
    SOURCE_PROJECTION_FIELDS,
    ordered_source_projection_sha256,
    source_task_projection,
    source_task_projection_sha256,
)
from gpt54_comparison_preflight import (
    ComparisonRunSpec,
    ComparisonGradingPlan,
    _canonical_json,
    catalog_sha256,
    compile_grading_plan,
    load_task_catalog,
    select_advance_check_tasks,
)
from gpt54_v2_grading_input import _object, _read_bytes
from step1_prepare_tasks import _public_codex_config


class PreparedInputRefused(ValueError):
    """The supplied bytes/captures are not the exact preregistered inputs."""


@dataclass(frozen=True)
class PreparedRunInputs:
    """Actual files for one ABBA run; paths are not identity or approval."""

    run_id: str
    generated_config: Path
    input_binding: Path
    prepared_tasks: Path | None = None


@dataclass(frozen=True)
class PreparedInputAttestation:
    document_json: str

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.document_json)

    def canonical_bytes(self) -> bytes:
        return self.document_json.encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def _same(label: str, actual: Any, expected: Any) -> None:
    # Includes key presence, numeric types, list order and null distinctions.
    if _canonical_json(actual) != _canonical_json(expected):
        raise PreparedInputRefused(f"{label} mismatch")


def _identity(data: bytes) -> dict[str, Any]:
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _json_object(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"), object_pairs_hook=_object)
    if not isinstance(value, dict):
        raise PreparedInputRefused("input document must be an object")
    _canonical_json(value)  # Refuse nonfinite numbers, including unused fields.
    return value


def _reference_snapshot(
    root: Path, versions: dict[str, str], *, reference_subtree: bool = False,
) -> dict[str, dict]:
    """Read exactly a cohort-only reference tree, without following links."""
    _assert_no_symlink_ancestors(root)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise PreparedInputRefused("reference root must be a directory")
    directories = {"."}
    for name, digest in versions.items():
        relative = validate_reference_relative_path(name)
        validate_reference_record({"sha256": digest, "size": 0})
        directories.update(parent.as_posix() for parent in relative.parents)
    # Runtime's actual dataset root also contains the pinned parquet. Only the
    # reference_files subtree is consumed as references. The attester's default
    # remains its original strict, reference-only root (including extra dirs).
    scan_root = root / "reference_files" if reference_subtree else root
    _assert_no_symlink_ancestors(scan_root)
    if not stat.S_ISDIR(scan_root.lstat().st_mode):
        raise PreparedInputRefused("reference scan root must be a directory")
    if reference_subtree and any(not name.startswith("reference_files/") for name in versions):
        raise PreparedInputRefused("reference outside the runtime reference subtree")
    found = set()
    for current, children, files in os.walk(scan_root, followlinks=False):
        for name in children:
            path = Path(current) / name
            if not stat.S_ISDIR(path.lstat().st_mode) or path.relative_to(root).as_posix() not in directories:
                raise PreparedInputRefused("unexpected or linked reference directory")
        for name in files:
            relative = (Path(current) / name).relative_to(root).as_posix()
            if relative not in versions:
                raise PreparedInputRefused("unexpected reference file")
            found.add(relative)
    _same("reference file set", sorted(found), sorted(versions))
    return {
        name: _identity(_read_bytes(root / name, sha256=digest))
        for name, digest in sorted(versions.items())
    }


def _dataset_tasks(data: bytes, task_ids: tuple[str, ...]) -> tuple[list[dict], dict[str, bool]]:
    # Hash the held snapshot before parsing. Read only selected row content;
    # physical parquet order is not the registered execution order.
    rows = parquet.read_table(
        io.BytesIO(data), columns=[*SOURCE_PROJECTION_FIELDS, "deliverable_files"],
        filters=[("task_id", "in", list(task_ids))],
    ).to_pylist()
    ids = [row["task_id"] for row in rows]
    _same("selected parquet task set", sorted(ids), sorted(task_ids))
    by_id = {row["task_id"]: row for row in rows}
    projections = []
    needs_files = {}
    for task_id in task_ids:
        row = by_id[task_id]
        projection = source_task_projection(**{key: row[key] for key in SOURCE_PROJECTION_FIELDS})
        # Preserve raw rubric JSON/pretty bytes, but do not accept invalid JSON.
        _canonical_json(json.loads(projection["rubric_json"], object_pairs_hook=_object))
        projections.append(projection)
        # Same default policy as Step 0. This attestation is explicitly limited
        # to deliverable_only; never confuse reference inputs with file outputs.
        files = row["deliverable_files"]
        if files is None:
            files = []
        elif isinstance(files, str):
            files = [files] if files else []
        if not isinstance(files, list) or any(not isinstance(name, str) for name in files):
            raise PreparedInputRefused("invalid source deliverable metadata")
        needs_files[task_id] = resolve_needs_files(bool(files), None, "deliverable_only")
    return projections, needs_files


def _prepared_condition(condition: Any) -> dict | None:
    if condition is None:
        return None
    # Step 1's public projection differs from the config serializer here.
    value = ExperimentConfig._condition_to_dict(condition)
    value["model"].pop("max_tokens")
    value["prompt"]["body"] = condition.prompt.body
    if not condition.qa or not condition.qa.enabled:
        value.pop("qa", None)
    return value


def _check_prepared(
    data: bytes, run: ComparisonRunSpec, projections: list[dict],
    references: dict[str, dict], needs_files: dict[str, bool],
) -> dict[str, Any]:
    prepared = _json_object(data)
    fingerprint = validate_prepared_fingerprint(prepared)
    generation = validate_publication_generation(prepared.get("publication_generation"))
    config = ExperimentConfig.from_dict(json.loads(run.config_json))
    if config.execution.agentic is not None or config.execution.agentic_v2 is not None:
        raise PreparedInputRefused("unexpected Codex execution projection")
    execution = config.to_dict()["execution"]
    execution = {key: execution[key] for key in (
        "mode", "max_retries", "resume_max_rounds", "tokens", "timeout", "sandbox",
    )}
    execution["codex"] = _public_codex_config(config.execution.codex)
    if config.execution.metrics is not None:
        execution["metrics"] = config.execution.metrics
    if config.execution.comparison_input_capture is not None:
        execution["comparison_input_capture"] = config.execution.comparison_input_capture.as_dict()
    tasks = [
        {
            "task_id": row["task_id"], "sector": row["sector"], "occupation": row["occupation"],
            "instruction": row["prompt"], "reference_files": row["reference_files"],
            "reference_file_records": [
                {"path": name, **references[name]} for name in row["reference_files"]
            ],
            "reference_file_urls": row["reference_file_urls"],
            "needs_files": needs_files[row["task_id"]],
            "source_projection_sha256": source_task_projection_sha256(**row),
        }
        for row in projections
    ]
    # config_path is deliberately excluded by the existing prepared fingerprint.
    # Bind actual config bytes separately; do not depend on a host absolute path.
    if not isinstance(prepared.get("config_path"), str) or not prepared["config_path"]:
        raise PreparedInputRefused("prepared config path is missing")
    expected = {
        "experiment_id": config.experiment_id, "experiment_name": config.name,
        "description": config.description, "source": config.data_filter.source,
        "publication_generation": generation,
        "task_scope": {"mode": "explicit_ids", "expected_count": len(tasks), "task_ids": list(run.task_ids)},
        "execution": execution, "total_tasks": len(tasks),
        "needs_files_count": sum(needs_files.values()),
        "text_only_count": len(tasks) - sum(needs_files.values()),
        "condition_a": _prepared_condition(config.condition_a),
        "condition_b": _prepared_condition(config.condition_b), "tasks": tasks,
    }
    _same("prepared task/config projection", {
        key: value for key, value in prepared.items() if key not in {"prepared_fingerprint", "config_path"}
    }, expected)
    return {
        "kind": "codex_step1_tasks", "prepared_fingerprint": fingerprint,
        "publication_generation": generation, "prepared_file": _identity(data),
        "tasks": prepared["tasks"],
    }


@dataclass(frozen=True)
class _SourceSnapshot:
    shared_binding: dict[str, Any]
    sources: list[dict]
    projections: list[dict]
    references: dict[str, dict]
    needs_files: dict[str, bool]
    bound: BoundManifest


def _source_snapshot(
    plan: ComparisonGradingPlan, dataset_parquet: Path, reference_root: Path,
    *, reference_subtree: bool = False,
) -> _SourceSnapshot:
    """One byte-derived source projection for both attestation and capture."""
    dataset = json.loads(plan.dispatch.controls_json)["dataset"]
    catalog = load_task_catalog()
    catalog_digest = catalog_sha256()
    task_ids = select_advance_check_tasks(catalog, catalog_fingerprint=catalog_digest).task_ids
    _same("catalog task order", list(task_ids), [row["task_id"] for row in dataset["tasks"]])
    parquet_data = _read_bytes(dataset_parquet, sha256=dataset["parquet_sha256"])
    projections, needs_files = _dataset_tasks(parquet_data, task_ids)
    bound = bind_stage(
        dataset["cohort"], dataset_tasks=[SimpleNamespace(**row) for row in projections],
        catalog=catalog, catalog_digest=catalog_digest,
    )
    dataset_key = dataset["repo_id"] + "@" + dataset["revision"]
    versions = dict(dataset["input_file_versions"])
    _same("dataset input version", versions.pop(dataset_key), dataset["parquet_sha256"])
    reference_paths = [name for row in projections for name in row["reference_files"]]
    if len(reference_paths) != len(set(reference_paths)):
        raise PreparedInputRefused("duplicate or cross-task reference path")
    _same("registered reference paths", sorted(reference_paths), sorted(versions))
    references = _reference_snapshot(reference_root, versions, reference_subtree=reference_subtree)
    sources = [
        {
            "projection": row, "source_projection_sha256": source_task_projection_sha256(**row),
            "text_bytes": {key: _identity(row[key].encode("utf-8")) for key in (
                "prompt", "rubric_json", "rubric_pretty",
            )},
            "reference_file_records": [{"path": name, **references[name]} for name in row["reference_files"]],
        }
        for row in projections
    ]
    shared_binding = {
        "binding_version": "gpt54-pre-execution-input-v1",
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": _identity(plan.canonical_bytes())["sha256"],
        "source_pins_sha256": _identity(plan.dispatch.source_pins_json.encode("utf-8"))["sha256"],
        "dataset": {
            "repo_id": dataset["repo_id"], "revision": dataset["revision"],
            "catalog_sha256": catalog_digest, "parquet": _identity(parquet_data),
        },
        "task_ids": list(task_ids),
        "ordered_source_projection_sha256": ordered_source_projection_sha256(
            row["source_projection_sha256"] for row in sources
        ),
        "needs_files_policy": "deliverable_only",
    }
    return _SourceSnapshot(shared_binding, sources, projections, references, needs_files, bound)


def _expected_binding(snapshot: _SourceSnapshot, run: ComparisonRunSpec, config_data: bytes, consumer: dict) -> dict:
    if config_data != run.config_json.encode("utf-8"):
        raise PreparedInputRefused("generated config bytes mismatch")
    return {
        **snapshot.shared_binding, "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "harness": run.harness, "provider": run.provider, "model": run.model,
        "reasoning_effort": run.reasoning_effort, "config_sha256": _identity(config_data)["sha256"],
        "consumer": consumer,
    }


def _v2_consumer(snapshot: _SourceSnapshot, bound: BoundManifest | None = None) -> dict:
    """Share the attester's exact projection with the held V2 runtime tasks."""
    if bound is None:
        bound = snapshot.bound
    _same("held V2 manifest", binding_record(bound), binding_record(snapshot.bound))
    consumer = {
        "kind": "sandbox_v2_task_to_run", "manifest_binding": binding_record(bound),
        "tasks": [
            {
                "task_id": task.task_id, "prompt": task.prompt,
                "sector": task.sector, "occupation": task.occupation,
                "reference_files": list(task.reference_files),
                "reference_file_records": [
                    {"path": name, **snapshot.references[name]} for name in task.reference_files
                ],
            }
            for task in bound.tasks
        ],
    }
    # V2 uses catalog reference ordering; Codex uses parquet order. Compare
    # the complete lists, including cardinality, against the byte projection.
    fields = ("task_id", "prompt", "sector", "occupation", "reference_files")
    _same("V2/Codex consumer projection",
          [{key: task[key] for key in fields} for task in consumer["tasks"]],
          [{key: source[key] for key in fields} for source in snapshot.projections])
    return consumer


def compile_prepared_input_attestation(
    *, manifest: dict[str, Any], combined_plan: dict[str, Any],
    dataset_parquet: Path, reference_root: Path, runs: tuple[PreparedRunInputs, ...],
) -> PreparedInputAttestation:
    """Compare all actual snapshots and captures; return bytes, never write.

    Captures must use the exact contract documented in benchmark section
    14.5.3. A claimed verified flag is neither accepted nor treated as approval.
    This does not attest rendered prompts, model service, capture time, future
    consumption, or an inference publication revision.
    """
    try:
        plan = compile_grading_plan(manifest)
        _same("combined dispatch/grading plan", combined_plan, plan.as_dict())
        if not isinstance(runs, tuple) or len(runs) != len(plan.dispatch.runs):
            raise PreparedInputRefused("exactly four typed run inputs are required")
        for supplied, run in zip(runs, plan.dispatch.runs):
            if type(supplied) is not PreparedRunInputs:
                raise PreparedInputRefused("run input is not typed")
            _same("ABBA run input", supplied.run_id, run.run_id)

        snapshot = _source_snapshot(plan, dataset_parquet, reference_root)
        shared_binding = snapshot.shared_binding
        projections, references, needs_files = (
            snapshot.projections, snapshot.references, snapshot.needs_files,
        )
        run_bindings = []
        for supplied, run in zip(runs, plan.dispatch.runs):
            config_data = _read_bytes(supplied.generated_config)
            if config_data != run.config_json.encode("utf-8"):
                raise PreparedInputRefused("generated config bytes mismatch")
            if run.condition == "sandbox_v2":
                if supplied.prepared_tasks is not None:
                    raise PreparedInputRefused("V2 must not substitute Codex prepared inputs")
                consumer = _v2_consumer(snapshot)
            else:
                if supplied.prepared_tasks is None:
                    raise PreparedInputRefused("Codex prepared input is required")
                consumer = _check_prepared(
                    _read_bytes(supplied.prepared_tasks), run, projections, references, needs_files,
                )
            binding_data = _read_bytes(supplied.input_binding)
            expected_binding = _expected_binding(snapshot, run, config_data, consumer)
            _same("captured pre-execution input", _json_object(binding_data), expected_binding)
            run_bindings.append({
                "binding": expected_binding, "binding_file": _identity(binding_data),
                "generated_config": {"path": run.config_path, **_identity(config_data)},
            })
        return PreparedInputAttestation(_canonical_json({
            "attestation_version": "gpt54-prepared-input-attestation-v1",
            "evidence_boundary": "offline_snapshot_and_supplied_capture_consistency",
            "manifest_sha256": plan.dispatch.manifest_sha256,
            "combined_plan_sha256": shared_binding["combined_plan_sha256"],
            "source_pins": json.loads(plan.dispatch.source_pins_json),
            "dataset": shared_binding["dataset"], "task_ids": shared_binding["task_ids"],
            "source_tasks": snapshot.sources,
            "ordered_source_projection_sha256": shared_binding["ordered_source_projection_sha256"],
            "runs": run_bindings,
        }))
    except PreparedInputRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ManifestRefused) as error:
        # Do not echo raw input, prompts, file contents or any claimed identity.
        raise PreparedInputRefused("prepared input attestation refused") from error


def validate_prepared_input_attestation(
    attestation: bytes, *, manifest: dict[str, Any], combined_plan: dict[str, Any],
    dataset_parquet: Path, reference_root: Path, runs: tuple[PreparedRunInputs, ...],
) -> PreparedInputAttestation:
    """Recompute from actual input snapshots and require canonical byte equality."""
    expected = compile_prepared_input_attestation(
        manifest=manifest, combined_plan=combined_plan, dataset_parquet=dataset_parquet,
        reference_root=reference_root, runs=runs,
    )
    if type(attestation) is not bytes or attestation != expected.canonical_bytes():
        raise PreparedInputRefused("attestation bytes mismatch")
    return expected
