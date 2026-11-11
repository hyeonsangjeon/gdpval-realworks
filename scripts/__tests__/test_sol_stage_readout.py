"""scripts/sol_stage_readout.py on exp036's published records and on stages built from the real configs.

Model-free and offline: the diagnosis's numbers for exp036, the money the
grade preflight would count, the cause table it shares with
merge_parity_regrade.py, the USD-gate rows it moves, the records it refuses,
and the grader identity two stages with different configs can share.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import shutil
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sol_stage_readout.py"
GRADE = REPO_ROOT / (
    "data/grades/exp036_sol_fixed5__judge_gpt-5_6-sol__exp036_v2_sol_max__cfg_1794403983325602__rubric_"
    "11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_8708d9206ce4c9c9ba96f8bfba0745e12e597777__src_"
    "814d56797e9fc3dc__v2.2.json")
#: That grade's own journal, opened by the run that wrote it (its
#: runner_evidence: run 42039154052, attempt 1). The exp036 regrade adds
#: another journal to the same directory, so the expected figures read this one file.
GRADE_JOURNAL = REPO_ROOT / "data/grades/_combined_usd/exp036_sol_fixed5/run-42039154052-1.combined_usd.jsonl"
#: The fields the readout reads from HyeonSang/exp036_sol_fixed5's self_report.json at 8708d920.
SELF_REPORT = {
 "meta": {
  "experiment_id": "exp036_sol_fixed5",
  "ordered_task_ids": [
   "02aa1805-c658-4069-8a6a-02dec146063a",
   "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
   "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
   "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
   "0818571f-5ff7-4d39-9d2c-ced5ae44299e"
  ]
 },
 "task_results": [
  {
   "task_id": "02aa1805-c658-4069-8a6a-02dec146063a",
   "status": "success",
   "latency_ms": 864701.73,
   "deliverable_files": [
    "deliverable_files/02aa1805-c658-4069-8a6a-02dec146063a/Email_to_Manager_Well_Recommendations.eml",
    "deliverable_files/02aa1805-c658-4069-8a6a-02dec146063a/Illinois_Green_Hydrogen_Well_Screening.xlsx"
   ],
   "observability": {
    "budget_metrics": {
     "schema_version": "1.0",
     "usage_complete": True,
     "conservative_cost_usd": 21.260681
    }
   }
  },
  {
   "task_id": "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
   "status": "success",
   "latency_ms": 228207.58,
   "deliverable_files": [
    "deliverable_files/0112fc9b-c3b2-4084-8993-5a4abb1f54f1/CS_SOAP_Note_2024-03-01.docx",
    "deliverable_files/0112fc9b-c3b2-4084-8993-5a4abb1f54f1/CS_SOAP_Note_2024-03-01.html"
   ],
   "observability": {
    "budget_metrics": {
     "schema_version": "1.0",
     "usage_complete": True,
     "conservative_cost_usd": 1.7645125
    }
   }
  },
  {
   "task_id": "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
   "status": "success",
   "latency_ms": 373718.3,
   "deliverable_files": [
    "deliverable_files/2ea2e5b5-257f-42e6-a7dc-93763f28b19d/Work Time Study - Activity Analysis.pptx",
    "deliverable_files/2ea2e5b5-257f-42e6-a7dc-93763f28b19d/build_work_time_study_deck.py"
   ],
   "observability": {
    "budget_metrics": {
     "schema_version": "1.0",
     "usage_complete": True,
     "conservative_cost_usd": 4.227676
    }
   }
  },
  {
   "task_id": "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
   "status": "success",
   "latency_ms": 121717.93,
   "deliverable_files": [
    "deliverable_files/3baa0009-5a60-4ae8-ae99-4955cb328ff3/create_global_growth_chart.py",
    "deliverable_files/3baa0009-5a60-4ae8-ae99-4955cb328ff3/world_bank_global_growth_2024_2025_2027.jpg",
    "deliverable_files/3baa0009-5a60-4ae8-ae99-4955cb328ff3/world_bank_global_outlook_article.md"
   ],
   "observability": {
    "budget_metrics": {
     "schema_version": "1.0",
     "usage_complete": True,
     "conservative_cost_usd": 1.010582
    }
   }
  },
  {
   "task_id": "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
   "status": "error",
   "latency_ms": 361825.47,
   "deliverable_files": [],
   "observability": {
    "error_category": "content_filtered",
    "budget_metrics": {
     "schema_version": "1.0",
     "usage_complete": False,
     "conservative_cost_usd": 10.5247045
    }
   }
  }
 ]
}


def _readout():
    spec = importlib.util.spec_from_file_location("sol_stage_readout", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exp036_reads_as_the_diagnosis_found_it(tmp_path):
    readout = _readout()
    report = tmp_path / "self_report.json"
    report.write_text(json.dumps(SELF_REPORT), encoding="utf-8")
    journals = tmp_path / "journals"
    journals.mkdir()
    shutil.copy(GRADE_JOURNAL, journals)
    rows = readout.read_stage("exp036_sol_fixed5", GRADE, report, journals)
    summary = readout.summarise(rows, 5, 0, 0)
    assert summary["score_fixed_denominator"] == 33.47
    assert summary["score_full_item_denominator"] == 30.74
    assert summary["score_judged_only"] == 83.66
    assert summary["zeros_by_cause"] == {"content_filter": 1, "grader_refusal": 2}
    assert summary["usd"]["solve"] == 38.79 and summary["usd"]["grading"] == 10.72
    habits = summary["file_habits"]
    assert (habits["email_files"], habits["same_stem_multi_format_groups"], habits["helper_files"]) == (1, 1, 2)
    assert summary["usd"]["grading_unattributed"] == 0.0
    # The grade preflight's own figure: "committed 51.50751850 of 200.00000000".
    assert summary["stages"] == [{
        "stage": "exp036_sol_fixed5", "ceiling_usd": 200.0, "solve_usd": 38.79, "prior_lineage_spend_usd": 0.0,
        "lost_booking_usd": 0.0, "narrative_allowance_usd": 2.0, "grading_usd": 10.72, "committed_usd": 51.51,
        "left_under_ceiling_usd": 148.49}]
    assert summary["rules"]["R1"] is False and summary["rules"]["R2"] is True
    assert summary["moved_by_usd_gate"] == [] and summary["projection"]["attempted_sample"] == 5
    # That grade was made before the reviewed selector changed the grader
    # closure, so this tree's grader is not the one that marked it.
    grader = summary["graders"][0]
    assert grader["grader_source_hash"].startswith("814d56797e9fc3dc")
    assert grader["config_name"] == "exp036_v2_sol_max" and grader["graded_by_this_tree"] is False
    assert summary["one_grader"] is False
    assert summary["one_grader_problems"][0].startswith("exp036_sol_fixed5: graded by grader source 814d56797e9fc3dc")


def test_a_reservation_that_never_concluded_is_counted_as_spent(tmp_path):
    readout = _readout()
    lines = [
        {"event": "open", "seq": 0},
        {"event": "reserve", "seq": 1, "ticket": "g1", "task_id": "A", "reserve_usd": "0.50000000"},
        {"event": "settle", "seq": 2, "ticket": "g1", "spent_usd": "0.40000000"},
        {"event": "reserve", "seq": 3, "ticket": "g2", "task_id": "B", "reserve_usd": "0.70000000"},
    ]
    (tmp_path / "run-1-1.combined_usd.jsonl").write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    assert readout.journal_usd_by_task(tmp_path) == {"A": Decimal("0.4"), "B": Decimal("0.7")}


def test_a_stage_reads_the_journals_it_is_pointed_at(tmp_path):
    readout = _readout()
    report = tmp_path / "self_report.json"
    report.write_text(json.dumps(SELF_REPORT), encoding="utf-8")
    journals = tmp_path / "journals"
    journals.mkdir()
    shutil.copy(GRADE_JOURNAL, journals)
    out = tmp_path / "out.json"
    readout.main(["--repo-root", str(REPO_ROOT), "--stage", "exp036_sol_fixed5", str(GRADE), str(report),
                  "--journals-dir", "exp036_sol_fixed5", str(journals), "--json", str(out)])
    assert json.loads(out.read_text(encoding="utf-8"))["summary"]["usd"]["grading"] == 10.72


def test_a_task_in_two_stages_is_refused(tmp_path):
    readout = _readout()
    report = tmp_path / "self_report.json"
    report.write_text(json.dumps(SELF_REPORT), encoding="utf-8")
    stage = ["exp036_sol_fixed5", str(GRADE), str(report)]
    try:
        readout.main(["--repo-root", str(REPO_ROOT), "--stage", *stage, "--stage", *stage])
    except SystemExit as stop:
        assert "counts every task once" in str(stop)
    else:
        raise AssertionError("a union with a repeated task was accepted")


def _exp036_argv(tmp_path: Path, *extra: str) -> list[str]:
    report = tmp_path / "self_report.json"
    report.write_text(json.dumps(SELF_REPORT), encoding="utf-8")
    journals = tmp_path / "journals"
    journals.mkdir(exist_ok=True)
    shutil.copy(GRADE_JOURNAL, journals)
    return ["--repo-root", str(REPO_ROOT), "--stage", "exp036_sol_fixed5", str(GRADE), str(report),
            "--journals-dir", "exp036_sol_fixed5", str(journals), "--json", str(tmp_path / "out.json"), *extra]


def test_nothing_projected_leaves_r3_and_r4_unevaluated(tmp_path):
    readout = _readout()
    readout.main(_exp036_argv(tmp_path))
    summary = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["summary"]
    # Zero legs and zero chunks for nothing projected would read as "R3 and R4 hold".
    assert summary["rules"]["R3"] is None and summary["rules"]["R4"] is None
    projection = summary["projection"]
    assert projection["remaining_tasks"] is projection["remaining_items"] is None
    assert projection["solve_legs"] is projection["grading_chunks"] is projection["grading_usd"] is None
    # Half the projection by hand is refused, not read as the other half 0.
    for half in (("--remaining-tasks", "195"), ("--remaining-items", "9248")):
        with pytest.raises(SystemExit):
            readout.main(_exp036_argv(tmp_path, *half))
    readout.main(_exp036_argv(tmp_path, "--remaining-tasks", "195", "--remaining-items", "9248"))
    summary = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["summary"]
    assert type(summary["rules"]["R3"]) is bool and type(summary["rules"]["R4"]) is bool
    assert summary["projection"]["solve_legs"] > 0 and summary["projection"]["grading_chunks"] > 0


def test_a_stage_commits_what_the_grade_preflight_counts(tmp_path, monkeypatch):
    readout = _readout()
    controls = readout._batch_runner_module("sol_batch_controls")
    grading = readout._batch_runner_module("sol_batch_grading")
    revision = "8708d9206ce4c9c9ba96f8bfba0745e12e597777"
    report = json.loads(json.dumps(SELF_REPORT))
    # A task that reached Codex but lost its booking, carried by lost_booking_usd,
    # and a lineage before this one that spent 40.
    lost = report["task_results"][3]
    lost["observability"].pop("budget_metrics")
    lost["observability"]["runner_evidence"] = {}
    run = dataclasses.replace(
        controls.RUNS["exp036_sol_fixed5"], prior_lineage_spend_usd=Decimal("40"),
        lost_booking_usd=MappingProxyType({(revision, lost["task_id"]): Decimal("1.25")}))
    monkeypatch.setattr(controls, "RUNS", MappingProxyType({**controls.RUNS, run.experiment_id: run}))
    report_path = tmp_path / "self_report.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    root = tmp_path / "repo"
    journals = root / "data/grades/_combined_usd/exp036_sol_fixed5"
    journals.mkdir(parents=True)
    shutil.copy(GRADE_JOURNAL, journals)
    rows = readout.read_stage("exp036_sol_fixed5", GRADE, report_path, journals)
    stage = readout.summarise(rows, 5, None, None)["stages"][0]
    # The preflight's own functions on the same records.
    solve, _floor, _status = grading.published_solve(
        "HyeonSang/exp036_sol_fixed5", revision, run,
        fetch=lambda _repo, name, _revision: report_path if name == "self_report.json" else None)
    prior, journal_list = grading.prior_grading(root, "exp036_sol_fixed5", grading.EXP036_SOL_BATCH)
    seed = grading.Seed(
        experiment_id=run.experiment_id, config_name=run.grading_config_name, inference_revision=revision,
        solve_usd=solve, published_ledger_floor_usd=Decimal(0), published_ledger_status="absent",
        narrative_allowance_usd=run.narrative_allowance_usd, prior_grading_usd=prior,
        prior_journals=tuple(journal_list), ceiling_usd=run.ceiling_usd)
    assert stage["committed_usd"] == round(float(seed.committed_floor()), 2) == 91.75
    assert stage["left_under_ceiling_usd"] == round(float(run.ceiling_usd - seed.committed_floor()), 2)
    assert stage["solve_usd"] == round(float(solve), 2) == round(38.788156 - 1.010582 + 1.25 + 40, 2)
    assert (stage["prior_lineage_spend_usd"], stage["lost_booking_usd"]) == (40.0, 1.25)
    assert [row["solve_usd"] for row in rows if row["task_id"] == lost["task_id"]] == [1.25]
    # A row the preflight would refuse refuses the readout too.
    monkeypatch.setattr(controls, "RUNS", MappingProxyType({
        **controls.RUNS, run.experiment_id: dataclasses.replace(run, lost_booking_usd=MappingProxyType({}))}))
    with pytest.raises(SystemExit, match="sol_batch_prior_spend_unaccounted"):
        readout.read_stage("exp036_sol_fixed5", GRADE, report_path, journals)


def test_a_stage_is_read_from_its_own_final_grade_and_journals_only(tmp_path):
    readout = _readout()
    report_path = tmp_path / "self_report.json"
    report_path.write_text(json.dumps(SELF_REPORT), encoding="utf-8")
    journals = tmp_path / "journals"
    journals.mkdir()
    shutil.copy(GRADE_JOURNAL, journals)
    published = json.loads(GRADE.read_text(encoding="utf-8"))

    def read(grade=published, report=SELF_REPORT, directory=journals, stage="exp036_sol_fixed5"):
        (tmp_path / "grade.json").write_text(json.dumps(grade), encoding="utf-8")
        report_path.write_text(json.dumps(report), encoding="utf-8")
        return readout.read_stage(stage, tmp_path / "grade.json", report_path, directory)

    assert len(read()) == 5
    # Between grading chunks the committed grade is partial.
    with pytest.raises(SystemExit, match="not a final grade"):
        read({**published, "run_status": "partial"})
    with pytest.raises(SystemExit, match="is not a grade of exp036_sol_fixed5"):
        read({**published, "experiment_id": "exp037_sol_first25"})
    with pytest.raises(SystemExit, match="does not grade the tasks"):
        read({**published, "tasks": published["tasks"][::-1]})
    with pytest.raises(SystemExit, match="does not grade the tasks"):
        read({**published, "tasks": published["tasks"][:4]})
    with pytest.raises(SystemExit, match="registered tasks"):
        read(report={**SELF_REPORT, "meta": {**SELF_REPORT["meta"],
                                             "ordered_task_ids": SELF_REPORT["meta"]["ordered_task_ids"][:4]},
                     "task_results": SELF_REPORT["task_results"][:4]})
    with pytest.raises(SystemExit, match="names no 40-hex source_inference_revision"):
        read({**published, "source_inference_revision": None})
    with pytest.raises(SystemExit, match="not a Sol run registered"):
        read(stage="exp035_codex_foundry_full220")
    # A mistyped journals directory is not "grading cost 0".
    with pytest.raises(SystemExit, match="holds no combined USD journal"):
        read(directory=tmp_path / "typo")
    # Another approval's journal is not this stage's spend.
    other = tmp_path / "other"
    other.mkdir()
    (other / "run-1-1.combined_usd.jsonl").write_text(
        json.dumps({"event": "open", "seq": 0, "schema": "sol-batch-grading-journal-v1",
                    "experiment_id": "exp035_codex_foundry_full220", "config_name": "e35par"}) + "\n",
        encoding="utf-8")
    with pytest.raises(SystemExit, match="not by exp036_sol_fixed5 / exp036_v2_sol_max"):
        read(directory=other)
    # The same pair's journal of another grade (exp036's regrade writes one) is
    # not the journal of the run that wrote this grade.
    regrade = tmp_path / "regrade"
    regrade.mkdir()
    shutil.copy(GRADE_JOURNAL, regrade / "run-99999999999-1.combined_usd.jsonl")
    with pytest.raises(SystemExit, match="was written by run 42039154052 attempt 1, whose combined USD journal "
                                         "is not in"):
        read(directory=regrade)
    unnamed = {key: value for key, value in published.items() if key != "runner_evidence"}
    with pytest.raises(SystemExit, match="names no grading run"):
        read(unnamed)
    with pytest.raises(SystemExit, match="names no grading run"):
        read({**published, "runner_evidence": {"observation": {"run_id": "42039154052", "run_attempt": "0"}}})


# -- journals: what the preflight counts ----------------------------------------


def _journal_lines(*lines: dict) -> str:
    opening = {"event": "open", "seq": 0, "schema": "sol-batch-grading-journal-v1",
               "experiment_id": "exp036_sol_fixed5", "config_name": "exp036_v2_sol_max"}
    return "".join(json.dumps(line) + "\n" for line in (opening, *lines))


def test_a_journal_total_above_its_task_lines_is_reported_unattributed(tmp_path):
    readout = _readout()
    # The close line carries the in-memory total; a conclusion whose own line
    # failed to write is in it and in sol_batch_grading.journal_spend, on no task.
    (tmp_path / "run-1-1.combined_usd.jsonl").write_text(_journal_lines(
        {"event": "reserve", "seq": 1, "ticket": "g1", "task_id": "A", "reserve_usd": "0.50000000"},
        {"event": "settle", "seq": 2, "ticket": "g1", "spent_usd": "0.40000000"},
        {"event": "close", "seq": 3, "spent_usd": "0.90000000"},
    ), encoding="utf-8")
    by_task, unattributed, names = readout.journal_usd(tmp_path)
    assert by_task == {"A": Decimal("0.4")} and unattributed == Decimal("0.5")
    assert names == ["run-1-1.combined_usd.jsonl"]


def test_a_journal_line_on_no_listed_task_is_still_counted(tmp_path):
    readout = _readout()
    journals = tmp_path / "journals"
    journals.mkdir()
    # Named after the run that wrote GRADE, as the readout requires.
    (journals / GRADE_JOURNAL.name).write_text(_journal_lines(
        {"event": "reserve", "seq": 1, "ticket": "g1", "task_id": None, "reserve_usd": "0.50000000"},
        {"event": "settle", "seq": 2, "ticket": "g1", "spent_usd": "0.30000000"},
    ), encoding="utf-8")
    report = tmp_path / "self_report.json"
    report.write_text(json.dumps(SELF_REPORT), encoding="utf-8")
    rows = readout.read_stage("exp036_sol_fixed5", GRADE, report, journals)
    summary = readout.summarise(rows, 5, 0, 0)
    assert summary["usd"]["grading"] == summary["usd"]["grading_unattributed"] == 0.3
    assert summary["stages"][0]["grading_usd"] == 0.3


def test_a_journal_the_preflight_would_refuse_refuses_the_readout(tmp_path):
    readout = _readout()
    (tmp_path / "run-1-1.combined_usd.jsonl").write_text(_journal_lines(
        {"event": "settle", "seq": 1, "ticket": "g9", "spent_usd": "0.40000000"},
    ), encoding="utf-8")
    with pytest.raises(SystemExit, match="concludes a ticket that is not open"):
        readout.journal_usd(tmp_path)


# -- the shared cause table -------------------------------------------------------


@pytest.mark.parametrize("grade_error, category, cause", [
    ("selection_error", None, "grader_refusal"),
    ("all_items_score_excluded", None, "grader_other"),
    (True, "content_filtered", "grader_other"),
    ("no_deliverables", "content_filtered", "content_filter"),
    ("no_deliverables", "usd_ceiling_reached", "usd_gate"),
    ("no_deliverables", "sol_batch_context_window_mismatch", "sol_gate"),
    ("no_deliverables", "sol_batch_gate_unverified", "sol_gate"),
    ("no_deliverables", "timeout", "turn_timeout"),
    ("no_deliverables", "rate_limited", "infrastructure"),
    ("no_deliverables", "turn_failed", "unclassified_failure"),
    ("no_deliverables", None, "model_other"),
    ("no_deliverables", "model_mismatch", "model_other"),
])
def test_the_readout_and_the_parity_record_share_one_cause_table(grade_error, category, cause):
    readout = _readout()
    spec = importlib.util.spec_from_file_location(
        "merge_parity_regrade_for_test", REPO_ROOT / "batch-runner/scripts/merge_parity_regrade.py")
    merge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(merge)
    assert readout.CAUSES.zero_cause_of(grade_error, category) == cause
    assert merge.zero_cause({"task_id": "t", "error": grade_error}, {"t": category}) == cause
    assert cause in merge.ZERO_CAUSES


def test_the_cause_table_names_the_sol_harness_refusals_by_their_codes():
    readout = _readout()
    controls = readout._batch_runner_module("sol_batch_controls")
    assert readout.CAUSES.USD_GATE == {controls.USD_CEILING_REACHED}
    assert readout.CAUSES.SOL_GATE == {controls.WINDOW_MISMATCH, controls.GATE_UNVERIFIED}
    assert readout.CAUSES.NOT_ATTEMPTED == {"usd_gate", "sol_gate"} <= set(readout.CAUSES.ZERO_CAUSES)


# -- two stages built from the real exp037 and exp038 configs ----------------------

EXPERIMENTS = REPO_ROOT / "batch-runner/experiments"
RENDERER = {"libreoffice_binary": "soffice", "libreoffice_version": "LibreOffice 24.2.7.2", "pymupdf_version": "2.1"}
REVISIONS = {"exp037_sol_first25": "37" * 20, "exp038_sol_rest195": "38" * 20}
#: The GitHub run that wrote each stage's final grade (runner_evidence.observation).
WRITERS = {"exp037_sol_first25": "37000000001", "exp038_sol_rest195": "38000000001"}


def _stage_tasks(experiment_id: str) -> list[str]:
    document = yaml.safe_load((EXPERIMENTS / f"{experiment_id}.yaml").read_text(encoding="utf-8"))
    return document["data"]["filter"]["task_ids"]


def _this_tree_hash(readout, config_name: str) -> str:
    step8 = readout._batch_runner_module("step8_grade")
    relative = f"grading_configs/{config_name}.yaml"
    config = yaml.safe_load((readout.BATCH_RUNNER / relative).read_text(encoding="utf-8"))
    return step8.compute_grader_source_hash(relative, config, batch_root=readout.BATCH_RUNNER)


@pytest.fixture
def registry(monkeypatch):
    """The two registries; ``approve_exp038`` and ``list_tasks`` edit them as exp038's approval PR would."""
    readout = _readout()
    controls = readout._batch_runner_module("sol_batch_controls")
    grading = readout._batch_runner_module("sol_batch_grading")

    class Registry:
        @staticmethod
        def approve_exp038(ceiling: str = "1500") -> None:
            approval = dataclasses.replace(grading.EXP038_REST195, ceiling_usd=Decimal(ceiling),
                                           approved="test: the exp038 approval PR")
            monkeypatch.setattr(grading, "APPROVALS", tuple(
                approval if entry.experiment_id == approval.experiment_id else entry for entry in grading.APPROVALS))
            run = dataclasses.replace(
                controls.RUNS["exp038_sol_rest195"], approval="test: the exp038 approval PR",
                ceiling_usd=Decimal(ceiling), grading_reserve_usd=Decimal("500"),
                attempt_reserve_usd=Decimal("51"), narrative_allowance_usd=Decimal("2.00"))
            monkeypatch.setattr(controls, "RUNS", MappingProxyType({**controls.RUNS, run.experiment_id: run}))

        @staticmethod
        def list_tasks(experiment_id: str, tasks: list[str]) -> None:
            run = dataclasses.replace(controls.RUNS[experiment_id], task_count=len(tasks),
                                      ordered_task_ids_sha256=controls.ordered_task_ids_sha256(tasks))
            monkeypatch.setattr(controls, "RUNS", MappingProxyType({**controls.RUNS, run.experiment_id: run}))

    return Registry


