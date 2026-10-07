"""Full-length synthetic Step0 at the real native callable boundary.

Auth/RPC, private storage and kernel state use the existing offline fixtures.
No case reads private originals or establishes real-host readiness.
"""

import json
import os
from types import SimpleNamespace

import pytest

import gpt54_time_budget_codex_ci as ci
from core.result_fingerprint import validate_inference_result_fingerprint
from gpt54_prepared_input_attestation import _identity
from .test_gpt54_time_budget_comparison import (
    dual_roots, handoff_source_seed as _small_source_seed, handoff_sources, observation_kernel,
)
from .test_time_budget_first_codex_ci import (
    _arguments, _invoke, actions_layout, case, local_kernel, offline, TOKEN,
)
from .test_time_budget_codex_observation import _native_transport, _FILE, _SECRET

_ORIGINAL_STEP0_PIN = dict(ci.originals.STEP0_PIN)


@pytest.fixture(scope="module")
def handoff_source_seed(tmp_path_factory, dual_roots):
    seed = _small_source_seed.__wrapped__(tmp_path_factory, dual_roots)
    small = seed.step0.read_bytes()
    assert _ORIGINAL_STEP0_PIN == {
        "size": 218405, "sha256": "463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512",
    }
    # Create a whole, valid synthetic JSON file of the actual original length.
    # Whitespace is part of its independently pinned bytes, not invented size
    # metadata. The transport/callable must preserve and hash the entire tail.
    full = small + b" " * (_ORIGINAL_STEP0_PIN["size"] - len(small))
    assert len(small) < 65536 < len(full) == 218405
    assert json.loads(full) == json.loads(small)
    assert json.loads(full)["_total_tasks"] == len(json.loads(full)["tasks"]) == 6
    seed.step0.write_bytes(full)
    seed.step0_sha = _identity(full)["sha256"]
    assert seed.step0_sha != _ORIGINAL_STEP0_PIN["sha256"]
    return seed


