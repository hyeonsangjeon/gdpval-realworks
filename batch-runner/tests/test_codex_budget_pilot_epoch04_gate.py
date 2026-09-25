"""One offline fixed-task2 gate; no live setup, admission or grade evidence.

Reuse the real compiler, Step2 writer, deadline, publisher, materializer and CAS
helpers. Native/source capability, model observations and HF are synthetic.
The original 30-cell order is not a grant to run its 24-cell eligible suffix.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import time

import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from core.codex_task_deadline import CodexTaskDeadlineControl
from .test_codex_budget_pilot_epoch02 import (
    OLD_CAMPAIGN, OLD_SOURCE, compiled, grading_environment, setup_case, setup_cli,
)  # noqa: F401 -- fixtures/helpers only, not the older families.
from .test_codex_budget_pilot_epoch03_gate import (
    EPOCH02, SOURCE02, GateHF,
)
from .test_codex_budget_pilot_retention import (
    SOURCE, TOKEN, TOKEN_KEYS, admitted, boundary, case, cell_root, cli, finalized,
    prepare, read_plan, read_state, scenario, select_fresh,
)  # noqa: F401 -- real local state/dispatcher and fake external boundaries.
from .test_codex_budget_pilot_success_retention import (
    DELIVERABLE, WriterChildren, _grade_inputs, offline,
)  # noqa: F401 -- genuine producer writer and materializer; fake native rename.

BASELINE = "0bb141f3bf93510ccb399800a4aa0901ceb36638"
FIRST = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1"
EPOCH03 = "budget_pilot_ci_20260924_03"
SOURCE03 = "fb232a074f395766f9f83ddc7195a9997a3428f5"
INFERENCE03 = "pilot-inference-20260924-03"
GRADING03 = "pilot-grades-20260924-03"
REAL_HF_CLIENT = output._hf_client


class CorrectiveHF(GateHF):
    """Extend the existing add-only fake to freeze both epoch03 refs too."""

    def __init__(self):
        super().__init__()
        self.path_queries = []
        for ref, revision in ((INFERENCE03, "a" * 40), (GRADING03, "b" * 40)):
            self.branches[ref] = revision
            self.trees[revision] = {f"cell-claims/{EPOCH03}/{FIRST}/frozen": b"synthetic old03 claim"}
            self.writers[revision] = {path: revision for path in self.trees[revision]}
            self.frozen[ref] = (revision, copy.deepcopy(self.trees[revision]))

    def record(self, name, kwargs):
        assert kwargs.get("revision") not in {INFERENCE03, GRADING03, "a" * 40, "b" * 40}
        if name == "paths":
            self.path_queries.append(tuple(kwargs["paths"]))
        return super().record(name, kwargs)

    def assert_frozen(self):
        super().assert_frozen()
        for ref in (retained.BRANCH, grading.BRANCH):
            assert all(EPOCH03 not in path for path in self.trees[self.branches[ref]])


@pytest.fixture
def gate(case, monkeypatch):
    case.api = CorrectiveHF()
    case.transport = WriterChildren(case.sources, case.ids, case.api, monkeypatch)
    assert case.selected == FIRST
    yield case
    case.api.assert_frozen()


def test_closed04_plan_preserves_original_order_and_controls(gate, monkeypatch, capsys):
    class NoCredentials(dict):
        def get(self, key, *args):
            assert key not in TOKEN_KEYS
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoCredentials(os.environ))
    assert cli(gate) == 0 and boundary(gate, capsys, monkeypatch)[0] == 0
    plan = read_plan(gate)
    assert gate.api.calls == gate.transport.calls == []
    assert ci.CAMPAIGN == plan["run_id"] == "budget_pilot_ci_20260925_04"
    assert ci.FIRST_CELL_ORDINAL == 6 and ci.FIRST_CELL_ID == plan["order"][6] == FIRST
    assert plan["ci"]["selected_cell_id"] == FIRST and plan["cells"][6]["index"] == 6
    assert len(plan["cells"]) == 30 and len(gate.ids) == 5
    assert pilot.ORDER == (("A", 1), ("B", 1), ("C", 1), ("C", 2), ("B", 2), ("A", 2))
    assert plan["order"] == [f"{task}_{arm}_r{repeat}" for task in gate.ids for arm, repeat in pilot.ORDER]
    assert plan["launch_authorized_by_plan"] is plan["grading_launched"] is False
    assert all(read_state(gate, cell["cell_id"]) == pilot._cell_state(plan, cell) for cell in plan["cells"])
    assert ci.PUBLIC_FIXED["denominator"] == 30 and ci.PUBLIC_FIXED["other_cells_not_run"] == 29
    registration = yaml.safe_load(ci._registration_bytes())
    assert ci.REGISTRATION.name == "codex_external_budget_ci_pilot_epoch04.yaml"
    assert registration["source_baseline"] == BASELINE
    assert registration["entrypoint"] == ci.ENTRYPOINT == {
        "first_ordinal": 6, "first_cell_id": FIRST, "earlier_cells": "out_of_scope"}
    assert registration["storage"] == ci.STORAGE == {
        "repository_name_sha256": "a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44",
        "bootstrap": "bfc7ae01ed14490817ceb7cb406adcb9bb95f557",
        "inference_branch": "pilot-inference-20260925-04", "grading_branch": "pilot-grades-20260925-04"}
    assert plan["ci"]["registration_sha256"] == hashlib.sha256(ci._registration_bytes()).hexdigest()
    assert {key: plan["model"][key] for key in ("deployment", "route_profile", "reasoning_effort")} == {
        "deployment": "gpt-5.4", "route_profile": "direct-v1", "reasoning_effort": "xhigh"}
    assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
    assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
    _, _, specs = pilot.compile_pilot(ci.CAMPAIGN, SOURCE)
    for campaign, source in ((OLD_CAMPAIGN, OLD_SOURCE), (EPOCH02, SOURCE02), (EPOCH03, SOURCE03)):
        historical, _, old_specs = pilot.compile_pilot(campaign, source)
        assert historical["order"] == plan["order"]
        assert {cell["run_id"] for cell in historical["cells"]}.isdisjoint(cell["run_id"] for cell in plan["cells"])
        for key in ("model", "dataset", "grading", "source_pins"):
            assert historical[key] == plan[key]
        for cell in plan["cells"]:
            current, old = (json.loads(items[cell["cell_id"]].config_json) for items in (specs, old_specs))
            assert current["experiment"].pop("id") != old["experiment"].pop("id")
            assert current == old
            control = CodexTaskDeadlineControl.from_mapping(current["execution"]["codex"]["task_deadline"])
            assert control.max_attempts == (4 if cell["condition"] == "A" else None)
        with pytest.raises(ci.CICellRefused, match="registered_ci_campaign_required"):
            ci.compile_ci_cell(campaign, FIRST, SOURCE)
    for name, campaign in (("codex_external_budget_ci_pilot.yaml", OLD_CAMPAIGN),
            ("codex_external_budget_ci_pilot_epoch02.yaml", EPOCH02),
            ("codex_external_budget_ci_pilot_epoch03.yaml", EPOCH03)):
        assert yaml.safe_load(ci.REGISTRATION.with_name(name).read_bytes())["campaign_id"] == campaign
    context = grading.compile_request("pilot/" + FIRST, SOURCE)
    assert context.run.command[2] == "pilot/cell-06" and context.cell["index"] == 6
    with monkeypatch.context() as grade_host:
        grading_environment(grade_host)
        for selector in grading.BRANCH_ROUTES:
            assert grading.main(["--selector", selector, "--reviewed-source-sha", SOURCE,
                                 "--root", str(gate.host / "no-plan-state")]) == 0
    assert not (gate.host / "no-plan-state").exists()
    assert gate.api.calls == gate.transport.calls == []
    workflow = yaml.safe_load((pilot.ROOT / ci.WORKFLOW).read_bytes())
    job = workflow["jobs"]["cell"]
    routed = [step for step in job["steps"] if "--campaign-id " in step.get("run", "")]
    assert [step["id"] for step in routed] == ["plan", "output_target", "output_setup", "intake", "execution"]
    assert all(step["run"].count("--campaign-id " + ci.CAMPAIGN) == 1 for step in routed)
    assert all(EPOCH03 not in step["run"] for step in routed)
    assert job["timeout-minutes"] == 240 and "strategy" not in job
    assert workflow["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    assert "steps.admission.outputs.admitted == 'true'" in routed[-1]["if"]


@pytest.mark.parametrize("ordinal", range(6))
def test_prefix_refuses_before_source_state_or_remote_authority(gate, monkeypatch, capsys, ordinal):
    plan, _, _ = pilot.compile_pilot(ci.CAMPAIGN, SOURCE)
    cell = plan["cells"][ordinal]
    gate.selected = cell["cell_id"]
    gate.argv[gate.argv.index("--cell") + 1] = gate.selected
    monkeypatch.setattr(ci, "_require_ci_context", lambda *_: pytest.fail("prefix reached host authority"))
    for options in ((), ("--check-inputs",), ("--execute",)):
        assert cli(gate, *options) == 2
    for mode in (None, "--admit", "--retain"):
        assert boundary(gate, capsys, monkeypatch, mode)[0] == 2
    with pytest.raises(adapter.PilotGradingInputRefused, match="registered_cell_controls_refused"):
        adapter.compile_cell_grading_plan(ci.CAMPAIGN, gate.selected, SOURCE)
    with pytest.raises(ci.CICellRefused, match="ci_prefix_cell_out_of_scope"):
        retained._binding(plan, cell, {})
    with pytest.raises(ci.CICellRefused, match="ci_prefix_cell_out_of_scope"):
        retained._predecessor(gate.api, gate.api.repo, retained.BOOTSTRAP, plan, cell, {},
                              gate.host, TOKEN, time.monotonic() + 30)
    assert gate.api.calls == gate.transport.calls == gate.transport.source_checks == []
    assert not gate.root.exists()


@pytest.mark.parametrize("field,value", [("campaign_id", EPOCH03), ("inference_branch", INFERENCE03),
                                        ("first_ordinal", 0)])
def test_closed_registration_rejects_epoch_or_entrypoint_mixture(gate, monkeypatch, field, value):
    registration = yaml.safe_load(ci._registration_bytes())
    section = registration if field == "campaign_id" else registration["entrypoint" if field == "first_ordinal" else "storage"]
    section[field] = value
    original = pilot._read_bytes
    monkeypatch.setattr(pilot, "_read_bytes", lambda path, **kwargs:
        yaml.safe_dump(registration).encode() if Path(path) == ci.REGISTRATION else original(path, **kwargs))
    with pytest.raises(ValueError):
        ci.compile_ci_cell(ci.CAMPAIGN, FIRST, SOURCE)
    with pytest.raises(ValueError):
        grading.compile_request("pilot/inference-branch-setup", SOURCE)
    assert gate.api.calls == gate.transport.calls == gate.transport.source_checks == []
    assert not gate.root.exists()


@pytest.mark.parametrize("damage", [None, "create_lost", "generic_404"], ids=["verified", "lost", "not_genuine_absence"])
def test_each_fixed_ref_setup_is_independent_one_use(setup_case, monkeypatch, capsys, damage):
    # The installed SDK/bounded client runs only through setup_case's fake HTTP;
    # the autouse socket/model/grader boundaries remain forbidden.
    monkeypatch.setattr(output, "_hf_client", REAL_HF_CLIENT)
    s = setup_case
    s.damage = damage
    code, observed = setup_cli(s, capsys)
    expected_calls = [("GET", retained.BOOTSTRAP), ("GET", retained.BRANCH)]
    if damage != "generic_404":
        expected_calls += [("POST", retained.BRANCH)]
    if damage is None:
        expected_calls += [("GET", retained.BRANCH)]
    assert s.calls == expected_calls and code == (0 if damage is None else 2)
    assert grading.BRANCH not in s.branches
    assert observed["outcome"] == ("acknowledged" if damage is None else "unresolved")
    before = {path.name: path.read_bytes() for path in s.root.iterdir()}
    assert setup_cli(s, capsys)[0] == 2 and s.calls == expected_calls
    assert before == {path.name: path.read_bytes() for path in s.root.iterdir()}
    if damage == "generic_404":
        assert s.creates == [] and observed["stage"] == "branch_absence"
        assert observed["reason"] == "grading_branch_absence_not_established"
        return
    first_root = s.root
    s.root, s.damage = first_root.with_name("separate-grade-ref-reservation"), None
    code, grade = setup_cli(s, capsys, "pilot/branch-setup")
    assert code == 0 and grade["stage"] == "branch_verified"
    assert s.calls[len(expected_calls):] == [("GET", retained.BOOTSTRAP), ("GET", grading.BRANCH),
                                            ("POST", grading.BRANCH), ("GET", grading.BRANCH)]
    assert s.branches == {retained.BRANCH: retained.BOOTSTRAP, grading.BRANCH: retained.BOOTSTRAP}
    assert s.creates == [retained.BRANCH, grading.BRANCH]
    for root, ref in ((first_root, retained.BRANCH), (s.root, grading.BRANCH)):
        reserved = retained._read(root / "branch-reserved.json")
        assert reserved["campaign_id"] == ci.CAMPAIGN and reserved["branch"] == ref
        assert reserved["source_sha"] == SOURCE and reserved["bootstrap"] == retained.BOOTSTRAP
    assert before == {path.name: path.read_bytes() for path in first_root.iterdir()}


def test_first6_retains_original_bytes_then_binds_first_grade_and_next7(gate, monkeypatch, capsys):
    s = gate
    finalized(s, capsys, monkeypatch)
    plan, cell = read_plan(s), read_plan(s)["cells"][6]
    original_state, completion_bytes = read_state(s, FIRST), s.envelope.read_bytes()
    admission = retained._read(cell_root(s) / retained.ADMISSION_RECEIPT)["claim"]
    assert admission["binding"]["ordinal"] == 6
    assert admission["expected_parent"] == retained.BOOTSTRAP and admission["predecessor"] is None
    inputs = output._checkpoint(s.root / "ci-inputs.json")
    for field, old in (("campaign_id", EPOCH03), ("source_sha", SOURCE03), ("inference_branch", INFERENCE03)):
        damaged = copy.deepcopy(admission)
        damaged["binding"][field] = old
        with pytest.raises(output.OutputPublicationRefused, match="claim_identity_mismatch"):
            retained._claim(damaged, plan, cell, inputs)
    with pytest.raises(output.OutputPublicationRefused, match="first_cell_bootstrap_required"):
        retained._claim({**admission, "expected_parent": "a" * 40}, plan, cell, inputs)
    with pytest.raises(output.OutputPublicationRefused, match="first_cell_bootstrap_required"):
        retained._predecessor(s.api, s.api.repo, "a" * 40, plan, cell, inputs,
                              s.host, TOKEN, time.monotonic() + 30)
    old_cell = {**cell, "run_id": EPOCH03 + "__" + FIRST}
    for paths in (retained._paths, grading._paths):
        with pytest.raises(output.OutputPublicationRefused, match="retained_epoch_mismatch"):
            paths(old_cell)
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    terminal = s.api.branches[retained.BRANCH]
    receipt = retained._read(cell_root(s) / output.RECEIPT)
    assert receipt["outcome"] == "acknowledged" and receipt["inference_branch"] == retained.BRANCH
    tree = s.api.trees[receipt["returned_commit"]]
    prefix = retained._paths(cell)[2] + "/"
    assert tree[prefix + "step2_inference_results.json"] == s.transport.result_bytes
    assert tree[prefix + Path(pilot.LEDGER).name] == s.transport.ledger_bytes
    assert DELIVERABLE in tree.values()
    assert read_state(s, FIRST) == original_state and s.envelope.read_bytes() == completion_bytes
    assert all(read_state(s, other["cell_id"]) == pilot._cell_state(plan, other) for other in plan["cells"] if other != cell)
    assert s.api.events == ["admission", "child", "child", "output", "terminal"]
    inference_tree = copy.deepcopy(s.api.trees[terminal])
    context, evidence, materialized, identity_sha = _grade_inputs(s, terminal, monkeypatch, None)
    assert context.cell["index"] == 6 and context.run.command[2] == "pilot/cell-06"
    assert evidence["observation"]["output_commit"] == receipt["returned_commit"] != terminal
    assert materialized["source_identity"]["source_revision"] == receipt["returned_commit"]
    # Only unchanged native/source entry readiness is substituted; the input
    # bytes/materializer and per-cell grading claim/binding/CAS are real.
    prepared = {"evidence": evidence, "identity_sha256": identity_sha, "materialization": materialized,
        "entry": {"grader_source_hash": "4" * 64, "config_hash": "5" * 64, "renderer_fingerprint": {}}}
    with monkeypatch.context() as grade_host:
        grading_environment(grade_host)
        grade_host.setenv("HF_TOKEN", TOKEN)
        grade_root = grading._root(s.host / "grade-claim", new=True)
        grade_host.setattr(grading, "_ready", lambda *_: prepared)
        claimed = grading.claim(context, grade_root, _test_api=s.api)
        assert claimed["outcome"] == "acknowledged" and claimed["claim"]["predecessor"] is None
        assert claimed["claim"]["expected_parent"] == retained.BOOTSTRAP
        binding = claimed["claim"]["binding"]
        grading._validate_binding(binding, context, prepared["entry"])
        assert binding["branch"] == grading.BRANCH and binding["inference_branch"] == retained.BRANCH
        for field, old in (("campaign_id", EPOCH03), ("source_sha", SOURCE03),
                           ("branch", GRADING03), ("inference_branch", INFERENCE03)):
            with pytest.raises(output.OutputPublicationRefused, match="grade_claim_contract_mismatch"):
                grading._validate_binding({**binding, field: old}, context, prepared["entry"])
        with pytest.raises(FileExistsError):
            grading.claim(context, grade_root, _test_api=s.api)
    assert s.api.branches[retained.BRANCH] == terminal and s.api.trees[terminal] == inference_tree
    assert s.transport.turns == 1 and len(s.transport.calls) == 2
    select_fresh(s, monkeypatch, ordinal=7)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 0
    next_claim = retained._read(cell_root(s) / retained.ADMISSION_RECEIPT)["claim"]
    assert next_claim["binding"]["ordinal"] == 7 and next_claim["predecessor"]["cell_id"] == FIRST
    assert next_claim["expected_parent"] == next_claim["predecessor"]["terminal_commit"] == terminal
    assert s.transport.calls == []  # Structural next-cell admission is not a launcher.


@pytest.mark.parametrize("damage", ["bootstrap", "claim_only", "output_lost", "source", "epoch", "branch"])
def test_next7_requires_actual04_terminal_and_never_adopts_unknown_output(gate, monkeypatch, capsys, damage):
    s = gate
    lost_bytes = lost_path = None
    if damage == "bootstrap":
        prepare(s)
    elif damage == "claim_only":
        admitted(s, capsys, monkeypatch)
    else:
        finalized(s, capsys, monkeypatch)
        if damage == "output_lost":
            s.api.lost = "output"
        assert boundary(s, capsys, monkeypatch, "--retain")[0] == (2 if damage == "output_lost" else 0)
        if damage == "output_lost":
            lost_path = cell_root(s) / retained.TERMINAL_RECEIPT
            lost_bytes = lost_path.read_bytes()
            assert json.loads(lost_bytes)["outcome"] == "unresolved"
            assert retained._read(cell_root(s) / output.RECEIPT)["outcome"] == "unresolved"
            assert not any(path.endswith("/terminal.json") for path in s.api.trees[s.api.branches[retained.BRANCH]])
            assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
        else:
            head = s.api.branches[retained.BRANCH]
            path = retained._paths(read_plan(s)["cells"][6])[1]
            terminal = json.loads(s.api.trees[head][path])
            if damage == "branch":
                terminal["inference_branch"] = INFERENCE03
            else:
                terminal["completion"]["source_sha" if damage == "source" else "campaign_id"] = SOURCE03 if damage == "source" else EPOCH03
            s.api.trees[head][path] = retained._encoded(terminal)
    commits = list(s.api.commits)
    if damage != "bootstrap":
        select_fresh(s, monkeypatch, same_cell=True)
        assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
        assert s.transport.calls == [] and s.api.commits == commits
    select_fresh(s, monkeypatch, ordinal=7)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
    assert s.api.commits == commits and s.transport.calls == []
    assert not (cell_root(s) / retained.SERVER_OBSERVATION).exists()
    if lost_path is not None:
        assert lost_path.read_bytes() == lost_bytes


def test_lost_terminal_response_keeps_local_receipt_but_verified_server_allows_next7(gate, monkeypatch, capsys):
    s = gate
    finalized(s, capsys, monkeypatch)
    s.api.lost = "terminal"
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 2
    path = cell_root(s) / retained.TERMINAL_RECEIPT
    original = path.read_bytes()
    assert json.loads(original)["outcome"] == "unresolved"
    assert retained._read(cell_root(s) / output.RECEIPT)["outcome"] == "acknowledged"
    terminal = s.api.branches[retained.BRANCH]
    select_fresh(s, monkeypatch, same_cell=True)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
    select_fresh(s, monkeypatch, ordinal=7)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 0
    observation = retained._read(cell_root(s) / retained.SERVER_OBSERVATION)
    assert observation["predecessor"]["terminal_commit"] == terminal
    assert observation["predecessor"]["cell_id"] == FIRST
    assert observation["writer_response_delivery"] == "not_asserted"
    assert path.read_bytes() == original and s.transport.calls == []


def test_grading_prefix_tip_is_unknown_not_an_invented_earlier_grade(gate, tmp_path):
    context = grading.compile_request("pilot/" + FIRST, SOURCE, "c" * 40)
    prefix_path = grading._paths(context.plan["cells"][0])[1]
    head = "d" * 40
    gate.api.seed(head, retained.BOOTSTRAP, {prefix_path: b"synthetic forbidden prefix control"})
    gate.api.branches[grading.BRANCH] = head
    cache = tmp_path / "grade-tip"
    cache.mkdir(mode=0o700)
    with pytest.raises(output.OutputPublicationRefused, match="unknown_or_unfinished_grading_branch_tip"):
        grading._branch_tip(gate.api, gate.api.repo, context, {}, cache, TOKEN, time.monotonic() + 30)
    paths = gate.api.path_queries[-1]
    assert len(paths) == 24 and prefix_path not in paths
    assert set(paths) == {grading._paths(cell)[1] for cell in context.plan["cells"][6:]}
    assert gate.api.branches[retained.BRANCH] == retained.BOOTSTRAP
    assert gate.api.commits == gate.transport.calls == []
