"""First-cell callable proof: real validators/factory, synthetic transport only."""

import json
import os
import socket
import subprocess
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt54_comparison_preflight as legacy
import gpt54_time_budget_comparison as registration
import gpt54_time_budget_grading_preparation as grading
import gpt54_time_budget_v2_observation as entry
from core import azure_ai_clients, agentic_v2_conversation_runner as conversation
from core import time_budget_observation_deadline as deadline
from core.agentic_v2_preregistration import seal
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_comparison_preflight import _canonical_json
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_time_budget_comparison import (
    _Clock, _handoff_arguments, dual_roots, handoff_source_seed, handoff_sources,
    observation_kernel,
)

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
_HOST = {"policy": "explicitly_synthetic_host_identity", "instance_sha256": "b" * 64,
         "ci_instance_sha256": None, "ownership_confirmed": False}


@pytest.fixture(autouse=True)
def offline(monkeypatch, handoff_sources, dual_roots, observation_kernel):
    from core import rubric_loader
    import step8_grade

    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("first-cell offline selector attempted an external effect")

    for owner, names in ((socket.socket, ("connect", "connect_ex")),
                         (socket, ("create_connection",)),
                         (subprocess, ("run", "Popen", "check_call", "check_output")),
                         (os, ("system",)),
                         (rubric_loader, ("snapshot_download", "hf_hub_download", "HfApi"))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr(step8_grade.Grader, "__init__", forbidden)
    monkeypatch.setattr(azure_ai_clients, "OpenAI", forbidden)
    monkeypatch.setattr(azure_ai_clients, "AzureOpenAI", forbidden)
    monkeypatch.setattr(azure_ai_clients, "DefaultAzureCredential", forbidden)
    monkeypatch.setattr(entry, "execution_host_identity", lambda source: dict(_HOST))
    for key in tuple(os.environ):
        if key.startswith(("AZURE_", "FOUNDRY_", "GITHUB_", "ACTIONS_", "HF_", "OPENAI_")):
            monkeypatch.delenv(key)
    monkeypatch.setenv(azure_ai_clients.ROUTE_PROFILE_ENV, "direct-v1")
    monkeypatch.setenv(azure_ai_clients.DIRECT_ENDPOINT_ENV,
                       "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/openai/v1/")
    monkeypatch.setenv(azure_ai_clients.PROJECT_ENDPOINT_ENV,
                       "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/gdpval-realworks")

    def local_git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        position = command.index("-C")
        assert Path(command[position + 1]) in {
            handoff_sources.runtime, handoff_sources.frozen,
            dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"],
        }
        assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", local_git)
    yield
    assert forbidden_calls == []


def _write_direction(case, value=None, *, trust=True):
    data = _canonical_json(case.direction if value is None else value).encode()
    case.arguments["direction_path"].write_bytes(data)
    if trust:
        case.arguments["expected_direction_sha256"] = _identity(data)["sha256"]


def _case(seed, tmp_path):
    handoff = _handoff_arguments(seed, tmp_path, task_index=0)
    marker = registration.prepare_observation_handoff(seed.plan, **handoff)
    prep = handoff.pop("destination")
    handoff.pop("step0_manifest")
    handoff.pop("run_id")
    handoff.pop("task_id")
    state = tmp_path / "owned-host-state"
    state.mkdir(mode=0o700)
    arguments = {**handoff, "observation": deadline.ObservationIdentity(**marker["observation"]),
                 "preparation_directory": prep, "expected_preparation_identity": _identity(_canonical_json(marker).encode()),
                 "observation_directory": state, "destination": tmp_path / "publications" / "result",
                 "direction_path": tmp_path / "synthetic-direction.json", "expected_host_sha256": _HOST["instance_sha256"]}
    # Independently declared synthetic authority, never produced by the
    # checker and never a mocked successful source/input/direction verdict.
    binding = registration.ObservationExecutionBinding(
        arguments["expected_preparation_identity"]["sha256"], arguments["expected_preparation_identity"]["size"],
        _canonical_json(marker["observation"]), seed.frozen_sha, seed.frozen_tree,
        registration.FROZEN_TEMPLATE_SHA256, str(prep), str(state))
    direction = {"direction_version": entry.DIRECTION_VERSION, "purpose": "execute_one_registered_observation",
                 "execution_binding": asdict(binding), "host_sha256": _HOST["instance_sha256"],
                 "not_before_unix": 0, "expires_unix": 4102444800,
                 "paths": {"direction": str(arguments["direction_path"]), "preparation": str(prep),
                     "runtime_root": str(seed.runtime), "frozen_grader_root": str(seed.frozen),
                     "input_registration_root": str(seed.frozen), "dataset_parquet": str(seed.parquet),
                     "reference_root": str(seed.references), "observation_directory": str(state),
                     "destination": str(arguments["destination"]), "input_source_sha": seed.frozen_sha,
                     "input_registration_path": registration.SOURCE_PROFILE,
                     "backend_workspace": str(arguments["destination"].with_name("result" + entry.WORK_SUFFIX))}}
    case = SimpleNamespace(arguments=arguments, marker=marker, direction=direction,
                           consumed=prep.with_name(prep.name + registration.HANDOFF_CONSUMED_SUFFIX))
    _write_direction(case)
    return case


def _transport(monkeypatch, case, *, outcome="success", during_response=None):
    clock, events, controls, requests, runners = _Clock(), [], [], [], []
    init, build = deadline.TimeBudgetObservation.__init__, conversation.build_runner_factory
    direction_check = entry._ExecutionDirection.require_execution_direction

    def check(checker, binding):
        direction_check(checker, binding)
        assert not case.consumed.exists() and controls == []
        events.append("direction")
        clock.advance(2000)  # validation/waits must not start generation

    def admit(control, directory, identity):
        assert events == ["direction"] and case.consumed.is_file()
        assert identity == case.arguments["observation"]
        init(control, directory, identity, clock=clock)
        assert control.first_start is None
        controls.append(control)
        events.append("admission")

    def real_build(**kwargs):
        assert kwargs["observation_for"](case.arguments["observation"].task_id, 1) is controls[0]
        factory = build(**kwargs)

        def task_factory(task):
            assert task.task_id == case.arguments["observation"].task_id
            assert "rubric" not in task.prompt and "withheld" not in task.prompt
            runner = factory(task)
            assert runner.observation_control is controls[0]
            runners.append(runner)
            return runner

        return task_factory

    original_start = entry.AgenticV2FixtureBackend.start

    def start(backend, timeout_seconds):
        assert controls[0].first_start is None and controls[0]._claimed
        clock.advance(500)
        events.append("backend_start")
        return original_start(backend, timeout_seconds)

    class Credential:
        def __init__(self):
            assert controls[0].first_start == 2600
            events.append("credential")

        def close(self):
            assert controls[0].terminal_reason is not None
            events.append("credential_close")

    class Transport:
        def __init__(self, **kwargs):
            assert events[:3] == ["direction", "admission", "backend_start"]
            assert controls[0].first_start == 2600 and controls[0].identity == case.arguments["observation"]
            assert kwargs["base_url"] == "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/openai/v1/"
            assert kwargs["timeout"] == 1200 and kwargs["max_retries"] == 0
            events.append("provider")
            self.responses = self
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: pytest.fail("chat path")))

        def create(self, **kwargs):
            requests.append(kwargs)
            assert kwargs["model"] == "gpt-5.4" and kwargs["reasoning"]["effort"] == "xhigh"
            assert kwargs["max_output_tokens"] == 8192 and kwargs["parallel_tool_calls"] is False
            assert kwargs["timeout"] == 1200
            assert "rubric" not in _canonical_json(kwargs["input"])
            assert "withheld" not in _canonical_json(kwargs["input"])
            clock.advance(1201 if outcome == "timeout" else 0.25)
            if during_response is not None:
                during_response()
            number = len(requests)
            tool = {"type": "function_call", "call_id": f"synthetic-{number}",
                    "name": "workspace_apply" if number == 1 else "finalize",
                    "arguments": json.dumps(
                        {"operation": "write", "path": "report.txt", "content": "Explicitly synthetic output.\n"}
                        if number == 1 else {"deliverables": ["report.txt"], "summary": "Synthetic first-cell work."})}
            return SimpleNamespace(
                model="different-model" if outcome == "wrong_model" else "gpt-5.4",
                usage=None if outcome == "missing_usage" else SimpleNamespace(
                    input_tokens=20 if number == 1 else 30, output_tokens=10 if number == 1 else 15,
                    input_tokens_details=SimpleNamespace(cached_tokens=5),
                    output_tokens_details=SimpleNamespace(reasoning_tokens=3)),
                output=[] if outcome == "failed" else [tool], output_text="Synthetic transport response.")

        def close(self):
            assert controls[0].terminal_reason is not None and not controls[0]._finished
            assert clock() < controls[0].cleanup_deadline
            events.append("provider_close")
            clock.advance(0.125)

    monkeypatch.setattr(entry._ExecutionDirection, "require_execution_direction", check)
    monkeypatch.setattr(deadline.TimeBudgetObservation, "__init__", admit)
    monkeypatch.setattr(conversation, "build_runner_factory", real_build)
    monkeypatch.setattr(entry.AgenticV2FixtureBackend, "start", start)
    monkeypatch.setattr(azure_ai_clients, "DefaultAzureCredential", Credential)
    monkeypatch.setattr(azure_ai_clients, "get_bearer_token_provider", lambda credential, scope: lambda: "synthetic-unused")
    monkeypatch.setattr(azure_ai_clients, "OpenAI", Transport)
    return SimpleNamespace(events=events, controls=controls, requests=requests, runners=runners, clock=clock)


