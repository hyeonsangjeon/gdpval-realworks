"""The registry of Sol runs: exp036 unchanged, exp037 approved at USD 700, exp038 registered only.

Model-free and offline. Every task list is re-derived from the committed
catalogue and the earlier stages' files, never trusted from the registry.
"""

from __future__ import annotations

import dataclasses
import json
import math
import shutil
import socket
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest
import yaml

import sol_batch_controls as controls
import sol_batch_grading as grading
import step8_grade as step8
from core.execution_envelope_tasks import full_run_tasks, load_task_catalog, select_trial_run_tasks
from core.inference_manifest import _ordered_task_ids_sha256

from .test_sol_batch_controls import (  # noqa: F401 - fixtures
    _executor, _install_kwargs, fixed_auth, ledgers, unit_runner,
)

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER.parent
EXPERIMENTS = BATCH_RUNNER / "experiments"
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"
EXP036, EXP037, EXP038 = "exp036_sol_fixed5", "exp037_sol_first25", "exp038_sol_rest195"
INFERENCE_SHA = "b" * 40
#: exp036's measured mean seconds per task (self_report.json at 8708d920).
EXP036_SECONDS_PER_TASK = 390


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in Sol registry tests")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


def _never(what: str):
    def called(*args, **kwargs):
        raise AssertionError(f"{what} must not be reached")
    return called


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _task_ids(experiment_id: str) -> list[str]:
    return _yaml(EXPERIMENTS / f"{experiment_id}.yaml")["data"]["filter"]["task_ids"]


# -- the table ------------------------------------------------------------------


def test_the_registry_is_well_formed_and_both_sides_name_the_same_runs():
    assert controls.registry_problems() == []
    assert set(controls.RUNS) == {EXP036, EXP037, EXP038}
    assert grading.approval_problems() == []
    sol_side = {approval.experiment_id: (approval.config_name, approval.ceiling_usd, approval.approved is not None)
                for approval in grading.APPROVALS if approval.solve_seed == grading.SOLVE_SEED_SOL_BATCH}
    assert sol_side == {run.experiment_id: (run.grading_config_name, run.ceiling_usd, run.approval is not None)
                        for run in controls.RUNS.values()}
    # Grade-only approvals (the exp035 parity regrade) stay out of RUNS, so
    # install() stays inert for exp035.
    assert grading.EXP035_PARITY.experiment_id not in controls.RUNS
    assert controls.NAME_BUDGET_CHARACTERS == grading.NAME_BUDGET_CHARACTERS == 36
    for run in controls.RUNS.values():
        assert len(run.experiment_id) + len(run.grading_config_name) <= controls.NAME_BUDGET_CHARACTERS


def test_exp036_is_registered_exactly_as_pr_799_ran_it():
    run = controls.RUNS[EXP036]
    assert (run.ceiling_usd, run.grading_reserve_usd, run.attempt_reserve_usd) == (
        Decimal("200"), Decimal("54"), Decimal("51"))
    assert (run.solve_budget_usd, run.admit_while_at_most_usd) == (Decimal("146"), Decimal("95"))
    assert run.narrative_allowance_usd == Decimal("2.00")
    assert run.prior_lineage_spend_usd == 0 and dict(run.lost_booking_usd) == {}
    assert run.wall_timeout_minutes == 170 and run.grading_config_name == "exp036_v2_sol_max"
    # The digest exp036's published inference_provenance.json carries.
    assert run.ordered_task_ids_sha256 == controls.ordered_task_ids_sha256(controls.FIXED_TASK_IDS) == (
        "23ede7c52a525584acce5840f69efcb8725ed7523714f5ad92e564cbae7331cd")
    assert tuple(_task_ids(EXP036)) == controls.FIXED_TASK_IDS and run.task_count == 5


#: The owner's words for exp037, quoted on both sides of the twin tables.
EXP037_OWNER_WORDS = ('"셋다 예", 01:55 KST', '"700으로 올려", 12:30 KST')


