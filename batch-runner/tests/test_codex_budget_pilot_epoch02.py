"""Closed epoch02 preparation, not live setup or a replacement campaign run.

Real compiler, serialization, deadline, CAS, terminal and grading validators;
synthetic inputs/outputs, source capability, child and HF boundaries. The HTTP
cases use the installed SDK and real bounded transport with fake responses.
No native installation, model, judge, original payload or credential is used.
"""

from __future__ import annotations

import copy
from functools import lru_cache
import json
import os
from pathlib import Path
import signal
from types import SimpleNamespace

import httpx
from huggingface_hub import HfApi, constants
import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading as grading
import codex_budget_pilot_grading_input as adapter
import codex_budget_pilot_output as output
import codex_budget_pilot_retention as retained
from .test_codex_budget_pilot_retention import (
    SOURCE, TOKEN, MemoryHF, RetainedChildren, boundary, case, cell_root, cli,
    finalized, offline, prepare, read_plan, scenario, select_fresh,
)  # noqa: F401 -- fixtures only; no previous family is selected.
from .test_codex_budget_pilot_failed_retention import CANARY, _local_bytes, _producer
from .test_codex_budget_pilot_grading import GradeHF
from .test_codex_budget_pilot_grading_branch_inspect import SourceOnly

OLD_CAMPAIGN = "budget_pilot_ci_20260923_01"
OLD_SOURCE = "2fe1c6925e6d76c03b85851046d52216bee74a16"
OLD_GRADE = "pilot-grades-20260923"
RAW = "SYNTHETIC_PRIVATE_RESPONSE https://private.invalid/?token=secret /private/path"
REAL_INFO, REAL_CREATE = HfApi.repo_info, HfApi.create_branch
REAL_COMPILE = pilot.compile_pilot


@pytest.fixture(scope="module")
def compiled():
    # Cache genuine, deterministic compiles only; each caller gets its own copy.
    return lru_cache(maxsize=8)(REAL_COMPILE)


@pytest.fixture(autouse=True)
def epoch_offline(monkeypatch, compiled, offline):
    monkeypatch.setattr(pilot, "compile_pilot", lambda *args: copy.deepcopy(compiled(*args)))

    def forbidden(*args, **kwargs):
        pytest.fail("epoch02 test reached a forbidden live boundary")

    for name in ("create_branch", "delete_branch", "delete_repo", "list_repo_refs", "list_repo_files",
                 "upload_file", "upload_folder"):
        monkeypatch.setattr(HfApi, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(key, raising=False)


def grading_environment(monkeypatch):
    for name, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
        "GITHUB_SHA": SOURCE, "PILOT_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + grading.WORKFLOW + "@refs/heads/main",
        "PILOT_GRADE_PAID_APPROVAL": "true", "PILOT_GRADE_DRY_RUN": "false",
        "GITHUB_RUN_ID": "90001", "GITHUB_JOB": "pilot-live",
        "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
        "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0",
        "GRADE_SHARD_COUNT": "1", "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1",
    }.items():
        monkeypatch.setenv(name, value)


class EpochHF(GradeHF):
    """Reuse the add-only fakes, with distinct inference/grade/protected refs."""

    def __init__(self):
        super().__init__()
        self.branches.update({retained.BRANCH: retained.BOOTSTRAP, "main": "e" * 40, OLD_GRADE: "f" * 40})
        for ref in ("main", OLD_GRADE):
            revision = self.branches[ref]
            self.trees[revision] = {f"cell-claims/{OLD_CAMPAIGN}/frozen": b"old01 remains unresolved"}
            self.writers[revision] = {path: revision for path in self.trees[revision]}
        self.frozen = {ref: (self.branches[ref], copy.deepcopy(self.trees[self.branches[ref]]))
                       for ref in ("main", OLD_GRADE)}

    def repo_info(self, **kwargs):
        self.record("metadata", kwargs)
        assert 0 < kwargs["timeout"] <= output.REQUEST_SECONDS
        requested = kwargs["revision"]
        assert requested not in {"main", OLD_GRADE}, "old refs are not epoch02 inputs"
        revision = self.branches.get(requested, requested)
        if revision not in self.trees:
            raise output.OutputPublicationRefused("hf_revision_not_found", 404)
        return SimpleNamespace(id=self.repo if self.id_matches else "synthetic-foreign/repo",
                               private=self.private, sha=revision)

    def create_commit(self, **kwargs):
        assert kwargs["revision"] in {retained.BRANCH, grading.BRANCH}
        if kwargs["revision"] == grading.BRANCH:
            return super().create_commit(**kwargs)
        self.head = self.branches[retained.BRANCH]
        try:
            return MemoryHF.create_commit(self, **kwargs)
        finally:
            # A lost response can still leave a durable server-side commit.
            self.branches[retained.BRANCH] = self.head

    def assert_frozen(self):
        assert self.frozen == {ref: (self.branches[ref], self.trees[self.branches[ref]]) for ref in self.frozen}
        assert not any(revision in {"main", OLD_GRADE} for _, revision in self.calls)
        for ref in (retained.BRANCH, grading.BRANCH):
            assert all(OLD_CAMPAIGN not in path for path in self.trees[self.branches[ref]])


