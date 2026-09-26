"""One offline first-grade handoff, not recovery of any historical payload.

Reuse genuine compilation, inference serialization, materialization, Step8 and
ledger writers. Synthetic commit labels and generated completion checksums are
fixture identities only. Every external, credential and model boundary is fake
or blocked; the two synthetic filenames say nothing about the live deliverables.
"""

import copy
from functools import lru_cache
import hashlib
import json
from types import SimpleNamespace
import time

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_task2_grade_completion as chain
from . import test_codex_budget_pilot_task2_final_readout as historical
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — forbid all live boundaries

CONTROLLER = "d" * 40  # Synthetic future controller, not a source to dispatch.
SELECTOR = "pilot/2ea2e5b5-257f-42e6-a7dc-93763f28b19d_A_r1"
PREVIOUS_CELL = chain.PREFIX + "A_r2"
CLAIM, OUTPUT, TERMINAL, ADVANCED = (f"{20_000 + offset:040x}" for offset in range(1, 5))
RUN = {"id": "900012", "job": "pilot-live", "attempt": 1}
PRIVATE = "PRIVATE https://private.invalid/path?token=PRIVATE"


@pytest.fixture(scope="module")
def compilations():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (
        grading.RETAINED_PRODUCER_SOURCE, readout.WRITER_SOURCE, grading.B1_PRODUCER_SOURCE,
        readout.B1_WRITER_SOURCE, readout.TASK2_WRITER_SOURCE, grading.TASK3_A1_PRODUCER_SOURCE, CONTROLLER)}


@pytest.fixture(scope="module")
def compiled_cells():
    return lru_cache(maxsize=64)(adapter.compile_cell_grading_plan)


def _address(api, original, label):
    # Label only this fake server's genuine writer output. No original claim,
    # binding or payload bytes change, and no live bytes are reconstructed.
    assert label not in api.trees
    api.trees[label] = copy.deepcopy(api.trees[original])
    api.writers[label] = {name: label if revision == original else revision
                          for name, revision in api.writers[original].items()}
    api.parents[label] = api.parents[original]


