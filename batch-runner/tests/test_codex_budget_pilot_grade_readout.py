"""One offline readout selector; synthetic writer evidence is not the live grade.

Real compiler, Step8 serialization, CostReceiptLedger export, publisher and
immutable terminal/file validators run with the existing fake external seams.
After fixture publication, every mutation, preparation and judge seam refuses.
"""

import copy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
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
import step8_grade as step8
from core.cost_receipts import BUCKET_GRADING, CallUsage, CostReceiptLedger, ledger_reference, load_receipt_price_table
from . import test_codex_budget_pilot_grading as base
from .test_codex_budget_pilot_grading import boundaries  # noqa: F401 — every real external boundary is forbidden

OBSERVER = "d" * 40
PRIVATE = "PRIVATE-canary https://private.invalid/path?token=PRIVATE"


@pytest.fixture(scope="module")
def compilations():
    return {source: pilot.compile_pilot(ci.CAMPAIGN, source)
            for source in (grading.RETAINED_PRODUCER_SOURCE, readout.WRITER_SOURCE, OBSERVER)}


@pytest.fixture(scope="module")
def compiled_cells():
    return lru_cache(maxsize=8)(adapter.compile_cell_grading_plan)


@pytest.fixture
def case(tmp_path, monkeypatch, compilations, compiled_cells):
    monkeypatch.setattr(base, "SOURCE", grading.RETAINED_PRODUCER_SOURCE)
    monkeypatch.setattr(base, "TERMINAL", grading.RETAINED_TERMINAL)
    state = base.case.__wrapped__(tmp_path, monkeypatch, compilations[base.SOURCE], compiled_cells)
    original_compile = pilot.compile_pilot
    monkeypatch.setattr(pilot, "compile_pilot", lambda campaign, source:
        copy.deepcopy(compilations[source]) if campaign == ci.CAMPAIGN and source in compilations
        else original_compile(campaign, source))
    state.context = grading.compile_request("pilot/" + grading.RETAINED_CELL, readout.WRITER_SOURCE,
        grading.RETAINED_TERMINAL, producer_source_sha=grading.RETAINED_PRODUCER_SOURCE)
    for key in ("GITHUB_SHA", "PILOT_WORKFLOW_SHA"):
        monkeypatch.setenv(key, readout.WRITER_SOURCE)
    monkeypatch.setenv("GITHUB_RUN_ID", readout.WRITER_RUN["id"])
    monkeypatch.setenv("PILOT_GRADE_APPROVAL_REQUEST_SHA256", grading._context_approval(state.context, readout.WRITER_RUN))
    state.api.branches.update({"main": retained.BOOTSTRAP, retained.BRANCH: grading.RETAINED_TERMINAL})
    return state


def _writer(case, capsys, tmp_path, monkeypatch, scenario):
    mode = {"partial": "partial", "failed": "error", "ungraded": "missing", "missing_ledger": "no_ledger"}.get(scenario, "grade")
    if mode == "missing":
        original = case.transport.process

        def no_payload(*args, **kwargs):
            original(*args, **kwargs)  # Genuine owned-cleanup fixture, no file.
            return SimpleNamespace(returncode=0)

        monkeypatch.setattr(case.transport, "process", no_payload)
    ready = base.judged(case, capsys, mode)
    assert ready["entry"]["grader_source_hash"] == readout.GRADER_SOURCE_HASH
    assert ready["entry"]["config_hash"] == readout.CONFIG_SHA256[:16]
    assert hashlib.sha256(case.context.run.grader_config_json.encode()).hexdigest() == readout.CONFIG_SHA256
    if mode not in {"missing", "no_ledger"}:
        path = case.root / "source" / ready["entry"]["grade_path"]
        ledger_path = path.with_name(path.stem + ".cost_ledger.jsonl")
        with CostReceiptLedger(tmp_path / "recorded-cost.sqlite3", run_id=ready["entry"]["cost_run_id"],
                               price_table=load_receipt_price_table()) as ledger:
            model = json.loads(case.context.run.grader_config_json)["judge"]["model"]
            ledger.reserve(call_id="recorded-call", task_id=case.context.cell["task_id"], stage="grading",
                retry_kind="none", provider="azure", requested_model=model, note="synthetic_recorded_call")
            if scenario == "partial_cost":
                ledger.settle("recorded-call", usage=CallUsage(input_tokens=111, cached_input_tokens=17,
                    output_tokens=23, reasoning_tokens=8), resolved_model=model)
                ledger.reserve(call_id="unsettled-call", task_id=case.context.cell["task_id"], stage="grading",
                    retry_kind="none", provider="azure", requested_model=model)
            digest = ledger.export_jsonl(ledger_path)
            receipt = ledger.receipt_for(case.context.cell["task_id"], BUCKET_GRADING).as_dict()
        payload = pilot._json_object(path.read_bytes())
        for task in payload["tasks"]:
            task["grading_cost"] = receipt
        payload["summary"] = step8._compute_summary(payload["tasks"])
        payload["cost_ledger"] = ledger_reference(str(ledger_path.relative_to(case.root / "source")), digest)
        path.write_bytes(base._json(payload))
    assert base.invoke(case, capsys, "publish")[0] == 0
    revision = case.api.branches[grading.BRANCH]
    terminal_path = grading._paths(case.context.cell)[1]
    terminal = pilot._json_object(case.api.trees[revision][terminal_path])
    return revision, terminal_path, terminal


