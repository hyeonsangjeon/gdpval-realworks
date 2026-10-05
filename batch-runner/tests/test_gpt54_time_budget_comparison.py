"""Offline registration evidence, not observations of private tasks or a model."""

import hashlib
import json
import io
import os
import signal
import socket
import subprocess
import tarfile
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt54_comparison_preflight as historical
import gpt54_time_budget_comparison as prospective
from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks
from gpt54_codex_input_capture import (
    ComparisonRuntimeLaunchRefused,
    require_comparison_runtime_launch,
)
from .test_gpt54_run_config_bundle import _guards

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen


@pytest.fixture(scope="module")
def dual_roots(tmp_path_factory):
    """Real local commit objects and source-only exports; never private inputs."""
    from .test_gpt54_disposable_checkout import _FIXTURE_ENV

    repository = Path(__file__).resolve().parents[2]
    environment = {**_FIXTURE_ENV, "GIT_ALLOW_PROTOCOL": "file"}

    def git(*command):
        return _REAL_RUN(["git", *command], check=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=environment, timeout=30).stdout

    runtime_sha = git("-C", str(repository), "rev-parse", "HEAD").decode().strip()
    roots = {}
    for role, sha in (("runtime", runtime_sha), ("frozen", prospective.ACCEPTED_BASE_SHA), ("substitute", runtime_sha)):
        root = tmp_path_factory.mktemp("deadline-" + role) / "source"
        git("clone", "--shared", "--no-checkout", "--", str(repository), str(root))
        archive = git("-C", str(repository), "archive", "--format=tar", sha, "batch-runner", ".github/workflows")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            assert source.pax_headers["comment"] == sha
            assert all(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                       and (member.isdir() or member.isfile()) for member in source.getmembers())
            source.extractall(root)
        git("-C", str(root), "update-ref", "--no-deref", "HEAD", sha)
        roots[role] = root
    substituted = roots["substitute"]
    role = "batch-runner/core/codex_runner.py"
    changed = (substituted / role).read_bytes() + b"\n# synthetic coherent replacement\n"
    (substituted / role).write_bytes(changed)
    manifest = prospective.load_registration(substituted / prospective.REGISTRATION_PATH)
    manifest["source_pins"][role] = hashlib.sha256(changed).hexdigest()
    (substituted / prospective.REGISTRATION_PATH).write_text(json.dumps(manifest, sort_keys=True))
    git("-C", str(substituted), "read-tree", runtime_sha)
    git("-C", str(substituted), "add", "--", role, prospective.REGISTRATION_PATH)
    git("-C", str(substituted), "commit", "-m", "test: coherent synthetic source substitution")
    replacement = git("-C", str(substituted), "rev-parse", "HEAD").decode().strip()
    git("-C", str(roots["runtime"]), "tag", "-a", "synthetic-review-tag", "-m", "synthetic tag", runtime_sha)
    tag = git("-C", str(roots["runtime"]), "rev-parse", "synthetic-review-tag").decode().strip()
    return {**roots, "runtime_sha": runtime_sha, "substitute_sha": replacement, "tag_sha": tag}


def _anchors(roots):
    return dict(runtime_root=roots["runtime"], expected_reviewed_source_sha=roots["runtime_sha"],
                frozen_grader_root=roots["frozen"], expected_grader_source_sha=prospective.ACCEPTED_BASE_SHA)


def _compile(plan, roots):
    return prospective.compile_registration(plan, **_anchors(roots))


