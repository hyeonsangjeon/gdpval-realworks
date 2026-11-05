"""The Sol fixed-five batch controls: inert for other runs, closed for exp036.

``sol_batch_controls`` is the only thing between the generic codex_foundry
path and an uncapped GPT-5.6 Sol run, so these tests check both directions:
every other run gets ``None`` back and nothing is touched, and the registered
batch gets the held 1M catalog and a gate that refuses to start an attempt
once booked spend plus one reserve would pass the solve budget.

No test here reaches a model. Endpoints and auth argv are fixtures, sockets
are blocked, and the one end-to-end test runs the pinned Codex binary against
:class:`ScriptedResponses` on 127.0.0.1. The Python process opens no
connection in that test either: the Codex child process is the only client of
the loopback server, so the socket block stays on for it too.
"""

from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import os
import shutil
import socket
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import sol_batch_controls as controls
import step2_run_inference as step2
from core import codex_runner, runner_environment
from core.codex_cost import CodexTokenTotals, settle_codex_turn
from core.codex_runner import CodexAgentRunner, TurnObservation
from core.codex_runtime_config import (
    CodexProviderSettings,
    LoopbackCodexProvider,
    _toml_literal,
    requested_model_config_overrides,
)
from core.cost_receipts import (
    STATE_ABANDONED,
    STATE_REFUSED,
    STATE_RESERVED,
    STATE_SETTLED,
    CostReceiptLedger,
)
from core.executor import TaskExecutor

from .test_codex_runtime_end_to_end import _RUNTIME_PROBLEM, ScriptedResponses, says

BATCH_RUNNER = Path(__file__).resolve().parents[1]
ENDPOINT = "https://fixture-host.openai.azure.com/openai/v1/"
AUTH_ARGV = ("/fixture/python", "/fixture/token.py", "--scope", "fixture-scope")
RUN_ID = "exp036_sol_fixed5:123456789:1"
TASKS = controls.FIXED_TASK_IDS
RECORD_NAME = "sol_batch_controls_condition_a.json"
ANCHOR_LEDGER = BATCH_RUNNER / "tests/fixtures/run_record/cost_ledger_condition_a.jsonl"


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in Sol batch controls tests")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


@pytest.fixture
def fixed_auth(monkeypatch):
    """A fixed auth argv, so override tuples are comparable and no token helper runs."""
    monkeypatch.setattr(
        CodexProviderSettings, "auth_command",
        lambda self, source_environment=None: list(AUTH_ARGV),
    )


@pytest.fixture
def unit_runner(monkeypatch, fixed_auth):
    """Runner construction without the pinned binary; a CI re-run must not look like a rerun."""
    monkeypatch.setattr(codex_runner, "require_pinned_runtime", lambda: None)
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")


@pytest.fixture
def ledgers(tmp_path):
    """Open ledgers by name under tmp_path and close every one at teardown."""
    opened: list[CostReceiptLedger] = []

    def open_ledger(name: str = "ledger", *, run_id: str = RUN_ID) -> CostReceiptLedger:
        ledger = CostReceiptLedger(tmp_path / f"{name}.sqlite3", run_id=run_id)
        opened.append(ledger)
        return ledger

    yield open_ledger
    for ledger in opened:
        ledger.close()


def _settings(**overrides: Any) -> CodexProviderSettings:
    values: dict[str, Any] = dict(endpoint=ENDPOINT, model="gpt-5.6-sol",
                                  reasoning_effort="max", model_context_window=1_000_000)
    values.update(overrides)
    return CodexProviderSettings(**values)


def _gpt54_settings() -> CodexProviderSettings:
    return _settings(model="gpt-5.4", reasoning_effort=None, model_context_window=None)


def _executor(ledger: CostReceiptLedger, settings: CodexProviderSettings | None = None,
              *, timeout: int = 1800) -> tuple[TaskExecutor, CodexProviderSettings]:
    """The executor step 2 builds for exp036, with the arguments its config gives."""
    settings = settings or _settings()
    executor = TaskExecutor(
        mode="codex_foundry", codex_options={"provider_settings": settings},
        codex_cost_ledger=ledger, timeout=timeout, run_id=RUN_ID, condition_name="condition_a",
    )
    return executor, settings


def _install_kwargs(settings: Any, ledger: Any, workspace: Path, /, **overrides: Any) -> dict[str, Any]:
    """The keywords step 2's hook passes for the registered batch; ``overrides`` replace any of them."""
    values: dict[str, Any] = dict(
        experiment_id=controls.EXPERIMENT_ID, condition_key="condition_a",
        codex_settings=settings, cost_ledger=ledger, run_id=RUN_ID, task_ids=list(TASKS),
        max_retries=3, resume_max_rounds=0, task_deadlines=None, restored_progress=None,
        workspace=workspace,
    )
    values.update(overrides)
    return values


def _session(ledger: Any, record_path: Path, *, seed: Decimal = Decimal(0),
             prior_legs: Decimal = Decimal(0), window_mismatch: bool = False) -> controls.SolBatchSession:
    return controls.SolBatchSession(
        ledger=ledger, rates=controls.load_sol_list_rates(), record_path=record_path,
        seed_usd=seed, prior_legs_usd=prior_legs, window_mismatch=window_mismatch, header={},
    )


def _sol_runner(session: controls.SolBatchSession, ledger: Any) -> controls.SolBatchCodexRunner:
    return controls.SolBatchCodexRunner(
        _settings(), session=session, timeout=1800, cost_ledger=ledger,
        run_id=RUN_ID, condition_name="condition_a",
    )


