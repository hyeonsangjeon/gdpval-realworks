"""A skipped check and a ready host must never look the same.

Two assertions in `test_codex_runtime_end_to_end.py` need the agent to actually
execute a command, and they skip wherever the sandbox will not start. That skip
is correct, and it is also the most dangerous line in this repository's Codex
work, because a suite that is all green with those two skipped reads exactly
like a suite that proved the thing. It is what let "the chain is verified end to
end" get written down while the execution leg had never run anywhere.

`scripts/diagnose_codex_sandbox_host.py` exists to make that difference
audible, and this file is what holds it to it. Three properties, in order of
how much they matter:

**Readiness has exactly one cause.** :func:`test_only_a_command_that_actually_ran_is_ready`
walks every wall and requires `ready` to come back only from a host where bwrap
ran a command to completion. No sysctl reading, no absent restriction, no
"nothing looked wrong" produces a pass.

**Every wall is distinguishable.** The NAS and the GitHub runner both print a
`bwrap:` line and are not the same problem: one has no `CONFIG_USER_NS` and
never will, the other is handed a namespace and then refused the capabilities
inside it. Both are pinned here against their real recorded output, so a future
simplification that collapses them into "no sandbox here" fails.

**The deprecated backend is not a way out.** :func:`test_landlock_is_an_observation_never_a_verdict`
requires a host with Landlock available and bubblewrap broken to still come
back not-ready. Switching to `use_legacy_landlock` would turn those two skips
green while measuring a sandbox no real run uses -- the same trade as disabling
the sandbox, just better disguised.

Everything runs off fabricated probes, so a Synology 3.10 kernel, an Ubuntu
24.04 runner and an Azure VM are all exercised wherever this suite happens to
be. The single test that reads the real machine only asserts self-consistency,
because the host underneath is not the subject.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_recorded_sandbox_verdicts as checker  # noqa: E402
import diagnose_codex_sandbox_host as host  # noqa: E402

BATCH_RUNNER = Path(__file__).resolve().parent.parent
REPO_ROOT = BATCH_RUNNER.parent

SCRIPT = BATCH_RUNNER / "scripts" / "diagnose_codex_sandbox_host.py"
RECORD = BATCH_RUNNER / "docs" / "codex_sandbox_hosts.json"
SURVEY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "codex-sandbox-host-survey.yml"

# --- real failure text, copied from the machines that produced it -----------

#: Synology DSM, Linux 3.10.102. There is no `/proc/sys/user/` on this kernel
#: at all -- user namespaces became a sysctl in 4.9.
NAS_BWRAP_STDERR = (
    "bwrap: Creating new namespace failed, likely because the kernel does not "
    "support user namespaces.  bwrap must be installed setuid on such systems."
)

#: GitHub-hosted `ubuntu-latest`, from the pytest run on PR #454. The namespace
#: is created; configuring the loopback interface inside it is then refused.
GITHUB_RUNNER_BWRAP_STDERR = (
    "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted"
)


def probes(
    *,
    max_user_namespaces: str | None,
    unprivileged_userns_clone: str | None = None,
    apparmor_restrict: str | None = None,
    unshare_ok: bool | None,
    bwrap_full_ok: bool | None = None,
    bwrap_full_stderr: str = "",
    bwrap_no_net_ok: bool | None = None,
    landlock_ok: bool | None = None,
) -> dict[str, host.Probe]:
    """Build one host's measurements. ``None`` means the probe did not run."""
    built = {
        "max_user_namespaces": host.Probe(
            name="user.max_user_namespaces",
            ran=True,
            ok=max_user_namespaces is not None
            and max_user_namespaces.isdigit()
            and int(max_user_namespaces) > 0,
            value=max_user_namespaces,
        ),
        "unprivileged_userns_clone": host.Probe(
            name="kernel.unprivileged_userns_clone",
            ran=unprivileged_userns_clone is not None,
            ok=None
            if unprivileged_userns_clone is None
            else unprivileged_userns_clone == "1",
            value=unprivileged_userns_clone,
        ),
        "apparmor_restrict_unprivileged_userns": host.Probe(
            name="kernel.apparmor_restrict_unprivileged_userns",
            ran=apparmor_restrict is not None,
            ok=None if apparmor_restrict is None else apparmor_restrict == "0",
            value=apparmor_restrict,
        ),
        "unshare": host.Probe(
            name="unshare",
            ran=unshare_ok is not None,
            ok=unshare_ok,
        ),
        "landlock": host.Probe(
            name="landlock",
            ran=landlock_ok is not None,
            ok=landlock_ok,
        ),
    }
    if bwrap_full_ok is not None:
        built["bwrap_full"] = host.Probe(
            name="bwrap full",
            ran=True,
            ok=bwrap_full_ok,
            detail=bwrap_full_stderr,
        )
    if bwrap_no_net_ok is not None:
        built["bwrap_no_net"] = host.Probe(
            name="bwrap no netns",
            ran=True,
            ok=bwrap_no_net_ok,
        )
    return built