@pytest.fixture(autouse=True)
def model_free(monkeypatch, request, dual_roots):
    deadline_case = "time_budget_observation_deadline" in request.node.name
    if deadline_case:
        calls = []
    else:
        calls = _guards(monkeypatch)

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("deadline contract attempted network/auth/private input/preparation")

    if deadline_case:
        from core import azure_ai_clients, codex_azure_token
        from openai_codex import Codex
        from openai_codex.client import CodexClient
        import step8_grade

        for owner, names in ((subprocess, ("run", "Popen", "check_call", "check_output")),
                             (socket.socket, ("connect", "connect_ex")),
                             (socket, ("create_connection",)), (os, ("system",)),
                             (codex_azure_token, ("acquire_token", "get_bearer_token_provider"))):
            for name in names:
                monkeypatch.setattr(owner, name, forbidden)
        for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                            azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                            Codex, CodexClient, step8_grade.Grader, step8_grade.RubricLoader):
            monkeypatch.setattr(constructor, "__init__", forbidden)

    def local_git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        position = command.index("-C")
        assert Path(command[position + 1]) in (dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"], historical.ROOT)
        assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert kwargs["timeout"] == 60
        with monkeypatch.context() as child:
            child.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", local_git)

    for name in (
        "gpt54_disposable_checkout.prepare_disposable_checkout",
        "gpt54_prepared_input_attestation._source_snapshot",
        "pandas.read_parquet",
    ):
        monkeypatch.setattr(name, forbidden)
    yield
    assert calls == []


def test_time_budget_registration_genuine_source_and_finite_scope(dual_roots):
    plan = prospective.load_registration()
    compiled = _compile(plan, dual_roots)
    report = compiled.as_dict()
    intent = report["registered_intent"]
    profile = historical.load_plan(historical.ROOT / prospective.SOURCE_PROFILE)
    # Genuine unchanged full-source validation, including the real template
    # closure, occurs inside compile_registration. No pin/helper is replaced.
    assert len(report["source_evidence"]["validated_source_pins"]) == 41
    assert report["source_evidence"]["validated_source_pins"] == plan["source_pins"]
    assert len(report["source_evidence"]["frozen_grader"]["source_files"]) == 37
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
    assert _compile(reordered, dual_roots).canonical_bytes() == compiled.canonical_bytes()
    with pytest.raises(FrozenInstanceError):
        compiled.runs[0].repeat = 3


def test_time_budget_registration_labels_intent_without_enforcement_or_launch(capsys, dual_roots):
    assert prospective.main([]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report == {"registration_valid": False, "reason": "manifest_fields", "compiled": None}
    document = _compile(prospective.load_registration(), dual_roots).as_dict()
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
        "registration_compiler": "implemented_offline", "generation_deadline": "opt_in_host_control",
        "cleanup_grace": "one_absolute_cleanup_deadline", "host_control_selected_by_executor": False,
        "native_measurement_availability": "not_verified",
        "executor_enforces_registered_policy": False,
        "dispatch_and_capture": "not_integrated_for_this_study", "observations_executed_by_compiler": 0,
    }
    assert document["launch_authority"] == {
        "launch_allowed": False, "execution_enabled": False, "full_220_allowed": False,
        "blockers": ["time_budget_dispatch_must_select_observation_control", *prospective.LAUNCH_BLOCKERS[1:]],
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
def test_time_budget_registration_rejects_changed_controls(path, value, reason, dual_roots):
    plan = prospective.load_registration()
    target = plan
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        _compile(plan, dual_roots)


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
def test_time_budget_registration_rejects_unknown_hard_cap_claims(container, key, value, reason, dual_roots):
    plan = prospective.load_registration()
    target = plan
    for part in container:
        target = target[part]
    target[key] = value
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        _compile(plan, dual_roots)


@pytest.mark.parametrize("change,reason", [
    ("missing_field", "manifest_fields"), ("reordered_tasks", "shared_facts"),
    ("reordered_runs", "repetition_matrix"), ("extra_run", "repetition_matrix"),
])
def test_time_budget_registration_rejects_missing_or_changed_inventory(change, reason, dual_roots):
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
        _compile(plan, dual_roots)


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
    (prospective.SOURCE_PROFILE, "source_differs_from_reviewed_blob"),
    (prospective.COMPILER, "source_differs_from_reviewed_blob"),
    ("batch-runner/core/codex_runner.py", "source_differs_from_reviewed_blob"),
])
def test_time_budget_registration_real_source_guard_rejects_drift(role, reason, dual_roots):
    plan = prospective.load_registration()
    root = dual_roots["frozen"] if role == prospective.SOURCE_PROFILE else dual_roots["runtime"]
    target = root / role
    before = target.read_bytes()
    try:
        target.write_bytes(before + b"\n# synthetic source drift\n")
        with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
            _compile(plan, dual_roots)
    finally:
        target.write_bytes(before)


def test_time_budget_registration_preserves_historical_and_default_refusals(monkeypatch, frozen_local_comparison_source):
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
            "core/agentic_v2_conversation_runner.py",
            "core/codex_runner.py", "step2_run_inference.py", "core/codex_task_deadline.py",
        )
    ]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert report["launch_blockers"] == list(historical.LAUNCH_BLOCKERS)
    with pytest.raises(historical.DispatchPlanRefused, match="comparison refused:"):
        historical.compile_dispatch_plan(historical.load_plan())
    with pytest.raises(historical.DispatchPlanRefused, match="source_pin:batch-runner/core/agentic_v2_conversation_runner.py"):
        historical.compile_dispatch_plan(historical.load_plan(profile_path))
    with monkeypatch.context() as frozen:
        frozen.setattr(historical, "ROOT", frozen_local_comparison_source)
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


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _observation(tmp_path, condition="codex", *, clock=None, task_index=0):
    from core.time_budget_observation_deadline import ObservationIdentity, STUDY_ID, TASK_IDS, TimeBudgetObservation

    clock = _Clock() if clock is None else clock
    store = tmp_path / "host-observations"
    store.mkdir(mode=0o700, exist_ok=True)
    identity = ObservationIdentity(
        STUDY_ID, f"gpt54_time_budget_v1_{'v2' if condition == 'sandbox_v2' else 'codex'}_r1",
        condition, 1, TASK_IDS[task_index], "1" * 40, "2" * 40,
        hashlib.sha256(b"synthetic registration").hexdigest(), hashlib.sha256(b"synthetic input").hexdigest(),
    )
    return TimeBudgetObservation(store, identity, clock=clock), clock


