"""Prospective static exception codes, never native execution or a private read."""

import socket
import subprocess

import pytest

import gpt54_time_budget_codex_observation as native
import gpt54_time_budget_result_readout as readout
import gpt54_time_budget_v2_ci as ci
from core import azure_ai_clients
from core.time_budget_observation_deadline import TimeBudgetObservation
from gpt54_v2_grading_input import V2GradingInputRefused


SECRET = "SYNTHETIC_PRIVATE_TOKEN Authorization: Bearer hidden /private/input.json provider body"
GENERIC = "execution_refused_or_uncertain"
NATIVE_REASON = "registered_codex_route_required"


@pytest.fixture
def no_effects(monkeypatch):
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append("forbidden_effect_or_exception_formatting")
        raise AssertionError("static taxonomy crossed its side-effect boundary")

    for owner, names in (
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (subprocess, ("Popen",)), (TimeBudgetObservation, ("__init__",)),
        (azure_ai_clients, ("OpenAI", "AzureOpenAI", "DefaultAzureCredential")),
        (native, ("run_codex_observation",)), (ci.observation, ("run_first_v2_observation",)),
        (ci, ("prepare_and_claim", "execute", "retain")),
        (readout.native_execution, ("prepare_and_claim", "execute", "retain")),
        (readout, ("_read_result",)),
        (native.CodexObservationRefused, ("__str__",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    yield attempted
    assert attempted == []


def _classified(error, category, reason):
    receipt = ci._execution_failure("observation_callable", error)
    assert receipt == {"outcome": "refused_or_uncertain", "returned": None, "failure": {
        "stage": "observation_callable", "category": category, "reason": reason,
    }}
    ci._check_execution_failure(receipt)
    assert SECRET not in ci._bytes(receipt).decode()
    return receipt


@pytest.mark.parametrize("scenario", [
    "native_guards", "unknown_native", "other_class_code", "no_args", "non_string",
    "string_subclass", "multiple_args", "malformed_args", "legacy_compatibility", "readout_projection",
])
def test_time_budget_native_failure_taxonomy(scenario, no_effects, capsys):
    if scenario == "native_guards":
        # Literal representatives of identity, provider, direction, path,
        # capture and parser guards in the accepted native callable.
        for reason in (
            "independent_identity_size_bound", NATIVE_REASON, "direction_schema",
            "execution_binding_type", "native_source_overlap", "input_registration_path_alias",
            "codex_provider_not_installed", "codex_runner_result_shape", "captured_deliverable_bytes",
            "result_member_symlink", "invalid_arguments",
        ):
            with pytest.raises(native.CodexObservationRefused) as caught:
                native._require(False, reason)
            _classified(caught.value, "observation_refused", reason)
    elif scenario == "legacy_compatibility":
        legacy = (
            (ci.FirstV2CIRefused, "controller_refused", "execution_already_consumed"),
            (ci.observation.FirstV2ObservationRefused, "observation_refused", "direction_not_current"),
            (ci.registration.TimeBudgetRegistrationRefused, "registration_refused",
             "observation_handoff_consumption_refused"),
            (ci.registration.TimeBudgetConsumptionRefused, "registration_refused", "prepared_observation_binding"),
            (ci.ObservationDeadlineRefused, "deadline_refused", ci.OWNERSHIP_REQUIRED),
        )
        for kind, category, reason in legacy:
            _classified(kind(reason), category, reason)
            # Expanding the receipt vocabulary must not expand these classes'
            # ability to preserve a previously generic native-only reason.
            _classified(kind(NATIVE_REASON), category, GENERIC)
            _classified(kind(SECRET), category, GENERIC)
        for kind, category in (
            (ValueError, "validation_refused"), (TypeError, "type_error"), (OSError, "io_error"),
            (KeyboardInterrupt, "interrupted"), (AttributeError, "attribute_error"),
            (KeyError, "key_error"), (RuntimeError, "unexpected_error"),
        ):
            _classified(kind(SECRET), category, GENERIC)
        _classified(ValueError(NATIVE_REASON), "validation_refused", GENERIC)
        _classified(V2GradingInputRefused("independent runtime source mismatch"), "validation_refused", GENERIC)
        receipt = _classified(ci.observation.FirstV2ObservationRefused("direction_not_current"),
                              "observation_refused", "direction_not_current")
        ci._emit_execution_failure(receipt)
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == (
            '{"category":"observation_refused","format":"gpt54-time-budget-first-v2-ci-failure-v1",'
            '"reason":"direction_not_current","stage":"observation_callable"}\n'
        )
    elif scenario == "readout_projection":
        receipt = _classified(native.CodexObservationRefused(NATIVE_REASON), "observation_refused", NATIVE_REASON)
        # Projection-only synthetic bindings, not a request or a checked live
        # source context. No transport, claim, original input or receipt read.
        source = {"sha": "1" * 40, "tree": "2" * 40}
        request = {"cell": dict(readout.native_execution.CELL), "registration_sha256": "3" * 64,
                   "execution_request_identity": ci._identity(b"synthetic unissued request"),
                   "completion": {"source": source, "claim_commit": "4" * 40}}
        manifest = {
            "format": readout.UNCERTAINTY_MANIFEST_FORMAT,
            "observation": {**request["cell"], "reviewed_source_sha": source["sha"],
                "reviewed_source_tree": source["tree"], "registration_sha256": request["registration_sha256"],
                "input_sha256": "5" * 64},
            "request_identity": request["execution_request_identity"], "claim_commit": "4" * 40,
            "claim_identity": ci._identity(b"synthetic unread claim"), "execution_receipt": receipt,
            "result": "unavailable_no_fabricated_study_row", "files": {}, "grading_performed": False,
        }
        data = readout.native_execution._encoded(manifest)
        summary = readout.project_uncertainty_manifest(data, {"request": request})
        assert summary == {**readout.UNCERTAINTY_SUMMARY, "failure": receipt["failure"],
                           "observed_manifest_identity": ci._identity(data)}
        assert summary["manifest_identity_basis"] == "observed_not_independently_expected"
        assert summary["native_model_calls_and_cost"] == "unavailable"
        assert summary["claim_and_request_objects"] == "not_reread"
        assert summary["terminal_reason"] is summary["usage"] is summary["cleanup_complete"] is None
        assert summary["host_reusable"] is None
        public = ci._bytes(summary).decode()
        assert all(value not in public for value in (
            SECRET, "CodexObservationRefused", "execution_receipt", "claim_identity", "input.json", "Authorization",
        ))
        for change in (
            {"reason": SECRET}, {"reason": NATIVE_REASON + "_unregistered"},
            {"reason": [NATIVE_REASON]}, {"message": SECRET}, {"category": "native_unregistered"},
        ):
            invalid = {**manifest, "execution_receipt": {
                **receipt, "failure": {**receipt["failure"], **change},
            }}
            with pytest.raises(ci.FirstV2CIRefused) as caught:
                readout.project_uncertainty_manifest(readout.native_execution._encoded(invalid), {"request": request})
            assert caught.value.args == ("execution_failure_schema",)
    else:
        class StringSubclass(str):
            pass

        class MalformedNative(native.CodexObservationRefused):
            @property
            def args(self):
                return [NATIVE_REASON]  # Not BaseException's tuple contract.

        arguments = {
            "unknown_native": (SECRET,),
            "other_class_code": (ci.OWNERSHIP_REQUIRED,),
            "no_args": (),
            "non_string": ({"secret": SECRET},),
            "string_subclass": (StringSubclass(NATIVE_REASON),),
            "multiple_args": (NATIVE_REASON, SECRET),
            "malformed_args": (),
        }
        kind = MalformedNative if scenario == "malformed_args" else native.CodexObservationRefused
        _classified(kind(*arguments[scenario]), "validation_refused", GENERIC)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
    assert no_effects == []
