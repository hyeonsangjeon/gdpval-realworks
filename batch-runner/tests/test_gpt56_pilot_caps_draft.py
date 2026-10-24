"""Check the inert proposal against recorded usage, without runtime imports."""

import json
from math import ceil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
DRAFT = ROOT / "batch-runner/experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml"


def _draft():
    return yaml.safe_load(DRAFT.read_text())


def test_usage_evidence_and_rounding():
    draft = _draft()
    evidence = draft["evidence"]["historical_usage"]
    recorded = json.loads((ROOT / evidence["path"]).read_text())
    costs = [row["problem_solving_cost"] for row in recorded["results"]]
    assert recorded["run_id"] == evidence["run_id"]
    assert len(costs) == evidence["tasks"] == draft["task_count"] == 5
    assert sum(row["model_calls"] for row in costs) == evidence["recorded_turns"] == 9
    for field in ("input_tokens", "output_tokens"):
        assert sum(row["usage"][field] for row in costs) == evidence[field]
        maximum = max(row["usage"][field] for row in costs)
        assert maximum == evidence["maximum_task_" + field]
        row = next(row for row in recorded["results"] if row["task_id"] == evidence["maximum_task_id"])
        assert row["problem_solving_cost"]["usage"][field] == maximum
    attempt = draft["per_attempt"]
    assert attempt["input_tokens"] == ceil(evidence["maximum_task_input_tokens"] / 100000) * 100000
    assert attempt["output_tokens"] == ceil(evidence["maximum_task_output_tokens"] / 10000) * 10000
    assert attempt["native_model_calls"] == ceil(attempt["input_tokens"] / draft["evidence"]["diagnostic"]["input_tokens"])


def test_retry_inclusive_caps_and_registration_are_unchanged():
    draft = _draft()
    plan = yaml.safe_load((ROOT / draft["registered_plan"]).read_text())
    limits = plan["limits"]
    assert draft["attempts_per_task"] == 1 + limits["infrastructure_retries_per_task"] == 4
    assert draft["infrastructure_retries_per_task"] == limits["infrastructure_retries_per_task"]
    assert draft["task_count"] == plan["pilot"]["task_count"]
    assert draft["per_attempt"]["wall_clock_seconds"] == limits["timeout_seconds_per_attempt"]
    assert draft["per_attempt"]["logical_turns"] == limits["logical_turns_per_attempt"]
    for name in ("request_max_retries", "stream_max_retries", "resume_max_rounds", "self_qa_enabled"):
        assert draft[name] == limits[name] == 0
    for name in ("native_model_calls", "native_input_tokens", "native_output_tokens"):
        assert limits[name + "_per_attempt"] is None
    attempt, task, pilot = (draft[name] for name in ("per_attempt", "per_task", "per_pilot"))
    for field in ("native_model_calls", "logical_turns", "input_tokens", "output_tokens"):
        assert task[field] == attempt[field] * draft["attempts_per_task"]
        assert pilot[field] == task[field] * draft["task_count"]
    assert task["retry_wait_seconds"] == sum((60, 120, 240))
    assert task["wall_clock_seconds"] == attempt["wall_clock_seconds"] * 4 + task["retry_wait_seconds"]
    for field in ("wall_clock_seconds", "retry_wait_seconds"):
        assert pilot[field] == task[field] * 5


def test_proposal_does_not_claim_spend_or_deployment_approval():
    draft = _draft()
    plan = yaml.safe_load((ROOT / draft["registered_plan"]).read_text())
    baseline = yaml.safe_load((ROOT / plan["baseline"]).read_text())
    check = draft["deployment_check"]
    assert draft["status"] == "draft_not_approved_or_enforced"
    assert draft["launch_enabled"] is plan["launch_enabled"] is False
    assert draft["cost"]["approved_maximum_usd"] is plan["cost"]["approved_maximum_usd"] is None
    assert "null # owner decision" in DRAFT.read_text()
    assert draft["evidence"]["diagnostic"]["archive_available_locally"] is True
    assert check["requested_name"] == check["plan_identity_model"] == plan["identity"]["model"]
    assert check["plan_grading_judge_model"] == plan["grading"]["judge_model"] == "gpt-5.6-sol"
    assert check["plan_foundry_identity_deployment"] is plan["foundry_identity"]["deployment"] is None
    assert check["baseline_condition_a_deployment"] == baseline["condition_a"]["model"]["deployment"] == "gpt-5.4"
    assert check["baseline_codex_model"] == baseline["execution"]["codex"]["model"] == "gpt-5.4"
    assert check["archived_diagnostic_input"] == check["requested_name"] == "gpt-5.6-sol"
    assert check["baseline_deployment_reachable_by_pilot_fallback"] is False
    assert check["generated_runtime_template_deployment"] is check["preflight_expected_deployment"] is None
    assert check["comparison"]["baseline_condition_a_deployment"] == "mismatch_historical_baseline_only"
    assert check["comparison"]["baseline_codex_model"] == "mismatch_historical_baseline_only"


def test_archived_connection_evidence_does_not_invent_served_identity():
    diagnostic = _draft()["evidence"]["diagnostic"]
    plan = yaml.safe_load((ROOT / _draft()["registered_plan"]).read_text())
    assert diagnostic["run_id"] == "39407062120"
    assert diagnostic["artifact_id"] == "12257312458"
    assert diagnostic["archive_sha256"] == "5d1a2540f0ba1291093b231d0e12e489ca197c32683aee521fb1622893600841"
    assert diagnostic["verdict"] == "connected"
    assert diagnostic["requested_deployment"] == plan["identity"]["model"] == "gpt-5.6-sol"
    for key in ("served_model", "served_model_version", "account_resource_id",
                "project_resource_id", "deployment_resource_id"):
        assert diagnostic[key] is None
    for key in ("pinned_sdk_version", "installed_sdk_version"):
        assert diagnostic[key] == plan["identity"]["sdk_version"] == "0.147.0"
    for key in ("pinned_cli_version", "installed_cli_version"):
        assert diagnostic[key] == plan["identity"]["cli_version"] == "0.147.0"
    assert diagnostic["endpoint_kind"] == plan["foundry_route"]["route_profile"] == "direct-v1"
    assert diagnostic["provider_id"] == plan["foundry_route"]["provider_id"] == "gdpval-foundry"
    assert diagnostic["endpoint_host_fingerprint"] == "sha256:69057d59166a82e3"
    assert diagnostic["endpoint_path"] == "/openai/v1/"
