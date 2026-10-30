"""Synthetic cross-job wallet transfer. Never a provider or billing test."""

import hashlib
import json
import os
import socket
import sqlite3
import stat
import subprocess
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

import gpt56_pilot_ledger_handoff as handoff
import gpt56_pilot_usd_budget as usd
from core import runner_environment as host

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/gpt56-pilot-ledger-handoff.yml"
REUSABLE = ROOT / ".github/workflows/gpt56-pilot-ledger-shard.yml"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch, native_hosted_runner):
    def forbidden(*args, **kwargs):
        pytest.fail("model-free handoff attempted a network connection or subprocess")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setenv("GITHUB_REPOSITORY", "hyeonsangjeon/gdpval-realworks")
    monkeypatch.setenv("GITHUB_SHA", "1" * 40)


@pytest.fixture
def lineage():
    return {"repository": "hyeonsangjeon/gdpval-realworks", "run_id": "123456789",
            "run_attempt": "1", "source_sha": "1" * 40}


def _step(root, lineage, index, previous=None, digest=None, suffix=""):
    output = root / f"handoff-{index}{suffix}"
    report, fingerprint = handoff.run_shard(root / f"workspace-{index}{suffix}", output,
        lineage=lineage, shard_index=index, predecessor=previous, expected_sha256=digest)
    return output, report, fingerprint


def _chain(root, lineage, count=5):
    rows = []
    previous = digest = None
    for index in range(count):
        previous, report, digest = _step(root, lineage, index, previous, digest)
        rows.append((previous, report, digest))
    return rows


def _changed_manifest(directory, mutate):
    path = directory / handoff.MANIFEST
    value = json.loads(path.read_bytes())
    mutate(value)
    raw = handoff._json(value)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_five_fresh_workspaces_keep_one_wallet_and_both_origins(lineage, tmp_path):
    rows = _chain(tmp_path, lineage)
    identities = [row[1]["scenarios"]["continuity"]["binding"] for row in rows]
    assert all(value == identities[0] for value in identities)
    assert [row[1]["scenarios"]["continuity"]["snapshot"]["combined_modeled_usd"]
            for row in rows] == ["5", "10", "15", "20", "25"]
    snapshot = rows[-1][1]["scenarios"]["continuity"]["snapshot"]
    assert snapshot["inference_known_usd"] == "5"
    assert snapshot["grading_known_usd"] == "20"
    assert snapshot["remaining_modeled_usd"] == "175"
    assert snapshot["approved_maximum_usd"] == "200"
    assert snapshot["actual_billing_hard_limit_verified"] is False
    output, _, digest = rows[-1]
    proof = handoff.verify_completed_handoff(output, digest, lineage=lineage,
                                             workspace=tmp_path / "audit")
    assert proof == {"schema": "pilot-ledger-handoff-proof-v1", "lineage": lineage,
                    "continuity_passed": True, "next_shard_ceiling_refusal_passed": True,
                    "interrupted_settlement_no_double_charge_passed": True,
                    "synthetic_combined_usd": {"continuity": "25", "ceiling": "196", "interruption": "25"},
                    "task_count": 5, "model_calls": 0, "judge_calls": 0,
                    "paid_execution_allowed": False, "actual_billing_hard_limit_verified": False}


def test_predecessor_refuses_ceiling_before_next_worker_starts(lineage, tmp_path, monkeypatch):
    rows = _chain(tmp_path, lineage, 4)
    previous, report, digest = rows[-1]
    refused = report["history"][-1]["scenarios"]["ceiling"]
    assert refused["snapshot"]["combined_modeled_usd"] == "196"
    assert refused["snapshot"]["stop_reason"] == "usd_ceiling_exceeded"
    assert refused["snapshot"]["stop_source"] == "inference"
    assert refused["snapshot"]["blocked_inference"] == 1
    assert refused["next_worker_allowed"] is False
    original = handoff._fake_transport
    def no_ceiling_transport(scenario, *args):
        assert scenario != "ceiling", "over-budget shard entered its transport"
        return original(scenario, *args)
    monkeypatch.setattr(handoff, "_fake_transport", no_ceiling_transport)
    _, final, _ = _step(tmp_path, lineage, 4, previous, digest)
    stopped = final["history"][-1]["scenarios"]["ceiling"]
    assert stopped["worker_started"] is False and stopped["synthetic_requests"] == 0
    assert stopped["snapshot"] == refused["snapshot"]