def _record(path: Path) -> dict:
    def refuse_constant(name: str) -> None:
        raise AssertionError(f"record carries {name}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=refuse_constant)


def _no_record_anywhere(root: Path) -> bool:
    return not any(path.name.startswith("sol_batch_controls_") for path in root.rglob("*"))


# -- (a) (b) inert for other runs, closed for other Sol runs -----------------


@pytest.mark.parametrize("experiment_id", ["exp033_codex_foundry_fixed5", "exp035_codex_foundry_full220", "x"])
def test_install_is_inert_for_a_run_that_does_not_ask_for_sol(tmp_path, capsys, experiment_id):
    sentinel = SimpleNamespace(runner=object())
    runner = sentinel.runner
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    got = controls.install(sentinel, **_install_kwargs(
        _gpt54_settings(), None, workspace, experiment_id=experiment_id, task_ids=[]))

    assert got is None
    assert sentinel.runner is runner and vars(sentinel) == {"runner": runner}
    assert list(workspace.iterdir()) == []
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("model", ["gpt-5.6-sol", "GPT-5.6-Sol", " gpt-5.6-sol-2026-07-09"])
def test_an_unregistered_experiment_asking_for_sol_is_refused(tmp_path, capsys, model):
    sentinel = SimpleNamespace(runner=object())
    runner = sentinel.runner
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(sentinel, **_install_kwargs(
            _settings(model=model), None, workspace, experiment_id="exp037_x"))

    assert str(refused.value) == "sol_batch_unregistered_experiment"
    assert sentinel.runner is runner
    assert list(workspace.iterdir()) == []
    assert capsys.readouterr().out == ""


# -- (c) the one hook in step 2 --------------------------------------------


def test_step2_has_exactly_one_guarded_hook():
    source = (BATCH_RUNNER / "step2_run_inference.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import)
               and any(alias.name == "sol_batch_controls" for alias in node.names)]
    assert len(imports) == 1
    assert not any(isinstance(node, ast.ImportFrom) and node.module == "sol_batch_controls"
                   for node in ast.walk(tree))

    impl = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "_run_inference_impl")
    hooks = [node for node in impl.body if isinstance(node, ast.If) and ast.unparse(node.test)
             == "execution_mode == 'codex_foundry' and pilot_wire_receipts is None"]
    assert len(hooks) == 1
    hook = hooks[0]
    assert imports[0] in list(ast.walk(hook))
    position = impl.body.index(hook)
    owner = next(index for index, node in enumerate(impl.body)
                 if "runtime_resources.own_executor(executor)" in ast.unparse(node))
    assert owner < position
    assert ast.unparse(impl.body[position + 1]).startswith("print(f'   Manifest:")

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and ast.unparse(node.func) == "sol_batch_controls.install"]
    assert len(calls) == 1
    assert [ast.unparse(arg) for arg in calls[0].args] == ["executor"]
    assert {keyword.arg for keyword in calls[0].keywords} == (
        set(inspect.signature(controls.install).parameters) - {"executor"})
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
                  and isinstance(node.value, ast.Name) and node.value.id == "sol_batch_controls"}
    assert attributes == {"install", "SolBatchControlsRefused"}

    constructors = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "codex_settings"
                            for target in node.targets)
                    and isinstance(node.value, ast.Call)
                    and ast.unparse(node.value.func) == "CodexProviderSettings"]
    assert len(constructors) == 1
    # test_the_config_check_does_not_need_the_run_places_credentials indexes
    # the first occurrence of this text; the hook must not move it.
    assert "codex_options=codex_options" not in ast.unparse(hook)


# -- (d) (e) the override tuple and #796 parity -----------------------------


def test_the_sol_provider_appends_only_the_held_catalog(fixed_auth):
    plain = _settings()
    sol = controls.SolLongContextProviderSettings.from_settings(plain)
    catalog = "model_catalog_json=" + _toml_literal(str(controls.CATALOG_PATH))

    assert sol.config_overrides() == (*plain.config_overrides(), catalog)
    assert sol.config_overrides()[-3:] == (
        'model_reasoning_effort="max"', "model_context_window=1000000", catalog)
    assert isinstance(sol, CodexProviderSettings)
    assert {field.name: getattr(sol, field.name) for field in dataclasses.fields(CodexProviderSettings)} == {
        field.name: getattr(plain, field.name) for field in dataclasses.fields(CodexProviderSettings)}
    assert [field.name for field in dataclasses.fields(controls.SolLongContextProviderSettings)] == [
        field.name for field in dataclasses.fields(CodexProviderSettings)]

    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.SolLongContextProviderSettings.from_settings(sol)
    assert str(refused.value) == "sol_batch_provider_type"


def test_the_held_catalog_matches_the_796_pilot():
    import gpt56_pilot_wire_receipt as wire
    import gpt56_sol_codex_pilot_preflight as pilot

    assert controls.CATALOG_RELATIVE == pilot.CODEX_LONG_CONTEXT_CATALOG
    assert controls.CATALOG_SHA256 == pilot.SOURCE_PROFILE_AUXILIARY[pilot.CODEX_LONG_CONTEXT_CATALOG]
    assert controls.CODEX_BUNDLED_SOL_CONTEXT_WINDOW == pilot.CODEX_BUNDLED_SOL_CONTEXT_WINDOW
    assert controls.CATALOG_PATH == pilot.ROOT / pilot.CODEX_LONG_CONTEXT_CATALOG
    assert controls.held_catalog_override() == wire._long_context_catalog(("model_context_window=1000000",))[0]

    catalog = json.loads(controls.CATALOG_PATH.read_text(encoding="utf-8"))
    (sol,) = [model for model in catalog["models"] if model["slug"] == controls.SOL_MODEL]
    assert sol["context_window"] == sol["max_context_window"] == controls.CATALOG_SOL_MAX_CONTEXT_WINDOW == 1_050_000
    assert sol["effective_context_window_percent"] == 100
    assert sol["default_reasoning_level"] == "low"
    assert "max" in {level["effort"] for level in sol["supported_reasoning_levels"]}


# -- (f) price parity --------------------------------------------------------


