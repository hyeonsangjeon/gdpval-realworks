"""Tests for the gold-ceiling analysis tool.

The tool exists so that stage 1's report quotes a run rather than restating
one. That only holds if three things are true, and each has a test here.

The thresholds have to be the specification's thresholds. They are written as
constants in the script, so ``test_the_thresholds_are_the_ones_the_spec_states``
holds them against the specification text: an acceptance bar loosened in the
code and not in the document fails rather than passes quietly.

The payload has to be the run that was pinned. Stage 2 will produce repeats and
every run produces shards, all of them structurally identical and all of them
wrong to read stage 1's number out of. The identity check refuses each, and
refuses a payload whose graded count does not match the count it declares.

And the tool has to survive a fresh clone. ``batch-runner/scripts/`` is ignored
with a per-file allow list, so a script added there works for whoever wrote it
and is absent for everyone else -- which is exactly how the manifest builder
reached CI red on an earlier pass of this same work.
"""

import json
from pathlib import Path
import subprocess

import pytest

from scripts import analyze_gold_ceiling as analysis


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/300-gold-ceiling.md"
TOOL_PATH = "batch-runner/scripts/analyze_gold_ceiling.py"


def _item(**overrides):
    item = {
        "rubric_item_id": "item-1",
        "criterion": "The workbook opens.",
        "max_score": 2,
        "awarded_score": 2.0,
        "verdict": "pass",
        "decided_by": "judge",
        "required": None,
        "evidence": "opened cleanly",
        "judge_confidence": 1.0,
        "routing_modality": "text",
        "perception_called": False,
        "perception_call_count": 0,
        "selection_status": "ok",
        "selection_error": None,
        "selected_paths": ["Sample.xlsx"],
        "score_excluded": False,
    }
    item.update(overrides)
    return item


def _task(task_id="task-1", items=None, **overrides):
    task = {
        "task_id": task_id,
        "sector": "Government",
        "occupation": "Auditor",
        "critical_fail": False,
        "error": None,
        "items": items if items is not None else [_item()],
    }
    task.update(overrides)
    return task


def _payload(tasks=None, **overrides):
    """A payload shaped like a real one and passing every identity check."""
    payload = {
        "experiment_id": "exp_gold_baseline",
        "run_status": "final",
        "graded_at": "2026-08-28T15:00:00Z",
        "judge": {"model": "gpt-5.6-sol"},
        "grader_source_hash": "a" * 64,
        "renderer_fingerprint": "libreoffice-24.2.7.2",
        "source_inference_revision": "1" * 40,
        "source_azure_ai_provenance_status": "gold-corpus",
        "expected_task_count": analysis.EXPECTED_TASK_COUNT,
        "expected_ordered_task_ids_sha256": (
            analysis.EXPECTED_ORDERED_TASK_IDS_SHA256
        ),
        "shard_provenance": None,
        "tasks": tasks if tasks is not None else [_task()],
        "summary": {
            "total_tasks": analysis.EXPECTED_TASK_COUNT,
            "graded_tasks": analysis.EXPECTED_TASK_COUNT,
            "error_tasks": 0,
            "openai_compat": {
                "avg_score_pct": 96.4,
                "ci_pct": 2.1,
                "perfect_count": 20,
                "zero_count": 0,
                "partial_count": 10,
            },
            "wow": {
                "critical_item_pass_rate": 0.98,
                "judge_error_rate": 0.004,
                "judge_pass_rate": 0.95,
                "precheck_pass_rate": 0.0,
                "rubric_item_coverage_avg": 0.97,
                "by_sector": {"Government": {"task_count": 30, "avg_pct": 96.4}},
                "score_density_histogram": [],
            },
            "cost": {
                "total_judge_calls": 1433,
                "total_main_judge_calls": 1400,
                "total_perception_calls": 33,
                "total_render_calls": 33,
                "main_input_tokens": 3_900_000,
                "main_output_tokens": 340_000,
                "main_cached_tokens": 1_000_000,
                "perception_input_tokens": 50_000,
                "perception_output_tokens": 6_000,
                "perception_cached_tokens": 0,
                "total_judge_latency_sec": 34567.8,
                "estimated_cost_usd": None,
                "pricing_complete": False,
                "unpriced_models": ["gpt-5.6-sol", "gpt-audio-1.5"],
                "usage_complete": True,
            },
        },
    }
    payload.update(overrides)
    return payload


