"""Turning one ``exec_run`` request into a boot, and one boot into a result.

Stage C proved a machine: it comes up with the containment rules applied, and
seven separate ways out of it are closed. What it did not build is the thing on
the other side of the tool contract, and the gap between the two is not
"connect the finished pieces".

**Stage C boots a machine to run one command and then destroys it.** The tool
contract's ``exec_run`` is called repeatedly inside a session that holds state:
the model writes a file, runs something, reads what came back, runs something
else. Between those calls the workspace has to still exist, and a machine that
is destroyed after one command has nowhere to keep it.

The way that is closed here is **a fresh machine per call, with the workspace
carried across on the host**. The workspace lives in a host directory between
calls; each ``exec_run`` builds a work disk out of it, boots, runs, is destroyed,
and the changed workspace is read back out of the disk image afterwards. It
costs a boot per call, and it buys two things worth more than that: every call
inherits stage C's evidence rather than needing its own, and nothing at all
survives a call except a disk image the host controls, so a call that gets
compromised has no resident machine to stay in.

This module is the *pure* half of that — the half that can be proven on a box
which cannot boot a microVM at all. It builds the guest command, and it reads
what a boot returned. It runs no subprocess, opens no socket, and touches no
file. The boot itself is :func:`core.agentic_v2_first_boot.first_boot`, injected
by the caller, exactly as stage C's attacks were.

**The one rule that decides whether any of this is honest.** A guest that
panicked on boot and a guest whose command returned 0 leave *different*
evidence, and telling them apart is the whole job:

- ``/out/exit_status`` present — the command ran, and this is its returncode
  whatever the number is. A non-zero returncode is a *successful tool call*
  reporting a failed command, and the model is shown it and chooses again.
- ``/out/exit_status`` absent — nothing ran to completion and there is no
  returncode. That is an error with a name, never ``returncode: 0`` and never
  an invented non-zero.

Getting that backwards is how a run of 220 tasks reports a wall of tidy command
failures that were really one broken launcher. Stage C's first attack run made
this mistake in the other direction — it read a destroyed reporter as a rule
that had not held — and the discipline that came out of it is the same one:
**absent evidence is not a result.**

What is deliberately not here: any way to open ``exec_run``. The guards in
``step2_run_inference.py`` and ``core/executor.py`` are untouched by this file,
and opening them is its own change with its own review.
"""

from __future__ import annotations

import base64
import shlex
from typing import Any, Mapping

from core.agentic_v2_microvm import REQUIRED_MICROVM_POLICY


WORKSPACE_IN_GUEST = "/work/ws"
"""Where the session workspace sits on the work disk.

``GUEST_INIT`` mounts the work disk at ``/work`` and runs ``/work/in/command.sh``
from it, so the workspace is a directory on that same disk. It is the only
writable place in the machine: the root filesystem is mounted read-only, which
is stage C's fifth attack.
"""

SCRATCH_IN_GUEST = "/work/in"

STDIN_IN_GUEST = f"{SCRATCH_IN_GUEST}/stdin"
SCRIPT_IN_GUEST = f"{SCRATCH_IN_GUEST}/script"

EXEC_RECORD_DIR = ".gdpval/exec"
"""Where a call's captured output is put *in the workspace*, for the model to read.

``exec_run``'s result carries a returncode and nothing else — that is the
contract, and ``additionalProperties`` is false, so there is no field to put
output in even if one wanted to. The model reads what its command printed the
same way it reads any other file, with ``workspace_apply``. These paths are
relative, contain no ``..`` and no control characters, so they satisfy the
contract's path rule and the model can address them.
"""

MOST_OUTPUT_BYTES = 1048576
"""How much of one stream is kept, matching the contract's per-file ceiling."""

TRUNCATION_NOTE = "\n[gdpval] output truncated at {kept} bytes of {produced}\n"
"""Written into the kept output when a stream ran past the ceiling.

Silently truncating is how a model reads a partial table as a whole one and is
confidently wrong about it. The note costs a line and removes that whole class
of mistake.
"""

CD_FAILED_MARKER = "gdpval-cd-failed"
"""The wrapper could not enter the requested directory, so nothing ran."""

