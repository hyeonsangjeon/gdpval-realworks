"""Every branch of the hardware-virtualisation probe, driven through its seams.

The machine these usually run on is kernel 3.10 inside a container with no
``/dev/kvm`` at all, so a test that used the real device would skip here and
say nothing about the branch it was written for. A skipped test is silent, not
passing. So each reading is driven through the injected ``opener``, ``ask``,
``closer`` and ``stat``, and the assertions are about what the probe concluded
and what it did with its descriptors — both of which are the same on any host.

The case that matters most is the one no existing check in this repository can
tell from a working host: the device is present, the permission bits allow it,
it opens, it answers its API version, and it still will not create a machine.
"""

from __future__ import annotations

import errno
import os
import stat as stat_module
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agentic_v2_kvm_probe import (  # noqa: E402
    KVM_CREATE_VM,
    KVM_GET_API_VERSION,
    THE_API_VERSION_THIS_EXPECTS,
    KvmProbe,
    probe_kvm,
)

A_DEVICE = "/dev/kvm"
THE_DEVICE_HANDLE = 7
THE_MACHINE_HANDLE = 9


def a_character_device(mode: int = 0o660, uid: int = 0, gid: int = 108) -> os.stat_result:
    """A ``stat`` answer shaped like the real device node on a runner."""
    return os.stat_result(
        (stat_module.S_IFCHR | mode, 1, 6, 1, uid, gid, 0, 0, 0, 0)
    )


class Recorder:
    """Stands in for the three calls, recording what was opened and closed."""

    def __init__(
        self,
        *,
        open_raises: OSError | None = None,
        answers: dict[int, int | OSError] | None = None,
    ) -> None:
        self.open_raises = open_raises
        self.answers = answers or {}
        self.opened: list[tuple[str, int]] = []
        self.closed: list[int] = []
        self.asked: list[tuple[int, int]] = []

    def opener(self, path: str, flags: int) -> int:
        self.opened.append((path, flags))
        if self.open_raises is not None:
            raise self.open_raises
        return THE_DEVICE_HANDLE

    def ask(self, handle: int, request: int, argument: int = 0) -> int:
        self.asked.append((handle, request))
        answer = self.answers.get(request)
        if isinstance(answer, OSError):
            raise answer
        if answer is None:
            raise AssertionError(f"the test did not say what {request:#x} answers")
        return answer

    def closer(self, handle: int) -> None:
        self.closed.append(handle)


def a_working_host(**overrides: object) -> Recorder:
    answers: dict[int, int | OSError] = {
        KVM_GET_API_VERSION: THE_API_VERSION_THIS_EXPECTS,
        KVM_CREATE_VM: THE_MACHINE_HANDLE,
    }
    answers.update(overrides.get("answers", {}))  # type: ignore[arg-type]
    return Recorder(answers=answers)


def run(recorder: Recorder, *, stat_answer: object = "device") -> KvmProbe:
    def stat(path: str) -> os.stat_result:
        if stat_answer == "device":
            return a_character_device()
        if isinstance(stat_answer, OSError):
            raise stat_answer
        raise AssertionError("unreachable")

    return probe_kvm(
        device=A_DEVICE,
        opener=recorder.opener,
        ask=recorder.ask,
        closer=recorder.closer,
        stat=stat,
        running_as=lambda: (1001, [1001, 4]),
    )


# ── the good path ─────────────────────────────────────────────────────────


def test_a_host_that_makes_a_machine_is_the_only_one_reported_usable() -> None:
    probe = run(a_working_host())

    assert probe.hardware_is_usable_here is True
    assert probe.made_a_machine is True
    assert probe.api_version == THE_API_VERSION_THIS_EXPECTS
    assert probe.opened is True
    assert probe.present is True


def test_the_machine_it_made_is_closed_and_so_is_the_device() -> None:
    recorder = a_working_host()

    run(recorder)

    assert recorder.closed == [THE_MACHINE_HANDLE, THE_DEVICE_HANDLE], (
        "both descriptors have to go back, and the machine before the device "
        "that made it"
    )


def test_it_asks_the_version_before_it_asks_for_a_machine() -> None:
    recorder = a_working_host()

    run(recorder)

    assert [request for _, request in recorder.asked] == [
        KVM_GET_API_VERSION,
        KVM_CREATE_VM,
    ]


def test_it_opens_the_device_for_writing() -> None:
    recorder = a_working_host()

    run(recorder)

    path, flags = recorder.opened[0]
    assert path == A_DEVICE
    assert flags & os.O_RDWR == os.O_RDWR, "KVM_CREATE_VM needs a writable handle"
    assert flags & os.O_CLOEXEC == os.O_CLOEXEC, (
        "nothing this probe opens should survive into a child process"
    )


