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
                            paths=[], failure=None, hook=None)

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
            return httpx.Response(status, headers={"content-type": "application/json", "location": "/unrelated"},
                                  stream=httpx.ByteStream(json.dumps(payload).encode()), request=request)

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
    assert set(inputs) == {"reviewed_source_sha", "reviewed_source_tree"}
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"metadata"}
    job = workflow["jobs"]["metadata"]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 10
    assert "permissions" not in job and "HF_TOKEN" not in job["env"]
    assert job["env"]["HF_HUB_DISABLE_TELEMETRY"] == job["env"]["DO_NOT_TRACK"] == "1"
    steps = job["steps"]
    secrets = [step for step in steps if "secrets." in json.dumps(step)]
    assert len(secrets) == 1 and secrets[0]["id"] == "metadata"
    assert secrets[0]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    guard = steps[0]["run"]
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
    artifact = steps[-1]
    assert artifact["with"]["path"] == "${{ runner.temp }}/" + subject.BASENAME
    assert artifact["if"] == "always() && steps.envelope.outputs.validated == 'true'"
    assert all(term not in raw for term in ("id-token:", "azure/login", "prepare-and-claim", "step2_run_inference",
                                           "gpt54_time_budget_v2_observation", "create_commit", "continue-on-error"))
