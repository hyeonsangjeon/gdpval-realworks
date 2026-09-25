"""Real CLI/compiler/byte/publication gates; synthetic cell facts and fake HF.

No pipeline child, original input, credential store, HF request or grader is
run. The fake transport is not evidence that an output target exists or works.
"""

from __future__ import annotations

import copy
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from types import SimpleNamespace

import httpx
from huggingface_hub import RepoFolder
import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
from core.cost_receipts import CostReceipt
from core.inference_manifest import bind_deliverable_file_records
from core.result_fingerprint import inference_result_fingerprint

SOURCE = "9cb1c0d84f299f610ec98c90f3bac9ff9cbbdc75"
REPO = "synthetic-owner/private-cell-outputs"
PARENT = "8" * 40
COMMIT = "9" * 40
TOKEN = "hf_SYNTHETIC_NEVER_A_CREDENTIAL"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("output regression crossed a live boundary")

    for target, names in (
        (pilot, ("dispatch", "_source_snapshot", "_step0_bytes")),
        (pilot.LocalTransport, ("require_source", "require_execution", "checkout", "child", "inputs")),
        (ci, ("_require_ci_context",)), (subprocess, ("Popen", "run")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (time, ("sleep",)),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    monkeypatch.delenv("HF_TOKEN", raising=False)


def folder(path):
    value = object.__new__(RepoFolder)
    value.path = path
    return value


class FakeHF:
    def __init__(self, cell_root):
        self.cell_root = cell_root
        self.calls, self.uploaded = [], {}
        self.private, self.repo_id, self.parent, self.commit = True, REPO, PARENT, COMMIT
        self.paths, self.fail_at, self.failure, self.post_sha = [], None, None, COMMIT
        self.ignore = False

    def call(self, stage, kwargs):
        reservation = json.loads((self.cell_root / output.RESERVATION).read_bytes())
        assert reservation["outcome"] == "unresolved"
        assert reservation["output_repository"] == REPO and reservation["expected_parent"] == PARENT
        assert TOKEN not in json.dumps(reservation)
        self.calls.append((stage, kwargs))
        assert kwargs["repo_id"] == REPO and kwargs["repo_type"] == "dataset" and kwargs["token"] == TOKEN
        if self.fail_at == stage:
            raise self.failure

    def repo_info(self, **kwargs):
        stage = "target_metadata" if kwargs["revision"] == "main" else "commit_metadata"
        self.call(stage, kwargs)
        assert 0 < kwargs["timeout"] <= output.REQUEST_SECONDS
        return SimpleNamespace(id=self.repo_id, private=self.private,
                               sha=self.parent if stage == "target_metadata" else self.post_sha)

    def get_paths_info(self, **kwargs):
        self.call("prefix_check", kwargs)
        assert kwargs["revision"] == PARENT
        return self.paths

    def create_commit(self, **kwargs):
        self.call("commit", kwargs)
        assert kwargs["revision"] == "main" and kwargs["parent_commit"] == PARENT
        assert kwargs["num_threads"] == 1 and kwargs["run_as_future"] is False and kwargs["create_pr"] is False
        from huggingface_hub import CommitOperationAdd

        for operation in kwargs["operations"]:
            assert type(operation) is CommitOperationAdd
            # Buffered streams keep the SDK on its guarded HTTP/LFS path,
            # not a hidden Xet/native upload engine.
            assert isinstance(operation.path_or_fileobj, io.BufferedIOBase)
            assert operation.path_in_repo not in self.uploaded
            self.uploaded[operation.path_in_repo] = operation.path_or_fileobj.read()
            if self.ignore:
                operation._should_ignore = True
        return SimpleNamespace(oid=self.commit)


@pytest.fixture
def cell(tmp_path):
    # Real canonical compiler. Only finalized execution/input/instance evidence
    # is synthetic; this fixture does not run even a fake pipeline child.
    plan, _, specs = pilot.compile_pilot(ci.CAMPAIGN, SOURCE)
    selected = plan["cells"][7]
    plan["ci"] = {
        "registration_sha256": pilot._identity(pilot._read_bytes(ci.REGISTRATION))["sha256"],
        "selected_cell_id": selected["cell_id"],
        "host": {"policy": ci.HOST_POLICY, "instance_sha256": "c" * 64,
                 "workflow": ci.WORKFLOW, "workflow_sha": SOURCE, "run_attempt": 1},
    }
    root = tmp_path / "private-campaign"
    root.mkdir(mode=0o700)
    cell_root = root / "cells" / selected["cell_id"]
    cell_root.mkdir(parents=True, mode=0o700)
    (root / "lock").touch(mode=0o600)
    pilot._save(root / "plan.json", plan)
    pilot._save(root / "ready.json", {"plan_sha256": pilot._digest(plan)})
    pilot._save(root / "ci-inputs.json", {"plan_sha256": pilot._digest(plan),
                "files_sha256": "d" * 64, "source_projection_sha256": "e" * 64})
    owner = pilot._owner_state(pilot._digest(plan))
    owner.update(phase="reaped", cell_id=selected["cell_id"], stage="infer", pid=123, exit_code=0)
    pilot._save(root / "owned-child.json", owner)
    config = specs[selected["cell_id"]].config_json.encode()
    checkout = root / selected["roles"]["checkout"]
    pilot._write_file(cell_root / "config.json", config)
    pilot._write_file(checkout / "batch-runner/pilot-run.json", config)
    upload = checkout / "batch-runner/workspace/upload"
    name = f"deliverable_files/{selected['task_id']}/synthetic-report.txt"
    pilot._write_file(upload / name, b"Synthetic generated deliverable.\n")
    row = {"task_id": selected["task_id"], "status": "success", "deliverable_files": [name],
           "content": "Synthetic final answer, not a transcript.", "usage": None,
           "observability": {"preprocessors": []}}
    payload = {"experiment_id": selected["run_id"], "run_id": selected["run_id"],
               "publication_generation": "synthetic-generation", "condition_identity": "condition_a",
               "execution_mode": "codex_foundry", "ordered_task_ids": [selected["task_id"]],
               "prepared_fingerprint": "a" * 64, "model": "gpt-5.4", "results": [row]}
    state = pilot._cell_state(plan, selected)
    state.update(status="running", phase="executing", child_invocations=1,
                 prepared={"publication_generation": "synthetic-generation", "prepared_fingerprint": "a" * 64})

    def seal():
        payload["results"] = bind_deliverable_file_records(payload["results"], upload)
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
        (root / selected["roles"]["result"]).write_bytes((json.dumps(payload, indent=2) + "\n").encode())
        pilot._finish(root, selected, state, 0)
        pilot._save(root / selected["roles"]["checkpoint"], state)

    seal()
    # Deliberately adjacent, nonallowlisted bytes. None may enter operations.
    for excluded in (".env", "auth.json", "native-transcript.jsonl", "cost_ledger_condition_a.sqlite3", "original.parquet"):
        pilot._write_file(checkout / "batch-runner/workspace" / excluded, b"DO NOT PUBLISH")
    args = ["--campaign-root", str(root), "--campaign-id", ci.CAMPAIGN, "--cell", selected["cell_id"],
            "--reviewed-source-sha", SOURCE, "--expected-config-sha256", selected["config_sha256"]]
    return SimpleNamespace(root=root, cell_root=cell_root, cell=selected, plan=plan, state=state, payload=payload,
                           upload=upload, name=name, args=args, seal=seal, api=FakeHF(cell_root))


def invoke(cell, capsys, *, publish=False, extra=(), args=None):
    argv = list(cell.args if args is None else args)
    if publish:
        argv += ["--publish", "--output-repo", REPO, "--expected-parent", PARENT]
    code = output.main([*argv, *extra], _test_api=cell.api)
    captured = capsys.readouterr()
    for secret in (TOKEN, REPO, str(cell.root), "signed-secret", "DO NOT PUBLISH", "synthetic-report.txt"):
        assert secret not in captured.out + captured.err
    value = json.loads(captured.out) if captured.out else None
    if value is not None:
        assert value["grade_ready"] is False and value["workflow_wired"] is False
    else:
        assert code == 2 and "Private cell output refused:" in captured.err
    return code, value, captured.err


def test_output_default_plan_never_looks_up_token_or_constructs_client(cell, capsys, monkeypatch):
    class NoToken(dict):
        def get(self, key, *args):
            assert key not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"}
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoToken(os.environ))
    monkeypatch.setattr(output, "_hf_client", lambda *a: pytest.fail("plan constructed a client"))
    original = (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes()
    code, value, _ = invoke(cell, capsys)
    assert code == 0 and value["mode"] == "plan" and value["can_publish"] is True
    assert value["accounting"] == "missing" and value["missing"] == ["bound_ledger_export", "usage"]
    assert cell.api.calls == [] and not (cell.cell_root / output.RESERVATION).exists()
    assert (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes() == original


@pytest.mark.parametrize("flag,value", [
    ("--campaign-id", "budget_pilot_20260923_01"), ("--cell", "foreign_A_r1"),
    ("--reviewed-source-sha", "1" * 40), ("--reviewed-source-sha", "main"),
    ("--expected-config-sha256", "1" * 64),
])
def test_output_external_identity_refusal(cell, capsys, flag, value):
    args = cell.args.copy()
    args[args.index(flag) + 1] = value
    assert invoke(cell, capsys, args=args)[0] == 2
    assert cell.api.calls == []


@pytest.mark.parametrize("corruption", ["config", "ready", "plan", "input", "active", "owner", "result", "deliverable", "extra"])
def test_output_retained_binding_current_bytes_and_cleanup_refusal(cell, capsys, corruption):
    if corruption == "config":
        (cell.cell_root / "config.json").write_bytes(b"{}")
    elif corruption == "ready":
        pilot._save(cell.root / "ready.json", {"plan_sha256": "f" * 64})
    elif corruption == "plan":
        cell.plan["ci"]["selected_cell_id"] = cell.plan["cells"][0]["cell_id"]
        pilot._save(cell.root / "plan.json", cell.plan)
    elif corruption == "input":
        pilot._save(cell.root / "ci-inputs.json", {"files_sha256": "f" * 64})
    elif corruption == "active":
        cell.state.update(status="running", phase="executing")
        pilot._save(cell.root / cell.cell["roles"]["checkpoint"], cell.state)
    elif corruption == "owner":
        owner = pilot._load(cell.root / "owned-child.json")
        owner["tree_reaped"] = False
        pilot._save(cell.root / "owned-child.json", owner)
    elif corruption == "result":
        (cell.root / cell.cell["roles"]["result"]).write_bytes(b"{}")
    elif corruption == "deliverable":
        (cell.upload / cell.payload["results"][0]["deliverable_files"][0]).write_bytes(b"changed")
    else:
        pilot._write_file(cell.upload / cell.payload["results"][0]["deliverable_files"][0].replace(".txt", ".extra"), b"extra")
    assert invoke(cell, capsys)[0] == 2
    assert cell.api.calls == []


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "size", "total", "count"])
def test_output_unsafe_or_oversized_payload_refused(cell, capsys, monkeypatch, kind):
    path = cell.upload / cell.payload["results"][0]["deliverable_files"][0]
    if kind in {"symlink", "hardlink", "fifo"}:
        original = path.with_name("held-original")
        path.rename(original)
        if kind == "symlink":
            path.symlink_to(original)
        elif kind == "hardlink":
            os.link(original, path)
        else:
            os.mkfifo(path)
    elif kind == "size":
        monkeypatch.setattr(output, "MAX_FILE_BYTES", 2)
    elif kind == "total":
        monkeypatch.setattr(output, "MAX_TOTAL_BYTES", 2)
    else:
        monkeypatch.setattr(output, "MAX_FILES", 0)
    assert invoke(cell, capsys)[0] == 2 and cell.api.calls == []


@pytest.mark.parametrize("where", ["top", "row", "nested", "error", "receipt"])
def test_output_unsafe_record_fields_refused_without_rewriting(cell, capsys, where):
    if where == "top":
        cell.payload["raw_logs"] = "signed-secret"
    elif where == "row":
        cell.payload["results"][0]["auth"] = "signed-secret"
    elif where == "nested":
        cell.payload["results"][0]["observability"]["raw_extra"] = "signed-secret"
    elif where == "error":
        cell.payload["results"][0]["error"] = "ClientError token=signed-secret"
    else:
        receipt = CostReceipt.unavailable().as_dict()
        receipt["extra_metadata"] = "signed-secret"
        cell.payload["results"][0]["problem_solving_cost"] = receipt
    cell.seal()
    before = (cell.root / cell.cell["roles"]["result"]).read_bytes()
    assert invoke(cell, capsys)[0] == 2
    assert (cell.root / cell.cell["roles"]["result"]).read_bytes() == before and cell.api.calls == []


def add_ledger(cell, mutate=None):
    row = {key: None for key in output._CALL_COLUMNS}
    row.update(record_type="call", call_id="synthetic-call", run_id=cell.cell["run_id"], task_id=cell.cell["task_id"],
               stage="generation", retry_kind="none", state="settled", input_tokens=17, output_tokens=9,
               reasoning_tokens=4, missing_reasons=[], note=None)
    rows = [row]
    if mutate:
        mutate(rows)
    data = b"".join((json.dumps(item) + "\n").encode() for item in rows)
    ledger = cell.root / cell.cell["roles"]["ledger"]
    ledger.write_bytes(data)
    cell.payload["cost_ledger"] = {"path": Path(pilot.LEDGER).name, "sha256": pilot._identity(data)["sha256"]}
    cell.seal()
    return data


def test_output_atomic_payload_and_actual_receipt_are_bound_without_payload_changes(cell, capsys, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    ledger = add_ledger(cell)
    result = (cell.root / cell.cell["roles"]["result"]).read_bytes()
    original_state = (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes()
    code, public, _ = invoke(cell, capsys, publish=True)
    assert code == 0 and public["publication_outcome"] == "acknowledged"
    prefix = f"cell-outputs/{ci.CAMPAIGN}/{cell.cell['cell_id']}"
    uploaded = {key.removeprefix(prefix + "/"): value for key, value in cell.api.uploaded.items()}
    expected = {"step2_inference_results.json", Path(pilot.LEDGER).name, output.MANIFEST,
                *cell.payload["results"][0]["deliverable_files"]}
    assert set(uploaded) == expected
    assert uploaded["step2_inference_results.json"] == result and uploaded[Path(pilot.LEDGER).name] == ledger
    assert uploaded[cell.payload["results"][0]["deliverable_files"][0]] == b"Synthetic generated deliverable.\n"
    manifest = json.loads(uploaded[output.MANIFEST])
    assert COMMIT not in json.dumps(manifest) and REPO not in json.dumps(manifest)
    for record in manifest["files"]:
        assert {key: record[key] for key in ("sha256", "size")} == pilot._identity(uploaded[record["path"]])
    receipt = json.loads((cell.cell_root / output.RECEIPT).read_bytes())
    assert receipt["returned_commit"] == COMMIT and receipt["expected_parent"] == PARENT
    assert receipt["repository_at_commit"] == {"id": REPO, "sha": COMMIT, "private": True}
    assert receipt["manifest"] == pilot._identity(uploaded[output.MANIFEST])
    assert receipt["privacy_atomic_with_commit"] is False and receipt["download_verified"] is False
    assert (cell.cell_root / output.RECEIPT).stat().st_mode & 0o777 == 0o600
    assert (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes() == original_state
    assert [stage for stage, _ in cell.api.calls] == ["target_metadata", "prefix_check", "commit", "commit_metadata"]
    before_calls = len(cell.api.calls)
    assert invoke(cell, capsys, publish=True)[0] == 2 and len(cell.api.calls) == before_calls


@pytest.mark.parametrize("status", ["failed", "stopped"])
def test_output_final_status_and_partial_accounting_are_not_upgraded(cell, capsys, monkeypatch, status):
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    cell.payload["results"][0]["problem_solving_cost"] = CostReceipt(
        status="partial", known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"), model_calls=1,
        usage={"input_tokens": 17, "output_tokens": 9, "reasoning_tokens": 4},
        missing_reasons=("synthetic_missing_cost",),
    ).as_dict()
    cell.seal()
    cell.state.update(status=status, reason="child_timeout_partial_accounting", exit_code=None)
    pilot._save(cell.root / cell.cell["roles"]["checkpoint"], cell.state)
    before = (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes()
    code, public, _ = invoke(cell, capsys, publish=True)
    assert code == 0 and public["status"] == status and public["accounting"] == "partial"
    record = json.loads((cell.cell_root / output.RECEIPT).read_bytes())["cell"]
    assert record["status"] == status and record["timeout"] is True and record["exit_code"] is None
    assert record["receipt"]["usage"]["output_tokens"] == 9 and record["receipt"]["usage"]["reasoning_tokens"] == 4
    assert record["receipt"]["estimated_cost_usd"] is None
    assert (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes() == before


def test_output_missing_result_is_not_adopted_or_made_grade_ready(cell, capsys, monkeypatch):
    # An unrecorded late result is deliberately still on disk: do not adopt it.
    cell.state.update(status="stopped", reason="child_timeout_partial_accounting", result=None, artifacts={}, exit_code=None)
    pilot._save(cell.root / cell.cell["roles"]["checkpoint"], cell.state)
    code, plan, _ = invoke(cell, capsys)
    assert code == 0 and plan["can_publish"] is False and plan["files"] == []
    assert "bound_inference_result" in plan["missing"]
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    assert invoke(cell, capsys, publish=True)[0] == 2 and cell.api.calls == []
    assert not (cell.cell_root / output.RESERVATION).exists()


def test_output_empty_receipt_usage_remains_explicitly_missing(cell, capsys):
    cell.payload["results"][0]["problem_solving_cost"] = CostReceipt.unavailable().as_dict()
    cell.seal()
    code, plan, _ = invoke(cell, capsys)
    assert code == 0 and plan["accounting"] == "unavailable" and "usage" in plan["missing"]
    assert cell.api.calls == []


@pytest.mark.parametrize("mutation", [
    "type", "extra", "duplicate", "foreign", "nonfinite", "note", "identity", "reasons", "tokens", "hash", "stage",
])
def test_output_ledger_schema_and_cell_binding_remain_real(cell, capsys, mutation):
    def mutate(rows):
        row = rows[0]
        if mutation == "type":
            row["record_type"] = "raw_native_event"
        elif mutation == "extra":
            row["auth"] = "signed-secret"
        elif mutation == "duplicate":
            rows.append(copy.deepcopy(row))
        elif mutation == "foreign":
            row["run_id"] = "foreign-cell"
        elif mutation == "nonfinite":
            row["model_cost_usd"] = "NaN"
        elif mutation == "note":
            row["note"] = "raw signed-secret https://host/private"
        elif mutation == "identity":
            row["provider"] = {"arbitrary": "signed-secret"}
        elif mutation == "reasons":
            row["missing_reasons"] = ["https://host/?signed-secret"]
        elif mutation == "tokens":
            row["input_tokens"] = True
        elif mutation == "hash":
            row["request_sha256"] = "not-a-hash"
        else:
            row["stage"] = "not-a-stage"
    add_ledger(cell, mutate)
    assert invoke(cell, capsys)[0] == 2 and cell.api.calls == []


def test_output_runtime_ledger_record_keeps_unattributed_missing_cost(cell, capsys, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    def runtime(rows):
        rows.append({"record_type": "runtime", "entry_id": "synthetic-runtime", "run_id": cell.cell["run_id"],
                     "task_id": cell.cell["task_id"], "bucket": "problem_solving_cost", "runtime_kind": "synthetic",
                     "attribution": "unknown", "runtime_cost_usd": None, "missing_reasons": ["runtime_cost_unpriced"]})

    data = add_ledger(cell, runtime)
    assert invoke(cell, capsys, publish=True)[0] == 0
    assert next(value for name, value in cell.api.uploaded.items() if name.endswith(".jsonl")) == data


@pytest.mark.parametrize("partial", ["reservation", "receipt", "symlink"])
def test_output_existing_or_partial_publication_state_is_never_adopted(cell, capsys, monkeypatch, partial):
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    path = cell.cell_root / (output.RECEIPT if partial == "receipt" else output.RESERVATION)
    if partial == "symlink":
        path.symlink_to("absent-private-reservation")
    else:
        path.write_bytes(b"incomplete")
    assert invoke(cell, capsys, publish=True)[0] == 2 and cell.api.calls == []
    assert os.path.lexists(path)


@pytest.mark.parametrize("refusal", ["public", "missing", "foreign", "parent", "prefix", "ancestor", "no_token", "missing_args"])
def test_output_private_target_parent_prefix_and_explicit_request_guards(cell, capsys, monkeypatch, refusal):
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    if refusal == "public":
        cell.api.private = False
    elif refusal == "missing":
        cell.api.fail_at, cell.api.failure = "target_metadata", output.OutputPublicationRefused("hf_http_failed", 404)
    elif refusal == "foreign":
        cell.api.repo_id = "other/private"
    elif refusal == "parent":
        cell.api.parent = "7" * 40
    elif refusal == "prefix":
        cell.api.paths = [folder(f"cell-outputs/{ci.CAMPAIGN}/{cell.cell['cell_id']}")]
    elif refusal == "ancestor":
        cell.api.paths = [SimpleNamespace(path="cell-outputs", size=1)]
    elif refusal == "no_token":
        monkeypatch.delenv("HF_TOKEN")
    else:
        assert invoke(cell, capsys, extra=("--publish",))[0] == 2 and cell.api.calls == []
        return
    code, value, _ = invoke(cell, capsys, publish=True)
    assert code == 2 and not cell.api.uploaded
    assert not any(stage == "commit" for stage, _ in cell.api.calls)
    if value:
        assert value["publication_outcome"] == "refused"
        if refusal == "missing":
            assert value["http_status"] == 404 and value["stage"] == "target_metadata"


@pytest.mark.parametrize("failure", ["http", "lost", "malformed", "ignored", "postcheck", "interrupt", "timeout", "receipt"])
def test_output_failed_or_ambiguous_attempt_is_retained_and_never_replayed(cell, capsys, monkeypatch, failure):
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    if failure in {"http", "lost", "interrupt", "timeout"}:
        cell.api.fail_at = "commit"
        cell.api.failure = {"http": output.OutputPublicationRefused("hf_http_failed", 409),
                            "lost": OSError("token=signed-secret https://host/?signed-secret"),
                            "interrupt": KeyboardInterrupt(),
                            "timeout": output.OutputPublicationRefused("publication_timeout")}[failure]
    elif failure == "malformed":
        cell.api.commit = "not-a-commit"
    elif failure == "ignored":
        cell.api.ignore = True
    elif failure == "postcheck":
        cell.api.post_sha = "7" * 40
    else:
        real_write = output._write_no_clobber
        def fail_receipt(path, data):
            if path.name == output.RECEIPT:
                raise OSError("private receipt path signed-secret")
            real_write(path, data)
        monkeypatch.setattr(output, "_write_no_clobber", fail_receipt)
    code, value, _ = invoke(cell, capsys, publish=True)
    assert code == 2
    reserved = (cell.cell_root / output.RESERVATION).read_bytes()
    assert json.loads(reserved)["outcome"] == "unresolved"
    if value:
        assert value["publication_outcome"] == "unresolved"
        assert value["http_status"] == (409 if failure == "http" else None)
    if failure == "postcheck":
        assert json.loads((cell.cell_root / output.RECEIPT).read_bytes())["returned_commit"] == COMMIT
    before_calls = len(cell.api.calls)
    assert invoke(cell, capsys, publish=True)[0] == 2 and len(cell.api.calls) == before_calls
    assert (cell.cell_root / output.RESERVATION).read_bytes() == reserved


@pytest.mark.parametrize("failure", ["status", "connect", "body", "forwarding"])
def test_output_real_hf_client_guard_disables_internal_retries_and_leaks(monkeypatch, capsys, failure):
    from huggingface_hub import constants
    from huggingface_hub.utils import _http

    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", False)  # Fake HTTP boundary only.
    attempts = []
    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            raise httpx.ReadError("signed-secret")
            yield b""  # pragma: no cover

    def fake(self, request):
        attempts.append(request)
        assert all(0 < value <= output.REQUEST_SECONDS for value in request.extensions["timeout"].values())
        if failure == "connect":
            raise httpx.ConnectError("signed-secret")
        if failure == "body":
            return httpx.Response(200, stream=Broken())
        return httpx.Response(503, content=b"raw response signed-secret")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", fake)
    old_factory = _http._GLOBAL_CLIENT_FACTORY
    with pytest.raises(output.OutputPublicationRefused) as caught:
        with output._hf_client(TOKEN, time.monotonic() + output.PUBLICATION_SECONDS):
            url = "https://not-hf.invalid/object" if failure == "forwarding" else "https://huggingface.co/api/synthetic"
            _http.http_backoff("POST", url, headers={"authorization": "Bearer " + TOKEN})
    assert len(attempts) == (0 if failure == "forwarding" else 1)
    assert caught.value.http_status == (503 if failure == "status" else 200 if failure == "body" else None)
    assert _http._GLOBAL_CLIENT_FACTORY is old_factory
    assert "signed-secret" not in capsys.readouterr().err