def _claim(control):
    control.claim(run_id=control.identity.run_id, condition=control.identity.condition,
                  task_id=control.identity.task_id)


@pytest.mark.parametrize("phase", ["admitted", "started", "terminal", "abandoned"])
def test_time_budget_observation_deadline_nonrenewable_admission(tmp_path, phase):
    from dataclasses import replace
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TimeBudgetObservation

    control, clock = _observation(tmp_path)
    assert control.first_start is None
    assert (control.directory / (control.identity.key + ".admitted.json")).is_file()
    clock.advance(5000)  # Preparation is not generation.
    if phase != "admitted":
        _claim(control)
        with control.supervise():
            control.start()
            assert control.first_start == clock.now
            if phase == "terminal":
                control.terminal("completed")
        if phase == "terminal":
            control.finish_cleanup(True)
            assert control.cleanup_complete
    # Neither a new runner/control nor changed bindings mint a retry.
    for identity in (control.identity, replace(control.identity, reviewed_source_sha="3" * 40),
                     replace(control.identity, input_sha256="4" * 64)):
        with pytest.raises(ObservationDeadlineRefused):
            TimeBudgetObservation(control.directory, identity, clock=clock)
    if phase != "terminal":
        with pytest.raises(ObservationDeadlineRefused):
            _observation(tmp_path, clock=clock, task_index=1)
    else:
        other, _ = _observation(tmp_path, clock=clock, task_index=1)
        assert other.first_start is None


@pytest.mark.parametrize("terminal", ["completed", "timeout"])
def test_time_budget_observation_deadline_one_cleanup_remainder(tmp_path, terminal, monkeypatch):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, ObservationTimedOut, TIMEOUT

    monkeypatch.setenv("CODEX_INTERRUPT_GRACE", "999999")
    monkeypatch.setenv("CODEX_TURN_TIMEOUT", "999999")
    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
        first = control.first_start
        clock.advance(1200 if terminal == "timeout" else 4)
        if terminal == "timeout":
            with pytest.raises(ObservationTimedOut):
                control.check_generation()
            assert control.terminal_reason == TIMEOUT
            assert control.cleanup_deadline == first + 1220
        else:
            control.terminal("completed")
            assert control.cleanup_deadline == first + 24
    events = []
    for stage, elapsed in (("interrupt", 8), ("join", 7), ("close", 4), ("remove", 2)):
        before = control.remaining_cleanup()

        def operation():
            events.append((stage, before))
            clock.advance(elapsed)
            return stage == "interrupt" or None

        assert control.cleanup(operation, interruption=stage == "interrupt") is (stage != "remove")
    assert [remaining for _, remaining in events] == [20, 12, 5, 1]
    assert control.cleanup(lambda: pytest.fail("expired cleanup restarted")) is False
    control.finish_cleanup(True)
    record = json.loads((control.directory / (control.identity.key + ".cleanup.json")).read_bytes())
    assert record["cleanup_expired"] is True and record["host_reusable"] is False
    assert record["interruption_attempted"] is record["interruption_acknowledged"] is True
    assert record["remote_cancellation_confirmed"] is record["remote_billing_bound"] is False
    with pytest.raises(ObservationDeadlineRefused):
        _observation(tmp_path, clock=clock, task_index=1)


def test_time_budget_observation_deadline_interrupt_latch_and_owned_group(tmp_path, monkeypatch):
    from core.time_budget_observation_deadline import ObservationTimedOut, TIMEOUT

    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
        clock.advance(1200)
        with pytest.raises(ObservationTimedOut):
            signal.raise_signal(signal.SIGALRM)  # Deliver the active owned-host alarm, no wall-clock wait.
    assert control.terminal_reason == TIMEOUT
    assert json.loads((control.directory / (control.identity.key + ".terminal.json")).read_bytes())["reason"] == TIMEOUT
    control.terminal("completed")  # A late result cannot replace the timeout latch.
    assert control.terminal_reason == TIMEOUT
    owned = {424242: (424242, "17", "S"), 424243: (os.getpgrp(), "18", "S")}
    control._before_processes = {}
    sent = []
    monkeypatch.setattr(control, "_descendants", lambda: dict(owned))
    monkeypatch.setattr(control, "_process", lambda pid: owned.get(pid))

    def kill(target, sig):
        sent.append((target, sig))
        assert target != os.getpgrp()
        if sig == signal.SIGKILL:
            owned.pop(target, None)

    monkeypatch.setattr(os, "kill", kill)
    monkeypatch.setattr(os, "killpg", kill)
    assert control.stop_owned_processes()
    assert sent == [(424242, signal.SIGTERM), (424243, signal.SIGTERM),
                    (424242, signal.SIGKILL), (424243, signal.SIGKILL)]
    control.finish_cleanup(True)
    assert control.cleanup_complete and not owned


