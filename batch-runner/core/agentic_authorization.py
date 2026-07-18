"""Signed, single-use authorization gate for live agentic model calls."""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import re
import sqlite3
import stat
import subprocess
import threading
from urllib.parse import urlsplit
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


REQUIRED_FIELDS = {
    "schema_version", "plan_sha", "implementation_sha", "run_id",
    "conditions", "task_ids", "input_merkle_roots", "provider_classifications",
    "provider", "model", "api_version", "endpoint_sha256", "workflow_sha",
    "workflow_inputs_sha256",
    "substrate_manifest_sha256", "price_table_sha256", "caps", "issued_at",
    "expires_at", "nonce", "official_scope_excluded",
    "approval_scope_sha256", "official_scope_registry_sha256",
}
MAX_APPROVAL_LIFETIME_SECONDS = 8 * 60 * 60


class AuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class ApprovalExpectation:
    plan_sha: str
    implementation_sha: str
    run_id: str
    condition: str
    provider: str
    model: str
    api_version: str
    endpoint_sha256: str
    workflow_sha: str
    workflow_inputs_sha256: str
    conditions: tuple[str, ...]
    task_ids: tuple[str, ...]
    input_merkle_roots: Mapping[str, str]
    provider_classifications: Mapping[str, str]
    approval_scope_sha256: str
    official_scope_registry_sha256: str


