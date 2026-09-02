#!/usr/bin/env python3
"""Report the roles the CI identity holds on the Foundry project, without naming it.

Why this exists
---------------
Two dispatches of the Code Interpreter arm were refused on every call with
http 403 while the token check ahead of them passed. The direct-v1 arm, run by
the same service principal in the same tenant and subscription and asking for
the same token audience, was served. The only variable left is the resource the
call is addressed to, which makes this an authorization gap at the Foundry
project rather than an authentication one.

Nothing in this repository could measure that: there is no infrastructure code
and no role tooling of any kind. This script closes that gap.

Where it has to be run
----------------------
Through its workflow, in CI. Not from a development box, and not from the agent
container.

What this reads is whatever subscription and identity the ``az`` session is
signed into, and a login taken outside CI is a different one of each. Such a
login is not signed into the subscription holding the Foundry account, so ``az``
refuses the lookup outright -- it exits non-zero and names the subscription as
not found, rather than answering with an empty list. The run stops at
``control_plane_read_never_completed``.

The two failures are kept apart deliberately, because they license opposite
conclusions. When az answers and the account is not in the answer, this identity
genuinely cannot see it: an absent resource and a withheld role come back
through the control plane looking the same, and either is a real finding about
the account. When az never answers, the account was not looked up at all, and
the run says nothing about roles in either direction. Reporting the second as
the first sends the next reader hunting a missing role in a directory that never
held the resource.

``AZURE_SUBSCRIPTION_ID`` is required rather than defaulted, below, so the
script cannot quietly inherit whichever subscription a local login happens to
carry. That is as far as a check can go: a subscription id supplied by hand is
well-formed whether or not it is the right one, and no assertion here can tell
the two apart.

What it does and does not do
----------------------------
Every call it makes is an ARM control-plane READ. It never creates, updates or
deletes anything, and it never calls a model endpoint, so running it cannot
re-trigger the refusal that made it necessary and cannot spend money.

What it prints
--------------
Role display names, role definition GUIDs and the SHAPE of each scope. Those are
public Azure-wide identifiers. It never prints the subscription id, the resource
group, the Foundry account name, the project name, the principal object id or
the tenant id, and it refuses to print at all if a known secret value survives
into the rendered report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess  # nosec B404 - control-plane reads via the pinned az CLI
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from core.azure_ai_clients import (  # noqa: E402
    PROJECT_ENDPOINT_ENV,
    EndpointKind,
    classify_endpoint,
)

# The action that decides whether the principal can fix this itself.
ROLE_ASSIGNMENT_WRITE = "Microsoft.Authorization/roleAssignments/write"

# The provider path a Foundry project lives under.
FOUNDRY_PROVIDER = "Microsoft.CognitiveServices"
FOUNDRY_ACCOUNT_TYPE = f"{FOUNDRY_PROVIDER}/accounts"


@dataclass(frozen=True)
class RoleCandidate:
    """One rung of the least-privilege ladder, quoted from the Microsoft doc."""

    name: str
    definition_id: str
    why: str


# Ordered least privilege first. Ask for the first rung; only if a run still
# refuses does the second become justified. Both are assigned at PROJECT scope,
# never at the account above it.
#
# Source: learn.microsoft.com/en-us/azure/ai-foundry/concepts/rbac-azure-ai-foundry
# The roles were renamed (Azure AI User became Foundry User and so on) but the
# definition ids did not change, so the ids are what this script matches on.
LEAST_PRIVILEGE_LADDER: tuple[RoleCandidate, ...] = (
    RoleCandidate(
        name="Foundry Agent Consumer",
        definition_id="eed3b665-ab3a-47b6-8f48-c9382fb1dad6",
        why=(
            "the documented role for an identity that only calls agents, the "
            "Responses API named as the example, without creating or "
            "modifying them"
        ),
    ),
    RoleCandidate(
        name="Foundry User",
        definition_id="53ca6127-db72-4b80-b1b0-d745d6d5456d",
        why=(
            "the next rung up, justified only if a run still refuses after the "
            "consumer role has propagated"
        ),
    ),
)

# Roles the same doc tells you not to reach for here. Recorded so that a future
# reader does not rediscover them as plausible.
FORBIDDEN_ROLE_IDS: Mapping[str, str] = {
    "25fbc0a9-bd7c-42a3-aa1a-3b75d497ee68": (
        "Cognitive Services Contributor carries no data actions at all, so it "
        "cannot authorize a token-based inference call"
    ),
    "64702f94-c441-49e6-a78b-ef80e0188fee": (
        "Azure AI Developer is not the Foundry project access path"
    ),
}
FORBIDDEN_ROLE_NAME_PREFIX = "Cognitive Services"


# -------------------------------------------------------------------------
# Scope shapes
# -------------------------------------------------------------------------

_SCOPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "foundry-project",
        re.compile(
            r"\A/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"
            r"Microsoft\.CognitiveServices/accounts/[^/]+/projects/[^/]+\Z",
            re.IGNORECASE,
        ),
    ),
    (
        "foundry-account",
        re.compile(
            r"\A/subscriptions/[^/]+/resourceGroups/[^/]+/providers/"
            r"Microsoft\.CognitiveServices/accounts/[^/]+\Z",
            re.IGNORECASE,
        ),
    ),
    (
        "other-resource",
        re.compile(
            r"\A/subscriptions/[^/]+/resourceGroups/[^/]+/providers/.+\Z",
            re.IGNORECASE,
        ),
    ),
    (
        "resource-group",
        re.compile(r"\A/subscriptions/[^/]+/resourceGroups/[^/]+\Z", re.IGNORECASE),
    ),
    ("subscription", re.compile(r"\A/subscriptions/[^/]+\Z", re.IGNORECASE)),
    (
        "management-group",
        re.compile(
            r"\A/providers/Microsoft\.Management/managementGroups/[^/]+\Z",
            re.IGNORECASE,
        ),
    ),
    ("tenant-root", re.compile(r"\A/\Z")),
)


def scope_shape(scope: str) -> str:
    """Say what KIND of thing a scope is, never which one.

    A reader needs to know whether a role sits on the project, on the account
    above it or on the whole subscription, because that is what decides whether
    it is least privilege. None of that requires the name.
    """
    if not isinstance(scope, str) or not scope.strip():
        return "unreadable"
    candidate = scope.strip().rstrip("/") or "/"
    for shape, pattern in _SCOPE_PATTERNS:
        if pattern.fullmatch(candidate):
            return shape
    return "unrecognised"


def project_scope(
    *, subscription_id: str, resource_group: str, account: str, project: str
) -> str:
    """Build the project-scope resource id the role has to be assigned at."""
    for label, value in (
        ("subscription id", subscription_id),
        ("resource group", resource_group),
        ("account", account),
        ("project", project),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} is required to build a project scope")
        if "/" in value:
            raise ValueError(f"{label} must not contain a path separator")
    return (
        f"/subscriptions/{subscription_id.strip()}"
        f"/resourceGroups/{resource_group.strip()}"
        f"/providers/{FOUNDRY_ACCOUNT_TYPE}/{account.strip()}"
        f"/projects/{project.strip()}"
    )


def resource_group_of(resource_id: str) -> str | None:
    """Pull the resource group out of an ARM resource id, or say it is absent."""
    if not isinstance(resource_id, str):
        return None
    match = re.search(r"/resourceGroups/([^/]+)", resource_id, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


# -------------------------------------------------------------------------
# Role definition permissions
# -------------------------------------------------------------------------


def _action_matches(pattern: str, action: str) -> bool:
    """Azure action globbing: only ``*`` is special, and matching is caseless."""
    if not isinstance(pattern, str):
        return False
    expression = "".join(
        ".*" if part == "*" else re.escape(part)
        for part in re.split(r"(\*)", pattern)
    )
    return re.fullmatch(expression, action, re.IGNORECASE) is not None


def permits_role_assignment(definitions: Iterable[Mapping[str, Any]]) -> bool:
    """Whether any of these role definitions grants roleAssignments/write.

    Evaluated the way Azure evaluates it: an action is granted by a permission
    block when ``actions`` matches it and ``notActions`` does not.
    """
    for definition in definitions:
        if not isinstance(definition, Mapping):
            continue
        for permission in definition.get("permissions") or ():
            if not isinstance(permission, Mapping):
                continue
            allowed = any(
                _action_matches(entry, ROLE_ASSIGNMENT_WRITE)
                for entry in permission.get("actions") or ()
            )
            if not allowed:
                continue
            denied = any(
                _action_matches(entry, ROLE_ASSIGNMENT_WRITE)
                for entry in permission.get("notActions") or ()
            )
            if not denied:
                return True
    return False


# -------------------------------------------------------------------------
# Assignments
# -------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldRole:
    """One role assignment, reduced to what can be said out loud."""

    role_name: str
    definition_id: str
    scope_shape: str
    covers_the_project: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "role_name": self.role_name,
            "role_definition_id": self.definition_id,
            "scope_shape": self.scope_shape,
            "covers_the_project": self.covers_the_project,
        }


def _definition_id_of(assignment: Mapping[str, Any]) -> str:
    raw = assignment.get("roleDefinitionId")
    if not isinstance(raw, str):
        return ""
    return raw.rstrip("/").rsplit("/", 1)[-1].lower()


def _covers(scope: str, target_scope: str) -> bool:
    """Whether a role at ``scope`` reaches ``target_scope``.

    Azure inherits downwards, so a role on the subscription reaches the project
    under it. Compared caselessly on whole path segments, so that an account
    named as a prefix of another cannot be mistaken for it.
    """
    if not isinstance(scope, str) or not scope.strip():
        return False
    held = scope.strip().rstrip("/").lower() or "/"
    target = target_scope.strip().rstrip("/").lower()
    if held == "/":
        return True
    return target == held or target.startswith(f"{held}/")


def summarize_assignments(
    assignments: Iterable[Mapping[str, Any]], *, target_scope: str
) -> tuple[HeldRole, ...]:
    """Reduce raw ``az role assignment list`` output to sayable records."""
    seen: set[tuple[str, str, str]] = set()
    held: list[HeldRole] = []
    for assignment in assignments:
        if not isinstance(assignment, Mapping):
            continue
        scope = assignment.get("scope")
        scope_text = scope if isinstance(scope, str) else ""
        name = assignment.get("roleDefinitionName")
        role_name = name if isinstance(name, str) and name.strip() else "unnamed"
        record = HeldRole(
            role_name=role_name,
            definition_id=_definition_id_of(assignment),
            scope_shape=scope_shape(scope_text),
            covers_the_project=_covers(scope_text, target_scope),
        )
        key = (record.role_name, record.definition_id, record.scope_shape)
        if key in seen:
            continue
        seen.add(key)
        held.append(record)
    return tuple(
        sorted(held, key=lambda item: (item.role_name, item.scope_shape))
    )


def missing_rungs(held: Sequence[HeldRole]) -> tuple[RoleCandidate, ...]:
    """Which rungs of the ladder are not already covering the project."""
    have = {
        role.definition_id
        for role in held
        if role.covers_the_project and role.definition_id
    }
    return tuple(rung for rung in LEAST_PRIVILEGE_LADDER if rung.definition_id not in have)


def forbidden_roles_held(held: Sequence[HeldRole]) -> tuple[str, ...]:
    """Roles the doc says are the wrong instrument for this, if any are held."""
    found: list[str] = []
    for role in held:
        reason = FORBIDDEN_ROLE_IDS.get(role.definition_id)
        if reason is None and role.role_name.startswith(FORBIDDEN_ROLE_NAME_PREFIX):
            reason = (
                "roles beginning 'Cognitive Services' address an AI Services "
                "resource directly and do not apply to Foundry"
            )
        if reason is not None:
            found.append(f"{role.role_name}: {reason}")
    return tuple(sorted(set(found)))


# -------------------------------------------------------------------------
# Redaction
# -------------------------------------------------------------------------

SENSITIVE_ENV: tuple[tuple[str, str], ...] = (
    ("AZURE_SUBSCRIPTION_ID", "<subscriptionId>"),
    ("AZURE_TENANT_ID", "<tenantId>"),
    ("AZURE_CLIENT_ID", "<principalId>"),
    ("AZURE_AI_EXPECTED_SUBSCRIPTION_ID", "<subscriptionId>"),
    ("AZURE_AI_EXPECTED_TENANT_ID", "<tenantId>"),
    ("AZURE_AI_EXPECTED_CLIENT_ID", "<principalId>"),
    ("AZURE_AI_EXPECTED_PROJECT_ACCOUNT", "<accountName>"),
    ("AZURE_AI_EXPECTED_PROJECT_NAME", "<projectName>"),
    ("AZURE_AI_EXPECTED_DIRECT_ACCOUNT", "<accountName>"),
    (PROJECT_ENDPOINT_ENV, "<projectEndpoint>"),
    ("AZURE_OPENAI_V1_ENDPOINT", "<directEndpoint>"),
    ("AZURE_OPENAI_ENDPOINT", "<directEndpoint>"),
)

# Values this short are ordinary words. Redacting them would corrupt the report
# without protecting anything, so they are excluded from the leak check and the
# caller is told the value was too short to defend.
MINIMUM_REDACTABLE_LENGTH = 6


def collect_secrets(
    env: Mapping[str, str], *, extra: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Every value that must not survive into the report, and its placeholder."""
    secrets: dict[str, str] = {}
    for name, placeholder in SENSITIVE_ENV:
        value = env.get(name, "")
        if isinstance(value, str) and len(value.strip()) >= MINIMUM_REDACTABLE_LENGTH:
            secrets[value.strip()] = placeholder
    for value, placeholder in (extra or {}).items():
        if isinstance(value, str) and len(value.strip()) >= MINIMUM_REDACTABLE_LENGTH:
            secrets[value.strip()] = placeholder
    return secrets


