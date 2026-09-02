"""Stage 3 measures the grader against itself, so its guards are the evidence.

Stage 2 asked how far a score moves when the same thirty answers are graded
three times. It answered with one number for the whole corpus, and that number
was reassuring. Stage 3 asks the question the corpus number hides: how often
does an individual rubric item come back with a different verdict? Those two
answers point in opposite directions, and both are true.

Because the second answer is a disagreement rate rather than a mean, almost
every way of getting it wrong makes it look better. Comparing a run with itself
reports no disagreement at all. Resampling items instead of tasks reports a
narrower interval than the data supports. Dropping the items the grader failed
on tidies the denominator and moves the mean. So this file spends most of its
length on the refusals rather than the arithmetic: every mutation in section 12
of the preregistration is applied here and has to make the tool stop.

The rest holds the tool to the preregistration's own figures. Those were
written before the tool existed, from a separate reading of the same payloads,
which is what makes them worth checking against.
"""

import ast
import hashlib
import json
from pathlib import Path

import pytest

from scripts import analyze_gold_ceiling as gold
from scripts import analyze_repeat_variation as rv


REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTIC_ROOT = REPO_ROOT / "data/grades/_diagnostic"
PREREG_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/315-repeat-variation-prereg.md"

# The task-list digest is the cohort's name. Read out of the tool's own pin so
# that repointing the analysis at another cohort cannot leave these tests
# quietly measuring the old one.
PINNED_TASK_LIST_DIGEST = next(
    value
    for _, path, value in rv.PINNED_FINGERPRINTS
    if path == ("expected_ordered_task_ids_sha256",)
)


def _repeat_grade_files() -> list[Path]:
    """The three finished runs of the pinned cohort, in repeat order.

    ``_superseded/`` is excluded because it holds a run graded by a reading
    tool that has since been fixed; comparing it to the current three would
    measure a code change, which is the one thing this analysis holds still.
    Shards are excluded by ``run_status`` -- a shard declares the whole corpus
    in its identity fields while holding one slice of it.

    ``--run-ordinal`` forks the output path above the shard fork, so run 1 sits
    at the canonical path and every later repeat lands under
    ``_repeats/run-NNN/``. Nothing inside a payload records which repeat it is,
    so the path is the only thing that orders them.
    """
    found: list[tuple[int, Path]] = []
    for path in sorted(DIAGNOSTIC_ROOT.rglob("*.json")):
        if "_superseded" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("expected_ordered_task_ids_sha256")
            != PINNED_TASK_LIST_DIGEST
            or payload.get("run_status") not in gold.COMPLETE_RUN_STATUSES
        ):
            continue
        ordinal = 1
        for part in path.parts:
            if part.startswith("run-") and part[4:].isdigit():
                ordinal = int(part[4:])
        found.append((ordinal, path))
    return [path for _, path in sorted(found)]


@pytest.fixture(scope="module")
def grade_files() -> list[Path]:
    files = _repeat_grade_files()
    assert len(files) == rv.EXPECTED_RUN_COUNT, (
        f"this analysis compares {rv.EXPECTED_RUN_COUNT} runs of the pinned "
        f"cohort and the repository holds {len(files)}: "
        f"{[str(path.relative_to(REPO_ROOT)) for path in files]}"
    )
    return files


@pytest.fixture
def runs(grade_files) -> list[dict]:
    """Reloaded per test, because the mutation tests edit what they are given.

    Reading all three costs about a tenth of a second, which is cheaper than
    deep-copying them.
    """
    return rv.load_runs(list(grade_files))


@pytest.fixture(scope="module")
def report(grade_files) -> dict:
    """One analysis at the registered settings, shared by the reading tests.

    Ten thousand resamples of six bootstraps takes about twenty seconds, so it
    is done once. Nothing below mutates it.
    """
    loaded = rv.load_runs(list(grade_files))
    return rv.analyze(
        loaded,
        resamples=rv.BOOTSTRAP_RESAMPLES,
        seed=rv.BOOTSTRAP_SEED,
        resample_unit="task",
    )


# -- the inputs really are one run, repeated -------------------------------


