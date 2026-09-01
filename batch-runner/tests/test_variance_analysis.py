"""What the variance tool must refuse, and what it must not.

Stage 2 asks three questions -- how far a task's score moves across repeats,
how wide the interval on the corpus mean is, and how often the judge failed to
answer -- and all three have the same failure mode: they produce a
comfortable-looking number when the runs being compared were never comparable
in the first place. A duplicated payload reports perfect stability. A run
graded by a different grader reports the difference between graders. Neither
announces itself.

So most of this file is about the refusals. The arithmetic is checked too, but
against hand-built payloads with known answers rather than against the real
run, because a test that recomputes the tool's own output using the tool's own
method proves nothing.
"""

import json
import statistics
import subprocess
from pathlib import Path

import pytest

from scripts import analyze_gold_ceiling as gold
from scripts import analyze_variance as variance


REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/303-variance-and-error.md"


# ── Building payloads the tool will accept ─────────────────────────────────


def _task(task_id: str, pct: float, *, judge_items: int = 2, errors: int = 0):
    items = []
    for index in range(judge_items):
        items.append(
            {
                "item_id": f"{task_id}-{index}",
                "decided_by": "judge",
                "verdict": "judge_error" if index < errors else "pass",
                "awarded_score": 0 if index < errors else 4,
                "max_score": 4,
            }
        )
    return {
        "task_id": task_id,
        "occupation": "Test Occupation",
        "sector": "Test Sector",
        "pct": pct,
        "items": items,
    }


def _payload(scores, *, graded_at, errors_in_first_task=0, **overrides):
    """A payload carrying only what the tool reads, and stage 1's identity.

    ``scores`` is one number per task, so a caller writes the spread it wants
    to test and nothing else.
    """
    tasks = [
        _task(
            f"task-{index:03d}",
            pct,
            errors=errors_in_first_task if index == 0 else 0,
        )
        for index, pct in enumerate(scores)
    ]
    judge_items = sum(len(task["items"]) for task in tasks)
    judge_errors = sum(
        1
        for task in tasks
        for item in task["items"]
        if item["verdict"] == "judge_error"
    )
    payload = {
        "schema_version": "1.3",
        "run_status": "diagnostic",
        "expected_task_count": gold.EXPECTED_TASK_COUNT,
        "expected_ordered_task_ids_sha256": gold.EXPECTED_ORDERED_TASK_IDS_SHA256,
        "grader_source_hash": "c" * 64,
        "graded_at": graded_at,
        "judge": {"model": "gpt-5.6-sol", "config_hash": "d1bfc8217c9981d2"},
        "prompt": {"template": "prompts/grader_judge.md", "version": "v2.2"},
        "rubric": {"revision": "11e7900"},
        "renderer_fingerprint": {
            "libreoffice_version": "LibreOffice 24.2.7.2 420(Build:2)",
            "pymupdf_version": "1.28.2",
        },
        "source_inference_revision": "1" * 40,
        "source_azure_ai_provenance_status": "gold-corpus",
        "azure_ai_routes": [{"runtime_fingerprint": "a" * 64}],
        "tasks": tasks,
        "summary": {
            "graded_tasks": len(tasks),
            "total_tasks": len(tasks),
            "cost": {"total_perception_calls": 0, "pricing_complete": False},
            "wow": {
                "judge_error_rate": variance.canonical_rate(
                    judge_errors, judge_items
                )
            },
        },
    }
    payload.update(overrides)
    return payload


