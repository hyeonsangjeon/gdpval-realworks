"""Validate the Copilot Sol pilot registration offline; never launch a run.

Exit 2 is intentional even for a valid registration. The pinned runtime is
Foundry-only and cannot verify the requested Copilot route, Max, or Long 1M.
This check is not wired into existing paid workflows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from core.agentic_v2_preregistration import seal
from core.codex_runtime_config import PINNED_CODEX_CLI_VERSION, PINNED_CODEX_SDK_VERSION
from core.cost_receipts import RECEIPT_SCHEMA_VERSION
from core.execution_envelope_tasks import (
    catalog_sha256,
    load_task_catalog,
    select_advance_check_tasks,
)
from core.experiment_config import ExperimentConfig
from gpt54_comparison_preflight import load_plan

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "6ccd4ae346d302e3da0af455a3c5a72ec79a6984"
ENVELOPE = "batch-runner/experiments/execution_envelope/"
PLAN = ROOT / ENVELOPE / "gpt56_sol_copilot_codex_pilot.yaml"
BASELINE = "batch-runner/experiments/exp035_codex_foundry_full220.yaml"
GRADER = "batch-runner/grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"
REQUIRED_SOURCES = {
    BASELINE,
    GRADER,
    ENVELOPE + "gdpval_task_catalog.json",
    ENVELOPE + "advance_check_plan.yaml",
    "batch-runner/core/experiment_config.py",
    "batch-runner/core/config.py",
    "batch-runner/core/codex_runtime_config.py",
    "batch-runner/core/codex_runner.py",
    "batch-runner/core/codex_cost.py",
    "batch-runner/core/executor.py",
    "batch-runner/core/cost_receipts.py",
    "batch-runner/core/result_projection.py",
    "batch-runner/schemas/grade.schema.json",
}
# Findings on BASE_SHA, not editable waivers. Runtime changes need new review.
LAUNCH_BLOCKERS = (
    "github_copilot_route_not_implemented",
    "max_and_long_1m_not_forwarded_or_verified",
    "native_call_and_token_limits_unresolved",
    "live_identity_and_input_bytes_unverified",
    "pilot_dispatch_and_grading_identity_not_wired",
    "copilot_usage_and_tariff_mapping_unverified",
)


def inspect_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Check declared controls against existing sources, not live capabilities."""
    baseline = ExperimentConfig.from_yaml(str(ROOT / BASELINE))
    envelope = load_plan(ROOT / ENVELOPE / "advance_check_plan.yaml")
    grader = load_plan(ROOT / GRADER)
    catalog = load_task_catalog()
    selection = select_advance_check_tasks(catalog)
    tasks = {task.task_id: task for task in catalog.tasks}
    expected = {
        "plan_version": "gpt56-sol-copilot-codex-pilot-v1",
        "base_sha": BASE_SHA,
        "baseline": BASELINE,
        "owner_approved_eventual_execution": True,
        "launch_enabled": False,
        "identity": {
            "provider": "github_copilot",
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
        "pilot": {
            "run_id": "gpt56_sol_copilot_codex_pilot5_v1",
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
            "source_sha": BASE_SHA,
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
            "use_foundry_or_openai_tariff_for_copilot": False,
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
