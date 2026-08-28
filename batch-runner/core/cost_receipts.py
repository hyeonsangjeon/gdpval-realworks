"""What each task actually cost, kept as two receipts that never add up.

The pre-run ceiling in :mod:`core.execution_envelope_cost` answers *how large
could the bill be*. This module answers a different question — *what did this
one task actually cost* — and it answers it twice per task, because solving a
problem and marking the answer are two separate pipelines with two separate
approvals, and a number that mixes them is worse than no number at all.

Three rules run through everything here.

**Zero is a measurement, not a default.** A missing usage block does not mean a
call was free; it means nobody can say what it cost. The honest output is
``partial`` with the confirmed part in ``known_cost_usd``, and
``estimated_cost_usd`` left as ``None``. The only real ``$0`` is a path that
never contacted a provider at all.

**A price has to match exactly.** A model is priced when the committed table
holds its ``provider:resolved_model`` key and not otherwise. No prefix match, no
nearest neighbour, no falling back to the family's flagship. An unpriced call is
recorded as unpriced.

**Nothing is ever removed.** A call that happened stays in the ledger even after
its output is thrown away and regenerated, even after a resumed round replaces
the answer, even after shards are merged. The cost of a run is what was spent,
not what survived.

Nothing in this module contacts a provider or spends anything.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

RECEIPT_SCHEMA_VERSION = "cost-receipt-v1"
PRICE_TABLE_SCHEMA_VERSION = "cost-receipt-price-table-v1"

PRICE_TABLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "execution_envelope"
    / "model_price_table.json"
)

TOKENS_PER_MILLION = Decimal(1_000_000)

#: Published amounts are rounded here. Eight places matches the precision the
#: rest of the pipeline already persists for conservative cost figures, and is
#: far below the smallest amount any single call can cost.
MONEY_PLACES = Decimal("0.00000001")


# ── The vocabulary the two sessions share ────────────────────────────────

STAGE_PREPROCESSING = "preprocessing"
STAGE_GENERATION = "generation"
STAGE_SELF_QA = "self_qa"
STAGE_GRADING = "grading"
STAGE_PERCEPTION = "perception"

STAGES = (
    STAGE_PREPROCESSING,
    STAGE_GENERATION,
    STAGE_SELF_QA,
    STAGE_GRADING,
    STAGE_PERCEPTION,
)

RETRY_NONE = "none"
RETRY_SEMANTIC = "semantic"
RETRY_INFRASTRUCTURE = "infrastructure"
RETRY_RESUME = "resume"
RETRY_INTERNAL_RECOVERY = "internal_recovery"

RETRY_KINDS = (
    RETRY_NONE,
    RETRY_SEMANTIC,
    RETRY_INFRASTRUCTURE,
    RETRY_RESUME,
    RETRY_INTERNAL_RECOVERY,
)

BUCKET_PROBLEM_SOLVING = "problem_solving_cost"
BUCKET_GRADING = "grading_cost"

BUCKETS = (BUCKET_PROBLEM_SOLVING, BUCKET_GRADING)

#: The one place that decides which pipeline a stage belongs to. Every caller
#: that needs the split reads it from here, so the two totals cannot drift into
#: each other through a second, disagreeing copy.
STAGE_BUCKET: dict[str, str] = {
    STAGE_PREPROCESSING: BUCKET_PROBLEM_SOLVING,
    STAGE_GENERATION: BUCKET_PROBLEM_SOLVING,
    STAGE_SELF_QA: BUCKET_PROBLEM_SOLVING,
    STAGE_GRADING: BUCKET_GRADING,
    STAGE_PERCEPTION: BUCKET_GRADING,
}

STATUS_COMPLETE = "complete"
STATUS_PARTIAL = "partial"
STATUS_UNAVAILABLE = "unavailable"
STATUS_NOT_RUN = "not_run"

STATUSES = (
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    STATUS_NOT_RUN,
)

REASON_USAGE_ABSENT = "usage_absent"
REASON_USAGE_PARTIAL = "usage_partial"
REASON_PRICE_MISSING = "price_missing"
REASON_CALL_REACHABILITY_UNKNOWN = "call_reachability_unknown"
REASON_RUNTIME_UNATTRIBUTABLE = "runtime_cost_unattributable"
REASON_RUNTIME_UNPRICED = "runtime_cost_unpriced"
REASON_LEDGER_ABSENT = "ledger_absent"
REASON_STAGE_UNSUPPORTED = "stage_unsupported"

MISSING_REASONS = (
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    REASON_PRICE_MISSING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_RUNTIME_UNATTRIBUTABLE,
    REASON_RUNTIME_UNPRICED,
    REASON_LEDGER_ABSENT,
    REASON_STAGE_UNSUPPORTED,
)

STATE_RESERVED = "reserved"
STATE_SETTLED = "settled"
STATE_ABANDONED = "abandoned"

ATTRIBUTION_PER_TASK = "per_task"
ATTRIBUTION_SHARED = "shared"

REASONING_BILLED_AS_OUTPUT = "output"
REASONING_BILLED_SEPARATELY = "separate"
REASONING_BILLED_UNKNOWN = "unknown"


class LedgerIntegrityError(RuntimeError):
    """The ledger was asked to contradict something it already recorded.

    Raised rather than resolved. A second settlement that disagrees with the
    first is not a race to be smoothed over — it means two different beliefs
    exist about what one call cost, and only a person can say which is right.
    """


# ── The committed price list ─────────────────────────────────────────────


@dataclass(frozen=True)
class ModelReceiptPrice:
    """What one provider's one model costs, per million tokens.

    ``reasoning_billed_as`` is the field that stops the same tokens being
    charged twice. Where a provider counts its own reasoning inside the output
    it reports, those tokens are already paid for by ``output_usd_per_million``
    and must not be multiplied again; where it bills them separately they must.
    Where nobody has established which, the call cannot be priced.
    """

    provider: str
    model: str
    input_usd_per_million: Decimal
    cached_input_usd_per_million: Decimal
    output_usd_per_million: Decimal
    reasoning_billed_as: str
    reasoning_usd_per_million: Decimal | None
    source: str
    last_reviewed: str
    currency: str
    unit: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True)
class RuntimePrice:
    """What a paid execution environment costs, and whether it can be attributed.

    ``attribution`` is the whole point. A container started for one task can be
    billed to that task. A pool shared by many cannot be divided among them
    without inventing a division, so it is not divided — see
    :meth:`CostReceiptLedger.record_runtime_cost`.
    """

    kind: str
    usd_per_hour: Decimal
    attribution: str
    source: str
    last_reviewed: str
    currency: str


@dataclass(frozen=True)
class ReceiptPriceTable:
    """The committed prices, plus the fingerprint of the file they came from."""

    models: Mapping[str, ModelReceiptPrice]
    runtimes: Mapping[str, RuntimePrice]
    sha256: str
    currency: str

    def lookup(self, provider: str, model: str) -> ModelReceiptPrice | None:
        """Find a price by exact ``provider:model``, or return ``None``.

        Deliberately not forgiving. ``None`` here becomes ``price_missing`` in
        the receipt, which is a smaller problem than a number computed from the
        wrong model's rates.
        """
        if not provider or not model:
            return None
        return self.models.get(f"{provider}:{model}")

    def runtime(self, kind: str) -> RuntimePrice | None:
        if not kind:
            return None
        return self.runtimes.get(kind)


def _decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 - re-raised with a readable message
        raise ValueError(f"{field_name} is not a number: {value!r}") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field_name} must be a finite amount of at least zero")
    return parsed


def load_receipt_price_table(
    path: str | Path | None = None,
) -> ReceiptPriceTable:
    """Read the committed receipt prices and fingerprint the file they are in.

    The fingerprint covers the whole file, not just the block read here, so a
    receipt that records it can be checked against the exact bytes that priced
    it. The pre-run ceiling's own ``models`` block lives in the same file and is
    left untouched; this reader ignores it.
    """
    target = Path(path) if path is not None else PRICE_TABLE_PATH
    if not target.is_file():
        raise ValueError(f"the price list is missing at {target}")
    raw_bytes = target.read_bytes()
    digest = hashlib.sha256(raw_bytes).hexdigest()
    try:
        document = json.loads(raw_bytes)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"the price list at {target} is not valid JSON") from exc
    if not isinstance(document, Mapping):
        raise ValueError("the price list must be a block of settings")
    version = document.get("cost_receipt_schema_version")
    if version != PRICE_TABLE_SCHEMA_VERSION:
        raise ValueError(
            "the receipt price list was written for "
            f"{version!r}, but this code reads {PRICE_TABLE_SCHEMA_VERSION!r}"
        )

    models: dict[str, ModelReceiptPrice] = {}
    for key, entry in dict(document.get("providers") or {}).items():
        if not isinstance(entry, Mapping):
            raise ValueError(f"the price entry for {key} is not a block")
        if ":" not in str(key):
            raise ValueError(
                f"the price key {key!r} must name a provider and a model, "
                "written as provider:model"
            )
        provider, _, model = str(key).partition(":")
        if not provider or not model:
            raise ValueError(
                f"the price key {key!r} must name both a provider and a model"
            )
        for required in ("source", "last_reviewed"):
            if not str(entry.get(required) or "").strip():
                raise ValueError(
                    f"the price entry for {key} has no {required}; a price "
                    "nobody can trace is not a price"
                )
        if entry.get("currency") != "USD":
            raise ValueError(f"the price entry for {key} must be in USD")
        billed_as = str(entry.get("reasoning_billed_as") or "")
        if billed_as not in (
            REASONING_BILLED_AS_OUTPUT,
            REASONING_BILLED_SEPARATELY,
            REASONING_BILLED_UNKNOWN,
        ):
            raise ValueError(
                f"the price entry for {key} does not say how reasoning tokens "
                "are billed; it must be one of output, separate, unknown"
            )
        reasoning_rate: Decimal | None = None
        if billed_as == REASONING_BILLED_SEPARATELY:
            if "reasoning_usd_per_million" not in entry:
                raise ValueError(
                    f"the price entry for {key} bills reasoning separately but "
                    "states no rate for it"
                )
            reasoning_rate = _decimal(
                entry["reasoning_usd_per_million"],
                field_name=f"{key}.reasoning_usd_per_million",
            )
        models[str(key)] = ModelReceiptPrice(
            provider=provider,
            model=model,
            input_usd_per_million=_decimal(
                entry["input_usd_per_million"],
                field_name=f"{key}.input_usd_per_million",
            ),
            cached_input_usd_per_million=_decimal(
                entry["cached_input_usd_per_million"],
                field_name=f"{key}.cached_input_usd_per_million",
            ),
            output_usd_per_million=_decimal(
                entry["output_usd_per_million"],
                field_name=f"{key}.output_usd_per_million",
            ),
            reasoning_billed_as=billed_as,
            reasoning_usd_per_million=reasoning_rate,
            source=str(entry["source"]),
            last_reviewed=str(entry["last_reviewed"]),
            currency="USD",
            unit=str(entry.get("unit") or "per 1,000,000 tokens"),
        )

    runtimes: dict[str, RuntimePrice] = {}
    for kind, entry in dict(document.get("runtime") or {}).items():
        if not isinstance(entry, Mapping):
            raise ValueError(f"the runtime price entry for {kind} is not a block")
        attribution = str(entry.get("attribution") or "")
        if attribution not in (ATTRIBUTION_PER_TASK, ATTRIBUTION_SHARED):
            raise ValueError(
                f"the runtime price entry for {kind} must say whether it is "
                "per_task or shared"
            )
        for required in ("source", "last_reviewed"):
            if not str(entry.get(required) or "").strip():
                raise ValueError(
                    f"the runtime price entry for {kind} has no {required}"
                )
        if entry.get("currency") != "USD":
            raise ValueError(f"the runtime price entry for {kind} must be in USD")
        runtimes[str(kind)] = RuntimePrice(
            kind=str(kind),
            usd_per_hour=_decimal(
                entry["usd_per_hour"], field_name=f"{kind}.usd_per_hour"
            ),
            attribution=attribution,
            source=str(entry["source"]),
            last_reviewed=str(entry["last_reviewed"]),
            currency="USD",
        )

    return ReceiptPriceTable(
        models=models, runtimes=runtimes, sha256=digest, currency="USD"
    )


# ── What one call reports back ───────────────────────────────────────────


@dataclass(frozen=True)
class CallUsage:
    """How much one call sent and wrote back, as the provider reported it.

    Every field may be ``None``, and ``None`` never becomes ``0``. A provider
    that returns no usage block has told us nothing, and nothing is not zero.

    ``cached_input_tokens`` is understood the way providers report it: as a
    part of ``input_tokens``, not an addition to it. The billable input is
    therefore the difference, which is what :func:`price_call` charges.
    """

    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.input_tokens is None
            and self.output_tokens is None
            and self.cached_input_tokens is None
            and self.reasoning_tokens is None
        )

    def as_dict(self) -> dict[str, int | None]:
        return {
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }


@dataclass(frozen=True)
class PricedCall:
    """The result of trying to put a number on one call."""

    cost_usd: Decimal | None
    missing_reasons: tuple[str, ...]

    @property
    def is_priced(self) -> bool:
        return self.cost_usd is not None and not self.missing_reasons


def price_call(
    price: ModelReceiptPrice | None, usage: CallUsage
) -> PricedCall:
    """Charge one call, or say why it cannot be charged.

    The two traps this exists to avoid:

    *Cached input counted twice.* Providers report ``input_tokens`` inclusive of
    whatever they served from cache. Charging the full input at the full rate
    and then charging the cached part again at the cache rate bills the same
    tokens twice. Only the difference is charged at full rate.

    *Reasoning counted twice.* Where reasoning tokens are already inside the
    reported output, charging them again on top double-bills the model's
    thinking. The price entry says which it is, and where it says ``unknown``
    and reasoning actually happened, the call is left unpriced rather than
    guessed.
    """
    reasons: list[str] = []
    if usage.is_empty:
        reasons.append(REASON_USAGE_ABSENT)
    elif usage.input_tokens is None or usage.output_tokens is None:
        reasons.append(REASON_USAGE_PARTIAL)

    cached = usage.cached_input_tokens or 0
    if usage.input_tokens is not None and cached > usage.input_tokens:
        # More was served from cache than was sent. One of the two numbers is
        # wrong and there is no way to tell which, so neither is trusted.
        if REASON_USAGE_PARTIAL not in reasons:
            reasons.append(REASON_USAGE_PARTIAL)

    if price is None:
        reasons.append(REASON_PRICE_MISSING)

    reasoning = usage.reasoning_tokens or 0
    if (
        price is not None
        and reasoning > 0
        and price.reasoning_billed_as == REASONING_BILLED_UNKNOWN
    ):
        if REASON_USAGE_PARTIAL not in reasons:
            reasons.append(REASON_USAGE_PARTIAL)

    if reasons:
        return PricedCall(cost_usd=None, missing_reasons=tuple(reasons))

    assert price is not None  # narrowed by the checks above
    billable_input = Decimal(max((usage.input_tokens or 0) - cached, 0))
    cost = (
        billable_input * price.input_usd_per_million
        + Decimal(cached) * price.cached_input_usd_per_million
        + Decimal(usage.output_tokens or 0) * price.output_usd_per_million
    )
    if (
        price.reasoning_billed_as == REASONING_BILLED_SEPARATELY
        and price.reasoning_usd_per_million is not None
    ):
        cost += Decimal(reasoning) * price.reasoning_usd_per_million
    return PricedCall(cost_usd=cost / TOKENS_PER_MILLION, missing_reasons=())


def make_call_id(
    *,
    run_id: str,
    task_id: str,
    stage: str,
    retry_kind: str,
    attempt_index: int,
    sequence: int,
) -> str:
    """A name for one call that two processes will agree on without talking.

    Derived only from where the call sits in the run, never from what it says.
    That keeps prompts out of the ledger and makes a merged shard's rows line up
    with the originals, so the same call cannot be counted twice under two
    different names.
    """
    material = "|".join(
        (
            str(run_id),
            str(task_id),
            str(stage),
            str(retry_kind),
            str(int(attempt_index)),
            str(int(sequence)),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ── The receipt ──────────────────────────────────────────────────────────


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP))


def _read_count(value: Any) -> int:
    """A call count read back off a published receipt; nonsense reads as zero.

    Unlike an amount, a bad count cannot make a receipt overstate what is
    known — the money fields are checked separately — so this one degrades
    quietly rather than voiding the receipt.
    """
    if value is None or isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed >= 0 else 0


def _read_money(value: Any) -> Decimal | None:
    """Take an amount back off a published receipt, or say it is not one.

    The round trip goes through JSON, so what comes back is a float. It is
    turned into a :class:`~decimal.Decimal` by way of its shortest decimal
    spelling rather than its binary expansion, so that ``0.1`` written out
    reads back as ``0.1`` and a column of them still adds up.

    An absent amount reads as zero; an amount that is present but is not a
    number returns ``None``, and the caller turns that into an unavailable
    receipt. The distinction matters: a corrupt figure quietly read as ``0``
    would leave a ``complete`` receipt claiming the work was free.
    """
    if value is None:
        return Decimal(0)
    try:
        parsed = Decimal(str(value))
    except Exception:  # noqa: BLE001 - a corrupt amount is not a real amount
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


@dataclass(frozen=True)
class ReceiptComponent:
    """One line of a receipt: what one stage, at one retry kind, cost."""

    stage: str
    retry_kind: str
    status: str
    model_calls: int
    known_cost_usd: Decimal
    usage: dict[str, int | None]
    missing_reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "retry_kind": self.retry_kind,
            "status": self.status,
            "model_calls": self.model_calls,
            "known_cost_usd": _money(self.known_cost_usd),
            "usage": dict(self.usage),
            "missing_reasons": list(self.missing_reasons),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReceiptComponent":
        known = _read_money(payload.get("known_cost_usd"))
        return cls(
            stage=str(payload.get("stage") or ""),
            retry_kind=str(payload.get("retry_kind") or RETRY_NONE),
            status=(
                str(payload.get("status") or STATUS_UNAVAILABLE)
                if known is not None
                else STATUS_UNAVAILABLE
            ),
            model_calls=_read_count(payload.get("model_calls")),
            known_cost_usd=known if known is not None else Decimal(0),
            usage=dict(payload.get("usage") or {}),
            missing_reasons=tuple(sorted(_decode_reasons(
                payload.get("missing_reasons")
            ))),
        )


@dataclass(frozen=True)
class CostReceipt:
    """What one pipeline cost for one task — or why that cannot be said.

    ``estimated_cost_usd`` is the only field that claims to be a total, and it
    is populated only when :data:`STATUS_COMPLETE` holds. ``known_cost_usd`` is
    always the sum of what was confirmed, which on a partial receipt is a floor
    and must never be displayed as a total.
    """

    status: str
    currency: str = "USD"
    known_cost_usd: Decimal = Decimal(0)
    model_cost_usd: Decimal = Decimal(0)
    runtime_cost_usd: Decimal = Decimal(0)
    model_calls: int = 0
    usage: dict[str, int | None] = field(default_factory=dict)
    components: tuple[ReceiptComponent, ...] = ()
    price_table_sha256: str | None = None
    missing_reasons: tuple[str, ...] = ()

    @property
    def estimated_cost_usd(self) -> Decimal | None:
        if self.status != STATUS_COMPLETE:
            return None
        return self.known_cost_usd

    def as_dict(self) -> dict[str, Any]:
        estimated = self.estimated_cost_usd
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "status": self.status,
            "currency": self.currency,
            "estimated_cost_usd": None if estimated is None else _money(estimated),
            "known_cost_usd": _money(self.known_cost_usd),
            "model_cost_usd": _money(self.model_cost_usd),
            "runtime_cost_usd": _money(self.runtime_cost_usd),
            "model_calls": self.model_calls,
            "usage": dict(self.usage),
            "components": [entry.as_dict() for entry in self.components],
            "price_table_sha256": self.price_table_sha256,
            "missing_reasons": list(self.missing_reasons),
        }

    @classmethod
    def not_run(cls) -> "CostReceipt":
        """This pipeline did not run. Not free — it did not happen."""
        return cls(status=STATUS_NOT_RUN)

    @classmethod
    def unavailable(
        cls, *, reasons: Sequence[str] = (REASON_LEDGER_ABSENT,)
    ) -> "CostReceipt":
        """It ran, but this run kept no record that could price it."""
        return cls(status=STATUS_UNAVAILABLE, missing_reasons=tuple(reasons))

    @classmethod
    def free(cls, *, price_table_sha256: str | None = None) -> "CostReceipt":
        """It ran, made no model call at all, and therefore really cost nothing.

        The one honest ``$0``. Reserved for paths that reach a verdict by rule
        rather than by asking a model.
        """
        return cls(
            status=STATUS_COMPLETE,
            price_table_sha256=price_table_sha256,
        )

    @classmethod
    def from_dict(cls, payload: Any) -> "CostReceipt":
        """Read a published receipt back, for summing rows that are already out.

        Needed wherever the totals must come from what was *published* rather
        than from a live ledger: a resumed grading run whose earlier tasks were
        written by an earlier process, and shard merging, where the shards' own
        ledgers may be long gone. Reading the rows keeps the summary equal to
        the sum of the receipts a reader can actually see.

        ``estimated_cost_usd`` is recomputed from ``status`` rather than
        trusted, so a file that had been edited to show a total on an
        incomplete receipt does not get to keep it. Anything that is not a
        readable receipt of this version comes back
        :meth:`unavailable` — a row we cannot price is not a row that cost
        nothing.
        """
        if not isinstance(payload, Mapping):
            return cls.unavailable()
        if payload.get("schema_version") != RECEIPT_SCHEMA_VERSION:
            return cls.unavailable()
        status = str(payload.get("status") or "")
        if status not in STATUSES:
            return cls.unavailable()
        if status == STATUS_NOT_RUN:
            return cls.not_run()
        known = _read_money(payload.get("known_cost_usd"))
        model_cost = _read_money(payload.get("model_cost_usd"))
        runtime_cost = _read_money(payload.get("runtime_cost_usd"))
        if known is None or model_cost is None or runtime_cost is None:
            return cls.unavailable()
        return cls(
            status=status,
            currency=str(payload.get("currency") or "USD"),
            known_cost_usd=known,
            model_cost_usd=model_cost,
            runtime_cost_usd=runtime_cost,
            model_calls=_read_count(payload.get("model_calls")),
            usage=dict(payload.get("usage") or {}),
            components=tuple(
                ReceiptComponent.from_dict(entry)
                for entry in (payload.get("components") or [])
                if isinstance(entry, Mapping)
            ),
            price_table_sha256=payload.get("price_table_sha256") or None,
            missing_reasons=tuple(sorted(_decode_reasons(
                payload.get("missing_reasons")
            ))),
        )


def empty_usage() -> dict[str, int | None]:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
    }


# ── The ledger ───────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cost_calls (
    call_id             TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL,
    task_id             TEXT NOT NULL,
    stage               TEXT NOT NULL,
    retry_kind          TEXT NOT NULL,
    provider            TEXT NOT NULL,
    requested_model     TEXT NOT NULL,
    resolved_model      TEXT,
    state               TEXT NOT NULL,
    input_tokens        INTEGER,
    cached_input_tokens INTEGER,
    output_tokens       INTEGER,
    reasoning_tokens    INTEGER,
    model_cost_usd      TEXT,
    missing_reasons     TEXT NOT NULL DEFAULT '[]',
    price_table_sha256  TEXT,
    request_sha256      TEXT,
    note                TEXT
);

CREATE TABLE IF NOT EXISTS cost_runtime (
    entry_id            TEXT PRIMARY KEY,
    run_id              TEXT NOT NULL,
    task_id             TEXT NOT NULL,
    bucket              TEXT NOT NULL,
    runtime_kind        TEXT NOT NULL,
    attribution         TEXT NOT NULL,
    runtime_cost_usd    TEXT,
    missing_reasons     TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS cost_calls_task ON cost_calls (task_id, stage);
CREATE INDEX IF NOT EXISTS cost_runtime_task ON cost_runtime (task_id, bucket);
"""

