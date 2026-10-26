"""Disabled-by-default supervision plus a fixed, separately enabled CLI smoke.

The caller must supply an argv and an explicit tool-call cap. JSONL start
notifications support cancellation after observation, not pre-effect admission.
The existing workflow does not call this adapter. The fixed CONNECTED smoke
uses a fresh NAS directory, not a VM, and never starts the five-task gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import selectors
import signal
import stat
import subprocess
import threading
import time
from pathlib import Path
from time import monotonic

import ghcp_sol_actions_gate as gate

POLL_SECONDS = 0.05
TERM_GRACE_SECONDS = 1.0
KILL_WAIT_SECONDS = 4.0
COPILOT_CLI_VERSION = "1.0.103"
COPILOT_CLI_SHA256 = "f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d"
SMOKE_TASK_ID = "connected-smoke"
SMOKE_ROW = "GHCP Copilot CLI agent + GPT-5.6 Sol"
SMOKE_PROMPT = "Reply with exactly CONNECTED"
SMOKE_TOOL_CALL_CAP = 32  # Leader-selected, 2026-10-26; not a VM-plan rewrite.
AUTH_ENV_NAMES = ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
MAX_USAGE_FILE_BYTES = 65_536
AUTH_MESSAGES = (
    "No authentication information found",
    "Authentication required",
    "Authentication failed",
    "Failed to authenticate",
    "not logged in",
    "not authenticated",
    "Please authenticate",
)


class _Stop(Exception):
    """Internal, program-selected refusal, never populated from child output."""

    def __init__(self, code):
        self.code = code


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # An accidentally supplied value must not be echoed as an invalid name.
        self.exit(2, "ghcp_sol_smoke_configuration_refused\n")


def auth_source_presence(environment=None):
    """Names and membership only; this diagnostic never retrieves a value."""
    environment = os.environ if environment is None else environment
    return {name: name in environment for name in AUTH_ENV_NAMES}


def _selected_auth_environment(name):
    if name is None:
        raise _Stop("auth_source_not_selected")
    if type(name) is not str or name not in AUTH_ENV_NAMES:
        raise _Stop("auth_source_not_allowed")
    if name not in os.environ:
        raise _Stop("auth_source_unavailable")
    # The selected value is consumed only for child-environment transfer and
    # in-memory leak detection, never returned as observation metadata.
    return {name: os.environ[name]}


class _CredentialGuard:
    """Ephemeral exact/JSON-escaped matching, not a general secret-store reader."""

    def __init__(self, value):
        if type(value) is not str or not value or len(value.encode("utf-8")) > 8192:
            raise _Stop("auth_source_unavailable")
        self._forms = tuple(dict.fromkeys((
            value, json.dumps(value, ensure_ascii=True)[1:-1],
            json.dumps(value, ensure_ascii=False)[1:-1],
        )))
        self._patterns = tuple(form.encode("utf-8") for form in self._forms)
        self.tail_size = max(len(pattern) for pattern in self._patterns) - 1
        self.blocked = False

    def check(self, data):
        if any(pattern in data for pattern in self._patterns):
            self.blocked = True
            raise _Stop("authentication_secret_exposure_refused")

    def clean_receipt(self, receipt):
        def clean(value):
            if type(value) is str:
                for form in self._forms:
                    value = value.replace(form, "[redacted]")
                return value
            if type(value) is list:
                return [clean(item) for item in value]
            if type(value) is dict:
                return {clean(key): clean(item) for key, item in value.items()}
            return value

        try:
            self.check(json.dumps(receipt, allow_nan=False).encode("utf-8"))
        except _Stop:
            safe = clean(receipt)
            receipt.clear()
            receipt.update(safe)
        if self.blocked:
            _reason(receipt, "authentication_secret_exposure_refused")
            receipt["diagnostic"]["stderr_sha256"] = None
            receipt["status"] = "failed" if receipt["subprocess_started"] else "refused"
            receipt["exit_status"] = 2
            receipt["settings_verification"] = "unverified"
            receipt["metadata_gate_passed"] = False


def _write_transcript(stream, line, guard):
    guard.check(line)
    stream.write(line)
    stream.flush()


def _reason(receipt, code):
    if code not in receipt["reason_codes"]:
        receipt["reason_codes"].append(code)


def _verify_copilot_binary(path):
    if not isinstance(path, Path) or not path.is_absolute():
        raise _Stop("copilot_binary_unverified")
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 512 * 1024 * 1024:
                raise _Stop("copilot_binary_unverified")
            digest = hashlib.sha256()
            total = 0
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > info.st_size:
                    raise _Stop("copilot_binary_unverified")
                digest.update(chunk)
        if digest.hexdigest() != COPILOT_CLI_SHA256:
            raise _Stop("copilot_binary_unverified")
    except OSError:
        raise _Stop("copilot_binary_unverified") from None


def _smoke_environment(private, authentication):
    """New HOME/config/cache only; never inspect or copy an existing auth store."""
    locations = {name: private / name for name in ("home", "config", "cache", "data", "state", "tmp")}
    for directory in locations.values():
        directory.mkdir(mode=0o700)
    environment = {
        "PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1",
        "HOME": str(locations["home"]), "XDG_CONFIG_HOME": str(locations["config"]),
        "XDG_CACHE_HOME": str(locations["cache"]), "XDG_DATA_HOME": str(locations["data"]),
        "XDG_STATE_HOME": str(locations["state"]), "TMPDIR": str(locations["tmp"]),
        "GH_CONFIG_DIR": str(locations["config"] / "gh"),
    }
    # Exactly one explicitly selected name, never automatic source fallback.
    environment.update(authentication)
    return environment, locations["config"]


def _smoke_command(binary, config, usage_file):
    return [
        str(binary), "--no-auto-update", "--disable-client-telemetry",
        "--config-dir", str(config), "--no-custom-instructions", "--disable-builtin-mcps",
        # Prompt mode requires autoapproval; an empty availability list hides
        # all tools. Denials also override autoapproval for shell/file writes.
        "--allow-all-tools", "--available-tools", "--deny-tool=shell", "--deny-tool=write",
        "--disallow-temp-dir", "--secret-env-vars=" + ",".join(AUTH_ENV_NAMES),
        "-p", SMOKE_PROMPT, "--model", gate.SOL_MODEL, "--reasoning-effort", "max",
        "--context", "long_context", "--output-format", "json", "--stream", "on",
        "--usage-output-file", str(usage_file),
    ]


def _observe_diagnostic(chunk, receipt):
    diagnostic = receipt.get("diagnostic")
    if diagnostic is None:
        return
    # Match static phrases only. Never retain a raw line, token, URL or user ID.
    lower = chunk.lower()
    for message in AUTH_MESSAGES:
        if message.lower().encode() in lower:
            diagnostic["message"] = message
            diagnostic["status"] = "reported_authentication_error"
            _reason(receipt, "copilot_authentication_failed")
            return


def _usage_file(path, credential_guard=None):
    try:
        if any(parent.is_symlink() for parent in path.parents):
            return None, "refused"
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_USAGE_FILE_BYTES:
                return None, "refused"
            raw = stream.read(MAX_USAGE_FILE_BYTES + 1)
        if len(raw) > MAX_USAGE_FILE_BYTES:
            return None, "refused"
        if credential_guard is not None:
            credential_guard.check(raw)
        value = json.loads(raw, object_pairs_hook=gate._unique_object, parse_constant=gate._invalid_constant)
        projected = gate.reported_usage(value)
        return projected, "reported" if projected is not None else "not available"
    except FileNotFoundError:
        return None, "not available"
    except (OSError, ValueError, UnicodeError):
        return None, "refused"


def _finish_smoke(receipt, usage_file, credential_guard=None):
    calls = receipt["session_event_receipt"]["calls"]
    receipt["observed_event_fields"] = [call["observed_fields"] for call in calls]
    receipt["observed_context_fields"] = receipt["session_event_receipt"].get("context_observations", [])
    file_usage, file_status = _usage_file(usage_file, credential_guard)
    receipt["usage_output_file_status"] = file_status
    if file_status == "refused":
        _reason(receipt, "usage_output_file_refused")
    sources = {
        "assistant.usage": [call["usage"] for call in calls if call.get("usage") is not None],
        "result.usage": receipt.pop("reported_result_usage", None),
        "usage_output_file": file_usage,
    }
    receipt["usage"] = sources if any(sources.values()) else None
    receipt["usage_status"] = "reported_not_reconciled_billing" if receipt["usage"] else "not available"
    if not receipt["cli_result"]["observed"]:
        _reason(receipt, "cli_result_unverified")
    if receipt["smoke_reply_exact"] is not True:
        _reason(receipt, "smoke_reply_unverified")
    receipt["settings_verification"] = (
        "verified" if calls and all(call.get("verification") == "verified" for call in calls)
        and not receipt["reason_codes"] else "unverified"
    )
    receipt["metadata_gate_passed"] = receipt["settings_verification"] == "verified"
    if receipt["reason_codes"]:
        receipt["status"] = "failed" if receipt["subprocess_started"] else "refused"
        receipt["exit_status"] = 2


def _receipt(task_id):
    return {
        "schema_version": "ghcp-sol-process-adapter-v1",
        "task_id": task_id if task_id in gate.TASK_IDS else None,
        "status": "refused",
        "reason_codes": [],
        "exit_status": 2,
        "subprocess_started": False,
        "subprocess_returncode": None,
        "elapsed_seconds": None,
        "event_stream_eof_observed": False,
        "cli_result": {
            "observed": False,
            "exit_code": None,
            "completion_authority": False,
            "settings_authority": False,
        },
        "limits": {
            "timeout_seconds": gate.PROPOSED_TASK_TIMEOUT_SECONDS,
            "max_turns": gate.PROPOSED_TASK_MAX_TURNS,
            "max_tool_calls": None,
            "observed_turn_starts": 0,
            "observed_tool_starts": 0,
            "count_semantics": "same_attempt_agent_scoped_start_events_not_native_requests",
        },
        "cleanup": {
            "status": "not_started",
            "signals_sent": [],
            "leader_reaped": False,
            "stdout_closed": False,
            "scope": "owned_process_group_not_escaped_sessions",
        },
        "session_event_receipt": gate.collect_session_events(None),
        "partial_files": "not_created",
        "usage": None,
        "usage_status": "not available",
        "cost": None,
        "cost_status": "not available",
        "grade": None,
        "paid_execution_allowed": False,
        "retry_allowed": False,
        "ghcp_command_binding_verified": False,
        "live_source_verified": False,
        "stream_completeness_verified": False,
        "pre_effect_limits_verified": False,
        "evidence_level": "process_supervision_and_settings_only_not_live_ghcp_proof",
    }


def _remaining(deadline):
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise _Stop("task_timeout_exceeded")
    return remaining


def _count_start(event, receipt, seen):
    kind = event["type"]
    if kind not in {"assistant.turn_start", "tool.execution_start"}:
        return
    tool = kind == "tool.execution_start"
    data = event["data"]
    identity = data.get("toolCallId" if tool else "turnId")
    agent = event.get("agentId")
    key = (agent, identity)
    if (type(identity) is not str or not 0 < len(identity) <= 256
            or (agent is not None and (type(agent) is not str or not 0 < len(agent) <= 256))
            or (agent is None and (data.get("initiator") == "sub-agent"
                                  or data.get("parentToolCallId") is not None))
            or key in seen[kind]):
        raise _Stop("tool_call_count_unverified" if tool else "turn_count_unverified")
    seen[kind].add(key)
    limits = receipt["limits"]
    field = "observed_tool_starts" if tool else "observed_turn_starts"
    limits[field] += 1
    if limits[field] > limits["max_tool_calls" if tool else "max_turns"]:
        raise _Stop("tool_call_cap_exceeded" if tool else "turn_cap_exceeded")


def _exited_without_reaping(process):
    # Keep the leader PID reserved until the whole group has been signalled.
    # Popen.poll()/wait() would reap it before descendant cleanup.
    return os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None


def _session_events(process, deadline, receipt, credential_guard=None, transcript=None):
    """Read only bounded stdout JSONL. Stderr never enters the event channel."""
    seen = {"assistant.turn_start": set(), "tool.execution_start": set()}
    total = count = 0
    pending = bytearray()
    eof = False
    session_id = None
    bound_cli = "copilot_cli" in receipt
    stderr_total = 0
    stderr_digest = hashlib.sha256()
    diagnostic_tail = b""
    stdout_tail = b""

    def decode(line):
        nonlocal count, session_id
        _remaining(deadline)
        if len(line) > gate.MAX_EVENT_LINE_BYTES:
            raise _Stop("session_event_stream_refused")
        count += 1
        if count > gate.MAX_EVENTS:
            raise _Stop("session_event_stream_refused")
        if credential_guard is not None:
            credential_guard.check(line)
        if bound_cli:
            _observe_diagnostic(line, receipt)
            if "copilot_authentication_failed" in receipt["reason_codes"]:
                raise _Stop("copilot_authentication_failed")
        event = json.loads(line, object_pairs_hook=gate._unique_object,
                           parse_constant=gate._invalid_constant)
        if (type(event) is not dict or type(event.get("type")) is not str
                or receipt["cli_result"]["observed"]):
            raise _Stop("session_event_stream_refused")
        if transcript is not None:
            _write_transcript(transcript, line, credential_guard)
        if event["type"] == "result":
            # Copilot 1.0.79 app.js:2745/2844 writes this CLI-only summary,
            # not a session event. Never project its session ID, timestamp,
            # private file list, or substitute aggregate usage for the
            # assistant.usage/session.usage_info events filtered by its CLI.
            # The new smoke may copy only allowlisted aggregate numeric fields.
            if (set(event) != {"type", "timestamp", "sessionId", "exitCode", "usage"}
                    or type(event["timestamp"]) is not str
                    or not 0 < len(event["timestamp"]) <= 64
                    or session_id is None or event["sessionId"] != session_id
                    or type(event["exitCode"]) is not int or event["exitCode"] not in (0, 1)
                    or type(event["usage"]) is not dict):
                raise _Stop("session_event_stream_refused")
            receipt["cli_result"]["observed"] = True
            receipt["cli_result"]["exit_code"] = event["exitCode"]
            if bound_cli:
                receipt["reported_result_usage"] = gate.reported_usage(event["usage"])
            if event["exitCode"] != 0:
                raise _Stop("cli_result_failed")
            _remaining(deadline)
            # Keep supervising through EOF/process exit; this is not a flush
            # barrier or permission to leave a child running after a summary.
            return None
        if type(event.get("data")) is not dict:
            raise _Stop("session_event_stream_refused")
        if event["type"] == "session.start":
            candidate = event["data"].get("sessionId")
            session_id = candidate if type(candidate) is str and 0 < len(candidate) <= 256 else None
        if bound_cli and event["type"] == "assistant.message":
            content = event["data"].get("content")
            if type(content) is str:
                receipt["smoke_reply_exact"] = content == "CONNECTED"
        _count_start(event, receipt, seen)
        _remaining(deadline)
        return event

    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ, "stdout")
            if bound_cli and process.stderr is not None:
                os.set_blocking(process.stderr.fileno(), False)
                ready.register(process.stderr, selectors.EVENT_READ, "stderr")
            while True:
                remaining = _remaining(deadline)
                if eof and not ready.get_map() and _exited_without_reaping(process):
                    _remaining(deadline)
                    return
                for key, _ in ready.select(min(remaining, POLL_SECONDS)):
                    _remaining(deadline)
                    chunk = os.read(key.fd, gate.MAX_EVENT_LINE_BYTES + 1)
                    if key.data == "stderr":
                        if not chunk:
                            ready.unregister(key.fileobj)
                            continue
                        stderr_total += len(chunk)
                        if credential_guard is not None:
                            credential_guard.check(diagnostic_tail + chunk)
                        stderr_digest.update(chunk)
                        receipt["diagnostic"]["stderr_bytes"] = stderr_total
                        receipt["diagnostic"]["stderr_sha256"] = stderr_digest.hexdigest()
                        _observe_diagnostic(diagnostic_tail + chunk, receipt)
                        tail_size = max(256, credential_guard.tail_size if credential_guard else 0)
                        diagnostic_tail = (diagnostic_tail + chunk)[-tail_size:]
                        if "copilot_authentication_failed" in receipt["reason_codes"]:
                            raise _Stop("copilot_authentication_failed")
                        if stderr_total > gate.MAX_EVENT_BYTES:
                            raise _Stop("session_error_stream_refused")
                        continue
                    if not chunk:
                        ready.unregister(process.stdout)
                        eof = True
                        receipt["event_stream_eof_observed"] = True
                        if pending:
                            event = decode(bytes(pending))
                            if event is not None:
                                yield event
                            pending.clear()
                        continue
                    total += len(chunk)
                    if total > gate.MAX_EVENT_BYTES:
                        raise _Stop("session_event_stream_refused")
                    if credential_guard is not None:
                        credential_guard.check(stdout_tail + chunk)
                        stdout_tail = ((stdout_tail + chunk)[-credential_guard.tail_size:]
                                       if credential_guard.tail_size else b"")
                    pending.extend(chunk)
                    while b"\n" in pending:
                        line, _, rest = pending.partition(b"\n")
                        pending = bytearray(rest)
                        event = decode(bytes(line) + b"\n")
                        if event is not None:
                            yield event
                    if len(pending) > gate.MAX_EVENT_LINE_BYTES:
                        raise _Stop("session_event_stream_refused")
    except _Stop as error:
        _reason(receipt, error.code)
    except gate._CollectionRefused as error:
        _reason(receipt, error.code)
    except Exception:
        _reason(receipt, "session_event_stream_refused")


def _cleanup(process, receipt):
    """TERM then KILL the owned group, even when the leader already exited.

    The five-second cleanup allowance uses real time independently of the task
    clock. Descendants that escape the group need a separately bound sandbox.
    Group signals plus leader reaping do not attest that every orphan was reaped.
    """
    cleanup = receipt["cleanup"]
    failed = False
    for signum, label in ((signal.SIGTERM, "TERM"), (signal.SIGKILL, "KILL")):
        try:
            os.killpg(process.pid, signum)
            cleanup["signals_sent"].append(label)
        except ProcessLookupError:
            pass
        except OSError:
            failed = True
        if signum == signal.SIGTERM:
            until = time.monotonic() + TERM_GRACE_SECONDS
            try:
                while not _exited_without_reaping(process):
                    remaining = until - time.monotonic()
                    if remaining <= 0:
                        break
                    threading.Event().wait(min(remaining, POLL_SECONDS))
            except OSError:
                failed = True
    try:
        receipt["subprocess_returncode"] = process.wait(timeout=KILL_WAIT_SECONDS)
        cleanup["leader_reaped"] = True
    except (OSError, subprocess.TimeoutExpired):
        failed = True
    try:
        process.stdout.close()
        cleanup["stdout_closed"] = True
    except OSError:
        failed = True
    if process.stderr is not None:
        try:
            process.stderr.close()
            cleanup["stderr_closed"] = True
        except OSError:
            failed = True
    cleanup["status"] = "failed" if failed else "group_signalled_leader_reaped"
    if failed:
        _reason(receipt, "subprocess_cleanup_failed")


def run_task(
    task_id: str, command: list[str] | tuple[str, ...], state_root: Path, *,
    execution_enabled: bool = False, execution_config: dict | None = None,
    model: str = gate.SOL_MODEL, byok: bool = False, provider_config=None,
    copilot_cli: Path | None = None, auth_source: str | None = None,
) -> dict:
    """Supervise one explicitly enabled, fresh task; return a safe receipt.

    Pre-launch refusals return metadata without making a task directory. Once
    admitted locally, reserve execution-receipt.json before spawning and retain
    private/files without copying its contents. This is not a ledger claim,
    paid permission, retry grant, model attestation or GHCP command binding.
    """
    receipt = _receipt(task_id)
    bound_cli = copilot_cli is not None
    authentication = None
    credential_guard = None
    if bound_cli:
        receipt.update({
            "task_id": SMOKE_TASK_ID if task_id == SMOKE_TASK_ID else None,
            "row_name": SMOKE_ROW,
            "execution_target": "NAS isolated directory (not a VM)",
            "copilot_cli": {"version": COPILOT_CLI_VERSION, "sha256": COPILOT_CLI_SHA256},
            "requested": {"model": gate.SOL_MODEL, "reasoningEffort": "max",
                          "context": "long_context", "tokenLimit": 1_000_000},
            "settings_verification": "unverified", "observed_event_fields": [],
            "metadata_gate_passed": False, "five_task_gate_allowed": False,
            "paid_smoke_authorized": execution_enabled is True,
            "full_220_allowed": False, "smoke_reply_exact": None,
            "diagnostic": {"status": "not available", "message": None,
                           "stderr_bytes": 0, "stderr_sha256": None},
            "evidence_level": "cli_event_settings_not_provider_attestation",
            "authentication": "inherited_supported_environment_only_no_cache_copy_or_login",
            "auth_source": None,
            "transcript": "private/transcript.jsonl",
            "transcript_scope": "adapter_owned_bounded_stdout_not_all_cli_logs",
            "isolation": "fresh_work_home_config_cache_not_a_vm_or_security_sandbox",
        })
    try:
        if execution_enabled is not True:
            raise _Stop("execution_disabled")
        if execution_config is None or (type(execution_config) is dict
                                        and execution_config.get("tool_calls_per_task") is None):
            raise _Stop("tool_call_cap_missing")
        if type(execution_config) is not dict:
            raise _Stop("tool_call_cap_invalid")
        cap = execution_config.get("tool_calls_per_task")
        if type(cap) is not int or not 0 < cap <= 2**31 - 1:
            raise _Stop("tool_call_cap_invalid")
        receipt["limits"]["max_tool_calls"] = cap
        gate.check_selection(model, byok=byok, provider_config=provider_config)
        if bound_cli and (task_id != SMOKE_TASK_ID or command or cap != SMOKE_TOOL_CALL_CAP):
            raise _Stop("copilot_smoke_scope_refused")
        if not bound_cli and task_id not in gate.fixed_task_ids():
            raise _Stop("execution_task_refused")
        if not bound_cli and (type(command) not in (list, tuple) or not command
                or any(type(arg) is not str or not arg or "\0" in arg for arg in command)
                or not Path(command[0]).is_absolute()):
            raise _Stop("execution_command_refused")
        if bound_cli:
            authentication = _selected_auth_environment(auth_source)
            credential_guard = _CredentialGuard(authentication[auth_source])
            receipt["auth_source"] = auth_source
            _verify_copilot_binary(copilot_cli)
            receipt["ghcp_command_binding_verified"] = True
        if os.name != "posix" or any(not hasattr(os, name) for name in (
                "killpg", "waitid", "WNOWAIT", "P_PID", "WEXITED", "WNOHANG")):
            raise _Stop("execution_platform_unsupported")
        if (threading.current_thread() is not threading.main_thread()
                or not hasattr(signal, "setitimer") or not hasattr(signal, "ITIMER_REAL")
                or any(signal.getitimer(signal.ITIMER_REAL))):
            raise _Stop("task_timeout_guard_unavailable")
        if not isinstance(state_root, Path) or not state_root.is_absolute():
            raise _Stop("execution_state_refused")
        if any(path.is_symlink() for path in (state_root, *state_root.parents)):
            raise _Stop("execution_state_refused")
    except (_Stop, gate.GateRefused) as error:
        _reason(receipt, error.code)
        return receipt
    except Exception:
        _reason(receipt, "execution_configuration_refused")
        return receipt

    process = None
    sink = None
    started = None
    usage_file = None
    transcript = None
    try:
        state_root.mkdir(mode=0o700, exist_ok=True)
        task_root = state_root / task_id
        task_root.mkdir(mode=0o700)  # No adoption, overwrite or local task reuse.
        private = task_root / "private"
        private.mkdir(mode=0o700)
        work = private / "files"
        work.mkdir(mode=0o700)
        sink = (task_root / "execution-receipt.json").open("x", encoding="utf-8")
        receipt["partial_files"] = "retained_private_not_uploaded"
        # The model-free command path must not fall back to the OS user's HOME
        # when testing the same fixed-task isolation boundary as the smoke.
        environment, config = _smoke_environment(private, authentication or {})
        if bound_cli:
            usage_file = private / "usage.json"
            transcript = (private / "transcript.jsonl").open("xb")
            command = _smoke_command(copilot_cli, config, usage_file)
        started = monotonic()
        deadline = started + gate.PROPOSED_TASK_TIMEOUT_SECONDS
        try:
            process = subprocess.Popen(
                list(command), cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if bound_cli else subprocess.DEVNULL,
                start_new_session=True, close_fds=True, bufsize=0,
                # All paths use fresh directories. Only the bound smoke can
                # add one explicitly selected authentication environment name.
                env=environment,
            )
        except Exception:
            raise _Stop("subprocess_start_failed") from None
        receipt["subprocess_started"] = True
        _remaining(deadline)
        evidence = gate.collect_session_events(
            _session_events(process, deadline, receipt, credential_guard, transcript),
            runtime_projection=bound_cli,
        )
        receipt["session_event_receipt"] = evidence
        for reason in evidence["reason_codes"]:
            _reason(receipt, reason)
        if evidence["calls"] and not receipt["limits"]["observed_turn_starts"]:
            _reason(receipt, "turn_count_unverified")
    except _Stop as error:
        _reason(receipt, error.code)
    except Exception:
        _reason(receipt, "execution_state_refused" if process is None else "execution_adapter_failed")
    except BaseException:
        _reason(receipt, "execution_interrupted")
        raise
    finally:
        if started is not None:
            receipt["elapsed_seconds"] = max(0.0, monotonic() - started)
        if process is not None:
            _cleanup(process, receipt)
            if receipt["subprocess_returncode"] != 0 and not receipt["reason_codes"]:
                _reason(receipt, "subprocess_exit_nonzero")
        if not receipt["reason_codes"] and process is not None:
            receipt["status"] = "completed_process_only"
            receipt["exit_status"] = 0
        elif receipt["subprocess_started"]:
            receipt["status"] = "failed"
        if bound_cli and usage_file is not None:
            try:
                _finish_smoke(receipt, usage_file, credential_guard)
            except _Stop as error:
                _reason(receipt, error.code)
                receipt["status"] = "failed"
                receipt["exit_status"] = 2
        if transcript is not None:
            try:
                transcript.close()
            except OSError:
                _reason(receipt, "transcript_close_failed")
                receipt["status"] = "failed"
                receipt["exit_status"] = 2
        if credential_guard is not None:
            credential_guard.clean_receipt(receipt)
        if bound_cli and receipt["reason_codes"]:
            receipt["settings_verification"] = "unverified"
            receipt["metadata_gate_passed"] = False
        if sink is not None:
            try:
                json.dump(receipt, sink, indent=2, sort_keys=True, allow_nan=False)
                sink.write("\n")
                sink.flush()
            except OSError:
                _reason(receipt, "execution_receipt_write_failed")
                receipt["status"] = "failed"
                receipt["exit_status"] = 2
            finally:
                sink.close()
    return receipt


def run_copilot_smoke(binary: Path, state_root: Path, *, execution_enabled=False, auth_source=None):
    """One fixed non-GDPVal prompt; no task selection, retries or gate dispatch."""
    return run_task(
        SMOKE_TASK_ID, [], state_root, execution_enabled=execution_enabled,
        execution_config={"tool_calls_per_task": SMOKE_TOOL_CALL_CAP}, copilot_cli=binary,
        auth_source=auth_source,
    )


def main(argv=None):
    parser = _Parser(description="Single fixed Copilot CLI CONNECTED smoke, disabled by default")
    parser.add_argument("--copilot-bin", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--execute-smoke", action="store_true", default=False)
    parser.add_argument("--auth-source", choices=AUTH_ENV_NAMES, default=None,
                        help="Explicit existing environment-variable name; never a token value")
    args = parser.parse_args(argv)
    receipt = run_copilot_smoke(args.copilot_bin, args.state_root,
                               execution_enabled=args.execute_smoke, auth_source=args.auth_source)
    print(json.dumps(receipt, separators=(",", ":"), allow_nan=False))
    return receipt["exit_status"]


if __name__ == "__main__":
    raise SystemExit(main())
