"""Tests for the gold-ceiling analysis tool.

The tool exists so that a stage's report quotes a run rather than restating
one. That only holds if four things are true, and each has a test here.

The thresholds have to be the specification's thresholds. They are written as
constants in the script, so ``test_the_thresholds_are_the_ones_the_spec_states``
holds them against the specification text: an acceptance bar loosened in the
code and not in the document fails rather than passes quietly.

The payload has to be one of the pinned corpora. Stage 2 produces repeats and
every run produces shards, all of them structurally identical and all of them
wrong to read a stage's number out of. The identity check refuses each, refuses
a payload whose graded count does not match the count it declares, and decides
*which* corpus a payload is from its ordered-id fingerprint rather than from
its size -- so stage 1's thirty and stage 3's hundred and eighty-five are both
read, and neither can be mistaken for the other.

The counting rules have to be the grader's counting rules. The second threshold
counts ``model_did_right`` over unexcluded items whose score magnitude reaches
the grader's own ``MAGNITUDE_THRESHOLD``, and for a penalty item that is the
*opposite* of a ``pass`` verdict. `_model_did_right` restates that rule for the
fixtures and ``test_the_helper_agrees_with_the_grader`` runs the real
`core.grader._aggregate` over the same cases to keep the restatement honest.

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


def _model_did_right(verdict, max_score, score_excluded):
    """The grader's own rule, from `core.grader._aggregate` lines 1352-1361.

    Restated here rather than imported because the grader computes it while
    building `ItemGrade` objects, not as a function a test can call. Restating
    it is only safe because `test_the_helper_agrees_with_the_grader` runs the
    real `_aggregate` over the same four cases and compares.
    """
    if verdict == "judge_error":
        return False
    if score_excluded:
        return True
    if (max_score or 0) < 0:
        return verdict != "pass"
    return verdict == "pass"


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
    # A real payload never carries a verdict without this flag beside it, and
    # the analysis counts the flag. A fixture that omitted it would let a test
    # assert a rate no run could produce.
    if "model_did_right" not in overrides:
        item["model_did_right"] = _model_did_right(
            item["verdict"], item["max_score"], item["score_excluded"]
        )
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


def test_the_spec_records_that_the_middle_bar_stopped_deciding():
    """The demotion is an owner decision, so it lives in the document too.

    The bar itself stays written where it always was -- the test above still
    demands both spellings of `0.95`. What this adds is that the document has
    to say the bar no longer gates, so a reader who finds `critical_pass ≥
    0.95` under `## Acceptance` is not left believing a stage still turns on
    it.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "critical_pass`는 더 이상 합격을 가르지 않는다" in spec
    assert "REQUIRED_ITEM_DEFINITION.md" in spec
    # The reason, not just the ruling: the rubric field the name implies is
    # empty, so magnitude stands in for it.
    assert f"abs(max_score) >= {analysis.REQUIRED_ITEM_MIN_ABS_SCORE}" in spec
    assert "not recorded" in spec


def test_the_pinned_corpora_match_the_grading_configs():
    """The tasks each corpus insists on are the tasks its run was told to grade.

    Recomputed through ``step8_grade``'s own function rather than by restating
    its formula here. The constant is compared against a field that function
    writes, so a second spelling of "hash these ids" is a second thing that can
    drift -- and it did: a newline-joined digest of these very ids sat in the
    constant and refused stage 1's own run, saying nothing about the corpus
    while looking exactly like a corpus mismatch.

    Both corpora are checked, because the second was added by hand from a
    measurement and a mistyped digit would refuse stage 3's own run the same
    way.
    """
    import yaml

    from step8_grade import _ordered_task_ids_sha256

    for corpus in analysis.PINNED_CORPORA:
        config = yaml.safe_load(
            (
                REPO_ROOT
                / f"batch-runner/grading_configs/{corpus.config_name}.yaml"
            ).read_text(encoding="utf-8")
        )
        pinned = config["rerun_identity"]["task_ids"]

        assert len(pinned) == corpus.task_count, corpus.key
        assert (
            _ordered_task_ids_sha256(pinned) == corpus.ordered_task_ids_sha256
        ), corpus.key


def test_the_back_compatible_names_still_point_at_stage_one():
    """Six call sites and the report's own blocks grew up around these."""
    assert analysis.EXPECTED_TASK_COUNT == analysis.STAGE_ONE_CORPUS.task_count
    assert (
        analysis.EXPECTED_ORDERED_TASK_IDS_SHA256
        == analysis.STAGE_ONE_CORPUS.ordered_task_ids_sha256
    )


def test_stage_ones_thirty_are_the_first_thirty_of_stage_threes():
    """The same-30 comparison rests on this, so it is checked rather than assumed.

    `step9_merge_shards.py` normalises shards back into canonical corpus order
    before writing, so a merged 185-task payload's first thirty entries are
    stage 1's corpus -- *if* stage 1's config was itself cut from the front of
    the same canonical order. That is a property of two YAML files, and this is
    where it is established.
    """
    import yaml

    from step8_grade import _ordered_task_ids_sha256

    def ids(corpus):
        return yaml.safe_load(
            (
                REPO_ROOT
                / f"batch-runner/grading_configs/{corpus.config_name}.yaml"
            ).read_text(encoding="utf-8")
        )["rerun_identity"]["task_ids"]

    thirty = ids(analysis.STAGE_ONE_CORPUS)
    hundred_and_eighty_five = ids(analysis.STAGE_THREE_CORPUS)

    assert hundred_and_eighty_five[:30] == thirty
    assert (
        _ordered_task_ids_sha256(hundred_and_eighty_five[:30])
        == analysis.STAGE_ONE_CORPUS.ordered_task_ids_sha256
    )


# ── Only a pinned corpus's own run may be read as its number ───────────────


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
    assert any("stage1-30" in problem for problem in problems)
    assert any("stage3-185" in problem for problem in problems)


