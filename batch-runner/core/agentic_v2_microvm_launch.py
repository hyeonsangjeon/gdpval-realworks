"""The containment rules, turned into the arguments that would apply them.

Every rule in :data:`core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY` has been
written down since 2026-08-26 and applied by nothing. That gap is what
core/agentic_v2_containment_readiness.py reports and what stage C exists to
close: a rule nobody turns into an argument is not a rule that is met, it is a
rule that is unenforced, and a report that confuses the two is worse than no
report.

This module closes the first half of it. It reads the policy and produces the
arguments ``jailer`` and ``firecracker`` would actually be given — and it starts
nothing. No process is spawned, no file is written, no directory is created. It
returns a document. Running that document is stage C2's job, on a host that has
been measured, and keeping the two apart is deliberate: the mapping from rule to
argument is the part that can be checked here, on a machine that could not host
a virtual machine if it tried.

**Why a builder can be checked when a boot cannot.** The tests beside this file
read the built arguments and fail when a rule is missing from them. That is a
real check with a real failure mode — the one this stage is named for, a rule
that reads as enforced and is not — and it needs no hardware. What it does not
do is prove the arguments have the effect their names suggest. Only C2 and C3
can do that, and they say so.

**This does not become a fourth copy of the policy.** core/agentic_v2_microvm.py
held containment values as literals, which made four places stating one set of
rules; that copy is taken with this change, and it reads the policy now.
:data:`_WHAT_THIS_BUILDER_CAN_EXPRESS` below is not a fifth. It does not say
what a rule is — it says which values this builder knows how to turn into an
argument, and anything outside it is a refusal rather than a different set of
arguments. A copy asserts the rule; a reach asserts the builder.

**Everything here was read from Firecracker v1.13.1**, the version stage B found
installed on the Azure dev host, rather than from the development branch where a
flag can exist that the deployed binary does not have. Four readings shaped the
result and none of them was obvious from the policy:

* The jailer's chroot is ``<chroot-base>/<exec-file-name>/<id>/root``, and the
  configuration file *and every path inside it* must be valid **relative to the
  jailed Firecracker**. So the configuration names in-jail paths, and the plan
  carries a separate list of what has to be placed inside the jail first.
* ``--no-api`` exists, takes no value, and requires ``--config-file``. Without
  it Firecracker serves its whole API on a socket for the life of the machine,
  and every device pinned below can be added back through it after boot —
  including ``/snapshot/load``. Pinning a device in a configuration file is a
  statement about start-up; ``--no-api`` is what makes it a statement about the
  run.
* ``--resource-limit fsize=`` is documented in **bytes**.
* The PID file is written whether or not ``--new-pid-ns`` is passed — the plan
  for this stage said otherwise and was corrected. What ``--new-pid-ns`` buys is
  the namespace; the file is written in both branches, at in-jail
  ``/firecracker.pid``, which is ``<chroot-dir>/firecracker.pid`` from outside.

**Two things this module cannot express, named rather than papered over.**

*The policy has no rule about processor share.* It bounds memory, disk, clock,
network, filesystem, user and credentials, and says nothing about how many
virtual CPUs a command gets. Firecracker requires the number, so it is taken as
an argument from the caller and validated as a positive integer — but a caller
choosing it freely is a real gap in a containment that bounds memory by rule. It
is not fixed here: adding a rule belongs in a change of its own, the same way
the credential rule was added, not in the change that discovers it.

*The jail always contains a ``/dev/net/tun`` device node.* The jailer creates it
with ``mknod`` unconditionally, before it knows anything about the
configuration. ``network: none`` therefore rests on no interface being
configured and no network namespace being joined, not on the device being
absent. That is worth knowing before someone reads the node as a network and
before someone reads its absence as the mechanism.

Nothing here calls a model, runs a command, or spends money.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from core.agentic_v2_guest_image import GUEST_INIT_PATH
from core.agentic_v2_microvm import inspect_microvm_readiness
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY, canonical_sha256

A_MEBIBYTE = 1024 * 1024

JAILER_DEFAULT_CHROOT_BASE = "/srv/jailer"
"""Where the jailer builds chroots when it is not told otherwise.