# ---------------------------------------------------------------------------
# The hosts, as they really behave
# ---------------------------------------------------------------------------


def synology_nas() -> dict[str, host.Probe]:
    """Linux 3.10.102: the kernel has no user namespaces to give."""
    return probes(
        max_user_namespaces=None,
        unshare_ok=False,
        bwrap_full_ok=False,
        bwrap_full_stderr=NAS_BWRAP_STDERR,
        bwrap_no_net_ok=False,
    )


def github_hosted_runner() -> dict[str, host.Probe]:
    """`ubuntu-latest`: namespace granted, capability inside it refused.

    `apparmor_restrict_unprivileged_userns=1` is Ubuntu 24.04's default and is
    the documented cause; the namespace itself is still created, which is why
    the unshare probe passes and bwrap does not.
    """
    return probes(
        max_user_namespaces="15000",
        apparmor_restrict="1",
        unshare_ok=True,
        bwrap_full_ok=False,
        bwrap_full_stderr=GITHUB_RUNNER_BWRAP_STDERR,
        bwrap_no_net_ok=True,
        landlock_ok=True,
    )


def working_host() -> dict[str, host.Probe]:
    """What the run place has to look like: a command ran, under the netns."""
    return probes(
        max_user_namespaces="15000",
        apparmor_restrict="0",
        unshare_ok=True,
        bwrap_full_ok=True,
        bwrap_no_net_ok=True,
        landlock_ok=True,
    )


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


def test_only_a_command_that_actually_ran_is_ready() -> None:
    """`ready` requires the sandbox to have executed something. Nothing else.

    This is the assertion the whole file is built around. Every other host
    below has some reassuring signal -- namespaces allowed, no restriction
    configured, Landlock present -- and none of them may add up to a pass.
    """
    assert host.classify(working_host(), "/usr/bin/bwrap") == host.READY

    for name, built in (
        ("nas", synology_nas()),
        ("github runner", github_hosted_runner()),
    ):
        verdict = host.classify(built, "/usr/bin/bwrap")
        assert verdict != host.READY, f"{name} must not read as ready"


def test_a_host_that_looks_fine_but_never_ran_a_command_is_not_ready() -> None:
    """Every encouraging reading, no successful execution: still not ready.

    The specific trap: sysctls all permissive, no LSM restriction, unshare
    works -- and bwrap failed anyway for a reason nobody has named yet. That is
    a host to go investigate, not a host to run on.
    """
    verdict = host.classify(
        probes(
            max_user_namespaces="15000",
            apparmor_restrict="0",
            unshare_ok=True,
            bwrap_full_ok=False,
            bwrap_full_stderr="bwrap: setting up uid map: Invalid argument",
            bwrap_no_net_ok=False,
            landlock_ok=True,
        ),
        "/usr/bin/bwrap",
    )
    assert verdict == host.UNCLASSIFIED_SANDBOX_FAILURE
    assert verdict != host.READY