def test_the_three_runs_pass_every_guard(runs):
    assert rv.fingerprint_problems(runs) == []
    assert rv.shape_problems(runs) == []


@pytest.mark.parametrize(
    "label,path,expected",
    rv.PINNED_FINGERPRINTS,
    ids=[label.replace(" ", "-") for label, _, _ in rv.PINNED_FINGERPRINTS],
)
def test_every_pinned_fingerprint_is_the_registered_value(
    label, path, expected, runs
):
    """Agreement between the runs is not enough on its own.

    Three runs of a different cohort agree with each other perfectly. The
    literal match is what ties these files to the document that registered the
    analysis, so it is checked field by field rather than in bulk.
    """
    observed = [rv._dig(run, path) for run in runs]

    assert observed == [expected] * rv.EXPECTED_RUN_COUNT, label


def test_the_pinned_list_covers_the_twelve_the_document_names(runs):
    """Section 4 names twelve. Pinning fewer would be a quieter analysis."""
    assert len(rv.PINNED_FINGERPRINTS) >= 12
    fields = {".".join(path) for _, path, _ in rv.PINNED_FINGERPRINTS}
    for required in (
        "expected_ordered_task_ids_sha256",
        "grader_source_hash",
        "judge.config_name",
        "judge.model",
        "judge.reasoning_effort",
        "judge.temperature",
        "judge.seed",
        "prompt.version",
        "rubric.revision",
        "renderer_fingerprint",
        "source_inference_revision",
        "schema_version",
    ):
        assert required in fields, required


def test_the_route_record_is_reported_but_not_frozen(runs):
    """The one field stage 3 deliberately left out of the freeze.

    A run's Azure route list is a union across shards, so it is not stable
    within a single run, let alone across three. Freezing it would make the
    accepted stage-1 run reject itself. It is reported instead.
    """
    fields = {".".join(path) for _, path, _ in rv.PINNED_FINGERPRINTS}

    assert "azure_ai_routes" not in fields


def test_the_schema_pin_is_the_version_these_files_carry(runs):
    """Pinned at 1.3, not at whatever the producer writes today.

    ``step8_grade.py`` has since moved to 1.4. Pinning the current value would
    make these three payloads fail their own analysis.
    """
    assert all(run["schema_version"] == "1.3" for run in runs)


# -- section 12, the six mutations, each of which must stop the tool --------


def test_mutation_a_tampered_fingerprint_is_refused(runs):
    runs[1]["judge"]["config_hash"] = "0000000000000000"

    problems = rv.fingerprint_problems(runs)

    assert problems, "a moved grading config hash was not noticed"
    assert any("config_hash" in problem for problem in problems)


def test_mutation_b_the_same_file_twice_is_refused(grade_files):
    """The failure that would pass every gate having measured nothing."""
    doubled = rv.load_runs([grade_files[0], grade_files[0], grade_files[1]])

    problems = rv.fingerprint_problems(doubled)

    assert problems, "being handed one run twice was not noticed"
    assert any("the same run" in problem for problem in problems)


def test_mutation_c_a_forged_verdict_value_is_refused(runs):
    item = runs[2]["tasks"][0]["items"][0]
    item["verdict"] = "mostly_pass"

    problems = rv.shape_problems(runs)

    assert problems, "a verdict outside the vocabulary was not noticed"
    assert any("mostly_pass" in problem for problem in problems)


def test_mutation_d_resampling_items_is_marked_unregistered(runs):
    """Item resampling still produces a number. It is not the official one."""
    swapped = rv.analyze(
        runs,
        resamples=rv.BOOTSTRAP_RESAMPLES,
        seed=rv.BOOTSTRAP_SEED,
        resample_unit="item",
    )

    assert swapped["settings"]["as_registered"] is False
    assert swapped["verdict_ok"] is False


def test_mutation_e_a_different_seed_is_marked_unregistered(runs):
    moved = rv.analyze(
        runs,
        resamples=rv.BOOTSTRAP_RESAMPLES,
        seed=rv.BOOTSTRAP_SEED + 1,
        resample_unit="task",
    )

    assert moved["settings"]["as_registered"] is False
    assert moved["verdict_ok"] is False
    assert moved["settings"]["seed"] != rv.BOOTSTRAP_SEED


