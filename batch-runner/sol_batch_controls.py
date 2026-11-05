"""Solve-side controls for the GPT-5.6 Sol fixed-five batch on the generic Codex path.

Step 2 calls :func:`install` once, right after its TaskExecutor exists, for
every codex_foundry run that is not the paused gpt56 pilot. It is inert unless
the run asks Codex for gpt-5.6-sol or is :data:`EXPERIMENT_ID`: every other run
gets ``None`` back before anything is read, written or printed.

For :data:`EXPERIMENT_ID` (owner approval 2026-11-05) it swaps the executor's
runner for :class:`SolBatchCodexRunner`, which adds two controls:

* The held #796 1M catalog. Codex 0.147.0's bundled catalog gives gpt-5.6-sol
  272,000 tokens and clamps the requested 1,000,000 to 258,400 usable; the held
  catalog keeps the request at 1,000,000. Its sha256 is checked on every
  attempt, before Codex starts.
* A between-attempt USD gate. Before each attempt it books every ledger row of
  the run at the published long-context list meter, adds what earlier relay
  legs booked, and refuses to START the attempt once that spend plus one
  attempt reserve would pass the solve budget. A running attempt is never
  stopped, so the last admitted attempt can overshoot; the owner accepted that.

Any other gpt-5.6-sol run on this path is refused before its first attempt, so a
copied or mistyped experiment file cannot run without the gate.

The module lives outside ``core/`` because the #794 grader seal hashes
``core/**/*.py``; a file there would move that seal. It imports only the
standard library and ``core``, and does no I/O at import time.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from core import runner_environment
from core.codex_cost import read_breakdown
from core.codex_runner import CodexAgentRunner, TurnObservation
from core.codex_runtime_config import (
    CodexProviderConfigurationError,
    CodexProviderSettings,
    _toml_literal,
    describe_version_pin,
    requested_model_config_overrides,
)
from core.cost_receipts import (
    MONEY_PLACES,
    PRICE_TABLE_PATH,
    STATE_ABANDONED,
    STATE_REFUSED,
    STATE_SETTLED,
    TOKENS_PER_MILLION,
)
from core.reference_integrity import open_verified_reference

#: The one experiment these controls run. Any other id asking for Sol is refused.
EXPERIMENT_ID = "exp036_sol_fixed5"
SOL_MODEL = "gpt-5.6-sol"
#: Requested explicitly: the 0.147.0 catalog default for gpt-5.6-sol is "low".
REASONING_EFFORT = "max"
CONTEXT_WINDOW = 1_000_000
#: Sol's window in Codex 0.147.0's bundled catalog (258,400 usable at 95%).
CODEX_BUNDLED_SOL_CONTEXT_WINDOW = 272_000
#: Sol's context_window and max_context_window in the held catalog, 100% usable.
CATALOG_SOL_MAX_CONTEXT_WINDOW = 1_050_000
FIXED_TASK_IDS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
)
#: The turn limit the attempt reserve was sized against; nothing else bounds a turn.
ATTEMPT_TIMEOUT_SECONDS = 1800
#: Infra retries per task; with resume_max_rounds 0 a task gets four attempts at most.
MAX_RETRIES = 3
ROOT = Path(__file__).resolve().parents[1]
CATALOG_RELATIVE = "batch-runner/codex_catalogs/codex-0.147.0-models-gpt56-sol-1m.json"
CATALOG_PATH = ROOT / CATALOG_RELATIVE
#: The #796 registration pins the same bytes.
CATALOG_SHA256 = "41e884c807616100cc92c8b734337725d37ecd096586c598f3c389032e8db49e"
#: model_price_table.json as pinned by #795.
PRICE_TABLE_SHA256 = "b01b384c532b1457804e3a77713d2b079b06b363a5ff3b8b939fe65a4cb30b4e"
#: The table's long-context Standard Global meter, the higher of its two Global tiers.
SOL_METER = "long_context_standard_global"
CEILING_USD = Decimal("200")
GRADING_RESERVE_USD = Decimal("54")
ATTEMPT_RESERVE_USD = Decimal("51")
SOLVE_BUDGET_USD = CEILING_USD - GRADING_RESERVE_USD
#: One refused first request: 64,000 input tokens x (10.00 + 12.50) plus
#: 128,000 output tokens x 45.00 per 1M (1.44 + 5.76).
REFUSED_REQUEST_USD = Decimal("7.20")
#: Step 6 narrative: two Sol Max calls, 12,288 output tokens at most. Booked by
#: sol_batch_grading, not by the solve gate.
NARRATIVE_ALLOWANCE_USD = Decimal("2.00")
#: Raise by PR before re-dispatching after an exp036 lineage died without a
#: relay checkpoint. Read its record in that run's batch-results artifact or
#: job log.
PRIOR_LINEAGE_SPEND_USD = Decimal("0")
USD_CEILING_REACHED = "usd_ceiling_reached"
WINDOW_MISMATCH = "sol_batch_context_window_mismatch"
GATE_UNVERIFIED = "sol_batch_gate_unverified"
RECORD_SCHEMA = "sol-batch-controls-v1"
EVIDENCE_BOUNDARY = (
    "codex_app_server_client_window_not_foundry_served_capability; "
    "clamped 258400 baseline = run 39407062120 and #796 probe"
)

_PRICE_TABLE_RELATIVE = "batch-runner/experiments/execution_envelope/model_price_table.json"
_STEP2_RELATIVE = "batch-runner/step2_run_inference.py"
_THIS_RELATIVE = "batch-runner/sol_batch_controls.py"
#: Runner options the generic batch path never sets. Each changes which binary
#: runs or how a turn is bounded or observed; the reserve and the window record
#: assume none of them.
_RUNNER_OPTIONS_REFUSED = ("pilot_wire_receipts", "task_deadline_store", "observation_control", "codex_bin")
#: Row bases whose amount is measured rather than reserved.
_COMPLETE_BASES = frozenset({"settled", "abandoned"})


class SolBatchControlsRefused(RuntimeError):
    """The run is refused before any attempt; step 2 exits 1.

    The message is one closed code and never carries an endpoint or a
    credential, because step 2 prints it to a published log.
    """


class SolLongContextRefused(CodexProviderConfigurationError):
    """The 1M request or the held catalog drifted when an attempt began.

    Raised from ``config_overrides()``, which ``open_runtime`` calls before
    Codex starts; ``_run_one_turn`` maps it to ``runtime_unavailable``, so no
    model request is sent. The auth probe that runs just before it may already
    have minted a token.
    """


# -- held inputs ------------------------------------------------------------


def _read_held(path: Path, sha256: str) -> bytes:
    """Read one held input under the rule the pilot applies to the same catalog.

    gpt54_v2_grading_input._read_bytes accepts one regular file with one link,
    no symlink anywhere in its path, and bytes that hash to the pin. Mirroring
    it with core alone keeps both paths accepting exactly the same file: a
    symlink could be re-pointed after the check, and a second link is another
    name through which the bytes can change.
    """
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ValueError("held input must be a single-link regular file")
        with open_verified_reference(path, expected_sha256=sha256) as (stream, _verified):
            if os.fstat(stream.fileno()).st_nlink != 1:
                raise ValueError("held input gained another link")
            data = stream.read()
    except OSError as exc:
        raise ValueError(f"held input unreadable ({type(exc).__name__})") from None
    if hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("held input changed while it was read")
    return data


def held_catalog_override() -> str:
    """The ``-c`` override that hands Codex the held 1M catalog.

    Byte-identical to what gpt56_pilot_wire_receipt._long_context_catalog
    returns for the same request. That helper is not imported: it pulls in the
    pilot's module graph and raises the pilot's own refusal.
    """
    try:
        _read_held(CATALOG_PATH, CATALOG_SHA256)
    except Exception:
        raise SolLongContextRefused("sol_batch_catalog_unverified") from None
    return "model_catalog_json=" + _toml_literal(str(CATALOG_PATH))


def sol_overrides(base: Sequence[str]) -> tuple[str, ...]:
    """Append the held catalog to an override tuple that asks for Max and 1M.

    The one builder production and the loopback end-to-end check share. The
    requested pair must be the tuple's last two items and appear once each, so
    nothing after it can restate the effort or the window, and a catalog that
    is already present cannot be shadowed by this one.
    """
    items = tuple(base)
    requested = requested_model_config_overrides(
        reasoning_effort=REASONING_EFFORT, model_context_window=CONTEXT_WINDOW,
    )
    if (
        any(not isinstance(item, str) for item in items)
        or items[-2:] != requested
        or sum(item.startswith("model_context_window=") for item in items) != 1
        or sum(item.startswith("model_reasoning_effort=") for item in items) != 1
        or any(item.startswith("model_catalog_json=") for item in items)
    ):
        raise SolLongContextRefused("sol_batch_override_drift")
    return (*items, held_catalog_override())


@dataclass(frozen=True)
class SolLongContextProviderSettings(CodexProviderSettings):
    """The run's own provider settings plus the held catalog; no new fields.

    A subclass rather than a copy, so the provider table, query parameters and
    requested pair come from the same code every other Codex run uses, and the
    result still passes core/executor.py's isinstance check.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        if (
            self.model != SOL_MODEL
            or self.reasoning_effort != REASONING_EFFORT
            or self.model_context_window != CONTEXT_WINDOW
            or self.request_max_retries != 0
            or self.stream_max_retries != 0
        ):
            raise SolLongContextRefused("sol_batch_request_drift")

    def config_overrides(self) -> tuple[str, ...]:
        return sol_overrides(super().config_overrides())

    @classmethod
    def from_settings(cls, settings: CodexProviderSettings) -> SolLongContextProviderSettings:
        if type(settings) is not CodexProviderSettings:
            raise SolBatchControlsRefused("sol_batch_provider_type")
        return cls(**{
            field.name: getattr(settings, field.name)
            for field in dataclasses.fields(CodexProviderSettings)
        })


