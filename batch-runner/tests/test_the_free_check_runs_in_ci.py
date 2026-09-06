"""The free run-place check runs in CI, and what it cannot see stays unsaid.

The advance check for the run-place comparison has existed for a while and
nothing ran it, so a change breaking one of the fixed conditions reached main
with nothing saying so. ``.github/workflows/execution-envelope-preflight.yml``
runs it on every pull request. That workflow is given no secrets, which is the
point and also the difficulty: the check's default policy is fail closed, and a
machine with no cloud sign-in cannot satisfy it, so wiring the default straight
into CI would produce a job that is red on every commit forever.

The narrowed mode exists for that, and these tests hold the two directions it
could go wrong in:

  * it must not let a real fault through -- a fault in the code or the plan
    reads the same on every machine and still decides the exit code
  * it must not report as passed anything it did not look at -- what a
    secret-less machine cannot settle is written down as not checked, and a
    green run never reports that a paid run may start

Then the pieces around it: a summariser that refuses an unreadable report
rather than rendering an empty one, and a workflow whose shape cannot drift
into claiming access it was never given.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

SCRIPTS = BATCH_RUNNER_ROOT / "scripts"
CHECK = SCRIPTS / "check_execution_envelope_advance_check.py"
SUMMARISE = SCRIPTS / "summarise_execution_envelope_check_in_korean.py"
WORKFLOW = (
    REPOSITORY_ROOT / ".github/workflows/execution-envelope-preflight.yml"
)

sys.path.insert(0, str(SCRIPTS))

from check_execution_envelope_advance_check import (  # noqa: E402
    STATUS_NOT_CHECKED,
    _offline_verdict,
    split_by_what_a_checkout_can_settle,
)
from summarise_execution_envelope_check_in_korean import (  # noqa: E402
    CannotSummarise,
    _group_notes_by_run_place,
    summarise,
)


def _as_a_machine_with_nothing(**extra: str) -> dict:
    """The environment the workflow runs in: no sign-in, no dataset cache.

    Spelled out rather than inherited, so a developer box that happens to hold
    Azure settings or a downloaded dataset does not quietly test a different
    situation from the one CI is in.
    """
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AZURE_", "FOUNDRY_", "OPENAI_", "HF_"))
    }
    for name in _credential_variables_the_code_names():
        environment.pop(name, None)
    environment["HF_HOME"] = "/nonexistent-so-nothing-is-cached"
    environment["HF_HUB_OFFLINE"] = "1"
    environment.update(extra)
    return environment


def _run_check(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK), *arguments],
        cwd=BATCH_RUNNER_ROOT,
        env=_as_a_machine_with_nothing(),
        capture_output=True,
        text=True,
    )


def _credential_variables_the_code_names() -> set[str]:
    """Every environment variable core/azure_ai_clients.py names, flattened.

    Two of these constants are tuples of static-credential names the module
    refuses to run with at all, so a name-by-name copy is not enough: reading
    the constants is what keeps this honest when one is added.
    """
    from core import azure_ai_clients

    names: set[str] = set()
    for attribute in dir(azure_ai_clients):
        if not attribute.endswith("_ENV"):
            continue
        value = getattr(azure_ai_clients, attribute)
        if isinstance(value, str):
            names.add(value)
        elif isinstance(value, (tuple, list, frozenset, set)):
            names.update(str(item) for item in value)
    return names


@pytest.fixture(scope="module")
def report() -> dict:
    """What the workflow's own command produces, run exactly as written."""
    completed = _run_check(
        "--json",
        "--skip-docker-probe",
        "--exit-on-code-and-contract-problems-only",
    )
    assert completed.returncode == 0, (
        "the free check reports a fault in the code or the plan on this tree:\n"
        + completed.stdout[-4000:]
        + completed.stderr[-2000:]
    )
    return json.loads(completed.stdout)


@pytest.fixture
def result(monkeypatch):
    """The check's own result object, for the split's unit-level tests.

    Built with the same environment the workflow has -- nothing -- rather than
    with this machine's. A developer box holding Azure settings or a warm
    dataset cache would otherwise test a situation CI is never in, and the
    tests below would pass here and mean nothing there.
    """
    for name in _credential_variables_the_code_names():
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HF_HOME", "/nonexistent-so-nothing-is-cached")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    from core.execution_envelope_preflight import load_plan, run_envelope_preflight

    plan = load_plan(
        BATCH_RUNNER_ROOT
        / "experiments"
        / "execution_envelope"
        / "advance_check_plan.yaml"
    )
    return run_envelope_preflight(
        plan,
        root=BATCH_RUNNER_ROOT,
        docker_daemon_available=None,
        docker_image_available=None,
        azure_route_profile=None,
        azure_route_served=None,
        dataset_root=None,
    )


