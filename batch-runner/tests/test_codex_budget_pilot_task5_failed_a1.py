"""One fixed consecutive no-judge boundary; no live result reconstruction.

Reuse the genuine task4 history once, then the native-error, receipt,
materialization and model-free writers for task5 A1. Only the native turn and
external boundaries are fake. Every mutation gets an isolated history copy.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import json
import shutil
from types import SimpleNamespace

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
import codex_budget_pilot_ungraded as ungraded
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as approval
from . import test_codex_budget_pilot_task3_grading_chain as chain
from . import test_codex_budget_pilot_task4_failed_grading as failed
from . import test_codex_budget_pilot_task4_failed_a2 as a2
from . import test_codex_budget_pilot_task4_successor_grading as successors
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_A_r1"
RECORDED = ("36247236594", "b23da4f1f5e81999039c473d27f3a70cc0d0681672ad08be0f9674b618915c97")


def _select(history, api, directory, patch, *, controller=failed.FUTURE_CONTROLLER):
    context = grading.compile_request("pilot/" + CELL, controller, grading.TASK5_RETAINED[CELL][1],
                                      producer_source_sha=failed.PRODUCER)
    current = SimpleNamespace(api=api, context=context, workflow=history.workflow,
        root=directory / "private-grade", request=context.requested_terminal, inference=history.task5_inference)
    current.transport = policy._SourceOnlyChild(current)
    patch.setattr(base, "OUTPUT", current.inference.output)
    patch.setenv("HF_TOKEN", base.TOKEN)
    base._synthetic_rubric(current, patch)
    approval._authorize(current, directory, patch, "991024")  # Synthetic, not an issued grading run.
    return current


def _no_judge(patch, current):
    def forbidden(*args, **kwargs):
        raise AssertionError("model-free task5 A1 reached a judge or rubric entry")
    patch.setattr(grading, "_entry_contract", forbidden)
    patch.setattr(grading, "_stage_rubric", forbidden)
    patch.setattr(current.transport, "process", forbidden)


def _store_record(api, cell, revision, terminal, claim):
    """Keep a synthetic mutation's claim identity coherent; no production bypass."""
    claim_path, terminal_path = grading._paths(cell)
    data = retained._encoded(claim)
    api.trees[terminal["claim_commit"]][claim_path] = api.trees[revision][claim_path] = data
    terminal["claim_identity"] = pilot._identity(data)
    api.trees[revision][terminal_path] = retained._encoded(terminal)


