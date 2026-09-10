"""The seven attacks, and what each one has to produce to count as stopped.

Stage C1 turned the policy into arguments. C2 showed a guest boots under them.
Neither shows that the arguments have the effect their names suggest, and the
gap between those two things is the whole reason this stage exists: a rule that
reads as enforced and is not is worse than a rule nobody wrote down, because the
report says it is covered.

**Absent evidence is never a pass.** Every verdict in this module starts at
"not stopped" and has to be argued into "stopped" by something that was actually
read back. A probe that did not run, a guest that died before it got there, a
file that came back empty — all of those are failures of the attack, recorded as
such. The alternative, treating silence as success, would turn a guest that
crashed on boot into a clean sweep of all seven.

**Two of the seven are not observed inside the guest, and cannot be.**
``user: jailer-unprivileged`` is a statement about the Firecracker process on
the host, not about the guest's own uid — inside the machine PID 1 is root and
is supposed to be. ``credentials: none-inherited`` is the same: what matters is
what the host-side process carries, in its environment *and* in its open
descriptors. Both are read from ``/proc/<pid>`` while the machine is alive,
which is why the runner needs a way to look at a machine mid-flight rather than
only at what it left behind.

**The attacks are grouped into separate boots on purpose.** Filling the work
disk destroys the only channel the guest has to answer on; provoking the memory
bound can take the guest down with it. Running those beside the quiet probes
would let one attack's success erase another's evidence, and the erased one
would read as "no evidence", which is a failure. So the destructive ones get
their own machines.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping

from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY

BOOT_PROBES = "probes"
BOOT_WORKDIR = "workdir-quota"
BOOT_MEMORY = "memory"
BOOT_WALL_CLOCK = "wall-clock"

_MIB = 1024 * 1024


class AttackRefused(RuntimeError):
    """An attack could not be judged, which is not the same as it being stopped."""


# --------------------------------------------------------------------------
# what each attack runs inside the guest
# --------------------------------------------------------------------------

_QUIET_PROBES = r"""
echo "== network =="
cat /proc/net/dev 2>/dev/null | awk 'NR>2 {print $1}' | tr -d ':'
python3 - <<'PY' 2>&1 || echo "connect_probe=no-python"
import socket
try:
    socket.create_connection(("1.1.1.1", 443), 5).close()
    print("connect_probe=CONNECTED")
except OSError as failure:
    print("connect_probe=refused:%s" % failure.__class__.__name__)
PY

echo "== rootfs =="
grep ' / ' /proc/mounts
if echo probe > /gdpval-root-write-probe 2>/dev/null; then
  echo "rootfs_write=SUCCEEDED"
  rm -f /gdpval-root-write-probe
else
  echo "rootfs_write=refused"
fi

echo "== memory bound =="
grep MemTotal /proc/meminfo

echo "== credentials =="
echo "env_count=$(env | wc -l)"
env | grep -Ei 'KEY|TOKEN|SECRET|PASSWORD|AZURE|OPENAI|ANTHROPIC|GITHUB' \
  && echo "guest_env=CARRIES SOMETHING" || echo "guest_env=clean"
echo "self_environ_bytes=$(wc -c < /proc/1/environ 2>/dev/null || echo unknown)"

# Two of the seven are facts about the host-side process rather than about
# anything in here, and they can only be read while it is alive. C2's guest
# was gone 1.269 seconds after the jailer started it, which is not reliably
# long enough for a watcher to land a /proc read. This holds the machine open
# and weakens nothing: the deadline still applies, and a guest that hangs past
# it is attack 3.
echo "holding_open=8s"
sleep 8
"""

_FILL_THE_WORK_DISK = r"""
echo "quota_mib_configured={quota}"
outcome=$(dd if=/dev/zero of=/work/gdpval-filler bs=1M count={overshoot} 2>&1; echo "rc=$?")
rm -f /work/gdpval-filler
sync
echo "$outcome" | tail -3
"""

_ALLOCATE_PAST_THE_BOUND = r"""
grep MemTotal /proc/meminfo

# Two things about the shape of this attack, both learned from a run where the
# bound held and the attack reported nothing, which reads as a failure.
#
# The allocation has to be charged to the process making it. tmpfs pages are
# shmem and count against no process's RSS, so when the machine filled, the
# kernel's OOM killer found nothing large to pick and took a bystander. And the
# reporter cannot be a child: `rc=$?` inside a command substitution runs in a
# fork, and that fork was the bystander it took. The attack destroyed its own
# evidence.
#
# So: anonymous memory, touched a page at a time, which makes the allocator the
# largest thing in the machine and the unambiguous target; and the report is
# made by the top-level shell, which allocates nothing and is never picked.
cat > /work/gdpval-allocate.py <<'PY'
import sys