def test_the_list_rates_are_the_795_meter():
    import gpt56_pilot_usd_budget as shared

    rates = controls.load_sol_list_rates()
    assert (rates.input, rates.cached_input, rates.cache_write, rates.output) == (
        Decimal("10.00"), Decimal("1.00"), Decimal("12.50"), Decimal("45.00"))
    assert controls.PRICE_TABLE_SHA256 == shared.PRICE_SHA256
    assert controls.SOL_METER == shared.LIST_PRICE_METER
    assert {"input": rates.input, "output": rates.output, "cache_write": rates.cache_write} == (
        shared.SOL_LIST_USD_PER_MILLION)
    table = json.loads(Path(controls.PRICE_TABLE_PATH).read_text(encoding="utf-8"))
    assert "azure:gpt-5.6-sol" not in table["providers"]


def test_a_changed_price_table_refuses(tmp_path):
    changed = tmp_path / "model_price_table.json"
    changed.write_bytes(Path(controls.PRICE_TABLE_PATH).read_bytes() + b" ")
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.load_sol_list_rates(changed)
    assert str(refused.value) == "sol_batch_price_table_unverified"


# -- (g) (h) catalog reads and request drift --------------------------------


def _catalog_copy(tmp_path: Path) -> Path:
    copy = tmp_path / "catalog" / "models.json"
    copy.parent.mkdir()
    shutil.copyfile(controls.CATALOG_PATH, copy)
    return copy


def test_a_plain_copy_of_the_held_catalog_is_accepted(tmp_path, monkeypatch):
    copy = _catalog_copy(tmp_path)
    monkeypatch.setattr(controls, "CATALOG_PATH", copy)
    assert controls.held_catalog_override() == "model_catalog_json=" + _toml_literal(str(copy))


@pytest.mark.parametrize("shape", ["symlink", "hard_link", "changed_byte", "missing"])
def test_a_catalog_that_is_not_the_held_file_refuses(tmp_path, monkeypatch, shape):
    copy = _catalog_copy(tmp_path)
    target = copy
    if shape == "symlink":
        target = tmp_path / "catalog-link.json"
        target.symlink_to(copy)
    elif shape == "hard_link":
        os.link(copy, tmp_path / "second-name.json")
    elif shape == "changed_byte":
        data = bytearray(copy.read_bytes())
        data[100] ^= 0x01
        copy.write_bytes(bytes(data))
    else:
        target = tmp_path / "absent.json"
    monkeypatch.setattr(controls, "CATALOG_PATH", target)

    with pytest.raises(controls.SolLongContextRefused) as refused:
        controls.held_catalog_override()
    assert str(refused.value) == "sol_batch_catalog_unverified"


@pytest.mark.parametrize("drift", [
    dict(model="gpt-5.4"),
    dict(reasoning_effort=None), dict(reasoning_effort="low"), dict(reasoning_effort="xhigh"),
    dict(model_context_window=None), dict(model_context_window=272_000),
    dict(model_context_window=999_999), dict(model_context_window=1_050_001),
    dict(request_max_retries=1), dict(stream_max_retries=1),
])
def test_a_drifted_request_refuses_the_sol_provider(drift):
    with pytest.raises(controls.SolLongContextRefused) as refused:
        controls.SolLongContextProviderSettings.from_settings(_settings(**drift))
    assert str(refused.value) == "sol_batch_request_drift"


_REQUESTED = requested_model_config_overrides(reasoning_effort="max", model_context_window=1_000_000)


@pytest.mark.parametrize("base", [
    ('model_catalog_json="elsewhere.json"', *_REQUESTED),
    ("model_context_window=1000000", *_REQUESTED),
    ('model_reasoning_effort="max"', *_REQUESTED),
    (*_REQUESTED, "x=1"),
    tuple(reversed(_REQUESTED)),
    ('model_reasoning_effort="max"', "model_context_window=272000"),
    ("x=1",),
    (),
])
def test_an_override_tuple_that_restates_or_omits_the_request_refuses(base):
    with pytest.raises(controls.SolLongContextRefused) as refused:
        controls.sol_overrides(base)
    assert str(refused.value) == "sol_batch_override_drift"
    assert controls.sol_overrides(("x=1", *_REQUESTED))[-1].startswith("model_catalog_json=")


# -- (i) (j) install against a real TaskExecutor ----------------------------


class _RunnerSubclass(CodexAgentRunner):
    pass


def _refusal_case(name: str, executor: TaskExecutor, settings: CodexProviderSettings,
                  ledger: CostReceiptLedger, ledgers, tmp_path: Path, monkeypatch) -> tuple[dict, str]:
    """The keyword overrides (after any executor change) and the code each case must refuse with."""
    if name == "condition_b":
        return dict(condition_key="condition_b"), "sol_batch_condition_refused"
    if name == "task_deadlines":
        return dict(task_deadlines={TASKS[0]: 1800}), "sol_batch_deadline_refused"
    if name == "ledger_none":
        return dict(cost_ledger=None), "sol_batch_ledger_drift"
    if name == "ledger_different":
        return dict(cost_ledger=ledgers("other")), "sol_batch_ledger_drift"
    if name == "runner_subclass":
        executor.runner = _RunnerSubclass(settings, timeout=1800, cost_ledger=ledger,
                                          run_id=RUN_ID, condition_name="condition_a")
        return {}, "sol_batch_runner_drift"
    if name == "provider_not_codex_settings":
        return dict(codex_settings=_settings()), "sol_batch_runner_drift"
    if name == "four_ids":
        return dict(task_ids=list(TASKS[:4])), "sol_batch_task_set_drift"
    if name == "reordered_ids":
        return dict(task_ids=list(reversed(TASKS))), "sol_batch_task_set_drift"
    if name == "max_retries_2":
        return dict(max_retries=2), "sol_batch_retry_policy_drift"
    if name == "resume_rounds_3":
        return dict(resume_max_rounds=3), "sol_batch_retry_policy_drift"
    if name == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
        return {}, "sol_batch_rerun_refused"
    if name == "unwritable_workspace":
        not_a_directory = tmp_path / "workspace-is-a-file"
        not_a_directory.write_text("", encoding="utf-8")
        return dict(workspace=not_a_directory), "sol_batch_record_unwritable"
    if name == "model_gpt54":
        return dict(codex_settings=_gpt54_settings()), "sol_batch_model_drift"
    raise AssertionError(name)