def sensitive_values(
    env: Mapping[str, str], *, extra: Mapping[str, str] | None = None
) -> frozenset[str]:
    """The same values with no length floor, lowercased, for detection only.

    Substitution needs the floor, because replacing a three-letter resource
    name everywhere would corrupt ordinary words. Detection does not: a field
    this repository copies out of Azure verbatim can simply be withheld when it
    contains one, which is safe at any length.
    """
    found: set[str] = set()
    for name, _ in SENSITIVE_ENV:
        value = env.get(name, "")
        if isinstance(value, str) and value.strip():
            found.add(value.strip().lower())
    for value in extra or {}:
        if isinstance(value, str) and value.strip():
            found.add(value.strip().lower())
    return frozenset(found)


# A role display name is the one field Azure hands back as free text a human
# wrote. Built-in names are tame; a custom role can be called anything, and
# people do name custom roles after the resource they apply to.
WITHHELD_ROLE_NAME = "custom role (name withheld)"
_SAFE_ROLE_NAME = re.compile(r"\A[A-Za-z0-9 ()./_-]{1,64}\Z")


def safe_role_name(name: str, values: frozenset[str]) -> str:
    """Keep a role name only when it cannot be carrying an identifier."""
    if not isinstance(name, str) or not name.strip():
        return "unnamed"
    candidate = name.strip()
    if _SAFE_ROLE_NAME.fullmatch(candidate) is None:
        return WITHHELD_ROLE_NAME
    lowered = candidate.lower()
    if any(value and value in lowered for value in values):
        return WITHHELD_ROLE_NAME
    return candidate


