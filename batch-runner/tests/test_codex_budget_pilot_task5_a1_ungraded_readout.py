"""Only fixed task5 A1 after genuine synthetic task4 A2/B2 writer history."""

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
from . import test_codex_budget_pilot_task4_a2_ungraded_readout as a2_reader
from . import test_codex_budget_pilot_task4_failed_grading as failed
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block live boundaries

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_A_r1"
PARENT = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r2"
BACKING = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2"
REQUEST = "b23da4f1f5e81999039c473d27f3a70cc0d0681672ad08be0f9674b618915c97"
RUN = {"id": "36300073091", "job": "pilot-live", "attempt": 1}
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{130_000 + offset:040x}" for offset in range(1, 5))
VARIANTS = ("ungraded", "partial_cost", "missing_receipt", "price_missing")


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _variants=VARIANTS):
    assert grading.TASK5_A1_CELL == CELL and grading.TASK5_RETAINED[CELL] == ("36247236594", REQUEST)
    assert ungraded.TASK5_POLICY == "task5-a1-model-free-ungraded" and readout.TASK5_A1_WRITER_RUN == RUN
    actual = readout._writer_context(REQUEST)
    assert actual.plan["order"][22:25] == [BACKING, PARENT, CELL] and len(actual.plan["order"]) == 30
    assert actual.controller_source_sha == WRITER and actual.plan["reviewed_source_sha"] == PRODUCER
    assert actual.terminal_revision == "" and actual.requested_terminal == REQUEST
    assert grading._model_free_context(actual) and len({WRITER, PRODUCER, OBSERVER}) == 3
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    prototype = grading.compile_request("pilot/" + CELL, PRODUCER, TERMINAL)
    error_row, native_ledger = failed._failed_row(prototype)  # Before inherited runtime blocks.
    prefix = a2_reader.history.__wrapped__(tmp_path_factory, _variants=("partial_cost",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task5-a1-reader-history")
    capture = _Capture()
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["partial_cost"]
            shared = SimpleNamespace(rows={}, previous_context=previous.context, previous_revision=previous.revision,
                previous_path=previous.path, backing_context=initial.previous_context,
                backing_revision=initial.previous_revision, backing_path=initial.previous_path,
                control_cell=initial.backing_cell, control_revision=initial.backing_revision,
                control_path=initial.backing_path, older_paths=initial.older_paths | {initial.historical_path})
            assert previous.context.cell["cell_id"] == PARENT and shared.backing_context.cell["cell_id"] == BACKING
            for variant in _variants:
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
                        ledger.settle("settled", usage=CallUsage(input_tokens=19, cached_input_tokens=7,
                            output_tokens=11, reasoning_tokens=5), resolved_model="gpt-5.4")
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
                parent_input = previous.terminal["binding"]["retained"]["terminal_commit"]
                parent_bytes = api.trees[parent_input][retained._paths(previous.context.cell)[1]]
                parent = pilot._json_object(parent_bytes)
                seeded.claim["binding"]["github_run"] = {"id": "36247236594", "job": "cell", "attempt": 1}
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
                assert request != REQUEST  # Never impersonate the actual retained bytes.
                patch.setitem(grading.TASK5_RETAINED, CELL, ("36247236594", request))
                current = SimpleNamespace(api=api, context=readout._writer_context(request), request=request,
                    root=destination / "record", workflow=workflow)
                current.transport = policy._SourceOnlyChild(current)
                with patch.context() as selected:
                    selected.setattr(base, "OUTPUT", OUTPUT)
                    selected.setenv("HF_TOKEN", base.TOKEN)
                    base._synthetic_rubric(current, selected)
                    approval._authorize(current, destination, selected, RUN["id"])
                    def no_judge(*args, **kwargs):
                        raise AssertionError("model-free task5 A1 writer invoked a judge or rubric")
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
                assert terminal["binding"]["github_run"] == RUN and terminal["binding"]["policy"] == ungraded.TASK5_POLICY
                assert terminal["outcome"] == "ungraded" and terminal["model_invoked"] is False
                assert not {"child", "files", "score", "verdict"}.intersection(terminal)
                shared.rows[variant] = SimpleNamespace(api=api, context=current.context, request=request,
                    revision=revision, path=path, terminal=terminal)
            yield shared
    finally:
        prefix.close()


BINDING_FIELDS = ("controller_source_sha", "source_sha", "config_sha256", "grader_config_sha256", "policy",
                  "approval_request_sha256", "cell_id", "publication_receipt_sha256")
RUN_CHANGES = {"run": ("id", "36300073092"), "job": ("job", "grade"), "attempt": ("attempt", 2),
               "typed_attempt": ("attempt", True), "float_attempt": ("attempt", 1.0)}
ALIASES = ("parent_terminal", "parent_claim", "backing_terminal", "backing_claim", "control_terminal",
           "parent_input_terminal", "parent_input_claim", "parent_input_output",
           "backing_input_terminal", "backing_input_claim", "backing_input_output")
SCENARIOS = (*VARIANTS, "advanced", "replay", "plan", "closed_registry",
    *("binding_" + field for field in BINDING_FIELDS), *RUN_CHANGES,
    *("parent_binding_" + field for field in BINDING_FIELDS), *("parent_" + key for key in RUN_CHANGES),
    "grader_hash", "renderer", "parent_grader_hash", "parent_renderer", "whole_observation", "parent_entry",
    "record_type", "outcome", "model", "score", "child", "files", "recorder_zero", "recorder_invoice", "recorder_http",
    "completion_status", "completion_type", "completion_receipt", "completion_denominator", "inference_missing",
    "claim_hash", "claim_bytes", "claim_type", "claim_float", "claim_format", "claim_extra", "claim_history", "claim_carried",
    "terminal_history", "parent_type", "parent_model", "parent_score", "parent_child", "parent_claim", "parent_claim_type",
    "parent_claim_float", "parent_claim_format", "parent_missing", "parent_hash", "parent_size", "parent_size_float",
    "parent_cell", "parent_carried", "parent_carried_bytes", "parent_result", "parent_ledger",
    "backing_run", "backing_writer", "backing_source", "backing_config", "backing_renderer", "backing_grader_hash",
    "backing_no_child", "backing_cleanup", "backing_type", "backing_missing", "backing_claim", "backing_history",
    "backing_carried", "backing_carried_bytes", "control_missing", "control_bytes", "control_history", "control_carried",
    "inference_run", "inference_source", "inference_config", "inference_predecessor", "inference_parent",
    "inference_ack", "inference_cleanup", "inference_deliverables", "inference_manifest", "inference_result", "inference_ledger",
    *(f"alias_{kind}_{target}" for kind in ("claim", "terminal") for target in ALIASES),
    *("own_claim_" + part for part in ("terminal", "claim", "output")),
    "ordinal", "ref", "inference_ref", "host_ref", "observer_writer", "observer_producer", "observer_source", "source_preflight",
    "paid", "rerun", "producer_override", "wrong_phase", "private_target", "lost_response", "facade_lost_response")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fixed_task5_a1_ungraded_readout(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["partial_cost"])
    monkeypatch.setitem(grading.TASK5_RETAINED, CELL, ("36247236594", row.request))
    api, terminal, context = copy.deepcopy(row.api), copy.deepcopy(row.terminal), copy.deepcopy(row.context)
    revision, path = row.revision, row.path
    claim_path = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
    pr, pp = history.previous_revision, history.previous_path
    previous = pilot._json_object(api.trees[pr][pp])
    pcp = grading._paths(history.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][pcp])
    br, bp = history.backing_revision, history.backing_path
    backing = pilot._json_object(api.trees[br][bp])
    bcp = grading._paths(history.backing_context.cell)[0]
    backing_claim = pilot._json_object(api.trees[backing["claim_commit"]][bcp])
    changed_parent = changed_backing = False

    if scenario == "advanced":
        api.seed(ADVANCED, revision, {"unrelated/PRIVATE": b"PRIVATE"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = ADVANCED
    elif scenario.startswith(("binding_", "parent_binding_")):
        is_parent = scenario.startswith("parent_")
        target = previous if is_parent else terminal
        target["binding"][scenario.removeprefix("parent_").removeprefix("binding_")] = "PRIVATE"
        changed_parent = is_parent
    elif scenario in RUN_CHANGES or scenario.removeprefix("parent_") in RUN_CHANGES:
        is_parent = scenario.startswith("parent_")
        target, current = (previous, history.previous_context) if is_parent else (terminal, context)
        key, value = RUN_CHANGES[scenario.removeprefix("parent_")]
        target["binding"]["github_run"][key] = value
        target["binding"]["approval_request_sha256"] = grading._context_approval(current, target["binding"]["github_run"])
        changed_parent = is_parent
    elif scenario in {"grader_hash", "renderer", "parent_grader_hash", "parent_renderer"}:
        is_parent = scenario.startswith("parent_")
        entry = (previous if is_parent else terminal)["binding"]["predecessor_entry"]
        if scenario.endswith("grader_hash"):
            entry["grader_source_hash"] = "9" * 64
        else:
            entry["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
        changed_parent = is_parent
    elif scenario in {"record_type", "outcome", "model", "score", "child", "files",
                      "parent_type", "parent_model", "parent_score", "parent_child"}:
        is_parent = scenario.startswith("parent_")
        key, value = {"record_type": ("format", grading.RESULT_FORMAT), "type": ("format", grading.RESULT_FORMAT),
            "outcome": ("outcome", "graded"), "model": ("model_invoked", True), "score": ("score", 0),
            "child": ("child", {"entry_invoked": True}), "files": ("files", [])}[scenario.removeprefix("parent_")]
        (previous if is_parent else terminal)[key] = value
        changed_parent = is_parent
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
    elif scenario in {"claim_format", "claim_extra"}:
        claim["format" if scenario == "claim_format" else "extra"] = grading.CLAIM_FORMAT
    elif scenario == "claim_history":
        api.writers[revision][claim_path] = revision
    elif scenario == "terminal_history":
        api.writers[revision][path] = terminal["claim_commit"]
    elif scenario.startswith("inference_") and scenario != "inference_ref":
        icp, itp, ip = retained._paths(context.cell)
        original = pilot._json_object(api.trees[TERMINAL][itp])
        original_claim = pilot._json_object(api.trees[CLAIM][icp])
        if scenario == "inference_run":
            original_claim["binding"]["github_run"]["id"] = "36247236595"
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
            api.trees[OUTPUT][ip + "/" + name] += b" "
        data = retained._encoded(original_claim)
        api.trees[CLAIM][icp] = data
        original["claim_identity"] = pilot._identity(data)
        data = retained._encoded(original)
        api.trees[TERMINAL][itp] = data
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
    elif scenario in {"parent_missing", "parent_claim", "parent_result", "parent_ledger"}:
        if scenario == "parent_missing":
            api.trees[pr].pop(pp)
        elif scenario == "parent_claim":
            api.trees[previous["claim_commit"]][pcp] += b" "
        else:
            name = "step2_inference_results.json" if scenario == "parent_result" else Path(pilot.LEDGER).name
            api.trees[previous["binding"]["retained"]["output_commit"]][retained._paths(history.previous_context.cell)[2] + "/" + name] += b" "
    elif scenario in {"parent_hash", "parent_size", "parent_size_float", "parent_cell"}:
        key, value = {"parent_hash": ("sha256", "9" * 64), "parent_size": ("size", True),
                      "parent_size_float": ("size", float(claim["predecessor"]["size"])),
                      "parent_cell": ("cell_id", BACKING)}[scenario]
        claim["predecessor"][key] = value
    elif scenario in {"parent_carried", "parent_carried_bytes"}:
        if scenario == "parent_carried":
            api.writers[terminal["claim_commit"]][pp] = terminal["claim_commit"]
        else:
            api.trees[terminal["claim_commit"]][pp] += b" "
    elif scenario.startswith("backing_"):
        if scenario in {"backing_missing", "backing_claim", "backing_history", "backing_carried", "backing_carried_bytes"}:
            if scenario == "backing_missing":
                api.trees[br].pop(bp)
            elif scenario == "backing_claim":
                api.trees[backing["claim_commit"]][bcp] += b" "
            elif scenario == "backing_history":
                api.writers[br][bp] = backing["claim_commit"]
            elif scenario == "backing_carried":
                api.writers[previous["claim_commit"]][bp] = previous["claim_commit"]
            else:
                api.trees[previous["claim_commit"]][bp] += b" "
        else:
            changed_backing = True
            if scenario == "backing_run":
                backing["binding"]["github_run"]["id"] = "36297122394"
                backing["binding"]["approval_request_sha256"] = grading._context_approval(
                    history.backing_context, backing["binding"]["github_run"])
            elif scenario in {"backing_no_child", "backing_cleanup"}:
                backing["child"]["entry_invoked" if scenario == "backing_no_child" else "cleanup_confirmed"] = False
            elif scenario == "backing_type":
                backing["format"] = ungraded.TERMINAL_FORMAT
            elif scenario == "backing_renderer":
                backing["binding"]["renderer_fingerprint"]["pymupdf_version"] = "PRIVATE"
            else:
                key = {"backing_writer": "controller_source_sha", "backing_source": "source_sha",
                       "backing_config": "config_hash", "backing_grader_hash": "grader_source_hash"}[scenario]
                backing["binding"][key] = "9" * (40 if scenario in {"backing_writer", "backing_source"} else 64)
    elif scenario.startswith("control_"):
        if scenario == "control_missing":
            api.trees[history.control_revision].pop(history.control_path)
        elif scenario == "control_bytes":
            api.trees[history.control_revision][history.control_path] += b" "
        elif scenario == "control_history":
            api.writers[history.control_revision][history.control_path] = br
        else:
            api.writers[backing["claim_commit"]][history.control_path] = backing["claim_commit"]
    elif scenario.startswith(("alias_", "own_claim_")):
        targets = {"parent_terminal": pr, "parent_claim": previous["claim_commit"], "backing_terminal": br,
                   "backing_claim": backing["claim_commit"], "control_terminal": history.control_revision}
        for label, current, value in (("parent", history.previous_context, previous), ("backing", history.backing_context, backing)):
            ir = value["binding"]["retained"]["terminal_commit"]
            it = pilot._json_object(api.trees[ir][retained._paths(current.cell)[1]])
            targets.update({label + "_input_terminal": ir, label + "_input_claim": it["claim_commit"],
                            label + "_input_output": it["output_commit"]})
        if scenario.startswith("own_claim_"):
            kind, alias = "claim", {"terminal": TERMINAL, "claim": CLAIM, "output": OUTPUT}[scenario.removeprefix("own_claim_")]
        else:
            _, kind, name = scenario.split("_", 2)
            alias = targets[name]
        # Populate the actual synthetic controls and history at the alias;
        # parent proofs stay genuine, so refusal is not a missing-file shortcut.
        original_revision = terminal["claim_commit"] if kind == "claim" else revision
        for member in (claim_path, pp, *((path,) if kind == "terminal" else ())):
            api.trees[alias][member] = api.trees[original_revision][member]
            api.writers[alias][member] = api.writers[original_revision][member]
        if kind == "claim":
            terminal["claim_commit"] = alias
            api.writers[alias][claim_path] = api.writers[revision][claim_path] = alias
        else:
            revision = alias
            api.writers[alias][path] = alias
            api.branches[grading.BRANCH] = alias
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            current = compile_writer(request)
            if current.cell["cell_id"] == CELL:
                current.plan["order"][23:25] = [CELL, PARENT]
            return current
        monkeypatch.setattr(readout, "_writer_context", wrong_order)
    elif scenario == "ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif scenario == "inference_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif scenario == "private_target":
        api.private = False
    elif scenario == "lost_response":
        api.read_fail = True

    if changed_backing:
        data = a1_reader._store_grade(api, br, bp, backing, backing_claim)
        for commit in (previous["claim_commit"], pr):
            api.trees[commit][bp] = data
        previous_claim["predecessor"].update(pilot._identity(data))
        changed_parent = True
    if changed_parent or scenario in {"parent_claim_type", "parent_claim_float", "parent_claim_format"}:
        data = a1_reader._store_grade(api, pr, pp, previous, previous_claim)
        if scenario in {"parent_claim_type", "parent_claim_float", "parent_claim_format"}:
            if scenario == "parent_claim_format":
                previous_claim["format"] = grading.CLAIM_FORMAT
            else:
                previous_claim["binding"]["github_run"]["attempt"] = True if scenario == "parent_claim_type" else 1.0
            encoded = retained._encoded(previous_claim)
            for commit in (previous["claim_commit"], pr):
                api.trees[commit][pcp] = encoded
            previous["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(previous)
            api.trees[pr][pp] = data
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][pp] = data
        claim["predecessor"].update(pilot._identity(data))
    a1_reader._store_grade(api, revision, path, terminal, claim)
    if scenario == "claim_hash":
        terminal["claim_identity"]["sha256"] = "9" * 64
        api.trees[revision][path] = retained._encoded(terminal)
    elif scenario in {"claim_bytes", "claim_carried"}:
        api.trees[terminal["claim_commit"] if scenario == "claim_bytes" else revision][claim_path] += b" "
    elif scenario in {"claim_type", "claim_float"}:
        claim["binding"]["github_run"]["attempt"] = True if scenario == "claim_type" else 1.0
        data = retained._encoded(claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][claim_path] = data
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[revision][path] = retained._encoded(terminal)

    def forbidden(*args, **kwargs):
        pytest.fail("task5 A1 reader crossed a model, auth, ordinary projection or write boundary")
    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "inspect_branch", "_entry_contract", "_stage_rubric"):
        monkeypatch.setattr(grading, name, forbidden)
    for name in ("create_commit", "create_branch"):
        monkeypatch.setattr(api, name, forbidden)
    for name in ("record", "prepare_record"):
        monkeypatch.setattr(ungraded, name, forbidden)
    monkeypatch.setattr(adapter, "materialize_pilot_grading_input", forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    monkeypatch.setattr(step8, "main", forbidden)
    monkeypatch.setattr(base.Child, "process", forbidden)
    monkeypatch.setattr(readout, "_projection", forbidden)
    monkeypatch.setattr(readout, "_verify_predecessor", forbidden)
    monkeypatch.setattr(readout._ReadOnlyGrade, "allow_verified_files", forbidden)
    readers, facades, ordinary, records, completed = [], [], [], [], []
    initialize, facade_init = readout._ReadOnlyGrade.__init__, readout._Task5A1NativeReads.__init__
    ordinary_terminal, record_terminal = grading._grade_terminal, ungraded.verify_terminal
    original_members = {(OUTPUT, retained._paths(context.cell)[2] + "/" + name)
                        for name in ("step2_inference_results.json", Path(pilot.LEDGER).name)}
    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)
    def remember_facade(facade, selected, parent, current, previous_context):
        facade_init(facade, selected, parent, current, previous_context)
        facades.append(facade)
        assert completed == [PARENT] and ordinary == [BACKING, BACKING]
        assert not original_members.intersection((commit, name) for op, commit, name, _ in api.reads if op == "download")
        assert not original_members.intersection(selected._downloads)
        before = copy.deepcopy((api.calls, api.reads))
        for wrong in (grading.BRANCH, retained.BRANCH, previous_context.terminal_revision, "9" * 40):
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(repo_id=api.repo, repo_type="dataset", revision=wrong, token=base.TOKEN, timeout=1)
        with pytest.raises(output.OutputPublicationRefused):
            facade.repo_info(repo_id="PRIVATE/wrong", repo_type="dataset", revision=current.terminal_revision,
                             token=base.TOKEN, timeout=1)
        control = pilot._json_object(api.trees[history.control_revision][history.control_path])
        deeper = {(history.control_revision, grading._paths(history.control_cell)[0]),
            (control["claim_commit"], grading._paths(history.control_cell)[0]),
            (control["binding"]["retained"]["terminal_commit"], retained._paths(history.control_cell)[1]),
            *((history.control_revision, item["path"]) for item in control["files"]), (OUTPUT, "PRIVATE/arbitrary")}
        denied = {(br, item["path"]) for item in backing["files"]}
        denied.update((backing["binding"]["retained"]["output_commit"], retained._paths(history.backing_context.cell)[2] + "/" + name)
                      for name in ("step2_inference_results.json", Path(pilot.LEDGER).name))
        for commit, member in denied | deeper | original_members:
            with pytest.raises(output.OutputPublicationRefused):
                facade.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=commit, filename=member, cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
        for commit, member in deeper:
            with pytest.raises(output.OutputPublicationRefused):
                facade.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=commit, paths=[member], expand=True)
        assert (api.calls, api.reads) == before
    def verify_ordinary(client, repo, rev, current, *args, **kwargs):
        assert current.cell["cell_id"] == BACKING
        result = ordinary_terminal(client, repo, rev, current, *args, **kwargs)
        ordinary.append(BACKING)
        return result
    def verify_record(client, repo, rev, current, *args, **kwargs):
        assert current.cell["cell_id"] in {CELL, PARENT}
        records.append(current.cell["cell_id"])
        result = record_terminal(client, repo, rev, current, *args, **kwargs)
        completed.append(current.cell["cell_id"])
        return result
    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(readout._Task5A1NativeReads, "__init__", remember_facade)
    monkeypatch.setattr(grading, "_grade_terminal", verify_ordinary)
    monkeypatch.setattr(ungraded, "verify_terminal", verify_record)
    if scenario == "whole_observation":
        bind_retained = readout._ReadOnlyGrade.bind_retained
        def wrong_observation(reader, binding, current, *args, **kwargs):
            value = bind_retained(reader, binding, current, *args, **kwargs)
            return {**value, "extra": True} if current.cell["cell_id"] == CELL else value
        monkeypatch.setattr(readout._ReadOnlyGrade, "bind_retained", wrong_observation)
    elif scenario == "parent_entry":
        verified_ungraded = readout._verified_ungraded
        def wrong_entry(reader, current, *args, **kwargs):
            verified, entry, files = verified_ungraded(reader, current, *args, **kwargs)
            return (verified, {**entry, "config_hash": "9" * 16}, files) if current.cell["cell_id"] == PARENT else (verified, entry, files)
        monkeypatch.setattr(readout, "_verified_ungraded", wrong_entry)
    elif scenario == "facade_lost_response":
        repo_info = readout._ReadOnlyGrade.repo_info
        def lost_before_owner_consumes(reader, **kwargs):
            if facades and reader is readers[0]:
                raise output.OutputPublicationRefused("PRIVATE", http_status=503)
            return repo_info(reader, **kwargs)
        monkeypatch.setattr(readout._ReadOnlyGrade, "repo_info", lost_before_owner_consumes)

    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
        "GITHUB_RUN_ID": "900051", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256",
                "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
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
    args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", source, "--terminal-revision", row.request,
            "--root", str(root), "--phase", phase]
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
    assert all(secret not in text for secret in ("PRIVATE", base.TOKEN, api.repo, str(tmp_path), "https://", "Traceback"))
    public = json.loads(text)
    assert (api.trees, api.writers, api.parents, api.branches, api.events) == frozen
    assert public["remote_mutation_possible"] is public["judge_entry_requested"] is public["inference_requested"] is False
    assert public["automatic_retry"] is public["invoice_complete"] is False and public["http_request_count"] is None
    assert public["cell_id"] == CELL and public["grade_writer_run"] == RUN
    assert public["grade_writer_source_sha"] == WRITER and public["inference_producer_source_sha"] == PRODUCER
    downloads = {(commit, name) for op, commit, name, _ in api.reads if op == "download"}
    assert not history.older_paths.intersection(name for _, name in downloads)
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        if scenario == "closed_registry":
            requests = a1_reader._unregistered_requests()
            assert len(requests) == 6 and row.request not in requests
            assert set(requests) == {*(grading.TASK5_RETAINED[cell][1] for cell in context.plan["order"][27:]), "9" * 64, "9" * 40, ""}
            assert CELL not in readout.TASK4_SUCCESSOR_READOUTS and CELL not in readout.TASK3_SUCCESSOR_READOUTS
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
        assert public["inference_completion"]["denominator"] == 30 and public["inference_completion"]["other_cells_not_run"] == 29
        assert public["inference_completion"]["status"] == "failed" and public["inference_completion"]["artifacts"]["deliverables"] == []
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
            assert costs["recorded_task_cost"]["known_cost_usd"] != previous["inference_completion"]["receipt"]["known_cost_usd"]
        assert len(readers) == 3 and len(facades) == 1
        assert ordinary == [BACKING, BACKING, BACKING] and records == [PARENT, CELL, PARENT]
        assert completed == [PARENT, PARENT, CELL]
        head = ADVANCED if scenario == "advanced" else revision
        assert public["observed_branch_head"] == head
        expected_downloads = original_members | {(history.control_revision, history.control_path)}
        allowed_paths = {(head, path)}
        inputs = []
        for current, value, commit in ((context, terminal, revision), (history.previous_context, previous, pr),
                                        (history.backing_context, backing, br)):
            cp, tp = grading._paths(current.cell)
            cr = value["claim_commit"]
            original_claim = pilot._json_object(api.trees[cr][cp])
            parent_cell = current.plan["cells"][current.plan["order"].index(current.cell["cell_id"]) - 1]
            parent_path = grading._paths(parent_cell)[1]
            expected_downloads.update({(commit, tp), (cr, cp)})
            allowed_paths.update((commit, member) for member in (tp, cp, *(item["path"] for item in value.get("files", []))))
            allowed_paths.update({(cr, cp), (cr, parent_path), (original_claim["expected_parent"], parent_path)})
            icp, itp, ip = retained._paths(current.cell)
            ir = value["binding"]["retained"]["terminal_commit"]
            inputs.append(ir)
            iterminal = pilot._json_object(api.trees[ir][itp])
            expected_downloads.update({(ir, itp), (iterminal["claim_commit"], icp),
                                      (iterminal["output_commit"], ip + "/" + output.MANIFEST)})
            if current.cell["cell_id"] == PARENT:
                expected_downloads.update((iterminal["output_commit"], ip + "/" + name)
                    for name in ("step2_inference_results.json", Path(pilot.LEDGER).name))
            allowed_paths.update({(ir, itp), (ir, icp), (iterminal["claim_commit"], icp)})
            for item in iterminal["output_objects"]:
                allowed_paths.update({(ir, item["path"]), (iterminal["output_commit"], item["path"])})
        assert downloads == expected_downloads and len(downloads) == 20
        assert sum(op == "download" for op, *_ in api.reads) == 88
        actual_paths = {(commit, name) for op, commit, _, members in api.reads if op == "paths" for name in members}
        assert actual_paths <= allowed_paths
        ia1, ia2, ib2 = inputs
        assert [rev for op, rev in api.calls if op == "metadata"] == [grading.BRANCH, ia1, ia2, ib2, ia2, ib2, ia1, ia2, ia2, ib2]
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        assert len({revision, terminal["claim_commit"], pr, previous["claim_commit"], br,
                    backing["claim_commit"], history.control_revision}) == 7
        denied = {(br, item["path"]) for item in backing["files"]}
        denied.update((backing["binding"]["retained"]["output_commit"], retained._paths(history.backing_context.cell)[2] + "/" + name)
                      for name in ("step2_inference_results.json", Path(pilot.LEDGER).name))
        control = pilot._json_object(api.trees[history.control_revision][history.control_path])
        deeper = {(history.control_revision, grading._paths(history.control_cell)[0]),
            (control["claim_commit"], grading._paths(history.control_cell)[0]),
            (control["binding"]["retained"]["terminal_commit"], retained._paths(history.control_cell)[1]),
            *((history.control_revision, item["path"]) for item in control["files"]), (OUTPUT, "PRIVATE/arbitrary")}
        before = copy.deepcopy((api.calls, api.reads))
        for reader in (*readers, *facades):
            assert not any(hasattr(reader, name) for name in ("create_commit", "create_branch", "create_repo", "__getattr__"))
            for commit, member in denied | deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
            for commit, member in deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, paths=[member], expand=True)
            for commit in (grading.BRANCH, retained.BRANCH, ia1, ia2, ib2):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=commit, timeout=1)
        for commit, member in expected_downloads - original_members - {(revision, path), (terminal["claim_commit"], claim_path),
                (TERMINAL, retained._paths(context.cell)[1]), (CLAIM, retained._paths(context.cell)[0]),
                (OUTPUT, retained._paths(context.cell)[2] + "/" + output.MANIFEST)}:
            with pytest.raises(output.OutputPublicationRefused):
                readers[0].hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=commit, filename=member, cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
        assert (api.calls, api.reads) == before
        assert all(not reader._inference_metadata for reader in readers)
        assert not facades[0]._open and not facades[0]._metadata
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused" and api.calls == calls
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        late = {"outcome", "score", "child", "files", "recorder_zero", "recorder_invoice", "recorder_http",
                "completion_status", "completion_type", "completion_receipt", "completion_denominator", "inference_missing",
                "inference_result", "inference_ledger"}
        if scenario not in late:
            assert not original_members.intersection(downloads)
        if scenario in {"lost_response", "facade_lost_response"}:
            assert public["http_status"] == 503
        if scenario == "facade_lost_response":
            assert len(facades) == 1 and not facades[0]._open and not facades[0]._metadata
            assert all(not reader._inference_metadata for reader in readers)
        if scenario.startswith("alias_") and not scenario.endswith(("parent_terminal", "parent_claim")):
            assert completed == [PARENT] and ordinary == [BACKING, BACKING]
    assert all(commit != retained.BRANCH for op, commit in api.calls if op == "metadata")
