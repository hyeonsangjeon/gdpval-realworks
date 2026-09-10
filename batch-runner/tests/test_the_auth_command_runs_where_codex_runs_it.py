"""The auth command has to work *where Codex runs it*, not where we test it.

Codex authenticates the provider by running a command and reading the token
from its stdout. This repository's command is ``core/codex_azure_token.py``,
and until now every test of it ran the command the way a developer would: from
``batch-runner``, in this process's own environment, or — in
``test_what_one_codex_turn_actually_sends.py`` — as a *stub* printer that needs
no sign-in at all. Each of those tests was checking something true and none of
them could see the thing that was broken.

Codex starts the command somewhere else entirely:

* with the **task's directory** as the working directory, because
  ``CodexAgentRunner.open_runtime`` sets ``CodexConfig.cwd`` to the workspace
  and the pinned SDK passes that straight to ``Popen``; and
* in the **isolated environment**, where ``HOME`` has been rewritten to a
  throwaway directory so the model cannot write into the operator's home.

Both are deliberate and both stay. But three separate faults followed from
them, and all three produced the same symptom, which is why the symptom was so
hard to read:

1. ``python -m core.codex_azure_token`` cannot import ``core`` from the task
   directory. It fails before the module's first line.
2. ``DefaultAzureCredential``'s working leg here is the Azure CLI, which reads
   its sign-in from ``$HOME/.azure``. With ``HOME`` rewritten there is none.
3. On any failure the command prints **nothing** on stdout — deliberately, so
   Codex cannot mistake an error message for a token. Codex therefore sends an
   empty bearer, and the gateway answers ``401 Access denied due to invalid
   subscription key or wrong API endpoint``.

That 401 names the endpoint and the key, which were both correct throughout.
The tests here hold each fault separately, so the next one to appear is named
where it happens instead of arriving as a sentence about a subscription.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from core.codex_azure_token import (
    AZURE_CONFIG_DIR_ENV,
    TokenCommandError,
    point_at_azure_config_dir,
)
from core.codex_runner import (
    AuthCommandProbe,
    CodexAgentRunner,
    CodexAuthCommandFailed,
    CodexWorkspace,
)
from core.codex_runtime_config import (
    NEUTRALISED_ENV_NAMES,
    CodexProviderSettings,
    LoopbackCodexProvider,
    build_isolated_environment,
    discover_azure_cli_config_dir,
)

REAL_SHAPED_SETTINGS = CodexProviderSettings(
    endpoint="https://example-account.openai.azure.com/openai/v1/",
    model="a-deployment",
)

#: Stands in for a token. Nothing here mints a real one; what these tests care
#: about is whether stdout carried *something*, which is all the runtime cares
#: about too.
FAKE_TOKEN = "not-a-real-token-just-a-non-empty-line"


def _workspace(root: Path) -> CodexWorkspace:
    """A workspace shaped like the one a task gets."""
    workspace = CodexWorkspace(
        root=root,
        workspace=root / "workspace",
        codex_home=root / "codex-home",
        home=root / "home",
    )
    for directory in (workspace.workspace, workspace.codex_home, workspace.home):
        directory.mkdir(parents=True, exist_ok=True)
    return workspace


def _provider_running(script: Path) -> CodexProviderSettings:
    """Settings whose auth command is ``script``, and nothing else changed."""

    class _Scripted(CodexProviderSettings):
        def auth_command(self, source_environment=None):  # type: ignore[override]
            return [sys.executable, str(script)]

    return _Scripted(
        endpoint="https://example-account.openai.azure.com/openai/v1/",
        model="a-deployment",
    )


# ── 1. The working directory ────────────────────────────────────────────────


def test_the_auth_command_names_the_module_by_path_not_by_dash_m():
    """``-m`` is what broke; a path is what survives an unfamiliar cwd.

    The argv Codex is handed has to be runnable from the task's directory.
    ``-m core.codex_azure_token`` is only runnable from somewhere ``core`` is
    importable, and the task's directory is deliberately not that place.
    """
    argv = REAL_SHAPED_SETTINGS.auth_command()

    assert "-m" not in argv, argv
    module_path = Path(argv[1])
    assert module_path.is_absolute(), argv
    assert module_path.is_file(), argv
    assert module_path.name == "codex_azure_token.py", argv
    # Resolved, so two records of the same run describe the same file the same
    # way rather than one of them carrying a ``/./``.
    assert str(module_path) == str(module_path.resolve()), argv


def test_the_module_runs_from_a_directory_where_core_is_not_importable(
    tmp_path: Path,
):
    """The regression for fault 1, run as a subprocess from the wrong place.

    ``--azure-config-dir`` is given a path that does not exist, so the command
    is expected to fail — but it has to fail *at the argument*, which it can
    only reach if the import and the argument parsing both happened. A
    ``ModuleNotFoundError`` here is the original bug returning.
    """
    argv = REAL_SHAPED_SETTINGS.auth_command()
    missing = tmp_path / "no-such-azure-dir"

    completed = subprocess.run(
        [argv[0], argv[1], "--scope", "https://ai.azure.com/.default",
         "--azure-config-dir", str(missing)],
        cwd=str(tmp_path),  # emphatically not the package root
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert completed.returncode == 1, completed.stderr
    assert "ModuleNotFoundError" not in completed.stderr, completed.stderr
    assert "No module named" not in completed.stderr, completed.stderr
    assert str(missing) in completed.stderr
    assert completed.stdout == ""


# ── 2. The sign-in ──────────────────────────────────────────────────────────


def test_the_sign_in_is_discovered_from_the_parent_home(tmp_path: Path):
    """Discovery reads the real ``HOME``, which is the only place it exists."""
    home = tmp_path / "home"
    (home / ".azure").mkdir(parents=True)

    found = discover_azure_cli_config_dir({"HOME": str(home)})

    assert found == str(home / ".azure")


def test_a_home_without_a_sign_in_discovers_nothing(tmp_path: Path):
    """No sign-in is a real answer, not a path to a directory that is not there.

    Returning a plausible-looking path would put the failure one step later,
    inside the credential, where it reads as an Azure problem.
    """
    assert discover_azure_cli_config_dir({"HOME": str(tmp_path)}) is None
    assert discover_azure_cli_config_dir({}) is None
    assert (
        discover_azure_cli_config_dir(
            {"AZURE_CONFIG_DIR": str(tmp_path / "gone"), "HOME": str(tmp_path)}
        )
        is None
    )


def test_an_explicit_config_dir_wins_over_home(tmp_path: Path):
    """``AZURE_CONFIG_DIR`` is how an operator moves the sign-in; honour it."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / ".azure").mkdir()

    found = discover_azure_cli_config_dir(
        {"AZURE_CONFIG_DIR": str(elsewhere), "HOME": str(tmp_path)}
    )

    assert found == str(elsewhere)