@pytest.mark.parametrize("name", [
    "condition_b", "task_deadlines", "ledger_none", "ledger_different", "runner_subclass",
    "provider_not_codex_settings", "four_ids", "reordered_ids", "max_retries_2",
    "resume_rounds_3", "rerun", "unwritable_workspace", "model_gpt54",
])
def test_install_refuses_a_drifted_registered_run_and_changes_nothing(
        tmp_path, monkeypatch, unit_runner, ledgers, name):
    ledger = ledgers()
    executor, settings = _executor(ledger)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    overrides, code = _refusal_case(name, executor, settings, ledger, ledgers, tmp_path, monkeypatch)
    runner = executor.runner

    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(settings, ledger, workspace, **overrides))

    assert str(refused.value) == code
    assert executor.runner is runner
    assert list(workspace.iterdir()) == []
    assert _no_record_anywhere(tmp_path)


def test_install_refuses_a_ledger_for_another_run(tmp_path, unit_runner, ledgers):
    ledger = ledgers(run_id="exp036_sol_fixed5:1:1")
    executor, settings = _executor(ledger)
    runner = executor.runner
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(settings, ledger, tmp_path))
    assert str(refused.value) == "sol_batch_ledger_drift"
    assert executor.runner is runner and _no_record_anywhere(tmp_path)


def test_install_refuses_a_turn_limit_other_than_the_reserve_was_sized_for(tmp_path, unit_runner, ledgers):
    ledger = ledgers()
    executor, settings = _executor(ledger, timeout=900)
    runner = executor.runner
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(settings, ledger, tmp_path))
    assert str(refused.value) == "sol_batch_timeout_drift"
    assert executor.runner is runner and _no_record_anywhere(tmp_path)


def test_install_refuses_when_the_held_catalog_changed(tmp_path, monkeypatch, unit_runner, ledgers):
    copy = _catalog_copy(tmp_path)
    copy.write_bytes(copy.read_bytes() + b"\n")
    monkeypatch.setattr(controls, "CATALOG_PATH", copy)
    ledger = ledgers()
    executor, settings = _executor(ledger)
    runner = executor.runner
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(settings, ledger, tmp_path))
    assert str(refused.value) == "sol_batch_catalog_unverified"
    assert executor.runner is runner and _no_record_anywhere(tmp_path)


def test_install_swaps_in_the_gated_runner_with_the_executors_own_arguments(
        tmp_path, capsys, unit_runner, ledgers):
    ledger = ledgers()
    executor, settings = _executor(ledger)
    original = executor.runner
    assert type(original) is CodexAgentRunner

    session = controls.install(executor, **_install_kwargs(settings, ledger, tmp_path))

    runner = executor.runner
    assert type(runner) is controls.SolBatchCodexRunner
    assert type(runner.provider) is controls.SolLongContextProviderSettings
    assert {field.name: getattr(runner.provider, field.name) for field in dataclasses.fields(CodexProviderSettings)} == {
        field.name: getattr(original.provider, field.name) for field in dataclasses.fields(CodexProviderSettings)}
    assert runner.timeout == original.timeout == controls.ATTEMPT_TIMEOUT_SECONDS
    assert runner.cost_ledger is original.cost_ledger is ledger
    assert (runner.run_id, runner.condition_name, runner.preflight_auth) == (
        original.run_id, original.condition_name, original.preflight_auth)
    assert runner._sol_session is session
    assert session.seed_usd == 0 and session.window_mismatch is False

    path = tmp_path / RECORD_NAME
    raw = path.read_bytes()
    record = _record(path)
    assert set(record) == {"schema", "header", "attempts", "summary"}
    assert record["schema"] == controls.RECORD_SCHEMA and record["attempts"] == [] and record["summary"] is None
    header = record["header"]
    assert {"schema", "experiment_id", "run_id", "condition_key", "github", "relay_lineage_id",
            "restored_progress", "codex", "requested", "catalog", "added_codex_overrides", "usd",
            "sources", "window_rule", "evidence_boundary"} <= set(header)
    assert header["requested"] == {"model": "gpt-5.6-sol", "reasoning_effort": "max",
                                   "model_context_window": 1_000_000}
    assert header["usd"]["admit_while_spend_at_most"] == "95.00000000"
    assert header["usd"]["solve_budget"] == "146.00000000"
    assert header["catalog"]["sha256"] == controls.CATALOG_SHA256
    assert header["evidence_boundary"] == controls.EVIDENCE_BOUNDARY
    for secret in (b"fixture-host", b"openai.azure.com", *(part.encode() for part in AUTH_ARGV)):
        assert secret not in raw

    banner = capsys.readouterr().out
    assert "controls on for exp036_sol_fixed5" in banner and "95.00" in banner
    assert controls.CATALOG_SHA256[:12] in banner and str(path) in banner
    assert "fixture-host" not in banner and AUTH_ARGV[1] not in banner


# -- (k) (l) (m) pricing and the admission boundary -------------------------


