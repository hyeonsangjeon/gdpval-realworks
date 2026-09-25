"""One OFFLINE approval/source-boundary family; no Azure or native-host proof.

Real compilation, canonical materialization, entry/hash/schema validation and
private CAS run against the existing synthetic HF/renderer/judge/rename seams.
The recorded producer/terminal labels bind synthetic bytes here, not recovered
payloads from the live run. The approval digest executes the actual workflow's
stdlib code independently of the connector's expected-request builder.
"""

from __future__ import annotations

import copy
from functools import lru_cache
import hashlib
import json
import os

import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as connector
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from scripts import check_grader_hash_freeze as freeze
from . import test_codex_budget_pilot_grading as base
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — forbids every live boundary

PRODUCER = connector.RETAINED_PRODUCER_SOURCE
TERMINAL = connector.RETAINED_TERMINAL
CONTROLLER = "d" * 40  # Synthetic separately reviewed workflow, never GITHUB_SHA spoofing in production.
SELECTOR = "pilot/" + connector.RETAINED_CELL
RUN = {"id": "12345", "attempt": 1}


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load((pilot.ROOT / connector.WORKFLOW).read_bytes())


def _inputs(selector=SELECTOR, terminal=TERMINAL):
    return {"experiment_yaml": selector, "inference_revision": terminal,
        "grading_config": "default_v2_sol_max.yaml", "force": False, "tasks_limit": 0, "tasks": "",
        "dry_run": False, "paid_approval": True, "resume": False, "resume_chunk": 0,
        "shard_count": 1, "shard_index": 0, "run_ordinal": 1}


def _approved_digest(workflow, tmp_path, monkeypatch, *, inputs=None):
    step = workflow["jobs"]["pilot-approve-paid"]["steps"][0]
    script = step["run"].removeprefix("python3 - <<'PY'\n").removesuffix("PY\n")
    destination = tmp_path / "approval-output"
    # Exactly one digest output, with no token or payload moving between jobs.
    with monkeypatch.context() as approval:
        approval.setenv("PILOT_GRADE_INPUTS_JSON", json.dumps(inputs or _inputs()))
        approval.setenv("GITHUB_OUTPUT", str(destination))
        approval.setenv("GITHUB_JOB", "pilot-approve-paid")
        for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN",
                    "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
            approval.delenv(key, raising=False)
        exec(compile(script, "<protected-pilot-approval>", "exec"), {})
    line = destination.read_text().splitlines()[-1]
    assert line.startswith("request_sha256=") and output._hash(line.split("=", 1)[1])
    return line.split("=", 1)[1]


@pytest.fixture(scope="module")
def compilations():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source) for source in (PRODUCER, CONTROLLER)}


@pytest.fixture(scope="module")
def compiled_cells():
    return lru_cache(maxsize=16)(adapter.compile_cell_grading_plan)


@pytest.fixture
def case(tmp_path, monkeypatch, compilations, compiled_cells, workflow):
    # Reuse genuine retained serialization and the fixed source-copy fixture.
    monkeypatch.setattr(base, "SOURCE", PRODUCER)
    monkeypatch.setattr(base, "TERMINAL", TERMINAL)
    state = base.case.__wrapped__(tmp_path, monkeypatch, compilations[PRODUCER], compiled_cells)
    original_compile = pilot.compile_pilot
    monkeypatch.setattr(pilot, "compile_pilot", lambda campaign, source:
        copy.deepcopy(compilations[source]) if campaign == ci.CAMPAIGN and source in compilations
        else original_compile(campaign, source))
    state.context = connector.compile_request(SELECTOR, CONTROLLER, TERMINAL, producer_source_sha=PRODUCER)
    for key in ("GITHUB_SHA", "PILOT_WORKFLOW_SHA"):
        monkeypatch.setenv(key, CONTROLLER)
    digest = _approved_digest(workflow, tmp_path, monkeypatch)
    assert digest == connector._context_approval(state.context, RUN)
    monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", digest)
    state.api.branches.update({"main": retained.BOOTSTRAP, retained.BRANCH: TERMINAL,
                              "pilot-grades-20260923": retained.BOOTSTRAP,
                              "pilot-inference-20260924-03": retained.BOOTSTRAP})
    yield state
    state.api.assert_main_unchanged()
    assert state.api.branches[retained.BRANCH] == TERMINAL
    assert all(ref == connector.BRANCH or revision in {retained.BOOTSTRAP, TERMINAL}
               for ref, revision in state.api.branches.items())
    assert all(revision == connector.BRANCH for name, revision in state.api.calls if name == "commit")


