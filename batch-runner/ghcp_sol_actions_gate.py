"""Model-free Actions plan/capture rehearsal; no GHCP, Codex or grader client."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import stat
import threading
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from time import monotonic

from core.execution_envelope_tasks import (
    CATALOG_PATH,
    TaskCatalog,
    select_advance_check_tasks,
)

CATALOG_SHA256 = "5f1eca853979b2b4efe6c6ba656545c3a416da920e3faf067d52f5d8ac4ae0eb"
TASK_IDS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
)
REQUESTED = {
    "provider": "GitHub Copilot",
    "model": "GPT-5.6 Sol",
    "harness": "Codex agent",
    "reasoning": "Max",
    "context": "1M",
    "context_tokens": 1_000_000,
}
PRIVATE_PATHS = {
    "transcript": "private/transcript.jsonl",
    "tool_calls": "private/tool-calls.jsonl",
    "commands": "private/commands.jsonl",
    "input_file_hashes": "private/input-file-hashes.json",
    "output_file_hashes": "private/output-file-hashes.json",
    "exit_status": "private/exit-status.json",
    "files": "private/files",
}
SOL_MODEL = "gpt-5.6-sol"
EFFORTS = frozenset({"none", "minimal", "low", "medium", "high", "xhigh", "max"})
# Parser bounds, not permission for this many calls or any paid execution.
MAX_EVENT_BYTES = 1_048_576
MAX_EVENT_LINE_BYTES = 65_536
MAX_EVENTS = 4096
# Existing Actions draft values, not the separate native pilot's caps and not
# paid approval. The inert VM plan still has no approved execution limits.
PROPOSED_TASK_TIMEOUT_SECONDS = 1200
PROPOSED_TASK_MAX_TURNS = 64
COLLECTION_REASONS = frozenset({
    "task_timeout_exceeded", "task_timeout_guard_unavailable",
    "turn_cap_exceeded", "turn_count_unverified",
})
SELECTION_REASONS = frozenset({
    "auto_model_refused", "model_selection_refused", "custom_provider_refused",
    "model_selection_unverified", "provider_configuration_unverified",
})


class GateRefused(ValueError):
    """Only program-selected codes cross the CLI boundary."""

    def __init__(self, code):
        self.code = code if type(code) is str and code in SELECTION_REASONS else "model_selection_unverified"
        super().__init__(self.code)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "ghcp_sol_dry_capture_refused\n")


def check_selection(
    model: str = SOL_MODEL, *, byok: bool = False, provider_config=None,
) -> None:
    """Refuse alternate routing before catalogue, capture or event reads.

    Inspect environment *names*, never credential values or config contents.
    Even an empty provider registry is refused, rather than read to prove safety.
    """
    if isinstance(model, str) and model.strip().lower() == "auto":
        raise GateRefused("auto_model_refused")
    if model != SOL_MODEL:
        raise GateRefused("model_selection_refused")
    if byok or provider_config is not None or any(
        name.startswith("COPILOT_PROVIDER_") or name == "COPILOT_PROVIDERS_CONFIG"
        for name in os.environ
    ):
        raise GateRefused("custom_provider_refused")
    if "COPILOT_MODEL" in os.environ:
        # Do not resolve an inherited selection or silently override Auto.
        raise GateRefused("model_selection_unverified")
    if "COPILOT_HOME" in os.environ:
        # Do not follow an uninspected user configuration override.
        raise GateRefused("provider_configuration_unverified")
    try:
        config_dir = Path.home() / ".copilot"
        if config_dir.is_symlink():
            raise GateRefused("provider_configuration_unverified")
        (config_dir / "providers.json").lstat()
    except FileNotFoundError:
        return
    except (OSError, RuntimeError):
        raise GateRefused("provider_configuration_unverified") from None
    raise GateRefused("custom_provider_refused")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_event_key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("nonfinite_event_value")


def read_session_events(path: Path) -> Iterable[dict]:
    """Read an explicitly supplied, bounded JSONL stream, never a session cache."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_EVENT_BYTES:
            raise ValueError("event_stream_refused")
        total = 0
        while line := stream.readline(MAX_EVENT_LINE_BYTES + 1):
            total += len(line)
            if len(line) > MAX_EVENT_LINE_BYTES or total > MAX_EVENT_BYTES:
                raise ValueError("event_stream_refused")
            yield json.loads(
                line, object_pairs_hook=_unique_object, parse_constant=_invalid_constant,
            )


def _token_limit(value):
    # No strings, booleans, fractional/NaN values or unbounded integers.
    return value if type(value) is int and 0 < value <= 2**31 - 1 else None


