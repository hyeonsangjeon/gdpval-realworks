"""Everything a guest wrote is under a dot, and the archive was dropping it.

The backend keeps each ``exec_run``'s stdout, stderr and a ``meta.json`` — that
call's boot outcome, result, grounds, ``host_left_running``, ``copy_integrity``
and ``guest_confirmed_stopped`` — under :data:`EXEC_RECORD_DIR`, which is
``.gdpval/exec``. The run directory is uploaded whole, and
``actions/upload-artifact`` defaults ``include-hidden-files`` to ``false``, so
every one of those files was excluded from the archive of a run that had
already been paid for.

Nothing said so. The upload was green, the artifact existed, the journal and
the ledger and the run record were all in it, and the per-call evidence — the
only place a command's output survives, and the only per-call record of whether
a machine came up and went down again — was simply not there.

It matters most where it is least visible. The run record now says how many
guests booted; these files are what a reader checks that against. A boot that
failed leaves its evidence here and nowhere else.

**And the flag alone did not do it.** The second half of this file was written
after run 35111267647 came back with ``include-hidden-files`` set and still no
transcripts in it. ``_keep_the_output`` writes the records where the *model*
can read them, which is inside ``work/`` — and ``work/`` is what ``close()``
destroys, in a ``finally`` at the end of every ``run()``, before the driver has
even seen the result. Each task's directory reached the upload step empty, and
an empty directory is not archived either. So the fix above was necessary and,
by itself, inert: there was nothing left under ``workspaces/`` to include,
hidden or not. ``close()`` now lifts the records one level up, out of ``work/``
and into the task's own root, keeping the hidden path so that the flag is what
carries them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))
if str(BATCH_RUNNER_ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT / "tests"))

from core.agentic_v2_contract import (  # noqa: E402
    TOOL_CONTRACT_VERSION,
    AgenticV2Profile,
)
from core.agentic_v2_exec_boot import EXEC_RECORD_DIR  # noqa: E402
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend  # noqa: E402
from core.agentic_v2_substrate import AgenticV2SubstrateManifest  # noqa: E402

import test_agentic_v2_microvm_backend as microvm_fixtures  # noqa: E402

WORKFLOW = (
    BATCH_RUNNER_ROOT.parent / ".github" / "workflows" / "agentic-v2-stage-run.yml"
)
BACKEND = BATCH_RUNNER_ROOT / "core" / "agentic_v2_microvm_backend.py"

#: Where the stage is told to write, and so what gets uploaded.
RUN_DIRECTORY = "agentic-v2-run"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def uploads_of_the_run_directory(workflow: dict) -> list[tuple[str, dict]]:
    """Every step that puts the run directory into an artifact, by job."""
    found = []
    for job, definition in workflow["jobs"].items():
        for step in definition.get("steps") or []:
            uses = str(step.get("uses") or "")
            if not uses.startswith("actions/upload-artifact@"):
                continue
            if RUN_DIRECTORY in str((step.get("with") or {}).get("path") or ""):
                found.append((job, step))
    return found


def test_the_run_artifact_keeps_the_hidden_exec_records(workflow):
    """The defect, stated as the archive the run is judged from.

    ``path: agentic-v2-run/`` reads as "keep everything under here" and is not,
    and the difference is invisible from the step: no error, no warning that
    names a file, an artifact that exists and is short.
    """
    uploads = uploads_of_the_run_directory(workflow)
    assert uploads, "nothing uploads the run directory any more"

    for job, step in uploads:
        assert (step.get("with") or {}).get("include-hidden-files") is True, (
            f"{job}/{step.get('name')!r} uploads {RUN_DIRECTORY} without "
            f"include-hidden-files, so everything under {EXEC_RECORD_DIR} is "
            "dropped from the archive"
        )


def test_the_flag_is_there_because_the_exec_records_are_hidden(workflow):
    """The coupling, so the flag is not left standing for no reason.

    Written as a condition rather than as two separate assertions: if the exec
    records ever stop being hidden this passes on its own terms and says the
    flag is no longer what is carrying them, instead of failing over a change
    that fixed the same problem a different way.
    """
    if not Path(EXEC_RECORD_DIR).parts[0].startswith("."):
        pytest.skip(
            f"{EXEC_RECORD_DIR} is no longer hidden, so the upload flag is not "
            "what keeps these files in the archive"
        )

    for _, step in uploads_of_the_run_directory(workflow):
        assert (step.get("with") or {}).get("include-hidden-files") is True


def test_the_streams_are_kept_in_the_workspace_and_nowhere_else():
    """Which is what makes the upload the only route out.

    If the exec records were written to ``RUNNER_TEMP`` they would need their
    own upload step and the test above would be guarding nothing. They are
    written through the backend's workspace writer, so they land inside the run
    directory and travel in its artifact -- or do not travel at all.
    """
    source = BACKEND.read_text("utf-8")

    keeper = source.split("def _keep_the_output(")[1].split("\n    def ")[0]
    assert "EXEC_RECORD_DIR" in keeper
    assert "self._write_bytes(" in keeper
    assert "RUNNER_TEMP" not in keeper


def test_the_meta_beside_each_stream_is_what_the_census_is_checked_against():
    """The per-call answers, which exist in this file and in no other.

    The run record counts guests. These name them one at a time, and the two
    are meant to be read together: a census of three over an artifact holding
    one ``meta.json`` is a disagreement worth having, and only possible to have
    if both survive.
    """
    source = BACKEND.read_text("utf-8")

    keeper = source.split("def _keep_the_output(")[1].split("\n    def ")[0]
    for answer in (
        "boot_outcome",
        "result",
        "grounds",
        "host_left_running",
        "copy_integrity",
        "guest_confirmed_stopped",
    ):
        assert f'"{answer}"' in keeper, f"meta.json no longer carries {answer}"


# ---------------------------------------------------------------------------
# The other half: there has to be something left for the flag to keep
# ---------------------------------------------------------------------------

#: What a command that did the work prints. Not empty, because an empty stdout
#: copied out and an absent stdout look the same on disk and the whole point of
#: these files is telling one from the other.
A_COMMAND_THAT_RAN = "rows written: 412\n"


def _a_backend(root: Path) -> AgenticV2MicroVMBackend:
    return AgenticV2MicroVMBackend(
        root=root,
        profile=AgenticV2Profile(
            tool_contract_version=TOOL_CONTRACT_VERSION,
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
        image=microvm_fixtures.AN_IMAGE,
        boot_one_command=microvm_fixtures.Launcher(),
        substrate_manifest=AgenticV2SubstrateManifest.load(
            microvm_fixtures.MANIFEST_PATH
        ),
    )


def _a_call_that_booted(backend: AgenticV2MicroVMBackend, call: int = 0) -> dict:
    """One ``exec_run``'s worth of records, written the way the backend does.

    Through ``_keep_the_output`` rather than by hand: the property under test is
    that what that method writes survives, and a test that wrote the files
    itself would keep passing after the writer moved them somewhere else.
    """
    reading = {
        "stdout": A_COMMAND_THAT_RAN,
        "stderr": "",
        "boot_outcome": "exited",
        "deadline": 120,
        "truncated": False,
        "result": {"returncode": 0},
        "grounds": "the command ran to completion",
    }
    machine = {
        "host_left_running": False,
        "guest_confirmed_stopped": True,
        "copy_integrity": "ok",
        "copy_integrity_because": None,
    }
    record = {"call": call, "booted": True, "machine": machine}
    record["output_files"] = backend._keep_the_output(call, reading, machine=machine)
    backend.boots.append(record)
    return record


def test_the_records_outlive_the_workspace_they_were_written_in(tmp_path):
    """The defect run 35111267647 actually had, at the level it lived at.

    Before the fix this left an empty directory: ``include-hidden-files`` was
    already ``true`` on that run and there was nothing under it to include.
    """
    task_root = tmp_path / "workspaces" / "a-task-attempt-1"
    backend = _a_backend(task_root)
    _a_call_that_booted(backend)

    backend.close()

    kept = sorted(
        str(path.relative_to(task_root)) for path in task_root.rglob("*") if path.is_file()
    )
    assert kept == [
        f"{EXEC_RECORD_DIR}/0000/meta.json",
        f"{EXEC_RECORD_DIR}/0000/stderr",
        f"{EXEC_RECORD_DIR}/0000/stdout",
    ], "the exec records did not survive the purge, so the artifact gets none"
    assert (
        task_root / EXEC_RECORD_DIR / "0000" / "stdout"
    ).read_text("utf-8") == A_COMMAND_THAT_RAN


def test_the_purge_still_takes_the_whole_workspace(tmp_path):
    """Isolation is the claim under test; this must not have bought evidence with it.

    A change that kept the records by not purging would pass the test above and
    be the wrong fix — so what the model could reach is checked separately from
    what survives.
    """
    task_root = tmp_path / "workspaces" / "a-task-attempt-1"
    backend = _a_backend(task_root)
    _a_call_that_booted(backend)
    (backend.work / "deliverable.xlsx").write_bytes(b"PK\x03\x04")
    work = backend.work

    backend.close()

    assert not work.exists(), "close() left the model's workspace on disk"


def test_only_what_the_backend_itself_wrote_is_carried_out(tmp_path):
    """Nothing walks a directory the model can write to.

    ``.gdpval/exec`` is inside the workspace, so the model can put things there
    — including a symlink. Copying that tree by walking it would put whatever it
    pointed at into an artifact a reader takes for guest output. The leaves come
    from :attr:`boots`, which lists what this backend wrote, so a file the
    backend never recorded is left to be purged with everything else.
    """
    task_root = tmp_path / "workspaces" / "a-task-attempt-1"
    backend = _a_backend(task_root)
    _a_call_that_booted(backend)
    backend._write_bytes(f"{EXEC_RECORD_DIR}/0000/planted", b"not the guest's output")
    backend._write_bytes(f"{EXEC_RECORD_DIR}/9999/stdout", b"a call that never was")

    backend.close()

    carried = sorted(
        str(path.relative_to(task_root)) for path in task_root.rglob("*") if path.is_file()
    )
    assert f"{EXEC_RECORD_DIR}/0000/planted" not in carried
    assert f"{EXEC_RECORD_DIR}/9999/stdout" not in carried
    assert backend.exec_records_carried == [
        f"{EXEC_RECORD_DIR}/0000/stdout",
        f"{EXEC_RECORD_DIR}/0000/stderr",
        f"{EXEC_RECORD_DIR}/0000/meta.json",
    ]


def test_a_run_that_booted_nothing_carries_nothing_and_says_so(tmp_path):
    """The two zeros, told apart on the object rather than from the artifact.

    An artifact with no transcripts in it means either that no command ran or
    that the copy lost them, and last time there was no way to tell from the
    outside. ``exec_records_carried`` empty with ``exec_records_not_carried``
    ``None`` is the first; a reason string is the second.
    """
    backend = _a_backend(tmp_path / "workspaces" / "a-task-attempt-1")

    backend.close()

    assert backend.exec_records_carried == []
    assert backend.exec_records_not_carried is None


def test_a_copy_that_fails_still_purges_and_leaves_a_reason(tmp_path, monkeypatch):
    """The purge is not conditional on the evidence being saved.

    Keeping a workspace alive because its transcripts could not be copied would
    trade the property under test for a record of it.
    """
    task_root = tmp_path / "workspaces" / "a-task-attempt-1"
    backend = _a_backend(task_root)
    _a_call_that_booted(backend)
    work = backend.work

    def fails(*_args, **_kwargs):
        raise OSError("no space left on device")

    monkeypatch.setattr(backend, "_carry_the_exec_records_out", fails)
    backend.close()

    assert not work.exists(), "a failed copy stopped the purge"
    assert backend.exec_records_not_carried is not None
    assert "no space left on device" in backend.exec_records_not_carried


def test_the_destination_is_still_hidden_so_the_upload_flag_still_carries_it(tmp_path):
    """Couples this half back to the first, which is otherwise dead weight.

    The records could have been lifted to an ordinary name and would then reach
    the archive with no flag at all — and the four tests above would be
    guarding an input nothing needed, which a later reader would rightly
    delete. Keeping the dot keeps them load-bearing.
    """
    task_root = tmp_path / "workspaces" / "a-task-attempt-1"
    backend = _a_backend(task_root)
    _a_call_that_booted(backend)

    backend.close()

    assert backend.exec_records_carried, (
        "nothing was carried out, so this would pass on an empty list and say "
        "nothing about where the records ended up"
    )
    for relative in backend.exec_records_carried:
        assert Path(relative).parts[0].startswith("."), (
            f"{relative} is no longer hidden; include-hidden-files is not what "
            "keeps it in the archive and the tests above say otherwise"
        )
