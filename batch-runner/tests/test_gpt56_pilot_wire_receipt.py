"""Synthetic transport behavior only: no live pilot, auth or served evidence."""

import ast
import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt56_pilot_input_capture as capture
import gpt56_pilot_wire_receipt as wire
import gpt56_pilot_native_result_host as native
import gpt56_sol_codex_pilot_preflight as pilot
import step2_run_inference as step2
from core import codex_runner
from core.codex_runtime_config import CodexProviderSettings
from .test_gpt56_pilot_input_capture import (
    PRIVATE, RAW_IDS, TASK_IDS, _fresh, _no_execution, _offline, _parse_cache, _seed,
    _tree, _verify, capture_seed, deployment_seeds, input_seeds, no_runtime,
    offline_only, runtime_guards, source_seed,
)

REAL_INIT = codex_runner.CodexAgentRunner.__init__
PRIVATE_TEXT = "private prompt/output /private/host never-publish Authorization: Bearer synthetic"
REQUESTED = {"provider": "azure", "provider_id": "gdpval-foundry", "model": "gpt-5.6-sol",
             "deployment": "reviewed-sol-deployment", "reasoning_effort": "max", "context_tokens": 1_000_000}
USAGE = {"total": {"inputTokens": 71, "outputTokens": 9, "reasoningOutputTokens": None, "totalTokens": 80},
         "last": {"inputTokens": 17, "outputTokens": 4}, "modelContextWindow": 1_000_000}


class Pipe:
    encoding = "utf-8"

    def __init__(self):
        self.written = []
        self.flushed = 0

    def write(self, value):
        self.written.append(value)
        return len(value)

    def flush(self):
        self.flushed += 1


def _transport(observer=None, *, thread_id="thread-private", turn_id="turn-private", workspace=Path("/private/task-workspace")):
    observer = observer or wire._TransportObservation(deepcopy(REQUESTED))
    if observer.task_text is None:
        observer.bind_task_text(PRIVATE_TEXT)
    observer.bind_runtime(workspace=workspace, developer_instructions="private developer text")
    pipe = Pipe()
    client = SimpleNamespace(_proc=SimpleNamespace(stdin=pipe),
                             _router=SimpleNamespace(route_response=lambda value: "original-response"),
                             _coerce_notification=lambda method, params: "original-notification")

    def send(value):
        # Deliberately different whitespace/encoding from canonical JSON.
        # The receipt must hash this actual serialization, including newline.
        client._proc.stdin.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
        client._proc.stdin.flush()

    client._write_message = send
    codex = SimpleNamespace(_client=client)
    wire.install_runtime_observer(codex, observer)
    return SimpleNamespace(observer=observer, codex=codex, client=client, pipe=pipe, thread_id=thread_id, turn_id=turn_id)


def _thread_request():
    return {"id": "rpc-thread", "method": "thread/start", "params": {
        "model": REQUESTED["deployment"], "modelProvider": "gdpval-foundry", "cwd": "/private/task-workspace",
        "sandbox": "workspace-write", "approvalPolicy": "never", "developerInstructions": "private developer text"}}


def _thread_response():
    return {"id": "rpc-thread", "result": {"thread": {"id": "thread-private"},
            "model": REQUESTED["deployment"], "modelProvider": "gdpval-foundry", "reasoningEffort": "max"}}


def _start(fake):
    request = _thread_request()
    request["params"]["cwd"] = fake.observer.runtime["cwd"]
    fake.client._write_message(request)
    response = _thread_response()
    response["result"]["thread"]["id"] = fake.thread_id
    assert fake.client._router.route_response(response) == "original-response"


def _turn_request():
    return {"id": "rpc-turn", "method": "turn/start",
            "params": {"threadId": "thread-private", "input": [{"type": "text", "text": PRIVATE_TEXT}]}}


def _turn(fake, *, usage=USAGE, success=True):
    request = _turn_request()
    request["params"]["threadId"] = fake.thread_id
    request["params"]["input"][0]["text"] = fake.observer.task_text
    fake.client._write_message(request)
    fake.client._router.route_response({"id": "rpc-turn", "result": {"turn": {"id": fake.turn_id}}})
    if usage is not None:
        assert fake.client._coerce_notification("thread/tokenUsage/updated", {
            "threadId": fake.thread_id, "turnId": fake.turn_id, "tokenUsage": usage,
        }) == "original-notification"
    fake.client._coerce_notification("item/agentMessage/delta", {"delta": PRIVATE_TEXT})
    fake.client._coerce_notification("turn/completed", {
        "threadId": fake.thread_id, "turn": {"id": fake.turn_id, "status": "completed" if success else "failed",
                                                "error": {"message": PRIVATE_TEXT}}})


def _finish(fake, *, success=True):
    return fake.observer.finish(success=success, thread_id="thread-private", turn_id="turn-private")


@pytest.fixture
def transport():
    return _transport()


@pytest.mark.parametrize("usage", [USAGE, None, {}, {"last": {"cacheWriteInputTokens": None}},
                                  {"total": {"cacheWriteInputTokens": 0}}])
def test_actual_flushed_serialization_and_native_absence_are_preserved(transport, usage, capsys):
    _start(transport)
    _turn(transport, usage=usage)
    result = _finish(transport)
    assert transport.pipe.flushed == 2
    for method, data in zip(("thread/start", "turn/start"), transport.pipe.written):
        assert result["requests"][method]["serialized_utf8"] == wire._digest(data.encode("utf-8"))
        assert wire._bytes(json.loads(data)) != data.encode("utf-8")
    snapshots = result["usage"]["snapshots"]
    assert ([row["native"] for row in snapshots] == [usage]) if usage is not None else snapshots == []
    if usage == USAGE:
        assert "cacheWriteInputTokens" not in snapshots[0]["native"]["total"]
        assert snapshots[0]["native"]["total"]["reasoningOutputTokens"] is None
    for key in ("foundry_http_payload", "foundry_request_id", "served_model", "served_model_version", "served_deployment"):
        assert result[key] == wire._unavailable()
    assert result["usage"]["pricing"] == result["usage"]["model_call_count"] == wire._unavailable()
    assert result["app_server_settings"]["source"] == "app_server_thread_settings_not_served_identity"
    public = wire._bytes(result).decode() + capsys.readouterr().out
    assert all(secret not in public for secret in (PRIVATE_TEXT, "/private", "thread-private", "turn-private", "rpc-turn"))
    assert result["scope"] == "codex_app_server_stdio_utf8_after_initialize"


@pytest.mark.parametrize("change", ["request-text", "thread", "turn-retry", "resume", "model-override", "effort-override",
                                   "raw-path", "same-rpc-id", "extra-field", "duplicate-turn"])
