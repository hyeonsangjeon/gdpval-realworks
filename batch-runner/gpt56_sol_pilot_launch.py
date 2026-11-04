"""Admission for the approved Sol five-task Actions launch (WIP, no live bridge).

Route A reuses Step 2/Codex and Step 8; it does not convert the model-free
handoff's fake transport into a model client. Source and financial admission
are executable here. The missing live session/shard bridge is a source-owned
stop BEFORE credentials or model-client construction, not a dispatch input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import yaml

from core import runner_environment as host
import gpt56_pilot_usd_budget as usd
from gpt56_pilot_ledger_handoff import TASKS

ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "hyeonsangjeon/gdpval-realworks"
PROFILE = "batch-runner/experiments/execution_envelope/gpt56_sol_foundry_codex_pilot_source_20261030_grader_seal.yaml"
PROFILE_SHA256 = "90a222ac56ed9276689b31f154fbfbdeb6d98decb614556abca131c22cc3cfc6"
GRADER_SOURCE_HASH = "099755b009e7563e5b3824ac34c1ab2cf5c83b3cdf4aba7886b50e1c28003fd7"
WORKFLOW = "gpt56-sol-paid-pilot.yml"
SCHEMA = "sol-pilot-launch-admission-v1"

# These are implementation omissions, not an extra owner spending decision.
# No CLI/env/manifest option may waive them. Remove each only with its real
# consumer and non-model tests in the same reviewed source change.
UNIMPLEMENTED_BRIDGE = (
    "five_task_live_receipt_and_result_assembly_for_step8",
    "step8_local_shard_invocation_and_retained_grade_assembly",
    "durable_pilot_once_claim_and_prior_diagnostic_reconciliation",
    "actions_input_runtime_and_worker_checkpoint_publication",
)


class LaunchRefused(ValueError):
    def __init__(self, code="sol_pilot_launch_refused"):
        self.code = code
        super().__init__(code)


def require(value, code="sol_pilot_launch_refused"):
    if not value:
        raise LaunchRefused(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def execution_stages():
    """One solve and one grading pass per fixed task, all jobs serial.

    Grading starts only after all five solve outcomes have been assembled.
    Failed/missing solve outcomes must remain in the five-task denominator.
    The paid bridge must never manufacture missing tasks as successful rows.
    """
    return tuple({"index": index, "phase": phase, "task_index": task_index,
                  "task_id": task_id,
                  "entrypoint": "step2_run_inference.run_inference" if phase == "solve" else "step8_grade.main",
                  "previous_index": index - 1 if index else None}
                 for index, (phase, task_index, task_id) in enumerate(
                     (phase, task_index, task_id)
                     for phase in ("solve", "grade")
                     for task_index, task_id in enumerate(TASKS)))


def context_from_environment():
    return {key: os.environ.get(name, "") for key, name in (
        ("repository", "GITHUB_REPOSITORY"), ("event", "GITHUB_EVENT_NAME"),
        ("ref", "GITHUB_REF"), ("run_id", "GITHUB_RUN_ID"),
        ("run_attempt", "GITHUB_RUN_ATTEMPT"), ("source_sha", "GITHUB_SHA"),
        ("workflow_sha", "GITHUB_WORKFLOW_SHA"),
    )}


def validate_request(*, execute_paid, expected_source_sha, context, checkout_sha,
                     runner_observation):
    """Pure admission predicate; production supplies actual Git/host readings."""
    require(execute_paid is True, "explicit_execute_paid_required")
    require(type(expected_source_sha) is str and
            re.fullmatch(r"[0-9a-f]{40}", expected_source_sha) is not None,
            "reviewed_source_sha_required")
    require(context.get("repository") == REPOSITORY and
            context.get("event") == "workflow_dispatch" and
            context.get("ref") == "refs/heads/main", "main_manual_dispatch_required")
    require(context.get("run_attempt") == "1", "paid_rerun_refused")
    require(type(context.get("run_id")) is str and
            re.fullmatch(r"[1-9][0-9]{0,19}", context["run_id"]) is not None,
            "actions_run_identity_required")
    require(context.get("source_sha") == context.get("workflow_sha") == checkout_sha ==
            expected_source_sha, "source_or_workflow_sha_mismatch")
    expected_host = {
        "github_actions": "true", "github_hosted": True,
        "eligible_for_execution": True, "runner_environment": "github-hosted",
        "os_id": "ubuntu", "os_version_id": "24.04", "image_os": "ubuntu24",
        "runner_os": "Linux", "platform_system": "Linux",
        "run_id": context["run_id"], "run_attempt": "1",
    }
    require(all(type(runner_observation.get(key)) is type(value) and
                runner_observation.get(key) == value for key, value in expected_host.items()),
            "hosted_ubuntu_2404_required")
    require(type(runner_observation.get("image_version")) is str and
            re.fullmatch(r"[0-9]{8}\.[0-9]+(?:\.[0-9]+)?", runner_observation["image_version"])
            is not None, "runner_image_version_required")
    return {key: context[key] for key in
            ("repository", "run_id", "run_attempt", "source_sha")}


def verify_contracts(expected_source_sha):
    """Verify current source using existing readers; never change their flags."""
    import gpt56_sol_codex_pilot_preflight as pilot
    import gpt56_pilot_grader_seal as grader_seal

    raw = (ROOT / PROFILE).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == PROFILE_SHA256, "source_profile_mismatch")
    plan, _, registration = pilot.source_plan_snapshot(
        expected_plan_sha256=pilot.seal(yaml.safe_load(raw)),
        reviewed_source_sha=expected_source_sha,
    )
    require(registration is not None and registration["status"] == "source_verified",
            "source_registration_refused")
    seal_receipt, _ = grader_seal.verify(ROOT)
    require(seal_receipt["grader_source_hash"] == GRADER_SOURCE_HASH,
            "grader_successor_seal_refused")
    require(tuple(row["task_id"] for row in plan["dataset"]["tasks"]) == TASKS and
            plan["pilot"]["task_count"] == 5 and plan["pilot"]["repeats"] == 1 and
            plan["identity"]["model"] == "gpt-5.6-sol" and
            plan["identity"]["reasoning_effort"] == "max" and
            plan["codex_request"]["model_context_window"] == 1_000_000 and
            plan["grading"]["prompt_version"] == "v2.2" and
            plan["grading"]["rubric_revision"] == "11e7900cdcac61bc4daf59e65feb238acda98fbf" and
            plan["limits"]["timeout_seconds_per_attempt"] == 1800 and
            plan["limits"]["logical_turns_per_attempt"] == 1,
            "fixed_pilot_contract_mismatch")
    usd.price_document()
    require(usd.APPROVED_MAXIMUM_USD == 200, "combined_usd_cap_mismatch")
    return {
        "source_profile": PROFILE, "source_profile_sha256": PROFILE_SHA256,
        "plan_sha256": pilot.seal(plan), "grader_source_hash": GRADER_SOURCE_HASH,
        "task_ids": list(TASKS), "model": "gpt-5.6-sol", "effort": "max",
        "context_requested": 1_000_000, "context_not_reported": "record_and_continue",
        "reported_context_mismatch": "stop", "served_model_mismatch": "stop",
        "prompt_version": "v2.2", "rubric_revision": plan["grading"]["rubric_revision"],
        "combined_modeled_usd_cap": "200", "pricing_policy": "owner_20261030_list_prices",
        "unknown_usage": "consume_reservation_without_resend",
        "attempt_timeout_seconds": 1800, "logical_turns_per_attempt": 1,
        "requested_is_not_served_evidence": True,
    }


def require_live_bridge():
    require(not UNIMPLEMENTED_BRIDGE, "sol_pilot_execution_bridge_incomplete")


def admit(*, execute_paid, expected_source_sha):
    # Missing explicit opt-in is rejected before Git, imports, host probes,
    # credentials, network, workspaces or any financial file is opened.
    require(execute_paid is True, "explicit_execute_paid_required")
    context = context_from_environment()
    observation = host.require_execution()
    checkout_sha = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "rev-parse", "HEAD"], cwd=ROOT,
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    lineage = validate_request(execute_paid=execute_paid,
        expected_source_sha=expected_source_sha, context=context,
        checkout_sha=checkout_sha, runner_observation=observation)
    contracts = verify_contracts(expected_source_sha)
    return {"schema": SCHEMA, "route": "A_existing_step2_codex_step8", "lineage": lineage,
            "contracts": contracts, "runner": host.receipt("inference", observation),
            "stages": list(execution_stages()), "implementation_ready": not UNIMPLEMENTED_BRIDGE,
            "remaining_implementation": list(UNIMPLEMENTED_BRIDGE),
            "model_calls": 0, "judge_calls": 0, "new_reservation_usd": "0"}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "sol_pilot_arguments_refused\n")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("action", choices=("admit", "run-stage"))
    parser.add_argument("--execute-paid", action="store_true")
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--stage-index", type=int, choices=range(10))
    parser.add_argument("--predecessor-artifact-id")
    parser.add_argument("--predecessor-sha256")
    args = parser.parse_args(argv)
    report = {"schema": SCHEMA, "model_calls": 0, "judge_calls": 0,
              "new_reservation_usd": "0", "implementation_ready": False}
    try:
        require(args.action == "run-stage" or all(value is None for value in (
            args.stage_index, args.predecessor_artifact_id, args.predecessor_sha256)),
            "unexpected_stage_arguments")
        if args.action == "run-stage":
            require(args.stage_index is not None, "stage_index_required")
            if args.stage_index == 0:
                require(args.predecessor_artifact_id is None and args.predecessor_sha256 is None,
                        "first_stage_predecessor_refused")
            else:
                require(type(args.predecessor_artifact_id) is str and
                        re.fullmatch(r"[1-9][0-9]{0,19}", args.predecessor_artifact_id) is not None and
                        type(args.predecessor_sha256) is str and
                        re.fullmatch(r"[0-9a-f]{64}", args.predecessor_sha256) is not None,
                        "immutable_predecessor_required")
        report = admit(execute_paid=args.execute_paid, expected_source_sha=args.expected_source_sha)
        require_live_bridge()  # BEFORE any authentication or paid pipeline import.
        # No dormant paid call is hidden behind an incomplete integration.
        # The completed bridge must replace this stop with real owned consumers.
        raise LaunchRefused("sol_pilot_execution_bridge_incomplete")
    except Exception as error:
        report["refusal_code"] = error.code if isinstance(error, (LaunchRefused, host.ExecutionEnvironmentRefused)) else "sol_pilot_admission_refused"
        report["paid_execution_allowed"] = False
        print(canonical(report).decode("ascii"))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
