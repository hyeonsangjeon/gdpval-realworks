"""The free gate must not green-light the Azure run place from a setting alone.

``scripts/check_execution_environment_readiness.py`` answers one question:
"may the execution-environment comparison start, and if not, what exactly is
missing?" Its exit code is meant to stand in front of a paid run.

For the Azure run place it used to answer that question by reading
``AZURE_AI_ROUTE_PROFILE`` and comparing it to a string. If the two matched,
the verdict was :data:`STATUS_CAN_RUN_REAL_EXPERIMENT`, whose own docstring
reads "A real experiment can be started here today."

exp032 disproved that twice. GitHub runs 33464316741 and 33468138329 both had
the profile set to exactly the required value, and neither could start: ten
calls, ten ``PermissionDeniedError (http 403)`` from the project-scoped
Responses route, zero responses served.

The setting was never evidence. It names the route the mode must use, and
``step2_run_inference._require_code_interpreter_route_profile`` refuses the
mode without it, so a real dispatch cannot help but have it set. The one input
the grade depended on is therefore always present in the only situation where
the grade matters.

Nothing in this file calls a model, contacts a provider, or spends money.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

from core.execution_environment_readiness import (
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_DOCKER_CONTAINER,
    STATUS_BLOCKED_REQUIREMENT_UNMET,
    STATUS_CAN_RUN_REAL_EXPERIMENT,
    STATUS_EVIDENCE_INSUFFICIENT,
    build_readiness_report,
    inspect_environment_support,
)
import core.execution_environment_readiness as readiness
import core.execution_envelope_preflight as preflight

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROUTE = "project-ci"


def _azure(entries) -> object:
    for entry in entries:
        if entry.environment == ENVIRONMENT_AZURE_CODE_INTERPRETER:
            return entry
    raise AssertionError("the Azure run place was not graded at all")


# ── The defect itself ──────────────────────────────────────────────────────


def test_the_required_route_setting_alone_is_not_a_green_light():
    """The exact call that used to return "can start today" for exp032.

    Both failing runs would have produced these arguments, because the profile
    is the value a Code Interpreter dispatch is required to set before it may
    run at all.
    """
    entry = _azure(inspect_environment_support(azure_route_profile=REQUIRED_ROUTE))

    assert entry.status != STATUS_CAN_RUN_REAL_EXPERIMENT
    assert entry.status == STATUS_EVIDENCE_INSUFFICIENT


def test_an_unmeasured_route_says_so_in_words_the_operator_can_act_on():
    entry = _azure(inspect_environment_support(azure_route_profile=REQUIRED_ROUTE))

    assert any("nobody checked" in note for note in entry.blockers), entry.blockers
    assert any(
        "names the route to use" in note for note in entry.blockers
    ), entry.blockers


def test_a_route_that_refused_is_blocked_rather_than_merely_unmeasured():
    """exp032's actual state, once somebody has looked.

    "Not measured" and "measured, and it said no" are different answers and
    the report must not collapse them: the first is a gap in the check, the
    second is a finding about the account.
    """
    entry = _azure(
        inspect_environment_support(
            azure_route_profile=REQUIRED_ROUTE, azure_route_served=False
        )
    )

    assert entry.status == STATUS_BLOCKED_REQUIREMENT_UNMET
    assert any("refused this sign-in" in note for note in entry.blockers)


def test_a_route_that_answered_is_the_only_way_to_a_green_light():
    entry = _azure(
        inspect_environment_support(
            azure_route_profile=REQUIRED_ROUTE, azure_route_served=True
        )
    )

    assert entry.status == STATUS_CAN_RUN_REAL_EXPERIMENT
    assert any("was observed to answer" in note for note in entry.evidence)


def test_an_answering_route_does_not_excuse_the_wrong_route_setting():
    """The two inputs are read in order and neither substitutes for the other.

    Observing that *some* route answers says nothing about a run configured to
    use a different one.
    """
    entry = _azure(
        inspect_environment_support(
            azure_route_profile="direct", azure_route_served=True
        )
    )

    assert entry.status == STATUS_BLOCKED_REQUIREMENT_UNMET


def test_an_answering_route_does_not_excuse_a_missing_route_setting():
    entry = _azure(inspect_environment_support(azure_route_served=True))

    assert entry.status == STATUS_EVIDENCE_INSUFFICIENT


# ── The same standard the container run place is already held to ───────────


def test_both_run_places_answer_not_measured_when_nobody_looked():
    """The asymmetry this change removes.

    ``_grade_docker_container`` has always read whether Docker is actually
    running on this machine and answered "not measured" when nobody looked.
    The Azure grade had no such input at all, so two run places inside one
    comparison were held to different standards — and the one with the lower
    standard is the one that costs money to be wrong about.
    """
    entries = inspect_environment_support(
        azure_route_profile=REQUIRED_ROUTE, docker_run_setting="always"
    )
    graded = {entry.environment: entry.status for entry in entries}

    assert graded[ENVIRONMENT_DOCKER_CONTAINER] == STATUS_EVIDENCE_INSUFFICIENT
    assert graded[ENVIRONMENT_AZURE_CODE_INTERPRETER] == STATUS_EVIDENCE_INSUFFICIENT


def test_the_azure_grade_takes_a_measurement_argument_at_all():
    """A signature-level lock, because dropping the argument would pass silently.

    Deleting ``azure_route_served`` from the grade and from every caller leaves
    a module that imports, runs, and green-lights on the setting again. The
    behaviour tests above would catch that, but only while they exist; this
    states the contract itself.
    """
    parameters = inspect.signature(
        readiness._grade_azure_code_interpreter
    ).parameters

    assert "azure_route_served" in parameters
    assert parameters["azure_route_served"].kind is inspect.Parameter.KEYWORD_ONLY


# ── The whole report, and the check standing in front of the money ─────────


def test_the_report_is_not_ready_while_the_route_is_unmeasured():
    report = build_readiness_report(
        conditions_by_environment=None,
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="always",
        azure_route_profile=REQUIRED_ROUTE,
        environ={readiness.PAID_RUN_APPROVAL_VARIABLE: "yes"},
    )

    assert report.ready is False
    assert ENVIRONMENT_AZURE_CODE_INTERPRETER in report.blocked_environments
    assert (
        report.status_of(ENVIRONMENT_AZURE_CODE_INTERPRETER)
        == STATUS_EVIDENCE_INSUFFICIENT
    )


def test_the_report_forwards_the_measurement():
    report = build_readiness_report(
        conditions_by_environment=None,
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="always",
        azure_route_profile=REQUIRED_ROUTE,
        azure_route_served=True,
        environ={readiness.PAID_RUN_APPROVAL_VARIABLE: "yes"},
    )

    assert (
        report.status_of(ENVIRONMENT_AZURE_CODE_INTERPRETER)
        == STATUS_CAN_RUN_REAL_EXPERIMENT
    )


def test_the_envelope_preflight_can_pass_the_measurement_through():
    """The paid run's own gate reaches the same grade the free tool does."""
    parameters = inspect.signature(preflight.run_envelope_preflight).parameters

    assert "azure_route_served" in parameters
    assert parameters["azure_route_served"].default is None