def test_exp037_holds_the_owner_approved_700():
    run = controls.RUNS[EXP037]
    assert run.approval == 'owner 2026-11-06 ("셋다 예", 01:55 KST; "700으로 올려", 12:30 KST)'
    approved = grading.EXP037_FIRST25.approved
    assert approved.startswith("2026-11-06 owner") and "USD 700" in approved
    for words in EXP037_OWNER_WORDS:
        assert words in approved
    # 700 = 550 solve + 150 grading (the narrative's 2.00 inside the 150).
    assert (run.ceiling_usd, run.grading_reserve_usd, run.attempt_reserve_usd) == (
        Decimal("700"), Decimal("150"), Decimal("51"))
    assert (run.solve_budget_usd, run.admit_while_at_most_usd) == (Decimal("550"), Decimal("499"))
    assert run.narrative_allowance_usd == Decimal("2.00") and run.prior_lineage_spend_usd == 0
    assert grading.EXP037_FIRST25.ceiling_usd == run.ceiling_usd
    # 25 tasks at exp036's measured mean (38.79 / 5) admit the 25th first
    # attempt with about 313 to spare, and a grade at exp035's per-item cost
    # for these 1,205 items (0.0936) plus the narrative fits the 150.
    assert run.admit_while_at_most_usd - 24 * Decimal("38.788156") / 5 > 312
    assert 1205 * Decimal("0.0936") + run.narrative_allowance_usd < run.grading_reserve_usd


def test_exp038_is_registered_but_not_approved():
    run = controls.RUNS[EXP038]
    assert run.approval is None
    assert (run.ceiling_usd, run.grading_reserve_usd, run.attempt_reserve_usd, run.narrative_allowance_usd) == (
        None, None, None, None)


def _patched(monkeypatch, experiment_id: str, **changes) -> controls.SolRun:
    runs = dict(controls.RUNS)
    runs[experiment_id] = dataclasses.replace(runs[experiment_id], **changes)
    monkeypatch.setattr(controls, "RUNS", MappingProxyType(runs))
    return runs[experiment_id]


@pytest.mark.parametrize("changes, field", [
    ({"ordered_task_ids_sha256": "A" * 64}, "ordered_task_ids_sha256"),
    ({"ordered_task_ids_sha256": "g" * 64}, "ordered_task_ids_sha256"),
    ({"ordered_task_ids_sha256": "a" * 63}, "ordered_task_ids_sha256"),
    ({"wall_timeout_minutes": 171}, "wall_timeout_minutes"),
    ({"wall_timeout_minutes": True}, "wall_timeout_minutes"),
    ({"prior_lineage_spend_usd": Decimal("-0.01")}, "prior_lineage_spend_usd"),
    ({"prior_lineage_spend_usd": Decimal("NaN")}, "prior_lineage_spend_usd"),
    ({"prior_lineage_spend_usd": Decimal("Infinity")}, "prior_lineage_spend_usd"),
    ({"prior_lineage_spend_usd": 3.5}, "prior_lineage_spend_usd"),
    ({"lost_booking_usd": {(INFERENCE_SHA, "t"): Decimal("-1")}}, "lost_booking_usd"),
    ({"lost_booking_usd": {(INFERENCE_SHA, "t"): 1.0}}, "lost_booking_usd"),
    ({"lost_booking_usd": {("B" * 40, "t"): Decimal("1")}}, "lost_booking_usd"),
    ({"lost_booking_usd": {("b" * 39, "t"): Decimal("1")}}, "lost_booking_usd"),
    ({"lost_booking_usd": {(INFERENCE_SHA, ""): Decimal("1")}}, "lost_booking_usd"),
    ({"lost_booking_usd": {(INFERENCE_SHA, " t"): Decimal("1")}}, "lost_booking_usd"),
    ({"lost_booking_usd": {"t": Decimal("1")}}, "lost_booking_usd"),
    ({"lost_booking_usd": {(INFERENCE_SHA, "t", "x"): Decimal("1")}}, "lost_booking_usd"),
])
@pytest.mark.parametrize("experiment_id", [EXP037, EXP038])
def test_the_registry_refuses_an_entry_that_would_skew_the_seed(experiment_id, changes, field):
    # The digest must be lowercase hex, and the two values the grade's seed
    # adds must be finite Decimals of at least 0: a negative one would lower it.
    run = dataclasses.replace(controls.RUNS[experiment_id], **changes)
    problems = controls.registry_problems({experiment_id: run})
    assert problems and all(field in problem for problem in problems)