Its own documented default. Repeated here because the plan has to name the
directory the images are placed in, and a plan that inherited the default
silently would name a directory nobody chose.
"""

HOST_SIDE_MEMORY_OVERHEAD_MIB = 256
"""How much the host-side memory bound is allowed above the guest's own.

Picked, not derived, and it has to be above zero for the bound to be correct at
all. ``--cgroup memory.max=`` bounds the whole Firecracker process, which is the
guest's memory *plus* the virtual machine monitor's own footprint. A host bound
set equal to the guest bound would kill the monitor rather than the command that
exceeded its memory, which is the same class of mistake as a disk smaller than
the writes the tool layer accepts: a limit that fires as the wrong limit.

Generous on purpose. The guest cannot exceed ``memory_mib`` regardless — that
bound is enforced inside the machine — so this one is a backstop against the
monitor itself, not a second ceiling on the command.
"""

IN_JAIL_KERNEL = "/vmlinux"
IN_JAIL_ROOTFS = "/rootfs.ext4"
IN_JAIL_WORK_DISK = "/work.ext4"
IN_JAIL_CONFIG = "/vmconfig.json"

PID_FILE_EXTENSION = ".pid"
"""The jailer's own suffix, appended to the exec file's name and not to a word.

``save_exec_file_pid`` builds this path as ``chroot_exec_file`` plus ``.pid``,
and ``chroot_exec_file`` is ``/`` joined to the **exec file's own name**. So a
binary at ``/opt/firecracker-v1.13.1`` produces ``/firecracker-v1.13.1.pid``,
not ``/firecracker.pid``. This was a fixed constant here until it was checked
against the source: the name only has to *contain* ``firecracker``, which is the
rule the jailer enforces on ``--exec-file``, and every other spelling of it
would have produced a plan whose deadline pointed at a file that never appears.

That is the failure this stage is about, in the one field that decides whether
``wall_clock_seconds`` can be enforced at all — a limit with no process to stop
is a limit in name. Derived from the binary now, by
:func:`_pid_file_the_jailer_will_write`.
"""

DEVICES_THAT_MUST_BE_ABSENT: dict[str, str] = {
    "balloon": "memory_mib — a balloon device reshapes guest memory at runtime, "
    "and it is the only mechanism in this Firecracker that does",
    "mmds-config": "network: none, by a route that is not a network interface — "
    "MMDS is a metadata service the guest reads over HTTP, and it is the "
    "standard way host-side data is handed to a guest",
    "vsock": "network: none — a host-to-guest socket is a channel whether or "
    "not it is a network interface",
}
"""Three devices no rule names, each of which can defeat a rule that is named.

Read off Firecracker's own configuration fixtures rather than assumed. They are
not added to the policy because they are not rules about what the containment
allows; they are devices that must be absent for the rules it already has to
mean what they say. If that reasoning is wrong, the fix is a change that adds
them to the policy, not a quiet reliance on a default.
"""

FLAGS_THAT_WOULD_WEAKEN_THE_JAIL: dict[str, str] = {
    "--netns": "network: none — joining a network namespace gives the machine "
    "the interfaces in it",
    "--no-seccomp": "every rule — Firecracker's own documentation calls this "
    "'not recommended', and it removes the syscall filter the containment "
    "sits on top of",
    "--metadata": "network: none — this loads MMDS content from a file, which "
    "is the mmds-config device arriving as a command-line flag instead",
}
"""Flags that exist, would be accepted, and would each undo a rule.

Checked by name against the built arguments rather than trusted to be absent,
because the way a boundary is usually lost is that somebody adds a flag to make
one thing work and nobody reads the whole command line again.
"""

CGROUP_MEMORY_FILE_BY_VERSION: dict[int, str] = {
    1: "memory.limit_in_bytes",
    2: "memory.max",
}
"""What the memory bound is called in each cgroup hierarchy.

