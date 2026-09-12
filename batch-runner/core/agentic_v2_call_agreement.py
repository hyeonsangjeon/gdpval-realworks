"""Two counts of the same calls, and the one term that makes them differ.

A V2 run keeps two independent records of how many times it asked the model.

The **voice** appends a row of its own each time a reply comes back carrying
usable token counts -- that is ``model_calls.per_attempt[*].calls`` in the run
record. The **ledger** is the bill: the sqlite file beside the run, settled
through :func:`~core.agentic_v2_conversation_runner.model_turns_of` from the
conversation's turns, and published per task as
``run.results[*].problem_solving_cost``.

``scripts/run_agentic_v2_stage.py`` says the two are worth keeping side by side
because "they are computed from different things and disagreement between them
is worth being able to see". Nothing has ever looked. This module looks, and it
reads a run record that already exists -- no ledger connection, no model, no
cost.

**The invariant is not equality, and assuming it was would stop good runs.**
:meth:`~core.agentic_v2_model_voice.AzureFoundryVoice.next_turn` appends its row
only *after* it has usable counts; a reply that arrives without them returns
``GaveUp`` and leaves no row behind. The same reply is listed in
:attr:`~core.agentic_v2_conversation.ConversationOutcome.turns_not_counted` and
reaches the ledger anyway, as a row with an empty usage, because the provider
answered and will bill for it. So the ledger is legitimately ahead by exactly
the number of replies that said nothing about what they used::

    receipt.model_calls == voice rows + model_calls_not_counted

That third term is the whole content of this module. Without it, the first V2
run to meet an unreported usage would read as a corrupted ledger.

**What a disagreement would mean.** The two sides share no arithmetic: one
counts replies as they arrive in :mod:`core.agentic_v2_model_voice`, the other
counts rows settled into sqlite from the conversation's own event log. A gap
between them is a call that one half of the run saw and the other did not, and
the direction says which: a ledger ahead of the voice by more than the
uncounted term is spend with no evidence behind it, and a voice ahead of the
ledger is a call that was made and never reached the bill.

**This is a post-run read and is not a mid-run halt.** A receipt exists only
once a task has settled, so the earliest this can fire is after a task ends --
not before the next call goes out. Anything that promises otherwise is
promising something no object in this repository can do yet.

Offline. A dictionary in, a verdict out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

#: The receipt statuses under which a count is worth comparing at all. A task
#: that did not run has no calls on either side, and saying its two zeros agree
#: would pad the "checked" figure with tasks nobody asked about.
_RAN = ("complete", "partial", "unavailable")

#: Keys the receipt's usage block carries. Compared only where the receipt
#: reports a number: absent is not zero here either, and a receipt that never
#: said what it used cannot disagree with anything.
_USAGE_KEYS = ("input_tokens", "output_tokens")


@dataclass(frozen=True)
class Agreement:
    """One task's two counts, with the uncounted term kept visible.

    Per task rather than per attempt because that is the grain the receipt is
    written at: ``ledger.receipt_for(task_id, ...)`` sums a task's attempts into
    one row. The attempts that fed it are named in :attr:`attempts` so that a
    disagreement can be narrowed by hand.
    """

    task_id: str
    attempts: tuple[int, ...]

    #: Replies the voice counted, summed over the task's attempts.
    voice_counted: int

    #: Replies that arrived without usable counts, from the conversation's own
    #: event log. The term that makes the two sides differ legitimately.
    not_counted: int

    #: What the receipt says was billed.
    ledger_counted: int

    voice_input_tokens: int
    voice_output_tokens: int
    ledger_usage: Mapping[str, Optional[int]]
    receipt_status: str

    #: Set when one of the three pieces is missing from the record. A verdict is
    #: not produced in that case; the reason is carried instead.
    not_comparable_because: Optional[str] = None

    @property
    def the_voice_accounts_for(self) -> int:
        """What the ledger should hold if nothing was lost on either side."""
        return self.voice_counted + self.not_counted

    @property
    def counts_agree(self) -> Optional[bool]:
        if self.not_comparable_because is not None:
            return None
        return self.ledger_counted == self.the_voice_accounts_for

    @property
    def tokens_agree(self) -> Optional[bool]:
        """``None`` when the receipt reported no usage to compare against.

        An uncounted reply contributes nothing to the receipt's usage rather
        than a zero, so this stays comparable on a task that had one -- the
        tokens the voice did see are the tokens the ledger holds.
        """
        if self.not_comparable_because is not None:
            return None
        mine = {
            "input_tokens": self.voice_input_tokens,
            "output_tokens": self.voice_output_tokens,
        }
        theirs = {key: self.ledger_usage.get(key) for key in _USAGE_KEYS}
        if any(value is None for value in theirs.values()):
            return None
        return all(theirs[key] == mine[key] for key in _USAGE_KEYS)

    @property
    def agrees(self) -> Optional[bool]:
        """Both answers, with an unanswerable one never reading as a pass."""
        if self.counts_agree is None:
            return None
        if self.counts_agree is False:
            return False
        return False if self.tokens_agree is False else True

    def why(self) -> str:
        """One sentence, for a person reading a job log."""
        if self.not_comparable_because is not None:
            return f"{self.task_id}: not comparable -- {self.not_comparable_because}"
        if self.agrees:
            return (
                f"{self.task_id}: {self.ledger_counted} call(s) on both sides "
                f"({self.voice_counted} counted by the voice"
                + (f" + {self.not_counted} uncounted" if self.not_counted else "")
                + ")"
            )
        parts = []
        if self.counts_agree is False:
            parts.append(
                f"the ledger holds {self.ledger_counted} call(s) and the voice "
                f"accounts for {self.the_voice_accounts_for} "
                f"({self.voice_counted} counted, {self.not_counted} uncounted)"
            )
        if self.tokens_agree is False:
            parts.append(
                f"the ledger holds {self.ledger_usage.get('input_tokens')} in "
                f"and {self.ledger_usage.get('output_tokens')} out, the voice "
                f"{self.voice_input_tokens} in and {self.voice_output_tokens} out"
            )
        return f"{self.task_id}: " + "; ".join(parts)

    def as_row(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "attempts": list(self.attempts),
            "voice_counted": self.voice_counted,
            "not_counted": self.not_counted,
            "the_voice_accounts_for": self.the_voice_accounts_for,
            "ledger_counted": self.ledger_counted,
            "counts_agree": self.counts_agree,
            "tokens_agree": self.tokens_agree,
            "agrees": self.agrees,
            "receipt_status": self.receipt_status,
            "not_comparable_because": self.not_comparable_because,
            "why": self.why(),
        }


def _voice_calls_by_task(
    record: Mapping[str, Any]
) -> dict[str, list[tuple[int, Sequence[Mapping[str, Any]]]]]:
    per_task: dict[str, list[tuple[int, Sequence[Mapping[str, Any]]]]] = {}
    block = record.get("model_calls")
    entries = block.get("per_attempt") if isinstance(block, Mapping) else None
    for entry in entries or ():
        if not isinstance(entry, Mapping):
            continue
        task_id = str(entry.get("task_id") or "")
        calls = entry.get("calls")
        per_task.setdefault(task_id, []).append(
            (int(entry.get("attempt") or 0), calls if isinstance(calls, list) else [])
        )
    return per_task


def _uncounted_by_task(record: Mapping[str, Any]) -> dict[str, int]:
    """Summed over a task's attempts, keyed the way the record keys them.

    ``held.as_dict()`` names each conversation ``"<task_id>#<attempt>"``, and a
    task id may itself contain a ``#``, so the split is from the right.
    """
    held = record.get("conversations")
    block = held.get("conversations") if isinstance(held, Mapping) else None
    totals: dict[str, int] = {}
    for key, outcome in (block or {}).items():
        if not isinstance(outcome, Mapping):
            continue
        task_id = str(key).rsplit("#", 1)[0]
        totals[task_id] = totals.get(task_id, 0) + int(
            outcome.get("model_calls_not_counted") or 0
        )
    return totals


def _receipts_by_task(record: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    run = record.get("run")
    rows = run.get("results") if isinstance(run, Mapping) else None
    found: dict[str, Mapping[str, Any]] = {}
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        receipt = row.get("problem_solving_cost")
        if isinstance(receipt, Mapping):
            found[str(row.get("task_id") or "")] = receipt
    return found


def compare(record: Mapping[str, Any]) -> tuple[Agreement, ...]:
    """Every task in the record, with its two counts put side by side.

    A task missing from either side is reported as not comparable rather than
    dropped: a task with a receipt and no voice rows is exactly the shape worth
    seeing, and silently leaving it out would hide it.
    """
    voices = _voice_calls_by_task(record)
    uncounted = _uncounted_by_task(record)
    receipts = _receipts_by_task(record)

    out: list[Agreement] = []
    for task_id in sorted(set(voices) | set(receipts)):
        attempts = tuple(sorted(attempt for attempt, _ in voices.get(task_id, ())))
        rows = [row for _, calls in voices.get(task_id, ()) for row in calls]
        receipt = receipts.get(task_id)
        status = str((receipt or {}).get("status") or "")

        missing: Optional[str] = None
        if receipt is None:
            missing = "the run record carries no receipt for this task"
        elif status not in _RAN:
            missing = f"the receipt reads {status!r}, so no call was billed here"

        usage = (receipt or {}).get("usage")
        out.append(
            Agreement(
                task_id=task_id,
                attempts=attempts,
                voice_counted=len(rows),
                not_counted=uncounted.get(task_id, 0),
                ledger_counted=int((receipt or {}).get("model_calls") or 0),
                voice_input_tokens=sum(int(row.get("input_tokens") or 0) for row in rows),
                voice_output_tokens=sum(
                    int(row.get("output_tokens") or 0) for row in rows
                ),
                ledger_usage=dict(usage) if isinstance(usage, Mapping) else {},
                receipt_status=status,
                not_comparable_because=missing,
            )
        )
    return tuple(out)


def the_stop_rule(record: Mapping[str, Any]) -> dict[str, Any]:
    """The verdict the plan's stopping rule is written about.

    ``agree`` is ``True`` only when every task that could be compared did. Tasks
    that could not be compared are counted and named rather than folded into
    either column -- a run whose receipts are all missing has not agreed about
    anything, and reporting it as agreement would be the failure this exists to
    catch.
    """
    agreements = compare(record)
    disagreed = [one for one in agreements if one.agrees is False]
    unchecked = [one for one in agreements if one.agrees is None]
    checked = [one for one in agreements if one.agrees is not None]
    return {
        "what_this_is": (
            "the voice's own count of its calls against the bill, per task. "
            "The two are computed from different things, so a difference is a "
            "call one half of the run saw and the other did not"
        ),
        "tasks": len(agreements),
        "compared": len(checked),
        "not_comparable": len(unchecked),
        "disagreed": len(disagreed),
        "agree": bool(checked) and not disagreed,
        "rows": [one.as_row() for one in agreements],
        "what_disagreement_means": (
            "a ledger ahead of the voice by more than the uncounted replies is "
            "spend with no evidence behind it; a voice ahead of the ledger is a "
            "call that was made and never reached the bill. Either way the "
            "published cost is not the run's cost"
        ),
        "when_this_can_fire": (
            "after a task settles, because a receipt does not exist before "
            "then. It is not a check that can stop the next call going out"
        ),
    }


def describe(verdict: Mapping[str, Any]) -> str:
    """The same thing in sentences, for whoever is reading the job log."""
    lines = [
        f"call agreement: {verdict['compared']} task(s) compared, "
        f"{verdict['disagreed']} disagreed, "
        f"{verdict['not_comparable']} not comparable"
    ]
    for row in verdict["rows"]:
        if row["agrees"] is not True:
            lines.append(f"  {row['why']}")
    if verdict["agree"]:
        lines.append("  the bill and the voice describe the same calls")
    return "\n".join(lines)
