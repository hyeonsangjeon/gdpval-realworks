"""What three gradings of the audio cohort do and do not establish.

``analyze_audio_repeat_variation.py`` reports two things that pull in opposite
directions, and this file exists to keep both of them honest.

The first is a refusal. The card asked for a task-unit confidence interval on
the audio flip rate, and the tool answers that the interval it produces bounds
nothing: with three tasks, a resample that picks one task three times is
likelier than the 2.5% tail being cut off, so the endpoints are the smallest
and the largest per-task rate by construction. That is an arithmetic claim, so
it is checked as arithmetic below -- the bootstrap endpoints must equal the
exact quantiles, which must equal the extremes, and multiplying the evidence
must move none of them. A tool that said "degenerate" while quietly printing a
real-looking interval would be worse than one that said nothing.

The second is a positive finding: inside every run, on the same task, the
grader flips far more often on criteria it listened to than on criteria it
read. That one can be wrong in the ordinary way, so it gets an ordinary
control -- a synthetic cohort whose whole pooled gap is manufactured by task
sizes, on which the stratified test must decline to find anything.

Nothing here calls a model, grades anything, or spends anything.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import analyze_audio_repeat_variation as av  # noqa: E402
from scripts import analyze_repeat_variation as rv  # noqa: E402

BATCH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_ROOT.parent
COHORT = (
    REPO_ROOT
    / "data/grades/_diagnostic"
    / "b16d9b188a763fa9382d9b18df796b2f08cf284b47619195a2feba963149063c"
)

#: The merged 185-task run, and the thirty-task repeat cohort. Neither may be
#: what this analysis reads, or it is quoting somebody else's evidence.
CORPUS_FINGERPRINT = (
    "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
)
THIRTY_TASK_DIGEST = next(
    value for label, _, value in rv.PINNED_FINGERPRINTS if label == "task list digest"
)


@pytest.fixture(scope="module")
def paths() -> list[Path]:
    found = sorted(COHORT.glob("*.json")) + sorted(COHORT.glob("_repeats/run-*/*.json"))
    assert len(found) == av.EXPECTED_RUN_COUNT, (
        f"expected {av.EXPECTED_RUN_COUNT} committed payloads under {COHORT}, "
        f"found {len(found)}. The repeats this analysis reads are not all here"
    )
    return found


@pytest.fixture(scope="module")
def runs(paths) -> list[dict]:
    return av.load_runs(list(paths))


@pytest.fixture(scope="module")
def run_output(paths) -> tuple[int, dict]:
    """One registered-settings run: its exit code and its report.

    Bought once for the module. The permutation is 100,000 draws over 94 items
    and takes several seconds, and every test that needs the real numbers needs
    the same ones, so paying per test would buy nothing but wall clock.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = av.main(["--json", *[str(path) for path in paths]])
    return code, json.loads(buffer.getvalue())


@pytest.fixture(scope="module")
def report(run_output) -> dict:
    return run_output[1]


def _build_runs(spec: list[tuple[str, str, tuple[str, str, str]]]) -> list[dict]:
    """Three synthetic runs from ``(task_id, modality, verdict per run)`` rows.

    Only the fields the census and the contrast read. These never pass the
    fingerprint gate and are not meant to -- they exist so the arithmetic can
    be exercised on inputs whose answer is known in advance.
    """
    scores = {"pass": 1.0, "partial": 0.5, "fail": 0.0}
    order: list[str] = []
    for task_id, _, _ in spec:
        if task_id not in order:
            order.append(task_id)

    runs = []
    for ordinal in range(3):
        tasks = []
        for task_id in order:
            rows = [row for row in spec if row[0] == task_id]
            tasks.append(
                {
                    "task_id": task_id,
                    "pct": 50.0,
                    "items": [
                        {
                            "rubric_item_id": f"{modality}-{index}",
                            "routing_modality": modality,
                            "verdict": verdicts[ordinal],
                            "awarded_score": scores[verdicts[ordinal]],
                            "max_score": 1.0,
                            "score_excluded": False,
                        }
                        for index, (_, modality, verdicts) in enumerate(rows)
                    ],
                }
            )
        runs.append({"_label": f"run-{ordinal + 1:03d}", "tasks": tasks})
    return runs


