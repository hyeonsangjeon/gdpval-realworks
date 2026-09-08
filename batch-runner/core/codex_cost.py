"""Turn Codex's token counts into entries in the shared cost receipt.

The receipt contract in ``core/cost_receipts.py`` is not re-designed here and
no new price table is introduced. This module is only a translator: it takes
what the pinned Codex SDK actually reports and expresses it in the vocabulary
the ledger already has — ``reserve`` a call, ``settle`` it with a
:class:`~core.cost_receipts.CallUsage`, and attach the missing-information
reasons that make a receipt honest rather than confident.

What the runtime really reports, and what it does not
-----------------------------------------------------

Read out of ``openai-codex==0.147.0``:

* ``TurnResult.usage`` is a ``ThreadTokenUsage | None``. It is collected by
  ``openai_codex._run._collect_turn_result``, which keeps the **last**
  ``thread/tokenUsage/updated`` notification seen during the turn. There may be
  none, so ``None`` is a real outcome and not a bug.
* ``ThreadTokenUsage`` has two breakdowns: ``total`` and ``last``. ``total`` is
  cumulative **for the whole thread**, not for the turn. ``last`` is the most
  recent sample, which for a turn that made several model requests is only the
  final one.
* ``TokenUsageBreakdown`` carries ``input_tokens``, ``cached_input_tokens``,
  ``cache_write_input_tokens``, ``output_tokens``, ``reasoning_output_tokens``
  and ``total_tokens``.

Three consequences drive everything below.

**A turn is not a call.** Codex decides for itself how many model requests to
make while working on one prompt, and nothing in the SDK exposes them
individually. One receipt entry therefore stands for an unknown number of
calls, which is exactly what
``core.cost_receipts.REASON_CALL_REACHABILITY_UNKNOWN`` was defined to say. It
is attached to every Codex settlement, including the ones that price cleanly,
because the uncertainty is structural and does not go away when the arithmetic
works.

**Cumulative totals must be differenced, or the same tokens are billed
repeatedly.** Settling turn 2 with ``total`` would re-charge turn 1. So the
adapter records the thread's totals before a turn and charges the difference.
:func:`turn_usage_delta` is the only supported way to get a per-turn number
here, and it refuses a total that went backwards rather than silently
clamping — a decreasing cumulative counter means the reading is not what we
think it is, and guessing past that is how a ledger stops meaning anything.

**A token class the receipt cannot express is a partial receipt, not a
rounding.** ``cache_write_input_tokens`` has no field in ``CallUsage`` and no
rate in the price table. Where it is zero, nothing is lost. Where it is not,
the settlement carries ``usage_partial``: the receipt is saying "there was
billable activity here I have no way to price", which is true, instead of
quietly dropping it and reporting a total that looks complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    CallUsage,
)

#: Which side of the ledger a Codex turn lands on. Solving the task, never
#: grading it — the two buckets stay separate, and no Codex entry may be
#: written against ``grading_cost``.
CODEX_COST_BUCKET = BUCKET_PROBLEM_SOLVING

#: Attached to every Codex settlement. See the module docstring: one turn
#: covers an unknown number of model requests, and the SDK reports no
#: per-request breakdown.
CODEX_STRUCTURAL_REASONS: tuple[str, ...] = (REASON_CALL_REACHABILITY_UNKNOWN,)


class CodexUsageError(ValueError):
    """A usage reading cannot be trusted, so it is refused rather than used."""


@dataclass(frozen=True)
class CodexTokenTotals:
    """One ``TokenUsageBreakdown``, read into plain integers.

    Every field is ``None``-able for the same reason it is in ``CallUsage``:
    a count that was not reported is not a count of zero.
    """

    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cache_write_input_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_output_tokens: int | None = None

    @property
    def is_empty(self) -> bool:
        return all(
            value is None
            for value in (
                self.input_tokens,
                self.cached_input_tokens,
                self.cache_write_input_tokens,
                self.output_tokens,
                self.reasoning_output_tokens,
            )
        )

    @classmethod
    def zero(cls) -> "CodexTokenTotals":
        """The starting point for a fresh thread: counted, and counted as none.

        This is the one place a zero is correct. A thread that has run no turn
        has demonstrably spent nothing, which is a measurement, not a default.
        """
        return cls(
            input_tokens=0,
            cached_input_tokens=0,
            cache_write_input_tokens=0,
            output_tokens=0,
            reasoning_output_tokens=0,
        )


def _read_int(source: Any, name: str) -> int | None:
    value = getattr(source, name, None)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CodexUsageError(
            f"Codex reported {name}={value!r}, which is not a token count"
        )
    if value < 0:
        raise CodexUsageError(
            f"Codex reported {name}={value}, and a negative token count means "
            "the reading is not what it appears to be"
        )
    return value


def read_breakdown(breakdown: Any) -> CodexTokenTotals:
    """Read one ``TokenUsageBreakdown`` without importing the SDK.

    Attribute access rather than an import keeps this module usable — and
    testable — on a machine where the Codex binary cannot run, which is the
    situation the mock end-to-end check is built around.
    """
    if breakdown is None:
        return CodexTokenTotals()
    return CodexTokenTotals(
        input_tokens=_read_int(breakdown, "input_tokens"),
        cached_input_tokens=_read_int(breakdown, "cached_input_tokens"),
        cache_write_input_tokens=_read_int(breakdown, "cache_write_input_tokens"),
        output_tokens=_read_int(breakdown, "output_tokens"),
        reasoning_output_tokens=_read_int(breakdown, "reasoning_output_tokens"),
    )


def read_thread_totals(usage: Any) -> CodexTokenTotals:
    """Read the cumulative ``total`` out of a ``ThreadTokenUsage``.

    ``None`` — no usage notification arrived during the turn — reads as an
    empty breakdown, which settles as ``usage_absent`` further down rather than
    as a free turn.
    """
    if usage is None:
        return CodexTokenTotals()
    return read_breakdown(getattr(usage, "total", None))


def _difference(
    field: str, before: int | None, after: int | None
) -> int | None:
    if after is None:
        return None
    if before is None:
        # The thread total was unreadable before the turn, so the share of
        # `after` belonging to this turn is unknown. Charging all of it would
        # bill earlier turns again.
        return None
    if after < before:
        raise CodexUsageError(
            f"the thread's cumulative {field} fell from {before} to {after}; a "
            "cumulative counter that decreases cannot be differenced into a "
            "turn's share"
        )
    return after - before


def turn_usage_delta(
    before: CodexTokenTotals, after: CodexTokenTotals
) -> CodexTokenTotals:
    """What one turn added to the thread's cumulative totals."""
    return CodexTokenTotals(
        input_tokens=_difference(
            "input_tokens", before.input_tokens, after.input_tokens
        ),
        cached_input_tokens=_difference(
            "cached_input_tokens",
            before.cached_input_tokens,
            after.cached_input_tokens,
        ),
        cache_write_input_tokens=_difference(
            "cache_write_input_tokens",
            before.cache_write_input_tokens,
            after.cache_write_input_tokens,
        ),
        output_tokens=_difference(
            "output_tokens", before.output_tokens, after.output_tokens
        ),
        reasoning_output_tokens=_difference(
            "reasoning_output_tokens",
            before.reasoning_output_tokens,
            after.reasoning_output_tokens,
        ),
    )


