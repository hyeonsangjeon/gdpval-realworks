"""Validate the Foundry Sol pilot registration offline; never launch a run.

Exit 2 is intentional even for a valid registration. A supported provider path
does not verify a deployment's identity, Max, Long 1M, limits, or tariff.
This check neither reads credentials nor opens an existing paid workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from core.agentic_v2_preregistration import seal
from core.azure_ai_clients import DIRECT_TOKEN_SCOPE
from core.codex_runtime_config import (
    DEFAULT_AUTH_MODULE,
    DEFAULT_PROVIDER_ID,
    PINNED_CODEX_CLI_VERSION,
    PINNED_CODEX_SDK_VERSION,
    requested_model_config_overrides,
)
from core.cost_receipts import RECEIPT_SCHEMA_VERSION
from core.execution_envelope_tasks import (
    catalog_sha256,
    load_task_catalog,
    select_advance_check_tasks,
)
from core.experiment_config import ExperimentConfig
from gpt54_comparison_preflight import load_plan

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "5cbbe3d90d491fde71c268629bdeacc8917ad937"
GRADER_SOURCE_SHA = "6ccd4ae346d302e3da0af455a3c5a72ec79a6984"
ENVELOPE = "batch-runner/experiments/execution_envelope/"
ACTIVE_PLAN = ENVELOPE + "gpt56_sol_foundry_codex_pilot.yaml"
HISTORICAL_PLAN = ENVELOPE + "gpt56_sol_copilot_codex_pilot.yaml"
PLAN = ROOT / ACTIVE_PLAN
RUN_ID = "gpt56_sol_foundry_codex_pilot5_v1"
BASELINE = "batch-runner/experiments/exp035_codex_foundry_full220.yaml"
GRADER = "batch-runner/grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"
EVIDENCE_INTAKE = {
    "schema": "batch-runner/schemas/foundry-pilot-evidence.schema.json",
    "compiler": "batch-runner/gpt56_foundry_evidence_intake.py",
    "source_base_sha": "d8fd52d9c75687a8e088748c589f9a9a07834a41",
    "ready_marker": "foundry-pilot-evidence-ready.json",
    "required_roles": ["identity", "reasoning", "context", "native_caps", "usage", "tariff"],
    "evidence_boundary": "offline_local_consistency",
}
EVIDENCE_SOURCES = {
    EVIDENCE_INTAKE["schema"],
    EVIDENCE_INTAKE["compiler"],
    "batch-runner/gpt54_codex_input_capture.py",
    "batch-runner/gpt54_run_config_bundle.py",
    "batch-runner/gpt54_v2_grading_input.py",
    "batch-runner/core/inference_manifest.py",
    "batch-runner/core/reference_integrity.py",
}
REQUIRED_SOURCES = {
    BASELINE,
    GRADER,
    ENVELOPE + "gdpval_task_catalog.json",
    ENVELOPE + "advance_check_plan.yaml",
    HISTORICAL_PLAN,
    "batch-runner/gpt54_comparison_preflight.py",
    "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    "batch-runner/core/agentic_v2_preregistration.py",
    "batch-runner/core/execution_envelope_tasks.py",
    "batch-runner/core/azure_ai_clients.py",
    "batch-runner/core/codex_azure_token.py",
    "batch-runner/requirements.txt",
    "batch-runner/core/experiment_config.py",
    "batch-runner/core/config.py",
    "batch-runner/core/codex_runtime_config.py",
    "batch-runner/core/codex_runner.py",
    "batch-runner/core/codex_cost.py",
    "batch-runner/core/executor.py",
    "batch-runner/step1_prepare_tasks.py",
    "batch-runner/step2_run_inference.py",
    "batch-runner/core/cost_receipts.py",
    "batch-runner/core/result_projection.py",
    "batch-runner/schemas/grade.schema.json",
} | EVIDENCE_SOURCES
# Findings on BASE_SHA, not editable waivers. Runtime changes need new review.
LAUNCH_BLOCKERS = (
    "foundry_account_project_deployment_identity_unverified",
    "foundry_served_model_version_unverified",
    "max_and_long_1m_capability_unverified",
    "native_call_and_token_limits_unresolved",
    "live_identity_and_input_bytes_unverified",
    "pilot_dispatch_and_grading_identity_not_wired",
    "foundry_usage_and_tariff_mapping_unverified",
    "native_sandbox_and_result_bundle_host_unverified",
    "actual_pilot_deployment_not_prepared",
)


def _registration_problems() -> list[str]:
    """Keep one active pilot; the old provider contract is retained, not routed."""
    paths = sorted((ROOT / ENVELOPE).glob("gpt56_sol_*_codex_pilot.yaml"))
    if {path.relative_to(ROOT).as_posix() for path in paths} != {
        ACTIVE_PLAN, HISTORICAL_PLAN,
    }:
        return ["pilot_registration_set"]
    registrations = {path.relative_to(ROOT).as_posix(): load_plan(path) for path in paths}
    active = [name for name, plan in registrations.items() if plan.get("status") == "active"]
    problems = []
    if active != [ACTIVE_PLAN] or registrations[ACTIVE_PLAN].get("pilot", {}).get("run_id") != RUN_ID:
        problems.append("active_pilot_identity")
    historical = registrations[HISTORICAL_PLAN]
    if (
        historical.get("status") != "superseded"
        or historical.get("superseded_by") != ACTIVE_PLAN
        or historical.get("launch_enabled") is not False
        or historical.get("pilot", {}).get("full_220_enabled") is not False
    ):
        problems.append("historical_pilot_not_retired")
    return problems


def inspect_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Check declared controls against existing sources, not live capabilities."""
    baseline = ExperimentConfig.from_yaml(str(ROOT / BASELINE))
    envelope = load_plan(ROOT / ENVELOPE / "advance_check_plan.yaml")
    grader = load_plan(ROOT / GRADER)
    catalog = load_task_catalog()
    selection = select_advance_check_tasks(catalog)
    tasks = {task.task_id: task for task in catalog.tasks}
    expected = {
        "plan_version": "gpt56-sol-foundry-codex-pilot-v1",
        "status": "active",
        "supersedes": HISTORICAL_PLAN,
        "base_sha": BASE_SHA,
        "baseline": BASELINE,
        "owner_approved_eventual_execution": True,
        "launch_enabled": False,
        "evidence_intake": EVIDENCE_INTAKE,
        "identity": {
            "provider": "azure",
            "model": "gpt-5.6-sol",
            "model_label": "GPT-5.6 Sol",
            "fast_mode": False,
            "harness": "codex",
            "sdk_version": PINNED_CODEX_SDK_VERSION,
            "cli_version": PINNED_CODEX_CLI_VERSION,
            "reasoning_effort": "max",
            "context_tier": "long",
            "context_label": "Long (1M)",
            "nominal_context_tokens": 1_000_000,
            "verified_route": None,
            "verified_model_id": None,
            "verified_context_tokens": None,
            "automatic_fallback_allowed": False,
            "fallbacks": [],
        },
        "foundry_route": {
            "execution_mode": "codex_foundry",
            "route_profile": "direct-v1",
            "endpoint_from_route": True,
            "provider_id": DEFAULT_PROVIDER_ID,
            "auth_module": DEFAULT_AUTH_MODULE,
            "auth_scope": DIRECT_TOKEN_SCOPE,
            "credential_policy": "repository_approved_entra_only",
            "require_expected_identities": True,
        },
        # A model label is not a deployment name or externally reviewed evidence.
        # No endpoint/account/credential values are committed or resolved here.
        "foundry_identity": {
            "account": None,
            "project": None,
            "deployment": None,
            "served_model": None,
            "served_model_version": None,
            "identity_evidence_sha256": None,
            "capability_evidence_sha256": None,
        },
        "codex_request": {
            "reasoning_effort": "max",
            "model_context_window": 1_000_000,
        },
        "pilot": {
            "run_id": RUN_ID,
            "cohort": "advance_check_5",
            "task_count": 5,
            "repeats": 1,
            "fresh_session_per_attempt": True,
            "relay_max_runs": 0,
            "auto_escalation": False,
            "full_220_enabled": False,
        },
        "dataset": {
            "repo_id": catalog.dataset_repo_id,
            "revision": catalog.dataset_revision,
            "parquet_sha256": catalog.dataset_file_sha256,
            "catalog_sha256": catalog_sha256(),
            "tasks": [
                {"task_id": task_id, "prompt_sha256": tasks[task_id].prompt_sha256}
                for task_id in selection.task_ids
            ],
            "input_file_versions": envelope["model_run_conditions"]["shared"][
                "input_file_versions"
            ],
        },
        "developer_instructions": baseline.condition_a.prompt.system,
        "limits": {
            "timeout_seconds_per_attempt": baseline.execution.timeout,
            "infrastructure_retries_per_task": baseline.execution.max_retries,
            "logical_turns_per_attempt": 1,
            "request_max_retries": baseline.execution.codex["request_max_retries"],
            "stream_max_retries": baseline.execution.codex["stream_max_retries"],
            "resume_max_rounds": baseline.execution.resume_max_rounds,
            "self_qa_enabled": baseline.condition_a.qa.enabled,
            "inactive_generic_token_settings": baseline.execution.tokens,
            "native_model_calls_per_attempt": None,
            "native_input_tokens_per_attempt": None,
            "native_output_tokens_per_attempt": None,
        },
        "grading": {
            "template": GRADER,
            "source_sha": GRADER_SOURCE_SHA,
            "rubric_revision": grader["rubric"]["revision"],
            "prompt_version": grader["prompt"]["version"],
            "judge_model": grader["judge"]["model"],
            "judge_effort": grader["judge"]["reasoning"]["effort"],
            "passes_per_task": 1,
            "pilot_expected_task_count": 5,
            "inference_revision": None,
            "reuse_baseline_rerun_identity": False,
        },
        "results": {
            "projector": "core.result_projection.project_result_row",
            "receipt_schema": RECEIPT_SCHEMA_VERSION,
            "grade_schema": "batch-runner/schemas/grade.schema.json",
            "grade_schema_version": "1.4",
            "missing_or_unpriced_usage": "preserve_null_and_partial_reasons",
            "publish_to_hf": baseline.output.publish_to_hf,
            "submit_to_evals": baseline.output.submit_to_evals,
        },
        "cost": {
            "policy": envelope["cost"]["policy"],
            "approved_maximum_usd": None,
            "usage_adapter": "core.codex_cost",
            "foundry_tariff_evidence_sha256": None,
            "use_openai_or_copilot_tariff_for_foundry": False,
            "billing_evidence": "provider_native_usage_without_invented_currency_conversion",
        },
    }
    # Canonical JSON comparison also distinguishes False from 0 and absence
    # from null. An added configuration field cannot silently become a waiver.
    problems = [
        name for name, value in expected.items()
        if seal({"value": plan.get(name)}) != seal({"value": value})
    ]
    if set(plan) != set(expected) | {"source_pins"}:
        problems.append("plan_key_set")
    problems.extend(_registration_problems())
    pins = plan.get("source_pins")
    if not isinstance(pins, dict) or set(pins) != REQUIRED_SOURCES:
        problems.append("source_pin_set")
    else:
        for name, digest in pins.items():
            path = ROOT / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                problems.append(f"source_pin:{name}")
    return {
        "configuration_valid": not problems,
        "configuration_problems": problems,
        "plan_sha256": seal(plan),
        # These are client requests, not proof of a served Foundry capability.
        "requested_codex_config_overrides": (
            list(requested_model_config_overrides(**plan["codex_request"]))
            if not problems else None
        ),
        "launch_allowed": False,
        "full_220_allowed": False,
        "launch_blockers": list(LAUNCH_BLOCKERS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args(argv)
    try:
        result = inspect_plan(load_plan(args.plan))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        result = {
            "configuration_valid": False,
            "launch_allowed": False,
            "full_220_allowed": False,
            "error": str(error),
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2  # No paid pilot or 220-task run can be launched by this module.


if __name__ == "__main__":
    raise SystemExit(main())
