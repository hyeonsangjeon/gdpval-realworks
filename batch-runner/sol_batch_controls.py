"""Solve-side controls for GPT-5.6 Sol runs on the generic Codex batch path.

Step 2 calls :func:`install` once, right after its TaskExecutor exists, for
every codex_foundry run that is not the paused gpt56 pilot. It is inert unless
the run asks Codex for gpt-5.6-sol or is registered in :data:`RUNS`: every
other run gets ``None`` back before anything is read, written or printed.

:data:`RUNS` holds every Sol run the owner registered, each with its own task
list and USD ceiling: exp036_sol_fixed5 (approved 2026-11-05),
exp037_sol_first25 (approved 2026-11-06), exp038_sol_rest195 (registered, not
approved: refused before any attempt), its two halves exp039_sol_next98 and
exp040_sol_last97 (approved 2026-11-14), and exp041_sol_retry10, the ten tasks
those two lost to Azure-side failures (approved 2026-11-26, the first run on
:data:`BASIS_TENANT_20261126`). For an approved run it swaps the
executor's runner for :class:`SolBatchCodexRunner`, which adds two controls:

* The held #796 1M catalog. Codex 0.147.0's bundled catalog gives gpt-5.6-sol
  272,000 tokens and clamps the requested 1,000,000 to 258,400 usable; the held
  catalog keeps the request at 1,000,000. Its sha256 is checked on every
  attempt, before Codex starts.
* A between-attempt USD gate. Before each attempt it books every ledger row of
  the run in the run's booking basis (:data:`BASIS_LIST_LONG`, the published
  long-context list meter, for every run registered before 2026-11-26), adds
  what earlier relay legs booked, and refuses to START the attempt once that
  spend plus the run's attempt reserve would pass the run's solve budget. A
  running attempt is never stopped, so the last admitted attempt can
  overshoot; the owner accepted that.

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
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Sequence

from core import runner_environment
from core.codex_cost import read_breakdown
from core.codex_runner import _NOTIFY_TOKEN_USAGE, CodexAgentRunner, TurnObservation
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

SOL_MODEL = "gpt-5.6-sol"
#: Requested explicitly: the 0.147.0 catalog default for gpt-5.6-sol is "low".
REASONING_EFFORT = "max"
CONTEXT_WINDOW = 1_000_000
#: Sol's window in Codex 0.147.0's bundled catalog (258,400 usable at 95%).
CODEX_BUNDLED_SOL_CONTEXT_WINDOW = 272_000
#: Sol's context_window and max_context_window in the held catalog, 100% usable.
CATALOG_SOL_MAX_CONTEXT_WINDOW = 1_050_000
#: exp036_sol_fixed5's five tasks, in exp033's order (its registry entry holds their digest).
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
#: One refused first request on the list_long_context basis: 64,000 input
#: tokens x (10.00 + 12.50) plus 128,000 output tokens x 45.00 per 1M
#: (1.44 + 5.76).
REFUSED_REQUEST_USD = Decimal("7.20")
#: Output allowance for the one request a turn that ended unfinished may still
#: have had in flight; the same 128,000 as REFUSED_REQUEST_USD.
IN_FLIGHT_OUTPUT_TOKENS = 128_000
#: Tool output Codex may append between the last reported request and the one
#: in flight: the held catalog truncates each output to 10,000 tokens and
#: allows parallel tool calls, so this allows ten of them.
IN_FLIGHT_TOOL_OUTPUT_TOKENS = 100_000
#: Turn endings that leave no billed request in flight: a 429 is not billed,
#: and a turn that never started sent nothing.
_NOTHING_IN_FLIGHT = frozenset({"rate_limited", "turn_start_failed"})
#: The longest step-2 watchdog any registered run may use, in minutes:
#: 15 setup + 170 + one 131-minute task + 5 + 30 fits the 360-minute job.
WALL_TIMEOUT_MINUTES = 170
#: Booking bases. A run's basis is fixed when it is registered and turns into
#: the rates every booking of the run uses (load_booking_rates).
#: list_long_context: the #795 list table's long-context Standard Global
#: meter, uncached input charged at input plus cache write. Every run
#: registered before 2026-11-26 (exp035 parity, exp036 to exp040) books on it
#: for good.
BASIS_LIST_LONG = "list_long_context"
#: tenant_observed_20261126: the rates Azure billed this tenant, x1.05, on
#: the short tier up to the record's request-size bound; list_long_context
#: above it or when the size is unknown.
BASIS_TENANT_20261126 = "tenant_observed_20261126"
BOOKING_BASES = frozenset({BASIS_LIST_LONG, BASIS_TENANT_20261126})
#: The list table's short-context Standard Global meter: no tenant rate may
#: be above it.
SOL_SHORT_METER = "short_context_standard_global"
#: The held record of the tenant's observed rates. Never edited after merge:
#: a new observation or a wider bound is a new file and a new basis id.
TENANT_RATES_RELATIVE = "batch-runner/experiments/execution_envelope/sol_batch_tenant_rates_20261126.json"
TENANT_RATES_PATH = ROOT / TENANT_RATES_RELATIVE
TENANT_RATES_SHA256 = "11bf182dfb0d9dfa720a788d87e9dc4b89500ed7fae8381e5d7a791cd8c976e2"
TENANT_RATES_SCHEMA = "sol-batch-tenant-rates-v1"
#: The refused first request's input, the same 64,000 as REFUSED_REQUEST_USD.
REFUSED_REQUEST_INPUT_TOKENS = 64_000
#: Codex app-server item notifications; the observer reads sub-agent items off them.
_NOTIFY_ITEM_EVENTS = frozenset({"item/started", "item/completed"})
#: Thread items a turn that used Codex's collaboration tools carries: a
#: spawned or contacted sub-agent, and a collaboration tool call.
_SUB_AGENT_ITEM_TYPES = frozenset({"subAgentActivity", "collabAgentToolCall"})
#: Collaboration tools that start no sub-agent request (CollabAgentTool values).
_COLLAB_TOOLS_WITHOUT_REQUESTS = frozenset({"wait", "closeAgent"})


@dataclass(frozen=True)
class SolRun:
    """One Sol run the owner registered on this path, with its own USD ceiling.

    ``approval`` names who approved spending and when. ``None`` registers the
    run without approving it: :func:`install` refuses it before any attempt
    and the grade preflight refuses it before reading anything published.
    The money fields of an approved run are all set; :func:`registry_problems`
    lists what is not.

    These fields were #799's module constants, and older CHANGELOG entries
    and run notes still use those names: ``EXPERIMENT_ID`` is
    ``RUNS["exp036_sol_fixed5"]``, ``CEILING_USD``, ``GRADING_RESERVE_USD``,
    ``ATTEMPT_RESERVE_USD``, ``SOLVE_BUDGET_USD`` and ``NARRATIVE_ALLOWANCE_USD``
    are its ``ceiling_usd``, ``grading_reserve_usd``, ``attempt_reserve_usd``,
    ``solve_budget_usd`` and ``narrative_allowance_usd``, and
    ``PRIOR_LINEAGE_SPEND_USD`` and ``LOST_BOOKING_USD`` are its
    ``prior_lineage_spend_usd`` and ``lost_booking_usd``. A recovery pull
    request edits the entry of the run it recovers, never another run's.
    """

    experiment_id: str
    #: The one grading config allowed to grade this run; its twin entry in
    #: sol_batch_grading.APPROVALS names the same config and ceiling.
    grading_config_name: str
    task_count: int
    #: core/inference_manifest._ordered_task_ids_sha256 of data.filter.task_ids,
    #: the digest inference_provenance.json publishes.
    ordered_task_ids_sha256: str
    approval: str | None
    #: Solve and grade together, in the run's booking basis.
    ceiling_usd: Decimal | None = None
    #: Kept out of the solve budget for grading and the step 6 narrative.
    grading_reserve_usd: Decimal | None = None
    #: The most one attempt is assumed to add when the gate admits it; also the
    #: booking of an attempt whose usage was never reported.
    attempt_reserve_usd: Decimal | None = None
    #: Step 6 narrative: two Sol Max calls, 12,288 output tokens at most.
    #: Booked by sol_batch_grading, not by the solve gate.
    narrative_allowance_usd: Decimal | None = None
    #: Everything earlier lineages of this run spent; a fresh dispatch
    #: (relay_run 0) restores no rows and starts from this alone. Raise it by
    #: PR before ANY fresh dispatch of this run that follows one which spent
    #: anything, including lineages whose legs did upload a checkpoint. Raise
    #: it by that lineage's OWN spend: its last cumulative "[sol-batch] ...
    #: solve spend" figure minus the prior-lineage figure it started from (the
    #: "leg closed" line and the install banner print it; record summary
    #: solve_spend_usd - prior_lineage_spend_usd), plus the narrative allowance
    #: if its final leg ran step 6, plus the run's attempt_reserve_usd if the
    #: last of its legs to print "[sol-batch] record:" printed no "[sol-batch]
    #: leg closed" line after it (record summary null). A hard kill
    #: mid-attempt (OOM, a lost runner, a cancellation or a timeout) skips both
    #: that attempt's booking and the close, so no printed figure includes the
    #: attempt it was running; if the leg died between attempts instead, the
    #: reserve over-counts, which is the safe side. Every solve spend figure
    #: already includes this value, so raising it by the whole figure counts
    #: it twice.
    prior_lineage_spend_usd: Decimal = Decimal(0)
    #: Bookings step 2 lost from a published result of this run, in USD, keyed
    #: by (HF inference revision, task id). Leave it empty unless a grade
    #: preflight refused with sol_batch_prior_spend_unaccounted: a task row
    #: reached Codex (its problem_solving_cost receipt counts model calls) but
    #: an error after the runner rebuilt it without its budget_metrics, and
    #: raising prior_lineage_spend_usd cannot clear that. Add the task's
    #: booking by PR: the sum of its "[sol-batch] <first 8 of task id> attempt
    #: N: booked X" in the publishing leg's job log (or of booked_usd over its
    #: attempts in that leg's sol_batch_controls record). Only the grade
    #: preflight reads it, for the revision it grades, so an entry never
    #: applies to another lineage.
    lost_booking_usd: Mapping[tuple[str, str], Decimal] = dataclasses.field(
        default_factory=lambda: MappingProxyType({}))
    #: This run's watchdog ceiling, at most WALL_TIMEOUT_MINUTES.
    wall_timeout_minutes: int = WALL_TIMEOUT_MINUTES
    #: One of BOOKING_BASES, fixed for the run's life. Its twin is
    #: sol_batch_grading.Approval.booking_basis.
    booking_basis: str = BASIS_LIST_LONG

    @property
    def solve_budget_usd(self) -> Decimal:
        return self.ceiling_usd - self.grading_reserve_usd

    @property
    def admit_while_at_most_usd(self) -> Decimal:
        return self.solve_budget_usd - self.attempt_reserve_usd


_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_FULL_SHA = re.compile(r"[0-9a-f]{40}")


def _spend(value: Any) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value >= 0


#: Every Sol run registered on this path. A new run, a raised ceiling or an
#: approval is a pull request that edits this table.
RUNS: Mapping[str, SolRun] = MappingProxyType({run.experiment_id: run for run in (
    # Owner approval 2026-11-05. USD 200 = 146 solve + 54 grading; 51 per attempt.
    SolRun(
        experiment_id="exp036_sol_fixed5",
        grading_config_name="exp036_v2_sol_max",
        task_count=5,
        ordered_task_ids_sha256="23ede7c52a525584acce5840f69efcb8725ed7523714f5ad92e564cbae7331cd",
        approval="owner 2026-11-05",
        ceiling_usd=Decimal("200"),
        grading_reserve_usd=Decimal("54"),
        attempt_reserve_usd=Decimal("51"),
        narrative_allowance_usd=Decimal("2.00"),
    ),
    # Owner approval 2026-11-06: the first 25 first ("셋다 예", 01:55 KST),
    # at USD 700 ("700으로 올려", 12:30 KST). USD 700 = 550 solve + 150
    # grading; 51 per attempt, so attempts start while booked solve spend
    # <= 499. 150 is about the grade's simulated median (138: each task's
    # exp035 grading cost at this meter, times 1.00-1.25 for Sol's
    # deliverables; p90 161) plus the 2.00 narrative. It only sets where the
    # solve gate stops: the grade is admitted against the whole 700 minus what
    # is committed. Simulated over 40,000 draws of exp036's five bookings
    # (resampled, or a fitted lognormal), every first attempt starts and the
    # grade fits with probability 1.000 / 0.999; expected spend about 330.
    SolRun(
        experiment_id="exp037_sol_first25",
        grading_config_name="exp037_v2_sol_max",
        task_count=25,
        ordered_task_ids_sha256="6721f7e99e7c4b59697ad925e68b5e43dc491f9c94d780c8f3777380b13c8093",
        approval='owner 2026-11-06 ("셋다 예", 01:55 KST; "700으로 올려", 12:30 KST)',
        ceiling_usd=Decimal("700"),
        grading_reserve_usd=Decimal("150"),
        attempt_reserve_usd=Decimal("51"),
        narrative_allowance_usd=Decimal("2.00"),
    ),
    # Registered, NOT approved, and never to be: exp037's readout projected
    # 12 solve legs and 11 grading chunks for these 195 (R3 and R4 failed), so
    # the owner had them solved as exp039 and exp040 below instead. Kept as
    # the list the two halves are cut from (test_sol_batch_runs holds them to
    # it).
    SolRun(
        experiment_id="exp038_sol_rest195",
        grading_config_name="exp038_v2_sol_max",
        task_count=195,
        ordered_task_ids_sha256="18699a1808cb03a6ecfdf9479879f1662b3b49ae5617df6fcbcf391f56269725",
        approval=None,
    ),
    # Owner approval 2026-11-14 ("추천대로"): exp038's 195 as two experiments,
    # USD 2,500 each for solve and grade together. 2,500 = 1,600 solve + 900
    # grading; 51 per attempt, so attempts start while booked solve spend
    # <= 1,549. Sized from exp037's 25 measured tasks (solve booking and
    # grading journal per task), resampled twice (the 25, then the stage's
    # tasks from them; 100,000 runs): median solve about 840 and grade about
    # 790, p99.9 about 1,500 and 1,263. The solve gate or the grading ceiling
    # stops about one run in 1,300 (exp039) and one in 1,700 (exp040).
    SolRun(
        experiment_id="exp039_sol_next98",
        grading_config_name="exp039_v2_sol_max",
        task_count=98,
        ordered_task_ids_sha256="147fbb87ac52a0ec8389ecf84ce2f3dee3d839c79849b23afb4f7102b7ced6f8",
        approval='owner 2026-11-14 ("추천대로": exp038 in two halves, USD 2,500 each)',
        ceiling_usd=Decimal("2500"),
        grading_reserve_usd=Decimal("900"),
        attempt_reserve_usd=Decimal("51"),
        narrative_allowance_usd=Decimal("2.00"),
    ),
    SolRun(
        experiment_id="exp040_sol_last97",
        grading_config_name="exp040_v2_sol_max",
        task_count=97,
        ordered_task_ids_sha256="8ee5de9e3c352a00c6be1d9289fd73101807ac629719f1066e05be3c127b05d1",
        approval='owner 2026-11-14 ("추천대로": exp038 in two halves, USD 2,500 each)',
        ceiling_usd=Decimal("2500"),
        grading_reserve_usd=Decimal("900"),
        attempt_reserve_usd=Decimal("51"),
        narrative_allowance_usd=Decimal("2.00"),
    ),
    # Owner approval 2026-11-26 ("Azure 오류 10건"; "USD 220 (추천)"): solve
    # and grade once more the ten tasks exp039 and exp040 lost to Azure-side
    # failures (network, Foundry 507 and peak-load refusals), in exp038's
    # order; not their content-filter or grader-side zeros. The first run on
    # tenant_observed_20261126. USD 220 = 150 solve + 70 grading; 30 per
    # attempt (at least the 29.385 in-flight bound), so attempts start while
    # booked solve spend <= 120; if every attempt booked the whole reserve,
    # five would start. A turn that uses Codex's sub-agent tools books its
    # row at list_long_context plus 30 per sub-agent thread
    # (sub_agent_bound_usd), so four threads in one turn, or one in each of
    # four turns, close the gate; exp039's solve ledgers replay at the
    # observed rates to within 0.27 of its bill (192.57 against 192.84), so
    # Sol used no sizable sub-agents there. Such a stop is a booking-rule
    # stop, not an Azure cascade, and no re-dispatch under 220 can follow
    # it: prior_lineage_spend_usd would carry the booked spend, already above
    # the 120 admit line. The ceiling is in tenant dollars; exp039's and
    # exp040's remaining limits (947.32 and 1,025.87) are list_long_context
    # dollars, a different unit. At the worst list/tenant ratio (22.50 / 5.25
    # = 4.2857, uncached input) 220 is at most 942.86 at the list meter,
    # inside both, so a tenant ceiling of 220 bounds the list figure by
    # construction. Expected spend at tenant rates about 54 (p99.9 about 128).
    # The ten first attempts stay booked in exp039 and exp040; this run starts
    # from 0.
    SolRun(
        experiment_id="exp041_sol_retry10",
        grading_config_name="exp041_v2_sol_max",
        task_count=10,
        ordered_task_ids_sha256="58675014aed6ab580517aca4abd58d7d8f074cec8fd95bfcc63c0bf8b1be8cf2",
        approval=('owner 2026-11-26 ("Azure 오류 10건": solve and grade again the ten tasks exp039 and'
                  ' exp040 lost to Azure-side failures; "USD 220 (추천)": USD 220 at tenant_observed_20261126)'),
        ceiling_usd=Decimal("220"),
        grading_reserve_usd=Decimal("70"),
        attempt_reserve_usd=Decimal("30"),
        narrative_allowance_usd=Decimal("2.00"),
        booking_basis=BASIS_TENANT_20261126,
    ),
)})
#: Experiment id plus grading config name: grade, ledger and progress file
#: names carry both, and NAME_MAX (255) leaves room for 36 characters together.
NAME_BUDGET_CHARACTERS = 36


def ordered_task_ids_sha256(task_ids: Sequence[str]) -> str:
    """The digest core/inference_manifest.py:381-387 publishes as ordered_task_ids_sha256."""
    encoded = json.dumps(list(task_ids), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def registered_run(experiment_id: Any) -> SolRun | None:
    """The registry entry for ``experiment_id``, or ``None``; reads nothing else."""
    return RUNS.get(experiment_id) if isinstance(experiment_id, str) else None


def registry_problems(runs: Mapping[str, SolRun] | None = None) -> list[str]:
    """What is wrong with the registry, as sentences; empty when nothing is."""
    problems: list[str] = []
    table = RUNS if runs is None else runs
    configs = [run.grading_config_name for run in table.values()]
    if len(set(configs)) != len(configs):
        problems.append("two runs share a grading config")
    for key, run in table.items():
        name = run.experiment_id
        if key != name:
            problems.append(f"{key}: keyed under another id")
        if len(name) + len(run.grading_config_name) > NAME_BUDGET_CHARACTERS:
            problems.append(f"{name}: id plus config name is past {NAME_BUDGET_CHARACTERS} characters")
        if type(run.task_count) is not int or run.task_count < 1:
            problems.append(f"{name}: task_count must be a positive int")
        if not (isinstance(run.ordered_task_ids_sha256, str)
                and _SHA256_HEX.fullmatch(run.ordered_task_ids_sha256)):
            problems.append(f"{name}: ordered_task_ids_sha256 must be 64 hex characters")
        if type(run.wall_timeout_minutes) is not int or not 0 < run.wall_timeout_minutes <= WALL_TIMEOUT_MINUTES:
            problems.append(f"{name}: wall_timeout_minutes must be 1..{WALL_TIMEOUT_MINUTES}")
        # Both feed the grade's seed, approved or not: a negative or
        # non-Decimal value would quietly lower it.
        if not _spend(run.prior_lineage_spend_usd):
            problems.append(f"{name}: prior_lineage_spend_usd must be a finite Decimal of at least 0")
        lost = run.lost_booking_usd
        if not isinstance(lost, Mapping) or not all(
                isinstance(key, tuple) and len(key) == 2
                and isinstance(key[0], str) and _FULL_SHA.fullmatch(key[0])
                and isinstance(key[1], str) and key[1] and key[1] == key[1].strip()
                and _spend(amount)
                for key, amount in lost.items()):
            problems.append(f"{name}: lost_booking_usd must map (40-hex revision, task id) to a finite "
                            "Decimal of at least 0")
        if not isinstance(run.booking_basis, str) or run.booking_basis not in BOOKING_BASES:
            problems.append(f"{name}: booking_basis must be one of {sorted(BOOKING_BASES)}")
        money = (run.ceiling_usd, run.grading_reserve_usd, run.attempt_reserve_usd,
                 run.narrative_allowance_usd)
        if run.approval is None:
            continue
        if any(not isinstance(value, Decimal) or not value.is_finite() or value <= 0 for value in money):
            problems.append(f"{name}: an approved run needs every money field above 0")
            continue
        if not run.narrative_allowance_usd < run.grading_reserve_usd < run.ceiling_usd:
            problems.append(f"{name}: narrative < grading reserve < ceiling does not hold")
        if not 0 < run.attempt_reserve_usd < run.solve_budget_usd:
            problems.append(f"{name}: the attempt reserve must leave a positive admission threshold")
    return problems
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
    """USD per 1,000,000 tokens on one meter, as its held source states them.

    The list_long_context basis books at :data:`SOL_METER` of the pinned
    table; the tenant basis carries its observed and booked rates in this
    shape too (:class:`SolTenantPricing`). Which one applies is the run's
    booking basis.
    """

    input: Decimal
    cached_input: Decimal
    cache_write: Decimal
    output: Decimal
    retrieved: str


_RATE_KINDS = ("input", "cached_input", "cache_write", "output")


def load_sol_list_rates(path: Path | str = PRICE_TABLE_PATH, *, meter: str = SOL_METER) -> SolRates:
    """Read a published Sol list meter from the #795-pinned price table.

    A list price, not a verified tariff. Any read or parse failure refuses,
    because a gate without rates cannot book anything.
    """
    try:
        raw = _read_held(Path(path), PRICE_TABLE_SHA256)
        meters = json.loads(raw)["azure_published_meters"]
        rates = meters[SOL_MODEL][meter]
        return SolRates(
            *(Decimal(rates[key]) for key in _RATE_KINDS),
            str(meters.get("retrieved", "")),
        )
    except Exception:
        raise SolBatchControlsRefused("sol_batch_price_table_unverified") from None


@dataclass(frozen=True)
class SolTenantPricing:
    """The tenant_observed_20261126 basis, as its held record states it.

    ``booked`` (``observed`` x ``margin``) applies on the short tier: a
    request whose input is at most ``short_through_input_tokens``. Above that,
    or when the request's size is unknown, ``fallback`` (the list_long_context
    rates) applies exactly as on that basis.
    """

    basis: str
    observed: SolRates
    booked: SolRates
    margin: Decimal
    short_through_input_tokens: int
    fallback: SolRates
    source_relative: str
    source_sha256: str
    retrieved: str


def _positive_rate(value: Any) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("a rate is not a string")
    rate = Decimal(value)
    if not rate.is_finite() or rate <= 0:
        raise ValueError("a rate is not a finite amount above 0")
    return rate


def load_sol_tenant_pricing(path: Path | str = TENANT_RATES_PATH) -> SolTenantPricing:
    """Read the held tenant-rates record and hold it to what Azure billed.

    Refuses with ``sol_batch_tenant_rates_unverified`` unless the file is the
    pinned single-link regular file and its figures agree with themselves:
    booked = observed x margin per kind, each observed rate the billed cost
    over its quantity at cents, the stated uncached quantity the sum of the
    input and cache-write quantities (arithmetic only: whether Azure bills
    uncached input once is shown by the billed windows' ledger replays, not
    by the record), one ShortCo Standard Global meter per kind and
    no long-context or Data Zone meter billed, a bound inside the held
    catalog's window, the list_long_context fallback pinned to the #795
    table, and no rate above the table's short-context list meter. A failure
    to read the table itself keeps ``sol_batch_price_table_unverified``.
    """
    fallback = load_sol_list_rates()
    short_list = load_sol_list_rates(meter=SOL_SHORT_METER)
    try:
        record = json.loads(_read_held(Path(path), TENANT_RATES_SHA256))
        if (record["schema"] != TENANT_RATES_SCHEMA or record["basis"] != BASIS_TENANT_20261126
                or record["model"] != SOL_MODEL):
            raise ValueError("another record")
        observation = record["observation"]
        retrieved = observation["queried_at_utc"]
        if not isinstance(retrieved, str) or not retrieved:
            raise ValueError("no observation time")
        observed = {kind: _positive_rate(record["observed_usd_per_million"][kind]) for kind in _RATE_KINDS}
        booked = {kind: _positive_rate(record["booked_usd_per_million"][kind]) for kind in _RATE_KINDS}
        margin = _positive_rate(record["safety_margin"])
        if margin < 1 or any(booked[kind] != observed[kind] * margin for kind in _RATE_KINDS):
            raise ValueError("booked is not observed x margin")
        meters = observation["meters"]
        if not isinstance(meters, list) or len(meters) != len(_RATE_KINDS):
            raise ValueError("not one meter per kind")
        by_kind: dict[str, tuple[Decimal, Decimal]] = {}
        for meter in meters:
            kind, name = meter["rate_kind"], meter["meter_name"]
            if (kind not in _RATE_KINDS or kind in by_kind or not isinstance(name, str)
                    or "ShortCo" not in name or "Std Gl" not in name):
                raise ValueError("a meter that is not one ShortCo Standard Global meter per kind")
            by_kind[kind] = (_positive_rate(meter["quantity_million_tokens"]), _positive_rate(meter["cost_usd"]))
        for kind, (quantity, cost) in by_kind.items():
            if (cost / quantity).quantize(Decimal("0.01")) != observed[kind]:
                raise ValueError("an observed rate is not its billed cost over its quantity")
        if sum((cost for _, cost in by_kind.values()), Decimal(0)) != _positive_rate(observation["period_cost_usd"]):
            raise ValueError("the meters do not add to the period cost")
        # A consistency check on the record's own arithmetic, not evidence
        # that Azure bills uncached input once: the record's figure is the sum
        # of these two quantities. The "once" rule rests on the billed
        # windows' ledger replays (test_the_tenant_basis_reconciles_with_billing).
        if (by_kind["input"][0] + by_kind["cache_write"][0]
                != _positive_rate(observation["uncached_input_million_tokens"])):
            raise ValueError("uncached_input_million_tokens is not the input plus cache-write quantities")
        if observation["long_context_meters_billed"] != [] or observation["data_zone_meters_billed"] != []:
            raise ValueError("a long-context or Data Zone meter was billed")
        bound = record["short_tier_through_request_input_tokens"]
        if type(bound) is not int or not 0 < bound < CATALOG_SOL_MAX_CONTEXT_WINDOW:
            raise ValueError("the short-tier bound is not inside the catalog window")
        named = record["fallback"]
        if (named["basis"] != BASIS_LIST_LONG or named["meter"] != SOL_METER
                or named["price_table_sha256"] != PRICE_TABLE_SHA256):
            raise ValueError("the fallback is not the list_long_context basis")
        ceiling = {kind: getattr(short_list, kind) for kind in _RATE_KINDS}
        if any(observed[kind] > ceiling[kind] or booked[kind] > ceiling[kind] for kind in _RATE_KINDS):
            raise ValueError("a tenant rate is above the short-context list meter")
    except Exception:
        raise SolBatchControlsRefused("sol_batch_tenant_rates_unverified") from None
    return SolTenantPricing(
        basis=BASIS_TENANT_20261126,
        observed=SolRates(*(observed[kind] for kind in _RATE_KINDS), retrieved),
        booked=SolRates(*(booked[kind] for kind in _RATE_KINDS), retrieved),
        margin=margin,
        short_through_input_tokens=bound,
        fallback=fallback,
        source_relative=TENANT_RATES_RELATIVE,
        source_sha256=TENANT_RATES_SHA256,
        retrieved=retrieved,
    )


def load_booking_rates(basis: Any) -> SolRates | SolTenantPricing:
    """The rates a run books with, from its booking basis; an unknown basis refuses."""
    if basis == BASIS_LIST_LONG and isinstance(basis, str):
        return load_sol_list_rates()
    if basis == BASIS_TENANT_20261126 and isinstance(basis, str):
        # Read at call time, so the record a run books from is the module's.
        return load_sol_tenant_pricing(TENANT_RATES_PATH)
    raise SolBatchControlsRefused("sol_batch_booking_basis_unknown")


def booking_source_sha256(basis: Any) -> str:
    """The sha256 of the held file a basis books from; an unknown basis refuses."""
    if basis == BASIS_LIST_LONG and isinstance(basis, str):
        return PRICE_TABLE_SHA256
    if basis == BASIS_TENANT_20261126 and isinstance(basis, str):
        return TENANT_RATES_SHA256
    raise SolBatchControlsRefused("sol_batch_booking_basis_unknown")


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

    The list_long_context basis, and the tenant basis's fallback; a run
    books through :func:`booked_price_usd`, which picks by the run's booking
    basis. Cache writes are booked as max(reported, input - cached): an upper
    bound on what one turn can write, since Codex's ledger keeps no
    cache-write count. Reasoning is billed inside output and is never added
    on top.
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


def _short_price_usd(
    pricing: SolTenantPricing, *, input_tokens: Any, cached_input_tokens: Any, output_tokens: Any,
    reported_cache_write_tokens: Any,
) -> Decimal:
    """The short-tier booking of counts list_price_usd already found priceable.

    Uncached input is billed once, on the input or the cache-write meter, so
    max(reported, input - cached) tokens are charged once at the higher of
    the two booked rates.
    """
    inputs = _count(input_tokens)
    outputs = _count(output_tokens)
    cached = 0 if cached_input_tokens is None else _count(cached_input_tokens)
    assert inputs is not None and outputs is not None and cached is not None
    reported = _count(reported_cache_write_tokens)
    writes = max(inputs - cached, reported if reported is not None else 0)
    rates = pricing.booked
    amount = (
        writes * max(rates.input, rates.cache_write)
        + cached * rates.cached_input
        + outputs * rates.output
    ) / TOKENS_PER_MILLION
    return amount.quantize(MONEY_PLACES, rounding=ROUND_CEILING)


def _short_tier(pricing: SolTenantPricing, request_input_tokens: Any) -> bool:
    size = _count(request_input_tokens)
    return size is not None and size <= pricing.short_through_input_tokens


def booked_tier(rates: Any, request_input_tokens: Any) -> str:
    """``"list"`` on the list_long_context basis; on the tenant basis ``"short"`` or ``"fallback"``."""
    if not isinstance(rates, SolTenantPricing):
        return "list"
    return "short" if _short_tier(rates, request_input_tokens) else "fallback"


def booked_price_usd(
    *,
    input_tokens: Any,
    cached_input_tokens: Any,
    output_tokens: Any,
    reasoning_tokens: Any = None,
    reported_cache_write_tokens: Any = None,
    request_input_tokens: Any = None,
    rates: Any,
) -> Decimal | None:
    """One booking in the run's booking basis, or ``None`` when its counts cannot be priced.

    On the list_long_context basis (any rates that are not a
    :class:`SolTenantPricing`) it is :func:`list_price_usd`. On the tenant
    basis a request of at most the record's bound (``request_input_tokens``,
    the largest request input of the turn) books at the short tier; above
    it, or of unknown size, it books exactly the list_long_context amount.
    The validity rules are list_price_usd's on both.
    """
    if not isinstance(rates, SolTenantPricing):
        return list_price_usd(
            input_tokens=input_tokens, cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
            reported_cache_write_tokens=reported_cache_write_tokens, rates=rates,
        )
    listed = list_price_usd(
        input_tokens=input_tokens, cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
        reported_cache_write_tokens=reported_cache_write_tokens, rates=rates.fallback,
    )
    if listed is None or not _short_tier(rates, request_input_tokens):
        return listed
    return _short_price_usd(
        rates, input_tokens=input_tokens, cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens, reported_cache_write_tokens=reported_cache_write_tokens,
    )


def floor_price_usd(
    *, input_tokens: Any, cached_input_tokens: Any, output_tokens: Any, reasoning_tokens: Any = None,
    rates: Any,
) -> Decimal | None:
    """The lowest booking a ledger row can get in the run's basis: the published-ledger floor.

    On the list basis it is :func:`list_price_usd` with writes = input -
    cached; on the tenant basis the short tier at any size, with the same
    writes.
    """
    listed = list_price_usd(
        input_tokens=input_tokens, cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens, reasoning_tokens=reasoning_tokens,
        rates=rates.fallback if isinstance(rates, SolTenantPricing) else rates,
    )
    if listed is None or not isinstance(rates, SolTenantPricing):
        return listed
    return _short_price_usd(
        rates, input_tokens=input_tokens, cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens, reported_cache_write_tokens=None,
    )


def refused_request_usd(rates: Any) -> Decimal:
    """One refused first request in the run's basis: 7.20 on the list basis, 3.024 on the tenant one."""
    if not isinstance(rates, SolTenantPricing):
        return REFUSED_REQUEST_USD
    amount = booked_price_usd(
        input_tokens=REFUSED_REQUEST_INPUT_TOKENS, cached_input_tokens=0,
        output_tokens=IN_FLIGHT_OUTPUT_TOKENS, request_input_tokens=REFUSED_REQUEST_INPUT_TOKENS,
        rates=rates,
    )
    assert amount is not None
    return amount