def _write_stage(tmp_path: Path, experiment_id: str, source_hash: str, tasks: list[str], *,
                 refused: tuple[str, ...] = (), refused_usd: float = 0.0, harness: tuple[str, ...] = (),
                 grader_failed: tuple[str, ...] = (), renderer: dict = RENDERER, writer: str | None = None,
                 earlier: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """A final grade, a self_report.json and the journals of the runs that graded ``tasks``.

    ``refused`` tasks ended at the USD gate (after ``refused_usd`` of earlier
    attempts); ``harness`` tasks were refused by the Sol harness's window check;
    ``grader_failed`` tasks left files the judge was called on but marked no
    item of. The grade's writer is GitHub run ``writer`` (attempt 1), whose
    journal holds every task's grading lines except those of ``earlier``
    chunks: {run id: tasks that chunk graded}, one journal each.
    """
    writer = writer or WRITERS[experiment_id]
    chunk_of = {task: run_id for run_id, chunk in (earlier or {}).items() for task in chunk}
    grade_rows, report_rows, journals_lines = [], [], {writer: [], **{run_id: [] for run_id in earlier or {}}}
    for task in tasks:
        if task in refused or task in harness:
            category = "usd_ceiling_reached" if task in refused else "sol_batch_context_window_mismatch"
            grade_rows.append({"task_id": task, "error": "no_deliverables", "judge_call_count": 0})
            report_rows.append({"task_id": task, "status": "error", "latency_ms": 10, "deliverable_files": [],
                                "observability": {"error_category": category, "budget_metrics": {
                                    "conservative_cost_usd": refused_usd if task in refused else 0}}})
            continue
        if task in grader_failed:
            grade_rows.append({"task_id": task, "error": "all_items_score_excluded", "items": [{}] * 10,
                               "score_excluded_items": 10, "grading_wall_time_ms": 60_000, "judge_call_count": 3,
                               "selection_rule": "single_main"})
        else:
            grade_rows.append({"task_id": task, "error": None, "pct": 50.0, "pct_full_denominator": 40.0,
                               "items": [{}] * 10, "score_excluded_items": 0, "grading_wall_time_ms": 60_000,
                               "judge_call_count": 3, "selection_rule": "single_main"})
        report_rows.append({"task_id": task, "status": "success", "latency_ms": 600_000,
                            "deliverable_files": [f"deliverable_files/{task}/answer.docx"],
                            "observability": {"budget_metrics": {"conservative_cost_usd": 6.0}}})
        journal = journals_lines[chunk_of.get(task, writer)]
        journal += [{"event": "reserve", "ticket": f"g{len(journal)}", "task_id": task, "reserve_usd": "1.00000000"},
                    {"event": "settle", "ticket": f"g{len(journal)}", "spent_usd": "0.50000000"}]
    config_name = f"{experiment_id[:6]}_v2_sol_max"
    grade = {"experiment_id": experiment_id, "run_status": "final",
             "source_inference_revision": REVISIONS[experiment_id], "tasks": grade_rows,
             "grader_source_hash": source_hash, "renderer_fingerprint": renderer,
             "judge": {"model": "gpt-5.6-sol", "reasoning_effort": "max"}, "prompt": {"version": "v2.2"},
             "rubric": {"commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf"},
             # step 8's native runner evidence: the run whose journal holds the last chunk.
             "runner_evidence": {"observation": {"run_id": writer, "run_attempt": "1"}}}
    (tmp_path / f"{experiment_id}.grade.json").write_text(json.dumps(grade), encoding="utf-8")
    (tmp_path / f"{experiment_id}.self_report.json").write_text(json.dumps({
        "meta": {"experiment_id": experiment_id, "ordered_task_ids": list(tasks)}, "task_results": report_rows,
    }), encoding="utf-8")
    journals = tmp_path / f"{experiment_id}.journals"
    shutil.rmtree(journals, ignore_errors=True)
    journals.mkdir()
    opening = {"event": "open", "schema": "sol-batch-grading-journal-v1", "experiment_id": experiment_id,
               "config_name": config_name}
    for run_id, journal in journals_lines.items():
        (journals / f"run-{run_id}-1.combined_usd.jsonl").write_text("".join(
            json.dumps({**line, "seq": seq}) + "\n" for seq, line in enumerate([opening, *journal])),
            encoding="utf-8")
    return [experiment_id, str(tmp_path / f"{experiment_id}.grade.json"),
            str(tmp_path / f"{experiment_id}.self_report.json")]


def _run(readout, tmp_path: Path, *stages: list[str], extra: tuple[str, ...] = ()) -> dict:
    out = tmp_path / "out.json"
    argv = ["--repo-root", str(REPO_ROOT), "--json", str(out)]
    for stage in stages:
        argv += ["--stage", *stage, "--journals-dir", stage[0], str(tmp_path / f"{stage[0]}.journals")]
    readout.main(argv + list(extra))
    return json.loads(out.read_text(encoding="utf-8"))


def test_two_stages_with_their_own_configs_can_be_one_grader(tmp_path, registry):
    readout = _readout()
    registry.approve_exp038()
    first, rest = _this_tree_hash(readout, "exp037_v2_sol_max"), _this_tree_hash(readout, "exp038_v2_sol_max")
    # The configs differ only in their name and description, and the raw
    # hash covers the config file: equal raw hashes are impossible.
    assert first != rest
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", first, _stage_tasks("exp037_sol_first25"))
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", rest, _stage_tasks("exp038_sol_rest195"))
    summary = _run(readout, tmp_path, exp037, exp038)["summary"]
    assert summary["tasks"] == summary["denominator"] == 220
    assert summary["one_grader"] is True and summary["one_grader_problems"] == []
    assert [(stage["stage"], stage["ceiling_usd"]) for stage in summary["stages"]] == [
        ("exp037_sol_first25", 700.0), ("exp038_sol_rest195", 1500.0)]
    assert summary["stages"][0]["committed_usd"] == 25 * 6.0 + 2.0 + 25 * 0.5
    assert [grader["graded_by_this_tree"] for grader in summary["graders"]] == [True, True]
    assert len({grader["template_blocks_sha256"] for grader in summary["graders"]}) == 1

    # Another renderer marks the second stage differently, however the code agrees.
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", rest, _stage_tasks("exp038_sol_rest195"),
                          renderer={**RENDERER, "pymupdf_version": "1.28.2"})
    summary = _run(readout, tmp_path, exp037, exp038)["summary"]
    assert summary["one_grader"] is False
    assert summary["one_grader_problems"] == ["the stages differ in renderer_fingerprint"]

    # A grade whose hash is not this tree's for its own config was marked by
    # another closure, or under another config.
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", first, _stage_tasks("exp038_sol_rest195"))
    summary = _run(readout, tmp_path, exp037, exp038)["summary"]
    assert summary["one_grader"] is False
    assert summary["one_grader_problems"][0].startswith("exp038_sol_rest195: graded by grader source")


