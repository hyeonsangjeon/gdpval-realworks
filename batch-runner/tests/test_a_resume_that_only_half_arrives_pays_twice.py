"""The guard on the two inputs that have to be given together or not at all.

The workflow's ``run_id`` input has said "reuse an earlier one to resume it"
since it was written, and until now that was false in CI. The journal and the
ledger are written under ``$GITHUB_WORKSPACE/agentic-v2-run/``, which leaves
the runner only as an upload artifact, and nothing downloaded it back before a
run started. A dispatch with ``run_id`` filled in ran the whole cohort again
and paid for it again, while printing the run id it was given -- so its own
logs read like a resume.

Restoring the directory fixes half of it. The other half is that the journal
is scoped by run id: ``run_manifest`` builds
``TaskJournal(journal_path, run_id=run_id, task_ids=...)``, so rows written
under one name are not found by a run carrying another. Restore without the
run id and the journal is on disk and unread. Give the run id without the
restore and the journal is not there at all. Both cost the full cohort, and
neither raises: an empty or foreign journal has no completed tasks in it, and
a correct driver reading one runs everything.

That is the shape these tests hold. Not "does resume work" -- the driver's own
suite has that, and had it while CI could not resume at all -- but "can the
pair of inputs be given in a way that quietly means a second full run".

Nothing here runs a stage, calls a model or downloads an artifact.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "check_agentic_v2_resume_inputs.py"
WORKFLOW = (
    BATCH_RUNNER_ROOT.parent
    / ".github"
    / "workflows"
    / "agentic-v2-stage-run.yml"
)

from scripts.check_agentic_v2_resume_inputs import (  # noqa: E402
    RESUME_FROM,
    RUN_ID,
    problems_with,
)


# ── The four ways the pair can arrive ───────────────────────────────────────


def test_neither_given_is_a_fresh_run_and_is_allowed():
    """The ordinary dispatch. Nothing is restored and nothing is claimed."""
    assert problems_with("", "") == []


def test_both_given_is_a_resume_and_is_allowed():
    """The only combination that actually resumes anything."""
    assert problems_with("stage-one-take-2", "34645403765") == []


def test_a_run_id_with_nothing_to_restore_from_is_refused():
    """The failure that reads like a resume in its own logs."""
    (problem,) = problems_with("stage-one-take-2", "")
    assert RESUME_FROM in problem
    assert "paid for again" in problem


def test_a_restore_with_no_run_id_to_read_it_under_is_refused():
    """The journal arrives and is unreadable, which looks like no journal."""
    (problem,) = problems_with("", "34645403765")
    assert RUN_ID in problem
    assert "paid for again" in problem


# ── The values that are not really values ───────────────────────────────────


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n"])
def test_whitespace_is_not_a_value(blank):
    """A stray keystroke in one field must not be read as "given".

    If it were, the pair would look complete, the guard would pass, and the
    run would go out as the exact failure this guard exists to stop.
    """
    assert problems_with(blank, blank) == []
    assert problems_with("stage-one-take-2", blank) != []
    assert problems_with(blank, "34645403765") != []


def test_a_github_run_id_that_is_not_a_number_is_refused_here():
    """Refused before the job starts rather than by the download step.

    The download's own refusal arrives after ``paid`` has begun, which is
    after the Azure login and after the dataset fetch. Nothing is charged
    there, but it is several minutes later and the message is about an
    artifact rather than about the thing that was typed wrong.
    """
    (problem,) = problems_with("stage-one-take-2", "https://github.com/x/y/actions/runs/1")
    assert "all digits" in problem


# ── The script, run the way the workflow runs it ────────────────────────────


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=BATCH_RUNNER_ROOT,
    )


def test_the_script_exits_zero_for_a_fresh_run():
    finished = _run()
    assert finished.returncode == 0, finished.stderr
    assert "fresh run" in finished.stdout


def test_the_script_exits_nonzero_for_half_a_resume():
    finished = _run("--run-id", "stage-one-take-2")
    assert finished.returncode == 1
    assert "refusing" in finished.stderr


def test_the_script_says_what_a_resume_will_skip():
    """The line a person reads before letting a paid run go.

    It names both halves, because the whole class of defect here is one half
    being present and reading as the pair.
    """
    finished = _run(
        "--run-id", "stage-one-take-2", "--resume-from-github-run", "34645403765"
    )
    assert finished.returncode == 0, finished.stderr
    assert "stage-one-take-2" in finished.stdout
    assert "34645403765" in finished.stdout
    assert "not paid for again" in finished.stdout


def test_the_script_needs_nothing_installed():
    """It runs before ``pip install``, so it may import only the standard library.

    The guard is placed immediately after checkout on purpose: a dispatch with
    half a resume in it should be refused in seconds, not after two minutes of
    dependency setup. That placement is only safe while this holds.
    """
    source = SCRIPT.read_text()
    for forbidden in ("import yaml", "from core", "import core", "import pandas"):
        assert forbidden not in source


# ── The wiring, which is the half that was missing ──────────────────────────


def test_the_workflow_offers_the_input_this_guard_checks():
    """A guard on an input nobody can fill in guards nothing."""
    assert f"{RESUME_FROM}:" in WORKFLOW.read_text()


def test_the_free_job_actually_calls_the_guard():
    """The defect this file exists for was a correct function nobody called.

    That is the same shape as the two before it -- ``coverage_problems`` in
    PR #546 and the ledger constructor in #547 -- so the call site is asserted
    rather than assumed.
    """
    assert "check_agentic_v2_resume_inputs.py" in WORKFLOW.read_text()


def test_the_paid_job_restores_the_directory_the_journal_lives_in():
    """Restoring the record is what makes the run id mean anything."""
    text = WORKFLOW.read_text()
    assert "run-id: ${{ inputs.resume_from_github_run }}" in text
    assert "path: agentic-v2-run/" in text


def test_the_paid_job_refuses_a_restore_that_produced_no_journal():
    """A download that quietly found nothing is the failure mode to catch.

    ``download-artifact`` can succeed with nothing when a name does not match,
    and the run would then start with an empty directory under a run id --
    exactly the full re-pay the guard above is for, arrived at the long way
    round.
    """
    assert "agentic-v2-run/journal.jsonl" in WORKFLOW.read_text()


def test_the_run_id_input_no_longer_promises_resume_on_its_own():
    """It said "reuse an earlier one to resume it", which was not true in CI.

    A description is what somebody reads before typing a value into a form
    that spends money, so it is held here like any other claim.
    """
    text = WORKFLOW.read_text()
    assert "reuse an earlier one to resume it" not in text
