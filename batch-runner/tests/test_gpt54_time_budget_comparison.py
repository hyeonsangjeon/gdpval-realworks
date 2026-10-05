"""Offline registration evidence, not observations of private tasks or a model."""

import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import gpt54_comparison_preflight as historical
import gpt54_time_budget_comparison as prospective
from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks
from gpt54_codex_input_capture import (
    ComparisonRuntimeLaunchRefused,
    require_comparison_runtime_launch,
)
from .test_gpt54_run_config_bundle import _guards


@pytest.fixture(autouse=True)
def model_free(monkeypatch):
    calls = _guards(monkeypatch)

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("registration attempted private input or preparation")

    for name in (
        "gpt54_disposable_checkout.prepare_disposable_checkout",
        "gpt54_prepared_input_attestation._source_snapshot",
        "pandas.read_parquet",
    ):
        monkeypatch.setattr(name, forbidden)
    yield
    assert calls == []


def test_time_budget_registration_genuine_source_and_finite_scope():
    plan = prospective.load_registration()
    compiled = prospective.compile_registration(plan)
    report = compiled.as_dict()
    intent = report["registered_intent"]
    profile = historical.load_plan(historical.ROOT / prospective.SOURCE_PROFILE)
    # Genuine unchanged full-source validation, including the real template
    # closure, occurs inside compile_registration. No pin/helper is replaced.
    assert len(report["source_evidence"]["validated_source_pins"]) == 37
    assert report["source_evidence"]["validated_source_pins"] == profile["source_pins"]
    assert intent["shared"] == {name: profile["shared"][name] for name in prospective.SHARED_FACTS}
    assert intent["shared"]["grading"]["template_source_sha256"] == (
        "37e1791da757a247eaf513352425128eb5c1772f3f6c814d1432b5eb665d48ce"
    )
    assert report["source_evidence"]["private_originals_verified"] is False
    assert report["source_evidence"]["template_not_materialized_grader"] is True
    assert report["manifest_sha256"] == historical.seal(plan)
    assert intent["study_id"] == "gpt54_sandboxv2_codex_time_budget_v1"
    assert intent["comparison"] == "configuration_bundle"
    assert intent["shared"]["model"]["deployment"] == "gpt-5.4"
    assert intent["shared"]["model"]["route_profile"] == "direct-v1"
    assert intent["shared"]["model"]["reasoning_effort"] == "xhigh"
    task_ids = select_advance_check_tasks(load_task_catalog()).task_ids
    assert [(run.run_id, run.condition, run.repeat) for run in compiled.runs] == [
        ("gpt54_time_budget_v1_v2_r1", "sandbox_v2", 1),
        ("gpt54_time_budget_v1_codex_r1", "codex", 1),
        ("gpt54_time_budget_v1_codex_r2", "codex", 2),
        ("gpt54_time_budget_v1_v2_r2", "sandbox_v2", 2),
    ]
    assert all(run.task_ids == task_ids for run in compiled.runs)
    cells = {(run.run_id, task) for run in compiled.runs for task in run.task_ids}
    assert len(cells) == sum(len(run.task_ids) for run in compiled.runs) == 20
    assert {run.run_id for run in compiled.runs}.isdisjoint(row["run_id"] for row in profile["runs"])
    assert intent["scope"]["inference_concurrency"] == 1
    assert intent["scope"]["max_generation_observations"] == 20
    assert intent["scope"]["external_attempts_per_observation"] == 1
    assert all(intent["scope"][name] is False for name in (
        "external_retry_allowed", "external_resume_allowed", "external_replay_allowed",
        "pool_with_other_studies",
    ))
    assert intent["grading_policy"] == {
        "attempts_per_resulting_observation": 1,
        "failed_or_missing_outcomes": "retain", "regrade_for_score": False,
    }
    assert not {"commands", "dispatch_plan", "config_json", "grading_runs"} & set(report)
    assert set(intent["runs"][0]) == {"run_id", "condition", "repeat", "task_ids"}
    # Returned JSON cannot mutate the sealed result; key order is not evidence.
    report["registered_intent"]["scope"]["inference_concurrency"] = 99
    reordered = json.loads(json.dumps(plan, sort_keys=True))
    assert prospective.compile_registration(reordered).canonical_bytes() == compiled.canonical_bytes()
    with pytest.raises(FrozenInstanceError):
        compiled.runs[0].repeat = 3