# ── the split: nothing is lost, and nothing is quietly forgiven ───────────


def test_every_problem_found_appears_under_exactly_one_heading(result):
    """The invariant the whole narrowing rests on.

    If a problem could appear in neither list it would vanish: absent from the
    exit code and absent from the report. The split is written to raise rather
    than let that happen, and this is the test that would notice if the two
    sources it partitions by ever stopped covering the whole.
    """
    code_and_contract, not_checked = split_by_what_a_checkout_can_settle(result)

    set_aside = {
        note for entry in not_checked for note in entry["notes"]
    }
    for problem in result.all_problems:
        appearances = (problem in code_and_contract) + (problem in set_aside)
        assert appearances == 1, (
            f"{problem!r} appears in {appearances} of the two lists, not one"
        )


def test_a_setting_this_machine_was_never_given_does_not_decide_the_exit_code(
    result,
):
    """The reason the narrowed mode exists.

    Every one of these is a true statement about the machine and a useless
    statement about the branch. Left in the exit code they would make the job
    red on every commit forever, and a job nobody can get green is a job
    nobody reads.
    """
    code_and_contract, not_checked = split_by_what_a_checkout_can_settle(result)

    assert result.azure is not None, "the plan stopped diagnosing Azure at all"
    assert result.azure.problems, (
        "this test is meaningless if the machine running it has the Azure "
        "settings; the environment fixture is supposed to strip them"
    )
    for problem in result.azure.problems:
        assert problem not in code_and_contract, problem

    reported = {note for entry in not_checked for note in entry["notes"]}
    for problem in result.azure.problems:
        assert problem in reported, f"{problem!r} was dropped rather than reported"


def test_a_fingerprint_that_could_not_be_compared_is_not_a_fingerprint_that_matched(
    report,
):
    """Asserted from the report the workflow produces, not from this machine.

    Whether the pinned files are on disk is decided by the Hugging Face cache,
    and that path is resolved when the package is imported -- so a test that
    set HF_HOME afterwards would still be reading this developer box's warm
    cache and would measure nothing. The subprocess above runs with a cache
    that is not there, which is the situation on a runner.
    """
    missing = report["missing_input_file_problems"]
    assert missing, (
        "the check found every pinned input file on a machine pointed at an "
        "empty cache, so it is not really comparing them"
    )

    verdict = report["offline_verdict"]
    reported = {
        note for entry in verdict["not_checked_here"] for note in entry["notes"]
    }
    for problem in missing:
        assert problem not in verdict["problems"], (
            f"{problem!r} decided the exit code, which would make this job red "
            "on every commit for a file the runner was never going to have"
        )
        assert problem in reported, f"{problem!r} was dropped rather than reported"


def test_a_fault_in_the_plan_still_decides_the_exit_code(result):
    """The other direction: narrowing must not narrow away a real fault."""
    invented = "the plan pins a task nobody in this repository can run"
    pretend = SimpleNamespace(
        all_problems=list(result.all_problems) + [invented],
        missing_input_file_problems=result.missing_input_file_problems,
        azure=result.azure,
        readiness=result.readiness,
        may_start=result.may_start,
    )

    code_and_contract, _ = split_by_what_a_checkout_can_settle(pretend)

    assert invented in code_and_contract


def test_a_list_that_stopped_feeding_the_verdict_is_raised_rather_than_reported(
    result,
):
    """The guard on the split's premise, exercised.

    The two lists set aside are sub-lists of the problems the check found. If
    the aggregate ever stopped collecting one of them, this function would go
    on printing its contents under "not checked here" while the check no
    longer counts them at all -- a summary describing a diagnosis nothing is
    running. It refuses rather than reporting a heading it can no longer
    justify.
    """
    pretend = SimpleNamespace(
        # The aggregate has lost the Azure findings while azure.problems still
        # holds them, which is what the refactor being guarded against looks
        # like from here.
        all_problems=[],
        missing_input_file_problems=[],
        azure=result.azure,
        readiness=result.readiness,
        may_start=result.may_start,
    )

    with pytest.raises(AssertionError, match="no longer feeds the verdict"):
        split_by_what_a_checkout_can_settle(pretend)


def test_the_two_lists_it_sets_aside_are_both_still_feeding_the_verdict(result):
    """The same premise, on the real result rather than a fabricated one."""
    counted = set(result.all_problems)

    assert set(result.missing_input_file_problems) <= counted
    assert result.azure is not None
    assert set(result.azure.problems) <= counted