# These are reported numeric fields, not a conversion to invoices or native
# request counts. Unknown keys (including files, prompts and headers) stay out.
USAGE_FIELDS = frozenset({
    "inputTokens", "outputTokens", "totalTokens", "cachedInputTokens",
    "cacheReadTokens", "cacheWriteTokens", "promptTokens", "completionTokens",
    "input_tokens", "output_tokens", "total_tokens", "cached_tokens",
    "premiumRequests", "totalPremiumRequests", "requests", "cost", "totalCost",
})


def reported_usage(value):
    """Copy consumption fields, not duration-only diagnostics or estimated usage."""
    if type(value) is not dict:
        return None
    fields = {
        key: number for key, number in value.items()
        if key in USAGE_FIELDS and type(number) in (int, float)
        and 0 <= number <= 2**53 and number == number
    }
    return fields or None


def observed_model_label(value):
    """Retain public-shaped model labels, never arbitrary error/private text."""
    if (type(value) is str and len(value) <= 96
            and re.fullmatch(r"(?:gpt-|claude-|gemini-|o[1-9](?:-|$))[a-z0-9.-]*", value)):
        return value
    return None


class _CollectionRefused(ValueError):
    def __init__(self, code):
        self.code = code if code in COLLECTION_REASONS else "task_timeout_guard_unavailable"
        super().__init__(self.code)


def _check_deadline(deadline):
    if monotonic() >= deadline:
        raise _CollectionRefused("task_timeout_exceeded")


@contextmanager
def _collection_timer(deadline):
    """Interrupt even a blocked local iterator; do not replace another timer.

    The hosted target is Linux. Unsupported embedding (including a worker
    thread or an already-owned timer) refuses before reading any events.
    This does not supervise a GHCP process: this route never starts one.
    """
    if (threading.current_thread() is not threading.main_thread()
            or not hasattr(signal, "setitimer") or not hasattr(signal, "ITIMER_REAL")
            or any(signal.getitimer(signal.ITIMER_REAL))):
        raise _CollectionRefused("task_timeout_guard_unavailable")
    _check_deadline(deadline)
    previous = signal.getsignal(signal.SIGALRM)

    def expired(signum, frame):
        raise _CollectionRefused("task_timeout_exceeded")

    signal.signal(signal.SIGALRM, expired)
    try:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise _CollectionRefused("task_timeout_exceeded")
        signal.setitimer(signal.ITIMER_REAL, remaining)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _bounded_session_events(events, limits):
    """Stop this capture, not a historical task, at the existing draft caps.

    Count documented assistant.turn_start events, including sub-agents; usage
    events and native requests are different units. Never use event timestamps
    to reset the clock or accept a claim of historical runtime enforcement.
    """
    deadline = monotonic() + PROPOSED_TASK_TIMEOUT_SECONDS
    seen_turns = set()
    with _collection_timer(deadline):
        iterator = iter(events)
        try:
            while True:
                _check_deadline(deadline)
                try:
                    event = next(iterator)
                except StopIteration:
                    _check_deadline(deadline)
                    break
                _check_deadline(deadline)
                if type(event) is dict and event.get("type") == "assistant.turn_start":
                    data = event.get("data")
                    turn = data.get("turnId") if type(data) is dict else None
                    agent = event.get("agentId")
                    if (type(turn) is not str or not 0 < len(turn) <= 256
                            or (agent is not None and (type(agent) is not str or not 0 < len(agent) <= 256))
                            or (agent, turn) in seen_turns):
                        raise _CollectionRefused("turn_count_unverified")
                    seen_turns.add((agent, turn))
                    limits["observed_turn_starts"] += 1
                    if limits["observed_turn_starts"] > PROPOSED_TASK_MAX_TURNS:
                        raise _CollectionRefused("turn_cap_exceeded")
                yield event
                _check_deadline(deadline)
        finally:
            # Closing the explicit file generator also releases its descriptor
            # on cap, parser or settings failures. No child process is launched.
            try:
                close = getattr(iterator, "close", None)
                if close is not None:
                    close()
                limits["event_stream_cleanup"] = "closed" if close is not None else "not_needed"
            except _CollectionRefused:
                limits["event_stream_cleanup"] = "failed"
                raise
            except Exception:
                limits["event_stream_cleanup"] = "failed"