DECODE_FAILED_MARKER = "gdpval-decode-failed"
"""``base64`` was missing or refused, so the payload never reached the disk.

A separate marker from the one above on purpose. Failing to enter a directory
is something about the *request* and the model can fix it by asking for another
one; a guest with no working ``base64`` is something about the *image*, and
telling the model to correct its path would send it chasing a fault it has no
way to reach.
"""

GUEST_SETUP_STATUS = 125
"""The status the wrapper exits with when its own setup failed.

125 is chosen because it is not one of the meanings a shell already assigns —
126 is "found but not executable", 127 is "not found", and 128+n is a signal.
It is still a number a command could return by itself, so it is never read
alone: it counts as a setup failure only alongside the matching marker on
stderr, and the residual ambiguity is a command that exits 125 having printed
exactly that marker and nothing else.
"""

INTERPRETERS: dict[str, str] = {
    "python": "python3",
    "node": "node",
    "r": "Rscript",
    "bash": "bash",
}
"""The four the contract names, mapped to what they are called in the guest.

An interpreter the image does not have is **not refused here**. The command
fails inside the machine with "not found", the model is shown that, and it
chooses again — which is the loop working. Refusing on the host would turn a
thing the model can recover from into a thing it cannot see.
"""

_BASE64_LINE = 76

_HEREDOC_DELIMITERS = {
    STDIN_IN_GUEST: "GDPVAL_STDIN_EOF",
    SCRIPT_IN_GUEST: "GDPVAL_SCRIPT_EOF",
}
"""Delimiters that base64 output provably cannot contain, because of ``_``.

The usual heredoc hazard is content that happens to include the delimiter line,
which ends the document early and feeds the rest of it to the shell. Here the
document is always base64, whose alphabet is ``A-Z a-z 0-9 + / =`` — an
underscore never appears in it, so the collision is not unlikely, it is
impossible. Carrying the payload as base64 also fixes two quieter problems: a
heredoc appends a newline that the model's own bytes may not have had, and a
single ``printf`` argument long enough to hold a 256 KiB script would be past
``MAX_ARG_STRLEN`` and fail to execute at all.
"""


class ExecRefused(ValueError):
    """The request cannot be expressed as a guest command, so none was built.

    Distinct from a command that fails: this is the host declining to write a
    script it cannot write faithfully, before anything boots and before any
    money is spent on it.
    """


def effective_deadline(
    requested_seconds: Any,
    *,
    policy: Mapping[str, Any] = REQUIRED_MICROVM_POLICY,
) -> dict[str, Any]:
    """Reconcile the bound the model asked for with the one the policy allows.

    ``exec_run``'s schema permits ``timeout_seconds`` up to 2700 and the
    containment policy allows 1200. A model asking for more than the policy
    permits is neither an error nor a refusal — it gets the policy's number.

    What matters is that the answer **says which number was applied**, so that
    nobody reading the record later takes a kill at 1200 seconds for the model's
    own 2700-second choice having been honoured.
    """
    allowed = policy.get("wall_clock_seconds")
    if not isinstance(allowed, int) or isinstance(allowed, bool) or allowed <= 0:
        raise ExecRefused(
            f"the policy's wall_clock_seconds is {allowed!r}, which is not a "
            "bound, and a call with no bound is not a call this will make"
        )
    if (
        not isinstance(requested_seconds, int)
        or isinstance(requested_seconds, bool)
        or requested_seconds <= 0
    ):
        raise ExecRefused(
            f"timeout_seconds was {requested_seconds!r}; the contract requires a "
            "positive whole number and there is no default worth inventing"
        )
    applied = min(requested_seconds, allowed)
    return {
        "requested_seconds": requested_seconds,
        "policy_seconds": allowed,
        "applied_seconds": applied,
        "capped_by_the_policy": applied < requested_seconds,
    }


def _decode_into(path: str, payload: str) -> str:
    encoded = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    delimiter = _HEREDOC_DELIMITERS[path]
    body = "\n".join(
        encoded[at : at + _BASE64_LINE] for at in range(0, len(encoded), _BASE64_LINE)
    )
    return (
        f"base64 -d > {path} 2>/dev/null <<'{delimiter}'\n"
        f"{body}\n"
        f"{delimiter}\n"
        f"if [ $? -ne 0 ]; then\n"
        f"  echo '{DECODE_FAILED_MARKER}' >&2\n"
        f"  exit {GUEST_SETUP_STATUS}\n"
        f"fi"
    )


