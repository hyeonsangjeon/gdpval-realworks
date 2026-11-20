"""Synthetic fixed-five scripts only; real client and Step8 contracts, no runtime."""

import copy
import json
from pathlib import Path
import socket
import subprocess
from unittest.mock import patch

import pytest

import ghcp_ahp_client as client
import ghcp_ahp_first_turn as first_turn
import ghcp_ahp_offline_fixture as fixtures
import ghcp_ahp_patched_runtime as patched
import ghcp_sol_actions_gate as gate
import ghcp_sol_grader_contract as bridge
import ghcp_sol_offline_rehearsal as rehearsal


def run_with_budget(*args, **kwargs):
    # Explicit fixture input for existing capture/guard tests, no runtime default.
    return rehearsal.run_rehearsal(*args, token_budget=fixtures.budget_config(), **kwargs)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline fixture attempted a native process or network")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)


def load(path):
    return json.loads(path.read_text())


def task_root(root, index=1):
    return root / "tasks" / gate.TASK_IDS[index]


def assert_boundary(report):
    assert all(report[key] is expected for key, expected in rehearsal.FLAGS.items())
    assert report["gate5_passed"] is report["ready_for_grading"] is False
    assert report["limits"] == {"turns": 64, "tool_calls": 32, "seconds": 1200}
    assert report["actual_calls"] == {"authentication": 0, "model_turns": 0, "capi_inference": 0, "external_http": 0, "judge": 0}
    assert report["overshoot_boundary"]["server_internal_model_requests"] == "no_finite_bound_proven"
    assert report["overshoot_boundary"]["server_internal_tool_calls"] == "no_finite_bound_proven"
    assert report["cap_scope"] == "client_admission_in_fixture_not_server_or_billing_limit"


def test_five_fresh_workspaces_through_real_first_turn_capture_and_step8(tmp_path):
    import step8_grade as step8
    import ghcp_sol_paid_gate as paid
    root = tmp_path / "five"
    with patch.object(step8, "load_local_inference_results", wraps=step8.load_local_inference_results) as reader, \
         patch.object(step8, "validate_local_deliverables", wraps=step8.validate_local_deliverables) as paths, \
         patch.object(paid, "stage_task", wraps=paid.stage_task) as stage, \
         patch.object(paid, "execute_task", side_effect=AssertionError("paid execution forbidden")), \
         patch.object(paid, "prepare_inputs", side_effect=AssertionError("input download forbidden")), \
         patch.object(first_turn, "require_report", wraps=first_turn.require_report) as guard:
        result = run_with_budget(root)
    assert result["fixture_pipeline_passed"] is True and result["exit_status"] == 0, result
    assert result == load(root / "rehearsal.json")
    assert reader.call_count == paths.call_count == 1
    assert stage.call_count == 5
    assert guard.call_count >= 5
    assert_boundary(result)
    assert [row["task_id"] for row in result["tasks"]] == list(gate.TASK_IDS)
    assert len({row["first_turn_attestation"]["thread_id"] for row in result["tasks"]}) == 5
    payload = load(root / "grader-input" / bridge.MANIFEST)
    assert payload["model_free"] is payload["synthetic"] is True
    assert payload["inference_performed"] is payload["grading_allowed"] is payload["execution_allowed"] is False
    assert payload["source_repo_id"] is payload["source_revision"] is None
    for index, row in enumerate(result["tasks"]):
        own = task_root(root, index)
        capture = rehearsal.validate_capture(own, gate.TASK_IDS[index])
        assert row["status"] == "completed" and row["capture_valid"] is True
        assert row["counts"]["admitted_or_observed_turns"] == row["counts"]["observed_tool_calls"] == 1
        assert row["counts"]["model_requests"] == row["counts"]["premium_requests"] == "not_reported"
        assert row["first_turn_attestation"]["synthetic"] is row["first_turn_attestation"]["verified"] is True
        assert row["first_turn_attestation"]["observed"] == first_turn.EXPECTED
        assert set(client.workspace_files(own / "workspace")) == {"reference_files/input.txt", "answer.txt"}
        assert len(capture["tool_calls"]) == 2 and len(capture["commands"]) == 1
        assert capture["commands"][0]["source"] == "tool_input_not_execution_proof"
        assert capture["cleanup"]["host_terminated"] is True
        assert capture["cleanup"]["dispose_attempts"] == 1 and capture["cleanup"]["cancel_attempts"] == 0
        published = payload["results"][index]
        assert published["status"] == "success" and published["synthetic"] is True and published["usage"] is None
        assert published["deliverable_files"] == [f"deliverable_files/{row['task_id']}/answer.txt"]
        target = root / "grader-input/workspace/upload" / published["deliverable_files"][0]
        assert target.read_bytes() == (own / "workspace/answer.txt").read_bytes()
        assert row["task_id"] in target.read_text() and "SYNTHETIC" in target.read_text()
    contract = result["grader_contract"]
    assert contract["step8_layout_valid"] is True and contract["grade"] is None
    assert contract["checks"]["live_refusals_observed"] == ["source_inference_identity_missing", "full220_rerun_identity_not_reusable"]
    assert contract["checks"]["grader_instantiated"] is contract["checks"]["rubric_loaded"] is False