def redact(text: str, secrets: Mapping[str, str]) -> str:
    """Replace every known secret value with its placeholder, longest first."""
    result = text
    for value in sorted(secrets, key=len, reverse=True):
        if value:
            result = re.sub(re.escape(value), secrets[value], result, flags=re.IGNORECASE)
    return result


def leaked_placeholders(text: str, secrets: Mapping[str, str]) -> tuple[str, ...]:
    """Which secret values survived redaction. Empty is the only safe answer."""
    lowered = text.lower()
    return tuple(
        sorted(
            {
                secrets[value]
                for value in secrets
                if value and value.lower() in lowered
            }
        )
    )


# -------------------------------------------------------------------------
# The az control-plane reads
# -------------------------------------------------------------------------


class AzureReadFailure(RuntimeError):
    """An az read failed. Carries a classification, never the provider text.

    ``completed`` separates the two ways a read can fail, which are different
    facts and support different conclusions:

    * ``completed=True``  -- az ran the query, returned parseable output, and
      the thing being looked for was not in it. Azure answered.
    * ``completed=False`` -- az did not answer at all: it exited non-zero, or
      returned something that would not parse. The question never reached the
      resource, so nothing at all was learned about it.

    Only the first supports an inference about what this identity can see. The
    default is the second, so a new raise site has to opt in to the stronger
    claim rather than inherit it.
    """

    def __init__(
        self, what: str, *, exit_code: int | None, completed: bool = False
    ) -> None:
        self.what = what
        self.exit_code = exit_code
        self.completed = completed
        detail = "no exit code" if exit_code is None else f"exit {exit_code}"
        super().__init__(f"{what} could not be read ({detail})")


