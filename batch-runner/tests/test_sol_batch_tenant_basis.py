"""The tenant_observed_20261126 booking basis, and the list_long_context basis every earlier run keeps.

Runs registered from 2026-11-26 book USD at the rates Azure billed this
tenant (observed 4.00 / 0.40 / 5.00 / 20.00 per 1M, booked x1.05) up to
187,594 request input tokens, and at today's list_long_context amount above
that or when the request's size is unknown. exp035 parity and exp036 to
exp040 stay on list_long_context for good, so no committed journal or
published figure moves.

Model-free and offline. Sockets are blocked; the one end-to-end test runs the
pinned Codex binary against a loopback server, as test_sol_batch_controls
does, and is skipped without it.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import os
import re
import socket
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

import sol_batch_controls as controls
import sol_batch_grading as grading
from core import codex_runner
from core.codex_cost import CodexTokenTotals, settle_codex_turn
from core.codex_runner import CodexAgentRunner, TurnObservation
from core.codex_runtime_config import LoopbackCodexProvider, requested_model_config_overrides
from core.cost_receipts import STATE_ABANDONED, STATE_REFUSED, STATE_RESERVED, STATE_SETTLED
from core.cost_receipts import STAGE_GRADING

from .test_codex_runtime_end_to_end import _RUNTIME_PROBLEM, ScriptedResponses, _sse, _usage, says, says_run_this
from .test_sol_batch_controls import (  # noqa: F401 - fixtures
    AUTH_ARGV, SETTLED, TASKS, _executor, _install_kwargs, _last, _record, _scripted_parent, _settings,
    fixed_auth, ledgers, unit_runner,
)
from .test_sol_batch_grading import (  # noqa: F401 - fixtures
    INFERENCE_SHA, KWARGS, SETTLED_CALL, FakeResponses, _input_paths, _published, _records, _seed, _task_row,
    _write_journal, admitted,
)

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER.parent
TENANT = controls.BASIS_TENANT_20261126
LIST = controls.BASIS_LIST_LONG
#: sha256 of batch-runner/experiments/execution_envelope/sol_batch_tenant_rates_20261126.json.
TENANT_RATES_SHA256 = "11bf182dfb0d9dfa720a788d87e9dc4b89500ed7fae8381e5d7a791cd8c976e2"
LEGACY_RUNS = {"exp036_sol_fixed5", "exp037_sol_first25", "exp038_sol_rest195", "exp039_sol_next98",
               "exp040_sol_last97"}
LEGACY_APPROVALS = {grading.EXP036_SOL_BATCH, grading.EXP035_PARITY, grading.EXP037_FIRST25,
                    grading.EXP038_REST195, grading.EXP039_NEXT98, grading.EXP040_LAST97}
JOURNALS = REPO_ROOT / "data/grades/_combined_usd"
BOUND_LEDGER = REPO_ROOT / (
    "data/grades/exp039_sol_next98__judge_gpt-5_6-sol__exp039_v2_sol_max__cfg_b1d01ade7e210fe7__rubric_"
    "11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_ea9ea042157011c6fd2a4adaf44ed0c5e69a4d06__src_"
    "f5fce752e314d028__v2.2.cost_ledger.jsonl")
BOUND_JOURNAL = JOURNALS / "exp039_sol_next98/run-45492421884-1.combined_usd.jsonl"
BOUND = 187_594
#: Committed gpt-5.6-sol grading settles when the basis was designed; exp040's
#: later chunks only add to it.
SOL_SETTLES_AT_DESIGN = 23_144


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in Sol booking basis tests")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


def _tenant() -> controls.SolTenantPricing:
    return controls.load_sol_tenant_pricing()


def _exp036_on(basis: str) -> controls.SolRun:
    return dataclasses.replace(controls.RUNS["exp036_sol_fixed5"], booking_basis=basis)


def _patch_exp036(monkeypatch, basis: str) -> controls.SolRun:
    run = _exp036_on(basis)
    monkeypatch.setattr(controls, "RUNS", MappingProxyType({**controls.RUNS, run.experiment_id: run}))
    return run


def _tenant_approval(monkeypatch) -> grading.Approval:
    """exp036's approval on the tenant basis, registered in place of the list one."""
    approval = dataclasses.replace(grading.EXP036_SOL_BATCH, booking_basis=TENANT)
    monkeypatch.setattr(grading, "APPROVALS", tuple(
        approval if entry is grading.EXP036_SOL_BATCH else entry for entry in grading.APPROVALS))
    return approval


def _price(i, c, o, *, rep=None, size=None, rates=None, reasoning=None):
    return controls.booked_price_usd(
        input_tokens=i, cached_input_tokens=c, output_tokens=o, reasoning_tokens=reasoning,
        reported_cache_write_tokens=rep, request_input_tokens=size,
        rates=_tenant() if rates is None else rates)


# -- 1. the earlier runs stay on the list basis --------------------------------


def test_runs_registered_before_the_tenant_basis_stay_on_the_list_basis():
    assert controls.BOOKING_BASES == grading.BOOKING_BASES == frozenset({LIST, TENANT})
    assert (controls.BASIS_LIST_LONG, controls.BASIS_TENANT_20261126) == (
        grading.BASIS_LIST_LONG, grading.BASIS_TENANT_20261126) == ("list_long_context", "tenant_observed_20261126")
    assert LEGACY_RUNS <= set(controls.RUNS)
    for name, run in controls.RUNS.items():
        if name in LEGACY_RUNS:
            assert run.booking_basis == LIST, name
        else:
            # A run registered from now on books on a basis other than list.
            assert run.booking_basis != LIST and run.booking_basis in controls.BOOKING_BASES, name
    assert LEGACY_APPROVALS <= set(grading.APPROVALS)
    for approval in grading.APPROVALS:
        if approval in LEGACY_APPROVALS:
            assert approval.booking_basis == LIST, approval.experiment_id
        else:
            assert approval.booking_basis != LIST and approval.booking_basis in grading.BOOKING_BASES
    for approval in grading.APPROVALS:
        if approval.solve_seed == grading.SOLVE_SEED_SOL_BATCH:
            assert controls.RUNS[approval.experiment_id].booking_basis == approval.booking_basis
    # The defaults, so no registry entry had to be edited.
    assert controls.SolRun.__dataclass_fields__["booking_basis"].default == LIST
    assert grading.Approval.__dataclass_fields__["booking_basis"].default == LIST
    assert grading.Seed.__dataclass_fields__["booking_basis"].default == LIST


# -- 2. the held record ----------------------------------------------------------


def test_the_tenant_rates_record_is_held_and_reads_as_billed():
    raw = controls.TENANT_RATES_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == controls.TENANT_RATES_SHA256 == TENANT_RATES_SHA256
    assert controls.TENANT_RATES_PATH == REPO_ROOT / controls.TENANT_RATES_RELATIVE
    assert raw.endswith(b"\n") and b"\r" not in raw
    raw.decode("utf-8")

    pricing = _tenant()
    assert pricing.basis == TENANT and pricing.margin == Decimal("1.05")
    assert pricing.short_through_input_tokens == BOUND
    kinds = ("input", "cached_input", "cache_write", "output")
    assert [getattr(pricing.observed, kind) for kind in kinds] == [
        Decimal("4.00"), Decimal("0.40"), Decimal("5.00"), Decimal("20.00")]
    assert [getattr(pricing.booked, kind) for kind in kinds] == [
        Decimal("4.20"), Decimal("0.42"), Decimal("5.25"), Decimal("21.00")]
    assert pricing.fallback == controls.load_sol_list_rates()
    assert (pricing.source_relative, pricing.source_sha256, pricing.retrieved) == (
        controls.TENANT_RATES_RELATIVE, TENANT_RATES_SHA256, "2026-11-26T00:55Z")

    record = json.loads(raw)
    observation = record["observation"]
    for meter in observation["meters"]:
        rate = Decimal(meter["cost_usd"]) / Decimal(meter["quantity_million_tokens"])
        assert rate.quantize(Decimal("0.01")) == getattr(pricing.observed, meter["rate_kind"])
    assert sum(Decimal(meter["cost_usd"]) for meter in observation["meters"]) == Decimal("778.72")
    by_kind = {meter["rate_kind"]: Decimal(meter["quantity_million_tokens"]) for meter in observation["meters"]}
    assert by_kind["input"] + by_kind["cache_write"] == Decimal("70.209712")
    assert observation["long_context_meters_billed"] == observation["data_zone_meters_billed"] == []

    # A grade's checkout verifies it: under a GRADING_INPUT_PATHS entry in both jobs.
    for job, step in (("grade-dry-run", "Verify read-only checkout and input files"),
                      ("grade", "Verify checked out main and input files")):
        entries = _input_paths(job, step)
        assert any(controls.TENANT_RATES_RELATIVE == entry or controls.TENANT_RATES_RELATIVE.startswith(entry + "/")
                   for entry in entries), job

    # The #795 table is untouched, and still prices no Sol provider.
    table = (REPO_ROOT / "batch-runner/experiments/execution_envelope/model_price_table.json").read_bytes()
    assert hashlib.sha256(table).hexdigest() == controls.PRICE_TABLE_SHA256 == (
        "b01b384c532b1457804e3a77713d2b079b06b363a5ff3b8b939fe65a4cb30b4e")
    assert "azure:gpt-5.6-sol" not in json.loads(table)["providers"]

    # Nothing that names the subscription, the tenant or an endpoint.
    text = raw.decode("utf-8")
    assert not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", text)
    assert "subscriptions/" not in text and ".azure.com" not in text and "https://" not in text