# -- pricing ----------------------------------------------------------------


@dataclass(frozen=True)
class SolRates:
    """USD per 1,000,000 tokens on :data:`SOL_METER`, as the pinned table states them."""

    input: Decimal
    cached_input: Decimal
    cache_write: Decimal
    output: Decimal
    retrieved: str


def load_sol_list_rates(path: Path | str = PRICE_TABLE_PATH) -> SolRates:
    """Read the published Sol list meter from the #795-pinned price table.

    A list price, not a verified tariff. Any read or parse failure refuses,
    because a gate without rates cannot book anything.
    """
    try:
        raw = _read_held(Path(path), PRICE_TABLE_SHA256)
        meters = json.loads(raw)["azure_published_meters"]
        meter = meters[SOL_MODEL][SOL_METER]
        return SolRates(
            *(Decimal(meter[key]) for key in ("input", "cached_input", "cache_write", "output")),
            str(meters.get("retrieved", "")),
        )
    except Exception:
        raise SolBatchControlsRefused("sol_batch_price_table_unverified") from None


def _count(value: Any) -> int | None:
    """A reported token count, or ``None`` when it is not a non-negative int."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def list_price_usd(
    *,
    input_tokens: Any,
    cached_input_tokens: Any,
    output_tokens: Any,
    reasoning_tokens: Any = None,
    reported_cache_write_tokens: Any = None,
    rates: SolRates,
) -> Decimal | None:
    """One turn at list price, or ``None`` when its counts cannot be priced.

    Cache writes are booked as max(reported, input - cached): an upper bound
    on what one turn can write, since Codex's ledger keeps no cache-write
    count. Reasoning is billed inside output and is never added on top.
    """
    inputs = _count(input_tokens)
    outputs = _count(output_tokens)
    cached = 0 if cached_input_tokens is None else _count(cached_input_tokens)
    if inputs is None or outputs is None or cached is None or cached > inputs:
        return None
    if reasoning_tokens is not None:
        reasoning = _count(reasoning_tokens)
        if reasoning is None or reasoning > outputs:
            return None
    uncached = inputs - cached
    reported = _count(reported_cache_write_tokens)
    writes = max(uncached, reported if reported is not None else 0)
    amount = (
        uncached * rates.input
        + cached * rates.cached_input
        + outputs * rates.output
        + writes * rates.cache_write
    ) / TOKENS_PER_MILLION
    return amount.quantize(MONEY_PLACES, rounding=ROUND_CEILING)


def fmt(amount: Decimal | int | float | str) -> str:
    """USD at the ledger's eight places, rounded up, as JSON-safe text."""
    # A float would carry its binary error into a ceiling rounding.
    value = Decimal(str(amount)) if isinstance(amount, float) else Decimal(amount)
    return format(value.quantize(MONEY_PLACES, rounding=ROUND_CEILING), "f")