def collect_session_events(events: Iterable[dict] | None, *, runtime_projection=False) -> dict:
    """Project the documented JSON event envelope; never retain raw events.

    assistant.usage has per-call model/effort, not a per-call context window.
    A preceding session.usage_info snapshot stays labelled as session metadata.
    This is not a GHCP client, native-request counter or completeness proof.
    """
    receipt = {
        "status": "not_collected",
        "reason_codes": [],
        "calls": [],
        "observed_usage_events": 0,
        "count_semantics": "supplied_assistant_usage_events_not_native_requests",
        "evidence_level": "settings_only",
        "applied_settings_verified": False,
        "live_source_verified": False,
        "stream_completeness_verified": False,
        "paid_execution_allowed": False,
        "retry_allowed": False,
        "collection_limits": {
            "scope": "offline_collection_not_live_task_execution",
            "timeout_seconds": PROPOSED_TASK_TIMEOUT_SECONDS,
            "max_turns": PROPOSED_TASK_MAX_TURNS,
            "max_tool_calls": None,
            "tool_call_cap_status": "value_not_defined",
            "observed_turn_starts": 0,
            "turn_count_semantics": "supplied_assistant_turn_start_events_not_native_requests",
            "event_stream_cleanup": "not_opened",
            "live_enforcement_verified": False,
            "subprocess_cleanup": "not_applicable_no_subprocess_started",
        },
    }
    if events is None:
        return receipt
    if runtime_projection:
        receipt["context_observations"] = []
    reasons = receipt["reason_codes"]
    contexts = {}
    seen_calls = set()
    previous = None
    session_started = False
    bounded = _bounded_session_events(events, receipt["collection_limits"])
    try:
        for index, event in enumerate(bounded, 1):
            if index > MAX_EVENTS or type(event) is not dict:
                raise ValueError("event_stream_refused")
            kind = event.get("type")
            if not isinstance(kind, str) or not isinstance(event.get("data"), dict):
                raise ValueError("event_stream_refused")
            if kind == "session.resume" or (
                kind == "session.start" and (session_started or contexts or receipt["calls"])
            ):
                raise ValueError("event_stream_refused")
            if kind == "session.start":
                session_started = True
            if kind not in {"assistant.usage", "session.usage_info"}:
                # Prompts, messages, tools, headers and error text are not projected.
                continue
            agent = event.get("agentId")
            if agent is not None and (type(agent) is not str or not 0 < len(agent) <= 256):
                raise ValueError("event_stream_refused")
            data = event["data"]
            if kind == "session.usage_info":
                token_limit = _token_limit(data.get("tokenLimit"))
                context_window = _token_limit(data.get("modelContextWindow")) if runtime_projection else None
                invalid = runtime_projection and any(
                    field in data and _token_limit(data[field]) is None
                    for field in ("tokenLimit", "modelContextWindow")
                )
                conflict = invalid or (token_limit is not None and context_window is not None
                                       and token_limit != context_window)
                contexts[agent] = (
                    None if conflict else token_limit if token_limit is not None else context_window,
                    index,
                    {"tokenLimit": token_limit, "modelContextWindow": context_window},
                    conflict,
                )
                if runtime_projection:
                    receipt["context_observations"].append({
                        "event_index": index, "tokenLimit": token_limit,
                        "modelContextWindow": context_window,
                        "verification": "verified" if not conflict and contexts[agent][0] == 1_000_000 else "unverified",
                        "source": "session.usage_info.data_not_provider_attestation",
                    })
                continue
            call_reasons = []
            identity = event.get("id")
            if type(identity) is not str or not 0 < len(identity) <= 256:
                call_reasons.append("session_event_identity_unverified")
            elif identity in seen_calls:
                call_reasons.append("session_event_duplicate")
            else:
                seen_calls.add(identity)
            unbound_subagent = agent is None and (
                data.get("initiator") == "sub-agent" or data.get("parentToolCallId") is not None
            )
            if unbound_subagent:
                call_reasons.append("session_event_identity_unverified")
            raw_model = data.get("model")
            model = SOL_MODEL if raw_model == SOL_MODEL else None
            if type(raw_model) is not str or not raw_model:
                call_reasons.append("served_model_unverified")
            elif model is None:
                call_reasons.append("served_model_mismatch")
            raw_effort = data.get("reasoningEffort")
            effort = raw_effort if type(raw_effort) is str and raw_effort in EFFORTS else None
            if effort is None:
                call_reasons.append("reasoning_effort_unverified")
            elif effort != "max":
                call_reasons.append("reasoning_effort_mismatch")
            limit, context_index, context_fields, context_conflict = (
                (None, None, {"tokenLimit": None, "modelContextWindow": None}, False)
                if unbound_subagent else contexts.get(
                    agent, (None, None, {"tokenLimit": None, "modelContextWindow": None}, False),
                )
            )
            if context_conflict:
                call_reasons.append("context_metadata_conflict")
            if limit is None:
                call_reasons.append("context_limit_unverified")
            elif limit != REQUESTED["context_tokens"]:
                call_reasons.append("context_limit_mismatch")
            values = (model, effort, limit)
            if previous is not None and values != previous:
                call_reasons.append("call_metadata_conflict")
            previous = values
            receipt["calls"].append({
                "call_index": len(receipt["calls"]) + 1,
                "event_index": index,
                "agent_scope": "unbound_subagent" if unbound_subagent else "main" if agent is None else "subagent",
                # Only Sol is public-allowlisted. Other arbitrary model strings
                # become null + mismatch, never a possible secret or endpoint.
                "model": model,
                "reasoningEffort": effort,
                "tokenLimit": limit,
                "modelContextWindow": None,
                "context_event_index": context_index,
                "context_binding": "preceding_same_agent_session_snapshot_not_call_attestation",
                "modelContextWindow_status": "not_in_documented_ghcp_event_contract",
                "reason_codes": call_reasons,
            })
            if runtime_projection:
                # Raw allowlisted fields remain separate from the legacy
                # normalized projection. Session context is not a per-call
                # provider attestation; never backfill from requested flags.
                receipt["calls"][-1].update({
                    "observed_fields": {
                        "model": observed_model_label(raw_model),
                        "reasoningEffort": effort,
                        **context_fields,
                    },
                    "field_sources": {
                        "model": "assistant.usage.data.model",
                        "reasoningEffort": "assistant.usage.data.reasoningEffort",
                        "context": "preceding_same_agent_session.usage_info.data",
                    },
                    "verification": "unverified" if call_reasons else "verified",
                    "verification_scope": "event_fields_match_requested_not_provider_attestation",
                    "usage": reported_usage(data),
                    "usage_status": "reported" if reported_usage(data) is not None else "not available",
                })
            for reason in call_reasons:
                if reason not in reasons:
                    reasons.append(reason)
            if runtime_projection and call_reasons:
                # The live supervisor's finally block terminates the owned
                # process group as soon as a required field is unverified.
                break
    except _CollectionRefused as error:
        reasons.append(error.code)
    except Exception:
        # No exception text/args, paths, event bodies or partial raw JSON escape.
        if "session_event_stream_refused" not in reasons:
            reasons.append("session_event_stream_refused")
    finally:
        try:
            bounded.close()
        except _CollectionRefused as error:
            if error.code not in reasons:
                reasons.append(error.code)
    if receipt["collection_limits"]["event_stream_cleanup"] == "failed":
        reasons.append("session_event_cleanup_refused")
    receipt["observed_usage_events"] = len(receipt["calls"])
    if not receipt["calls"]:
        reasons.extend([
            "served_model_unverified", "reasoning_effort_unverified", "context_limit_unverified",
        ])
    receipt["status"] = "failed" if reasons else "consistent_settings_only"
    return receipt


