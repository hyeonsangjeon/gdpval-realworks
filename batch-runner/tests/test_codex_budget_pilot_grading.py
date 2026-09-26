"""One OFFLINE connector family. Synthetic outputs, HF, renderer and judge.

The compiler, terminal/claim/manifest checks, materializer, Step8 entry/schema,
hashes and CAS are exercised. Successful staging uses an explicit rename test
double; a separate native observation may refuse on this host. None of these
cases is a native-install, provider-authentication, paid-grade or HF observation.
"""

from __future__ import annotations

import copy
import ctypes
import errno
from functools import lru_cache
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest
import yaml
from huggingface_hub import CommitOperationAdd

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as connector
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_ci_input_intake as intake
import gpt54_v2_grading_input as primitives
import step8_grade as step8
from core.cost_receipts import CostReceipt, ledger_reference
from core.inference_manifest import bind_deliverable_file_records
from core.result_fingerprint import inference_result_fingerprint
from .test_codex_budget_pilot_retention import MemoryHF, TOKEN

SOURCE = "50676dd63b948bc8fa329f9b24871af75fe29c54"
CLAIM, OUTPUT, TERMINAL = "a" * 40, "b" * 40, "c" * 40
RENDERER = {"libreoffice_binary": "soffice", "libreoffice_version": "synthetic-fixed-renderer",
            "pymupdf_version": "synthetic-version"}


def _json(value):
    return (pilot._canonical_json(value) + "\n").encode()


def _ledger(run_id, task, stage="generation"):
    row = {key: None for key in output._CALL_COLUMNS}
    row.update(record_type="call", call_id="synthetic-call", run_id=run_id, task_id=task,
        stage=stage, retry_kind="none", state="reserved", missing_reasons=["usage_absent"], note=None)
    return _json(row)


class GradeHF(MemoryHF):
    """Immutable bytes/object history with a separate branch and real fake CAS."""

    def __init__(self):
        super().__init__()
        self.branches = {connector.BRANCH: retained.BOOTSTRAP}
        self.originals, self.events = {}, []
        self.main_snapshot = None
        self.branch_loss = False

    def record(self, name, kwargs):
        assert kwargs["repo_type"] == "dataset" and kwargs["token"] == TOKEN
        assert kwargs["repo_id"] == self.repo or (name == "download" and kwargs["repo_id"] == "openai/gdpval")
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}.intersection(os.environ)
        self.calls.append((name, kwargs.get("revision")))

    def repo_info(self, **kwargs):
        self.record("metadata", kwargs)
        assert 0 < kwargs["timeout"] <= output.REQUEST_SECONDS
        revision = kwargs["revision"]
        if revision == "main":
            revision = self.head
        elif revision == connector.BRANCH:
            if revision not in self.branches:
                raise output.OutputPublicationRefused("hf_revision_not_found", 404)
            revision = self.branches[revision]
        if revision not in self.trees:
            raise output.OutputPublicationRefused("hf_http_failed", 404)
        return SimpleNamespace(id=self.repo if self.id_matches else "synthetic-foreign/repo", private=self.private, sha=revision)

    def create_branch(self, **kwargs):
        self.record("branch", kwargs)
        assert kwargs["branch"] == connector.BRANCH and kwargs["revision"] == retained.BOOTSTRAP
        assert kwargs["exist_ok"] is False and connector.BRANCH not in self.branches
        self.branches[connector.BRANCH] = kwargs["revision"]
        if self.branch_loss:
            raise output.OutputPublicationRefused("hf_transport_failed")

    def hf_hub_download(self, **kwargs):
        self.record("download", kwargs)
        assert output._hash(kwargs["revision"], 40)
        assert kwargs["force_download"] is True and kwargs["local_files_only"] is False
        assert 0 < kwargs["etag_timeout"] <= output.REQUEST_SECONDS
        if self.read_fail:
            raise output.OutputPublicationRefused("hf_http_failed", 503)
        path = Path(kwargs["cache_dir"]) / "buffer"
        if kwargs["repo_id"] == "openai/gdpval":
            data = self.originals[(kwargs["revision"], kwargs["filename"])]
        else:
            data = self.trees[kwargs["revision"]][kwargs["filename"]]
        output._write_no_clobber(path, data)
        return str(path)

    def create_commit(self, **kwargs):
        self.record("commit", kwargs)
        assert kwargs["revision"] == connector.BRANCH, "grading must NEVER write inference main"
        assert kwargs["num_threads"] == 1 and kwargs["run_as_future"] is False and kwargs["create_pr"] is False
        parent = self.branches[connector.BRANCH]
        records = {}
        for operation in kwargs["operations"]:
            assert type(operation) is CommitOperationAdd
            records[operation.path_in_repo] = operation.path_or_fileobj.read()
        kind = "grade_claim" if any(name.endswith("/claim.json") for name in records) else "grade_output"
        self.events.append(kind)
        if self.move_before_commit or kwargs["parent_commit"] != parent:
            raise output.OutputPublicationRefused("hf_http_failed", 409)
        if self.fail == kind:
            raise RuntimeError("private-secret " + TOKEN + " https://private.invalid/?signed=secret")
        assert not set(records).intersection(self.trees[parent]), "no overwrites"
        revision = f"{len(self.parents) + 100:040x}"
        self.trees[revision] = {**self.trees[parent], **records}
        self.writers[revision] = {**self.writers[parent], **{path: revision for path in records}}
        self.parents[revision] = parent
        self.branches[connector.BRANCH] = revision
        if self.lost == kind:
            raise output.OutputPublicationRefused("hf_transport_failed")
        return SimpleNamespace(oid=revision)

    def seed(self, revision, parent, files):
        self.trees[revision] = {**self.trees[parent], **files}
        self.writers[revision] = {**self.writers[parent], **{path: revision for path in files}}
        self.parents[revision] = parent

    def assert_main_unchanged(self):
        assert self.head == TERMINAL and self.trees[self.head] == self.main_snapshot
        assert not any(name == "commit" and revision == "main" for name, revision in self.calls)


