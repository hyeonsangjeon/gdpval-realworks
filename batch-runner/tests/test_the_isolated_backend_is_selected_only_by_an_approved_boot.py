"""The two arguments the cohort path could not supply, and where they come from.

This is the measured gap, written as a test. Building the isolated backend from
the cohort factory's own arguments raises, and the message names the three it is
short of::

    AgenticV2MicroVMBackend(root=..., **what_the_runner_passes)
    -> TypeError: missing 3 required keyword-only arguments:
       'profile', 'image', and 'boot_one_command'

One of the three — ``profile`` — the runner already passes, so the real
shortfall is two, and both are things that cannot exist without a host that has
booted a guest. :mod:`core.agentic_v2_isolated_selection` is where they come
from, and everything below is about one question: does a run get them only when
a real boot says it may?

**No microVM boots here.** The launcher is a callable the backend is handed, the
same injection the backend's own tests use. What is proven is the wiring and the
refusals — that a host which never booted anything cannot reach the isolated
backend by any argument, that the two missing pieces arrive when it did, and
that the identity a caller would declare is the one the backend reports. That
this is not evidence of isolation is the point of saying so here.

**Every assertion has a negative control.** Each one is a defect deliberately
introduced into an otherwise-valid setup — a boot that did not boot, a kernel
whose bytes moved, an approver nobody named — and the test that would catch it
is the assertion beside it. A check that has never been seen to fail is not a
check.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

import pytest

from core.agentic_v2_contract import (
    MICROVM_BACKEND_ID,
    TOOL_CONTRACT_VERSION,
    AgenticV2Profile,
)
from core.agentic_v2_exec_boot import EXEC_RECORD_DIR
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_guest_image import sha256_file
from core.agentic_v2_isolated_selection import (
    BackendChoice,
    IsolatedBackendRefused,
    IsolationApproval,
    isolated_environment_note,
    select_backend,
    the_fixture,
    what_a_booted_host_left,
)
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend
from core.agentic_v2_runner import AgenticV2ScriptedRunner
from core.agentic_v2_task_journal import JournalRefused


BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = BATCH_RUNNER_ROOT / "sandbox" / "agentic_v2_capabilities.json"
A_DIGEST = "sha256:" + "e" * 64


def a_profile() -> AgenticV2Profile:
    return AgenticV2Profile.from_mapping(
        {
            "tool_contract_version": TOOL_CONTRACT_VERSION,
            "policy_profile_id": "offline-full-v1",
            "foundation_only": True,
        }
    )


# The boot protocol is the backend's, so the double for it is the backend's
# too. A private copy here drifted on its first contact with the real code --
# it returned ``out``/``exit_status`` where the reader wants ``results``/
# ``command_exit_status`` -- and a double that disagrees with the thing it
# stands for tests the double. Importing the one the backend's own suite uses
# means a change to that protocol turns both files red in the same commit.
from tests.test_agentic_v2_microvm_backend import Launcher  # noqa: E402


def a_booted_host(tmp_path: Path, **changes) -> Path:
    """What stage C2 leaves behind, with the files it names really present.

    The kernel and rootfs are written and then hashed, rather than given
    placeholder hashes, because the re-hash on selection is one of the things
    under test and a placeholder would make it vacuous.
    """
    host = tmp_path / "host"
    host.mkdir(parents=True, exist_ok=True)
    for name in ("firecracker", "jailer"):
        (host / name).write_text("#!/bin/sh\n", encoding="utf-8")
    kernel = host / "vmlinux"
    rootfs = host / "rootfs.ext4"
    kernel.write_bytes(b"not a kernel, but the same bytes twice")
    rootfs.write_bytes(b"not a root filesystem either")

    artefact = {
        "schema_version": "1.0",
        "stage": "C2",
        "outcome": "booted",
        "host": {
            "kernel_release": os.uname().release,
            "cgroup_version": 2,
            "kvm_present": True,
            "firecracker": (host / "firecracker").as_posix(),
            "jailer": (host / "jailer").as_posix(),
            "firecracker_version": "v1.13.1",
        },
        "jail_account": {"name": "gdpvaljail", "uid": 997, "gid": 997},
        "images": {
            "kernel": {"path": kernel.as_posix(), "sha256": sha256_file(kernel)},
            "rootfs": {"path": rootfs.as_posix(), "sha256": sha256_file(rootfs)},
            "image": {
                "repository": "ghcr.io/hyeonsangjeon/gdpval-sandbox",
                "pinned_digest": A_DIGEST,
                "manifest_digest": "sha256:" + "9" * 64,
            },
            "work_disk": {"path": (host / "work.ext4").as_posix()},
        },
        "boot": {"outcome": "booted"},
    }
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(artefact.get(key), dict):
            artefact[key] = {**artefact[key], **value}
        else:
            artefact[key] = value
    written = host / "c2-first-boot.json"
    written.write_text(json.dumps(artefact), encoding="utf-8")
    return written


def an_approval(tmp_path: Path, artefact: Path, **changes) -> IsolationApproval:
    document = {
        "approved_by": "the repository owner, in writing",
        "first_boot_artefact": artefact.as_posix(),
        "substrate_manifest": MANIFEST_PATH.as_posix(),
        "scratch": (tmp_path / "scratch").as_posix(),
    }
    document.update(changes)
    return IsolationApproval.from_mapping(document)


# -- what the cohort factory actually hands a backend -----------------------


def what_the_runner_passes() -> set[str]:
    """The keyword names, read out of the runner rather than copied from it.

    Copied, this list would agree with the runner on the day it was written and
    never again, and the failure it would then hide is a backend built without
    something a run depends on. Parsed, a new argument in the runner shows up
    here as a red test in the same commit.
    """
    source = Path(AgenticV2ScriptedRunner.__module__.replace(".", "/") + ".py")
    tree = ast.parse(
        (BATCH_RUNNER_ROOT / source).read_text(encoding="utf-8")
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "backend_factory"
        ):
            return {kw.arg for kw in node.keywords if kw.arg}
    raise AssertionError(
        "the runner no longer calls self.backend_factory(...) with keywords, "
        "so this test cannot tell what a backend is handed"
    )


def test_the_cohort_factorys_arguments_do_not_build_the_isolated_backend():
    """The gap, measured, so that closing it is a change to something real.

    Negative control for the whole module: if this ever passes, the isolated
    backend has acquired defaults for the two things that cannot have defaults,
    and every test below is testing a different problem than it thinks.
    """
    passed = what_the_runner_passes()
    assert "profile" in passed, (
        "the runner used to pass profile, and if it stopped then the shortfall "
        "is three arguments rather than two"
    )
    kwargs = {name: None for name in passed}

    with pytest.raises(TypeError) as raised:
        AgenticV2MicroVMBackend(root="/tmp/nowhere", **kwargs)

    message = str(raised.value)
    assert "image" in message and "boot_one_command" in message
    assert "profile" not in message, (
        "profile is supplied by the runner; a TypeError naming it means the "
        "parse above found the wrong call"
    )


def test_with_no_approval_the_choice_is_the_fixture_and_declares_nothing(tmp_path):
    """The default path, which is every caller in this repository today."""
    choice = select_backend()

    assert choice.backend_class is AgenticV2FixtureBackend
    assert choice.is_isolated is False
    assert choice.identity_to_declare is None
    assert dict(choice.extra_kwargs) == {}
    assert choice == the_fixture()


def test_an_approval_and_a_booted_host_supply_the_two_missing_arguments(tmp_path):
    """The seam this module exists for: the cohort factory's call now builds.

    Constructed from the runner's own keyword list plus what the choice adds,
    which is the same expression the stage factory will use. No boot happens —
    the launcher is a callable — so this is evidence about wiring and about
    nothing else.
    """
    approval = an_approval(tmp_path, a_booted_host(tmp_path))
    choice = select_backend(approval=approval, session="run-under-test")

    assert choice.backend_class is AgenticV2MicroVMBackend
    assert choice.is_isolated is True
    assert set(choice.extra_kwargs) == {
        "image", "boot_one_command", "substrate_manifest"
    }

    kwargs = {name: None for name in what_the_runner_passes()}
    kwargs["profile"] = a_profile()
    backend = choice.backend_class(
        root=tmp_path / "work-root", **choice.extra_kwargs, **kwargs
    )
    assert isinstance(backend, AgenticV2MicroVMBackend)
    assert backend.start(timeout_seconds=5)["ok"] is True


def test_the_declared_identity_is_the_one_the_backend_reports(tmp_path):
    """Two derivations of the same hash, and admission depends on them agreeing.

    The selection module rebuilds the identity from the contract, the
    interpreter table and the policy; the backend builds it from its own
    attributes. If they disagree, a run that declared the first would die at
    ``compute_start_failed`` on every task — after the ledger was open. Here
    that disagreement is a red test instead.
    """
    approval = an_approval(tmp_path, a_booted_host(tmp_path))
    choice = select_backend(approval=approval, session="run-under-test")
    backend = choice.backend_class(
        root=tmp_path / "work-root",
        profile=a_profile(),
        **choice.extra_kwargs,
    )

    assert choice.identity_to_declare == backend.backend_identity()
    assert choice.identity_to_declare["backend_id"] == MICROVM_BACKEND_ID
    assert choice.identity_to_declare["foundation_only"] is True


def test_two_guests_are_two_identities(tmp_path):
    """Negative control for the identity: a different rootfs is a different machine."""
    first = select_backend(
        approval=an_approval(tmp_path / "a", a_booted_host(tmp_path / "a")),
        session="run-under-test",
    )
    elsewhere = tmp_path / "b"
    artefact = a_booted_host(elsewhere)
    (elsewhere / "host" / "rootfs.ext4").write_bytes(b"a different filesystem")
    document = json.loads(artefact.read_text(encoding="utf-8"))
    document["images"]["rootfs"]["sha256"] = sha256_file(
        elsewhere / "host" / "rootfs.ext4"
    )
    artefact.write_text(json.dumps(document), encoding="utf-8")
    second = select_backend(
        approval=an_approval(elsewhere, artefact), session="run-under-test"
    )

    assert (
        first.identity_to_declare["implementation_sha256"]
        != second.identity_to_declare["implementation_sha256"]
    )


# -- the refusals, one per way a host can fail to be the one that booted ----


def test_a_host_that_never_booted_anything_cannot_be_approved_onto(tmp_path):
    approval = an_approval(
        tmp_path, a_booted_host(tmp_path, outcome="refused", reason="no kvm")
    )
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(approval=approval, session="run-under-test")
    assert "'refused', not a boot" in str(raised.value)
    assert "no kvm" in str(raised.value)


def test_an_artefact_from_another_machine_is_refused(tmp_path):
    approval = an_approval(
        tmp_path,
        a_booted_host(tmp_path, host={"kernel_release": "6.8.0-somewhere-else"}),
    )
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(approval=approval, session="run-under-test")
    assert "6.8.0-somewhere-else" in str(raised.value)
    assert os.uname().release in str(raised.value)


def _with_a_host_block(artefact: Path, mutate) -> Path:
    """Rewrite the artefact's host evidence in place, including by removing it.

    ``a_booted_host``'s ``changes`` merges dictionaries, which cannot express
    "this key is not there" — and not being there is the case the check exists
    for, so it needs saying.
    """
    document = json.loads(artefact.read_text(encoding="utf-8"))
    mutate(document)
    artefact.write_text(json.dumps(document), encoding="utf-8")
    return artefact


def test_an_intact_artefact_is_returned_as_it_was_written(tmp_path):
    """The control. Without it, "everything is refused" would also pass."""
    artefact = a_booted_host(tmp_path)
    assert what_a_booted_host_left(artefact) == json.loads(
        artefact.read_text(encoding="utf-8")
    )


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda d: d.pop("host"), "carries no host block"),
        (lambda d: d["host"].pop("kernel_release"), "records no kernel_release"),
        (lambda d: d["host"].update(kernel_release=""), "is empty"),
        (lambda d: d["host"].update(kernel_release="   "), "is empty"),
        (
            lambda d: d["host"].update(kernel_release=["6.8.0"]),
            "rather than a release string",
        ),
        (
            lambda d: d.update(host=["kernel_release", "6.8.0"]),
            "rather than a block of host facts",
        ),
    ],
    ids=["no-host", "no-release", "empty", "blank", "not-a-string", "not-a-mapping"],
)
def test_an_artefact_with_no_readable_kernel_evidence_is_refused(
    tmp_path, mutate, expected
):
    """Absent evidence is refused, not skipped.

    The check read the release with ``or ""`` and then compared only when the
    result was non-empty, so the three artefacts that say nothing about their
    host — no block, no key, an empty string — went through the check that
    exists to catch exactly them. Two malformed shapes are here for the same
    reason: something that is not a host block is not evidence of a host.
    """
    artefact = _with_a_host_block(a_booted_host(tmp_path), mutate)
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(
            approval=an_approval(tmp_path, artefact), session="run-under-test"
        )
    assert expected in str(raised.value)


def test_missing_kernel_evidence_stops_before_anything_can_start_a_machine(
    tmp_path, monkeypatch
):
    """Where the refusal lands, not just that it lands.

    ``one_machine_per_call`` is the last thing selection builds, and it is the
    object every later boot goes through. A refusal that arrived after it would
    still be a refusal and would still be too late.
    """
    reached: list[dict] = []

    def spy(*args, **kwargs):
        reached.append(dict(kwargs))
        return "a machine nothing in this test starts"

    monkeypatch.setattr(
        "core.agentic_v2_isolated_selection.one_machine_per_call", spy
    )

    blinded = _with_a_host_block(a_booted_host(tmp_path), lambda d: d.pop("host"))
    with pytest.raises(IsolatedBackendRefused):
        select_backend(
            approval=an_approval(tmp_path, blinded), session="run-under-test"
        )
    assert reached == []

    # And the spy is not vacuous: the same call on an intact artefact reaches it.
    select_backend(
        approval=an_approval(tmp_path, a_booted_host(tmp_path)),
        session="run-under-test",
    )
    assert len(reached) == 1


def test_a_matching_kernel_release_is_not_claimed_to_be_a_host_identity(tmp_path):
    """Two machines built from one image report the same release.

    So the value is recorded with what it does and does not establish beside it,
    rather than left for a reader to over-read.
    """
    choice = select_backend(
        approval=an_approval(tmp_path, a_booted_host(tmp_path)),
        session="run-under-test",
    )
    shows = choice.grounds["what_the_kernel_release_shows"]
    assert "not a host identity" in shows
    assert "differently provisioned" in shows


@pytest.mark.parametrize("binary", ["firecracker", "jailer"])
def test_a_binary_that_has_gone_is_refused(tmp_path, binary):
    artefact = a_booted_host(tmp_path)
    (tmp_path / "host" / binary).unlink()
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(
            approval=an_approval(tmp_path, artefact), session="run-under-test"
        )
    assert binary in str(raised.value)


@pytest.mark.parametrize("image", ["kernel", "rootfs"])
def test_bytes_that_moved_since_the_boot_are_refused(tmp_path, image):
    """The check expected to pass, which is exactly why it is worth running.

    A re-provisioned disk, a truncated download and a rootfs somebody rebuilt
    between stages all look like a healthy host right up to the first command —
    and for a cohort that is many paid tasks after the money started.
    """
    artefact = a_booted_host(tmp_path)
    named = {"kernel": "vmlinux", "rootfs": "rootfs.ext4"}[image]
    (tmp_path / "host" / named).write_bytes(b"rebuilt between stages")

    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(
            approval=an_approval(tmp_path, artefact), session="run-under-test"
        )
    assert "these are different bytes" in str(raised.value).lower()


def test_an_image_that_has_gone_is_refused(tmp_path):
    artefact = a_booted_host(tmp_path)
    (tmp_path / "host" / "vmlinux").unlink()
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(
            approval=an_approval(tmp_path, artefact), session="run-under-test"
        )
    assert "not there now" in str(raised.value)


def test_the_work_disk_is_not_pinned(tmp_path):
    """Deliberately unchecked, because every call builds its own.

    Pinning it would assert the opposite of the ``workdir: ephemeral``
    obligation, so its absence from the re-check is a decision and is recorded
    as one.
    """
    artefact = a_booted_host(tmp_path)
    choice = select_backend(
        approval=an_approval(tmp_path, artefact), session="run-under-test"
    )
    rechecked = choice.grounds["images_rechecked"]
    assert set(rechecked) == {
        "kernel", "rootfs", "matches_the_guest_that_booted", "work_disk"
    }
    assert "ephemeral" in rechecked["work_disk"]


def test_a_session_name_is_required(tmp_path):
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(
            approval=an_approval(tmp_path, a_booted_host(tmp_path)), session=""
        )
    assert "session name" in str(raised.value)


def test_a_manifest_that_cannot_be_read_is_refused_as_a_sentence(tmp_path):
    """Not as a stack trace. The stage catches one exception type.

    An OSError or ValueError escaping this module ends the run in a traceback
    where a reason belongs, and a traceback on task one reads as an
    infrastructure fault rather than as a configuration that was never right.
    """
    broken = tmp_path / "not-a-manifest.json"
    broken.write_text("{}", encoding="utf-8")
    approval = an_approval(
        tmp_path, a_booted_host(tmp_path), substrate_manifest=broken.as_posix()
    )
    with pytest.raises(IsolatedBackendRefused) as raised:
        select_backend(approval=approval, session="run-under-test")
    assert "substrate manifest" in str(raised.value)


# -- the approval document itself -------------------------------------------


@pytest.mark.parametrize(
    "defect, expected",
    [
        ({"approved_by": "   "}, "approved_by"),
        ({"first_boot_artefact": ""}, "first_boot_artefact"),
        ({"substrate_manifest": ""}, "substrate_manifest"),
        ({"scratch": ""}, "scratch"),
    ],
)
def test_an_approval_missing_any_of_its_four_answers_is_refused(defect, expected):
    document = {
        "approved_by": "someone",
        "first_boot_artefact": "/somewhere/c2.json",
        "substrate_manifest": "/somewhere/manifest.json",
        "scratch": "/somewhere/scratch",
        **defect,
    }
    with pytest.raises(IsolatedBackendRefused) as raised:
        IsolationApproval.from_mapping(document)
    assert expected in str(raised.value)


def test_a_key_nobody_reads_is_refused_rather_than_ignored():
    """A misspelt setting is a condition somebody believes they set."""
    with pytest.raises(IsolatedBackendRefused) as raised:
        IsolationApproval.from_mapping(
            {
                "approved_by": "someone",
                "first_boot_artefact": "/somewhere/c2.json",
                "substrate_manifest": "/somewhere/manifest.json",
                "scratch": "/somewhere/scratch",
                "aproved_by": "someone else",
            }
        )
    assert "aproved_by" in str(raised.value)


@pytest.mark.parametrize("count", [0, -1, True, 1.5, "two"])
def test_a_processor_count_that_is_not_one_is_refused(count):
    with pytest.raises(IsolatedBackendRefused):
        IsolationApproval.from_mapping(
            {
                "approved_by": "someone",
                "first_boot_artefact": "/somewhere/c2.json",
                "substrate_manifest": "/somewhere/manifest.json",
                "scratch": "/somewhere/scratch",
                "vcpu_count": count,
            }
        )


def test_an_approval_that_is_not_on_disk_is_refused(tmp_path):
    with pytest.raises(IsolatedBackendRefused) as raised:
        IsolationApproval.load(tmp_path / "never-written.json")
    assert "no isolation approval" in str(raised.value)


def test_an_approval_round_trips_through_a_file(tmp_path):
    artefact = a_booted_host(tmp_path)
    written = tmp_path / "approval.json"
    written.write_text(
        json.dumps(
            {
                "approved_by": "the repository owner, in writing",
                "first_boot_artefact": artefact.as_posix(),
                "substrate_manifest": MANIFEST_PATH.as_posix(),
                "scratch": (tmp_path / "scratch").as_posix(),
                "vcpu_count": 4,
            }
        ),
        encoding="utf-8",
    )
    approval = IsolationApproval.load(written)
    assert approval.vcpu_count == 4
    choice = select_backend(approval=approval, session="run-under-test")
    assert choice.grounds["approved_by"] == "the repository owner, in writing"
    assert choice.grounds["first_boot_artefact"] == artefact.as_posix()


# -- one call is one machine, with the machine scripted --------------------


def an_exec(**changes) -> dict:
    """One valid ``exec_run`` argument object, in the contract's own shape.

    ``cwd`` and ``timeout_seconds`` are required by the schema, and an argument
    object missing either is refused by the path check before a machine is ever
    launched. Writing them out here rather than at each call site is why the
    tests below are about the backend instead of about a typo: the first draft
    of this file sent ``code`` where the contract says ``script`` and omitted
    ``cwd``, and four assertions about booted machines went green without any
    machine being asked for.
    """
    base = {
        "interpreter": "bash",
        "script": "true",
        "cwd": ".",
        "timeout_seconds": 60,
    }
    base.update(changes)
    return base


def a_backend(tmp_path, launcher) -> AgenticV2MicroVMBackend:
    approval = an_approval(tmp_path, a_booted_host(tmp_path))
    choice = select_backend(approval=approval, session="run-under-test")
    return choice.backend_class(
        root=tmp_path / "work-root",
        profile=a_profile(),
        image=choice.extra_kwargs["image"],
        boot_one_command=launcher,
        substrate_manifest=choice.extra_kwargs["substrate_manifest"],
    )


def test_a_command_that_ran_leaves_its_streams_in_the_workspace(tmp_path):
    launcher = Launcher(status=0, stdout="七\n", stderr="")
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)

    result = backend.exec_run(an_exec(script="echo 七"))

    assert result["ok"] is True
    assert result["data"] == {"returncode": 0}
    assert len(launcher.calls) == 1

    records = sorted((backend.work / EXEC_RECORD_DIR).glob("*/meta.json"))
    assert len(records) == 1
    meta = json.loads(records[0].read_text(encoding="utf-8"))
    assert meta["result"]["ok"] is True
    assert meta["result"]["data"] == {"returncode": 0}
    stdout = records[0].parent / "stdout"
    assert stdout.read_text(encoding="utf-8") == "七\n"


def test_a_command_that_failed_is_a_successful_call_reporting_a_failure(tmp_path):
    """Non-zero is not an error of the tool. Conflating the two would make a
    task that correctly reported a failing command look like a broken sandbox.
    """
    launcher = Launcher(status=3, stderr="no such file\n")
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)

    result = backend.exec_run(an_exec(script="cat missing"))

    assert launcher.calls
    assert result["ok"] is True
    assert result["data"]["returncode"] == 3


def test_a_boot_with_no_exit_status_is_never_returncode_zero(tmp_path):
    """The one honesty rule of the boot reader, checked from this end.

    Absent evidence is not a result. A guest that came up and left nothing at
    ``/out/exit_status`` has told us nothing about what the command did, and the
    two ways to paper over that — reporting success, or inventing a non-zero —
    are both a record that says something nobody observed.
    """
    launcher = Launcher(status=None)
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)

    result = backend.exec_run(an_exec())

    assert launcher.calls, (
        "a machine has to have been asked for before its silence means anything; "
        "without this line a refusal before launch passes this test"
    )
    assert result["ok"] is False
    assert result.get("data", {}).get("returncode") != 0
    assert "returncode" not in result.get("data", {})


def test_a_machine_that_did_not_come_back_is_an_error_not_an_exit_code(tmp_path):
    launcher = Launcher(outcome="stopped_by_the_deadline", status=None)
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)

    result = backend.exec_run(an_exec(script="sleep 100", timeout_seconds=100))

    assert launcher.calls
    assert result["ok"] is False
    assert result["error_type"] == "cancelled", (
        "a deadline that fires is the bound working, not the machine breaking, "
        "and the model is told which one it was"
    )
    assert "returncode" not in result.get("data", {})


def test_the_launcher_is_handed_the_workspace_the_model_writes_into(tmp_path):
    """Staged inputs are reachable from inside, because it is the same tree.

    The stage factory stages a task's reference files under the backend's work
    directory before the model is asked anything. If the launcher were handed a
    different directory, every staged file would be missing from the guest and
    the failure would read as a model that ignored its inputs.
    """
    launcher = Launcher()
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)
    staged = backend.work / "inputs" / "reference_files" / "a.txt"
    staged.parent.mkdir(parents=True, exist_ok=True)
    staged.write_text("the reference", encoding="utf-8")

    backend.exec_run(an_exec(script="ls"))

    handed = launcher.calls[0]["workspace"]
    assert handed == backend.work
    assert (handed / "inputs" / "reference_files" / "a.txt").read_text(
        encoding="utf-8"
    ) == "the reference"


def test_a_refusal_never_spends_a_boot(tmp_path):
    """Ordering, and it is the ordering that keeps a refusal free.

    The path check and the deadline are decided before anything is launched, so
    a call that was never going to be allowed does not first pay for a machine.
    """
    launcher = Launcher()
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)

    refused = backend.exec_run(an_exec(interpreter="brainfuck", script="+."))

    assert refused["ok"] is False
    assert launcher.calls == []


def test_the_deadline_reaches_the_machine(tmp_path):
    launcher = Launcher()
    backend = a_backend(tmp_path, launcher)
    backend.start(timeout_seconds=5)

    backend.exec_run(an_exec(timeout_seconds=11))

    assert launcher.calls[0]["deadline_seconds"] == 11


# -- what the record will say -----------------------------------------------


def test_the_isolated_note_says_the_browser_got_worse_not_better(tmp_path):
    """The sentence most likely to be quoted back, pinned so it cannot soften.

    In the one paid cohort that has run, every ``browser_run`` call asked for a
    network operation, and both backends refuse those. The isolated backend
    additionally refuses ``open_local``, which the fixture served. So booting a
    real guest recovers none of those tasks and takes one capability away, and
    a record that let a reader infer otherwise would be the expensive kind of
    wrong.
    """
    note = isolated_environment_note({"policy_profile_id": "offline-full-v1"})

    assert note["backend"] == AgenticV2MicroVMBackend.__name__
    assert note["guest_booted"] is True
    assert note["exec_run_open"] is True
    not_real = " ".join(note["what_was_not_real"])
    assert "open_local" in not_real
    assert "fails harder here, not less" in not_real
    assert "the cost of a boot, which nothing in this repository has measured" in not_real


def test_the_isolated_note_has_the_same_shape_as_the_fixtures():
    """A backend switch changes what the record says, never how much it says."""
    from tests.test_run_agentic_v2_stage import _load_runner  # noqa: PLC0415

    fixture_note = _load_runner().environment_note(
        {"policy_profile_id": "offline-full-v1"}
    )
    isolated = isolated_environment_note({"policy_profile_id": "offline-full-v1"})

    assert set(isolated) == set(fixture_note)


def test_the_note_carries_the_availability_the_model_is_told_about():
    from core.agentic_v2_tool_availability import availability_for  # noqa: PLC0415

    note = isolated_environment_note({"policy_profile_id": "offline-full-v1"})
    assert note["tool_availability"] == [
        {"tool": entry.tool, "verdict": entry.verdict, "how_we_know": entry.evidence}
        for entry in availability_for(AgenticV2MicroVMBackend)
    ]
    by_tool = {entry["tool"]: entry for entry in note["tool_availability"]}
    assert by_tool["exec_run"]["verdict"] == "works"
    assert by_tool["exec_run"]["how_we_know"] == "asserted", (
        "nothing has executed exec_run on a booted guest, and the day something "
        "does this becomes 'executed' — which is the line that says isolation "
        "stopped being a claim"
    )
    assert by_tool["browser_run"]["verdict"] == "refuses"


def test_the_choice_is_frozen(tmp_path):
    """Nothing downstream may edit what was selected after it was recorded."""
    choice = select_backend()
    assert isinstance(choice, BackendChoice)
    with pytest.raises(Exception):
        choice.backend_class = AgenticV2MicroVMBackend  # type: ignore[misc]


# -- the cohort loop, with the isolated backend underneath it ---------------
#
# The two seams below are the ones the design record listed and could not check
# while the stage script was unable to construct this backend at all. They are
# about money: on the fixture a repeated task costs nothing, and on this backend
# every ``exec_run`` is a machine. So "resume skips what is done" and "the
# receipt agrees with what ran" stop being bookkeeping and become the difference
# between paying once and paying twice.
#
# The driver's own suite already checks resume with a stand-in runner. What it
# cannot say -- because a stand-in has no backend -- is that a skipped task
# boots nothing. That is the only claim these add.

from tests.test_agentic_v2_run_driver import _success, _tasks  # noqa: E402


def a_cohort_factory(tmp_path, launcher, *, script=None):
    """A runner factory whose runners are the real isolated backend.

    Each task gets its own root, so ``launcher.calls`` can be read back per
    task: the workspace path a boot was handed contains the task id that owns
    it. ``script`` may refuse a task by returning a failure envelope *without*
    reaching ``exec_run``, which is how an interrupted first run is staged.
    """
    approval = an_approval(tmp_path, a_booted_host(tmp_path))
    choice = select_backend(approval=approval, session="cohort-under-test")
    assert choice.is_isolated, "this factory is pointless against the fixture"
    made: list[str] = []

    class Runner:
        def __init__(self, task):
            self.task = task

        def run(self, prompt, reference_files, occupation, **kwargs):
            task_id = kwargs["task_id"]
            made.append(task_id)
            if script is not None:
                answer = script(task_id)
                if answer is not None:
                    return answer
            backend = choice.backend_class(
                root=tmp_path / "roots" / task_id,
                profile=a_profile(),
                image=choice.extra_kwargs["image"],
                boot_one_command=launcher,
                substrate_manifest=choice.extra_kwargs["substrate_manifest"],
            )
            backend.start(timeout_seconds=5)
            ran = backend.exec_run(an_exec(script="echo done"))
            assert ran["ok"] is True, ran
            return _success(task_id)

        def close(self):
            return None

    def build(task):
        return Runner(task)

    build.made = made  # type: ignore[attr-defined]
    return build


def boots_by_task(launcher) -> list[str]:
    """Which task each boot belonged to, in the order the boots happened."""
    owners = []
    for call in launcher.calls:
        parts = Path(call["workspace"]).resolve().parts
        owners.append(next(part for part in parts if part.startswith("task-")))
    return owners


def test_a_resumed_run_does_not_boot_again_for_a_task_the_journal_finished(tmp_path):
    """The seam the design record called resume, priced.

    The first run is interrupted after two tasks. The second must boot for the
    third and for nothing else -- on this backend a re-run is not a repeated
    row, it is a second machine for work already paid for.
    """
    from core.agentic_v2_run_driver import run_manifest

    tasks = _tasks(3)
    journal = tmp_path / "journal.jsonl"
    first_launcher = Launcher(status=0, stdout="done\n", stderr="")
    attempts = {"n": 0}

    def two_then_stop(task_id):
        attempts["n"] += 1
        if attempts["n"] > 2:
            raise KeyboardInterrupt
        return None  # fall through to the backend

    with pytest.raises(KeyboardInterrupt):
        run_manifest(
            tasks,
            run_id="run-resume",
            runner_factory=a_cohort_factory(
                tmp_path / "first", first_launcher, script=two_then_stop
            ),
            journal_path=journal,
            collect_into=tmp_path / "collected",
        )

    # The control for the assertion below: boots really do happen here, so
    # "one boot in the second run" is a count and not an absence.
    assert boots_by_task(first_launcher) == ["task-0001", "task-0002"]

    second_launcher = Launcher(status=0, stdout="done\n", stderr="")
    factory = a_cohort_factory(tmp_path / "second", second_launcher)
    outcome = run_manifest(
        tasks,
        run_id="run-resume",
        runner_factory=factory,
        journal_path=journal,
        collect_into=tmp_path / "collected",
    )

    assert outcome.skipped_on_resume == ("task-0001", "task-0002")
    assert factory.made == ["task-0003"], "a skipped task must not reach a runner"
    assert boots_by_task(second_launcher) == ["task-0003"], (
        "resume skipped the task and booted for it anyway, which is the one "
        "way this backend costs twice for one task"
    )


def test_a_journal_from_another_run_is_refused_before_a_machine_starts(tmp_path):
    """Preregistered negative control: the resume that is handed the wrong journal.

    The refusal has to come before the first boot, not after it. A run that
    discovers the mismatch on task two has already bought task one.
    """
    from core.agentic_v2_run_driver import run_manifest

    tasks = _tasks(2)
    journal = tmp_path / "journal.jsonl"
    launcher = Launcher(status=0, stdout="done\n", stderr="")
    run_manifest(
        tasks,
        run_id="run-one",
        runner_factory=a_cohort_factory(tmp_path / "one", launcher),
        journal_path=journal,
        collect_into=tmp_path / "collected",
    )
    assert len(launcher.calls) == 2

    intruder = Launcher(status=0, stdout="done\n", stderr="")
    with pytest.raises(JournalRefused) as refusal:
        run_manifest(
            tasks,
            run_id="run-two",
            runner_factory=a_cohort_factory(tmp_path / "two", intruder),
            journal_path=journal,
            collect_into=tmp_path / "collected",
        )
    assert "run-one" in str(refusal.value)
    assert intruder.calls == [], "the wrong journal was noticed after a boot"


def test_every_task_that_booted_has_a_receipt_and_one_that_did_not_has_none(tmp_path):
    """The seam the design record called per-task attribution.

    Reservation and settlement agree per task, and the agreement is read the
    only way that means anything here: against the boots, not against the rows.
    """
    from core.agentic_v2_run_driver import run_manifest
    from core.cost_receipts import STATUS_COMPLETE

    priced: list[tuple[str, int]] = []

    def receipt_for(task, attempt):
        priced.append((task.task_id, attempt))
        return {
            "status": STATUS_COMPLETE,
            "estimated_cost_usd": 0.5,
            "known_cost_usd": 0.5,
        }

    tasks = _tasks(2)
    launcher = Launcher(status=0, stdout="done\n", stderr="")
    outcome = run_manifest(
        tasks,
        run_id="run-priced",
        runner_factory=a_cohort_factory(tmp_path / "first", launcher),
        journal_path=tmp_path / "journal.jsonl",
        collect_into=tmp_path / "collected",
        receipt_for=receipt_for,
    )

    assert boots_by_task(launcher) == ["task-0001", "task-0002"]
    assert [task_id for task_id, _ in priced] == ["task-0001", "task-0002"]
    assert outcome.summary["cost_is_fully_accounted"] is True
    assert outcome.summary["unaccounted_tasks"] == []

    # Resume: the second run boots for nothing, and prices nothing. A pricing
    # callback that fires for a skipped task would be charging for a machine
    # that never started.
    priced.clear()
    quiet = Launcher(status=0, stdout="done\n", stderr="")
    again = run_manifest(
        tasks,
        run_id="run-priced",
        runner_factory=a_cohort_factory(tmp_path / "second", quiet),
        journal_path=tmp_path / "journal.jsonl",
        collect_into=tmp_path / "collected",
        receipt_for=receipt_for,
    )
    assert again.skipped_on_resume == ("task-0001", "task-0002")
    assert quiet.calls == []
    assert priced == []


def test_a_booted_task_whose_receipt_is_missing_is_unaccounted_not_free(tmp_path):
    """Preregistered negative control: the charge nobody can settle.

    A machine started. If that task can then be reported as fully accounted,
    the run's cost total is a number with a hole in it, and the hole is exactly
    the size of the part this backend adds.
    """
    from core.agentic_v2_run_driver import run_manifest

    tasks = _tasks(2)
    launcher = Launcher(status=0, stdout="done\n", stderr="")
    outcome = run_manifest(
        tasks,
        run_id="run-unpriced",
        runner_factory=a_cohort_factory(tmp_path / "first", launcher),
        journal_path=tmp_path / "journal.jsonl",
        collect_into=tmp_path / "collected",
        receipt_for=lambda task, attempt: (
            None if task.task_id == "task-0002" else {
                "status": "complete",
                "estimated_cost_usd": 0.5,
                "known_cost_usd": 0.5,
            }
        ),
    )

    assert boots_by_task(launcher) == ["task-0001", "task-0002"]
    assert outcome.summary["unaccounted_tasks"] == ["task-0002"]
    assert outcome.summary["cost_is_fully_accounted"] is False