@pytest.fixture
def case(tmp_path, monkeypatch, capsys, compilations, compiled_cells):
    assert grading.TASK3_A1_CELL == SELECTOR[6:]
    assert grading.TASK3_A1_PRODUCER_SOURCE == "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e"
    assert grading.TASK3_A1_COMPLETION_SHA256 == "1fb1bc33acab5b2bdefd70744a899c808d984e9c231deded4217ad92d4dc7e3d"
    assert grading.TASK3_A1_INFERENCE_RUN == {"id": "36225255532", "job": "cell", "attempt": 1}
    assert grading.TASK3_A1_PREVIOUS_GRADE == "3a8e135cd232ab900e003fc6d9c459957a0b990e"
    assert grading.TASK3_A1_PREVIOUS_TERMINAL == "e22f0c3de79bbfce084aedde64fa56c40959fde0"
    assert readout.TASK2_WRITER_SOURCE == "a5e5d2589caff21309f0a1c21bb7d9d333ad47c6"
    assert readout.TASK2_GRADE_RUNS[PREVIOUS_CELL] == "36214413190"
    state = chain.case.__wrapped__(tmp_path, monkeypatch, capsys, compilations, compiled_cells)
    api = state.api
    a2_revision, a2_output = state.inferences[PREVIOUS_CELL]
    _address(api, a2_revision, grading.TASK3_A1_PREVIOUS_TERMINAL)
    state.inferences[PREVIOUS_CELL] = (grading.TASK3_A1_PREVIOUS_TERMINAL, a2_output)
    api.branches[retained.BRANCH] = grading.TASK3_A1_PREVIOUS_TERMINAL
    chain._publish(state, capsys, tmp_path / "b1-writer", monkeypatch)
    # Genuine first-grade sequence, not a manufactured completed prefix.
    for suffix in ("C_r1", "C_r2", "B_r2", "A_r2"):
        previous = historical._selected(state, suffix, tmp_path, monkeypatch)
        revision, previous_path, previous_grade = chain._publish(
            previous, capsys, tmp_path / (suffix + "-writer"), monkeypatch)
    _address(api, revision, grading.TASK3_A1_PREVIOUS_GRADE)
    api.branches[grading.BRANCH] = grading.TASK3_A1_PREVIOUS_GRADE
    previous_bytes = api.trees[grading.TASK3_A1_PREVIOUS_TERMINAL][retained._paths(previous.context.cell)[1]]
    previous_terminal = pilot._json_object(previous_bytes)

    with monkeypatch.context() as seed:
        for name, value in {"SOURCE": grading.TASK3_A1_PRODUCER_SOURCE,
                            "CLAIM": CLAIM, "OUTPUT": OUTPUT, "TERMINAL": TERMINAL}.items():
            seed.setattr(base, name, value)
        seed_context = grading.compile_request(SELECTOR, grading.TASK3_A1_PRODUCER_SOURCE, TERMINAL)
        current = SimpleNamespace(context=seed_context, api=api, root=tmp_path / "private-task3-grade")
        base._seed_outputs(current, tmp_path, extra_deliverable=True)
    claim_path, terminal_path, prefix = retained._paths(seed_context.cell)
    current.claim["binding"]["github_run"] = dict(grading.TASK3_A1_INFERENCE_RUN)
    current.claim["expected_parent"] = grading.TASK3_A1_PREVIOUS_TERMINAL
    current.claim["predecessor"] = {"cell_id": PREVIOUS_CELL,
        "terminal_commit": grading.TASK3_A1_PREVIOUS_TERMINAL,
        "terminal_sha256": pilot._identity(previous_bytes)["sha256"],
        "output_commit": previous_terminal["output_commit"],
        "manifest_sha256": previous_terminal["manifest_identity"]["sha256"]}
    current.terminal["claim_identity"] = pilot._identity(retained._encoded(current.claim))
    files = {name: data for name, data in api.trees[OUTPUT].items() if name.startswith(prefix + "/")}
    api.seed(CLAIM, grading.TASK3_A1_PREVIOUS_TERMINAL, {claim_path: retained._encoded(current.claim)})
    api.seed(OUTPUT, CLAIM, files)
    api.seed(TERMINAL, OUTPUT, {terminal_path: retained._encoded(current.terminal)})
    api.branches[retained.BRANCH] = TERMINAL
    api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
    current.request = pilot._digest(current.terminal["completion"])
    monkeypatch.setattr(grading, "TASK3_A1_COMPLETION_SHA256", current.request)
    current.context = grading.compile_request(SELECTOR, CONTROLLER, current.request,
                                               producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)
    current.transport, current.workflow = base.Child(current), state.workflow
    current.previous_context, current.previous_grade = previous.context, previous_grade
    current.previous_path = previous_path
    current.claim_path, current.terminal_path = claim_path, terminal_path
    monkeypatch.setattr(base, "OUTPUT", OUTPUT)
    base._synthetic_rubric(current, monkeypatch)
    chain._authorize(current, tmp_path, monkeypatch, RUN["id"])
    api.calls.clear()
    api.events.clear()
    api.reads.clear()
    return current


def _invoke(case, capsys, phase="plan", **changes):
    code, observed = base.invoke(case, capsys, phase, **{"terminal": case.request, **changes})
    assert "PRIVATE" not in json.dumps(observed)
    return code, observed