def test_the_advance_check_offers_the_same_opt_in_as_the_readiness_tool():
    """Two commands stand in front of this comparison and both must agree.

    ``check_execution_envelope_advance_check.py`` is the gate for the five-task
    advance check — the one immediately before money is spent. Closing the
    fail-open only in the other command would leave this one unable to report a
    route anybody has actually seen answer, which is the opposite failure: a run
    place that can never be cleared even after the account is fixed.
    """
    finished = subprocess.run(
        [
            sys.executable,
            "scripts/check_execution_envelope_advance_check.py",
            "--help",
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert finished.returncode == 0
    assert "--azure-route-served" in finished.stdout
    assert "AZURE_AI_ROUTE_PROFILE is not an answer" in " ".join(
        finished.stdout.split()
    )


def _run_the_tool(*extra: str, route_profile: str | None = None) -> dict:
    """Run the free tool and return the grade it gave each run place.

    The paid-run approval is set because without it every run place that could
    otherwise start is demoted to ``blocked_requirement_unmet``, which would
    hide the difference these tests are about. Nothing here calls a model; the
    variable is only read by the readiness grading. The approval axis is
    covered separately by
    ``test_no_run_place_is_ready_while_paid_calls_are_unapproved``.
    """
    environ = dict(os.environ)
    environ.pop("AZURE_AI_ROUTE_PROFILE", None)
    environ[readiness.PAID_RUN_APPROVAL_VARIABLE] = "yes"
    if route_profile is not None:
        environ["AZURE_AI_ROUTE_PROFILE"] = route_profile
    finished = subprocess.run(
        [
            sys.executable,
            "scripts/check_execution_environment_readiness.py",
            "--skip-docker-probe",
            "--json",
            *extra,
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env=environ,
    )
    assert finished.stdout, finished.stderr
    payload = json.loads(finished.stdout)
    return {
        entry["environment"]: entry["status"] for entry in payload["environments"]
    }


def test_the_tool_does_not_green_light_the_route_from_the_environment_variable():
    """End to end, through the command an operator actually runs.

    This is the shape of the original finding: setting one environment
    variable to one string was enough to move the Azure run place to "a real
    experiment can be started here today", with the paid-run approval already
    in hand — which is exactly the state a dispatch is in.
    """
    graded = _run_the_tool(route_profile=REQUIRED_ROUTE)

    assert graded[ENVIRONMENT_AZURE_CODE_INTERPRETER] == STATUS_EVIDENCE_INSUFFICIENT


def test_the_tool_reports_a_refused_route_as_blocked():
    graded = _run_the_tool("--azure-route-served", "no", route_profile=REQUIRED_ROUTE)

    assert (
        graded[ENVIRONMENT_AZURE_CODE_INTERPRETER] == STATUS_BLOCKED_REQUIREMENT_UNMET
    )


def test_the_tool_accepts_an_observed_route():
    graded = _run_the_tool("--azure-route-served", "yes", route_profile=REQUIRED_ROUTE)

    assert (
        graded[ENVIRONMENT_AZURE_CODE_INTERPRETER] == STATUS_CAN_RUN_REAL_EXPERIMENT
    )


def test_the_tool_leaves_the_measurement_out_by_default():
    """No probe exists, so silence must mean silence.

    The container run place is measured by default and opts *out* with
    ``--skip-docker-probe``. There is no equivalent probe for an Azure
    authorization decision, so this one opts *in*, and the default has to be
    the honest answer rather than the convenient one.
    """
    graded = _run_the_tool()

    assert graded[ENVIRONMENT_AZURE_CODE_INTERPRETER] == STATUS_EVIDENCE_INSUFFICIENT


def test_the_flag_tells_the_operator_that_the_route_profile_is_not_an_answer():
    finished = subprocess.run(
        [
            sys.executable,
            "scripts/check_execution_environment_readiness.py",
            "--help",
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert finished.returncode == 0
    assert "--azure-route-served" in finished.stdout
    assert "AZURE_AI_ROUTE_PROFILE is not an answer" in " ".join(
        finished.stdout.split()
    )


# ── What this change does not claim ────────────────────────────────────────


def test_the_measurement_is_operator_supplied_and_the_code_says_so():
    """An honest limit, stated where it cannot drift out of the PR text.

    This change does not prove the project-scoped route works. No live
    authorization probe ships here, because one cannot be exercised from the
    machine this suite runs on — a different tenant — and an untested network
    probe standing in front of a paid run would be worse than none.

    What it does is stop the check from claiming the route works on its own
    evidence. The default moved from optimistic to unmeasured, so the green
    light can no longer be obtained by accident from a variable that a real
    dispatch is required to set anyway.
    """
    doc = inspect.getdoc(readiness.inspect_environment_support) or ""

    assert "azure_route_served" in doc
    assert "observation" in doc
