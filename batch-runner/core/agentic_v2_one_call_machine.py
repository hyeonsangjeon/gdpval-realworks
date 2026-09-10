"""One ``exec_run``, one machine: staging, boot, read-back, and nothing left.

D2's backend holds a workspace and calls ``boot_one_command`` once per
``exec_run``. This is the thing that satisfies that call on a host that can
really boot — it is the only place where the carriage
(:mod:`core.agentic_v2_work_disk`), the launcher
(:mod:`core.agentic_v2_microvm_launch`) and the boot
(:mod:`core.agentic_v2_first_boot`) meet.

**Every rule stays where it was written.** The launch plan is built by C1's
builder from :data:`REQUIRED_MICROVM_POLICY`, and exactly one key is changed on
the way past: ``wall_clock_seconds``, set to the deadline D1 already reconciled
between what the model asked for and what the policy allows. Tightening a bound
is the one adjustment a per-call launcher can make without becoming a second
place where containment is decided; a test here asserts that no other rule
differs, so a loosening cannot arrive disguised as a deadline.

**Where the changed workspace actually is after a boot.** Not in the jail —
:func:`first_boot` destroys the chroot as the last thing it does, because
``workdir: ephemeral-quota`` says so. Just before that it copies the work disk
to ``<work_disk>.returned``, and that copy is the only surviving record of what
the guest wrote. Reading from anywhere else finds an empty directory and reports
a model that did nothing.

**A command that finished and a workspace that came back are two facts, and the
model needs both.** If the command exits 0 and its files cannot be carried out,
handing back ``returncode: 0`` would tell the model its work is on disk when it
is not, and every later turn would be reasoning about files that are not there.
So the call is reported as an infrastructure failure, and the exit status the
guest really wrote is kept in the record under its own name rather than thrown
away.

The outcome used for that case is ``workspace_did_not_come_back``.
:func:`core.agentic_v2_exec_boot.read_the_boot` has no branch naming it, so it
falls to the last one and becomes ``compute_backend_error`` — the right answer,
reached by the right route. Its *wording* there ("wrote no exit status") is not
quite right for this case, and sharpening it is a small change to D1 that is
deliberately not made from here while D1's own tests are in flight.

Nothing in this module opens ``exec_run`` in the product path, changes
``foundation_only`` or ``production_activation``, or touches the runner's
backend-identity check. Those are D4, each on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY
from core.agentic_v2_work_disk import (
    carry_the_workspace_back,
    stage_the_work_disk,
    work_disk_fingerprint,
)


THE_ONE_RULE_A_CALL_MAY_TIGHTEN = "wall_clock_seconds"

WORKSPACE_DID_NOT_COME_BACK = "workspace_did_not_come_back"
"""The command ran and its files could not be carried off the disk.