def test_the_exp033_fixture_ledger_prices_at_the_independently_computed_amount(tmp_path, ledgers):
    anchor = ledgers("anchor", run_id="exp033_codex_foundry_fixed5:34528903950:1")
    anchor.import_jsonl(ANCHOR_LEDGER)

    # Recomputed here from the fixture alone, at the meter's per-1M rates:
    # writes = input - cached, reasoning inside output, each turn rounded up
    # to eight places as the ledger rounds money.
    rows = [json.loads(line) for line in ANCHOR_LEDGER.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 9 and {row["state"] for row in rows} == {"settled"}
    expected = Decimal(0)
    for row in rows:
        uncached = row["input_tokens"] - row["cached_input_tokens"]
        turn = (Decimal(uncached) * Decimal("10.00") + Decimal(row["cached_input_tokens"]) * Decimal("1.00")
                + Decimal(row["output_tokens"]) * Decimal("45.00") + Decimal(uncached) * Decimal("12.50"))
        expected += (turn / Decimal(1_000_000)).quantize(Decimal("0.00000001"), rounding=ROUND_CEILING)
    assert expected == Decimal("5.42008050")

    assert _session(anchor, tmp_path / "anchor.json").spend_usd() == Decimal("5.42008050")
    other_run = ledgers("anchor", run_id="another-run")
    assert _session(other_run, tmp_path / "other.json").spend_usd() == 0


RATES = SimpleNamespace(input=Decimal("10.00"), cached_input=Decimal("1.00"),
                        cache_write=Decimal("12.50"), output=Decimal("45.00"))
SETTLED = {"call_id": "a", "state": STATE_SETTLED, "input_tokens": 100_000,
           "cached_input_tokens": 40_000, "output_tokens": 2_000, "reasoning_tokens": 500}


@pytest.mark.parametrize("row, evidence, booked", [
    # 60k x 10 + 40k x 1 + 2k x 45 + 60k writes x 12.50, per 1M.
    (SETTLED, None, (Decimal("1.48000000"), "settled")),
    ({"state": STATE_RESERVED}, None, (Decimal("51"), "usage_unreported")),
    ({"state": STATE_RESERVED}, {"error_category": "rate_limited", "items_seen": 0},
     (Decimal("7.20"), "rate_limited_first_request")),
    ({"state": STATE_RESERVED}, {"error_category": "rate_limited", "items_seen": 4},
     (Decimal("51"), "usage_unreported")),
    ({"state": STATE_RESERVED}, {"error_category": "rate_limited", "items_seen": False},
     (Decimal("51"), "usage_unreported")),
    ({"state": STATE_RESERVED}, {"error_category": "turn_failed", "items_seen": 0},
     (Decimal("51"), "usage_unreported")),
    ({"state": STATE_ABANDONED}, None, (Decimal(0), "abandoned")),
    ({"state": STATE_REFUSED}, None, (Decimal("7.20"), "refused_request")),
    ({"state": STATE_SETTLED, "input_tokens": None, "cached_input_tokens": None,
      "output_tokens": None, "reasoning_tokens": None}, None, (Decimal("51"), "settled_without_usage")),
    (dict(SETTLED, input_tokens=None), None, (Decimal("51"), "settled_without_usage")),
    (dict(SETTLED, output_tokens=None), None, (Decimal("51"), "settled_without_usage")),
    (dict(SETTLED, cached_input_tokens=100_001), None, (Decimal("51"), "settled_without_usage")),
    (dict(SETTLED, reasoning_tokens=2_001), None, (Decimal("51"), "settled_without_usage")),
    # A reported write count above the bound is used: 70k x 12.50 instead of 60k.
    (SETTLED, {"cache_write_input_tokens": 70_000}, (Decimal("1.60500000"), "settled")),
    # A smaller reported count does not lower the bound.
    (SETTLED, {"cache_write_input_tokens": 10}, (Decimal("1.48000000"), "settled")),
])
def test_book_row(row, evidence, booked):
    assert controls.book_row(row, rates=RATES, evidence=evidence) == booked


def test_reasoning_never_adds_to_a_settled_turn():
    priced = {reasoning: controls.list_price_usd(
        input_tokens=100_000, cached_input_tokens=40_000, output_tokens=2_000,
        reasoning_tokens=reasoning, rates=RATES) for reasoning in (None, 0, 500, 2_000)}
    assert set(priced.values()) == {Decimal("1.48000000")}
    # No cached count is zero cached tokens, not an unpriceable turn.
    assert controls.list_price_usd(input_tokens=10, cached_input_tokens=None, output_tokens=0,
                                   rates=RATES) == Decimal("0.00022500")


def test_the_rates_reach_the_price_unchanged():
    assert controls.list_price_usd(input_tokens=1_000_000, cached_input_tokens=0, output_tokens=0,
                                   rates=controls.load_sol_list_rates()) == Decimal("22.50000000")
    assert controls.list_price_usd(input_tokens=1_000_000, cached_input_tokens=1_000_000,
                                   output_tokens=1_000_000, rates=controls.load_sol_list_rates()) == Decimal("46.00000000")


@pytest.mark.parametrize("seed, code", [
    (Decimal("95.00000000"), None),
    (Decimal("95.00000001"), controls.USD_CEILING_REACHED),
    (Decimal(0), None),
])
def test_admission_boundary(tmp_path, ledgers, seed, code):
    refusal, decision = _session(ledgers(), tmp_path / "r.json", seed=seed).admit(TASKS[0])
    assert refusal == code
    assert decision == {"spend_before_usd": controls.fmt(seed), "reserve_usd": "51.00000000",
                        "solve_budget_usd": "146.00000000"}


def test_admission_counts_unreported_rows_at_the_reserve(tmp_path, unit_runner, ledgers):
    ledger = ledgers()
    executor, _ = _executor(ledger)
    executor.runner._reserve_call(TASKS[0])
    assert _session(ledger, tmp_path / "r.json", seed=Decimal(44)).admit(TASKS[1])[0] is None
    executor.runner._reserve_call(TASKS[0])
    assert _session(ledger, tmp_path / "r.json").admit(TASKS[1])[0] == controls.USD_CEILING_REACHED


def test_an_unreadable_ledger_refuses_rather_than_guesses(tmp_path):
    class Broken:
        run_id = RUN_ID

        def task_ids(self):
            raise OSError("ledger unreadable")

    assert _session(Broken(), tmp_path / "r.json").admit(TASKS[0]) == (controls.GATE_UNVERIFIED, {})


# -- (n) a refusal starts nothing -------------------------------------------


def test_a_refused_attempt_starts_nothing(tmp_path, monkeypatch, native_hosted_runner, unit_runner, ledgers):
    started: list[str] = []

    def forbidden(name):
        def start(*args, **kwargs):
            started.append(name)
            raise AssertionError(f"{name} ran for a refused attempt")
        return start

    monkeypatch.setattr(CodexAgentRunner, "_run", forbidden("_run"))
    monkeypatch.setattr(CodexAgentRunner, "open_runtime", forbidden("open_runtime"))
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    runner = _sol_runner(_session(ledger, record_path, seed=Decimal("95.00000001")), ledger)

    result = runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])

    assert started == []
    assert result["success"] is False
    assert result["error"] == result["error_category"] == controls.USD_CEILING_REACHED
    runner_environment.validate_receipt(result["runner_evidence"])
    assert result["runner_evidence"]["stage"] == "inference"
    assert result["budget_metrics"] == {"conservative_cost_usd": "0.00000000", "usage_complete": True}
    assert ledger.calls_for(TASKS[0]) == []
    last = _record(record_path)["attempts"][-1]
    assert last["admitted"] is False and last["refusal"] == controls.USD_CEILING_REACHED
    assert last["spend_before_usd"] == "95.00000001"

    observability = step2._build_execution_observability(result, [])
    assert observability["error_category"] == controls.USD_CEILING_REACHED
    assert observability["budget_metrics"]["conservative_cost_usd"] == 0.0
    row = {"task_id": TASKS[0], "status": "error", "error": result["error"], "observability": observability}
    assert step2.infra_retry_category(row) is None
    for code in (controls.USD_CEILING_REACHED, controls.WINDOW_MISMATCH, controls.GATE_UNVERIFIED):
        assert len(code) <= 80 and code not in step2.RETRYABLE_INFRA_ERROR_CATEGORIES