# ── the census the payloads carry ────────────────────────────────────────


def test_the_census_is_the_one_the_payloads_carry(report):
    """The numbers, pinned. Everything downstream is a claim about these.

    Pinned rather than recomputed here: recomputing them with the code the tool
    uses would agree with itself whatever either of them did.
    """
    census = report["census"]
    assert census["items"] == 108
    assert census["pairs"] == 324
    assert census["verdict_flips"] == 24
    assert census["score_moves"] == 28

    assert census["by_modality"] == {
        "audio": {
            "items": 31,
            "pairs": 93,
            "verdict_flips": 18,
            "verdict_flip_rate_pct": pytest.approx(19.3548, abs=1e-3),
            "score_moves": 18,
            "score_move_rate_pct": pytest.approx(19.3548, abs=1e-3),
            "items_that_ever_flipped": 9,
        },
        "formatting": {
            "items": 10,
            "pairs": 30,
            "verdict_flips": 2,
            "verdict_flip_rate_pct": pytest.approx(6.6667, abs=1e-3),
            "score_moves": 2,
            "score_move_rate_pct": pytest.approx(6.6667, abs=1e-3),
            "items_that_ever_flipped": 1,
        },
        "text": {
            "items": 63,
            "pairs": 189,
            "verdict_flips": 4,
            "verdict_flip_rate_pct": pytest.approx(2.1164, abs=1e-3),
            "score_moves": 8,
            "score_move_rate_pct": pytest.approx(4.2328, abs=1e-3),
            "items_that_ever_flipped": 2,
        },
        "visual": {
            "items": 4,
            "pairs": 12,
            "verdict_flips": 0,
            "verdict_flip_rate_pct": 0.0,
            "score_moves": 0,
            "score_move_rate_pct": 0.0,
            "items_that_ever_flipped": 0,
        },
    }

    assert report["audio_flip_rate_pct"] == pytest.approx(19.3548, abs=1e-3)


def test_the_direction_of_the_flips_is_recorded_and_not_only_the_count(report):
    """Six criteria the grader failed then passed, ten it passed then failed.

    A flip rate on its own cannot distinguish a grader that softened from one
    that hardened from one that is simply unsteady, and the audio column here
    is unsteady in both directions.
    """
    assert report["census"]["transitions"] == {
        "audio:fail->pass": 6,
        "audio:pass->fail": 10,
        "audio:pass->partial": 2,
        "formatting:fail->pass": 2,
        "text:fail->partial": 2,
        "text:pass->fail": 2,
    }


def test_the_headline_rate_is_derived_rather_than_typed_in(runs):
    """Break one audio verdict and the count has to move.

    Without this the table above would pass equally well against a tool that
    printed constants, which is the failure a table of expected values invites.
    """
    before = av.census(runs)["by_modality"][av.REQUIRED_MODALITY]

    mutated = copy.deepcopy(runs)
    for task in mutated[1]["tasks"]:
        for item in task["items"]:
            if item.get("routing_modality") == av.REQUIRED_MODALITY:
                item["verdict"] = "fail" if item["verdict"] != "fail" else "pass"
                item["awarded_score"] = 0.0 if item["verdict"] == "fail" else 1.0
                break
        else:
            continue
        break

    after = av.census(mutated)["by_modality"][av.REQUIRED_MODALITY]
    assert after["verdict_flips"] != before["verdict_flips"], (
        "flipping one audio verdict in one run changed no count; the census is "
        "not reading the payloads it was handed"
    )


def test_the_denominator_did_not_move_between_the_three_gradings(report):
    """Why these rates are not a moving denominator in disguise.

    The thirty-task analysis had to correct for a set of scored items that
    changed between runs. Had that happened here, a "flip" could be an item
    entering or leaving the scoreboard rather than the grader changing its
    mind. It did not: the same four items are excluded in all three, all of
    them visual, and no audio item is ever excluded.
    """
    denominator = report["denominator"]
    assert denominator["excluded_per_run"] == [4, 4, 4]
    assert denominator["identical_across_runs"] is True
    assert denominator["modalities_ever_excluded"] == {"visual": 4}
    assert denominator[f"{av.REQUIRED_MODALITY}_items_ever_excluded"] == 0
    assert len(denominator["excluded_always"]) == 4


