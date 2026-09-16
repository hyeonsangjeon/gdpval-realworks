"""Whether hardware virtualisation actually works here, by using it once.

Every reading this repository takes of ``/dev/kvm`` stops short of the thing
that matters. :func:`core.agentic_v2_microvm.inspect_microvm_readiness` asks
whether the path is a character device the process may read and write, and
``read_the_host`` in ``scripts/run_agentic_c2_first_boot.py`` asks only whether
the path exists. Both are answers about a filename. Neither opens it.

On the execution host that distinction never came up, because the process there
is root and the device works. It comes up on a GitHub-hosted runner, which is
the machine the same-host arrangement depends on, and where the two can come
apart in three ways this module separates:

* the node is present and the account the job runs as is not in the ``kvm``
  group, so the open is refused — ``os.access`` reads the permission bits with
  the *real* uid and can answer yes to a device that will not open;
* the node opens and is not the interface it looks like, so the version ioctl
  refuses;
* the node opens and answers its version and will still not create a machine,
  which is what a host with the module loaded but nested virtualisation turned
  off looks like from userspace.

The third is the one worth the trouble. It is indistinguishable from a working
host by every check already in the tree, and the place it would otherwise have
surfaced is the first ``exec_run`` of a cohort that has already been paid for.

So this module asks the device to make an empty machine, and closes it. No
memory is given to a guest, no vcpu is started, no image is read, nothing is
installed and no network is touched. What it costs is one file descriptor for
the length of one function call.

**The readings are separable and reported separately.** A caller that learns
"this host cannot host a guest" is owed which of the three it was, because the
first is fixed by a udev rule on the runner and the third cannot be fixed from
inside the job at all.

**Not-measured is not a pass.** Every field is tri-state and ``None`` means the
reading was not reached. :attr:`KvmProbe.hardware_is_usable_here` is true only
when a machine was actually made, so a probe that fell over answers no.

The seams — ``opener``, ``ask``, ``closer``, ``device`` — exist because the
machine this is most often run on cannot exercise any of this: kernel 3.10 has
no ``/dev/kvm`` here, so without them every test of this module would skip, and
a skipped test says nothing about the branch it was written for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

KVM_DEVICE = "/dev/kvm"

KVM_GET_API_VERSION = 0xAE00
"""``_IO(KVMIO, 0x00)``. Answers 12 on every kernel that carries the interface."""

KVM_CREATE_VM = 0xAE01
"""``_IO(KVMIO, 0x01)``. Answers a descriptor for a machine with nothing in it."""

THE_API_VERSION_THIS_EXPECTS = 12
"""What ``KVM_GET_API_VERSION`` has answered since the interface was stabilised.