def _workflow_contract():
    jobs = yaml.safe_load((pilot.ROOT / grading.WORKFLOW).read_bytes())["jobs"]
    job = jobs["pilot-readout"]
    assert job["permissions"] == {"contents": "read"} and job["environment"] == {"name": "grading"}
    assert "needs" not in job and job["timeout-minutes"] == 25
    for condition in ("inputs.experiment_yaml == 'pilot/grade-readout'", "inputs.paid_approval == false",
                      "github.ref == 'refs/heads/main'", "github.sha == github.workflow_sha", "github.run_attempt == '1'"):
        assert condition in job["if"]
    for name in ("pilot-plan", "pilot-approve-paid", "pilot-live"):
        assert "inputs.experiment_yaml != 'pilot/grade-readout'" in jobs[name]["if"]
    for name in ("validate-request", "approve-paid", "grade-dry-run", "grade", "verify-published"):
        assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in jobs[name]["if"]
    raw = yaml.safe_dump(job)
    for forbidden in ("id-token", "azure/login", "AZURE", "FOUNDRY", "--phase claim", "--phase judge",
                      "--phase publish", "--phase setup", "--phase prepare", "renderer", "upload-artifact"):
        assert forbidden not in raw
    assert "secrets." not in yaml.safe_dump(job["env"])
    secret_steps = [step for step in job["steps"] if "secrets." in yaml.safe_dump(step)]
    assert len(secret_steps) == 1 and secret_steps[0] is job["steps"][-1]
    assert secret_steps[0]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert secret_steps[0]["if"] == "inputs.dry_run == false && success()"
    assert "--phase readout" in secret_steps[0]["run"] and "--phase" not in job["steps"][-2]["run"]
    assert job["steps"][0]["with"] == {"ref": "${{ github.sha }}", "persist-credentials": False}
    from scripts import check_grader_hash_freeze as freeze
    assert freeze.is_paid_path_job("pilot-live") and not freeze.is_paid_path_job("pilot-readout")


