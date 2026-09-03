"""The trigger checker has to agree with the decision it is checking.

The Xenology card looked at this host on 2026-09-01 and decided: not yet, no
Azure VM. `scripts/check_dev_host_migration_triggers.py` now answers the same
question automatically, and the two must not contradict each other. A checker
that fires on the numbers a human already judged acceptable is not a checker --
it is a second opinion that overrules the first one without being asked.

So the anchor of this file is `test_the_cards_own_baseline_stays_quiet`. It
feeds the tool the exact readings written on the card -- 8 vCPU under load
5.34/3.43/2.10, ~21 GiB available, ~199 GiB free -- and requires the resource
conditions to stay silent. Anyone who lowers a threshold past that line fails a
test that names the date and the decision.

The second thing this file defends is the difference between *no* and *did not
ask*. The tool has three states, not two, and the tests that matter most are
the ones asserting that an unmeasurable condition never collapses into a pass:
condition 2 on every host, the OOM counter on any kernel below 4.13, and the
seccomp probe whenever it cannot reach a verdict.

Everything is driven through fabricated `HostFacts`, so a Synology 3.10 kernel
and an Azure 6.8 kernel are both exercised wherever this suite happens to run.
That is deliberate: the rules are about hosts this suite will mostly not be
running on.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_dev_host_migration_triggers as triggers  # noqa: E402

GIB = 1024 ** 3


# ---------------------------------------------------------------------------
# Two hosts, neither of which is necessarily the one running this test
# ---------------------------------------------------------------------------


def synology_3_10() -> triggers.HostFacts:
    """This box, as measured on 2026-09-01 and written on the card.

    Kernel 3.10.102 under an Ubuntu 22.04 userspace: no seccomp TSYNC (3.17),
    no user-namespace sysctl (4.9), no oom_kill counter (4.13), no MemAvailable
    (3.14), cgroup v1, aufs instead of overlay, Docker 20.10.3.

    The load and headroom figures are the card's own baseline readings, which
    is what makes this fixture a calibration anchor rather than an example.
    """
    return triggers.HostFacts(
        kernel_release="3.10.102",
        kernel_version_tuple=(3, 10, 102),
        os_pretty_name="Ubuntu 22.04.5 LTS",
        machine="x86_64",
        cpu_count=8,
        load1=5.34,
        load5=3.43,
        load15=2.10,
        mem_total_bytes=31 * GIB,
        mem_available_bytes=21 * GIB,
        mem_available_is_estimated=True,
        root_free_bytes=199 * GIB,
        tmpdir_path="/tmp",
        tmpdir_free_bytes=199 * GIB,
        seccomp_tsync_available=False,
        seccomp_probe_detail="core.agentic_python_launcher raised 'seccomp TSYNC unavailable'",
        cgroup_version=1,
        user_namespaces_max=None,
        user_namespace_sysctl_present=False,
        overlayfs_available=False,
        docker_client_present=True,
        docker_server_version="20.10.3",
        docker_server_version_tuple=(20, 10, 3),
        oom_kill_count=None,
        oom_counter_present=False,
    )


def azure_6_8() -> triggers.HostFacts:
    """What the card would be buying: a current kernel with room to spare."""
    return triggers.HostFacts(
        kernel_release="6.8.0-51-generic",
        kernel_version_tuple=(6, 8, 0),
        os_pretty_name="Ubuntu 24.04.1 LTS",
        machine="x86_64",
        cpu_count=16,
        load1=0.4,
        load5=0.3,
        load15=0.2,
        mem_total_bytes=64 * GIB,
        mem_available_bytes=58 * GIB,
        mem_available_is_estimated=False,
        root_free_bytes=400 * GIB,
        tmpdir_path="/tmp",
        tmpdir_free_bytes=400 * GIB,
        seccomp_tsync_available=True,
        seccomp_probe_detail="the launcher installed its filter with TSYNC",
        cgroup_version=2,
        user_namespaces_max=63488,
        user_namespace_sysctl_present=True,
        overlayfs_available=True,
        docker_client_present=True,
        docker_server_version="27.3.1",
        docker_server_version_tuple=(27, 3, 1),
        oom_kill_count=0,
        oom_counter_present=True,
    )


def condition(report: dict, number: int) -> dict:
    return next(c for c in report["conditions"] if c["id"] == number)


# ---------------------------------------------------------------------------
# The calibration anchor
# ---------------------------------------------------------------------------


def test_the_cards_own_baseline_stays_quiet() -> None:
    """The resource thresholds must not overrule a decision already made.

    On 2026-09-01 the operator read these numbers and wrote "지금은 Azure VM을
    만들지 않는다". Conditions 3 and 4 are the two the operator was weighing
    when they wrote it, so a default threshold that fires on them would put the
    tool in direct contradiction with the card it implements.

    Scoped to 3 and 4 on purpose. Conditions 1 and 5 were *also* true on that
    date -- see the next test -- and the card not recording them is the gap
    this tool exists to close, not a judgement it has to respect.
    """
    report = triggers.evaluate(synology_3_10())

    assert condition(report, 3)["status"] == triggers.NOT_FIRED
    assert condition(report, 4)["status"] == triggers.NOT_FIRED

    # 2.10 across 8 cores is roughly a quarter of the default threshold; if a
    # future edit halves the threshold this still passes, and that is fine. The
    # line this test draws is at the card's numbers, not at any given margin.
    assert condition(report, 3)["evidence"][0]["load15_per_cpu"] == 0.263


def test_the_kernel_conditions_were_already_firing_on_that_baseline() -> None:
    """The card's five conditions were not all in the future.

    Two of them had already reproduced on the day the baseline was written, and
    nothing in the repository said so. That is the finding this tool delivers on
    its first run -- so it is asserted here rather than left to be rediscovered.
    """
    report = triggers.evaluate(synology_3_10())

    assert report["fired"] == [1, 5]
    assert report["verdict"] == "migrate"
    assert "seccomp TSYNC" in condition(report, 1)["missing_features"]


def test_a_current_kernel_fires_nothing() -> None:
    report = triggers.evaluate(azure_6_8())

    assert report["fired"] == []
    assert report["verdict"] == "stay"
    for number in (1, 3, 4, 5):
        assert condition(report, number)["status"] == triggers.NOT_FIRED


# ---------------------------------------------------------------------------
# "Did not ask" must never read as "no"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("facts", [synology_3_10(), azure_6_8()], ids=["3.10", "6.8"])
def test_condition_two_is_unanswered_on_every_host(facts: triggers.HostFacts) -> None:
    """No single machine can tell whether it disagrees with another one.

    Even the ideal host reports this as unanswered. If it ever came back
    `not_fired`, the tool would be claiming CI and local agree on the strength
    of never having compared them.
    """
    report = triggers.evaluate(facts)

    assert condition(report, 2)["status"] == triggers.NOT_MEASURABLE
    assert 2 in report["not_measurable_here"]
    assert condition(report, 2)["what_would_answer_it"]


def test_a_clean_verdict_still_names_what_was_not_asked() -> None:
    """Exit 0 has to carry its own caveat, in the text and in the JSON."""
    report = triggers.evaluate(azure_6_8())

    assert report["verdict"] == "stay"
    assert report["not_measurable_here"] == [2]
    assert "not answered" in report["verdict_means"].lower() or (
        "Conditions [2] were not answered" in report["verdict_means"]
    )
    assert "not evidence of anything" in report["verdict_means"]


def test_an_absent_oom_counter_is_reported_even_when_headroom_is_fine() -> None:
    """Free memory now is not evidence that nothing was killed an hour ago.

    Condition 4 is `not_fired` on this host, which is a true statement about
    headroom and says nothing at all about the OOM killer. The report has to
    carry both, or the honest half disappears behind the reassuring half.
    """
    report = triggers.evaluate(synology_3_10())
    fourth = condition(report, 4)

    assert fourth["status"] == triggers.NOT_FIRED
    assert "whether the OOM killer has fired" in fourth["unanswered_parts"]

    oom_row = next(
        row for row in fourth["evidence"]
        if row["measure"] == "oom_kill events since boot"
    )
    assert oom_row["value"] is None
    assert "4.13" in oom_row["note"]


def test_a_kernel_with_the_counter_reports_a_real_oom_history() -> None:
    facts = replace(azure_6_8(), oom_kill_count=3, oom_counter_present=True)
    fourth = condition(triggers.evaluate(facts), 4)

    assert fourth["status"] == triggers.FIRED
    assert "OOM killer has fired 3 times" in fourth["summary"]
    assert fourth["unanswered_parts"] == []


def test_an_undecided_seccomp_probe_is_not_a_pass() -> None:
    """A probe that could not run must not be counted as a working sandbox.

    This is the failure mode that would matter most: libseccomp missing, the
    subprocess timing out, the module moving. Reporting `not_fired` there would
    tell the operator the security verification runs here when nobody checked.
    """
    facts = replace(
        azure_6_8(),
        seccomp_tsync_available=None,
        seccomp_probe_detail="probe reached no verdict: ModuleNotFoundError: seccomp",
    )
    report = triggers.evaluate(facts)

    assert condition(report, 5)["status"] == triggers.NOT_MEASURABLE
    assert "seccomp TSYNC" in condition(report, 1)["unknown_features"]
    assert "seccomp TSYNC" not in condition(report, 1)["missing_features"]
    assert 5 in report["not_measurable_here"]


def test_resource_readings_that_fail_entirely_do_not_report_as_healthy() -> None:
    facts = replace(
        azure_6_8(),
        mem_available_bytes=None,
        root_free_bytes=None,
        tmpdir_free_bytes=None,
        oom_counter_present=False,
        oom_kill_count=None,
    )
    fourth = condition(triggers.evaluate(facts), 4)

    assert fourth["status"] == triggers.NOT_MEASURABLE
    assert "memory and disk headroom are above" not in fourth["summary"]


def test_a_missing_load_average_is_unmeasurable_rather_than_idle() -> None:
    facts = replace(azure_6_8(), load15=None)
    assert condition(triggers.evaluate(facts), 3)["status"] == triggers.NOT_MEASURABLE


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------


def test_sustained_saturation_fires_but_the_judgement_is_handed_back() -> None:
    """A busy box is a measurement; "it is blocking me" is not.

    The tool can see the run queue. It cannot see whether anyone is waiting on
    it, and a saturated machine nobody is waiting on is not a reason to spend
    money. Firing without saying so would dress a judgement up as a reading.
    """
    facts = replace(azure_6_8(), cpu_count=8, load15=9.6)
    third = condition(triggers.evaluate(facts), 3)

    assert third["status"] == triggers.FIRED
    assert third["operator_judgement_still_required"] is True
    assert "judgement, not a reading" in third["unmeasured_half"]


def test_the_one_minute_spike_of_a_test_run_does_not_fire() -> None:
    """Two pytest runs push load1 over the core count for a minute at a time.

    That is this box working, not this box failing. Condition 3 reads the
    fifteen-minute figure precisely so a test suite cannot trigger a migration
    recommendation by running.
    """
    facts = replace(azure_6_8(), cpu_count=8, load1=19.0, load5=8.0, load15=1.2)
    assert condition(triggers.evaluate(facts), 3)["status"] == triggers.NOT_FIRED


def test_low_memory_and_low_disk_each_fire_on_their_own() -> None:
    starved = replace(azure_6_8(), mem_available_bytes=int(0.5 * GIB))
    assert condition(triggers.evaluate(starved), 4)["status"] == triggers.FIRED

    full = replace(azure_6_8(), tmpdir_free_bytes=int(2 * GIB))
    fourth = condition(triggers.evaluate(full), 4)
    assert fourth["status"] == triggers.FIRED
    assert "tmpdir" in fourth["summary"]


def test_thresholds_are_arguments_not_constants() -> None:
    """The same facts, judged twice, differently. Anything else is a hard-code."""
    facts = synology_3_10()
    strict = triggers.Thresholds(min_free_disk_gib=500.0)

    assert condition(triggers.evaluate(facts), 4)["status"] == triggers.NOT_FIRED
    assert condition(triggers.evaluate(facts, strict), 4)["status"] == triggers.FIRED


# ---------------------------------------------------------------------------
# Purity, parsing, output shape
# ---------------------------------------------------------------------------


def test_evaluate_never_reads_the_host_it_runs_on() -> None:
    """Otherwise these tests only pass on the machine that wrote them.

    Whichever kernel this suite is running on, one of the two fixtures is a lie
    about it -- and both still have to be judged on their own contents.
    """
    report = triggers.evaluate(azure_6_8())

    assert report["host"]["kernel"] == "6.8.0-51-generic"
    assert report["host"]["cpu_count"] == 16
    assert triggers.evaluate(azure_6_8()) == report  # deterministic


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3.10.102", (3, 10, 102)),
        ("6.8.0-51-generic", (6, 8, 0)),
        ("20.10.3", (20, 10, 3)),
        ("27.3.1+azure", (27, 3, 1)),
        ("", ()),
        ("unknown", ()),
    ],
)
def test_version_parsing(text: str, expected: tuple) -> None:
    assert triggers._parse_version(text) == expected


def test_an_unparseable_docker_version_is_unknown_not_ancient() -> None:
    """A version string this tool cannot read is not evidence of an old daemon."""
    facts = replace(
        azure_6_8(), docker_server_version="dev", docker_server_version_tuple=(),
    )
    first = condition(triggers.evaluate(facts), 1)

    assert "current Docker" not in first["missing_features"]
    assert "docker server version" in first["unknown_features"]


def test_the_text_report_puts_the_unanswered_list_above_the_verdict() -> None:
    """A reader who stops after the first screen must not read an all-clear."""
    text = triggers.render_text(triggers.evaluate(azure_6_8()))

    assert "NOT ANSWERED HERE" in text
    assert text.index("NOT ANSWERED HERE") < text.index("verdict:")


def test_exit_status_separates_fired_from_clean(monkeypatch) -> None:
    monkeypatch.setattr(triggers, "gather_host_facts", lambda **_: azure_6_8())
    assert triggers.main([]) == 0

    monkeypatch.setattr(triggers, "gather_host_facts", lambda **_: synology_3_10())
    assert triggers.main([]) == 1


def test_a_probe_that_cannot_read_the_host_at_all_exits_two(monkeypatch) -> None:
    """Distinct from both verdicts: a broken instrument is not a result."""
    def explode(**_):
        raise OSError("/proc is not mounted")

    monkeypatch.setattr(triggers, "gather_host_facts", explode)
    assert triggers.main([]) == 2


def test_json_output_is_written_where_asked(tmp_path, monkeypatch, capsys) -> None:
    import json

    monkeypatch.setattr(triggers, "gather_host_facts", lambda **_: synology_3_10())
    out = tmp_path / "nested" / "report.json"

    assert triggers.main(["--json", "--out", str(out)]) == 1

    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["fired"] == [1, 5]
    assert json.loads(capsys.readouterr().out) == written


# ---------------------------------------------------------------------------
# The parts that have to keep agreeing with code this file does not own
# ---------------------------------------------------------------------------


def test_the_seccomp_marker_is_the_same_string_in_all_three_places() -> None:
    """The launcher raises it, the security test skips on it, this tool reads it.

    Three files grepping for one literal. If someone rewords the exception, the
    security test starts failing instead of skipping -- loudly -- but this tool
    would quietly return "no verdict" forever. This test makes the rewording
    fail here too, next to the reason.
    """
    marker = "seccomp TSYNC unavailable"
    root = Path(__file__).resolve().parent.parent

    launcher = (root / "core" / "agentic_python_launcher.py").read_text(encoding="utf-8")
    security = (root / "tests" / "test_agentic_sandbox_security.py").read_text(encoding="utf-8")
    tool = Path(triggers.__file__).read_text(encoding="utf-8")

    assert marker in launcher
    assert marker in security
    assert marker in tool


def test_the_probe_reaches_a_verdict_or_says_why_not() -> None:
    """Run the real probe here, whatever "here" is.

    Deliberately not asserting which answer: this suite runs on a 3.10 kernel
    locally and a 6.x one in CI, and pinning the outcome would mean pinning the
    host. What is asserted is that the probe always produces a verdict *and* a
    reason -- an unexplained None is the one result that would leave conditions
    1 and 5 silently unanswerable.
    """
    available, detail = triggers.probe_seccomp_tsync()

    assert available in (True, False, None)
    assert detail
    if available is False:
        assert "seccomp TSYNC unavailable" in detail
    if available is None:
        assert "probe" in detail


def test_reading_this_host_produces_a_report(tmp_path) -> None:
    """End to end, on the real machine, with no assertion about the answer."""
    facts = triggers.gather_host_facts(run_seccomp_probe=False)
    report = triggers.evaluate(facts)

    assert len(report["conditions"]) == 5
    assert {c["status"] for c in report["conditions"]} <= {
        triggers.FIRED, triggers.NOT_FIRED, triggers.NOT_MEASURABLE,
    }
    assert report["host"]["kernel"]
    # Skipping the probe must not silently upgrade seccomp to "fine".
    assert 5 in report["not_measurable_here"]


def test_every_condition_carries_its_korean_title() -> None:
    """The card is in Korean and so is the record written back to it."""
    report = triggers.evaluate(synology_3_10())
    for item in report["conditions"]:
        assert item["title_ko"]
        assert item["title"]


# ---------------------------------------------------------------------------
# The fingerprint
# ---------------------------------------------------------------------------


def test_this_script_does_not_move_the_grader_fingerprint() -> None:
    """A diagnostic must not invalidate a grading approval given for something else.

    ``compute_grader_source_hash`` takes exactly one file out of ``scripts/``,
    ``download_inference_from_hf.py``. Restating that from the source listing
    would prove nothing, so this creates a real file beside the tool and
    requires the digest to come back byte-identical.
    """
    import yaml

    from step8_grade import compute_grader_source_hash  # noqa: E402

    config_path = Path(__file__).resolve().parent.parent / "grading_configs" / "default_v2.yaml"
    with config_path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    before = compute_grader_source_hash(config_path, config)

    intruder = Path(triggers.__file__).with_name("_dev_host_fingerprint_tmp.py")
    assert not intruder.exists()
    try:
        intruder.write_text("# transient, for one assertion\n", encoding="utf-8")
        after = compute_grader_source_hash(config_path, config)
    finally:
        intruder.unlink(missing_ok=True)

    assert after == before
    assert len(before) == 64


def test_the_tool_lives_where_that_exemption_applies() -> None:
    """Named so that moving it into core/ is caught here rather than in a run."""
    assert Path(triggers.__file__).parent.name == "scripts"
    assert Path(triggers.__file__).name == "check_dev_host_migration_triggers.py"