def test_a_zero_lost_booking_and_a_raised_prior_spend_are_well_formed():
    run = dataclasses.replace(controls.RUNS[EXP037], prior_lineage_spend_usd=Decimal("12.5"),
                              lost_booking_usd={(INFERENCE_SHA, _task_ids(EXP037)[0]): Decimal("0")})
    assert controls.registry_problems({EXP037: run}) == []


def test_a_malformed_entry_refuses_the_solve_and_the_grade(tmp_path, monkeypatch, unit_runner, ledgers):
    _patched(monkeypatch, EXP037, prior_lineage_spend_usd=Decimal("-1"))
    ledger = ledgers()
    executor, settings = _executor(ledger)
    runner = executor.runner
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(
            settings, ledger, workspace, experiment_id=EXP037, task_ids=_task_ids(EXP037)))
    assert str(refused.value) == "sol_batch_registry_invalid"
    assert executor.runner is runner and list(workspace.iterdir()) == []
    monkeypatch.chdir(BATCH_RUNNER)
    monkeypatch.setattr(grading, "published_solve", _never("a published solve read"))
    with pytest.raises(grading.CombinedUsdRefused, match="registry entry is incomplete"):
        grading.preflight(EXP037, "grading_configs/exp037_v2_sol_max.yaml", INFERENCE_SHA, 1)


def test_the_digest_is_the_one_inference_provenance_publishes():
    for task_ids in (list(controls.FIXED_TASK_IDS), _task_ids(EXP037), _task_ids(EXP038)):
        assert controls.ordered_task_ids_sha256(task_ids) == _ordered_task_ids_sha256(task_ids)


# -- which tasks ----------------------------------------------------------------


def test_exp037_is_the_first_25_of_the_trial_stage_rule():
    catalog = load_task_catalog()
    rule = list(select_trial_run_tasks(catalog))
    plan = _yaml(EXPERIMENTS / "execution_envelope/advance_check_plan.yaml")
    first25 = _task_ids(EXP037)
    assert first25 == rule[:25] == _task_ids("exp034_codex_foundry_trial30")[:25]
    assert first25 == plan["run_sizes"]["trial_run"]["task_ids"][:25]
    run = controls.RUNS[EXP037]
    assert len(first25) == run.task_count == 25
    assert controls.ordered_task_ids_sha256(first25) == run.ordered_task_ids_sha256
    by_id = {task.task_id: task for task in catalog.sorted_tasks()}
    sectors = {by_id[task].sector for task in first25}
    assert sectors == {task.sector for task in catalog.sorted_tasks()} and len(sectors) == 9
    raw = json.loads((EXPERIMENTS / "execution_envelope/gdpval_task_catalog.json").read_text(encoding="utf-8"))
    items = {task["task_id"]: task["rubric_item_count"] for task in raw["tasks"]}
    assert sum(items[task] for task in first25) == 1205


def test_exp038_is_every_other_task_in_exp035s_order():
    every = list(full_run_tasks(load_task_catalog()))
    assert every == _task_ids("exp035_codex_foundry_full220")
    first25, rest = _task_ids(EXP037), _task_ids(EXP038)
    assert rest == [task for task in every if task not in set(first25)]
    assert set(first25).isdisjoint(rest) and sorted(first25 + rest) == sorted(every)
    run = controls.RUNS[EXP038]
    assert len(rest) == run.task_count == 195
    assert controls.ordered_task_ids_sha256(rest) == run.ordered_task_ids_sha256


# -- the experiment files ---------------------------------------------------------