def test_the_185_task_corpus_is_read_without_a_flag():
    """Stage 3's run is a first-class corpus, not something read past a warning.

    ``--allow-any-run``'s own help says it is *never* for a number a report
    will quote, and stage 3's report quotes every number in its payload. So the
    corpus is pinned rather than waved through.
    """
    corpus = analysis.STAGE_THREE_CORPUS
    payload = _payload(
        expected_task_count=corpus.task_count,
        expected_ordered_task_ids_sha256=corpus.ordered_task_ids_sha256,
    )
    payload["summary"]["graded_tasks"] = corpus.task_count

    assert analysis._identity_problems(payload) == []
    assert analysis.identify_corpus(payload) is corpus
    assert analysis.analyze(payload)["identity"]["corpus"] == "stage3-185"


def test_the_digest_decides_which_corpus_it_is_not_the_count():
    """A 185-task digest carrying stage 1's count is a merge that lost tasks.

    Matching on the count first would let this pass as stage 1 while holding
    stage 3's fingerprint. Matching on the digest first names it: this is
    stage 3's corpus, and 155 of it is missing.
    """
    corpus = analysis.STAGE_THREE_CORPUS
    payload = _payload(
        expected_task_count=30,
        expected_ordered_task_ids_sha256=corpus.ordered_task_ids_sha256,
    )

    problems = analysis._identity_problems(payload)

    assert any(
        "expected_task_count is 30" in problem and "stage3-185" in problem
        for problem in problems
    ), problems


def test_an_unpinned_payload_read_with_the_flag_says_it_is_unpinned(tmp_path, capsys):
    """The readable report must not imply a corpus it could not identify."""
    grade_file = tmp_path / "shard.json"
    grade_file.write_text(
        json.dumps(_payload(expected_ordered_task_ids_sha256="c" * 64))
    )

    analysis.main([str(grade_file), "--allow-any-run", "--shortfall-limit", "0"])

    assert "unpinned corpus" in capsys.readouterr().out


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

    assert "is not a pinned corpus, fully graded" in str(refused.value)


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


# ── The two gates, and the diagnostic that stopped being one ───────────────


def test_every_gate_met_reports_success():
    report = analysis.analyze(_payload())

    assert report["all_gates_met"]
    assert report["gates"]["mean_score_pct"]["met"]
    assert report["gates"]["judge_error_rate"]["met"]


def test_the_high_magnitude_rate_is_not_a_gate():
    """The owner decision, pinned where the exit code reads it.

    `main` returns `0 if report["all_gates_met"]`, so anything left in `gates`
    keeps deciding the stage no matter what the label around it says. The rate
    has to be *absent* from that dict, not merely annotated inside it.
    """
    report = analysis.analyze(_payload())

    assert "critical_item_pass_rate" not in report["gates"]
    assert set(report["gates"]) == {"mean_score_pct", "judge_error_rate"}
    assert analysis.CRITICAL_ITEM_PASS_DECIDES_VERDICT is False

    diagnostic = report["diagnostics"]["high_magnitude_item_pass_rate"]
    assert diagnostic["decides_verdict"] is False
    # Still measured and still reported against the number the spec wrote --
    # demoted, not deleted.
    assert diagnostic["value"] == _payload()["summary"]["wow"][
        "critical_item_pass_rate"
    ]
    assert diagnostic["reference"] == analysis.CRITICAL_ITEM_PASS_FLOOR
    assert diagnostic["min_abs_score"] == analysis.REQUIRED_ITEM_MIN_ABS_SCORE


def test_a_run_far_under_the_old_bar_still_passes_on_the_two_real_gates():
    """The demotion's whole effect, stated as a number.

    A run that would have failed only on the retired gate now passes. That is
    the intended change and it should be visible here rather than inferred.
    """
    payload = _payload()
    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.10

    report = analysis.analyze(payload)

    assert report["all_gates_met"]
    assert report["diagnostics"]["high_magnitude_item_pass_rate"]["value"] == 0.10
    assert not report["diagnostics"]["high_magnitude_item_pass_rate"][
        "meets_reference"
    ]


