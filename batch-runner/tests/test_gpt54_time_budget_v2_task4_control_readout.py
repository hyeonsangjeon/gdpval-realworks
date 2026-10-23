"""Synthetic controls/Actions/Git only; real SDK, bounded transport and validators.

The historical cell/source/request are the fixed production bindings. All
control contents, host/input digests, reader CI identity and Git commits are
synthetic. No result body, cached credential or live host is inspected.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace

import httpx
import huggingface_hub
from huggingface_hub import HfApi, constants
from huggingface_hub.utils import _auth, _headers
import pytest
import yaml

import gpt54_time_budget_v2_task4_control_readout as subject

ROOT = Path(__file__).resolve().parents[2]
PARENT, CLAIM_COMMIT = "8" * 40, "9" * 40
TOKEN = "hf_SYNTHETIC_CONTROL_READER_NOT_A_CREDENTIAL"
CANARY = "hf_PRIVATE_CONTROL_CANARY_NOT_A_CREDENTIAL"
IDENTITY = {"source": {"sha": "a" * 40, "tree": "b" * 40},
            "ci": {"run_id": "123456789", "job": subject.JOB, "attempt": 1}}


def encoded(value):
    # Matches the existing native controller's retained control encoding.
    return (subject._canonical_json(value) + "\n").encode()


def controls():
    observation = {**subject.CELL, "reviewed_source_sha": subject.HISTORICAL_SOURCE["sha"],
                   "reviewed_source_tree": subject.HISTORICAL_SOURCE["tree"],
                   "registration_sha256": "1" * 64, "input_sha256": "2" * 64}
    identity = {"sha256": "3" * 64, "size": 1234}
    paths = {key: "/synthetic-private/" + CANARY + "/" + key for key in subject.PATH_FIELDS}
    paths.update(input_source_sha=subject.registration.ACCEPTED_BASE_SHA,
                 input_registration_path=subject.registration.SOURCE_PROFILE)
    admission = {
        "format": "gpt54-time-budget-first-codex-admission-v1", "observation": observation,
        "source": dict(subject.HISTORICAL_SOURCE), "request_identity": {**identity, "sha256": subject.REQUEST_SHA256},
        "preparation_identity": dict(identity), "input_binding_sha256": "4" * 64,
        "step0_provenance": {"repository_name_sha256": "5" * 64, "revision": "6" * 40,
                             "member": "synthetic/" + CANARY, "identity": dict(identity)},
        "host": {"policy": "linux-boot-namespace-user-ci-instance-v1", "instance_sha256": "7" * 64,
                 "ci_instance_sha256": "8" * 64, "ownership_confirmed": False},
        "ci": {"run_id": subject.HISTORICAL_RUN, "run_number": 7, "job": "observation", "attempt": 1},
        "direction_identity": dict(identity), "paths": paths, "expected_parent": "6" * 40,
        "storage": {"repository_name_sha256": subject.TARGET_SHA256, "branch": "main", "prefix": subject.PREFIX},
        "state": "permanently_consumed_not_completion",
    }
    returned = {"result_path": paths["destination"] + "/step2_inference_results.json",
                "result_identity": dict(identity), "result_fingerprint": "a" * 64, "status": "success",
                "observation": copy.deepcopy(observation), "grading_performed": False, "upload_performed": False}
    manifest = {"format": "gpt54-time-budget-first-codex-private-output-v1", "observation": copy.deepcopy(observation),
                "request_identity": dict(admission["request_identity"]), "claim_commit": CLAIM_COMMIT,
                "claim_identity": subject._identity(encoded(admission)),
                "execution_receipt": {"outcome": "returned", "returned": returned}, "result": "canonical_step2",
                "files": {subject.RESULT_MEMBER: dict(identity), "result/upload/" + CANARY + ".txt": dict(identity)},
                "grading_performed": False}
    return admission, manifest


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    attempted = []
    old_sleep, old_popen, old_logging = time.sleep, subprocess.Popen, logging.root.manager.disable

    def forbidden(*args, **kwargs):
        attempted.append("forbidden_effect")
        raise AssertionError(CANARY)

    for obj, names in (
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (huggingface_hub, ("get_token", "hf_hub_download", "snapshot_download")),
        (_auth, ("get_token",)), (_headers, ("get_token",)),
        (HfApi, ("whoami", "create_repo", "create_commit", "upload_file", "upload_folder", "delete_file",
                 "delete_repo", "create_branch", "get_paths_info", "list_repo_tree")),
    ):
        for name in names:
            monkeypatch.setattr(obj, name, forbidden)

    def bounded_local_process(args, *rest, **kwargs):
        # Source fixtures use real, fixture-owned Git, never a launcher/executor.
        if args[0] in ("git", "/usr/bin/git") and "-C" in args:
            assert Path(args[args.index("-C") + 1]).is_relative_to(tmp_path)
        elif args[:3] != ["/bin/bash", "--noprofile", "--norc"]:
            forbidden()
        return old_popen(args, *rest, **kwargs)

    def no_backoff(seconds):
        if not constants.HF_HUB_OFFLINE:
            forbidden()
        old_sleep(seconds)  # Local bounded Git subprocess reaping, not HTTP retry.

    monkeypatch.setattr(subprocess, "Popen", bounded_local_process)
    monkeypatch.setattr(time, "sleep", no_backoff)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "1")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    yield
    logging.disable(old_logging)
    assert attempted == []  # Suppression of a forbidden effect is still a test failure.


@pytest.fixture
def transport(monkeypatch):
    admission, manifest = controls()
    state = SimpleNamespace(calls=[], chunks=[], closed=[], admission=admission, manifest=manifest,
                            head={"id": subject.TARGET, "private": True, "sha": PARENT, "private_extra": CANARY},
                            raw={}, headers={}, status={}, stream={}, hook=None, failure=None)

    class Stream(httpx.SyncByteStream):
        def __init__(self, number, chunks):
            self.number, self.chunks = number, chunks

        def __iter__(self):
            for chunk in self.chunks:
                state.chunks.append((self.number, len(chunk)))
                yield chunk

        def close(self):
            state.closed.append(self.number)

    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs == {"retries": 0, "trust_env": False}

        def handle_request(self, request):
            state.calls.append(request)
            number = len(state.calls)
            assert number <= 3 and request.method == "GET"
            assert request.url.host == "huggingface.co"
            assert request.headers["authorization"] == "Bearer " + TOKEN
            assert request.headers["accept-encoding"] == "identity" and "cookie" not in request.headers
            assert "HF_TOKEN" not in os.environ  # Existing process-local HF scope, no token cache.
            if state.hook:
                state.hook(number)
            if state.failure == number:
                raise httpx.ReadTimeout(CANARY, request=request)
            payload = {1: state.head, 2: state.admission, 3: state.manifest}[number]
            data = state.raw.get(number, encoded(payload))
            chunks = state.stream.get(number, [data[:17], data[17:]])
            return httpx.Response(state.status.get(number, 200), request=request,
                                  headers=state.headers.get(number, {}), stream=Stream(number, chunks))

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    return state


CASES = [
    "returned", "returned_error", "uncertain", "uncertain_legacy", "no_receipt", "immutable_snapshot",
    "missing_token", "empty_token", "invalid_token", "telemetry", "nonprivate", "wrong_target", "bad_head",
    "head_404", "admission_404", "manifest_404", "head_duplicate", "admission_duplicate", "manifest_duplicate",
    "malformed", "array", "noncanonical", "nonfinite", "missing_field", "admission_extra", "manifest_extra",
    "claim_digest", "claim_size", "request_conflict", "observation_conflict", "returned_conflict", "result_conflict",
    "unavailable_conflict", "unsafe_file", "graded", "redirect", "timeout", "encoding", "length", "length_mismatch",
    "chunks", "head_chunks", "cumulative_deadline", "stream_deadline", "cookie", "wrong_path", "wrong_revision",
    "wrong_host", "wrong_method", "fourth_request",
]


@pytest.mark.parametrize("case", CASES)
def test_task4_control_transport(case, transport, monkeypatch, capsys, caplog):
    """One snapshot, genuine SDK/event hooks/stream limits, no live requests."""
    good = case in {"returned", "returned_error", "uncertain", "uncertain_legacy", "no_receipt", "immutable_snapshot"}
    admission, manifest = transport.admission, transport.manifest
    expected_calls, expected_stage = 3, "control_binding"
    if case == "returned_error":
        manifest["execution_receipt"]["returned"]["status"] = "error"
    elif case in ("uncertain", "uncertain_legacy", "no_receipt"):
        receipt = {"outcome": "refused_or_uncertain", "returned": None}
        if case == "uncertain":
            receipt["failure"] = {"stage": "observation_callable", "category": "io_error",
                                  "reason": "execution_refused_or_uncertain"}
        manifest.update(execution_receipt=None if case == "no_receipt" else receipt,
                        files={}, result="unavailable_no_fabricated_study_row")
    elif case == "immutable_snapshot":
        transport.hook = lambda number: transport.head.update(sha="f" * 40) if number == 2 else None
    elif case in ("missing_token", "empty_token", "invalid_token", "telemetry"):
        expected_calls, expected_stage = 0, "environment"
        if case == "missing_token":
            monkeypatch.delenv("HF_TOKEN")
            monkeypatch.setenv("HUGGING_FACE_HUB_TOKEN", TOKEN)  # Neither alias nor SDK cache is reader authority.
        elif case == "telemetry":
            monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", False)
        else:
            monkeypatch.setenv("HF_TOKEN", "" if case == "empty_token" else "invalid\n" + CANARY)
    elif case in ("nonprivate", "wrong_target", "bad_head"):
        expected_calls, expected_stage = 1, "head"
        key, value = {"nonprivate": ("private", False), "wrong_target": ("id", "unrelated/" + CANARY),
                      "bad_head": ("sha", CANARY)}[case]
        transport.head[key] = value
    elif case.endswith("_404"):
        expected_calls = {"head_404": 1, "admission_404": 2, "manifest_404": 3}[case]
        expected_stage = {1: "head", 2: "admission", 3: "output_manifest"}[expected_calls]
        transport.status[expected_calls] = 404
        transport.raw[expected_calls] = CANARY.encode()
    elif case.endswith("_duplicate"):
        expected_calls = {"head_duplicate": 1, "admission_duplicate": 2, "manifest_duplicate": 3}[case]
        expected_stage = {1: "head", 2: "admission", 3: "output_manifest"}[expected_calls]
        transport.raw[expected_calls] = b'{"duplicate":1,"duplicate":2}'
    elif case in ("malformed", "array", "noncanonical", "nonfinite"):
        expected_calls, expected_stage = 2, "admission"
        transport.raw[2] = {"malformed": (CANARY + "{").encode(), "array": b"[]",
                            "noncanonical": json.dumps(admission).encode(), "nonfinite": b'{"private":NaN}'}[case]
    elif case == "missing_field":
        admission.pop("host")
    elif case in ("admission_extra", "manifest_extra"):
        (admission if case == "admission_extra" else manifest)["raw_private_payload"] = CANARY
    elif case == "claim_digest":
        manifest["claim_identity"]["sha256"] = "0" * 64
    elif case == "claim_size":
        manifest["claim_identity"]["size"] = True
    elif case == "request_conflict":
        manifest["request_identity"]["size"] += 1
    elif case == "observation_conflict":
        manifest["observation"]["input_sha256"] = "0" * 64
    elif case == "returned_conflict":
        manifest["execution_receipt"]["returned"]["observation"]["registration_sha256"] = "0" * 64
    elif case == "result_conflict":
        manifest["files"][subject.RESULT_MEMBER]["sha256"] = "0" * 64
    elif case == "unavailable_conflict":
        manifest["execution_receipt"] = None  # A result without its corresponding receipt is not verified.
    elif case == "unsafe_file":
        manifest["files"]["result/upload/../" + CANARY] = manifest["files"].pop(subject.RESULT_MEMBER)
    elif case == "graded":
        manifest["grading_performed"] = True
    elif case in ("redirect", "timeout", "encoding", "length", "length_mismatch", "chunks"):
        expected_calls, expected_stage = 2, "admission"
        if case == "redirect":
            transport.status[2] = 302
            transport.headers[2] = {"location": "https://example.invalid/" + CANARY}
        elif case == "timeout":
            transport.failure = 2
        elif case == "encoding":
            transport.headers[2] = {"content-encoding": "gzip"}
        elif case in ("length", "length_mismatch"):
            transport.headers[2] = {"content-length": str(subject.MAX_BYTES + 1) if case == "length" else "1"}
        else:
            transport.stream[2] = [b" " * 32768] * 3 + [CANARY.encode()]
    elif case == "head_chunks":
        expected_calls, expected_stage = 1, "head"
        transport.stream[1] = [b" " * 32768] * 3 + [CANARY.encode()]
    elif case in ("cumulative_deadline", "stream_deadline"):
        now = [1000.0]  # Exactly representable origin, no cancellation flake.
        monkeypatch.setattr(time, "monotonic", lambda: now[0])
        transport.hook = lambda number: now.__setitem__(0, now[0] + (35 if case == "cumulative_deadline" else 61))
        expected_calls, expected_stage = (2, "admission") if case == "cumulative_deadline" else (1, "head")
    elif case == "cookie":
        transport.headers[1] = {"set-cookie": "private=" + CANARY + "; Path=/"}
        expected_calls, expected_stage = 1, "admission"
    elif case in ("wrong_path", "wrong_revision", "wrong_host", "wrong_method"):
        original = httpx.Client.send

        def altered(client, request, *args, **kwargs):
            if len(transport.calls) == 1:
                if case == "wrong_method":
                    request.method = "POST"
                else:
                    url = str(request.url)
                    url = {"wrong_path": url.replace("/admission.json", "/" + CANARY),
                           "wrong_revision": url.replace(PARENT, "f" * 40),
                           "wrong_host": url.replace("huggingface.co", "example.invalid")}[case]
                    request.url = httpx.URL(url)
            return original(client, request, *args, **kwargs)

        monkeypatch.setattr(httpx.Client, "send", altered)
        expected_calls, expected_stage = 1, "admission"
    elif case == "fourth_request":
        original = httpx.Client.get

        def extra(client, *args, **kwargs):
            response = original(client, *args, **kwargs)
            if len(transport.calls) == 3:
                original(client, args[0], **kwargs)  # Must refuse before a fourth transport call.
            return response

        monkeypatch.setattr(httpx.Client, "get", extra)
        expected_stage = "output_manifest"
    if case not in ("claim_digest", "claim_size"):
        manifest["claim_identity"] = subject._identity(encoded(admission))

    report = subject._read_controls(copy.deepcopy(IDENTITY))
    public = subject._canonical_json(report)
    subject.validate_report(json.loads(public), IDENTITY)
    captured = capsys.readouterr()
    assert all(secret not in public + captured.out + captured.err + caplog.text
               for secret in (TOKEN, CANARY, subject.TARGET, "https://", "result_path", "files", "step0_provenance"))
    assert report["source"] == IDENTITY["source"] and report["cell"] == subject.CELL
    assert report["historical"]["source"] == subject.HISTORICAL_SOURCE
    assert report["historical"]["request_sha256"] == subject.REQUEST_SHA256
    assert report["historical"]["job_id_verification"] == "not_serialized_in_control_records"
    assert all(report[key] is None for key in ("terminal_reason", "cleanup_confirmed", "host_reusable"))
    assert all(report[key] is False for key in ("retry_allowed", "completion_authority", "admission_authority",
                                               "execution_authority", "result_contents_verified"))
    assert report["read_outcome"] == ("verified" if good else "unknown")
    assert len(transport.calls) == expected_calls
    assert subject.MAX_HTTP_REQUESTS == 3 <= 4 and subject.SECONDS == 60 and subject.MAX_BYTES == 65536
    for request in transport.calls:
        assert all(0 < value <= 30 for value in request.extensions["timeout"].values())
    if case == "cumulative_deadline":
        assert transport.calls[1].extensions["timeout"]["read"] == 25
    if case in ("redirect", "encoding", "length"):
        assert not any(number == 2 for number, _ in transport.chunks)
    if case in ("chunks", "head_chunks"):
        assert sum(number == expected_calls for number, _ in transport.chunks) == 3
    if good:
        assert report["parent_commit"] == PARENT and report["verified_private"] is True
        assert report["failure_stage"] is None and report["control"]["claim_state"] == "permanently_consumed_not_completion"
        assert report["control"]["observed_run_number"] == 7  # Synthetic observation, not historical run-number evidence.
        assert report["records"]["admission"]["identity"] == subject._identity(encoded(admission))
        assert report["records"]["output_manifest"]["identity"] == subject._identity(encoded(manifest))
        assert report["control"]["declared_result_status"] == (
            None if case in ("uncertain", "uncertain_legacy", "no_receipt") else "error" if case == "returned_error" else "success")
        assert [request.url.path for request in transport.calls[1:]] == [
            f"/datasets/{subject.TARGET}/raw/{PARENT}/{path}" for path in subject.PATHS.values()]
    else:
        assert report["control"] == subject._blank_control() and report["failure_stage"] == expected_stage
        assert all(item["identity"] is None for item in report["records"].values())


@pytest.mark.parametrize("field,value", [
    ("source.sha", "0" * 40), ("source.tree", "0" * 40), ("request_identity.sha256", "0" * 64),
    ("ci.run_id", "37651514734"), ("ci.job", "other"), ("ci.attempt", 2), ("ci.attempt", True),
    ("ci.run_number", True), ("observation.study_id", "other"), ("observation.run_id", "gpt54_time_budget_v1_codex_r2"),
    ("observation.task_id", "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"), ("observation.condition", "sandbox_v2"),
    ("observation.repeat", 2), ("observation.repeat", True), ("observation.reviewed_source_sha", "0" * 40),
    ("observation.reviewed_source_tree", "0" * 40), ("observation.registration_sha256", "bad"),
    ("paths.input_source_sha", "0" * 40), ("storage.prefix", "other"), ("storage.branch", "other"),
    ("storage.repository_name_sha256", "0" * 64),
])
def test_task4_control_historical_binding(field, value, transport, capsys):
    first, second = field.split(".")
    transport.admission[first][second] = value
    # Even internally matching records cannot override the fixed independent binding.
    transport.manifest["claim_identity"] = subject._identity(encoded(transport.admission))
    transport.manifest["observation"] = copy.deepcopy(transport.admission["observation"])
    transport.manifest["request_identity"] = dict(transport.admission["request_identity"])
    transport.manifest["execution_receipt"]["returned"]["observation"] = copy.deepcopy(transport.admission["observation"])
    report = subject._read_controls(copy.deepcopy(IDENTITY))
    subject.validate_report(report, IDENTITY)
    assert report["read_outcome"] == "unknown" and report["control"] == subject._blank_control()
    assert report["failure_stage"] == "control_binding" and len(transport.calls) == 3
    captured = capsys.readouterr()
    assert CANARY not in subject._canonical_json(report) + captured.out + captured.err


@pytest.fixture
def source(tmp_path, monkeypatch):
    workspace, runner_temp = tmp_path / "checkout", tmp_path / "runner-temp"
    workspace.mkdir()
    runner_temp.mkdir()
    root = runner_temp / subject.SOURCE_BASENAME
    roles = subject.SOURCE_ROLES | {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "batch-runner/core").rglob("*.py")}
    for role in sorted(roles):
        destination = workspace / role
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / role, destination)

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "user.name=Synthetic Task4 fixture", "-c", "user.email=fixture@example.invalid",
             "-C", str(workspace), *args], stderr=subprocess.PIPE, text=True, timeout=10,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}).strip()

    git("init", "--quiet")
    git("add", ".")
    git("commit", "--quiet", "-m", "Synthetic Task4 reader source only")
    sha, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    git("switch", "--quiet", "--detach", sha)
    git("worktree", "add", "--quiet", "--detach", str(root), sha)
    environment = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": subject.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": subject.OWNER,
        "GITHUB_TRIGGERING_ACTOR": subject.OWNER, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": subject.JOB,
        "GITHUB_SHA": sha, "CONTROL_WORKFLOW_SHA": sha, "GITHUB_RUN_ID": IDENTITY["ci"]["run_id"],
        "GITHUB_WORKFLOW_REF": subject.REPOSITORY + "/" + subject.WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "GITHUB_WORKSPACE": str(workspace), "RUNNER_TEMP": str(runner_temp),
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return SimpleNamespace(root=root, sha=sha, tree=tree, destination=runner_temp / subject.BASENAME,
                           identity={"source": {"sha": sha, "tree": tree}, "ci": dict(IDENTITY["ci"])})


@pytest.mark.parametrize("outcome", ["verified", "unknown", "source_drift"])
def test_task4_control_source_cli(outcome, source, transport, monkeypatch, capsys):
    arguments = ["--runtime-root", str(source.root), "--reviewed-source-sha", source.sha,
                 "--reviewed-source-tree", source.tree]
    for key, value in (("GITHUB_ACTOR", "other"), ("GITHUB_TRIGGERING_ACTOR", "other"),
                       ("GITHUB_REF", "refs/heads/other"), ("GITHUB_RUN_ATTEMPT", "2"),
                       ("CONTROL_WORKFLOW_SHA", "0" * 40)):
        with monkeypatch.context() as changed:
            changed.setenv(key, value)
            assert subject.main(["validate-source", *arguments]) == 2
    assert subject.main(["validate-source", *arguments]) == 0 and transport.calls == []
    if outcome == "unknown":
        transport.status[2] = 404
    elif outcome == "source_drift":
        def drift(number):
            if number == 3:
                with (source.root / subject.HELPER).open("ab") as stream:
                    stream.write(b"\n# synthetic post-read source drift\n")
        transport.hook = drift
    result = subject.main(["inspect", *arguments])
    captured = capsys.readouterr()
    assert CANARY not in captured.out + captured.err and TOKEN not in captured.out + captured.err
    if outcome == "source_drift":
        assert result == 2 and not source.destination.exists()
        return
    assert result == (0 if outcome == "verified" else 2)
    data = source.destination.read_bytes()
    report = json.loads(data)
    assert data == subject._canonical_json(report).encode() and len(data) <= subject.REPORT_MAX_BYTES
    assert (source.destination.stat().st_mode & 0o777) == 0o600
    subject.validate_report(report, source.identity)
    monkeypatch.delenv("HF_TOKEN")  # Independent verification must not need/cache a storage token.
    assert subject.main(["verify-report", *arguments]) == 0
    calls = len(transport.calls)
    assert subject.main(["inspect", *arguments]) == 2  # No replacement or implicit reread.
    assert source.destination.read_bytes() == data and len(transport.calls) == calls
    report["retry_allowed"] = True
    source.destination.write_bytes(subject._canonical_json(report).encode())
    assert subject.main(["verify-report", *arguments]) == 2
    assert len(transport.calls) == calls


def test_task4_control_public_report(transport):
    good = subject._read_controls(copy.deepcopy(IDENTITY))
    assert good["read_outcome"] == "verified"
    mutations = [
        {"format": "gpt54-time-budget-first-codex-ci-completion-v1"}, {"purpose": "execute"},
        {"source": {"sha": "0" * 40, "tree": IDENTITY["source"]["tree"]}}, {"private_payload": CANARY},
        {"cell": {**subject.CELL, "repeat": True}}, {"prefix": "other"}, {"target_identity_sha256": "0" * 64},
        {"read_outcome": "unspent"}, {"read_outcome": "unknown"}, {"failure_stage": CANARY}, {"parent_commit": None},
        {"historical": {**good["historical"], "leader_job_id": "other"}},
        {"control": {**good["control"], "claim_state": "unspent"}},
        {"control": {**good["control"], "observed_run_number": True}},
        {"control": {**good["control"], "declared_result_status": CANARY}},
        {"records": {**good["records"], "admission": {"path": "other", "identity": good["records"]["admission"]["identity"]}}},
    ]
    mutations.extend({name: True} for name in ("terminal_reason", "cleanup_confirmed", "host_reusable", "retry_allowed",
                                             "completion_authority", "admission_authority", "execution_authority",
                                             "result_contents_verified"))
    for mutation in mutations:
        with pytest.raises((subject.ControlReadoutRefused, ValueError)):
            subject.validate_report({**copy.deepcopy(good), **mutation}, IDENTITY)


def test_task4_control_workflow():
    raw = (ROOT / subject.WORKFLOW).read_text()
    workflow = yaml.safe_load(raw)
    events = workflow.get("on", workflow.get(True))
    assert set(events) == {"workflow_dispatch"}
    assert set(events["workflow_dispatch"]["inputs"]) == {"reviewed_source_sha", "reviewed_source_tree"}
    assert workflow["permissions"] == {"contents": "read"} and set(workflow["jobs"]) == {subject.JOB}
    assert workflow["concurrency"] == {
        "group": "gpt54-time-budget-task4-control-readout", "cancel-in-progress": False}
    job = workflow["jobs"][subject.JOB]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 10
    assert job["if"] == "github.repository == 'hyeonsangjeon/gdpval-realworks' && github.ref == 'refs/heads/main'"
    assert "permissions" not in job and "HF_TOKEN" not in job["env"]
    assert job["env"]["HF_HUB_DISABLE_TELEMETRY"] == job["env"]["DO_NOT_TRACK"] == "1"
    steps = job["steps"]
    secrets = [step for step in steps if "secrets." in json.dumps(step)]
    read = next(step for step in steps if step.get("id") == "read")
    assert secrets == [read] and read["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert "timeout --signal=TERM --kill-after=5s 60s" in read["run"] and read["timeout-minutes"] == 2
    actions = {step["uses"].split("@")[0]: step for step in steps if "uses" in step}
    assert actions["actions/checkout"]["uses"] == "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
    assert actions["actions/checkout"]["with"] == {
        "ref": "${{ inputs.reviewed_source_sha }}", "fetch-depth": 1, "persist-credentials": False}
    assert actions["actions/setup-python"]["uses"] == "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
    assert actions["actions/setup-python"]["with"] == {"python-version": "3.10.12", "token": ""}
    source = next(step for step in steps if step.get("id") == "source")
    report = next(step for step in steps if step.get("id") == "report")
    assert steps.index(source) < steps.index(read) < steps.index(report)
    assert "validate-source" in source["run"] and "verify-report" in report["run"]
    assert "always()" in report["if"] and "steps.source.outputs.validated == 'true'" in report["if"]
    artifact = actions["actions/upload-artifact"]
    assert artifact["uses"] == "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    assert artifact["with"]["retention-days"] == 7 and artifact["with"]["if-no-files-found"] == "error"
    assert artifact["with"]["path"] == "${{ runner.temp }}/" + subject.BASENAME
    assert artifact["if"] == "always() && steps.report.outputs.validated == 'true'"
    assert all(term not in raw for term in ("id-token:", "azure/login", "prepare-and-claim", "execute", "create_commit",
                                           "continue-on-error", "schedule:", "workflow_run:"))
    guard = steps[0]["run"]
    environment = {
        "PATH": "/usr/bin:/bin", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": subject.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_ACTOR": subject.OWNER, "GITHUB_TRIGGERING_ACTOR": subject.OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "REVIEWED_SOURCE_SHA": "a" * 40, "REVIEWED_SOURCE_TREE": "b" * 40,
        "GITHUB_SHA": "a" * 40, "CONTROL_WORKFLOW_SHA": "a" * 40,
        "GITHUB_WORKFLOW_REF": subject.REPOSITORY + "/" + subject.WORKFLOW + "@refs/heads/main",
    }
    for changes in ({}, {"GITHUB_ACTOR": "other"}, {"GITHUB_REF": "refs/heads/other"}, {"GITHUB_RUN_ATTEMPT": "2"},
                    {"GITHUB_SHA": "c" * 40}, {"CONTROL_WORKFLOW_SHA": "c" * 40}):
        result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", guard], env={**environment, **changes},
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        assert (result.returncode == 0) is (not changes)
    # Existing scopes, pinned shared helper and old envelopes remain separate.
    assert subject.metadata.DEFAULT_SCOPE == "generation_task1" and subject.metadata.NATIVE_SCOPE == "native_task3_grade"
    assert hashlib.sha256((ROOT / "batch-runner/gpt54_disposable_checkout.py").read_bytes()).hexdigest() == (
        "77d6d1957f123b7f32d710be7ffddbd99f6043e00b0313bc7b1cc9802975fa62")
