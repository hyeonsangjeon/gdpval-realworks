"""Validate the Foundry Sol pilot registration offline; never launch a run.

Exit 2 is intentional even for a valid registration. A supported provider path
does not verify a deployment's identity, Max, Long 1M, limits, or tariff.
This check neither reads credentials nor opens an existing paid workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
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
from gpt54_comparison_preflight import _canonical_json, load_plan

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
DISPATCH_GRADING_IDENTITY = {
    "compiler": "batch-runner/gpt56_pilot_identity_plan.py",
    "source_base_sha": "ed6c64f0afb90b0b3a6a9e4719e44184384296ec",
    "plan_file": "foundry-pilot-identity-plan.json",
    "ready_marker": "foundry-pilot-identity-ready.json",
    "grader_template_source_hash": "49f882c8b4e19d60c91130431fa06393d9da7d96b15aff25b16755136298f8bc",
    "evidence_boundary": "offline_dispatch_grading_identity",
}
IDENTITY_SOURCES = {
    DISPATCH_GRADING_IDENTITY["compiler"],
    "batch-runner/step8_grade.py",
    "batch-runner/core/grader.py",
    "batch-runner/core/rubric_loader.py",
    "batch-runner/core/grade_payload.py",
    "batch-runner/prompts/grader_judge.md",
    "batch-runner/prompts/grader_judge_v2.md",
}
CONFIG_BUNDLE = {
    "materializer": "batch-runner/gpt56_pilot_config_bundle.py",
    "source_base_sha": "1c038f8f46df3936228cbeb7bc36a0b8aef61337",
    "ready_marker": "pilot-config-bundle-ready.json",
    "evidence_boundary": "offline_pilot_config_bundle",
}
INPUT_BUNDLE = {
    "materializer": "batch-runner/gpt56_pilot_input_bundle.py",
    "source_base_sha": "845d721886e599b06077da8f3524db9cba8520f0",
    "ready_marker": "pilot-input-bundle-ready.json",
    "evidence_boundary": "local_prepared_input_consistency_not_model_consumption",
}
INPUT_SOURCES = {
    INPUT_BUNDLE["materializer"],
    "batch-runner/gpt54_prepared_input_attestation.py",
    "batch-runner/gpt54_run_input_bundle.py",
    "batch-runner/core/source_identity.py",
    "batch-runner/core/needs_files.py",
}
DEPLOYMENT_BINDING = {
    "materializer": "batch-runner/gpt56_pilot_deployment_binding.py",
    "source_base_sha": "9cda8a92040d6679cbfe7f83bca73b0fe657484f",
    "ready_marker": "pilot-deployment-binding-ready.json",
    "evidence_boundary": "offline_deployment_resource_binding_not_launch_or_execution",
}
DEPLOYMENT_SOURCES = {
    DEPLOYMENT_BINDING["materializer"],
    "batch-runner/core/repository_identity.py",
    "batch-runner/core/agentic_experiments.py",
}
PRE_EXECUTION_CAPTURE = {
    "compiler": "batch-runner/gpt56_pilot_input_capture.py",
    "source_base_sha": "140cbf4eef59a2b3c6ee731ac3dd4c75d9e005d7",
    "capture_file": "pilot-pre-execution-input.json",
    "binding_version": "gpt56-pre-execution-input-v1",
    "evidence_boundary": "prepared_request_intent_not_wire_or_served_identity",
}
CAPTURE_SOURCES = {
    PRE_EXECUTION_CAPTURE["compiler"],
    "batch-runner/core/prepared_fingerprint.py",
    "batch-runner/core/publication_generation.py",
    "batch-runner/core/data_loader.py",
    "batch-runner/prepare_dataset.py",
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
} | EVIDENCE_SOURCES | IDENTITY_SOURCES | INPUT_SOURCES | DEPLOYMENT_SOURCES | CAPTURE_SOURCES | {CONFIG_BUNDLE["materializer"]}
# Findings on BASE_SHA, not editable waivers. Runtime changes need new review.
LAUNCH_BLOCKERS = (
    "foundry_account_project_deployment_identity_unverified",
    "foundry_served_model_version_unverified",
    "max_and_long_1m_capability_unverified",
    "native_call_and_token_limits_unresolved",
    "prepared_input_bytes_unverified",
    "live_inference_identity_and_wire_unverified",
    "pilot_dispatch_and_grading_identity_not_wired",
    "foundry_usage_and_tariff_mapping_unverified",
    "native_sandbox_and_result_bundle_host_unverified",
    "actual_pilot_deployment_not_prepared",
    "prepared_request_capture_unverified",
)
# Only these local evidence requirements may be satisfied by the intake
# verifier. The mapping is closed, not inferred from blocker-name substrings.
EVIDENCE_BLOCKER_ROLES = {
    "foundry_account_project_deployment_identity_unverified": ("identity",),
    "foundry_served_model_version_unverified": ("identity",),
    "max_and_long_1m_capability_unverified": ("reasoning", "context"),
    "native_call_and_token_limits_unresolved": ("native_caps",),
    "foundry_usage_and_tariff_mapping_unverified": ("usage", "tariff"),
}
EVIDENCE_REFUSAL = "foundry_evidence_gate_refused"
IDENTITY_REFUSAL = "pilot_identity_plan_gate_refused"
# A verified inert plan closes one local contract requirement, not dispatch.
IDENTITY_PLAN_BLOCKERS = ("pilot_dispatch_and_grading_identity_not_wired",)
INPUT_BUNDLE_BLOCKERS = ("prepared_input_bytes_unverified",)
INPUT_REFUSAL = "pilot_input_bundle_gate_refused"
DEPLOYMENT_BINDING_BLOCKERS = ("actual_pilot_deployment_not_prepared",)
DEPLOYMENT_REFUSAL = "pilot_deployment_binding_gate_refused"
CAPTURE_BLOCKERS = ("prepared_request_capture_unverified",)
CAPTURE_REFUSAL = "pilot_pre_execution_capture_gate_refused"


class _CLIArgumentsRefused(ValueError):
    """An argument error cannot safely identify the caller's intended mode."""