@pytest.mark.parametrize(
    "block, field, value, gate",
    [
        ("openai_compat", "avg_score_pct", 89.9, "mean_score_pct"),
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


def test_a_missed_high_magnitude_rate_no_longer_exits_nonzero(tmp_path):
    """The same 0.94 that used to fail the run, now only reported."""
    payload = _payload()
    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.94
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    assert analysis.analyze(payload)["all_gates_met"]
    assert analysis.main([str(grade_file)]) == 0


def test_the_bars_themselves_are_met():
    """Exactly at each bar passes, so the comparison is not off by one side."""
    payload = _payload()
    payload["summary"]["openai_compat"]["avg_score_pct"] = 90.0
    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.95
    payload["summary"]["wow"]["judge_error_rate"] = 0.0199

    assert analysis.analyze(payload)["all_gates_met"]


def test_the_retired_bar_is_still_compared_so_the_distance_stays_readable():
    """Demoted, not deleted: the 0.95 the spec wrote is still reported against."""
    payload = _payload(
        tasks=[_task("task-1", items=[_item(max_score=5, verdict="pass")])]
    )
    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.95

    diagnostic = analysis.analyze(payload)["diagnostics"][
        "high_magnitude_item_pass_rate"
    ]

    assert diagnostic["reference"] == 0.95
    assert diagnostic["meets_reference"] is True

    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.94
    assert not analysis.analyze(payload)["diagnostics"][
        "high_magnitude_item_pass_rate"
    ]["meets_reference"]


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


def _receipt(**overrides):
    """A schema-1.4 grading receipt as `step8_grade` writes it."""
    receipt = {
        "schema_version": "cost-receipt-v1",
        "status": "complete",
        "currency": "USD",
        "estimated_cost_usd": 412.75,
        "known_cost_usd": 412.75,
        "model_calls": 1433,
        "usage": {},
        "components": [],
        "price_table_sha256": "a" * 64,
        "missing_reasons": [],
    }
    receipt.update(overrides)
    return receipt


def test_a_grade_written_before_the_cost_receipt_is_unknown_not_zero(
    tmp_path, capsys
):
    """Schema 1.3 and earlier carry no receipt, so the cost cannot be stated.

    Rendering that as $0 would be the one wrong answer, because it reads as
    "this cost nothing" rather than "nobody can say what this cost". The
    declared judge models are still worth naming — not as a pricing verdict,
    but so the reader knows which models the silence is about.
    """
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(_payload()))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "UNKNOWN" in printed
    assert "gpt-5.6-sol" in printed
    assert "$0" not in printed


def test_a_priced_run_shows_the_total_from_its_receipt(tmp_path, capsys):
    payload = _payload()
    payload["summary"]["grading_cost"] = _receipt()
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "$412.75" in printed
    assert "UNKNOWN" not in printed


def test_the_pinned_legacy_fields_do_not_hide_a_complete_receipt(
    tmp_path, capsys
):
    """The defect this fixture reproduces.

    `step8_grade` pins `summary.cost.estimated_cost_usd` to null and
    `pricing_complete` to false, and `grade_payload` rejects any payload that
    says otherwise — so a real grade file carries both a frozen "unpriced"
    claim and, beside it, a receipt with an exact figure. Branching on the
    frozen pair told every run ever analysed that its cost was unknown, and
    named models that were priced (or never called) as the reason.
    """
    payload = _payload()
    assert payload["summary"]["cost"]["pricing_complete"] is False
    assert payload["summary"]["cost"]["estimated_cost_usd"] is None
    payload["summary"]["grading_cost"] = _receipt()
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "$412.75" in printed
    assert "not every model used has a published price" not in printed


def test_a_partial_receipt_is_reported_as_a_floor_not_a_total(tmp_path, capsys):
    """One call whose usage never arrived means there is no total to show."""
    payload = _payload()
    payload["summary"]["grading_cost"] = _receipt(
        status="partial",
        estimated_cost_usd=None,
        known_cost_usd=91.5,
        missing_reasons=["usage_absent"],
    )
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "AT LEAST $91.5" in printed
    assert "a floor, not a total" in printed
    assert "usage_absent" in printed


def test_a_partial_receipt_with_a_zero_floor_is_unknown_not_zero(
    tmp_path, capsys
):
    """The 185-task gold corpus is exactly this case.

    Its judge has no published price, so the receipt is incomplete and the
    confirmed total is $0.00 — not because it was free, but because nothing
    in it could be priced. "AT LEAST $0.0" is literally true and reads as
    free, which is the one thing this report must never say.
    """
    payload = _payload()
    payload["summary"]["grading_cost"] = _receipt(
        status="partial",
        estimated_cost_usd=None,
        known_cost_usd=0.0,
        missing_reasons=["price_missing"],
    )
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "UNKNOWN" in printed
    assert "price_missing" in printed
    assert "$0" not in printed


def test_a_run_that_kept_no_priceable_record_is_unknown_not_zero(
    tmp_path, capsys
):
    payload = _payload()
    payload["summary"]["grading_cost"] = _receipt(
        status="unavailable",
        estimated_cost_usd=None,
        known_cost_usd=0.0,
        model_calls=0,
        price_table_sha256=None,
        missing_reasons=["ledger_absent"],
    )
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(payload))

    analysis.main([str(grade_file)])
    printed = capsys.readouterr().out

    assert "UNKNOWN" in printed
    assert "ledger_absent" in printed
    assert "$0" not in printed


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

    assert "high-magnitude item failed in 12 task(s):" in printed
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


# ── Every task gets a row, not just the biggest individual losses ──────────


def test_every_graded_task_gets_a_row():
    """Ranking item losses hides tasks; the specification asks about tasks.

    Stage 1's first run lost its forty largest item scores across nine tasks,
    so a report built from that ranking alone would never mention the other
    twenty-one -- including the ones that scored well, which is the evidence
    that the low scores are not uniform.
    """
    tasks = [
        _task("task-a", pct=100.0, total_awarded=2.0, total_max=2),
        _task("task-b", pct=50.0, total_awarded=1.0, total_max=2),
    ]

    rows = analysis.per_task(_payload(tasks=tasks))

    assert [row["task_id"] for row in rows] == ["task-b", "task-a"]
    assert rows[0]["pct"] == 50.0


def test_a_task_with_no_score_at_all_sorts_first_rather_than_disappearing():
    """A task the grader could not score is the most interesting row there is."""
    tasks = [
        _task("task-ok", pct=80.0, total_awarded=8.0, total_max=10),
        _task("task-broken", pct=None, total_awarded=None, total_max=None),
    ]

    rows = analysis.per_task(_payload(tasks=tasks))

    assert rows[0]["task_id"] == "task-broken"
    assert rows[0]["points_lost"] is None


def test_a_fired_penalty_is_counted_as_lost_points():
    """A negative-maximum item is full marks at zero, so it never reads as low.

    `core/grader.py` keeps penalty items out of the denominator with
    ``max(0, it.max_score)``. An item-wise sum of "maximum minus awarded" over
    items *below their maximum* therefore misses a penalty that fired: -2
    awarded against a -2 maximum is not below it. Reading the loss off the
    task's own totals is what makes the two agree.
    """
    penalty = _item(
        rubric_item_id="penalty",
        criterion="Cites sources behind a paywall.",
        max_score=-2,
        awarded_score=-2.0,
        verdict="pass",
    )
    task = _task(
        "task-penalised",
        items=[_item(max_score=10, awarded_score=10.0), penalty],
        pct=80.0,
        total_awarded=8.0,
        total_max=10,
    )

    row = analysis.per_task(_payload(tasks=[task]))[0]

    assert row["items_below_full_marks"] == 0
    assert row["points_lost"] == 2.0
    assert analysis.items_below_full_marks(_payload(tasks=[task])) == []