def test_a_task_the_usd_gate_refused_is_moved_not_sampled(tmp_path):
    readout = _readout()
    first25 = _stage_tasks("exp037_sol_first25")
    refused = first25[24]
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"),
                          first25, refused=(refused,))
    document = _run(readout, tmp_path, exp037, extra=("--remaining-from", "exp038_sol_rest195"))
    summary = document["summary"]
    # On the fixed 25 it is a 0, and it is listed as moved ...
    assert summary["tasks"] == summary["denominator"] == 25
    assert summary["score_fixed_denominator"] == 48.0 and summary["zeros_by_cause"] == {"usd_gate": 1}
    assert summary["moved_by_usd_gate"] == [refused]
    # ... but no per-task cost, time or projection counts its zero spend.
    assert summary["usd"]["solve_per_task_mean"] == 6.0 and summary["projection"]["attempted_sample"] == 24
    assert summary["time"]["solve_minutes_per_task_mean"] == 10.0
    assert summary["projection"]["solve_usd_mean"] == round(6.0 * 196)
    # The remainder is exp038's registered list plus the moved task.
    catalog = json.loads((REPO_ROOT / readout.TASK_CATALOG).read_text(encoding="utf-8"))
    items = {task["task_id"]: task["rubric_item_count"] for task in catalog["tasks"]}
    rest = _stage_tasks("exp038_sol_rest195")
    assert summary["projection"]["remaining_from"] == "exp038_sol_rest195"
    assert summary["projection"]["remaining_tasks"] == len(rest) + 1 == 196
    assert summary["projection"]["remaining_items"] == sum(items[task] for task in rest) + items[refused]
    assert document["remaining_task_ids"] == rest + [refused]
    assert type(summary["rules"]["R3"]) is bool and type(summary["rules"]["R4"]) is bool
    with pytest.raises(SystemExit):
        readout.main(["--repo-root", str(REPO_ROOT), "--stage", *exp037,
                      "--remaining-from", "exp038_sol_rest195", "--remaining-tasks", "195"])