@pytest.fixture(scope="module")
def compilation():
    return pilot.compile_pilot(ci.CAMPAIGN, SOURCE)


@pytest.fixture(autouse=True)
def boundaries(monkeypatch):
    from huggingface_hub import HfApi, hf_api
    from huggingface_hub.utils import _auth, _headers
    from core import azure_ai_clients, codex_runner, codex_azure_token

    def blocked(*args, **kwargs):
        raise AssertionError("offline grading connector crossed a live boundary")

    for target, names in (
        (subprocess, ("run", "Popen", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (HfApi, ("repo_info", "create_commit", "create_branch", "hf_hub_download", "create_repo", "whoami")),
        (_auth, ("get_token", "_get_token_from_file", "_get_token_from_environment", "_get_token_from_google_colab")),
        (_headers, ("get_token",)),
        (hf_api, ("_get_token_from_file", "_get_token_from_environment", "_get_token_from_google_colab")),
        (pilot, ("dispatch",)), (codex_azure_token, ("main",)),
    ):
        for name in names:
            monkeypatch.setattr(target, name, blocked)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI, azure_ai_clients.AzureOpenAI,
                        azure_ai_clients.DefaultAzureCredential, codex_runner.CodexAgentRunner, step8.Grader):
        monkeypatch.setattr(constructor, "__init__", blocked)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("HF_DATASETS_OFFLINE", "1")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr("core.tools.get_renderer_fingerprint", lambda: RENDERER.copy())


@pytest.fixture(scope="module")
def compiled_cache():
    # Cache only genuine deterministic compiles, to keep this family bounded.
    return lru_cache(maxsize=32)(adapter.compile_cell_grading_plan)


@pytest.fixture
def case(tmp_path, monkeypatch, compilation, compiled_cache):
    original_compile = pilot.compile_pilot
    monkeypatch.setattr(pilot, "compile_pilot", lambda campaign, source: copy.deepcopy(compilation)
                        if (campaign, source) == (ci.CAMPAIGN, SOURCE) else original_compile(campaign, source))
    monkeypatch.setattr(adapter, "compile_cell_grading_plan", lambda *args: copy.deepcopy(compiled_cache(*args)))
    context = connector.compile_request("pilot/" + compilation[0]["order"][ci.FIRST_CELL_ORDINAL], SOURCE, TERMINAL)
    api = GradeHF()
    root = tmp_path / "private-grade"
    state = SimpleNamespace(root=root, context=context, api=api, files={}, status="success")
    env = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE, "PILOT_WORKFLOW_SHA": SOURCE,
        "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + connector.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": "12345", "GITHUB_JOB": "pilot-live", "PILOT_GRADE_PAID_APPROVAL": "true",
        "PILOT_GRADE_DRY_RUN": "false", "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false",
        "GRADE_TASKS_LIMIT": "0", "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0",
        "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1",
        "PILOT_GRADE_APPROVAL_RESULT": "success",
        "PILOT_GRADE_APPROVAL_REQUEST_SHA256": connector._context_approval(context, {"id": "12345", "attempt": 1}),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("HF_TOKEN", TOKEN)

    def fixture_rename(src_fd, src, dest_fd, dest, flags):
        assert flags == 1
        if os.path.lexists(Path(f"/proc/self/fd/{dest_fd}") / os.fsdecode(dest)):
            ctypes.set_errno(errno.EEXIST)
            return -1
        os.rename(src, dest, src_dir_fd=src_fd, dst_dir_fd=dest_fd)
        return 0

    state.native_rename = primitives._no_replace_rename
    monkeypatch.setattr(primitives, "_no_replace_rename", lambda: fixture_rename)
    _seed_outputs(state, tmp_path)
    _synthetic_rubric(state, monkeypatch)
    state.transport = Child(state)
    return state


def _seed_outputs(case, tmp_path, *, failed=False, missing=False, ledger=True, extra_deliverable=False,
                  producer_row=None, producer_ledger=None, reason=None):
    context, api = case.context, case.api
    cell = context.cell
    config = json.loads(context.grading.dispatch.runs[0].config_json)
    upload = tmp_path / ("synthetic-error-deliverables" if failed else "synthetic-deliverables")
    upload.mkdir(exist_ok=True)
    name = f"deliverable_files/{cell['task_id']}/answer.txt"
    names = [name] + ([f"deliverable_files/{cell['task_id']}/supplement.txt"] if extra_deliverable else [])
    if not failed:
        (upload / name).parent.mkdir(parents=True, exist_ok=True)
        (upload / name).write_bytes(b"synthetic generated answer\r\n\x00unchanged\n")
        if extra_deliverable:
            (upload / names[1]).write_bytes(b"synthetic supplement; not a historical deliverable\n")
    rows = bind_deliverable_file_records([producer_row] if producer_row is not None else [{
        "task_id": cell["task_id"], "status": "error" if failed else "success", "model": "gpt-5.4",
        "deliverable_files": [] if failed else names, "content": None if failed else "synthetic answer",
        "deliverable_text": None if failed else "synthetic answer", "usage": None, "problem_solving_cost": None,
        "observability": {"preprocessors": []}, "latency_ms": 1.0,
        "timestamp": "2026-09-23T00:00:00Z", "error": "synthetic_failure" if failed else None,
    }], upload)
    ledger_data = _ledger(cell["run_id"], cell["task_id"]) if producer_ledger is None else producer_ledger
    payload = {
        "experiment_id": cell["run_id"], "experiment_name": config["experiment"]["name"],
        "source": config["data"]["source"], "condition": config["condition_a"]["name"], "condition_identity": "condition_a",
        "run_id": cell["run_id"], "publication_generation": cell["run_id"] + ":local:" + "d" * 32,
        "execution_mode": config["execution"]["mode"], "ordered_task_ids": [cell["task_id"]],
        "prepared_fingerprint": "d" * 64, "model": "gpt-5.4", "started_at": "2026-09-23T00:00:00Z",
        "completed_at": "2026-09-23T00:01:00Z", "resume_rounds_used": 0, "results": rows,
        "summary": {"total": 1, "success": 0 if failed else 1, "error": 1 if failed else 0, "qa_failed": 0},
        "cost_ledger": ledger_reference(Path(pilot.LEDGER).name, hashlib.sha256(ledger_data).hexdigest()) if ledger else None,
    }
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    files = {} if missing else {"step2_inference_results.json": _json(payload)}
    roles = {"step2_inference_results.json": "inference_result"}
    if not missing and not failed:
        for name in names:
            files[name] = (upload / name).read_bytes()
            roles[name] = "generated_deliverable"
    if not missing and ledger:
        files[Path(pilot.LEDGER).name] = ledger_data
        roles[Path(pilot.LEDGER).name] = "cost_ledger_export"
    inputs = {"files_sha256": "4" * 64, "source_projection_sha256": "5" * 64}
    host = {"policy": ci.HOST_POLICY, "instance_sha256": "6" * 64, "workflow": ci.WORKFLOW,
            "workflow_sha": SOURCE, "run_attempt": 1}
    plan = {**context.plan, "ci": {"registration_sha256": hashlib.sha256(pilot._read_bytes(ci.REGISTRATION)).hexdigest(),
            "selected_cell_id": cell["cell_id"], "host": host}}
    binding = retained._binding(plan, cell, inputs, run={"id": "999", "job": "cell", "attempt": 1})
    claim = {"format": retained.CLAIM_FORMAT, "binding": binding, "expected_parent": retained.BOOTSTRAP,
             "predecessor": None, "model_result": False, "grade": False}
    state = {"receipt": None, "status": "failed" if failed or missing else "succeeded", "reason": reason,
        "child_invocations": 1, "exit_code": 1 if failed or missing else 0,
        "result": None if missing else pilot._identity(files["step2_inference_results.json"]),
        "artifacts": {"ledger": pilot._identity(ledger_data) if ledger and not missing else None,
                      "deliverable_files": [pilot._identity(files[name]) for name in names]
                          if not failed and not missing else []}}
    completed = ci.completion(plan, cell, execute=True, state=state, inputs=inputs, cleanup=True)
    fields = ("campaign_id", "cell_id", "source_sha", "config_sha256", "plan_sha256", "order_sha256",
              "verified_inputs_sha256", "host_policy_sha256", "status", "exit_code", "reason", "timeout", "cleanup_confirmed", "receipt")
    manifest = {key: completed[key] for key in fields}
    manifest.update(format=output.FORMAT, inference_branch=retained.BRANCH,
        grade_ready=False, grading_launched=False, accounting="missing",
        files=[{"role": roles[name], "path": name, **pilot._identity(data)} for name, data in sorted(files.items())],
        missing=(["bound_inference_result", "validated_deliverables", "bound_ledger_export"] if missing else
                 ["bound_ledger_export"] if not ledger else []) + ["usage"])
    retained._manifest(manifest, completed, cell)
    claim_path, terminal_path, prefix = retained._paths(cell)
    remote = {prefix + "/" + name: data for name, data in files.items()}
    remote[prefix + "/" + output.MANIFEST] = retained._encoded(manifest)
    terminal = {"format": retained.TERMINAL_FORMAT, "repository_name_sha256": retained.TARGET_SHA256,
        "inference_branch": retained.BRANCH,
        "claim_commit": CLAIM, "claim_identity": pilot._identity(retained._encoded(claim)),
        "output_commit": OUTPUT, "manifest_identity": pilot._identity(retained._encoded(manifest)),
        "publication_receipt_sha256": "7" * 64, "publication_acknowledged": True,
        "output_objects": [retained._object(name, data) for name, data in sorted(remote.items())], "completion": completed}
    api.seed(CLAIM, retained.BOOTSTRAP, {claim_path: retained._encoded(claim)})
    api.seed(OUTPUT, CLAIM, remote)
    api.seed(TERMINAL, OUTPUT, {terminal_path: retained._encoded(terminal)})
    api.head = TERMINAL
    api.main_snapshot = copy.deepcopy(api.trees[TERMINAL])
    case.files, case.payload, case.terminal, case.claim = files, payload, terminal, claim


def _synthetic_rubric(case, monkeypatch):
    cell = case.context.cell
    reference = "reference_files/synthetic.txt"
    frame = pd.DataFrame([{"task_id": cell["task_id"], "prompt": "synthetic task", "sector": "s", "occupation": "o",
        "rubric_json": json.dumps([{"rubric_item_id": "ri-1", "criterion": "synthetic criterion", "score": 2},
                                  {"rubric_item_id": "ri-2", "criterion": "second synthetic criterion", "score": 2}]),
        "reference_files": [reference], "deliverable_files": []}])
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    revision = json.loads(case.context.run.grader_config_json)["rubric"]["revision"]
    origins = [("parquet", "openai/gdpval", revision, "data/synthetic.parquet", intake.HFRole.PARQUET),
               ("reference", "openai/gdpval", revision, reference, intake.HFRole.REFERENCE_1),
               ("unused", "openai/gdpval", revision, "reference_files/unused.txt", intake.HFRole.REFERENCE_2)]
    data = {"parquet": buffer.getvalue(), "reference": b"synthetic reference only", "unused": b"not selected"}
    specs = {name: pilot._identity(value) for name, value in data.items()}
    for name, _, ref, member, _ in origins:
        case.api.originals[(ref, member)] = data[name]
    monkeypatch.setattr(intake, "_hf_origins", lambda: (revision, specs, origins))


class Child(pilot.LocalTransport):
    def __init__(self, case):
        self.case, self.calls, self.mode = case, 0, "grade"

    def require_source(self, plan, parent):
        assert plan["reviewed_source_sha"] == self.case.context.controller_source_sha
        assert parent.dispatch.source_base_sha == pilot.load_plan()["base_sha"]
        return {"synthetic_reviewed_source": True}

    def checkout(self, destination, sha):
        assert sha == self.case.context.controller_source_sha
        destination.mkdir(mode=0o700)
        # Actual fixed source closure/configs, not original data or a workspace.
        for directory in ("core", "schemas", "prompts"):
            shutil.copytree(pilot.ROOT / "batch-runner" / directory, destination / "batch-runner" / directory,
                            ignore=shutil.ignore_patterns("__pycache__"))
        members = set(pilot.load_plan()["source_pins"])
        members.update({connector.configs.MANIFEST_PATH, "batch-runner/step8_grade.py",
                        "batch-runner/scripts/download_inference_from_hf.py"})
        members.update(str(path.relative_to(pilot.ROOT)) for path in step8._requirements_closure(
            pilot.ROOT / "batch-runner", pilot.ROOT / "batch-runner/requirements.txt"))
        for name in members:
            path = destination / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(pilot.ROOT / name, path)

    def process(self, command, *, ownership, **options):
        self.calls += 1
        self.case.api.events.append("judge")
        assert self.case.api.events[-2] == "grade_claim"
        assert command == list(self.case.context.run.command)
        assert options["timeout"] == connector.CHILD_SECONDS
        assert not {"HF_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_OUTPUT"}.intersection(options["env"])
        assert options["env"]["HF_HUB_OFFLINE"] == "1"
        path, binding = ownership
        quiet = self.mode != "cleanup_lost"
        pilot._save(path, {**pilot._owner_state(binding["plan_sha256"]), **binding,
            "phase": "reaped" if quiet else "cleanup_unresolved", "tree_reaped": quiet, "owner_reaped": quiet})
        if self.mode not in {"missing", "cleanup_lost"}:
            _judge_output(self.case, self.mode)
        return SimpleNamespace(returncode=0 if self.mode in {"grade", "no_ledger"} else 1)


def _judge_output(case, mode):
    from core.grader import ItemGrade, TaskGrade
    from core.rubric_loader import RubricLoader
    from core.task_checkpoint import build_progress, write_checkpoint, TaskProgressDraft

    prepared = retained._read(case.root / "prepared.json")
    entry = prepared["entry"]
    config = json.loads(case.context.run.grader_config_json)
    path = case.root / "source" / entry["grade_path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = path.with_name(path.stem + ".cost_ledger.jsonl")
    ledger = _ledger(entry["cost_run_id"], case.context.cell["task_id"], "grading")
    if mode != "no_ledger":
        ledger_path.write_bytes(ledger)
    with connector._cwd(case.root / "source/batch-runner"):
        loader = RubricLoader(config["rubric"]["repo_id"], config["rubric"]["revision"], config["rubric"]["cache_dir"])
        result = step8.load_local_inference_results()
        task = TaskGrade(task_id=case.context.cell["task_id"], sector="s", occupation="o", items=[
            ItemGrade(rubric_item_id=item_id, criterion="synthetic criterion", max_score=2, awarded_score=2,
                verdict="pass", decided_by="precheck", required=None, evidence="synthetic generated evidence",
                precheck_pattern_id="file_exists_or_name") for item_id in prepared["rubric"]["rubric_item_ids"]],
            total_awarded=4, total_max=4, pct=100, critical_fail=False, gold_referenced=False,
            judge_call_count=0, precheck_count=2, judge_total_latency_ms=0, judge_input_tokens=0, judge_output_tokens=0,
            error="synthetic_runtime_failure" if mode == "error" else None)
        tasks = [] if mode == "partial" else [step8._task_to_dict(task, grading_wall_time_ms=1.0)]
        for row in tasks:
            row["grading_cost"] = CostReceipt.unavailable().as_dict()
        payload = step8._build_grade_payload(exp_name=case.context.run.command[2], inf_results=result, config=config,
            config_hash=entry["config_hash"], loader=loader, prompt_version=config["prompt"]["version"], task_dicts=tasks,
            grader_source_hash=entry["grader_source_hash"], source_inference_repo_id=retained._target(),
            source_inference_revision=OUTPUT, azure_ai_runtime_fingerprint="f" * 64,
            azure_ai_routes=[{"workload": "grader", "runtime_fingerprint": "f" * 64,
                              "profile": "direct-v1", "endpoint_kind": "direct-v1"}],
            run_status="partial" if mode == "partial" else "diagnostic", expected_task_ids=[case.context.cell["task_id"]],
            source_experiment_id=case.context.cell["run_id"], renderer_fingerprint=RENDERER,
            cost_ledger=None if mode == "no_ledger" else ledger_reference(
                str(ledger_path.relative_to(case.root / "source")), hashlib.sha256(ledger).hexdigest()))
        path.write_bytes(_json(payload))
        if mode == "partial":
            progress = build_progress(task_id=case.context.cell["task_id"], grader_source_hash=entry["grader_source_hash"],
                rubric_item_ids=prepared["rubric"]["rubric_item_ids"], draft=TaskProgressDraft())
            write_checkpoint(path, progress)


def invoke(case, capsys, phase="plan", **changes):
    args = ["--selector", changes.get("selector", "pilot/" + case.context.cell["cell_id"]),
            "--reviewed-source-sha", changes.get("source", case.context.controller_source_sha),
            "--producer-source-sha", changes.get("producer", case.context.plan["reviewed_source_sha"]
                if case.context.plan["reviewed_source_sha"] != case.context.controller_source_sha else ""),
            "--terminal-revision", changes.get("terminal", case.context.terminal_revision),
            "--root", str(changes.get("root", case.root)), "--phase", phase]
    diagnostic = []
    original_context = output._error_context
    def error_context(error):
        # Test diagnostics expose locations/types only, never exception text
        # (which may deliberately contain synthetic secrets/private locators).
        item = error
        for _ in range(6):
            diagnostic.append(type(item).__name__)
            trace = item.__traceback__
            while trace is not None:
                diagnostic.append(f"{Path(trace.tb_frame.f_code.co_filename).name}:{trace.tb_lineno}")
                trace = trace.tb_next
            if item.__cause__ is None:
                break
            item = item.__cause__
        return original_context(error)
    with patch.object(output, "_error_context", error_context):
        code = connector.main(args, _test_api=case.api, _test_transport=case.transport)
    case.diagnostic = diagnostic
    capture = capsys.readouterr()
    text = capture.out + capture.err
    for secret in (TOKEN, case.api.repo, str(case.root), "https://", "signed=", "private-secret", "Traceback"):
        assert secret not in text
    value = json.loads(capture.out or capture.err)
    case.api.assert_main_unchanged()
    return code, value


def prepared(case, capsys):
    code, value = invoke(case, capsys, "prepare")
    if code != 0:
        pytest.fail(pilot._canonical_json(value) + "\n" + ";".join(case.diagnostic))
    assert value["judge_ready"] is True
    return retained._read(case.root / "prepared.json")


def admitted(case, capsys):
    ready = prepared(case, capsys)
    code, value = invoke(case, capsys, "claim")
    if code != 0:
        pytest.fail(pilot._canonical_json(value) + "\n" + ";".join(case.diagnostic))
    return ready


def judged(case, capsys, mode="grade"):
    ready = admitted(case, capsys)
    case.transport.mode = mode
    assert invoke(case, capsys, "judge")[0] == (2 if mode == "cleanup_lost" else 0)
    return ready


def test_plan_never_looks_up_credentials_or_network(case, capsys, monkeypatch):
    monkeypatch.delenv("PILOT_GRADE_DRY_RUN")  # Ordinary plan, not the live job's approval check.
    class NoTokens(dict):
        def get(self, key, *args):
            assert key not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"}
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoTokens(os.environ))
    code, value = invoke(case, capsys)
    assert code == 0 and value["outcome"] == "plan_only" and value["judge_entry_requested"] is False
    assert case.api.calls == [] and not case.root.exists() and case.transport.calls == 0
    assert invoke(case, capsys, selector="pilot/branch-setup", terminal="")[0] == 0


@pytest.mark.parametrize("bad", ["foreign_cell", "mutable_revision", "git_revision", "dataset_revision", "setup_revision",
                                  "setup_cell_mode", "force", "repeat", "resume", "task_override", "rerun", "source"])
def test_closed_request_and_authority_refusals(case, capsys, monkeypatch, bad):
    arguments, phase = {}, "plan"
    if bad == "foreign_cell":
        arguments["selector"] = "pilot/foreign_A_r1"
    elif bad in {"mutable_revision", "git_revision", "dataset_revision"}:
        arguments["terminal"] = {"mutable_revision": "main", "git_revision": SOURCE,
                                 "dataset_revision": case.context.plan["dataset"]["revision"]}[bad]
    elif bad == "setup_revision":
        arguments["selector"] = "pilot/branch-setup"
    elif bad == "setup_cell_mode":
        phase = "setup"
    else:
        name, value = {"force": ("GRADE_FORCE", "true"), "repeat": ("GRADE_RUN_ORDINAL", "2"),
            "resume": ("GRADE_RESUME", "true"), "task_override": ("GRADE_TASKS", "foreign"),
            "rerun": ("GITHUB_RUN_ATTEMPT", "2"), "source": ("PILOT_WORKFLOW_SHA", "0" * 40)}[bad]
        monkeypatch.setenv(name, value)
        phase = "prepare"
    assert invoke(case, capsys, phase, **arguments)[0] == 2
    assert case.api.calls == [] and case.transport.calls == 0


def test_aliases_preserve_fixed_config_and_canonical_run(case, compilation):
    parent = compilation[1]
    for index in (6, 7, 29):
        _, cell, grading = adapter.compile_cell_grading_plan(ci.CAMPAIGN, compilation[0]["order"][index], SOURCE)
        run = grading.runs[0]
        assert run.command[2] == f"pilot/cell-{index:02d}"
        assert step8._experiment_path_slug(run.command[2]) == f"pilot__cell-{index:02d}"
        assert run.run_id == cell["run_id"] == run.command[run.command.index("--source-experiment-id") + 1]
        assert run.grader_config_json == parent.runs[0].grader_config_json
        assert json.loads(run.experiment_config_json)["experiment"]["id"] == run.run_id
    for index in range(6):
        with pytest.raises(adapter.PilotGradingInputRefused, match="^registered_cell_controls_refused$") as refused:
            adapter.compile_cell_grading_plan(ci.CAMPAIGN, compilation[0]["order"][index], SOURCE)
        assert isinstance(refused.value.__cause__, ci.CICellRefused)
        assert str(refused.value.__cause__) == "ci_prefix_cell_out_of_scope"
    assert all(run.command[2].startswith("execution_envelope/") for run in parent.runs)


def test_materializes_actual_retained_bytes_without_self_approved_provenance(case, capsys):
    ready = prepared(case, capsys)
    assert ready["proof_boundary"] == connector.PROOF and ready["grading_state"] == "UNRUN"
    identity = retained._read(case.root / "inference-identity.json")
    assert identity["source_revision"] == OUTPUT and identity["source_repo_id"] == case.api.repo
    assert identity["source_revision"] not in {SOURCE, case.context.plan["dataset"]["revision"], TERMINAL}
    derived = json.loads((case.root / "inputs/batch-runner/workspace/step2_inference_results.json").read_bytes())
    original = case.payload
    assert {key: value for key, value in derived.items() if key not in {
        "source_repo_id", "source_revision", "source_identity_document_sha256", "result_fingerprint"}} == {
        key: value for key, value in original.items() if key != "result_fingerprint"}
    for name, data in case.files.items():
        base = case.root / "original" / ("upload" if name.startswith("deliverable_files/") else "")
        assert (base / name).read_bytes() == data
    assert not any(name.startswith("cell-grades/") for name in case.api.trees[case.api.head])
    assert case.transport.calls == 0


@pytest.mark.parametrize("damage", ["private", "foreign_repo", "terminal_hash_only", "manifest_hash", "claim_source",
    "claim_input", "host_policy", "unconfirmed_cleanup", "unacknowledged_output", "wrong_result_bytes", "foreign_task"])
def test_retained_evidence_cannot_be_replaced_by_self_hashed_metadata(case, capsys, damage):
    api, cell = case.api, case.context.cell
    claim_path, terminal_path, prefix = retained._paths(cell)
    if damage == "private":
        api.private = False
    elif damage == "foreign_repo":
        api.id_matches = False
    elif damage == "wrong_result_bytes":
        api.trees[OUTPUT][prefix + "/step2_inference_results.json"] += b" "
    elif damage == "foreign_task":
        case.payload["results"][0]["task_id"] = "foreign"
        api.trees[OUTPUT][prefix + "/step2_inference_results.json"] = _json(case.payload)
    elif damage in {"claim_source", "claim_input", "host_policy"}:
        claim = copy.deepcopy(case.claim)
        if damage == "host_policy":
            claim["binding"]["host"]["policy"] = {**ci.HOST_POLICY, "runner": "foreign"}
        else:
            key = "source_sha" if damage == "claim_source" else "verified_inputs_sha256"
            claim["binding"][key] = "0" * (40 if key == "source_sha" else 64)
        api.trees[CLAIM][claim_path] = retained._encoded(claim)
        case.terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
    else:
        if damage == "terminal_hash_only":
            case.terminal["output_objects"] = []
        elif damage == "manifest_hash":
            case.terminal["manifest_identity"]["sha256"] = "0" * 64
        elif damage == "unconfirmed_cleanup":
            case.terminal["completion"]["cleanup_confirmed"] = False
        else:
            case.terminal["publication_acknowledged"] = False
    api.trees[TERMINAL][terminal_path] = retained._encoded(case.terminal)
    api.main_snapshot = copy.deepcopy(api.trees[TERMINAL])
    assert invoke(case, capsys, "prepare")[0] == 2
    assert case.transport.calls == 0 and not (case.root / "claim-reserved.json").exists()


def test_missing_result_remains_ungraded_without_claim_or_original_fetch(case, capsys, tmp_path):
    _seed_outputs(case, tmp_path, missing=True)
    code, value = invoke(case, capsys, "prepare")
    assert code == 0 and value["outcome"] == "ungraded" and value["judge_ready"] is False
    assert invoke(case, capsys, "claim")[0] == 2
    assert case.transport.calls == 0 and case.api.events == []


def test_failed_retained_result_stays_failed_and_explicitly_ungraded(case, capsys, tmp_path):
    _seed_outputs(case, tmp_path, failed=True)
    code, value = invoke(case, capsys, "prepare")
    assert code == 0 and value["judge_ready"] is False and value["outcome"] == "ungraded"
    ready = retained._read(case.root / "prepared.json")
    assert ready["evidence"]["terminal"]["completion"]["status"] == "failed"
    assert ready["materialization"]["task_status"] == "error"
    assert invoke(case, capsys, "claim")[0] == 2 and case.transport.calls == 0


@pytest.mark.parametrize("native", ["forced_unavailable", "actual_host"])
def test_native_install_boundary_is_not_a_test_double_readiness_claim(case, capsys, monkeypatch, record_property, native):
    observed = []
    real = case.native_rename()
    def rename(*args):
        result = real(*args) if native == "actual_host" else -1
        if native != "actual_host":
            ctypes.set_errno(errno.EINVAL)
        observed.append((result, ctypes.get_errno()))
        return result
    monkeypatch.setattr(primitives, "_no_replace_rename", lambda: rename)
    code, value = invoke(case, capsys, "prepare")
    assert observed
    record_property("native_install_observation", f"{native}:return={observed[0][0]},errno={observed[0][1]},cli={code}")
    if observed[0][0] == 0:
        assert native == "actual_host" and code == 0
    else:
        assert code == 2 and value["reason"] == "grading_input_materialization_refused"
        assert not (case.root / "prepared.json").exists()
    assert case.api.events == [] and case.transport.calls == 0


@pytest.mark.parametrize("failure", ["public", "branch_missing", "unknown_tip", "claimed", "parent_conflict", "lost_claim", "failed_claim"])
def test_grade_claim_refuses_before_judge_and_never_replays(case, capsys, failure):
    prepared(case, capsys)
    api = case.api
    if failure == "public":
        api.private = False
    elif failure == "branch_missing":
        api.branches.clear()
    elif failure == "unknown_tip":
        api.branches[connector.BRANCH] = OUTPUT
    elif failure == "claimed":
        api.trees[retained.BOOTSTRAP][connector._paths(case.context.cell)[0]] = b"incomplete claim"
    elif failure == "parent_conflict":
        api.move_before_commit = True
    elif failure == "lost_claim":
        api.lost = "grade_claim"
    else:
        api.fail = "grade_claim"
    assert invoke(case, capsys, "claim")[0] == 2
    calls = len(api.calls)
    assert invoke(case, capsys, "claim")[0] == 2 and len(api.calls) == calls
    assert invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 0
    assert retained._read(case.root / "claim-receipt.json")["outcome"] == "unresolved"


@pytest.mark.parametrize("damage", ["deliverable", "derived_result", "config", "source", "partial_destination"])
def test_prepared_immutable_inputs_and_no_clobber(case, capsys, damage):
    if damage == "partial_destination":
        case.root.mkdir(mode=0o700)
        assert invoke(case, capsys, "prepare")[0] == 2
        assert case.api.calls == []
        return
    ready = prepared(case, capsys)
    name = {"deliverable": next(name for name in ready["immutable_files"] if "/deliverable_files/" in name),
        "derived_result": case.context.run.inference_results_path, "config": case.context.run.grader_config_path,
        "source": "batch-runner/step8_grade.py"}[damage]
    path = case.root / "source" / name
    path.write_bytes(path.read_bytes() + b"changed")
    assert invoke(case, capsys, "claim")[0] == 2 and case.api.events == [] and case.transport.calls == 0


@pytest.mark.parametrize("mode,expected", [("grade", "graded"), ("partial", "partial"), ("missing", "failed"),
                                          ("error", "failed"), ("no_ledger", "graded")])
def test_one_claim_one_entry_validated_private_outputs_and_missing_accounting(case, capsys, mode, expected):
    ready = judged(case, capsys, mode)
    code, value = invoke(case, capsys, "publish")
    assert code == 0, value
    receipt = retained._read(case.root / "publication-receipt.json")
    revision = receipt["returned_commit"]
    assert revision == case.api.branches[connector.BRANCH] and revision not in {SOURCE, OUTPUT, TERMINAL}
    terminal = json.loads(case.api.trees[revision][connector._paths(case.context.cell)[1]])
    assert terminal["outcome"] == expected
    assert terminal["invoice_complete"] is False and terminal["http_request_count"] is None
    assert "returned_commit" not in terminal
    assert case.api.events == ["grade_claim", "judge", "grade_output"] and case.transport.calls == 1
    for record in terminal["files"]:
        relative = record["path"].split(case.context.cell["cell_id"] + "/", 1)[1]
        assert case.api.trees[revision][record["path"]] == (case.root / "source" / relative).read_bytes()
        assert not relative.endswith("sqlite3") and "original" not in relative
    assert ("grade_result" in terminal["missing"]) == (mode == "missing")
    assert ("grade_cost_ledger" in terminal["missing"]) == (mode in {"missing", "no_ledger"})
    calls = len(case.api.calls)
    assert invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 1
    assert invoke(case, capsys, "publish")[0] == 2 and len(case.api.calls) == calls
    assert ready["materialization"]["grading"]["state"] == "UNRUN"


@pytest.mark.parametrize("failure", ["cleanup", "lost_output", "failed_output", "invalid_grade", "invalid_schema", "missing_items", "wrong_ledger"])
def test_failed_or_lost_publication_blocks_replay_and_keeps_observations_separate(case, capsys, failure):
    ready = judged(case, capsys, "cleanup_lost" if failure == "cleanup" else "grade")
    if failure in {"lost_output", "failed_output"}:
        setattr(case.api, "lost" if failure == "lost_output" else "fail", "grade_output")
    if failure in {"invalid_grade", "invalid_schema", "missing_items", "wrong_ledger"}:
        path = case.root / "source" / ready["entry"]["grade_path"]
        if failure in {"invalid_grade", "invalid_schema", "missing_items"}:
            payload = json.loads(path.read_bytes())
            if failure == "invalid_grade":
                payload["source_inference_revision"] = SOURCE
            elif failure == "invalid_schema":
                payload.pop("judge")
            else:
                payload["tasks"][0]["items"].pop()
            path.write_bytes(_json(payload))
        else:
            path.with_name(path.stem + ".cost_ledger.jsonl").write_bytes(_ledger("foreign", case.context.cell["task_id"]))
    assert invoke(case, capsys, "publish")[0] == 2
    assert invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 1
    if failure == "lost_output":
        original = (case.root / "publication-receipt.json").read_bytes()
        code, value = invoke(case, capsys, "reconcile")
        assert code == 0 and value["outcome"] == "verified_server_state"
        assert (case.root / "publication-receipt.json").read_bytes() == original
        assert json.loads(original)["outcome"] == "unresolved"
        assert invoke(case, capsys, "claim")[0] == 2
        assert case.api.events == ["grade_claim", "judge", "grade_output"]
    else:
        assert invoke(case, capsys, "reconcile")[0] == 2


def test_lost_grade_ack_valid_server_tip_can_admit_only_an_absent_other_cell(case, capsys, tmp_path):
    ready = judged(case, capsys)
    case.api.lost = "grade_output"
    assert invoke(case, capsys, "publish")[0] == 2
    lost_receipt = (case.root / "publication-receipt.json").read_bytes()
    with retained._session(case.api) as (api, token, deadline):
        head, observation = connector._branch_tip(api, api.repo, case.context, ready,
            connector._cache(case.root, "next-read"), token, deadline)
        assert head == api.branches[connector.BRANCH] and observation["cell_id"] == case.context.cell["cell_id"]
        # There is no added grading order: this is canonical membership plus
        # absent per-cell identity, not a scheduler or permission to skip inference.
        connector._absent(api, api.repo, head, case.context.plan["cells"][11], token, deadline)
        with pytest.raises(output.OutputPublicationRefused, match="cell_already_claimed"):
            connector._absent(api, api.repo, head, case.context.cell, token, deadline)
    assert (case.root / "publication-receipt.json").read_bytes() == lost_receipt
    # A fresh host/root may not replay the same cell either.
    case.root = tmp_path / "fresh-host"
    prepared(case, capsys)
    assert invoke(case, capsys, "claim")[0] == 2 and case.transport.calls == 1


@pytest.mark.parametrize("damage", ["missing", "conflicting", "arbitrary_path", "read_failed"])
def test_unverified_grade_server_state_stays_blocked(case, capsys, damage):
    judged(case, capsys)
    case.api.lost = "grade_output"
    assert invoke(case, capsys, "publish")[0] == 2
    original = (case.root / "publication-receipt.json").read_bytes()
    path = connector._paths(case.context.cell)[1]
    head = case.api.branches[connector.BRANCH]
    if damage == "missing":
        case.api.trees[head].pop(path)
    elif damage in {"conflicting", "arbitrary_path"}:
        terminal = json.loads(case.api.trees[head][path])
        if damage == "conflicting":
            terminal["binding"]["publication_receipt_sha256"] = "0" * 64
        else:
            terminal["files"][0]["path"] = path.rsplit("/", 1)[0] + "/data/grades/arbitrary.json"
        case.api.trees[head][path] = retained._encoded(terminal)
    else:
        case.api.read_fail = True
    assert invoke(case, capsys, "reconcile")[0] == 2
    assert (case.root / "publication-receipt.json").read_bytes() == original
    assert invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 1


@pytest.mark.parametrize("mode", ["absent", "existing", "public", "lost_create"])
def test_only_explicit_fixed_branch_setup_from_bootstrap(case, capsys, monkeypatch, mode):
    monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", connector._approval_request_sha256(
        SOURCE, "pilot/branch-setup", "", {"id": "12345", "attempt": 1}))
    if mode != "existing":
        case.api.branches.clear()
    if mode == "public":
        case.api.private = False
    if mode == "lost_create":
        case.api.branch_loss = True
    code, value = invoke(case, capsys, "setup", selector="pilot/branch-setup", terminal="")
    assert code == (0 if mode == "absent" else 2)
    if mode in {"absent", "lost_create"}:
        assert case.api.branches[connector.BRANCH] == retained.BOOTSTRAP
    calls = len(case.api.calls)
    assert invoke(case, capsys, "setup", selector="pilot/branch-setup", terminal="")[0] == 2
    assert len(case.api.calls) == calls and case.transport.calls == 0