def fixed_task_ids() -> tuple[str, ...]:
    """Re-derive the cohort from the pinned score-free public catalogue."""
    data = CATALOG_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != CATALOG_SHA256:
        raise ValueError("public_catalog_identity_refused")
    catalog = TaskCatalog.from_mapping(json.loads(data))
    selected = select_advance_check_tasks(catalog, catalog_fingerprint=CATALOG_SHA256)
    if selected.task_ids != TASK_IDS:
        raise ValueError("fixed_cohort_refused")
    return selected.task_ids


def capture_envelope(task_id: str, *, session_events: Iterable[dict] | None = None) -> dict:
    """Construct constants plus the closed event projection, never raw captures."""
    evidence = collect_session_events(session_events)
    failed = evidence["status"] == "failed"
    return {
        "schema_version": "ghcp-sol-actions-dry-capture-v1",
        "task_id": task_id,
        "cohort": "advance_check_5",
        "catalog_sha256": CATALOG_SHA256,
        "status": "failed" if failed else "dry_run_only",
        "paid_execution_allowed": False,
        "model_calls": 0,
        "grader_calls": 0,
        "requested": dict(REQUESTED),
        "actual_served": {key: "not available" for key in REQUESTED},
        "session_event_receipt": evidence,
        "versions": {
            "python": platform.python_version(),
            "os": platform.system(),
            "kernel": platform.release(),
            "ghcp_cli": "not available",
            "codex_cli": "not available",
            "codex_sdk": "not available",
        },
        "execution_target": "GitHub Actions standard runner ubuntu-24.04",
        "target_observed": False,
        "limits": {
            "proposed_paid_timeout_seconds_per_task": PROPOSED_TASK_TIMEOUT_SECONDS,
            "proposed_paid_max_turns_per_task": PROPOSED_TASK_MAX_TURNS,
            "proposed_paid_max_tool_calls_per_task": None,
            "proposed_paid_retries": 0,
            "paid_limits_approved_or_verified": False,
            "workflow_dry_run_process_timeout_seconds": 60,
            "workflow_dry_run_job_timeout_minutes": 5,
            "dry_run_max_model_turns": 0,
        },
        "capture": {
            "private_task_relative_paths": dict(PRIVATE_PATHS),
            "path_semantics": "relative_to_task_state_not_host_paths",
            "raw_capture_status": "empty_dry_run_placeholders_not_model_evidence",
            "private_inputs_read": False,
            "files_captured": 0,
            "artifact_allowlist": ["capture.json"],
            "private_capture_upload_allowed": False,
            "log_policy": "static_status_only_no_inputs_environment_or_raw_streams",
        },
        "exit_status": 2 if failed else 0,
        "usage": None,
        "usage_status": "not available",
        "usage_reason": "native_ghcp_usage_not_collected",
        "cost": None,
        "cost_status": "not available",
        "cost_reason": "native_ghcp_cost_not_collected",
        "grade": None,
        "evidence_boundary": "local_plan_and_empty_capture_wiring_not_hosted_or_paid_execution",
    }