def reservation_usd_per_million(rates: Any, allowance_input_tokens: Any) -> tuple[Decimal, Decimal]:
    """``(per input token, per output token)`` USD per 1M a grading reservation is sized at.

    Every allowance input token is reserved as uncached: input plus cache
    write on the list basis (and above the tenant bound), the higher of the
    two booked rates on the tenant short tier.
    """
    if not isinstance(rates, SolTenantPricing):
        return rates.input + rates.cache_write, rates.output
    if _short_tier(rates, allowance_input_tokens):
        return max(rates.booked.input, rates.booked.cache_write), rates.booked.output
    return rates.fallback.input + rates.fallback.cache_write, rates.fallback.output


def fmt(amount: Decimal | int | float | str) -> str:
    """USD at the ledger's eight places, rounded up, as JSON-safe text."""
    # A float would carry its binary error into a ceiling rounding.
    value = Decimal(str(amount)) if isinstance(amount, float) else Decimal(amount)
    return format(value.quantize(MONEY_PLACES, rounding=ROUND_CEILING), "f")


def in_flight_bound_usd(last: Any, *, rates: SolRates | SolTenantPricing) -> Decimal:
    """The most the one request an unfinished turn may still have had in flight can cost.

    Codex reports usage only when a request completes, so a turn settled after
    a timeout, a content stop or a transport failure leaves out the request it
    was waiting on (codex_runner._settle_what_was_measured: "at least this
    much"). That request re-sends the last completed request's input and
    output plus whatever tool output Codex appended in between, and its cache
    may have gone cold. It is priced as that input grown by that output and by
    :data:`IN_FLIGHT_TOOL_OUTPUT_TOKENS`, capped at the held catalog's
    :data:`CATALOG_SOL_MAX_CONTEXT_WINDOW`, all of it uncached, plus
    :data:`IN_FLIGHT_OUTPUT_TOKENS` of output. Without a readable last request
    it is that whole window uncached plus the same output, 29.385 at the list
    meter, which is also the most it can ever be. It is priced in the run's
    booking basis, with that grown input as the request's size: on the tenant
    basis a grown input of at most the record's bound books at the short
    tier, a larger one at list_long_context.
    """
    grown = CATALOG_SOL_MAX_CONTEXT_WINDOW
    try:
        breakdown = read_breakdown(last) if last is not None else None
    except Exception:  # noqa: BLE001 - an unreadable count takes the window bound
        breakdown = None
    if breakdown is not None:
        inputs = _count(breakdown.input_tokens)
        outputs = _count(breakdown.output_tokens)
        cached = 0 if breakdown.cached_input_tokens is None else _count(breakdown.cached_input_tokens)
        # Counts that cannot describe a request take the window bound.
        if inputs and outputs is not None and cached is not None and cached <= inputs:
            grown = min(CATALOG_SOL_MAX_CONTEXT_WINDOW, inputs + outputs + IN_FLIGHT_TOOL_OUTPUT_TOKENS)
    amount = booked_price_usd(input_tokens=grown, cached_input_tokens=0,
                              output_tokens=IN_FLIGHT_OUTPUT_TOKENS, request_input_tokens=grown,
                              rates=rates)
    assert amount is not None
    return amount


