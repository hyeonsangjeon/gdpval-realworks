"""Synthetic retained Task3 bytes -> real F preparation; no intake/model/grade run."""

from contextlib import ExitStack
from copy import deepcopy
import gzip
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from types import SimpleNamespace

import httpx
import pytest

import gpt54_time_budget_native_grading_intake as subject
from core.result_fingerprint import inference_result_fingerprint
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_time_budget_comparison import (
    _handoff_arguments, dual_roots, handoff_source_seed as _small_seed, handoff_sources,
)

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
TOKEN = "hf_synthetic_bridge_credential_NEVER_REAL"
PRIVATE = "PRIVATE_SYNTHETIC_NATIVE_PROSE"
NAMES = ("PRIVATE_FIRST.txt", "PRIVATE_SECOND.bin")
ORIGINAL_STEP0 = dict(subject.native.originals.STEP0_PIN)


@pytest.fixture(scope="module")
def handoff_source_seed(tmp_path_factory, dual_roots):
    seed = _small_seed.__wrapped__(tmp_path_factory, dual_roots)
    small = seed.step0.read_bytes()
    full = small + b" " * (ORIGINAL_STEP0["size"] - len(small))
    assert len(full) == 218405 > 65536 and json.loads(full) == json.loads(small)
    seed.step0.write_bytes(full)
    seed.step0_sha = _identity(full)["sha256"]
    assert seed.step0_sha != ORIGINAL_STEP0["sha256"]
    return seed


