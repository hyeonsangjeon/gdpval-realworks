"""Ordinary task5 B2 after the fixed C2 UNGRADED proof, entirely offline.

The existing writers build one shared synthetic history; mutations are isolated
copies. Fixture payloads, terminal revisions, grade runs and numeric scores are
not reconstructions of live files, future records or quality observations.
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
from . import test_codex_budget_pilot_task5_failed_b1 as b1
from . import test_codex_budget_pilot_task5_failed_c2 as c2
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block live boundaries

CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_B_r2"
RECORDED = ("36266871064", "5b942d71fe284b5d2831c01cf17ac17e92857c26ef2dad820b9367d3c8cf0245")
CONFIG = "a6db185d3e6f5885ddf631d3c5e73c4062c6f2803be9ccf086605ed3394f6738"


def _select(history, api, directory, patch, *, controller=failed.FUTURE_CONTROLLER):
    context = grading.compile_request("pilot/" + CELL, controller, grading.TASK5_RETAINED[CELL][1],
                                      producer_source_sha=failed.PRODUCER)
    current = SimpleNamespace(api=api, context=context, workflow=history.workflow,
        root=directory / "private-grade", request=context.requested_terminal, inference=history.b2_inference)
    current.transport = policy._SourceOnlyChild(current)
    patch.setattr(base, "OUTPUT", current.inference.output)
    patch.setenv("HF_TOKEN", base.TOKEN)
    base._synthetic_rubric(current, patch)
    approval._authorize(current, directory, patch, "991028")  # Synthetic, not an issued grade run.
    return current


@pytest.fixture(scope="module")
def b2_history(tmp_path_factory):
    assert grading.TASK5_B2_CELL == CELL and grading.TASK5_RETAINED[CELL] == RECORDED
    prototype = grading.compile_request("pilot/" + CELL, failed.FUTURE_CONTROLLER, RECORDED[1],
                                        producer_source_sha=failed.PRODUCER)
    assert prototype.cell["config_sha256"] == CONFIG and prototype.plan["order"][28] == CELL
    histories = c2.c2_history.__wrapped__(tmp_path_factory)
    history = next(histories)  # Existing genuine writers, never previous test functions.
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("task5-b2-history")
            capture, api = chain._Capture(), copy.deepcopy(history.c2_after)
            previous = history.c2_inference
            claim_revision, output_revision, terminal_revision, snapshot = (
                f"{100_280 + i:040x}" for i in (1, 2, 3, 4))
            assert not {claim_revision, output_revision, terminal_revision, snapshot}.intersection(api.trees)
            context = grading.compile_request("pilot/" + CELL, failed.PRODUCER, terminal_revision)
            seeded = SimpleNamespace(context=context, api=api)
            with patch.context() as seed:
                for key, value in {"SOURCE": failed.PRODUCER, "CLAIM": claim_revision,
                                   "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                    seed.setattr(base, key, value)
                base._seed_outputs(seeded, directory, extra_deliverable=True)
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
            assert digest != RECORDED[1]  # Synthetic bytes, not the supplied live completion.
            patch.setitem(grading.TASK5_RETAINED, CELL, (RECORDED[0], digest))
            history.b2_inference = SimpleNamespace(context=context, claim=claim_revision, output=output_revision,
                terminal=terminal_revision, claim_path=claim_path, terminal_path=terminal_path, evidence=evidence)
            api.seed(snapshot, terminal_revision, {})  # No A2 result or binding is created.
            api.branches[retained.BRANCH] = snapshot
            api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
            history.b2_before = copy.deepcopy(api)
            current = _select(history, api, directory, patch)
            api.calls.clear()
            api.events.clear()
            frozen = copy.deepcopy((api.trees, api.writers, api.parents, snapshot))
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                code, observed = successors._invoke(current, capture, "prepare")
                assert code == 0 and observed["judge_ready"] is True, (observed, current.diagnostic)
                prepared = retained._read(current.root / "prepared.json")
                assert not prepared.get("model_free_record_ready") and "predecessor_entry" not in prepared
                assert {key: prepared["entry"][key] for key in (
                    "config_hash", "grader_source_hash", "renderer_fingerprint")} == history.c2.prepared["predecessor_entry"]
                history.b2_prepared_root = directory / "prepared-b2"
                shutil.copytree(current.root, history.b2_prepared_root)
                visits, ordinary_visits = [], []
                verify, ordinary = ungraded.verify_terminal, grading._grade_terminal

                def fixed_chain(*args, **kwargs):
                    visits.append(args[3].cell["cell_id"])
                    return verify(*args, **kwargs)

                def judged_backing(*args, **kwargs):
                    ordinary_visits.append(args[3].cell["cell_id"])
                    return ordinary(*args, **kwargs)

                with patch.context() as proving:
                    proving.setattr(ungraded, "verify_terminal", fixed_chain)
                    proving.setattr(grading, "_grade_terminal", judged_backing)
                    code, observed = successors._invoke(current, capture, "claim")
                    assert code == 0 and observed["outcome"] == "acknowledged", (observed, current.diagnostic)
                assert visits == [grading.TASK5_C2_CELL, grading.TASK5_B1_CELL,
                                  grading.TASK5_A1_CELL, grading.TASK4_A2_CELL]
                assert ordinary_visits == [grading.TASK5_C1_CELL, context.plan["order"][22]]
                for phase in ("judge", "publish"):
                    code, observed = successors._invoke(current, capture, phase)
                    assert code == 0, (phase, observed, current.diagnostic)
            assert api.events == ["grade_claim", "judge", "grade_output"] and current.transport.calls == 1
            successors._unchanged(api, frozen)
            revision, path = api.branches[grading.BRANCH], grading._paths(context.cell)[1]
            history.b2 = SimpleNamespace(revision=revision, path=path, root=current.root, prepared=prepared,
                terminal=pilot._json_object(api.trees[revision][path]),
                admission=retained._read(current.root / "claim-receipt.json"))
            history.b2_after = copy.deepcopy(api)
            yield history
    finally:
        histories.close()


PREPARE_CASES = ["inference_run", "inference_source", "inference_attempt_type", "completion", "inference_bytes",
    "inference_ack", "snapshot_hash", "wrong_ref", "private_ref", "approval_missing", "approval_skipped",
    "approval_failed", "approval_request", "rerun", "source_spoof", "producer_override", "wrong_completion"]
PREDECESSOR_CASES = ["previous_type", "previous_policy", "previous_score", "previous_claim_type",
    "previous_controller", "previous_source", "previous_config", "previous_grader", "previous_renderer",
    "previous_observation", "previous_receipt", "previous_order", "previous_cycle", "previous_hash",
    "previous_history", "previous_missing", "previous_skipped", "previous_unfinished", "previous_private",
    "c1_child", "c1_cleanup", "c1_type", "c1_source", "c1_hash", "b1_policy", "b1_type", "backing_child",
    "backing_cleanup", "backing_hash", "nonadjacent_alias", "controller_drift", "inference_predecessor",
    "c1_inference_predecessor"]
CLAIM_CASES = ["resolution", "cas", "claim_lost", "claim_readback", "unapproved_claim"]
ADMISSION_CASES = ["admission_cache", "admission_parent", "admission_type", "unapproved_judge"]
PUBLISH_CASES = ["publication_cas", "publication_parent", "publication_lost", "publication_readback",
    "cleanup", "raw_output", "unapproved_publish"]
TERMINAL_CASES = ["terminal_parent", "terminal_hash", "terminal_child", "terminal_cleanup", "terminal_type",
    "terminal_history", "terminal_exit_type"]
CASES = ["chain", "plan_workflow", "record_ungraded", "replay", "remote_replay"] + PREPARE_CASES + (
    PREDECESSOR_CASES + CLAIM_CASES + ADMISSION_CASES + PUBLISH_CASES + TERMINAL_CASES)


@pytest.mark.parametrize("change", CASES)
def test_successful_task5_b2_after_ungraded_c2(b2_history, tmp_path, monkeypatch, capsys, change):
    history, row = b2_history, b2_history.b2
    terminal_case = change in TERMINAL_CASES
    api = copy.deepcopy(history.b2_after if terminal_case or change in {"chain", "replay", "remote_replay"}
                        else history.b2_before)
    current = _select(history, api, tmp_path, monkeypatch,
        controller=chain.FOREIGN if change == "controller_drift" else failed.FUTURE_CONTROLLER)
    context, inference = current.context, current.inference
    api.calls.clear()
    api.events.clear()
    api.reads.clear()
    assert not grading._model_free_context(context) and grading._shared_controller_successor(context)
    assert context.cell["cell_id"] == context.plan["order"][28] == CELL

    if change == "chain":
        prepared, claim, terminal = row.prepared, row.admission["claim"], row.terminal
        assert claim["expected_parent"] == history.c2.revision
        assert claim["predecessor"] == {"cell_id": grading.TASK5_C2_CELL, "revision": history.c2.revision,
                                       **pilot._identity(retained._encoded(history.c2.terminal))}
        assert prepared["evidence"] == inference.evidence
        assert prepared["evidence"]["claim"]["predecessor"] == history.c2.terminal["binding"]["retained"]
        assert prepared["evidence"]["claim"]["binding"]["github_run"] == {"id": RECORDED[0], "job": "cell", "attempt": 1}
        assert prepared["terminal_revision"] == inference.terminal != api.branches[retained.BRANCH]
        assert prepared["judge_ready"] is True and "predecessor_entry" not in prepared and "rubric" in prepared
        assert {key: prepared["entry"][key] for key in history.c2.prepared["predecessor_entry"]} == (
            history.c2.prepared["predecessor_entry"])
        binding = terminal["binding"]
        assert binding["source_sha"] == failed.PRODUCER and binding["controller_source_sha"] == failed.FUTURE_CONTROLLER
        assert binding["github_run"] == {"id": "991028", "job": "pilot-live", "attempt": 1}
        assert binding["retained"] == inference.evidence["observation"]
        assert terminal["format"] == grading.RESULT_FORMAT and terminal["outcome"] == "graded"  # Synthetic only.
        assert terminal["child"]["entry_invoked"] is True and terminal["child"]["cleanup_confirmed"] is True
        assert terminal["invoice_complete"] is False and terminal["http_request_count"] is None
        assert history.c2.terminal["format"] == ungraded.TERMINAL_FORMAT
        assert history.c2.terminal["outcome"] == "ungraded" and history.c2.terminal["model_invoked"] is False
        assert history.c2.terminal["binding"]["policy"] == ungraded.TASK5_C2_POLICY
        assert history.c2.terminal["inference_completion"]["status"] == "failed"
        assert not {"child", "score", "verdict", "files"}.intersection(history.c2.terminal)
        assert history.c2.admission["claim"]["expected_parent"] == history.c1.revision
        assert history.c1.terminal["child"]["entry_invoked"] is True
        assert history.c1.admission["claim"]["expected_parent"] == history.b1_revision
        pairs = b1._records(history, context) + [(context.plan["cells"][26], history.c1.revision),
            (context.plan["cells"][27], history.c2.revision), (context.cell, row.revision)]
        revisions = [value for cell, revision in pairs for value in (
            revision, pilot._json_object(api.trees[revision][grading._paths(cell)[1]])["claim_commit"])]
        assert len(revisions) == len(set(revisions)) == 14
        context.terminal_revision = inference.terminal
        with retained._session(api) as (client, token, deadline):
            verified = grading._grade_terminal(client, api.repo, row.revision, context, prepared["entry"],
                grading._cache(tmp_path, "verified"), token, deadline)
        assert verified["terminal"] == terminal and api.events == [] and current.transport.calls == 0
        successors._unchanged(api, (history.b2_before.trees, history.b2_before.writers,
            history.b2_before.parents, history.b2_before.branches[retained.BRANCH]))
        return

    if change == "plan_workflow":
        assert context.plan["order"][24:29] == list(grading.TASK5_RETAINED) == [
            grading.TASK5_A1_CELL, grading.TASK5_B1_CELL, grading.TASK5_C1_CELL, grading.TASK5_C2_CELL, CELL]
        assert context.plan["order"][29:] == ["0818571f-5ff7-4d39-9d2c-ced5ae44299e_A_r2"]
        assert context.cell["config_sha256"] == CONFIG and len(context.plan["order"]) == 30
        for key in ("model", "dataset", "source_pins", "grading", "order"):
            assert context.plan[key] == pilot.compile_pilot(ci.CAMPAIGN, failed.PRODUCER)[0][key]
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        assert context.terminal_revision == "" and context.requested_terminal == grading.TASK5_RETAINED[CELL][1]
        for cell_id in context.plan["order"][29:]:
            assert cell_id not in grading.TASK5_RETAINED
            with pytest.raises(output.OutputPublicationRefused, match="closed_retained_producer_binding_required"):
                grading.compile_request("pilot/" + cell_id, failed.FUTURE_CONTROLLER, current.request,
                                        producer_source_sha=failed.PRODUCER)
        jobs = history.workflow["jobs"]
        live, approve, plan = jobs["pilot-live"], jobs["pilot-approve-paid"], jobs["pilot-plan"]
        expression = live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert expression == plan["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert all(expression.count('"pilot/' + cell_id + '"') == 1
                   for cell_id in [*grading.TASK4_RETAINED, *grading.TASK5_RETAINED])
        assert all('"pilot/' + cell_id + '"' not in expression for cell_id in context.plan["order"][29:])
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
        eligible = [grading.TASK4_A1_CELL, grading.TASK4_A2_CELL, grading.TASK5_A1_CELL,
                    grading.TASK5_B1_CELL, grading.TASK5_C2_CELL]
        assert [cell_id for cell_id in context.plan["order"] if grading._model_free_context(
            SimpleNamespace(cell={"cell_id": cell_id}, terminal_request=current.request))] == eligible
        recorder = phases["record-ungraded"]
        assert " ".join(recorder["if"].split()) == "(" + " || ".join(
            "inputs.experiment_yaml == 'pilot/" + cell_id + "'" for cell_id in eligible) + (
            ") && steps.pilot_input.outputs.model_free_record_ready == 'true' && "
            "steps.pilot_input.outputs.judge_ready == 'false'")
        assert all(cell_id not in recorder["if"] for cell_id in [grading.TASK5_C1_CELL, CELL, *context.plan["order"][29:]])
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
        assert grading._context_authority(context)["id"] == "991028"  # Actual approval digest, synthetic run.
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        assert successors._invoke(current, capsys)[0] == 0
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if change == "record_ungraded":
        code, observed = successors._invoke(current, capsys, "record-ungraded")
        assert code == 2 and observed["reason"] == "fixed_model_free_a1_required"
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if change == "replay":
        shutil.copytree(row.root, current.root)
        for phase in ("claim", "judge", "publish", "record-ungraded"):
            assert successors._invoke(current, capsys, phase)[0] == 2
        assert api.events == [] and current.transport.calls == 0
        return

    if terminal_case:
        terminal, claim = copy.deepcopy(row.terminal), copy.deepcopy(row.admission["claim"])
        if change == "terminal_parent":
            claim["expected_parent"] = claim["predecessor"]["revision"] = row.revision
        elif change == "terminal_hash":
            claim["predecessor"]["sha256"] = "9" * 64
        elif change == "terminal_child":
            terminal["child"]["entry_invoked"] = False
        elif change == "terminal_cleanup":
            terminal["child"]["cleanup_confirmed"] = False
        elif change == "terminal_type":
            terminal["format"] = ungraded.TERMINAL_FORMAT
        elif change == "terminal_exit_type":
            terminal["child"]["exit_code"] = False
        else:
            api.trees[terminal["claim_commit"]][history.c2.path] += b" "
        claim_data = retained._encoded(claim)
        claim_path = grading._paths(context.cell)[0]
        api.trees[terminal["claim_commit"]][claim_path] = api.trees[row.revision][claim_path] = claim_data
        terminal["claim_identity"] = pilot._identity(claim_data)
        api.trees[row.revision][row.path] = retained._encoded(terminal)
        context.terminal_revision = inference.terminal
        frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
        with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused):
            grading._grade_terminal(client, api.repo, row.revision, context, row.prepared["entry"],
                                    grading._cache(tmp_path, "terminal-refusal"), token, deadline)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    overrides = {}
    if change in {"inference_run", "inference_source", "inference_attempt_type", "inference_predecessor",
                  "c1_inference_predecessor"}:
        target = history.c1_inference if change == "c1_inference_predecessor" else inference
        claim = pilot._json_object(api.trees[target.claim][target.claim_path])
        if change == "inference_run":
            claim["binding"]["github_run"]["id"] = str(int(RECORDED[0]) + 1)
        elif change == "inference_source":
            claim["binding"]["source_sha"] = failed.FUTURE_CONTROLLER
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
            # Propagate valid hashes so the original inference-predecessor
            # equality, not an unrelated stale C1/C2 link, refuses this history.
            prior = copy.deepcopy(history.c1.terminal)
            prior["binding"]["retained"]["terminal_sha256"] = pilot._identity(retained._encoded(terminal))["sha256"]
            prior_claim = copy.deepcopy(history.c1.admission["claim"])
            prior_claim["binding"] = prior["binding"]
            c2._rewrite(api, history, context, 26, prior, prior_claim)
    elif change in {"completion", "inference_ack"}:
        terminal = pilot._json_object(api.trees[inference.terminal][inference.terminal_path])
        if change == "completion":
            terminal["completion"]["child_invocations"] = 2
        else:
            terminal["publication_acknowledged"] = False
        api.trees[inference.terminal][inference.terminal_path] = retained._encoded(terminal)
    elif change == "inference_bytes":
        api.trees[inference.output][retained._paths(context.cell)[2] + "/step2_inference_results.json"] += b"PRIVATE"
    elif change == "snapshot_hash":
        api.trees[api.branches[retained.BRANCH]][inference.terminal_path] += b" "
    elif change == "wrong_ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif change == "private_ref":
        api.private = False
    elif change == "approval_missing":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif change in {"approval_skipped", "approval_failed"}:
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped" if change == "approval_skipped" else "failure")
    elif change == "approval_request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "9" * 64)
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
            "previous_skipped": history.c1.revision, "previous_unfinished": history.c2.terminal["claim_commit"]}[change]
    elif change == "nonadjacent_alias":
        alias = history.grades["B_r2"].terminal["claim_commit"]
        api.trees[alias] = copy.deepcopy(api.trees[history.c2.revision])
        api.writers[alias] = {path: alias if writer == history.c2.revision else writer
                              for path, writer in api.writers[history.c2.revision].items()}
        api.branches[grading.BRANCH] = alias
    elif change in PREDECESSOR_CASES and change != "controller_drift":
        ordinal = 22 if change.startswith("backing_") else 25 if change.startswith("b1_") else (
            26 if change.startswith("c1_") else 27)
        pairs = b1._records(history, context) + [(context.plan["cells"][26], history.c1.revision),
                                                (context.plan["cells"][27], history.c2.revision)]
        cell, revision = pairs[ordinal - 22]
        path, claim_path = grading._paths(cell)[1], grading._paths(cell)[0]
        terminal = pilot._json_object(api.trees[revision][path])
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
        binding = terminal["binding"]
        if change in {"previous_type", "b1_type", "c1_type"}:
            terminal["format"] = ungraded.TERMINAL_FORMAT if ordinal == 26 else grading.RESULT_FORMAT
        elif change in {"previous_policy", "b1_policy"}:
            binding["policy"] = ungraded.TASK5_POLICY
        elif change == "previous_score":
            terminal["score"] = 0
        elif change == "previous_private":
            terminal["debug"] = chain.PRIVATE
        elif change == "previous_claim_type":
            claim["binding"]["github_run"]["attempt"] = True
        elif change == "previous_controller":
            binding["controller_source_sha"] = chain.FOREIGN
            binding["approval_request_sha256"] = grading._approval_request_sha256(chain.FOREIGN, "pilot/" + cell["cell_id"],
                grading.TASK5_RETAINED[cell["cell_id"]][1], binding["github_run"], producer_source_sha=failed.PRODUCER)
        elif change in {"previous_source", "c1_source"}:
            binding["source_sha"] = chain.FOREIGN
        elif change == "previous_config":
            binding["predecessor_entry"]["config_hash"] = "9" * 64
        elif change == "previous_grader":
            binding["predecessor_entry"]["grader_source_hash"] = "9" * 64
        elif change in {"c1_hash", "backing_hash"}:
            binding["grader_source_hash"] = "9" * 64
        elif change == "previous_renderer":
            assert binding["predecessor_entry"]["renderer_fingerprint"] is not None
            binding["predecessor_entry"]["renderer_fingerprint"] = None
        elif change == "previous_observation":
            binding["retained"]["manifest_sha256"] = "9" * 64
        elif change == "previous_receipt":
            binding["publication_receipt_sha256"] = "9" * 64
        elif change == "previous_order":
            claim["predecessor"]["cell_id"] = grading.TASK5_B1_CELL
        elif change == "previous_cycle":
            claim["expected_parent"] = claim["predecessor"]["revision"] = revision
        elif change == "previous_hash":
            claim["predecessor"]["sha256"] = "9" * 64
        elif change == "previous_history":
            api.trees[terminal["claim_commit"]][history.c1.path] += b" "
        elif change in {"c1_child", "backing_child"}:
            terminal["child"]["entry_invoked"] = False
        elif change in {"c1_cleanup", "backing_cleanup"}:
            terminal["child"]["cleanup_confirmed"] = False
        if change != "previous_claim_type":
            claim["binding"] = binding
        c2._rewrite(api, history, context, ordinal, terminal, claim)

    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
    if change in PREPARE_CASES:
        code, observed = successors._invoke(current, capsys, "prepare", **overrides)
        assert code == 2 and observed["outcome"] == "refused", (observed, current.diagnostic)
        successors._unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"controller_drift", "inference_predecessor"}:
        code, observed = successors._invoke(current, capsys, "prepare")
        assert code == 0 and observed["judge_ready"] is True, (observed, current.diagnostic)
    else:
        shutil.copytree(history.b2_prepared_root, current.root)
    if change == "resolution":
        path = current.root / "retained-resolution.json"
        value = retained._read(path)
        value["terminal_revision"] = history.c2_inference.terminal
        path.write_bytes(retained._encoded(value))
    elif change == "cas":
        api.move_before_commit = True
    elif change == "claim_lost":
        api.lost = "grade_claim"
    elif change == "unapproved_claim":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif change == "claim_readback":
        download = api.hf_hub_download

        def lost_claim(**kwargs):
            if kwargs["filename"] == grading._paths(context.cell)[0]:
                raise output.OutputPublicationRefused("hf_transport_failed")
            return download(**kwargs)

        api.hf_hub_download = lost_claim
    code, observed = successors._invoke(current, capsys, "claim")
    if change in PREDECESSOR_CASES + CLAIM_CASES + ["remote_replay"]:
        assert code == 2 and observed["outcome"] in {"refused", "unresolved"}, (observed, current.diagnostic)
        if change == "inference_predecessor":
            assert observed["reason"] == "recorded_task2_inference_predecessor_mismatch"
        if change == "nonadjacent_alias":
            assert observed["reason"] == "model_free_task5_c2_chain_revision_changed"
        if change in {"claim_lost", "claim_readback"}:
            assert observed["outcome"] == "unresolved"
        events = list(api.events)
        assert events == (["grade_claim"] if change in {"cas", "claim_lost", "claim_readback"} else [])
        for phase in ("judge", "claim", "publish"):
            assert successors._invoke(current, capsys, phase)[0] == 2
        successors._unchanged(api, frozen)
        assert api.events == events and current.transport.calls == 0
        return
    assert code == 0 and observed["outcome"] == "acknowledged", (observed, current.diagnostic)
    receipt_path = current.root / "claim-receipt.json"
    receipt = retained._read(receipt_path)
    assert receipt["claim"]["expected_parent"] == history.c2.revision
    if change in ADMISSION_CASES:
        if change == "admission_cache":
            cached = current.root / "claim-verified" / (receipt["returned_commit"] + ".json")
            cached.write_bytes(cached.read_bytes() + b" ")
        elif change == "unapproved_judge":
            monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
        else:
            if change == "admission_parent":
                receipt["claim"]["expected_parent"] = receipt["claim"]["predecessor"]["revision"] = history.c1.revision
            else:
                receipt["claim"]["binding"]["github_run"]["attempt"] = True
            receipt["claim_identity"] = pilot._identity(retained._encoded(receipt["claim"]))
            receipt_path.write_bytes(retained._encoded(receipt))
        reads = list(api.reads)
        assert successors._invoke(current, capsys, "judge")[0] == 2
        successors._unchanged(api, frozen)
        assert api.events == ["grade_claim"] and api.reads == reads and current.transport.calls == 0
        return

    assert change in PUBLISH_CASES
    if change == "cleanup":
        current.transport.mode = "cleanup_lost"
    code, observed = successors._invoke(current, capsys, "judge")
    if change == "cleanup":
        assert code == 2 and observed["outcome"] == "unresolved" and observed["stage"] == "judge"
        child = retained._read(current.root / "judge-receipt.json")
        assert child["entry_invoked"] is True and child["cleanup_confirmed"] is False
    else:
        assert code == 0
    if change == "publication_cas":
        api.move_before_commit = True
    elif change == "publication_parent":
        api.branches[grading.BRANCH] = history.c2.revision
    elif change == "publication_lost":
        api.lost = "grade_output"
    elif change == "publication_readback":
        download = api.hf_hub_download

        def lost_terminal(**kwargs):
            if kwargs["filename"] == grading._paths(context.cell)[1]:
                raise output.OutputPublicationRefused("hf_transport_failed")
            return download(**kwargs)

        api.hf_hub_download = lost_terminal
    elif change == "raw_output":
        path = current.root / "source" / row.prepared["entry"]["grade_path"]
        payload = pilot._json_object(path.read_bytes())
        payload["judge_raw_response"] = chain.PRIVATE
        path.write_bytes(base._json(payload))
    elif change == "unapproved_publish":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    code, observed = successors._invoke(current, capsys, "publish")
    assert code == 2 and observed["outcome"] in {"refused", "unresolved"}, (observed, current.diagnostic)
    if change == "cleanup":
        assert observed["reason"] == "grade_cleanup_unconfirmed"
    if change in {"publication_lost", "publication_readback"}:
        assert observed["outcome"] == "unresolved"
    events = list(api.events)
    assert events == ["grade_claim", "judge"] + (["grade_output"] if change in {
        "publication_cas", "publication_lost", "publication_readback"} else [])
    assert successors._invoke(current, capsys, "publish")[0] == successors._invoke(current, capsys, "judge")[0] == 2
    successors._unchanged(api, frozen)
    assert api.events == events and current.transport.calls == 1