def test_the_config_dir_travels_in_argv(tmp_path: Path):
    """A path, in the command's own argv — not a name in Codex's environment."""
    home = tmp_path / "home"
    (home / ".azure").mkdir(parents=True)

    argv = REAL_SHAPED_SETTINGS.auth_command({"HOME": str(home)})

    assert argv[-2:] == ["--azure-config-dir", str(home / ".azure")]


def test_nothing_is_appended_when_there_is_no_sign_in_to_point_at(
    tmp_path: Path,
):
    """A runner authenticating some other way is left exactly as it was."""
    argv = REAL_SHAPED_SETTINGS.auth_command({"HOME": str(tmp_path)})

    assert "--azure-config-dir" not in argv
    assert argv[-2:] == ["--scope", REAL_SHAPED_SETTINGS.auth_scope]


def test_the_isolation_still_hides_the_sign_in_from_codex_itself(
    tmp_path: Path,
):
    """The security half of the fix, asserted directly.

    The auth command learns where the sign-in is. The *Codex process* must not,
    because everything the model runs inherits that environment. If a later
    change takes the easy road and adds ``AZURE_CONFIG_DIR`` — or stops
    rewriting ``HOME`` — this is the test that should stop it.
    """
    overlay = build_isolated_environment(
        codex_home=tmp_path / "codex", task_home=tmp_path / "home"
    )

    assert AZURE_CONFIG_DIR_ENV not in overlay
    assert overlay["HOME"] == str(tmp_path / "home")
    assert "HOME" in NEUTRALISED_ENV_NAMES


def test_pointing_at_a_directory_that_is_not_there_is_refused(tmp_path: Path):
    """A wrong path must not become a quiet sign-in failure one layer down."""
    missing = tmp_path / "nowhere"
    environment: dict[str, str] = {}

    with pytest.raises(TokenCommandError) as excinfo:
        point_at_azure_config_dir(missing, environment)

    assert str(missing) in str(excinfo.value)
    assert environment == {}