# -- 3. the bound ------------------------------------------------------------------


def _sol_ledger_row(row: dict) -> bool:
    return row.get("record_type") == "call" and "gpt-5.6-sol" in (
        row.get("resolved_model"), row.get("deployment"), row.get("requested_model"))


def test_the_bound_is_a_request_billed_on_a_short_meter():
    record = json.loads(controls.TENANT_RATES_PATH.read_text(encoding="utf-8"))
    evidence = record["bound_evidence"]
    assert REPO_ROOT / evidence["cost_ledger"] == BOUND_LEDGER
    assert REPO_ROOT / evidence["journal"] == BOUND_JOURNAL
    row = json.loads(BOUND_LEDGER.read_text(encoding="utf-8").splitlines()[5138 - 1])
    assert row["call_id"] == evidence["call_id"]
    assert (row["input_tokens"], row["cached_input_tokens"]) == (BOUND, 94_347) == (
        evidence["input_tokens"], evidence["cached_input_tokens"])
    assert _sol_ledger_row(row) and row["state"] == "settled"
    assert row["concluded_at"] == evidence["concluded_at"] and row["concluded_at"].startswith("2026-11-24")

    lines = [json.loads(line) for line in BOUND_JOURNAL.read_text(encoding="utf-8").splitlines()]
    settle = lines[evidence["journal_seq"]]
    assert settle["seq"] == 376 and settle["event"] == "settle" and settle["input_tokens"] == BOUND
    reserve = next(line for line in lines if line.get("event") == "reserve" and line["ticket"] == settle["ticket"])
    assert reserve["model"] == "gpt-5.6-sol"

    # Every committed Sol request the bill for 11-12 to 11-24 covers is at or below it.
    largest = 0
    for path in sorted((REPO_ROOT / "data/grades").rglob("*.cost_ledger.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            day = str(entry.get("concluded_at") or "")[:10]
            if (_sol_ledger_row(entry) and "2026-11-12" <= day <= "2026-11-24"
                    and type(entry.get("input_tokens")) is int):
                largest = max(largest, entry["input_tokens"])
    assert largest == BOUND


# -- 4. a record that is not the held file -----------------------------------------


def _repinned(tmp_path: Path, monkeypatch, change=None) -> Path:
    record = json.loads(controls.TENANT_RATES_PATH.read_text(encoding="utf-8"))
    if change is not None:
        change(record)
    path = tmp_path / "rates.json"
    data = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    monkeypatch.setattr(controls, "TENANT_RATES_SHA256", hashlib.sha256(data).hexdigest())
    return path


def _refused(path: Path) -> str:
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.load_sol_tenant_pricing(path)
    return str(refused.value)


def test_a_tenant_rates_record_that_is_not_the_held_file_refuses(tmp_path, monkeypatch):
    raw = controls.TENANT_RATES_PATH.read_bytes()
    appended = tmp_path / "appended.json"
    appended.write_bytes(raw + b" ")
    linked = tmp_path / "linked.json"
    linked.symlink_to(controls.TENANT_RATES_PATH)
    copy = tmp_path / "copy.json"
    copy.write_bytes(raw)
    assert controls.load_sol_tenant_pricing(copy).booked == _tenant().booked
    os.link(copy, tmp_path / "second-name.json")
    for path in (appended, linked, copy, tmp_path / "missing.json"):
        assert _refused(path) == "sol_batch_tenant_rates_unverified", path.name

    # A re-pinned copy loads only while its figures agree with themselves.
    assert controls.load_sol_tenant_pricing(_repinned(tmp_path, monkeypatch)).booked == _tenant().booked

    def booked_off(record):
        record["booked_usd_per_million"]["output"] = "21.01"

    def above_short_list(record):
        record["observed_usd_per_million"]["output"] = "30.01"
        record["booked_usd_per_million"]["output"] = "31.5105"

    def long_meter(record):
        record["observation"]["meters"][3]["meter_name"] = "5.6 sol LongCo Opt Std Gl 1M Tokens"

    def long_billed(record):
        record["observation"]["long_context_meters_billed"] = ["5.6 sol LongCo Opt Std Gl 1M Tokens"]

    def window_bound(record):
        record["short_tier_through_request_input_tokens"] = 1_050_000

    for change in (booked_off, above_short_list, long_meter, long_billed, window_bound):
        assert _refused(_repinned(tmp_path, monkeypatch, change)) == "sol_batch_tenant_rates_unverified", (
            change.__name__)
    monkeypatch.setattr(controls, "TENANT_RATES_SHA256", TENANT_RATES_SHA256)

    for basis in ("x", None, 7):
        with pytest.raises(controls.SolBatchControlsRefused) as refused:
            controls.load_booking_rates(basis)
        assert str(refused.value) == "sol_batch_booking_basis_unknown"
        with pytest.raises(controls.SolBatchControlsRefused):
            controls.booking_source_sha256(basis)

    # The list basis never reads the tenant record.
    monkeypatch.setattr(controls, "TENANT_RATES_PATH", tmp_path / "missing.json")
    assert controls.load_booking_rates(LIST) == controls.load_sol_list_rates()
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.load_booking_rates(TENANT)
    assert str(refused.value) == "sol_batch_tenant_rates_unverified"


# -- 5. the tenant price -------------------------------------------------------------


def test_tenant_price_books_uncached_input_once_and_tiers_on_request_size():
    # 60k uncached x 5.25 (once) + 40k cached x 0.42 + 2k out x 21.00, per 1M.
    assert _price(100_000, 40_000, 2_000, size=60_000) == Decimal("0.37380000")
    assert _price(100_000, 40_000, 2_000, rep=70_000, size=60_000) == Decimal("0.42630000")
    # Unknown size: exactly the list_long_context amount.
    assert _price(100_000, 40_000, 2_000) == Decimal("1.48000000")
    assert _price(100_000, 40_000, 2_000, rep=70_000) == Decimal("1.60500000")
    assert _price(100_000, 40_000, 2_000, size=BOUND) == Decimal("0.37380000")
    assert _price(100_000, 40_000, 2_000, size=BOUND + 1) == Decimal("1.48000000")
    assert _price(100_000, 40_000, 2_000, size=True) == Decimal("1.48000000")
    assert controls.booked_tier(_tenant(), BOUND) == "short"
    assert controls.booked_tier(_tenant(), BOUND + 1) == controls.booked_tier(_tenant(), None) == "fallback"
    assert controls.booked_tier(controls.load_sol_list_rates(), 10) == "list"

    # The real bound row, and one token past it.
    assert _price(BOUND, 94_347, 907, size=BOUND) == Decimal("0.54821949")
    assert _price(BOUND + 1, 94_347, 907, size=BOUND + 1) == Decimal("2.23324200")

    priced = {_price(100_000, 40_000, 2_000, size=60_000, reasoning=reasoning) for reasoning in (None, 0, 500, 2_000)}
    assert priced == {Decimal("0.37380000")}
    assert _price(10, None, 0, size=10) == _price(10, 0, 0, size=10) == Decimal("0.00005250")
    for counts in ((10, 20, 0), (10, 0, True), (True, 0, 0), (-1, 0, 0)):
        assert _price(*counts, size=10) is None
    assert _price(100_000, 0, 10, reasoning=11, size=10) is None

    # On the list basis the size changes nothing.
    rates = controls.load_sol_list_rates()
    assert _price(100_000, 40_000, 2_000, size=60_000, rates=rates) == Decimal("1.48000000")


# -- 6. refused requests and in-flight bounds ----------------------------------------


@pytest.mark.parametrize("last, bound", [
    (None, Decimal("29.38500000")),
    # 161k grown input on the short tier: 161k x 5.25 + 128k x 21.00 per 1M.
    (_last(60_000, 50_000, 1_000), Decimal("3.53325000")),
    (_last(600_000, 590_000, 2_000), Decimal("21.55500000")),
    # Grown to exactly the bound, and one thousand past it.
    (_last(86_594, 0, 1_000), Decimal("3.67286850")),
    (_last(87_594, 0, 1_000), Decimal("10.00336500")),
])
def test_refused_and_in_flight_bookings_on_the_tenant_basis(last, bound):
    tenant = _tenant()
    rates = controls.load_sol_list_rates()
    assert controls.refused_request_usd(tenant) == Decimal("3.02400000")
    assert controls.refused_request_usd(rates) == controls.REFUSED_REQUEST_USD == controls.list_price_usd(
        input_tokens=64_000, cached_input_tokens=0, output_tokens=128_000, rates=rates) == Decimal("7.20")

    assert controls.in_flight_bound_usd(last, rates=tenant) == bound
    assert controls.in_flight_bound_usd(None, rates=rates) == Decimal("29.38500000")
    assert controls.in_flight_bound_usd(_last(60_000, 50_000, 1_000), rates=rates) == Decimal("9.38250000")
    if last is not None:
        grown = min(controls.CATALOG_SOL_MAX_CONTEXT_WINDOW,
                    last.input_tokens + last.output_tokens + controls.IN_FLIGHT_TOOL_OUTPUT_TOKENS)
        cold = _price(grown, 0, controls.IN_FLIGHT_OUTPUT_TOKENS, size=grown)
        warm = _price(grown, min(last.cached_input_tokens, grown), controls.IN_FLIGHT_OUTPUT_TOKENS, size=grown)
        assert bound >= cold >= warm


# -- 7. book_row ------------------------------------------------------------------------


@pytest.mark.parametrize("row, evidence, booked", [
    (SETTLED, {"tier_request_input_tokens": 60_000}, (Decimal("0.37380000"), "settled")),
    (SETTLED, {"tier_request_input_tokens": 60_000, "cache_write_input_tokens": 70_000},
     (Decimal("0.42630000"), "settled")),
    (SETTLED, None, (Decimal("1.48000000"), "settled")),
    (SETTLED, {"tier_request_input_tokens": None}, (Decimal("1.48000000"), "settled")),
    ({"state": STATE_REFUSED}, None, (Decimal("3.02400000"), "refused_request")),
    ({"state": STATE_RESERVED}, {"error_category": "rate_limited", "items_seen": 0},
     (Decimal("3.02400000"), "rate_limited_first_request")),
    ({"state": STATE_RESERVED}, None, (Decimal("51"), "usage_unreported")),
    (dict(SETTLED, output_tokens=None), {"tier_request_input_tokens": 60_000},
     (Decimal("51"), "settled_without_usage")),
    ({"state": STATE_ABANDONED}, None, (Decimal(0), "abandoned")),
    (SETTLED, {"tier_request_input_tokens": 60_000, "in_flight_usd": Decimal("3.53325000")},
     (Decimal("3.90705000"), "settled_partial")),
    # Sub-agent threads book their bound on top, whatever the row books.
    (SETTLED, {"tier_request_input_tokens": None, "sub_agent_usd": Decimal("51")},
     (Decimal("52.48000000"), "settled_with_sub_agents")),
    (SETTLED, {"in_flight_usd": Decimal("3.53325000"), "sub_agent_usd": Decimal("102")},
     (Decimal("107.01325000"), "settled_partial_with_sub_agents")),
    ({"state": STATE_RESERVED}, {"sub_agent_usd": Decimal("51")}, (Decimal("102"), "usage_unreported_with_sub_agents")),
    ({"state": STATE_ABANDONED}, {"sub_agent_usd": Decimal("51")}, (Decimal(0), "abandoned")),
])
def test_book_row_on_the_tenant_basis(row, evidence, booked):
    assert controls.book_row(row, rates=_tenant(), reserve=Decimal("51"), evidence=evidence) == booked


# -- 8. the request-size observer ----------------------------------------------------


def _update(size: Any, total: Any) -> SimpleNamespace:
    """One thread/tokenUsage/updated: ``size`` is last.input_tokens, ``total`` the thread's total."""
    return SimpleNamespace(method="thread/tokenUsage/updated", payload=SimpleNamespace(
        token_usage=SimpleNamespace(last=SimpleNamespace(input_tokens=size),
                                    total=SimpleNamespace(input_tokens=total))))


def _updates(sizes: list) -> list:
    """One update per request, each total the running sum, as Codex 0.147.0 sends them."""
    events, total = [], 0
    for size in sizes:
        total += size if isinstance(size, int) else 0
        events.append(_update(size, total))
    return events


def _sub_agent_item(item_type: str, item_id: str, **fields: Any) -> SimpleNamespace:
    """An item/started event as the parent stream carries it: payload.item.root is the thread item."""
    return SimpleNamespace(method="item/started", payload=SimpleNamespace(
        item=SimpleNamespace(root=SimpleNamespace(type=item_type, id=item_id, **fields))))


class _FakeStream:
    def __init__(self, events: list) -> None:
        self.events = events
        self.closed = False
        self.extra = "kept"

    def __iter__(self):
        return iter(self.events)

    def close(self) -> str:
        self.closed = True
        return "closed"


class _FakeHandle:
    id = "turn-1"

    def __init__(self, events: list) -> None:
        self.events = events
        self.interrupted = False
        self.streams: list[_FakeStream] = []

    def stream(self) -> _FakeStream:
        self.streams.append(_FakeStream(self.events))
        return self.streams[-1]

    def interrupt(self) -> str:
        self.interrupted = True
        return "interrupted"


class _Hostile:
    @property
    def method(self):
        raise RuntimeError("an event that cannot be read")


def _observe(seen: list, row_input: Any = 400_000) -> tuple[controls._RequestSizes, int | None]:
    """``seen``: request sizes (running totals added) or ready-made events."""
    events = seen if seen and not isinstance(seen[0], (int, type(None))) else _updates(seen)
    sizes = controls._RequestSizes()
    turn = controls._SizedTurn(_FakeHandle(events), sizes)
    list(turn.stream())
    return sizes, controls.tier_request_input_tokens(sizes, row_input)


def test_the_request_size_observer():
    other = SimpleNamespace(method="item/completed", payload=None)
    hostile = _Hostile()
    no_usage = SimpleNamespace(method="thread/tokenUsage/updated", payload=SimpleNamespace(token_usage=None))
    events = [other, _update(50_000, 50_000), hostile, no_usage, _update(60_000, 110_000)]
    handle = _FakeHandle(events)
    sizes = controls._RequestSizes()
    turn = controls._SizedTurn(handle, sizes)
    assert (turn.id, turn.interrupt()) == ("turn-1", "interrupted") and handle.interrupted
    stream = turn.stream()
    assert list(stream) == events and all(a is b for a, b in zip(list(turn.stream()), events))
    assert stream.extra == "kept" and stream.close() == "closed" and handle.streams[0].closed
    assert sizes.unreadable is True
    assert controls.tier_request_input_tokens(sizes, 400_000) is None

    sizes, size = _observe([50_000, 120_000, 180_000])
    assert size == 180_000
    assert sizes.as_record() == {"updates": 3, "repeats": 0, "peak": 180_000, "observed_sum": 350_000,
                                 "unobserved_input_tokens": 0, "shrank": False, "unreadable": False,
                                 "sub_agent_items": 0, "sub_agent_threads": 0}
    sizes, size = _observe([50_000, 20_000])
    assert sizes.shrank is True and size is None
    sizes, size = _observe([50_000, None])
    assert sizes.unreadable is True and size is None
    assert _observe([])[1] is None and controls.tier_request_input_tokens(None, 400_000) is None
    # More observed than the row holds, sizes never shrinking: the sizes do not describe this row.
    assert _observe([200_000, 300_000])[1] is None
    assert _observe([300_000, 200_000])[1] is None
    assert _observe([50_000, 60_000], row_input=None)[1] is None
    # Every request the observer missed is bounded by the unobserved remainder.
    assert _observe([50_000, 60_000])[1] == 290_000


def test_the_observer_skips_a_re_sent_update_and_bounds_a_missed_request():
    # Codex 0.147.0 re-sends the previous update when a request fails, is cut
    # off or reports no usage: the same last, an unchanged total.
    sizes, size = _observe([_update(11, 11), _update(11, 11)], row_input=11)
    assert (size, sizes.updates, sizes.repeats, sizes.observed_sum) == (11, 2, 1, 11)
    sizes, size = _observe([_update(11, 11), _update(11, 11), _update(25, 36), _update(40, 76)], row_input=76)
    assert (size, sizes.repeats, sizes.observed_sum, sizes.unobserved) == (40, 1, 76, 0)
    # A total that grew by more than last: a request the observer never saw,
    # bounded by the excess (here 150k, above the 120k peak).
    sizes, size = _observe([_update(50_000, 50_000), _update(120_000, 320_000)], row_input=400_000)
    assert (size, sizes.unobserved, sizes.observed_sum) == (150_000, 150_000, 170_000)
    # Ditto with the excess larger than the row allows.
    assert _observe([_update(50_000, 50_000), _update(120_000, 420_000)], row_input=400_000)[1] is None
    # A total that fell, or grew by less than last, cannot be read.
    for events in ([_update(50_000, 50_000), _update(60_000, 40_000)],
                   [_update(50_000, 50_000), _update(60_000, 100_000)],
                   [_update(50_000, 40_000)],
                   [_update(50_000, None)]):
        sizes, size = _observe(events)
        assert sizes.unreadable is True and size is None
    # The same size with a grown total is a new request, not a repeat.
    sizes, size = _observe([_update(50_000, 50_000), _update(50_000, 100_000)], row_input=100_000)
    assert (size, sizes.repeats, sizes.observed_sum) == (50_000, 0, 100_000)


def test_a_turn_that_used_sub_agents_has_no_size():
    spawn = _sub_agent_item("collabAgentToolCall", "call-1", tool="spawnAgent", receiver_thread_ids=["child-a"])
    started = _sub_agent_item("subAgentActivity", "act-1", agent_thread_id="child-a", kind="started")
    again = SimpleNamespace(method="item/completed", payload=started.payload)
    other = _sub_agent_item("agentMessage", "msg-1")
    sizes, size = _observe([_update(150_000, 150_000), spawn, started, again, other,
                            _update(160_000, 310_000)], row_input=310_000)
    assert size is None
    assert (sizes.sub_agent_items, sizes.sub_agent_threads, sizes.peak) == (2, 1, 160_000)
    second = _sub_agent_item("subAgentActivity", "act-2", agent_thread_id="child-b")
    sizes, _ = _observe([_update(10, 10), started, second], row_input=10)
    assert (sizes.sub_agent_items, sizes.sub_agent_threads) == (2, 2)
    # An item that names no thread still counts one.
    sizes, _ = _observe([_update(10, 10), _sub_agent_item("collabAgentToolCall", "call-9")], row_input=10)
    assert (sizes.sub_agent_items, sizes.sub_agent_threads) == (1, 1)
    # Waiting on or closing an agent sends no request of its own (the SDK's CollabAgentTool enum).
    wait = _sub_agent_item("collabAgentToolCall", "call-w", tool=SimpleNamespace(value="wait"),
                           receiver_thread_ids=[])
    close = _sub_agent_item("collabAgentToolCall", "call-c", tool="closeAgent")
    sizes, size = _observe([_update(10, 10), wait, close], row_input=10)
    assert (sizes.sub_agent_items, size) == (0, 10)
    # Only the tenant basis books a bound for them: one attempt reserve per thread.
    sizes, _ = _observe([_update(10, 10), started, second], row_input=10)
    assert controls.sub_agent_bound_usd(sizes, rates=_tenant(), reserve=Decimal("51")) == Decimal("102")
    assert controls.sub_agent_bound_usd(sizes, rates=controls.load_sol_list_rates(), reserve=Decimal("51")) is None
    assert controls.sub_agent_bound_usd(_observe([10], 10)[0], rates=_tenant(), reserve=Decimal("51")) is None
    assert controls.sub_agent_bound_usd(None, rates=_tenant(), reserve=Decimal("51")) is None


# -- 9. a tenant run books its attempt at the observed size ---------------------------


_TOTALS = dict(input_tokens=400_000, cached_input_tokens=300_000, cache_write_input_tokens=70_000,
               output_tokens=2_000, reasoning_output_tokens=500)


def _tenant_session(ledger, record_path: Path) -> controls.SolBatchSession:
    return controls.SolBatchSession(
        run=_exp036_on(TENANT), ledger=ledger, rates=_tenant(), record_path=record_path,
        seed_usd=Decimal(0), prior_legs_usd=Decimal(0), window_mismatch=False, header={})


def _streamed_turn(monkeypatch, sizes: list, *, rows: int = 1, extra: list | None = None) -> None:
    """A turn whose _await_turn reads the handle's stream, as core's does; ``rows`` ledger rows.

    ``extra`` events follow the token-usage updates on the stream.
    """
    usage = SimpleNamespace(model_context_window=1_000_000, last=SimpleNamespace(input_tokens=sizes[-1]),
                            total=SimpleNamespace(**_TOTALS))

    def await_turn(self, turn_handle, **kwargs):
        stream = turn_handle.stream()
        try:
            for _event in stream:
                pass
        finally:
            stream.close()
        return TurnObservation(result=SimpleNamespace(usage=usage), usage=usage, items_seen=3)

    def run(self, task_prompt, model=None, reference_files=None, occupation="professional",
            experiment_prompt=None, perception_text=None, run_id=None, condition_name=None, task_id=None):
        calls = [self._reserve_call(task_id) for _ in range(rows)]
        self._await_turn(_FakeHandle(_updates(sizes) + list(extra or [])))
        for call_id in calls:
            settle_codex_turn(self.cost_ledger, call_id, totals=CodexTokenTotals(**{
                key: value // rows for key, value in _TOTALS.items()}), resolved_model=self.provider.model)
        return {"success": True, "text": "ok", "files": [], "codex_diagnostics": {"items_seen": 3}}

    monkeypatch.setattr(CodexAgentRunner, "_await_turn", await_turn)
    monkeypatch.setattr(CodexAgentRunner, "run", run)


def _runner(session, ledger) -> controls.SolBatchCodexRunner:
    return controls.SolBatchCodexRunner(_settings(), session=session, timeout=1800, cost_ledger=ledger,
                                        run_id=ledger.run_id, condition_name="condition_a")


@pytest.mark.parametrize("sizes, rows, booked, tier, size", [
    # 100k uncached x 5.25 (once; 70k reported writes are fewer) + 300k cached
    # x 0.42 + 2k out x 21.00, per 1M.
    ([50_000, 120_000, 180_000], 1, "0.69300000", "short", 180_000),
    # 190k is past the bound: the list_long_context amount.
    ([50_000, 120_000, 190_000], 1, "2.64000000", "fallback", 190_000),
    ([50_000, 20_000], 1, "2.64000000", "fallback", None),
    # Two rows: neither the thread total nor the sizes can be attributed.
    ([50_000, 120_000, 180_000], 2, "2.64000000", "fallback+fallback", None),
])
def test_a_tenant_run_books_its_attempt_at_the_observed_request_size(
        tmp_path, monkeypatch, capsys, unit_runner, ledgers, sizes, rows, booked, tier, size):
    _streamed_turn(monkeypatch, sizes, rows=rows)
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    session = _tenant_session(ledger, record_path)
    result = _runner(session, ledger).run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])

    attempt = _record(record_path)["attempts"][-1]
    assert (attempt["booked_usd"], attempt["tier"], attempt["tier_request_input_tokens"]) == (booked, tier, size)
    assert attempt["request_sizes"]["updates"] == len(sizes)
    assert result["budget_metrics"] == {"conservative_cost_usd": booked, "usage_complete": True}
    out = capsys.readouterr().out
    assert f"tier {tier} at {size if size is not None else 'unknown'}; solve spend {booked}" in out


def test_a_turn_that_spawned_sub_agents_books_their_bound_and_is_incomplete(
        tmp_path, monkeypatch, capsys, unit_runner, ledgers):
    spawn = _sub_agent_item("collabAgentToolCall", "call-1", tool="spawnAgent", receiver_thread_ids=["child-a"])
    started = _sub_agent_item("subAgentActivity", "act-1", agent_thread_id="child-a", kind="started")
    _streamed_turn(monkeypatch, [50_000, 120_000, 180_000], extra=[spawn, started])
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    result = _runner(_tenant_session(ledger, record_path), ledger).run("prompt", model="gpt-5.6-sol",
                                                                       task_id=TASKS[0])
    attempt = _record(record_path)["attempts"][-1]
    # The row at list_long_context (no size) plus one attempt reserve for the one child thread.
    assert (attempt["booked_usd"], attempt["basis"], attempt["tier"], attempt["sub_agent_usd"]) == (
        "53.64000000", "settled_with_sub_agents", "fallback", "51.00000000")
    assert attempt["request_sizes"]["sub_agent_items"] == 2 and attempt["request_sizes"]["sub_agent_threads"] == 1
    assert attempt["tier_request_input_tokens"] is None
    assert result["budget_metrics"] == {"conservative_cost_usd": "53.64000000", "usage_complete": False}

    # The list basis books exactly what it always did.
    ledger = ledgers("list")
    record_path = tmp_path / "list.json"
    session = controls.SolBatchSession(
        run=_exp036_on(LIST), ledger=ledger, rates=controls.load_sol_list_rates(), record_path=record_path,
        seed_usd=Decimal(0), prior_legs_usd=Decimal(0), window_mismatch=False, header={})
    result = _runner(session, ledger).run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])
    attempt = _record(record_path)["attempts"][-1]
    assert (attempt["booked_usd"], attempt["basis"], attempt["sub_agent_usd"]) == ("2.64000000", "settled", None)
    assert result["budget_metrics"] == {"conservative_cost_usd": "2.64000000", "usage_complete": True}


def test_each_attempt_starts_its_request_sizes_afresh(tmp_path, monkeypatch, unit_runner, ledgers):
    _streamed_turn(monkeypatch, [50_000, 120_000, 180_000])
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    runner = _runner(_tenant_session(ledger, record_path), ledger)
    runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])
    runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])
    first, second = _record(record_path)["attempts"]
    for attempt in (first, second):
        assert attempt["request_sizes"]["updates"] == 3 and attempt["request_sizes"]["observed_sum"] == 350_000
        assert (attempt["tier"], attempt["booked_usd"]) == ("short", "0.69300000")