def test_mutation_f_an_injected_audio_item_is_refused(runs):
    runs[0]["tasks"][0]["items"][0]["routing_modality"] = "audio"

    problems = rv.shape_problems(runs)

    assert problems, "an audio item was not noticed"
    assert any("audio" in problem for problem in problems)


def test_a_mutation_reaches_the_exit_code_through_the_real_entry_point(
    grade_files, capsys
):
    """Two mutations driven end to end, so the refusals are not test-only.

    A settings mutation reaches the caller as an exit code and a payload
    mutation reaches it as an exception, and both paths are worth walking. An
    unregistered resample count is the cheapest settings mutation to run: it
    needs no bootstrap worth the name to prove the point.
    """
    argv = [str(path) for path in grade_files] + [
        "--bootstrap-resamples",
        "50",
        "--json",
    ]

    assert rv.main(argv) == 1

    emitted = json.loads(capsys.readouterr().out)
    assert emitted["settings"]["resamples"] == 50
    assert emitted["settings"]["as_registered"] is False

    with pytest.raises(rv.RepeatsAreNotComparable):
        rv.main([str(grade_files[0])] * rv.EXPECTED_RUN_COUNT)


# -- the negative control ---------------------------------------------------


def test_comparing_a_run_with_itself_reports_perfect_agreement(grade_files):
    """The control that shows what a broken input would have published.

    Three copies of one file produce a flawless result: no verdict ever moves,
    no score ever moves, the corpus mean does not budge and every interval is
    zero wide. It clears the preregistered target by the widest possible
    margin. That is precisely why the same-file check has to run before the
    numbers, and the second half of this test is that check firing.
    """
    same = rv.load_runs([grade_files[0]] * rv.EXPECTED_RUN_COUNT)
    control = rv.analyze(
        same,
        resamples=200,
        seed=rv.BOOTSTRAP_SEED,
        resample_unit="task",
    )

    assert control["flips"]["verdict"]["differing"] == 0
    assert control["flips"]["score_outcome"]["differing"] == 0
    assert control["flips"]["transitions"] == {}
    assert control["corpus_common_denominator"]["mean_spread_pp"] == 0.0
    assert control["corpus_as_published"]["mean_spread_pp"] == 0.0
    assert control["worst_half_width_pp"] == 0.0
    assert control["target_half_width_met"] is True

    problems = rv.fingerprint_problems(same)
    assert any("the same run" in problem for problem in problems), (
        "the control produced a perfect result and nothing stopped it being "
        "published"
    )


def test_a_degenerate_rate_is_reported_rather_than_crashing():
    """A grader that never disagreed with itself is a legitimate observation.

    The bracket is exact binomial arithmetic and ``log(0)`` raises, so both
    ends of the range are answered without the sum. Without this the control
    above dies inside a helper instead of returning the perfect result it
    exists to expose.
    """
    agree = rv.naive_endpoint_bracket([0] * 100)
    differ = rv.naive_endpoint_bracket([1] * 100)

    assert agree["bracketing_counts"] == [
        {"count": 0, "rate_pct": 0.0, "cdf": 1.0}
    ]
    assert differ["bracketing_counts"] == [
        {"count": 100, "rate_pct": 100.0, "cdf": 1.0}
    ]


# -- the preregistration's own figures --------------------------------------


def test_the_denominator_moved_and_is_reported_rather_than_absorbed(report):
    """Section 5. Three items leave the corpus total, not just the score."""
    denominator = report["denominator"]

    assert denominator["shared_items"] == 1433
    assert denominator["items_in_common_denominator"] == 1430
    assert denominator["items_dropped_from_common_denominator"] == 3

    moved = {
        entry["task_id"]: entry["total_max"]
        for entry in denominator["tasks_whose_total_max_moved"]
    }
    assert moved == {
        "43dc9778-450b-4b46-b77e-b6d82b202035": [121, 121, 119],
        "a328feea-47db-4856-b4be-2bdc63dd88fb": [22, 24, 24],
        "17111c03-aac7-45c2-857d-c06d8223d6ad": [60, 61, 60],
    }