The jailer takes ``--cgroup <cgroup_file>=<value>`` and writes the value to that
file under the hierarchy ``--cgroup-version`` selects. The file name is supplied
by the caller and is *not* translated: its own parser requires
``<controller>.<property>`` and takes the rest on trust. So a launcher that
passes ``--cgroup-version 2`` with v1's name asks for a file that does not exist
in that hierarchy — a memory bound that reads as enforced and is not, arriving
through a name rather than through a deletion.

``--cgroup-version`` itself defaults to ``1`` in v1.13.1, while the host stage B
measured runs Ubuntu 24.04, which has used the v2 unified hierarchy since 21.10.
So the version is passed explicitly and never inherited, and C2 reads it off the
host before anything is launched rather than assuming the distribution default.
"""

_WHAT_THIS_BUILDER_CAN_EXPRESS: dict[str, frozenset[Any]] = {
    "required": frozenset({True}),
    "runtime": frozenset({"firecracker"}),
    "network": frozenset({"none"}),
    "rootfs": frozenset({"read-only"}),
    "workdir": frozenset({"ephemeral-quota"}),
    "user": frozenset({"jailer-unprivileged"}),
    "credentials": frozenset({"none-inherited"}),
    "on_breach": frozenset({"stop-and-report"}),
}
"""Which values of each rule this builder knows how to turn into an argument.

Not a copy of the policy. The policy says what the rule *is*; this says what
this module can *do*, and every value outside it is a refusal rather than a
different set of arguments. The difference matters when a rule is weakened: a
copy would be updated to match and go on emitting, where a reach makes the
builder stop and name the rule it cannot express.

