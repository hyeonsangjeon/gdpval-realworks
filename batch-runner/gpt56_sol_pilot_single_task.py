"""Owned single-task Step 2 fragments for the registered Sol five-task pilot.

This is a new witness, not an adopted/partially completed PilotWireReceiptSession.
The parent experiment and five-task wallet stay fixed. The derived execution ID
names this fragment only; it never claims that all five live tasks completed.
The global paid launcher remains blocked while result/grading assembly is WIP.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import threading
import uuid

from core import runner_environment as host
from core.codex_runner import CodexAgentRunner, CodexWorkspace
from core.codex_runtime_config import CodexProviderLike, CodexProviderSettings
from core.inference_manifest import bind_deliverable_file_records
from core.reference_integrity import resolve_verified_reference_paths, stage_verified_references
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_run_config_bundle import _root
from gpt54_v2_grading_input import _read_bytes
import gpt56_native_response_capture as responses
import gpt56_pilot_usd_budget as usd
import gpt56_pilot_wire_receipt as wire
import gpt56_pilot_deployment_binding as deployment
import gpt56_sol_pilot_inputs as inputs_module
import gpt56_sol_pilot_launch as launch
import gpt56_sol_pilot_wallet as wallet
import step2_run_inference as step2

SCHEMA = "sol-pilot-single-task-witness-v1"
RESULT = "sol-single-task-result.json"
RECEIPT = "sol-single-task-witness.json"
CLAIM = "sol-single-task-claim.json"
BOUNDARY = "one_owned_step2_task_not_a_complete_five_task_live_witness"


class SingleTaskRefused(ValueError):
    def __init__(self, code="sol_pilot_single_task_refused"):
        self.code = code
        super().__init__(code)


def _require(value, code="sol_pilot_single_task_refused"):
    if not value:
        raise SingleTaskRefused(code)


def _digest(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def _restored_request_budget(ledger):
    """Restore conservative request counts from the admitted real SQL ledger.

    Unknown/reserved requests count too: a missing reply cannot refund a model
    request. New budget objects never reset previously booked pilot requests.
    The original reservation and all HTTP/token/USD guards remain unchanged.
    """
    budget = wire._NativeRequestBudget(list(launch.TASKS), usd_ledger=ledger)
    with ledger._transaction():
        rows = ledger.connection.execute(
            "SELECT a.task, COUNT(*) AS n FROM reservations r JOIN accounts a ON a.id=r.account "
            "WHERE a.origin='inference' GROUP BY a.task").fetchall()
    counts = {task: 0 for task in launch.TASKS}
    for row in rows:
        _require(row["task"] in counts and type(row["n"]) is int and row["n"] >= 0)
        counts[row["task"]] = row["n"]
    with budget.lock:
        budget.counts = counts
        budget.total = sum(counts.values())
    return budget


class _RuntimeHandle:
    def __init__(self, owner):
        self.owner = owner
        self.runtime = owner.runtime

    def close(self):
        self.owner.close_runtime()

    def __getattr__(self, name):
        return getattr(self.runtime, name)


class _OwnedThread:
    def __init__(self, thread, owner, expected_text):
        self.thread, self.owner, self.expected_text = thread, owner, expected_text

    def turn(self, text, *args, **kwargs):
        with self.owner.lock:
            self.owner.require_current()
            _require(self.owner.phase == "running" and self.owner.turns == 0 and
                     text == self.expected_text and not args and not kwargs,
                     "single_task_turn_or_input_refused")
            self.owner.turns = 1  # Claim before the call; an exception is not a retry.
        return self.thread.turn(text)

    def __getattr__(self, name):
        return getattr(self.thread, name)


class _SingleTaskRunner(CodexAgentRunner):
    """Reuse the real generic runner with a formally owned single-task opener.

    No legacy five-task instance is fabricated and no global class/function is
    replaced. Only this runner's SDK opener binds the existing HTTP observer to
    the restored shared wallet. Workspace, SDK, thread, turn, output collection
    and Step 2 serialization still use the existing native implementation.
    """

    def __init__(self, owner, provider):
        self.owner = owner
        super().__init__(provider, timeout=1800, run_id=owner.execution_id,
                         condition_name="codex_foundry")

    def build_task_text(self, task_prompt, workspace, *, occupation="professional", perception_text=None):
        owner = self.owner
        owner.require_current()
        _require(task_prompt == owner.task["instruction"] and
                 occupation == owner.task["occupation"] and perception_text is None,
                 "single_task_render_input_mismatch")
        text = super().build_task_text(task_prompt, workspace,
            occupation=occupation, perception_text=perception_text)
        _require(owner.task_text is None or owner.task_text == text, "single_task_render_changed")
        owner.task_text = text
        return text

    def open_runtime(self, workspace, *, pilot_wire_observer=None, native_response_observer=None):
        from openai_codex import Codex
        from openai_codex.client import CodexConfig

        owner = self.owner
        owner.require_current()
        _require(owner.phase == "running" and owner.runtime_starts == 0 and
                 pilot_wire_observer is None and native_response_observer is None and
                 type(workspace) is CodexWorkspace, "single_task_runtime_owner_refused")
        owner.runtime_starts += 1
        owner.model_workspace = workspace.workspace
        owner.require_provider(self.provider)
        observer = wire._TransportObservation(owner.inputs.capture["requested"])
        observer.approved_base_url = self.provider.base_url
        observer.response_artifacts = owner.response_artifacts
        observer.native_budget, observer.native_budget_task = owner.budget, owner.task_id
        owner.observer = observer
        environment = self._build_environment(workspace)
        overrides = observer.configure_provider_observer(self.provider,
            self.provider.config_overrides(), timeout=self.timeout)
        config = CodexConfig(codex_bin=self.codex_bin, config_overrides=tuple(overrides),
                             env=environment, cwd=str(workspace.workspace))
        codex = Codex.__new__(Codex)
        try:
            with observer.supervise_provider_startup(codex):
                Codex.__init__(codex, config)
            with owner.runtime_lock, observer.provider_capture.lock:
                _require(not observer.provider_capture.closed and observer.provider_capture.requests == 0,
                         "single_task_startup_expired")
                owner.runtime = codex
                observer.provider_capture.stop_runtime = owner.close_runtime
            return _RuntimeHandle(owner)
        except BaseException:
            try:
                if getattr(codex, "_client", None) is not None:
                    codex.close()
            finally:
                observer.close_startup_process()
                observer.close_provider_observer()
            raise

    def start_thread(self, codex, workspace, *, developer_instructions=None):
        owner = self.owner
        with owner.lock:
            owner.require_current()
            _require(owner.phase == "running" and owner.threads == 0 and
                     developer_instructions == owner.developer_instructions.strip(),
                     "single_task_thread_or_developer_input_refused")
            owner.threads = 1
        thread = super().start_thread(codex, workspace, developer_instructions=developer_instructions)
        return _OwnedThread(thread, owner, owner.task_text)


class SingleTaskWitness:
    """One live owner, one registered task, one restored wallet; no disk adoption."""

    def __init__(self, inputs, ledger, *, stage_index, provider, predecessor, predecessor_sha256,
                 fixture_transport=False,
                 account_resource_id_file=None, deployment_resource_id_file=None):
        _require(type(inputs) is inputs_module.VerifiedInputs)
        inputs.require_current()
        _require(type(stage_index) is int and 0 < stage_index < 5,
                 "single_task_requires_a_previous_solve_checkpoint")
        _require(type(ledger) is usd.PilotUsdLedger and not ledger.closed)
        self.inputs, self.ledger, self.stage_index = inputs, ledger, stage_index
        self.task = inputs.task(stage_index)
        self.task_id = self.task["task_id"]
        self.root = _root(ledger.workspace)
        self.runner_observation = host.require_execution()
        self.lock, self.runtime_lock = threading.RLock(), threading.RLock()
        self.phase = "claimed"
        self.runtime = self.observer = self.model_workspace = None
        self.runtime_starts = self.threads = self.turns = 0
        self.task_text = None
        self.fixture_transport = fixture_transport
        _require(type(fixture_transport) is bool)
        self.provider = provider
        self.route_files = (account_resource_id_file, deployment_resource_id_file)
        self.route_receipt = None
        self.provider_identity = self._provider_identity(provider)
        self.require_provider(provider)
        plan = inputs_module._plan()
        self.developer_instructions = plan["developer_instructions"]
        self.execution_id = "gpt56-sol-task-" + hashlib.sha256(launch.canonical({
            "lineage": inputs.lineage, "capture_sha256": inputs.capture_sha256,
            "task_id": self.task_id, "stage_index": stage_index})).hexdigest()[:32]
        self.binding = ledger.binding()
        previous, _ = wallet.read_checkpoint(predecessor, expected_sha256=predecessor_sha256,
            lineage=inputs.lineage, capture_sha256=inputs.capture_sha256, next_stage=stage_index)
        _require(previous["outcome"] == "success" and previous["snapshot"]["stop_reason"] is None and
                 previous["binding"] == self.binding and previous["snapshot"] == ledger.snapshot(),
                 "single_task_restored_predecessor_required")
        self.predecessor_sha256 = predecessor_sha256
        _require(self.binding["run_id"] == usd.RUN_ID and
                 self.binding["task_ids"] == list(launch.TASKS) and
                 self.binding["capture_sha256"] == inputs.capture_sha256)
        self.budget = _restored_request_budget(ledger)
        _require(self.budget.counts[self.task_id] == 0, "already_attempted_task_refused")
        self.budget.require_available(self.task_id)
        self.claim = launch.canonical({"schema": SCHEMA, "execution_id": self.execution_id,
            "experiment_id": usd.RUN_ID, "task_id": self.task_id, "stage_index": stage_index,
            "capture_sha256": inputs.capture_sha256, "wallet_id": self.binding["ledger_id"],
            "predecessor_sha256": predecessor_sha256,
            "owner_nonce": uuid.uuid4().hex, "full_five_task_witness": False})
        _write_no_clobber(self.root / CLAIM, self.claim)
        os.mkdir(self.root / "output", 0o700)
        self.response_artifacts = responses.NativeResponseArtifacts(self.root, "single-task-native-responses")
        self.runner = _SingleTaskRunner(self, provider)

    @staticmethod
    def _provider_identity(provider):
        _require(isinstance(provider, CodexProviderLike), "single_task_provider_required")
        return (provider.model, provider.provider_id, provider.base_url,
                getattr(provider, "reasoning_effort", None), getattr(provider, "model_context_window", None),
                getattr(provider, "request_max_retries", None), getattr(provider, "stream_max_retries", None))

    def require_provider(self, provider):
        _require(self._provider_identity(provider) == self.provider_identity and
                 provider.model == "gpt-5.6-sol" and provider.provider_id == "gdpval-foundry" and
                 provider.reasoning_effort == "max" and provider.model_context_window == 1_000_000 and
                 type(provider.request_max_retries) is int and provider.request_max_retries == 0 and
                 type(provider.stream_max_retries) is int and provider.stream_max_retries == 0,
                 "single_task_provider_settings_mismatch")
        if self.fixture_transport:
            from core.codex_runtime_config import LOOPBACK_PLACEHOLDER_KEY

            _require(type(provider) is not CodexProviderSettings and
                     provider.base_url == "https://fixture-foundry.services.ai.azure.com/openai/v1" and
                     not callable(getattr(provider, "auth_command", None)) and
                     provider.extra_environment() == {"GDPVAL_CODEX_LOOPBACK_KEY": LOOPBACK_PLACEHOLDER_KEY} and
                     self.route_files == (None, None), "fixture_provider_boundary_refused")
            receipt = {"fixture_transport": True, "configured_foundry_route_matched": False}
        else:
            _require(type(provider) is CodexProviderSettings and all(self.route_files),
                     "production_foundry_route_binding_required")
            from core.codex_runtime_config import DEFAULT_AUTH_MODULE, DIRECT_TOKEN_SCOPE

            _require(not provider.query_params and provider.auth_module == DEFAULT_AUTH_MODULE and
                     provider.auth_scope == DIRECT_TOKEN_SCOPE, "single_task_auth_route_changed")
            receipt = deployment.bind_approved_connection(deployment.approved_connection_reference(), provider,
                *(deployment._resource_bytes(Path(path)) for path in self.route_files))
        _require(self.route_receipt is None or self.route_receipt == receipt, "single_task_route_changed")
        self.route_receipt = receipt

    def require_current(self):
        _require(self.phase in ("claimed", "running"), "single_task_witness_not_live")
        self.inputs.require_current()
        _require(_read_bytes(self.root / CLAIM) == self.claim, "single_task_claim_changed")
        _require(self.ledger.binding() == self.binding, "single_task_wallet_changed")
        host.require_execution(self.runner_observation)
        self.require_provider(self.provider)

    def close_runtime(self):
        with self.runtime_lock:
            if self.runtime is not None:
                runtime, self.runtime = self.runtime, None
                runtime.close()

    def execute(self, **kwargs):
        """The actual executor boundary called by unchanged Step 2."""
        with self.lock:
            self.require_current()
            _require(self.phase == "running" and self.runtime_starts == 0 and
                     kwargs["run_id"] == self.execution_id and kwargs["task_id"] == self.task_id and
                     kwargs["condition_name"] == "codex_foundry" and kwargs["model"] == "gpt-5.6-sol" and
                     kwargs["task_prompt"] == self.task["instruction"] and kwargs.get("perception_text") is None,
                     "single_task_step2_scope_mismatch")
            _require(kwargs["occupation"] == self.task["occupation"] and
                     kwargs["experiment_prompt"] == {"system": self.developer_instructions,
                         "prefix": None, "body": None, "suffix": None}, "single_task_prompt_settings_mismatch")
        try:
            result = self.runner.run(**{key: value for key, value in kwargs.items() if key != "verbose"})
        finally:
            self.close_runtime()
            if self.observer is not None:
                self.observer.close_provider_observer()
        evidence = self.response_artifacts.report()
        reason = None if evidence["state"] == "observed" else evidence["reason"]
        if self.observer is not None and self.observer.provider_capture.stop_reason is not None:
            reason = self.observer.provider_capture.stop_reason
        if reason:
            return self.runner._failure(reason, category=reason)
        return result

    def run_step2(self):
        with self.lock:
            self.require_current()
            _require(self.phase == "claimed", "single_task_replay_refused")
            self.phase = "running"
        try:
            references = resolve_verified_reference_paths(self.inputs.root,
                self.task["reference_files"], self.task["reference_file_records"])
            with stage_verified_references(references) as staged:
                task = {**self.task, "reference_files": list(staged)}
                condition = {"prompt": {"system": self.developer_instructions}, "preprocessors": []}
                row = step2._execute_single_task(task, condition, self, "codex_foundry", None,
                    "gpt-5.6-sol", run_id=self.execution_id, condition_name="codex_foundry",
                    experiment_id=usd.RUN_ID, strict_inputs=True, upload_root=self.root / "output")
            _require(type(row) is dict and row["task_id"] == self.task_id)
            rows = bind_deliverable_file_records([row], self.root / "output")
            row = step2._public_persisted_results(rows)[0]
            result_data = launch.canonical({"schema": SCHEMA, "experiment_id": usd.RUN_ID,
                "execution_id": self.execution_id, "task_id": self.task_id,
                "full_five_task_witness": False, "fixture_transport": self.fixture_transport,
                "capture_sha256": self.inputs.capture_sha256, "result": row})
            _write_no_clobber(self.root / RESULT, result_data)
            self.phase = "completed" if row["status"] == "success" else "failed"
            return row, _digest(result_data)
        except BaseException:
            self.phase = "failed"
            raise
        finally:
            self.close_runtime()
            if self.observer is not None:
                self.observer.close_provider_observer()


def run_single_task_shard(inputs, *, stage_index, predecessor, predecessor_sha256,
                          workspace, checkpoint, provider, execute_paid=False, fixture_transport=False,
                          account_resource_id_file=None, deployment_resource_id_file=None):
    """Real component path; the global CLI still refuses the unfinished pilot.

    A fixture transport is explicitly marked and can never be a real five-task
    grading input. It replaces provider I/O only, not source/input/Step2/SQL code.
    """
    _require(execute_paid is True, "explicit_execute_paid_required")
    _require(type(inputs) is inputs_module.VerifiedInputs)
    inputs.require_current()
    admission = launch.admit(execute_paid=True, expected_source_sha=inputs.lineage["source_sha"])
    _require(admission["lineage"] == inputs.lineage, "single_task_lineage_mismatch")
    ledger = wallet.restore_checkpoint(workspace, predecessor, expected_sha256=predecessor_sha256,
        lineage=inputs.lineage, capture_sha256=inputs.capture_sha256, stage_index=stage_index)
    owner = None
    try:
        owner = SingleTaskWitness(inputs, ledger, stage_index=stage_index,
            provider=provider, fixture_transport=fixture_transport,
            predecessor=predecessor, predecessor_sha256=predecessor_sha256,
            account_resource_id_file=account_resource_id_file,
            deployment_resource_id_file=deployment_resource_id_file)
        row, result_binding = owner.run_step2()
        outcome = "success" if row["status"] == "success" else "failed"
        _, digest = wallet.publish_checkpoint(ledger, checkpoint, lineage=inputs.lineage,
            capture_sha256=inputs.capture_sha256, stage_index=stage_index, outcome=outcome,
            runner_receipt=host.receipt("inference", owner.runner_observation),
            predecessor=predecessor, predecessor_sha256=predecessor_sha256)
        receipt = {"schema": SCHEMA, "evidence_boundary": BOUNDARY, "experiment_id": usd.RUN_ID,
            "lineage": inputs.lineage, "task_id": owner.task_id, "stage_index": stage_index,
            "execution_id": owner.execution_id, "status": outcome, "result": {"path": RESULT, **result_binding},
            "capture_sha256": inputs.capture_sha256, "input_ready_sha256": inputs.ready_sha256,
            "predecessor_sha256": predecessor_sha256,
            "wallet_checkpoint_sha256": digest, "requested": inputs.capture["requested"],
            "provider_observation": owner.observer.provider_capture.summary() if owner.observer else None,
            "response_evidence": owner.response_artifacts.report(), "threads": owner.threads, "turns": owner.turns,
            "route_binding": owner.route_receipt,
            "rendered_input_sha256": hashlib.sha256(owner.task_text.encode()).hexdigest() if owner.task_text else None,
            "fixture_transport": fixture_transport, "full_five_task_witness": False,
            "paid_launch_bridge_still_blocked": bool(launch.UNIMPLEMENTED_BRIDGE)}
        _write_no_clobber(owner.root / RECEIPT, launch.canonical(receipt))
        return receipt
    finally:
        if owner is not None:
            owner.close_runtime()
            if owner.observer is not None:
                owner.observer.close_provider_observer()
        ledger.close()
