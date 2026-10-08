"""Synthetic Actions/Git identities and HTTP metadata, never a live HF call."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
from huggingface_hub import HfApi, constants
import pytest
import yaml

import gpt54_time_budget_storage_metadata as subject

ROOT = Path(__file__).resolve().parents[2]
PARENT = "8" * 40
TOKEN = "hf_SYNTHETIC_METADATA_ONLY_NOT_A_CREDENTIAL"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    attempted = []
    ordinary_sleep = time.sleep

    def forbidden(*args, **kwargs):
        attempted.append("forbidden effect")
        raise AssertionError("metadata test crossed its offline boundary")

    for obj, names in (
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (HfApi, ("create_repo", "create_commit", "upload_file", "delete_file")),
    ):
        for name in names:
            monkeypatch.setattr(obj, name, forbidden)
    monkeypatch.setenv("HF_HUB_DISABLE_TELEMETRY", "1")
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)

    def no_transport_backoff(seconds):
        # subprocess.communicate(timeout=...) may sleep while reaping local
        # Git. Only the HF session's online scope must not back off or retry.
        if not constants.HF_HUB_OFFLINE:
            forbidden()
        ordinary_sleep(seconds)

    monkeypatch.setattr(time, "sleep", no_transport_backoff)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    yield
    assert attempted == []  # A caught network exception is still a test failure.


@pytest.fixture
def source(tmp_path, monkeypatch):
    workspace, runner_temp = tmp_path / "checkout", tmp_path / "runner-temp"
    workspace.mkdir()
    runner_temp.mkdir()
    root = runner_temp / subject.SOURCE_BASENAME
    roles = subject.SOURCE_ROLES | {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "batch-runner/core").rglob("*.py")
    }
    for role in sorted(roles):
        destination = workspace / role
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / role, destination)

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "user.name=Synthetic metadata fixture", "-c", "user.email=fixture@example.invalid",
             "-C", str(workspace), *args], stderr=subprocess.PIPE, text=True, timeout=10).strip()

    git("init", "--quiet")
    git("add", ".")
    git("commit", "--quiet", "-m", "Explicit synthetic metadata source")
    sha, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    git("switch", "--quiet", "--detach", sha)
    git("worktree", "add", "--quiet", "--detach", str(root), sha)
    environment = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": subject.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": subject.OWNER,
        "GITHUB_TRIGGERING_ACTOR": subject.OWNER, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": subject.JOB,
        "GITHUB_SHA": sha, "METADATA_WORKFLOW_SHA": sha, "GITHUB_RUN_ID": "123456789",
        "GITHUB_WORKFLOW_REF": subject.REPOSITORY + "/" + subject.WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
        "GITHUB_WORKSPACE": str(workspace), "RUNNER_TEMP": str(runner_temp),
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return SimpleNamespace(root=root, sha=sha, tree=tree, destination=runner_temp / subject.BASENAME,
                           identity={"source": {"sha": sha, "tree": tree},
                                     "ci": {"run_id": "123456789", "job": "metadata", "attempt": 1}})


@pytest.fixture
def transport(monkeypatch):
    state = SimpleNamespace(calls=[], head={"id": subject.TARGET, "private": True, "sha": PARENT},
                            paths=[], failure=None, hook=None, raw={}, headers={})

    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs == {"retries": 0, "trust_env": False}

        def handle_request(self, request):
            state.calls.append(request)
            assert "HF_TOKEN" not in os.environ
            assert request.headers["authorization"] == "Bearer " + TOKEN
            assert len(state.calls) <= 2
            number = len(state.calls)
            if state.hook:
                state.hook(number)
            status, payload = 200, state.head if number == 1 else state.paths
            if state.failure and state.failure[0] == number:
                failure = state.failure[1]
                if failure == "timeout":
                    raise httpx.ReadTimeout("PRIVATE_EXCEPTION_" + TOKEN, request=request)
                status, payload = failure, {"error": "PRIVATE_BODY_" + TOKEN}
            return httpx.Response(status, headers={"content-type": "application/json", "location": "/unrelated",
                                                   **state.headers.get(number, {})},
                                  stream=httpx.ByteStream(state.raw.get(number, json.dumps(payload).encode())),
                                  request=request)

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    return state


def invoke(source, operation="inspect"):
    return subject.main([operation, "--reviewed-source-sha", source.sha,
                         "--reviewed-source-tree", source.tree, "--runtime-root", str(source.root)])


def envelope(source):
    value = json.loads(source.destination.read_bytes())
    subject.validate_envelope(value, source.identity)
    return value


@pytest.mark.parametrize("outcome", ["absent", "present"])
def test_time_budget_storage_metadata_roundtrip(source, transport, capsys, outcome):
    if outcome == "present":
        transport.paths = [{"type": "directory", "path": subject.PREFIX, "oid": "9" * 40}]
    assert invoke(source, "validate-source") == 0
    assert transport.calls == []
    assert invoke(source) == 0
    value = envelope(source)
    assert value == {"format": subject.FORMAT, **source.identity, "timestamp_utc": value["timestamp_utc"],
                     "target_identity_sha256": subject.TARGET_SHA256, "verified_private": True,
                     "parent_commit": PARENT, "prefix": subject.PREFIX, "prefix_outcome": outcome}
    assert invoke(source, "verify-envelope") == 0
    assert len(transport.calls) == 2
    first, second = transport.calls
    assert first.method == "GET" and first.url.path == f"/api/datasets/{subject.TARGET}/revision/main"
    assert parse_qs(first.url.query.decode()) == {"expand": ["private", "sha"]}
    assert second.method == "POST" and second.url.path == f"/api/datasets/{subject.TARGET}/paths-info/{PARENT}"
    assert parse_qs(second.content.decode()) == {"paths": [subject.PREFIX], "expand": ["false"]}
    assert all(0 < request.extensions["timeout"]["read"] <= 30 for request in transport.calls)
    assert TOKEN not in capsys.readouterr().out
    original = source.destination.read_bytes()
    assert invoke(source) == 2  # Existing local envelope is not overwritten.
    assert source.destination.read_bytes() == original and len(transport.calls) == 2


@pytest.mark.parametrize("case", ["actor", "ref", "source", "tree", "attempt", "blob"])
def test_time_budget_storage_metadata_source_refusal(source, transport, monkeypatch, case):
    if case in ("actor", "ref", "attempt"):
        name = {"actor": "GITHUB_ACTOR", "ref": "GITHUB_REF", "attempt": "GITHUB_RUN_ATTEMPT"}[case]
        monkeypatch.setenv(name, {"actor": "other-owner", "ref": "refs/heads/other", "attempt": "2"}[case])
    elif case == "source":
        monkeypatch.setenv("METADATA_WORKFLOW_SHA", "0" * 40)
    elif case == "tree":
        source.tree = "0" * 40
    else:
        with (source.root / subject.HELPER).open("a") as stream:
            stream.write("\n# Unreviewed source bytes\n")
    assert invoke(source) == 2
    assert transport.calls == [] and not source.destination.exists()


@pytest.mark.parametrize("case", ["missing_credential", "nonprivate", "wrong_target", "bad_parent"])
def test_time_budget_storage_metadata_target_refusal(source, transport, monkeypatch, case):
    if case == "missing_credential":
        monkeypatch.delenv("HF_TOKEN")
    else:
        name, value = {"nonprivate": ("private", False), "wrong_target": ("id", "other/private"),
                       "bad_parent": ("sha", "main")}[case]
        transport.head[name] = value
    assert invoke(source) == 2
    value = envelope(source)
    assert value["prefix_outcome"] == "refused" and value["verified_private"] is None
    assert value["parent_commit"] is None
    assert len(transport.calls) == (0 if case == "missing_credential" else 1)
    assert invoke(source, "verify-envelope") == 0  # Safe refusal evidence may be retained.


@pytest.mark.parametrize("operation,failure", [(1, 401), (1, 403), (1, 404), (2, 404), (2, "timeout"), (2, 302)],
                         ids=["head_401", "head_403", "head_404", "prefix_404", "prefix_timeout", "prefix_redirect"])
def test_time_budget_storage_metadata_transport_refusal(source, transport, capsys, operation, failure):
    transport.failure = (operation, failure)
    assert invoke(source) == 2
    value = envelope(source)
    assert value["prefix_outcome"] == "refused"
    assert value["verified_private"] is (True if operation == 2 else None)
    assert value["parent_commit"] == (PARENT if operation == 2 else None)
    assert len(transport.calls) == operation
    public = source.destination.read_text() + capsys.readouterr().out
    assert TOKEN not in public and "PRIVATE_" not in public and "unrelated" not in public


@pytest.mark.parametrize("case", ["not_list", "wrong_path", "duplicate"])
def test_time_budget_storage_metadata_malformed_prefix(source, transport, case):
    row = {"type": "directory", "path": subject.PREFIX, "oid": "9" * 40}
    transport.paths = {"not_list": {}, "wrong_path": [{**row, "path": "unrelated"}],
                       "duplicate": [row, row]}[case]
    assert invoke(source) == 2
    assert envelope(source)["prefix_outcome"] == "refused" and len(transport.calls) == 2


def test_time_budget_storage_metadata_cumulative_bound(source, transport, monkeypatch):
    now = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    transport.hook = lambda number: now.__setitem__(0, now[0] + 35)
    assert invoke(source) == 2
    assert subject.SECONDS == 60 and len(transport.calls) == 2
    assert transport.calls[1].extensions["timeout"]["read"] == 25
    assert envelope(source)["prefix_outcome"] == "refused"


def test_time_budget_storage_metadata_final_source_reread(source, transport):
    def change_source(number):
        if number == 2:
            with (source.root / subject.WORKFLOW).open("a") as stream:
                stream.write("\n# Replaced during metadata operation\n")

    transport.hook = change_source
    assert invoke(source) == 2
    assert len(transport.calls) == 2 and not source.destination.exists()


def test_time_budget_storage_metadata_envelope_allowlist(source):
    good = {"format": subject.FORMAT, **source.identity, "timestamp_utc": "2026-10-06T00:00:00Z",
            "target_identity_sha256": subject.TARGET_SHA256, "verified_private": None,
            "parent_commit": None, "prefix": subject.PREFIX, "prefix_outcome": "refused"}
    subject.validate_envelope(good, source.identity)
    for mutation in ({"raw_exception": TOKEN}, {"prefix_outcome": "absent"}, {"verified_private": 1},
                     {"source": {"sha": "0" * 40, "tree": source.tree}}, {"prefix": "unrelated"}):
        with pytest.raises((subject.MetadataRefused, ValueError)):
            subject.validate_envelope({**copy.deepcopy(good), **mutation}, source.identity)


def test_time_budget_storage_metadata_workflow_contract():
    raw = (ROOT / subject.WORKFLOW).read_text()
    workflow = yaml.safe_load(raw)
    assert set(workflow.get("on", workflow.get(True))) == {"workflow_dispatch"}
    inputs = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"reviewed_source_sha", "reviewed_source_tree", "scope"}
    assert inputs["scope"] == {
        "description": "Fixed metadata scope only; no contents, admission or retry authority",
        "required": True, "type": "choice", "default": "generation_task1",
        "options": ["generation_task1", "native_task3_grade"],
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"metadata"}
    job = workflow["jobs"]["metadata"]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 10
    assert "permissions" not in job and "HF_TOKEN" not in job["env"]
    assert job["env"]["HF_HUB_DISABLE_TELEMETRY"] == job["env"]["DO_NOT_TRACK"] == "1"
    assert job["env"]["METADATA_SCOPE"] == "${{ inputs.scope }}"
    steps = job["steps"]
    secrets = [step for step in steps if "secrets." in json.dumps(step)]
    assert len(secrets) == 1 and secrets[0]["id"] == "metadata"
    assert secrets[0]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    guard = steps[0]["run"]
    assert '[[ "$METADATA_SCOPE" == generation_task1 || "$METADATA_SCOPE" == native_task3_grade ]]' in guard
    for literal in ("GITHUB_EVENT_NAME", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_ACTOR",
                    "GITHUB_TRIGGERING_ACTOR", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "METADATA_WORKFLOW_SHA",
                    "GITHUB_WORKFLOW_REF", "REVIEWED_SOURCE_TREE"):
        assert literal in guard
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    assert checkout["with"]["ref"] == "${{ inputs.reviewed_source_sha }}"
    source = next(step for step in steps if step.get("id") == "source")
    assert steps.index(source) < steps.index(secrets[0]) and "validate-source" in source["run"]
    linked = next(step for step in steps if "git worktree add --detach" in step.get("run", ""))
    assert steps.index(linked) < steps.index(source)
    assert '--runtime-root "$RUNNER_TEMP/time-budget-metadata-source"' in source["run"]
    assert "timeout --signal=TERM --kill-after=5s 60s" in secrets[0]["run"]
    verify = next(step for step in steps if step.get("id") == "envelope")
    assert "always()" in verify["if"] and "verify-envelope" in verify["run"]
    assert all('--scope "$METADATA_SCOPE"' in step["run"] for step in (source, secrets[0], verify))
    artifact = steps[-1]
    assert artifact["with"]["path"] == "${{ runner.temp }}/" + subject.BASENAME
    assert artifact["if"] == "always() && steps.envelope.outputs.validated == 'true'"
    assert all(term not in raw for term in ("id-token:", "azure/login", "prepare-and-claim", "step2_run_inference",
                                           "gpt54_time_budget_v2_observation", "create_commit", "continue-on-error"))


@pytest.mark.parametrize("case", [
    "present", "absent", "admission_only", "output_only", "legacy_default", "legacy_explicit", "unknown_scope",
    "nonprivate", "wrong_target", "bad_parent", "head_404", "paths_404", "redirect", "timeout",
    "malformed", "duplicate_path", "duplicate_key", "head_duplicate_key", "unrelated_path", "directory",
    "oid", "size", "oversized", "head_oversized", "encoding", "cumulative_bound", "revision_drift",
    "path_drift", "third_operation", "source_drift",
])
def test_native_task3_grade_metadata_scope(source, transport, monkeypatch, capsys, case):
    """Real source/CLI/SDK/bounds; synthetic Actions identities and metadata, no contents."""
    canary = "hf_SECRET_CANARY_private_exception_payload_not_a_credential"
    prefix = ("time-budget-grading/gpt54_sandboxv2_codex_time_budget_v1/gpt54_time_budget_v1_codex_r1/"
              "2ea2e5b5-257f-42e6-a7dc-93763f28b19d/882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2")
    paths = [prefix + "/admission.json", prefix + "/output-manifest.json"]
    assert list(subject.NATIVE_PATHS.values()) == paths and subject.SECONDS == 60
    rows = [{"type": "file", "path": path, "oid": digit * 40, "size": size, "private_extra": canary}
            for path, digit, size in zip(paths, ("9", "a"), (123, 456))]
    transport.head["private_extra"] = canary
    transport.paths = copy.deepcopy(rows)
    scope = subject.DEFAULT_SCOPE if case.startswith("legacy_") else subject.NATIVE_SCOPE
    selected = [] if case == "legacy_default" else ["--scope", scope]
    successful = case in {"present", "absent", "admission_only", "output_only", "legacy_default", "legacy_explicit"}
    expected_calls = 2
    if case == "absent":
        transport.paths = []
    elif case == "admission_only":
        transport.paths = rows[:1]
    elif case == "output_only":
        transport.paths = rows[1:]
    elif case.startswith("legacy_"):
        transport.paths = [{"type": "directory", "path": subject.PREFIX, "oid": "b" * 40}]
    elif case == "unknown_scope":
        selected, expected_calls = ["--scope", canary], 0
    elif case in ("nonprivate", "wrong_target", "bad_parent"):
        key, value = {"nonprivate": ("private", False), "wrong_target": ("id", canary),
                      "bad_parent": ("sha", "main")}[case]
        transport.head[key], expected_calls = value, 1
    elif case in ("head_404", "paths_404", "redirect", "timeout"):
        transport.failure = {"head_404": (1, 404), "paths_404": (2, 404),
                             "redirect": (2, 302), "timeout": (2, "timeout")}[case]
        expected_calls = transport.failure[0]
    elif case == "malformed":
        transport.paths = {"error": canary}
    elif case == "duplicate_path":
        transport.paths = [rows[0], rows[0]]
    elif case in ("duplicate_key", "head_duplicate_key"):
        number = 1 if case == "head_duplicate_key" else 2
        raw = json.dumps(transport.head if number == 1 else rows)
        key = "sha" if number == 1 else "oid"
        transport.raw[number] = raw.replace('"' + key + '":', '"' + key + '": "' + canary + '", "' + key + '":', 1).encode()
        expected_calls = number
    elif case in ("unrelated_path", "directory", "oid", "size"):
        key, value = {"unrelated_path": ("path", prefix + "/" + canary), "directory": ("type", "directory"),
                      "oid": ("oid", canary), "size": ("size", True)}[case]
        transport.paths[0][key] = value
    elif case in ("oversized", "head_oversized"):
        number = 1 if case == "head_oversized" else 2
        transport.raw[number] = b" " * (64 * 1024) + json.dumps(transport.head if number == 1 else []).encode()
        expected_calls = number
    elif case == "encoding":
        transport.headers[2] = {"content-encoding": "gzip"}
    elif case == "cumulative_bound":
        now = [time.monotonic()]
        monkeypatch.setattr(time, "monotonic", lambda: now[0])
        transport.hook = lambda number: now.__setitem__(0, now[0] + 35)
    elif case in ("revision_drift", "path_drift", "third_operation"):
        original = HfApi.get_paths_info

        def unexpected_operation(self, *args, **kwargs):
            if case == "revision_drift":
                kwargs["revision"] = "c" * 40
            elif case == "path_drift":
                kwargs["paths"] = [*paths, prefix + "/" + canary]
            result = original(self, *args, **kwargs)
            if case == "third_operation":
                from huggingface_hub.utils import _http
                _http.get_session().get("https://huggingface.co/api/datasets/" + subject.TARGET + "/revision/main",
                                        headers={"authorization": "Bearer " + TOKEN})
            return result

        monkeypatch.setattr(HfApi, "get_paths_info", unexpected_operation)
        expected_calls = 2 if case == "third_operation" else 1
    elif case == "source_drift":
        def changed_source(number):
            if number == 2:
                with (source.root / subject.WORKFLOW).open("a") as stream:
                    stream.write("\n# Synthetic unreviewed source drift\n")
        transport.hook = changed_source

    def run(operation):
        return subject.main([operation, "--reviewed-source-sha", source.sha,
                             "--reviewed-source-tree", source.tree, "--runtime-root", str(source.root), *selected])

    assert run("validate-source") == (2 if case == "unknown_scope" else 0)
    assert transport.calls == []
    assert run("inspect") == (0 if successful else 2)
    assert len(transport.calls) == expected_calls
    if case in ("unknown_scope", "source_drift"):
        assert not source.destination.exists()
    else:
        raw = source.destination.read_bytes()
        value = json.loads(raw)
        assert len(raw) <= 4096
        subject.validate_envelope(value, source.identity, scope=scope)
        assert value["source"] == source.identity["source"] and value["ci"] == source.identity["ci"]
        assert value["target_identity_sha256"] == subject.TARGET_SHA256
        assert run("verify-envelope") == 0 and len(transport.calls) == expected_calls
        if scope == subject.DEFAULT_SCOPE:
            assert value == {"format": subject.FORMAT, **source.identity, "timestamp_utc": value["timestamp_utc"],
                             "target_identity_sha256": subject.TARGET_SHA256, "verified_private": True,
                             "parent_commit": PARENT, "prefix": subject.PREFIX, "prefix_outcome": "present"}
        else:
            assert value["scope"] == scope and value["prefix"] == prefix
            assert value["cell"] == subject.NATIVE_CELL and value["frozen_grader"] == subject.NATIVE_FROZEN
            assert value["contents_verified"] is False and value["retry_allowed"] is False
            assert value["metadata_outcome"] == ("verified" if successful else "refused")
            for name, path in subject.NATIVE_PATHS.items():
                row = next((row for row in transport.paths if type(row) is dict and row.get("path") == path), None)
                assert value["objects"][name] == {
                    "presence": "present" if successful and row else "absent" if successful else "unknown",
                    "metadata_oid": row["oid"] if successful and row else None,
                    "metadata_size_bytes": row["size"] if successful and row else None,
                }
            if successful:
                assert value["verified_private"] is True and value["parent_commit"] == PARENT
            if case == "present":
                with pytest.raises(subject.MetadataRefused):
                    subject.validate_envelope(value, source.identity)  # No scope autodetection from downloaded JSON.
                mutations = [
                    {"scope": subject.DEFAULT_SCOPE}, {"prefix": subject.PREFIX},
                    {"cell": {**value["cell"], "task_id": "02aa1805-c658-4069-8a6a-02dec146063a"}},
                    {"cell": {**value["cell"], "repeat": True}},
                    {"frozen_grader": {**value["frozen_grader"], "sha": "d" * 40}},
                    {"source": {**value["source"], "tree": "d" * 40}},
                    {"ci": {**value["ci"], "run_id": "2"}}, {"target_identity_sha256": "d" * 64},
                    {"contents_verified": True}, {"retry_allowed": True}, {"parent_commit": None},
                    {"metadata_outcome": "absent"}, {"objects": {}}, {"raw_exception": canary},
                ]
                for mutation in mutations:
                    with pytest.raises((subject.MetadataRefused, ValueError)):
                        subject.validate_envelope({**copy.deepcopy(value), **mutation}, source.identity, scope=scope)
                for mutation in ({"presence": "present", "metadata_oid": None}, {"metadata_size_bytes": True},
                                 {"presence": "unknown"}, {"private_body": canary}):
                    bad = copy.deepcopy(value)
                    bad["objects"]["admission"].update(mutation)
                    with pytest.raises(subject.MetadataRefused):
                        subject.validate_envelope(bad, source.identity, scope=scope)
        assert run("inspect") == 2  # No clobber, extra HTTP or implicit retry.
        assert source.destination.read_bytes() == raw and len(transport.calls) == expected_calls
    if transport.calls:
        first = transport.calls[0]
        assert first.method == "GET" and first.url.path == f"/api/datasets/{subject.TARGET}/revision/main"
        assert parse_qs(first.url.query.decode()) == {"expand": ["private", "sha"]} and not first.content
        if len(transport.calls) == 2:
            second = transport.calls[1]
            assert second.method == "POST" and second.url.path == f"/api/datasets/{subject.TARGET}/paths-info/{PARENT}"
            assert parse_qs(second.content.decode()) == {"paths": [subject.PREFIX] if scope == subject.DEFAULT_SCOPE else paths,
                                                        "expand": ["false"]}
        if scope == subject.NATIVE_SCOPE:
            assert all(call.headers["accept-encoding"] == "identity" for call in transport.calls)
        assert all(0 < call.extensions["timeout"]["read"] <= 30 for call in transport.calls)
        if case == "cumulative_bound":
            assert transport.calls[1].extensions["timeout"]["read"] == 25
    captured = capsys.readouterr()
    public = captured.out + captured.err + (source.destination.read_text() if source.destination.exists() else "")
    assert all(secret not in public for secret in (TOKEN, canary, "PRIVATE_", "unrelated", "https://"))
