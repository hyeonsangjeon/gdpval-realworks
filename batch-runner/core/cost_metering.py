"""Turning a provider client into one that keeps its own receipts.

The pipeline calls models from a dozen places — a subprocess runner, a
container, a self-check, four judges, two perception readers. Threading a
ledger through every one of those signatures would touch most of the codebase
and would still miss whichever path was added last.

So the ledger is attached to the *client* instead. :meth:`CostRecorder.meter`
wraps whatever the provider factory returned, and from then on every
``chat.completions.create`` and ``responses.create`` that goes through it
reserves a row before the request and settles it after the reply, without the
calling code knowing. What the calling code does supply is *whose* call it is —
:meth:`CostRecorder.attributed` marks a block as belonging to one task at one
stage, and calls made inside it are filed there.

Metering is opt-in, one client at a time. A path nobody wrapped records
nothing, and its receipt says ``stage_unsupported`` rather than quietly
reporting a smaller bill. That is the intended behaviour for execution paths
that have no confirmed model call to meter: silence is reported as silence.

Nothing here contacts a provider. It sits between code that does and the
ledger.
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from core.cost_receipts import (
    BUCKETS,
    RETRY_NONE,
    RETRY_KINDS,
    STAGES,
    STAGE_BUCKET,
    CallUsage,
    CostReceipt,
    CostReceiptLedger,
    load_receipt_price_table,
    make_call_id,
)

__all__ = [
    "Attribution",
    "CostRecorder",
    "MeteredClient",
    "ROUTE_IDENTITY_ATTRIBUTE",
    "ReportedUsage",
    "RouteCallIdentity",
    "api_version_of",
    "deployment_of",
    "extract_usage",
    "open_cost_recorder",
    "read_reported_usage",
    "request_digest_of",
    "resolved_model_of",
    "route_identity_of",
]


@dataclass(frozen=True)
class Attribution:
    """Whose call this is: one task, one stage, one kind of retry."""

    task_id: str
    stage: str
    retry_kind: str = RETRY_NONE
    attempt_index: int = 0

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ValueError(f"unknown stage {self.stage!r}")
        if self.retry_kind not in RETRY_KINDS:
            raise ValueError(f"unknown retry kind {self.retry_kind!r}")
        if not self.task_id:
            raise ValueError("a metered call must belong to a task")

    @property
    def bucket(self) -> str:
        return STAGE_BUCKET[self.stage]


_CURRENT: ContextVar[Attribution | None] = ContextVar(
    "cost_attribution", default=None
)


@dataclass(frozen=True)
class RouteCallIdentity:
    """What a connection's builder knows that the connection cannot say.

    :func:`deployment_of` and :func:`api_version_of` normally read a client,
    because the client is what puts those values on the wire. Azure's undated
    ``/openai/v1/`` route defeats that: it is reached through the *plain*
    ``OpenAI`` class, which carries neither ``_azure_endpoint`` nor
    ``_api_version``, so an observer questioning the object sees an unmarked
    direct provider and honestly answers "unknown" to both. That is how a fully
    settled 84-call grading receipt came to record its deployment and its API
    version nowhere at all.

    The route knows. This is the route saying so, once, at the point of
    construction — not the meter guessing from a URL afterwards.
    """

    #: Whether the per-request ``model`` argument names an Azure deployment
    #: rather than a bare model. This is the endpoint's own routing rule, not a
    #: judgement about the string: on ``/openai/v1/`` the model argument is
    #: what selects the deployment, exactly as ``azure_deployment`` is on the
    #: dated route.
    model_argument_names_deployment: bool
    #: The API contract, where the route has a fixed one. A dated route
    #: resolves its own ``api-version`` and the client reports it, so a route
    #: that leaves this ``None`` is deferring to the client, not claiming the
    #: version is unknowable.
    api_version: str | None = None


#: Attribute a client builder may attach to carry a :class:`RouteCallIdentity`.
#: Read through :func:`_probe`, so a client that has never heard of it — every
#: client outside the typed Azure factory — simply says nothing.
ROUTE_IDENTITY_ATTRIBUTE = "_gdpval_route_call_identity"


# ── Reading usage off whatever the provider returned ─────────────────────


def _as_int(value: Any) -> int | None:
    """Accept a token count only if it is really one.

    ``bool`` is excluded on purpose — ``True`` is an ``int`` in Python and a
    truthy flag arriving where a count belongs should not silently become one
    token.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    return None


