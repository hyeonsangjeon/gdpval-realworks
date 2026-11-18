"""One real Step 2/SDK/SQLite path; only provider I/O and host labels are fake.

The public registered input bytes, source admission, request observer, single
task owner and financial handoff are NOT mocked. No sandbox tool command or
real endpoint is used. These fixtures are not live Foundry/runner evidence.
"""

from dataclasses import dataclass, replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from core import runner_environment as host
from core.codex_runner import CodexAgentRunner
from core.codex_runtime_config import CodexProviderLike, LOOPBACK_PLACEHOLDER_KEY
from gpt56_pilot_native_result_host import native_result_host_for, PilotNativeResultHostRefused
import gpt56_pilot_usd_budget as usd
import gpt56_pilot_wire_receipt as wire
import gpt56_sol_pilot_inputs as inputs
import gpt56_sol_pilot_launch as launch
import gpt56_sol_pilot_single_task as single
import gpt56_sol_pilot_wallet as wallet
import step2_run_inference as step2
from .test_gpt56_pilot_provider_observation import _upstream

FIXTURES = Path(__file__).parent / "fixtures/sol_pilot_inputs"
USAGE = {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 0},
         "output_tokens": 10, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 110}


@dataclass(frozen=True)
class FixtureProvider(CodexProviderLike):
    """No credential discovery; HTTPS forwarding is replaced by local HTTP."""

    model: str = "gpt-5.6-sol"
    provider_id: str = "gdpval-foundry"
    reasoning_effort: str = "max"
    model_context_window: int = 1_000_000
    base_url: str = "https://fixture-foundry.services.ai.azure.com/openai/v1"
    request_max_retries: int = 0
    stream_max_retries: int = 0

    def config_overrides(self):
        prefix = f"model_providers.{self.provider_id}"
        return (f'{prefix}.name="{self.provider_id}"', f'{prefix}.base_url="{self.base_url}"',
                f'{prefix}.wire_api="responses"', f'{prefix}.env_key="GDPVAL_CODEX_LOOPBACK_KEY"',
                f"{prefix}.request_max_retries={self.request_max_retries}",
                f"{prefix}.stream_max_retries={self.stream_max_retries}",
                f'model_reasoning_effort="{self.reasoning_effort}"',
                f"model_context_window={self.model_context_window}")

    def extra_environment(self):
        return {"GDPVAL_CODEX_LOOPBACK_KEY": LOOPBACK_PLACEHOLDER_KEY}


@pytest.fixture(autouse=True)
def local_transport_only(monkeypatch, native_hosted_runner):
    """The Python forwarder can reach only loopback; SDK gets its local URL."""
    for method in ("connect", "connect_ex"):
        original = getattr(socket.socket, method)

        def checked(sock, address, original=original):
            assert sock.family == socket.AF_INET and address[0] == "127.0.0.1", "external transport forbidden"
            return original(sock, address)

        monkeypatch.setattr(socket.socket, method, checked)


@pytest.fixture
def lineage(monkeypatch):
    # Actual Git/source admission must execute on the clean candidate commit.
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=launch.ROOT,
                         check=True, capture_output=True, text=True).stdout.strip()
    for name, value in {"GITHUB_REPOSITORY": launch.REPOSITORY, "GITHUB_SHA": sha,
                        "GITHUB_WORKFLOW_SHA": sha, "GITHUB_EVENT_NAME": "workflow_dispatch",
                        "GITHUB_REF": "refs/heads/main"}.items():
        monkeypatch.setenv(name, value)
    return {"repository": launch.REPOSITORY, "source_sha": sha,
            "run_id": "123456789", "run_attempt": "1"}


@pytest.fixture
def bundle(tmp_path, lineage):
    return inputs.prepare_input_bundle(FIXTURES, tmp_path / "verified-inputs", lineage=lineage)