The three numeric rules are absent because their reach is a shape rather than a
set — a positive integer — and they are checked as one.
"""

_NUMERIC_RULES = ("workdir_quota_mib", "memory_mib", "wall_clock_seconds")


class LaunchRefused(ValueError):
    """Refusal to build arguments, naming the rule that could not be expressed.

    ``on_breach: stop-and-report`` is a rule about what happens when a limit is
    exceeded, and the same answer applies one step earlier: a builder that
    cannot express a rule stops and says which one, rather than emitting the
    other ten and leaving the eleventh to be noticed by whoever reads the
    command line.
    """

    def __init__(self, rule: str, why: str) -> None:
        super().__init__(f"containment rule {rule!r} cannot be applied: {why}")
        self.rule = rule
        self.why = why


def build_launch_plan(
    *,
    vm_id: str,
    firecracker_binary: str | Path,
    kernel_path: str | Path,
    rootfs_path: str | Path,
    work_disk_path: str | Path,
    uid: int,
    gid: int,
    vcpu_count: int,
    cgroup_version: int,
    chroot_base: str | Path = JAILER_DEFAULT_CHROOT_BASE,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Turn the containment rules into the arguments that would apply them.

    Returns a document and starts nothing. Every rule in the policy appears in
    ``rules_applied`` with a sentence saying where it went, and the builder
    refuses rather than returning a document with a rule missing from it.

    ``vcpu_count`` is taken from the caller because the policy does not bound
    processor share — see the module docstring, where that gap is named rather
    than filled here.

    ``cgroup_version`` has no default on purpose. Inheriting the jailer's own
    default of ``1`` on a host running the v2 hierarchy is exactly the failure
    this module is meant to make impossible.
    """
    rules = dict(REQUIRED_MICROVM_POLICY if policy is None else policy)

    missing = sorted(set(REQUIRED_MICROVM_POLICY) - set(rules))
    if missing:
        raise LaunchRefused(
            missing[0],
            "it is not in the policy this builder was given, and a containment "
            "with a rule missing is not the containment that was written down",
        )
    unknown = sorted(set(rules) - set(REQUIRED_MICROVM_POLICY))
    if unknown:
        raise LaunchRefused(
            unknown[0],
            "the policy has gained a rule this builder does not know how to "
            "turn into an argument. Teach it here before relying on these "
            "arguments, rather than emitting the rest without it",
        )

    for rule, reach in _WHAT_THIS_BUILDER_CAN_EXPRESS.items():
        if rules[rule] not in reach:
            raise LaunchRefused(
                rule,
                f"this builder can express {sorted(map(repr, reach))} and the "
                f"policy says {rules[rule]!r}",
            )
    for rule in _NUMERIC_RULES:
        value = rules[rule]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise LaunchRefused(
                rule, f"a limit has to be a positive whole number, not {value!r}"
            )

    _refuse_a_bad_identity(vm_id)
    firecracker_binary = Path(firecracker_binary)
    if rules["runtime"] not in firecracker_binary.name:
        raise LaunchRefused(
            "runtime",
            f"the jailer requires the name of its --exec-file to contain "
            f"{rules['runtime']!r}, and it was given "
            f"{firecracker_binary.name!r}",
        )
    for label, value in (("uid", uid), ("gid", gid)):
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise LaunchRefused(
                "user",
                f"{label} {value!r} is not an unprivileged account — 0 is root "
                "and anything else here is not an account at all",
            )
    if not isinstance(vcpu_count, int) or isinstance(vcpu_count, bool):
        raise LaunchRefused("runtime", f"vcpu_count {vcpu_count!r} is not a number")
    if vcpu_count <= 0:
        raise LaunchRefused("runtime", f"vcpu_count {vcpu_count!r} is not a count")
    if cgroup_version not in CGROUP_MEMORY_FILE_BY_VERSION:
        raise LaunchRefused(
            "memory_mib",
            f"cgroup version {cgroup_version!r} is not one this jailer supports, "
            f"so there is no file to write the host-side memory bound to",
        )

    asset_paths = {"kernel": Path(kernel_path), "rootfs": Path(rootfs_path)}
    host_reading = inspect_microvm_readiness(asset_paths=asset_paths)
    for name in sorted(asset_paths):
        if host_reading["assets"][name]["status"] != "present":
            raise LaunchRefused(
                "runtime",
                f"the {name} image is not a readable file at "
                f"{str(asset_paths[name])!r}, so there is nothing to boot",
            )

    chroot_dir = (
        Path(chroot_base) / firecracker_binary.name / vm_id / "root"
    ).as_posix()

    config = _firecracker_configuration(rules, vcpu_count=vcpu_count)
    reopened = devices_that_would_reopen_a_closed_rule(config)
    if reopened:
        raise LaunchRefused(
            "network", "the configuration names " + ", ".join(reopened)
        )

    argv = _jailer_arguments(
        rules,
        vm_id=vm_id,
        firecracker_binary=firecracker_binary,
        chroot_base=chroot_base,
        uid=uid,
        gid=gid,
        cgroup_version=cgroup_version,
    )
    weakened = flags_that_would_weaken_the_jail(argv)
    if weakened:
        raise LaunchRefused("required", "the arguments name " + ", ".join(weakened))

    plan: dict[str, Any] = {
        "schema_version": "1.0",
        "starts_nothing": True,
        "vm_id": vm_id,
        "policy_sha256": canonical_sha256(dict(rules)),
        "host_reading_sha256": host_reading["report_sha256"],
        "host_could_run_this": host_reading["status"] == "ready_for_boot_test",
        "jailer": {"program": "jailer", "argv": argv},
        "firecracker": {"config": config},
        "place_in_jail": [
            {
                "in_jail": IN_JAIL_KERNEL,
                "how": "copy",
                "from_host": Path(kernel_path).as_posix(),
                "sha256": host_reading["assets"]["kernel"]["sha256"],
                "writable_by_the_jailed_user": False,
            },
            {
                "in_jail": IN_JAIL_ROOTFS,
                "how": "copy",
                "from_host": Path(rootfs_path).as_posix(),
                "sha256": host_reading["assets"]["rootfs"]["sha256"],
                "writable_by_the_jailed_user": False,
            },
            {
                "in_jail": IN_JAIL_WORK_DISK,
                "how": "create-empty",
                "from_host": Path(work_disk_path).as_posix(),
                "size_mib": rules["workdir_quota_mib"],
                "writable_by_the_jailed_user": True,
            },
            {
                "in_jail": IN_JAIL_CONFIG,
                "how": "write",
                "from_host": None,
                "writable_by_the_jailed_user": False,
            },
        ],
        "host_side": {
            "chroot_dir": chroot_dir,
            "pid_file": _pid_file_the_jailer_will_write(
                chroot_dir, firecracker_binary
            ),
            "deadline_seconds": rules["wall_clock_seconds"],
            "on_deadline": rules["on_breach"],
            "destroy_after_the_run": [chroot_dir],
        },
        "devices_pinned": {name: None for name in sorted(DEVICES_THAT_MUST_BE_ABSENT)},
        "rules_applied": _where_each_rule_went(cgroup_version=cgroup_version),
    }

    unaccounted = sorted(set(rules) - set(plan["rules_applied"]))
    if unaccounted:
        raise LaunchRefused(
            unaccounted[0],
            "the builder produced arguments without accounting for this rule, "
            "which is the silent drop these refusals exist to prevent",
        )

    plan["plan_sha256"] = canonical_sha256(plan)
    return plan