def test_a_non_streaming_turn_on_a_tenant_session_books_at_list_long_context(
        tmp_path, monkeypatch, unit_runner, ledgers):
    # test_sol_batch_controls's scripted parent never reads the stream: no size, no short tier.
    _scripted_parent(monkeypatch, 1_000_000)
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    result = _runner(_tenant_session(ledger, record_path), ledger).run("prompt", model="gpt-5.6-sol",
                                                                       task_id=TASKS[0])
    assert result["budget_metrics"]["conservative_cost_usd"] == "1.60500000"
    attempt = _record(record_path)["attempts"][-1]
    assert attempt["tier"] == "fallback" and attempt["request_sizes"]["updates"] == 0


# -- 10. install --------------------------------------------------------------------------


_LEGACY_IN_FLIGHT_RULE = (
    "a settled turn that did not finish, other than a rate refusal, also books the request it may have left "
    "in flight: the last reported request's input grown by its output and 100000 tool-output tokens, capped "
    "at 1050000, all uncached, plus 128000 output tokens; without one, 1050000 uncached input tokens plus "
    "128000 output tokens")


def test_a_tenant_run_installs_with_its_basis_on_record(tmp_path, monkeypatch, capsys, unit_runner, ledgers):
    legacy_dir, tenant_dir = tmp_path / "legacy", tmp_path / "tenant"
    legacy_dir.mkdir()
    tenant_dir.mkdir()
    ledger = ledgers("legacy")
    executor, settings = _executor(ledger)
    controls.install(executor, **_install_kwargs(settings, ledger, legacy_dir))
    legacy = _record(legacy_dir / "sol_batch_controls_condition_a.json")["header"]
    assert legacy["usd"] == {
        "ceiling": "200.00000000", "grading_reserve": "54.00000000", "attempt_reserve": "51.00000000",
        "solve_budget": "146.00000000", "admit_while_spend_at_most": "95.00000000",
        "booking_basis": "list_long_context", "refused_request": "7.20000000",
        "meter": "long_context_standard_global",
        "rates": {"input": "10.00", "cached_input": "1.00", "cache_write": "12.50", "output": "45.00"},
        "rates_retrieved": "2026-08-29", "price_table_sha256": controls.PRICE_TABLE_SHA256,
        "cache_write_rule": "max(reported, input - cached)", "reasoning": "inside output",
        "unknown_usage": (
            "a turn with no reported usage books the attempt reserve; a rate refusal with no completed item "
            "books one refused request; a settled turn without priceable counts books the attempt reserve; "
            "an abandoned turn books 0"),
        "in_flight_rule": _LEGACY_IN_FLIGHT_RULE,
        "prior_lineage_spend_usd": controls.fmt(controls.RUNS["exp036_sol_fixed5"].prior_lineage_spend_usd),
        "prior_legs_spend_usd": "0.00000000", "prior_leg_tasks": [],
    }
    assert controls.TENANT_RATES_RELATIVE not in legacy["sources"]
    banner = capsys.readouterr().out
    assert f"[sol-batch] booking basis list_long_context ({controls.PRICE_TABLE_SHA256[:12]})" in banner

    _patch_exp036(monkeypatch, TENANT)
    ledger = ledgers("tenant")
    executor, settings = _executor(ledger)
    session = controls.install(executor, **_install_kwargs(settings, ledger, tenant_dir))
    assert isinstance(session.rates, controls.SolTenantPricing)
    path = tenant_dir / "sol_batch_controls_condition_a.json"
    raw = path.read_bytes()
    header = _record(path)["header"]
    usd = header["usd"]
    assert {key: usd[key] for key in ("ceiling", "grading_reserve", "attempt_reserve", "solve_budget",
                                      "admit_while_spend_at_most")} == {
        key: legacy["usd"][key] for key in ("ceiling", "grading_reserve", "attempt_reserve", "solve_budget",
                                            "admit_while_spend_at_most")}
    assert usd["booking_basis"] == TENANT and usd["refused_request"] == "3.02400000"
    assert usd["meter"] == controls.SOL_SHORT_METER
    assert usd["rates"] == {"input": "4.20", "cached_input": "0.42", "cache_write": "5.25", "output": "21.00"}
    assert usd["observed_rates"] == {"input": "4.00", "cached_input": "0.40", "cache_write": "5.00",
                                     "output": "20.00"}
    assert (usd["safety_margin"], usd["rates_retrieved"]) == ("1.05", "2026-11-26T00:55Z")
    assert usd["rates_source"] == {"path": controls.TENANT_RATES_RELATIVE, "sha256": TENANT_RATES_SHA256}
    assert usd["short_tier_through_request_input_tokens"] == BOUND
    assert usd["fallback"] == {"basis": LIST, "meter": controls.SOL_METER, "rates": legacy["usd"]["rates"],
                               "rates_retrieved": "2026-08-29", "price_table_sha256": controls.PRICE_TABLE_SHA256}
    assert usd["price_table_sha256"] == controls.PRICE_TABLE_SHA256
    assert "max(input, cache_write)" in usd["cache_write_rule"] and "187594" in usd["tier_rule"]
    assert "re-sent update is no request" in usd["tier_rule"] and "sub-agent tools" in usd["tier_rule"]
    assert "attempt reserve" in usd["sub_agent_rule"] and "incomplete" in usd["sub_agent_rule"]
    assert "sub_agent_rule" not in legacy["usd"]
    rule = usd["in_flight_rule"]
    assert rule.startswith(_LEGACY_IN_FLIGHT_RULE) and "all uncached" in rule and "1050000" in rule
    assert rule.endswith("priced at the short tier when that grown input is at most 187594, else at "
                         "list_long_context")
    assert header["sources"][controls.TENANT_RATES_RELATIVE] == TENANT_RATES_SHA256
    banner = capsys.readouterr().out
    assert f"[sol-batch] booking basis {TENANT} ({TENANT_RATES_SHA256[:12]})" in banner
    for secret in (b"fixture-host", b"openai.azure.com", *(part.encode() for part in AUTH_ARGV)):
        assert secret not in raw


