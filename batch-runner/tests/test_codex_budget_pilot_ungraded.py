"""One synthetic task3 A2 -> model-free failed A1 -> judged B1 history.

No live payload, terminal SHA or future grading run is reconstructed. The real
native-error producer/serializer, materializer and immutable/CAS helpers operate
behind blocked external boundaries. Mutations copy the shared history only.
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
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary


class _SourceOnlyChild(base.Child):
    def verify_checkout(self, destination, sha):
        # Git/source ownership is the same isolated boundary as base.Child.
        assert sha == self.case.context.controller_source_sha
        assert (destination / "batch-runner/step8_grade.py").is_file()


def _select(history, suffix, api, directory, patch, *, controller=failed.FUTURE_CONTROLLER):
    cell_id = failed.PREFIX + suffix
    context = grading.compile_request("pilot/" + cell_id, controller, grading.TASK4_RETAINED[cell_id][1],
                                      producer_source_sha=failed.PRODUCER)
    current = SimpleNamespace(api=api, context=context, root=directory / "private-grade", workflow=history.workflow,
                              request=context.requested_terminal)
    current.transport = _SourceOnlyChild(current)
    patch.setattr(base, "OUTPUT", history.rows[suffix].output)
    patch.setenv("HF_TOKEN", base.TOKEN)
    base._synthetic_rubric(current, patch)
    approval._authorize(current, directory, patch, "991018" if suffix == "A_r1" else "991019")
    return current


def _invoke(current, capture, phase="plan", **changes):
    return base.invoke(current, capture, phase, **{"terminal": current.request, **changes})


@pytest.fixture(scope="module")
def recorded_pair(tmp_path_factory):
    assert grading.TASK4_RETAINED == {failed.PREFIX + suffix: row for suffix, row in failed.RECORDED.items()}
    history_generator = failed.failed_pair.__wrapped__(tmp_path_factory)
    history = next(history_generator)
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("model-free-shared-history")
            capture = chain._Capture()
            for suffix, row in history.rows.items():
                patch.setitem(grading.TASK4_RETAINED, failed.PREFIX + suffix,
                    (failed.RECORDED[suffix][0], pilot._digest(row.evidence["terminal"]["completion"])))
            api = copy.deepcopy(history.api)
            history.before_a1 = copy.deepcopy(api)
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                a1_dir = directory / "a1"
                a1_dir.mkdir()
                a1 = _select(history, "A_r1", api, a1_dir, patch)
                api.events.clear()
                api.calls.clear()
                with patch.context() as no_judge:
                    def forbidden(*args, **kwargs):
                        raise AssertionError("model-free A1 reached a judge/rubric entry")
                    no_judge.setattr(grading, "_entry_contract", forbidden)
                    no_judge.setattr(grading, "_stage_rubric", forbidden)
                    no_judge.setattr(a1.transport, "process", forbidden)
                    code, observed = _invoke(a1, capture, "prepare")
                    assert code == 0, (observed, a1.diagnostic)
                    history.prepared = retained._read(a1.root / "prepared.json")
                    history.prepared_root = directory / "prepared-a1"
                    shutil.copytree(a1.root, history.prepared_root)
                    code, observed = _invoke(a1, capture, "record-ungraded")
                    assert code == 0, (observed, a1.diagnostic)
                assert api.events == ["grade_claim", "grade_output"] and a1.transport.calls == 0
                history.a1_receipt = retained._read(a1.root / "model-free-publication-receipt.json")
                history.a1_admission = retained._read(a1.root / "model-free-claim-receipt.json")
                history.a1_revision = api.branches[grading.BRANCH]
                history.a1_path = grading._paths(a1.context.cell)[1]
                history.a1_terminal = pilot._json_object(api.trees[history.a1_revision][history.a1_path])
                history.a1_root = a1.root
                history.after_a1 = copy.deepcopy(api)
                b1_dir = directory / "b1"
                b1_dir.mkdir()
                b1 = _select(history, "B_r1", api, b1_dir, patch)
                api.events.clear()
                for phase in ("prepare", "claim", "judge", "publish"):
                    code, observed = _invoke(b1, capture, phase)
                    assert code == 0, (phase, observed, b1.diagnostic)
                assert api.events == ["grade_claim", "judge", "grade_output"] and b1.transport.calls == 1
                history.b1_prepared = retained._read(b1.root / "prepared.json")
                history.b1_admission = retained._read(b1.root / "claim-receipt.json")
                history.b1_revision = api.branches[grading.BRANCH]
                history.b1_path = grading._paths(b1.context.cell)[1]
                history.b1_terminal = pilot._json_object(api.trees[history.b1_revision][history.b1_path])
                history.after_b1 = copy.deepcopy(api)
            yield history
    finally:
        history_generator.close()


@pytest.mark.parametrize("change", [
    "chain", "plan", "workflow", "legacy_closed_a1", "legacy_closed_b1",
    "success", "exit", "reason", "child_count", "cleanup", "timeout", "deliverables",
    "source", "inference_run", "completion", "original_bytes", "private_result", "inference_ack",
    "approval", "request", "rerun", "controller", "wrong_ref", "previous_missing", "previous_controller",
    "previous_hash", "previous_ungraded_no_child", "resolution", "materialized_bytes", "readiness", "predecessor_source",
    "cas", "claim_lost", "publication_lost", "claim_readback", "admission_cache", "publication_parent",
    "terminal_type", "terminal_score", "terminal_child", "terminal_receipt", "terminal_controller", "terminal_boolean",
    "terminal_parent", "terminal_previous_hash", "terminal_history", "b1_missing", "b1_observation",
    "replay", "ordinary_refused",
])
def test_fixed_failed_a1_no_judge_policy(recorded_pair, tmp_path, monkeypatch, capsys, change):
    history = recorded_pair
    if change.startswith("legacy_closed_"):
        failed.test_failed_task4_a1_grading_policy_gap(history, tmp_path, monkeypatch, capsys,
                                                      change.removeprefix("legacy_"))
        return
    terminal_case = change.startswith("terminal_") or change in {"b1_missing", "b1_observation"}
    api = copy.deepcopy(history.after_a1 if terminal_case or change in {"chain", "ordinary_refused", "replay"}
                        else history.before_a1)
    selected = "B_r1" if terminal_case else "A_r1"
    current = _select(history, selected, api, tmp_path, monkeypatch,
                      controller="e" * 40 if change == "controller" else failed.FUTURE_CONTROLLER)
    context = current.context
    api.events.clear()
    api.calls.clear()
    api.reads.clear()
    old = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))

    if change == "chain":
        terminal, prepared = history.a1_terminal, history.prepared
        assert terminal["format"] == ungraded.TERMINAL_FORMAT and terminal["outcome"] == "ungraded"
        assert terminal["model_invoked"] is False and not {"child", "files", "score", "verdict"}.intersection(terminal)
        assert terminal["inference_completion"] == history.rows["A_r1"].evidence["terminal"]["completion"]
        assert terminal["inference_completion"]["status"] == "failed"
        assert terminal["inference_completion"]["denominator"] == 30
        assert terminal["inference_completion"]["receipt"] == prepared["evidence"]["terminal"]["completion"]["receipt"]
        assert terminal["recorder_accounting"] == {"status": "not_measured", "known_cost_usd": None,
            "estimated_cost_usd": None, "invoice_complete": False, "http_request_count": None}
        assert prepared["model_free_record_ready"] is True and prepared["judge_ready"] is False
        assert "entry" not in prepared and "rubric" not in prepared
        assert history.a1_admission["claim"]["predecessor"]["cell_id"] == failed.PREVIOUS
        assert history.b1_admission["claim"]["predecessor"] == {
            "cell_id": grading.TASK4_A1_CELL, "revision": history.a1_revision,
            **pilot._identity(retained._encoded(terminal))}
        assert history.b1_terminal["format"] == grading.RESULT_FORMAT
        assert history.b1_terminal["child"]["entry_invoked"] is True
        assert history.b1_prepared["evidence"]["claim"]["predecessor"] == terminal["binding"]["retained"]
        for revision, data in history.before_a1.trees.items():
            assert history.after_b1.trees[revision] == data
            assert history.after_b1.writers[revision] == history.before_a1.writers[revision]
        assert history.after_b1.branches[retained.BRANCH] == history.before_a1.branches[retained.BRANCH]
        return
    if change == "plan":
        assert context.plan["order"][18:20] == list(grading.TASK4_RETAINED)
        assert len(context.plan["order"]) == 30
        assert context.controller_source_sha != context.plan["reviewed_source_sha"] == failed.PRODUCER
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert context.plan["model"]["deployment"] == "gpt-5.4" and context.plan["model"]["route_profile"] == "direct-v1"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        for cell_id in context.plan["order"][20:]:
            with pytest.raises(output.OutputPublicationRefused):
                grading.compile_request("pilot/" + cell_id, failed.FUTURE_CONTROLLER, current.request,
                                        producer_source_sha=failed.PRODUCER)
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        assert _invoke(current, capsys)[0] == 0
        assert not current.root.exists() and api.calls == []
        return
    if change == "workflow":
        jobs = history.workflow["jobs"]
        steps = {step["name"]: step for step in jobs["pilot-live"]["steps"] if "name" in step}
        record_step = steps["Record only the verified failed task4 A1 without a judge"]
        assert "'pilot/" + grading.TASK4_A1_CELL + "'" in record_step["if"]
        assert "model_free_record_ready == 'true'" in record_step["if"]
        assert "judge_ready == 'false'" in record_step["if"]
        assert "--phase record-ungraded" in record_step["run"] and set(record_step["env"]) == {"HF_TOKEN"}
        for name in ("Validate grading OIDC identity", "Validate fixed grader Azure route", "Grading Azure login (OIDC)",
                     "Verify grading OIDC session", "Verify fixed grader model connection", "Claim one private grading admission with parent CAS",
                     "Invoke exactly the compiled fixed Step8 command once"):
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in steps[name]["if"]
        assert "steps.pilot_judge.outcome != 'skipped'" in steps["Retain validated private grade and accounting on the grading branch"]["if"]
        expression = jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == expression
        assert all(expression.count('"pilot/' + cell_id + '"') == 1 for cell_id in grading.TASK4_RETAINED)
        assert all('"pilot/' + cell_id + '"' not in expression for cell_id in context.plan["order"][20:])
        assert jobs["pilot-live"]["needs"] == ["pilot-approve-paid"] and "environment" not in jobs["pilot-live"]
        assert jobs["pilot-live"]["permissions"] == {"contents": "read", "id-token": "write"}
        assert jobs["pilot-approve-paid"]["permissions"] == {} and len(jobs["pilot-approve-paid"]["steps"]) == 1
        assert jobs["pilot-approve-paid"]["environment"] == {"name": "grading"}
        # _select executed this actual inline approval digest, not its connector helper.
        assert grading._context_authority(context)["id"] == "991018"
        return

    if terminal_case:
        terminal = copy.deepcopy(history.a1_terminal)
        claim_revision = terminal["claim_commit"]
        claim_path = grading._paths(history.rows["A_r1"].context.cell)[0]
        claim = pilot._json_object(api.trees[claim_revision][claim_path])
        if change == "terminal_type":
            terminal["format"] = grading.RESULT_FORMAT
        elif change == "terminal_score":
            terminal["score"] = 0
        elif change == "terminal_child":
            terminal["child"] = {"entry_invoked": True, "exit_code": 0, "cleanup_confirmed": True}
        elif change == "terminal_receipt":
            terminal["inference_completion"]["receipt"] = None
        elif change == "terminal_controller":
            terminal["binding"]["controller_source_sha"] = "e" * 40
        elif change == "terminal_boolean":
            terminal["inference_completion"]["exit_code"] = True
        elif change in {"terminal_parent", "terminal_previous_hash"}:
            if change == "terminal_parent":
                claim["expected_parent"] = retained.BOOTSTRAP
                claim["predecessor"]["revision"] = retained.BOOTSTRAP
            else:
                claim["predecessor"]["sha256"] = "0" * 64
            claim_bytes = retained._encoded(claim)
            for revision in (claim_revision, history.a1_revision):
                api.trees[revision][claim_path] = claim_bytes
            terminal["claim_identity"] = pilot._identity(claim_bytes)
        elif change == "terminal_history":
            previous_path = grading._paths(context.plan["cells"][17])[1]
            api.trees[claim_revision][previous_path] += b" "
        elif change == "b1_missing":
            api.branches[grading.BRANCH] = history.a1_admission["returned_commit"]
        elif change == "b1_observation":
            terminal["binding"]["retained"]["manifest_sha256"] = "0" * 64
        api.trees[history.a1_revision][history.a1_path] = retained._encoded(terminal)
        assert _invoke(current, capsys, "prepare")[0] == 0
        before = len(api.events)
        code, observed = _invoke(current, capsys, "claim")
        assert code == 2, (observed, current.diagnostic)
        assert len(api.events) == before and current.transport.calls == 0
        return

    if change in {"ordinary_refused", "replay"}:
        shutil.copytree(history.a1_root, current.root)
        if change == "ordinary_refused":
            prepared = retained._read(current.root / "prepared.json")
            prepared["judge_ready"] = True  # Even edited readiness must never route A1 to Step8.
            (current.root / "prepared.json").write_bytes(retained._encoded(prepared))
            for phase in ("claim", "judge", "publish", "reconcile"):
                assert _invoke(current, capsys, phase)[0] == 2
            context.terminal_revision = history.rows["A_r1"].terminal
            with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                    match="model_free_terminal_not_judged"):
                grading._grade_terminal(client, api.repo, history.a1_revision, context, history.prepared["predecessor_entry"],
                                        grading._cache(tmp_path, "ordinary"), token, deadline)
        else:
            assert _invoke(current, capsys, "record-ungraded")[0] == 2
        assert api.events == [] and current.transport.calls == 0
        return

    inference = history.rows["A_r1"]
    if change in {"success", "exit", "reason", "child_count", "cleanup", "timeout", "deliverables",
                  "source", "completion", "inference_ack"}:
        terminal = copy.deepcopy(inference.evidence["terminal"])
        key, value = {"success": ("status", "succeeded"), "exit": ("exit_code", 0),
            "reason": ("reason", None), "child_count": ("child_invocations", 2), "cleanup": ("cleanup_confirmed", False),
            "timeout": ("timeout", True), "source": ("source_sha", "e" * 40),
            "completion": ("config_sha256", "0" * 64)}.get(change, (None, None))
        if key:
            terminal["completion"][key] = value
        elif change == "deliverables":
            terminal["completion"]["artifacts"]["deliverables"] = [{"size": 1, "sha256": "0" * 64}]
        else:
            terminal["publication_acknowledged"] = False
        api.trees[inference.terminal][inference.terminal_path] = retained._encoded(terminal)
    elif change == "inference_run":
        claim = copy.deepcopy(inference.evidence["claim"])
        claim["binding"]["github_run"]["id"] = "991099"
        api.trees[inference.claim][inference.claim_path] = retained._encoded(claim)
    elif change in {"original_bytes", "private_result"}:
        path = retained._paths(context.cell)[2] + "/step2_inference_results.json"
        api.trees[inference.output][path] += b" " if change == "original_bytes" else b'PRIVATE prompt'
    elif change == "wrong_ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif change == "approval":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped")
    elif change == "request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change in {"previous_missing", "previous_controller", "previous_hash", "previous_ungraded_no_child"}:
        previous_revision = history.a1_admission["claim"]["expected_parent"]
        previous_path = grading._paths(context.plan["cells"][17])[1]
        if change == "previous_missing":
            api.branches[grading.BRANCH] = retained.BOOTSTRAP
        elif change == "previous_hash":
            api.trees[previous_revision][previous_path] += b" "
        else:
            value = pilot._json_object(api.trees[previous_revision][previous_path])
            if change == "previous_controller":
                value["binding"]["controller_source_sha"] = "e" * 40
            else:
                value["outcome"] = "ungraded"
                value["child"]["entry_invoked"] = False
            api.trees[previous_revision][previous_path] = retained._encoded(value)

    early = {"success", "exit", "reason", "child_count", "cleanup", "timeout", "deliverables", "source", "inference_run",
             "completion", "original_bytes", "private_result", "inference_ack", "approval", "request", "rerun", "wrong_ref"}
    if change in early:
        code, observed = _invoke(current, capsys, "prepare")
        assert code == 2, (observed, current.diagnostic)
        assert api.events == [] and current.transport.calls == 0
        return

    shutil.copytree(history.prepared_root, current.root)
    if change in {"resolution", "readiness", "predecessor_source"}:
        path = current.root / ("retained-resolution.json" if change == "resolution" else "prepared.json")
        value = retained._read(path)
        if change == "resolution":
            value["terminal_revision"] = "0" * 40
        elif change == "readiness":
            value["judge_ready"] = True
        else:
            value["predecessor_entry"]["grader_source_hash"] = "0" * 64
        path.write_bytes(retained._encoded(value))
    elif change == "materialized_bytes":
        path = current.root / "inputs" / context.run.inference_results_path
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "cas":
        api.move_before_commit = True
    elif change in {"claim_lost", "publication_lost"}:
        api.lost = "grade_claim" if change == "claim_lost" else "grade_output"
    elif change == "claim_readback":
        download = api.hf_hub_download
        def bad_readback(**kwargs):
            if kwargs["filename"] == grading._paths(context.cell)[0]:
                raise output.OutputPublicationRefused("hf_transport_failed")
            return download(**kwargs)
        api.hf_hub_download = bad_readback
    elif change in {"admission_cache", "publication_parent"}:
        write = grading._record
        def change_after_claim(path, value):
            write(path, value)
            if path.name == "model-free-claim-receipt.json" and value["outcome"] == "acknowledged":
                if change == "admission_cache":
                    cached = current.root / "model-free-claim-verified.json"
                    cached.write_bytes(cached.read_bytes() + b" ")
                else:
                    api.branches[grading.BRANCH] = retained.BOOTSTRAP
        monkeypatch.setattr(grading, "_record", change_after_claim)
    code, observed = _invoke(current, capsys, "record-ungraded")
    assert code == 2, (observed, current.diagnostic)
    assert current.transport.calls == 0
    expected_calls = (2 if change == "publication_lost" else 1 if change in {
        "cas", "claim_lost", "claim_readback", "admission_cache", "publication_parent"} else 0)
    assert len(api.events) == expected_calls
    before = list(api.events)
    assert _invoke(current, capsys, "record-ungraded")[0] == 2
    assert api.events == before  # Ambiguity consumes the attempt; it never retries.
    for revision, data in old[0].items():
        if change not in {"previous_controller", "previous_hash", "previous_ungraded_no_child"}:
            assert api.trees[revision] == data and api.writers[revision] == old[1][revision]
    assert api.branches[retained.BRANCH] == old[3]