# ── the three ways it comes apart ─────────────────────────────────────────


def test_a_device_that_is_not_there_is_reported_absent_not_unreadable() -> None:
    recorder = Recorder()

    probe = run(recorder, stat_answer=FileNotFoundError(errno.ENOENT, "nope"))

    assert probe.present is False
    assert probe.opened is None, "not reached is not the same as refused"
    assert probe.made_a_machine is None
    assert probe.hardware_is_usable_here is False
    assert recorder.opened == [], "there was nothing to open"


def test_a_device_this_account_may_not_open_says_so_and_shows_the_bits() -> None:
    recorder = Recorder(open_raises=PermissionError(errno.EACCES, "Permission denied"))

    probe = run(recorder)

    assert probe.present is True
    assert probe.opened is False
    assert probe.hardware_is_usable_here is False
    assert probe.ownership is not None
    assert probe.ownership["mode"] == "0o660"
    assert probe.ownership["this_process_runs_as"] == {"uid": 1001, "groups": [4, 1001]}
    assert "group" in probe.because, (
        "a refused open is fixed by a udev rule or a group, and the reading "
        "has to say which so a reader can act on it"
    )
    assert recorder.closed == [], "nothing opened, so nothing to close"


def test_a_device_that_will_not_answer_its_version_is_not_the_interface() -> None:
    recorder = Recorder(
        answers={KVM_GET_API_VERSION: OSError(errno.ENOTTY, "Inappropriate ioctl")}
    )

    probe = run(recorder)

    assert probe.opened is True
    assert probe.api_version is None
    assert probe.made_a_machine is None, "it was never asked for one"
    assert probe.hardware_is_usable_here is False
    assert recorder.closed == [THE_DEVICE_HANDLE]


def test_an_unexpected_api_version_is_refused_rather_than_coped_with() -> None:
    recorder = Recorder(answers={KVM_GET_API_VERSION: 11})

    probe = run(recorder)

    assert probe.api_version == 11
    assert probe.made_a_machine is None
    assert probe.hardware_is_usable_here is False
    assert recorder.asked == [(THE_DEVICE_HANDLE, KVM_GET_API_VERSION)], (
        "a version this was not written against is not asked for a machine"
    )


def test_the_host_that_opens_and_answers_and_still_refuses_a_machine() -> None:
    """The reading nothing else in the tree takes.

    ``inspect_microvm_readiness`` says yes to this host: the node is a character
    device and the permission bits allow a read and a write. ``read_the_host``
    in the admission generator says yes too, on ``Path.exists()`` alone. It
    opens. It answers its version. And it will not create a machine, which is
    what a host with the module loaded and hardware virtualisation unavailable
    looks like from userspace. Without this reading the place it surfaces is the
    first command of a cohort that has already been paid for.
    """
    recorder = Recorder(
        answers={
            KVM_GET_API_VERSION: THE_API_VERSION_THIS_EXPECTS,
            KVM_CREATE_VM: OSError(errno.EBUSY, "Device or resource busy"),
        }
    )

    probe = run(recorder)

    assert probe.present is True
    assert probe.opened is True
    assert probe.api_version == THE_API_VERSION_THIS_EXPECTS
    assert probe.made_a_machine is False, (
        "asked for and refused, which is a stronger finding than not asked"
    )
    assert probe.hardware_is_usable_here is False
    assert recorder.closed == [THE_DEVICE_HANDLE], (
        "no machine came back, so there is no machine descriptor to return"
    )


# ── what the answer is allowed to be ──────────────────────────────────────


@pytest.mark.parametrize(
    "made_a_machine",
    [None, False],
    ids=["not reached", "refused"],
)
def test_anything_short_of_a_machine_is_not_usable(made_a_machine: bool | None) -> None:
    probe = KvmProbe(
        device=A_DEVICE,
        present=True,
        opened=True,
        api_version=THE_API_VERSION_THIS_EXPECTS,
        made_a_machine=made_a_machine,
        because="whatever the reason was",
    )

    assert probe.hardware_is_usable_here is False, (
        "a reading that was not taken is not a reading that passed"
    )


def test_the_dictionary_carries_the_verdict_and_not_just_the_parts() -> None:
    probe = run(a_working_host())

    written = probe.as_dict()

    assert written["hardware_is_usable_here"] is True
    assert written["api_version"] == THE_API_VERSION_THIS_EXPECTS
    assert written["because"], "a reading without its reason is not reportable"
    assert set(written) == {
        "device",
        "present",
        "opened",
        "api_version",
        "made_a_machine",
        "hardware_is_usable_here",
        "because",
        "ownership",
    }