# -- 11. grading on the tenant basis ---------------------------------------------------------


def _kwargs_of_allowance(inputs: int) -> dict:
    base = len(json.dumps({**KWARGS, "input": ""}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    return {**KWARGS, "input": "x" * (inputs - base)}


def test_a_tenant_grade_reserves_and_settles_on_its_tier(admitted, monkeypatch):
    admission, recorder = admitted(_seed(booking_basis=TENANT), "run-8-1.combined_usd.jsonl")
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(FakeResponses(), provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
        heavy = FakeResponses(tokens={"input_tokens": 200_000, "cached": 0, "output_tokens": 200, "reasoning": 0})
        recorder.meter(heavy, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
        large = _kwargs_of_allowance(200_000)
        recorder.meter(FakeResponses(), provider="azure", model="gpt-5.6-sol").responses.create(**large)
    records = _records(admission.journal_path)
    assert [record["event"] for record in records] == ["open", "reserve", "settle", "reserve", "settle",
                                                       "reserve", "settle"]
    opening, reserve, settle = records[0], records[1], records[2]
    assert (opening["booking_basis"], opening["booking_rates_sha256"]) == (TENANT, TENANT_RATES_SHA256)
    # 82 x 5.25 + 2,400 x 21.00 per 1M.
    assert (reserve["reserve_usd"], reserve["allowance_input_tokens"], reserve["allowance_output_tokens"],
            reserve["tier"]) == ("0.05083050", 82, 2400, "short")
    assert (settle["spent_usd"], settle["tier"]) == ("0.00945000", "short")
    # Past the bound the settle books list_long_context, as observed and without a stop.
    assert (records[4]["spent_usd"], records[4]["tier"]) == ("4.50900000", "fallback")
    assert (records[5]["reserve_usd"], records[5]["allowance_input_tokens"], records[5]["tier"]) == (
        "4.60800000", 200_000, "fallback")
    assert admission.stops == []

    legacy, _ = admitted(_seed(), "run-9-1.combined_usd.jsonl")
    opening = _records(legacy.journal_path)[0]
    assert (opening["booking_basis"], opening["booking_rates_sha256"]) == (LIST, controls.PRICE_TABLE_SHA256)
    # Each journal reads back under the approval on its own basis.
    admission.close(0)
    legacy.close(0)
    approval = _tenant_approval(monkeypatch)
    assert grading._read_journal(admission.journal_path, approval)[0] == Decimal("4.52790000")
    with pytest.raises(grading.CombinedUsdRefused):
        grading._read_journal(legacy.journal_path, approval)


class _RetryingClient(FakeResponses):
    """An OpenAI-shaped client: the SDK's retry policy, and a call that took ``seconds`` on a fake clock."""

    def __init__(self, clock: list, seconds: float, *, max_retries: Any = 2, timeout: Any = 600,
                 error: BaseException | None = None, **kwargs: Any) -> None:
        super().__init__(error=error, **kwargs)
        self.max_retries = max_retries
        self.timeout = timeout
        self._clock = clock
        self._seconds = seconds

    def create(self, **kwargs):
        self._clock[0] += self._seconds
        return super().create(**kwargs)


def test_a_tenant_grade_books_the_attempts_sdk_retries_hide(admitted):
    import httpx
    import openai

    clock = [1_000.0]
    admission, recorder = admitted(_seed(booking_basis=TENANT), "run-12-1.combined_usd.jsonl")
    admission._clock = lambda: clock[0]
    # exp037 run-42850641369-1 seq 854: 611.8 s against the 600 s judge timeout,
    # 2385 in / 2382 cached / 110 out. One hidden attempt books one more reservation.
    tokens = {"input_tokens": 2385, "cached": 2382, "output_tokens": 110, "reasoning": 73}
    calls = [
        _RetryingClient(clock, 611.8, tokens=tokens),
        _RetryingClient(clock, 12.0, tokens=tokens),
        _RetryingClient(clock, 1_900.0, tokens=tokens),                     # capped at max_retries
        _RetryingClient(clock, 611.8, max_retries=0, tokens=tokens),        # no SDK retries
        _RetryingClient(clock, 611.8, timeout=httpx.Timeout(600.0), tokens=tokens),
        _RetryingClient(clock, 611.8, timeout=None, tokens=tokens),         # never times out
        _RetryingClient(clock, 5.0, timeout="soon", tokens=tokens),         # unreadable: every retry
    ]
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        for client in calls:
            recorder.meter(client, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
        failing = _RetryingClient(clock, 1_850.0, error=TimeoutError("read timed out"))
        with pytest.raises(TimeoutError):
            recorder.meter(failing, provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
    records = _records(admission.journal_path)
    reserves = [record for record in records if record["event"] == "reserve"]
    concluded = [record for record in records if record["event"] in ("settle", "abandon")]
    assert [(r["sdk_max_retries"], r["sdk_timeout_sec"]) for r in reserves] == [
        (2, 600.0), (2, 600.0), (2, 600.0), (None, None), (2, 600.0), (None, None), (2, None), (2, 600.0)]
    reserve = Decimal(reserves[0]["reserve_usd"])
    settle = Decimal("0.00332619")
    assert [(r["event"], r["hidden_attempts"], Decimal(r["spent_usd"])) for r in concluded] == [
        ("settle", 1, settle + reserve), ("settle", 0, settle), ("settle", 2, settle + 2 * reserve),
        ("settle", 0, settle), ("settle", 1, settle + reserve), ("settle", 0, settle),
        ("settle", 2, settle + 2 * reserve),
        # Three attempts that each timed out: the reservation plus two hidden ones.
        ("abandon", 2, 3 * reserve),
    ]
    assert all(Decimal(r["hidden_attempts_usd"]) == r["hidden_attempts"] * reserve for r in concluded)
    assert admission.spent == sum((Decimal(r["spent_usd"]) for r in concluded), Decimal(0))
    admission.close(0)
    assert grading.journal_spend(admission.journal_path) == admission.spent

    # A real OpenAI client reads as SDK retries 2 at its timeout; nothing is sent.
    client = openai.OpenAI(api_key="unused", base_url="http://127.0.0.1:9/v1", timeout=600)
    assert grading._sdk_retry_policy(client) == (2, 600.0)
    assert grading._sdk_retry_policy(client.with_options(max_retries=0)) is None
    assert grading._sdk_retry_policy(SimpleNamespace()) is None

    # The list basis books one conclusion per call, as it always has.
    clock[0] = 0.0
    legacy, recorder = admitted(_seed(), "run-13-1.combined_usd.jsonl")
    legacy._clock = lambda: clock[0]
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(_RetryingClient(clock, 1_900.0, tokens=tokens), provider="azure",
                       model="gpt-5.6-sol").responses.create(**KWARGS)
    reserve_line, settle_line = _records(legacy.journal_path)[1:3]
    assert "sdk_max_retries" not in reserve_line and "hidden_attempts" not in settle_line
    assert settle_line["spent_usd"] == "0.00739950"


# -- 12. the published floor -------------------------------------------------------------------


def test_the_floor_is_the_runs_basis_at_its_lowest_tier(tmp_path):
    tenant = _exp036_on(TENANT)
    task = controls.FIXED_TASK_IDS[0]
    fetch, _ = _published(tmp_path, [_task_row(task, 0.6)], [SETTLED_CALL])
    solve, floor, status = grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, tenant, fetch=fetch)
    # 80k uncached x 5.25 + 20k cached x 0.42 + 5k out x 21.00, per 1M.
    assert (floor, status) == (Decimal("0.53340000"), "present")
    assert solve == tenant.prior_lineage_spend_usd + Decimal("0.6")
    fetch, _ = _published(tmp_path, [_task_row(task, 0.5)], [SETTLED_CALL])
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, tenant, fetch=fetch)
    assert "below the published ledger" in refused.value.detail
    legacy = controls.RUNS["exp036_sol_fixed5"]
    fetch, _ = _published(tmp_path, [_task_row(task, 2.1)], [SETTLED_CALL])
    assert grading.published_solve("HyeonSang/exp036_sol_fixed5", INFERENCE_SHA, legacy, fetch=fetch)[1] == (
        Decimal("2.04500000"))
    assert controls.floor_price_usd(input_tokens=100_000, cached_input_tokens=20_000, output_tokens=5_000,
                                    rates=_tenant()) == Decimal("0.53340000")


# -- 13. journals booked under another basis or rates ------------------------------------------


def _journal(path: Path, **opening: Any) -> Path:
    records = [{"event": "reserve", "ticket": "g1", "task_id": "t", "reserve_usd": "0.50000000"},
               {"event": "settle", "ticket": "g1", "spent_usd": "0.25000000"}]
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"event": "open", "schema": grading.JOURNAL_SCHEMA, "experiment_id": "exp036_sol_fixed5",
              "config_name": "exp036_v2_sol_max", **opening}, *records]
    path.write_text("".join(json.dumps({**line, "seq": seq}, sort_keys=True) + "\n"
                            for seq, line in enumerate(lines)), encoding="utf-8")
    return path


def _refusal(path: Path, approval) -> str:
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading._read_journal(path, approval)
    return refused.value.detail


def test_a_journal_booked_under_another_basis_or_rates_refuses(tmp_path, monkeypatch):
    plain = _journal(tmp_path / "run-1-1.combined_usd.jsonl")
    listed = _journal(tmp_path / "run-2-1.combined_usd.jsonl", booking_basis=LIST,
                      booking_rates_sha256=controls.PRICE_TABLE_SHA256)
    tenant = _journal(tmp_path / "run-3-1.combined_usd.jsonl", booking_basis=TENANT,
                      booking_rates_sha256=TENANT_RATES_SHA256)
    wrong = _journal(tmp_path / "run-4-1.combined_usd.jsonl", booking_basis=TENANT,
                     booking_rates_sha256=controls.PRICE_TABLE_SHA256)
    missing = _journal(tmp_path / "run-5-1.combined_usd.jsonl", booking_basis=TENANT)
    listed_wrong = _journal(tmp_path / "run-6-1.combined_usd.jsonl", booking_basis=LIST,
                            booking_rates_sha256=TENANT_RATES_SHA256)
    unknown = _journal(tmp_path / "run-7-1.combined_usd.jsonl", booking_basis="x")
    not_text = _journal(tmp_path / "run-8-1.combined_usd.jsonl", booking_basis=7)

    for path in (plain, listed, tenant, wrong, missing):
        assert grading.journal_spend(path) == Decimal("0.25")
    for path in (unknown, not_text):
        with pytest.raises(grading.CombinedUsdRefused) as refused:
            grading.journal_spend(path)
        assert refused.value.detail == f"{path.name} names an unknown booking basis"

    legacy = grading.EXP036_SOL_BATCH
    for path in (plain, listed):
        assert grading._read_journal(path, legacy)[0] == Decimal("0.25")
    assert _refusal(tenant, legacy) == (f"{tenant.name} was booked under {TENANT}; this approval books under "
                                        f"{LIST}")
    assert _refusal(listed_wrong, legacy) == f"{listed_wrong.name} was booked from other rates than {LIST} pins"

    approval = _tenant_approval(monkeypatch)
    assert grading._read_journal(tenant, approval)[0] == Decimal("0.25")
    assert _refusal(plain, approval) == f"{plain.name} was booked under {LIST}; this approval books under {TENANT}"
    assert _refusal(listed, approval).startswith(f"{listed.name} was booked under {LIST}")
    for path in (wrong, missing):
        assert _refusal(path, approval) == f"{path.name} was booked from other rates than {TENANT} pins"
    assert _refusal(unknown, approval) == f"{unknown.name} names an unknown booking basis"


# -- 14. the two registries ----------------------------------------------------------------------


def test_the_two_registries_must_agree_on_the_basis(monkeypatch):
    experiment = {"data": {"source": "HyeonSang/exp036_sol_fixed5"}}

    def never(*args, **kwargs):
        raise AssertionError("nothing published is read for a pair whose bases differ")

    monkeypatch.setattr(grading, "published_solve", never)
    _patch_exp036(monkeypatch, TENANT)
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading._solve_seed(grading.EXP036_SOL_BATCH, experiment, INFERENCE_SHA)
    assert refused.value.detail == "the solve and grade sides book under different bases"
    _patch_exp036(monkeypatch, LIST)
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        grading._solve_seed(_tenant_approval(monkeypatch), experiment, INFERENCE_SHA)
    assert refused.value.detail == "the solve and grade sides book under different bases"


def test_an_unknown_basis_is_named():
    for basis in ("x", 7, None):
        run = _exp036_on(basis)
        assert controls.registry_problems({run.experiment_id: run}) == [
            f"exp036_sol_fixed5: booking_basis must be one of {sorted(controls.BOOKING_BASES)}"]
        unapproved = dataclasses.replace(controls.RUNS["exp038_sol_rest195"], booking_basis=basis)
        assert controls.registry_problems({unapproved.experiment_id: unapproved}) == [
            f"exp038_sol_rest195: booking_basis must be one of {sorted(controls.BOOKING_BASES)}"]
        approval = dataclasses.replace(grading.EXP036_SOL_BATCH, booking_basis=basis)
        assert grading.approval_problems([approval]) == [
            "exp036_sol_fixed5/exp036_v2_sol_max: an unknown booking basis"]
    assert controls.registry_problems({"exp036_sol_fixed5": _exp036_on(TENANT)}) == []
    assert grading.approval_problems([dataclasses.replace(grading.EXP036_SOL_BATCH, booking_basis=TENANT)]) == []


# -- 15. the attempt reserve covers the in-flight window on both bases -------------------------


def test_every_approved_run_reserve_covers_its_in_flight_window():
    for basis in sorted(controls.BOOKING_BASES):
        assert controls.in_flight_bound_usd(None, rates=controls.load_booking_rates(basis)) == Decimal("29.38500000")
    for run in controls.RUNS.values():
        if run.approval is None:
            continue
        window = controls.in_flight_bound_usd(None, rates=controls.load_booking_rates(run.booking_basis))
        assert run.attempt_reserve_usd >= window, run.experiment_id


# -- 16. every committed journal replays on its own basis -----------------------------------------


def _replay_journals(journals: list[Path]) -> tuple[int, int]:
    """``(gpt-5.6-sol settles, mismatches)``: each journal replayed on the basis its open line names.

    Every journal must name a known basis, the one its approval books under;
    a journal of an approval registered before the tenant basis must be on
    list_long_context. A tenant settle may add the attempts SDK retries hid
    (``hidden_attempts_usd``) on top of its booked price.
    """
    settles = mismatches = 0
    for path in journals:
        lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert lines[0]["event"] == "open", path.name
        basis = lines[0].get("booking_basis", LIST)
        owner = grading._journal_owner(lines[0])
        assert owner is not None and basis in controls.BOOKING_BASES and basis == owner.booking_basis, path.name
        if owner in LEGACY_APPROVALS:
            assert basis == LIST, path.name
        assert lines[0].get("booking_rates_sha256", controls.PRICE_TABLE_SHA256) == (
            controls.booking_source_sha256(basis)), path.name
        rates = controls.load_booking_rates(basis)
        models = {line["ticket"]: line.get("model") for line in lines if line.get("event") == "reserve"}
        for line in lines:
            if line.get("event") != "settle" or models.get(line["ticket"]) != "gpt-5.6-sol":
                continue
            settles += 1
            replayed = controls.booked_price_usd(
                input_tokens=line["input_tokens"], cached_input_tokens=line["cached_input_tokens"],
                output_tokens=line["output_tokens"], reasoning_tokens=line["reasoning_tokens"],
                request_input_tokens=line["input_tokens"], rates=rates)
            hidden = Decimal(line.get("hidden_attempts_usd", "0"))
            mismatches += replayed + hidden != Decimal(line["spent_usd"])
    return settles, mismatches


def test_every_committed_journal_replays_exactly_on_its_own_basis():
    journals = sorted(JOURNALS.glob("*/run-*.combined_usd.jsonl"))
    assert journals
    settles, mismatches = _replay_journals(journals)
    assert settles >= SOL_SETTLES_AT_DESIGN
    assert mismatches == 0
    for approval in grading.APPROVALS:
        if approval.approved is None or not (JOURNALS / approval.experiment_id).is_dir():
            continue
        total, read = grading.prior_grading(REPO_ROOT, approval.experiment_id, approval)
        assert read and total > 0, approval.experiment_id
    assert grading.prior_grading(REPO_ROOT, "exp036_sol_fixed5", grading.EXP036_SOL_BATCH)[0] >= Decimal("10.7193625")


def test_a_committed_tenant_journal_replays_on_its_own_basis(tmp_path, admitted, monkeypatch):
    # What grade-run commits for the first tenant run: the replay must take it
    # on its own basis, and still hold a legacy approval to list_long_context.
    approval = _tenant_approval(monkeypatch)
    admission, recorder = admitted(_seed(booking_basis=TENANT), "run-99-1.combined_usd.jsonl")
    with recorder.attributed(task_id="t", stage=STAGE_GRADING):
        recorder.meter(FakeResponses(), provider="azure", model="gpt-5.6-sol").responses.create(**KWARGS)
    admission.close(0)
    assert grading._journal_owner(_records(admission.journal_path)[0]) is approval
    assert _replay_journals([admission.journal_path]) == (1, 0)

    forged = tmp_path / "forged" / "run-98-1.combined_usd.jsonl"
    forged.parent.mkdir()
    lines = _records(admission.journal_path)
    lines[0]["booking_basis"] = "tenant_observed_29991231"
    forged.write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines), encoding="utf-8")
    with pytest.raises(AssertionError):
        _replay_journals([forged])
    # A legacy approval's journal that names the tenant basis is refused by the replay too.
    legacy = sorted((JOURNALS / "exp037_sol_first25").glob("run-*.combined_usd.jsonl"))[0]
    copied = tmp_path / "legacy" / legacy.name
    copied.parent.mkdir()
    lines = [json.loads(line) for line in legacy.read_text(encoding="utf-8").splitlines()]
    assert grading._journal_owner(lines[0]) is grading.EXP037_FIRST25
    lines[0].update(booking_basis=TENANT, booking_rates_sha256=TENANT_RATES_SHA256)
    copied.write_text("".join(json.dumps(line, sort_keys=True) + "\n" for line in lines), encoding="utf-8")
    with pytest.raises(AssertionError):
        _replay_journals([copied])