def command_script(
    arguments: Mapping[str, Any],
    *,
    interpreters: Mapping[str, str] = INTERPRETERS,
) -> str:
    """Build the ``command.sh`` the guest's init will run, or refuse to.

    Two shapes are accepted because the contract has two: an ``argv`` to run,
    and a ``script`` for one of four named interpreters. Both end up as the same
    thing — a short wrapper that puts the payload on the work disk, enters the
    requested directory, and runs the command with its input redirected.

    **Standard input is always redirected, from ``/dev/null`` when the request
    gave none.** Without that, a command that reads stdin inherits whatever
    descriptor the guest's init had, which is neither a terminal nor empty and
    is not the same thing twice. A command that quietly consumed part of its own
    launcher script would be a very hard afternoon.

    ``interpreters`` maps the four names the contract allows to the binaries to
    invoke. It is an argument rather than a constant because the guest is a
    fact about the image, not about this file: an image whose Python is
    ``python`` and not ``python3`` is answered by pinning the mapping, not by
    editing a table here on the strength of what is usually true.
    """
    cwd = arguments.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        raise ExecRefused("exec_run needs a cwd and this request has none")
    if cwd.startswith("/") or any(part == ".." for part in cwd.split("/")):
        raise ExecRefused(
            f"cwd {cwd!r} leaves the workspace, and the workspace is the only "
            "place in the machine that is writable"
        )

    lines = [
        "#!/bin/sh",
        "# Built by core/agentic_v2_exec_boot.py, and run by the guest's init as",
        "# its only command. Its stdout and stderr are the work disk's files.",
        f"mkdir -p {SCRATCH_IN_GUEST}",
    ]

    stdin_text = arguments.get("stdin")
    if stdin_text is None:
        stdin_from = "/dev/null"
    elif isinstance(stdin_text, str):
        lines.append(_decode_into(STDIN_IN_GUEST, stdin_text))
        stdin_from = STDIN_IN_GUEST
    else:
        raise ExecRefused(f"stdin must be text if it is given, not {type(stdin_text)}")

    has_argv = "argv" in arguments
    has_script = "script" in arguments or "interpreter" in arguments
    if has_argv == has_script:
        raise ExecRefused(
            "exec_run is either an argv or an interpreter and a script, and "
            "this request is " + ("both" if has_argv else "neither")
        )

    if has_argv:
        argv = arguments["argv"]
        if not isinstance(argv, list) or not argv:
            raise ExecRefused("argv has to be a non-empty list of strings")
        if any(not isinstance(item, str) for item in argv):
            raise ExecRefused("every argv entry has to be a string")
        command = " ".join(shlex.quote(item) for item in argv)
    else:
        interpreter = arguments.get("interpreter")
        script = arguments.get("script")
        if interpreter not in interpreters:
            raise ExecRefused(
                f"interpreter {interpreter!r} is not one of "
                f"{sorted(interpreters)}, and guessing which was meant is how "
                "the wrong language runs the right file"
            )
        if not isinstance(script, str) or not script:
            raise ExecRefused("an interpreter needs a script and this has none")
        lines.append(_decode_into(SCRIPT_IN_GUEST, script))
        command = f"{interpreters[interpreter]} {SCRIPT_IN_GUEST}"

    target = f"{WORKSPACE_IN_GUEST}/{cwd}".rstrip("/")
    # The shell's own "can't cd to ..." goes to /dev/null so that stderr holds
    # the marker and nothing else. Without that the marker is preceded by a
    # sentence whose wording differs between dash, ash and bash, and the reader
    # downstream is matching stderr exactly — it would have matched on no real
    # guest at all.
    lines.append(
        f"cd {shlex.quote(target)} 2>/dev/null || "
        f"{{ echo '{CD_FAILED_MARKER}' >&2; exit {GUEST_SETUP_STATUS}; }}"
    )
    lines.append(f"{command} < {stdin_from}")
    return "\n".join(lines) + "\n"


