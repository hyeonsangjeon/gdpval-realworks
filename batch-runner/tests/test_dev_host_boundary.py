"""The line under the development host, tested as a refusal.

The Xenology card allows an Azure VM for development and test and then says the
pre-registered GDPVal execution arms are not to be quietly re-pointed at it. The
card offers a choice: "a test or a documented contract". A document is read
once. This is the contract as behaviour, so the substitution has to be argued
with rather than merely not thought about.

The three cases that matter are all failure cases, and they fail differently:

  * a development host refuses, and says how registration would work;
  * a *partly* registered host refuses too, and names which pins are missing --
    four of six is not a registration, and a boundary that accepted it would be
    worse than none, because the run would then carry an arm name it had not
    earned;
  * a marker file that exists and cannot be read refuses. Unknown is answered
    the way "development" is answered. Treating an unreadable file as an absent
    one is how a check quietly stops checking.

And one success case, because a refusal that cannot be satisfied is a wall
rather than a boundary: a machine registered as its own arm, on the kernel it
was pinned to, runs.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dev_host_boundary as boundary  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = REPO_ROOT / "infra" / "dev-host" / "bootstrap.sh"

DEV_MARKER = """\
# This machine is the gdpval-realworks development and test host.
role=development
benchmark_execution_environment=no
defined_by=infra/dev-host/main.bicep
"""

FULL_REGISTRATION = """\
role=benchmark
benchmark_execution_environment=yes
benchmark_arm=azure-vm-krc
benchmark_arm_kernel={kernel}
benchmark_arm_image=Canonical:ubuntu-24_04-lts:server:24.04.202508010
benchmark_arm_vm_size=Standard_D8as_v5
benchmark_arm_region=koreacentral
benchmark_arm_task_manifest_sha256=8d969eef6ecad3c29a3a629280e686cf
"""


def _marker(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "gdpval-dev-host"
    path.write_text(text, encoding="utf-8")
    return path


# ── The machine that never heard of any of this ────────────────────────────


def test_a_machine_with_no_marker_is_not_this_modules_business(tmp_path):
    """Every machine in CI, and the one this test is running on.

    The boundary applies to hosts that *declared* themselves development hosts.
    It does not try to recognise one from the shape of the hardware, because a
    guess that refuses a legitimate run is the failure that gets the check
    deleted.
    """
    absent = tmp_path / "not-here"
    assert boundary.check_benchmark_allowed(marker_path=absent) is None
    assert boundary.read_marker(absent) is None


def test_the_default_path_is_the_one_bootstrap_writes():
    assert boundary.DEFAULT_MARKER_PATH == "/etc/gdpval-dev-host"


def test_the_environment_can_point_it_somewhere_else(tmp_path):
    path = _marker(tmp_path, DEV_MARKER)
    with pytest.raises(boundary.DevHostBoundaryError):
        boundary.check_benchmark_allowed(
            environ={boundary.MARKER_ENV: str(path)}
        )


def test_an_explicit_path_beats_the_environment(tmp_path):
    elsewhere = _marker(tmp_path, DEV_MARKER)
    absent = tmp_path / "not-here"
    assert boundary.check_benchmark_allowed(
        marker_path=absent, environ={boundary.MARKER_ENV: str(elsewhere)}
    ) is None


# ── The development host refuses ───────────────────────────────────────────


def test_a_development_host_refuses_a_benchmark_run(tmp_path):
    path = _marker(tmp_path, DEV_MARKER)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    message = str(excinfo.value)
    assert "refusing" in message
    assert str(path) in message
    assert "development host" in message


def test_the_refusal_says_how_registration_would_work(tmp_path):
    """A refusal with no way out of it gets worked around instead of answered."""
    path = _marker(tmp_path, DEV_MARKER)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    message = str(excinfo.value)
    for pin in boundary.REQUIRED_ARM_PINS:
        assert pin in message, f"the refusal never mentions {pin}"
    assert "MISSING" in message


def test_the_refusal_names_the_run_it_is_refusing(tmp_path):
    path = _marker(tmp_path, DEV_MARKER)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(
            marker_path=path, what="benchmark inference run (codex_foundry)"
        )
    assert "codex_foundry" in str(excinfo.value)


def test_deleting_the_marker_is_not_offered_as_the_answer(tmp_path):
    path = _marker(tmp_path, DEV_MARKER)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    assert "Deleting the marker file is not it" in str(excinfo.value)


@pytest.mark.parametrize("value", ["no", "No", "NO", "false", "", "maybe", "0"])
def test_only_yes_means_yes(tmp_path, value):
    """Anything that is not the word is a refusal. A marker that says `0` or
    `false` was written by somebody who did not read this, and guessing at their
    intent is how a benchmark ends up on the wrong machine."""
    path = _marker(tmp_path, f"role=development\nbenchmark_execution_environment={value}\n")
    with pytest.raises(boundary.DevHostBoundaryError):
        boundary.check_benchmark_allowed(marker_path=path)


def test_a_marker_that_says_nothing_about_it_refuses(tmp_path):
    """No key at all is not consent."""
    path = _marker(tmp_path, "role=something\n")
    with pytest.raises(boundary.DevHostBoundaryError):
        boundary.check_benchmark_allowed(marker_path=path)


# ── Half a registration is not a registration ──────────────────────────────


@pytest.mark.parametrize("dropped", boundary.REQUIRED_ARM_PINS)
def test_a_missing_pin_is_refused_and_named(tmp_path, dropped):
    text = FULL_REGISTRATION.format(kernel=platform.release())
    kept = "\n".join(
        line for line in text.splitlines() if not line.startswith(f"{dropped}=")
    ) + "\n"
    path = _marker(tmp_path, kept)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    message = str(excinfo.value)
    assert "incomplete" in message
    assert dropped in message


def test_a_pin_set_to_nothing_counts_as_missing(tmp_path):
    """`benchmark_arm_region=` is a key with no answer, which is the same
    situation as no key, dressed as an answer."""
    text = FULL_REGISTRATION.format(kernel=platform.release()).replace(
        "benchmark_arm_region=koreacentral", "benchmark_arm_region="
    )
    path = _marker(tmp_path, text)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    assert "benchmark_arm_region" in str(excinfo.value)


def test_the_partial_refusal_says_why_the_pins_are_there(tmp_path):
    text = FULL_REGISTRATION.format(kernel=platform.release()).replace(
        "benchmark_arm_vm_size=Standard_D8as_v5\n", ""
    )
    path = _marker(tmp_path, text)
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    assert "comparable" in str(excinfo.value)


# ── A registered arm runs, on the kernel it was registered on ──────────────


def test_a_fully_registered_arm_is_allowed(tmp_path):
    path = _marker(tmp_path, FULL_REGISTRATION.format(kernel="6.8.0-1064-azure"))
    marker = boundary.check_benchmark_allowed(
        marker_path=path, kernel="6.8.0-1064-azure"
    )
    assert marker is not None
    assert marker.values["benchmark_arm"] == "azure-vm-krc"
    assert marker.missing_pins == ()


def test_a_different_kernel_than_the_one_pinned_is_refused(tmp_path):
    """The pin is the point. An arm registered on one kernel and run on another
    is two arms wearing one name, and the comparison it feeds says the only
    thing that changed was the run place."""
    path = _marker(tmp_path, FULL_REGISTRATION.format(kernel="6.8.0-1064-azure"))
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path, kernel="6.11.0-1018-azure")
    message = str(excinfo.value)
    assert "6.8.0-1064-azure" in message
    assert "6.11.0-1018-azure" in message


def test_the_running_kernel_is_used_when_none_is_given(tmp_path):
    path = _marker(tmp_path, FULL_REGISTRATION.format(kernel=platform.release()))
    assert boundary.check_benchmark_allowed(marker_path=path) is not None


# ── Unreadable is not absent ───────────────────────────────────────────────


def test_a_marker_that_cannot_be_read_refuses(tmp_path):
    """The failure this repository keeps writing tests against: a check that
    treats an unreadable input as a clean one. A directory where the file should
    be is not "no marker"; it is a machine whose role nobody can establish."""
    path = tmp_path / "gdpval-dev-host"
    path.mkdir()
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        boundary.check_benchmark_allowed(marker_path=path)
    assert "could not be read" in str(excinfo.value)


def test_read_marker_also_refuses_rather_than_returning_none(tmp_path):
    path = tmp_path / "gdpval-dev-host"
    path.mkdir()
    with pytest.raises(boundary.DevHostBoundaryError):
        boundary.read_marker(path)


def test_unparseable_lines_are_skipped_not_guessed_at(tmp_path):
    path = _marker(
        tmp_path,
        "# a comment\n\n  \nnot a key value line\nrole=development\n"
        "benchmark_execution_environment=no\n",
    )
    marker = boundary.read_marker(path)
    assert marker is not None
    assert marker.role == "development"
    assert "not a key value line" not in marker.values


def test_a_value_containing_an_equals_sign_survives(tmp_path):
    path = _marker(tmp_path, "role=development\nbenchmark_arm_image=a:b:c=d\n")
    marker = boundary.read_marker(path)
    assert marker.values["benchmark_arm_image"] == "a:b:c=d"


# ── What a run writes down about the machine it believes it is on ──────────


def test_describe_says_nothing_confident_about_an_unmarked_machine():
    assert "no development-host marker" in boundary.describe(None)


def test_describe_names_the_arm_when_there_is_one(tmp_path):
    path = _marker(tmp_path, FULL_REGISTRATION.format(kernel="6.8.0-1064-azure"))
    line = boundary.describe(boundary.read_marker(path))
    assert "azure-vm-krc" in line
    assert "Standard_D8as_v5" in line
    assert "koreacentral" in line


def test_describe_does_not_call_a_development_host_an_arm(tmp_path):
    path = _marker(tmp_path, DEV_MARKER)
    line = boundary.describe(boundary.read_marker(path))
    assert "not a registered benchmark execution environment" in line


def test_the_summary_carries_the_pins_for_the_run_record(tmp_path):
    path = _marker(tmp_path, FULL_REGISTRATION.format(kernel="6.8.0-1064-azure"))
    summary = boundary.marker_summary(boundary.read_marker(path))
    assert summary["benchmark_arm"] == "azure-vm-krc"
    assert set(summary["benchmark_arm_pins"]) == set(boundary.REQUIRED_ARM_PINS)
    assert summary["benchmark_arm_pins"]["benchmark_arm_region"] == "koreacentral"


def test_the_summary_of_an_unmarked_machine_says_none_not_zero(tmp_path):
    summary = boundary.marker_summary(None)
    assert summary["dev_host_marker"] is None
    assert summary["benchmark_arm"] is None


def test_an_unregistered_marker_summarises_without_inventing_an_arm(tmp_path):
    path = _marker(tmp_path, DEV_MARKER)
    summary = boundary.marker_summary(boundary.read_marker(path))
    assert summary["dev_host_role"] == "development"
    assert summary["benchmark_arm"] is None


# ── The file the bootstrap actually writes ─────────────────────────────────


def _marker_heredoc() -> str:
    text = BOOTSTRAP.read_text(encoding="utf-8")
    start = text.index("<<'MARKERDOC'") + len("<<'MARKERDOC'\n")
    return text[start : text.index("\nMARKERDOC")]


def test_the_marker_bootstrap_writes_is_refused_by_this_module(tmp_path):
    """Not a paraphrase of it -- the bytes out of infra/dev-host/bootstrap.sh.

    The two halves of this contract are in different languages and different
    directories, and the way they come apart is somebody editing one of them.
    """
    path = _marker(tmp_path, _marker_heredoc() + "\n")
    with pytest.raises(boundary.DevHostBoundaryError):
        boundary.check_benchmark_allowed(marker_path=path)


def test_the_marker_bootstrap_writes_parses_to_what_it_says(tmp_path):
    marker = boundary.read_marker(_marker(tmp_path, _marker_heredoc() + "\n"))
    assert marker.role == "development"
    assert marker.values["benchmark_execution_environment"] == boundary.REFUSED
    assert marker.values["defined_by"] == "infra/dev-host/main.bicep"


def test_the_marker_explains_every_pin_this_module_requires():
    """The marker's own comment block tells a reader how to register the arm.

    If a pin is added here and not there, the instructions on the machine are
    wrong -- and they are the only instructions the person standing in front of
    the refusal has.
    """
    heredoc = _marker_heredoc()
    for pin in boundary.REQUIRED_ARM_PINS:
        assert pin in heredoc, f"the marker file never mentions {pin}"
    assert "benchmark_execution_environment=yes" in heredoc


# ── Wired into the run, not merely available to it ─────────────────────────


def test_step2_refuses_to_start_on_a_development_host(tmp_path, monkeypatch, capsys):
    """A boundary nothing calls is a document with a test suite."""
    import step2_run_inference as step2

    path = _marker(tmp_path, DEV_MARKER)
    monkeypatch.setenv(boundary.MARKER_ENV, str(path))
    with pytest.raises(boundary.DevHostBoundaryError):
        step2._require_host_may_carry_a_benchmark_run("subprocess")


def test_step2_says_which_mode_it_was_refusing(tmp_path, monkeypatch):
    import step2_run_inference as step2

    path = _marker(tmp_path, DEV_MARKER)
    monkeypatch.setenv(boundary.MARKER_ENV, str(path))
    with pytest.raises(boundary.DevHostBoundaryError) as excinfo:
        step2._require_host_may_carry_a_benchmark_run("codex_foundry")
    assert "codex_foundry" in str(excinfo.value)


def test_step2_is_unaffected_on_a_machine_with_no_marker(tmp_path, monkeypatch):
    import step2_run_inference as step2

    monkeypatch.setenv(boundary.MARKER_ENV, str(tmp_path / "not-here"))
    assert step2._require_host_may_carry_a_benchmark_run("subprocess") is None


def test_step2_announces_a_registered_arm(tmp_path, monkeypatch, capsys):
    import step2_run_inference as step2

    path = _marker(tmp_path, FULL_REGISTRATION.format(kernel=platform.release()))
    monkeypatch.setenv(boundary.MARKER_ENV, str(path))
    assert step2._require_host_may_carry_a_benchmark_run("subprocess") is not None
    assert "azure-vm-krc" in capsys.readouterr().out


def test_the_boundary_is_not_in_core_where_it_would_move_the_grader_hash():
    """Placement, as a test rather than as a comment.

    ``step8_grade.compute_grader_source_hash`` hashes every ``core/**/*.py``.
    Moving this file there would change the grader's source fingerprint, which
    invalidates the smoke run a paid grading run is gated on -- for a module
    grading never calls.
    """
    assert (REPO_ROOT / "batch-runner" / "dev_host_boundary.py").is_file()
    assert not (REPO_ROOT / "batch-runner" / "core" / "dev_host_boundary.py").exists()