_CALL_COLUMNS = (
    "call_id",
    "run_id",
    "task_id",
    "stage",
    "retry_kind",
    "provider",
    "requested_model",
    "resolved_model",
    "state",
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "model_cost_usd",
    "missing_reasons",
    "price_table_sha256",
    "request_sha256",
    "note",
)

_RUNTIME_COLUMNS = (
    "entry_id",
    "run_id",
    "task_id",
    "bucket",
    "runtime_kind",
    "attribution",
    "runtime_cost_usd",
    "missing_reasons",
)


class CostReceiptLedger:
    """An append-only record of every call that was paid for.

    Two writes per call. :meth:`reserve` happens *before* the request goes out,
    :meth:`settle` after the reply comes back. The gap between them is not
    bookkeeping pedantry — it is the only way to notice a call that left and
    never returned. A reservation that is never settled stays in the ledger as
    exactly that, and turns its task's receipt ``partial`` with
    ``call_reachability_unknown``, because a request that may have been served
    may also have been billed.

    Rows are never deleted and never silently rewritten. Settling the same call
    twice with the same numbers is a no-op, which makes retried writes and
    re-imported shards safe. Settling it twice with *different* numbers raises
    :class:`LedgerIntegrityError`.

    Concurrency is left to SQLite. Shards run as separate processes against the
    same file, and a primary key on ``call_id`` is what stops the same call
    being counted once per process.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: str,
        price_table: ReceiptPriceTable | None = None,
    ):
        self.path = Path(path)
        self.run_id = str(run_id)
        self._price_table = price_table
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path), timeout=30.0)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.executescript(_SCHEMA)
        self._connection.commit()

    # -- lifecycle -------------------------------------------------------

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "CostReceiptLedger":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    @property
    def price_table(self) -> ReceiptPriceTable | None:
        return self._price_table

    # -- writing ---------------------------------------------------------

    def reserve(
        self,
        *,
        call_id: str,
        task_id: str,
        stage: str,
        retry_kind: str,
        provider: str,
        requested_model: str,
        request_sha256: str | None = None,
        note: str | None = None,
    ) -> str:
        """Record that a call is about to go out.

        Written before the request, so that a crash between here and the reply
        leaves evidence rather than silence.
        """
        _require(stage in STAGES, f"unknown stage {stage!r}")
        _require(retry_kind in RETRY_KINDS, f"unknown retry kind {retry_kind!r}")
        _require(bool(task_id), "a call must belong to a task")
        if request_sha256 is not None:
            _require(
                _is_sha256(request_sha256),
                "a request identifier may only be recorded as a SHA-256 digest",
            )
        existing = self._row(call_id)
        if existing is not None:
            # A resumed round re-reserving a call it already recorded. Keep the
            # original row; re-reserving must never reset a settled one.
            return call_id
        self._connection.execute(
            "INSERT INTO cost_calls (call_id, run_id, task_id, stage, "
            "retry_kind, provider, requested_model, state, missing_reasons, "
            "request_sha256, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)",
            (
                call_id,
                self.run_id,
                str(task_id),
                stage,
                retry_kind,
                str(provider),
                str(requested_model),
                STATE_RESERVED,
                request_sha256,
                note,
            ),
        )
        self._connection.commit()
        return call_id

    def settle(
        self,
        call_id: str,
        *,
        usage: CallUsage,
        resolved_model: str | None = None,
        extra_reasons: Sequence[str] = (),
    ) -> PricedCall:
        """Record what the call actually reported, and price it.

        ``resolved_model`` is the model the *reply* names. Where a provider
        answers a deployment alias with a different underlying model, the reply
        is what gets priced, because the reply is what was billed.
        """
        row = self._row(call_id)
        if row is None:
            raise LedgerIntegrityError(
                f"call {call_id} was settled without ever being reserved"
            )
        if row["state"] == STATE_ABANDONED:
            raise LedgerIntegrityError(
                f"call {call_id} was recorded as never sent, and cannot now "
                "report usage"
            )

        model = str(resolved_model or row["requested_model"] or "")
        price = None
        table = self._price_table
        if table is not None:
            price = table.lookup(str(row["provider"]), model)
        priced = price_call(price, usage)
        reasons = list(priced.missing_reasons)
        for reason in extra_reasons:
            _require(reason in MISSING_REASONS, f"unknown reason {reason!r}")
            if reason not in reasons:
                reasons.append(reason)
        if table is None and REASON_PRICE_MISSING not in reasons:
            reasons.append(REASON_PRICE_MISSING)
        cost = None if reasons else priced.cost_usd

        if row["state"] == STATE_SETTLED:
            self._require_same_settlement(row, usage, model, cost, reasons)
            return PricedCall(cost_usd=cost, missing_reasons=tuple(reasons))

        self._connection.execute(
            "UPDATE cost_calls SET state = ?, resolved_model = ?, "
            "input_tokens = ?, cached_input_tokens = ?, output_tokens = ?, "
            "reasoning_tokens = ?, model_cost_usd = ?, missing_reasons = ?, "
            "price_table_sha256 = ? WHERE call_id = ?",
            (
                STATE_SETTLED,
                model,
                usage.input_tokens,
                usage.cached_input_tokens,
                usage.output_tokens,
                usage.reasoning_tokens,
                None if cost is None else str(cost),
                json.dumps(sorted(reasons)),
                None if table is None else table.sha256,
                call_id,
            ),
        )
        self._connection.commit()
        return PricedCall(cost_usd=cost, missing_reasons=tuple(reasons))

    def abandon(self, call_id: str, *, note: str | None = None) -> None:
        """Record that the call never left — so it never cost anything.

        Only correct where the failure is known to precede the request: a
        prompt that could not be assembled, a client that could not be built.
        A timeout is *not* this; a timeout leaves the reservation standing,
        because the request may well have been served and billed.
        """
        row = self._row(call_id)
        if row is None:
            raise LedgerIntegrityError(
                f"call {call_id} was abandoned without ever being reserved"
            )
        if row["state"] == STATE_SETTLED:
            raise LedgerIntegrityError(
                f"call {call_id} already reported usage and cannot now be "
                "recorded as never sent"
            )
        self._connection.execute(
            "UPDATE cost_calls SET state = ?, note = COALESCE(?, note) "
            "WHERE call_id = ?",
            (STATE_ABANDONED, note, call_id),
        )
        self._connection.commit()

    def record_runtime_cost(
        self,
        *,
        entry_id: str,
        task_id: str,
        bucket: str,
        runtime_kind: str,
        seconds: float | None = None,
        usd: Decimal | None = None,
    ) -> None:
        """Record a paid execution environment against one task, if it can be.

        A shared environment is recorded but **not** costed. Splitting a pool's
        bill across the tasks that happened to use it produces a number that
        looks like measurement and is not one, so the entry carries
        ``runtime_cost_unattributable`` instead and holds the task's receipt at
        ``partial``. Under-claiming is recoverable; a fabricated split is not.
        """
        _require(bucket in BUCKETS, f"unknown bucket {bucket!r}")
        reasons: list[str] = []
        amount: Decimal | None = None
        price = (
            self._price_table.runtime(runtime_kind)
            if self._price_table is not None
            else None
        )
        if usd is not None:
            amount = Decimal(str(usd))
        elif price is None:
            reasons.append(REASON_RUNTIME_UNPRICED)
        elif price.attribution == ATTRIBUTION_SHARED:
            reasons.append(REASON_RUNTIME_UNATTRIBUTABLE)
        elif seconds is None:
            reasons.append(REASON_RUNTIME_UNPRICED)
        else:
            amount = (
                price.usd_per_hour * Decimal(str(seconds)) / Decimal(3600)
            )
        if price is not None and price.attribution == ATTRIBUTION_SHARED:
            amount = None
            if REASON_RUNTIME_UNATTRIBUTABLE not in reasons:
                reasons.append(REASON_RUNTIME_UNATTRIBUTABLE)
        self._connection.execute(
            "INSERT OR REPLACE INTO cost_runtime (entry_id, run_id, task_id, "
            "bucket, runtime_kind, attribution, runtime_cost_usd, "
            "missing_reasons) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(entry_id),
                self.run_id,
                str(task_id),
                bucket,
                str(runtime_kind),
                price.attribution if price is not None else "unknown",
                None if amount is None else str(amount),
                json.dumps(sorted(reasons)),
            ),
        )
        self._connection.commit()

    # -- reading ---------------------------------------------------------

    def call_count(self) -> int:
        """How many calls this ledger already holds.

        A resumed run reads this to number its round. Identifiers are derived
        from position, so a task that was being graded when the previous
        process died would otherwise be re-graded under exactly the same
        identifiers — and settling one of those a second time, with the second
        attempt's token counts, is a contradiction the ledger refuses. Starting
        the new round at the current row count separates them, and it is
        monotonic for the only reason that matters: a round can only repeat a
        count it has already written past.
        """
        row = self._connection.execute(
            "SELECT COUNT(*) AS n FROM cost_calls"
        ).fetchone()
        return int(row["n"]) if row is not None else 0

    def task_ids(self) -> list[str]:
        rows = self._connection.execute(
            "SELECT DISTINCT task_id FROM cost_calls "
            "UNION SELECT DISTINCT task_id FROM cost_runtime"
        ).fetchall()
        return sorted(str(row["task_id"]) for row in rows)

    def calls_for(self, task_id: str, *, bucket: str | None = None) -> list[dict]:
        rows = self._connection.execute(
            "SELECT * FROM cost_calls WHERE task_id = ? ORDER BY call_id",
            (str(task_id),),
        ).fetchall()
        out = []
        for row in rows:
            if bucket is not None and STAGE_BUCKET.get(row["stage"]) != bucket:
                continue
            out.append(_row_to_dict(row, _CALL_COLUMNS))
        return out

    def receipt_for(
        self,
        task_id: str,
        bucket: str,
        *,
        when_empty: str = STATUS_NOT_RUN,
    ) -> CostReceipt:
        """Build one task's receipt for one pipeline.

        ``when_empty`` settles what silence means, because the ledger cannot
        tell on its own. No rows may mean the pipeline never ran
        (:data:`STATUS_NOT_RUN`), or ran by rule without calling a model
        (:data:`STATUS_COMPLETE`, a real ``$0``), or ran on a build that kept no
        record (:data:`STATUS_UNAVAILABLE`). Those are three different sentences
        and the caller knows which one applies.
        """
        _require(bucket in BUCKETS, f"unknown bucket {bucket!r}")
        _require(
            when_empty in (STATUS_NOT_RUN, STATUS_COMPLETE, STATUS_UNAVAILABLE),
            f"unknown empty meaning {when_empty!r}",
        )
        calls = self.calls_for(task_id, bucket=bucket)
        runtime_rows = [
            _row_to_dict(row, _RUNTIME_COLUMNS)
            for row in self._connection.execute(
                "SELECT * FROM cost_runtime WHERE task_id = ? AND bucket = ? "
                "ORDER BY entry_id",
                (str(task_id), bucket),
            ).fetchall()
        ]
        if not calls and not runtime_rows:
            if when_empty == STATUS_NOT_RUN:
                return CostReceipt.not_run()
            if when_empty == STATUS_UNAVAILABLE:
                return CostReceipt.unavailable()
            return CostReceipt.free(
                price_table_sha256=(
                    self._price_table.sha256
                    if self._price_table is not None
                    else None
                )
            )
        return build_receipt(
            calls,
            runtime_rows,
            price_table_sha256=(
                self._price_table.sha256 if self._price_table is not None else None
            ),
        )

    # -- exchange --------------------------------------------------------

    def export_jsonl(self, path: str | Path) -> str:
        """Write the ledger out as one line per record, and return its digest.

        Deterministic: fixed key order, rows sorted by identifier. Two exports
        of the same ledger produce byte-identical files, which is what lets the
        digest published beside a result mean anything.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for row in self._connection.execute(
            "SELECT * FROM cost_calls ORDER BY call_id"
        ).fetchall():
            record = _row_to_dict(row, _CALL_COLUMNS)
            record["record_type"] = "call"
            lines.append(_canonical_json(record))
        for row in self._connection.execute(
            "SELECT * FROM cost_runtime ORDER BY entry_id"
        ).fetchall():
            record = _row_to_dict(row, _RUNTIME_COLUMNS)
            record["record_type"] = "runtime"
            lines.append(_canonical_json(record))
        payload = "".join(line + "\n" for line in lines)
        target.write_text(payload, encoding="utf-8")
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def import_jsonl(self, path: str | Path) -> int:
        """Fold another ledger's records in, and return how many were new.

        Used by a resumed round reading its predecessor and by shard merging.
        Identifiers are derived from position rather than content, so a record
        that arrives twice is recognised as the same record and counted once.
        A record that arrives twice with different numbers is a contradiction
        and raises rather than overwriting.
        """
        target = Path(path)
        if not target.is_file():
            raise ValueError(f"there is no ledger export at {target}")
        added = 0
        for line in target.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            kind = record.pop("record_type", "call")
            if kind == "runtime":
                added += self._import_runtime(record)
            else:
                added += self._import_call(record)
        self._connection.commit()
        return added

    def _import_call(self, record: Mapping[str, Any]) -> int:
        call_id = str(record.get("call_id") or "")
        _require(bool(call_id), "an imported call has no identifier")
        existing = self._row(call_id)
        if existing is not None:
            _require_agreement(existing, record)
            if existing["state"] == STATE_RESERVED and str(
                record.get("state") or ""
            ) in (STATE_SETTLED, STATE_ABANDONED):
                # We only knew the request had gone out; the arriving export
                # knows how it ended. Taking the outcome resolves a doubt
                # rather than overwriting a figure, and it is the difference
                # between a receipt that stays partial forever and one that
                # closes. The reverse direction is not allowed: a settled row
                # is never demoted back to an open question.
                self._connection.execute(
                    "UPDATE cost_calls SET {assignments} WHERE call_id = ?".format(
                        assignments=", ".join(
                            f"{column} = ?"
                            for column in _CALL_COLUMNS
                            if column != "call_id"
                        )
                    ),
                    tuple(
                        _import_value(record, column)
                        for column in _CALL_COLUMNS
                        if column != "call_id"
                    )
                    + (call_id,),
                )
            return 0
        self._connection.execute(
            "INSERT INTO cost_calls ({columns}) VALUES ({slots})".format(
                columns=", ".join(_CALL_COLUMNS),
                slots=", ".join("?" for _ in _CALL_COLUMNS),
            ),
            tuple(_import_value(record, column) for column in _CALL_COLUMNS),
        )
        return 1

    def _import_runtime(self, record: Mapping[str, Any]) -> int:
        entry_id = str(record.get("entry_id") or "")
        _require(bool(entry_id), "an imported runtime entry has no identifier")
        existing = self._connection.execute(
            "SELECT * FROM cost_runtime WHERE entry_id = ?", (entry_id,)
        ).fetchone()
        if existing is not None:
            return 0
        self._connection.execute(
            "INSERT INTO cost_runtime ({columns}) VALUES ({slots})".format(
                columns=", ".join(_RUNTIME_COLUMNS),
                slots=", ".join("?" for _ in _RUNTIME_COLUMNS),
            ),
            tuple(_import_value(record, column) for column in _RUNTIME_COLUMNS),
        )
        return 1

    # -- internals -------------------------------------------------------

    def _row(self, call_id: str) -> sqlite3.Row | None:
        return self._connection.execute(
            "SELECT * FROM cost_calls WHERE call_id = ?", (str(call_id),)
        ).fetchone()

    @staticmethod
    def _require_same_settlement(
        row: sqlite3.Row,
        usage: CallUsage,
        model: str,
        cost: Decimal | None,
        reasons: Sequence[str],
    ) -> None:
        recorded = (
            row["input_tokens"],
            row["cached_input_tokens"],
            row["output_tokens"],
            row["reasoning_tokens"],
            str(row["resolved_model"] or ""),
            row["model_cost_usd"],
            row["missing_reasons"],
        )
        incoming = (
            usage.input_tokens,
            usage.cached_input_tokens,
            usage.output_tokens,
            usage.reasoning_tokens,
            model,
            None if cost is None else str(cost),
            json.dumps(sorted(reasons)),
        )
        if recorded != incoming:
            raise LedgerIntegrityError(
                f"call {row['call_id']} was already settled with different "
                "usage; the ledger will not overwrite a recorded cost"
            )