def predecessor(root, bundle, amount="1", *, unknown=False, stages=1):
    workspace = root / "previous-worker"
    workspace.mkdir(mode=0o700)
    ledger = usd.PilotUsdLedger(workspace, capture_sha256=bundle.capture_sha256,
                               task_ids=list(launch.TASKS), create=True)
    path = digest = None
    for index in range(stages):
        if index:
            ledger = wallet.restore_checkpoint(root / f"previous-worker-{index}", path,
                expected_sha256=digest, lineage=bundle.lineage,
                capture_sha256=bundle.capture_sha256, stage_index=index)
        account = ledger.begin("inference", launch.TASKS[index])
        reservation = ledger.reserve(account, Decimal(amount))
        if unknown:
            ledger.abandon(account)
        else:
            assert ledger.settle(reservation, Decimal(amount), Decimal(0)) is None
        target = root / f"previous-checkpoint-{index}"
        document, digest = wallet.publish_checkpoint(ledger, target, lineage=bundle.lineage,
            capture_sha256=bundle.capture_sha256, stage_index=index, outcome="success",
            runner_receipt=host.receipt("inference"), predecessor=path, predecessor_sha256=digest)
        path = target
    return path, digest, document


def scripted_response(*, model="gpt-5.6-sol", effort="max", context=1_000_000, usage=USAGE):
    message = {"type": "message", "id": "fixture-message", "role": "assistant", "status": "completed",
               "content": [{"type": "output_text", "text": "Fixture deliverable saved."}]}
    response = {"object": "response", "id": "fixture-response", "status": "completed", "output": [message]}
    if model is not None:
        response["model"] = model
    if effort is not None:
        response["reasoning"] = {"effort": effort}
    if context is not None:
        response["context_window"] = context
    if usage is not None:
        response["usage"] = usage
    events = [{"type": "response.created", "response": {"object": "response", "id": "fixture-response", "status": "in_progress"}},
              {"type": "response.output_item.done", "output_index": 0, "item": message},
              {"type": "response.completed", "response": response}]
    return {"type": "text/event-stream", "body": b"".join(
        f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode() for event in events)}


def model_creates_file():
    # The fake model's sole output effect. No fake Step 2/runner/file collector,
    # no native shell tool on NAS, and no manufactured completed task row.
    workspaces = list(Path(os.environ["GDPVAL_CODEX_RUN_ROOT"]).glob("*/workspace"))
    assert len(workspaces) == 1
    (workspaces[0] / "fixture-deliverable.txt").write_text("Synthetic provider output, not a benchmark answer.\n")


def run_shard(tmp_path, bundle, previous, digest, *, stage_index=1, **kwargs):
    return single.run_single_task_shard(bundle, stage_index=stage_index,
        predecessor=previous, predecessor_sha256=digest, workspace=tmp_path / f"worker-{stage_index}",
        checkpoint=tmp_path / f"checkpoint-{stage_index}", provider=FixtureProvider(),
        execute_paid=True, fixture_transport=True, **kwargs)


def test_registered_public_inputs_and_requested_capture_are_exact(bundle):
    assert tuple(row["task_id"] for row in bundle.capture["tasks"]) == launch.TASKS
    assert bundle.capture["dataset"]["parquet"]["sha256"] == "f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202"
    assert bundle.capture["requested"]["model"] == "gpt-5.6-sol"
    assert bundle.capture["requested"]["reasoning_effort"] == "max"
    assert bundle.capture["requested"]["context_tokens"] == 1_000_000
    assert set(bundle.capture["observed"].values()) == {"not_observed"}
    assert not bundle.capture["full_five_task_witness"] and bundle.capture["model_calls"] == 0
    assert bundle.capture["response_policy"]["context_not_reported"] == "record_and_continue"
    assert len(json.loads(bundle.ready_bytes)["files"]) == 3
    assert bundle.task(2)["reference_file_records"]
    bundle.require_current()


@pytest.mark.parametrize("change", ["parquet", "reference", "capture", "ready", "extra_file",
                                    "extra_directory", "directory_symlink", "file_symlink", "missing"])