@pytest.mark.parametrize("experiment_id", [EXP036, EXP037, EXP038])
def test_every_registered_run_is_exp036s_setup_on_its_own_tasks(experiment_id):
    run = controls.RUNS[experiment_id]
    document = _yaml(EXPERIMENTS / f"{experiment_id}.yaml")
    exp033 = _yaml(EXPERIMENTS / "exp033_codex_foundry_fixed5.yaml")
    assert document["experiment"]["id"] == experiment_id
    assert document["data"]["source"] == f"HyeonSang/{experiment_id}"
    # exp033's prompt, byte for byte: no format hint was added anywhere.
    assert document["condition_a"]["prompt"] == exp033["condition_a"]["prompt"]
    assert document["condition_a"]["qa"]["enabled"] is False
    assert document["condition_a"]["model"]["deployment"] == controls.SOL_MODEL
    execution = document["execution"]
    assert execution["mode"] == "codex_foundry"
    assert {key: execution["codex"][key] for key in (
        "model", "reasoning_effort", "model_context_window", "request_max_retries", "stream_max_retries")} == {
        "model": controls.SOL_MODEL, "reasoning_effort": controls.REASONING_EFFORT,
        "model_context_window": controls.CONTEXT_WINDOW, "request_max_retries": 0, "stream_max_retries": 0}
    assert execution["timeout"] == controls.ATTEMPT_TIMEOUT_SECONDS
    assert execution["max_retries"] == controls.MAX_RETRIES and execution["resume_max_rounds"] == 0
    assert execution["install_libreoffice"] is True
    assert execution["wall_timeout"] == run.wall_timeout_minutes == 170
    assert 0 <= execution["relay_max_runs"] <= 10


def test_the_relay_legs_cover_the_measured_rate_with_room():
    legs = {name: _yaml(EXPERIMENTS / f"{name}.yaml")["execution"]["relay_max_runs"] + 1
            for name in (EXP037, EXP038)}
    work_minutes = {name: controls.RUNS[name].task_count * EXP036_SECONDS_PER_TASK / 60 for name in legs}
    # exp037: six legs, room for four times exp036's rate.
    assert legs[EXP037] * 170 >= 4 * work_minutes[EXP037]
    # exp038: exp036's rate needs eight legs (7.5); eleven also cover a
    # quarter more than that rate.
    assert math.ceil(work_minutes[EXP038] / 170) == 8
    assert legs[EXP038] >= math.ceil(1.25 * work_minutes[EXP038] / 170)


@pytest.mark.parametrize("experiment_id", [EXP036, EXP037, EXP038])
def test_every_registered_config_is_the_template_and_fits_the_name_budget(monkeypatch, experiment_id):
    monkeypatch.chdir(BATCH_RUNNER)
    name = controls.RUNS[experiment_id].grading_config_name
    assert {approval.experiment_id: approval.config_name for approval in grading.APPROVALS}[experiment_id] == name
    path = f"grading_configs/{name}.yaml"
    config = _yaml(BATCH_RUNNER / path)
    template = _yaml(BATCH_RUNNER / grading.TEMPLATE)
    assert config["config_name"] == name
    assert all(config[block] == template[block] for block in grading.TEMPLATE_BLOCKS)
    # No pinned subset: the grade covers every published task and is never diagnostic.
    assert "rerun_identity" not in config
    out = grading.check_name_budget(step8, config, path, experiment_id, INFERENCE_SHA)
    assert len(out.stem.encode("utf-8")) + grading.CHECKPOINT_TMP_EXTRA <= grading.NAME_MAX


# -- the solve side ---------------------------------------------------------------


def _install_args(experiment_id: str, task_ids: list[str], workspace: Path, **overrides):
    values = dict(experiment_id=experiment_id, condition_key="condition_a",
                  codex_settings=SimpleNamespace(model="gpt-5.6-sol"), cost_ledger=None,
                  run_id=f"{experiment_id}:1:1", task_ids=task_ids, max_retries=3, resume_max_rounds=0,
                  task_deadlines=None, restored_progress=None, workspace=workspace, wall_timeout=170)
    values.update(overrides)
    return values


def test_a_run_registered_without_approval_is_refused_before_anything(tmp_path, capsys):
    executor = SimpleNamespace(runner=object())
    runner = executor.runner
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_args(EXP038, _task_ids(EXP038), tmp_path))
    assert str(refused.value) == "sol_batch_run_not_approved"
    assert executor.runner is runner and list(tmp_path.iterdir()) == []
    assert capsys.readouterr().out == ""