def verify_export(path: str | Path, expected_sha256: str) -> bool:
    """Check an exported ledger against the digest published beside it."""
    target = Path(path)
    if not target.is_file():
        return False
    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    return actual == str(expected_sha256).lower()


# ── Building receipts out of rows ────────────────────────────────────────


def build_receipt(
    calls: Iterable[Mapping[str, Any]],
    runtime_rows: Iterable[Mapping[str, Any]] = (),
    *,
    price_table_sha256: str | None = None,
) -> CostReceipt:
    """Add up rows into one receipt, keeping every doubt visible.

    Abandoned calls contribute nothing and cost nothing — they never went out.
    Reserved-but-unsettled calls contribute nothing but *do* cost the receipt
    its ``complete`` status, because whether they were billed is unknown.
    """
    per_component: dict[tuple[str, str], dict[str, Any]] = {}
    reasons: set[str] = set()
    model_cost = Decimal(0)
    model_calls = 0
    totals = empty_usage()

    for call in calls:
        state = str(call.get("state") or "")
        if state == STATE_ABANDONED:
            continue
        stage = str(call.get("stage") or "")
        retry_kind = str(call.get("retry_kind") or RETRY_NONE)
        key = (stage, retry_kind)
        bucket = per_component.setdefault(
            key,
            {
                "model_calls": 0,
                "known_cost_usd": Decimal(0),
                "usage": empty_usage(),
                "reasons": set(),
            },
        )
        model_calls += 1
        bucket["model_calls"] += 1

        if state == STATE_RESERVED:
            reasons.add(REASON_CALL_REACHABILITY_UNKNOWN)
            bucket["reasons"].add(REASON_CALL_REACHABILITY_UNKNOWN)
            continue

        row_reasons = _decode_reasons(call.get("missing_reasons"))
        reasons.update(row_reasons)
        bucket["reasons"].update(row_reasons)

        raw_cost = call.get("model_cost_usd")
        if raw_cost is not None:
            amount = Decimal(str(raw_cost))
            model_cost += amount
            bucket["known_cost_usd"] += amount

        for name in totals:
            value = call.get(name)
            if value is None:
                # Absent is not zero, but it is also not automatically a gap.
                # Whether this call could be priced was already settled by
                # :func:`price_call`, which knows that a model reporting no
                # cached or reasoning tokens simply had none. Re-deciding it
                # here would mark every ordinary call partial.
                continue
            totals[name] = (totals[name] or 0) + int(value)
            bucket["usage"][name] = (bucket["usage"][name] or 0) + int(value)

    runtime_cost = Decimal(0)
    for entry in runtime_rows:
        entry_reasons = _decode_reasons(entry.get("missing_reasons"))
        reasons.update(entry_reasons)
        raw = entry.get("runtime_cost_usd")
        if raw is not None:
            runtime_cost += Decimal(str(raw))

    status = STATUS_PARTIAL if reasons else STATUS_COMPLETE
    components = tuple(
        ReceiptComponent(
            stage=stage,
            retry_kind=retry_kind,
            status=STATUS_PARTIAL if data["reasons"] else STATUS_COMPLETE,
            model_calls=data["model_calls"],
            known_cost_usd=data["known_cost_usd"],
            usage=data["usage"],
            missing_reasons=tuple(sorted(data["reasons"])),
        )
        for (stage, retry_kind), data in sorted(per_component.items())
    )
    return CostReceipt(
        status=status,
        known_cost_usd=model_cost + runtime_cost,
        model_cost_usd=model_cost,
        runtime_cost_usd=runtime_cost,
        model_calls=model_calls,
        usage=totals,
        components=components,
        price_table_sha256=price_table_sha256,
        missing_reasons=tuple(sorted(reasons)),
    )


