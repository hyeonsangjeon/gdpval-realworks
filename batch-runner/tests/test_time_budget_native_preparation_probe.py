"""Real model-free preparation with synthetic HTTP/source facts, never a grade."""

from contextlib import contextmanager
from copy import deepcopy
import json
import os
import shlex
import signal
import time

import pytest

import gpt54_time_budget_native_grading_ci as subject
from gpt54_prepared_input_attestation import _identity
from .test_time_budget_native_grading_ci import (
    case, dual_roots, handoff_source_seed, handoff_sources, hosted, offline,
)
from .test_time_budget_native_grading_intake import NAMES, PRIVATE, TOKEN


@pytest.mark.parametrize("scenario", [
    "ready", "original", "file", "preparation", "deadline_originals", "deadline_preparation",
    "context_exit", "private_error", "derived_drift",
])
def test_native_task3_preparation_probe(hosted, monkeypatch, capsys, record_property, scenario):
    """Actual controller CLI/context/F validators; every paid/write edge is trapped."""
    state, paths = hosted.state, hosted.paths
    canary = "hf_SECRET_CANARY_probe_private_exception_payload_not_a_credential"
    forbidden, formatted, handles = [], [], []

    class PrivateFailure(ValueError):
        def __str__(self):
            formatted.append(True)
            raise AssertionError("private probe exception was formatted")

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
    # The inherited offline fixture also traps real network, HF writes, model
    # constructors, native generation, Step8's judge and unowned subprocesses.
    assert not {"source_repo_id", "source_revision", "source_identity_document_sha256"} & hosted.case.payload.keys()
    assert hosted.original_step0 == hosted.case.seed.step0.read_bytes() and len(hosted.original_step0) == 218405
    for name in ("AZURE_AI_ROUTE_PROFILE", "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES",
                 "AZURE_AI_EXPECTED_DIRECT_ACCOUNT", "FOUNDRY_PROJECT_ENDPOINT"):
        monkeypatch.delenv(name)

    request = deepcopy(hosted.request)
    request.update(format=subject.PROBE_REQUEST_FORMAT, purpose=subject.PROBE_PURPOSE,
                   policy=deepcopy(subject.PROBE_POLICY))
    del request["storage"]  # No grading parent, namespace authority or claim permission.

    def selected(value):
        data = subject.bridge.reader._bytes(value)
        monkeypatch.setenv("TIME_BUDGET_GRADE_REQUEST_JSON", data.decode())
        monkeypatch.setenv("REQUEST_SHA256", _identity(data)["sha256"])
        return hosted.cli[:-1] + [_identity(data)["sha256"]]

    cli = selected(request)
    monkeypatch.setenv("TIME_BUDGET_NATIVE_OPERATION", "prepare-probe")
    arguments = {**hosted.arguments, "request_json": subject.bridge.reader._bytes(request).decode(),
                 "expected_request_sha256": cli[-1], "preparation_only": True}

    if scenario == "ready":
        workflow, steps = hosted.workflow, hosted.workflow["jobs"][subject.JOB]["steps"]
        inputs = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
        assert inputs["operation"] == {"description": "Explicit operation; preparation cannot authorize a grade",
            "required": True, "type": "choice", "default": "grade", "options": ["grade", "prepare-probe"]}
        assert set(workflow["jobs"]) == {"grade"} and workflow["jobs"]["grade"]["timeout-minutes"] == 270
        assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
        probe = next(step for step in steps if step.get("id") == "probe")
        check = next(step for step in steps if step.get("id") == "probe_request")
        grade = next(step for step in steps if step.get("id") == "grade")
        assert probe["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
        assert check["if"] == probe["if"] == "inputs.operation == 'prepare-probe'" and probe["timeout-minutes"] == 6
        assert grade["if"] == "inputs.operation == 'grade'" and grade["timeout-minutes"] == 252
        assert steps.index(check) < steps.index(probe) and "env" not in check
        for step in steps:
            if "AZURE_CLIENT_ID" in json.dumps(step) or "--verify-session" in step.get("run", "") or "preflight_grading_renderer.py" in step.get("run", ""):
                assert step["if"] == "inputs.operation == 'grade'"
        for operation, minutes in (("grade", 269), ("prepare-probe", 19)):
            other = "prepare-probe" if operation == "grade" else "grade"
            assert sum(step["timeout-minutes"] for step in steps if step.get("if") != "inputs.operation == '" + other + "'") == minutes
        assert "timeout --signal=TERM --kill-after=5s 300s python3 " in probe["run"]
        assert subject.PROBE_SECONDS == 300 and subject.intake.TRANSFER_TIMEOUT_SECONDS == 120 and subject.bridge.SECONDS == 60
        for step, operation in ((check, "validate-probe-request"), (probe, "prepare-probe")):
            command = step["run"][step["run"].index("python3 "):]
            argv = [os.path.expandvars(part) for part in shlex.split(command.replace("\\\n", ""))]
            assert argv == ["python3", str(paths["controller_root"] / subject.HELPER), operation, *cli]
        completion = next(step for step in steps if step.get("id") == "completion")
        assert "verify-probe-completion" in completion["run"] and "verify-completion" in completion["run"]
        assert "steps.probe.outcome != 'skipped'" in completion["if"]
        assert steps[-1]["if"] == "always() && steps.completion.outputs.validated == 'true'"
        assert steps[-1]["with"]["path"] == "${{ runner.temp }}/time-budget-task3-grade/completion.json"
        assert "time-budget-native-task3-preparation-completion" in steps[-1]["with"]["name"]
        assert subject.main(["validate-probe-request", *cli]) == 0
        assert json.loads(capsys.readouterr().out) == {"outcome": "validated_not_execution_authority"}
        # Both CLI and direct operations reject the other independently bound
        # purpose before credentials, local state or any effectful call.
        for value, operation in ((request, "run"), (request, "validate-request"),
                                 (hosted.request, "prepare-probe"), (hosted.request, "validate-probe-request")):
            wrong_cli = selected(value)
            assert subject.main([operation, *wrong_cli]) == 2
            assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        with subject.checked_request(**hosted.arguments) as context:
            with pytest.raises(ValueError):
                subject.prepare_probe(context)
        with subject.checked_request(**arguments) as context:
            with pytest.raises(ValueError):
                subject.run(context)
        cli = selected(request)
        for mutation in ("digest", "source", "cell", "registration", "step0", "permission", "storage"):
            changed = deepcopy(request)
            if mutation == "source":
                changed["completion"]["source"]["sha"] = "0" * 40
            elif mutation == "cell":
                changed["cell"]["repeat"] = 2
            elif mutation == "registration":
                changed["registration_sha256"] = "0" * 64
            elif mutation == "step0":
                changed["step0"]["identity"]["sha256"] = "0" * 64
            elif mutation == "permission":
                changed["policy"]["grading_allowed"] = True
            elif mutation == "storage":
                changed["storage"] = deepcopy(hosted.request["storage"])
            wrong_cli = selected(changed)
            if mutation == "digest":
                wrong_cli[-1] = "0" * 64
            assert subject.main(["prepare-probe", *wrong_cli]) == 2
            assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        cli = selected(request)
        for name, value in (("GITHUB_ACTOR", "wrong-owner"), ("GITHUB_RUN_ATTEMPT", "2"),
                            ("GITHUB_SHA", "0" * 40)):
            with monkeypatch.context() as drift:
                drift.setenv(name, value)
                assert subject.main(["prepare-probe", *cli]) == 2
                assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        workflow_path = paths["controller_root"] / subject.WORKFLOW
        original = workflow_path.read_bytes()
        try:
            workflow_path.write_bytes(original + b"\n# Synthetic unreviewed source drift\n")
            assert subject.main(["prepare-probe", *cli]) == 2
            assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
        finally:
            workflow_path.write_bytes(original)
        assert state.original_gets == state.retained_gets == state.store.calls == forbidden == []
        assert not paths["state_root"].exists()

    now = [1000.0]
    if scenario.startswith("deadline_"):
        monkeypatch.setattr(time, "monotonic", lambda: now[0])
    if scenario in {"original", "file", "preparation"}:
        state.fault = scenario
    real_originals = subject._originals

    def originals(*args, **kwargs):
        if scenario == "private_error":
            raise PrivateFailure(canary)
        result = real_originals(*args, **kwargs)
        if scenario == "deadline_originals":
            now[0] += 300
        return result

    monkeypatch.setattr(subject, "_originals", originals)
    real_context = subject.execution.prepare_native_task3_grading_execution

    @contextmanager
    def observe_context(**kwargs):
        try:
            with real_context(**kwargs) as handle:
                handles.append(handle)
                assert handle in subject.execution._NATIVE_INTAKES and "HF_TOKEN" not in os.environ
                if scenario == "deadline_preparation":
                    now[0] += 300
                elif scenario == "derived_drift":
                    path = paths["execution_input_directory"] / subject.preparation.RESULT
                    path.write_bytes(path.read_bytes() + b" ")
                yield handle
        finally:
            assert all(handle not in subject.execution._NATIVE_INTAKES for handle in handles)
        if scenario == "context_exit":
            raise PrivateFailure(canary)

    monkeypatch.setattr(subject.execution, "prepare_native_task3_grading_execution", observe_context)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    previous_term = signal.getsignal(signal.SIGTERM)
    record_property("operation", "actual_controller_CLI_prepare_probe")
    status = subject.main(["prepare-probe", *cli])
    captured = capsys.readouterr()
    assert status == (0 if scenario == "ready" else 2), (state.stages, state.failures, captured)
    assert captured == ("", "")
    raw = (paths["state_root"] / "completion.json").read_bytes()
    value = json.loads(raw)
    assert len(raw) <= 4096 and signal.getsignal(signal.SIGTERM) == previous_term
    assert "HF_TOKEN" not in os.environ and subject.execution._NATIVE_INTAKES == {}
    assert formatted == forbidden == state.store.calls == state.store.commits == state.children == []
    assert not any(paths[name].exists() for name in ("attempt_store", "direction_file", "destination"))
    assert not any((paths["state_root"] / name).exists() for name in (
        "claim-reserved.json", "claim-receipt.json", "retention-reserved.json", "retention-receipt.json"))
    public = raw.decode() + captured.out + captured.err
    assert all(private not in public for private in (TOKEN, PRIVATE, canary, *NAMES, "https://", str(paths["state_root"])))
    assert value["status"] == ("ready" if scenario == "ready" else "refused")
    assert value["grading_authority"] is value["handle_reusable"] is value["retry_allowed"] is False
    with subject.checked_request(**arguments, completion_only=True) as context:
        subject.validate_probe_completion(value, context)
        with pytest.raises(subject.NativeGradingCIRefused, match="^completion_is_not_preparation_authority$"):
            subject.prepare_probe(context)
        for mutation in ({"raw_error": canary}, {"status": "success"}, {"grading_authority": True},
                         {"retry_allowed": True}, {"handle_reusable": True}, {"format": subject.FORMAT},
                         {"expected_result_identity": {"sha256": "0" * 64, "size": 1}}):
            with pytest.raises(ValueError):
                subject.validate_probe_completion({**deepcopy(value), **mutation}, context)
        for mutation in ({"state": "ready"}, {"category": canary}):
            changed = deepcopy(value)
            changed["diagnostics"]["originals"].update(mutation)
            with pytest.raises(ValueError):
                subject.validate_probe_completion(changed, context)
        with pytest.raises(ValueError):
            subject.validate_completion(value, context)
    for handle in handles:
        with pytest.raises(subject.execution.GradingExecutionRefused, match="^current_authenticated_native_intake_required$"):
            subject.execution._native_arguments(handle)
    assert subject.main(["verify-probe-completion", *cli]) == 0
    assert json.loads(capsys.readouterr().out) == {"outcome": "validated_not_execution_authority"}
    assert subject.main(["verify-completion", *cli]) == 2
    assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
    assert subject.main(["prepare-probe", *cli]) == 2  # Never adopt a receipt or preserved partial inputs.
    assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
    assert (paths["state_root"] / "completion.json").read_bytes() == raw and forbidden == state.store.calls == []
    if scenario == "ready":
        assert len(state.original_gets) == len(state.retained_gets) == 4 and len(hosted.offline.prepared) == 1
        assert all(item == {"state": "completed", "category": None} for item in value["diagnostics"].values())
        verified = value["verified_preparation"]
        assert verified["result_identity"] == _identity(hosted.data)
        assert (paths["hydration_root"] / subject.native.observation.RESULT).read_bytes() == hosted.data
        assert (paths["preparation_root"] / subject.preparation.RESULT).read_bytes() == hosted.data
        assert verified["derived_result_identity"] == _identity((paths["execution_input_directory"] / subject.preparation.RESULT).read_bytes())
        assert verified["derived_result_fingerprint"] != value["expected_result_fingerprint"]
    else:
        failed_stage = {"original": "originals", "private_error": "originals", "deadline_originals": "originals",
                        "context_exit": "context_exit"}.get(scenario, "intake_preparation")
        assert value["diagnostics"][failed_stage]["state"] == "started"
        assert value["diagnostics"][failed_stage]["category"] in subject.FAILURE_CATEGORIES
        assert (value["verified_preparation"] is not None) == (scenario == "context_exit")
        assert len(state.original_gets) == (0 if scenario == "private_error" else 4)
        assert len(state.retained_gets) == (0 if failed_stage == "originals" else 3 if scenario == "file" else 4)
    record_property("bounded_outcome", json.dumps({"scenario": scenario, "status": value["status"],
        "original_GETs": len(state.original_gets), "retained_GETs": len(state.retained_gets),
        "real_F_preparer_calls": len(hosted.offline.prepared), "native_handles_closed": True,
        "direction_claim_executor_model_private_write_calls": 0, "synthetic_step0_bytes": 218405,
        "source_HTTP_auth_namespace_facts": "synthetic_not_live_host_or_private_evidence"}, sort_keys=True))
