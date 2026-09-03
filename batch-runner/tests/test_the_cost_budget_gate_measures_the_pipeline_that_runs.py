"""What a grading run costs, and why the gate that says ``< $50`` never saw it.

PR3 task 302 sets one acceptance: ``per-run cost < $50``, with the remedy on
failure spelled out as *tighten the vision/audio caps or narrow the routing
patterns*. Both halves were written against a pipeline that no longer exists.
The figure came from a three-task smoke on ``gpt-5.4`` at ``reasoning_effort:
medium``; production moved to ``default_v2_sol_max.yaml`` -- ``gpt-5.6-sol`` at
``effort: max`` -- on 2026-07-26, and the criterion was never restated. The
spec still says "per task cap 5" where the config says 112.

``PR3_COST_BUDGET.md`` answers 302 from three real runs instead. This file
recomputes every figure that report states, from payloads and ledgers committed
to this repository, so the report cannot drift away from its evidence.

Four things it is careful about.

**These are bounds, not prices.** ``gpt-5.6-sol`` is deliberately absent from
``providers`` in the price table, so no row anywhere carries a dollar value.
The bound comes from ``azure_published_meters`` at ``standard_global``, short
context low and long context high, cache-write excluded because the meter
exists but the write-token count is not recorded. Asserting the model is still
unpriced sits alongside asserting the numbers: a change that turned this
arithmetic into a published price would have to break this file first.

**Audio is a different model and is not in the sol bound.** The 185-task gold
run made 25 ``gpt-audio-1.5`` calls, also unpriced. Folding their tokens into
the sol meters gives $549.61 instead of $549.50 -- small, and wrong, and the
reason the split is tested rather than assumed. The two sol-220 runs have no
audio items at all, which is what lets their ledger-less summaries be priced
the same way.

**The summary is trusted only because it was checked twice.** The receipt
system postdates both sol-220 runs, so neither has a cost ledger and the run
summary is the only record. That summary is a faithful roll-up: proven against
the 22,528-row ledger on gold-185, and independently against the 220 per-task
token fields on each sol-220 run.

**Corpus-wide request sizes are not re-pinned here.** The 226,701-token maximum
and the zero calls over 272,000 that the report cites in section 9 are already
recomputed by ``test_the_grading_ledger_no_longer_dies_with_the_runner.py``.
Pinning them twice would mean two files to update for one fact.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import collections
import json
from decimal import Decimal
from pathlib import Path

import pytest

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = Path(__file__).resolve().parents[1]
GRADES = REPO_ROOT / "data/grades"
REPORT = REPO_ROOT / "tasks/rebuilding_grading_task/PR3_COST_BUDGET.md"
SPEC = REPO_ROOT / "tasks/rebuilding_grading_task/302-cost-budget-recheck.md"
SMOKE_FINDINGS = REPO_ROOT / "tasks/rebuilding_grading_task/PR3_SMOKE_FINDINGS.md"
PRICE_TABLE = (
    BATCH_RUNNER / "experiments/execution_envelope/model_price_table.json"
)
PRODUCTION_CONFIG = BATCH_RUNNER / "grading_configs/default_v2_sol_max.yaml"
GATE_CONFIG = BATCH_RUNNER / "grading_configs/default_v2.yaml"

MILLION = Decimal(1_000_000)
SOL = "gpt-5.6-sol"
AUDIO = "gpt-audio-1.5"

#: The acceptance 302 states, in dollars per run.
GATE_USD = Decimal(50)

# ── the runs, by the fingerprint in their filename ────────────────────
PUBLISHED_220 = "src_1c967673eb8081a6"  # 2026-08-19, the published sol run
RERUN_220 = "src_595c7254caf8fbd7"  # 2026-08-23, post-#190
GOLD_185 = "src_79c2f5035c4aa826"  # 2026-08-31, the run 317 priced

#: The two schema-1.0 gpt-5.4 runs the $50 projection was built on and against.
SMOKE_54 = "exp998_smoke_baseline_sample__judge_gpt-5_4__rubric_v2_tools"
FULL_54 = "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools"


def _price(uncached: int, cached: int, output: int, rate: dict) -> Decimal:
    """Bill a token triple at one published tier.

    ``gpt-5.4-pro`` publishes no cached-input meter, so its cached tokens are
    billed at the full input rate -- what a bill without a cache discount
    actually looks like. Every tier used for the sol bounds publishes one, so
    this fallback changes no figure in the report; it only keeps the
    whole-table sweep from having to silently drop three rows.
    """
    cached_rate = rate["cached_input"] if rate.get("cached_input") is not None else rate["input"]
    return (
        Decimal(uncached) / MILLION * Decimal(rate["input"])
        + Decimal(cached) / MILLION * Decimal(cached_rate)
        + Decimal(output) / MILLION * Decimal(rate["output"])
    )


def _token_tiers(meters: dict) -> dict[str, dict]:
    """Every published per-token tier in the table, as ``model:tier``.

    The block also carries provenance strings, per-session execution-environment
    rates, and an ``audio`` entry whose one model resolves to ``None`` because
    no meter for it exists. None of those price a token, and all of them would
    otherwise land in a sweep that claims to be exhaustive.
    """
    return {
        f"{model}:{tier}": rate
        for model, tiers in meters["azure_published_meters"].items()
        if isinstance(tiers, dict)
        for tier, rate in tiers.items()
        if isinstance(rate, dict) and {"input", "output"} <= rate.keys()
    }


def _usd(value: Decimal) -> str:
    """How the report writes a dollar figure, so the two can be compared."""
    return f"${value:,.2f}"


@pytest.fixture(scope="module")
def meters() -> dict:
    return json.loads(PRICE_TABLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sol_meters(meters) -> dict:
    return meters["azure_published_meters"][SOL]


@pytest.fixture(scope="module")
def report() -> str:
    return REPORT.read_text(encoding="utf-8")


def _payload(name: str) -> dict:
    """The one merged grade payload for a run, by fingerprint or by full stem.

    Exact stem wins over substring, because ``..._rubric_v2_tools`` is also a
    prefix of ``..._rubric_v2_tools_tight`` -- a 10-task run that would quietly
    answer in place of the 220-task one.
    """
    found = [
        p
        for p in GRADES.rglob(f"*{name}*.json")
        if "_shards" not in p.parts
    ]
    exact = [p for p in found if p.stem == name]
    found = exact or found
    assert len(found) == 1, f"{name} matched {len(found)} merged payloads"
    return json.loads(found[0].read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def runs() -> dict[str, dict]:
    return {fp: _payload(fp) for fp in (PUBLISHED_220, RERUN_220, GOLD_185)}


@pytest.fixture(scope="module")
def gold_ledger() -> list[dict]:
    found = sorted(GRADES.rglob("*gold_ceiling_185*.cost_ledger.jsonl"))
    assert len(found) == 1
    return [
        json.loads(line)
        for line in found[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sol_totals(payload: dict) -> tuple[int, int, int]:
    """Uncached input, cached input, output -- for the sol model only.

    The two sol-220 runs route nothing to audio, so their summary totals are
    already sol-only; ``test_the_two_sol_220_runs_never_listened_to_anything``
    is what makes that safe to rely on. Gold-185 is read from its ledger
    instead, which resolves the model per call.
    """
    cost = payload["summary"]["cost"]
    cached = cost["total_cached_tokens"]
    return (
        cost["total_input_tokens"] - cached,
        cached,
        cost["total_output_tokens"],
    )


def _sol_totals_from_ledger(rows: list[dict]) -> tuple[int, int, int]:
    sol = [r for r in rows if r.get("resolved_model") == SOL]
    cached = sum(r["cached_input_tokens"] or 0 for r in sol)
    return (
        sum(r["input_tokens"] or 0 for r in sol) - cached,
        cached,
        sum(r["output_tokens"] or 0 for r in sol),
    )


@pytest.fixture(scope="module")
def bounds(runs, gold_ledger, sol_meters) -> dict[str, tuple[Decimal, Decimal]]:
    totals = {
        PUBLISHED_220: _sol_totals(runs[PUBLISHED_220]),
        RERUN_220: _sol_totals(runs[RERUN_220]),
        GOLD_185: _sol_totals_from_ledger(gold_ledger),
    }
    return {
        key: (
            _price(*t, sol_meters["short_context_standard_global"]),
            _price(*t, sol_meters["long_context_standard_global"]),
        )
        for key, t in totals.items()
    }


# ── the answer to 302 ─────────────────────────────────────────────────

def test_the_fifty_dollar_gate_fails_by_between_eight_and_twenty_times(
    bounds, report
):
    """$411.80 at the cheapest reading, $980.84 at the dearest. The gate is $50.

    Stated as a ratio rather than a difference because the gate's problem is
    not that it is slightly tight. No reading of any of the three runs comes
    within an order of magnitude of it.
    """
    low = min(lo for lo, _ in bounds.values())
    high = max(hi for _, hi in bounds.values())

    assert low > GATE_USD and high > GATE_USD
    assert f"{low / GATE_USD:.1f}" == "8.2"
    assert f"{high / GATE_USD:.1f}" == "19.6"
    assert "8.2배에서 19.6배 초과" in report


@pytest.mark.parametrize(
    "fingerprint,tasks,low,high",
    [
        (PUBLISHED_220, 220, "$411.80", "$714.14"),
        (RERUN_220, 220, "$425.92", "$740.54"),
        (GOLD_185, 185, "$549.50", "$980.84"),
    ],
)
def test_each_run_bound_recomputes_and_the_report_states_it(
    bounds, runs, report, fingerprint, tasks, low, high
):
    """Arithmetic on published meters, then the same string in the report.

    The second half is the half that catches drift. Recomputing a number and
    keeping it in a variable proves nothing about the document a reader opens.
    """
    lo, hi = bounds[fingerprint]

    assert runs[fingerprint]["summary"]["total_tasks"] == tasks
    assert _usd(lo) == low
    assert _usd(hi) == high
    assert low in report and high in report


def test_the_gold_bound_is_the_one_317_published(bounds):
    """$549.50 / $980.84 -- the same pair, from the same ledger, unchanged.

    317 is the methodology this report follows, so a divergence here means one
    of the two documents is describing a run the other is not.
    """
    lo, hi = bounds[GOLD_185]
    assert (_usd(lo), _usd(hi)) == ("$549.50", "$980.84")


def test_pricing_the_audio_calls_at_sol_rates_would_move_the_bound(
    runs, gold_ledger, sol_meters
):
    """The 11 cents that say the model split is real rather than tidy.

    Gold-185's summary block totals every model together. Priced whole at sol
    meters it gives $549.61; priced on the sol rows alone, $549.50. The second
    is the published figure. Small enough to miss and structural enough to
    matter -- an audio corpus large enough would move it by a lot more.
    """
    audio = [r for r in gold_ledger if r.get("resolved_model") == AUDIO]
    assert len(audio) == 25
    assert sum(r["input_tokens"] for r in audio) == 11_216
    assert sum(r["output_tokens"] for r in audio) == 1_786

    rate = sol_meters["short_context_standard_global"]
    everything = _price(*_sol_totals(runs[GOLD_185]), rate)
    sol_only = _price(*_sol_totals_from_ledger(gold_ledger), rate)

    assert _usd(everything) == "$549.61"
    assert _usd(sol_only) == "$549.50"
    assert everything > sol_only


def test_the_two_sol_220_runs_never_listened_to_anything(runs):
    """Zero audio items -- which is why their summaries can be priced directly.

    ``unpriced_models`` lists ``gpt-audio-1.5`` on both runs, but that list is
    configured, not observed. Reading it as evidence of audio spend is exactly
    the mistake the previous test guards from the other direction.
    """
    for fingerprint in (PUBLISHED_220, RERUN_220):
        payload = runs[fingerprint]
        modalities = collections.Counter(
            child.get("routing_modality")
            for task in payload["tasks"]
            for item in task["items"]
            for child in [item, *(item.get("child_grades") or [])]
        )
        assert modalities["audio"] == 0
        assert AUDIO in payload["summary"]["cost"]["unpriced_models"]


# ── why the summary can be trusted where no ledger exists ─────────────

def test_the_gold_ledger_sums_to_its_own_summary(runs, gold_ledger):
    """22,528 rows, three totals, no drift. The first of two proofs."""
    cost = runs[GOLD_185]["summary"]["cost"]
    assert len(gold_ledger) == cost["total_judge_calls"] == 22_528
    assert len({r["call_id"] for r in gold_ledger}) == len(gold_ledger)
    assert sum(r["input_tokens"] for r in gold_ledger) == cost["total_input_tokens"]
    assert sum(r["output_tokens"] for r in gold_ledger) == cost["total_output_tokens"]
    assert (
        sum(r["cached_input_tokens"] for r in gold_ledger)
        == cost["total_cached_tokens"]
    )


@pytest.mark.parametrize("fingerprint", [PUBLISHED_220, RERUN_220])
def test_the_ledgerless_runs_sum_from_their_task_rows(runs, fingerprint):
    """The second proof, on the runs that need it.

    Neither sol-220 run has a cost ledger -- the receipt system is younger than
    both -- so the summary is the only record of what they spent. Summing the
    220 per-task token fields is an independent path to the same three numbers,
    and it is the reason section 2 of the report prices them at all.
    """
    payload = runs[fingerprint]
    cost = payload["summary"]["cost"]
    fields = (
        ("total_input_tokens", "judge_input_tokens", "perception_input_tokens"),
        ("total_output_tokens", "judge_output_tokens", "perception_output_tokens"),
        ("total_cached_tokens", "judge_cached_tokens", "perception_cached_tokens"),
    )
    for total, judge, perception in fields:
        summed = sum(
            (task.get(judge) or 0) + (task.get(perception) or 0)
            for task in payload["tasks"]
        )
        assert summed == cost[total], f"{fingerprint}: {total} does not roll up"


# ── the remedy 302 names cannot reach the money ───────────────────────

@pytest.mark.parametrize(
    "fingerprint,share",
    [(PUBLISHED_220, "1.85"), (RERUN_220, "3.39"), (GOLD_185, "3.49")],
)
def test_perception_is_a_few_percent_of_the_bill(
    runs, gold_ledger, bounds, sol_meters, report, fingerprint, share
):
    """Vision and audio together are under 4% everywhere. That is the finding.

    302's stated remedy on failure is to tighten the perception caps or narrow
    the routing. This measures what that remedy is allowed to touch. It is not
    a small effect being called small -- it is an effect an order of magnitude
    below the overspend it was offered to fix.
    """
    rate = sol_meters["short_context_standard_global"]
    if fingerprint == GOLD_185:
        rows = [
            r
            for r in gold_ledger
            if r.get("resolved_model") == SOL and r.get("stage") == "perception"
        ]
        cost = _price(*_sol_totals_from_ledger(rows), rate)
    else:
        c = runs[fingerprint]["summary"]["cost"]
        cost = _price(
            c["perception_input_tokens"] - c["perception_cached_tokens"],
            c["perception_cached_tokens"],
            c["perception_output_tokens"],
            rate,
        )

    low, _ = bounds[fingerprint]
    assert f"{cost / low * 100:.2f}" == share
    assert f"{share}%" in report
    assert cost / low < Decimal("0.04")


def test_deleting_every_perception_call_still_misses_the_gate(
    runs, bounds, sol_meters, report
):
    """$411.80 minus all of it is $404.17, and the gate is still $50.

    The strongest form of the previous test: not "the remedy is small" but
    "the remedy applied perfectly, at zero quality cost, does not pass".
    """
    c = runs[PUBLISHED_220]["summary"]["cost"]
    rate = sol_meters["short_context_standard_global"]
    perception = _price(
        c["perception_input_tokens"] - c["perception_cached_tokens"],
        c["perception_cached_tokens"],
        c["perception_output_tokens"],
        rate,
    )
    low, _ = bounds[PUBLISHED_220]
    remaining = low - perception

    assert _usd(remaining) == "$404.17"
    assert f"{remaining / GATE_USD:.1f}" == "8.1"
    assert "$404.17" in report and "8.1배" in report


def test_the_money_is_in_the_reasoning_tokens(gold_ledger, bounds, sol_meters, report):
    """82.3% of output is reasoning, and that is 35.4% of the bill.

    Gold-185 is the only run whose ledger records reasoning tokens, so this is
    the one place the driver can be named rather than inferred. $194.41 against
    the $19.19 the named remedy could reach: the lever 302 reaches for is about
    a tenth the size of the one it walks past.
    """
    sol = [r for r in gold_ledger if r.get("resolved_model") == SOL]
    reasoning = sum(r["reasoning_tokens"] or 0 for r in sol)
    output = sum(r["output_tokens"] or 0 for r in sol)
    rate = sol_meters["short_context_standard_global"]
    cost = Decimal(reasoning) / MILLION * Decimal(rate["output"])
    low, _ = bounds[GOLD_185]

    assert f"{reasoning / output * 100:.1f}" == "82.3"
    assert _usd(cost) == "$194.41"
    assert f"{cost / low * 100:.1f}" == "35.4"
    for figure in ("82.3%", "$194.41", "35.4%"):
        assert figure in report


def test_the_bill_splits_into_three_pieces_the_report_names(
    gold_ledger, bounds, sol_meters, report
):
    """51.2% uncached input, 5.8% cached input, 43.0% output.

    The decomposition is what makes the recommendation section honest: it says
    where the money is rather than where it would be convenient for it to be.
    The three shares have to add back up to the bound they came from.
    """
    uncached, cached, output = _sol_totals_from_ledger(gold_ledger)
    rate = sol_meters["short_context_standard_global"]
    pieces = {
        "$281.42": Decimal(uncached) / MILLION * Decimal(rate["input"]),
        "$31.75": Decimal(cached) / MILLION * Decimal(rate["cached_input"]),
        "$236.32": Decimal(output) / MILLION * Decimal(rate["output"]),
    }
    low, _ = bounds[GOLD_185]

    for stated, value in pieces.items():
        assert _usd(value) == stated
        assert stated in report
    assert sum(pieces.values()) == low
    assert [f"{v / low * 100:.1f}" for v in pieces.values()] == ["51.2", "5.8", "43.0"]
    assert uncached == 56_284_648


@pytest.mark.parametrize(
    "fingerprint,task_prefix,low,high",
    [
        (GOLD_185, "19403010", "$29.59", "$58.24"),
        (PUBLISHED_220, "47ef842d", "$29.52", "$58.03"),
    ],
)
def test_one_task_alone_can_exceed_the_whole_run_budget(
    runs, sol_meters, report, fingerprint, task_prefix, low, high
):
    """At the long-context reading, a single task costs more than $50.

    Read off the per-task token fields rather than the ledger so the same
    measurement works on the run that has no ledger. The point is the shape of
    the distribution: a gate set at $50 per *run* is below the cost of one
    task at the upper bound, which no cap on perception can reach.
    """
    per_task = []
    for task in runs[fingerprint]["tasks"]:
        totals = (
            (task.get("judge_input_tokens") or 0)
            + (task.get("perception_input_tokens") or 0)
            - (task.get("judge_cached_tokens") or 0)
            - (task.get("perception_cached_tokens") or 0),
            (task.get("judge_cached_tokens") or 0)
            + (task.get("perception_cached_tokens") or 0),
            (task.get("judge_output_tokens") or 0)
            + (task.get("perception_output_tokens") or 0),
        )
        per_task.append(
            (
                _price(*totals, sol_meters["short_context_standard_global"]),
                _price(*totals, sol_meters["long_context_standard_global"]),
                task["task_id"],
            )
        )
    dearest = max(per_task)

    assert dearest[2].startswith(task_prefix)
    assert (_usd(dearest[0]), _usd(dearest[1])) == (low, high)
    assert dearest[1] > GATE_USD
    assert f"{low} ~ {high}" in report


# ── the projection the gate was built on ──────────────────────────────

def test_the_smoke_headline_is_not_reproducible_at_any_published_meter(meters):
    """$0.71 is below the cheapest published gpt-5.4 rate for its own tokens.

    ``PR3_SMOKE_FINDINGS.md`` names no rate, so every published tier is tried.
    The cheapest, ``batch_global``, gives $0.82; the standard tier gives $1.65.
    A projection whose base cannot be recomputed is not a measurement, and that
    is the first half of why the $50 gate has to be rebuilt rather than argued
    with.
    """
    payload = _payload(SMOKE_54)
    cost = payload["summary"]["cost"]
    tiers = {
        name: _price(cost["total_input_tokens"], 0, cost["total_output_tokens"], rate)
        for name, rate in meters["azure_published_meters"]["gpt-5.4"].items()
        if isinstance(rate, dict)
    }

    assert payload["summary"]["total_tasks"] == 3
    assert "$0.71 / 3 tasks" in SMOKE_FINDINGS.read_text(encoding="utf-8")
    assert min(tiers.values()) > Decimal("0.71")
    assert _usd(min(tiers.values())) == "$0.82"
    assert _usd(tiers["standard_global"]) == "$1.65"


def test_the_three_task_sample_understated_the_corpus_by_two_point_eight(
    meters, report
):
    """$0.5490 a task on N=3; $1.5427 a task on the 220 that followed.

    Both held to one convention -- ``standard_global``, all input uncached,
    because schema 1.0 records no cached-token field -- so the ratio is a
    property of the sample and not of two different pricing choices. The smoke
    projected $120.78 for a corpus that came to $339.40.
    """
    rate = meters["azure_published_meters"]["gpt-5.4"]["standard_global"]
    out = {}
    for name in (SMOKE_54, FULL_54):
        payload = _payload(name)
        cost = payload["summary"]["cost"]
        total = _price(
            cost["total_input_tokens"], 0, cost["total_output_tokens"], rate
        )
        out[name] = (total, payload["summary"]["total_tasks"])

    smoke, smoke_n = out[SMOKE_54]
    full, full_n = out[FULL_54]
    projection = smoke / smoke_n * full_n

    assert _usd(projection) == "$120.78"
    assert _usd(full) == "$339.40"
    assert f"{(full / full_n) / (smoke / smoke_n):.2f}" == "2.81"
    for figure in ("$120.78", "$339.40", "2.81배"):
        assert figure in report


def test_the_full_gpt_5_4_run_records_zero_where_it_means_unknown(report):
    """220 tasks, 107,844,571 input tokens, ``estimated_cost_usd: 0.0``.

    The run that would have answered 302 in 2026-06 exists and was never
    priced. Its schema-1.0 summary has no cached-token field, so it bounds at
    $96.75 to $339.40 rather than settling -- and it writes the zero that
    section 10 of the report is about.
    """
    payload = _payload(FULL_54)
    cost = payload["summary"]["cost"]

    assert payload["summary"]["total_tasks"] == 220
    assert cost["total_input_tokens"] == 107_844_571
    assert cost["total_output_tokens"] == 4_652_556
    assert cost["estimated_cost_usd"] == 0.0
    assert "total_cached_tokens" not in cost
    assert "$96.75" in report and "$339.40" in report


# ── the gate against the pipeline that actually runs ──────────────────

def test_the_gate_describes_a_configuration_production_left_behind(report):
    """cap 5 against cap 112, medium against max, gpt-5.4 against gpt-5.6-sol.

    Read out of the configs rather than asserted as constants, so the day
    production changes again this says so instead of going quietly stale.
    """
    spec = SPEC.read_text(encoding="utf-8")
    production = yaml.safe_load(PRODUCTION_CONFIG.read_text(encoding="utf-8"))
    gate_era = yaml.safe_load(GATE_CONFIG.read_text(encoding="utf-8"))

    assert "per-run cost < $50" in spec
    assert "per task cap 5" in spec

    judge = production["judge"]
    assert judge["model"] == SOL
    assert judge["reasoning"]["effort"] == "max"
    assert judge["perception"]["visual"]["call_cap_per_task"] == 112
    assert judge["perception"]["audio"]["call_cap_per_task"] == 32

    assert gate_era["judge"]["model"] == "gpt-5.4"
    assert gate_era["judge"]["reasoning"]["effort"] == "medium"

    workflow = (REPO_ROOT / ".github/workflows/grade-run.yml").read_text(
        encoding="utf-8"
    )
    assert 'default: "default_v2_sol_max.yaml"' in workflow
    assert "call_cap_per_task: **112**" in report


def test_the_knobs_the_smoke_proposed_tightening_are_still_at_their_originals(
    report,
):
    """``max_iterations: 10`` and ``per_item_call_cap: 8``, unchanged.

    The report's recommendation table says these are untouched. If someone
    tightens them the sentence stops being true, and -- more to the point --
    the grader fingerprint moves and every bound above describes a pipeline
    that no longer exists.
    """
    tools = yaml.safe_load(PRODUCTION_CONFIG.read_text(encoding="utf-8"))["judge"][
        "tools"
    ]["read_deliverable"]

    assert tools["max_iterations"] == 10
    assert tools["per_item_call_cap"] == 8
    assert "`max_iterations: 10`, `per_item_call_cap: 8`" in report


def test_only_the_nano_tier_puts_this_workload_under_the_gate(meters, report):
    """Twenty of twenty-one published meters miss $50. The one that clears is nano.

    A rate substitution, not a forecast: it holds the token count fixed, and a
    different model would not produce these tokens -- 82.3% of the output is
    reasoning at ``effort: max``, which is a property of the judge, not of the
    workload. What survives that caveat is the shape. There is a way to satisfy
    the gate by price alone, and it is to drop the judge two classes to
    ``gpt-5.4-nano``, whose rubric-grading quality this repository has never
    measured. That is a different benchmark, not a tightened cap.

    Written as "exactly one" rather than "none" because the first draft of this
    report claimed no published meter reached $50, having swept the table
    without nano in it. The count is asserted so the sweep cannot go partial
    again without saying so.
    """
    uncached, cached, output = _sol_totals(_payload(PUBLISHED_220))
    priced = {
        name: _price(uncached, cached, output, rate)
        for name, rate in _token_tiers(meters).items()
    }
    under = {name: value for name, value in priced.items() if value < GATE_USD}

    assert len(priced) == 21
    assert list(under) == ["gpt-5.4-nano:standard_global"]
    assert _usd(under["gpt-5.4-nano:standard_global"]) == "$16.84"
    assert _usd(priced["gpt-5.4-mini:standard_global"]) == "$61.77"
    assert _usd(priced["gpt-5.4:standard_global"]) == "$205.90"
    assert _usd(priced["gpt-5.4:batch_global"]) == "$103.20"
    assert _usd(max(priced.values())) == "$6,998.66"

    for figure in ("$16.84", "$61.77", "$205.90", "$103.20", "$6,998.66"):
        assert figure in report
    assert "21개 중 20개가 $50을 넘는다" in report


def test_the_published_bill_covers_194_tasks_not_220(runs, sol_meters, report):
    """26 tasks never reached a judge call, so they cost nothing.

    Which means the $411.80 is not a 220-task price, and fixing the selector
    raises it rather than lowering it -- the rerun, with five of those tasks
    revived by #190, costs more. A cost report that quietly divided by 220
    would understate the per-task figure by 13%.
    """
    payload = runs[PUBLISHED_220]
    rate = sol_meters["short_context_standard_global"]
    free = [
        task
        for task in payload["tasks"]
        if _price(
            (task.get("judge_input_tokens") or 0)
            + (task.get("perception_input_tokens") or 0)
            - (task.get("judge_cached_tokens") or 0)
            - (task.get("perception_cached_tokens") or 0),
            (task.get("judge_cached_tokens") or 0)
            + (task.get("perception_cached_tokens") or 0),
            (task.get("judge_output_tokens") or 0)
            + (task.get("perception_output_tokens") or 0),
            rate,
        )
        == 0
    ]

    assert len(free) == 26
    assert collections.Counter(t["selection_status"] for t in free) == {
        "wrong_format_primary": 20,
        "selection_error": 5,
        "no_generated_candidate": 1,
    }
    assert len(payload["tasks"]) - len(free) == 194
    assert "194과제" in report


# ── the figures are bounds, and stay bounds ───────────────────────────

def test_the_cache_write_meter_exists_and_still_cannot_be_applied(
    gold_ledger, sol_meters, report
):
    """+$351.78 on gold-185, and no way to know how much of it was real.

    ``gpt-5.6-sol`` bills cache *writes*, which ``gpt-5.4`` does not. The rate
    is published; the write-token count is not recorded on any receipt. So the
    third open axis in section 9 is bounded from above -- every uncached input
    token treated as a write -- and left there. Recording the ceiling is the
    honest form of "excluded": it says how wrong the exclusion can be.
    """
    uncached, _, _ = _sol_totals_from_ledger(gold_ledger)
    rate = sol_meters["short_context_standard_global"]
    ceiling = Decimal(uncached) / MILLION * Decimal(rate["cache_write"])

    assert rate["cache_write"] == "6.25"
    assert not any("cache_write_tokens" in row for row in gold_ledger)
    assert _usd(ceiling) == "$351.78"
    assert "$351.78" in report


def test_none_of_this_gave_the_model_a_price(meters, runs):
    """No dollar value anywhere: not in the table, not on any of the runs.

    The report's whole method depends on ``gpt-5.6-sol`` staying unpriced --
    the moment a nearest-match rate is written into ``providers``, every figure
    above silently becomes an assertion about a price nobody published.
    """
    assert SOL not in meters.get("providers", {}).get("azure", {})
    assert f"azure:{SOL}" in meters["models_deliberately_not_priced"]
    assert f"azure:{AUDIO}" in meters["models_deliberately_not_priced"]

    for fingerprint, payload in runs.items():
        cost = payload["summary"]["cost"]
        assert cost["estimated_cost_usd"] is None, (
            f"{fingerprint} now carries a price; a null there is the difference "
            "between 'nobody can say' and 'it was free'"
        )
        assert cost["pricing_complete"] is False
        assert SOL in cost["unpriced_models"]
