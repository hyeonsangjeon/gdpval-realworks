"""Future CI diagnostics from real Codex/Step2 serialization, never live causes.

Original-input provenance, reviewed source, runtime and child transport are
synthetic. Compiler, dispatcher, producer categories, receipts, fingerprints,
byte checks, cleanup validation and CLI completion/log projection remain real.
"""

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import step2_run_inference as step2
import step8_grade
from core import azure_ai_clients, codex_azure_token, codex_runner
from core.codex_runtime_config import CodexProviderSettings
from core.cost_projection import project_cost_receipt
from core.cost_receipts import BUCKET_PROBLEM_SOLVING, CostReceiptLedger, load_receipt_price_table
from core.inference_manifest import bind_deliverable_file_records
from core.result_fingerprint import inference_result_fingerprint
from .test_codex_budget_pilot import read_plan, read_state, scenario  # noqa: F401
from .test_codex_budget_pilot_ci import CICellChildren, ci_scenario, invoke  # noqa: F401

PREFIX = "CI cell recorded failure category: "
PRIVATE = "hf_SYNTHETIC_DIAGNOSTIC_SECRET /private/native/auth.json https://private.invalid/secret"
UNCHANGED = object()


@pytest.fixture(autouse=True)
def no_runtime_auth_or_publication(monkeypatch):
    from huggingface_hub import HfApi
    from huggingface_hub.utils import _auth, _headers

    def forbidden(*args, **kwargs):
        pytest.fail("failure-category regression crossed a live boundary")

    # Same SDK-independent boundary guards as the retained-cell family. The
    # real runner's constructor/categories need no SDK when runtime/auth are
    # disabled; forbidding a native launch must not require installing it.
    for target, names in (
        (subprocess, ("run", "Popen", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (os, ("system",)), (pilot.time, ("sleep",)),
        (codex_azure_token, ("acquire_token", "get_bearer_token_provider")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                        step8_grade.Grader):
        monkeypatch.setattr(constructor, "__init__", forbidden)
    for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(codex_runner, "require_pinned_runtime", forbidden)
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "open_runtime", forbidden)
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "preflight_auth_command", forbidden)
    monkeypatch.setattr(codex_runner, "_descendant_pids", lambda _: set())
    monkeypatch.setattr(codex_runner, "sweep_orphans", lambda _: ())
    monkeypatch.setattr(output, "_hf_client", forbidden)
    monkeypatch.setattr(output, "publish", forbidden)
    monkeypatch.setattr(_auth, "get_token", forbidden)
    monkeypatch.setattr(_headers, "get_token", forbidden)
    for name in ("repo_info", "create_commit", "create_repo", "create_branch", "hf_hub_download", "whoami"):
        monkeypatch.setattr(HfApi, name, forbidden)


class DiagnosticChildren(CICellChildren):
    """Reuse fake owned children, but produce the row through Codex and Step2."""

    def __init__(self, sources, task_ids):
        super().__init__(sources, task_ids)
        self.producer = "rate_limited"
        self.category = UNCHANGED
        self.corruption = None
        self.child_exit = 1
        self.produced = []

    def _process(self, command, **options):
        completed = super()._process(command, **options)
        if command[1] != "step2_run_inference.py":
            return completed
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"} & options["env"].keys()
        cwd = options["cwd"]
        result_path = cwd / "workspace" / Path(pilot.RESULT).name
        payload = json.loads(result_path.read_bytes())
        prepared = json.loads((cwd / "workspace/step1_tasks_prepared.json").read_bytes())
        config = json.loads((cwd / "pilot-run.json").read_bytes())
        task = prepared["tasks"][0]
        usage = SimpleNamespace(total=SimpleNamespace(
            input_tokens=17, output_tokens=9, cached_input_tokens=5,
            reasoning_output_tokens=4, cache_write_input_tokens=0,
        ))
        with CostReceiptLedger(cwd / "workspace/diagnostic-producer.sqlite3",
                               run_id=payload["run_id"], price_table=load_receipt_price_table()) as ledger:
            runner = codex_runner.CodexAgentRunner(
                CodexProviderSettings(endpoint="https://example-account.openai.azure.com/openai/v1/", model="gpt-5.4"),
                cost_ledger=ledger, run_id=payload["run_id"], condition_name="condition_a",
                timeout=1800, verify_runtime=False, preflight_auth=False,
            )

            def runtime(workspace):
                if self.producer == "runtime_start_failed":
                    raise RuntimeError(PRIVATE)
                return SimpleNamespace(close=lambda: None)

            def observed(handle):
                if self.producer == "success":
                    return codex_runner.TurnObservation(result=SimpleNamespace(
                        id=handle.id, final_response=PRIVATE, usage=usage,
                    ))
                return codex_runner.TurnObservation(failure=PRIVATE, http_status_code=429, usage=usage)

            # Only runtime boundaries are fake; category production is real.
            runner.open_runtime = runtime
            runner.start_thread = lambda *a, **k: SimpleNamespace(
                id="synthetic-thread", turn=lambda _: SimpleNamespace(id="synthetic-turn"),
            )
            runner._await_turn = observed

            def execute(**kwargs):
                kwargs.pop("verbose")
                raw = runner.run(**kwargs)
                self.produced.append(copy.deepcopy(raw))
                if self.category is None:
                    raw.pop("error_category", None)
                elif self.category is not UNCHANGED:
                    raw["error_category"] = self.category
                return raw

            upload = cwd / "workspace/upload"
            row = step2._execute_single_task(
                task, config["condition_a"], SimpleNamespace(execute=execute),
                "codex_foundry", None, "gpt-5.4", run_id=payload["run_id"],
                condition_name="condition_a", upload_root=upload,
            )
            row["problem_solving_cost"] = ledger.receipt_for(task["task_id"], BUCKET_PROBLEM_SOLVING).as_dict()
            ledger_path = cwd / "workspace" / Path(pilot.LEDGER).name
            digest = ledger.export_jsonl(ledger_path)
        payload["cost_ledger"] = {"path": ledger_path.name, "sha256": digest}
        payload["results"] = step2._public_persisted_results(bind_deliverable_file_records([row], upload))
        if self.corruption == "cell":
            payload["results"][0]["task_id"] = self.task_ids[0]
        elif self.corruption == "run":
            payload["run_id"] = "foreign_synthetic_run"
        elif self.corruption == "nonstr_category":
            payload["results"][0]["observability"]["error_category"] = {"private": PRIVATE}
        elif self.corruption == "observability":
            payload["results"][0]["observability"] = [PRIVATE]
        elif self.corruption == "unsafe_field":
            payload["results"][0]["unapproved_private_field"] = PRIVATE
        payload["result_fingerprint"] = inference_result_fingerprint(payload)
        if self.corruption == "fingerprint":
            payload["result_fingerprint"] = "0" * 64
        self.result_bytes = json.dumps(payload, ensure_ascii=False).encode()
        self.ledger_bytes = ledger_path.read_bytes()
        result_path.write_bytes(self.result_bytes)
        if self.corruption == "missing_result":
            result_path.unlink()  # This test-owned synthetic output only.
        return subprocess.CompletedProcess(command, self.child_exit)


@pytest.fixture
def diagnostic_case(ci_scenario, monkeypatch):
    # Explicit synthetic host-version boundary, as in the retained-cell tests;
    # this is not native install/capability evidence.
    real_version = ci.importlib.metadata.version
    monkeypatch.setattr(ci.importlib.metadata, "version", lambda name:
                        "0.147.0" if name in {"openai-codex", "openai-codex-cli-bin"} else real_version(name))
    s = ci_scenario
    # The second synthetic task has no reference files and accepts text output.
    s.selected = s.ids[1] + "_A_r1"
    s.argv[s.argv.index("--cell") + 1] = s.selected
    s.transport = DiagnosticChildren(s.sources, s.ids)
    return s


def diagnostics(caplog):
    return [json.loads(record.getMessage()[len(PREFIX):]) for record in caplog.records
            if record.name == ci.LOG.name and record.getMessage().startswith(PREFIX)]


def assert_final_facts(s, *, status="failed", reason="child_nonzero_exit"):
    plan = read_plan(s)
    cell = next(cell for cell in plan["cells"] if cell["cell_id"] == s.selected)
    state = read_state(s, s.selected)
    record = pilot._load(s.envelope)
    assert record == ci.completion(plan, cell, execute=True, state=state,
                                   inputs=pilot._load(s.root / "ci-inputs.json"), cleanup=True)
    assert (record["status"], record["reason"]) == (status, reason)
    assert record["child_invocations"] == 1 and record["cleanup_confirmed"] is True
    assert record["grading_launched"] is False and record["invoice_complete"] is False
    assert record["http_request_count"] is None and record["other_cells_not_run"] == 29
    assert record["denominator"] == 30 and record["format"] == "codex-budget-ci-cell-completion-v1"
    assert record["artifacts"]["result"] == pilot._identity(s.transport.result_bytes)
    assert record["artifacts"]["ledger"] == pilot._identity(s.transport.ledger_bytes)
    assert pilot._read_bytes(s.root / cell["roles"]["result"]) == s.transport.result_bytes
    assert pilot._read_bytes(s.root / cell["roles"]["ledger"]) == s.transport.ledger_bytes
    receipt = project_cost_receipt(json.loads(s.transport.result_bytes)["results"][0]["problem_solving_cost"])
    assert state["receipt"] == receipt and record["receipt"]["sha256"] == pilot._digest(receipt)
    assert record["receipt"]["estimated_cost_usd"] is None
    assert record["receipt"]["known_cost_usd"] == receipt["known_cost_usd"]
    if s.transport.producer != "runtime_start_failed":
        assert record["receipt"]["status"] == "partial"
        assert record["receipt"]["usage"] == {
            "input_tokens": 17, "output_tokens": 9, "cached_input_tokens": 5,
            "reasoning_tokens": 4, "audio_input_tokens": None, "audio_output_tokens": None,
        }
    assert [(stage, key) for stage, key, _ in s.transport.calls] == [("prepare", s.selected), ("infer", s.selected)]
    for other in plan["cells"]:
        if other["cell_id"] != s.selected:
            assert read_state(s, other["cell_id"]) == pilot._cell_state(plan, other)
    return plan, cell, state, record


@pytest.mark.parametrize("producer,stop", [
    ("rate_limited", None), ("runtime_start_failed", None), ("rate_limited", "timeout"),
])
def test_real_producer_category_reaches_one_ci_log_without_changing_facts(diagnostic_case, caplog, producer, stop):
    s = diagnostic_case
    s.transport.producer, s.transport.stop = producer, stop
    assert invoke(s, "--execute") == 1
    assert s.transport.produced[0]["error_category"] == producer
    expected_status = "stopped" if stop else "failed"
    plan, cell, state, record = assert_final_facts(
        s, status=expected_status, reason="child_timeout_partial_accounting" if stop else "child_nonzero_exit",
    )
    assert diagnostics(caplog) == [{
        "source_sha": "1" * 40, "cell_id": s.selected, "status": expected_status, "error_category": producer,
    }]
    assert len(caplog.records[-1].getMessage()) < 300
    assert PRIVATE not in caplog.text and str(s.host) not in caplog.text
    before_state = copy.deepcopy(state)
    caplog.clear()
    pilot._finish(s.root, cell, copy.deepcopy(state), state["exit_code"])
    assert diagnostics(caplog) == []  # Publisher-style revalidation is silent.
    assert read_state(s, s.selected) == before_state
    assert invoke(s, "--execute", "--resume") == 1
    assert diagnostics(caplog) == []  # No second emission or child for an already finalized cell.
    assert pilot._load(s.envelope) == record


@pytest.mark.parametrize("category,expected", [
    (None, "unavailable"),
    ("future_unknown_category", "unclassified"),
    ("hf_SYNTHETIC_DIAGNOSTIC_SECRET", "unclassified"),
    ("https://private.invalid/secret", "unclassified"),
    ("/private/native/auth.json", "unclassified"),
    ("rate_limited\nPRIVATE", "unclassified"),
    ("rate_limited_private_suffix", "unclassified"),
])
def test_missing_unknown_and_private_categories_are_not_disclosed(diagnostic_case, caplog, category, expected):
    s = diagnostic_case
    s.transport.category = category
    assert invoke(s, "--execute") == 1
    assert_final_facts(s)
    assert diagnostics(caplog) == [{
        "source_sha": "1" * 40, "cell_id": s.selected, "status": "failed", "error_category": expected,
    }]
    assert PRIVATE not in caplog.text and str(s.host) not in caplog.text
    if category is not None:
        assert category not in caplog.text


def test_present_nonstring_category_is_unclassified(diagnostic_case, caplog):
    s = diagnostic_case
    s.transport.corruption = "nonstr_category"
    assert invoke(s, "--execute") == 1
    assert_final_facts(s)
    assert diagnostics(caplog)[0]["error_category"] == "unclassified"
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("exit_code", [0, 1])
def test_success_row_never_supplies_a_child_failure_cause(diagnostic_case, caplog, exit_code):
    s = diagnostic_case
    s.transport.producer, s.transport.child_exit = "success", exit_code
    s.transport.category = "rate_limited"  # Even a stale allowlisted value is not a cause here.
    assert invoke(s, "--execute") == exit_code
    assert_final_facts(s, status="failed" if exit_code else "succeeded",
                       reason="child_nonzero_exit" if exit_code else None)
    assert diagnostics(caplog) == ([{
        "source_sha": "1" * 40, "cell_id": s.selected, "status": "failed", "error_category": "unavailable",
    }] if exit_code else [])
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("corruption", ["fingerprint", "cell", "run", "missing_result", "observability"])
def test_unbound_or_malformed_result_has_no_trusted_diagnostic(diagnostic_case, caplog, corruption):
    s = diagnostic_case
    s.transport.corruption = corruption
    assert invoke(s, "--execute") == (1 if corruption in {"missing_result", "observability"} else 2)
    assert diagnostics(caplog) == []
    assert PRIVATE not in caplog.text and str(s.host) not in caplog.text
    assert len(s.transport.produced) == 1


@pytest.mark.parametrize("change", ["bytes", "idle_owner", "foreign_owner", "unreaped_owner", "log_io"])
def test_diagnostic_rechecks_bytes_and_owned_cleanup_without_rewriting_completion(
    diagnostic_case, caplog, monkeypatch, change,
):
    s = diagnostic_case
    real_publish = ci._publish
    finalized = []

    def publish(path, root, payload):
        real_publish(path, root, payload)
        if payload["status"] != "failed":
            return
        finalized.append(copy.deepcopy(payload))
        plan = read_plan(s)
        if change == "bytes":
            result_path = root / "cells" / s.selected / "checkout" / pilot.RESULT
            result_path.write_bytes(result_path.read_bytes() + b" ")
        elif change in {"idle_owner", "foreign_owner", "unreaped_owner"}:
            owner = pilot._load(root / "owned-child.json")
            if change == "idle_owner":
                owner = pilot._owner_state(pilot._digest(plan))
            elif change == "foreign_owner":
                owner["cell_id"] = plan["order"][0]
            else:
                owner["tree_reaped"] = False
            pilot._save(root / "owned-child.json", owner)

    def log_failure(*args, **kwargs):
        raise RuntimeError(PRIVATE)

    monkeypatch.setattr(ci, "_publish", publish)
    if change == "log_io":
        monkeypatch.setattr(ci.LOG, "warning", log_failure)
    assert invoke(s, "--execute") == 1
    assert len(finalized) == 1 and pilot._load(s.envelope) == finalized[0]
    assert finalized[0]["reason"] == "child_nonzero_exit" and finalized[0]["receipt"]["status"] == "partial"
    assert diagnostics(caplog) == [] and PRIVATE not in caplog.text


def test_unconfirmed_cleanup_never_emits_category(diagnostic_case, caplog):
    s = diagnostic_case
    s.transport.stop = "unresolved"
    assert invoke(s, "--execute") == 2
    record = pilot._load(s.envelope)
    assert record["cleanup_confirmed"] is False and record["status"] == "unresolved"
    assert record["reason"] == "owned_child_cleanup_unconfirmed"
    assert diagnostics(caplog) == [] and PRIVATE not in caplog.text


def test_diagnostic_survives_later_publisher_refusal_without_granting_authority(diagnostic_case, caplog):
    s = diagnostic_case
    s.transport.corruption = "unsafe_field"
    assert invoke(s, "--execute") == 1
    plan, cell, _, record = assert_final_facts(s)
    observed = diagnostics(caplog)
    assert len(observed) == 1 and observed[0]["error_category"] == "rate_limited"
    with pytest.raises(output.OutputPublicationRefused, match="^unsafe_result_fields$"):
        output.prepare(root=s.root, campaign=ci.CAMPAIGN, cell_id=s.selected,
                       source_sha=plan["reviewed_source_sha"], config_sha=cell["config_sha256"])
    assert diagnostics(caplog) == observed and pilot._load(s.envelope) == record
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("options", [(), ("--check-inputs",)])
def test_nonexecution_modes_have_no_diagnostic_or_child(diagnostic_case, caplog, options):
    s = diagnostic_case
    assert invoke(s, *options) == 0
    assert diagnostics(caplog) == [] and s.transport.calls == [] and s.transport.produced == []
    assert pilot._load(s.envelope)["execution_requested"] is False
