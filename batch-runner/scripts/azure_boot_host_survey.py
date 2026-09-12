#!/usr/bin/env python3
"""Ask whether the subscription the model lives in could already host a guest.

Stage D needs two things in one place: a GPT deployment to call, and a machine
that can boot a Firecracker microVM to run what the model decides. This
repository has both, and they are not in one place.

* The model is a deployment on a Foundry account in one subscription and one
  tenant, reachable from CI by the federated identity.
* The only host shown to boot a guest -- C2 booted one on it, C3 attacked it --
  is a VM in a *different* subscription in a *different* tenant, reachable from
  a development box by an interactive login.

Two routes close that gap. The first, boot the guest on the GitHub-hosted
runner that already holds the model credential, is recorded as closed:
``RECORDED_FINDINGS[0]`` in :mod:`core.agentic_v2_containment_readiness` cites
GitHub's own documentation calling nested virtualisation on hosted runners
technically possible but not officially supported, and a boundary offered with
no guarantee is not a boundary. The second is this one: put a host in the
subscription the model is already in.

**What this script does about that: nothing.** It measures. Every call it makes
is an ARM control-plane read. It creates no resource, registers no provider,
requests no role, and calls no model endpoint, so running it changes nothing
and spends nothing. That matters beyond tidiness -- creating a machine and
granting a role are access changes, and the standing instruction on this task is
that those get reported exactly, not performed quietly. A survey that quietly
fixed what it found would be the failure mode, not the feature.

So the output is one of four answers, and only the first two are good news:

``host_already_exists``
    There is already a virtual machine in this subscription. Nothing needs
    creating, and the next question is whether *that* machine can boot a guest
    -- which is C2's question, not this one's.
``creation_is_within_existing_permissions``
    The identity holds a role permitting the writes, the Compute provider is
    registered, and the region has quota. A host could be deployed under
    permissions that already exist, with no access change at all.
``blocked_and_the_change_is_named``
    One or more of those preconditions is missing. The report names which, in
    the exact terms somebody would need to approve it. It does not ask for it.
``not_measured``
    ``az`` did not answer. Nothing was learned, and in particular this is *not*
    evidence that anything is absent. A local login reaches a different
    subscription entirely and will land here; that is correct behaviour, not a
    bug. Run it in CI, or do not run it.

Usage:

    python scripts/azure_boot_host_survey.py
    python scripts/azure_boot_host_survey.py --json
    python scripts/azure_boot_host_survey.py --location koreacentral

Exit status:

    0   the survey completed and reported an answer, whatever that answer was
    1   the survey could not run, or a redaction check failed
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCRIPTS_DIR = Path(__file__).resolve().parent
BATCH_ROOT = SCRIPTS_DIR.parent
RBAC_DIAGNOSTIC = SCRIPTS_DIR / "azure_rbac_diagnostic.py"

if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))


RBAC_MODULE_NAME = "azure_rbac_diagnostic"


def _rbac_module() -> Any:
    """Load the RBAC diagnostic for its redaction and az-read helpers.

    By path because ``scripts`` is not a package, which is how
    :mod:`run_agentic_stage_d_probe` and the tests already load these. Shared
    rather than reimplemented on purpose: redaction that is copied is redaction
    that drifts, and the failure mode of drifted redaction is a subscription id
    in a public log.

    An already-loaded copy is reused rather than loaded again, and the module is
    registered before it is executed. Both are needed. Registering is not
    optional -- ``dataclasses`` resolves field annotations through
    ``sys.modules[cls.__module__]``, so a frozen dataclass in a module loaded by
    path and left unregistered raises on definition. Reusing matters because two
    live copies would define two different ``AzureReadFailure`` classes, and the
    ``except`` clauses below would stop catching the one actually raised.
    """
    existing = sys.modules.get(RBAC_MODULE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(RBAC_MODULE_NAME, RBAC_DIAGNOSTIC)
    if spec is None or spec.loader is None:  # pragma: no cover - a missing file
        raise SurveyRefused(f"the RBAC diagnostic is not at {RBAC_DIAGNOSTIC}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[RBAC_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


class SurveyRefused(RuntimeError):
    """The survey did not run, and the reason is not a fact about Azure."""


# -------------------------------------------------------------------------
# What a host would need
# -------------------------------------------------------------------------

SCOPE_RESOURCE_GROUP = "resource_group"
SCOPE_SUBSCRIPTION = "subscription"


@dataclass(frozen=True)
class NeededAction:
    """One control-plane action deploying the host definition would perform.

    ``scope`` is the smallest scope an assignment granting it could sit at, and
    it is the difference between an access change the resource-group owner can
    make and one that has to be made across the whole subscription.

    ``only_if`` names the condition under which the template performs it at all.
    An action carrying one is measured like the others but does not block the
    verdict, because a deployment that never takes that branch never needs it.
    """

    action: str
    why: str
    scope: str = SCOPE_RESOURCE_GROUP
    only_if: str = ""

    @property
    def always(self) -> bool:
        return not self.only_if


#: Every control-plane write that deploying ``infra/dev-host/main.bicep``
#: performs, one entry per resource the template declares, read off the
#: template rather than chosen here. Listed as actions rather than as a role
#: name because the question is what the identity *can do*, and two identities
#: holding different roles can both be able to do this.
#:
#: An earlier version of this list named three actions. That was not the
#: template's list: it was missing the network security group, the virtual
#: network, the data disk, the auto-shutdown schedule and the deployment object
#: itself, so an identity could have passed the survey and still failed the
#: deployment. The three it did name are still here.
REQUIRED_ACTIONS: tuple[NeededAction, ...] = (
    NeededAction(
        "Microsoft.Resources/deployments/write",
        "submit the template at all -- a deployment is itself a resource",
    ),
    NeededAction(
        "Microsoft.Network/networkSecurityGroups/write",
        "create the security group that closes the host to the internet",
    ),
    NeededAction(
        "Microsoft.Network/virtualNetworks/write",
        "create the network and the subnet the host sits on",
    ),
    NeededAction(
        "Microsoft.Network/networkInterfaces/write",
        "give it a network interface",
    ),
    NeededAction(
        "Microsoft.Compute/disks/write",
        "create the data disk the guest images would live on",
    ),
    NeededAction(
        "Microsoft.Compute/virtualMachines/write",
        "create the machine itself",
    ),
    NeededAction(
        "Microsoft.DevTestLab/schedules/write",
        "attach the auto-shutdown that stops it billing overnight",
    ),
    NeededAction(
        "Microsoft.Network/publicIPAddresses/write",
        "give it an address reachable from outside",
        only_if="attachPublicIp is set, and the template defaults it to false",
    ),
    NeededAction(
        "Microsoft.Resources/subscriptions/resourceGroups/write",
        "create the resource group to put it all in",
        scope=SCOPE_SUBSCRIPTION,
        only_if=(
            "the resource group does not already exist -- deploy.sh creates it "
            "in a separate step, so an owner who creates it first removes this "
            "action, and with it the only subscription-scope item on the list"
        ),
    ),
)

#: The joins. Creating a resource that attaches to another one needs permission
#: on *both*, and these are the ones the template's own attachments require.
#: Kept apart from the writes because they are the reason
#: ``Virtual Machine Contributor`` alone nearly works: it holds every join here
#: and only two of the writes above are outside it.
REQUIRED_JOINS: tuple[NeededAction, ...] = (
    NeededAction(
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "put the interface on the subnet",
    ),
    NeededAction(
        "Microsoft.Network/networkSecurityGroups/join/action",
        "apply the security group to that subnet",
    ),
    NeededAction(
        "Microsoft.Network/networkInterfaces/join/action",
        "attach the interface to the machine",
    ),
)


def actions_measured() -> tuple[NeededAction, ...]:
    """Everything the survey asks about, writes first."""
    return REQUIRED_ACTIONS + REQUIRED_JOINS


def actions_that_block() -> tuple[NeededAction, ...]:
    """The subset a deployment cannot go ahead without, under the defaults."""
    return tuple(needed for needed in actions_measured() if needed.always)

#: Without this registered, no virtual machine can be created in the
#: subscription however the roles read. Registering it is itself a write, so it
#: is measured here and never performed.
COMPUTE_PROVIDER = "Microsoft.Compute"

#: The size the repository's own dev-host definition names, and the quota family
#: Azure counts it under. Taken from ``infra/dev-host/main.bicep`` rather than
#: chosen here, so that a survey saying "there is room" is saying it about the
#: machine this repository would actually deploy.
HOST_VM_SIZE = "Standard_D8as_v5"
HOST_QUOTA_FAMILY = "standardDASv5Family"
HOST_VCPUS = 8

#: Where a host would go by default: the region the model deployment is in, so
#: that the model-to-host hop does not cross one. Overridable, because the
#: existing definition names ``koreacentral`` and comparing the two is a fair
#: question.
DEFAULT_LOCATION = "eastus2"

VERDICT_HOST_EXISTS = "host_already_exists"
VERDICT_WITHIN_PERMISSIONS = "creation_is_within_existing_permissions"
VERDICT_BLOCKED = "blocked_and_the_change_is_named"
VERDICT_NOT_MEASURED = "not_measured"


@dataclass(frozen=True)
class Finding:
    """One thing that was asked, and what came back.

    ``measured`` is the field that carries the weight. ``False`` means az never
    answered, and a reader must not turn that into an absence: not knowing
    whether there is quota and knowing there is none are different facts that
    support different decisions.
    """

    question: str
    measured: bool
    answer: Any
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "measured": self.measured,
            "answer": self.answer,
            "note": self.note,
        }


# -------------------------------------------------------------------------
# The reads
# -------------------------------------------------------------------------


def _permits(definitions: Sequence[Mapping[str, Any]], action: str, rbac: Any) -> bool:
    """Whether any of these definitions grants ``action``.

    Evaluated the way Azure evaluates it -- ``actions`` matches and
    ``notActions`` does not -- by reusing the diagnostic's own matcher, so a
    wildcard is read the same way in both places.
    """
    for definition in definitions:
        if not isinstance(definition, Mapping):
            continue
        for permission in definition.get("permissions") or ():
            if not isinstance(permission, Mapping):
                continue
            allowed = any(
                rbac._action_matches(entry, action)
                for entry in permission.get("actions") or ()
            )
            if not allowed:
                continue
            denied = any(
                rbac._action_matches(entry, action)
                for entry in permission.get("notActions") or ()
            )
            if not denied:
                return True
    return False


def read_session(runner: Callable[[Sequence[str]], Any], rbac: Any) -> Finding:
    """Which subscription and tenant this session is actually in.

    Asked first because every answer below is only about the place it was asked.
    The ids themselves are never reported -- they are secrets in CI and get
    redacted anyway -- so what comes back is their shape and whether the session
    is where it was expected to be.
    """
    try:
        account = runner(["account", "show"])
    except rbac.AzureReadFailure as failure:
        return Finding(
            "which subscription is this session in",
            measured=False,
            answer=None,
            note=(
                "az could not answer, so nothing below was measured either. A "
                "login taken outside CI reaches a different subscription and "
                f"lands here ({failure.what})"
            ),
        )
    if not isinstance(account, Mapping):
        return Finding(
            "which subscription is this session in",
            measured=False,
            answer=None,
            note="az returned something that was not an account record",
        )
    expected = (os.environ.get("AZURE_SUBSCRIPTION_ID") or "").strip().lower()
    found = str(account.get("id") or "").strip().lower()
    return Finding(
        "which subscription is this session in",
        measured=True,
        answer={
            "is_the_expected_subscription": bool(expected) and found == expected,
            "subscription_id_was_read": bool(found),
            "state": str(account.get("state") or ""),
        },
        note=(
            "the id is deliberately not reported; only whether it is the one "
            "the model credential names"
        ),
    )


def read_provider(runner: Callable[[Sequence[str]], Any], rbac: Any) -> Finding:
    """Whether ``Microsoft.Compute`` is registered in this subscription."""
    question = f"is {COMPUTE_PROVIDER} registered here"
    try:
        provider = runner(["provider", "show", "--namespace", COMPUTE_PROVIDER])
    except rbac.AzureReadFailure as failure:
        return Finding(
            question, measured=False, answer=None, note=f"az did not answer ({failure.what})"
        )
    if not isinstance(provider, Mapping):
        return Finding(
            question, measured=False, answer=None, note="not a provider record"
        )
    state = str(provider.get("registrationState") or "")
    return Finding(
        question,
        measured=True,
        answer={"registration_state": state, "registered": state == "Registered"},
        note=(
            ""
            if state == "Registered"
            else (
                "registering a provider is itself a write, so this survey "
                "reports the state and does not change it"
            )
        ),
    )


def read_existing_hosts(runner: Callable[[Sequence[str]], Any], rbac: Any) -> Finding:
    """How many virtual machines already exist here.

    A count, never a name. A VM name is free text somebody chose and can carry
    a project or customer in it; the count is the whole answer to "does anything
    need creating".
    """
    question = "are there already virtual machines in this subscription"
    try:
        machines = runner(["vm", "list"])
    except rbac.AzureReadFailure as failure:
        return Finding(
            question,
            measured=False,
            answer=None,
            note=(
                "az did not answer, which is also what a missing read role looks "
                f"like from here ({failure.what})"
            ),
        )
    listed = rbac._as_mappings(machines)
    return Finding(
        question,
        measured=True,
        answer={"count": len(listed)},
        note="names withheld; the count is what the verdict turns on",
    )


def read_quota(
    runner: Callable[[Sequence[str]], Any], rbac: Any, *, location: str
) -> Finding:
    """Whether the region has room for the size the dev-host definition names."""
    question = f"is there {HOST_VM_SIZE} quota in {location}"
    try:
        usage = runner(["vm", "list-usage", "--location", location])
    except rbac.AzureReadFailure as failure:
        return Finding(
            question, measured=False, answer=None, note=f"az did not answer ({failure.what})"
        )
    for entry in rbac._as_mappings(usage):
        name = entry.get("name")
        value = name.get("value") if isinstance(name, Mapping) else None
        if str(value or "").strip().lower() != HOST_QUOTA_FAMILY.lower():
            continue
        try:
            limit = int(entry.get("limit", 0))
            current = int(entry.get("currentValue", 0))
        except (TypeError, ValueError):
            return Finding(
                question,
                measured=False,
                answer=None,
                note="the quota entry did not carry readable numbers",
            )
        return Finding(
            question,
            measured=True,
            answer={
                "family": HOST_QUOTA_FAMILY,
                "limit_vcpus": limit,
                "in_use_vcpus": current,
                "free_vcpus": limit - current,
                "enough_for_one_host": (limit - current) >= HOST_VCPUS,
            },
        )
    return Finding(
        question,
        measured=True,
        answer={"family": HOST_QUOTA_FAMILY, "enough_for_one_host": False},
        note=(
            "the family is not in this subscription's usage list at all, which "
            "Azure reports for a family with no allocation in the region"
        ),
    )


def _list_assignments(
    runner: Callable[[Sequence[str]], Any], rbac: Any, *, principal: str
) -> tuple[list[Mapping[str, Any]], bool]:
    """Every assignment this principal holds, group-inherited ones included.

    ``--include-groups`` is asked for first and dropped if the installed CLI
    will not take it. It matters in one direction only: without it, a grant the
    identity holds through a group is invisible, and this survey's "no" is about
    to be quoted as the reason for a role request. A "no" that has not looked at
    group membership is a weaker "no", so which of the two ran is reported.
    """
    base = ["role", "assignment", "list", "--all", "--assignee", principal]
    try:
        return rbac._as_mappings(runner([*base, "--include-groups"])), True
    except rbac.AzureReadFailure:
        return rbac._as_mappings(runner(base)), False


def read_permissions(
    runner: Callable[[Sequence[str]], Any], rbac: Any, *, principal: str
) -> Finding:
    """Which of the actions a deployment performs this identity's roles permit."""
    question = "can this identity already perform the writes a host needs"
    if not principal:
        return Finding(
            question,
            measured=False,
            answer=None,
            note="no principal id was available to ask about",
        )
    try:
        assignments, groups_included = _list_assignments(
            runner, rbac, principal=principal
        )
    except rbac.AzureReadFailure as failure:
        return Finding(
            question, measured=False, answer=None, note=f"az did not answer ({failure.what})"
        )

    definitions: list[Mapping[str, Any]] = []
    for definition_id in sorted(
        {rbac._definition_id_of(item) for item in assignments} - {""}
    ):
        try:
            definitions.extend(
                rbac._as_mappings(
                    runner(["role", "definition", "list", "--name", definition_id])
                )
            )
        except rbac.AzureReadFailure:
            # One unreadable definition is not the whole answer, but it does
            # mean a "no" below could be wrong, so it is recorded as such.
            return Finding(
                question,
                measured=False,
                answer=None,
                note=(
                    "at least one role definition could not be read, so an "
                    "answer here would be a guess about what the role allows"
                ),
            )

    permitted = {
        needed.action: _permits(definitions, needed.action, rbac)
        for needed in actions_measured()
    }
    blocked = sorted(
        needed.action
        for needed in actions_that_block()
        if not permitted[needed.action]
    )
    return Finding(
        question,
        measured=True,
        answer={
            "assignments_held": len(assignments),
            "permits": permitted,
            "permits_every_action_a_deployment_would_take": not blocked,
            "actions_measured": len(permitted),
            "blocking_actions_not_permitted": blocked,
            "scopes": {
                needed.action: needed.scope for needed in actions_measured()
            },
            "measured_but_not_blocking": {
                needed.action: needed.only_if
                for needed in actions_measured()
                if not needed.always
            },
        },
        note=(
            ""
            if groups_included
            else (
                "the installed az would not take --include-groups, so a grant "
                "held through a group membership would not appear here"
            )
        ),
    )


