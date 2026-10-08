"""Closed native refusal points through real wrappers; all storage IO is synthetic."""

from contextlib import contextmanager
from copy import deepcopy
import json
import os

import httpx
import pytest

import gpt54_time_budget_native_grading_ci as subject
from gpt54_prepared_input_attestation import _identity
from .test_time_budget_native_grading_ci import (
    case, dual_roots, handoff_source_seed, handoff_sources, hosted, offline,
)
from .test_time_budget_native_grading_intake import NAMES, PRIVATE, TOKEN


@pytest.mark.parametrize("scenario,point,gets,preparations", [
    ("request_binding", "intake_request_validation", 0, 0),
    ("metadata_private_error", "retained_metadata", 1, 0),
    ("raw_lfs_pointer", "retained_deliverable_identity", 3, 0),
    ("frozen_preparation", "frozen_preparation", 4, 1),
    ("intake_reread", "intake_final_reread", 4, 1),
    ("checked_preparation", "native_checked_preparation", 4, 1),
    ("materialized_reread", "materialized_native_reread", 4, 1),
], ids=["request_binding", "metadata_private_error", "raw_lfs_pointer", "frozen_preparation",
        "intake_reread", "checked_preparation", "materialized_reread"])
def test_native_task3_intake_refusal_points(hosted, monkeypatch, capsys, record_property,
                                           scenario, point, gets, preparations):
    """No successful preparer/intake verdict is stubbed; fail actual byte gates."""
    paths, state = hosted.paths, hosted.state
    canary = "hf_SECRET_CANARY_native_intake_exception_not_a_credential"
    forbidden, formatted, handles, contexts, protocol = [], [], [], [], []

    class PrivateFailure(ValueError):
        # An arbitrary exception attribute is not a typed internal location.
        refusal_point = canary

        def __str__(self):
            formatted.append(True)
            raise AssertionError("private exception formatted")

    def deny(name):
        def forbidden_call(*args, **kwargs):
            forbidden.append(name)
            raise PrivateFailure(canary)
        return forbidden_call

    for owner, names in (
        (subject, ("_direction", "_claim", "_retain", "_commit", "_snapshot", "_session", "preflight_routes")),
        (subject.execution, ("execute_native_task3_grading", "execute_first_observation_grading",
                             "_execute_observation_grading", "_execution_binding", "require_execution_direction")),
        (subject.execution.owned.LocalTransport, ("process",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, deny(name))
    # The imported offline fixture also traps HF writes, sockets, real model
    # constructors, Step8 grading, generation and unowned subprocesses.
    for name in ("AZURE_AI_ROUTE_PROFILE", "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES",
                 "AZURE_AI_EXPECTED_DIRECT_ACCOUNT", "FOUNDRY_PROJECT_ENDPOINT"):
        monkeypatch.delenv(name)
    assert not {"source_repo_id", "source_revision", "source_identity_document_sha256"} & hosted.case.payload.keys()
    assert len(hosted.original_step0) == 218405

    request = deepcopy(hosted.request)
    request.update(format=subject.PROBE_REQUEST_FORMAT, purpose=subject.PROBE_PURPOSE,
                   policy=deepcopy(subject.PROBE_POLICY))
    del request["storage"]
    data = subject.bridge.reader._bytes(request)
    monkeypatch.setenv("TIME_BUDGET_GRADE_REQUEST_JSON", data.decode())
    monkeypatch.setenv("TIME_BUDGET_NATIVE_OPERATION", "prepare-probe")
    monkeypatch.setenv("REQUEST_SHA256", _identity(data)["sha256"])
    cli = hosted.cli[:-1] + [_identity(data)["sha256"]]

    real_checked_request = subject.checked_request

    @contextmanager
    def checked_request(**kwargs):
        with real_checked_request(**kwargs) as context:
            contexts.append(context)
            yield context

    monkeypatch.setattr(subject, "checked_request", checked_request)
    real_request = subject._intake_request

    def intake_request(context):
        raw = real_request(context)
        if scenario == "request_binding":
            changed = json.loads(raw)
            changed["registration_sha256"] = "0" * 64
            return subject.bridge.reader._bytes(changed)
        return raw

    monkeypatch.setattr(subject, "_intake_request", intake_request)
    real_transport = httpx.HTTPTransport

    class Transport(real_transport):
        def handle_request(self, outgoing):
            response = super().handle_request(outgoing)
            if scenario == "metadata_private_error" and len(state.retained_gets) == 1:
                raise PrivateFailure(canary)
            if scenario == "raw_lfs_pointer" and len(state.retained_gets) == 3:
                # Git LFS v1 pointer representation, not its binary payload.
                # The historical files' storage representation is unknown.
                record = hosted.case.payload["results"][0]["deliverable_file_records"][0]
                pointer = ("version https://git-lfs.github.com/spec/v1\n"
                           "oid sha256:" + record["sha256"] + "\nsize " + str(record["size"]) + "\n").encode()
                assert "/raw/" in outgoing.url.path and _identity(pointer) != {
                    key: record[key] for key in ("size", "sha256")}
                protocol.append({"representation": "synthetic_git_lfs_v1_pointer",
                    "pointer_identity": _identity(pointer), "declared_payload_size": record["size"],
                    "redirects_followed": 0})
                return httpx.Response(200, stream=httpx.ByteStream(pointer), request=outgoing)
            return response

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    if scenario == "frozen_preparation":
        state.fault = "preparation"  # Mutates bytes before the real F preparer, not its verdict.
    real_prepare = subject.preparation.prepare_observation_grading

    def prepare(*args, **kwargs):
        result = real_prepare(*args, **kwargs)
        if scenario == "intake_reread":
            reserved = paths["hydration_root"].with_name(
                paths["hydration_root"].name + subject.bridge.RESERVATION_SUFFIX)
            reserved.write_bytes(reserved.read_bytes() + b" ")
        return result

    monkeypatch.setattr(subject.preparation, "prepare_observation_grading", prepare)
    real_intake = subject.bridge.prepare_retained_native_task3_grading

    def retained_intake(**kwargs):
        summary = real_intake(**kwargs)
        if scenario == "checked_preparation":
            ready = paths["hydration_root"] / subject.bridge.READY
            ready.write_bytes(ready.read_bytes() + b" ")
        return summary

    monkeypatch.setattr(subject.bridge, "prepare_retained_native_task3_grading", retained_intake)
    real_context = subject.execution.prepare_native_task3_grading_execution

    @contextmanager
    def native_context(**kwargs):
        try:
            with real_context(**kwargs) as handle:
                handles.append(handle)
                assert handle in subject.execution._NATIVE_INTAKES and "HF_TOKEN" not in os.environ
                if scenario == "materialized_reread":
                    derived = paths["execution_input_directory"] / subject.preparation.RESULT
                    derived.write_bytes(derived.read_bytes() + b" ")
                yield handle
        finally:
            assert all(handle not in subject.execution._NATIVE_INTAKES for handle in handles)

    monkeypatch.setattr(subject.execution, "prepare_native_task3_grading_execution", native_context)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    assert subject.main(["prepare-probe", *cli]) == 2
    captured = capsys.readouterr()
    assert captured == ("", "")
    assert len(contexts) == 1
    raw = (paths["state_root"] / "completion.json").read_bytes()
    value, context = json.loads(raw), contexts[0]
    assert len(raw) <= 4096 and value["status"] == "refused"
    assert value["refusal_point"] == point
    assert value["diagnostics"] == {
        "environment": {"state": "completed", "category": None},
        "originals": {"state": "completed", "category": None},
        "intake_preparation": {"state": "started", "category": "validation_refused"},
        "context_exit": {"state": "unknown", "category": None},
    }
    assert value["verified_preparation"] is None
    assert value["grading_authority"] is value["handle_reusable"] is value["retry_allowed"] is False
    for key, expected in (("controller", request["controller"]), ("observation_source", request["completion"]["source"]),
                          ("frozen_source", request["frozen_source"]), ("request_identity", _identity(data)),
                          ("expected_result_identity", request["completion"]["result_identity"]),
                          ("expected_result_fingerprint", request["completion"]["result_fingerprint"]),
                          ("original_output_commit", request["completion"]["output_commit"]), ("ci", context["ci"]),
                          ("cell", subject.CELL)):
        assert value[key] == expected
    subject.validate_probe_completion(value, context)
    for bad in (canary, "unknown", True, {"point": point}, [point]):
        with pytest.raises(ValueError, match="^public_probe_refusal_point_refused$"):
            subject.validate_probe_completion({**value, "refusal_point": bad}, context)
    wrong_stage = deepcopy(value)
    wrong_stage["diagnostics"]["intake_preparation"] = {"state": "completed", "category": None}
    with pytest.raises(ValueError, match="^public_probe_refusal_point_refused$"):
        subject.validate_probe_completion(wrong_stage, context)
    for key in ("grading_authority", "handle_reusable", "retry_allowed"):
        with pytest.raises(ValueError):
            subject.validate_probe_completion({**value, key: True}, context)
    with pytest.raises(ValueError):
        subject.run(context)  # Probe purpose remains unusable by the grade entry.
    for handle in handles:
        with pytest.raises(ValueError, match="^current_authenticated_native_intake_required$"):
            subject.execution._native_arguments(handle)
    assert "HF_TOKEN" not in os.environ and not subject.execution._NATIVE_INTAKES
    assert formatted == forbidden == hosted.offline.denied == state.store.calls == state.store.commits == state.children == []
    assert len(state.original_gets) == 4 and len(state.retained_gets) == gets
    assert len(hosted.offline.prepared) == preparations
    assert not any(paths[name].exists() for name in ("attempt_store", "direction_file", "destination"))
    assert not any((paths["state_root"] / name).exists() for name in (
        "claim-reserved.json", "claim-receipt.json", "retention-reserved.json", "retention-receipt.json"))
    assert (paths["hydration_root"].exists()) == (gets > 0)  # Failed local input state is retained.
    public = raw.decode() + captured.out + captured.err
    assert all(secret not in public for secret in (TOKEN, PRIVATE, canary, *NAMES, "https://", str(paths["state_root"])))
    record_property("refusal_receipt", json.dumps({"scenario": scenario, "point": point,
        "original_GETs": 4, "retained_GETs": gets, "real_F_preparer_calls": preparations,
        "native_handles_issued": len(handles), "all_handles_closed": True,
        "forbidden_calls": 0, "private_exception_formats": 0, "public_canary_absent": True,
        "protocol": protocol, "basis": "synthetic_IO_real_adapters_wrappers_F_and_public_validator_not_historical_cause"},
        sort_keys=True))
