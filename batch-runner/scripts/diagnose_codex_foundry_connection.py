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
SCHEMA = "codex_foundry_connection/1"

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
#: what is fixed here is the boundary this script controls.
TURNS_SENT = 1

#: Wall clock for that turn. Long enough for a cold provider, short enough that
#: a hang is a finding rather than a bill.
DEFAULT_TIMEOUT_SECONDS = 120


def request_plan() -> dict[str, Any]:
    return {
        "prompt_id": PROMPT_ID,
        "prompt_sha256": hashlib.sha256(PROMPT.encode("utf-8")).hexdigest(),
        "prompt_characters": len(PROMPT),
        "expected_reply": EXPECTED_REPLY,
        "turns_sent": TURNS_SENT,
        "retries_configured": 0,
        "tools_requested": False,
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
        "request": request_plan(),
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

    if not args.send_request:
        _emit(_plan(description), args.out)
        return 0

    record = probe(settings, timeout=args.timeout, redact=redact)
    _emit(record, args.out)
    return 0 if record["verdict"] == VERDICT_CONNECTED else 1


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