def _write(tmp_path: Path, payload, *, ordinal: int) -> Path:
    if ordinal == 1:
        path = tmp_path / "run.json"
    else:
        path = tmp_path / "_repeats" / f"run-{ordinal:03d}" / "run.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _three_runs(tmp_path, per_run_scores):
    """Write one payload per run and load them back the way the tool does."""
    paths = [
        _write(
            tmp_path,
            _payload(scores, graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z"),
            ordinal=ordinal,
        )
        for ordinal, scores in enumerate(per_run_scores, start=1)
    ]
    return variance.load_runs(paths)


STEADY = [80.0] * gold.EXPECTED_TASK_COUNT


# ── The thresholds are the specification's ─────────────────────────────────


def test_the_thresholds_are_the_ones_the_specification_names():
    """`303-variance-and-error.md` fixes all three; none may drift here."""
    assert variance.TASK_PCT_STDEV_CEILING == 5.0
    assert variance.CI95_WIDTH_CEILING_PCT == 10.0
    assert variance.EXPECTED_RUN_COUNT == 3
    # Taken from stage 1 rather than retyped, so one edit moves both.
    assert variance.JUDGE_ERROR_RATE_CEILING is gold.JUDGE_ERROR_RATE_CEILING


def test_the_specification_points_at_the_report():
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "PR3_VARIANCE.md" in spec


def test_the_tool_is_in_the_repository():
    """``batch-runner/scripts/*`` is ignored by default and needs a line."""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "batch-runner/scripts/analyze_variance.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert tracked.returncode == 0, (
        "analyze_variance.py is not tracked, so a fresh clone would not have "
        "it. Add it to the allow list in .gitignore."
    )


# ── Runs that are not repeats of one another ───────────────────────────────


@pytest.mark.parametrize("description,field", variance.FROZEN_FIELDS)
def test_a_run_that_changed_a_frozen_field_is_refused(
    tmp_path, description, field
):
    """Every frozen field, one at a time, must fail closed.

    Parametrised over the list itself rather than over a hand-written copy, so
    adding a field to ``FROZEN_FIELDS`` adds a test and removing one removes a
    test -- there is no way to list a field and leave it unchecked.
    """
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[2]["payload"][field] = "changed"

    problems = variance.freeze_problems(runs)

    assert any(field in problem for problem in problems), (
        f"{description} ({field}) was listed as frozen but changing it was "
        f"not refused: {problems}"
    )


def test_the_same_payload_twice_is_refused(tmp_path):
    """The failure the whole check exists for: stability measured against self."""
    payload = _payload(STEADY, graded_at="2026-08-28T18:00:00Z")
    first = _write(tmp_path, payload, ordinal=1)
    second = _write(tmp_path, payload, ordinal=2)

    problems = variance.freeze_problems(variance.load_runs([first, second]))

    assert any("passed more than once" in problem for problem in problems)


def test_two_runs_finishing_at_the_same_instant_are_refused(tmp_path):
    """Different bytes, same stamp: still one run wearing two names."""
    stamp = "2026-08-28T18:00:00Z"
    first = _write(tmp_path, _payload(STEADY, graded_at=stamp), ordinal=1)
    second = _write(
        tmp_path,
        _payload([81.0] * gold.EXPECTED_TASK_COUNT, graded_at=stamp),
        ordinal=2,
    )

    problems = variance.freeze_problems(variance.load_runs([first, second]))

    assert any("graded_at" in problem for problem in problems)


def test_a_run_that_graded_a_different_corpus_is_refused(tmp_path):
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[2]["payload"]["tasks"][0]["task_id"] = "some-other-task"

    problems = variance.freeze_problems(runs)

    assert any("different corpus" in problem for problem in problems)


def test_a_shard_is_refused(tmp_path):
    """A shard declares the whole corpus while holding one slice of it."""
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[1]["payload"]["run_status"] = "partial"

    problems = variance.freeze_problems(runs)

    assert any("run_status" in problem for problem in problems)


def test_a_task_missing_a_score_in_one_run_is_refused(tmp_path):
    """The task ids still match, so nothing else would notice.

    A task scored in two runs out of three gets a deviation taken over two
    points while every other task's is taken over three, and the report would
    print them in the same column as if they meant the same thing.
    """
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[1]["payload"]["tasks"][4]["pct"] = None

    problems = variance.freeze_problems(runs)

    assert any("task-004" in problem for problem in problems), problems


def test_three_matching_runs_are_accepted(tmp_path):
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])

    assert variance.freeze_problems(runs) == []


