"""Only actual B1's ordinary reader after a genuine synthetic no-judge A1.

The shared writer history uses fake external/model seams. Synthetic payloads,
accounting and revisions are not live evidence or an inferred grade outcome.
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
from . import test_codex_budget_pilot_task3_a1_readout as a1_reader
from . import test_codex_budget_pilot_task3_c_readout as c_reader
from . import test_codex_budget_pilot_task4_a1_ungraded_readout as ng_reader
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — every live boundary blocked

CELL = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_B_r1"
REQUEST = "f3546942ebac25c3c3cd1788dfb792a80e3e10f465999bebf7730fb651cb2bde"
RUN = {"id": "36292532223", "job": "pilot-live", "attempt": 1}
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{90_000 + offset:040x}" for offset in range(1, 5))
VARIANTS = c_reader.VARIANTS


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _variants=VARIANTS):
    assert grading.TASK4_B1_CELL == CELL
    assert grading.TASK4_RETAINED[CELL] == ("36235926112", REQUEST)
    assert readout.TASK4_B1_WRITER_RUN == RUN and CELL not in readout.TASK3_SUCCESSOR_READOUTS
    actual, parent = readout._writer_context(REQUEST), readout._writer_context(ng_reader.REQUEST)
    assert actual.plan["order"][17:20] == [readout.TASK3_A2_CELL, ng_reader.CELL, CELL]
    assert len(actual.plan["order"]) == 30 and len({WRITER, PRODUCER, OBSERVER}) == 3
    assert actual.controller_source_sha == parent.controller_source_sha == WRITER
    assert actual.plan["reviewed_source_sha"] == PRODUCER
    assert actual.terminal_revision == "" and actual.terminal_request == REQUEST
    assert actual.run.grader_config_json == parent.run.grader_config_json
    assert hashlib.sha256(actual.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert readout._writer_run(parent) == ng_reader.RUN
    assert not grading._model_free_context(actual) and grading._model_free_context(parent)

    # Build the backing history once and only one A1 accounting variant.
    # No previous reader test body runs, and no success-shaped A1 is substituted.
    prefix = ng_reader.history.__wrapped__(tmp_path_factory, _variants=("partial_cost",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task4-b1-readout-history")
    capture = _Capture()
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["partial_cost"]
            api = copy.deepcopy(previous.api)
            assert previous.terminal["format"] == ungraded.TERMINAL_FORMAT
            assert previous.terminal["binding"]["policy"] == ungraded.POLICY
            assert previous.terminal["outcome"] == "ungraded" and previous.terminal["model_invoked"] is False
            assert not {"child", "files", "score", "verdict"}.intersection(previous.terminal)
            assert not {CLAIM, OUTPUT, TERMINAL, ADVANCED}.intersection(api.trees)
            seeded = SimpleNamespace(api=api, context=grading.compile_request("pilot/" + CELL, PRODUCER, TERMINAL))
            with patch.context() as seed:
                for key, value in {"SOURCE": PRODUCER, "CLAIM": CLAIM, "OUTPUT": OUTPUT, "TERMINAL": TERMINAL}.items():
                    seed.setattr(base, key, value)
                base._seed_outputs(seeded, directory, extra_deliverable=True)
            cp, tp, input_prefix = retained._paths(seeded.context.cell)
            input_parent = previous.terminal["binding"]["retained"]["terminal_commit"]
            prior_bytes = api.trees[input_parent][retained._paths(previous.context.cell)[1]]
            prior_input = pilot._json_object(prior_bytes)
            seeded.claim["binding"]["github_run"] = {"id": "36235926112", "job": "cell", "attempt": 1}
            seeded.claim["expected_parent"] = input_parent
            seeded.claim["predecessor"] = {"cell_id": ng_reader.CELL, "terminal_commit": input_parent,
                "terminal_sha256": pilot._identity(prior_bytes)["sha256"], "output_commit": prior_input["output_commit"],
                "manifest_sha256": prior_input["manifest_identity"]["sha256"]}
            seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
            files = {name: data for name, data in api.trees[OUTPUT].items() if name.startswith(input_prefix + "/")}
            api.seed(CLAIM, input_parent, {cp: retained._encoded(seeded.claim)})
            api.seed(OUTPUT, CLAIM, files)
            api.seed(TERMINAL, OUTPUT, {tp: retained._encoded(seeded.terminal)})
            api.branches[retained.BRANCH] = TERMINAL
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            request = pilot._digest(seeded.terminal["completion"])
            assert request != REQUEST
            patch.setitem(grading.TASK4_RETAINED, CELL, ("36235926112", request))
            shared = SimpleNamespace(rows={}, request=request, previous_context=previous.context,
                previous_revision=previous.revision, previous_path=previous.path,
                backing_context=initial.previous_context, backing_revision=initial.previous_revision,
                backing_path=initial.previous_path, intrinsic_cell=initial.backing_cell,
                intrinsic_revision=initial.backing_revision, intrinsic_path=initial.backing_path,
                historical_path=initial.historical_path)
            assert shared.backing_context.cell["cell_id"] == readout.TASK3_A2_CELL
            assert shared.intrinsic_cell["cell_id"] == readout.TASK3_B2_CELL
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
                    assert claim["predecessor"] == {"cell_id": ng_reader.CELL, "revision": previous.revision,
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


SCENARIOS = (*VARIANTS, "advanced", "replay", "plan", "closed_registry", "exclusions", "redacted_text",
    "writer", "producer", "run", "job", "attempt", "typed_attempt", "config", "grader_config", "grader_hash",
    "renderer", "approval", "cell", "record_type", "cleanup", "no_child", "outcome", "bytes", "ledger_bytes",
    "path", "artifact_history", "claim_hash", "claim_bytes", "claim_type", "claim_float", "claim_extra",
    "claim_format", "claim_history", "claim_carried_bytes", "terminal_history", "raw_judge", "private_cost_reason",
    "denominator_type", "payload_source", "ledger_pointer", "inference_run", "inference_source", "inference_config",
    "inference_predecessor", "inference_parent", "inference_receipt", "inference_cleanup", "inference_manifest",
    "previous_run", "previous_writer", "previous_source", "previous_policy", "previous_approval", "previous_cell",
    "previous_grader_hash", "previous_config", "previous_renderer", "previous_type", "previous_score", "previous_child",
    "previous_completion", "previous_receipt", "previous_recorder", "previous_claim_type", "previous_hash",
    "previous_carried", "previous_carried_bytes", "previous_size", "previous_missing", "previous_original_result",
    "previous_original_ledger", "previous_inference_run", "previous_inference_source", "previous_inference_predecessor",
    "previous_inference_cleanup", "previous_inference_deliverables", "backing_run", "backing_writer", "backing_no_child",
    "backing_cleanup", "backing_renderer", "backing_type", "backing_claim_type", "backing_carried", "backing_missing",
    "intrinsic_bytes", "intrinsic_history", "intrinsic_carried", "intrinsic_missing", "parent_claim_alias",
    "parent_terminal_alias", "a1_claim_alias_selected_claim", "a1_claim_alias_selected_terminal",
    "a2_claim_alias_selected_claim", "a2_claim_alias_selected_terminal", "intrinsic_alias_selected_claim",
    "intrinsic_alias_selected_terminal", "ordinal", "ref", "inference_ref", "host_ref", "observer_writer",
    "observer_producer", "observer_source", "source_preflight", "paid", "rerun", "producer_override", "wrong_phase",
    "private_target", "lost_response")


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_fixed_task4_b1_readout_after_ungraded(history, tmp_path, monkeypatch, capsys, scenario):
    row = history.rows.get(scenario, history.rows["graded"])
    api, context, terminal = copy.deepcopy(row.api), copy.deepcopy(row.context), copy.deepcopy(row.terminal)
    revision, path = row.revision, row.path
    cp = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][cp])
    previous_revision, previous_path = history.previous_revision, history.previous_path
    previous = pilot._json_object(api.trees[previous_revision][previous_path])
    pcp = grading._paths(history.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][pcp])
    backing_revision, backing_path = history.backing_revision, history.backing_path
    backing = pilot._json_object(api.trees[backing_revision][backing_path])
    bcp = grading._paths(history.backing_context.cell)[0]
    backing_claim = pilot._json_object(api.trees[backing["claim_commit"]][bcp])
    record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)
    changed_previous = changed_backing = False
    if scenario == "advanced":
        api.seed(ADVANCED, revision, {"unrelated/PRIVATE": b"PRIVATE"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = ADVANCED
    elif scenario in {"writer", "producer", "config", "grader_config", "grader_hash", "approval", "cell"}:
        key = {"writer": "controller_source_sha", "producer": "source_sha", "config": "config_hash",
               "grader_config": "grader_config_sha256", "grader_hash": "grader_source_hash",
               "approval": "approval_request_sha256", "cell": "cell_id"}[scenario]
        terminal["binding"][key] = "PRIVATE"
    elif scenario in {"run", "job", "attempt", "typed_attempt"}:
        key, value = {"run": ("id", "36292532224"), "job": ("job", "grade"),
                      "attempt": ("attempt", 2), "typed_attempt": ("attempt", True)}[scenario]
        terminal["binding"]["github_run"][key] = value
        terminal["binding"]["approval_request_sha256"] = grading._context_approval(context, terminal["binding"]["github_run"])
    elif scenario == "renderer":
        terminal["binding"]["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
    elif scenario in {"cleanup", "no_child"}:
        terminal["child"]["cleanup_confirmed" if scenario == "cleanup" else "entry_invoked"] = False
    elif scenario == "record_type":
        terminal["format"] = ungraded.TERMINAL_FORMAT
    elif scenario == "outcome":
        terminal["outcome"] = "failed"
    elif scenario in {"exclusions", "redacted_text", "raw_judge", "private_cost_reason", "denominator_type",
                      "payload_source", "ledger_pointer"}:
        payload = pilot._json_object(api.trees[revision][record["path"]])
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
        api.trees[revision][record["path"]] = data
        record.update(retained._object(record["path"], data))
    elif scenario in {"bytes", "ledger_bytes"}:
        item = record if scenario == "bytes" else next(item for item in terminal["files"] if item["role"] == "grade_cost_ledger")
        api.trees[revision][item["path"]] += b"PRIVATE"
    elif scenario == "path":
        record["path"] = "PRIVATE/foreign.json"
    elif scenario == "claim_extra":
        claim["extra"] = "PRIVATE"
    elif scenario == "claim_format":
        claim["format"] = ungraded.CLAIM_FORMAT
    elif scenario in {"claim_history", "terminal_history", "artifact_history"}:
        commit, member, last = {"claim_history": (revision, cp, revision),
            "terminal_history": (revision, path, terminal["claim_commit"]),
            "artifact_history": (revision, record["path"], terminal["claim_commit"])}[scenario]
        api.writers[commit][member] = last
    elif scenario.startswith("inference_") and scenario != "inference_ref":
        icp, itp, ip = retained._paths(context.cell)
        original = pilot._json_object(api.trees[TERMINAL][itp])
        original_claim = pilot._json_object(api.trees[CLAIM][icp])
        if scenario == "inference_run":
            original_claim["binding"]["github_run"]["id"] = "36235926113"
        elif scenario in {"inference_source", "inference_config"}:
            original_claim["binding"]["source_sha" if scenario == "inference_source" else "config_sha256"] = "9" * 64
        elif scenario == "inference_predecessor":
            original_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "inference_parent":
            original_claim["expected_parent"] = "9" * 40
        elif scenario == "inference_receipt":
            original["publication_receipt_sha256"] = "9" * 64
        elif scenario == "inference_cleanup":
            original["completion"]["cleanup_confirmed"] = False
        else:
            api.trees[OUTPUT][ip + "/" + output.MANIFEST] += b"PRIVATE"
        encoded = retained._encoded(original_claim)
        for commit in (CLAIM, OUTPUT, TERMINAL):
            api.trees[commit][icp] = encoded
        original["claim_identity"] = pilot._identity(encoded)
        encoded = retained._encoded(original)
        api.trees[TERMINAL][itp] = encoded
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(encoded)["sha256"]
    elif scenario in {"previous_run", "previous_writer", "previous_source", "previous_policy", "previous_approval",
                      "previous_cell", "previous_grader_hash", "previous_config", "previous_renderer", "previous_type",
                      "previous_score", "previous_child", "previous_completion", "previous_receipt", "previous_recorder"}:
        changed_previous = True
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = "36291118507"
            previous["binding"]["approval_request_sha256"] = grading._context_approval(
                history.previous_context, previous["binding"]["github_run"])
        elif scenario in {"previous_writer", "previous_source", "previous_policy", "previous_approval", "previous_cell"}:
            key = {"previous_writer": "controller_source_sha", "previous_source": "source_sha", "previous_policy": "policy",
                   "previous_approval": "approval_request_sha256", "previous_cell": "cell_id"}[scenario]
            previous["binding"][key] = ungraded.A2_POLICY if scenario == "previous_policy" else "PRIVATE"
        elif scenario in {"previous_grader_hash", "previous_config", "previous_renderer"}:
            entry = previous["binding"]["predecessor_entry"]
            if scenario == "previous_renderer":
                entry["renderer_fingerprint"]["pymupdf_version"] = "PRIVATE"
            else:
                entry["grader_source_hash" if scenario == "previous_grader_hash" else "config_hash"] = "PRIVATE"
        elif scenario == "previous_type":
            previous["format"] = grading.RESULT_FORMAT
        elif scenario == "previous_score":
            previous["score"] = 0
        elif scenario == "previous_child":
            previous["child"] = {"entry_invoked": False, "cleanup_confirmed": True, "exit_code": 0, "timed_out": False}
        elif scenario == "previous_completion":
            previous["inference_completion"]["exit_code"] = True
        elif scenario == "previous_receipt":
            previous["inference_completion"]["receipt"]["known_cost_usd"] = 0
        else:
            previous["recorder_accounting"]["known_cost_usd"] = 0
    elif scenario in {"previous_original_result", "previous_original_ledger"}:
        name = "step2_inference_results.json" if scenario == "previous_original_result" else Path(pilot.LEDGER).name
        ip = retained._paths(history.previous_context.cell)[2]
        api.trees[previous["binding"]["retained"]["output_commit"]][ip + "/" + name] += b"PRIVATE"
    elif scenario.startswith("previous_inference_"):
        icp, itp, _ = retained._paths(history.previous_context.cell)
        ir = previous["binding"]["retained"]["terminal_commit"]
        original = pilot._json_object(api.trees[ir][itp])
        original_claim = pilot._json_object(api.trees[original["claim_commit"]][icp])
        if scenario == "previous_inference_run":
            original_claim["binding"]["github_run"]["id"] = "36234320020"
        elif scenario == "previous_inference_source":
            original_claim["binding"]["source_sha"] = "9" * 40
        elif scenario == "previous_inference_predecessor":
            original_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "previous_inference_cleanup":
            original["completion"]["cleanup_confirmed"] = False
        else:
            original["completion"]["artifacts"]["deliverables"] = [{"sha256": "9" * 64, "size": 1}]
        encoded = retained._encoded(original_claim)
        for commit in (original["claim_commit"], original["output_commit"], ir):
            api.trees[commit][icp] = encoded
        original["claim_identity"] = pilot._identity(encoded)
        encoded = retained._encoded(original)
        api.trees[ir][itp] = encoded
        previous["binding"]["retained"]["terminal_sha256"] = pilot._identity(encoded)["sha256"]
        changed_previous = True
    elif scenario == "previous_hash":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "previous_size":
        claim["predecessor"]["size"] = True
    elif scenario == "previous_carried":
        api.writers[terminal["claim_commit"]][previous_path] = terminal["claim_commit"]
    elif scenario == "previous_carried_bytes":
        api.trees[terminal["claim_commit"]][previous_path] += b" "
    elif scenario == "previous_missing":
        api.trees[previous_revision].pop(previous_path)
    elif scenario in {"backing_run", "backing_writer", "backing_no_child", "backing_cleanup", "backing_renderer", "backing_type"}:
        changed_backing = True
        if scenario == "backing_run":
            backing["binding"]["github_run"]["id"] = "36289615942"
            backing["binding"]["approval_request_sha256"] = grading._context_approval(
                history.backing_context, backing["binding"]["github_run"])
        elif scenario == "backing_writer":
            backing["binding"]["controller_source_sha"] = "9" * 40
        elif scenario in {"backing_no_child", "backing_cleanup"}:
            backing["child"]["entry_invoked" if scenario == "backing_no_child" else "cleanup_confirmed"] = False
        elif scenario == "backing_renderer":
            backing["binding"]["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
        else:
            backing["format"] = ungraded.TERMINAL_FORMAT
    elif scenario == "backing_carried":
        api.writers[previous["claim_commit"]][backing_path] = previous["claim_commit"]
    elif scenario == "backing_missing":
        api.trees[backing_revision].pop(backing_path)
    elif scenario in {"intrinsic_bytes", "intrinsic_history", "intrinsic_carried", "intrinsic_missing"}:
        ir, ip = history.intrinsic_revision, history.intrinsic_path
        if scenario == "intrinsic_bytes":
            api.trees[ir][ip] += b" "
        elif scenario == "intrinsic_history":
            api.writers[ir][ip] = backing["claim_commit"]
        elif scenario == "intrinsic_carried":
            api.writers[backing["claim_commit"]][ip] = backing["claim_commit"]
        else:
            api.trees[ir].pop(ip)
    elif scenario in {"parent_claim_alias", "parent_terminal_alias"}:
        claim["expected_parent"] = claim["predecessor"]["revision"] = (
            terminal["claim_commit"] if scenario == "parent_claim_alias" else revision)
    elif "_alias_selected_" in scenario:
        alias = terminal["claim_commit"] if scenario.endswith("_claim") else revision
        if scenario.startswith("a1_claim_"):
            previous["claim_commit"] = alias
            for commit in (alias, previous_revision):
                api.writers[commit][pcp] = alias
            changed_previous = True
        elif scenario.startswith("a2_claim_"):
            backing["claim_commit"] = alias
            for commit in (alias, backing_revision):
                api.writers[commit][bcp] = alias
            changed_backing = True
        else:
            backing_claim["expected_parent"] = backing_claim["predecessor"]["revision"] = alias
            for commit in (alias, backing["claim_commit"]):
                api.trees[commit][history.intrinsic_path] = api.trees[history.intrinsic_revision][history.intrinsic_path]
                api.writers[commit][history.intrinsic_path] = alias
            changed_backing = True
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            current = compile_writer(request)
            if current.cell["cell_id"] == CELL:
                current.plan["order"][18:20] = [CELL, ng_reader.CELL]
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

    # Rehash complete isolated adversarial records and their carried copies.
    # Alias cases preserve local proofs so the new enclosing B1 check is tested.
    if changed_backing or scenario == "backing_claim_type":
        data = a1_reader._store_grade(api, backing_revision, backing_path, backing, backing_claim)
        if scenario == "backing_claim_type":
            backing_claim["binding"]["github_run"]["attempt"] = True
            encoded = retained._encoded(backing_claim)
            for commit in (backing["claim_commit"], backing_revision):
                api.trees[commit][bcp] = encoded
            backing["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(backing)
            api.trees[backing_revision][backing_path] = data
        for commit in (previous["claim_commit"], previous_revision, terminal["claim_commit"], revision):
            api.trees[commit][backing_path] = data
        previous_claim["predecessor"].update(pilot._identity(data))
        changed_previous = True
    if changed_previous or scenario == "previous_claim_type":
        data = a1_reader._store_grade(api, previous_revision, previous_path, previous, previous_claim)
        if scenario == "previous_claim_type":
            previous_claim["binding"]["github_run"]["attempt"] = True
            encoded = retained._encoded(previous_claim)
            for commit in (previous["claim_commit"], previous_revision):
                api.trees[commit][pcp] = encoded
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
        api.trees[terminal["claim_commit"]][cp] += b" "
    elif scenario == "claim_carried_bytes":
        api.trees[revision][cp] += b" "
    elif scenario in {"claim_type", "claim_float"}:
        claim["binding"]["github_run"]["attempt"] = True if scenario == "claim_type" else 1.0
        encoded = retained._encoded(claim)
        for commit in (terminal["claim_commit"], revision):
            api.trees[commit][cp] = encoded
        terminal["claim_identity"] = pilot._identity(encoded)
        api.trees[revision][path] = retained._encoded(terminal)

    def forbidden(*args, **kwargs):
        pytest.fail("B1 readout crossed a model, rubric, auth, no-judge projection or remote-write boundary")
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
    monkeypatch.setattr(readout, "_ungraded_projection", forbidden)
    readers, ordinary, records, handoffs, verified_ng = [], [], [], [], []
    initialize, ordinary_terminal = readout._ReadOnlyGrade.__init__, grading._grade_terminal
    record_terminal, verify_ng = ungraded.verify_terminal, readout._verified_ungraded
    predecessor, grant = readout._verify_predecessor, readout._ReadOnlyGrade.allow_verified_files
    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)
    def verify_ordinary(api, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] in {CELL, readout.TASK3_A2_CELL}
        ordinary.append(current.cell["cell_id"])
        return ordinary_terminal(api, repo, revision, current, *args, **kwargs)
    def verify_record(api, repo, revision, current, *args, **kwargs):
        assert current.cell["cell_id"] == ng_reader.CELL
        records.append(current.cell["cell_id"])
        return record_terminal(api, repo, revision, current, *args, **kwargs)
    def verified_record(api, current, *args, **kwargs):
        result = verify_ng(api, current, *args, **kwargs)
        verified_ng.append(current.cell["cell_id"])
        return result
    def verified_predecessor(api, current, *args, **kwargs):
        assert current.cell["cell_id"] == CELL
        result = predecessor(api, current, *args, **kwargs)
        handoffs.append(current.cell["cell_id"])
        return result
    def grant_selected(reader, members):
        assert reader is readers[0] and handoffs == [CELL] and verified_ng == [ng_reader.CELL]
        return grant(reader, members)
    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(grading, "_grade_terminal", verify_ordinary)
    monkeypatch.setattr(ungraded, "verify_terminal", verify_record)
    monkeypatch.setattr(readout, "_verified_ungraded", verified_record)
    monkeypatch.setattr(readout, "_verify_predecessor", verified_predecessor)
    monkeypatch.setattr(readout._ReadOnlyGrade, "allow_verified_files", grant_selected)
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
            "--terminal-revision", history.request, "--root", str(root), "--phase", phase]
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
    downloads = {(op, commit, name) for op, commit, name, _ in api.reads if op == "download"}
    selected_files = {("download", revision, item["path"]) for item in terminal["files"]}
    accepted = {*VARIANTS, "advanced", "replay", "exclusions", "redacted_text"}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        if scenario == "closed_registry":
            requests = a1_reader._unregistered_requests()
            assert len(requests) == 7 and history.request not in requests
            assert all(value[1] in requests for cell, value in {**grading.TASK4_RETAINED, **grading.TASK5_RETAINED}.items()
                       if cell not in {ng_reader.CELL, grading.TASK4_A2_CELL, grading.TASK5_A1_CELL, grading.TASK5_B1_CELL,
                                       CELL, *readout.TASK4_SUCCESSOR_READOUTS})
            assert ng_reader.CELL not in readout.TASK3_SUCCESSOR_READOUTS and CELL not in readout.TASK3_SUCCESSOR_READOUTS
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
        assert "record_kind" not in public and "inference_accounting" not in public and "recorder_accounting" not in public
        assert public["grade_revision"] == revision and public["inference_terminal"] == TERMINAL
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
                assert receipt["known_cost_usd"] > 0
            else:
                assert receipt["known_cost_usd"] is receipt["estimated_cost_usd"] is None
        else:
            assert public["ledger_derived_cost"]["estimated_cost_usd"] is None
            assert public["ledger_derived_cost"]["missing_reasons"] == ["call_reachability_unknown"]
        for receipt in (public["recorded_task_cost"], public["recorded_summary_cost"], public["ledger_derived_cost"]):
            if receipt is not None:
                assert receipt["invoice_complete"] is False and receipt["http_request_count"] is None
        assert len(readers) == 3 and handoffs == [CELL] and verified_ng == records == [ng_reader.CELL]
        assert ordinary == [CELL, readout.TASK3_A2_CELL, readout.TASK3_A2_CELL]
        head = ADVANCED if scenario == "advanced" else revision
        assert public["observed_branch_head"] == head
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        originals = {("download", previous["binding"]["retained"]["output_commit"],
            retained._paths(history.previous_context.cell)[2] + "/" + name)
            for name in ("step2_inference_results.json", Path(pilot.LEDGER).name)}
        expected_downloads = selected_files | originals | {("download", history.intrinsic_revision, history.intrinsic_path)}
        allowed_paths, metadata = {("paths", head, path)}, {("metadata", grading.BRANCH)}
        for current, value, commit in ((context, terminal, revision),
                (history.previous_context, previous, previous_revision), (history.backing_context, backing, backing_revision)):
            claim_path, terminal_path = grading._paths(current.cell)
            cr = value["claim_commit"]
            original_claim = pilot._json_object(api.trees[cr][claim_path])
            parent_cell = current.plan["cells"][current.plan["order"].index(current.cell["cell_id"]) - 1]
            pp = grading._paths(parent_cell)[1]
            expected_downloads.update({("download", commit, terminal_path), ("download", cr, claim_path)})
            allowed_paths.update(("paths", commit, member) for member in (
                terminal_path, claim_path, *(item["path"] for item in value.get("files", []))))
            allowed_paths.update({("paths", cr, claim_path), ("paths", cr, pp), ("paths", original_claim["expected_parent"], pp)})
            icp, itp, ip = retained._paths(current.cell)
            ir = value["binding"]["retained"]["terminal_commit"]
            inference = pilot._json_object(api.trees[ir][itp])
            metadata.add(("metadata", ir))
            expected_downloads.update({("download", ir, itp), ("download", inference["claim_commit"], icp),
                                      ("download", inference["output_commit"], ip + "/" + output.MANIFEST)})
            allowed_paths.update({("paths", ir, itp), ("paths", ir, icp), ("paths", inference["claim_commit"], icp)})
            for item in inference["output_objects"]:
                allowed_paths.update({("paths", ir, item["path"]), ("paths", inference["output_commit"], item["path"])})
        assert downloads == expected_downloads
        actual_paths = {("paths", commit, member) for op, commit, _, members in api.reads if op == "paths" for member in members}
        assert actual_paths <= allowed_paths and {call for call in api.calls if call[0] == "metadata"} == metadata
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        intrinsic = pilot._json_object(api.trees[history.intrinsic_revision][history.intrinsic_path])
        for reader in readers:
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            for commit, member in ((backing_revision, backing["files"][0]["path"]),
                    (history.intrinsic_revision, grading._paths(history.intrinsic_cell)[0]),
                    (history.intrinsic_revision, retained._paths(history.intrinsic_cell)[1]),
                    *((history.intrinsic_revision, item["path"]) for item in intrinsic["files"]),
                    (OUTPUT, "PRIVATE/arbitrary")):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
            for commit in (grading.BRANCH, retained.BRANCH, TERMINAL, history.previous_context.terminal_revision):
                with pytest.raises(output.OutputPublicationRefused):
                    reader.repo_info(repo_id=api.repo, repo_type="dataset", token=base.TOKEN, revision=commit, timeout=1)
        assert readers[0]._downloads.isdisjoint((commit, member) for _, commit, member in originals)
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused" and api.calls == calls
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario not in {"outcome", "raw_judge", "private_cost_reason", "denominator_type", "payload_source", "ledger_pointer"}:
            assert not downloads.intersection(selected_files)
        if "_alias_selected_" in scenario:
            assert verified_ng == [ng_reader.CELL] and not handoffs
        if scenario == "lost_response":
            assert public["http_status"] == 503
    assert all(commit != retained.BRANCH for op, commit in api.calls if op == "metadata")
    assert history.historical_path not in {name for _, _, name in downloads}
