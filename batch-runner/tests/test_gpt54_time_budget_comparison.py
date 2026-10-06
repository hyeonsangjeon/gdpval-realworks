"""Offline registration evidence, not observations of private tasks or a model."""

import hashlib
import json
import io
import os
import signal
import socket
import subprocess
import sys
import tarfile
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt54_comparison_preflight as historical
import gpt54_time_budget_comparison as prospective
from core.codex_runner import CodexAgentRunner as _REAL_CODEX_RUNNER
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend as _FIXTURE_BACKEND
from core.execution_envelope_tasks import load_task_catalog, select_advance_check_tasks
from gpt54_codex_input_capture import (
    ComparisonRuntimeLaunchRefused,
    require_comparison_runtime_launch,
)
from .test_gpt54_run_config_bundle import _guards
from . import test_codex_retention_task4_fresh_r1 as retained_fixture
from . import test_codex_retention_budget_report as retention_report

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
_FIXTURE_BACKEND_INIT = _FIXTURE_BACKEND.__init__


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
    gitdirs = {}
    for role, sha in (("runtime", runtime_sha), ("frozen", prospective.ACCEPTED_BASE_SHA), ("substitute", runtime_sha)):
        parent = tmp_path_factory.mktemp("deadline-" + role)
        root, owner = parent / "source", parent / "source-objects"
        git("clone", "--shared", "--no-checkout", "--", str(repository), str(owner))
        git("-C", str(owner), "worktree", "add", "--detach", "--no-checkout", str(root), sha)
        archive = git("-C", str(repository), "archive", "--format=tar", sha, "batch-runner", ".github/workflows")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            assert source.pax_headers["comment"] == sha
            assert all(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                       and (member.isdir() or member.isfile()) for member in source.getmembers())
            source.extractall(root)
        roots[role] = root
        gitdirs[role] = Path(git("-C", str(root), "rev-parse", "--absolute-git-dir").decode().strip())
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
    return {**roots, "gitdirs": gitdirs, "runtime_sha": runtime_sha, "substitute_sha": replacement, "tag_sha": tag}


def _anchors(roots):
    return dict(runtime_root=roots["runtime"], expected_reviewed_source_sha=roots["runtime_sha"],
                frozen_grader_root=roots["frozen"], expected_grader_source_sha=prospective.ACCEPTED_BASE_SHA)


def _compile(plan, roots):
    return prospective.compile_registration(plan, **_anchors(roots))