def _capped(stream: Any) -> tuple[str, bool]:
    text = stream if isinstance(stream, str) else ""
    produced = len(text.encode("utf-8"))
    if produced <= MOST_OUTPUT_BYTES:
        return text, False
    kept = text.encode("utf-8")[:MOST_OUTPUT_BYTES].decode("utf-8", "ignore")
    return kept + TRUNCATION_NOTE.format(kept=len(kept), produced=produced), True


def read_the_boot(
    boot: Mapping[str, Any], *, deadline: Mapping[str, Any]
) -> dict[str, Any]:
    """Read one boot as a tool result, and say on what grounds.

    Four outcomes come back from the launcher and they mean four different
    things. The table is small and every row of it matters:

    ===========================  =============  ==================================
    boot outcome                 exit status    what the model is told
    ===========================  =============  ==================================
    ``booted``                   present        ``ok``, with that returncode
    ``booted``                   absent         ``compute_backend_error``
    ``booted_but_wrote_nothing`` absent         ``compute_backend_error``
    ``never_started``            absent         ``compute_start_failed``
    ``stopped_by_the_deadline``  absent         ``cancelled`` — the bound worked
    ``stopped_by_the_deadline``  **present**    ``ok``, with that returncode
    ===========================  =============  ==================================

    The last row is the one that is easy to get wrong. If the guest wrote an
    exit status, the command **finished**; the machine merely failed to shut
    down inside its deadline afterwards. Throwing the returncode away there
    would discard a real answer because of something that happened after it.

    A deadline that fires is not an error in the machine. It is stage C's third
    attack succeeding on purpose — the bound doing exactly what it was measured
    doing — and the model is told the call was cancelled and how long it had.

    The exit status is a file the *guest* wrote, so it is not trusted to be a
    number in range. Anything else is ``invalid_backend_result``, because a
    returncode outside 0–255 is not a returncode.
    """
    outcome = boot.get("outcome")
    results = boot.get("results") or {}
    stdout, stdout_cut = _capped(results.get("/out/stdout"))
    stderr, stderr_cut = _capped(results.get("/out/stderr"))
    status = boot.get("command_exit_status")

    def answer(
        ok: bool, error_type: str | None, data: dict, grounds: str
    ) -> dict[str, Any]:
        return {
            "result": {"ok": ok, "error_type": error_type, "data": data},
            "stdout": stdout,
            "stderr": stderr,
            "truncated": {"stdout": stdout_cut, "stderr": stderr_cut},
            "deadline": dict(deadline),
            "boot_outcome": outcome,
            "grounds": grounds,
        }

    if status is not None:
        if not isinstance(status, int) or isinstance(status, bool):
            return answer(
                False,
                "invalid_backend_result",
                {},
                f"the guest wrote {status!r} where a returncode goes",
            )
        if not 0 <= status <= 255:
            return answer(
                False,
                "invalid_backend_result",
                {},
                f"the guest reported {status}, which is not a returncode",
            )
        if status == GUEST_SETUP_STATUS and stderr.strip() == CD_FAILED_MARKER:
            return answer(
                False,
                "path_not_directory",
                {},
                "the wrapper could not enter the requested directory, so the "
                "command never ran and this is not its returncode",
            )
        if status == GUEST_SETUP_STATUS and stderr.strip() == DECODE_FAILED_MARKER:
            return answer(
                False,
                "compute_backend_error",
                {},
                "the guest could not decode the payload onto the work disk, "
                "which is a fault in the image and not in the request",
            )
        ran_anyway = (
            " after its deadline had already fired, so the command finished and "
            "only the shutdown overran"
            if outcome == "stopped_by_the_deadline"
            else ""
        )
        return answer(
            True,
            None,
            {"returncode": status},
            f"the guest wrote an exit status of {status}{ran_anyway}",
        )

    if outcome == "stopped_by_the_deadline":
        return answer(
            False,
            "cancelled",
            {},
            f"the machine was stopped at its {deadline.get('applied_seconds')} "
            "second bound with no exit status written, so the command was still "
            "running when the bound was reached",
        )
    if outcome == "never_started":
        return answer(
            False,
            "compute_start_failed",
            {},
            "the jailer wrote no pid file, so no machine existed to run in",
        )
    return answer(
        False,
        "compute_backend_error",
        {},
        f"the machine ended as {outcome!r} and wrote no exit status, so nothing "
        "here says the command ran — and a missing result is not a returncode",
    )
