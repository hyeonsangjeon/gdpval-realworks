"""A test file that no CI job executes gates nothing, and says nothing.

`scripts/__tests__/` sat outside CI for its whole life. The backend job
changes into `batch-runner` before invoking pytest, and `npm test` picks up
only the `.mjs` files that share that directory, so eight Python files and
ninety-five test functions ran nowhere. Two of them were red on `main` --
`test_sol_max_anchor_selection.py` since #188 (2026-08-21) and
`test_analyze_grade_run.py` since #302 (2026-08-31) -- and nothing reported
it. They were found by hand, days later.

Wiring that directory in fixes the instance. This guards the class: a third
directory of tests can be added just as easily, and it would be just as
silent. So every Python test file in the repository has to live somewhere a
CI job actually runs, and the roots below have to be the ones the workflow
names -- otherwise deleting the step would leave this passing.

This guard deliberately lives under `batch-runner/tests/`, the directory CI
has run since the beginning. In `scripts/__tests__/` it could be switched off
by the very defect it exists to catch.
"""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/backend-tests.yml"

# Every directory a pytest invocation in backend-tests.yml reaches. Adding a
# test directory means adding a step there and a line here, in one commit.
COVERED_ROOTS = (
    "batch-runner/tests",
    "scripts/__tests__",
)


def _test_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("test_*.py")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    )


def _pytest_targets() -> set[Path]:
    """The directories the workflow's pytest invocations actually reach.

    Matching the workflow text for a directory name is not enough -- the name
    appears in comments too, and a comment runs nothing. This reads the
    invocations: a `run:` block may `cd` somewhere first, and an invocation
    with no path argument collects everything beneath wherever it is standing.

    Path arguments are told apart from flag values by asking the filesystem
    rather than by parsing option syntax, so `-m "not integration"` needs no
    special case: `not integration` is not a directory.
    """
    targets: set[Path] = set()
    base = REPO_ROOT

    for raw in WORKFLOW.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            continue
        if line.startswith("- name:"):
            base = REPO_ROOT  # a new step starts back at the repo root
        elif line.startswith("cd "):
            base = REPO_ROOT / line[3:].strip()
        elif "python -m pytest" in line:
            args = shlex.split(line.split("python -m pytest", 1)[1])
            paths = [base / arg for arg in args if (base / arg).is_dir()]
            targets.update(path.resolve() for path in (paths or [base]))

    return targets


def test_every_python_test_file_sits_under_a_root_ci_runs():
    files = _test_files()

    # If this is ever near-empty the check below passes for the wrong reason.
    assert len(files) > 100, f"only found {len(files)} test files; rglob broke"

    stranded = [
        str(path.relative_to(REPO_ROOT))
        for path in files
        if not str(path.relative_to(REPO_ROOT)).startswith(COVERED_ROOTS)
    ]
    assert not stranded, (
        "these test files are not under any root backend-tests.yml runs, so "
        "nothing executes them and they can be red indefinitely without a "
        f"single red run: {stranded}"
    )


@pytest.mark.parametrize("root", COVERED_ROOTS)
def test_the_workflow_still_runs_each_root_this_file_vouches_for(root: str):
    """The list above is only true while the workflow still runs each root.

    Without this, removing a pytest step would strand a whole directory again
    and the check above would keep passing -- it would simply be reading a
    list that had quietly stopped describing CI.
    """
    directory = (REPO_ROOT / root).resolve()
    targets = _pytest_targets()

    assert any(
        directory == target or target in directory.parents for target in targets
    ), (
        f"{root} is listed as CI-covered here, but no pytest invocation in "
        f"{WORKFLOW.name} reaches it. Reached instead: "
        f"{sorted(str(t.relative_to(REPO_ROOT)) or '.' for t in targets)}. "
        "Either restore the step or stop claiming the directory is covered."
    )


def test_the_orphaned_directory_that_prompted_this_is_actually_wired():
    """The specific regression, pinned separately from the general rule.

    The rule above is satisfied by any invocation reaching the path, including
    one rooted higher up. This asserts the shape that was missing: a pytest run
    naming the directory, from the repository root.
    """
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "python -m pytest scripts/__tests__" in workflow, (
        "the repo-root script tests are unwired again; they resolve fixtures "
        "through parents[2] and must be invoked from the repository root"
    )


@pytest.mark.parametrize("root", COVERED_ROOTS)
def test_a_change_under_each_covered_root_actually_starts_this_workflow(root: str):
    """A step that exists but never fires is still a step nobody runs.

    Wiring the invocation fixed half of it. The trigger did not follow: the
    path filter listed only `batch-runner/**`, so a pull request touching
    just repo-root `scripts/` started no run, and the step above never
    executed on the change it was added to cover.

    Measured, not inferred -- #392 changed `scripts/grading_cost_sweep.py` and
    added twenty-five tests under `scripts/__tests__/`, and the only workflow
    that ran on it was Aggregate Tests & Deploy. The suite was green and
    nothing had checked it.
    """
    triggers = _trigger_block()

    for event in ("pull_request", "push"):
        patterns = triggers[event]["paths"]
        assert any(_pattern_covers(pattern, root) for pattern in patterns), (
            f"a change under {root}/ starts no {event} run of "
            f"{WORKFLOW.name}, so the pytest step that covers it never "
            f"executes. Filter is: {patterns}"
        )


def _trigger_block() -> dict:
    """The workflow's `on:` mapping.

    Keyed by `True`, not by `"on"` -- PyYAML follows YAML 1.1, where a bare
    `on` is a boolean. Reading `["on"]` here would raise `KeyError` rather
    than check anything, so both spellings are accepted.
    """
    document = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = document.get("on", document.get(True))
    assert isinstance(triggers, dict), f"no trigger block in {WORKFLOW.name}"
    return triggers


def _pattern_covers(pattern: str, root: str) -> bool:
    """Whether a workflow path filter would match a file under `root`.

    Only the `dir/**` and exact-path forms this workflow uses are understood;
    anything cleverer should be checked deliberately rather than guessed at.
    """
    if pattern.endswith("/**"):
        return (root + "/").startswith(pattern[:-2])
    return pattern == root