def book_row(
    row: Mapping[str, Any], *, rates: SolRates | SolTenantPricing, reserve: Decimal,
    evidence: Mapping[str, Any] | None = None,
) -> tuple[Decimal, str]:
    """What one Codex ledger row costs the gate in the run's booking basis, and on what basis.

    ``evidence`` is what the attempt itself reported: its error category,
    items seen, the thread's cache-write count, the turn's largest request
    input (the tenant basis tiers on it) and, for a turn that settled
    without finishing, the bound on the request it left in flight. Usage that
    was never reported books the whole attempt reserve, except a rate refusal
    before any item completed, which books one refused first request. Booking
    a 429 at the full reserve would let two zero-cost refusals close the gate.

    ``evidence["sub_agent_usd"]``, set only on the tenant basis, is the bound
    booked for sub-agent threads the turn spawned: their requests reach no
    ledger row and no stream this process reads. It is added to whatever the
    row books, and the row's basis gains ``_with_sub_agents``, so the usage
    counts as incomplete.
    """
    amount, basis = _book_row_measured(row, rates=rates, reserve=reserve, evidence=evidence)
    sub_agents = (evidence or {}).get("sub_agent_usd")
    if sub_agents is not None and basis != "abandoned":
        return amount + Decimal(sub_agents), f"{basis}_with_sub_agents"
    return amount, basis