def summarise_receipts(receipts: Sequence[CostReceipt]) -> CostReceipt:
    """Roll per-task receipts into one experiment-level receipt.

    A summary is ``complete`` only when every task it covers is. One task whose
    usage went missing is enough to stop the experiment total being presented as
    a total — which is the point, since a headline figure that quietly omits a
    task is read as if it did not.

    Where *nothing* under the summary could be priced the answer is
    ``unavailable``, not ``partial``. The two are not the same claim: partial
    says part of this is known and the rest is not, and its ``known_cost_usd``
    is a real floor. A run with no record at all has no floor, and reporting one
    of ``$0`` invites exactly the reading — "so far it has cost nothing" — that
    the four statuses exist to prevent.
    """
    contributing = [
        receipt
        for receipt in receipts
        if receipt.status not in (STATUS_NOT_RUN,)
    ]
    if not contributing:
        return CostReceipt.not_run()

    reasons: set[str] = set()
    known = Decimal(0)
    model_cost = Decimal(0)
    runtime_cost = Decimal(0)
    model_calls = 0
    totals = empty_usage()
    sha = None
    for receipt in contributing:
        reasons.update(receipt.missing_reasons)
        known += receipt.known_cost_usd
        model_cost += receipt.model_cost_usd
        runtime_cost += receipt.runtime_cost_usd
        model_calls += receipt.model_calls
        sha = sha or receipt.price_table_sha256
        for name in totals:
            value = receipt.usage.get(name)
            if value is None:
                continue
            totals[name] = (totals[name] or 0) + int(value)
    return CostReceipt(
        status=_summary_status(contributing),
        known_cost_usd=known,
        model_cost_usd=model_cost,
        runtime_cost_usd=runtime_cost,
        model_calls=model_calls,
        usage=totals,
        price_table_sha256=sha,
        missing_reasons=tuple(sorted(reasons)),
    )


