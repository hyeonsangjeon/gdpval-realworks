"""Plan-first publication of one finalized CI cell to an explicit private target.

No target is selected or approved here. Publication is not wired to a workflow
and does not make a cell grade-ready. The separate metadata inspection cannot
publish. A retained reservation always forbids replay, including after a lost
response. Source results and accounting are never edited.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import io
import logging
import os
from pathlib import Path
import re
import signal
import stat
import sys
import time

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
from core.cost_projection import _missing_reasons, project_cost_receipt
from core.cost_receipts import (
    BUCKETS, RETRY_KINDS, STAGES, _CALL_COLUMNS, _RUNTIME_COLUMNS,
)
from core.hf_publication import _PublicationFile, _fsync_directory, _publication_additions
from core.inference_manifest import canonical_deliverable_path, canonicalize_azure_ai_routes
from core.public_error import public_task_error_text
from core.repository_identity import validate_hf_dataset_repo_id
from gpt54_codex_input_capture import _write_no_clobber

FORMAT = "codex-private-cell-output-v1"
RESERVATION = "output-publication-reserved.json"
RECEIPT = "output-publication-receipt.json"
MANIFEST = "output-manifest.json"
MAX_FILES = 128
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
MAX_LEDGER_ROWS = 10000
REQUEST_SECONDS = 30
PUBLICATION_SECONDS = 120
HF_ENDPOINT = "https://huggingface.co"
TARGET_CHECK_SECONDS = 20
OUTPUT_TARGET_REPO_SHA256 = "88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf"
TARGET_CHECK_REASONS = frozenset({
    "registered_output_target_mismatch", "explicit_hf_token_required", "existing_timer_refused",
    "hf_offline_mode", "hf_metadata_request_refused", "hf_metadata_redirect_refused",
    "hf_metadata_response_refused", "hf_http_failed", "hf_transport_failed",
    "hf_response_bytes_exceeded", "output_target_identity_mismatch",
    "output_target_privacy_unavailable", "output_target_head_unavailable", "private_output_target_required",
})

# These are Step2's supported record fields, not an alternate result schema.
# Unknown fields are refused, never stripped from an otherwise unchanged file.
RESULT_FIELDS = frozenset({
    "experiment_id", "experiment_name", "publication_generation", "source", "condition",
    "condition_identity", "run_id", "execution_mode", "ordered_task_ids", "prepared_fingerprint",
    "model", "started_at", "completed_at", "resume_rounds_used", "summary", "results",
    "azure_ai_routes", "cost_ledger", "result_fingerprint",
})
ROW_FIELDS = frozenset({
    "task_id", "status", "content", "deliverable_text", "deliverable_files", "deliverable_file_records",
    "model", "usage", "observability", "latency_ms", "timestamp", "error", "problem_solving_cost",
    "resume_round", "task_deadline", "failure_evidence",
})
FORBIDDEN_KEYS = frozenset({
    "token", "access_token", "refresh_token", "authorization", "api_key", "env", "environment",
    "codex_home", "auth", "auth_store", "transcript", "native_transcript", "messages", "raw_response",
    "stdout", "stderr", "logs", "workspace", "workspace_path", "reference_files", "reference_file_urls",
    "reference_file_records", "instruction", "prompt", "original_parquet",
})


class OutputPublicationRefused(ValueError):
    """Only a closed code and an actually received HTTP status may escape."""

    def __init__(self, code: str, http_status: int | None = None):
        super().__init__(code)
        self.http_status = http_status


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise OutputPublicationRefused("invalid_arguments")


def _hash(value: object, width: int = 64) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(width) + "}", value) is not None


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise OutputPublicationRefused(reason)


def _bytes(path: Path, *, limit: int, expected: dict | None = None) -> bytes:
    """Bound a single-link read before parsing, with the existing byte identity."""
    pilot._assert_no_symlink_ancestors(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                 and before.st_size <= limit, "payload_file_or_size_refused")
        data = stream.read(limit + 1)
        after, current = os.fstat(stream.fileno()), path.lstat()
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        _require(len(data) == before.st_size and all(
            getattr(before, key) == getattr(item, key) for key in fields for item in (after, current)
        ), "payload_file_changed")
    if expected is not None:
        _require(pilot._identity(data) == {key: expected[key] for key in ("size", "sha256")},
                 "payload_identity_mismatch")
    return data


def _checkpoint(path: Path) -> dict:
    pilot._regular_private(path)
    record = pilot._json_object(_bytes(path, limit=MAX_RECORD_BYTES))
    _require(set(record) == {"payload", "sha256"} and record["sha256"] == pilot._digest(record["payload"]),
             "checkpoint_checksum_mismatch")
    return record["payload"]


def _safe_record(value: object, depth: int = 0) -> None:
    """Reject raw-state fields; generated text remains text, not executable data."""
    _require(depth <= 24, "unsafe_result_structure")
    if isinstance(value, dict):
        _require(not {str(key).lower() for key in value} & FORBIDDEN_KEYS, "unsafe_result_fields")
        for item in value.values():
            _safe_record(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _safe_record(item, depth + 1)


def _receipt_fields(value: object) -> None:
    """Use the existing cost reader without publishing discarded extra fields."""
    projected = project_cost_receipt(value)
    if projected is not None:
        _require(set(value) <= set(projected), "unsafe_receipt_fields")
        for raw, checked in zip(value.get("components") or [], projected["components"]):
            _require(set(raw) <= set(checked), "unsafe_receipt_fields")


def _ledger(data: bytes, cell: dict) -> None:
    lines = data.decode("utf-8").splitlines()
    _require(len(lines) <= MAX_LEDGER_ROWS, "ledger_rows_exceeded")
    seen = set()
    for line in lines:
        row = pilot._json_object(line.encode())
        kind = row.get("record_type")
        columns = _CALL_COLUMNS if kind == "call" else _RUNTIME_COLUMNS if kind == "runtime" else ()
        _require(bool(columns) and set(row) == {*columns, "record_type"}, "ledger_schema_refused")
        key = "call_id" if kind == "call" else "entry_id"
        identity = (kind, row[key])
        _require(type(row[key]) is str and bool(row[key]) and identity not in seen,
                 "ledger_duplicate_or_missing_identity")
        seen.add(identity)
        _require(row["run_id"] == cell["run_id"] and row["task_id"] in (None, cell["task_id"]),
                 "ledger_cell_mismatch")
        # Do not price, aggregate, instantiate SQLite, or re-export this evidence.
        _safe_record(row)
        _require(type(row["missing_reasons"]) is list, "ledger_reasons_refused")
        _missing_reasons(row["missing_reasons"], "ledger missing reasons")
        if kind == "call":
            _require(row["state"] in {"reserved", "settled", "abandoned", "refused"}, "ledger_state_refused")
            _require(row["stage"] in STAGES and row["retry_kind"] in RETRY_KINDS, "ledger_stage_refused")
            _require(row["note"] is None or (type(row["note"]) is str and
                     re.fullmatch(r"[a-z][a-z0-9_.:-]{0,127}", row["note"]) is not None), "unsafe_ledger_note")
            _require(all(row[name] is None or _hash(row[name]) for name in
                         ("price_table_sha256", "request_sha256")), "ledger_hash_refused")
        else:
            _require(row["bucket"] in BUCKETS and row["attribution"] in {"per_task", "shared", "unknown"},
                     "ledger_runtime_refused")
        for name, value in row.items():
            if name.endswith("_tokens"):
                _require(value is None or (type(value) is int and value >= 0), "ledger_usage_refused")
            elif name.endswith("_cost_usd") and value is not None:
                from decimal import Decimal, InvalidOperation

                _require(type(value) in (str, int, float), "ledger_amount_refused")
                try:
                    amount = Decimal(str(value))
                    _require(amount.is_finite() and amount >= 0, "ledger_amount_refused")
                except InvalidOperation as error:
                    raise OutputPublicationRefused("ledger_amount_refused") from error
            elif name != "missing_reasons":
                _require(value is None or (type(value) is str and
                         re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:+-]{0,511}", value) is not None),
                         "ledger_identity_refused")


@dataclass
class Snapshot:
    manifest: dict
    files: dict[str, bytes]
    cell_root: Path


def prepare(*, root: Path, campaign: str, cell_id: str, source_sha: str, config_sha: str) -> Snapshot:
    """Validate retained facts under the dispatch lock; never repair a cell."""
    _require(campaign == ci.CAMPAIGN, "registered_ci_campaign_required")
    _require(_hash(source_sha, 40) and _hash(config_sha), "explicit_source_and_config_required")
    _require(".." not in root.parts, "unsafe_campaign_root")
    root = pilot._assert_no_symlink_ancestors(root)
    _require(stat.S_IMODE(root.stat().st_mode) == 0o700, "private_campaign_root_required")
    canonical, _, _ = pilot.compile_pilot(campaign, source_sha)
    matches = [cell for cell in canonical["cells"] if cell["cell_id"] == cell_id]
    _require(len(matches) == 1, "canonical_selected_cell_required")
    cell = matches[0]
    _require(cell["config_sha256"] == config_sha, "expected_config_mismatch")
    pilot._regular_private(root / "lock")
    with os.fdopen(os.open(root / "lock", os.O_RDONLY | os.O_NOFOLLOW), "rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = _checkpoint(root / "plan.json")
        _require({key: value for key, value in plan.items() if key != "ci"} == canonical, "retained_plan_mismatch")
        context = plan["ci"]
        host = context["host"]
        _require(set(context) == {"registration_sha256", "selected_cell_id", "host"}
                 and context["selected_cell_id"] == cell_id
                 and context["registration_sha256"] == pilot._identity(pilot._read_bytes(ci.REGISTRATION))["sha256"]
                 and set(host) == {"policy", "instance_sha256", "workflow", "workflow_sha", "run_attempt"}
                 and host["policy"] == ci.HOST_POLICY and _hash(host["instance_sha256"])
                 and host["workflow_sha"] == source_sha and type(host["run_attempt"]) is int
                 and host["run_attempt"] == 1 and type(host["workflow"]) is str
                 and re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.yml", host["workflow"]) is not None,
                 "retained_ci_binding_mismatch")
        _require(_checkpoint(root / "ready.json") == {"plan_sha256": pilot._digest(plan)}, "ready_binding_mismatch")
        state = _checkpoint(root / cell["roles"]["checkpoint"])
        pilot._validate_state(plan, cell, state)
        _require(state["status"] in pilot.TERMINAL and state["phase"] == "finished", "finalized_cell_required")
        _require(state["accounting"] in {"missing", *ci.COST_STATUSES}, "recorded_accounting_refused")
        _require(stat.S_IMODE((root / "cells" / cell_id).stat().st_mode) == 0o700, "private_cell_root_required")
        owner = _checkpoint(root / "owned-child.json")
        pilot._require_quiet_owner(root, plan)
        _require(owner["phase"] == "reaped" and owner["cell_id"] == cell_id, "selected_cell_cleanup_required")
        checkout = root / cell["roles"]["checkout"]
        for config in (root / "cells" / cell_id / "config.json", checkout / "batch-runner/pilot-run.json"):
            _require(hashlib.sha256(_bytes(config, limit=MAX_RECORD_BYTES)).hexdigest() == config_sha,
                     "config_bytes_mismatch")
        inputs = _checkpoint(root / "ci-inputs.json")
        _require(set(inputs) == {"plan_sha256", "files_sha256", "source_projection_sha256"}
                 and inputs["plan_sha256"] == pilot._digest(plan)
                 and _hash(inputs["files_sha256"]) and _hash(inputs["source_projection_sha256"]),
                 "retained_input_binding_mismatch")
        completion = ci.completion(plan, cell, execute=True, state=state, inputs=inputs, cleanup=True)
        manifest = {
            "format": FORMAT, "campaign_id": campaign, "cell_id": cell_id,
            "source_sha": source_sha, "config_sha256": config_sha, "plan_sha256": pilot._digest(plan),
            "order_sha256": pilot._digest(plan["order"]), "verified_inputs_sha256": inputs["files_sha256"],
            "host_policy_sha256": pilot._digest(ci.HOST_POLICY), "status": state["status"],
            "exit_code": state["exit_code"], "reason": completion["reason"], "timeout": completion["timeout"],
            "cleanup_confirmed": True, "accounting": state["accounting"], "receipt": completion["receipt"],
            "grade_ready": False, "grading_launched": False, "files": [], "missing": [],
        }
        files: dict[str, bytes] = {}
        path = root / cell["roles"]["result"]
        if state["result"] is None:
            # Do not adopt a late/unrecorded result or search the native workspace.
            manifest["missing"] = ["bound_inference_result", "validated_deliverables", "bound_ledger_export"]
            if completion["receipt"] is None or completion["receipt"]["usage"] is None:
                manifest["missing"].append("usage")
            return Snapshot(manifest, files, root / "cells" / cell_id)
        _require(state["result"]["path"] == cell["roles"]["result"], "result_role_mismatch")
        result_bytes = _bytes(path, limit=MAX_RECORD_BYTES, expected=state["result"])
        payload = pilot._json_object(result_bytes)
        _require(set(payload) <= RESULT_FIELDS, "unsafe_result_fields")
        _safe_record(payload)
        if "source" in payload:
            _require(payload["source"] == plan["dataset"]["repo_id"], "result_source_mismatch")
        if "summary" in payload:
            _require(type(payload["summary"]) is dict and set(payload["summary"]) <= {
                "total", "success", "error", "qa_failed", "problem_solving_cost"}, "unsafe_result_summary")
            _receipt_fields(payload["summary"].get("problem_solving_cost"))
        if "azure_ai_routes" in payload:
            pilot._same("recorded routes", canonicalize_azure_ai_routes(payload["azure_ai_routes"]), payload["azure_ai_routes"])
        _require(len(payload["results"]) == 1, "result_cell_mismatch")
        row = payload["results"][0]
        _require(set(row) <= ROW_FIELDS and not row.get("failure_evidence"), "unsafe_result_fields")
        _require(row.get("usage") is None, "unsupported_codex_usage_field")
        _receipt_fields(row.get("problem_solving_cost"))
        if payload.get("cost_ledger") is not None:
            _require(set(payload["cost_ledger"]) == {"path", "sha256"}, "unsafe_ledger_reference")
        if "observability" in row:
            from step2_run_inference import _build_execution_observability

            observed = row["observability"]
            _require(type(observed) is dict and observed.get("preprocessors", []) == [], "unsafe_result_observability")
            # The registered Codex treatment has no preprocessing or sandbox QA.
            # Reuse Step2's bounded metadata projection; refuse rather than edit.
            projected = _build_execution_observability({
                "error_category": observed.get("error_category"), "execution_metrics": observed.get("execution_metrics"),
                "codex_diagnostics": observed.get("codex"), "task_deadline": observed.get("task_deadline"),
                "budget_metrics": observed.get("budget_metrics"), "substrate_manifest": observed.get("substrate"),
            }, [])
            pilot._same("bounded Step2 observability", projected, observed)
        _require(not row.get("error") or row["error"] == public_task_error_text(row["error"]),
                 "unsafe_result_error")
        records = row.get("deliverable_file_records", [])
        _require(type(records) is list and len(records) <= MAX_FILES, "payload_file_count_exceeded")
        # Pre-bound all reads before the existing current-byte/result checks.
        files["step2_inference_results.json"] = result_bytes
        roles = {"step2_inference_results.json": "inference_result"}
        for record in records:
            relative = record["path"]
            _require(canonical_deliverable_path(cell["task_id"], relative) == relative, "deliverable_role_refused")
            _require(not {part.lower() for part in Path(relative).parts} & {
                "codex_home", "auth.json", "credentials.json", "transcript.jsonl", "native-transcript.jsonl",
            } and Path(relative).suffix.lower() not in {".sqlite", ".sqlite3"}, "private_state_file_refused")
            _require(relative not in files, "duplicate_payload_path")
            files[relative] = _bytes(checkout / "batch-runner/workspace/upload" / relative,
                                     limit=MAX_FILE_BYTES, expected=record)
            roles[relative] = "generated_deliverable"
            _require(sum(map(len, files.values())) <= MAX_TOTAL_BYTES, "payload_bytes_exceeded")
        ledger = state["artifacts"].get("ledger")
        if ledger is not None:
            _require(ledger["path"] == cell["roles"]["ledger"], "ledger_role_mismatch")
            data = _bytes(root / cell["roles"]["ledger"], limit=MAX_RECORD_BYTES, expected=ledger)
            _ledger(data, cell)
            name = Path(pilot.LEDGER).name
            files[name], roles[name] = data, "cost_ledger_export"
        else:
            manifest["missing"].append("bound_ledger_export")
        checked = copy.deepcopy(state)
        pilot._finish(root, cell, checked, state["exit_code"])
        # _finish's status/reason updates are NOT publication authority. Keep the
        # original outcome, including stopped cells and missing/partial usage.
        for key in ("result", "receipt", "accounting", "artifacts"):
            pilot._same("retained output evidence", checked[key], state[key])
        if completion["receipt"] is None or completion["receipt"]["usage"] is None:
            manifest["missing"].append("usage")
        _require(sum(map(len, files.values())) <= MAX_TOTAL_BYTES, "payload_bytes_exceeded")
        manifest["files"] = [{"role": roles[name], "path": name, **pilot._identity(data)}
                             for name, data in sorted(files.items())]
        _require(len(pilot._canonical_json(manifest).encode()) <= MAX_MANIFEST_BYTES, "manifest_bytes_exceeded")
        return Snapshot(manifest, files, root / "cells" / cell_id)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    _require(remaining > 0, "publication_timeout")
    return min(REQUEST_SECONDS, remaining)


@contextmanager
def _hf_client(token: str, deadline: float, *, metadata_repo: str | None = None,
               observation: dict | None = None):
    """Scoped supported HF client hook: bounded HTTP, terminal failures, no Xet.

    Buffered immutable operations select the SDK's HTTP/LFS path. Responses and
    transport errors become our exception BEFORE SDK http_backoff can retry or
    log URLs. This does not promise one HTTP request for a multipart commit.
    The optional metadata mode permits only one exact GET, never a redirect.
    """
    import httpx
    from huggingface_hub import HfApi, constants
    from huggingface_hub.utils import _http, are_progress_bars_disabled, disable_progress_bars, enable_progress_bars

    _require(not constants.HF_HUB_OFFLINE, "hf_offline_mode")
    metadata_attempts = 0  # Shared even if the SDK recreates a client/transport.

    class Stream(httpx.SyncByteStream):
        def __init__(self, stream, status):
            self.stream, self.status = stream, status

        def __iter__(self):
            size = 0
            try:
                for chunk in self.stream:
                    _remaining(deadline)
                    size += len(chunk)
                    _require(size <= MAX_RECORD_BYTES, "hf_response_bytes_exceeded")
                    yield chunk
            except httpx.TransportError as error:
                raise OutputPublicationRefused("hf_transport_failed", self.status) from error

        def close(self):
            self.stream.close()

    class Once(httpx.BaseTransport):
        def __init__(self):
            self.transport = httpx.HTTPTransport(retries=0, trust_env=False)

        def handle_request(self, request):
            nonlocal metadata_attempts
            if metadata_repo is not None:
                expected = f"{HF_ENDPOINT}/api/datasets/{metadata_repo}/revision/main"
                _require(observation is not None and metadata_attempts == 0
                         and request.method == "GET" and str(request.url) == expected,
                         "hf_metadata_request_refused")
                metadata_attempts += 1
            _require(request.url.scheme == "https", "hf_insecure_request_refused")
            _require(request.url.host == "huggingface.co" or request.headers.get("authorization") != "Bearer " + token,
                     "hf_credential_forwarding_refused")
            request.extensions["timeout"] = {key: _remaining(deadline) for key in ("connect", "read", "write", "pool")}
            try:
                response = self.transport.handle_request(request)
            except httpx.TransportError as error:
                raise OutputPublicationRefused("hf_transport_failed") from error
            if metadata_repo is not None:
                observation["http_status"] = response.status_code
                if response.status_code != 200:
                    status = response.status_code
                    response.close()
                    reason = ("hf_http_failed" if status >= 400 else "hf_metadata_redirect_refused"
                              if 300 <= status < 400 else "hf_metadata_response_refused")
                    raise OutputPublicationRefused(reason, status)
            if response.status_code >= 400:
                status = response.status_code
                response.close()
                raise OutputPublicationRefused("hf_http_failed", status)
            response.stream = Stream(response.stream, response.status_code)
            return response

        def close(self):
            self.transport.close()

    old_factory, old_logging = _http._GLOBAL_CLIENT_FACTORY, logging.root.manager.disable
    progress_disabled = are_progress_bars_disabled()
    try:
        logging.disable(logging.CRITICAL)
        disable_progress_bars()
        _http.set_client_factory(lambda: httpx.Client(transport=Once(), timeout=REQUEST_SECONDS,
                                                    follow_redirects=metadata_repo is None, trust_env=False))
        yield HfApi(endpoint=HF_ENDPOINT, token=token)
    finally:
        _http.set_client_factory(old_factory)
        logging.disable(old_logging)
        if not progress_disabled:
            enable_progress_bars()


@contextmanager
def _time_bound(seconds: int = PUBLICATION_SECONDS):
    _require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0), "existing_timer_refused")
    previous = {name: signal.getsignal(name) for name in (signal.SIGALRM, signal.SIGTERM)}

    def stop(signum, frame):
        raise OutputPublicationRefused("publication_timeout" if signum == signal.SIGALRM else "publication_interrupted")

    try:
        for name in previous:
            signal.signal(name, stop)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield time.monotonic() + seconds
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for name, handler in previous.items():
            signal.signal(name, handler)


def _metadata(api, repo: str, revision: str, token: str, deadline: float) -> dict:
    observed = api.repo_info(repo_id=repo, repo_type="dataset", revision=revision, token=token,
                             timeout=_remaining(deadline))
    _require(getattr(observed, "id", None) == repo and getattr(observed, "private", None) is True,
             "existing_exact_private_repository_required")
    sha = getattr(observed, "sha", None)
    _require(_hash(sha, 40), "repository_revision_unavailable")
    return {"id": repo, "private": True, "sha": sha}


def _error_context(error: BaseException) -> tuple[str, int | None]:
    # SDK LFS wrappers may wrap the terminal transport error. Never print their
    # messages, which can contain a payload path, request URL or response body.
    for _ in range(8):
        if isinstance(error, OutputPublicationRefused):
            return str(error), error.http_status
        if error.__cause__ is None:
            break
        error = error.__cause__
    return ("publication_interrupted" if isinstance(error, KeyboardInterrupt) else "hf_operation_failed", None)


def inspect_output_target() -> dict:
    """One fixed candidate's metadata, not destination approval or write access.

    Called only by the explicitly selected CI mode, before any dispatch/input
    admission. No token lookup occurs in the ordinary plan path. The public
    projection never includes the operational repository locator or raw errors.
    """
    observed = {
        "role": "exp033_submission_result", "repository_name_sha256": OUTPUT_TARGET_REPO_SHA256,
        "exact_identity_match": False, "private": None, "head": None, "http_status": None,
        "observed_at": None, "eligible_private_target": False, "write_access": "not_established",
        "publication_authorized": False, "model_requested": False, "reason": None,
    }
    try:
        repo = pilot.load_plan(pilot.ROOT / pilot.CODEX_TEMPLATE)["data"]["source"]
        _require(type(repo) is str and hashlib.sha256(repo.encode()).hexdigest() == OUTPUT_TARGET_REPO_SHA256,
                 "registered_output_target_mismatch")
        _require(validate_hf_dataset_repo_id(repo) == repo, "registered_output_target_mismatch")
        token = os.environ.get("HF_TOKEN", "")
        _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
                 "explicit_hf_token_required")
        # Reuse the existing reversible environment scope, not an intake call.
        from codex_ci_input_intake import _hf_environment

        with _time_bound(TARGET_CHECK_SECONDS) as deadline, _hf_environment(online=True):
            with _hf_client(token, deadline, metadata_repo=repo, observation=observed) as api:
                metadata = api.repo_info(repo_id=repo, repo_type="dataset", revision="main", token=token,
                                         timeout=_remaining(deadline))
                _require(getattr(metadata, "id", None) == repo, "output_target_identity_mismatch")
                observed["exact_identity_match"] = True
                private, head = getattr(metadata, "private", None), getattr(metadata, "sha", None)
                observed["private"] = private if type(private) is bool else None
                observed["head"] = head if _hash(head, 40) else None
                _require(type(private) is bool, "output_target_privacy_unavailable")
                _require(observed["head"] is not None, "output_target_head_unavailable")
                _require(private is True, "private_output_target_required")
                _remaining(deadline)
                observed["eligible_private_target"] = True
    except (Exception, KeyboardInterrupt) as error:
        reason, _ = _error_context(error)
        observed["reason"] = ({"publication_timeout": "output_target_check_timeout",
                               "publication_interrupted": "output_target_check_interrupted"}.get(reason)
                              or (reason if reason in TARGET_CHECK_REASONS else "output_target_check_failed"))
        observed["eligible_private_target"] = False
    observed["observed_at"] = datetime.now(timezone.utc).isoformat()
    return observed


def publish(snapshot: Snapshot, *, repo: str, expected_parent: str, _test_api=None) -> dict:
    """One reservation and one CAS commit; never reconcile/retry a lost reply."""
    _require(bool(snapshot.files), "bound_inference_result_required")
    _require(validate_hf_dataset_repo_id(repo) == repo and _hash(expected_parent, 40), "explicit_target_parent_required")
    reservation, receipt_path = snapshot.cell_root / RESERVATION, snapshot.cell_root / RECEIPT
    _require(not os.path.lexists(reservation) and not os.path.lexists(receipt_path), "publication_already_reserved")
    token = os.environ.get("HF_TOKEN", "")
    _require(bool(token) and len(token) <= 4096 and all(33 <= ord(char) <= 126 for char in token),
             "explicit_hf_token_required")
    manifest_bytes = (pilot._canonical_json(snapshot.manifest) + "\n").encode()
    prefix = f"cell-outputs/{snapshot.manifest['campaign_id']}/{snapshot.manifest['cell_id']}"
    attempt = {"format": FORMAT, "outcome": "unresolved", "output_repository": repo,
               "expected_parent": expected_parent, "prefix": prefix, "manifest": pilot._identity(manifest_bytes),
               "cell": snapshot.manifest, "returned_commit": None, "grade_ready": False}
    _write_no_clobber(reservation, (pilot._canonical_json(attempt) + "\n").encode())
    _fsync_directory(snapshot.cell_root)
    stage, returned, before, after = "target_metadata", None, None, None
    outcome, reason, status = "unresolved", None, None
    try:
        with _time_bound() as deadline:
            from contextlib import nullcontext
            from huggingface_hub import RepoFolder

            with (nullcontext(_test_api) if _test_api is not None else _hf_client(token, deadline)) as api:
                before = _metadata(api, repo, "main", token, deadline)
                _require(before["sha"] == expected_parent, "publication_parent_changed")
                stage = "prefix_check"
                ancestors = ["cell-outputs", prefix.rsplit("/", 1)[0]]
                paths = api.get_paths_info(repo_id=repo, repo_type="dataset", revision=expected_parent,
                                          paths=[*ancestors, prefix], token=token)
                _require(type(paths) is list and len(paths) <= len(ancestors), "output_prefix_exists")
                seen = set()
                for path in paths:
                    name = getattr(path, "path", None)
                    _require(isinstance(path, RepoFolder) and name in ancestors and name not in seen,
                             "output_prefix_or_ancestor_refused")
                    seen.add(name)
                staged = tuple(_PublicationFile(prefix + "/" + name, io.BytesIO(data), len(data),
                                                hashlib.sha256(data).hexdigest())
                               for name, data in {**snapshot.files, MANIFEST: manifest_bytes}.items())
                try:
                    stage = "commit"
                    _remaining(deadline)
                    operations = _publication_additions(staged)
                    response = api.create_commit(repo_id=repo, repo_type="dataset", revision="main", token=token,
                        parent_commit=expected_parent, operations=operations,
                        commit_message="Preserve one private pilot cell output", num_threads=1, run_as_future=False,
                        create_pr=False)
                    candidate = getattr(response, "oid", None)
                    if _hash(candidate, 40):
                        returned = candidate
                    _require(returned is not None and returned != expected_parent, "commit_identity_unavailable")
                    _require(not any(getattr(operation, "_should_ignore", False)
                                     for operation in operations), "payload_ignored")
                    stage = "commit_metadata"
                    after = _metadata(api, repo, returned, token, deadline)
                    _require(after["sha"] == returned, "returned_commit_metadata_mismatch")
                    _remaining(deadline)
                    outcome = "acknowledged"
                finally:
                    for record in staged:
                        record.stream.close()
    except (Exception, KeyboardInterrupt) as error:
        reason, status = _error_context(error)
        # Once create_commit starts, a lost/failed response can hide uploaded
        # objects or a commit. Do not replace that uncertainty with a new HEAD.
        outcome = "refused" if stage in {"target_metadata", "prefix_check"} else "unresolved"
        if reason in {"publication_interrupted", "publication_timeout"}:
            outcome = "unresolved"
    receipt = {**attempt, "outcome": outcome, "stage": stage, "reason": reason, "http_status": status,
               "returned_commit": returned, "repository_before": before, "repository_at_commit": after,
               "privacy_atomic_with_commit": False, "download_verified": False}
    # A failed receipt write leaves the original unresolved reservation. No
    # replacement, alternate receipt, or replay is available.
    _write_no_clobber(receipt_path, (pilot._canonical_json(receipt) + "\n").encode())
    _fsync_directory(snapshot.cell_root)
    return receipt


def main(argv: list[str] | None = None, *, _test_api=None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--cell", required=True)
    parser.add_argument("--reviewed-source-sha", required=True)
    parser.add_argument("--expected-config-sha256", required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--output-repo")
    parser.add_argument("--expected-parent")
    try:
        args = parser.parse_args(argv)
        _require((args.publish and bool(args.output_repo) and bool(args.expected_parent))
                 or (not args.publish and args.output_repo is None and args.expected_parent is None),
                 "explicit_publication_target_parent_required")
        snapshot = prepare(root=args.campaign_root, campaign=args.campaign_id, cell_id=args.cell,
                           source_sha=args.reviewed_source_sha, config_sha=args.expected_config_sha256)
        receipt = publish(snapshot, repo=args.output_repo, expected_parent=args.expected_parent,
                          _test_api=_test_api) if args.publish else None
        result = {"format": FORMAT, "mode": "publish" if args.publish else "plan",
                  "campaign_id": args.campaign_id, "cell_id": args.cell, "status": snapshot.manifest["status"],
                  "grade_ready": False, "workflow_wired": False, "can_publish": bool(snapshot.files),
                  "missing": snapshot.manifest["missing"], "accounting": snapshot.manifest["accounting"],
                  "files": [{key: record[key] for key in ("role", "size", "sha256")}
                            for record in snapshot.manifest["files"]],
                  "publication_outcome": None if receipt is None else receipt["outcome"],
                  "stage": None if receipt is None else receipt["stage"],
                  "http_status": None if receipt is None else receipt["http_status"],
                  "reason": None if receipt is None else receipt["reason"],
                  "private_receipt_written": receipt is not None}
        print(pilot._canonical_json(result))
        return 0 if receipt is None or receipt["outcome"] == "acknowledged" else 2
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        reason = str(error) if isinstance(error, OutputPublicationRefused) else "private_cell_output_refused"
        print("Private cell output refused: " + reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