@pytest.fixture
def epoch(case):
    case.api = EpochHF()
    case.transport = RetainedChildren(case.sources, case.ids, case.api)
    yield case
    case.api.assert_frozen()


@pytest.fixture
def setup_case(tmp_path, monkeypatch):
    grading_environment(monkeypatch)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    state = SimpleNamespace(root=tmp_path / "one-ref", source=SourceOnly(), repo=retained._target(),
                            calls=[], branches={}, creates=[], damage=None)

    def info(api, **kwargs):
        assert kwargs["repo_id"] == state.repo and kwargs["repo_type"] == "dataset" and kwargs["token"] == TOKEN
        assert kwargs["revision"] in {retained.BOOTSTRAP, retained.BRANCH, grading.BRANCH}
        return REAL_INFO(api, **kwargs)

    def create(api, **kwargs):
        assert kwargs["revision"] == retained.BOOTSTRAP and kwargs["exist_ok"] is False
        assert kwargs["branch"] in {retained.BRANCH, grading.BRANCH}
        if state.damage == "create_parent":
            kwargs["revision"] = "main"
        return REAL_CREATE(api, **kwargs)

    def request(transport, message):
        assert str(message.url).startswith(f"https://huggingface.co/api/datasets/{state.repo}/")
        assert not message.url.query and message.headers["authorization"] == "Bearer " + TOKEN
        assert constants.HF_HUB_OFFLINE is False and os.environ["HF_HUB_OFFLINE"] == "0"
        assert not {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}.intersection(os.environ)
        assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= output.PUBLICATION_SECONDS
        assert all(0 < limit <= output.REQUEST_SECONDS for limit in message.extensions["timeout"].values())
        ref = message.url.path.rsplit("/", 1)[-1]
        state.calls.append((message.method, ref))
        if message.method == "POST":
            assert ref in {retained.BRANCH, grading.BRANCH} and ref not in state.branches
            assert json.loads(message.content) == {"startingPoint": retained.BOOTSTRAP}
            state.creates.append(ref)
            state.branches[ref] = retained.BOOTSTRAP
            if state.damage == "create_lost":
                raise httpx.ConnectError(RAW)
            return httpx.Response(200, json={})
        assert message.method == "GET" and not message.content
        if ref == retained.BOOTSTRAP and state.damage == "bootstrap_missing":
            return httpx.Response(404, headers={"X-Error-Code": "RevisionNotFound"}, text=RAW)
        if ref != retained.BOOTSTRAP and ref not in state.branches:
            status = 403 if state.damage == "branch_forbidden" else 307 if state.damage == "branch_redirect" else 404
            headers = {"location": "https://private.invalid/"}
            if state.damage != "generic_404":
                headers["X-Error-Code"] = "RevisionNotFound"
            return httpx.Response(status, headers=headers, text=RAW)
        if ref != retained.BOOTSTRAP and state.damage == "readback_unavailable":
            raise httpx.ConnectError(RAW)
        head = retained.BOOTSTRAP if ref == retained.BOOTSTRAP else state.branches[ref]
        if ref != retained.BOOTSTRAP and state.damage == "readback_drift":
            head = "a" * 40
        return httpx.Response(200, json={
            "id": "synthetic-foreign/repo" if state.damage == "foreign" else state.repo,
            "private": state.damage != "public", "sha": head, "siblings": [],
        })

    monkeypatch.setattr(HfApi, "repo_info", info)
    monkeypatch.setattr(HfApi, "create_branch", create)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", request)
    return state