# -------------------------------------------------------------------------
# The verdict
# -------------------------------------------------------------------------


def decide(findings: Mapping[str, Finding]) -> dict[str, Any]:
    """Turn the findings into one of four answers, and say why.

    The ordering is deliberate. An unmeasured read outranks every conclusion,
    because a survey that could not see is not a survey that saw nothing. An
    existing machine outranks the permission question, because if a host is
    already there then nothing needs creating and the roles to create one are
    beside the point.
    """
    unmeasured = sorted(name for name, f in findings.items() if not f.measured)
    if unmeasured:
        return {
            "verdict": VERDICT_NOT_MEASURED,
            "because": (
                "these reads did not complete, so nothing here is evidence of "
                "absence: " + ", ".join(unmeasured)
            ),
            "what_would_have_to_change": [],
        }

    hosts = findings["existing_hosts"].answer or {}
    if int(hosts.get("count", 0)) > 0:
        return {
            "verdict": VERDICT_HOST_EXISTS,
            "because": (
                f"{hosts['count']} virtual machine(s) already exist in this "
                "subscription, so no machine needs creating. Whether one of "
                "them can boot a guest is C2's question, not this one's"
            ),
            "what_would_have_to_change": [],
        }

    missing: list[str] = []
    provider = findings["provider"].answer or {}
    if not provider.get("registered"):
        missing.append(
            f"{COMPUTE_PROVIDER} is {provider.get('registration_state') or 'unknown'} "
            "in this subscription and would have to be registered"
        )
    quota = findings["quota"].answer or {}
    if not quota.get("enough_for_one_host"):
        missing.append(
            f"the region has {quota.get('free_vcpus', 0)} free vCPUs in "
            f"{HOST_QUOTA_FAMILY} and one host needs {HOST_VCPUS}, so a quota "
            "increase would have to be requested"
        )
    permissions = findings["permissions"].answer or {}
    denied = list(permissions.get("blocking_actions_not_permitted") or [])
    if denied:
        missing.append(
            "this identity's roles do not permit: " + ", ".join(denied)
        )
    # Held apart from ``missing`` on purpose. A deployment under the template's
    # defaults never reaches these, so they must neither block a verdict on
    # their own nor pad the list somebody takes to the subscription owner.
    would_also_be_needed = [
        f"{action}, but only if {why}"
        for action, why in sorted(
            (permissions.get("measured_but_not_blocking") or {}).items()
        )
        if not (permissions.get("permits") or {}).get(action, True)
    ]

    if missing:
        return {
            "verdict": VERDICT_BLOCKED,
            "because": (
                "a host could not be created here under the permissions and "
                "capacity that exist today"
            ),
            "what_would_have_to_change": missing,
            "would_also_be_needed_under_other_options": would_also_be_needed,
            "and_note": (
                "this is a report, not a request. Each item above is an access "
                "or capacity change and belongs to whoever owns the "
                "subscription, so it is named here and left undone"
            ),
        }

    measured_count = int(permissions.get("actions_measured") or 0)
    return {
        "verdict": VERDICT_WITHIN_PERMISSIONS,
        "because": (
            "the provider is registered, the region has room for one "
            f"{HOST_VM_SIZE}, and this identity's existing roles permit every "
            f"one of the {measured_count} actions a deployment would take. No "
            "access change is needed to put a host here"
        ),
        "what_would_have_to_change": [],
        "would_also_be_needed_under_other_options": would_also_be_needed,
    }