@pytest.mark.parametrize("case", ["claimed_elsewhere", "timer_in_use", "backwards_clock", "lease_replaced"])
def test_time_budget_observation_deadline_refuses_unsafe_host_state(tmp_path, monkeypatch, case):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused

    control, clock = _observation(tmp_path)
    if case == "timer_in_use":
        monkeypatch.setattr(signal, "getitimer", lambda timer: (1.0, 0.0))
        with pytest.raises(ObservationDeadlineRefused, match="owned_host_supervision_required"):
            _claim(control)
        assert control.first_start is None
    elif case == "claimed_elsewhere":
        (control.directory / (control.identity.key + ".claimed.json")).write_text("{}")
        with pytest.raises(ObservationDeadlineRefused):
            _claim(control)
        assert control.first_start is None
    elif case == "backwards_clock":
        _claim(control)
        clock.advance(-1)
        with pytest.raises(ObservationDeadlineRefused, match="monotonic_clock_refused"):
            with control.supervise():
                control.start()
    else:
        _claim(control)
        control.terminal("abandoned")
        (control.directory / "host-lease.json").write_text("{}")
        with pytest.raises(ObservationDeadlineRefused):
            control.finish_cleanup(True)
        assert not (control.directory / (control.identity.key + ".cleanup.json")).exists()
    assert (control.directory / "host-lease.json").exists()


def test_time_budget_observation_deadline_unconfirmed_cleanup_cannot_release_host(tmp_path):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TIMEOUT

    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
        clock.advance(1200)
        control.terminal(TIMEOUT)
    assert control.cleanup(lambda: clock.advance(0.6), interruption=True, step_seconds=0.5) is False
    assert 19 < control.remaining_cleanup() < 20
    assert control.stop_owned_processes()  # Still use the remainder to remove owned workers.
    control.finish_cleanup(True)
    assert control.interruption_attempted and not control.interruption_acknowledged
    assert not control.cleanup_complete and not control.cleanup_expired
    with pytest.raises(ObservationDeadlineRefused):
        _observation(tmp_path, clock=clock, task_index=1)


def test_time_budget_observation_deadline_timeout_receipt_failure_still_interrupts(tmp_path, monkeypatch):
    from core.time_budget_observation_deadline import ObservationTimedOut, TIMEOUT

    control, clock = _observation(tmp_path)
    _claim(control)
    write = control._write

    def fail_terminal(name, value):
        if name.endswith(".terminal.json"):
            raise OSError("synthetic durable-record failure")
        return write(name, value)

    with control.supervise():
        control.start()
        monkeypatch.setattr(control, "_write", fail_terminal)
        clock.advance(1200)
        with pytest.raises(ObservationTimedOut):
            signal.raise_signal(signal.SIGALRM)
    assert control.terminal_reason == TIMEOUT and control.interruption_attempted
    assert control.cleanup_failed
    control.finish_cleanup(True)
    assert not control.cleanup_complete and (control.directory / "host-lease.json").exists()