def test_protected_approval_ref_main_execution_and_actual_freeze_coverage(workflow):
    jobs = workflow["jobs"]
    approval, live, plan = (jobs[name] for name in ("pilot-approve-paid", "pilot-live", "pilot-plan"))
    assert approval["environment"] == {"name": "grading"} and approval["permissions"] == {}
    assert approval["name"] == "Approve paid pilot grading"
    for gate in ("inputs.dry_run == false", "inputs.paid_approval == true", "github.ref == 'refs/heads/main'",
                 "github.repository == 'hyeonsangjeon/gdpval-realworks'", "github.event_name == 'workflow_dispatch'",
                 "github.sha == github.workflow_sha", "github.run_attempt == '1'"):
        assert gate in approval["if"]
    assert not {"needs", "container"} & set(approval)
    assert not any(text in yaml.safe_dump(approval) for text in ("secrets.", "azure/login", "id-token", "approval_inherited"))
    assert live["needs"] == ["pilot-approve-paid"] and "needs.pilot-approve-paid.result == 'success'" in live["if"]
    assert all(word not in live["if"] for word in ("always()", "skipped", "approval_inherited"))
    assert "environment" not in live and "name" not in live
    assert live["permissions"] == {"contents": "read", "id-token": "write"}
    assert live["container"] == jobs["grade"]["container"] and live["timeout-minutes"] == 300
    assert live["env"]["PILOT_WORKFLOW_SHA"] == "${{ github.workflow_sha }}"
    assert live["env"]["PILOT_GRADE_APPROVAL_RESULT"] == "${{ needs.pilot-approve-paid.result }}"
    assert live["env"]["PILOT_GRADE_APPROVAL_REQUEST_SHA256"] == "${{ needs.pilot-approve-paid.outputs.request_sha256 }}"
    assert plan["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"] == live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    assert PRODUCER in live["env"]["PILOT_GRADE_PRODUCER_SOURCE_SHA"]
    assert "secrets." not in yaml.safe_dump(plan) and "--phase judge" not in yaml.safe_dump(plan)
    steps = live["steps"]
    gate = next(i for i, step in enumerate(steps) if step.get("name") == "Validate the exact selected pilot route")
    for i, step in enumerate(steps):
        if "HF_TOKEN" in step.get("env", {}) or "azure" in step.get("run", "").lower() or "azure/login" in step.get("uses", ""):
            assert i > gate
        if any("--phase " + phase in step.get("run", "") for phase in ("prepare", "claim", "judge", "publish")):
            assert '--producer-source-sha "$PILOT_GRADE_PRODUCER_SOURCE_SHA"' in step["run"]
    judge = next(step for step in steps if step.get("id") == "pilot_judge")
    assert "steps.pilot_claim.outcome == 'success'" in judge["if"] and judge["timeout-minutes"] == 245
    assert "HF_TOKEN" not in judge.get("env", {}) and "HF_TOKEN" not in live["env"]
    assert jobs["grade"]["needs"] == ["validate-request", "approve-paid"]
    for name in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in jobs[name]["if"]
    # Exercise enforcement, not merely the paid-name set. A protected approval
    # waiting, or a paid execution active, must freeze a grader source change.
    for active in (approval["name"], "pilot-live"):
        raw = [{"id": "12345", "status": "waiting", "jobs": [
            {"name": name, "conclusion": None if name == active else "skipped"}
            for name in (approval["name"], "pilot-live", "grade")]}]
        decision = freeze.decide(["batch-runner/core/grader.py"], raw)
        assert decision.frozen and decision.blocking_runs[0].paid_reason == "paid job not skipped: " + active
        for job in raw[0]["jobs"]:
            job["conclusion"] = "skipped"
        assert not freeze.decide(["batch-runner/core/grader.py"], raw).frozen


def test_approval_binds_branch_role_and_all_fixed_request_controls(case, workflow, tmp_path, monkeypatch):
    for selector in connector.BRANCH_ROUTES:
        digest = _approved_digest(workflow, tmp_path, monkeypatch, inputs=_inputs(selector, ""))
        assert digest == connector._approval_request_sha256(CONTROLLER, selector, "", RUN)
        assert digest != os.environ["PILOT_GRADE_APPROVAL_REQUEST_SHA256"]
    for key, value in (("inference_revision", "e" * 40), ("tasks", "foreign"), ("force", True),
                       ("run_ordinal", 2), ("resume", True), ("paid_approval", False)):
        changed = _approved_digest(workflow, tmp_path, monkeypatch, inputs={**_inputs(), key: value})
        assert changed != connector._context_approval(case.context, RUN)


