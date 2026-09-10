"""The runner that spends stage D's money, exercised without spending it.

Stage D costs more per run than stage A did and costs it in two currencies —
model calls and boots — so the parts that decide whether it happens are worth
more than the run. Four of them are tested here.

**Refusing on the wrong host.** Stage D runs where C2 booted a guest, and it
establishes that by reading C2's artefact rather than by trying. A model call
made on a host with no KVM would be bought and then discarded at the first
``exec_run``. Each refusal is separate, because they ask the reader for
different things: run C2, run C2 here, fix the host, or go and look at why the
boot failed.

**Using what C2 measured rather than what was intended.** The kernel, the
rootfs, the jail account and the binaries all come out of the artefact, so the
paid run is against the images that were actually booted.

**The exit condition, which is not stage A's.** A model can be reached, ask for
a command that the backend refuses on the host, and never boot. Stage D's middle
term is that a command really ran inside a guest, and a test proves the middle
term is load-bearing by removing only it.

**What survives.** The record carries what is *known* about the guest image —
``not_run`` — beside its digest, so no reader can take a stage D pass for image
verification. It does not carry the benchmark wording or anything the model
said.

Nothing here boots anything or reaches a network.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

RUNNER_PATH = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_stage_d_probe.py"

from core.agentic_v2_stage_d_probe import (  # noqa: E402
    PROBE_TOOLS,
    StageDProbeOutcome,
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_agentic_stage_d_probe", RUNNER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = _load_runner()

A_DIGEST = "sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb"

#: One boot that came back the way a working one does.
#:
#: The returncode matters and ``boot_outcome`` does not, because those answer
#: different questions: a machine can start cleanly and its guest still write no
#: status, and only the guest's own returncode file separates that from a
#: command that ran and exited.
A_BOOT_THAT_CAME_BACK = {
    "boot_outcome": "booted",
    "booted": True,
    "result": {"data": {"returncode": 0}},
}


def a_c2_artefact(tmp_path: Path, **changes) -> Path:
    """What C2 leaves behind after a boot that worked, minus what stage D never reads."""
    firecracker = tmp_path / "firecracker"
    jailer = tmp_path / "jailer"
    firecracker.write_text("#!/bin/sh\n", encoding="utf-8")
    jailer.write_text("#!/bin/sh\n", encoding="utf-8")

    artefact = {
        "schema_version": "1.0",
        "stage": "C2",
        "outcome": "booted",
        "host": {
            "kernel_release": os.uname().release,
            "cgroup_version": 2,
            "kvm_present": True,
            "firecracker": firecracker.as_posix(),
            "jailer": jailer.as_posix(),
            "firecracker_version": "v1.13.1",
        },
        "jail_account": {"name": "gdpvaljail", "uid": 997, "gid": 997},
        "images": {
            "kernel": {"path": (tmp_path / "vmlinux").as_posix(), "sha256": "a" * 64},
            "rootfs": {"path": (tmp_path / "rootfs.ext4").as_posix(), "sha256": "b" * 64},
            "image": {
                "repository": "ghcr.io/hyeonsangjeon/gdpval-sandbox",
                "pinned_digest": A_DIGEST,
                "manifest_digest": "sha256:" + "9" * 64,
            },
            "work_disk": {"path": (tmp_path / "work.ext4").as_posix()},
        },
        "boot": {"outcome": "booted"},
    }
    artefact.update(changes)
    written = tmp_path / "c2-first-boot.json"
    written.write_text(json.dumps(artefact), encoding="utf-8")
    return written


def an_outcome(**changes) -> StageDProbeOutcome:
    settings = {
        "reached_a_model": True,
        "resolved_model": "gpt-5.4",
        "requested_deployment": "gpt-5.4",
        "resource": "a-foundry-resource",
        "tools_offered": PROBE_TOOLS,
        "tools_asked_for": ("exec_run", "workspace_apply"),
        "turns_taken": 4,
        "stop_reason": "model_stopped_without_finishing",
        "detail": "",
        "guest_image": {"digest": A_DIGEST},
        "image_evidence": {"status": "not_run", "subject": A_DIGEST, "grounds": "x"},
        "boots": (
            A_BOOT_THAT_CAME_BACK,
            A_BOOT_THAT_CAME_BACK,
        ),
        "ledger": (
            {"turn": 1, "history_entries_sent": 0},
            {"turn": 2, "history_entries_sent": 1},
            {"turn": 3, "history_entries_sent": 2},
        ),
    }
    settings.update(changes)
    return StageDProbeOutcome(**settings)


def run_command(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(RUNNER_PATH), *arguments],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


# ── the host, established by reading rather than by trying ────────────────


class TestWhatStageDRefusesToRunOn:
    def test_a_host_that_has_never_booted_a_guest(self, tmp_path):
        with pytest.raises(runner.StageDRefused) as refused:
            runner.read_what_c2_left(tmp_path / "nothing.json")
        assert "Run scripts/run_agentic_c2_first_boot.py first" in str(refused.value)

    def test_a_c2_run_that_recorded_a_failure_says_what_c2_said(self, tmp_path):
        artefact = a_c2_artefact(
            tmp_path,
            outcome="host_cannot_boot",
            reason="no /dev/kvm or no jailer on this machine",
        )
        with pytest.raises(runner.StageDRefused) as refused:
            runner.read_what_c2_left(artefact)
        said = str(refused.value)
        assert "'host_cannot_boot'" in said
        assert "no /dev/kvm" in said

    def test_an_artefact_from_a_different_machine(self, tmp_path):
        # The specific way this goes wrong in practice: the artefact is copied
        # from the execution host to a developer box, and everything in it still
        # reads as a successful boot.
        artefact = a_c2_artefact(tmp_path)
        moved = json.loads(artefact.read_text())
        moved["host"]["kernel_release"] = "6.8.0-somewhere-else"
        artefact.write_text(json.dumps(moved), encoding="utf-8")

        with pytest.raises(runner.StageDRefused) as refused:
            runner.read_what_c2_left(artefact)
        assert "different machine" in str(refused.value)

    def test_binaries_that_have_gone_since_c2_ran(self, tmp_path):
        artefact = a_c2_artefact(tmp_path)
        (tmp_path / "jailer").unlink()

        with pytest.raises(runner.StageDRefused) as refused:
            runner.read_what_c2_left(artefact)
        assert "jailer" in str(refused.value)

    def test_a_good_artefact_is_returned_whole(self, tmp_path):
        artefact = runner.read_what_c2_left(a_c2_artefact(tmp_path))
        assert artefact["outcome"] == "booted"
        assert artefact["jail_account"]["uid"] == 997


# ── the guest, named by what C2 measured ──────────────────────────────────


class TestTheImageAndTheMachineComeFromC2:
    def test_the_digest_is_the_one_c2_pinned_and_the_hashes_are_c2_s_own(
        self, tmp_path
    ):
        image = runner.the_guest_c2_booted(
            json.loads(a_c2_artefact(tmp_path).read_text())
        )
        assert image.digest == A_DIGEST
        assert image.kernel_sha256 == "a" * 64
        assert image.rootfs_sha256 == "b" * 64

    def test_naming_the_image_is_not_evidence_about_it(self, tmp_path):
        # The whole reason this field exists. A record that named a digest and
        # stopped reads as though the evidence followed the name.
        from core.agentic_v2_stage_d_probe import capability_evidence_for

        image = runner.the_guest_c2_booted(
            json.loads(a_c2_artefact(tmp_path).read_text())
        )
        assert capability_evidence_for(image)["status"] == "not_run"

    def test_the_machine_jails_to_the_account_c2_used(self, tmp_path):
        artefact = json.loads(a_c2_artefact(tmp_path).read_text())
        machine = runner.the_machine_c2_proved(
            artefact, scratch=tmp_path / "m", session="stage-d", vcpu_count=2
        )
        assert (machine.uid, machine.gid) == (997, 997)
        assert machine.cgroup_version == 2
        assert Path(machine.firecracker_binary).name == "firecracker"

    def test_each_call_would_get_its_own_machine_name(self, tmp_path):
        artefact = json.loads(a_c2_artefact(tmp_path).read_text())
        machine = runner.the_machine_c2_proved(
            artefact, scratch=tmp_path / "m", session="stage-d-task", vcpu_count=2
        )
        assert machine.name_the_machine() == "stage-d-task-0000"


# ── the same bytes, not merely the same paths ─────────────────────────────
#
# C2 and C3 ran on a host that was then deallocated, and stage D runs after it
# is started again. These files are on the OS disk and are expected to survive
# that, which is exactly why the check is worth having: nothing here would
# notice a reprovisioned disk until the money had been spent.


def _images_that_are_really_there(tmp_path: Path) -> Path:
    """C2's artefact with a kernel and rootfs that exist and hash to what it says."""
    from core.agentic_v2_guest_image import sha256_file

    kernel = tmp_path / "vmlinux"
    rootfs = tmp_path / "rootfs.ext4"
    kernel.write_bytes(b"not really a kernel")
    rootfs.write_bytes(b"not really a filesystem")
    written = a_c2_artefact(tmp_path)
    artefact = json.loads(written.read_text())
    artefact["images"]["kernel"]["sha256"] = sha256_file(kernel)
    artefact["images"]["rootfs"]["sha256"] = sha256_file(rootfs)
    written.write_text(json.dumps(artefact), encoding="utf-8")
    return written


