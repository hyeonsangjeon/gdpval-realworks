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
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Mapping

# The settings that name each kind of Azure endpoint. These are the same names
# core/azure_ai_clients.py reads, so a plan checked here is checked against the
# variables the run itself will use.
DIRECT_ENDPOINT_VARIABLE = "AZURE_OPENAI_V1_ENDPOINT"
PROJECT_ENDPOINT_VARIABLE = "FOUNDRY_PROJECT_ENDPOINT"
ROUTE_PROFILE_VARIABLE = "AZURE_AI_ROUTE_PROFILE"
DEPRECATED_ENDPOINT_VARIABLE = "AZURE_OPENAI_ENDPOINT"

# Static credentials this repository refuses to run with. Naming them here lets
# the free check say so up front, instead of the run failing later with the
# same complaint after someone has already scheduled it.
FORBIDDEN_CREDENTIAL_VARIABLES = (
    "AZURE_OPENAI_API_KEY",
    "AZURE_API_KEY",
    "AZURE_AI_API_KEY",
    "AZURE_AI_PROJECT_API_KEY",
    "AZURE_OPENAI_AD_TOKEN",
    "AZURE_CLIENT_SECRET",
    "AZURE_CLIENT_CERTIFICATE_PATH",
    "AZURE_CLIENT_CERTIFICATE_PASSWORD",
    "AZURE_USERNAME",
    "AZURE_PASSWORD",
)


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
    module = importlib.import_module("core.azure_ai_clients")
    return module.classify_endpoint(value)


def diagnose_azure_connection(
    requirement: AzureConnectionRequirement,
    environ: Mapping[str, str],
) -> AzureConnectionDiagnosis:
    """Say exactly which part of the Azure setup does not match the plan.

    The point of this function is that "not configured" and "configured, but
    pointing somewhere else" are different problems with different fixes, and a
    check that reports both as "not measured" sends the reader looking in the
    wrong place.
    """
    problems: list[str] = []
    observed_account: str | None = None
    observed_project: str | None = None

    profile = str(environ.get(ROUTE_PROFILE_VARIABLE, "") or "").strip()
    if not profile:
        problems.append(
            f"{ROUTE_PROFILE_VARIABLE} is not set, so the Azure run place "
            "refuses to start. It must be "
            f"{requirement.route_profile!r} for this comparison."
        )
    elif profile != requirement.route_profile:
        problems.append(
            f"{ROUTE_PROFILE_VARIABLE} is {profile!r}, but this comparison "
            f"requires {requirement.route_profile!r}"
        )

    deprecated = str(environ.get(DEPRECATED_ENDPOINT_VARIABLE, "") or "").strip()
    if deprecated:
        problems.append(
            f"{DEPRECATED_ENDPOINT_VARIABLE} is set. This repository refuses to "
            "run while it is, because it does not say which kind of endpoint it "
            f"holds. Move the address to {PROJECT_ENDPOINT_VARIABLE} or "
            f"{DIRECT_ENDPOINT_VARIABLE} and unset it."
        )

    present_forbidden = [
        name for name in FORBIDDEN_CREDENTIAL_VARIABLES if environ.get(name)
    ]
    if present_forbidden:
        problems.append(
            "these fixed credentials are set, and this repository refuses to "
            "run with any of them because it requires a sign-in that can be "
            "traced to a person or a workload: " + ", ".join(present_forbidden)
        )

    project_endpoint = str(
        environ.get(PROJECT_ENDPOINT_VARIABLE, "") or ""
    ).strip()
    if not project_endpoint:
        problems.append(
            f"{PROJECT_ENDPOINT_VARIABLE} is not set. The Azure run place needs "
            "the address of the project that holds the deployment, which looks "
            f"like https://{requirement.account}.services.ai.azure.com"
            f"/api/projects/{requirement.project}"
        )
    else:
        try:
            endpoint = _classify(project_endpoint)
        except Exception as error:
            problems.append(
                f"{PROJECT_ENDPOINT_VARIABLE} is not an address this "
                f"repository recognises: {error}"
            )
        else:
            observed_account = getattr(endpoint, "account", None)
            observed_project = getattr(endpoint, "project", None)
            if observed_account != requirement.account:
                problems.append(
                    f"{PROJECT_ENDPOINT_VARIABLE} names the account "
                    f"{observed_account!r}, but the comparison is pinned to "
                    f"{requirement.account!r}. A deployment name is not unique "
                    "across accounts, so running against a different account "
                    "would compare a different deployment while reporting the "
                    "same name."
                )
            if observed_project != requirement.project:
                problems.append(
                    f"{PROJECT_ENDPOINT_VARIABLE} names the project "
                    f"{observed_project!r}, but the comparison is pinned to "
                    f"{requirement.project!r}"
                )

    direct_endpoint = str(environ.get(DIRECT_ENDPOINT_VARIABLE, "") or "").strip()
    if direct_endpoint:
        try:
            endpoint = _classify(direct_endpoint)
        except Exception as error:
            problems.append(
                f"{DIRECT_ENDPOINT_VARIABLE} is not an address this repository "
                f"recognises: {error}"
            )
        else:
            account = getattr(endpoint, "account", None)
            if account != requirement.account:
                problems.append(
                    f"{DIRECT_ENDPOINT_VARIABLE} names the account "
                    f"{account!r}, but the comparison is pinned to "
                    f"{requirement.account!r}"
                )

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