def test_a_task_the_sol_harness_refused_is_infrastructure_not_a_sample(tmp_path):
    readout = _readout()
    first25 = _stage_tasks("exp037_sol_first25")
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"),
                          first25, harness=tuple(first25[20:]))
    summary = _run(readout, tmp_path, exp037, extra=("--remaining-from", "exp038_sol_rest195"))["summary"]
    # Not the model's zeros, and nothing to move: the harness refused before an attempt started.
    assert summary["zeros_by_cause"] == {"sol_gate": 5} and summary["moved_by_usd_gate"] == []
    assert summary["projection"]["attempted_sample"] == 20
    assert summary["usd"]["solve_per_task_mean"] == 6.0
    assert summary["time"]["solve_minutes_per_task_mean"] == 10.0
    # Five harness refusals of 25 are past R2's two.
    assert summary["rules"]["R2"] is False


def test_a_later_stage_replaces_a_refused_row_but_not_its_spend(tmp_path, registry):
    readout = _readout()
    registry.approve_exp038()
    first25 = _stage_tasks("exp037_sol_first25")
    refused = first25[24]
    # The gate refused the task's retry after an attempt that booked 40.
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"),
                          first25, refused=(refused,), refused_usd=40.0)
    single = _run(readout, tmp_path, exp037)["summary"]
    assert single["usd"]["solve"] == single["stages"][0]["solve_usd"] == 24 * 6.0 + 40.0
    assert single["usd"]["solve_per_task_mean"] == 6.0
    # exp038's approval PR appends the moved task to its list.
    rest = _stage_tasks("exp038_sol_rest195") + [refused]
    registry.list_tasks("exp038_sol_rest195", rest)
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", _this_tree_hash(readout, "exp038_v2_sol_max"), rest)
    document = _run(readout, tmp_path, exp037, exp038)
    summary = document["summary"]
    assert summary["tasks"] == summary["denominator"] == 220 and summary["rerun_after_usd_gate"] == [refused]
    assert summary["moved_by_usd_gate"] == [] and "usd_gate" not in summary["zeros_by_cause"]
    assert [(row["stage"], row["cause"]) for row in document["tasks"] if row["task_id"] == refused] == [
        ("exp038_sol_rest195", "judged")]
    # The replaced row's 40 stays in exp037's stage and in the union's solve.
    assert summary["stages"][0]["solve_usd"] == 24 * 6.0 + 40.0
    assert summary["usd"]["solve"] == 24 * 6.0 + 40.0 + 196 * 6.0
    # A judged task cannot be graded twice in one union.
    again = _stage_tasks("exp038_sol_rest195") + [first25[0]]
    registry.list_tasks("exp038_sol_rest195", again)
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", _this_tree_hash(readout, "exp038_v2_sol_max"), again)
    with pytest.raises(SystemExit, match="counts every task once"):
        _run(readout, tmp_path, exp037, exp038)