# -- (o) the window rule ----------------------------------------------------


def _scripted_parent(monkeypatch, window: int | None) -> None:
    """Stand in for CodexAgentRunner's turn: one reserved row, one usage report, one settlement."""
    usage = SimpleNamespace(
        model_context_window=window, last=SimpleNamespace(input_tokens=60_000),
        total=SimpleNamespace(input_tokens=100_000, cached_input_tokens=40_000,
                              cache_write_input_tokens=70_000, output_tokens=2_000,
                              reasoning_output_tokens=500))

    def await_turn(self, turn_handle, **kwargs):
        return TurnObservation(result=SimpleNamespace(usage=usage), usage=usage, items_seen=3)

    def run(self, task_prompt, model=None, reference_files=None, occupation="professional",
            experiment_prompt=None, perception_text=None, run_id=None, condition_name=None, task_id=None):
        call_id = self._reserve_call(task_id)
        self._await_turn(object())
        settle_codex_turn(self.cost_ledger, call_id, totals=CodexTokenTotals(
            input_tokens=100_000, cached_input_tokens=40_000, cache_write_input_tokens=70_000,
            output_tokens=2_000, reasoning_output_tokens=500), resolved_model=self.provider.model)
        return {"success": True, "text": "ok", "files": [],
                "codex_diagnostics": {"items_seen": 3}}

    monkeypatch.setattr(CodexAgentRunner, "_await_turn", await_turn)
    monkeypatch.setattr(CodexAgentRunner, "run", run)


@pytest.mark.parametrize("window, stops", [(258_400, True), (1_000_000, False), (None, False)])
def test_an_app_server_window_other_than_1m_stops_further_attempts(
        tmp_path, monkeypatch, unit_runner, ledgers, window, stops):
    _scripted_parent(monkeypatch, window)
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    session = _session(ledger, record_path)
    runner = _sol_runner(session, ledger)

    result = runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])

    assert result["success"] is True
    assert result["budget_metrics"] == {"conservative_cost_usd": "1.60500000", "usage_complete": True}
    attempt = _record(record_path)["attempts"][-1]
    assert attempt["admitted"] is True and attempt["basis"] == "settled"
    assert attempt["booked_usd"] == attempt["spend_after_usd"] == "1.60500000"
    assert attempt["app_server"] == {"usage_observed": True, "model_context_window": window,
                                     "last_request_input_tokens": 60_000}
    assert attempt["window_matches_request"] is (None if window is None else window == 1_000_000)
    assert session.window_mismatch is stops
    assert session.admit(TASKS[1])[0] == (controls.WINDOW_MISMATCH if stops else None)

    following = runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[1])
    assert following["success"] is not stops
    if stops:
        assert following["error_category"] == controls.WINDOW_MISMATCH
        assert ledger.calls_for(TASKS[1]) == []


def test_an_attempt_that_raises_still_carries_its_booking(tmp_path, monkeypatch, unit_runner, ledgers):
    def run(self, task_prompt, task_id=None, **kwargs):
        self._reserve_call(task_id)
        raise RuntimeError("runtime went away")

    monkeypatch.setattr(CodexAgentRunner, "run", run)
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    runner = _sol_runner(_session(ledger, record_path), ledger)

    result = runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])

    # The dict TaskExecutor.execute builds for a runner that raises.
    assert result["success"] is False
    assert result["error"] == "Executor error (codex_foundry): runtime went away"
    assert result["budget_metrics"] == {"conservative_cost_usd": "51.00000000", "usage_complete": False}
    attempt = _record(record_path)["attempts"][-1]
    assert attempt["admitted"] is True and attempt["basis"] == "usage_unreported"
    assert attempt["booked_usd"] == attempt["spend_after_usd"] == "51.00000000"
    assert attempt["app_server"]["usage_observed"] is False


