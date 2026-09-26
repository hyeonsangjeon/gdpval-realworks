"""Only the fixed 25 -> 24 -> 23 -> ordinary 22 boundary, entirely offline.

Build the genuine synthetic predecessor history once, then isolate mutations.
The failed native turn and remote boundaries are fake, not reconstructed live
payloads, private revisions, issued record runs, or an inferred failure cause.
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
from . import test_codex_budget_pilot_task4_successor_grading as successors
from . import test_codex_budget_pilot_task5_failed_a1 as a1
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_B_r1"
RECORDED = ("36248894311", "dd05f2ed43235b69d9eecfefadfb0a5ebd68d83b31daf38355a4acf6f0a21c5b")


def _select(history, api, directory, patch, *, controller=failed.FUTURE_CONTROLLER):
    context = grading.compile_request("pilot/" + CELL, controller, grading.TASK5_RETAINED[CELL][1],
                                      producer_source_sha=failed.PRODUCER)
    current = SimpleNamespace(api=api, context=context, workflow=history.workflow,
        root=directory / "private-grade", request=context.requested_terminal, inference=history.b1_inference)
    current.transport = policy._SourceOnlyChild(current)
    patch.setattr(base, "OUTPUT", current.inference.output)
    patch.setenv("HF_TOKEN", base.TOKEN)
    base._synthetic_rubric(current, patch)
    approval._authorize(current, directory, patch, "991025")  # Synthetic, never an issued record run.
    return current


@pytest.fixture(scope="module")
def task5_b1_history(tmp_path_factory):
    assert grading.TASK5_B1_CELL == CELL and grading.TASK5_RETAINED[CELL] == RECORDED
    prototype = grading.compile_request("pilot/" + CELL, failed.PRODUCER, "8" * 40)
    error_row, ledger = failed._failed_row(prototype)
    histories = a1.task5_history.__wrapped__(tmp_path_factory)
    history = next(histories)  # Existing writers only; no prior test selector is called.
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("task5-failed-b1-history")
            capture, api = chain._Capture(), copy.deepcopy(history.after_task5)
            previous = history.task5_inference
            claim_revision, output_revision, terminal_revision = (f"{100_250 + i:040x}" for i in (1, 2, 3))
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
            assert digest != RECORDED[1]  # Genuine synthetic bytes are not the live completion.
            patch.setitem(grading.TASK5_RETAINED, CELL, (RECORDED[0], digest))
            history.b1_inference = SimpleNamespace(context=context, claim=claim_revision, output=output_revision,
                terminal=terminal_revision, claim_path=claim_path, terminal_path=terminal_path, evidence=evidence)
            api.branches[retained.BRANCH] = terminal_revision
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            history.before_b1 = copy.deepcopy(api)
            current = _select(history, api, directory, patch)
            api.calls.clear()
            api.events.clear()
            frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
            with patch.context() as no_judge, redirect_stdout(capture.out), redirect_stderr(capture.err):
                a1._no_judge(no_judge, current)
                code, observed = successors._invoke(current, capture, "prepare")
                assert code == 0 and observed["model_free_record_ready"] is True, (observed, current.diagnostic)
                assert observed["judge_ready"] is False and observed["grade_success"] is False
                history.b1_prepared = retained._read(current.root / "prepared.json")
                history.b1_prepared_root = directory / "prepared-task5-b1"
                shutil.copytree(current.root, history.b1_prepared_root)
                code, observed = successors._invoke(current, capture, "record-ungraded")
                assert code == 0 and observed["grading_state"] == "ungraded", (observed, current.diagnostic)
            assert api.events == ["grade_claim", "grade_output"] and current.transport.calls == 0
            successors._unchanged(api, frozen)
            history.b1_revision = api.branches[grading.BRANCH]
            history.b1_path = grading._paths(context.cell)[1]
            history.b1_terminal = pilot._json_object(api.trees[history.b1_revision][history.b1_path])
            history.b1_admission = retained._read(current.root / "model-free-claim-receipt.json")
            history.b1_root, history.after_b1 = current.root, copy.deepcopy(api)
            yield history
    finally:
        histories.close()


def _records(history, context):
    backing = history.grades["B_r2"]
    return [(context.plan["cells"][ordinal], revision) for ordinal, revision in (
        (22, backing.revision), (23, history.a2_revision),
        (24, history.task5_revision), (25, history.b1_revision))]


def _rewrite_linked(api, history, context, ordinal, terminal, claim):
    """Coherent isolated counterfactuals, so a deeper guard—not stale hashes—refuses."""
    previous_identity = None
    for cell, revision in _records(history, context)[ordinal - 22:]:
        if revision not in api.trees:  # B1 is not written in pre-admission cases.
            continue
        claim_path, terminal_path = grading._paths(cell)
        if previous_identity is not None:
            terminal = pilot._json_object(api.trees[revision][terminal_path])
            claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
            claim["predecessor"].update(previous_identity)
        claim_bytes = retained._encoded(claim)
        terminal["claim_identity"] = pilot._identity(claim_bytes)
        terminal_bytes = retained._encoded(terminal)
        for snapshot, tree in api.trees.items():
            if api.writers[snapshot].get(claim_path) == terminal["claim_commit"]:
                tree[claim_path] = claim_bytes
            if api.writers[snapshot].get(terminal_path) == revision:
                tree[terminal_path] = terminal_bytes
        previous_identity = pilot._identity(terminal_bytes)


CASES = [
    "chain", "plan_workflow", "wrong_cell", "scope_order", "ordinary_refused", "replay", "remote_replay",
    "success", "exit", "deliverables", "cleanup", "timeout", "receipt", "source", "inference_run",
    "original_bytes", "private_payload", "inference_ack", "approval_skipped", "approval_failed", "request", "rerun",
    "controller", "wrong_ref", "private_ref", "previous_missing", "previous_skipped", "previous_unfinished",
    "previous_controller", "previous_policy", "previous_type", "previous_observation",
    "a2_policy", "a2_type", "a2_order", "a2_claim_type", "backing_no_child", "backing_cleanup",
    "backing_source", "backing_hash", "backing_missing", "backing_run", "resolution", "cas", "claim_lost",
    "publication_lost", "claim_readback", "publication_readback", "admission_cache", "publication_parent",
    "terminal_policy", "terminal_score", "terminal_child", "terminal_receipt", "terminal_boolean", "terminal_private",
    "terminal_parent", "terminal_previous_hash", "terminal_history", "terminal_claim_type",
    "alias_terminal_backing_claim", "alias_claim_backing_claim", "alias_a1_claim_a2_claim",
    "alias_a2_terminal_b1_claim", "alias_a2_claim_b1_terminal", "alias_backing_terminal_b1_terminal",
]


@pytest.mark.parametrize("change", CASES)
def test_fixed_task5_b1_after_ungraded_a1(task5_b1_history, tmp_path, monkeypatch, capsys, change):
    history = task5_b1_history
    terminal_case = change.startswith(("terminal_", "alias_"))
    api = copy.deepcopy(history.after_b1 if terminal_case or change in {
        "chain", "ordinary_refused", "replay", "remote_replay"} else history.before_b1)
    current = _select(history, api, tmp_path, monkeypatch,
        controller=chain.FOREIGN if change == "controller" else failed.FUTURE_CONTROLLER)
    a1._no_judge(monkeypatch, current)
    context, inference, backing = current.context, current.inference, history.grades["B_r2"]
    api.calls.clear()
    api.events.clear()
    api.reads.clear()

    if change == "chain":
        terminal, prepared = history.b1_terminal, history.b1_prepared
        assert terminal["binding"]["policy"] == "task5-b1-model-free-ungraded"
        assert terminal["format"] == ungraded.TERMINAL_FORMAT and terminal["outcome"] == "ungraded"
        assert terminal["binding"]["github_run"] == {"id": "991025", "job": "pilot-live", "attempt": 1}
        assert terminal["model_invoked"] is False and not {"child", "files", "score", "verdict"}.intersection(terminal)
        completed = terminal["inference_completion"]
        assert completed == inference.evidence["terminal"]["completion"]
        assert completed["status"] == "failed" and completed["exit_code"] == 1 and completed["denominator"] == 30
        assert completed["reason"] == "child_nonzero_exit" and completed["artifacts"]["deliverables"] == []
        assert completed["child_invocations"] == 1 and completed["cleanup_confirmed"] is True
        assert completed["timeout"] is False and completed["receipt"] is not None
        assert terminal["inference_missing"] == inference.evidence["manifest"]["missing"]
        assert terminal["recorder_accounting"] == {"status": "not_measured", "known_cost_usd": None,
            "estimated_cost_usd": None, "invoice_complete": False, "http_request_count": None}
        assert prepared["model_free_record_ready"] is True and prepared["judge_ready"] is False
        assert "entry" not in prepared and "rubric" not in prepared
        previous = history.task5_terminal
        assert history.b1_admission["claim"]["predecessor"] == {"cell_id": grading.TASK5_A1_CELL,
            "revision": history.task5_revision, **pilot._identity(retained._encoded(previous))}
        assert prepared["evidence"]["claim"]["predecessor"] == previous["binding"]["retained"]
        assert previous["binding"]["policy"] == ungraded.TASK5_POLICY
        assert history.task5_admission["claim"]["expected_parent"] == history.a2_revision
        assert history.a2_terminal["binding"]["policy"] == ungraded.A2_POLICY
        assert history.a2_admission["claim"]["expected_parent"] == backing.revision
        assert backing.terminal["format"] == grading.RESULT_FORMAT and backing.terminal["child"]["entry_invoked"] is True
        revisions = [value for cell, revision in _records(history, context) for value in (
            revision, pilot._json_object(api.trees[revision][grading._paths(cell)[1]])["claim_commit"])]
        assert len(revisions) == len(set(revisions)) == 8
        visits, ordinary_visits = [], []
        verify, ordinary = ungraded.verify_terminal, grading._grade_terminal
        def bounded(*args, **kwargs):
            visits.append(args[3].cell["cell_id"])
            assert visits == [CELL, grading.TASK5_A1_CELL, grading.TASK4_A2_CELL][:len(visits)]
            return verify(*args, **kwargs)
        def backing_only(*args, **kwargs):
            ordinary_visits.append(args[3].cell["cell_id"])
            return ordinary(*args, **kwargs)
        monkeypatch.setattr(ungraded, "verify_terminal", bounded)
        monkeypatch.setattr(grading, "_grade_terminal", backing_only)
        with retained._session(api) as (client, token, deadline):
            verified = ungraded.verify_terminal(client, api.repo, history.b1_revision, context,
                prepared["predecessor_entry"], grading._cache(tmp_path, "verified"), token, deadline)
        assert visits == [CELL, grading.TASK5_A1_CELL, grading.TASK4_A2_CELL]
        assert ordinary_visits == [context.plan["order"][22]] and verified["terminal"] == terminal
        successors._unchanged(api, (history.before_b1.trees, history.before_b1.writers,
                                   history.before_b1.parents, history.before_b1.branches[retained.BRANCH]))
        assert api.events == [] and current.transport.calls == 0
        return

    if change == "plan_workflow":
        assert context.plan["order"][24:27] == list(grading.TASK5_RETAINED) == [
            grading.TASK5_A1_CELL, CELL, grading.TASK5_C1_CELL]
        assert context.plan["order"].index(CELL) == 25 and len(context.plan["order"]) == 30
        assert context.plan["order"][18:24] == list(grading.TASK4_RETAINED)
        assert context.cell["config_sha256"] == "db68ac51fb78fcce2497ee874aad33de5c81da3343736c8b75a4da17b88304d8"
        assert context.controller_source_sha != context.plan["reviewed_source_sha"] == failed.PRODUCER
        assert context.terminal_revision == "" and grading._model_free_context(context)
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        eligible = [cell["cell_id"] for cell in context.plan["cells"] if grading._model_free_context(
            SimpleNamespace(cell=cell, terminal_request=current.request))]
        assert eligible == [grading.TASK4_A1_CELL, grading.TASK4_A2_CELL, grading.TASK5_A1_CELL, CELL]
        for cell_id in context.plan["order"][27:]:
            with pytest.raises(output.OutputPublicationRefused, match="closed_retained_producer_binding_required"):
                grading.compile_request("pilot/" + cell_id, failed.FUTURE_CONTROLLER, current.request,
                                        producer_source_sha=failed.PRODUCER)
        jobs = history.workflow["jobs"]
        live, approve = jobs["pilot-live"], jobs["pilot-approve-paid"]
        expression = live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert expression == jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert expression.count('"pilot/' + CELL + '"') == 1
        assert all('"pilot/' + cell_id + '"' not in expression for cell_id in context.plan["order"][27:])
        assert live["needs"] == ["pilot-approve-paid"] and "environment" not in live
        assert "needs.pilot-approve-paid.result == 'success'" in live["if"]
        assert live["env"]["PILOT_WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
        assert live["permissions"] == {"contents": "read", "id-token": "write"}
        assert approve["permissions"] == {} and len(approve["steps"]) == 1
        assert approve["environment"] == {"name": "grading"}
        assert "HF_TOKEN" not in live["env"] and "HF_TOKEN" not in jobs["pilot-plan"]["env"]
        token_steps = [step for step in live["steps"] if "HF_TOKEN" in step.get("env", {})]
        phases = {}
        for step in token_steps:
            arguments = step["run"].split()
            assert arguments.count("--phase") == 1
            phase = arguments[arguments.index("--phase") + 1]
            assert phase not in phases
            phases[phase] = step
        assert len(token_steps) == 6 and set(phases) == {"setup", "inspect", "prepare", "claim", "publish", "record-ungraded"}
        recorder = phases["record-ungraded"]
        assert " ".join(recorder["if"].split()) == "(" + " || ".join(
            "inputs.experiment_yaml == 'pilot/" + cell_id + "'" for cell_id in eligible) + (
            ") && steps.pilot_input.outputs.model_free_record_ready == 'true' && "
            "steps.pilot_input.outputs.judge_ready == 'false'")
        assert recorder["timeout-minutes"] == 5 and recorder["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
        assert recorder["run"] == (
            "umask 077\npython batch-runner/codex_budget_pilot_grading.py --phase record-ungraded \\\n"
            '  --selector "$GRADE_SELECTOR" --reviewed-source-sha "$GITHUB_SHA" \\\n'
            '  --producer-source-sha "$PILOT_GRADE_PRODUCER_SOURCE_SHA" \\\n'
            '  --terminal-revision "$GRADE_TERMINAL" --root "$RUNNER_TEMP/pilot-fixed-grade"\n')
        steps = {step["name"]: step for step in live["steps"] if "name" in step}
        for name in ("Validate grading OIDC identity", "Validate fixed grader Azure route", "Grading Azure login (OIDC)",
                     "Verify grading OIDC session", "Verify fixed grader model connection",
                     "Claim one private grading admission with parent CAS", "Invoke exactly the compiled fixed Step8 command once"):
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in steps[name]["if"]
        assert "steps.pilot_judge.outcome != 'skipped'" in steps["Retain validated private grade and accounting on the grading branch"]["if"]
        assert not any("upload-artifact" in step.get("uses", "") for step in live["steps"])
        assert "HF_TOKEN" not in next(step for step in live["steps"] if step.get("id") == "pilot_judge").get("env", {})
        assert grading._context_authority(context)["id"] == "991025"  # Actual workflow digest executed by _select.
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        assert successors._invoke(current, capsys)[0] == 0
        assert not current.root.exists() and api.calls == []
        return

    if change in {"wrong_cell", "scope_order"}:
        other = copy.deepcopy(context)
        if change == "wrong_cell":
            other.cell = other.plan["cells"][26]
        else:
            other.plan["order"][24] = grading.TASK4_A2_CELL
        with pytest.raises(output.OutputPublicationRefused):
            ungraded.record(other, current.root, _test_api=api, _test_transport=current.transport)
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if terminal_case:
        terminal, claim = copy.deepcopy(history.b1_terminal), copy.deepcopy(history.b1_admission["claim"])
        revision = history.b1_revision
        if change == "terminal_policy":
            terminal["binding"]["policy"] = ungraded.TASK5_POLICY
            claim["binding"] = terminal["binding"]
        elif change == "terminal_score":
            terminal["score"] = 0
        elif change == "terminal_child":
            terminal["child"] = {"entry_invoked": True, "cleanup_confirmed": True, "exit_code": 0}
        elif change == "terminal_receipt":
            terminal["inference_completion"]["receipt"]["sha256"] = "0" * 64
            assert terminal["inference_completion"]["receipt"] != history.b1_terminal["inference_completion"]["receipt"]
            ci.validate_completion(terminal["inference_completion"])
        elif change == "terminal_boolean":
            terminal["inference_completion"]["exit_code"] = True
        elif change == "terminal_private":
            terminal["debug"] = "PRIVATE https://private.invalid/?token=PRIVATE"
        elif change == "terminal_parent":
            claim["expected_parent"] = claim["predecessor"]["revision"] = revision
        elif change == "terminal_previous_hash":
            claim["predecessor"]["sha256"] = "0" * 64
        elif change == "terminal_history":
            api.trees[terminal["claim_commit"]][history.task5_path] += b" "
        elif change == "terminal_claim_type":
            claim["binding"]["github_run"]["attempt"] = True
        elif change in {"alias_terminal_backing_claim", "alias_claim_backing_claim"}:
            alias = backing.terminal["claim_commit"]
            if change == "alias_terminal_backing_claim":
                revision = alias
            else:
                terminal["claim_commit"] = alias
                api.writers[alias][grading._paths(context.cell)[0]] = alias
        elif change.startswith("alias_"):
            ordinal = 24 if change == "alias_a1_claim_a2_claim" else 23
            cell, target_revision = _records(history, context)[ordinal - 22]
            target_path = grading._paths(cell)[1]
            target = pilot._json_object(api.trees[target_revision][target_path])
            target_claim = pilot._json_object(api.trees[target["claim_commit"]][grading._paths(cell)[0]])
            if change == "alias_a1_claim_a2_claim":
                target["claim_commit"] = history.a2_terminal["claim_commit"]
                api.trees[target["claim_commit"]][grading._paths(cell)[0]] = retained._encoded(target_claim)
                api.writers[target["claim_commit"]][grading._paths(cell)[0]] = target["claim_commit"]
            elif change == "alias_a2_claim_b1_terminal":
                target["claim_commit"] = revision
                api.writers[revision][grading._paths(cell)[0]] = revision
            else:
                # A1's A2 link aliases B1's claim, or A2's B2 link aliases B1's terminal.
                if change == "alias_a2_terminal_b1_claim":
                    ordinal = 24
                    cell, target_revision = _records(history, context)[2]
                    target = copy.deepcopy(history.task5_terminal)
                    target_claim = copy.deepcopy(history.task5_admission["claim"])
                    alias = terminal["claim_commit"]
                else:
                    alias = revision
                target_claim["expected_parent"] = target_claim["predecessor"]["revision"] = alias
            _rewrite_linked(api, history, context, ordinal, target, target_claim)
            terminal = pilot._json_object(api.trees[history.b1_revision][history.b1_path])
            claim = pilot._json_object(api.trees[terminal["claim_commit"]][grading._paths(context.cell)[0]])
        a1._store_record(api, context.cell, revision, terminal, claim)
        api.writers[revision][history.b1_path] = revision
        frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
        with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                match="model_free_task5_b1_chain_revision_changed" if change.startswith("alias_") else None):
            ungraded.verify_terminal(client, api.repo, revision, context, history.b1_prepared["predecessor_entry"],
                grading._cache(tmp_path, "terminal"), token, deadline)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"ordinary_refused", "replay"}:
        shutil.copytree(history.b1_root, current.root)
        if change == "ordinary_refused":
            prepared = retained._read(current.root / "prepared.json")
            prepared["judge_ready"] = True
            (current.root / "prepared.json").write_bytes(retained._encoded(prepared))
            for phase in ("claim", "judge", "publish", "reconcile"):
                assert successors._invoke(current, capsys, phase)[0] == 2
            with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                    match="model_free_terminal_not_judged"):
                grading._grade_terminal(client, api.repo, history.b1_revision, context,
                    history.b1_prepared["predecessor_entry"], grading._cache(tmp_path, "ordinary"), token, deadline)
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
    elif change == "private_ref":
        api.private = False
    elif change in {"approval_skipped", "approval_failed"}:
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped" if change == "approval_skipped" else "failure")
    elif change == "request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change in {"previous_missing", "previous_skipped", "previous_unfinished"}:
        api.branches[grading.BRANCH] = {"previous_missing": retained.BOOTSTRAP,
            "previous_skipped": history.a2_revision, "previous_unfinished": history.task5_terminal["claim_commit"]}[change]
    elif change.startswith(("previous_", "a2_", "backing_")):
        ordinal = 24 if change.startswith("previous_") else 23 if change.startswith("a2_") else 22
        cell, revision = _records(history, context)[ordinal - 22]
        path = grading._paths(cell)[1]
        terminal = pilot._json_object(api.trees[revision][path])
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][grading._paths(cell)[0]])
        if change in {"previous_controller", "backing_source"}:
            terminal["binding"]["controller_source_sha"] = chain.FOREIGN
        elif change in {"previous_policy", "a2_policy"}:
            terminal["binding"]["policy"] = ungraded.TASK5_B1_POLICY
        elif change in {"previous_type", "a2_type"}:
            terminal["format"] = grading.RESULT_FORMAT
        elif change == "previous_observation":
            terminal["binding"]["retained"]["manifest_sha256"] = "0" * 64
        elif change == "a2_order":
            claim["predecessor"]["cell_id"] = grading.TASK4_A1_CELL
        elif change == "backing_no_child":
            terminal["child"]["entry_invoked"] = False
        elif change == "backing_cleanup":
            terminal["child"]["cleanup_confirmed"] = False
        elif change == "backing_hash":
            terminal["binding"]["grader_source_hash"] = "0" * 64
        elif change == "backing_run":
            terminal["binding"]["github_run"]["attempt"] = 2
        claim["binding"] = copy.deepcopy(terminal["binding"])
        if change == "a2_claim_type":
            claim["binding"]["github_run"]["attempt"] = True
        _rewrite_linked(api, history, context, ordinal, terminal, claim)
        if change == "backing_missing":
            api.trees[revision].pop(path)

    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
    if change in {"success", "exit", "deliverables", "cleanup", "timeout", "receipt", "source", "inference_run",
                  "original_bytes", "private_payload", "inference_ack", "approval_skipped", "approval_failed", "request",
                  "rerun", "wrong_ref", "private_ref"}:
        code, observed = successors._invoke(current, capsys, "prepare")
        assert code == 2 and observed["outcome"] == "refused", (observed, current.diagnostic)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    shutil.copytree(history.b1_prepared_root, current.root)
    if change == "resolution":
        path = current.root / "retained-resolution.json"
        value = retained._read(path)
        value["terminal_revision"] = history.task5_inference.terminal
        path.write_bytes(retained._encoded(value))
    elif change == "cas":
        api.move_before_commit = True
    elif change in {"claim_lost", "publication_lost"}:
        api.lost = "grade_claim" if change == "claim_lost" else "grade_output"
    elif change in {"claim_readback", "publication_readback"}:
        download = api.hf_hub_download
        def missing_readback(**kwargs):
            if kwargs["filename"] == grading._paths(context.cell)[0 if change == "claim_readback" else 1]:
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
                    api.branches[grading.BRANCH] = history.a2_revision
        monkeypatch.setattr(grading, "_record", change_after_claim)
    code, observed = successors._invoke(current, capsys, "record-ungraded")
    assert code == 2, (observed, current.diagnostic)
    expected_calls = 2 if change in {"publication_lost", "publication_readback"} else 1 if change in {
        "cas", "claim_lost", "claim_readback", "admission_cache", "publication_parent"} else 0
    assert len(api.events) == expected_calls and current.transport.calls == 0
    if change in {"claim_lost", "publication_lost"}:
        assert observed["outcome"] == "unresolved"
    events = list(api.events)
    assert successors._invoke(current, capsys, "record-ungraded")[0] == 2
    assert api.events == events
    successors._unchanged(api, frozen)