class TestTheImagesAreStillTheOnesC2Booted:
    def test_files_that_hash_to_what_c2_recorded_pass(self, tmp_path):
        checked = runner.the_images_are_still_the_ones_c2_booted(
            json.loads(_images_that_are_really_there(tmp_path).read_text())
        )
        assert checked["matches_the_guest_c2_booted"] is True
        assert checked["kernel"]["sha256"] and checked["rootfs"]["sha256"]

    def test_a_rootfs_that_is_gone_stops_the_run(self, tmp_path):
        written = _images_that_are_really_there(tmp_path)
        (tmp_path / "rootfs.ext4").unlink()
        with pytest.raises(runner.StageDRefused) as refused:
            runner.the_images_are_still_the_ones_c2_booted(
                json.loads(written.read_text())
            )
        assert "not there now" in str(refused.value)
        assert "run_agentic_c2_first_boot" in str(refused.value)

    def test_a_rootfs_rebuilt_since_c2_stops_the_run(self, tmp_path):
        # The case a path check alone would miss, and the expensive one: the
        # file is present, the host looks healthy, and the model call is
        # charged in full before the first command finds a different machine.
        written = _images_that_are_really_there(tmp_path)
        (tmp_path / "rootfs.ext4").write_bytes(b"a filesystem somebody rebuilt")
        with pytest.raises(runner.StageDRefused) as refused:
            runner.the_images_are_still_the_ones_c2_booted(
                json.loads(written.read_text())
            )
        assert "different bytes" in str(refused.value)

    def test_the_work_disk_is_not_pinned_and_says_why(self, tmp_path):
        # Pinning it would assert the opposite of the workdir: ephemeral
        # obligation stage C recorded and handed to stage D.
        checked = runner.the_images_are_still_the_ones_c2_booted(
            json.loads(_images_that_are_really_there(tmp_path).read_text())
        )
        assert isinstance(checked["work_disk"], str), "a note, not a measurement"
        assert "ephemeral" in checked["work_disk"]