def test_an_unfired_penalty_costs_nothing():
    penalty = _item(max_score=-2, awarded_score=-0.0, verdict="fail")
    task = _task(
        "task-clean",
        items=[_item(max_score=10, awarded_score=10.0), penalty],
        pct=100.0,
        total_awarded=10.0,
        total_max=10,
    )

    row = analysis.per_task(_payload(tasks=[task]))[0]

    assert row["items_below_full_marks"] == 0
    assert row["points_lost"] == 0.0


def test_every_task_is_named_in_the_readable_report(tmp_path, capsys):
    """The report's per-task classification is checked against this block."""
    tasks = [
        _task(f"task-{n:02d}", pct=float(n), total_awarded=float(n), total_max=100)
        for n in range(30)
    ]
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(json.dumps(_payload(tasks=tasks)))

    analysis.main([str(grade_file), "--shortfall-limit", "0"])
    printed = capsys.readouterr().out

    assert "Per task (worst first)" in printed
    for task in tasks:
        assert task["task_id"] in printed
    assert max(len(line) for line in printed.splitlines()) < 120


def test_a_long_occupation_does_not_run_off_the_page():
    """Real occupation names reach 41 characters; the line has to hold them."""
    task = _task(
        "task-wide",
        occupation="Computer and Information Systems Managers",
        critical_fail=True,
        selection_status="degraded",
        pct=47.1,
        total_awarded=47.57,
        total_max=101,
    )

    rendered = analysis._render(
        analysis.analyze(_payload(tasks=[task])), shortfall_limit=0
    )

    assert "Computer and Information Systems Managers" in rendered
    assert "selection degraded" in rendered
    assert max(len(line) for line in rendered.splitlines()) < 120


def test_the_two_verdicts_line_up_in_one_column():
    """Two gates decide the stage, so the eye should run down one column.

    The bars are different lengths -- 'needs >= 90.0%' against 'needs < 0.02'
    -- so writing the lines by hand left PASS and MISS stepping across the
    page. This is worth a test because it is the block every reader looks at
    first, and because the padding is computed from the widest row, so another
    gate or a re-worded bar would silently break the alignment again.

    It also pins the count. A PASS/MISS column with three rows in it would mean
    the demoted rate had found its way back into the table.
    """
    rendered = analysis._render(
        analysis.analyze(_payload(tasks=[_task("task-1")])), shortfall_limit=0
    )

    verdicts = [
        line for line in rendered.splitlines() if line.endswith(("  PASS", "  MISS"))
    ]
    assert len(verdicts) == 2, verdicts

    columns = {line.index("(") for line in verdicts}
    assert len(columns) == 1, f"the bars start in different columns: {verdicts}"
    columns = {len(line) for line in verdicts}
    assert len(columns) == 1, f"the verdicts end in different columns: {verdicts}"


def test_a_long_criterion_wraps_instead_of_stopping_mid_word():
    """The criterion and the evidence are other people's prose, at any length.

    The real corpus carries criteria past 300 characters and judge evidence
    past 400. These used to be cut with a bare slice, which both ran off the
    side of the page and stopped mid-word -- one real line ended at
    'for YTD amor'. Wrapping keeps the sentence and keeps the width.
    """
    criterion = (
        "Prepaid Summary totals are linked by formulas to the detailed tabs "
        "(not hard-coded values), directly referencing the 1250 and 1251 "
        "sheets for YTD amortization and April ending balances."
    )
    evidence = "Row header: " + ", ".join(f"Debit Adds {n}" for n in range(40))
    task = _task(
        "task-prose",
        items=[
            _item(
                verdict="fail",
                max_score=2,
                awarded_score=0.0,
                criterion=criterion,
                evidence=evidence,
            )
        ],
    )

    rendered = analysis._render(
        analysis.analyze(_payload(tasks=[task])), shortfall_limit=5
    )

    assert max(len(line) for line in rendered.splitlines()) < 120
    # The sentence survives the wrap: joining the wrapped lines back up
    # reproduces it, so nothing was dropped to make it fit.
    flattened = " ".join(rendered.split())
    assert criterion in flattened
    assert "for YTD amortization and April ending balances." in flattened


def test_prose_too_long_even_to_wrap_is_cut_on_a_word():
    """A budget still applies -- but it ends on a word, not inside one."""
    criterion = " ".join(f"clause{n}" for n in range(200))
    task = _task(
        "task-endless",
        items=[_item(verdict="fail", max_score=2, awarded_score=0.0, criterion=criterion)],
    )

    rendered = analysis._render(
        analysis.analyze(_payload(tasks=[task])), shortfall_limit=5
    )

    assert max(len(line) for line in rendered.splitlines()) < 120
    assert "..." in rendered
    # Cut between words, so no half-word is left behind.
    assert "clause" in rendered
    for line in rendered.splitlines():
        for fragment in line.split():
            if fragment.startswith("clause") and fragment != "clause":
                assert fragment.removeprefix("clause").isdigit(), fragment


def test_newlines_in_evidence_cannot_break_the_width_guarantee():
    """Judge evidence arrives with newlines in it; they must not pass through.

    A raw newline would split one logical line into two that the width check
    never sees as over-long, so the collapse happens before the wrap.
    """
    evidence = "first line\n" + "x" * 300 + "\nlast line"
    task = _task(
        "task-newline",
        items=[_item(verdict="fail", max_score=2, awarded_score=0.0, evidence=evidence)],
    )

    rendered = analysis._render(
        analysis.analyze(_payload(tasks=[task])), shortfall_limit=5
    )

    assert max(len(line) for line in rendered.splitlines()) < 120
    assert "first line" in rendered


# ── What the second threshold is counting ─────────────────────────────────