@pytest.fixture(scope="module")
def task5_history(tmp_path_factory):
    assert grading.TASK5_A1_CELL == CELL and grading.TASK5_RETAINED[CELL] == RECORDED
    assert list(grading.TASK5_RETAINED) == [CELL, grading.TASK5_B1_CELL, grading.TASK5_C1_CELL]
    prototype = grading.compile_request("pilot/" + CELL, failed.PRODUCER, "8" * 40)
    error_row, ledger = failed._failed_row(prototype)
    histories = a2.failed_a2_history.__wrapped__(tmp_path_factory)
    history = next(histories)  # Reuse writers, never invoke the prior test selectors.
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("task5-failed-a1-history")
            capture, api = chain._Capture(), copy.deepcopy(history.after_a2)
            previous = history.inferences["A_r2"]
            claim_revision, output_revision, terminal_revision = (f"{100_240 + i:040x}" for i in (1, 2, 3))
            assert not {claim_revision, output_revision, terminal_revision}.intersection(api.trees)
            context = grading.compile_request("pilot/" + CELL, failed.PRODUCER, terminal_revision)
            seeded = SimpleNamespace(context=context, api=api)
            with patch.context() as seed:
                for key, value in {"SOURCE": failed.PRODUCER, "CLAIM": claim_revision,
                                   "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                    seed.setattr(base, key, value)
                base._seed_outputs(seeded, directory, failed=True, producer_row=error_row, producer_ledger=ledger,
                                   producer_receipt=error_row["problem_solving_cost"], reason="child_nonzero_exit")
            claim_path, terminal_path, prefix = retained._paths(context.cell)
            seeded.claim["binding"]["github_run"] = {"id": RECORDED[0], "job": "cell", "attempt": 1}
            seeded.claim["expected_parent"] = previous.terminal
            seeded.claim["predecessor"] = previous.evidence["observation"]
            seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
            files = {name: data for name, data in api.trees[output_revision].items() if name.startswith(prefix + "/")}
            api.seed(claim_revision, previous.terminal, {claim_path: retained._encoded(seeded.claim)})
            api.seed(output_revision, claim_revision, files)
            api.seed(terminal_revision, output_revision, {terminal_path: retained._encoded(seeded.terminal)})
            patch.setenv("HF_TOKEN", base.TOKEN)
            with retained._session(api) as (client, token, deadline):
                evidence = grading._retained_input(context, client, api.repo,
                    grading._cache(directory, "inference"), token, deadline)
            digest = pilot._digest(evidence["terminal"]["completion"])
            assert digest != RECORDED[1]  # Synthetic bytes are not the supplied live completion.
            patch.setitem(grading.TASK5_RETAINED, CELL, (RECORDED[0], digest))
            history.task5_inference = SimpleNamespace(context=context, claim=claim_revision,
                output=output_revision, terminal=terminal_revision, claim_path=claim_path,
                terminal_path=terminal_path, evidence=evidence)
            api.branches[retained.BRANCH] = terminal_revision
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            history.before_task5 = copy.deepcopy(api)
            current = _select(history, api, directory, patch)
            api.calls.clear()
            api.events.clear()
            frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
            with patch.context() as no_judge, redirect_stdout(capture.out), redirect_stderr(capture.err):
                _no_judge(no_judge, current)
                code, observed = successors._invoke(current, capture, "prepare")
                assert code == 0 and observed["model_free_record_ready"] is True, (observed, current.diagnostic)
                assert observed["judge_ready"] is False and observed["grade_success"] is False
                history.task5_prepared = retained._read(current.root / "prepared.json")
                history.task5_prepared_root = directory / "prepared-task5-a1"
                shutil.copytree(current.root, history.task5_prepared_root)
                code, observed = successors._invoke(current, capture, "record-ungraded")
                assert code == 0 and observed["grading_state"] == "ungraded", (observed, current.diagnostic)
            assert api.events == ["grade_claim", "grade_output"] and current.transport.calls == 0
            successors._unchanged(api, frozen)
            history.task5_revision = api.branches[grading.BRANCH]
            history.task5_path = grading._paths(context.cell)[1]
            history.task5_terminal = pilot._json_object(api.trees[history.task5_revision][history.task5_path])
            history.task5_admission = retained._read(current.root / "model-free-claim-receipt.json")
            history.task5_root, history.after_task5 = current.root, copy.deepcopy(api)
            yield history
    finally:
        histories.close()


CASES = [
    "chain", "plan_workflow", "wrong_cell", "scope_order", "ordinary_refused", "replay", "remote_replay",
    "success", "exit", "deliverables", "cleanup", "timeout", "receipt", "source", "inference_run",
    "original_bytes", "private_payload", "inference_ack", "approval_skipped", "approval_failed", "request", "rerun",
    "controller", "wrong_ref", "previous_missing", "previous_skipped", "previous_unfinished", "previous_controller",
    "previous_policy", "previous_type", "previous_observation", "backing_no_child", "backing_source", "backing_hash",
    "backing_missing", "resolution", "cas", "claim_lost", "publication_lost", "claim_readback", "admission_cache",
    "publication_parent", "terminal_policy", "terminal_score", "terminal_child", "terminal_receipt",
    "terminal_boolean", "terminal_private", "terminal_parent", "terminal_previous_hash", "terminal_history",
    "terminal_cross_cycle",
]


@pytest.mark.parametrize("change", CASES)
def test_fixed_task5_a1_after_ungraded_a2(task5_history, tmp_path, monkeypatch, capsys, change):
    history = task5_history
    terminal_case = change.startswith("terminal_")
    api = copy.deepcopy(history.after_task5 if terminal_case or change in {
        "chain", "ordinary_refused", "replay", "remote_replay"} else history.before_task5)
    current = _select(history, api, tmp_path, monkeypatch,
        controller=chain.FOREIGN if change == "controller" else failed.FUTURE_CONTROLLER)
    _no_judge(monkeypatch, current)
    context, inference, backing = current.context, current.inference, history.grades["B_r2"]
    previous_cell = context.plan["cells"][23]
    api.calls.clear()
    api.events.clear()
    api.reads.clear()

    if change == "chain":
        terminal, prepared = history.task5_terminal, history.task5_prepared
        assert terminal["format"] == ungraded.TERMINAL_FORMAT and terminal["outcome"] == "ungraded"
        assert terminal["binding"]["policy"] == "task5-a1-model-free-ungraded"
        assert terminal["binding"]["github_run"] == {"id": "991024", "job": "pilot-live", "attempt": 1}
        assert terminal["model_invoked"] is False and not {"child", "files", "score", "verdict"}.intersection(terminal)
        completed = terminal["inference_completion"]
        assert completed == inference.evidence["terminal"]["completion"]
        assert completed["status"] == "failed" and completed["exit_code"] == 1 and completed["denominator"] == 30
        assert completed["reason"] == "child_nonzero_exit" and completed["artifacts"]["deliverables"] == []
        assert completed["receipt"] is not None and terminal["inference_missing"] == inference.evidence["manifest"]["missing"]
        assert terminal["recorder_accounting"] == {"status": "not_measured", "known_cost_usd": None,
            "estimated_cost_usd": None, "invoice_complete": False, "http_request_count": None}
        assert prepared["model_free_record_ready"] is True and prepared["judge_ready"] is False
        assert "entry" not in prepared and "rubric" not in prepared
        claim = history.task5_admission["claim"]
        assert claim["expected_parent"] == history.a2_revision
        assert claim["predecessor"] == {"cell_id": grading.TASK4_A2_CELL, "revision": history.a2_revision,
                                      **pilot._identity(retained._encoded(history.a2_terminal))}
        assert prepared["evidence"]["claim"]["predecessor"] == history.a2_terminal["binding"]["retained"]
        assert history.a2_terminal["binding"]["policy"] == "recorded_task4_failed_a2_no_judge"
        assert history.a2_admission["claim"]["expected_parent"] == backing.revision
        assert history.a2_prepared["evidence"]["claim"]["predecessor"] == backing.terminal["binding"]["retained"]
        assert backing.terminal["format"] == grading.RESULT_FORMAT and backing.terminal["child"]["entry_invoked"] is True
        assert history.pair.a1_terminal["binding"]["policy"] == "recorded_task4_failed_a1_no_judge"
        assert history.pair.a1_admission["claim"]["predecessor"]["cell_id"] == failed.PREVIOUS
        assert history.pair.b1_admission["claim"]["predecessor"]["revision"] == history.pair.a1_revision
        assert history.pair.b1_terminal["child"]["entry_invoked"] is True
        assert len({history.task5_revision, terminal["claim_commit"], history.a2_revision,
                    history.a2_terminal["claim_commit"], backing.revision}) == 5
        visits, verify = [], ungraded.verify_terminal
        def bounded(*args, **kwargs):
            visits.append(args[3].cell["cell_id"])
            assert visits == [CELL] or visits == [CELL, grading.TASK4_A2_CELL]
            return verify(*args, **kwargs)
        monkeypatch.setattr(ungraded, "verify_terminal", bounded)
        with retained._session(api) as (client, token, deadline):
            verified = ungraded.verify_terminal(client, api.repo, history.task5_revision, context,
                prepared["predecessor_entry"], grading._cache(tmp_path, "verified"), token, deadline)
        assert visits == [CELL, grading.TASK4_A2_CELL] and verified["terminal"] == terminal
        successors._unchanged(api, (history.before_task5.trees, history.before_task5.writers,
                                   history.before_task5.parents, history.before_task5.branches[retained.BRANCH]))
        assert api.events == [] and current.transport.calls == 0
        return

    if change == "plan_workflow":
        assert list(grading.TASK5_RETAINED) == [CELL, grading.TASK5_B1_CELL, grading.TASK5_C1_CELL]
        assert context.plan["order"][24:27] == [CELL, grading.TASK5_B1_CELL, grading.TASK5_C1_CELL]
        assert context.plan["order"][23:25] == [grading.TASK4_A2_CELL, CELL] and len(context.plan["order"]) == 30
        assert context.plan["order"][18:24] == list(grading.TASK4_RETAINED)
        assert context.controller_source_sha != context.plan["reviewed_source_sha"] == failed.PRODUCER
        assert grading._model_free_context(context) and context.terminal_revision == ""
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert context.plan["model"]["deployment"] == "gpt-5.4" and context.plan["model"]["route_profile"] == "direct-v1"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        for cell_id in context.plan["order"][27:]:
            assert cell_id not in grading.TASK5_RETAINED
            with pytest.raises(output.OutputPublicationRefused, match="closed_retained_producer_binding_required"):
                grading.compile_request("pilot/" + cell_id, failed.FUTURE_CONTROLLER, current.request,
                                        producer_source_sha=failed.PRODUCER)
        jobs = history.workflow["jobs"]
        expression = jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == expression
        assert expression.count('"pilot/' + CELL + '"') == 1
        assert all('"pilot/' + cell_id + '"' not in expression for cell_id in context.plan["order"][27:])
        assert jobs["pilot-live"]["needs"] == ["pilot-approve-paid"] and "environment" not in jobs["pilot-live"]
        assert "needs.pilot-approve-paid.result == 'success'" in jobs["pilot-live"]["if"]
        assert jobs["pilot-live"]["env"]["PILOT_WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
        assert jobs["pilot-live"]["permissions"] == {"contents": "read", "id-token": "write"}
        assert jobs["pilot-approve-paid"]["permissions"] == {} and len(jobs["pilot-approve-paid"]["steps"]) == 1
        assert jobs["pilot-approve-paid"]["environment"] == {"name": "grading"}
        steps = {step["name"]: step for step in jobs["pilot-live"]["steps"] if "name" in step}
        recorder = steps["Record only the fixed failed task4 A1/A2 or task5 A1/B1 without a judge"]
        assert "(inputs.experiment_yaml == 'pilot/" + grading.TASK4_A1_CELL + "' ||" in recorder["if"]
        assert "inputs.experiment_yaml == 'pilot/" + grading.TASK4_A2_CELL + "' ||" in recorder["if"]
        assert "inputs.experiment_yaml == 'pilot/" + CELL + "' ||" in recorder["if"]
        assert "inputs.experiment_yaml == 'pilot/" + grading.TASK5_B1_CELL + "') &&" in recorder["if"]
        assert all(cell_id not in recorder["if"] for cell_id in context.plan["order"][26:])
        assert "judge_ready == 'false'" in recorder["if"] and "model_free_record_ready == 'true'" in recorder["if"]
        assert set(recorder["env"]) == {"HF_TOKEN"} and "--phase record-ungraded" in recorder["run"]
        for name in ("Validate grading OIDC identity", "Validate fixed grader Azure route", "Grading Azure login (OIDC)",
                     "Verify grading OIDC session", "Verify fixed grader model connection",
                     "Claim one private grading admission with parent CAS", "Invoke exactly the compiled fixed Step8 command once"):
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in steps[name]["if"]
        assert "steps.pilot_judge.outcome != 'skipped'" in steps["Retain validated private grade and accounting on the grading branch"]["if"]
        assert grading._context_authority(context)["id"] == "991024"  # Actual workflow digest was executed by _select.
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        assert successors._invoke(current, capsys)[0] == 0
        assert not current.root.exists() and api.calls == []
        return

    if change in {"wrong_cell", "scope_order"}:
        other = copy.deepcopy(context)
        if change == "wrong_cell":
            other.cell = other.plan["cells"][25]
        else:
            other.plan["order"][23] = grading.TASK4_A1_CELL
        with pytest.raises(output.OutputPublicationRefused):
            ungraded.record(other, current.root, _test_api=api, _test_transport=current.transport)
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if terminal_case:
        terminal = copy.deepcopy(history.task5_terminal)
        claim_path = grading._paths(context.cell)[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
        if change == "terminal_policy":
            terminal["binding"]["policy"] = ungraded.A2_POLICY
        elif change == "terminal_score":
            terminal["score"] = 0
        elif change == "terminal_child":
            terminal["child"] = {"entry_invoked": True, "exit_code": 0, "cleanup_confirmed": True}
        elif change == "terminal_receipt":
            terminal["inference_completion"]["receipt"]["sha256"] = "0" * 64
            assert terminal["inference_completion"]["receipt"] != history.task5_terminal["inference_completion"]["receipt"]
            ci.validate_completion(terminal["inference_completion"])
        elif change == "terminal_boolean":
            terminal["inference_completion"]["exit_code"] = True
        elif change == "terminal_private":
            terminal["debug"] = "PRIVATE https://private.invalid/?token=PRIVATE"
        elif change == "terminal_parent":
            claim["expected_parent"] = claim["predecessor"]["revision"] = history.task5_revision
        elif change == "terminal_previous_hash":
            claim["predecessor"]["sha256"] = "0" * 64
        elif change == "terminal_history":
            api.trees[terminal["claim_commit"]][history.a2_path] += b" "
        elif change == "terminal_cross_cycle":
            previous = copy.deepcopy(history.a2_terminal)
            previous_claim = copy.deepcopy(history.a2_admission["claim"])
            previous_claim["expected_parent"] = previous_claim["predecessor"]["revision"] = terminal["claim_commit"]
            _store_record(api, previous_cell, history.a2_revision, previous, previous_claim)
            claim["predecessor"].update(pilot._identity(retained._encoded(previous)))
        _store_record(api, context.cell, history.task5_revision, terminal, claim)
        frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
        with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                match="model_free_task5_chain_revision_changed" if change == "terminal_cross_cycle" else None):
            ungraded.verify_terminal(client, api.repo, history.task5_revision, context,
                history.task5_prepared["predecessor_entry"], grading._cache(tmp_path, "terminal"), token, deadline)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"ordinary_refused", "replay"}:
        shutil.copytree(history.task5_root, current.root)
        if change == "ordinary_refused":
            prepared = retained._read(current.root / "prepared.json")
            prepared["judge_ready"] = True
            (current.root / "prepared.json").write_bytes(retained._encoded(prepared))
            for phase in ("claim", "judge", "publish", "reconcile"):
                assert successors._invoke(current, capsys, phase)[0] == 2
            with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                    match="model_free_terminal_not_judged"):
                grading._grade_terminal(client, api.repo, history.task5_revision, context,
                    history.task5_prepared["predecessor_entry"], grading._cache(tmp_path, "ordinary"), token, deadline)
        else:
            assert successors._invoke(current, capsys, "record-ungraded")[0] == 2
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"success", "exit", "deliverables", "cleanup", "timeout", "receipt", "source", "inference_ack"}:
        terminal = copy.deepcopy(inference.evidence["terminal"])
        key, value = {"success": ("status", "succeeded"), "exit": ("exit_code", 0), "cleanup": ("cleanup_confirmed", False),
                      "timeout": ("timeout", True), "source": ("source_sha", chain.FOREIGN)}.get(change, (None, None))
        if key:
            terminal["completion"][key] = value
        elif change == "deliverables":
            terminal["completion"]["artifacts"]["deliverables"] = [{"size": 1, "sha256": "0" * 64}]
        elif change == "receipt":
            terminal["completion"]["receipt"]["sha256"] = "0" * 64
            assert terminal["completion"]["receipt"] != inference.evidence["terminal"]["completion"]["receipt"]
            ci.validate_completion(terminal["completion"])
        else:
            terminal["publication_acknowledged"] = False
        api.trees[inference.terminal][inference.terminal_path] = retained._encoded(terminal)
    elif change == "inference_run":
        claim = copy.deepcopy(inference.evidence["claim"])
        claim["binding"]["github_run"]["id"] = "991099"
        api.trees[inference.claim][inference.claim_path] = retained._encoded(claim)
    elif change in {"original_bytes", "private_payload"}:
        path = retained._paths(context.cell)[2] + "/step2_inference_results.json"
        api.trees[inference.output][path] += b" " if change == "original_bytes" else b"PRIVATE https://private.invalid"
    elif change == "wrong_ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif change in {"approval_skipped", "approval_failed"}:
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped" if change == "approval_skipped" else "failure")
    elif change == "request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change in {"previous_missing", "previous_skipped", "previous_unfinished"}:
        api.branches[grading.BRANCH] = {"previous_missing": retained.BOOTSTRAP,
            "previous_skipped": backing.revision, "previous_unfinished": history.a2_terminal["claim_commit"]}[change]
    elif change.startswith("previous_"):
        terminal, claim = copy.deepcopy(history.a2_terminal), copy.deepcopy(history.a2_admission["claim"])
        if change == "previous_controller":
            terminal["binding"]["controller_source_sha"] = chain.FOREIGN
            terminal["binding"]["approval_request_sha256"] = grading._approval_request_sha256(chain.FOREIGN,
                "pilot/" + grading.TASK4_A2_CELL, grading.TASK4_RETAINED[grading.TASK4_A2_CELL][1],
                terminal["binding"]["github_run"], producer_source_sha=failed.PRODUCER)
        elif change == "previous_policy":
            terminal["binding"]["policy"] = ungraded.POLICY
        elif change == "previous_type":
            terminal["format"] = grading.RESULT_FORMAT
        else:
            terminal["binding"]["retained"]["manifest_sha256"] = "0" * 64
        claim["binding"] = terminal["binding"]
        _store_record(api, previous_cell, history.a2_revision, terminal, claim)
    elif change.startswith("backing_"):
        if change == "backing_missing":
            api.trees[backing.revision].pop(backing.path)
        else:
            terminal = copy.deepcopy(backing.terminal)
            if change == "backing_no_child":
                terminal["child"]["entry_invoked"] = False
            elif change == "backing_source":
                terminal["binding"]["controller_source_sha"] = chain.FOREIGN
            else:
                terminal["binding"]["grader_source_hash"] = "0" * 64
            claim_path = grading._paths(context.plan["cells"][22])[0]
            claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
            claim["binding"] = terminal["binding"]
            _store_record(api, context.plan["cells"][22], backing.revision, terminal, claim)
            previous, previous_claim = copy.deepcopy(history.a2_terminal), copy.deepcopy(history.a2_admission["claim"])
            previous_claim["predecessor"].update(pilot._identity(retained._encoded(terminal)))
            _store_record(api, previous_cell, history.a2_revision, previous, previous_claim)

    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
    if change in {"success", "exit", "deliverables", "cleanup", "timeout", "receipt", "source", "inference_run",
                  "original_bytes", "private_payload", "inference_ack", "approval_skipped", "approval_failed", "request",
                  "rerun", "wrong_ref"}:
        code, observed = successors._invoke(current, capsys, "prepare")
        assert code == 2 and observed["outcome"] == "refused", (observed, current.diagnostic)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    shutil.copytree(history.task5_prepared_root, current.root)
    if change == "resolution":
        path = current.root / "retained-resolution.json"
        value = retained._read(path)
        value["terminal_revision"] = history.inferences["A_r2"].terminal
        path.write_bytes(retained._encoded(value))
    elif change == "cas":
        api.move_before_commit = True
    elif change in {"claim_lost", "publication_lost"}:
        api.lost = "grade_claim" if change == "claim_lost" else "grade_output"
    elif change == "claim_readback":
        download = api.hf_hub_download
        def missing_readback(**kwargs):
            if kwargs["filename"] == grading._paths(context.cell)[0]:
                raise output.OutputPublicationRefused("hf_transport_failed")
            return download(**kwargs)
        api.hf_hub_download = missing_readback
    elif change in {"admission_cache", "publication_parent"}:
        write = grading._record
        def change_after_claim(path, value):
            write(path, value)
            if path.name == "model-free-claim-receipt.json" and value["outcome"] == "acknowledged":
                if change == "admission_cache":
                    cached = current.root / "model-free-claim-verified.json"
                    cached.write_bytes(cached.read_bytes() + b" ")
                else:
                    api.branches[grading.BRANCH] = backing.revision
        monkeypatch.setattr(grading, "_record", change_after_claim)
    code, observed = successors._invoke(current, capsys, "record-ungraded")
    assert code == 2, (observed, current.diagnostic)
    expected_calls = 2 if change == "publication_lost" else 1 if change in {
        "cas", "claim_lost", "claim_readback", "admission_cache", "publication_parent"} else 0
    assert len(api.events) == expected_calls and current.transport.calls == 0
    if change in {"claim_lost", "publication_lost"}:
        assert observed["outcome"] == "unresolved"
    events = list(api.events)
    assert successors._invoke(current, capsys, "record-ungraded")[0] == 2
    assert api.events == events
    successors._unchanged(api, frozen)
