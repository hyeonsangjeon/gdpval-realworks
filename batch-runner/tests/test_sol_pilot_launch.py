"""Offline admission and real SQLite checkpoints; no live execution claim."""

import hashlib
import json
import socket
import sqlite3
import subprocess
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from core import runner_environment as host
import gpt56_native_response_capture as response
import gpt56_pilot_usd_budget as usd
import gpt56_sol_pilot_launch as launch
import gpt56_sol_pilot_wallet as wallet

ROOT = Path(__file__).resolve().parents[2]
SHA = "1" * 40
CAPTURE = "2" * 64
PARENT = ROOT / ".github/workflows/gpt56-sol-paid-pilot.yml"
STAGE = ROOT / ".github/workflows/gpt56-sol-paid-pilot-stage.yml"


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch, native_hosted_runner):
    def refuse(*args, **kwargs):
        pytest.fail("unit test attempted a network/model/grader process")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


@pytest.fixture
def lineage():
    return {"repository": launch.REPOSITORY, "source_sha": SHA,
            "run_id": "123456789", "run_attempt": "1"}


def request_arguments(lineage):
    return {"execute_paid": True, "expected_source_sha": SHA, "checkout_sha": SHA,
            "context": {**lineage, "workflow_sha": SHA, "event": "workflow_dispatch",
                        "ref": "refs/heads/main"}, "runner_observation": host.observe()}


def test_exact_paid_request_only_on_hosted_2404(lineage):
    assert launch.validate_request(**request_arguments(lineage)) == lineage


@pytest.mark.parametrize("value", [False, None, 0, 1, "true", "false", "", {}, []])
def test_explicit_paid_opt_in_is_a_strict_boolean(lineage, value):
    arguments = request_arguments(lineage)
    arguments["execute_paid"] = value
    with pytest.raises(launch.LaunchRefused, match="explicit_execute_paid_required"):
        launch.validate_request(**arguments)


@pytest.mark.parametrize("field,value", [
    ("repository", "elsewhere/repo"), ("event", "push"), ("event", "pull_request"),
    ("ref", "refs/heads/launch-draft"), ("run_attempt", "2"), ("run_attempt", 1),
    ("run_id", "0"), ("run_id", "not-an-id"), ("source_sha", "3" * 40),
    ("workflow_sha", "3" * 40),
])
def test_wrong_workflow_identity_or_rerun_is_refused(lineage, field, value):
    arguments = request_arguments(lineage)
    arguments["context"][field] = value
    with pytest.raises(launch.LaunchRefused):
        launch.validate_request(**arguments)


@pytest.mark.parametrize("field,value", [
    ("os_version_id", "22.04"), ("image_os", "ubuntu22"), ("image_os", "ubuntu26"),
    ("runner_environment", "self-hosted"), ("github_hosted", False),
    ("github_hosted", 1), ("eligible_for_execution", False), ("github_actions", None),
    ("run_id", "987654"), ("run_attempt", "2"), ("image_version", None),
    ("platform_system", "Darwin"),
])
def test_wrong_host_or_runner_image_is_refused(lineage, field, value):
    arguments = request_arguments(lineage)
    arguments["runner_observation"][field] = value
    with pytest.raises(launch.LaunchRefused):
        launch.validate_request(**arguments)


@pytest.mark.parametrize("field", ["expected_source_sha", "checkout_sha"])
def test_independent_reviewed_sha_cannot_be_replaced(lineage, field):
    arguments = request_arguments(lineage)
    arguments[field] = "3" * 40
    with pytest.raises(launch.LaunchRefused):
        launch.validate_request(**arguments)