def _pid_file_the_jailer_will_write(chroot_dir: str, firecracker_binary: Path) -> str:
    """Where the deadline will find the process it has to be able to stop.

    Two facts from ``src/jailer/src/env.rs`` in v1.13.1, both of which have to
    hold for ``wall_clock_seconds`` to mean anything:

    The **name** is the exec file's own, with ``.pid`` appended — not the word
    ``firecracker``. The jailer requires only that the name *contain* it, so
    ``firecracker-v1.13.1`` is a legal binary that writes
    ``firecracker-v1.13.1.pid``.

    The **place** is inside the jail. ``chroot()`` runs before either call site,
    so the in-jail ``/`` is ``<chroot_dir>`` seen from the host, and the file the
    host-side deadline opens is ``<chroot_dir>/<name>.pid``.

    The PID in it is the right one to signal because ``--new-pid-ns`` is passed:
    that branch clones and records the **child's** PID, which is Firecracker.
    Without it, and with ``--daemonize``, the recorded PID is the daemonised
    grandchild's — still the right process, by a different route worth knowing
    about before somebody removes a flag and changes which one it is.
    """
    return (
        Path(chroot_dir) / (firecracker_binary.name + PID_FILE_EXTENSION)
    ).as_posix()


def rules_this_builder_accounts_for() -> frozenset[str]:
    """Which containment rules this builder turns into an argument.

    Asked by core/agentic_v2_containment_readiness.py, which reports how far the
    translation from rule to argument has got. It asks for the set rather than
    for a yes, so that a rule added to the policy and not to this builder turns
    that report's answer to no by itself, rather than waiting for somebody to
    notice.

    This is emphatically not the same question as whether the rules are applied.
    Nothing here starts a machine, and a rule with an argument nobody runs is
    still unenforced.
    """
    return frozenset(
        # Only the keys leave this function. The cgroup version changes the file
        # name inside the sentences and never which rules there are sentences
        # for, so any supported version answers this question identically.
        _where_each_rule_went(cgroup_version=sorted(CGROUP_MEMORY_FILE_BY_VERSION)[0])
    )


def devices_that_would_reopen_a_closed_rule(config: Mapping[str, Any]) -> list[str]:
    """Which of the three devices a Firecracker configuration names.

    Written as a check over a configuration rather than as an assertion about
    the one built here, so C3 can run it against a configuration read back off
    the host and get the same answer. A device is named if its key is present at
    all: ``"vsock": null`` and a configured vsock are different things to
    Firecracker and the same thing to a reader, and the reader is who this is
    for.
    """
    return [
        f"{name} (which defeats {defeats})"
        for name, defeats in sorted(DEVICES_THAT_MUST_BE_ABSENT.items())
        if name in config
    ]


