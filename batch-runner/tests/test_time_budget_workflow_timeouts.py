"""Static workflow arithmetic only: no Actions, host probe, credentials or model.

Generation/cleanup belong to the immutable time-budget registration, not the
outer job. Ten minutes reserve checkout/setup/login/artifact operations which
have no per-step timeout. This planning reserve is not their hard runtime cap.
"""

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
ENVELOPE = ROOT / "batch-runner/experiments/execution_envelope"
PLAN = ENVELOPE / "gpt54_sandboxv2_codex_time_budget_v1.yaml"
OVERHEAD_SECONDS = 10 * 60
HOSTED_MAX_MINUTES = 6 * 60
WORKFLOWS = {
    "v2": {
        "file": "gpt54-time-budget-first-v2.yml", "job_minutes": 55, "step_seconds": 23 * 60,
        "execute_name": "Execute the real first V2 callable once on this host",
        "execute_marker": 'gpt54_time_budget_v2_ci.py" execute ',
        "overhead_steps": {
            "Refuse wrong source, caller, cell and reruns before credentials",
            "Check out the exact reviewed bootstrap and workflow",
            "Verify bootstrap and create distinct linked runtime and frozen sources",
            "Setup pinned Python", "Azure Login through the existing approved connection",
            "Validate only the allowlisted nonsecret completion envelope",
            "Retain the allowlisted metadata only",
        },
    },
    "codex": {
        "file": "gpt54-time-budget-first-codex.yml", "job_minutes": 65, "step_seconds": 30 * 60,
        "execute_name": "Execute the accepted native callable once",
        "execute_marker": 'gpt54_time_budget_codex_ci.py" execute ',
        "overhead_steps": {
            "Refuse wrong source, caller, cell and reruns before credentials",
            "Check out the exact reviewed bootstrap and workflow",
            "Verify bootstrap and create distinct linked runtime and frozen sources",
            "Setup pinned Python", "Retain the credential-free runner and sandbox proof",
            "Azure Login through the existing approved connection",
            "Publish only allowlisted completion metadata",
        },
    },
}


def _workflow(condition):
    return yaml.safe_load((ROOT / ".github/workflows" / WORKFLOWS[condition]["file"]).read_text())


def _positive_integer(value, reason):
    assert type(value) is int and value > 0, reason
    return value


def _budget(condition, document, plan):
    job = document["jobs"]["observation"]
    minutes = _positive_integer(job.get("timeout-minutes"), "finite_job_timeout_required")
    assert minutes <= HOSTED_MAX_MINUTES, "hosted_job_limit_exceeded"
    generation = plan["generation_budget"]
    runtime_seconds = (_positive_integer(generation["seconds_per_observation"], "registered_generation_required")
                       + _positive_integer(generation["local_cleanup_grace_seconds"], "registered_cleanup_required"))
    assert runtime_seconds == generation["max_planned_host_lifecycle_seconds"], "registered_lifecycle_mismatch"
    spec, steps = WORKFLOWS[condition], job["steps"]
    execute = [step for step in steps if spec["execute_marker"] in step.get("run", "")]
    assert len(execute) == 1 and execute[0]["name"] == spec["execute_name"], "single_registered_execution_required"
    # Do not impose a new rounded step timeout on the registered 1200+20 path.
    assert "timeout-minutes" not in execute[0], "generation_timeout_owned_by_registration"
    names = [step["name"] for step in steps]
    assert len(names) == len(set(names)), "unique_step_inventory_required"
    untimed = {step["name"] for step in steps if step is not execute[0] and "timeout-minutes" not in step}
    assert untimed == spec["overhead_steps"], "unaccounted_operational_step"
    timed_seconds = sum(60 * _positive_integer(step["timeout-minutes"], "finite_step_timeout_required")
                        for step in steps if step is not execute[0] and "timeout-minutes" in step)
    required = timed_seconds + runtime_seconds + OVERHEAD_SECONDS
    assert minutes * 60 >= required, (
        f"job_timeout_too_short: {condition}: job={minutes * 60}s required={required}s "
        f"(steps={timed_seconds}s registered={runtime_seconds}s overhead={OVERHEAD_SECONDS}s)"
    )
    return {"step_seconds": timed_seconds, "registered_seconds": runtime_seconds,
            "required_seconds": required, "job_seconds": minutes * 60,
            "headroom_seconds": minutes * 60 - timed_seconds - runtime_seconds}


@pytest.fixture
def plan():
    return yaml.safe_load(PLAN.read_text())