def test_interrupted_job_replays_settlement_without_a_second_debit(lineage, tmp_path):
    rows = _chain(tmp_path, lineage)
    interrupted = rows[1][1]["history"][-1]["scenarios"]["interruption"]
    assert interrupted["interruption_injected"] is True
    assert interrupted["snapshot"]["combined_modeled_usd"] == "6"
    resumed = rows[2][1]["history"][-1]["scenarios"]["interruption"]
    assert resumed["snapshot"]["combined_modeled_usd"] == "15"
    assert resumed["replayed_settlements"] == 3
    assert resumed["synthetic_requests"] == 3  # Lost job's grade + next task's two calls.
    final = rows[-1][1]
    assert sum(row["scenarios"]["interruption"]["synthetic_requests"] for row in final["history"]) == 10
    assert final["scenarios"]["interruption"]["snapshot"]["combined_modeled_usd"] == "25"
    with sqlite3.connect(tmp_path / "workspace-4/interruption" / usd.DIRECTORY / usd.DATABASE) as db:
        assert db.execute("SELECT COUNT(*),COUNT(DISTINCT id) FROM reservations").fetchone() == (10, 10)


@pytest.mark.parametrize("origin,expected", [("inference", "1"), ("grading", "5")])
def test_unknown_reply_keeps_reserve_after_transfer_and_never_retries(lineage, tmp_path, monkeypatch, origin, expected):
    original = handoff._fake_transport
    def lost_reply(scenario, task_id, role, amount):
        if scenario == "continuity" and role == origin:
            raise RuntimeError("synthetic lost reply")
        return original(scenario, task_id, role, amount)
    monkeypatch.setattr(handoff, "_fake_transport", lost_reply)
    previous, first, digest = _step(tmp_path, lineage, 0)
    stopped = first["scenarios"]["continuity"]["snapshot"]
    assert stopped["combined_modeled_usd"] == expected
    assert stopped["stop_reason"] == usd.UNKNOWN and stopped["unknown_requests"] == 1
    def never_resume_unknown(scenario, *args):
        assert scenario != "continuity"
        return original(scenario, *args)
    monkeypatch.setattr(handoff, "_fake_transport", never_resume_unknown)
    _, second, _ = _step(tmp_path, lineage, 1, previous, digest)
    assert second["scenarios"]["continuity"]["snapshot"] == stopped
    assert second["history"][-1]["scenarios"]["continuity"]["worker_started"] is False


@pytest.mark.parametrize("index", [1, 2, 3, 4])
def test_missing_predecessor_never_initializes_replacement_budget(lineage, tmp_path, index):
    with pytest.raises(handoff.HandoffRefused, match="handoff_predecessor_required"):
        _step(tmp_path, lineage, index)
    assert not (tmp_path / f"workspace-{index}").exists()


@pytest.mark.parametrize("change", ["db", "identity", "manifest", "extra_file", "missing_file"])
def test_tampering_or_partial_export_refuses_before_import(lineage, tmp_path, change):
    previous, _, digest = _step(tmp_path, lineage, 0)
    if change == "db":
        path = previous / "continuity-ledger.sqlite3"
        path.write_bytes(path.read_bytes() + b"tampered")
    elif change == "identity":
        path = previous / "continuity-identity.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif change == "manifest":
        (previous / handoff.MANIFEST).write_bytes(b"{}")
    elif change == "extra_file":
        (previous / "unexpected.txt").write_text("no arbitrary artifact members")
    else:
        (previous / "ceiling-ledger.sqlite3").unlink()
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, digest)
    assert not (tmp_path / "workspace-1").exists()


