"""Session-owned receipts for the pinned Codex app-server transport.

This is not an Azure HTTP observer. The pinned SDK exposes serialized stdio
requests, correlated app-server replies and native thread usage, but no Foundry
request ID or served model/version. Those facts remain unavailable; neither a
receipt nor its hashes clear the live wire/identity blocker. A saved document
cannot recreate the in-process witness required to accept a task result.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import gpt56_pilot_input_capture as capture
import gpt56_pilot_deployment_binding as deployment
import gpt56_sol_codex_pilot_preflight as pilot
from core.cost_receipts import make_call_id
from core.azure_ai_clients import EndpointKind, classify_endpoint
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

DIRECTORY = "pilot-wire-receipts"
READY_PATH = "pilot-wire-receipts-ready.json"
RESERVATION = DIRECTORY + ".reservation.json"
BOUNDARY = "codex_app_server_transport_not_foundry_http_or_served_identity"
REFUSAL = "pilot_wire_receipt_refused"
_bytes, _digest = capture._bytes, capture._digest
_USAGE_FIELDS = {"inputTokens", "cachedInputTokens", "cacheWriteInputTokens",
                 "outputTokens", "reasoningOutputTokens", "totalTokens"}


class PilotWireReceiptRefused(ValueError):
    def __init__(self) -> None:
        super().__init__(REFUSAL)


def _require(value: bool) -> None:
    if not value:
        raise PilotWireReceiptRefused()


@contextmanager
def _closed():
    try:
        yield
    except Exception:
        raise PilotWireReceiptRefused() from None


def _correlation(value: Any) -> str:
    _require(type(value) is str and 0 < len(value) <= 256)
    return _digest(value.encode("utf-8"))["sha256"]


def _unavailable() -> dict:
    return {"state": "not_available", "reason": "not_exposed_by_pinned_codex_route"}


class _TransportObservation:
    """One fresh task attempt. Private inputs never enter the receipt shape."""

    def __init__(self, requested: dict) -> None:
        self.requested = requested
        self.lock = threading.RLock()
        self.invalid = False
        self.installed = False
        self.sealed = False
        self.task_text = None
        self.runtime = None
        self.requests: dict[str, dict] = {}
        self.responses: set[str] = set()
        self.thread = None
        self.turn = None
        self.settings = None
        self.usage: list[dict] = []
        self.completion = None

    @contextmanager
    def guard(self):
        with self.lock, _closed():
            try:
                _require(not self.invalid and not self.sealed)
                yield
            except Exception:
                self.invalid = True
                raise PilotWireReceiptRefused() from None

    def bind_task_text(self, text: str) -> None:
        with self.guard():
            _require(self.task_text is None and type(text) is str and bool(text))
            self.task_text = text

    def bind_runtime(self, *, workspace: Path, developer_instructions: str | None) -> None:
        with self.guard():
            _require(self.runtime is None and self.task_text is not None)
            self.runtime = {"cwd": str(workspace), "developerInstructions": developer_instructions}

    def request(self, data: str) -> tuple[str, dict]:
        """Validate the actual serialized line, not a second serialization."""
        _require(type(data) is str and data.endswith("\n") and self.runtime is not None)
        message = json.loads(data)
        _require(type(message) is dict and set(message) == {"id", "method", "params"})
        method, params = message["method"], message["params"]
        _require(method in ("thread/start", "turn/start", "turn/interrupt") and method not in self.requests)
        rpc_id = _correlation(message["id"])
        _require(rpc_id not in {entry["request_id_sha256"] for entry in self.requests.values()})
        if method == "thread/start":
            expected = {"model": self.requested["deployment"], "modelProvider": self.requested["provider_id"],
                        "cwd": self.runtime["cwd"], "sandbox": "workspace-write", "approvalPolicy": "never"}
            if self.runtime["developerInstructions"] is not None:
                expected["developerInstructions"] = self.runtime["developerInstructions"]
            _require(params == expected and not self.requests)
        elif method == "turn/start":
            _require(self.thread is not None and type(params) is dict and set(params) == {"threadId", "input"})
            _require(_correlation(params["threadId"]) == self.thread
                     and params["input"] == [{"type": "text", "text": self.task_text}])
        else:
            _require(self.turn is not None and type(params) is dict and set(params) == {"threadId", "turnId"})
            _require(_correlation(params["threadId"]) == self.thread and _correlation(params["turnId"]) == self.turn)
        return method, {"request_id_sha256": rpc_id, "serialized_utf8": _digest(data.encode("utf-8"))}

    def response(self, message: dict) -> None:
        with self.guard():
            rpc_id = _correlation(message.get("id"))
            methods = [method for method, request in self.requests.items() if request["request_id_sha256"] == rpc_id]
            _require(len(methods) == 1 and rpc_id not in self.responses and "error" not in message)
            self.responses.add(rpc_id)
            result, method = message["result"], methods[0]
            if method == "thread/start":
                _require(result["model"] == self.requested["deployment"]
                         and result["modelProvider"] == self.requested["provider_id"]
                         and result.get("reasoningEffort") in (None, self.requested["reasoning_effort"]))
                self.thread = _correlation(result["thread"]["id"])
                self.settings = {"source": "app_server_thread_settings_not_served_identity",
                                 "model": result["model"], "provider_id": result["modelProvider"],
                                 "reasoning_effort": result.get("reasoningEffort")}
            elif method == "turn/start":
                self.turn = _correlation(result["turn"]["id"])

    def notification(self, method: str, params: Any) -> None:
        if method not in ("model/rerouted", "thread/tokenUsage/updated", "turn/completed"):
            return  # Never retain free-form output, error messages or tool events.
        with self.guard():
            _require(method != "model/rerouted" and type(params) is dict)
            thread = _correlation(params["threadId"])
            if method == "turn/completed":
                _require(self.completion is None)
                status = params["turn"]["status"]
                _require(status in ("completed", "failed", "interrupted"))
                self.completion = {"thread_id_sha256": thread, "turn_id_sha256": _correlation(params["turn"]["id"]),
                                   "status": status}
            else:
                usage = params["tokenUsage"]
                _require(type(usage) is dict and set(usage) <= {"total", "last", "modelContextWindow"})
                for role in ("total", "last"):
                    if role in usage:
                        _require(type(usage[role]) is dict and set(usage[role]) <= _USAGE_FIELDS)
                        _require(all(value is None or type(value) is int and value >= 0 for value in usage[role].values()))
                if "modelContextWindow" in usage:
                    value = usage["modelContextWindow"]
                    _require(value is None or type(value) is int and value > 0)
                self.usage.append({"thread_id_sha256": thread, "turn_id_sha256": _correlation(params["turnId"]),
                                   "native": json.loads(_bytes(usage))})

    def finish(self, *, success: bool, thread_id: str, turn_id: str) -> dict:
        with self.guard():
            _require(self.installed and type(success) is bool and self.completion is not None)
            _require(self.thread == _correlation(thread_id) and self.turn == _correlation(turn_id)
                     and {"thread/start", "turn/start"} <= set(self.requests)
                     and self.responses == {entry["request_id_sha256"] for entry in self.requests.values()})
            _require(all(row["thread_id_sha256"] == self.thread and row["turn_id_sha256"] == self.turn
                         for row in [self.completion, *self.usage]))
            _require(success == (self.completion["status"] == "completed"))
            result = {"scope": "codex_app_server_stdio_utf8_after_initialize",
                      "requests": self.requests, "correlation": self.completion,
                      "app_server_settings": self.settings,
                      "usage": {"state": "observed" if self.usage else "not_available", "unit": "tokens",
                                "source": "app_server_thread_usage_not_provider_billing",
                                "snapshots": self.usage, "model_call_count": _unavailable(), "pricing": _unavailable()},
                      "foundry_http_payload": _unavailable(), "foundry_request_id": _unavailable(),
                      "served_model": _unavailable(), "served_model_version": _unavailable(),
                      "served_deployment": _unavailable()}
            self.sealed = True
            self.task_text = self.runtime = None
            return json.loads(_bytes(result))


class _ObservedPipe:
    def __init__(self, pipe, observer: _TransportObservation):
        self.pipe, self.observer, self.pending = pipe, observer, None

    def write(self, data):
        with self.observer.guard():
            _require(self.pending is None)
            pending = self.observer.request(data)
            count = self.pipe.write(data)
            _require(type(count) is int and count == len(data))
            self.pending = pending
            return count

    def flush(self):
        with self.observer.guard():
            self.pipe.flush()
            _require(self.pending is not None)
            method, record = self.pending
            self.observer.requests[method] = record
            self.pending = None

    def __getattr__(self, name):
        return getattr(self.pipe, name)


def install_runtime_observer(codex, observer: _TransportObservation) -> None:
    """Instance-local pass-through hooks for openai-codex==0.147.0 only.

    Holding the observation lock across the SDK's write+flush prevents its
    reader from correlating an early response before the write is committed.
    No HTTP interception, second client, auth lookup or SDK defaulted usage.
    """
    with observer.guard():
        _require(not observer.installed)
        client = codex._client
        pipe = client._proc.stdin
        _require(pipe.encoding.lower().replace("-", "") == "utf8" and not isinstance(pipe, _ObservedPipe))
        write, response, notification = client._write_message, client._router.route_response, client._coerce_notification

        def observed_write(payload):
            with observer.guard():
                return write(payload)

        def observed_response(message):
            observer.response(message)
            return response(message)

        def observed_notification(method, params):
            observer.notification(method, params)
            return notification(method, params)

        client._proc.stdin = _ObservedPipe(pipe, observer)
        client._write_message = observed_write
        client._router.route_response = observed_response
        client._coerce_notification = observed_notification
        observer.installed = True


class PilotWireReceiptSession:
    """One run, exclusive files and a non-serializable in-process witness.

    The initial linkage is from Step 2's real capture gate. Publication and
    result acceptance re-run that verifier; no cached verdict waives drift.
    Disk-only receipts cannot be adopted, and there is no offline preflight
    option that can turn a synthetic transcript into live identity evidence.
    """

    def __init__(self, *, sources: capture.PilotCaptureSources, workspace: Path,
                 dataset_root: Path, verified_capture: dict):
        with _closed():
            self.sources, self.workspace, self.dataset_root = sources, capture._workspace(workspace, sources), dataset_root
            self.linkage = json.loads(_bytes(verified_capture))
            self.capture_data = _read_bytes(self.workspace / capture.CAPTURE_PATH,
                                           size=self.linkage["size"], sha256=self.linkage["sha256"])
            self.document = json.loads(self.capture_data)
            self.prepared = json.loads(_read_bytes(self.workspace / capture.PREPARED_PATH,
                                                   sha256=self.linkage["prepared_sha256"]))
            _require(self.linkage["run_id"] == pilot.RUN_ID == self.document["run_id"]
                     and self.document["task_ids"] == [row["task_id"] for row in self.prepared["tasks"]])
            self.root = self.workspace / DIRECTORY
            self.reserved = self.workspace / RESERVATION
            self.lock = threading.RLock()
            self.failed = False
            self.armed: dict[str, int] = {}
            self.active: dict[str, _TransportObservation] = {}
            self.thread_ids: set[str] = set()
            self.files: dict[str, bytes] = {}
            self.attempts: dict[str, list[dict]] = {task_id: [] for task_id in self.document["task_ids"]}
            self.ready: bytes | None = None
            self.reservation = _bytes({"reservation_version": "pilot-wire-reservation-v1", "run_id": pilot.RUN_ID,
                                       "prepared_capture": self.linkage, "launch_allowed": False, "full_220_allowed": False})
            with _held_parents(self.workspace, (DIRECTORY, RESERVATION)) as check:
                _require(not os.path.lexists(self.root) and not os.path.lexists(self.reserved))
                check()
                _write_no_clobber(self.reserved, self.reservation)
                check()
                parent_fd = os.open(self.workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    check()
                    os.mkdir(DIRECTORY, mode=0o700, dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
                check()
            metadata = self.root.stat()
            self.root_identity = (metadata.st_dev, metadata.st_ino)

    @contextmanager
    def _guard(self):
        with self.lock, _closed():
            try:
                _require(not self.failed)
                yield
            except Exception:
                self.failed = True
                raise PilotWireReceiptRefused() from None

    def _current(self) -> None:
        _require(capture.verify_pilot_input_capture(self.sources, workspace=self.workspace,
                                                  dataset_root=self.dataset_root) == self.linkage)
        _read_bytes(self.workspace / capture.CAPTURE_PATH, **_digest(self.capture_data))
        _read_bytes(self.reserved, **_digest(self.reservation))
        root = _root(self.root)
        metadata = root.stat()
        _require((metadata.st_dev, metadata.st_ino) == self.root_identity)
        expected = set(self.files) | ({READY_PATH} if self.ready is not None else set())
        _require({path.name for path in root.iterdir()} == expected)
        for name, data in self.files.items():
            _read_bytes(_path(root, name), **_digest(data))
        if self.ready is not None:
            _read_bytes(root / READY_PATH, **_digest(self.ready))

    def arm_task(self, task_id: str, attempt_index: int) -> None:
        """Use Step 2's actual zero-based infrastructure attempt, before auth."""
        with self._guard():
            _require(self.ready is None and task_id in self.attempts and task_id not in self.armed
                     and task_id not in self.active and type(attempt_index) is int
                     and attempt_index == len(self.attempts[task_id])
                     and 0 <= attempt_index <= self.prepared["execution"]["max_retries"])
            previous = self.attempts[task_id]
            _require(not previous or previous[-1]["accepted"] and not previous[-1]["success"])
            self._current()
            self.armed[task_id] = attempt_index

    def begin_task(self, *, task_id, run_id, condition_name, task_prompt, occupation,
                   experiment_prompt, perception_text, reference_files, provider) -> _TransportObservation:
        with self._guard():
            _require(run_id == pilot.RUN_ID and condition_name == "condition_a" and task_id in self.armed
                     and task_id not in self.active and perception_text is None)
            row = next(row for row in self.prepared["tasks"] if row["task_id"] == task_id)
            prompt = self.prepared["condition_a"]["prompt"]
            _require(task_prompt == row["instruction"] and occupation == row["occupation"]
                     and experiment_prompt == {"system": prompt.get("system", "You are a helpful assistant."),
                                                **{key: prompt.get(key) for key in ("prefix", "body", "suffix")}})
            requested = self.document["requested"]
            # Keep the resource bytes private. The endpoint account must be
            # the account sealed by the capture, not a same-named deployment
            # on a different resource selected through environment settings.
            ready = json.loads(_read_bytes(
                _path(_root(self.sources.deployment_binding), deployment.READY_PATH),
                **self.document["upstream_bundles"]["deployment"]["ready"],
            ))
            account = deployment._resource_bytes(deployment._resource_path(self.sources.account_resource_id_file))
            _require(_digest(account) == {key: ready["resource_files"]["account"][key] for key in ("size", "sha256")})
            account_leaf = deployment._resource_parts(account, "account")[-1]
            endpoint = classify_endpoint(provider.endpoint)
            _require(provider.model == requested["deployment"] and provider.provider_id == requested["provider_id"]
                     and provider.reasoning_effort == requested["reasoning_effort"]
                     and provider.model_context_window == requested["context_tokens"]
                     and provider.request_max_retries == provider.stream_max_retries == 0
                     and provider.auth_module == pilot.DEFAULT_AUTH_MODULE and not provider.query_params
                     and provider.auth_scope == pilot.DIRECT_TOKEN_SCOPE
                     and endpoint.kind is EndpointKind.DIRECT_V1 and endpoint.account == account_leaf
                     and os.environ.get("AZURE_AI_ROUTE_PROFILE") == "direct-v1")
            references = reference_files or []
            _require(len(references) == len(row["reference_file_records"]))
            for path, record in zip(references, row["reference_file_records"]):
                path = Path(path)
                _require(path.name == Path(record["path"]).name)
                _root(path.parent)
                _read_bytes(path, size=record["size"], sha256=record["sha256"])
            observer = _TransportObservation(json.loads(_bytes(requested)))
            self.active[task_id] = observer
            return observer

    def finish_task(self, observer, *, success, thread_id, turn_id) -> dict:
        with self._guard():
            task_ids = [task_id for task_id, held in self.active.items() if held is observer]
            _require(type(observer) is _TransportObservation and len(task_ids) == 1)
            task_id = task_ids[0]
            index = self.armed[task_id]
            transport = observer.finish(success=success, thread_id=thread_id, turn_id=turn_id)
            thread_digest = transport["correlation"]["thread_id_sha256"]
            _require(thread_digest not in self.thread_ids)
            call_id = make_call_id(run_id=pilot.RUN_ID, task_id=task_id, stage="codex_app_server_turn",
                                   retry_kind="initial" if index == 0 else "infrastructure", attempt_index=index, sequence=0)
            name = call_id + ".json"
            task = next(row for row in self.document["tasks"] if row["task_id"] == task_id)
            data = _bytes({"receipt_version": "pilot-wire-receipt-v1", "evidence_boundary": BOUNDARY,
                           "run_id": pilot.RUN_ID, "condition": "codex_foundry", "task_order": self.document["task_ids"],
                           "task": task, "attempt_index": index, "retry_kind": "initial" if index == 0 else "infrastructure",
                           "repeat": 1, "logical_turn": 1, "call_id": call_id, "success": success,
                           "prepared_capture": self.linkage, "requested": {**self.document["requested"], "profile": "direct-v1"},
                           "transport": transport, "launch_allowed": False, "full_220_allowed": False})
            with _held_parents(self.workspace, (RESERVATION, DIRECTORY + "/" + name)) as check:
                self._current()
                check()
                _write_no_clobber(self.root / name, data)
                self.files[name] = data
                self._current()
                check()
            linkage = {"path": DIRECTORY + "/" + name, **_digest(data), "attempt_index": index,
                       "evidence_boundary": BOUNDARY}
            self.attempts[task_id].append({"linkage": linkage, "success": success, "accepted": False})
            self.thread_ids.add(thread_digest)
            del self.active[task_id], self.armed[task_id]
            return json.loads(_bytes(linkage))

    def accept_task(self, *, task_id: str, attempt_index: int, result: dict) -> None:
        """Reject forged/missing/stale results before deliverables are accepted."""
        with self._guard():
            rows = self.attempts[task_id]
            _require(type(attempt_index) is int and attempt_index == len(rows) - 1 and bool(rows))
            latest = rows[-1]
            _require(not latest["accepted"] and result.get("pilot_wire_receipt") == latest["linkage"]
                     and result.get("success") is latest["success"])
            self._current()
            latest["accepted"] = True

    def finalize(self, ordered_task_ids: list[str]) -> dict:
        with self._guard():
            _require(self.ready is None and not self.armed and not self.active and ordered_task_ids == self.document["task_ids"])
            _require(all(rows and all(row["accepted"] for row in rows) for rows in self.attempts.values()))
            data = _bytes({"bundle_version": "pilot-wire-receipts-ready-v1", "evidence_boundary": BOUNDARY,
                           "run_id": pilot.RUN_ID, "task_ids": ordered_task_ids, "prepared_capture": self.linkage,
                           "reservation": _digest(self.reservation),
                           "receipts": {task_id: [row["linkage"] for row in self.attempts[task_id]] for task_id in ordered_task_ids},
                           "live_inference_identity_and_wire_unverified": True,
                           "launch_allowed": False, "full_220_allowed": False})
            with _held_parents(self.workspace, (RESERVATION, DIRECTORY + "/" + READY_PATH)) as check:
                self._current()
                check()
                _write_no_clobber(self.root / READY_PATH, data)
                self.ready = data
                self._current()
                check()
            return {"path": DIRECTORY + "/" + READY_PATH, **_digest(data), "evidence_boundary": BOUNDARY,
                    "launch_allowed": False, "full_220_allowed": False}


def verify_pilot_wire_receipts(session: PilotWireReceiptSession) -> dict:
    """A live witness is mandatory: never adopt a disk-only or partial bundle."""
    with _closed():
        _require(type(session) is PilotWireReceiptSession and session.ready is not None)
        with session._guard():
            session._current()
            return json.loads(session.ready)