AzRunner = Callable[[Sequence[str]], Any]


def _default_runner(arguments: Sequence[str]) -> Any:
    """Run one ``az`` read and parse its JSON.

    The subprocess output is parsed, never echoed. An az error message can name
    the resource it failed on, which is precisely what must not reach a log.
    """
    completed = subprocess.run(  # nosec B603 B607 - fixed argv, no shell
        ["az", *arguments, "--only-show-errors", "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if completed.returncode != 0:
        raise AzureReadFailure(
            " ".join(arguments[:2]), exit_code=completed.returncode
        )
    stdout = completed.stdout.strip()
    if not stdout:
        return []
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        raise AzureReadFailure(" ".join(arguments[:2]), exit_code=None) from None


def _as_mappings(payload: Any) -> list[Mapping[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, Mapping)]


def resolve_resource_group(
    runner: AzRunner, *, account: str, subscription_id: str
) -> str:
    """Ask Azure where the Foundry account lives.

    No secret and no repository variable records the resource group, so it has
    to come from Azure itself.

    An answered query that does not contain the account is a finding in its own
    right: the account is either absent from this subscription or withheld from
    this principal, and the control plane returns both the same way. That is the
    ``completed=True`` raise below. A query az never completed is not that
    finding, and is raised without the flag by the runner.
    """
    payload = runner(
        [
            "resource",
            "list",
            "--name",
            account,
            "--resource-type",
            FOUNDRY_ACCOUNT_TYPE,
            "--subscription",
            subscription_id,
        ]
    )
    for resource in _as_mappings(payload):
        group = resource.get("resourceGroup")
        if isinstance(group, str) and group.strip():
            return group.strip()
        derived = resource_group_of(str(resource.get("id", "")))
        if derived:
            return derived
    raise AzureReadFailure("the Foundry account", exit_code=None, completed=True)


def read_assignments(
    runner: AzRunner, *, principal_id: str, scope: str
) -> list[Mapping[str, Any]]:
    """Every role assignment reaching the project, inherited ones included."""
    payload = runner(
        [
            "role",
            "assignment",
            "list",
            "--assignee",
            principal_id,
            "--scope",
            scope,
            "--include-inherited",
            "--include-groups",
        ]
    )
    return _as_mappings(payload)


def read_definitions(
    runner: AzRunner, *, names: Sequence[str], scope: str
) -> list[Mapping[str, Any]]:
    """Fetch the permission blocks behind the roles the principal holds."""
    definitions: list[Mapping[str, Any]] = []
    for name in names:
        payload = runner(
            ["role", "definition", "list", "--name", name, "--scope", scope]
        )
        definitions.extend(_as_mappings(payload))
    return definitions


# -------------------------------------------------------------------------
# The diagnosis
# -------------------------------------------------------------------------


def _remediation(rung: RoleCandidate) -> list[str]:
    """The exact command an owner runs, with every identifier a placeholder."""
    return [
        'PROJECT_SCOPE="/subscriptions/<subscriptionId>/resourceGroups/'
        "<resourceGroup>/providers/Microsoft.CognitiveServices/accounts/"
        '<accountName>/projects/<projectName>"',
        "az role assignment create \\",
        '    --assignee-object-id "<principalId>" \\',
        "    --assignee-principal-type ServicePrincipal \\",
        f'    --role "{rung.definition_id}" \\',
        '    --scope "$PROJECT_SCOPE"',
    ]


def diagnose(
    env: Mapping[str, str], *, runner: AzRunner
) -> dict[str, Any]:
    """Read the roles, decide what is missing, and say who has to grant it."""
    endpoint_value = env.get(PROJECT_ENDPOINT_ENV, "").strip()
    if not endpoint_value:
        raise ValueError(f"{PROJECT_ENDPOINT_ENV} is required")
    endpoint = classify_endpoint(endpoint_value)
    if endpoint.kind is not EndpointKind.PROJECT or not endpoint.project:
        raise ValueError(
            f"{PROJECT_ENDPOINT_ENV} is not a Foundry project endpoint, so "
            "there is no project scope to read roles at"
        )

    subscription_id = env.get("AZURE_SUBSCRIPTION_ID", "").strip()
    principal_id = env.get("AZURE_CLIENT_ID", "").strip()
    if not subscription_id:
        raise ValueError("AZURE_SUBSCRIPTION_ID is required")
    if not principal_id:
        raise ValueError("AZURE_CLIENT_ID is required")

    problems: list[str] = []
    report: dict[str, Any] = {
        "route_profile": "project-ci",
        "endpoint_kind": endpoint.kind.value,
        "target_scope_shape": "foundry-project",
        "roles_held": [],
        "roles_reaching_the_project": [],
        "missing_least_privilege_roles": [
            {"name": rung.name, "role_definition_id": rung.definition_id}
            for rung in LEAST_PRIVILEGE_LADDER
        ],
        "forbidden_roles_held": [],
        "principal_can_assign_roles": None,
        "read_failures": [],
        "verdict": "unmeasured",
        # The account and project names live inside the endpoint secret rather
        # than in a variable of their own, so redaction of the whole endpoint
        # string would not catch either of them on its own.
        "secret_values": {
            endpoint.account: "<accountName>",
            endpoint.project: "<projectName>",
        },
    }

    try:
        resource_group = resolve_resource_group(
            runner, account=endpoint.account, subscription_id=subscription_id
        )
    except AzureReadFailure as failure:
        if failure.completed:
            problems.append(
                "could not resolve the Foundry account through the control "
                "plane, so the project scope could not be built. Azure "
                "answered and the account was not in the answer, which means "
                f"this identity has no reader on it ({failure.what})"
            )
            report["verdict"] = "cannot_read_control_plane"
        else:
            problems.append(
                "the Foundry account lookup did not complete, so the project "
                "scope could not be built. az did not answer the query, which "
                "is how a subscription this session is not signed into fails, "
                "so the account was never looked up and no role was measured "
                f"({failure.what})"
            )
            report["verdict"] = "control_plane_read_never_completed"
        report["read_failures"] = problems
        return report

    scope = project_scope(
        subscription_id=subscription_id,
        resource_group=resource_group,
        account=endpoint.account,
        project=endpoint.project,
    )
    # The resolved group joins the redaction set: it was read from Azure, not
    # from the environment, so collect_secrets could not have known it.
    report["secret_values"][resource_group] = "<resourceGroup>"
    values = sensitive_values(env, extra=report["secret_values"])

    try:
        assignments = read_assignments(
            runner, principal_id=principal_id, scope=scope
        )
    except AzureReadFailure as failure:
        problems.append(
            "could not list this identity's own role assignments at the "
            "project scope, which needs Microsoft.Authorization/"
            f"roleAssignments/read ({failure.what})"
        )
        report["read_failures"] = problems
        report["verdict"] = "cannot_read_role_assignments"
        return report

    # Two views of the same assignments. The raw names are what az has to be
    # asked about; only the sanitised ones are ever written down.
    raw = summarize_assignments(assignments, target_scope=scope)
    held = tuple(
        replace(role, role_name=safe_role_name(role.role_name, values))
        for role in raw
    )
    covering = tuple(role for role in held if role.covers_the_project)
    report["roles_held"] = [role.as_dict() for role in held]
    report["roles_reaching_the_project"] = [role.as_dict() for role in covering]
    report["forbidden_roles_held"] = list(forbidden_roles_held(held))

    missing = missing_rungs(held)
    report["missing_least_privilege_roles"] = [
        {"name": rung.name, "role_definition_id": rung.definition_id}
        for rung in missing
    ]

    try:
        definitions = read_definitions(
            runner,
            names=sorted(
                {
                    role.role_name
                    for role in raw
                    if role.covers_the_project and role.role_name != "unnamed"
                }
            ),
            scope=scope,
        )
    except AzureReadFailure as failure:
        problems.append(
            "could not read the permissions behind the roles this identity "
            "holds, so whether it can assign a role is unmeasured "
            f"({failure.what})"
        )
    else:
        report["principal_can_assign_roles"] = permits_role_assignment(definitions)

    report["read_failures"] = problems

    if not missing:
        report["verdict"] = "least_privilege_role_already_held"
    elif report["principal_can_assign_roles"] is True:
        report["verdict"] = "role_missing_and_this_identity_can_grant_it"
    elif report["principal_can_assign_roles"] is False:
        report["verdict"] = "role_missing_and_an_owner_must_grant_it"
    else:
        report["verdict"] = "role_missing_and_the_grantor_is_unmeasured"

    return report


# -------------------------------------------------------------------------
# Rendering
# -------------------------------------------------------------------------

_VERDICT_LINES: Mapping[str, str] = {
    "least_privilege_role_already_held": (
        "A least-privilege role already reaches the project. If a call is "
        "still refused, the cause is not this role assignment."
    ),
    "role_missing_and_this_identity_can_grant_it": (
        "The role is missing and this identity holds roleAssignments/write, so "
        "it can assign the role itself at project scope."
    ),
    "role_missing_and_an_owner_must_grant_it": (
        "The role is missing and this identity cannot assign roles. An Azure "
        "Owner on the account or project has to run the command below."
    ),
    "role_missing_and_the_grantor_is_unmeasured": (
        "The role is missing. Whether this identity could assign it was not "
        "measurable, so treat it as an owner action."
    ),
    "cannot_read_control_plane": (
        "This identity cannot read the Foundry account through the control "
        "plane, so no role could be read. An owner has to look."
    ),
    "control_plane_read_never_completed": (
        "The account lookup did not complete, so nothing was measured. This "
        "is what a subscription the session is not signed into looks like, "
        "and it is not evidence that a role is missing. Re-run it where the "
        "signed-in subscription is the one holding the project."
    ),
    "cannot_read_role_assignments": (
        "This identity cannot read its own role assignments at the project "
        "scope. An owner has to look."
    ),
    "unmeasured": "Nothing was measured.",
}


def render(report: Mapping[str, Any]) -> str:
    """Turn the diagnosis into text a public log can carry."""
    lines: list[str] = [
        "Azure Foundry project RBAC diagnostic (control-plane reads only)",
        "",
        f"route profile        : {report.get('route_profile')}",
        f"endpoint kind        : {report.get('endpoint_kind')}",
        f"target scope shape   : {report.get('target_scope_shape')}",
        f"verdict              : {report.get('verdict')}",
        "",
        _VERDICT_LINES.get(str(report.get("verdict")), _VERDICT_LINES["unmeasured"]),
        "",
    ]

    held = list(report.get("roles_held") or ())
    if held:
        lines.append(f"roles this identity holds ({len(held)}):")
        for role in held:
            reach = "reaches the project" if role.get("covers_the_project") else "does not reach it"
            lines.append(
                f"  - {role.get('role_name')} "
                f"[{role.get('role_definition_id')}] "
                f"at {role.get('scope_shape')}, {reach}"
            )
    else:
        lines.append("roles this identity holds: none were returned")
    lines.append("")

    can_assign = report.get("principal_can_assign_roles")
    lines.append(
        "can this identity assign roles: "
        + {True: "yes", False: "no", None: "unmeasured"}[can_assign]
    )

    forbidden = list(report.get("forbidden_roles_held") or ())
    if forbidden:
        lines.append("")
        lines.append("roles held that are the wrong instrument here:")
        lines.extend(f"  - {entry}" for entry in forbidden)

    failures = list(report.get("read_failures") or ())
    if failures:
        lines.append("")
        lines.append("reads that did not succeed:")
        lines.extend(f"  - {entry}" for entry in failures)

    missing = list(report.get("missing_least_privilege_roles") or ())
    if missing:
        lines.append("")
        lines.append("least privilege ladder, first rung first:")
        for rung in missing:
            name = str(rung.get("name", ""))
            why = next(
                (
                    candidate.why
                    for candidate in LEAST_PRIVILEGE_LADDER
                    if candidate.name == name
                ),
                "",
            )
            lines.append(f"  - {name} [{rung.get('role_definition_id')}]: {why}")
        lines.append("")
        lines.append(
            "Assign the first rung only. The portal can assign it at account "
            "scope alone, so project scope needs the CLI:"
        )
        first = next(
            (
                candidate
                for candidate in LEAST_PRIVILEGE_LADDER
                if candidate.name == str(missing[0].get("name", ""))
            ),
            LEAST_PRIVILEGE_LADDER[0],
        )
        lines.append("")
        lines.extend(f"  {line}" for line in _remediation(first))

    lines.append("")
    lines.append(
        "This diagnostic made control-plane reads only. It called no model "
        "endpoint, so it neither reproduces the http 403 nor spends anything."
    )
    return "\n".join(lines)


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the redacted report as JSON instead of prose",
    )
    parser.add_argument(
        "--require-project-role",
        action="store_true",
        help=(
            "Exit non-zero unless a least-privilege role already reaches the "
            "project. Off by default so that reporting a gap is not an error"
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    runner: AzRunner | None = None,
    stream: Any = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    values = os.environ if env is None else env
    out = sys.stdout if stream is None else stream

    try:
        report = diagnose(values, runner=runner or _default_runner)
    except ValueError as exc:
        # Safe to print: these messages name environment variables, not values.
        print(f"azure rbac diagnostic refused to run: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("azure rbac diagnostic failed", file=sys.stderr)
        return 2

    extra = dict(report.pop("secret_values", {}) or {})
    secrets = collect_secrets(values, extra=extra)
    body = json.dumps(report, indent=2, sort_keys=True) if args.json else render(report)
    body = redact(body, secrets)

    survivors = leaked_placeholders(body, secrets)
    if survivors:
        # Fail closed. A report that still carries an identifier is worse than
        # no report, because the log is public and cannot be unpublished.
        print(
            "azure rbac diagnostic withheld its report: redaction did not "
            f"clear {len(survivors)} identifier(s)",
            file=sys.stderr,
        )
        return 3

    print(body, file=out)

    if args.require_project_role and report["verdict"] != "least_privilege_role_already_held":
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