def dry_capture(
    task_id: str, state_root: Path, *, session_events: Iterable[dict] | None = None,
    model: str = SOL_MODEL, byok: bool = False, provider_config=None,
) -> int:
    check_selection(model, byok=byok, provider_config=provider_config)
    if task_id not in fixed_task_ids():
        raise ValueError("fixed_task_refused")
    if not state_root.is_absolute() or state_root.is_symlink():
        raise ValueError("state_root_refused")
    state_root.mkdir(mode=0o700, exist_ok=True)
    task_root = state_root / task_id
    # Refuse reuse, including symlinks; never adopt a previous conversation.
    task_root.mkdir(mode=0o700)
    envelope = capture_envelope(task_id, session_events=session_events)
    private = task_root / "private"
    private.mkdir(mode=0o700)
    (private / "files").mkdir(mode=0o700)
    for name, relative in PRIVATE_PATHS.items():
        if name == "files":
            continue
        contents = ""
        if name.endswith("file_hashes"):
            contents = "[]\n"
        elif name == "exit_status":
            contents = json.dumps({
                "dry_run": True, "model_started": False, "exit_status": envelope["exit_status"],
            }) + "\n"
        with (task_root / relative).open("x", encoding="utf-8") as stream:
            stream.write(contents)
    with (task_root / "capture.json").open("x", encoding="utf-8") as stream:
        json.dump(envelope, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return envelope["exit_status"]


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--dry-run", choices=("true", "false"), default="true")
    parser.add_argument("--task-id", choices=TASK_IDS)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--model", default=SOL_MODEL)
    parser.add_argument("--byok", action="store_true")
    parser.add_argument("--provider-config", help="Any custom provider configuration is refused, never read")
    parser.add_argument("--session-events", type=Path, help="Explicit offline JSONL; never discovers session logs")
    args = parser.parse_args(argv)
    if args.dry_run != "true":
        parser.error("paid_execution_not_implemented_or_approved")
    try:
        check_selection(args.model, byok=args.byok, provider_config=args.provider_config)
    except GateRefused as error:
        parser.exit(2, f"{error.code}\n")
    if args.matrix:
        if args.task_id is not None or args.state_root is not None or args.session_events is not None:
            parser.error("matrix_does_not_accept_capture_arguments")
        print(json.dumps({"task_id": fixed_task_ids()}, separators=(",", ":")))
        return 0
    if args.task_id is None or args.state_root is None:
        parser.error("capture_requires_task_id_and_state_root")
    try:
        result = dry_capture(
            args.task_id, args.state_root,
            session_events=read_session_events(args.session_events) if args.session_events is not None else None,
            model=args.model, byok=args.byok, provider_config=args.provider_config,
        )
    except GateRefused as error:
        parser.exit(2, f"{error.code}\n")
    except (OSError, ValueError):
        # Paths and exception strings may contain private data. Emit a fixed error.
        parser.exit(2, "ghcp_sol_dry_capture_refused\n")
    if result:
        parser.exit(2, "ghcp_sol_session_evidence_refused\n")
    print("ghcp_sol_dry_capture_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
