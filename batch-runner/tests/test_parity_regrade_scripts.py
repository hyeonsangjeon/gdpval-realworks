"""The parity regrade's two offline scripts, on synthetic grade payloads.

No parquet, no network, no model: the selector is the real one, handed
synthetic file lists, and the grades are small hand-built payloads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.rubric_loader import RubricItem, TaskRubric
from scripts import merge_parity_regrade as merge
from scripts import selection_diff_against_grade as sdiff

REV = "c" * 40


def _task(task_id: str, prompt: str = "Write the memo for the client.") -> TaskRubric:
    return TaskRubric(task_id=task_id, sector="s", occupation="o", prompt=prompt,
                      rubric_items=[RubricItem("i1", "The memo states the deadline.", 2, None)],
                      rubric_pretty="", reference_files=[], gold_deliverable_files=[])


def _row(task_id: str, *, status: str, rule: str, primaries: list[list[str]], support: list[str],
         error: str | None = None, pct: float = 0.0, full: float = 0.0, items: int = 1) -> dict:
    return {
        "task_id": task_id, "error": error, "pct": pct, "pct_full_denominator": full,
        "items": [{}] * items,
        "selected_deliverables": {
            "selection_status": status, "selection_rule": rule,
            "primary_targets": [{"paths": paths} for paths in primaries],
            "support_artifacts": support, "reference_files_excluded": [],
        },
    }


# -- selection_diff_against_grade --------------------------------------------


def test_only_a_selection_the_judge_would_now_see_differently_is_listed():
    same = _row("t-same", status="ok", rule="set_diff_single", primaries=[["memo.docx"]], support=[])
    now_ok = _row("t-now-ok", status="selection_error", rule="format_variant_no_match", primaries=[],
                  support=["memo.docx"], error="selection_error", items=3)
    grade = {"tasks": [same, now_ok]}
    tasks = {"t-same": _task("t-same"), "t-now-ok": _task("t-now-ok")}
    refused: list[dict] = []
    changed = sdiff.diff(grade, tasks, refused)
    assert [entry["task_id"] for entry in changed] == ["t-now-ok"]
    assert changed[0]["rubric_items"] == 3
    assert changed[0]["replayed"]["selection_status"] == "ok"
    assert changed[0]["replayed"]["primary_paths"] == [["memo.docx"]]
    assert refused == []


def test_a_task_refused_before_and_after_is_not_regraded():
    # Nothing the selector knows: refused at grading time and refused again,
    # with a different refusal detail. The judge sees nothing either way.
    row = _row("t-refused", status="selection_error", rule="some_older_rule", primaries=[],
               support=["a.bin", "b.bin"], error="selection_error")
    refused: list[dict] = []
    assert sdiff.diff({"tasks": [row]}, {"t-refused": _task("t-refused")}, refused) == []
    assert [entry["task_id"] for entry in refused] == ["t-refused"]


def test_a_file_recorded_twice_is_refused():
    row = _row("t-dup", status="ok", rule="set_diff_single", primaries=[["memo.docx"]], support=["memo.docx"])
    with pytest.raises(ValueError, match="recorded twice"):
        sdiff.recorded_files(row)


# -- merge_parity_regrade ----------------------------------------------------


def _grade(rows: list[dict], *, status: str = "final", revision: str = REV) -> dict:
    return {
        "experiment_id": "expX", "source_inference_repo_id": "o/expX", "source_inference_revision": revision,
        "judge": {"model": "gpt-5.6-sol", "reasoning_effort": "max"}, "prompt": {"version": "v2.2"},
        "rubric": {"commit_sha": "d" * 40}, "run_status": status, "expected_task_count": len(rows),
        "tasks": rows, "grader_source_hash": "h" * 64,
    }


def _published() -> dict:
    return _grade([
        _row("t1", status="ok", rule="r", primaries=[["a"]], support=[], pct=80.0, full=70.0),
        _row("t2", status="selection_error", rule="r", primaries=[], support=["b"], error="selection_error"),
        _row("t3", status="no_generated_candidate", rule="r", primaries=[], support=[], error="no_deliverables"),
        _row("t4", status="ok", rule="r", primaries=[["c"]], support=[], pct=60.0, full=60.0),
    ])


def test_the_merged_view_replaces_only_the_regraded_rows_and_keeps_both_denominators():
    published = _published()
    regrade = _grade([_row("t2", status="ok", rule="r2", primaries=[["b"]], support=[], pct=90.0, full=81.0)],
                     status="diagnostic")
    merge.check_pair(published, regrade)
    merged, per_task = merge.merge(published, regrade)
    before, after = merge.headline(published["tasks"]), merge.headline(merged)
    assert before["judged_only_mean_pct"] == 70.0 and before["fixed_denominator_mean_pct"] == 35.0
    assert after["judged_only_mean_pct"] == round((80 + 90 + 60) / 3, 4)
    assert after["fixed_denominator_mean_pct"] == 57.5
    assert after["fixed_denominator_mean_pct_full_denominator"] == round((70 + 81 + 0 + 60) / 4, 4)
    # No self report: the raw grade errors, under a key of their own.
    assert after["unjudged_by_grade_error"] == {"no_deliverables": 1}
    assert "unjudged_by_error" not in after
    assert [entry["task_id"] for entry in per_task] == ["t2"]
    assert per_task[0]["before"]["error"] == "selection_error" and per_task[0]["after"]["pct"] == 90.0


def test_zeros_are_split_by_their_inference_cause():
    published = _published()
    causes = {"t3": "content_filtered"}
    assert merge.headline(published["tasks"], causes)["unjudged_by_error"] == {
        "content_filter": 1, "grader_refusal": 1}
    assert merge.zero_cause({"task_id": "t9", "error": "no_deliverables"}, {"t9": "rate_limited"}) == "infrastructure"


RENDERER_OLD = {"libreoffice_version": "LibreOffice 24.2.7.2", "pymupdf_version": "1.28.2"}
RENDERER_NEW = {"libreoffice_version": "LibreOffice 24.2.7.2", "pymupdf_version": "2.1"}


def test_a_partial_regrade_names_what_its_merged_rows_mix():
    published = _published()
    published["renderer_fingerprint"] = RENDERER_OLD
    regrade = _grade([_row("t2", status="ok", rule="r2", primaries=[["b"]], support=[], pct=90.0, full=81.0)],
                     status="diagnostic")
    regrade["grader_source_hash"], regrade["renderer_fingerprint"] = "g" * 64, RENDERER_NEW
    assert merge.identity_caveat(published, regrade) == (
        "merged rows come from two grader source hashes, two renderer fingerprints and two judge draws; "
        "it is a parity view, not a published grade")
    # Same renderer, same source hash: only the judge draws still differ.
    regrade["grader_source_hash"], regrade["renderer_fingerprint"] = published["grader_source_hash"], RENDERER_OLD
    caveat = merge.identity_caveat(published, regrade)
    assert caveat.startswith("merged rows come from one grader source hash, one renderer fingerprint and two judge")
    assert "parity view, not a published grade" in caveat


def test_a_regrade_of_every_task_is_the_merged_view_itself():
    published = _published()
    published["renderer_fingerprint"] = RENDERER_NEW
    rows = [_row(task_id, status="ok", rule="r2", primaries=[["x"]], support=[], pct=90.0, full=90.0)
            for task_id in ("t1", "t2", "t3", "t4")]
    regrade = _grade(rows)
    regrade["grader_source_hash"], regrade["renderer_fingerprint"] = "g" * 64, RENDERER_NEW
    merge.check_pair(published, regrade)
    merged, per_task = merge.merge(published, regrade)
    assert merged == regrade["tasks"] and len(per_task) == 4
    caveat = merge.identity_caveat(published, regrade)
    assert caveat == ("the regrade replaces every published row, so the merged view is the regrade itself "
                      "(run_status final): one grader source hash, one renderer fingerprint and one judge draw")
    assert "two" not in caveat and "parity view" not in caveat


def test_each_side_of_a_comparison_names_its_zeros_in_one_vocabulary():
    published = _published()
    other = _grade([_row("t3", status="no_generated_candidate", rule="r", primaries=[], support=[],
                         error="no_deliverables"),
                    _row("t4", status="ok", rule="r", primaries=[["c"]], support=[], pct=70.0, full=70.0)])
    both = merge.compare(published["tasks"], other, {"t3": "rate_limited"}, {"t3": "content_filtered"})
    assert both["this"]["unjudged_by_error"] == {"infrastructure": 1}
    assert both["other"]["unjudged_by_error"] == {"content_filter": 1}
    # Without the other inference's self report its side keeps the raw grade
    # errors, and says so by its key, instead of mixing them in with causes.
    one = merge.compare(published["tasks"], other, {"t3": "rate_limited"})
    assert one["this"]["unjudged_by_error"] == {"infrastructure": 1}
    assert "unjudged_by_error" not in one["other"]
    assert one["other"]["unjudged_by_grade_error"] == {"no_deliverables": 1}
    means = {key: value for key, value in both["other"].items() if key != "unjudged_by_error"}
    assert {key: value for key, value in one["other"].items() if key != "unjudged_by_grade_error"} == means


@pytest.mark.parametrize("case", ["revision", "foreign_task", "order", "incomplete", "published_partial", "judge"])
def test_a_regrade_of_anything_else_is_refused(case):
    published = _published()
    rows = [_row("t2", status="ok", rule="r", primaries=[["b"]], support=[], pct=90.0, full=90.0),
            _row("t4", status="ok", rule="r", primaries=[["c"]], support=[], pct=60.0, full=60.0)]
    regrade = _grade(rows, status="diagnostic")
    if case == "revision":
        regrade["source_inference_revision"] = "e" * 40
    elif case == "foreign_task":
        regrade["tasks"][0]["task_id"] = "t9"
    elif case == "order":
        regrade["tasks"].reverse()
    elif case == "incomplete":
        regrade["expected_task_count"] = 3
    elif case == "published_partial":
        published["run_status"] = "partial"
    elif case == "judge":
        regrade["judge"] = {"model": "gpt-5.4", "reasoning_effort": "max"}
    with pytest.raises(SystemExit):
        merge.check_pair(published, regrade)


def test_the_cli_writes_a_run_record_and_never_a_grade_file(tmp_path, monkeypatch):
    published, regrade = _published(), _grade(
        [_row("t2", status="ok", rule="r2", primaries=[["b"]], support=[], pct=90.0, full=81.0)], status="diagnostic")
    for name, payload in (("pub.json", published), ("re.json", regrade)):
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "record.json"
    monkeypatch.setattr("sys.argv", ["merge_parity_regrade.py", "--published", str(tmp_path / "pub.json"),
                                     "--regrade", str(tmp_path / "re.json"), "--json-out", str(out)])
    assert merge.main() == 0
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["schema"] == "parity-regrade-record-v1"
    assert record["merged_headline"]["judged_tasks"] == 3
    assert "parity view" in record["mixed_identity_caveat"]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["pub.json", "re.json", "record.json"]


def test_a_comparison_self_report_without_a_comparison_is_refused(tmp_path, monkeypatch):
    published, regrade = _published(), _grade(
        [_row("t2", status="ok", rule="r2", primaries=[["b"]], support=[], pct=90.0, full=81.0)], status="diagnostic")
    for name, payload in (("pub.json", published), ("re.json", regrade), ("sr.json", {"task_results": []})):
        (tmp_path / name).write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["merge_parity_regrade.py", "--published", str(tmp_path / "pub.json"),
                                     "--regrade", str(tmp_path / "re.json"), "--compare-self-report",
                                     str(tmp_path / "sr.json"), "--json-out", str(tmp_path / "record.json")])
    with pytest.raises(SystemExit, match="needs --compare"):
        merge.main()
    assert not (tmp_path / "record.json").exists()