def _book_row_measured(
    row: Mapping[str, Any], *, rates: SolRates | SolTenantPricing, reserve: Decimal,
    evidence: Mapping[str, Any] | None = None,
) -> tuple[Decimal, str]:
    """:func:`book_row` without the sub-agent bound."""
    facts = evidence or {}
    state = row.get("state")
    if state == STATE_ABANDONED:
        # The turn never started (codex_runner.py:1914).
        return Decimal(0), "abandoned"
    if state == STATE_SETTLED:
        amount = booked_price_usd(
            input_tokens=row.get("input_tokens"),
            cached_input_tokens=row.get("cached_input_tokens"),
            output_tokens=row.get("output_tokens"),
            reasoning_tokens=row.get("reasoning_tokens"),
            reported_cache_write_tokens=facts.get("cache_write_input_tokens"),
            request_input_tokens=facts.get("tier_request_input_tokens"),
            rates=rates,
        )
        if amount is None:
            # A turn can settle with no counts (usage_absent).
            return reserve, "settled_without_usage"
        in_flight = facts.get("in_flight_usd")
        if in_flight is not None:
            # What the stream reported, plus the request it never reported.
            return amount + Decimal(in_flight), "settled_partial"
        return amount, "settled"
    if state == STATE_REFUSED:
        return refused_request_usd(rates), "refused_request"
    # Reserved: the stream reported no usage (codex_runner.py:1978).
    items_seen = facts.get("items_seen")
    if (facts.get("error_category") == "rate_limited"
            and type(items_seen) is int and items_seen == 0):
        return refused_request_usd(rates), "rate_limited_first_request"
    return reserve, "usage_unreported"