def test_a_different_azure_route_is_reported_and_not_refused(tmp_path):
    """Route drift is expected, so gating on it would reject a good run.

    `step9_merge_shards.py` merges ``azure_ai_routes`` as a union across shards
    precisely because a single run observes more than one grader fingerprint,
    and stage 1's own accepted payload carries two. A check that refused a
    difference here would refuse the run stage 1 accepted.
    """
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[2]["payload"]["azure_ai_routes"] = [{"runtime_fingerprint": "b" * 64}]

    assert variance.freeze_problems(runs) == []

    reported = [row["azure_ai_routes"] for row in variance.usage_by_run(runs)]
    assert ["b" * 64] in reported, "the differing route was not reported at all"


def test_two_payloads_that_are_not_repeats_get_distinguishable_names(tmp_path):
    """Both sit outside ``_repeats/``, so both would read as 'run 1'."""
    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    first.write_text(json.dumps(_payload(STEADY, graded_at="2026-08-28T01:00:00Z")))
    second.write_text(json.dumps(_payload(STEADY, graded_at="2026-08-28T02:00:00Z")))

    labels = [run["label"] for run in variance.load_runs([first, second])]

    assert len(set(labels)) == 2, labels


def test_the_repeat_number_is_read_from_the_path():
    """``run_ordinal`` never reaches the payload, so the directory is it."""
    assert variance.run_label(Path("a/b/c.json")) == "run 1"
    assert variance.run_label(Path("a/_repeats/run-002/c.json")) == "run 2"
    assert variance.run_label(Path("a/_repeats/run-010/c.json")) == "run 10"


# ── How far each task moved ────────────────────────────────────────────────


def test_a_task_that_never_moved_has_no_deviation(tmp_path):
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])

    report = variance.analyze(runs, resamples=200)

    assert report["stability"]["max_stdev_pct"] == 0.0
    assert report["stability"]["identical_across_runs"] == gold.EXPECTED_TASK_COUNT


def test_the_deviation_is_the_sample_form(tmp_path):
    """Three runs are a sample of the grader, not the whole of it.

    The population form would report a spread about 18% narrower on three
    points, which is the wrong direction for a number that has to stay under a
    ceiling.
    """
    runs = _three_runs(
        tmp_path,
        [
            [70.0] + STEADY[1:],
            [80.0] + STEADY[1:],
            [90.0] + STEADY[1:],
        ],
    )

    report = variance.analyze(runs, resamples=200)
    worst = report["stability"]["per_task"][0]

    assert worst["stdev_pct"] == round(statistics.stdev([70.0, 80.0, 90.0]), 4)
    assert worst["stdev_pct"] != round(statistics.pstdev([70.0, 80.0, 90.0]), 4)


def test_one_unstable_task_fails_the_gate_even_when_the_average_is_calm(
    tmp_path,
):
    """The gate is on the worst task, and this is the case that decides it.

    Twenty-nine steady tasks and one that swings thirty points average out to
    well under the ceiling. Averaging would call that stable; the specification
    asks about tasks, so it is a miss.
    """
    runs = _three_runs(
        tmp_path,
        [
            [50.0] + STEADY[1:],
            [80.0] + STEADY[1:],
            [65.0] + STEADY[1:],
        ],
    )

    report = variance.analyze(runs, resamples=200)

    assert report["stability"]["mean_stdev_pct"] < variance.TASK_PCT_STDEV_CEILING
    assert report["stability"]["max_stdev_pct"] > variance.TASK_PCT_STDEV_CEILING
    assert report["gates"]["max_task_pct_stdev"]["met"] is False
    assert report["all_gates_met"] is False
    assert report["stability"]["tasks_over_ceiling"] == ["task-000"]


# ── The interval ───────────────────────────────────────────────────────────


def test_an_unmoving_corpus_has_no_interval(tmp_path):
    """Nothing varies, so nothing can be resampled into a width."""
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])

    report = variance.analyze(runs, resamples=500)

    assert report["confidence_interval"]["tasks_and_runs"]["width_pct"] == 0.0
    assert report["confidence_interval"]["tasks_only"]["width_pct"] == 0.0
    assert report["confidence_interval"]["runs_only"]["width_pct"] == 0.0


