"""One offline B1 intake/source seam, never a live grade or recovered payload.

Real compilers, serialization, materialization, Step8 writer and immutable
claim/file/CAS validators use the existing synthetic external boundaries. Fake
commit addresses label newly generated evidence; no historical bytes or private
terminal SHA are reconstructed. Only the fixed completion checksum is replaced
with the genuine synthetic completion's digest, never with a remote assertion.
"""

import copy
from functools import lru_cache
import hashlib
import json
from types import SimpleNamespace

import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_grade_readout as readout
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from . import test_codex_budget_pilot_grading as base
from . import test_codex_budget_pilot_grade_readout as writer
from . import test_codex_budget_pilot_grading_oidc as approval
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — forbids all live boundaries

CONTROLLER = "d" * 40  # Synthetic new controller; never an inference producer.
B1_CLAIM, B1_OUTPUT, B1_TERMINAL = "3" * 40, "4" * 40, "5" * 40
ADVANCED = "6" * 40
RUN = {"id": "67890", "job": "pilot-live", "attempt": 1}
SELECTOR = "pilot/" + grading.B1_CELL


class B1HF(base.GradeHF):
    def __init__(self):
        super().__init__()
        self.reads = []

    def record(self, name, kwargs):
        super().record(name, kwargs)
        self.reads.append((name, kwargs.get("revision"), kwargs.get("filename"), kwargs.get("paths")))

    def repo_info(self, **kwargs):
        self.record("metadata", kwargs)
        assert 0 < kwargs["timeout"] <= output.REQUEST_SECONDS
        revision = self.branches.get(kwargs["revision"], kwargs["revision"])
        assert revision in self.trees
        return SimpleNamespace(id=self.repo, private=self.private, sha=revision)

    def assert_main_unchanged(self):
        assert self.trees[self.head] == self.main_snapshot
        assert all(revision == grading.BRANCH for name, revision in self.calls if name == "commit")


@pytest.fixture(scope="module")
def compilations():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (
        grading.RETAINED_PRODUCER_SOURCE, readout.WRITER_SOURCE, grading.B1_PRODUCER_SOURCE, CONTROLLER)}


@pytest.fixture(scope="module")
def compiled_cells():
    return lru_cache(maxsize=16)(adapter.compile_cell_grading_plan)