# -- spend carried across relay legs and to grading -------------------------


def task_budget_metrics(amount: Decimal, complete: bool) -> dict[str, Any]:
    """The task's booked USD in the shape step 2 publishes as budget_metrics.

    Only USD is carried: step 2's bounded copy drops token counts above
    1,000,000, and this field is what crosses relay checkpoints and reaches
    self_report.json.
    """
    return {"conservative_cost_usd": fmt(amount), "usage_complete": bool(complete)}


def _usd(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
    try:
        amount = Decimal(str(value))
    except (ArithmeticError, ValueError):
        raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted") from None
    if not amount.is_finite() or not Decimal(0) <= amount < Decimal(1_000_000):
        raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
    return amount


def _made_no_codex_call(row: Mapping[str, Any], observability: Mapping[str, Any]) -> bool:
    """Whether step 2 recorded that no Codex attempt was ever reserved for the row's task.

    Step 2 stamps every row with the task's ``problem_solving_cost`` receipt,
    read from the per-turn ledger each attempt reserves in, so ``model_calls``
    0 means no attempt reached Codex (reference_input_integrity_failed is the
    known case). A missing ``runner_evidence`` cannot say this: step 2 drops
    it, and the booking with it, when anything after the runner raises. Nor
    can the error text: the checkpoint keeps only a public projection of it,
    and self_report.json drops it.
    """
    if "runner_evidence" in observability:
        return False
    receipt = row.get("problem_solving_cost")
    calls = receipt.get("model_calls") if isinstance(receipt, dict) else None
    return type(calls) is int and calls == 0


def booked_from_rows(
    rows: Iterable[Any], lost_bookings: Mapping[str, Any] | None = None,
) -> tuple[Decimal, list[str]]:
    """Sum the USD earlier legs booked onto their task rows.

    A row without a booking counts as zero only when its solving receipt
    shows no Codex call at all. Any other such row takes its amount from
    ``lost_bookings`` (by task id), or refuses, because counting it as zero
    would under-seed the gate. Pending rows are watchdog placeholders for
    tasks that have not run.
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
        elif not _made_no_codex_call(row, observability):
            task_id = row.get("task_id")
            lost = (lost_bookings or {}).get(task_id) if isinstance(task_id, str) else None
            if lost is None:
                raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
            total += _usd(lost)
            tasks.append(task_id)
    return total, tasks


def lost_bookings_for(run: SolRun, revision: Any) -> dict[str, Decimal]:
    """The run's lost_booking_usd entries for one published inference revision, by task id."""
    found: dict[str, Decimal] = {}
    for key, amount in run.lost_booking_usd.items():
        if not (isinstance(key, tuple) and len(key) == 2 and all(isinstance(part, str) for part in key)):
            raise SolBatchControlsRefused("sol_batch_prior_spend_unaccounted")
        if isinstance(revision, str) and key[0] == revision:
            found[key[1]] = amount
    return found


def solve_spend_usd(rows: Iterable[Any], revision: str | None, run: SolRun) -> Decimal:
    """The lineage's solve spend from its published task rows; the grade side seeds from this.

    ``revision`` is the published inference commit being graded; it selects
    the run's lost_booking_usd entries recorded for that result.
    """
    return run.prior_lineage_spend_usd + booked_from_rows(rows, lost_bookings_for(run, revision))[0]


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


class _RequestSizes:
    """The input size of each request a turn reported, read off its event stream.

    Codex 0.147.0 sends a ``thread/tokenUsage/updated`` notification after a
    completed request: ``last.input_tokens`` is that request's input and
    ``total.input_tokens`` the thread's running total. When a request fails,
    is cut off or reports no usage, it sends the previous notification again
    (the same ``last`` and an unchanged ``total``); that repeat is not a
    request and is skipped. A total that grew by more than ``last`` means
    requests the observer never saw; the excess is kept as
    ``unobserved_input_tokens`` and bounds each of them. The tenant basis
    tiers a turn on its largest request; anything that makes the sizes
    untrustworthy (an unreadable size or total, a total that fell or grew by
    less than ``last``, a size that shrank) is recorded so the turn falls
    back to list_long_context.

    Sub-agent threads (Codex's ``collaboration`` tools) send their usage to
    their own turn, never to this stream, and their requests reach no ledger
    row. The parent stream does carry the ``subAgentActivity`` items and
    the ``collabAgentToolCall`` items that spawn or message an agent, so
    they are counted (``sub_agent_items``; a wait or close call starts no
    request and is not): a turn with any of them cannot be sized, and the
    tenant basis books a bound for the threads it spawned.
    """

    def __init__(self) -> None:
        self.updates = 0
        self.repeats = 0
        self.peak: int | None = None
        self.observed_sum = 0
        self.unobserved = 0
        self.previous: int | None = None
        self.previous_total: int | None = None
        self.shrank = False
        self.unreadable = False
        self._sub_agent_items: set[str] = set()
        self._sub_agent_threads: set[str] = set()

    @property
    def sub_agent_items(self) -> int:
        return len(self._sub_agent_items)

    @property
    def sub_agent_threads(self) -> int:
        """Sub-agent threads seen; at least 1 once any sub-agent item was seen."""
        if not self._sub_agent_items:
            return 0
        return max(1, len(self._sub_agent_threads))

    def observe(self, event: Any) -> None:
        method = getattr(event, "method", None)
        if method in _NOTIFY_ITEM_EVENTS:
            self._observe_item(getattr(getattr(event, "payload", None), "item", None))
            return
        if method != _NOTIFY_TOKEN_USAGE:
            return
        usage = getattr(getattr(event, "payload", None), "token_usage", None)
        if usage is None:
            return
        self.updates += 1
        size = _count(getattr(getattr(usage, "last", None), "input_tokens", None))
        total = _count(getattr(getattr(usage, "total", None), "input_tokens", None))
        if size is None or total is None:
            self.unreadable = True
            return
        if total == self.previous_total and size == self.previous:
            # Codex re-sent the previous update; no request completed.
            self.repeats += 1
            return
        grown = total - (self.previous_total or 0)
        if grown < size:
            # A total that fell, or grew by less than one request's input.
            self.unreadable = True
            return
        self.unobserved += grown - size
        self.previous_total = total
        if self.previous is not None and size < self.previous:
            self.shrank = True
        else:
            self.peak = size if self.peak is None else max(self.peak, size)
            self.observed_sum += size
        self.previous = size

    def _observe_item(self, item: Any) -> None:
        if item is None:
            return
        root = getattr(item, "root", item)
        kind = getattr(root, "type", None)
        if kind not in _SUB_AGENT_ITEM_TYPES:
            return
        tool = getattr(root, "tool", None)
        if kind == "collabAgentToolCall" and getattr(tool, "value", tool) in _COLLAB_TOOLS_WITHOUT_REQUESTS:
            # Waiting on or closing an agent sends nothing; any agent it names
            # was spawned, and counted, in this turn.
            return
        self._sub_agent_items.add(str(getattr(root, "id", None) or f"unnamed-{len(self._sub_agent_items)}"))
        thread = getattr(root, "agent_thread_id", None)
        if isinstance(thread, str) and thread:
            self._sub_agent_threads.add(thread)
        for receiver in getattr(root, "receiver_thread_ids", None) or ():
            if isinstance(receiver, str) and receiver:
                self._sub_agent_threads.add(receiver)

    def as_record(self) -> dict[str, Any]:
        return {"updates": self.updates, "repeats": self.repeats, "peak": self.peak,
                "observed_sum": self.observed_sum, "unobserved_input_tokens": self.unobserved,
                "shrank": self.shrank, "unreadable": self.unreadable,
                "sub_agent_items": self.sub_agent_items, "sub_agent_threads": self.sub_agent_threads}


class _SizedStream:
    """A turn's event stream, unchanged, with every event shown to a :class:`_RequestSizes`."""

    def __init__(self, stream: Any, sizes: _RequestSizes) -> None:
        self._stream = stream
        self._sizes = sizes

    def __iter__(self) -> Any:
        for event in self._stream:
            try:
                self._sizes.observe(event)
            except Exception:  # noqa: BLE001 - observing never touches the stream
                self._sizes.unreadable = True
            yield event

    def close(self) -> Any:
        return self._stream.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._stream, name)


