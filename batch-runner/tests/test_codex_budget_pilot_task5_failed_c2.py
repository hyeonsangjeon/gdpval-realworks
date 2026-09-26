"""Exact failed C2 after ordinary C1 and its fixed B1 backing, entirely offline.

The shared history uses genuine writers and synthetic inputs; no live payload,
private revision, future record run, quality or failure cause is reconstructed.
Each counterfactual gets an isolated copy, not another full-history fixture.
"""

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
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
from . import test_codex_budget_pilot_task5_c1_grading as c1
from . import test_codex_budget_pilot_task5_failed_a1 as a1
from . import test_codex_budget_pilot_task5_failed_b1 as b1
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block live boundaries

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_C_r2"
RECORDED = ("36265102718", "db5c3fa1a927e88684b99b8eca93b6e442e97e05f500f36755c50000f3d42294")


def _select(history, api, directory, patch, *, controller=failed.FUTURE_CONTROLLER):
    context = grading.compile_request("pilot/" + CELL, controller, grading.TASK5_RETAINED[CELL][1],
                                      producer_source_sha=failed.PRODUCER)
    current = SimpleNamespace(api=api, context=context, workflow=history.workflow,
        root=directory / "private-grade", request=context.requested_terminal, inference=history.c2_inference)
    current.transport = policy._SourceOnlyChild(current)
    patch.setattr(base, "OUTPUT", current.inference.output)
    patch.setenv("HF_TOKEN", base.TOKEN)
    base._synthetic_rubric(current, patch)
    approval._authorize(current, directory, patch, "991027")  # Synthetic, not an issued record run.
    return current


@pytest.fixture(scope="module")
def c2_history(tmp_path_factory):
    assert grading.TASK5_C2_CELL == CELL and grading.TASK5_RETAINED[CELL] == RECORDED
    prototype = grading.compile_request("pilot/" + CELL, failed.PRODUCER, "8" * 40)
    error_row, ledger = failed._failed_row(prototype)
    histories = c1.c1_history.__wrapped__(tmp_path_factory)
    history = next(histories)  # Existing writers only; no previous test function is invoked.
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("task5-failed-c2-history")
            capture, api = chain._Capture(), copy.deepcopy(history.c1_after)
            previous = history.c1_inference
            claim_revision, output_revision, terminal_revision, snapshot = (
                f"{100_270 + i:040x}" for i in (1, 2, 3, 4))
            assert not {claim_revision, output_revision, terminal_revision, snapshot}.intersection(api.trees)
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
            assert digest != RECORDED[1]  # Fixture bytes are not the supplied live completion.
            patch.setitem(grading.TASK5_RETAINED, CELL, (RECORDED[0], digest))
            history.c2_inference = SimpleNamespace(context=context, claim=claim_revision, output=output_revision,
                terminal=terminal_revision, claim_path=claim_path, terminal_path=terminal_path, evidence=evidence)
            api.seed(snapshot, terminal_revision, {})  # Advance a snapshot, not another registered cell.
            api.branches[retained.BRANCH] = snapshot
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            history.c2_before = copy.deepcopy(api)
            current = _select(history, api, directory, patch)
            api.calls.clear()
            api.events.clear()
            frozen = copy.deepcopy((api.trees, api.writers, api.parents, snapshot))
            with patch.context() as no_judge, redirect_stdout(capture.out), redirect_stderr(capture.err):
                a1._no_judge(no_judge, current)
                code, observed = successors._invoke(current, capture, "prepare")
                assert code == 0 and observed["model_free_record_ready"] is True, (observed, current.diagnostic)
                assert observed["judge_ready"] is False and observed["grade_success"] is False
                prepared = retained._read(current.root / "prepared.json")
                history.c2_prepared_root = directory / "prepared-c2"
                shutil.copytree(current.root, history.c2_prepared_root)
                assert prepared["predecessor_entry"] == {key: history.c1.prepared["entry"][key]
                    for key in ("config_hash", "grader_source_hash", "renderer_fingerprint")}
                code, observed = successors._invoke(current, capture, "record-ungraded")
                assert code == 0 and observed["grading_state"] == "ungraded", (observed, current.diagnostic)
            assert api.events == ["grade_claim", "grade_output"] and current.transport.calls == 0
            successors._unchanged(api, frozen)
            revision, path = api.branches[grading.BRANCH], grading._paths(context.cell)[1]
            history.c2 = SimpleNamespace(revision=revision, path=path, root=current.root, prepared=prepared,
                terminal=pilot._json_object(api.trees[revision][path]),
                admission=retained._read(current.root / "model-free-claim-receipt.json"))
            history.c2_after = copy.deepcopy(api)
            yield history
    finally:
        histories.close()