def test_the_interval_is_reproducible(tmp_path):
    """The report quotes this output and a test re-derives it byte-for-byte.

    An unseeded interval would fail that comparison every time it was checked,
    so the seed is part of the contract rather than a convenience.
    """
    scores = [float(60 + index) for index in range(gold.EXPECTED_TASK_COUNT)]
    runs = _three_runs(tmp_path, [scores, scores, scores])

    first = variance.analyze(runs, resamples=500, seed=11)
    again = variance.analyze(runs, resamples=500, seed=11)
    other = variance.analyze(runs, resamples=500, seed=12)

    assert (
        first["confidence_interval"]["tasks_and_runs"]
        == again["confidence_interval"]["tasks_and_runs"]
    )
    assert (
        first["confidence_interval"]["tasks_and_runs"]["width_pct"]
        != other["confidence_interval"]["tasks_and_runs"]["width_pct"]
    )


def test_the_two_sources_of_width_are_separable(tmp_path):
    """Which tasks were drawn, and how the grader answered, reported apart.

    Here the runs agree exactly and only the tasks differ, so run-to-run
    resampling has nothing to move and its width must be zero while the
    task-sampling width is not. Without the split, a reader could not tell
    whether a wide interval calls for more runs or for more tasks.
    """
    scores = [float(40 + 2 * index) for index in range(gold.EXPECTED_TASK_COUNT)]
    runs = _three_runs(tmp_path, [scores, scores, scores])

    interval = variance.analyze(runs, resamples=1000)["confidence_interval"]

    assert interval["runs_only"]["width_pct"] == 0.0
    assert interval["tasks_only"]["width_pct"] > 0.0
    assert interval["tasks_and_runs"]["width_pct"] > 0.0


def test_a_wide_corpus_misses_the_width_gate(tmp_path):
    """Scores spread from 0 to 100 cannot pin a mean inside ten points."""
    scores = [
        float(index * 100 / (gold.EXPECTED_TASK_COUNT - 1))
        for index in range(gold.EXPECTED_TASK_COUNT)
    ]
    runs = _three_runs(tmp_path, [scores, scores, scores])

    report = variance.analyze(runs, resamples=2000)

    assert report["gates"]["bootstrap_ci95_width_pct"]["met"] is False


def test_the_percentile_interpolates():
    values = [0.0, 1.0, 2.0, 3.0, 4.0]

    assert variance._percentile(values, 0) == 0.0
    assert variance._percentile(values, 100) == 4.0
    assert variance._percentile(values, 50) == 2.0
    assert variance._percentile(values, 25) == 1.0
    assert variance._percentile(values, 12.5) == 0.5


# ── Judge errors ───────────────────────────────────────────────────────────


def test_the_error_rate_counts_only_items_the_judge_decided(tmp_path):
    """A pre-checked item is not evidence about the judge either way."""
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    for run in runs:
        run["payload"]["tasks"][0]["items"].append(
            {
                "item_id": "prechecked",
                "decided_by": "precheck",
                "verdict": "fail",
                "awarded_score": 0,
                "max_score": 4,
            }
        )

    errors = variance.judge_errors(runs)

    assert errors["per_run"][0]["judge_items"] == 2 * gold.EXPECTED_TASK_COUNT


def test_the_published_rate_is_checked_against_a_recount(tmp_path):
    """A rate that disagrees with its own items is the one nothing else catches."""
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[1]["payload"]["summary"]["wow"]["judge_error_rate"] = 0.0

    runs[1]["payload"]["tasks"][0]["items"][0]["verdict"] = "judge_error"
    errors = variance.judge_errors(runs)

    assert errors["per_run"][1]["agrees_with_payload"] is False
    assert errors["disagreements"] == [runs[1]["label"]]

    report = variance.analyze(runs, resamples=200)
    assert report["gates"]["judge_error_rate"]["met"] is False


def test_too_many_judge_errors_fail_the_gate(tmp_path):
    """Sixty judge items, two errors, is 3.33% -- over the 2% ceiling."""
    paths = []
    for ordinal in range(1, 4):
        payload = _payload(
            STEADY,
            graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z",
            errors_in_first_task=2,
        )
        paths.append(_write(tmp_path, payload, ordinal=ordinal))
    runs = variance.load_runs(paths)

    report = variance.analyze(runs, resamples=200)

    assert report["judge_errors"]["pooled_rate"] == pytest.approx(0.0333, abs=1e-4)
    assert report["gates"]["judge_error_rate"]["met"] is False


