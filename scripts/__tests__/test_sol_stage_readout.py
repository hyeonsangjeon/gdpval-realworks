"""scripts/sol_stage_readout.py on exp036's published records: the diagnosis's numbers, model-free."""
from __future__ import annotations

import importlib.util
import json
import shutil
from decimal import Decimal
from pathlib import Path

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
    assert summary["rules"]["R1"] is False and summary["rules"]["R2"] is True
    # One stage, one grader: the union check has nothing to disagree with.
    assert summary["one_grader"] is True
    assert summary["graders"][0]["grader_source_hash"].startswith("814d56797e9fc3dc")


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
