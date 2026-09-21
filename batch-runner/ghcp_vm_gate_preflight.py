"""Inspect one inert GHCP VM contract using local pinned bytes only.

Configuration validity is not served-model evidence, judge validation or launch
approval. Only an explicitly verified local input bundle can satisfy the input
materialization blocker. This is not VM or model consumption; every invocation
still exits 2 and keeps every execution flag false.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from core.agentic_v2_oci import _read_regular_path, canonical_json, sha256_bytes
from core.execution_envelope_tasks import TaskCatalog, select_advance_check_tasks

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "99e62ed5d4f1b1506841dd70a66c2696ac95b4c6"
ENVELOPE = "batch-runner/experiments/execution_envelope/"
PLAN_PATH = ENVELOPE + "gpt56_sol_ghcp_codex_vm_gate.yaml"
PLAN = ROOT / PLAN_PATH
SELF = "batch-runner/ghcp_vm_gate_preflight.py"
INPUT_BUNDLE = "batch-runner/ghcp_vm_input_bundle.py"
HISTORICAL_PLAN = ENVELOPE + "gpt56_sol_copilot_codex_pilot.yaml"
CATALOG = ENVELOPE + "gdpval_task_catalog.json"
ADVANCE_PLAN = ENVELOPE + "advance_check_plan.yaml"
GRADER = "batch-runner/grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"
CONDITION_ID = "gpt56_sol_ghcp_codex_vm_pilot5_v1"
REFUSAL = "ghcp_vm_gate_refused"
MAX_PLAN_BYTES = 65536
MAX_SOURCE_BYTES = 8 * 1024 * 1024

# The existing bytes are immutable inputs, not assertions supplied by a caller.
# The local readers' digests are sealed in the YAML at their reviewed Git HEAD.
PINNED_SOURCES = {
    "batch-runner/core/agentic_v2_oci.py": "3828aebc41bc27ed571991b27f7847a7a77f0b2240a2616fe554fd5e0c513337",
    "batch-runner/core/execution_envelope_tasks.py": "dd934314ce447b78efa45ad9d349f198d1e429531eccdf430106b87335dc2ea0",
    "batch-runner/core/reference_integrity.py": "13198897c189a9276494b78ea3359fc2e623211ab2f32554b81ab9b12d9cf19e",
    "batch-runner/core/source_identity.py": "1a619857e9a7ba8d6d572fa712796da380f648b6c541af727d2c45b6f9848d3b",
    CATALOG: "5f1eca853979b2b4efe6c6ba656545c3a416da920e3faf067d52f5d8ac4ae0eb",
    ADVANCE_PLAN: "9ecf85f1e9eb40ddb0232baa854c10052c3e4457fe2cf174f9b34d4cbecdc26e",
    HISTORICAL_PLAN: "47799d3f61374679722df32c67de14f9d0d56bd6586cf7b28c10076fd41d1901",
    GRADER: "89820de9d9c4e2e3edc1420d3c05fd12c7bb4c3475fd47ad92ed56566a897025",
    "batch-runner/step8_grade.py": "ec23fc941aa0edb54e2858750cc1df5a6a6954a1732cd3f3197d9f9b4b3c18f4",
    "batch-runner/core/grader.py": "d7904ea02659bb9d703712e16f89ed8bc5af5a6c6d104a34d11668f8a396180f",
    "batch-runner/core/rubric_loader.py": "804e1a90d9e96d686d022d9243cfe47b5f5041651c25d450855b30e8d3f2b059",
    "batch-runner/core/grade_payload.py": "4992c803dd60fd239bb76f6fa87d080e1239288a4485a1075337d343c91f0dae",
    "batch-runner/prompts/grader_judge.md": "9bf9ec73be0fe0886e17171aabcd9470869e8aeccafa22b53217d229029c2e11",
    "batch-runner/prompts/grader_judge_v2.md": "9bbded2220760521846637486971b9a7d89eab0d4832295778a16cb672c22af9",
    "batch-runner/schemas/grade.schema.json": "9c611874c2d7aa57018eecdc86b7c0d579aaa9c29dd0df649058eec9ad5175b9",
    "batch-runner/core/result_projection.py": "1b47c4ee0f6d050e5edd4ac5a301203ba834c8d159b1557b04d83046ca965ec6",
    "batch-runner/core/cost_receipts.py": "4b936516da622ceaf8cf8d5e10d2dd1b69ded831b4143557b6431a197bab9cbe",
}
LOCAL_MODULES = frozenset({SELF, INPUT_BUNDLE})
REQUIRED_SOURCES = frozenset(PINNED_SOURCES) | LOCAL_MODULES
FALSE_FLAGS = (
    "launch_enabled", "launch_allowed", "paid_execution_enabled",
    "paid_execution_allowed", "full_220_enabled", "full_220_allowed",
)
OBSERVED_FACTS = (
    "verified_served", "verified_capability", "verified_auth", "verified_reset",
    "verified_capture", "verified_enforced_limits", "verified_usage",
    "verified_task_inputs", "grader_validation",
)
LAUNCH_BLOCKERS = (
    "ghcp_route_served_identity_unverified",
    "max_long_1m_capability_unverified",
    "ghcp_codex_versions_unresolved",
    "authentication_supply_disposal_unresolved",
    "vm_image_os_packages_version_policy_unresolved",
    "fresh_task_vm_reset_unverified",
    "network_permission_policy_unresolved",
    "native_execution_limits_unresolved",
    "repeat_and_variance_plan_unresolved",
    "five_task_time_cost_caps_unresolved",
    "native_ghcp_usage_and_missing_usage_policy_unresolved",
    "original_task_input_materialization_unverified",
    "transcript_tool_command_file_exit_capture_unverified",
    "grading_result_runtime_unwired",
    "grader_validation_unverified",
)


class GHCPVMGateRefused(ValueError):
    """A static refusal without caller values, host paths or exception details."""

    def __init__(self) -> None:
        super().__init__(REFUSAL)


def _require(condition: bool) -> None:
    if not condition:
        raise GHCPVMGateRefused()


class _UniqueLoader(yaml.SafeLoader):
    """Refuse aliases before expansion, plus duplicate and non-string keys."""

    def compose_node(self, parent: yaml.Node | None, index: Any) -> yaml.Node:
        _require(not self.check_event(yaml.AliasEvent))
        return super().compose_node(parent, index)


def _mapping(loader: yaml.SafeLoader, node: yaml.MappingNode) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        _require(type(key) is str and key not in result)
        result[key] = loader.construct_object(value_node, deep=True)
    return result


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _yaml(data: bytes) -> dict[str, Any]:
    value = yaml.load(data.decode("utf-8"), Loader=_UniqueLoader)
    _require(type(value) is dict)
    canonical_json(value)  # Refuse cycles, non-JSON objects and non-finite values.
    return value


def load_plan(path: Path | None = None) -> dict[str, Any]:
    """Read one bounded local YAML file; expose only a static failure."""
    try:
        return _yaml(_read_regular_path(ROOT / PLAN_PATH if path is None else Path(path), MAX_PLAN_BYTES))
    except Exception:
        raise GHCPVMGateRefused() from None


def _sources(plan: dict[str, Any]) -> dict[str, bytes]:
    pins = plan.get("source_pins")
    _require(type(pins) is dict and set(pins) == REQUIRED_SOURCES)
    sources = {}
    for name in sorted(REQUIRED_SOURCES):
        digest = pins[name]
        _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None)
        _require(name in LOCAL_MODULES or digest == PINNED_SOURCES[name])
        data = _read_regular_path(ROOT / name, MAX_SOURCE_BYTES)
        _require(sha256_bytes(data) == digest)
        if name in LOCAL_MODULES:
            _require(data == _read_regular_path(Path(__file__).with_name(Path(name).name), MAX_SOURCE_BYTES))
        sources[name] = data
    return sources


def _expected(sources: dict[str, bytes]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Derive the five tasks without importing any runtime or grading module."""
    historical = _yaml(sources[HISTORICAL_PLAN])
    advance = _yaml(sources[ADVANCE_PLAN])["model_run_conditions"]["shared"]
    _require(historical["status"] == "superseded" and historical["launch_enabled"] is False)
    catalog = TaskCatalog.from_mapping(json.loads(sources[CATALOG]))
    selection = select_advance_check_tasks(catalog, catalog_fingerprint=PINNED_SOURCES[CATALOG])
    ids = list(selection.task_ids)
    _require(len(ids) == len(set(ids)) == 5 and ids == advance["task_ids"])
    by_id = {task.task_id: task for task in catalog.tasks}
    tasks = [by_id[task_id] for task_id in ids]
    dataset = historical["dataset"]
    _require(dataset["tasks"] == [{"task_id": task.task_id, "prompt_sha256": task.prompt_sha256} for task in tasks])
    _require(dataset["repo_id"] == catalog.dataset_repo_id and dataset["revision"] == catalog.dataset_revision
             and dataset["parquet_sha256"] == catalog.dataset_file_sha256
             and dataset["catalog_sha256"] == PINNED_SOURCES[CATALOG]
             and dataset["input_file_versions"] == advance["input_file_versions"])
    expected = {
        "plan_version": "ghcp-vm-gate-v1", "base_sha": BASE_SHA, "condition_id": CONDITION_ID,
        "status": "blocked_preregistration",
        "question": "missing_or_drifted_prerequisites_refuse_before_paid_five_task_execution",
        **{name: False for name in FALSE_FLAGS},
        "identity": {
            "provider": "github_copilot", "model": "gpt-5.6-sol", "model_label": "GPT-5.6 Sol",
            "fast_mode": False, "harness": "codex", "reasoning_effort": "max",
            "context_tier": "long", "context_label": "Long (1M)", "nominal_context_tokens": 1000000,
            "capability_semantics": "request_not_served_evidence",
            "ghcp_cli_version": None, "codex_cli_version": None, "codex_sdk_version": None,
            "automatic_fallback_allowed": False, "fallbacks": [],
        },
        "dataset": {
            "cohort": "advance_check_5", "task_count": 5,
            "selector": "core.execution_envelope_tasks.select_advance_check_tasks",
            "catalog": CATALOG, "input_plan": ADVANCE_PLAN, "inherited_contract": HISTORICAL_PLAN,
            "repo_id": dataset["repo_id"], "revision": dataset["revision"],
            "parquet_sha256": dataset["parquet_sha256"], "catalog_sha256": dataset["catalog_sha256"],
            "task_content_policy": "original_unchanged", "reference_policy": "original_unchanged",
            "deliverable_policy": "original_unchanged",
        },
        "instructions": {"source": HISTORICAL_PLAN, "field": "developer_instructions", "policy": "copy_exactly"},
        "grading": {**historical["grading"], "policy_scope": "policy_blocks_not_full220_rerun_identity",
                    "pin_semantics": "source_consistency_not_judge_accuracy"},
        "vm": {
            "fresh_snapshot_per_task": True, "fresh_workdir_per_task": True,
            "prior_conversations_allowed": False, "prior_caches_allowed": False, "prior_outputs_allowed": False,
            "image_sha256": None, "os_sha256": None, "package_manifest_sha256": None, "version_policy": None,
        },
        "authentication": {"supply_method": None, "disposal_method": None, "identity_scope": None},
        "execution": {
            "network_policy": None, "permission_policy": None, "timeout_seconds_per_task": None,
            "tool_calls_per_task": None, "turns_per_task": None, "retry_limit": None,
            "native_input_tokens_per_task": None, "native_output_tokens_per_task": None,
        },
        "capture": {
            "required": ["transcript", "tool_calls", "commands", "input_file_hashes", "output_file_hashes", "exit_status"],
            "credential_capture_allowed": False, "private_host_path_capture_allowed": False, "storage_policy": None,
        },
        "study": {
            "performance_comparison": False, "pool_with_foundry": False, "environment_only_causality": False,
            "repeats": None, "within_condition_spread": None,
            "pass_decision": "fresh_immutable_review_only_not_launch_approval", "failure_decision": "stop_before_spend",
        },
        "cost": {"policy": "record_cost_findings_only", "five_task_wallclock_seconds": None, "approved_maximum_usd": None},
        "usage": {
            "source": "github_copilot_native_only", "missing_usage_execution_policy": None,
            "missing_or_unpriced": "preserve_null_and_partial_reasons", "infer_missing_as_zero": False,
            "use_foundry_or_openai_tariff": False, "invent_currency_conversion": False,
        },
        "results": historical["results"], "observed": {name: None for name in OBSERVED_FACTS},
    }
    derived = {
        "task_ids": ids,
        "tasks": [{"task_id": task.task_id, "prompt_sha256": task.prompt_sha256,
                   "reference_file_paths": list(task.reference_file_paths),
                   "deliverable_file_extensions": list(task.deliverable_file_extensions),
                   "deliverable_formats": list(task.deliverable_formats)} for task in tasks],
        "input_file_versions": dataset["input_file_versions"],
        "developer_instructions_sha256": sha256_bytes(historical["developer_instructions"].encode("utf-8")),
    }
    return expected, derived


