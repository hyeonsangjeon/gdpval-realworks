"""Validate the Foundry Sol pilot registration offline; never launch a run.

Exit 2 is intentional even for a valid registration. A supported provider path
does not verify a deployment's identity, Max, Long 1M, limits, or tariff.
This check neither reads credentials nor opens an existing paid workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tarfile
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
# A source profile for the SAME pilot/run identity, not another execution right.
# The original registrations and their source pins remain byte-for-byte intact.
SOURCE_PROFILE = ENVELOPE + "gpt56_sol_foundry_codex_pilot_source_20261026_token_precheck.yaml"
SOURCE_PROFILE_BINDINGS = ENVELOPE + "gpt56_sol_foundry_codex_pilot_source_20261025_bindings.yaml"
SOURCE_PROFILE_BINDINGS_SHA256 = "740ec085c047ad359b4c5e56a8bf5867ebc2cb6c229d479262d6815fbe8154cf"
SOURCE_PROFILE_CAPS = ENVELOPE + "gpt56_sol_foundry_codex_pilot_source_20261025.yaml"
SOURCE_PROFILE_CAPS_SHA256 = "f88c850558674a4c3a89ae0840f23dc27402aefafe56f7323ba3d3b8ad33a3b2"
SOURCE_PROFILE_PREVIOUS = ENVELOPE + "gpt56_sol_foundry_codex_pilot_source_20261023.yaml"
SOURCE_PROFILE_PREVIOUS_SHA256 = "506de35370ffe6d54e6decb2459a4f4abda47136d550c010086b0fffd5c1e482"
FOUNDRY_PLAN_SHA256 = "f51d92c35f388f016488f15d5e96acd1f9de10345fb2379dac7e194eadbbe2fd"
SOURCE_PROFILE_REFRESH = frozenset({
    "batch-runner/core/codex_runner.py", "batch-runner/step2_run_inference.py",
    "batch-runner/gpt56_sol_codex_pilot_preflight.py",
    "batch-runner/gpt56_foundry_evidence_intake.py",
    "batch-runner/gpt54_codex_input_capture.py", "batch-runner/gpt54_run_config_bundle.py",
    "batch-runner/gpt54_prepared_input_attestation.py", "batch-runner/gpt54_run_input_bundle.py",
    "batch-runner/gpt56_pilot_identity_plan.py", "batch-runner/gpt56_pilot_deployment_binding.py",
    "batch-runner/gpt56_pilot_input_capture.py", "batch-runner/core/codex_task_deadline.py",
    "batch-runner/gpt56_pilot_wire_receipt.py", "batch-runner/gpt56_pilot_runtime_caps_usage.py",
})
# Exact successor delta: four caps files plus this source-profile selector.
# Other original source changes remain those sealed in the 2026-10-23 profile.
SOURCE_PROFILE_DELTA = frozenset({
    "batch-runner/core/codex_runner.py", "batch-runner/step2_run_inference.py",
    "batch-runner/gpt56_pilot_wire_receipt.py", "batch-runner/gpt56_pilot_runtime_caps_usage.py",
    "batch-runner/gpt56_sol_codex_pilot_preflight.py",
})
SOURCE_PROFILE_AUXILIARY = {
    "batch-runner/gpt54_disposable_checkout.py":
        "77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62",
}
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
    "grader_template_source_hash": "47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf",
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
WIRE_RECEIPT = {
    "recorder": "batch-runner/gpt56_pilot_wire_receipt.py",
    "source_base_sha": "0cd4c5e76805384a77afabf28b3663a3ad6596c0",
    "ready_marker": "pilot-wire-receipts-ready.json",
    "evidence_boundary": "codex_app_server_transport_not_foundry_http_or_served_identity",
    "requires_live_session_witness": True,
    "clears_live_identity_and_wire_blocker": False,
}
NATIVE_RESULT_HOST = {
    "recorder": "batch-runner/gpt56_pilot_native_result_host.py",
    "source_base_sha": "f6d76e2084bcda75de5dad15b98503f598734bc0",
    "ready_marker": "pilot-native-result-host-ready.json",
    "evidence_boundary": "local_codex_workspace_and_step2_saved_result_not_remote_isolation_or_served_identity",
    "requires_live_wire_session_witness": True,
    "eligible_blocker": "native_sandbox_and_result_bundle_host_unverified",
    "offline_preflight_consumption": False,
    "clears_live_identity_and_wire_blocker": False,
}
RUNTIME_CAPS_USAGE = {
    "recorder": "batch-runner/gpt56_pilot_runtime_caps_usage.py",
    "source_base_sha": "0ae151d105258c6f716e22aea54c7df8cd0a8112",
    "ready_marker": "pilot-runtime-caps-usage-ready.json",
    "evidence_boundary": "observed_app_server_token_thresholds_not_native_call_enforcement_or_billing",
    "requires_live_host_session_witness": True,
    "offline_preflight_consumption": False,
    "clears_native_call_or_billing_blockers": False,
}
EXTERNAL_LIVE_RECEIPT = {
    "recorder": "batch-runner/gpt56_pilot_external_live_receipt.py",
    "source_base_sha": "20c2fea35fbd0bc9cd197f5fd07c5b4f4113377a",
    "ready_marker": "pilot-external-live-receipt-ready.json",
    "evidence_boundary": "offline_external_receipt_consistency_not_provider_authenticity_or_launch_approval",
    "requires_live_caps_usage_witness": True,
    "offline_preflight_consumption": False,
    "clears_current_blockers": False,
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
    "batch-runner/core/codex_task_deadline.py",
    "batch-runner/core/codex_cost.py",
    "batch-runner/core/executor.py",
    "batch-runner/step1_prepare_tasks.py",
    "batch-runner/step2_run_inference.py",
    "batch-runner/core/cost_receipts.py",
    "batch-runner/core/result_projection.py",
    "batch-runner/schemas/grade.schema.json",
} | EVIDENCE_SOURCES | IDENTITY_SOURCES | INPUT_SOURCES | DEPLOYMENT_SOURCES | CAPTURE_SOURCES | {
    CONFIG_BUNDLE["materializer"], WIRE_RECEIPT["recorder"], NATIVE_RESULT_HOST["recorder"], RUNTIME_CAPS_USAGE["recorder"],
    EXTERNAL_LIVE_RECEIPT["recorder"],
    "batch-runner/core/result_fingerprint.py", "batch-runner/core/public_error.py",
}
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


class PilotSourceRegistrationRefused(ValueError):
    """One closed code; no Git output, source bytes or caller strings escape."""


def source_plan_snapshot(
    *, expected_plan_sha256: str | None = None, reviewed_source_sha: str | None = None,
) -> tuple[dict[str, Any], bytes, dict[str, Any] | None]:
    """Select a closed source profile by its sealed plan, never grant execution.

    Old/default callers retain the original reader. The prospective profile
    needs an independently supplied full commit and verifies the current files
    against that commit, including this reader and its actual imported helpers.
    No file, environment, module global, Git setting or execution ledger is written.
    """
    from gpt54_run_config_bundle import _held_parents, _path
    from gpt54_v2_grading_input import _read_bytes

    try:
        original_data = _read_bytes(_path(ROOT, ACTIVE_PLAN))
        original = yaml.safe_load(original_data)
        if expected_plan_sha256 is None or expected_plan_sha256 == seal(original):
            return original, original_data, None

        def require(condition: bool) -> None:
            if not condition:
                raise PilotSourceRegistrationRefused("pilot_source_registration_refused")

        require(hashlib.sha256(original_data).hexdigest() == FOUNDRY_PLAN_SHA256)
        require(type(reviewed_source_sha) is str
                and re.fullmatch(r"[0-9a-f]{40}", reviewed_source_sha) is not None)
        previous_data = _read_bytes(_path(ROOT, SOURCE_PROFILE_PREVIOUS),
                                    sha256=SOURCE_PROFILE_PREVIOUS_SHA256)
        require(len(previous_data) <= 65536)
        previous = yaml.safe_load(previous_data)
        caps_data = _read_bytes(_path(ROOT, SOURCE_PROFILE_CAPS), sha256=SOURCE_PROFILE_CAPS_SHA256)
        require(len(caps_data) <= 65536)
        caps_profile = yaml.safe_load(caps_data)
        bindings_data = _read_bytes(_path(ROOT, SOURCE_PROFILE_BINDINGS), sha256=SOURCE_PROFILE_BINDINGS_SHA256)
        require(len(bindings_data) <= 65536)
        bindings_profile = yaml.safe_load(bindings_data)
        profile_data = _read_bytes(_path(ROOT, SOURCE_PROFILE))
        require(len(profile_data) <= 65536)
        profile = yaml.safe_load(profile_data)
        require(type(profile) is dict and set(profile) == set(original))
        require(seal(profile) == expected_plan_sha256)
        require(seal({k: v for k, v in profile.items() if k != "source_pins"})
                == seal({k: v for k, v in original.items() if k != "source_pins"}))
        pins = profile["source_pins"]
        require(type(pins) is dict and set(pins) == REQUIRED_SOURCES)
        require(all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
                    for value in pins.values()))
        require({name for name, digest in pins.items()
                 if digest != original["source_pins"][name]} == SOURCE_PROFILE_REFRESH)
        require({name for name, digest in pins.items()
                 if digest != previous["source_pins"][name]} == SOURCE_PROFILE_DELTA)
        require({name for name, digest in bindings_profile["source_pins"].items()
                 if digest != caps_profile["source_pins"][name]}
                == {"batch-runner/gpt56_sol_codex_pilot_preflight.py"})
        require({name for name, digest in pins.items()
                 if digest != bindings_profile["source_pins"][name]}
                == {"batch-runner/gpt56_sol_codex_pilot_preflight.py", "batch-runner/gpt56_pilot_wire_receipt.py"})

        # Reuse the existing sanitized, bounded, local-only Git implementation.
        # Archive reads Git objects, not LFS payloads; nothing is extracted.
        import gpt54_disposable_checkout as checkout

        source_roles = {**pins, **SOURCE_PROFILE_AUXILIARY,
                        SOURCE_PROFILE_PREVIOUS: SOURCE_PROFILE_PREVIOUS_SHA256,
                        SOURCE_PROFILE_CAPS: SOURCE_PROFILE_CAPS_SHA256,
                        SOURCE_PROFILE_BINDINGS: SOURCE_PROFILE_BINDINGS_SHA256}
        roles = tuple(sorted({*source_roles, ACTIVE_PLAN, SOURCE_PROFILE}))
        with _held_parents(ROOT, roles) as check:
            repository, _ = checkout._repository(ROOT)
            require(checkout._git(repository, "rev-parse", "--verify", "HEAD^{commit}").stdout
                    == reviewed_source_sha.encode("ascii") + b"\n")
            require(not checkout._git(repository, "status", "--porcelain=v1", "--untracked-files=normal").stdout)
            tree = checkout._git(repository, "rev-parse", "--verify", "HEAD^{tree}").stdout.decode("ascii").strip()
            require(re.fullmatch(r"[0-9a-f]{40}", tree) is not None)
            archive = checkout._git(repository, "archive", "--format=tar", reviewed_source_sha, "--", *roles).stdout
            require(len(archive) <= 16 * 1024 * 1024)
            blobs = {}
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as snapshot:
                require(snapshot.pax_headers.get("comment") == reviewed_source_sha)
                for member in snapshot.getmembers():
                    if member.isdir():
                        require(any(name.startswith(member.name.rstrip("/") + "/") for name in roles))
                        continue
                    require(member.isfile() and member.name in roles and member.name not in blobs)
                    stream = snapshot.extractfile(member)
                    require(stream is not None)
                    blobs[member.name] = stream.read()
            require(set(blobs) == set(roles))
            require(blobs[ACTIVE_PLAN] == original_data and blobs[SOURCE_PROFILE] == profile_data)
            require(blobs[SOURCE_PROFILE_PREVIOUS] == previous_data)
            require(blobs[SOURCE_PROFILE_CAPS] == caps_data)
            require(blobs[SOURCE_PROFILE_BINDINGS] == bindings_data)
            def recheck() -> None:
                for role, data in blobs.items():
                    digest = hashlib.sha256(data).hexdigest()
                    require(role not in source_roles or digest == source_roles[role])
                    _read_bytes(_path(ROOT, role), sha256=digest, size=len(data))
                    if role.endswith(".py"):
                        module = sys.modules.get(role.removeprefix("batch-runner/")[:-3].replace("/", "."))
                        if module is not None:
                            require(Path(os.path.abspath(module.__file__)) == _path(ROOT, role))
                require(Path(os.path.abspath(__file__)) == ROOT / "batch-runner/gpt56_sol_codex_pilot_preflight.py")
                check()

            recheck()
            require(_inspect_plan_only(profile)["configuration_valid"])
            # Admission and final rechecks share the same held paths and bytes.
            recheck()
            require(checkout._git(repository, "rev-parse", "--verify", "HEAD^{commit}").stdout
                    == reviewed_source_sha.encode("ascii") + b"\n")
            check()
        return profile, profile_data, {
            "status": "source_verified", "source_sha": reviewed_source_sha, "source_tree": tree,
            "profile_path": SOURCE_PROFILE, "profile_sha256": hashlib.sha256(profile_data).hexdigest(),
            "supersedes_profile": SOURCE_PROFILE_BINDINGS,
            "supersedes_profile_sha256": SOURCE_PROFILE_BINDINGS_SHA256,
            "source_change_reason": "client_token_precheck_and_complete_response_usage",
            "plan_sha256": seal(profile), "historical_plan_sha256": FOUNDRY_PLAN_SHA256,
            "run_id": RUN_ID, "launch_authority": False, "retry_authority": False,
        }
    except Exception:
        raise PilotSourceRegistrationRefused("pilot_source_registration_refused") from None


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
        "wire_receipt": WIRE_RECEIPT,
        "native_result_host": NATIVE_RESULT_HOST,
        "runtime_caps_usage": RUNTIME_CAPS_USAGE,
        "external_live_receipt": EXTERNAL_LIVE_RECEIPT,
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
        # Complete external exports bind declarations; they do not enumerate
        # live model calls or prove that billing applied those tariff meters.
        roles = set(EVIDENCE_INTAKE["required_roles"])
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


def _project_resource_required(plan: dict[str, Any]) -> bool:
    """Only the validated direct-account route can omit a child project."""
    return plan.get("foundry_route", {}).get("route_profile") != "direct-v1"


def _same_reported_upstreams(upstreams: dict[str, Any], result: dict[str, Any]) -> bool:
    """Do not combine separately verified generations in one preflight report.

    Real bundle verifiers still own schema, byte and freshness checks. These
    comparisons additionally bind their output to the preceding gate results.
    Missing or malformed metadata raises into the caller's closed refusal.
    """
    evidence = result["evidence_gate"]
    identity = result["identity_plan_gate"]
    inputs = result["input_bundle_gate"]
    linkage = identity["evidence_linkage"]
    pairs = (
        (upstreams["evidence"]["ready_sha256"], evidence["consumed_bundle_sha256"]),
        (upstreams["identity"]["plan_sha256"], identity["consumed_plan_sha256"]),
        (upstreams["config"]["ready_sha256"], inputs["config_bundle_sha256"]),
        (upstreams["input"]["ready_sha256"], inputs["consumed_bundle_sha256"]),
        (inputs["identity_plan_sha256"], identity["consumed_plan_sha256"]),
        (linkage["ready_bundle_sha256"], evidence["consumed_bundle_sha256"]),
    )
    return (all(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected)
                and actual == expected for actual, expected in pairs)
            and type(evidence["reviewed_source_sha"]) is str
            and re.fullmatch(r"[0-9a-f]{40}", evidence["reviewed_source_sha"]) is not None
            and linkage["reviewed_source_sha"] == evidence["reviewed_source_sha"])


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
        required_files = [account_resource_id_file, deployment_resource_id_file]
        if _project_resource_required(plan):
            required_files.append(project_resource_id_file)
        if (deployment_binding is None or any(value is None for value in (*options.values(), *required_files))
                or not result["configuration_valid"]
                or result.get("evidence_gate", {}).get("evidence_complete") is not True
                or result.get("identity_plan_gate", {}).get("identity_complete") is not True
                or result.get("input_bundle_gate", {}).get("input_bundle_complete") is not True):
            return _deployment_refusal(result)
        from gpt56_pilot_deployment_binding import CANDIDATE_PATH, verify_pilot_deployment_binding

        verified = verify_pilot_deployment_binding(plan, bundle_root=deployment_binding, **options, **resource_files)
        document = verified.as_dict()
        if (not _same_reported_upstreams(document["upstream_bundles"], result)
                or seal(document["evidence_linkage"]) != seal(result["identity_plan_gate"]["evidence_linkage"])):
            return _deployment_refusal(result)
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
        required_options = [value for name, value in options.items()
                            if name != "project_resource_id_file" or _project_resource_required(plan)]
        if (not result["configuration_valid"] or any(value is None for value in required_options)
                or result.get("deployment_binding_gate", {}).get("deployment_binding_complete") is not True):
            return _capture_refusal(result)
        from gpt56_pilot_input_capture import PilotCaptureSources, verify_pilot_input_capture

        verified = verify_pilot_input_capture(
            PilotCaptureSources(**options), workspace=capture_workspace, dataset_root=input_bundle, plan=plan,
        )
        deployment_sha256 = result["deployment_binding_gate"]["consumed_bundle_sha256"]
        if (not _same_reported_upstreams(verified["upstream_bundles"], result)
                or type(deployment_sha256) is not str
                or re.fullmatch(r"[0-9a-f]{64}", deployment_sha256) is None
                or verified["upstream_bundles"]["deployment"]["ready"]["sha256"] != deployment_sha256
                or verified["reviewed_source_sha"] != reviewed_source_sha):
            return _capture_refusal(result)
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
    source_requested = False
    source_report = None
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
        source_requested = args.plan.absolute() in {
            ROOT / SOURCE_PROFILE, ROOT / SOURCE_PROFILE_CAPS, ROOT / SOURCE_PROFILE_PREVIOUS,
        }
        capture_requested = args.capture_workspace is not None
        evidence_requested = any(value is not None for value in (
            args.evidence_bundle, args.reviewed_source_sha, args.as_of,
        ))
        identity_requested = args.identity_bundle is not None
        input_requested = args.input_bundle is not None or args.config_bundle is not None
        deployment_requested = any(value is not None for value in (
            args.deployment_binding, args.account_resource_id_file, args.project_resource_id_file, args.deployment_resource_id_file,
        ))
        plan = load_plan(args.plan)
        if source_requested:
            plan, _, source_report = source_plan_snapshot(
                expected_plan_sha256=seal(plan), reviewed_source_sha=args.reviewed_source_sha,
            )
        result = inspect_plan(
            plan, evidence_bundle=args.evidence_bundle,
            reviewed_source_sha=args.reviewed_source_sha, as_of=args.as_of, identity_bundle=args.identity_bundle,
            config_bundle=args.config_bundle, input_bundle=args.input_bundle,
            deployment_binding=args.deployment_binding, account_resource_id_file=args.account_resource_id_file,
            project_resource_id_file=args.project_resource_id_file, deployment_resource_id_file=args.deployment_resource_id_file,
            capture_workspace=args.capture_workspace,
        )
    except Exception as error:
        if source_requested:
            result = _evidence_refusal()
            result["source_registration"] = {"status": "refused", "refusal_code": "pilot_source_registration_refused"}
            print(_canonical_json(result))
            return 2
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
    if source_report is not None:
        result["source_registration"] = source_report
    print(_canonical_json(result) if evidence_requested or identity_requested or input_requested or deployment_requested or capture_requested else json.dumps(result, indent=2, ensure_ascii=False))
    return 2  # No paid pilot or 220-task run can be launched by this module.


if __name__ == "__main__":
    raise SystemExit(main())