def test_the_helper_agrees_with_the_grader():
    """The fixture's rule and the grader's rule, over every branch.

    `_model_did_right` restates `core.grader._aggregate`. A restatement can
    drift, and drift here would be invisible: every test in this file would
    still pass, against a payload no run could produce. So the real thing is
    run over the same cases and compared.
    """
    from core.grader import Grader, ItemGrade
    from core.rubric_loader import TaskRubric

    cases = [
        ("pass", 5, False),
        ("partial", 5, False),
        ("fail", 5, False),
        ("pass", -4, False),      # the penalty fired
        ("fail", -4, False),      # the penalty was avoided
        ("judge_error", 5, False),
        ("pass", 5, True),
    ]
    graded = [
        ItemGrade(
            rubric_item_id="i",
            criterion="c",
            max_score=max_score,
            awarded_score=0.0,
            verdict=verdict,
            decided_by="judge",
            required=None,
            evidence="",
            score_excluded=excluded,
        )
        for verdict, max_score, excluded in cases
    ]
    Grader._aggregate(
        graded,
        TaskRubric(
            task_id="t",
            sector="s",
            occupation="o",
            prompt="p",
            rubric_items=[],
            rubric_pretty="",
            reference_files=[],
            gold_deliverable_files=[],
        ),
    )

    for item, (verdict, max_score, excluded) in zip(graded, cases):
        assert item.model_did_right == _model_did_right(
            verdict, max_score, excluded
        ), f"{verdict} at max_score={max_score}, excluded={excluded}"


