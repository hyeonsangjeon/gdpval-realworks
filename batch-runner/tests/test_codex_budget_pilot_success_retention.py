"""Step2's real no-QA writer through private retention and grading inputs.

Original-input provenance, source/host capability, native turns and HF are
synthetic. Serialization, deadlines, receipts, byte/identity/privacy checks,
CAS and terminal/grading bindings are real. The install syscall is an explicit
test double, not native-host proof. No historical payload is reconstructed.
"""

import contextlib
import copy
import ctypes
import errno
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import gpt54_v2_grading_input as primitives
import step2_run_inference as step2
import step8_grade
from core import azure_ai_clients, codex_azure_token, codex_runner
from core.codex_task_deadline import CodexTaskDeadlineStore
from core.needs_files import NeedsFilesManifest
from core.result_fingerprint import inference_result_fingerprint, validate_inference_result_fingerprint
from core.source_identity import source_task_projection_sha256
from .test_codex_budget_pilot_ci import CICellChildren
from .test_codex_budget_pilot_epoch02 import compiled  # noqa: F401 -- genuine compiler cache only
from .test_codex_budget_pilot_epoch03_gate import GateHF
from .test_codex_budget_pilot_retention import (
    SOURCE, TOKEN, TOKEN_KEYS, boundary, case, cell_root, cli, finalized,
    read_plan, scenario, select_fresh,
)  # noqa: F401 -- fixtures/helpers, never previous test families

PRIVATE = "PRIVATE_SYNTHETIC_SECRET https://private.invalid/?token=secret /private/native/auth.json"
DELIVERABLE = b"Synthetic generated answer.\n"
REFLECTION = {"reflection_history", "reflection_attempts"}