def test_readiness_can_fail_and_says_so_in_the_exit_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not ready is an error, not a shrug.

    A tool whose every outcome is exit 0 cannot gate anything, and a gate that
    cannot fail is the mechanism that let two never-executed assertions sit
    inside a green suite. So: `ready` exits 0, every wall exits 1, and a probe
    that could not run at all exits 2 rather than borrowing either answer.
    """

    def report_for(readiness: str) -> host.HostReport:
        return host.HostReport(
            readiness=readiness,
            explanation=host.WALL_EXPLANATIONS[readiness],
            kernel="6.8.0",
            machine="x86_64",
            in_container=False,
            container_evidence="no container marker found",
            probes=[p.as_dict() for p in working_host().values()],
        )

    for wall in host.ALL_READINESS_VALUES:
        monkeypatch.setattr(host, "collect", lambda w=wall: report_for(w))
        status = host.main([])
        capsys.readouterr()
        assert status == (0 if wall == host.READY else 1), wall

    def explode() -> host.HostReport:
        raise OSError("/proc is not mounted")

    monkeypatch.setattr(host, "collect", explode)
    assert host.main([]) == 2
    capsys.readouterr()


# ---------------------------------------------------------------------------
# The walls are different problems
# ---------------------------------------------------------------------------


def test_the_nas_and_the_github_runner_do_not_share_a_verdict() -> None:
    """Both print `bwrap:`. They are not the same problem and must not merge.

    Treating every `bwrap:` line as one condition is what made "no sandbox
    anywhere" look like a single fact about the world rather than two separate
    ones, only one of which is fixable.
    """
    nas = host.classify(synology_nas(), "/usr/bin/bwrap")
    runner = host.classify(github_hosted_runner(), "/usr/bin/bwrap")

    assert nas == host.KERNEL_LACKS_USER_NAMESPACES
    assert runner == host.USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY
    assert nas != runner


def test_a_kernel_without_the_feature_outranks_every_other_reading() -> None:
    """No `/proc/sys/user/` is the end of the conversation.

    Nothing installable or configurable moves this host, so the report must not
    offer a nearer-looking cause that implies somebody could fix it.
    """
    built = synology_nas()
    built["apparmor_restrict_unprivileged_userns"] = host.Probe(
        name="apparmor", ran=True, ok=False, value="1"
    )
    assert (
        host.classify(built, "/usr/bin/bwrap") == host.KERNEL_LACKS_USER_NAMESPACES
    )


def test_switched_off_is_told_apart_from_never_built() -> None:
    """`max_user_namespaces=0` is one sysctl away from working. Say that."""
    verdict = host.classify(
        probes(max_user_namespaces="0", unshare_ok=False, bwrap_full_ok=False),
        "/usr/bin/bwrap",
    )
    assert verdict == host.USER_NAMESPACES_DISABLED_BY_SYSCTL


def test_the_debian_family_switch_is_read_too() -> None:
    """Debian kernels use a different sysctl for the same decision."""
    verdict = host.classify(
        probes(
            max_user_namespaces="15000",
            unprivileged_userns_clone="0",
            unshare_ok=False,
            bwrap_full_ok=False,
        ),
        "/usr/bin/bwrap",
    )
    assert verdict == host.USER_NAMESPACES_DISABLED_BY_SYSCTL


def test_a_denied_capability_with_no_lsm_to_blame_stays_its_own_wall() -> None:
    """A container's seccomp filter is not AppArmor, and needs another fix.

    Same visible symptom as the runner case -- namespace granted, capability
    refused -- with no LSM knob reading 1. Naming it "restricted by security
    policy" would point whoever reads it at a profile that is not there.
    """
    verdict = host.classify(
        probes(
            max_user_namespaces="15000",
            apparmor_restrict="0",
            unshare_ok=True,
            bwrap_full_ok=False,
            bwrap_full_stderr=GITHUB_RUNNER_BWRAP_STDERR,
            bwrap_no_net_ok=True,
        ),
        "/usr/bin/bwrap",
    )
    assert verdict == host.CAPABILITY_DENIED_INSIDE_NAMESPACE


def test_no_bwrap_at_all_is_reported_before_anything_else() -> None:
    """Nothing downstream is meaningful without the binary."""
    assert host.classify(working_host(), None) == host.SANDBOX_BINARY_MISSING


def test_an_unnamed_failure_is_not_quietly_filed_under_a_named_one() -> None:
    """An unexplained refusal stays unexplained in the report.

    Guessing a cause here would put a sentence in the record that reads like
    evidence and is not.
    """
    verdict = host.classify(
        probes(
            max_user_namespaces="15000",
            apparmor_restrict="0",
            unshare_ok=True,
            bwrap_full_ok=False,
            bwrap_full_stderr="bwrap: Can't mount proc on /newroot/proc",
            bwrap_no_net_ok=False,
        ),
        "/usr/bin/bwrap",
    )
    assert verdict == host.UNCLASSIFIED_SANDBOX_FAILURE


# ---------------------------------------------------------------------------
# The deprecated backend is not a shortcut
# ---------------------------------------------------------------------------


def test_landlock_is_an_observation_never_a_verdict() -> None:
    """Landlock available + bubblewrap broken is still not ready.

    The pinned build calls this backend `use_legacy_landlock` and describes it
    as the legacy behaviour; the default pipeline is bubblewrap. Passing the
    two end-to-end assertions by opting into Landlock would prove a command can
    run under a sandbox that no real run configures.
    """
    built = github_hosted_runner()
    assert built["landlock"].ok is True
    assert host.classify(built, "/usr/bin/bwrap") != host.READY


def test_landlock_absence_does_not_make_a_working_host_unready() -> None:
    """The observation cuts neither way: a working bwrap host is ready."""
    built = working_host()
    built["landlock"] = host.Probe(name="landlock", ran=True, ok=False)
    assert host.classify(built, "/usr/bin/bwrap") == host.READY


# ---------------------------------------------------------------------------
# The report a human or a workflow actually reads
# ---------------------------------------------------------------------------


def test_every_verdict_carries_an_explanation_that_adds_something() -> None:
    """The label names the wall; the sentence has to say what it means.

    An explanation that only spells the identifier back out
    ("kernel lacks user namespaces") leaves the reader exactly where they
    started, so each one is required to be substantially longer than its label.
    """
    for wall in host.ALL_READINESS_VALUES:
        explanation = host.WALL_EXPLANATIONS[wall]
        assert explanation, wall
        assert len(explanation) > 2 * len(wall), f"{wall}: explanation says no more than the label"
        assert explanation.replace(" ", "_") != wall


def test_the_rendered_report_names_the_wall_and_shows_the_measurements() -> None:
    report = host.HostReport(
        readiness=host.KERNEL_LACKS_USER_NAMESPACES,
        explanation=host.WALL_EXPLANATIONS[host.KERNEL_LACKS_USER_NAMESPACES],
        kernel="3.10.102",
        machine="x86_64",
        in_container=True,
        container_evidence="/.dockerenv exists",
        probes=[p.as_dict() for p in synology_nas().values()],
    )
    rendered = host.render(report)
    assert host.KERNEL_LACKS_USER_NAMESPACES in rendered
    assert "3.10.102" in rendered
    assert "user.max_user_namespaces" in rendered


def test_it_runs_on_this_machine_and_reaches_a_named_verdict() -> None:
    """Whatever host this suite is on, the tool must reach a verdict on it.

    Deliberately not asserting *which* one: this test runs on a NAS, on a
    hosted runner and one day on an Azure VM, and the answer differs. What must
    hold everywhere is that the tool ran, named one of its own walls, and
    exited 0 only if it saw a command execute.
    """
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert completed.returncode in (0, 1), completed.stderr
    payload = json.loads(completed.stdout)

    assert payload["readiness"] in host.ALL_READINESS_VALUES
    assert (payload["readiness"] == host.READY) == (completed.returncode == 0)
    assert payload["explanation"]
    assert payload["probes"], "a verdict with no measurements behind it"


@pytest.mark.parametrize("wall", host.ALL_READINESS_VALUES)
def test_no_two_walls_share_a_name(wall: str) -> None:
    assert host.ALL_READINESS_VALUES.count(wall) == 1


# ---------------------------------------------------------------------------
# The record, and the workflow that is supposed to be held to it
# ---------------------------------------------------------------------------
#
# `docs/codex_sandbox_hosts.json` opens by promising that every entry was
# measured and that nothing in it was written from expectation. A promise in a
# comment is worth what anyone remembers of it, so the parts of that promise a
# test can check are checked here.
#
# The rest of this section exists because of a specific failure shape. The
# survey workflow and the record are two files that have to agree about host
# keys, and the diagnostic and the record have to agree about verdict spellings.
# Neither agreement is visible when you edit one of them. A typo'd verdict makes
# the survey permanently red for a reason that has nothing to do with any host;
# a host key present in one file and absent from the other makes it permanently
# red for a host nobody forgot to measure. Both read as "the sandbox check is
# broken again", and both teach people to stop reading it.


def recorded_hosts() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))["hosts"]


def survey_workflow() -> dict:
    return yaml.safe_load(SURVEY_WORKFLOW.read_text(encoding="utf-8"))


def test_every_recorded_verdict_is_one_the_diagnostic_can_produce() -> None:
    """A verdict the tool cannot emit can never match, so it can never go green.

    This is the cheap half of keeping the record honest: it does not know
    whether a row is *true*, but it does know whether a row is *reachable*.
    """
    for name, entry in recorded_hosts().items():
        assert entry["readiness"] in host.ALL_READINESS_VALUES, (
            f"{name} is recorded as {entry['readiness']!r}, which "
            "scripts/diagnose_codex_sandbox_host.py never emits"
        )


def test_every_recorded_host_says_who_measured_it_and_when() -> None:
    """The file's own claim is that somebody looked. Make it say so per row."""
    for name, entry in recorded_hosts().items():
        assert entry.get("measured_by"), f"{name} does not say how it was measured"
        assert entry.get("measured_on"), f"{name} does not say when"
        assert entry.get("note"), f"{name} records a verdict with no reading of it"