def _get(container: Any, name: str) -> Any:
    if container is None:
        return None
    if isinstance(container, Mapping):
        return container.get(name)
    return getattr(container, name, None)


def _probe(container: Any, name: str) -> Any:
    """Ask an object for an attribute, accepting "no answer" as an answer.

    Kept separate from :func:`_get` because this one reads *clients*, and a
    client is entitled to be hostile about attribute access. Step 2's typed
    Azure route wraps its client in a proxy that turns every failed lookup into
    a ``RuntimeError`` so provider exceptions cannot leak — which defeats
    ``getattr``'s default and would let a metering question kill the call it was
    only watching.

    Metering observes; it does not participate. So a container that refuses to
    answer is recorded as having said nothing, which is what ``None`` means
    everywhere else in this module. It never means the value was empty.
    """
    if container is None:
        return None
    if isinstance(container, Mapping):
        return container.get(name)
    try:
        return getattr(container, name)
    except Exception:
        return None


def _first_int(container: Any, *names: str) -> int | None:
    for name in names:
        found = _as_int(_get(container, name))
        if found is not None:
            return found
    return None


def extract_usage(response: Any) -> CallUsage:
    """Read one reply's token counts, whatever API shape it arrived in.

    Three shapes reach this function: the Chat Completions object with
    ``prompt_tokens``/``completion_tokens``, the Responses object with
    ``input_tokens``/``output_tokens``, and the normalised wrapper this
    repository puts around non-OpenAI providers. All three are read here so
    that no call site has to know which one it is holding.

    A field that is absent stays ``None``. It is not defaulted to zero — a
    provider that reported nothing has not told us the call was free.
    """
    usage = _get(response, "usage")
    if usage is None:
        return CallUsage()

    input_tokens = _first_int(usage, "input_tokens", "prompt_tokens")
    output_tokens = _first_int(usage, "output_tokens", "completion_tokens")

    cached = _first_int(usage, "cached_tokens", "cache_read_input_tokens")
    if cached is None:
        for details_name in ("prompt_tokens_details", "input_tokens_details"):
            cached = _first_int(_get(usage, details_name), "cached_tokens")
            if cached is not None:
                break

    reasoning = _first_int(usage, "reasoning_tokens")
    if reasoning is None:
        for details_name in (
            "completion_tokens_details",
            "output_tokens_details",
        ):
            reasoning = _first_int(_get(usage, details_name), "reasoning_tokens")
            if reasoning is not None:
                break

    return CallUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning,
    )


@dataclass(frozen=True)
class ReportedUsage:
    """One call's token counts, as a running tally needs them.

    Separate from :class:`CallUsage` because the two answer different
    questions. ``CallUsage`` is what the ledger stores, where an absent count
    must stay ``None`` forever and never becomes a zero. This is what a
    *caller keeping a running total* needs: counts it can add up, and one flag
    saying whether the total is still worth publishing.

    That flag deliberately does not depend on whether the prompt-cache
    breakdown arrived. Cached tokens are a *part* of the input, not an
    addition to it, so a call that comes back without a breakdown is still
    fully counted — counted as though none of it were served from cache, which
    is the conservative reading and can only overstate the bill, never
    understate it. Which calls had no breakdown is not lost by flattening it
    to zero here: the metered client records that call's
    ``cached_input_tokens`` as ``None`` in the receipt, and ``None`` is not
    ``0`` there.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    usage_complete: bool = False


def read_reported_usage(response: Any) -> ReportedUsage:
    """Read one reply's usage the way a running tally needs it.

    Three call sites keep their own token totals — the tool-calling judge and
    the two perception sub-judges — and each used to read the usage block
    itself. All three then treated a missing prompt-cache breakdown as
    *unknown usage*, which is neither what a missing breakdown means nor what
    the rest of this pipeline does with one:
    :func:`core.cost_receipts.price_call` charges a ``None`` cached count at
    the full uncached rate and does not call the receipt partial, and
    ``AgenticSandboxRunner._usage`` returns a complete tuple with a cached
    count of zero. This is the one place that decides, so the copies cannot
    disagree with the ledger — or with each other — again.

    Usage is incomplete when, and only when:

    * no usage block came back at all; or
    * the input or the output count is missing, or is not a count; or
    * more tokens were served from cache than were sent — a contradiction that
      makes both numbers untrustworthy, and the same check ``price_call``
      makes before it will put a number on a call.
    """
    usage = extract_usage(response)
    cached = usage.cached_input_tokens
    complete = usage.input_tokens is not None and usage.output_tokens is not None
    if (
        usage.input_tokens is not None
        and cached is not None
        and cached > usage.input_tokens
    ):
        complete = False
    return ReportedUsage(
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
        cached_tokens=cached or 0,
        usage_complete=complete,
    )


def resolved_model_of(response: Any, fallback: str) -> str:
    """The model the *reply* names, falling back to the one we asked for.

    A deployment alias and the model behind it can differ, and it is the model
    behind it that appears on the bill. Where the reply says nothing, the
    request's name is used and the price lookup either matches exactly or
    reports itself missing.
    """
    named = _get(response, "model")
    if isinstance(named, str) and named.strip():
        return named.strip()
    return fallback


def route_identity_of(client: Any) -> RouteCallIdentity | None:
    """The declaration a client's builder left on it, if it left one."""
    found = _probe(client, ROUTE_IDENTITY_ATTRIBUTE)
    return found if isinstance(found, RouteCallIdentity) else None