def test_input_bundle_changes_fail_closed(bundle, tmp_path, change):
    if change in ("parquet", "reference", "missing"):
        name = inputs.PARQUET_PATH if change == "parquet" else bundle.task(2)["reference_files"][0]
        path = bundle.root / name
        if change == "missing":
            path.unlink()
        else:
            path.write_bytes(path.read_bytes() + b"changed")
    elif change in ("capture", "ready"):
        (bundle.root / (inputs.CAPTURE if change == "capture" else inputs.READY)).write_bytes(b"{}")
    elif change == "extra_file":
        (bundle.root / "extra").write_text("unexpected")
    elif change == "extra_directory":
        (bundle.root / "unexpected-empty").mkdir()
    elif change == "directory_symlink":
        (bundle.root / "extra-link").symlink_to(tmp_path, target_is_directory=True)
    else:
        path = bundle.root / inputs.CAPTURE
        path.unlink()
        path.symlink_to(FIXTURES / "README.md")
    with pytest.raises((inputs.InputRefused, ValueError)):
        bundle.require_current()


def test_independent_digest_and_live_input_witness_cannot_be_adopted(bundle):
    with pytest.raises(inputs.InputRefused):
        inputs.verify_input_bundle(bundle.root, lineage=bundle.lineage, expected_sha256="0" * 64)
    forged = inputs.VerifiedInputs(bundle.root, bundle.ready_bytes, bundle.capture_bytes, bundle.lineage_json)
    with pytest.raises(inputs.InputRefused, match="unissued_input_witness"):
        forged.require_current()


@pytest.mark.parametrize("index", [-1, 5, True, "1"])
def test_only_fixed_task_indices_are_accepted(bundle, index):
    with pytest.raises(inputs.InputRefused, match="task_index_outside_pilot"):
        bundle.task(index)


@pytest.mark.parametrize("context", [1_000_000, None])
def test_actual_single_task_step2_and_restored_wallet_end_to_end(monkeypatch, tmp_path, bundle, context):
    previous, digest, before = predecessor(tmp_path, bundle)
    with _upstream(monkeypatch, [scripted_response(context=context)], on_request=model_creates_file) as (received, _):
        receipt = run_shard(tmp_path, bundle, previous, digest)
    assert receipt["status"] == "success", receipt
    assert len(received) == 1
    request = json.loads(received[0][1])
    assert request["model"] == "gpt-5.6-sol" and request["reasoning"]["effort"] == "max"
    assert request["max_output_tokens"] <= 10_000
    text_parts = [part["text"] for item in request["input"] if item.get("role") == "user"
                  for part in item.get("content", []) if type(part) is dict and "text" in part]
    # The unchanged native renderer strips only surrounding prompt whitespace.
    # Bind the WHOLE rendered message sent by the real SDK, not a substring hash.
    assert any(bundle.task(1)["instruction"].strip() in text and
               hashlib.sha256(text.encode()).hexdigest() == receipt["rendered_input_sha256"]
               for text in text_parts)
    evidence = receipt["response_evidence"]
    assert evidence["state"] == "observed" and evidence["served_model"] == "gpt-5.6-sol"
    assert evidence["reasoning_effort"] == "max"
    assert evidence["context_tokens"] == (context if context else "not_reported")
    assert receipt["threads"] == receipt["turns"] == 1
    assert receipt["experiment_id"] == usd.RUN_ID
    assert not receipt["full_five_task_witness"] and receipt["fixture_transport"]
    assert receipt["paid_launch_bridge_still_blocked"]
    result = json.loads((tmp_path / "worker-1" / single.RESULT).read_bytes())
    row = result["result"]
    assert row["status"] == "success" and row["task_id"] == launch.TASKS[1]
    assert row["deliverable_files"] and row["deliverable_file_records"]
    assert receipt["result"] == {"path": single.RESULT, **single._digest((tmp_path / "worker-1" / single.RESULT).read_bytes())}
    after, _ = wallet.read_checkpoint(tmp_path / "checkpoint-1",
        expected_sha256=receipt["wallet_checkpoint_sha256"], lineage=bundle.lineage,
        capture_sha256=bundle.capture_sha256, next_stage=2)
    assert after["binding"] == before["binding"]  # Same ledger identity, not a new USD 200 allowance.
    assert after["history"][0] == before["history"][0]
    assert after["previous_sha256"] == digest
    assert Decimal(after["snapshot"]["combined_modeled_usd"]) > Decimal("1")
    assert after["snapshot"]["pending_requests"] == 0
    assert receipt["provider_observation"]["runtime_caps"]["pilot_requests"] == 2
    assert hashlib.sha256((previous / wallet.MANIFEST).read_bytes()).hexdigest() == digest
    with pytest.raises(wire.PilotWireReceiptRefused):
        CodexAgentRunner(FixtureProvider(), run_id=usd.RUN_ID)
    with pytest.raises(PilotNativeResultHostRefused):
        native_result_host_for(receipt)  # Fragment JSON is never a whole-five live owner.
    with pytest.raises((wallet.WalletRefused, single.SingleTaskRefused)):
        run_shard(tmp_path, bundle, previous, digest)
    with pytest.raises(launch.LaunchRefused, match="sol_pilot_execution_bridge_incomplete"):
        launch.require_live_bridge()