# -- 17. the tenant basis against the bill ------------------------------------------------------------


def _replayed(path: Path, pricing: controls.SolTenantPricing) -> Decimal:
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    models = {line["ticket"]: line.get("model") for line in lines if line.get("event") == "reserve"}
    total = Decimal(0)
    for line in lines:
        # Audio settles take their stand-in rate on every basis; they are no Sol meter.
        if line.get("event") == "settle" and models.get(line["ticket"]) == "gpt-5.6-sol":
            total += controls.booked_price_usd(
                input_tokens=line["input_tokens"], cached_input_tokens=line["cached_input_tokens"],
                output_tokens=line["output_tokens"], reasoning_tokens=line["reasoning_tokens"],
                request_input_tokens=line["input_tokens"], rates=pricing)
    return total


def test_the_tenant_basis_reconciles_with_billing():
    """The evidence that Azure bills uncached input once: committed ledgers replayed against billed days.

    The record's ``uncached_input_million_tokens`` is the sum of its own input
    and cache-write quantities, so the loader's check on it, and the period
    figure below, are arithmetic on the bill, not evidence of "once". Only
    the replayable billed windows compare the ledgers' tokens with the bill:
    had Azure charged the same uncached tokens on both meters, the bill for
    those days would sit about 9.00 / 5.00 above the observed replay on
    uncached input, far outside 0.5%.
    """
    booked = _tenant()
    observed = dataclasses.replace(booked, booked=booked.observed)
    record = json.loads(controls.TENANT_RATES_PATH.read_text(encoding="utf-8"))
    windows = {window["window_utc"]: window for window in record["billed_windows"]}
    # Every window the record says can be replayed from committed files is.
    replayable = [window for window in record["billed_windows"]
                  if window.get("replayable_from_committed_files", True)]
    assert {window["window_utc"] for window in replayable} == {"2026-11-12", "2026-11-13"}
    for window in replayable:
        billed = Decimal(window["sol_cost_usd"]) - Decimal(window["deduction_usd"])
        path = REPO_ROOT / window["journal"]
        assert abs(_replayed(path, observed) - billed) <= billed * Decimal("0.005"), window["window_utc"]
        assert billed <= _replayed(path, booked), window["window_utc"]

    first = windows["2026-11-13"]
    billed = Decimal(first["sol_cost_usd"]) - Decimal(first["deduction_usd"])
    assert billed == Decimal("23.3567")
    path = REPO_ROOT / first["journal"]
    assert path.name == "run-43310879444-1.combined_usd.jsonl"
    assert _replayed(path, observed) == Decimal("23.36072080")
    assert abs(_replayed(path, observed) - billed) <= billed * Decimal("0.005")
    assert billed <= _replayed(path, booked) == Decimal("24.52875684") <= billed * Decimal("1.06")

    second = windows["2026-11-12"]
    billed = Decimal(second["sol_cost_usd"]) - Decimal(second["deduction_usd"])
    assert billed == Decimal("30.58")
    path = REPO_ROOT / second["journal"]
    assert path.name == "run-42850641369-1.combined_usd.jsonl"
    assert _replayed(path, observed) == Decimal("30.60473240")
    assert abs(_replayed(path, observed) - billed) <= billed * Decimal("0.005")
    assert billed <= _replayed(path, booked) == Decimal("32.13496902") <= billed * Decimal("1.06")

    # The whole period's billed quantities, at the observed and the booked
    # rates: this prices the bill's own quantities (779.43 is the 0.702739M
    # input-meter tokens at 5.00 instead of 4.00, plus cents rounding), not
    # the ledgers', so it shows the rates' arithmetic, not "billed once".
    observation = record["observation"]
    quantity = {meter["rate_kind"]: Decimal(meter["quantity_million_tokens"]) for meter in observation["meters"]}
    uncached = Decimal(observation["uncached_input_million_tokens"])

    def priced(rates: controls.SolRates) -> Decimal:
        return (uncached * max(rates.input, rates.cache_write) + quantity["cached_input"] * rates.cached_input
                + quantity["output"] * rates.output).quantize(Decimal("0.01"))

    assert priced(booked.observed) == Decimal("779.43")
    assert priced(booked.booked) == Decimal("818.40")
    assert Decimal(observation["period_cost_usd"]) == Decimal("778.72")