def _report() -> dict[str, Any]:
    return {
        "report_version": "ghcp-vm-gate-preflight-v1", "condition_id": CONDITION_ID,
        "configuration_valid": False, "configuration_problems": [REFUSAL], "plan_sha256": None,
        "evidence_boundary": "offline_source_consistency_not_observed_execution_or_launch_approval",
        "task_ids": [], "tasks": [], "input_file_versions": {}, "developer_instructions_sha256": None,
        "observed": {name: None for name in OBSERVED_FACTS},
        "launch_blockers": list(LAUNCH_BLOCKERS), "eligible_facts": [], "cleared_blockers": [],
        **{name: False for name in FALSE_FLAGS},
    }


def inspect_plan(
    plan: object, *, local_input_bundle: Path | None = None,
    reviewed_plan_sha256: str | None = None,
) -> dict[str, Any]:
    """Keep the legacy report unless explicit current-byte input verification succeeds."""
    try:
        _require(type(plan) is dict)
        sources = _sources(plan)
        expected, derived = _expected(sources)
        _require(set(plan) == set(expected) | {"source_pins"})
        _require(canonical_json({key: value for key, value in plan.items() if key != "source_pins"}) == canonical_json(expected))
        report = {**_report(), **derived, "configuration_valid": True, "configuration_problems": [],
                  "plan_sha256": sha256_bytes(canonical_json(plan))}
        if local_input_bundle is None:
            _require(reviewed_plan_sha256 is None)
            return report
        # No import or extra observation on the legacy absent/null path.
        from ghcp_vm_input_bundle import BOUNDARY, verify_ghcp_input_bundle

        bundle = verify_ghcp_input_bundle(
            plan, reviewed_plan_sha256=reviewed_plan_sha256, bundle_root=local_input_bundle,
        )
        satisfied = "original_task_input_materialization_unverified"
        return {
            **report,
            "local_input_bundle": {"sha256": bundle.sha256, "evidence_boundary": BOUNDARY},
            "eligible_facts": ["local_original_task_input_materialization"],
            "cleared_blockers": [satisfied],
            "launch_blockers": [blocker for blocker in LAUNCH_BLOCKERS if blocker != satisfied],
        }
    except Exception:
        return _report()


def main(argv: list[str] | None = None) -> int:
    """Inspect local prerequisites; even verified local input bytes never enable launch."""
    try:
        arguments = sys.argv[1:] if argv is None else argv
        _require(type(arguments) is list and all(type(value) is str for value in arguments))
        _require(len(arguments) % 2 == 0)
        options = {}
        for name, value in zip(arguments[::2], arguments[1::2]):
            _require(name in {"--plan", "--local-input-bundle", "--reviewed-plan-sha256"} and name not in options)
            options[name] = value
        _require(("--local-input-bundle" in options) == ("--reviewed-plan-sha256" in options))
        report = inspect_plan(
            load_plan(Path(options["--plan"]) if "--plan" in options else None),
            local_input_bundle=Path(options["--local-input-bundle"]) if "--local-input-bundle" in options else None,
            reviewed_plan_sha256=options.get("--reviewed-plan-sha256"),
        )
    except Exception:
        report = _report()
    sys.stdout.write(canonical_json(report).decode("utf-8") + "\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