@pytest.mark.parametrize("role", ["handoff.json", "continuity-ledger.sqlite3", "interruption-identity.json"])
@pytest.mark.parametrize("kind", ["symlink", "hardlink"])
def test_artifact_links_are_not_adopted(lineage, tmp_path, role, kind):
    previous, _, digest = _step(tmp_path, lineage, 0)
    path = previous / role
    external = tmp_path / "external"
    path.rename(external)
    if kind == "symlink":
        path.symlink_to(external)
    else:
        os.link(external, path)
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, digest)
    assert not (tmp_path / "workspace-1").exists()


@pytest.mark.parametrize("field,value", [
    ("run_id", "999"), ("source_sha", "2" * 40), ("run_attempt", "2"),
    ("repository", "someone/other"),
])
def test_other_run_attempt_source_or_repository_cannot_reopen_wallet(lineage, tmp_path, field, value):
    previous, _, digest = _step(tmp_path, lineage, 0)
    changed = {**lineage, field: value}
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, changed, 1, previous, digest)
    assert not (tmp_path / "workspace-1").exists()


@pytest.mark.parametrize("field,value", [
    ("mode", "paid"), ("shard_index", True), ("shard_index", 3),
    ("model_calls", 1), ("model_calls", False), ("judge_calls", 1),
    ("paid_execution_allowed", True), ("task_ids", list(reversed(handoff.TASKS))),
])
def test_malformed_producer_claims_refuse_even_with_a_supplied_digest(lineage, tmp_path, field, value):
    previous, _, _ = _step(tmp_path, lineage, 0)
    digest = _changed_manifest(previous, lambda record: record.update({field: value}))
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, digest)


def test_invented_balance_cannot_replace_the_actual_database(lineage, tmp_path):
    previous, _, _ = _step(tmp_path, lineage, 0)
    def invent(record):
        current = record["scenarios"]["continuity"]["snapshot"]
        current.update(inference_known_usd="0", grading_known_usd="0", inference_input_output_usd="0",
                       combined_modeled_usd="0", remaining_modeled_usd="200")
        record["history"][-1]["scenarios"]["continuity"]["snapshot"] = deepcopy(current)
    digest = _changed_manifest(previous, invent)
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, digest)
    assert not (tmp_path / "handoff-1").exists()


def test_stale_stage_and_rollback_digest_are_not_latest_predecessor(lineage, tmp_path):
    rows = _chain(tmp_path, lineage, 2)
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 2, rows[0][0], rows[1][2])
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 2, rows[0][0], rows[0][2], suffix="old-stage")
    assert not (tmp_path / "workspace-2").exists()


def test_duplicate_json_keys_are_rejected(lineage, tmp_path):
    previous, _, _ = _step(tmp_path, lineage, 0)
    path = previous / handoff.MANIFEST
    raw = b'{"model_calls":0,' + path.read_bytes()[1:]
    path.write_bytes(raw)
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("destination", ["workspace", "output"])
def test_destinations_are_never_overwritten(lineage, tmp_path, destination):
    path = tmp_path / ("workspace-0" if destination == "workspace" else "handoff-0")
    path.mkdir()
    marker = path / "user-file"
    marker.write_text("preserve")
    with pytest.raises(handoff.HandoffRefused, match="handoff_destination_not_fresh"):
        _step(tmp_path, lineage, 0)
    assert marker.read_text() == "preserve"


def test_rehydrated_database_and_identity_are_private_regular_files(lineage, tmp_path):
    _chain(tmp_path, lineage, 2)
    for scenario in handoff.SCENARIOS:
        for role in (usd.IDENTITY, usd.DATABASE):
            path = tmp_path / "workspace-1" / scenario / usd.DIRECTORY / role
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert path.stat().st_nlink == 1 and not path.is_symlink()


def test_changed_runner_receipt_is_not_accepted(lineage, tmp_path):
    previous, _, _ = _step(tmp_path, lineage, 0)
    def change(record):
        observation = record["producer_runner"]["observation"]
        observation["run_id"] = "999"
        record["producer_runner"] = host.receipt("diagnostic", observation)
    digest = _changed_manifest(previous, change)
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, digest)