def load_approval_scope(
    *, repository_root: str | Path, scope_path: str | Path
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    candidate = Path(scope_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("approval scope path escapes repository") from exc
    current = root
    for part in relative.parts:
        current /= part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError("approval scope path contains a symlink")
    metadata = candidate.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError("approval scope must be a single-link regular file")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative.as_posix()],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        raise ValueError("approval scope must be tracked in the clean checkout")
    document = json.loads(candidate.read_text(encoding="utf-8"))
    required = {
        "schema_version", "conditions", "ordered_task_ids",
        "input_merkle_roots", "provider_classifications", "sha256",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("approval scope fields are invalid")
    canonical = {key: value for key, value in document.items() if key != "sha256"}
    digest = hashlib.sha256(canonical_json(canonical)).hexdigest()
    if document["schema_version"] != "agentic-approval-scope-v1":
        raise ValueError("approval scope version is invalid")
    if document["sha256"] != digest:
        raise ValueError("approval scope hash mismatch")
    conditions = document["conditions"]
    task_ids = document["ordered_task_ids"]
    roots = document["input_merkle_roots"]
    classifications = document["provider_classifications"]
    if (
        not isinstance(conditions, list)
        or not conditions
        or len(conditions) != len(set(conditions))
        or any(not isinstance(value, str) or not value for value in conditions)
        or not isinstance(task_ids, list)
        or not task_ids
        or len(task_ids) > 25
        or len(task_ids) != len(set(task_ids))
        or any(not isinstance(value, str) or not value for value in task_ids)
        or not isinstance(roots, dict)
        or set(roots) != set(task_ids)
        or any(
            not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in roots.values()
        )
        or not isinstance(classifications, dict)
        or set(classifications) != set(task_ids)
        or any(
            not isinstance(value, str) or not value
            for value in classifications.values()
        )
    ):
        raise ValueError("approval scope identities are invalid")
    registry = root / "src" / "lib" / "officialExperimentScope.js"
    if not registry.is_file() or registry.is_symlink():
        raise ValueError("official scope registry is missing or symlinked")
    return {
        "conditions": tuple(conditions),
        "task_ids": tuple(task_ids),
        "input_merkle_roots": dict(roots),
        "provider_classifications": dict(classifications),
        "approval_scope_sha256": digest,
        "official_scope_registry_sha256": hashlib.sha256(
            registry.read_bytes()
        ).hexdigest(),
    }


class ApprovalNonceLedger:
    """Atomically consume approval nonces across processes and restarts."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(f"{self.path}.init.lock", "a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with self._connect() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute(
                    """
                CREATE TABLE IF NOT EXISTS approval_nonces (
                    nonce TEXT PRIMARY KEY,
                    envelope_sha256 TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    consumed_at TEXT NOT NULL
                )
                    """
                )
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.execute("PRAGMA busy_timeout=30000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def consume(self, *, nonce: str, envelope_sha256: str, run_id: str) -> None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO approval_nonces(nonce, envelope_sha256, run_id, consumed_at)
                VALUES (?, ?, ?, ?)
                """,
                (nonce, envelope_sha256, run_id, datetime.now(timezone.utc).isoformat()),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            connection.rollback()
            raise AuthorizationError("approval_nonce_already_consumed") from exc
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class SignedApprovalGate:
    """Verify immutable approval scope before a client can be constructed."""

    def __init__(
        self,
        *,
        signed_envelope_path: str | Path,
        owner_public_key_path: str | Path,
        nonce_ledger: ApprovalNonceLedger,
        expectation: ApprovalExpectation,
        now: Optional[datetime] = None,
    ):
        self.signed_envelope_path = Path(signed_envelope_path)
        self.owner_public_key_path = Path(owner_public_key_path)
        self.nonce_ledger = nonce_ledger
        self.expectation = expectation
        self.now = now
        self._lock = threading.Lock()
        self._active_digest: Optional[str] = None
        self._envelope: Optional[dict] = None

    def authorize_request(
        self,
        scope: str,
        request_id: str,
        runtime_context: Mapping[str, Any],
    ) -> None:
        if not scope or not request_id:
            raise AuthorizationError("authorization_identity_missing")
        expected_scope = json.dumps(
            [
                self.expectation.run_id,
                self.expectation.condition,
                runtime_context.get("task_id"),
            ],
            separators=(",", ":"),
        )
        if scope != expected_scope:
            raise AuthorizationError("authorization_scope_mismatch")
        if re.fullmatch(r"[0-9a-f]{64}", request_id) is None:
            raise AuthorizationError("authorization_request_id_invalid")
        with self._lock:
            envelope, digest = self._load_and_verify(runtime_context)
            if self._active_digest is not None:
                if digest != self._active_digest:
                    raise AuthorizationError("approval_changed_after_claim")
                return
            self.nonce_ledger.consume(
                nonce=envelope["nonce"],
                envelope_sha256=digest,
                run_id=envelope["run_id"],
            )
            self._active_digest = digest
            self._envelope = envelope

    def _load_and_verify(self, runtime_context: Mapping[str, Any]) -> tuple[dict, str]:
        try:
            signed = json.loads(self.signed_envelope_path.read_text(encoding="utf-8"))
            envelope = signed["envelope"]
            signature = base64.b64decode(signed["signature"], validate=True)
        except Exception as exc:
            raise AuthorizationError("approval_envelope_invalid") from exc
        if not isinstance(envelope, dict) or set(envelope) != REQUIRED_FIELDS:
            raise AuthorizationError("approval_fields_invalid")
        self._validate_structure(envelope)
        canonical = canonical_json(envelope)
        digest = hashlib.sha256(canonical).hexdigest()
        try:
            public_key = serialization.load_pem_public_key(
                self.owner_public_key_path.read_bytes()
            )
        except Exception as exc:
            raise AuthorizationError("approval_public_key_invalid") from exc
        if not isinstance(public_key, Ed25519PublicKey):
            raise AuthorizationError("approval_public_key_type_invalid")
        try:
            public_key.verify(signature, canonical)
        except InvalidSignature as exc:
            raise AuthorizationError("approval_signature_invalid") from exc

        self._validate_time(envelope)
        self._validate_expectation(envelope, runtime_context)
        return envelope, digest

    @staticmethod
    def _validate_structure(envelope: Mapping[str, Any]) -> None:
        if envelope.get("schema_version") != "1.0":
            raise AuthorizationError("approval_schema_version_invalid")
        conditions = envelope.get("conditions")
        task_ids = envelope.get("task_ids")
        roots = envelope.get("input_merkle_roots")
        classifications = envelope.get("provider_classifications")
        if (
            not isinstance(conditions, list)
            or not conditions
            or len(conditions) > 3
            or len(set(conditions)) != len(conditions)
            or any(not isinstance(value, str) or not value for value in conditions)
        ):
            raise AuthorizationError("approval_conditions_invalid")
        if (
            not isinstance(task_ids, list)
            or not task_ids
            or len(task_ids) > 25
            or len(set(task_ids)) != len(task_ids)
            or any(not isinstance(value, str) or not value for value in task_ids)
        ):
            raise AuthorizationError("approval_tasks_invalid")
        if not isinstance(roots, dict) or set(roots) != set(task_ids):
            raise AuthorizationError("approval_input_roots_invalid")
        if any(
            not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in roots.values()
        ):
            raise AuthorizationError("approval_input_roots_invalid")
        if (
            not isinstance(classifications, dict)
            or set(classifications) != set(task_ids)
            or any(
                not isinstance(value, str) or not value
                for value in classifications.values()
            )
        ):
            raise AuthorizationError("approval_classifications_invalid")
        nonce = envelope.get("nonce")
        if (
            not isinstance(nonce, str)
            or len(nonce) < 32
            or len(nonce) > 256
        ):
            raise AuthorizationError("approval_nonce_invalid")

    def _validate_time(self, envelope: Mapping[str, Any]) -> None:
        try:
            issued = _timestamp(envelope["issued_at"])
            expires = _timestamp(envelope["expires_at"])
        except Exception as exc:
            raise AuthorizationError("approval_time_invalid") from exc
        now = self.now or datetime.now(timezone.utc)
        lifetime = (expires - issued).total_seconds()
        if (
            issued > now
            or expires <= now
            or expires <= issued
            or lifetime > MAX_APPROVAL_LIFETIME_SECONDS
        ):
            raise AuthorizationError("approval_expired_or_not_yet_valid")

    def _validate_expectation(
        self,
        envelope: Mapping[str, Any],
        runtime_context: Mapping[str, Any],
    ) -> None:
        expected = self.expectation
        scalar_fields = {
            "plan_sha": expected.plan_sha,
            "implementation_sha": expected.implementation_sha,
            "run_id": expected.run_id,
            "provider": expected.provider,
            "model": expected.model,
            "api_version": expected.api_version,
            "endpoint_sha256": expected.endpoint_sha256,
            "workflow_sha": expected.workflow_sha,
            "workflow_inputs_sha256": expected.workflow_inputs_sha256,
        }
        if any(envelope.get(key) != value for key, value in scalar_fields.items()):
            raise AuthorizationError("approval_identity_mismatch")
        if envelope.get("conditions") != list(expected.conditions):
            raise AuthorizationError("approval_condition_mismatch")
        if envelope.get("task_ids") != list(expected.task_ids):
            raise AuthorizationError("approval_task_set_mismatch")
        if envelope.get("input_merkle_roots") != dict(
            expected.input_merkle_roots
        ):
            raise AuthorizationError("approval_input_set_mismatch")
        if envelope.get("provider_classifications") != dict(
            expected.provider_classifications
        ):
            raise AuthorizationError("approval_classification_set_mismatch")
        if envelope.get("approval_scope_sha256") != expected.approval_scope_sha256:
            raise AuthorizationError("approval_scope_identity_mismatch")
        if (
            envelope.get("official_scope_registry_sha256")
            != expected.official_scope_registry_sha256
        ):
            raise AuthorizationError("official_scope_registry_mismatch")
        task_id = runtime_context.get("task_id")
        if not isinstance(task_id, str) or task_id not in expected.task_ids:
            raise AuthorizationError("approval_task_mismatch")
        input_merkle_root = expected.input_merkle_roots[task_id]
        provider_classification = expected.provider_classifications[task_id]
        if runtime_context.get("input_merkle_root") != input_merkle_root:
            raise AuthorizationError("runtime_input_identity_mismatch")
        if runtime_context.get("provider_classification") != provider_classification:
            raise AuthorizationError("runtime_classification_mismatch")
        runtime_scalars = {
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
        }
        if any(runtime_context.get(key) != value for key, value in runtime_scalars.items()):
            raise AuthorizationError("runtime_scope_mismatch")
        if runtime_context.get("runtime_preflight_passed") is not True:
            raise AuthorizationError("runtime_preflight_missing")
        if (
            envelope.get("official_scope_excluded") is not True
            or runtime_context.get("official_scope_excluded") is not True
        ):
            raise AuthorizationError("official_scope_exclusion_missing")
        for field in (
            "substrate_manifest_sha256", "price_table_sha256"
        ):
            value = runtime_context.get(field)
            if (
                not isinstance(value, str)
                or not value
                or envelope.get(field) != value
            ):
                raise AuthorizationError(f"approval_{field}_mismatch")
        caps = envelope.get("caps")
        runtime_caps = runtime_context.get("caps")
        if (
            not isinstance(caps, dict)
            or not caps
            or not isinstance(runtime_caps, dict)
            or canonical_json(caps) != canonical_json(runtime_caps)
        ):
            raise AuthorizationError("approval_caps_invalid")


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("utf-8")


def provider_endpoint_sha256(provider: str, endpoint: Optional[str]) -> str:
    normalized_provider = "azure" if provider == "azure_openai" else provider
    if normalized_provider == "openai" and not endpoint:
        endpoint = "https://api.openai.com/v1"
    if normalized_provider not in {"azure", "openai"} or not isinstance(
        endpoint, str
    ):
        raise ValueError("provider endpoint is required")
    parsed = urlsplit(endpoint.strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("provider endpoint must be an HTTPS origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("provider endpoint port is invalid") from exc
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    origin = f"https://{host}"
    if port not in (None, 443):
        origin += f":{port}"
    return hashlib.sha256(origin.encode("ascii")).hexdigest()


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)