Kept distinct from ``booted_but_wrote_nothing``, which means the guest produced
no exit status at all. Collapsing the two would lose the difference between a
machine that failed and a carriage that failed, and those get fixed in different
places.
"""


class MachineRefused(RuntimeError):
    """The call cannot be made as asked, so nothing was started."""


def policy_for_this_call(deadline_seconds: int) -> dict[str, Any]:
    """The containment rules with one bound tightened, and nothing else moved.

    Returns a full policy rather than a patch, because
    :func:`build_launch_plan` refuses a policy that is missing a rule or has
    gained one — which is what makes "nothing else moved" checkable rather than
    promised.
    """
    if (
        not isinstance(deadline_seconds, int)
        or isinstance(deadline_seconds, bool)
        or deadline_seconds <= 0
    ):
        raise MachineRefused(
            f"a deadline of {deadline_seconds!r} is not a bound, and a call with "
            "no bound is not a call this will make"
        )
    allowed = int(REQUIRED_MICROVM_POLICY[THE_ONE_RULE_A_CALL_MAY_TIGHTEN])
    if deadline_seconds > allowed:
        raise MachineRefused(
            f"{deadline_seconds} seconds is longer than the policy's {allowed}. "
            "A call may tighten this bound and may not loosen it, and D1 is "
            "where the model's request is reconciled with the policy"
        )
    return {**REQUIRED_MICROVM_POLICY, THE_ONE_RULE_A_CALL_MAY_TIGHTEN: deadline_seconds}


@dataclass
class OneCallMachine:
    """A host that can boot, holding everything that is fixed for the session.

    The image paths, the account to jail to and the processor count are facts
    about the host and are settled once. What arrives per call is the command,
    the workspace and the deadline — which is exactly D2's ``boot_one_command``
    signature, so an instance of this *is* that callable.
    """

    kernel: str | Path
    rootfs: str | Path
    firecracker_binary: str | Path
    uid: int
    gid: int
    vcpu_count: int
    cgroup_version: int
    scratch: str | Path
    session: str = "call"
    jailer_binary: str = "jailer"
    build_plan: Callable[..., Mapping[str, Any]] | None = None
    boot: Callable[..., Mapping[str, Any]] | None = None
    calls: int = 0
    record: list[dict[str, Any]] = field(default_factory=list)

    def name_the_machine(self) -> str:
        """A per-call identity the jailer will accept, and two calls never share.

        The jailer takes at most 64 alphanumerics and hyphens and turns the id
        into a directory under the chroot base, so a repeated id would be a
        second call building its jail on top of a first one's.
        """
        clean = "".join(ch for ch in self.session if ch.isalnum() or ch == "-")
        stem = (clean.strip("-") or "call")[:48]
        if not stem[0].isalnum():
            stem = f"c{stem}"
        return f"{stem}-{self.calls:04d}"

    def __call__(
        self,
        *,
        command_sh: str,
        workspace: str | Path,
        deadline_seconds: int,
    ) -> dict[str, Any]:
        from core.agentic_v2_first_boot import first_boot
        from core.agentic_v2_microvm_launch import build_launch_plan

        build_plan = self.build_plan or build_launch_plan
        boot = self.boot or first_boot

        call = self.calls
        # Named before the counter moves, and once, so the jail directory and
        # the plan's vm_id are the same string rather than two calls to a
        # function whose answer changed in between.
        name = self.name_the_machine()
        self.calls += 1
        here = Path(self.scratch) / name
        here.mkdir(parents=True, exist_ok=True)

        staged = stage_the_work_disk(
            workspace=workspace, command_sh=command_sh, into=here
        )
        plan = build_plan(
            vm_id=name,
            firecracker_binary=self.firecracker_binary,
            kernel_path=self.kernel,
            rootfs_path=self.rootfs,
            work_disk_path=staged["image"],
            uid=self.uid,
            gid=self.gid,
            vcpu_count=self.vcpu_count,
            cgroup_version=self.cgroup_version,
            policy=policy_for_this_call(deadline_seconds),
        )
        booted = dict(
            boot(
                plan,
                jailer_binary=self.jailer_binary,
                kernel=self.kernel,
                rootfs=self.rootfs,
                work_disk=staged["image"],
                uid=self.uid,
                gid=self.gid,
            )
        )

        # first_boot leaves the disk it took out of the jail beside the one that
        # went in, and then removes the jail. This copy is the only place the
        # guest's writes still exist.
        returned = Path(str(staged["image"]) + ".returned")
        carried = carry_the_workspace_back(
            image=returned, workspace=workspace, scratch=here / "back"
        )
        booted["workspace_carriage"] = carried
        booted["work_disk"] = {
            "staged_sha256": staged["sha256"],
            "returned_sha256": work_disk_fingerprint(returned),
            "carried_in": staged["carried"],
        }

        if booted.get("command_exit_status") is not None and not carried["replaced"]:
            # The command finished and its files did not come out. Reporting the
            # returncode here would tell the model its work is on disk.
            booted["command_exit_status_before_the_carriage_failed"] = booted[
                "command_exit_status"
            ]
            booted["command_exit_status"] = None
            booted["outcome"] = WORKSPACE_DID_NOT_COME_BACK

        self.record.append(
            {
                "call": call,
                "vm_id": plan["vm_id"],
                "deadline_seconds": deadline_seconds,
                "outcome": booted.get("outcome"),
                "carriage": {
                    "replaced": carried["replaced"],
                    "files": carried["files"],
                    "refused_symlinks": carried["refused_symlinks"],
                },
                "teardown": booted.get("teardown"),
            }
        )
        return booted
