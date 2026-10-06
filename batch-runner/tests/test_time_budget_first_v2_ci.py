"""New Actions route only: real validators, synthetic inputs/HTTP/model/kernel.

No private original, live receipt, provider, HF or platform probe is accessed.
The temporary Git declarations name synthetic input bytes, not paid evidence.
"""

import io
import json
import os
import shlex
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
from .test_gpt54_disposable_checkout import _FIXTURE_ENV

_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen
TOKEN = "explicitly-synthetic-storage-token"


class PrivateStore:
    """Transport seam with real immutable byte objects, CAS and first writers."""

    def __init__(self, *, prefix=ci.PREFIX):
        self.head = "1" * 40
        self.claim, self.manifest = prefix + "/admission.json", prefix + "/output-manifest.json"
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
        assert kwargs["filename"] in {self.claim, self.manifest}
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
        kind = "claim" if set(files) == {self.claim} else "output"
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


@pytest.fixture
def actions_layout(handoff_source_seed, tmp_path, monkeypatch):
    """Ordinary Actions bootstrap plus real registered R/F; no credential use."""
    seed = handoff_source_seed
    bootstrap, runner_temp = tmp_path / "bootstrap", tmp_path / "runner-temp"
    runner_temp.mkdir()
    environment = {**_FIXTURE_ENV, "GIT_ALLOW_PROTOCOL": "file",
                   "GITHUB_WORKSPACE": str(bootstrap), "RUNNER_TEMP": str(runner_temp),
                   "REVIEWED_SOURCE_SHA": seed.runtime_sha, "REVIEWED_SOURCE_TREE": seed.runtime_tree}

    def local(command, *, check=True, cwd=None):
        # Only this explicit fixture setup may write temporary Git metadata.
        # The controller's ordinary subprocess seam below stays read-only.
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, check=check, cwd=cwd, env=environment,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    local(["/usr/bin/git", "clone", "--shared", "--", str(seed.runtime), str(bootstrap)])
    local(["/usr/bin/git", "-C", str(bootstrap), "fetch", "--no-tags", "--", str(seed.frozen), seed.frozen_sha])
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load((root / ci.WORKFLOW).read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"][ci.JOB]["steps"]
    layout_command = next(step["run"] for step in steps if "git worktree add --detach" in step.get("run", ""))
    # Only the independently declared synthetic F identities replace literals;
    # all path, no-clobber and actual worktree commands are the workflow's bytes.
    layout_command = layout_command.replace("882868ccf4e2ddeeab56cf7d02ba4ba9edba6fd2", seed.frozen_sha)
    layout_command = layout_command.replace("45d024f15c8d4b90ec6c65a4dacdbaa16c41f9ca", seed.frozen_tree)

    def create_sources():
        return local(["/bin/bash", "-c", layout_command], cwd=bootstrap, check=False)

    created = create_sources()
    assert created.returncode == 0, created.stderr.decode()
    runtime, frozen = runner_temp / ci.RUNTIME_BASENAME, runner_temp / ci.FROZEN_BASENAME
    return SimpleNamespace(bootstrap=bootstrap, runner_temp=runner_temp, runtime=runtime, frozen=frozen,
                           workflow=workflow, local=local, create_sources=create_sources,
                           git_roots={bootstrap, runtime, frozen})


@pytest.fixture(autouse=True)
def offline(monkeypatch, handoff_sources, actions_layout, dual_roots, observation_kernel):
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
        assert Path(command[index + 1]) in actions_layout.git_roots | {
            handoff_sources.runtime, handoff_sources.frozen,
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
def case(handoff_sources, actions_layout, monkeypatch):
    seed = SimpleNamespace(**{**vars(handoff_sources), "runtime": actions_layout.runtime,
                              "frozen": actions_layout.frozen})
    root = actions_layout.runner_temp / "time-budget-first-v2"
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
        "GITHUB_WORKSPACE": str(actions_layout.bootstrap), "RUNNER_TEMP": str(actions_layout.runner_temp),
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


@pytest.mark.parametrize("change", [
    "task2", "unregistered_task", "run", "condition", "repeat", "prefix", "source",
    "direction_task", "result_task", "result_source", "old_task1_claim",
])
def test_time_budget_v2_registered_task_selection(case, actions_layout, monkeypatch, change):
    """One selected task, real validators/factory, and immutable synthetic CAS.

    The pre-existing Task1 objects below are invented test bytes, not a read or
    reconstruction of its real consumed/uncertain claim or private output.
    """
    task1 = "02aa1805-c658-4069-8a6a-02dec146063a"
    task2 = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1"
    base = "time-budget/gpt54_sandboxv2_codex_time_budget_v1/gpt54_time_budget_v1_v2_r1/"
    old_prefix, selected_prefix = base + task1, base + task2
    assert case.seed.task_ids[:2] == (task1, task2)
    assert (ci.PREFIX, ci.CLAIM, ci.MANIFEST) == (
        old_prefix, old_prefix + "/admission.json", old_prefix + "/output-manifest.json")
    old_objects = {
        old_prefix + "/admission.json": b"Explicitly synthetic old permanent claim; never adopt.\n",
        old_prefix + "/output-manifest.json": b"Explicitly synthetic old uncertainty; never rewrite.\n",
    }
    case.request["cell"]["task_id"] = task1 if change == "old_task1_claim" else task2
    case.request["storage"]["prefix"] = old_prefix if change == "old_task1_claim" else selected_prefix
    case.api = PrivateStore(prefix=case.request["storage"]["prefix"])
    case.api.trees[case.api.head] = dict(old_objects)
    case.api.writers[case.api.head] = {name: case.api.head for name in old_objects}
    original_head = case.api.head
    original_trees, original_writers = deepcopy(case.api.trees), deepcopy(case.api.writers)
    if change == "unregistered_task":
        case.request["cell"]["task_id"] = "00000000-0000-4000-8000-000000000000"
    elif change == "run":
        case.request["cell"]["run_id"] = "gpt54_time_budget_v1_v2_r2"
    elif change == "condition":
        case.request["cell"]["condition"] = "codex"
    elif change == "repeat":
        case.request["cell"]["repeat"] = 2
    elif change == "prefix":
        case.request["storage"]["prefix"] = old_prefix
    elif change == "source":
        case.request["source"]["sha"] = "f" * 40
    _request_changed(case)

    # Run the actual credential-free early guard, not a hand-built equivalent.
    # The only child is this inspected Bash/Python source guard; the ordinary
    # controller's socket/write/subprocess sentinels remain installed.
    gate = actions_layout.workflow["jobs"][ci.JOB]["steps"][0]["run"]
    environment = {key: value for key, value in os.environ.items() if key not in ci.TOKEN_KEYS}
    environment.update(REVIEWED_SOURCE_SHA=case.seed.runtime_sha, REVIEWED_SOURCE_TREE=case.seed.runtime_tree,
                       REQUEST_SHA256=case.args["expected_request_sha256"],
                       TIME_BUDGET_REQUEST_JSON=case.args["request_json"])
    with monkeypatch.context() as process:
        process.setattr(subprocess, "Popen", _REAL_POPEN)
        guarded = _REAL_RUN(["/bin/bash", "-c", gate], cwd=actions_layout.bootstrap, env=environment,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    assert (guarded.returncode != 0) == (change in {"unregistered_task", "run", "condition", "repeat", "source"})

    if change in {"unregistered_task", "run", "condition", "repeat", "prefix", "source"}:
        with pytest.raises(ValueError):
            _prepare(case)
        assert case.downloads == case.api.calls == [] and not case.root.exists()
        assert case.api.trees == original_trees and case.api.writers == original_writers
        return
    if change == "old_task1_claim":
        with pytest.raises(ci.FirstV2CIRefused, match="claim_unconfirmed_permanently_reserved"):
            _prepare(case)
        assert ci._read(case.root / "claim-receipt.json")["outcome"] == "unresolved"
        assert case.api.head == original_head and case.api.trees == original_trees
        assert case.api.writers == original_writers and case.api.commits == []
        assert case.api.calls == ["metadata", "objects"]  # No old body read/adoption or new CAS.
        with ci.checked_request(**case.args) as context, pytest.raises(
                ci.FirstV2CIRefused, match="acknowledged_same_host_claim_required"):
            ci.execute(context)
        with pytest.raises(ci.FirstV2CIRefused, match="partial_or_consumed_state_refused"):
            _prepare(case)
        assert not (case.root / "execution-reserved.json").exists()
        assert not (case.root / "result").exists() and list((case.root / "observation").iterdir()) == []
        assert case.api.trees == original_trees and case.api.commits == []
        return

    receipt = _prepare(case)
    claim = receipt["claim"]
    marker = ci._read(case.root / "preparation" / registration.HANDOFF_READY)
    assert claim["observation"] == marker["observation"]
    assert marker["inputs"]["task_id"] == marker["observation"]["task_id"] == task2
    assert marker["inputs"]["step0_manifest"] is None
    config = ci._read(case.root / "preparation/configuration.json")
    assert config["task_ids"] == [task2]
    assert config["fixed_settings"]["retry_max_attempts"] == 1
    assert config["fixed_settings"]["per_task_timeout_seconds"] == 1200
    assert claim["storage"]["prefix"] == selected_prefix
    assert claim["ci"] == {"run_id": "7001", "run_number": 7, "job": ci.JOB, "attempt": 1}
    assert receipt["outcome"] == "acknowledged" and case.api.commits == ["claim"]
    claim_tree = deepcopy(case.api.trees[case.api.head])
    assert {name: claim_tree[name] for name in old_objects} == old_objects
    assert set(claim_tree) - set(old_objects) == {selected_prefix + "/admission.json"}
    direction = ci._read(case.root / "direction.json")
    assert json.loads(direction["execution_binding"]["observation_json"]) == marker["observation"]
    assert direction["host_sha256"] == claim["host"]["instance_sha256"]
    assert _identity(ci._bytes(direction)) == claim["direction_identity"]
    effects = _effects(case, monkeypatch, "success")
    if change == "direction_task":
        cross_task = {**marker["observation"], "task_id": task1}
        direction["execution_binding"]["observation_json"] = ci._canonical_json(cross_task)
        (case.root / "direction.json").write_bytes(ci._bytes(direction))
        with ci.checked_request(**case.args) as context, pytest.raises(ValueError):
            ci.execute(context)
        assert effects.controls == effects.events == effects.requests == []
        assert not (case.root / "execution-reserved.json").exists()
        assert not (case.root / ("preparation" + registration.HANDOFF_CONSUMED_SUFFIX)).exists()
        assert not (case.root / "result").exists() and case.api.trees[case.api.head] == claim_tree
        return

    for key in ci.TOKEN_KEYS:
        monkeypatch.setenv(key, "synthetic-storage-token-must-not-enter-inference")
    with ci.checked_request(**case.args) as context:
        assert context["cell"] == case.request["cell"]
        returned = ci.execute(context)
    assert returned["returned"]["status"] == "success"
    assert len(effects.controls) == len(effects.runners) == 1
    assert effects.controls[0].identity == ObservationIdentity(**claim["observation"])
    assert effects.events[:3] == ["direction", "admission", "backend_start"]
    assert effects.controls[0].first_start == 2600
    assert b"Synthetic handoff task 1:" in ci._bytes(effects.requests[0]["input"])
    assert b"Synthetic handoff task 0:" not in ci._bytes(effects.requests[0]["input"])
    _assert_no_storage_tokens()
    result_path = case.root / "result" / entry.RESULT
    raw = result_path.read_bytes()
    payload = json.loads(raw)
    assert payload["time_budget_observation"]["identity"] == claim["observation"]
    assert payload["time_budget_observation"]["terminal_reason"] == "completed"
    assert payload["observation_execution"]["inputs"] == marker["inputs"]
    row = payload["results"][0]
    deliverable = "deliverable_files/" + task2 + "/report.txt"
    assert row["task_id"] == task2 and row["deliverable_files"] == [deliverable]
    assert row["deliverable_file_records"] == [
        {"path": deliverable, **_identity(b"Explicitly synthetic output.\n")}]
    assert row["retried"] is False and row["resume_round"] is None
    assert payload["result_fingerprint"] == entry.inference_result_fingerprint(payload)
    if change in {"result_task", "result_source"}:
        if change == "result_task":
            row["task_id"] = task1
            row["deliverable_files"] = [deliverable.replace(task2, task1)]
            row["deliverable_file_records"][0]["path"] = deliverable.replace(task2, task1)
        else:
            payload["source"] = "synthetic/wrong-dataset"
        payload["result_fingerprint"] = entry.inference_result_fingerprint(payload)
        assert entry.canonicalize_inference_payload(payload) == payload
        changed = ci._bytes(payload)
        result_path.write_bytes(changed)
        execution = ci._read(case.root / "execution-receipt.json")
        execution["returned"].update(result_identity=_identity(changed), result_fingerprint=payload["result_fingerprint"])
        (case.root / "execution-receipt.json").write_bytes(ci._bytes(execution))
        calls = list(case.api.calls)
        monkeypatch.setenv("HF_TOKEN", TOKEN)
        reason = "result task scope" if change == "result_task" else "result source"
        with ci.checked_request(**case.args, admission=False) as context, pytest.raises(ValueError, match=reason):
            ci.retain(context)
        assert case.api.calls == calls and case.api.trees[case.api.head] == claim_tree
        assert not (case.root / "retention-reserved.json").exists()
        assert not (case.root / "completion.json").exists()
    else:
        monkeypatch.setenv("HF_TOKEN", TOKEN)  # Separate bounded private-retention step.
        with ci.checked_request(**case.args, admission=False) as context:
            envelope = ci.retain(context)
        ci.validate_envelope(envelope, expected_cell=case.request["cell"])
        assert envelope["task_id"] == task2 and envelope["retention"] == "acknowledged"
        assert envelope["status"] == "success" and envelope["retry_allowed"] is False
        assert envelope["grading_performed"] is False and envelope["other_cells_executed"] == 0
        assert envelope["result_identity"] == returned["returned"]["result_identity"] == _identity(raw)
        assert envelope["result_fingerprint"] == payload["result_fingerprint"]
        tree = case.api.trees[case.api.head]
        assert case.api.commits == ["claim", "output"]
        assert {name: tree[name] for name in old_objects} == old_objects
        assert all(name.startswith(selected_prefix + "/") for name in set(tree) - set(old_objects))
        assert tree[selected_prefix + "/result/" + entry.RESULT] == raw
        manifest = json.loads(tree[selected_prefix + "/output-manifest.json"])
        assert manifest["observation"] == claim["observation"] and manifest["claim_commit"] == receipt["returned_commit"]
        for name, identity in manifest["files"].items():
            assert _identity(tree[selected_prefix + "/" + name]) == identity
        assert b"Synthetic handoff task" not in ci._bytes(envelope) and TOKEN.encode() not in ci._bytes(envelope)
        assert not any("original.parquet" in name or "reference-only" in name for name in tree)
        with pytest.raises(ValueError, match="completion constants"):
            ci.validate_envelope({**envelope, "task_id": task1}, expected_cell=case.request["cell"])
    attempts = len(effects.requests)
    with ci.checked_request(**case.args) as context, pytest.raises(ci.FirstV2CIRefused, match="execution_already_consumed"):
        ci.execute(context)
    assert len(effects.requests) == attempts
    assert (case.root / "claim-reserved.json").is_file() and (case.root / "execution-reserved.json").is_file()


@pytest.mark.parametrize("change", [
    "linked", "ordinary_runtime", "bootstrap_commit", "bootstrap_tree", "bootstrap_common",
    "final_bootstrap_commit", "final_bootstrap_common",
])
def test_time_budget_first_v2_ci_source_layout(case, actions_layout, monkeypatch, observation_kernel, capsys, change):
    """Exercise the real workflow layout and source guards, never input intake."""
    layout = actions_layout
    assert (layout.bootstrap / ".git").is_dir()
    for root in (layout.runtime, layout.frozen):
        assert (root / ".git").is_file()
        assert ci._repository(root)[1] == layout.bootstrap / ".git"
    assert layout.runtime != layout.frozen

    if change == "linked":
        before = [(root / ".git").read_bytes() for root in (layout.runtime, layout.frozen)]
        assert layout.create_sources().returncode != 0  # No adoption or clobber.
        assert [(root / ".git").read_bytes() for root in (layout.runtime, layout.frozen)] == before
        assert (layout.runtime / ci.HELPER).read_bytes() == Path(ci.__file__).read_bytes()
        for key, value in {"REVIEWED_SOURCE_SHA": case.seed.runtime_sha,
                           "REVIEWED_SOURCE_TREE": case.seed.runtime_tree,
                           "REQUEST_SHA256": case.args["expected_request_sha256"],
                           "TIME_BUDGET_REQUEST_JSON": case.args["request_json"]}.items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("HF_TOKEN")
        steps = layout.workflow["jobs"][ci.JOB]["steps"]
        for operation in ("validate-request", "prepare-and-claim", "execute", "retain", "verify-envelope"):
            prefix = 'python3 "$RUNNER_TEMP/time-budget-v2-runtime/' + ci.HELPER + '" ' + operation
            command = next(step["run"] for step in steps if prefix in step.get("run", ""))
            lines = command[command.index(prefix):].splitlines()
            end = next(index for index, line in enumerate(lines) if not line.endswith("\\"))
            argv = shlex.split(os.path.expandvars("\n".join(lines[:end + 1]).replace("\\\n", "")))
            assert argv == ["python3", str(layout.runtime / ci.HELPER), operation,
                "--reviewed-source-sha", case.seed.runtime_sha, "--reviewed-source-tree", case.seed.runtime_tree,
                "--expected-request-sha256", case.args["expected_request_sha256"],
                "--runtime-root", str(layout.runtime), "--frozen-root", str(layout.frozen), "--state-root", str(case.root)]
            if operation == "validate-request":
                assert ci.main(argv[2:]) == 0
                assert json.loads(capsys.readouterr().out) == {"operation": operation, "outcome": "completed"}
        assert os.environ["GITHUB_WORKSPACE"] == str(layout.bootstrap)
    else:
        peer = None
        if change.endswith("common"):
            peer = layout.bootstrap.with_name("other-bootstrap")
            layout.local(["/usr/bin/git", "clone", "--shared", "--", str(layout.bootstrap), str(peer)])
            layout.git_roots.add(peer)
            assert ci._git(peer, "rev-parse", "HEAD").stdout == (case.seed.runtime_sha + "\n").encode()
            assert ci._git(peer, "rev-parse", "HEAD^{tree}").stdout == (case.seed.runtime_tree + "\n").encode()

        def change_bootstrap():
            if change.endswith("commit"):
                (layout.bootstrap / ".git/HEAD").write_text(case.seed.frozen_sha + "\n")
            elif change == "final_bootstrap_common":
                (layout.bootstrap / ".git").rename(layout.bootstrap / ".git-previous")
                (peer / ".git").rename(layout.bootstrap / ".git")
            else:
                monkeypatch.setenv("GITHUB_WORKSPACE", str(peer))

        if change.startswith("final_"):
            reason = "bundle parent changed" if change.endswith("common") else "actions_bootstrap_commit_or_tree_changed"
            with pytest.raises(ValueError, match=reason):
                with ci.checked_request(**case.args):
                    change_bootstrap()
        else:
            reason = "actions_bootstrap_commit_or_tree_changed"
            if change == "ordinary_runtime":
                # The shared source validator still refuses an ordinary .git.
                with pytest.raises(ValueError, match="detached checkout registration mismatch"):
                    with registration._reviewed_source(layout.bootstrap, case.seed.runtime_sha, ci.SOURCE_ROLES):
                        pytest.fail("ordinary bootstrap admitted as runtime")
                case.args["runtime_root"] = layout.bootstrap
                case.request["paths"]["runtime_root"] = str(layout.bootstrap)
                reason = "ci_canonical_roots_required"
            elif change == "bootstrap_tree":
                case.args["reviewed_source_tree"] = case.seed.frozen_tree
                case.request["source"]["tree"] = case.seed.frozen_tree
            else:
                change_bootstrap()
                if change == "bootstrap_common":
                    reason = "actions_linked_common_git_required"
            _request_changed(case)
            with pytest.raises(ci.FirstV2CIRefused, match=reason):
                _prepare(case)

    assert case.downloads == [] and case.api.calls == [] and case.api.commits == []
    assert not case.root.exists()
    assert observation_kernel.subreaper == 0 and observation_kernel.processes == {}
    assert observation_kernel.signals == [] and observation_kernel.reaped == []


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
        assert returned["returned"]["status"] == ("error" if outcome in {"failed", "missing_usage"} else "success")
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
    ci.validate_envelope(envelope, expected_cell=case.request["cell"])
    assert envelope == ci._read(case.root / "completion.json")
    assert case.api.commits == ["claim", "output"] and envelope["output_commit"] == case.api.head
    assert envelope["status"] == ("uncertain" if outcome == "not_started" else "error" if outcome in {"failed", "missing_usage"} else "success")
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
        if outcome == "missing_usage":
            payload = json.loads(raw)
            row = payload["results"][0]
            assert row["status"] == "error" and payload["time_budget_observation"]["terminal_reason"] == "failed"
            assert row["usage"] is None and row["observability"]["usage_availability"]["usage_complete"] is False
            assert row["deliverable_file_records"] == [] and row["deliverable_files"] == []
            assert set(manifest["files"]) == {"result/" + entry.RESULT}
            assert not any(path.is_file() for path in (case.root / "result" / "upload").rglob("*"))
            assert envelope["terminal_reason"] == "failed" and envelope["usage"] is None
            assert "usage_complete" not in envelope and envelope["retention"] == "acknowledged"
            assert envelope["result_identity"] == returned["returned"]["result_identity"] == _identity(raw)
            assert (envelope["result_fingerprint"] == returned["returned"]["result_fingerprint"]
                    == payload["result_fingerprint"] == entry.inference_result_fingerprint(payload))
            assert (case.root / "claim-reserved.json").is_file()
            assert (case.root / "execution-reserved.json").is_file()
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
        case.request["cell"]["task_id"] = "00000000-0000-4000-8000-000000000000"
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
    ci.validate_envelope(envelope, expected_cell=case.request["cell"])
    for name, value in (("exception", "private body"), ("prompt", "original input"), ("status", "success")):
        changed = {**envelope, name: value}
        with pytest.raises(ValueError):
            ci.validate_envelope(changed, expected_cell=case.request["cell"])
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
        command = 'python3 "$RUNNER_TEMP/time-budget-v2-runtime/batch-runner/gpt54_time_budget_v2_ci.py" ' + operation
        selected = [step for step in steps if command in step.get("run", "")]
        assert len(selected) == 1
        for flag in ("--reviewed-source-sha", "--reviewed-source-tree", "--expected-request-sha256",
                     "--runtime-root", "--frozen-root", "--state-root"):
            assert flag in selected[0]["run"]
    claim = next(index for index, step in enumerate(steps) if step.get("id") == "admission")
    login = next(index for index, step in enumerate(steps) if step.get("uses", "").startswith("azure/login@"))
    execute = next(index for index, step in enumerate(steps) if 'gpt54_time_budget_v2_ci.py" execute' in step.get("run", ""))
    retain = next(index for index, step in enumerate(steps) if 'gpt54_time_budget_v2_ci.py" retain' in step.get("run", ""))
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
