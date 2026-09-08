"""Where a Codex task's directories are allowed to live, and why it matters.

The short version: Codex builds the sandbox helper — the thing bubblewrap is
told to exec — as a symlink under ``$CODEX_HOME/tmp/arg0/`` when it starts, and
refuses to build it when ``CODEX_HOME`` is inside the temporary directory. Every
task directory in this repository used to be made with ``tempfile.mkdtemp()``,
so the helper was never built, so the agent could not execute anything anywhere.

What made that expensive to find is that the resulting message begins
``bwrap: ``:

    bwrap: execvp codex-linux-sandbox: No such file or directory

and the end-to-end tests treated any line starting ``bwrap: `` as "this machine
will not give Codex a sandbox" and skipped. On a machine that genuinely cannot
sandbox — which was every machine this project had — the skip was correct for
the wrong reason, and hid a defect that would have survived getting a working
host. It surfaced the first time the suite ran on a host measured able to
sandbox, with skips turned into failures.

These tests are about the rule, not about any host, so they run everywhere and
need neither a sandbox nor the Codex binary.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from core.codex_runtime_config import (
    RUN_ROOT_DIR_NAME,
    RUN_ROOT_ENV_NAME,
    CodexRunRootError,
    path_is_within,
    resolve_run_root_base,
    system_temporary_directory,
)

RELEVANT_NAMES = (RUN_ROOT_ENV_NAME, "XDG_CACHE_HOME", "HOME", "TMPDIR")


def environment(**values: str) -> dict[str, str]:
    """An environment with only the names these functions read.

    Built from nothing rather than from ``os.environ``, so a test cannot pass
    because of a variable the machine running it happened to have set.
    """
    return {name: value for name, value in values.items() if value}


# ── What "the temporary directory" means here ───────────────────────────────


def test_the_temporary_directory_is_the_one_the_binary_will_compute():
    """``$TMPDIR`` if set, ``/tmp`` otherwise — Rust's rule, not Python's.

    ``tempfile.gettempdir()`` reads ``TMPDIR``, ``TEMP`` and ``TMP`` in turn and
    would answer differently on a machine that set only the second or third.
    The value that decides whether Codex builds the helper is the one Codex
    computes, so that is the one computed here.
    """
    assert system_temporary_directory(environment()) == Path("/tmp")
    assert system_temporary_directory(
        environment(TMPDIR="/scratch/space")
    ) == Path("/scratch/space")
    # Set-but-empty is the same as unset, which is what Rust does with it.
    assert system_temporary_directory({"TMPDIR": ""}) == Path("/tmp")
    # And the names Python would have honoured are not honoured here.
    assert system_temporary_directory({"TEMP": "/elsewhere"}) == Path("/tmp")
    assert system_temporary_directory({"TMP": "/elsewhere"}) == Path("/tmp")


def test_containment_is_decided_after_symlinks_are_followed(tmp_path: Path):
    """A symlink out of the temporary directory does not make a path safe.

    ``/tmp`` is a symlink on some systems, and on those a textual prefix
    comparison answers "not inside" for a directory that plainly is. The check
    resolves both sides; this pins that, in both directions.
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)

    assert path_is_within(link / "child", real)
    assert path_is_within(real, real), "a directory is within itself"
    assert not path_is_within(tmp_path, real), "a parent is not within its child"

    sideways = tmp_path / "sideways"
    sideways.mkdir()
    assert not path_is_within(sideways, real)


# ── Choosing the directory ──────────────────────────────────────────────────


def test_the_cache_directory_is_used_when_nothing_overrides_it():
    assert resolve_run_root_base(
        environment(HOME="/home/someone")
    ) == Path("/home/someone/.cache") / RUN_ROOT_DIR_NAME


def test_an_explicit_cache_home_wins_over_the_home_directory():
    chosen = resolve_run_root_base(
        environment(HOME="/home/someone", XDG_CACHE_HOME="/var/cache/mine")
    )
    assert chosen == Path("/var/cache/mine") / RUN_ROOT_DIR_NAME


def test_the_override_wins_over_both_and_is_used_verbatim():
    """The override names a directory; nothing is appended to it.

    It exists for hosts where the derived answer is unusable — a home directory
    inside the temporary directory, or a disk somebody wants the run
    directories on — so it has to be able to name the directory exactly.
    """
    chosen = resolve_run_root_base(
        environment(
            HOME="/home/someone",
            XDG_CACHE_HOME="/var/cache/mine",
            **{RUN_ROOT_ENV_NAME: "/fast-disk/codex-runs"},
        )
    )
    assert chosen == Path("/fast-disk/codex-runs")