def test_what_was_not_checked_says_why_and_what_would_settle_it(result):
    """"Not checked" is only useful if it names the way out."""
    _, not_checked = split_by_what_a_checkout_can_settle(result)

    assert not_checked, "a machine with no sign-in checked everything?"
    for entry in not_checked:
        assert entry["status"] == STATUS_NOT_CHECKED
        assert entry["status"] != "passed"
        assert entry["why_this_machine_cannot_say"].strip()
        assert entry["what_would_settle_it"].strip()


def test_each_run_place_that_was_not_confirmed_is_named_with_its_state(result):
    """The three run places' individual states survive the narrowing.

    A summary that said only "no fault found" would read as three working run
    places. Two of them were not looked at.
    """
    _, not_checked = split_by_what_a_checkout_can_settle(result)

    about_run_places = [
        entry for entry in not_checked if "run place really answers" in entry["what"]
    ]
    assert len(about_run_places) == 1
    said = " ".join(about_run_places[0]["notes"])
    for environment in ("docker_container", "azure_code_interpreter"):
        assert environment in said, f"{environment} was not named: {said}"
        assert "evidence_insufficient" in said


def test_the_narrowed_verdict_never_reports_that_a_run_may_start(result):
    """The sentence this whole job must not be able to say."""
    verdict = _offline_verdict(
        *split_by_what_a_checkout_can_settle(result), result=result
    )

    assert verdict["run_may_start"] is result.may_start
    assert verdict["run_may_start"] is False, (
        "the default fail-closed policy passed on a machine with no sign-in, "
        "which means it stopped requiring one"
    )
    assert verdict["no_problem_here_is_not_permission_to_start"] is True
    assert verdict["nothing_was_spent"] is True


# ── the script's exit codes, run the way the workflow runs it ─────────────


def test_the_default_policy_is_still_fail_closed_without_a_sign_in():
    """The paid path is untouched. This is the half that must stay red."""
    completed = _run_check("--json", "--skip-docker-probe")

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["may_start"] is False
    assert "offline_verdict" not in payload, (
        "the narrowed block appeared without being asked for, so the default "
        "policy is reporting a verdict it did not compute"
    )


def test_the_narrowed_mode_passes_on_this_tree_and_still_says_may_start_false(
    report,
):
    verdict = report["offline_verdict"]

    assert verdict["problems"] == []
    assert verdict["run_may_start"] is False
    assert report["may_start"] is False
    assert verdict["not_checked_here"], (
        "the narrowed mode passed and recorded nothing as unchecked, which "
        "would mean it believes a secret-less machine verified everything"
    )


def test_the_narrowed_mode_leaves_the_full_report_intact(report):
    """The narrowing changes the exit code, not what is written down."""
    for key in (
        "readiness",
        "uncontrolled_differences",
        "pure_run_place_effect_is_measurable",
        "input_files",
        "cost_ceiling",
        "azure_connection",
    ):
        assert key in report, f"{key} was dropped from the narrowed report"

    assert report["pure_run_place_effect_is_measurable"] is False
    assert len(report["uncontrolled_differences"]) >= 6


def test_the_text_output_says_it_is_not_permission_to_start():
    completed = _run_check(
        "--skip-docker-probe", "--exit-on-code-and-contract-problems-only"
    )

    assert completed.returncode == 0
    assert "Not checked here (not the same as checked and passed)" in completed.stdout
    assert "not permission to start a paid run" in completed.stdout
    assert "may_start=False" in completed.stdout


# ── the summary: an unreadable report is a failure, not an empty page ─────


def _summarise_file(tmp_path: Path, contents: str) -> subprocess.CompletedProcess:
    report_path = tmp_path / "report.json"
    report_path.write_text(contents, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SUMMARISE), str(report_path)],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("what", "contents"),
    [
        ("empty", ""),
        ("whitespace", "   \n  \n"),
        ("truncated", '{"offline_verdict": {"problems": ['),
        ("not an object", "[1, 2, 3]"),
        ("not json at all", "Traceback (most recent call last):"),
    ],
)
def test_an_unreadable_report_fails_loudly_rather_than_summarising_nothing(
    tmp_path, what, contents
):
    """The failure mode this program exists to prevent.

    A summariser that shrugged at a damaged report would print a short page
    with no problems on it, which on a build page is indistinguishable from a
    page saying nothing was wrong.
    """
    completed = _summarise_file(tmp_path, contents)

    assert completed.returncode == 1, what
    assert "요약을 만들 수 없습니다" in completed.stderr, what
    assert completed.stdout == "", (
        f"{what}: something was printed as a summary anyway: {completed.stdout!r}"
    )