@pytest.fixture(autouse=True)
def offline(monkeypatch, compiled):
    from huggingface_hub import HfApi
    from huggingface_hub.utils import _auth, _headers

    def forbidden(*args, **kwargs):
        pytest.fail("success-retention test crossed a live boundary")

    monkeypatch.setattr(pilot, "compile_pilot", lambda *args: copy.deepcopy(compiled(*args)))
    for target, names in (
        (subprocess, ("run", "Popen", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (os, ("system",)), (time, ("sleep",)),
        (codex_azure_token, ("acquire_token", "get_bearer_token_provider")),
        (codex_runner, ("require_pinned_runtime",)),
        (codex_runner.CodexAgentRunner, ("open_runtime", "preflight_auth_command")),
        (output, ("_hf_client",)), (_auth, ("get_token",)), (_headers, ("get_token",)),
        (HfApi, ("repo_info", "create_commit", "create_repo", "create_branch", "hf_hub_download", "whoami")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential, step8_grade.Grader):
        monkeypatch.setattr(constructor, "__init__", forbidden)
    monkeypatch.setattr(codex_runner, "_descendant_pids", lambda _: set())
    monkeypatch.setattr(codex_runner, "sweep_orphans", lambda _: ())


class WriterChildren(CICellChildren):
    """Use the dispatched Step2 CLI, not a hand-built row or copied writer."""

    def __init__(self, sources, task_ids, api, monkeypatch):
        super().__init__(sources, task_ids)
        self.api, self.monkeypatch = api, monkeypatch
        self.damage = None
        self.turns = 0
        self.child_log = io.StringIO()

    def _executor(self, **kwargs):
        assert kwargs["llm_client"] is None and kwargs["mode"] == "codex_foundry"
        assert kwargs["timeout"] == 1800 and kwargs["reasoning_effort"] == "xhigh"
        runner = codex_runner.CodexAgentRunner(
            kwargs["codex_options"]["provider_settings"], timeout=kwargs["timeout"],
            cost_ledger=kwargs["codex_cost_ledger"], run_id=kwargs["run_id"],
            condition_name=kwargs["condition_name"], verify_runtime=False, preflight_auth=False,
            task_deadline_store=kwargs["codex_options"]["task_deadline_store"],
        )

        def runtime(workspace):
            assert not TOKEN_KEYS.intersection(os.environ)
            if self.damage != "failed_withheld":
                (workspace.workspace / "answer.txt").write_bytes(DELIVERABLE)
            return SimpleNamespace(close=lambda: None)

        def observed(handle, *, task_deadline):
            assert task_deadline.store is runner.task_deadline_store
            self.turns += 1
            usage = SimpleNamespace(total=SimpleNamespace(input_tokens=17, output_tokens=9,
                cached_input_tokens=5, reasoning_output_tokens=4, cache_write_input_tokens=0))
            if self.damage == "failed_withheld":
                return codex_runner.TurnObservation(failure="synthetic turn failure", usage=usage)
            return codex_runner.TurnObservation(result=SimpleNamespace(
                id=handle.id, final_response="Synthetic answer.", usage=usage))

        runner.open_runtime = runtime
        runner.start_thread = lambda *a, **k: SimpleNamespace(
            id="synthetic-thread", turn=lambda _: SimpleNamespace(id="synthetic-turn"))
        runner._await_turn = observed

        def execute(**options):
            options.pop("verbose")
            return runner.run(**options)

        return SimpleNamespace(runner=runner, execute=execute, close=runner.close)

    def _process(self, command, **options):
        assert self.api.commits == ["admission"] and not TOKEN_KEYS.intersection(options["env"])
        self.api.events.append("child")
        if command[1] != "step2_run_inference.py":
            return super()._process(command, **options)
        cwd, workspace = options["cwd"], options["cwd"] / "workspace"
        self.calls.append(("infer", cwd.parent.parent.name, tuple(command)))
        # Synthetic original provenance uses the same checked input projection
        # as preparation. Result, reference-byte and fingerprint readers stay real.
        manifest = NeedsFilesManifest({"_schema_version": 4, "reference_files": self.snapshot.references,
            "tasks": {row["task_id"]: {"needs_files": self.snapshot.needs_files[row["task_id"]],
                "source_projection_sha256": source_task_projection_sha256(**row)} for row in self.snapshot.projections}})

        def host(mode):
            assert mode == "codex_foundry"  # Explicit fake native-host boundary.

        with self.monkeypatch.context() as scoped, patch.dict(os.environ, options["env"], clear=True), \
                contextlib.redirect_stdout(self.child_log), contextlib.redirect_stderr(self.child_log):
            # This is the fake child boundary, not a provider observation.
            scoped.setenv("CODEX_FOUNDRY_CONNECTION_CONFIRMED", "1")
            scoped.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")
            scoped.setenv("AZURE_OPENAI_V1_ENDPOINT", "https://synthetic.services.ai.azure.com/openai/v1/")
            scoped.setattr(step2, "WORKSPACE_DIR", workspace)
            scoped.setattr(step2, "UPLOAD_DIR", workspace / "upload")
            scoped.setattr(step2, "DEFAULT_LOCAL_PATH", cwd.parent / "data/gdpval-local")
            scoped.setattr(NeedsFilesManifest, "load", classmethod(lambda cls, path=None: manifest))
            scoped.setattr(step2, "_require_host_may_carry_a_benchmark_run", host)
            scoped.setattr(step2, "AzureAIClientFactory", lambda **_: SimpleNamespace(close=lambda: None))
            scoped.setattr(step2, "TaskExecutor", self._executor)
            scoped.setattr(step2, "CodexTaskDeadlineStore", lambda *a, **k:
                           CodexTaskDeadlineStore(*a, **k, clock=self.clock))
            scoped.setattr(step2.sys, "argv", command[1:])
            code = 0
            try:
                step2.main()
            except SystemExit as error:
                code = error.code
        assert self.turns == 1, self.child_log.getvalue()
        result = workspace / Path(pilot.RESULT).name
        self.writer_bytes = result.read_bytes()
        assert self.writer_bytes == (workspace / "step2_inference_results_condition_a.json").read_bytes()
        payload = json.loads(self.writer_bytes)
        validate_inference_result_fingerprint(payload)
        row = payload["results"][0]
        assert row["reflection_history"] == [] and type(row["reflection_attempts"]) is int
        assert row["reflection_attempts"] == 0 and "reflection_final_score" not in row
        assert code == (1 if self.damage == "failed_withheld" else 0)
        # Adversarial cases change the serialized fixture before finalization,
        # then bind a NEW fingerprint; never reuse a hash after changing bytes.
        if self.damage == "absent":
            for key in REFLECTION:
                row.pop(key)
        elif self.damage == "history":
            row["reflection_history"] = [PRIVATE]
        elif self.damage in {"attempts_bool", "attempts_float", "attempts_positive"}:
            row["reflection_attempts"] = {"attempts_bool": False, "attempts_float": 0.0, "attempts_positive": 1}[self.damage]
        elif self.damage in {"missing_history", "missing_attempts"}:
            row.pop("reflection_history" if self.damage == "missing_history" else "reflection_attempts")
        elif self.damage == "score":
            row["reflection_final_score"] = 10
        elif self.damage in {"unknown", "failed_withheld"}:
            row["unsupported_private_field"] = PRIVATE
        elif self.damage == "nested_secret":
            row["observability"]["extra"] = {"authorization": PRIVATE}
        elif self.damage == "raw_messages":
            row["messages"] = [PRIVATE]
        elif self.damage == "originals":
            payload["reference_files"] = [PRIVATE]
        elif self.damage == "source":
            payload["source"] = "synthetic-foreign/dataset"
        if payload != json.loads(self.writer_bytes):
            payload["result_fingerprint"] = inference_result_fingerprint(payload)
            result.write_bytes(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode())
        self.result_bytes, self.ledger_bytes = result.read_bytes(), (workspace / Path(pilot.LEDGER).name).read_bytes()
        return subprocess.CompletedProcess(command, code)


@pytest.fixture
def success_case(case, monkeypatch):
    case.api = GateHF()
    case.transport = WriterChildren(case.sources, case.ids, case.api, monkeypatch)
    yield case
    case.api.assert_frozen()


def _grade_inputs(s, terminal, monkeypatch, damage):
    context = grading.compile_request("pilot/" + s.selected, SOURCE, terminal)
    root = s.host / "grading-inputs"
    root.mkdir(mode=0o700)
    deadline = time.monotonic() + output.PUBLICATION_SECONDS
    evidence = grading._retained_input(context, s.api, s.api.repo, root, TOKEN, deadline)
    revision = evidence["terminal"]["output_commit"]
    assert revision not in {terminal, SOURCE, retained.BOOTSTRAP}
    _, _, prefix = retained._paths(context.cell)
    files = {record["path"]: grading._fetch(s.api, s.api.repo, revision, prefix + "/" + record["path"],
        record, root, TOKEN, deadline) for record in evidence["manifest"]["files"]}
    identity = grading._inference_identity(context, evidence, files, s.api.repo)
    for name, data in files.items():
        base = root / "original" / ("upload" if name.startswith("deliverable_files/") else "")
        pilot._write_file(base / name, data)
    original = root / "original/step2_inference_results.json"
    identity_path = root / "identity.json"
    identity_bytes = retained._encoded(identity)
    pilot._write_file(identity_path, identity_bytes)
    if damage == "grade_bytes":
        original.write_bytes(original.read_bytes() + b" ")
    elif damage == "grade_identity":
        identity_path.write_bytes(retained._encoded({**identity, "source_revision": SOURCE}))

    def fixture_rename(src_fd, src, dest_fd, dest, flags):
        assert flags == 1
        if os.path.lexists(Path(f"/proc/self/fd/{dest_fd}") / os.fsdecode(dest)):
            ctypes.set_errno(errno.EEXIST)
            return -1
        os.rename(src, dest, src_dir_fd=src_fd, dst_dir_fd=dest_fd)
        return 0

    monkeypatch.setattr(primitives, "_no_replace_rename", lambda: fixture_rename)
    options = dict(campaign_id=ci.CAMPAIGN, cell_id=s.selected, reviewed_source_sha=SOURCE,
        inference_results=original, source_upload=root / "original/upload", inference_identity=identity_path,
        approved_identity_sha256=pilot._identity(identity_bytes)["sha256"], destination=root / "inputs")
    if damage in {"grade_bytes", "grade_identity"}:
        with pytest.raises(adapter.PilotGradingInputRefused):
            adapter.materialize_pilot_grading_input(**options)
        assert not (root / "inputs").exists()
        return
    prepared = adapter.materialize_pilot_grading_input(**options)
    assert prepared["task_status"] == "success" and prepared["grading"]["state"] == "UNRUN"
    assert prepared["source_identity"]["source_revision"] == revision
    data = (root / "inputs" / prepared["materialized_result"]["path"]).read_bytes()
    materialized, raw = json.loads(data), json.loads(s.transport.result_bytes)
    validate_inference_result_fingerprint(materialized)
    assert materialized["results"] == raw["results"]
    assert materialized["result_fingerprint"] != raw["result_fingerprint"]
    assert set(materialized) - set(raw) == {"source_repo_id", "source_revision", "source_identity_document_sha256"}
    assert original.read_bytes() == s.transport.result_bytes
    assert (root / "inputs" / Path(prepared["materialized_result"]["path"]).parent / Path(pilot.LEDGER).name).read_bytes() == s.transport.ledger_bytes
    assert next((root / "inputs").rglob("answer.txt")).read_bytes() == DELIVERABLE


@pytest.mark.parametrize("damage", [
    "plan", "supported", "absent", "history", "attempts_bool", "attempts_float", "attempts_positive",
    "missing_history", "missing_attempts", "score", "unknown", "nested_secret", "raw_messages", "originals",
    "result_bytes", "deliverable_bytes", "ledger_bytes", "source", "receipt", "cleanup",
    "failed_withheld", "publication_lost", "grade_bytes", "grade_identity",
])
def test_success_writer_retention_contract(success_case, monkeypatch, capsys, damage):
    s = success_case
    s.transport.damage = damage
    if damage == "plan":
        class NoToken(dict):
            def get(self, key, *args):
                assert key not in TOKEN_KEYS
                return super().get(key, *args)
        monkeypatch.setattr(os, "environ", NoToken(os.environ))
        assert cli(s) == 0 and boundary(s, capsys, monkeypatch)[1]["outcome"] == "plan_only"
        assert s.api.calls == s.transport.calls == [] and s.transport.turns == 0
        return
    finalized(s, capsys, monkeypatch, expected=1 if damage == "failed_withheld" else 0)
    plan = read_plan(s)
    cell = next(cell for cell in plan["cells"] if cell["cell_id"] == s.selected)
    completion_bytes = s.envelope.read_bytes()
    completion = json.loads(completion_bytes)
    status = "failed" if damage == "failed_withheld" else "succeeded"
    assert completion["status"] == status and completion["exit_code"] == (1 if status == "failed" else 0)
    assert completion["reason"] == ("child_nonzero_exit" if status == "failed" else None)
    assert completion["cleanup_confirmed"] is True and completion["child_invocations"] == 1
    assert completion["invoice_complete"] is completion["grading_launched"] is False
    assert completion["http_request_count"] is None and completion["other_cells_not_run"] == 29
    assert completion["artifacts"]["result"] == pilot._identity(s.transport.result_bytes)
    assert completion["artifacts"]["ledger"] == pilot._identity(s.transport.ledger_bytes)
    assert completion["receipt"]["status"] == "partial"
    assert completion["receipt"]["usage"]["input_tokens"] == 17
    state_path = s.root / cell["roles"]["checkpoint"]
    state = pilot._load(state_path)
    options = dict(root=s.root, campaign=ci.CAMPAIGN, cell_id=s.selected, source_sha=SOURCE,
                   config_sha=cell["config_sha256"], _failure_metadata=True)
    if damage == "supported":
        raw = json.loads(s.transport.writer_bytes)
        assert set(raw) <= output.RESULT_FIELDS
        output._safe_record(raw)
        old_fields = output.ROW_FIELDS - REFLECTION
        # Exact locally reproduced paths; no claim about the missing live file.
        assert {"results[0]." + key for key in set(raw["results"][0]) - old_fields} == {
            "results[0].reflection_history", "results[0].reflection_attempts"}
        with monkeypatch.context() as old_contract:
            old_contract.setattr(output, "ROW_FIELDS", old_fields)
            with pytest.raises(output.OutputPublicationRefused, match="^unsafe_result_fields$"):
                output.prepare(**options)
        assert s.transport.result_bytes == s.transport.writer_bytes
    if damage in {"result_bytes", "ledger_bytes", "deliverable_bytes"}:
        name = "result" if damage == "result_bytes" else "ledger"
        path = s.root / cell["roles"][name]
        if damage == "deliverable_bytes":
            path = s.root / cell["roles"]["checkout"] / "batch-runner/workspace/upload" / state["artifacts"]["deliverable_files"][0]["path"]
        path.write_bytes(path.read_bytes() + b" ")
    elif damage == "receipt":
        state["receipt"]["usage"]["input_tokens"] += 1
        pilot._save(state_path, state)
    elif damage == "cleanup":
        owner = pilot._load(s.root / "owned-child.json")
        owner.update(phase="cleanup_unresolved", tree_reaped=False, owner_reaped=False)
        pilot._save(s.root / "owned-child.json", owner)
    elif damage == "publication_lost":
        s.api.lost = "output"
    captured = capsys.readouterr()
    assert PRIVATE not in captured.out + captured.err
    before = list(s.api.calls)
    code, record = boundary(s, capsys, monkeypatch, "--retain")
    accepted = {"supported", "absent", "failed_withheld", "grade_bytes", "grade_identity"}
    if damage in accepted:
        assert code == 0 and record["outcome"] == "acknowledged"
        receipt = pilot._load(cell_root(s) / retained.TERMINAL_RECEIPT)
        assert receipt["terminal_commit"] == s.api.branches[retained.BRANCH]
        tree = s.api.trees[receipt["output_commit"]]
        _, _, prefix = retained._paths(cell)
        manifest = json.loads(tree[prefix + "/" + output.MANIFEST])
        assert manifest["status"] == status and manifest["grade_ready"] is False
        if damage == "failed_withheld":
            assert manifest["files"] == [] and "bound_inference_result" in manifest["missing"]
            assert manifest["withheld"]["artifacts"] == completion["artifacts"]
            assert not any(name.startswith(prefix + "/") and name != prefix + "/" + output.MANIFEST for name in tree)
        else:
            assert tree[prefix + "/step2_inference_results.json"] == s.transport.result_bytes
            assert tree[prefix + "/" + Path(pilot.LEDGER).name] == s.transport.ledger_bytes
            assert tree[prefix + "/" + state["artifacts"]["deliverable_files"][0]["path"]] == DELIVERABLE
            _grade_inputs(s, receipt["terminal_commit"], monkeypatch, damage)
        assert s.api.commits == ["admission", "output", "terminal"]
    else:
        assert code == 2
        if damage == "publication_lost":
            assert record["outcome"] == "unresolved" and s.api.commits == ["admission", "output"]
            receipt = pilot._load(cell_root(s) / retained.TERMINAL_RECEIPT)
            assert receipt["output_commit"] is receipt["terminal_commit"] is None
            assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
            assert s.api.commits == ["admission", "output"]  # No publication retry.
        else:
            assert s.api.calls == before and s.api.commits == ["admission"]
            assert not (cell_root(s) / retained.TERMINAL_RESERVED).exists()
    assert s.envelope.read_bytes() == completion_bytes
    assert pilot._load(state_path)["status"] == status
    assert s.transport.turns == 1 and [call[0] for call in s.transport.calls] == ["prepare", "infer"]
    assert s.api.branches[grading.BRANCH] == retained.BOOTSTRAP
    assert all(PRIVATE.encode() not in data for tree in s.api.trees.values() for data in tree.values())
    emitted = capsys.readouterr()
    assert PRIVATE not in emitted.out + emitted.err
    if damage == "publication_lost":
        select_fresh(s, monkeypatch)
        assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
        assert s.transport.calls == [] and s.api.commits == ["admission", "output"]