Linux's own ``Documentation/virt/kvm/api.rst`` calls 12 the stable version and
says applications should refuse anything else rather than try to cope, so a
different number is reported as not usable rather than quietly accepted.
"""


@dataclass(frozen=True)
class KvmProbe:
    """What using the device once established, with each step kept apart."""

    device: str
    present: bool
    opened: bool | None
    api_version: int | None
    made_a_machine: bool | None
    because: str
    ownership: dict[str, Any] | None = None

    @property
    def hardware_is_usable_here(self) -> bool:
        """True only when a machine was made. Anything else is no, not maybe."""
        return self.made_a_machine is True

    def as_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "present": self.present,
            "opened": self.opened,
            "api_version": self.api_version,
            "made_a_machine": self.made_a_machine,
            "hardware_is_usable_here": self.hardware_is_usable_here,
            "because": self.because,
            "ownership": self.ownership,
        }


def probe_kvm(
    *,
    device: str | Path = KVM_DEVICE,
    opener: Callable[..., int] | None = None,
    ask: Callable[[int, int, int], int] | None = None,
    closer: Callable[[int], None] | None = None,
    stat: Callable[[str], os.stat_result] | None = None,
    running_as: Callable[[], tuple[int, list[int]]] | None = None,
) -> KvmProbe:
    """Open the device, ask its version, make one empty machine, close both.

    Returns what happened rather than raising, because every failure here is a
    finding about the host and a caller needs to report it rather than crash on
    it. The one thing not caught is a caller's own seam raising something that
    is not an :class:`OSError`; that is a bug in the test, not a host fact.
    """
    import fcntl

    opener = os.open if opener is None else opener
    ask = fcntl.ioctl if ask is None else ask
    closer = os.close if closer is None else closer
    stat = os.stat if stat is None else stat
    running_as = _who_this_is if running_as is None else running_as

    path = str(device)
    ownership = _ownership(path, stat=stat, running_as=running_as)
    if ownership is None:
        return KvmProbe(
            device=path,
            present=False,
            opened=None,
            api_version=None,
            made_a_machine=None,
            because=(
                f"there is no {path}, so this machine exposes no hardware "
                "virtualisation to userspace and no guest can be started on it"
            ),
        )

    try:
        handle = opener(path, os.O_RDWR | os.O_CLOEXEC)
    except PermissionError as denied:
        return KvmProbe(
            device=path,
            present=True,
            opened=False,
            api_version=None,
            made_a_machine=None,
            ownership=ownership,
            because=(
                f"{path} is present and this process may not open it "
                f"({denied.strerror}). Being able to see the device and being "
                "allowed to use it are different things: the node is commonly "
                "mode 0660 owned by group 'kvm', and the account a job runs as "
                "need not be in that group"
            ),
        )
    except OSError as failed:
        return KvmProbe(
            device=path,
            present=True,
            opened=False,
            api_version=None,
            made_a_machine=None,
            ownership=ownership,
            because=f"{path} is present and would not open ({failed})",
        )

    try:
        return _what_the_open_device_says(
            handle, path=path, ownership=ownership, ask=ask, closer=closer
        )
    finally:
        closer(handle)


def _what_the_open_device_says(
    handle: int,
    *,
    path: str,
    ownership: dict[str, Any],
    ask: Callable[[int, int, int], int],
    closer: Callable[[int], None],
) -> KvmProbe:
    """The two readings that need the device already open."""
    try:
        version = ask(handle, KVM_GET_API_VERSION, 0)
    except OSError as refused:
        return KvmProbe(
            device=path,
            present=True,
            opened=True,
            api_version=None,
            made_a_machine=None,
            ownership=ownership,
            because=(
                f"{path} opened and would not answer its API version "
                f"({refused}), so whatever opened is not the interface a guest "
                "would be started through"
            ),
        )

    if version != THE_API_VERSION_THIS_EXPECTS:
        return KvmProbe(
            device=path,
            present=True,
            opened=True,
            api_version=version,
            made_a_machine=None,
            ownership=ownership,
            because=(
                f"{path} answered API version {version}, and the stable version "
                f"this and Firecracker are written against is "
                f"{THE_API_VERSION_THIS_EXPECTS}. Linux's own documentation "
                "says to refuse a different one rather than try to cope"
            ),
        )

    try:
        machine = ask(handle, KVM_CREATE_VM, 0)
    except OSError as refused:
        return KvmProbe(
            device=path,
            present=True,
            opened=True,
            api_version=version,
            made_a_machine=False,
            ownership=ownership,
            because=(
                f"{path} opened and answered its version and then refused to "
                f"create a machine ({refused}). This is the reading that "
                "separates a host which merely exposes the device from one "
                "where hardware virtualisation is actually available to this "
                "process, and it is the only one of the three that cannot be "
                "fixed from inside the job"
            ),
        )

    closer(machine)
    return KvmProbe(
        device=path,
        present=True,
        opened=True,
        api_version=version,
        made_a_machine=True,
        ownership=ownership,
        because=(
            f"{path} opened, answered API version {version}, and created an "
            "empty machine which was closed again. Hardware virtualisation is "
            "available to this process"
        ),
    )


def _ownership(
    path: str,
    *,
    stat: Callable[[str], os.stat_result],
    running_as: Callable[[], tuple[int, list[int]]],
) -> dict[str, Any] | None:
    """Mode, owner and who is asking — for a reader working out *why* not.

    ``None`` when the device is not there at all, which is the one case where
    there is nothing to describe.
    """
    try:
        seen = stat(path)
    except OSError:
        return None
    uid, groups = running_as()
    return {
        "uid": seen.st_uid,
        "gid": seen.st_gid,
        "mode": oct(seen.st_mode & 0o7777),
        "this_process_runs_as": {"uid": uid, "groups": sorted(groups)},
    }


def _who_this_is() -> tuple[int, list[int]]:
    return os.getuid(), list(os.getgroups())