# ── the two cohorts cannot be swapped ────────────────────────────────────


def test_this_tool_requires_exactly_what_the_other_one_refuses():
    """The mirror, asserted from both sides.

    ``analyze_repeat_variation`` refuses audio because its cohort predates the
    routing. This one requires it. If those two constants ever drift apart,
    each cohort becomes eligible for the other's analysis and the refusal that
    keeps audio flipping out of the thirty-task intervals stops meaning
    anything.
    """
    assert av.REQUIRED_MODALITY == rv.FORBIDDEN_MODALITY == "audio"
    assert av.shared_arithmetic_problems() == []


def test_the_thirty_task_tool_refuses_these_very_payloads(runs):
    """The same point, exercised rather than read off a constant."""
    problems = rv.shape_problems(copy.deepcopy(runs))
    complaining = [p for p in problems if rv.FORBIDDEN_MODALITY in p]
    assert len(complaining) == av.EXPECTED_RUN_COUNT, (
        "the thirty-task analysis accepted the audio cohort, so its intervals "
        f"can now absorb audio flipping: {problems}"
    )


def test_the_shared_arithmetic_check_can_fail(monkeypatch):
    """A check nobody has watched fail is a comment.

    Two of the numbers in the report come out of the other module's bootstraps,
    which cut at *its* percentiles. If it were ever re-registered at different
    ones, this cohort's endpoints would move with it silently. That is the
    coupling the check exists for, so the check is shown noticing.
    """
    monkeypatch.setattr(rv, "PERCENTILE_LOW", 5.0)
    assert any(
        "PERCENTILE_LOW" in problem for problem in av.shared_arithmetic_problems()
    )

    monkeypatch.setattr(rv, "FORBIDDEN_MODALITY", "video")
    assert any(
        "analyze_repeat_variation refuses" in problem
        for problem in av.shared_arithmetic_problems()
    )


def test_a_run_that_listened_to_nothing_is_refused(runs):
    """The premise of the whole file, enforced.

    Reporting an audio flip rate from runs that never listened is exactly the
    mistake that made the 38% figure unusable, and it is the mistake a
    conveniently available corpus invites.
    """
    stripped = copy.deepcopy(runs)
    for run in stripped:
        for task in run["tasks"]:
            task["items"] = [
                item
                for item in task["items"]
                if item.get("routing_modality") != av.REQUIRED_MODALITY
            ]

    problems = av.shape_problems(stripped)
    assert any("listened to nothing" in problem for problem in problems), problems


def test_the_same_file_three_times_is_refused(paths):
    """The failure that would pass every gate having compared nothing.

    Handed one payload three times, every difference is exactly zero, the flip
    rate is 0.00%, and the report announces a perfectly steady grader. It has
    to be an error rather than a result.
    """
    duplicated = av.load_runs([paths[0], paths[0], paths[0]])
    problems = av.fingerprint_problems(duplicated)
    assert any("same run" in problem for problem in problems), problems


def test_an_item_that_changed_modality_between_runs_is_refused(runs):
    """A contrast by modality needs the modality to belong to the item.

    If the router sent one criterion to listening in one run and to reading in
    the next, the audio-versus-text gap would be partly a fact about the
    router. These three runs route identically; a set that did not is refused
    rather than averaged.
    """
    assert av.shape_problems(copy.deepcopy(runs)) == []

    moved = copy.deepcopy(runs)
    for task in moved[2]["tasks"]:
        for item in task["items"]:
            if item.get("routing_modality") == av.REQUIRED_MODALITY:
                item["routing_modality"] = av.CONTRAST_MODALITY
                break
        else:
            continue
        break

    problems = av.shape_problems(moved)
    assert any("changed routing modality" in problem for problem in problems), problems


