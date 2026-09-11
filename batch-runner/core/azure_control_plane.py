"""The control-plane reads, and the promise that a report never names a resource.

Why this is its own module
--------------------------
These pieces were written once, for :mod:`scripts.azure_rbac_diagnostic`, to
answer why the Code Interpreter arm was refused with http 403. A second question
now needs the same machinery -- what throughput the deployment is declared to
have -- and a security property is the worst possible thing to own two copies
of. The second copy passes its own tests on the day it is written and then stops
tracking the first one, so a fix made in the place someone was looking never
reaches the place that was actually running.

There is a layering reason as well. The capacity a deployment declares is the
denominator a run divides its token counts into, so the run itself will want to
record it, and a run cannot reasonably import from a diagnostic script.

What is here and what is not
----------------------------
Only the parts that are about *reading Azure safely*: how an ``az`` read fails,
how its output is parsed without ever being echoed, where a resource group comes
from, and how a rendered report is stripped of identifiers and then checked for
survivors. Everything about roles -- the least-privilege ladder, the scope
shapes, the permission matching -- stays in the diagnostic, because it answers
one question and this module answers none.

Every call made from here is an ARM control-plane READ. Nothing here creates,
updates or deletes, and nothing here calls a model endpoint, so importing it
cannot spend money.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 - control-plane reads via the pinned az CLI
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from core.azure_ai_clients import PROJECT_ENDPOINT_ENV

# The provider path a Foundry account lives under. Both the project a role is
# read at and the deployment a capacity is read from hang off an account of
# this type.
FOUNDRY_PROVIDER = "Microsoft.CognitiveServices"
FOUNDRY_ACCOUNT_TYPE = f"{FOUNDRY_PROVIDER}/accounts"


def resource_group_of(resource_id: str) -> str | None:
    """Pull the resource group out of an ARM resource id, or say it is absent."""
    if not isinstance(resource_id, str):
        return None
    match = re.search(r"/resourceGroups/([^/]+)", resource_id, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


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


def default_runner(arguments: Sequence[str]) -> Any:
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


def as_mappings(payload: Any) -> list[Mapping[str, Any]]:
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
    for resource in as_mappings(payload):
        group = resource.get("resourceGroup")
        if isinstance(group, str) and group.strip():
            return group.strip()
        derived = resource_group_of(str(resource.get("id", "")))
        if derived:
            return derived
    raise AzureReadFailure("the Foundry account", exit_code=None, completed=True)
