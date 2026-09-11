#!/usr/bin/env python3
"""Record what throughput the deployment is *declared* to have, without naming it.

Why this exists
---------------
Run ``34540053904`` (exp034, thirty tasks) was dispatched to narrow one
question: of request rate, a token reservation, the deployment's throughput and
the interval between calls, which one is refusing our requests. Response
evidence ruled out two. It could not touch the other two, for two reasons, and
this script is the second of them.

The first was that the cost ledger recorded how many tokens each call used and
never recorded when, so the tokens settled in the window before a refusal could
not be counted. That is fixed: ``cost_calls`` now carries ``reserved_at`` and
``concluded_at``, and a rolling window can be drawn.

The second is that a count in that window means nothing on its own. Two hundred
thousand tokens a minute is either comfortably inside the ceiling or over it,
and nothing in this repository recorded which. A numerator without a denominator
is not a measurement.

So this reads the denominator: what Azure says the deployment's limits are.

What it reads, and what it refuses to infer
-------------------------------------------
``properties.rateLimits`` is Azure stating a limit -- a count, a key and the
number of seconds it renews over. Those are converted to per-minute figures,
which is arithmetic on quantities the payload supplies.

``sku.capacity`` is recorded exactly as returned and is deliberately NOT turned
into tokens per minute. The conversion is real but it is a per-model convention
that lives in documentation, not in the payload: the same integer means
different throughput for different models, and multiplying it by a remembered
constant would produce a number indistinguishable in the report from one Azure
actually stated. A figure that looks measured and was guessed is worse than an
absent one, because the absent one gets chased.

If the deployment states no rate limits at all, the verdict says so and the
per-minute fields stay null. This tool would rather report that the denominator
is unavailable than supply one.

A caveat that belongs in the report, not in a footnote
------------------------------------------------------
A shared-capacity sku -- anything Global or shared-standard -- can refuse a
request while the deployment is under its own declared limit, because the
capacity it draws on is not exclusively this deployment's. So a declared ceiling
bounds the question rather than settling it: usage measured *at* the ceiling
implicates the deployment's throughput, and usage measured well under it does
not exonerate the deployment. The verdict carries the sku name so the next
reader can tell which of those they are looking at.

Where it has to be run
----------------------
Through its workflow, in CI. It reads whatever subscription and identity the
``az`` session holds, and a login taken on a development box or in an agent
container is a different one of each -- so the account is never looked up and
the run stops at ``control_plane_read_never_completed``, which says nothing was
measured. That is the honest outcome and it is kept strictly apart from "az
answered and the deployment was not there", because the two license opposite
conclusions.

This read may also simply be refused. The RBAC diagnostic beside it exists
because this identity was already refused at the Foundry project, and a reader
role on the account is not implied by anything. A refusal is recorded as
"not readable with the permissions we have" and is not a reason to ask for more.

What it does and does not do
----------------------------
Every call it makes is an ARM control-plane READ. It never creates, updates or
deletes anything, and it never calls a model endpoint, so running it cannot
re-trigger the refusal it exists to explain and cannot spend money.

What it prints
--------------
The deployment name, its model name and version, its sku name, and the limits
Azure stated. Those are values this repository already commits to git in the
experiment YAML. It never prints the subscription id, the resource group, the
account name, the project name, the principal object id or the tenant id, and
it refuses to print at all if a known secret value survives into the report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Callable

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)

from core.azure_ai_clients import (  # noqa: E402
    ROUTE_PROFILE_ENV,
    AzureAIRouteSettings,
    ClassifiedEndpoint,
)
from core.azure_control_plane import (  # noqa: E402
    AzRunner,
    AzureReadFailure,
    as_mappings,
    collect_secrets,
    default_runner,
    leaked_placeholders,
    redact,
    resolve_resource_group,
)

SECONDS_PER_MINUTE = 60

# The rate-limit keys Azure uses. ``key`` is free-ish text -- deployments have
# been seen with "request", "token" and per-feature variants -- so these are
# matched as prefixes rather than equality, and anything unrecognised is kept in
# the report under its own name rather than dropped. A limit nobody knows how to
# read is still a limit, and dropping it would quietly shrink the evidence.
TOKEN_LIMIT_PREFIX = "token"
REQUEST_LIMIT_PREFIX = "request"

# Sku names whose capacity is drawn from a pool this deployment does not own.
# Matched case-insensitively as substrings, because Microsoft has shipped
# "GlobalStandard", "GlobalBatch", "DataZoneStandard" and more, and the property
# they share is the one that matters here.
SHARED_CAPACITY_MARKERS: tuple[str, ...] = ("global", "datazone", "shared")

# What a property name has to look like before it is repeated back. Azure's own
# schema names all pass; anything else is withheld rather than printed.
SCHEMA_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

VERDICT_CAPACITY_RECORDED = "capacity_recorded"
VERDICT_LIMITS_NOT_STATED = "limits_not_stated"
VERDICT_DEPLOYMENT_ABSENT = "deployment_absent_or_withheld"
VERDICT_CANNOT_READ_ACCOUNT = "cannot_read_control_plane"
VERDICT_NEVER_COMPLETED = "control_plane_read_never_completed"
VERDICT_UNMEASURED = "unmeasured"


def _utc_now() -> datetime:
    """The wall clock, in UTC.

    The same choice, for the same reason, as the ledger this figure is the
    denominator for: a capacity read and the calls it will be divided into
    happen in different processes, and only a wall clock orders those against
    each other. It is stamped at all because a deployment's limits can be
    changed between the read and the run, and a denominator with no date cannot
    be told apart from one that is still true.
    """
    return datetime.now(timezone.utc)


def _stamp(clock: Callable[[], datetime]) -> str:
    moment = clock()
    if not isinstance(moment, datetime):
        raise ValueError("the clock returned something that is not a datetime")
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError(
            "the clock returned a datetime with no timezone; a moment without "
            "one cannot be compared against a moment from another process"
        )
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


# -------------------------------------------------------------------------
# Reading the limits out of what Azure returned
# -------------------------------------------------------------------------


def per_minute(count: Any, renewal_period_seconds: Any) -> float | None:
    """Scale a stated count over a stated period to one minute, or decline.

    Declines rather than assumes whenever either half is missing or unusable.
    A limit whose renewal period Azure did not state is not a per-minute limit
    with an obvious period; it is a limit of unknown shape, and the only honest
    rendering of it is the raw pair, which the caller keeps.
    """
    if isinstance(count, bool) or not isinstance(count, (int, float)):
        return None
    if isinstance(renewal_period_seconds, bool) or not isinstance(
        renewal_period_seconds, (int, float)
    ):
        return None
    if count < 0 or renewal_period_seconds <= 0:
        return None
    return float(count) * SECONDS_PER_MINUTE / float(renewal_period_seconds)


def normalize_rate_limits(payload: Any) -> list[dict[str, Any]]:
    """Every rate limit Azure stated, with a per-minute figure where possible."""
    limits: list[dict[str, Any]] = []
    for entry in as_mappings(payload if isinstance(payload, list) else []):
        key = entry.get("key")
        count = entry.get("count")
        period = entry.get("renewalPeriod")
        limits.append(
            {
                "key": str(key) if isinstance(key, str) and key.strip() else None,
                "count": count if isinstance(count, (int, float)) else None,
                "renewal_period_seconds": (
                    period if isinstance(period, (int, float)) else None
                ),
                "per_minute": per_minute(count, period),
            }
        )
    return limits


def _first_per_minute(limits: Sequence[Mapping[str, Any]], prefix: str) -> float | None:
    """The per-minute figure for the first limit whose key starts with ``prefix``."""
    for limit in limits:
        key = limit.get("key")
        if not isinstance(key, str):
            continue
        if key.strip().lower().startswith(prefix) and limit.get("per_minute") is not None:
            value = limit["per_minute"]
            if isinstance(value, (int, float)):
                return float(value)
    return None


def draws_on_shared_capacity(sku_name: Any) -> bool | None:
    """Whether this sku's throughput is pooled. ``None`` when the sku is unnamed.

    ``None`` rather than ``False``: not knowing which kind of sku this is, and
    knowing it is a dedicated one, support different readings of a refusal.
    """
    if not isinstance(sku_name, str) or not sku_name.strip():
        return None
    lowered = sku_name.strip().lower()
    return any(marker in lowered for marker in SHARED_CAPACITY_MARKERS)


def schema_keys(payload: Any) -> list[str]:
    """The property names Azure returned, so an empty answer is diagnosable.

    "This deployment declares no limits" and "the limits are under a name this
    tool does not look for" produce the same empty report, and telling them
    apart afterwards would otherwise mean reading the payload -- which means
    another run, in CI, because that is the only place the account is visible.
    Recording the names it did carry settles it from the first run.

    Names only, sorted, and only ones shaped like schema identifiers. These are
    Azure's own property names rather than anything anybody chose, but the
    filter is cheap and this report's whole promise is that nothing chosen by a
    person survives into it.
    """
    if not isinstance(payload, Mapping):
        return []
    return sorted(
        key
        for key in payload
        if isinstance(key, str) and SCHEMA_KEY_PATTERN.match(key)
    )


def read_deployments(
    runner: AzRunner, *, account: str, resource_group: str, subscription_id: str
) -> list[Mapping[str, Any]]:
    """Every deployment on the account, as the control plane reports them."""
    payload = runner(
        [
            "cognitiveservices",
            "account",
            "deployment",
            "list",
            "--name",
            account,
            "--resource-group",
            resource_group,
            "--subscription",
            subscription_id,
        ]
    )
    return as_mappings(payload)


def select_deployment(
    deployments: Sequence[Mapping[str, Any]], *, deployment: str
) -> Mapping[str, Any]:
    """The named deployment, or a completed failure saying it was not there.

    Matched case-insensitively. Azure preserves the case a deployment was
    created with and the experiment YAML records the case somebody typed; a
    mismatch between the two is a spelling difference, not a missing resource,
    and reporting it as a missing resource would send the next reader looking
    for a deployment that exists.
    """
    wanted = deployment.strip().lower()
    for entry in deployments:
        name = entry.get("name")
        if isinstance(name, str) and name.strip().lower() == wanted:
            return entry
    raise AzureReadFailure(
        "the named deployment", exit_code=None, completed=True
    )


# -------------------------------------------------------------------------
# The report
# -------------------------------------------------------------------------


def _account_for_capacity(
    settings: AzureAIRouteSettings,
) -> tuple[ClassifiedEndpoint, str]:
    """Which endpoint's account holds the deployment, and which one it was.

    A deployment lives on a Cognitive Services account, never on a project, so
    the project endpoint is not a candidate even under the project-ci profile --
    under that profile the route already derives the account endpoint, and this
    takes the same one the run would call.
    """
    if settings.direct_v1 is not None:
        return settings.direct_v1, settings.direct_v1.kind.value
    if settings.legacy is not None:
        return settings.legacy, settings.legacy.kind.value
    raise ValueError(
        "the route resolved no account endpoint, so there is no account to read "
        "a deployment's capacity from"
    )


def measure(
    env: Mapping[str, str],
    *,
    deployment: str,
    runner: AzRunner,
    clock: Callable[[], datetime] = _utc_now,
) -> dict[str, Any]:
    """Read the deployment's declared limits and say how far the read got."""
    if not isinstance(deployment, str) or not deployment.strip():
        raise ValueError("a deployment name is required")

    # from_env is what the run itself uses, so this reads the account the run
    # actually calls rather than a rule retyped here that agrees until one of
    # the two is edited.
    settings = AzureAIRouteSettings.from_env(env)
    endpoint, account_source = _account_for_capacity(settings)

    subscription_id = env.get("AZURE_SUBSCRIPTION_ID", "").strip()
    if not subscription_id:
        raise ValueError("AZURE_SUBSCRIPTION_ID is required")

    problems: list[str] = []
    report: dict[str, Any] = {
        "measured_at": _stamp(clock),
        "route_profile": settings.profile.value,
        "account_source": account_source,
        "deployment": deployment.strip(),
        "model_name": None,
        "model_version": None,
        "sku_name": None,
        "sku_capacity": None,
        # Recorded so no reader has to wonder whether the null below is an
        # oversight. The unit is not in the payload, so it is not in the report.
        "sku_capacity_unit_stated_by_azure": False,
        "draws_on_shared_capacity": None,
        "tokens_per_minute": None,
        "requests_per_minute": None,
        "rate_limits": [],
        "properties_seen": [],
        "deployments_seen": None,
        "read_failures": problems,
        "verdict": VERDICT_UNMEASURED,
        # The account name lives inside the endpoint secret rather than in a
        # variable of its own, so redacting the endpoint string would not catch
        # it on its own.
        "secret_values": {endpoint.account: "<accountName>"},
    }

    try:
        resource_group = resolve_resource_group(
            runner, account=endpoint.account, subscription_id=subscription_id
        )
    except AzureReadFailure as failure:
        if failure.completed:
            problems.append(
                "Azure answered and the account was not in the answer, so this "
                "identity cannot see it and no deployment could be read "
                f"({failure.what})"
            )
            report["verdict"] = VERDICT_CANNOT_READ_ACCOUNT
        else:
            problems.append(
                "az did not answer the account lookup, which is how a "
                "subscription this session is not signed into fails, so the "
                f"account was never looked up and nothing was measured "
                f"({failure.what})"
            )
            report["verdict"] = VERDICT_NEVER_COMPLETED
        return report

    # Read from Azure rather than from the environment, so collect_secrets could
    # not have known it.
    report["secret_values"][resource_group] = "<resourceGroup>"

    try:
        deployments = read_deployments(
            runner,
            account=endpoint.account,
            resource_group=resource_group,
            subscription_id=subscription_id,
        )
    except AzureReadFailure as failure:
        problems.append(
            "az did not answer the deployment list, so this account's "
            "deployments were never enumerated and nothing was measured "
            f"({failure.what})"
        )
        report["verdict"] = VERDICT_NEVER_COMPLETED
        return report

    # A count, never the names. How many deployments an account holds is not an
    # identifier; what they are called is chosen by the owner and can be.
    report["deployments_seen"] = len(deployments)

    try:
        entry = select_deployment(deployments, deployment=deployment)
    except AzureReadFailure as failure:
        problems.append(
            "Azure answered with this account's deployments and the named one "
            "was not among them, so it is either absent or withheld from this "
            f"identity ({failure.what})"
        )
        report["verdict"] = VERDICT_DEPLOYMENT_ABSENT
        return report

    properties = entry.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}
    model = properties.get("model")
    model = model if isinstance(model, Mapping) else {}
    sku = entry.get("sku")
    sku = sku if isinstance(sku, Mapping) else {}
    report["properties_seen"] = schema_keys(properties)

    name = model.get("name")
    version = model.get("version")
    report["model_name"] = name if isinstance(name, str) and name.strip() else None
    report["model_version"] = (
        version if isinstance(version, str) and version.strip() else None
    )

    sku_name = sku.get("name")
    sku_capacity = sku.get("capacity")
    report["sku_name"] = (
        sku_name if isinstance(sku_name, str) and sku_name.strip() else None
    )
    report["sku_capacity"] = (
        sku_capacity
        if isinstance(sku_capacity, (int, float)) and not isinstance(sku_capacity, bool)
        else None
    )
    report["draws_on_shared_capacity"] = draws_on_shared_capacity(sku_name)

    limits = normalize_rate_limits(properties.get("rateLimits"))
    report["rate_limits"] = limits
    report["tokens_per_minute"] = _first_per_minute(limits, TOKEN_LIMIT_PREFIX)
    report["requests_per_minute"] = _first_per_minute(limits, REQUEST_LIMIT_PREFIX)

    if report["tokens_per_minute"] is None and report["requests_per_minute"] is None:
        problems.append(
            "the deployment was found and states no rate limit this tool can "
            "read, so the denominator is unavailable. sku.capacity is recorded "
            "above and is deliberately not converted: the payload does not say "
            "what one unit of it buys"
        )
        report["verdict"] = VERDICT_LIMITS_NOT_STATED
        return report

    report["verdict"] = VERDICT_CAPACITY_RECORDED
    return report