@pytest.fixture
def case(tmp_path, monkeypatch, capsys, compilations, compiled_cells):
    assert grading.B1_PRODUCER_SOURCE == "e7a28db07ebe10d6508b9256137763cc82f9a1d1"
    assert grading.B1_COMPLETION_SHA256 == "6a23d38158e81cd5ed184a05a7871545d140bb1d92dc1131326d96df29c236f8"
    assert grading.B1_PREVIOUS_GRADE == "a0ded8b7146c028516d007a9afaa0993797fa1ca"
    monkeypatch.setattr(base, "GradeHF", B1HF)
    old = writer.case.__wrapped__(tmp_path, monkeypatch, compilations, compiled_cells)
    revision, grade_path, grade = writer._writer(old, capsys, tmp_path, monkeypatch, "graded")
    api = old.api
    # Address only the fake server's genuine old-grade publication by its fixed
    # historical label, without rewriting its claim/binding/payload bytes.
    api.trees[grading.B1_PREVIOUS_GRADE] = copy.deepcopy(api.trees[revision])
    api.writers[grading.B1_PREVIOUS_GRADE] = {
        name: grading.B1_PREVIOUS_GRADE if value == revision else value
        for name, value in api.writers[revision].items()}
    api.parents[grading.B1_PREVIOUS_GRADE] = api.parents[revision]
    api.branches[grading.BRANCH] = grading.B1_PREVIOUS_GRADE
    old_terminal_path = retained._paths(old.context.cell)[1]
    old_terminal_bytes = api.trees[grading.RETAINED_TERMINAL][old_terminal_path]
    old_terminal = pilot._json_object(old_terminal_bytes)

    with monkeypatch.context() as seed:
        for key, value in {"SOURCE": grading.B1_PRODUCER_SOURCE, "CLAIM": B1_CLAIM,
                           "OUTPUT": B1_OUTPUT, "TERMINAL": B1_TERMINAL}.items():
            seed.setattr(base, key, value)
        context = grading.compile_request(SELECTOR, grading.B1_PRODUCER_SOURCE, B1_TERMINAL)
        state = SimpleNamespace(context=context, api=api, root=tmp_path / "private-b1-grade")
        base._seed_outputs(state, tmp_path)
    claim_path, terminal_path, prefix = retained._paths(context.cell)
    claim = state.claim
    claim["binding"]["github_run"] = dict(grading.B1_INFERENCE_RUN)
    claim["expected_parent"] = grading.RETAINED_TERMINAL
    claim["predecessor"] = {"cell_id": grading.RETAINED_CELL,
        "terminal_commit": grading.RETAINED_TERMINAL, "terminal_sha256": pilot._identity(old_terminal_bytes)["sha256"],
        "output_commit": old_terminal["output_commit"], "manifest_sha256": old_terminal["manifest_identity"]["sha256"]}
    terminal = state.terminal
    terminal["claim_identity"] = pilot._identity(retained._encoded(claim))
    outputs = {name: data for name, data in api.trees[B1_OUTPUT].items() if name.startswith(prefix + "/")}
    api.seed(B1_CLAIM, grading.RETAINED_TERMINAL, {claim_path: retained._encoded(claim)})
    api.seed(B1_OUTPUT, B1_CLAIM, outputs)
    api.seed(B1_TERMINAL, B1_OUTPUT, {terminal_path: retained._encoded(terminal)})
    api.branches.update({retained.BRANCH: B1_TERMINAL, "main": retained.BOOTSTRAP})
    api.head, api.main_snapshot = retained.BOOTSTRAP, copy.deepcopy(api.trees[retained.BOOTSTRAP])
    state.request = pilot._digest(terminal["completion"])
    monkeypatch.setattr(grading, "B1_COMPLETION_SHA256", state.request)
    monkeypatch.setitem(grading.TASK2_RETAINED, grading.B1_CELL, (grading.B1_INFERENCE_RUN["id"], state.request))
    state.context = grading.compile_request(SELECTOR, CONTROLLER, state.request,
                                            producer_source_sha=grading.B1_PRODUCER_SOURCE)
    monkeypatch.setattr(base, "OUTPUT", B1_OUTPUT)  # Existing fake Step8 writer's input revision.
    state.transport = base.Child(state)
    state.old_context, state.old_grade, state.old_grade_path = old.context, grade, grade_path
    state.claim_path, state.terminal_path = claim_path, terminal_path
    state.workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())
    for key, value in {"GITHUB_SHA": CONTROLLER, "PILOT_WORKFLOW_SHA": CONTROLLER,
                       "GITHUB_RUN_ID": RUN["id"]}.items():
        monkeypatch.setenv(key, value)
    # Independently execute the actual protected workflow digest with the
    # captured runtime string-number/absent-optional-field representation.
    inputs = approval._inputs(SELECTOR, state.request)
    inputs.pop("tasks")
    for key in ("tasks_limit", "resume_chunk", "shard_count", "shard_index", "run_ordinal"):
        inputs[key] = str(inputs[key])
    digest = approval._approved_digest(state.workflow, tmp_path, monkeypatch, inputs=inputs)
    assert digest == grading._context_approval(state.context, RUN)
    monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", digest)
    api.calls.clear()
    api.events.clear()
    api.reads.clear()
    return state


def _invoke(case, capsys, phase="plan", **changes):
    return base.invoke(case, capsys, phase, **{"terminal": case.request, **changes})