def test_every_host_the_survey_measures_has_a_record() -> None:
    """Otherwise the survey is red forever on a host nobody forgot to measure.

    The checker exits 3 for an unrecorded key on purpose -- it refuses to write
    its own expectation. That is right on the day a host is first measured and
    wrong as a steady state, so the two files are held together here instead.
    """
    workflow = survey_workflow()
    matrix = workflow["jobs"]["survey"]["strategy"]["matrix"]["include"]
    keys = {leg["host_key"] for leg in matrix}

    # The container leg is compared too, and its key is written into the step
    # rather than into the matrix, so it is named here as well.
    keys.add("ubuntu-24.04-container")

    missing = keys - set(recorded_hosts())
    assert not missing, f"the survey measures {sorted(missing)} and nothing records them"


def test_the_host_the_suite_demands_a_sandbox_from_is_one_it_measured_ready() -> None:
    """`CODEX_SANDBOX_MUST_RUN=1` is only honest where the sandbox works.

    Setting it on a host that cannot sandbox would turn a true skip into a false
    failure, which is the same crime as the one this whole line of work exists
    to undo, pointed the other way. So the job that sets it must run on a host
    the record calls `ready`.
    """
    workflow = survey_workflow()
    job = workflow["jobs"]["prove-execution"]

    demanding = [
        step
        for step in job["steps"]
        if (step.get("env") or {}).get("CODEX_SANDBOX_MUST_RUN") == "1"
    ]
    assert demanding, "no step demands the sandbox actually run"

    runner = job["runs-on"]
    recorded = recorded_hosts().get(f"{runner}-host")
    assert recorded is not None, f"{runner} runs the demanding job and is unrecorded"
    assert recorded["readiness"] == host.READY, (
        f"{runner} is recorded as {recorded['readiness']!r}, so demanding that "
        "the sandbox run there would fail the suite for a property of the machine"
    )


