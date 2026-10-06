"""Registered Codex callable: real consumer/SDK/runner, synthetic transports."""

import io
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from openai_codex import Sandbox, api as native_api
from openai_codex._sandbox import _sandbox_policy
from openai_codex.client import CodexClient
from openai_codex.generated.v2_all import (
    ItemCompletedNotification, ThreadStartParams, ThreadTokenUsageUpdatedNotification,
    TurnCompletedNotification, TurnStartParams,
)
from openai_codex.models import Notification

import gpt54_time_budget_codex_observation as entry
import gpt54_time_budget_comparison as registration
from core import azure_ai_clients, codex_azure_token, codex_runner, codex_runtime_config
from core import time_budget_observation_deadline as deadline
from core.agentic_v2_preregistration import seal
from core.inference_manifest import STEP2_PROGRESS_SCHEMA, validate_step2_progress_results
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_comparison_preflight import _canonical_json
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_time_budget_comparison import (
    _Clock, _handoff_arguments, dual_roots, handoff_source_seed, handoff_sources,
    observation_kernel,
)

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
_ENDPOINT = "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/openai/v1/"
_SECRET = "synthetic-private-provider-error-not-a-credential"
_FILE = b"Synthetic Codex deliverable; not original data.\n"


def _expected_provider():
    return codex_runtime_config.CodexProviderSettings(
        endpoint=_ENDPOINT, model="gpt-5.4", provider_id=codex_runtime_config.DEFAULT_PROVIDER_ID,
        reasoning_effort="xhigh", model_context_window=None, request_max_retries=0, stream_max_retries=0,
    )


