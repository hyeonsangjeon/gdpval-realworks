"""scripts/sol_stage_readout.py on exp036's published records and on stages built from the real configs.

Model-free and offline: the diagnosis's numbers for exp036, the cause table it
shares with merge_parity_regrade.py, the USD-gate rows it moves, and the
grader identity two stages with different configs can share.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sol_stage_readout.py"
GRADE = REPO_ROOT / (
    "data/grades/exp036_sol_fixed5__judge_gpt-5_6-sol__exp036_v2_sol_max__cfg_1794403983325602__rubric_"
    "11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_8708d9206ce4c9c9ba96f8bfba0745e12e597777__src_"
    "814d56797e9fc3dc__v2.2.json")
#: That grade's own journal. The exp036 regrade adds another journal to the
#: same directory, so the expected figures read this one file.
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
        "stage": "exp036_sol_fixed5", "ceiling_usd": 200.0, "solve_usd": 38.79, "narrative_allowance_usd": 2.0,
        "grading_usd": 10.72, "committed_usd": 51.51, "left_under_ceiling_usd": 148.49}]
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
    (journals / "run-1-1.combined_usd.jsonl").write_text(_journal_lines(
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


# -- two stages built from the real exp037 and exp038 configs ----------------------

EXPERIMENTS = REPO_ROOT / "batch-runner/experiments"
RENDERER = {"libreoffice_binary": "soffice", "libreoffice_version": "LibreOffice 24.2.7.2", "pymupdf_version": "2.1"}


def _stage_tasks(experiment_id: str) -> list[str]:
    document = yaml.safe_load((EXPERIMENTS / f"{experiment_id}.yaml").read_text(encoding="utf-8"))
    return document["data"]["filter"]["task_ids"]


def _this_tree_hash(readout, config_name: str) -> str:
    step8 = readout._batch_runner_module("step8_grade")
    relative = f"grading_configs/{config_name}.yaml"
    config = yaml.safe_load((readout.BATCH_RUNNER / relative).read_text(encoding="utf-8"))
    return step8.compute_grader_source_hash(relative, config, batch_root=readout.BATCH_RUNNER)


def _write_stage(tmp_path: Path, experiment_id: str, source_hash: str, tasks: list[str], *,
                 refused: tuple[str, ...] = (), renderer: dict = RENDERER) -> list[str]:
    """A grade and a self_report.json for ``tasks``; ``refused`` never left the USD gate."""
    grade_rows, report_rows = [], []
    for task in tasks:
        if task in refused:
            grade_rows.append({"task_id": task, "error": "no_deliverables", "judge_call_count": 0})
            report_rows.append({"task_id": task, "status": "error", "latency_ms": 10, "deliverable_files": [],
                                "observability": {"error_category": "usd_ceiling_reached",
                                                  "budget_metrics": {"conservative_cost_usd": 0}}})
            continue
        grade_rows.append({"task_id": task, "error": None, "pct": 50.0, "pct_full_denominator": 40.0,
                           "items": [{}] * 10, "score_excluded_items": 0, "grading_wall_time_ms": 60_000,
                           "judge_call_count": 3, "selection_rule": "single_main"})
        report_rows.append({"task_id": task, "status": "success", "latency_ms": 600_000,
                            "deliverable_files": [f"deliverable_files/{task}/answer.docx"],
                            "observability": {"budget_metrics": {"conservative_cost_usd": 6.0}}})
    grade = {"tasks": grade_rows, "grader_source_hash": source_hash, "renderer_fingerprint": renderer,
             "judge": {"model": "gpt-5.6-sol", "reasoning_effort": "max"}, "prompt": {"version": "v2.2"},
             "rubric": {"commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf"}}
    (tmp_path / f"{experiment_id}.grade.json").write_text(json.dumps(grade), encoding="utf-8")
    (tmp_path / f"{experiment_id}.self_report.json").write_text(
        json.dumps({"meta": {"experiment_id": experiment_id}, "task_results": report_rows}), encoding="utf-8")
    (tmp_path / f"{experiment_id}.journals").mkdir(exist_ok=True)
    return [experiment_id, str(tmp_path / f"{experiment_id}.grade.json"),
            str(tmp_path / f"{experiment_id}.self_report.json")]


def _run(readout, tmp_path: Path, *stages: list[str], extra: tuple[str, ...] = ()) -> dict:
    out = tmp_path / "out.json"
    argv = ["--repo-root", str(REPO_ROOT), "--json", str(out)]
    for stage in stages:
        argv += ["--stage", *stage, "--journals-dir", stage[0], str(tmp_path / f"{stage[0]}.journals")]
    readout.main(argv + list(extra))
    return json.loads(out.read_text(encoding="utf-8"))


def test_two_stages_with_their_own_configs_can_be_one_grader(tmp_path):
    readout = _readout()
    first, rest = _this_tree_hash(readout, "exp037_v2_sol_max"), _this_tree_hash(readout, "exp038_v2_sol_max")
    # The configs differ only in their name and description, and the raw
    # hash covers the config file: equal raw hashes are impossible.
    assert first != rest
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", first, _stage_tasks("exp037_sol_first25")[:3])
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", rest, _stage_tasks("exp038_sol_rest195")[:2])
    summary = _run(readout, tmp_path, exp037, exp038)["summary"]
    assert summary["one_grader"] is True and summary["one_grader_problems"] == []
    assert [(stage["stage"], stage["ceiling_usd"]) for stage in summary["stages"]] == [
        ("exp037_sol_first25", 700.0), ("exp038_sol_rest195", None)]
    assert summary["stages"][0]["committed_usd"] == 3 * 6.0 + 2.0
    assert [grader["graded_by_this_tree"] for grader in summary["graders"]] == [True, True]
    assert len({grader["template_blocks_sha256"] for grader in summary["graders"]}) == 1

    # Another renderer marks the second stage differently, however the code agrees.
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", rest, _stage_tasks("exp038_sol_rest195")[:2],
                          renderer={**RENDERER, "pymupdf_version": "1.28.2"})
    summary = _run(readout, tmp_path, exp037, exp038)["summary"]
    assert summary["one_grader"] is False
    assert summary["one_grader_problems"] == ["the stages differ in renderer_fingerprint"]

    # A grade whose hash is not this tree's for its own config was marked by
    # another closure, or under another config.
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", first, _stage_tasks("exp038_sol_rest195")[:2])
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
    with pytest.raises(SystemExit):
        readout.main(["--repo-root", str(REPO_ROOT), "--stage", *exp037,
                      "--remaining-from", "exp038_sol_rest195", "--remaining-tasks", "195"])


def test_a_later_stage_replaces_a_refused_row_and_nothing_else(tmp_path):
    readout = _readout()
    first25 = _stage_tasks("exp037_sol_first25")
    refused = first25[24]
    exp037 = _write_stage(tmp_path, "exp037_sol_first25", _this_tree_hash(readout, "exp037_v2_sol_max"),
                          first25[:3] + [refused], refused=(refused,))
    exp038 = _write_stage(tmp_path, "exp038_sol_rest195", _this_tree_hash(readout, "exp038_v2_sol_max"),
                          [refused] + _stage_tasks("exp038_sol_rest195")[:1])
    document = _run(readout, tmp_path, exp037, exp038)
    summary = document["summary"]
    assert summary["tasks"] == 5 and summary["rerun_after_usd_gate"] == [refused]
    assert summary["moved_by_usd_gate"] == [] and "usd_gate" not in summary["zeros_by_cause"]
    assert [(row["stage"], row["cause"]) for row in document["tasks"] if row["task_id"] == refused] == [
        ("exp038_sol_rest195", "judged")]
    # A judged task cannot be graded twice in one union.
    again = _write_stage(tmp_path, "exp038_sol_rest195", _this_tree_hash(readout, "exp038_v2_sol_max"),
                         first25[:1])
    with pytest.raises(SystemExit, match="counts every task once"):
        _run(readout, tmp_path, exp037, again)
