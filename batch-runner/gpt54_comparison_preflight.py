"""Check one preregistration offline. This module cannot launch an experiment.

Exit 2 means the study must not spend, even when its configuration is valid.
The pinned adapters cannot yet express the requested effort and call limits.
Keeping that refusal separate from configuration validity prevents a passing
fixture from being mistaken for a verified Foundry deployment or a launch gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from core.agentic_v2_conversation_runner import ceilings_from
from core.agentic_v2_preregistration import seal
from core.codex_runtime_config import PINNED_CODEX_CLI_VERSION, PINNED_CODEX_SDK_VERSION
from core.execution_envelope_tasks import (
    catalog_sha256,
    load_task_catalog,
    select_advance_check_tasks,
)

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "96b181e1128039891f2cbbd9c26af9701e7e8e22"
ENVELOPE = "batch-runner/experiments/execution_envelope/"
PLAN = ROOT / ENVELOPE / "gpt54_sandboxv2_codex_comparison.yaml"
V2_TEMPLATE = ENVELOPE + "agentic_corrected_harness_plan.yaml"
CODEX_TEMPLATE = "batch-runner/experiments/exp033_codex_foundry_fixed5.yaml"
GRADER = "batch-runner/grading_configs/default_v2_sol_max.yaml"
REQUIRED_SOURCES = {
    ENVELOPE + "gdpval_task_catalog.json",
    ENVELOPE + "advance_check_plan.yaml",
    V2_TEMPLATE,
    CODEX_TEMPLATE,
    GRADER,
    "batch-runner/schemas/grade.schema.json",
    "batch-runner/core/result_projection.py",
    "batch-runner/core/agentic_v2_model_voice.py",
    "batch-runner/core/agentic_v2_conversation_runner.py",
    "batch-runner/core/codex_runtime_config.py",
    "batch-runner/core/codex_runner.py",
}

# These are findings on BASE_SHA, not user-editable waivers. Removing a blocker
# requires a reviewed implementation and a new contract, not an enabled flag.
LAUNCH_BLOCKERS = (
    "v2_reasoning_effort_unwired",
    "codex_reasoning_effort_unwired",
    "codex_native_model_call_and_token_limits_unenforced",
    "live_deployment_identity_and_input_bytes_not_verified",
    "comparison_dispatch_and_pinned_grading_not_wired",
)


def load_plan(path: Path = PLAN) -> dict[str, Any]:
    """Read the checked-in contract without reading credentials or the network."""
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("comparison plan must be an object")
    return value


def inspect_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Validate both target conditions; never turn target parity into readiness."""
    problems: list[str] = []

    def expect(name: str, actual: Any, expected: Any) -> None:
        # Preserve type as well as value: True is not the integer 1.
        if seal({"value": actual}) != seal({"value": expected}):
            problems.append(name)

    envelope = load_plan(ROOT / ENVELOPE / "advance_check_plan.yaml")
    v2 = load_plan(ROOT / V2_TEMPLATE)
    codex = load_plan(ROOT / CODEX_TEMPLATE)
    grader = load_plan(ROOT / GRADER)
    catalog = load_task_catalog()
    selection = select_advance_check_tasks(catalog)
    by_id = {task.task_id: task for task in catalog.tasks}

    expect("plan_version", plan.get("plan_version"), "gpt54-sandboxv2-codex-comparison-v1")
    expect("base_sha", plan.get("base_sha"), BASE_SHA)
    expect("comparison", plan.get("comparison"), "configuration_bundle")
    expect("paid_comparison_approved", plan.get("paid_comparison_approved"), True)
    expect("launch_enabled", plan.get("launch_enabled"), False)
    expect(
        "template_model",
        codex["condition_a"]["model"]["deployment"],
        v2["model"]["deployment"],
    )
    limits = ceilings_from(v2, SimpleNamespace(**v2["cost"]["chosen_settings"])).as_dict()
    limits.update(
        attempts_per_task=v2["fixed_settings"]["retry_max_attempts"],
        request_max_retries=0,
        stream_max_retries=0,
        self_review_max_attempts=0,
        resume_max_rounds=0,
    )
    expected = {
        "model": {
            "provider": "azure",
            "account": v2["azure_connection"]["account"],
            "deployment": "gpt-5.4",
            "resolved_model": "gpt-5.4",
            "route_profile": "direct-v1",
            "reasoning_effort": "xhigh",
            "automatic_model_switch_allowed": False,
        },
        "dataset": {
            "repo_id": catalog.dataset_repo_id,
            "revision": catalog.dataset_revision,
            "parquet_sha256": catalog.dataset_file_sha256,
            "catalog_sha256": catalog_sha256(),
            "cohort": "advance_check_5",
            "tasks": [
                {"task_id": task_id, "prompt_sha256": by_id[task_id].prompt_sha256}
                for task_id in selection.task_ids
            ],
            "input_file_versions": envelope["model_run_conditions"]["shared"][
                "input_file_versions"
            ],
        },
        "limits": limits,
        "grading": {
            "config": GRADER,
            "source_sha": BASE_SHA,
            "rubric_revision": catalog.dataset_revision,
            "prompt_version": grader["prompt"]["version"],
            "judge_model": grader["judge"]["model"],
            "judge_effort": grader["judge"]["reasoning"]["effort"],
            "grades_per_task": 1,
        },
        "results": {
            "projector": "core.result_projection.project_result_row",
            "receipt_schema": "cost-receipt-v1",
            "grade_schema": "batch-runner/schemas/grade.schema.json",
            "missing_or_unpriced_usage": "preserve_null_and_partial_reasons",
        },
        "cost": {
            "policy": envelope["cost"]["policy"],
            "approved_maximum_usd": None,
        },
    }
    expect("shared_controls", plan.get("shared"), expected)
    expect(
        "conditions",
        plan.get("conditions"),
        {
            "sandbox_v2": {
                "controls": expected,
                "template": V2_TEMPLATE,
                "workflow": ".github/workflows/agentic-v2-stage-run.yml",
                "isolation": "same-host",
                "replay_format": "faithful",
            },
            "codex": {
                "controls": expected,
                "template": CODEX_TEMPLATE,
                "workflow": ".github/workflows/batch-run.yml",
                "sdk_version": PINNED_CODEX_SDK_VERSION,
                "cli_version": PINNED_CODEX_CLI_VERSION,
            },
        },
    )
    expect(
        "repetition_matrix",
        plan.get("runs"),
        [
            {
                "run_id": f"gpt54_v2_codex_v1_{suffix}_r{repeat}",
                "condition": condition,
                "repeat": repeat,
                "task_count": 5,
            }
            for condition, suffix, repeat in (
                ("sandbox_v2", "v2", 1),
                ("codex", "codex", 1),
                ("codex", "codex", 2),
                ("sandbox_v2", "v2", 2),
            )
        ],
    )
    pins = plan.get("source_pins") or {}
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
        "launch_blockers": list(LAUNCH_BLOCKERS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args(argv)
    try:
        result = inspect_plan(load_plan(args.plan))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        result = {"configuration_valid": False, "launch_allowed": False, "error": str(error)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2  # This config/spec PR cannot authorize or dispatch a paid run.


if __name__ == "__main__":
    raise SystemExit(main())
