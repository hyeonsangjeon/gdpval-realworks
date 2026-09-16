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
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_exec_boot import EXEC_RECORD_DIR  # noqa: E402

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