def api_version_of(client: Any) -> str | None:
    """The API version this client will put on the wire, if it has one.

    Read off the client rather than asked of the caller, because the client is
    what actually sends it: ``AzureOpenAI.__init__`` resolves the argument (or
    ``OPENAI_API_VERSION``) and keeps the result in ``_api_version``, and that
    resolved value is the one on every request.

    A client with nothing to say is asked whether its builder left a
    :class:`RouteCallIdentity` — Azure's undated v1 route travels over the
    plain ``OpenAI`` class and so has no ``_api_version`` to read, though its
    contract is perfectly well known to whoever opened the connection. A client
    with neither answers ``None``, which is a direct provider correctly saying
    the concept does not apply.

    Recorded because ``resolved_model`` alone does not say which API contract
    produced it, and two contracts can name the same model differently.
    """
    found = _probe(client, "_api_version")
    if isinstance(found, str) and found.strip():
        return found.strip()
    declared = route_identity_of(client)
    if declared is not None and declared.api_version:
        return declared.api_version
    return None


def deployment_of(client: Any, requested: str | None) -> str | None:
    """The deployment a request is routed to, where that is knowable.

    Not an inference — this is the SDK's own routing rule. ``AzureOpenAI``
    builds ``…/openai/deployments/{name}/…`` from the client-level
    ``azure_deployment`` when one was given, and otherwise from the per-request
    ``model`` argument. So on Azure the string a caller passes as the model IS
    the deployment, which is precisely the ambiguity that makes a receipt
    carrying only ``requested_model`` unpriceable: the reader cannot tell
    whether they are holding an alias or a model name.

    The same rule holds on the undated ``/openai/v1/`` route, but there the
    client is a plain ``OpenAI`` with no Azure attribute to find it by, so the
    route states it instead through a :class:`RouteCallIdentity`. Resolved per
    call in both cases, because one connection may legitimately address two
    deployments.

    Anything that is neither answers ``None``, because it has no deployment.
    ``None`` here means "does not apply or was not observed" — it never means
    the deployment was empty.
    """
    pinned = _probe(client, "_azure_deployment")
    if isinstance(pinned, str) and pinned.strip():
        return pinned.strip()
    declared = route_identity_of(client)
    routes_by_model = declared is not None and (
        declared.model_argument_names_deployment
    )
    # Presence only. The endpoint itself is never read out or recorded.
    if not routes_by_model and _probe(client, "_azure_endpoint") is None:
        return None
    text = (requested or "").strip()
    return text or None