def _rewrite(api, history, context, ordinal, terminal, claim):
    """Propagate isolated mutations through known hashes, not stale-link failures."""
    identity = None
    if ordinal < 26:
        b1._rewrite_linked(api, history, context, ordinal, terminal, claim)
        identity = pilot._identity(api.trees[history.b1_revision][history.b1_path])
        ordinal = 26
    for index, row in ((26, history.c1), (27, history.c2)):
        if index < ordinal or row.revision not in api.trees:
            continue
        cell = context.plan["cells"][index]
        claim_path, terminal_path = grading._paths(cell)
        if identity is not None:
            terminal = pilot._json_object(api.trees[row.revision][terminal_path])
            claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
            claim["predecessor"].update(identity)
        claim_bytes = retained._encoded(claim)
        terminal["claim_identity"] = pilot._identity(claim_bytes)
        terminal_bytes = retained._encoded(terminal)
        for snapshot, tree in api.trees.items():
            if api.writers[snapshot].get(claim_path) == terminal["claim_commit"]:
                tree[claim_path] = claim_bytes
            if api.writers[snapshot].get(terminal_path) == row.revision:
                tree[terminal_path] = terminal_bytes
        identity = pilot._identity(terminal_bytes)


PREPARE_CASES = ["success", "exit", "deliverables", "cleanup", "timeout", "receipt", "source",
    "inference_run", "inference_attempt_type", "original_bytes", "private_payload", "inference_ack",
    "snapshot_hash", "approval_missing", "approval_skipped", "approval_failed", "request", "rerun",
    "source_spoof", "producer_override", "wrong_completion", "wrong_ref", "private_ref"]
PREDECESSOR_CASES = ["previous_missing", "previous_skipped", "previous_unfinished", "previous_type",
    "previous_child", "previous_cleanup", "previous_controller", "previous_source", "previous_hash",
    "previous_claim_type", "previous_order", "previous_receipt", "previous_observation", "previous_history",
    "b1_policy", "b1_type", "backing_child", "backing_cleanup", "backing_hash", "controller",
    "inference_predecessor", "c1_inference_predecessor", "alias_c1_terminal_b1_claim"]
WRITE_CASES = ["resolution", "cas", "claim_lost", "publication_lost", "claim_readback", "publication_readback",
    "admission_cache", "admission_type", "admission_receipt_type", "publication_parent", "unapproved_record"]
TERMINAL_CASES = ["terminal_policy", "terminal_score", "terminal_child", "terminal_receipt", "terminal_boolean",
    "terminal_private", "terminal_parent", "terminal_previous_hash", "terminal_history", "terminal_claim_type",
    "terminal_c1_child", "terminal_b1_policy", "alias_terminal_backing_claim", "alias_claim_a2_claim"]
CASES = ["chain", "plan_workflow", "wrong_cell", "scope_order", "ordinary_refused", "replay", "remote_replay"] + (
    PREPARE_CASES + PREDECESSOR_CASES + WRITE_CASES + TERMINAL_CASES)