step = 64 * 1024 * 1024
target = {overshoot} * 1024 * 1024
held = []
allocated = 0
while allocated < target:
    # bytearray(n) is calloc, and calloc over a fresh mapping is a promise of
    # zeroes rather than pages. Untouched it would allocate address space and
    # never reach the bound at all.
    block = bytearray(step)
    for offset in range(0, step, 4096):
        block[offset] = 1
    held.append(block)
    allocated += step
    sys.stdout.write("allocated_mib=%d\n" % (allocated // (1024 * 1024)))
    sys.stdout.flush()
sys.stdout.write("ALLOCATED_ALL\n")
PY
python3 /work/gdpval-allocate.py &
allocator=$!
wait "$allocator"
echo "rc=$?"
rm -f /work/gdpval-allocate.py
"""

_HANG_FOREVER = """
echo 'about to hang on purpose'
while true; do sleep 5; done
"""


def guest_commands(policy: Mapping[str, Any] = REQUIRED_MICROVM_POLICY) -> dict[str, str]:
    """The script each boot runs, with the overshoot sized from the rule itself.

    Taken from the policy rather than written as a number, so that raising a
    bound cannot silently leave an attack probing below it — which would be an
    attack that passes because it never reached the limit.
    """
    quota = int(policy["workdir_quota_mib"])
    memory = int(policy["memory_mib"])
    return {
        BOOT_PROBES: _QUIET_PROBES,
        BOOT_WORKDIR: _FILL_THE_WORK_DISK.format(
            quota=quota, overshoot=quota * 2
        ),
        BOOT_MEMORY: _ALLOCATE_PAST_THE_BOUND.format(overshoot=int(memory * 1.5)),
        BOOT_WALL_CLOCK: _HANG_FOREVER,
    }


# --------------------------------------------------------------------------
# how each attack is judged
# --------------------------------------------------------------------------


def _stdout(evidence: Mapping[str, Any], boot: str) -> str | None:
    boot_result = (evidence.get("boots") or {}).get(boot)
    if not isinstance(boot_result, Mapping):
        return None
    return ((boot_result.get("results") or {}).get("/out/stdout")) or None


def _network(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    output = _stdout(evidence, BOOT_PROBES)
    if output is None:
        return False, "the probe guest returned nothing, so nothing was observed"
    if "connect_probe=CONNECTED" in output:
        return False, "the guest opened a connection to 1.1.1.1:443"
    interfaces = {
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.startswith(("=", " "))
        and line.strip() in {"lo", "eth0", "ens3", "tap0"}
    }
    beyond_loopback = interfaces - {"lo"}
    if beyond_loopback:
        return False, f"the guest has interfaces beyond loopback: {sorted(beyond_loopback)}"
    if "connect_probe=" not in output:
        return False, "the connection probe did not report, so it did not run"
    return True, (
        "no interface but loopback in /proc/net/dev and the connection attempt "
        f"failed: {_line_with(output, 'connect_probe=')}"
    )


def _read_only_root(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    output = _stdout(evidence, BOOT_PROBES)
    if output is None:
        return False, "the probe guest returned nothing, so nothing was observed"
    if "rootfs_write=SUCCEEDED" in output:
        return False, "a write to / succeeded inside the guest"
    if "rootfs_write=refused" not in output:
        return False, "the write probe did not report, so it did not run"
    mount_line = _line_with(output, " / ")
    if mount_line and " ro," not in mount_line and not mount_line.endswith(" ro"):
        # The mount table is the second half of the same rule. A guest that
        # could not write because of a permission bit, on a root the kernel
        # mounted read-write, is one remount away from writing.
        return False, f"the write failed but / is not mounted read-only: {mount_line}"
    return True, f"the write was refused and / is mounted read-only: {mount_line}"


def _memory_bound(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    output = _stdout(evidence, BOOT_MEMORY)
    if output is None:
        return False, "the memory guest returned nothing, so nothing was observed"
    total_kib = _mem_total_kib(output)
    if total_kib is None:
        return False, "MemTotal did not come back, so the bound was not observed"
    allowed_mib = int(REQUIRED_MICROVM_POLICY["memory_mib"])
    if total_kib // 1024 > allowed_mib:
        return False, (
            f"the guest sees {total_kib // 1024} MiB, which is more than the "
            f"{allowed_mib} MiB the rule allows"
        )
    reached = _high_water_mib(output)
    if reached is not None and reached > allowed_mib:
        # Every one of those pages was written to, and a guest with no swap
        # cannot reclaim anonymous memory it has touched. Getting past the
        # number is the escape whatever the process's exit status ends up being.
        return False, (
            f"the guest held {reached} MiB of touched anonymous memory, past the "
            f"{allowed_mib} MiB the rule allows"
        )
    if "rc=0" in output or "ALLOCATED_ALL" in output:
        return False, (
            f"an allocation of {int(allowed_mib * 1.5)} MiB succeeded inside a "
            f"machine bounded to {allowed_mib} MiB"
        )
    if "rc=" not in output:
        return False, "the allocation probe did not report, so it did not run"
    got_to = f", having reached {reached} MiB" if reached is not None else ""
    return True, (
        f"the guest sees {total_kib // 1024} MiB against a {allowed_mib} MiB "
        f"bound and the over-allocation was stopped{got_to}: "
        f"{_line_with(output, 'rc=')}"
    )


def _workdir_quota(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    output = _stdout(evidence, BOOT_WORKDIR)
    if output is None:
        return False, "the quota guest returned nothing, so nothing was observed"
    if "rc=0" in output:
        quota = REQUIRED_MICROVM_POLICY["workdir_quota_mib"]
        return False, f"writing {int(quota) * 2} MiB into a {quota} MiB disk succeeded"
    if "rc=" not in output:
        return False, "the fill probe did not report, so it did not run"
    return True, (
        "the write past the quota failed: " + (_line_with(output, "rc=") or "")
    )


def _wall_clock(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    boot = (evidence.get("boots") or {}).get(BOOT_WALL_CLOCK)
    if not isinstance(boot, Mapping):
        return False, "the hanging guest was not run, so nothing was observed"
    if not boot.get("stopped_by_the_deadline"):
        return False, (
            f"the guest that hangs on purpose ended as {boot.get('outcome')!r} "
            "rather than being stopped by the deadline"
        )
    if not boot.get("teardown", {}).get("all_gone"):
        return False, "the deadline fired but the machine's chroot survived it"
    return True, (
        f"the guest hung and was stopped after {boot.get('ran_for_seconds')}s "
        f"against a {boot.get('deadline_seconds')}s bound, and its chroot is gone"
    )


def _unprivileged_host_process(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    """Read from the host, because the guest cannot see the thing being ruled on.

    Inside the machine PID 1 is root and is meant to be. The rule is about the
    Firecracker process the jailer left running on the host after it dropped
    privilege, and a test that looked for an unprivileged uid inside the guest
    would pass on a launcher that had never dropped anything.
    """
    watch = _host_watch(evidence)
    if watch is None:
        return False, "the host-side process was not looked at while it ran"
    uid = watch.get("real_uid")
    if uid is None:
        return False, "the process's uid did not come back, so it was not observed"
    if int(uid) == 0:
        return False, "the Firecracker process is still running as root on the host"
    expected = watch.get("expected_uid")
    if expected is not None and int(uid) != int(expected):
        return False, f"the process runs as uid {uid}, not the jail account's {expected}"
    groups = watch.get("supplementary_groups") or []
    if groups:
        return False, f"the process carries supplementary groups {groups}"
    return True, (
        f"the host-side Firecracker process runs as uid {uid} with no "
        "supplementary groups"
    )


def _no_credentials_inherited(evidence: Mapping[str, Any]) -> tuple[bool, str]:
    """Both halves. The jailer covers them differently and only one is unconditional.

    The environment is wiped whatever else is passed. The three standard
    descriptors are redirected by ``--daemonize`` and by nothing else, so an
    attack that checked the environment alone would pass on a launcher that had
    quietly dropped that flag — which is exactly the regression this is for.
    """
    watch = _host_watch(evidence)
    if watch is None:
        return False, "the host-side process was not looked at while it ran"
    if watch.get("environment_seen") is None:
        return False, "the process's environment did not come back"
    leaked = watch.get("canaries_in_environment") or []
    if leaked:
        return False, f"the process's environment carries {leaked}"
    descriptors = watch.get("descriptors")
    if descriptors is None:
        return False, (
            "the process's open descriptors did not come back, and the "
            "environment alone is not the rule"
        )
    pointing_out = watch.get("descriptors_reaching_the_orchestrator") or []
    if pointing_out:
        return False, f"descriptors still reach the orchestrator: {pointing_out}"
    standard = watch.get("standard_descriptors") or {}
    not_closed = {
        fd: target
        for fd, target in standard.items()
        if target is not None and target != "/dev/null"
    }
    if not_closed:
        return False, (
            f"the standard descriptors are not all /dev/null: {not_closed}. "
            "--daemonize is the only thing that redirects them, and without it "
            "the guest's console is whatever the orchestrator was writing to"
        )
    guest = _stdout(evidence, BOOT_PROBES)
    if guest is None:
        return False, "the guest half of the probe returned nothing"
    if "guest_env=CARRIES SOMETHING" in guest:
        return False, "the guest's own environment carries a credential-shaped name"
    return True, (
        f"the host process's environment holds {watch.get('environment_seen')} "
        f"entries with none of the canaries, its {len(descriptors)} descriptors "
        "reach nothing of the orchestrator's, all three standard ones are "
        "/dev/null, and the guest's environment is clean"
    )


def _host_watch(evidence: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for boot in (evidence.get("boots") or {}).values():
        if isinstance(boot, Mapping) and isinstance(boot.get("watched"), Mapping):
            return boot["watched"]
    return None


def _line_with(output: str, needle: str) -> str | None:
    for line in output.splitlines():
        if needle in line:
            return line.strip()
    return None


def _mem_total_kib(output: str) -> int | None:
    line = _line_with(output, "MemTotal")
    if not line:
        return None
    for part in line.split():
        if part.isdigit():
            return int(part)
    return None


def _high_water_mib(output: str) -> int | None:
    """The most the allocator was holding, as it last reported it.

    Printed as it goes rather than at the end, because the end is exactly what a
    process the kernel decided to kill does not get to reach. It is also the
    only number that says how far the guest got, as opposed to merely that
    something stopped it.
    """
    marks = [
        int(line.split("=", 1)[1])
        for line in output.splitlines()
        if line.startswith("allocated_mib=") and line.split("=", 1)[1].isdigit()
    ]
    return max(marks) if marks else None


ATTACKS: tuple[dict[str, Any], ...] = (
    {
        "number": 1,
        "id": "workdir-quota",
        "rule": "workdir_quota_mib",
        "boot": BOOT_WORKDIR,
        "observed": "guest",
        "what_it_tries": "write twice the quota into the ephemeral work disk",
        "judge": _workdir_quota,
    },
    {
        "number": 2,
        "id": "memory",
        "rule": "memory_mib",
        "boot": BOOT_MEMORY,
        "observed": "guest",
        "what_it_tries": "allocate half again the memory bound inside the guest",
        "judge": _memory_bound,
    },
    {
        "number": 3,
        "id": "wall-clock",
        "rule": "wall_clock_seconds",
        "boot": BOOT_WALL_CLOCK,
        "observed": "host",
        "what_it_tries": "never finish",
        "judge": _wall_clock,
    },
    {
        "number": 4,
        "id": "network",
        "rule": "network",
        "boot": BOOT_PROBES,
        "observed": "guest",
        "what_it_tries": "find an interface and open a connection through it",
        "judge": _network,
    },
    {
        "number": 5,
        "id": "read-only-root",
        "rule": "rootfs",
        "boot": BOOT_PROBES,
        "observed": "guest",
        "what_it_tries": "write a file into the root filesystem",
        "judge": _read_only_root,
    },
    {
        "number": 6,
        "id": "privileged-user",
        "rule": "user",
        "boot": BOOT_PROBES,
        "observed": "host",
        "what_it_tries": (
            "be a host-side process that kept root, which the guest cannot see "
            "and so cannot be asked about"
        ),
        "judge": _unprivileged_host_process,
    },
    {
        "number": 7,
        "id": "inherited-credentials",
        "rule": "credentials",
        "boot": BOOT_PROBES,
        "observed": "host and guest",
        "what_it_tries": (
            "reach a token the orchestrator holds, through the environment and "
            "through an inherited descriptor"
        ),
        "judge": _no_credentials_inherited,
    },
)


def judge_all(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Turn what was collected into seven verdicts and one overall answer.

    Seven passes is the condition. Six and a note is a failure, and so is seven
    verdicts where one of them was reached without evidence — which is why each
    verdict carries the sentence that argued it rather than only a boolean.
    """
    verdicts = []
    for attack in ATTACKS:
        judge: Callable[[Mapping[str, Any]], tuple[bool, str]] = attack["judge"]
        try:
            stopped, why = judge(evidence)
        except Exception as failure:  # noqa: BLE001 - an unjudgeable attack failed
            stopped, why = False, f"the attack could not be judged: {failure!r}"
        verdicts.append(
            {
                "number": attack["number"],
                "id": attack["id"],
                "rule_it_enforced": attack["rule"],
                "rule_value": REQUIRED_MICROVM_POLICY.get(attack["rule"]),
                "observed": attack["observed"],
                "what_it_tried": attack["what_it_tries"],
                "stopped": bool(stopped),
                "evidence": why,
            }
        )
    stopped_count = sum(1 for verdict in verdicts if verdict["stopped"])
    return {
        "schema_version": "1.0",
        "verdicts": verdicts,
        "stopped": stopped_count,
        "attempted": len(ATTACKS),
        "all_seven_stopped": stopped_count == len(ATTACKS),
        "escapes": [v["id"] for v in verdicts if not v["stopped"]],
        "how_absent_evidence_is_treated": (
            "as a failure of that attack. A probe that did not run and a rule "
            "that did not hold leave the same silence, and calling silence a "
            "pass would let a guest that never booted sweep all seven."
        ),
    }