@pytest.mark.parametrize("field", ["model", "effort", "context", "web"])
@pytest.mark.parametrize("damage", ["missing", "wrong"])
def test_first_turn_missing_or_mismatch_stops_only_its_task(tmp_path, field, damage):
    fixture = fixtures.fixed_five()
    task = fixture["tasks"][1]
    task["steps"] += fixtures.turn_steps("turn2", tools=False)
    records = task["first_turn_records"]
    response = records[4]["value"]["response"]
    owner, key, wrong = {
        "model": (response, "model", "gpt-5.3-codex"),
        "effort": (response["reasoning"], "effort", "xhigh"),
        "context": (records[-1]["value"]["params"]["tokenUsage"], "modelContextWindow", 200000),
        "web": (response, "output", [{"type": "web_search_call"}]),
    }[field]
    if damage == "missing":
        del owner[key]
    else:
        owner[key] = wrong
    result = run_with_budget(tmp_path / "isolated", fixture=fixture)
    assert_boundary(result)
    assert result["exit_status"] == 2 and result["reason_codes"] == ["rehearsal_task_stopped"]
    assert [row["status"] for row in result["tasks"]] == ["completed", "stopped", "completed", "completed", "completed"]
    failed = result["tasks"][1]
    assert failed["reason_codes"] == ["first_turn_attestation_refused"]
    assert failed["counts"]["admitted_or_observed_turns"] == 1
    assert failed["first_turn_attestation"]["verified"] is False
    capture = rehearsal.validate_capture(task_root(tmp_path / "isolated"), gate.TASK_IDS[1])
    assert capture["cleanup"]["cancel_attempts"] == capture["cleanup"]["dispose_attempts"] == 1
    assert capture["cleanup"]["host_terminated"] is True
    assert not any(row["direction"] == "client_work" and row["message"]["params"]["action"]["turnId"] == "turn2"
                   for row in capture["transcript"]["wire"])
    payload = load(tmp_path / "isolated/grader-input" / bridge.MANIFEST)
    assert payload["results"][1]["status"] == "error"
    assert payload["results"][1]["deliverable_files"] == [] and payload["results"][1]["content"] is None
    assert result["grader_contract"]["step8_layout_valid"] is True


def test_requested_fields_cannot_replace_missing_response_fields(tmp_path):
    fixture = fixtures.fixed_five()
    records = fixture["tasks"][0]["first_turn_records"]
    records[2]["value"].update(model="gpt-5.6-sol", reasoning={"effort": "max"}, modelContextWindow=1000000, webSearch=False)
    records[4]["value"]["response"] = {"id": "fixture", "status": "completed"}
    records[-1]["value"]["params"]["tokenUsage"] = {}
    result = run_with_budget(tmp_path / "request-only", fixture=fixture)
    observed = result["tasks"][0]["first_turn_attestation"]["observed"]
    assert observed == dict.fromkeys(first_turn.EXPECTED, "not_reported")
    assert result["tasks"][0]["status"] == "stopped"
    assert all(row["status"] == "completed" for row in result["tasks"][1:])


