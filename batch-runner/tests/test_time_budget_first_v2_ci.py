"""New Actions route only: real validators, synthetic inputs/HTTP/model/kernel.

No private original, live receipt, provider, HF or platform probe is accessed.
The temporary Git declarations name synthetic input bytes, not paid evidence.
"""

import io
import json
import os
import socket
import subprocess
import time
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest
import yaml
from huggingface_hub import CommitOperationAdd, RepoFile, RepoFolder

import gpt54_time_budget_comparison as registration
import gpt54_time_budget_v2_ci as ci
import gpt54_time_budget_v2_observation as entry
from core import azure_ai_clients
from core.agentic_v2_preregistration import seal
from core.time_budget_observation_deadline import ObservationIdentity
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_time_budget_comparison import (
    dual_roots, handoff_source_seed, handoff_sources, observation_kernel,
)
from .test_time_budget_first_v2_observation import _transport

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
TOKEN = "explicitly-synthetic-storage-token"


class PrivateStore:
    """Transport seam with real immutable byte objects, CAS and first writers."""

    def __init__(self):
        self.head = "1" * 40
        self.trees, self.writers = {self.head: {}}, {self.head: {}}
        self.calls, self.commits = [], []
        self.race = False
        self.lost = None

    def record(self, operation, kwargs):
        assert kwargs["repo_id"] == ci.TARGET and kwargs["repo_type"] == "dataset" and kwargs["token"] == TOKEN
        assert not any(os.environ.get(key) for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"))
        self.calls.append(operation)

    def repo_info(self, **kwargs):
        self.record("metadata", kwargs)
        revision = self.head if kwargs["revision"] == ci.BRANCH else kwargs["revision"]
        assert revision in self.trees and 0 < kwargs["timeout"] <= 30
        return SimpleNamespace(id=ci.TARGET, private=True, sha=revision)

    def get_paths_info(self, **kwargs):
        self.record("objects", kwargs)
        tree, found = self.trees[kwargs["revision"]], []
        for name in kwargs["paths"]:
            if name in tree:
                item = object.__new__(RepoFile)
                item.path, item.size, item.blob_id = name, len(tree[name]), ci._object(name, tree[name])["git_blob_sha1"]
                item.lfs = None
                item.last_commit = SimpleNamespace(oid=self.writers[kwargs["revision"]][name])
                found.append(item)
            elif any(role.startswith(name + "/") for role in tree):
                item = object.__new__(RepoFolder)
                item.path = name
                found.append(item)
        return found

    def hf_hub_download(self, **kwargs):
        self.record("immutable_control_readback", kwargs)
        assert kwargs["filename"] in {ci.CLAIM, ci.MANIFEST}
        assert kwargs["force_download"] is True and kwargs["local_files_only"] is False
        target = Path(kwargs["cache_dir"]) / "control.json"
        target.write_bytes(self.trees[kwargs["revision"]][kwargs["filename"]])
        return str(target)

    def create_commit(self, **kwargs):
        self.record("cas", kwargs)
        assert kwargs["revision"] == ci.BRANCH and kwargs["num_threads"] == 1
        assert kwargs["run_as_future"] is False and kwargs["create_pr"] is False
        files = {}
        for operation in kwargs["operations"]:
            assert type(operation) is CommitOperationAdd
            assert isinstance(operation.path_or_fileobj, io.BufferedIOBase)
            files[operation.path_in_repo] = operation.path_or_fileobj.read()
        kind = "claim" if set(files) == {ci.CLAIM} else "output"
        self.commits.append(kind)
        if self.race or kwargs["parent_commit"] != self.head:
            raise ci.storage.OutputPublicationRefused("hf_http_failed", 409)
        assert not set(files).intersection(self.trees[self.head])
        revision = f"{len(self.trees) + 1:040x}"
        self.trees[revision] = {**self.trees[self.head], **files}
        self.writers[revision] = {**self.writers[self.head], **{name: revision for name in files}}
        self.head = revision
        if self.lost == kind:
            raise ci.storage.OutputPublicationRefused("hf_transport_failed")
        return SimpleNamespace(oid=revision)


@pytest.fixture(autouse=True)
def offline(monkeypatch, handoff_sources, dual_roots, observation_kernel):
    import huggingface_hub
    from huggingface_hub import constants
    import step8_grade

    # Match the workflow's HF_HUB_DISABLE_TELEMETRY=1 / DO_NOT_TRACK=1.
    # The SDK caches this setting at import; its header builder otherwise
    # fetches an agent registry before our ordinary original-file HTTP seam.
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("first V2 Actions proof attempted an external effect")

    for owner, names in ((socket.socket, ("connect", "connect_ex")), (socket, ("create_connection",)),
                         (subprocess, ("Popen", "run", "check_output", "check_call")), (os, ("system",)),
                         (huggingface_hub, ("HfApi", "snapshot_download", "hf_hub_download")),
                         (azure_ai_clients, ("OpenAI", "AzureOpenAI", "DefaultAzureCredential"))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    monkeypatch.setattr(step8_grade.Grader, "__init__", forbidden)

    def git(command, **kwargs):
        assert command[:2] == ["/usr/bin/git", "--no-replace-objects"]
        index = command.index("-C")
        assert Path(command[index + 1]) in {handoff_sources.runtime, handoff_sources.frozen,
                                           dual_roots["runtime"], dual_roots["frozen"], dual_roots["substitute"]}
        assert command[index + 2] in {"config", "rev-parse", "ls-tree", "cat-file"}
        assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        with monkeypatch.context() as actual:
            actual.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", git)
    for key in tuple(os.environ):
        if key.startswith(("AZURE_", "FOUNDRY_", "GITHUB_", "ACTIONS_", "HF_", "OPENAI_", "RUNNER_")):
            monkeypatch.delenv(key)
    # Ordinary OS metadata seam, not a successful host-validator replacement.
    original_open, original_stat = Path.open, Path.stat

    def opened(path, *args, **kwargs):
        if str(path) == "/proc/sys/kernel/random/boot_id":
            return io.StringIO("00000000-1111-4222-8333-444444444444\n")
        return original_open(path, *args, **kwargs)

    def stat(path, *args, **kwargs):
        if str(path) == "/proc/self/ns/pid":
            return SimpleNamespace(st_dev=55, st_ino=77)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", opened)
    monkeypatch.setattr(Path, "stat", stat)
    yield
    assert forbidden_calls == []


@pytest.fixture
def case(handoff_sources, tmp_path, monkeypatch):
    seed = handoff_sources
    root = tmp_path / "time-budget-first-v2"
    request = {
        "format": ci.REQUEST_VERSION, "purpose": "execute_and_privately_retain_first_v2_observation",
        "source": {"sha": seed.runtime_sha, "tree": seed.runtime_tree},
        "frozen_source": {"sha": seed.frozen_sha, "tree": seed.frozen_tree},
        "input_registration": {"source_sha": seed.frozen_sha, "source_tree": seed.frozen_tree,
            "path": registration.SOURCE_PROFILE, "sha256": seed.profile_sha},
        "cell": dict(ci.CELL), "registration_sha256": seal(seed.plan), "dataset_sha256": seal(seed.plan["shared"]["dataset"]),
        "ci": {"repository": ci.REPOSITORY, "workflow": ci.WORKFLOW, "ref": "refs/heads/main", "actor": ci.OWNER,
               "job": ci.JOB, "attempt": 1, "run_number": 7, "runner": "ubuntu-22.04", "runner_os": "Linux", "runner_arch": "X64"},
        "paths": {"runtime_root": str(seed.runtime), "frozen_root": str(seed.frozen), "state_root": str(root)},
        "storage": {"repository_name_sha256": ci.TARGET_SHA256, "branch": ci.BRANCH, "prefix": ci.PREFIX, "expected_parent": "1" * 40},
        "not_before_unix": int(time.time()) - 10, "expires_unix": int(time.time()) + 1800,
    }
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": ci.OWNER, "GITHUB_TRIGGERING_ACTOR": ci.OWNER,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": "7", "GITHUB_JOB": ci.JOB,
        "GITHUB_SHA": seed.runtime_sha, "TIME_BUDGET_WORKFLOW_SHA": seed.runtime_sha,
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "RUNNER_ENVIRONMENT": "github-hosted", "ImageOS": "ubuntu22",
        "GITHUB_RUN_ID": "7001", "RUNNER_NAME": "explicitly-synthetic-Actions-host",
        "GITHUB_WORKSPACE": str(seed.runtime), "RUNNER_TEMP": str(tmp_path),
        "AZURE_AI_ROUTE_PROFILE": "direct-v1",
        "FOUNDRY_PROJECT_ENDPOINT": "https://hjeon-fdpo-foundry-eus2.services.ai.azure.com/api/projects/gdpval-realworks",
        "HF_TOKEN": TOKEN,
    }.items():
        monkeypatch.setenv(key, value)
    value = SimpleNamespace(request=request, root=root, seed=seed, api=PrivateStore(), downloads=[], corrupt=False)
    value.args = {"request_json": ci._bytes(request).decode(), "expected_request_sha256": _identity(ci._bytes(request))["sha256"],
                  "reviewed_source_sha": seed.runtime_sha, "reviewed_source_tree": seed.runtime_tree,
                  "runtime_root": seed.runtime, "frozen_root": seed.frozen, "state_root": root}
    originals = {"data/train-00000-of-00001.parquet": seed.parquet.read_bytes(),
                 **{name: (seed.references / name).read_bytes() for name in seed.records}}

    @contextmanager
    def http(method, url, **kwargs):
        assert method == "GET" and kwargs["headers"]["authorization"] == "Bearer " + TOKEN
        assert kwargs["max_retries"] == 0 and kwargs["follow_redirects"] is False
        assert urlsplit(url).netloc == "huggingface.co"
        prefix = "/datasets/openai/gdpval/resolve/" + seed.plan["shared"]["dataset"]["revision"] + "/"
        path = unquote(urlsplit(url).path)
        assert path.startswith(prefix)
        member = path[len(prefix):]
        assert member in originals and "step0" not in member
        value.downloads.append(member)
        data = originals[member] + (b"tamper" if value.corrupt else b"")
        yield SimpleNamespace(status_code=200, headers={"content-length": str(len(data))},
                              iter_raw=lambda **kw: iter((data,)))

    @contextmanager
    def client(token, deadline, **kwargs):
        assert token == TOKEN and deadline > time.monotonic()
        yield value.api

    monkeypatch.setattr("huggingface_hub.utils.http_stream_backoff", http)
    monkeypatch.setattr(ci.storage, "_hf_client", client)
    return value


def _request_changed(case):
    case.args["request_json"] = ci._bytes(case.request).decode()
    case.args["expected_request_sha256"] = _identity(ci._bytes(case.request))["sha256"]


def _prepare(case):
    with ci.checked_request(**case.args) as context:
        return ci.prepare_and_claim(context)


def _effects(case, monkeypatch, outcome):
    marker = ci._read(case.root / "preparation" / registration.HANDOFF_READY)
    spec = SimpleNamespace(arguments={"observation": ObservationIdentity(**marker["observation"])},
                           consumed=case.root / ("preparation" + registration.HANDOFF_CONSUMED_SUFFIX))
    effects = _transport(monkeypatch, spec, outcome=outcome,
                         during_response=lambda: (_assert_no_storage_tokens()))
    return effects


def _assert_no_storage_tokens():
    assert not any(os.environ.get(key) for key in ci.TOKEN_KEYS)


@pytest.mark.parametrize("outcome", ["success", "failed", "missing_usage", "not_started"])
def test_time_budget_first_v2_ci_roundtrip(case, monkeypatch, outcome):
    receipt = _prepare(case)
    assert receipt["outcome"] == "acknowledged" and case.api.commits == ["claim"]
    assert len(case.downloads) == 3 and len(set(case.downloads)) == 3
    claim = receipt["claim"]
    assert claim["observation"]["condition"] == "sandbox_v2" and claim["observation"]["task_id"] == entry.TASK
    assert claim["ci"] == {"run_id": "7001", "run_number": 7, "job": ci.JOB, "attempt": 1}
    assert claim["host"]["ownership_confirmed"] is False
    assert claim["input_binding_sha256"] == claim["observation"]["input_sha256"]
    assert claim["preparation_identity"] == _identity((case.root / "preparation/preparation.json").read_bytes())
    if outcome != "not_started":
        effects = _effects(case, monkeypatch, outcome)
        for key in ci.TOKEN_KEYS:
            monkeypatch.setenv(key, "synthetic-token-that-must-not-reach-inference")
        with ci.checked_request(**case.args) as context:
            returned = ci.execute(context)
        assert len(effects.controls) == 1 and len(effects.runners) == 1
        assert effects.controls[0].identity == ObservationIdentity(**claim["observation"])
        assert effects.events[:3] == ["direction", "admission", "backend_start"]
        assert effects.controls[0].first_start == 2600
        assert returned["returned"]["status"] == ("error" if outcome == "failed" else "success")
        assert effects.requests and all(item["model"] == "gpt-5.4" for item in effects.requests)
        assert ci._read(case.root / "result" / entry.RESULT)["observation_execution"]["inputs"]["step0_manifest"] is None
        previous = len(effects.requests)
        with ci.checked_request(**case.args) as context, pytest.raises(ci.FirstV2CIRefused, match="execution_already_consumed"):
            ci.execute(context)
        assert len(effects.requests) == previous
    else:
        assert list((case.root / "observation").iterdir()) == []
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # A distinct storage step, not inference credentials.
    with ci.checked_request(**case.args, admission=False) as context:
        envelope = ci.retain(context)
    ci.validate_envelope(envelope)
    assert envelope == ci._read(case.root / "completion.json")
    assert case.api.commits == ["claim", "output"] and envelope["output_commit"] == case.api.head
    assert envelope["status"] == ("uncertain" if outcome == "not_started" else "error" if outcome == "failed" else "success")
    tree = case.api.trees[case.api.head]
    assert tree[ci.CLAIM] == ci._encoded(claim)
    manifest = json.loads(tree[ci.MANIFEST])
    assert manifest["claim_commit"] == receipt["returned_commit"]
    assert not any("original.parquet" in name or "reference-only" in name for name in tree)
    assert b"Synthetic handoff task" not in ci._bytes(envelope) and TOKEN.encode() not in ci._bytes(envelope)
    if outcome == "not_started":
        assert manifest["files"] == {} and envelope["result_identity"] is None and envelope["usage"] is None
        assert not (case.root / "result").exists()
        assert list((case.root / "observation").iterdir()) == []
    else:
        raw = (case.root / "result" / entry.RESULT).read_bytes()
        assert tree[ci.PREFIX + "/result/" + entry.RESULT] == raw
        assert envelope["result_identity"] == _identity(raw)
        assert (envelope["usage"] is None) == (outcome == "missing_usage")
        for name, identity in manifest["files"].items():
            assert _identity(tree[ci.PREFIX + "/" + name]) == identity
    with ci.checked_request(**case.args, admission=False) as context, pytest.raises((ValueError, FileExistsError)):
        ci.retain(context)
    assert case.api.commits == ["claim", "output"]


@pytest.mark.parametrize("change", ["digest", "extra", "source", "tree", "cell", "stale", "rerun", "manual_number", "workflow", "host", "input_anchor"])
def test_time_budget_first_v2_ci_authority_refuses_before_effects(case, monkeypatch, change):
    if change == "extra":
        case.request["approved"] = True
    elif change in {"source", "tree"}:
        case.request["source"]["sha" if change == "source" else "tree"] = "f" * 40
    elif change == "cell":
        case.request["cell"]["task_id"] = case.seed.task_ids[1]
    elif change == "stale":
        case.request.update(not_before_unix=1, expires_unix=2)
    elif change == "input_anchor":
        case.request["input_registration"]["source_sha"] = case.seed.runtime_sha
    elif change in {"rerun", "manual_number", "workflow", "host"}:
        key, value = {"rerun": ("GITHUB_RUN_ATTEMPT", "2"), "manual_number": ("GITHUB_RUN_NUMBER", "8"),
                      "workflow": ("TIME_BUDGET_WORKFLOW_SHA", "f" * 40), "host": ("RUNNER_ENVIRONMENT", "self-hosted")}[change]
        monkeypatch.setenv(key, value)
    _request_changed(case)
    if change == "digest":
        case.args["expected_request_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        _prepare(case)
    assert case.downloads == [] and case.api.calls == [] and not case.root.exists()


@pytest.mark.parametrize("change", ["runtime_bytes", "original_bytes", "direction", "preparation"])
def test_time_budget_first_v2_ci_genuine_validation_refusals(case, monkeypatch, change):
    if change == "runtime_bytes":
        source = case.seed.runtime / ci.HELPER
        before = source.read_bytes()
        try:
            source.write_bytes(before + b"\n# changed source\n")
            with pytest.raises(ValueError, match="source_differs_from_reviewed_blob"):
                _prepare(case)
        finally:
            source.write_bytes(before)
        assert case.downloads == [] and case.api.calls == [] and not case.root.exists()
        return
    if change == "original_bytes":
        case.corrupt = True
        with pytest.raises(ValueError, match="original byte identity"):
            _prepare(case)
        assert case.api.calls == [] and not (case.root / "preparation").exists()
        return
    _prepare(case)
    target = case.root / ("direction.json" if change == "direction" else "preparation/configuration.json")
    target.write_bytes(target.read_bytes() + b" ")
    with ci.checked_request(**case.args) as context, pytest.raises(ValueError):
        ci.execute(context)
    assert case.api.commits == ["claim"]
    assert not (case.root / ("preparation" + registration.HANDOFF_CONSUMED_SUFFIX)).exists()
    assert list((case.root / "observation").iterdir()) == []
    assert not (case.root / "result").exists()


@pytest.mark.parametrize("fault", ["race", "lost"])
def test_time_budget_first_v2_ci_cas_uncertainty_is_permanent(case, fault):
    case.api.race = fault == "race"
    case.api.lost = "claim" if fault == "lost" else None
    with pytest.raises(ci.FirstV2CIRefused, match="claim_unconfirmed_permanently_reserved"):
        _prepare(case)
    assert ci._read(case.root / "claim-receipt.json")["outcome"] == "unresolved"
    assert (case.root / "claim-reserved.json").is_file() and case.api.commits == ["claim"]
    with ci.checked_request(**case.args) as context, pytest.raises(ci.FirstV2CIRefused, match="acknowledged_same_host_claim_required"):
        ci.execute(context)
    with pytest.raises(ci.FirstV2CIRefused, match="partial_or_consumed_state_refused"):
        _prepare(case)
    assert case.api.commits == ["claim"] and not (case.root / "execution-reserved.json").exists()
    assert (ci.CLAIM in case.api.trees[case.api.head]) == (fault == "lost")


def test_time_budget_first_v2_ci_new_dispatch_cannot_reclaim_observation(case, monkeypatch):
    first = _prepare(case)
    original_tree = deepcopy(case.api.trees[case.api.head])
    case.root = case.root.with_name("another-private-destination")
    case.args["state_root"] = case.root
    case.request["paths"]["state_root"] = str(case.root)
    case.request["ci"]["run_number"] = 8
    case.request["storage"]["expected_parent"] = first["returned_commit"]
    _request_changed(case)
    monkeypatch.setenv("GITHUB_RUN_NUMBER", "8")
    monkeypatch.setenv("GITHUB_RUN_ID", "7002")
    with pytest.raises(ci.FirstV2CIRefused, match="claim_unconfirmed_permanently_reserved"):
        _prepare(case)
    assert case.api.commits == ["claim"] and case.api.trees[case.api.head] == original_tree
    assert ci._read(case.root / "claim-receipt.json")["outcome"] == "unresolved"
    assert not (case.root / "execution-reserved.json").exists()


def test_time_budget_first_v2_ci_retention_lost_response_and_envelope_allowlist(case, monkeypatch):
    _prepare(case)
    case.api.lost = "output"
    with ci.checked_request(**case.args, admission=False) as context, pytest.raises(ci.FirstV2CIRefused, match="private_retention_unconfirmed"):
        ci.retain(context)
    envelope = ci._read(case.root / "completion.json")
    assert envelope["retention"] == "unresolved" and envelope["output_commit"] is None
    assert ci.MANIFEST in case.api.trees[case.api.head] and (case.root / "retention-reserved.json").is_file()
    ci.validate_envelope(envelope)
    for name, value in (("exception", "private body"), ("prompt", "original input"), ("status", "success")):
        changed = {**envelope, name: value}
        with pytest.raises(ValueError):
            ci.validate_envelope(changed)
    with ci.checked_request(**case.args, admission=False) as context, pytest.raises((ValueError, FileExistsError)):
        ci.retain(context)
    assert case.api.commits == ["claim", "output"]


def test_time_budget_first_v2_ci_cli_request_validation_is_not_admission(case, monkeypatch, capsys):
    import logging

    monkeypatch.setenv("TIME_BUDGET_REQUEST_JSON", case.args["request_json"])
    command = ["validate-request", "--reviewed-source-sha", case.seed.runtime_sha,
               "--reviewed-source-tree", case.seed.runtime_tree,
               "--expected-request-sha256", case.args["expected_request_sha256"],
               "--runtime-root", str(case.seed.runtime), "--frozen-root", str(case.seed.frozen),
               "--state-root", str(case.root)]
    previous_mask, previous_logging = os.umask(0o077), logging.root.manager.disable
    try:
        assert ci.main(command) == 0
        assert json.loads(capsys.readouterr().out) == {"operation": "validate-request", "outcome": "completed"}
        monkeypatch.delenv("TIME_BUDGET_REQUEST_JSON")
        assert ci.main(command) == 2
        assert json.loads(capsys.readouterr().out) == {"outcome": "refused_or_uncertain"}
    finally:
        os.umask(previous_mask)
        logging.disable(previous_logging)
    assert case.downloads == case.api.calls == [] and not case.root.exists()


def test_time_budget_first_v2_ci_workflow_command_and_guard_contract():
    root = Path(__file__).resolve().parents[2]
    text = (root / ci.WORKFLOW).read_text()
    document = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(document["on"]) == {"workflow_dispatch"}
    assert set(document["on"]["workflow_dispatch"]["inputs"]) == {
        "reviewed_source_sha", "reviewed_source_tree", "request_sha256", "request_json"}
    assert document["permissions"] == {"contents": "read", "id-token": "write"}
    assert document["concurrency"] == {"group": "gpt54-time-budget-first-v2-observation", "cancel-in-progress": "false"}
    assert set(document["jobs"]) == {ci.JOB}
    job = document["jobs"][ci.JOB]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == "45"
    steps = job["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    gate = steps[0]["run"]
    for item in ("GITHUB_EVENT_NAME", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_ACTOR", "GITHUB_TRIGGERING_ACTOR",
                 "GITHUB_RUN_ATTEMPT", "REVIEWED_SOURCE_SHA", "REVIEWED_SOURCE_TREE", "GITHUB_SHA",
                 "TIME_BUDGET_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF", "REQUEST_SHA256", "GITHUB_RUN_NUMBER", entry.TASK):
        assert item in gate
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"] == {"ref": "${{ inputs.reviewed_source_sha }}", "fetch-depth": "0", "persist-credentials": "false"}
    for operation in ("validate-request", "prepare-and-claim", "execute", "retain", "verify-envelope"):
        command = "python3 batch-runner/gpt54_time_budget_v2_ci.py " + operation
        selected = [step for step in steps if command in step.get("run", "")]
        assert len(selected) == 1
        for flag in ("--reviewed-source-sha", "--reviewed-source-tree", "--expected-request-sha256",
                     "--runtime-root", "--frozen-root", "--state-root"):
            assert flag in selected[0]["run"]
    claim = next(index for index, step in enumerate(steps) if step.get("id") == "admission")
    login = next(index for index, step in enumerate(steps) if step.get("uses", "").startswith("azure/login@"))
    execute = next(index for index, step in enumerate(steps) if "gpt54_time_budget_v2_ci.py execute" in step.get("run", ""))
    retain = next(index for index, step in enumerate(steps) if "gpt54_time_budget_v2_ci.py retain" in step.get("run", ""))
    assert claim < login < execute < retain
    assert "steps.admission.outputs.acknowledged == 'true'" in steps[login]["if"]
    assert "steps.admission.outputs.acknowledged == 'true'" in steps[execute]["if"]
    assert steps[retain]["if"].startswith("always()")
    assert steps[execute]["env"] == {"AZURE_AI_ROUTE_PROFILE": "direct-v1", "FOUNDRY_PROJECT_ENDPOINT": "${{ secrets.FOUNDRY_PROJECT_ENDPOINT }}"}
    for key in ci.TOKEN_KEYS:
        assert key in steps[execute]["run"]
    assert [index for index, step in enumerate(steps) if "HF_TOKEN" in step.get("env", {})] == [claim, retain]
    assert steps[-1]["with"]["path"] == "${{ runner.temp }}/time-budget-first-v2/completion.json"
    assert steps[-1]["with"]["retention-days"] == "7"
    assert "steps.envelope.outputs.safe == 'true'" in steps[-1]["if"]
    assert all("continue-on-error" not in step for step in steps)
    for forbidden in ("workflow_call", "_import_local_bundle", "--resume", "step0", "step8", "az deployment", "gh run", "CODEX_FOUNDRY_CONNECTION_CONFIRMED"):
        assert forbidden not in commands