def _assert_pre_admission_refusal(case, effects):
    assert effects.events == [] and effects.controls == [] and effects.requests == []
    assert not case.consumed.exists()
    assert list(case.arguments["observation_directory"].iterdir()) == []
    output = case.arguments["destination"]
    assert not (output / entry.RESULT).exists()
    assert not output.with_name(output.name + entry.RESERVATION_SUFFIX).exists()
    assert not output.with_name(output.name + entry.WORK_SUFFIX).exists()


@pytest.mark.parametrize("outcome", ["success", "failed", "missing_usage", "wrong_model", "timeout"])
def test_time_budget_first_v2_entrypoint_roundtrip(handoff_sources, tmp_path, monkeypatch, outcome):
    import step8_grade

    case = _case(handoff_sources, tmp_path)
    effects = _transport(monkeypatch, case, outcome=outcome)
    result = entry.run_first_v2_observation(handoff_sources.plan, **case.arguments)
    data = Path(result["result_path"]).read_bytes()
    payload = json.loads(data)
    assert _identity(data) == result["result_identity"]
    assert validate_inference_result_fingerprint(payload) == result["result_fingerprint"]
    assert payload["time_budget_observation"] == effects.controls[0].as_record()
    assert effects.controls[0].first_start == 2600
    assert len(effects.controls) == len(effects.runners) == 1
    assert effects.events.count("provider_close") == effects.events.count("credential_close") == 1
    assert payload["time_budget_observation"]["cleanup_complete"] is True
    assert payload["time_budget_observation"]["remote_cancellation_confirmed"] is False
    row = payload["results"][0]
    assert row["task_id"] == entry.TASK and row["retried"] is False and row["resume_round"] is None
    assert type(row["observability"]["runner_result_verified"]) is bool
    available = row["observability"]["usage_availability"]
    assert available["native_model_attempts"] is available["repeated_request_count"] is available["written_tokens"] is None
    assert available["money_hard_cap"] is False and available["cached_and_reasoning_tokens_are_subsets"] is True
    assert row["status"] == result["status"] == ("success" if outcome == "success" else "error")
    if outcome == "success":
        assert row["observability"]["runner_result_verified"] is True
        assert row["usage"] == {"input_tokens": 50, "output_tokens": 25}
        assert row["deliverable_file_records"] == [{
            "path": f"deliverable_files/{entry.TASK}/report.txt", **_identity(b"Explicitly synthetic output.\n")}]
        assert payload["time_budget_observation"]["terminal_reason"] == "completed"
    else:
        assert row["deliverable_file_records"] == [] and row["error"]
        assert payload["time_budget_observation"]["terminal_reason"] == (deadline.TIMEOUT if outcome == "timeout" else "failed")
        if outcome == "missing_usage":
            assert row["usage"] is None and available["usage_complete"] is False
    assert result["grading_performed"] is result["upload_performed"] is False
    # Genuine F-derived materialization, using the actual canonical captured
    # result and real synthetic input/source validators, never a hasher stub.
    arguments = {name: case.arguments[name] for name in (
        "observation", "runtime_root", "expected_reviewed_source_sha", "frozen_grader_root",
        "expected_grader_source_sha", "input_registration_root", "expected_input_source_sha",
        "input_registration_path", "dataset_parquet", "reference_root")}
    prepared = grading.prepare_observation_grading(
        handoff_sources.plan, **arguments, expected_input_binding=case.marker["inputs"],
        result_path=Path(result["result_path"]), expected_result_identity=result["result_identity"],
        deliverables_root=case.arguments["destination"] / "upload", destination=tmp_path / "publications" / "grading")
    materialized = tmp_path / "publications" / "grading"
    config = json.loads((materialized / grading.CONFIG).read_bytes())
    assert step8_grade.compute_grader_source_hash(
        config_path=materialized / grading.CONFIG, config=config, batch_root=materialized / "source/batch-runner"
    ) == prepared["grader"]["materialized_source_sha256"] != registration.FROZEN_TEMPLATE_SHA256
    assert prepared["grader"]["execution_source"] == "source"
    assert prepared["result"]["status"] == row["status"]
    assert prepared["launch_allowed"] is prepared["execution_enabled"] is False
    before = list(effects.events)
    replay = {**case.arguments, "destination": tmp_path / "publications" / "second-result"}
    with pytest.raises(entry.FirstV2ObservationRefused, match="direction_observation_already_consumed"):
        entry.run_first_v2_observation(handoff_sources.plan, **replay)
    assert effects.events == before and case.consumed.is_file()