@pytest.mark.parametrize("change", CASES)
def test_fixed_task5_c2_after_ordinary_c1(c2_history, tmp_path, monkeypatch, capsys, change):
    history, row = c2_history, c2_history.c2
    terminal_case = change in TERMINAL_CASES
    api = copy.deepcopy(history.c2_after if terminal_case or change in {
        "chain", "ordinary_refused", "replay", "remote_replay"} else history.c2_before)
    current = _select(history, api, tmp_path, monkeypatch,
        controller=chain.FOREIGN if change == "controller" else failed.FUTURE_CONTROLLER)
    a1._no_judge(monkeypatch, current)
    context, inference = current.context, current.inference
    api.calls.clear()
    api.events.clear()
    api.reads.clear()

    if change == "chain":
        terminal, prepared, claim = row.terminal, row.prepared, row.admission["claim"]
        assert terminal["format"] == ungraded.TERMINAL_FORMAT and terminal["outcome"] == "ungraded"
        assert terminal["binding"]["policy"] == "task5-c2-model-free-ungraded"
        assert terminal["binding"]["github_run"] == {"id": "991027", "job": "pilot-live", "attempt": 1}
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
        assert prepared["terminal_revision"] == inference.terminal != api.branches[retained.BRANCH]
        assert prepared["evidence"] == inference.evidence
        assert claim["expected_parent"] == history.c1.revision
        assert claim["predecessor"] == {"cell_id": grading.TASK5_C1_CELL, "revision": history.c1.revision,
                                       **pilot._identity(retained._encoded(history.c1.terminal))}
        assert prepared["evidence"]["claim"]["predecessor"] == history.c1.terminal["binding"]["retained"]
        assert history.c1.terminal["format"] == grading.RESULT_FORMAT
        assert history.c1.terminal["child"]["entry_invoked"] is True
        assert history.c1.terminal["child"]["cleanup_confirmed"] is True
        assert history.c1.admission["claim"]["expected_parent"] == history.b1_revision
        assert history.c1.prepared["evidence"]["claim"]["predecessor"] == history.b1_terminal["binding"]["retained"]
        pairs = b1._records(history, context) + [(context.plan["cells"][26], history.c1.revision),
                                                (context.cell, row.revision)]
        revisions = [value for cell, revision in pairs for value in (
            revision, pilot._json_object(api.trees[revision][grading._paths(cell)[1]])["claim_commit"])]
        assert len(revisions) == len(set(revisions)) == 12
        visits, ordinary_visits = [], []
        verify, ordinary = ungraded.verify_terminal, grading._grade_terminal

        def fixed(*args, **kwargs):
            visits.append(args[3].cell["cell_id"])
            return verify(*args, **kwargs)

        def ordinary_only(*args, **kwargs):
            ordinary_visits.append(args[3].cell["cell_id"])
            return ordinary(*args, **kwargs)

        monkeypatch.setattr(ungraded, "verify_terminal", fixed)
        monkeypatch.setattr(grading, "_grade_terminal", ordinary_only)
        with retained._session(api) as (client, token, deadline):
            result = ungraded.verify_terminal(client, api.repo, row.revision, context, prepared["predecessor_entry"],
                grading._cache(tmp_path, "verified"), token, deadline)
        assert visits == [CELL, grading.TASK5_B1_CELL, grading.TASK5_A1_CELL, grading.TASK4_A2_CELL]
        assert ordinary_visits == [grading.TASK5_C1_CELL, context.plan["order"][22]]
        assert result["terminal"] == terminal and api.events == [] and current.transport.calls == 0
        successors._unchanged(api, (history.c2_before.trees, history.c2_before.writers,
            history.c2_before.parents, history.c2_before.branches[retained.BRANCH]))
        return

    if change == "plan_workflow":
        assert context.plan["order"][24:28] == list(grading.TASK5_RETAINED) == [
            grading.TASK5_A1_CELL, grading.TASK5_B1_CELL, grading.TASK5_C1_CELL, CELL]
        assert context.plan["order"].index(CELL) == 27 and len(context.plan["order"]) == 30
        assert context.cell["config_sha256"] == "3200e72fa661cd5c54ddd5f777f35fdbdf5c866011d073647df3ac2e0f997a71"
        assert context.controller_source_sha != context.plan["reviewed_source_sha"] == failed.PRODUCER
        assert context.terminal_revision == "" and grading._model_free_context(context)
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        eligible = [cell["cell_id"] for cell in context.plan["cells"] if grading._model_free_context(
            SimpleNamespace(cell=cell, terminal_request=current.request))]
        assert eligible == [grading.TASK4_A1_CELL, grading.TASK4_A2_CELL, grading.TASK5_A1_CELL,
                            grading.TASK5_B1_CELL, CELL]
        for cell_id in context.plan["order"][28:]:
            assert cell_id not in grading.TASK5_RETAINED
            with pytest.raises(output.OutputPublicationRefused, match="closed_retained_producer_binding_required"):
                grading.compile_request("pilot/" + cell_id, failed.FUTURE_CONTROLLER, current.request,
                                        producer_source_sha=failed.PRODUCER)
        jobs = history.workflow["jobs"]
        live, approve, plan = jobs["pilot-live"], jobs["pilot-approve-paid"], jobs["pilot-plan"]
        expression = live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert expression == plan["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert all(expression.count('"pilot/' + cell_id + '"') == 1 for cell_id in grading.TASK5_RETAINED)
        assert all('"pilot/' + cell_id + '"' not in expression for cell_id in context.plan["order"][28:])
        assert live["needs"] == ["pilot-approve-paid"] and "environment" not in live
        assert "needs.pilot-approve-paid.result == 'success'" in live["if"]
        assert live["env"]["PILOT_WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
        assert live["permissions"] == {"contents": "read", "id-token": "write"} and live["timeout-minutes"] == 300
        assert approve["permissions"] == {} and len(approve["steps"]) == 1
        assert approve["environment"] == {"name": "grading"}
        assert "HF_TOKEN" not in live["env"] and "HF_TOKEN" not in plan["env"]
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
        assert grading.TASK5_C1_CELL not in recorder["if"]
        assert recorder["timeout-minutes"] == 5 and recorder["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
        assert recorder["run"] == (
            "umask 077\npython batch-runner/codex_budget_pilot_grading.py --phase record-ungraded \\\n"
            '  --selector "$GRADE_SELECTOR" --reviewed-source-sha "$GITHUB_SHA" \\\n'
            '  --producer-source-sha "$PILOT_GRADE_PRODUCER_SOURCE_SHA" \\\n'
            '  --terminal-revision "$GRADE_TERMINAL" --root "$RUNNER_TEMP/pilot-fixed-grade"\n')
        assert phases["inspect"]["if"] == ("inputs.experiment_yaml == 'pilot/branch-inspect' || "
                                          "inputs.experiment_yaml == 'pilot/inference-branch-inspect'")
        assert phases["inspect"]["timeout-minutes"] == 2
        for step in live["steps"]:
            if ("azure" in step.get("run", "").lower() or "azure/login" in step.get("uses", "")
                    or step.get("id") in {"pilot_claim", "pilot_judge"}):
                assert "steps.pilot_input.outputs.judge_ready == 'true'" in step["if"]
        assert "steps.pilot_claim.outcome == 'success'" in phases["publish"]["if"]
        assert "steps.pilot_judge.outcome != 'skipped'" in phases["publish"]["if"]
        assert not any("upload-artifact" in step.get("uses", "") for job in (plan, live) for step in job["steps"])
        assert "HF_TOKEN" not in next(step for step in live["steps"] if step.get("id") == "pilot_judge").get("env", {})
        validate = next(step for step in live["steps"] if step.get("name") == "Validate the exact selected pilot route")
        assert all(fragment in validate["run"] for fragment in (
            'test "$GITHUB_SHA" = "$PILOT_WORKFLOW_SHA"', 'test "$GITHUB_REF" = refs/heads/main',
            'test "$GITHUB_RUN_ATTEMPT" = 1'))
        assert grading._context_authority(context)["id"] == "991027"  # Actual workflow digest, synthetic authority.
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
            other.plan["order"][26] = grading.TASK5_B1_CELL
        with pytest.raises(output.OutputPublicationRefused):
            ungraded.record(other, current.root, _test_api=api, _test_transport=current.transport)
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if terminal_case:
        terminal, claim, revision = copy.deepcopy(row.terminal), copy.deepcopy(row.admission["claim"]), row.revision
        if change == "terminal_policy":
            terminal["binding"]["policy"] = ungraded.TASK5_B1_POLICY
            claim["binding"] = terminal["binding"]
        elif change == "terminal_score":
            terminal["score"] = 0
        elif change == "terminal_child":
            terminal["child"] = {"entry_invoked": True, "cleanup_confirmed": True, "exit_code": 0}
        elif change == "terminal_receipt":
            terminal["inference_completion"]["receipt"]["sha256"] = "0" * 64
        elif change == "terminal_boolean":
            terminal["inference_completion"]["exit_code"] = True
        elif change == "terminal_private":
            terminal["debug"] = chain.PRIVATE
        elif change == "terminal_parent":
            claim["expected_parent"] = claim["predecessor"]["revision"] = revision
        elif change == "terminal_previous_hash":
            claim["predecessor"]["sha256"] = "0" * 64
        elif change == "terminal_history":
            api.trees[terminal["claim_commit"]][history.c1.path] += b" "
        elif change == "terminal_claim_type":
            claim["binding"]["github_run"]["attempt"] = True
        elif change in {"terminal_c1_child", "terminal_b1_policy"}:
            ordinal = 26 if change == "terminal_c1_child" else 25
            prior = history.c1.terminal if ordinal == 26 else history.b1_terminal
            prior = copy.deepcopy(prior)
            prior_claim = pilot._json_object(api.trees[prior["claim_commit"]][grading._paths(context.plan["cells"][ordinal])[0]])
            if ordinal == 26:
                prior["child"]["entry_invoked"] = False
            else:
                prior["binding"]["policy"] = ungraded.TASK5_C2_POLICY
            prior_claim["binding"] = prior["binding"]
            _rewrite(api, history, context, ordinal, prior, prior_claim)
            terminal = pilot._json_object(api.trees[revision][row.path])
            claim = pilot._json_object(api.trees[terminal["claim_commit"]][grading._paths(context.cell)[0]])
        elif change == "alias_terminal_backing_claim":
            revision = history.grades["B_r2"].terminal["claim_commit"]
        elif change == "alias_claim_a2_claim":
            terminal["claim_commit"] = history.a2_terminal["claim_commit"]
            api.writers[terminal["claim_commit"]][grading._paths(context.cell)[0]] = terminal["claim_commit"]
        a1._store_record(api, context.cell, revision, terminal, claim)
        api.writers[revision][row.path] = revision
        frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
        with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                match="model_free_task5_c2_chain_revision_changed" if change.startswith("alias_") else None):
            ungraded.verify_terminal(client, api.repo, revision, context, row.prepared["predecessor_entry"],
                grading._cache(tmp_path, "terminal"), token, deadline)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"ordinary_refused", "replay"}:
        shutil.copytree(row.root, current.root)
        if change == "ordinary_refused":
            prepared = retained._read(current.root / "prepared.json")
            prepared["judge_ready"] = True
            (current.root / "prepared.json").write_bytes(retained._encoded(prepared))
            for phase in ("claim", "judge", "publish", "reconcile"):
                assert successors._invoke(current, capsys, phase)[0] == 2
            with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                    match="model_free_terminal_not_judged"):
                grading._grade_terminal(client, api.repo, row.revision, context, row.prepared["predecessor_entry"],
                    grading._cache(tmp_path, "ordinary"), token, deadline)
        else:
            assert successors._invoke(current, capsys, "record-ungraded")[0] == 2
        assert api.events == [] and current.transport.calls == 0
        return

    overrides = {}
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
        else:
            terminal["publication_acknowledged"] = False
        api.trees[inference.terminal][inference.terminal_path] = retained._encoded(terminal)
    elif change in {"inference_run", "inference_attempt_type", "inference_predecessor", "c1_inference_predecessor"}:
        target = history.c1_inference if change == "c1_inference_predecessor" else inference
        claim = pilot._json_object(api.trees[target.claim][target.claim_path])
        if change == "inference_run":
            claim["binding"]["github_run"]["id"] = "991099"
        elif change == "inference_attempt_type":
            claim["binding"]["github_run"]["attempt"] = True
        else:
            claim["predecessor"]["manifest_sha256"] = "9" * 64
        terminal = pilot._json_object(api.trees[target.terminal][target.terminal_path])
        terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
        for tree in api.trees.values():
            if target.claim_path in tree:
                tree[target.claim_path] = retained._encoded(claim)
            if target.terminal_path in tree:
                tree[target.terminal_path] = retained._encoded(terminal)
        if change == "c1_inference_predecessor":
            # Keep C1's retained observation coherent so the new backing-equality
            # guard, rather than a stale grade hash, rejects the wrong link.
            prior = copy.deepcopy(history.c1.terminal)
            prior["binding"]["retained"]["terminal_sha256"] = pilot._identity(retained._encoded(terminal))["sha256"]
            prior_claim = copy.deepcopy(history.c1.admission["claim"])
            prior_claim["binding"] = prior["binding"]
            _rewrite(api, history, context, 26, prior, prior_claim)
    elif change in {"original_bytes", "private_payload"}:
        api.trees[inference.output][retained._paths(context.cell)[2] + "/step2_inference_results.json"] += (
            b" " if change == "original_bytes" else chain.PRIVATE.encode())
    elif change == "snapshot_hash":
        api.trees[api.branches[retained.BRANCH]][inference.terminal_path] += b" "
    elif change == "wrong_ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif change == "private_ref":
        api.private = False
    elif change in {"approval_missing", "approval_skipped", "approval_failed"}:
        if change == "approval_missing":
            monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
        else:
            monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped" if change == "approval_skipped" else "failure")
    elif change == "request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change == "source_spoof":
        monkeypatch.setenv("GITHUB_SHA", failed.PRODUCER)
    elif change == "producer_override":
        overrides["producer"] = chain.FOREIGN
    elif change == "wrong_completion":
        overrides["terminal"] = "9" * 64
    elif change in {"previous_missing", "previous_skipped", "previous_unfinished"}:
        api.branches[grading.BRANCH] = {"previous_missing": retained.BOOTSTRAP,
            "previous_skipped": history.b1_revision, "previous_unfinished": history.c1.terminal["claim_commit"]}[change]
    elif change == "alias_c1_terminal_b1_claim":
        alias = history.b1_terminal["claim_commit"]
        api.trees[alias], api.writers[alias] = copy.deepcopy(api.trees[history.c1.revision]), copy.deepcopy(api.writers[history.c1.revision])
        api.writers[alias][history.c1.path] = alias
        api.branches[grading.BRANCH] = alias
    elif change in PREDECESSOR_CASES and change != "controller":
        ordinal = 22 if change.startswith("backing_") else 25 if change.startswith("b1_") else 26
        cell, revision = (b1._records(history, context) + [(context.plan["cells"][26], history.c1.revision)])[ordinal - 22]
        path = grading._paths(cell)[1]
        terminal = pilot._json_object(api.trees[revision][path])
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][grading._paths(cell)[0]])
        if change in {"previous_type", "b1_type"}:
            terminal["format"] = ungraded.TERMINAL_FORMAT if ordinal == 26 else grading.RESULT_FORMAT
        elif change in {"previous_child", "backing_child"}:
            terminal["child"]["entry_invoked"] = False
        elif change in {"previous_cleanup", "backing_cleanup"}:
            terminal["child"]["cleanup_confirmed"] = False
        elif change == "previous_controller":
            terminal["binding"]["controller_source_sha"] = chain.FOREIGN
        elif change == "previous_source":
            terminal["binding"]["source_sha"] = chain.FOREIGN
        elif change in {"previous_hash", "backing_hash"}:
            terminal["binding"]["grader_source_hash"] = "0" * 64
        elif change == "previous_order":
            claim["predecessor"]["cell_id"] = grading.TASK5_A1_CELL
        elif change == "previous_receipt":
            terminal["binding"]["publication_receipt_sha256"] = "0" * 64
        elif change == "previous_observation":
            terminal["binding"]["retained"]["manifest_sha256"] = "0" * 64
        elif change == "previous_history":
            api.trees[terminal["claim_commit"]][history.b1_path] += b" "
        elif change == "b1_policy":
            terminal["binding"]["policy"] = ungraded.TASK5_C2_POLICY
        claim["binding"] = copy.deepcopy(terminal["binding"])
        if change == "previous_claim_type":
            claim["binding"]["github_run"]["attempt"] = True
        _rewrite(api, history, context, ordinal, terminal, claim)

    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
    if change in PREPARE_CASES:
        code, observed = successors._invoke(current, capsys, "prepare", **overrides)
        assert code == 2 and observed["outcome"] == "refused", (observed, current.diagnostic)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"controller", "inference_predecessor"}:
        code, observed = successors._invoke(current, capsys, "prepare")
        assert code == 0 and observed["model_free_record_ready"] is True, (observed, current.diagnostic)
    else:
        shutil.copytree(history.c2_prepared_root, current.root)
    if change == "resolution":
        path = current.root / "retained-resolution.json"
        value = retained._read(path)
        value["terminal_revision"] = history.c1_inference.terminal
        path.write_bytes(retained._encoded(value))
    elif change == "cas":
        api.move_before_commit = True
    elif change in {"claim_lost", "publication_lost"}:
        api.lost = "grade_claim" if change == "claim_lost" else "grade_output"
    elif change in {"claim_readback", "publication_readback"}:
        download = api.hf_hub_download

        def lost_readback(**kwargs):
            if kwargs["filename"] == grading._paths(context.cell)[0 if change == "claim_readback" else 1]:
                raise output.OutputPublicationRefused("hf_transport_failed")
            return download(**kwargs)

        api.hf_hub_download = lost_readback
    elif change in {"admission_cache", "admission_type", "admission_receipt_type", "publication_parent"}:
        write = grading._record

        def change_after_claim(path, value):
            write(path, value)
            if path.name == "model-free-claim-receipt.json" and value["outcome"] == "acknowledged":
                if change == "admission_cache":
                    cached = current.root / "model-free-claim-verified.json"
                    cached.write_bytes(cached.read_bytes() + b" ")
                elif change == "admission_type":
                    cached = current.root / "model-free-claim-reserved.json"
                    changed = retained._read(cached)
                    changed["github_run"]["attempt"] = True
                    cached.write_bytes(retained._encoded(changed))
                elif change == "admission_receipt_type":
                    changed = retained._read(path)
                    changed["claim"]["binding"]["github_run"]["attempt"] = True
                    path.write_bytes(retained._encoded(changed))
                else:
                    api.branches[grading.BRANCH] = history.b1_revision

        monkeypatch.setattr(grading, "_record", change_after_claim)
    elif change == "unapproved_record":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    code, observed = successors._invoke(current, capsys, "record-ungraded")
    assert code == 2, (observed, current.diagnostic)
    expected_calls = 2 if change in {"publication_lost", "publication_readback"} else 1 if change in {
        "cas", "claim_lost", "claim_readback", "admission_cache", "admission_type", "admission_receipt_type",
        "publication_parent"} else 0
    assert len(api.events) == expected_calls and current.transport.calls == 0
    if change in {"claim_lost", "publication_lost"}:
        assert observed["outcome"] == "unresolved"
    if change == "alias_c1_terminal_b1_claim":
        assert observed["reason"] == "model_free_task5_c2_chain_revision_changed"
    if change == "c1_inference_predecessor":
        assert observed["reason"] == "model_free_task5_c2_backing_changed"
    events = list(api.events)
    assert successors._invoke(current, capsys, "record-ungraded")[0] == 2
    assert api.events == events
    successors._unchanged(api, frozen)