@pytest.fixture
def offline(monkeypatch, handoff_sources, dual_roots):
    from huggingface_hub import HfApi, constants
    from core import azure_ai_clients, rubric_loader
    from core.time_budget_observation_deadline import TimeBudgetObservation
    import gpt54_time_budget_grading_execution
    import step8_grade

    denied, prepared = [], []

    def forbidden(*args, **kwargs):
        denied.append(True)
        raise AssertionError("native grading intake crossed its model-free boundary")

    for owner, names in (
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (subprocess, ("Popen", "check_call", "check_output")), (os, ("system",)),
        (HfApi, ("create_repo", "create_commit", "upload_file", "delete_file", "delete_repo")),
        (rubric_loader, ("snapshot_download", "hf_hub_download", "HfApi")),
        (subject.native, ("prepare_and_claim", "execute", "retain")),
        (subject.native.observation, ("run_codex_observation",)),
        (gpt54_time_budget_grading_execution, ("execute_first_observation_grading",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                        step8_grade.Grader, TimeBudgetObservation):
        monkeypatch.setattr(constructor, "__init__", forbidden)

    def local_git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        position = command.index("-C")
        assert Path(command[position + 1]) in {handoff_sources.runtime, handoff_sources.frozen,
                                              dual_roots["runtime"], dual_roots["frozen"]}
        assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        assert "HF_TOKEN" not in kwargs["env"] and kwargs["timeout"] == 60
        kwargs["timeout"] = 30  # Named, guarded, local fixture Git only.
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", local_git)
    ordinary_sleep = time.sleep

    def no_online_sleep(seconds):
        if not constants.HF_HUB_OFFLINE:
            forbidden()
        ordinary_sleep(seconds)

    monkeypatch.setattr(time, "sleep", no_online_sleep)
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    for key in subject.OTHER_CREDENTIALS | {"HF_TOKEN"}:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(subject.native.originals, "PARQUET_PIN", _identity(handoff_sources.parquet.read_bytes()))
    monkeypatch.setattr(subject.native.originals, "STEP0_PIN", _identity(handoff_sources.step0.read_bytes()))
    real_prepare = subject.preparation.prepare_observation_grading

    def prepare(*args, **kwargs):
        assert not any(os.environ.get(key) for key in subject.OTHER_CREDENTIALS | {"HF_TOKEN"})
        assert constants.HF_HUB_OFFLINE and os.environ["HF_HUB_OFFLINE"] == "1"
        assert TOKEN not in repr((args, kwargs))
        prepared.append(kwargs)
        return real_prepare(*args, **kwargs)  # Actual source/input/result/file/F validators.

    monkeypatch.setattr(subject.preparation, "prepare_observation_grading", prepare)
    yield SimpleNamespace(denied=denied, prepared=prepared)
    assert denied == []


@pytest.fixture
def case(handoff_sources, dual_roots, tmp_path, offline):
    seed = handoff_sources
    handoff = _handoff_arguments(seed, tmp_path, condition="codex", task_index=2)
    with ExitStack() as sources:
        marker, _, _ = subject.registration._observation_handoff_data(seed.plan, sources=sources, **handoff)
    assert marker["observation"]["task_id"] == subject.CELL["task_id"]
    assert not handoff["destination"].exists()  # Reconstruction publishes no inference handoff.
    assert marker["inputs"]["step0_manifest"] == _identity(seed.step0.read_bytes())
    control = {
        **subject.reader.CONTROL_STATIC, "identity": marker["observation"], "admitted": True,
        "first_start_monotonic": 1.0, "terminal_reason": "completed", "generation_elapsed_seconds": 2.0,
        "cleanup_deadline_monotonic": 23.0, "cleanup_finished_monotonic": 4.0, "cleanup_elapsed_seconds": 1.0,
        "interruption_attempted": False, "interruption_acknowledged": False,
        "interruption_acknowledgement_scope": "local_runtime_only_not_remote_cancellation",
        "cleanup_complete": True, "cleanup_expired": False, "owned_processes_stopped": True,
        "host_reusable": True, "remote_cancellation_confirmed": False, "remote_billing_bound": False,
    }
    prepared_identity = _identity(subject.reader._bytes(marker))
    host = {"policy": "linux-boot-namespace-user-ci-instance-v1", "instance_sha256": "1" * 64,
            "ci_instance_sha256": "2" * 64, "ownership_confirmed": False}
    direction = SimpleNamespace(expected="3" * 64, host=host, paths={"synthetic_only": PRIVATE},
                                binding=SimpleNamespace(preparation_sha256=prepared_identity["sha256"],
                                                        preparation_size=prepared_identity["size"]))
    bodies = [PRIVATE.encode() + b"a" * (200000 - len(PRIVATE)), b"b" * 208601]
    native = subject.native.observation
    payload, files = native._capture({"success": True, "text": PRIVATE, "error": None,
        "files": [{"filename": name, "content": body} for name, body in zip(NAMES, bodies, strict=True)],
        "time_budget_observation": control, "handoff_preparation_identity": prepared_identity,
        "codex_diagnostics": {"items_seen": 3, "http_status_code": None, "rate_limit_kind": None}},
        marker, direction, {"settings_sha256": "4" * 64, "config_overrides_sha256": "5" * 64,
            "sdk_version": native.PINNED_CODEX_SDK_VERSION, "cli_version": native.PINNED_CODEX_CLI_VERSION})
    # Control metadata above is synthetic capture input, never a kernel/host verdict.
    assert sum(map(len, files.values())) == 408601 and len(files) == 2
    completion = {
        "format": subject.native.ENVELOPE_VERSION, **subject.CELL,
        "source": {"sha": seed.runtime_sha, "tree": seed.runtime_tree},
        "ci": {"run_id": "1001", "run_number": 5, "attempt": 1, "job": "observation"},
        "request_sha256": "6" * 64, "host_sha256": host["instance_sha256"],
        "claim_commit": "7" * 40, "output_commit": "8" * 40, "retention": "acknowledged",
        "result_identity": None, "result_fingerprint": payload["result_fingerprint"], "status": "success",
        "usage": None, "terminal_reason": "completed", "cleanup_complete": True, "host_reusable": True,
        "grading_performed": False, "retry_allowed": False, "other_cells_executed": 0,
    }
    parent = tmp_path / "private-intake"
    parent.mkdir(mode=0o700)
    paths = {"controller_root": dual_roots["runtime"], "runtime_root": seed.runtime,
        "frozen_root": seed.frozen, "input_registration_root": seed.frozen, "dataset_parquet": seed.parquet,
        "reference_root": seed.references, "step0_manifest": seed.step0,
        "hydration_root": parent / "hydration", "destination": parent / "grading"}
    with subject.registration._reviewed_source(dual_roots["runtime"], dual_roots["runtime_sha"], {subject.HELPER}) as (_, tree, _):
        controller = {"sha": dual_roots["runtime_sha"], "tree": tree}
    step0, _ = subject.native._input_contract(seed.plan, seed.frozen)
    request = {"format": subject.REQUEST_FORMAT, "purpose": subject.PURPOSE, "controller": controller,
        "cell": dict(subject.CELL), "completion": completion, "registration_sha256": subject.seal(seed.plan),
        "dataset_sha256": subject.seal(seed.plan["shared"]["dataset"]), "frozen_source": {"sha": seed.frozen_sha, "tree": seed.frozen_tree},
        "input_registration": {"sha": seed.frozen_sha, "tree": seed.frozen_tree, "path": subject.registration.SOURCE_PROFILE},
        "step0": step0, "deliverables": dict(subject.DELIVERABLES), "paths": {key: str(value) for key, value in paths.items()}}
    original_step0 = seed.step0.read_bytes()
    yield SimpleNamespace(seed=seed, paths=paths, marker=marker, payload=deepcopy(payload), files=files, request=request)
    if seed.step0.read_bytes() != original_step0:
        seed.step0.write_bytes(original_step0)


@pytest.mark.parametrize("scenario", [
    "positive", "result_digest", "fingerprint", "file_digest", "file_size", "path", "revision", "cell", "R",
    "R_tree", "private_identity", "input_seal", "step0", "gzip_metadata", "gzip_file", "overbudget", "partial", "no_clobber",
    "credential_environment", "credential_body", "private_field",
])
def test_time_budget_native_retained_grading_intake(case, offline, monkeypatch, capsys, scenario):
    completion, paths = case.request["completion"], case.paths
    payload = case.payload
    records = payload["results"][0]["deliverable_file_records"]
    expected_calls = 4 if scenario in {"positive", "partial"} else 2
    if scenario == "path":
        records[0]["path"] = "../" + NAMES[0]
        payload["results"][0]["deliverable_files"][0] = records[0]["path"]
    elif scenario == "cell":
        payload["time_budget_observation"]["identity"]["task_id"] = case.seed.task_ids[1]
    elif scenario == "R":
        payload["observation_execution"]["runtime_source"]["source_sha"] = "9" * 40
    elif scenario == "input_seal":
        payload["observation_execution"]["inputs"]["source_projection_sha256"] = "9" * 64
        payload["time_budget_observation"]["identity"]["input_sha256"] = subject.seal(payload["observation_execution"]["inputs"])
    elif scenario == "private_field":
        payload["results"][0]["observability"]["private_diagnostic"] = PRIVATE
    elif scenario == "credential_body":
        first = sorted(case.files)[0]
        case.files[first] = TOKEN.encode() + case.files[first][len(TOKEN):]
        records[0].update(_identity(case.files[first]))
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    data = subject.reader._bytes(payload)
    completion.update(result_identity=_identity(data), result_fingerprint=payload["result_fingerprint"])
    if scenario == "result_digest":
        completion["result_identity"]["sha256"] = "0" * 64
    elif scenario == "fingerprint":
        completion["result_fingerprint"] = "0" * 64
    elif scenario == "R_tree":
        completion["source"]["tree"] = "0" * 40
    elif scenario == "step0":
        case.seed.step0.write_bytes(case.seed.step0.read_bytes()[:-1] + b"\n")
    elif scenario == "no_clobber":
        paths["hydration_root"].with_name(paths["hydration_root"].name + subject.RESERVATION_SUFFIX).write_bytes(b"prior partial")
    if scenario in {"R_tree", "step0", "no_clobber", "credential_environment"}:
        expected_calls = 0
    elif scenario in {"revision", "private_identity", "gzip_metadata"}:
        expected_calls = 1
    elif scenario in {"file_digest", "file_size", "gzip_file", "credential_body", "overbudget"}:
        expected_calls = 3
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    if scenario == "credential_environment":
        monkeypatch.setenv("OPENAI_API_KEY", PRIVATE)
    prefix, _, _ = subject.native.shared._namespace(subject.CELL)
    member = prefix + "/result/" + subject.native.observation.RESULT
    immutable = completion["output_commit"]
    target = subject.reader.metadata.TARGET
    bodies = {f"/datasets/{target}/raw/{immutable}/{member}": data,
              **{f"/datasets/{target}/resolve/{immutable}/{prefix}/result/upload/{name}": body
                 for name, body in case.files.items()}}
    calls, formatted = [], []
    offset, monotonic = [0.0], time.monotonic
    if scenario == "overbudget":
        monkeypatch.setattr(subject.storage.time, "monotonic", lambda: monotonic() + offset[0])

    class SecretTimeout(httpx.ReadTimeout):
        def __str__(self):
            formatted.append(True)
            raise AssertionError("private transport exception was formatted")

    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs == {"retries": 0, "trust_env": False}

        def handle_request(self, request):
            calls.append(request)
            number = len(calls)
            assert number <= 4 and request.method == "GET" and request.headers["accept-encoding"] == "identity"
            assert request.headers["authorization"] == "Bearer " + TOKEN and "HF_TOKEN" not in os.environ
            assert all(0 < seconds <= 60 for seconds in request.extensions["timeout"].values())
            if scenario == "partial" and number == 4:
                raise SecretTimeout(PRIVATE + TOKEN, request=request)
            if number == 1:
                assert request.url.path == f"/api/datasets/{target}/revision/{immutable}"
                body = subject.reader._bytes({"id": target, "private": scenario != "private_identity",
                    "sha": "9" * 40 if scenario == "revision" else immutable})
            else:
                body = bodies[request.url.path]
            if number == 3:
                if scenario == "file_digest":
                    body = b"x" + body[1:]
                elif scenario == "file_size":
                    body += b"x"
                elif scenario == "overbudget":
                    offset[0] = 61.0
            headers = {"content-type": "application/json" if number <= 2 else "application/octet-stream"}
            if (scenario == "gzip_metadata" and number == 1) or (scenario == "gzip_file" and number == 3):
                headers["content-encoding"] = "gzip"
                body = gzip.compress(body, mtime=0)
            return httpx.Response(200, headers=headers, stream=httpx.ByteStream(body), request=request)

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    request_data = subject.reader._bytes(case.request)
    arguments = {"request_json": request_data.decode(), "expected_request_sha256": _identity(request_data)["sha256"]}
    if scenario == "positive":
        summary = subject.prepare_retained_native_task3_grading(**arguments)
        assert set(summary) == {"format", "status", "cell", "controller", "observation_source", "frozen_source",
            "registration_sha256", "request_identity", "execution_request_sha256", "output_commit", "claim_commit",
            "result_identity", "result_fingerprint", "input_binding_sha256", "deliverables", "preparation_identity",
            "materialized_grader_source_sha256", "launch_allowed", "execution_enabled", "grading_performed"}
        assert summary["status"] == "prepared" and len(offline.prepared) == 1
        assert summary["deliverables"] == {"verified_count": 2, "verified_bytes": 408601,
            "basis": "full_contents_verified_against_authenticated_result"}
        assert not any(summary[key] for key in ("launch_allowed", "execution_enabled", "grading_performed"))
        assert summary["controller"] != summary["observation_source"] != summary["frozen_source"]
        assert summary["result_identity"] == _identity(data) and summary["result_fingerprint"] == payload["result_fingerprint"]
        assert summary["input_binding_sha256"] == subject.seal(case.marker["inputs"])
        assert json.loads((paths["hydration_root"] / subject.READY).read_bytes()) == summary
        prepared_data = (paths["destination"] / subject.preparation.READY).read_bytes()
        assert summary["preparation_identity"] == _identity(prepared_data)
        prepared = json.loads(prepared_data)
        assert prepared["inputs"] == case.marker["inputs"] and prepared["inputs"]["step0_manifest"]["size"] == 218405
        assert not prepared["launch_allowed"] and not prepared["execution_enabled"]
        assert prepared["grader"]["derivation"] == "regular_tracked_F_source_blobs_not_a_runtime_checkout"
        assert prepared["grader"]["materialized_source_sha256"] == summary["materialized_grader_source_sha256"]
        assert summary["materialized_grader_source_sha256"] != subject.registration.FROZEN_TEMPLATE_SHA256
        assert (paths["destination"] / "source/batch-runner/step8_grade.py").read_bytes() == (case.seed.frozen / "batch-runner/step8_grade.py").read_bytes()
        assert (paths["destination"] / subject.preparation.RESULT).read_bytes() == data
        for name, body in case.files.items():
            assert (paths["hydration_root"] / "upload" / name).read_bytes() == body
            assert (paths["destination"] / subject.preparation.UPLOAD / name).read_bytes() == body
        for root in (paths["hydration_root"], paths["destination"]):
            assert root.stat().st_mode & 0o777 == 0o700
            for path in root.rglob("*"):
                assert path.stat().st_mode & 0o777 == (0o700 if path.is_dir() else 0o600)
                if path.is_file():
                    assert TOKEN.encode() not in path.read_bytes()
        public = subject.reader._bytes(summary).decode()
        assert not any(text in public for text in (PRIVATE, TOKEN, *NAMES, *case.request["paths"].values()))
        assert "inference_sha" not in case.request and "inference_sha" not in summary
    else:
        with pytest.raises(subject.NativeGradingIntakeRefused) as error:
            subject.prepare_retained_native_task3_grading(**arguments)
        assert error.value.args in {(reason,) for reason in (
            "native_grading_intake_refused", "response_size_bound", "encoded_or_failed_response",
            "destination_or_reservation_exists", "unexpected_credential_environment", "credential_in_retained_bytes")}
        assert offline.prepared == [] and not paths["destination"].exists()
        assert not (paths["hydration_root"] / subject.READY).exists()
        reservation = paths["hydration_root"].with_name(paths["hydration_root"].name + subject.RESERVATION_SUFFIX)
        if scenario == "no_clobber":
            assert reservation.read_bytes() == b"prior partial" and not paths["hydration_root"].exists()
        elif calls:
            assert reservation.is_file() and paths["hydration_root"].is_dir()
            assert json.loads(reservation.read_bytes())["request_identity"] == _identity(request_data)
        else:
            assert not reservation.exists() and not paths["hydration_root"].exists()
        if len(calls) >= 3:
            assert (paths["hydration_root"] / subject.native.observation.RESULT).read_bytes() == data
            found = [path for path in paths["hydration_root"].rglob("*") if path.is_file()]
            assert len(found) == (2 if scenario == "partial" else 1)
            if scenario == "partial":
                first = sorted(case.files)[0]
                assert (paths["hydration_root"] / "upload" / first).read_bytes() == case.files[first]
        assert not any(text in repr(error.value.args) for text in (PRIVATE, TOKEN, *NAMES))
    assert len(calls) == expected_calls and subject.SECONDS == 60 and formatted == []
    assert offline.denied == [] and capsys.readouterr() == ("", "")