# -- 18. the private contract the observer relies on ---------------------------------------------------


def test_the_private_contract_the_observer_relies_on():
    assert codex_runner._NOTIFY_TOKEN_USAGE == controls._NOTIFY_TOKEN_USAGE == "thread/tokenUsage/updated"
    assert "token_usage" in inspect.getsource(codex_runner._recording_stream)
    source = inspect.getsource(CodexAgentRunner._await_turn)
    for needle in ("turn_handle.stream()", "stream.close()", "turn_handle.id"):
        assert needle in source
    assert list(inspect.signature(CodexAgentRunner._await_turn).parameters) == [
        "self", "turn_handle", "task_deadline", "observation_control", "observed", "pilot_wire_observer"]
    assert "self._await_turn(turn_handle" in inspect.getsource(CodexAgentRunner._run_one_turn)


# -- 19. the real pinned Codex reports one update per request ------------------------------------------


@pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)
def test_loopback_codex_reports_every_request_size(tmp_path, native_hosted_runner, ledgers):
    ledger = ledgers(run_id="codex-e2e")
    record_path = tmp_path / "r.json"
    session = _tenant_session(ledger, record_path)
    with ScriptedResponses([says_run_this("true"), says("done")]) as server:
        runner = controls.SolBatchCodexRunner(
            LoopbackCodexProvider(port=server.port), session=session, timeout=180, cost_ledger=ledger,
            run_id="codex-e2e", condition_name="condition_a")
        result = runner.run("Run true, then reply with the word done.", task_id="task-e2e")
        runner.close()
        assert len(server.request_bodies()) == 2

    assert result["success"] is True, result.get("error")
    [row] = ledger.calls_for("task-e2e")
    assert row["state"] == STATE_SETTLED and row["input_tokens"] == 51
    attempt = _record(record_path)["attempts"][-1]
    assert attempt["request_sizes"] == {"updates": 2, "repeats": 0, "peak": 40, "observed_sum": 51,
                                        "unobserved_input_tokens": 0, "shrank": False, "unreadable": False,
                                        "sub_agent_items": 0, "sub_agent_threads": 0}
    assert attempt["tier_request_input_tokens"] == 40 and attempt["tier"] == "short"