def test_workflow_isolates_private_pilot_from_legacy_publication_and_inference():
    workflow = yaml.safe_load((pilot.ROOT / connector.WORKFLOW).read_text())
    jobs = workflow["jobs"]
    for name in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in jobs[name]["if"]
    plan, live = jobs["pilot-plan"], jobs["pilot-live"]
    assert "inputs.dry_run == true" in plan["if"] and plan["permissions"] == {"contents": "read"}
    approval = jobs["pilot-approve-paid"]
    assert "inputs.paid_approval == true" in live["if"] and approval["environment"]["name"] == "grading"
    assert "environment" not in live and live["needs"] == ["pilot-approve-paid"]
    assert "needs.pilot-approve-paid.result == 'success'" in live["if"]
    assert live["permissions"] == {"contents": "read", "id-token": "write"}
    assert live["container"] == jobs["grade"]["container"]
    for job in (plan, live):
        assert not any("upload-artifact" in step.get("uses", "") for step in job["steps"])
        checkout = next(step for step in job["steps"] if "actions/checkout" in step.get("uses", ""))
        assert checkout["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
        assert not any("codex-budget-pilot-ci-cell" in step.get("run", "") for step in job["steps"])
    token_steps = [step for step in live["steps"] if "HF_TOKEN" in step.get("env", {})]
    assert len(token_steps) == 5
    assert all(any("--phase " + phase in step["run"] for phase in ("setup", "inspect", "prepare", "claim", "publish")) for step in token_steps)
    inspection = next(step for step in token_steps if "--phase inspect" in step["run"])
    assert inspection["if"] == ("inputs.experiment_yaml == 'pilot/branch-inspect' || "
                                "inputs.experiment_yaml == 'pilot/inference-branch-inspect'")
    assert all("inputs.experiment_yaml != 'pilot/branch-inspect'" in step["if"]
               for step in live["steps"] if step.get("id") == "pilot_input" or "preflight_grading_renderer.py" in step.get("run", ""))
    judge = next(step for step in live["steps"] if step.get("id") == "pilot_judge")
    assert "HF_TOKEN" not in judge.get("env", {}) and "steps.pilot_claim.outcome == 'success'" in judge["if"]
    assert ci.PUBLIC_FIXED["grading_launched"] is False