def test_exp037_installs_only_with_its_own_tasks_and_its_own_money(tmp_path, capsys, unit_runner, ledgers):
    ledger = ledgers()
    executor, settings = _executor(ledger)
    runner = executor.runner
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(controls.SolBatchControlsRefused) as refused:
        controls.install(executor, **_install_kwargs(settings, ledger, workspace, experiment_id=EXP037))
    assert str(refused.value) == "sol_batch_task_set_drift"
    assert executor.runner is runner and list(workspace.iterdir()) == []

    session = controls.install(executor, **_install_kwargs(
        settings, ledger, workspace, experiment_id=EXP037, task_ids=_task_ids(EXP037)))
    assert session.run is controls.RUNS[EXP037] and executor.runner is not runner
    record = json.loads((workspace / "sol_batch_controls_condition_a.json").read_text(encoding="utf-8"))
    assert record["header"]["experiment_id"] == EXP037
    assert record["header"]["registered_run"]["approval"] == controls.RUNS[EXP037].approval
    assert {key: record["header"]["usd"][key] for key in (
        "ceiling", "grading_reserve", "attempt_reserve", "solve_budget", "admit_while_spend_at_most")} == {
        "ceiling": "700.00000000", "grading_reserve": "150.00000000", "attempt_reserve": "51.00000000",
        "solve_budget": "550.00000000", "admit_while_spend_at_most": "499.00000000"}
    banner = capsys.readouterr().out
    assert ('[sol-batch] controls on for exp037_sol_first25 (owner 2026-11-06 ("셋다 예", 01:55 KST; '
            '"700으로 올려", 12:30 KST))') in banner
    assert "USD gate: 700 ceiling − 150 grading = 550 solve budget; 51 reserve per attempt" in banner
    assert "attempts start while booked spend ≤ 499.00" in banner


def test_exp037s_gate_admits_through_499_and_books_unreported_usage_at_51(tmp_path):
    from core.cost_receipts import STATE_RESERVED

    class Ledger:
        run_id = "r"

        def task_ids(self):
            return []

        def calls_for(self, task):
            return []

    run = controls.RUNS[EXP037]
    rates = controls.load_sol_list_rates()

    def session(seed: Decimal) -> controls.SolBatchSession:
        return controls.SolBatchSession(run=run, ledger=Ledger(), rates=rates, record_path=tmp_path / "r.json",
                                        seed_usd=seed, prior_legs_usd=Decimal(0), window_mismatch=False, header={})

    assert session(Decimal("499")).admit("t")[0] is None
    refusal, decision = session(Decimal("499.00000001")).admit("t")
    assert refusal == controls.USD_CEILING_REACHED
    assert decision == {"spend_before_usd": "499.00000001", "reserve_usd": "51.00000000",
                        "solve_budget_usd": "550.00000000"}
    assert controls.book_row({"state": STATE_RESERVED}, rates=rates, reserve=run.attempt_reserve_usd) == (
        Decimal("51"), "usage_unreported")


# -- the grade side ---------------------------------------------------------------


def test_the_unapproved_pair_is_refused_before_any_download(monkeypatch):
    monkeypatch.chdir(BATCH_RUNNER)
    # published_solve binds _fetch as its default when it is defined, so
    # patching _fetch could never fire; trap the readers themselves.
    for name in ("published_solve", "prior_grading", "check_grade_writers", "_fetch"):
        monkeypatch.setattr(grading, name, _never(name))
    for ask in (grading.applies, grading.approval_for):
        with pytest.raises(grading.CombinedUsdRefused, match="registered but not approved for spending"):
            ask(EXP038, "grading_configs/exp038_v2_sol_max.yaml")
    with pytest.raises(grading.CombinedUsdRefused, match="registered but not approved for spending") as refused:
        grading.preflight(EXP038, "grading_configs/exp038_v2_sol_max.yaml", INFERENCE_SHA, 1)
    assert refused.value.code == grading.UNVERIFIED