@pytest.mark.parametrize("case_name", [
    "missing_direction", "missing_digest", "wrong_digest", "stale", "malformed", "approval_bit",
    "direction_host", "changed_host", "different_task", "different_run", "source_anchor", "source_tree",
    "runtime_root", "frozen_anchor", "input_binding", "input_drift",
    "preparation_digest", "marker", "coherent_marker", "config_member", "extra_member", "path_alias",
    "destination_exists", "direction_paths",
])
def test_time_budget_first_v2_entrypoint_refusals(handoff_sources, dual_roots, tmp_path, monkeypatch, case_name):
    case = _case(handoff_sources, tmp_path)
    effects = _transport(monkeypatch, case)
    args, prep = case.arguments, case.arguments["preparation_directory"]
    if case_name == "missing_direction":
        args["direction_path"].unlink()
    elif case_name == "missing_digest":
        args["expected_direction_sha256"] = None
    elif case_name == "wrong_digest":
        args["expected_direction_sha256"] = "0" * 64
    elif case_name == "stale":
        case.direction["expires_unix"] = 1
        _write_direction(case)
    elif case_name == "malformed":
        args["direction_path"].write_bytes(b"{")
        args["expected_direction_sha256"] = _identity(b"{")["sha256"]
    elif case_name == "approval_bit":
        _write_direction(case, {**case.direction, "approved": True})
    elif case_name == "direction_host":
        _write_direction(case, {**case.direction, "host_sha256": "a" * 64})
    elif case_name == "changed_host":
        monkeypatch.setattr(entry, "execution_host_identity", lambda sha: {**_HOST, "instance_sha256": "a" * 64})
    elif case_name == "different_task":
        args["observation"] = replace(args["observation"], task_id=handoff_sources.task_ids[1])
    elif case_name == "different_run":
        args["observation"] = replace(args["observation"], run_id="gpt54_time_budget_v1_codex_r1", condition="codex")
    elif case_name == "source_anchor":
        args["expected_reviewed_source_sha"] = "d" * 40
    elif case_name == "source_tree":
        args["observation"] = replace(args["observation"], reviewed_source_tree="d" * 40)
        case.direction["execution_binding"]["observation_json"] = _canonical_json(asdict(args["observation"]))
        _write_direction(case)
    elif case_name == "runtime_root":
        args["runtime_root"] = dual_roots["substitute"]
        case.direction["paths"]["runtime_root"] = str(args["runtime_root"])
        _write_direction(case)
    elif case_name == "frozen_anchor":
        args["expected_grader_source_sha"] = handoff_sources.runtime_sha
    elif case_name == "input_binding":
        args["observation"] = replace(args["observation"], input_sha256="d" * 64)
        case.direction["execution_binding"]["observation_json"] = _canonical_json(asdict(args["observation"]))
        _write_direction(case)
    elif case_name == "input_drift":
        changed = tmp_path / "changed-synthetic.parquet"
        changed.write_bytes(handoff_sources.parquet.read_bytes() + b"drift")
        args["dataset_parquet"] = changed
        case.direction["paths"]["dataset_parquet"] = str(changed)
        _write_direction(case)
    elif case_name == "preparation_digest":
        args["expected_preparation_identity"] = {**args["expected_preparation_identity"], "sha256": "e" * 64}
    elif case_name in {"marker", "coherent_marker"}:
        changed = {**case.marker, "evidence_boundary": "coherent_but_not_registered"}
        (prep / registration.HANDOFF_READY).write_bytes(_canonical_json(changed).encode())
        if case_name == "coherent_marker":
            identity = _identity((prep / registration.HANDOFF_READY).read_bytes())
            reserved = prep.with_name(prep.name + registration.HANDOFF_RESERVATION_SUFFIX)
            value = json.loads(reserved.read_bytes())
            value["intended_preparation"] = identity
            reserved.write_bytes(_canonical_json(value).encode())
            # Mutually consistent local marker/reservation cannot replace the
            # leader's independent preparation/direction expectation.
    elif case_name == "config_member":
        value = json.loads((prep / registration.HANDOFF_CONFIG).read_bytes())
        value["configuration"]["model"]["deployment"] = "not-the-model"
        (prep / registration.HANDOFF_CONFIG).write_bytes(_canonical_json(value).encode())
    elif case_name == "extra_member":
        (prep / "unexpected.json").write_text("{}")
    elif case_name == "path_alias":
        alias = tmp_path / "alias"
        alias.symlink_to(prep, target_is_directory=True)
        args["preparation_directory"] = alias
    elif case_name == "destination_exists":
        args["destination"].mkdir()
        (args["destination"] / "keep").write_text("not ours")
    elif case_name == "direction_paths":
        case.direction["paths"]["destination"] += "-replacement"
        _write_direction(case)
    with pytest.raises((ValueError, OSError)):
        entry.run_first_v2_observation(handoff_sources.plan, **args)
    _assert_pre_admission_refusal(case, effects)
    if case_name == "destination_exists":
        assert (args["destination"] / "keep").read_text() == "not ours"


