"""Owned app-server usage observations, not native spend or billing proof.

The parent capture has already verified the evidence chain. This owner binds
its approved thresholds to raw notifications and actual accepted host rows;
external evidence quantities and prices never become runtime measurements.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_native_result_host as native
import gpt56_pilot_wire_receipt as wire
from core.codex_cost import CODEX_STRUCTURAL_REASONS, CodexTokenTotals, read_breakdown, turn_usage_delta
from core.cost_receipts import REASON_PRICE_MISSING, REASON_USAGE_PARTIAL
from core.result_fingerprint import inference_result_fingerprint

DIRECTORY = "pilot-runtime-caps-usage"
RESERVATION = DIRECTORY + ".reservation.json"
READY_PATH = wire.pilot.RUNTIME_CAPS_USAGE["ready_marker"]
BOUNDARY = wire.pilot.RUNTIME_CAPS_USAGE["evidence_boundary"]
REFUSAL = "pilot_runtime_caps_usage_refused"
BLOCKERS = tuple(name for name in wire.pilot.LAUNCH_BLOCKERS if name in {
    "native_call_and_token_limits_unresolved", "foundry_usage_and_tariff_mapping_unverified",
    "live_inference_identity_and_wire_unverified", "native_sandbox_and_result_bundle_host_unverified",
})
_bytes, _digest = wire._bytes, wire._digest
_FIELDS = {field.name: "".join(part if index == 0 else part.title()
                              for index, part in enumerate(field.name.split("_")))
           for field in fields(CodexTokenTotals)}


class PilotRuntimeCapsUsageRefused(ValueError):
    """A static refusal without private evidence, paths, IDs or exception text."""

    def __init__(self) -> None:
        super().__init__(REFUSAL)


def _require(value: bool) -> None:
    if not value:
        raise PilotRuntimeCapsUsageRefused()


@contextmanager
def _closed():
    try:
        yield
    except Exception:
        raise PilotRuntimeCapsUsageRefused() from None


def _boundary() -> dict:
    return {"evidence_boundary": BOUNDARY, "cost": None, "cost_state": "partial",
            "partial_reasons": [*CODEX_STRUCTURAL_REASONS, REASON_USAGE_PARTIAL, REASON_PRICE_MISSING],
            "not_available": {name: wire._unavailable() for name in (
                "model_call_count", "native_spend_enforcement", "foundry_http_payload", "foundry_request_id",
                "served_model", "served_model_version", "served_deployment", "billing_quantity", "currency_conversion")},
            "remaining_launch_blockers": list(BLOCKERS), "cleared_blockers": [],
            "launch_allowed": False, "full_220_allowed": False}


def _totals(values: dict) -> CodexTokenTotals:
    return read_breakdown(SimpleNamespace(**{name: values.get(field) for name, field in _FIELDS.items()}))


class _UsageObservation:
    """Only the observer lock is used here: no parent locks, I/O or verifiers."""

    def __init__(self, owner: PilotRuntimeCapsUsageSession, observer: wire._TransportObservation) -> None:
        self.owner, self.observer = owner, observer
        self.limits = dict(owner.approved_limits)
        self.context = owner.wire.document["requested"]["context_tokens"]
        self.bound_limits, self.bound_context = _bytes(self.limits), _bytes(self.context)
        self.snapshots: list[bytes] = []
        self.known = {field: 0 for field in wire._USAGE_FIELDS}
        self.finished: bytes | None = None
        self.failed = False

    @contextmanager
    def _guard(self):
        with self.observer.lock, _closed():
            try:
                _require(not self.failed and not self.owner.failed and not self.observer.invalid
                         and self.observer.caps_usage_observer is self)
                _require(_bytes(self.limits) == self.bound_limits == _bytes(self.owner.approved_limits)
                         and _bytes(self.context) == self.bound_context
                         == _bytes(self.owner.wire.document["requested"]["context_tokens"]))
                yield
            except Exception:
                self.failed = self.observer.invalid = True
                self.owner._poison()
                raise PilotRuntimeCapsUsageRefused() from None

    def observe(self, snapshot: dict) -> None:
        """Check each raw, correlated sample before the wire observer appends it."""
        with self._guard():
            _require(self.finished is None and not self.observer.sealed and type(snapshot) is dict
                     and set(snapshot) == {"thread_id_sha256", "turn_id_sha256", "native"})
            for field in ("thread_id_sha256", "turn_id_sha256"):
                value = snapshot[field]
                _require(type(value) is str and len(value) == 64 and set(value) <= set("0123456789abcdef"))
            usage = snapshot["native"]
            _require(type(usage) is dict and set(usage) <= {"total", "last", "modelContextWindow"})
            for role in ("total", "last"):
                if role not in usage:
                    continue
                counts = usage[role]
                _require(type(counts) is dict and set(counts) <= wire._USAGE_FIELDS)
                _require(all(value is None or type(value) is int and value >= 0 for value in counts.values()))
                for child, parent in (("inputTokens", "totalTokens"), ("outputTokens", "totalTokens"),
                                      ("cachedInputTokens", "inputTokens"), ("cacheWriteInputTokens", "inputTokens"),
                                      ("reasoningOutputTokens", "outputTokens")):
                    if counts.get(child) is not None and counts.get(parent) is not None:
                        _require(counts[child] <= counts[parent])
                if all(counts.get(field) is not None for field in ("inputTokens", "outputTokens", "totalTokens")):
                    # Cache and reasoning are subcounts, never added again.
                    _require(counts["totalTokens"] == counts["inputTokens"] + counts["outputTokens"])
            total = usage.get("total", {})
            _require(all(type(total.get(field)) is int for field in ("inputTokens", "outputTokens", "totalTokens")))
            turn_usage_delta(_totals(self.known), _totals(total))
            _require(total["totalTokens"] >= self.known["totalTokens"])
            _require(total["inputTokens"] <= self.limits["input_tokens"]
                     and total["outputTokens"] <= self.limits["output_tokens"])
            for field, value in usage.get("last", {}).items():
                if value is not None and total.get(field) is not None:
                    _require(value <= total[field])
            if usage.get("modelContextWindow") is not None:
                _require(type(usage["modelContextWindow"]) is int and usage["modelContextWindow"] == self.context)
            self.known.update({field: value for field, value in total.items() if value is not None})
            self.snapshots.append(_bytes(snapshot))

    def _document(self, observer: wire._TransportObservation) -> dict:
        _require(observer is self.observer and observer.installed and bool(self.snapshots)
                 and self.snapshots == [_bytes(row) for row in observer.usage])
        _require(set(observer.requests) in ({"thread/start", "turn/start"}, {"thread/start", "turn/start", "turn/interrupt"})
                 and observer.responses == {row["request_id_sha256"] for row in observer.requests.values()})
        rows = [observer.completion, *observer.usage]
        _require(all(row["thread_id_sha256"] == observer.thread and row["turn_id_sha256"] == observer.turn for row in rows))
        _require(observer.completion["status"] in ("completed", "failed", "interrupted"))
        return {"source": "app_server_thread_usage_not_provider_billing", "unit": "tokens",
                "counter_semantics": "total_cumulative_per_thread_last_latest_model_request",
                "correlation": observer.completion, "requests": observer.requests,
                "snapshots": [json.loads(row) for row in self.snapshots],
                "threshold_observation": "reported_input_and_output_within_reviewed_limits_not_native_enforcement"}

    def finish(self, observer: wire._TransportObservation) -> None:
        """Seal only the exact stream just validated by the live wire owner."""
        with self._guard():
            _require(self.finished is None and not observer.sealed)
            self.finished = _bytes(self._document(observer))

    def verified(self) -> dict:
        with self._guard():
            _require(self.observer.sealed and self.finished is not None
                     and self.finished == _bytes(self._document(self.observer)))
            return json.loads(self.finished)


class PilotRuntimeCapsUsageSession:
    """One non-adoptable owner of thresholds, observed attempts and final bytes."""

    def __init__(self, host: native.PilotNativeResultHostSession) -> None:
        with _closed():
            _require(type(host) is native.PilotNativeResultHostSession and type(host.wire) is wire.PilotWireReceiptSession)
            self.host, self.wire, self.workspace = host, host.wire, host.workspace
            self.failed, self.ready = False, None
            self.files: dict[str, bytes] = {}
            self.observations: dict[tuple[str, int], _UsageObservation] = {}
            self.recorded: dict[tuple[str, int], str] = {}
            self.pending: tuple[str, int] | None = None
            self.started: list[str] = []
            self.task_ids = tuple(self.wire.document["task_ids"])
            with self._guard(attached=False):
                _require(len(self.task_ids) == len(set(self.task_ids)) == 5 and not host.witnesses
                         and host.ready is None and not host.files and not host.results
                         and not self.wire.armed and not self.wire.active and not self.wire.files
                         and all(not rows for rows in self.wire.attempts.values()) and self.wire.ready is None)
                # The host just called the real wire/capture verifier. Do not
                # add another capture event or trust an unpinned evidence file.
                self.evidence_root = wire._root(self.wire.sources.evidence_bundle)
                ready = wire._read_bytes(self.evidence_root / evidence.READY_PATH,
                                         sha256=self.wire.document["upstream_bundles"]["evidence"]["ready_sha256"])
                document = json.loads(ready)
                _require(document["evidence_complete"] is True and document["missing_evidence"] == []
                         and set(document["claims"]) == set(evidence.ROLES)
                         and document["run_id"] == wire.pilot.RUN_ID
                         and document["reviewed_source_sha"] == self.wire.document["reviewed_source_sha"])
                self.evidence_files = {evidence.READY_PATH: ready}
                roles = {}
                for role in ("native_caps", "usage", "tariff"):
                    claim = document["claims"][role]
                    reference = claim["artifact"]
                    _require(reference["path"] == "artifacts/" + role + ".json")
                    data = wire._read_bytes(wire._path(self.evidence_root, reference["path"]),
                                            **{key: reference[key] for key in ("size", "sha256")})
                    _require(_bytes(json.loads(data)) == _bytes(claim["evidence"]))
                    self.evidence_files[reference["path"]] = data
                    roles[role] = _digest(data)
                claims = document["claims"]
                caps = claims["native_caps"]["evidence"]["observed"]
                self.approved_limits = {key: caps[key] for key in ("model_calls", "input_tokens", "output_tokens")}
                _require(all(type(value) is int and value > 0 for value in self.approved_limits.values()))
                meters = {name: claims["usage"]["evidence"]["observed"]["meters"][name]["meter_id"] for name in evidence.METERS}
                _require(all(type(value) is str and value for value in meters.values()) and len(set(meters.values())) == len(meters)
                         and all(value == claims["tariff"]["evidence"]["observed"]["rates"][name]["meter_id"]
                                 for name, value in meters.items()))
                self.reviewed_evidence = {"ready": _digest(ready), "roles": roles, "meter_ids": meters,
                                          "approved_limits": self.approved_limits,
                                          "source": "reviewed_evidence_not_runtime_billing_or_enforcement"}
                self.root, self.reserved = self.workspace / DIRECTORY, self.workspace / RESERVATION
                self.reservation = _bytes({"reservation_version": "pilot-runtime-caps-usage-reservation-v1",
                                           "run_id": wire.pilot.RUN_ID, "prepared_capture": self.wire.linkage,
                                           "host_reservation": _digest(host.reservation), "reviewed_evidence": self.reviewed_evidence,
                                           "launch_allowed": False, "full_220_allowed": False})
                with wire._held_parents(self.workspace, (DIRECTORY, RESERVATION)) as check:
                    _require(not os.path.lexists(self.root) and not os.path.lexists(self.reserved))
                    check()
                    wire._write_no_clobber(self.reserved, self.reservation)
                    host._mkdir(self.workspace, DIRECTORY)
                    check()
                self.root_identity = native._identity(self.root)
                self.workspace_identity = native._identity(self.workspace)
                self.evidence_identity = native._identity(self.evidence_root)
                self._current()

    def _poison(self) -> None:
        self.failed = self.host.failed = self.wire.failed = True

    @contextmanager
    def _guard(self, *, attached: bool = True):
        with self.wire.lock, _closed():
            try:
                _require(not self.failed and not self.host.failed and not self.wire.failed
                         and self.wire.native_host is self.host and self.host.wire is self.wire)
                _require(getattr(self.host, "runtime_caps_usage", None) is (self if attached else None))
                yield
            except Exception:
                self._poison()
                raise PilotRuntimeCapsUsageRefused() from None

    def _current(self) -> None:
        """Read only owned bytes here; never recurse into a parent verifier."""
        reserved = json.loads(self.reservation)
        reviewed = reserved["reviewed_evidence"]
        _require(_bytes(self.reviewed_evidence) == _bytes(reviewed)
                 and _bytes(self.approved_limits) == _bytes(reviewed["approved_limits"]))
        _require(_bytes(self.wire.linkage) == _bytes(reserved["prepared_capture"])
                 and _digest(self.host.reservation) == reserved["host_reservation"]
                 and _bytes(self.wire.document) == self.wire.capture_data
                 and _digest(_bytes(self.wire.prepared))["sha256"] == self.wire.document["prepared"]["canonical_sha256"]
                 and tuple(self.wire.document["task_ids"]) == self.task_ids)
        _require(native._identity(self.workspace) == self.workspace_identity
                 and native._identity(self.root) == self.root_identity
                 and native._identity(self.evidence_root) == self.evidence_identity)
        wire._read_bytes(self.reserved, **_digest(self.reservation))
        _require({path.name for path in self.root.iterdir()} == set(self.files) | ({READY_PATH} if self.ready is not None else set()))
        for name, data in self.evidence_files.items():
            wire._read_bytes(wire._path(self.evidence_root, name), **_digest(data))
        for name, data in self.files.items():
            wire._read_bytes(wire._path(self.root, name), **_digest(data))
        if self.ready is not None:
            wire._read_bytes(self.root / READY_PATH, **_digest(self.ready))

    def arm_task(self, task_id: str, attempt_index: int) -> None:
        with self._guard():
            _require(self.ready is None and self.host.ready is None and self.pending is None
                     and task_id in self.task_ids and type(attempt_index) is int
                     and 0 <= attempt_index <= self.wire.prepared["execution"]["max_retries"]
                     and attempt_index == len(self.wire.attempts[task_id]))
            if attempt_index:
                previous = self.host.witnesses[(task_id, attempt_index - 1)]
                _require(self.started[-1] == task_id and previous.accepted and previous.row is not None
                         and (task_id, attempt_index - 1) in self.recorded
                         and not self.wire.attempts[task_id][-1]["success"])
            else:
                _require(len(self.started) < len(self.task_ids) and task_id == self.task_ids[len(self.started)])
                if self.started:
                    previous_id = self.started[-1]
                    _require((previous_id, len(self.wire.attempts[previous_id]) - 1) in self.recorded)
                self.started.append(task_id)
            self._current()
            self.pending = task_id, attempt_index

    def bind_observer(self, task_id: str, attempt_index: int, observer: wire._TransportObservation) -> None:
        with self._guard():
            key = task_id, attempt_index
            _require(self.pending == key and key not in self.observations
                     and type(observer) is wire._TransportObservation and self.wire.active.get(task_id) is observer
                     and self.wire.armed[task_id] == attempt_index and not observer.sealed
                     and observer.caps_usage_observer is None)
            self._current()
            self.observations[key] = observer.caps_usage_observer = _UsageObservation(self, observer)

    def _attempt(self, witness: native._WorkspaceWitness) -> tuple[str, dict]:
        key = witness.task_id, witness.attempt
        _require(type(witness) is native._WorkspaceWitness and self.host.witnesses.get(key) is witness
                 and witness.closed and witness.result_digest is not None)
        observed = self.observations[key]
        _require(observed.observer is witness.observer)
        usage = observed.verified()
        attempt = self.wire.attempts[witness.task_id][witness.attempt]
        _require(witness.linkage == attempt["linkage"] and attempt["accepted"] is witness.accepted)
        name = Path(witness.linkage["path"]).name
        data = self.wire.files[name]
        _require(_bytes(witness.linkage) == _bytes({"path": wire.DIRECTORY + "/" + name, **_digest(data),
                                                  "attempt_index": witness.attempt, "evidence_boundary": wire.BOUNDARY}))
        wire._read_bytes(self.wire.root / name, **_digest(data))
        record = json.loads(data)
        _require(record["attempt_index"] == witness.attempt and record["task"]["task_id"] == witness.task_id
                 and record["success"] is attempt["success"]
                 and _bytes(record["transport"]["usage"]["snapshots"]) == _bytes(usage["snapshots"])
                 and _bytes(record["transport"]["correlation"]) == _bytes(usage["correlation"])
                 and _bytes(record["transport"]["requests"]) == _bytes(usage["requests"]))
        return name, usage

    def check_attempt(self, witness: native._WorkspaceWitness) -> None:
        with self._guard():
            _require(self.ready is None and self.pending == (witness.task_id, witness.attempt)
                     and self.pending not in self.recorded)
            self._current()
            self._attempt(witness)

    def _receipt(self, witness: native._WorkspaceWitness) -> tuple[str, bytes]:
        name, usage = self._attempt(witness)
        _require(witness.accepted and witness.row is not None)
        host_data = self.host.files[name]
        wire._read_bytes(self.host.root / name, **_digest(host_data))
        host_record = json.loads(host_data)
        row_digest = inference_result_fingerprint(witness.row)
        _require(host_record["step2_accepted_row_sha256"] == row_digest
                 and host_record["wire_receipt"] == witness.linkage
                 and host_record["runner_result_sha256"] == witness.result_digest)
        return name, _bytes({"receipt_version": "pilot-runtime-caps-usage-attempt-v1", **_boundary(),
                             "run_id": wire.pilot.RUN_ID, "condition": "codex_foundry", "task_id": witness.task_id,
                             "task_order": list(self.task_ids), "task_index": self.task_ids.index(witness.task_id),
                             "attempt_index": witness.attempt, "retry_kind": "initial" if witness.attempt == 0 else "infrastructure",
                             "infrastructure_retry_count": witness.attempt, "logical_turn": 1,
                             "thread_count": sum(name == "thread/start" for name in usage["requests"]),
                             "turn_count": sum(name == "turn/start" for name in usage["requests"]),
                             "count_boundary": "app_server_sessions_not_model_calls", "prepared_capture": self.wire.linkage,
                             "wire_receipt": witness.linkage,
                             "native_result_host_receipt": {"path": native.DIRECTORY + "/" + name, **_digest(host_data)},
                             "step2_accepted_row_sha256": row_digest, "step2_status": witness.row["status"],
                             "reviewed_evidence": self.reviewed_evidence, "usage": usage})

    def _write(self, name: str, data: bytes, *, ready: bool = False) -> None:
        with wire._held_parents(self.workspace, (RESERVATION, DIRECTORY + "/" + name)) as check:
            self._current()
            check()
            wire._write_no_clobber(self.root / name, data)
            if ready:
                self.ready = data
            else:
                self.files[name] = data
            self._current()
            check()

    def record_step2_result(self, witness: native._WorkspaceWitness) -> None:
        with self._guard():
            self.check_attempt(witness)
            key = witness.task_id, witness.attempt
            name, data = self._receipt(witness)
            self._write(name, data)
            # Re-read the real upstream/host bytes after publication, not only
            # this owner's inventory. A raced parent receipt poisons all owners.
            self.host._current()
            _require(self._receipt(witness) == (name, data))
            self.recorded[key] = name
            self.pending = None

    def _ready_document(self) -> dict:
        host_document = native.verify_pilot_native_result_host(self.host)
        _require(self.pending is None and tuple(self.started) == self.task_ids and not self.wire.armed and not self.wire.active)
        expected = {(task, index) for task in self.task_ids for index in range(len(self.wire.attempts[task]))}
        _require(all(self.wire.attempts[task] for task in self.task_ids)
                 and set(self.recorded) == set(self.observations) == set(self.host.witnesses) == expected
                 and set(self.files) == set(self.recorded.values()))
        for key in expected:
            name, data = self._receipt(self.host.witnesses[key])
            _require(name == self.recorded[key] and self.files[name] == data)
        self._current()
        return {"bundle_version": "pilot-runtime-caps-usage-ready-v1", **_boundary(), "run_id": wire.pilot.RUN_ID,
                "task_ids": list(self.task_ids), "prepared_capture": self.wire.linkage,
                "infrastructure_retry_count": sum(len(self.wire.attempts[task]) - 1 for task in self.task_ids),
                "thread_count": len(self.recorded), "turn_count": len(self.recorded),
                "count_boundary": "app_server_sessions_not_model_calls",
                "reservation": _digest(self.reservation), "reviewed_evidence": self.reviewed_evidence,
                "wire_ready": host_document["wire_ready"],
                "native_result_host": {"path": native.DIRECTORY + "/" + native.READY_PATH, **_digest(self.host.ready)},
                "accepted_results": {path.name: {**_digest(data), "result_fingerprint": json.loads(data)["result_fingerprint"]}
                                     for path, data in sorted(self.host.results.items())},
                "receipts": {task: [{"path": DIRECTORY + "/" + self.recorded[(task, index)],
                                      **_digest(self.files[self.recorded[(task, index)]]), "attempt_index": index}
                                     for index in range(len(self.wire.attempts[task]))] for task in self.task_ids}}

    def finalize(self) -> dict:
        """Publish only after the real host has saved and verified both results."""
        with self._guard():
            _require(self.ready is None)
            data = _bytes(self._ready_document())
            self._write(READY_PATH, data, ready=True)
            _require(data == _bytes(self._ready_document()))
            return json.loads(data)


def runtime_caps_usage_for(wire_session: wire.PilotWireReceiptSession | None) -> PilotRuntimeCapsUsageSession | None:
    """Legacy None is the only absent path; an active pilot requires its owner."""
    if wire_session is None:
        return None
    with _closed():
        _require(type(wire_session) is wire.PilotWireReceiptSession)
        host = wire_session.native_host
        _require(type(host) is native.PilotNativeResultHostSession)
        owner = host.runtime_caps_usage
        _require(type(owner) is PilotRuntimeCapsUsageSession and owner.host is host and owner.wire is wire_session)
        with owner._guard():
            _require(owner.ready is None and host.ready is None)
            owner._current()
            return owner


def verify_pilot_runtime_caps_usage(instance: PilotRuntimeCapsUsageSession) -> dict:
    """Recheck the exact live owner, all upstreams, accepted results and bytes."""
    with _closed():
        _require(type(instance) is PilotRuntimeCapsUsageSession and instance.ready is not None)
        with instance._guard():
            instance._current()
            _require(instance.ready == _bytes(instance._ready_document()))
            return json.loads(instance.ready)