@pytest.mark.parametrize("cap", ["turns", "tools", "time"])
def test_exact_gate_caps_stop_before_any_further_fixture_work(tmp_path, cap):
    fixture = fixtures.fixed_five()
    task = fixture["tasks"][1]
    if cap == "turns":
        task["steps"] = [step for index in range(1, 66) for step in fixtures.turn_steps(f"turn{index}", tools=False)]
        reason, count, expected = "turn_limit_reached", "admitted_or_observed_turns", 64
    elif cap == "tools":
        task["steps"] = fixtures.turn_steps(tools=False)[:3] + [
            {"kind": "event", "action": {"type": "chat/toolCallReady", "turnId": "turn1",
                "toolCallId": f"tool{index}", "toolInput": "fixture only"}} for index in range(1, 34)]
        reason, count, expected = "tool_limit_reached", "observed_tool_calls", 32
    else:
        task["steps"] = fixtures.turn_steps(tools=False)[:3] + [{"kind": "advance", "seconds": 1200}]
        reason, count, expected = "time_limit_reached", "admitted_or_observed_turns", 1
    task["steps"] += [{"kind": "write", "path": "MUST-NOT-EXIST", "content": "work after cap"}]
    root = tmp_path / cap
    result = run_with_budget(root, fixture=fixture)
    assert_boundary(result)
    assert result["exit_status"] == 2 and result["fixture_pipeline_passed"] is False
    # The old turn cap interrupts turn64 before its usage can arrive. That
    # unknown cost now also closes aggregate admission; do not price it as zero.
    expected_tail = ["stopped"] * 3 if cap == "turns" else ["completed"] * 3
    assert [row["status"] for row in result["tasks"]] == ["completed", "stopped", *expected_tail]
    if cap == "turns":
        assert all(row["reason_codes"] == ["token_ledger_usage_missing"]
                   and row["counts"]["admitted_or_observed_turns"] == 0 for row in result["tasks"][2:])
    failed = result["tasks"][1]
    assert failed["reason_codes"] == [reason] and failed["counts"][count] == expected
    assert not (task_root(root) / "workspace/MUST-NOT-EXIST").exists()
    capture = rehearsal.validate_capture(task_root(root), gate.TASK_IDS[1])
    assert capture["cleanup"]["cancel_attempts"] == capture["cleanup"]["dispose_attempts"] == 1
    assert capture["observed_overshoot"] == {"turns": 0, "tool_calls": 0}
    assert not any(row["direction"] == "client_work" and row["after_stop"] for row in capture["transcript"]["wire"])
    if cap == "time":
        assert capture["elapsed_seconds"] == 1200
    if cap == "turns":
        assert sum(row["direction"] == "client_work" for row in capture["transcript"]["wire"]) == 64
        assert not any(row["message"].get("params", {}).get("action", {}).get("turnId") == "turn65"
                       for row in capture["transcript"]["wire"])
    if cap == "tools":
        assert all(row["toolCallId"] != "tool33" for row in capture["tool_calls"])


@pytest.mark.parametrize("key", ["transcript", "tool_calls", "commands", "generated_files", "cleanup", "counts", "limits",
                                  "status", "reason_codes", "first_turn_attestation", "workspace_collected"])
def test_missing_capture_field_refuses_grader_publication_but_runs_other_tasks(tmp_path, monkeypatch, key):
    original = client.SessionClient.capture
    def damaged(self, path, **kwargs):
        value = original(self, path, **kwargs)
        if gate.TASK_IDS[1] in path.parts:
            del value[key]
        return value
    monkeypatch.setattr(client.SessionClient, "capture", damaged)
    result = run_with_budget(tmp_path / "missing")
    assert result["exit_status"] == 2 and result["reason_codes"] == ["rehearsal_capture_incomplete"]
    assert result["tasks"][1]["status"] == "capture_refused"
    assert [row["status"] for index, row in enumerate(result["tasks"]) if index != 1] == ["completed"] * 4
    assert result["grader_contract"] is None and not (tmp_path / "missing/grader-input").exists()
    assert_boundary(result)


@pytest.mark.parametrize("name", [*rehearsal.CAPTURE_FILES, "files/answer.txt"])
def test_missing_persisted_component_is_rejected_before_grader_checks(tmp_path, monkeypatch, name):
    root = tmp_path / "missing-file"
    assert run_with_budget(root)["exit_status"] == 0
    (task_root(root) / "capture" / name).rename(tmp_path / "removed-component")
    def must_not_check(*args):
        pytest.fail("incomplete capture reached grader validators")
    monkeypatch.setattr(rehearsal, "_check_step8", must_not_check)
    with pytest.raises(rehearsal.Refused, match="rehearsal_capture_inventory_mismatch"):
        rehearsal.prepare_grader_input(root)


@pytest.mark.parametrize("name", ["client-capture.json", "transcript.jsonl", "tool-calls.jsonl", "commands.jsonl",
                                  "first-turn-wire.jsonl", "input-file-hashes.json", "output-file-hashes.json",
                                  "exit-status.json", "files/answer.txt"])