@pytest.mark.parametrize("mutation", ["balance_backwards", "wallet_id", "runner", "counter_type"])
def test_prior_history_cannot_be_replaced_by_a_new_wallet_or_refund(lineage, tmp_path, mutation):
    previous, _, _ = _chain(tmp_path, lineage, 2)[-1]
    def damage(record):
        historical = record["history"][0]
        snapshot = historical["scenarios"]["continuity"]["snapshot"]
        if mutation == "balance_backwards":
            snapshot.update(inference_known_usd="25", inference_input_output_usd="25",
                            combined_modeled_usd="29", remaining_modeled_usd="171")
        elif mutation == "wallet_id":
            snapshot["ledger_id"] = "f" * 32
        elif mutation == "runner":
            observed = historical["runner"]["observation"]
            observed["os_version_id"] = "22.04"
            historical["runner"] = host.receipt("diagnostic", observed)
        else:
            historical["scenarios"]["continuity"]["synthetic_requests"] = True
    digest = _changed_manifest(previous, damage)
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 2, previous, digest)
    assert not (tmp_path / "workspace-2").exists()


def test_pending_database_cannot_hide_behind_a_settled_receipt(lineage, tmp_path, monkeypatch):
    previous, _, _ = _step(tmp_path, lineage, 0)
    database = previous / "continuity-ledger.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("UPDATE reservations SET state='reserved' WHERE rowid=(SELECT MIN(rowid) FROM reservations)")
    raw = database.read_bytes()
    digest = _changed_manifest(previous, lambda record: record["scenarios"]["continuity"]["files"].update(
        {usd.DATABASE: {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}}))
    monkeypatch.setattr(handoff, "_fake_transport", lambda *a: pytest.fail("pending import reached work"))
    with pytest.raises(handoff.HandoffRefused):
        _step(tmp_path, lineage, 1, previous, digest)
    assert not (tmp_path / "handoff-1").exists()


def test_cli_exits_after_persisting_expected_interruption_and_resumes(lineage, tmp_path, monkeypatch, capsys):
    previous, _, digest = _step(tmp_path, lineage, 0)
    job_output = tmp_path / "github-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(job_output))
    exit_code = handoff.main(["run-shard", "--mode", "model-free", "--shard-index", "1",
        "--workspace", str(tmp_path / "workspace-1"), "--output", str(tmp_path / "handoff-1"),
        "--predecessor", str(previous), "--expected-sha256", digest])
    assert exit_code == 75
    report = json.loads(capsys.readouterr().out)
    assert report["model_calls"] == report["judge_calls"] == 0
    assert job_output.read_text().strip() == "manifest_sha256=" + report["manifest_sha256"]
    _, resumed, _ = _step(tmp_path, lineage, 2, tmp_path / "handoff-1", report["manifest_sha256"])
    assert resumed["scenarios"]["interruption"]["snapshot"]["combined_modeled_usd"] == "15"


@pytest.mark.parametrize("field,value", [("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_ACTIONS", "false"),
                                          ("GITHUB_RUN_ATTEMPT", "2")])