def _summary_status(contributing: Sequence[CostReceipt]) -> str:
    if all(receipt.status == STATUS_COMPLETE for receipt in contributing):
        return STATUS_COMPLETE
    if all(receipt.status == STATUS_UNAVAILABLE for receipt in contributing):
        return STATUS_UNAVAILABLE
    return STATUS_PARTIAL


def ledger_reference(path: str | Path, sha256: str) -> dict[str, str]:
    """The pointer a published result carries to its own audit trail."""
    return {"path": str(path), "sha256": str(sha256)}


# ── Small helpers ────────────────────────────────────────────────────────


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_sha256(value: str) -> bool:
    text = str(value)
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _decode_reasons(raw: Any) -> set[str]:
    if raw is None:
        return set()
    if isinstance(raw, (list, tuple)):
        return {str(item) for item in raw}
    try:
        parsed = json.loads(str(raw))
    except Exception:  # noqa: BLE001 - a corrupt cell is a partial receipt
        return {REASON_USAGE_PARTIAL}
    if isinstance(parsed, list):
        return {str(item) for item in parsed}
    return set()


def _row_to_dict(row: sqlite3.Row, columns: Sequence[str]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for column in columns:
        value = row[column]
        if column == "missing_reasons":
            record[column] = sorted(_decode_reasons(value))
        else:
            record[column] = value
    return record


def _canonical_json(record: Mapping[str, Any]) -> str:
    return json.dumps(
        dict(sorted(record.items())),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _import_value(record: Mapping[str, Any], column: str) -> Any:
    value = record.get(column)
    if column == "missing_reasons":
        return json.dumps(sorted(_decode_reasons(value)))
    return value


def _require_agreement(
    existing: sqlite3.Row, record: Mapping[str, Any]
) -> None:
    """An imported call that clashes with a recorded one is not merged away."""
    if existing["state"] == STATE_RESERVED:
        # The local row knows less than the arriving one. Fill it in rather
        # than treat the arrival as a contradiction.
        return
    for column in ("input_tokens", "output_tokens", "model_cost_usd"):
        incoming = record.get(column)
        recorded = existing[column]
        if incoming is None or recorded is None:
            continue
        if str(incoming) != str(recorded):
            raise LedgerIntegrityError(
                f"imported call {existing['call_id']} disagrees with the "
                f"recorded {column}; the ledger will not overwrite it"
            )