def setup_cli(s, capsys, selector="pilot/inference-branch-setup", phase="setup"):
    before = dict(os.environ)
    code = grading.main(["--selector", selector, "--phase", phase, "--reviewed-source-sha", SOURCE,
                         "--root", str(s.root)], _test_transport=s.source)
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert not any(secret in text for secret in (TOKEN, RAW, s.repo, str(s.root)))
    assert dict(os.environ) == before and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    record = json.loads(text)
    assert record["inference_requested"] is record["automatic_retry"] is False
    return code, record


def test_epoch02_plan_is_closed_independent_and_offline(epoch, monkeypatch, capsys):
    class NoCredentials(dict):
        def get(self, key, *args):
            assert key not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoCredentials(os.environ))
    assert cli(epoch) == 0
    plan = read_plan(epoch)
    assert boundary(epoch, capsys, monkeypatch)[0] == 0
    assert epoch.api.calls == epoch.transport.calls == []
    assert plan["run_id"] == ci.CAMPAIGN == "budget_pilot_ci_20260924_02"
    assert len(plan["cells"]) == 30 and len({cell["task_id"] for cell in plan["cells"]}) == 5
    assert [(row["condition"], row["repetition"]) for row in plan["cells"][:6]] == list(pilot.ORDER)
    old_plan, _, _ = pilot.compile_pilot(OLD_CAMPAIGN, OLD_SOURCE)
    assert old_plan["order"] == plan["order"]
    assert {row["run_id"] for row in old_plan["cells"]}.isdisjoint(row["run_id"] for row in plan["cells"])
    assert all(new["config_sha256"] != old["config_sha256"] for new, old in zip(plan["cells"], old_plan["cells"]))
    for key in ("model", "dataset", "grading"):
        assert plan[key] == old_plan[key]
    assert yaml.safe_load(ci._registration_bytes())["storage"] == ci.STORAGE
    historical = ci.REGISTRATION.with_name("codex_external_budget_ci_pilot.yaml")
    assert yaml.safe_load(historical.read_bytes())["campaign_id"] == OLD_CAMPAIGN
    with pytest.raises(ci.CICellRefused, match="registered_ci_campaign_required"):
        ci.compile_ci_cell(OLD_CAMPAIGN, epoch.selected, SOURCE)
    with pytest.raises(adapter.PilotGradingInputRefused, match="registered_ci_campaign_required"):
        adapter.compile_cell_grading_plan(OLD_CAMPAIGN, epoch.selected, SOURCE)


@pytest.mark.parametrize("selector", tuple(grading.BRANCH_ROUTES))
def test_branch_plans_do_not_lookup_tokens_and_cross_use_is_closed(setup_case, monkeypatch, capsys, selector):
    s = setup_case
    class NoCredentials(dict):
        def get(self, key, *args):
            assert key not in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}
            return super().get(key, *args)

    monkeypatch.setattr(output, "_hf_client", lambda *args, **kwargs: pytest.fail("plan reached HF"))
    monkeypatch.delenv("HF_TOKEN")
    monkeypatch.setattr(os, "environ", NoCredentials(os.environ))
    assert setup_cli(s, capsys, selector, "plan")[0] == 0
    other = "inspect" if grading.BRANCH_ROUTES[selector][0] == "setup" else "setup"
    code, record = setup_cli(s, capsys, selector, other)
    assert code == 2 and record["reason"] == "pilot_grade_mode_conflict"
    assert s.calls == s.creates == [] and s.source.calls == 0 and not s.root.exists()


@pytest.mark.parametrize("field", ["campaign_id", "source_baseline", "inference_branch", "grading_branch",
                                   "bootstrap", "repository_name_sha256"])
def test_registration_mixture_refuses_before_source_token_or_mutation(setup_case, monkeypatch, capsys, field):
    document = yaml.safe_load(ci._registration_bytes())
    if field in document:
        document[field] = OLD_CAMPAIGN if field == "campaign_id" else OLD_SOURCE
    else:
        document["storage"][field] = "main"
    changed = yaml.safe_dump(document).encode()
    original = pilot._read_bytes
    monkeypatch.setattr(pilot, "_read_bytes", lambda path, **kwargs:
                        changed if Path(path) == ci.REGISTRATION else original(path, **kwargs))
    assert setup_cli(setup_case, capsys)[0] == 2
    assert setup_case.calls == setup_case.creates == [] and setup_case.source.calls == 0
    assert not setup_case.root.exists()


@pytest.mark.parametrize("selector,branch", [("pilot/inference-branch-setup", retained.BRANCH),
                                             ("pilot/branch-setup", grading.BRANCH)])