def book_row(
    row: Mapping[str, Any], *, rates: SolRates, evidence: Mapping[str, Any] | None = None,
) -> tuple[Decimal, str]:
    """What one Codex ledger row costs the gate, and on what basis.

    ``evidence`` is what the attempt itself reported: its error category,
    items seen and the thread's cache-write count. Usage that was never
    reported books the whole attempt reserve, except a rate refusal before any
    item completed, which books one refused first request. Booking a 429 at
    the full reserve would let two zero-cost refusals close the gate.
    """
    facts = evidence or {}
    state = row.get("state")
    if state == STATE_ABANDONED:
        # The turn never started (codex_runner.py:1914).
        return Decimal(0), "abandoned"
    if state == STATE_SETTLED:
        amount = list_price_usd(
            input_tokens=row.get("input_tokens"),
            cached_input_tokens=row.get("cached_input_tokens"),
            output_tokens=row.get("output_tokens"),
            reasoning_tokens=row.get("reasoning_tokens"),
            reported_cache_write_tokens=facts.get("cache_write_input_tokens"),
            rates=rates,
        )
        if amount is None:
            # A turn can settle with no counts (usage_absent).
            return ATTEMPT_RESERVE_USD, "settled_without_usage"
        return amount, "settled"
    if state == STATE_REFUSED:
        return REFUSED_REQUEST_USD, "refused_request"
    # Reserved: the stream reported no usage (codex_runner.py:1978).
    items_seen = facts.get("items_seen")
    if (facts.get("error_category") == "rate_limited"
            and type(items_seen) is int and items_seen == 0):
        return REFUSED_REQUEST_USD, "rate_limited_first_request"
    return ATTEMPT_RESERVE_USD, "usage_unreported"


# -- spend carried across relay legs and to grading -------------------------


def task_budget_metrics(amount: Decimal, complete: bool) -> dict[str, Any]:
    """The task's booked USD in the shape step 2 publishes as budget_metrics.

    Only USD is carried: step 2's bounded copy drops token counts above
    1,000,000, and this field is what crosses relay checkpoints and reaches
    self_report.json.
    """
    return {"conservative_cost_usd": fmt(amount), "usage_complete": bool(complete)}


