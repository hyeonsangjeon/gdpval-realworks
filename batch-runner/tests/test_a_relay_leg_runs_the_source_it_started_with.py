"""A relay leg runs the pipeline its first leg ran, and says so or stops.

The relay hands a half-finished experiment from one runner to the next. Until
now the only thing keeping the legs on the same code was the dispatch
contract's `SOURCE_SHA == EVENT_SHA`, and that is a proxy for the wrong thing
in both directions.

It is too strict, and measurably so. The retrigger is `gh workflow run
batch-run.yml --ref main`, which resolves main again at every handover, so one
unrelated commit ends the run. Run `34540053904` started at `a21eec3` and main
had moved twice before its first leg finished; the eleven `batch-runner/` files
that changed in between were a probe, an analysis script and their tests, none
of them on the execution path that run was using. Its second leg would have
died at a `[[ ]]` for that.

It is also too loose. When it passed, it passed because nobody had pushed yet
-- and the leg then checked out main's tip, so the guarantee was luck. A commit
landing one second after the dispatch was resolved would have been picked up
silently, changing the pipeline between task 40 and task 41 of one experiment
with nothing in the record to say so.

What replaces it is the thing the proxy stood for: the leg checks out the first
leg's `batch-runner/` tree. Two residues cannot be covered that way and are
checked instead -- that `SOURCE_SHA` is an ancestor of this event, and that
`batch-run.yml` itself has not changed, since Actions runs the dispatch ref's
copy of the workflow and a checkout cannot reach it.

These tests run the steps rather than reading them. A guard that is present but
inverted, or shadowed by an earlier `exit`, passes any assertion made against
the text of a `run:` block. For the two git-reading steps that means building a
real repository in `tmp_path` and handing the step two real commits, which is
also the only way to find out whether the commands do what their names suggest
-- `git checkout <sha> -- <path>` writes and overwrites but never deletes, and
that asymmetry is a test below rather than a comment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BATCH_WORKFLOW = ROOT / ".github" / "workflows" / "batch-run.yml"
WORKFLOW_PATH_IN_REPO = ".github/workflows/batch-run.yml"


def _document() -> dict:
    return yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))


def _step(job: str, name: str) -> dict:
    steps = _document()["jobs"][job]["steps"]
    return next(item for item in steps if item.get("name") == name)


def _run_step(
    job: str, name: str, *, cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess:
    """Execute a step's `run:` block as bash, with exactly `env` in scope."""
    script = cwd / f"_{name.replace(' ', '_')}.sh"
    script.write_text(_step(job, name)["run"], encoding="utf-8")
    return subprocess.run(
        ["bash", str(script)],
        cwd=cwd,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(cwd), **env},
        capture_output=True,
        text=True,
    )


# --- the dispatch contract, which no longer pins the commit -----------------


CONTRACT_BASE = {
    "EVENT_NAME": "workflow_dispatch",
    "EVENT_REF": "refs/heads/main",
    "EVENT_SHA": "a" * 40,
    "WORKFLOW_SHA": "a" * 40,
    "WALL_TIMEOUT": "290",
    "RELAY_RUN": "1",
    "RELAY_LINEAGE_ID": "exp035:1:1",
    "SOURCE_SHA": "a" * 40,
    "SANDBOX_IMAGE_DIGEST": "",
}


def _contract(tmp_path: Path, **overrides: str) -> subprocess.CompletedProcess:
    return _run_step(
        "inspect-mode",
        "Verify dispatch contract",
        cwd=tmp_path,
        env={**CONTRACT_BASE, **overrides},
    )


def test_a_relay_leg_is_no_longer_refused_because_main_moved(tmp_path):
    """The change itself, stated as the case that used to fail.

    Measured against the unmodified workflow this combination exited 1, which
    is why run 34540053904 could not have relayed.
    """
    result = _contract(tmp_path, EVENT_SHA="b" * 40, WORKFLOW_SHA="b" * 40)
    assert result.returncode == 0, result.stderr


def test_the_first_leg_still_may_not_name_a_source(tmp_path):
    """Leg zero has nothing to continue, so a forwarded sha there is a bug."""
    result = _contract(
        tmp_path, RELAY_RUN="0", RELAY_LINEAGE_ID="", SOURCE_SHA="a" * 40
    )
    assert result.returncode != 0


@pytest.mark.parametrize("value", ["", "main", "A" * 40, "a" * 39, "a" * 41])
def test_a_relay_leg_still_needs_a_real_sha(tmp_path, value):
    """The sha is the checkpoint's address, not a label.

    `_lineage_root` hashes it to find the run's files on the hub, so a
    malformed one does not degrade to a slow path -- it addresses nothing.
    """
    result = _contract(tmp_path, SOURCE_SHA=value)
    assert result.returncode != 0