@pytest.mark.parametrize("change", [
    "accepted", "advanced_snapshot", "plan", "completion", "inference_run", "inference_source",
    "inference_bytes", "inference_parent", "inference_predecessor", "inference_cleanup",
    "snapshot_mismatch", "wrong_ref", "previous_revision", "previous_run", "previous_writer",
    "previous_grader_hash", "previous_claim", "previous_receipt", "previous_inference_revision",
    "resolution", "missing_approval", "skipped_approval", "rerun", "approval_request",
    "admission_parent", "admission_cell", "terminal_parent", "cas", "claim_lost",
    "publication_lost", "cleanup",
])
def test_fixed_task3_a1_grading_handoff(case, tmp_path, monkeypatch, capsys, change):
    api, context = case.api, case.context
    assert context.terminal_revision == "" and context.requested_terminal == case.request
    assert context.controller_source_sha == CONTROLLER
    assert context.plan["reviewed_source_sha"] == grading.TASK3_A1_PRODUCER_SOURCE
    assert context.plan["order"][11:13] == [PREVIOUS_CELL, grading.TASK3_A1_CELL]
    assert len(context.plan["order"]) == 30 and len(context.plan["cells"]) == 30
    assert len(case.terminal["completion"]["artifacts"]["deliverables"]) == 2
    for key in ("model", "dataset", "source_pins", "grading", "order"):
        assert context.plan[key] == case.previous_context.plan[key]
    assert context.run.grader_config_json == case.previous_context.run.grader_config_json
    assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
    assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
    assert context.plan["model"]["deployment"] == "gpt-5.4"
    assert context.plan["model"]["route_profile"] == "direct-v1"
    assert context.plan["model"]["reasoning_effort"] == "xhigh"
    assert context.cell["config_sha256"] == "35a23a8842d378a8326ec8483553145ee5c63c9c63a383be3eb903bda77136a3"
    jobs = case.workflow["jobs"]
    env_expression = jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    assert jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == env_expression
    assert env_expression.count(f"inputs.experiment_yaml == '{SELECTOR}' && '{grading.TASK3_A1_PRODUCER_SOURCE}'") == 1
    assert jobs["pilot-approve-paid"]["environment"] == {"name": "grading"}
    assert jobs["pilot-approve-paid"]["permissions"] == {} and len(jobs["pilot-approve-paid"]["steps"]) == 1
    assert jobs["pilot-live"]["needs"] == ["pilot-approve-paid"] and "environment" not in jobs["pilot-live"]
    assert "needs.pilot-approve-paid.result == 'success'" in jobs["pilot-live"]["if"]
    assert jobs["pilot-live"]["permissions"] == {"contents": "read", "id-token": "write"}
    judge_step = next(step for step in jobs["pilot-live"]["steps"] if step.get("id") == "pilot_judge")
    assert "steps.pilot_claim.outcome == 'success'" in judge_step["if"]
    assert "steps.pilot_input.outputs.judge_ready == 'true'" in judge_step["if"]
    assert "HF_TOKEN" not in judge_step.get("env", {})
    # Fixture authorization independently executed the actual protected workflow
    # digest; it did not use the connector helper as both producer and oracle.
    assert grading._context_approval(context, RUN) == grading._approval_request_sha256(
        CONTROLLER, SELECTOR, case.request, RUN, producer_source_sha=grading.TASK3_A1_PRODUCER_SOURCE)

    if change == "plan":
        for selector, source, producer, request in (
            (SELECTOR, CONTROLLER, "e" * 40, case.request),
            (SELECTOR, grading.TASK3_A1_PRODUCER_SOURCE, grading.TASK3_A1_PRODUCER_SOURCE, case.request),
            (SELECTOR, CONTROLLER, grading.TASK3_A1_PRODUCER_SOURCE, "e" * 64),
            ("pilot/" + context.plan["order"][13], CONTROLLER, grading.TASK3_A1_PRODUCER_SOURCE, case.request),
            ("pilot/" + PREVIOUS_CELL, CONTROLLER, grading.TASK3_A1_PRODUCER_SOURCE,
             grading.TASK2_RETAINED[PREVIOUS_CELL][1]),
        ):
            with pytest.raises(output.OutputPublicationRefused):
                grading.compile_request(selector, source, request, producer_source_sha=producer)
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN", raising=False)
        assert _invoke(case, capsys)[0] == 0
        assert not case.root.exists() and api.calls == [] and api.events == [] and case.transport.calls == 0
        return

    if change in {"advanced_snapshot", "snapshot_mismatch"}:
        api.seed(ADVANCED, TERMINAL, {"unrelated/PRIVATE": PRIVATE.encode()})
        api.branches[retained.BRANCH] = ADVANCED
        if change == "snapshot_mismatch":
            api.trees[ADVANCED][case.terminal_path] += b" "
    if change in {"completion", "inference_cleanup"}:
        terminal = copy.deepcopy(case.terminal)
        terminal["completion"]["child_invocations" if change == "completion" else "cleanup_confirmed"] = (
            2 if change == "completion" else False)
        api.trees[TERMINAL][case.terminal_path] = retained._encoded(terminal)
    elif change in {"inference_run", "inference_source", "inference_parent", "inference_predecessor"}:
        claim = copy.deepcopy(case.claim)
        if change == "inference_run":
            claim["binding"]["github_run"]["id"] = "36225255533"
        elif change == "inference_source":
            claim["binding"]["source_sha"] = CONTROLLER
        elif change == "inference_parent":
            claim["expected_parent"] = ADVANCED
            claim["predecessor"]["terminal_commit"] = ADVANCED
        else:
            claim["predecessor"]["manifest_sha256"] = "e" * 64
        data = retained._encoded(claim)
        for revision in (CLAIM, OUTPUT, TERMINAL):
            api.trees[revision][case.claim_path] = data
        terminal = copy.deepcopy(case.terminal)
        terminal["claim_identity"] = pilot._identity(data)
        api.trees[TERMINAL][case.terminal_path] = retained._encoded(terminal)
    elif change == "inference_bytes":
        api.trees[OUTPUT][retained._paths(context.cell)[2] + "/step2_inference_results.json"] += PRIVATE.encode()
    elif change == "wrong_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif change == "previous_revision":
        api.branches[grading.BRANCH] = retained.BOOTSTRAP
    elif change in {"previous_run", "previous_writer", "previous_grader_hash", "previous_receipt", "previous_inference_revision"}:
        terminal = copy.deepcopy(case.previous_grade)
        binding = terminal["binding"]
        if change == "previous_run":
            binding["github_run"]["id"] = "36214413191"
            binding["approval_request_sha256"] = grading._context_approval(case.previous_context, binding["github_run"])
        elif change == "previous_writer":
            binding["controller_source_sha"] = CONTROLLER
        elif change == "previous_inference_revision":
            binding["retained"]["terminal_commit"] = TERMINAL
        else:
            binding["grader_source_hash" if change == "previous_grader_hash" else "publication_receipt_sha256"] = "e" * 64
        api.trees[grading.TASK3_A1_PREVIOUS_GRADE][case.previous_path] = retained._encoded(terminal)
    elif change == "previous_claim":
        path = grading._paths(case.previous_context.cell)[0]
        api.trees[case.previous_grade["claim_commit"]][path] += b" "
    elif change == "missing_approval":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif change == "skipped_approval":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped")
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change == "approval_request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "e" * 64)

    before = copy.deepcopy(api.trees)
    code, observed = _invoke(case, capsys, "prepare")
    if change in {"completion", "inference_run", "inference_source", "inference_bytes", "inference_parent",
                  "inference_cleanup", "snapshot_mismatch", "wrong_ref", "missing_approval", "skipped_approval",
                  "rerun", "approval_request"}:
        assert code == 2 and observed["outcome"] == "refused", (observed, case.diagnostic)
        assert case.transport.calls == 0 and api.events == [] and api.trees == before
        return
    assert code == 0 and observed["judge_ready"] is True, (observed, case.diagnostic)
    ready = retained._read(case.root / "prepared.json")
    assert ready["terminal_revision"] == TERMINAL and ready["terminal_request"] == case.request
    assert ready["source_sha"] == grading.TASK3_A1_PRODUCER_SOURCE and ready["controller_source_sha"] == CONTROLLER
    assert ready["evidence"]["claim"]["binding"]["github_run"] == grading.TASK3_A1_INFERENCE_RUN
    deliverables = ready["materialization"]["source_identity"]["deliverables"]
    assert len(deliverables) == 1 and deliverables[0]["task_id"] == context.cell["task_id"]
    assert len(deliverables[0]["files"]) == 2
    for name, data in case.files.items():
        original = case.root / "original" / ("upload" if name.startswith("deliverable_files/") else "")
        assert (original / name).read_bytes() == data
    derived = pilot._json_object((case.root / "inputs/batch-runner/workspace/step2_inference_results.json").read_bytes())
    assert derived["source_revision"] == OUTPUT and derived["result_fingerprint"] != case.payload["result_fingerprint"]
    assert derived["results"] == case.payload["results"]
    assert ready["entry"]["grader_source_hash"] == readout.TASK2_GRADER_SOURCE_HASH
    assert api.events == [] and case.transport.calls == 0
    reads_before_claim = len(api.reads)
    if change == "resolution":
        resolution_path = case.root / "retained-resolution.json"
        resolution = retained._read(resolution_path)
        resolution["terminal_revision"] = ADVANCED
        resolution_path.write_bytes(retained._encoded(resolution))
    elif change == "cas":
        api.move_before_commit = True
    elif change == "claim_lost":
        api.lost = "grade_claim"
    code, observed = _invoke(case, capsys, "claim")
    if change.startswith("previous_") or change in {"inference_predecessor", "resolution", "cas", "claim_lost"}:
        assert code == 2 and observed["outcome"] in {"refused", "unresolved"}, (observed, case.diagnostic)
        assert _invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 0
        assert api.events == (["grade_claim"] if change in {"cas", "claim_lost"} else [])
        events = list(api.events)
        assert _invoke(case, capsys, "claim")[0] == 2 and api.events == events
        assert all(api.trees[revision] == data for revision, data in before.items())
        return
    assert code == 0 and observed["outcome"] == "acknowledged", (observed, case.diagnostic)
    receipt_path = case.root / "claim-receipt.json"
    receipt = retained._read(receipt_path)
    assert receipt["claim"]["expected_parent"] == grading.TASK3_A1_PREVIOUS_GRADE
    assert receipt["claim"]["predecessor"] == {"cell_id": PREVIOUS_CELL,
        "revision": grading.TASK3_A1_PREVIOUS_GRADE, **pilot._identity(retained._encoded(case.previous_grade))}
    assert receipt["claim"]["binding"]["source_sha"] == grading.TASK3_A1_PRODUCER_SOURCE
    assert receipt["claim"]["binding"]["controller_source_sha"] == CONTROLLER
    assert all(revision != retained.BRANCH for name, revision, _, _ in api.reads[reads_before_claim:] if name == "metadata")
    assert all(name in {case.previous_path, grading._paths(case.previous_context.cell)[0]}
               for operation, revision, name, _ in api.reads[reads_before_claim:]
               if operation == "download" and revision in {grading.TASK3_A1_PREVIOUS_GRADE, case.previous_grade["claim_commit"]})
    if change in {"admission_parent", "admission_cell"}:
        claim = receipt["claim"]
        if change == "admission_parent":
            claim["expected_parent"] = ADVANCED
            claim["predecessor"]["revision"] = ADVANCED
        else:
            claim["predecessor"]["cell_id"] = context.plan["order"][10]
        receipt["claim_identity"] = pilot._identity(retained._encoded(claim))
        receipt_path.write_bytes(retained._encoded(receipt))
        assert _invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 0
        assert api.events == ["grade_claim"]
        assert all(api.trees[revision] == data for revision, data in before.items())
        return
    if change == "cleanup":
        case.transport.mode = "cleanup_lost"
    code, _ = _invoke(case, capsys, "judge")
    assert code == (2 if change == "cleanup" else 0) and case.transport.calls == 1
    assert _invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 1
    if change == "publication_lost":
        api.lost = "grade_output"
    code, observed = _invoke(case, capsys, "publish")
    assert code == (2 if change in {"cleanup", "publication_lost"} else 0), (observed, case.diagnostic)
    assert observed["outcome"] == ("unresolved" if change == "publication_lost" else
                                   "refused" if change == "cleanup" else "acknowledged")
    if change == "terminal_parent":
        revision = api.branches[grading.BRANCH]
        terminal_path = grading._paths(context.cell)[1]
        terminal = pilot._json_object(api.trees[revision][terminal_path])
        claim_path = grading._paths(context.cell)[0]
        claim = pilot._json_object(api.trees[terminal["claim_commit"]][claim_path])
        claim["expected_parent"] = ADVANCED
        claim["predecessor"]["revision"] = ADVANCED
        claim_data = retained._encoded(claim)
        api.trees[terminal["claim_commit"]][claim_path] = claim_data
        api.trees[revision][claim_path] = claim_data
        terminal["claim_identity"] = pilot._identity(claim_data)
        api.trees[revision][terminal_path] = retained._encoded(terminal)
        context.terminal_revision = TERMINAL
        with pytest.raises(output.OutputPublicationRefused, match="recorded_task3_grade_predecessor_required"):
            grading._grade_terminal(api, api.repo, revision, context, ready["entry"],
                grading._cache(tmp_path, "terminal-proof"), base.TOKEN, time.monotonic() + 60)
    events = list(api.events)
    assert _invoke(case, capsys, "publish")[0] == 2 and api.events == events
    assert _invoke(case, capsys, "claim")[0] == 2 and api.events == events
    assert case.transport.calls == 1
    assert all(api.trees[revision] == data for revision, data in before.items())