# -- 20. the same, on the configuration production runs ---------------------------------------------


@dataclasses.dataclass(frozen=True)
class _SolProductionLoopback(LoopbackCodexProvider):
    """The held Sol catalog (sol_overrides) and production's zero Codex retries, at a loopback port."""

    def config_overrides(self) -> tuple[str, ...]:
        prefix = f"model_providers.{self.provider_id}"
        base = (*super().config_overrides(), f"{prefix}.request_max_retries=0",
                f"{prefix}.stream_max_retries=0",
                *requested_model_config_overrides(reasoning_effort="max", model_context_window=1_000_000))
        return controls.sol_overrides(base)


def _u(inputs: int, *, cached: int = 0, output: int = 5) -> dict:
    return _usage(input_tokens=inputs, output_tokens=output, cached=cached, reasoning=0)


def _calls(name: str, arguments: dict, call_id: str, usage: dict):
    """A reply that calls a collaboration tool, as the held catalog offers it."""
    def reply(_request: dict, index: int) -> tuple[int, bytes]:
        item = {"type": "function_call", "id": f"fc_{index}", "call_id": call_id, "name": name,
                "namespace": "collaboration", "arguments": json.dumps(arguments), "status": "completed"}
        return 200, _sse([
            {"type": "response.created", "response": {"id": f"resp_{index}", "status": "in_progress"}},
            {"type": "response.output_item.done", "output_index": 0, "item": item},
            {"type": "response.completed", "response": {"id": f"resp_{index}", "status": "completed",
                                                        "usage": usage}},
        ])
    return reply