def flags_that_would_weaken_the_jail(argv: list[str]) -> list[str]:
    """Which weakening flags a jailer command line carries.

    Matches ``--flag`` and ``--flag=value`` alike, because a flag written with
    an equals sign is the same flag and a check that only knew one spelling
    would be a check somebody could walk around without meaning to.
    """
    named = []
    for flag, defeats in sorted(FLAGS_THAT_WOULD_WEAKEN_THE_JAIL.items()):
        if any(item == flag or item.startswith(flag + "=") for item in argv):
            named.append(f"{flag} (which defeats {defeats})")
    return named


def _firecracker_configuration(
    rules: Mapping[str, Any], *, vcpu_count: int
) -> dict[str, Any]:
    """The configuration file, in in-jail paths, naming none of the three devices.

    Key spellings are Firecracker's own and are not tidied: the top-level
    sections are hyphenated and the fields inside them are not.

    ``network-interfaces`` is written as an empty list rather than left out.
    Firecracker's own fixtures write it that way, an absent key and an empty
    list mean the same thing to it, and stating the empty list makes
    ``network: none`` something a reader can see rather than something they have
    to notice is missing.
    """
    read_only = rules["rootfs"] == "read-only"
    return {
        "boot-source": {
            "kernel_image_path": IN_JAIL_KERNEL,
            # ``ro`` is the same rule as ``is_read_only`` below, said to the
            # kernel. Only one of the two is Firecracker's; a guest told to
            # mount a read-only drive read-write fails at boot in a way that
            # reads as a broken image rather than as an enforced rule.
            #
            # ``init=`` is named rather than left to the kernel's search. With
            # it absent the kernel tries /sbin/init, /etc/init, /bin/init and
            # then falls back to /bin/sh — and an image built from a language
            # runtime has no init but does have a shell, so the guest would
            # come up on an interactive shell attached to a console that
            # ``--daemonize`` has already sent to /dev/null. That is a machine
            # that boots, runs nothing, writes nothing and sits there until the
            # deadline stops it, which is the hardest of all the failures here
            # to tell apart from a broken image.
            "boot_args": (
                "console=ttyS0 reboot=k panic=1 pci=off root=/dev/vda"
                + (" ro" if read_only else "")
                + f" init={GUEST_INIT_PATH}"
            ),
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": IN_JAIL_ROOTFS,
                "is_root_device": True,
                "is_read_only": read_only,
            },
            {
                "drive_id": "work",
                "path_on_host": IN_JAIL_WORK_DISK,
                "is_root_device": False,
                "is_read_only": False,
            },
        ],
        "machine-config": {
            "vcpu_count": vcpu_count,
            "mem_size_mib": rules["memory_mib"],
        },
        "network-interfaces": [],
    }


def _jailer_arguments(
    rules: Mapping[str, Any],
    *,
    vm_id: str,
    firecracker_binary: Path,
    chroot_base: str | Path,
    uid: int,
    gid: int,
    cgroup_version: int,
) -> list[str]:
    """The jailer command line, with the three flags no policy key names.

    ``--new-pid-ns`` so the guest process is not in the host's PID namespace;
    ``--cgroup`` for the host-side memory bound underneath the guest-visible
    one; and ``--daemonize``, which is the step that points the three standard
    descriptors at ``/dev/null``. The jailer's own cleanup closes every other
    descriptor and clears the environment, and leaves those three open, so
    ``credentials: none-inherited`` holds by default for the environment and
    only because of this flag for the descriptors.

    ``--daemonize`` costs the console: Firecracker's standard output goes to
    ``/dev/null`` unless a log path is configured. That is acceptable only
    because it is not where results come from — deliverables are collected off
    the ephemeral work disk, which ``workdir`` already governs.

    ``--no-api`` goes to Firecracker rather than the jailer, after the ``--``.
    Without it the API socket stays live for the run and every pinned device can
    be added back through it, snapshots included; with it, the configuration
    file is the whole of what the machine will ever be.
    """
    host_bound_bytes = (
        rules["memory_mib"] + HOST_SIDE_MEMORY_OVERHEAD_MIB
    ) * A_MEBIBYTE
    return [
        "--id",
        vm_id,
        "--exec-file",
        firecracker_binary.as_posix(),
        "--uid",
        str(uid),
        "--gid",
        str(gid),
        "--chroot-base-dir",
        Path(chroot_base).as_posix(),
        "--cgroup-version",
        str(cgroup_version),
        "--cgroup",
        f"{CGROUP_MEMORY_FILE_BY_VERSION[cgroup_version]}={host_bound_bytes}",
        # In bytes, and bounding any single file the process creates. The work
        # disk image is what bounds the total; this is what stops one file
        # inside it from being the whole quota by itself. The root filesystem is
        # larger than this and is never written to, being read-only.
        "--resource-limit",
        f"fsize={rules['workdir_quota_mib'] * A_MEBIBYTE}",
        "--new-pid-ns",
        "--daemonize",
        "--",
        "--config-file",
        IN_JAIL_CONFIG,
        "--no-api",
    ]


