"""The host-permissions report, held to the survey artifact it cites.

``tasks/0822_saturday/HOST_PERMISSIONS.md`` is the file an owner reads before
deciding whether to grant anything, and every number in it comes from
``boot_host_survey_widened.json``, which is committed beside it. Nothing
connected the two. The report could be edited, or the survey re-run with a
different template, and neither would notice the other.

That matters here more than it usually would, because the report is about a
**security-sensitive grant** and because its numbers have already been quoted
in two shorthands that are wrong in different ways:

* *"three permissions"* -- the superseded ``1.0`` artifact measured three
  actions. Those three are ``false`` in both artifacts, so ``1.1`` extends the
  earlier reading rather than correcting it; quoting three as the current
  figure understates the ask by nine.
* *"twelve roles"* -- a category error. Twelve is the count of **actions**.
  The roles are **two**, and the difference is the whole shape of the request:
  a reader who hears "twelve roles" imagines something far larger than two
  built-ins on one resource group.

So what this file pins is the three-way split the report has to keep straight:
**ten blocking actions**, **two conditional ones that do not drive the
verdict**, and **two roles** at **resource-group** scope. Every assertion reads
the artifact for the truth and the report for the claim. Neither is hard-coded
here, except the two counts that are the point.

Offline, free, and read-only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SURVEY_DIR = REPO_ROOT / "tasks" / "0822_saturday"
REPORT = SURVEY_DIR / "HOST_PERMISSIONS.md"
WIDENED = SURVEY_DIR / "boot_host_survey_widened.json"
NARROW = SURVEY_DIR / "boot_host_survey.json"


@pytest.fixture(scope="module")
def report() -> str:
    return REPORT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def flat(report) -> str:
    """The report with its line breaks collapsed.

    Every phrase assertion below reads this rather than the raw text. Reflowing
    a paragraph to a different width is not a change to what it says, and a
    test that fails on it teaches people to stop editing the file.
    """
    return " ".join(report.split())


@pytest.fixture(scope="module")
def answer() -> dict:
    survey = json.loads(WIDENED.read_text(encoding="utf-8"))
    return survey["findings"]["permissions"]["answer"]


def _actions_named_in(text: str) -> set[str]:
    """Every ARM action the report writes in backticks."""
    return set(re.findall(r"`(Microsoft\.[A-Za-z]+/[A-Za-z/]+(?:write|action))`", text))


def _the_requirement_tables(report: str) -> str:
    """The two tables of actions the deployment takes, and nothing else.

    Stops short of "Two things the template does **not** need", which names
    ``Microsoft.Authorization/roleAssignments/write`` precisely so that nobody
    grants it defensively. Scanning that paragraph for requirements would read
    a disclaimer as an ask.
    """
    section = report.split("## Every action the deployment would take")[1]
    return section.split("Two things the template does **not** need")[0]


# ── the split ─────────────────────────────────────────────────────────────


def test_every_blocking_action_the_survey_found_is_named_in_the_report(
    report, answer
):
    """The ten are listed, not summarised.

    An owner granting a custom role under Option B works from this table. A
    blocking action present in the survey and missing from the report would
    produce a role that is one action short, and the deployment would fail
    after the grant rather than before it.
    """
    for action in answer["blocking_actions_not_permitted"]:
        assert f"`{action}`" in report, f"{action} blocks and the report omits it"


def test_the_report_invents_no_action_the_survey_did_not_measure(report, answer):
    """The other direction, which is how a list grows stale.

    A row left behind after the template dropped a resource reads as a
    requirement and would be granted for nothing.
    """
    measured = set(answer["permits"])
    for action in _actions_named_in(_the_requirement_tables(report)):
        assert action in measured, (
            f"{action} is in the report and was never measured; either the "
            f"survey needs re-running against the current template or the row "
            f"is left over"
        )


def test_an_action_the_template_does_not_need_is_named_only_to_be_excluded(report):
    """``roleAssignments/write`` appears once, in the paragraph that rules it out.

    It is there because a cautious owner would otherwise grant it alongside the
    two roles. If it ever moved into a requirement table, the test above would
    fail for a real reason rather than this one.
    """
    disclaimer = report.split("Two things the template does **not** need")[1]
    action = "Microsoft.Authorization/roleAssignments/write"
    assert action in disclaimer
    assert action not in _actions_named_in(_the_requirement_tables(report))
    assert "SystemAssigned" in disclaimer


def test_the_two_conditionals_are_named_as_conditional_with_their_condition(
    flat, answer
):
    """Reported apart from the ask, and the reason travels with them.

    A denial on an action the deployment does not take is not a block. Listing
    these two beside the ten without their condition is how ten becomes twelve
    in the next summary that quotes it.
    """
    conditionals = answer["measured_but_not_blocking"]
    assert set(conditionals) == {
        "Microsoft.Network/publicIPAddresses/write",
        "Microsoft.Resources/subscriptions/resourceGroups/write",
    }
    for action in conditionals:
        assert f"`{action}`" in flat

    assert "attachPublicIp" in flat
    assert "defaults it to `false`" in flat
    assert "does not already exist" in flat or "does not exist" in flat


def test_the_counts_in_the_report_are_the_counts_in_the_survey(flat, answer):
    """Twelve measured, ten blocking, two conditional, two assignments held."""
    assert answer["actions_measured"] == 12
    assert len(answer["permits"]) == 12
    assert len(answer["blocking_actions_not_permitted"]) == 10
    assert len(answer["measured_but_not_blocking"]) == 2
    assert answer["assignments_held"] == 2

    assert "12 actions measured" in flat
    assert "10 of them block" in flat
    assert "Twelve actions measured; ten of them block." in flat
    assert "2 role assignments" in flat


def test_not_one_of_the_twelve_is_permitted(flat, answer):
    """The verdict rests on this, so it is asserted rather than read off prose."""
    assert set(answer["permits"].values()) == {False}
    assert answer["permits_every_action_a_deployment_would_take"] is False
    assert "**0 of 12**" in flat


# ── scope, which is what keeps the grant small ────────────────────────────


def test_every_blocking_action_is_at_resource_group_scope(flat, answer):
    """The claim that nothing needs subscription scope, checked per action.

    This is the sentence that decides how large the grant is. If one blocking
    action were ever at subscription scope, "nothing at subscription scope"
    would be false and the recommendation would have to change shape.
    """
    scopes = answer["scopes"]
    for action in answer["blocking_actions_not_permitted"]:
        assert scopes[action] == "resource_group", (
            f"{action} blocks at {scopes[action]}; the report's "
            f"resource-group-only recommendation no longer covers the ask"
        )

    at_subscription = {
        action for action, scope in scopes.items() if scope == "subscription"
    }
    assert at_subscription == {"Microsoft.Resources/subscriptions/resourceGroups/write"}
    assert at_subscription.isdisjoint(set(answer["blocking_actions_not_permitted"]))
    assert "nothing at subscription scope" in flat


# ── the two shorthands the report exists to stop ──────────────────────────


def test_the_report_says_two_roles_and_never_twelve_of_them(flat):
    """Twelve is actions. Roles are two, and the report must not blur them.

    "Twelve roles" has been said out loud about this work. It is not a rounding
    error -- it turns a request for two built-in roles on one resource group
    into something that sounds like a subscription-wide grant, which is the
    opposite of what the survey supports.
    """
    assert "**two roles**" in flat
    assert "Virtual Machine Contributor + Network Contributor" in flat
    assert not re.search(r"(twelve|12)\s+roles", flat, re.IGNORECASE)
    assert not re.search(r"(three|3)\s+roles", flat, re.IGNORECASE)


def test_the_superseded_three_action_figure_is_kept_as_history_not_as_the_answer(
    flat,
):
    """Three is quotable, because earlier write-ups cite it. It is not current.

    The narrow artifact stays committed and the report keeps its column, so the
    test is not that three has vanished -- it is that three never appears as
    the size of the ask.
    """
    assert NARROW.exists(), "the narrow artifact is cited by earlier write-ups"
    assert "**0 of 3**" in flat, "the history column is the honest place for it"
    assert "0 of 3" not in flat.split("## Every action the deployment would take")[1]


def test_the_recommended_pair_is_not_called_the_smallest_grant(flat):
    """It is not, and the report says why a few screens further down.

    Virtual Machine Contributor and Network Contributor also carry ``delete``,
    ``powerOff``, ``restart`` and extension actions the deployment never takes.
    Option B -- a custom role holding exactly the ten -- is strictly smaller.
    Labelling the pair "smallest" in the summary and "strictly smaller" in
    Option B lets an owner grant more than the survey supports while believing
    they granted the minimum.
    """
    summary = flat.split("## What is measured, and when")[0]
    assert "Recommended change" in summary
    assert "Smallest change" not in summary
    assert "strictly smaller" in flat
    assert "not for being minimal" in summary


# ── what the report must not be read as ───────────────────────────────────


def test_the_report_still_refuses_to_be_a_role_request(flat):
    """Naming the change and asking for it are different acts.

    Every other assertion in this file makes the report easier to act on, which
    is exactly the direction in which it could quietly turn into a request.
    """
    assert "It is a **report**" in flat
    assert "left undone" in flat
    assert "Not a role request" in flat
    assert "az role assignment create" in flat


def test_the_grant_is_still_the_first_of_four_gates(flat):
    """So that granting it is never reported as unblocking a real run."""
    assert "first of four gates" in flat
    for gate in ("Admission", "Activation", "`browser_run`"):
        assert gate in flat
    assert "a fixture result must never be reported as an isolation result" in flat