def test_a_grader_failure_raises_the_score_it_was_counted_out_of(report, runs):
    """The concrete reason the two baselines are kept apart.

    Task ``a328feea`` scores the same 18.6 points in run 1 and run 2. Run 1
    lost an item to a grader failure, so it is counted out of 22 rather than
    24, and the run that failed comes out seven points ahead.
    """
    task_id = "a328feea-47db-4856-b4be-2bdc63dd88fb"
    scored = [
        next(task for task in run["tasks"] if task["task_id"] == task_id)
        for run in runs
    ]

    assert scored[0]["total_awarded"] == scored[1]["total_awarded"]
    assert scored[0]["total_max"] < scored[1]["total_max"]
    assert scored[0]["pct"] > scored[1]["pct"]


def test_judge_error_and_score_excluded_are_the_same_events(report):
    denominator = report["denominator"]

    assert denominator["judge_error_events"] == 4
    assert denominator["score_excluded_events"] == 4
    assert denominator["excluded_and_error_disagree"] == 0


def test_the_two_disagreement_rates_match_the_preregistration(report):
    """Section 6. Verdict and score are separate metrics on purpose."""
    flips = report["flips"]

    assert flips["compared_items"] == 1433
    assert flips["compared_item_pairs"] == 4299

    assert flips["verdict"]["differing"] == 204
    assert flips["verdict"]["per_pair"] == [66, 65, 73]
    assert flips["verdict"]["rate_pct"] == pytest.approx(4.7453, abs=5e-5)

    assert flips["score_outcome"]["differing"] == 450
    assert flips["score_outcome"]["per_pair"] == [153, 144, 153]
    assert flips["score_outcome"]["rate_pct"] == pytest.approx(10.4676, abs=5e-5)


def test_the_verdict_rate_alone_would_miss_246_moved_scores(report):
    """Why both metrics exist rather than one.

    A ``partial`` that drops from 2.0 to 1.5 is still a ``partial``. Counting
    verdicts alone hides it; counting scores alone hides the sentence a reader
    would have quoted.
    """
    flips = report["flips"]

    assert flips["same_verdict_moved_score"] == 246
    assert flips["adjacent_moves"] == 175
    assert flips["two_step_moves"] == 23
    assert (
        flips["adjacent_moves"] + flips["two_step_moves"]
        < flips["verdict"]["differing"]
    ), "every verdict move should be adjacent, two-step, or error-involved"


def test_the_moves_go_both_ways_which_is_why_the_mean_holds_still(report):
    """The reconciliation between the two headline answers.

    Upward and downward moves nearly cancel, so a corpus mean can be steady
    while one item in twenty comes back differently.
    """
    transitions = report["flips"]["transitions"]
    rank = rv.VERDICT_RANK

    upward = sum(
        count
        for move, count in transitions.items()
        for before, after in [move.split("->")]
        if before in rank and after in rank and rank[after] > rank[before]
    )
    downward = sum(
        count
        for move, count in transitions.items()
        for before, after in [move.split("->")]
        if before in rank and after in rank and rank[after] < rank[before]
    )
    involving_error = sum(
        count
        for move, count in transitions.items()
        if "judge_error" in move
    )

    assert upward == 107
    assert downward == 91
    assert involving_error == 6
    assert upward + downward + involving_error == report["flips"]["verdict"][
        "differing"
    ]


def test_the_official_interval_is_the_task_cluster_one(report):
    """Section 7. Four decimal places, because the document has four."""
    assert report["settings"]["resample_unit"] == "task"
    ci = report["flips"]["verdict"]["ci"]

    assert ci["low"] == pytest.approx(3.821, abs=5e-4)
    assert ci["high"] == pytest.approx(5.745, abs=5e-4)
    assert ci["width"] == pytest.approx(1.924, abs=5e-4)
    assert report["design_effect"]["cluster_ci"] == ci


def test_the_item_interval_is_reported_and_labelled_as_not_used(report):
    """Items inside one task move together, so treating them as independent
    reports a precision the data does not have."""
    design = report["design_effect"]

    assert design["naive_item_ci"]["width"] < design["cluster_ci"]["width"]
    assert design["width_ratio"] == pytest.approx(1.5037, abs=5e-4)