def test_the_directory_is_not_created_merely_by_asking_where_it_is(
    tmp_path: Path,
):
    """Answering the question leaves nothing behind.

    ``TMPDIR`` is pointed elsewhere so that ``tmp_path`` — which pytest makes
    under the real temporary directory — counts as an ordinary directory for
    the duration of this question.
    """
    target = tmp_path / "not-yet"
    resolve_run_root_base(
        environment(TMPDIR="/scratch/elsewhere", **{RUN_ROOT_ENV_NAME: str(target)})
    )
    assert not target.exists()


# ── Refusing the temporary directory ────────────────────────────────────────


def test_a_home_inside_the_temporary_directory_is_refused_not_used():
    """The failure mode this whole module exists to prevent.

    A machine whose ``HOME`` is inside ``/tmp`` would otherwise derive a run
    root inside ``/tmp`` and reproduce the original defect exactly — a run that
    starts cleanly and fails at the agent's first command.
    """
    with pytest.raises(CodexRunRootError) as raised:
        resolve_run_root_base(environment(HOME="/tmp/ephemeral-home"))
    message = str(raised.value)
    assert "codex-linux-sandbox" in message, "say what actually breaks"
    assert RUN_ROOT_ENV_NAME in message, "say what the reader can do about it"


def test_an_override_inside_the_temporary_directory_is_refused_too():
    """Naming it explicitly is not permission to reintroduce the fault.

    The override says *where*; it does not say *anywhere*. A setting that could
    switch the check off would be found and used by the first person who wanted
    a red run to go green, and the defect it guards against is invisible until
    the agent tries to execute something.
    """
    with pytest.raises(CodexRunRootError):
        resolve_run_root_base(
            environment(**{RUN_ROOT_ENV_NAME: "/tmp/somewhere-i-chose"})
        )


def test_the_refusal_follows_tmpdir_rather_than_the_literal_slash_tmp():
    """A relocated temporary directory is still the temporary directory."""
    with pytest.raises(CodexRunRootError):
        resolve_run_root_base(
            environment(
                TMPDIR="/scratch/tmp",
                **{RUN_ROOT_ENV_NAME: "/scratch/tmp/runs"},
            )
        )
    # ...and /tmp is then an ordinary directory, so it is allowed.
    assert resolve_run_root_base(
        environment(TMPDIR="/scratch/tmp", **{RUN_ROOT_ENV_NAME: "/tmp/runs"})
    ) == Path("/tmp/runs")


def test_nowhere_to_put_it_is_an_error_rather_than_a_fallback():
    """With no HOME, no cache home and no override, this stops.

    Falling back to the temporary directory would be the tidy-looking choice
    and is the one thing that must not happen: it is where the original defect
    came from, and it would come back silently.
    """
    with pytest.raises(CodexRunRootError) as raised:
        resolve_run_root_base(environment())
    assert "temporary directory is not a fallback" in str(raised.value)


# ── What a real task directory ends up looking like ─────────────────────────


def test_a_real_task_workspace_is_made_outside_the_temporary_directory():
    """The layout the runner builds, checked against the rule above.

    Separate from the tests of the policy function because a correct policy that
    nothing calls is worth nothing, and this is the call that matters.
    """
    from core.codex_runner import CodexWorkspace

    workspace = CodexWorkspace.create(task_id="task-run-root")
    try:
        temporary = system_temporary_directory()
        assert not path_is_within(workspace.root, temporary)
        assert not path_is_within(workspace.codex_home, temporary)
        assert workspace.root.parent.resolve() == resolve_run_root_base().resolve()
        # Still one directory per task, and still private to this user.
        assert workspace.codex_home.is_dir()
        assert oct(workspace.root.stat().st_mode & 0o777) == oct(0o700)
    finally:
        workspace.cleanup()
    assert not workspace.root.exists()


def test_two_tasks_still_get_two_directories_after_the_move():
    from core.codex_runner import CodexWorkspace

    first = CodexWorkspace.create(task_id="task-run-root-a")
    second = CodexWorkspace.create(task_id="task-run-root-b")
    try:
        assert first.root != second.root
        assert not path_is_within(first.root, second.root)
        assert not path_is_within(second.root, first.root)
    finally:
        first.cleanup()
        second.cleanup()


def test_the_real_environment_yields_a_usable_run_root():
    """On the machine running this suite, the answer is one we can write in.

    A policy that is correct in the abstract and unsatisfiable here would turn
    every Codex run into a refusal, so this is checked against the actual
    environment rather than a constructed one — the one place in this file
    where ``os.environ`` is the input.
    """
    try:
        base = resolve_run_root_base()
    except CodexRunRootError as exc:  # pragma: no cover - depends on the host
        pytest.fail(
            "this machine has nowhere to put a Codex task directory, so no "
            f"Codex run could start on it: {exc}"
        )
    assert base.is_absolute()
    assert not path_is_within(base, system_temporary_directory())
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    probe = Path(tempfile.mkdtemp(prefix="gdpval-codex-writable-", dir=base))
    try:
        assert os.access(probe, os.W_OK)
    finally:
        probe.rmdir()