def test_required_items_counts_what_the_grader_counts():
    """Partial credit is a miss, and a negative maximum still qualifies.

    Both come from `core.grader`: an item is required iff its score magnitude
    reaches ``MAGNITUDE_THRESHOLD``, and it is marked done right on
    ``model_did_right`` -- which for a penalty item is the *opposite* of a
    ``pass`` verdict, because a penalty's verdict answers "did the deliverable
    do this prohibited thing".

    So the ``fail`` on the penalty below is a **pass** for this rate: the
    deliverable avoided the trap. The retired spelling counted it as a miss.
    """
    task = _task(
        "task-1",
        items=[
            _item(criterion="required, passed", max_score=5, verdict="pass"),
            _item(criterion="required, partial", max_score=5, verdict="partial"),
            _item(criterion="required penalty avoided", max_score=-4, verdict="fail"),
            _item(criterion="not required", max_score=3, verdict="partial"),
        ],
    )

    required = analysis.required_items(_payload(tasks=[task]))

    assert required["total"] == 3
    assert required["passed"] == 2
    assert required["rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert required["by_verdict"] == {"pass": 1, "partial": 1, "fail": 1}

    assert required["penalty_items"] == 1
    assert required["penalty_items_fired"] == 0

    # And the retired spelling is reported beside it rather than erased, so a
    # report whose earlier edition quoted the old number can see the move.
    legacy = required["legacy_verdict_pass"]
    assert legacy["passed"] == 1
    assert legacy["rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert legacy["disagreements"] == 1
    assert legacy["disagreeing_items"][0]["criterion"] == "required penalty avoided"


def test_a_fired_penalty_is_a_miss_under_both_counts():
    """The other half of the inversion, so the fix is not one-directional."""
    task = _task(
        "task-1",
        items=[_item(criterion="penalty fired", max_score=-4, verdict="pass")],
    )

    required = analysis.required_items(_payload(tasks=[task]))

    assert required["total"] == 1
    assert required["passed"] == 0
    assert required["penalty_items_fired"] == 1
    # The retired spelling called this a success: `verdict == "pass"`.
    assert required["legacy_verdict_pass"]["passed"] == 1
    assert required["legacy_verdict_pass"]["disagreements"] == 1


def test_an_excluded_item_leaves_the_denominator():
    """`step8_grade.py:1386` counts only `not score_excluded`.

    An excluded item is one the grader declined to score, so leaving it in the
    denominator would put an item there that no deliverable could have moved.
    The count is still reported, because a denominator that silently shrank is
    how a rate improves without anything improving.
    """
    task = _task(
        "task-1",
        items=[
            _item(criterion="scored", max_score=5, verdict="pass"),
            _item(
                criterion="the judge errored",
                max_score=5,
                verdict="judge_error",
                score_excluded=True,
            ),
        ],
    )

    required = analysis.required_items(_payload(tasks=[task]))

    assert required["total"] == 1
    assert required["passed"] == 1
    assert required["rate"] == 1.0
    assert required["score_excluded"] == 1


def test_an_item_with_no_flag_is_counted_and_named():
    """A payload too old to carry the field must not read as total failure.

    The grader defaults a missing flag to False, and this matches it so the
    rate agrees -- but it says how many items it did that to, because a rate
    computed over absent data should not look like a rate computed over data.
    """
    task = _task(
        "task-1",
        items=[_item(max_score=5, verdict="pass", model_did_right=None)],
    )

    required = analysis.required_items(_payload(tasks=[task]))

    assert required["total"] == 1
    assert required["passed"] == 0
    assert required["unscorable"] == 1


def test_a_recount_that_parts_from_the_run_says_so():
    """Two answers to one question is a finding, not something to average.

    The rate the gate is judged on is written by the grader. This tool
    recomputes it from the same items, so agreement is the expected case and
    disagreement means one of them is wrong.
    """
    agreeing = _payload(
        tasks=[_task("task-1", items=[_item(max_score=5, verdict="pass")])],
        summary={
            **_payload()["summary"],
            "wow": {**_payload()["summary"]["wow"], "critical_item_pass_rate": 1.0},
        },
    )
    assert analysis.required_items(agreeing)["agrees_with_payload"] is True

    # The payload claims 0.98; the items say 1.0.
    assert analysis.required_items(
        _payload(tasks=[_task("task-1", items=[_item(max_score=5, verdict="pass")])])
    )["agrees_with_payload"] is False


def test_the_disagreement_reaches_the_readable_report(tmp_path, capsys):
    """A recount that parted from the run cannot be findable only in --json."""
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(
        json.dumps(
            _payload(
                tasks=[
                    _task(
                        "task-1",
                        items=[_item(max_score=5, verdict="pass")],
                        pct=100.0,
                        total_awarded=5.0,
                        total_max=5,
                    )
                ]
            )
        )
    )

    analysis.main([str(grade_file), "--shortfall-limit", "0"])
    printed = capsys.readouterr().out

    assert "recount disagrees with the run's own 0.98" in printed
    assert max(len(line) for line in printed.splitlines()) < 120


def test_the_threshold_is_the_graders_own():
    """A copy of the number could drift from the number that decides."""
    from core.grader import MAGNITUDE_THRESHOLD

    assert analysis.REQUIRED_ITEM_MIN_ABS_SCORE == MAGNITUDE_THRESHOLD


def test_a_criterion_repeated_across_tasks_is_surfaced():
    """One recurring subjective criterion can set the whole rate.

    In stage 1's first run, nineteen of the thirty-five required items were
    "Overall formatting and style of the deliverable" and twelve of them drew
    partial credit -- three quarters of every miss. A rate of 0.5429 does not
    show that; this does.
    """
    shared = "Overall formatting and style of the deliverable"
    tasks = [
        _task(
            f"task-{n}",
            items=[
                _item(criterion=shared, max_score=5, verdict="pass" if n else "partial"),
                _item(criterion=f"unique to task {n}", max_score=5, verdict="pass"),
            ],
        )
        for n in range(3)
    ]

    required = analysis.required_items(_payload(tasks=tasks))

    # Two of the three passed: `n=0` drew partial credit, `n=1` and `n=2`
    # passed. Counted on `model_did_right`, which for these positive items is
    # the same thing the verdict says.
    assert required["recurring_criteria"] == [
        {"criterion": shared, "tasks": 3, "passed": 2}
    ]


def test_the_required_item_block_reaches_the_readable_report(tmp_path, capsys):
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(
        json.dumps(
            _payload(
                tasks=[
                    _task(
                        "task-1",
                        items=[_item(max_score=5, verdict="partial")],
                        pct=50.0,
                        total_awarded=2.5,
                        total_max=5,
                    )
                ]
            )
        )
    )

    analysis.main([str(grade_file), "--shortfall-limit", "0"])
    printed = capsys.readouterr().out

    assert "High-magnitude items (|max score| >= 4)" in printed
    assert "0 of 1 passed" in printed
    # The heading must not go back to calling these items required. The rubric
    # never said they were; `abs(max_score) >= 4` did.
    assert "Required items" not in printed
    assert max(len(line) for line in printed.splitlines()) < 120


def test_a_run_with_no_required_items_does_not_divide_by_zero():
    payload = _payload(tasks=[_task("task-1", items=[_item(max_score=1)])])

    required = analysis.required_items(payload)

    assert required["total"] == 0
    assert required["passed"] == 0
    assert required["rate"] is None
    assert required["by_verdict"] == {}
    assert required["recurring_criteria"] == []
    assert required["penalty_items"] == 0
    assert required["legacy_verdict_pass"]["rate"] is None
    # No rate to compare, so no claim of agreement either.
    assert required["agrees_with_payload"] is False
    analysis._render(analysis.analyze(payload), shortfall_limit=0)


def test_an_empty_denominator_is_not_recorded_rather_than_zero_percent():
    """`0.0` and "nothing was counted" are the same glyph out of `_rate`.

    `step8_grade._rate` returns `0.0` for an empty denominator, and `0.0` is
    also the worst score a real run can earn. 45 of the 447 sector rows in
    `data/grades/` publish exactly `0.0` over a denominator of exactly zero, so
    this is measured behaviour rather than a hypothetical.
    """
    payload = _payload(tasks=[_task("task-1", items=[_item(max_score=1)])])
    # What the producer wrote for a run that counted nothing.
    payload["summary"]["wow"]["critical_item_pass_rate"] = 0.0

    diagnostic = analysis.analyze(payload)["diagnostics"][
        "high_magnitude_item_pass_rate"
    ]

    assert diagnostic["items"] == 0
    assert diagnostic["recorded"] is False
    assert diagnostic["usable"] is False
    assert diagnostic["meets_reference"] is False

    rendered = analysis._render(analysis.analyze(payload), shortfall_limit=0)
    diagnostic_line = next(
        line for line in rendered.splitlines() if "high-magnitude item pass" in line
    )
    assert "not recorded" in diagnostic_line
    # The number the producer wrote must not reach the page as a rate.
    assert "0.0" not in diagnostic_line
    assert "%" not in diagnostic_line


def test_a_denominator_too_small_to_read_says_so_beside_the_rate():
    """One item makes the rate `0.0` or `1.0`, and neither is a measurement.

    123 of the 447 published sector rows sit between 1 and 19 items. The floor
    is derived rather than chosen: under `1 / (1 - 0.95)` items, one failure
    costs more than the entire distance between the reference and a clean
    sweep.
    """
    assert analysis.MIN_USABLE_REQUIRED_ITEMS == 20

    payload = _payload(
        tasks=[_task("task-1", items=[_item(max_score=5, verdict="pass")])]
    )
    payload["summary"]["wow"]["critical_item_pass_rate"] = 1.0

    report = analysis.analyze(payload)
    diagnostic = report["diagnostics"]["high_magnitude_item_pass_rate"]

    assert diagnostic["items"] == 1
    assert diagnostic["recorded"] is True
    assert diagnostic["usable"] is False
    # A perfect 1.0 over one item still clears the retired reference. Saying so
    # and saying it means nothing are both true, and the report prints both.
    assert diagnostic["meets_reference"] is True

    rendered = analysis._render(report, shortfall_limit=0)
    assert "high-magnitude item pass   1.0" in rendered
    assert "1 item(s) is under the 20" in rendered
    assert max(len(line) for line in rendered.splitlines()) < 120


def test_the_diagnostic_carries_its_own_explanation():
    """A reader who starts at this line should not need the paragraph above."""
    rendered = analysis._render(
        analysis.analyze(_payload(tasks=[_task("task-1")])), shortfall_limit=0
    )

    assert "Diagnostics" in rendered
    # Whole, on one line -- a caveat broken across a line wrap is one a reader
    # skimming the value can miss.
    assert f"  {analysis.REQUIRED_ITEM_SUBSTITUTE_NOTE}" in rendered.splitlines()
    assert "no explicit `required` signal" in rendered
    assert "score magnitude stands in for it" in rendered


def test_a_rate_that_cannot_be_compared_is_not_reported_as_a_conflict():
    """"Nothing to compare" and "the two disagree" are different findings.

    `agrees_with_payload` is false in three situations and only one of them is
    a conflict. Printing the conflict wording for the other two would put a
    disagreement in the report that no two numbers ever had -- and in the case
    where the run states no rate at all, would print the word `None` as if it
    were the run's answer.
    """
    # A rate on the payload, nothing here to recount it against.
    no_required = analysis._render(
        analysis.analyze(_payload(tasks=[_task("task-1", items=[_item(max_score=1)])])),
        shortfall_limit=0,
    )
    assert "disagrees" not in no_required
    assert (
        "no high-magnitude items here to recount, so the run's own 0.98"
        in no_required
    )

    # A recount here, no rate on the payload to check it against.
    no_payload_rate = analysis._render(
        analysis.analyze(
            _payload(
                tasks=[_task("task-1", items=[_item(max_score=5, verdict="pass")])],
                summary={**_payload()["summary"], "wow": {}},
            )
        ),
        shortfall_limit=0,
    )
    assert "disagrees" not in no_payload_rate
    assert "the run's own None" not in no_payload_rate
    assert "states no critical-item rate of its own" in no_payload_rate


# ── The breakdowns 304 asks for and the payload does not carry ─────────────


def test_occupations_are_grouped_and_scored():
    """Stage 1 reached 7 occupations of 44; stage 3 reaches all of them.

    A sector average over nine buckets cannot show which of the newly-covered
    occupations moved the ceiling, and the payload carries no occupation
    breakdown at all -- so this computes one.
    """
    tasks = [
        _task("task-1", occupation="Auditor", pct=90.0),
        _task("task-2", occupation="Auditor", pct=70.0),
        _task("task-3", occupation="Film Editor", pct=50.0),
    ]

    grouped = analysis.by_occupation(_payload(tasks=tasks))

    assert set(grouped) == {"Auditor", "Film Editor"}
    assert grouped["Auditor"]["task_count"] == 2
    assert grouped["Auditor"]["avg_pct"] == pytest.approx(80.0)
    assert grouped["Film Editor"]["avg_pct"] == pytest.approx(50.0)


def test_an_unrecorded_occupation_gets_a_bucket_rather_than_vanishing():
    """Dropping it would make the buckets sum to less than the corpus."""
    grouped = analysis.by_occupation(
        _payload(tasks=[_task("task-1", occupation=None, pct=40.0)])
    )

    assert grouped["unrecorded"]["task_count"] == 1


def test_the_mean_is_macro_and_the_required_rate_is_micro():
    """The two headline numbers aggregate differently, and both are recomputed.

    `step8_grade.py` averages per-task percentages for the mean -- every task
    weighs the same -- and pools required items for the rate, so a task with
    four required items pulls four times as hard. A recomputation that picked
    one style for both would be wrong twice, and would be wrong *quietly*: the
    numbers would still look like numbers.
    """
    tasks = [
        _task(
            "task-1",
            pct=100.0,
            items=[_item(max_score=5, verdict="pass") for _ in range(4)],
        ),
        _task(
            "task-2",
            pct=0.0,
            items=[_item(max_score=5, verdict="fail")],
        ),
    ]

    block = analysis.subset_scores(_payload(tasks=tasks), ["task-1", "task-2"])

    # Macro: the two tasks weigh the same.
    assert block["avg_pct"] == pytest.approx(50.0)
    # Micro: four passing items against one failing one.
    assert block["required_items"] == 5
    assert block["required_passed"] == 4
    assert block["critical_item_pass_rate"] == pytest.approx(0.8)


def test_a_task_in_error_is_out_of_the_mean_but_in_the_count():
    """The grader averages over `[t for t in tasks if not t["error"]]`."""
    tasks = [
        _task("task-1", pct=80.0),
        _task("task-2", pct=None, error="judge unreachable"),
    ]

    block = analysis.subset_scores(_payload(tasks=tasks), ["task-1", "task-2"])

    assert block["task_count"] == 2
    assert block["graded_tasks"] == 1
    assert block["error_tasks"] == 1
    assert block["avg_pct"] == pytest.approx(80.0)


def test_the_unclamped_mean_is_reported_beside_the_clamped_one():
    """One task in the 185 carries -380 points against a 50-point maximum.

    `core.grader` floors `pct` at zero and keeps the real value in `pct_raw`.
    Averaging only the clamped value cannot tell a fired penalty from an answer
    that simply scored nothing, and the difference is the whole finding.
    """
    tasks = [
        _task("task-1", pct=100.0, pct_raw=100.0),
        _task("task-2", pct=0.0, pct_raw=-660.0),
    ]

    block = analysis.subset_scores(_payload(tasks=tasks), ["task-1", "task-2"])

    assert block["avg_pct"] == pytest.approx(50.0)
    assert block["avg_pct_raw"] == pytest.approx(-280.0)
    assert block["tasks_clamped_at_zero"] == ["task-2"]


def test_a_subset_can_be_taken_or_left():
    """`304` promises the mean *with and without* the five declared limits."""
    tasks = [
        _task("aaaaaaaa-1111", pct=20.0),
        _task("bbbbbbbb-2222", pct=80.0),
        _task("cccccccc-3333", pct=90.0),
    ]
    payload = _payload(tasks=tasks)

    only = analysis.subset_scores(payload, ["aaaaaaaa"])
    without = analysis.subset_scores(payload, ["aaaaaaaa"], exclude=True)

    assert only["matched"] == ["aaaaaaaa-1111"]
    assert only["avg_pct"] == pytest.approx(20.0)
    assert without["task_count"] == 2
    assert without["avg_pct"] == pytest.approx(85.0)
    assert without["excluded"] is True


def test_a_prefix_matching_nothing_is_named_rather_than_absorbed():
    """A subset that silently shrank would move a mean the report quotes."""
    block = analysis.subset_scores(
        _payload(tasks=[_task("aaaaaaaa-1111", pct=20.0)]), ["zzzzzzzz"]
    )

    assert block["missing"] == ["zzzzzzzz"]
    assert block["matched"] == []
    assert block["avg_pct"] is None


def test_a_prefix_matching_two_tasks_is_refused_rather_than_guessed():
    """The spec names tasks by eight characters; the payload holds UUIDs.

    Eight hex characters over 185 tasks is not obviously collision-free, and a
    prefix that matched two would double-count one of them into a mean.
    """
    payload = _payload(
        tasks=[_task("aaaaaaaa-1111", pct=20.0), _task("aaaaaaaa-2222", pct=90.0)]
    )

    block = analysis.subset_scores(payload, ["aaaaaaaa"])

    assert block["ambiguous"] == ["aaaaaaaa"]
    assert block["matched"] == []


def test_an_ambiguous_prefix_in_an_exclusion_is_not_called_left_out():
    """Refusing to match puts a task on opposite sides of the two subsets.

    "everything but those five" is built by dropping what `matched` holds, and
    an ambiguous prefix never reaches `matched` -- so those tasks stay in the
    mean this line prints. Labelling them "left out" would tell the reader the
    five were taken out when two of them were not.
    """
    payload = _payload(
        tasks=[
            _task("aaaaaaaa-1111", pct=20.0),
            _task("aaaaaaaa-2222", pct=90.0),
            _task("bbbbbbbb-3333", pct=50.0),
        ]
    )

    block = analysis.subset_scores(payload, ["aaaaaaaa"], exclude=True)

    assert block["ambiguous"] == ["aaaaaaaa"]
    assert block["matched"] == []
    # Nothing was taken out, so the mean still spans all three.
    assert block["task_count"] == 3

    rendered = "\n".join(analysis._render_subset("everything but those five", block))
    assert "left in rather than taken out" in rendered
    assert "so left out" not in rendered


def test_the_known_limit_ids_are_eight_characters_of_a_real_task():
    """A typo in the pinned five would silently produce an empty subset.

    The five are quoted from `300-gold-ceiling.md`'s declared input limits, and
    each has to name a task the 185-corpus config actually grades.
    """
    import yaml

    config = yaml.safe_load(
        (
            REPO_ROOT
            / "batch-runner/grading_configs"
            / f"{analysis.STAGE_THREE_CORPUS.config_name}.yaml"
        ).read_text(encoding="utf-8")
    )
    graded = config["rerun_identity"]["task_ids"]

    for prefix in analysis.KNOWN_LIMIT_TASK_IDS:
        hits = [task_id for task_id in graded if task_id.startswith(prefix)]
        assert len(hits) == 1, f"{prefix} matched {len(hits)} of the 185"


# ── The same thirty, compared like for like ────────────────────────────────


def test_the_same_thirty_are_verified_before_they_are_reported():
    """Withheld rather than wrong, if the first thirty are not stage 1's.

    The comparison rests on `step9_merge_shards.py` normalising into canonical
    order. That is an inference, so the thirty ids are hashed and the digest
    has to be stage 1's -- otherwise nothing downstream could tell that the
    "same 30" were a different 30.
    """
    block = analysis.stage_one_subset(
        _payload(tasks=[_task(f"task-{n}", pct=50.0) for n in range(30)])
    )

    assert block["verified"] is False
    assert "not stage 1's corpus" in block["reason"]
    assert "avg_pct" not in block


def test_the_same_thirty_are_scored_when_the_digest_matches():
    """The real thirty, read from stage 1's own config."""
    import yaml

    thirty = yaml.safe_load(
        (
            REPO_ROOT
            / "batch-runner/grading_configs"
            / f"{analysis.STAGE_ONE_CORPUS.config_name}.yaml"
        ).read_text(encoding="utf-8")
    )["rerun_identity"]["task_ids"]

    tasks = [_task(task_id, pct=80.0) for task_id in thirty]
    tasks.append(_task("a-thirty-first-task", pct=10.0))

    block = analysis.stage_one_subset(_payload(tasks=tasks))

    assert block["verified"] is True
    assert block["task_count"] == 30
    # The thirty-first is outside the comparison, so it cannot move it.
    assert block["avg_pct"] == pytest.approx(80.0)
    assert (
        block["ordered_task_ids_sha256"]
        == analysis.STAGE_ONE_CORPUS.ordered_task_ids_sha256
    )


def test_a_payload_too_small_for_the_comparison_says_so():
    block = analysis.stage_one_subset(_payload(tasks=[_task("task-1")]))

    assert block["verified"] is False
    assert "fewer than the 30" in block["reason"]


def test_the_subsets_reach_the_readable_report(tmp_path, capsys):
    grade_file = tmp_path / "grade.json"
    grade_file.write_text(
        json.dumps(
            _payload(
                tasks=[
                    _task(f"task-{n:02d}", pct=float(n), occupation=f"Job {n % 3}")
                    for n in range(30)
                ]
            )
        )
    )

    analysis.main([str(grade_file), "--shortfall-limit", "0"])
    printed = capsys.readouterr().out

    assert "By occupation (3)" in printed
    assert "Subsets" in printed
    assert "the same thirty stage 1 graded" in printed
    assert "the five declared input limits" in printed
    assert "everything but those five" in printed
    # The withheld reason carries two 64-character fingerprints.
    assert "withheld" in printed
    assert max(len(line) for line in printed.splitlines()) < 120
