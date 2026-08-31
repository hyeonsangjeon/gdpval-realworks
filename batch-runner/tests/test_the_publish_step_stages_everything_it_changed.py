"""The publish step commits by naming paths, and twice it named too few.

Both defects have the same shape and neither announced itself. The publish
step stages ``git add -- "$SOME_FILE"`` for each output it knows about. Any
change that is not one of those named paths is simply not committed, and
because ``git commit`` succeeds on what *was* staged, the run goes green or
fails somewhere unrelated.

  RUN 33422393221 -- shard 4 graded all seventeen of its tasks and died in the
  publish step with exit 128. One of those tasks, ``9e39df84``, had been cut
  in half by the clock in an earlier chunk, so that chunk committed a
  checkpoint under ``_progress/``. When this chunk finished the task, step8
  deleted the checkpoint -- correctly; it described nothing any more. But the
  file was tracked, the delete was never staged, and::

      error: cannot pull with rebase: You have unstaged changes.
      Process completed with exit code 128.

  Four hours of paid grading reached the publish step intact and had to be
  recovered from the uploaded artifact instead.

  RUN 33445681382 -- the merge step wrote the first complete 185-task grade
  and committed it. step9 also wrote that grade's cost ledger beside it, and
  the payload names the ledger and carries its SHA-256. Only the grade was
  staged. Main now holds a merged grade whose ``cost_ledger.path`` points at a
  file no clone of this repository contains: an honest pointer to nothing.
  Nothing failed, and nothing would, until somebody tried to verify the cost.

The two are one lesson: a step that stages named paths has to name everything
it changed, including the things it *removed* and the things a subprocess
wrote on its behalf.

The shell under test is sliced out of the shipped workflow rather than
paraphrased -- a paraphrase passes while the workflow ships something else,
which is exactly the class of defect this file is about. No model, no network.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"

COMMIT_STEP = "Commit grade result"
MERGE_STEP = "Merge shards into the final grade"


# ── slicing the shipped shell ────────────────────────────────────────────


def _step(name: str) -> dict:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name") == name:
                return step
    raise AssertionError(f"grade-run.yml has no step named {name!r}")


def _slice(step_name: str, first: str, last: str) -> str:
    """The shipped lines from the one starting with ``first`` up to ``last``.

    Both anchors must be unique. An anchor that matches twice would silently
    take the first hit and test a fragment nobody ships -- the same
    substitute-a-copy failure the module docstring warns about, one level up.
    """
    lines = _step(step_name)["run"].splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip().startswith(first)]
    if len(starts) != 1:
        raise AssertionError(f"{step_name}: {first!r} matches {len(starts)} lines")
    ends = [
        i for i, line in enumerate(lines)
        if i > starts[0] and line.strip().startswith(last)
    ]
    if not ends:
        raise AssertionError(f"{step_name}: no {last!r} after {first!r}")
    return "\n".join(lines[starts[0]:ends[0]]) + "\n"


def checkpoint_fragment() -> str:
    return _slice(COMMIT_STEP, 'PROGRESS_DIR=', 'if git diff --staged --quiet')


def ledger_fragment() -> str:
    return _slice(MERGE_STEP, 'MERGED_LEDGER=', 'if git diff --staged --quiet')


# ── a repository shaped like the runner's checkout ───────────────────────


GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}

SHARD_DIR = "data/grades/_diagnostic/corpus/_shards/run__src_abc__v2.2"
GRADE = f"{SHARD_DIR}/shard-004-of-011.json"
CKPT = f"{SHARD_DIR}/_progress/shard-004-of-011__9e39df84.json"
SIBLING_CKPT = f"{SHARD_DIR}/_progress/shard-007-of-011__deadbeef.json"

MERGED = "data/grades/_diagnostic/corpus/run__src_abc__v2.2.json"
MERGED_LEDGER = "data/grades/_diagnostic/corpus/run__src_abc__v2.2.cost_ledger.jsonl"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True, check=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(cwd), **GIT_ENV},
    )
    return result.stdout


def _write(repo: Path, relative: str, content: str) -> Path:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def bindir(tmp_path_factory) -> Path:
    """A PATH the fragments can find ``python`` on.

    The fragments shell out to ``python``; CI runners have one, this
    interpreter may be a venv that is not on ``/usr/bin``. Symlinking the
    running interpreter keeps the fragment's own heredocs under test instead
    of skipping them.
    """
    d = tmp_path_factory.mktemp("bin")
    (d / "python").symlink_to(sys.executable)
    return d


@pytest.fixture
def repo(tmp_path) -> Path:
    if shutil.which("git") is None:  # pragma: no cover - git is a hard dep here
        pytest.skip("git is required")
    r = tmp_path / "checkout"
    r.mkdir()
    _git(r, "init", "--initial-branch=main", "--quiet")
    return r


def _run(fragment: str, repo: Path, bindir: Path, **env: str):
    return subprocess.run(
        ["bash", "-e", "-c", fragment], cwd=repo, capture_output=True, text=True,
        env={"PATH": f"{bindir}:/usr/bin:/bin", "HOME": str(repo), **GIT_ENV, **env},
    )


def _unstaged(repo: Path) -> list[str]:
    """What ``git pull --rebase`` would refuse to run over."""
    return _git(repo, "diff", "--name-only").split()


# ── the checkpoint a finished task leaves behind ─────────────────────────


@pytest.fixture
def resumed(repo: Path) -> Path:
    """An earlier chunk's committed checkpoint, and this chunk finishing it."""
    _write(repo, GRADE, '{"tasks": []}\n')
    _write(repo, CKPT, '{"completed_items": [1, 2, 3]}\n')
    _write(repo, SIBLING_CKPT, '{"completed_items": [9]}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "partial chunk 0")

    # What this chunk does: grades the task whole, then discards the progress
    # file that described it as unfinished (core.task_checkpoint.discard).
    _write(repo, GRADE, '{"tasks": [{"task_id": "9e39df84"}]}\n')
    (repo / CKPT).unlink()
    _git(repo, "add", "--", GRADE)
    return repo


def test_the_finished_checkpoints_removal_is_staged(resumed, bindir):
    """Run 33422393221, replayed: the delete now lands in the commit."""
    result = _run(checkpoint_fragment(), resumed, bindir, GRADE_FILE=GRADE)
    assert result.returncode == 0, result.stderr

    staged = _git(resumed, "diff", "--staged", "--name-status").split()
    assert f"D\t{CKPT}".split() == staged[staged.index("D"):staged.index("D") + 2]
    assert CKPT in _git(resumed, "diff", "--staged", "--name-only")


def test_nothing_is_left_for_the_rebase_to_refuse(resumed, bindir):
    """The property that actually mattered, stated as the error did.

    ``git pull --rebase`` does not care what is staged; it refuses when
    anything is *un*staged. Asserting the delete was added is not the same
    claim as asserting the working tree is clean, and it was the second one
    that failed in production.
    """
    assert _unstaged(resumed) == [CKPT], "fixture should start dirty"
    _run(checkpoint_fragment(), resumed, bindir, GRADE_FILE=GRADE)
    assert _unstaged(resumed) == []


def test_a_siblings_checkpoint_is_not_swept_up(resumed, bindir):
    """Eleven shards share one ``_progress/`` directory.

    ``git add -A`` would have fixed the reported bug and quietly given every
    shard the power to commit its siblings' state. The stage is scoped to this
    grade's own stem, so a sibling's deleted checkpoint stays untouched.
    """
    (resumed / SIBLING_CKPT).unlink()
    result = _run(checkpoint_fragment(), resumed, bindir, GRADE_FILE=GRADE)
    assert result.returncode == 0, result.stderr

    assert SIBLING_CKPT not in _git(resumed, "diff", "--staged", "--name-only")
    assert SIBLING_CKPT in _unstaged(resumed)


def test_an_ordinary_chunk_with_no_checkpoint_is_untouched(repo, bindir):
    """Almost every chunk. The fragment must be a no-op, not an error."""
    _write(repo, GRADE, '{"tasks": []}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "plain")

    result = _run(checkpoint_fragment(), repo, bindir, GRADE_FILE=GRADE)
    assert result.returncode == 0, result.stderr
    assert _git(repo, "diff", "--staged", "--name-only").split() == []


# ── the ledger the merge wrote and did not commit ────────────────────────


def _merged(repo: Path, *, ledger: str | None, claim: str | None) -> None:
    """A merged grade, optionally with its ledger and a claim about it."""
    payload: dict = {"run_status": "final", "tasks": []}
    if claim is not None:
        payload["cost_ledger"] = {"path": Path(MERGED_LEDGER).name, "sha256": claim}
    _write(repo, MERGED, json.dumps(payload, indent=2))
    if ledger is not None:
        _write(repo, MERGED_LEDGER, ledger)
    _git(repo, "add", "--", MERGED)


LEDGER_BODY = '{"call_id": 1, "input_tokens": 10}\n{"call_id": 2}\n'
LEDGER_SHA = hashlib.sha256(LEDGER_BODY.encode()).hexdigest()


def test_the_merged_ledger_is_committed_with_the_merge(repo, bindir):
    """Run 33445681382, replayed: the pointer now has a file behind it."""
    _merged(repo, ledger=LEDGER_BODY, claim=LEDGER_SHA)
    result = _run(ledger_fragment(), repo, bindir, FINAL_FILE=MERGED)
    assert result.returncode == 0, result.stderr

    staged = _git(repo, "diff", "--staged", "--name-only").split()
    assert MERGED_LEDGER in staged
    assert MERGED in staged


def test_a_claimed_ledger_that_is_not_there_stops_the_merge(repo, bindir):
    """Fail closed. Publishing the pointer alone is what created the defect."""
    _merged(repo, ledger=None, claim=LEDGER_SHA)
    result = _run(ledger_fragment(), repo, bindir, FINAL_FILE=MERGED)

    assert result.returncode != 0
    assert "claims a cost ledger that is not on disk" in result.stdout + result.stderr
    assert MERGED_LEDGER not in _git(repo, "diff", "--staged", "--name-only")


def test_a_ledger_that_drifted_from_its_digest_stops_the_merge(repo, bindir):
    """A file under the right name is not evidence that it is the right file."""
    _merged(repo, ledger=LEDGER_BODY + '{"call_id": 3}\n', claim=LEDGER_SHA)
    result = _run(ledger_fragment(), repo, bindir, FINAL_FILE=MERGED)

    assert result.returncode != 0
    assert "does not match the digest" in result.stdout + result.stderr


def test_a_merge_claiming_no_ledger_is_left_alone(repo, bindir):
    """Older payloads carry no ``cost_ledger``; the merge must still publish."""
    _merged(repo, ledger=None, claim=None)
    result = _run(ledger_fragment(), repo, bindir, FINAL_FILE=MERGED)

    assert result.returncode == 0, result.stderr
    assert _git(repo, "diff", "--staged", "--name-only").split() == [MERGED]


# ── the defects, named so a rewrite cannot reintroduce them quietly ──────


def test_the_merge_step_still_stages_a_ledger_at_all():
    """Structural, because the behavioural tests above run a *slice*.

    If someone deletes the block, ``_slice`` raises and every behavioural test
    errors -- loudly, but with a message about anchors rather than about cost
    provenance. This says the thing itself.
    """
    run = _step(MERGE_STEP)["run"]
    assert 'git add -- "$MERGED_LEDGER"' in run
    assert run.index('git add -- "$FINAL_FILE"') < run.index('MERGED_LEDGER=')


def test_the_commit_step_stages_deletions_without_reaching_for_add_dash_A():
    """``git add -A`` in this step is the fix that is worse than the bug."""
    run = _step(COMMIT_STEP)["run"]
    assert "git ls-files --deleted" in run

    # Comments stripped first. The block this guards *discusses* ``git add -A``
    # by name, to say why it was not used -- and an earlier draft of this test
    # failed on that sentence, which is a checker reading the explanation as
    # the thing explained.
    code = "\n".join(
        line for line in run.splitlines() if not line.strip().startswith("#")
    )
    for blunt in ("git add -A", "git add --all", "git add ."):
        assert blunt not in code, f"{blunt!r} would commit a sibling shard's state"