@pytest.mark.parametrize("change", [
    "accepted", "advanced_snapshot", "completion", "inference_run", "inference_source", "inference_bytes",
    "wrong_ref", "snapshot_mismatch", "outer_metadata", "previous_revision", "previous_writer",
    "previous_source", "previous_grader_hash", "previous_claim", "prepared_resolution", "missing_approval",
    "skipped_approval", "rerun", "approval_request", "producer_override", "claim_lost", "publication_lost", "plan",
])
def test_fixed_b1_grading_intake_and_previous_source(case, monkeypatch, capsys, change):
    api, context = case.api, case.context
    assert context.terminal_revision == "" and context.requested_terminal == case.request
    assert context.plan["reviewed_source_sha"] == grading.B1_PRODUCER_SOURCE
    assert context.controller_source_sha == CONTROLLER and context.plan["order"][7] == grading.B1_CELL
    assert len(context.plan["order"]) == 30 and context.plan["order"][6] == grading.RETAINED_CELL
    # Exact old seam: recompiling A1 with B1's new sources still refuses. The
    # repair must verify A1 separately, not make that forged source pair valid.
    with pytest.raises(output.OutputPublicationRefused, match="closed_retained_producer_binding_required"):
        grading.compile_request("pilot/" + grading.RETAINED_CELL, CONTROLLER, grading.RETAINED_TERMINAL,
                                producer_source_sha=grading.B1_PRODUCER_SOURCE)
    jobs = case.workflow["jobs"]
    assert jobs["pilot-approve-paid"]["environment"] == {"name": "grading"}
    assert jobs["pilot-approve-paid"]["permissions"] == {} and len(jobs["pilot-approve-paid"]["steps"]) == 1
    assert jobs["pilot-live"]["needs"] == ["pilot-approve-paid"] and "environment" not in jobs["pilot-live"]
    assert "needs.pilot-approve-paid.result == 'success'" in jobs["pilot-live"]["if"]
    assert jobs["pilot-plan"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    assert grading.B1_PRODUCER_SOURCE in jobs["pilot-live"]["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    judge_step = next(step for step in jobs["pilot-live"]["steps"] if step.get("id") == "pilot_judge")
    assert "steps.pilot_claim.outcome == 'success'" in judge_step["if"]
    assert "steps.pilot_input.outputs.judge_ready == 'true'" in judge_step["if"]
    assert "HF_TOKEN" not in judge_step.get("env", {})
    assert context.run.grader_config_json == case.old_context.run.grader_config_json
    assert hashlib.sha256(context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    for key in ("model", "dataset", "source_pins", "grading", "order"):
        assert context.plan[key] == case.old_context.plan[key]
    assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
    assert context.plan["model"]["deployment"] == "gpt-5.4"
    assert context.plan["model"]["route_profile"] == "direct-v1"
    assert context.plan["model"]["reasoning_effort"] == "xhigh"
    assert pilot.TOTAL_SECONDS == 10800 and pilot.ATTEMPT_SECONDS == 1800
    assert context.cell["config_sha256"] == "85852f9b8bdbfa66e5c775283ca1fe092e60af21f51eafe82b0021b83109c049"
    config = json.loads(context.grading.dispatch.runs[0].config_json)
    assert config["execution"]["timeout"] == 1800
    assert config["execution"]["codex"]["task_deadline"] == {"condition": "B", "repetition": 1}
    assert config["output"] == {"publish_to_hf": False, "submit_to_evals": False}
    assert context.grading.dispatch.source_pins_json == case.old_context.grading.dispatch.source_pins_json

    if change == "plan":
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.setattr(case.transport, "require_source", lambda *_: pytest.fail("plan checked source"))
        assert _invoke(case, capsys)[0] == 0
        assert api.calls == [] and not case.root.exists() and case.transport.calls == 0
        return

    if change in {"advanced_snapshot", "snapshot_mismatch", "outer_metadata"}:
        files = {"unrelated-cell/PRIVATE": b"PRIVATE unrelated bytes"}
        if change == "outer_metadata":
            value = copy.deepcopy(case.terminal)
            value["publication_receipt_sha256"] = "8" * 64
            files = {case.terminal_path: retained._encoded(value)}
        api.seed(ADVANCED, B1_TERMINAL, files)
        api.branches[retained.BRANCH] = ADVANCED
        if change == "snapshot_mismatch":
            api.trees[ADVANCED][case.terminal_path] += b" "
    if change in {"completion", "inference_run", "inference_source"}:
        terminal = copy.deepcopy(case.terminal)
        if change == "completion":
            terminal["completion"]["child_invocations"] = 2
        else:
            claim = copy.deepcopy(case.claim)
            if change == "inference_run":
                claim["binding"]["github_run"]["id"] = "36192851763"
            else:
                claim["binding"]["source_sha"] = CONTROLLER
            data = retained._encoded(claim)
            for revision in (B1_CLAIM, B1_OUTPUT, B1_TERMINAL):
                api.trees[revision][case.claim_path] = data
            terminal["claim_identity"] = pilot._identity(data)
        api.trees[B1_TERMINAL][case.terminal_path] = retained._encoded(terminal)
    elif change == "inference_bytes":
        prefix = retained._paths(context.cell)[2]
        path = prefix + "/step2_inference_results.json"
        api.trees[B1_OUTPUT][path] += b"PRIVATE"
    elif change == "wrong_ref":
        monkeypatch.setattr(retained, "BRANCH", "pilot-inference-20260924-03")
    elif change == "previous_revision":
        api.branches[grading.BRANCH] = retained.BOOTSTRAP
    elif change in {"previous_writer", "previous_source", "previous_grader_hash"}:
        terminal = copy.deepcopy(case.old_grade)
        if change == "previous_writer":
            terminal["binding"]["github_run"]["id"] = "36161541598"
        elif change == "previous_source":
            terminal["binding"]["controller_source_sha"] = CONTROLLER
        else:
            terminal["binding"]["grader_source_hash"] = "e" * 64
        api.trees[grading.B1_PREVIOUS_GRADE][case.old_grade_path] = retained._encoded(terminal)
    elif change == "previous_claim":
        path = grading._paths(case.old_context.cell)[0]
        api.trees[case.old_grade["claim_commit"]][path] += b" "
    elif change == "missing_approval":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif change == "skipped_approval":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", "skipped")
    elif change == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif change == "approval_request":
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64)
    before = copy.deepcopy(api.trees)
    changes = {"producer": "e" * 40} if change == "producer_override" else {}
    code, observed = _invoke(case, capsys, "prepare", **changes)
    if change in {"completion", "inference_run", "inference_source", "inference_bytes", "wrong_ref",
                  "snapshot_mismatch", "missing_approval", "skipped_approval", "rerun", "approval_request", "producer_override"}:
        assert code == 2 and observed["outcome"] == "refused", case.diagnostic
        assert case.transport.calls == 0 and api.events == [] and api.trees == before
        return
    assert code == 0 and observed["judge_ready"] is True, (observed, case.diagnostic)
    ready = retained._read(case.root / "prepared.json")
    assert ready["terminal_request"] == case.request
    assert ready["source_sha"] == grading.B1_PRODUCER_SOURCE and ready["controller_source_sha"] == CONTROLLER
    assert ready["terminal_revision"] == (ADVANCED if change == "outer_metadata" else B1_TERMINAL)
    assert ready["evidence"]["claim"]["binding"]["github_run"] == grading.B1_INFERENCE_RUN
    assert pilot._digest(ready["evidence"]["terminal"]["completion"]) == case.request
    assert ready["approval_request_sha256"] == grading._context_approval(context, RUN)
    assert api.events == [] and case.transport.calls == 0
    if change == "outer_metadata":
        # Counterexample retained explicitly: checksum-authenticated completion
        # is not proof of the original enclosing terminal or receipt identity.
        assert ready["evidence"]["observation"]["terminal_sha256"] != pilot._identity(
            retained._encoded(case.terminal))["sha256"]
        assert api.trees == before
        return
    reads_before_claim = len(api.calls)
    if change == "prepared_resolution":
        ready["terminal_revision"] = ADVANCED
        ready["evidence"]["observation"]["terminal_commit"] = ADVANCED
        (case.root / "prepared.json").write_bytes(retained._encoded(ready))
    if change == "claim_lost":
        api.lost = "grade_claim"
    code, observed = _invoke(case, capsys, "claim")
    if change.startswith("previous_") or change in {"prepared_resolution", "claim_lost"}:
        assert code == 2 and observed["outcome"] in {"refused", "unresolved"}, (observed, case.diagnostic)
        assert _invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 0
        assert api.events == (["grade_claim"] if change == "claim_lost" else [])
        count = len(api.events)
        assert _invoke(case, capsys, "claim")[0] == 2 and len(api.events) == count
        return
    assert code == 0 and observed["outcome"] == "acknowledged", (observed, case.diagnostic)
    receipt = retained._read(case.root / "claim-receipt.json")
    assert receipt["claim"]["expected_parent"] == grading.B1_PREVIOUS_GRADE
    assert receipt["claim"]["predecessor"]["cell_id"] == grading.RETAINED_CELL
    assert receipt["claim"]["binding"]["source_sha"] == grading.B1_PRODUCER_SOURCE
    assert receipt["claim"]["binding"]["controller_source_sha"] == CONTROLLER
    assert receipt["claim"]["binding"]["retained"]["terminal_commit"] == B1_TERMINAL
    # The saved resolution, not an advanced ref, drives every later phase.
    assert all(revision != retained.BRANCH for name, revision in api.calls[reads_before_claim:] if name == "metadata")
    assert all(name in {case.old_grade_path, grading._paths(case.old_context.cell)[0]}
               for operation, revision, name, _ in api.reads[reads_before_claim:]
               if operation == "download" and revision in {grading.B1_PREVIOUS_GRADE, case.old_grade["claim_commit"]})
    assert _invoke(case, capsys, "judge")[0] == 0
    assert case.transport.calls == 1
    if change == "publication_lost":
        api.lost = "grade_output"
    code, observed = _invoke(case, capsys, "publish")
    assert code == (2 if change == "publication_lost" else 0), (observed, case.diagnostic)
    assert observed["outcome"] == ("unresolved" if change == "publication_lost" else "acknowledged")
    assert api.events == ["grade_claim", "judge", "grade_output"] and case.transport.calls == 1
    assert all(api.trees[revision] == tree for revision, tree in before.items())
    assert api.branches[retained.BRANCH] == (ADVANCED if change == "advanced_snapshot" else B1_TERMINAL)
    assert all(revision not in {"main", "pilot-grades-20260923", "pilot-inference-20260924-03"}
               for _, revision in api.calls)