def test_the_demanding_job_checks_readiness_before_it_demands_it() -> None:
    """The record can go stale; the host is asked again in the same job.

    Without this the job would be trusting a JSON file about a machine that is
    re-imaged on somebody else's schedule. With it, a 22.04 image that gains the
    restriction stops at the diagnostic -- which names the wall -- instead of at
    a pytest failure that would read as a broken run place.
    """
    job = survey_workflow()["jobs"]["prove-execution"]
    steps = job["steps"]

    diagnosed = next(
        (i for i, s in enumerate(steps) if "diagnose_codex_sandbox_host.py" in (s.get("run") or "")),
        None,
    )
    demanded = next(
        (
            i
            for i, s in enumerate(steps)
            if (s.get("env") or {}).get("CODEX_SANDBOX_MUST_RUN") == "1"
        ),
        None,
    )
    assert diagnosed is not None, "the job never asks whether this host can sandbox"
    assert demanded is not None
    assert diagnosed < demanded, "readiness is demanded before it is measured"

    gate = steps[diagnosed]
    assert not gate.get("continue-on-error"), (
        "the readiness gate cannot be advisory: a host that stopped sandboxing "
        "would sail past it into a pytest failure that names the wrong cause"
    )


def test_nothing_in_the_survey_buys_a_pass_by_weakening_isolation() -> None:
    """The four refused shortcuts, refused in a way that a diff would show.

    Any of these would make the tests green against a run place nobody uses. The
    check is textual on purpose -- it is looking for the flags themselves, so
    that adding one is a visible edit to this file's expectations rather than a
    line in a workflow nobody re-reads.
    """
    text = SURVEY_WORKFLOW.read_text(encoding="utf-8")
    for forbidden in (
        "--privileged",
        "--cap-add",
        "--security-opt",
        "--userns=host",
        "sysctl -w",
        "--dangerously-bypass-approvals-and-sandbox",
        "--use-legacy-landlock",
    ):
        offending = [
            line
            for line in text.splitlines()
            if forbidden in line and not line.lstrip().startswith("#")
        ]
        assert not offending, f"{forbidden} appears outside a comment: {offending}"