def test_changed_request_or_retry_is_refused_at_the_transport_seam(transport, change):
    _start(transport)
    request = _turn_request()
    if change == "request-text":
        request["params"]["input"][0]["text"] += " changed"
    elif change == "thread":
        request["params"]["threadId"] = "different"
    elif change in ("turn-retry", "resume"):
        request["method"] = "turn/retry" if change == "turn-retry" else "thread/resume"
    elif change == "model-override":
        request["params"]["model"] = "gpt-5.6-fast"
    elif change == "effort-override":
        request["params"]["effort"] = "low"
    elif change == "raw-path":
        request["params"]["input"] = [{"type": "localImage", "path": "/private/host"}]
    elif change == "same-rpc-id":
        request["id"] = "rpc-thread"
    elif change == "extra-field":
        request["authorization"] = PRIVATE_TEXT
    else:
        transport.client._write_message(request)
    before = list(transport.pipe.written)
    with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$"):
        transport.client._write_message(request)
    assert transport.pipe.written == before and transport.observer.invalid


@pytest.mark.parametrize("change", ["provider", "deployment", "effort", "rpc-id", "duplicate-response", "error", "rerouted"])
def test_returned_route_drift_and_mismatched_response_fail_closed(transport, change):
    transport.client._write_message(_thread_request())
    response = _thread_response()
    if change in ("provider", "deployment", "effort"):
        response["result"][{"provider": "modelProvider", "deployment": "model", "effort": "reasoningEffort"}[change]] = PRIVATE_TEXT
    elif change == "rpc-id":
        response["id"] = "wrong"
    elif change == "error":
        response["error"] = {"message": PRIVATE_TEXT}
    elif change == "duplicate-response":
        transport.client._router.route_response(response)
    with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$") as failure:
        if change == "rerouted":
            transport.client._coerce_notification("model/rerouted", {"fromModel": "gpt-5.6-sol", "toModel": "gpt-5.6-fast"})
        else:
            transport.client._router.route_response(response)
    assert PRIVATE_TEXT not in str(failure.value) and failure.value.__suppress_context__


@pytest.mark.parametrize("usage", [{"total": {"inputTokens": True}}, {"last": {"outputTokens": -1}},
                                  {"total": {"inputTokens": PRIVATE_TEXT}}, {"currency": "USD"},
                                  {"last": {"prompt": PRIVATE_TEXT}}, {"modelContextWindow": 0}])
def test_closed_native_usage_shape_never_publishes_untyped_fields(transport, usage):
    _start(transport)
    with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$"):
        _turn(transport, usage=usage)


@pytest.mark.parametrize("change", ["write-failed", "short-write", "flush-failed", "missing-response", "wrong-thread", "wrong-turn",
                                   "wrong-success", "usage-correlation", "double-finish", "double-install"])
def test_incomplete_or_duplicated_observation_never_completes(transport, monkeypatch, change):
    def fail(*args):
        raise OSError(PRIVATE_TEXT)

    if change in ("write-failed", "short-write", "flush-failed"):
        if change == "flush-failed":
            monkeypatch.setattr(transport.pipe, "flush", fail)
        else:
            monkeypatch.setattr(transport.pipe, "write", fail if change == "write-failed" else lambda _: 0)
        with pytest.raises(wire.PilotWireReceiptRefused):
            transport.client._write_message(_thread_request())
        assert transport.observer.requests == {}
        return
    if change == "double-install":
        with pytest.raises(wire.PilotWireReceiptRefused):
            wire.install_runtime_observer(transport.codex, transport.observer)
        return
    _start(transport)
    _turn(transport)
    if change == "usage-correlation":
        transport.client._coerce_notification("thread/tokenUsage/updated", {
            "threadId": "other", "turnId": "turn-private", "tokenUsage": USAGE})
    elif change == "missing-response":
        transport.observer.responses.remove(wire._correlation("rpc-turn"))
    elif change == "double-finish":
        _finish(transport)
    with pytest.raises(wire.PilotWireReceiptRefused):
        transport.observer.finish(success=change != "wrong-success",
            thread_id="wrong" if change == "wrong-thread" else "thread-private",
            turn_id="wrong" if change == "wrong-turn" else "turn-private")


@pytest.fixture
def case(capture_seed, tmp_path, monkeypatch):
    return _fresh(capture_seed, tmp_path, monkeypatch)


def _session(case):
    return wire.PilotWireReceiptSession(sources=case.context, workspace=case.workspace,
                                       dataset_root=case.context.input_bundle, verified_capture=_verify(case))


def _begin(session, task_id, *, attempt=0, override=None):
    session.arm_task(task_id, attempt)
    row = next(row for row in session.prepared["tasks"] if row["task_id"] == task_id)
    prompt = session.prepared["condition_a"]["prompt"]
    provider = SimpleNamespace(model=REQUESTED["deployment"], provider_id="gdpval-foundry", reasoning_effort="max",
        model_context_window=1_000_000, request_max_retries=0, stream_max_retries=0,
        auth_module=pilot.DEFAULT_AUTH_MODULE, auth_scope=pilot.DIRECT_TOKEN_SCOPE, query_params={},
        endpoint="https://fixture-foundry.services.ai.azure.com/openai/v1/")
    options = dict(task_id=task_id, run_id=pilot.RUN_ID, condition_name="condition_a", task_prompt=row["instruction"],
        occupation=row["occupation"], experiment_prompt={"system": prompt.get("system", "You are a helpful assistant."),
            **{key: prompt.get(key) for key in ("prefix", "body", "suffix")}}, perception_text=None,
        reference_files=[session.dataset_root / value["path"] for value in row["reference_file_records"]], provider=provider)
    options.update(override or {})
    return session.begin_task(**options)


def _task(session, task_id, *, attempt=0, success=True):
    observer = _begin(session, task_id, attempt=attempt)
    fake = _transport(observer, thread_id=f"thread-{task_id}-{attempt}", turn_id=f"turn-{task_id}-{attempt}")
    _start(fake)
    _turn(fake, success=success)
    linkage = session.finish_task(observer, success=success, thread_id=fake.thread_id, turn_id=fake.turn_id)
    return {"success": success, "pilot_wire_receipt": linkage}