def test_component_byte_tamper_fails_closed(tmp_path, name):
    root = tmp_path / "tamper"
    assert run_with_budget(root)["exit_status"] == 0
    target = task_root(root) / "capture" / name
    target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(rehearsal.Refused, match="rehearsal_capture_hash_mismatch"):
        rehearsal.validate_capture(task_root(root), gate.TASK_IDS[1])


@pytest.mark.parametrize("key", list(rehearsal.FLAGS))
def test_synthetic_and_disabled_execution_markers_cannot_be_flipped(tmp_path, key):
    root = tmp_path / "markers"
    assert run_with_budget(root)["exit_status"] == 0
    path = task_root(root) / "capture/capture.json"
    value = load(path)
    value[key] = not value[key]
    path.write_text(json.dumps(value))
    with pytest.raises(rehearsal.Refused, match="rehearsal_capture_contract_refused"):
        rehearsal.validate_capture(task_root(root), gate.TASK_IDS[1])


@pytest.mark.parametrize("key", ["transcript", "generated_files", "first_turn_attestation", "limits", "cleanup"])
def test_rehashed_capture_still_needs_semantic_components(tmp_path, key):
    root = tmp_path / "rehashed"
    assert run_with_budget(root)["exit_status"] == 0
    folder = task_root(root) / "capture"
    capture = load(folder / "client-capture.json")
    if key == "transcript": capture[key]["wire"] = []
    if key == "generated_files": capture[key] = []
    if key == "first_turn_attestation": capture[key]["observed"]["served_model"] = "other"
    if key == "limits": capture[key]["turns"] = 65
    if key == "cleanup": capture[key]["host_terminated"] = False
    raw = rehearsal.encoded(capture) + b"\n"
    (folder / "client-capture.json").write_bytes(raw)
    record = load(folder / "capture.json")
    record["files"]["client-capture.json"] = rehearsal.identity(raw)
    (folder / "capture.json").write_text(json.dumps(record))
    with pytest.raises(rehearsal.Refused):
        rehearsal.validate_capture(task_root(root), gate.TASK_IDS[1])


@pytest.mark.parametrize("path", ["../escape", "/tmp/escape", "a/../escape", "a//b", "a\\b", "C:/escape", ".env", "auth.json"])
def test_fixture_path_escape_or_credential_file_refuses_before_work(tmp_path, path):
    fixture = fixtures.fixed_five()
    next(step for step in fixture["tasks"][0]["steps"] if step["kind"] == "write")["path"] = path
    result = run_with_budget(tmp_path / "unsafe", fixture=fixture)
    assert result["exit_status"] == 2 and result["reason_codes"] == ["fixture_path_refused"]
    assert result["tasks"] == [] and not (tmp_path / "unsafe").exists()


@pytest.mark.parametrize("damage", ["order", "fewer", "duplicate", "extra", "turns", "tools", "time", "live", "real-record"])
def test_fixture_cannot_change_cohort_limits_or_evidence_kind(tmp_path, damage):
    fixture = fixtures.fixed_five()
    if damage == "order": fixture["tasks"].reverse()
    if damage == "fewer": fixture["tasks"].pop()
    if damage == "duplicate": fixture["tasks"][1] = copy.deepcopy(fixture["tasks"][0])
    if damage == "extra": fixture["tasks"].append(copy.deepcopy(fixture["tasks"][0]))
    if damage == "turns": fixture["limits"]["turns"] = 65
    if damage == "tools": fixture["limits"]["tool_calls"] = 33
    if damage == "time": fixture["limits"]["seconds"] = 1201
    if damage == "live": fixture["execution_allowed"] = True
    if damage == "real-record": fixture["tasks"][0]["first_turn_records"][0]["synthetic"] = False
    result = run_with_budget(tmp_path / "invalid", fixture=fixture)
    assert result["exit_status"] == 2 and result["tasks"] == []
    assert not (tmp_path / "invalid").exists()


def test_existing_workspace_is_not_reused_or_overwritten(tmp_path):
    root = tmp_path / "once"
    assert run_with_budget(root)["exit_status"] == 0
    before = client.workspace_files(root)
    refused = run_with_budget(root)
    assert refused["reason_codes"] == ["rehearsal_output_reuse_or_checkout_refused"]
    assert client.workspace_files(root) == before


