"""The free Azure check must apply the rules the paid run really applies.

``core/execution_envelope_azure.py`` is the last gate before the run-place
comparison spends anything: whatever it reports flows straight into whether the
comparison may start. Its own file says a plan checked there is checked against
the rules the real run applies, and until this file existed nothing measured
whether that was so.

It was not so. Sweeping seventeen Azure settings one at a time and comparing
what the free check said against what ``AzureAIRouteSettings.from_env`` did,
seven disagreed, and six of the seven disagreed in the direction that costs
money: the free check handed out a clean bill of health for a setting the run
refuses to start with. Three were identity settings the run demands and the
check never looked at; three more were identity settings the run compares
against the endpoint and the check never compared.

So these tests do not read the code and agree with it. They set a setting, ask
both sides, and require the same answer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core import azure_ai_clients
from core.azure_ai_clients import AzureAIRouteSettings
from core.execution_envelope_azure import (
    AzureConnectionRequirement,
    describe_expected_project_endpoint,
    diagnose_azure_connection,
)

ACCOUNT = "hjeon-fdpo-foundry-eus2"
PROJECT = "gdpval-realworks"
ANOTHER_ACCOUNT = "some-other-account"
ANOTHER_PROJECT = "some-other-project"

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def requirement() -> AzureConnectionRequirement:
    return AzureConnectionRequirement.from_mapping(
        {
            "account": ACCOUNT,
            "project": PROJECT,
            "route_profile": "project-ci",
        }
    )


def _settings(**changes: str | None) -> dict[str, str]:
    """A correct set of Azure settings, with the named ones changed or removed.

    The starting point is what the automated run place sets: the profile, the
    two endpoints, the switch that turns identity pinning on, and the three
    names that pinning compares.
    """
    values = {
        "AZURE_AI_ROUTE_PROFILE": "project-ci",
        "FOUNDRY_PROJECT_ENDPOINT": (
            f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"
        ),
        "AZURE_OPENAI_V1_ENDPOINT": (
            f"https://{ACCOUNT}.services.ai.azure.com/openai/v1/"
        ),
        "AZURE_AI_REQUIRE_EXPECTED_IDENTITIES": "1",
        "AZURE_AI_EXPECTED_DIRECT_ACCOUNT": ACCOUNT,
        "AZURE_AI_EXPECTED_PROJECT_ACCOUNT": ACCOUNT,
        "AZURE_AI_EXPECTED_PROJECT_NAME": PROJECT,
    }
    for name, value in changes.items():
        if value is None:
            values.pop(name, None)
        else:
            values[name] = value
    return values


def _the_run_refuses(settings: dict[str, str]) -> bool:
    """What the paid run does with these settings, asked rather than assumed."""
    try:
        AzureAIRouteSettings.from_env(settings)
    except ValueError:
        return True
    return False


# ── The settings a correct run already had ────────────────────────────────


def test_a_correct_set_of_settings_has_no_problems(requirement) -> None:
    diagnosis = diagnose_azure_connection(requirement, _settings())
    assert diagnosis.problems == []
    assert diagnosis.reachable_intent is True
    assert diagnosis.observed_account == ACCOUNT
    assert diagnosis.observed_project == PROJECT


def test_the_address_the_check_describes_is_the_address_it_accepts(
    requirement,
) -> None:
    """The written-out address and the accepted address must be the same one.

    The check tells a reader which address to set when it is missing. If that
    sentence and the rule that accepts an address ever part company, the check
    sends people to fix it in a way it will still refuse.
    """
    described = describe_expected_project_endpoint(requirement)
    diagnosis = diagnose_azure_connection(
        requirement, _settings(FOUNDRY_PROJECT_ENDPOINT=described)
    )
    assert diagnosis.problems == []


def test_an_unset_route_profile_is_refused(requirement) -> None:
    settings = _settings(AZURE_AI_ROUTE_PROFILE=None)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any("AZURE_AI_ROUTE_PROFILE" in note for note in diagnosis.problems)
    assert _the_run_refuses(settings)


def test_the_deprecated_endpoint_setting_is_refused(requirement) -> None:
    settings = _settings(
        AZURE_OPENAI_ENDPOINT=f"https://{ACCOUNT}.openai.azure.com/"
    )
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(
        "AZURE_OPENAI_ENDPOINT is set" in note for note in diagnosis.problems
    )
    assert _the_run_refuses(settings)


def test_an_endpoint_naming_another_account_is_refused(requirement) -> None:
    settings = _settings(
        FOUNDRY_PROJECT_ENDPOINT=(
            f"https://{ANOTHER_ACCOUNT}.services.ai.azure.com"
            f"/api/projects/{PROJECT}"
        )
    )
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(ANOTHER_ACCOUNT in note for note in diagnosis.problems)


def test_an_endpoint_naming_another_project_is_refused(requirement) -> None:
    settings = _settings(
        FOUNDRY_PROJECT_ENDPOINT=(
            f"https://{ACCOUNT}.services.ai.azure.com"
            f"/api/projects/{ANOTHER_PROJECT}"
        )
    )
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(ANOTHER_PROJECT in note for note in diagnosis.problems)


# ── The lists are read from the run place, not copied from it ─────────────


def test_a_credential_the_run_starts_refusing_is_refused_here_too(
    requirement, monkeypatch
) -> None:
    """Adding a name to the run's list must not leave this check behind.

    This check used to hold its own typed-out copy of the ten fixed credentials
    the repository refuses to run with. The copy was correct on the day it was
    typed. Adding an eleventh name to the real list left the run refusing to
    start while this check reported no problems at all — a clean bill of health
    for the exact setting that stops the run.
    """
    monkeypatch.setattr(
        azure_ai_clients,
        "FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV",
        azure_ai_clients.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
        + ("AZURE_TENANT_PASSWORD",),
    )
    settings = _settings(AZURE_TENANT_PASSWORD="a-fixed-credential")

    assert _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(
        "AZURE_TENANT_PASSWORD" in note for note in diagnosis.problems
    ), diagnosis.problems


@pytest.mark.parametrize(
    "name",
    [
        "AZURE_OPENAI_API_KEY",
        "AZURE_CLIENT_SECRET",
        "AZURE_PASSWORD",
    ],
)
def test_each_fixed_credential_the_run_refuses_is_refused_here(
    requirement, name
) -> None:
    settings = _settings(**{name: "a-fixed-credential"})
    assert _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(name in note for note in diagnosis.problems)


def test_the_setting_names_are_read_from_the_run_place(
    requirement, monkeypatch
) -> None:
    """Renaming a setting in the run place renames it here.

    A name typed out again here would keep the old spelling and quietly stop
    matching anything, which reads as "the setting is not set" for a setting
    that is.
    """
    monkeypatch.setattr(
        azure_ai_clients, "PROJECT_ENDPOINT_ENV", "FOUNDRY_PROJECT_ADDRESS"
    )
    settings = _settings(FOUNDRY_PROJECT_ENDPOINT=None)
    settings["FOUNDRY_PROJECT_ADDRESS"] = (
        f"https://{ACCOUNT}.services.ai.azure.com/api/projects/{PROJECT}"
    )

    diagnosis = diagnose_azure_connection(requirement, settings)
    assert diagnosis.problems == []
    assert diagnosis.observed_account == ACCOUNT


def test_a_requirement_the_plan_cannot_answer_is_reported_not_ignored(
    requirement, monkeypatch
) -> None:
    """A new identity setting with nothing to compare it against must be said.

    Passing quietly over a requirement nobody has pinned would be this file's
    own fault happening again one layer along.
    """
    monkeypatch.setattr(
        azure_ai_clients,
        "REQUIRED_IDENTITY_ENV_BY_PROFILE",
        {
            **azure_ai_clients.REQUIRED_IDENTITY_ENV_BY_PROFILE,
            "project-ci": (
                *azure_ai_clients.REQUIRED_IDENTITY_ENV_BY_PROFILE[
                    "project-ci"
                ],
                "AZURE_AI_EXPECTED_REGION",
            ),
        },
    )
    diagnosis = diagnose_azure_connection(
        requirement, _settings(AZURE_AI_EXPECTED_REGION="eastus2")
    )
    assert any(
        "AZURE_AI_EXPECTED_REGION" in note for note in diagnosis.problems
    ), diagnosis.problems


def test_every_identity_the_run_requires_has_something_to_compare_against(
    requirement,
) -> None:
    """No setting in the real table falls into the "cannot answer" branch.

    Written as a test rather than a comment so that adding a name to the run
    place without pinning it in the plan is reported here as work still to do.
    """
    diagnosis = diagnose_azure_connection(requirement, _settings())
    assert not any(
        "says nothing this check can compare" in note
        for note in diagnosis.problems
    ), diagnosis.problems


# ── Identity pinning is applied before the money, not after ───────────────


@pytest.mark.parametrize(
    "missing",
    [
        "AZURE_AI_EXPECTED_DIRECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_ACCOUNT",
        "AZURE_AI_EXPECTED_PROJECT_NAME",
    ],
)
def test_an_identity_the_run_demands_is_demanded_here(
    requirement, missing
) -> None:
    """The run refuses to start without these, so this must refuse first."""
    settings = _settings(**{missing: None})
    assert _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(missing in note for note in diagnosis.problems), (
        diagnosis.problems
    )


@pytest.mark.parametrize(
    "name, wrong_value",
    [
        ("AZURE_AI_EXPECTED_DIRECT_ACCOUNT", ANOTHER_ACCOUNT),
        ("AZURE_AI_EXPECTED_PROJECT_ACCOUNT", ANOTHER_ACCOUNT),
        ("AZURE_AI_EXPECTED_PROJECT_NAME", ANOTHER_PROJECT),
    ],
)
def test_an_identity_naming_another_resource_is_refused(
    requirement, name, wrong_value
) -> None:
    """These are the settings the plan says it agrees with, now compared.

    The plan pins one account and one project and says in writing that they are
    the two the repository already records for its automated runs. Nothing
    compared the two until this test.
    """
    settings = _settings(**{name: wrong_value})
    assert _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(
        name in note and wrong_value in note for note in diagnosis.problems
    ), diagnosis.problems


def test_the_identities_are_demanded_even_when_the_local_switch_is_off(
    requirement,
) -> None:
    """On purpose stricter than one run of the run place, and never looser.

    ``AzureAIRouteSettings.from_env`` demands the identity settings only when
    the switch is on. Every automated run place in this repository that can
    spend money turns it on, so a local switch that is off describes a rule the
    paid run will not follow. Refusing before the start beats stopping after
    it.
    """
    settings = _settings(
        AZURE_AI_REQUIRE_EXPECTED_IDENTITIES="0",
        AZURE_AI_EXPECTED_PROJECT_NAME=None,
    )
    assert not _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any(
        "AZURE_AI_EXPECTED_PROJECT_NAME" in note
        for note in diagnosis.problems
    ), diagnosis.problems


def test_an_account_written_in_capitals_is_the_same_account(
    requirement,
) -> None:
    """The run folds account names to lower case, so this must not object."""
    settings = _settings(AZURE_AI_EXPECTED_PROJECT_ACCOUNT=ACCOUNT.upper())
    assert not _the_run_refuses(settings)
    assert diagnose_azure_connection(requirement, settings).problems == []


def test_a_project_written_in_capitals_is_a_different_project(
    requirement,
) -> None:
    """The run does not fold project names, so a capital is a difference."""
    settings = _settings(AZURE_AI_EXPECTED_PROJECT_NAME=PROJECT.upper())
    assert _the_run_refuses(settings)
    assert diagnose_azure_connection(requirement, settings).problems


def test_a_plan_pinning_a_profile_the_run_does_not_know_is_refused() -> None:
    """A profile the run place cannot read stops it whatever else is right."""
    requirement = AzureConnectionRequirement.from_mapping(
        {
            "account": ACCOUNT,
            "project": PROJECT,
            "route_profile": "project-ci-v2",
        }
    )
    settings = _settings(AZURE_AI_ROUTE_PROFILE="project-ci-v2")
    assert _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any("project-ci-v2" in note for note in diagnosis.problems)


# ── The measurement itself, kept as a test ────────────────────────────────

AGREEMENT_CASES = [
    ("everything correct", _settings()),
    ("the profile is not set", _settings(AZURE_AI_ROUTE_PROFILE=None)),
    ("the profile is unreadable", _settings(AZURE_AI_ROUTE_PROFILE="nonsense")),
    (
        "the deprecated endpoint is set",
        _settings(AZURE_OPENAI_ENDPOINT=f"https://{ACCOUNT}.openai.azure.com/"),
    ),
    ("the project endpoint is not set", _settings(FOUNDRY_PROJECT_ENDPOINT=None)),
    (
        "the project endpoint names another account",
        _settings(
            FOUNDRY_PROJECT_ENDPOINT=(
                f"https://{ANOTHER_ACCOUNT}.services.ai.azure.com"
                f"/api/projects/{PROJECT}"
            )
        ),
    ),
    (
        "the direct endpoint names another account",
        _settings(
            AZURE_OPENAI_V1_ENDPOINT=(
                f"https://{ANOTHER_ACCOUNT}.services.ai.azure.com/openai/v1/"
            )
        ),
    ),
    ("a fixed credential is set", _settings(AZURE_OPENAI_API_KEY="x")),
    (
        "the expected direct account is not set",
        _settings(AZURE_AI_EXPECTED_DIRECT_ACCOUNT=None),
    ),
    (
        "the expected project account is not set",
        _settings(AZURE_AI_EXPECTED_PROJECT_ACCOUNT=None),
    ),
    (
        "the expected project name is not set",
        _settings(AZURE_AI_EXPECTED_PROJECT_NAME=None),
    ),
    (
        "the expected direct account names another account",
        _settings(AZURE_AI_EXPECTED_DIRECT_ACCOUNT=ANOTHER_ACCOUNT),
    ),
    (
        "the expected project account names another account",
        _settings(AZURE_AI_EXPECTED_PROJECT_ACCOUNT=ANOTHER_ACCOUNT),
    ),
    (
        "the expected project name names another project",
        _settings(AZURE_AI_EXPECTED_PROJECT_NAME=ANOTHER_PROJECT),
    ),
    (
        "the expected project name differs only in capitals",
        _settings(AZURE_AI_EXPECTED_PROJECT_NAME=PROJECT.upper()),
    ),
    (
        "the expected project account differs only in capitals",
        _settings(AZURE_AI_EXPECTED_PROJECT_ACCOUNT=ACCOUNT.upper()),
    ),
]


@pytest.mark.parametrize(
    "label, settings",
    AGREEMENT_CASES,
    ids=[label for label, _ in AGREEMENT_CASES],
)
def test_the_free_check_and_the_paid_run_reach_the_same_verdict(
    requirement, label, settings
) -> None:
    """Every setting, one at a time: both sides must say the same word.

    The one setting deliberately left out of this sweep is the profile being
    ``direct-v1``. The run place builds that route happily; the comparison
    refuses it because the comparison is pinned to ``project-ci``. That
    disagreement is the point of pinning, and the test below states it.
    """
    free_refuses = bool(
        diagnose_azure_connection(requirement, settings).problems
    )
    assert free_refuses == _the_run_refuses(settings), label


def test_the_one_place_the_check_is_stricter_on_purpose(requirement) -> None:
    """Pinned to project-ci, so a route the run would build is still refused.

    Written down rather than left as a surprise: this is the single setting
    where the free check and the run place part company, and it parts company
    in the direction that costs nothing.
    """
    settings = _settings(AZURE_AI_ROUTE_PROFILE="direct-v1")
    assert not _the_run_refuses(settings)
    diagnosis = diagnose_azure_connection(requirement, settings)
    assert any("project-ci" in note for note in diagnosis.problems)


# ── The fact the wording rests on ─────────────────────────────────────────


def test_every_run_place_that_can_spend_turns_identity_pinning_on() -> None:
    """The check's wording claims this, so the claim is measured here.

    The message shown when an identity setting is missing says every automated
    run place in this repository that can spend money turns the requirement on.
    That sentence is why the check demands the names regardless of the local
    switch. If a workflow ever stops setting it, this fails instead of the
    sentence quietly becoming untrue.
    """
    name = azure_ai_clients.REQUIRE_EXPECTED_IDENTITIES_ENV
    assignments: list[tuple[str, str]] = []
    for workflow in sorted((REPOSITORY_ROOT / ".github" / "workflows").glob("*.yml")):
        for line in workflow.read_text(encoding="utf-8").splitlines():
            match = re.match(rf"\s*{re.escape(name)}\s*:\s*(.+?)\s*$", line)
            if match:
                assignments.append((workflow.name, match.group(1)))

    assert assignments, f"no workflow sets {name}"
    for workflow_name, value in assignments:
        assert "'1'" in value, (
            f"{workflow_name} sets {name} to {value}, so a run there would not "
            "demand the endpoint identities"
        )