def test_cli_refuses_unapproved_host_or_rerun_before_creating_budget(lineage, tmp_path, monkeypatch, capsys, field, value):
    monkeypatch.setenv(field, value)
    assert handoff.main(["run-shard", "--mode", "model-free", "--shard-index", "0",
        "--workspace", str(tmp_path / "state"), "--output", str(tmp_path / "export")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "refused"
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("action", [lambda: socket.create_connection(("example.com", 443)),
                                    lambda: subprocess.Popen(["should-never-run"])])
def test_model_free_cli_denies_external_effects(action):
    with handoff.no_external_effects():
        with pytest.raises(handoff.HandoffRefused, match="model_free_external_effect_refused"):
            action()


def test_fixed_cohort_and_owner_cap_are_read_unchanged():
    profile = yaml.safe_load((ROOT / "batch-runner/experiments/execution_envelope/"
                             "gpt56_sol_foundry_codex_pilot_source_20261029_capture_counters.yaml").read_text())
    assert list(handoff.TASKS) == [row["task_id"] for row in profile["dataset"]["tasks"]]
    assert profile["pilot"]["relay_max_runs"] == 0  # No paid relay policy change.
    assert usd.APPROVED_MAXIMUM_USD == Decimal(200)
    assert hashlib.sha256(usd.CAP_PATH.read_bytes()).hexdigest() == usd.CAP_SHA256
    assert hashlib.sha256(usd.PRICE_PATH.read_bytes()).hexdigest() == usd.PRICE_SHA256


def test_workflow_has_exact_linear_chain_and_only_model_free_dispatch():
    document = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert set(document["on"]) == {"pull_request", "workflow_dispatch"}
    assert document["on"]["workflow_dispatch"]["inputs"] == {
        "mode": {"type": "choice", "required": "true", "default": "model-free", "options": ["model-free"]}}
    assert document["permissions"] == {"contents": "read"}
    jobs = document["jobs"]
    assert set(jobs) == {"contracts", "verify", *(f"shard_{i}" for i in range(1, 6))}
    for number in range(1, 6):
        job = jobs[f"shard_{number}"]
        previous = "contracts" if number == 1 else f"shard_{number - 1}"
        assert job["needs"] == previous
        assert job["uses"] == "./.github/workflows/gpt56-pilot-ledger-shard.yml"
        expected = {"mode": "model-free", "shard_index": str(number - 1)}
        if number > 1:
            expected.update(predecessor_artifact="${{ needs." + previous + ".outputs.artifact_id }}",
                            predecessor_sha256="${{ needs." + previous + ".outputs.manifest_sha256 }}")
        assert job["with"] == expected
    assert jobs["verify"]["needs"] == "shard_5"
    assert jobs["contracts"]["runs-on"] == jobs["verify"]["runs-on"] == "ubuntu-24.04"
    assert jobs["contracts"]["timeout-minutes"] == "15"
    assert jobs["verify"]["timeout-minutes"] == "10"


def test_reusable_job_requires_exact_failure_and_immutable_predecessor():
    document = yaml.load(REUSABLE.read_text(), Loader=yaml.BaseLoader)
    assert set(document["on"]) == {"workflow_call"}
    assert document["permissions"] == {"contents": "read"}
    job = document["jobs"]["shard"]
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == "10"
    steps = job["steps"]
    download = next(step for step in steps if "download-artifact@" in step.get("uses", ""))
    assert download["with"]["artifact-ids"] == "${{ inputs.predecessor_artifact }}"
    assert "name" not in download["with"] and "pattern" not in download["with"]
    worker = next(step for step in steps if step.get("id") == "worker")
    checked = next(step for step in steps if step.get("id") == "checked")
    assert [step.get("id") for step in steps if step.get("continue-on-error") == "true"] == ["worker"]
    assert "--mode model-free" in worker["run"] and "120s" in worker["run"]
    assert "if timeout --signal=TERM" in worker["run"]  # bash -e must not lose exit 75.
    assert '"$WORKER_EXIT" == 75 && "$WORKER_OUTCOME" == failure' in checked["run"]
    assert '"$WORKER_EXIT" == 0 && "$WORKER_OUTCOME" == success' in checked["run"]
    assert steps.index(worker) < steps.index(checked) < next(i for i, step in enumerate(steps) if step.get("id") == "upload")
    assert '"$GITHUB_RUN_ATTEMPT" == 1' in steps[0]["run"]


@pytest.mark.parametrize("path", [WORKFLOW, REUSABLE])
def test_model_free_workflows_cannot_reference_secrets_or_paid_commands(path):
    text = path.read_text()
    for forbidden in ("secrets.", "secrets: inherit", "id-token:", "azure/login", "gh workflow run",
                      "step8_grade.py", "step2_run_inference.py", "--execute-paid", "copilot -p"):
        assert forbidden not in text
    document = yaml.load(text, Loader=yaml.BaseLoader)
    for job in document["jobs"].values():
        assert "environment" not in job
        for step in job.get("steps", []):
            if step.get("uses", "").startswith("actions/"):
                assert len(step["uses"].split("@", 1)[1]) == 40
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"