@pytest.mark.parametrize("scenario", [
    "graded", "partial", "failed", "ungraded", "missing_ledger", "partial_cost", "advanced_snapshot",
    "wrong_writer", "foreign_run", "source", "hash", "bytes", "path", "claim", "cleanup", "outcome",
    "raw_judge", "hostile_text", "private_cost_reason", "private_target", "absent", "plan", "cross_phase", "rerun", "observer_spoof",
])
def test_closed_retained_grade_readout(case, tmp_path, monkeypatch, capsys, scenario):
    no_read = scenario in {"plan", "cross_phase", "rerun", "observer_spoof"}
    revision = terminal_path = terminal = None
    if not no_read:
        revision, terminal_path, terminal = _writer(case, capsys, tmp_path, monkeypatch, scenario)
        result_record = next((row for row in terminal["files"] if row["role"] == "grade_result"), None)
        if scenario in {"source", "raw_judge", "hostile_text", "private_cost_reason"}:
            payload = pilot._json_object(case.api.trees[revision][result_record["path"]])
            if scenario == "source":
                payload["source_inference_revision"] = "e" * 40
            elif scenario == "raw_judge":
                payload["tasks"][0]["items"][0]["judge_raw_response"] = PRIVATE
            elif scenario == "private_cost_reason":
                payload["tasks"][0]["grading_cost"]["missing_reasons"] = ["private_canary"]
            else:
                payload["tasks"][0]["sector"] = PRIVATE
                payload["tasks"][0]["items"][0].update(criterion=PRIVATE, evidence=PRIVATE)
                payload["tasks"][0]["grading_cost"]["components"][0]["provider"] = PRIVATE
            data = base._json(payload)
            case.api.trees[revision][result_record["path"]] = data
            result_record.update(retained._object(result_record["path"], data))
        elif scenario == "wrong_writer":
            terminal["binding"]["controller_source_sha"] = OBSERVER
        elif scenario == "foreign_run":
            terminal["binding"]["github_run"]["id"] = "36161541598"
            terminal["binding"]["approval_request_sha256"] = grading._context_approval(
                case.context, terminal["binding"]["github_run"])
        elif scenario == "hash":
            terminal["binding"]["grader_source_hash"] = "e" * 64
        elif scenario == "path":
            result_record["path"] = "PRIVATE/foreign.json"
        elif scenario == "claim":
            claim_path = grading._paths(case.context.cell)[0]
            case.api.trees[terminal["claim_commit"]][claim_path] += b" "
        elif scenario == "cleanup":
            terminal["child"]["cleanup_confirmed"] = False
        elif scenario == "outcome":
            terminal["outcome"] = "failed"
        elif scenario == "private_target":
            case.api.private = False
        elif scenario == "bytes":
            download = case.api.hf_hub_download

            def changed_bytes(**kwargs):
                path = Path(download(**kwargs))
                if kwargs["filename"] == result_record["path"]:
                    path.write_bytes(b"PRIVATE changed bytes")
                return str(path)

            monkeypatch.setattr(case.api, "hf_hub_download", changed_bytes)
        case.api.trees[revision][terminal_path] = retained._encoded(terminal)
        if scenario == "advanced_snapshot":
            head = "f" * 40
            case.api.seed(head, revision, {"unrelated-cell/PRIVATE": b"PRIVATE unrelated payload"})
            case.api.branches[grading.BRANCH] = head
        elif scenario == "absent":
            case.api.branches[grading.BRANCH] = retained.BOOTSTRAP

    def forbidden(*args, **kwargs):
        pytest.fail("readout crossed a mutation, preparation or judge boundary")

    for name in ("prepare", "claim", "judge", "publish", "reconcile", "setup", "_retained_input", "_entry_contract", "_ready"):
        monkeypatch.setattr(grading, name, forbidden)
    monkeypatch.setattr(case.api, "create_commit", forbidden)
    monkeypatch.setattr(case.api, "create_branch", forbidden)
    monkeypatch.setattr(output, "_hf_client", forbidden)
    for key, value in {"GITHUB_SHA": OBSERVER, "PILOT_WORKFLOW_SHA": OBSERVER, "GITHUB_JOB": "pilot-readout",
                       "GITHUB_RUN_ID": "900001", "PILOT_GRADE_PAID_APPROVAL": "false"}.items():
        monkeypatch.setenv(key, value)
    for key in ("PILOT_GRADE_APPROVAL_RESULT", "PILOT_GRADE_APPROVAL_REQUEST_SHA256"):
        monkeypatch.delenv(key)
    case.api.calls.clear()
    frozen = copy.deepcopy((case.api.trees, case.api.writers, case.api.branches, case.api.events))
    source_checks = []

    def observer_source(plan, parent):
        assert plan["reviewed_source_sha"] == OBSERVER
        source_checks.append(OBSERVER)

    observer = SimpleNamespace(require_source=observer_source)
    root = tmp_path / "readout"
    args = ["--selector", readout.SELECTOR, "--reviewed-source-sha", OBSERVER,
            "--terminal-revision", grading.RETAINED_TERMINAL, "--root", str(root), "--phase", "readout"]
    if scenario == "plan":
        _workflow_contract()
        monkeypatch.delenv("HF_TOKEN")
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        args[-1] = "plan"
    elif scenario == "cross_phase":
        args[-1] = "setup"
    elif scenario == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif scenario == "observer_spoof":
        args[3] = readout.WRITER_SOURCE

    code = grading.main(args, _test_api=case.api, _test_transport=observer)
    capture = capsys.readouterr()
    text = capture.out + capture.err
    assert len(text.splitlines()) == 1
    for private in ("PRIVATE", "private_canary", base.TOKEN, case.api.repo, str(tmp_path), "https://", "Traceback"):
        assert private not in text
    observed = json.loads(text)
    assert (case.api.trees, case.api.writers, case.api.branches, case.api.events) == frozen
    assert all(name in {"metadata", "paths", "download"} for name, _ in case.api.calls)
    assert observed["remote_mutation_possible"] is False and observed["judge_entry_requested"] is False
    assert observed["inference_requested"] is False and observed["automatic_retry"] is False
    assert observed["invoice_complete"] is False and observed["http_request_count"] is None
    if no_read:
        assert case.api.calls == [] and source_checks == [] and not root.exists()
        assert code == (0 if scenario == "plan" else 2)
        if scenario == "cross_phase":
            args[1], args[-1] = "pilot/" + grading.RETAINED_CELL, "readout"
            assert grading.main(args, _test_api=case.api, _test_transport=observer) == 2
            rejected = capsys.readouterr()
            assert json.loads(rejected.err)["reason"] == "pilot_grade_mode_conflict"
            assert "PRIVATE" not in rejected.out + rejected.err
            assert case.api.calls == [] and source_checks == [] and not root.exists()
        return
    assert source_checks == [OBSERVER]
    successful = {"graded", "partial", "failed", "ungraded", "missing_ledger", "partial_cost", "advanced_snapshot", "hostile_text"}
    if scenario not in successful:
        assert code == 2 and observed["outcome"] == "refused" and "grade_state" not in observed
        assert observed["reason"] == "grade_readout_contract_refused"
        return
    assert code == 0 and observed["outcome"] == "verified_retained_grade"
    assert observed["grade_state"] == {"partial": "partial", "failed": "failed", "ungraded": "ungraded"}.get(scenario, "graded")
    assert observed["observer_source_sha"] == OBSERVER
    assert observed["grade_writer_source_sha"] == readout.WRITER_SOURCE
    assert observed["inference_producer_source_sha"] == grading.RETAINED_PRODUCER_SOURCE
    assert observed["grade_writer_run"] == readout.WRITER_RUN and observed["inference_terminal"] == grading.RETAINED_TERMINAL
    assert observed["grade_revision"] == revision and observed["terminal_identity"] == pilot._identity(retained._encoded(terminal))
    assert observed["observed_branch_head"] == ("f" * 40 if scenario == "advanced_snapshot" else revision)
    assert observed["grader_source_hash"] == readout.GRADER_SOURCE_HASH
    assert observed["expected_tasks"] == 1
    if scenario in {"partial", "failed", "ungraded"}:
        assert observed["score"] is None and observed["scored_tasks"] == 0
    else:
        assert observed["score"]["earned"] == observed["score"]["possible"] == 4
        assert observed["score"]["pct"] == 100 and observed["scored_tasks"] == 1
        assert observed["coverage"]["passed_items"] == observed["coverage"]["rubric_items"] == 2
    if scenario in {"ungraded", "missing_ledger"}:
        assert observed["ledger_state"] == "missing" and observed["ledger_derived_cost"] is None
        if scenario == "ungraded":
            assert observed["recorded_task_cost"] is None
        else:
            assert observed["recorded_task_cost"]["known_cost_usd"] is None
    else:
        assert observed["ledger_state"] == "present" and observed["ledger_derived_cost"]["status"] == "partial"
        assert observed["ledger_derived_cost"]["estimated_cost_usd"] is None
    if scenario == "partial_cost":
        cost = observed["ledger_derived_cost"]
        assert cost["known_cost_usd"] > 0 and cost["usage"]["input_tokens"] == 111 and cost["usage"]["output_tokens"] == 23
        assert cost["usage"]["cached_input_tokens"] == 17 and cost["usage"]["reasoning_tokens"] == 8
        assert cost["model_calls"] == 2 and cost["http_request_count"] is None
        assert "call_reachability_unknown" in cost["missing_reasons"] and "components" not in cost
    assert observed["partial_progress_retained"] is (scenario == "partial")
    # Even before any authorized revision/path exists, the facade cannot write
    # or use foreign refs/paths. This probe itself makes no fake remote call.
    api = readout._ReadOnlyGrade(case.api, case.api.repo, base.TOKEN, case.context)
    assert not any(hasattr(api, name) for name in ("create_commit", "create_branch", "upload_file", "delete_file", "list_repo_files"))
    with pytest.raises(output.OutputPublicationRefused):
        api.get_paths_info(repo_id=case.api.repo, repo_type="dataset", revision=retained.BRANCH,
                           paths=["PRIVATE/foreign"], expand=True, token=base.TOKEN)