def test_offline_plan_preserves_producer_without_credentials_or_source_checkout(case, capsys, monkeypatch):
    for key in ("GITHUB_ACTIONS", "HF_TOKEN", "PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(case.transport, "require_source", lambda *_: pytest.fail("offline plan checked source"))
    code, observed = base.invoke(case, capsys)
    assert code == 0 and observed["outcome"] == "plan_only"
    assert observed["source_sha"] == PRODUCER and observed["controller_source_sha"] == CONTROLLER
    assert not observed["judge_entry_requested"] and not observed["inference_requested"]
    assert case.api.calls == [] and not case.root.exists() and case.transport.calls == 0


@pytest.mark.parametrize("damage", ["missing_approval", "skipped", "failure", "cancelled", "rerun", "workflow_sha",
    "ref", "request", "other_run", "producer", "terminal", "cell", "implicit_controller_producer", "branch_producer"])
def test_request_tampering_or_unapproved_attempt_stops_before_external_work(case, capsys, monkeypatch, damage):
    changes = {}
    if damage == "missing_approval":
        monkeypatch.delenv("PILOT_GRADE_APPROVAL_RESULT")
    elif damage in {"skipped", "failure", "cancelled"}:
        monkeypatch.setenv("PILOT_GRADE_APPROVAL_RESULT", damage)
    elif damage in {"rerun", "workflow_sha", "ref", "request", "other_run"}:
        key, value = {"rerun": ("GITHUB_RUN_ATTEMPT", "2"), "workflow_sha": ("PILOT_WORKFLOW_SHA", PRODUCER),
            "ref": ("GITHUB_REF", "refs/heads/foreign"), "request": ("PILOT_GRADE_APPROVAL_REQUEST_SHA256", "0" * 64),
            "other_run": ("GITHUB_RUN_ID", "12346")}[damage]
        monkeypatch.setenv(key, value)
    elif damage == "producer":
        changes["producer"] = "e" * 40
    elif damage == "terminal":
        changes["terminal"] = "e" * 40
    elif damage == "cell":
        changes["selector"] = "pilot/" + case.context.plan["order"][7]
    elif damage == "implicit_controller_producer":
        changes["producer"] = ""
    else:
        changes.update(selector="pilot/branch-setup", terminal="")
    for phase in ("plan", "prepare"):
        code, observed = base.invoke(case, capsys, phase, **changes)
        assert code == 2 and observed["outcome"] == "refused"
    assert case.api.calls == [] and not case.root.exists() and case.transport.calls == 0


@pytest.mark.parametrize("lost_response", [False, True], ids=["acknowledged", "lost_response"])
def test_old_retained_producer_new_controller_fixed_judge_and_private_publication(case, capsys, compilations, lost_response):
    before = copy.deepcopy(case.api.trees)
    ready = base.prepared(case, capsys)
    assert ready["source_sha"] == PRODUCER and ready["controller_source_sha"] == CONTROLLER
    assert ready["approval_request_sha256"] == connector._context_approval(case.context, RUN)
    assert ready["proof_boundary"] == connector.PROOF and ready["materialization"]["reviewed_source_sha"] == PRODUCER
    identity = retained._read(case.root / "inference-identity.json")
    assert identity["grading_plan_sha256"] == hashlib.sha256(case.context.grading.canonical_bytes()).hexdigest()
    assert identity["source_revision"] == base.OUTPUT
    assert base.OUTPUT not in {CONTROLLER, PRODUCER, TERMINAL, case.context.plan["dataset"]["revision"]}
    for name, data in case.files.items():
        root = case.root / "original" / ("upload" if name.startswith("deliverable_files/") else "")
        assert (root / name).read_bytes() == data
    for name, data in connector.configs._files(case.context.grading, case.context.run.run_id).items():
        assert (case.root / "source" / name).read_bytes() == data
    assert case.context.grading.dispatch.source_base_sha == PRODUCER
    assert case.context.run.grader_config_json == compilations[PRODUCER][1].runs[0].grader_config_json
    assert base.invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 0  # No private claim yet.
    assert base.invoke(case, capsys, "claim")[0] == 0
    admission = retained._read(case.root / "claim-receipt.json")
    binding = admission["claim"]["binding"]
    assert binding["source_sha"] == PRODUCER and binding["controller_source_sha"] == CONTROLLER
    assert binding["retained"]["terminal_commit"] == TERMINAL
    assert binding["branch"] == "pilot-grades-20260925-04" and binding["inference_branch"] == "pilot-inference-20260925-04"
    assert binding["grader_source_hash"] == ready["entry"]["grader_source_hash"]
    for field, foreign in (("source_sha", CONTROLLER), ("controller_source_sha", PRODUCER),
                           ("approval_request_sha256", "0" * 64)):
        with pytest.raises(output.OutputPublicationRefused, match="grade_claim_contract_mismatch"):
            connector._validate_binding({**binding, field: foreign}, case.context, ready["entry"])
    without_controller = {key: value for key, value in binding.items() if key != "controller_source_sha"}
    with pytest.raises(output.OutputPublicationRefused, match="grade_claim_contract_mismatch"):
        connector._validate_binding(without_controller, case.context, ready["entry"])
    assert base.invoke(case, capsys, "judge")[0] == 0 and case.transport.calls == 1
    if lost_response:
        case.api.lost = "grade_output"
    code, _ = base.invoke(case, capsys, "publish")
    assert code == (2 if lost_response else 0)
    receipt = case.root / "publication-receipt.json"
    original_receipt = receipt.read_bytes()
    assert retained._read(receipt)["outcome"] == ("unresolved" if lost_response else "acknowledged")
    terminal = json.loads(case.api.trees[case.api.branches[connector.BRANCH]][connector._paths(case.context.cell)[1]])
    assert terminal["binding"] == binding and terminal["invoice_complete"] is False and terminal["http_request_count"] is None
    assert case.api.events == ["grade_claim", "judge", "grade_output"]
    assert base.invoke(case, capsys, "judge")[0] == 2 and case.transport.calls == 1
    assert base.invoke(case, capsys, "claim")[0] == 2
    if lost_response:
        code, observed = base.invoke(case, capsys, "reconcile")
        assert code == 0 and observed["outcome"] == "verified_server_state"
        assert retained._read(case.root / "grade-server-observation.json")["writer_acknowledgment"] == "not_established"
    assert receipt.read_bytes() == original_receipt
    assert all(case.api.trees[revision] == data for revision, data in before.items())
    assert {row["role"] for row in terminal["files"]} == {"grade_result", "grade_cost_ledger"}
    assert all(not any(text in row["path"] for text in ("original", "judge.stdout", "judge.stderr", "inference-identity"))
               for row in terminal["files"])


@pytest.mark.parametrize("damage", ["producer_claim", "manifest", "receipt_ack", "cleanup", "bytes"])
def test_retained_producer_proofs_still_refuse_tampering(case, capsys, damage):
    claim_path, terminal_path, prefix = retained._paths(case.context.cell)
    if damage == "producer_claim":
        value = copy.deepcopy(case.claim)
        value["binding"]["source_sha"] = CONTROLLER
        case.api.trees[base.CLAIM][claim_path] = retained._encoded(value)
        case.terminal["claim_identity"] = pilot._identity(retained._encoded(value))
    elif damage == "manifest":
        case.terminal["manifest_identity"]["sha256"] = "0" * 64
    elif damage == "receipt_ack":
        case.terminal["publication_acknowledged"] = False
    elif damage == "cleanup":
        case.terminal["completion"]["cleanup_confirmed"] = False
    else:
        case.api.trees[base.OUTPUT][prefix + "/step2_inference_results.json"] += b" "
    case.api.trees[TERMINAL][terminal_path] = retained._encoded(case.terminal)
    case.api.main_snapshot = copy.deepcopy(case.api.trees[TERMINAL])
    code, observed = base.invoke(case, capsys, "prepare")
    assert code == 2 and observed["reason"] != "grading_source_preflight_refused"
    assert case.api.calls  # Refusal must reach the retained proof, not an earlier fixture boundary.
    assert case.transport.calls == 0 and case.api.events == []
    assert not (case.root / "claim-reserved.json").exists()


@pytest.mark.parametrize("damage", ["controller_source_sha", "approval_request_sha256", "prepared_bytes", "staged_grader"])
def test_prepared_controller_request_and_pinned_bytes_revalidated_before_claim(case, capsys, damage):
    ready = base.prepared(case, capsys)
    if damage in {"controller_source_sha", "approval_request_sha256"}:
        ready[damage] = "0" * (40 if damage == "controller_source_sha" else 64)
        (case.root / "prepared.json").write_bytes(retained._encoded(ready))
    else:
        relative = ("batch-runner/core/grader.py" if damage == "staged_grader"
                    else "batch-runner/workspace/step2_inference_results.json")
        path = case.root / "source" / relative
        path.write_bytes(path.read_bytes() + b" ")
    calls = list(case.api.calls)
    assert base.invoke(case, capsys, "claim")[0] == 2
    assert case.api.calls == calls and case.api.events == [] and case.transport.calls == 0
    assert not (case.root / "claim-reserved.json").exists()
