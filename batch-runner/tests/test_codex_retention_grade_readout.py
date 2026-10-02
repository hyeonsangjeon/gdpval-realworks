"""One offline writer-recorded readout, not a live score or provider proof.

Canonical compilation, recorded identity/schema/projection and object/history
checks are real. Only Git metadata and immutable transport facts are simulated.
Synthetic terminal digests never replace the separately asserted production pin.
"""

from copy import deepcopy
from dataclasses import replace
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
from core.cost_receipts import build_receipt, ledger_reference
from core.grader import ItemGrade, TaskGrade
from core.rubric_loader import RubricLoader
from . import test_codex_budget_pilot_grading as base
from .test_codex_budget_pilot_retention import offline, TOKEN  # noqa: F401 — live boundaries forbidden

bridge, grade, pilot, output, retained = reader.bridge, reader.grade, reader.pilot, reader.output, reader.retained
OBSERVER = "d" * 40
PRIVATE = "PRIVATE-readout-canary https://private.invalid/path?credential=PRIVATE"


class ReadHF(base.GradeHF):
    def __init__(self, *, selector=reader.SELECTOR):
        super().__init__()
        self.terminal_revision = reader._fixed(selector).terminal
        self.downloads, self.paths = [], []
        self.corrupt_download = None

    def repo_info(self, **kwargs):
        assert kwargs["revision"] == self.terminal_revision, "no mutable branch discovery"
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


def _fixture(context, *, selector=reader.SELECTOR):
    profile = reader._fixed(selector)
    fixed = bridge._fixed(profile.grading_selector)
    config = json.loads(context.run.grader_config_json)
    config_hash = hashlib.sha256(context.run.grader_config_json.encode()).hexdigest()[:16]
    path = grade._grade_path(context, config_hash, fixed.GRADER_SHA256, fixed.RESULT["output_commit"])
    entry = {"grade_path": str(path), "config_hash": config_hash, "grader_source_hash": fixed.GRADER_SHA256,
        "renderer_fingerprint": base.RENDERER,
        "cost_run_id": step8.make_cost_run_id(experiment_yaml_name=fixed.SELECTOR,
            config_hash=config_hash, grader_source_hash=fixed.GRADER_SHA256)}
    ledger = base._ledger(entry["cost_run_id"], context.cell["task_id"], "grading")
    # Step8 persists the producer receipt; safe readout projection happens only
    # after schema validation and may turn partial-accounting placeholders null.
    receipt = build_receipt([json.loads(ledger)], []).as_dict()
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
    payload = step8._build_grade_payload(exp_name=fixed.SELECTOR, inf_results={"model": "synthetic-inference"},
        config=config, config_hash=config_hash, loader=loader, prompt_version=config["prompt"]["version"],
        task_dicts=[row], grader_source_hash=fixed.GRADER_SHA256, source_inference_repo_id=retained._target(),
        source_inference_revision=fixed.RESULT["output_commit"], azure_ai_runtime_fingerprint="f" * 64,
        azure_ai_routes=[{"workload": "grader", "runtime_fingerprint": "f" * 64,
                          "profile": "direct-v1", "endpoint_kind": "direct-v1"}],
        run_status="diagnostic", expected_task_ids=[context.cell["task_id"]],
        source_experiment_id=context.cell["run_id"], renderer_fingerprint=base.RENDERER,
        cost_ledger=ledger_reference(str(path.with_name(path.stem + ".cost_ledger.jsonl")), hashlib.sha256(ledger).hexdigest()))
    binding = {"source_sha": profile.writer_source, "selector": fixed.SELECTOR, "cell_id": fixed.CELL,
        "fixed_evidence_sha256": bridge.fixed_evidence_sha256(fixed.SELECTOR), "intake_sha256": fixed.RESULT["intake_sha256"],
        "approval_sha256": pilot._digest(bridge.approval_request(profile.writer_source, profile.writer_run,
                                                              selector=fixed.SELECTOR)),
        "github_run": profile.writer_run, "entry": entry, "grading_plan_sha256": pilot._digest(context.grading.as_dict()),
        "preparation_sha256": "a" * 64, "proof_boundary": grade.PROOF}
    claim = {"format": fixed.CLAIM_FORMAT, "binding": binding,
             "expected_parent": fixed.PARENT["revision"], "predecessor": fixed.PARENT}
    terminal = {"format": fixed.TERMINAL_FORMAT, "binding": binding, "claim_commit": profile.claim,
        "claim_identity": pilot._identity(retained._encoded(claim)), "outcome": "graded",
        "child": {"entry_invoked": True, "exit_code": 0, "timed_out": False, "cleanup_confirmed": True},
        "files": [], "missing": [], "invoice_complete": False, "http_request_count": None}
    return terminal, claim, payload, ledger