def test_the_dispatch_ref_is_still_main_only(tmp_path):
    """Nothing here loosens where a credentialed run may be launched from.

    Pinning by tag would have been the other way to solve this, and it would
    have meant accepting `refs/tags/...` as a dispatch ref. That trade was not
    made.
    """
    result = _contract(tmp_path, EVENT_REF="refs/tags/relay-34540053904")
    assert result.returncode != 0


# --- the lineage check, against real commits --------------------------------


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "HOME": str(cwd),
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid",
        },
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """A repository with a workflow file and one `batch-runner/` module."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "batch-run.yml").write_text(
        "name: batch-run\n", encoding="utf-8"
    )
    (repo / "batch-runner").mkdir()
    (repo / "batch-runner" / "runner.py").write_text("V = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "first")
    return repo


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _lineage(
    repo: Path, *, source_sha: str, github_sha: str
) -> subprocess.CompletedProcess:
    return _run_step(
        "inspect-mode",
        "Verify relay source lineage",
        cwd=repo,
        env={"SOURCE_SHA": source_sha, "GITHUB_SHA": github_sha},
    )


def test_an_unrelated_commit_on_main_does_not_end_the_run(tmp_path):
    """The live case: somebody merged something that is not this pipeline."""
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("a line\n", encoding="utf-8")
    event = _commit(repo, "docs")

    result = _lineage(repo, source_sha=source, github_sha=event)
    assert result.returncode == 0, result.stderr
    assert "unchanged between them" in result.stdout


def test_a_changed_batch_runner_does_not_end_the_run_either(tmp_path):
    """Because the pin rolls it back rather than the lineage refusing it.

    This is the eleven files of the live case. Refusing here would have left
    the freeze exactly where it was, just with a longer explanation.
    """
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / "batch-runner" / "runner.py").write_text("V = 2\n", encoding="utf-8")
    event = _commit(repo, "someone else's module")

    assert _lineage(repo, source_sha=source, github_sha=event).returncode == 0


def test_a_commit_that_was_never_on_main_is_refused(tmp_path):
    """A sibling branch is not a leg of this run.

    The checkpoint is addressed by `sha256(source_sha, lineage_id)`, so a
    caller free to name any commit could have a credentialed leg run code that
    was never reviewed onto main.
    """
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "batch-runner" / "runner.py").write_text("V = 9\n", encoding="utf-8")
    sibling = _commit(repo, "side")
    _git(repo, "checkout", "-q", "main")
    (repo / "README.md").write_text("main moved\n", encoding="utf-8")
    event = _commit(repo, "main")

    assert base != sibling
    assert _lineage(repo, source_sha=sibling, github_sha=event).returncode != 0


def test_a_changed_workflow_file_is_refused_and_named(tmp_path):
    """The one file the pin cannot reach, so the run stops instead.

    Actions runs the dispatch ref's copy of this workflow, and the dispatch ref
    has to be main. A leg orchestrated by steps the first leg never ran is a
    different experiment, and no checkout of `batch-runner/` changes that.
    """
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / WORKFLOW_PATH_IN_REPO).write_text(
        "name: batch-run\n# and a new step\n", encoding="utf-8"
    )
    event = _commit(repo, "workflow")

    result = _lineage(repo, source_sha=source, github_sha=event)
    assert result.returncode != 0
    assert "batch-run.yml changed since the first leg" in result.stdout + result.stderr
    # The reader is told the work is not lost, because the reflex on seeing a
    # relay leg fail is to start the experiment again from zero.
    assert "checkpoint" in result.stdout + result.stderr


def test_the_same_commit_twice_is_still_the_ordinary_case(tmp_path):
    """Nothing landed between the legs. A commit is its own ancestor."""
    repo = _repo(tmp_path)
    sha = _git(repo, "rev-parse", "HEAD")
    assert _lineage(repo, source_sha=sha, github_sha=sha).returncode == 0


# --- the pin, against real commits ------------------------------------------


def _pin(repo: Path, *, source_sha: str, github_sha: str):
    return _run_step(
        "batch-run",
        "Pin pipeline source to the first leg",
        cwd=repo,
        env={"SOURCE_SHA_INPUT": source_sha, "GITHUB_SHA": github_sha},
    )


def test_a_module_that_changed_is_rolled_back_to_the_first_leg(tmp_path):
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / "batch-runner" / "runner.py").write_text("V = 2\n", encoding="utf-8")
    event = _commit(repo, "changed")

    result = _pin(repo, source_sha=source, github_sha=event)
    assert result.returncode == 0, result.stderr
    assert (repo / "batch-runner" / "runner.py").read_text(encoding="utf-8") == "V = 1\n"


def test_a_module_added_since_is_removed_rather_than_left_importable(tmp_path):
    """`git checkout <sha> -- <path>` writes and overwrites but never deletes.

    Without the removal the next leg would carry a module the first leg never
    had. Nothing would import it today, which is exactly why the omission would
    have gone unnoticed until something did.
    """
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / "batch-runner" / "newcomer.py").write_text("V = 3\n", encoding="utf-8")
    event = _commit(repo, "added")

    assert _pin(repo, source_sha=source, github_sha=event).returncode == 0
    assert not (repo / "batch-runner" / "newcomer.py").exists()


def test_a_file_outside_batch_runner_is_left_alone(tmp_path):
    """The pin is about the pipeline, not about undoing the repository.

    HEAD is main's tip and the results pull request is branched from it, so
    rolling back the tree wholesale would be a rollback of everyone else's work
    wearing an experiment's title.
    """
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / "README.md").write_text("newer\n", encoding="utf-8")
    event = _commit(repo, "docs")

    assert _pin(repo, source_sha=source, github_sha=event).returncode == 0
    assert (repo / "README.md").read_text(encoding="utf-8") == "newer\n"
    assert _git(repo, "rev-parse", "HEAD") == event


def test_the_rollback_is_not_staged_for_the_results_pull_request(tmp_path):
    """create-pull-request commits the index it finds.

    `git checkout <sha> -- <path>` stages what it writes. Left staged, the
    results pull request -- which is supposed to carry one report file --
    would also carry a revert of every `batch-runner/` change merged during the
    run. The step unstages, so the working tree keeps the first leg's files
    while the index still matches HEAD.
    """
    repo = _repo(tmp_path)
    source = _git(repo, "rev-parse", "HEAD")
    (repo / "batch-runner" / "runner.py").write_text("V = 2\n", encoding="utf-8")
    (repo / "batch-runner" / "newcomer.py").write_text("V = 3\n", encoding="utf-8")
    event = _commit(repo, "changed and added")

    assert _pin(repo, source_sha=source, github_sha=event).returncode == 0
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    # ...and the working tree really is the first leg's, so the unstaging did
    # not also undo the pin.
    assert (repo / "batch-runner" / "runner.py").read_text(encoding="utf-8") == "V = 1\n"


def test_nothing_having_changed_is_not_an_error(tmp_path):
    """The common case once a freeze is actually held."""
    repo = _repo(tmp_path)
    sha = _git(repo, "rev-parse", "HEAD")
    result = _pin(repo, source_sha=sha, github_sha=sha)
    assert result.returncode == 0, result.stderr
    assert "0 file(s) differ" in result.stdout


# --- the wiring the two steps depend on -------------------------------------


@pytest.mark.parametrize(
    "job,step",
    [
        ("inspect-mode", "Checkout config only"),
        ("batch-run", "Checkout"),
    ],
)
def test_both_checkouts_fetch_the_whole_history(job, step):
    """`fetch-depth: 0`, written out, and not as a conditional.

    The conditional anybody would reach for is wrong in a way that reads as
    correct: `${{ inputs.relay_run > 0 && 0 || 1 }}` always renders 1, because
    Actions' `a && b || c` yields `c` whenever `b` is falsy and 0 is falsy. A
    relay leg would get the shallow clone, fail `merge-base --is-ancestor`, and
    stop -- safely, but hours into a paid run. This asserts the literal.
    """
    with_block = _step(job, step)["with"]
    assert with_block["fetch-depth"] == 0
    assert with_block["persist-credentials"] is False


@pytest.mark.parametrize(
    "job,step",
    [
        ("inspect-mode", "Verify relay source lineage"),
        ("batch-run", "Pin pipeline source to the first leg"),
    ],
)
def test_neither_new_step_touches_the_first_leg(job, step):
    """Leg zero has no source to pin and no ancestry to check.

    Both steps would fail on an empty `SOURCE_SHA`, which is the right
    behaviour for a relay leg and the wrong behaviour for every ordinary
    dispatch in the repository.
    """
    assert _step(job, step)["if"] == "inputs.relay_run > 0"


def test_the_pin_runs_before_anything_reads_the_pipeline():
    """A pin applied after the first `cd batch-runner` would pin nothing.

    Naming the steps rather than counting them, so inserting an unrelated step
    does not fail this.
    """
    names = [s.get("name") for s in _document()["jobs"]["batch-run"]["steps"]]
    pin = names.index("Pin pipeline source to the first leg")
    assert pin < names.index("Setup Python")
    assert pin < names.index("Validate experiment YAML exists")
    assert pin < names.index("Step 2a: Run inference (condition_a)")
    # And after the checkout it depends on, which is the only ordering that
    # could be got backwards without the file looking wrong.
    assert pin > names.index("Checkout")


def test_the_retrigger_still_forwards_the_first_legs_sha():
    """The pin reads `SOURCE_SHA_INPUT`, so the handover has to keep sending it.

    It is also the checkpoint's address. If a later edit made each leg forward
    its own `GITHUB_SHA` -- which would make the deleted equality assertion
    true again, and is the obvious wrong fix -- the next leg would look for its
    checkpoint under a key nothing had written.
    """
    retrigger = _step("batch-run", "Retrigger relay run")["run"]
    assert '-f source_sha="$SOURCE_SHA"' in retrigger
    assert 'SOURCE_SHA="$SOURCE_SHA_INPUT"' in retrigger
