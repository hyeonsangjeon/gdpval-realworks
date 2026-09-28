"""Only final B2 ordinary and A2 MODEL-FREE readouts over genuine fixed history.

Synthetic writer bytes, revisions and accounting are not live records or
provider observations. No previous selector or test body runs here.
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
from . import test_codex_budget_pilot_task3_a1_readout as controls
from . import test_codex_budget_pilot_task3_c_readout as c_reader
from . import test_codex_budget_pilot_task4_failed_grading as failed
from . import test_codex_budget_pilot_task5_c2_ungraded_readout as c2_reader
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary

PREFIX = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_"
CELLS = {"b2": PREFIX + "B_r2", "a2": PREFIX + "A_r2", "c2": PREFIX + "C_r2",
    "c1": PREFIX + "C_r1", "b1": PREFIX + "B_r1", "a1": PREFIX + "A_r1",
    "t4a2": "3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r2",
    "t4b2": "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2"}
PROFILES = {
    "b2": (28, "36304692953", "36266871064", "5b942d71fe284b5d2831c01cf17ac17e92857c26ef2dad820b9367d3c8cf0245"),
    "a2": (29, "36306339791", "36277325255", "40a4785b0720dfc271ffe1d148c77c6da9ed5c65a4101b6dc61e69e30ec0dab7"),
}
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
PARENTS = {"a2": "b2", "b2": "c2", "c2": "c1", "c1": "b1", "b1": "a1", "a1": "t4a2", "t4a2": "t4b2"}
CHAIN = ("a2", "b2", "c2", "c1", "b1", "a1", "t4a2", "t4b2")
NG_ROLES = {"a2", "c2", "b1", "a1", "t4a2"}
REVISIONS = {profile: tuple(f"{170_000 + index * 10 + offset:040x}" for offset in range(1, 5))
             for index, profile in enumerate(PROFILES)}
VARIANTS = {"b2": c_reader.VARIANTS, "a2": ("ungraded", "partial_cost", "missing_receipt", "price_missing")}
NAMES = ("step2_inference_results.json", Path(pilot.LEDGER).name)


@pytest.fixture(scope="module")
def history(tmp_path_factory, historical_budget_source):
    assert len({WRITER, PRODUCER, OBSERVER}) == 3
    for profile, (ordinal, run_id, inference_run, request) in PROFILES.items():
        context = readout._writer_context(request)
        assert grading.TASK5_RETAINED[CELLS[profile]] == (inference_run, request)
        assert context.cell["cell_id"] == CELLS[profile] and context.controller_source_sha == WRITER
        assert context.plan["reviewed_source_sha"] == PRODUCER and context.terminal_revision == ""
        assert context.requested_terminal == request and len(context.plan["order"]) == 30
        assert context.plan["order"][21:ordinal + 1] == [readout.TASK4_C2_CELL,
            *(CELLS[role] for role in reversed(CHAIN[CHAIN.index(profile):]))]
        assert readout._writer_run(context) == {"id": run_id, "job": "pilot-live", "attempt": 1}
        assert grading._model_free_context(context) is (profile == "a2")
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert ungraded.TASK5_A2_POLICY == "task5-a2-model-free-ungraded"

    # Build the genuine A2 failure before reused history installs its runner guard.
    prototype = grading.compile_request("pilot/" + CELLS["a2"], PRODUCER, REVISIONS["a2"][2])
    error_row, native_ledger = failed._failed_row(prototype)
    # Reuse genuine C2 writer construction only, not the old 406 test cases.
    prefix = c2_reader.history.__wrapped__(tmp_path_factory, historical_budget_source, _variants=("partial_cost",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task5-final-readout-history")
    capture = _Capture()
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    previous_c2 = initial.rows["partial_cost"]
    shared = SimpleNamespace(rows={"b2": {}, "a2": {}}, ancestors={"c2": previous_c2},
        control_cell=initial.control_cell, control_revision=initial.control_revision,
        control_path=initial.control_path, older_paths=initial.older_paths)
    for role, name in (("c1", "previous"), ("b1", "b1"), ("a1", "a1"), ("t4a2", "a2"), ("t4b2", "backing")):
        shared.ancestors[role] = SimpleNamespace(context=getattr(initial, name + "_context"),
            revision=getattr(initial, name + "_revision"), path=getattr(initial, name + "_path"))
    try:
        with pytest.MonkeyPatch.context() as patch:
            # Exactly one successful inference history for the ordinary B2 variants.
            profile = "b2"
            claim_revision, output_revision, terminal_revision, _ = REVISIONS[profile]
            _, run_id, inference_run, actual_request = PROFILES[profile]
            api = copy.deepcopy(previous_c2.api)
            assert previous_c2.terminal["binding"]["policy"] == "task5-c2-model-free-ungraded"
            assert not {"child", "files", "score", "verdict"}.intersection(previous_c2.terminal)
            assert not set(REVISIONS[profile]).intersection(api.trees)
            seeded = SimpleNamespace(api=api,
                context=grading.compile_request("pilot/" + CELLS[profile], PRODUCER, terminal_revision))
            with patch.context() as seed:
                for key, value in {"SOURCE": PRODUCER, "CLAIM": claim_revision,
                                   "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                    seed.setattr(base, key, value)
                base._seed_outputs(seeded, directory, extra_deliverable=True)
            cp, tp, ip = retained._paths(seeded.context.cell)
            input_parent = previous_c2.terminal["binding"]["retained"]["terminal_commit"]
            parent_bytes = api.trees[input_parent][retained._paths(previous_c2.context.cell)[1]]
            parent_input = pilot._json_object(parent_bytes)
            seeded.claim["binding"]["github_run"] = {"id": inference_run, "job": "cell", "attempt": 1}
            seeded.claim["expected_parent"] = input_parent
            seeded.claim["predecessor"] = {"cell_id": CELLS["c2"], "terminal_commit": input_parent,
                "terminal_sha256": pilot._identity(parent_bytes)["sha256"], "output_commit": parent_input["output_commit"],
                "manifest_sha256": parent_input["manifest_identity"]["sha256"]}
            seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
            files = {name: data for name, data in api.trees[output_revision].items() if name.startswith(ip + "/")}
            api.seed(claim_revision, input_parent, {cp: retained._encoded(seeded.claim)})
            api.seed(output_revision, claim_revision, files)
            api.seed(terminal_revision, output_revision, {tp: retained._encoded(seeded.terminal)})
            api.branches[retained.BRANCH] = terminal_revision
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            request = pilot._digest(seeded.terminal["completion"])
            assert request != actual_request
            patch.setitem(grading.TASK5_RETAINED, CELLS[profile], (inference_run, request))
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                for variant in VARIANTS[profile]:
                    destination = directory / (profile + "-" + variant)
                    destination.mkdir()
                    current = SimpleNamespace(api=copy.deepcopy(api), context=readout._writer_context(request),
                        request=request, workflow=workflow, root=destination / "grade")
                    current.transport = base.Child(current)
                    current.api.events.clear()
                    with patch.context() as selected:
                        selected.setattr(base, "OUTPUT", output_revision)
                        selected.setenv("HF_TOKEN", base.TOKEN)
                        base._synthetic_rubric(current, selected)
                        approval._authorize(current, destination, selected, run_id)
                        revision, path, terminal = writer._writer(current, capture, destination, selected, variant)
                    claim = retained._read(current.root / "claim-receipt.json")["claim"]
                    assert claim["expected_parent"] == previous_c2.revision
                    assert terminal["binding"]["github_run"] == {"id": run_id, "job": "pilot-live", "attempt": 1}
                    assert terminal["format"] == grading.RESULT_FORMAT
                    assert terminal["child"]["entry_invoked"] is terminal["child"]["cleanup_confirmed"] is True
                    assert current.transport.calls == 1 and current.api.events == ["grade_claim", "judge", "grade_output"]
                    assert all(current.api.trees[commit] == tree for commit, tree in api.trees.items())
                    shared.rows[profile][variant] = SimpleNamespace(api=current.api, context=current.context,
                        request=request, revision=revision, path=path, terminal=terminal)

            # Final A2 is a genuine NG writer after the ordinary graded B2 variant.
            profile = "a2"
            claim_revision, output_revision, terminal_revision, _ = REVISIONS[profile]
            _, run_id, inference_run, actual_request = PROFILES[profile]
            previous = shared.rows["b2"]["graded"]
            for variant in VARIANTS[profile]:
                destination = directory / (profile + "-" + variant)
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
                        ledger.settle("settled", usage=CallUsage(input_tokens=59, cached_input_tokens=13,
                            output_tokens=19, reasoning_tokens=9), resolved_model="gpt-5.4")
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
                assert previous.terminal["format"] == grading.RESULT_FORMAT
                assert previous.terminal["child"]["entry_invoked"] is previous.terminal["child"]["cleanup_confirmed"] is True
                assert not set(REVISIONS[profile]).intersection(api.trees)
                seeded = SimpleNamespace(api=api, context=prototype)
                with patch.context() as seed:
                    for key, value in {"SOURCE": PRODUCER, "CLAIM": claim_revision,
                                       "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                        seed.setattr(base, key, value)
                    base._seed_outputs(seeded, destination, failed=True, producer_row=row,
                        producer_ledger=ledger_bytes, producer_receipt=row["problem_solving_cost"], reason="child_nonzero_exit")
                cp, tp, ip = retained._paths(prototype.cell)
                input_parent = previous.terminal["binding"]["retained"]["terminal_commit"]
                parent_bytes = api.trees[input_parent][retained._paths(previous.context.cell)[1]]
                parent_input = pilot._json_object(parent_bytes)
                seeded.claim["binding"]["github_run"] = {"id": inference_run, "job": "cell", "attempt": 1}
                seeded.claim["expected_parent"] = input_parent
                seeded.claim["predecessor"] = {"cell_id": CELLS["b2"], "terminal_commit": input_parent,
                    "terminal_sha256": pilot._identity(parent_bytes)["sha256"], "output_commit": parent_input["output_commit"],
                    "manifest_sha256": parent_input["manifest_identity"]["sha256"]}
                seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                files = {name: data for name, data in api.trees[output_revision].items() if name.startswith(ip + "/")}
                api.seed(claim_revision, input_parent, {cp: retained._encoded(seeded.claim)})
                api.seed(output_revision, claim_revision, files)
                api.seed(terminal_revision, output_revision, {tp: retained._encoded(seeded.terminal)})
                api.branches[retained.BRANCH] = terminal_revision
                api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
                request = pilot._digest(seeded.terminal["completion"])
                assert request != actual_request
                patch.setitem(grading.TASK5_RETAINED, CELLS[profile], (inference_run, request))
                current = SimpleNamespace(api=api, context=readout._writer_context(request), request=request,
                    workflow=workflow, root=destination / "record")
                current.transport = policy._SourceOnlyChild(current)
                with patch.context() as selected:
                    selected.setattr(base, "OUTPUT", output_revision)
                    selected.setenv("HF_TOKEN", base.TOKEN)
                    base._synthetic_rubric(current, selected)
                    approval._authorize(current, destination, selected, run_id)
                    def no_judge(*args, **kwargs):
                        raise AssertionError("final A2 writer invoked a judge or rubric")
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
                assert terminal["binding"]["github_run"] == {"id": run_id, "job": "pilot-live", "attempt": 1}
                assert terminal["binding"]["policy"] == ungraded.TASK5_A2_POLICY
                assert terminal["outcome"] == "ungraded" and terminal["model_invoked"] is False
                assert not {"child", "files", "score", "verdict"}.intersection(terminal)
                assert all(api.trees[commit] == tree for commit, tree in previous.api.trees.items())
                shared.rows[profile][variant] = SimpleNamespace(api=api, context=current.context,
                    request=request, revision=revision, path=path, terminal=terminal)
            yield shared
    finally:
        prefix.close()


RUN_CHANGES = {"run": ("id", "PRIVATE"), "job": ("job", "grade"), "attempt": ("attempt", 2),
               "typed_attempt": ("attempt", True), "float_attempt": ("attempt", 1.0)}
BINDING_FIELDS = ("controller_source_sha", "source_sha", "config_sha256", "grader_config_sha256",
                  "approval_request_sha256", "cell_id", "publication_receipt_sha256")
C2_HANDOFFS = ("missing", "type", "open", "metadata", "owners_list", "owners_short", "wrong_owner", "owner_type",
    "full_type", "full_changed", "routing_type", "routing_changed", "owner_metadata", "owner_snapshot",
    "metadata_footprint", "inference_footprint", "download_footprint", "shared_metadata", "shared_download",
    "shared_inference_alias")
B2_HANDOFFS = ("missing", "list", "length", "footprint_type", "proof_type", "footprint_changed",
    "owner_metadata", "owner_snapshot", "shared_metadata", "shared_download", "shared_inference_alias", "c2_reopened")
COMMON = ("advanced", "replay", "plan", "closed_registry", "active_denials", "whole_observation", "parent_entry",
    "claim_hash", "claim_bytes", "claim_extra", "terminal_history", "ordinal", "ref", "inference_ref", "host_ref",
    "observer_writer", "observer_producer", "observer_source", "source_preflight", "paid", "rerun",
    "producer_override", "wrong_phase", "private_target", "lost_response",
    *("control_" + part for part in ("missing", "bytes", "history", "carried")),
    *("c2_handoff_" + part for part in C2_HANDOFFS),
    *("facade_lost_" + role for role in ("a1", "b1", "c2")))
# Each mutation belongs to one of the two new consumers. Older helpers supply
# writer construction only; no previously passing test body is called.
CASES = []
for _profile in PROFILES:
    _parent = PARENTS[_profile]
    _roles = CHAIN[CHAIN.index(_profile):]
    _scenarios = [*VARIANTS[_profile], *COMMON]
    for _role in (_profile, _parent):
        _scenarios.extend(f"{_role}:binding:{field}" for field in BINDING_FIELDS)
        _scenarios.extend(f"{_role}:run:{field}" for field in RUN_CHANGES)
        _scenarios.extend(f"{_role}:entry:{field}" for field in ("grader_hash", "renderer"))
        _scenarios.extend(f"{_role}:claim:{field}" for field in ("type", "float", "format", "history", "carried"))
        _scenarios.extend(f"{_role}:parent:{field}" for field in ("hash", "size_float", "cell", "carried", "carried_bytes"))
        _scenarios.extend(f"{_role}:input:{field}" for field in
                         ("run", "source", "config", "predecessor", "parent", "ack", "cleanup", "manifest"))
        if _role in NG_ROLES:
            _scenarios.extend(f"{_role}:record:{field}" for field in ("policy", "type", "model", "score", "child", "files", "outcome"))
            _scenarios.extend(f"{_role}:original:{field}" for field in ("result", "ledger"))
        else:
            _scenarios.extend(f"{_role}:ordinary:{field}" for field in ("no_child", "cleanup", "type", "missing", "artifact_history"))
    # Verify that each deeper fixed owner is actually checked, without copying
    # the old families' full mutation matrices into this selector.
    for _role in _roles[2:]:
        _scenarios.extend((f"{_role}:binding:controller_source_sha", f"{_role}:run:run",
            f"{_role}:entry:renderer", f"{_role}:claim:type", f"{_role}:input:predecessor"))
        _scenarios.append(f"{_role}:record:policy" if _role in NG_ROLES else f"{_role}:ordinary:no_child")
        if _role in NG_ROLES:
            _scenarios.append(f"{_role}:original:ledger")
    for _role in _roles[1:]:
        _scenarios.extend(f"alias:{kind}:{_role}:{part}" for kind in ("claim", "terminal")
                         for part in ("terminal", "claim", "input_terminal"))
        _scenarios.extend(f"alias:{kind}:{_role}:{kind}" for kind in ("input_terminal", "input_claim", "input_output"))
    _scenarios.extend(f"alias:{kind}:control:terminal" for kind in ("claim", "terminal"))
    _scenarios.extend(f"alias:claim:{_profile}:{part}" for part in ("input_terminal", "input_claim", "input_output"))
    # Both legitimate shared terminal revisions must not hide an inference alias.
    _scenarios.extend(f"alias:{kind}:{role}:terminal" for kind in ("input_terminal", "input_claim", "input_output")
                     for role in ("c2", "b1"))
    if _profile == "b2":
        _scenarios.extend(("exclusions", "redacted_text", "raw_judge", "private_cost_reason", "denominator_type",
            "payload_source", "ledger_pointer", "bytes", "ledger_bytes", "path", "outcome"))
    else:
        _scenarios.extend((*("b2_handoff_" + part for part in B2_HANDOFFS), "facade_lost_a2",
            "recorder_zero", "recorder_invoice", "recorder_http", "completion_status", "completion_type",
            "completion_receipt", "completion_denominator", "inference_missing", "inference_deliverables"))
    assert len(_scenarios) == len(set(_scenarios))
    CASES.extend((_profile, scenario) for scenario in _scenarios)


@pytest.mark.parametrize("profile,scenario", CASES, ids=[profile + "-" + scenario for profile, scenario in CASES])
def test_final_task5_readouts(history, tmp_path, monkeypatch, capsys, profile, scenario):
    row = history.rows[profile].get(scenario, history.rows[profile]["partial_cost"])
    ordinal, run_id, inference_run, _ = PROFILES[profile]
    monkeypatch.setitem(grading.TASK5_RETAINED, CELLS[profile], (inference_run, row.request))
    api = copy.deepcopy(row.api)
    roles = CHAIN[CHAIN.index(profile):]
    nodes = {}
    for role in roles:
        source = row if role == profile else history.rows["b2"]["graded"] if role == "b2" else history.ancestors[role]
        terminal = pilot._json_object(api.trees[source.revision][source.path])
        claim_path = grading._paths(source.context.cell)[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
        nodes[role] = SimpleNamespace(context=copy.deepcopy(source.context), revision=source.revision, path=source.path,
            terminal=terminal, claim=claim, claim_path=claim_path)
    selected, parent, backing = nodes[profile], nodes[PARENTS[profile]], nodes["t4b2"]
    context, terminal, claim = selected.context, selected.terminal, selected.claim
    changed, claim_overrides, corrupt_bytes, corrupt_history, remove = {profile}, {}, [], [], []
    input_claim, input_output, input_terminal, advanced = REVISIONS[profile]

    if scenario.count(":") == 2:
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
            entry = node.terminal["binding"]["predecessor_entry"] if role in NG_ROLES else node.terminal["binding"]
            if field == "grader_hash":
                entry["grader_source_hash"] = "9" * 64
            else:
                entry["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
            changed.add(role)
        elif kind == "record":
            if field == "policy":
                node.terminal["binding"]["policy"] = "PRIVATE"
            else:
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
                corrupt_bytes.append((node.revision, node.claim_path))
        elif kind == "parent":
            previous = nodes[PARENTS[role]]
            if field == "carried":
                corrupt_history.append((node.terminal["claim_commit"], previous.path, node.terminal["claim_commit"]))
            elif field == "carried_bytes":
                corrupt_bytes.append((node.terminal["claim_commit"], previous.path))
            else:
                key, value = {"hash": ("sha256", "9" * 64), "size_float": ("size", float(node.claim["predecessor"]["size"])),
                              "cell": ("cell_id", CELLS[profile])}[field]
                node.claim["predecessor"][key] = value
                changed.add(role)
        elif kind == "ordinary":
            if field == "missing":
                remove.append((node.revision, node.path))
            elif field == "artifact_history":
                corrupt_history.append((node.revision, node.terminal["files"][0]["path"], node.terminal["claim_commit"]))
            else:
                if field == "type":
                    node.terminal["format"] = ungraded.TERMINAL_FORMAT
                else:
                    node.terminal["child"]["entry_invoked" if field == "no_child" else "cleanup_confirmed"] = False
                changed.add(role)
        elif kind == "original":
            corrupt_bytes.append((node.terminal["binding"]["retained"]["output_commit"],
                retained._paths(node.context.cell)[2] + "/" + NAMES[field == "ledger"]))
        elif kind == "input":
            icp, itp, ip = retained._paths(node.context.cell)
            ir = node.terminal["binding"]["retained"]["terminal_commit"]
            original = pilot._json_object(api.trees[ir][itp])
            original_claim = pilot._json_object(api.trees[original["claim_commit"]][icp])
            if field == "run":
                original_claim["binding"]["github_run"]["id"] = "PRIVATE"
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
            else:
                corrupt_bytes.append((original["output_commit"], ip + "/" + output.MANIFEST))
            data = retained._encoded(original_claim)
            for commit in (original["claim_commit"], original["output_commit"], ir):
                api.trees[commit][icp] = data
            original["claim_identity"] = pilot._identity(data)
            data = retained._encoded(original)
            api.trees[ir][itp] = data
            node.terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
            changed.add(role)
        else:
            raise AssertionError(scenario)
    elif scenario == "advanced":
        api.seed(advanced, selected.revision, {"unrelated/PRIVATE": b"PRIVATE"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = advanced
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
    elif scenario == "inference_deliverables":
        terminal["inference_completion"]["artifacts"]["deliverables"] = [{"size": 1, "sha256": "9" * 64}]
    elif scenario in {"exclusions", "redacted_text", "raw_judge", "private_cost_reason", "denominator_type", "payload_source", "ledger_pointer"}:
        record = next(item for item in terminal["files"] if item["role"] == "grade_result")
        payload = pilot._json_object(api.trees[selected.revision][record["path"]])
        task = payload["tasks"][0]
        if scenario == "exclusions":
            task["items"][1].update(score_excluded=True, verdict="judge_error", awarded_score=0,
                model_did_right=False, decided_by="judge")
            task.update(total_awarded=2, total_max=2, pct=100, score_excluded_items=1, score_excluded_max=2, pct_full_denominator=50)
            payload["summary"] = step8._compute_summary(payload["tasks"],
                unpriced_models=step8._unpriced_models(json.loads(context.run.grader_config_json)))
        elif scenario == "redacted_text":
            task["sector"] = c_reader.PRIVATE
            task["items"][0].update(criterion=c_reader.PRIVATE, evidence=c_reader.PRIVATE)
            task["grading_cost"]["components"][0]["provider"] = c_reader.PRIVATE
        elif scenario == "raw_judge":
            task["items"][0]["judge_raw_response"] = c_reader.PRIVATE
        elif scenario == "private_cost_reason":
            task["grading_cost"]["missing_reasons"] = [c_reader.PRIVATE]
        elif scenario == "denominator_type":
            task["total_max"] = "PRIVATE"
        elif scenario == "payload_source":
            payload["source_inference_revision"] = "9" * 40
        else:
            payload["cost_ledger"]["sha256"] = "9" * 64
        data = base._json(payload)
        api.trees[selected.revision][record["path"]] = data
        record.update(retained._object(record["path"], data))
    elif scenario in {"bytes", "ledger_bytes", "path"}:
        record = next(item for item in terminal["files"] if item["role"] == ("grade_cost_ledger" if scenario == "ledger_bytes" else "grade_result"))
        if scenario == "path":
            record["path"] = "PRIVATE/foreign.json"
        else:
            corrupt_bytes.append((selected.revision, record["path"]))
    elif scenario == "outcome":
        terminal["outcome"] = "failed"
    elif scenario == "claim_bytes":
        corrupt_bytes.append((terminal["claim_commit"], selected.claim_path))
    elif scenario == "claim_extra":
        claim["extra"] = "PRIVATE"
    elif scenario == "terminal_history":
        corrupt_history.append((selected.revision, selected.path, terminal["claim_commit"]))
    elif scenario.startswith("control_"):
        if scenario == "control_missing":
            remove.append((history.control_revision, history.control_path))
        elif scenario == "control_bytes":
            corrupt_bytes.append((history.control_revision, history.control_path))
        elif scenario == "control_history":
            corrupt_history.append((history.control_revision, history.control_path, backing.revision))
        else:
            corrupt_history.append((backing.terminal["claim_commit"], history.control_path, backing.terminal["claim_commit"]))
    elif scenario.startswith("alias:"):
        _, kind, role, part = scenario.split(":")
        if role == "control":
            alias = history.control_revision
        else:
            target = nodes[role]
            ir = target.terminal["binding"]["retained"]["terminal_commit"]
            it = pilot._json_object(api.trees[ir][retained._paths(target.context.cell)[1]])
            alias = {"terminal": target.revision, "claim": target.terminal["claim_commit"],
                "input_terminal": ir, "input_claim": it["claim_commit"], "input_output": it["output_commit"]}[part]
        preserved = copy.deepcopy((api.trees[alias], api.writers[alias]))
        if kind in {"claim", "terminal"}:
            original_revision = terminal["claim_commit"] if kind == "claim" else selected.revision
            members = [selected.claim_path, parent.path]
            if kind == "terminal":
                members.extend([selected.path, *(item["path"] for item in terminal.get("files", []))])
            for member in members:
                api.trees[alias][member] = api.trees[original_revision][member]
                api.writers[alias][member] = api.writers[original_revision][member]
            if kind == "claim":
                terminal["claim_commit"] = alias
                api.writers[alias][selected.claim_path] = api.writers[selected.revision][selected.claim_path] = alias
            else:
                selected.revision = alias
                api.writers[alias][selected.path] = alias
                for item in terminal.get("files", []):
                    api.writers[alias][item["path"]] = alias
                api.branches[grading.BRANCH] = alias
        else:
            icp, itp, _ = retained._paths(context.cell)
            original = pilot._json_object(api.trees[input_terminal][itp])
            original_revision = {"input_terminal": input_terminal, "input_claim": input_claim, "input_output": input_output}[kind]
            members = [icp]
            if kind != "input_claim":
                members.extend(item["path"] for item in original["output_objects"])
            if kind == "input_terminal":
                members.append(itp)
            for member in members:
                api.trees[alias][member] = api.trees[original_revision][member]
                api.writers[alias][member] = api.writers[original_revision][member]
            if kind == "input_terminal":
                api.writers[alias][itp] = alias
                terminal["binding"]["retained"]["terminal_commit"] = alias
            elif kind == "input_claim":
                original["claim_commit"] = alias
                for commit in (alias, input_output, input_terminal):
                    api.writers[commit][icp] = alias
            else:
                original["output_commit"] = alias
                terminal["binding"]["retained"]["output_commit"] = alias
                for item in original["output_objects"]:
                    api.writers[alias][item["path"]] = api.writers[input_terminal][item["path"]] = alias
                if profile == "b2":
                    # Coherent ordinary file names, payload source and ledger
                    # pointer: alias refusal must not rely on stale artifacts.
                    entry = readout._writer_entry(context, terminal["binding"]["renderer_fingerprint"])
                    paths = grading._grade_artifact_paths(context, entry, alias)
                    grade_path = grading._grade_path(context, entry["config_hash"], entry["grader_source_hash"], alias)
                    for item in terminal["files"]:
                        data = api.trees[selected.revision][item["path"]]
                        if item["role"] == "grade_result":
                            payload = pilot._json_object(data)
                            payload["source_inference_revision"] = alias
                            if payload.get("cost_ledger") is not None:
                                payload["cost_ledger"]["path"] = str(grade_path.with_name(grade_path.stem + ".cost_ledger.jsonl"))
                            data = base._json(payload)
                        path = paths[item["role"]]
                        api.trees[selected.revision][path] = data
                        api.writers[selected.revision][path] = selected.revision
                        item.update(retained._object(path, data))
            data = retained._encoded(original)
            api.trees[alias if kind == "input_terminal" else input_terminal][itp] = data
            terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
        # Target ancestor files and their last-writer histories stay intact.
        # These are cross-level alias attacks, not absent-file fixtures.
        assert all(api.trees[alias][member] == data for member, data in preserved[0].items())
        assert all(api.writers[alias][member] == written for member, written in preserved[1].items())
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            current = compile_writer(request)
            if current.cell["cell_id"] == CELLS[profile]:
                current.plan["order"][ordinal - 1:ordinal + 1] = [CELLS[profile], CELLS[PARENTS[profile]]]
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

    # Rehash only these fixed pairs, from oldest to selected. Each isolated
    # mutation keeps every child's actual parent bytes and identity coherent.
    for role in reversed(roles):
        if role not in changed:
            continue
        node = nodes[role]
        data = controls._store_grade(api, node.revision, node.path, node.terminal, node.claim)
        if role in claim_overrides:
            field = claim_overrides[role]
            if field == "format":
                node.claim["format"] = grading.CLAIM_FORMAT if role in NG_ROLES else ungraded.CLAIM_FORMAT
            else:
                node.claim["binding"]["github_run"]["attempt"] = True if field == "type" else 1.0
            encoded = retained._encoded(node.claim)
            for commit in (node.terminal["claim_commit"], node.revision):
                api.trees[commit][node.claim_path] = encoded
            node.terminal["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(node.terminal)
            api.trees[node.revision][node.path] = data
        if role != profile:
            child_role = roles[roles.index(role) - 1]
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
        pytest.fail("final task5 reader crossed a model, auth, write or parent-grade payload boundary")
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
    if profile == "a2":
        monkeypatch.setattr(readout, "_projection", forbidden)

    readers, facades, ordinary, records, completed, handoffs = [], [], [], [], [], []
    initialize = readout._ReadOnlyGrade.__init__
    facade_init = {cls: cls.__init__ for cls in (readout._Task5A1NativeReads, readout._Task5B1NativeReads,
                                               readout._Task5C2NativeReads, readout._Task5A2NativeReads)}
    ordinary_terminal, record_terminal = grading._grade_terminal, ungraded.verify_terminal
    verified_ng, verified_grade, predecessor = readout._verified_ungraded, readout._verified_grade, readout._verify_predecessor
    allow_files = readout._ReadOnlyGrade.allow_verified_files
    selected_files = {(selected.revision, item["path"]) for item in terminal.get("files", [])}
    original_members = {(terminal["binding"]["retained"]["output_commit"], retained._paths(context.cell)[2] + "/" + name) for name in NAMES}
    selected_payloads = original_members if profile == "a2" else selected_files
    denied = set()
    for role in roles:
        if role in NG_ROLES:
            continue
        node = nodes[role]
        if role != profile:
            denied.update((node.revision, item["path"]) for item in node.terminal.get("files", []))
        ir = node.terminal["binding"]["retained"]["terminal_commit"]
        itp = retained._paths(node.context.cell)[1]
        original = pilot._json_object(api.trees[ir][itp])
        denied.update((original["output_commit"], item["path"]) for item in original["output_objects"]
                      if not item["path"].endswith("/" + output.MANIFEST))
    control = pilot._json_object(row.api.trees[history.control_revision][history.control_path])
    control_cp = grading._paths(history.control_cell)[0]
    control_icp, control_itp, _ = retained._paths(history.control_cell)
    control_ir = control["binding"]["retained"]["terminal_commit"]
    control_input = pilot._json_object(row.api.trees[control_ir][control_itp])
    deeper = {(history.control_revision, control_cp), (control["claim_commit"], control_cp),
        (control_ir, control_itp), (control_input["claim_commit"], control_icp),
        *((history.control_revision, item["path"]) for item in control["files"]),
        *((control_input["output_commit"], item["path"]) for item in control_input["output_objects"]),
        (input_output, "PRIVATE/arbitrary")}
    input_revisions = {role: node.terminal["binding"]["retained"]["terminal_commit"] for role, node in nodes.items()}

    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)

    def download(client, revision, member):
        return client.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
            revision=revision, filename=member, cache_dir=tmp_path,
            force_download=True, local_files_only=False, etag_timeout=1)

    def remember_facade(facade, owner, prior, current, previous, *proof):
        if current.cell["cell_id"] == CELLS["a2"] and scenario in {"b2_handoff_owner_metadata", "b2_handoff_owner_snapshot"}:
            prior = copy.copy(prior)
            if scenario == "b2_handoff_owner_metadata":
                prior._inference_metadata = {"9" * 40}
            else:
                prior._metadata_open = True
        facade_init[type(facade)](facade, owner, prior, current, previous, *proof)
        facades.append(facade)
        cell = current.cell["cell_id"]
        role = next(role for role in ("a1", "b1", "c2", "a2") if CELLS[role] == cell)
        expected_roles = {"a1": ("a1", "t4a2"), "b1": ("b1", "a1", "t4a2"),
            "c2": ("c2", "c1", "b1", "a1", "t4a2"), "a2": ("a2", "b2", "c2", "c1", "b1", "a1", "t4a2")}[role]
        assert facade._owners == tuple(readers[roles.index(item)] for item in expected_roles)
        assert all(not other._open and not other._metadata for other in facades[:-1])
        sequences = {"a1": ("a1", "t4a2", "t4a2", "t4b2"),
            "b1": ("b1", "a1", "a1", "t4a2", "t4a2", "t4b2"),
            "c2": ("c2", "c1", "c1", "b1", "a1", "a1", "t4a2", "t4a2", "t4b2"),
            "a2": ("a2", "b2", "b2", "c2", "c1", "c1", "b1", "a1", "a1", "t4a2", "t4a2", "t4b2")}
        assert [rev for rev, _ in facade._metadata] == [input_revisions[item] for item in sequences[role]]
        assert all(facade._revisions[index].isdisjoint(other)
                   for index in range(len(expected_roles)) for other in facade._revisions[index + 1:])
        if role == "c2":
            assert facade._revisions[1] == facade._full_footprints[1] - {nodes["b1"].revision}
            assert facade._owner(nodes["b1"].revision) is readers[roles.index("b1")]
        elif role == "a2":
            assert type(proof[0]) is tuple and type(proof[0][1]) is frozenset
            assert facade._revisions[1] == proof[0][1] - {nodes["c2"].revision}
            assert facade._owner(nodes["c2"].revision) is readers[roles.index("c2")]
            assert facade._owner(nodes["b1"].revision) is readers[roles.index("b1")]
            assert handoffs == ["c1", "b2"]
        own = nodes[role]
        own_members = {(own.terminal["binding"]["retained"]["output_commit"],
            retained._paths(current.cell)[2] + "/" + name) for name in NAMES}
        assert not own_members.intersection(owner._downloads)
        assert not selected_payloads.intersection(readers[0]._downloads)
        assert not selected_payloads.intersection((rev, member) for op, rev, member, _ in api.reads if op == "download")
        if scenario != "active_denials":
            return
        before = copy.deepcopy((api.calls, api.reads))
        for wrong in (grading.BRANCH, retained.BRANCH, previous.terminal_revision, "9" * 40):
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(repo_id=api.repo, repo_type="dataset", revision=wrong, token=base.TOKEN, timeout=1)
        for wrong in ({"repo_id": "PRIVATE/wrong"}, {"repo_type": "model"}, {"token": "PRIVATE"}):
            kwargs = dict(repo_id=api.repo, repo_type="dataset", revision=current.terminal_revision, token=base.TOKEN, timeout=1)
            kwargs.update(wrong)
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(**kwargs)
        wrong_owner = {(owner.revision, nodes["t4a2"].path), (previous.terminal_revision, owner._claim)}
        for rev, member in denied | deeper | wrong_owner | selected_payloads | own_members:
            with pytest.raises(output.OutputPublicationRefused):
                download(facade, rev, member)
        for rev, member in deeper | wrong_owner:
            with pytest.raises(output.OutputPublicationRefused):
                facade.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=rev, paths=[member], expand=True)
        assert (api.calls, api.reads) == before

    def verify_ordinary(client, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] in {CELLS[role] for role in ("b2", "c1", "t4b2")}
        result = ordinary_terminal(client, repo, revision, current, *args, **kwargs)
        ordinary.append(current.cell["cell_id"])
        return result

    def verify_record(client, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] in {CELLS[role] for role in NG_ROLES}
        records.append(current.cell["cell_id"])
        result = record_terminal(client, repo, revision, current, *args, **kwargs)
        completed.append(current.cell["cell_id"])
        matching = {readout._Task5A1NativeReads: "a1", readout._Task5B1NativeReads: "b1",
                    readout._Task5C2NativeReads: "c2", readout._Task5A2NativeReads: "a2"}
        if type(client) in matching and current.cell["cell_id"] == CELLS[matching[type(client)]]:
            assert client._open and not client._metadata
            if scenario == "active_denials":
                before = copy.deepcopy((api.calls, api.reads))
                with pytest.raises(output.OutputPublicationRefused):
                    client.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=current.terminal_revision, timeout=1)
                blocked = denied | deeper | (selected_payloads if current.cell["cell_id"] != CELLS[profile] else set())
                for rev, member in blocked:
                    with pytest.raises(output.OutputPublicationRefused):
                        download(client, rev, member)
                assert (api.calls, api.reads) == before
        return result

    def verify_ng(reader, current, *args, **kwargs):
        result, entry, files = verified_ng(reader, current, *args, **kwargs)
        if current.cell["cell_id"] == CELLS[PARENTS[profile]] and scenario == "parent_entry":
            entry = {**entry, "config_hash": "9" * 16}
        if current.cell["cell_id"] != CELLS["c2"]:
            return result, entry, files
        proof = reader._task5_c2_proof
        assert type(proof) is readout._Task5C2NativeReads and proof is facades[2]
        assert not proof._open and not proof._metadata
        assert proof._owners[0] is reader and len(proof._full_footprints) == 5
        if scenario.startswith("c2_handoff_"):
            field = scenario.removeprefix("c2_handoff_")
            if field == "missing":
                reader.__dict__.pop("_task5_c2_proof")
            elif field == "type":
                reader._task5_c2_proof = SimpleNamespace()
            else:
                injected = copy.copy(proof)
                if field == "open":
                    injected._open = True
                elif field == "metadata":
                    injected._metadata = ((input_terminal, readers[0]),)
                elif field == "owners_list":
                    injected._owners = list(proof._owners)
                elif field == "owners_short":
                    injected._owners = ()
                elif field == "wrong_owner":
                    injected._owners = (proof._owners[1], proof._owners[0], *proof._owners[2:])
                elif field == "owner_type":
                    injected._owners = (SimpleNamespace(**proof._owners[0].__dict__), *proof._owners[1:])
                elif field == "full_type":
                    injected._full_footprints = tuple(set(value) for value in proof._full_footprints)
                elif field == "full_changed":
                    injected._full_footprints = (proof._full_footprints[0] | {"9" * 40}, *proof._full_footprints[1:])
                elif field == "routing_type":
                    injected._revisions = list(proof._revisions)
                elif field == "routing_changed":
                    injected._revisions = (proof._revisions[0] | {"9" * 40}, *proof._revisions[1:])
                elif field in {"owner_metadata", "owner_snapshot"}:
                    owner = copy.copy(proof._owners[0])
                    if field == "owner_metadata":
                        owner._inference_metadata = {"9" * 40}
                    else:
                        owner._metadata_open = True
                    injected._owners = (owner, *proof._owners[1:])
                elif field == "metadata_footprint":
                    proof._owners[0]._metadata_paths["9" * 40] = {"PRIVATE"}
                elif field == "inference_footprint":
                    proof._owners[3]._inference_revisions.add("9" * 40)
                elif field == "download_footprint":
                    proof._owners[4]._downloads.add(("9" * 40, "PRIVATE"))
                elif field == "shared_metadata":
                    proof._owners[1]._metadata_paths[nodes["b1"].revision].add("PRIVATE")
                elif field == "shared_download":
                    proof._owners[1]._downloads.add((nodes["b1"].revision, "PRIVATE"))
                else:
                    assert field == "shared_inference_alias"
                    proof._owners[1]._inference_revisions.add(nodes["b1"].revision)
                    # The revision was already present as terminal control;
                    # footprint equality alone cannot detect this alias.
                    assert frozenset({*proof._owners[1]._metadata_paths, *proof._owners[1]._inference_revisions,
                        *(rev for rev, _ in proof._owners[1]._downloads)}) == proof._full_footprints[1]
                reader._task5_c2_proof = injected
        return result, entry, files

    def verify_grade(reader, current, *args, **kwargs):
        result, entry, previous_input = verified_grade(reader, current, *args, **kwargs)
        if current.cell["cell_id"] == CELLS[PARENTS[profile]] and scenario == "parent_entry":
            entry = {**entry, "config_hash": "9" * 16}
        return result, entry, previous_input

    def verify_predecessor(reader, current, *args, **kwargs):
        assert current.cell["cell_id"] in {CELLS["b2"], CELLS["c1"]}
        assert not selected_payloads.intersection(readers[0]._downloads)
        result = predecessor(reader, current, *args, **kwargs)
        role = "b2" if current.cell["cell_id"] == CELLS["b2"] else "c1"
        handoffs.append(role)
        if role != "b2":
            return result
        proof, footprint = reader._task5_b2_proof
        assert proof is facades[2] and not proof._open and not proof._metadata
        assert type(footprint) is frozenset
        assert "_task5_c2_proof" not in proof._owners[0].__dict__
        if scenario.startswith("b2_handoff_"):
            field = scenario.removeprefix("b2_handoff_")
            if field == "missing":
                reader.__dict__.pop("_task5_b2_proof")
            elif field in {"list", "length", "footprint_type", "proof_type", "footprint_changed"}:
                reader._task5_b2_proof = {"list": [proof, footprint], "length": (proof,),
                    "footprint_type": (proof, set(footprint)), "proof_type": (SimpleNamespace(), footprint),
                    "footprint_changed": (proof, footprint | {"9" * 40})}[field]
            elif field == "shared_metadata":
                reader._metadata_paths[nodes["c2"].revision].add("PRIVATE")
            elif field == "shared_download":
                reader._downloads.add((nodes["c2"].revision, "PRIVATE"))
            elif field == "shared_inference_alias":
                reader._inference_revisions.add(nodes["c2"].revision)
                assert frozenset({*reader._metadata_paths, *reader._inference_revisions,
                    *(rev for rev, _ in reader._downloads)}) == footprint
            elif field == "c2_reopened":
                injected = copy.copy(proof)
                injected._open = True
                reader._task5_b2_proof = (injected, footprint)
            else:
                assert field in {"owner_metadata", "owner_snapshot"}  # Copied parent injected at A2 construction.
        return result

    def allow_selected_files(reader, files):
        assert profile == "b2" and reader is readers[0]
        assert handoffs == ["c1", "b2"] and len(facades) == 3
        assert all(not facade._open and not facade._metadata for facade in facades)
        assert not selected_files.intersection(reader._downloads)
        return allow_files(reader, files)

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    for cls in facade_init:
        monkeypatch.setattr(cls, "__init__", remember_facade)
    monkeypatch.setattr(grading, "_grade_terminal", verify_ordinary)
    monkeypatch.setattr(ungraded, "verify_terminal", verify_record)
    monkeypatch.setattr(readout, "_verified_ungraded", verify_ng)
    monkeypatch.setattr(readout, "_verified_grade", verify_grade)
    monkeypatch.setattr(readout, "_verify_predecessor", verify_predecessor)
    monkeypatch.setattr(readout._ReadOnlyGrade, "allow_verified_files", allow_selected_files)
    if scenario == "whole_observation":
        bind_retained = readout._ReadOnlyGrade.bind_retained
        def wrong_observation(reader, binding, current, *args, **kwargs):
            value = bind_retained(reader, binding, current, *args, **kwargs)
            return {**value, "extra": True} if current.cell["cell_id"] == CELLS[profile] else value
        monkeypatch.setattr(readout._ReadOnlyGrade, "bind_retained", wrong_observation)
    lost_slots = []
    if scenario.startswith("facade_lost_"):
        repo_info = readout._ReadOnlyGrade.repo_info
        lost_role = scenario.removeprefix("facade_lost_")
        expected_count = {"a1": 1, "b1": 2, "c2": 3, "a2": 4}[lost_role]
        def lost_before_owner_consumes(reader, **kwargs):
            if len(facades) == expected_count and reader is readers[roles.index(lost_role)]:
                assert not lost_slots  # No replay or retry after an unresolved response.
                assert kwargs["revision"] in reader._inference_metadata
                assert len(facades[-1]._metadata) == {"a1": 3, "b1": 5, "c2": 8, "a2": 11}[lost_role]
                lost_slots.append(kwargs["revision"])
                raise output.OutputPublicationRefused("PRIVATE", http_status=503)
            return repo_info(reader, **kwargs)
        monkeypatch.setattr(readout._ReadOnlyGrade, "repo_info", lost_before_owner_consumes)

    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
        "GITHUB_RUN_ID": "900055", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
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
    assert public["cell_id"] == CELLS[profile] and public["grade_writer_run"] == {"id": run_id, "job": "pilot-live", "attempt": 1}
    assert public["grade_writer_source_sha"] == WRITER and public["inference_producer_source_sha"] == PRODUCER
    downloads = {(revision, member) for op, revision, member, _ in api.reads if op == "download"}
    assert not history.older_paths.intersection(member for _, member in downloads)
    selected_result = ({(terminal["binding"]["retained"]["output_commit"],
                         retained._paths(context.cell)[2] + "/step2_inference_results.json")}
                       if profile == "b2" else set())
    assert not ((denied - selected_result) | deeper).intersection(downloads)
    accepted = {*VARIANTS[profile], "advanced", "replay", "active_denials", "exclusions", "redacted_text"}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        if scenario == "closed_registry":
            requests = controls._unregistered_requests()
            assert requests == ["9" * 64, "9" * 40, ""] and row.request not in requests
            assert context.plan["order"][24:] == [CELLS[role] for role in ("a1", "b1", "c1", "c2", "b2", "a2")]
            assert len(context.plan["order"]) == len(set(context.plan["order"])) == 30
            assert context.plan["order"][30:] == [] and set(grading.TASK5_RETAINED) == set(context.plan["order"][24:])
            for role in ("a1", "b1", "c1", "c2", "b2", "a2"):
                compiled = readout._writer_context(grading.TASK5_RETAINED[CELLS[role]][1])
                assert grading._model_free_context(compiled) is (role in NG_ROLES)
            for request in requests:
                closed = list(args)
                closed[5] = request
                assert grading.main(closed, _test_api=api) == 2
                refused = capsys.readouterr()
                assert not refused.out and json.loads(refused.err)["outcome"] == "refused"
                assert not api.calls and not root.exists()
    elif scenario in accepted:
        assert code == 0, public
        assert public["outcome"] == ("verified_retained_ungraded" if profile == "a2" else "verified_retained_grade")
        assert public["grade_revision"] == selected.revision and public["inference_terminal"] == input_terminal
        assert public["inference_output_commit"] == input_output and public["inference_request_checksum"] == row.request
        assert public["observer_source_sha"] == OBSERVER and public["grader_source_hash"] == readout.TASK3_A1_GRADER_SOURCE_HASH
        assert public["grader_config_sha256"] == readout.CONFIG_SHA256 and public["expected_tasks"] == 1
        assert public["proof_boundary"] == grading.PROOF
        if profile == "b2":
            state = scenario if scenario in {"partial", "failed", "ungraded"} else "graded"
            assert public["grade_state"] == state
            assert not {"grade_success", "record_kind", "inference_accounting", "recorder_accounting", "child", "verdict"}.intersection(public)
            if state != "graded":
                assert public["score"] is None and public["scored_tasks"] == 0
            else:
                score = public["score"]
                assert score["earned"] == score["possible"] == (2 if scenario == "exclusions" else 4)
                assert score["pct"] == 100 and public["coverage"]["rubric_items"] == (1 if scenario == "exclusions" else 2)
                assert score["excluded_items"] == (1 if scenario == "exclusions" else 0)
                assert score["excluded_max_score"] == (2 if scenario == "exclusions" else 0)
                assert score["avg_score_pct_full_denominator"] == (50 if scenario == "exclusions" else 100)
                assert score["avg_score_pct_lift"] == (50 if scenario == "exclusions" else 0)
                assert score["possible"] + score["excluded_max_score"] == 4
            if scenario in {"missing_ledger", "ungraded"}:
                assert public["ledger_state"] == "missing" and public["ledger_derived_cost"] is None
            elif scenario == "price_missing":
                receipt = public["ledger_derived_cost"]
                assert receipt["missing_reasons"] == ["price_missing"]
                assert receipt["known_cost_usd"] is receipt["estimated_cost_usd"] is None
            else:
                assert public["ledger_derived_cost"]["estimated_cost_usd"] is None
                assert public["ledger_derived_cost"]["missing_reasons"] == ["call_reachability_unknown"]
            if scenario in {"partial_cost", "price_missing", "advanced", "replay", "active_denials", "exclusions", "redacted_text"}:
                receipt = public["ledger_derived_cost"]
                assert receipt["model_calls"] == (1 if scenario == "price_missing" else 2)
                assert receipt["usage"] == {"input_tokens": 111, "output_tokens": 23, "cached_input_tokens": 17,
                    "reasoning_tokens": 8, "audio_input_tokens": None, "audio_output_tokens": None}
                if scenario != "price_missing":
                    assert receipt["known_cost_usd"] > 0
            for receipt in (public["recorded_task_cost"], public["recorded_summary_cost"], public["ledger_derived_cost"]):
                if receipt is not None:
                    assert receipt["invoice_complete"] is False and receipt["http_request_count"] is None
            assert parent.terminal["outcome"] == "ungraded" and "child" not in parent.terminal
        else:
            assert public["grade_state"] == "ungraded" and public["record_kind"] == "model_free_ungraded"
            assert public["grade_success"] is public["model_requested"] is public["model_invoked"] is False
            assert public["score"] is public["coverage"] is None and public["scored_tasks"] == public["task_rows"] == 0
            assert public["inference_task_status"] == "error" and public["file_identities"] == []
            assert public["inference_completion"] == row.terminal["inference_completion"]
            assert public["inference_completion"]["denominator"] == 30 and public["inference_completion"]["other_cells_not_run"] == 29
            assert public["inference_completion"]["status"] == "failed" and public["inference_completion"]["artifacts"]["deliverables"] == []
            assert public["inference_missing"] == row.terminal["inference_missing"]
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
            if scenario in {"partial_cost", "price_missing", "advanced", "replay", "active_denials"}:
                receipt = costs["ledger_derived_cost"]
                assert receipt["usage"] == {"input_tokens": 59, "output_tokens": 19, "cached_input_tokens": 13,
                    "reasoning_tokens": 9, "audio_input_tokens": None, "audio_output_tokens": None}
                assert receipt["model_calls"] == (1 if scenario == "price_missing" else 2)
                assert costs["recorded_task_cost"] == receipt
                if scenario != "price_missing":
                    assert receipt["known_cost_usd"] > 0
                    assert receipt["known_cost_usd"] != nodes["c2"].terminal["inference_completion"]["receipt"]["known_cost_usd"]
            assert parent.terminal["format"] == grading.RESULT_FORMAT
            assert parent.terminal["child"]["entry_invoked"] is parent.terminal["child"]["cleanup_confirmed"] is True

        assert len(readers) == len(roles) == (7 if profile == "b2" else 8)
        assert len(facades) == (3 if profile == "b2" else 4) and handoffs == ["c1", "b2"]
        ordinary_roles = ["b2", "c1", *("t4b2",) * 4, "c1", "t4b2"]
        record_roles = ["t4a2", "a1", "t4a2", "b1", "a1", "t4a2", "c2", "b1", "a1", "t4a2"]
        completed_roles = ["t4a2", "t4a2", "a1", "t4a2", "a1", "b1", "t4a2", "a1", "b1", "c2"]
        if profile == "a2":
            ordinary_roles.extend(["b2", "c1", "t4b2"])
            record_roles.extend(["a2", "c2", "b1", "a1", "t4a2"])
            completed_roles.extend(["t4a2", "a1", "b1", "c2", "a2"])
            assert all(not any(key in reader.__dict__ for key in
                ("_task5_a1_proof", "_task5_b1_proof", "_task5_c1_proof", "_task5_c2_proof", "_task5_b2_proof")) for reader in readers)
        assert ordinary == [CELLS[role] for role in ordinary_roles]
        assert records == [CELLS[role] for role in record_roles]
        assert completed == [CELLS[role] for role in completed_roles]
        head = advanced if scenario == "advanced" else selected.revision
        assert public["observed_branch_head"] == head
        expected_downloads = selected_files | {(history.control_revision, history.control_path)}
        if profile == "b2":
            expected_downloads.add((terminal["binding"]["retained"]["output_commit"],
                                    retained._paths(context.cell)[2] + "/step2_inference_results.json"))
        allowed_paths = {(head, selected.path)}
        failure_members = set()
        for role in roles:
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
            it = pilot._json_object(api.trees[ir][itp])
            expected_downloads.update({(ir, itp), (it["claim_commit"], icp), (it["output_commit"], ip + "/" + output.MANIFEST)})
            if role in NG_ROLES:
                members = {(it["output_commit"], ip + "/" + name) for name in NAMES}
                expected_downloads.update(members)
                failure_members.update(members)
            allowed_paths.update({(ir, itp), (ir, icp), (it["claim_commit"], icp)})
            for item in it["output_objects"]:
                allowed_paths.update({(ir, item["path"]), (it["output_commit"], item["path"])})
        assert downloads == expected_downloads
        assert len(downloads) == (45 + len(selected_files) if profile == "b2" else 51)
        assert len(failure_members) == (8 if profile == "b2" else 10)
        assert sum(op == "download" for op, *_ in api.reads) == (282 + len(selected_files) if profile == "b2" else 421)
        actual_paths = {(commit, member) for op, commit, _, members in api.reads if op == "paths" for member in members}
        assert actual_paths <= allowed_paths
        p = ["b1", "a1", "t4a2", "t4b2", "t4a2", "t4b2", "a1", "t4a2", "t4a2", "t4b2", "b1", "a1", "a1", "t4a2", "t4a2", "t4b2"]
        q = ["c2", "c1", "c1", "b1", "a1", "a1", "t4a2", "t4a2", "t4b2"]
        r = ["a2", "b2", "b2", "c2", "c1", "c1", "b1", "a1", "a1", "t4a2", "t4a2", "t4b2"]
        sequence = (["b2", "c2", "c1"] + p + q if profile == "b2" else ["a2", "b2", "c2", "c1"] + p + q + r)
        assert [rev for op, rev in api.calls if op == "metadata"] == [grading.BRANCH, *(input_revisions[role] for role in sequence)]
        assert len(sequence) + 1 == (29 if profile == "b2" else 42)
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        grade_revisions = {history.control_revision}
        for node in nodes.values():
            grade_revisions.update({node.revision, node.terminal["claim_commit"]})
        assert len(grade_revisions) == (15 if profile == "b2" else 17)
        all_revisions = set().union(*(set(reader._metadata_paths) | reader._inference_revisions
            | {rev for rev, _ in reader._downloads} for reader in readers))
        assert len(all_revisions) == (36 if profile == "b2" else 41) + (scenario == "advanced")

        before = copy.deepcopy((api.calls, api.reads))
        for reader in (*readers, *facades):
            assert not any(hasattr(reader, name) for name in ("create_commit", "create_branch", "create_repo", "__getattr__"))
            for revision, member in denied | deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    download(reader, revision, member)
            for revision, member in deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, paths=[member], expand=True)
            for revision in (grading.BRANCH, retained.BRANCH, *input_revisions.values()):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=revision, timeout=1)
        selected_members = selected_payloads | {(selected.revision, selected.path), (terminal["claim_commit"], selected.claim_path),
            (input_terminal, retained._paths(context.cell)[1]), (input_claim, retained._paths(context.cell)[0]),
            (input_output, retained._paths(context.cell)[2] + "/" + output.MANIFEST)}
        if profile == "b2":
            selected_members.add((parent.revision, parent.path))
        for revision, member in expected_downloads - selected_members:
            with pytest.raises(output.OutputPublicationRefused):
                download(readers[0], revision, member)
        for reader, role in zip(readers, roles):
            own = {(nodes[role].terminal["binding"]["retained"]["output_commit"],
                retained._paths(nodes[role].context.cell)[2] + "/" + name) for name in NAMES} if role in NG_ROLES else set()
            blocked = failure_members - own
            if role != profile:
                blocked |= selected_payloads
            for revision, member in blocked:
                with pytest.raises(output.OutputPublicationRefused):
                    download(reader, revision, member)
        for facade in facades:
            for revision, member in expected_downloads:
                with pytest.raises(output.OutputPublicationRefused):
                    download(facade, revision, member)
        assert (api.calls, api.reads) == before
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        late = {"bytes", "ledger_bytes", "raw_judge", "private_cost_reason", "denominator_type", "payload_source", "ledger_pointer", "outcome"}
        if profile == "a2":
            late.update({"a2:record:" + field for field in ("score", "child", "files", "outcome")})
            late.update({"recorder_zero", "recorder_invoice", "recorder_http", "completion_status", "completion_type",
                "completion_receipt", "completion_denominator", "inference_missing", "inference_deliverables",
                "a2:original:result", "a2:original:ledger", "facade_lost_a2"})
        if scenario not in late:
            assert not selected_payloads.intersection(downloads)
            assert not readers or not selected_payloads.intersection(readers[0]._downloads)
        if scenario == "lost_response" or scenario.startswith("facade_lost_"):
            assert public["http_status"] == 503
        if scenario.startswith("facade_lost_"):
            assert len(facades) == expected_count and lost_slots == [input_revisions[lost_role]]
        if scenario.startswith("c2_handoff_"):
            assert len(facades) == 3 and handoffs == ["c1"]
        elif scenario.startswith("b2_handoff_"):
            assert len(facades) == 3 and handoffs == ["c1", "b2"]
    assert all(not facade._open and not facade._metadata for facade in facades)
    assert all(not reader._inference_metadata for reader in readers)
    assert all(revision != retained.BRANCH for op, revision in api.calls if op == "metadata")
    if scenario == "replay" or scenario == "lost_response" or scenario.startswith("facade_lost_"):
        calls = copy.deepcopy((api.calls, api.reads))
        assert grading.main(args, _test_api=api, _test_transport=transport) == 2
        repeated = capsys.readouterr()
        assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused"
        assert (api.calls, api.reads) == calls
        for facade in facades:
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=input_terminal, timeout=1)
        assert (api.calls, api.reads) == calls
