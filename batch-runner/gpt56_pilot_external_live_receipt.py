"""Bind sanitized external claims to one owned pilot, without authenticating them.

A caller-pinned export digest freezes reviewed bytes, not the issuer's identity.
Even an exact finalized session can be exercised by synthetic fixtures. Neither
that Python type nor app-server correlation attests to a live Foundry request.
This library therefore publishes only unverified claims and clears no blocker.
"""

from __future__ import annotations

import json
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_native_result_host as native
import gpt56_pilot_runtime_caps_usage as caps
import gpt56_pilot_wire_receipt as wire

DIRECTORY = "pilot-external-live-receipt"
RESERVATION = DIRECTORY + ".reservation.json"
ARTIFACT_PATH = "external-live-receipt.json"
READY_PATH = wire.pilot.EXTERNAL_LIVE_RECEIPT["ready_marker"]
BOUNDARY = wire.pilot.EXTERNAL_LIVE_RECEIPT["evidence_boundary"]
SCHEMA_DEF = "external_live_receipt"
REFUSAL = "pilot_external_live_receipt_refused"
MAX_ARTIFACT_SIZE = 262144  # One bounded export, including all twenty possible attempts.
_bytes, _digest = wire._bytes, wire._digest


class PilotExternalLiveReceiptRefused(ValueError):
    """A static refusal without private input, paths or exception details."""

    def __init__(self) -> None:
        super().__init__(REFUSAL)


def _require(condition: bool) -> None:
    if not condition:
        raise PilotExternalLiveReceiptRefused()


@contextmanager
def _closed():
    try:
        yield
    except Exception:
        raise PilotExternalLiveReceiptRefused() from None