@pytest.mark.parametrize("target", ["workspace", "capture"])
def test_symlink_in_work_or_capture_is_not_followed(tmp_path, target):
    root = tmp_path / "links"
    assert run_with_budget(root)["exit_status"] == 0
    folder = task_root(root) / target
    (folder / "unexpected-link").symlink_to(tmp_path / "outside")
    with pytest.raises(client.Refused, match="capture_path_refused"):
        rehearsal.validate_capture(task_root(root), gate.TASK_IDS[1])


@pytest.mark.parametrize("event", ["socket.connect", "socket.getaddrinfo", "socket.sendto", "subprocess.Popen", "os.system",
                                   "os.exec", "os.posix_spawn", "os.fork"])
def test_attempted_external_effect_is_fatal_without_trying_it(tmp_path, monkeypatch, event):
    def attempt(*args, **kwargs):
        # Exercise the installed guard directly, never issue the forbidden call.
        bridge._audit(event, ())
        pytest.fail("effect guard did not refuse")
    monkeypatch.setattr(rehearsal, "run_task", attempt)
    result = run_with_budget(tmp_path / "effect")
    assert result["exit_status"] == 2 and result["reason_codes"] == ["offline_effect_refused"]
    assert result["tasks"] == [] and result["grader_contract"] is None


def test_offline_boundary_denies_provider_import_and_auth_file_reads(tmp_path):
    credential = tmp_path / "auth.json"
    credential.write_text("SYNTHETIC credential only")
    with bridge._no_effects(), pytest.raises(bridge.EffectsRefused):
        __import__("openai")
    with bridge._no_effects(), pytest.raises(bridge.EffectsRefused):
        credential.read_text()


def test_fixture_success_does_not_unlock_patch_activation_or_paid_client(tmp_path):
    assert run_with_budget(tmp_path / "locked")["exit_status"] == 0
    with pytest.raises(patched.Refused, match="patched_runtime_activation_pending_owner"):
        patched.require_activation()
    receipt = client.draft_receipt()
    assert receipt["launch_allowed"] is receipt["gate_ready"] is False
    assert receipt["reason_codes"] == ["ahp_paid_contract_unverified"]


def test_cli_has_only_offline_output_and_no_execution_switch(tmp_path, capsys):
    budget = tmp_path / "explicit-fixture-budget.json"
    budget.write_text(json.dumps(fixtures.budget_config()))
    assert rehearsal.main(["--output", str(tmp_path / "cli"), "--token-budget-config", str(budget)]) == 0
    value = json.loads(capsys.readouterr().out)
    assert value == {"synthetic": True, "execution_allowed": False, "fixture_pipeline_passed": True, "exit_status": 0, "reason_codes": []}
    with pytest.raises(SystemExit) as error:
        rehearsal.main(["--output", str(tmp_path / "live"), "--execute-paid"])
    assert error.value.code == 2 and not (tmp_path / "live").exists()


@pytest.mark.parametrize("field", ["admitted_or_observed_turns", "observed_turns", "observed_tool_calls",
                                    "model_requests", "premium_requests"])
def test_missing_capture_counter_cannot_be_substituted_with_zero(tmp_path, monkeypatch, field):
    original = client.SessionClient.capture
    def missing(self, path, **kwargs):
        value = original(self, path, **kwargs)
        if gate.TASK_IDS[1] in path.parts:
            del value["counts"][field]
        return value
    monkeypatch.setattr(client.SessionClient, "capture", missing)
    result = run_with_budget(tmp_path / "missing-count")
    assert result["tasks"][1]["reason_codes"] == ["rehearsal_capture_counts_refused"]
    assert result["exit_status"] == 2 and result["grader_contract"] is None


def test_step8_manifest_modified_during_check_cannot_be_published(tmp_path, monkeypatch):
    original = rehearsal._check_step8
    def changed(output, payload):
        checks = original(output, payload)
        path = output / bridge.MANIFEST
        value = load(path)
        value["execution_allowed"] = True
        path.write_text(json.dumps(value))
        return checks
    monkeypatch.setattr(rehearsal, "_check_step8", changed)
    result = run_with_budget(tmp_path / "changed-manifest")
    assert result["exit_status"] == 2 and result["reason_codes"] == ["step8_manifest_changed"]
    assert result["grader_contract"] is None
    assert not (tmp_path / "changed-manifest/grader-input" / bridge.REPORT).exists()