@pytest.mark.parametrize("narrowing", [["--tasks", "0ed38524-a4ad-405f-9dee-7b2252659aad"], ["--limit", "3"],
                                       ["--tasks", "0ed38524-a4ad-405f-9dee-7b2252659aad", "--limit", "1"]],
                         ids=["tasks", "limit", "both"])
@pytest.mark.parametrize("experiment_id", [EXP037, EXP038])
def test_a_sol_220_grade_cannot_be_narrowed_to_a_subset(tmp_path, monkeypatch, capsys, experiment_id, narrowing):
    # The approval, not the dispatch, defines the scope: a subset would be a
    # _diagnostic/ grade paid under a ceiling sized for the whole stage.
    # Refused from the arguments alone, before the preflight or a journal.
    monkeypatch.chdir(BATCH_RUNNER)
    monkeypatch.setattr(grading, "preflight", _never("the preflight"))
    monkeypatch.setattr(step8, "main", _never("step 8"))
    monkeypatch.setattr(step8, "_repo_root", lambda: tmp_path)
    config = controls.RUNS[experiment_id].grading_config_name
    argv = [experiment_id, "--config", f"grading_configs/{config}.yaml", "--source", "local", *narrowing]
    assert grading.run(argv, INFERENCE_SHA) == grading.REFUSED_EXIT
    refusal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert refusal["reason"] == grading.UNVERIFIED and "whole scope" in refusal["detail"]
    assert not (tmp_path / grading.JOURNAL_DIR).exists()


@pytest.mark.parametrize("experiment_id, config", [
    (EXP037, "exp036_v2_sol_max"), (EXP036, "exp037_v2_sol_max"), (EXP038, "exp037_v2_sol_max"),
    ("exp035_codex_foundry_full220", "exp037_v2_sol_max"),
])
def test_runs_and_configs_only_grade_their_own_pair(monkeypatch, experiment_id, config):
    monkeypatch.chdir(BATCH_RUNNER)
    with pytest.raises(grading.CombinedUsdRefused, match="only grade each other"):
        grading.applies(experiment_id, f"grading_configs/{config}.yaml")


def _publish(tmp_path: Path, experiment_id: str, ordered: list[str], rows: list[str] | None = None):
    report = tmp_path / "self_report.json"
    task_rows = [{"task_id": task, "status": "success",
                  "observability": {"budget_metrics": {"conservative_cost_usd": 1.0}}}
                 for task in (ordered if rows is None else rows)]
    report.write_text(json.dumps({"meta": {"experiment_id": experiment_id, "ordered_task_ids": ordered},
                                  "task_results": task_rows}), encoding="utf-8")
    return lambda repo_id, filename, revision: report if filename == "self_report.json" else None


def test_the_grade_covers_the_whole_registered_task_list_or_refuses(tmp_path):
    run = controls.RUNS[EXP037]
    tasks = _task_ids(EXP037)
    repo = f"HyeonSang/{EXP037}"
    fetch = _publish(tmp_path, EXP037, tasks)
    assert grading.published_solve(repo, INFERENCE_SHA, run, fetch=fetch) == (Decimal(25), Decimal(0), "absent")
    for ordered, rows in ((tasks[:24], None), (list(reversed(tasks)), None), (tasks + tasks[:1], None),
                          (tasks, tasks[:24]), (tasks, list(reversed(tasks)))):
        with pytest.raises(grading.CombinedUsdRefused, match="not the registered one"):
            grading.published_solve(repo, INFERENCE_SHA, run, fetch=_publish(tmp_path, EXP037, ordered, rows))


def _grade(path: Path, run_id: str | None, attempt: str = "1") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    evidence = {} if run_id is None else {"observation": {"run_id": run_id, "run_attempt": attempt}}
    path.write_text(json.dumps({"run_status": "partial", "runner_evidence": evidence}), encoding="utf-8")
    return path