# -- the writer's journal ------------------------------------------------------------


def test_a_final_grade_is_read_with_the_journal_of_the_run_that_wrote_it(tmp_path):
    readout = _readout()
    first25 = _stage_tasks("exp037_sol_first25")
    # Two chunks: run 100 graded the first 13 tasks and committed a partial;
    # run 200 graded the other 12 and wrote the final grade.
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"), first25,
                          writer="200", earlier={"100": tuple(first25[:13])})
    journals = tmp_path / "exp037_sol_first25.journals"
    assert sorted(path.name for path in journals.iterdir()) == [
        "run-100-1.combined_usd.jsonl", "run-200-1.combined_usd.jsonl"]
    summary = _run(readout, tmp_path, exp037, extra=("--remaining-from", "exp038_sol_rest195"))["summary"]
    assert summary["usd"]["grading"] == summary["stages"][0]["grading_usd"] == 25 * 0.5
    assert summary["usd"]["grading_per_judged_item"] == 0.05
    # The last chunk's journal push failed and the grade was committed by hand:
    # that chunk's 6.00 would drop out of the stage's committed figure, its
    # per-item rate and the grading projection. check_grade_writers refuses
    # the pair's next grade on main for the same missing journal.
    (journals / "run-200-1.combined_usd.jsonl").unlink()
    with pytest.raises(SystemExit, match="was written by run 200 attempt 1, whose combined USD journal is not in"):
        _run(readout, tmp_path, exp037)
    grading = readout._batch_runner_module("sol_batch_grading")
    root = tmp_path / "repo"
    (root / "data/grades").mkdir(parents=True)
    shutil.copy(exp037[1], root / "data/grades" / (
        "exp037_sol_first25__judge_gpt-5_6-sol__exp037_v2_sol_max__cfg_0123456789abcdef__x.json"))
    with pytest.raises(grading.CombinedUsdRefused, match="was written by run 200 attempt 1"):
        grading.check_grade_writers(root, "exp037_sol_first25", "exp037_v2_sol_max",
                                    [{"path": "run-100-1.combined_usd.jsonl"}])
    # A grade that judged nothing spent nothing to read: no journal is needed.
    gated = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"), first25,
                         refused=tuple(first25))
    for path in journals.iterdir():
        path.unlink()
    assert _run(readout, tmp_path, gated)["summary"]["usd"]["grading"] == 0.0