def test_the_documents_naive_endpoint_and_this_ones_differ_by_one_item(report):
    """Exact arithmetic, so it is checked without running a bootstrap.

    The document recorded 4.094 and every implementation here returns 4.117.
    Both are honest: under item resampling the statistic can only land on
    multiples of one item in 4,299, and the true 2.5th percentile falls
    between two counts no draw can return.
    """
    bracket = report["design_effect"]["naive_endpoint_bracket"]
    low, high = bracket["bracketing_counts"]

    assert bracket["trials"] == 4299
    assert bracket["observed"] == 204
    assert (low["count"], high["count"]) == (176, 177)
    assert low["rate_pct"] == pytest.approx(4.094, abs=5e-4)
    assert high["rate_pct"] == pytest.approx(4.117, abs=5e-4)
    assert low["cdf"] < 0.025 < high["cdf"]
    assert high["count"] - low["count"] == 1
    assert bracket["step_pct"] == pytest.approx(0.0233, abs=5e-5)
    assert report["design_effect"]["naive_item_ci"]["low"] == pytest.approx(
        high["rate_pct"], abs=1e-9
    )


def test_the_binomial_bracket_is_reproducible_arithmetic():
    """Directly, on the same numbers, with no payload and no resampling."""
    assert rv._binomial_cdf(4299, 176, 204 / 4299) == pytest.approx(
        0.02241, abs=5e-6
    )
    assert rv._binomial_cdf(4299, 177, 204 / 4299) == pytest.approx(
        0.02672, abs=5e-6
    )


def test_the_percentile_helper_interpolates(report):
    values = [float(index) for index in range(101)]

    assert rv.percentile(values, 50.0) == pytest.approx(50.0)
    assert rv.percentile(values, 2.5) == pytest.approx(2.5)
    assert rv.percentile(values, 97.5) == pytest.approx(97.5)
    assert rv.percentile([7.0], 2.5) == 7.0


# -- the corpus answer and the preregistered target -------------------------


def test_the_corpus_means_and_their_spread(report):
    published = [
        entry["mean_pct"] for entry in report["corpus_as_published"]["per_run"]
    ]
    common = [
        entry["mean_pct"]
        for entry in report["corpus_common_denominator"]["per_run"]
    ]

    assert published == pytest.approx([82.8733, 83.0727, 83.2457], abs=5e-5)
    assert common == pytest.approx([83.1275, 83.6129, 83.5383], abs=5e-5)
    assert report["corpus_as_published"]["mean_spread_pp"] == pytest.approx(
        0.3723, abs=5e-5
    )


def test_no_mean_shift_is_distinguishable_from_chance(report):
    """The drift is visible and it is not significant. Both get said.

    Six pairs across two baselines, and every interval contains zero.
    """
    intervals = [
        pair["corpus_mean_shift_ci"]
        for basis in ("difference_common_denominator", "difference_as_published")
        for pair in report[basis]["per_pair"]
    ]

    assert len(intervals) == 6
    for interval in intervals:
        assert interval["low"] <= 0.0 <= interval["high"], interval


def test_the_target_is_judged_on_the_worse_of_the_two_baselines(report):
    """Section 8. The published basis is the wider one, so it is the gate."""
    common = report["difference_common_denominator"]["worst_half_width_pp"]
    published = report["difference_as_published"]["worst_half_width_pp"]

    assert report["worst_half_width_pp"] == max(common, published)
    assert report["worst_half_width_pp"] == pytest.approx(0.8894, abs=5e-5)
    assert report["worst_half_width_pp"] <= rv.HALF_WIDTH_TARGET_PP
    assert report["target_half_width_met"] is True
    assert report["verdict_ok"] is True


def test_the_target_leaves_room_against_the_ninety_percent_line(report):
    """Why 1.0pp is the target and not a round number picked to be passed.

    The corpus sits about seven points below ninety. A repeat-grading wobble
    of a point cannot move that judgement.
    """
    lowest = min(
        entry["mean_pct"] for entry in report["corpus_as_published"]["per_run"]
    )

    assert 90.0 - lowest > 7.0
    assert rv.HALF_WIDTH_TARGET_PP < (90.0 - lowest) / 7.0


