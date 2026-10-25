"""Disabled-by-default process supervision; no bound GHCP command or authority.

The caller must supply an argv and an explicit tool-call cap. JSONL start
notifications support cancellation after observation, not pre-effect admission.
The existing workflow does not call this adapter. No authentication is supplied.
"""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import threading
import time
from pathlib import Path
from time import monotonic

import ghcp_sol_actions_gate as gate

POLL_SECONDS = 0.05
TERM_GRACE_SECONDS = 1.0
KILL_WAIT_SECONDS = 4.0


class _Stop(Exception):
    """Internal, program-selected refusal, never populated from child output."""

    def __init__(self, code):
        self.code = code


def _reason(receipt, code):
    if code not in receipt["reason_codes"]:
        receipt["reason_codes"].append(code)


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


def _session_events(process, deadline, receipt):
    """Read only bounded stdout JSONL. Stderr never enters the event channel."""
    seen = {"assistant.turn_start": set(), "tool.execution_start": set()}
    total = count = 0
    pending = bytearray()
    eof = False
    session_id = None

    def decode(line):
        nonlocal count, session_id
        _remaining(deadline)
        if len(line) > gate.MAX_EVENT_LINE_BYTES:
            raise _Stop("session_event_stream_refused")
        count += 1
        if count > gate.MAX_EVENTS:
            raise _Stop("session_event_stream_refused")
        event = json.loads(line, object_pairs_hook=gate._unique_object,
                           parse_constant=gate._invalid_constant)
        if (type(event) is not dict or type(event.get("type")) is not str
                or receipt["cli_result"]["observed"]):
            raise _Stop("session_event_stream_refused")
        if event["type"] == "result":
            # Copilot 1.0.79 app.js:2745/2844 writes this CLI-only summary,
            # not a session event. Never project its session ID, timestamp,
            # private file list, usage or cost, or substitute them for the
            # assistant.usage/session.usage_info events filtered by its CLI.
            if (set(event) != {"type", "timestamp", "sessionId", "exitCode", "usage"}
                    or type(event["timestamp"]) is not str
                    or not 0 < len(event["timestamp"]) <= 64
                    or session_id is None or event["sessionId"] != session_id
                    or type(event["exitCode"]) is not int or event["exitCode"] not in (0, 1)
                    or type(event["usage"]) is not dict):
                raise _Stop("session_event_stream_refused")
            receipt["cli_result"]["observed"] = True
            receipt["cli_result"]["exit_code"] = event["exitCode"]
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
        _count_start(event, receipt, seen)
        _remaining(deadline)
        return event

    try:
        os.set_blocking(process.stdout.fileno(), False)
        with selectors.DefaultSelector() as ready:
            ready.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = _remaining(deadline)
                if eof and _exited_without_reaping(process):
                    _remaining(deadline)
                    return
                for key, _ in ready.select(min(remaining, POLL_SECONDS)):
                    _remaining(deadline)
                    chunk = os.read(key.fd, gate.MAX_EVENT_LINE_BYTES + 1)
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
    cleanup["status"] = "failed" if failed else "group_signalled_leader_reaped"
    if failed:
        _reason(receipt, "subprocess_cleanup_failed")


def run_task(
    task_id: str, command: list[str] | tuple[str, ...], state_root: Path, *,
    execution_enabled: bool = False, execution_config: dict | None = None,
    model: str = gate.SOL_MODEL, byok: bool = False, provider_config=None,
) -> dict:
    """Supervise one explicitly enabled, fresh task; return a safe receipt.

    Pre-launch refusals return metadata without making a task directory. Once
    admitted locally, reserve execution-receipt.json before spawning and retain
    private/files without copying its contents. This is not a ledger claim,
    paid permission, retry grant, model attestation or GHCP command binding.
    """
    receipt = _receipt(task_id)
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
        if task_id not in gate.fixed_task_ids():
            raise _Stop("execution_task_refused")
        if (type(command) not in (list, tuple) or not command
                or any(type(arg) is not str or not arg or "\0" in arg for arg in command)
                or not Path(command[0]).is_absolute()):
            raise _Stop("execution_command_refused")
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
        started = monotonic()
        deadline = started + gate.PROPOSED_TASK_TIMEOUT_SECONDS
        try:
            process = subprocess.Popen(
                list(command), cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True, bufsize=0,
                # Never inherit tokens, routing overrides or credential channels.
                # This minimal environment is not proof of a CLI cache sandbox.
                env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1"},
            )
        except Exception:
            raise _Stop("subprocess_start_failed") from None
        receipt["subprocess_started"] = True
        _remaining(deadline)
        evidence = gate.collect_session_events(_session_events(process, deadline, receipt))
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