# ── The thresholds are the specification's ─────────────────────────────────


def test_the_thresholds_are_the_ones_the_spec_states():
    """A bar moved in the code and not in the document must fail here.

    The specification writes them once as a list of expectations and again as
    the acceptance criteria, so both spellings are checked -- loosening either
    alone would leave the document self-contradictory and this green.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert f"≥ {analysis.MEAN_SCORE_PCT_FLOOR:.0f}%" in spec
    assert f"≥ {analysis.CRITICAL_ITEM_PASS_FLOOR}" in spec
    assert f"< {analysis.JUDGE_ERROR_RATE_CEILING:.0%}" in spec
    assert (
        f"{analysis.MEAN_SCORE_PCT_FLOOR:.0f}% / "
        f"{analysis.CRITICAL_ITEM_PASS_FLOOR} / "
        f"{analysis.JUDGE_ERROR_RATE_CEILING:.0%}"
    ) in spec


def test_the_pinned_corpus_matches_the_grading_config():
    """The 30 the tool insists on are the 30 the run was told to grade."""
    import hashlib

    import yaml

    config = yaml.safe_load(
        (
            REPO_ROOT / "batch-runner/grading_configs/gold_ceiling_30_v2_sol_max.yaml"
        ).read_text(encoding="utf-8")
    )
    pinned = config["rerun_identity"]["task_ids"]

    assert len(pinned) == analysis.EXPECTED_TASK_COUNT
    digest = hashlib.sha256("\n".join(pinned).encode("utf-8")).hexdigest()
    assert digest == analysis.EXPECTED_ORDERED_TASK_IDS_SHA256


# ── Only stage 1's own run may be read as stage 1's number ─────────────────


def test_a_complete_pinned_run_is_accepted():
    assert analysis._identity_problems(_payload()) == []


def test_a_shard_is_refused():
    """A shard's aggregates cover its slice, and read like the whole run's."""
    problems = analysis._identity_problems(_payload(run_status="partial"))

    assert any("run_status" in problem for problem in problems)


def test_a_complete_run_is_accepted_under_either_spelling():
    """Sharding, not completeness, decides which word a gold run gets.

    `step8_grade.py` calls a gold-corpus run `diagnostic` so that it forks away
    from the dashboard, but `step9_merge_shards.py` writes a flat `final` when
    it joins shards back up. So the same thirty tasks, fully graded, land under
    one name or the other purely on whether the run was split. Refusing
    `diagnostic` would refuse a complete single-shard repeat -- and stage 2 is
    made of repeats.
    """
    for status in ("final", "diagnostic"):
        assert analysis._identity_problems(_payload(run_status=status)) == [], status


def test_a_run_with_no_status_at_all_is_refused():
    """Absent is not complete. A payload that never says must not be assumed."""
    payload = _payload()
    payload.pop("run_status")

    problems = analysis._identity_problems(payload)

    assert any("run_status" in problem for problem in problems)


def test_a_different_corpus_is_refused():
    problems = analysis._identity_problems(
        _payload(expected_ordered_task_ids_sha256="b" * 64)
    )

    assert any("ordered_task_ids" in problem for problem in problems)


def test_a_run_that_graded_fewer_tasks_than_it_declared_is_refused():
    """The declared count and the graded count disagreeing is the whole point.

    A payload can claim 30 while holding 12 -- that is what a merge failure
    looks like -- and its mean would be the mean of 12.
    """
    payload = _payload()
    payload["summary"]["graded_tasks"] = 12

    problems = analysis._identity_problems(payload)

    assert any("graded_tasks" in problem for problem in problems)


def test_the_command_line_refuses_rather_than_reporting(tmp_path):
    grade_file = tmp_path / "shard.json"
    grade_file.write_text(json.dumps(_payload(run_status="partial")))

    with pytest.raises(SystemExit) as refused:
        analysis.main([str(grade_file)])

    assert "not the run stage 1 pinned" in str(refused.value)


def test_the_refusal_can_be_overridden_on_purpose(tmp_path, capsys):
    """Looking inside one shard is a legitimate thing to want to do.

    Not for a number any report quotes -- a shard's mean is the mean of its
    slice -- but for working out which shard a bad task landed in.
    """
    grade_file = tmp_path / "repeat.json"
    grade_file.write_text(json.dumps(_payload(run_status="partial")))

    exit_code = analysis.main([str(grade_file), "--allow-any-run", "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["gates"]["mean_score_pct"]["met"]


# ── The three gates ────────────────────────────────────────────────────────


def test_every_gate_met_reports_success():
    report = analysis.analyze(_payload())

    assert report["all_gates_met"]
    assert report["gates"]["mean_score_pct"]["met"]
    assert report["gates"]["critical_item_pass_rate"]["met"]
    assert report["gates"]["judge_error_rate"]["met"]


@pytest.mark.parametrize(
    "block, field, value, gate",
    [
        ("openai_compat", "avg_score_pct", 89.9, "mean_score_pct"),
        ("wow", "critical_item_pass_rate", 0.94, "critical_item_pass_rate"),
        ("wow", "judge_error_rate", 0.02, "judge_error_rate"),
    ],
)
def test_a_missed_gate_is_reported_and_exits_nonzero(
    block, field, value, gate, tmp_path
):
    """Just under each bar, including the error rate's exact boundary.

    The error rate is specified as strictly under 2%, so 0.02 itself misses.
    """
    payload = _payload()
    payload["summary"][block][field] = value
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    report = analysis.analyze(payload)
    assert not report["gates"][gate]["met"]
    assert not report["all_gates_met"]

    assert analysis.main([str(grade_file)]) == 1


def test_the_bars_themselves_are_met():
    """Exactly at each bar passes, so the comparison is not off by one side."""
    payload = _payload()
    payload["summary"]["openai_compat"]["avg_score_pct"] = 90.0
    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.95
    payload["summary"]["wow"]["judge_error_rate"] = 0.0199

    assert analysis.analyze(payload)["all_gates_met"]


def test_a_missing_number_is_a_miss_rather_than_a_pass():
    """A payload with no mean must not read as clearing the bar."""
    payload = _payload()
    payload["summary"]["openai_compat"].pop("avg_score_pct")

    report = analysis.analyze(payload)

    assert not report["gates"]["mean_score_pct"]["met"]
    assert not report["all_gates_met"]


# ── Image and audio, counted apart ─────────────────────────────────────────


def test_perception_calls_are_split_by_modality():
    """The specification asks for the image and audio counts separately.

    ``summary.cost`` only carries their sum, so the split has to come from the
    rubric items.
    """
    payload = _payload(
        tasks=[
            _task(
                "task-1",
                items=[
                    _item(routing_modality="visual", perception_call_count=3),
                    _item(routing_modality="audio", perception_call_count=2),
                    _item(routing_modality="text", perception_call_count=0),
                ],
            ),
            _task(
                "task-2",
                items=[_item(routing_modality="visual", perception_call_count=1)],
            ),
        ]
    )

    assert analysis.perception_calls_by_modality(payload) == {
        "audio": 2,
        "visual": 4,
    }


def test_a_perception_call_with_no_recorded_modality_is_still_counted():
    """Dropping it would make the parts silently smaller than the whole."""
    payload = _payload(
        tasks=[
            _task(
                items=[_item(routing_modality=None, perception_call_count=5)],
            )
        ]
    )

    assert analysis.perception_calls_by_modality(payload) == {"unrecorded": 5}


# ── The shortfalls a person has to classify ────────────────────────────────


def test_only_items_below_their_maximum_are_listed():
    payload = _payload(
        tasks=[
            _task(
                items=[
                    _item(rubric_item_id="full", awarded_score=2.0, max_score=2),
                    _item(rubric_item_id="short", awarded_score=0.5, max_score=2),
                ]
            )
        ]
    )

    listed = analysis.items_below_full_marks(payload)

    assert [row["rubric_item_id"] for row in listed] == ["short"]
    assert listed[0]["lost"] == 1.5


def test_an_excluded_item_is_not_counted_as_a_shortfall():
    """A score the config excludes did not fall short; it was not in play."""
    payload = _payload(
        tasks=[
            _task(
                items=[
                    _item(awarded_score=0.0, max_score=3, score_excluded=True),
                ]
            )
        ]
    )

    assert analysis.items_below_full_marks(payload) == []


def test_the_biggest_losses_come_first():
    """The readable report truncates, so order decides what a reader sees."""
    payload = _payload(
        tasks=[
            _task(
                items=[
                    _item(rubric_item_id="small", awarded_score=1.0, max_score=2),
                    _item(rubric_item_id="large", awarded_score=0.0, max_score=5),
                    _item(rubric_item_id="middle", awarded_score=1.0, max_score=4),
                ]
            )
        ]
    )

    assert [row["rubric_item_id"] for row in analysis.items_below_full_marks(payload)] == [
        "large",
        "middle",
        "small",
    ]


def test_the_evidence_a_classification_needs_travels_with_the_shortfall():
    """Library limit or genuine miss is decided from these fields."""
    payload = _payload(
        tasks=[
            _task(
                items=[
                    _item(
                        awarded_score=0.0,
                        max_score=2,
                        verdict="fail",
                        evidence="the renderer produced no page for slide 4",
                        routing_modality="visual",
                        selection_status="ok",
                    )
                ]
            )
        ]
    )

    row = analysis.items_below_full_marks(payload)[0]

    assert row["evidence"] == "the renderer produced no page for slide 4"
    assert row["routing_modality"] == "visual"
    assert row["verdict"] == "fail"
    assert row["criterion"]
    assert row["task_id"] == "task-1"


def test_a_task_that_failed_a_required_item_is_named():
    payload = _payload(
        tasks=[_task("task-1"), _task("task-2", critical_fail=True)]
    )

    report = analysis.analyze(payload)

    assert report["shortfalls"]["tasks_failing_a_required_item"] == ["task-2"]


def test_a_task_that_errored_is_named_with_its_error():
    payload = _payload(tasks=[_task("task-1", error="judge timed out")])

    report = analysis.analyze(payload)

    assert report["shortfalls"]["tasks_with_errors"] == [
        {"task_id": "task-1", "error": "judge timed out"}
    ]


# ── An unpriced run is never reported as free ──────────────────────────────


def test_an_unpriced_run_is_reported_as_unknown_rather_than_zero(tmp_path, capsys):
    """`gpt-5.6-sol` and `gpt-audio-1.5` have no published price.

    Rendering that as $0 would be the one wrong answer, because it reads as
    "this cost nothing" rather than "nobody can say what this cost".
    """
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(_payload()))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "UNKNOWN" in printed
    assert "gpt-5.6-sol" in printed
    assert "$0" not in printed


def test_a_priced_run_shows_its_total(tmp_path, capsys):
    payload = _payload()
    payload["summary"]["cost"]["pricing_complete"] = True
    payload["summary"]["cost"]["estimated_cost_usd"] = 412.75
    payload["summary"]["cost"]["unpriced_models"] = []
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])

    assert "$412.75" in capsys.readouterr().out


# ── The readable report stays readable ─────────────────────────────────────


def test_the_libreoffice_version_is_named_on_its_own_line(tmp_path, capsys):
    """It is one of the frozen things, so it should not need digging out."""
    payload = _payload(
        renderer_fingerprint={
            "libreoffice_binary": "soffice",
            "libreoffice_version": "LibreOffice 24.2.7.2 420(Build:2)",
            "pymupdf_version": "1.28.2",
        }
    )
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "renderer        LibreOffice 24.2.7.2 420(Build:2), pymupdf 1.28.2" in printed


def test_many_failing_tasks_are_listed_down_the_page(tmp_path, capsys):
    """One line of a hundred identifiers is a line nobody reads."""
    tasks = [_task(f"task-{n:02d}", critical_fail=True) for n in range(12)]
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(_payload(tasks=tasks)))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "required item failed in 12 task(s):" in printed
    assert max(len(line) for line in printed.splitlines()) < 120
    for task in tasks:
        assert task["task_id"] in printed


# ── The contract must survive a fresh clone ────────────────────────────────


def test_the_tool_is_in_the_repository():
    """``batch-runner/scripts/`` is ignored except by an explicit allow list.

    A script written here and left out of that list runs for its author and is
    missing for CI, which is how an earlier pass of this work reached red.
    """
    assert (REPO_ROOT / TOOL_PATH).is_file()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", TOOL_PATH],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{TOOL_PATH} exists here but git does not track it, so a fresh clone "
        "would not have it. Add it to the allow list in .gitignore."
    )
