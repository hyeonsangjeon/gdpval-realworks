"""One offline retained-cell integration family, not a paid-cell observation.

The compiler, input-byte reads, dispatcher, deadlines, owned-child projections,
publisher, CAS ordering and immutable byte checks are real. Only original-input
provenance, reviewed source/host capability, child execution and HF are synthetic.
No credential store, provider, original payload, model or grader is accessed.
"""

from __future__ import annotations

from decimal import Decimal
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from types import SimpleNamespace

from huggingface_hub import CommitOperationAdd, RepoFile, RepoFolder
import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retention
from core import azure_ai_clients, codex_azure_token, codex_runner
from core.cost_receipts import CostReceipt
from core.inference_manifest import bind_deliverable_file_records
from core.result_fingerprint import inference_result_fingerprint
from .test_codex_budget_pilot import scenario, read_plan, read_state  # noqa: F401
from .test_codex_budget_pilot_ci import CICellChildren

TOKEN = "hf_SYNTHETIC_RETENTION_NOT_A_CREDENTIAL"
SOURCE = "1" * 40
TOKEN_KEYS = {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # This family uses fake children and must not require a native SDK install
    # merely to forbid one. Block the existing repository constructors as well
    # as all process/socket/auth/data boundaries; do not fabricate an SDK module.
    import step8_grade
    from huggingface_hub import HfApi, hf_api
    from huggingface_hub.utils import _auth, _headers

    def blocked(*args, **kwargs):
        raise AssertionError("retained-cell regression crossed a live boundary")

    for target, names in (
        (subprocess, ("run", "Popen", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (os, ("system",)), (time, ("sleep",)),
        (pilot, ("_source_snapshot", "_step0_bytes")),
        (codex_azure_token, ("acquire_token", "get_bearer_token_provider")),
        (_auth, ("get_token",)), (_headers, ("get_token",)),
        (hf_api, ("_get_token_from_file", "_get_token_from_environment", "_get_token_from_google_colab")),
        (HfApi, ("repo_info", "create_commit", "hf_hub_download", "create_repo", "whoami")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, blocked)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                        codex_runner.CodexAgentRunner, step8_grade.Grader):
        monkeypatch.setattr(constructor, "__init__", blocked)


class MemoryHF:
    """Add-only immutable fake with actual parent/CAS and object-byte checks."""

    def __init__(self):
        self.repo = retention._target()
        self.head = retention.BOOTSTRAP
        self.trees = {self.head: {}}
        self.parents, self.writers = {}, {self.head: {}}
        self.calls, self.commits, self.events = [], [], []
        self.private, self.id_matches = True, True
        self.fail, self.lost, self.bad_oid, self.ignore = None, None, None, None
        self.read_fail = False
        self.move_before_commit = False

    def record(self, name, kwargs):
        valid = kwargs["repo_id"] == self.repo and kwargs["repo_type"] == "dataset" and kwargs["token"] == TOKEN
        assert valid, "exact selected dataset and explicit synthetic token required"
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}.intersection(os.environ)
        self.calls.append((name, kwargs.get("revision")))

    def repo_info(self, **kwargs):
        self.record("metadata", kwargs)
        assert 0 < kwargs["timeout"] <= output.REQUEST_SECONDS
        revision = self.head if kwargs["revision"] == retention.BRANCH else kwargs["revision"]
        assert revision in self.trees
        return SimpleNamespace(id=self.repo if self.id_matches else "synthetic-foreign/target", private=self.private, sha=revision)

    def get_paths_info(self, **kwargs):
        self.record("paths", kwargs)
        revision = kwargs["revision"]
        assert output._hash(revision, 40)
        tree, found = self.trees[revision], []
        if self.read_fail:
            raise output.OutputPublicationRefused("hf_http_failed", 503)
        for name in kwargs["paths"]:
            if name in tree:
                item = object.__new__(RepoFile)
                item.path, item.size, item.blob_id = name, len(tree[name]), retention._git_blob(tree[name])
                item.lfs = None
                item.last_commit = SimpleNamespace(oid=self.writers[revision][name])
                found.append(item)
            elif any(path.startswith(name + "/") for path in tree):
                item = object.__new__(RepoFolder)
                item.path = name
                found.append(item)
        return found

    def hf_hub_download(self, **kwargs):
        self.record("control_read", kwargs)
        assert kwargs["force_download"] is True and kwargs["local_files_only"] is False
        assert kwargs["filename"].rsplit("/", 1)[-1] in {"admission.json", "terminal.json", output.MANIFEST}
        assert 0 < kwargs["etag_timeout"] <= output.REQUEST_SECONDS
        path = Path(kwargs["cache_dir"]) / "control.json"
        output._write_no_clobber(path, self.trees[kwargs["revision"]][kwargs["filename"]])
        return str(path)

    def create_commit(self, **kwargs):
        self.record("commit", kwargs)
        assert kwargs["revision"] == retention.BRANCH and kwargs["num_threads"] == 1
        assert kwargs["run_as_future"] is False and kwargs["create_pr"] is False
        records = {}
        for operation in kwargs["operations"]:
            assert type(operation) is CommitOperationAdd and isinstance(operation.path_or_fileobj, io.BufferedIOBase)
            records[operation.path_in_repo] = operation.path_or_fileobj.read()
        kind = ("admission" if any(name.endswith("/admission.json") for name in records) else
                "terminal" if any(name.endswith("/terminal.json") for name in records) else "output")
        self.commits.append(kind)
        self.events.append(kind)
        if self.move_before_commit or kwargs["parent_commit"] != self.head:
            raise output.OutputPublicationRefused("hf_http_failed", 409)
        if self.fail == kind:
            raise output.OutputPublicationRefused("hf_http_failed", 403)
        assert not set(records).intersection(self.trees[self.head]), "fake server does not overwrite"
        previous, revision = self.head, f"{len(self.parents) + 1:040x}"
        self.trees[revision] = {**self.trees[previous], **records}
        self.writers[revision] = {**self.writers[previous], **{name: revision for name in records}}
        self.parents[revision], self.head = previous, revision
        if self.ignore == kind:
            kwargs["operations"][0]._should_ignore = True
        if self.lost == kind:
            raise output.OutputPublicationRefused("hf_transport_failed")
        return SimpleNamespace(oid="not-an-immutable-id" if self.bad_oid == kind else revision)


class RetainedChildren(CICellChildren):
    def __init__(self, sources, task_ids, api):
        super().__init__(sources, task_ids)
        self.api, self.partial, self.with_ledger = api, False, True

    def _process(self, command, **options):
        assert not TOKEN_KEYS.intersection(options["env"])
        assert options["env"]["HF_HUB_OFFLINE"] == options["env"]["HF_DATASETS_OFFLINE"] == "1"
        assert self.api.commits == ["admission"], "the verified CAS claim must precede either child"
        self.api.events.append("child")
        result = super()._process(command, **options)
        if command[1] != "step2_run_inference.py":
            return result
        workspace = options["cwd"] / "workspace"
        path = workspace / Path(pilot.RESULT).name
        if not path.exists():
            return result
        payload = json.loads(path.read_bytes())
        row = payload["results"][0]
        row["observability"] = {"preprocessors": []}
        name = f"deliverable_files/{row['task_id']}/synthetic-result.txt"
        row["deliverable_files"] = [name]
        pilot._write_file(workspace / "upload" / name, b"Synthetic retained deliverable.\n")
        payload["results"] = bind_deliverable_file_records(payload["results"], workspace / "upload")
        if self.partial:
            row["problem_solving_cost"] = CostReceipt(status="partial", known_cost_usd=Decimal("0.01"),
                model_cost_usd=Decimal("0.01"), model_calls=1,
                usage={"input_tokens": 12, "output_tokens": 3, "reasoning_tokens": 2},
                missing_reasons=("synthetic_missing_cost",)).as_dict()
            payload["results"][0]["problem_solving_cost"] = row["problem_solving_cost"]
        if self.with_ledger:
            ledger = {key: None for key in output._CALL_COLUMNS}
            ledger.update(record_type="call", call_id="synthetic-call", run_id=payload["run_id"],
                          task_id=row["task_id"], stage="generation", retry_kind="none", state="settled",
                          missing_reasons=["synthetic_missing_cost"])
            data = (json.dumps(ledger) + "\n").encode()
            pilot._write_file(workspace / Path(pilot.LEDGER).name, data)
            payload["cost_ledger"] = {"path": Path(pilot.LEDGER).name, "sha256": pilot._identity(data)["sha256"]}
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
        path.write_bytes((json.dumps(payload, indent=2) + "\n").encode())
        # Neighbouring files/native partials must never be published.
        for excluded in ("auth.json", "raw.log", "native-transcript.jsonl", "raw.sqlite3"):
            pilot._write_file(workspace / excluded, b"DO NOT RETAIN")
        return result


@pytest.fixture
def case(scenario, monkeypatch):
    s = scenario
    real_version = ci.importlib.metadata.version
    monkeypatch.setattr(ci.importlib.metadata, "version", lambda name:
                        "0.147.0" if name in {"openai-codex", "openai-codex-cli-bin"} else real_version(name))
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_SHA": SOURCE,
        "PILOT_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ATTEMPT": "1", "RUNNER_OS": "Linux", "ImageOS": "ubuntu22",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": "1234", "GITHUB_JOB": "cell", "RUNNER_NAME": "synthetic-retention-host"}.items():
        monkeypatch.setenv(key, value)
    for key in TOKEN_KEYS:
        monkeypatch.delenv(key, raising=False)
    # Everything under _hf_client would be a real transport and is forbidden.
    monkeypatch.setattr(output, "_hf_client", lambda *a, **k: pytest.fail("live HF client reached"))
    s.api = MemoryHF()
    s.transport = RetainedChildren(s.sources, s.ids, s.api)
    s.selected = s.ids[1] + "_A_r1"
    s.envelope = s.host / "completion.json"
    s.argv[0:2] = ["--campaign-id", ci.CAMPAIGN]
    s.argv += ["--cell", s.selected, "--completion-out", str(s.envelope)]
    return s


def cli(s, *options):
    return ci.main([*s.argv, *options], _test_transport=s.transport)


def boundary(s, capsys, monkeypatch, mode=None):
    if mode:
        monkeypatch.setenv("HF_TOKEN", TOKEN)
    argv = ["--cell", s.selected, "--reviewed-source-sha", SOURCE, "--output", str(s.root)]
    try:
        code = retention.main([*argv, *([] if mode is None else [mode])],
                              _test_api=s.api, _test_transport=s.transport)
    finally:
        if mode:
            monkeypatch.delenv("HF_TOKEN")
    captured = capsys.readouterr()
    for private in (TOKEN, s.api.repo, str(s.host), "DO NOT RETAIN", "synthetic-result.txt"):
        assert private not in captured.out + captured.err
    record = json.loads(captured.out) if captured.out else None
    if record:
        assert record["model_requested"] is record["grading_launched"] is record["grade_ready"] is False
    return code, record


def prepare(s):
    assert cli(s, "--check-inputs") == 0


def admitted(s, capsys, monkeypatch):
    prepare(s)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 0


def finalized(s, capsys, monkeypatch, expected=0):
    admitted(s, capsys, monkeypatch)
    assert cli(s, "--resume", "--execute") == expected


def cell_root(s):
    return s.root / "cells" / s.selected


def select_fresh(s, monkeypatch, ordinal=7, *, same_cell=False):
    old = read_plan(s)
    key = s.selected if same_cell else old["order"][ordinal]
    s.root = s.host / ("new-host-" + str(ordinal) + ("-replay" if same_cell else ""))
    s.envelope = s.host / (s.root.name + "-completion.json")
    for option, value in (("--output", str(s.root)), ("--completion-out", str(s.envelope)), ("--cell", key)):
        s.argv[s.argv.index(option) + 1] = value
    s.selected = key
    s.transport = RetainedChildren(s.sources, s.ids, s.api)
    monkeypatch.setenv("GITHUB_RUN_ID", str(1235 + ordinal))
    monkeypatch.setenv("RUNNER_NAME", "synthetic-other-live-host")
    prepare(s)


def test_retention_default_plan_is_local_no_token_or_network(case, capsys, monkeypatch):
    class NoToken(dict):
        def get(self, key, *args):
            assert key not in TOKEN_KEYS
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoToken(os.environ))
    assert cli(case) == 0
    assert boundary(case, capsys, monkeypatch)[1]["outcome"] == "plan_only"
    assert case.api.calls == case.transport.calls == []
    assert not (cell_root(case) / retention.ADMISSION_RESERVED).exists()
    assert len(read_plan(case)["cells"]) == 30


def test_retention_execute_without_remote_admission_refuses_before_child(case):
    assert cli(case, "--execute") == 2
    assert case.transport.calls == case.api.calls == []
    assert pilot._load(case.envelope)["status"] == "unresolved"


def test_retention_real_dispatch_deadline_bytes_and_actual_commit_binding(case, capsys, monkeypatch):
    s = case
    finalized(s, capsys, monkeypatch)
    plan, state = read_plan(s), read_state(s, s.selected)
    selected = next(cell for cell in plan["cells"] if cell["cell_id"] == s.selected)
    snapshot = output.prepare(root=s.root, campaign=ci.CAMPAIGN, cell_id=s.selected,
                             source_sha=SOURCE, config_sha=selected["config_sha256"])
    before = {name: data for name, data in snapshot.files.items()}
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    receipt = retention._read(cell_root(s) / retention.TERMINAL_RECEIPT)
    claim = retention._read(cell_root(s) / retention.ADMISSION_RECEIPT)
    assert s.api.parents[receipt["output_commit"]] == claim["returned_commit"]
    assert s.api.parents[receipt["terminal_commit"]] == receipt["output_commit"]
    prefix = retention._paths(selected)[2]
    assert all(s.api.trees[receipt["output_commit"]][prefix + "/" + name] == data for name, data in before.items())
    assert read_state(s, s.selected) == state
    assert s.api.events == ["admission", "child", "child", "output", "terminal"]
    assert set(s.api.trees[s.api.head]) == {retention._paths(selected)[0], retention._paths(selected)[1],
        *(prefix + "/" + name for name in snapshot.files), prefix + "/" + output.MANIFEST}
    deadline = pilot._load(s.root / selected["roles"]["deadline"] / "deadlines.json")["cells"][selected["task_id"]]
    assert deadline["expires_unix"] - deadline["started_unix"] == 10800
    assert len(deadline["attempts"]) == 1
    assert s.transport.forwarded[1][2] == 10860
    assert len(plan["order"]) == 30 and [row["condition"] + str(row["repetition"]) for row in plan["cells"][:6]] == ["A1", "B1", "C1", "C2", "B2", "A2"]
    assert all(read_state(s, cell["cell_id"]) == pilot._cell_state(plan, cell) for cell in plan["cells"] if cell != selected)
    public = pilot._load(s.envelope)
    assert ci.validate_completion(public) == public and public["other_cells_not_run"] == 29
    assert public["receipt"] is None and public["http_request_count"] is None


@pytest.mark.parametrize("outcome,stop,partial,expected,status", [
    ("filtered", None, False, 1, "failed"), ("missing_result", None, False, 1, "failed"),
    ("missing_result", "timeout", False, 1, "stopped"), ("success", "timeout", True, 1, "stopped"),
    ("success", None, True, 0, "succeeded"),
])
def test_retention_preserves_failed_stopped_partial_and_missing(case, capsys, monkeypatch, outcome, stop, partial, expected, status):
    s = case
    s.transport.outcomes[s.selected], s.transport.stop, s.transport.partial = outcome, stop, partial
    finalized(s, capsys, monkeypatch, expected)
    before = read_state(s, s.selected)
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    selected = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    terminal = json.loads(s.api.trees[s.api.head][retention._paths(selected)[1]])
    projected = terminal["completion"]
    manifest = json.loads(s.api.trees[terminal["output_commit"]][retention._paths(selected)[2] + "/" + output.MANIFEST])
    assert projected["status"] == manifest["status"] == status and read_state(s, s.selected) == before
    if partial:
        assert projected["receipt"]["status"] == "partial"
        assert projected["receipt"]["usage"]["output_tokens"] == 3  # Reasoning is included, not 3+2.
        assert projected["receipt"]["usage"]["reasoning_tokens"] == 2
        assert projected["receipt"]["estimated_cost_usd"] is None
        assert projected["receipt"]["known_cost_usd"] == 0.01
    if outcome == "missing_result":
        assert manifest["files"] == [] and "bound_inference_result" in manifest["missing"]
        assert projected["receipt"] is projected["artifacts"]["result"] is None
    assert manifest["grade_ready"] is False and projected["denominator"] == 30


@pytest.mark.parametrize("change", ["public", "foreign", "bootstrap", "skip", "duplicate", "output_prefix", "cas", "missing_auth"])
def test_retention_admission_refusals_precede_inference(case, capsys, monkeypatch, change):
    s = case
    if change == "skip":
        s.selected = s.ids[1] + "_C_r1"
        s.argv[s.argv.index("--cell") + 1] = s.selected
    prepare(s)
    cell = next(row for row in read_plan(s)["cells"] if row["cell_id"] == s.selected)
    if change == "public":
        s.api.private = False
    elif change == "foreign":
        s.api.id_matches = False
    elif change == "bootstrap":
        s.api.head = "e" * 40
        s.api.trees[s.api.head], s.api.writers[s.api.head] = {}, {}
    elif change in {"duplicate", "output_prefix"}:
        name = retention._paths(cell)[0] if change == "duplicate" else retention._paths(cell)[2] + "/unresolved"
        s.api.trees[s.api.head][name] = b"incomplete still forbids replay"
        s.api.writers[s.api.head][name] = s.api.head
    elif change == "cas":
        s.api.move_before_commit = True
    if change == "missing_auth":
        code = retention.main(["--cell", s.selected, "--reviewed-source-sha", SOURCE, "--output", str(s.root), "--admit"],
                              _test_api=s.api, _test_transport=s.transport)
        assert code == 2 and not s.api.calls
    else:
        assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
    assert s.api.commits == (["admission"] if change == "cas" else [])
    assert cli(s, "--resume", "--execute") == 2 and not s.transport.calls


@pytest.mark.parametrize("change", ["host", "run", "config", "input", "receipt", "token"])
def test_retention_token_free_execution_gate_is_bound_to_current_host_and_bytes(case, capsys, monkeypatch, change):
    s = case
    admitted(s, capsys, monkeypatch)
    if change == "host":
        monkeypatch.setenv("RUNNER_NAME", "different")
    elif change == "run":
        monkeypatch.setenv("GITHUB_RUN_ID", "9999")
    elif change == "config":
        (cell_root(s) / "config.json").write_bytes(b"changed")
    elif change == "input":
        s.sources.parquet.write_bytes(b"changed")
    elif change == "receipt":
        record = retention._read(cell_root(s) / retention.ADMISSION_RECEIPT)
        record["outcome"] = "unresolved"
        (cell_root(s) / retention.ADMISSION_RECEIPT).write_bytes(retention._encoded(record))
    else:
        monkeypatch.setenv("HF_TOKEN", TOKEN)
    assert cli(s, "--resume", "--execute") == 2 and not s.transport.calls


def test_retention_child_boundary_strips_input_tokens_even_for_other_local_callers(case, monkeypatch):
    # Check the actual child constructor separately from the stricter CI gate.
    s = case
    prepare(s)
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    for key in TOKEN_KEYS:
        monkeypatch.setenv(key, "synthetic-forbidden")
    seen = []

    def process(command, **kwargs):
        seen.append(kwargs["env"])
        assert not TOKEN_KEYS.intersection(kwargs["env"])
        return SimpleNamespace(returncode=0)

    transport = pilot.LocalTransport()
    monkeypatch.setattr(transport, "process", process)
    with (s.root / "lock").open("rb") as lock:
        assert transport.child(stage="prepare", cell=cell, root=s.root, lock=lock.fileno(), timeout=300) == 0
    assert len(seen) == 1


@pytest.mark.parametrize("boundary_kind", ["admission", "output", "terminal"])
@pytest.mark.parametrize("failure", ["fail", "lost", "bad_oid", "ignore"])
def test_retention_mutation_failure_keeps_reservations_and_never_replays(case, capsys, monkeypatch, boundary_kind, failure):
    s = case
    if boundary_kind == "admission":
        prepare(s)
        setattr(s.api, failure, boundary_kind)
        assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
        receipt_name, reserved_name, mode = retention.ADMISSION_RECEIPT, retention.ADMISSION_RESERVED, "--admit"
    else:
        finalized(s, capsys, monkeypatch)
        setattr(s.api, failure, boundary_kind)
        assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
        receipt_name, reserved_name, mode = retention.TERMINAL_RECEIPT, retention.TERMINAL_RESERVED, "--retain"
    receipt = (cell_root(s) / receipt_name).read_bytes()
    reserved = (cell_root(s) / reserved_name).read_bytes()
    assert json.loads(receipt)["outcome"] == "unresolved"
    before = (len(s.api.commits), len(s.transport.calls))
    assert boundary(s, capsys, monkeypatch, mode)[0] == 2
    assert (len(s.api.commits), len(s.transport.calls)) == before
    assert (cell_root(s) / receipt_name).read_bytes() == receipt
    assert (cell_root(s) / reserved_name).read_bytes() == reserved


@pytest.mark.parametrize("outcome", ["success", "filtered", "missing_result"])
@pytest.mark.parametrize("lost_response", [False, True])
def test_retention_lost_terminal_response_valid_server_state_admits_only_successor(case, capsys, monkeypatch, outcome, lost_response):
    s = case
    s.transport.outcomes[s.selected] = outcome
    finalized(s, capsys, monkeypatch, expected=0 if outcome == "success" else 1)
    s.api.lost = "terminal" if lost_response else None
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == (2 if lost_response else 0)
    prior = cell_root(s) / retention.TERMINAL_RECEIPT
    original = prior.read_bytes()
    assert json.loads(original)["outcome"] == ("unresolved" if lost_response else "acknowledged")
    assert (json.loads(original)["terminal_commit"] is None) == lost_response
    output_receipt = retention._read(cell_root(s) / output.RECEIPT)
    assert output_receipt["outcome"] == "acknowledged"
    preceding_tip = s.api.head
    select_fresh(s, monkeypatch)
    s.api.lost = None
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 0
    claim = retention._read(cell_root(s) / retention.ADMISSION_RECEIPT)
    assert claim["claim"]["expected_parent"] == preceding_tip
    assert claim["claim"]["binding"]["ordinal"] == 7
    observed = retention._read(cell_root(s) / retention.SERVER_OBSERVATION)
    assert observed["observation"] == "verified_server_terminal_state"
    assert observed["writer_response_delivery"] == "not_asserted" and prior.read_bytes() == original
    assert not s.transport.calls and s.api.commits == ["admission", "output", "terminal", "admission"]


@pytest.mark.parametrize("change", ["ambiguous_output", "missing_terminal", "cleanup", "foreign", "config", "inputs",
    "order", "source", "manifest_hash", "output_bytes", "claim_bytes", "acknowledged", "unknown_tip", "read_failed", "same_cell"])
def test_retention_invalid_predecessor_or_same_cell_never_advances(case, capsys, monkeypatch, change):
    s = case
    finalized(s, capsys, monkeypatch)
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    if change == "ambiguous_output":
        s.api.lost = "output"
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == (2 if change == "ambiguous_output" else 0)
    claim_path, terminal_path, prefix = retention._paths(cell)
    if change not in {"ambiguous_output", "same_cell", "read_failed"}:
        terminal = json.loads(s.api.trees[s.api.head][terminal_path])
        if change == "missing_terminal":
            del s.api.trees[s.api.head][terminal_path]
        elif change == "unknown_tip":
            tip = "f" * 40
            s.api.trees[tip], s.api.writers[tip] = dict(s.api.trees[s.api.head]), dict(s.api.writers[s.api.head])
            s.api.head = tip
        elif change == "output_bytes":
            name = next(row["path"] for row in terminal["output_objects"] if row["path"].endswith(".txt"))
            s.api.trees[terminal["output_commit"]][name] += b"changed"
        elif change == "claim_bytes":
            s.api.trees[terminal["claim_commit"]][claim_path] += b" "
        else:
            if change in {"source", "config", "inputs", "order", "foreign", "cleanup"}:
                field = {"source": "source_sha", "config": "config_sha256", "inputs": "verified_inputs_sha256",
                         "order": "order_sha256", "foreign": "cell_id", "cleanup": "cleanup_confirmed"}[change]
                terminal["completion"][field] = False if change == "cleanup" else (
                    s.ids[2] + "_A_r1" if change == "foreign" else "f" * (40 if change == "source" else 64))
            elif change == "manifest_hash":
                terminal["manifest_identity"]["sha256"] = "f" * 64
            else:
                terminal["publication_acknowledged"] = False
            s.api.trees[s.api.head][terminal_path] = retention._encoded(terminal)
    before = len(s.api.commits)
    select_fresh(s, monkeypatch, same_cell=change == "same_cell")
    s.api.read_fail = change == "read_failed"
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
    assert len(s.api.commits) == before and not s.transport.calls
    assert not (cell_root(s) / retention.SERVER_OBSERVATION).exists()


def test_retention_unconfirmed_cleanup_and_changed_output_refuse_before_network(case, capsys, monkeypatch):
    s = case
    s.transport.stop = "unresolved"
    finalized(s, capsys, monkeypatch, expected=2)
    before = len(s.api.calls)
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    assert len(s.api.calls) == before and s.api.commits == ["admission"]


@pytest.mark.parametrize("change", ["public", "parent"])
def test_retention_output_rechecks_private_identity_and_exact_admission_parent(case, capsys, monkeypatch, change):
    s = case
    finalized(s, capsys, monkeypatch)
    if change == "public":
        s.api.private = False
    else:
        tip = "d" * 40
        s.api.trees[tip], s.api.writers[tip] = dict(s.api.trees[s.api.head]), dict(s.api.writers[s.api.head])
        s.api.head = tip
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    assert s.api.commits == ["admission"]
    assert retention._read(cell_root(s) / output.RECEIPT)["outcome"] == "refused"


def test_retention_raw_errors_are_redacted_and_no_response_status_is_not_guessed(case, capsys, monkeypatch):
    s = case
    prepare(s)

    def unavailable(**kwargs):
        raise RuntimeError(TOKEN + s.api.repo + str(s.host) + "?signed=DO_NOT_REPORT")

    monkeypatch.setattr(s.api, "repo_info", unavailable)
    code, record = boundary(s, capsys, monkeypatch, "--admit")
    assert code == 2 and record["reason"] == "hf_operation_failed" and record["http_status"] is None
    assert not s.api.commits and not s.transport.calls


def test_retention_target_fingerprint_refuses_before_credential_or_network(case, capsys, monkeypatch):
    original = pilot.load_plan

    def changed(path=None):
        result = original() if path is None else original(path)
        if path == pilot.ROOT / pilot.CODEX_TEMPLATE:
            result["data"]["source"] = "synthetic-foreign/target"
        return result

    monkeypatch.setattr(pilot, "load_plan", changed)
    assert boundary(case, capsys, monkeypatch)[0] == 2
    assert not case.api.calls


@pytest.mark.parametrize("change", ["result", "deliverable", "ledger"])
def test_retention_current_byte_mismatch_refuses_before_publication(case, capsys, monkeypatch, change):
    s = case
    finalized(s, capsys, monkeypatch)
    cell = read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    if change == "deliverable":
        path = s.root / cell["roles"]["checkout"] / "batch-runner/workspace/upload" / f"deliverable_files/{cell['task_id']}/synthetic-result.txt"
    else:
        path = s.root / cell["roles"][change]
    path.write_bytes(path.read_bytes() + b"changed")
    before = len(s.api.calls)
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2 and len(s.api.calls) == before


def test_retention_conflicting_modes_refuse_before_token(case, capsys):
    assert retention.main(["--cell", case.selected, "--reviewed-source-sha", SOURCE, "--output", str(case.root),
        "--admit", "--retain"], _test_api=case.api, _test_transport=case.transport) == 2
    assert not case.api.calls and "invalid_arguments" in capsys.readouterr().err


def test_retention_workflow_token_scopes_and_existing_controls():
    document = yaml.safe_load((pilot.ROOT / ci.WORKFLOW).read_bytes())
    triggers = document.get("on", document.get(True))
    assert len(triggers["workflow_dispatch"]["inputs"]) == 10
    assert document["permissions"] == {"contents": "read", "id-token": "write"}
    assert document["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    job = document["jobs"]["cell"]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 240
    steps = job["steps"]
    ids = {step.get("id"): step for step in steps}
    assert steps.index(ids["intake"]) < steps.index(ids["admission"]) < steps.index(ids["execution"]) < steps.index(ids["retention"])
    for key, flag in (("admission", "--admit"), ("retention", "--retain")):
        assert ids[key]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
        assert ids[key]["timeout-minutes"] == 3 and "kill-after=5s 130s" in ids[key]["run"] and flag in ids[key]["run"]
        assert all(guard in ids[key]["if"] for guard in ("inputs.execute", "!inputs.input_check", "!inputs.output_target_check", "!inputs.output_target_setup"))
    assert "steps.admission.outputs.admitted == 'true'" in ids["execution"]["if"]
    assert ids["retention"]["if"].startswith("always()")
    assert not TOKEN_KEYS.intersection(ids["execution"]["env"]) and not TOKEN_KEYS.intersection(job["env"])
    public = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(public) == 1 and public[0]["with"]["path"] == "${{ runner.temp }}/budget-pilot-ci-completion.json"
    assert all("step8" not in step.get("run", "") for step in steps)
    assert output.PUBLICATION_SECONDS == 120 and output.REQUEST_SECONDS == 30