def _usd(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
    try:
        amount = Decimal(str(value))
    except (ArithmeticError, ValueError):
        raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted") from None
    if not amount.is_finite() or not Decimal(0) <= amount < Decimal(1_000_000):
        raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
    return amount


def booked_from_rows(rows: Iterable[Any]) -> tuple[Decimal, list[str]]:
    """Sum the USD earlier legs booked onto their task rows.

    A row that reached the Codex runner without a booking refuses: counting it
    as zero would under-seed the gate. A row that never reached the runner
    (for example reference_input_integrity_failed) spent nothing. Pending rows
    are watchdog placeholders for tasks that have not run.
    """
    total = Decimal(0)
    tasks: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("status") == "pending":
            continue
        observability = row.get("observability") or {}
        if not isinstance(observability, dict):
            raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
        metrics = observability.get("budget_metrics")
        if isinstance(metrics, dict) and "conservative_cost_usd" in metrics:
            total += _usd(metrics["conservative_cost_usd"])
            tasks.append(str(row.get("task_id")))
        elif "runner_evidence" in observability:
            raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
    return total, tasks


def solve_spend_usd(rows: Iterable[Any]) -> Decimal:
    """The lineage's solve spend from its published task rows; the grade side seeds from this."""
    return PRIOR_LINEAGE_SPEND_USD + booked_from_rows(rows)[0]


# -- the gate ---------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _say(line: str, *, inline: bool = False) -> None:
    """Print one ``[sol-batch]`` line; a log that cannot be written stops nothing.

    ``inline`` lines land mid-way through step 2's progress line for a task,
    formatted the way its own retry notices are (run_with_infra_retries).
    """
    try:
        if inline:
            print(f"\n      {line}", end=" ", flush=True)
        else:
            print(f"   {line}", flush=True)
    except Exception:  # noqa: BLE001
        pass


def _sum_counts(values: Iterable[Any]) -> int | None:
    counts = [value for value in (_count(item) for item in values) if value is not None]
    return sum(counts) if counts else None


def _app_server_facts(usage: Any) -> dict[str, Any]:
    """The window Codex's app-server applied and the last request's size.

    The window is the client's setting, not proof of what Foundry serves; it
    is what shows whether the held catalog lifted the 258,400 clamp.
    """
    window = getattr(usage, "model_context_window", None) if usage is not None else None
    last = getattr(getattr(usage, "last", None), "input_tokens", None) if usage is not None else None
    window = _count(window)
    return {
        "usage_observed": usage is not None,
        "model_context_window": window if window else None,
        "last_request_input_tokens": _count(last),
    }


class SolBatchSession:
    """The gate's state for one step-2 process, which is one relay leg.

    Spend is recomputed from the per-turn ledger at every admission rather
    than kept as a running total, so a booking this process failed to record
    is still counted the next time.
    """

    def __init__(
        self, *, ledger: Any, rates: SolRates, record_path: Path | str,
        seed_usd: Decimal, prior_legs_usd: Decimal, window_mismatch: bool,
        header: Mapping[str, Any],
    ) -> None:
        self.ledger = ledger
        self.rates = rates
        self.record_path = Path(record_path)
        self.seed_usd = Decimal(seed_usd)
        self.prior_legs_usd = Decimal(prior_legs_usd)
        self.window_mismatch = bool(window_mismatch)
        self.header = header
        self.evidence: dict[str, dict] = {}
        self.attempts: list[dict] = []
        self.summary: dict | None = None

    @staticmethod
    def _key(task_id: str | None) -> str:
        # The name codex_runner._reserve_call files a turn under.
        return task_id or "unknown-task"

    def _rows(self, task_id: str | None = None) -> list[dict]:
        tasks = [self._key(task_id)] if task_id is not None else self.ledger.task_ids()
        run_id = self.ledger.run_id
        return [
            row for task in tasks for row in self.ledger.calls_for(task)
            if row.get("run_id") == run_id
        ]

    def _booked(self, rows: Iterable[Mapping[str, Any]]) -> tuple[Decimal, bool]:
        total = Decimal(0)
        complete = True
        for row in rows:
            amount, basis = book_row(row, rates=self.rates, evidence=self.evidence.get(row["call_id"]))
            total += amount
            complete = complete and basis in _COMPLETE_BASES
        return total, complete

    def _task_attempt(self, key: str) -> int:
        return 1 + sum(1 for row in self.attempts if row.get("task_id") == key)

    def spend_usd(self) -> Decimal:
        """Earlier legs and lineages plus every row this leg's ledger holds for the run."""
        return self.seed_usd + self._booked(self._rows())[0]

    def admit(self, task_id: str | None) -> tuple[str | None, dict[str, str]]:
        """Whether the next attempt may start: ``(None, decision)`` or ``(code, decision)``."""
        try:
            spend = self.spend_usd()
        except Exception:  # noqa: BLE001 - an unreadable ledger refuses rather than guesses
            return GATE_UNVERIFIED, {}
        decision = {
            "spend_before_usd": fmt(spend),
            "reserve_usd": fmt(ATTEMPT_RESERVE_USD),
            "solve_budget_usd": fmt(SOLVE_BUDGET_USD),
        }
        if self.window_mismatch:
            return WINDOW_MISMATCH, decision
        if spend + ATTEMPT_RESERVE_USD > SOLVE_BUDGET_USD:
            return USD_CEILING_REACHED, decision
        return None, decision

    def call_ids(self, task_id: str | None) -> frozenset[str] | None:
        """The task's rows before an attempt, so the attempt's own rows can be told apart."""
        try:
            return frozenset(row["call_id"] for row in self._rows(self._key(task_id)))
        except Exception:  # noqa: BLE001
            return None

    def book_attempt(
        self, *, task_id: str | None, before: frozenset[str] | None,
        decision: Mapping[str, str] | None, result: Any, usage: Any,
    ) -> None:
        """Record one admitted attempt: its rows, their booking and the app-server window.

        Never raises. It runs in a ``finally`` after a paid attempt, and an
        exception here would replace that attempt's result.
        """
        key = self._key(task_id)
        row: dict[str, Any] = {"task_id": key, "admitted": True}
        try:
            row.update({"ordinal": len(self.attempts) + 1, "task_attempt": self._task_attempt(key),
                        "at_utc": _now()})
            row.update(dict(decision or {}))
            if before is None:
                raise ValueError("the ledger was unreadable before the attempt")
            outcome = result if isinstance(result, dict) else {}
            diagnostics = outcome.get("codex_diagnostics")
            diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
            app_server = _app_server_facts(usage)
            try:
                totals = read_breakdown(getattr(usage, "total", None)) if usage is not None else None
            except Exception:  # noqa: BLE001 - an unreadable count falls back to the bound
                totals = None
            reported = totals.cache_write_input_tokens if totals is not None else None
            new = [entry for entry in self._rows(key) if entry["call_id"] not in before]
            booked = []
            for entry in new:
                # The thread total belongs to this attempt's one turn; with more
                # rows than turns it cannot be attributed, and the bound applies.
                facts = {
                    "error_category": outcome.get("error_category"),
                    "items_seen": diagnostics.get("items_seen"),
                    "cache_write_input_tokens": reported if len(new) == 1 else None,
                }
                self.evidence[entry["call_id"]] = facts
                booked.append(book_row(entry, rates=self.rates, evidence=facts))
            window = app_server["model_context_window"]
            if window is not None and window != CONTEXT_WINDOW:
                self.window_mismatch = True
            category = outcome.get("error_category")
            row.update(
                call_ids=[entry["call_id"] for entry in new],
                booked_usd=fmt(sum((amount for amount, _ in booked), Decimal(0))),
                basis="+".join(basis for _, basis in booked) or "no_row",
                input_tokens=_sum_counts(entry.get("input_tokens") for entry in new),
                cached_input_tokens=_sum_counts(entry.get("cached_input_tokens") for entry in new),
                output_tokens=_sum_counts(entry.get("output_tokens") for entry in new),
                reasoning_tokens=_sum_counts(entry.get("reasoning_tokens") for entry in new),
                reported_cache_write_tokens=_count(reported),
                app_server=app_server,
                window_matches_request=None if window is None else window == CONTEXT_WINDOW,
                success=outcome.get("success") is True,
                error_category=category[:80] if isinstance(category, str) and category else None,
                spend_after_usd=fmt(self.spend_usd()),
            )
        except Exception as exc:  # noqa: BLE001
            row["booking_error"] = type(exc).__name__
        self.attempts.append(row)
        label = f"[sol-batch] {str(key)[:8]} attempt {row.get('task_attempt')}"
        if "booking_error" in row:
            _say(f"{label}: booking failed ({row['booking_error']}); the next admission "
                 "reads the ledger again", inline=True)
        else:
            facts = row["app_server"]
            window = facts["model_context_window"]
            last = facts["last_request_input_tokens"]
            _say(f"{label}: booked {row['booked_usd']} ({row['basis']}); app-server window "
                 f"{window if window is not None else 'not reported'}; last request input tokens "
                 f"{last if last is not None else 'not reported'}; solve spend {row['spend_after_usd']}",
                 inline=True)
        self._write()

    def record_refusal(self, task_id: str | None, code: str, decision: Mapping[str, str] | None) -> None:
        """Record an attempt the gate did not start. Never raises."""
        try:
            key = self._key(task_id)
            row = {"task_id": key, "ordinal": len(self.attempts) + 1,
                   "task_attempt": self._task_attempt(key), "at_utc": _now(),
                   "admitted": False, "refusal": code, **dict(decision or {})}
            self.attempts.append(row)
            _say(f"[sol-batch] {str(key)[:8]} attempt {row['task_attempt']}: {code}; "
                 "nothing was started", inline=True)
            self._write()
        except Exception:  # noqa: BLE001
            pass

    def task_budget(self, task_id: str | None) -> dict[str, Any]:
        """The task's booked USD in this leg, as the budget_metrics step 2 publishes.

        When the ledger cannot be read, every admitted attempt of the task is
        booked at the full reserve, never at zero.
        """
        key = self._key(task_id)
        try:
            return task_budget_metrics(*self._booked(self._rows(key)))
        except Exception:  # noqa: BLE001
            admitted = sum(1 for row in self.attempts
                           if row.get("task_id") == key and row.get("admitted") is True)
            return task_budget_metrics(ATTEMPT_RESERVE_USD * max(1, admitted), False)

    def finish(self) -> None:
        """Close the leg's record with its spend summary. Never raises; a second call does nothing."""
        if self.summary is not None:
            return
        try:
            money: dict[str, Any]
            try:
                this_leg = self._booked(self._rows())[0]
                solve = self.seed_usd + this_leg
                money = {"this_leg_spend_usd": fmt(this_leg), "solve_spend_usd": fmt(solve),
                         "remaining_under_ceiling_usd": fmt(CEILING_USD - solve)}
            except Exception as exc:  # noqa: BLE001
                money = {"this_leg_spend_usd": None, "solve_spend_usd": None,
                         "remaining_under_ceiling_usd": None, "summary_error": type(exc).__name__}
            refused = [row for row in self.attempts if row.get("admitted") is False]
            self.summary = {
                "closed_at_utc": _now(),
                "prior_lineage_spend_usd": fmt(self.seed_usd - self.prior_legs_usd),
                "prior_legs_spend_usd": fmt(self.prior_legs_usd),
                **money,
                "attempts_admitted": sum(1 for row in self.attempts if row.get("admitted") is True),
                "attempts_refused": len(refused),
                "first_refusal": refused[0].get("refusal") if refused else None,
                "window_mismatch": self.window_mismatch,
            }
            # Inline, because the leg can close mid-way through a progress line
            # (the wall-clock watchdog, or an error out of a task).
            _say(f"[sol-batch] leg closed: solve spend {money['solve_spend_usd']} "
                 f"(prior legs {self.summary['prior_legs_spend_usd']}, this leg "
                 f"{money['this_leg_spend_usd']}); {money['remaining_under_ceiling_usd']} left under "
                 f"the {CEILING_USD} ceiling; {self.summary['attempts_admitted']} attempts "
                 f"admitted, {len(refused)} refused; window mismatch: "
                 f"{'yes' if self.window_mismatch else 'no'}", inline=True)
            self._write()
        except Exception:  # noqa: BLE001
            pass

    def _write(self, strict: bool = False) -> None:
        """Replace the record file whole, so a reader never sees half of it.

        ``strict`` is install time: no attempt has started, and a record that
        cannot be written refuses the run. Afterwards a write failure only
        warns, because the job log carries the same lines.
        """
        temporary = self.record_path.with_name(self.record_path.name + ".tmp")
        try:
            document = {"schema": RECORD_SCHEMA, "header": self.header,
                        "attempts": self.attempts, "summary": self.summary}
            payload = json.dumps(document, sort_keys=True, indent=1, allow_nan=False) + "\n"
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, self.record_path)
        except Exception as exc:  # noqa: BLE001
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if strict:
                if isinstance(exc, OSError):
                    raise SolBatchControlsRefused("sol_batch_record_unwritable") from None
                raise
            _say(f"[sol-batch] record not written ({type(exc).__name__}); the job log keeps these lines",
                 inline=True)