@pytest.fixture(autouse=True)
def offline(monkeypatch, handoff_sources, dual_roots, observation_kernel):
    """Keep all real guards; permit only read-only Git and scripted auth I/O."""
    import step8_grade
    from core import rubric_loader

    forbidden_calls, auth_calls = [], []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("Codex observation proof crossed a live process/network/credential boundary")

    for owner, names in ((socket.socket, ("connect", "connect_ex")),
                         (socket, ("create_connection", "getaddrinfo")),
                         (subprocess, ("run", "Popen", "check_call", "check_output")),
                         (os, ("system",)), (rubric_loader, ("snapshot_download", "hf_hub_download", "HfApi")),
                         (codex_azure_token, ("acquire_token", "get_bearer_token_provider"))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for constructor in (azure_ai_clients.OpenAI, azure_ai_clients.AzureOpenAI,
                        azure_ai_clients.DefaultAzureCredential, step8_grade.Grader):
        monkeypatch.setattr(constructor, "__init__", forbidden)
    monkeypatch.setattr(CodexClient, "start", forbidden)
    for key in tuple(os.environ):
        if key.startswith(("AZURE_", "FOUNDRY_", "GITHUB_", "ACTIONS_", "HF_", "OPENAI_", "CODEX_")):
            monkeypatch.delenv(key)
    for key in ("HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.setenv(key, "1")
    monkeypatch.setenv(azure_ai_clients.ROUTE_PROFILE_ENV, "direct-v1")
    monkeypatch.setenv(azure_ai_clients.DIRECT_ENDPOINT_ENV, _ENDPOINT)
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "HF_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.setenv(key, "synthetic-secret-must-be-blank-in-native-child")

    # Ordinary /proc metadata seam, not a successful host/ownership verdict.
    boot = "11111111-2222-3333-4444-555555555555"
    real_open, real_stat = Path.open, Path.stat

    def proc_open(path, *args, **kwargs):
        if str(path) == "/proc/sys/kernel/random/boot_id":
            return io.StringIO(boot + "\n")
        return real_open(path, *args, **kwargs)

    def proc_stat(path, *args, **kwargs):
        if str(path) == "/proc/self/ns/pid":
            return SimpleNamespace(st_dev=123, st_ino=456)
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", proc_open)
    monkeypatch.setattr(Path, "stat", proc_stat)
    host = seal({"boot_id": boot, "uname": list(os.uname()), "uid": os.getuid(), "pid_namespace": [123, 456]})

    # A genuine non-/tmp runtime root: preserve the existing native path guard.
    # This directory contains only synthetic files and is owned by this fixture.
    with tempfile.TemporaryDirectory(prefix="time-budget-codex-offline-", dir="/var/tmp") as owned:
        root = Path(owned)
        native_root, login = root / "native", root / "synthetic-login"
        native_root.mkdir(mode=0o700)
        login.mkdir(mode=0o700)
        monkeypatch.setenv(codex_runtime_config.RUN_ROOT_ENV_NAME, str(native_root))
        monkeypatch.setenv("AZURE_CONFIG_DIR", str(login))
        transport = SimpleNamespace(auth=None)

        def process(command, **kwargs):
            if command[:2] == ["/usr/bin/git", "--no-replace-objects"]:
                index = command.index("-C")
                assert Path(command[index + 1]) in {
                    handoff_sources.runtime, handoff_sources.frozen,
                    dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"],
                }
                assert command[index + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
                assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
                with monkeypatch.context() as local:
                    local.setattr(subprocess, "Popen", _REAL_POPEN)
                    return _REAL_RUN(command, **kwargs)
            assert command == _expected_provider().auth_command()
            assert transport.auth is not None, "authentication before a validated test invocation"
            auth_calls.append(command)
            transport.auth(command, kwargs)
            return subprocess.CompletedProcess(command, 0, "synthetic-auth-transport-token", "")

        monkeypatch.setattr(subprocess, "run", process)
        yield SimpleNamespace(host=host, native_root=native_root, login=login, transport=transport,
                              auth_calls=auth_calls, forbidden=forbidden_calls)
    assert forbidden_calls == []


def _write_direction(case, *, trust=True):
    data = _canonical_json(case.direction).encode()
    case.arguments["direction_path"].write_bytes(data)
    if trust:
        case.arguments["expected_direction_sha256"] = _identity(data)["sha256"]


def _case(seed, tmp_path, offline, *, repeat=1, task_index=0):
    preparation = _handoff_arguments(seed, tmp_path, condition="codex", repeat=repeat, task_index=task_index)
    marker = registration.prepare_observation_handoff(seed.plan, **preparation)
    prep = preparation.pop("destination")
    preparation.pop("run_id")
    preparation.pop("task_id")
    store = tmp_path / "owned-observation-store"
    store.mkdir(mode=0o700)
    arguments = {**preparation, "observation": deadline.ObservationIdentity(**marker["observation"]),
                 "preparation_directory": prep, "expected_preparation_identity": _identity(_canonical_json(marker).encode()),
                 "expected_step0_identity": _identity(seed.step0.read_bytes()), "observation_directory": store,
                 "destination": tmp_path / "publications/result", "direction_path": tmp_path / "direction.json",
                 "expected_host_sha256": offline.host}
    binding = registration.ObservationExecutionBinding(
        arguments["expected_preparation_identity"]["sha256"], arguments["expected_preparation_identity"]["size"],
        _canonical_json(marker["observation"]), seed.frozen_sha, seed.frozen_tree,
        registration.FROZEN_TEMPLATE_SHA256, str(prep), str(store))
    # Independently authored synthetic direction, not the checker's output and
    # never authority for any real host, input or registered observation.
    provider = _expected_provider()
    now = int(time.time())
    direction = {
        "direction_version": entry.DIRECTION_VERSION, "purpose": "execute_one_registered_observation",
        "execution_binding": asdict(binding), "host_sha256": offline.host,
        "not_before_unix": now - 60, "expires_unix": now + 3600,
        "provider_binding": {"settings_sha256": seal(asdict(provider)),
            "config_overrides_sha256": seal(provider.config_overrides()), "sdk_version": "0.147.0", "cli_version": "0.147.0"},
        "step0_identity": arguments["expected_step0_identity"],
        "paths": {"direction": str(arguments["direction_path"]), "preparation": str(prep),
            "runtime_root": str(seed.runtime), "frozen_grader_root": str(seed.frozen),
            "input_registration_root": str(seed.frozen), "dataset_parquet": str(seed.parquet),
            "reference_root": str(seed.references), "step0_manifest": str(seed.step0),
            "observation_directory": str(store), "destination": str(arguments["destination"]),
            "native_run_root": str(offline.native_root), "input_source_sha": seed.frozen_sha,
            "input_registration_path": registration.SOURCE_PROFILE},
    }
    case = SimpleNamespace(arguments=arguments, marker=marker, direction=direction,
                           consumed=prep.with_name(prep.name + registration.HANDOFF_CONSUMED_SUFFIX))
    _write_direction(case)
    return case


def _native_transport(monkeypatch, case, offline, *, outcome):
    """Real pinned SDK facade/types/collector above an app-server I/O seam."""
    clock, controls, requests, clients = _Clock(), [], [], []
    initialize = deadline.TimeBudgetObservation.__init__

    def observation_init(control, directory, identity):
        assert case.consumed.is_file()
        initialize(control, directory, identity, clock=clock)
        assert identity == case.arguments["observation"]
        controls.append(control)

    monkeypatch.setattr(deadline.TimeBudgetObservation, "__init__", observation_init)

    def isolated(environment, workspace):
        for key in codex_runtime_config.CREDENTIAL_ENV_NAMES:
            assert environment[key] == ""
        assert environment["HOME"] == str(workspace.parent / "home")
        assert environment["CODEX_HOME"] == str(workspace.parent / "codex_home")
        assert workspace.parent.parent == offline.native_root

    def auth(command, kwargs):
        assert len(controls) == 1 and controls[0]._claimed and controls[0].first_start is None
        assert kwargs["timeout"] == codex_runner._AUTH_PREFLIGHT_TIMEOUT
        assert kwargs["capture_output"] is True and kwargs["text"] is True
        isolated(kwargs["env"], Path(kwargs["cwd"]))
        clock.advance(2000)  # setup/auth is not a new generation budget

    offline.transport.auth = auth

    class SyntheticNativeTransport(CodexClient):
        def start(self):
            assert len(offline.auth_calls) == 1 and controls[0].first_start is None
            assert self.config.codex_bin is None and self.config.launch_args_override is None
            assert self.config.config_overrides == _expected_provider().config_overrides()
            self.workspace = Path(self.config.cwd)
            isolated(self.config.env, self.workspace)
            self.events = iter(())
            clients.append(self)

        def notify(self, method, params=None):
            assert method == "initialized" and params is None

        def _request_raw(self, method, params=None):
            requests.append((method, params))
            if method == "initialize":
                assert params["clientInfo"]["version"] == "0.147.0"
                return {"userAgent": "synthetic-codex/0.147.0",
                        "serverInfo": {"name": "synthetic-codex", "version": "0.147.0"}}
            if method == "thread/start":
                ThreadStartParams.model_validate(params)
                assert params["model"] == "gpt-5.4"
                assert params["modelProvider"] == codex_runtime_config.DEFAULT_PROVIDER_ID
                assert params["cwd"] == str(self.workspace)
                assert params["sandbox"] == "workspace-write" and params["approvalPolicy"] == "never"
                assert controls[0].first_start is None
                for item in case.marker["inputs"]["reference_file_records"]:
                    actual = self.workspace / Path(item["path"]).name
                    assert _identity(actual.read_bytes()) == {key: item[key] for key in ("sha256", "size")}
                    assert actual.stat().st_mode & 0o777 == 0o400
                thread = {"id": "synthetic-native-thread", "cliVersion": "0.147.0", "createdAt": 1, "updatedAt": 1,
                          "cwd": str(self.workspace), "ephemeral": False, "modelProvider": params["modelProvider"],
                          "preview": "synthetic", "sessionId": "synthetic-native-thread", "source": "exec",
                          "status": {"type": "idle"}, "turns": []}
                return {"thread": thread, "cwd": str(self.workspace), "model": params["model"],
                        "modelProvider": params["modelProvider"], "approvalPolicy": params["approvalPolicy"],
                        "approvalsReviewer": params.get("approvalsReviewer", "user"),
                        "sandbox": _sandbox_policy(Sandbox.workspace_write)}
            assert method == "turn/start", "no resume, retry, account or extra native request"
            TurnStartParams.model_validate(params)
            assert params["threadId"] == "synthetic-native-thread"
            task_text = params["input"][0]["text"]
            assert "Synthetic handoff task" in task_text and "rubric" not in task_text and "withheld" not in task_text
            assert controls[0].first_start == clock.now and controls[0].remaining_seconds() == 1200
            (self.workspace / "deliverable.txt").write_bytes(_FILE)
            clock.advance(1)
            item = {"type": "agentMessage", "id": "synthetic-message", "text": "Synthetic final answer.", "phase": "final_answer"}
            total = {"inputTokens": 100, "cachedInputTokens": 10, "cacheWriteInputTokens": 0,
                     "outputTokens": 20, "reasoningOutputTokens": 5, "totalTokens": 120}
            turn = {"id": "synthetic-native-turn", "items": [item],
                    "status": "failed" if outcome == "failed" else "completed",
                    "error": {"message": _SECRET} if outcome == "failed" else None}
            self.events = iter([
                Notification("thread/tokenUsage/updated", ThreadTokenUsageUpdatedNotification.model_validate({
                    "threadId": params["threadId"], "turnId": turn["id"], "tokenUsage": {"total": total, "last": total}})),
                Notification("item/completed", ItemCompletedNotification.model_validate({
                    "threadId": params["threadId"], "turnId": turn["id"], "item": item, "completedAtMs": 1})),
                Notification("turn/completed", TurnCompletedNotification.model_validate({
                    "threadId": params["threadId"], "turn": turn})),
            ])
            return {"turn": {**turn, "status": "inProgress", "error": None}}

        def next_turn_notification(self, turn_id):
            assert turn_id == "synthetic-native-turn"
            clock.advance(1)
            return next(self.events)

        def close(self):
            assert controls[0].terminal_reason is not None
            clock.advance(1)
            return super().close()

    monkeypatch.setattr(native_api, "CodexClient", SyntheticNativeTransport)
    return SimpleNamespace(controls=controls, requests=requests, clients=clients)


def _cli_arguments(case):
    args, identity = case.arguments, asdict(case.arguments["observation"])
    values = {name.replace("_", "-"): args[name] for name in (
        "preparation_directory", "runtime_root", "frozen_grader_root", "input_registration_root",
        "input_registration_path", "dataset_parquet", "reference_root", "step0_manifest",
        "observation_directory", "destination")}
    values.update({"direction": args["direction_path"], "direction-sha256": args["expected_direction_sha256"],
        "host-sha256": args["expected_host_sha256"], "grader-source-sha": args["expected_grader_source_sha"],
        "input-source-sha": args["expected_input_source_sha"],
        **{name.replace("_", "-"): identity[name] for name in (
            "run_id", "task_id", "repeat", "reviewed_source_sha", "reviewed_source_tree", "registration_sha256", "input_sha256")}})
    for label in ("preparation", "step0"):
        for key, value in args[f"expected_{label}_identity"].items():
            values[f"{label}-{key}"] = value
    return [item for key, value in values.items() for item in ("--" + key, str(value))]


@pytest.mark.parametrize("repeat,task_index,outcome", [(1, 0, "success"), (2, 1, "success"), (1, 2, "failed")])
def test_time_budget_codex_callable_roundtrip(handoff_sources, tmp_path, offline, monkeypatch, capsys,
                                            repeat, task_index, outcome):
    case = _case(handoff_sources, tmp_path, offline, repeat=repeat, task_index=task_index)
    native = _native_transport(monkeypatch, case, offline, outcome=outcome)
    if repeat == 2:
        assert entry.main(_cli_arguments(case)) == 0
        response = json.loads(capsys.readouterr().out)
    else:
        response = entry.run_codex_observation(handoff_sources.plan, **case.arguments)
    captured = capsys.readouterr()
    assert captured.err == "" and _SECRET not in captured.out
    data = (case.arguments["destination"] / entry.RESULT).read_bytes()
    payload = json.loads(data)
    assert response["result_identity"] == _identity(data)
    assert response["result_fingerprint"] == validate_inference_result_fingerprint(payload)
    assert response["observation"] == case.marker["observation"]
    assert payload["experiment_id"] == case.arguments["observation"].run_id
    assert payload["condition"] == "codex" and payload["execution_mode"] == "codex_foundry"
    row = payload["results"][0]
    validate_step2_progress_results([row], schema_version=STEP2_PROGRESS_SCHEMA)
    assert row["status"] == response["status"] == ("error" if outcome == "failed" else "success")
    assert row["task_id"] == handoff_sources.task_ids[task_index] and row["model"] == "gpt-5.4"
    assert row["content"] == row["deliverable_text"] == ("" if outcome == "failed" else "Synthetic final answer.")
    role = f"deliverable_files/{row['task_id']}/deliverable.txt"
    assert row["deliverable_files"] == [role]
    assert row["deliverable_file_records"] == [{"path": role, **_identity(_FILE)}]
    assert (case.arguments["destination"] / "upload" / role).read_bytes() == _FILE
    assert row["usage"] is None and row["observability"]["usage_availability"] == {
        "usage_complete": False, "reason": "consumer_does_not_export_native_usage"}
    assert all(value is None for value in row["observability"]["native_measurements"].values())
    assert row["observability"]["codex_diagnostics"] == {"items_seen": 1, "http_status_code": None, "rate_limit_kind": None}
    assert _SECRET.encode() not in data
    assert len(native.controls) == len(offline.auth_calls) == len(native.clients) == 1
    assert [method for method, _ in native.requests] == ["initialize", "thread/start", "turn/start"]
    control = payload["time_budget_observation"]
    assert control == native.controls[0].as_record()
    assert control["identity"] == case.marker["observation"] and control["admitted"] is True
    assert control["terminal_reason"] == ("failed" if outcome == "failed" else "completed")
    assert control["generation_elapsed_seconds"] == 4 and row["latency_ms"] == 4000
    assert control["cleanup_deadline_monotonic"] - native.controls[0].terminal_at == 20
    assert control["cleanup_complete"] is True and control["host_reusable"] is True
    assert control["remote_billing_bound"] is False and control["remote_cancellation_confirmed"] is False
    assert list(offline.native_root.iterdir()) == []
    execution = payload["observation_execution"]
    for key in ("runtime_source", "frozen_grader", "inputs", "condition_template"):
        assert execution[key] == case.marker[key]
    assert execution["provider_binding"] == case.direction["provider_binding"]
    assert execution["configuration"] == case.marker["files"][registration.HANDOFF_CONFIG]
    assert execution["direction_sha256"] == case.arguments["expected_direction_sha256"]
    assert execution["paths_sha256"] == seal(case.direction["paths"])
    assert execution["grading_performed"] is execution["upload_performed"] is False
    store = case.arguments["observation_directory"]
    assert len(list(store.glob("*.admitted.json"))) == 1
    before = {path.name: path.read_bytes() for path in store.iterdir()}
    consumed = case.consumed.read_bytes()
    with pytest.raises(entry.CodexObservationRefused, match="already_consumed"):
        entry.run_codex_observation(handoff_sources.plan, **{
            **case.arguments, "destination": case.arguments["destination"].with_name("other-result")})
    assert case.consumed.read_bytes() == consumed
    assert {path.name: path.read_bytes() for path in store.iterdir()} == before
    assert len(offline.auth_calls) == 1 and (case.arguments["destination"] / entry.RESULT).read_bytes() == data

    if repeat == 1 and task_index == 0:
        # A fresh preparation copy/destination and newly bound direction cannot
        # mint another attempt at this observation in the independently named store.
        original_prep = case.arguments["preparation_directory"]
        copied = original_prep.with_name("copied-preparation")
        shutil.copytree(original_prep, copied)
        reservation = original_prep.with_name(original_prep.name + registration.HANDOFF_RESERVATION_SUFFIX)
        shutil.copyfile(reservation, copied.with_name(copied.name + registration.HANDOFF_RESERVATION_SUFFIX))
        case.arguments.update(preparation_directory=copied, destination=copied.with_name("copied-result"))
        case.direction["paths"].update(preparation=str(copied), destination=str(case.arguments["destination"]))
        case.direction["execution_binding"]["preparation_directory"] = str(copied)
        _write_direction(case)
        with pytest.raises(deadline.ObservationDeadlineRefused, match=deadline.REFUSED):
            entry.run_codex_observation(handoff_sources.plan, **case.arguments)
        assert not case.arguments["destination"].exists()
        assert {path.name: path.read_bytes() for path in store.iterdir()} == before
        assert case.consumed.read_bytes() == consumed and len(offline.auth_calls) == 1
        assert len(native.controls) == 1 and len(native.requests) == 3


@pytest.mark.parametrize("change", ["direction_digest", "stale_direction", "direction_binding", "selection", "step0", "route"])
def test_time_budget_codex_callable_refusals(handoff_sources, tmp_path, offline, monkeypatch, change):
    case = _case(handoff_sources, tmp_path, offline)
    if change == "direction_digest":
        case.arguments["expected_direction_sha256"] = "0" * 64
    elif change == "stale_direction":
        case.direction.update(not_before_unix=0, expires_unix=1)
        _write_direction(case)
    elif change == "direction_binding":
        wrong = {**case.marker["observation"], "task_id": handoff_sources.task_ids[1]}
        case.direction["execution_binding"]["observation_json"] = _canonical_json(wrong)
        _write_direction(case)
    elif change == "step0":
        case.arguments["expected_step0_identity"] = {**case.arguments["expected_step0_identity"], "sha256": "0" * 64}
    elif change == "route":
        monkeypatch.setenv(azure_ai_clients.DIRECT_ENDPOINT_ENV, "https://other-account.services.ai.azure.com/openai/v1/")
    else:
        with pytest.raises(deadline.ObservationDeadlineRefused):
            replace(case.arguments["observation"], task_id="unregistered-task")
        with pytest.raises(entry.CodexObservationRefused, match="registered_codex_observation_only"):
            entry.run_codex_observation(handoff_sources.plan, **{**case.arguments, "observation": replace(
                case.arguments["observation"], condition="sandbox_v2", run_id="gpt54_time_budget_v1_v2_r1")})
        case.arguments["observation"] = replace(case.arguments["observation"], task_id=handoff_sources.task_ids[1])
    reason = {"direction_digest": "reference file hash mismatch", "step0": "reference file hash mismatch",
              "stale_direction": "direction_not_current", "direction_binding": "direction execution binding mismatch",
              "selection": "independent observation mismatch", "route": "registered_codex_route_required"}[change]
    with pytest.raises(ValueError, match=reason):
        entry.run_codex_observation(handoff_sources.plan, **case.arguments)
    assert not case.consumed.exists() and not case.arguments["destination"].exists()
    assert not case.arguments["destination"].with_name(case.arguments["destination"].name + entry.RESERVATION_SUFFIX).exists()
    assert list(case.arguments["observation_directory"].iterdir()) == []
    assert list(offline.native_root.iterdir()) == [] and offline.auth_calls == []
