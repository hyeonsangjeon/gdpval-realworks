"""Read-only startup evidence from the isolated, credential-free probe only.

No process, socket connection, authentication, session or model is started here.
Only the invocation-owned tree and the supervisor's descendants are inspected;
no process environment or credential/configuration file is read.
"""

from __future__ import annotations

import os
from pathlib import Path
import stat

from ghcp_ahp_diagnostics import DiagnosticRedactor
from ghcp_ahp_probe import Refused, digest, save_json

MAX_ENTRIES = 512
MAX_PROCESSES = 32
MAX_LOG_FILES = 12
MAX_FILE_BYTES = 128 * 1024
LOG_NAMES = frozenset({"agent-host-stable.log", "remoteagent.log", "agenthost.log", "agentHost.log"})
SOCKET_FLAGS = ("--socket-path", "--agent-host-path")


def _read(path, limit=MAX_FILE_BYTES):
    # Never follow a log symlink or block on a FIFO/device. Proc files report
    # st_size=0, so bound the actual read rather than trusting that size.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise Refused("backend_diagnostic_nonregular_file")
        data = source.read(limit + 1)
    return data[:limit].decode("utf-8", errors="replace"), len(data) > limit


def _tree(scratch):
    entries, logs, errors, pending = [], [], [], [scratch]
    truncated = False
    while pending and len(entries) < MAX_ENTRIES:
        directory = pending.pop(0)
        try:
            with os.scandir(directory) as children:
                for entry in children:
                    if len(entries) + len(errors) >= MAX_ENTRIES:
                        truncated = True
                        break
                    path = Path(entry.path)
                    relative = path.relative_to(scratch).as_posix()
                    try:
                        info = entry.stat(follow_symlinks=False)
                        kind = ("symlink" if stat.S_ISLNK(info.st_mode) else "directory" if stat.S_ISDIR(info.st_mode)
                                else "socket" if stat.S_ISSOCK(info.st_mode) else "file" if stat.S_ISREG(info.st_mode) else "other")
                        entries.append({"path": relative, "kind": kind, "mode": oct(stat.S_IMODE(info.st_mode)),
                                        "uid": info.st_uid, "gid": info.st_gid, "bytes": info.st_size})
                        if kind == "directory":
                            pending.append(path)
                        elif kind == "file" and path.name in LOG_NAMES and len(logs) < MAX_LOG_FILES:
                            # Restrict content reads to known VS Code startup log roots.
                            if relative.startswith(("home/.vscode-server/cli/", "server-data/logs/")):
                                content, cut = _read(path)
                                logs.append({"path": relative, "content": content, "truncated": cut})
                    except (OSError, Refused) as error:
                        if len(entries) + len(errors) < MAX_ENTRIES:
                            errors.append({"path": relative, "error": type(error).__name__})
                        else:
                            truncated = True
        except OSError as error:
            if len(entries) + len(errors) < MAX_ENTRIES:
                errors.append({"path": str(directory.relative_to(scratch)), "error": type(error).__name__})
            else:
                truncated = True
        if len(entries) + len(errors) >= MAX_ENTRIES:
            truncated = True
            break
    return {"entries": entries, "truncated": truncated or bool(pending), "logs": logs, "errors": errors,
            "log_limit_reached": len(logs) == MAX_LOG_FILES}


def _processes(supervisor_pid, scratch, proc_root):
    pending, rows, seen = [supervisor_pid], [], set()
    while pending and len(rows) < MAX_PROCESSES:
        pid = pending.pop(0)
        if pid in seen:
            continue
        seen.add(pid)
        row = {"pid": pid, "state": "not_observed", "exit_code": None}
        try:
            base = proc_root / str(pid)
            text, cut = _read(base / "stat", 8192)
            if cut or ") " not in text:
                raise Refused("backend_diagnostic_proc_shape")
            # comm (field 2) can contain spaces/parentheses; fields 3+ follow
            # its final closing parenthesis. Field 52 is a wait(2) status.
            tail = text.rsplit(") ", 1)[1].split()
            row.update(state=tail[0], parent_pid=int(tail[1]))
            if tail[0] == "Z" and len(tail) >= 50:
                row["exit_code"] = os.waitstatus_to_exitcode(int(tail[49]))
            row["exit_evidence"] = "proc_zombie_wait_status" if row["exit_code"] is not None else "not_exited_or_not_reported"
            command, cut = _read(base / "cmdline", 16384)
            args = command.split("\0")
            row["executable_name"] = Path(args[0]).name
            row["command_truncated"] = cut
            # Keep only path flags, never the raw command or inline shell code.
            row["socket_arguments"] = {}
            for index, arg in enumerate(args[:-1]):
                if arg in SOCKET_FLAGS:
                    candidate = Path(args[index + 1])
                    row["socket_arguments"][arg] = (str(candidate.relative_to(scratch))
                        if candidate.is_relative_to(scratch) else "outside_invocation_tree")
            children, cut = _read(base / "task" / str(pid) / "children", 8192)
            row["children_truncated"] = cut
            pending.extend(int(child) for child in children.split() if child.isdecimal())
        except (OSError, ValueError, IndexError, Refused) as error:
            row["inspection_error"] = str(error) if isinstance(error, Refused) else type(error).__name__
        rows.append(row)
    return {"entries": rows, "truncated": bool(pending),
            "scope": "supervisor_and_descendants_only_no_environ_or_credential_reads"}


def snapshot(scratch, process, *, proc_root=Path("/proc")):
    scratch = Path(scratch)
    if scratch.is_symlink() or not scratch.is_dir():
        raise Refused("backend_diagnostic_tree_refused")
    result = {"filesystem": _tree(scratch), "supervisor": None, "processes": None}
    if process is not None:
        result["supervisor"] = process.record()
        result["processes"] = _processes(process.process.pid, scratch, proc_root)
    return DiagnosticRedactor("").clean(result)


def export(evidence, *, before, after, primary_error_code, environment, vscode_commit):
    report = {"schema": "ghcp-ahp-backend-startup-v1", "synthetic": False, "diagnostic_only": True,
              "admission_allowed": False, "session_create_requests": 0, "model_calls": 0,
              "vscode_commit": vscode_commit, "primary_error_code": primary_error_code,
              "before_cleanup": before, "after_cleanup": after,
              "environment_contract": {"authentication_supplied": False, "credential_environment_inherited": False,
                  "display_present": bool(environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY")),
                  "shell_variable_present": bool(environment.get("SHELL")),
                  "isolated_home": environment.get("HOME"), "isolated_tmp": environment.get("TMPDIR")},
              "limitations": ["supervisor_ready_banner_is_not_backend_readiness",
                  "exit_after_cleanup_is_not_evidence_of_a_spontaneous_crash",
                  "missing_exit_status_is_null_not_zero", "no_authentication_or_model_readiness_claim"]}
    path = evidence / "backend-startup.json"
    save_json(path, DiagnosticRedactor("").clean(report))
    return {"path": path.name, "sha256": digest(path), "diagnostic_only": True, "admission_allowed": False}