def test_the_cohort_is_neither_measurement_that_already_exists():
    """This analysis must not be quoting evidence that belongs to something else."""
    pinned = {label: value for label, _, value in av.PINNED_FINGERPRINTS}
    assert pinned["task list digest"] not in {CORPUS_FINGERPRINT, THIRTY_TASK_DIGEST}
    assert pinned["grading config"] == "gold_audio_repeat_v2_sol_max"
    assert pinned["run status"] == "diagnostic", (
        "a payload calling itself final here would be one that escaped the "
        "diagnostic fork and could overwrite the published corpus"
    )


def test_every_pin_names_a_field_the_payloads_actually_carry(runs):
    """A pin against a missing key passes by matching ``None`` against ``None``.

    ``_dig`` returns ``None`` for a path that does not exist, so a typo in a key
    path would produce a fingerprint that agreed with itself across all three
    runs while checking nothing at all.
    """
    assert av.fingerprint_problems(runs) == []
    for label, path, expected in av.PINNED_FINGERPRINTS:
        observed = av._dig(runs[0], path)
        assert observed is not None, (
            f"the pin for {label} reads {'.'.join(path)}, which no payload "
            "carries; it is comparing None against None"
        )
        assert observed == expected


def test_the_listening_settings_are_pinned_too(runs):
    """Four pins the thirty-task cohort has no equivalent of.

    The audio model, its deployment, how many seconds of each clip were sent,
    and how many perception calls a task was allowed. A repeat that listened to
    sixty seconds where the first listened to thirty is not a repeat, and none
    of the text-era pins would notice.
    """
    pinned = {label: value for label, _, value in av.PINNED_FINGERPRINTS}
    assert pinned["audio model"] == "gpt-audio-1.5"
    assert pinned["audio deployment"] == "gpt-audio-1.5"
    assert pinned["audio clip seconds"] == 30
    assert pinned["audio call cap per task"] == 32
    assert av.fingerprint_problems(runs) == []


# ── the interval that was asked for, and why it is not one ───────────────


def test_the_interval_is_exactly_the_range_of_the_three_task_rates(report):
    """The degeneracy, stated as an equality rather than as a worry.

    Bootstrap endpoints, exact quantiles and the extremes of the attainable set
    are all the same two numbers, and those two numbers are the lowest and the
    highest per-task rate. The interval is not a measurement; it is a
    restatement of the spread between three tasks.
    """
    interval = report["task_unit_interval"]
    rates = sorted(interval["per_task_rate_pct"].values())

    assert interval["is_informative"] is False
    assert interval["bootstrap"]["low"] == pytest.approx(rates[0], abs=1e-3)
    assert interval["bootstrap"]["high"] == pytest.approx(rates[-1], abs=1e-3)
    assert interval["exact_quantiles_pct"]["low"] == pytest.approx(rates[0], abs=1e-3)
    assert interval["exact_quantiles_pct"]["high"] == pytest.approx(rates[-1], abs=1e-3)
    assert interval["extremes_pct"]["min"] == pytest.approx(rates[0], abs=1e-3)
    assert interval["extremes_pct"]["max"] == pytest.approx(rates[-1], abs=1e-3)
    assert interval["width_floor_pp"] == pytest.approx(rates[-1] - rates[0], abs=1e-3)
    assert interval["bootstrap"]["width"] == pytest.approx(
        interval["width_floor_pp"], abs=1e-3
    )


def test_the_enumeration_is_exact_and_complete(report):
    """Twenty-seven draws, ten distinct values, and a single-task draw at 1/27.

    With three clusters the whole bootstrap distribution can be written down,
    so the endpoints are not an artefact of how many resamples were taken.
    """
    interval = report["task_unit_interval"]
    assert interval["clusters"] == 3
    assert interval["ordered_draws"] == 27
    assert interval["distinct_attainable_values"] == 10
    assert interval["attainable_values_pct"] == [
        13.3333,
        14.8148,
        16.6667,
        17.6471,
        19.0476,
        19.3548,
        21.0526,
        21.4286,
        22.8571,
        23.8095,
    ]

    probabilities = interval["probability_of_an_extreme_draw"]
    assert probabilities["at_min"] == pytest.approx(1 / 27, abs=1e-6)
    assert probabilities["at_max"] == pytest.approx(1 / 27, abs=1e-6)
    assert probabilities["at_min"] >= probabilities["tail_being_cut"], (
        "a single-task draw is now rarer than the tail being cut off, so the "
        "endpoints are no longer pinned to the extremes and this analysis's "
        "central finding has changed"
    )