def to_call_usage(totals: CodexTokenTotals) -> CallUsage:
    """Express a Codex breakdown as the ledger's :class:`CallUsage`.

    ``cache_write_input_tokens`` is deliberately dropped here and reported
    through :func:`missing_reasons_for` instead. Folding it into
    ``input_tokens`` would change the priced amount on a guess about how the
    provider bills cache writes; leaving it out silently would report a total
    that looks complete. Saying "partial" is the only one of the three that is
    true.

    The audio fields stay ``None``. Codex's turn accounting reports no audio
    split, and ``None`` there means "not reported", which is the fact.
    """
    return CallUsage(
        input_tokens=totals.input_tokens,
        cached_input_tokens=totals.cached_input_tokens,
        output_tokens=totals.output_tokens,
        reasoning_tokens=totals.reasoning_output_tokens,
        audio_input_tokens=None,
        audio_output_tokens=None,
    )


def missing_reasons_for(totals: CodexTokenTotals) -> tuple[str, ...]:
    """The reasons a Codex settlement must carry beyond what pricing finds.

    ``price_call`` already contributes ``usage_absent`` and ``price_missing``
    from the numbers it was handed. These are the ones only this adapter can
    know: that a turn is not a call, and that a reported token class has no
    home in the receipt.
    """
    reasons: list[str] = list(CODEX_STRUCTURAL_REASONS)
    if totals.is_empty:
        reasons.append(REASON_USAGE_ABSENT)
    if totals.cache_write_input_tokens:
        reasons.append(REASON_USAGE_PARTIAL)
    return tuple(dict.fromkeys(reasons))


def settle_codex_turn(
    ledger: Any,
    call_id: str,
    *,
    totals: CodexTokenTotals,
    resolved_model: str | None = None,
) -> Any:
    """Settle one reserved call with a turn's share of the thread's tokens.

    ``totals`` must already be a per-turn delta from :func:`turn_usage_delta`,
    not a cumulative thread total. Passing the cumulative figure would bill the
    thread's earlier turns again on every settlement, which is the specific
    double-count this module exists to prevent.
    """
    return ledger.settle(
        call_id,
        usage=to_call_usage(totals),
        resolved_model=resolved_model,
        extra_reasons=missing_reasons_for(totals),
    )