@pytest.mark.parametrize("condition", WORKFLOWS)
def test_observation_job_covers_all_declared_steps_registered_lifecycle_and_operating_reserve(condition, plan):
    value = _budget(condition, _workflow(condition), plan)
    assert value["step_seconds"] == WORKFLOWS[condition]["step_seconds"]
    assert value["registered_seconds"] == 1220
    assert value["job_seconds"] == WORKFLOWS[condition]["job_minutes"] * 60
    assert value["headroom_seconds"] >= OVERHEAD_SECONDS


@pytest.mark.parametrize("condition", WORKFLOWS)
def test_original_45_minute_job_is_a_regression_even_for_v2(condition, plan):
    document = _workflow(condition)
    document["jobs"]["observation"]["timeout-minutes"] = 45
    with pytest.raises(AssertionError, match="job_timeout_too_short"):
        _budget(condition, document, plan)


@pytest.mark.parametrize("condition", WORKFLOWS)
def test_reserve_cannot_disappear_in_minute_rounding(condition, plan):
    document = _workflow(condition)
    required = WORKFLOWS[condition]["step_seconds"] + 1220 + OVERHEAD_SECONDS
    document["jobs"]["observation"]["timeout-minutes"] = required // 60
    with pytest.raises(AssertionError, match="job_timeout_too_short"):
        _budget(condition, document, plan)
    document["jobs"]["observation"]["timeout-minutes"] += 1
    assert _budget(condition, document, plan)["headroom_seconds"] >= OVERHEAD_SECONDS


@pytest.mark.parametrize("condition", WORKFLOWS)
@pytest.mark.parametrize("change,reason", [
    ("raise_step", "job_timeout_too_short"),
    ("drop_step_timeout", "unaccounted_operational_step"),
    ("new_unbounded_step", "unaccounted_operational_step"),
    ("new_timed_step", "job_timeout_too_short"),
    ("duplicate_step", "unique_step_inventory_required"),
    ("omit_execute", "single_registered_execution_required"),
    ("second_execute", "single_registered_execution_required"),
    ("round_execution", "generation_timeout_owned_by_registration"),
])
def test_later_workflow_edits_cannot_silently_exhaust_job_time(condition, plan, change, reason):
    document = _workflow(condition)
    job = document["jobs"]["observation"]
    job["timeout-minutes"] = WORKFLOWS[condition]["job_minutes"]
    timed = next(step for step in job["steps"] if "timeout-minutes" in step)
    execute = next(step for step in job["steps"] if step["name"] == WORKFLOWS[condition]["execute_name"])
    if change == "raise_step": timed["timeout-minutes"] += 20
    elif change == "drop_step_timeout": timed.pop("timeout-minutes")
    elif change == "new_unbounded_step": job["steps"].append({"name": "unreviewed upload", "run": "true"})
    elif change == "new_timed_step": job["steps"].append({"name": "extra upload", "run": "true", "timeout-minutes": 20})
    elif change == "duplicate_step": job["steps"].append(deepcopy(timed))
    elif change == "omit_execute": job["steps"].remove(execute)
    elif change == "second_execute": job["steps"].append(deepcopy(execute))
    elif change == "round_execution": execute["timeout-minutes"] = 21
    with pytest.raises(AssertionError, match=reason):
        _budget(condition, document, plan)


@pytest.mark.parametrize("condition", WORKFLOWS)
@pytest.mark.parametrize("value", [None, 0, -1, True, 65.5, "65", "${{ inputs.timeout }}"])
def test_job_timeout_must_be_an_explicit_positive_integer(condition, plan, value):
    document = _workflow(condition)
    document["jobs"]["observation"]["timeout-minutes"] = value
    with pytest.raises(AssertionError, match="finite_job_timeout_required"):
        _budget(condition, document, plan)


@pytest.mark.parametrize("condition", WORKFLOWS)
def test_hosted_six_hour_limit_cannot_be_exceeded(condition, plan):
    document = _workflow(condition)
    document["jobs"]["observation"]["timeout-minutes"] = 361
    with pytest.raises(AssertionError, match="hosted_job_limit_exceeded"):
        _budget(condition, document, plan)


def test_both_original_registrations_and_generation_cleanup_values_are_unchanged(plan):
    assert hashlib.sha256(PLAN.read_bytes()).hexdigest() == "e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699"
    comparison = ENVELOPE / "gpt54_sandboxv2_codex_comparison.yaml"
    assert hashlib.sha256(comparison.read_bytes()).hexdigest() == "3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1"
    assert plan["generation_budget"] == {
        "policy": "external_elapsed_time_v1", "seconds_per_observation": 1200,
        "starts_at": "first_generation_start", "includes": ["all_waits", "native_internal_recovery"],
        "deadline_action": "request_interruption", "local_cleanup_grace_seconds": 20,
        "cleanup_grace_recorded_separately": True, "max_planned_host_lifecycle_seconds": 1220,
        "remote_billing_bound": False, "server_side_cancellation_guaranteed": False,
    }