def test_no_further_paid_run_is_required(report):
    """Section 13. The free analysis met the target, so nothing is dispatched."""
    extra = report["extra_runs"]

    assert extra["runs_required_for_target"] == rv.EXPECTED_RUN_COUNT
    assert extra["runs_held"] == rv.EXPECTED_RUN_COUNT
    assert extra["runs_required_for_target"] <= extra["runs_held"]
    assert extra["worst_pair_difference_stdev_pp"] == pytest.approx(
        2.1448, abs=5e-5
    )


# -- section 9, where absence is recorded as absence ------------------------


def test_this_cohort_contains_no_audio(report):
    """Audio flipping was measured elsewhere and must not be folded in here."""
    assert rv.FORBIDDEN_MODALITY not in report["vocabulary"]["routing_modality"]


def test_what_was_not_measured_says_so_rather_than_reporting_zero(report):
    """A rate of zero and a field that does not exist are different claims."""
    vocabulary = report["vocabulary"]

    assert "not measured" in vocabulary["refusal"]
    assert "no field exists" in vocabulary["tool_failure"]
    # And the census is not offered in its place. It was, and the next test is
    # why it is not any more.
    assert "is not one" in vocabulary["tool_failure"]


def test_the_judge_error_rate_is_reported_as_the_small_number_it_is(report):
    vocabulary = report["vocabulary"]

    assert vocabulary["judge_error_rate_pct"] == pytest.approx(0.0930, abs=5e-5)
    assert vocabulary["verdicts"]["judge_error"] == 4
    assert set(vocabulary["verdicts"]) == set(rv.VERDICT_VOCABULARY)
    assert vocabulary["selection_status"] == {"ok": 4299}
    assert all(entry["error_tasks"] == 0 for entry in vocabulary["error_tasks"])


def test_items_decided_without_reading_the_deliverable_are_surfaced(report):
    """Ninety-two items were judged on zero reads. Reported, not explained.

    The keys are read counts, so they are integers here. They become strings
    the moment the report is written as JSON, which is why the census is read
    off the object rather than off the file.
    """
    census = report["vocabulary"]["read_deliverable_calls"]

    assert census[0] == 92
    assert sum(census.values()) == 4299
    assert max(census) == 6


def test_the_zero_read_items_all_opened_the_file_as_a_picture(report):
    """The 92 are not a tool failure, and this is the measurement that says so.

    The report used to leave them as a candidate, on the plain reading that a
    verdict reached without calling ``read_deliverable`` is a verdict reached
    without opening the deliverable. Every one of them opened it. They are
    routed to pictures, so they render the file and look at the rendering, and
    ``read_deliverable`` is not the tool for that.

    The direction that settles it is the one below the split: 92 of the 231
    visual items never call it, and not one of the 3,858 text items is in the
    bucket at all. A tool failure would not sort itself by routing.
    """
    vocabulary = report["vocabulary"]
    never = vocabulary["never_read"]

    assert never["items"] == vocabulary["read_deliverable_calls"][0]
    assert never["rendered_and_looked"] == 92
    assert never["other_tools_only"] == 0
    assert never["no_tool_at_all"] == 0
    assert never["by_modality"] == {"visual": 92}
    assert vocabulary["routing_modality"]["visual"] == 231
    assert vocabulary["routing_modality"]["text"] == 3858


def test_an_item_that_reached_the_file_no_way_at_all_is_told_apart(runs):
    """The negative control, because the split above is worth nothing without
    it.

    A bucket that reported everything as ``rendered_and_looked`` would produce
    exactly the figures the previous test asserts, and would be wrong the first
    time an item genuinely failed to reach its deliverable. So one item is
    stripped of its perception and its tools, and it has to move.
    """
    before = rv.observed_vocabulary(runs)
    stripped = next(
        item
        for task in runs[0]["tasks"]
        for item in task["items"]
        if "read_deliverable" not in (item.get("tools_used") or [])
    )
    stripped["perception_called"] = False
    stripped["tools_used"] = []

    after = rv.observed_vocabulary(runs)

    assert before["never_read"]["rendered_and_looked"] == 92
    assert after["never_read"]["items"] == before["never_read"]["items"]
    assert after["never_read"]["rendered_and_looked"] == 91
    assert after["never_read"]["no_tool_at_all"] == 1