def test_one_exact_ref_setup_uses_real_sdk_transport_and_own_receipt(setup_case, capsys, selector, branch):
    s = setup_case
    code, record = setup_cli(s, capsys, selector)
    assert code == 0 and record["outcome"] == "acknowledged" and record["branch"] == branch
    assert s.calls == [("GET", retained.BOOTSTRAP), ("GET", branch), ("POST", branch), ("GET", branch)]
    assert s.branches == {branch: retained.BOOTSTRAP} and s.creates == [branch]
    reserved = retained._read(s.root / "branch-reserved.json")
    receipt = retained._read(s.root / "branch-receipt.json")
    assert reserved["campaign_id"] == ci.CAMPAIGN and reserved["branch"] == branch
    assert reserved["bootstrap"] == receipt["returned_commit"] == retained.BOOTSTRAP
    assert reserved["source_sha"] == receipt["source_sha"] == SOURCE
    assert receipt["http_status"] == 200 and receipt["stage"] == "branch_verified"
    before = {path.name: path.read_bytes() for path in s.root.iterdir()}
    assert setup_cli(s, capsys, selector)[0] == 2
    assert len(s.calls) == 4 and s.creates == [branch]
    assert before == {path.name: path.read_bytes() for path in s.root.iterdir()}


@pytest.mark.parametrize("damage,requests,mutated", [
    ("public", 1, False), ("foreign", 1, False), ("bootstrap_missing", 1, False),
    ("generic_404", 2, False), ("branch_forbidden", 2, False), ("branch_redirect", 2, False),
    ("existing", 2, False), ("create_parent", 2, False), ("create_lost", 3, True),
    ("readback_unavailable", 4, True), ("readback_drift", 4, True),
])
def test_setup_refusals_keep_reservation_and_never_create_other_ref(setup_case, capsys, damage, requests, mutated):
    s = setup_case
    s.damage = damage
    if damage == "existing":
        s.branches[retained.BRANCH] = retained.BOOTSTRAP
    code, record = setup_cli(s, capsys)
    assert code == 2 and record["outcome"] != "acknowledged"
    assert len(s.calls) == requests and bool(s.creates) is mutated
    assert grading.BRANCH not in s.branches
    if damage in {"create_parent", "create_lost", "readback_unavailable"}:
        stage = "branch_readback" if damage == "readback_unavailable" else "branch_create"
        assert record["stage"] == stage and record["http_status"] is None
        receipt = retained._read(s.root / "branch-receipt.json")
        assert receipt["stage"] == stage and receipt["http_status"] is None
        responses = [{"stage": "bootstrap_metadata", "http_status": 200},
                     {"stage": "branch_absence", "http_status": 404}]
        if damage == "readback_unavailable":
            responses.append({"stage": "branch_create", "http_status": 200})
        assert receipt["responses"] == responses
    before = {path.name: path.read_bytes() for path in s.root.iterdir()}
    assert setup_cli(s, capsys)[0] == 2 and len(s.calls) == requests
    assert before == {path.name: path.read_bytes() for path in s.root.iterdir()}
    if mutated:
        assert "branch-reserved.json" in before and s.branches[retained.BRANCH] == retained.BOOTSTRAP
        # A fresh runner/root can observe existence but cannot adopt/recreate it.
        s.root = s.root.with_name("separate-attempt")
        s.damage = None
        assert setup_cli(s, capsys)[0] == 2 and len(s.creates) == 1


@pytest.mark.parametrize("present", [False, True])
def test_inference_inspection_is_two_reads_not_setup_or_acknowledgment(setup_case, capsys, present):
    s = setup_case
    if present:
        s.branches[retained.BRANCH] = retained.BOOTSTRAP
    code, record = setup_cli(s, capsys, "pilot/inference-branch-inspect", "inspect")
    assert code == 0 and record["branch_state"] == ("present" if present else "absent")
    assert record["branch"] == retained.BRANCH and record["bootstrap_access_verified"] is True
    assert record["remote_mutation_possible"] is record["judge_entry_requested"] is False
    assert record["head"] == (retained.BOOTSTRAP if present else None)
    assert s.calls == [("GET", retained.BOOTSTRAP), ("GET", retained.BRANCH)]
    assert not s.root.exists() and s.creates == []


