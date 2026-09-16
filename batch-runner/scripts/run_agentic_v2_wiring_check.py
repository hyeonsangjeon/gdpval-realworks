#!/usr/bin/env python3
"""Drive the approved isolated backend end to end, with no model in the loop.

Everything between ``--isolated-approval`` and a guest that has run a command
is already written, and every piece of it has tests. What has never happened is
the pieces being asked to work as one thing on a host that can really boot: the
approval read, the backend selected, the identity the runner would admit
checked against the identity the backend reports, a file staged into the
workspace, a command run inside a machine, the file the guest wrote read back
on the host, the machine confirmed gone, and then a second call and a second
task admitted onto the same host.

A model is not needed for any of that, and would make the answer worse. The
model's part is choosing the command; the part in question here is whether the
command reaches a guest at all. So the command is fixed, and what it does is
chosen to be something the host could not have produced for itself:

* it digests the staged input **inside the guest**, so a digest that matches
  means the bytes crossed into the machine and the answer crossed back;
* it counts its processors, which is the launch plan's ``vcpu_count`` and not
  this host's much larger number, so a command that had somehow run on the
  host answers this one wrong;
* it copies the input to an output file, which the second call then reads, so
  the workspace is shown to survive one machine being destroyed and another
  being built.

**Nothing here decides anything.** Every gate is the real one:
:func:`select_backend` chooses the backend, ``_validate_admitted_identity`` --
the runner's own function, imported rather than reimplemented -- checks the
identity, and the refusals are whatever those raise. There is no flag that
means "use the isolated one anyway"; if the approval does not hold up, this
exits non-zero having booted nothing. In particular there is **no fixture
fallback**: a run that selects the fixture stops, because a wiring check that
passes on the fixture would be checking the wrong wiring.

This does not activate anything. ``foundation_only`` stays true -- it is a
condition of selection, not an obstacle to it -- and ``production_activation``
is untouched and unread, exactly as ``_validate_admitted_identity`` says.

Usage::

    run_agentic_v2_wiring_check.py \\
        --approval /var/tmp/.../approval.json \\
        --session  wiring-check-<sha> \\
        --scratch  /var/tmp/.../wiring \\
        --out      /var/tmp/.../wiring-check.json

Exit status is 0 only when every case in the list passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_contract import AgenticV2Profile  # noqa: E402
from core.agentic_v2_exec_boot import EXEC_RECORD_DIR  # noqa: E402
from core.agentic_v2_isolated_selection import (  # noqa: E402
    IsolationApproval,
    IsolatedBackendRefused,
    select_backend,
)
from core.agentic_v2_microvm_backend import (  # noqa: E402
    UNRESOLVED_HOST_RECORD,
    AgenticV2MicroVMBackend,
)
from core.agentic_v2_runner import _validate_admitted_identity  # noqa: E402


INPUT_LEAF = "input.txt"
OUT_DIR = "out"
DEADLINE_SECONDS = 60
"""Well inside the policy's 1200. The command is trivial; the boot is not the
part being timed, and a generous bound here would only make a hang slower to
notice."""


class WiringRefused(RuntimeError):
    """A gate said no. Nothing was booted, or nothing more will be."""


# -- the fixed command -------------------------------------------------------

GUEST_SCRIPT = """\
set -e
mkdir -p {out}
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum {inp} | cut -d' ' -f1 > {out}/input_digest
  printf '%s' sha256sum > {out}/digest_tool
else
  cksum {inp} | cut -d' ' -f1 > {out}/input_digest
  printf '%s' cksum > {out}/digest_tool
fi
wc -c < {inp} | tr -d ' \\n' > {out}/input_bytes
uname -r > {out}/guest_kernel_release
(nproc 2>/dev/null || grep -c '^processor' /proc/cpuinfo) > {out}/guest_cpu_count
cp {inp} {out}/echoed_back
printf '%s' '{marker}' > {out}/marker
"""

SECOND_GUEST_SCRIPT = """\
set -e
test -f {out}/echoed_back
wc -c < {out}/echoed_back | tr -d ' \\n' > {out}/second_call_saw_bytes
printf '%s' '{marker}' > {out}/second_marker
"""

THIRD_GUEST_SCRIPT = """\
set -e
mkdir -p {out}
printf '%s' '{marker}' > {out}/next_task_marker
"""


def _argv(script: str) -> list[str]:
    """The command as the contract takes it.

    ``argv`` rather than one of the four named interpreters, because the guest
    image is not required to carry python, node, R or bash -- and the one thing
    it certainly carries is the shell that runs ``command.sh`` itself.
    """
    return ["/bin/sh", "-c", script]


# -- the case list -----------------------------------------------------------


class Cases:
    """The finite list this run is judged on, and its own denominator."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def record(self, name: str, passed: bool, detail: Any) -> bool:
        self.rows.append({"case": name, "passed": bool(passed), "detail": detail})
        mark = "pass" if passed else "FAIL"
        print(f"  [{mark}] {name}")
        if not passed:
            print(f"         {detail}")
        return bool(passed)

    @property
    def all_passed(self) -> bool:
        return bool(self.rows) and all(row["passed"] for row in self.rows)

    def summary(self) -> dict[str, int]:
        return {
            "cases": len(self.rows),
            "passed": sum(1 for row in self.rows if row["passed"]),
        }