class _SizedTurn:
    """A turn handle whose ``stream()`` is observed; everything else is the handle's own."""

    def __init__(self, handle: Any, sizes: _RequestSizes) -> None:
        self._handle = handle
        self._sizes = sizes

    def stream(self) -> _SizedStream:
        return _SizedStream(self._handle.stream(), self._sizes)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)


def tier_request_input_tokens(sizes: _RequestSizes | None, row_input_tokens: Any) -> int | None:
    """The turn's largest request input, or ``None`` when it cannot be trusted.

    Requests the observer missed are bounded by what their notifications'
    totals grew by beyond ``last`` (``unobserved``), and by the row's input
    less everything the totals account for, so the size is max(peak,
    unobserved, row input - observed sum - unobserved). A turn that spawned
    sub-agents has requests no total counts, so it has no size.
    """
    if (sizes is None or sizes.updates == 0 or sizes.unreadable or sizes.shrank or sizes.peak is None
            or sizes.sub_agent_items):
        return None
    total = _count(row_input_tokens)
    seen = sizes.observed_sum + sizes.unobserved
    if total is None or seen > total:
        return None
    return max(sizes.peak, sizes.unobserved, total - seen)



def sub_agent_bound_usd(sizes: _RequestSizes | None, *, rates: Any, reserve: Decimal) -> Decimal | None:
    """What the tenant basis books for the sub-agent threads a turn spawned, or ``None``.

    Their requests reach no ledger row and no stream this process reads, so
    each thread the parent stream named books the attempt reserve, the
    amount a turn with no reported usage books. The list_long_context basis
    keeps its booking unchanged, for good.
    """
    if sizes is None or not isinstance(rates, SolTenantPricing) or not sizes.sub_agent_items:
        return None
    return reserve * sizes.sub_agent_threads


