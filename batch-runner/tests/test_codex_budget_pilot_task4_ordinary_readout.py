"""Only recorded task4 C1/C2/B2, with one genuine synthetic writer history.

C1 preserves the full B1-after-NG boundary. C2/B2 stop at their immediate
ordinary parent and its intrinsic older control. Synthetic private bytes,
revisions and scores are not live evidence or readout authorization.
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
from . import test_codex_budget_pilot_task4_b1_readout as b1_reader
from .test_codex_budget_pilot_task3_grading_chain import _Capture
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — live boundaries blocked

PREFIX = "3baa0009-5a60-4ae8-ae99-4955cb328ff3_"
WRITER, PRODUCER, OBSERVER = c_reader.WRITER, c_reader.PRODUCER, c_reader.OBSERVER
VARIANTS = c_reader.VARIANTS
RECORDED = {
    "C_r1": (20, "36294081159", "36239016015",
             "76c1904cfbed0588f5fcb6c15f48f66cd065933a8c829cbd18fcfb323f8ab710", "B_r1"),
    "C_r2": (21, "36295603145", "36242339639",
             "817d2515c4719b7f12b40c5c58e446661e2e41fd5d8023a78045208548e4dcbd", "C_r1"),
    "B_r2": (22, "36297122393", "36243795189",
             "ec4221834b04014e58775a4a4d94fc139e49ad2b7b45321e7fd2ccd58d75ef41", "C_r2"),
}


@pytest.fixture(scope="module")
def history(tmp_path_factory, *, _variants=VARIANTS):
    # Assert actual pins before substituting any synthetic completion checksum.
    expected = {}
    for suffix, (ordinal, grade_run, inference_run, request, parent) in RECORDED.items():
        cell = PREFIX + suffix
        expected[cell] = (ordinal, PREFIX + parent, {"id": grade_run, "job": "pilot-live", "attempt": 1})
        assert grading.TASK4_RETAINED[cell] == (inference_run, request)
        current = readout._writer_context(request)
        assert current.cell["cell_id"] == cell and current.controller_source_sha == WRITER
        assert current.plan["reviewed_source_sha"] == PRODUCER
        assert current.terminal_revision == "" and current.terminal_request == request
        assert current.plan["order"][ordinal - 1:ordinal + 1] == [PREFIX + parent, cell]
        assert len(current.plan["order"]) == 30 and not grading._model_free_context(current)
        assert readout._writer_run(current) == expected[cell][2]
        assert hashlib.sha256(current.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert readout.TASK4_SUCCESSOR_READOUTS == expected
    assert list(expected) == [readout.TASK4_C1_CELL, readout.TASK4_C2_CELL, readout.TASK4_B2_CELL]
    assert len({WRITER, PRODUCER, OBSERVER}) == 3
    assert readout.CONFIG_SHA256 == "62a6d99d9e74d187e517d60d9a5afb112e38926917710ac6e6606eb28404dfa0"
    assert readout.TASK3_A1_GRADER_SOURCE_HASH == "0a66e518dbe9dfe403e68aee69ec13d7f15ee7d86c6c2de7ccedfe990242e7df"
    assert readout.TASK4_A1_WRITER_RUN == ng_reader.RUN and readout.TASK4_B1_WRITER_RUN == b1_reader.RUN

    # One B1 variant, including genuine NG A1 and ordinary task3 A2 backing.
    # No previous test body or old parametrized reader family runs.
    prefix = b1_reader.history.__wrapped__(tmp_path_factory, _variants=("graded",))
    initial = next(prefix)
    directory = tmp_path_factory.mktemp("task4-ordinary-readout-history")
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    capture, shared = _Capture(), {}
    try:
        with pytest.MonkeyPatch.context() as patch:
            previous = initial.rows["graded"]
            input_parent = b1_reader.TERMINAL
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                for suffix, (ordinal, grade_run, inference_run, _, parent) in RECORDED.items():
                    local = directory / suffix
                    local.mkdir()
                    cell = PREFIX + suffix
                    ic, io, it, advanced = (f"{100_000 + ordinal * 10 + offset:040x}" for offset in (1, 2, 3, 4))
                    api = copy.deepcopy(previous.api)
                    assert not {ic, io, it, advanced}.intersection(api.trees)
                    seeded = SimpleNamespace(api=api, context=grading.compile_request("pilot/" + cell, PRODUCER, it))
                    with patch.context() as seed:
                        for key, value in {"SOURCE": PRODUCER, "CLAIM": ic, "OUTPUT": io, "TERMINAL": it}.items():
                            seed.setattr(base, key, value)
                        base._seed_outputs(seeded, local, extra_deliverable=True)
                    cp, tp, ip = retained._paths(seeded.context.cell)
                    prior_bytes = api.trees[input_parent][retained._paths(previous.context.cell)[1]]
                    prior = pilot._json_object(prior_bytes)
                    seeded.claim["binding"]["github_run"] = {"id": inference_run, "job": "cell", "attempt": 1}
                    seeded.claim["expected_parent"] = input_parent
                    seeded.claim["predecessor"] = {"cell_id": PREFIX + parent, "terminal_commit": input_parent,
                        "terminal_sha256": pilot._identity(prior_bytes)["sha256"], "output_commit": prior["output_commit"],
                        "manifest_sha256": prior["manifest_identity"]["sha256"]}
                    seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                    files = {name: data for name, data in api.trees[io].items() if name.startswith(ip + "/")}
                    api.seed(ic, input_parent, {cp: retained._encoded(seeded.claim)})
                    api.seed(io, ic, files)
                    api.seed(it, io, {tp: retained._encoded(seeded.terminal)})
                    api.branches[retained.BRANCH] = it
                    api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
                    request = pilot._digest(seeded.terminal["completion"])
                    patch.setitem(grading.TASK4_RETAINED, cell, (inference_run, request))
                    previous_claim = pilot._json_object(api.trees[previous.terminal["claim_commit"]][
                        grading._paths(previous.context.cell)[0]])
                    backing_cell = previous.context.plan["cells"][ordinal - 2]
                    assert previous_claim["predecessor"]["cell_id"] == backing_cell["cell_id"]
                    row = SimpleNamespace(rows={}, request=request, cell=cell, ordinal=ordinal,
                        input_claim=ic, input_output=io, input_terminal=it, advanced=advanced,
                        previous_context=copy.deepcopy(previous.context), previous_revision=previous.revision,
                        previous_path=previous.path, backing_cell=backing_cell,
                        backing_revision=previous_claim["expected_parent"], backing_path=grading._paths(backing_cell)[1],
                        ng_context=initial.previous_context, ng_revision=initial.previous_revision, ng_path=initial.previous_path,
                        a2_context=initial.backing_context, a2_revision=initial.backing_revision, a2_path=initial.backing_path,
                        intrinsic_cell=initial.intrinsic_cell, intrinsic_revision=initial.intrinsic_revision,
                        intrinsic_path=initial.intrinsic_path, historical_path=initial.historical_path)
                    for variant in _variants:
                        destination = local / variant
                        destination.mkdir()
                        current = SimpleNamespace(api=copy.deepcopy(api), workflow=workflow,
                            context=readout._writer_context(request), request=request, root=destination / "grade")
                        current.transport = base.Child(current)
                        current.api.calls.clear()
                        current.api.reads.clear()
                        current.api.events.clear()
                        with patch.context() as selected:
                            selected.setattr(base, "OUTPUT", io)
                            selected.setenv("HF_TOKEN", base.TOKEN)
                            base._synthetic_rubric(current, selected)
                            approval._authorize(current, destination, selected, grade_run)
                            revision, path, terminal = writer._writer(current, capture, destination, selected, variant)
                        claim = retained._read(current.root / "claim-receipt.json")["claim"]
                        assert claim["expected_parent"] == previous.revision
                        assert claim["predecessor"] == {"cell_id": PREFIX + parent, "revision": previous.revision,
                                                       **pilot._identity(retained._encoded(previous.terminal))}
                        assert terminal["binding"]["github_run"] == expected[cell][2]
                        assert terminal["binding"]["controller_source_sha"] == WRITER
                        assert terminal["format"] == grading.RESULT_FORMAT
                        assert terminal["child"]["entry_invoked"] is terminal["child"]["cleanup_confirmed"] is True
                        assert current.transport.calls == 1 and current.api.events == ["grade_claim", "judge", "grade_output"]
                        assert all(current.api.trees[rev] == data for rev, data in api.trees.items())
                        row.rows[variant] = SimpleNamespace(api=current.api, context=current.context,
                            revision=revision, path=path, terminal=terminal)
                    shared[suffix] = row
                    previous, input_parent = row.rows["graded"], it
            yield shared
    finally:
        prefix.close()


COMMON = (*c_reader.SCENARIOS, "claim_type", "claim_float", "claim_carried_bytes", "host_ref",
    "previous_claim_type", "previous_record_type", "previous_identity_float", "parent_entry_type",
    "whole_inference_observation", "parent_claim_alias_selected_claim", "parent_claim_alias_selected_terminal",
    "older_control_alias_selected_claim", "older_control_alias_selected_terminal")
C1_ONLY = ("ng_policy", "ng_run", "ng_source", "ng_writer", "ng_approval", "ng_cell", "ng_type", "ng_score",
    "ng_child", "ng_completion", "ng_receipt", "ng_recorder", "ng_claim_type", "ng_result", "ng_ledger",
    "ng_inference_run", "ng_inference_predecessor", "ng_inference_cleanup", "ng_inference_deliverables",
    "a2_run", "a2_writer", "a2_renderer", "a2_no_child", "a2_cleanup", "a2_type", "a2_claim_type",
    "a2_carried", "a2_missing", "intrinsic_bytes", "intrinsic_history", "intrinsic_carried", "intrinsic_missing",
    "ng_claim_alias_selected_claim", "ng_claim_alias_selected_terminal", "a2_claim_alias_selected_claim",
    "a2_claim_alias_selected_terminal", "intrinsic_alias_selected_claim", "intrinsic_alias_selected_terminal")
CASES = [(suffix, scenario) for suffix in RECORDED for scenario in COMMON]
CASES.extend(("C_r1", scenario) for scenario in C1_ONLY)


@pytest.mark.parametrize("suffix,scenario", CASES, ids=[f"{suffix}-{scenario}" for suffix, scenario in CASES])
def test_fixed_task4_ordinary_readouts(history, tmp_path, monkeypatch, capsys, suffix, scenario):
    selected, recorded = history[suffix], RECORDED[suffix]
    deep = suffix == "C_r1"
    row = selected.rows.get(scenario, selected.rows["graded"])
    api, terminal = copy.deepcopy(row.api), copy.deepcopy(row.terminal)
    context, revision, path = copy.deepcopy(row.context), row.revision, row.path
    cp = grading._paths(context.cell)[0]
    claim = pilot._json_object(api.trees[terminal["claim_commit"]][cp])
    pr, pp = selected.previous_revision, selected.previous_path
    previous = pilot._json_object(api.trees[pr][pp])
    pcp = grading._paths(selected.previous_context.cell)[0]
    previous_claim = pilot._json_object(api.trees[previous["claim_commit"]][pcp])
    record = next((item for item in terminal["files"] if item["role"] == "grade_result"), None)
    run = {"id": recorded[1], "job": "pilot-live", "attempt": 1}
    changed_previous = False
    if deep:
        ng = pilot._json_object(api.trees[selected.ng_revision][selected.ng_path])
        ncp = grading._paths(selected.ng_context.cell)[0]
        ng_claim = pilot._json_object(api.trees[ng["claim_commit"]][ncp])
        a2 = pilot._json_object(api.trees[selected.a2_revision][selected.a2_path])
        acp = grading._paths(selected.a2_context.cell)[0]
        a2_claim = pilot._json_object(api.trees[a2["claim_commit"]][acp])
        changed_ng = changed_a2 = False

    if scenario == "advanced":
        api.seed(selected.advanced, revision, {"unrelated/PRIVATE": b"PRIVATE unrelated later write"})
        api.branches[grading.BRANCH] = api.branches[retained.BRANCH] = selected.advanced
    elif scenario in {"writer", "producer", "grader_hash", "config_hash", "grader_config", "approval"}:
        key = {"writer": "controller_source_sha", "producer": "source_sha", "grader_hash": "grader_source_hash",
               "config_hash": "config_hash", "grader_config": "grader_config_sha256", "approval": "approval_request_sha256"}[scenario]
        terminal["binding"][key] = "PRIVATE"
    elif scenario in {"run", "job", "attempt", "typed_attempt"}:
        key, value = {"run": ("id", str(int(run["id"]) + 1)), "job": ("job", "grade"),
                      "attempt": ("attempt", 2), "typed_attempt": ("attempt", True)}[scenario]
        terminal["binding"]["github_run"][key] = value
        terminal["binding"]["approval_request_sha256"] = grading._context_approval(context, terminal["binding"]["github_run"])
    elif scenario == "renderer":
        terminal["binding"]["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
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
    elif scenario in {"cleanup", "no_child"}:
        terminal["child"]["cleanup_confirmed" if scenario == "cleanup" else "entry_invoked"] = False
    elif scenario == "outcome":
        terminal["outcome"] = "failed"
    elif scenario == "record_type":
        terminal["format"] = ungraded.TERMINAL_FORMAT
    elif scenario == "claim_format":
        claim["format"] = ungraded.CLAIM_FORMAT
    elif scenario == "claim_extra":
        claim["extra"] = "PRIVATE"
    elif scenario in {"claim_history", "terminal_history", "artifact_history"}:
        member, last = {"claim_history": (cp, revision), "terminal_history": (path, terminal["claim_commit"]),
                        "artifact_history": (record["path"], terminal["claim_commit"])}[scenario]
        api.writers[revision][member] = last
    elif scenario.startswith("inference_") and scenario != "inference_ref":
        icp, itp, ip = retained._paths(context.cell)
        original = pilot._json_object(api.trees[selected.input_terminal][itp])
        original_claim = pilot._json_object(api.trees[selected.input_claim][icp])
        if scenario == "inference_completion":
            original["completion"]["child_invocations"] = 2
        elif scenario == "inference_run":
            original_claim["binding"]["github_run"]["id"] = str(int(recorded[2]) + 1)
        elif scenario in {"inference_source", "inference_config"}:
            original_claim["binding"]["source_sha" if scenario == "inference_source" else "config_sha256"] = "9" * 64
        elif scenario == "inference_predecessor":
            original_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "inference_parent":
            original_claim["expected_parent"] = "9" * 40
        elif scenario == "inference_history":
            api.writers[selected.input_terminal][icp] = selected.input_terminal
        elif scenario == "inference_bytes":
            api.trees[selected.input_output][ip + "/" + output.MANIFEST] += b"PRIVATE"
        else:
            original["publication_receipt_sha256"] = "9" * 64
        data = retained._encoded(original_claim)
        for commit in (selected.input_claim, selected.input_output, selected.input_terminal):
            api.trees[commit][icp] = data
        original["claim_identity"] = pilot._identity(data)
        data = retained._encoded(original)
        api.trees[selected.input_terminal][itp] = data
        terminal["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
    elif scenario in {"previous_run", "previous_writer", "previous_source", "previous_grader_hash", "previous_config",
                      "previous_renderer", "previous_cleanup", "previous_no_child", "previous_receipt", "previous_inference",
                      "previous_handoff", "previous_record_type"}:
        changed_previous = True
        if scenario == "previous_run":
            previous["binding"]["github_run"]["id"] = str(int(previous["binding"]["github_run"]["id"]) + 1)
            previous["binding"]["approval_request_sha256"] = grading._context_approval(
                selected.previous_context, previous["binding"]["github_run"])
        elif scenario in {"previous_writer", "previous_source", "previous_grader_hash", "previous_config"}:
            key = {"previous_writer": "controller_source_sha", "previous_source": "source_sha",
                   "previous_grader_hash": "grader_source_hash", "previous_config": "config_hash"}[scenario]
            previous["binding"][key] = "PRIVATE"
        elif scenario == "previous_renderer":
            previous["binding"]["renderer_fingerprint"]["pymupdf_version"] = "PRIVATE"
        elif scenario in {"previous_cleanup", "previous_no_child"}:
            previous["child"]["cleanup_confirmed" if scenario == "previous_cleanup" else "entry_invoked"] = False
        elif scenario == "previous_receipt":
            previous["binding"]["publication_receipt_sha256"] = "9" * 64
        elif scenario == "previous_handoff":
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = "9" * 40
        elif scenario == "previous_record_type":
            previous["format"] = ungraded.TERMINAL_FORMAT
        else:
            previous["binding"]["retained"]["terminal_commit"] = "9" * 40
    elif scenario in {"previous_grade", "parent_claim_alias", "parent_terminal_alias"}:
        parent = {"previous_grade": "9" * 40, "parent_claim_alias": terminal["claim_commit"],
                  "parent_terminal_alias": revision}[scenario]
        claim["expected_parent"] = claim["predecessor"]["revision"] = parent
    elif scenario == "previous_hash":
        claim["predecessor"]["sha256"] = "9" * 64
    elif scenario == "previous_carried":
        api.writers[terminal["claim_commit"]][pp] = terminal["claim_commit"]
    elif scenario == "previous_carried_bytes":
        api.trees[terminal["claim_commit"]][pp] += b" "
    elif scenario == "previous_cell":
        claim["predecessor"]["cell_id"] = grading.TASK3_A1_CELL
    elif scenario in {"previous_size", "previous_identity_float"}:
        claim["predecessor"]["size"] = True if scenario == "previous_size" else float(claim["predecessor"]["size"])
    elif scenario == "previous_type":
        claim["predecessor"] = []
    elif scenario == "previous_absent":
        api.trees[pr].pop(pp)
    elif scenario == "previous_claim":
        api.trees[previous["claim_commit"]][pcp] += b" "
    elif scenario.startswith("backing_"):
        br, bp = selected.backing_revision, selected.backing_path
        if scenario == "backing_missing":
            api.trees[br].pop(bp)
        elif scenario == "backing_bytes":
            api.trees[br][bp] += b" "
        elif scenario == "backing_history":
            api.writers[br][bp] = previous["claim_commit"]
        elif scenario == "backing_carried":
            api.writers[previous["claim_commit"]][bp] = previous["claim_commit"]
        elif scenario == "backing_carried_bytes":
            api.trees[previous["claim_commit"]][bp] += b" "
        else:
            changed_previous = True
            if scenario == "backing_hash":
                previous_claim["predecessor"]["sha256"] = "9" * 64
            elif scenario == "backing_cell":
                previous_claim["predecessor"]["cell_id"] = selected.cell
            elif scenario == "backing_size":
                previous_claim["predecessor"]["size"] = True
            else:
                parent = previous["claim_commit"] if scenario == "backing_claim_alias" else pr
                previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = parent
    elif scenario in {"ng_policy", "ng_run", "ng_source", "ng_writer", "ng_approval", "ng_cell", "ng_type", "ng_score",
                      "ng_child", "ng_completion", "ng_receipt", "ng_recorder"}:
        changed_ng = True
        if scenario in {"ng_policy", "ng_source", "ng_writer", "ng_approval", "ng_cell"}:
            key = {"ng_policy": "policy", "ng_source": "source_sha", "ng_writer": "controller_source_sha",
                   "ng_approval": "approval_request_sha256", "ng_cell": "cell_id"}[scenario]
            ng["binding"][key] = "PRIVATE"
        elif scenario == "ng_run":
            ng["binding"]["github_run"]["id"] = "36291118507"
            ng["binding"]["approval_request_sha256"] = grading._context_approval(selected.ng_context, ng["binding"]["github_run"])
        elif scenario == "ng_type":
            ng["format"] = grading.RESULT_FORMAT
        elif scenario == "ng_score":
            ng["score"] = 0
        elif scenario == "ng_child":
            ng["child"] = {"entry_invoked": False, "cleanup_confirmed": True, "exit_code": 0, "timed_out": False}
        elif scenario == "ng_completion":
            ng["inference_completion"]["exit_code"] = True
        elif scenario == "ng_receipt":
            ng["inference_completion"]["receipt"]["known_cost_usd"] = 0
        else:
            ng["recorder_accounting"]["known_cost_usd"] = 0
    elif scenario in {"ng_result", "ng_ledger"}:
        name = "step2_inference_results.json" if scenario == "ng_result" else Path(pilot.LEDGER).name
        ip = retained._paths(selected.ng_context.cell)[2]
        api.trees[ng["binding"]["retained"]["output_commit"]][ip + "/" + name] += b"PRIVATE"
    elif scenario.startswith("ng_inference_"):
        icp, itp, _ = retained._paths(selected.ng_context.cell)
        ir = ng["binding"]["retained"]["terminal_commit"]
        original = pilot._json_object(api.trees[ir][itp])
        original_claim = pilot._json_object(api.trees[original["claim_commit"]][icp])
        if scenario == "ng_inference_run":
            original_claim["binding"]["github_run"]["id"] = "36234320020"
        elif scenario == "ng_inference_predecessor":
            original_claim["predecessor"]["manifest_sha256"] = "9" * 64
        elif scenario == "ng_inference_cleanup":
            original["completion"]["cleanup_confirmed"] = False
        else:
            original["completion"]["artifacts"]["deliverables"] = [{"sha256": "9" * 64, "size": 1}]
        data = retained._encoded(original_claim)
        for commit in (original["claim_commit"], original["output_commit"], ir):
            api.trees[commit][icp] = data
        original["claim_identity"] = pilot._identity(data)
        data = retained._encoded(original)
        api.trees[ir][itp] = data
        ng["binding"]["retained"]["terminal_sha256"] = pilot._identity(data)["sha256"]
        changed_ng = True
    elif scenario in {"a2_run", "a2_writer", "a2_renderer", "a2_no_child", "a2_cleanup", "a2_type"}:
        changed_a2 = True
        if scenario == "a2_run":
            a2["binding"]["github_run"]["id"] = "36289615942"
            a2["binding"]["approval_request_sha256"] = grading._context_approval(selected.a2_context, a2["binding"]["github_run"])
        elif scenario == "a2_writer":
            a2["binding"]["controller_source_sha"] = "9" * 40
        elif scenario == "a2_renderer":
            a2["binding"]["renderer_fingerprint"]["libreoffice_version"] = "PRIVATE"
        elif scenario in {"a2_no_child", "a2_cleanup"}:
            a2["child"]["entry_invoked" if scenario == "a2_no_child" else "cleanup_confirmed"] = False
        else:
            a2["format"] = ungraded.TERMINAL_FORMAT
    elif scenario == "a2_carried":
        api.writers[ng["claim_commit"]][selected.a2_path] = ng["claim_commit"]
    elif scenario == "a2_missing":
        api.trees[selected.a2_revision].pop(selected.a2_path)
    elif scenario in {"intrinsic_bytes", "intrinsic_history", "intrinsic_carried", "intrinsic_missing"}:
        ir, ip = selected.intrinsic_revision, selected.intrinsic_path
        if scenario == "intrinsic_bytes":
            api.trees[ir][ip] += b" "
        elif scenario == "intrinsic_history":
            api.writers[ir][ip] = a2["claim_commit"]
        elif scenario == "intrinsic_carried":
            api.writers[a2["claim_commit"]][ip] = a2["claim_commit"]
        else:
            api.trees[ir].pop(ip)
    elif "_alias_selected_" in scenario:
        alias = terminal["claim_commit"] if scenario.endswith("_claim") else revision
        if scenario.startswith("parent_claim_"):
            previous["claim_commit"] = alias
            for commit in (alias, pr):
                api.writers[commit][pcp] = alias
            changed_previous = True
        elif scenario.startswith("older_control_"):
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = alias
            for commit in (alias, previous["claim_commit"]):
                api.trees[commit][selected.backing_path] = api.trees[selected.backing_revision][selected.backing_path]
                api.writers[commit][selected.backing_path] = alias
            changed_previous = True
        elif scenario.startswith("ng_claim_"):
            ng["claim_commit"] = alias
            for commit in (alias, selected.ng_revision):
                api.writers[commit][ncp] = alias
            changed_ng = True
        elif scenario.startswith("a2_claim_"):
            a2["claim_commit"] = alias
            for commit in (alias, selected.a2_revision):
                api.writers[commit][acp] = alias
            changed_a2 = True
        else:
            a2_claim["expected_parent"] = a2_claim["predecessor"]["revision"] = alias
            for commit in (alias, a2["claim_commit"]):
                api.trees[commit][selected.intrinsic_path] = api.trees[selected.intrinsic_revision][selected.intrinsic_path]
                api.writers[commit][selected.intrinsic_path] = alias
            changed_a2 = True
    elif scenario == "ordinal":
        compile_writer = readout._writer_context
        def wrong_order(request):
            current = compile_writer(request)
            if current.cell["cell_id"] == selected.cell:
                current.plan["order"][selected.ordinal - 1:selected.ordinal + 1] = [selected.cell, PREFIX + recorded[4]]
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

    # Rebind every enclosing grade's exact identity and carried bytes. In C1
    # cases invalid NG semantics must survive B1's intrinsic hash/history check.
    if deep and (changed_a2 or scenario == "a2_claim_type"):
        data = a1_reader._store_grade(api, selected.a2_revision, selected.a2_path, a2, a2_claim)
        if scenario == "a2_claim_type":
            a2_claim["binding"]["github_run"]["attempt"] = True
            encoded = retained._encoded(a2_claim)
            for commit in (a2["claim_commit"], selected.a2_revision):
                api.trees[commit][acp] = encoded
            a2["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(a2)
            api.trees[selected.a2_revision][selected.a2_path] = data
        for commit in (ng["claim_commit"], selected.ng_revision, previous["claim_commit"], pr, terminal["claim_commit"], revision):
            api.trees[commit][selected.a2_path] = data
        ng_claim["predecessor"].update(pilot._identity(data))
        changed_ng = True
    if deep and (changed_ng or scenario == "ng_claim_type"):
        data = a1_reader._store_grade(api, selected.ng_revision, selected.ng_path, ng, ng_claim)
        if scenario == "ng_claim_type":
            ng_claim["binding"]["github_run"]["attempt"] = True
            encoded = retained._encoded(ng_claim)
            for commit in (ng["claim_commit"], selected.ng_revision):
                api.trees[commit][ncp] = encoded
            ng["claim_identity"] = pilot._identity(encoded)
            data = retained._encoded(ng)
            api.trees[selected.ng_revision][selected.ng_path] = data
        for commit in (previous["claim_commit"], pr, terminal["claim_commit"], revision):
            api.trees[commit][selected.ng_path] = data
        previous_claim["predecessor"].update(pilot._identity(data))
        changed_previous = True
    if changed_previous or scenario == "previous_claim_type":
        data = a1_reader._store_grade(api, pr, pp, previous, previous_claim)
        if scenario == "previous_claim_type":
            previous_claim["binding"]["github_run"]["attempt"] = True
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
    elif scenario == "absent":
        api.trees[revision].pop(path)
    elif scenario == "unfinished":
        api.branches[grading.BRANCH] = terminal["claim_commit"]

    def forbidden(*args, **kwargs):
        pytest.fail("Task4 tail crossed a model, rubric, auth, NG projection, history or remote-write boundary")
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
    readers, ordinary, records, handoffs, completed, ng_done = [], [], [], [], [], []
    initialize, native_grade = readout._ReadOnlyGrade.__init__, grading._grade_terminal
    native_ng, verify_ng = ungraded.verify_terminal, readout._verified_ungraded
    predecessor, grant = readout._verify_predecessor, readout._ReadOnlyGrade.allow_verified_files
    verified_grade = readout._verified_grade
    expected_handoffs = [selected.cell, b1_reader.CELL] if deep else [selected.cell]
    expected_ordinary = ([selected.cell, b1_reader.CELL, readout.TASK3_A2_CELL, readout.TASK3_A2_CELL]
                         if deep else [selected.cell, selected.previous_context.cell["cell_id"]])
    def remember(reader, *args, **kwargs):
        initialize(reader, *args, **kwargs)
        readers.append(reader)
    def ordinary_only(api, repo, commit, current, *args, **kwargs):
        assert current.cell["cell_id"] in expected_ordinary
        ordinary.append(current.cell["cell_id"])
        return native_grade(api, repo, commit, current, *args, **kwargs)
    def record_only(api, repo, commit, current, *args, **kwargs):
        assert deep and current.cell["cell_id"] == ng_reader.CELL
        records.append(current.cell["cell_id"])
        return native_ng(api, repo, commit, current, *args, **kwargs)
    def ng_only(api, current, *args, **kwargs):
        assert deep and current.cell["cell_id"] == ng_reader.CELL
        result = verify_ng(api, current, *args, **kwargs)
        ng_done.append(current.cell["cell_id"])
        return result
    def bounded_predecessor(api, current, *args, **kwargs):
        assert current.cell["cell_id"] == expected_handoffs[len(handoffs)]
        handoffs.append(current.cell["cell_id"])
        result = predecessor(api, current, *args, **kwargs)
        completed.append(current.cell["cell_id"])
        return result
    def typed_observations(api, current, *args, **kwargs):
        value, entry, observed = verified_grade(api, current, *args, **kwargs)
        # Isolate the outer canonical comparison after genuine native proof.
        if scenario == "parent_entry_type" and current.cell["cell_id"] == selected.previous_context.cell["cell_id"]:
            entry = {**entry, "extra": True}
        if scenario == "whole_inference_observation" and current.cell["cell_id"] == selected.cell:
            observed = {**observed, "extra": True}
        return value, entry, observed
    def grant_selected(reader, members):
        assert reader is readers[0] and completed == list(reversed(expected_handoffs))
        assert ordinary == expected_ordinary and ng_done == ([ng_reader.CELL] if deep else [])
        return grant(reader, members)
    monkeypatch.setattr(readout._ReadOnlyGrade, "__init__", remember)
    monkeypatch.setattr(grading, "_grade_terminal", ordinary_only)
    monkeypatch.setattr(ungraded, "verify_terminal", record_only)
    monkeypatch.setattr(readout, "_verified_ungraded", ng_only)
    monkeypatch.setattr(readout, "_verify_predecessor", bounded_predecessor)
    monkeypatch.setattr(readout, "_verified_grade", typed_observations)
    monkeypatch.setattr(readout._ReadOnlyGrade, "allow_verified_files", grant_selected)
    source = WRITER if scenario == "observer_writer" else PRODUCER if scenario == "observer_producer" else OBSERVER
    for key, value in {"GITHUB_SHA": source, "PILOT_WORKFLOW_SHA": source, "GITHUB_JOB": "pilot-readout",
        "GITHUB_RUN_ID": "900043", "PILOT_GRADE_PAID_APPROVAL": "false", "HF_TOKEN": base.TOKEN}.items():
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
            "--terminal-revision", selected.request, "--root", str(root), "--phase", phase]
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
    assert public["cell_id"] == selected.cell and public["grade_writer_run"] == run
    assert public["grade_writer_source_sha"] == WRITER and public["inference_producer_source_sha"] == PRODUCER
    downloads = {(op, commit, name) for op, commit, name, _ in api.reads if op == "download"}
    selected_files = {("download", revision, item["path"]) for item in terminal["files"]}
    accepted = {*VARIANTS, "advanced", "replay", "exclusions", "redacted_text"}
    if scenario in {"plan", "closed_registry"}:
        assert code == 0 and public["outcome"] == "plan_only" and not api.calls and not root.exists()
        assert public["inference_terminal"] is None and public["observer_source_sha"] == OBSERVER
        if scenario == "closed_registry":
            requests = a1_reader._unregistered_requests()
            assert len(requests) == 7 and selected.request not in requests
            assert list(readout.TASK4_SUCCESSOR_READOUTS) == [PREFIX + name for name in RECORDED]
            assert all(grading.TASK4_RETAINED[PREFIX + name][1] not in requests for name in RECORDED)
            assert grading.TASK4_RETAINED[PREFIX + "A_r2"][1] not in requests
            assert all(record[1] in requests for cell, record in grading.TASK5_RETAINED.items()
                       if cell not in {grading.TASK5_A1_CELL, grading.TASK5_B1_CELL})
            assert all(value[1] in requests for cell, value in grading.TASK5_RETAINED.items()
                       if cell not in {grading.TASK5_A1_CELL, grading.TASK5_B1_CELL})
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
        assert not {"record_kind", "inference_accounting", "recorder_accounting"}.intersection(public)
        assert public["grade_revision"] == revision and public["inference_terminal"] == selected.input_terminal
        assert public["inference_request_checksum"] == selected.request and public["observer_source_sha"] == OBSERVER
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
        assert len(readers) == (4 if deep else 2) and handoffs == expected_handoffs
        assert completed == list(reversed(expected_handoffs)) and ordinary == expected_ordinary
        assert ng_done == records == ([ng_reader.CELL] if deep else [])
        head = selected.advanced if scenario == "advanced" else revision
        assert public["observed_branch_head"] == head
        assert sum(call == ("metadata", grading.BRANCH) for call in api.calls) == 1
        terminal_only = (selected.intrinsic_revision, selected.intrinsic_path, selected.intrinsic_cell) if deep else (
            selected.backing_revision, selected.backing_path, selected.backing_cell)
        tr, tp, tc = terminal_only
        expected_downloads = selected_files | {("download", tr, tp)}
        allowed_paths, metadata = {("paths", head, path)}, {("metadata", grading.BRANCH)}
        semantic = [(context, terminal, revision), (selected.previous_context, previous, pr)]
        originals = set()
        if deep:
            assert ng["format"] == ungraded.TERMINAL_FORMAT and ng["binding"]["policy"] == ungraded.POLICY
            assert ng["outcome"] == "ungraded" and ng["model_invoked"] is False
            assert not {"score", "child", "files", "verdict"}.intersection(ng)
            assert ng["inference_completion"]["status"] == "failed"
            assert ng["recorder_accounting"]["known_cost_usd"] is None
            semantic.extend([(selected.ng_context, ng, selected.ng_revision), (selected.a2_context, a2, selected.a2_revision)])
            originals = {("download", ng["binding"]["retained"]["output_commit"],
                retained._paths(selected.ng_context.cell)[2] + "/" + name)
                for name in ("step2_inference_results.json", Path(pilot.LEDGER).name)}
            expected_downloads.update(originals)
        distinct_grade_revisions = {tr}
        for current, value, commit in semantic:
            gcp, gtp = grading._paths(current.cell)
            cr = value["claim_commit"]
            distinct_grade_revisions.update({commit, cr})
            original_claim = pilot._json_object(api.trees[cr][gcp])
            parent_cell = current.plan["cells"][current.plan["order"].index(current.cell["cell_id"]) - 1]
            gpp = grading._paths(parent_cell)[1]
            expected_downloads.update({("download", commit, gtp), ("download", cr, gcp)})
            allowed_paths.update(("paths", commit, member) for member in (
                gtp, gcp, *(item["path"] for item in value.get("files", []))))
            allowed_paths.update({("paths", cr, gcp), ("paths", cr, gpp), ("paths", original_claim["expected_parent"], gpp)})
            icp, itp, ip = retained._paths(current.cell)
            ir = value["binding"]["retained"]["terminal_commit"]
            inference = pilot._json_object(api.trees[ir][itp])
            metadata.add(("metadata", ir))
            expected_downloads.update({("download", ir, itp), ("download", inference["claim_commit"], icp),
                                      ("download", inference["output_commit"], ip + "/" + output.MANIFEST)})
            allowed_paths.update({("paths", ir, itp), ("paths", ir, icp), ("paths", inference["claim_commit"], icp)})
            for item in inference["output_objects"]:
                allowed_paths.update({("paths", ir, item["path"]), ("paths", inference["output_commit"], item["path"])})
        assert len(distinct_grade_revisions) == (9 if deep else 5)
        assert downloads == expected_downloads and len(downloads) == (23 if deep else 11) + len(selected_files)
        actual_paths = {("paths", commit, member) for op, commit, _, members in api.reads if op == "paths" for member in members}
        assert actual_paths <= allowed_paths and {call for call in api.calls if call[0] == "metadata"} == metadata
        assert all(op in {"metadata", "paths", "download"} for op, *_ in api.reads)
        older = pilot._json_object(api.trees[tr][tp])
        forbidden_files = [(commit, item["path"]) for _, value, commit in semantic[1:] for item in value.get("files", [])]
        forbidden_files.extend([(tr, grading._paths(tc)[0]), (tr, retained._paths(tc)[1]),
                                *((tr, item["path"]) for item in older.get("files", [])), (selected.input_output, "PRIVATE/arbitrary")])
        for reader in readers:
            assert not hasattr(reader, "create_commit") and not hasattr(reader, "create_branch")
            for commit, member in forbidden_files:
                with pytest.raises(output.OutputPublicationRefused):
                    reader.hf_hub_download(repo_id=api.repo, repo_type="dataset", token=base.TOKEN,
                        revision=commit, filename=member, cache_dir=tmp_path,
                        force_download=True, local_files_only=False, etag_timeout=1)
        assert readers[0]._downloads.isdisjoint((commit, member) for _, commit, member in originals)
        if deep:
            assert readers[1]._downloads.isdisjoint((commit, member) for _, commit, member in originals)
        if scenario == "replay":
            calls = list(api.calls)
            assert grading.main(args, _test_api=api, _test_transport=transport) == 2
            repeated = capsys.readouterr()
            assert not repeated.out and json.loads(repeated.err)["outcome"] == "refused" and api.calls == calls
    else:
        assert code == 2 and public["outcome"] == "refused" and "score" not in public, public
        if scenario not in {"outcome", "raw_judge", "private_cost_reason", "denominator_type", "payload_source", "ledger_pointer"}:
            assert not downloads.intersection(selected_files)
        if scenario in C1_ONLY:
            assert handoffs == [selected.cell, b1_reader.CELL]
        if scenario.startswith(("ng_claim_alias_", "a2_claim_alias_", "intrinsic_alias_")):
            assert ng_done == [ng_reader.CELL] and completed == [b1_reader.CELL]
        if scenario.startswith(("parent_claim_alias_selected_", "older_control_alias_selected_")):
            assert ordinary == expected_ordinary
            assert completed == ([b1_reader.CELL] if deep else [])
            assert ng_done == ([ng_reader.CELL] if deep else [])
        if scenario == "lost_response":
            assert public["http_status"] == 503
    assert all(commit != retained.BRANCH for op, commit in api.calls if op == "metadata")
    assert selected.historical_path not in {member for _, _, member in downloads}