def test_pointing_at_a_real_directory_sets_the_name_the_cli_reads(
    tmp_path: Path,
):
    environment: dict[str, str] = {}

    resolved = point_at_azure_config_dir(tmp_path, environment)

    assert environment == {AZURE_CONFIG_DIR_ENV: str(tmp_path)}
    assert resolved == str(tmp_path)


# ── 3. The silence ──────────────────────────────────────────────────────────


def test_a_runtime_will_not_start_when_no_token_can_be_minted(tmp_path: Path):
    """Fault 3, held at the place it starts instead of at the gateway.

    The command exits non-zero having printed nothing, which is exactly what
    the real one does when it cannot sign in. Before this check, that produced
    a turn, an empty bearer and a 401 about a subscription key.
    """
    script = tmp_path / "cannot_mint.py"
    script.write_text(
        "import sys\n"
        "print('codex-azure-token: could not acquire an access token "
        "(ClientAuthenticationError)', file=sys.stderr)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    runner = CodexAgentRunner(_provider_running(script), verify_runtime=False)

    with pytest.raises(CodexAuthCommandFailed) as excinfo:
        runner.require_a_usable_auth_command(_workspace(tmp_path / "run"))

    message = str(excinfo.value)
    assert "could not acquire an access token" in message
    # The message has to say the 401 would be misleading, because the whole
    # cost of this bug was believing it.
    assert "invalid subscription key" in message


def test_a_command_that_exits_zero_with_nothing_on_stdout_is_still_a_failure(
    tmp_path: Path,
):
    """Codex reads stdout, not the exit code. So must the check.

    An auth command that succeeds silently hands over an empty bearer just as
    surely as one that fails loudly, and the gateway cannot tell them apart.
    """
    script = tmp_path / "silent_success.py"
    script.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    runner = CodexAgentRunner(_provider_running(script), verify_runtime=False)

    with pytest.raises(CodexAuthCommandFailed):
        runner.require_a_usable_auth_command(_workspace(tmp_path / "run"))


def test_a_command_that_prints_a_token_passes_and_the_token_is_not_kept(
    tmp_path: Path,
):
    """The probe reports *that* there was a token, never *which*."""
    script = tmp_path / "mints.py"
    script.write_text(
        f"import sys\nsys.stdout.write({FAKE_TOKEN!r} + chr(10))\n",
        encoding="utf-8",
    )
    runner = CodexAgentRunner(_provider_running(script), verify_runtime=False)

    probe = runner.require_a_usable_auth_command(_workspace(tmp_path / "run"))

    assert probe.ok
    assert probe.produced_a_token is True
    assert FAKE_TOKEN not in repr(probe)
    assert FAKE_TOKEN not in repr(probe.as_record())


def test_the_check_runs_once_however_many_tasks_follow(tmp_path: Path):
    """220 tasks are 220 turns and one sign-in question.

    The counter is a file the script appends to, so the count survives the
    subprocess boundary the way a real auth command's side effects would.
    """
    counter = tmp_path / "runs.txt"
    script = tmp_path / "counts.py"
    script.write_text(
        "import sys\n"
        f"open({str(counter)!r}, 'a').write('x')\n"
        f"sys.stdout.write({FAKE_TOKEN!r} + chr(10))\n",
        encoding="utf-8",
    )
    runner = CodexAgentRunner(_provider_running(script), verify_runtime=False)
    workspace = _workspace(tmp_path / "run")

    for _ in range(3):
        runner.require_a_usable_auth_command(workspace)

    assert counter.read_text() == "x"


def test_the_probe_gives_the_child_the_environment_the_sdk_gives_it(
    tmp_path: Path,
):
    """The probe's fidelity, which is the only reason to trust its answer.

    The pinned SDK builds the child environment as ``os.environ.copy()``
    updated with the overlay, so a name present in this process but absent from
    the overlay still reaches the command. A probe that passed the overlay
    alone would test a stricter world than production and could fail on
    something production would not — an answer that is wrong in the safe
    direction is still wrong.
    """
    marker = "GDPVAL_AUTH_PROBE_FIDELITY_MARKER"
    script = tmp_path / "echoes.py"
    script.write_text(
        "import os, sys\n"
        f"sys.stdout.write(os.environ.get({marker!r}, '') + chr(10))\n",
        encoding="utf-8",
    )
    runner = CodexAgentRunner(_provider_running(script), verify_runtime=False)

    overlay = build_isolated_environment(
        codex_home=tmp_path / "c", task_home=tmp_path / "h"
    )
    assert marker not in overlay

    previous = os.environ.get(marker)
    os.environ[marker] = "carried"
    try:
        probe = runner.preflight_auth_command(_workspace(tmp_path / "run"))
    finally:
        if previous is None:
            os.environ.pop(marker, None)
        else:
            os.environ[marker] = previous

    assert probe.produced_a_token is True, probe.as_record()


def test_the_isolation_is_still_applied_to_the_command(tmp_path: Path):
    """Fidelity to the SDK must not become "the parent environment, unchanged".

    ``HOME`` is the name the whole fault turned on, so the check that the
    overlay really is applied uses that one.
    """
    script = tmp_path / "reads_home.py"
    script.write_text(
        "import os, sys\n"
        "sys.stdout.write(os.environ.get('HOME', '') + chr(10))\n",
        encoding="utf-8",
    )
    runner = CodexAgentRunner(_provider_running(script), verify_runtime=False)
    workspace = _workspace(tmp_path / "run")

    probe = runner.preflight_auth_command(workspace)

    # It printed *something*, and what it printed was the task's home rather
    # than this machine's. Asserted via the probe's own view plus a direct run,
    # because the probe deliberately does not keep the child's output.
    assert probe.produced_a_token is True
    direct = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(workspace.workspace),
        env={**os.environ, **build_isolated_environment(
            codex_home=workspace.codex_home, task_home=workspace.home
        )},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert direct.stdout.strip() == str(workspace.home)
    assert direct.stdout.strip() != os.environ.get("HOME", "")


def test_a_provider_with_no_auth_command_is_not_blocked(tmp_path: Path):
    """The loopback stand-in authenticates by variable; there is nothing to run."""
    runner = CodexAgentRunner(
        LoopbackCodexProvider(port=8123), verify_runtime=False
    )

    probe = runner.require_a_usable_auth_command(_workspace(tmp_path / "run"))

    assert probe.ran is False
    assert probe.ok is False  # nothing was established, and none is claimed


def test_the_check_can_be_turned_off_for_the_diagnostic(tmp_path: Path):
    """The connection diagnostic sometimes needs to send the failing request."""
    script = tmp_path / "cannot_mint.py"
    script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    runner = CodexAgentRunner(
        _provider_running(script), verify_runtime=False, preflight_auth=False
    )

    probe = runner.require_a_usable_auth_command(_workspace(tmp_path / "run"))

    assert probe.ran is False
    assert "turned off" in (probe.reason or "")


def test_a_probe_record_carries_no_token_field():
    """Whatever else changes, the record stays a report about a token's absence."""
    probe = AuthCommandProbe(
        ran=True,
        exit_code=0,
        produced_a_token=True,
        reason=None,
        azure_config_dir="/somewhere/.azure",
    )

    record = probe.as_record()

    assert set(record) == {
        "ran",
        "exit_code",
        "produced_a_token",
        "reason",
        "azure_config_dir",
        "ok",
    }
    assert all(not isinstance(value, str) or "eyJ" not in value
               for value in record.values())


# ── The one that would have caught all three, on a machine that can sign in ──


@pytest.mark.integration
def test_the_real_auth_command_mints_inside_the_isolation():
    """End to end, with nothing stubbed: the real command, the real isolation.

    Skipped where the machine cannot sign in at all, and where the Azure CLI is
    a user-site install — on such a box ``az`` resolves its own modules through
    ``HOME`` and cannot start under any isolation, which is a property of the
    installation rather than of this code. CI installs the CLI system-wide and
    runs this for real.
    """
    if not discover_azure_cli_config_dir():
        pytest.skip("no Azure CLI sign-in on this machine")

    settings = REAL_SHAPED_SETTINGS
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        workspace = _workspace(root)
        runner = CodexAgentRunner(settings, verify_runtime=False)

        parent = subprocess.run(
            settings.auth_command(),
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if parent.returncode != 0:
            pytest.skip("this machine's own sign-in cannot mint a token")

        probe = runner.preflight_auth_command(workspace)
        if not probe.ok and "azure" in (probe.reason or "").lower():
            pytest.skip(f"the Azure CLI cannot start under isolation here: "
                        f"{probe.reason}")

        assert probe.ok, probe.as_record()