def request_digest_of(payload: Any) -> str | None:
    """A fingerprint of what was asked, or nothing at all.

    Two rows carrying the same digest were sent the same request. That is the
    one question the ledger could not answer: when the four attempts at chunk 0
    were reconstructed, the 818 rows proved the *same positions* had been run
    four times, and could not prove the same *bytes* had been bought four
    times, because this column was empty in all 818. It is the same question
    run-to-run variance asks — a score that moved between two runs at one
    grader fingerprint means nothing until the requests behind it are known to
    have been identical.

    The digest is over the request as sent, with keys ordered, so the same call
    hashes the same on any machine and in any run. Nothing is excluded and
    nothing is normalised away: a field that differs is a request that differs,
    and a fingerprint that quietly forgave some fields would answer "same"
    about calls that were not.

    **A request that cannot be canonically rendered gets no digest at all.**
    The tempting alternative is to hash a lossy rendering — ``str`` of whatever
    would not serialise, say — and that is worse than nothing here, because the
    failure mode is a false *match*: two genuinely different requests collapsing
    onto one placeholder and reporting themselves identical. A missing digest
    only fails to answer. So ``None`` means "not captured", exactly as it does
    everywhere else in this module.

    Never raises. Metering observes; it does not participate. A payload holding
    something exotic — an open file, a proxy that objects to being read — must
    not take down the paid call it was only writing a note about.

    One-way by construction, which is what makes the column publishable: the
    ledger carries the digest of a prompt and never the prompt.
    """
    try:
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except Exception:  # noqa: BLE001 - see "never raises" above
        return None
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ── The recorder ─────────────────────────────────────────────────────────


class CostRecorder:
    """Files metered calls into a ledger under whichever task is in scope.

    ``round_index`` keeps a resumed run from colliding with the round before
    it. Call identifiers are derived from position rather than content, so the
    second round's first generation call would otherwise be named exactly like
    the first round's — and settling an already-settled identifier with
    different numbers is, correctly, an error. Numbering the round separates
    them, and the earlier round's costs survive alongside the new ones.
    """

    def __init__(
        self,
        ledger: CostReceiptLedger,
        *,
        run_id: str | None = None,
        round_index: int = 0,
    ):
        self.ledger = ledger
        self.run_id = str(run_id or ledger.run_id)
        self.round_index = int(round_index)
        self._sequences: dict[tuple[str, str, str, int], int] = {}

    # -- attribution -----------------------------------------------------

    @contextmanager
    def attributed(
        self,
        *,
        task_id: str,
        stage: str,
        retry_kind: str = RETRY_NONE,
        attempt_index: int | None = None,
    ) -> Iterator[Attribution]:
        """Mark a block of work as one task's, at one stage.

        Nests: a perception read taken during grading can open its own scope
        and the outer one is restored on the way out, so the two land in
        different components of the same receipt.
        """
        attribution = Attribution(
            task_id=str(task_id),
            stage=stage,
            retry_kind=retry_kind,
            attempt_index=(
                self.round_index if attempt_index is None else int(attempt_index)
            ),
        )
        token = _CURRENT.set(attribution)
        try:
            yield attribution
        finally:
            _CURRENT.reset(token)

    @staticmethod
    def current() -> Attribution | None:
        return _CURRENT.get()

    def _next_call_id(self, attribution: Attribution) -> str:
        key = (
            attribution.task_id,
            attribution.stage,
            attribution.retry_kind,
            attribution.attempt_index,
        )
        sequence = self._sequences.get(key, 0)
        self._sequences[key] = sequence + 1
        # The round is folded into the hashed run identity rather than left to
        # ``attempt_index``, because callers that know their own attempt number
        # — a Self-QA loop, say — pass one and would otherwise reuse the
        # previous round's identifiers exactly.
        return make_call_id(
            run_id=f"{self.run_id}|round{self.round_index}",
            task_id=attribution.task_id,
            stage=attribution.stage,
            retry_kind=attribution.retry_kind,
            attempt_index=attribution.attempt_index,
            sequence=sequence,
        )

    # -- metering --------------------------------------------------------

    def meter(
        self,
        client: Any,
        *,
        provider: str,
        model: str | None = None,
        stage: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
    ) -> "MeteredClient":
        """Wrap a provider client so its calls record themselves.

        ``stage`` pins every call made through this wrapper to one stage,
        overriding whatever scope it happens to run inside. That is how a
        perception reader sharing the judge's client still lands in its own
        component: the two get two wrappers around one connection, and the
        task in scope is taken from the enclosing block either way.

        ``deployment`` and ``api_version`` are overrides. Left unset — which is
        the normal case — both are read off the client itself, since the client
        is what puts them on the wire and asking the caller to restate them
        invites the two drifting apart. Pass one only where the caller knows
        something the client object does not.
        """
        if stage is not None and stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        return MeteredClient(
            client,
            recorder=self,
            provider=str(provider),
            default_model=model,
            stage=stage,
            deployment=deployment,
            api_version=api_version,
        )

    def record_call(
        self,
        *,
        provider: str,
        requested_model: str,
        response: Any,
        attribution: Attribution | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
    ) -> str | None:
        """File a call that has already happened.

        For the handful of paths that own their own transport and cannot be
        wrapped. Reserves and settles in one go, which means it cannot show a
        request that left and never came back — use :meth:`meter` where the
        call can be intercepted.

        Nothing here can see the client, so ``deployment`` and ``api_version``
        are the caller's to supply. Unsupplied, they are recorded as unknown
        rather than filled in from the request — a caller owning its own
        transport is exactly the caller whose routing we cannot observe.
        """
        target = attribution or self.current()
        if target is None:
            return None
        call_id = self._next_call_id(target)
        self.ledger.reserve(
            call_id=call_id,
            task_id=target.task_id,
            stage=target.stage,
            retry_kind=target.retry_kind,
            provider=provider,
            requested_model=requested_model,
            deployment=deployment,
            api_version=api_version,
        )
        self.ledger.settle(
            call_id,
            usage=extract_usage(response),
            resolved_model=resolved_model_of(response, requested_model),
        )
        return call_id

    def abandon_call(self, call_id: str, *, note: str | None = None) -> None:
        """Record that a reserved call never went out, so it cost nothing."""
        self.ledger.abandon(call_id, note=note)

    # -- reading ---------------------------------------------------------

    def receipt_for(
        self, task_id: str, bucket: str, **kwargs: Any
    ) -> CostReceipt:
        if bucket not in BUCKETS:
            raise ValueError(f"unknown bucket {bucket!r}")
        return self.ledger.receipt_for(task_id, bucket, **kwargs)


