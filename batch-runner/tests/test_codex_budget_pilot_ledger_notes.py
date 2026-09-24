"""Real Codex note producers and ledger export, with fake model/HF boundaries.

These synthetic records do not reconstruct either unavailable live payload.
No native runtime, provider, historical claim or remote repository is touched.
"""

from contextlib import ExitStack
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
from core import codex_runner
from core.codex_runtime_config import CodexProviderSettings
from core.codex_task_deadline import (
    ATTEMPT_SECONDS, TOTAL_SECONDS, CodexTaskDeadlineControl, CodexTaskDeadlineStore,
)
from core.cost_projection import project_cost_receipt
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING, CostReceiptLedger, load_receipt_price_table,
)
from .test_codex_budget_pilot_output import (
    COMMIT, PARENT, TOKEN, cell, invoke, offline,  # noqa: F401 - real compiler fixture and offline guards
)

RESERVATION_NOTE = "one Codex turn; the model requests inside it are not individually reported"
DEADLINE_NOTE = "deadline refused before the turn started"
NOT_STARTED_NOTE = "the turn never started"


@pytest.fixture(autouse=True)
def no_native_or_hf(monkeypatch, offline):
    def forbidden(*args, **kwargs):
        pytest.fail("ledger-note regression crossed a live boundary")

    monkeypatch.setattr(codex_runner, "require_pinned_runtime", forbidden)
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "open_runtime", forbidden)
    monkeypatch.setattr(codex_runner, "_descendant_pids", lambda _: set())
    monkeypatch.setattr(codex_runner, "sweep_orphans", lambda _: ())
    monkeypatch.setattr(output, "_hf_client", forbidden)


def produce(cell, tmp_path, monkeypatch, branch="success", *, abandon_note=None):
    """Exercise real reserve/settle/abandon callers, not a note-only JSON fixture."""
    events = []
    with ExitStack() as resources:
        ledger = resources.enter_context(CostReceiptLedger(
            tmp_path / "producer.sqlite3", run_id=cell.cell["run_id"],
            price_table=load_receipt_price_table(),
        ))
        workspace = SimpleNamespace(root=tmp_path / "fake-native", collect_deliverables=lambda: [])
        store = deadline = None
        clock = SimpleNamespace(now=1_000_000.0)
        if branch not in {"turn_not_started", "override"}:
            # Real private deadline persistence, outside the agent-writable /tmp.
            host = Path(resources.enter_context(tempfile.TemporaryDirectory(
                prefix=".ledger-note-deadline-", dir=pilot.ROOT,
            )))
            store = CodexTaskDeadlineStore(
                host / "deadline", run_id=cell.cell["run_id"], experiment_id=cell.cell["run_id"],
                condition_key="condition_a", control=CodexTaskDeadlineControl("A", 1),
                task_ids=[cell.cell["task_id"]], prepared_fingerprint="a" * 64,
                initialize=True, clock=lambda: clock.now,
            )
            resources.callback(store.close)
            deadline = store.for_task(cell.cell["task_id"])
        runner = codex_runner.CodexAgentRunner(
            CodexProviderSettings(endpoint="https://example-account.openai.azure.com/openai/v1/", model="gpt-5.4"),
            cost_ledger=ledger, run_id=cell.cell["run_id"], condition_name="condition_a",
            timeout=ATTEMPT_SECONDS, verify_runtime=False, preflight_auth=False, task_deadline_store=store,
        )
        usage = SimpleNamespace(total=SimpleNamespace(
            input_tokens=17, output_tokens=9, cached_input_tokens=5,
            reasoning_output_tokens=4, cache_write_input_tokens=0,
        ))

        def turn(text):
            # A real reservation must precede even this fake child boundary.
            assert ledger.calls_for(cell.cell["task_id"], bucket=BUCKET_PROBLEM_SOLVING)[0]["state"] == "reserved"
            events.append("turn")
            if branch == "turn_not_started":
                raise RuntimeError("synthetic pre-turn failure")
            return SimpleNamespace(id="synthetic-turn")

        def observed(handle, **kwargs):
            events.append("observation")
            if branch in {"failed_with_usage", "failed_without_usage"}:
                return codex_runner.TurnObservation(
                    failure="synthetic failure, not a live child diagnosis",
                    usage=usage if branch == "failed_with_usage" else None,
                )
            return codex_runner.TurnObservation(result=SimpleNamespace(
                id=handle.id, final_response="Synthetic generated answer.", usage=usage,
            ))

        monkeypatch.setattr(runner, "open_runtime", lambda _: SimpleNamespace(close=lambda: events.append("closed")))
        monkeypatch.setattr(runner, "start_thread", lambda *a, **k: SimpleNamespace(id="synthetic-thread", turn=turn))
        monkeypatch.setattr(runner, "_await_turn", observed)
        if branch == "deadline":
            reserve = runner._reserve_call

            def expires_after_real_reservation(*args, **kwargs):
                call_id = reserve(*args, **kwargs)
                clock.now += TOTAL_SECONDS
                return call_id

            monkeypatch.setattr(runner, "_reserve_call", expires_after_real_reservation)
        if branch == "override":
            call_id = runner._reserve_call(cell.cell["task_id"])
            runner._abandon_call(call_id, abandon_note)
            outcome = codex_runner.CodexRunOutcome(success=False, text="")
        else:
            attempt = deadline.admit_attempt(workspace.root) if deadline is not None else None
            outcome = runner._run_one_turn(
                workspace=workspace, task_text="Synthetic task, never sent to a model.",
                experiment_prompt=None, task_id=cell.cell["task_id"],
                task_deadline=deadline, attempt_index=attempt,
            )
            assert events[-1] == "closed"
        ledger_path = cell.root / cell.cell["roles"]["ledger"]
        digest = ledger.export_jsonl(ledger_path)
        data = ledger_path.read_bytes()
        receipt = ledger.receipt_for(cell.cell["task_id"], BUCKET_PROBLEM_SOLVING).as_dict()
    assert digest == pilot._identity(data)["sha256"]
    exported = [json.loads(line) for line in data.splitlines()]
    assert len(exported) == 1
    row = cell.payload["results"][0]
    row.update(status="success" if outcome.success else "error", content=outcome.text,
               problem_solving_cost=receipt)
    if not outcome.success:
        row["deliverable_files"] = []
    bind(cell, data)
    pilot._finish(cell.root, cell.cell, cell.state, 0 if outcome.success else 1)
    pilot._save(cell.root / cell.cell["roles"]["checkpoint"], cell.state)
    return SimpleNamespace(data=data, row=exported[0], receipt=project_cost_receipt(receipt),
                           outcome=outcome, events=events)