@pytest.mark.parametrize("case", ["success", "late_success", "tool_wait", "blocking_responses"])
def test_time_budget_observation_deadline_v2_actual_factory(tmp_path, monkeypatch, case):
    from core.agentic_v2_conversation import AskForTool, StopReason
    from core.agentic_v2_conversation_runner import PerTaskCeilings, TaskConversations, build_runner_factory
    from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
    from core.agentic_v2_model_voice import AzureFoundryVoice
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TIMEOUT
    from .test_agentic_v2_conversation_runner import PROFILE

    control, clock = _observation(tmp_path, "sandbox_v2")
    held = TaskConversations(PerTaskCeilings(9, 8192, 1200.0, 9, 737280, 73728, 2))
    calls, reservations = [], []
    clock.advance(2000)

    class Backend(AgenticV2FixtureBackend):
        def start(self, timeout):
            assert control.first_start is None
            clock.advance(500)
            return super().start(timeout)

        def workspace_apply(self, arguments):
            clock.advance(800 if case == "tool_wait" else 100)
            return super().workspace_apply(arguments)

        def close(self):
            clock.advance(1)
            super().close()

    def close_client():
        calls.append("client_close")
        clock.advance(1)

    class Voice:
        makes_paid_calls = False
        client = SimpleNamespace(close=close_client)

        def next_turn(self, request):
            assert reservations[-1] == request.turn
            assert control.first_start == 2600
            calls.append(request.turn)
            clock.advance(400 if request.turn == 1 else 701 if case == "late_success" else 200)
            if request.turn == 1:
                return AskForTool("write", "workspace_apply", {"operation": "write", "path": "report.txt", "content": "synthetic"},
                                  input_tokens=20, output_tokens=10)
            return AskForTool("finalize", "finalize", {"deliverables": ["report.txt"], "summary": "synthetic"},
                              input_tokens=30, output_tokens=15)

    def voice_for(budget):
        if case != "blocking_responses":
            return Voice()

        def create(**payload):
            assert reservations == [1] and control.first_start == 2600
            assert payload["max_output_tokens"] == 8192
            calls.append("responses.create")
            clock.advance(1200)
            signal.raise_signal(signal.SIGALRM)
            pytest.fail("blocking generation was not interrupted")

        # The real next_turn/Responses.create path, but a controlled in-memory
        # transport. No Azure client, endpoint, credential or model is created.
        return AzureFoundryVoice(
            client=SimpleNamespace(responses=SimpleNamespace(create=create), close=close_client),
            deployment="gpt-5.4", resource="synthetic", budget=budget, instructions="synthetic",
            max_output_tokens_per_turn=8192, replay_format="faithful", reasoning_effort="xhigh",
        )

    def reserve(turn):
        assert control._claimed and (control.directory / (control.identity.key + ".admitted.json")).is_file()
        if turn == 1:
            assert control.first_start is None
        reservations.append(turn)

    factory = build_runner_factory(
        backend_factory=lambda **kwargs: Backend(root=tmp_path / "backend", **kwargs),
        profile=PROFILE, conversations=held, attempt_of=lambda task: 1, voice_for=voice_for,
        before_model_call_for=lambda task, attempt: reserve, observation_for=lambda task, attempt: control,
    )
    runner = factory(SimpleNamespace(task_id=control.identity.task_id))
    result = runner.run("synthetic", run_id=control.identity.run_id,
                        condition_name="sandbox_v2", task_id=control.identity.task_id)
    assert result["success"] is (case == "success")
    outcome = held.outcome_of(control.identity.task_id, 1)
    if case != "success":
        assert outcome.stop_reason is StopReason.TIME_LIMIT_REACHED
        assert control.terminal_reason == TIMEOUT and result["error"] == "task_wall_time_exhausted"
        assert len(outcome.turns) == (0 if case == "blocking_responses" else 2 if case == "late_success" else 1)
    assert runner.last_observation_deadline["cleanup_complete"] is True
    assert control.first_start == 2600
    assert not (control.directory / "host-lease.json").exists()
    before = list(calls)
    with pytest.raises(ObservationDeadlineRefused):
        runner.run("no restart", run_id=control.identity.run_id, condition_name="sandbox_v2", task_id=control.identity.task_id)
    with pytest.raises(ObservationDeadlineRefused):
        factory(SimpleNamespace(task_id=control.identity.task_id))
    assert calls == before