class SolBatchSession:
    """The gate's state for one step-2 process, which is one relay leg.

    Spend is recomputed from the per-turn ledger at every admission rather
    than kept as a running total, so a booking this process failed to record
    is still counted the next time.
    """

    def __init__(
        self, *, run: SolRun, ledger: Any, rates: SolRates | SolTenantPricing, record_path: Path | str,
        seed_usd: Decimal, prior_legs_usd: Decimal, window_mismatch: bool,
        header: Mapping[str, Any],
    ) -> None:
        self.run = run
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
            amount, basis = book_row(row, rates=self.rates, reserve=self.run.attempt_reserve_usd,
                                     evidence=self.evidence.get(row["call_id"]))
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
        run = self.run
        decision = {
            "spend_before_usd": fmt(spend),
            "reserve_usd": fmt(run.attempt_reserve_usd),
            "solve_budget_usd": fmt(run.solve_budget_usd),
        }
        if self.window_mismatch:
            return WINDOW_MISMATCH, decision
        if spend + run.attempt_reserve_usd > run.solve_budget_usd:
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
        requests: _RequestSizes | None = None,
    ) -> None:
        """Record one admitted attempt: its rows, their booking and the app-server window.

        ``requests`` are the request sizes the turn's stream reported; with
        the row's input they give the size the tenant basis tiers the row on.
        Like the reported cache-write count, that size applies only when the
        attempt added exactly one row. On the tenant basis, sub-agent threads
        the stream named book :func:`sub_agent_bound_usd` once, on the
        attempt's first row.

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
            category = outcome.get("error_category")
            # A turn that did not finish may have had one request in flight,
            # which its settled total never includes.
            in_flight = None
            if outcome.get("success") is not True and not (
                    isinstance(category, str) and category in _NOTHING_IN_FLIGHT):
                in_flight = in_flight_bound_usd(
                    getattr(usage, "last", None) if usage is not None else None, rates=self.rates)
            new = [entry for entry in self._rows(key) if entry["call_id"] not in before]
            size = tier_request_input_tokens(requests, new[0].get("input_tokens")) if len(new) == 1 else None
            sub_agents = sub_agent_bound_usd(requests, rates=self.rates, reserve=self.run.attempt_reserve_usd)
            booked = []
            tiers = []
            in_flight_booked = False
            sub_agents_booked = False
            for entry in new:
                # The thread total belongs to this attempt's one turn; with more
                # rows than turns it cannot be attributed, and the bound applies.
                facts = {
                    "error_category": category,
                    "items_seen": diagnostics.get("items_seen"),
                    "cache_write_input_tokens": reported if len(new) == 1 else None,
                    "tier_request_input_tokens": size,
                }
                if entry.get("state") == STATE_SETTLED:
                    tiers.append(booked_tier(self.rates, size))
                if in_flight is not None and entry.get("state") == STATE_SETTLED:
                    facts["in_flight_usd"] = in_flight
                    in_flight_booked = True
                if sub_agents is not None and not sub_agents_booked and entry.get("state") != STATE_ABANDONED:
                    # Once per attempt, on its first row that books anything.
                    facts["sub_agent_usd"] = sub_agents
                    sub_agents_booked = True
                self.evidence[entry["call_id"]] = facts
                booked.append(book_row(entry, rates=self.rates, reserve=self.run.attempt_reserve_usd,
                                       evidence=facts))
            window = app_server["model_context_window"]
            if window is not None and window != CONTEXT_WINDOW:
                self.window_mismatch = True
            row.update(
                call_ids=[entry["call_id"] for entry in new],
                booked_usd=fmt(sum((amount for amount, _ in booked), Decimal(0))),
                basis="+".join(basis for _, basis in booked) or "no_row",
                in_flight_usd=fmt(in_flight) if in_flight_booked else None,
                sub_agent_usd=fmt(sub_agents) if sub_agents_booked else None,
                input_tokens=_sum_counts(entry.get("input_tokens") for entry in new),
                cached_input_tokens=_sum_counts(entry.get("cached_input_tokens") for entry in new),
                output_tokens=_sum_counts(entry.get("output_tokens") for entry in new),
                reasoning_tokens=_sum_counts(entry.get("reasoning_tokens") for entry in new),
                reported_cache_write_tokens=_count(reported),
                request_sizes=requests.as_record() if requests is not None else None,
                tier_request_input_tokens=size,
                tier="+".join(tiers) or None,
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
            size = row["tier_request_input_tokens"]
            _say(f"{label}: booked {row['booked_usd']} ({row['basis']}); app-server window "
                 f"{window if window is not None else 'not reported'}; last request input tokens "
                 f"{last if last is not None else 'not reported'}; tier {row['tier']} at "
                 f"{size if size is not None else 'unknown'}; solve spend {row['spend_after_usd']}",
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
            return task_budget_metrics(self.run.attempt_reserve_usd * max(1, admitted), False)

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
                         "remaining_under_ceiling_usd": fmt(self.run.ceiling_usd - solve)}
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
                 f"(prior lineages {self.summary['prior_lineage_spend_usd']}, "
                 f"prior legs {self.summary['prior_legs_spend_usd']}, this leg "
                 f"{money['this_leg_spend_usd']}); {money['remaining_under_ceiling_usd']} left under "
                 f"the {self.run.ceiling_usd} ceiling; {self.summary['attempts_admitted']} attempts "
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
        self._sol_requests: _RequestSizes | None = None

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
        self._sol_requests = _RequestSizes()
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
                                 result=result, usage=self._sol_usage, requests=self._sol_requests)
        result["budget_metrics"] = session.task_budget(task_id)
        return result

    def _await_turn(self, turn_handle: Any, **kwargs: Any) -> TurnObservation:
        """Keep the usage object the settlement reads, for its context window.

        The only coupling to a private method of the sealed class:
        _run_one_turn calls ``self._await_turn(turn_handle)`` when there is no
        deadline or observer. Core keeps only ``.total`` from this object, so
        the app-server window is otherwise lost. The handle goes in wrapped,
        so the token-usage updates and sub-agent items the stream carries are
        read by :class:`_RequestSizes` (the tenant basis tiers on the largest
        request); the events themselves pass through unchanged.
        """
        sizes = self._sol_requests if self._sol_requests is not None else _RequestSizes()
        observed = super()._await_turn(_SizedTurn(turn_handle, sizes), **kwargs)
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


def _rates_record(rates: SolRates) -> dict[str, str]:
    return {kind: str(getattr(rates, kind)) for kind in _RATE_KINDS}


def install(
    executor: Any, *, experiment_id: str, condition_key: str, codex_settings: Any,
    cost_ledger: Any, run_id: str, task_ids: Sequence[str], max_retries: Any,
    resume_max_rounds: Any, task_deadlines: Any, restored_progress: Mapping[str, Any] | None,
    workspace: Path | str, wall_timeout: Any,
) -> SolBatchSession | None:
    """Attach the Sol controls to step 2's executor, or do nothing at all.

    Returns ``None``, touching and printing nothing, unless the run is in
    :data:`RUNS` or asks Codex for gpt-5.6-sol. For an approved registered run
    it returns the installed session. Every refusal is a
    :class:`SolBatchControlsRefused` raised before any attempt, with
    ``executor.runner`` unchanged.
    """
    run = registered_run(experiment_id)
    if run is None and not _asks_for_sol(codex_settings):
        return None
    try:
        return _install(
            executor, run=run, experiment_id=experiment_id, condition_key=condition_key,
            codex_settings=codex_settings, cost_ledger=cost_ledger, run_id=run_id,
            task_ids=task_ids, max_retries=max_retries, resume_max_rounds=resume_max_rounds,
            task_deadlines=task_deadlines, restored_progress=restored_progress, workspace=workspace,
            wall_timeout=wall_timeout,
        )
    except SolBatchControlsRefused:
        raise
    except Exception as exc:  # noqa: BLE001 - the message may name an endpoint; only the type leaves
        raise SolBatchControlsRefused(f"sol_batch_install_failed:{type(exc).__name__}"[:80]) from None


def _install(
    executor: Any, *, run: SolRun | None, experiment_id: str, condition_key: str, codex_settings: Any,
    cost_ledger: Any, run_id: str, task_ids: Sequence[str], max_retries: Any,
    resume_max_rounds: Any, task_deadlines: Any, restored_progress: Mapping[str, Any] | None,
    workspace: Path | str, wall_timeout: Any,
) -> SolBatchSession:
    _require(run is not None and run.experiment_id == experiment_id, "sol_batch_unregistered_experiment")
    # Registered for a later approval: nothing below is read or started.
    _require(run.approval is not None, "sol_batch_run_not_approved")
    _require(not registry_problems({run.experiment_id: run}), "sol_batch_registry_invalid")
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
    task_list = list(task_ids)
    _require(all(isinstance(task, str) for task in task_list)
             and len(task_list) == run.task_count
             and ordered_task_ids_sha256(task_list) == run.ordered_task_ids_sha256,
             "sol_batch_task_set_drift")
    # Step 2's watchdog, as step 2a resolved it. The dispatch input's default
    # (290) or no watchdog at all lets a late task run past the job's
    # 360-minute cap, which kills the leg before it uploads a checkpoint.
    _require(type(wall_timeout) is int and 0 < wall_timeout <= run.wall_timeout_minutes,
             "sol_batch_watchdog_drift")
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
    rates = load_booking_rates(run.booking_basis)

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

    in_flight_rule = (
        "a settled turn that did not finish, other than a rate refusal, also "
        "books the request it may have left in flight: the last reported "
        f"request's input grown by its output and {IN_FLIGHT_TOOL_OUTPUT_TOKENS} "
        f"tool-output tokens, capped at {CATALOG_SOL_MAX_CONTEXT_WINDOW}, all "
        f"uncached, plus {IN_FLIGHT_OUTPUT_TOKENS} output tokens; without one, "
        f"{CATALOG_SOL_MAX_CONTEXT_WINDOW} uncached input tokens plus "
        f"{IN_FLIGHT_OUTPUT_TOKENS} output tokens"
    )
    if isinstance(rates, SolTenantPricing):
        bound = rates.short_through_input_tokens
        pricing: dict[str, Any] = {
            "refused_request": fmt(refused_request_usd(rates)),
            "meter": SOL_SHORT_METER,
            "rates": _rates_record(rates.booked),
            "observed_rates": _rates_record(rates.observed),
            "safety_margin": str(rates.margin),
            "rates_retrieved": rates.retrieved,
            "rates_source": {"path": rates.source_relative, "sha256": rates.source_sha256},
            "short_tier_through_request_input_tokens": bound,
            "fallback": {"basis": BASIS_LIST_LONG, "meter": SOL_METER,
                         "rates": _rates_record(rates.fallback),
                         "rates_retrieved": rates.fallback.retrieved,
                         "price_table_sha256": PRICE_TABLE_SHA256},
            "price_table_sha256": PRICE_TABLE_SHA256,
            "cache_write_rule": ("uncached input once: max(reported, input - cached) tokens at "
                                 "max(input, cache_write) on the short tier; list_long_context above it"),
            "tier_rule": ("short when the turn's largest request input is at most "
                          f"{bound}: the largest request its parent stream's token-usage updates name "
                          "(a re-sent update is no request), any request they missed bounded by what "
                          "their totals grew by beyond it and by the row's input less what the totals "
                          "account for; list_long_context otherwise, or when unknown, or when the turn "
                          "used Codex's sub-agent tools"),
            "sub_agent_rule": ("sub-agent threads send their usage to no ledger row and no stream this "
                               "process reads: each one the parent stream names books the attempt reserve "
                               "on top of the turn's row, and the turn's usage counts as incomplete"),
            "in_flight_rule": (f"{in_flight_rule}; priced at the short tier when that grown input is at "
                               f"most {bound}, else at list_long_context"),
        }
    else:
        pricing = {
            "refused_request": fmt(REFUSED_REQUEST_USD),
            "meter": SOL_METER,
            "rates": _rates_record(rates),
            "rates_retrieved": rates.retrieved,
            "price_table_sha256": PRICE_TABLE_SHA256,
            "cache_write_rule": "max(reported, input - cached)",
            "in_flight_rule": in_flight_rule,
        }
    sources = {
        _STEP2_RELATIVE: _sha256_file(ROOT / _STEP2_RELATIVE),
        _THIS_RELATIVE: _sha256_file(Path(__file__).resolve()),
        CATALOG_RELATIVE: _sha256_file(CATALOG_PATH),
        _PRICE_TABLE_RELATIVE: _sha256_file(Path(PRICE_TABLE_PATH)),
    }
    if isinstance(rates, SolTenantPricing):
        sources[TENANT_RATES_RELATIVE] = _sha256_file(TENANT_RATES_PATH)
    # Never the endpoint, base_url or auth argv: this file is uploaded.
    header = {
        "schema": RECORD_SCHEMA,
        "experiment_id": experiment_id,
        "registered_run": {"approval": run.approval, "task_count": run.task_count,
                           "ordered_task_ids_sha256": run.ordered_task_ids_sha256,
                           "grading_config_name": run.grading_config_name},
        "run_id": run_id,
        "condition_key": condition_key,
        "wall_timeout_minutes": wall_timeout,
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
            "ceiling": fmt(run.ceiling_usd),
            "grading_reserve": fmt(run.grading_reserve_usd),
            "attempt_reserve": fmt(run.attempt_reserve_usd),
            "solve_budget": fmt(run.solve_budget_usd),
            "admit_while_spend_at_most": fmt(run.admit_while_at_most_usd),
            "booking_basis": run.booking_basis,
            **pricing,
            "reasoning": "inside output",
            "unknown_usage": (
                "a turn with no reported usage books the attempt reserve; a rate "
                "refusal with no completed item books one refused request; a "
                "settled turn without priceable counts books the attempt reserve; "
                "an abandoned turn books 0"
            ),
            "prior_lineage_spend_usd": fmt(run.prior_lineage_spend_usd),
            "prior_legs_spend_usd": fmt(prior_legs_usd),
            "prior_leg_tasks": prior_tasks,
        },
        "sources": sources,
        "window_rule": "stop starting attempts after an app-server window other than 1000000",
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }
    session = SolBatchSession(
        run=run, ledger=cost_ledger, rates=rates,
        record_path=Path(workspace) / f"sol_batch_controls_{condition_key}.json",
        seed_usd=run.prior_lineage_spend_usd + prior_legs_usd, prior_legs_usd=prior_legs_usd,
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
    _say(f"[sol-batch] controls on for {run.experiment_id} ({run.approval})")
    _say(f"[sol-batch] reasoning effort {REASONING_EFFORT} (the Codex 0.147.0 catalog default "
         f"for {SOL_MODEL} is low)")
    _say(f"[sol-batch] context window {CONTEXT_WINDOW:,} via held catalog {CATALOG_SHA256[:12]}")
    _say(f"[sol-batch] booking basis {run.booking_basis} ({booking_source_sha256(run.booking_basis)[:12]})")
    _say(f"[sol-batch] USD gate: {run.ceiling_usd} ceiling − {run.grading_reserve_usd} grading = "
         f"{run.solve_budget_usd} solve budget; {run.attempt_reserve_usd} reserve per attempt; attempts "
         f"start while booked spend ≤ {run.admit_while_at_most_usd:.2f}; prior lineages "
         f"{fmt(run.prior_lineage_spend_usd)}; prior legs {fmt(prior_legs_usd)}")
    _say(f"[sol-batch] record: {session.record_path}")
    return session
