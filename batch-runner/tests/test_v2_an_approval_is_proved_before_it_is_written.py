"""An approval is written only if the selector that will use it accepts it.

The file this script writes is the one thing standing between a dispatch that
asked for isolation and a run that silently used the fixture. Two orderings
matter and neither is visible from reading the output.

The first: prove, *then* write. A file that exists is a file the next step
passes along, so an approval that would be refused on task one -- after
``azure/login``, after the ledger is opened -- has to be refused before it
reaches the disk. Every refusal test here checks that nothing was written, not
just that something was raised.

The second: the boot id, not the kernel release. ``what_a_booted_host_left``
compares kernel releases and its own docstring says that is not a host
identity. On GitHub's runners it demonstrably is not -- runs 35072131325 and
35072747069 were different machines and both reported ``6.17.0-1022-azure`` --
so an artefact carried from one runner to another would pass it. The boot id
is what makes "the proof was made here" checkable, which is the condition the
whole same-host arrangement rests on.

Nothing here boots a guest or reaches the network. The kernel and rootfs are
small files with real digests, which is all the re-hashing gate reads.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_isolated_selection import IsolationApproval  # noqa: E402
from scripts import write_isolation_approval as module  # noqa: E402
from scripts.write_isolation_approval import (  # noqa: E402
    SUBSTRATE_MANIFEST,
    ApprovalRefused,
    main,
    prove_and_write,
    the_artefact_was_written_here,
    this_boot,
)

THIS_BOOT = "11111111-2222-3333-4444-555555555555"
ANOTHER_BOOT = "99999999-8888-7777-6666-555555555555"


@pytest.fixture()
def host(tmp_path: Path) -> dict:
    """A machine that booted a guest, with the files still where it left them."""
    for name in ("firecracker", "jailer"):
        (tmp_path / name).write_text("#!/bin/true\n", encoding="utf-8")
    kernel = tmp_path / "vmlinux"
    kernel.write_bytes(b"a kernel, for the purposes of hashing it")
    rootfs = tmp_path / "rootfs.ext4"
    rootfs.write_bytes(b"a root filesystem, likewise")

    artefact = {
        "outcome": "booted",
        "host": {
            "boot_id": THIS_BOOT,
            "kernel_release": os.uname().release,
            "cgroup_version": 2,
            "firecracker": (tmp_path / "firecracker").as_posix(),
            "jailer": (tmp_path / "jailer").as_posix(),
        },
        "jail_account": {"name": "gdpvaljail", "uid": 997, "gid": 997},
        "images": {
            "kernel": {
                "path": kernel.as_posix(),
                "sha256": hashlib.sha256(kernel.read_bytes()).hexdigest(),
            },
            "rootfs": {
                "path": rootfs.as_posix(),
                "sha256": hashlib.sha256(rootfs.read_bytes()).hexdigest(),
            },
            "image": {
                "repository": "hyeonsangjeon/gdpval-sandbox",
                "manifest_digest": "sha256:" + "e" * 64,
            },
        },
    }
    written = tmp_path / "c2-first-boot.json"
    written.write_text(json.dumps(artefact), encoding="utf-8")
    return {"root": tmp_path, "artefact": artefact, "path": written}


def write(host: dict, *, boot_id: str | None = THIS_BOOT, **overrides):
    arguments = {
        "artefact_path": host["path"],
        "substrate_manifest": SUBSTRATE_MANIFEST,
        "scratch": host["root"] / "scratch",
        "approved_by": "the test that proves the selector agrees",
        "session": "a-session",
        "vcpu_count": 2,
        "into": host["root"] / "approval.json",
        "boot_id": boot_id,
    }
    arguments.update(overrides)
    return prove_and_write(**arguments)


def rewrite(host: dict, change) -> None:
    artefact = json.loads(host["path"].read_text(encoding="utf-8"))
    change(artefact)
    host["path"].write_text(json.dumps(artefact), encoding="utf-8")


@pytest.fixture()
def the_host_says_this_boot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Make the command line read the fixture's boot rather than this machine's.

    ``main`` asks the kernel, which is the point of it. Pointing that read at a
    file we control is what lets the command-line tests assert on the good path
    at all -- and it keeps them from depending on whether the machine running
    pytest publishes a boot id, which kernel 3.10 here does and a container may
    not.
    """
    published = tmp_path / "published-boot-id"
    published.write_text(f"{THIS_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(module, "BOOT_ID", published)


# ── the good path ─────────────────────────────────────────────────────────


def test_an_artefact_from_this_boot_produces_an_approval(host: dict) -> None:
    record = write(host)

    assert record["backend"] == "AgenticV2MicroVMBackend", (
        "an approval that resolves to anything else is a run reporting "
        "isolation it never had"
    )
    assert (host["root"] / "approval.json").is_file()
    assert record["same_machine"]["boot_id"] == THIS_BOOT


def test_what_was_written_is_what_the_stage_will_load(host: dict) -> None:
    """A key the approval loader refuses is an unapproved run believing it was
    approved, and the loader refuses unknown keys by design."""
    write(host)

    approval = IsolationApproval.load(host["root"] / "approval.json")

    assert approval.first_boot_artefact == host["path"]
    assert approval.substrate_manifest == SUBSTRATE_MANIFEST
    assert approval.vcpu_count == 2
    assert approval.approved_by == "the test that proves the selector agrees"


def test_the_manifest_this_repository_ships_passes_the_gate(host: dict) -> None:
    """The default is only a useful default if the selector accepts it.

    ``select_backend`` refuses a manifest that is not foundation-only, and the
    committed manifest is the one every same-host dispatch will use without
    naming it. If it ever stopped satisfying that, the failure would appear on
    a runner rather than here.
    """
    record = write(host)

    assert SUBSTRATE_MANIFEST.is_file()
    assert record["grounds"]["approved_by"]


def test_the_grounds_name_what_was_rechecked(host: dict) -> None:
    record = write(host)

    assert record["images_rechecked"]["matches_the_guest_that_booted"] is True
    assert "kernel_release" in record["grounds"]


# ── proof does not travel between hosts ───────────────────────────────────


def test_an_artefact_from_another_boot_is_refused(host: dict) -> None:
    with pytest.raises(ApprovalRefused, match="different machine"):
        write(host, boot_id=ANOTHER_BOOT)


def test_a_refused_artefact_leaves_no_approval_behind(host: dict) -> None:
    """The next step reads a path, not a return value."""
    with pytest.raises(ApprovalRefused):
        write(host, boot_id=ANOTHER_BOOT)

    assert not (host["root"] / "approval.json").exists()


def test_an_artefact_that_records_no_boot_is_refused(host: dict) -> None:
    """Older artefacts predate the field, and that is the case to refuse."""
    rewrite(host, lambda a: a["host"].pop("boot_id"))

    with pytest.raises(ApprovalRefused, match="records no boot id"):
        write(host)


def test_a_kernel_that_publishes_no_boot_id_is_refused(host: dict) -> None:
    """Not knowing is not the same as agreeing, and it is answered the same way."""
    with pytest.raises(ApprovalRefused, match="does not publish"):
        write(host, boot_id=None)


def test_an_artefact_with_no_host_block_is_refused(host: dict) -> None:
    rewrite(host, lambda a: a.pop("host"))

    with pytest.raises(ApprovalRefused, match="no host block"):
        write(host)


def test_the_boot_id_check_reads_the_file_and_tolerates_its_absence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "BOOT_ID", tmp_path / "nothing-here")
    assert this_boot() is None

    published = tmp_path / "boot_id"
    published.write_text(f"{THIS_BOOT}\n", encoding="utf-8")
    monkeypatch.setattr(module, "BOOT_ID", published)
    assert this_boot() == THIS_BOOT