def bind(cell, data):
    (cell.root / cell.cell["roles"]["ledger"]).write_bytes(data)
    cell.payload["cost_ledger"] = {"path": Path(pilot.LEDGER).name, "sha256": pilot._identity(data)["sha256"]}
    cell.seal()


@pytest.mark.parametrize("branch,expected_state,expected_note", [
    ("success", "settled", RESERVATION_NOTE),
    ("failed_with_usage", "settled", RESERVATION_NOTE),
    ("failed_without_usage", "reserved", RESERVATION_NOTE),
    ("deadline", "abandoned", DEADLINE_NOTE),
    ("turn_not_started", "abandoned", NOT_STARTED_NOTE),
])
def test_real_producer_notes_publish_original_bytes_and_preserve_outcome(
    cell, tmp_path, monkeypatch, capsys, branch, expected_state, expected_note,
):
    assert type(output.CODEX_LEDGER_NOTES) is frozenset
    assert output.CODEX_LEDGER_NOTES == {RESERVATION_NOTE, DEADLINE_NOTE, NOT_STARTED_NOTE}
    produced = produce(cell, tmp_path, monkeypatch, branch)
    assert produced.row["state"] == expected_state and produced.row["note"] == expected_note
    assert produced.outcome.success is (branch == "success")
    assert ("turn" in produced.events) is (branch != "deadline")
    output._ledger(produced.data, cell.cell)
    result_before = (cell.root / cell.cell["roles"]["result"]).read_bytes()
    checkpoint_before = (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes()
    completion = ci.completion(cell.plan, cell.cell, execute=True, state=cell.state,
                               inputs=output._checkpoint(cell.root / "ci-inputs.json"), cleanup=True)
    assert completion["invoice_complete"] is False and completion["http_request_count"] is None
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    code, public, _ = invoke(cell, capsys, publish=True)
    assert code == 0 and public["publication_outcome"] == "acknowledged"
    assert public["status"] == ("succeeded" if produced.outcome.success else "failed")
    assert public["accounting"] == produced.receipt["status"]
    prefix = f"cell-outputs/{ci.CAMPAIGN}/{cell.cell['cell_id']}/"
    uploaded = {key.removeprefix(prefix): data for key, data in cell.api.uploaded.items()}
    assert uploaded[Path(pilot.LEDGER).name] == produced.data
    assert uploaded["step2_inference_results.json"] == result_before
    manifest = json.loads(uploaded[output.MANIFEST])
    assert manifest["receipt"] == completion["receipt"] and manifest["status"] == public["status"]
    assert manifest["receipt"]["sha256"] == pilot._digest(produced.receipt)
    assert project_cost_receipt(json.loads(uploaded["step2_inference_results.json"])["results"][0][
        "problem_solving_cost"]) == produced.receipt
    assert manifest["grade_ready"] is False and manifest["grading_launched"] is False
    for record in manifest["files"]:
        assert {key: record[key] for key in ("size", "sha256")} == pilot._identity(uploaded[record["path"]])
    if branch in {"success", "failed_with_usage"}:
        assert manifest["accounting"] == "partial"
        assert manifest["receipt"]["estimated_cost_usd"] is None
        assert "call_reachability_unknown" in produced.receipt["missing_reasons"]
        assert {key: manifest["receipt"]["usage"][key] for key in (
            "input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens",
        )} == {"input_tokens": 17, "output_tokens": 9, "cached_input_tokens": 5, "reasoning_tokens": 4}
    receipt = json.loads((cell.cell_root / output.RECEIPT).read_bytes())
    assert receipt["returned_commit"] == COMMIT and receipt["expected_parent"] == PARENT
    assert receipt["cell"] == manifest
    assert (cell.root / cell.cell["roles"]["ledger"]).read_bytes() == produced.data
    assert (cell.root / cell.cell["roles"]["checkpoint"]).read_bytes() == checkpoint_before


@pytest.mark.parametrize("note", ["provider_refused_429", "deadline.refused_before_turn:v1", "x" * 128])
def test_original_strict_code_notes_remain_compatible(cell, tmp_path, monkeypatch, capsys, note):
    produced = produce(cell, tmp_path, monkeypatch, "override", abandon_note=note)
    assert produced.row["state"] == "abandoned" and produced.row["note"] == note
    output._ledger(produced.data, cell.cell)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    assert invoke(cell, capsys, publish=True)[0] == 0
    assert next(data for path, data in cell.api.uploaded.items() if path.endswith(".jsonl")) == produced.data


@pytest.mark.parametrize("note", [
    "unknown prose is not a code-defined note", RESERVATION_NOTE + " extra",
    "hf_SYNTHETIC_NEVER_A_CREDENTIAL", "https://example.invalid/private?token=synthetic",
    "/private/native/auth.json", "../private/ledger", DEADLINE_NOTE + "\n",
    NOT_STARTED_NOTE + "\t", RESERVATION_NOTE + "\x00", " " + NOT_STARTED_NOTE,
])
def test_unapproved_notes_from_real_export_refuse_before_publication(cell, tmp_path, monkeypatch, capsys, note):
    produced = produce(cell, tmp_path, monkeypatch, "override", abandon_note=note)
    assert produced.row["note"] == note
    with pytest.raises(output.OutputPublicationRefused, match="^unsafe_ledger_note$"):
        output._ledger(produced.data, cell.cell)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    code, _, error = invoke(cell, capsys, publish=True)
    assert code == 2 and "unsafe_ledger_note" in error and note not in error
    assert cell.api.calls == [] and not (cell.cell_root / output.RESERVATION).exists()
    assert (cell.root / cell.cell["roles"]["ledger"]).read_bytes() == produced.data


@pytest.mark.parametrize("field,value,reason", [
    ("provider", RESERVATION_NOTE, "ledger_identity_refused"),
    ("request_sha256", "not-a-hash", "ledger_hash_refused"),
    ("price_table_sha256", "not-a-hash", "ledger_hash_refused"),
    ("input_tokens", -1, "ledger_usage_refused"),
    ("output_tokens", True, "ledger_usage_refused"),
    ("model_cost_usd", "NaN", "ledger_amount_refused"),
    ("model_cost_usd", "-0.1", "ledger_amount_refused"),
    ("run_id", "foreign-cell", "ledger_cell_mismatch"),
    ("auth", "synthetic-secret", "ledger_schema_refused"),
    ("note", [RESERVATION_NOTE], "unsafe_ledger_note"),
])
def test_note_exception_does_not_bypass_other_ledger_guards(
    cell, tmp_path, monkeypatch, capsys, field, value, reason,
):
    produced = produce(cell, tmp_path, monkeypatch)
    row = copy.deepcopy(produced.row)
    row[field] = value
    data = (json.dumps(row) + "\n").encode()
    bind(cell, data)
    with pytest.raises(output.OutputPublicationRefused, match=f"^{reason}$"):
        output._ledger(data, cell.cell)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    code, _, error = invoke(cell, capsys, publish=True)
    assert code == 2 and reason in error
    assert cell.api.calls == [] and not (cell.cell_root / output.RESERVATION).exists()
    assert (cell.root / cell.cell["roles"]["ledger"]).read_bytes() == data


@pytest.mark.parametrize("change", ["bytes", "bound_hash", "accounting"])
def test_export_identity_and_recorded_accounting_still_refuse_changes(
    cell, tmp_path, monkeypatch, capsys, change,
):
    produced = produce(cell, tmp_path, monkeypatch)
    if change == "bytes":
        (cell.root / cell.cell["roles"]["ledger"]).write_bytes(produced.data + b" ")
    else:
        if change == "bound_hash":
            cell.state["artifacts"]["ledger"]["sha256"] = "0" * 64
        else:
            cell.state["accounting"] = "complete"
        pilot._save(cell.root / cell.cell["roles"]["checkpoint"], cell.state)
    before = (cell.root / cell.cell["roles"]["ledger"]).read_bytes()
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    code, _, error = invoke(cell, capsys, publish=True)
    assert code == 2
    if change != "accounting":
        assert "payload_identity_mismatch" in error
    assert cell.api.calls == [] and not (cell.cell_root / output.RESERVATION).exists()
    assert (cell.root / cell.cell["roles"]["ledger"]).read_bytes() == before