class SolBatchCodexRunner(CodexAgentRunner):
    """CodexAgentRunner behind the between-attempt USD gate, recording the app-server window.

    Built with the same arguments core/executor.py gives CodexAgentRunner. It
    accepts any CodexProviderLike so the loopback end-to-end check can drive
    it; :func:`install` holds the production type checks.
    """

    def __init__(self, provider: Any, *, session: SolBatchSession, **kwargs: Any) -> None:
        if any(kwargs.get(name) is not None for name in _RUNNER_OPTIONS_REFUSED):
            raise SolBatchControlsRefused("sol_batch_runner_option_refused")
        super().__init__(provider, **kwargs)
        self._sol_session = session
        self._sol_usage: Any = None

    def run(
        self, task_prompt: str, model: str | None = None,
        reference_files: Optional[list] = None, occupation: str = "professional",
        experiment_prompt: Optional[dict] = None, perception_text: Optional[str] = None,
        run_id: Optional[str] = None, condition_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict:
        """Admit, run and book one attempt; the signature is CodexAgentRunner.run's.

        The task's rows are listed before admission so the attempt's own rows
        can be told apart afterwards. Every result carries the task's booked
        USD as ``budget_metrics``, which step 2 publishes and relay legs read.
        """
        session = self._sol_session
        before = session.call_ids(task_id)
        refusal, decision = session.admit(task_id)
        if refusal is None and before is None:
            refusal = GATE_UNVERIFIED
        if refusal is not None:
            # Nothing is created: no workspace, runtime or ledger reservation.
            # The category is not one step 2 retries, so the task ends here.
            result = self._failure(refusal, category=refusal)
            result["runner_evidence"] = runner_environment.receipt("inference")
            result["budget_metrics"] = session.task_budget(task_id)
            session.record_refusal(task_id, refusal, decision)
            return result
        self._sol_usage = None
        result = None
        try:
            result = super().run(
                task_prompt, model=model, reference_files=reference_files,
                occupation=occupation, experiment_prompt=experiment_prompt,
                perception_text=perception_text, run_id=run_id,
                condition_name=condition_name, task_id=task_id,
            )
        except Exception as exc:  # noqa: BLE001
            # The dict TaskExecutor.execute builds for a runner that raises
            # (core/executor.py:880-886), so the attempt still carries its booking.
            result = {"success": False, "text": "", "files": [],
                      "error": f"Executor error (codex_foundry): {exc}"}
        finally:
            session.book_attempt(task_id=task_id, before=before, decision=decision,
                                 result=result, usage=self._sol_usage)
        result["budget_metrics"] = session.task_budget(task_id)
        return result

    def _await_turn(self, turn_handle: Any, **kwargs: Any) -> TurnObservation:
        """Keep the usage object the settlement reads, for its context window.

        The only coupling to a private method of the sealed class:
        _run_one_turn calls ``self._await_turn(turn_handle)`` when there is no
        deadline or observer. Core keeps only ``.total`` from this object, so
        the app-server window is otherwise lost.
        """
        observed = super()._await_turn(turn_handle, **kwargs)
        result_usage = getattr(observed.result, "usage", None) if observed.result is not None else None
        self._sol_usage = result_usage if result_usage is not None else observed.usage
        return observed

    def close(self) -> None:
        # Step 2 closes the executor before the ledger, so the summary can still read it.
        try:
            self._sol_session.finish()
        finally:
            super().close()


# -- installation -----------------------------------------------------------


def _asks_for_sol(settings: Any) -> bool:
    # Normalized and prefix-matched, so a dated, suffixed or differently cased
    # Sol deployment name cannot step around the gate.
    model = getattr(settings, "model", None)
    return isinstance(model, str) and model.strip().lower().startswith(SOL_MODEL)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SolBatchControlsRefused(code)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(
    executor: Any, *, experiment_id: str, condition_key: str, codex_settings: Any,
    cost_ledger: Any, run_id: str, task_ids: Sequence[str], max_retries: Any,
    resume_max_rounds: Any, task_deadlines: Any, restored_progress: Mapping[str, Any] | None,
    workspace: Path | str,
) -> SolBatchSession | None:
    """Attach the Sol controls to step 2's executor, or do nothing at all.

    Returns ``None``, touching and printing nothing, unless the run is
    :data:`EXPERIMENT_ID` or asks Codex for gpt-5.6-sol. For the registered
    batch it returns the installed session. Every refusal is a
    :class:`SolBatchControlsRefused` raised before any attempt, with
    ``executor.runner`` unchanged.
    """
    if experiment_id != EXPERIMENT_ID and not _asks_for_sol(codex_settings):
        return None
    try:
        return _install(
            executor, experiment_id=experiment_id, condition_key=condition_key,
            codex_settings=codex_settings, cost_ledger=cost_ledger, run_id=run_id,
            task_ids=task_ids, max_retries=max_retries, resume_max_rounds=resume_max_rounds,
            task_deadlines=task_deadlines, restored_progress=restored_progress, workspace=workspace,
        )
    except SolBatchControlsRefused:
        raise
    except Exception as exc:  # noqa: BLE001 - the message may name an endpoint; only the type leaves
        raise SolBatchControlsRefused(f"sol_batch_install_failed:{type(exc).__name__}"[:80]) from None


def _install(
    executor: Any, *, experiment_id: str, condition_key: str, codex_settings: Any,
    cost_ledger: Any, run_id: str, task_ids: Sequence[str], max_retries: Any,
    resume_max_rounds: Any, task_deadlines: Any, restored_progress: Mapping[str, Any] | None,
    workspace: Path | str,
) -> SolBatchSession:
    _require(experiment_id == EXPERIMENT_ID, "sol_batch_unregistered_experiment")
    _require(type(codex_settings) is CodexProviderSettings and codex_settings.model == SOL_MODEL,
             "sol_batch_model_drift")
    _require(codex_settings.reasoning_effort == REASONING_EFFORT
             and codex_settings.model_context_window == CONTEXT_WINDOW
             and codex_settings.request_max_retries == 0
             and codex_settings.stream_max_retries == 0, "sol_batch_request_drift")
    _require(condition_key == "condition_a", "sol_batch_condition_refused")
    _require(task_deadlines is None, "sol_batch_deadline_refused")
    # The reserve assumes four attempts per task at most: three infra retries
    # and no resume round.
    _require(type(max_retries) is int and max_retries == MAX_RETRIES
             and type(resume_max_rounds) is int and resume_max_rounds == 0,
             "sol_batch_retry_policy_drift")
    _require(tuple(task_ids) == FIXED_TASK_IDS, "sol_batch_task_set_drift")
    # A GitHub re-run restarts from an older checkpoint, or from nothing, and
    # would forget spend already made. Relay legs are fresh dispatches.
    _require(os.environ.get("GITHUB_RUN_ATTEMPT", "1") in {"", "1"}, "sol_batch_rerun_refused")
    runner = getattr(executor, "runner", None)
    _require(type(runner) is CodexAgentRunner and runner.provider is codex_settings,
             "sol_batch_runner_drift")
    _require(all(getattr(runner, name, None) is None for name in _RUNNER_OPTIONS_REFUSED),
             "sol_batch_runner_option_refused")
    _require(cost_ledger is not None and runner.cost_ledger is cost_ledger
             and cost_ledger.run_id == run_id, "sol_batch_ledger_drift")
    _require(runner.run_id == run_id and runner.condition_name == condition_key,
             "sol_batch_runner_drift")
    _require(runner.timeout == ATTEMPT_TIMEOUT_SECONDS, "sol_batch_timeout_drift")

    provider = SolLongContextProviderSettings.from_settings(codex_settings)
    try:
        held_catalog_override()
    except SolLongContextRefused:
        raise SolBatchControlsRefused("sol_batch_catalog_unverified") from None
    rates = load_sol_list_rates()

    # Tasks this ledger already holds rows for (a local resume) are counted
    # from the ledger, not again from their progress rows.
    live = {
        task for task in cost_ledger.task_ids()
        if any(row.get("run_id") == cost_ledger.run_id for row in cost_ledger.calls_for(task))
    }
    results = (restored_progress or {}).get("results") or []
    prior_rows = [row for row in results if isinstance(row, dict) and row.get("task_id") not in live]
    prior_legs_usd, prior_tasks = booked_from_rows(prior_rows)
    window_mismatch = any(
        isinstance(row.get("observability"), dict)
        and row["observability"].get("error_category") == WINDOW_MISMATCH
        for row in prior_rows
    )
    statuses: dict[str, int] = {}
    for row in results:
        if isinstance(row, dict):
            status = str(row.get("status"))
            statuses[status] = statuses.get(status, 0) + 1

    # Never the endpoint, base_url or auth argv: this file is uploaded.
    header = {
        "schema": RECORD_SCHEMA,
        "experiment_id": experiment_id,
        "run_id": run_id,
        "condition_key": condition_key,
        "github": {"run_id": os.environ.get("GITHUB_RUN_ID"),
                   "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")},
        "relay_lineage_id": os.environ.get("GDPVAL_RELAY_LINEAGE_ID"),
        "restored_progress": {"present": restored_progress is not None,
                              "status_counts": dict(sorted(statuses.items()))},
        "codex": describe_version_pin(),
        "requested": {"model": codex_settings.model,
                      "reasoning_effort": codex_settings.reasoning_effort,
                      "model_context_window": codex_settings.model_context_window},
        "catalog": {"path": CATALOG_RELATIVE, "sha256": CATALOG_SHA256,
                    "sol_window": CATALOG_SOL_MAX_CONTEXT_WINDOW, "effective_percent": 100,
                    "bundled_window": CODEX_BUNDLED_SOL_CONTEXT_WINDOW},
        "added_codex_overrides": ["model_catalog_json=" + CATALOG_RELATIVE],
        "usd": {
            "ceiling": fmt(CEILING_USD),
            "grading_reserve": fmt(GRADING_RESERVE_USD),
            "attempt_reserve": fmt(ATTEMPT_RESERVE_USD),
            "solve_budget": fmt(SOLVE_BUDGET_USD),
            "admit_while_spend_at_most": fmt(SOLVE_BUDGET_USD - ATTEMPT_RESERVE_USD),
            "refused_request": fmt(REFUSED_REQUEST_USD),
            "meter": SOL_METER,
            "rates": {"input": str(rates.input), "cached_input": str(rates.cached_input),
                      "cache_write": str(rates.cache_write), "output": str(rates.output)},
            "rates_retrieved": rates.retrieved,
            "price_table_sha256": PRICE_TABLE_SHA256,
            "cache_write_rule": "max(reported, input - cached)",
            "reasoning": "inside output",
            "unknown_usage": (
                "a turn with no reported usage books the attempt reserve; a rate "
                "refusal with no completed item books one refused request; a "
                "settled turn without priceable counts books the attempt reserve; "
                "an abandoned turn books 0"
            ),
            "prior_lineage_spend_usd": fmt(PRIOR_LINEAGE_SPEND_USD),
            "prior_legs_spend_usd": fmt(prior_legs_usd),
            "prior_leg_tasks": prior_tasks,
        },
        "sources": {
            _STEP2_RELATIVE: _sha256_file(ROOT / _STEP2_RELATIVE),
            _THIS_RELATIVE: _sha256_file(Path(__file__).resolve()),
            CATALOG_RELATIVE: _sha256_file(CATALOG_PATH),
            _PRICE_TABLE_RELATIVE: _sha256_file(Path(PRICE_TABLE_PATH)),
        },
        "window_rule": "stop starting attempts after an app-server window other than 1000000",
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }
    session = SolBatchSession(
        ledger=cost_ledger, rates=rates,
        record_path=Path(workspace) / f"sol_batch_controls_{condition_key}.json",
        seed_usd=PRIOR_LINEAGE_SPEND_USD + prior_legs_usd, prior_legs_usd=prior_legs_usd,
        window_mismatch=window_mismatch, header=header,
    )
    # The same arguments core/executor.py:721-731 gives CodexAgentRunner. Built
    # before the record is written, so a failure here leaves no record behind.
    replacement = SolBatchCodexRunner(
        provider, session=session, timeout=runner.timeout, cost_ledger=runner.cost_ledger,
        run_id=runner.run_id, condition_name=runner.condition_name,
    )
    session._write(strict=True)
    # An attribute of the executor step 2 owns; no class or function in a
    # sealed module is patched.
    executor.runner = replacement
    _say(f"[sol-batch] controls on for {EXPERIMENT_ID}")
    _say(f"[sol-batch] reasoning effort {REASONING_EFFORT} (the Codex 0.147.0 catalog default "
         f"for {SOL_MODEL} is low)")
    _say(f"[sol-batch] context window {CONTEXT_WINDOW:,} via held catalog {CATALOG_SHA256[:12]}")
    _say(f"[sol-batch] USD gate: {CEILING_USD} ceiling − {GRADING_RESERVE_USD} grading = "
         f"{SOLVE_BUDGET_USD} solve budget; {ATTEMPT_RESERVE_USD} reserve per attempt; attempts "
         f"start while booked spend ≤ {SOLVE_BUDGET_USD - ATTEMPT_RESERVE_USD:.2f}; prior legs "
         f"{fmt(prior_legs_usd)}")
    _say(f"[sol-batch] record: {session.record_path}")
    return session