# ── against the artefact the host really wrote ────────────────────────────


class TestAgainstTheRealC2Record:
    """The readers are held to C2's committed artefact, not only to fixtures.

    Everything above builds the shape stage D expects and then checks stage D
    reads it. That is circular in one specific way: it cannot notice the shape
    being wrong. ``tasks/0822_saturday/c2_first_boot.json`` is what the Azure
    host actually wrote on 2026-09-10, so these tests fail if the two ever
    disagree — which is a failure that would otherwise appear on a started host
    with a paid run waiting behind it.
    """

    REAL = (
        Path(__file__).resolve().parents[2]
        / "tasks"
        / "0822_saturday"
        / "c2_first_boot.json"
    )

    @pytest.fixture
    def real(self):
        if not self.REAL.is_file():  # pragma: no cover - it is committed
            pytest.skip(f"{self.REAL} is not committed here")
        return json.loads(self.REAL.read_text(encoding="utf-8"))

    def test_the_guest_reads_out_of_the_real_artefact(self, real):
        image = runner.the_guest_c2_booted(real)
        assert image.digest == A_DIGEST
        assert len(image.kernel_sha256) == 64
        assert len(image.rootfs_sha256) == 64

    def test_the_machine_reads_out_of_the_real_artefact(self, real):
        machine = runner.the_machine_c2_proved(
            real, scratch=Path("/tmp/never-used"), session="d", vcpu_count=2
        )
        assert machine.cgroup_version == 2, "stage D's policy needs cgroup v2"
        assert Path(machine.kernel).name and Path(machine.rootfs).name
        assert machine.uid > 0 and machine.gid > 0, "not root on the host"

    def test_this_box_is_refused_by_the_real_artefact(self, real, tmp_path):
        """Wherever this suite runs, it is not the host C2 booted on — and the
        reason it is refused says which check caught it.

        Written first as a kernel comparison, and CI corrected it. GitHub's
        hosted runners are Azure virtual machines carrying the same
        ``6.17.0-…-azure`` kernel build as the development host, so on a runner
        the kernel matches and the artefact still describes a different
        machine. The binaries are what separated them. So kernel equality is
        necessary and not sufficient, both checks are load-bearing, and this
        asserts the refusal rather than the route it took.
        """
        copied = tmp_path / "c2-first-boot.json"
        copied.write_text(json.dumps(real), encoding="utf-8")
        recorded = real["host"]["kernel_release"]
        firecracker = Path(str(real["host"]["firecracker"]))

        if recorded == os.uname().release and firecracker.is_file():
            # The execution host itself. Nothing is refused here, which is the
            # whole point of the gate.
            assert runner.read_what_c2_left(copied)["outcome"] == "booted"
            return

        with pytest.raises(runner.StageDRefused) as refused:
            runner.read_what_c2_left(copied)
        said = str(refused.value)
        if recorded != os.uname().release:
            assert recorded in said and os.uname().release in said
        else:
            assert "is not there now" in said
            assert firecracker.as_posix() in said