@pytest.mark.parametrize("change", [
    "full_step0", "step0_bytes", "step0_digest", "step0_size", "step0_over_bound",
    "preparation_over_bound", "direction_over_bound",
])
def test_time_budget_native_step0_identity_bound(case, offline, monkeypatch, capsys, change):
    entry = ci.observation
    assert ci.registration.MAX_MANIFEST_BYTES == entry.MAX_DIRECTION_BYTES == 65536
    assert entry.STEP0_PIN == _ORIGINAL_STEP0_PIN
    full = case.seed.step0.read_bytes()
    full_identity = _identity(full)
    assert full_identity == case.request["step0"]["identity"] == ci.originals.STEP0_PIN
    assert full_identity["size"] == 218405 and full_identity["sha256"] != _ORIGINAL_STEP0_PIN["sha256"]
    # All state is newly created by this fixture, never a historical claim.
    selected = {**ci.CELL, "task_id": case.seed.task_ids[1]}
    assert selected["task_id"] == "0112fc9b-c3b2-4084-8993-5a4abb1f54f1"
    prefix, claim_path, manifest_path = ci.shared._namespace(selected)
    case.request["cell"] = selected
    case.request["storage"]["prefix"] = prefix
    case.api.claim, case.api.manifest = claim_path, manifest_path
    assert _invoke(case, monkeypatch, "prepare-and-claim") == 0
    assert len(case.downloads) == 4 and case.api.commits == ["claim"] and offline.auth_calls == []
    step0 = case.root / "inputs" / ci.originals.STEP0
    assert step0.read_bytes() == full
    marker = ci._read(case.root / "preparation" / ci.registration.HANDOFF_READY)
    assert marker["inputs"]["step0_manifest"] == full_identity
    claim_bytes = case.api.trees[case.api.head][claim_path]
    assert json.loads(claim_bytes)["step0_provenance"] == case.request["step0"]
    private_before = dict(case.api.trees[case.api.head])
    calls_before = list(case.api.calls)
    direction_path = case.root / "direction.json"
    direction_bytes = direction_path.read_bytes()
    assert json.loads(direction_bytes)["step0_identity"] == full_identity
    protected = {path: path.read_bytes() for path in (
        case.root / "claim-reserved.json", case.root / "claim-receipt.json",
        case.root / "preparation" / ci.registration.HANDOFF_READY,
    )}
    spec = SimpleNamespace(arguments={"observation": entry.ObservationIdentity(**marker["observation"])},
                           marker=marker, consumed=case.root / ("preparation" + ci.registration.HANDOFF_CONSUMED_SUFFIX))
    native = _native_transport(monkeypatch, spec, offline, outcome="success")
    (offline.login / "synthetic-session").write_bytes(b"Synthetic login state; not credentials.")
    destination = case.root / "result"

    if change == "full_step0":
        assert _invoke(case, monkeypatch, "execute") == 0
        assert len(native.controls) == len(native.clients) == len(offline.auth_calls) == 1
        assert [method for method, _ in native.requests] == ["initialize", "thread/start", "turn/start"]
        control = native.controls[0]
        assert control.identity == spec.arguments["observation"]
        assert control.cleanup_complete and control.as_record()["host_reusable"]
        assert control.cleanup_deadline - control.terminal_at == 20
        assert spec.consumed.is_file() and (case.root / "execution-reserved.json").is_file()
        assert not any(os.environ.get(key) for key in ci.shared.TOKEN_KEYS)
        data = (destination / entry.RESULT).read_bytes()
        payload = json.loads(data)
        assert payload["condition"] == "codex" and payload["execution_mode"] == "codex_foundry"
        assert payload["observation_execution"]["inputs"]["step0_manifest"] == full_identity
        assert payload["time_budget_observation"] == control.as_record()
        row = payload["results"][0]
        assert row["task_id"] == selected["task_id"] and row["status"] == "success" and row["usage"] is None
        assert all(value is None for value in row["observability"]["native_measurements"].values())
        assert validate_inference_result_fingerprint(payload) == payload["result_fingerprint"]
        member = "result/upload/deliverable_files/" + selected["task_id"] + "/deliverable.txt"
        assert (case.root / member).read_bytes() == _FILE
        assert step0.read_bytes() == case.seed.step0.read_bytes() == full
        assert direction_path.read_bytes() == direction_bytes
        monkeypatch.setenv("HF_TOKEN", TOKEN)
        assert _invoke(case, monkeypatch, "retain") == 0
        envelope = ci._read(case.root / "completion.json")
        ci.validate_envelope(envelope, expected_cell=selected)
        assert _invoke(case, monkeypatch, "verify-envelope") == 0
        assert envelope["status"] == "success" and envelope["retention"] == "acknowledged"
        assert envelope["result_identity"] == _identity(data) and envelope["result_fingerprint"] == payload["result_fingerprint"]
        assert envelope["retry_allowed"] is False and envelope["grading_performed"] is False and envelope["other_cells_executed"] == 0
        assert case.api.commits == ["claim", "output"]
        assert case.api.trees[case.api.head][prefix + "/result/" + entry.RESULT] == data
        assert case.api.trees[case.api.head][prefix + "/" + member] == _FILE
        manifest = json.loads(case.api.trees[case.api.head][manifest_path])
        assert manifest["observation"] == marker["observation"]
        assert manifest["request_identity"] == json.loads(claim_bytes)["request_identity"]
        assert step0.read_bytes() == case.seed.step0.read_bytes() == full
    else:
        # Derive the same native arguments as execute from the real controller
        # context. Change only the selected input under test, not any verdict.
        with ci.checked_request(request_json=ci._bytes(case.request).decode(),
                                **_arguments(case, monkeypatch)) as context:
            direction, preparation = ci._direction(context, marker)
            arguments = {**ci._common(context), "observation": spec.arguments["observation"],
                "direction_path": direction_path, "expected_direction_sha256": _identity(ci._bytes(direction))["sha256"],
                "expected_host_sha256": context["host"]["instance_sha256"],
                "preparation_directory": case.root / "preparation", "expected_preparation_identity": preparation,
                "expected_step0_identity": dict(full_identity), "observation_directory": case.root / "observation",
                "destination": destination}
        for key in ci.shared.TOKEN_KEYS:
            monkeypatch.delenv(key, raising=False)
        if change == "step0_bytes":
            # Mutate a byte beyond the old cap, retaining valid JSON and size.
            step0.write_bytes(full[:-1] + b"\n")
            assert len(step0.read_bytes()) == 218405 and json.loads(step0.read_bytes()) == json.loads(full)
        elif change == "step0_digest":
            arguments["expected_step0_identity"]["sha256"] = "0" * 64
        elif change == "step0_size":
            arguments["expected_step0_identity"]["size"] -= 1
        elif change == "step0_over_bound":
            arguments["expected_step0_identity"]["size"] += 1
        elif change == "preparation_over_bound":
            boundary = {"sha256": preparation["sha256"], "size": 65536}
            assert entry._expected_identity(boundary) == boundary
            arguments["expected_preparation_identity"] = {**boundary, "size": 65537}
        else:
            assert change == "direction_over_bound" and len(direction_bytes) < 65536
            oversized = direction_bytes.ljust(65537, b" ")
            direction_path.write_bytes(oversized)
            arguments["expected_direction_sha256"] = _identity(oversized)["sha256"]
            assert json.loads(oversized) == json.loads(direction_bytes)
        expected = (f"reference file hash mismatch: {step0}" if change in {"step0_bytes", "step0_digest"}
                    else f"reference file size mismatch: {step0}" if change == "step0_size"
                    else "direction_size_bound" if change == "direction_over_bound"
                    else "independent_identity_size_bound")
        current_step0, current_direction = step0.read_bytes(), direction_path.read_bytes()
        with pytest.raises(ValueError) as refused:
            entry.run_codex_observation(case.seed.plan, **arguments)
        assert refused.value.args == (expected,)
        assert native.controls == native.clients == native.requests == offline.auth_calls == []
        assert not spec.consumed.exists() and not destination.exists()
        assert not destination.with_name(destination.name + entry.RESERVATION_SUFFIX).exists()
        assert not (case.root / "execution-reserved.json").exists() and not (case.root / "execution-receipt.json").exists()
        assert not (case.root / "retention-reserved.json").exists() and not (case.root / "completion.json").exists()
        assert list((case.root / "observation").iterdir()) == [] and list(offline.native_root.iterdir()) == []
        assert case.api.calls == calls_before and case.api.commits == ["claim"]
        assert case.api.trees[case.api.head] == private_before
        assert step0.read_bytes() == current_step0 and direction_path.read_bytes() == current_direction
    assert {path: path.read_bytes() for path in protected} == protected
    assert case.api.trees[case.api.head][claim_path] == claim_bytes
    assert case.api.trees[case.api.head][case.prior] == case.prior_bytes
    assert case.seed.step0.read_bytes() == full and len(case.downloads) == 4
    captured = capsys.readouterr()
    assert captured.err == ""
    assert all(secret not in captured.out for secret in (TOKEN, _SECRET, "Synthetic final answer.", "deliverable.txt", "reference_files"))
