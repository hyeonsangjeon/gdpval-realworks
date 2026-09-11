"""The sweep taken in the guest, exercised without booting one.

The container sweep's own artifact says its numbers belong to the host it ran
on — docker, cgroup v1, a 3.10 kernel — and asks to be re-taken where tasks
will actually run. :mod:`sandbox.v2.sweep_in_guest` is that re-take. What needs
proving here is not that probes work; the shared module already proves that.
It is the three things that are new:

**The driver's scratch paths really move.** In the guest the rootfs is
read-only, so a redirect to ``/tmp`` fails and every probe exits non-zero — a
sweep that would report an image with nothing in it at all. The substitution is
checked, and so is the case where the shared driver changes underneath it.

**A guest that wrote nothing is not an image with nothing in it.** Same
property the container sweep has, in a machine that has more ways to produce
it, so it is asserted again here rather than assumed to carry over.

**The committed artifact was taken in a guest.** The last class reads
``tasks/0822_saturday/guest_declared_command_sweep.json`` and asserts the guest
kernel differs from the host kernel. Running the driver on the host would
produce a plausible-looking sweep with the same probe names in it, and that one
comparison is what separates the two.

Nothing here boots anything. The boot is injected, exactly as it is in the
stage D tests.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path

import pytest

from core.agentic_v2_substrate import validate_capability_receipt
from sandbox.v2 import sweep_in_guest as module
from sandbox.v2.probe_declared_commands import MARK, DEFAULT_MANIFEST

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REAL_SWEEP = (
    BATCH_RUNNER_ROOT.parent
    / "tasks"
    / "0822_saturday"
    / "guest_declared_command_sweep.json"
)


def a_c2_record(tmp_path: Path, **changes) -> dict:
    """What C2 writes after a boot that worked, with files that exist."""
    (tmp_path / "vmlinux").write_bytes(b"not really a kernel")
    (tmp_path / "rootfs.ext4").write_bytes(b"not really a filesystem")
    record = {
        "outcome": "booted",
        "host": {
            "kernel_release": platform.release(),
            "cgroup_version": 2,
            "firecracker": "/usr/local/bin/firecracker",
            "jailer": "/usr/local/bin/jailer",
            "firecracker_version": "Firecracker v1.13.1",
        },
        "jail_account": {"uid": 997, "gid": 997},
        "images": {
            "kernel": {"path": (tmp_path / "vmlinux").as_posix(), "sha256": "a" * 64},
            "rootfs": {"path": (tmp_path / "rootfs.ext4").as_posix(), "sha256": "b" * 64},
            "image": {"pinned_digest": "sha256:" + "e" * 64},
        },
    }
    record.update(changes)
    return record


def framed(name: str, returncode: int, stdout: str = "", stderr: str = "") -> str:
    """One probe's answer, in the framing the shared driver emits."""
    return (
        f"{MARK}BEGIN {name}\n"
        f"{MARK}RC {returncode}\n"
        f"{MARK}OUT\n{stdout}\n"
        f"{MARK}ERR\n{stderr}\n"
        f"{MARK}END\n"
    )


# ── the substitution, which is the only thing this module changes ─────────


class TestTheDriverGoesToTheWorkDisk:
    def test_no_scratch_path_is_left_on_the_read_only_rootfs(self):
        probes = module.build_probes(
            json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        )
        driver = module.guest_driver(probes)
        assert "/tmp/probe." not in driver
        # Twice per probe each: once as the redirect, once as the ``head`` that
        # reads it back. A count of len(probes) would mean half the paths had
        # been missed.
        assert driver.count("/work/probe.out") == 2 * len(probes)
        assert driver.count("/work/probe.err") == 2 * len(probes)

    def test_the_environment_gives_probes_somewhere_to_write(self):
        # Without this a probe that needed a temporary file would exit
        # non-zero, and the artifact would call its command absent.
        driver = module.guest_driver([{"name": "sh", "probe": ["sh", "-c", "echo ok"]}])
        assert driver.startswith("HOME=/work\nTMPDIR=/work\nexport HOME TMPDIR\n")

    def test_every_probe_is_still_framed_the_way_the_reader_expects(self):
        probes = [
            {"name": "python3", "probe": ["python3", "--version"]},
            {"name": "sh", "probe": ["sh", "-c", "echo ok"]},
        ]
        driver = module.guest_driver(probes)
        for probe in probes:
            assert f"{MARK}BEGIN {probe['name']}" in driver

    def test_a_shared_driver_that_stopped_using_tmp_stops_this_module(
        self, monkeypatch
    ):
        # The failure this guards against is silent: the substitution would
        # match nothing, the redirect would hit a read-only filesystem, and the
        # sweep would report every command in the image as absent.
        monkeypatch.setattr(
            module, "_shell_driver", lambda probes: "echo somewhere-else\n"
        )
        with pytest.raises(module.GuestSweepRefused) as refused:
            module.guest_driver([{"name": "sh", "probe": ["sh"]}])
        assert "read-only rootfs" in str(refused.value)


