"""Only recorded task5 B1, backed by genuine synthetic A1/A2/B2 history."""

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
from . import test_codex_budget_pilot_task3_a1_readout as controls
from . import test_codex_budget_pilot_task3_c_readout as c_reader
from . import test_codex_budget_pilot_task4_failed_grading as failed
from . import test_codex_budget_pilot_task5_a1_ungraded_readout as a1_reader
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block live boundaries

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_B_r1"
PARENT = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_A_r1"
A2 = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r2"
BACKING = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2"
REQUEST = "dd05f2ed43235b69d9eecfefadfb0a5ebd68d83b31daf38355a4acf6f0a21c5b"
RUN = {"id": "36301611455", "job": "pilot-live", "attempt": 1}
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{140_000 + offset:040x}" for offset in range(1, 5))
VARIANTS = ("ungraded", "partial_cost", "missing_receipt", "price_missing")


@pytest.fixture(scope="module")
def history(tmp_path_factory):
    assert grading.TASK5_B1_CELL == CELL and grading.TASK5_RETAINED[CELL] == ("36248894311", REQUEST)
    assert ungraded.TASK5_B1_POLICY == "task5-b1-model-free-ungraded" and readout.TASK5_B1_WRITER_RUN == RUN
    actual = readout._writer_context(REQUEST)
    assert actual.plan["order"][22:26] == [BACKING, A2, PARENT, CELL] and len(actual.plan["order"]) == 30
    assert actual.controller_source_sha == WRITER and actual.plan["reviewed_source_sha"] == PRODUCER
    assert actual.terminal_revision == "" and actual.requested_terminal == REQUEST
    assert grading._model_free_context(actual) and len({WRITER, PRODUCER, OBSERVER}) == 3
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    prototype = grading.compile_request("pilot/" + CELL, PRODUCER, TERMINAL)
    error_row, native_ledger = failed._failed_row(prototype)
    prefix = a1_reader.history.__wrapped__(tmp_path_factory, _variants=("partial_cost",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task5-b1-reader-history")
    capture = _Capture()
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["partial_cost"]
            shared = SimpleNamespace(rows={}, previous_context=previous.context, previous_revision=previous.revision,
                previous_path=previous.path, a2_context=initial.previous_context, a2_revision=initial.previous_revision,
                a2_path=initial.previous_path, backing_context=initial.backing_context,
                backing_revision=initial.backing_revision, backing_path=initial.backing_path,
                control_cell=initial.control_cell, control_revision=initial.control_revision,
                control_path=initial.control_path, older_paths=initial.older_paths)
            assert previous.context.cell["cell_id"] == PARENT and shared.a2_context.cell["cell_id"] == A2
            assert shared.backing_context.cell["cell_id"] == BACKING
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
                        ledger.settle("settled", usage=CallUsage(input_tokens=23, cached_input_tokens=9,
                            output_tokens=13, reasoning_tokens=6), resolved_model="gpt-5.4")
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
                seeded.claim["binding"]["github_run"] = {"id": "36248894311", "job": "cell", "attempt": 1}
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
                assert request != REQUEST  # Synthetic bytes never impersonate the supplied actual checksum.
                patch.setitem(grading.TASK5_RETAINED, CELL, ("36248894311", request))
                current = SimpleNamespace(api=api, context=readout._writer_context(request), request=request,
                    root=destination / "record", workflow=workflow)
                current.transport = policy._SourceOnlyChild(current)
                with patch.context() as selected:
                    selected.setattr(base, "OUTPUT", OUTPUT)
                    selected.setenv("HF_TOKEN", base.TOKEN)
                    base._synthetic_rubric(current, selected)
                    approval._authorize(current, destination, selected, RUN["id"])
                    def no_judge(*args, **kwargs):
                        raise AssertionError("model-free task5 B1 writer invoked a judge or rubric")
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
                assert terminal["binding"]["github_run"] == RUN and terminal["binding"]["policy"] == ungraded.TASK5_B1_POLICY
                assert terminal["outcome"] == "ungraded" and terminal["model_invoked"] is False
                assert not {"child", "files", "score", "verdict"}.intersection(terminal)
                shared.rows[variant] = SimpleNamespace(api=api, context=current.context, request=request,
                    revision=revision, path=path, terminal=terminal)
            yield shared
    finally:
        prefix.close()


BINDING_FIELDS = ("controller_source_sha", "source_sha", "config_sha256", "grader_config_sha256", "policy",
                  "approval_request_sha256", "cell_id", "publication_receipt_sha256")
RUN_CHANGES = {"run": ("id", "36301611456"), "job": ("job", "grade"), "attempt": ("attempt", 2),
               "typed_attempt": ("attempt", True), "float_attempt": ("attempt", 1.0)}
NG_ROLES = ("selected", "parent", "a2")
ALIASES = ("parent_terminal", "parent_claim", "a2_terminal", "a2_claim", "backing_terminal", "backing_claim",
           "control_terminal", *(f"{role}_input_{part}" for role in ("parent", "a2", "backing")
                                 for part in ("terminal", "claim", "output")))
SCENARIOS = (*VARIANTS, "advanced", "replay", "plan", "closed_registry",
    *(f"{role}:binding:{field}" for role in NG_ROLES for field in BINDING_FIELDS),
    *(f"{role}:run:{field}" for role in NG_ROLES for field in RUN_CHANGES),
    *(f"{role}:entry:{field}" for role in NG_ROLES for field in ("grader_hash", "renderer")),
    *(f"{role}:record:{field}" for role in NG_ROLES for field in ("type", "model", "score", "child", "files", "outcome")),
    *(f"{role}:claim:{field}" for role in NG_ROLES for field in ("type", "float", "format", "bytes", "history", "carried")),
    *(f"{role}:parent:{field}" for role in NG_ROLES for field in ("hash", "size", "size_float", "cell", "carried", "carried_bytes")),
    "whole_observation", "parent_entry", "handoff_missing", "handoff_wrong_owner",
    "recorder_zero", "recorder_invoice", "recorder_http", "completion_status", "completion_type",
    "completion_receipt", "completion_denominator", "inference_missing", "claim_hash", "terminal_history",
    *("backing_" + field for field in ("run", "writer", "source", "config", "renderer", "grader_hash",
        "no_child", "cleanup", "type", "missing", "claim", "history", "claim_type")),
    *("control_" + field for field in ("missing", "bytes", "history", "carried")),
    *("inference_" + field for field in ("run", "source", "config", "predecessor", "parent", "ack", "cleanup",
        "deliverables", "manifest", "result", "ledger")),
    "parent_result", "parent_ledger", "a2_result", "a2_ledger", "parent_input_predecessor", "a2_input_predecessor",
    *(f"alias_{kind}_{target}" for kind in ("claim", "terminal") for target in ALIASES),
    *("own_claim_" + part for part in ("terminal", "claim", "output")),
    "ordinal", "ref", "inference_ref", "host_ref", "observer_writer", "observer_producer", "observer_source",
    "source_preflight", "paid", "rerun", "producer_override", "wrong_phase", "private_target", "lost_response",
    "a1_facade_lost_response", "b1_facade_lost_response")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fixed_task5_b1_ungraded_readout(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["partial_cost"])
    monkeypatch.setitem(grading.TASK5_RETAINED, CELL, ("36248894311", row.request))
    api = copy.deepcopy(row.api)
    nodes = {}
    for role, context, revision, path in (
        ("selected", row.context, row.revision, row.path),
        ("parent", history.previous_context, history.previous_revision, history.previous_path),
        ("a2", history.a2_context, history.a2_revision, history.a2_path),
        ("backing", history.backing_context, history.backing_revision, history.backing_path),
    ):
        terminal = pilot._json_object(api.trees[revision][path])
        claim_path = grading._paths(context.cell)[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
        nodes[role] = SimpleNamespace(context=copy.deepcopy(context), revision=revision, path=path,
            terminal=terminal, claim=claim, claim_path=claim_path)
    selected, parent, a2, backing = (nodes[role] for role in ("selected", "parent", "a2", "backing"))
    context, terminal, claim = selected.context, selected.terminal, selected.claim
    changed, claim_overrides, corrupt_bytes, corrupt_history, remove = {"selected"}, {}, [], [], []

    if ":" in scenario:
        role, kind, field = scenario.split(":")
        node = nodes[role]
        if kind == "binding":
            node.terminal["binding"][field] = "PRIVATE"
            changed.add(role)
        elif kind == "run":
            key, value = RUN_CHANGES[field]
            node.terminal["binding"]["github_run"][key] = value
            node.terminal["binding"]["approval_request_sha256"] = grading._context_approval(
                node.context, node.terminal["binding"]["github_run"])
            changed.add(role)
        elif kind == "entry":
            entry = node.terminal["binding"]["predecessor_entry"]
            if field == "grader_hash":
                entry["grader_source_hash"] = "9" * 64
            else:
                entry["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
            changed.add(role)
        elif kind == "record":
            key, value = {"type": ("format", grading.RESULT_FORMAT), "model": ("model_invoked", True),
                "score": ("score", 0), "child": ("child", {"entry_invoked": True}),
                "files": ("files", []), "outcome": ("outcome", "graded")}[field]
            node.terminal[key] = value
            changed.add(role)
        elif kind == "claim":
            if field in {"type", "float", "format"}:
                claim_overrides[role] = field
                changed.add(role)
            elif field == "history":
                corrupt_history.append((node.revision, node.claim_path, node.revision))
            else:
                corrupt_bytes.append((node.revision if field == "carried" else node.terminal["claim_commit"], node.claim_path))
        elif kind == "parent":
            previous = nodes[{"selected": "parent", "parent": "a2", "a2": "backing"}[role]]
            if field == "carried":
                corrupt_history.append((node.terminal["claim_commit"], previous.path, node.terminal["claim_commit"]))
            elif field == "carried_bytes":
                corrupt_bytes.append((node.terminal["claim_commit"], previous.path))
            else:
                key, value = {"hash": ("sha256", "9" * 64), "size": ("size", True),
                    "size_float": ("size", float(node.claim["predecessor"]["size"])),
                    "cell": ("cell_id", CELL)}[field]
                node.claim["predecessor"][key] = value
                changed.add(role)
    elif scenario == "advanced":
        api.seed(ADVANCED, selected.revision, {"unrelated/PRIVATE": b"PRIVATE"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = ADVANCED
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
    elif scenario == "terminal_history":
        corrupt_history.append((selected.revision, selected.path, terminal["claim_commit"]))
    elif scenario.startswith("backing_"):
        if scenario == "backing_missing":
            remove.append((backing.revision, backing.path))
        elif scenario == "backing_claim":
            corrupt_bytes.append((backing.terminal["claim_commit"], backing.claim_path))
        elif scenario == "backing_history":
            corrupt_history.append((backing.revision, backing.path, backing.terminal["claim_commit"]))
        else:
            changed.add("backing")
            if scenario == "backing_run":
                backing.terminal["binding"]["github_run"]["id"] = "36297122394"
                backing.terminal["binding"]["approval_request_sha256"] = grading._context_approval(
                    backing.context, backing.terminal["binding"]["github_run"])
            elif scenario in {"backing_no_child", "backing_cleanup"}:
                backing.terminal["child"]["entry_invoked" if scenario == "backing_no_child" else "cleanup_confirmed"] = False
            elif scenario == "backing_type":
                backing.terminal["format"] = ungraded.TERMINAL_FORMAT
            elif scenario == "backing_claim_type":
                claim_overrides["backing"] = "type"
            elif scenario == "backing_renderer":
                backing.terminal["binding"]["renderer_fingerprint"]["pymupdf_version"] = "PRIVATE"
            else:
                key = {"backing_writer": "controller_source_sha", "backing_source": "source_sha",
                       "backing_config": "config_hash", "backing_grader_hash": "grader_source_hash"}[scenario]
                backing.terminal["binding"][key] = "9" * (40 if scenario in {"backing_writer", "backing_source"} else 64)
    elif scenario.startswith("control_"):
        if scenario == "control_missing":
            remove.append((history.control_revision, history.control_path))
        elif scenario == "control_bytes":
            corrupt_bytes.append((history.control_revision, history.control_path))
        elif scenario == "control_history":
            corrupt_history.append((history.control_revision, history.control_path, backing.revision))
        else:
            corrupt_history.append((backing.terminal["claim_commit"], history.control_path, backing.terminal["claim_commit"]))
    elif scenario in {"parent_result", "parent_ledger", "a2_result", "a2_ledger"}:
        role, field = scenario.split("_")
        node = nodes[role]
        name = "step2_inference_results.json" if field == "result" else Path(pilot.LEDGER).name
        corrupt_bytes.append((node.terminal["binding"]["retained"]["output_commit"],
                              retained._paths(node.context.cell)[2] + "/" + name))
    elif ((scenario.startswith("inference_") and scenario != "inference_ref")
          or scenario in {"parent_input_predecessor", "a2_input_predecessor"}):
        role = scenario.split("_")[0] if "_input_" in scenario else "selected"
        node = nodes[role]
        icp, itp, ip = retained._paths(node.context.cell)
        ir = node.terminal["binding"]["retained"]["terminal_commit"]
        original = pilot._json_object(api.trees[ir][itp])
        original_claim = pilot._json_object(api.trees[original["claim_commit"]][icp])
        field = "predecessor" if "_input_" in scenario else scenario.removeprefix("inference_")
        if field == "run":
            original_claim["binding"]["github_run"]["id"] = "36248894312"
        elif field in {"source", "config"}:
            original_claim["binding"]["source_sha" if field == "source" else "config_sha256"] = "9" * 64
        elif field == "predecessor":
            original_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif field == "parent":
            original_claim["expected_parent"] = "9" * 40
        elif field == "ack":
            original["publication_acknowledged"] = False
        elif field == "cleanup":
            original["completion"]["cleanup_confirmed"] = False
        elif field == "deliverables":
            original["completion"]["artifacts"]["deliverables"] = [{"sha256": "9" * 64, "size": 1}]
        else:
            name = {"manifest": output.MANIFEST, "result": "step2_inference_results.json",
                    "ledger": Path(pilot.LEDGER).name}[field]
            corrupt_bytes.append((original["output_commit"], ip + "/" + name))
        data = retained._encoded(original_claim)
        api.trees[original["claim_commit"]][icp] = data
        original["claim_identity"] = pilot._identity(data)
        data = retained._encoded(original)
        api.trees[ir][itp] = data
        node.terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
        changed.add(role)
    elif scenario.startswith(("alias_", "own_claim_")):
        targets = {"control_terminal": history.control_revision}
        for role in ("parent", "a2", "backing"):
            node = nodes[role]
            ir = node.terminal["binding"]["retained"]["terminal_commit"]
            it = pilot._json_object(api.trees[ir][retained._paths(node.context.cell)[1]])
            targets.update({role + "_terminal": node.revision, role + "_claim": node.terminal["claim_commit"],
                role + "_input_terminal": ir, role + "_input_claim": it["claim_commit"], role + "_input_output": it["output_commit"]})
        if scenario.startswith("own_claim_"):
            kind, alias = "claim", {"terminal": TERMINAL, "claim": CLAIM, "output": OUTPUT}[scenario.removeprefix("own_claim_")]
        else:
            _, kind, name = scenario.split("_", 2)
            alias = targets[name]
        original_revision = terminal["claim_commit"] if kind == "claim" else selected.revision
        # Keep the ancestor's real synthetic objects/history at the alias;
        # populate B1's controls so a missing-file shortcut cannot pass this case.
        for member in (selected.claim_path, parent.path, *((selected.path,) if kind == "terminal" else ())):
            api.trees[alias][member] = api.trees[original_revision][member]
            api.writers[alias][member] = api.writers[original_revision][member]
        if kind == "claim":
            terminal["claim_commit"] = alias
            api.writers[alias][selected.claim_path] = api.writers[selected.revision][selected.claim_path] = alias
        else:
            selected.revision = alias
            api.writers[alias][selected.path] = alias
            api.branches[grading.BRANCH] = alias
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            current = compile_writer(request)
            if current.cell["cell_id"] == CELL:
                current.plan["order"][24:26] = [CELL, PARENT]
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

    # Rehash only the mutated fixed controls and their immediate carried links.
    # No prior test body is called, and no native verifier is bypassed.
    for role in ("backing", "a2", "parent", "selected"):
        if role not in changed:
            continue
        node = nodes[role]
        data = controls._store_grade(api, node.revision, node.path, node.terminal, node.claim)
        if role in claim_overrides:
            field = claim_overrides[role]
            if field == "format":
                node.claim["format"] = grading.CLAIM_FORMAT
            else:
                node.claim["binding"]["github_run"]["attempt"] = True if field == "type" else 1.0
            encoded = retained._encoded(node.claim)
            for commit in (node.terminal["claim_commit"], node.revision):
                api.trees[commit][node.claim_path] = encoded
            node.terminal["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(node.terminal)
            api.trees[node.revision][node.path] = data
        if role != "selected":
            child_role = {"backing": "a2", "a2": "parent", "parent": "selected"}[role]
            child = nodes[child_role]
            for commit in (child.terminal["claim_commit"], child.revision):
                api.trees[commit][node.path] = data
            child.claim["predecessor"].update(pilot._identity(data))
            changed.add(child_role)
    for commit, member in corrupt_bytes:
        api.trees[commit][member] += b" "
    for commit, member, written in corrupt_history:
        api.writers[commit][member] = written
    for commit, member in remove:
        api.trees[commit].pop(member)
    if scenario == "claim_hash":
        terminal["claim_identity"]["sha256"] = "9" * 64
        api.trees[selected.revision][selected.path] = retained._encoded(terminal)

    def forbidden(*args, **kwargs):
        pytest.fail("task5 B1 reader crossed a model, auth, ordinary projection or write boundary")
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
    initialize = readout._ReadOnlyGrade.__init__
    a1_facade_init, b1_facade_init = readout._Task5A1NativeReads.__init__, readout._Task5B1NativeReads.__init__
    ordinary_terminal, record_terminal = grading._grade_terminal, ungraded.verify_terminal
    names = ("step2_inference_results.json", Path(pilot.LEDGER).name)
    original_members = {(OUTPUT, retained._paths(context.cell)[2] + "/" + name) for name in names}
    denied = {(backing.revision, item["path"]) for item in backing.terminal["files"]}
    denied.update((backing.terminal["binding"]["retained"]["output_commit"],
        retained._paths(backing.context.cell)[2] + "/" + name) for name in names)
    # C2's terminal is intrinsically necessary; none of its other history is.
    control = pilot._json_object(row.api.trees[history.control_revision][history.control_path])
    control_cp = grading._paths(history.control_cell)[0]
    control_icp, control_itp, control_ip = retained._paths(history.control_cell)
    control_ir = control["binding"]["retained"]["terminal_commit"]
    control_input = pilot._json_object(row.api.trees[control_ir][control_itp])
    deeper = {(history.control_revision, control_cp), (control["claim_commit"], control_cp),
        (control_ir, control_itp), (control_input["claim_commit"], control_icp),
        *((history.control_revision, item["path"]) for item in control["files"]),
        *((control_input["output_commit"], control_ip + "/" + name) for name in (*names, output.MANIFEST)),
        (OUTPUT, "PRIVATE/arbitrary")}

    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)

    def probe_open(facade, owner, current, previous_context):
        assert facade._open
        own = nodes["selected" if current.cell["cell_id"] == CELL else "parent"]
        own_members = {(own.terminal["binding"]["retained"]["output_commit"],
            retained._paths(current.cell)[2] + "/" + name) for name in names}
        assert not own_members.intersection(owner._downloads)
        assert not original_members.intersection((rev, name) for op, rev, name, _ in api.reads if op == "download")
        before = copy.deepcopy((api.calls, api.reads))
        for wrong in (grading.BRANCH, retained.BRANCH, previous_context.terminal_revision, "9" * 40):
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(repo_id=api.repo, repo_type="dataset", revision=wrong, token=base.TOKEN, timeout=1)
        for wrong in ({"repo_id": "PRIVATE/wrong"}, {"repo_type": "model"}, {"token": "PRIVATE"}):
            kwargs = dict(repo_id=api.repo, repo_type="dataset", revision=current.terminal_revision, token=base.TOKEN, timeout=1)
            kwargs.update(wrong)
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(**kwargs)
        wrong_owner = {(owner.revision, a2.path), (previous_context.terminal_revision, owner._claim)}
        for rev, member in denied | deeper | wrong_owner | original_members | own_members:
            with pytest.raises(output.OutputPublicationRefused):
                facade.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=rev, filename=member, cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
        for rev, member in deeper | wrong_owner:
            with pytest.raises(output.OutputPublicationRefused):
                facade.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=rev, paths=[member], expand=True)
        assert (api.calls, api.reads) == before

    def remember_a1_facade(facade, owner, prior, current, previous_context):
        a1_facade_init(facade, owner, prior, current, previous_context)
        facades.append(facade)
        assert current.cell["cell_id"] == PARENT and completed == [A2] and ordinary == [BACKING, BACKING]
        probe_open(facade, owner, current, previous_context)

    def remember_b1_facade(facade, owner, prior, current, previous_context, proof):
        b1_facade_init(facade, owner, prior, current, previous_context, proof)
        facades.append(facade)
        assert current.cell["cell_id"] == CELL and completed == [A2, A2, PARENT] and ordinary == [BACKING] * 3
        assert proof is facades[0] and not proof._open and not proof._metadata
        assert "_task5_a1_proof" not in prior.__dict__ and "_task5_a1_proof" not in owner.__dict__
        assert facade._owners == (owner, prior, proof._owners[1])
        assert len(facade._revisions) == 3 and all(facade._revisions[index].isdisjoint(other)
            for index in range(3) for other in facade._revisions[index + 1:])
        assert [rev for rev, _ in facade._metadata] == [current.terminal_revision,
            previous_context.terminal_revision, previous_context.terminal_revision,
            a2.terminal["binding"]["retained"]["terminal_commit"], a2.terminal["binding"]["retained"]["terminal_commit"],
            backing.terminal["binding"]["retained"]["terminal_commit"]]
        probe_open(facade, owner, current, previous_context)

    def verify_ordinary(client, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] == BACKING
        result = ordinary_terminal(client, repo, revision, current, *args, **kwargs)
        ordinary.append(BACKING)
        return result

    def verify_record(client, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] in {CELL, PARENT, A2}
        records.append(current.cell["cell_id"])
        result = record_terminal(client, repo, revision, current, *args, **kwargs)
        completed.append(current.cell["cell_id"])
        if ((type(client) is readout._Task5A1NativeReads and current.cell["cell_id"] == PARENT)
                or (type(client) is readout._Task5B1NativeReads and current.cell["cell_id"] == CELL)):
            # Exhausted slots refuse before the caller's finally closes the facade.
            assert client._open and not client._metadata
            before = copy.deepcopy((api.calls, api.reads))
            with pytest.raises(output.OutputPublicationRefused):
                client.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=current.terminal_revision, timeout=1)
            assert (api.calls, api.reads) == before
        return result

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(readout._Task5A1NativeReads, "__init__", remember_a1_facade)
    monkeypatch.setattr(readout._Task5B1NativeReads, "__init__", remember_b1_facade)
    monkeypatch.setattr(grading, "_grade_terminal", verify_ordinary)
    monkeypatch.setattr(ungraded, "verify_terminal", verify_record)
    if scenario == "whole_observation":
        bind_retained = readout._ReadOnlyGrade.bind_retained
        def wrong_observation(reader, binding, current, *args, **kwargs):
            value = bind_retained(reader, binding, current, *args, **kwargs)
            return {**value, "extra": True} if current.cell["cell_id"] == CELL else value
        monkeypatch.setattr(readout._ReadOnlyGrade, "bind_retained", wrong_observation)
    elif scenario in {"parent_entry", "handoff_missing", "handoff_wrong_owner"}:
        verified_ungraded = readout._verified_ungraded
        def wrong_parent(reader, current, *args, **kwargs):
            verified, entry, files = verified_ungraded(reader, current, *args, **kwargs)
            if current.cell["cell_id"] == PARENT:
                if scenario == "parent_entry":
                    entry = {**entry, "config_hash": "9" * 16}
                elif scenario == "handoff_missing":
                    reader.__dict__.pop("_task5_a1_proof")
                else:
                    proof = reader._task5_a1_proof
                    proof._owners = (proof._owners[1], proof._owners[0])
            return verified, entry, files
        monkeypatch.setattr(readout, "_verified_ungraded", wrong_parent)
    elif scenario in {"a1_facade_lost_response", "b1_facade_lost_response"}:
        repo_info = readout._ReadOnlyGrade.repo_info
        def lost_before_owner_consumes(reader, **kwargs):
            target = readers[1] if scenario.startswith("a1_") and len(readers) > 1 else readers[0]
            count = 1 if scenario.startswith("a1_") else 2
            if len(facades) == count and reader is target:
                raise output.OutputPublicationRefused("PRIVATE", http_status=503)
            return repo_info(reader, **kwargs)
        monkeypatch.setattr(readout._ReadOnlyGrade, "repo_info", lost_before_owner_consumes)

    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
        "GITHUB_RUN_ID": "900052", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256", "ACTIONS_ID_TOKEN_REQUEST_URL",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"):
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
    downloads = {(revision, name) for op, revision, name, _ in api.reads if op == "download"}
    assert not history.older_paths.intersection(name for _, name in downloads)
    assert not (denied | deeper).intersection(downloads)
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        if scenario == "closed_registry":
            requests = controls._unregistered_requests()
            assert len(requests) == 7 and row.request not in requests
            assert context.plan["order"][24:] == [PARENT, CELL, grading.TASK5_C1_CELL, grading.TASK5_C2_CELL,
                                                 grading.TASK5_B2_CELL, grading.TASK5_A2_CELL]
            assert set(requests) == {*(grading.TASK5_RETAINED[cell][1] for cell in context.plan["order"][26:]),
                                     "9" * 64, "9" * 40, ""}
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
        assert public["grade_revision"] == selected.revision and public["file_identities"] == []
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
            assert costs["recorded_task_cost"]["known_cost_usd"] != parent.terminal["inference_completion"]["receipt"]["known_cost_usd"]
        assert len(readers) == 4 and len(facades) == 2
        assert ordinary == [BACKING] * 4 and records == [A2, PARENT, A2, CELL, PARENT, A2]
        assert completed == [A2, A2, PARENT, A2, PARENT, CELL]
        head = ADVANCED if scenario == "advanced" else selected.revision
        assert public["observed_branch_head"] == head
        expected_downloads = {(history.control_revision, history.control_path)}
        allowed_paths = {(head, selected.path)}
        inputs, failure_members = [], set()
        for role in ("selected", "parent", "a2", "backing"):
            node = nodes[role]
            current, value, commit = node.context, node.terminal, node.revision
            cp, tp = grading._paths(current.cell)
            cr = value["claim_commit"]
            previous_cell = current.plan["cells"][current.plan["order"].index(current.cell["cell_id"]) - 1]
            previous_path = grading._paths(previous_cell)[1]
            expected_downloads.update({(commit, tp), (cr, cp)})
            allowed_paths.update((commit, member) for member in (tp, cp, *(item["path"] for item in value.get("files", []))))
            allowed_paths.update({(cr, cp), (cr, previous_path), (node.claim["expected_parent"], previous_path)})
            icp, itp, ip = retained._paths(current.cell)
            ir = value["binding"]["retained"]["terminal_commit"]
            inputs.append(ir)
            inference_terminal = pilot._json_object(api.trees[ir][itp])
            expected_downloads.update({(ir, itp), (inference_terminal["claim_commit"], icp),
                                      (inference_terminal["output_commit"], ip + "/" + output.MANIFEST)})
            if role in NG_ROLES:
                members = {(inference_terminal["output_commit"], ip + "/" + name) for name in names}
                expected_downloads.update(members)
                failure_members.update(members)
            allowed_paths.update({(ir, itp), (ir, icp), (inference_terminal["claim_commit"], icp)})
            for item in inference_terminal["output_objects"]:
                allowed_paths.update({(ir, item["path"]), (inference_terminal["output_commit"], item["path"])})
        assert downloads == expected_downloads and len(downloads) == 27
        assert sum(op == "download" for op, *_ in api.reads) == 154
        actual_paths = {(commit, name) for op, commit, _, members in api.reads if op == "paths" for name in members}
        assert actual_paths <= allowed_paths
        ib1, ia1, ia2, ib2 = inputs
        assert [rev for op, rev in api.calls if op == "metadata"] == [grading.BRANCH,
            ib1, ia1, ia2, ib2, ia2, ib2, ia1, ia2, ia2, ib2, ib1, ia1, ia1, ia2, ia2, ib2]
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        grade_revisions = {history.control_revision}
        for node in nodes.values():
            grade_revisions.update({node.revision, node.terminal["claim_commit"]})
        assert len(grade_revisions) == 9
        before = copy.deepcopy((api.calls, api.reads))
        for reader in (*readers, *facades):
            assert not any(hasattr(reader, name) for name in ("create_commit", "create_branch", "create_repo", "__getattr__"))
            for revision, member in denied | deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
            for revision, member in deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, paths=[member], expand=True)
            for revision in (grading.BRANCH, retained.BRANCH, ib1, ia1, ia2, ib2):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=revision, timeout=1)
        selected_members = original_members | {(selected.revision, selected.path),
            (terminal["claim_commit"], selected.claim_path), (TERMINAL, retained._paths(context.cell)[1]),
            (CLAIM, retained._paths(context.cell)[0]), (OUTPUT, retained._paths(context.cell)[2] + "/" + output.MANIFEST)}
        for revision, member in expected_downloads - selected_members:
            with pytest.raises(output.OutputPublicationRefused):
                readers[0].hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=revision, filename=member, cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
        parent_members = {(parent.terminal["binding"]["retained"]["output_commit"],
            retained._paths(parent.context.cell)[2] + "/" + name) for name in names}
        for owner, denied_members in ((readers[1], failure_members - parent_members), (readers[3], failure_members)):
            for revision, member in denied_members:
                with pytest.raises(output.OutputPublicationRefused):
                    owner.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
        assert (api.calls, api.reads) == before
        assert all("_task5_a1_proof" not in reader.__dict__ for reader in readers)
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused" and api.calls == calls
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        late = {"selected:record:" + field for field in ("score", "child", "files", "outcome")}
        late.update({"recorder_zero", "recorder_invoice", "recorder_http", "completion_status", "completion_type",
            "completion_receipt", "completion_denominator", "inference_missing", "inference_result", "inference_ledger"})
        if scenario not in late:
            assert not original_members.intersection(downloads)
        if scenario in {"lost_response", "a1_facade_lost_response", "b1_facade_lost_response"}:
            assert public["http_status"] == 503
        if scenario == "a1_facade_lost_response":
            assert len(facades) == 1
        elif scenario == "b1_facade_lost_response":
            assert len(facades) == 2
        if scenario.startswith("alias_") and not scenario.endswith(("parent_terminal", "parent_claim")):
            assert completed == [A2, A2, PARENT] and ordinary == [BACKING] * 3
    assert all(not facade._open and not facade._metadata for facade in facades)
    assert all(not reader._inference_metadata for reader in readers)
    assert all(revision != retained.BRANCH for op, revision in api.calls if op == "metadata")