def test_a_report_that_is_not_there_fails_rather_than_being_treated_as_empty(
    tmp_path,
):
    completed = subprocess.run(
        [sys.executable, str(SUMMARISE), str(tmp_path / "never-written.json")],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "요약을 만들 수 없습니다" in completed.stderr
    assert completed.stdout == ""


@pytest.mark.parametrize(
    "key",
    [
        "offline_verdict",
        "readiness",
        "uncontrolled_differences",
        "pure_run_place_effect_is_measurable",
        "may_start",
        "input_files",
    ],
)
def test_a_report_missing_a_key_is_refused_and_the_key_is_named(report, key):
    """A missing key is not an empty value.

    Reading these with ``.get(key, [])`` would let a report that lost half its
    contents render as a clean summary -- the exact shape of hiding a failure
    as a success.
    """
    damaged = {k: v for k, v in report.items() if k != key}

    with pytest.raises(CannotSummarise, match=key):
        summarise(damaged)


def test_a_report_with_no_input_fingerprints_is_refused(report):
    """Zero is not a pass.

    The comparison's premise is five pinned tasks with pinned input files. A
    report listing none of them has not shown that they agree; it has failed
    to say anything, and it must not render as a page with a tidy empty list.
    """
    damaged = dict(report)
    damaged["input_files"] = {}

    with pytest.raises(CannotSummarise, match="빈 목록은 통과가 아니라"):
        summarise(damaged)


def test_a_compared_run_place_with_no_recorded_state_is_refused(report):
    damaged = json.loads(json.dumps(report))
    dropped = damaged["readiness"]["compared_environments"][0]
    damaged["readiness"]["environments"] = [
        entry
        for entry in damaged["readiness"]["environments"]
        if entry["environment"] != dropped
    ]

    with pytest.raises(CannotSummarise, match=dropped):
        summarise(damaged)


# ── the summary: what a Korean reader must be able to see on the page ─────


@pytest.fixture(scope="module")
def korean(report) -> str:
    return summarise(report, commit="0" * 40)


def test_the_summary_keeps_all_three_run_places_and_their_states(report, korean):
    compared = report["readiness"]["compared_environments"]
    assert len(compared) == 3
    for environment in compared:
        assert environment in korean, environment

    graded = {
        entry["environment"]: entry["status"]
        for entry in report["readiness"]["environments"]
    }
    # One of the three really can run here and two were never looked at. A
    # summary that flattened those into one verdict would be the failure this
    # whole job is meant to avoid.
    assert graded["host_python_process"] == "can_run_real_experiment"
    assert "지금 실제로 돌릴 수 있음" in korean
    for environment in ("docker_container", "azure_code_interpreter"):
        assert graded[environment] == "evidence_insufficient"
    assert korean.count("확인하지 않음") >= 2

    # Every blocker recorded against a compared run place reaches the page.
    for environment in compared:
        entry = next(
            e
            for e in report["readiness"]["environments"]
            if e["environment"] == environment
        )
        for blocker in entry.get("blockers") or []:
            assert blocker in korean, blocker


def test_the_summary_keeps_the_run_places_this_repository_cannot_run(
    report, korean
):
    """V2 and the Codex routes stay on the page, each with its own state.

    They are not part of the comparison, and a summary that quietly omitted
    them would read as though every run place in the repository took part.
    Naming them without their state would be worse: "structure check only"
    and "no code for this here" are different situations.
    """
    compared = report["readiness"]["compared_environments"]
    others = [
        entry
        for entry in report["readiness"]["environments"]
        if entry["environment"] not in compared
    ]
    assert len(others) >= 5, "the report stopped grading the run places it excludes"

    for entry in others:
        assert entry["environment"] in korean, entry["environment"]
    assert "이 저장소에 이 방식으로 돌리는 코드가 없음" in korean
    assert "모양만 볼 수 있음" in korean


def test_the_summary_keeps_the_differences_nobody_could_control(report, korean):
    assert "없앨 수 없는 차이" in korean
    assert f"{len(report['uncontrolled_differences'])}개" in korean
    assert "실행 장소만의 효과를 잴 수 있는가 = 아니오(False)" in korean


def test_the_summary_says_green_is_not_permission(korean):
    assert "유료 실험을 돌려도 된다는 허가가 **아닙니다**" in korean
    assert "실행 환경이 다 준비됐다는 뜻도 **아닙니다**" in korean
    assert "실행 가능 = 아니오(False)" in korean


def test_the_summary_carries_the_commit_and_the_input_fingerprints(
    report, korean
):
    """Requirement for tying this run to the earlier free five-task result.

    A date does not identify a tree and a branch name does not either. The
    commit and the written fingerprints do, so both are on the page.
    """
    assert "0" * 40 in korean

    written = {
        check["written"]
        for verification in report["input_files"].values()
        for check in verification["checks"]
    }
    assert written, "the report listed no input fingerprints at all"
    for fingerprint in written:
        assert fingerprint in korean, fingerprint


def test_a_summary_with_no_commit_says_so_rather_than_leaving_a_blank(report):
    assert "(전달받지 못함)" in summarise(report)


def test_the_summary_does_not_call_an_unknown_cost_zero(korean):
    """The rule the rest of this repository is held to, on this page too."""
    assert "0원이라는 뜻이 아니라" in korean


def test_grouping_repeated_notes_names_every_run_place_it_collapsed():
    """Shortening the page must not lose which run place a finding came from."""
    grouped = _group_notes_by_run_place(
        [
            "host_python_process: no copy of data/x.parquet is on this machine",
            "docker_container: no copy of data/x.parquet is on this machine",
            "azure_code_interpreter: no copy of data/x.parquet is on this machine",
            "docker_container: something only this one said",
            "a line with no run place in front of it",
        ]
    )

    assert len(grouped) == 3
    shared = next(line for line in grouped if "data/x.parquet" in line)
    for environment in (
        "host_python_process",
        "docker_container",
        "azure_code_interpreter",
    ):
        assert environment in shared
    assert "[docker_container] something only this one said" in grouped
    assert "a line with no run place in front of it" in grouped


def test_a_state_this_file_has_no_korean_for_is_shown_rather_than_hidden(report):
    """An unknown state must not silently render as nothing.

    The readiness grades are defined in core/, not here. If one is added, this
    file will not know its Korean name -- and printing the raw name is the
    only honest option. Dropping the line, or defaulting it to something
    reassuring, would misreport a run place.
    """
    damaged = json.loads(json.dumps(report))
    compared = damaged["readiness"]["compared_environments"][0]
    for entry in damaged["readiness"]["environments"]:
        if entry["environment"] == compared:
            entry["status"] = "some_state_invented_after_this_file_was_written"

    text = summarise(damaged)

    assert "some_state_invented_after_this_file_was_written" in text
    assert "한국어 설명 없음" in text


# ── the workflow: it cannot drift into claiming access it never had ───────


@pytest.fixture(scope="module")
def workflow() -> tuple[str, dict]:
    text = WORKFLOW.read_text(encoding="utf-8")
    return _without_comments(text), yaml.safe_load(text)


def _without_comments(text: str) -> str:
    """The workflow with its whole-line comments removed.

    Searched against the executable content, because that file explains at
    length why it references no secret, wraps nothing in continue-on-error,
    and does not pass --azure-route-served -- and a search over the raw text
    finds every one of those phrases in the sentence saying it is absent.
    Only whole-line comments go, so a `#` inside a value is left alone.
    """
    return "\n".join(
        line
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )


def _steps(parsed: dict) -> dict:
    return {
        step["name"]: step
        for step in parsed["jobs"]["advance-check"]["steps"]
        if step.get("name")
    }


def test_the_workflow_is_read_only_and_references_no_secret(workflow):
    text, parsed = workflow

    assert parsed["permissions"] == {"contents": "read"}
    assert "secrets." not in text, (
        "this job's report means something only because the machine had "
        "nothing; a secret here would make it a report about a machine that "
        "did"
    )
    assert "azure/login" not in text
    assert "id-token" not in text
    assert "contents: write" not in text


def test_the_workflow_never_swallows_a_failure(workflow):
    text, parsed = workflow

    assert "continue-on-error" not in text, (
        "a check whose failures are marked as passing is not a check"
    )
    for step in parsed["jobs"]["advance-check"]["steps"]:
        assert step.get("continue-on-error") is not True


def test_the_workflow_runs_the_free_check_in_the_narrowed_mode(workflow):
    _, parsed = workflow
    command = _steps(parsed)["Run the free advance check"]["run"]

    assert "check_execution_envelope_advance_check.py" in command
    assert "--exit-on-code-and-contract-problems-only" in command
    assert "--json" in command
    # A runner's Docker service says nothing about the machine that would host
    # the real comparison.
    assert "--skip-docker-probe" in command


def test_the_workflow_does_not_assert_an_access_fact_it_cannot_measure(workflow):
    """--azure-route-served is a claim, not a probe.

    Passing `yes` would make this workflow state that somebody asked the
    project-scoped route and it answered. Nothing here asked anything.
    """
    text, _ = workflow

    assert "--azure-route-served" not in text


def test_the_credential_guard_names_every_variable_the_code_defines(workflow):
    """The guard is held to core/azure_ai_clients.py rather than to a memory.

    That module keeps these names at module scope precisely so a checker can
    read them instead of retyping them. A retyped copy agrees until somebody
    adds one -- and the one that gets added is the one that then arrives in
    this job unnoticed. Ten of them come from a tuple of static-credential
    names the module refuses to run with at all, which is why this flattens
    rather than reading the string constants alone.
    """
    text, parsed = workflow
    guard = _steps(parsed)["Verify this job was given no credentials"]["run"]

    defined = _credential_variables_the_code_names()
    assert len(defined) >= 20, (
        "core/azure_ai_clients.py names far fewer variables than it did, so "
        "this test is probably reading the wrong thing"
    )
    missing = sorted(name for name in defined if name not in guard)
    assert not missing, (
        "the workflow's credential guard does not check these, so this job "
        f"could run with them set: {missing}"
    )
    # Names only. A value printed here would be a secret in a public log.
    assert "${!name:-}" in guard
    assert "$found" in guard
    assert not any(
        f"${name}" in guard or f"${{{name}}}" in guard for name in defined
    ), "the guard expands a credential's value, which would print it in the log"


def test_the_workflow_uploads_its_evidence_even_when_the_check_fails(workflow):
    _, parsed = workflow
    upload = next(
        step
        for step in parsed["jobs"]["advance-check"]["steps"]
        if "upload-artifact" in step.get("uses", "")
    )

    assert upload["if"] == "always()"
    assert upload["with"]["if-no-files-found"] == "error"
    for name in (
        "execution_envelope_report.json",
        "execution_envelope_summary_ko.md",
        "execution_envelope_stderr.txt",
    ):
        assert name in upload["with"]["path"], name
    # The artifact is named after the tree it describes, so it can be tied to
    # a commit rather than to a date.
    assert "${{ github.sha }}" in upload["with"]["name"]


def test_the_summary_is_written_from_the_report_and_carries_the_commit(workflow):
    _, parsed = workflow
    step = _steps(parsed)["Write the Korean summary"]

    assert step["if"] == "always()"
    assert "summarise_execution_envelope_check_in_korean.py" in step["run"]
    assert '--commit "$GITHUB_SHA"' in step["run"]
    assert "$GITHUB_STEP_SUMMARY" in step["run"]


def test_the_recorded_exit_code_is_raised_and_an_absent_one_is_a_failure(
    workflow,
):
    """The deferred failure is really raised.

    The check's exit code is captured rather than allowed to end its step, so
    that the summary and the artifact are produced on a red run too. That is
    only safe if something afterwards raises it -- including when the check
    step never ran and recorded nothing.
    """
    _, parsed = workflow
    gate = _steps(parsed)["Raise the check's verdict"]

    assert gate["if"] == "always()"
    assert gate["env"]["CHECK_EXIT_CODE"] == "${{ steps.check.outputs.exit_code }}"
    assert 'if [ -z "${CHECK_EXIT_CODE:-}" ]' in gate["run"]
    assert "raise SystemExit(code)" in gate["run"]
    # A report that the summariser refused must not reach a green tick through
    # a gate that only reads offline_verdict.
    assert "execution_envelope_summary_ko.md" in gate["run"]


def test_the_gate_refuses_a_check_that_contradicted_itself(workflow):
    """Exit 1 from a traceback and exit 1 from a fault look identical.

    What separates them is whether a readable report naming problems came
    with it, so the gate checks the pair rather than the code alone.
    """
    _, parsed = workflow
    gate = _steps(parsed)["Raise the check's verdict"]["run"]

    assert "code == 0 and problems" in gate
    assert "code != 0 and not problems" in gate
    assert "left no readable report" in gate


def test_the_workflow_pins_the_python_the_license_evaluator_requires(workflow):
    """core/agentic_v2_license.py compares this against sys.version_info."""
    from core.agentic_v2_license import LICENSE_EVALUATOR_PYTHON_VERSION

    _, parsed = workflow
    setup = next(
        step
        for step in parsed["jobs"]["advance-check"]["steps"]
        if "setup-python" in step.get("uses", "")
    )

    assert setup["with"]["python-version"] == LICENSE_EVALUATOR_PYTHON_VERSION


def test_every_action_is_pinned_to_a_commit(workflow):
    import re

    text, parsed = workflow
    for step in parsed["jobs"]["advance-check"]["steps"]:
        uses = step.get("uses")
        if uses:
            assert re.search(r"@[0-9a-f]{40}$", uses), uses


def test_the_trigger_is_wide_enough_that_the_job_actually_starts(workflow):
    """A filter narrowed to the envelope's own files would gate nothing.

    The check imports core/, and its verdict depends on constants elsewhere in
    the package -- the pinned API version lives in core/config.py. Measured
    precedent: #392 changed repo-root scripts/ while backend-tests.yml did not
    list that path, and the job that would have caught it never woke up.
    """
    _, parsed = workflow
    triggers = parsed.get("on", parsed.get(True))

    assert "workflow_dispatch" in triggers
    for event in ("pull_request", "push"):
        paths = triggers[event]["paths"]
        assert "batch-runner/**" in paths, event
        assert (
            ".github/workflows/execution-envelope-preflight.yml" in paths
        ), event
    assert triggers["push"]["branches"] == ["main"]


def test_the_tests_holding_this_workflow_are_themselves_reachable():
    """This file must run when the workflow it asserts about is edited.

    These tests are run by backend-tests.yml, whose path filter did not list
    .github/workflows/. A pull request editing only the workflow -- adding
    --azure-route-served, say -- would have started no run of this file, and
    every assertion above would have been decoration.
    """
    backend = yaml.safe_load(
        (REPOSITORY_ROOT / ".github/workflows/backend-tests.yml").read_text(
            encoding="utf-8"
        )
    )
    triggers = backend.get("on", backend.get(True))

    for event in ("pull_request", "push"):
        assert (
            ".github/workflows/execution-envelope-preflight.yml"
            in triggers[event]["paths"]
        ), (
            f"backend-tests.yml does not run on {event} for the workflow this "
            "file asserts about, so these assertions gate nothing"
        )


# ── the fixed conditions the free check cannot see for itself ─────────────
#
# Requirement: a code-level regression of a fixed condition must turn CI red.
# Fourteen regressions were applied one at a time and measured against three
# places: the free check, the existing envelope suite, and this file. Every one
# is caught somewhere. Two are caught *only* here -- reordering the shared
# prompt's sections, and rewording it so a sentence is true in one run place
# and false in another -- and those two are why this section exists. The third
# guard below is redundant with the free check and says so in its own words;
# it stays for readability, not for coverage.
#
# They are asserted here rather than added to the check because the shared
# prompt lives under batch-runner/prompts/, which is inside the grader source
# hash: a change there freezes any grading run in flight. A test reads the file
# without moving it.


ENVELOPE_SETTINGS = (
    "exp030_envelope_host_python_process.yaml",
    "exp031_envelope_docker_container.yaml",
    "exp032_envelope_azure_code_interpreter.yaml",
)


@pytest.mark.parametrize("settings_file", ENVELOPE_SETTINGS)
def test_every_run_place_is_still_opted_in_to_the_one_shared_request(
    settings_file,
):
    """One switch un-does the whole equalisation. Said plainly, beside the rest.

    ``shared_first_request`` is off by default, and with it off a run place
    loads the prompt file its own runner class prefers -- which is how the
    three came to differ by 3,774 characters in the first place.

    This one is deliberately not closing a gap: the free check already refuses
    a settings file with this off, and so does the existing envelope suite.
    Measured, six ways -- off and removed entirely, in each of the three files
    -- and every one of the six went red in both. An earlier sweep of mine
    reported the opposite, and it was wrong: the pattern it edited matched a
    comment above the setting rather than the setting, so nothing was ever
    flipped. That is the reason this docstring names its numbers.

    It stays because it is the only place that says which value is required,
    in one line, next to the prompt pins it belongs with. The check says it in
    a paragraph of arithmetic about first requests.
    """
    settings = yaml.safe_load(
        (
            BATCH_RUNNER_ROOT / "experiments" / "execution_envelope" / settings_file
        ).read_text(encoding="utf-8")
    )

    execution = settings.get("execution") or {}
    assert execution.get("shared_first_request") is True, (
        f"{settings_file} no longer opts in to the one shared first request, "
        "so this run place would send a prompt the other two do not"
    )


def test_the_shared_prompt_still_names_exactly_the_agreed_sections():
    """Adding a forbidden section is refused; the order between them was not.

    ``shared_section_order`` already refuses a section only the container can
    build, so the list cannot grow into an asymmetry, and dropping
    ``available_files_any_run_place`` is caught by the existing envelope suite.
    What nothing held was the order. Measured: swapping ``file_structure`` and
    ``task`` left the free check green with zero problems and the existing
    suite green -- all three run places would have gone on agreeing with each
    other while sending the task in a different shape than the one that was
    agreed, and nothing would have said so.

    Both halves are pinned here rather than only the order, so the list and its
    order are read in one place.
    """
    from core.shared_first_request import (
        SECTIONS_EVERY_RUN_PLACE_CAN_BUILD,
        shared_prompt_data,
        shared_section_order,
    )

    order = shared_section_order(shared_prompt_data())

    assert order == [
        "file_structure",
        "task",
        "previews",
        "available_files_any_run_place",
    ], (
        "the shared prompt's section list changed. Every run place assembles "
        "this list, so a change here changes what all three send -- which is "
        "allowed, but only deliberately, and this pin is what makes it "
        "deliberate"
    )
    assert set(order) == set(SECTIONS_EVERY_RUN_PLACE_CAN_BUILD), (
        "the list and the set of sections every run place can build have "
        "drifted apart"
    )


def test_the_shared_prompt_says_the_same_thing_it_said_when_it_was_agreed():
    """A sentence true in one run place and false in another is a difference.

    The prompt file says so itself: it is why it names no container, no
    /mnt/data and no current directory. Nothing enforced it. Measured:
    rewording the system_message to say "working inside a Docker container"
    left the free check green with zero problems and the suite green, and the
    comparison would have gone ahead sending the Azure and host run places a
    sentence that is false where they run.

    Wording cannot be checked mechanically, so this pins the digest instead --
    using the same function the run records per run place, so this pin and the
    run's own record are the same measurement. A deliberate edit updates the
    value here and says why in the message; an accidental one stops.
    """
    from core.shared_first_request import first_request_fingerprint, shared_prompt_data

    prompt = shared_prompt_data()

    assert (
        first_request_fingerprint(prompt["system_message"], prompt["user_prompt"])
        == "82a9105cc4dc644a"
    ), (
        "the shared prompt's wording changed. All three run places send this "
        "text, so a change is not automatically wrong -- but every sentence in "
        "it has to be true in all three places at once, and that is a judgement "
        "somebody has to make rather than something a check can make. Re-read "
        "it against that rule, then update this value"
    )


def _scripts_the_workflow_runs(workflow_text: str) -> list[str]:
    """Every ``scripts/...py`` path named in the workflow's shell steps.

    Read out of the file rather than listed here, so a step added later is
    covered without anybody remembering to come back.
    """
    return sorted(set(re.findall(r"scripts/[\w./-]+\.py", workflow_text)))


def test_the_workflow_names_at_least_the_two_scripts_it_is_built_around(workflow):
    """Guards the extraction above, which would otherwise fail open.

    A regex that stops matching finds nothing, and a loop over nothing passes.
    The next test would then report every script as tracked while looking at
    none of them.
    """
    text, _ = workflow
    found = _scripts_the_workflow_runs(text)

    assert CHECK.name in " ".join(found), (
        f"the workflow no longer names {CHECK.name}, so either the job stopped "
        "running the check or the way this file finds it stopped working"
    )
    assert SUMMARISE.name in " ".join(found), (
        f"the workflow no longer names {SUMMARISE.name}"
    )


def test_every_script_the_workflow_runs_is_actually_in_the_repository(workflow):
    """A workflow may only call files git agreed to carry.

    ``.gitignore`` ignores all of ``batch-runner/scripts/`` and re-admits
    individual files by name. A new script is therefore invisible by default:
    ``git add -A`` skips it without a word, the branch looks complete, and the
    job dies on the runner at the step that reads the report -- reporting a
    missing summariser as an unreadable report, which sends the reader to the
    wrong problem entirely.

    Measured on this very branch: the summariser was written, tested, wired
    into the workflow, and was not in ``git status`` at all.

    Asks git what is tracked rather than reading the allowlist, because the
    allowlist is the thing that goes stale.
    """
    text, _ = workflow

    for relative in _scripts_the_workflow_runs(text):
        script = BATCH_RUNNER_ROOT / relative
        assert script.exists(), (
            f"the workflow runs {relative}, which is not in this checkout"
        )

        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(script)],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, (
            f"the workflow runs {relative}, but git is not tracking it, so a "
            "clone of this repository does not have it and the job cannot "
            "run. If it is under an ignored directory, add a '!' line for it "
            f"in .gitignore. git said: {tracked.stderr.strip()!r}"
        )