# -- a projection needs a sample ------------------------------------------------------


def test_nothing_attempted_projects_nothing(tmp_path):
    readout = _readout()
    first25 = _stage_tasks("exp037_sol_first25")
    hashed = _this_tree_hash(readout, "exp037_v2_sol_max")
    # The USD gate refused every attempt (a lineage dispatched with no
    # admission room left): every task moves, and none is a sample.
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", hashed, first25, refused=tuple(first25))
    summary = _run(readout, tmp_path, exp037, extra=("--remaining-from", "exp038_sol_rest195"))["summary"]
    projection = summary["projection"]
    assert summary["zeros_by_cause"] == {"usd_gate": 25} and len(summary["moved_by_usd_gate"]) == 25
    assert (projection["attempted_sample"], projection["judged_item_sample"]) == (0, 0)
    assert projection["remaining_tasks"] == 220
    # Legs and chunks of 0 would read as "R3 and R4 hold" with nothing measured.
    for field in ("solve_usd_mean", "solve_usd_p90", "solve_legs", "grading_usd", "grading_chunks"):
        assert projection[field] is None, field
    assert summary["rules"]["R3"] is None and summary["rules"]["R4"] is None
    assert summary["time"] == {"solve_minutes_per_task_mean": None, "grading_seconds_per_judged_item": None}
    assert summary["usd"]["solve_per_task_mean"] is None and summary["usd"]["grading_per_judged_item"] is None
    # By hand, the same.
    summary = _run(readout, tmp_path, exp037, extra=("--remaining-tasks", "195", "--remaining-items", "9248"))[
        "summary"]
    assert summary["rules"]["R3"] is None and summary["rules"]["R4"] is None
    assert summary["projection"]["solve_legs"] is summary["projection"]["grading_chunks"] is None
    # The Sol harness refused every attempt: R2 fails, R3 and R4 are not evaluated.
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", hashed, first25, harness=tuple(first25))
    summary = _run(readout, tmp_path, exp037, extra=("--remaining-from", "exp038_sol_rest195"))["summary"]
    assert summary["zeros_by_cause"] == {"sol_gate": 25} and summary["rules"]["R2"] is False
    assert summary["rules"]["R3"] is None and summary["rules"]["R4"] is None
    # The same rows passed to summarise directly.
    rows = readout.read_stage("exp037_sol_first25", Path(exp037[1]), Path(exp037[2]),
                              tmp_path / "exp037_sol_first25.journals")
    direct = readout.summarise(rows, 25, 195, 9248)
    assert direct["rules"]["R3"] is direct["rules"]["R4"] is None
    assert direct["projection"]["solve_usd_p90"] is direct["projection"]["grading_usd"] is None