def test_real_retention_predecessor_and_grading_cas_use_distinct_refs(epoch, capsys, monkeypatch, tmp_path):
    s = epoch
    finalized(s, capsys, monkeypatch)
    before = _local_bytes(s)
    assert boundary(s, capsys, monkeypatch, "--retain")[0] == 0
    assert _local_bytes(s) == before
    plan, cell = read_plan(s), read_plan(s)["cells"][0]
    revision = s.api.branches[retained.BRANCH]
    claim = retained._read(cell_root(s) / retained.ADMISSION_RECEIPT)["claim"]
    terminal = json.loads(s.api.trees[revision][retained._paths(cell)[1]])
    assert claim["binding"]["inference_branch"] == terminal["inference_branch"] == retained.BRANCH
    assert claim["expected_parent"] == retained.BOOTSTRAP and claim["predecessor"] is None
    assert s.api.events == ["admission", "child", "child", "output", "terminal"]
    inputs = output._checkpoint(s.root / "ci-inputs.json")
    for field, wrong in (("campaign_id", OLD_CAMPAIGN), ("source_sha", OLD_SOURCE), ("inference_branch", "main")):
        damaged = copy.deepcopy(claim)
        damaged["binding"][field] = wrong
        with pytest.raises(output.OutputPublicationRefused, match="claim_identity_mismatch"):
            retained._claim(damaged, plan, cell, inputs)
    context = grading.compile_request("pilot/" + s.selected, SOURCE, revision)
    cache = tmp_path / "verified"
    cache.mkdir(mode=0o700)
    monkeypatch.setenv("HF_TOKEN", TOKEN)
    with retained._session(s.api) as (api, token, deadline):
        evidence = grading._retained_input(context, api, api.repo, cache, token, deadline)
        # Synthetic prepared identity, not native-install/judge readiness. The
        # real binding validator and add-only grading CAS are the tested seam.
        prepared = {"evidence": evidence, "identity_sha256": "3" * 64,
            "entry": {"grader_source_hash": "4" * 64, "config_hash": "5" * 64, "renderer_fingerprint": {}},
            "materialization": {"materialized_result": {"path": context.run.inference_results_path,
                "size": 1, "sha256": "6" * 64, "result_fingerprint": "7" * 64}}}
        binding = grading._binding(context, prepared, {"id": "99", "job": "grade", "attempt": 1})
        grading._validate_binding(binding, context, prepared["entry"])
        assert binding["branch"] == grading.BRANCH and binding["inference_branch"] == retained.BRANCH
        for field, wrong in (("campaign_id", OLD_CAMPAIGN), ("source_sha", OLD_SOURCE),
                              ("branch", OLD_GRADE), ("inference_branch", "main")):
            with pytest.raises(output.OutputPublicationRefused, match="grade_claim_contract_mismatch"):
                grading._validate_binding({**binding, field: wrong}, context, prepared["entry"])
        record = {"format": grading.CLAIM_FORMAT, "binding": binding,
                  "expected_parent": retained.BOOTSTRAP, "predecessor": None}
        committed = grading._commit(api, api.repo, retained.BOOTSTRAP,
            {grading._paths(cell)[0]: retained._encoded(record)}, token, deadline, {})
    monkeypatch.delenv("HF_TOKEN")
    assert committed == s.api.branches[grading.BRANCH] and s.api.branches[retained.BRANCH] == revision
    select_fresh(s, monkeypatch, ordinal=1)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 0
    admitted = retained._read(cell_root(s) / retained.ADMISSION_RECEIPT)["claim"]
    assert admitted["predecessor"]["terminal_commit"] == admitted["expected_parent"] == revision
    assert admitted["predecessor"]["cell_id"] == plan["order"][0]
    assert s.transport.calls == []  # Admission never invokes a paid child.
    select_fresh(s, monkeypatch, same_cell=True)
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2 and s.transport.calls == []


@pytest.mark.parametrize("damage", ["private", "parent", "skip", "old_claim", "mixed_source"])
def test_epoch02_admission_refuses_before_child(epoch, monkeypatch, capsys, damage):
    s = epoch
    if damage == "skip":
        s.selected = s.ids[0] + "_B_r1"
        s.argv[s.argv.index("--cell") + 1] = s.selected
    prepare(s)
    if damage == "private":
        s.api.private = False
    elif damage == "parent":
        s.api.branches[retained.BRANCH] = "d" * 40
        s.api.trees["d" * 40], s.api.writers["d" * 40] = {}, {}
    elif damage == "old_claim":
        path = retained._paths(read_plan(s)["cells"][0])[0]
        s.api.trees[retained.BOOTSTRAP][path] = retained._encoded({"campaign_id": OLD_CAMPAIGN})
        s.api.writers[retained.BOOTSTRAP][path] = retained.BOOTSTRAP
    elif damage == "mixed_source":
        plan = read_plan(s)
        plan["reviewed_source_sha"] = OLD_SOURCE
        (s.root / "plan.json").write_bytes(retained._encoded(plan))
    assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2
    assert not s.api.commits and not s.transport.calls


