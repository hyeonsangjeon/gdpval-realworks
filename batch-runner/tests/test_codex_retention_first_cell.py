"""Real retained inputs/staging, then explicitly simulated local control.

The one opt-in selector never interprets the original packet as authority and
never invokes the SDK, a model, a cloud service or a real child. Private input
locations and payloads stay out of the committed fixture and public receipt.
"""

from copy import deepcopy
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pytest

import codex_budget_pilot as owned
import codex_retention_diagnostic as registration
import codex_retention_first_cell as controller
import codex_retention_prepare_packet as preparation
from core.codex_task_deadline import (
    ATTEMPT_SECONDS, TOTAL_SECONDS, CodexTaskDeadline, CodexTaskDeadlineStore,
    TaskDeadlineExhausted,
)
from core.prepared_fingerprint import validate_prepared_fingerprint
from step8_grade import compute_grader_source_hash
from .test_codex_budget_pilot import Clock, offline  # noqa: F401; unchanged process/network/SDK guards


def test_first_retention_cell_staging_and_serial_control_are_closed(tmp_path, monkeypatch, capsys):
    locator = os.environ.get("GDPVAL_RETENTION_PREPARED_HANDOFF")
    if not locator:
        pytest.skip("explicit retained original-input handoff required; no substitute or fetch")
    handoff = preparation._json_object(preparation._read(Path(locator), "private_fixture_handoff"))
    assert handoff["prepared_role"] == preparation.PREPARED_PATH
    sources = preparation.PreparedInputs(Path(handoff["destination"]), Path(handoff["original_parquet"]),
                                         Path(handoff["reference_root"]), Path(handoff["step0_manifest"]))
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        raise AssertionError("offline first-cell selector crossed a live boundary")

    for name in ("core.codex_runner.CodexAgentRunner.__init__", "core.executor.TaskExecutor.__init__",
                 "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset",
                 "step8_grade.RubricLoader.__init__"):
        monkeypatch.setattr(name, forbidden)
    # This is one fresh, dedicated runtime worktree; never move/delete an old
    # staging output to make the positive fit. An unexpected collision fails.
    controller.WORKSPACE_DIR.mkdir(mode=0o700, exist_ok=True)
    preparation._path(controller.WORKSPACE_DIR)
    private = Path(tempfile.mkdtemp(prefix="retention-controller-test-", dir=controller.WORKSPACE_DIR))
    # A synthetic host must stay outside /tmp and the native writable roots.
    host_parent = Path(tempfile.mkdtemp(prefix=".retention-controller-host-", dir=Path(__file__).resolve().parents[3]))
    monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(host_parent / "unrelated-native-root"))
    monkeypatch.setenv("TMPDIR", str(host_parent / "agent-temp"))
    plan = registration.compile_plan()
    expected_plan = registration.seal(plan)
    preparer_identity = preparation.source_identity()
    controller_identity = controller.source_identity()
    packet_path = private / "task4-keep-r1"
    request = controller.Request(controller.FIRST_CELL_ID, sources, packet_path, controller.ROOT,
                                 preparer_identity["sha256"], controller_identity["sha256"], plan)
    original_roles = [sources.dataset_parquet, sources.step0_manifest,
                      sources.prepared_root / preparation.PREPARED_PATH,
                      sources.prepared_root / preparation.CONFIG_PATH]
    original_roles += [sources.reference_root / role for role in
                      registration.load_plan(registration.ROOT / registration.ORIGINAL_PROFILE)["shared"]["dataset"]["input_file_versions"]
                      if role.startswith("reference_files/")]
    original_identities = {path: preparation._identity(preparation._read(path, "original_fixture_role"))
                           for path in original_roles}

    def positive(phase, operation):
        try:
            return operation()
        except Exception as error:
            reason = str(error) if isinstance(error, (controller.RetentionControllerRefused,
                preparation.RetentionPreparationRefused, registration.RetentionRegistrationRefused)) else type(error).__name__
            frame = error.__traceback__
            while frame.tb_next is not None:
                frame = frame.tb_next
            where = Path(frame.tb_frame.f_code.co_filename).name + ":" + str(frame.tb_lineno) + ":" + frame.tb_frame.f_code.co_name
            pytest.fail(phase + ": " + reason + " at " + where, pytrace=False)

    # The real store/attempt owners are guarded during preparation, default
    # planning and refused execution. They are restored only for simulations.
    with monkeypatch.context() as guards:
        guards.setattr(CodexTaskDeadlineStore, "__init__", forbidden)
        guards.setattr(CodexTaskDeadline, "admit_attempt", forbidden)
        packet = positive("real_packet_preparation", lambda: preparation.prepare_packet(
            cell_id=request.cell_id, sources=sources, output=packet_path,
            expected_preparer_sha256=request.expected_preparer_sha256, plan=plan,
        ))
        description = positive("real_first_cell_plan", lambda: controller.plan_first_cell(request))
        assert description["cell_id"] == plan["order"][0] == controller.FIRST_CELL_ID
        assert description["ordinal"] == 0 and len(plan["cells"]) == 8
        assert description["launch_authorized"] is description["inference_slot_reserved"] is False
        assert description["deadline_started"] is description["runtime_inputs_staged"] is False
        assert description["commands"] == [] and description["controller_source"]["reviewed"] is False
        assert not controller.STAGING.exists() and not controller.STAGED.exists()
        denied_host = host_parent / "missing-authority"
        with pytest.raises(controller.RetentionControllerRefused, match="^" + controller.LIVE_GATE + "$"):
            controller.execute_first_cell(request, host_state=denied_host)
        for transport in (None, owned.LocalTransport()):
            with pytest.raises(controller.RetentionControllerRefused, match="^" + controller.LIVE_GATE + "$"):
                controller._run_post_authority_cell(request, host_state=denied_host, _test_transport=transport)
        assert not denied_host.exists()
        for cell_id in ("unregistered", plan["order"][1], plan["order"][4]):
            with pytest.raises(controller.RetentionControllerRefused, match="^only_registered_ordinal_zero_supported$"):
                controller.plan_first_cell(replace(request, cell_id=cell_id))
        with pytest.raises(controller.RetentionControllerRefused, match="^controller_source_mismatch$"):
            controller.stage_runtime(replace(request, expected_controller_sha256="0" * 64))
        with pytest.raises(preparation.RetentionPreparationRefused, match="^preparer_source_mismatch$"):
            controller.stage_runtime(replace(request, expected_preparer_sha256="0" * 64))
        with pytest.raises(controller.RetentionControllerRefused, match="^controller_must_run_from_explicit_runtime_checkout$"):
            controller.stage_runtime(replace(request, runtime_checkout=tmp_path))
        altered_plan = deepcopy(plan)
        altered_plan["order"][0], altered_plan["order"][1] = altered_plan["order"][1], altered_plan["order"][0]
        with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
            controller.plan_first_cell(replace(request, plan=altered_plan))
        altered_plan = deepcopy(plan)
        altered_plan["source_pins"]["runtime"]["batch-runner/step2_run_inference.py"] = "0" * 64
        with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
            controller.plan_first_cell(replace(request, plan=altered_plan))
        bad_manifest = private / "changed-schema4.json"
        bad_manifest.write_bytes(preparation._read(sources.step0_manifest, "original_schema4") + b"\n")
        with pytest.raises(preparation.RetentionPreparationRefused, match="^original_schema4_refused:"):
            controller.stage_runtime(replace(request, sources=replace(sources, step0_manifest=bad_manifest)))
        held_packet = preparation._read(packet_path / preparation.PACKET, "test_owned_packet")
        forged = deepcopy(packet)
        forged["launch_authorized"] = True
        (packet_path / preparation.PACKET).write_bytes(controller._encoded(forged))
        with pytest.raises(preparation.RetentionPreparationRefused, match="^packet_readback_mismatch$"):
            controller.execute_first_cell(request, host_state=denied_host)
        (packet_path / preparation.PACKET).write_bytes(held_packet)
        assert not denied_host.exists() and not controller.STAGING.exists()
        staged = positive("real_step2_runtime_staging", lambda: controller.stage_runtime(request))
        assert controller.verify_staged_runtime(request) == staged
        assert staged["runtime_inputs_staged"] is True
        assert staged["launch_authorized"] is staged["deadline_started"] is staged["inference_slot_reserved"] is False
        assert staged["commands"] == [] and controller.LIVE_GATE in staged["launch_blockers"]
        assert staged["input_roles_sha256"] == "40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38"
        prepared = controller.read_codex_prepared(controller.PREPARED)
        assert len(prepared["tasks"]) == 1 and prepared["tasks"][0]["task_id"] == registration.TASK4
        assert validate_prepared_fingerprint(prepared) == staged["prepared_fingerprint"]
        assert prepared["execution"]["codex"]["task_deadline"] == plan["cells"][0]["control"]
        assert prepared["execution"]["timeout"] == ATTEMPT_SECONDS == 1800
        assert prepared["execution"]["max_retries"] == 3 and prepared["execution"]["resume_max_rounds"] == 0
        assert "C_recovery_context" not in controller._encoded(prepared).decode()
        assert len(packet["input_verification"]["task_ids"]) == 5
        for record in prepared["tasks"][0]["reference_file_records"]:
            identity = preparation._identity(preparation._read(controller.DEFAULT_LOCAL_PATH / record["path"], "staged_reference"))
            assert identity == {key: record[key] for key in ("size", "sha256")}
        assert preparation._identity(preparation._read(controller.MANIFEST, "staged_manifest")) == original_identities[sources.step0_manifest]
        grader = preparation._json_object(preparation._read(packet_path / preparation.GRADER, "actual_grader"))
        actual_grader = compute_grader_source_hash(packet_path / preparation.GRADER, grader,
                                                   batch_root=controller.ROOT / "batch-runner")
        assert actual_grader == staged["grading"]["materialized_grader_source_sha256"]
        assert actual_grader != plan["grading"]["template_source_sha256"]
        with pytest.raises(controller.RetentionControllerRefused, match="^runtime_path_already_used_or_partial$"):
            controller.stage_runtime(request)
        with pytest.raises(controller.RetentionControllerRefused, match="^" + controller.LIVE_GATE + "$"):
            controller.execute_first_cell(request, host_state=denied_host)
        assert not denied_host.exists()
        held_prepared = preparation._read(controller.PREPARED, "test_owned_prepared")
        controller.PREPARED.write_bytes(held_prepared + b"\n")
        with pytest.raises(controller.RetentionControllerRefused, match="^staged_runtime_bytes_mismatch$"):
            controller.verify_staged_runtime(request)
        controller.PREPARED.write_bytes(held_prepared)
        argv = ["--cell-id", request.cell_id, "--packet", str(packet_path),
                "--runtime-checkout", str(controller.ROOT), "--prepared-root", str(sources.prepared_root),
                "--dataset-parquet", str(sources.dataset_parquet), "--reference-root", str(sources.reference_root),
                "--step0-manifest", str(sources.step0_manifest), "--expected-preparer-sha256", request.expected_preparer_sha256,
                "--expected-controller-sha256", request.expected_controller_sha256]
        assert controller.main(argv) == 0
        assert controller.main([*argv, "--execute", "--host-state", str(denied_host)]) == 2
        public = capsys.readouterr().out
        assert controller.LIVE_GATE in public and str(sources.prepared_root) not in public
        assert str(packet_path) not in public and not denied_host.exists()

    class SimulatedChildren(owned.LocalTransport):
        """Only process transport is synthetic; no validator/authority override."""

        def __init__(self, host, outcome="exit"):
            self.host, self.outcome = host, outcome
            self.clock, self.calls = Clock(), []
            self.active, self.peak = 0, 0

        def process(self, command, *, ownership, **options):
            assert command == [sys.executable, "step2_run_inference.py", "--condition", "condition_a",
                               "--codex-deadline-state", str(self.host / "deadline")]
            assert options["cwd"] == controller.ROOT / "batch-runner"
            assert options["timeout"] == TOTAL_SECONDS + 60 and options["check"] is False
            assert options["env"]["GDPVAL_RELAY_LINEAGE_ID"] == prepared["experiment_id"]
            assert options["env"]["GDPVAL_CODEX_RUN_ROOT"] == str(self.host / "native-workspaces")
            assert all(name not in options["env"] for name in ("PYTHONPATH", "PYTHONHOME", "HF_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"))
            assert "--initialize-codex-deadlines" not in command
            lock, = options["pass_fds"]
            os.fstat(lock)
            assert (self.host / "reservation.json").is_file()
            assert owned._load(self.host / "cell.json")["child_invocations"] == 1
            self.calls.append(tuple(command))
            self.active += 1
            self.peak = max(self.peak, self.active)
            # The real flock, not a simulated always-owned decision, blocks a
            # concurrent controller before a second child or clock operation.
            with pytest.raises(controller.RetentionControllerRefused, match="^local_serial_slot_busy$"):
                controller._run_post_authority_cell(request, host_state=self.host, _test_transport=self)
            path, binding = ownership
            assert path == self.host / "owned-child.json"
            assert binding == {"plan_sha256": registration.seal(plan), "cell_id": controller.FIRST_CELL_ID, "stage": "infer"}
            owner = {**owned._owner_state(registration.seal(plan)), **binding,
                     "phase": "launching", "tree_reaped": False, "owner_reaped": False}
            owned._save(path, owner)
            if self.outcome == "ambiguous-start":
                raise OSError("simulated start has no acknowledgment")
            store = controller._deadline(self.host, controller._context(request), staged, self)
            try:
                native = store.for_task(registration.TASK4)
                before = store._read()["cells"][registration.TASK4]
                assert before["started_unix"] == self.clock.now
                assert before["expires_unix"] == self.clock.now + TOTAL_SECONDS
                assert before["attempts"] == [] and native.retains_thread and not native.fresh_bundle
                assert store.control.max_attempts is None and store.control.condition == "retention_bundle_v1"
                assert native.bound_timeout(ATTEMPT_SECONDS) == ATTEMPT_SECONDS
                workspace = self.host / "native-workspaces" / "synthetic-attempt"
                workspace.mkdir(parents=True, mode=0o700)
                assert native.admit_attempt(workspace) == 0  # Synthetic clock/workspace, no SDK.
                self.clock.now += 17
                assert native.remaining_seconds() == TOTAL_SECONDS - 17
            finally:
                store.close()
            owner.update(pid=4242, phase="cleanup_unresolved" if self.outcome == "unconfirmed" else "reaped",
                         tree_reaped=self.outcome != "unconfirmed", owner_reaped=self.outcome != "unconfirmed",
                         exit_code=None if self.outcome == "unconfirmed" else 0,
                         reason="owned_child_cleanup_unconfirmed" if self.outcome == "unconfirmed" else None)
            owned._save(path, owner)
            self.active -= 1
            if self.outcome == "unconfirmed":
                raise owned.OwnedChildCleanupRefused("owned_child_cleanup_unconfirmed")
            if self.outcome == "ambiguous-completion":
                raise OSError("simulated completion has no acknowledgment")
            return subprocess.CompletedProcess(command, 0)

    # The production entrypoint is not opened by the injected transport. These
    # direct private-protocol tests are simulated control evidence only.
    successful = SimulatedChildren(host_parent / "simulated-confirmed")
    state = controller._run_post_authority_cell(
        request, host_state=successful.host, _test_transport=successful,
    )
    assert len(successful.calls) == successful.peak == 1 and successful.active == 0
    assert state["status"] == "failed" and state["reason"] == "missing_result"
    assert state["result"] is None and state["receipt"] is None and state["accounting"] == "missing"
    # A harmless/simulated zero exit is never promoted to an inference result.
    with pytest.raises(controller.RetentionControllerRefused, match="^first_cell_already_reserved_or_partial_no_replay$"):
        controller._run_post_authority_cell(request, host_state=successful.host, _test_transport=successful)
    successful.clock.now += 600
    restored = controller._deadline(successful.host, controller._context(request), staged, successful)
    try:
        native = restored.for_task(registration.TASK4)
        assert native.remaining_seconds() == TOTAL_SECONDS - 617
        snapshot = restored._read()["cells"][registration.TASK4]
        assert snapshot["started_unix"] == 1_000_000 and snapshot["expires_unix"] == 1_000_000 + TOTAL_SECONDS
        assert len(snapshot["attempts"]) == 1
        successful.clock.now = 1_000_000 + TOTAL_SECONDS + 1
        assert native.remaining_seconds() == 0
        with pytest.raises(TaskDeadlineExhausted):
            native.admit_attempt(successful.host / "native-workspaces" / "not-admitted")
        assert len(restored._read()["cells"][registration.TASK4]["attempts"]) == 1
    finally:
        restored.close()
    for outcome in ("ambiguous-start", "ambiguous-completion", "unconfirmed"):
        simulation = SimulatedChildren(host_parent / ("simulated-" + outcome), outcome)
        expected = owned.OwnedChildCleanupRefused if outcome == "unconfirmed" else OSError
        with pytest.raises(expected):
            controller._run_post_authority_cell(request, host_state=simulation.host, _test_transport=simulation)
        before = preparation._identity(preparation._read(simulation.host / "deadline/deadlines.json", "simulated_deadline"))
        simulation.clock.now += 500
        replay_error = controller.RetentionControllerRefused if outcome == "ambiguous-completion" else owned.OwnedChildCleanupRefused
        replay_reason = ("^first_cell_already_reserved_or_partial_no_replay$" if outcome == "ambiguous-completion"
                         else "^owned_child_cleanup_unconfirmed$")
        with pytest.raises(replay_error, match=replay_reason):
            controller._run_post_authority_cell(request, host_state=simulation.host, _test_transport=simulation)
        assert preparation._identity(preparation._read(simulation.host / "deadline/deadlines.json", "simulated_deadline")) == before
        assert len(simulation.calls) == 1 and (simulation.host / "reservation.json").is_file()
    with pytest.raises(owned.PilotDispatchRefused, match="^output_overlaps_source_or_agent_writable_root$"):
        controller._run_post_authority_cell(request, host_state=tmp_path / "unsafe-host", _test_transport=successful)
    assert not (tmp_path / "unsafe-host").exists()
    assert registration.seal(plan) == expected_plan
    for path, expected in original_identities.items():
        assert preparation._identity(preparation._read(path, "original_after_test")) == expected
    assert forbidden_calls == []
    assert not (controller.ROOT / owned.RESULT).exists() and not (controller.ROOT / owned.LEDGER).exists()
    receipt = {
        "evidence": "real_original_packet_and_runtime_staging_plus_simulated_local_control",
        "cell_id": controller.FIRST_CELL_ID, "plan_sha256": registration.seal(plan),
        "input_roles_sha256": staged["input_roles_sha256"], "controller_source": controller_identity,
        "packet_sha256": registration.seal(packet), "stage_sha256": registration.seal(staged),
        "prepared_fingerprint": staged["prepared_fingerprint"], "materialized_grader_source_sha256": actual_grader,
        "simulated_control_cases": ["single_slot", "one_use", "ambiguous_start", "ambiguous_completion",
                                    "unconfirmed_cleanup", "durable_restart_expiry"],
        "live_inference": False, "grading_done": False, "launch_authorized": False,
    }
    receipt_path = os.environ.get("GDPVAL_RETENTION_CONTROLLER_TEST_RECEIPT")
    if receipt_path:
        with Path(receipt_path).open("xb") as stream:
            stream.write(controller._encoded({**receipt, "private_artifacts": {
                "original_handoff": locator, "packet": str(packet_path),
                "runtime_checkout": str(controller.ROOT), "simulated_host_parent": str(host_parent),
            }}))
    print(controller.registration._canonical_json(receipt))
