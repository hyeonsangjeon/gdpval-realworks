"""The approval registry in sol_batch_grading: the exp036 Sol batch and the exp035 parity regrade.

Model-free and offline, like test_sol_batch_grading.py, whose helpers and
fixtures this reuses.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

import sol_batch_controls as controls
import sol_batch_grading as grading
import step8_grade as step8

from .test_sol_batch_grading import (  # noqa: F401 - fixtures are found by name
    BATCH_RUNNER,
    WORKFLOW,
    EXP035,
    EXP035_CONFIG,
    EXP035_REVISION,
    EXP036,
    EXP036_CONFIG,
    INFERENCE_SHA,
    REPO_ROOT,
    _good_lines,
    _write_journal,
    in_batch_runner,
    offline,
)

PARITY_CONFIG = "grading_configs/e35par.yaml"
PARITY = grading.EXP035_PARITY
#: The exp036 grade's committed journal at cc256a50 (run 42039154052).
PUBLISHED_EXP036_JOURNAL = (REPO_ROOT / "data/grades/_combined_usd/exp036_sol_fixed5"
                            / "run-42039154052-1.combined_usd.jsonl")


def _parity_config() -> dict:
    return yaml.safe_load((BATCH_RUNNER / PARITY_CONFIG).read_text(encoding="utf-8"))


def _template() -> dict:
    return yaml.safe_load((BATCH_RUNNER / grading.TEMPLATE).read_text(encoding="utf-8"))


def _no_solve_read(*args, **kwargs):
    raise AssertionError("a grading-only approval never reads a published solve spend")


def _never(what: str):
    def called(*args, **kwargs):
        raise AssertionError(f"{what} must not be reached")
    return called


# -- the registry -------------------------------------------------------------


def test_one_approval_per_experiment_and_per_config_and_the_sol_batch_unchanged():
    experiments = [approval.experiment_id for approval in grading.APPROVALS]
    configs = [approval.config_name for approval in grading.APPROVALS]
    assert len(set(experiments)) == len(experiments)
    assert len(set(configs)) == len(configs)
    sol = grading.EXP036_SOL_BATCH
    assert (sol.experiment_id, sol.config_name) == (grading.GRADED_EXPERIMENT_ID, grading.GRADING_CONFIG_NAME)
    assert (sol.experiment_id, sol.ceiling_usd) == (controls.EXPERIMENT_ID, controls.CEILING_USD)
    assert (sol.solve_seed, sol.exclusive_experiment, sol.task_ids_sha256) == (
        grading.SOLVE_SEED_SOL_BATCH, True, None)
    assert PARITY.solve_seed == grading.SOLVE_SEED_NONE and PARITY.exclusive_experiment is False
    # The owner raised the parity stop to USD 200 on 2026-11-06 ("한도 높여.
    # 중간에 멈출 확률 제로로"). Any other figure needs a new dated owner
    # approval, written into this same entry's `approved` with the constant;
    # a second exp035 entry is refused (see APPROVALS).
    assert PARITY.ceiling_usd == grading.EXP035_PARITY_CEILING_USD == Decimal("200")
    assert "USD 200" in PARITY.approved
    assert all(approval.approved for approval in (sol, PARITY))


def test_the_registry_keeps_its_own_rules():
    assert grading.approval_problems() == []
    assert grading.NAME_BUDGET_CHARACTERS == 36


@pytest.mark.parametrize("entries, problem", [
    (lambda: (*grading.APPROVALS, dataclasses.replace(PARITY, experiment_id="exp034_codex_foundry_trial30")),
     "a second approval for the config"),
    (lambda: (*grading.APPROVALS, dataclasses.replace(PARITY, config_name="e35pa2")),
     "a second approval for the experiment"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, config_name="e35par_v2_sol_max")),
     "past 36 characters"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, approved=None)),
     "a ceiling without an approval"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, ceiling_usd=None)),
     "an approval without a positive ceiling"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, ceiling_usd=Decimal("0"))),
     "an approval without a positive ceiling"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, task_ids_sha256=None)),
     "pins its inference revision and task scope"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, inference_revision=None)),
     "pins its inference revision and task scope"),
    (lambda: (dataclasses.replace(grading.EXP036_SOL_BATCH, task_ids_sha256="0" * 64), PARITY),
     "takes its scope from sol_batch_controls"),
    (lambda: (dataclasses.replace(grading.EXP036_SOL_BATCH, exclusive_experiment=False), PARITY),
     "takes its scope from sol_batch_controls"),
    (lambda: (grading.EXP036_SOL_BATCH, dataclasses.replace(PARITY, solve_seed="published")),
     "an unknown solve seed"),
])
def test_a_registry_entry_that_breaks_a_rule_is_named(entries, problem):
    assert any(problem in found for found in grading.approval_problems(entries()))


def test_a_malformed_registry_refuses_every_approved_grade_but_leaves_the_rest_inert(
        in_batch_runner, monkeypatch):
    monkeypatch.setattr(grading, "APPROVALS",
                        (*grading.APPROVALS, dataclasses.replace(PARITY, config_name="e35pa2")))
    with pytest.raises(grading.CombinedUsdRefused, match="registry is malformed"):
        grading.approval_for(EXP035, PARITY_CONFIG)
    assert grading.applies(EXP035, EXP035_CONFIG) is False


def test_a_registered_but_unapproved_pair_admits_nothing_and_lends_neither_half(
        in_batch_runner, tmp_path, monkeypatch):
    held = grading.Approval(
        experiment_id="exp034_codex_foundry_trial30", config_name="x34hold", ceiling_usd=None,
        solve_seed=grading.SOLVE_SEED_SOL_BATCH, exclusive_experiment=True,
        inference_revision=None, task_ids_sha256=None, approved=None,
    )
    monkeypatch.setattr(grading, "APPROVALS", (*grading.APPROVALS, held))
    monkeypatch.setattr(grading, "published_solve", _no_solve_read)
    assert grading.approval_problems() == []
    config = tmp_path / "x34hold.yaml"
    config.write_text(yaml.safe_dump({**_template(), "config_name": "x34hold"}, sort_keys=False),
                      encoding="utf-8")
    for ask in (grading.applies, grading.approval_for):
        with pytest.raises(grading.CombinedUsdRefused, match="registered but not approved for spending"):
            ask(held.experiment_id, config)
    with pytest.raises(grading.CombinedUsdRefused, match="registered but not approved for spending"):
        grading.preflight(held.experiment_id, config, EXP035_REVISION, 1)
    # Neither half is graded by anything else.
    with pytest.raises(grading.CombinedUsdRefused, match="only grade each other"):
        grading.approval_for(held.experiment_id, EXP035_CONFIG)
    with pytest.raises(grading.CombinedUsdRefused, match="only grade each other"):
        grading.approval_for(EXP035, config)
    # And no journal can claim it.
    journal = _write_journal(tmp_path / "run-41-1.combined_usd.jsonl", _good_lines(),
                             experiment_id=held.experiment_id, config_name=held.config_name)
    with pytest.raises(grading.CombinedUsdRefused, match="approved admission"):
        grading.journal_spend(journal)


def test_the_parity_config_grades_only_exp035_and_leaves_exp035s_own_config_inert(in_batch_runner):
    assert grading.approval_for(EXP035, PARITY_CONFIG) is PARITY
    assert grading.approval_for(EXP036, EXP036_CONFIG) is grading.EXP036_SOL_BATCH
    # exp035 graded by its historical config is still no business of this module.
    assert grading.applies(EXP035, EXP035_CONFIG) is False
    for experiment, config in ((EXP036, PARITY_CONFIG), (EXP035, EXP036_CONFIG), (EXP036, EXP035_CONFIG)):
        with pytest.raises(grading.CombinedUsdRefused, match="only grade each other") as refused:
            grading.approval_for(experiment, config)
        assert refused.value.code == grading.UNVERIFIED


def test_the_parity_config_copies_the_template_and_pins_the_approved_scope(in_batch_runner):
    config, template = _parity_config(), _template()
    step8.validate_grading_config(config)
    assert config["config_name"] == PARITY.config_name
    for block in grading.TEMPLATE_BLOCKS:
        assert config[block] == template[block], block
    rerun = config["rerun_identity"]
    assert rerun["experiment_id"] == PARITY.experiment_id == template["rerun_identity"]["experiment_id"]
    assert rerun["inference_revision"] == PARITY.inference_revision == template["rerun_identity"]["inference_revision"]
    assert rerun["rubric_commit_sha"] == template["rerun_identity"]["rubric_commit_sha"]
    ids = rerun["task_ids"]
    assert rerun["expected_task_count"] == len(ids) == len(set(ids))
    assert step8._ordered_task_ids_sha256(ids) == PARITY.task_ids_sha256
    # A canonical-order subsequence of the 220 the published grade covered.
    corpus = template["rerun_identity"]["task_ids"]
    assert step8._is_ordered_subsequence(ids, corpus) and len(ids) < len(corpus)


# -- the parity preflight -----------------------------------------------------


def _parity_preflight(monkeypatch, tmp_path, journals: dict[str, str] | None = None, *,
                      config: str | Path = PARITY_CONFIG, revision: str = EXP035_REVISION):
    monkeypatch.setattr(grading, "published_solve", _no_solve_read)
    monkeypatch.setattr(step8, "_repo_root", lambda: tmp_path)
    for name, spent in (journals or {}).items():
        _write_journal(tmp_path / grading.JOURNAL_DIR / EXP035 / name, [
            {"event": "reserve", "ticket": "g1", "reserve_usd": spent},
            {"event": "settle", "ticket": "g1", "spent_usd": spent},
        ], experiment_id=EXP035, config_name=PARITY.config_name)
    return grading.preflight(EXP035, config, revision, 1)


def test_the_parity_seed_is_its_own_journals_and_no_solve_spend(in_batch_runner, tmp_path, monkeypatch):
    seed = _parity_preflight(monkeypatch, tmp_path)
    record = seed.as_record()
    assert record["experiment_id"] == EXP035 and record["config_name"] == PARITY.config_name
    assert (record["solve_usd"], record["narrative_allowance_usd"], record["prior_grading_usd"]) == (
        "0.00000000", "0.00000000", "0.00000000")
    assert record["published_ledger_status"] == "not_applicable"
    assert record["ceiling_usd"] == grading._money(PARITY.ceiling_usd)

    seed = _parity_preflight(monkeypatch, tmp_path, {"run-21-1.combined_usd.jsonl": "12.50000000"})
    assert seed.committed_floor() == Decimal("12.5")
    assert [journal["path"] for journal in seed.as_record()["prior_journals"]] == [
        f"data/grades/_combined_usd/{EXP035}/run-21-1.combined_usd.jsonl"]


def test_spent_parity_journals_refuse_before_any_login(in_batch_runner, tmp_path, monkeypatch):
    spent = grading._money(PARITY.ceiling_usd)
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        _parity_preflight(monkeypatch, tmp_path, {"run-22-1.combined_usd.jsonl": spent})
    assert refused.value.code == grading.CEILING


@pytest.mark.parametrize("case", ["revision", "no_rerun", "other_scope", "one_more_task", "count"])
def test_the_parity_preflight_refuses_anything_but_the_approved_scope(in_batch_runner, tmp_path, monkeypatch, case):
    config = _parity_config()
    revision = EXP035_REVISION
    if case == "revision":
        revision = INFERENCE_SHA
    elif case == "no_rerun":
        del config["rerun_identity"]
    elif case == "other_scope":
        config["rerun_identity"]["task_ids"] = list(reversed(config["rerun_identity"]["task_ids"]))
    elif case == "one_more_task":
        config["rerun_identity"]["task_ids"].append("0e386e32-df20-4d1f-b536-7159bc409ad5")
        config["rerun_identity"]["expected_task_count"] += 1
    elif case == "count":
        config["rerun_identity"]["expected_task_count"] += 1
    path = tmp_path / "configs" / "e35par.yaml"
    path.parent.mkdir()
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    with pytest.raises(grading.CombinedUsdRefused) as refused:
        _parity_preflight(monkeypatch, tmp_path, config=path, revision=revision)
    assert refused.value.code == grading.UNVERIFIED


def test_an_alias_experiment_yaml_cannot_open_a_second_journal_directory(in_batch_runner, tmp_path, monkeypatch):
    alias = tmp_path / "exp035_alias.yaml"
    alias.write_text((BATCH_RUNNER / "experiments" / f"{EXP035}.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    real = grading._experiment_path
    monkeypatch.setattr(grading, "_experiment_path",
                        lambda name: alias if name == "exp035_alias" else real(name))
    assert grading.approval_for("exp035_alias", PARITY_CONFIG) is PARITY
    with pytest.raises(grading.CombinedUsdRefused, match="own YAML name"):
        grading.preflight("exp035_alias", PARITY_CONFIG, EXP035_REVISION, 1)


def test_the_parity_pair_leaves_room_for_every_file_step8_creates(in_batch_runner):
    out = grading.check_name_budget(step8, _parity_config(), PARITY_CONFIG, EXP035, EXP035_REVISION)
    assert len(out.stem.encode("utf-8")) + grading.CHECKPOINT_TMP_EXTRA <= grading.NAME_MAX
    assert len(EXP035) + len(PARITY.config_name) <= 36


# -- journals across approvals ------------------------------------------------


def test_a_journal_written_under_another_approval_refuses_the_sum(tmp_path):
    root = tmp_path / "repo"
    _write_journal(root / grading.JOURNAL_DIR / EXP036 / "run-31-1.combined_usd.jsonl", _good_lines(),
                   experiment_id=EXP035, config_name=PARITY.config_name)
    with pytest.raises(grading.CombinedUsdRefused, match="journal"):
        grading.prior_grading(root, EXP036, grading.EXP036_SOL_BATCH)
    # Read alone, it is a well-formed journal of the parity approval.
    assert grading.journal_spend(root / grading.JOURNAL_DIR / EXP036 / "run-31-1.combined_usd.jsonl") == Decimal("0.5")


def test_a_journal_without_its_config_name_refuses(tmp_path):
    path = tmp_path / "run-32-1.combined_usd.jsonl"
    path.write_text(
        json.dumps({"event": "open", "schema": grading.JOURNAL_SCHEMA, "experiment_id": EXP036, "seq": 0}) + "\n",
        encoding="utf-8")
    with pytest.raises(grading.CombinedUsdRefused, match="approved admission"):
        grading.journal_spend(path)


def test_the_published_exp036_journal_still_reads_under_the_registry():
    if not PUBLISHED_EXP036_JOURNAL.is_file():
        pytest.skip("the exp036 grade journal is committed from cc256a50 on")
    assert grading.journal_spend(PUBLISHED_EXP036_JOURNAL) == Decimal("10.7193625")
    raw = PUBLISHED_EXP036_JOURNAL.read_bytes()
    total, journals = grading.prior_grading(REPO_ROOT, EXP036, grading.EXP036_SOL_BATCH)
    assert total >= Decimal("10.7193625")
    assert any(entry["sha256"] == hashlib.sha256(raw).hexdigest() for entry in journals)


# -- the pinned scope is the committed selection diff of the sealed selector ---

#: Step S output: scripts/selection_diff_against_grade.py run on the published
#: exp035 grade at the selector reseal's merge commit.
PARITY_SELECTION_RECORD = BATCH_RUNNER / "docs" / "run_records" / "exp035_parity_selection_20261106.json"
SELECTOR_RESEAL_RECORD = (BATCH_RUNNER / "experiments" / "execution_envelope"
                          / "gpt56_sol_grader_seal_20261106.json")
SELECTOR = "batch-runner/core/deliverable_selector.py"


def test_the_parity_scope_is_the_selection_diff_of_the_sealed_selector():
    record = json.loads(PARITY_SELECTION_RECORD.read_text(encoding="utf-8"))
    rerun = _parity_config()["rerun_identity"]
    assert record["schema"] == "selection-diff-v1"
    assert record["grade_experiment_id"] == PARITY.experiment_id
    assert record["grade_source_inference_revision"] == PARITY.inference_revision
    assert record["rubric_revision"] == rerun["rubric_commit_sha"]
    assert record["ordered_task_ids"] == rerun["task_ids"]
    assert record["ordered_task_ids_sha256"] == PARITY.task_ids_sha256
    # Computed with the selector this tree grades with, and that selector is
    # the one the successor seal reviewed. A later selector change fails here,
    # and there are two ways out. (a) Edit EXP035_PARITY in place: regenerate
    # this record, e35par.yaml's task list and EXP035_PARITY.task_ids_sha256
    # together, under a new dated owner approval written into
    # EXP035_PARITY.approved; the ceiling and the committed journal carry over.
    # (b) First give the registry the retired state described next to
    # APPROVALS. A second exp035 entry, or removing or un-approving this one,
    # is refused (see APPROVALS).
    selector = hashlib.sha256((REPO_ROOT / SELECTOR).read_bytes()).hexdigest()
    assert record["selector_sha256"] == selector
    seal = json.loads(SELECTOR_RESEAL_RECORD.read_text(encoding="utf-8"))
    assert seal["files"][SELECTOR] == selector
    # ...against the published grade it is a diff of (data/ may be absent).
    published = REPO_ROOT / "data" / "grades" / record["grade_file"]
    if published.is_file():
        assert record["grade_sha256"] == hashlib.sha256(published.read_bytes()).hexdigest()


# -- the approval, not the dispatch, defines the scope -------------------------

SUBSET_TASK = "15d37511-75c5-4c7f-81f1-16e00c0d95f3"


def _approved_argv(approval: grading.Approval, *extra: str) -> list[str]:
    return [approval.experiment_id, "--config", f"grading_configs/{approval.config_name}.yaml",
            "--source", "local", *extra]


@pytest.mark.parametrize("approval", grading.APPROVALS, ids=lambda approval: approval.config_name)
@pytest.mark.parametrize("narrowing", [
    ["--tasks", SUBSET_TASK],
    ["--limit", "3"],
    ["--limit", "-1"],
    ["--tasks", SUBSET_TASK, "--limit", "1"],
], ids=["tasks", "limit", "negative_limit", "both"])
def test_run_refuses_a_subset_of_any_approved_scope(
        in_batch_runner, tmp_path, monkeypatch, capsys, approval, narrowing):
    # A subset would be a _diagnostic/ grade paid under a ceiling sized for the
    # whole scope. Refused before the preflight reads anything and before a
    # journal exists.
    monkeypatch.setattr(grading, "preflight", _never("the preflight"))
    monkeypatch.setattr(step8, "main", _never("step 8"))
    monkeypatch.setattr(step8, "_repo_root", lambda: tmp_path)
    argv = ["run", "--inference-revision", EXP035_REVISION, "--", *_approved_argv(approval, *narrowing)]
    assert grading.main(argv) == grading.REFUSED_EXIT
    refusal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert refusal["status"] == "refused" and refusal["reason"] == grading.UNVERIFIED
    assert "whole scope" in refusal["detail"]
    assert not (tmp_path / grading.JOURNAL_DIR).exists()


@pytest.mark.parametrize("approval", grading.APPROVALS, ids=lambda approval: approval.config_name)
def test_run_lets_the_whole_approved_scope_through_to_the_preflight(
        in_batch_runner, tmp_path, monkeypatch, capsys, approval):
    asked: list[tuple] = []
    monkeypatch.setattr(grading, "preflight", lambda *args: asked.append(args) or None)
    monkeypatch.setattr(step8, "main", _never("step 8"))
    monkeypatch.setattr(step8, "_repo_root", lambda: tmp_path)
    argv = _approved_argv(approval, "--limit", "0", "--tasks", "")
    assert grading.run(argv, EXP035_REVISION) == grading.REFUSED_EXIT
    assert asked == [(approval.experiment_id, f"grading_configs/{approval.config_name}.yaml",
                      EXP035_REVISION, 1)]
    refusal = json.loads(capsys.readouterr().err.splitlines()[-1])
    assert "whole scope" not in refusal["detail"]


def test_the_workflow_hands_tasks_and_tasks_limit_to_run_where_they_are_refused():
    grade = next(step for step in yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["grade"]["steps"]
                 if step.get("name") == "Run grading")
    script = grade["run"]
    wrapper = script.index('python sol_batch_grading.py run --inference-revision "$GRADE_INFERENCE_REVISION" -- "${ARGS[@]}"')
    assert script.index('ARGS+=(--limit "$GRADE_TASKS_LIMIT")') < wrapper
    assert script.index('ARGS+=(--tasks "$GRADE_TASKS")') < wrapper