class _SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # Never repeat arguments that might contain evidence or credentials.
        raise _CLIArgumentsRefused(EVIDENCE_REFUSAL)


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


def _inspect_plan_only(plan: dict[str, Any]) -> dict[str, Any]:
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
        "dispatch_grading_identity": DISPATCH_GRADING_IDENTITY,
        "config_bundle": CONFIG_BUNDLE,
        "input_bundle": INPUT_BUNDLE,
        "deployment_binding": DEPLOYMENT_BINDING,
        "pre_execution_capture": PRE_EXECUTION_CAPTURE,
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


def _evidence_refusal(result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep every blocker and expose no unverified input or exception value."""
    if result is None:
        result = {"configuration_valid": False}
    result.update({
        "launch_allowed": False,
        "full_220_allowed": False,
        "launch_blockers": list(LAUNCH_BLOCKERS),
        "evidence_gate": {
            "evidence_complete": False,
            "consumed_bundle_sha256": None,
            "reviewed_source_sha": None,
            "evaluated_at": None,
            "cleared_blockers": [],
            "remaining_blockers": list(LAUNCH_BLOCKERS),
            "evidence_boundary": EVIDENCE_INTAKE["evidence_boundary"],
            "refusal_code": EVIDENCE_REFUSAL,
        },
    })
    return result


def _inspect_plan_with_evidence(
    plan: dict[str, Any], *, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
) -> dict[str, Any]:
    """Inspect a plan, optionally consuming a published local evidence bundle.

    All three evidence arguments must be explicit. With all absent/null, the
    legacy report and verifier-free path are unchanged. Verification is read
    only and satisfies local evidence requirements, never launch authorization.
    Refused evidence retains every blocker and returns a static refusal code.
    """
    if evidence_bundle is None and reviewed_source_sha is None and as_of is None:
        return _inspect_plan_only(plan)
    result = None
    try:
        result = _inspect_plan_only(plan)
        if (not result["configuration_valid"] or evidence_bundle is None
                or type(reviewed_source_sha) is not str or type(as_of) is not str):
            return _evidence_refusal(result)
        # Intake calls inspect_plan(plan) to validate its own active plan. A
        # lazy import and the no-evidence branch above avoid recursive intake.
        from gpt56_foundry_evidence_intake import verify_foundry_evidence

        bundle = verify_foundry_evidence(
            bundle_root=evidence_bundle, reviewed_source_sha=reviewed_source_sha, as_of=as_of,
        )
        document = bundle.as_dict()
        expected_binding = {
            "bundle_version": "foundry-pilot-evidence-ready-v1",
            "evidence_boundary": EVIDENCE_INTAKE["evidence_boundary"],
            "reviewed_source_sha": reviewed_source_sha,
            "plan_base_sha": plan["base_sha"],
            "plan_sha256": result["plan_sha256"],
            "run_id": RUN_ID,
            "source_pins": plan["source_pins"],
            "evidence_complete": True,
            "missing_evidence": [],
            "launch_enabled": False,
            "full_220_enabled": False,
            "remaining_launch_blockers": list(LAUNCH_BLOCKERS),
        }
        if bundle.missing or any(
            seal({"value": document.get(key)}) != seal({"value": value})
            for key, value in expected_binding.items()
        ):
            return _evidence_refusal(result)
        # The real verifier checked each role's schema, observations and bytes.
        # Select only the explicitly mapped requirements from that complete set.
        roles = {role for required in EVIDENCE_BLOCKER_ROLES.values() for role in required}
        if set(document["claims"]) != roles:
            return _evidence_refusal(result)
        cleared = [name for name in LAUNCH_BLOCKERS if name in EVIDENCE_BLOCKER_ROLES]
        remaining = [name for name in LAUNCH_BLOCKERS if name not in EVIDENCE_BLOCKER_ROLES]
        result["launch_blockers"] = remaining
        result["evidence_gate"] = {
            "evidence_complete": True,
            "consumed_bundle_sha256": bundle.sha256,
            "reviewed_source_sha": reviewed_source_sha,
            # Reverification uses the supplied time, not the original intake time.
            "evaluated_at": as_of,
            "cleared_blockers": cleared,
            "remaining_blockers": remaining,
            "evidence_boundary": EVIDENCE_INTAKE["evidence_boundary"],
        }
        return result
    except Exception:
        # This trust boundary must not render parser/verifier exception text.
        # Unexpected errors are refusals too, never an evidence waiver.
        return _evidence_refusal(result)


def _identity_refusal(result: dict[str, Any] | None = None) -> dict[str, Any]:
    if result is None:
        result = {"configuration_valid": False, "launch_blockers": list(LAUNCH_BLOCKERS)}
    result.update({
        "launch_allowed": False,
        "full_220_allowed": False,
        "identity_plan_gate": {
            "identity_complete": False, "consumed_plan_sha256": None,
            "evidence_linkage": None, "cleared_blockers": [],
            "remaining_blockers": list(result["launch_blockers"]),
            "evidence_boundary": DISPATCH_GRADING_IDENTITY["evidence_boundary"],
            "refusal_code": IDENTITY_REFUSAL,
        },
    })
    return result


def _inspect_plan_with_identity(
    plan: dict[str, Any], *, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
    identity_bundle: Path | None = None,
) -> dict[str, Any]:
    """Optionally consume an exact sealed identity; absent/null is unchanged."""
    if identity_bundle is None:
        return _inspect_plan_with_evidence(
            plan, evidence_bundle=evidence_bundle, reviewed_source_sha=reviewed_source_sha, as_of=as_of,
        )
    result = None
    try:
        result = _inspect_plan_with_evidence(
            plan, evidence_bundle=evidence_bundle, reviewed_source_sha=reviewed_source_sha, as_of=as_of,
        )
        if not result["configuration_valid"] or (
            "evidence_gate" in result and result["evidence_gate"]["evidence_complete"] is not True
        ):
            return _identity_refusal(result)
        # Intake/compiler plan checks re-enter the no-bundle path, never this
        # explicit consumption branch. Do not import or verify on legacy calls.
        from gpt56_pilot_identity_plan import verify_pilot_identity

        verified = verify_pilot_identity(
            plan, bundle_root=identity_bundle, evidence_bundle=evidence_bundle,
            reviewed_source_sha=reviewed_source_sha, as_of=as_of,
        )
        remaining = [name for name in result["launch_blockers"] if name not in IDENTITY_PLAN_BLOCKERS]
        gate = {
            "identity_complete": True, "consumed_plan_sha256": verified.sha256,
            "evidence_linkage": verified.as_dict()["evidence_linkage"],
            "cleared_blockers": list(IDENTITY_PLAN_BLOCKERS), "remaining_blockers": remaining,
            "evidence_boundary": DISPATCH_GRADING_IDENTITY["evidence_boundary"],
        }
        result["launch_blockers"] = remaining
        if "evidence_gate" in result:
            result["evidence_gate"]["remaining_blockers"] = remaining
        result["identity_plan_gate"] = gate
        return result
    except Exception:
        return _identity_refusal(result)


def _input_refusal(result: dict[str, Any] | None = None) -> dict[str, Any]:
    if result is None:
        result = {"configuration_valid": False, "launch_blockers": list(LAUNCH_BLOCKERS)}
    result.update({
        "launch_allowed": False, "full_220_allowed": False,
        "input_bundle_gate": {
            "input_bundle_complete": False, "consumed_bundle_sha256": None,
            "config_bundle_sha256": None, "identity_plan_sha256": None,
            "cleared_blockers": [], "remaining_blockers": list(result["launch_blockers"]),
            "evidence_boundary": INPUT_BUNDLE["evidence_boundary"], "refusal_code": INPUT_REFUSAL,
        },
    })
    return result


def _inspect_plan_with_input(
    plan: dict[str, Any], *, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
    identity_bundle: Path | None = None, config_bundle: Path | None = None, input_bundle: Path | None = None,
) -> dict[str, Any]:
    """An explicit verified local bundle closes only prepared-input consistency.

    The old combined input/live-identity requirement is now two closed entries.
    Both remain on absent/null calls; no consumption, wire or launch claim is
    inferred from publication. Existing evidence/identity gates remain explicit.
    """
    options = {"evidence_bundle": evidence_bundle, "reviewed_source_sha": reviewed_source_sha,
               "as_of": as_of, "identity_bundle": identity_bundle}
    if input_bundle is None and config_bundle is None:
        return _inspect_plan_with_identity(plan, **options)
    result = None
    try:
        result = _inspect_plan_with_identity(plan, **options)
        if (input_bundle is None or config_bundle is None or identity_bundle is None
                or not result["configuration_valid"]
                or result.get("identity_plan_gate", {}).get("identity_complete") is not True):
            return _input_refusal(result)
        from gpt56_pilot_input_bundle import verify_pilot_input_bundle

        verified = verify_pilot_input_bundle(plan, bundle_root=input_bundle, config_bundle=config_bundle, **options)
        document = verified.as_dict()
        remaining = [name for name in result["launch_blockers"] if name not in INPUT_BUNDLE_BLOCKERS]
        gate = {
            "input_bundle_complete": True, "consumed_bundle_sha256": verified.sha256,
            "config_bundle_sha256": document["config_bundle"]["sha256"],
            "identity_plan_sha256": document["identity_plan_sha256"],
            "cleared_blockers": list(INPUT_BUNDLE_BLOCKERS), "remaining_blockers": remaining,
            "evidence_boundary": INPUT_BUNDLE["evidence_boundary"],
        }
        result["launch_blockers"] = remaining
        for name in ("evidence_gate", "identity_plan_gate"):
            if name in result:
                result[name]["remaining_blockers"] = remaining
        result["input_bundle_gate"] = gate
        return result
    except Exception:
        return _input_refusal(result)


def _deployment_refusal(result: dict[str, Any] | None = None) -> dict[str, Any]:
    if result is None:
        result = {"configuration_valid": False, "launch_blockers": list(LAUNCH_BLOCKERS)}
    result.update({
        "launch_allowed": False, "full_220_allowed": False,
        "deployment_binding_gate": {
            "deployment_binding_complete": False, "consumed_bundle_sha256": None,
            "candidate_config_sha256": None, "evidence_linkage": None,
            "cleared_blockers": [], "remaining_blockers": list(result["launch_blockers"]),
            "evidence_boundary": DEPLOYMENT_BINDING["evidence_boundary"], "refusal_code": DEPLOYMENT_REFUSAL,
        },
    })
    return result


def _inspect_plan_with_deployment(
    plan: dict[str, Any], *, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
    identity_bundle: Path | None = None, config_bundle: Path | None = None, input_bundle: Path | None = None,
    deployment_binding: Path | None = None, account_resource_id_file: Path | None = None,
    project_resource_id_file: Path | None = None, deployment_resource_id_file: Path | None = None,
) -> dict[str, Any]:
    """Explicit verified deployment binding clears one local requirement only."""
    options = {"evidence_bundle": evidence_bundle, "reviewed_source_sha": reviewed_source_sha,
               "as_of": as_of, "identity_bundle": identity_bundle,
               "config_bundle": config_bundle, "input_bundle": input_bundle}
    resource_files = {"account_resource_id_file": account_resource_id_file,
                      "project_resource_id_file": project_resource_id_file,
                      "deployment_resource_id_file": deployment_resource_id_file}
    if deployment_binding is None and all(path is None for path in resource_files.values()):
        return _inspect_plan_with_input(plan, **options)
    result = None
    try:
        result = _inspect_plan_with_input(plan, **options)
        if (deployment_binding is None or any(value is None for value in (*options.values(), *resource_files.values()))
                or not result["configuration_valid"]
                or result.get("evidence_gate", {}).get("evidence_complete") is not True
                or result.get("identity_plan_gate", {}).get("identity_complete") is not True
                or result.get("input_bundle_gate", {}).get("input_bundle_complete") is not True):
            return _deployment_refusal(result)
        from gpt56_pilot_deployment_binding import CANDIDATE_PATH, verify_pilot_deployment_binding

        verified = verify_pilot_deployment_binding(plan, bundle_root=deployment_binding, **options, **resource_files)
        document = verified.as_dict()
        remaining = [name for name in result["launch_blockers"] if name not in DEPLOYMENT_BINDING_BLOCKERS]
        gate = {
            "deployment_binding_complete": True, "consumed_bundle_sha256": verified.sha256,
            "candidate_config_sha256": document["files"][CANDIDATE_PATH]["sha256"],
            "evidence_linkage": document["evidence_linkage"], "evaluated_at": as_of,
            "cleared_blockers": list(DEPLOYMENT_BINDING_BLOCKERS), "remaining_blockers": remaining,
            "remaining_work": document["remaining_work"], "evidence_boundary": DEPLOYMENT_BINDING["evidence_boundary"],
        }
        result["launch_blockers"] = remaining
        for name in ("evidence_gate", "identity_plan_gate", "input_bundle_gate"):
            result[name]["remaining_blockers"] = remaining
        result["deployment_binding_gate"] = gate
        return result
    except Exception:
        return _deployment_refusal(result)


def _capture_refusal(result: dict[str, Any] | None = None) -> dict[str, Any]:
    if result is None:
        result = {"configuration_valid": False, "launch_blockers": list(LAUNCH_BLOCKERS)}
    result.update({
        "launch_allowed": False, "full_220_allowed": False,
        "pre_execution_capture_gate": {
            "capture_complete": False, "capture_sha256": None, "reviewed_source_sha": None,
            "evaluated_at": None, "cleared_blockers": [], "remaining_blockers": list(result["launch_blockers"]),
            "evidence_boundary": PRE_EXECUTION_CAPTURE["evidence_boundary"], "refusal_code": CAPTURE_REFUSAL,
        },
    })
    return result


def inspect_plan(
    plan: dict[str, Any], *, evidence_bundle: Path | None = None,
    reviewed_source_sha: str | None = None, as_of: str | None = None,
    identity_bundle: Path | None = None, config_bundle: Path | None = None, input_bundle: Path | None = None,
    deployment_binding: Path | None = None, account_resource_id_file: Path | None = None,
    project_resource_id_file: Path | None = None, deployment_resource_id_file: Path | None = None,
    capture_workspace: Path | None = None,
) -> dict[str, Any]:
    """Explicit consumption closes prepared intent only, never live wire identity."""
    options = {"evidence_bundle": evidence_bundle, "reviewed_source_sha": reviewed_source_sha, "as_of": as_of,
               "identity_bundle": identity_bundle, "config_bundle": config_bundle, "input_bundle": input_bundle,
               "deployment_binding": deployment_binding, "account_resource_id_file": account_resource_id_file,
               "project_resource_id_file": project_resource_id_file, "deployment_resource_id_file": deployment_resource_id_file}
    if capture_workspace is None:
        return _inspect_plan_with_deployment(plan, **options)
    result = None
    try:
        result = _inspect_plan_with_deployment(plan, **options)
        if (not result["configuration_valid"] or any(value is None for value in options.values())
                or result.get("deployment_binding_gate", {}).get("deployment_binding_complete") is not True):
            return _capture_refusal(result)
        from gpt56_pilot_input_capture import PilotCaptureSources, verify_pilot_input_capture

        verified = verify_pilot_input_capture(
            PilotCaptureSources(**options), workspace=capture_workspace, dataset_root=input_bundle, plan=plan,
        )
        remaining = [name for name in result["launch_blockers"] if name not in CAPTURE_BLOCKERS]
        gate = {"capture_complete": True, "capture_sha256": verified["sha256"],
                "reviewed_source_sha": verified["reviewed_source_sha"], "evaluated_at": as_of,
                "cleared_blockers": list(CAPTURE_BLOCKERS), "remaining_blockers": remaining,
                "evidence_boundary": verified["evidence_boundary"]}
        result["launch_blockers"] = remaining
        for name in ("evidence_gate", "identity_plan_gate", "input_bundle_gate", "deployment_binding_gate"):
            result[name]["remaining_blockers"] = remaining
        result["pre_execution_capture_gate"] = gate
        return result
    except Exception:
        return _capture_refusal(result)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    evidence_requested = False
    identity_requested = False
    input_requested = False
    deployment_requested = False
    capture_requested = False
    # A misspelled option can conceal which mode was intended. All argument
    # errors are non-echoing; valid plan-only invocations keep their report bytes.
    parser = _SafeArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument("--evidence-bundle", type=Path, help="Published local Foundry evidence bundle")
    parser.add_argument("--reviewed-source-sha", help="Externally reviewed full 40-hex source SHA")
    parser.add_argument("--as-of", help="Externally supplied UTC time, YYYY-MM-DDTHH:MM:SSZ")
    parser.add_argument("--identity-bundle", type=Path, help="Published inert pilot dispatch/grading identity")
    parser.add_argument("--config-bundle", type=Path, help="Verified inert pilot configuration bundle")
    parser.add_argument("--input-bundle", type=Path, help="Published five-task local input bundle")
    parser.add_argument("--deployment-binding", type=Path, help="Published local deployment binding")
    parser.add_argument("--capture-workspace", type=Path, help="Local Step 1 prepared request capture (not launch approval)")
    for role in ("account", "project", "deployment"):
        parser.add_argument("--" + role + "-resource-id-file", type=Path, help="Private local resource ID bytes")
    try:
        args = parser.parse_args(arguments)
        capture_requested = args.capture_workspace is not None
        evidence_requested = any(value is not None for value in (
            args.evidence_bundle, args.reviewed_source_sha, args.as_of,
        ))
        identity_requested = args.identity_bundle is not None
        input_requested = args.input_bundle is not None or args.config_bundle is not None
        deployment_requested = any(value is not None for value in (
            args.deployment_binding, args.account_resource_id_file, args.project_resource_id_file, args.deployment_resource_id_file,
        ))
        result = inspect_plan(
            load_plan(args.plan), evidence_bundle=args.evidence_bundle,
            reviewed_source_sha=args.reviewed_source_sha, as_of=args.as_of, identity_bundle=args.identity_bundle,
            config_bundle=args.config_bundle, input_bundle=args.input_bundle,
            deployment_binding=args.deployment_binding, account_resource_id_file=args.account_resource_id_file,
            project_resource_id_file=args.project_resource_id_file, deployment_resource_id_file=args.deployment_resource_id_file,
            capture_workspace=args.capture_workspace,
        )
    except Exception as error:
        if isinstance(error, _CLIArgumentsRefused):
            evidence_requested = True
        if not (evidence_requested or identity_requested or input_requested or deployment_requested or capture_requested) and not isinstance(error, (OSError, ValueError, KeyError, TypeError, yaml.YAMLError)):
            raise
        result = _capture_refusal() if capture_requested else _deployment_refusal() if deployment_requested else _input_refusal() if input_requested else _identity_refusal() if identity_requested else _evidence_refusal() if evidence_requested else {
            "configuration_valid": False,
            "launch_allowed": False,
            "full_220_allowed": False,
            "error": str(error),
        }
    print(_canonical_json(result) if evidence_requested or identity_requested or input_requested or deployment_requested or capture_requested else json.dumps(result, indent=2, ensure_ascii=False))
    return 2  # No paid pilot or 220-task run can be launched by this module.


if __name__ == "__main__":
    raise SystemExit(main())