def test_five_task_bundle_real_upstream_verification_ready_last_and_no_live_clear(case, monkeypatch, capsys):
    original = wire._write_no_clobber
    writes = []

    def write(path, data):
        assert not (case.workspace / wire.DIRECTORY / wire.READY_PATH).exists()
        writes.append(path.name)
        return original(path, data)

    monkeypatch.setattr(wire, "_write_no_clobber", write)
    before = dict(_tree(case.parent))
    session = _session(case)
    initial_linkage = deepcopy(session.linkage)
    for task_id in TASK_IDS:
        result = _task(session, task_id)
        session.accept_task(task_id=task_id, attempt_index=0, result=result)
    linkage = session.finalize(TASK_IDS)
    document = wire.verify_pilot_wire_receipts(session)
    assert document["task_ids"] == TASK_IDS and list(document["receipts"]) == sorted(TASK_IDS)
    assert len(session.files) == 5 and writes[0] == wire.RESERVATION and writes[-1] == wire.READY_PATH
    assert linkage["sha256"] == wire._digest(session.ready)["sha256"]
    assert session.ready == wire._bytes(document)
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    assert document["live_inference_identity_and_wire_unverified"] is True
    for task_id, entries in document["receipts"].items():
        receipt = json.loads((case.workspace / entries[0]["path"]).read_bytes())
        assert receipt["task"]["task_id"] == task_id and receipt["task_order"] == TASK_IDS
        assert receipt["prepared_capture"] == initial_linkage
        assert set(receipt["prepared_capture"]["upstream_bundles"]) == {"evidence", "identity", "config", "input", "deployment"}
        assert receipt["attempt_index"] == 0 and receipt["retry_kind"] == "initial"
        assert receipt["launch_allowed"] is receipt["full_220_allowed"] is False
    report = pilot.inspect_plan(case.plan, **vars(case.context), capture_workspace=case.workspace)
    assert report["launch_blockers"] == ["native_call_and_token_limits_unresolved", "live_inference_identity_and_wire_unverified",
                                       "foundry_usage_and_tariff_mapping_unverified", "native_sandbox_and_result_bundle_host_unverified"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    public = session.ready + b"".join(session.files.values()) + wire._bytes(report)
    assert PRIVATE_TEXT.encode() not in public and str(case.parent).encode() not in public
    assert PRIVATE.encode() not in public and all(value not in public for value in RAW_IDS)
    assert all(path.stat().st_nlink == 1 for path in session.root.iterdir())
    after = dict(_tree(case.parent))
    assert all(after[name] == data for name, data in before.items())
    assert PRIVATE_TEXT not in capsys.readouterr().out
    (session.root / wire.READY_PATH).write_bytes(session.ready + b" ")
    with pytest.raises(wire.PilotWireReceiptRefused):
        wire.verify_pilot_wire_receipts(session)


@pytest.mark.parametrize("change", ["capture", "prepared", "evidence", "identity", "config", "input", "deployment", "candidate", "source"])
def test_each_current_upstream_drift_refuses_task_acceptance(case, change):
    session = _session(case)
    result = _task(session, TASK_IDS[0])
    names = {"capture": case.workspace / capture.CAPTURE_PATH, "prepared": case.workspace / capture.PREPARED_PATH,
             "evidence": case.parent / "evidence/foundry-pilot-evidence-ready.json",
             "identity": case.parent / "identity/foundry-pilot-identity-plan.json",
             "config": case.parent / "configs/pilot-config-bundle-ready.json",
             "input": case.parent / "inputs/pilot-input-bundle-ready.json",
             "deployment": case.parent / "deployment/pilot-deployment-binding-ready.json",
             "candidate": case.candidate,
             "source": pilot.ROOT / "batch-runner/core/codex_runner.py"}
    path = names[change]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(wire.PilotWireReceiptRefused):
        session.accept_task(task_id=TASK_IDS[0], attempt_index=0, result=result)
    assert not (session.root / wire.READY_PATH).exists()


@pytest.mark.parametrize("change", ["missing", "digest", "request-digest", "attempt", "run", "upstream", "extra", "hardlink", "symlink", "reservation"])
def test_disk_receipt_forgery_and_links_cannot_replace_owned_observation(case, change):
    session = _session(case)
    result = _task(session, TASK_IDS[0])
    path = case.workspace / result["pilot_wire_receipt"]["path"]
    if change == "missing":
        path.unlink()
    elif change == "extra":
        (session.root / "extra.json").write_bytes(b"{}")
    elif change == "hardlink":
        os.link(path, case.parent / "alias")
    elif change == "symlink":
        alias = case.parent / "alias"
        path.rename(alias)
        path.symlink_to(alias)
    elif change == "reservation":
        session.reserved.write_bytes(b"{}")
    elif change == "digest":
        result["pilot_wire_receipt"]["sha256"] = "f" * 64
    else:
        value = json.loads(path.read_bytes())
        if change == "request-digest":
            value["transport"]["requests"]["turn/start"]["serialized_utf8"]["sha256"] = "f" * 64
        elif change == "run":
            value["run_id"] = "other"
        elif change == "attempt":
            value["attempt_index"] = 2
        else:
            value["prepared_capture"]["sha256"] = "f" * 64
        path.write_bytes(wire._bytes(value))
        # Rehashing a forged disk file is not a new runtime observation.
        result["pilot_wire_receipt"].update(wire._digest(path.read_bytes()))
    with pytest.raises(wire.PilotWireReceiptRefused):
        session.accept_task(task_id=TASK_IDS[0], attempt_index=0, result=result)
    assert not (session.root / wire.READY_PATH).exists()


@pytest.mark.parametrize("change", ["run", "condition", "task", "prompt", "perception", "stale-sha", "as-of", "retry-index"])
def test_wrong_identity_or_override_never_reaches_transport(case, change):
    session = _session(case)
    if change in ("stale-sha", "as-of"):
        session.sources = replace(session.sources, **({"reviewed_source_sha": "f" * 40} if change == "stale-sha" else {"as_of": "2099-01-01T00:00:00Z"}))
    overrides = {"run": {"run_id": "other"}, "condition": {"condition_name": "condition_b"},
                 "task": {"task_id": "unregistered"}, "prompt": {"task_prompt": PRIVATE_TEXT},
                 "perception": {"perception_text": PRIVATE_TEXT}}
    with pytest.raises(wire.PilotWireReceiptRefused):
        _begin(session, TASK_IDS[0], attempt=1 if change == "retry-index" else 0, override=overrides.get(change))
    assert session.files == {} and not (session.root / wire.READY_PATH).exists()


def test_infrastructure_attempt_identity_and_success_cannot_be_replayed(case):
    session = _session(case)
    for attempt in (0, 1):
        result = _task(session, TASK_IDS[0], attempt=attempt, success=attempt == 1)
        session.accept_task(task_id=TASK_IDS[0], attempt_index=attempt, result=result)
    assert len(session.files) == 2
    assert [json.loads(data)["retry_kind"] for data in session.files.values()] == ["initial", "infrastructure"]
    with pytest.raises(wire.PilotWireReceiptRefused):
        session.accept_task(task_id=TASK_IDS[0], attempt_index=1, result=result)
    with pytest.raises(wire.PilotWireReceiptRefused):
        session.arm_task(TASK_IDS[0], 2)
    with pytest.raises(wire.PilotWireReceiptRefused):
        session.finalize(TASK_IDS)


@pytest.mark.parametrize("change", ["destination", "reservation", "symlink", "parent-link", "traversal", "partial", "write-failure", "mid-write-drift"])
def test_no_clobber_paths_and_failed_partials_are_never_adopted(case, monkeypatch, change):
    if change in ("destination", "reservation", "symlink", "parent-link", "traversal"):
        if change == "destination":
            (case.workspace / wire.DIRECTORY).mkdir()
        elif change == "reservation":
            (case.workspace / wire.RESERVATION).write_bytes(b"{}")
        elif change == "symlink":
            (case.workspace / wire.DIRECTORY).symlink_to(case.parent, target_is_directory=True)
        elif change == "parent-link":
            alias = case.parent / "workspace-alias"
            alias.symlink_to(case.workspace, target_is_directory=True)
            case.workspace = alias
        else:
            case.workspace = case.workspace / ".." / "workspace"
        with pytest.raises((wire.PilotWireReceiptRefused, capture.PilotInputCaptureRefused)):
            _session(case)
        return
    session = _session(case)
    if change == "partial":
        (session.root / "partial.json").write_bytes(b"{}")
    else:
        writer = wire._write_no_clobber

        def altered(path, data):
            if change == "write-failure":
                raise OSError(PRIVATE_TEXT)
            writer(path, data)
            capture_path = case.workspace / capture.CAPTURE_PATH
            capture_path.write_bytes(capture_path.read_bytes() + b" ")

        monkeypatch.setattr(wire, "_write_no_clobber", altered)
    with pytest.raises(wire.PilotWireReceiptRefused):
        _task(session, TASK_IDS[0])
    assert session.reserved.exists() and session.root.exists() and not (session.root / wire.READY_PATH).exists()
    with pytest.raises((wire.PilotWireReceiptRefused, capture.PilotInputCaptureRefused)):
        _session(case)
    with pytest.raises(wire.PilotWireReceiptRefused):
        wire.verify_pilot_wire_receipts(session)


@pytest.mark.parametrize("value", [None, {}, "pilot-wire-receipts-ready.json"])
def test_missing_or_disk_only_witness_is_not_live_evidence(value):
    with pytest.raises(wire.PilotWireReceiptRefused):
        wire.verify_pilot_wire_receipts(value)


@pytest.mark.parametrize("kwargs", [{}, {"pilot_wire_receipts": None}])
def test_legacy_runner_absent_and_null_do_not_install_or_serialize_receipts(kwargs, monkeypatch):
    provider = object.__new__(CodexProviderSettings)
    runner = object.__new__(codex_runner.CodexAgentRunner)
    REAL_INIT(runner, provider, verify_runtime=False, preflight_auth=False, run_id="legacy", **kwargs)
    assert runner.pilot_wire_receipts is None
    assert not list(Path(".").glob(wire.DIRECTORY))
    # The no-task result path remains the same bytes for absent and null.
    runner.provider = SimpleNamespace(model="legacy")
    result = runner.run("text", model="different")
    assert "pilot_wire_receipt" not in result
    assert result == runner._failure(
        "this Codex run place is configured for deployment 'legacy' and was asked for 'different'; "
        "refusing rather than calling a different model than the one the run will be recorded against",
        category="model_mismatch")


@pytest.mark.parametrize("boundary", ["constructor", "run", "open_runtime", "task-acceptance"])
def test_registered_missing_session_refuses_before_auth_or_task_creation(boundary, monkeypatch):
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.run_id = pilot.RUN_ID
    runner.pilot_wire_receipts = None
    touched = []

    def forbidden(*args, **kwargs):
        touched.append("runtime")
        raise AssertionError("runtime must not be reached")

    monkeypatch.setattr(codex_runner, "require_pinned_runtime", forbidden)
    monkeypatch.setattr(codex_runner.CodexWorkspace, "create", forbidden)
    monkeypatch.setattr(runner, "require_a_usable_auth_command", forbidden)
    with pytest.raises(wire.PilotWireReceiptRefused):
        if boundary == "constructor":
            REAL_INIT(runner, None, run_id=pilot.RUN_ID)
        elif boundary == "run":
            runner.run("text", run_id=pilot.RUN_ID)
        elif boundary == "open_runtime":
            runner.open_runtime(None)
        else:
            step2._execute_single_task({"task_id": TASK_IDS[0]}, {}, None, "codex_foundry", None,
                                      REQUESTED["deployment"], run_id=pilot.RUN_ID)
    assert touched == []


def test_native_result_host_step2_order_and_final_acceptance_are_not_optional_for_registered_path():
    tree = ast.parse(Path(step2.__file__).read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    text = ast.unparse(functions["_run_inference_impl"])
    assert text.index("verified_input_capture = _pilot_input_gate") < text.index("pilot_wire_receipts = PilotWireReceiptSession")
    assert text.index("pilot_wire_receipts = PilotWireReceiptSession") < text.index("_require_host_may_carry_a_benchmark_run")
    assert text.index("pilot_wire_receipts = PilotWireReceiptSession") < text.index("AzureAIRouteSettings.from_env")
    assert text.index("pilot_native_result_host = PilotNativeResultHostSession") < text.index("AzureAIRouteSettings.from_env")
    assert text.index("pilot_wire_receipts.finalize") < text.index("pilot_native_result_host.publish_result")
    assert text.index("pilot_wire_receipts.finalize") < text.index("final_output['result_fingerprint']")
    assert "run_identity = PilotInputCapture.RUN_ID" in text
    assert "'pilot_attempt_index': infra_attempt" in text
    text = ast.unparse(functions["_execute_single_task"])
    assert text.index("pilot_wire_receipts.arm_task") < text.index("executor.execute")
    assert text.index("native_result_host_for") < text.index("executor.execute")
    assert text.index("executor.execute") < text.index("pilot_host.accept_task") < text.index("pilot_host.save_task") < text.index("_save_files")
    acceptance = ast.unparse(ast.parse(Path(native.__file__).read_text()))
    assert acceptance.index("_runner_digest(result) == witness.result_digest") < acceptance.index("self.wire.accept_task")
    assert "pilot_native_result_host.require_absent_task_output" in ast.unparse(functions["_run_inference_impl"])
    assert pilot.WIRE_RECEIPT["clears_live_identity_and_wire_blocker"] is False
    assert "live_inference_identity_and_wire_unverified" in pilot.LAUNCH_BLOCKERS


@pytest.mark.parametrize("missing", [False, True])
def test_native_result_host_step2_real_task_acceptance_precedes_file_acceptance(case, monkeypatch, missing):
    session = _session(case)
    host = native.PilotNativeResultHostSession(session)
    task = session.prepared["tasks"][0]
    events = []
    condition = session.prepared["condition_a"]
    provider = SimpleNamespace(model=REQUESTED["deployment"], provider_id="gdpval-foundry", reasoning_effort="max",
        model_context_window=1_000_000, request_max_retries=0, stream_max_retries=0,
        auth_module=pilot.DEFAULT_AUTH_MODULE, auth_scope=pilot.DIRECT_TOKEN_SCOPE, query_params={},
        endpoint="https://fixture-foundry.services.ai.azure.com/openai/v1/")

    def execute(**kwargs):
        events.append("synthetic-transport")
        observer = session.begin_task(**{key: kwargs[key] for key in (
            "task_id", "run_id", "condition_name", "task_prompt", "occupation", "experiment_prompt",
            "perception_text", "reference_files")}, provider=provider)
        workspace = _native_workspace(case, session, task["task_id"], 0)
        witness = host.begin_task(observer, workspace)
        fake = _transport(observer, workspace=workspace.workspace)
        _start(fake)
        _turn(fake)
        files = host.collect_deliverables(witness, workspace)
        linkage = session.finish_task(observer, success=True, thread_id=fake.thread_id, turn_id=fake.turn_id)
        result = {"success": True, "files": files, "text": "synthetic result", "pilot_wire_receipt": linkage}
        host.finish_task(witness, result=result)
        if missing:
            del result["pilot_wire_receipt"]
        return result

    accept = session.accept_task

    def accepted(**kwargs):
        accept(**kwargs)
        events.append("verified-receipt")

    monkeypatch.setattr(session, "accept_task", accepted)
    save = host.save_task

    def saved(**kwargs):
        result = save(**kwargs)
        events.append("save")
        return result

    monkeypatch.setattr(host, "save_task", saved)
    monkeypatch.setattr(step2, "_save_files", lambda *args, **kwargs: pytest.fail("pilot used overwriting legacy saver"))
    options = dict(run_id=pilot.RUN_ID, condition_name="condition_a", pilot_wire_receipts=session,
                   upload_root=case.workspace / "upload")
    if missing:
        with pytest.raises(wire.PilotWireReceiptRefused):
            step2._execute_single_task(task, condition, SimpleNamespace(execute=execute), "codex_foundry", None,
                                      REQUESTED["deployment"], **options)
        assert events == ["synthetic-transport"]
    else:
        step2._execute_single_task(task, condition, SimpleNamespace(execute=execute), "codex_foundry", None,
                                  REQUESTED["deployment"], **options)
        assert events == ["synthetic-transport", "verified-receipt", "save"]


@pytest.mark.parametrize("wrong_account", [False, True])
def test_native_result_host_runner_passes_owned_observer_and_finishes_before_cleanup(case, monkeypatch, wrong_account, capsys):
    session = _session(case)
    host = native.PilotNativeResultHostSession(session)
    task = session.prepared["tasks"][0]
    session.arm_task(task["task_id"], 0)
    provider = SimpleNamespace(model=REQUESTED["deployment"], provider_id="gdpval-foundry", reasoning_effort="max",
        model_context_window=1_000_000, request_max_retries=0, stream_max_retries=0,
        auth_module=pilot.DEFAULT_AUTH_MODULE, auth_scope=pilot.DIRECT_TOKEN_SCOPE, query_params={},
        endpoint="https://fixture-foundry.services.ai.azure.com/openai/v1/")
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.run_id, runner.condition_name = pilot.RUN_ID, "condition_a"
    runner.provider, runner.pilot_wire_receipts = provider, session
    events = []

    def cleanup():
        assert len(session.files) == 1
        assert host.witnesses[(task["task_id"], 0)].result_digest is not None
        events.append("cleanup-after-receipt")

    workspace = _native_workspace(case, session, task["task_id"], 0, stage=False)
    monkeypatch.setattr(workspace, "cleanup", cleanup)
    monkeypatch.setattr(codex_runner.CodexWorkspace, "create", lambda **kwargs: workspace)

    def turn(**kwargs):
        assert kwargs["task_text"] == kwargs["pilot_wire_observer"].task_text
        fake = _transport(kwargs["pilot_wire_observer"], workspace=workspace.workspace)
        _start(fake)
        _turn(fake)
        files = host.collect_deliverables(kwargs["pilot_host_witness"], workspace)
        return codex_runner.CodexRunOutcome(success=True, text="synthetic", files=files,
                                           thread_id=fake.thread_id, turn_id=fake.turn_id)

    monkeypatch.setattr(runner, "_run_one_turn", turn)
    prompt = session.prepared["condition_a"]["prompt"]

    def run():
        return runner.run(task["instruction"], model=REQUESTED["deployment"],
            reference_files=[session.dataset_root / record["path"] for record in task["reference_file_records"]],
            occupation=task["occupation"], experiment_prompt={"system": prompt.get("system", "You are a helpful assistant."),
                **{key: prompt.get(key) for key in ("prefix", "body", "suffix")}},
            run_id=pilot.RUN_ID, condition_name="condition_a", task_id=task["task_id"])

    if wrong_account:
        provider.endpoint = "https://wrong-account.services.ai.azure.com/openai/v1/"

        def forbidden(**kwargs):
            events.append("runtime-boundary")
            raise AssertionError("wrong account reached workspace/auth/client")

        monkeypatch.setattr(codex_runner.CodexWorkspace, "create", forbidden)
        monkeypatch.setattr(runner, "open_runtime", forbidden)
        with pytest.raises(wire.PilotWireReceiptRefused) as refused:
            run()
        assert str(refused.value) == wire.REFUSAL
        output = capsys.readouterr()
        assert provider.endpoint not in output.out + output.err
        assert all(value.decode() not in output.out + output.err for value in RAW_IDS)
        assert events == [] and session.files == {} and session.active == {}
        assert not (session.root / wire.READY_PATH).exists()
        return

    result = run()
    host.accept_task(task_id=task["task_id"], attempt_index=0, result=result)
    assert result["success"] and events == ["cleanup-after-receipt"]


def _native_workspace(case, session, task_id, attempt, *, stage=True):
    root = case.parent / f"native-{task_id}-{attempt}"
    root.mkdir(mode=0o700)
    for name in ("workspace", "codex_home", "home"):
        (root / name).mkdir(mode=0o700)
    workspace = codex_runner.CodexWorkspace(root, root / "workspace", root / "codex_home", root / "home")
    if stage:
        task = next(row for row in session.prepared["tasks"] if row["task_id"] == task_id)
        workspace.stage_references([session.dataset_root / row["path"] for row in task["reference_file_records"]])
    return workspace


def _native_start(case, host, task_id=TASK_IDS[0], *, attempt=0):
    observer = _begin(host.wire, task_id, attempt=attempt)
    workspace = _native_workspace(case, host.wire, task_id, attempt)
    witness = host.begin_task(observer, workspace)
    fake = _transport(observer, workspace=workspace.workspace, thread_id=f"thread-{task_id}-{attempt}", turn_id=f"turn-{task_id}-{attempt}")
    _start(fake)
    return SimpleNamespace(host=host, observer=observer, witness=witness, workspace=workspace, fake=fake,
                           task_id=task_id, attempt=attempt)


def _native_finish(state, *, success=True, output=True, text=PRIVATE_TEXT):
    if output:
        (state.workspace.workspace / "answer").mkdir()
        (state.workspace.workspace / "answer" / "result.txt").write_bytes(PRIVATE_TEXT.encode())
    _turn(state.fake, success=success)
    files = state.host.collect_deliverables(state.witness, state.workspace)
    linkage = state.host.wire.finish_task(state.observer, success=success,
                                         thread_id=state.fake.thread_id, turn_id=state.fake.turn_id)
    result = {"success": success, "files": files, "text": text if success else "", "pilot_wire_receipt": linkage}
    if not success:
        result.update(error="pilot_task_failed", error_category="timeout")
    state.host.finish_task(state.witness, result=result)
    return result


def _native_accept(case, state, result):
    host = state.host
    options = {"task_id": state.task_id, "attempt_index": state.attempt}
    host.accept_task(**options, result=result)
    saved = host.save_task(**options, result=result, upload_root=case.workspace / "upload") if result["success"] else []
    task = next(row for row in host.wire.prepared["tasks"] if row["task_id"] == state.task_id)
    no_output = result["success"] and task["needs_files"] and not saved
    row = {"task_id": state.task_id, "status": "success" if result["success"] and not no_output else "error",
           "content": result["text"], "deliverable_text": result["text"] if result["success"] else None,
           "deliverable_files": saved, "model": REQUESTED["deployment"], "usage": None,
           "observability": step2._build_execution_observability(result, []),
           "latency_ms": 1, "timestamp": "2026-09-20T00:00:00Z"}
    if no_output:
        row["error"] = "needs_files=True but no deliverable files produced"
    elif not result["success"]:
        row.update(error=result["error"], failure_evidence=None)
    return host.record_step2_result(**options, row=row, upload_root=case.workspace / "upload")


def _native_payload(case, host):
    rows = []
    for task_id in TASK_IDS:
        state = _native_start(case, host, task_id)
        rows.append(_native_accept(case, state, _native_finish(state)))
    rows = step2._public_persisted_results(step2.bind_deliverable_file_records(rows, case.workspace / "upload"))
    return {**{key: host.wire.prepared[key] for key in ("experiment_id", "publication_generation", "experiment_name", "source", "prepared_fingerprint")},
            "condition": host.wire.prepared["condition_a"]["name"], "model": REQUESTED["deployment"],
            "started_at": "2026-09-20T00:00:00Z", "completed_at": "2026-09-20T00:01:00Z",
            "run_id": pilot.RUN_ID, "condition_identity": "condition_a", "execution_mode": "codex_foundry",
            "ordered_task_ids": TASK_IDS, "resume_rounds_used": 0, "pre_execution_input_capture": host.wire.linkage,
            "pilot_wire_receipts": host.wire.finalize(TASK_IDS), "results": rows,
            "summary": {"total": 5, "success": 5, "error": 0, "qa_failed": 0}}


def _native_publish(case, host, payload):
    return host.publish_result(payload, output_path=case.workspace / "step2_inference_results_condition_a.json",
                               legacy_output_path=case.workspace / "step2_inference_results.json",
                               upload_root=case.workspace / "upload")


def test_native_result_host_five_task_real_verifiers_ready_last_and_private_result_digest(case, monkeypatch, capsys, offline_only):
    host = native.PilotNativeResultHostSession(_session(case))
    writes, original = [], native._write_no_clobber

    def write(path, data):
        assert not (host.root / native.READY_PATH).exists()
        writes.append(path)
        original(path, data)

    monkeypatch.setattr(native, "_write_no_clobber", write)
    payload = _native_payload(case, host)
    # Exercise the same closed final-result validator without repeating five
    # expensive real upstream preparations for each scalar/order mutation.
    for field in ("run", "order", "missing-task", "summary", "accepted-row", "file-record",
                  "observability-category", "observability-codex", "observability-preprocessors"):
        changed = deepcopy(payload)
        if field == "run":
            changed["run_id"] = "other"
        elif field == "order":
            changed["results"].reverse()
        elif field == "missing-task":
            changed["results"].pop()
        elif field == "summary":
            changed["summary"]["success"] = 4
        elif field == "accepted-row":
            changed["results"][0]["content"] += " forged"
        elif field == "file-record":
            changed["results"][0]["deliverable_file_records"][0]["sha256"] = "0" * 64
        elif field == "observability-category":
            changed["results"][0]["observability"]["error_category"] = "timeout"
        elif field == "observability-codex":
            changed["results"][0]["observability"]["codex"] = {"fresh_session": False}
        else:
            changed["results"][0]["observability"]["preprocessors"] = [{"status": "forged"}]
        with pytest.raises(native.PilotNativeResultHostRefused):
            host._final_rows(changed)
    before = native.inference_result_fingerprint(payload)
    linked = _native_publish(case, host, payload)
    document = native.verify_pilot_native_result_host(host)
    assert writes[-1] == host.root / native.READY_PATH and writes[-2].name == "step2_inference_results.json"
    assert len(document["receipts"]) == 5 and document["task_ids"] == TASK_IDS
    assert document["result_payload_before_host_sha256"] == before
    assert native.inference_result_fingerprint(linked) == linked["result_fingerprint"] != before
    assert linked[native.LINK]["sha256"] == wire._digest(host.ready)["sha256"]
    assert all(path.read_bytes() == wire._bytes(linked) for path in host.results)
    assert all(path.stat().st_nlink == 1 for path in writes)
    receipts = [json.loads(value) for value in host.files.values()]
    for receipt in receipts:
        assert receipt["selected_policy"] == {"sandbox": "workspace-write", "approval": "never", "source": "observed_app_server_thread_start"}
        assert receipt["remote_or_kernel_isolation"] == "not_attested"
        assert receipt["collected"] == [{"path": "answer/result.txt", **wire._digest(PRIVATE_TEXT.encode())}]
        assert receipt["saved_deliverables"] == [{"path": f"deliverable_files/{receipt['task_id']}/answer/result.txt", **wire._digest(PRIVATE_TEXT.encode())}]
        assert receipt["attempt_index"] == 0 and receipt["retry_kind"] == "initial"
        assert receipt["step2_status"] == "success" and receipt["output_state"] == "saved"
        assert receipt["launch_allowed"] is receipt["full_220_allowed"] is False
    public = b"".join([host.reservation, *host.files.values(), host.ready]).decode() + capsys.readouterr().out
    assert all(secret not in public for secret in (PRIVATE_TEXT, str(case.parent), "Authorization", "thread-", "rpc-thread",
                                                  "https://fixture-foundry", *(value.decode() for value in RAW_IDS)))
    assert document["eligible_blocker"] == native.BLOCKER and document["live_inference_identity_and_wire_unverified"] is True
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    report = pilot.inspect_plan(case.plan)
    assert native.BLOCKER in report["launch_blockers"] and "live_inference_identity_and_wire_unverified" in report["launch_blockers"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert case.plan["native_result_host"] == pilot.NATIVE_RESULT_HOST
    assert pilot.NATIVE_RESULT_HOST["offline_preflight_consumption"] is False
    assert offline_only == []
    with pytest.raises(native.PilotNativeResultHostRefused):
        _native_publish(case, host, payload)
    assert all(path.read_bytes() == wire._bytes(linked) for path in host.results)


@pytest.mark.parametrize("damage", ["capture", "wire", "wire-reservation", "host-reservation", "input", "source"])
def test_native_result_host_current_upstream_and_wire_bytes_required(case, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host)
    result = _native_finish(state)
    targets = {"capture": case.workspace / capture.CAPTURE_PATH,
               "wire": case.workspace / result["pilot_wire_receipt"]["path"],
               "wire-reservation": host.wire.reserved, "host-reservation": host.reserved,
               "input": case.parent / "inputs/pilot-input-bundle-ready.json",
               "source": pilot.ROOT / "batch-runner/core/codex_runner.py"}
    path = targets[damage]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(native.PilotNativeResultHostRefused, match="^pilot_native_result_host_refused$"):
        host.accept_task(task_id=state.task_id, attempt_index=0, result=result)
    assert host.failed and host.wire.failed and not (host.root / native.READY_PATH).exists()


@pytest.mark.parametrize("damage", ["text", "file", "name", "wire", "missing-wire", "attempt", "task", "extra"])
def test_native_result_host_rejects_forged_or_mismatched_runner_handoff(case, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host)
    result = _native_finish(state)
    task, attempt = state.task_id, 0
    if damage == "text":
        result["text"] += " changed"
    elif damage == "file":
        result["files"][0]["content"] += b" changed"
    elif damage == "name":
        result["files"][0]["filename"] = "/private/escaped"
    elif damage == "wire":
        result["pilot_wire_receipt"]["sha256"] = "0" * 64
    elif damage == "missing-wire":
        del result["pilot_wire_receipt"]
    elif damage == "attempt":
        attempt = 1
    elif damage == "task":
        task = TASK_IDS[1]
    else:
        result["command"] = PRIVATE_TEXT
    with pytest.raises(native.PilotNativeResultHostRefused):
        host.accept_task(task_id=task, attempt_index=attempt, result=result)


@pytest.mark.parametrize("damage", ["symlink", "hardlink", "fifo", "hidden", "runtime", "pyc", "collision", "unsafe-name", "directory-link", "containment"])
def test_native_result_host_strict_collection_refuses_unsafe_inputs_before_read(case, damage, monkeypatch, capsys):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host)
    root = state.workspace.workspace
    if damage == "symlink":
        (root / "answer.txt").symlink_to(case.candidate)
    elif damage == "hardlink":
        os.link(case.candidate, root / "answer.txt")
    elif damage == "fifo":
        os.mkfifo(root / "answer.txt")
    elif damage in {"hidden", "runtime", "pyc", "unsafe-name"}:
        name = {"hidden": ".secret", "runtime": "__pycache__", "pyc": "answer.pyc", "unsafe-name": "bad:name.txt"}[damage]
        (root / name).write_bytes(PRIVATE_TEXT.encode())
    elif damage == "collision":
        (root / "Answer.txt").write_bytes(b"one")
        (root / "answer.txt").write_bytes(b"two")
    elif damage == "directory-link":
        (root / "escaped").symlink_to(case.parent, target_is_directory=True)
    else:
        root.rename(root.with_name("displaced-workspace"))
        root.mkdir()
    with pytest.raises(native.PilotNativeResultHostRefused) as refusal:
        host.collect_deliverables(state.witness, state.workspace)
    assert str(refusal.value) == native.REFUSAL
    output = capsys.readouterr()
    assert PRIVATE_TEXT not in output.out + output.err and str(case.parent) not in str(refusal.value)
    assert not (host.root / native.READY_PATH).exists()


@pytest.mark.parametrize("replacement", ["fifo", "ancestor-link"])
def test_native_result_host_raced_runtime_leaf_cannot_block_or_escape(case, monkeypatch, replacement):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host)
    directory = state.workspace.workspace / "answer"
    directory.mkdir()
    path = directory / "result.txt"
    path.write_bytes(b"initial")
    original = os.open
    raced = []

    def opened(name, flags, *args, **kwargs):
        if not raced and kwargs.get("dir_fd") is not None:
            if replacement == "fifo" and name == "result.txt" and flags & os.O_NONBLOCK:
                path.rename(directory / "held-original")
                os.mkfifo(path)
                raced.append(name)
            elif replacement == "ancestor-link" and name == "answer":
                directory.rename(state.workspace.workspace / "held-original")
                directory.symlink_to(case.parent, target_is_directory=True)
                raced.append(name)
        return original(name, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", opened)
    with pytest.raises(native.PilotNativeResultHostRefused):
        host.collect_deliverables(state.witness, state.workspace)
    assert raced


@pytest.mark.parametrize("damage", ["seeded-answer", "relative-overlap", "upload-link", "upload-escape", "pre-auth-drift"])
def test_native_result_host_fresh_containment_and_pre_auth_gate(case, monkeypatch, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    if damage in {"upload-link", "upload-escape"}:
        if damage == "upload-link":
            (case.workspace / "upload").symlink_to(case.parent, target_is_directory=True)
        with pytest.raises(native.PilotNativeResultHostRefused):
            host.require_absent_task_output(TASK_IDS[0], case.parent if damage == "upload-escape" else case.workspace / "upload")
        return
    if damage == "pre-auth-drift":
        (case.workspace / capture.CAPTURE_PATH).write_bytes(b"changed before auth")
        with pytest.raises(native.PilotNativeResultHostRefused):
            native.native_result_host_for(host.wire)
        return
    observer = _begin(host.wire, TASK_IDS[0])
    if damage == "relative-overlap":
        monkeypatch.chdir(case.parent)
        root = Path("workspace/runtime-root")
        root.mkdir()
        for name in ("workspace", "codex_home", "home"):
            (root / name).mkdir()
        workspace = codex_runner.CodexWorkspace(root, root / "workspace", root / "codex_home", root / "home")
    else:
        workspace = _native_workspace(case, host.wire, TASK_IDS[0], 0)
        (workspace.workspace / "answer.txt").write_bytes(b"pre-populated answer")
    with pytest.raises(native.PilotNativeResultHostRefused):
        host.begin_task(observer, workspace)


@pytest.mark.parametrize("damage", ["bytes", "extra", "reference", "root"])
def test_native_result_host_post_collection_drift_is_refused_before_cleanup(case, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host, TASK_IDS[2] if damage == "reference" else TASK_IDS[0])
    target = state.workspace.workspace / "answer.txt"
    target.write_bytes(b"initial")
    _turn(state.fake)
    files = host.collect_deliverables(state.witness, state.workspace)
    link = host.wire.finish_task(state.observer, success=True, thread_id=state.fake.thread_id, turn_id=state.fake.turn_id)
    if damage == "bytes":
        target.write_bytes(b"changed")
    elif damage == "extra":
        (target.parent / "extra.txt").write_bytes(b"extra")
    elif damage == "reference":
        reference = state.workspace.workspace / state.workspace.staged_reference_names[0]
        reference.chmod(0o600)
        reference.write_bytes(b"changed reference")
    else:
        state.workspace.codex_home.rename(state.workspace.root / "displaced-runtime")
        state.workspace.codex_home.mkdir()
    with pytest.raises(native.PilotNativeResultHostRefused):
        host.finish_task(state.witness, result={"success": True, "text": "", "files": files, "pilot_wire_receipt": link})


@pytest.mark.parametrize("damage", ["missing-witness", "duplicate-collect", "duplicate-finish", "duplicate-accept", "different-session"])
def test_native_result_host_witness_is_owned_and_single_use(case, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    with pytest.raises(native.PilotNativeResultHostRefused):
        native.verify_pilot_native_result_host(host)
    state = _native_start(case, host)
    if damage == "missing-witness":
        with pytest.raises(native.PilotNativeResultHostRefused):
            host.collect_deliverables(None, state.workspace)
    elif damage == "duplicate-collect":
        host.collect_deliverables(state.witness, state.workspace)
        with pytest.raises(native.PilotNativeResultHostRefused):
            host.collect_deliverables(state.witness, state.workspace)
    elif damage == "different-session":
        host.wire.native_host = SimpleNamespace()
        with pytest.raises(native.PilotNativeResultHostRefused):
            native.native_result_host_for(host.wire)
    else:
        result = _native_finish(state)
        if damage == "duplicate-finish":
            with pytest.raises(native.PilotNativeResultHostRefused):
                host.finish_task(state.witness, result=result)
        else:
            host.accept_task(task_id=state.task_id, attempt_index=0, result=result)
            with pytest.raises(native.PilotNativeResultHostRefused):
                host.accept_task(task_id=state.task_id, attempt_index=0, result=result)


@pytest.mark.parametrize("kind", ["root", "reservation", "symlink", "hardlink", "second-owner"])
def test_native_result_host_no_adoption_or_clobber(case, kind):
    session = _session(case)
    if kind == "root":
        (case.workspace / native.DIRECTORY).mkdir()
    elif kind == "reservation":
        (case.workspace / native.RESERVATION).write_bytes(b"partial")
    elif kind == "symlink":
        (case.workspace / native.DIRECTORY).symlink_to(case.parent, target_is_directory=True)
    elif kind == "hardlink":
        os.link(case.candidate, case.workspace / native.RESERVATION)
    else:
        native.PilotNativeResultHostSession(session)
    before = (case.candidate.read_bytes(), (case.workspace / capture.CAPTURE_PATH).read_bytes())
    with pytest.raises(native.PilotNativeResultHostRefused):
        native.PilotNativeResultHostSession(session)
    assert (case.candidate.read_bytes(), (case.workspace / capture.CAPTURE_PATH).read_bytes()) == before
    assert not (case.workspace / native.DIRECTORY / native.READY_PATH).exists()


@pytest.mark.parametrize("damage", ["saved-bytes", "saved-hardlink", "accepted-text", "accepted-status", "collision",
                                    "observability-category", "observability-codex"])
def test_native_result_host_binds_actual_step2_records_and_saved_bytes(case, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host)
    result = _native_finish(state)
    host.accept_task(task_id=state.task_id, attempt_index=0, result=result)
    upload = case.workspace / "upload"
    if damage == "collision":
        path = upload / "deliverable_files" / state.task_id
        path.mkdir(parents=True)
        (path / "keep.txt").write_bytes(b"do not delete")
        with pytest.raises(native.PilotNativeResultHostRefused):
            host.save_task(task_id=state.task_id, attempt_index=0, result=result, upload_root=upload)
        assert (path / "keep.txt").read_bytes() == b"do not delete"
        return
    saved = host.save_task(task_id=state.task_id, attempt_index=0, result=result, upload_root=upload)
    row = {"task_id": state.task_id, "status": "success", "deliverable_files": saved, "content": result["text"],
           "deliverable_text": result["text"], "model": REQUESTED["deployment"], "usage": None,
           "observability": step2._build_execution_observability(result, [])}
    if damage == "saved-bytes":
        (upload / saved[0]).write_bytes(b"altered")
    elif damage == "saved-hardlink":
        os.link(upload / saved[0], case.parent / "extra-link")
    elif damage == "accepted-text":
        row["content"] += " forged"
    elif damage == "observability-category":
        row["observability"]["error_category"] = "timeout"
    elif damage == "observability-codex":
        row["observability"]["codex"] = {"fresh_session": False}
    else:
        row["status"] = "error"
    with pytest.raises(native.PilotNativeResultHostRefused):
        host.record_step2_result(task_id=state.task_id, attempt_index=0, row=row, upload_root=upload)


@pytest.mark.parametrize("state_name", ["error", "no_output", "text_only"])
def test_native_result_host_records_error_and_no_output_without_inventing_success(case, state_name):
    host = native.PilotNativeResultHostSession(_session(case))
    state = _native_start(case, host)
    result = _native_finish(state, success=state_name != "error", output=False,
                            text=PRIVATE_TEXT if state_name == "text_only" else "")
    row = _native_accept(case, state, result)
    receipt = json.loads(next(iter(host.files.values())))
    assert receipt["output_state"] == state_name and receipt["saved_deliverables"] == []
    assert receipt["step2_status"] == row["status"]
    if state_name == "error":
        retry = _native_start(case, host, attempt=1)
        _native_accept(case, retry, _native_finish(retry))
        receipt = json.loads(list(host.files.values())[-1])
        assert receipt["retry_kind"] == "infrastructure" and receipt["attempt_index"] == 1
    assert not (host.root / native.READY_PATH).exists()


@pytest.mark.parametrize("damage", ["payload", "saved", "ready", "partial-publication"])
def test_native_result_host_final_payload_drift_and_partial_quarantine(case, monkeypatch, damage):
    host = native.PilotNativeResultHostSession(_session(case))
    payload = _native_payload(case, host)
    if damage == "partial-publication":
        original = native._write_no_clobber

        def write(path, data):
            original(path, data)
            if path.name == "step2_inference_results.json":
                (case.workspace / capture.CAPTURE_PATH).write_bytes(b"changed during publication")

        monkeypatch.setattr(native, "_write_no_clobber", write)
        with pytest.raises(native.PilotNativeResultHostRefused):
            _native_publish(case, host, payload)
        assert (case.workspace / "step2_inference_results_condition_a.json").is_file()
        assert host.reserved.is_file() and not (host.root / native.READY_PATH).exists()
        with pytest.raises(native.PilotNativeResultHostRefused):
            _native_publish(case, host, payload)
        return
    _native_publish(case, host, payload)
    if damage == "payload":
        path = next(iter(host.results))
        changed = json.loads(path.read_bytes())
        changed["results"][0]["content"] = "forged"
        changed["result_fingerprint"] = native.inference_result_fingerprint(changed)
        path.write_bytes(wire._bytes(changed))
    elif damage == "saved":
        (case.workspace / "upload" / payload["results"][0]["deliverable_files"][0]).write_bytes(b"drift")
    else:
        (host.root / native.READY_PATH).write_bytes(host.ready + b" ")
    with pytest.raises(native.PilotNativeResultHostRefused):
        native.verify_pilot_native_result_host(host)


@pytest.mark.parametrize("value", [None, {}, {"bundle_version": "pilot-native-result-host-ready-v1"}, "pilot-native-result-host-ready.json"])
def test_native_result_host_saved_json_cannot_replace_live_witness(value):
    with pytest.raises(native.PilotNativeResultHostRefused, match="^pilot_native_result_host_refused$"):
        native.verify_pilot_native_result_host(value)


@pytest.mark.parametrize("kwargs", [{}, {"pilot_wire_receipts": None}])
def test_native_result_host_legacy_absent_null_collector_and_result_shapes_unchanged(tmp_path, monkeypatch, kwargs):
    workspace = codex_runner.CodexWorkspace(tmp_path, tmp_path, tmp_path / "runtime", tmp_path / "home")
    (tmp_path / "ordinary.txt").write_bytes(b"ordinary")
    (tmp_path / ".hidden").write_bytes(b"legacy skipped")
    (tmp_path / "link").symlink_to(tmp_path / "ordinary.txt")
    assert workspace.collect_deliverables() == [{"filename": "ordinary.txt", "content": b"ordinary"}]
    monkeypatch.setattr(native, "native_result_host_for", lambda _: pytest.fail("legacy reached pilot host"))
    monkeypatch.setattr(step2, "_save_files", lambda *args, **options: [])
    task = {"task_id": "legacy-task", "instruction": "legacy input", "reference_files": [], "needs_files": False}
    result = step2._execute_single_task(task, {"prompt": {}}, SimpleNamespace(execute=lambda **_: {
        "success": True, "text": "legacy result", "files": []}), "codex_foundry", None, "legacy-model", **kwargs)
    assert result["status"] == "success" and result["content"] == "legacy result"
    assert not any("pilot" in key for key in result)