@pytest.mark.parametrize("items_seen, booked, basis", [
    (0, "7.20000000", "rate_limited_first_request"),
    (2, "51.00000000", "usage_unreported"),
])
def test_a_rate_refusal_is_booked_from_what_the_attempt_reported(
        tmp_path, monkeypatch, unit_runner, ledgers, items_seen, booked, basis):
    def run(self, task_prompt, task_id=None, **kwargs):
        self._reserve_call(task_id)  # left reserved: the stream reported no usage
        return {"success": False, "text": "", "files": [], "error": "429",
                "error_category": "rate_limited", "codex_diagnostics": {"items_seen": items_seen}}

    monkeypatch.setattr(CodexAgentRunner, "run", run)
    ledger = ledgers()
    record_path = tmp_path / "r.json"
    session = _session(ledger, record_path)
    runner = _sol_runner(session, ledger)

    result = runner.run("prompt", model="gpt-5.6-sol", task_id=TASKS[0])

    assert result["budget_metrics"] == {"conservative_cost_usd": booked, "usage_complete": False}
    attempt = _record(record_path)["attempts"][-1]
    assert (attempt["basis"], attempt["booked_usd"], attempt["error_category"]) == (basis, booked, "rate_limited")
    assert session.spend_usd() == Decimal(booked)


def test_a_restored_window_mismatch_keeps_the_next_leg_closed(tmp_path, unit_runner, ledgers):
    ledger = ledgers()
    executor, settings = _executor(ledger)
    restored = {"results": [{
        "task_id": TASKS[0], "status": "error", "error": controls.WINDOW_MISMATCH,
        "observability": {"error_category": controls.WINDOW_MISMATCH,
                          "budget_metrics": {"conservative_cost_usd": 0.0}},
    }]}

    session = controls.install(executor, **_install_kwargs(settings, ledger, tmp_path, restored_progress=restored))

    assert session.window_mismatch is True
    assert session.admit(TASKS[1])[0] == controls.WINDOW_MISMATCH


# -- (p) spend carried across relay legs ------------------------------------


def _row(task_id: str, status: str, observability: Any = None) -> dict:
    row: dict[str, Any] = {"task_id": task_id, "status": status}
    if observability is not None:
        row["observability"] = observability
    return row


def test_prior_legs_are_summed_from_their_budget_metrics():
    rows = [
        _row("a", "success", {"budget_metrics": {"conservative_cost_usd": 12.5}}),
        _row("b", "error", {"budget_metrics": {"conservative_cost_usd": "0.75"}}),
        _row("c", "pending", {"runner_evidence": {}}),
        _row("d", "error", {"error_category": "reference_input_integrity_failed"}),
        _row("e", "error"),
        "not a row",
    ]
    assert controls.booked_from_rows(rows) == (Decimal("13.25"), ["a", "b"])
    assert controls.solve_spend_usd(rows) == controls.PRIOR_LINEAGE_SPEND_USD + Decimal("13.25")


@pytest.mark.parametrize("observability", [
    {"runner_evidence": {"stage": "inference"}},
    {"runner_evidence": {}, "budget_metrics": {"usage_complete": True}},
    {"budget_metrics": {"conservative_cost_usd": True}},
    {"budget_metrics": {"conservative_cost_usd": "nan"}},
    {"budget_metrics": {"conservative_cost_usd": "Infinity"}},
    {"budget_metrics": {"conservative_cost_usd": -1}},
    {"budget_metrics": {"conservative_cost_usd": None}},
    ["not", "a", "dict"],
])
def test_a_row_that_reached_the_runner_without_a_booking_refuses(observability):
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.booked_from_rows([_row("a", "error", observability)])
    assert str(refused.value) == "sol_batch_prior_spend_unaccounted"


def test_install_seeds_from_prior_legs_once_and_skips_tasks_already_in_the_ledger(
        tmp_path, monkeypatch, unit_runner, ledgers):
    monkeypatch.setattr(controls, "PRIOR_LINEAGE_SPEND_USD", Decimal("3"))
    ledger = ledgers()
    executor, settings = _executor(ledger)
    executor.runner._reserve_call(TASKS[0])  # a live row: counted from the ledger at 51
    restored = {"results": [
        _row(TASKS[0], "error", {"budget_metrics": {"conservative_cost_usd": 10.0}}),
        _row(TASKS[1], "success", {"budget_metrics": {"conservative_cost_usd": 2.5},
                                    "runner_evidence": {}}),
        _row(TASKS[2], "pending"),
        _row(TASKS[3], "error", {"error_category": "reference_input_integrity_failed"}),
    ]}

    session = controls.install(executor, **_install_kwargs(settings, ledger, tmp_path, restored_progress=restored))

    assert session.prior_legs_usd == Decimal("2.5")
    assert session.seed_usd == Decimal("5.5")
    assert session.spend_usd() == Decimal("56.5")
    usd = _record(tmp_path / RECORD_NAME)["header"]["usd"]
    assert usd["prior_lineage_spend_usd"] == "3.00000000"
    assert usd["prior_legs_spend_usd"] == "2.50000000"
    assert usd["prior_leg_tasks"] == [TASKS[1]]
    session.finish()
    summary = _record(tmp_path / RECORD_NAME)["summary"]
    assert summary["prior_lineage_spend_usd"] == "3.00000000"
    assert summary["prior_legs_spend_usd"] == "2.50000000"
    assert summary["this_leg_spend_usd"] == "51.00000000"
    assert summary["solve_spend_usd"] == "56.50000000"
    assert summary["remaining_under_ceiling_usd"] == "143.50000000"


def test_install_refuses_a_prior_leg_row_without_a_booking(tmp_path, unit_runner, ledgers):
    ledger = ledgers()
    executor, settings = _executor(ledger)
    runner = executor.runner
    restored = {"results": [_row(TASKS[0], "error", {"runner_evidence": {}})]}
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(settings, ledger, tmp_path, restored_progress=restored))
    assert str(refused.value) == "sol_batch_prior_spend_unaccounted"
    assert executor.runner is runner and _no_record_anywhere(tmp_path)


# -- (q) the private-method contract ----------------------------------------


