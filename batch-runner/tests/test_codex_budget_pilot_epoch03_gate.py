"""One offline first-A1 gate: real closed routing, fake external boundaries.

The compiler retains 30 cells; only a later leader decision may authorize the
named A1. These synthetic setup/CAS/retention checks grant no live authority and
do not replay either historical cell. Reuse fixtures, not previous test families.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

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
    OLD_CAMPAIGN, OLD_SOURCE, EpochHF, compiled, epoch_offline, grading_environment,
    setup_case, setup_cli,
)  # noqa: F401 -- existing compiler cache and fake SDK transport fixtures only.
from .test_codex_budget_pilot_failed_retention import CANARY, _local_bytes, _producer
from .test_codex_budget_pilot_grading_branch_inspect import SourceOnly
from .test_codex_budget_pilot_retention import (
    SOURCE, TOKEN, RetainedChildren, boundary, case, cell_root, cli, finalized,
    offline, read_plan, scenario,
)  # noqa: F401 -- live process/auth/network/model/grader boundaries stay forbidden.

BASELINE = "0bb141f3bf93510ccb399800a4aa0901ceb36638"
FIRST = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1_A_r1"
HISTORICAL_FIRST = "02aa1805-c658-4069-8a6a-02dec146063a_A_r1"
EPOCH02 = "budget_pilot_ci_20260924_02"
SOURCE02 = "4aac36b6f92d2a14b8cac02d793356d6687ace6d"
INFERENCE02 = "pilot-inference-20260924-02"
GRADING02 = "pilot-grades-20260924-02"


class GateHF(EpochHF):
    """The existing fake also freezes epoch02 refs/bytes, not just old01."""

    def __init__(self):
        super().__init__()
        for ref, revision in ((INFERENCE02, "8" * 40), (GRADING02, "9" * 40)):
            self.branches[ref] = revision
            self.trees[revision] = {f"cell-claims/{EPOCH02}/{HISTORICAL_FIRST}/frozen": b"epoch02 unresolved"}
            self.writers[revision] = {path: revision for path in self.trees[revision]}
            self.frozen[ref] = (revision, copy.deepcopy(self.trees[revision]))

    def record(self, name, kwargs):
        assert kwargs.get("revision") not in {INFERENCE02, GRADING02, "8" * 40, "9" * 40}
        return super().record(name, kwargs)

    def assert_frozen(self):
        super().assert_frozen()
        for ref in (retained.BRANCH, grading.BRANCH):
            assert all(EPOCH02 not in path for path in self.trees[self.branches[ref]])


@pytest.fixture
def gate(case):
    case.api = GateHF()
    case.transport = RetainedChildren(case.sources, case.ids, case.api)
    yield case
    case.api.assert_frozen()


def test_gate_plan_keeps_thirty_cell_shape_without_launch_authority(gate, monkeypatch, capsys):
    class NoCredentials(dict):
        def get(self, key, *args):
            assert key not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"}
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoCredentials(os.environ))
    assert cli(gate) == 0 and boundary(gate, capsys, monkeypatch)[0] == 0
    plan = read_plan(gate)
    assert gate.api.calls == gate.transport.calls == []
    # Active routing moves; the original epoch03 registration stays historical.
    assert plan["run_id"] == ci.CAMPAIGN == "budget_pilot_ci_20260925_04"
    assert plan["reviewed_source_sha"] == SOURCE  # Synthetic reviewed-host boundary, not a source seal.
    assert gate.selected == plan["order"][6] == FIRST
    assert len(plan["cells"]) == 30 and len(gate.ids) == 5
    assert pilot.ORDER == (("A", 1), ("B", 1), ("C", 1), ("C", 2), ("B", 2), ("A", 2))
    assert plan["order"] == [f"{task}_{arm}_r{repeat}" for task in gate.ids for arm, repeat in pilot.ORDER]
    assert plan["launch_authorized_by_plan"] is plan["grading_launched"] is False
    assert ci.PUBLIC_FIXED["denominator"] == 30 and ci.PUBLIC_FIXED["other_cells_not_run"] == 29
    registration = yaml.safe_load(ci._registration_bytes())
    assert ci.REGISTRATION.name == "codex_external_budget_ci_pilot_epoch04.yaml"
    assert registration["source_baseline"] == BASELINE and registration["selection"] == "one_explicit_canonical_cell"
    assert registration["storage"] == ci.STORAGE == {
        "repository_name_sha256": "a13dedada5465377761961d050e021a4db8e44d6284179a9ce40b562e4396a44",
        "bootstrap": "bfc7ae01ed14490817ceb7cb406adcb9bb95f557",
        "inference_branch": "pilot-inference-20260925-04", "grading_branch": "pilot-grades-20260925-04",
    }
    assert plan["ci"]["registration_sha256"] == hashlib.sha256(ci._registration_bytes()).hexdigest()
    assert {key: plan["model"][key] for key in ("deployment", "route_profile", "reasoning_effort")} == {
        "deployment": "gpt-5.4", "route_profile": "direct-v1", "reasoning_effort": "xhigh"}
    assert ci.HOST_POLICY["sdk"] == ci.HOST_POLICY["cli"] == "0.147.0"
    assert (pilot.TOTAL_SECONDS, pilot.ATTEMPT_SECONDS) == (10800, 1800)
    _, _, specs = pilot.compile_pilot(ci.CAMPAIGN, SOURCE)
    for old_campaign, old_source in ((OLD_CAMPAIGN, OLD_SOURCE), (EPOCH02, SOURCE02)):
        old, _, old_specs = pilot.compile_pilot(old_campaign, old_source)
        assert old["order"] == plan["order"]
        assert {cell["run_id"] for cell in old["cells"]}.isdisjoint(cell["run_id"] for cell in plan["cells"])
        for key in ("model", "dataset", "grading", "source_pins"):
            assert old[key] == plan[key]
        for cell in plan["cells"]:
            current, previous = (json.loads(items[cell["cell_id"]].config_json) for items in (specs, old_specs))
            assert current["experiment"].pop("id") != previous["experiment"].pop("id")
            assert current == previous  # No model/input/attempt/feedback/grader axis changed.
            control = CodexTaskDeadlineControl.from_mapping(current["execution"]["codex"]["task_deadline"])
            assert control.max_attempts == (4 if cell["condition"] == "A" else None)
        with pytest.raises(ci.CICellRefused, match="registered_ci_campaign_required"):
            ci.compile_ci_cell(old_campaign, FIRST, SOURCE)
        with pytest.raises(adapter.PilotGradingInputRefused, match="registered_ci_campaign_required"):
            adapter.compile_cell_grading_plan(old_campaign, FIRST, SOURCE)
    for name, campaign in (("codex_external_budget_ci_pilot.yaml", OLD_CAMPAIGN),
                            ("codex_external_budget_ci_pilot_epoch02.yaml", EPOCH02)):
        assert yaml.safe_load(ci.REGISTRATION.with_name(name).read_bytes())["campaign_id"] == campaign

    workflow = yaml.safe_load((pilot.ROOT / ci.WORKFLOW).read_bytes())
    job = workflow["jobs"]["cell"]
    routed = [step for step in job["steps"] if "--campaign-id " in step.get("run", "")]
    assert [step["id"] for step in routed] == ["plan", "output_target", "output_setup", "intake", "execution"]
    assert all(step["run"].count("--campaign-id " + ci.CAMPAIGN) == 1 for step in routed)
    assert all(EPOCH02 not in step["run"] and OLD_CAMPAIGN not in step["run"] for step in routed)
    assert job["timeout-minutes"] == 240 and "strategy" not in job
    assert workflow["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    assert "--execute" not in routed[0]["run"]
    assert "steps.admission.outputs.admitted == 'true'" in routed[-1]["if"]


@pytest.mark.parametrize("field,old", [("campaign_id", EPOCH02), ("source_baseline", SOURCE02),
    ("inference_branch", INFERENCE02), ("grading_branch", GRADING02)])
def test_mixed_registration_refuses_before_source_or_hf(setup_case, monkeypatch, capsys, field, old):
    registration = yaml.safe_load(ci._registration_bytes())
    (registration if field in registration else registration["storage"])[field] = old
    changed = yaml.safe_dump(registration).encode()
    original = pilot._read_bytes
    monkeypatch.setattr(pilot, "_read_bytes", lambda path, **kwargs:
                        changed if Path(path) == ci.REGISTRATION else original(path, **kwargs))
    assert setup_cli(setup_case, capsys)[0] == 2
    assert setup_case.calls == setup_case.creates == [] and setup_case.source.calls == 0
    assert not setup_case.root.exists()


@pytest.mark.parametrize("selector,branch", [("pilot/inference-branch-setup", "pilot-inference-20260925-04"),
                                             ("pilot/branch-setup", "pilot-grades-20260925-04")])
def test_each_fixed_ref_has_offline_plan_four_request_setup_and_read_only_inspect(setup_case, capsys, monkeypatch, selector, branch):
    s = setup_case
    frozen = {"main": "e" * 40, "pilot-grades-20260923": "f" * 40,
              INFERENCE02: "8" * 40, GRADING02: "9" * 40}
    s.branches.update(frozen)
    with monkeypatch.context() as local:
        local.delenv("HF_TOKEN")
        local.setattr(output, "_hf_client", lambda *a, **k: pytest.fail("plan reached HF"))
        assert setup_cli(s, capsys, selector, "plan")[0] == 0
    assert setup_cli(s, capsys, selector, "inspect")[0] == 2
    assert s.calls == [] and s.source.calls == 0 and not s.root.exists()
    code, record = setup_cli(s, capsys, selector)
    assert code == 0 and record["outcome"] == "acknowledged" and record["branch"] == branch
    assert s.calls == [("GET", retained.BOOTSTRAP), ("GET", branch), ("POST", branch), ("GET", branch)]
    assert s.branches == {**frozen, branch: retained.BOOTSTRAP} and s.creates == [branch]
    reserved = retained._read(s.root / "branch-reserved.json")
    receipt = retained._read(s.root / "branch-receipt.json")
    assert reserved["campaign_id"] == receipt["campaign_id"] == ci.CAMPAIGN
    assert reserved["branch"] == receipt["branch"] == branch
    assert reserved["source_sha"] == receipt["source_sha"] == SOURCE
    assert reserved["bootstrap"] == receipt["returned_commit"] == retained.BOOTSTRAP
    assert receipt["stage"] == "branch_verified"
    before = {path.name: path.read_bytes() for path in s.root.iterdir()}
    assert setup_cli(s, capsys, selector)[0] == 2 and len(s.calls) == 4
    code, record = setup_cli(s, capsys, selector.replace("-setup", "-inspect"), "inspect")
    assert code == 0 and record["branch_state"] == "present" and record["head"] == retained.BOOTSTRAP
    assert record["remote_mutation_possible"] is record["judge_entry_requested"] is False
    assert s.calls[4:] == [("GET", retained.BOOTSTRAP), ("GET", branch)] and s.creates == [branch]
    assert before == {path.name: path.read_bytes() for path in s.root.iterdir()}


@pytest.mark.parametrize("damage,requests,mutated", [("generic_404", 2, False), ("existing", 2, False),
    ("create_lost", 3, True), ("readback_unavailable", 4, True)])
def test_setup_never_adopts_replays_or_creates_the_other_ref(setup_case, capsys, damage, requests, mutated):
    s = setup_case
    s.damage = damage
    if damage == "existing":
        s.branches[retained.BRANCH] = retained.BOOTSTRAP
    code, record = setup_cli(s, capsys)
    assert code == 2 and record["outcome"] != "acknowledged"
    assert len(s.calls) == requests and bool(s.creates) is mutated
    assert grading.BRANCH not in s.branches
    frozen = {path.name: path.read_bytes() for path in s.root.iterdir()}
    assert ("branch-reserved.json" in frozen) is mutated
    assert setup_cli(s, capsys)[0] == 2 and len(s.calls) == requests
    assert frozen == {path.name: path.read_bytes() for path in s.root.iterdir()}


@pytest.mark.parametrize("failed", [False, True], ids=["retained_success", "withheld_failure"])
def test_first_claim_output_and_grade_binding_stay_on_active_refs(gate, capsys, monkeypatch, tmp_path, failed):
    s = gate
    if failed:
        _producer(s, monkeypatch, fields="row")
    finalized(s, capsys, monkeypatch, expected=1 if failed else 0)
    before = _local_bytes(s)
    plan, cell = read_plan(s), read_plan(s)["cells"][ci.FIRST_CELL_ORDINAL]
    claim = retained._read(cell_root(s) / retained.ADMISSION_RECEIPT)["claim"]
    assert claim["expected_parent"] == retained.BOOTSTRAP and claim["predecessor"] is None
    assert claim["binding"]["ordinal"] == 6 and cell["cell_id"] == FIRST
    assert claim["binding"]["campaign_id"] == ci.CAMPAIGN and claim["binding"]["inference_branch"] == retained.BRANCH
    inputs = output._checkpoint(s.root / "ci-inputs.json")
    for field, old in (("campaign_id", EPOCH02), ("source_sha", SOURCE02), ("inference_branch", INFERENCE02)):
        damaged = copy.deepcopy(claim)
        damaged["binding"][field] = old
        with pytest.raises(output.OutputPublicationRefused, match="claim_identity_mismatch"):
            retained._claim(damaged, plan, cell, inputs)
    historical_cell = {**cell, "run_id": EPOCH02 + "__" + FIRST}
    for paths in (retained._paths, grading._paths):
        with pytest.raises(output.OutputPublicationRefused, match="retained_epoch_mismatch"):
            paths(historical_cell)
    snapshot = output.prepare(root=s.root, campaign=ci.CAMPAIGN, cell_id=FIRST, source_sha=SOURCE,
                              config_sha=cell["config_sha256"], _failure_metadata=failed)
    original = copy.deepcopy(snapshot.manifest)
    for field, old in (("campaign_id", EPOCH02), ("inference_branch", INFERENCE02)):
        snapshot.manifest = {**original, "inference_branch": retained.BRANCH, field: old}
        with pytest.raises(output.OutputPublicationRefused, match="retained_output_ref_required"):
            output.publish(snapshot, repo=s.api.repo, expected_parent=s.api.branches[retained.BRANCH],
                           _test_api=s.api, _failure_metadata=failed, _retained_ref=True)
    assert s.api.commits == ["admission"] and not (cell_root(s) / output.RESERVATION).exists()
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0 and _local_bytes(s) == before
    revision = s.api.branches[retained.BRANCH]
    receipt = retained._read(cell_root(s) / output.RECEIPT)
    terminal = json.loads(s.api.trees[revision][retained._paths(cell)[1]])
    assert terminal["inference_branch"] == receipt["inference_branch"] == retained.BRANCH
    assert terminal["output_commit"] == receipt["returned_commit"] != revision
    assert s.api.events == ["admission", "child", "child", "output", "terminal"]
    assert all(CANARY.encode() not in data for tree in s.api.trees.values() for data in tree.values())
    context = grading.compile_request("pilot/" + FIRST, SOURCE, revision)
    if failed:
        manifest = receipt["cell"]
        assert manifest["status"] == "failed" and manifest["files"] == []
        assert manifest["withheld"]["artifacts"] == pilot._load(s.envelope)["artifacts"]
        assert manifest["receipt"]["known_cost_usd"] == 0.01 and manifest["receipt"]["estimated_cost_usd"] is None
        grading_environment(monkeypatch)
        monkeypatch.setenv("HF_TOKEN", TOKEN)
        prepared = grading.prepare(context, tmp_path / "ungraded", _test_api=s.api, _test_transport=SourceOnly())
        monkeypatch.delenv("HF_TOKEN")
        assert prepared["judge_ready"] is False and prepared["reason"] == "retained_result_missing_ungraded"
        assert prepared["inference_branch"] == retained.BRANCH and prepared["grading_branch"] == grading.BRANCH
        assert s.api.branches[grading.BRANCH] == retained.BOOTSTRAP
    else:
        cache = tmp_path / "verified"
        cache.mkdir(mode=0o700)
        monkeypatch.setenv("HF_TOKEN", TOKEN)
        with retained._session(s.api) as (api, token, deadline):
            evidence = grading._retained_input(context, api, api.repo, cache, token, deadline)
            # Synthetic preparation identities; real retained evidence/binding/CAS.
            # This is not native-install, grader invocation or grade-quality proof.
            prepared = {"evidence": evidence, "identity_sha256": "3" * 64,
                "entry": {"grader_source_hash": "4" * 64, "config_hash": "5" * 64, "renderer_fingerprint": {}},
                "materialization": {"materialized_result": {"path": context.run.inference_results_path,
                    "size": 1, "sha256": "6" * 64, "result_fingerprint": "7" * 64}}}
            binding = grading._binding(context, prepared, {"id": "99", "job": "grade", "attempt": 1})
            grading._validate_binding(binding, context, prepared["entry"])
            assert binding["branch"] == grading.BRANCH and binding["inference_branch"] == retained.BRANCH
            for field, old in (("campaign_id", EPOCH02), ("source_sha", SOURCE02),
                              ("branch", GRADING02), ("inference_branch", INFERENCE02)):
                with pytest.raises(output.OutputPublicationRefused, match="grade_claim_contract_mismatch"):
                    grading._validate_binding({**binding, field: old}, context, prepared["entry"])
            record = {"format": grading.CLAIM_FORMAT, "binding": binding,
                      "expected_parent": retained.BOOTSTRAP, "predecessor": None}
            committed = grading._commit(api, api.repo, retained.BOOTSTRAP,
                {grading._paths(cell)[0]: retained._encoded(record)}, token, deadline, {})
        monkeypatch.delenv("HF_TOKEN")
        assert committed == s.api.branches[grading.BRANCH]
    assert s.api.branches[retained.BRANCH] == revision
    assert len(s.transport.calls) == 2  # Prepare + infer for only A1; no successor is dispatched.