def _runtime_time(value: Any) -> datetime:
    """Read owned UTC timestamps, including Step 2's fractional +00:00 form."""
    _require(type(value) is str and re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", value) is not None)
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    _require(result.tzinfo is not None and result.utcoffset() == timezone.utc.utcoffset(result))
    return result


def _utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _snapshot(runtime: caps.PilotRuntimeCapsUsageSession, *, reviewed_source_sha: str) -> dict:
    """Read real current owners; this sanitized snapshot is not an adoptable witness."""
    with _closed():
        _require(type(runtime) is caps.PilotRuntimeCapsUsageSession)
        _require(type(reviewed_source_sha) is str and re.fullmatch(r"[0-9a-f]{40}", reviewed_source_sha) is not None
                 and reviewed_source_sha != "0" * 40)
        with runtime._guard():
            document = caps.verify_pilot_runtime_caps_usage(runtime)
            held_wire, host = runtime.wire, runtime.host
            _require(reviewed_source_sha == held_wire.document["reviewed_source_sha"]
                     == document["prepared_capture"]["reviewed_source_sha"])
            saved = [json.loads(data) for _, data in sorted(host.results.items())]
            _require(len(saved) == 2 and _bytes(saved[0]) == _bytes(saved[1]))
            started, completed = (_runtime_time(saved[0][key]) for key in ("started_at", "completed_at"))
            _require(started <= completed and len(runtime.task_ids) == len(set(runtime.task_ids)) == 5)
            ready = json.loads(runtime.evidence_files[evidence.READY_PATH])
            roles = ready["claims"]
            prepared = wire._read_bytes(runtime.workspace / wire.capture.PREPARED_PATH,
                                        sha256=held_wire.linkage["prepared_sha256"])
            binding = {
                "run_id": wire.pilot.RUN_ID, "reviewed_source_sha": reviewed_source_sha,
                "task_ids": list(runtime.task_ids), "run_started_at": _utc(started), "run_completed_at": _utc(completed),
                "capture": _digest(held_wire.capture_data), "capture_linkage_sha256": _digest(_bytes(held_wire.linkage))["sha256"],
                "prepared": _digest(prepared),
                "upstream_bundles_sha256": _digest(_bytes(held_wire.document["upstream_bundles"]))["sha256"],
                "caps_ready": _digest(runtime.ready), "caps_reservation": _digest(runtime.reservation),
                "wire_ready": _digest(held_wire.ready), "wire_reservation": _digest(held_wire.reservation),
                "host_ready": _digest(host.ready), "host_reservation": _digest(host.reservation),
                "evidence_ready": _digest(runtime.evidence_files[evidence.READY_PATH]),
                "evidence_roles": {role: {key: roles[role]["artifact"][key] for key in ("size", "sha256")}
                                   for role in evidence.ROLES},
                "accepted_results": document["accepted_results"],
            }
            attempts, native_usage, correlations = [], [], set()
            previous = started
            for task_id in runtime.task_ids:
                for index in range(len(held_wire.attempts[task_id])):
                    name = runtime.recorded[(task_id, index)]
                    receipt = json.loads(runtime.files[name])
                    transport = json.loads(held_wire.files[name])["transport"]
                    accepted = _runtime_time(host.witnesses[(task_id, index)].row["timestamp"])
                    _require(previous <= accepted <= completed)
                    # These unavailable fields are a property of the pinned route.
                    # Never promote its local RPC ID to a provider HTTP identity.
                    _require(all(transport[key] == wire._unavailable() for key in (
                        "foundry_http_payload", "foundry_request_id", "served_model", "served_model_version", "served_deployment")))
                    correlation = receipt["usage"]["correlation"]
                    requests = receipt["usage"]["requests"]
                    native_usage.append(receipt["usage"]["snapshots"][-1]["native"])
                    correlations.update(row["request_id_sha256"] for row in requests.values())
                    correlations.update(correlation[key] for key in ("thread_id_sha256", "turn_id_sha256"))
                    attempts.append({
                        "task_id": task_id, "attempt_index": index, "retry_kind": "initial" if index == 0 else "infrastructure",
                        "logical_turn": 1, "not_before": _utc(previous), "accepted_at": _utc(accepted),
                        "caps_receipt": _digest(runtime.files[name]), "wire_receipt": _digest(held_wire.files[name]),
                        "host_receipt": _digest(host.files[name]), "accepted_row_sha256": receipt["step2_accepted_row_sha256"],
                        "thread_start": requests["thread/start"], "turn_start": requests["turn/start"],
                        "thread_id_sha256": correlation["thread_id_sha256"], "turn_id_sha256": correlation["turn_id_sha256"],
                    })
                    previous = accepted
            return json.loads(_bytes({
                "binding": binding, "attempt_bindings": attempts, "local_correlations": sorted(correlations),
                "native_usage": native_usage,
                "reviewed": {"subject": roles["identity"]["evidence"]["subject"],
                             "usage": roles["usage"]["evidence"]["observed"],
                             "tariff": roles["tariff"]["evidence"]["observed"]},
            }))


def _matching_present(value: Any, expected: Any) -> None:
    """Null remains unknown; a non-null external identity must match its pin."""
    if value is None:
        return
    if type(value) is dict:
        _require(type(expected) is dict)
        for key, child in value.items():
            _matching_present(child, expected[key])
    else:
        _require(_bytes(value) == _bytes(expected))


def _validate_artifact(data: bytes, *, schema: dict, snapshot: dict, as_of: str) -> dict:
    """Pure closed-shape consistency checks, never authenticity or a ready witness."""
    with _closed():
        _require(type(data) is bytes and 0 < len(data) <= MAX_ARTIFACT_SIZE)
        artifact = evidence._json(data)
        evidence._validate(schema, artifact, SCHEMA_DEF)
        _require(_bytes(artifact["binding"]) == _bytes(snapshot["binding"])
                 and _bytes([row["binding"] for row in artifact["attempts"]]) == _bytes(snapshot["attempt_bindings"]))
        evaluated = evidence._time(as_of).replace(tzinfo=timezone.utc)
        _require(_runtime_time(snapshot["binding"]["run_completed_at"]) <= evaluated)
        reviewed = snapshot["reviewed"]
        tariff = reviewed["tariff"]
        effective, expires = (evidence._time(tariff[key]).replace(tzinfo=timezone.utc)
                              for key in ("effective_at", "expires_at"))
        _require(effective <= evaluated <= expires)
        provider_ids = set()
        for index, record in enumerate(artifact["attempts"]):
            bound = record["binding"]
            times = {key: evidence._time(record[key]).replace(tzinfo=timezone.utc) for key in (
                "window_started_at", "window_ended_at", "observed_at", "issued_at", "valid_until")}
            _require(_runtime_time(bound["not_before"]) <= times["window_started_at"] <= times["observed_at"]
                     <= times["window_ended_at"] <= _runtime_time(bound["accepted_at"]))
            _require(times["window_ended_at"] <= times["issued_at"] <= evaluated <= times["valid_until"]
                     and effective <= times["window_started_at"] <= times["window_ended_at"] <= expires)
            for field in ("provider_request_id_sha256", "provider_response_id_sha256"):
                provider_id = record[field]
                if provider_id is not None:
                    _require(provider_id not in snapshot["local_correlations"] and provider_id not in provider_ids)
                    provider_ids.add(provider_id)
            _matching_present(record["served"], reviewed["subject"])
            _matching_present(record["tariff"], tariff)
            for role in ("usage", "billing"):
                usage = record[role]
                if usage is None:
                    continue
                for field in ("currency", "region"):
                    _matching_present(usage[field], reviewed["usage"][field])
                    _matching_present(usage[field], tariff[field])
                for meter, values in usage["meters"].items():
                    _matching_present(values["meter_id"], reviewed["usage"]["meters"][meter]["meter_id"])
                    _matching_present(values["meter_id"], tariff["rates"][meter]["meter_id"])
                    if values["quantity"] is not None:
                        _require(values["meter_id"] is not None and values["unit"] == "tokens")
                        if role == "usage":
                            # This field only corroborates the final raw cumulative
                            # app-server snapshot. Missing/native-null is not zero.
                            observed = snapshot["native_usage"][index].get("total", {}).get(caps._FIELDS[meter])
                            _require(observed is not None and values["quantity"] == observed)
                if role == "usage":
                    total, cached = (usage["meters"][meter]["quantity"] for meter in ("input_tokens", "cached_input_tokens"))
                    _require(total is None or cached is None or cached <= total)
                # Billing uses separately reported provider-meter quantities.
                # Neither equality with app-server tokens nor cached<=input is
                # inferred for those independent billing meters.
        # Nothing here computes calls, billable quantities, prices or currency.
        return artifact


def _boundary() -> dict:
    parent = caps._boundary()
    return {**parent, "evidence_boundary": BOUNDARY, "provenance_status": "unverified",
            "not_available": {**parent["not_available"], "foundry_response_id": wire._unavailable()},
            "eligible_facts": [], "authenticity": "not_authenticated_offline",
            "time_boundary": "run_and_accepted_row_bounds_not_measured_transport_time",
            "usage_boundary": "external_corroboration_of_reported_app_server_tokens_not_provider_billing",
            "billing_boundary": "independent_unverified_provider_meter_quantities_not_derived_from_app_server_tokens",
            "claims_boundary": "external_assertions_not_runtime_provider_observations"}


class PilotExternalLiveReceiptSession:
    """One absent subtree, exact live owner, immutable caller pins and no adoption."""

    def __init__(self, runtime: caps.PilotRuntimeCapsUsageSession, *, artifact_path: Path,
                 artifact_sha256: str, artifact_size: int, reviewed_source_sha: str, as_of: str) -> None:
        with _closed():
            _require(type(runtime) is caps.PilotRuntimeCapsUsageSession)
            self.runtime, self.workspace = runtime, runtime.workspace
            self.failed, self.ready = False, None
            self.files: dict[str, bytes] = {}
            self.root, self.reserved = self.workspace / DIRECTORY, self.workspace / RESERVATION
            # Invalid caller inputs have not acquired this runtime. Once attached,
            # any failed write/check poisons the owner and retains its partials.
            with runtime.wire.lock:
                _require(not runtime.failed and getattr(runtime, "external_live_receipt", None) is None)
                _require(type(artifact_size) is int and 0 < artifact_size <= MAX_ARTIFACT_SIZE
                         and type(artifact_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", artifact_sha256) is not None)
                self.snapshot = _bytes(_snapshot(runtime, reviewed_source_sha=reviewed_source_sha))
                self.reviewed_source_sha, self.as_of = reviewed_source_sha, as_of
                supplied = Path(artifact_path)
                _require(".." not in supplied.parts)
                self.source = Path(os.path.abspath(supplied))
                self.source_parent = wire._root(self.source.parent)
                self.source_identity = native._identity(self.source_parent)
                self.workspace_identity = native._identity(self.workspace)
                _require(not self.source.is_relative_to(self.root) and self.source != self.reserved)
                self.source_pin = {"size": artifact_size, "sha256": artifact_sha256}
                self.source_data = self._source_bytes()
                evidence_ready = json.loads(runtime.evidence_files[evidence.READY_PATH])
                self.schema_data = wire._read_bytes(wire.pilot.ROOT / evidence.SCHEMA_PATH,
                                                    sha256=evidence_ready["source_pins"][evidence.SCHEMA_PATH])
                self.schema = json.loads(self.schema_data, object_pairs_hook=evidence._object)
                _validate_artifact(self.source_data, schema=self.schema, snapshot=json.loads(self.snapshot), as_of=as_of)
                self.reservation = _bytes({"reservation_version": "pilot-external-live-receipt-reservation-v1",
                                           "reviewed_source_sha": reviewed_source_sha, "as_of": as_of,
                                           "artifact": self.source_pin, "snapshot": _digest(self.snapshot),
                                           "schema": _digest(self.schema_data), **_boundary()})
                with wire._held_parents(self.workspace, (DIRECTORY, RESERVATION)) as check:
                    _require(not os.path.lexists(self.root) and not os.path.lexists(self.reserved))
                    check()
                    runtime.external_live_receipt = self
                    with self._guard():
                        wire._write_no_clobber(self.reserved, self.reservation)
                        native.PilotNativeResultHostSession._mkdir(self.workspace, DIRECTORY)
                        check()
                        self.root_identity = native._identity(self.root)
                        self._current()

    def _poison(self) -> None:
        self.failed = True
        self.runtime._poison()

    @contextmanager
    def _guard(self):
        with self.runtime.wire.lock, _closed():
            try:
                _require(not self.failed and not self.runtime.failed
                         and getattr(self.runtime, "external_live_receipt", None) is self)
                yield
            except Exception:
                self._poison()
                raise PilotExternalLiveReceiptRefused() from None

    def _source_bytes(self) -> bytes:
        _require(native._identity(self.source_parent) == self.source_identity)
        metadata = self.source.lstat()
        _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
                 and 0 < metadata.st_size <= MAX_ARTIFACT_SIZE)
        return native._workspace_bytes(self.source_parent, Path(self.source.name), self.source_identity,
                                       self.source_pin, max_bytes=self.source_pin["size"])

    def _current(self) -> None:
        """Check owned/source bytes without treating a previous verdict as current."""
        reserved = json.loads(self.reservation)
        _require(reserved["artifact"] == self.source_pin and reserved["snapshot"] == _digest(self.snapshot)
                 and reserved["schema"] == _digest(self.schema_data)
                 and reserved["reviewed_source_sha"] == self.reviewed_source_sha and reserved["as_of"] == self.as_of)
        _require(native._identity(self.workspace) == self.workspace_identity and native._identity(self.root) == self.root_identity)
        _require(self._source_bytes() == self.source_data)
        wire._read_bytes(self.reserved, **_digest(self.reservation))
        wire._read_bytes(wire.pilot.ROOT / evidence.SCHEMA_PATH, **_digest(self.schema_data))
        _require(_bytes(self.schema) == _bytes(json.loads(self.schema_data)))
        _require({path.name for path in self.root.iterdir()} == set(self.files) | ({READY_PATH} if self.ready is not None else set()))
        for name, data in self.files.items():
            wire._read_bytes(self.root / name, **_digest(data))
        if self.ready is not None:
            wire._read_bytes(self.root / READY_PATH, **_digest(self.ready))

    def _recheck(self) -> None:
        self._current()
        _require(self.snapshot == _bytes(_snapshot(self.runtime, reviewed_source_sha=self.reviewed_source_sha)))
        _validate_artifact(self.source_data, schema=self.schema, snapshot=json.loads(self.snapshot), as_of=self.as_of)
        self._current()

    def _document(self) -> dict:
        return {"bundle_version": "pilot-external-live-receipt-ready-v1", **_boundary(),
                "reviewed_source_sha": self.reviewed_source_sha, "evaluated_at": self.as_of,
                "binding": json.loads(self.snapshot)["binding"], "reservation": _digest(self.reservation),
                "artifact": {"path": ARTIFACT_PATH, **self.source_pin}, "schema": _digest(self.schema_data)}

    def publish(self) -> dict:
        """Write the exact pinned export, then ready last; retain failed partials."""
        with self._guard():
            _require(self.ready is None and not self.files)
            self._recheck()
            paths = (RESERVATION, DIRECTORY + "/" + ARTIFACT_PATH, DIRECTORY + "/" + READY_PATH)
            with wire._held_parents(self.workspace, paths) as check:
                check()
                wire._write_no_clobber(self.root / ARTIFACT_PATH, self.source_data)
                self.files[ARTIFACT_PATH] = self.source_data
                self._recheck()
                check()
                data = _bytes(self._document())
                wire._write_no_clobber(self.root / READY_PATH, data)
                self.ready = data
                self._recheck()
                _require(self.ready == _bytes(self._document()))
                check()
            return json.loads(self.ready)


def external_live_receipt_for(runtime: caps.PilotRuntimeCapsUsageSession | None) -> PilotExternalLiveReceiptSession | None:
    """Legacy None is the only absent path; files cannot replace the live owner."""
    if runtime is None:
        return None
    with _closed():
        _require(type(runtime) is caps.PilotRuntimeCapsUsageSession)
        owner = runtime.external_live_receipt
        _require(type(owner) is PilotExternalLiveReceiptSession and owner.runtime is runtime)
        with owner._guard():
            owner._recheck()
            return owner


def verify_pilot_external_live_receipt(instance: PilotExternalLiveReceiptSession) -> dict:
    """Require the same healthy live witness and reread its complete byte chain."""
    with _closed():
        _require(type(instance) is PilotExternalLiveReceiptSession and instance.ready is not None)
        with instance._guard():
            _require(set(instance.files) == {ARTIFACT_PATH} and instance.files[ARTIFACT_PATH] == instance.source_data)
            instance._recheck()
            _require(instance.ready == _bytes(instance._document()))
            return json.loads(instance.ready)