def test_the_rate_is_pooled_across_runs(tmp_path):
    runs = _three_runs(tmp_path, [STEADY, STEADY, STEADY])
    runs[0]["payload"]["tasks"][0]["items"][0]["verdict"] = "judge_error"
    runs[0]["payload"]["summary"]["wow"]["judge_error_rate"] = (
        variance.canonical_rate(1, 60)
    )

    errors = variance.judge_errors(runs)

    assert errors["pooled_judge_errors"] == 1
    assert errors["pooled_judge_items"] == 180
    assert errors["pooled_rate"] == variance.canonical_rate(1, 180)


# ── The command line ───────────────────────────────────────────────────────


def test_one_file_is_not_a_comparison(tmp_path):
    path = _write(tmp_path, _payload(STEADY, graded_at="2026-08-28T01:00:00Z"), ordinal=1)

    with pytest.raises(SystemExit) as exited:
        variance.main([str(path)])

    assert exited.value.code == 2


def test_two_runs_report_but_do_not_pass(tmp_path, capsys):
    """The specification says three, so two is a partial answer."""
    paths = [
        _write(
            tmp_path,
            _payload(STEADY, graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z"),
            ordinal=ordinal,
        )
        for ordinal in (1, 2)
    ]

    assert variance.main([str(path) for path in paths]) == 1

    printed = capsys.readouterr().out
    assert "runs compared" in printed
    assert "MISS" in printed


def test_three_steady_runs_exit_zero(tmp_path, capsys):
    paths = [
        _write(
            tmp_path,
            _payload(STEADY, graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z"),
            ordinal=ordinal,
        )
        for ordinal in (1, 2, 3)
    ]

    assert variance.main([str(path) for path in paths] + ["--bootstrap-resamples", "200"]) == 0

    assert "MISS" not in capsys.readouterr().out


def test_the_json_output_carries_every_task(tmp_path, capsys):
    paths = [
        _write(
            tmp_path,
            _payload(STEADY, graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z"),
            ordinal=ordinal,
        )
        for ordinal in (1, 2, 3)
    ]

    variance.main(
        [str(path) for path in paths] + ["--json", "--bootstrap-resamples", "200"]
    )

    report = json.loads(capsys.readouterr().out)
    assert len(report["stability"]["per_task"]) == gold.EXPECTED_TASK_COUNT


def test_an_unpriced_run_is_never_rendered_as_free(tmp_path, capsys):
    """Unknown is not zero, and the roadmap forbids writing it as zero."""
    paths = [
        _write(
            tmp_path,
            _payload(STEADY, graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z"),
            ordinal=ordinal,
        )
        for ordinal in (1, 2, 3)
    ]

    variance.main([str(path) for path in paths] + ["--bootstrap-resamples", "200"])

    printed = capsys.readouterr().out
    assert "UNKNOWN" in printed
    assert "$0" not in printed


def test_each_run_shows_the_total_from_its_own_receipt(tmp_path, capsys):
    """What the comparison is for: the same fingerprint billed three times.

    `summary.cost.pricing_complete` is pinned false by contract, so branching
    on it printed UNKNOWN for every run and hid the one number a variance
    report over repeated runs exists to compare.
    """
    paths = []
    for ordinal in (1, 2, 3):
        payload = _payload(
            STEADY, graded_at=f"2026-08-2{ordinal}T0{ordinal}:00:00Z"
        )
        payload["summary"]["grading_cost"] = {
            "status": "complete",
            "estimated_cost_usd": 40.0 + ordinal,
            "known_cost_usd": 40.0 + ordinal,
            "model_calls": 700,
            "missing_reasons": [],
            "price_table_sha256": "a" * 64,
        }
        paths.append(_write(tmp_path, payload, ordinal=ordinal))

    variance.main([str(path) for path in paths] + ["--bootstrap-resamples", "200"])

    printed = capsys.readouterr().out
    assert "$41.0" in printed
    assert "$42.0" in printed
    assert "$43.0" in printed
    assert "UNKNOWN" not in printed