# ── the question stage D asked, which is not the one stage A asked ────────


class TestTheExitCondition:
    def test_reached_ran_and_worked_on_is_what_counts(self):
        assert runner.exit_condition_met(an_outcome()) is True

    def test_a_model_that_never_asked_for_a_command_does_not_count(self):
        declined = an_outcome(
            tools_asked_for=("capabilities_query",),
            boots=(),
            turns_taken=2,
            ledger=({"turn": 1, "history_entries_sent": 0},),
        )
        assert declined.reached_a_model is True
        assert runner.exit_condition_met(declined) is False

    def test_a_command_the_backend_refused_before_booting_does_not_count(self):
        # The middle term, alone. The model was reached and did go on afterwards
        # — it went on from a refusal. Stage A's condition would pass this and it
        # would prove nothing about the machine.
        never_booted = an_outcome(boots=())
        assert never_booted.reached_a_model is True
        assert never_booted.worked_on_after_running_something is True
        assert never_booted.a_command_really_ran is False
        assert runner.exit_condition_met(never_booted) is False

    def test_a_boot_that_failed_is_not_a_command_that_ran(self):
        broken = an_outcome(
            boots=({"boot_outcome": "workspace_did_not_come_back"},)
        )
        assert runner.exit_condition_met(broken) is False

    def test_a_service_that_never_answered_does_not_count(self):
        unreachable = an_outcome(
            reached_a_model=False, resolved_model=None, turns_taken=0,
            boots=(), ledger=(),
        )
        assert runner.exit_condition_met(unreachable) is False


# ── what is left on disk afterwards ───────────────────────────────────────


class FakeVerdict:
    task_id = "02aa1805-c658-4069-8a6a-02dec146063a"


def a_record(**changes):
    said = {
        "prompt_sha256": "c" * 64,
        "approved_maximum_usd": "12.00",
        "most_it_could_cost_usd": "3.40",
    }
    return runner.build_record(
        verdict=FakeVerdict(),
        said=said,
        outcome=an_outcome(**changes),
        fingerprint={"route_profile": "project-ci"},
        workspace=Path("/tmp/agentic-v2-stage-d-xyz"),
        artefact=Path("/var/tmp/gdpval-c2/c2-first-boot.json"),
    )


class TestTheRecord:
    def test_it_names_the_task_and_hashes_its_wording_but_keeps_neither(self):
        record = a_record()
        assert record["task_id"] == FakeVerdict.task_id
        assert record["prompt_sha256"] == "c" * 64
        assert "prompt" not in record
        assert "task_prompt" not in record

    def test_it_carries_what_is_known_about_the_image_beside_the_digest(self):
        probe = a_record()["probe"]
        assert probe["guest_image"]["digest"] == A_DIGEST
        assert probe["image_evidence"]["status"] == "not_run"

    def test_it_says_whether_the_question_was_answered(self):
        assert a_record()["exit_condition_met"] is True
        assert a_record(boots=())["exit_condition_met"] is False

    def test_it_points_at_the_c2_artefact_the_run_stood_on(self):
        assert a_record()["c2_artefact"].endswith("c2-first-boot.json")

    def test_it_can_be_written_down_as_it_stands(self):
        json.dumps(a_record(), indent=2, sort_keys=True)


# ── the free path really being free ───────────────────────────────────────


def test_a_missing_c2_artefact_stops_the_command_before_anything_is_built(tmp_path):
    """The first thing checked, because it is the cheapest and the most likely."""
    finished = run_command(
        "--dry-run", "--c2-artefact", str(tmp_path / "nothing.json")
    )

    assert finished.returncode == 1
    assert "Refused before spending anything" in finished.stdout
    assert "run_agentic_c2_first_boot.py first" in finished.stdout


def test_the_refusal_happens_without_an_azure_route_configured():
    """Not asserted — demonstrated.

    Nothing in the test environment configures a route, and the client factory
    refuses to build without one. A command that exits on the C2 check has not
    reached that far, which is the ordering that makes the free path free.
    """
    assert "AZURE_AI_ROUTE_PROFILE" not in os.environ

    finished = run_command("--dry-run", "--c2-artefact", "/nonexistent/c2.json")

    assert finished.returncode == 1
    assert "Traceback" not in finished.stderr