@pytest.mark.parametrize("case", ["success", "creation_timeout", "native_recovery", "late_success", "cleanup_expired"])
def test_time_budget_observation_deadline_codex_actual_entry(tmp_path, monkeypatch, case):
    import core.codex_runner as native
    from core.codex_runtime_config import LoopbackCodexProvider
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TIMEOUT, CLEANUP_UNCONFIRMED
    from openai_codex.generated.v2_all import TurnInterruptResponse

    control, clock = _observation(tmp_path)
    events = []

    class Process:
        alive = True

        def poll(self):
            return None if self.alive else 0

        def kill(self):
            events.append("kill_owned_process")
            self.alive = False

        def wait(self, timeout):
            assert 0 < timeout <= min(1, control.remaining_cleanup())
            events.append("bounded_wait")
            clock.advance(0.25)
            return 0

    process = Process()

    def cleanup():
        events.append("remove")
        clock.advance(20 if case == "cleanup_expired" else 1)

    def collect():
        events.append("collect")
        assert not process.alive
        clock.advance(1)
        return []

    workspace = SimpleNamespace(stage_references=lambda refs: events.append("stage_synthetic"), cleanup=cleanup,
                                collect_deliverables=collect)
    monkeypatch.setattr(native.CodexWorkspace, "create", lambda **kwargs: workspace)
    usage = SimpleNamespace(total=SimpleNamespace(input_tokens=100, cached_input_tokens=20,
                            output_tokens=40, reasoning_output_tokens=10, cache_write_input_tokens=None))

    class Turn:
        id = "synthetic-turn"

        def stream(self):
            yield SimpleNamespace(method="thread/tokenUsage/updated", payload=SimpleNamespace(token_usage=usage))
            for _ in range(3):
                clock.advance(300 if case == "native_recovery" else 10)
                yield SimpleNamespace(method="item/completed", payload=None)
            if case == "native_recovery":
                clock.advance(100)  # 200 creation + 900 recovery + 100 final wait == 1200.
                signal.raise_signal(signal.SIGALRM)
            if case == "late_success":
                clock.advance(971)

        def interrupt(self):
            events.append("interrupt")
            assert control.terminal_reason == TIMEOUT
            assert (control.directory / (control.identity.key + ".terminal.json")).is_file()
            clock.advance(0.25)
            return TurnInterruptResponse()

    def turn(text):
        events.append("turn_create")
        assert control.first_start == 2600 and control._claimed
        clock.advance(1200 if case == "creation_timeout" else 200)
        if case == "creation_timeout":
            signal.raise_signal(signal.SIGALRM)
            pytest.fail("turn creation survived the observation deadline")
        return Turn()

    def collector(stream, turn_id):
        list(stream)
        return SimpleNamespace(id=turn_id, usage=usage, final_response="synthetic success")

    monkeypatch.setattr(native, "_load_turn_collector", lambda: collector)
    runner = native.CodexAgentRunner(LoopbackCodexProvider(1, model="gpt-5.4"), verify_runtime=False, preflight_auth=False,
                                   run_id=control.identity.run_id, condition_name="codex", observation_control=control)
    monkeypatch.setattr(runner, "build_task_text", lambda *args, **kwargs: "synthetic")

    def open_runtime(*args, **kwargs):
        assert control.first_start is None
        clock.advance(2000)
        return SimpleNamespace(_client=SimpleNamespace(_proc=process), close=lambda: events.append("close_sdk"))

    def start_thread(*args, **kwargs):
        assert control.first_start is None
        clock.advance(500)
        return SimpleNamespace(id="synthetic-thread", turn=turn)

    monkeypatch.setattr(runner, "open_runtime", open_runtime)
    monkeypatch.setattr(runner, "start_thread", start_thread)
    monkeypatch.setattr(native, "CODEX_INTERRUPT_GRACE_SECONDS", 999999)
    result = runner.run("synthetic", task_id=control.identity.task_id)
    assert control.first_start == 2600 and events.count("turn_create") == 1
    assert result["success"] is (case == "success")
    if case in ("creation_timeout", "native_recovery", "late_success"):
        assert result["error_category"] == TIMEOUT and control.terminal_reason == TIMEOUT
        assert control.cleanup_deadline == 3820
    elif case == "cleanup_expired":
        assert result["error_category"] == CLEANUP_UNCONFIRMED
        assert result["time_budget_observation"]["host_reusable"] is False
    assert events.index("kill_owned_process") < events.index("close_sdk") < events.index("collect") < events.index("remove")
    if case == "native_recovery":
        measured = runner.last_run_diagnostics["usage_delta"]
        assert measured["input_tokens"] == 100 and measured["cached_input_tokens"] == 20
        assert measured["output_tokens"] == 40 and measured["reasoning_output_tokens"] == 10
        assert control.interruption_acknowledged is True  # app-server acknowledgement only
    if case == "creation_timeout":
        assert runner.last_run_diagnostics["usage_delta"]["input_tokens"] is None
        assert control.interruption_attempted and not control.interruption_acknowledged
    before = list(events)
    with pytest.raises(ObservationDeadlineRefused):
        runner.run("no external retry", task_id=control.identity.task_id)
    with pytest.raises(ObservationDeadlineRefused):
        native.CodexAgentRunner(LoopbackCodexProvider(1), verify_runtime=False, preflight_auth=False,
                               run_id=control.identity.run_id, condition_name="codex", observation_control=control)
    assert events == before


def test_time_budget_observation_deadline_omission_preserves_legacy_paths(tmp_path, monkeypatch):
    from core.agentic_v2_conversation import ScriptedVoice
    from core.agentic_v2_conversation_runner import TaskConversations, build_runner_factory
    from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
    from .test_agentic_v2_conversation_runner import PROFILE, CEILINGS, _write, _finalize
    from core.codex_runner import CodexAgentRunner
    from core.codex_runtime_config import LoopbackCodexProvider
    import core.codex_runner as native

    held = TaskConversations(CEILINGS)
    factory = build_runner_factory(backend_factory=lambda **kw: AgenticV2FixtureBackend(root=tmp_path / "old-v2", **kw),
                                   profile=PROFILE, conversations=held, attempt_of=lambda task: 1,
                                   voice=ScriptedVoice([_write(), _finalize()]))
    runner = factory(SimpleNamespace(task_id="legacy-task"))
    assert runner.run("synthetic", task_id="legacy-task")["success"] is True
    assert runner.last_observation_deadline is None and not (tmp_path / "host-observations").exists()
    monkeypatch.setattr(native, "_load_turn_collector", lambda: None)
    native_runner = CodexAgentRunner(LoopbackCodexProvider(1), verify_runtime=False, preflight_auth=False, timeout=7)
    result = SimpleNamespace(final_response="synthetic")
    observed = native_runner._await_turn(SimpleNamespace(run=lambda: result))
    assert observed.result is result and not observed.timed_out
    assert native_runner.observation_control is native_runner.last_observation_deadline is None