# ── what it declines to sweep ─────────────────────────────────────────────


class TestWhatItRefuses:
    def test_a_host_that_has_never_booted_a_guest(self, tmp_path):
        with pytest.raises(module.GuestSweepRefused) as refused:
            module.read_the_c2_record(tmp_path / "nothing.json")
        assert "run_agentic_c2_first_boot.py first" in str(refused.value)

    def test_a_c2_run_that_recorded_a_failure(self, tmp_path):
        written = tmp_path / "c2.json"
        written.write_text(
            json.dumps(
                a_c2_record(tmp_path, outcome="host_cannot_boot", reason="no /dev/kvm")
            ),
            encoding="utf-8",
        )
        with pytest.raises(module.GuestSweepRefused) as refused:
            module.read_the_c2_record(written)
        assert "no /dev/kvm" in str(refused.value)

    def test_a_record_copied_from_another_machine(self, tmp_path):
        record = a_c2_record(tmp_path)
        record["host"]["kernel_release"] = "6.8.0-somewhere-else"
        written = tmp_path / "c2.json"
        written.write_text(json.dumps(record), encoding="utf-8")
        with pytest.raises(module.GuestSweepRefused) as refused:
            module.read_the_c2_record(written)
        assert "different machine" in str(refused.value)

    def test_a_good_record_comes_back_whole(self, tmp_path):
        written = tmp_path / "c2.json"
        written.write_text(json.dumps(a_c2_record(tmp_path)), encoding="utf-8")
        assert module.read_the_c2_record(written)["outcome"] == "booted"


class TestTheImagesAreThere:
    def test_presence_is_checked_without_reading_nine_gibibytes(self, tmp_path):
        checked = module.images_are_where_c2_left_them(a_c2_record(tmp_path))
        assert checked["rehashed"] is False
        assert checked["rootfs"]["sha256_recorded_by_c2"] == "b" * 64
        assert "sha256" not in checked["rootfs"], "nothing was measured"

    def test_a_rootfs_that_is_gone_stops_the_sweep(self, tmp_path):
        record = a_c2_record(tmp_path)
        (tmp_path / "rootfs.ext4").unlink()
        with pytest.raises(module.GuestSweepRefused) as refused:
            module.images_are_where_c2_left_them(record)
        assert "not there now" in str(refused.value)

    def test_asking_for_hashes_gets_them_compared(self, tmp_path):
        record = a_c2_record(tmp_path)
        with pytest.raises(module.GuestSweepRefused) as refused:
            module.images_are_where_c2_left_them(record, rehash=True)
        assert "different bytes" in str(refused.value)

    def test_hashes_that_agree_are_recorded_as_measured(self, tmp_path):
        record = a_c2_record(tmp_path)
        checked = module.images_are_where_c2_left_them(
            record, rehash=True, measure=lambda path: "b" * 64 if "rootfs" in str(path) else "a" * 64
        )
        assert checked["rehashed"] is True
        assert checked["kernel"]["sha256"] == "a" * 64


# ── reading a guest that answered, and one that did not ───────────────────


def sweep_with(transcript: str, tmp_path: Path, **guest) -> dict:
    booted = {
        "vm_id": "declared-sweep",
        "outcome": "booted",
        "ran_for_seconds": 9.2,
        "deadline_seconds": 1200.0,
        "command_exit_status": 0,
        "policy_is_the_required_one": True,
        "teardown": {"all_gone": True},
        "results": {
            "/out/stdout": transcript,
            "/out/guest_kernel": "6.1.141\n",
            "/out/guest_uid": "0\n",
            "/out/init_reached_the_end": "done\n",
        },
    }
    booted.update(guest)
    return module.sweep_in_guest(
        record=a_c2_record(tmp_path),
        workdir=tmp_path,
        boot=lambda **_: booted,
    )


