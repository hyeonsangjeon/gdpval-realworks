"""Compile one inert eight-cell retention registration; never launch a cell.

The reviewed runtime base, this unreviewed compiler and the grader template
closure have different identities. Public input provenance is not a reading of
private payloads. No command, scheduler, storage or paid-call path is emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from core.agentic_v2_preregistration import seal
from core.codex_runtime_config import (
    DEFAULT_PROVIDER_ID, PINNED_CODEX_CLI_VERSION, PINNED_CODEX_SDK_VERSION,
)
from core.codex_task_deadline import (
    ATTEMPT_SECONDS, RECOVERY_FAILURE_CATEGORIES, RETENTION_BUNDLE_CONDITION,
    TOTAL_SECONDS, CodexTaskDeadlineControl,
)
from core.execution_envelope_tasks import catalog_sha256, load_task_catalog
from core.experiment_config import ExperimentConfig
from core.repository_identity import validate_experiment_id
from gpt54_comparison_preflight import CODEX_TEMPLATE, GRADER, _canonical_json, load_plan

ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = "batch-runner/experiments/execution_envelope/"
REGISTRATION = ENVELOPE + "codex_retention_diagnostic.yaml"
ORIGINAL_PROFILE = ENVELOPE + "gpt54_sandboxv2_codex_comparison.yaml"
ORIGINAL_REGISTRATION = ENVELOPE + "codex_external_budget_pilot.yaml"
CATALOG = ENVELOPE + "gdpval_task_catalog.json"
COMPILER = "batch-runner/codex_retention_diagnostic.py"
BASE_SHA = "18bc942b97114cca3b9f6ed913b9841dda3a5874"
BASE_TREE = "062d668f967bb9e772f0de353dbef27e99987479"
REVIEWED_HEAD = "610d39c2744be8b8879f884fa0a43abb053ecd44"
# Actual selected baseline file bindings and the full grader-template closure
# at BASE_SHA. Editing registration pins cannot relabel changed runtime bytes.
BASELINE_PIN_SET_SHA256 = "79e958f96ee652a2e79ffe33f606dbde5a46f1d6987e785523b8a3cdc0c563c0"
BASE_GRADER_TEMPLATE_SOURCE_SHA256 = "37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce"
DATASET_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
CAMPAIGN = "retention_bundle_diagnostic_20260929"
TASK4 = "3baa0009-5a60-4ae8-ae99-4955cb328ff3"
TASK5 = "0818571f-5ff7-4d39-9d2c-ced5ae44299e"
ORDER = (
    (TASK4, "keep", 1), (TASK4, "fresh", 1),
    (TASK4, "fresh", 2), (TASK4, "keep", 2),
    (TASK5, "fresh", 1), (TASK5, "keep", 1),
    (TASK5, "keep", 2), (TASK5, "fresh", 2),
)
SOURCE_ROLES = {
    "runtime": (
        "batch-runner/core/codex_runner.py",
        "batch-runner/core/codex_task_deadline.py",
        "batch-runner/core/codex_runtime_config.py",
        "batch-runner/core/executor.py",
        "batch-runner/core/experiment_config.py",
        "batch-runner/step1_prepare_tasks.py",
        "batch-runner/step2_run_inference.py",
    ),
    "compiler": (
        COMPILER,
        "batch-runner/gpt54_comparison_preflight.py",
        "batch-runner/core/agentic_v2_preregistration.py",
        "batch-runner/core/execution_envelope_tasks.py",
    ),
    "input_provenance": (ORIGINAL_PROFILE, ORIGINAL_REGISTRATION, CATALOG, CODEX_TEMPLATE),
    "grader": (GRADER, "batch-runner/step8_grade.py"),
}
LAUNCH_BLOCKERS = (
    "exact_new_controller_head_not_reviewed_or_authorized",
    "private_input_bytes_not_staged_or_reverified_here",
    "serial_execution_and_reservation_controller_not_implemented",
    "live_runtime_and_deployment_consumption_not_verified_here",
    "paid_run_requires_separate_leader_direction",
)


class RetentionRegistrationRefused(ValueError):
    """The supplied bytes cannot describe this closed, offline registration."""


def _same(label: str, actual, expected) -> None:
    # Existing canonical representation preserves types, nulls and list order.
    if _canonical_json(actual) != _canonical_json(expected):
        raise RetentionRegistrationRefused(f"{label}_mismatch")


def _source_pins(registration: dict) -> None:
    pins = registration.get("source_pins")
    if not isinstance(pins, dict) or set(pins) != set(SOURCE_ROLES):
        raise RetentionRegistrationRefused("source_pin_roles")
    for role, paths in SOURCE_ROLES.items():
        if not isinstance(pins[role], dict) or set(pins[role]) != set(paths):
            raise RetentionRegistrationRefused(f"source_pin_set:{role}")
        for name in paths:
            path = ROOT / name
            if (any(part.is_symlink() for part in (path, *path.parents))
                    or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != pins[role][name]):
                raise RetentionRegistrationRefused(f"source_pin:{name}")
    baseline = {name: digest for group in pins.values() for name, digest in group.items()
                if name != COMPILER}
    _same("baseline_source_pins", seal(baseline), BASELINE_PIN_SET_SHA256)


def _inputs() -> dict:
    # These are committed public hashes, not reconstructed private task bytes.
    original = load_plan(ROOT / ORIGINAL_PROFILE)["shared"]["dataset"]
    catalog = load_task_catalog(ROOT / CATALOG)
    _same("dataset_revision", catalog.dataset_revision, DATASET_REVISION)
    _same("dataset_catalog", original["catalog_sha256"], catalog_sha256(ROOT / CATALOG))
    _same("dataset_parquet", original["parquet_sha256"], catalog.dataset_file_sha256)
    by_id = {task.task_id: task for task in catalog.tasks}
    prompts = {task["task_id"]: task["prompt_sha256"] for task in original["tasks"]}
    tasks = []
    for task_id in (TASK4, TASK5):
        task = by_id[task_id]
        _same("original_prompt", task.prompt_sha256, prompts[task_id])
        tasks.append({
            "task_id": task_id, "prompt_sha256": task.prompt_sha256,
            "reference_files": {
                name: original["input_file_versions"][name]
                for name in task.reference_file_paths
            },
        })
    return {
        "repo_id": catalog.dataset_repo_id, "revision": catalog.dataset_revision,
        "parquet_sha256": catalog.dataset_file_sha256,
        "catalog_sha256": catalog_sha256(ROOT / CATALOG), "tasks": tasks,
        "provenance": ORIGINAL_PROFILE,
        "verification_here": "public_provenance_only_no_private_payload_read",
        "before_execution": "original_schema4_manifest_and_exact_task_prompt_reference_bytes_required",
    }


def _contract() -> dict:
    return {
        "plan_version": "codex-retention-diagnostic-registration-v1",
        "campaign_id": CAMPAIGN,
        "runtime_baseline": {
            "source_sha": BASE_SHA, "tree_sha": BASE_TREE,
            "reviewed_head": REVIEWED_HEAD, "review_id": 5345799305,
        },
        "compiler_reviewed": False, "launch_authorized": False,
        "default_mode": "offline_plan_only", "cell_count": 8,
        "runtime_condition": RETENTION_BUNDLE_CONDITION,
        "cells": [
            {"task_id": task, "retention_bundle": bundle, "repetition": repeat}
            for task, bundle, repeat in ORDER
        ],
        "common": {
            "global_inference_slots": 1,
            "cumulative_seconds": TOTAL_SECONDS,
            "native_turn_wait_seconds": ATTEMPT_SECONDS,
            "native_turn_wait_is_all_in_attempt_ceiling": False,
            "max_admissions": None, "restart_outer_clock": False,
            "mechanical_recovery_policy": "B",
            "recovery_failure_categories": sorted(RECOVERY_FAILURE_CATEGORIES),
            "backoff": "existing_B_including_index_restart_on_process_reentry",
            "c_recovery_context": False,
            "model": load_plan(ROOT / ORIGINAL_PROFILE)["shared"]["model"],
            "sdk": "0.147.0", "cli": "0.147.0", "parent_profile": CODEX_TEMPLATE,
            "treatment": ["native_thread", "workspace", "HOME", "CODEX_HOME", "owned_outputs"],
            "shared_temporary_carveouts": "unchanged",
            "cost_policy": "record_known_usage_partial_costs_and_missing_prices_no_automatic_monetary_cap",
        },
        "inputs": _inputs(),
        "grading": {
            "template": GRADER, "rubric_revision": DATASET_REVISION,
            "judge_model": "gpt-5.6-sol", "judge_effort": "max",
            "grades_per_produced_result": 1, "low_score_regrades": 0,
            "no_result_grade": None,
            "fingerprint_role": "template_source_closure_not_materialized_grader_source",
        },
        "analysis": {
            "purpose": "decide_whether_to_consider_a_larger_retention_study",
            "selection": "post_selected_Task4_Task5_after_pilot_not_representative",
            "effect": "thread_and_owned_files_bundle_not_thread_versus_files",
            "preliminary_signal": "keep_only_deliverable_advantage_in_both_pairs_within_a_predeclared_task_and_no_reverse_pair",
            "otherwise": "benefit_not_established",
            "no_recovery_opportunity": "uninformative_about_retention_remains_in_denominator",
            "denominator": 8, "forced_online_faults": False,
            "additional_repeats": False, "automatic_expansion": False,
            "limits": ["two_repetitions", "service_variation", "source_changes_from_original_pilot",
                       "uncalibrated_judge", "post_selection", "no_generic_model_superiority"],
        },
        "recording": [
            "all_eight_cells_including_failed_filtered_expired_and_no_recovery",
            "actual_recovery_opportunity_and_bundle_retention_exposure",
            "durable_admissions_confirmed_native_resumes_recorded_retry_backoff",
            "usage_costs_and_missing_reasons_without_HTTP_call_or_invoice_conversion",
            "snapshot_budget_is_not_exact_uncapped_elapsed_or_all_recovery_time",
            "produced_output_identity_one_selected_grade_or_NG_null_not_zero",
        ],
    }


def compile_plan(registration: dict | None = None) -> dict:
    """Check fixed source/input/control bindings and return canonical plan data."""
    registration = load_plan(ROOT / REGISTRATION) if registration is None else registration
    if not isinstance(registration, dict):
        raise RetentionRegistrationRefused("registration_not_object")
    _source_pins(registration)
    _same("registration", {
        key: value for key, value in registration.items()
        if key not in {"source_pins", "grader_template_source_sha256"}
    }, _contract())
    _same("native_versions", [PINNED_CODEX_SDK_VERSION, PINNED_CODEX_CLI_VERSION],
          ["0.147.0", "0.147.0"])

    # The real helper reads the whole core/requirements/prompt/schema closure.
    # The raw template identity is deliberately not the future generated path.
    from step8_grade import compute_grader_source_hash, validate_grading_config

    grader = load_plan(ROOT / GRADER)
    template_source_hash = compute_grader_source_hash(
        ROOT / GRADER, grader, batch_root=ROOT / "batch-runner",
    )
    _same("grader_baseline_closure", template_source_hash, BASE_GRADER_TEMPLATE_SOURCE_SHA256)
    _same("grader_template_source", registration.get("grader_template_source_sha256"),
          template_source_hash)
    _same("judge", [grader["judge"]["model"], grader["judge"]["reasoning"]["effort"]],
          ["gpt-5.6-sol", "max"])
    grader["rubric"].update(revision=DATASET_REVISION, cache_dir="../data/gdpval-local")
    checked_grader = json.loads(_canonical_json(grader))
    for key in ("template", "tool_template"):
        checked_grader["prompt"][key] = str(ROOT / "batch-runner" / grader["prompt"][key])
    validate_grading_config(checked_grader)

    cells = []
    for task_id, bundle, repeat in ORDER:
        control = CodexTaskDeadlineControl.from_mapping({
            "condition": RETENTION_BUNDLE_CONDITION,
            "retention_bundle": bundle, "repetition": repeat,
        }).as_dict()
        cell_id = f"{task_id}_{RETENTION_BUNDLE_CONDITION}_{bundle}_r{repeat}"
        config = load_plan(ROOT / CODEX_TEMPLATE)
        # Keep the full registered cell identity above. Its runtime experiment
        # ID needs no repeated policy label within this fixed campaign namespace.
        config["experiment"].update(
            id=validate_experiment_id(f"{CAMPAIGN}__{task_id}_{bundle}_r{repeat}"),
            name="GPT-5.4 retention bundle diagnostic",
            description="Inert prospective recipe; no launch authority or new result.",
        )
        model = registration["common"]["model"]
        config["data"]["source"] = registration["inputs"]["repo_id"]
        config["data"]["filter"]["task_ids"] = [task_id]
        config["condition_a"]["model"].update(
            provider=model["provider"], deployment=model["deployment"],
            reasoning_effort=model["reasoning_effort"],
        )
        config["execution"]["codex"].update(
            model=model["deployment"], provider_id=DEFAULT_PROVIDER_ID,
            reasoning_effort=model["reasoning_effort"], model_context_window=None,
            request_max_retries=0, stream_max_retries=0, task_deadline=control,
        )
        # Preserve B's existing compatibility settings. The identity-bound
        # deadline policy, not this legacy retry setting, admits these cells.
        config["execution"].update(timeout=ATTEMPT_SECONDS, max_retries=3, resume_max_rounds=0)
        errors = ExperimentConfig.from_dict(config).validate()
        if errors:
            raise RetentionRegistrationRefused("compiled_config_refused: " + "; ".join(errors))
        cells.append({
            "index": len(cells), "cell_id": cell_id, "task_id": task_id,
            "control": control, "config": config, "config_sha256": seal(config),
        })
    return {
        "plan_version": "codex-retention-diagnostic-plan-v1", "campaign_id": CAMPAIGN,
        "registration_canonical_sha256": seal(registration),
        "runtime_baseline": registration["runtime_baseline"],
        "source_pins": registration["source_pins"], "compiler_reviewed": False,
        "launch_authorized": False, "launch_blockers": list(LAUNCH_BLOCKERS),
        "commands": [], "scheduler_implemented": False,
        "cell_count": 8, "order": [cell["cell_id"] for cell in cells], "cells": cells,
        "common": registration["common"], "inputs": registration["inputs"],
        "grading": {
            **registration["grading"], "template_source_sha256": template_source_hash,
            "generated_config": grader, "generated_config_sha256": seal(grader),
            "materialized_grader_source_sha256": None,
        },
        "analysis": registration["analysis"], "recording": registration["recording"],
    }


def validate_plan(candidate: dict, registration: dict | None = None) -> dict:
    """Refuse edited plans, including a new launch flag or a stale source pin."""
    expected = compile_plan(registration)
    _same("compiled_plan", candidate, expected)
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, default=ROOT / REGISTRATION)
    parser.add_argument("--plan", type=Path, help="Reconcile an existing offline plan; never execute it")
    args = parser.parse_args(argv)
    try:
        registration = load_plan(args.registration)
        plan = (validate_plan(load_plan(args.plan), registration) if args.plan
                else compile_plan(registration))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(_canonical_json({"configuration_valid": False, "launch_authorized": False,
                               "reason": str(error)}))
        return 2
    print(_canonical_json({"configuration_valid": True, "launch_authorized": False,
                           "plan_sha256": seal(plan), "plan": plan}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