def test_registered_reference_bytes_reach_real_native_workspace(monkeypatch, tmp_path, bundle):
    previous, digest, before = predecessor(tmp_path, bundle, stages=2)
    reference = bundle.task(2)["reference_file_records"][0]

    def respond():
        workspace, = Path(os.environ["GDPVAL_CODEX_RUN_ROOT"]).glob("*/workspace")
        staged = workspace / Path(reference["path"]).name
        assert hashlib.sha256(staged.read_bytes()).hexdigest() == reference["sha256"]
        assert staged.stat().st_size == reference["size"]
        assert staged.stat().st_mode & 0o777 == 0o400
        model_creates_file()

    with _upstream(monkeypatch, [scripted_response()], on_request=respond) as (received, _):
        receipt = run_shard(tmp_path, bundle, previous, digest, stage_index=2)
    assert receipt["status"] == "success" and len(received) == 1
    assert receipt["task_id"] == launch.TASKS[2]
    assert receipt["provider_observation"]["runtime_caps"]["pilot_requests"] == 3
    after, _ = wallet.read_checkpoint(tmp_path / "checkpoint-2",
        expected_sha256=receipt["wallet_checkpoint_sha256"], lineage=bundle.lineage,
        capture_sha256=bundle.capture_sha256, next_stage=3)
    assert after["binding"] == before["binding"]
    result = json.loads((tmp_path / "worker-2" / single.RESULT).read_bytes())["result"]
    assert len(result["deliverable_files"]) == 1  # Reference input is not republished as a deliverable.
    assert result["deliverable_files"][0].endswith("fixture-deliverable.txt")


@pytest.mark.parametrize("changes,reason", [
    ({"model": "gpt-5.6-sol-fast"}, "served_model_mismatch"),
    ({"model": None}, "served_model_unverified"),
    ({"effort": "high"}, "reasoning_effort_mismatch"),
    ({"effort": None}, "reasoning_effort_unverified"),
    ({"context": 258_400}, "context_window_mismatch"),
])
def test_first_response_refusal_is_failed_no_retry_and_checkpointed(monkeypatch, tmp_path, bundle, changes, reason):
    previous, digest, before = predecessor(tmp_path, bundle)
    with _upstream(monkeypatch, [scripted_response(**changes)], on_request=model_creates_file) as (received, _):
        receipt = run_shard(tmp_path, bundle, previous, digest)
    assert len(received) == 1
    assert receipt["status"] == "failed"
    assert receipt["response_evidence"]["reason"] == reason
    after = json.loads((tmp_path / "checkpoint-1" / wallet.MANIFEST).read_bytes())
    assert after["binding"] == before["binding"]
    assert after["outcome"] == "failed" and after["snapshot"]["pending_requests"] == 0
    assert Decimal(after["snapshot"]["combined_modeled_usd"]) >= Decimal("1")
    with pytest.raises(wallet.WalletRefused):
        wallet.restore_checkpoint(tmp_path / "worker-2", tmp_path / "checkpoint-1",
            expected_sha256=receipt["wallet_checkpoint_sha256"], lineage=bundle.lineage,
            capture_sha256=bundle.capture_sha256, stage_index=2)
    assert not (tmp_path / "worker-2").exists()