def test_nothing_judged_projects_no_grading(tmp_path):
    readout = _readout()
    first25 = _stage_tasks("exp037_sol_first25")
    # Every task left files and was attempted, but the judge marked no item
    # of any: the solve side is a sample, the grading side is not.
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"), first25,
                          grader_failed=tuple(first25))
    summary = _run(readout, tmp_path, exp037, extra=("--remaining-from", "exp038_sol_rest195"))["summary"]
    projection = summary["projection"]
    assert summary["zeros_by_cause"] == {"grader_other": 25}
    assert (projection["attempted_sample"], projection["judged_item_sample"]) == (25, 0)
    # The judge's calls still spent under the ceiling.
    assert summary["usd"]["grading"] == summary["stages"][0]["grading_usd"] == 25 * 0.5
    assert summary["usd"]["grading_per_judged_item"] is None
    assert summary["time"]["grading_seconds_per_judged_item"] is None
    assert projection["grading_usd"] is projection["grading_chunks"] is None and summary["rules"]["R4"] is None
    # 195 tasks at 10 minutes each: 1,950 minutes, 12 legs of 170.
    assert projection["solve_legs"] == 12 and summary["rules"]["R3"] is False
    assert projection["solve_usd_mean"] == round(6.0 * 195) and projection["solve_usd_p90"] == round(6.0 * 195)
