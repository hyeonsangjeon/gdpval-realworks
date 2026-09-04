"""Eleven shards write to one branch; that must not be fatal to any of them.

Run ``33248832615`` was dispatched at ``d5c1e18`` at 10:53:02Z, cleared its
paid-approval gate, checked out main, and died. Not on a model error, not on a
budget — on ``origin/main moved after dispatch``. At 10:54:59Z, a hundred and
seventeen seconds into the approval wait, shard 3 had committed ``8828ba1``: a
single file, ``shard-003-of-011.json``, its own graded output.

Every shard commits its grade to main. With eleven of them and a chunked
resume, the branch tip is essentially never still, so a check demanding it be
unchanged since dispatch fails for the most ordinary reason there is — and it
fails *after* the approval, which is the one moment the run is least able to
absorb it.

What the check was protecting is real: the code that grades must be the code
that was reviewed and approved. So that is now what is checked. The branch tip
may advance; the grading inputs may not. A sibling's grade file moves the tip
and changes nothing this job reads, so it no longer costs a chunk.

Nothing here calls a model or a network. The behavioural tests run the shipped
shell fragment, sliced out of the workflow, against real local repositories.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"

PAID_STEP = "Verify checked out main and input files"
DRY_RUN_STEP = "Verify read-only checkout and input files"


# ── reading the workflow ─────────────────────────────────────────────────


def _steps() -> list[dict]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return [
        step
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    ]


def _step(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"grade-run.yml has no step named {name!r}")


def _input_paths(step_name: str) -> list[str]:
    """The pathspec list as the shipped step declares it."""
    lines = _step(step_name)["run"].splitlines()
    start = next(
        index for index, line in enumerate(lines)
        if line.strip() == "GRADING_INPUT_PATHS=("
    )
    paths: list[str] = []
    for line in lines[start + 1:]:
        if line.strip() == ")":
            return paths
        paths.append(line.strip())
    raise AssertionError(f"{step_name}: GRADING_INPUT_PATHS is not closed")


def _pin_fragment(step_name: str) -> str:
    """The shipped pin itself, so the behavioural tests run it and not a copy.

    Sliced rather than reimplemented: a paraphrase of a shell check passes
    happily while the workflow ships something else, which is the failure mode
    this file exists to rule out.
    """
    lines = _step(step_name)["run"].splitlines()
    start = next(
        index for index, line in enumerate(lines)
        if line.strip() == "GRADING_INPUT_PATHS=("
    )
    seen_pin_echo = False
    for end, line in enumerate(lines[start:], start=start):
        if "[pin] main advanced" in line:
            seen_pin_echo = True
        elif seen_pin_echo and line.strip() == "fi":
            return "set -euo pipefail\n" + "\n".join(lines[start:end + 1]) + "\n"
    raise AssertionError(f"{step_name}: could not find the end of the pin")


# ── what the list must and must not contain ──────────────────────────────


def test_neither_job_still_demands_an_unmoved_branch_tip():
    """The defect, named directly.

    ``refs/remotes/origin/main`` compared against ``$GITHUB_SHA`` is the line
    that killed run 33248832615, and an equality against ``$GITHUB_SHA``
    anywhere in these steps reintroduces it under a different spelling.
    """
    for step_name in (PAID_STEP, DRY_RUN_STEP):
        run = _step(step_name)["run"]
        assert "refs/remotes/origin/main" not in run, (
            f"{step_name} still pins the branch tip; a sibling shard's grade "
            "commit will kill this chunk again"
        )
        assert "origin/main moved after dispatch" not in run
        assert '"$(git rev-parse HEAD)" != "$GITHUB_SHA"' not in run


def test_both_jobs_pin_the_same_inputs():
    """Two copies in one file, held together by reading both.

    YAML has no include, so the fragment is duplicated. The duplication is
    only safe while a change to one is a failure about the other.
    """
    paid = _input_paths(PAID_STEP)
    dry_run = _input_paths(DRY_RUN_STEP)
    assert paid == dry_run, (
        "the read-only job and the paid job must agree on what counts as a "
        "grading input, or the dry run stops predicting the real one"
    )
    assert paid == sorted(paid), "kept sorted so a diff of the two reads cleanly"


def test_the_pin_covers_everything_the_source_hash_covers(monkeypatch):
    """Derived from the real hash function, not from a list typed twice.

    ``compute_grader_source_hash`` is what the merge compares across shards; a
    file inside it that the pin leaves out could change mid-run, and the change
    would surface as an unmergeable shard hours later instead of as a refusal
    here.

    The docstring above used to sit over a restatement of the hash function's
    file list, which is not the same thing as deriving it. The copy went stale
    the day the hash started following the ``-r`` include in
    ``requirements.txt``: the restatement still named one requirements file, so
    it agreed with itself while the pin missed a file the grader's identity had
    started to depend on. It now watches what the real function reads.
    """
    import step8_grade as s8

    monkeypatch.chdir(REPO_ROOT / "batch-runner")
    config_path = Path("grading_configs/gold_ceiling_185_v2_sol_max.yaml")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    seen: list[Path] = []
    real_read_bytes = Path.read_bytes

    def spy(self: Path) -> bytes:
        seen.append(self)
        return real_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", spy)
    s8.compute_grader_source_hash(str(config_path), config)
    monkeypatch.undo()

    covered = sorted({p.resolve().relative_to(REPO_ROOT).as_posix() for p in seen})
    # A spy that caught nothing would make every assertion below vacuous.
    assert len(covered) > 20, "the hash function read nothing, so this proves nothing"
    for expected in (
        "batch-runner/step8_grade.py",
        "batch-runner/requirements.txt",
        "batch-runner/requirements-renderer.txt",
    ):
        assert expected in covered, (
            f"{expected} is no longer read by the hash; if that is deliberate, "
            f"this list is measuring something other than what it was written for"
        )

    pinned = _input_paths(PAID_STEP)
    for relative in covered:
        assert any(
            relative == entry or relative.startswith(entry + "/")
            for entry in pinned
        ), f"{relative} feeds grader_source_hash but no pathspec covers it"


def test_the_pin_ignores_what_the_run_writes():
    """The grades are the moving part; pinning them is the bug itself."""
    pinned = _input_paths(PAID_STEP)
    for written in ("data/grades", "data", "data/tests", "public/generated"):
        assert written not in pinned, (
            f"{written} is an output of this workflow; pinning it makes every "
            "sibling shard's commit fatal again"
        )
    assert ".github/workflows/grade-run.yml" in pinned, (
        "the workflow is read by the resume it dispatches, so an edit to it "
        "mid-run is exactly the change that must stop a chunk"
    )


def test_the_unmoved_case_costs_nothing():
    """No fetch, no diff, when the tip is where it was.

    Most dispatches are not racing anything, and those should not pay a
    network round trip to learn it.
    """
    fragment = _pin_fragment(PAID_STEP)
    guard = 'if [[ "$HEAD_SHA" != "$GITHUB_SHA" ]]; then'
    assert guard in fragment
    assert fragment.index(guard) < fragment.index("git fetch")
    assert fragment.index(guard) < fragment.index("git diff")


# ── the race, replayed against real repositories ─────────────────────────


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args), cwd=cwd, capture_output=True, text=True, check=True,
        env={
            "PATH": "/usr/bin:/bin", "HOME": str(cwd),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
        },
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str, **files: str) -> str:
    for relative, content in files.items():
        path = repo / relative.replace("__", "/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def race(tmp_path):
    """An upstream main, and a shallow checkout of it — the runner's view.

    ``uploadpack.allowAnySHA1InWant`` is set because the fragment fetches one
    commit by identifier, and git refuses that by default over local transport.
    GitHub enables it server-side, so this makes the fixture behave like the
    remote the fragment actually talks to rather than granting it something
    new.
    """
    if shutil.which("git") is None:  # pragma: no cover - git is a hard dep here
        pytest.skip("git is required")

    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git(upstream, "init", "--initial-branch=main", "--quiet")
    _git(upstream, "config", "uploadpack.allowAnySHA1InWant", "true")
    dispatched = _commit(
        upstream, "base",
        **{
            "batch-runner__core__grader.py": "class Grader:\n    pass\n",
            "batch-runner__step8_grade.py": "def main():\n    return 0\n",
            "data__grades__shard-002-of-011.json": '{"tasks": []}\n',
            "src__App.tsx": "export const App = () => null\n",
        },
    )

    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "--depth=1", "--quiet", str(upstream), str(checkout))
    return upstream, checkout, dispatched


def _advance(upstream: Path, checkout: Path, message: str, **files: str) -> str:
    """Land a commit upstream and let the runner check it out, as it would."""
    head = _commit(upstream, message, **files)
    _git(checkout, "fetch", "--depth=1", "--quiet", "origin", "main")
    _git(checkout, "reset", "--hard", "--quiet", "FETCH_HEAD")
    return head


def _run_pin(checkout: Path, dispatched: str, step_name: str = PAID_STEP):
    return subprocess.run(
        ["bash", "-c", _pin_fragment(step_name)],
        cwd=checkout, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(checkout),
             "GITHUB_SHA": dispatched,
             "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
    )


def test_a_sibling_shard_landing_its_grade_does_not_stop_this_one(race):
    """Run 33248832615, replayed: the commit that killed it now passes.

    One file, ``shard-003-of-011.json``, committed by another shard while this
    one waited for approval. The tip moves, the diff is empty, the chunk runs.
    """
    upstream, checkout, dispatched = race
    moved = _advance(
        upstream, checkout, "chore(grades): grade [shard 3 of 11]",
        **{"data__grades__shard-003-of-011.json": '{"tasks": [1, 2, 3]}\n'},
    )
    assert moved != dispatched

    result = _run_pin(checkout, dispatched)

    assert result.returncode == 0, result.stderr
    assert "main advanced" in result.stdout
    # ``::error::`` is an annotation on stdout, as everywhere else in
    # this workflow; a run that emits none of them raised no objection.
    assert "::error::" not in result.stdout


def test_a_changed_grader_still_stops_the_chunk(race):
    """The property the old check was defending, kept intact.

    An approval was given for a revision. If the code moved underneath it, the
    approval no longer describes what would run, and the shard's grade would
    not merge with its siblings' anyway.
    """
    upstream, checkout, dispatched = race
    _advance(
        upstream, checkout, "fix(grader): change scoring",
        **{"batch-runner__core__grader.py": "class Grader:\n    SCORE = 2\n"},
    )

    result = _run_pin(checkout, dispatched)

    assert result.returncode == 1
    assert "grading inputs changed" in result.stdout
    assert "changed grading input: batch-runner/core/grader.py" in result.stdout


def test_a_grade_and_a_grader_moving_together_stops_the_chunk(race):
    """The benign file must not launder the dangerous one.

    A pathspec list that stopped at the first match, or a check that asked
    only whether *some* file was untouched, would let this through.
    """
    upstream, checkout, dispatched = race
    _advance(
        upstream, checkout, "chore: grades and a quiet edit",
        **{
            "data__grades__shard-003-of-011.json": '{"tasks": [1]}\n',
            "batch-runner__step8_grade.py": "def main():\n    return 7\n",
        },
    )

    result = _run_pin(checkout, dispatched)

    assert result.returncode == 1
    assert "changed grading input: batch-runner/step8_grade.py" in result.stdout


def test_an_unrelated_dashboard_commit_does_not_stop_the_chunk(race):
    """Session B works on ``src/`` while this runs. It should not collide."""
    upstream, checkout, dispatched = race
    _advance(
        upstream, checkout, "feat(ui): cost column",
        **{"src__App.tsx": "export const App = () => <table />\n"},
    )

    result = _run_pin(checkout, dispatched)

    assert result.returncode == 0, result.stderr


def test_a_still_tip_needs_no_network(race):
    """The unmoved case, proven by removing the remote before running it."""
    upstream, checkout, dispatched = race
    _git(checkout, "remote", "remove", "origin")

    result = _run_pin(checkout, dispatched)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""


def test_the_read_only_job_behaves_the_same_way(race):
    """The dry run predicts the paid run only if it decides the same way."""
    upstream, checkout, dispatched = race
    _advance(
        upstream, checkout, "chore(grades): grade [shard 3 of 11]",
        **{"data__grades__shard-003-of-011.json": '{"tasks": [1]}\n'},
    )
    assert _run_pin(checkout, dispatched, DRY_RUN_STEP).returncode == 0

    _advance(
        upstream, checkout, "fix(grader): change scoring",
        **{"batch-runner__core__grader.py": "class Grader:\n    SCORE = 3\n"},
    )
    assert _run_pin(checkout, dispatched, DRY_RUN_STEP).returncode == 1
