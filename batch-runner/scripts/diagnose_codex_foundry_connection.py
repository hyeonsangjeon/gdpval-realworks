#!/usr/bin/env python3
"""Ask one Foundry deployment one question through the real Codex runtime.

Three things about the Codex run place have never been observed, and
``core.execution_environment_readiness`` says so in three sentences that no
amount of reading can clear: the auth command has never had a token *accepted*;
which API contract this deployment answers Codex's Responses payload on is
unmeasured; and whether the pinned Codex version's request is accepted by this
resource's model version and content filters is a separate question again. Only
a request settles any of them, so this is that request.

What this is, precisely
-----------------------

One turn, one deployment, one fixed prompt of a few words, driven through
``core.codex_runner.CodexAgentRunner`` so that the runtime, the isolated
environment, the provider table, the sandbox preset and the approval mode are
*the ones a real run uses* rather than a convenient copy of them. Nothing is
turned off to make it pass. If it needs something switched off, that is the
finding.

What it deliberately is **not**
-------------------------------

It is not proof that the run place works. The prompt asks for one word and
forbids the agent to run anything, so a success here says the model leg
answered — and says nothing whatever about the tool leg. Those are separate
facts and the record keeps them separate: ``tool_execution_observed`` is
``false`` in every record this script writes, and ``not_established`` spells out
what a green verdict still does not buy. The sandbox leg is proven somewhere
else, by ``tests/test_codex_runtime_end_to_end.py`` under
``CODEX_SANDBOX_MUST_RUN=1``, and neither result substitutes for the other.

It also does not clear the readiness blockers. Writing evidence and acting on
evidence are different steps and a diagnostic that quietly did the second would
be a toggle with a diagnostic's name on it.

Why the stream is consumed here rather than by the SDK
------------------------------------------------------

``TurnHandle.run()`` collects the turn and, on failure, raises
``RuntimeError(turn.error.message)`` — see ``openai_codex/_run.py``. That throws
away ``turn.error.codex_error_info``, which is the only structured statement of
*why*: an ``unauthorized`` where we would otherwise guess from prose, a
``badRequest`` distinguished from a 404, an upstream ``httpStatusCode``
forwarded from the provider. Recovering it after the fact would need a second
request, and a second request costs money to learn something the first one
already said. So this consumes ``TurnHandle.stream()`` itself and keeps the
error object.

What is never written down
--------------------------

The endpoint URL, the account name, the project name, and anything that could
carry a token. The endpoint is recorded as its kind, its path, and a hash of
its host; every free-text message from the runtime goes through
:func:`build_redactor` first, which blanks URLs, JWT-shaped strings, and the
literal values of the identity variables this job runs with. Those variables
are repository *variables*, not secrets, so Actions will not mask them — which
means the discipline has to be here.

Usage::

    python -m scripts.diagnose_codex_foundry_connection --deployment gpt-5.4
    python -m scripts.diagnose_codex_foundry_connection --deployment gpt-5.4 \
        --send-request --out docs/codex_foundry_connection.json

Without ``--send-request`` nothing is sent: the plan is printed, fingerprint
included, so the request can be fixed before it is paid for.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from enum import Enum
from typing import Any, Callable, Iterable, Iterator

_HERE = os.path.dirname(os.path.abspath(__file__))
_BATCH_RUNNER = os.path.dirname(_HERE)
if _BATCH_RUNNER not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, _BATCH_RUNNER)

from core.azure_ai_clients import (  # noqa: E402
    DEPRECATED_ENDPOINT_ENV,
    DIRECT_ENDPOINT_ENV,
    EXPECTED_DIRECT_ACCOUNT_ENV,
    EXPECTED_LEGACY_ACCOUNT_ENV,
    EXPECTED_PROJECT_ACCOUNT_ENV,
    EXPECTED_PROJECT_NAME_ENV,
    LEGACY_ENDPOINT_ENV,
    PROJECT_ENDPOINT_ENV,
    AzureAIRouteSettings,
    classify_endpoint,
)
from core.codex_runtime_config import (  # noqa: E402
    AUTH_RETRY_REQUESTS_NOT_REMOVED_BY_PINNING,
    PINNED_CODEX_CLI_DISTRIBUTION,
    PINNED_CODEX_CLI_VERSION,
    PINNED_CODEX_SDK_DISTRIBUTION,
    PINNED_CODEX_SDK_VERSION,
    SUPPORTED_WIRE_API,
    CodexProviderConfigurationError,
    CodexProviderSettings,
    CodexRuntimeUnavailable,
    installed_cli_version,
    installed_sdk_version,
)

#: The record format. Bumped if a field changes meaning, so a reader can tell
#: an old record from a new one rather than mis-reading it.
#:
#: /2 changed ``request.retries_configured`` from the scalar ``0`` -- a claim
#: the plan made about itself and the runtime never saw -- to the two counters
#: actually written into the provider table, and added
#: ``request.retries_not_removed_by_pinning``. A ``/1`` record says nothing
#: about how many requests its turn made.
SCHEMA = "codex_foundry_connection/2"

# ── The verdict vocabulary ──────────────────────────────────────────────────
#
# Fixed, and fixed on purpose. A diagnostic whose vocabulary grows a term per
# run cannot be compared across runs, and the three readiness blockers this
# exists to settle are each a specific term below rather than "it worked".

#: The turn completed and the model answered. Says nothing about tools.
VERDICT_CONNECTED = "connected"
#: A token was minted and the provider refused it — 401, 403, ``unauthorized``.
VERDICT_AUTHENTICATION_REJECTED = "authentication_rejected"
#: The sign-in was fine and the *payload* was not — 400, ``badRequest``. This
#: is the wire-contract blocker, and it is why it must not be merged with the
#: one above: the fixes are in different files.
VERDICT_REQUEST_SHAPE_REJECTED = "request_shape_rejected"
#: 404. The route exists and the deployment named on it does not.
VERDICT_DEPLOYMENT_NOT_FOUND = "deployment_not_found"
#: 429 or ``serverOverloaded``. Nothing is wrong with the settings.
VERDICT_RATE_LIMITED = "rate_limited"
#: 5xx or ``internalServerError``. Also not a settings fault.
VERDICT_PROVIDER_SERVER_ERROR = "provider_server_error"
#: The connection never produced a status at all.
VERDICT_PROVIDER_UNREACHABLE = "provider_unreachable"
#: ``cyberPolicy`` — a content filter answered instead of the model.
VERDICT_CONTENT_FILTERED = "content_filtered"
#: ``usageLimitExceeded`` / ``sessionBudgetExceeded``. Quota, not compatibility.
VERDICT_QUOTA_EXHAUSTED = "quota_exhausted"
#: ``contextWindowExceeded``. Impossible for this prompt; kept so that seeing
#: it is a loud surprise rather than a silent "other".
VERDICT_CONTEXT_WINDOW_EXCEEDED = "context_window_exceeded"
#: ``sandboxError`` — the tool leg failed inside a probe that asked for no
#: tools, which would mean the runtime tried to sandbox something anyway.
VERDICT_SANDBOX_FAILED = "sandbox_failed"
#: The turn was sent and did not finish inside the fixed limit. The reservation
#: stays open: a cost may exist here that this run cannot measure.
VERDICT_TURN_TIMED_OUT = "turn_timed_out"
#: The pinned SDK or binary is missing or is the wrong version.
VERDICT_RUNTIME_UNAVAILABLE = "runtime_unavailable"
#: The runtime started and the session did not open, so nothing was sent.
VERDICT_SESSION_NOT_STARTED = "session_not_started"
#: The environment does not describe a deployment. Nothing was sent, and
#: nothing was substituted for the missing setting.
VERDICT_SETTINGS_INCOMPLETE = "settings_incomplete"
#: ``--send-request`` was not passed. The plan was computed; no request exists.
VERDICT_NOT_SENT = "not_sent"
#: A failure the structured error did not explain. Deliberately last, and
#: deliberately not a synonym for any of the above.
VERDICT_UNCLASSIFIED_FAILURE = "unclassified_failure"

VERDICTS: tuple[str, ...] = (
    VERDICT_CONNECTED,
    VERDICT_AUTHENTICATION_REJECTED,
    VERDICT_REQUEST_SHAPE_REJECTED,
    VERDICT_DEPLOYMENT_NOT_FOUND,
    VERDICT_RATE_LIMITED,
    VERDICT_PROVIDER_SERVER_ERROR,
    VERDICT_PROVIDER_UNREACHABLE,
    VERDICT_CONTENT_FILTERED,
    VERDICT_QUOTA_EXHAUSTED,
    VERDICT_CONTEXT_WINDOW_EXCEEDED,
    VERDICT_SANDBOX_FAILED,
    VERDICT_TURN_TIMED_OUT,
    VERDICT_RUNTIME_UNAVAILABLE,
    VERDICT_SESSION_NOT_STARTED,
    VERDICT_SETTINGS_INCOMPLETE,
    VERDICT_NOT_SENT,
    VERDICT_UNCLASSIFIED_FAILURE,
)

#: Verdicts that mean a request reached the provider and was answered by it,
#: whether or not the answer was the one we wanted. Only these settle anything
#: about the deployment; the rest are about us or about nothing having happened.
VERDICTS_THE_PROVIDER_ANSWERED: frozenset[str] = frozenset(
    {
        VERDICT_CONNECTED,
        VERDICT_AUTHENTICATION_REJECTED,
        VERDICT_REQUEST_SHAPE_REJECTED,
        VERDICT_DEPLOYMENT_NOT_FOUND,
        VERDICT_RATE_LIMITED,
        VERDICT_PROVIDER_SERVER_ERROR,
        VERDICT_CONTENT_FILTERED,
        VERDICT_QUOTA_EXHAUSTED,
        VERDICT_CONTEXT_WINDOW_EXCEEDED,
    }
)

#: What ``CodexErrorInfoValue`` says, mapped onto the vocabulary above.
_VERDICT_BY_ERROR_NAME: Mapping[str, str] = {
    "unauthorized": VERDICT_AUTHENTICATION_REJECTED,
    "badRequest": VERDICT_REQUEST_SHAPE_REJECTED,
    "serverOverloaded": VERDICT_RATE_LIMITED,
    "internalServerError": VERDICT_PROVIDER_SERVER_ERROR,
    "cyberPolicy": VERDICT_CONTENT_FILTERED,
    "usageLimitExceeded": VERDICT_QUOTA_EXHAUSTED,
    "sessionBudgetExceeded": VERDICT_QUOTA_EXHAUSTED,
    "contextWindowExceeded": VERDICT_CONTEXT_WINDOW_EXCEEDED,
    "sandboxError": VERDICT_SANDBOX_FAILED,
}


def verdict_for_http_status(status: int) -> str:
    """The HTTP status the provider returned, as one of the verdicts.

    Taken in preference to the error name whenever both are present: the name
    is Codex's summary of the status, and the status is the thing the provider
    actually said.
    """
    if status in (401, 403):
        return VERDICT_AUTHENTICATION_REJECTED
    if status == 404:
        return VERDICT_DEPLOYMENT_NOT_FOUND
    if status == 429:
        return VERDICT_RATE_LIMITED
    if 400 <= status < 500:
        return VERDICT_REQUEST_SHAPE_REJECTED
    if 500 <= status < 600:
        return VERDICT_PROVIDER_SERVER_ERROR
    return VERDICT_UNCLASSIFIED_FAILURE


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def read_codex_error_info(info: Any) -> tuple[str | None, int | None]:
    """Pull the error's name and any forwarded HTTP status out of the SDK type.

    ``CodexErrorInfo`` is a ``RootModel`` over an enum and five one-field
    models, four of which carry ``httpStatusCode``. Rather than name the five,
    this reads whatever single field the variant has and asks it for a status —
    so a variant added in a later SDK reports its name instead of being
    silently classified as "other".
    """
    if info is None:
        return None, None
    root = getattr(info, "root", info)

    if isinstance(root, Enum):
        return str(root.value), None

    name = type(root).__name__
    if name.endswith("CodexErrorInfo"):
        name = name[: -len("CodexErrorInfo")]

    status: int | None = None
    fields = getattr(root, "model_fields", None) or {}
    for field_name in fields:
        inner = getattr(root, field_name, None)
        candidate = getattr(inner, "http_status_code", None)
        if isinstance(candidate, int):
            status = candidate
            break

    return _snake(name), status


def classify_turn_error(error: Any) -> tuple[str, str | None, int | None]:
    """``(verdict, error_name, http_status)`` for one ``TurnError``.

    A turn that failed with no structured information at all is
    ``unclassified_failure`` and stays that way. Guessing a cause from the
    message text is exactly the kind of reading this whole script exists to
    replace.
    """
    if error is None:
        return VERDICT_UNCLASSIFIED_FAILURE, None, None
    name, status = read_codex_error_info(getattr(error, "codex_error_info", None))
    if status is not None:
        return verdict_for_http_status(status), name, status
    if name is not None:
        mapped = _VERDICT_BY_ERROR_NAME.get(name)
        if mapped is None:
            # The four structured variants without a status mean the request
            # never got one — the connection failed rather than being answered.
            if name.endswith("_failed") or name.endswith("_disconnected"):
                return VERDICT_PROVIDER_UNREACHABLE, name, None
            return VERDICT_UNCLASSIFIED_FAILURE, name, None
        return mapped, name, None
    return VERDICT_UNCLASSIFIED_FAILURE, None, None


# ── Keeping names out of the record ─────────────────────────────────────────

_URL = re.compile(r"https?://[^\s\"'<>)\]]+")
_JWT = re.compile(r"\bey[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.?[A-Za-z0-9_-]*")
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")

#: Repository variables that name the resource. Actions does not mask a
#: variable, so a runtime message that happened to quote one would otherwise
#: land in a public log verbatim.
IDENTITY_ENV_NAMES: tuple[str, ...] = (
    EXPECTED_DIRECT_ACCOUNT_ENV,
    EXPECTED_PROJECT_ACCOUNT_ENV,
    EXPECTED_PROJECT_NAME_ENV,
    EXPECTED_LEGACY_ACCOUNT_ENV,
)

#: Endpoint variables. These are *secrets*, so Actions masks the whole string —
#: but not the account and project names inside it, which a message can quote on
#: their own ("account X was not found"). So the names are pulled back out and
#: blanked individually, as ``azure_rbac_diagnostic.py`` does for the same
#: reason.
ENDPOINT_ENV_NAMES: tuple[str, ...] = (
    DIRECT_ENDPOINT_ENV,
    PROJECT_ENDPOINT_ENV,
    LEGACY_ENDPOINT_ENV,
    DEPRECATED_ENDPOINT_ENV,
)

MESSAGE_LIMIT = 400


def _names_in_endpoints(values: Mapping[str, str]) -> Iterator[str]:
    """The account and project names carried by whatever endpoints are set.

    This is what lets the workflow *not* pass the four identity variables. It
    must not: a step's ``env:`` block is reprinted verbatim in the log, and a
    variable is not masked, so asking for the account name would print the
    account name in the header of the job whose purpose is not to print it.
    """
    for name in ENDPOINT_ENV_NAMES:
        raw = values.get(name, "")
        if not raw or not raw.strip():
            continue
        try:
            endpoint = classify_endpoint(raw)
        except ValueError:
            # An endpoint we cannot parse is one we cannot mine for names. The
            # URL pattern still covers it, and a run configured with one will
            # not get far enough to produce a message about it.
            continue
        yield endpoint.account
        if endpoint.project:
            yield endpoint.project


def build_redactor(
    environ: Mapping[str, str] | None = None,
) -> Callable[[Any], str | None]:
    """Return a function that makes one runtime message safe to write down.

    Order matters: the names are blanked *after* URLs, because an account name
    is usually inside the URL and blanking it first would leave a URL that no
    longer matches the URL pattern.
    """
    values = os.environ if environ is None else environ
    named = [values.get(name, "") for name in IDENTITY_ENV_NAMES]
    named.extend(_names_in_endpoints(values))
    secrets = sorted(
        {value.strip() for value in named if value and value.strip()},
        key=len,
        reverse=True,
    )

    def redact(message: Any) -> str | None:
        if message is None:
            return None
        text = str(message)
        text = _JWT.sub("<token redacted>", text)
        text = _BEARER.sub("bearer <token redacted>", text)
        text = _URL.sub("<url redacted>", text)
        for secret in secrets:
            text = re.sub(re.escape(secret), "<name redacted>", text, flags=re.I)
        text = " ".join(text.split())
        if len(text) > MESSAGE_LIMIT:
            text = text[:MESSAGE_LIMIT] + "…"
        return text

    return redact


def host_fingerprint(url: str) -> str:
    """A stable, non-reversing name for the endpoint's host.

    Enough to tell two runs apart, or to tell that they used the same resource.
    Not enough to tell anybody which resource it was.
    """
    host = re.sub(r"\Ahttps?://", "", url).split("/", 1)[0].split(":", 1)[0]
    digest = hashlib.sha256(host.lower().encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


# ── The request, fixed before it is sent ────────────────────────────────────

#: The prompt. Short on purpose — the cheapest question that still needs the
#: whole model leg to answer it — and explicit that no tool is to be used, so a
#: green verdict cannot be mistaken for a tool-execution result.
PROMPT_ID = "connectivity/one-word/1"
PROMPT = (
    "Reply with exactly the single word CONNECTED and nothing else. "
    "Do not run any command, do not read any file, and do not write any file."
)
EXPECTED_REPLY = "CONNECTED"

#: One turn. Codex opens its own requests inside a turn and does not report how
#: many, which is the ``call_reachability_unknown`` the cost adapter records;
#: what is fixed here is the boundary this script controls. For the refusal
#: case the count is no longer unknown: a turn answered ``401`` makes exactly
#: two POSTs to ``/v1/responses`` and no request of any other verb, measured in
#: ``tests/test_what_one_codex_turn_actually_sends.py``. A turn that is *served*
#: is still unmeasured, so the unknown stands for the case that matters to cost.
TURNS_SENT = 1

#: How many tool definitions the runtime attaches to a turn regardless of the
#: prompt. Not a preference and not something this script sets -- a measured
#: property of the pinned binary, asserted against the wire in
#: ``tests/test_what_one_codex_turn_actually_sends.py`` so that this number and
#: the record cannot drift apart. If that test fails on a version bump, the
#: runtime changed and this constant is what to update.
TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS = 10

#: Wall clock for that turn. Long enough for a cold provider, short enough that
#: a hang is a finding rather than a bill.
DEFAULT_TIMEOUT_SECONDS = 120


def request_plan(description: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """What this run intends to send, read off the settings it will send with.

    ``retries_configured`` is taken from ``description`` -- the same mapping
    the fingerprint is computed over -- rather than written here as a literal.
    A plan that asserts its own zero proves nothing: the number that decides
    how many requests leave this machine is the one in the provider table, and
    if the two ever disagree the plan is the one that is wrong.

    ``None`` when there is no description, because a run whose settings could
    not be built did not configure zero retries; it configured nothing, and
    that is not the same record.
    """
    retries: dict[str, Any] | None = None
    if description is not None:
        configured = description.get("retries")
        if isinstance(configured, Mapping):
            retries = dict(configured)
    return {
        "prompt_id": PROMPT_ID,
        "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
        "prompt_characters": len(PROMPT),
        "expected_reply": EXPECTED_REPLY,
        "turns_sent": TURNS_SENT,
        "retries_configured": retries,
        # What pinning does not buy, stated next to what it does. Measured
        # against the pinned binary in tests/test_codex_retry_pins_are_enforced
        # .py: with both counters at 0, a 401 still costs two requests and two
        # auth-command runs, because Codex re-mints the token once and retries.
        # No supported key removes that, so a record that claimed one request
        # per turn would be claiming something the runtime does not do.
        "retries_not_removed_by_pinning": {
            "on_authentication_failure_requests": (
                AUTH_RETRY_REQUESTS_NOT_REMOVED_BY_PINNING
            ),
            "reason": (
                "the runtime re-runs the provider auth command once after an "
                "authentication failure and retries with the fresh token; "
                "neither retry counter binds it"
            ),
        },
        "tools_requested": False,
        "tool_definitions_sent": TOOL_DEFINITIONS_THE_RUNTIME_ALWAYS_SENDS,
        "tools_note": (
            "`tools_requested: false` is a property of this plan: the prompt "
            "asks for none and none ran, which `tool_execution_observed` "
            "records separately. It is not a property of the request. The "
            "runtime attaches its own tool definitions to every turn with "
            "`tool_choice: auto`, and no prompt wording or key in "
            "core/codex_runtime_config.py removes them, so the body is about "
            "45.9 KB rather than the 135 characters of the prompt. Measured "
            "offline against the pinned binary in "
            "tests/test_what_one_codex_turn_actually_sends.py"
        ),
    }


# ── The settings, described without naming the resource ─────────────────────


def describe_settings(settings: CodexProviderSettings) -> dict[str, Any]:
    """Everything that decides the answer, minus everything that identifies it.

    ``core.codex_runtime_config.describe_provider`` exists and is not used here
    because it prints ``base_url`` — correct for a local operator staring at a
    terminal, wrong for a file that gets committed.
    """
    classified = classify_endpoint(settings.endpoint)
    path = "/" + settings.endpoint.split("://", 1)[-1].split("/", 1)[-1]
    return {
        "endpoint_kind": classified.kind.value,
        "endpoint_host_fingerprint": host_fingerprint(settings.endpoint),
        "endpoint_path": path if path != "/" + settings.endpoint else "/",
        "deployment": settings.model,
        "provider_id": settings.provider_id,
        "wire_api": SUPPORTED_WIRE_API,
        "query_param_names": sorted(dict(settings.query_params)),
        "auth": {
            "mechanism": "auth_command",
            "module": settings.auth_module,
            "scope": settings.auth_scope,
            "refresh_interval_ms": settings.auth_refresh_interval_ms,
            "timeout_ms": settings.auth_timeout_ms,
        },
        # In the fingerprint on purpose. These two numbers decide how many
        # requests one turn sends -- up to thirty when they are left unset --
        # so a verdict measured with them pinned is not evidence for a run
        # without them, and the fingerprint has to be able to tell the two
        # apart.
        "retries": {
            "request_max_retries": settings.request_max_retries,
            "stream_max_retries": settings.stream_max_retries,
        },
        "sandbox": "workspace-write",
        "approval_mode": "deny-all",
        "pinned": {
            PINNED_CODEX_SDK_DISTRIBUTION: PINNED_CODEX_SDK_VERSION,
            PINNED_CODEX_CLI_DISTRIBUTION: PINNED_CODEX_CLI_VERSION,
        },
        "installed": {
            PINNED_CODEX_SDK_DISTRIBUTION: installed_sdk_version(),
            PINNED_CODEX_CLI_DISTRIBUTION: installed_cli_version(),
        },
    }


def settings_fingerprint(description: Mapping[str, Any]) -> str:
    """One hash over the description above.

    The point of a fingerprint is that a verdict is only about the settings it
    was measured under. Change the deployment, the route, the wire contract or
    the pinned version and this changes, so an old record cannot be read as
    evidence for a new configuration.
    """
    canonical = json.dumps(description, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def settings_from_environment(
    deployment: str, environ: Mapping[str, str] | None = None
) -> CodexProviderSettings:
    """Build the provider settings from the environment this job already has.

    No new variable and no new secret: the direct ``/openai/v1/`` endpoint is
    derived from the Foundry project endpoint by
    ``AzureAIRouteSettings.from_env`` exactly as every other Azure caller in
    this repository derives it, and the token comes from the same OIDC sign-in.

    Raises ``ValueError`` when the environment does not describe a deployment.
    It does not fall back to anything: a diagnostic that quietly measured a
    different resource than the one it was asked about would be worse than no
    diagnostic.
    """
    if not deployment or not deployment.strip():
        raise ValueError("a deployment name is required; there is no default")
    route = AzureAIRouteSettings.from_env(environ)
    if route.direct_v1 is None:
        raise ValueError(
            "the environment describes no direct /openai/v1/ endpoint, and the "
            "legacy dated route is a different contract rather than a fallback"
        )
    return CodexProviderSettings(
        endpoint=route.direct_v1.url, model=deployment.strip()
    )


# ── What a green verdict still does not buy ─────────────────────────────────

NOT_ESTABLISHED_BY_A_TEXT_TURN: tuple[str, ...] = (
    "the tool leg: this prompt forbids commands, so nothing here says the "
    "agent can execute one against this deployment; that is proven separately "
    "by tests/test_codex_runtime_end_to_end.py under CODEX_SANDBOX_MUST_RUN=1, "
    "and on one runner image only",
    "the deliverable leg: no file was asked for, so file creation, collection "
    "and retrieval are unobserved here",
    "the batch leg: one turn on one task says nothing about 5, 30 or 220, "
    "about concurrency, or about how the run place behaves for an hour",
    "the cost leg: this records the usage the runtime reported for one turn; "
    "the price of those tokens is not read here and an unpriced record is not "
    "a free one",
)


def _empty_observation() -> dict[str, Any]:
    return {
        "thread_started": False,
        "turn_sent": False,
        "turn_status": None,
        "runtime_model": None,
        "runtime_model_provider": None,
        "served_model": None,
        "served_model_note": (
            "the pinned SDK surfaces no field carrying the model the provider "
            "reported serving, so this is left unrecorded rather than filled "
            "in from what we asked for"
        ),
        "streaming": {
            "notifications": 0,
            "by_method": {},
            "usage_updates": 0,
            "item_types": [],
        },
        "usage": None,
        "final_response_present": False,
        "final_response_matched_instruction": False,
        "tool_execution_observed": False,
        "error": None,
    }


def _record(
    *,
    verdict: str,
    description: Mapping[str, Any] | None,
    observed: Mapping[str, Any],
    note: str | None = None,
) -> dict[str, Any]:
    if verdict not in VERDICTS:  # pragma: no cover - guarded by tests
        raise ValueError(f"{verdict!r} is not one of the fixed verdicts")
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "provider_answered": verdict in VERDICTS_THE_PROVIDER_ANSWERED,
        "note": note,
        "settings": dict(description) if description is not None else None,
        "settings_fingerprint": (
            settings_fingerprint(description) if description is not None else None
        ),
        "request": request_plan(description),
        "observed": dict(observed),
        "not_established": list(NOT_ESTABLISHED_BY_A_TEXT_TURN),
    }


# ── Driving the real runtime ────────────────────────────────────────────────


def observe_stream(
    events: Iterable[Any], *, turn_id: str
) -> tuple[dict[str, Any], Any, Any]:
    """Consume a turn's notifications, keeping what the SDK throws away.

    Returns the streaming summary, the completed ``Turn`` (or ``None``) and the
    ``ThreadTokenUsage`` (or ``None``). Nothing is raised on a failed turn:
    the failure *is* the result here.
    """
    from openai_codex.generated.v2_all import (
        ItemCompletedNotification,
        ThreadSettingsUpdatedNotification,
        ThreadTokenUsageUpdatedNotification,
        TurnCompletedNotification,
    )

    by_method: dict[str, int] = {}
    item_types: list[str] = []
    usage: Any = None
    usage_updates = 0
    turn: Any = None
    thread_settings: Any = None
    total = 0

    for event in events:
        total += 1
        method = getattr(event, "method", None) or "<unnamed>"
        by_method[method] = by_method.get(method, 0) + 1
        payload = getattr(event, "payload", None)

        if isinstance(payload, ItemCompletedNotification):
            if getattr(payload, "turn_id", None) == turn_id:
                item = getattr(payload, "item", None)
                inner = getattr(item, "root", item)
                item_types.append(type(inner).__name__)
            continue
        if isinstance(payload, ThreadTokenUsageUpdatedNotification):
            if getattr(payload, "turn_id", None) == turn_id:
                usage = getattr(payload, "token_usage", None)
                usage_updates += 1
            continue
        if isinstance(payload, ThreadSettingsUpdatedNotification):
            thread_settings = getattr(payload, "thread_settings", None)
            continue
        if isinstance(payload, TurnCompletedNotification):
            candidate = getattr(payload, "turn", None)
            if getattr(candidate, "id", None) == turn_id:
                turn = candidate
            continue

    summary = {
        "notifications": total,
        "by_method": dict(sorted(by_method.items())),
        "usage_updates": usage_updates,
        "item_types": item_types,
        "thread_settings_seen": thread_settings is not None,
    }
    return summary, turn, (usage, thread_settings)


def _usage_record(usage: Any) -> dict[str, Any] | None:
    """The two token numbers the SDK reports, with their meanings kept apart.

    ``total`` is the thread's running sum and ``last`` is the most recent
    request inside the turn. On a one-turn thread with more than one internal
    request they are different numbers and neither is the other's increment;
    subtracting them would invent a per-request figure the SDK does not expose.
    """
    if usage is None:
        return None

    def breakdown(value: Any) -> dict[str, Any] | None:
        if value is None:
            return None
        return {
            name: getattr(value, name, None)
            for name in (
                "input_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
            )
        }

    return {
        "thread_total": breakdown(getattr(usage, "total", None)),
        "most_recent_request": breakdown(getattr(usage, "last", None)),
        "model_context_window": getattr(usage, "model_context_window", None),
        "note": (
            "thread_total is cumulative over the thread; most_recent_request "
            "is the last request inside it. Codex does not report how many "
            "requests it opened, so the difference between them is not a "
            "per-request figure"
        ),
    }


def probe(
    settings: CodexProviderSettings,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    redact: Callable[[Any], str | None] | None = None,
) -> dict[str, Any]:
    """Send the one fixed turn and record what came back.

    Constructed through ``CodexAgentRunner`` rather than beside it, so that the
    isolated environment, the provider table, the sandbox preset and the
    approval mode are the production ones. The only thing done differently is
    consuming the stream, and that is to keep information the SDK discards.
    """
    from core.codex_runner import CodexAgentRunner, CodexWorkspace

    redact = redact or build_redactor()
    description = describe_settings(settings)
    observed = _empty_observation()

    try:
        runner = CodexAgentRunner(settings, timeout=timeout)
    except CodexRuntimeUnavailable as exc:
        observed["error"] = {"stage": "runtime", "message": redact(exc)}
        return _record(
            verdict=VERDICT_RUNTIME_UNAVAILABLE,
            description=description,
            observed=observed,
            note="nothing was sent, so nothing was billed",
        )

    workspace = CodexWorkspace.create(task_id="foundry-connection-probe")
    codex: Any = None
    try:
        try:
            codex = runner.open_runtime(workspace)
        except Exception as exc:  # noqa: BLE001
            observed["error"] = {"stage": "runtime", "message": redact(exc)}
            return _record(
                verdict=VERDICT_RUNTIME_UNAVAILABLE,
                description=description,
                observed=observed,
                note="the runtime never started, so no request was sent",
            )

        try:
            thread = runner.start_thread(codex, workspace)
        except Exception as exc:  # noqa: BLE001
            observed["error"] = {"stage": "session", "message": redact(exc)}
            return _record(
                verdict=VERDICT_SESSION_NOT_STARTED,
                description=description,
                observed=observed,
                note="the session never opened, so no request was sent",
            )

        observed["thread_started"] = True

        try:
            handle = thread.turn(PROMPT)
        except Exception as exc:  # noqa: BLE001
            observed["error"] = {"stage": "turn_start", "message": redact(exc)}
            return _record(
                verdict=VERDICT_SESSION_NOT_STARTED,
                description=description,
                observed=observed,
                note="the turn never started, so no request was sent",
            )

        observed["turn_sent"] = True
        stream: Iterator[Any] = handle.stream()
        try:
            summary, turn, extras = observe_stream(stream, turn_id=handle.id)
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                close()

        usage, thread_settings = extras
        observed["streaming"] = summary
        observed["usage"] = _usage_record(usage)
        if thread_settings is not None:
            observed["runtime_model"] = getattr(thread_settings, "model", None)
            observed["runtime_model_provider"] = getattr(
                thread_settings, "model_provider", None
            )
        observed["tool_execution_observed"] = any(
            "Command" in name or "Exec" in name or "Patch" in name
            for name in summary["item_types"]
        )

        if turn is None:
            observed["error"] = {
                "stage": "turn",
                "message": "the turn produced no completion event",
            }
            return _record(
                verdict=VERDICT_TURN_TIMED_OUT,
                description=description,
                observed=observed,
                note=(
                    "the turn was sent and never completed; a cost may exist "
                    "here that this run cannot measure"
                ),
            )

        status = getattr(getattr(turn, "status", None), "value", None)
        observed["turn_status"] = status
        error = getattr(turn, "error", None)

        if status == "completed" and error is None:
            text = _final_text(turn, summary)
            observed["final_response_present"] = bool(text)
            observed["final_response_matched_instruction"] = (
                text.strip().strip(".").upper() == EXPECTED_REPLY
                if text
                else False
            )
            return _record(
                verdict=VERDICT_CONNECTED,
                description=description,
                observed=observed,
                note=(
                    "the model leg answered under these settings; the tool "
                    "leg was not exercised"
                ),
            )

        verdict, name, http_status = classify_turn_error(error)
        observed["error"] = {
            "stage": "turn",
            "codex_error": name,
            "http_status_code": http_status,
            "message": redact(getattr(error, "message", None)),
            "additional_details": redact(
                getattr(error, "additional_details", None)
            ),
        }
        return _record(
            verdict=verdict,
            description=description,
            observed=observed,
            note="the turn was sent and failed; it may still have been billed",
        )
    finally:
        if codex is not None:
            try:
                codex.close()
            except Exception:  # noqa: BLE001 - closing must not mask a result
                pass
        workspace.cleanup()


def _final_text(turn: Any, summary: Mapping[str, Any]) -> str:
    """The turn's own final response, if the completion event carried one.

    Falls back to nothing rather than to the last item of any kind: an empty
    answer and a tool's output are different things and only one of them is an
    answer.
    """
    for attribute in ("final_response", "output_text"):
        value = getattr(turn, attribute, None)
        if isinstance(value, str) and value.strip():
            return value
    return ""


# ── The free half: does the token work on this host at all? ─────────────────

#: The read-only record's own format, kept apart from the connection record
#: because it answers a different question and a reader must not confuse a
#: model listing with a turn.
READ_ONLY_SCHEMA = "codex_foundry_readonly_probe/1"

#: Seconds for the token command and for the listing. Short: both are meant to
#: be quick, and a hang here would otherwise look like a network verdict.
READ_ONLY_TIMEOUT_SECONDS = 60


def mint_token_the_way_codex_does(
    settings: CodexProviderSettings, *, timeout: int = READ_ONLY_TIMEOUT_SECONDS
) -> str:
    """Run the provider's ``auth.command`` and return what it printed.

    This is the point of the whole read-only probe. The Python paths that grade
    and infer mint their token *in process*, through
    ``get_bearer_token_provider``. Codex does not: it runs the argv in
    ``auth.command`` as a child process and reads stdout. Those two can resolve
    to different credentials in the same job — a chain that finds an
    environment credential in one and falls through to the CLI session in the
    other — and nothing in this repository had ever compared them.

    The token is returned and never logged. The exception raised on failure
    carries the command's *stderr* only; stdout is where the token would be, so
    stdout is not quoted even when the command fails.
    """
    import subprocess

    # `auth_command` is a method on the settings object, not a field. Reading it
    # without calling it yields a bound method, which `subprocess.run` accepts
    # and then fails on inside the standard library with "'method' object is not
    # iterable" -- a message naming neither this file nor the attribute. Run
    # 34340775246 spent a real OIDC login to produce exactly that, and reported
    # it as a `token.error` where a reader could mistake it for the host having
    # refused. Resolve the argv here and check its shape, so a wrong one is
    # named before any child process starts.
    argv = settings.auth_command()
    if not isinstance(argv, (list, tuple)) or not all(
        isinstance(item, str) for item in argv
    ):
        raise RuntimeError(
            "the provider's auth command did not resolve to a list of strings; "
            f"got {type(argv).__name__}. This is a defect in this probe or in "
            "the settings object, not an answer from the host."
        )

    completed = subprocess.run(  # noqa: S603 - argv built by the settings object
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"the auth command exited {completed.returncode}: "
            f"{(completed.stderr or '').strip()[:MESSAGE_LIMIT]}"
        )
    token = (completed.stdout or "").strip()
    if not token:
        raise RuntimeError("the auth command succeeded but printed no token")
    return token


def list_models_read_only(
    settings: CodexProviderSettings,
    token: str,
    *,
    timeout: int = READ_ONLY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """``GET {base_url}/models`` with the token Codex would have sent.

    A listing, not a turn: no prompt, no completion, nothing to generate. It is
    the same host, the same ``/openai/v1/`` contract and the same
    ``Authorization: Bearer`` header the turn uses, which is exactly what makes
    it able to separate two things a 401 on the turn cannot:

    * ``200`` — the token is accepted by this resource. Whatever refused the
      turn refused something narrower than "this identity".
    * ``401`` — the refusal reproduces without spending anything, and the
      question moves to the token itself.

    Model names are counted, never recorded. The count and one boolean are
    enough to answer the question, and a deployment list is the sort of thing
    that names a resource.
    """
    import urllib.error
    import urllib.request

    url = f"{settings.base_url}/models"
    request = urllib.request.Request(  # noqa: S310 - scheme fixed by classify_endpoint
        url,
        method="GET",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    outcome: dict[str, Any] = {
        "requested": "GET /models",
        "status": None,
        "models_listed": None,
        "deployment_listed": None,
        "error": None,
    }
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            outcome["status"] = int(response.status)
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        outcome["status"] = int(exc.code)
        outcome["error"] = (exc.reason or "").strip()[:MESSAGE_LIMIT] or None
        return outcome
    except Exception as exc:  # noqa: BLE001 - a transport failure is a finding
        outcome["error"] = f"{type(exc).__name__}: {exc}"[:MESSAGE_LIMIT]
        return outcome

    try:
        payload = json.loads(body)
    except ValueError:
        outcome["error"] = "the listing was not JSON"
        return outcome
    entries = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(entries, list):
        outcome["error"] = "the listing carried no data array"
        return outcome
    identifiers = {
        entry.get("id") for entry in entries if isinstance(entry, Mapping)
    }
    outcome["models_listed"] = len(entries)
    outcome["deployment_listed"] = settings.model in identifiers
    return outcome


#: What a 200 here still does not buy. Written out because "the token works"
#: is the exact claim a reader would over-read this record into.
NOT_ESTABLISHED_BY_A_LISTING: tuple[str, ...] = (
    "the turn leg: a listing is not a completion. A resource can list its "
    "models to an identity and still refuse that identity's inference",
    "the deployment leg: `deployment_listed` says the name appears in the "
    "listing, not that this identity may call it",
    "the cost leg: no inference was requested, so no tokens were generated. "
    "This record does not price the call and an unpriced call is not a proven "
    "free one",
)


def read_only_probe(
    settings: CodexProviderSettings,
    *,
    timeout: int = READ_ONLY_TIMEOUT_SECONDS,
    redact: Callable[[Any], str | None],
) -> dict[str, Any]:
    """Mint the token the way Codex does, then ask the host to list models."""
    description = describe_settings(settings)
    record: dict[str, Any] = {
        "schema": READ_ONLY_SCHEMA,
        "inference_requested": False,
        "settings": description,
        "settings_fingerprint": settings_fingerprint(description),
        "endpoint_host_fingerprint": host_fingerprint(settings.base_url),
        "token": {
            "minted": False,
            "mechanism": "auth_command",
            "how": (
                "the provider's auth.command was run as a child process, which "
                "is how the Codex runtime obtains it -- not the in-process "
                "provider the grading and inference paths use"
            ),
            "error": None,
        },
        "listing": None,
        "not_established": list(NOT_ESTABLISHED_BY_A_LISTING),
    }
    try:
        token = mint_token_the_way_codex_does(settings, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - a mint failure is the finding
        record["token"]["error"] = redact(exc)
        return record
    record["token"]["minted"] = True
    record["listing"] = list_models_read_only(settings, token, timeout=timeout)
    if record["listing"].get("error"):
        record["listing"]["error"] = redact(record["listing"]["error"])
    return record


# ── Does the bearer get past the gate, or not? ──────────────────────────────
#
# What is left after the read-only probe. Run 34346945494 minted a token the
# Codex way and got 200 from `GET /models` on the same host, with the same
# bearer, minutes before run 34347516170 sent one turn to the same host and got
# 401. So the identity is admitted by the resource for one operation and
# refused for another, and the refusal message ("invalid subscription key or
# wrong API endpoint") is an Azure gateway string that several different
# refusals share. Nothing measured so far says whether the turn died at
# authorization or somewhere past it.
#
# This separates those two for nothing, by asking the *turn route* a question
# it cannot answer with a completion: `POST {base_url}/responses` carrying a
# body the route cannot serve under any credential.
#
# One arm would not be enough, and that is the whole design here. A 400 from
# the minted bearer only means "the token got past authorization" if this host
# checks authorization *before* it validates the body — and no measurement in
# this repository establishes that ordering. So there are two arms: the same
# malformed body sent once with the minted bearer and once with a string that
# is obviously not a token. The control arm is not credential guessing and
# cannot become it: the string is a fixed sentence, it is never varied, and its
# only job is to make the host demonstrate which check it runs first.
#
#   control 401/403, minted 400/422  -> authorization runs first and the minted
#                                       bearer cleared it. The turn's 401 is
#                                       about something past the gate.
#   control 401/403, minted 401/403  -> the minted bearer is refused where a
#                                       plainly invalid one is. The question
#                                       stays on the token.
#   control NOT 401/403              -> this host looks at the body first, so
#                                       the minted arm's status says nothing
#                                       about authorization. The instrument
#                                       cannot answer, and says so.
#
# The third outcome is why this is written as three verdicts and not two. An
# instrument that can only return the answer it was built to find is not an
# instrument.

#: Its own schema. A reader must not be able to confuse this with a turn or
#: with a listing: it is neither, and it grades neither.
AUTH_DISCRIMINATOR_SCHEMA = "codex_foundry_auth_discriminator/1"

#: The body. Deliberately not a Responses request: no `model`, no `input`, no
#: field this API knows. Two independent reasons it cannot produce output --
#: the route has nothing to validate into a request, and with no model named
#: there is no deployment for a token to be generated by.
MALFORMED_TURN_BODY: dict[str, Any] = {
    "this_is_not_a_responses_request": (
        "sent by diagnose_codex_foundry_connection.py to learn which check "
        "this host runs first. It names no model and asks for no completion."
    )
}

#: The control arm's credential. Not a credential: a sentence. Fixed, never
#: varied, never derived from anything real, and chosen to be unmistakable in a
#: log. If a host ever accepted this, that would be the finding of the year and
#: the verdict below would still not call it a pass.
OBVIOUSLY_INVALID_BEARER = "this-string-is-not-a-token-and-never-was"

#: Statuses that mean the request was stopped at authorization.
AUTH_GATE_STATUSES = frozenset({401, 403})

#: Statuses that mean the request reached the part that reads the body. Getting
#: one of these is only informative alongside the control arm; see above.
REQUEST_VALIDATION_STATUSES = frozenset({400, 422})

VERDICT_BEARER_CLEARS_THE_AUTH_GATE = "bearer_clears_the_auth_gate"
VERDICT_BEARER_REFUSED_AT_THE_AUTH_GATE = "bearer_refused_at_the_auth_gate"
#: The honest no-answer. The host did not refuse a plainly invalid bearer at
#: the gate, so nothing the minted bearer got back can be read as a statement
#: about authorization.
VERDICT_CHECK_ORDER_NOT_ESTABLISHED = "check_order_not_established"
#: Everything else: a transport failure, a 5xx, a 404, a contradictory pair, or
#: a 200 that should never have happened.
VERDICT_DISCRIMINATOR_INCONCLUSIVE = "discriminator_inconclusive"


def post_malformed_turn(
    settings: CodexProviderSettings,
    token: str,
    *,
    timeout: int = READ_ONLY_TIMEOUT_SECONDS,
    extra_headers: Mapping[str, str] | None = None,
    body: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """``POST {base_url}/responses`` with a body the route cannot serve.

    The refusal *text* is kept, redacted, because two arms returning the same
    sentence is itself evidence: a host that answers a minted bearer exactly
    what it answers a fixed non-token is not distinguishing between them.

    ``extra_headers`` and ``body`` default to nothing and to
    ``MALFORMED_TURN_BODY``, so the discriminator's two arms are unchanged by
    their existence. They are here for the sweep below, which varies one
    request property at a time; a body passed in must still name no model, and
    the sweep is where that is enforced rather than here.
    """
    import urllib.error
    import urllib.request

    payload = json.dumps(MALFORMED_TURN_BODY if body is None else dict(body)).encode(
        "utf-8"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    headers.update(dict(extra_headers or {}))
    request = urllib.request.Request(  # noqa: S310 - scheme fixed by classify_endpoint
        f"{settings.base_url}/responses",
        method="POST",
        data=payload,
        headers=headers,
    )
    outcome: dict[str, Any] = {
        "requested": "POST /responses",
        "status": None,
        "message": None,
        "error": None,
    }
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            outcome["status"] = int(response.status)
            answer = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        outcome["status"] = int(exc.code)
        try:
            answer = exc.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - a body we cannot read is not a crash
            answer = ""
    except Exception as exc:  # noqa: BLE001 - a transport failure is a finding
        outcome["error"] = f"{type(exc).__name__}: {exc}"
        return outcome

    outcome["message"] = _message_in(answer)
    return outcome


def _message_in(body: str) -> str | None:
    """Pull the human-readable sentence out of an error body, if there is one.

    Returned raw; every caller passes it through the redactor before it reaches
    a record. Kept separate so that a body which is not the shape we expect
    degrades to the first stretch of text rather than to nothing -- a refusal
    nobody can read is barely better than a refusal nobody recorded.
    """
    try:
        parsed = json.loads(body)
    except ValueError:
        return " ".join(body.split())[:MESSAGE_LIMIT] or None
    if isinstance(parsed, Mapping):
        error = parsed.get("error")
        if isinstance(error, Mapping):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:MESSAGE_LIMIT]
        message = parsed.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:MESSAGE_LIMIT]
    return " ".join(body.split())[:MESSAGE_LIMIT] or None


def classify_discriminator(
    minted: Mapping[str, Any], control: Mapping[str, Any]
) -> tuple[str, str]:
    """Read the two arms and name what they do — and do not — establish.

    Returns the verdict and the sentence that goes with it. The order of the
    tests matters and is not the order a reader expects: the control arm is
    examined *first*, because a minted-arm status cannot be interpreted at all
    until the host has shown that it refuses a non-token at the gate.
    """
    minted_status = minted.get("status")
    control_status = control.get("status")

    if minted.get("error") or control.get("error"):
        return (
            VERDICT_DISCRIMINATOR_INCONCLUSIVE,
            "one of the two arms never reached the host, so there is no pair "
            "to compare. This says nothing about the resource",
        )
    if minted_status is None or control_status is None:
        return (
            VERDICT_DISCRIMINATOR_INCONCLUSIVE,
            "one of the two arms recorded no status, which is a defect in this "
            "probe rather than an answer from the host",
        )
    if minted_status == 200:
        return (
            VERDICT_DISCRIMINATOR_INCONCLUSIVE,
            "the host accepted a body that names no model and asks for no "
            "completion. That is not a result this probe can interpret, and "
            "the assumption that nothing could be generated no longer holds: "
            "treat this run as one whose cost is unknown",
        )
    if control_status not in AUTH_GATE_STATUSES:
        return (
            VERDICT_CHECK_ORDER_NOT_ESTABLISHED,
            f"a bearer that is plainly not a token got {control_status}, not "
            "401 or 403. This host therefore does not stop an unauthenticated "
            f"request at the gate, so the minted bearer's {minted_status} is "
            "not evidence about authorization either way. The question this "
            "probe was built to answer is still open",
        )
    if minted_status in AUTH_GATE_STATUSES:
        return (
            VERDICT_BEARER_REFUSED_AT_THE_AUTH_GATE,
            "the minted bearer was refused where a plainly invalid one is "
            "refused, on a request that could not have been served anyway. "
            "The turn's refusal is at authorization, and the question is the "
            "token or this identity's rights on this operation -- not the "
            "payload, the deployment name or the route",
        )
    if minted_status in REQUEST_VALIDATION_STATUSES:
        return (
            VERDICT_BEARER_CLEARS_THE_AUTH_GATE,
            "this host stops an invalid bearer at the gate, and the minted "
            "bearer got past it to the part that reads the body. Whatever "
            "refused the real turn is past authorization, so a role grant is "
            "not obviously the fix and should not be requested on this "
            "evidence alone",
        )
    return (
        VERDICT_DISCRIMINATOR_INCONCLUSIVE,
        f"the host stops an invalid bearer at the gate but answered the minted "
        f"bearer {minted_status}, which is neither an authorization refusal nor "
        "a complaint about the body. This pair does not fit the question",
    )


#: What this cannot settle no matter which way it comes out.
NOT_ESTABLISHED_BY_THE_DISCRIMINATOR: tuple[str, ...] = (
    "the turn leg: this is urllib on the same route, not the Codex runtime. "
    "The header name and format are the ones the pinned binary was measured "
    "sending (tests/test_codex_retry_pins_are_enforced.py), but the rest of "
    "the runtime's request is not reproduced here and is not being tested",
    "the fix: `bearer_clears_the_auth_gate` narrows where to look. It does not "
    "name what to change, and it is not a reason to grant a role",
    "the cost leg: a body naming no model cannot select a deployment, so "
    "nothing should be generated -- but no usage record is returned by a "
    "refusal, so this is an argument and not a measurement. An unpriced call "
    "is not a proven free one",
    "the message leg: `same_message_as_control` compares two refusals from "
    "this probe. Neither is compared against the turn's refusal, which was "
    "produced by a different client on a different day",
)


def auth_discriminator_probe(
    settings: CodexProviderSettings,
    *,
    timeout: int = READ_ONLY_TIMEOUT_SECONDS,
    redact: Callable[[Any], str | None],
) -> dict[str, Any]:
    """Send the same unservable body twice — minted bearer, then a non-token."""
    description = describe_settings(settings)
    record: dict[str, Any] = {
        "schema": AUTH_DISCRIMINATOR_SCHEMA,
        "inference_requested": False,
        "settings": description,
        "settings_fingerprint": settings_fingerprint(description),
        "endpoint_host_fingerprint": host_fingerprint(settings.base_url),
        "body_sha256": hashlib.sha256(
            json.dumps(MALFORMED_TURN_BODY, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "token": {
            "minted": False,
            "mechanism": "auth_command",
            "error": None,
        },
        "arms": {"minted_bearer": None, "invalid_bearer_control": None},
        "same_message_as_control": None,
        "verdict": VERDICT_DISCRIMINATOR_INCONCLUSIVE,
        "verdict_note": "the probe did not run",
        "not_established": list(NOT_ESTABLISHED_BY_THE_DISCRIMINATOR),
    }
    try:
        token = mint_token_the_way_codex_does(settings, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - a mint failure is the finding
        record["token"]["error"] = redact(exc)
        record["verdict_note"] = (
            "no token could be minted, so neither arm was sent. This measures "
            "nothing about the resource"
        )
        return record
    record["token"]["minted"] = True

    minted = post_malformed_turn(settings, token, timeout=timeout)
    control = post_malformed_turn(
        settings, OBVIOUSLY_INVALID_BEARER, timeout=timeout
    )

    # Compare before redacting. Redaction collapses distinct strings onto the
    # same placeholder, so two different refusals can come out identical on the
    # far side of it and this flag would then be measuring the redactor.
    if minted.get("message") and control.get("message"):
        record["same_message_as_control"] = minted["message"] == control["message"]

    verdict, note = classify_discriminator(minted, control)
    record["verdict"] = verdict
    record["verdict_note"] = note

    for key, arm in (("minted_bearer", minted), ("invalid_bearer_control", control)):
        arm = dict(arm)
        arm["message"] = redact(arm.get("message"))
        arm["error"] = redact(arm.get("error"))
        record["arms"][key] = arm
    return record


# ── Which request property closes the gate ──────────────────────────────────
#
# Run 34361684546 established the check order on this host: a plainly invalid
# bearer is stopped at the gate (401), and the minted bearer gets past it to
# the part that reads the body (400). The Codex runtime, sending *the same
# minted token to the same URL*, is answered 401 with the control arm's
# sentence word for word.
#
# Four transmission explanations were measured offline against the pinned
# binary and all four are false: the `authorization` header is present, it
# carries the `Bearer ` scheme, its value is exactly what the auth command
# printed, and no second credential header rides alongside. So what is left is
# everything else the runtime puts on the wire that `urllib` does not.
#
# This sweep adds those, one property at a time, to a request already known to
# clear the gate — and whose body still names no model, so no arm can select a
# deployment or generate anything. A 400 that turns into a 401 names a property
# that changes how this host authorizes. Nothing turning names the body, and
# that is a result too.
#
# What a flip does *not* establish is spelled out in the record: this is still
# urllib, not the runtime, and a property that closes the gate here is a
# candidate for the turn's refusal, not a demonstrated cause of it.

SWEEP_SCHEMA = "codex_foundry_transmission_sweep/1"

#: Stands in for every identifier the runtime generates per session. The real
#: ones name this machine's installation; the question is whether the *header*
#: changes the answer, and a synthetic value of the same shape asks that
#: without putting an installation identifier on someone else's host.
SYNTHETIC_ID = "00000000-0000-7000-8000-000000000000"

#: Measured off the wire, not guessed — the guess would have been wrong twice.
#: The originator is `codex_python_sdk`, not the `codex_cli_rs` the CLI sends,
#: and the runtime asks for `text/event-stream`, not JSON.
CODEX_ACCEPT = "text/event-stream"
CODEX_ORIGINATOR = "codex_python_sdk"
CODEX_USER_AGENT = "codex_python_sdk/0.147.0 (unknown; x86_64) unknown"

#: The six remaining headers the working `openai.OpenAI` client never sends.
#: Values are shape-preserving stand-ins; `x-codex-turn-metadata` is real JSON
#: with real keys because a gateway that parses it would reject a placeholder
#: for the wrong reason, and none of its values identify anything.
CODEX_RUNTIME_HEADERS: dict[str, str] = {
    "session-id": SYNTHETIC_ID,
    "thread-id": SYNTHETIC_ID,
    "x-client-request-id": SYNTHETIC_ID,
    "x-codex-window-id": f"{SYNTHETIC_ID}:0",
    "x-codex-beta-features": "remote_compaction_v2",
    "x-codex-turn-metadata": json.dumps(
        {
            "installation_id": SYNTHETIC_ID,
            "session_id": SYNTHETIC_ID,
            "thread_id": SYNTHETIC_ID,
            "turn_id": SYNTHETIC_ID,
            "window_id": f"{SYNTHETIC_ID}:0",
            "request_kind": "turn",
            "sandbox": "seccomp",
            "turn_started_at_unix_ms": 0,
        },
        separators=(",", ":"),
    ),
}

#: One arm per property, plus a combination. Isolated rather than cumulative:
#: cumulative arms make the first flip un-attributable to anything narrower
#: than "this group or an earlier one", and the extra request buys the
#: difference between "this property is sufficient" and "something before it
#: was". The combination arm is what catches a property that only closes the
#: gate in company.
SWEEP_ARMS: tuple[tuple[str, dict[str, str], dict[str, Any] | None, str], ...] = (
    (
        "baseline",
        {},
        None,
        "the discriminator's minted arm, re-sent in this run so the comparison "
        "is against today's host and not against a result from another day",
    ),
    (
        "accept_event_stream",
        {"Accept": CODEX_ACCEPT},
        None,
        "the runtime asks for a stream; content negotiation can route a "
        "request to a different backend before anything reads the body",
    ),
    (
        "originator_and_user_agent",
        {"originator": CODEX_ORIGINATOR, "User-Agent": CODEX_USER_AGENT},
        None,
        "the two headers that name the client. A gateway policy keyed on "
        "either would refuse before it looked at the bearer",
    ),
    (
        "codex_runtime_headers",
        dict(CODEX_RUNTIME_HEADERS),
        None,
        "the six session and turn headers the working client never sends",
    ),
    (
        "stream_true",
        {},
        {**MALFORMED_TURN_BODY, "stream": True},
        "the one body field that can be varied without naming a model. Sent "
        "with the plain Accept on purpose: the point is to separate the body "
        "field from the header that usually accompanies it",
    ),
    (
        "everything",
        {
            "Accept": CODEX_ACCEPT,
            "originator": CODEX_ORIGINATOR,
            "User-Agent": CODEX_USER_AGENT,
            **CODEX_RUNTIME_HEADERS,
        },
        {**MALFORMED_TURN_BODY, "stream": True},
        "as close to a Codex request as a request that names no model can be",
    ),
)

VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE = "a_request_property_closes_the_auth_gate"
VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE = "no_request_property_closes_the_auth_gate"
#: The honest no-answer, and the one this sweep is most likely to need: it is
#: built on a premise -- that the plain request still clears the gate today --
#: which it re-tests every run rather than assuming.
VERDICT_SWEEP_INCONCLUSIVE = "sweep_inconclusive"

#: What the sweep cannot settle whichever way it comes out.
NOT_ESTABLISHED_BY_THE_SWEEP: tuple[str, ...] = (
    "the cause: every arm here is urllib. A property that closes the gate for "
    "urllib is a candidate for what refuses the runtime, not a demonstration "
    "that it is what refuses the runtime",
    "the body: no arm names a model, carries instructions, or sends the ten "
    "tool definitions. The runtime's request is ~45 KB and these are a few "
    "hundred bytes, so a null result here points at the body and does not "
    "test it",
    "the transport: TLS negotiation, HTTP version and connection reuse differ "
    "between urllib and the runtime's client and are not varied here",
    "the fix: a named property is somewhere to look next. It is not a change "
    "to make, and it is not a reason to request a role",
    "the permission: this reads the order the host checks a request in, not "
    "what the identity may do. Clearing the gate with an unservable body "
    "shows authorization is checked before the body is read; it does not "
    "show that a servable body would be served, because no arm here is one",
    "the cost: a refusal returns no usage record, so these calls are unpriced "
    "rather than proven free",
)


def classify_sweep(
    arms: Mapping[str, Mapping[str, Any]], control: Mapping[str, Any]
) -> tuple[str, str, list[str]]:
    """Read the arms, and say what they establish and what they do not.

    The premise is checked before the result, in two steps, because a sweep
    whose baseline no longer clears the gate is measuring a different host than
    the one the question is about -- and would otherwise report every arm as a
    flip.
    """
    if control.get("error") or control.get("status") not in AUTH_GATE_STATUSES:
        return (
            VERDICT_SWEEP_INCONCLUSIVE,
            "the control arm did not get stopped at the gate, so this host is "
            f"not showing the check order the sweep reads against (control: "
            f"{control.get('status')}). No arm's status can be interpreted",
            [],
        )
    baseline = arms.get("baseline") or {}
    if baseline.get("status") not in REQUEST_VALIDATION_STATUSES:
        return (
            VERDICT_SWEEP_INCONCLUSIVE,
            f"the plain request got {baseline.get('status')}, not the 400 that "
            "made this question worth asking. Whatever changed, it is not one "
            "of the properties this sweep varies",
            [],
        )

    closed = [
        name
        for name, arm in arms.items()
        if name != "baseline" and arm.get("status") in AUTH_GATE_STATUSES
    ]
    if not closed:
        return (
            VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE,
            "every property the runtime adds to its headers, and the one body "
            "field that can be varied without naming a model, left the request "
            "clearing the gate. What refuses the runtime is therefore in the "
            "part of the body this sweep cannot send -- the model, the "
            "instructions, the ten tool definitions -- or in the transport",
            [],
        )
    if closed == ["everything"]:
        return (
            VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE,
            "no single property closed the gate and the combination did, so "
            "what refuses the request needs more than one of them present. The "
            "isolated arms name which to combine next",
            closed,
        )
    return (
        VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE,
        f"adding {', '.join(sorted(n for n in closed if n != 'everything'))} to "
        "a request that otherwise clears the gate makes this host refuse it at "
        "the gate, with the same body. That is where to look, and it is not a "
        "reason to request a role",
        closed,
    )


def transmission_sweep(
    settings: CodexProviderSettings,
    *,
    timeout: int = READ_ONLY_TIMEOUT_SECONDS,
    redact: Callable[[Any], str | None],
) -> dict[str, Any]:
    """Vary one request property at a time and see which one closes the gate."""
    description = describe_settings(settings)
    record: dict[str, Any] = {
        "schema": SWEEP_SCHEMA,
        "inference_requested": False,
        "settings": description,
        "settings_fingerprint": settings_fingerprint(description),
        "endpoint_host_fingerprint": host_fingerprint(settings.base_url),
        "requests_planned": len(SWEEP_ARMS) + 1,
        "requests_sent": 0,
        "arms_described": {name: why for name, _h, _b, why in SWEEP_ARMS},
        "token": {"minted": False, "mechanism": "auth_command", "error": None},
        "arms": {},
        "control": None,
        "properties_that_closed_the_gate": [],
        "verdict": VERDICT_SWEEP_INCONCLUSIVE,
        "verdict_note": "the sweep did not run",
        "not_established": list(NOT_ESTABLISHED_BY_THE_SWEEP),
    }

    # Enforced here rather than trusted: an arm that named a model could select
    # a deployment, and the argument that nothing can be generated would stop
    # holding for the whole run.
    for name, _headers, body, _why in SWEEP_ARMS:
        if body is not None and "model" in body:
            raise ValueError(
                f"arm {name!r} names a model, which this sweep must never do"
            )

    try:
        token = mint_token_the_way_codex_does(settings, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - a mint failure is the finding
        record["token"]["error"] = redact(exc)
        record["verdict_note"] = (
            "no token could be minted, so no arm was sent. This measures "
            "nothing about the resource"
        )
        return record
    record["token"]["minted"] = True

    raw_arms: dict[str, dict[str, Any]] = {}
    for name, headers, body, _why in SWEEP_ARMS:
        outcome = post_malformed_turn(
            settings, token, timeout=timeout, extra_headers=headers, body=body
        )
        outcome["body_sha256"] = hashlib.sha256(
            json.dumps(
                MALFORMED_TURN_BODY if body is None else dict(body), sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        outcome["headers_added"] = sorted(headers)
        raw_arms[name] = outcome
        record["requests_sent"] += 1

    control = post_malformed_turn(
        settings, OBVIOUSLY_INVALID_BEARER, timeout=timeout
    )
    record["requests_sent"] += 1

    verdict, note, closed = classify_sweep(raw_arms, control)
    record["verdict"] = verdict
    record["verdict_note"] = note
    record["properties_that_closed_the_gate"] = closed

    # Compared before redaction, for the reason the discriminator gives: the
    # redactor collapses distinct strings onto one placeholder, so two
    # different refusals can come out identical on the far side of it.
    baseline_message = (raw_arms.get("baseline") or {}).get("message")
    for name, arm in raw_arms.items():
        arm = dict(arm)
        arm["same_message_as_baseline"] = (
            (arm.get("message") == baseline_message)
            if arm.get("message") and baseline_message
            else None
        )
        arm["same_message_as_control"] = (
            (arm.get("message") == control.get("message"))
            if arm.get("message") and control.get("message")
            else None
        )
        arm["message"] = redact(arm.get("message"))
        arm["error"] = redact(arm.get("error"))
        record["arms"][name] = arm

    control = dict(control)
    control["message"] = redact(control.get("message"))
    control["error"] = redact(control.get("error"))
    record["control"] = control
    return record


# ── Command line ────────────────────────────────────────────────────────────


def _plan(description: Mapping[str, Any]) -> dict[str, Any]:
    return _record(
        verdict=VERDICT_NOT_SENT,
        description=description,
        observed=_empty_observation(),
        note=(
            "--send-request was not passed. This is the plan, fixed and "
            "fingerprinted; no request exists and no cost was incurred"
        ),
    )


def _emit(record: Mapping[str, Any], out: str | None) -> None:
    """Print the record, and write it to ``--out`` if one was named.

    Every exit goes through here, including the one where nothing could be
    configured. A run that dies at its configuration and leaves no file behind
    is indistinguishable, from the artifact alone, from a run that never
    happened -- and the difference between those two is the whole subject of
    this diagnostic.
    """
    text = json.dumps(record, indent=2, sort_keys=False)
    sys.stdout.write(text + "\n")
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Send one fixed turn to a Foundry deployment through the real "
            "Codex runtime and record what came back."
        )
    )
    parser.add_argument(
        "--deployment",
        required=True,
        help="the deployment to call. Required, with no default: this probe "
        "reports on the deployment it was asked about or on none at all.",
    )
    parser.add_argument(
        "--send-request",
        action="store_true",
        help="actually send the turn. Without it the plan is printed and "
        "nothing is sent, so the request can be fixed before it is paid for.",
    )
    parser.add_argument(
        "--read-only-probe",
        action="store_true",
        help="mint the token the way the Codex runtime does and ask the host "
        "to list its models. No prompt, no completion, no turn. Answers "
        "whether a refusal is about this identity or about something "
        "narrower, without sending anything that could generate a token.",
    )
    parser.add_argument(
        "--auth-discriminator",
        action="store_true",
        help="ask the turn route a question it cannot answer with a "
        "completion, twice: once with the token the Codex runtime would mint "
        "and once with a string that is plainly not a token. Separates 'the "
        "bearer was refused' from 'the bearer got past and something later "
        "refused', and reports that it cannot tell when this host validates "
        "the body before it checks authorization. Exits 0 only when it "
        "established one of those, not when it merely ran.",
    )
    parser.add_argument(
        "--transmission-sweep",
        action="store_true",
        help="send the same unservable body once per request property the "
        "Codex runtime adds and the working client does not, plus a "
        "combination and an invalid-bearer control. Names which property, if "
        "any, makes this host refuse at the gate a request it otherwise lets "
        "through. No arm names a model, so no arm can generate anything. "
        "Exits 0 only when it establishes an answer, not when it merely ran.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="wall-clock seconds for the turn.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="write the record here as well as to standard output.",
    )
    args = parser.parse_args(argv)

    chosen = [
        name
        for name, on in (
            ("--read-only-probe", args.read_only_probe),
            ("--auth-discriminator", args.auth_discriminator),
            ("--transmission-sweep", args.transmission_sweep),
            ("--send-request", args.send_request),
        )
        if on
    ]
    if len(chosen) > 1:
        parser.error(
            f"{', '.join(chosen)} ask different questions and write different "
            "records; run them separately"
        )

    redact = build_redactor()

    try:
        settings = settings_from_environment(args.deployment)
    except (ValueError, CodexProviderConfigurationError) as exc:
        _emit(
            _record(
                verdict=VERDICT_SETTINGS_INCOMPLETE,
                description=None,
                observed=_empty_observation(),
                note=redact(exc),
            ),
            args.out,
        )
        return 2

    description = describe_settings(settings)

    if args.read_only_probe:
        record = read_only_probe(settings, redact=redact)
        _emit(record, args.out)
        # Non-zero unless the host both minted a token and answered 200: this
        # is a diagnostic, and "the probe ran" is not the result.
        listing = record.get("listing") or {}
        return 0 if listing.get("status") == 200 else 1

    if args.auth_discriminator:
        record = auth_discriminator_probe(settings, redact=redact)
        _emit(record, args.out)
        # 0 for either conclusive verdict, including the unwelcome one: this
        # exit code answers "did the instrument discriminate", not "was the
        # news good". A run that could not tell must not look like a pass.
        return (
            0
            if record["verdict"]
            in (
                VERDICT_BEARER_CLEARS_THE_AUTH_GATE,
                VERDICT_BEARER_REFUSED_AT_THE_AUTH_GATE,
            )
            else 1
        )

    if args.transmission_sweep:
        record = transmission_sweep(settings, redact=redact)
        _emit(record, args.out)
        # As above: 0 for either conclusive verdict. "No property closed the
        # gate" is an answer -- it moves the question to the body -- and a run
        # that could not tell must not look like one.
        return (
            0
            if record["verdict"]
            in (
                VERDICT_A_REQUEST_PROPERTY_CLOSES_THE_GATE,
                VERDICT_NO_REQUEST_PROPERTY_CLOSES_THE_GATE,
            )
            else 1
        )

    if not args.send_request:
        _emit(_plan(description), args.out)
        return 0

    record = probe(settings, timeout=args.timeout, redact=redact)
    _emit(record, args.out)
    return 0 if record["verdict"] == VERDICT_CONNECTED else 1


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