# ---------------------------------------------------------------------------
# The checker, against the real record
# ---------------------------------------------------------------------------


def measurement(tmp_path: Path, readiness: str) -> Path:
    path = tmp_path / "observed.json"
    path.write_text(
        json.dumps({"readiness": readiness, "explanation": "written by a test"}),
        encoding="utf-8",
    )
    return path


def test_a_host_that_still_behaves_as_recorded_passes(tmp_path: Path) -> None:
    for name, entry in recorded_hosts().items():
        observed = measurement(tmp_path, entry["readiness"])
        assert checker.main(["--host-key", name, "--observed", str(observed)]) == 0


def test_a_host_that_changed_fails_in_either_direction(tmp_path: Path) -> None:
    """Gaining the ability to sandbox is as important to hear about as losing it.

    A hosted runner image that quietly starts running commands under bubblewrap
    is a free execution host nobody would otherwise notice for months, which is
    the exact position this project spent weeks in.
    """
    was_ready = [n for n, e in recorded_hosts().items() if e["readiness"] == host.READY]
    was_not = [n for n, e in recorded_hosts().items() if e["readiness"] != host.READY]
    assert was_ready and was_not, "the record has lost one side of the comparison"

    became_unready = measurement(tmp_path, host.USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY)
    assert checker.main(["--host-key", was_ready[0], "--observed", str(became_unready)]) == 1

    became_ready = measurement(tmp_path, host.READY)
    assert checker.main(["--host-key", was_not[0], "--observed", str(became_ready)]) == 1


def test_an_unmeasured_host_is_refused_rather_than_accepted(tmp_path: Path) -> None:
    observed = measurement(tmp_path, host.READY)
    assert checker.main(["--host-key", "a-machine-nobody-has-run", "--observed", str(observed)]) == 3


def test_an_unreadable_measurement_is_not_a_pass(tmp_path: Path) -> None:
    missing = tmp_path / "never-written.json"
    assert checker.main(["--host-key", "xenology-nas", "--observed", str(missing)]) == 2

    garbled = tmp_path / "garbled.json"
    garbled.write_text("{not json", encoding="utf-8")
    assert checker.main(["--host-key", "xenology-nas", "--observed", str(garbled)]) == 2


def test_an_unreadable_record_fails_closed(tmp_path: Path) -> None:
    """An empty record would accept every observation. That is the wrong default.

    Each of these is a way the file could stop being readable, and none of them
    may be mistaken for "nothing has been recorded yet".
    """
    observed = measurement(tmp_path, host.READY)

    for content in ("{not json", json.dumps({"no_hosts_key": {}})):
        broken = tmp_path / "record.json"
        broken.write_text(content, encoding="utf-8")
        with pytest.raises(SystemExit):
            checker.main(
                [
                    "--host-key",
                    "xenology-nas",
                    "--observed",
                    str(observed),
                    "--record",
                    str(broken),
                ]
            )

    with pytest.raises(SystemExit):
        checker.main(
            [
                "--host-key",
                "xenology-nas",
                "--observed",
                str(observed),
                "--record",
                str(tmp_path / "absent.json"),
            ]
        )
