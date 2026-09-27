"""Only the recorded task4 A2 NG reader, using genuine synthetic writers.

The ordinary B2 parent is verified, with C2 terminal control only. Synthetic
failure bytes, receipts and revisions are not live evidence or authority.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_budget_pilot_ungraded as ungraded
import step8_grade as step8
from core.cost_receipts import BUCKET_PROBLEM_SOLVING, CallUsage, CostReceiptLedger, load_receipt_price_table
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as approval
from . import test_codex_budget_pilot_task3_a1_readout as a1_reader
from . import test_codex_budget_pilot_task3_c_readout as c_reader
from . import test_codex_budget_pilot_task4_failed_grading as failed
from . import test_codex_budget_pilot_task4_ordinary_readout as ordinary_reader
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — live boundaries blocked

CELL = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r2"
PARENT = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2"
REQUEST = "8f2f6edd7bb2fda964d8a24b4532b8af725bcefbb1513d9a60df86e983446fe9"
RUN = {"id": "36298545498", "job": "pilot-live", "attempt": 1}
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{120_000 + offset:040x}" for offset in range(1, 5))
VARIANTS = ("ungraded", "partial_cost", "missing_receipt", "price_missing")


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    assert grading.TASK4_A2_CELL == CELL and grading.TASK4_RETAINED[CELL] == ("36245490377", REQUEST)
    assert ungraded.A2_POLICY == "recorded_task4_failed_a2_no_judge"
    assert readout.TASK4_A2_WRITER_RUN == RUN and CELL not in readout.TASK4_SUCCESSOR_READOUTS
    actual = readout._writer_context(REQUEST)
    assert actual.plan["order"][22:24] == [PARENT, CELL] and len(actual.plan["order"]) == 30
    assert actual.controller_source_sha == WRITER and actual.plan["reviewed_source_sha"] == PRODUCER
    assert actual.terminal_revision == "" and actual.terminal_request == REQUEST
    assert grading._model_free_context(actual) and len({WRITER, PRODUCER, OBSERVER}) == 3
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    # Create an actual synthetic native failure before inherited runtime blocks.
    # Do not reclassify a successful row or supply a fabricated child receipt.
    prototype = grading.compile_request("pilot/" + CELL, PRODUCER, TERMINAL)
    error_row, native_ledger = failed._failed_row(prototype)
    prefix = ordinary_reader.history.__wrapped__(tmp_path_factory, _variants=("graded",))
    initial = next(prefix)["B_r2"]
    directory = tmp_path_factory.mktemp("task4-a2-reader-history")
    capture = _Capture()
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["graded"]
            shared = SimpleNamespace(rows={}, previous_context=previous.context,
                previous_revision=previous.revision, previous_path=previous.path,
                backing_cell=initial.previous_context.cell, backing_revision=initial.previous_revision,
                backing_path=initial.previous_path, historical_path=initial.historical_path,
                older_paths={initial.backing_path, initial.ng_path, initial.a2_path, initial.intrinsic_path})
            assert previous.context.cell["cell_id"] == PARENT
            assert shared.backing_cell["cell_id"] == readout.TASK4_C2_CELL
            for variant in VARIANTS:
                destination = directory / variant
                destination.mkdir()
                row, ledger_bytes = copy.deepcopy(error_row), native_ledger
                if variant in {"partial_cost", "price_missing"}:
                    prices = copy.deepcopy(writer.SYNTHETIC_PRICE_TABLE)
                    if variant == "partial_cost":
                        prices["providers"] = {"azure:gpt-5.4": prices["providers"]["azure:test-model"]}
                    price_path = destination / "synthetic-prices.json"
                    price_path.write_text(json.dumps(prices), encoding="utf-8")
                    with CostReceiptLedger(destination / "synthetic.sqlite3", run_id=prototype.cell["run_id"],
                                           price_table=load_receipt_price_table(price_path)) as ledger:
                        ledger.reserve(call_id="settled", task_id=prototype.cell["task_id"], stage="generation",
                            retry_kind="none", provider="azure", requested_model="gpt-5.4")
                        ledger.settle("settled", usage=CallUsage(input_tokens=17, cached_input_tokens=5,
                            output_tokens=9, reasoning_tokens=4), resolved_model="gpt-5.4")
                        if variant == "partial_cost":
                            ledger.reserve(call_id="unsettled", task_id=prototype.cell["task_id"], stage="generation",
                                retry_kind="none", provider="azure", requested_model="gpt-5.4")
                        ledger_path = destination / "synthetic.jsonl"
                        ledger.export_jsonl(ledger_path)
                        row["problem_solving_cost"] = ledger.receipt_for(
                            prototype.cell["task_id"], BUCKET_PROBLEM_SOLVING).as_dict()
                        ledger_bytes = ledger_path.read_bytes()
                elif variant == "missing_receipt":
                    row["problem_solving_cost"] = None
                api = copy.deepcopy(previous.api)
                assert not {CLAIM, OUTPUT, TERMINAL, ADVANCED}.intersection(api.trees)
                seeded = SimpleNamespace(context=prototype, api=api)
                with patch.context() as seed:
                    for key, value in {"SOURCE": PRODUCER, "CLAIM": CLAIM, "OUTPUT": OUTPUT, "TERMINAL": TERMINAL}.items():
                        seed.setattr(base, key, value)
                    base._seed_outputs(seeded, destination, failed=True, producer_row=row,
                        producer_ledger=ledger_bytes, producer_receipt=row["problem_solving_cost"], reason="child_nonzero_exit")
                cp, tp, ip = retained._paths(prototype.cell)
                parent_input = initial.input_terminal
                parent_bytes = api.trees[parent_input][retained._paths(previous.context.cell)[1]]
                parent = pilot._json_object(parent_bytes)
                seeded.claim["binding"]["github_run"] = {"id": "36245490377", "job": "cell", "attempt": 1}
                seeded.claim["expected_parent"] = parent_input
                seeded.claim["predecessor"] = {"cell_id": PARENT, "terminal_commit": parent_input,
                    "terminal_sha256": pilot._identity(parent_bytes)["sha256"], "output_commit": parent["output_commit"],
                    "manifest_sha256": parent["manifest_identity"]["sha256"]}
                seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                files = {name: data for name, data in api.trees[OUTPUT].items() if name.startswith(ip + "/")}
                api.seed(CLAIM, parent_input, {cp: retained._encoded(seeded.claim)})
                api.seed(OUTPUT, CLAIM, files)
                api.seed(TERMINAL, OUTPUT, {tp: retained._encoded(seeded.terminal)})
                api.branches[retained.BRANCH] = TERMINAL
                api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
                request = pilot._digest(seeded.terminal["completion"])
                assert request != REQUEST  # Synthetic bytes never impersonate the recorded completion.
                patch.setitem(grading.TASK4_RETAINED, CELL, ("36245490377", request))
                current = SimpleNamespace(api=api, context=readout._writer_context(request), request=request,
                    root=destination / "record", workflow=workflow)
                current.transport = policy._SourceOnlyChild(current)
                with patch.context() as selected:
                    selected.setattr(base, "OUTPUT", OUTPUT)
                    selected.setenv("HF_TOKEN", base.TOKEN)
                    base._synthetic_rubric(current, selected)
                    approval._authorize(current, destination, selected, RUN["id"])
                    def no_judge(*args, **kwargs):
                        raise AssertionError("model-free A2 writer invoked a judge or rubric")
                    for name in ("_entry_contract", "_stage_rubric"):
                        selected.setattr(grading, name, no_judge)
                    selected.setattr(current.transport, "process", no_judge)
                    api.events.clear()
                    with redirect_stdout(capture.out), redirect_stderr(capture.err):
                        for phase in ("prepare", "record-ungraded"):
                            code, observed = base.invoke(current, capture, phase, terminal=request)
                            assert code == 0, (phase, observed, current.diagnostic)
                assert api.events == ["grade_claim", "grade_output"] and current.transport.calls == 0
                revision = api.branches[grading.BRANCH]
                path = grading._paths(current.context.cell)[1]
                terminal = pilot._json_object(api.trees[revision][path])
                assert terminal["binding"]["github_run"] == RUN and terminal["binding"]["policy"] == ungraded.A2_POLICY
                assert terminal["outcome"] == "ungraded" and terminal["model_invoked"] is False
                assert not {"child", "files", "score", "verdict"}.intersection(terminal)
                shared.rows[variant] = SimpleNamespace(api=api, context=current.context, request=request,
                    revision=revision, path=path, terminal=terminal)
            yield shared
    finally:
        prefix.close()


SCENARIOS = (*VARIANTS, "advanced", "replay", "plan", "closed_registry",
    "writer", "producer", "run", "job", "attempt", "typed_attempt", "float_attempt", "policy", "config", "grader_config",
    "grader_hash", "renderer", "approval", "cell", "record_type", "outcome", "model", "score", "child", "files",
    "recorder_zero", "recorder_invoice", "recorder_http", "completion_status", "completion_type", "completion_receipt",
    "completion_denominator", "inference_missing", "claim_hash", "claim_bytes", "claim_type", "claim_float",
    "claim_extra", "claim_format", "claim_history", "claim_carried_bytes", "terminal_history",
    "inference_run", "inference_source", "inference_config", "inference_predecessor", "inference_parent",
    "inference_ack", "inference_cleanup", "inference_deliverables", "inference_manifest", "inference_result", "inference_ledger",
    "previous_run", "previous_writer", "previous_source", "previous_grader_hash", "previous_config", "previous_renderer",
    "previous_cleanup", "previous_no_child", "previous_format", "previous_receipt", "previous_claim", "previous_claim_type",
    "previous_claim_float", "previous_hash", "previous_carried", "previous_carried_bytes", "previous_cell", "previous_size",
    "previous_size_float", "previous_missing", "parent_claim_alias", "parent_terminal_alias",
    "backing_missing", "backing_bytes", "backing_history", "backing_carried", "backing_carried_bytes", "backing_hash",
    "backing_alias", "parent_claim_alias_selected_claim", "parent_claim_alias_selected_terminal",
    "older_control_alias_selected_claim", "older_control_alias_selected_terminal", "whole_inference_observation",
    "parent_entry_mismatch", "ordinal", "ref", "inference_ref", "host_ref", "observer_writer", "observer_producer",
    "observer_source", "source_preflight", "paid", "rerun", "producer_override", "wrong_phase", "private_target", "lost_response")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fixed_task4_a2_ungraded_readout(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["partial_cost"])
    monkeypatch.setitem(grading.TASK4_RETAINED, CELL, ("36245490377", row.request))
    api, terminal, context = copy.deepcopy(row.api), copy.deepcopy(row.terminal), copy.deepcopy(row.context)
    revision, path = row.revision, row.path
    claim_path = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
    previous_revision, previous_path = history.previous_revision, history.previous_path
    previous = pilot._json_object(api.trees[previous_revision][previous_path])
    previous_claim_path = grading._paths(history.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][previous_claim_path])
    changed_previous = False
    if scenario == "advanced":
        api.seed(ADVANCED, revision, {"unrelated/PRIVATE": b"PRIVATE"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = ADVANCED
    elif scenario in {"writer", "producer", "config", "grader_config", "approval", "policy", "cell"}:
        key = {"writer": "controller_source_sha", "producer": "source_sha", "config": "config_sha256",
               "grader_config": "grader_config_sha256", "approval": "approval_request_sha256",
               "policy": "policy", "cell": "cell_id"}[scenario]
        terminal["binding"][key] = ungraded.POLICY if scenario == "policy" else "PRIVATE"
    elif scenario in {"run", "job", "attempt", "typed_attempt", "float_attempt"}:
        key, value = {"run": ("id", "36298545499"), "job": ("job", "grade"), "attempt": ("attempt", 2),
                      "typed_attempt": ("attempt", True), "float_attempt": ("attempt", 1.0)}[scenario]
        terminal["binding"]["github_run"][key] = value
        terminal["binding"]["approval_request_sha256"] = grading._context_approval(context, terminal["binding"]["github_run"])
    elif scenario in {"grader_hash", "renderer"}:
        entry = terminal["binding"]["predecessor_entry"]
        if scenario == "grader_hash":
            entry["grader_source_hash"] = "9" * 64
        else:
            entry["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
    elif scenario in {"record_type", "outcome", "model", "score", "child", "files"}:
        key, value = {"record_type": ("format", grading.RESULT_FORMAT), "outcome": ("outcome", "graded"),
            "model": ("model_invoked", True), "score": ("score", 0), "child": ("child", {"entry_invoked": False}),
            "files": ("files", [])}[scenario]
        terminal[key] = value
    elif scenario.startswith("recorder_"):
        key, value = {"recorder_zero": ("known_cost_usd", 0), "recorder_invoice": ("invoice_complete", True),
                      "recorder_http": ("http_request_count", 0)}[scenario]
        terminal["recorder_accounting"][key] = value
    elif scenario.startswith("completion_"):
        if scenario == "completion_receipt":
            terminal["inference_completion"]["receipt"]["known_cost_usd"] = 0
        else:
            key, value = {"completion_status": ("status", "succeeded"), "completion_type": ("exit_code", True),
                          "completion_denominator": ("denominator", 1)}[scenario]
            terminal["inference_completion"][key] = value
    elif scenario == "inference_missing":
        terminal["inference_missing"] = ["PRIVATE"]
    elif scenario == "claim_extra":
        claim["extra"] = "PRIVATE"
    elif scenario == "claim_format":
        claim["format"] = grading.CLAIM_FORMAT
    elif scenario == "claim_history":
        api.writers[revision][claim_path] = revision
    elif scenario == "terminal_history":
        api.writers[revision][path] = terminal["claim_commit"]
    elif scenario.startswith("inference_") and scenario != "inference_ref":
        icp, itp, ip = retained._paths(context.cell)
        original = pilot._json_object(api.trees[TERMINAL][itp])
        original_claim = pilot._json_object(api.trees[CLAIM][icp])
        if scenario == "inference_run":
            original_claim["binding"]["github_run"]["id"] = "36245490378"
        elif scenario in {"inference_source", "inference_config"}:
            original_claim["binding"]["source_sha" if scenario == "inference_source" else "config_sha256"] = "9" * 64
        elif scenario == "inference_predecessor":
            original_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "inference_parent":
            original_claim["expected_parent"] = "9" * 40
        elif scenario == "inference_ack":
            original["publication_acknowledged"] = False
        elif scenario == "inference_cleanup":
            original["completion"]["cleanup_confirmed"] = False
        elif scenario == "inference_deliverables":
            original["completion"]["artifacts"]["deliverables"] = [{"sha256": "9" * 64, "size": 1}]
        else:
            name = {"inference_manifest": output.MANIFEST, "inference_result": "step2_inference_results.json",
                    "inference_ledger": Path(pilot.LEDGER).name}[scenario]
            api.trees[OUTPUT][ip + "/" + name] += b"PRIVATE"
        data = retained._encoded(original_claim)
        for commit in (CLAIM, OUTPUT, TERMINAL):
            api.trees[commit][icp] = data
        original["claim_identity"] = pilot._identity(data)
        data = retained._encoded(original)
        api.trees[TERMINAL][itp] = data
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
    elif scenario in {"previous_run", "previous_writer", "previous_source", "previous_grader_hash", "previous_config",
                      "previous_renderer", "previous_cleanup", "previous_no_child", "previous_format", "previous_receipt"}:
        changed_previous = True
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = "36297122394"
            previous["binding"]["approval_request_sha256"] = grading._context_approval(
                history.previous_context, previous["binding"]["github_run"])
        elif scenario == "previous_renderer":
            previous["binding"]["renderer_fingerprint"]["pymupdf_version"] = "PRIVATE"
        elif scenario in {"previous_cleanup", "previous_no_child"}:
            previous["child"]["cleanup_confirmed" if scenario == "previous_cleanup" else "entry_invoked"] = False
        elif scenario == "previous_format":
            previous["format"] = ungraded.TERMINAL_FORMAT
        else:
            key = {"previous_writer": "controller_source_sha", "previous_source": "source_sha",
                   "previous_grader_hash": "grader_source_hash", "previous_config": "config_hash",
                   "previous_receipt": "publication_receipt_sha256"}[scenario]
            previous["binding"][key] = "9" * (40 if scenario in {"previous_writer", "previous_source"}
                                               else 16 if scenario == "previous_config" else 64)
    elif scenario == "previous_hash":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "previous_carried":
        api.writers[terminal["claim_commit"]][previous_path] = terminal["claim_commit"]
    elif scenario == "previous_carried_bytes":
        api.trees[terminal["claim_commit"]][previous_path] += b" "
    elif scenario == "previous_cell":
        claim["predecessor"]["cell_id"] = readout.TASK4_C2_CELL
    elif scenario in {"previous_size", "previous_size_float"}:
        claim["predecessor"]["size"] = True if scenario == "previous_size" else float(claim["predecessor"]["size"])
    elif scenario == "previous_missing":
        api.trees[previous_revision].pop(previous_path)
    elif scenario == "previous_claim":
        api.trees[previous["claim_commit"]][previous_claim_path] += b" "
    elif scenario in {"parent_claim_alias", "parent_terminal_alias"}:
        claim["expected_parent"] = claim["predecessor"]["revision"] = (
            terminal["claim_commit"] if scenario == "parent_claim_alias" else revision)
    elif scenario.startswith("backing_"):
        if scenario == "backing_missing":
            api.trees[history.backing_revision].pop(history.backing_path)
        elif scenario == "backing_bytes":
            api.trees[history.backing_revision][history.backing_path] += b" "
        elif scenario == "backing_history":
            api.writers[history.backing_revision][history.backing_path] = previous["claim_commit"]
        elif scenario == "backing_carried":
            api.writers[previous["claim_commit"]][history.backing_path] = previous["claim_commit"]
        elif scenario == "backing_carried_bytes":
            api.trees[previous["claim_commit"]][history.backing_path] += b" "
        elif scenario == "backing_hash":
            previous_claim["predecessor"]["sha256"] = "9" * 64
            changed_previous = True
        else:
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = terminal["claim_commit"]
            changed_previous = True
    elif scenario.startswith(("parent_claim_alias_selected_", "older_control_alias_selected_")):
        alias = terminal["claim_commit"] if scenario.endswith("_claim") else revision
        if scenario.startswith("parent_claim_alias_selected_"):
            original_revision = previous["claim_commit"]
            previous["claim_commit"] = alias
            # Carry the actual parent claim and old terminal at the alias so
            # refusal proves distinctness, not a missing-file shortcut.
            for member in (previous_claim_path, history.backing_path):
                api.trees[alias][member] = api.trees[original_revision][member]
                api.writers[alias][member] = alias if member == previous_claim_path else history.backing_revision
            api.writers[previous_revision][previous_claim_path] = alias
        else:
            api.trees[alias][history.backing_path] = api.trees[history.backing_revision][history.backing_path]
            api.writers[alias][history.backing_path] = alias
            api.writers[previous["claim_commit"]][history.backing_path] = alias
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = alias
        changed_previous = True
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            other = compile_writer(request)
            if other.cell["cell_id"] == CELL:
                other.plan["order"][22:24] = [CELL, PARENT]
            return other
        monkeypatch.setattr(readout, "_writer_context", wrong_order)
    elif scenario == "ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif scenario == "inference_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif scenario == "private_target":
        api.private = False
    elif scenario == "lost_response":
        api.read_fail = True

    if changed_previous or scenario in {"previous_claim_type", "previous_claim_float"}:
        data = a1_reader._store_grade(api, previous_revision, previous_path, previous, previous_claim)
        if scenario in {"previous_claim_type", "previous_claim_float"}:
            previous_claim["binding"]["github_run"]["attempt"] = True if scenario == "previous_claim_type" else 1.0
            encoded = retained._encoded(previous_claim)
            for commit in (previous["claim_commit"], previous_revision):
                api.trees[commit][previous_claim_path] = encoded
            previous["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(previous)
            api.trees[previous_revision][previous_path] = data
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][previous_path] = data
        claim["predecessor"].update(pilot._identity(data))
    a1_reader._store_grade(api, revision, path, terminal, claim)
    if scenario == "claim_hash":
        terminal["claim_identity"]["sha256"] = "9" * 64
        api.trees[revision][path] = retained._encoded(terminal)
    elif scenario == "claim_bytes":
        api.trees[terminal["claim_commit"]][claim_path] += b" "
    elif scenario == "claim_carried_bytes":
        api.trees[revision][claim_path] += b" "
    elif scenario in {"claim_type", "claim_float"}:
        claim["binding"]["github_run"]["attempt"] = True if scenario == "claim_type" else 1.0
        data = retained._encoded(claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][claim_path] = data
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[revision][path] = retained._encoded(terminal)

    def forbidden(*args, **kwargs):
        pytest.fail("A2 NG reader crossed a model, rubric, auth, ordinary projection or write boundary")
    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "inspect_branch", "_entry_contract", "_stage_rubric"):
        monkeypatch.setattr(grading, name, forbidden)
    for name in ("create_commit", "create_branch"):
        monkeypatch.setattr(api, name, forbidden)
    monkeypatch.setattr(ungraded, "record", forbidden)
    monkeypatch.setattr(ungraded, "prepare_record", forbidden)
    monkeypatch.setattr(adapter, "materialize_pilot_grading_input", forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    monkeypatch.setattr(step8, "main", forbidden)
    monkeypatch.setattr(base.Child, "process", forbidden)
    monkeypatch.setattr(readout, "_projection", forbidden)
    monkeypatch.setattr(readout, "_verify_predecessor", forbidden)
    monkeypatch.setattr(readout._ReadOnlyGrade, "allow_verified_files", forbidden)
    readers, ordinary, records = [], [], []
    initialize, ordinary_terminal, record_terminal = readout._ReadOnlyGrade.__init__, grading._grade_terminal, ungraded.verify_terminal
    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)
    def verify_ordinary(api, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] == PARENT
        ordinary.append(current.cell["cell_id"])
        return ordinary_terminal(api, repo, revision, current, *args, **kwargs)
    def verify_record(api, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] == CELL
        records.append(current.cell["cell_id"])
        return record_terminal(api, repo, revision, current, *args, **kwargs)
    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(grading, "_grade_terminal", verify_ordinary)
    monkeypatch.setattr(ungraded, "verify_terminal", verify_record)
    if scenario == "whole_inference_observation":
        bind_retained = readout._ReadOnlyGrade.bind_retained
        def wrong_observation(api, binding, current, *args, **kwargs):
            observed = bind_retained(api, binding, current, *args, **kwargs)
            return {**observed, "extra": True} if current.cell["cell_id"] == CELL else observed
        monkeypatch.setattr(readout._ReadOnlyGrade, "bind_retained", wrong_observation)
    elif scenario == "parent_entry_mismatch":
        verified_grade = readout._verified_grade
        def wrong_entry(api, current, *args, **kwargs):
            verified, entry, observed = verified_grade(api, current, *args, **kwargs)
            return verified, {**entry, "config_hash": "9" * 16}, observed
        monkeypatch.setattr(readout, "_verified_grade", wrong_entry)
    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
        "GITHUB_RUN_ID": "900042", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
        monkeypatch.delenv(key, raising=False)
    if scenario == "observer_source":
        monkeypatch.setenv("PILOT_WORKFLOW_SHA", "9" * 40)
    elif scenario == "paid":
        monkeypatch.setenv("PILOT_GRADE_PAID_APPROVAL", "true")
    elif scenario == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif scenario == "host_ref":
        monkeypatch.setenv("GITHUB_REF", "refs/heads/PRIVATE")
    phase = "plan" if scenario in {"plan", "closed_registry"} else "claim" if scenario == "wrong_phase" else "readout"
    if phase == "plan":
        writer._workflow_contract()
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        monkeypatch.setattr(retained, "_session", forbidden)
    root = tmp_path / "readout"
    args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", source,
            "--terminal-revision", row.request, "--root", str(root), "--phase", phase]
    if scenario == "producer_override":
        args.extend(["--producer-source-sha", PRODUCER])
    def require_source(plan, parent):
        assert plan["reviewed_source_sha"] == OBSERVER
        if scenario == "source_preflight":
            raise ValueError(c_reader.PRIVATE)
    transport = SimpleNamespace(require_source=require_source)
    api.calls.clear()
    api.reads.clear()
    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches, api.events))
    code = grading.main(args, _test_api=api, _test_transport=transport)
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert len(text.splitlines()) == 1
    assert all(private not in text for private in ("PRIVATE", base.TOKEN, api.repo, str(tmp_path), "https://", "Traceback"))
    public = json.loads(text)
    assert (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    assert public["remote_mutation_possible"] is public["judge_entry_requested"] is public["inference_requested"] is False
    assert public["automatic_retry"] is public["invoice_complete"] is False and public["http_request_count"] is None
    assert public["cell_id"] == CELL and public["grade_writer_run"] == RUN
    assert public["grade_writer_source_sha"] == WRITER and public["inference_producer_source_sha"] == PRODUCER
    downloads = {("download", commit, name) for op, commit, name, _ in api.reads if op == "download"}
    originals = {("download", OUTPUT, retained._paths(context.cell)[2] + "/" + name)
                 for name in ("step2_inference_results.json", Path(pilot.LEDGER).name)}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        if scenario == "closed_registry":
            requests = a1_reader._unregistered_requests()
            assert len(requests) == 9 and row.request not in requests
            assert set(requests) == {*(record[1] for record in grading.TASK5_RETAINED.values()), "9" * 64, "9" * 40, ""}
            assert CELL not in readout.TASK4_SUCCESSOR_READOUTS and CELL not in readout.TASK3_SUCCESSOR_READOUTS
            assert [cell for cell in context.plan["order"][18:24]
                    if grading._model_free_context(readout._writer_context(grading.TASK4_RETAINED[cell][1]))] == [
                        grading.TASK4_A1_CELL, CELL]
            for request in requests:
                closed = list(args)
                closed[5] = request
                assert grading.main(closed, _test_api=api) == 2
                refused = capsys.readouterr()
                assert not refused.out and json.loads(refused.err)["outcome"] == "refused"
                assert not api.calls and not root.exists()
    elif scenario in {*VARIANTS, "advanced", "replay"}:
        assert code == 0 and public["outcome"] == "verified_retained_ungraded", public
        assert public["grade_state"] == "ungraded" and public["record_kind"] == "model_free_ungraded"
        assert public["grade_success"] is public["model_requested"] is public["model_invoked"] is False
        assert public["score"] is public["coverage"] is None and public["scored_tasks"] == public["task_rows"] == 0
        assert public["expected_tasks"] == 1 and public["inference_task_status"] == "error"
        assert public["inference_completion"] == row.terminal["inference_completion"]
        assert public["inference_completion"]["denominator"] == 30
        assert public["inference_completion"]["other_cells_not_run"] == 29
        assert public["inference_completion"]["status"] == "failed"
        assert public["inference_completion"]["artifacts"]["deliverables"] == []
        assert public["inference_missing"] == row.terminal["inference_missing"]
        assert public["inference_terminal"] == TERMINAL and public["inference_output_commit"] == OUTPUT
        assert public["grade_revision"] == revision and public["file_identities"] == []
        assert not {"child", "verdict", "rubric_items", "total_max"}.intersection(public)
        assert public["recorder_accounting"] == {"status": "not_measured", "known_cost_usd": None,
            "estimated_cost_usd": None, "invoice_complete": False, "http_request_count": None}
        assert public["recorded_task_cost"] is public["recorded_summary_cost"] is public["ledger_derived_cost"] is None
        costs = public["inference_accounting"]
        assert costs["recorded_summary_cost"] is None
        if scenario == "missing_receipt":
            assert costs["recorded_task_cost"] is None and public["inference_completion"]["receipt"] is None
        for receipt in costs.values():
            if receipt is not None:
                assert receipt["estimated_cost_usd"] is None and receipt["invoice_complete"] is False
                assert receipt["http_request_count"] is None
                if scenario == "price_missing":
                    assert receipt["missing_reasons"] == ["price_missing"] and receipt["known_cost_usd"] is None
                else:
                    assert "call_reachability_unknown" in receipt["missing_reasons"]
        if scenario in {"partial_cost", "advanced", "replay"}:
            assert costs["recorded_task_cost"]["known_cost_usd"] > 0
            assert costs["recorded_task_cost"] == costs["ledger_derived_cost"]
        assert len(readers) == 2 and ordinary == [PARENT, PARENT] and records == [CELL]
        head = ADVANCED if scenario == "advanced" else revision
        assert public["observed_branch_head"] == head
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        expected_downloads = originals | {("download", history.backing_revision, history.backing_path)}
        allowed_paths = {("paths", head, path)}
        metadata = {("metadata", grading.BRANCH)}
        for current, value, commit in ((context, terminal, revision), (history.previous_context, previous, previous_revision)):
            cp, tp = grading._paths(current.cell)
            cr = value["claim_commit"]
            original_claim = pilot._json_object(api.trees[cr][cp])
            parent_cell = current.plan["cells"][current.plan["order"].index(current.cell["cell_id"]) - 1]
            pp = grading._paths(parent_cell)[1]
            expected_downloads.update({("download", commit, tp), ("download", cr, cp)})
            allowed_paths.update(("paths", commit, member) for member in (tp, cp, *(item["path"] for item in value.get("files", []))))
            allowed_paths.update({("paths", cr, cp), ("paths", cr, pp), ("paths", original_claim["expected_parent"], pp)})
            icp, itp, ip = retained._paths(current.cell)
            ir = value["binding"]["retained"]["terminal_commit"]
            iterminal = pilot._json_object(api.trees[ir][itp])
            metadata.add(("metadata", ir))
            expected_downloads.update({("download", ir, itp), ("download", iterminal["claim_commit"], icp),
                                      ("download", iterminal["output_commit"], ip + "/" + output.MANIFEST)})
            allowed_paths.update({("paths", ir, itp), ("paths", ir, icp), ("paths", iterminal["claim_commit"], icp)})
            for item in iterminal["output_objects"]:
                allowed_paths.update({("paths", ir, item["path"]), ("paths", iterminal["output_commit"], item["path"])})
        assert downloads == expected_downloads and len(downloads) == 13
        assert sum(op == "download" for op, *_ in api.reads) == 42
        actual_paths = {("paths", commit, name) for op, commit, _, members in api.reads if op == "paths" for name in members}
        assert actual_paths <= allowed_paths and {call for call in api.calls if call[0] == "metadata"} == metadata
        assert sum(op == "metadata" for op, *_ in api.calls) == 5
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        assert len({revision, terminal["claim_commit"], previous_revision,
                    previous["claim_commit"], history.backing_revision}) == 5
        backing = pilot._json_object(api.trees[history.backing_revision][history.backing_path])
        parent_input = previous["binding"]["retained"]["output_commit"]
        parent_prefix = retained._paths(history.previous_context.cell)[2]
        for reader in readers:
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            # B2 grade files and inference payloads never receive download grants.
            for commit, member in (*((previous_revision, item["path"]) for item in previous["files"]),
                    (parent_input, parent_prefix + "/step2_inference_results.json"),
                    (parent_input, parent_prefix + "/" + Path(pilot.LEDGER).name)):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
            for commit, member in ((history.backing_revision, grading._paths(history.backing_cell)[0]),
                    (history.backing_revision, retained._paths(history.backing_cell)[1]),
                    (backing["claim_commit"], grading._paths(history.backing_cell)[0]),
                    (backing["binding"]["retained"]["terminal_commit"], retained._paths(history.backing_cell)[1]),
                    *((history.backing_revision, item["path"]) for item in backing["files"]),
                    (OUTPUT, "PRIVATE/arbitrary")):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
                with pytest.raises(output.OutputPublicationRefused):
                    reader.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, paths=[member], expand=True)
            for commit in (grading.BRANCH, retained.BRANCH, TERMINAL, history.previous_context.terminal_revision):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=commit, timeout=1)
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused" and api.calls == calls
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario.startswith(("previous_", "parent_", "backing_", "older_control_")) or scenario in {
                "writer", "producer", "run", "job", "attempt", "typed_attempt", "float_attempt", "policy", "config", "grader_config",
                "grader_hash", "renderer", "approval", "cell", "record_type", "model", "claim_hash", "claim_bytes", "claim_float",
                "claim_type", "claim_extra", "claim_format", "claim_history", "claim_carried_bytes", "ordinal", "whole_inference_observation",
                "inference_run", "inference_source", "inference_config", "inference_predecessor", "inference_parent",
                "inference_ack", "inference_cleanup", "inference_deliverables", "inference_manifest"}:
            assert not downloads.intersection(originals)
        if scenario == "lost_response":
            assert public["http_status"] == 503
    assert all(commit != retained.BRANCH for op, commit in api.calls if op == "metadata")
    assert not (history.older_paths | {history.historical_path}).intersection(name for _, _, name in downloads)
