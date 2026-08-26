"""Confirm the Azure run place would reach the *intended* deployment.

A deployment name on its own does not identify a deployment. Two different
Azure AI Foundry accounts in the same tenant can each expose a deployment named
``gpt-5.4``, and they may sit in different regions, run different model
versions, and apply different content filters. A comparison that pins only the
name can therefore run against a resource nobody intended and still report that
every run place used "the same deployment".

That is not hypothetical. When the five-task advance check was first attempted,
the tenant it was attempted from contained two accounts each exposing a
deployment named ``gpt-5.4``, and a third exposing the same underlying model
under a different deployment name.

This module closes that hole. It reads the endpoint settings that are already
in the environment, classifies them with the repository's own endpoint rules,
and reports precisely which part does not line up with the account and project
the plan pins. Every check here reads settings only: nothing contacts Azure,
signs in, or spends money.

Every rule it applies is read from ``core/azure_ai_clients.py``, which is the
module the paid run uses to decide whether a route may be built at all. That is
deliberate and it was not always so. This module used to hold its own written-
out copies of the same lists, and a copy agrees only until one of the two is
edited: seventeen settings were swept one at a time, and seven of them got
different answers here and there, six of the seven in the direction where this
check hands out a clean bill of health for a setting the run refuses to start
with. Reading the rules instead of restating them closes six of those seven;
``tests/test_envelope_azure_applies_the_run_rules.py`` holds all seventeen in
place and states the seventh, which is refused here on purpose.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Mapping


def _route_rules() -> Any:
    """The module the paid run uses to decide whether a route may be built.

    Every setting name and every rule below is read from here rather than
    written out again. The two used to be written out in both places, and a
    copy agrees only until somebody edits one of them: adding a name to the
    list of forbidden fixed credentials in that module left this check handing
    out a clean bill of health for a setting the run refuses to start with.

    It is imported inside the function, rather than at the top of the file, so
    that this check keeps working in a stripped-down environment where the
    Azure client libraries are absent until something actually needs them.
    """
    return importlib.import_module("core.azure_ai_clients")



@dataclass(frozen=True)
class AzureConnectionRequirement:
    """Which Azure resource the comparison is pinned to.

    ``account`` is the Azure AI Foundry account, and ``project`` the project
    inside it. Together with the deployment name they identify one deployment
    exactly, which the deployment name alone does not.
    """

    account: str
    project: str
    route_profile: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "AzureConnectionRequirement":
        missing = sorted({"account", "project", "route_profile"} - set(raw))
        if missing:
            raise ValueError(
                "the Azure connection requirement is missing: "
                + ", ".join(missing)
            )
        for name in ("account", "project", "route_profile"):
            if not str(raw[name] or "").strip():
                raise ValueError(
                    f"the Azure connection requirement leaves {name} empty, so "
                    "it does not identify one deployment"
                )
        return cls(
            account=str(raw["account"]).strip(),
            project=str(raw["project"]).strip(),
            route_profile=str(raw["route_profile"]).strip(),
        )


@dataclass
class AzureConnectionDiagnosis:
    """What the settings say, and what is wrong with them."""

    problems: list[str]
    reachable_intent: bool
    """True when the settings name exactly the pinned account and project.

    This says the settings point at the intended resource. It does not say the
    resource can be reached, because reaching it needs a sign-in and this check
    never signs in.
    """

    observed_account: str | None = None
    observed_project: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "settings_name_the_intended_resource": self.reachable_intent,
            "observed_account": self.observed_account,
            "observed_project": self.observed_project,
            "problems": list(self.problems),
        }


def _classify(value: str):
    return _route_rules().classify_endpoint(value)


def _same_identity(observed: str, expected: str, names_a_project: bool) -> bool:
    """Compare two names the way the run place compares them.

    Account names are folded to lower case on both sides before the run place
    compares them, so a difference in capitals is not a difference. Project
    names are not folded, so there it is.
    """
    if names_a_project:
        return observed == expected
    return observed.lower() == expected.lower()


def _pinned_identity_problems(
    rules: Any,
    requirement: AzureConnectionRequirement,
    environ: Mapping[str, str],
) -> list[str]:
    """Apply the run place's own identity pinning before anything is spent.

    The run place refuses to build a route unless the identity settings for its
    profile are present, and refuses again if one of them names a resource the
    endpoints do not match. Both refusals arrive after a run has started and
    after the money has been committed to it, which is the wrong moment to find
    out about a setting.

    Which names matter is read from the run place rather than listed here, so a
    name added there is checked here without anyone having to remember.

    This check demands the names whatever the local value of the switch that
    turns the requirement on, because every automated run place in this
    repository that can spend money turns it on, and the local value of that
    switch does not change what those runs do. Refusing before the start beats
    stopping after it.
    """
    problems: list[str] = []
    required = rules.REQUIRED_IDENTITY_ENV_BY_PROFILE.get(
        requirement.route_profile
    )
    if required is None:
        # An unrecognised profile is reported by the caller, and there is no
        # identity list to apply for one.
        return problems

    # What the plan pins each of those names to. The plan names one account and
    # one project, and every identity setting the run place compares names one
    # or the other.
    pinned: Mapping[str, tuple[str, bool]] = {
        rules.EXPECTED_DIRECT_ACCOUNT_ENV: (requirement.account, False),
        rules.EXPECTED_PROJECT_ACCOUNT_ENV: (requirement.account, False),
        rules.EXPECTED_LEGACY_ACCOUNT_ENV: (requirement.account, False),
        rules.EXPECTED_PROJECT_NAME_ENV: (requirement.project, True),
    }

    for name in required:
        value = str(environ.get(name, "") or "").strip()
        entry = pinned.get(name)
        if entry is None:
            # The run place has gained an identity setting that the plan has
            # nothing to compare against. Saying so is the whole point: an
            # unchecked requirement is exactly what this function exists to
            # stop, and staying quiet about one would be the old fault in a
            # new place.
            problems.append(
                f"the Azure run place requires {name} before it will start, "
                "and the plan says nothing this check can compare it against. "
                "Either pin the value in the plan or say in writing why it "
                "does not need pinning."
            )
            continue

        expected, names_a_project = entry
        subject = "project" if names_a_project else "account"
        if not value:
            problems.append(
                f"{name} is not set. Every automated run place in this "
                "repository that can spend money turns on "
                f"{rules.REQUIRE_EXPECTED_IDENTITIES_ENV}, and the Azure run "
                f"place then refuses to start unless this names the {subject} "
                f"— which for this comparison is {expected!r}."
            )
            continue
        if not _same_identity(value, expected, names_a_project):
            problems.append(
                f"{name} names the {subject} {value!r}, but the comparison is "
                f"pinned to {expected!r}. The Azure run place compares this "
                "setting against the endpoint it is about to use and refuses "
                "when the two differ, so the run would stop after it had "
                "started."
            )

    return problems


def diagnose_azure_connection(
    requirement: AzureConnectionRequirement,
    environ: Mapping[str, str],
) -> AzureConnectionDiagnosis:
    """Say exactly which part of the Azure setup does not match the plan.

    The point of this function is that "not configured" and "configured, but
    pointing somewhere else" are different problems with different fixes, and a
    check that reports both as "not measured" sends the reader looking in the
    wrong place.

    Every rule applied here is read from the module the paid run uses to decide
    whether a route may be built. A rule described here but not read from there
    would only be a second opinion, and the opinion that stops a run is that
    module's.
    """
    rules = _route_rules()
    problems: list[str] = []
    observed_account: str | None = None
    observed_project: str | None = None

    route_profile_variable = rules.ROUTE_PROFILE_ENV
    project_endpoint_variable = rules.PROJECT_ENDPOINT_ENV
    direct_endpoint_variable = rules.DIRECT_ENDPOINT_ENV
    deprecated_endpoint_variable = rules.DEPRECATED_ENDPOINT_ENV

    known_profiles = tuple(profile.value for profile in rules.RouteProfile)
    if requirement.route_profile not in known_profiles:
        problems.append(
            f"the plan pins the route profile {requirement.route_profile!r}, "
            "which the Azure run place does not recognise, so it would refuse "
            "to start whatever the settings say. It must be one of: "
            + ", ".join(known_profiles)
        )

    profile = str(environ.get(route_profile_variable, "") or "").strip()
    if not profile:
        problems.append(
            f"{route_profile_variable} is not set, so the Azure run place "
            "refuses to start. It must be "
            f"{requirement.route_profile!r} for this comparison."
        )
    elif profile != requirement.route_profile:
        problems.append(
            f"{route_profile_variable} is {profile!r}, but this comparison "
            f"requires {requirement.route_profile!r}"
        )

    deprecated = str(
        environ.get(deprecated_endpoint_variable, "") or ""
    ).strip()
    if deprecated:
        problems.append(
            f"{deprecated_endpoint_variable} is set. This repository refuses "
            "to run while it is, because it does not say which kind of "
            f"endpoint it holds. Move the address to "
            f"{project_endpoint_variable} or {direct_endpoint_variable} and "
            "unset it."
        )

    present_forbidden = [
        name
        for name in rules.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
        if environ.get(name)
    ]
    if present_forbidden:
        problems.append(
            "these fixed credentials are set, and this repository refuses to "
            "run with any of them because it requires a sign-in that can be "
            "traced to a person or a workload: " + ", ".join(present_forbidden)
        )

    project_endpoint = str(
        environ.get(project_endpoint_variable, "") or ""
    ).strip()
    if not project_endpoint:
        problems.append(
            f"{project_endpoint_variable} is not set. The Azure run place "
            "needs the address of the project that holds the deployment, "
            f"which looks like https://{requirement.account}"
            f".services.ai.azure.com/api/projects/{requirement.project}"
        )
    else:
        try:
            endpoint = _classify(project_endpoint)
        except Exception as error:
            problems.append(
                f"{project_endpoint_variable} is not an address this "
                f"repository recognises: {error}"
            )
        else:
            observed_account = getattr(endpoint, "account", None)
            observed_project = getattr(endpoint, "project", None)
            if observed_account != requirement.account:
                problems.append(
                    f"{project_endpoint_variable} names the account "
                    f"{observed_account!r}, but the comparison is pinned to "
                    f"{requirement.account!r}. A deployment name is not unique "
                    "across accounts, so running against a different account "
                    "would compare a different deployment while reporting the "
                    "same name."
                )
            if observed_project != requirement.project:
                problems.append(
                    f"{project_endpoint_variable} names the project "
                    f"{observed_project!r}, but the comparison is pinned to "
                    f"{requirement.project!r}"
                )

    direct_endpoint = str(
        environ.get(direct_endpoint_variable, "") or ""
    ).strip()
    if direct_endpoint:
        try:
            endpoint = _classify(direct_endpoint)
        except Exception as error:
            problems.append(
                f"{direct_endpoint_variable} is not an address this repository "
                f"recognises: {error}"
            )
        else:
            account = getattr(endpoint, "account", None)
            if account != requirement.account:
                problems.append(
                    f"{direct_endpoint_variable} names the account "
                    f"{account!r}, but the comparison is pinned to "
                    f"{requirement.account!r}"
                )

    problems.extend(_pinned_identity_problems(rules, requirement, environ))

    return AzureConnectionDiagnosis(
        problems=problems,
        reachable_intent=not problems,
        observed_account=observed_account,
        observed_project=observed_project,
    )


def describe_expected_project_endpoint(
    requirement: AzureConnectionRequirement,
) -> str:
    """The address the settings should hold, written out so it can be checked."""
    return (
        f"https://{requirement.account}.services.ai.azure.com"
        f"/api/projects/{requirement.project}"
    )