def _seed(monkeypatch, terminal, claim, payload, ledger, *, declared=True, selector=reader.SELECTOR):
    profile = reader._fixed(selector)
    fixed = bridge._fixed(profile.grading_selector)
    api = ReadHF(selector=selector)
    entry = terminal["binding"]["entry"]
    path = Path(entry["grade_path"])
    files = {fixed.PREFIX + "/" + str(path): base._json(payload)}
    roles = {name: "grade_result" for name in files}
    if ledger is not None:
        name = fixed.PREFIX + "/" + str(path.with_name(path.stem + ".cost_ledger.jsonl"))
        files[name], roles[name] = ledger, "grade_cost_ledger"
    if declared:
        terminal["files"] = [{"role": roles[name], **retained._object(name, data)} for name, data in sorted(files.items())]
        terminal["missing"] = [] if ledger is not None else ["grade_cost_ledger"]
    api.seed(fixed.PARENT["revision"], retained.BOOTSTRAP, {})
    api.seed(profile.claim, fixed.PARENT["revision"], {fixed.CLAIM_PATH: retained._encoded(claim)})
    raw = retained._encoded(terminal)
    api.seed(profile.terminal, profile.claim, {**files, fixed.TERMINAL_PATH: raw})
    # Bind this synthetic publication, never assert it is the actual terminal.
    identity_name = "TERMINAL_IDENTITY" if selector == reader.SELECTOR else "KEEP_R2_TERMINAL_IDENTITY"
    monkeypatch.setattr(reader, identity_name, pilot._identity(raw))
    return api