def _where_each_rule_went(*, cgroup_version: int) -> dict[str, str]:
    """One sentence per rule, saying which argument carries it.

    The point of writing this out is the check that follows it: if a rule is in
    the policy and not in here, the builder refuses. A reader can also use it,
    but that is second — its first job is to make a dropped rule loud.

    Only the wording depends on the cgroup hierarchy. The set of rules does not,
    which is what lets :func:`rules_this_builder_accounts_for` ask this question
    without having a host to ask it about.
    """
    return {
        "required": "any rule this builder cannot express raises LaunchRefused "
        "naming that rule, rather than producing arguments without it",
        "runtime": "--exec-file names the Firecracker binary the jailer execs, "
        "and the jailer refuses a name that does not contain 'firecracker'",
        "network": "no interface is configured and no --netns is passed, so "
        "there is no interface to bring up; mmds-config and vsock are absent "
        "from the configuration and --no-api stops either being added later",
        "rootfs": "the root drive's is_read_only, and 'ro' on the kernel "
        "command line",
        "workdir": "a second drive, writable, on an image created for this run "
        "and destroyed with the jail",
        "workdir_quota_mib": "the size of that image, and --resource-limit "
        "fsize= in bytes for any single file within it",
        "memory_mib": "machine-config.mem_size_mib inside the guest, and "
        f"--cgroup {CGROUP_MEMORY_FILE_BY_VERSION[cgroup_version]}= outside it "
        f"with {HOST_SIDE_MEMORY_OVERHEAD_MIB} MiB of headroom for the monitor "
        "itself",
        "wall_clock_seconds": "host_side.deadline_seconds, enforced against the "
        "PID the jailer writes to host_side.pid_file — a guest cannot be "
        "trusted to time itself",
        "user": "--uid and --gid, both refused at 0",
        "credentials": "the jailer clears the environment and closes every "
        "descriptor but three, and --daemonize points those three at "
        "/dev/null; nothing of the orchestrator's is passed in",
        "on_breach": "LaunchRefused carries the rule by name, and "
        "host_side.on_deadline says the same for the deadline",
    }


def _refuse_a_bad_identity(vm_id: Any) -> None:
    """The jailer's own rule for an id, checked before it is put in a path.

    Alphanumerics and hyphens, at most 64 characters. Checked here because the
    id becomes a directory name under the chroot base, and an id that escaped
    that would be choosing where the jail is built.
    """
    if (
        not isinstance(vm_id, str)
        or not vm_id
        or len(vm_id) > 64
        or not all(part.isalnum() for part in vm_id.split("-") if part != "")
        or not vm_id[0].isalnum()
        or not vm_id.isascii()
    ):
        raise LaunchRefused(
            "runtime",
            f"the jailer takes an id of at most 64 alphanumerics and hyphens, "
            f"and this one is {vm_id!r}",
        )
