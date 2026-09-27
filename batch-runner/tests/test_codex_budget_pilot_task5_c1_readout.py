"""Only ordinary task5 C1 after the genuine fixed B1/A1/A2 UNGRADED proof.

Synthetic writer history and accounting are not live grades, private revisions,
provider-authentication evidence or HTTP request counts.
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
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as approval
from . import test_codex_budget_pilot_task3_a1_readout as controls
from . import test_codex_budget_pilot_task3_c_readout as c_reader
from . import test_codex_budget_pilot_task5_b1_ungraded_readout as b1_reader
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_C_r1"
PARENT = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_B_r1"
A1 = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_A_r1"
A2 = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_A_r2"
BACKING = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r2"
REQUEST = "ed11b060948692463105b5981245f4cedfaa3e597418313a7c55dc9c580a41bf"
RUN = {"id": "36301834721", "job": "pilot-live", "attempt": 1}
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{150_000 + offset:040x}" for offset in range(1, 5))
VARIANTS = c_reader.VARIANTS


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _variants=VARIANTS):
    assert grading.TASK5_C1_CELL == CELL and grading.TASK5_RETAINED[CELL] == ("36259780431", REQUEST)
    assert readout.TASK5_C1_WRITER_RUN == RUN
    actual, parent = readout._writer_context(REQUEST), readout._writer_context(b1_reader.REQUEST)
    assert actual.plan["order"][21:27] == [readout.TASK4_C2_CELL, BACKING, A2, A1, PARENT, CELL]
    assert len(actual.plan["order"]) == 30 and len({WRITER, PRODUCER, OBSERVER}) == 3
    assert actual.controller_source_sha == parent.controller_source_sha == WRITER
    assert actual.plan["reviewed_source_sha"] == PRODUCER
    assert actual.terminal_revision == "" and actual.terminal_request == REQUEST
    assert actual.run.grader_config_json == parent.run.grader_config_json
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert not grading._model_free_context(actual) and grading._model_free_context(parent)

    # One genuine failed-parent history, not any previous selector or test body.
    prefix = b1_reader.history.__wrapped__(tmp_path_factory, _variants=("partial_cost",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task5-c1-readout-history")
    capture = _Capture()
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["partial_cost"]
            api = copy.deepcopy(previous.api)
            assert previous.terminal["format"] == ungraded.TERMINAL_FORMAT
            assert previous.terminal["binding"]["policy"] == "task5-b1-model-free-ungraded"
            assert previous.terminal["binding"]["github_run"] == b1_reader.RUN
            assert previous.terminal["outcome"] == "ungraded" and previous.terminal["model_invoked"] is False
            assert not {"child", "files", "score", "verdict"}.intersection(previous.terminal)
            assert not {CLAIM, OUTPUT, TERMINAL, ADVANCED}.intersection(api.trees)
            seeded = SimpleNamespace(api=api, context=grading.compile_request("pilot/" + CELL, PRODUCER, TERMINAL))
            with patch.context() as seed:
                for key, value in {"SOURCE": PRODUCER, "CLAIM": CLAIM, "OUTPUT": OUTPUT, "TERMINAL": TERMINAL}.items():
                    seed.setattr(base, key, value)
                base._seed_outputs(seeded, directory, extra_deliverable=True)
            cp, tp, ip = retained._paths(seeded.context.cell)
            input_parent = previous.terminal["binding"]["retained"]["terminal_commit"]
            prior_bytes = api.trees[input_parent][retained._paths(previous.context.cell)[1]]
            prior_input = pilot._json_object(prior_bytes)
            seeded.claim["binding"]["github_run"] = {"id": "36259780431", "job": "cell", "attempt": 1}
            seeded.claim["expected_parent"] = input_parent
            seeded.claim["predecessor"] = {"cell_id": PARENT, "terminal_commit": input_parent,
                "terminal_sha256": pilot._identity(prior_bytes)["sha256"], "output_commit": prior_input["output_commit"],
                "manifest_sha256": prior_input["manifest_identity"]["sha256"]}
            seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
            files = {name: data for name, data in api.trees[OUTPUT].items() if name.startswith(ip + "/")}
            api.seed(CLAIM, input_parent, {cp: retained._encoded(seeded.claim)})
            api.seed(OUTPUT, CLAIM, files)
            api.seed(TERMINAL, OUTPUT, {tp: retained._encoded(seeded.terminal)})
            api.branches[retained.BRANCH] = TERMINAL
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            request = pilot._digest(seeded.terminal["completion"])
            assert request != REQUEST  # Synthetic bytes cannot impersonate the actual supplied completion.
            patch.setitem(grading.TASK5_RETAINED, CELL, ("36259780431", request))
            shared = SimpleNamespace(rows={}, request=request, previous_context=previous.context,
                previous_revision=previous.revision, previous_path=previous.path,
                a1_context=initial.previous_context, a1_revision=initial.previous_revision, a1_path=initial.previous_path,
                a2_context=initial.a2_context, a2_revision=initial.a2_revision, a2_path=initial.a2_path,
                backing_context=initial.backing_context, backing_revision=initial.backing_revision,
                backing_path=initial.backing_path, control_cell=initial.control_cell,
                control_revision=initial.control_revision, control_path=initial.control_path,
                older_paths=initial.older_paths)
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                for variant in _variants:
                    destination = directory / variant
                    destination.mkdir()
                    current = SimpleNamespace(api=copy.deepcopy(api), context=readout._writer_context(request),
                        request=request, workflow=workflow, root=destination / "grade")
                    current.transport = base.Child(current)
                    current.api.events.clear()
                    with patch.context() as selected:
                        selected.setattr(base, "OUTPUT", OUTPUT)
                        selected.setenv("HF_TOKEN", base.TOKEN)
                        base._synthetic_rubric(current, selected)
                        approval._authorize(current, destination, selected, RUN["id"])
                        revision, path, terminal = writer._writer(current, capture, destination, selected, variant)
                    claim = retained._read(current.root / "claim-receipt.json")["claim"]
                    assert claim["expected_parent"] == previous.revision
                    assert claim["predecessor"] == {"cell_id": PARENT, "revision": previous.revision,
                                                   **pilot._identity(retained._encoded(previous.terminal))}
                    assert terminal["binding"]["github_run"] == RUN and terminal["format"] == grading.RESULT_FORMAT
                    assert terminal["child"]["entry_invoked"] is terminal["child"]["cleanup_confirmed"] is True
                    assert current.transport.calls == 1 and current.api.events == ["grade_claim", "judge", "grade_output"]
                    assert all(current.api.trees[commit] == tree for commit, tree in api.trees.items())
                    shared.rows[variant] = SimpleNamespace(api=current.api, context=current.context,
                        terminal=terminal, revision=revision, path=path)
            yield shared
    finally:
        prefix.close()


NG_ROLES = ("parent", "a1", "a2")
BINDING_FIELDS = ("controller_source_sha", "source_sha", "config_sha256", "grader_config_sha256",
                  "approval_request_sha256", "cell_id", "publication_receipt_sha256")
RUN_CHANGES = {"run": ("id", "36301834722"), "job": ("job", "grade"), "attempt": ("attempt", 2),
               "typed_attempt": ("attempt", True), "float_attempt": ("attempt", 1.0)}
ALIASES = ("parent_terminal", "parent_claim", "a1_terminal", "a1_claim", "a2_terminal", "a2_claim",
    "backing_terminal", "backing_claim", "control_terminal",
    *(f"{role}_input_{part}" for role in (*NG_ROLES, "backing") for part in ("terminal", "claim", "output")))
SCENARIOS = (*VARIANTS, "advanced", "replay", "plan", "closed_registry", "exclusions", "redacted_text",
    *(f"{role}:binding:{field}" for role in ("selected", *NG_ROLES) for field in BINDING_FIELDS),
    *(f"{role}:run:{field}" for role in ("selected", *NG_ROLES) for field in RUN_CHANGES),
    *(f"{role}:entry:{field}" for role in ("selected", *NG_ROLES) for field in ("grader_hash", "renderer")),
    *(f"{role}:record:{field}" for role in NG_ROLES for field in ("policy", "type", "model", "score", "child")),
    *(f"{role}:claim:{field}" for role in ("selected", *NG_ROLES) for field in ("type", "float", "format", "history", "carried")),
    *(f"{role}:parent:{field}" for role in ("selected", *NG_ROLES)
      for field in ("hash", "size_float", "cell", "carried", "carried_bytes")),
    "record_type", "no_child", "cleanup", "outcome", "bytes", "ledger_bytes", "path", "artifact_history",
    "claim_hash", "claim_bytes", "claim_extra", "terminal_history", "raw_judge", "private_cost_reason",
    "denominator_type", "payload_source", "ledger_pointer", "whole_observation", "parent_entry",
    "handoff_missing", "handoff_open", "handoff_wrong_owner", "handoff_changed_footprint",
    "recorder_zero", "recorder_invoice", "recorder_http", "completion_status", "completion_receipt",
    "completion_denominator", "inference_missing",
    *("backing_" + field for field in ("run", "writer", "source", "config", "renderer", "grader_hash",
        "no_child", "cleanup", "type", "missing", "claim_type")),
    *("control_" + field for field in ("missing", "bytes", "history", "carried")),
    *(f"{role}:input:{field}" for role in ("selected", *NG_ROLES) for field in
      ("run", "source", "config", "predecessor", "parent", "ack", "cleanup", "manifest")),
    *(f"{role}:original:{field}" for role in NG_ROLES for field in ("result", "ledger")),
    *(f"alias_{kind}_{target}" for kind in ("claim", "terminal") for target in ALIASES),
    *("own_claim_" + part for part in ("terminal", "claim", "output")), "input_terminal_alias_parent",
    "ordinal", "ref", "inference_ref", "host_ref", "observer_writer", "observer_producer", "observer_source",
    "source_preflight", "paid", "rerun", "producer_override", "wrong_phase", "private_target", "lost_response",
    "a1_facade_lost_response", "b1_facade_lost_response")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fixed_task5_c1_readout_after_ungraded(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["graded"])
    api = copy.deepcopy(row.api)
    nodes = {}
    for role, context, revision, path in (
        ("selected", row.context, row.revision, row.path),
        ("parent", history.previous_context, history.previous_revision, history.previous_path),
        ("a1", history.a1_context, history.a1_revision, history.a1_path),
        ("a2", history.a2_context, history.a2_revision, history.a2_path),
        ("backing", history.backing_context, history.backing_revision, history.backing_path),
    ):
        terminal = pilot._json_object(api.trees[revision][path])
        claim_path = grading._paths(context.cell)[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
        nodes[role] = SimpleNamespace(context=copy.deepcopy(context), revision=revision, path=path,
            terminal=terminal, claim=claim, claim_path=claim_path)
    selected, parent, a1, a2, backing = (nodes[role] for role in ("selected", "parent", "a1", "a2", "backing"))
    context, terminal, claim = selected.context, selected.terminal, selected.claim
    record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)
    changed, claim_overrides, corrupt_bytes, corrupt_history, remove = {"selected"}, {}, [], [], []
    names = ("step2_inference_results.json", Path(pilot.LEDGER).name)

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
            entry = node.terminal["binding"] if role == "selected" else node.terminal["binding"]["predecessor_entry"]
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
                    "score": ("score", 0), "child": ("child", {"entry_invoked": True})}[field]
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
            previous = nodes[{"selected": "parent", "parent": "a1", "a1": "a2", "a2": "backing"}[role]]
            if field == "carried":
                corrupt_history.append((node.terminal["claim_commit"], previous.path, node.terminal["claim_commit"]))
            elif field == "carried_bytes":
                corrupt_bytes.append((node.terminal["claim_commit"], previous.path))
            else:
                key, value = {"hash": ("sha256", "9" * 64),
                    "size_float": ("size", float(node.claim["predecessor"]["size"])), "cell": ("cell_id", CELL)}[field]
                node.claim["predecessor"][key] = value
                changed.add(role)
        elif kind == "original":
            corrupt_bytes.append((node.terminal["binding"]["retained"]["output_commit"],
                retained._paths(node.context.cell)[2] + "/" + names[field == "ledger"]))
        elif kind == "input":
            icp, itp, ip = retained._paths(node.context.cell)
            ir = node.terminal["binding"]["retained"]["terminal_commit"]
            original = pilot._json_object(api.trees[ir][itp])
            original_claim = pilot._json_object(api.trees[original["claim_commit"]][icp])
            if field == "run":
                original_claim["binding"]["github_run"]["id"] = "36259780432"
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
        api.seed(ADVANCED, selected.revision, {"unrelated/PRIVATE": b"PRIVATE"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = ADVANCED
    elif scenario in {"no_child", "cleanup"}:
        terminal["child"]["entry_invoked" if scenario == "no_child" else "cleanup_confirmed"] = False
    elif scenario == "record_type":
        terminal["format"] = ungraded.TERMINAL_FORMAT
    elif scenario == "outcome":
        terminal["outcome"] = "failed"
    elif scenario in {"exclusions", "redacted_text", "raw_judge", "private_cost_reason", "denominator_type",
                      "payload_source", "ledger_pointer"}:
        payload = pilot._json_object(api.trees[selected.revision][record["path"]])
        task = payload["tasks"][0]
        if scenario == "exclusions":
            task["items"][1].update(score_excluded=True, verdict="judge_error", awarded_score=0,
                model_did_right=False, decided_by="judge")
            task.update(total_awarded=2, total_max=2, pct=100, score_excluded_items=1, score_excluded_max=2,
                pct_full_denominator=50)
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
    elif scenario in {"bytes", "ledger_bytes"}:
        item = record if scenario == "bytes" else next(item for item in terminal["files"] if item["role"] == "grade_cost_ledger")
        corrupt_bytes.append((selected.revision, item["path"]))
    elif scenario == "path":
        record["path"] = "PRIVATE/foreign.json"
    elif scenario == "artifact_history":
        corrupt_history.append((selected.revision, record["path"], terminal["claim_commit"]))
    elif scenario == "claim_bytes":
        corrupt_bytes.append((terminal["claim_commit"], selected.claim_path))
    elif scenario == "claim_extra":
        claim["extra"] = "PRIVATE"
    elif scenario == "terminal_history":
        corrupt_history.append((selected.revision, selected.path, terminal["claim_commit"]))
    elif scenario.startswith("recorder_"):
        key, value = {"recorder_zero": ("known_cost_usd", 0), "recorder_invoice": ("invoice_complete", True),
                      "recorder_http": ("http_request_count", 0)}[scenario]
        parent.terminal["recorder_accounting"][key] = value
        changed.add("parent")
    elif scenario.startswith("completion_"):
        if scenario == "completion_receipt":
            parent.terminal["inference_completion"]["receipt"]["known_cost_usd"] = 0
        else:
            key, value = {"completion_status": ("status", "succeeded"), "completion_denominator": ("denominator", 1)}[scenario]
            parent.terminal["inference_completion"][key] = value
        changed.add("parent")
    elif scenario == "inference_missing":
        parent.terminal["inference_missing"] = ["PRIVATE"]
        changed.add("parent")
    elif scenario.startswith("backing_"):
        if scenario == "backing_missing":
            remove.append((backing.revision, backing.path))
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
    elif scenario.startswith(("alias_", "own_claim_")):
        targets = {"control_terminal": history.control_revision}
        for role in (*NG_ROLES, "backing"):
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
        # Keep ancestor bytes/history intact. C1's ordinary artifacts must also
        # exist with coherent history, so alias refusals cannot pass on absence.
        members = [selected.claim_path, parent.path]
        if kind == "terminal":
            members.extend([selected.path, *(item["path"] for item in terminal["files"])])
        for member in members:
            api.trees[alias][member] = api.trees[original_revision][member]
            api.writers[alias][member] = api.writers[original_revision][member]
        if kind == "claim":
            terminal["claim_commit"] = alias
            api.writers[alias][selected.claim_path] = api.writers[selected.revision][selected.claim_path] = alias
        else:
            selected.revision = alias
            for member in [selected.path, *(item["path"] for item in terminal["files"])]:
                api.writers[alias][member] = alias
            api.branches[grading.BRANCH] = alias
    elif scenario == "input_terminal_alias_parent":
        icp, itp, _ = retained._paths(context.cell)
        original = pilot._json_object(api.trees[TERMINAL][itp])
        for member in (itp, icp, *(item["path"] for item in original["output_objects"])):
            api.trees[parent.revision][member] = api.trees[TERMINAL][member]
            api.writers[parent.revision][member] = api.writers[TERMINAL][member]
        api.writers[parent.revision][itp] = parent.revision
        terminal["binding"]["retained"]["terminal_commit"] = parent.revision
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            current = compile_writer(request)
            if current.cell["cell_id"] == CELL:
                current.plan["order"][25:27] = [CELL, PARENT]
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

    # Carry repaired identities through only the fixed B2 -> A2 -> A1 -> B1 -> C1
    # synthetic controls before applying each deliberate byte/history failure.
    for role in ("backing", "a2", "a1", "parent", "selected"):
        if role not in changed:
            continue
        node = nodes[role]
        data = controls._store_grade(api, node.revision, node.path, node.terminal, node.claim)
        if role in claim_overrides:
            field = claim_overrides[role]
            if field == "format":
                node.claim["format"] = ungraded.CLAIM_FORMAT if role == "selected" else grading.CLAIM_FORMAT
            else:
                node.claim["binding"]["github_run"]["attempt"] = True if field == "type" else 1.0
            encoded = retained._encoded(node.claim)
            for commit in (node.terminal["claim_commit"], node.revision):
                api.trees[commit][node.claim_path] = encoded
            node.terminal["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(node.terminal)
            api.trees[node.revision][node.path] = data
        if role != "selected":
            child_role = {"backing": "a2", "a2": "a1", "a1": "parent", "parent": "selected"}[role]
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
        pytest.fail("task5 C1 reader crossed a model, auth, model-free projection or write boundary")
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
    monkeypatch.setattr(readout, "_ungraded_projection", forbidden)
    readers, facades, ordinary, records, completed, verified_ng, handoffs = [], [], [], [], [], [], []
    initialize = readout._ReadOnlyGrade.__init__
    a1_facade_init, b1_facade_init = readout._Task5A1NativeReads.__init__, readout._Task5B1NativeReads.__init__
    ordinary_terminal, record_terminal = grading._grade_terminal, ungraded.verify_terminal
    verify_ng, predecessor, grant = readout._verified_ungraded, readout._verify_predecessor, readout._ReadOnlyGrade.allow_verified_files
    selected_files = {(selected.revision, item["path"]) for item in terminal["files"]}
    original = pilot._json_object(row.api.trees[TERMINAL][retained._paths(context.cell)[1]])
    selected_originals = {(OUTPUT, item["path"]) for item in original["output_objects"]
                          if not item["path"].endswith("/" + output.MANIFEST)}
    denied = {(backing.revision, item["path"]) for item in backing.terminal["files"]}
    denied.update((backing.terminal["binding"]["retained"]["output_commit"],
        retained._paths(backing.context.cell)[2] + "/" + name) for name in names)
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
        assert facade._open and not handoffs
        own = nodes["parent" if current.cell["cell_id"] == PARENT else "a1"]
        own_members = {(own.terminal["binding"]["retained"]["output_commit"],
            retained._paths(current.cell)[2] + "/" + name) for name in names}
        assert not own_members.intersection(owner._downloads)
        assert not selected_files.intersection(readers[0]._downloads)
        assert not (selected_files | selected_originals).intersection(
            (rev, name) for op, rev, name, _ in api.reads if op == "download")
        before = copy.deepcopy((api.calls, api.reads))
        for wrong in (grading.BRANCH, retained.BRANCH, previous_context.terminal_revision,
                      context.terminal_revision, "9" * 40):
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(repo_id=api.repo, repo_type="dataset", revision=wrong, token=base.TOKEN, timeout=1)
        for wrong in ({"repo_id": "PRIVATE/wrong"}, {"repo_type": "model"}, {"token": "PRIVATE"}):
            kwargs = dict(repo_id=api.repo, repo_type="dataset", revision=current.terminal_revision, token=base.TOKEN, timeout=1)
            kwargs.update(wrong)
            with pytest.raises(output.OutputPublicationRefused):
                facade.repo_info(**kwargs)
        wrong_owner = {(owner.revision, a2.path), (previous_context.terminal_revision, owner._claim)}
        for rev, member in denied | deeper | wrong_owner | selected_files | selected_originals | own_members:
            with pytest.raises(output.OutputPublicationRefused):
                facade.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=rev, filename=member, cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
        for rev, member in deeper | wrong_owner | selected_files | selected_originals:
            with pytest.raises(output.OutputPublicationRefused):
                facade.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=rev, paths=[member], expand=True)
        assert (api.calls, api.reads) == before

    def remember_a1_facade(facade, owner, prior, current, previous_context):
        a1_facade_init(facade, owner, prior, current, previous_context)
        facades.append(facade)
        assert current.cell["cell_id"] == A1 and completed == [A2] and ordinary == [CELL, BACKING, BACKING]
        probe_open(facade, owner, current, previous_context)

    def remember_b1_facade(facade, owner, prior, current, previous_context, proof):
        b1_facade_init(facade, owner, prior, current, previous_context, proof)
        facades.append(facade)
        assert current.cell["cell_id"] == PARENT and completed == [A2, A2, A1] and ordinary == [CELL, BACKING, BACKING, BACKING]
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
        assert current.cell["cell_id"] in {CELL, BACKING}
        result = ordinary_terminal(client, repo, revision, current, *args, **kwargs)
        ordinary.append(current.cell["cell_id"])
        return result

    def verify_record(client, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] in {PARENT, A1, A2}
        records.append(current.cell["cell_id"])
        result = record_terminal(client, repo, revision, current, *args, **kwargs)
        completed.append(current.cell["cell_id"])
        if ((type(client) is readout._Task5A1NativeReads and current.cell["cell_id"] == A1)
                or (type(client) is readout._Task5B1NativeReads and current.cell["cell_id"] == PARENT)):
            assert client._open and not client._metadata
            before = copy.deepcopy((api.calls, api.reads))
            with pytest.raises(output.OutputPublicationRefused):
                client.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=current.terminal_revision, timeout=1)
            # Selected ordinary files must stay closed even when every native
            # metadata slot is consumed but the verifier facade remains open.
            for rev, member in selected_files | selected_originals | denied | deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    client.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=rev, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
            assert (api.calls, api.reads) == before
        return result

    def verified_record(reader, current, *args, **kwargs):
        result, entry, files = verify_ng(reader, current, *args, **kwargs)
        verified_ng.append(current.cell["cell_id"])
        assert not handoffs and not selected_files.intersection(readers[0]._downloads)
        if current.cell["cell_id"] == PARENT:
            assert reader._task5_b1_proof is facades[1]
            assert not reader._task5_b1_proof._open and not reader._task5_b1_proof._metadata
            if scenario == "parent_entry":
                entry = {**entry, "config_hash": "9" * 16}
            elif scenario == "handoff_missing":
                reader.__dict__.pop("_task5_b1_proof")
            elif scenario in {"handoff_open", "handoff_wrong_owner"}:
                # Inject a malformed proof without reopening a genuine facade.
                proof = copy.copy(reader._task5_b1_proof)
                if scenario == "handoff_open":
                    proof._open = True
                else:
                    proof._owners = (proof._owners[1], proof._owners[0], proof._owners[2])
                reader._task5_b1_proof = proof
            elif scenario == "handoff_changed_footprint":
                reader._metadata_paths["9" * 40] = {"PRIVATE"}
        return result, entry, files

    def verified_predecessor(reader, current, *args, **kwargs):
        assert reader is readers[0] and current.cell["cell_id"] == CELL
        result = predecessor(reader, current, *args, **kwargs)
        handoffs.append(CELL)
        return result

    def grant_selected(reader, members):
        assert reader is readers[0] and handoffs == [CELL] and verified_ng == [A2, A1, PARENT]
        assert completed == [A2, A2, A1, A2, A1, PARENT]
        assert all(not facade._open and not facade._metadata for facade in facades)
        assert all("_task5_a1_proof" not in owner.__dict__ and "_task5_b1_proof" not in owner.__dict__ for owner in readers)
        assert not selected_files.intersection(reader._downloads)
        return grant(reader, members)

    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(readout._Task5A1NativeReads, "__init__", remember_a1_facade)
    monkeypatch.setattr(readout._Task5B1NativeReads, "__init__", remember_b1_facade)
    monkeypatch.setattr(grading, "_grade_terminal", verify_ordinary)
    monkeypatch.setattr(ungraded, "verify_terminal", verify_record)
    monkeypatch.setattr(readout, "_verified_ungraded", verified_record)
    monkeypatch.setattr(readout, "_verify_predecessor", verified_predecessor)
    monkeypatch.setattr(readout._ReadOnlyGrade, "allow_verified_files", grant_selected)
    if scenario == "whole_observation":
        bind_retained = readout._ReadOnlyGrade.bind_retained
        def wrong_observation(reader, binding, current, *args, **kwargs):
            value = bind_retained(reader, binding, current, *args, **kwargs)
            return {**value, "extra": True} if current.cell["cell_id"] == CELL else value
        monkeypatch.setattr(readout._ReadOnlyGrade, "bind_retained", wrong_observation)
    elif scenario in {"a1_facade_lost_response", "b1_facade_lost_response"}:
        repo_info = readout._ReadOnlyGrade.repo_info
        def lost_before_owner_consumes(reader, **kwargs):
            count = 1 if scenario.startswith("a1_") else 2
            if len(facades) == count and reader is readers[2 if scenario.startswith("a1_") else 1]:
                raise output.OutputPublicationRefused("PRIVATE", http_status=503)
            return repo_info(reader, **kwargs)
        monkeypatch.setattr(readout._ReadOnlyGrade, "repo_info", lost_before_owner_consumes)

    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
        "GITHUB_RUN_ID": "900053", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
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
    args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", source, "--terminal-revision", history.request,
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
    assert not (denied | deeper | selected_originals).intersection(downloads)
    accepted = {*VARIANTS, "advanced", "replay", "exclusions", "redacted_text"}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        if scenario == "closed_registry":
            requests = controls._unregistered_requests()
            assert len(requests) == 5 and history.request not in requests
            assert context.plan["order"][24:28] == [A1, PARENT, CELL, grading.TASK5_C2_CELL]
            assert context.plan["order"][28:] == [grading.TASK5_B2_CELL, grading.TASK5_A2_CELL]
            assert set(requests) == {*(grading.TASK5_RETAINED[cell][1] for cell in context.plan["order"][28:]),
                                     "9" * 64, "9" * 40, ""}
            assert not grading._model_free_context(readout._writer_context(history.request))
            assert CELL not in readout.TASK4_SUCCESSOR_READOUTS and CELL not in readout.TASK3_SUCCESSOR_READOUTS
            for request in requests:
                closed = list(args)
                closed[5] = request
                assert grading.main(closed, _test_api=api) == 2
                refused = capsys.readouterr()
                assert not refused.out and json.loads(refused.err)["outcome"] == "refused"
                assert not api.calls and not root.exists()
    elif scenario in accepted:
        assert code == 0 and public["outcome"] == "verified_retained_grade", public
        assert public["grade_state"] == (scenario if scenario in {"partial", "failed", "ungraded"} else "graded")
        assert not {"record_kind", "inference_accounting", "recorder_accounting", "child", "verdict"}.intersection(public)
        assert public["grade_revision"] == selected.revision and public["inference_terminal"] == TERMINAL
        assert public["inference_request_checksum"] == history.request and public["observer_source_sha"] == OBSERVER
        assert public["grader_source_hash"] == readout.TASK3_A1_GRADER_SOURCE_HASH
        assert public["grader_config_sha256"] == readout.CONFIG_SHA256 and public["expected_tasks"] == 1
        assert public["proof_boundary"] == grading.PROOF
        if scenario in {"partial", "failed", "ungraded"}:
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
        elif scenario in {"partial_cost", "price_missing"}:
            receipt = public["ledger_derived_cost"]
            assert receipt["model_calls"] == (2 if scenario == "partial_cost" else 1)
            assert receipt["usage"] == {"input_tokens": 111, "output_tokens": 23, "cached_input_tokens": 17,
                "reasoning_tokens": 8, "audio_input_tokens": None, "audio_output_tokens": None}
            assert receipt["missing_reasons"] == ["call_reachability_unknown" if scenario == "partial_cost" else "price_missing"]
            if scenario == "partial_cost":
                assert receipt["known_cost_usd"] > 0 and receipt["estimated_cost_usd"] is None
            else:
                assert receipt["known_cost_usd"] is receipt["estimated_cost_usd"] is None
        else:
            assert public["ledger_derived_cost"]["estimated_cost_usd"] is None
            assert public["ledger_derived_cost"]["missing_reasons"] == ["call_reachability_unknown"]
        for receipt in (public["recorded_task_cost"], public["recorded_summary_cost"], public["ledger_derived_cost"]):
            if receipt is not None:
                assert receipt["invoice_complete"] is False and receipt["http_request_count"] is None
        assert len(readers) == 5 and len(facades) == 2 and handoffs == [CELL] and verified_ng == [A2, A1, PARENT]
        assert ordinary == [CELL, BACKING, BACKING, BACKING, BACKING]
        assert records == [A2, A1, A2, PARENT, A1, A2] and completed == [A2, A2, A1, A2, A1, PARENT]
        head = ADVANCED if scenario == "advanced" else selected.revision
        assert public["observed_branch_head"] == head
        expected_downloads = selected_files | {(history.control_revision, history.control_path)}
        allowed_paths = {(head, selected.path)}
        inputs, failure_members = [], set()
        for role in ("selected", "parent", "a1", "a2", "backing"):
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
        assert downloads == expected_downloads and len(downloads) == 32 + len(selected_files)
        assert sum(op == "download" for op, *_ in api.reads) == 167 + len(selected_files)
        actual_paths = {(commit, name) for op, commit, _, members in api.reads if op == "paths" for name in members}
        assert actual_paths <= allowed_paths
        ic1, ib1, ia1, ia2, ib2 = inputs
        assert [rev for op, rev in api.calls if op == "metadata"] == [grading.BRANCH,
            ic1, ib1, ia1, ia2, ib2, ia2, ib2, ia1, ia2, ia2, ib2, ib1, ia1, ia1, ia2, ia2, ib2]
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        grade_revisions = {history.control_revision}
        for node in nodes.values():
            grade_revisions.update({node.revision, node.terminal["claim_commit"]})
        assert len(grade_revisions) == 11
        before = copy.deepcopy((api.calls, api.reads))
        for reader in (*readers, *facades):
            assert not any(hasattr(reader, name) for name in ("create_commit", "create_branch", "create_repo", "__getattr__"))
            for revision, member in denied | deeper | selected_originals:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
            for revision, member in deeper:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.get_paths_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, paths=[member], expand=True)
            for revision in (grading.BRANCH, retained.BRANCH, ic1, ib1, ia1, ia2, ib2):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=revision, timeout=1)
        # C1 owns only its controls/artifacts and B1's single terminal-control
        # grant. Even after success it cannot read any parent failure payload.
        selected_members = selected_files | {(selected.revision, selected.path),
            (terminal["claim_commit"], selected.claim_path), (TERMINAL, retained._paths(context.cell)[1]),
            (CLAIM, retained._paths(context.cell)[0]), (OUTPUT, retained._paths(context.cell)[2] + "/" + output.MANIFEST),
            (parent.revision, parent.path)}
        for revision, member in expected_downloads - selected_members:
            with pytest.raises(output.OutputPublicationRefused):
                readers[0].hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                    revision=revision, filename=member, cache_dir=tmp_path,
                    force_download=True, local_files_only=False, etag_timeout=1)
        for owner, role in ((readers[1], "parent"), (readers[2], "a1"), (readers[3], "a2"), (readers[4], "backing")):
            own_members = {(nodes[role].terminal["binding"]["retained"]["output_commit"],
                retained._paths(nodes[role].context.cell)[2] + "/" + name) for name in names} if role in NG_ROLES else set()
            for revision, member in (failure_members - own_members) | selected_files:
                with pytest.raises(output.OutputPublicationRefused):
                    owner.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=revision, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
        assert (api.calls, api.reads) == before
        assert all("_task5_a1_proof" not in reader.__dict__ and "_task5_b1_proof" not in reader.__dict__ for reader in readers)
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused" and api.calls == calls
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario not in {"outcome", "raw_judge", "private_cost_reason", "denominator_type", "payload_source", "ledger_pointer"}:
            assert not selected_files.intersection(downloads) and not handoffs
        if scenario in {"lost_response", "a1_facade_lost_response", "b1_facade_lost_response"}:
            assert public["http_status"] == 503
        if scenario == "a1_facade_lost_response":
            assert len(facades) == 1
        elif scenario == "b1_facade_lost_response":
            assert len(facades) == 2
        if ((scenario.startswith("alias_") and not scenario.endswith(("parent_terminal", "parent_claim")))
                or scenario == "input_terminal_alias_parent" or scenario.startswith("handoff_")):
            assert verified_ng == [A2, A1, PARENT] and completed == [A2, A2, A1, A2, A1, PARENT]
            assert ordinary == [CELL, BACKING, BACKING, BACKING, BACKING]
            assert all("_task5_b1_proof" not in reader.__dict__ for reader in readers)
    assert all(not facade._open and not facade._metadata for facade in facades)
    assert all(not reader._inference_metadata for reader in readers)
    assert all(revision != retained.BRANCH for op, revision in api.calls if op == "metadata")