def test_missing_opt_in_refuses_before_host_git_or_source_reads(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("opt-in must be checked first")
    monkeypatch.setattr(launch.host, "require_execution", forbidden)
    monkeypatch.setattr(launch, "verify_contracts", forbidden)
    assert launch.main(["admit", "--expected-source-sha", SHA]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["refusal_code"] == "explicit_execute_paid_required"
    assert report["model_calls"] == report["judge_calls"] == 0
    assert report["new_reservation_usd"] == "0"


def test_wip_source_stop_remains_before_credentials_or_paid_calls(monkeypatch, capsys):
    assert launch.UNIMPLEMENTED_BRIDGE
    monkeypatch.setattr(launch, "admit", lambda **kwargs: {
        "schema": launch.SCHEMA, "model_calls": 0, "judge_calls": 0,
        "new_reservation_usd": "0", "remaining_implementation": list(launch.UNIMPLEMENTED_BRIDGE),
    })
    assert launch.main(["admit", "--execute-paid", "--expected-source-sha", SHA]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["refusal_code"] == "sol_pilot_execution_bridge_incomplete"
    assert report["paid_execution_allowed"] is False


@pytest.mark.parametrize("args", [
    ["admit", "--stage-index", "0"],
    ["run-stage"],
    ["run-stage", "--stage-index", "0", "--predecessor-artifact-id", "123"],
    ["run-stage", "--stage-index", "1"],
    ["run-stage", "--stage-index", "1", "--predecessor-artifact-id", "0", "--predecessor-sha256", CAPTURE],
    ["run-stage", "--stage-index", "1", "--predecessor-artifact-id", "123", "--predecessor-sha256", "bad"],
])
def test_stage_arguments_refused_before_admission(args, monkeypatch, capsys):
    monkeypatch.setattr(launch, "admit", lambda **kwargs: pytest.fail("invalid stage admitted"))
    assert launch.main([*args, "--execute-paid", "--expected-source-sha", SHA]) == 2
    assert json.loads(capsys.readouterr().out)["paid_execution_allowed"] is False


def test_fixed_ten_stages_mean_five_solves_then_five_grades_not_ten_tasks():
    stages = launch.execution_stages()
    assert len(stages) == 10
    assert [row["task_id"] for row in stages[:5]] == list(launch.TASKS)
    assert [row["task_id"] for row in stages[5:]] == list(launch.TASKS)
    assert [row["phase"] for row in stages] == ["solve"] * 5 + ["grade"] * 5
    assert [row["previous_index"] for row in stages] == [None, *range(9)]
    assert all(row["entrypoint"] == "step2_run_inference.run_inference" for row in stages[:5])
    assert all(row["entrypoint"] == "step8_grade.main" for row in stages[5:])


def create_ledger(root):
    root.mkdir(mode=0o700)
    return usd.PilotUsdLedger(root, capture_sha256=CAPTURE, task_ids=list(launch.TASKS), create=True)


def charge(ledger, index, amount, *, unknown=False, request_id=None):
    stage = launch.execution_stages()[index]
    account = ledger.begin("inference" if stage["phase"] == "solve" else "grading", stage["task_id"])
    request_id = request_id or hashlib.sha256(f"fixture-only-{index}".encode()).hexdigest()[:32]
    ticket = ledger.reserve(account, Decimal(amount), request_id=request_id)
    if unknown:
        ledger.abandon(account)
    else:
        assert ledger.settle(ticket, Decimal(amount), Decimal(0)) is None
    return ticket


def publish(ledger, root, lineage, index, *, previous=None, digest=None, outcome="success"):
    path = root / f"checkpoint-{index}"
    report, new_digest = wallet.publish_checkpoint(ledger, path, lineage=lineage,
        capture_sha256=CAPTURE, stage_index=index, outcome=outcome,
        runner_receipt=host.receipt("inference" if index < 5 else "grading"),
        predecessor=previous, predecessor_sha256=digest)
    return path, report, new_digest


def restore(root, previous, digest, lineage, index):
    return wallet.restore_checkpoint(root / f"worker-{index}", previous,
        expected_sha256=digest, lineage=lineage, capture_sha256=CAPTURE, stage_index=index)


def test_ten_stages_transfer_one_real_sqlite_wallet_without_new_allowances(tmp_path, lineage):
    ledger = create_ledger(tmp_path / "worker-0")
    previous = digest = None
    rows = []
    for index in range(10):
        if index:
            ledger = restore(tmp_path, previous, digest, lineage, index)
        charge(ledger, index, "1" if index < 5 else "4")  # Synthetic charges, real ledger methods.
        previous, report, digest = publish(ledger, tmp_path, lineage, index, previous=previous, digest=digest)
        assert ledger.closed
        rows.append(report)
    assert len({row["binding"]["ledger_id"] for row in rows}) == 1
    assert [row["snapshot"]["combined_modeled_usd"] for row in rows] == [
        "1", "2", "3", "4", "5", "9", "13", "17", "21", "25"]
    assert rows[-1]["snapshot"]["remaining_modeled_usd"] == "175"
    assert rows[-1]["snapshot"]["inference_known_usd"] == "5"
    assert rows[-1]["snapshot"]["grading_known_usd"] == "20"
    assert rows[-1]["evidence_boundary"] == wallet.BOUNDARY
    checked, _ = wallet.read_checkpoint(previous, expected_sha256=digest,
        lineage=lineage, capture_sha256=CAPTURE, next_stage=10)
    assert checked == rows[-1]


@pytest.mark.parametrize("amount", ["200", "201"])
def test_ceiling_refuses_before_next_workspace_or_worker(tmp_path, lineage, amount):
    ledger = create_ledger(tmp_path / "worker-0")
    if amount == "200":
        charge(ledger, 0, amount)
        outcome = "success"
    else:
        account = ledger.begin("inference", launch.TASKS[0])
        with pytest.raises(usd.PilotUsdRefused, match="usd_ceiling_exceeded"):
            ledger.reserve(account, Decimal(amount))
        outcome = "stopped"
    previous, _, digest = publish(ledger, tmp_path, lineage, 0, outcome=outcome)
    with pytest.raises(wallet.WalletRefused, match="stopped_wallet_cannot_start_next_stage"):
        restore(tmp_path, previous, digest, lineage, 1)
    assert not (tmp_path / "worker-1").exists()


def test_unknown_reservation_stays_booked_and_request_id_cannot_be_reused(tmp_path, lineage):
    ledger = create_ledger(tmp_path / "worker-0")
    request_id = charge(ledger, 0, "7.20", unknown=True)
    previous, report, digest = publish(ledger, tmp_path, lineage, 0)
    assert report["snapshot"]["unknown_consumed_usd"] == "7.20"
    assert report["snapshot"]["unknown_requests"] == 1
    ledger = restore(tmp_path, previous, digest, lineage, 1)
    try:
        before = ledger.snapshot()
        account = ledger.begin("inference", launch.TASKS[0])
        with pytest.raises(usd.PilotUsdRefused):
            ledger.reserve(account, Decimal("7.20"), request_id=request_id)
        assert ledger.snapshot()["combined_modeled_usd"] == before["combined_modeled_usd"]
        with sqlite3.connect(ledger.path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM reservations").fetchone() == (1,)
    finally:
        ledger.close()


def test_failed_stage_checkpoint_is_retained_but_next_stage_cannot_resume(tmp_path, lineage):
    ledger = create_ledger(tmp_path / "worker-0")
    charge(ledger, 0, "2", unknown=True)
    previous, _, digest = publish(ledger, tmp_path, lineage, 0, outcome="failed")
    with pytest.raises(wallet.WalletRefused):
        restore(tmp_path, previous, digest, lineage, 1)
    assert previous.is_dir() and not (tmp_path / "worker-1").exists()


def test_pending_reservation_refuses_publication_without_closing_owner(tmp_path, lineage):
    ledger = create_ledger(tmp_path / "worker-0")
    account = ledger.begin("inference", launch.TASKS[0])
    ledger.reserve(account, Decimal("2"))
    try:
        with pytest.raises(wallet.WalletRefused, match="pending_reservation_checkpoint_refused"):
            publish(ledger, tmp_path, lineage, 0)
        assert not ledger.closed
        assert not (tmp_path / "checkpoint-0").exists()
    finally:
        ledger.close()


@pytest.mark.parametrize("kind", ["digest", "capture", "run", "source", "attempt", "stage", "task_order", "extra_file", "missing_file", "symlink", "hardlink"])
def test_changed_checkpoint_or_lineage_refused_before_new_wallet(tmp_path, lineage, kind):
    ledger = create_ledger(tmp_path / "worker-0")
    charge(ledger, 0, "1")
    previous, _, digest = publish(ledger, tmp_path, lineage, 0)
    kwargs = {"expected_sha256": digest, "lineage": deepcopy(lineage), "capture_sha256": CAPTURE, "stage_index": 1}
    if kind == "digest":
        kwargs["expected_sha256"] = "f" * 64
    elif kind == "capture":
        kwargs["capture_sha256"] = "f" * 64
    elif kind in ("run", "source", "attempt"):
        key, value = {"run": ("run_id", "42"), "source": ("source_sha", "f" * 40), "attempt": ("run_attempt", "2")}[kind]
        kwargs["lineage"][key] = value
    elif kind == "stage":
        kwargs["stage_index"] = 2
    elif kind == "task_order":
        document = json.loads((previous / wallet.MANIFEST).read_bytes())
        document["task_ids"].reverse()
        raw = launch.canonical(document)
        (previous / wallet.MANIFEST).write_bytes(raw)
        kwargs["expected_sha256"] = hashlib.sha256(raw).hexdigest()
    elif kind == "extra_file":
        (previous / "extra").write_text("not admitted")
    elif kind == "missing_file":
        (previous / usd.DATABASE).unlink()
    elif kind == "symlink":
        path = previous / usd.DATABASE
        held = tmp_path / "held.sqlite"
        path.rename(held)
        path.symlink_to(held)
    elif kind == "hardlink":
        (tmp_path / "other.sqlite").hardlink_to(previous / usd.DATABASE)
    with pytest.raises(wallet.WalletRefused):
        wallet.restore_checkpoint(tmp_path / "new-wallet", previous, **kwargs)
    assert not (tmp_path / "new-wallet").exists()


def test_database_semantics_are_rechecked_not_just_its_new_hash(tmp_path, lineage):
    ledger = create_ledger(tmp_path / "worker-0")
    charge(ledger, 0, "3")
    previous, _, _ = publish(ledger, tmp_path, lineage, 0)
    with sqlite3.connect(previous / usd.DATABASE) as db:
        db.execute("UPDATE accounts SET io='0'")
    manifest = json.loads((previous / wallet.MANIFEST).read_bytes())
    data = (previous / usd.DATABASE).read_bytes()
    manifest["files"][usd.DATABASE] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    raw = launch.canonical(manifest)
    (previous / wallet.MANIFEST).write_bytes(raw)
    with pytest.raises(wallet.WalletRefused):
        restore(tmp_path, previous, hashlib.sha256(raw).hexdigest(), lineage, 1)


def test_destination_reuse_refused_instead_of_minting_or_overwriting(tmp_path, lineage):
    ledger = create_ledger(tmp_path / "worker-0")
    charge(ledger, 0, "1")
    previous, _, digest = publish(ledger, tmp_path, lineage, 0)
    restored = restore(tmp_path, previous, digest, lineage, 1)
    restored.close()
    before = (tmp_path / "worker-1" / usd.DIRECTORY / usd.DATABASE).read_bytes()
    with pytest.raises(wallet.WalletRefused):
        restore(tmp_path, previous, digest, lineage, 1)
    assert (tmp_path / "worker-1" / usd.DIRECTORY / usd.DATABASE).read_bytes() == before


@pytest.mark.parametrize("field,value", [("os_version_id", "22.04"), ("image_os", "ubuntu22"), ("runner_environment", "self-hosted")])
def test_checkpoint_rejects_non_2404_producer(tmp_path, lineage, field, value):
    ledger = create_ledger(tmp_path / "worker-0")
    observed = host.observe()
    observed[field] = value
    try:
        with pytest.raises(wallet.WalletRefused):
            wallet.publish_checkpoint(ledger, tmp_path / "bad", lineage=lineage, capture_sha256=CAPTURE,
                stage_index=0, outcome="success", runner_receipt=host.receipt("inference", observed))
    finally:
        ledger.close()


@pytest.mark.parametrize("fields,reason", [
    ({}, None),
    ({"served_model": "other-model"}, "served_model_mismatch"),
    ({"served_model": "not_reported"}, "served_model_unverified"),
    ({"reasoning_effort": "low"}, "reasoning_effort_mismatch"),
    ({"context_tokens": 258400}, "context_window_mismatch"),
    ({"context_tokens": "not_reported", "context_fields": {}}, None),
])
def test_existing_response_policy_preserves_796_without_claiming_live_wiring(tmp_path, fields, reason):
    store = response.NativeResponseArtifacts(tmp_path, "offline-response-contract")
    value = {"served_model": "gpt-5.6-sol", "reasoning_effort": "max",
             "context_tokens": 1_000_000, "context_fields": {"context_window": 1_000_000}}
    value.update(fields)
    assert store._field_reason(value) == reason


def test_workflow_is_dispatch_only_serial_2404_and_defaults_paid_off():
    parent = yaml.safe_load(PARENT.read_text())
    stage = yaml.safe_load(STAGE.read_text())
    triggers = parent.get("on", parent.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    assert triggers["workflow_dispatch"]["inputs"]["execute_paid"]["default"] is False
    assert parent["concurrency"]["cancel-in-progress"] is False
    assert parent["permissions"] == stage["permissions"] == {"contents": "read"}
    assert parent["jobs"]["admit"]["runs-on"] == stage["jobs"]["stage"]["runs-on"] == "ubuntu-24.04"
    assert 0 < stage["jobs"]["stage"]["timeout-minutes"] <= 360
    jobs = parent["jobs"]
    previous = "admit"
    for entry in launch.execution_stages():
        name = f"{entry['phase']}_{entry['task_index'] + 1}"
        job = jobs[name]
        assert job["needs"] == previous
        assert job["uses"] == "./.github/workflows/gpt56-sol-paid-pilot-stage.yml"
        assert job["with"]["stage_index"] == entry["index"]
        assert job["with"]["execute_paid"] == "${{ inputs.execute_paid }}"
        if entry["index"]:
            assert job["with"]["predecessor_artifact_id"] == "${{ needs." + previous + ".outputs.artifact_id }}"
            assert job["with"]["predecessor_sha256"] == "${{ needs." + previous + ".outputs.manifest_sha256 }}"
        previous = name
    assert len(jobs) == 11
    text = PARENT.read_text() + STAGE.read_text()
    for forbidden in ("secrets.", "id-token:", "azure/login", "continue-on-error", "_fake_transport"):
        assert forbidden not in text
    assert "sol_pilot_execution_bridge_incomplete" in (ROOT / "batch-runner/gpt56_sol_pilot_launch.py").read_text()


def test_original_profile_seal_scope_and_price_hashes_are_unchanged():
    raw = (ROOT / launch.PROFILE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == launch.PROFILE_SHA256
    plan = yaml.safe_load(raw)
    assert plan["dispatch_grading_identity"]["grader_template_source_hash"] == launch.GRADER_SOURCE_HASH
    for path, digest in plan["source_pins"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path
    assert usd.APPROVED_MAXIMUM_USD == 200
    assert hashlib.sha256(usd.CAP_PATH.read_bytes()).hexdigest() == usd.CAP_SHA256
    assert hashlib.sha256(usd.PRICE_PATH.read_bytes()).hexdigest() == usd.PRICE_SHA256