def test_a_committed_grade_whose_run_left_no_journal_refuses_the_next_grade(tmp_path):
    stem = f"{EXP037}__judge_gpt-5_6-sol__exp037_v2_sol_max__cfg_0123456789abcdef__x"
    grades = tmp_path / "data/grades"
    journal = {"path": f"data/grades/_combined_usd/{EXP037}/run-41-1.combined_usd.jsonl"}
    _grade(grades / f"{stem}.json", "41")
    # Its progress files carry no runner evidence and are not grades.
    _grade(grades / "_progress" / f"{stem}__0ed38524-a4ad-405f-9dee-7b2252659aad.json", None)
    grading.check_grade_writers(tmp_path, EXP037, "exp037_v2_sol_max", [journal])
    with pytest.raises(grading.CombinedUsdRefused, match="run 41 attempt 1, whose combined USD journal"):
        grading.check_grade_writers(tmp_path, EXP037, "exp037_v2_sol_max", [])
    _grade(grades / "_diagnostic" / ("a" * 64) / f"{stem}.json", "42")
    with pytest.raises(grading.CombinedUsdRefused, match="run 42"):
        grading.check_grade_writers(tmp_path, EXP037, "exp037_v2_sol_max", [journal])
    both = [journal, {"path": f"data/grades/_combined_usd/{EXP037}/run-42-1.combined_usd.jsonl"}]
    grading.check_grade_writers(tmp_path, EXP037, "exp037_v2_sol_max", both)
    _grade(grades / f"{stem}.json", None)
    with pytest.raises(grading.CombinedUsdRefused, match="names no grading run"):
        grading.check_grade_writers(tmp_path, EXP037, "exp037_v2_sol_max", both)


def test_exp036s_published_grade_names_its_committed_journal():
    _, journals = grading.prior_grading(REPO_ROOT, EXP036)
    grading.check_grade_writers(REPO_ROOT, EXP036, "exp036_v2_sol_max", journals)
    # The first exp036 grade's writer. A later exp036 regrade adds its own
    # journal beside it, which the writer check above must also find.
    assert "run-42039154052-1.combined_usd.jsonl" in [Path(entry["path"]).name for entry in journals]


def test_a_registered_run_is_graded_only_from_the_file_named_after_it(tmp_path, monkeypatch):
    (tmp_path / "experiments").mkdir()
    (tmp_path / "grading_configs").mkdir()
    shutil.copy(EXPERIMENTS / f"{EXP037}.yaml", tmp_path / "experiments" / "exp037_copy.yaml")
    shutil.copy(BATCH_RUNNER / "grading_configs/exp037_v2_sol_max.yaml", tmp_path / "grading_configs")
    monkeypatch.chdir(tmp_path)
    # The copy declares exp037's id, so it finds exp037's approval; the
    # preflight then refuses it before reading anything published, because its
    # journals would open a second, empty directory under the copy's name.
    assert grading.approval_for("exp037_copy", "grading_configs/exp037_v2_sol_max.yaml") is grading.EXP037_FIRST25
    with pytest.raises(grading.CombinedUsdRefused, match="own YAML name"):
        grading.preflight("exp037_copy", "grading_configs/exp037_v2_sol_max.yaml", INFERENCE_SHA, 1)


def test_the_next_chunk_waits_for_this_chunks_journal():
    ordered = _yaml(WORKFLOW)["jobs"]["grade"]["steps"]
    names = [step.get("name") for step in ordered]
    steps = {step.get("name"): step for step in ordered}
    journal = steps["Commit combined solve+grade USD journal"]
    retrigger = steps["Auto-retrigger next chunk (time budget hit)"]
    # What already makes the retrigger wait: the journal step runs first and
    # a failed push fails the job, and the retrigger's `if` names no status
    # function, so GitHub adds success().
    assert names.index(journal["name"]) < names.index(retrigger["name"])
    assert "continue-on-error" not in journal and "continue-on-error" not in retrigger
    assert not any(check in retrigger["if"] for check in ("always()", "failure()", "cancelled()"))
    # The clause that states it where it is used.
    assert journal["id"] == "usd_journal"
    assert "steps.commit_grade.outputs.committed == 'true'" in retrigger["if"]
    assert ("(steps.sol_usd.outputs.enabled != 'true' || steps.usd_journal.outcome == 'success')"
            in retrigger["if"])
