"""The derived repair must be something a clone actually has.

``.gitignore`` closes all of ``batch-runner/scripts/`` and re-admits files one
at a time by name. A new script there is invisible by default: it sits in the
working tree, every local run finds it, ``git add -A`` skips it without a word,
and the branch looks finished. Measured on this very branch -- the derivation
script was written, run, hashed, cited by the README, cited by the pull request
and cited by the commit message while being ignored by git the entire time.

That failure is quiet in a way worth spelling out. The README tells a reader to
reproduce the derived files by running the script. Had it shipped this way, the
instruction would have pointed at nothing, and the published sha256 of a file
absent from the repository would have looked like provenance while proving
nothing at all. Derived evidence that cannot be re-derived is not evidence.

So this file asks git what it is carrying, and asks the files themselves what
they hash to, rather than trusting either the allowlist or the README. Both of
those are written by hand and both go stale.

No model is called. Nothing is written.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from scripts import check_grader_hash_freeze as freeze  # noqa: E402

RECORD_DIR = BATCH_RUNNER_ROOT / "docs" / "run_records" / "audio_receipt_repair_v1"
README = RECORD_DIR / "README.md"
SCRIPT = BATCH_RUNNER_ROOT / "scripts" / "derive_audio_receipt_repair.py"

#: Everything the repair publishes, relative to the repository root. The script
#: is listed with the files it produced because the three only mean something
#: together: the derived files say what the audio was, and the script says how
#: to get that answer again without trusting them.
PUBLISHED = (
    "batch-runner/scripts/derive_audio_receipt_repair.py",
    "batch-runner/docs/run_records/audio_receipt_repair_v1/README.md",
    "batch-runner/docs/run_records/audio_receipt_repair_v1/"
    "exp035_codex_foundry_full220__src_fd0db9d9d78d6d54__shard-002-of-009"
    ".audio_repair.json",
    "batch-runner/docs/run_records/audio_receipt_repair_v1/"
    "exp035_codex_foundry_full220__src_fd0db9d9d78d6d54__shard-008-of-009"
    ".audio_repair.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hashes_the_readme_publishes() -> dict[str, str]:
    """Read the README's fenced hash blocks as ``{filename: sha256}``.

    The README writes each hash on its own line with the file it belongs to on
    the next, which is the shape ``sha256sum`` prints. Parsing that rather than
    hard-coding the values here keeps this test honest: if someone edits the
    README to match a changed file, the assertion below still has to agree with
    the file itself.
    """
    pairs: dict[str, str] = {}
    lines = README.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines[:-1]):
        match = re.fullmatch(r"([0-9a-f]{64})", line.strip())
        if match is None:
            continue
        named = lines[index + 1].strip()
        if named:
            pairs[Path(named).name] = match.group(1)
    return pairs


@pytest.mark.parametrize("relative", PUBLISHED)
def test_git_is_carrying_every_published_file(relative: str) -> None:
    """A path the README names must be one a clone receives.

    Asks git rather than reading the allowlist, because the allowlist is the
    thing that goes stale. ``--error-unmatch`` is satisfied by a staged file as
    well as a committed one, which is the right moment to catch this: before
    the commit that would have shipped without it.
    """
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
def test_every_published_file_is_actually_here(relative: str) -> None:
    """Tracked and present are different failures, so they are checked apart."""
    assert (REPO_ROOT / relative).is_file(), f"{relative} is not in this checkout"


def test_the_readme_publishes_the_script_hash_the_script_actually_has() -> None:
    """The script's own hash is the only thing tying a derived file to a method.

    Each derived file records the hash of the script that wrote it. If the
    README's copy of that hash drifts from the script on disk, a reader
    checking provenance gets a mismatch and no way to tell which of the two is
    lying.
    """
    published = _hashes_the_readme_publishes()
    assert SCRIPT.name in published, (
        f"the README no longer publishes a hash for {SCRIPT.name}"
    )
    assert published[SCRIPT.name] == _sha256(SCRIPT), (
        "the README's hash for the derivation script does not match the script "
        "in this checkout. Either the script changed without the record being "
        "redone, or the record was edited by hand."
    )


@pytest.mark.parametrize(
    "name",
    [
        "exp035_codex_foundry_full220__src_fd0db9d9d78d6d54__shard-002-of-009"
        ".audio_repair.json",
        "exp035_codex_foundry_full220__src_fd0db9d9d78d6d54__shard-008-of-009"
        ".audio_repair.json",
    ],
)
def test_the_readme_publishes_the_derived_hashes_they_actually_have(
    name: str,
) -> None:
    published = _hashes_the_readme_publishes()
    assert name in published, f"the README no longer publishes a hash for {name}"
    assert published[name] == _sha256(RECORD_DIR / name), (
        f"{name} does not hash to what the README says. The derivation is "
        "deterministic, so a difference here is a file that was edited rather "
        "than re-derived."
    )


def test_the_reproduction_command_names_a_file_that_is_here() -> None:
    """The README's own instruction has to be runnable.

    It is the one place a reader is told to stop trusting the hashes above and
    check for themselves, which only works if the file it names exists.
    """
    text = README.read_text(encoding="utf-8")
    match = re.search(r"python3 (scripts/[\w./-]+\.py)", text)
    assert match is not None, (
        "the README no longer shows a reproduction command, so nothing here "
        "checks that the derived files can be re-derived at all"
    )
    named = BATCH_RUNNER_ROOT / match.group(1)
    assert named.is_file(), (
        f"the README says to run {match.group(1)}, which is not in this "
        "checkout"
    )


def test_the_derivation_script_does_not_move_the_grader_fingerprint() -> None:
    """Adding a way to read the evidence must not disturb the evidence.

    ``batch-runner/scripts/`` is outside the frozen set on purpose: the checks
    that read a paid run have to be able to land during one. If this script
    ever became grader source, committing it would move the fingerprint every
    published grade was signed under, and the repair would have damaged the
    thing it set out to describe.
    """
    assert not freeze.is_grader_source_path(
        "batch-runner/scripts/derive_audio_receipt_repair.py"
    )
    assert not freeze.is_grader_source_path(
        "batch-runner/docs/run_records/audio_receipt_repair_v1/README.md"
    )