# -- helpers that only read --------------------------------------------------


def _host_digest(path: Path, tool: str) -> str:
    """The same digest the guest reported, computed here.

    ``cksum`` is shelled out to rather than reimplemented: the point of the
    comparison is that two independent programs agree, and a reimplementation
    of the CRC in this file would be one program compared with itself.
    """
    if tool == "sha256sum":
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if tool == "cksum":
        out = subprocess.run(
            ["cksum", str(path)], capture_output=True, text=True, check=True
        )
        return out.stdout.split()[0]
    raise WiringRefused(f"the guest named a digest tool nobody here knows: {tool!r}")


def _read_if_there(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _paths_the_teardown_says_it_removed(
    machine: Mapping[str, Any]
) -> tuple[list[str], list[str]]:
    """What the teardown claims it took away, and what is still there now.

    Deliberately not ``all_gone``. That flag is false for reasons that have
    nothing to do with a machine still running -- an empty list is one of them
    -- so reading it as "the host is dirty" is reading a different fact. The
    paths themselves are checkable: the teardown names them, and this asks the
    filesystem.
    """
    teardown = machine.get("teardown") or {}
    removed = teardown.get("removed") or {}
    named = sorted(str(path) for path in removed)
    still_there = [path for path in named if Path(path).exists()]
    return named, still_there


# -- the run -----------------------------------------------------------------


def _choose(approval_path: Path, session: str, cases: Cases):
    approval = IsolationApproval.load(approval_path)
    choice = select_backend(approval=approval, session=session)
    if choice.backend_class is not AgenticV2MicroVMBackend:
        cases.record(
            "an approved run selects the isolated backend",
            False,
            f"selected {choice.backend_class.__name__}; a wiring check that "
            "continues on the fixture is checking the wrong wiring",
        )
        raise WiringRefused("the fixture was selected")
    cases.record(
        "an approved run selects the isolated backend",
        True,
        {
            "backend_class": choice.backend_class.__name__,
            "is_isolated": bool(choice.is_isolated),
            "grounds": {
                key: value
                for key, value in sorted(choice.grounds.items())
                if key != "images_rechecked"
            },
        },
    )
    return approval, choice


def _admission(choice, cases: Cases) -> dict[str, Any]:
    """The runner's own check, run here rather than described here."""
    admitted = _validate_admitted_identity(choice.identity_to_declare)
    if admitted is None:
        cases.record(
            "the runner would admit the identity selection declares",
            False,
            "identity_to_declare was None, which is the fixture default",
        )
        raise WiringRefused("no identity to admit")
    cases.record(
        "the runner would admit the identity selection declares", True, admitted
    )
    return admitted


def _build(choice, *, root: Path, host_state: Path, task_id: str, profile):
    """Constructed the way the stage script constructs it, not a way of its own."""
    return choice.backend_class(
        root=root,
        host_state_dir=host_state,
        **choice.extra_kwargs,
        profile=profile,
        task_id=task_id,
        budget_caps=None,
    )


def _stage_input(backend, payload: bytes) -> Path:
    staged = backend.work / INPUT_LEAF
    staged.write_bytes(payload)
    return staged


def _run_one(backend, script: str, *, cases: Cases, label: str) -> Mapping[str, Any]:
    result = backend.exec_run(
        {
            "cwd": ".",
            "argv": _argv(script),
            "timeout_seconds": DEADLINE_SECONDS,
        }
    )
    cases.record(
        f"{label}: exec_run came back with a returncode",
        bool(result.get("ok")) and (result.get("data") or {}).get("returncode") == 0,
        result,
    )
    return result


def _boot_record(backend) -> Mapping[str, Any]:
    if not backend.boots:
        raise WiringRefused("the backend filed no boot record at all")
    return backend.boots[-1]


def _judge_first_call(
    backend, *, staged: Path, payload: bytes, marker: str, vcpu_count: int, cases: Cases
) -> None:
    out = backend.work / OUT_DIR
    tool = _read_if_there(out / "digest_tool")
    reported = _read_if_there(out / "input_digest")
    if tool is None or reported is None:
        cases.record(
            "the staged input was digested inside the guest",
            False,
            f"digest_tool={tool!r} input_digest={reported!r}; the guest wrote "
            "neither, so nothing read the staged file",
        )
    else:
        expected = _host_digest(staged, tool)
        cases.record(
            "the staged input was digested inside the guest",
            reported == expected,
            {"tool": tool, "guest": reported, "host": expected},
        )

    echoed = out / "echoed_back"
    cases.record(
        "the file the guest wrote came back to the host",
        echoed.is_file() and echoed.read_bytes() == payload,
        {
            "path": str(echoed),
            "exists": echoed.is_file(),
            "bytes": echoed.stat().st_size if echoed.is_file() else None,
            "expected_bytes": len(payload),
        },
    )

    counted = _read_if_there(out / "guest_cpu_count")
    host_cpus = os.cpu_count()
    cases.record(
        "the command ran on the machine the plan built, not on this host",
        counted == str(vcpu_count) and str(vcpu_count) != str(host_cpus),
        {
            "guest_reported": counted,
            "plan_vcpu_count": vcpu_count,
            "host_cpu_count": host_cpus,
        },
    )

    cases.record(
        "the guest named its own kernel",
        bool(_read_if_there(out / "guest_kernel_release")),
        {
            "guest_kernel_release": _read_if_there(out / "guest_kernel_release"),
            "host_kernel_release": os.uname().release,
        },
    )

    cases.record(
        "this run's marker is the one that came back",
        _read_if_there(out / "marker") == marker,
        {"expected": marker, "found": _read_if_there(out / "marker")},
    )

    kept = backend.work / EXEC_RECORD_DIR / "0000"
    leaves = sorted(p.name for p in kept.iterdir()) if kept.is_dir() else []
    cases.record(
        "the transcript was kept where the model would read it",
        leaves == ["meta.json", "stderr", "stdout"],
        {"directory": str(kept), "leaves": leaves},
    )


def _judge_cleanup(backend, *, host_state: Path, cases: Cases, label: str) -> None:
    record = _boot_record(backend)
    machine = record.get("machine") or {}
    cases.record(
        f"{label}: the guest was confirmed stopped and the host was not left running",
        machine.get("guest_confirmed_stopped") is True
        and machine.get("host_left_running") is False,
        machine,
    )
    named, still_there = _paths_the_teardown_says_it_removed(machine)
    cases.record(
        f"{label}: everything the teardown named is gone from the disk",
        bool(named) and still_there == [],
        {"named": named, "still_there": still_there},
    )
    unresolved = host_state / UNRESOLVED_HOST_RECORD
    cases.record(
        f"{label}: nothing was written down as an unresolved host",
        not unresolved.exists(),
        {"path": str(unresolved), "exists": unresolved.exists()},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--session", required=True)
    parser.add_argument("--scratch", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--policy-profile-id",
        default="offline-full-v1",
        help="the profile the stage script would have read from the plan",
    )
    args = parser.parse_args()

    cases = Cases()
    scratch = args.scratch.resolve()
    if scratch.exists():
        raise WiringRefused(
            f"{scratch} already exists; this run wants a directory nobody else "
            "has written into, so that what is found in it afterwards is this "
            "run's doing"
        )

    profile = AgenticV2Profile.from_mapping(
        {
            "tool_contract_version": "2.0",
            "policy_profile_id": args.policy_profile_id,
            "foundation_only": True,
        }
    )

    print(f"Agentic Sandbox V2 — wiring check, session {args.session}")
    print("=" * 74)

    artefact: dict[str, Any] = {
        "schema": "agentic_v2_wiring_check/1",
        "session": args.session,
        "approval": str(args.approval),
        "host": {
            "kernel_release": os.uname().release,
            "cpu_count": os.cpu_count(),
            "hostname": os.uname().nodename,
        },
        "model_calls": 0,
        "paid_runs": 0,
    }

    approval, choice = _choose(args.approval, args.session, cases)
    artefact["admitted_identity"] = _admission(choice, cases)
    artefact["image"] = {
        "reference": choice.extra_kwargs["image"].reference,
        "digest": choice.extra_kwargs["image"].digest,
    }

    # Made only once the gates have all said yes. A refusal that had already
    # created it would leave the directory behind, and the next attempt would
    # then refuse on the line above -- for the wrong reason, and forever.
    scratch.mkdir(parents=True)
    host_state = scratch / "host-state"
    host_state.mkdir()

    payload = hashlib.sha256(
        f"{args.session}|wiring-check|staged-input".encode("utf-8")
    ).hexdigest().encode("utf-8") * 64
    marker = hashlib.sha256(
        f"{args.session}|wiring-check|marker".encode("utf-8")
    ).hexdigest()[:32]

    # -- task one -----------------------------------------------------------
    first_root = scratch / "task-one"
    backend = _build(
        choice,
        root=first_root,
        host_state=host_state,
        task_id="wiring-check-task-one",
        profile=profile,
    )
    try:
        started = backend.start(timeout_seconds=float(DEADLINE_SECONDS))
        cases.record(
            "the backend describes itself from a verified manifest",
            bool(started.get("ok"))
            and bool(
                ((started.get("data") or {}).get("substrate_manifest") or {}).get(
                    "sha256"
                )
            ),
            started.get("data", {}).get("substrate_manifest", started),
        )
        cases.record(
            "the identity the backend reports is the identity the run admits",
            backend.backend_identity() == artefact["admitted_identity"],
            {
                "reported": backend.backend_identity(),
                "admitted": artefact["admitted_identity"],
            },
        )

        staged = _stage_input(backend, payload)
        first = _run_one(
            backend,
            GUEST_SCRIPT.format(out=OUT_DIR, inp=INPUT_LEAF, marker=marker),
            cases=cases,
            label="call one",
        )
        artefact["call_one"] = {"result": dict(first), "record": _boot_record(backend)}
        _judge_first_call(
            backend,
            staged=staged,
            payload=payload,
            marker=marker,
            vcpu_count=approval.vcpu_count,
            cases=cases,
        )
        _judge_cleanup(backend, host_state=host_state, cases=cases, label="call one")

        # -- call two, same task, same host ---------------------------------
        second = _run_one(
            backend,
            SECOND_GUEST_SCRIPT.format(out=OUT_DIR, marker=marker),
            cases=cases,
            label="call two",
        )
        artefact["call_two"] = {"result": dict(second), "record": _boot_record(backend)}
        saw = _read_if_there(backend.work / OUT_DIR / "second_call_saw_bytes")
        cases.record(
            "a second machine was admitted and found what the first one wrote",
            saw == str(len(payload)),
            {"second_call_saw_bytes": saw, "expected": len(payload)},
        )
        artefact["task_one_boots"] = [dict(row) for row in backend.boots]
    finally:
        backend.close()
    cases.record(
        "the first task's workspace was purged on close",
        not first_root.joinpath("work").exists(),
        {"work": str(first_root / "work")},
    )

    # -- task two: the next task on the same host ---------------------------
    second_root = scratch / "task-two"
    next_backend = _build(
        choice,
        root=second_root,
        host_state=host_state,
        task_id="wiring-check-task-two",
        profile=profile,
    )
    try:
        third = _run_one(
            next_backend,
            THIRD_GUEST_SCRIPT.format(out=OUT_DIR, marker=marker),
            cases=cases,
            label="next task",
        )
        next_marker = _read_if_there(next_backend.work / OUT_DIR / "next_task_marker")
        cases.record(
            "the next task was admitted onto the same host",
            bool(third.get("ok")) and next_marker == marker,
            {"next_task_marker": next_marker, "expected": marker},
        )
        artefact["task_two_boots"] = [dict(row) for row in next_backend.boots]
        _judge_cleanup(
            next_backend, host_state=host_state, cases=cases, label="next task"
        )
    finally:
        next_backend.close()

    artefact["cases"] = cases.rows
    artefact["summary"] = cases.summary()
    artefact["all_passed"] = cases.all_passed
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(artefact, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )

    print("=" * 74)
    print(f"  {cases.summary()['passed']} of {cases.summary()['cases']} cases passed")
    print(f"  artefact       {args.out}")
    return 0 if cases.all_passed else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (WiringRefused, IsolatedBackendRefused, ValueError) as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        raise SystemExit(2) from refusal