def test_time_budget_registration_labels_intent_without_enforcement_or_launch(capsys):
    assert prospective.main([]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["registration_valid"] is True
    document = report["compiled"]
    intent = document["registered_intent"]
    budget = intent["generation_budget"]
    assert budget == {
        "policy": "external_elapsed_time_v1", "seconds_per_observation": 1200,
        "starts_at": "first_generation_start", "includes": ["all_waits", "native_internal_recovery"],
        "deadline_action": "request_interruption", "local_cleanup_grace_seconds": 20,
        "cleanup_grace_recorded_separately": True, "max_planned_host_lifecycle_seconds": 1220,
        "remote_billing_bound": False, "server_side_cancellation_guaranteed": False,
    }
    assert budget["max_planned_host_lifecycle_seconds"] == (
        budget["seconds_per_observation"] + budget["local_cleanup_grace_seconds"]
    )
    assert "limits" not in intent["shared"]
    assert intent["shared"]["cost"]["approved_maximum_usd"] is None
    assert intent["conditions"]["sandbox_v2"]["local_settings"] == {
        "max_model_turns": 9, "max_written_tokens_per_turn": 8192,
    }
    assert "local_settings" not in intent["conditions"]["codex"]
    assert intent["conditions"]["codex"]["retry_settings_bound_all_native_recovery"] is False
    assert intent["conditions"]["codex"]["native_turn_is_v2_turn_equivalent"] is False
    assert intent["native_measurements"] == {
        "policy": "observation_only_when_available",
        "metrics": ["model_attempt_count", "repeated_request_count", "input_tokens",
                    "output_tokens", "written_tokens", "native_retries"],
        "unavailable": "explicitly_unavailable_not_zero_or_estimated",
        "token_accounting": "difference_cumulative_totals_not_sum_snapshots",
        "cached_input_and_reasoning": "subsets_not_additional_tokens",
        "incomplete_usage": "preserve_null_and_partial_reasons",
        "shared_native_request_token_hard_caps": False, "native_turn_equals_model_attempt": False,
    }
    assert intent["decision_rule"] == {
        "analysis": "descriptive_paired_outcome_and_grade_differences",
        "pairing": ["task_id", "repeat"], "spread": "within_condition_across_fixed_observations",
        "early_selection": False, "score_dependent_repeats": False,
        "precise_uncertainty_claim": False, "isolated_harness_causality_claim": False,
        "equal_native_compute_claim": False,
    }
    assert document["implementation_status"] == {
        "registration_compiler": "implemented_offline", "generation_deadline": "not_integrated",
        "cleanup_grace": "not_integrated", "native_measurement_availability": "not_verified",
        "executor_enforces_registered_policy": False,
        "dispatch_and_capture": "not_integrated_for_this_study", "observations_executed_by_compiler": 0,
    }
    assert document["launch_authority"] == {
        "launch_allowed": False, "execution_enabled": False, "full_220_allowed": False,
        "blockers": list(prospective.LAUNCH_BLOCKERS),
    }
    with pytest.raises(ComparisonRuntimeLaunchRefused, match="^comparison_runtime_launch_refused$"):
        require_comparison_runtime_launch()


@pytest.mark.parametrize("path,value,reason", [
    (("plan_version",), "gpt54-sandboxv2-codex-comparison-v1", "plan_version"),
    (("study_id",), "gpt54_v2_codex_v1", "study_id"),
    (("comparison",), "isolated_harness_causality", "comparison"),
    (("launch_enabled",), True, "launch_enabled"),
    (("launch_enabled",), 0, "launch_enabled"),
    (("execution_enabled",), True, "execution_enabled"),
    (("scope", "inference_concurrency"), 2, "scope"),
    (("scope", "inference_concurrency"), True, "scope"),
    (("scope", "max_generation_observations"), 21, "scope"),
    (("scope", "repeats_per_condition"), 3, "scope"),
    (("scope", "external_attempts_per_observation"), 2, "scope"),
    (("scope", "external_retry_allowed"), True, "scope"),
    (("scope", "external_replay_allowed"), True, "scope"),
    (("scope", "external_resume_allowed"), True, "scope"),
    (("scope", "pool_with_other_studies"), True, "scope"),
    (("generation_budget", "seconds_per_observation"), 10800, "generation_budget"),
    (("generation_budget", "seconds_per_observation"), 1200.0, "generation_budget"),
    (("generation_budget", "starts_at"), "each_native_turn", "generation_budget"),
    (("generation_budget", "includes"), [], "generation_budget"),
    (("generation_budget", "local_cleanup_grace_seconds"), 21, "generation_budget"),
    (("generation_budget", "max_planned_host_lifecycle_seconds"), 1240, "generation_budget"),
    (("generation_budget", "cleanup_grace_recorded_separately"), False, "generation_budget"),
    (("generation_budget", "remote_billing_bound"), True, "generation_budget"),
    (("generation_budget", "server_side_cancellation_guaranteed"), True, "generation_budget"),
    (("native_measurements", "policy"), "hard_cap", "native_measurements"),
    (("native_measurements", "unavailable"), 0, "native_measurements"),
    (("native_measurements", "shared_native_request_token_hard_caps"), True, "native_measurements"),
    (("native_measurements", "native_turn_equals_model_attempt"), True, "native_measurements"),
    (("native_measurements", "token_accounting"), "sum_snapshots", "native_measurements"),
    (("native_measurements", "cached_input_and_reasoning"), "add_to_totals", "native_measurements"),
    (("grading_policy", "attempts_per_resulting_observation"), 2, "grading_policy"),
    (("grading_policy", "failed_or_missing_outcomes"), "drop", "grading_policy"),
    (("grading_policy", "regrade_for_score"), True, "grading_policy"),
    (("decision_rule", "early_selection"), True, "decision_rule"),
    (("decision_rule", "score_dependent_repeats"), True, "decision_rule"),
    (("decision_rule", "precise_uncertainty_claim"), True, "decision_rule"),
    (("decision_rule", "equal_native_compute_claim"), True, "decision_rule"),
    (("source_basis", "source_profile", "sha256"), "0" * 64, "source_basis"),
    (("source_basis", "registration_compiler", "sha256"), "0" * 64, "source_basis"),
    (("shared", "cost", "approved_maximum_usd"), 100, "shared_facts"),
    (("shared", "dataset", "revision"), "wrong", "shared_facts"),
    (("shared", "dataset", "tasks", 0, "prompt_sha256"), "0" * 64, "shared_facts"),
    (("shared", "grading", "template_source_sha256"), "0" * 64, "shared_facts"),
    (("conditions", "sandbox_v2", "local_settings", "max_model_turns"), 10, "condition_settings"),
    (("conditions", "codex", "native_turn_is_v2_turn_equivalent"), True, "condition_settings"),
    (("conditions", "codex", "provider_retry_settings", "request_max_retries"), 2, "condition_settings"),
    (("runs", 0, "run_id"), "gpt54_v2_codex_v1_v2_r1", "repetition_matrix"),
    (("runs", 0, "task_count"), 6, "repetition_matrix"),
])
def test_time_budget_registration_rejects_changed_controls(path, value, reason):
    plan = prospective.load_registration()
    target = plan
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        prospective.compile_registration(plan)


@pytest.mark.parametrize("container,key,value,reason", [
    ((), "max_model_calls", 9, "manifest_fields"),
    ((), "implementation_status", {"executor_enforces_registered_policy": True}, "manifest_fields"),
    (("shared",), "limits", {"max_model_calls": 9}, "shared_facts"),
    (("native_measurements",), "max_model_calls", 9, "native_measurements"),
    (("native_measurements",), "max_input_tokens", 737280, "native_measurements"),
    (("native_measurements",), "max_output_tokens", 73728, "native_measurements"),
    (("native_measurements",), "max_written_tokens_per_turn", 8192, "native_measurements"),
    (("native_measurements",), "max_repeats_of_one_request", 2, "native_measurements"),
    (("conditions", "codex"), "local_settings", {"max_model_turns": 9}, "condition_settings"),
])
def test_time_budget_registration_rejects_unknown_hard_cap_claims(container, key, value, reason):
    plan = prospective.load_registration()
    target = plan
    for part in container:
        target = target[part]
    target[key] = value
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        prospective.compile_registration(plan)


@pytest.mark.parametrize("change,reason", [
    ("missing_field", "manifest_fields"), ("reordered_tasks", "shared_facts"),
    ("reordered_runs", "repetition_matrix"), ("extra_run", "repetition_matrix"),
])
def test_time_budget_registration_rejects_missing_or_changed_inventory(change, reason):
    plan = prospective.load_registration()
    if change == "missing_field":
        plan.pop("execution_enabled")
    elif change == "reordered_tasks":
        plan["shared"]["dataset"]["tasks"].reverse()
    elif change == "reordered_runs":
        plan["runs"].reverse()
    else:
        plan["runs"].append(dict(plan["runs"][0]))
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        prospective.compile_registration(plan)


@pytest.mark.parametrize("text,reason", [
    ("launch_enabled: true\nlaunch_enabled: false\n", "manifest_duplicate_or_nonstring_key"),
    ("scope:\n  concurrency: 2\n  concurrency: 1\n", "manifest_duplicate_or_nonstring_key"),
    ("scope: &scope {}\nother: *scope\n", "manifest_alias"),
    ("true: forbidden\n", "manifest_duplicate_or_nonstring_key"),
    ("[]\n", "manifest_not_object"),
    ("scope: [\n", "manifest_unreadable"),
    ("#" * (prospective.MAX_MANIFEST_BYTES + 1), "manifest_too_large"),
])
def test_time_budget_registration_strict_yaml(text, reason, tmp_path):
    path = tmp_path / "synthetic-registration.yaml"
    path.write_text(text)
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        prospective.load_registration(path)


@pytest.mark.parametrize("role,reason", [
    (prospective.SOURCE_PROFILE, "source_profile_bytes"),
    (prospective.COMPILER, "source_basis"),
    ("batch-runner/core/codex_runner.py", "source_contract_refused"),
])
def test_time_budget_registration_real_source_guard_rejects_drift(role, reason, monkeypatch):
    plan = prospective.load_registration()
    read_bytes = Path.read_bytes
    target = prospective.ROOT / role

    def drift(path):
        raw = read_bytes(path)
        return raw + b"\n# synthetic source drift\n" if path == target else raw

    monkeypatch.setattr(Path, "read_bytes", drift)
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$") as caught:
        prospective.compile_registration(plan)
    if reason == "source_contract_refused":
        assert isinstance(caught.value.__cause__, historical.DispatchPlanRefused)
        assert f"source_pin:{role}" in str(caught.value.__cause__)


def test_time_budget_registration_preserves_historical_and_default_refusals():
    assert hashlib.sha256(historical.PLAN.read_bytes()).hexdigest() == (
        "3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1"
    )
    profile_path = historical.ROOT / prospective.SOURCE_PROFILE
    assert hashlib.sha256(profile_path.read_bytes()).hexdigest() == prospective.SOURCE_PROFILE_SHA256
    report = historical.inspect_plan(historical.load_plan())
    assert report["configuration_valid"] is False
    assert report["configuration_problems"] == [
        f"source_pin:batch-runner/{name}" for name in (
            "gpt54_codex_input_capture.py", "gpt54_v2_input_capture.py",
            "gpt54_run_config_bundle.py", "gpt54_run_input_bundle.py",
            "gpt54_disposable_checkout.py", "gpt54_workflow_gate.py",
            "core/codex_runner.py", "step2_run_inference.py", "core/codex_task_deadline.py",
        )
    ]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert report["launch_blockers"] == list(historical.LAUNCH_BLOCKERS)
    with pytest.raises(historical.DispatchPlanRefused, match="comparison refused:"):
        historical.compile_dispatch_plan(historical.load_plan())
    local = historical.compile_dispatch_plan(historical.load_plan(profile_path)).as_dict()
    assert local["launch_allowed"] is False
    assert local["shared_controls"]["limits"] == {
        "max_model_turns": 9, "max_written_tokens_per_turn": 8192, "max_seconds": 1200.0,
        "max_model_calls": 9, "max_input_tokens": 737280, "max_output_tokens": 73728,
        "max_repeats_of_one_request": 2, "attempts_per_task": 1, "request_max_retries": 0,
        "stream_max_retries": 0, "self_review_max_attempts": 0, "resume_max_rounds": 0,
    }
    # Neither compiler silently interprets the other study's schema as its own.
    with pytest.raises(historical.DispatchPlanRefused, match="source_pin_set"):
        historical.compile_dispatch_plan(prospective.load_registration())
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match="^manifest_fields$"):
        prospective.compile_registration(historical.load_plan(profile_path))


def test_time_budget_registration_cli_refusal_has_no_launch_fallback(tmp_path, capsys):
    path = tmp_path / "synthetic-invalid.yaml"
    path.write_text("execution_enabled: true\n")
    assert prospective.main(["--manifest", str(path)]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "registration_valid": False, "reason": "manifest_fields", "compiled": None,
    }