@pytest.fixture(autouse=True)
def model_free(monkeypatch, request, dual_roots):
    consumer_case = "time_budget_handoff_consumer" in request.node.name
    handoff_case = "time_budget_observation_handoff" in request.node.name or consumer_case
    handoff = request.getfixturevalue("handoff_source_seed") if handoff_case else None
    deadline_case = "time_budget_observation_deadline" in request.node.name
    if deadline_case:
        # Exercise the ownership checks through a deterministic kernel adapter.
        # Never change the pytest host's subreaper state or signal its children.
        request.getfixturevalue("observation_kernel")
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
        permitted = [dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"], historical.ROOT]
        if handoff is not None:
            permitted.extend((handoff.runtime, handoff.frozen))
        assert Path(command[position + 1]) in permitted
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
    if handoff_case and not consumer_case:
        from core.time_budget_observation_deadline import TimeBudgetObservation

        monkeypatch.setattr(TimeBudgetObservation, "__init__", forbidden)
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
    assert len(report["source_evidence"]["validated_source_pins"]) == 42
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
            "gpt54_prepared_input_attestation.py",
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


class _ObservationKernel:
    """Controlled Linux child/subreaper/pidfd semantics, with no real signals."""

    def __init__(self, monkeypatch):
        import core.time_budget_observation_deadline as deadline

        self.host = os.getpid()
        self.subreaper = 0
        self.one_thread = True
        self.processes = {}
        self.handles = {}
        self.signals = []
        self.reaped = []
        self.next_pid = 424242
        self.on_signal = None
        self.on_blocking_wait = None
        self.candidates = None
        monkeypatch.setattr(deadline, "_child_subreaper", self.prctl)
        monkeypatch.setattr(deadline.TimeBudgetObservation, "_process_owner", None)
        monkeypatch.setattr(deadline.TimeBudgetObservation, "_subreaper_host", None)
        monkeypatch.setattr(deadline.TimeBudgetObservation, "_released_hosts", {})
        monkeypatch.setattr(deadline.TimeBudgetObservation, "_single_threaded", staticmethod(lambda: self.one_thread))
        monkeypatch.setattr(deadline.TimeBudgetObservation, "_child_pids", staticmethod(self.child_pids))
        monkeypatch.setattr(os, "pidfd_open", self.pidfd_open, raising=False)
        monkeypatch.setattr(signal, "pidfd_send_signal", self.send_signal, raising=False)
        monkeypatch.setattr(os, "waitid", self.waitid)

    def prctl(self, enable=None):
        if enable is not None:
            self.subreaper = int(enable)
        return self.subreaper

    def spawn(self, parent=None, *, pid=None):
        pid = self.next_pid if pid is None else pid
        self.next_pid = max(self.next_pid, pid + 1)
        child = SimpleNamespace(pid=pid, parent=self.host if parent is None else parent, alive=True)
        self.processes[pid] = child
        return child

    def exit(self, child):
        child.alive = False
        for descendant in self.processes.values():
            if descendant.parent == child.pid:
                descendant.parent = self.host if self.subreaper else 1

    def child_pids(self):
        if self.candidates is not None:
            return set(self.candidates)
        return {child.pid for child in self.processes.values() if child.parent == self.host}

    def pidfd_open(self, pid):
        child = None if pid == self.host else self.processes.get(pid)
        if pid != self.host and child is None:
            raise ProcessLookupError
        # An actual local fd keeps close() real; the mapping pins the object,
        # not its replaceable PID, just as the kernel pidfd does.
        handle = os.open(os.devnull, os.O_RDONLY)
        self.handles[handle] = child
        return handle

    def send_signal(self, handle, sig):
        child = self.handles[handle]
        if sig == 0:
            assert child is None
            return
        assert child is not None and child.parent == self.host
        self.signals.append((child.pid, sig))
        if self.on_signal is not None:
            self.on_signal(child, sig)
        if sig == signal.SIGKILL:
            self.exit(child)

    def waitid(self, kind, target, options):
        from core.time_budget_observation_deadline import _WAIT_ALL_CHILDREN

        assert options & _WAIT_ALL_CHILDREN and options & os.WEXITED
        if kind == os.P_PIDFD:
            child = self.handles[target]
            if child is None or child.parent != self.host or self.processes.get(child.pid) is not child:
                raise ChildProcessError
            children = [child]
        else:
            assert kind == os.P_ALL and target == 0
            children = [child for child in self.processes.values() if child.parent == self.host]
        if not children:
            raise ChildProcessError
        if not options & os.WNOHANG and self.on_blocking_wait is not None:
            self.on_blocking_wait()
        exited = next((child for child in children if not child.alive), None)
        if exited is None:
            assert options & os.WNOHANG, "controlled blocking wait has no scheduled exit"
            return None
        if not options & os.WNOWAIT:
            self.reaped.append(exited.pid)
            del self.processes[exited.pid]
        return SimpleNamespace(si_pid=exited.pid)


@pytest.fixture
def observation_kernel(monkeypatch):
    return _ObservationKernel(monkeypatch)


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


@pytest.mark.parametrize("when", ["before_cleanup", "during_termination"])
def test_time_budget_observation_deadline_process_ownership_reparenting(tmp_path, monkeypatch, observation_kernel, when):
    kernel = observation_kernel
    unrelated = kernel.spawn(parent=1)
    control, clock = _observation(tmp_path)
    _claim(control)
    assert kernel.subreaper == 1 and control.first_start is None
    parent = kernel.spawn()
    orphan = None
    if when == "before_cleanup":
        orphan = kernel.spawn(parent=parent.pid)
        kernel.exit(parent)
        assert orphan.alive and orphan.parent == kernel.host
    else:
        def fork_during_term(child, sig):
            nonlocal orphan
            if child is parent and sig == signal.SIGTERM:
                orphan = kernel.spawn(parent=parent.pid)

        kernel.on_signal = fork_during_term
    for name in ("kill", "killpg"):
        monkeypatch.setattr(os, name, lambda *args: pytest.fail("bare PID/group signalling is not ownership"))
    control.terminal("completed")
    end = control.cleanup_deadline
    assert control.stop_owned_processes()
    assert orphan is not None and not orphan.alive
    assert set(kernel.reaped) == {parent.pid, orphan.pid}
    assert all(pid != unrelated.pid for pid, _ in kernel.signals)
    assert (orphan.pid, signal.SIGKILL) in kernel.signals
    control.finish_cleanup(True)
    assert control.cleanup_deadline == end == clock.now + 20
    assert control.as_record()["host_reusable"] is True
    assert control.as_record()["owned_processes_stopped"] is True
    assert kernel.subreaper == 0  # No new-mode process setting leaks to legacy work.
    assert kernel.processes == {unrelated.pid: unrelated} and unrelated.alive


@pytest.mark.parametrize("case", [
    "preexisting_child", "preexisting_zombie", "another_thread", "foreign_subreaper",
    "pidfd_missing", "pidfd_enosys", "pidfd_denied", "signal_denied", "waitid_unsupported",
    "subreaper_denied", "subreaper_unconfirmed", "nonlinux", "sigchld_ignored",
])
def test_time_budget_observation_deadline_process_ownership_admission_refuses(tmp_path, monkeypatch, observation_kernel, case):
    import errno
    import core.time_budget_observation_deadline as deadline

    kernel = observation_kernel
    before = None

    def denied(*args, **kwargs):
        raise OSError(errno.ENOSYS if case in ("pidfd_enosys", "waitid_unsupported") else errno.EPERM, "synthetic unsupported interface")

    if case in ("preexisting_child", "preexisting_zombie"):
        before = kernel.spawn()
        if case == "preexisting_zombie":
            kernel.exit(before)
    elif case == "another_thread":
        kernel.one_thread = False
    elif case == "foreign_subreaper":
        kernel.subreaper = 1
    elif case == "pidfd_missing":
        monkeypatch.delattr(os, "pidfd_open")
    elif case in ("pidfd_enosys", "pidfd_denied"):
        monkeypatch.setattr(os, "pidfd_open", denied)
    elif case == "signal_denied":
        monkeypatch.setattr(signal, "pidfd_send_signal", denied)
    elif case == "waitid_unsupported":
        monkeypatch.setattr(os, "waitid", denied)
    elif case == "subreaper_denied":
        monkeypatch.setattr(deadline, "_child_subreaper", denied)
    elif case == "subreaper_unconfirmed":
        monkeypatch.setattr(deadline, "_child_subreaper", lambda **kwargs: 0)
    elif case == "nonlinux":
        monkeypatch.setattr(sys, "platform", "unsupported")
    elif case == "sigchld_ignored":
        getsignal = signal.getsignal
        monkeypatch.setattr(signal, "getsignal", lambda sig: signal.SIG_IGN if sig == signal.SIGCHLD else getsignal(sig))
    with pytest.raises(deadline.ObservationDeadlineRefused, match=deadline.OWNERSHIP_REQUIRED):
        _observation(tmp_path)
    assert list((tmp_path / "host-observations").iterdir()) == []
    assert kernel.signals == kernel.reaped == []
    if before is not None:
        assert kernel.processes == {before.pid: before}


@pytest.mark.parametrize("case", ["stale_candidate", "pid_reused_before_open", "pid_reused_after_open"])
def test_time_budget_observation_deadline_process_ownership_pidfd_child_identity(tmp_path, monkeypatch, observation_kernel, case):
    kernel = observation_kernel
    outside = kernel.spawn(parent=1)
    control, _ = _observation(tmp_path)
    _claim(control)
    owned = kernel.spawn()
    stale_pid = outside.pid
    if case != "stale_candidate":
        original = kernel.spawn()
        stale_pid = original.pid
        opener = os.pidfd_open

        def substitute(pid):
            if pid != stale_pid:
                return opener(pid)
            if case == "pid_reused_after_open":
                handle = opener(pid)
            kernel.exit(original)
            del kernel.processes[pid]
            kernel.spawn(parent=1, pid=pid)
            return handle if case == "pid_reused_after_open" else opener(pid)

        monkeypatch.setattr(os, "pidfd_open", substitute)
    kernel.candidates = {owned.pid, stale_pid}
    control.terminal("completed")
    assert control.stop_owned_processes()
    control.finish_cleanup(True)
    assert control.cleanup_complete
    assert kernel.signals == [(owned.pid, signal.SIGTERM), (owned.pid, signal.SIGKILL)]
    assert kernel.processes[stale_pid].alive and outside.alive


@pytest.mark.parametrize("case", [
    "wait_expiry", "empty_proc_listing", "new_child_after_stop", "thread_not_joined",
    "signal_denied", "child_wait_denied",
])
def test_time_budget_observation_deadline_process_ownership_incomplete_refuses_reuse(tmp_path, monkeypatch, observation_kernel, case):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TIMEOUT

    kernel = observation_kernel
    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
        clock.advance(1200)
        control.terminal(TIMEOUT)
    end = control.cleanup_deadline
    if case in ("wait_expiry", "empty_proc_listing"):
        child = kernel.spawn()
        if case == "empty_proc_listing":
            kernel.candidates = set()

        def expire():
            assert control._supervising > 0
            clock.advance(control.remaining_cleanup())
            signal.raise_signal(signal.SIGALRM)

        kernel.on_blocking_wait = expire
        assert control.stop_owned_processes() is False
        assert child.pid in kernel.processes  # No confirmed reap, even after KILL.
    elif case in ("signal_denied", "child_wait_denied"):
        child = kernel.spawn()

        def denied(*args, **kwargs):
            raise PermissionError("synthetic child ownership/termination uncertainty")

        if case == "signal_denied":
            monkeypatch.setattr(signal, "pidfd_send_signal", denied)
        else:
            waitid = os.waitid
            monkeypatch.setattr(os, "waitid", lambda kind, target, options: denied() if kind == os.P_PIDFD else waitid(kind, target, options))
        assert control.stop_owned_processes() is False
        assert child.alive
    else:
        assert control.stop_owned_processes()
        if case == "new_child_after_stop":
            kernel.spawn()
        else:
            kernel.one_thread = False
    control.finish_cleanup(True)
    assert control.cleanup_deadline == end == control.first_start + 1220
    assert not control.as_record()["host_reusable"] and not control.cleanup_complete
    assert control.cleanup_expired is (case in ("wait_expiry", "empty_proc_listing"))
    assert (control.directory / "host-lease.json").exists()
    receipt = control.directory / (control.identity.key + ".cleanup.json")
    if receipt.exists():
        durable = json.loads(receipt.read_bytes())
        assert durable["cleanup_complete"] is durable["host_reusable"] is False
    else:
        assert control.cleanup_expired  # Expiry does not start unbounded receipt I/O.
    kernel.one_thread = True
    # Changing the private receipt directory cannot discharge kernel ownership.
    other = tmp_path / "another-directory"
    other.mkdir(mode=0o700)
    with pytest.raises(ObservationDeadlineRefused):
        _observation(other, clock=clock, task_index=1)
    assert list((other / "host-observations").iterdir()) == []


@pytest.mark.parametrize("case", ["subreaper_removed", "forked_host", "sigchld_changed"])
def test_time_budget_observation_deadline_process_ownership_authority_lost(tmp_path, monkeypatch, observation_kernel, case):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, OWNERSHIP_REQUIRED

    control, _ = _observation(tmp_path)
    if case == "subreaper_removed":
        observation_kernel.subreaper = 0
    elif case == "forked_host":
        monkeypatch.setattr(os, "getpid", lambda: observation_kernel.host + 1)
    else:
        getsignal = signal.getsignal
        monkeypatch.setattr(signal, "getsignal", lambda sig: signal.SIG_IGN if sig == signal.SIGCHLD else getsignal(sig))
    with pytest.raises(ObservationDeadlineRefused, match=OWNERSHIP_REQUIRED):
        _claim(control)
    assert control.first_start is None and not control.cleanup_complete
    assert (control.directory / "host-lease.json").exists()
    assert observation_kernel.signals == observation_kernel.reaped == []


def test_time_budget_observation_deadline_process_ownership_release_and_exclusivity(tmp_path, observation_kernel):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused

    kernel = observation_kernel
    control, clock = _observation(tmp_path)
    other = tmp_path / "other-host-name"
    other.mkdir(mode=0o700)
    with pytest.raises(ObservationDeadlineRefused):
        _observation(other, clock=clock, task_index=1)
    _claim(control)
    child = kernel.spawn()
    control.terminal("completed")

    class UntrustedSDKHandle:
        def __getattr__(self, name):
            pytest.fail("SDK handle is not ownership/kill/wait authority")

    assert control.stop_owned_processes(UntrustedSDKHandle())
    assert kernel.reaped == [child.pid]
    control.finish_cleanup(True)
    assert control.cleanup_complete and kernel.subreaper == 0
    next_control, _ = _observation(tmp_path, clock=clock, task_index=1)
    assert next_control.first_start is None and kernel.subreaper == 1
    next_control.terminal("abandoned")
    next_control.finish_cleanup(True)
    assert next_control.cleanup_complete and kernel.subreaper == 0


def test_time_budget_observation_deadline_process_ownership_source_pin():
    source = historical.ROOT / "batch-runner/core/time_budget_observation_deadline.py"
    manifest = prospective.load_registration()
    assert manifest["source_pins"]["batch-runner/core/time_budget_observation_deadline.py"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert prospective.ACCEPTED_BASE_SHA == "882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2"
    assert hashlib.sha256((historical.ROOT / prospective.SOURCE_PROFILE).read_bytes()).hexdigest() == "81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe"


def test_time_budget_observation_deadline_process_ownership_platform_contract(tmp_path, record_property):
    """One short real-kernel lifecycle OR explicit unsupported-host refusal.

    This child imports only the helper, uses synthetic identity/files, and has
    no provider, credentials, network, private inputs or long-running worker.
    The daemon has a five-second test failsafe in addition to parent supervision.
    """
    script = r'''
import json, os, signal, sys
from pathlib import Path
from core.time_budget_observation_deadline import (
    ObservationIdentity, TimeBudgetObservation, ObservationDeadlineRefused,
    OWNERSHIP_REQUIRED, STUDY_ID, TASK_IDS,
)
directory = Path(sys.argv[1]) / "synthetic-owned-host"
directory.mkdir(mode=0o700)
identity = ObservationIdentity(STUDY_ID, "gpt54_time_budget_v1_codex_r1", "codex", 1,
    TASK_IDS[0], "1" * 40, "2" * 40, "3" * 64, "4" * 64)
try:
    control = TimeBudgetObservation(directory, identity)
except ObservationDeadlineRefused as error:
    assert str(error) == OWNERSHIP_REQUIRED
    assert list(directory.iterdir()) == []
    print(json.dumps({"platform_result": "admission_refused", "host_reusable": False, "reason": str(error),
        "cause_type": type(error.__cause__).__name__, "errno": getattr(error.__cause__, "errno", None)}))
    sys.exit(0)
control.claim(run_id=identity.run_id, condition=identity.condition, task_id=identity.task_id)
with control.supervise():
    control.start()
reader, writer = os.pipe()
parent = os.fork()
if parent == 0:
    orphan = os.fork()
    if orphan == 0:
        os.close(reader)
        os.setsid()
        signal.alarm(5)
        os.write(writer, str(os.getpid()).encode() + b"\n")
        os.close(writer)
        signal.pause()
        os._exit(90)
    os._exit(0)
os.close(writer)
os.waitpid(parent, 0)
with os.fdopen(reader, "rb") as pipe:
    orphan = int(pipe.readline(64))
assert orphan in control._child_pids()
fields = Path(f"/proc/{orphan}/stat").read_bytes().rsplit(b")", 1)[1].split()
assert int(fields[1]) == os.getpid()  # Parent exit and setsid did not escape ownership.
control.terminal("completed")
assert control.stop_owned_processes()
control.finish_cleanup(True)
assert control.cleanup_complete and control._no_kernel_children()
assert not (directory / "host-lease.json").exists()
print(json.dumps({"platform_result": "real_reparenting_confirmed", "host_reusable": True}))
'''
    process = _REAL_POPEN([sys.executable, "-c", script, str(tmp_path)],
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=10)
    except BaseException:
        process.kill()
        process.communicate(timeout=2)
        raise
    assert process.returncode == 0, stderr.decode(errors="replace")[:4000]
    outcome = json.loads(stdout)
    assert outcome["platform_result"] in {"admission_refused", "real_reparenting_confirmed"}
    assert outcome["host_reusable"] is (outcome["platform_result"] == "real_reparenting_confirmed")
    record_property("time_budget_owned_host_platform", json.dumps(outcome, sort_keys=True))
    print(json.dumps(outcome, sort_keys=True))


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
    # An expired observation must not start receipt I/O outside its deadline.
    record = control.as_record()
    assert not (control.directory / (control.identity.key + ".cleanup.json")).exists()
    assert record["cleanup_expired"] is True and record["host_reusable"] is False
    assert record["interruption_attempted"] is record["interruption_acknowledged"] is True
    assert record["remote_cancellation_confirmed"] is record["remote_billing_bound"] is False
    with pytest.raises(ObservationDeadlineRefused):
        _observation(tmp_path, clock=clock, task_index=1)


def test_time_budget_observation_deadline_interrupt_latch_and_owned_child(tmp_path, observation_kernel):
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
    child = observation_kernel.spawn()
    assert control.stop_owned_processes()
    assert observation_kernel.signals == [(child.pid, signal.SIGTERM), (child.pid, signal.SIGKILL)]
    control.finish_cleanup(True)
    assert control.cleanup_complete and not observation_kernel.processes


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


def _assert_finalization_refused(tmp_path, control, clock, *, lease_present):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused

    record = control.as_record()
    assert record["cleanup_expired"] is True
    assert record["cleanup_complete"] is record["host_reusable"] is False
    assert record["cleanup_finished_monotonic"] is None
    assert control.cleanup_failed
    assert (control.directory / "host-lease.json").exists() is lease_present
    admitted = control.directory / (control.identity.key + ".admitted.json")
    assert json.loads(admitted.read_bytes())["run_id"] == control.identity.run_id
    receipt = control.directory / (control.identity.key + ".cleanup.json")
    if receipt.exists():
        durable = json.loads(receipt.read_bytes())
        assert durable["cleanup_complete"] is durable["host_reusable"] is False
        assert durable["finalization_pending"] is True
        assert durable["cleanup_finished_monotonic"] is None
    before = {path.name: path.read_bytes() for path in control.directory.iterdir()}
    # Both the same observation and a different task refuse, including after
    # unlink succeeded but its fsync/finalization did not finish in time.
    for task_index in (0, 1):
        with pytest.raises(ObservationDeadlineRefused):
            _observation(tmp_path, clock=clock, task_index=task_index)
    with pytest.raises(ObservationDeadlineRefused):
        control.finish_cleanup(True)
    assert {path.name: path.read_bytes() for path in control.directory.iterdir()} == before
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


@pytest.mark.parametrize("entry", ["generation_alarm", "outside_supervisor"])
@pytest.mark.parametrize("stage", ["file_fsync", "directory_fsync"])
def test_time_budget_observation_deadline_finalization_terminal_persistence(tmp_path, monkeypatch, entry, stage):
    import stat
    from core.time_budget_observation_deadline import ObservationCleanupExpired, TIMEOUT

    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
    first = control.first_start
    fsync = os.fsync
    pending = []

    def pending_fsync(fd):
        file = stat.S_ISREG(os.fstat(fd).st_mode)
        if file == (stage == "file_fsync"):
            # The generation alarm is one-shot: its handler must already have
            # armed the original cleanup end BEFORE entering this pending I/O.
            assert control._supervising > 0
            assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 20
            assert control.cleanup_deadline == first + 1220
            assert control.remaining_cleanup() == 20
            pending.append(stage)
            clock.advance(20)
            signal.raise_signal(signal.SIGALRM)
            pytest.fail("pending terminal persistence escaped cleanup expiry")
        return fsync(fd)

    with monkeypatch.context() as io_patch:
        io_patch.setattr(os, "fsync", pending_fsync)
        with pytest.raises(ObservationCleanupExpired):
            if entry == "generation_alarm":
                with control.supervise():
                    clock.advance(1200)
                    signal.raise_signal(signal.SIGALRM)
            else:
                clock.advance(1200)
                control.terminal(TIMEOUT)
        assert control.interruption_attempted is (entry == "generation_alarm")
        assert pending == [stage]
        assert control.terminal_reason == TIMEOUT
        assert control.cleanup_deadline == first + 1220
        io_patch.setattr(control, "_write", lambda *args: pytest.fail("post-expiry receipt I/O"))
        assert control.finish_cleanup(True) is None
    assert not (control.directory / (control.identity.key + ".cleanup.json")).exists()
    _assert_finalization_refused(tmp_path, control, clock, lease_present=True)


@pytest.mark.parametrize("expiry", ["alarm", "late_return"])
@pytest.mark.parametrize("stage", [
    "directory_open", "receipt_write", "receipt_file_fsync", "receipt_directory_fsync",
    "lease_unlink", "lease_directory_fsync", "directory_close",
])
def test_time_budget_observation_deadline_finalization_io_expiry(tmp_path, monkeypatch, stage, expiry):
    import stat

    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
        clock.advance(3)
        control.terminal("completed")
    end = control.cleanup_deadline
    clock.advance(19)
    assert control.remaining_cleanup() == 1
    directory_fd, write, fsync, unlink, close = control._directory_fd, control._write, os.fsync, os.unlink, os.close
    state = {"parent": None, "writing": False, "unlinked": False, "expired": False}

    def cross_deadline():
        assert not state["expired"]
        assert control._supervising > 0
        assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 1
        assert not control.cleanup_complete
        state["expired"] = True
        clock.advance(1)
        if expiry == "alarm":
            signal.raise_signal(signal.SIGALRM)

    def open_parent():
        parent = directory_fd()
        if state["parent"] is None:
            state["parent"] = parent
            if stage == "directory_open":
                try:
                    cross_deadline()
                except BaseException:
                    close(parent)
                    raise
        return parent

    def receipt_write(name, value):
        assert name.endswith(".cleanup.json")
        assert value["cleanup_complete"] is value["host_reusable"] is False
        assert value["finalization_pending"] is True
        state["writing"] = True
        try:
            result = write(name, value)
            if stage == "receipt_write":
                cross_deadline()
            return result
        finally:
            state["writing"] = False

    def delayed_fsync(fd):
        assert clock.now < end
        file = stat.S_ISREG(os.fstat(fd).st_mode)
        result = fsync(fd)
        if ((state["writing"] and stage == ("receipt_file_fsync" if file else "receipt_directory_fsync"))
                or (state["unlinked"] and stage == "lease_directory_fsync")):
            cross_deadline()
        return result

    def delayed_unlink(name, **kwargs):
        assert clock.now < end
        assert name == "host-lease.json" and not state["writing"]
        result = unlink(name, **kwargs)
        state["unlinked"] = True
        if stage == "lease_unlink":
            cross_deadline()
        return result

    def delayed_close(fd):
        result = close(fd)
        if fd == state["parent"] and stage == "directory_close":
            cross_deadline()
        return result

    with monkeypatch.context() as io_patch:
        io_patch.setattr(control, "_directory_fd", open_parent)
        io_patch.setattr(control, "_write", receipt_write)
        io_patch.setattr(os, "fsync", delayed_fsync)
        io_patch.setattr(os, "unlink", delayed_unlink)
        io_patch.setattr(os, "close", delayed_close)
        assert control.finish_cleanup(True) is None
    assert state["expired"]
    assert control.cleanup_deadline == end == 123
    assert control.terminal_reason == "completed"  # Finalization failed, not generation.
    _assert_finalization_refused(tmp_path, control, clock, lease_present=not state["unlinked"])


@pytest.mark.parametrize("reuse", ["same_host", "lost_confirmation", "forked_host"])
def test_time_budget_observation_deadline_finalization_before_deadline(tmp_path, monkeypatch, reuse):
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TimeBudgetObservation

    control, clock = _observation(tmp_path)
    _claim(control)
    with control.supervise():
        control.start()
        clock.advance(4)
        control.terminal("completed")
    clock.advance(15)
    fsync = os.fsync
    persisted = []

    def finite_fsync(fd):
        assert control._supervising > 0
        assert not control.cleanup_complete
        persisted.append(control.remaining_cleanup())
        result = fsync(fd)
        clock.advance(1)
        return result

    with monkeypatch.context() as io_patch:
        io_patch.setattr(os, "fsync", finite_fsync)
        assert control.finish_cleanup(True) is None
    assert persisted == [5, 4, 3]
    record = control.as_record()
    assert record["cleanup_complete"] is record["host_reusable"] is True
    assert record["cleanup_expired"] is False
    assert record["cleanup_finished_monotonic"] == 122 < control.cleanup_deadline == 124
    assert record["cleanup_elapsed_seconds"] == 18
    assert not (control.directory / "host-lease.json").exists()
    durable = json.loads((control.directory / (control.identity.key + ".cleanup.json")).read_bytes())
    assert durable["cleanup_complete"] is durable["host_reusable"] is False
    assert durable["finalization_pending"] is True
    assert durable["cleanup_finished_monotonic"] is None
    with pytest.raises(ObservationDeadlineRefused):
        control.cleanup(lambda: pytest.fail("finalized observation restarted cleanup"))
    clock.advance(100)  # Returning/reading evidence later does not redo cleanup.
    assert control.as_record()["cleanup_elapsed_seconds"] == 18
    with pytest.raises(ObservationDeadlineRefused):
        _observation(tmp_path, clock=clock)
    if reuse == "same_host":
        other, _ = _observation(tmp_path, clock=clock, task_index=1)
        assert other.first_start is None
        with pytest.raises(ObservationDeadlineRefused):
            _observation(tmp_path, clock=clock, task_index=2)
    else:
        if reuse == "lost_confirmation":
            monkeypatch.setattr(TimeBudgetObservation, "_released_hosts", {})
        else:
            pid = os.getpid()
            monkeypatch.setattr(os, "getpid", lambda: pid + 1)
        with pytest.raises(ObservationDeadlineRefused):
            _observation(tmp_path, clock=clock, task_index=1)
        assert not (control.directory / "host-lease.json").exists()
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


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
def test_time_budget_observation_deadline_codex_actual_entry(tmp_path, monkeypatch, observation_kernel, case):
    import core.codex_runner as native
    from core.codex_runtime_config import LoopbackCodexProvider
    from core.time_budget_observation_deadline import ObservationDeadlineRefused, TIMEOUT, CLEANUP_UNCONFIRMED
    from openai_codex.generated.v2_all import TurnInterruptResponse

    control, clock = _observation(tmp_path)
    events = []

    class Process:
        child = None

        @property
        def alive(self):
            return self.child is not None and self.child.alive

    process = Process()

    def signalled(child, sig):
        if child is process.child and sig == signal.SIGKILL:
            events.append("kill_owned_process")

    def reaping():
        assert control._supervising and control.remaining_cleanup() > 0
        events.append("bounded_wait")
        clock.advance(0.25)

    observation_kernel.on_signal = signalled
    observation_kernel.on_blocking_wait = reaping

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
        process.child = observation_kernel.spawn()
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


def test_time_budget_frozen_judge_binding_genuine_dual_roots(dual_roots, tmp_path, monkeypatch):
    from step8_grade import compute_grader_source_hash
    import gpt54_run_config_bundle as bundle
    from gpt54_disposable_checkout import DisposableCheckoutRefused

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

    # Complete the identity checks that the first failed positive could not
    # reach: its clone was not a registered detached linked worktree. Do not
    # mistake that early layout refusal for tracked-blob/anchor evidence.
    for case in ("swapped_roots", "wrong_runtime_commit", "coherent_substitution"):
        candidate, anchors = deepcopy(plan), _anchors(dual_roots)
        if case == "swapped_roots":
            anchors["runtime_root"], anchors["frozen_grader_root"] = frozen, runtime
        elif case == "wrong_runtime_commit":
            anchors["expected_reviewed_source_sha"] = prospective.ACCEPTED_BASE_SHA
        else:
            anchors["runtime_root"] = dual_roots["substitute"]
            candidate = prospective.load_registration(dual_roots["substitute"] / prospective.REGISTRATION_PATH)
        with pytest.raises(prospective.TimeBudgetRegistrationRefused) as refused:
            prospective.compile_registration(candidate, **anchors)
        assert isinstance(refused.value.__cause__, DisposableCheckoutRefused)
        assert str(refused.value.__cause__) == "runtime checkout HEAD must be the reviewed detached commit"

    for field, reason in (("runtime_digest", "runtime_source_roles"), ("judge_digest", "shared_facts")):
        candidate = deepcopy(plan)
        if field == "runtime_digest":
            candidate["source_pins"][prospective.COMPILER] = "0" * 64
        else:
            candidate["shared"]["grading"]["template_source_sha256"] = "0" * 64
        with pytest.raises(prospective.TimeBudgetRegistrationRefused, match="^" + reason + "$"):
            _compile(candidate, dual_roots)

    for root in (runtime, frozen):
        target = root / "batch-runner/core/codex_runner.py"
        before = target.read_bytes()
        try:
            target.write_bytes(before + b"\n# synthetic runtime/judge substitution\n")
            with pytest.raises(prospective.TimeBudgetRegistrationRefused, match="^source_differs_from_reviewed_blob$"):
                _compile(plan, dual_roots)
        finally:
            target.write_bytes(before)

    untracked = runtime / "batch-runner/core/untracked_deadline.py"
    try:
        untracked.write_text("# synthetic untracked source\n")
        with pytest.raises(prospective.TimeBudgetRegistrationRefused, match="^source_core_inventory$"):
            _compile(plan, dual_roots)
    finally:
        untracked.unlink()

    target = runtime / prospective.REGISTRATION_PATH
    before = target.read_bytes()
    try:
        target.write_bytes(before + b"\n# synthetic unreviewed manifest bytes\n")
        with pytest.raises(prospective.TimeBudgetRegistrationRefused, match="^source_differs_from_reviewed_blob$"):
            _compile(plan, dual_roots)
    finally:
        target.write_bytes(before)

    for substitution in ("symlink", "hardlink"):
        target = runtime / historical.GRADER
        before = target.read_bytes()
        external = tmp_path / (substitution + "-grader.yaml")
        try:
            if substitution == "symlink":
                external.write_bytes(before)
                target.unlink()
                target.symlink_to(external)
            else:
                os.link(target, external)
            with pytest.raises(prospective.TimeBudgetRegistrationRefused) as refused:
                _compile(plan, dual_roots)
            assert "detached checkout registration mismatch" not in str(refused.value.__cause__)
            assert "regular" in str(refused.value.__cause__) or "symlink" in str(refused.value.__cause__)
        finally:
            if substitution == "symlink":
                target.unlink()
                target.write_bytes(before)
            external.unlink()

    for race in ("final_reread", "held_parent", "head_substitution"):
        target = runtime / "batch-runner/core/codex_runner.py"
        before = target.read_bytes()
        head = dual_roots["gitdirs"]["runtime"] / "HEAD"
        before_head = head.read_bytes()
        moved = None
        sources = bundle._sources

        def raced(root, manifest, locator):
            nonlocal moved
            actual = sources(root, manifest, locator)
            if root == runtime:
                if race == "held_parent":
                    parent = runtime / "batch-runner/core"
                    moved = parent.with_name("held-original-core")
                    parent.rename(moved)
                    parent.mkdir()
                elif race == "head_substitution":
                    head.write_text(prospective.ACCEPTED_BASE_SHA + "\n")
                else:
                    target.write_bytes(before + b"\n# final reread race\n")
            return actual

        try:
            with monkeypatch.context() as guarded:
                guarded.setattr(bundle, "_sources", raced)
                with pytest.raises(prospective.TimeBudgetRegistrationRefused) as refused:
                    _compile(plan, dual_roots)
                assert str(refused.value) == "registration_cannot_be_compiled"
                assert "detached checkout registration mismatch" not in str(refused.value.__cause__)
        finally:
            if moved is not None:
                (runtime / "batch-runner/core").rmdir()
                moved.rename(runtime / "batch-runner/core")
            target.write_bytes(before)
            head.write_bytes(before_head)


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
            head = dual_roots["gitdirs"]["runtime"] / "HEAD"
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
    from step8_grade import compute_grader_source_hash

    root = tmp_path / "synthetic-retained-source"
    retained_fixture._source_tree(root)  # Shared old fresh/keep fixture, not a live preparation.
    template = root / historical.GRADER
    template.parent.mkdir(parents=True)
    with template.open("xb") as target:
        target.write((historical_retention_source / historical.GRADER).read_bytes())
    for name in (historical_retention_source / "batch-runner/core").rglob("*.py"):
        assert (root / name.relative_to(historical_retention_source)).read_bytes() == name.read_bytes()
    assert compute_grader_source_hash(root / historical.GRADER, historical.load_plan(root / historical.GRADER),
                                      batch_root=root / "batch-runner") == prospective.FROZEN_TEMPLATE_SHA256
    for role, digest in retention_report.FROZEN_SOURCE.items():
        assert hashlib.sha256((historical_retention_source / role).read_bytes()).hexdigest() == digest
    for role, digest in retention_report.CURRENT_SOURCE.items():
        assert hashlib.sha256((retained_fixture.REAL_ROOT / role).read_bytes()).hexdigest() == digest


def test_time_budget_legacy_role_compatibility_workflow_profile(monkeypatch, frozen_local_comparison_source):
    from .test_gpt54_workflow_gate import test_workflow_profile_anchor_current_source_and_frozen_refusals

    test_workflow_profile_anchor_current_source_and_frozen_refusals(monkeypatch, frozen_local_comparison_source)


def test_time_budget_legacy_role_compatibility_disposable_profile(monkeypatch, capsys, frozen_local_comparison_source):
    from .test_gpt54_disposable_checkout import test_prospective_source_profile_real_tracked_compilation_and_refusals

    test_prospective_source_profile_real_tracked_compilation_and_refusals(monkeypatch, capsys, frozen_local_comparison_source)


@pytest.fixture(scope="module")
def handoff_source_seed(tmp_path_factory, dual_roots):
    """Explicit synthetic input declarations in genuine temporary R/F commits.

    Only dataset/catalog/envelope/profile metadata is changed in synthetic F;
    its real core/grader/template closure is untouched. No validator returns a
    mocked success. No production or original/private input is read or repinned.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    import yaml
    from core.source_identity import SOURCE_PROJECTION_FIELDS, source_task_projection_sha256
    from gpt54_prepared_input_attestation import _identity
    from .test_gpt54_disposable_checkout import _FIXTURE_ENV

    repository = Path(__file__).resolve().parents[2]
    parent = tmp_path_factory.mktemp("synthetic-observation-inputs")
    environment = {**_FIXTURE_ENV, "GIT_ALLOW_PROTOCOL": "file"}

    def git(*command):
        return _REAL_RUN(["git", *command], check=True, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, env=environment, timeout=30).stdout

    def export(role, sha):
        root, owner = parent / role, parent / (role + "-objects")
        git("clone", "--shared", "--no-checkout", "--", str(repository), str(owner))
        git("-C", str(owner), "worktree", "add", "--detach", "--no-checkout", str(root), sha)
        archive = git("-C", str(repository), "archive", "--format=tar", sha, "batch-runner", ".github/workflows")
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as source:
            assert source.pax_headers["comment"] == sha
            assert all(not Path(member.name).is_absolute() and ".." not in Path(member.name).parts
                       and (member.isdir() or member.isfile()) for member in source.getmembers())
            source.extractall(root)
        git("-C", str(root), "read-tree", sha)
        return root

    runtime = export("runtime", dual_roots["runtime_sha"])
    frozen = export("frozen", prospective.ACCEPTED_BASE_SHA)
    catalog_role = historical.ENVELOPE + "gdpval_task_catalog.json"
    envelope_role = historical.ENVELOPE + "advance_check_plan.yaml"
    profile = historical.load_plan(frozen / prospective.SOURCE_PROFILE)
    catalog = json.loads((frozen / catalog_role).read_bytes())
    by_id = {row["task_id"]: row for row in catalog["tasks"]}
    task_ids = tuple(row["task_id"] for row in profile["shared"]["dataset"]["tasks"])
    references = parent / "references"
    references.mkdir()
    rows, records = [], {}
    for index, task_id in enumerate(task_ids):
        declaration = by_id[task_id]
        prompt = f"Synthetic handoff task {index}: create a small example.\n"
        declaration["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
        declaration["prompt_character_count"] = len(prompt)
        names = declaration["reference_file_paths"]
        for name in names:
            path = references / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"Synthetic reference for observation task {index}.\n".encode())
            records[name] = _identity(path.read_bytes())
        rows.append({
            "task_id": task_id, "prompt": prompt,
            "occupation": declaration["occupation"], "sector": declaration["sector"],
            "rubric_json": '[{"criterion":"synthetic only; not a grade"}]',
            "rubric_pretty": "Synthetic grading metadata; not model input.\n",
            "reference_files": names, "reference_file_urls": [],
            "reference_file_hf_uris": [],
            "deliverable_files": ["synthetic-withheld-answer"] if declaration["deliverable_file_extensions"] else [],
        })
    parquet = parent / "synthetic-original.parquet"
    pq.write_table(pa.Table.from_pylist(list(reversed(rows))), parquet)
    catalog["dataset_file_sha256"] = _identity(parquet.read_bytes())["sha256"]
    catalog_data = historical._canonical_json(catalog).encode()
    versions = {catalog["dataset_repo_id"] + "@" + catalog["dataset_revision"]: catalog["dataset_file_sha256"],
                **{name: record["sha256"] for name, record in records.items()}}
    envelope = historical.load_plan(frozen / envelope_role)
    envelope["model_run_conditions"]["shared"]["input_file_versions"] = versions
    envelope_data = historical._canonical_json(envelope).encode()
    dataset = profile["shared"]["dataset"]
    dataset.update(parquet_sha256=catalog["dataset_file_sha256"], input_file_versions=versions,
                   catalog_sha256=_identity(catalog_data)["sha256"],
                   tasks=[{"task_id": task, "prompt_sha256": by_id[task]["prompt_sha256"]} for task in task_ids])
    profile["source_pins"].update({catalog_role: _identity(catalog_data)["sha256"],
                                   envelope_role: _identity(envelope_data)["sha256"]})
    for root in (runtime, frozen):
        (root / catalog_role).write_bytes(catalog_data)
        (root / envelope_role).write_bytes(envelope_data)
    profile_data = yaml.safe_dump(profile, sort_keys=False, allow_unicode=True).encode()
    assert b"&id001" in profile_data and b"*id001" in profile_data
    (frozen / prospective.SOURCE_PROFILE).write_bytes(profile_data)
    input_only_role = historical.ENVELOPE + "synthetic-input-only.yaml"
    (frozen / input_only_role).write_bytes(profile_data)
    mismatch_role = historical.ENVELOPE + "synthetic-mismatched-input-only.yaml"
    mismatch = deepcopy(profile)
    mismatch["shared"]["dataset"]["cohort"] = "full_220"
    (frozen / mismatch_role).write_bytes(historical._canonical_json(mismatch).encode())
    git("-C", str(frozen), "add", "--", catalog_role, envelope_role, prospective.SOURCE_PROFILE,
        input_only_role, mismatch_role)
    git("-C", str(frozen), "commit", "-m", "test: declare synthetic input-only source")
    frozen_sha = git("-C", str(frozen), "rev-parse", "HEAD").decode().strip()
    frozen_tree = git("-C", str(frozen), "rev-parse", "HEAD^{tree}").decode().strip()
    plan = prospective.load_registration(runtime / prospective.REGISTRATION_PATH)
    plan["shared"]["dataset"] = dataset
    plan["source_pins"].update({name: profile["source_pins"][name] for name in (catalog_role, envelope_role)})
    basis = plan["source_basis"]
    basis.update(accepted_base_sha=frozen_sha, accepted_base_tree=frozen_tree)
    basis["source_profile"]["sha256"] = _identity(profile_data)["sha256"]
    basis["frozen_grader"].update(source_sha=frozen_sha, source_tree=frozen_tree)
    (runtime / prospective.REGISTRATION_PATH).write_bytes(historical._canonical_json(plan).encode())
    git("-C", str(runtime), "add", "--", catalog_role, envelope_role, prospective.REGISTRATION_PATH)
    git("-C", str(runtime), "commit", "-m", "test: bind prospective runtime to synthetic inputs")
    runtime_sha = git("-C", str(runtime), "rev-parse", "HEAD").decode().strip()
    runtime_tree = git("-C", str(runtime), "rev-parse", "HEAD^{tree}").decode().strip()
    step0_value = {
        "_schema_version": 4, "_summary": {"active_policy": "deliverable_only"},
        "_total_tasks": 6,
        "tasks": {row["task_id"]: {
            "needs_files": bool(row["deliverable_files"]),
            "source_projection_sha256": source_task_projection_sha256(**{name: row[name] for name in SOURCE_PROJECTION_FIELDS}),
        } for row in rows}, "reference_files": records,
    }
    step0_value["tasks"]["unselected-synthetic-task"] = {
        "needs_files": False, "source_projection_sha256": "e" * 64,
    }
    step0 = parent / "synthetic-canonical-step0.json"
    step0.write_bytes(historical._canonical_json(step0_value).encode())
    return SimpleNamespace(
        runtime=runtime, runtime_sha=runtime_sha, runtime_tree=runtime_tree,
        frozen=frozen, frozen_sha=frozen_sha, frozen_tree=frozen_tree,
        profile_sha=_identity(profile_data)["sha256"], plan=plan,
        parquet=parquet, references=references, step0=step0,
        step0_sha=_identity(step0.read_bytes())["sha256"], rows=rows, records=records, task_ids=task_ids,
        mismatch_role=mismatch_role, input_only_role=input_only_role,
    )


@pytest.fixture
def handoff_sources(handoff_source_seed, monkeypatch):
    from core import repo_bootstrapper

    seed = handoff_source_seed
    # Only explicit fixture identities differ. The tracked-blob/closure/input
    # checks themselves are unmodified and must all succeed on actual bytes.
    monkeypatch.setattr(prospective, "ACCEPTED_BASE_SHA", seed.frozen_sha)
    monkeypatch.setattr(prospective, "ACCEPTED_BASE_TREE", seed.frozen_tree)
    monkeypatch.setattr(prospective, "SOURCE_PROFILE_SHA256", seed.profile_sha)
    monkeypatch.setattr(repo_bootstrapper, "CANONICAL_MANIFEST_SHA256_BY_POLICY", {
        **repo_bootstrapper.CANONICAL_MANIFEST_SHA256_BY_POLICY, "deliverable_only": seed.step0_sha,
    })
    return seed


def _handoff_arguments(seed, tmp_path, *, condition="sandbox_v2", repeat=1, task_index=0):
    parent = tmp_path / "publications"
    parent.mkdir(exist_ok=True)
    return dict(
        run_id=f"gpt54_time_budget_v1_{'v2' if condition == 'sandbox_v2' else 'codex'}_r{repeat}",
        task_id=seed.task_ids[task_index], runtime_root=seed.runtime, expected_reviewed_source_sha=seed.runtime_sha,
        frozen_grader_root=seed.frozen, expected_grader_source_sha=seed.frozen_sha,
        input_registration_root=seed.frozen, expected_input_source_sha=seed.frozen_sha,
        input_registration_path=prospective.SOURCE_PROFILE, dataset_parquet=seed.parquet,
        reference_root=seed.references, destination=parent / "one-observation",
        step0_manifest=seed.step0 if condition == "codex" else None,
    )


def _assert_unpublished(arguments):
    output = arguments["destination"]
    assert not output.exists()
    assert not output.with_name(output.name + prospective.HANDOFF_RESERVATION_SUFFIX).exists()


@pytest.mark.parametrize("condition,repeat,task_index", [
    ("sandbox_v2", 1, 0), ("sandbox_v2", 2, 1), ("codex", 1, 0), ("codex", 2, 1),
])
def test_time_budget_observation_handoff_valid_exact_shape(handoff_sources, tmp_path, condition, repeat, task_index):
    from core.agentic_v2_run_driver import TaskToRun
    from core.experiment_config import ExperimentConfig
    from core.time_budget_observation_deadline import ObservationIdentity
    from gpt54_prepared_input_attestation import _identity

    seed = handoff_sources
    arguments = _handoff_arguments(seed, tmp_path, condition=condition, repeat=repeat, task_index=task_index)
    if repeat == 2:
        arguments["input_registration_path"] = seed.input_only_role
    marker = prospective.prepare_observation_handoff(seed.plan, **arguments)
    output = arguments["destination"]
    assert marker == json.loads((output / prospective.HANDOFF_READY).read_bytes())
    assert set(marker) == {
        "preparation_version", "observation", "abba_index", "registration_file", "runtime_source",
        "frozen_grader", "condition_template", "inputs", "observation_control", "files", "launch_authority",
        "evidence_boundary",
    }
    assert marker["preparation_version"] == "gpt54-time-budget-observation-preparation-v1"
    assert marker["evidence_boundary"] == "model_free_one_observation_preparation_not_execution"
    compiled = prospective.compile_registration(seed.plan, runtime_root=seed.runtime,
        expected_reviewed_source_sha=seed.runtime_sha, frozen_grader_root=seed.frozen,
        expected_grader_source_sha=seed.frozen_sha)
    expected_identity = {
        "study_id": prospective.STUDY_ID, "run_id": arguments["run_id"], "condition": condition,
        "repeat": repeat, "task_id": arguments["task_id"], "reviewed_source_sha": seed.runtime_sha,
        "reviewed_source_tree": seed.runtime_tree, "registration_sha256": compiled.manifest_sha256,
        "input_sha256": historical.seal(marker["inputs"]),
    }
    assert marker["observation"] == expected_identity
    assert ObservationIdentity(**expected_identity).task_id == arguments["task_id"]
    assert marker["abba_index"] == [row.run_id for row in compiled.runs].index(arguments["run_id"])
    assert marker["runtime_source"] == {"source_sha": seed.runtime_sha, "source_tree": seed.runtime_tree}
    assert marker["frozen_grader"] == {
        "source_sha": seed.frozen_sha, "source_tree": seed.frozen_tree,
        "template_source_sha256": prospective.FROZEN_TEMPLATE_SHA256,
        "template_config_path": historical.GRADER, "materialized_config_path": None,
        "materialized_grader_source_sha256": None, "execution_source": "frozen_source_only_not_runtime_root",
    }
    assert marker["registration_file"] == {"path": prospective.REGISTRATION_PATH,
        **_identity((seed.runtime / prospective.REGISTRATION_PATH).read_bytes())}
    role = seed.plan["conditions"][condition]["template"]
    assert marker["condition_template"] == {"path": role, **_identity((seed.runtime / role).read_bytes())}
    inputs = marker["inputs"]
    assert inputs["registration"]["source_sha"] == seed.frozen_sha
    assert inputs["registration"]["source_tree"] == seed.frozen_tree
    assert inputs["registration"]["scope"] == "dataset_and_cohort_only_not_legacy_dispatch"
    assert inputs["registration"]["manifest_path"] == arguments["input_registration_path"]
    assert inputs["registration"]["files"] == {
        role: _identity((seed.frozen / role).read_bytes()) for role in (
            arguments["input_registration_path"], historical.ENVELOPE + "gdpval_task_catalog.json",
            historical.ENVELOPE + "advance_check_plan.yaml",
        )
    }
    assert inputs["dataset"]["parquet"] == _identity(seed.parquet.read_bytes())
    assert inputs["step0_manifest"] == (_identity(seed.step0.read_bytes()) if condition == "codex" else None)
    assert inputs["task_id"] == arguments["task_id"]
    config = json.loads((output / prospective.HANDOFF_CONFIG).read_bytes())
    assert set(config) == {"handoff_version", "factory", "configuration", "observation_control",
                           "model_binding", "launch_allowed", "execution_enabled"}
    assert config["model_binding"] == seed.plan["shared"]["model"]
    assert config["launch_allowed"] is config["execution_enabled"] is False
    assert config["observation_control"] == marker["observation_control"] == {
        "required": True, "type": "core.time_budget_observation_deadline.TimeBudgetObservation",
        "factory_argument": "observation_for" if condition == "sandbox_v2" else "observation_control",
        "identity": expected_identity, "generation_seconds": 1200, "cleanup_seconds": 20,
        "admission_reserved": False, "generation_started": False,
    }
    payload = json.loads((output / prospective.HANDOFF_TASK).read_bytes())
    assert set(payload) == {"kind", "arguments", "reference_path_base", "reference_file_records"}
    assert payload["reference_path_base"] == "handoff_directory"
    assert payload["reference_file_records"] == inputs["reference_file_records"]
    assert payload["arguments"]["task_id"] == arguments["task_id"]
    if condition == "sandbox_v2":
        assert config["factory"] == "core.agentic_v2_conversation_runner.build_runner_factory"
        assert payload["kind"] == "sandbox_v2_task_to_run"
        task = TaskToRun(**payload["arguments"])
        assert task.prompt == seed.rows[task_index]["prompt"]
        assert config["configuration"]["task_ids"] == [arguments["task_id"]]
        assert config["configuration"]["model"]["reasoning_effort"] == "xhigh"
        assert config["configuration"]["azure_connection"]["route_profile"] == "direct-v1"
        assert config["configuration"]["fixed_settings"]["exec_run_open"] is False
        assert config["configuration"]["cost"] == {"chosen_settings": {
            "tool_calls_per_attempt": 8, "max_output_tokens_per_turn": 8192,
        }}
        assert config["configuration"]["profile"] == {
            "tool_contract_version": "2.0", "policy_profile_id": "offline-full-v1", "foundation_only": True,
        }
        assert "approved_maximum_usd" not in (output / prospective.HANDOFF_CONFIG).read_text()
    else:
        assert config["factory"] == "core.codex_runner.CodexAgentRunner"
        assert payload["kind"] == "codex_run_arguments"
        assert payload["arguments"]["task_prompt"] == seed.rows[task_index]["prompt"]
        assert payload["arguments"]["run_id"] == arguments["run_id"]
        typed = ExperimentConfig.from_dict(config["configuration"])
        assert typed.validate() == []
        assert config["configuration"]["data"]["filter"]["task_ids"] == [arguments["task_id"]]
        assert config["configuration"]["execution"]["max_retries"] == 0
        assert config["configuration"]["execution"]["resume_max_rounds"] == 0
        assert config["configuration"]["execution"]["codex"]["reasoning_effort"] == "xhigh"
        assert config["configuration"]["execution"]["timeout"] == 1200
    selected = seed.rows[task_index]["reference_files"]
    assert set(marker["files"]) == {prospective.HANDOFF_CONFIG, prospective.HANDOFF_TASK, *selected}
    assert {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()} == {
        *marker["files"], prospective.HANDOFF_READY,
    }
    for name, identity in marker["files"].items():
        assert identity == _identity((output / name).read_bytes())
        assert (output / name).stat().st_nlink == 1
    assert "rubric" not in (output / prospective.HANDOFF_TASK).read_text()
    assert "synthetic-withheld-answer" not in (output / prospective.HANDOFF_TASK).read_text()
    assert not (output / "data").exists() and not (output / "workspace").exists()
    assert marker["launch_authority"] == compiled.as_dict()["launch_authority"]
    assert marker["launch_authority"]["launch_allowed"] is marker["launch_authority"]["execution_enabled"] is False
    with pytest.raises(ComparisonRuntimeLaunchRefused, match="^comparison_runtime_launch_refused$"):
        require_comparison_runtime_launch()
    before = {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}
    with pytest.raises(prospective.TimeBudgetPreparationRefused, match="^handoff_or_reservation_exists$"):
        prospective.prepare_observation_handoff(seed.plan, **arguments)
    assert before == {path: path.read_bytes() for path in output.rglob("*") if path.is_file()}


@pytest.mark.parametrize("case", [
    "wrong_preparation", "missing_preparation", "malformed_size", "unknown_run", "cross_task",
    "missing_runtime_anchor", "wrong_runtime_anchor", "swapped_roots", "wrong_input_anchor",
    "different_input_locator", "input_drift", "codex_step0_drift", "v2_step0_forbidden",
    "marker_bytes", "marker_duplicate_key", "coherent_other_observation", "coherent_source",
    "config_factory", "control_identity", "duplicate_reference", "member_size",
    "reference_bytes", "reservation_binding", "extra_file", "extra_directory", "missing_member",
    "symlink_member", "hardlink_member", "path_alias", "partial", "used",
])
def test_time_budget_handoff_consumer_refuses_before_effects(handoff_sources, dual_roots, tmp_path, monkeypatch, case):
    from gpt54_prepared_input_attestation import _identity

    seed = handoff_sources
    condition = "codex" if case == "codex_step0_drift" else "sandbox_v2"
    marker, arguments = _consumer_arguments(seed, tmp_path, condition=condition)
    output = arguments["preparation_directory"]
    reservation = output.with_name(output.name + prospective.HANDOFF_RESERVATION_SUFFIX)
    ready = output / prospective.HANDOFF_READY
    effects = _consumer_no_effects(monkeypatch, arguments)
    restore = []

    def replace_bytes(path, data):
        restore.append((path, path.read_bytes()))
        path.write_bytes(data)

    def rebind_marker(*, new_external_expectation=False):
        raw = historical._canonical_json(marker).encode()
        ready.write_bytes(raw)
        reservation.write_bytes(historical._canonical_json({
            "reservation_version": "gpt54-time-budget-preparation-reservation-v1",
            "intended_preparation": _identity(raw), "ready_path": prospective.HANDOFF_READY,
        }).encode())
        if new_external_expectation:
            # Deliberately declare an invalid preparation as the caller's
            # expectation: an external digest alone cannot waive semantics.
            arguments["expected_preparation_identity"] = _identity(raw)

    if case == "wrong_preparation":
        arguments["expected_preparation_identity"]["sha256"] = "0" * 64
    elif case == "missing_preparation":
        arguments["expected_preparation_identity"] = None
    elif case == "malformed_size":
        arguments["expected_preparation_identity"]["size"] = True
    elif case == "unknown_run":
        arguments["run_id"] = "outside-study"
    elif case == "cross_task":
        arguments["task_id"] = seed.task_ids[1]
    elif case == "missing_runtime_anchor":
        arguments["expected_reviewed_source_sha"] = None
    elif case == "wrong_runtime_anchor":
        arguments["expected_reviewed_source_sha"] = "0" * 40
    elif case == "swapped_roots":
        arguments["runtime_root"], arguments["frozen_grader_root"] = seed.frozen, seed.runtime
    elif case == "wrong_input_anchor":
        arguments["expected_input_source_sha"] = seed.runtime_sha
    elif case == "different_input_locator":
        arguments["input_registration_path"] = seed.input_only_role
    elif case == "input_drift":
        replace_bytes(seed.parquet, seed.parquet.read_bytes() + b"synthetic drift")
    elif case == "codex_step0_drift":
        replace_bytes(seed.step0, seed.step0.read_bytes() + b" ")
    elif case == "v2_step0_forbidden":
        arguments["step0_manifest"] = tmp_path / "must-never-read-step0"
    elif case == "marker_bytes":
        ready.write_bytes(ready.read_bytes() + b" ")
    elif case == "marker_duplicate_key":
        raw = b'{"preparation_version":"duplicate",' + ready.read_bytes()[1:]
        ready.write_bytes(raw)
        arguments["expected_preparation_identity"] = _identity(raw)
    elif case == "coherent_other_observation":
        preparation = _handoff_arguments(seed, tmp_path, task_index=1)
        preparation["destination"] = output.with_name("other-observation")
        prospective.prepare_observation_handoff(seed.plan, **preparation)
        output.rename(output.with_name("saved-original"))
        preparation["destination"].rename(output)
        other_reservation = preparation["destination"].with_name(
            preparation["destination"].name + prospective.HANDOFF_RESERVATION_SUFFIX)
        reservation.write_bytes(other_reservation.read_bytes())
        # A complete genuinely prepared replacement still lacks the caller's
        # independent original expectation. No hand-edited partial fixture.
    elif case == "coherent_source":
        arguments["runtime_root"] = dual_roots["substitute"]
        marker["runtime_source"]["source_sha"] = dual_roots["substitute_sha"]
        marker["observation"]["reviewed_source_sha"] = dual_roots["substitute_sha"]
        marker["observation_control"]["identity"] = deepcopy(marker["observation"])
        configuration = json.loads((output / prospective.HANDOFF_CONFIG).read_bytes())
        configuration["observation_control"]["identity"] = deepcopy(marker["observation"])
        raw = historical._canonical_json(configuration).encode()
        (output / prospective.HANDOFF_CONFIG).write_bytes(raw)
        marker["files"][prospective.HANDOFF_CONFIG] = _identity(raw)
        rebind_marker(new_external_expectation=True)
        # The independently expected R anchor remains the genuine original,
        # so the actual replacement Git HEAD must refuse before input effects.
    elif case in ("config_factory", "control_identity", "duplicate_reference"):
        name = prospective.HANDOFF_TASK if case == "duplicate_reference" else prospective.HANDOFF_CONFIG
        changed = json.loads((output / name).read_bytes())
        if case == "config_factory":
            changed["factory"] = "subprocess.Popen"
        elif case == "control_identity":
            changed["observation_control"]["identity"]["task_id"] = seed.task_ids[1]
            marker["observation_control"] = deepcopy(changed["observation_control"])
        else:
            changed["arguments"]["reference_files"] *= 2
            changed["reference_file_records"] *= 2
        raw = historical._canonical_json(changed).encode()
        (output / name).write_bytes(raw)
        marker["files"][name] = _identity(raw)
        rebind_marker(new_external_expectation=True)
    elif case == "member_size":
        marker["files"][prospective.HANDOFF_CONFIG]["size"] += 1
        rebind_marker(new_external_expectation=True)
    elif case == "reference_bytes":
        (output / marker["inputs"]["reference_file_records"][0]["path"]).write_bytes(b"synthetic alteration")
    elif case == "reservation_binding":
        value = json.loads(reservation.read_bytes())
        value["intended_preparation"]["sha256"] = "0" * 64
        reservation.write_bytes(historical._canonical_json(value).encode())
    elif case == "extra_file":
        (output / "unregistered.txt").write_bytes(b"extra")
    elif case == "extra_directory":
        (output / "unregistered").mkdir()
    elif case == "missing_member":
        (output / prospective.HANDOFF_CONFIG).unlink()
    elif case == "symlink_member":
        config = output / prospective.HANDOFF_CONFIG
        saved = tmp_path / "external-config.json"
        config.rename(saved)
        config.symlink_to(saved)
    elif case == "hardlink_member":
        os.link(output / prospective.HANDOFF_CONFIG, tmp_path / "aliased-config.json")
    elif case == "path_alias":
        alias = tmp_path / "aliased-handoff"
        alias.symlink_to(output, target_is_directory=True)
        arguments["preparation_directory"] = alias
    elif case == "partial":
        ready.unlink()
    elif case == "used":
        _consumer_claim(arguments).write_bytes(b"partial consumption; do not adopt")
    else:
        raise AssertionError(case)

    try:
        with pytest.raises(prospective.TimeBudgetRegistrationRefused) as error:
            prospective.consume_observation_handoff(seed.plan, **arguments)
        assert "direction" not in str(error.value), "a negative must reach its real identity/member refusal"
        assert effects == []
        assert list(arguments["observation_directory"].iterdir()) == []
        if case == "used":
            assert _consumer_claim(arguments).read_bytes() == b"partial consumption; do not adopt"
        else:
            assert not _consumer_claim(arguments).exists()
    finally:
        for path, data in restore:
            path.write_bytes(data)


@pytest.mark.parametrize("race", ["marker", "reservation", "reference", "parent", "runtime", "input"])
def test_time_budget_handoff_consumer_final_rereads(handoff_sources, tmp_path, monkeypatch, race):
    import shutil

    seed = handoff_sources
    marker, arguments = _consumer_arguments(seed, tmp_path)
    output = arguments["preparation_directory"]
    effects = _consumer_no_effects(monkeypatch, arguments)
    restore = []

    def direction(binding):
        effects.append("direction")
        assert json.loads(binding.observation_json) == marker["observation"]
        if race == "parent":
            moved = output.with_name("moved-held-handoff")
            output.rename(moved)
            shutil.copytree(moved, output)
            return
        target = {
            "marker": output / prospective.HANDOFF_READY,
            "reservation": output.with_name(output.name + prospective.HANDOFF_RESERVATION_SUFFIX),
            "reference": output / marker["inputs"]["reference_file_records"][0]["path"],
            "runtime": seed.runtime / "batch-runner/core/codex_runner.py",
            "input": seed.parquet,
        }[race]
        restore.append((target, target.read_bytes()))
        target.write_bytes(target.read_bytes() + b"\n# synthetic final-reread drift\n")

    arguments["require_execution_direction"] = direction
    try:
        with pytest.raises(prospective.TimeBudgetRegistrationRefused):
            prospective.consume_observation_handoff(seed.plan, **arguments)
        assert effects == ["direction"] and not _consumer_claim(arguments).exists()
        assert list(arguments["observation_directory"].iterdir()) == []
    finally:
        for path, data in restore:
            path.write_bytes(data)


@pytest.mark.parametrize("case,reason", [
    ("unknown_run", "exactly_one_registered_observation_required"),
    ("old_run", "exactly_one_registered_observation_required"),
    ("unknown_task", "exactly_one_registered_observation_required"),
    ("duplicate_selection", "exactly_one_registered_observation_required"),
    ("duplicate_runs", "repetition_matrix"),
    ("duplicate_tasks", "shared_facts"),
    ("launch_toggle", "launch_enabled"),
    ("missing_runtime_anchor", "explicit_source_and_input_anchors_required"),
    ("missing_input_anchor", "explicit_source_and_input_anchors_required"),
    ("input_ref_not_sha", "review_anchor_must_be_full_commit"),
    ("runtime_ref_not_sha", "review_anchor_must_be_full_commit"),
    ("wrong_frozen_anchor", "frozen_grader_review_anchor"),
    ("wrong_runtime_anchor", "observation_handoff_refused"),
    ("swapped_roots", "observation_handoff_refused"),
    ("wrong_input_anchor", "observation_handoff_refused"),
    ("input_facts_disagree", "input_registration_dataset"),
    ("external_input_locator", "observation_handoff_refused"),
    ("traversal_input_locator", "observation_handoff_refused"),
    ("output_traversal", "handoff_parent_traversal"),
    ("output_source_overlap", "handoff_source_overlap"),
    ("v2_step0_supplied", "condition_specific_step0_required"),
    ("codex_step0_missing", "condition_specific_step0_required"),
])
def test_time_budget_observation_handoff_invalid_selection_and_anchors(handoff_sources, tmp_path, case, reason):
    seed = handoff_sources
    plan = deepcopy(seed.plan)
    arguments = _handoff_arguments(seed, tmp_path, condition="codex" if case == "codex_step0_missing" else "sandbox_v2")
    if case in ("unknown_run", "old_run"):
        arguments["run_id"] = "not-registered" if case == "unknown_run" else "gpt54_v2_codex_v1_v2_r1"
    elif case == "unknown_task":
        arguments["task_id"] = "not-registered"
    elif case == "duplicate_selection":
        arguments["task_id"] = [seed.task_ids[0], seed.task_ids[0]]
    elif case == "duplicate_runs":
        plan["runs"].append(deepcopy(plan["runs"][0]))
    elif case == "duplicate_tasks":
        plan["shared"]["dataset"]["tasks"].append(deepcopy(plan["shared"]["dataset"]["tasks"][0]))
    elif case == "launch_toggle":
        plan["launch_enabled"] = True
    elif case.startswith("missing_"):
        arguments["expected_reviewed_source_sha" if case == "missing_runtime_anchor" else "expected_input_source_sha"] = None
    elif case in ("input_ref_not_sha", "runtime_ref_not_sha"):
        arguments["expected_input_source_sha" if case == "input_ref_not_sha" else "expected_reviewed_source_sha"] = "HEAD"
    elif case == "wrong_frozen_anchor":
        arguments["expected_grader_source_sha"] = seed.runtime_sha
    elif case == "wrong_runtime_anchor":
        arguments["expected_reviewed_source_sha"] = "0" * 40
    elif case == "wrong_input_anchor":
        arguments["expected_input_source_sha"] = "0" * 40
    elif case == "swapped_roots":
        arguments.update(runtime_root=seed.frozen, frozen_grader_root=seed.runtime)
    elif case == "input_facts_disagree":
        arguments["input_registration_path"] = seed.mismatch_role
    elif case == "external_input_locator":
        arguments["input_registration_path"] = str(seed.frozen / prospective.SOURCE_PROFILE)
    elif case == "traversal_input_locator":
        arguments["input_registration_path"] = historical.ENVELOPE + "../execution_envelope/gpt54_sandboxv2_codex_comparison_local_source.yaml"
    elif case == "output_traversal":
        arguments["destination"] = arguments["destination"].parent / ".." / "escape"
    elif case == "output_source_overlap":
        arguments["destination"] = seed.runtime / "forbidden-handoff"
    elif case == "v2_step0_supplied":
        arguments["step0_manifest"] = tmp_path / "do-not-open-step0"
    else:
        arguments["step0_manifest"] = None
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match=f"^{reason}$"):
        prospective.prepare_observation_handoff(plan, **arguments)
    _assert_unpublished(arguments)


@pytest.mark.parametrize("case", [
    "parquet_digest", "reference_digest", "step0_digest", "runtime_blob", "frozen_blob",
    "input_registration_blob", "untracked_input_locator", "input_locator_symlink", "parquet_hardlink",
    "reference_symlink", "output_symlink", "reserved_partial", "existing_destination",
])
def test_time_budget_observation_handoff_tamper_and_clobber(handoff_sources, tmp_path, case):
    seed = handoff_sources
    reference_index = next(index for index, row in enumerate(seed.rows) if row["reference_files"])
    arguments = _handoff_arguments(
        seed, tmp_path, condition="codex" if case == "step0_digest" else "sandbox_v2",
        task_index=reference_index if case in ("reference_digest", "reference_symlink") else 0,
    )
    output = arguments["destination"]
    reservation = output.with_name(output.name + prospective.HANDOFF_RESERVATION_SUFFIX)
    target, original, extra = None, None, None
    if case in ("parquet_digest", "parquet_hardlink"):
        target = seed.parquet
    elif case in ("reference_digest", "reference_symlink"):
        target = seed.references / seed.rows[reference_index]["reference_files"][0]
    elif case == "step0_digest":
        target = seed.step0
    elif case == "runtime_blob":
        target = seed.runtime / "batch-runner/core/codex_runner.py"
    elif case == "frozen_blob":
        target = seed.frozen / historical.GRADER
    elif case in ("input_registration_blob", "input_locator_symlink"):
        # The explicit alternate locator is tracked but isn't in F's grader
        # closure/profile, so refusal exercises the actual input-source stage.
        target = seed.frozen / seed.input_only_role
        arguments["input_registration_path"] = seed.input_only_role
    if target is not None:
        original = target.read_bytes()
    try:
        if case == "parquet_hardlink":
            extra = tmp_path / "parquet-alias"
            os.link(target, extra)
        elif case in ("reference_symlink", "input_locator_symlink"):
            extra = tmp_path / "external-target"
            extra.write_bytes(original)
            target.unlink()
            target.symlink_to(extra)
        elif target is not None:
            target.write_bytes(original + b"\nchanged\n")
        elif case == "untracked_input_locator":
            extra = seed.frozen / historical.ENVELOPE / "untracked-input.yaml"
            extra.write_bytes((seed.frozen / prospective.SOURCE_PROFILE).read_bytes())
            arguments["input_registration_path"] = extra.relative_to(seed.frozen).as_posix()
        elif case == "output_symlink":
            extra = tmp_path / "external-output"
            extra.mkdir()
            output.symlink_to(extra, target_is_directory=True)
        elif case == "reserved_partial":
            reservation.write_bytes(b"retained incomplete reservation")
        else:
            output.mkdir()
            (output / "owned-by-someone-else").write_bytes(b"untouched")
        with pytest.raises(prospective.TimeBudgetRegistrationRefused):
            prospective.prepare_observation_handoff(seed.plan, **arguments)
        assert not (output / prospective.HANDOFF_READY).exists()
        if case == "reserved_partial":
            assert reservation.read_bytes() == b"retained incomplete reservation"
        elif case == "existing_destination":
            assert (output / "owned-by-someone-else").read_bytes() == b"untouched"
        elif case == "output_symlink":
            assert list(extra.iterdir()) == []
        else:
            _assert_unpublished(arguments)
    finally:
        if target is not None:
            if target.is_symlink():
                target.unlink()
            target.write_bytes(original)
        if extra is not None and extra.is_file():
            extra.unlink()


@pytest.mark.parametrize("case", [
    "parquet", "reference", "step0", "runtime_source", "input_source", "installed_config", "parent_swap",
])
def test_time_budget_observation_handoff_final_rereads_quarantine(handoff_sources, tmp_path, monkeypatch, case):
    import ghcp_vm_input_bundle as publication

    seed = handoff_sources
    reference_index = next(index for index, row in enumerate(seed.rows) if row["reference_files"])
    arguments = _handoff_arguments(seed, tmp_path, condition="codex" if case == "step0" else "sandbox_v2",
                                   task_index=reference_index)
    output = arguments["destination"]
    target = {
        "parquet": seed.parquet, "reference": seed.references / seed.rows[reference_index]["reference_files"][0],
        "step0": seed.step0, "runtime_source": seed.runtime / "batch-runner/core/codex_runner.py",
        "input_source": seed.frozen / prospective.SOURCE_PROFILE,
        "installed_config": output / prospective.HANDOFF_CONFIG,
    }.get(case)
    original = None if target is None or case == "installed_config" else target.read_bytes()
    write = publication._write_no_clobber
    changed = []

    def race(path, data, *, parent_fd):
        write(path, data, parent_fd=parent_fd)
        if path.name == prospective.HANDOFF_TASK and not changed:
            changed.append(True)
            if case == "parent_swap":
                output.rename(output.with_name("held-original-output"))
                output.mkdir()
            else:
                target.write_bytes(target.read_bytes() + b"\nchanged after member publication\n")

    monkeypatch.setattr(publication, "_write_no_clobber", race)
    try:
        with pytest.raises(prospective.TimeBudgetRegistrationRefused):
            prospective.prepare_observation_handoff(seed.plan, **arguments)
        assert changed == [True]  # A negative must reach the valid publication boundary.
        assert not (output / prospective.HANDOFF_READY).exists()
        assert not (output.with_name("held-original-output") / prospective.HANDOFF_READY).exists()
        reservation = output.with_name(output.name + prospective.HANDOFF_RESERVATION_SUFFIX)
        assert reservation.is_file()
        before = reservation.read_bytes()
        with pytest.raises(prospective.TimeBudgetPreparationRefused, match="^handoff_or_reservation_exists$"):
            prospective.prepare_observation_handoff(seed.plan, **arguments)
        assert reservation.read_bytes() == before
    finally:
        if original is not None:
            target.write_bytes(original)


def test_time_budget_observation_handoff_v2_never_reads_step0_and_stays_closed(handoff_sources, tmp_path, monkeypatch):
    from core import repo_bootstrapper

    def forbidden(*args, **kwargs):
        pytest.fail("V2 attempted a Codex-only canonical Step0 read")

    monkeypatch.setattr(repo_bootstrapper, "require_canonical_manifest_bytes", forbidden)
    for name in ("TIME_BUDGET_LAUNCH_ENABLED", "COMPARISON_LAUNCH_ALLOWED", "EXPECTED_REVIEWED_SOURCE_SHA"):
        monkeypatch.setenv(name, "true")
    seed = handoff_sources
    arguments = _handoff_arguments(seed, tmp_path)
    marker = prospective.prepare_observation_handoff(seed.plan, **arguments)
    assert marker["inputs"]["step0_manifest"] is None
    assert marker["launch_authority"]["launch_allowed"] is False
    assert marker["observation_control"]["admission_reserved"] is False
    with pytest.raises(ComparisonRuntimeLaunchRefused, match="^comparison_runtime_launch_refused$"):
        require_comparison_runtime_launch()
    with pytest.raises(prospective.TimeBudgetRegistrationRefused, match="^manifest_fields$"):
        prospective.compile_registration(seed.plan)
    assert hashlib.sha256(historical.PLAN.read_bytes()).hexdigest() == (
        "3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1"
    )
    assert hashlib.sha256((historical.ROOT / prospective.SOURCE_PROFILE).read_bytes()).hexdigest() == (
        "81b9930102a19f298dfbb5e45c8f0d39045b89512aa5dc9b4d5543312835cbbe"
    )


@pytest.mark.parametrize("condition", ["sandbox_v2", "codex"])
def test_time_budget_observation_handoff_valid_reference_payload(handoff_sources, tmp_path, condition):
    """A reference-bearing baseline, separate from the four no-reference proofs."""
    from gpt54_prepared_input_attestation import _identity

    seed = handoff_sources
    index = next(index for index, row in enumerate(seed.rows) if row["reference_files"])
    assert seed.rows[index]["task_id"] == "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"
    arguments = _handoff_arguments(seed, tmp_path, condition=condition, task_index=index)
    marker = prospective.prepare_observation_handoff(seed.plan, **arguments)
    output = arguments["destination"]
    names = seed.rows[index]["reference_files"]
    assert names and marker["observation"]["task_id"] == seed.rows[index]["task_id"]
    assert set(marker["files"]) == {prospective.HANDOFF_CONFIG, prospective.HANDOFF_TASK, *names}
    payload = json.loads((output / prospective.HANDOFF_TASK).read_bytes())
    assert payload["arguments"]["reference_files"] == names
    assert payload["reference_file_records"] == [{"path": name, **seed.records[name]} for name in names]
    assert marker["inputs"]["reference_file_records"] == payload["reference_file_records"]
    for name in names:
        assert (output / name).read_bytes() == (seed.references / name).read_bytes()
        assert marker["files"][name] == _identity((output / name).read_bytes())
        assert (output / name).stat().st_nlink == 1 and not (output / name).is_symlink()
    assert {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()} == {
        *marker["files"], prospective.HANDOFF_READY,
    }
    assert json.loads((output / prospective.HANDOFF_READY).read_bytes()) == marker
    assert marker["launch_authority"]["launch_allowed"] is False
    with pytest.raises(ComparisonRuntimeLaunchRefused, match="^comparison_runtime_launch_refused$"):
        require_comparison_runtime_launch()


def _consumer_arguments(seed, tmp_path, *, condition="sandbox_v2", task_index=2):
    """Retain the preparer's returned identity independently, before mutations."""
    from gpt54_prepared_input_attestation import _identity

    preparation = _handoff_arguments(seed, tmp_path, condition=condition, task_index=task_index)
    marker = prospective.prepare_observation_handoff(seed.plan, **preparation)
    expected = _identity(historical._canonical_json(marker).encode())
    store = tmp_path / "consumer-observations"
    store.mkdir(mode=0o700)
    arguments = {name: value for name, value in preparation.items() if name != "destination"}
    arguments.update(preparation_directory=preparation["destination"], expected_preparation_identity=expected,
                     observation_directory=store)
    return marker, arguments


def _consumer_claim(arguments):
    output = arguments["preparation_directory"]
    return output.with_name(output.name + prospective.HANDOFF_CONSUMED_SUFFIX)


def _consumer_no_effects(monkeypatch, arguments):
    from core.time_budget_observation_deadline import TimeBudgetObservation

    effects = []

    def forbidden(*args, **kwargs):
        effects.append("effect")
        pytest.fail("consumer reached admission/provider/factory before validation/direction")

    monkeypatch.setattr(TimeBudgetObservation, "__init__", forbidden)
    arguments["require_execution_direction"] = lambda binding: effects.append("direction")
    if "_codex_" in arguments["run_id"]:
        arguments["codex_provider_for"] = forbidden
    else:
        arguments.update(v2_backend_factory=forbidden, v2_voice_for=forbidden)
    return effects


@pytest.mark.parametrize("condition", ["sandbox_v2", "codex"])
@pytest.mark.parametrize("direction", ["missing", "boolean", "denied", "approval_bit"])
def test_time_budget_handoff_consumer_direction_is_independent(
    handoff_sources, tmp_path, monkeypatch, condition, direction,
):
    _, arguments = _consumer_arguments(handoff_sources, tmp_path, condition=condition)
    effects = _consumer_no_effects(monkeypatch, arguments)
    if direction == "missing":
        arguments.pop("require_execution_direction")
    elif direction == "boolean":
        arguments["require_execution_direction"] = True
    elif direction == "approval_bit":
        arguments["require_execution_direction"] = lambda binding: True
    else:
        def refuse(binding):
            raise prospective.TimeBudgetConsumptionRefused("independent_direction_denied")
        arguments["require_execution_direction"] = refuse
    with pytest.raises(prospective.TimeBudgetConsumptionRefused, match="direction"):
        prospective.consume_observation_handoff(handoff_sources.plan, **arguments)
    assert effects == [] and not _consumer_claim(arguments).exists()
    assert list(arguments["observation_directory"].iterdir()) == []


@pytest.mark.parametrize("condition,task_index", [
    ("sandbox_v2", 0), ("sandbox_v2", 2), ("codex", 0), ("codex", 2),
])
def test_time_budget_handoff_consumer_real_factory_binding(
    handoff_sources, tmp_path, monkeypatch, observation_kernel, condition, task_index,
):
    import core.agentic_v2_conversation_runner as v2
    import core.codex_runner as native
    import core.time_budget_observation_deadline as deadline
    from core.agentic_v2_conversation import AskForTool
    from core.codex_runtime_config import CodexProviderLike
    from core.reference_integrity import VerifiedReferencePath

    seed = handoff_sources
    marker, arguments = _consumer_arguments(seed, tmp_path, condition=condition, task_index=task_index)
    configuration = json.loads((arguments["preparation_directory"] / prospective.HANDOFF_CONFIG).read_bytes())
    payload = json.loads((arguments["preparation_directory"] / prospective.HANDOFF_TASK).read_bytes())
    clock, events, controls, actual_arguments = _Clock(), [], [], []
    original_init = deadline.TimeBudgetObservation.__init__
    original_build = v2.build_runner_factory

    def admit(control, directory, identity):
        assert events == ["direction"] and _consumer_claim(arguments).is_file()
        assert json.loads(_consumer_claim(arguments).read_bytes())["observation"] == marker["observation"]
        assert identity == deadline.ObservationIdentity(**marker["observation"])
        original_init(control, directory, identity, clock=clock)
        controls.append(control)
        events.append("admission")
        assert control.first_start is None

    def direction(binding):
        assert not _consumer_claim(arguments).exists()
        assert list(arguments["observation_directory"].iterdir()) == []
        assert binding == prospective.ObservationExecutionBinding(
            arguments["expected_preparation_identity"]["sha256"], arguments["expected_preparation_identity"]["size"],
            historical._canonical_json(marker["observation"]), seed.frozen_sha, seed.frozen_tree,
            prospective.FROZEN_TEMPLATE_SHA256, str(arguments["preparation_directory"]),
            str(arguments["observation_directory"]),
        )
        with pytest.raises(FrozenInstanceError):
            binding.preparation_sha256 = "0" * 64
        events.append("direction")
        clock.advance(2000)

    def check_references(references):
        assert len(references) == len(payload["reference_file_records"])
        for value, record in zip(references, payload["reference_file_records"]):
            assert type(value) is VerifiedReferencePath
            assert value.declared_path == record["path"]
            assert (value.sha256, value.size) == (record["sha256"], record["size"])
            assert Path(value) == arguments["preparation_directory"] / record["path"]
            assert hashlib.sha256(Path(value).read_bytes()).hexdigest() == value.sha256

    monkeypatch.setattr(deadline.TimeBudgetObservation, "__init__", admit)
    arguments["require_execution_direction"] = direction
    if condition == "sandbox_v2":
        monkeypatch.setattr(_FIXTURE_BACKEND, "__init__", _FIXTURE_BACKEND_INIT)

        class Backend(_FIXTURE_BACKEND):
            def start(self, timeout):
                assert controls[0]._claimed and controls[0].first_start is None
                events.append("backend_start")
                clock.advance(500)
                return super().start(timeout)

        class Voice:
            makes_paid_calls = False

            def next_turn(self, request):
                control = controls[0]
                assert control.first_start == 2600 and control._claimed
                events.append("generation")
                clock.advance(0.25)
                if request.turn == 1:
                    return AskForTool("write", "workspace_apply", {
                        "operation": "write", "path": "report.txt", "content": "synthetic consumer result",
                    }, input_tokens=20, output_tokens=10)
                return AskForTool("finalize", "finalize", {
                    "deliverables": ["report.txt"], "summary": "synthetic consumer result",
                }, input_tokens=30, output_tokens=15)

        def voice_for(config, budget):
            assert config == configuration["configuration"]
            assert config["model"]["reasoning_effort"] == "xhigh"
            assert config["fixed_settings"]["retry_max_attempts"] == 1
            assert budget.max_model_calls == 9 and budget.model_calls_made == 0
            assert controls[0].first_start is None
            events.append("voice_factory")
            return Voice()

        def build(**kwargs):
            control = controls[0]
            assert kwargs["observation_for"](arguments["task_id"], 1) is control
            for task, attempt in ((seed.task_ids[1], 1), (arguments["task_id"], 2), (arguments["task_id"], True)):
                with pytest.raises(prospective.TimeBudgetConsumptionRefused, match="observation_factory_selection"):
                    kwargs["observation_for"](task, attempt)
            assert events == ["direction", "admission"]
            events.append("v2_factory")
            real_factory = original_build(**kwargs)

            def for_task(task):
                assert task.prompt == seed.rows[task_index]["prompt"]
                check_references(task.reference_files)
                runner = real_factory(task)
                assert runner.observation_control is control
                original_run = runner.run

                def run(**values):
                    actual_arguments.append(values)
                    return original_run(**values)

                runner.run = run
                return runner

            return for_task

        monkeypatch.setattr(v2, "build_runner_factory", build)
        arguments.update(v2_backend_factory=lambda **kw: Backend(root=tmp_path / "synthetic-backend", **kw),
                         v2_voice_for=voice_for)
    else:
        class Provider(CodexProviderLike):
            def __init__(self, config):
                self.__dict__.update(config["execution"]["codex"])

        def provider_for(config):
            assert config == configuration["configuration"]
            assert config["data"]["filter"]["task_ids"] == [arguments["task_id"]]
            assert config["execution"]["max_retries"] == config["execution"]["resume_max_rounds"] == 0
            assert controls[0].first_start is None and not controls[0]._claimed
            events.append("provider_factory")
            return Provider(config)

        def build(provider, **kwargs):
            assert kwargs == {"timeout": 1200, "run_id": arguments["run_id"], "condition_name": "codex",
                              "observation_control": controls[0]}
            events.append("codex_factory")
            runner = _REAL_CODEX_RUNNER(provider, **kwargs)
            assert runner.observation_control is controls[0] and runner.preflight_auth is True

            def transport(**values):
                control = controls[0]
                assert control._claimed and control.first_start is None
                actual_arguments.append(values)
                check_references(values["reference_files"])
                # Only the native transport is substituted. The real run()
                # claims and finalizes the genuine control around this adapter.
                with control.supervise():
                    control.start()
                    events.append("generation")
                    clock.advance(0.5)
                    control.check_generation()
                return {"success": True, "synthetic_transport": True}

            monkeypatch.setattr(runner, "_run", transport)
            return runner

        monkeypatch.setattr(native, "require_pinned_runtime", lambda: events.append("runtime_version_seam"))
        monkeypatch.setattr(native, "CodexAgentRunner", build)
        arguments["codex_provider_for"] = provider_for

    result = prospective.consume_observation_handoff(seed.plan, **arguments)
    assert result["success"] is True
    assert result["handoff_preparation_identity"] == arguments["expected_preparation_identity"]
    assert result["time_budget_observation"] == controls[0].as_record()
    assert controls[0].identity == deadline.ObservationIdentity(**marker["observation"])
    assert controls[0].terminal_reason == "completed" and controls[0].cleanup_complete is True
    assert result["time_budget_observation"]["remote_cancellation_confirmed"] is False
    assert result["time_budget_observation"]["generation_elapsed_seconds"] == 0.5
    assert len(actual_arguments) == 1
    values = actual_arguments[0]
    assert values["task_prompt"] == seed.rows[task_index]["prompt"]
    assert (values["run_id"], values["condition_name"], values["task_id"]) == (
        arguments["run_id"], condition, arguments["task_id"],
    )
    assert "rubric" not in json.dumps(values) and "withheld" not in json.dumps(values)
    if condition == "codex":
        assert values["model"] == "gpt-5.4"
        assert values["experiment_prompt"] == payload["arguments"]["experiment_prompt"]
    before = list(events)
    with pytest.raises(prospective.TimeBudgetConsumptionRefused, match="already_consumed"):
        prospective.consume_observation_handoff(seed.plan, **arguments)
    with pytest.raises(deadline.ObservationDeadlineRefused):
        original_init(object.__new__(deadline.TimeBudgetObservation), arguments["observation_directory"],
                      controls[0].identity, clock=clock)
    assert events == before
    assert _consumer_claim(arguments).is_file()
    assert not (arguments["observation_directory"] / "host-lease.json").exists()
    with pytest.raises(ComparisonRuntimeLaunchRefused):
        require_comparison_runtime_launch()
    assert marker["launch_authority"]["launch_allowed"] is marker["launch_authority"]["execution_enabled"] is False


@pytest.mark.parametrize("condition", ["sandbox_v2", "codex"])
def test_time_budget_handoff_consumer_failed_factory_is_nonrenewable(
    handoff_sources, tmp_path, monkeypatch, observation_kernel, condition,
):
    import core.time_budget_observation_deadline as deadline

    marker, arguments = _consumer_arguments(handoff_sources, tmp_path, condition=condition)
    controls, effects, clock = [], [], _Clock()
    original_init = deadline.TimeBudgetObservation.__init__

    def admit(control, directory, identity):
        original_init(control, directory, identity, clock=clock)
        controls.append(control)

    def failure(*args):
        effects.append("factory")
        assert controls[0].first_start is None
        raise RuntimeError("synthetic factory construction failure")

    def backend(**kwargs):
        pytest.fail("backend must not precede voice construction")

    monkeypatch.setattr(deadline.TimeBudgetObservation, "__init__", admit)
    arguments["require_execution_direction"] = lambda binding: None
    if condition == "sandbox_v2":
        arguments.update(v2_backend_factory=backend, v2_voice_for=failure)
    else:
        arguments["codex_provider_for"] = failure
    with pytest.raises(RuntimeError, match="synthetic factory construction failure"):
        prospective.consume_observation_handoff(handoff_sources.plan, **arguments)
    assert effects == ["factory"] and controls[0].first_start is None
    assert controls[0].terminal_reason == "failed" and controls[0]._finished
    assert controls[0].cleanup_complete
    assert json.loads((controls[0].directory / (controls[0].identity.key + ".admitted.json")).read_bytes()) == marker["observation"]
    assert _consumer_claim(arguments).is_file()
    with pytest.raises(prospective.TimeBudgetConsumptionRefused, match="already_consumed"):
        prospective.consume_observation_handoff(handoff_sources.plan, **arguments)
    assert effects == ["factory"]


@pytest.mark.parametrize("condition", ["sandbox_v2", "codex"])
def test_time_budget_handoff_consumer_requires_condition_specific_dependencies(
    handoff_sources, tmp_path, monkeypatch, condition,
):
    _, arguments = _consumer_arguments(handoff_sources, tmp_path, condition=condition)
    effects = _consumer_no_effects(monkeypatch, arguments)
    if condition == "sandbox_v2":
        arguments["codex_provider_for"] = lambda config: pytest.fail("foreign provider")
    else:
        arguments["v2_backend_factory"] = lambda **kwargs: pytest.fail("foreign backend")
    with pytest.raises(prospective.TimeBudgetConsumptionRefused, match="condition_specific_factory_dependencies_required"):
        prospective.consume_observation_handoff(handoff_sources.plan, **arguments)
    assert effects == [] and not _consumer_claim(arguments).exists()
    assert list(arguments["observation_directory"].iterdir()) == []