def survey(
    *,
    runner: Callable[[Sequence[str]], Any] | None = None,
    rbac: Any = None,
    location: str = DEFAULT_LOCATION,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Ask every question once and report the answers with a verdict."""
    rbac = rbac or _rbac_module()
    run = runner or rbac._default_runner
    environment = env if env is not None else os.environ
    principal = (environment.get("AZURE_CLIENT_ID") or "").strip()

    findings = {
        "session": read_session(run, rbac),
        "provider": read_provider(run, rbac),
        "existing_hosts": read_existing_hosts(run, rbac),
        "quota": read_quota(run, rbac, location=location),
        "permissions": read_permissions(run, rbac, principal=principal),
    }
    report: dict[str, Any] = {
        "artifact": "agentic-v2-boot-host-survey",
        # 1.1 widened the measured action list from three writes to every
        # action the host definition performs, and split the answer by scope.
        "artifact_version": "1.1",
        "question": (
            "could the subscription the model deployment lives in host a "
            "Firecracker guest, under permissions that already exist"
        ),
        "is_not": [
            "a deployment",
            "a role request",
            "a measurement that any machine here can actually boot a guest",
        ],
        "reads_only": True,
        "location_asked_about": location,
        "host_definition": {
            "from": "infra/dev-host/main.bicep",
            "vm_size": HOST_VM_SIZE,
            "vcpus": HOST_VCPUS,
            "quota_family": HOST_QUOTA_FAMILY,
            "actions_it_performs": [
                {
                    "action": needed.action,
                    "why": needed.why,
                    "scope": needed.scope,
                    "only_if": needed.only_if,
                }
                for needed in actions_measured()
            ],
        },
        "findings": {name: f.as_dict() for name, f in findings.items()},
    }
    report.update(decide(findings))
    return report


# -------------------------------------------------------------------------
# Output
# -------------------------------------------------------------------------


def render(report: Mapping[str, Any]) -> str:
    lines = [
        "Boot-host survey of the subscription the model deployment lives in",
        "=" * 66,
        f"verdict   {report['verdict']}",
        f"because   {report['because']}",
        "",
        f"asked about {report['location_asked_about']}, for one "
        f"{report['host_definition']['vm_size']} as "
        f"{report['host_definition']['from']} defines it",
        "",
    ]
    for name, finding in report["findings"].items():
        mark = "ok " if finding["measured"] else "?? "
        lines.append(f"  {mark}{name:<18} {finding['question']}")
        lines.append(f"       {json.dumps(finding['answer'], sort_keys=True)}")
        if finding["note"]:
            lines.append(f"       note: {finding['note']}")
    if report["what_would_have_to_change"]:
        lines.append("")
        lines.append("What would have to change, reported and not performed:")
        for item in report["what_would_have_to_change"]:
            lines.append(f"  - {item}")
        lines.append(f"  {report.get('and_note', '')}")
    if report.get("would_also_be_needed_under_other_options"):
        lines.append("")
        lines.append("Not needed for this deployment, and not part of the ask:")
        for item in report["would_also_be_needed_under_other_options"]:
            lines.append(f"  - {item}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Survey, never deploy.")
    parser.add_argument("--location", default=DEFAULT_LOCATION)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    try:
        rbac = _rbac_module()
        report = survey(rbac=rbac, location=args.location)
    except SurveyRefused as refused:
        print(f"The survey did not run: {refused}")
        return 1

    secrets = rbac.collect_secrets(os.environ)
    text = rbac.redact(
        json.dumps(report, indent=2, sort_keys=True) if args.as_json else render(report),
        secrets,
    )
    leaked = rbac.leaked_placeholders(text, secrets)
    if leaked:
        # Printing the report anyway would be the one unrecoverable mistake this
        # script can make, so it prints nothing at all.
        print(f"FATAL: redaction failed for {', '.join(leaked)}; nothing printed")
        return 1

    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