def _fails(_request: dict, index: int) -> tuple[int, bytes]:
    return 200, _sse([
        {"type": "response.created", "response": {"id": f"resp_{index}", "status": "in_progress"}},
        {"type": "response.failed", "response": {"id": f"resp_{index}", "status": "failed",
                                                 "error": {"code": "server_error", "message": "scripted"}}},
    ])


def _routed(parent: list, child: list):
    """Requests carrying the sub-agent developer prompt follow ``child``; the rest follow ``parent``."""
    counts = {"parent": 0, "child": 0}

    def reply(request: dict, index: int) -> tuple[int, bytes]:
        is_child = any(
            isinstance(item, dict) and item.get("type") == "message" and item.get("role") == "developer"
            and "You are an agent in a team of agents" in json.dumps(item)
            for item in request.get("input") or ())
        who = "child" if is_child else "parent"
        script = child if is_child else parent
        n = counts[who]
        counts[who] += 1
        if n >= len(script):
            return 409, b'{"error":{"message":"unscripted request"}}'
        return script[n](request, index)
    return reply, counts


def _production_turn(tmp_path, ledgers, script, *, name: str = "e2e") -> tuple[dict, dict, list]:
    ledger = ledgers(name, run_id="codex-e2e")
    record_path = tmp_path / f"{name}.json"
    session = _tenant_session(ledger, record_path)
    with ScriptedResponses(script) as server:
        runner = controls.SolBatchCodexRunner(
            _SolProductionLoopback(port=server.port, model="gpt-5.6-sol"), session=session, timeout=180,
            cost_ledger=ledger, run_id="codex-e2e", condition_name="condition_a")
        result = runner.run("Do the task.", model="gpt-5.6-sol", task_id="task-e2e")
        runner.close()
    return result, _record(record_path)["attempts"][-1], ledger.calls_for("task-e2e")


@pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)
def test_loopback_production_codex_sizes_requests_and_skips_a_re_sent_update(
        tmp_path, native_hosted_runner, ledgers):
    wait = _calls("wait_agent", {"timeout_ms": 10_000}, "c1", _u(11))
    result, attempt, rows = _production_turn(tmp_path, ledgers, [wait, says("done", usage=_u(40))])
    assert result["success"] is True, result.get("error")
    assert [(row["state"], row["input_tokens"]) for row in rows] == [(STATE_SETTLED, 51)]
    assert attempt["request_sizes"]["updates"] == 2 and attempt["request_sizes"]["repeats"] == 0
    assert (attempt["tier"], attempt["tier_request_input_tokens"]) == ("short", 40)

    # A final stream that fails: Codex 0.147.0 re-sends the first update; the
    # row keeps its short tier and books its in-flight bound.
    result, attempt, rows = _production_turn(tmp_path, ledgers, [wait, _fails], name="failed")
    assert result["success"] is False
    assert [(row["state"], row["input_tokens"]) for row in rows] == [(STATE_SETTLED, 11)]
    sizes = attempt["request_sizes"]
    assert (sizes["updates"], sizes["repeats"], sizes["observed_sum"]) == (2, 1, 11)
    assert (attempt["tier"], attempt["tier_request_input_tokens"], attempt["basis"]) == (
        "short", 11, "settled_partial")


@pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)
def test_loopback_production_codex_books_a_spawned_sub_agent(tmp_path, native_hosted_runner, ledgers):
    parent = [
        _calls("spawn_agent", {"task_name": "helper", "message": "Check the file.", "fork_turns": "all"}, "c1",
               _u(150_000, cached=100_000)),
        _calls("wait_agent", {"timeout_ms": 20_000}, "c2", _u(160_000, cached=150_000)),
        says("done", usage=_u(170_000, cached=160_000)),
    ]
    # The child's 190k request is above the bound and reaches no ledger row.
    child = [says("sub", usage=_u(190_000, output=2_000))]
    route, counts = _routed(parent, child)
    result, attempt, rows = _production_turn(tmp_path, ledgers, [route] * 12)
    assert result["success"] is True, result.get("error")
    assert counts == {"parent": 3, "child": 1}
    [row] = rows
    assert (row["input_tokens"], row["cached_input_tokens"]) == (480_000, 410_000)
    sizes = attempt["request_sizes"]
    assert sizes["sub_agent_items"] >= 1 and sizes["sub_agent_threads"] == 1
    assert (attempt["tier"], attempt["tier_request_input_tokens"]) == ("fallback", None)
    listed = controls.booked_price_usd(input_tokens=480_000, cached_input_tokens=410_000, output_tokens=15,
                                       rates=_tenant())
    assert attempt["basis"] == "settled_with_sub_agents" and attempt["sub_agent_usd"] == "51.00000000"
    assert Decimal(attempt["booked_usd"]) == listed + Decimal("51")
    assert result["budget_metrics"]["usage_complete"] is False
