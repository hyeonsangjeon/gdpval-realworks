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


def _transport(observer=None, *, thread_id="thread-private", turn_id="turn-private"):
    observer = observer or wire._TransportObservation(deepcopy(REQUESTED))
    if observer.task_text is None:
        observer.bind_task_text(PRIVATE_TEXT)
    observer.bind_runtime(workspace=Path("/private/task-workspace"), developer_instructions="private developer text")
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
    fake.client._write_message(_thread_request())
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
        endpoint="https://synthetic-resource.services.ai.azure.com/openai/v1/")
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
    assert report["launch_blockers"] == ["live_inference_identity_and_wire_unverified", "native_sandbox_and_result_bundle_host_unverified"]
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


def test_step2_order_and_final_acceptance_are_not_optional_for_registered_path():
    tree = ast.parse(Path(step2.__file__).read_text())
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    text = ast.unparse(functions["_run_inference_impl"])
    assert text.index("verified_input_capture = _pilot_input_gate") < text.index("pilot_wire_receipts = PilotWireReceiptSession")
    assert text.index("pilot_wire_receipts = PilotWireReceiptSession") < text.index("_require_host_may_carry_a_benchmark_run")
    assert text.index("pilot_wire_receipts = PilotWireReceiptSession") < text.index("AzureAIRouteSettings.from_env")
    assert text.index("pilot_wire_receipts.finalize") < text.index("final_output['result_fingerprint']")
    assert "run_identity = PilotInputCapture.RUN_ID" in text
    assert "'pilot_attempt_index': infra_attempt" in text
    text = ast.unparse(functions["_execute_single_task"])
    assert text.index("pilot_wire_receipts.arm_task") < text.index("executor.execute")
    assert text.index("executor.execute") < text.index("pilot_wire_receipts.accept_task") < text.index("_save_files")
    assert pilot.WIRE_RECEIPT["clears_live_identity_and_wire_blocker"] is False
    assert "live_inference_identity_and_wire_unverified" in pilot.LAUNCH_BLOCKERS


@pytest.mark.parametrize("missing", [False, True])
def test_step2_real_task_acceptance_precedes_file_acceptance(case, monkeypatch, missing):
    session = _session(case)
    task = session.prepared["tasks"][0]
    events = []
    condition = session.prepared["condition_a"]
    provider = SimpleNamespace(model=REQUESTED["deployment"], provider_id="gdpval-foundry", reasoning_effort="max",
        model_context_window=1_000_000, request_max_retries=0, stream_max_retries=0,
        auth_module=pilot.DEFAULT_AUTH_MODULE, auth_scope=pilot.DIRECT_TOKEN_SCOPE, query_params={},
        endpoint="https://synthetic-resource.services.ai.azure.com/openai/v1/")

    def execute(**kwargs):
        events.append("synthetic-transport")
        observer = session.begin_task(**{key: kwargs[key] for key in (
            "task_id", "run_id", "condition_name", "task_prompt", "occupation", "experiment_prompt",
            "perception_text", "reference_files")}, provider=provider)
        fake = _transport(observer)
        _start(fake)
        _turn(fake)
        linkage = session.finish_task(observer, success=True, thread_id=fake.thread_id, turn_id=fake.turn_id)
        result = {"success": True, "files": [], "text": "synthetic result"}
        if not missing:
            result["pilot_wire_receipt"] = linkage
        return result

    accept = session.accept_task

    def accepted(**kwargs):
        accept(**kwargs)
        events.append("verified-receipt")

    monkeypatch.setattr(session, "accept_task", accepted)
    monkeypatch.setattr(step2, "_save_files", lambda *args, **kwargs: events.append("save") or [])
    options = dict(run_id=pilot.RUN_ID, condition_name="condition_a", pilot_wire_receipts=session)
    if missing:
        with pytest.raises(wire.PilotWireReceiptRefused):
            step2._execute_single_task(task, condition, SimpleNamespace(execute=execute), "codex_foundry", None,
                                      REQUESTED["deployment"], **options)
        assert events == ["synthetic-transport"]
    else:
        step2._execute_single_task(task, condition, SimpleNamespace(execute=execute), "codex_foundry", None,
                                  REQUESTED["deployment"], **options)
        assert events == ["synthetic-transport", "verified-receipt", "save"]


def test_runner_passes_owned_observer_and_finishes_before_cleanup(case, monkeypatch):
    session = _session(case)
    task = session.prepared["tasks"][0]
    session.arm_task(task["task_id"], 0)
    provider = SimpleNamespace(model=REQUESTED["deployment"], provider_id="gdpval-foundry", reasoning_effort="max",
        model_context_window=1_000_000, request_max_retries=0, stream_max_retries=0,
        auth_module=pilot.DEFAULT_AUTH_MODULE, auth_scope=pilot.DIRECT_TOKEN_SCOPE, query_params={},
        endpoint="https://synthetic-resource.services.ai.azure.com/openai/v1/")
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.run_id, runner.condition_name = pilot.RUN_ID, "condition_a"
    runner.provider, runner.pilot_wire_receipts = provider, session
    events = []

    def cleanup():
        assert len(session.files) == 1
        events.append("cleanup-after-receipt")

    workspace = SimpleNamespace(staged_reference_names=(), stage_references=lambda _: None, cleanup=cleanup)
    monkeypatch.setattr(codex_runner.CodexWorkspace, "create", lambda **kwargs: workspace)

    def turn(**kwargs):
        assert kwargs["task_text"] == kwargs["pilot_wire_observer"].task_text
        fake = _transport(kwargs["pilot_wire_observer"])
        _start(fake)
        _turn(fake)
        return codex_runner.CodexRunOutcome(success=True, text="synthetic", thread_id=fake.thread_id, turn_id=fake.turn_id)

    monkeypatch.setattr(runner, "_run_one_turn", turn)
    prompt = session.prepared["condition_a"]["prompt"]
    result = runner.run(task["instruction"], model=REQUESTED["deployment"],
        reference_files=[session.dataset_root / record["path"] for record in task["reference_file_records"]],
        occupation=task["occupation"], experiment_prompt={"system": prompt.get("system", "You are a helpful assistant."),
            **{key: prompt.get(key) for key in ("prefix", "body", "suffix")}},
        run_id=pilot.RUN_ID, condition_name="condition_a", task_id=task["task_id"])
    session.accept_task(task_id=task["task_id"], attempt_index=0, result=result)
    assert result["success"] and events == ["cleanup-after-receipt"]