@pytest.mark.parametrize("change", ["handoff_member", "publication_failure"])
def test_time_budget_first_v2_entrypoint_final_reread_and_partial(handoff_sources, tmp_path, monkeypatch, change):
    case = _case(handoff_sources, tmp_path)

    def change_member():
        (case.arguments["preparation_directory"] / "late-extra").write_text("synthetic")

    effects = _transport(monkeypatch, case, during_response=change_member if change == "handoff_member" else None)
    if change == "publication_failure":
        original = entry._write_no_clobber

        def write(path, data, **kwargs):
            if path.name == entry.RESULT:
                raise OSError("synthetic interrupted publication")
            return original(path, data, **kwargs)

        monkeypatch.setattr(entry, "_write_no_clobber", write)
    with pytest.raises((ValueError, OSError)):
        entry.run_first_v2_observation(handoff_sources.plan, **case.arguments)
    assert len(effects.controls) == 1 and effects.controls[0]._finished and case.consumed.exists()
    output = case.arguments["destination"]
    assert not (output / entry.RESULT).exists()
    assert output.with_name(output.name + entry.RESERVATION_SUFFIX).exists() is (change == "publication_failure")


def test_time_budget_first_v2_entrypoint_defaults_and_source_roles(handoff_sources, dual_roots, monkeypatch, capsys):
    assert entry.main([]) == 2
    assert json.loads(capsys.readouterr().out)["retry_allowed"] is False
    profile = legacy.load_plan(handoff_sources.runtime / registration.SOURCE_PROFILE)
    # CURRENT differs for these exact bytes. Historical positives remain on F.
    current = legacy.inspect_plan(profile)
    assert current["configuration_problems"] == [
        "source_pin:batch-runner/gpt54_prepared_input_attestation.py",
        "source_pin:batch-runner/core/agentic_v2_conversation_runner.py",
        "source_pin:batch-runner/core/codex_runner.py",
    ]
    assert current["launch_allowed"] is False
    with monkeypatch.context() as source:
        # The synthetic input-only profile is not a legacy dispatch plan.
        # This historical positive needs F's untouched profile and source.
        source.setattr(legacy, "ROOT", dual_roots["frozen"])
        frozen = legacy.compile_dispatch_plan(legacy.load_plan(dual_roots["frozen"] / registration.SOURCE_PROFILE))
        assert frozen.as_dict()["launch_allowed"] is False


