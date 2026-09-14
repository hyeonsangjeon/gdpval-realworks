"""Both halves of a published floor have to reach a clone of this repository.

The sidecar carries the sha256 of the script that wrote it, so a reader can
check that the file on disk is what that script projects from that record. That
citation is only worth something if the script is in the repository. It very
nearly was not: ``batch-runner/scripts/`` is ignored wholesale by
``.gitignore``, with individual files re-admitted one at a time by ``!`` lines,
and a new script there is invisible to ``git status`` rather than untracked-
looking. The sidecar would have shipped naming a hash of a file nobody else has.

So this file holds four things together:

  * both files are in the index, so a clone receives them
  * both are on disk, which is a different failure and worth saying separately
  * the hashes the sidecar cites are the hashes those files actually have
  * the committed bytes are still what the record projects to, checked by
    running the script's own ``--check``

The fourth is what makes the first three matter. A hash that agrees with a file
that no longer agrees with the record is a consistent citation of the wrong
thing.

Nothing here writes to the repository: ``--check`` compares and returns.
No model is called.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts import check_grader_hash_freeze as freeze  # noqa: E402

#: Repository-relative, because that is the form git and the freeze check both
#: speak. The producer and the file it produces travel together or not at all.
SCRIPT = "batch-runner/scripts/derive_round_cost_sidecar.py"
SIDECAR = "batch-runner/results/exp035_codex_foundry_full220/report/derived_cost.json"
PUBLISHED = (SCRIPT, SIDECAR)

#: Paths as the script itself is invoked with them, from ``batch-runner/``. The
#: method string in the sidecar interpolates the round-state path it was given,
#: so reproducing the committed bytes means reproducing the invocation.
ROUND_STATE_ARG = "docs/run_records/round_state.json"
SIDECAR_ARG = "results/exp035_codex_foundry_full220/report/derived_cost.json"


def sha256_of(relative: str) -> str:
    return hashlib.sha256((REPO_ROOT / relative).read_bytes()).hexdigest()


def the_sidecar() -> dict:
    return json.loads((REPO_ROOT / SIDECAR).read_text(encoding="utf-8"))


@pytest.mark.parametrize("relative", PUBLISHED)
def test_git_is_carrying_both_halves(relative: str) -> None:
    tracked = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", "--", relative],
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{relative} is not tracked, so a clone of this repository does not "
        "have it. If it sits under an ignored directory, add a '!' line for it "
        f"in .gitignore; otherwise it was simply never added. git said: "
        f"{tracked.stderr.strip()!r}"
    )


@pytest.mark.parametrize("relative", PUBLISHED)
def test_both_halves_are_actually_here(relative: str) -> None:
    """Tracked and present are different failures, so they are asked separately.

    A deleted file stays tracked, and a file staged but removed from the working
    tree passes the check above while nothing can read it.
    """
    assert (REPO_ROOT / relative).is_file(), f"{relative} is not on disk"


def test_the_sidecar_names_the_script_that_wrote_it() -> None:
    assert the_sidecar()["source"]["derived_by"] == SCRIPT


def test_the_script_hash_in_the_sidecar_is_the_script_on_disk() -> None:
    """Editing the producer without regenerating leaves a citation of a ghost.

    Any change to the script -- a comment, a guard, a message -- moves this
    hash. The published file would then cite a version of the producer that
    exists nowhere, and a reader checking provenance would find nothing to
    check against.
    """
    assert the_sidecar()["source"]["derived_by_sha256"] == sha256_of(SCRIPT), (
        "the sidecar cites a different version of the script than the one "
        "committed here. Regenerate it: from batch-runner/, "
        f"python scripts/derive_round_cost_sidecar.py --round-state {ROUND_STATE_ARG} "
        f"--output {SIDECAR_ARG}"
    )


def test_the_record_hash_in_the_sidecar_is_the_record_on_disk() -> None:
    """The round state is the only surviving route to this figure.

    Its six sqlite ledgers lived on runners that are gone, so the derivation
    cannot be performed again. If the record moves and the sidecar does not,
    the published figure describes a round state nobody can produce.
    """
    record = "batch-runner/" + ROUND_STATE_ARG
    assert the_sidecar()["source"]["round_state_sha256"] == sha256_of(record)


def test_the_committed_bytes_are_still_what_the_record_projects_to() -> None:
    """The script's own --check, run the way the file was written.

    Byte-for-byte, not field-by-field: key order, indentation and the method
    string are all part of what a reader hashes. --check writes nothing.
    """
    check = subprocess.run(
        [
            sys.executable,
            "scripts/derive_round_cost_sidecar.py",
            "--round-state",
            ROUND_STATE_ARG,
            "--output",
            SIDECAR_ARG,
            "--check",
        ],
        cwd=str(BATCH_RUNNER_ROOT),
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, (
        "the committed sidecar is not what the round state projects to.\n"
        f"stdout: {check.stdout}\nstderr: {check.stderr}"
    )
    assert "identical" in check.stdout


@pytest.mark.parametrize("relative", PUBLISHED)
def test_neither_half_moves_the_grader_fingerprint(relative: str) -> None:
    """Both sit outside the grading source set, and that is worth pinning.

    A change to a hash-moving path invalidates a dispatched grading chunk at
    checkout. Neither of these is one -- ``batch-runner/scripts/`` is not in the
    set and ``results/`` is not either -- so this work can merge while a sharded
    grading run is in flight. If that ever stops being true, it should stop
    here rather than at someone else's dispatch.
    """
    assert not freeze.is_grader_source_path(relative)