def test_the_same_machine_check_is_usable_on_its_own(host: dict) -> None:
    evidence = the_artefact_was_written_here(host["artefact"], boot_id=THIS_BOOT)

    assert evidence["boot_id"] == THIS_BOOT
    assert "two runners built from one image" in evidence["what_this_shows"]


# ── the selector's own refusals arrive before anything is written ─────────


def test_an_artefact_that_did_not_boot_is_refused(host: dict) -> None:
    rewrite(
        host,
        lambda a: a.update({"outcome": "refused", "reason": "no jailer on PATH"}),
    )

    with pytest.raises(ApprovalRefused, match="not a boot"):
        write(host)

    assert not (host["root"] / "approval.json").exists()


def test_a_rootfs_whose_bytes_moved_is_refused(host: dict) -> None:
    """A rebuilt rootfs looks like a healthy host until the first exec_run."""
    (host["root"] / "rootfs.ext4").write_bytes(b"somebody rebuilt this")

    with pytest.raises(ApprovalRefused, match="different bytes"):
        write(host)

    assert not (host["root"] / "approval.json").exists()


def test_a_refusal_says_where_it_would_otherwise_have_surfaced(host: dict) -> None:
    rewrite(host, lambda a: a.update({"outcome": "refused"}))

    with pytest.raises(ApprovalRefused, match="after the ledger was open"):
        write(host)


def test_an_absent_artefact_is_a_sentence_about_running_the_first_boot(
    host: dict,
) -> None:
    host["path"].unlink()

    with pytest.raises(ApprovalRefused, match="run_agentic_c2_first_boot"):
        write(host)


# ── the command line ──────────────────────────────────────────────────────


def test_the_command_writes_the_approval_and_reports_zero(
    host: dict, the_host_says_this_boot: None, capsys: pytest.CaptureFixture
) -> None:
    into = host["root"] / "cli-approval.json"

    code = main(
        [
            "--first-boot-artefact", host["path"].as_posix(),
            "--scratch", (host["root"] / "scratch").as_posix(),
            "--approved-by", "workflow run 1 attempt 1",
            "--session", "a-session",
            "--into", into.as_posix(),
        ]
    )

    assert code == 0
    assert into.is_file()
    assert "AgenticV2MicroVMBackend" in capsys.readouterr().out


def test_the_command_refuses_a_carried_artefact_without_writing(
    host: dict, the_host_says_this_boot: None, capsys: pytest.CaptureFixture
) -> None:
    rewrite(host, lambda a: a["host"].update({"boot_id": ANOTHER_BOOT}))
    into = host["root"] / "cli-approval.json"

    code = main(
        [
            "--first-boot-artefact", host["path"].as_posix(),
            "--scratch", (host["root"] / "scratch").as_posix(),
            "--approved-by", "workflow run 1 attempt 1",
            "--session", "a-session",
            "--into", into.as_posix(),
        ]
    )

    assert code == 1
    assert not into.exists()
    assert "was not written" in capsys.readouterr().err


def test_a_first_boot_artefact_that_is_not_json_is_a_sentence(
    host: dict, the_host_says_this_boot: None, capsys: pytest.CaptureFixture
) -> None:
    host["path"].write_text("this is not a document", encoding="utf-8")

    code = main(
        [
            "--first-boot-artefact", host["path"].as_posix(),
            "--scratch", (host["root"] / "scratch").as_posix(),
            "--approved-by", "workflow run 1 attempt 1",
            "--session", "a-session",
            "--into", (host["root"] / "cli-approval.json").as_posix(),
        ]
    )

    assert code == 1
    assert "could not be read as one" in capsys.readouterr().err