def test_time_budget_first_v2_entrypoint_synchronous_input_keeps_legacy_default(handoff_sources, monkeypatch):
    import gpt54_prepared_input_attestation as inputs

    events = []
    table, parquet_file = inputs.parquet.read_table, inputs.parquet.ParquetFile

    def legacy_read(*args, **kwargs):
        assert "use_threads" not in kwargs and "pre_buffer" not in kwargs
        events.append("legacy")
        return table(*args, **kwargs)

    class SynchronousFile:
        def __init__(self, *args, **kwargs):
            assert kwargs == {"pre_buffer": False}
            self.source = parquet_file(*args, **kwargs)

        def __enter__(self):
            self.source.__enter__()
            return self

        def __exit__(self, *args):
            return self.source.__exit__(*args)

        def read(self, **kwargs):
            assert kwargs["use_threads"] is False
            events.append("synchronous")
            return self.source.read(**kwargs)

    monkeypatch.setattr(inputs.parquet, "read_table", legacy_read)
    monkeypatch.setattr(inputs.parquet, "ParquetFile", SynchronousFile)
    data = handoff_sources.parquet.read_bytes()
    assert inputs._dataset_tasks(data, handoff_sources.task_ids) == inputs._dataset_tasks(
        data, handoff_sources.task_ids, synchronous=True)
    assert events == ["legacy", "synchronous"]