class TestReadingWhatTheGuestWrote:
    def test_a_command_that_answered_zero_is_present(self, tmp_path):
        result = sweep_with(framed("python3", 0, "Python 3.11.15"), tmp_path)
        row = next(r for r in result["records"] if r["name"] == "python3")
        assert row["present"] is True
        assert row["first_line"] == "Python 3.11.15"

    def test_a_command_that_is_not_there_is_absent_not_missing(self, tmp_path):
        result = sweep_with(framed("node", 127, "", "node: not found"), tmp_path)
        row = next(r for r in result["records"] if r["name"] == "node")
        assert row["answered"] is True and row["present"] is False

    def test_a_guest_that_wrote_nothing_is_not_an_empty_image(self, tmp_path):
        # The expensive misreading. Forty probes with no record would otherwise
        # read as forty findings about the image.
        result = sweep_with("", tmp_path, outcome="booted_but_wrote_nothing")
        assert result["probes_answered"] == 0
        assert result["present"] == 0 and result["absent"] == 0
        assert all("did not finish" in r["grounds"] for r in result["records"])

    def test_the_host_and_the_guest_are_both_named(self, tmp_path):
        result = sweep_with(framed("sh", 0, "ok"), tmp_path)
        assert result["guest"]["kernel"] == "6.1.141"
        assert result["host"]["kernel"] == platform.release()
        assert result["host"]["jailed_to_uid"] == 997

    def test_root_in_the_guest_is_explained_rather_than_left_to_be_read(
        self, tmp_path
    ):
        guest = sweep_with(framed("sh", 0, "ok"), tmp_path)["guest"]
        assert guest["uid"] == "0"
        assert "the boundary is the machine" in guest["uid_note"]

    def test_it_does_not_answer_to_the_name_capability_receipt(self, tmp_path):
        result = sweep_with(framed("sh", 0, "ok"), tmp_path)
        assert result["is_not"][0] == "a capability receipt"
        with pytest.raises(Exception):
            validate_capability_receipt(result)


# ── the artifact the host really wrote ────────────────────────────────────


class TestTheCommittedSweep:
    """Held to what came off the execution host on 2026-09-10.

    Everything above builds a shape and checks the reader reads it, which
    cannot notice the shape being wrong. This can.
    """

    @pytest.fixture
    def real(self):
        if not REAL_SWEEP.is_file():  # pragma: no cover - it is committed
            pytest.skip(f"{REAL_SWEEP} is not committed here")
        return json.loads(REAL_SWEEP.read_text(encoding="utf-8"))

    def test_it_was_taken_in_a_guest_and_not_on_the_host(self, real):
        # The one comparison that separates this from running the driver on the
        # host and calling the result a guest sweep.
        assert real["guest"]["kernel"] and real["host"]["kernel"]
        assert real["guest"]["kernel"] != real["host"]["kernel"]

    def test_the_guest_ran_under_the_required_policy_and_was_cleaned_up(self, real):
        guest = real["guest"]
        assert guest["policy_is_the_required_one"] is True
        assert guest["outcome"] == "booted"
        assert guest["command_exit_status"] == 0
        assert guest["stopped_by_the_deadline"] is False
        assert guest["ran_for_seconds"] < guest["deadline_seconds"]
        assert guest["teardown"]["all_gone"] is True

    def test_every_declared_probe_got_an_answer(self, real):
        assert real["probes_answered"] == real["probes_declared"]
        assert real["present"] + real["absent"] == real["probes_declared"]

    def test_it_swept_the_image_c2_booted(self, real):
        assert real["image"]["pinned_digest"].startswith("sha256:")
        assert real["host"]["cgroup_version"] == 2

    def test_what_is_absent_is_named_rather_than_summarised(self, real):
        absent = sorted(
            row["name"] for row in real["records"] if row["answered"] and not row["present"]
        )
        assert absent, "a sweep with nothing absent would make this test vacuous"
        for name in absent:
            row = next(r for r in real["records"] if r["name"] == name)
            assert row["returncode"] not in (0, None)
            assert row["grounds"].startswith("the probe exited")