def test_the_enumeration_is_a_distribution_and_not_a_sample():
    """Every ordered draw accounted for, in exact arithmetic.

    Fractions rather than floats so that two draws landing on the same rate are
    recognised as one value instead of being separated in the sixteenth
    decimal, which would inflate the distinct-value count above.
    """
    distribution = av.attainable_distribution(
        ["a", "b", "c"], {"a": 4, "b": 10, "c": 4}, {"a": 30, "b": 42, "c": 21}
    )
    assert sum(count for _, count in distribution) == 27
    assert all(isinstance(value, Fraction) for value, _ in distribution)
    assert distribution == sorted(distribution)

    # Three tasks at one rate collapse to a single attainable value, which
    # floats would not have managed for a third.
    flat = av.attainable_distribution(
        ["a", "b", "c"], {"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 6, "c": 9}
    )
    assert flat == [(Fraction(1, 3), 27)]


def test_more_repeats_could_not_narrow_it(report):
    """The claim that this is not a sample-size problem, made checkable.

    Twice as many repeats, with every task's rate landing exactly where it
    landed here, is this numerator and denominator doubled. The interval does
    not move by a thousandth, because its endpoints are per-task rates and
    those are what was held fixed.
    """
    rows = {
        row["task_id"]: row[av.REQUIRED_MODALITY]
        for row in report["contrast"]["per_task"]
    }
    task_ids = list(rows)
    numerator = {task_id: rows[task_id]["flips"] for task_id in task_ids}
    denominator = {task_id: rows[task_id]["pairs"] for task_id in task_ids}

    first = av.task_unit_interval(
        task_ids, numerator, denominator, resamples=2000, seed=av.BOOTSTRAP_SEED
    )
    # Rebuilt from the payloads, so it has to reproduce what the tool reported.
    assert first["extremes_pct"] == report["task_unit_interval"]["extremes_pct"]

    for multiple in (2, 10, 100):
        scaled = av.task_unit_interval(
            task_ids,
            {task_id: value * multiple for task_id, value in numerator.items()},
            {task_id: value * multiple for task_id, value in denominator.items()},
            resamples=2000,
            seed=av.BOOTSTRAP_SEED,
        )
        assert scaled["bootstrap"] == first["bootstrap"]
        assert scaled["extremes_pct"] == first["extremes_pct"]
        assert scaled["is_informative"] is False


def test_a_fourth_task_is_what_would_cut_a_tail(report):
    """What the tool says would fix it, shown fixing it.

    The report claims four clusters is the first count at which a single-task
    draw is rarer than the 2.5% tail. That is a claim about arithmetic, so it
    is run: the same rates spread over four tasks give an interval whose
    endpoints are no longer the extremes.
    """
    assert report["task_unit_interval"]["clusters_needed_for_a_cut_tail"] == 4

    four = av.task_unit_interval(
        ["a", "b", "c", "d"],
        {"a": 4, "b": 10, "c": 4, "d": 6},
        {"a": 30, "b": 42, "c": 21, "d": 30},
        resamples=4000,
        seed=av.BOOTSTRAP_SEED,
    )
    assert four["ordered_draws"] == 256
    assert four["is_informative"] is True
    assert four["exact_quantiles_pct"]["low"] > four["extremes_pct"]["min"]
    assert four["exact_quantiles_pct"]["high"] < four["extremes_pct"]["max"]


def test_the_unit_that_was_not_used_is_reported_beside_it(report):
    """Choosing a resampling unit is a decision, so the other one is shown.

    On the thirty-task cohort the item bootstrap is the narrower, over-confident
    one, which is the usual argument for preferring the task. Here it is the
    wider, and that inversion is the clamping above seen from the other side
    rather than a point in the task interval's favour. Printing only the ratio
    would invite the usual conclusion from an unusual number.
    """
    not_used = report["item_unit_interval_not_used"]
    assert not_used["width_ratio_item_over_task"] > 1.0
    assert not_used["width"] > report["task_unit_interval"]["bootstrap"]["width"]
    assert "degeneracy" in not_used["note"]


# ── the contrast that does not resample tasks ────────────────────────────


def test_the_contrast_is_the_one_the_runs_show(report):
    """Audio against text, pooled and then task by task."""
    contrast = report["contrast"]
    assert contrast["left"] == "audio"
    assert contrast["right"] == "text"
    assert contrast["left_rate_pct"] == pytest.approx(19.3548, abs=1e-3)
    assert contrast["right_rate_pct"] == pytest.approx(2.1164, abs=1e-3)
    assert contrast["gap_pp"] == pytest.approx(17.2384, abs=1e-3)

    counted = {
        row["task_id"][:8]: {
            name: (row[name]["flips"], row[name]["pairs"]) for name in ("audio", "text")
        }
        for row in contrast["per_task"]
    }
    assert counted == {
        "38889c3b": {"audio": (4, 30), "text": (4, 45)},
        "75401f7c": {"audio": (10, 42), "text": (0, 69)},
        "e222075d": {"audio": (4, 21), "text": (0, 75)},
    }

    assert contrast["holds_in_every_task"] is True
    assert contrast["significant"] is True
    assert contrast["permutation"]["p_one_sided"] < av.ALPHA


def test_a_p_value_cannot_come_out_at_zero(report):
    """A permutation test does not establish impossibility.

    With the plain count-over-draws form, a gap that no shuffle reached would
    be reported as p = 0. The (1 + c) / (1 + n) form bounds it below by one
    draw, which is the honest resolution of a finite number of shuffles. The
    identity is asserted rather than just the bound, because on this cohort 128
    shuffles did reach the gap and the bound alone would hold either way.
    """
    permutation = report["contrast"]["permutation"]
    assert permutation["p_one_sided"] == pytest.approx(
        (1 + permutation["at_least_observed"]) / (1 + permutation["draws"])
    )
    assert permutation["p_one_sided"] >= 1 / (1 + permutation["draws"])
    assert permutation["p_one_sided"] <= permutation["p_two_sided"]


def _confounded_cohort() -> list[dict]:
    """A cohort whose entire pooled gap is manufactured by task sizes.

    Task A holds 20 audio and 2 text criteria and *every* one of them changes
    verdict in run 3. Task B holds 2 audio and 20 text and none of them move.
    Pooled, audio looks far less steady than text. Inside each task the two are
    identical, so the gap is the strata and nothing else.

    This is the control for the real finding: the same shape of evidence with
    the effect removed and the confound left in.
    """
    unstable = ("pass", "pass", "fail")
    steady = ("pass", "pass", "pass")
    return _build_runs(
        [("task-a", "audio", unstable) for _ in range(20)]
        + [("task-a", "text", unstable) for _ in range(2)]
        + [("task-b", "audio", steady) for _ in range(2)]
        + [("task-b", "text", steady) for _ in range(20)]
    )


def test_a_gap_that_is_really_about_task_sizes_is_not_reported_as_a_finding():
    """The control. Stratification is what separates this from the real result.

    Unstratified, this cohort would look like a large, clean audio effect.
    Shuffling the labels inside each task leaves every count where it was, so
    the test reports the observed gap as entirely ordinary -- which it is.
    """
    contrast = av.modality_contrast(
        av.census(_confounded_cohort()), draws=2000, seed=av.PERMUTATION_SEED
    )

    assert contrast["gap_pp"] > 20.0, (
        "the control cohort no longer shows a large pooled gap, so it is no "
        "longer controlling for anything"
    )
    assert contrast["permutation"]["p_one_sided"] > 0.5
    assert contrast["significant"] is False
    for row in contrast["per_task"]:
        assert row["audio"]["rate_pct"] == pytest.approx(row["text"]["rate_pct"])


def test_the_permutation_moves_whole_items_and_not_single_comparisons():
    """Why the unit is the rubric item and not the pair-observation.

    Each item is compared three times, and those three comparisons are one
    item's behaviour rather than three items'. On this cohort the difference is
    visible in the p-value: one audio criterion that disagrees on all three
    pairs, against one steady text criterion. Moving whole items, one of the
    two labellings reaches the observed gap, so p is about a half. Moving the
    six pair-observations independently, all three flips landing on the audio
    label is 1 in 20 -- a tenfold more certain answer from the same evidence.
    """
    runs = _build_runs(
        [
            ("solo", "audio", ("pass", "fail", "partial")),
            ("solo", "text", ("pass", "pass", "pass")),
        ]
    )
    counted = av.census(runs)
    assert counted["by_modality"]["audio"]["verdict_flips"] == 3
    assert counted["by_modality"]["text"]["verdict_flips"] == 0

    contrast = av.modality_contrast(counted, draws=4000, seed=av.PERMUTATION_SEED)
    assert contrast["gap_pp"] == pytest.approx(100.0)
    assert 0.35 < contrast["permutation"]["p_one_sided"] < 0.65, (
        "the permutation is no longer moving whole items; a p near 0.05 here "
        "would mean an item's three comparisons are being shuffled apart and "
        "counted as three independent criteria"
    )
    assert "three pair outcomes moved together" in contrast["permutation"]["unit"]


def test_text_flipping_more_than_audio_does_not_come_out_as_an_audio_finding():
    """The registered claim has a direction, so the reverse has to fail.

    A two-sided reading of this contrast would let "reading is less steady than
    listening" be reported as evidence about listening.
    """
    runs = _build_runs(
        [("solo", "audio", ("pass", "pass", "pass"))] * 8
        + [("solo", "text", ("pass", "pass", "fail"))] * 8
    )
    contrast = av.modality_contrast(
        av.census(runs), draws=2000, seed=av.PERMUTATION_SEED
    )
    assert contrast["gap_pp"] < 0
    assert contrast["significant"] is False
    assert contrast["holds_in_every_task"] is False


# ── the exit status ──────────────────────────────────────────────────────


def test_the_command_exits_zero_on_the_committed_runs(run_output):
    """The tool's own verdict on the evidence it ships with."""
    code, payload = run_output
    assert code == 0
    assert payload["verdict_ok"] is True
    assert payload["settings"]["as_registered"] is True
    assert payload["cohort"]["tasks"] == av.EXPECTED_TASK_COUNT
    assert payload["cohort"]["audio_items"] == av.EXPECTED_AUDIO_ITEMS


def test_a_cohort_the_tool_will_not_read_is_an_error_and_not_a_verdict(tmp_path):
    """Refusals leave by the exception, so they cannot be mistaken for a result."""
    empty = tmp_path / "not-a-grade.json"
    empty.write_text(json.dumps({"tasks": []}), encoding="utf-8")
    with pytest.raises(av.RepeatsAreNotComparable):
        av.main([str(empty), str(empty), str(empty)])


def test_settings_that_are_not_the_registered_ones_turn_the_verdict_red(runs):
    """A real analysis at other settings is still not *this* analysis.

    The seeds and the draw counts are quotable, so a report produced at other
    ones must not be able to present itself as the registered result. Passing
    them stays allowed -- it is how the controls above are run -- it just
    cannot come out green.
    """
    other = av.analyze(
        runs, resamples=500, seed=1, permutation_draws=400, permutation_seed=1
    )
    assert other["settings"]["as_registered"] is False
    assert other["verdict_ok"] is False
    # The contrast itself does not depend on the settings; only the claim to be
    # the registered run does.
    assert other["contrast"]["significant"] is True
    assert other["contrast"]["holds_in_every_task"] is True


def test_the_readable_report_states_the_degeneracy_in_words(report):
    """The finding has to survive being read rather than parsed.

    A JSON field named ``is_informative`` is easy to miss beside an interval
    printed to two decimals, and the interval is what a reader came for.
    """
    text = av._render(report)
    assert "is_informative: False" in text
    assert "by construction" in text
    assert "not zero" in text
    assert text.splitlines()[-1].strip() == "PASS"
