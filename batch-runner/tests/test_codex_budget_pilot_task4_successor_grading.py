"""One synthetic failed-A1 -> judged B1/C1/C2/B2 history, isolated mutations.

The existing writers produce the no-judge record and ordinary grade artifacts;
only external boundaries are fake. Synthetic bytes, revisions and grade runs
are not reconstructions of the recorded deliverables or private terminal SHAs.
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
from . import test_codex_budget_pilot_ungraded as policy
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — block every live boundary

RECORDED = {
    "C_r1": ("36239016015", "76c1904cfbed0588f5fcb6c15f48f66cd065933a8c829cbd18fcfb323f8ab710"),
    "C_r2": ("36242339639", "817d2515c4719b7f12b40c5c58e446661e2e41fd5d8023a78045208548e4dcbd"),
    "B_r2": ("36243795189", "ec4221834b04014e58775a4a4d94fc139e49ad2b7b45321e7fd2ccd58d75ef41"),
}
SEQUENCE = (*failed.RECORDED, *RECORDED)
FOREIGN = "e" * 40


def _select(history, suffix, api, directory, patch, *, controller=failed.FUTURE_CONTROLLER):
    cell_id = failed.PREFIX + suffix
    context = grading.compile_request("pilot/" + cell_id, controller, grading.TASK4_RETAINED[cell_id][1],
                                      producer_source_sha=failed.PRODUCER)
    current = SimpleNamespace(api=api, context=context, workflow=history.workflow,
        root=directory / "private-grade", request=context.requested_terminal, inference=history.inferences[suffix])
    current.transport = policy._SourceOnlyChild(current)
    patch.setattr(base, "OUTPUT", current.inference.output)
    patch.setenv("HF_TOKEN", base.TOKEN)
    base._synthetic_rubric(current, patch)
    # Explicit fixture-only grade runs, not future issued IDs. This executes
    # the actual protected-approval workflow digest independently of its helper.
    approval._authorize(current, directory, patch, str(991000 + context.plan["order"].index(cell_id)))
    return current


def _invoke(current, capture, phase="plan", **changes):
    code, public = base.invoke(current, capture, phase, **{"terminal": current.request, **changes})
    assert "PRIVATE" not in json.dumps(public)
    return code, public


def _unchanged(api, frozen):
    trees, writers, parents, inference_tip = frozen
    assert all(api.trees[revision] == data for revision, data in trees.items())
    assert all(api.writers[revision] == data for revision, data in writers.items())
    assert all(api.parents[revision] == parent for revision, parent in parents.items())
    assert api.branches[retained.BRANCH] == inference_tip
    assert not any(name == "branch" or (name == "commit" and revision != grading.BRANCH)
                   for name, revision in api.calls)


@pytest.fixture(scope="module")
def successor_history(tmp_path_factory):
    assert grading.TASK4_RETAINED == {
        failed.PREFIX + suffix: row for suffix, row in {**failed.RECORDED, **RECORDED}.items()}
    histories = policy.recorded_pair.__wrapped__(tmp_path_factory)
    pair = next(histories)  # Genuine failed A1 recorder then ordinary B1, built only once.
    try:
        with pytest.MonkeyPatch.context() as patch:
            directory = tmp_path_factory.mktemp("task4-successor-history")
            capture, api = chain._Capture(), copy.deepcopy(pair.after_b1)
            history = SimpleNamespace(workflow=pair.workflow, pair=pair, inferences=dict(pair.rows), grades={
                "A_r1": SimpleNamespace(revision=pair.a1_revision, path=pair.a1_path, terminal=pair.a1_terminal),
                "B_r1": SimpleNamespace(revision=pair.b1_revision, path=pair.b1_path, terminal=pair.b1_terminal),
            })
            original = copy.deepcopy((api.trees, api.writers, api.parents))
            previous, evidence = pair.rows["B_r1"].terminal, pair.rows["B_r1"].evidence
            with redirect_stdout(capture.out), redirect_stderr(capture.err):
                for ordinal, suffix in enumerate(RECORDED, 20):
                    claim_revision, output_revision, terminal_revision = (
                        f"{70_000 + ordinal * 10 + offset:040x}" for offset in (1, 2, 3))
                    assert not {claim_revision, output_revision, terminal_revision}.intersection(api.trees)
                    context = grading.compile_request("pilot/" + failed.PREFIX + suffix,
                                                      failed.PRODUCER, terminal_revision)
                    seeded = SimpleNamespace(context=context, api=api)
                    with patch.context() as seed:
                        for key, value in {"SOURCE": failed.PRODUCER, "CLAIM": claim_revision,
                                           "OUTPUT": output_revision, "TERMINAL": terminal_revision}.items():
                            seed.setattr(base, key, value)
                        base._seed_outputs(seeded, directory, extra_deliverable=True)
                    claim_path, terminal_path, prefix = retained._paths(context.cell)
                    # Replace the writer fixture's bootstrap scaffold before
                    # verification with the complete actual synthetic predecessor.
                    seeded.claim["binding"]["github_run"] = {"id": RECORDED[suffix][0], "job": "cell", "attempt": 1}
                    seeded.claim["expected_parent"] = previous
                    seeded.claim["predecessor"] = evidence["observation"]
                    seeded.terminal["claim_identity"] = pilot._identity(retained._encoded(seeded.claim))
                    files = {name: data for name, data in api.trees[output_revision].items()
                             if name.startswith(prefix + "/")}
                    api.seed(claim_revision, previous, {claim_path: retained._encoded(seeded.claim)})
                    api.seed(output_revision, claim_revision, files)
                    api.seed(terminal_revision, output_revision, {terminal_path: retained._encoded(seeded.terminal)})
                    patch.setenv("HF_TOKEN", base.TOKEN)
                    with retained._session(api) as (client, token, deadline):
                        evidence = grading._retained_input(context, client, api.repo,
                            grading._cache(directory, suffix), token, deadline)
                    digest = pilot._digest(evidence["terminal"]["completion"])
                    assert digest != RECORDED[suffix][1]
                    patch.setitem(grading.TASK4_RETAINED, failed.PREFIX + suffix, (RECORDED[suffix][0], digest))
                    history.inferences[suffix] = SimpleNamespace(context=context, claim=claim_revision,
                        output=output_revision, terminal=terminal_revision, claim_path=claim_path,
                        terminal_path=terminal_path, evidence=evidence)
                    previous = terminal_revision
                assert all(api.trees[revision] == data for revision, data in original[0].items())
                assert all(api.writers[revision] == data for revision, data in original[1].items())
                assert all(api.parents[revision] == parent for revision, parent in original[2].items())
                api.branches[retained.BRANCH] = previous  # Earlier cells resolve behind this advanced ref.
                api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
                for suffix in RECORDED:
                    local = directory / (suffix + "-writer")
                    local.mkdir()
                    current = _select(history, suffix, api, local, patch)
                    api.events.clear()
                    api.calls.clear()
                    api.reads.clear()
                    before = copy.deepcopy(api)
                    for phase in ("prepare", "claim", "judge", "publish"):
                        code, observed = _invoke(current, capture, phase)
                        assert code == 0, (phase, observed, current.diagnostic)
                    assert api.events == ["grade_claim", "judge", "grade_output"] and current.transport.calls == 1
                    _unchanged(api, (before.trees, before.writers, before.parents, previous))
                    revision, path = api.branches[grading.BRANCH], grading._paths(current.context.cell)[1]
                    history.grades[suffix] = SimpleNamespace(before=before, revision=revision, path=path,
                        terminal=pilot._json_object(api.trees[revision][path]), root=current.root,
                        ready=retained._read(current.root / "prepared.json"),
                        receipt=retained._read(current.root / "claim-receipt.json"))
                history.api = copy.deepcopy(api)
            yield history
    finally:
        histories.close()


CASES = [(suffix, change) for suffix in RECORDED for change in ("chain", "inference_run", "record_ungraded")] + [
    ("C_r1", "plan_workflow"), ("C_r1", "inference_source"), ("C_r1", "completion"),
    ("C_r1", "inference_bytes"), ("C_r1", "wrong_ref"), ("C_r1", "snapshot_hash"),
    ("C_r1", "previous_observation"), ("C_r1", "previous_receipt"), ("C_r1", "previous_child"),
    ("C_r2", "previous_controller"), ("B_r2", "previous_grader_hash"),
    ("C_r2", "skipped"), ("B_r2", "unfinished"), ("B_r2", "controller_drift"),
    ("C_r1", "missing_approval"), ("C_r1", "skipped_approval"), ("C_r1", "failed_approval"),
    ("C_r1", "approval_request"), ("C_r1", "rerun"), ("C_r1", "resolution"),
    ("C_r1", "cas"), ("C_r2", "claim_lost"), ("B_r2", "publication_lost"),
    ("C_r1", "admission_cache"), ("C_r2", "admission_parent"),
    ("C_r1", "raw_output"), ("B_r2", "cleanup"),
    ("C_r1", "terminal_parent"), ("C_r2", "terminal_hash"), ("B_r2", "terminal_child"),
    ("C_r1", "terminal_history"),
]


@pytest.mark.parametrize("suffix,change", CASES, ids=[suffix + "-" + change for suffix, change in CASES])
def test_recorded_task4_successor_grading(successor_history, tmp_path, monkeypatch, capsys, suffix, change):
    history, index = successor_history, SEQUENCE.index(suffix)
    row, previous, earlier = (history.grades[item] for item in (suffix, SEQUENCE[index - 1], SEQUENCE[index - 2]))
    terminal_check = change.startswith("terminal_")
    api = copy.deepcopy(history.api if terminal_check or change == "chain" else row.before)
    current = _select(history, suffix, api, tmp_path, monkeypatch,
                      controller=FOREIGN if change == "controller_drift" else failed.FUTURE_CONTROLLER)
    context, inference = current.context, current.inference
    api.calls.clear()
    api.events.clear()
    api.reads.clear()
    assert context.terminal_request == grading.TASK4_RETAINED[failed.PREFIX + suffix][1]
    assert context.plan["order"][18:23] == [failed.PREFIX + item for item in SEQUENCE]
    assert context.plan["order"][18 + index] == context.cell["cell_id"]
    assert not grading._model_free_context(context) and grading._shared_controller_successor(context)

    def no_model_free_predecessor(*args, **kwargs):
        raise AssertionError("successful successors must verify ordinary judged predecessors")
    monkeypatch.setattr(ungraded, "verify_terminal", no_model_free_predecessor)

    if change == "chain":
        claim, binding = row.receipt["claim"], row.terminal["binding"]
        assert claim["expected_parent"] == previous.revision
        assert claim["predecessor"] == {"cell_id": failed.PREFIX + SEQUENCE[index - 1],
            "revision": previous.revision, **pilot._identity(retained._encoded(previous.terminal))}
        assert row.ready["evidence"] == inference.evidence
        assert row.ready["evidence"]["claim"]["predecessor"] == previous.terminal["binding"]["retained"]
        assert row.ready["evidence"]["claim"]["binding"]["github_run"] == {
            "id": RECORDED[suffix][0], "job": "cell", "attempt": 1}
        assert row.ready["terminal_revision"] == inference.terminal and row.ready["judge_ready"] is True
        assert binding["source_sha"] == failed.PRODUCER and binding["controller_source_sha"] == failed.FUTURE_CONTROLLER
        assert binding["github_run"] == {"id": str(991018 + index), "job": "pilot-live", "attempt": 1}
        assert binding["retained"] == inference.evidence["observation"]
        assert row.terminal["format"] == grading.RESULT_FORMAT and row.terminal["child"]["entry_invoked"] is True
        assert row.terminal["outcome"] == "graded"  # Synthetic writer only, never a live quality observation.
        assert row.terminal["invoice_complete"] is False and row.terminal["http_request_count"] is None
        assert history.pair.a1_terminal["format"] == ungraded.TERMINAL_FORMAT
        assert history.pair.a1_terminal["outcome"] == "ungraded" and history.pair.a1_terminal["model_invoked"] is False
        assert not {"child", "score", "verdict", "files"}.intersection(history.pair.a1_terminal)
        assert history.pair.a1_terminal["inference_completion"]["status"] == "failed"
        assert history.pair.b1_terminal["child"]["entry_invoked"] is True
        assert history.pair.b1_admission["claim"]["predecessor"]["revision"] == history.pair.a1_revision
        assert history.pair.b1_prepared["evidence"]["claim"]["predecessor"] == history.pair.a1_terminal["binding"]["retained"]
        if suffix != "B_r2":
            assert inference.terminal != api.branches[retained.BRANCH]
        context.terminal_revision = inference.terminal
        with retained._session(api) as (client, token, deadline):
            verified = grading._grade_terminal(client, api.repo, row.revision, context, row.ready["entry"],
                                               grading._cache(tmp_path, "verified"), token, deadline)
        assert verified["terminal"] == row.terminal
        shutil.copytree(row.root, current.root)
        frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
        for phase in ("claim", "judge", "publish"):
            assert _invoke(current, capsys, phase)[0] == 2
        _unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change == "plan_workflow":
        assert len(context.plan["order"]) == 30 and context.plan["run_id"] == "budget_pilot_ci_20260925_04"
        assert context.controller_source_sha != context.plan["reviewed_source_sha"] == failed.PRODUCER
        assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
        assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
        assert context.plan["model"]["deployment"] == "gpt-5.4" and context.plan["model"]["route_profile"] == "direct-v1"
        assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
        for cell_id in context.plan["order"][23:]:
            assert cell_id not in grading.TASK4_RETAINED
            with pytest.raises(output.OutputPublicationRefused, match="closed_retained_producer_binding_required"):
                grading.compile_request("pilot/" + cell_id, failed.FUTURE_CONTROLLER, current.request,
                                        producer_source_sha=failed.PRODUCER)
        jobs = history.workflow["jobs"]
        expression = jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
        assert jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == expression
        assert all(expression.count('"pilot/' + cell_id + '"') == 1 for cell_id in grading.TASK4_RETAINED)
        assert all('"pilot/' + cell_id + '"' not in expression for cell_id in context.plan["order"][23:])
        assert jobs["pilot-live"]["needs"] == ["pilot-approve-paid"] and "environment" not in jobs["pilot-live"]
        assert "needs.pilot-approve-paid.result == 'success'" in jobs["pilot-live"]["if"]
        assert jobs["pilot-live"]["permissions"] == {"contents": "read", "id-token": "write"}
        assert jobs["pilot-live"]["env"]["PILOT_WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
        assert jobs["pilot-approve-paid"]["permissions"] == {} and len(jobs["pilot-approve-paid"]["steps"]) == 1
        assert jobs["pilot-approve-paid"]["environment"] == {"name": "grading"}
        steps = {step["name"]: step for step in jobs["pilot-live"]["steps"] if "name" in step}
        recorder = steps["Record only the verified failed task4 A1 without a judge"]
        assert "'pilot/" + grading.TASK4_A1_CELL + "'" in recorder["if"]
        assert not any(failed.PREFIX + item in recorder["if"] for item in RECORDED)
        assert "judge_ready == 'false'" in recorder["if"] and "model_free_record_ready == 'true'" in recorder["if"]
        for name in ("Grading Azure login (OIDC)", "Claim one private grading admission with parent CAS",
                     "Invoke exactly the compiled fixed Step8 command once"):
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in steps[name]["if"]
        assert "steps.pilot_judge.outcome != 'skipped'" in steps["Retain validated private grade and accounting on the grading branch"]["if"]
        assert grading._context_authority(context)["id"] == "991020"
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN")
        assert _invoke(current, capsys)[0] == 0
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if change == "record_ungraded":
        code, observed = _invoke(current, capsys, "record-ungraded")
        assert code == 2 and observed["reason"] == "fixed_model_free_a1_required"
        assert not current.root.exists() and api.calls == [] and current.transport.calls == 0
        return

    if terminal_check:
        terminal = copy.deepcopy(row.terminal)
        claim_revision, claim_path = terminal["claim_commit"], grading._paths(context.cell)[0]
        claim = pilot._json_object(api.trees[claim_revision][claim_path])
        if change == "terminal_parent":
            claim["expected_parent"] = claim["predecessor"]["revision"] = earlier.revision
        elif change == "terminal_hash":
            claim["predecessor"]["sha256"] = "9" * 64
        elif change == "terminal_child":
            terminal["child"]["entry_invoked"] = False
        else:
            api.trees[claim_revision][previous.path] += b" "
        data = retained._encoded(claim)
        api.trees[claim_revision][claim_path] = api.trees[row.revision][claim_path] = data
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[row.revision][row.path] = retained._encoded(terminal)
        context.terminal_revision = inference.terminal
        frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
        with retained._session(api) as (client, token, deadline), pytest.raises(output.OutputPublicationRefused,
                match="grade_cleanup_unconfirmed" if change == "terminal_child" else None):
            grading._grade_terminal(client, api.repo, row.revision, context, row.ready["entry"],
                                    grading._cache(tmp_path, "tampered-terminal"), token, deadline)
        _unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return

    if change in {"inference_run", "inference_source"}:
        claim = pilot._json_object(api.trees[inference.claim][inference.claim_path])
        if change == "inference_run":
            claim["binding"]["github_run"]["id"] = str(int(RECORDED[suffix][0]) + 1)
        else:
            claim["binding"]["source_sha"] = failed.FUTURE_CONTROLLER
        terminal = pilot._json_object(api.trees[inference.terminal][inference.terminal_path])
        terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
        for tree in api.trees.values():
            if inference.claim_path in tree:
                tree[inference.claim_path] = retained._encoded(claim)
            if inference.terminal_path in tree:
                tree[inference.terminal_path] = retained._encoded(terminal)
    elif change == "completion":
        terminal = pilot._json_object(api.trees[inference.terminal][inference.terminal_path])
        terminal["completion"]["child_invocations"] = 2
        api.trees[inference.terminal][inference.terminal_path] = retained._encoded(terminal)
    elif change == "inference_bytes":
        api.trees[inference.output][retained._paths(context.cell)[2] + "/step2_inference_results.json"] += b"PRIVATE"
    elif change == "wrong_ref":
        monkeypatch.setattr(grading, "BRANCH", "pilot-grades-20260924-03")
    elif change == "snapshot_hash":
        api.trees[api.branches[retained.BRANCH]][inference.terminal_path] += b" "
    elif change.startswith("previous_"):
        terminal = copy.deepcopy(previous.terminal)
        binding = terminal["binding"]
        if change == "previous_observation":
            binding["retained"]["manifest_sha256"] = "9" * 64
        elif change == "previous_receipt":
            binding["publication_receipt_sha256"] = "9" * 64
        elif change == "previous_child":
            terminal["child"]["entry_invoked"] = False
        elif change == "previous_controller":
            binding["controller_source_sha"] = FOREIGN
            binding["approval_request_sha256"] = grading._approval_request_sha256(FOREIGN,
                "pilot/" + failed.PREFIX + SEQUENCE[index - 1], grading.TASK4_RETAINED[failed.PREFIX + SEQUENCE[index - 1]][1],
                binding["github_run"], producer_source_sha=failed.PRODUCER)
        else:
            binding["grader_source_hash"] = "9" * 64
        path = grading._paths(context.plan["cells"][18 + index - 1])[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][path])
        claim["binding"] = binding
        data = retained._encoded(claim)
        api.trees[terminal["claim_commit"]][path] = api.trees[previous.revision][path] = data
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[previous.revision][previous.path] = retained._encoded(terminal)
    elif change in {"unfinished", "skipped"}:
        api.branches[grading.BRANCH] = previous.terminal["claim_commit"] if change == "unfinished" else earlier.revision
    elif change == "missing_approval":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif change in {"skipped_approval", "failed_approval"}:
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped" if change == "skipped_approval" else "failure")
    elif change == "approval_request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "9" * 64)
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")

    frozen = copy.deepcopy((api.trees, api.writers, api.parents, api.branches[retained.BRANCH]))
    code, observed = _invoke(current, capsys, "prepare")
    if change in {"inference_run", "inference_source", "completion", "inference_bytes", "wrong_ref", "snapshot_hash",
                  "missing_approval", "skipped_approval", "failed_approval", "approval_request", "rerun"}:
        assert code == 2 and observed["outcome"] == "refused", (observed, current.diagnostic)
        _unchanged(api, frozen)
        assert api.events == [] and current.transport.calls == 0
        return
    assert code == 0 and observed["judge_ready"] is True, (observed, current.diagnostic)
    assert retained._read(current.root / "prepared.json")["terminal_revision"] == inference.terminal
    if change == "resolution":
        path = current.root / "retained-resolution.json"
        value = retained._read(path)
        value["terminal_revision"] = history.inferences["B_r1"].terminal
        path.write_bytes(retained._encoded(value))
    elif change == "cas":
        api.move_before_commit = True
    elif change == "claim_lost":
        api.lost = "grade_claim"
    code, observed = _invoke(current, capsys, "claim")
    if change.startswith("previous_") or change in {"unfinished", "skipped", "controller_drift", "resolution", "cas", "claim_lost"}:
        assert code == 2 and observed["outcome"] in {"refused", "unresolved"}, (observed, current.diagnostic)
        if change == "previous_child":
            assert observed["reason"] == "grade_cleanup_unconfirmed"
        events = list(api.events)
        assert events == (["grade_claim"] if change in {"cas", "claim_lost"} else [])
        assert _invoke(current, capsys, "judge")[0] == _invoke(current, capsys, "claim")[0] == 2
        _unchanged(api, frozen)
        assert api.events == events and current.transport.calls == 0
        return
    assert code == 0 and observed["outcome"] == "acknowledged", (observed, current.diagnostic)
    receipt_path = current.root / "claim-receipt.json"
    receipt = retained._read(receipt_path)
    assert receipt["claim"]["expected_parent"] == previous.revision
    if change in {"admission_cache", "admission_parent"}:
        if change == "admission_cache":
            cache = current.root / "claim-verified" / (receipt["returned_commit"] + ".json")
            cache.write_bytes(retained._encoded(receipt["claim"]) + b"PRIVATE")
        else:
            receipt["claim"]["expected_parent"] = receipt["claim"]["predecessor"]["revision"] = earlier.revision
            receipt["claim_identity"] = pilot._identity(retained._encoded(receipt["claim"]))
            receipt_path.write_bytes(retained._encoded(receipt))
        reads = list(api.reads)
        assert _invoke(current, capsys, "judge")[0] == 2
        _unchanged(api, frozen)
        assert api.events == ["grade_claim"] and api.reads == reads and current.transport.calls == 0
        return
    if change == "cleanup":
        current.transport.mode = "cleanup_lost"
    assert _invoke(current, capsys, "judge")[0] == (2 if change == "cleanup" else 0)
    assert current.transport.calls == 1
    if change == "publication_lost":
        api.lost = "grade_output"
    elif change == "raw_output":
        ready = retained._read(current.root / "prepared.json")
        path = current.root / "source" / ready["entry"]["grade_path"]
        payload = pilot._json_object(path.read_bytes())
        payload["judge_raw_response"] = chain.PRIVATE
        path.write_bytes(base._json(payload))
    code, observed = _invoke(current, capsys, "publish")
    assert code == 2 and observed["outcome"] == ("unresolved" if change == "publication_lost" else "refused"), (
        observed, current.diagnostic)
    events = list(api.events)
    assert _invoke(current, capsys, "publish")[0] == _invoke(current, capsys, "judge")[0] == 2
    _unchanged(api, frozen)
    assert api.events == events and current.transport.calls == 1
