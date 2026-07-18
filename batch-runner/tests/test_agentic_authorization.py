"""Tests for signed, single-use agentic approval envelopes."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from core.agentic_authorization import (
    ApprovalExpectation,
    ApprovalNonceLedger,
    AuthorizationError,
    SignedApprovalGate,
    canonical_json,
    load_approval_scope,
    provider_endpoint_sha256,
)


def _expectation():
    return ApprovalExpectation(
        plan_sha="a" * 40,
        implementation_sha="b" * 40,
        run_id="run-1",
        condition="treatment",
        provider="azure",
        model="deployment",
        api_version="2025-04-01-preview",
        endpoint_sha256="9" * 64,
        workflow_sha="d" * 40,
        workflow_inputs_sha256="e" * 64,
        conditions=("treatment",),
        task_ids=("task-1",),
        input_merkle_roots={"task-1": "c" * 64},
        provider_classifications={
            "task-1": "approved_public_gdpval",
        },
        approval_scope_sha256="7" * 64,
        official_scope_registry_sha256="8" * 64,
    )


def _envelope(now):
    expected = _expectation()
    return {
        "schema_version": "1.0",
        "plan_sha": expected.plan_sha,
        "implementation_sha": expected.implementation_sha,
        "run_id": expected.run_id,
        "conditions": list(expected.conditions),
        "task_ids": list(expected.task_ids),
        "input_merkle_roots": dict(expected.input_merkle_roots),
        "provider_classifications": dict(expected.provider_classifications),
        "provider": expected.provider,
        "model": expected.model,
        "api_version": expected.api_version,
        "endpoint_sha256": expected.endpoint_sha256,
        "workflow_sha": expected.workflow_sha,
        "workflow_inputs_sha256": expected.workflow_inputs_sha256,
        "substrate_manifest_sha256": "1" * 64,
        "price_table_sha256": "2" * 64,
        "official_scope_excluded": True,
        "approval_scope_sha256": expected.approval_scope_sha256,
        "official_scope_registry_sha256": (
            expected.official_scope_registry_sha256
        ),
        "caps": {"cost_usd": "6.25", "api_attempts": 30},
        "issued_at": (now - timedelta(minutes=1)).isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "nonce": "single-use-nonce-" + "f" * 32,
    }


def _write_signed(tmp_path, envelope):
    tmp_path.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    key_path = tmp_path / "owner.pub.pem"
    key_path.write_bytes(public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    signature = private_key.sign(canonical_json(envelope))
    envelope_path = tmp_path / "approval.json"
    envelope_path.write_text(json.dumps({
        "envelope": envelope,
        "signature": base64.b64encode(signature).decode("ascii"),
    }), encoding="utf-8")
    return envelope_path, key_path


def _gate(tmp_path, envelope, now, ledger_path=None):
    envelope_path, key_path = _write_signed(tmp_path, envelope)
    return SignedApprovalGate(
        signed_envelope_path=envelope_path,
        owner_public_key_path=key_path,
        nonce_ledger=ApprovalNonceLedger(ledger_path or tmp_path / "nonces.sqlite3"),
        expectation=_expectation(),
        now=now,
    ), envelope_path


def _context():
    expected = _expectation()
    return {
        "runtime_preflight_passed": True,
        "input_merkle_root": expected.input_merkle_roots["task-1"],
        "provider_classification": expected.provider_classifications["task-1"],
        "task_id": "task-1",
        "run_id": expected.run_id,
        "condition": expected.condition,
        "model": expected.model,
        "provider": expected.provider,
        "api_version": expected.api_version,
        "endpoint_sha256": expected.endpoint_sha256,
        "approval_scope_sha256": expected.approval_scope_sha256,
        "official_scope_registry_sha256": (
            expected.official_scope_registry_sha256
        ),
        "caps": {"cost_usd": "6.25", "api_attempts": 30},
        "substrate_manifest_sha256": "1" * 64,
        "price_table_sha256": "2" * 64,
        "official_scope_excluded": True,
    }


def test_valid_envelope_claims_once_and_allows_same_active_gate(tmp_path):
    now = datetime.now(timezone.utc)
    gate, _ = _gate(tmp_path, _envelope(now), now)

    scope = '["run-1","treatment","task-1"]'
    gate.authorize_request(scope, "a" * 64, _context())
    gate.authorize_request(scope, "b" * 64, _context())


def test_signature_tamper_and_expiry_fail_closed(tmp_path):
    now = datetime.now(timezone.utc)
    gate, envelope_path = _gate(tmp_path, _envelope(now), now)
    signed = json.loads(envelope_path.read_text(encoding="utf-8"))
    signed["envelope"]["model"] = "other-deployment"
    envelope_path.write_text(json.dumps(signed), encoding="utf-8")

    with pytest.raises(AuthorizationError, match="signature_invalid"):
        gate.authorize_request(
            '["run-1","treatment","task-1"]', "a" * 64, _context()
        )

    expired = _envelope(now)
    expired["issued_at"] = (now - timedelta(hours=2)).isoformat()
    expired["expires_at"] = (now - timedelta(hours=1)).isoformat()
    expired_gate, _ = _gate(tmp_path / "expired", expired, now)
    with pytest.raises(AuthorizationError, match="expired"):
        expired_gate.authorize_request(
            '["run-1","treatment","task-1"]', "a" * 64, _context()
        )


def test_runtime_caps_must_exactly_match_signed_caps(tmp_path):
    now = datetime.now(timezone.utc)
    gate, _ = _gate(tmp_path, _envelope(now), now)
    context = _context()
    context["caps"] = {"cost_usd": "6.26", "api_attempts": 30}

    with pytest.raises(AuthorizationError, match="approval_caps_invalid"):
        gate.authorize_request(
            '["run-1","treatment","task-1"]', "a" * 64, context
        )


def test_official_scope_exclusion_must_be_signed_and_runtime_true(tmp_path):
    now = datetime.now(timezone.utc)
    envelope = _envelope(now)
    envelope["official_scope_excluded"] = False
    gate, _ = _gate(tmp_path, envelope, now)

    with pytest.raises(AuthorizationError, match="official_scope"):
        gate.authorize_request(
            '["run-1","treatment","task-1"]', "a" * 64, _context()
        )


def test_replay_in_new_process_identity_is_rejected(tmp_path):
    now = datetime.now(timezone.utc)
    ledger_path = tmp_path / "nonces.sqlite3"
    envelope = _envelope(now)
    first, _ = _gate(tmp_path / "first", envelope, now, ledger_path)
    second, _ = _gate(tmp_path / "second", envelope, now, ledger_path)

    scope = '["run-1","treatment","task-1"]'
    first.authorize_request(scope, "a" * 64, _context())
    with pytest.raises(AuthorizationError, match="already_consumed"):
        second.authorize_request(scope, "a" * 64, _context())


def test_concurrent_nonce_claim_has_exactly_one_winner(tmp_path):
    now = datetime.now(timezone.utc)
    ledger_path = tmp_path / "nonces.sqlite3"
    envelope = _envelope(now)
    gates = [
        _gate(tmp_path / f"gate-{index}", envelope, now, ledger_path)[0]
        for index in range(2)
    ]

    def claim(gate):
        try:
            gate.authorize_request(
                '["run-1","treatment","task-1"]', "a" * 64, _context()
            )
            return "accepted"
        except AuthorizationError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, gates))

    assert sorted(outcomes) == ["accepted", "rejected"]


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda envelope: envelope.update(schema_version="2.0"), "schema_version"),
        (lambda envelope: envelope.update(task_ids=["task-1", "task-1"]), "tasks_invalid"),
        (
            lambda envelope: envelope["input_merkle_roots"].update(
                {"unexpected": "0" * 64}
            ),
            "input_roots_invalid",
        ),
        (
            lambda envelope: envelope.update(
                expires_at=(
                    datetime.now(timezone.utc) + timedelta(hours=9)
                ).isoformat()
            ),
            "expired_or_not_yet_valid",
        ),
    ],
)
def test_approval_structure_and_lifetime_are_strict(
    tmp_path, mutation, match
):
    now = datetime.now(timezone.utc)
    envelope = _envelope(now)
    mutation(envelope)
    gate, _ = _gate(tmp_path, envelope, now)

    with pytest.raises(AuthorizationError, match=match):
        gate.authorize_request(
            '["run-1","treatment","task-1"]', "a" * 64, _context()
        )


def test_provider_endpoint_hash_normalizes_https_origin_and_rejects_unsafe():
    expected = provider_endpoint_sha256(
        "azure", "https://Example.OpenAI.Azure.com/path/"
    )

    assert expected == provider_endpoint_sha256(
        "azure_openai", "https://example.openai.azure.com/other"
    )
    assert expected != provider_endpoint_sha256(
        "azure", "https://other.openai.azure.com"
    )
    with pytest.raises(ValueError, match="HTTPS origin"):
        provider_endpoint_sha256("azure", "http://example.test")
    with pytest.raises(ValueError, match="HTTPS origin"):
        provider_endpoint_sha256("openai", "https://user@example.test")


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("task_ids", ["task-1", "task-2"], "task_set_mismatch"),
        (
            "input_merkle_roots",
            {"task-1": "0" * 64},
            "input_set_mismatch",
        ),
        (
            "provider_classifications",
            {"task-1": "other-provider-class"},
            "classification_set_mismatch",
        ),
        ("official_scope_registry_sha256", "0" * 64, "registry_mismatch"),
    ],
)
def test_signed_phase_scope_must_exactly_match_preregistered_scope(
    tmp_path, field, value, match
):
    now = datetime.now(timezone.utc)
    envelope = _envelope(now)
    envelope[field] = value
    if field == "task_ids":
        envelope["input_merkle_roots"]["task-2"] = "d" * 64
        envelope["provider_classifications"][
            "task-2"
        ] = "approved_public_gdpval"
    gate, _ = _gate(tmp_path, envelope, now)

    with pytest.raises(AuthorizationError, match=match):
        gate.authorize_request(
            '["run-1","treatment","task-1"]', "a" * 64, _context()
        )


def test_load_approval_scope_requires_tracked_exact_manifest(tmp_path):
    repository = tmp_path / "repository"
    registry = repository / "src" / "lib" / "officialExperimentScope.js"
    scope_path = repository / "approval-scope.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("export const hidden = ['exp030']\n", encoding="utf-8")
    body = {
        "schema_version": "agentic-approval-scope-v1",
        "conditions": ["treatment"],
        "ordered_task_ids": ["task-1"],
        "input_merkle_roots": {"task-1": "c" * 64},
        "provider_classifications": {
            "task-1": "approved_public_gdpval",
        },
    }
    body["sha256"] = hashlib.sha256(canonical_json(body)).hexdigest()
    scope_path.write_text(json.dumps(body), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)

    scope = load_approval_scope(
        repository_root=repository,
        scope_path="approval-scope.json",
    )

    assert scope["conditions"] == ("treatment",)
    assert scope["task_ids"] == ("task-1",)
    assert scope["approval_scope_sha256"] == body["sha256"]
    assert scope["official_scope_registry_sha256"] == hashlib.sha256(
        registry.read_bytes()
    ).hexdigest()