def test_missing_usage_stays_reserved_at_list_price_without_reset(monkeypatch, tmp_path, bundle):
    previous, digest, _ = predecessor(tmp_path, bundle, unknown=True)
    with _upstream(monkeypatch, [scripted_response(usage=None)], on_request=model_creates_file) as (received, _):
        receipt = run_shard(tmp_path, bundle, previous, digest)
    assert len(received) == 1
    after = json.loads((tmp_path / "checkpoint-1" / wallet.MANIFEST).read_bytes())
    assert after["snapshot"]["unknown_requests"] == 2
    assert after["snapshot"]["pending_requests"] == 0
    assert Decimal(after["snapshot"]["combined_modeled_usd"]) > 1
    assert receipt["provider_observation"]["runtime_caps"]["pilot_requests"] == 2


def test_shared_usd_ceiling_stops_before_provider_forward(monkeypatch, tmp_path, bundle):
    previous, digest, _ = predecessor(tmp_path, bundle, amount="199.999999")
    with _upstream(monkeypatch, []) as (received, _):
        receipt = run_shard(tmp_path, bundle, previous, digest)
    assert not received and receipt["status"] == "failed"
    after = json.loads((tmp_path / "checkpoint-1" / wallet.MANIFEST).read_bytes())
    assert after["snapshot"]["stop_reason"] == "usd_ceiling_exceeded"
    assert after["snapshot"]["combined_modeled_usd"] == "199.999999"
    assert after["snapshot"]["pending_requests"] == 0


@pytest.mark.parametrize("changes", [{"model": "other"}, {"reasoning_effort": "high"},
                                    {"model_context_window": 272_000}, {"base_url": "https://other.example/openai/v1"},
                                    {"request_max_retries": 1}, {"stream_max_retries": 1}])
def test_presend_provider_mismatch_refuses_before_runtime(tmp_path, bundle, changes):
    previous, digest, _ = predecessor(tmp_path, bundle)
    ledger = wallet.restore_checkpoint(tmp_path / "worker-1", previous, expected_sha256=digest,
        lineage=bundle.lineage, capture_sha256=bundle.capture_sha256, stage_index=1)
    try:
        with pytest.raises(single.SingleTaskRefused):
            single.SingleTaskWitness(bundle, ledger, stage_index=1,
                predecessor=previous, predecessor_sha256=digest,
                provider=replace(FixtureProvider(), **changes), fixture_transport=True)
        assert not (tmp_path / "worker-1" / single.CLAIM).exists()
    finally:
        ledger.close()


def test_single_task_witness_cannot_replace_predecessor_with_a_fresh_wallet(tmp_path, bundle):
    previous, digest, _ = predecessor(tmp_path, bundle)
    root = tmp_path / "wrong-fresh-wallet"
    root.mkdir()
    ledger = usd.PilotUsdLedger(root, capture_sha256=bundle.capture_sha256,
                               task_ids=list(launch.TASKS), create=True)
    try:
        with pytest.raises(single.SingleTaskRefused, match="single_task_restored_predecessor_required"):
            single.SingleTaskWitness(bundle, ledger, stage_index=1, provider=FixtureProvider(),
                predecessor=previous, predecessor_sha256=digest, fixture_transport=True)
        assert not (root / single.CLAIM).exists()
    finally:
        ledger.close()


def test_component_default_is_off_before_input_or_wallet_access(tmp_path):
    with pytest.raises(single.SingleTaskRefused, match="explicit_execute_paid_required"):
        single.run_single_task_shard(None, stage_index=1, predecessor=tmp_path / "absent",
            predecessor_sha256="0" * 64, workspace=tmp_path / "worker", checkpoint=tmp_path / "checkpoint",
            provider=FixtureProvider())
    assert not (tmp_path / "worker").exists()


def test_whole_five_step2_still_requires_its_actual_live_session(bundle, tmp_path):
    with pytest.raises(wire.PilotWireReceiptRefused):
        step2._execute_single_task(bundle.task(1), {"prompt": {}}, None, "codex_foundry", None,
            "gpt-5.6-sol", run_id=usd.RUN_ID, experiment_id=usd.RUN_ID, upload_root=tmp_path)