def test_the_private_method_contract_this_module_relies_on():
    assert list(inspect.signature(CodexAgentRunner._await_turn).parameters) == [
        "self", "turn_handle", "task_deadline", "observation_control", "observed", "pilot_wire_observer"]
    assert "usage" in {field.name for field in dataclasses.fields(TurnObservation)}
    assert "self._await_turn(turn_handle" in inspect.getsource(CodexAgentRunner._run_one_turn)
    assert inspect.signature(controls.SolBatchCodexRunner.run) == inspect.signature(CodexAgentRunner.run)
    assert inspect.signature(controls.SolBatchCodexRunner.run, eval_str=True) == (
        inspect.signature(CodexAgentRunner.run, eval_str=True))
    assert isinstance(inspect.getattr_static(CodexAgentRunner, "_failure"), staticmethod)


# -- (r) the record never stops a run ---------------------------------------


def test_a_record_that_cannot_be_written_never_raises(tmp_path, capsys, ledgers):
    directory = tmp_path / "record-is-a-directory"
    directory.mkdir()
    session = _session(ledgers(), directory)

    session.record_refusal(TASKS[0], controls.USD_CEILING_REACHED, {"spend_before_usd": "95.00000001"})
    session.book_attempt(task_id=TASKS[1], before=frozenset(), decision={}, result=None, usage=None)
    session.finish()
    session.finish()

    assert "record not written" in capsys.readouterr().out
    assert [row["admitted"] for row in session.attempts] == [False, True]
    assert session.summary is not None and session.summary["attempts_refused"] == 1
    assert list(tmp_path.glob("*.tmp")) == []
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        session._write(strict=True)
    assert str(refused.value) == "sol_batch_record_unwritable"


def test_a_record_that_cannot_be_serialised_only_warns(tmp_path, capsys, ledgers):
    session = controls.SolBatchSession(
        ledger=ledgers(), rates=controls.load_sol_list_rates(), record_path=tmp_path / "r.json",
        seed_usd=Decimal(0), prior_legs_usd=Decimal(0), window_mismatch=False,
        header={"not_json": float("nan")})
    session.finish()
    assert "record not written (ValueError)" in capsys.readouterr().out
    assert not (tmp_path / "r.json").exists() and list(tmp_path.glob("*.tmp")) == []


def test_a_booking_that_cannot_read_the_ledger_is_recorded_not_raised(tmp_path, capsys, ledgers):
    session = _session(ledgers(), tmp_path / "r.json")
    session.book_attempt(task_id=TASKS[0], before=None, decision={"spend_before_usd": "0.00000000"},
                         result={"success": True}, usage=None)
    attempt = _record(tmp_path / "r.json")["attempts"][-1]
    assert attempt["admitted"] is True and attempt["booking_error"] == "ValueError"
    assert "booking failed" in capsys.readouterr().out
    assert session.task_budget(TASKS[0]) == {"conservative_cost_usd": "0.00000000", "usage_complete": True}


# -- (s) the real pinned Codex against a loopback server --------------------


@pytest.mark.skipif(
    _RUNTIME_PROBLEM is not None,
    reason=f"the pinned Codex runtime is not installed: {_RUNTIME_PROBLEM}",
)
@pytest.mark.parametrize("with_catalog, window", [(True, 1_000_000), (False, 258_400)])
def test_loopback_codex_reports_the_window_the_held_catalog_sets(
        tmp_path, native_hosted_runner, ledgers, with_catalog, window):
    @dataclasses.dataclass(frozen=True)
    class SolLoopback(LoopbackCodexProvider):
        def config_overrides(self) -> tuple[str, ...]:
            base = (*super().config_overrides(), *requested_model_config_overrides(
                reasoning_effort="max", model_context_window=1_000_000))
            return controls.sol_overrides(base) if with_catalog else base

    ledger = ledgers(run_id="codex-e2e")
    record_path = tmp_path / "r.json"
    session = controls.SolBatchSession(
        ledger=ledger, rates=controls.load_sol_list_rates(), record_path=record_path,
        seed_usd=Decimal(0), prior_legs_usd=Decimal(0), window_mismatch=False, header={})

    with ScriptedResponses([says("done")]) as server:
        provider = SolLoopback(port=server.port, model="gpt-5.6-sol")
        assert provider.config_overrides()[-1].startswith("model_catalog_json=") is with_catalog
        runner = controls.SolBatchCodexRunner(
            provider, session=session, timeout=180, cost_ledger=ledger,
            run_id="codex-e2e", condition_name="condition_a")
        result = runner.run("Reply with the word done.", model="gpt-5.6-sol", task_id="task-e2e")
        runner.close()
        bodies = server.request_bodies()

    assert result["success"] is True, result.get("error")
    assert bodies[0]["model"] == "gpt-5.6-sol"
    assert bodies[0]["reasoning"]["effort"] == "max"
    assert result["budget_metrics"]["usage_complete"] is True
    record = _record(record_path)
    attempt = record["attempts"][-1]
    assert attempt["admitted"] is True and attempt["basis"] == "settled"
    assert attempt["app_server"]["model_context_window"] == window
    assert session.window_mismatch is (window != 1_000_000)
    assert record["summary"]["window_mismatch"] is (window != 1_000_000)


# -- (t) where the module lives and what it may import ----------------------


def test_the_module_sits_outside_core_and_outside_every_seal():
    module = Path(controls.__file__).resolve()
    assert module == (BATCH_RUNNER / "sol_batch_controls.py").resolve()
    roots: set[str] = set()
    for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            roots.add((node.module or "").split(".")[0])
    assert roots - set(sys.stdlib_module_names) == {"core"}

    seal = json.loads((BATCH_RUNNER / "experiments/execution_envelope/gpt56_sol_grader_seal_20261030.json")
                      .read_text(encoding="utf-8"))
    assert not any("sol_batch_controls" in json.dumps(entry) for entry in seal["files"])
    import gpt56_sol_codex_pilot_preflight as pilot
    assert not any("sol_batch_controls" in path for path in pilot.SOURCE_PROFILE_AUXILIARY)