def _environment(monkeypatch, *, selector=reader.SELECTOR):
    profile = reader._fixed(selector)
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": bridge.pilot_ci.REPOSITORY,
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": OBSERVER,
        "PILOT_WORKFLOW_SHA": OBSERVER, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "12345",
        "GITHUB_JOB": "pilot-readout", "PILOT_GRADE_PAID_APPROVAL": "false", "PILOT_GRADE_DRY_RUN": "false",
        "GITHUB_WORKFLOW_REF": bridge.pilot_ci.REPOSITORY + "/" + grade.WORKFLOW + "@refs/heads/main",
        "GRADE_SELECTOR": profile.selector, "GRADE_TERMINAL": profile.terminal,
        "GRADE_CONFIG": "default_v2_sol_max.yaml", "GRADE_FORCE": "false", "GRADE_TASKS_LIMIT": "0",
        "GRADE_TASKS": "", "GRADE_RESUME": "false", "GRADE_RESUME_CHUNK": "0", "GRADE_SHARD_COUNT": "1",
        "GRADE_SHARD_INDEX": "0", "GRADE_RUN_ORDINAL": "1", "HF_TOKEN": TOKEN}
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _workflow():
    jobs = yaml.safe_load((bridge.ROOT / grade.WORKFLOW).read_bytes())["jobs"]
    job = jobs["pilot-readout"]
    assert " ".join(job["if"].split()) == (
        "${{ (inputs.experiment_yaml == 'pilot/grade-readout' || inputs.experiment_yaml == 'retention/grade-readout' "
        "|| inputs.experiment_yaml == 'retention/keep-r2-readout') "
        "&& inputs.paid_approval == false && github.repository == 'hyeonsangjeon/gdpval-realworks' "
        "&& github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main' "
        "&& github.sha == github.workflow_sha && github.run_attempt == '1' }}")
    assert job["permissions"] == {"contents": "read"} and job["environment"] == {"name": "grading"}
    assert job["runs-on"] == "ubuntu-24.04" and "needs" not in job
    assert job["steps"][1]["with"] == {"python-version": "3.11"}
    assert job["steps"][0]["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
    assert "inputs.experiment_yaml != 'retention/grade-readout'" in jobs["pilot-plan"]["if"]
    assert "inputs.experiment_yaml != 'retention/keep-r2-readout'" in jobs["pilot-plan"]["if"]
    assert " ".join(jobs["pilot-plan"]["if"].split()) == (
        "${{ (startsWith(inputs.experiment_yaml, 'pilot/') || startsWith(inputs.experiment_yaml, 'retention/')) && "
        "inputs.experiment_yaml != 'pilot/grade-readout' && "
        "inputs.experiment_yaml != 'retention/grade-readout' && "
        "inputs.experiment_yaml != 'retention/keep-r2-readout' && "
        "(inputs.dry_run == true || (startsWith(inputs.experiment_yaml, 'retention/') && "
        "inputs.experiment_yaml != 'retention/first-cell' && inputs.experiment_yaml != 'retention/keep-r2')) }}")
    for name in ("pilot-approve-paid", "pilot-live"):
        assert (
            "|| inputs.experiment_yaml == 'retention/first-cell' || inputs.experiment_yaml == 'retention/keep-r2')"
        ) in jobs[name]["if"]
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

    with monkeypatch.context() as local:
        local.delenv("GITHUB_ACTIONS", raising=False)
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
    payload_refusals = []
    fixed_reasons = frozenset({
        "bounded_immutable_file_required", "unsafe_retained_member", "grading_download_cache_escape",
        "retained_file_identity_mismatch", "payload_file_or_size_refused", "payload_file_changed",
        "payload_identity_mismatch", "grade_readout_download_refused",
        "fixed_retention_grade_projection_binding_required", "canonical_retention_grade_context_required",
        "retention_grade_context_changed", "unsafe_grade_structure", "unsafe_grade_fields",
        "raw_judge_response_refused", "fixed_grade_schema_refused", "grade_scope_identity_mismatch",
        "grade_task_set_mismatch", "fixed_judge_identity_mismatch",
        "fixed_retention_grading_ledger_binding_required", "fixed_retention_grading_ledger_run_required",
        "fixed_grading_ledger_run_required", "ledger_schema_refused", "ledger_cell_mismatch",
        "ledger_duplicate_or_missing_identity", "ledger_rows_exceeded", "ledger_reasons_refused",
        "ledger_state_refused", "ledger_stage_refused", "ledger_hash_refused", "ledger_runtime_refused",
        "ledger_usage_refused", "ledger_amount_refused", "ledger_identity_refused", "unsafe_ledger_note",
        "grade_ledger_pointer_mismatch", "bound_grade_ledger_missing", "unsafe_receipt_fields",
        "grade_readout_accounting_refused", "grade_readout_outcome_mismatch", "completed_grade_has_partial_checkpoint",
    })
    fixed_classes = (output.OutputPublicationRefused, ValueError, KeyError, AttributeError, TypeError,
        OSError, FileNotFoundError, FileExistsError, PermissionError, NotADirectoryError, IsADirectoryError,
        RecursionError, step8.SchemaError, step8.ValidationError)

    def observe_payload(function_name, real_helper):
        def observed(*args, **kwargs):
            try:
                return real_helper(*args, **kwargs)
            except Exception as error:
                # Never stringify the error: schema/identity errors can contain
                # private values. Record only fixed symbols and public schema
                # details, then re-raise the same exception.
                refusal = {"function": function_name,
                    "exception": next((kind.__name__ for kind in fixed_classes if type(error) is kind), "Exception"),
                    "reason": next((reason for reason in fixed_reasons
                        if type(error) is output.OutputPublicationRefused and error.args == (reason,)), None)}
                if type(error) is step8.ValidationError:
                    refusal["validator"] = error.validator
                    refusal["absolute_schema_path"] = list(error.absolute_schema_path)
                    if error.validator == "required":
                        refusal["missing_properties"] = [name for name in error.schema["required"]
                            if name not in error.instance]
                payload_refusals.append(refusal)
                raise
        return observed

    # Observe only the intended-success payload path. These are the real
    # helpers, with unchanged arguments, results, exceptions and validators.
    with monkeypatch.context() as diagnostics:
        for target, name, function_name in (
            (grade, "_fetch", "codex_budget_pilot_grading._fetch"),
            (reader.readout, "_recorded_projection", "codex_budget_pilot_grade_readout._recorded_projection"),
            (grade, "_validate_grade_identity", "codex_budget_pilot_grading._validate_grade_identity"),
            (step8, "_validate_schema", "step8_grade._validate_schema"),
            (step8, "_validate_grade_resume_identity", "step8_grade._validate_grade_resume_identity"),
            (output, "_ledger", "codex_budget_pilot_output._ledger"),
            (reader.readout, "_receipt", "codex_budget_pilot_grade_readout._receipt"),
        ):
            diagnostics.setattr(target, name, observe_payload(function_name, getattr(target, name)))
        status, result = invoke()
    safe_refusal = {key: result[key] for key in ("reason", "stage")}
    safe_refusal["payload_helpers"] = payload_refusals
    assert status == 0 and result["outcome"] == "verified_writer_recorded_grade", json.dumps(safe_refusal, sort_keys=True)
    assert result["grade_state"] == "graded" and result["record_kind"] == "writer_recorded_grade"
    assert result["score"] == {"earned": 2, "possible": 4, "pct": 50,
        "tasks_with_excluded_items": 1, "excluded_items": 1, "excluded_max_score": 2.0,
        "avg_score_pct_full_denominator": 33.33, "avg_score_pct_lift": 16.67}
    assert result["coverage"]["passed_items"] == 1 and result["coverage"]["rubric_item_coverage"] == 0.5
    assert result["recorded_task_cost"]["model_calls"] == 1 and result["recorded_task_cost"]["missing_reasons"]
    assert result["recorded_task_cost"]["runtime_cost_usd"] is None
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


def test_retention_grade_entry_restores_cwd_for_fixed_relative_prompts(tmp_path, monkeypatch):
    original_cwd = Path.cwd()
    source_root, batch_root = pilot.ROOT, pilot.ROOT / "batch-runner"
    assert source_root == bridge.ROOT
    assert reader.TERMINAL == "40712e0980cc05c31688fdbb98c693774fb90c0d"
    assert reader.TERMINAL_IDENTITY == {
        "sha256": "11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234", "size": 3119}
    assert reader.WRITER_SOURCE == "29e0353f1539265b1741e71be894fedf9be32a8b"
    assert reader.CLAIM == "dec305d669e3ca2e53c7f7b9ebfbe7974d661350"
    # Construct the existing writer fixture in its own cwd, not the caller's.
    with grade._cwd(batch_root):
        context = bridge.compile_request(reader.WRITER_SOURCE)
        template = _fixture(context)
    assert Path.cwd() == original_cwd
    config_bytes = context.run.grader_config_json
    config = json.loads(config_bytes)
    prompts = {key: config["prompt"][key] for key in ("template", "tool_template")}
    assert prompts == {"template": "prompts/grader_judge.md", "tool_template": "prompts/grader_judge_v2.md"}
    assert all(not (source_root / name).exists() and (batch_root / name).is_file() for name in prompts.values())
    recorded = deepcopy(template[0]["binding"]["entry"])
    expected_entry = pilot._digest(recorded)
    effects, observed_entries = [], []

    def forbidden(*args, **kwargs):
        effects.append("forbidden_effect")
        pytest.fail("entry cwd validation crossed a payload, write or paid boundary")

    for target, names in (
        (bridge, ("_authority", "prepare", "claim", "judge", "publish", "reconcile", "_ready", "_derived_inputs")),
        (grade, ("_ci_authority", "prepare", "claim", "judge", "publish", "reconcile", "_owned_judge", "setup", "_fetch")),
        (pilot, ("dispatch",)), (step8, ("main",)), (bridge.reader, ("read_result",)),
        (reader.readout, ("_recorded_projection",)),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    monkeypatch.setattr("core.tools.get_renderer_fingerprint", forbidden)
    monkeypatch.setattr(RubricLoader, "load", forbidden)
    _environment(monkeypatch)

    for label, caller_root in (("repository", source_root), ("batch-runner", batch_root)):
        with monkeypatch.context() as caller:
            caller.chdir(caller_root)
            # Reproduce the unscoped call's exact predicate in this one test.
            # No production validator or configuration is replaced.
            if label == "repository":
                with pytest.raises(ValueError) as unscoped:
                    step8.validate_grading_config(json.loads(config_bytes))
                assert type(unscoped.value) is ValueError
                assert unscoped.value.args == ("prompt template not found: prompts/grader_judge.md",)
            else:
                step8.validate_grading_config(json.loads(config_bytes))
            assert Path.cwd() == caller_root

            entry = reader._entry(context, deepcopy(recorded))
            assert Path.cwd() == caller_root and pilot._digest(entry) == expected_entry
            api = _seed(monkeypatch, *deepcopy(template))
            before = deepcopy((api.trees, api.writers, api.branches))
            root = grade._root(tmp_path / label, new=True)
            with retained._session(api, response_bytes_limit=output.MAX_RECORD_BYTES) as (transport, token, deadline):
                facade = reader._ReadOnlyGrade(transport, retained._target(), token)
                terminal, verified_entry, identity = facade.verify(context, root, deadline)
            assert Path.cwd() == caller_root
            assert pilot._digest(verified_entry) == expected_entry and identity == reader.TERMINAL_IDENTITY
            assert terminal["claim_commit"] == reader.CLAIM and terminal["child"]["cleanup_confirmed"] is True
            assert facade._verification_substage == "terminal_identity"
            observed_entries.append(pilot._digest(verified_entry))
            assert api.downloads == [(reader.TERMINAL, bridge.TERMINAL_PATH),
                                    (reader.TERMINAL, bridge.TERMINAL_PATH), (reader.CLAIM, bridge.CLAIM_PATH)]
            assert sum(name == "metadata" for name, _ in api.calls) == 1 and len(api.paths) == 5
            assert (api.trees, api.writers, api.branches) == before and not api.commits

            # Negative configs are direct _entry refusal inputs only, never
            # canonical contexts offered as successful terminal evidence.
            for key in ("template", "tool_template"):
                bad_config = json.loads(config_bytes)
                missing = "prompts/__missing_retention_entry_test__.md"
                assert not (batch_root / missing).exists()
                bad_config["prompt"][key] = missing
                bad_run = replace(context.run, grader_config_json=pilot._canonical_json(bad_config))
                bad_context = replace(context, grading=replace(context.grading, runs=(bad_run,)))
                with pytest.raises(ValueError) as refused:
                    reader._entry(bad_context, deepcopy(recorded))
                assert Path.cwd() == caller_root and type(refused.value) is ValueError
                message = "prompt template not found: " if key == "template" else "prompt.tool_template not found: "
                assert refused.value.args == (message + missing,)
                assert reader._terminal_diagnostic(refused.value, "terminal_binding") == {
                    "verification_substage": "terminal_binding", "verification_reason": "unclassified_verification_error"}

            bad_terminal = deepcopy(terminal)
            bad_terminal["binding"]["entry"]["config_hash"] = "e" * 16
            with pytest.raises(output.OutputPublicationRefused) as mismatch:
                reader._terminal_contract(context, bad_terminal)
            assert Path.cwd() == caller_root
            assert mismatch.value.args == ("retention_grade_readout_entry_mismatch",)
            assert reader._terminal_diagnostic(mismatch.value, "terminal_binding") == {
                "verification_substage": "terminal_binding", "verification_reason": "retention_grade_readout_entry_mismatch"}
            assert context.run.grader_config_json == config_bytes
            assert pilot._digest(template[0]["binding"]["entry"]) == expected_entry
            assert not effects and not any((root / name).exists() for name in (
                "claim-reserved.json", "publication-reserved.json", "judge-owner.json", "judge-receipt.json"))
        assert Path.cwd() == original_cwd
    assert observed_entries == [expected_entry, expected_entry] and effects == []


def test_retention_grade_terminal_diagnostics_are_closed_and_read_only(tmp_path, monkeypatch, capsys):
    assert reader.TERMINAL == "40712e0980cc05c31688fdbb98c693774fb90c0d"
    assert reader.TERMINAL_IDENTITY == {
        "sha256": "11eb15cd4cb783d35fcfda62b458f14d34bfb3742e60d949c6671a56399c9234", "size": 3119}
    assert reader.WRITER_SOURCE == "29e0353f1539265b1741e71be894fedf9be32a8b"
    assert reader.CLAIM == "dec305d669e3ca2e53c7f7b9ebfbe7974d661350"
    assert reader._TERMINAL_SUBSTAGES == (
        "metadata", "terminal_control", "terminal_binding", "claim_history", "terminal_identity")
    context = bridge.compile_request(reader.WRITER_SOURCE)
    template = _fixture(context)  # Real writer serializer; no payload projection is substituted.
    effects, git_calls, roots = [], [], []

    def forbidden(*args, **kwargs):
        effects.append("forbidden_effect")
        pytest.fail("terminal verification crossed a payload, write or paid boundary")

    for target, names in (
        (bridge, ("_authority", "prepare", "claim", "judge", "publish", "reconcile", "_ready", "_derived_inputs")),
        (grade, ("_ci_authority", "prepare", "claim", "judge", "publish", "reconcile", "_owned_judge", "setup", "_fetch")),
        (pilot, ("dispatch",)), (step8, ("main",)), (bridge.reader, ("read_result",)),
        (reader.readout, ("_recorded_projection",)),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)
    monkeypatch.setattr("core.tools.get_renderer_fingerprint", forbidden)
    monkeypatch.setattr(RubricLoader, "load", forbidden)
    common = tmp_path / "synthetic-git-metadata"
    common.mkdir()

    def git(path, *command, ok=(0,)):
        assert Path(path) == bridge.ROOT
        git_calls.append(command)
        answers = {("rev-parse", "--show-toplevel"): os.fsencode(path) + b"\n",
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): os.fsencode(common) + b"\n",
            ("rev-parse", "HEAD"): (OBSERVER + "\n").encode(),
            ("diff", "--name-only", "HEAD", "--"): b"",
            ("status", "--porcelain", "--untracked-files=normal"): b"",
            ("config", "--name-only", "--get-regexp",
             r"^(filter\.|include\.|includeif\.|extensions\.partialclone$|remote\..*\.promisor$|core\.alternaterefscommand$)"): b""}
        assert command in answers, "only the established Git metadata seam is simulated"
        return SimpleNamespace(stdout=answers[command], returncode=0)

    monkeypatch.setattr(source_checkout, "_git", git)
    monkeypatch.setattr(pilot, "_git", git)

    def invoke(api, phase="readout"):
        root = tmp_path / f"terminal-refusal-{len(roots)}"
        roots.append(root)
        args = ["--selector", reader.SELECTOR, "--reviewed-source-sha", OBSERVER,
                "--terminal-revision", reader.TERMINAL, "--root", str(root), "--phase", phase]
        status = grade.main(args, _test_api=api)
        captured = capsys.readouterr()
        text = captured.out if status == 0 else captured.err
        assert not (captured.err if status == 0 else captured.out)
        for private in (PRIVATE, TOKEN, str(tmp_path), retained._target(), '"criterion":', '"evidence":'):
            assert private not in text
        receipt = json.loads(text)
        assert receipt["remote_mutation_possible"] is False and receipt["judge_entry_requested"] is False
        assert receipt["inference_requested"] is False and receipt["automatic_retry"] is False
        assert receipt["invoice_complete"] is False
        assert receipt["materialized_input_fingerprint"] == {
            "status": "unavailable", "value": None, "comparison": None,
            "reason": "materialized_input_fingerprint_not_recorded"}
        assert not {"score", "terminal_identity", "recorded_task_cost", "file_identities"}.intersection(receipt)
        assert not effects
        return status, receipt

    api = _seed(monkeypatch, *deepcopy(template))
    with monkeypatch.context() as local:
        local.delenv("GITHUB_ACTIONS", raising=False)
        status, receipt = invoke(api, phase="plan")
        assert status == 0 and receipt["outcome"] == "plan_only"
        assert not {"verification_reason", "verification_substage"}.intersection(receipt)
        status, receipt = invoke(api)
        assert status == 2 and receipt["stage"] == "observer_authority"
        assert not {"verification_reason", "verification_substage"}.intersection(receipt)
    assert not api.calls and not git_calls and all(not root.exists() for root in roots)
    _environment(monkeypatch)

    # Actual terminal/claim/entry/history predicates succeed without fetching
    # either declared payload. Diagnostic state never grants a new operation.
    before = deepcopy((api.trees, api.writers, api.branches))
    root = grade._root(tmp_path / "verified-controls", new=True)
    with retained._session(api, response_bytes_limit=output.MAX_RECORD_BYTES) as (transport, token, deadline):
        facade = reader._ReadOnlyGrade(transport, retained._target(), token)
        terminal, entry, identity = facade.verify(context, root, deadline)
    assert identity == reader.TERMINAL_IDENTITY and entry == template[0]["binding"]["entry"]
    assert terminal["claim_commit"] == reader.CLAIM and terminal["child"]["cleanup_confirmed"] is True
    assert facade._verification_substage == "terminal_identity"
    assert api.downloads == [(reader.TERMINAL, bridge.TERMINAL_PATH),
                            (reader.TERMINAL, bridge.TERMINAL_PATH), (reader.CLAIM, bridge.CLAIM_PATH)]
    assert sum(name == "metadata" for name, _ in api.calls) == 1 and len(api.paths) == 5
    assert (api.trees, api.writers, api.branches) == before and not api.commits

    cases = (
        ("private_target", "metadata", "existing_exact_private_repository_required"),
        ("terminal_hash", "terminal_control", "payload_identity_mismatch"),
        ("terminal_history", "terminal_control", "retention_control_history_mismatch"),
        ("writer_source", "terminal_binding", "retention_grade_readout_writer_binding_mismatch"),
        ("entry_hash", "terminal_binding", "retention_grade_readout_entry_mismatch"),
        ("claim_hash", "claim_history", "payload_identity_mismatch"),
        ("claim_history", "claim_history", "retention_control_history_mismatch"),
        ("inherited_claim_history", "claim_history", "remote_output_history_mismatch"),
        ("file_history", "claim_history", "remote_output_history_mismatch"),
    )
    for case, substage, reason in cases:
        t, c, payload, ledger = deepcopy(template)
        if case == "writer_source":
            t["binding"]["source_sha"] = "e" * 40
        elif case == "entry_hash":
            t["binding"]["entry"]["config_hash"] = "e" * 16
        elif case == "claim_hash":
            t["claim_identity"]["sha256"] = "0" * 64
        bad = _seed(monkeypatch, t, c, payload, ledger)
        if case == "private_target":
            bad.private = False
        elif case == "terminal_hash":
            monkeypatch.setattr(reader, "TERMINAL_IDENTITY", {**reader.TERMINAL_IDENTITY, "sha256": "0" * 64})
        elif case == "terminal_history":
            bad.writers[reader.TERMINAL][bridge.TERMINAL_PATH] = reader.CLAIM
        elif case in {"claim_history", "inherited_claim_history"}:
            revision = reader.CLAIM if case == "claim_history" else reader.TERMINAL
            bad.writers[revision][bridge.CLAIM_PATH] = bridge.PARENT["revision"]
        elif case == "file_history":
            bad.writers[reader.TERMINAL][t["files"][0]["path"]] = reader.CLAIM
        before = deepcopy((bad.trees, bad.writers, bad.branches))
        status, receipt = invoke(bad)
        safe = {key: receipt.get(key) for key in ("reason", "stage", "verification_reason", "verification_substage")}
        assert status == 2 and receipt["outcome"] == "refused", safe
        assert safe == {"reason": "retention_grade_readout_contract_refused", "stage": "grade_terminal",
                        "verification_reason": reason, "verification_substage": substage}
        assert receipt["http_status"] is None
        assert all(name in {bridge.TERMINAL_PATH, bridge.CLAIM_PATH} for _, name in bad.downloads)
        assert sum(name == "metadata" for name, _ in bad.calls) == 1
        assert len(bad.paths) <= 5 and len(bad.downloads) <= 3
        assert (bad.trees, bad.writers, bad.branches) == before and not bad.commits

    class RefusalSubclass(output.OutputPublicationRefused):
        pass

    class StringSubclass(str):
        pass

    class UnprintableError(ValueError):
        def __str__(self):
            pytest.fail("diagnostics must not stringify an unknown exception")

    known = "retention_control_history_mismatch"
    extra_args = output.OutputPublicationRefused(known)
    extra_args.args = (known, PRIVATE)
    wrapped = ValueError(PRIVATE)
    wrapped.__cause__ = output.OutputPublicationRefused(known, 503)
    for error in (RefusalSubclass(known), output.OutputPublicationRefused(StringSubclass(known)),
                  extra_args, wrapped, output.OutputPublicationRefused({"private": PRIVATE}),
                  UnprintableError(PRIVATE)):
        assert reader._terminal_diagnostic(error, StringSubclass("metadata")) == {
            "verification_substage": "unclassified_verification_substage",
            "verification_reason": "unclassified_verification_error"}
    assert reader._terminal_diagnostic(output.OutputPublicationRefused(known), PRIVATE) == {
        "verification_substage": "unclassified_verification_substage", "verification_reason": known}

    # Simulate only external failure boundaries; the real CLI must still refuse.
    for error, expected_reason, http_status in (
        (OSError(PRIVATE), "unclassified_verification_error", None),
        (output.OutputPublicationRefused(PRIVATE), "unclassified_verification_error", None),
        (wrapped, "unclassified_verification_error", 503),
        (output.OutputPublicationRefused("hf_http_failed", 503), "hf_http_failed", 503),
        (UnprintableError(PRIVATE), "unclassified_verification_error", None),
    ):
        bad = _seed(monkeypatch, *deepcopy(template))

        def failed_metadata(**kwargs):
            bad.record("metadata", kwargs)
            raise error

        monkeypatch.setattr(bad, "repo_info", failed_metadata)
        before = deepcopy((bad.trees, bad.writers, bad.branches))
        status, receipt = invoke(bad)
        assert status == 2 and receipt["outcome"] == "refused"
        assert receipt["reason"] == "retention_grade_readout_contract_refused" and receipt["stage"] == "grade_terminal"
        assert receipt["verification_substage"] == "metadata" and receipt["verification_reason"] == expected_reason
        assert receipt["http_status"] == http_status
        assert bad.calls == [("metadata", reader.TERMINAL)] and not bad.paths and not bad.downloads
        assert (bad.trees, bad.writers, bad.branches) == before and not bad.commits
    assert all(not (root / name).exists() for root in roots for name in (
        "claim-reserved.json", "publication-reserved.json", "judge-owner.json", "judge-receipt.json"))
    assert effects == [] and git_calls
