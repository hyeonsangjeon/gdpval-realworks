"""One offline writer-recorded readout, not a live score or provider proof.

Canonical compilation, recorded identity/schema/projection and object/history
checks are real. Only Git metadata and immutable transport facts are simulated.
Synthetic terminal digests never replace the separately asserted production pin.
"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

import pytest
import yaml

import codex_retention_grade_readout as reader
import gpt54_disposable_checkout as source_checkout
import step8_grade as step8
from core.cost_projection import project_cost_receipt
from core.cost_receipts import build_receipt, ledger_reference
from core.grader import ItemGrade, TaskGrade
from core.rubric_loader import RubricLoader
from . import test_codex_budget_pilot_grading as base
from .test_codex_budget_pilot_retention import offline, TOKEN  # noqa: F401 — live boundaries forbidden

bridge, grade, pilot, output, retained = reader.bridge, reader.grade, reader.pilot, reader.output, reader.retained
OBSERVER = "d" * 40
PRIVATE = "PRIVATE-readout-canary https://private.invalid/path?credential=PRIVATE"


class ReadHF(base.GradeHF):
    def __init__(self):
        super().__init__()
        self.downloads, self.paths = [], []
        self.corrupt_download = None

    def repo_info(self, **kwargs):
        assert kwargs["revision"] == reader.TERMINAL, "no mutable branch discovery"
        return super().repo_info(**kwargs)

    def get_paths_info(self, **kwargs):
        self.paths.append((kwargs["revision"], tuple(kwargs["paths"])))
        return super().get_paths_info(**kwargs)

    def hf_hub_download(self, **kwargs):
        self.downloads.append((kwargs["revision"], kwargs["filename"]))
        if kwargs["filename"] == self.corrupt_download:
            self.record("download", kwargs)
            path = Path(kwargs["cache_dir"]) / "buffer"
            output._write_no_clobber(path, b"synthetic_corrupt_payload")
            return str(path)
        return super().hf_hub_download(**kwargs)

    def create_commit(self, **kwargs):
        pytest.fail("readout attempted publication")

    def create_branch(self, **kwargs):
        pytest.fail("readout attempted branch creation")


def _fixture(context):
    config = json.loads(context.run.grader_config_json)
    config_hash = hashlib.sha256(context.run.grader_config_json.encode()).hexdigest()[:16]
    path = grade._grade_path(context, config_hash, bridge.GRADER_SHA256, bridge.RESULT["output_commit"])
    entry = {"grade_path": str(path), "config_hash": config_hash, "grader_source_hash": bridge.GRADER_SHA256,
        "renderer_fingerprint": base.RENDERER,
        "cost_run_id": step8.make_cost_run_id(experiment_yaml_name=bridge.SELECTOR,
            config_hash=config_hash, grader_source_hash=bridge.GRADER_SHA256)}
    ledger = base._ledger(entry["cost_run_id"], context.cell["task_id"], "grading")
    receipt = project_cost_receipt(build_receipt([json.loads(ledger)], []).as_dict())
    items = [ItemGrade(rubric_item_id=f"synthetic-{index}", criterion=PRIVATE, max_score=2,
        awarded_score=2 if index == 0 else 0, verdict=verdict,
        decided_by="judge" if index == 2 else "precheck", required=None, evidence=PRIVATE,
        score_excluded=index == 2, model_did_right=index == 0,
        precheck_pattern_id=None if index == 2 else "file_exists_or_name")
        for index, verdict in enumerate(("pass", "fail", "judge_error"))]
    task = TaskGrade(task_id=context.cell["task_id"], sector=PRIVATE, occupation=PRIVATE, items=items,
        total_awarded=2, total_max=4, pct=50, critical_fail=False, gold_referenced=False,
        judge_call_count=1, precheck_count=2, judge_total_latency_ms=1, judge_input_tokens=0, judge_output_tokens=0,
        score_excluded_items=1, score_excluded_max=2, pct_full_denominator=100 / 3)
    row = step8._task_to_dict(task, grading_wall_time_ms=1.0)
    row["grading_cost"] = receipt
    loader = RubricLoader(config["rubric"]["repo_id"], config["rubric"]["revision"], config["rubric"]["cache_dir"])
    payload = step8._build_grade_payload(exp_name=bridge.SELECTOR, inf_results={"model": "synthetic-inference"},
        config=config, config_hash=config_hash, loader=loader, prompt_version=config["prompt"]["version"],
        task_dicts=[row], grader_source_hash=bridge.GRADER_SHA256, source_inference_repo_id=retained._target(),
        source_inference_revision=bridge.RESULT["output_commit"], azure_ai_runtime_fingerprint="f" * 64,
        azure_ai_routes=[{"workload": "grader", "runtime_fingerprint": "f" * 64,
                          "profile": "direct-v1", "endpoint_kind": "direct-v1"}],
        run_status="diagnostic", expected_task_ids=[context.cell["task_id"]],
        source_experiment_id=context.cell["run_id"], renderer_fingerprint=base.RENDERER,
        cost_ledger=ledger_reference(str(path.with_name(path.stem + ".cost_ledger.jsonl")), hashlib.sha256(ledger).hexdigest()))
    binding = {"source_sha": reader.WRITER_SOURCE, "selector": bridge.SELECTOR, "cell_id": bridge.CELL,
        "fixed_evidence_sha256": bridge.fixed_evidence_sha256(), "intake_sha256": bridge.RESULT["intake_sha256"],
        "approval_sha256": pilot._digest(bridge.approval_request(reader.WRITER_SOURCE, reader.WRITER_RUN)),
        "github_run": reader.WRITER_RUN, "entry": entry, "grading_plan_sha256": pilot._digest(context.grading.as_dict()),
        "preparation_sha256": "a" * 64, "proof_boundary": grade.PROOF}
    claim = {"format": bridge.CLAIM_FORMAT, "binding": binding,
             "expected_parent": bridge.PARENT["revision"], "predecessor": bridge.PARENT}
    terminal = {"format": bridge.TERMINAL_FORMAT, "binding": binding, "claim_commit": reader.CLAIM,
        "claim_identity": pilot._identity(retained._encoded(claim)), "outcome": "graded",
        "child": {"entry_invoked": True, "exit_code": 0, "timed_out": False, "cleanup_confirmed": True},
        "files": [], "missing": [], "invoice_complete": False, "http_request_count": None}
    return terminal, claim, payload, ledger


def _seed(monkeypatch, terminal, claim, payload, ledger, *, declared=True):
    api = ReadHF()
    entry = terminal["binding"]["entry"]
    path = Path(entry["grade_path"])
    files = {bridge.PREFIX + "/" + str(path): base._json(payload)}
    roles = {name: "grade_result" for name in files}
    if ledger is not None:
        name = bridge.PREFIX + "/" + str(path.with_name(path.stem + ".cost_ledger.jsonl"))
        files[name], roles[name] = ledger, "grade_cost_ledger"
    if declared:
        terminal["files"] = [{"role": roles[name], **retained._object(name, data)} for name, data in sorted(files.items())]
        terminal["missing"] = [] if ledger is not None else ["grade_cost_ledger"]
    api.seed(bridge.PARENT["revision"], retained.BOOTSTRAP, {})
    api.seed(reader.CLAIM, bridge.PARENT["revision"], {bridge.CLAIM_PATH: retained._encoded(claim)})
    raw = retained._encoded(terminal)
    api.seed(reader.TERMINAL, reader.CLAIM, {**files, bridge.TERMINAL_PATH: raw})
    # Bind this synthetic publication, never assert it is the actual terminal.
    monkeypatch.setattr(reader, "TERMINAL_IDENTITY", pilot._identity(raw))
    return api


def _environment(monkeypatch):
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": bridge.pilot_ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": OBSERVER,
        "PILOT_WORKFLOW_SHA": OBSERVER, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "12345",
        "GITHUB_JOB": "pilot-readout", "PILOT_GRADE_PAID_APPROVAL": "false", "PILOT_GRADE_DRY_RUN": "false",
        "GITHUB_WORKFLOW_REF": bridge.pilot_ci.REPOSITORY + "/" + grade.WORKFLOW + "@refs/heads/main",
        "GRADE_SELECTOR": reader.SELECTOR, "GRADE_TERMINAL": reader.TERMINAL,
        "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
        "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0", "GRADE_SHARD_COUNT": "1",
        "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1", "HF_TOKEN": TOKEN}
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _workflow():
    jobs = yaml.safe_load((bridge.ROOT / grade.WORKFLOW).read_bytes())["jobs"]
    job = jobs["pilot-readout"]
    assert " ".join(job["if"].split()) == (
        "${{ (inputs.experiment_yaml == 'pilot/grade-readout' || inputs.experiment_yaml == 'retention/grade-readout') "
        "&& inputs.paid_approval == false && github.repository == 'hyeonsangjeon/gdpval-realworks' "
        "&& github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
        "&& github.sha == github.workflow_sha && github.run_attempt == '1' }}")
    assert job["permissions"] == {"contents": "read"} and job["environment"] == {"name": "grading"}
    assert job["runs-on"] == "ubuntu-24.04" and "needs" not in job
    assert job["steps"][1]["with"] == {"python-version": "3.11"}
    assert job["steps"][0]["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
    assert "inputs.experiment_yaml != 'retention/grade-readout'" in jobs["pilot-plan"]["if"]
    for name in ("pilot-approve-paid", "pilot-live"):
        assert "|| inputs.experiment_yaml == 'retention/first-cell')" in jobs[name]["if"]
        assert "startsWith(inputs.experiment_yaml, 'retention/')" not in jobs[name]["if"]
        assert "inputs.paid_approval == true" in jobs[name]["if"]
    for name in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'retention/')" in jobs[name]["if"]
    secret_steps = [step for step in job["steps"] if "secrets." in yaml.safe_dump(step)]
    assert len(secret_steps) == 1 and secret_steps[0] is job["steps"][-1]
    assert secret_steps[0]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert secret_steps[0]["if"] == "inputs.dry_run == false && success()"
    assert "--phase readout" in secret_steps[0]["run"]
    assert "--phase" not in job["steps"][-2]["run"] and "secrets." not in yaml.safe_dump(job["env"])
    for forbidden in ("id-token", "azure/login", "AZURE", "FOUNDRY", "--phase claim", "--phase judge",
                      "--phase publish", "--phase prepare", "--phase reconcile", "upload-artifact"):
        assert forbidden not in yaml.safe_dump(job)


def test_first_retention_grade_readout_is_immutable_writer_recorded_and_unpaid(tmp_path, monkeypatch, capsys):
    assert reader.TERMINAL == "40712e0980cc05c31688fdbb98c693774fb90c0d"
    assert reader.TERMINAL_IDENTITY == {
        "sha256": "11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234", "size": 3119}
    assert reader.CLAIM == "dec305d669e3ca2e53c7f7b9ebfbe7974d661350"
    assert reader.WRITER_SOURCE == "29e0353f1539265b1741e71be894fedf9be32a8b"
    assert reader.WRITER_RUN == {"id": "36776393736", "job": "pilot-live", "attempt": 1}
    assert bridge.fixed_evidence_sha256() == "1ced90e270d80055cc3482bea4a5489f045f1b9dcb0ed2622ebd8de80285a56d"
    _workflow()
    context = bridge.compile_request(reader.WRITER_SOURCE)
    template = _fixture(context)
    api = _seed(monkeypatch, *deepcopy(template))
    terminal = pilot._json_object(api.trees[reader.TERMINAL][bridge.TERMINAL_PATH])
    assert template[2].get("result_fingerprint") is None
    with pytest.raises(output.OutputPublicationRefused, match="^canonical_retention_grade_context_required$"):
        reader._terminal_contract(SimpleNamespace(**context.__dict__), terminal)
    effects = []

    def forbidden(*args, **kwargs):
        effects.append("forbidden_effect")
        pytest.fail("read-only route crossed a write, input, renderer, admission or judge boundary")

    for target, names in (
        (bridge, ("_authority", "prepare", "claim", "judge", "publish", "reconcile", "_ready", "_derived_inputs")),
        (grade, ("_ci_authority", "prepare", "claim", "judge", "publish", "reconcile", "_owned_judge", "setup")),
        (pilot, ("dispatch",)), (step8, ("main",)), (bridge.reader, ("read_result",)),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    monkeypatch.setattr("core.tools.get_renderer_fingerprint", forbidden)
    monkeypatch.setattr(RubricLoader, "load", forbidden)
    common = tmp_path / "synthetic-git-metadata"
    common.mkdir()
    git_state, git_calls = {"head": OBSERVER, "dirty": b""}, []

    def git(path, *command, ok=(0,)):
        assert Path(path) == bridge.ROOT
        git_calls.append(command)
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (git_state["head"] + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): git_state["dirty"],
            ("status", "--porcelain", "--untracked-files=normal"): git_state["dirty"],
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): b""}
        assert command in answers, "only source metadata is simulated"
        return SimpleNamespace(stdout=answers[command], returncode=0)

    # Imported repository validators resolve Git in their defining module.
    # Simulate the same transport there; keep both validators themselves real.
    monkeypatch.setattr(source_checkout, "_git", git)
    monkeypatch.setattr(pilot, "_git", git)
    roots = []

    def invoke(api=api, *, phase="readout", source=OBSERVER, selector=reader.SELECTOR,
               terminal_revision=reader.TERMINAL, producer="", root=None, script=False):
        root = root or tmp_path / f"readout-{len(roots)}"
        roots.append(root)
        args = ["--selector", selector, "--reviewed-source-sha", source, "--terminal-revision", terminal_revision,
                "--root", str(root), "--producer-source-sha", producer]
        if phase is not None:
            args += ["--phase", phase]
        if script:
            with monkeypatch.context() as scoped:
                scoped.setattr(sys, "argv", [str(bridge.ROOT / "batch-runner/codex_budget_pilot_grading.py"), *args])
                with pytest.raises(SystemExit) as exit_info:
                    runpy.run_path(sys.argv[0], run_name="__main__")
                status = exit_info.value.code
        else:
            status = grade.main(args, _test_api=api)
        captured = capsys.readouterr()
        text = captured.out if status == 0 else captured.err
        assert not (captured.err if status == 0 else captured.out)
        for private in (PRIVATE, TOKEN, str(tmp_path), retained._target(), '"criterion":', '"evidence":', '"judge_raw_response":'):
            assert private not in text
        receipt = json.loads(text)
        assert receipt["remote_mutation_possible"] is False and receipt["judge_entry_requested"] is False
        assert receipt["invoice_complete"] is False and receipt["automatic_retry"] is False
        assert receipt["materialized_input_fingerprint"] == {
            "status": "unavailable", "value": None, "comparison": None,
            "reason": "materialized_input_fingerprint_not_recorded"}
        assert not effects
        return status, receipt

    assert invoke(phase=None, script=True)[0] == 0  # Actual canonical script/router; inert default.
    assert not api.calls and not git_calls and not roots[-1].exists()
    assert invoke()[0] == 2  # No local read authority.
    assert not api.calls and not roots[-1].exists()
    _environment(monkeypatch)
    for changes in ({"phase": phase} for phase in ("inspect", "setup", "prepare", "claim", "judge", "publish", "reconcile", "record-ungraded")):
        assert invoke(**changes)[0] == 2
        assert not roots[-1].exists()
    for changes in ({"source": reader.WRITER_SOURCE}, {"source": bridge.RESULT["producer_source_sha"]},
                    {"source": "not-a-sha"}, {"terminal_revision": "main"},
                    {"terminal_revision": bridge.RESULT["terminal_commit"]}, {"producer": reader.WRITER_SOURCE}):
        assert invoke(**changes)[0] == 2 and not roots[-1].exists()
    for key, value in (("PILOT_GRADE_PAID_APPROVAL", "true"), ("PILOT_GRADE_DRY_RUN", "true"),
            ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_JOB", "pilot-live"), ("GITHUB_REF", "refs/heads/other"),
            ("PILOT_WORKFLOW_SHA", reader.WRITER_SOURCE), ("GRADE_TERMINAL", "main"),
            ("GRADE_SELECTOR", bridge.SELECTOR), ("GRADE_FORCE", "true"), ("GRADE_RESUME", "true"),
            ("GRADE_RESUME_CHUNK", "1"), ("GRADE_SHARD_COUNT", "2"), ("GRADE_SHARD_INDEX", "1"),
            ("GRADE_TASKS", context.cell["task_id"]), ("GRADE_TASKS_LIMIT", "1"), ("GRADE_RUN_ORDINAL", "2"),
            ("GRADE_CONFIG", "other.yaml")):
        with monkeypatch.context() as scoped:
            scoped.setenv(key, value)
            assert invoke()[0] == 2 and not roots[-1].exists()
    assert not api.calls
    git_state["head"] = "e" * 40
    assert invoke()[0] == 2 and not api.calls
    git_state.update(head=OBSERVER, dirty=b"synthetic-dirty-source\n")
    assert invoke()[0] == 2 and not api.calls
    git_state["dirty"] = b""

    before = deepcopy((api.trees, api.writers, api.branches))
    status, result = invoke()
    safe_refusal = {key: result[key] for key in ("reason", "stage")}
    assert status == 0 and result["outcome"] == "verified_writer_recorded_grade", safe_refusal
    assert result["grade_state"] == "graded" and result["record_kind"] == "writer_recorded_grade"
    assert result["score"] == {"earned": 2, "possible": 4, "pct": 50,
        "tasks_with_excluded_items": 1, "excluded_items": 1, "excluded_max_score": 2.0,
        "avg_score_pct_full_denominator": 33.33, "avg_score_pct_lift": 16.67}
    assert result["coverage"]["passed_items"] == 1 and result["coverage"]["rubric_item_coverage"] == 0.5
    assert result["recorded_task_cost"]["model_calls"] == 1 and result["recorded_task_cost"]["missing_reasons"]
    assert result["recorded_task_cost"]["invoice_complete"] is False
    assert result["recorded_task_cost"]["http_request_count"] is None
    assert result["original_result_fingerprint"] == bridge.RESULT["result"]["result_fingerprint"]
    assert result["writer_preparation_sha256"] == "a" * 64
    assert result["original_result_fingerprint"] != result["writer_preparation_sha256"]
    assert result["grade_writer_source_sha"] != result["observer_source_sha"]
    assert result["proof_boundary"] == grade.PROOF and result["mutable_branch_head_observed"] is False
    assert result["grade_revision"] == reader.TERMINAL and result["claim_revision"] == reader.CLAIM
    assert result["terminal_identity"] == reader.TERMINAL_IDENTITY
    assert (api.trees, api.writers, api.branches) == before and not api.commits
    assert sum(name == "metadata" for name, _ in api.calls) == 1 and len(api.paths) == 5
    allowed = {(reader.TERMINAL, bridge.TERMINAL_PATH), (reader.CLAIM, bridge.CLAIM_PATH),
               *((reader.TERMINAL, row["path"]) for row in terminal["files"])}
    assert set(api.downloads) == allowed and len(api.downloads) == 5
    assert all(revision in {reader.TERMINAL, reader.CLAIM} for _, revision in api.calls)
    count = len(api.calls)
    assert invoke(root=roots[-1])[0] == 2 and len(api.calls) == count  # No-clobber, no retry.

    for layer, field, value in (
        ("binding", "source_sha", "e" * 40), ("binding", "cell_id", "other-cell"),
        ("binding", "selector", "pilot/cell-00"), ("binding", "github_run", {**reader.WRITER_RUN, "id": "1"}),
        ("binding", "approval_sha256", "e" * 64), ("binding", "fixed_evidence_sha256", "e" * 64),
        ("binding", "intake_sha256", "e" * 64), ("binding", "grading_plan_sha256", "e" * 64),
        ("binding", "preparation_sha256", "unrecorded"), ("entry", "config_hash", "e" * 16),
        ("entry", "grader_source_hash", "e" * 64), ("entry", "cost_run_id", "arbitrary/family"),
        ("entry", "grade_path", "native-home/private.json"),
        ("terminal", "child", {**template[0]["child"], "cleanup_confirmed": False}),
        ("terminal", "claim_commit", bridge.RESULT["claim_commit"]), ("terminal", "invoice_complete", True)):
        t, c, p, ledger = deepcopy(template)
        target = t if layer == "terminal" else t["binding"] if layer == "binding" else t["binding"]["entry"]
        target[field] = value
        bad = _seed(monkeypatch, t, c, p, ledger)
        assert invoke(bad)[0] == 2
        assert bad.downloads == [(reader.TERMINAL, bridge.TERMINAL_PATH)]

    for case in ("terminal_hash", "terminal_missing", "terminal_history", "claim_hash", "claim_missing",
                 "claim_binding", "claim_parent", "claim_history", "inherited_claim_history", "file_hash",
                 "file_history", "download_hash", "duplicate", "missing_result", "unsafe_path", "private_role",
                 "missing_field", "file_bound", "private_target"):
        t, c, p, ledger = deepcopy(template)
        bad = _seed(monkeypatch, t, c, p, ledger)
        if case == "terminal_hash":
            monkeypatch.setattr(reader, "TERMINAL_IDENTITY", {**reader.TERMINAL_IDENTITY, "sha256": "0" * 64})
        elif case == "terminal_missing":
            del bad.trees[reader.TERMINAL][bridge.TERMINAL_PATH]
        elif case == "terminal_history":
            bad.writers[reader.TERMINAL][bridge.TERMINAL_PATH] = reader.CLAIM
        elif case == "claim_missing":
            del bad.trees[reader.CLAIM][bridge.CLAIM_PATH]
        elif case in {"claim_binding", "claim_parent"}:
            c = deepcopy(c)  # Corrupt only the claim; keep the terminal binding intact.
            if case == "claim_binding":
                c["binding"]["source_sha"] = "e" * 40
            else:
                c["expected_parent"] = "e" * 40
            raw = retained._encoded(c)
            bad.trees[reader.CLAIM][bridge.CLAIM_PATH] = raw
            bad.trees[reader.TERMINAL][bridge.CLAIM_PATH] = raw
            t["claim_identity"] = pilot._identity(raw)
        elif case == "claim_hash":
            t["claim_identity"]["sha256"] = "0" * 64
        elif case in {"claim_history", "inherited_claim_history"}:
            revision = reader.CLAIM if case == "claim_history" else reader.TERMINAL
            bad.writers[revision][bridge.CLAIM_PATH] = bridge.PARENT["revision"]
        elif case == "file_hash":
            t["files"][0]["git_blob_sha1"] = "0" * 40
        elif case == "file_history":
            bad.writers[reader.TERMINAL][t["files"][0]["path"]] = reader.CLAIM
        elif case == "download_hash":
            bad.corrupt_download = t["files"][0]["path"]
        elif case == "duplicate":
            t["files"] = [t["files"][0], t["files"][0]]
        elif case == "missing_result":
            t["files"] = [row for row in t["files"] if row["role"] != "grade_result"]
        elif case == "unsafe_path":
            t["files"][0]["path"] = "../native-home/transcript.json"
        elif case == "private_role":
            t["files"][0]["role"] = "native_sqlite"
        elif case == "missing_field":
            t["missing"] = ["grade_result"]
        elif case == "file_bound":
            t["files"][0]["size"] = output.MAX_RECORD_BYTES + 1
        elif case == "private_target":
            bad.private = False
        if case not in {"terminal_hash", "terminal_missing"}:
            raw = retained._encoded(t)
            bad.trees[reader.TERMINAL][bridge.TERMINAL_PATH] = raw
            monkeypatch.setattr(reader, "TERMINAL_IDENTITY", pilot._identity(raw))
        assert invoke(bad)[0] == 2
        if case != "download_hash":
            assert all(name in {bridge.TERMINAL_PATH, bridge.CLAIM_PATH} for _, name in bad.downloads)
        assert not bad.commits

    for field, value in (("source_inference_revision", "e" * 40), ("source_inference_experiment_id", "foreign"),
            ("grader_source_hash", "e" * 64), ("expected_task_count", 2), ("run_status", "final"),
            ("experiment_yaml_name", "pilot/cell-00"), ("tasks", [])):
        t, c, p, ledger = deepcopy(template)
        p[field] = value
        assert invoke(_seed(monkeypatch, t, c, p, ledger))[0] == 2
    for case in ("task", "malformed_score", "raw_judge", "judge", "rubric", "ledger_task", "ledger_hash"):
        t, c, p, ledger = deepcopy(template)
        if case == "task":
            p["tasks"][0]["task_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        elif case == "malformed_score":
            p["tasks"][0]["pct"] = "not-a-number"
        elif case == "raw_judge":
            p["tasks"][0]["items"][0]["judge_raw_response"] = PRIVATE
        elif case == "judge":
            p["judge"]["model"] = "foreign-model"
        elif case == "rubric":
            p["rubric"]["commit_sha"] = "e" * 40
        elif case == "ledger_task":
            row = json.loads(ledger)
            row["task_id"] = "other-task"
            ledger = base._json(row)
        else:
            p["cost_ledger"]["sha256"] = "e" * 64
        assert invoke(_seed(monkeypatch, t, c, p, ledger))[0] == 2

    # An absent optional ledger stays missing, not a measured zero or an invoice.
    t, c, p, _ = deepcopy(template)
    p["cost_ledger"] = None
    missing = _seed(monkeypatch, t, c, p, None)
    status, receipt = invoke(missing)
    assert status == 0 and receipt["missing"] == ["grade_cost_ledger"]
    assert receipt["ledger_derived_cost"] is None and receipt["ledger_state"] == "missing"
    # The unchanged legacy wrapper does not acquire retention ledger authority.
    legacy_terminal = deepcopy(terminal)
    legacy_terminal["binding"]["retained"] = {"output_commit": bridge.RESULT["output_commit"]}
    with pytest.raises(output.OutputPublicationRefused, match="^fixed_grading_ledger_run_required$"):
        reader.readout._projection(context, legacy_terminal,
            {"grade_result": base._json(template[2]), "grade_cost_ledger": template[3]}, template[0]["binding"]["entry"])
    facade = reader._ReadOnlyGrade(missing, missing.repo, TOKEN)
    for absent in ("create_commit", "create_branch", "create_repo", "list_repo_tree", "upload_file", "delete_file"):
        assert not hasattr(facade, absent)
    with pytest.raises(output.OutputPublicationRefused, match="^grade_readout_metadata_refused$"):
        facade.repo_info(repo_id=missing.repo, repo_type="dataset", revision=grade.BRANCH, token=TOKEN, timeout=1)
    count = len(missing.calls)
    with pytest.raises(output.OutputPublicationRefused, match="^grade_readout_paths_refused$"):
        facade.get_paths_info(repo_id=missing.repo, repo_type="dataset", revision=reader.CLAIM,
            paths=[bridge.CLAIM_PATH], expand=True, token=TOKEN)
    with pytest.raises(output.OutputPublicationRefused, match="^grade_readout_download_refused$"):
        facade.hf_hub_download(repo_id=missing.repo, repo_type="dataset", revision=reader.TERMINAL,
            filename=terminal["files"][0]["path"], token=TOKEN, cache_dir=tmp_path,
            force_download=True, local_files_only=False, etag_timeout=1)
    assert len(missing.calls) == count
    assert effects == [] and git_calls