# ── The wrapper ──────────────────────────────────────────────────────────


class _MeteredCreate:
    """Stands in for one ``…create`` method and records around it."""

    def __init__(self, inner: Any, wrapper: "MeteredClient"):
        self._inner = inner
        self._wrapper = wrapper

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def create(self, **kwargs: Any) -> Any:
        return self._wrapper._around(self._inner.create, kwargs)


class _MeteredChat:
    def __init__(self, inner: Any, wrapper: "MeteredClient"):
        self._inner = inner
        self._wrapper = wrapper

    def __getattr__(self, name: str) -> Any:
        if name == "completions":
            return _MeteredCreate(self._inner.completions, self._wrapper)
        return getattr(self._inner, name)


class MeteredClient:
    """A provider client that writes a ledger row for every call it makes.

    Everything not intercepted is passed straight through, so this can stand in
    anywhere the unwrapped client stood. Only the two request methods are
    replaced.

    ``stage`` pins calls to one stage regardless of the scope they run in,
    which lets two wrappers around one connection file into two different
    components — the judge's own calls and the perception reads it shares its
    client with.

    When a call raises, the reservation is deliberately *left standing* rather
    than cleaned up. A request that timed out may well have been served and
    billed, and the honest record of that is an unsettled reservation, which
    turns the task's receipt ``partial`` with ``call_reachability_unknown``. A
    caller that knows the failure happened before anything left the process can
    say so with :meth:`CostRecorder.abandon_call`.
    """

    #: Lets code that must know a client's real provider type look through the
    #: wrapper. ``isinstance`` cannot see past a forwarding proxy, so the one
    #: place in the pipeline that dispatches on client type reads this instead.
    _is_cost_metered = True

    def __init__(
        self,
        inner: Any,
        *,
        recorder: CostRecorder,
        provider: str,
        default_model: str | None = None,
        stage: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
    ):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_recorder", recorder)
        object.__setattr__(self, "_provider", provider)
        object.__setattr__(self, "_default_model", default_model)
        object.__setattr__(self, "_stage", stage)
        object.__setattr__(self, "_deployment", deployment)
        # Resolved once, because a client's API version does not change between
        # calls. An explicit argument wins; otherwise the client is asked.
        object.__setattr__(
            self, "_api_version", api_version or api_version_of(inner)
        )
        object.__setattr__(self, "last_call_id", None)

    # -- the two request surfaces ----------------------------------------

    def __getattr__(self, name: str) -> Any:
        inner = object.__getattribute__(self, "_inner")
        if name == "responses":
            return _MeteredCreate(inner.responses, self)
        if name == "chat":
            return _MeteredChat(inner.chat, self)
        return getattr(inner, name)

    def chat_complete(self, **kwargs: Any) -> Any:
        """The normalised entry point non-OpenAI providers expose."""
        inner = object.__getattribute__(self, "_inner")
        return self._around(inner.chat_complete, kwargs)

    # -- passthrough for the parts callers rely on -----------------------

    @property
    def inner(self) -> Any:
        return object.__getattribute__(self, "_inner")

    @property
    def provider(self) -> str:
        return object.__getattribute__(self, "_provider")

    def close(self) -> None:
        inner = object.__getattribute__(self, "_inner")
        close = getattr(inner, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "MeteredClient":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    # -- internals -------------------------------------------------------

    def _around(self, call: Any, kwargs: dict[str, Any]) -> Any:
        recorder: CostRecorder = object.__getattribute__(self, "_recorder")
        attribution = recorder.current()
        if attribution is None:
            # Outside any task's scope. Report generation and other
            # out-of-band work belongs to neither pipeline, and inventing a
            # home for it would corrupt both totals.
            return call(**kwargs)

        pinned = object.__getattribute__(self, "_stage")
        if pinned is not None and pinned != attribution.stage:
            attribution = Attribution(
                task_id=attribution.task_id,
                stage=pinned,
                retry_kind=attribution.retry_kind,
                attempt_index=attribution.attempt_index,
            )

        requested = str(
            kwargs.get("model")
            or object.__getattribute__(self, "_default_model")
            or ""
        )
        inner = object.__getattribute__(self, "_inner")
        # Per call, because on Azure the deployment can be the request's own
        # ``model`` argument — one wrapper around one connection can legitimately
        # address two deployments.
        deployment = object.__getattribute__(
            self, "_deployment"
        ) or deployment_of(inner, requested)
        call_id = recorder._next_call_id(attribution)
        recorder.ledger.reserve(
            call_id=call_id,
            task_id=attribution.task_id,
            stage=attribution.stage,
            retry_kind=attribution.retry_kind,
            provider=object.__getattribute__(self, "_provider"),
            requested_model=requested,
            deployment=deployment,
            api_version=object.__getattribute__(self, "_api_version"),
            # Taken before the call rather than after, for the same reason the
            # row itself is: what a crashed call asked for is exactly what a
            # reader of the wreckage needs, and by then ``kwargs`` is gone.
            request_sha256=request_digest_of(kwargs),
        )
        object.__setattr__(self, "last_call_id", call_id)
        response = call(**kwargs)
        recorder.ledger.settle(
            call_id,
            usage=extract_usage(response),
            resolved_model=resolved_model_of(response, requested),
        )
        return response


# ── Opening a recorder for a run ─────────────────────────────────────────


def open_cost_recorder(
    path: Path | str,
    *,
    run_id: str,
    round_index: int = 0,
    continue_rounds: bool = False,
    price_table_path: Path | str | None = None,
    logger: Any = None,
) -> tuple[CostRecorder | None, str | None]:
    """Open the ledger for one run, or explain why there is none.

    Returns ``(recorder, note)``. A failure here does not stop the run: a
    pipeline that cannot open a bookkeeping file should still do the work it
    was started for. What it must not do is pretend the work was free, so the
    failure returns ``None`` and every receipt built afterwards says
    ``ledger_absent`` instead of showing a total.

    A missing or malformed price table is treated the same way but less
    severely — the ledger still records what was *sent*, and the receipts come
    out ``partial`` with ``price_missing`` rather than showing nothing at all.

    ``continue_rounds`` is for callers that resume without counting their own
    rounds. Where a run knows it is on round *n* it says so; where it only
    knows it is picking up a ledger somebody else left behind, this reads the
    round number off the ledger's own size. See
    :meth:`CostReceiptLedger.call_count`.
    """
    from pathlib import Path as _Path

    price_table = None
    note = None
    try:
        price_table = load_receipt_price_table(price_table_path)
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        note = (
            f"price table unreadable ({type(exc).__name__}); "
            "calls recorded unpriced"
        )
        if logger is not None:
            logger.warning("cost receipts: %s", note)

    try:
        ledger = CostReceiptLedger(
            _Path(path), run_id=run_id, price_table=price_table
        )
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        failure = f"cost ledger could not be opened ({type(exc).__name__})"
        if logger is not None:
            logger.warning("cost receipts: %s", failure)
        return None, failure

    if continue_rounds:
        round_index = max(int(round_index), ledger.call_count())
    return CostRecorder(ledger, round_index=round_index), note