def test_time_budget_frozen_judge_binding_genuine_dual_roots(dual_roots, tmp_path):
    from step8_grade import compute_grader_source_hash

    plan = prospective.load_registration()
    report = _compile(plan, dual_roots).as_dict()
    evidence = report["source_evidence"]
    assert evidence["runtime"]["source_sha"] == dual_roots["runtime_sha"]
    assert evidence["frozen_grader"]["source_sha"] == prospective.ACCEPTED_BASE_SHA
    assert evidence["frozen_grader"]["source_tree"] == prospective.ACCEPTED_BASE_TREE
    assert evidence["frozen_grader"]["template_source_sha256"] == prospective.FROZEN_TEMPLATE_SHA256
    assert evidence["frozen_grader"]["materialized_grader_source_sha256"] is None
    assert evidence["frozen_grader"]["materialized_config_path"] is None
    assert report["launch_authority"]["launch_allowed"] is report["launch_authority"]["execution_enabled"] is False
    assert report["implementation_status"]["host_control_selected_by_executor"] is False
    assert report["registered_intent"]["scope"]["max_generation_observations"] == 20
    assert report["registered_intent"]["generation_budget"]["seconds_per_observation"] == 1200
    runtime, frozen = dual_roots["runtime"], dual_roots["frozen"]
    assert compute_grader_source_hash(runtime / historical.GRADER, historical.load_plan(runtime / historical.GRADER),
                                      batch_root=runtime / "batch-runner") != prospective.FROZEN_TEMPLATE_SHA256
    config = historical.load_plan(frozen / historical.GRADER)
    # A test-owned materialized config has its actual new path AND new bytes in
    # the unchanged whole-closure algorithm. Nothing executes this grader.
    materialized = frozen / "batch-runner" / "synthetic-materialized-grader.json"
    config["rubric"]["revision"] = plan["shared"]["dataset"]["revision"]
    try:
        materialized.write_text(json.dumps(config, sort_keys=True))
        actual = compute_grader_source_hash(materialized, config, batch_root=frozen / "batch-runner")
        assert actual != prospective.FROZEN_TEMPLATE_SHA256
    finally:
        materialized.unlink()
    with pytest.raises(ComparisonRuntimeLaunchRefused, match="^comparison_runtime_launch_refused$"):
        require_comparison_runtime_launch()


@pytest.mark.parametrize("case", ["missing_runtime", "missing_judge", "wrong_runtime", "ref", "short", "uppercase", "tag",
                                  "wrong_judge", "swapped_roots", "same_root", "wrong_template", "coherent_substitution"])
def test_time_budget_frozen_judge_binding_anchor_refusals(dual_roots, case):
    plan, anchors = prospective.load_registration(), _anchors(dual_roots)
    if case == "missing_runtime":
        anchors["expected_reviewed_source_sha"] = None
    elif case == "missing_judge":
        anchors["expected_grader_source_sha"] = None
    elif case == "wrong_runtime":
        anchors["expected_reviewed_source_sha"] = prospective.ACCEPTED_BASE_SHA
    elif case in ("ref", "short", "uppercase"):
        anchors["expected_reviewed_source_sha"] = {"ref": "HEAD", "short": dual_roots["runtime_sha"][:8],
                                                    "uppercase": dual_roots["runtime_sha"].upper()}[case]
    elif case == "wrong_judge":
        anchors["expected_grader_source_sha"] = dual_roots["runtime_sha"]
    elif case == "tag":
        anchors["expected_reviewed_source_sha"] = dual_roots["tag_sha"]
    elif case == "coherent_substitution":
        anchors["runtime_root"] = dual_roots["substitute"]
        plan = prospective.load_registration(dual_roots["substitute"] / prospective.REGISTRATION_PATH)
        assert dual_roots["substitute_sha"] != anchors["expected_reviewed_source_sha"]
    elif case == "swapped_roots":
        anchors["runtime_root"], anchors["frozen_grader_root"] = anchors["frozen_grader_root"], anchors["runtime_root"]
    elif case == "same_root":
        anchors["frozen_grader_root"] = anchors["runtime_root"]
    else:
        plan["shared"]["grading"]["template_source_sha256"] = "0" * 64
    with pytest.raises(prospective.TimeBudgetRegistrationRefused):
        prospective.compile_registration(plan, **anchors)


@pytest.mark.parametrize("case", ["runtime_core", "frozen_core", "manifest", "untracked_core", "symlink",
                                  "hardlink", "compiler_digest", "held_parent", "final_reread", "head_substitution"])
