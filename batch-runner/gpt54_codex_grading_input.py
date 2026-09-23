"""Validate and isolate one externally bound Codex input bundle for step8.

The identity issuer, not this offline function, verifies the publication and
prepared-input provenance. No provider, authentication, or grader is invoked.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import gpt54_v2_grading_input as primitives
from core.cost_projection import project_cost_ledger_reference
from core.inference_manifest import (
    STEP2_PROGRESS_SCHEMA,
    canonicalize_inference_payload,
    validate_step2_progress_results,
)
from core.prepared_fingerprint import FINGERPRINT_RE
from core.publication_generation import validate_publication_generation
from core.result_fingerprint import (
    inference_result_fingerprint,
    validate_inference_result_fingerprint,
)
from core.result_projection import project_result_row
from gpt54_comparison_preflight import ComparisonGradingPlan, ComparisonGradingRunSpec, compile_grading_plan


class CodexGradingInputRefused(ValueError):
    """The source is not the exact, independently approved Codex input."""


def _validate_producer(payload: dict, run: ComparisonGradingRunSpec, config: dict) -> None:
    same = primitives._same
    same("canonical source semantics", canonicalize_inference_payload(payload), payload)
    same("experiment identity", payload["experiment_id"], run.run_id)
    same("experiment name", payload["experiment_name"], config["experiment"]["name"])
    same("dataset declaration", payload["source"], config["data"]["source"])
    same("producer condition", payload["condition"], config["condition_a"]["name"])
    same("condition identity", payload["condition_identity"], "condition_a")
    same("execution mode", payload["execution_mode"], config["execution"]["mode"])
    same("model", payload["model"], config["condition_a"]["model"]["deployment"])
    same("producer task order", payload["ordered_task_ids"], list(run.task_ids))
    same("resume rounds", payload["resume_rounds_used"], 0)
    # The producer's runtime ID is not the comparison's deterministic run ID.
    # Both identities are bound independently below; never rewrite either one.
    for key in ("run_id", "publication_generation"):
        validate_publication_generation(payload[key])
    prepared = payload["prepared_fingerprint"]
    if not isinstance(prepared, str) or FINGERPRINT_RE.fullmatch(prepared) is None:
        raise CodexGradingInputRefused("prepared fingerprint is missing or invalid")
    for key in ("started_at", "completed_at"):
        if not isinstance(payload[key], str) or not payload[key]:
            raise CodexGradingInputRefused(f"terminal producer {key} is missing")

    rows = payload["results"]
    validate_step2_progress_results(rows, schema_version=STEP2_PROGRESS_SCHEMA)
    same("ordered terminal tasks", [row["task_id"] for row in rows], list(run.task_ids))
    for row in rows:
        status = row["status"]
        if status not in ("success", "error"):
            raise CodexGradingInputRefused("nonterminal or QA-failed Codex row")
        if (status == "success") != bool(row["deliverable_files"]):
            raise CodexGradingInputRefused("status contradicts collected deliverables")
        if status == "success" and row.get("error") is not None:
            raise CodexGradingInputRefused("success row carries an error")
        same("row model", row["model"], payload["model"])
        same("reflection attempts", row.get("reflection_attempts", 0), 0)
        same("reflection history", row.get("reflection_history", []), [])
        same("retried", row.get("retried", False), False)
        if row.get("resume_round") is not None:
            raise CodexGradingInputRefused("resumed row is outside this comparison")
        if "deliverable_files_count" in row:
            same("deliverable count", row["deliverable_files_count"], len(row["deliverable_files"]))
        # Validate through the existing projector, but do not replace raw rows:
        # it adds report defaults and normalizes receipts. Source semantics,
        # including absent/null fields, partial reasons and extensions, stay put.
        project_result_row(row, row)
    for key, expected in {
        "total": len(run.task_ids),
        "success": sum(row["status"] == "success" for row in rows),
        "error": sum(row["status"] == "error" for row in rows),
        "qa_failed": 0,
    }.items():
        same(f"terminal summary {key}", payload["summary"][key], expected)


def materialize_codex_grading_input(
    run_spec: ComparisonGradingRunSpec,
    *,
    manifest: dict[str, Any],
    inference_results: Path,
    source_upload: Path,
    inference_identity: Path,
    approved_identity_sha256: str,
    destination: Path,
) -> Path:
    """Install validated step2/upload bytes into an absent isolated bundle root.

    The independently approved document binds the original JSON bytes and
    fingerprint. Only approved source identity fields and the resulting output
    fingerprint are added/updated; every other source field is retained. An
    optional producer ledger is copied verbatim beside the output JSON, never
    repriced or reconstructed. Native no-clobber support is mandatory.
    """
    try:
        if type(run_spec) is not ComparisonGradingRunSpec or run_spec.condition != "codex":
            raise CodexGradingInputRefused("an exact Codex grading run spec is required")
        plan = compile_grading_plan(manifest)
        return _materialize_bound_codex_grading_input(
            run_spec, plan=plan, manifest=manifest, inference_results=inference_results,
            source_upload=source_upload, inference_identity=inference_identity,
            approved_identity_sha256=approved_identity_sha256, destination=destination,
        )
    except CodexGradingInputRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise CodexGradingInputRefused(f"Codex grading input refused: {error}") from error


def _materialize_bound_codex_grading_input(
    run_spec: ComparisonGradingRunSpec,
    *,
    plan: ComparisonGradingPlan,
    manifest: dict[str, Any],
    inference_results: Path,
    source_upload: Path,
    inference_identity: Path,
    approved_identity_sha256: str,
    destination: Path,
) -> Path:
    """Shared checks after a public entry has compiled its exact registered plan.

    This is not an arbitrary-run admission API. The parent entry above and the
    canonical pilot-cell adapter each compile their own plan before reaching it.
    """
    try:
        if type(run_spec) is not ComparisonGradingRunSpec or run_spec.condition != "codex":
            raise CodexGradingInputRefused("an exact Codex grading run spec is required")
        expected = next((run for run in plan.runs if run.run_id == run_spec.run_id), None)
        if expected is None:
            raise CodexGradingInputRefused("unknown comparison run")
        primitives._same("grading run spec", run_spec.as_dict(), expected.as_dict())
        dispatch = next(run for run in plan.dispatch.runs if run.run_id == run_spec.run_id)
        paths = [Path(path) for path in (inference_results, source_upload, inference_identity, destination)]
        if any(".." in path.parts for path in paths):
            raise CodexGradingInputRefused("parent traversal is not allowed")
        inference_results, source_upload, inference_identity, destination = [
            Path(os.path.abspath(path)) for path in paths
        ]
        for path in paths:
            primitives._assert_no_symlink_ancestors(path)
        if os.path.lexists(destination) or not destination.parent.is_dir():
            raise CodexGradingInputRefused("destination exists or its parent is missing")
        for source in (inference_results, source_upload, inference_identity):
            if destination.is_relative_to(source) or source.is_relative_to(destination):
                raise CodexGradingInputRefused("source and destination overlap")

        identity = primitives._read_object(inference_identity, sha256=approved_identity_sha256)
        from step8_grade import resolve_source_inference_identity

        repo_id, revision = resolve_source_inference_identity(identity, "2.0")
        primitives._same("inference repository", identity["source_repo_id"], repo_id)
        primitives._same("inference revision", identity["source_revision"], revision)
        shared = manifest["shared"]
        if repo_id == shared["dataset"]["repo_id"] or revision in {
            shared["dataset"]["revision"], manifest["base_sha"], shared["grading"]["source_sha"],
        }:
            raise CodexGradingInputRefused("dataset/Git provenance is not inference identity")
        payload = primitives._read_object(inference_results, sha256=identity["inference_results_sha256"])
        source_fingerprint = validate_inference_result_fingerprint(payload)
        _validate_producer(payload, run_spec, json.loads(dispatch.config_json))
        rows, files = primitives._snapshot_deliverables(payload["results"], source_upload)
        primitives._same("source file records", rows, payload["results"])

        # Step2 names this sibling after condition_a. Preserve both the pointer
        # and its bytes, rather than producing a dangling reference in the bundle.
        ledger = project_cost_ledger_reference(payload.get("cost_ledger"))
        adjacent_ledger = None
        ledger_binding = None
        if ledger is not None:
            primitives._same("producer ledger reference", payload["cost_ledger"], ledger)
            primitives._same("producer ledger filename", ledger["path"], "cost_ledger_condition_a.jsonl")
            ledger_bytes = primitives._read_bytes(inference_results.parent / ledger["path"], sha256=ledger["sha256"])
            adjacent_ledger = (ledger["path"], ledger_bytes)
            ledger_binding = {**ledger, "size": len(ledger_bytes)}
        expected_identity = {
            "source_repo_id": repo_id, "source_revision": revision,
            "run_id": run_spec.run_id, "condition": run_spec.condition, "repeat": run_spec.repeat,
            "task_ids": list(run_spec.task_ids),
            "producer_results_path": run_spec.producer_results_path,
            "producer_rows_pointer": run_spec.producer_rows_pointer,
            "manifest_sha256": plan.dispatch.manifest_sha256,
            "grading_plan_sha256": hashlib.sha256(plan.canonical_bytes()).hexdigest(),
            "config_sha256": hashlib.sha256(dispatch.config_json.encode("utf-8")).hexdigest(),
            "source_pins_sha256": hashlib.sha256(plan.dispatch.source_pins_json.encode("utf-8")).hexdigest(),
            "inference_results_sha256": identity["inference_results_sha256"],
            "result_fingerprint": source_fingerprint,
            "producer_run_id": payload["run_id"],
            "publication_generation": payload["publication_generation"],
            "prepared_fingerprint": payload["prepared_fingerprint"],
            "deliverables": [{"task_id": row["task_id"], "files": row["deliverable_file_records"]} for row in rows],
            "cost_ledger": ledger_binding,
        }
        primitives._same("approved inference binding", identity, expected_identity)
        additions = {
            "source_repo_id": repo_id, "source_revision": revision,
            "source_identity_document_sha256": approved_identity_sha256,
        }
        for key, value in additions.items():
            if key in payload:
                primitives._same(f"existing {key}", payload[key], value)
        output = {**payload, **additions}
        output["result_fingerprint"] = inference_result_fingerprint(output)
        return primitives._install(destination, output, files, run_spec, adjacent_ledger=adjacent_ledger)
    except CodexGradingInputRefused:
        raise
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        raise CodexGradingInputRefused(f"Codex grading input refused: {error}") from error