@pytest.mark.parametrize("lost_output", [False, True])
def test_epoch02_withholding_stays_failed_ungraded_and_ambiguity_blocks_next(epoch, capsys, monkeypatch, tmp_path, lost_output):
    s = epoch
    _producer(s, monkeypatch, fields="row")
    finalized(s, capsys, monkeypatch, expected=1)
    before = _local_bytes(s)
    if lost_output:
        s.api.lost = "output"
    code, _ = boundary(s, capsys, monkeypatch, "--retain")
    assert code == (2 if lost_output else 0) and _local_bytes(s) == before
    receipt = retained._read(cell_root(s) / output.RECEIPT)
    manifest = receipt["cell"]
    assert manifest["inference_branch"] == receipt["inference_branch"] == retained.BRANCH
    assert manifest["files"] == [] and manifest["withheld"]["artifacts"] == pilot._load(s.envelope)["artifacts"]
    assert manifest["status"] == "failed" and manifest["receipt"]["status"] == "partial"
    assert manifest["receipt"]["known_cost_usd"] == 0.01 and manifest["receipt"]["estimated_cost_usd"] is None
    assert manifest["grade_ready"] is manifest["grading_launched"] is False
    assert all(CANARY.encode() not in data for tree in s.api.trees.values() for data in tree.values())
    if lost_output:
        assert receipt["outcome"] == "unresolved" and "terminal" not in s.api.commits
        receipt_path = cell_root(s) / output.RECEIPT
        frozen = receipt_path.read_bytes()
        select_fresh(s, monkeypatch, ordinal=1)
        assert boundary(s, capsys, monkeypatch, "--admit")[0] == 2 and not s.transport.calls
        assert receipt_path.read_bytes() == frozen
    else:
        revision = s.api.branches[retained.BRANCH]
        context = grading.compile_request("pilot/" + s.selected, SOURCE, revision)
        grading_environment(monkeypatch)
        monkeypatch.setenv("HF_TOKEN", TOKEN)
        prepared = grading.prepare(context, tmp_path / "ungraded", _test_api=s.api, _test_transport=SourceOnly())
        monkeypatch.delenv("HF_TOKEN")
        assert prepared["judge_ready"] is False and prepared["grading_state"] == "UNRUN"
        assert prepared["reason"] == "retained_result_missing_ungraded"
        assert prepared["inference_branch"] == retained.BRANCH and prepared["grading_branch"] == grading.BRANCH
        assert s.api.branches[grading.BRANCH] == retained.BOOTSTRAP


def test_workflows_route_only_closed_epoch_modes_without_new_authority():
    workflow = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_text())
    live = workflow["jobs"]["pilot-live"]
    assert live["environment"]["name"] == "grading" and live["timeout-minutes"] == 300
    assert "HF_TOKEN" not in live["env"]
    steps = live["steps"]
    setup_step = next(step for step in steps if "--phase setup" in step.get("run", ""))
    inspect_step = next(step for step in steps if "--phase inspect" in step.get("run", ""))
    for selector, (phase, _) in grading.BRANCH_ROUTES.items():
        chosen = setup_step if phase == "setup" else inspect_step
        assert "inputs.experiment_yaml == '" + selector + "'" in chosen["if"]
        for step in steps:
            if step.get("id") == "pilot_input" or "preflight_grading_renderer.py" in step.get("run", ""):
                assert "inputs.experiment_yaml != '" + selector + "'" in step["if"]
    assert '${GRADE_SELECTOR##*/}' in setup_step["run"]  # Distinct one-use setup roots.
    for step in steps:
        if "azure/login" in step.get("uses", "") or step.get("id") in {"pilot_claim", "pilot_judge"}:
            assert "steps.pilot_input.outputs.judge_ready == 'true'" in step["if"]
    for job in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in workflow["jobs"][job]["if"]
    cell_workflow = (pilot.ROOT / ci.WORKFLOW).read_text()
    assert OLD_CAMPAIGN not in cell_workflow and "--campaign-id " + ci.CAMPAIGN in cell_workflow
    assert ci.PUBLIC_FIXED["grading_launched"] is False
