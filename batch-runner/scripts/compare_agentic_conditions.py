#!/usr/bin/env python3
"""Compute preregistered paired Agentic Sandbox endpoints from frozen JSON."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_budget import AgenticBudgetLedger  # noqa: E402
from core.agentic_endpoints import compute_paired_endpoints  # noqa: E402


FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _read(path):
    content = Path(path).read_bytes()
    return json.loads(content), hashlib.sha256(content).hexdigest()


def _canonical_sha256(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _validate_scope(scopes, documents, hashes):
    required = {
        "schema_version", "paired_run_id", "ordered_task_ids",
        "dataset_revision", "rubric_commit", "baseline_inference_revision",
        "treatment_inference_revision", "judge_config_hash", "prompt_version",
        "grader_source_hash", "baseline_task_scopes",
        "treatment_task_scopes", "artifact_sha256", "sha256",
    }
    if not isinstance(scopes, dict) or set(scopes) != required:
        raise ValueError("budget scope manifest fields are invalid")
    canonical = {key: value for key, value in scopes.items() if key != "sha256"}
    if (
        scopes["schema_version"] != "agentic-budget-scope-manifest-v2"
        or scopes["sha256"] != _canonical_sha256(canonical)
    ):
        raise ValueError("budget scope manifest identity is invalid")
    ordered = scopes["ordered_task_ids"]
    if (
        not isinstance(scopes["paired_run_id"], str)
        or not scopes["paired_run_id"]
        or not isinstance(ordered, list)
        or len(ordered) != 20
        or len(ordered) != len(set(ordered))
        or any(not isinstance(task_id, str) or not task_id for task_id in ordered)
    ):
        raise ValueError("paired scope task identity is invalid")
    for field in (
        "dataset_revision", "rubric_commit", "baseline_inference_revision",
        "treatment_inference_revision",
    ):
        if FULL_COMMIT_RE.fullmatch(str(scopes[field])) is None:
            raise ValueError(f"paired scope {field} is invalid")
    if FULL_SHA256_RE.fullmatch(str(scopes["grader_source_hash"])) is None:
        raise ValueError("paired scope grader source hash is invalid")
    if not all(
        isinstance(scopes[field], str) and scopes[field]
        for field in ("judge_config_hash", "prompt_version")
    ):
        raise ValueError("paired grade configuration identity is invalid")
    expected_names = {
        "task_manifest", "baseline_results", "treatment_results",
        "rubric_maxima", "baseline_grades", "treatment_grades",
    }
    if (
        not isinstance(scopes["artifact_sha256"], dict)
        or set(scopes["artifact_sha256"]) != expected_names
        or any(
            FULL_SHA256_RE.fullmatch(str(value)) is None
            for value in scopes["artifact_sha256"].values()
        )
        or scopes["artifact_sha256"] != hashes
    ):
        raise ValueError("paired artifact byte identity mismatch")

    manifest = documents["task_manifest"]
    if (
        manifest.get("diagnostic_task_ids") != ordered
        or (manifest.get("dataset") or {}).get("revision")
        != scopes["dataset_revision"]
        or (manifest.get("rubric") or {}).get("revision")
        != scopes["rubric_commit"]
    ):
        raise ValueError("task manifest provenance mismatch")
    maxima = documents["rubric_maxima"]
    if (
        not isinstance(maxima, dict)
        or set(maxima) != {"schema_version", "rubric_commit", "tasks"}
        or maxima["schema_version"] != "agentic-rubric-maxima-v1"
        or maxima["rubric_commit"] != scopes["rubric_commit"]
        or set(maxima["tasks"]) != set(ordered)
    ):
        raise ValueError("rubric maxima provenance mismatch")

    _validate_results(
        documents["baseline_results"], scopes, "exp029", "baseline",
        "sandbox",
    )
    _validate_results(
        documents["treatment_results"], scopes, "exp030", "treatment",
        "agentic_sandbox",
    )
    _validate_grade(
        documents["baseline_grades"], scopes, "exp029",
        scopes["baseline_inference_revision"],
    )
    _validate_grade(
        documents["treatment_grades"], scopes, "exp030",
        scopes["treatment_inference_revision"],
    )


def _validate_results(document, scopes, experiment_id, condition, mode):
    expected = {
        "experiment_id": experiment_id,
        "condition_identity": condition,
        "execution_mode": mode,
        "run_id": scopes["paired_run_id"],
        "ordered_task_ids": scopes["ordered_task_ids"],
    }
    if not isinstance(document, dict) or any(
        document.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(f"{condition} inference provenance mismatch")
    results = document.get("results")
    if not isinstance(results, list) or [
        result.get("task_id") for result in results if isinstance(result, dict)
    ] != scopes["ordered_task_ids"]:
        raise ValueError(f"{condition} inference task order mismatch")


def _validate_grade(document, scopes, experiment_id, inference_revision):
    expected = {
        "experiment_id": experiment_id,
        "source_inference_experiment_id": experiment_id,
        "source_inference_revision": inference_revision,
        "grader_source_hash": scopes["grader_source_hash"],
    }
    if not isinstance(document, dict) or any(
        document.get(key) != value for key, value in expected.items()
    ):
        raise ValueError(f"{experiment_id} grade provenance mismatch")
    if (
        (document.get("rubric") or {}).get("commit_sha")
        != scopes["rubric_commit"]
        or (document.get("judge") or {}).get("config_hash")
        != scopes["judge_config_hash"]
        or (document.get("prompt") or {}).get("version")
        != scopes["prompt_version"]
    ):
        raise ValueError(f"{experiment_id} grade configuration mismatch")
    tasks = document.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError(f"{experiment_id} grade tasks are invalid")
    task_ids = [task.get("task_id") for task in tasks if isinstance(task, dict)]
    if len(task_ids) != len(set(task_ids)) or not set(task_ids) <= set(
        scopes["ordered_task_ids"]
    ):
        raise ValueError(f"{experiment_id} grade task identity mismatch")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-manifest", required=True)
    parser.add_argument("--baseline-results", required=True)
    parser.add_argument("--treatment-results", required=True)
    parser.add_argument("--rubric-maxima", required=True)
    parser.add_argument("--baseline-grades", required=True)
    parser.add_argument("--treatment-grades", required=True)
    parser.add_argument("--budget-ledger", required=True)
    parser.add_argument("--scope-manifest", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    input_paths = {
        "task_manifest": args.task_manifest,
        "baseline_results": args.baseline_results,
        "treatment_results": args.treatment_results,
        "rubric_maxima": args.rubric_maxima,
        "baseline_grades": args.baseline_grades,
        "treatment_grades": args.treatment_grades,
    }
    loaded = {name: _read(path) for name, path in input_paths.items()}
    documents = {name: value[0] for name, value in loaded.items()}
    hashes = {name: value[1] for name, value in loaded.items()}
    scopes, _ = _read(args.scope_manifest)
    _validate_scope(scopes, documents, hashes)
    endpoints = compute_paired_endpoints(
        expected_task_ids=scopes["ordered_task_ids"],
        baseline_results=documents["baseline_results"]["results"],
        treatment_results=documents["treatment_results"]["results"],
        rubric_maxima=documents["rubric_maxima"]["tasks"],
        baseline_grades=documents["baseline_grades"],
        treatment_grades=documents["treatment_grades"],
        budget_ledger=AgenticBudgetLedger(args.budget_ledger),
        paired_run_id=scopes["paired_run_id"],
        baseline_task_scopes=scopes["baseline_task_scopes"],
        treatment_task_scopes=scopes["treatment_task_scopes"],
    )
    endpoints["provenance"] = {
        key: scopes[key]
        for key in (
            "paired_run_id", "ordered_task_ids", "dataset_revision",
            "rubric_commit", "baseline_inference_revision",
            "treatment_inference_revision", "judge_config_hash",
            "prompt_version", "grader_source_hash", "artifact_sha256",
            "sha256",
        )
    }
    Path(args.output).write_text(
        json.dumps(endpoints, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()