def render(report: Mapping[str, Any]) -> str:
    """The report as prose, with every figure labelled by where it came from."""
    lines: list[str] = []
    lines.append("azure deployment capacity")
    lines.append(f"  read at:        {report.get('measured_at')}")
    lines.append(f"  route profile:  {report.get('route_profile')}")
    lines.append(f"  account from:   {report.get('account_source')} endpoint")
    lines.append(f"  deployment:     {report.get('deployment')}")
    lines.append(f"  verdict:        {report.get('verdict')}")

    model_name = report.get("model_name")
    if model_name:
        lines.append("")
        lines.append(f"  model:          {model_name} {report.get('model_version') or ''}".rstrip())

    sku_name = report.get("sku_name")
    if sku_name or report.get("sku_capacity") is not None:
        lines.append(f"  sku:            {sku_name or 'unnamed'}")
        lines.append(
            f"  sku.capacity:   {report.get('sku_capacity')} "
            "(raw; Azure does not state the unit, so it is not converted)"
        )
    shared = report.get("draws_on_shared_capacity")
    if shared is True:
        lines.append(
            "  NOTE: this sku draws on pooled capacity, so it can refuse a "
            "request while under its own declared limit. A declared ceiling "
            "bounds the question and does not settle it."
        )
    elif shared is None and sku_name:
        lines.append(
            "  NOTE: the sku was not named, so whether its capacity is pooled "
            "is unknown."
        )

    limits = list(report.get("rate_limits") or ())
    if limits:
        lines.append("")
        lines.append("limits Azure stated:")
        for limit in limits:
            rate = limit.get("per_minute")
            shown = "not convertible" if rate is None else f"{rate:g} per minute"
            lines.append(
                f"  - {limit.get('key') or 'unnamed'}: {limit.get('count')} "
                f"per {limit.get('renewal_period_seconds')}s  ->  {shown}"
            )

    # Only when there is nothing to show instead. A reader who got their
    # denominator does not need the schema; a reader who did not has one
    # question, and this is the answer to it.
    properties_seen = list(report.get("properties_seen") or ())
    if properties_seen and not limits:
        lines.append("")
        lines.append("no limits were stated. the deployment's properties carried:")
        lines.append(f"  {', '.join(properties_seen)}")
        lines.append(
            "  (listed because a deployment that declares no limits and a "
            "payload that declares them under a name this tool does not look "
            "for read identically)"
        )

    lines.append("")
    lines.append("the denominator this run recorded:")
    tokens = report.get("tokens_per_minute")
    requests = report.get("requests_per_minute")
    lines.append(
        f"  tokens/minute:   {'unavailable' if tokens is None else f'{tokens:g}'}"
    )
    lines.append(
        f"  requests/minute: {'unavailable' if requests is None else f'{requests:g}'}"
    )

    seen = report.get("deployments_seen")
    if seen is not None:
        lines.append("")
        lines.append(f"deployments on the account: {seen} (names withheld)")

    failures = list(report.get("read_failures") or ())
    if failures:
        lines.append("")
        lines.append("reads that did not succeed:")
        lines.extend(f"  - {entry}" for entry in failures)

    lines.append("")
    lines.append(
        "This read was control-plane only. It called no model endpoint, so it "
        "neither reproduces a refusal nor spends anything."
    )
    return "\n".join(lines)


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read a deployment's declared limits")
    parser.add_argument(
        "--deployment",
        required=True,
        help="The deployment name, as the experiment YAML records it",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the redacted report as JSON instead of prose",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Write the redacted JSON report here as well, so a run can keep it "
            "beside the ledger the figure is the denominator for"
        ),
    )
    parser.add_argument(
        "--require-limits",
        action="store_true",
        help=(
            "Exit non-zero unless Azure stated a limit. Off by default so that "
            "reporting an unavailable denominator is not an error"
        ),
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    runner: AzRunner | None = None,
    clock: Callable[[], datetime] | None = None,
    stream: Any = None,
) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    values = os.environ if env is None else env
    out = sys.stdout if stream is None else stream

    try:
        report = measure(
            values,
            deployment=args.deployment,
            runner=runner or default_runner,
            clock=clock or _utc_now,
        )
    except ValueError as exc:
        # Safe to print: these messages name environment variables and settings,
        # never their values.
        print(f"deployment capacity read refused to run: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("deployment capacity read failed", file=sys.stderr)
        return 2

    extra = dict(report.pop("secret_values", {}) or {})
    secrets = collect_secrets(values, extra=extra)
    serialized = json.dumps(report, indent=2, sort_keys=True)
    body = serialized if args.json else render(report)
    body = redact(body, secrets)

    survivors = leaked_placeholders(body, secrets)
    if survivors:
        # Fail closed. A report that still carries an identifier is worse than
        # no report, because the log is public and cannot be unpublished.
        print(
            "deployment capacity read withheld its report: redaction did not "
            f"clear {len(survivors)} identifier(s)",
            file=sys.stderr,
        )
        return 3

    if args.output:
        payload = redact(serialized, secrets)
        if leaked_placeholders(payload, secrets):
            print(
                "deployment capacity read withheld its file: redaction did not "
                "clear every identifier",
                file=sys.stderr,
            )
            return 3
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")

    print(body, file=out)

    if args.require_limits and report["verdict"] != VERDICT_CAPACITY_RECORDED:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