def test_time_budget_frozen_judge_binding_tracked_bytes_and_races(dual_roots, tmp_path, monkeypatch, case):
    import gpt54_run_config_bundle as bundle

    plan = prospective.load_registration()
    root = dual_roots["frozen"] if case == "frozen_core" else dual_roots["runtime"]
    role = historical.GRADER if case == "symlink" else "batch-runner/core/codex_runner.py"
    if case == "manifest":
        role = prospective.REGISTRATION_PATH
    target = root / role
    original = target.read_bytes()
    extras = []
    moved = None
    try:
        if case in ("runtime_core", "frozen_core", "manifest"):
            target.write_bytes(original + b"\n# synthetic substitution\n")
        elif case == "untracked_core":
            path = root / "batch-runner/core/untracked_deadline.py"
            path.write_text("# untracked source\n")
            extras.append(path)
        elif case == "symlink":
            outside = tmp_path / "external.yaml"
            outside.write_bytes(original)
            target.unlink()
            target.symlink_to(outside)
        elif case == "hardlink":
            extra = tmp_path / "linked-runtime.py"
            os.link(target, extra)
            extras.append(extra)
        elif case == "compiler_digest":
            plan["source_pins"][prospective.COMPILER] = "0" * 64
        elif case == "head_substitution":
            # A coherent other HEAD has no authority to substitute for the
            # independently supplied R. The new value is a real local commit.
            head = root / ".git/HEAD"
            original_head = head.read_bytes()
            head.write_text(prospective.ACCEPTED_BASE_SHA + "\n")
        else:
            sources = bundle._sources

            def raced(selected, manifest, locator):
                nonlocal moved
                evidence = sources(selected, manifest, locator)
                if selected == root:
                    if case == "held_parent":
                        parent = root / "batch-runner/core"
                        moved = parent.with_name("held-original-core")
                        parent.rename(moved)
                        parent.mkdir()
                    else:
                        target.write_bytes(original + b"\n# final read race\n")
                return evidence

            monkeypatch.setattr(bundle, "_sources", raced)
        with pytest.raises(prospective.TimeBudgetRegistrationRefused):
            _compile(plan, dual_roots)
    finally:
        if moved is not None:
            (root / "batch-runner/core").rmdir()
            moved.rename(root / "batch-runner/core")
        if case == "symlink":
            target.unlink()
        for extra in extras:
            extra.unlink()
        target.write_bytes(original)
        if case == "head_substitution":
            head.write_bytes(original_head)


def test_time_budget_legacy_role_compatibility_frozen_profile(monkeypatch, frozen_local_comparison_source):
    test_time_budget_registration_preserves_historical_and_default_refusals(monkeypatch, frozen_local_comparison_source)


def test_time_budget_legacy_role_compatibility_closed_retention(historical_retention_source):
    import codex_retention_diagnostic as closed

    plan = closed.compile_plan()
    assert closed.ROOT == historical_retention_source
    assert plan["grading"]["template_source_sha256"] == prospective.FROZEN_TEMPLATE_SHA256
    assert plan["cell_count"] == 8 and plan["launch_authorized"] is False
    assert plan["common"]["cumulative_seconds"] == 10800


def test_time_budget_legacy_role_compatibility_shared_retained_source(tmp_path, historical_retention_source):
    from .test_codex_retention_task4_fresh_r1 import _source_tree, REAL_ROOT
    from .test_codex_retention_budget_report import FROZEN_SOURCE, CURRENT_SOURCE
    from step8_grade import compute_grader_source_hash

    root = tmp_path / "synthetic-retained-source"
    _source_tree(root)  # Shared by the old fresh/keep fixture family, not a live preparation.
    template = root / historical.GRADER
    template.parent.mkdir(parents=True)
    with template.open("xb") as target:
        target.write((historical_retention_source / historical.GRADER).read_bytes())
    for name in (historical_retention_source / "batch-runner/core").rglob("*.py"):
        assert (root / name.relative_to(historical_retention_source)).read_bytes() == name.read_bytes()
    assert compute_grader_source_hash(root / historical.GRADER, historical.load_plan(root / historical.GRADER),
                                      batch_root=root / "batch-runner") == prospective.FROZEN_TEMPLATE_SHA256
    for role, digest in FROZEN_SOURCE.items():
        assert hashlib.sha256((historical_retention_source / role).read_bytes()).hexdigest() == digest
    for role, digest in CURRENT_SOURCE.items():
        assert hashlib.sha256((REAL_ROOT / role).read_bytes()).hexdigest() == digest


def test_time_budget_legacy_role_compatibility_workflow_profile(monkeypatch, frozen_local_comparison_source):
    from .test_gpt54_workflow_gate import test_workflow_profile_anchor_current_source_and_frozen_refusals

    test_workflow_profile_anchor_current_source_and_frozen_refusals(monkeypatch, frozen_local_comparison_source)


def test_time_budget_legacy_role_compatibility_disposable_profile(monkeypatch, capsys, frozen_local_comparison_source):
    from .test_gpt54_disposable_checkout import test_prospective_source_profile_real_tracked_compilation_and_refusals

    test_prospective_source_profile_real_tracked_compilation_and_refusals(monkeypatch, capsys, frozen_local_comparison_source)