def test_the_money_column_stays_unregistered_and_never_zero(report):
    """A run nobody could price is not a run that cost nothing."""
    for entry in report["usage"]:
        cost = entry["estimated_cost_usd"]
        assert cost.startswith("unregistered")
        assert "gpt-5.6-sol" in cost
        assert "0.00" not in cost


# -- what this analysis is not allowed to disturb ---------------------------


def test_the_analysis_does_not_modify_the_payloads_it_reads(grade_files):
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in grade_files]

    loaded = rv.load_runs(list(grade_files))
    rv.analyze(loaded, resamples=50, seed=rv.BOOTSTRAP_SEED, resample_unit="task")

    after = [hashlib.sha256(path.read_bytes()).hexdigest() for path in grade_files]
    assert before == after


def test_this_tool_shares_no_code_with_the_stage_two_tool():
    """Stage 2's published numbers must not move because stage 3 was written.

    ``analyze_variance.py`` produced figures that are already quoted in a
    merged report. Importing from it would put those figures one refactor away
    from this file.

    Checked against the import graph rather than the text, because the tool
    discusses the stage-2 tool at length in its own docstrings and a substring
    search cannot tell an explanation from a dependency.
    """
    source = (
        REPO_ROOT / "batch-runner/scripts/analyze_repeat_variation.py"
    ).read_text(encoding="utf-8")

    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(
                f"{node.module or ''}.{alias.name}" for alias in node.names
            )

    assert not any("analyze_variance" in name for name in imported), sorted(
        name for name in imported if "analyze_variance" in name
    )


def test_the_preregistration_is_present_and_names_this_tool():
    """The document was written first. It is what these numbers answer to."""
    assert PREREG_PATH.is_file()
    text = PREREG_PATH.read_text(encoding="utf-8")

    assert "analyze_repeat_variation.py" in text


def test_the_bootstraps_do_not_share_a_random_stream(runs):
    """Each interval has to be the same whether or not others were computed.

    A single shared generator would make an interval depend on how many
    bootstraps ran before it, and the report's byte-for-byte check would then
    be pinning an ordering rather than a result.
    """
    flips = rv.disagreement(runs)
    task_ids = rv._document_order(runs[0])

    first = rv.cluster_bootstrap_ratio(
        task_ids,
        flips["verdict"]["by_task"],
        flips["pairs_by_task"],
        resamples=300,
        seed=rv.BOOTSTRAP_SEED,
    )
    rv.cluster_bootstrap_ratio(
        task_ids,
        flips["score_outcome"]["by_task"],
        flips["pairs_by_task"],
        resamples=300,
        seed=rv.BOOTSTRAP_SEED,
    )
    again = rv.cluster_bootstrap_ratio(
        task_ids,
        flips["verdict"]["by_task"],
        flips["pairs_by_task"],
        resamples=300,
        seed=rv.BOOTSTRAP_SEED,
    )

    assert first == again


def test_the_resampling_order_is_the_payloads_order_not_sorted(runs):
    """Sorting would move the endpoints for no reason, so it is not done."""
    order = rv._document_order(runs[0])

    assert len(order) == rv.EXPECTED_TASK_COUNT
    assert order != sorted(order)
    assert order == [task["task_id"] for task in runs[0]["tasks"]]


def test_a_missing_task_score_stops_the_run_rather_than_being_dropped(runs):
    """Dropping it would move the mean towards the tasks that survived."""
    runs[1]["tasks"][3]["pct"] = None

    problems = rv.fingerprint_problems(runs)

    assert any("no score" in problem for problem in problems)


def test_an_item_missing_from_one_run_cannot_be_paired(runs):
    dropped = runs[2]["tasks"][0]["items"].pop()

    problems = rv.shape_problems(runs)

    assert problems, f"a run short of item {dropped['rubric_item_id']} passed"
    assert any("cannot be paired" in problem for problem in problems)


def test_a_run_of_the_wrong_size_is_refused(runs):
    problems = rv.fingerprint_problems(runs[:2])

    assert any(str(rv.EXPECTED_RUN_COUNT) in problem for problem in problems)
