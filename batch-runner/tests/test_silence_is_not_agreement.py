"""336 — silence is not agreement, and a silent arm is not a cheap one.

Two changes are pinned here, both of them about the same mistake in two
places: treating "no answer" as if it were an answer.

1. **The stability count.** ``summarise`` used to call a claim stable when
   its three verdicts formed a one-element set. Three ``judge_error`` values
   are a one-element set, so a claim nobody ever answered was counted as
   perfectly consistent. 334's observation arm scored 13 of 20 "identical
   across repeats" while not a single one of those 13 had been answered even
   once. The same line failed in the other direction too: a claim answered
   ``fail`` twice with one repeat lost counted as *differing*, because the
   missing answer was a second element of the set.

2. **The stop rule.** 330's rules can stop an arm that is completely silent.
   They cannot stop one that answers 15% of the time, which is what 334's
   observation arm did for all sixty of its calls. 336 adds a response-rate
   rule whose threshold comes from the corpus, not from 334.

Everything here runs on constructed calls. Two tests read the committed 334
log, and both open it read-only: 330/331/334's published numbers are not
recomputed, not overwritten, and not compared against as though the old
figures had been right.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_audio_grading_accuracy as probe  # noqa: E402


TASKS = (
    Path(__file__).resolve().parents[2] / "tasks" / "rebuilding_grading_task"
)


# --------------------------------------------------------------------------
# Builders. Nothing here calls a model.
# --------------------------------------------------------------------------


def _claims(n: int) -> tuple[probe.Claim, ...]:
    """``n`` claims, alternating true and false so pairs are well formed."""
    out = []
    for index in range(n):
        holds = index % 2 == 0
        out.append(
            probe.Claim(
                claim_id=f"c{index}",
                clip_id=f"clip{index // 2}",
                family="mock",
                criterion=f"criterion {index}",
                holds=holds,
                because="constructed for this test",
                explicit_pair_id=f"pair{index // 2}",
            )
        )
    return tuple(out)


def _call(
    claim: probe.Claim,
    *,
    repeat: int,
    verdict: str,
    arm: str = "production",
    marker: str = "format_error:unparseable_json",
) -> dict[str, Any]:
    """One call log entry, with the fields the two code paths actually read.

    ``verdict`` of ``judge_error`` is the shape every kind of non-answer takes
    in the log -- a refusal, an unparseable reply and a provider failure all
    land here and differ only in the marker that decides
    ``unanswered_kind``. The stability code sees only the verdict, which is
    exactly why it could not tell any of them from an answer of "no". The
    default marker is 334's: a reply that arrived and would not parse.
    """
    error = marker if verdict == "judge_error" else None
    return {
        "repeat": repeat,
        "arm": arm,
        "claim_id": claim.claim_id,
        "pair_id": claim.pair_id,
        "clip_id": claim.clip_id,
        "family": claim.family,
        "holds": claim.holds,
        "verdict": verdict,
        "outcome": probe.classify(claim, verdict),
        "unanswered_kind": probe.unanswered_kind(verdict, error),
        "confidence": None,
        "evidence": None,
        "judge_error": error,
        "api_call_count": 1,
        "input_tokens": 100,
        "output_tokens": 30,
        "latency_ms": 1.0,
        "usage_complete": True,
    }


def _log(
    pattern: dict[str, list[str]], *, arm: str = "production"
) -> tuple[list[dict[str, Any]], tuple[probe.Claim, ...]]:
    """``{claim_id: [verdict per repeat]}`` -> a call log and its claims."""
    claims = _claims(len(pattern))
    by_id = {c.claim_id: c for c in claims}
    calls = []
    for claim_id, verdicts in pattern.items():
        for repeat, verdict in enumerate(verdicts, start=1):
            calls.append(
                _call(by_id[claim_id], repeat=repeat, verdict=verdict, arm=arm)
            )
    return calls, claims


def _stability(
    pattern: dict[str, list[str]], *, arm: str = "production"
) -> dict[str, Any]:
    calls, claims = _log(pattern, arm=arm)
    return probe.summarise(calls, claims=claims)["stability"]


# --------------------------------------------------------------------------
# 1. The stability count
# --------------------------------------------------------------------------


def test_a_claim_nobody_answered_is_not_counted_as_consistent() -> None:
    """The 334 defect, at its smallest.

    Three failures in a row are three failures in a row. Before this change
    they were one distinct value, and one distinct value meant "identical
    across repeats".
    """
    stab = _stability(
        {
            "c0": ["judge_error", "judge_error", "judge_error"],
            "c1": ["judge_error", "judge_error", "judge_error"],
        }
    )
    assert stab["claims"] == 2
    assert stab["identical_across_repeats"] == 0
    assert stab["differed_across_repeats"] == 0
    assert stab["claims_without_two_answers"] == 2
    assert stab["claims_with_two_or_more_answers"] == 0


def test_no_comparable_claim_gives_null_not_a_perfect_score() -> None:
    """The share is undefined, and undefined is not 100% and not 0%.

    A corpus where nothing was answered twice has no consistency to report.
    Publishing 1.0 would say the judge was perfectly reliable; publishing 0.0
    would say it was perfectly unreliable. Both are inventions.
    """
    stab = _stability({"c0": ["judge_error"] * 3})
    assert stab["identical_share_of_comparable"] is None
    assert stab["repeat_flips"]["flip_rate_pct"] is None
    assert stab["repeat_flips"]["claims_compared"] == 0
    assert stab["repeat_flips"]["claims_with_no_comparable_pair"] == 1


def test_one_answer_is_not_two_and_cannot_be_stable() -> None:
    """A single reply agrees with nothing. It is not evidence either way."""
    stab = _stability({"c0": ["pass", "judge_error", "judge_error"]})
    assert stab["claims_with_two_or_more_answers"] == 0
    assert stab["identical_across_repeats"] == 0
    assert stab["claims_without_two_answers"] == 1
    assert stab["identical_share_of_comparable"] is None


def test_a_missing_repeat_no_longer_makes_a_steady_claim_look_unsteady() -> None:
    """The same bug, pointing the other way -- and it hit the healthy arm.

    334's production arm has exactly this: ``column_second`` answered ``fail``
    twice and lost one repeat to a refusal. The old rule saw ``{judge_error,
    fail}``, two distinct values, and filed it as "differed across repeats".
    Silence was being read as a *disagreement* there, having been read as an
    agreement one column over.
    """
    stab = _stability({"c0": ["judge_error", "fail", "fail"]})
    assert stab["claims_with_two_or_more_answers"] == 1
    assert stab["identical_across_repeats"] == 1
    assert stab["differed_across_repeats"] == 0
    assert stab["identical_share_of_comparable"] == 1.0


def test_a_real_disagreement_is_still_a_disagreement() -> None:
    """The fix must not quietly make everything look stable."""
    stab = _stability({"c0": ["pass", "fail", "pass"]})
    assert stab["differed_across_repeats"] == 1
    assert stab["identical_across_repeats"] == 0
    assert stab["identical_share_of_comparable"] == 0.0
    assert stab["repeat_flips"]["claims_that_ever_flipped"] == 1
    assert stab["repeat_flips"]["claims_compared"] == 1


def test_a_judge_that_says_no_every_time_is_consistent_not_silent() -> None:
    """The distinction the whole change rests on.

    ``fail`` three times is a judge that answered three times and answered
    the same way. It is a bad judge on this corpus -- 331 measured exactly
    that -- but it is not a silent one, and counting it as consistent is
    correct. A fix that swept up genuine negatives along with non-answers
    would erase 331's finding rather than repair 334's arithmetic.
    """
    stab = _stability({f"c{i}": ["fail", "fail", "fail"] for i in range(4)})
    assert stab["identical_across_repeats"] == 4
    assert stab["claims_without_two_answers"] == 0
    assert stab["identical_share_of_comparable"] == 1.0
    assert stab["repeat_flips"]["flip_rate_pct"] == 0.0


def test_the_three_claim_buckets_always_add_up_to_the_corpus() -> None:
    """No claim can fall out of the count, and none can be counted twice."""
    stab = _stability(
        {
            "c0": ["pass", "pass", "pass"],
            "c1": ["pass", "fail", "pass"],
            "c2": ["judge_error", "judge_error", "judge_error"],
            "c3": ["judge_error", "judge_error", "pass"],
            "c4": ["fail", "judge_error", "fail"],
        }
    )
    assert stab["claims"] == 5
    assert (
        stab["identical_across_repeats"]
        + stab["differed_across_repeats"]
        + stab["claims_without_two_answers"]
        == stab["claims"]
    )
    assert stab["claims_with_two_or_more_answers"] == 3
    assert stab["identical_across_repeats"] == 2  # c0 and c4
    assert stab["differed_across_repeats"] == 1  # c1
    assert stab["claims_without_two_answers"] == 2  # c2 and c3


def test_the_flip_denominators_separate_pairs_from_claims() -> None:
    """Two denominators, both reported, neither standing in for the other."""
    stab = _stability(
        {
            "c0": ["pass", "fail", "pass"],  # 3 pairs, 2 flips
            "c1": ["judge_error", "judge_error", "judge_error"],  # 0 pairs
            "c2": ["pass", "judge_error", "pass"],  # 1 pair, 0 flips
        }
    )
    flips = stab["repeat_flips"]
    assert flips["comparable_pairs"] == 4
    assert flips["pairs_dropped_for_a_missing_answer"] == 5
    assert flips["flips"] == 2
    assert flips["claims_compared"] == 2
    assert flips["claims_with_no_comparable_pair"] == 1
    assert flips["claims_that_ever_flipped"] == 1
    assert flips["flip_rate_pct"] == pytest.approx(50.0)


def test_the_published_block_says_the_key_changed_meaning() -> None:
    """``identical_across_repeats`` kept its name and changed its value.

    Renaming it would have hidden that every run before 336 published a
    different quantity under it. Keeping the name and saying so in the
    artifact is the version a reader comparing two runs can act on.
    """
    stab = _stability({"c0": ["pass", "pass", "pass"]})
    meaning = stab["meaning"]
    assert "336" in meaning
    assert "identical_across_repeats" in meaning
    assert "not comparable" in meaning.lower()


# --------------------------------------------------------------------------
# 2. Where the threshold comes from
# --------------------------------------------------------------------------


def test_the_threshold_is_derived_from_the_corpus_not_from_334() -> None:
    """The number is recomputed here from the design, with no 334 input.

    20 claims, 3 repeats. A claim needs two answered repeats before it can
    contribute either a majority the primary test can use or a pair the
    stability figure can use. Five settled claims is the smallest corpus that
    can reach alpha at all, and the rate that yields five out of twenty --
    under the optimistic assumption that failures are independent -- is where
    the requirement sits. 334's numbers appear nowhere in this calculation.
    """
    assert probe.minimum_settled_claims(0.05) == 5
    # Four cannot reach alpha however they land, five can.
    assert 0.5 ** 4 > 0.05
    assert 0.5 ** 5 <= 0.05

    required = probe.required_response_rate(
        claims=20, repeats=3, settled_claims_needed=5
    )
    assert required == pytest.approx(0.32635, abs=5e-5)
    # Pinned at 1/3: above the requirement, and a number a reader can hold.
    assert probe.MIN_RESPONSE_RATE == pytest.approx(1 / 3)
    assert required <= probe.MIN_RESPONSE_RATE <= required + 0.02


def test_the_derivation_refuses_the_cases_it_cannot_answer() -> None:
    """It raises rather than returning a plausible number.

    One repeat can never settle a claim under the two-answer rule, and asking
    for more settled claims than the corpus has is a design that does not
    exist. Both used to be reachable only by reading the source.
    """
    with pytest.raises(ValueError):
        probe.required_response_rate(
            claims=20, repeats=1, settled_claims_needed=5
        )
    with pytest.raises(ValueError):
        probe.required_response_rate(
            claims=20, repeats=3, settled_claims_needed=21
        )


def test_the_rules_are_the_ones_336_writes_down() -> None:
    """Three numbers in two files. This keeps them equal.

    The four rules 330 pinned are asserted by 330's own test and are not
    re-asserted here; what this covers is the three 336 adds.
    """
    rules = probe.SPEECH_STOP_RULES
    assert rules.min_response_rate == pytest.approx(1 / 3)
    assert rules.response_rate_min_observations == 10
    assert rules.response_rate_alpha == 0.05

    doc = (TASKS / "336-silence-is-not-agreement.md").read_text(
        encoding="utf-8"
    )
    assert "1/3" in doc
    assert "10번" in doc
    assert "0.05" in doc


def test_the_older_rules_are_untouched() -> None:
    """336 extends 330's rules in place. It does not re-tune them."""
    rules = probe.SPEECH_STOP_RULES
    assert rules.wall_clock_seconds == 20 * 60
    assert rules.zero_response_after == 10
    assert rules.max_provider_failures == 10
    assert rules.stop_on_undelivered_audio is True


def test_the_rule_defaults_to_off_so_published_corpora_do_not_move() -> None:
    """A run that did not pre-register this rule does not acquire it."""
    bare = probe.StopRules()
    assert bare.min_response_rate is None
    assert bare.response_rate_min_observations is None
    calls = _dead_arm(60)
    assert probe._stop_reason(bare, calls=calls, elapsed_s=1.0) is None


# --------------------------------------------------------------------------
# 3. When the rule fires
# --------------------------------------------------------------------------


def _arm_calls(
    pattern: list[bool], *, arm: str, start: int = 0
) -> list[dict[str, Any]]:
    """One call per entry; ``True`` answered, ``False`` not."""
    claims = _claims(len(pattern) + start)
    out = []
    for index, answered in enumerate(pattern):
        claim = claims[index + start]
        out.append(
            _call(
                claim,
                repeat=1,
                verdict="pass" if answered else "judge_error",
                arm=arm,
            )
        )
    return out


def _dead_arm(n: int) -> list[dict[str, Any]]:
    return _arm_calls([False] * n, arm="production")


def _fire(calls: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    return probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=1.0
    )


def _replay(calls: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """Feed the calls one at a time, the way ``run_measurement`` does.

    Handing the rule a finished log answers "would this run have stopped".
    Handing it one call at a time answers "where", which is the only version
    that decides how much money is spent.
    """
    seen: list[dict[str, Any]] = []
    for call in calls:
        seen.append(call)
        fired = probe._stop_reason(
            probe.SPEECH_STOP_RULES, calls=seen, elapsed_s=1.0
        )
        if fired is not None:
            return fired
    return None


def test_nine_calls_are_never_enough_to_stop_on_rate() -> None:
    """The minimum window is a floor on evidence, not a grace period.

    Nine straight failures is a worse-looking run than some windows that do
    fire later, and it still does not fire: P(0 answers | 9, 1/3) is 0.026,
    below alpha, so without the floor this would stop. The floor is what
    stops the rule from ruling on a sample too small to have a rate.
    """
    assert probe._binomial_at_most(0, 9, 1 / 3) < 0.05
    assert _fire(_arm_calls([False] * 9, arm="production")) is None


def test_ten_silent_calls_are_still_reported_under_the_older_rule() -> None:
    """Both rules fire at n=10 with zero answers. The older one is named.

    Not an accident of ordering: at its minimum window the new rule reduces
    to exactly "no answers at all", because P(<=1 | 10, 1/3) is 0.104 and
    does not clear alpha. Reporting it as ``zero_response_after`` keeps a
    plain fact from being re-described as a probability, and it means the new
    rule buys nothing on its first opportunity -- which is why it cannot have
    been chosen to make any particular run stop early.
    """
    assert probe._binomial_at_most(1, 10, 1 / 3) > 0.05
    fired = _fire(_arm_calls([False] * 10, arm="production"))
    assert fired is not None
    assert fired["rule"] == "zero_response_after"


def test_the_boundary_is_where_the_evidence_crosses_alpha() -> None:
    """Checked at n=20 on both sides of the crossing, not at a round number.

    Two answers in twenty fires (p = 0.018); three does not (p = 0.060). The
    rule is a test on the evidence, so its boundary moves with n rather than
    sitting at a fixed observed rate -- 2/20 and 3/20 are both far below 1/3.
    """
    assert probe._binomial_at_most(2, 20, 1 / 3) <= 0.05
    assert probe._binomial_at_most(3, 20, 1 / 3) > 0.05

    two = [True, True] + [False] * 18
    three = [True, True, True] + [False] * 17
    fired = _fire(_arm_calls(two, arm="production"))
    assert fired is not None and fired["rule"] == "min_response_rate"
    assert fired["answered_in_arm"] == 2
    assert fired["after_calls_in_arm"] == 20
    assert _fire(_arm_calls(three, arm="production")) is None


def test_an_arm_at_the_required_rate_is_not_stopped_for_being_average() -> None:
    """Exactly at the requirement, evenly spread, over a long run."""
    pattern = [index % 3 == 0 for index in range(60)]
    assert sum(pattern) == 20
    assert _fire(_arm_calls(pattern, arm="production")) is None


def test_an_intermittent_arm_is_stopped_once_the_evidence_arrives() -> None:
    """334's actual shape: answers sometimes, far too rarely.

    One in ten is below the requirement but not silent, which is the gap
    between 330's rules and this one. Nothing fires early -- the first ten
    calls contain an answer, so the zero-response rule is out, and the first
    six windows after that are still consistent with 1/3. The stop lands on
    call seventeen, when two answers in seventeen has become unlikely enough
    (p = 0.044) at a rate the design needs.
    """
    pattern = [index % 10 == 0 for index in range(40)]
    fired = _replay(_arm_calls(pattern, arm="production"))
    assert fired is not None
    assert fired["rule"] == "min_response_rate"
    assert fired["after_calls_in_arm"] == 17
    assert fired["answered_in_arm"] == 2
    assert fired["p_if_the_arm_met_the_limit"] == pytest.approx(0.044, abs=1e-3)


def test_a_healthy_arm_hides_nothing_when_the_other_one_is_failing() -> None:
    """Per arm, for the reason 334 section 6 gives.

    Pooled over both arms the run answers 55% of the time and no rule of any
    threshold would fire. The failing arm is only visible once the arms are
    counted apart.
    """
    calls = []
    for index in range(30):
        good = _arm_calls([True], arm="production", start=index)[0]
        bad = _arm_calls(
            [index % 10 == 0], arm="observation", start=index
        )[0]
        calls.append(good)
        calls.append(bad)

    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=1.0
    )
    assert fired is not None
    assert fired["arm"] == "observation"
    assert fired["rule"] == "min_response_rate"

    answered = sum(1 for c in calls if c["unanswered_kind"] is None)
    assert answered / len(calls) > 0.5


def test_the_order_the_arms_run_in_does_not_change_the_verdict() -> None:
    """Crossed ordering. The rule reads counts, so it must not read position.

    334 ran production first within each claim. A run that interleaved the
    other way has the same arms with the same calls in the same within-arm
    order, so it must stop in the same arm after the same number of that
    arm's calls -- the interleaving is not an input to the decision.

    Shuffling is the other half. It reorders calls *within* an arm too, so
    when the stop lands may legitimately move: two answers arriving first
    look different from two arriving last, and pretending otherwise would be
    asserting that the rule ignores its own data. What must not move is which
    arm is named, and that the healthy arm is never the one named.
    """
    def build(observation_first: bool, shuffle_seed: Optional[int] = None):
        calls = []
        for index in range(30):
            good = _arm_calls([True], arm="production", start=index)[0]
            bad = _arm_calls(
                [index % 10 == 0], arm="observation", start=index
            )[0]
            calls.extend([bad, good] if observation_first else [good, bad])
        if shuffle_seed is not None:
            random.Random(shuffle_seed).shuffle(calls)
        return calls

    def stop_point(calls):
        fired = _replay(calls)
        if fired is None:
            return None
        return fired["arm"], fired["after_calls_in_arm"], fired["rule"]

    forward = stop_point(build(False))
    reverse = stop_point(build(True))
    assert forward == reverse == ("observation", 17, "min_response_rate")

    for seed in (20260908, 1, 77):
        shuffled = stop_point(build(False, shuffle_seed=seed))
        assert shuffled is not None
        assert shuffled[0] == "observation"
        # Which of the two rules names it also depends on the within-arm
        # order -- a shuffle that puts ten unanswered calls first is caught by
        # the older rule, which is the correct report for that window.
        assert shuffled[2] in {"min_response_rate", "zero_response_after"}


def test_a_third_arm_is_judged_on_its_own_calls() -> None:
    """Independence, checked with more than two arms.

    Nothing in the rule averages arms together, so a run with a healthy arm,
    a dead arm and an intermittent one stops on whichever crosses first and
    names it.
    """
    calls = []
    for index in range(30):
        calls.append(_arm_calls([True], arm="healthy", start=index)[0])
        calls.append(
            _arm_calls([index % 10 == 0], arm="thin", start=index)[0]
        )
    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=1.0
    )
    assert fired is not None
    assert fired["arm"] == "thin"


def test_the_reading_says_it_is_a_spending_rule_not_a_finding() -> None:
    """A stop is about the run's design, never about the model's quality."""
    fired = _fire(_arm_calls([True, True] + [False] * 18, arm="production"))
    reading = fired["reading"]
    assert "spending rule" in reading
    assert "not a finding" in reading
    assert fired["p_if_the_arm_met_the_limit"] < fired["alpha"]
    assert fired["limit"] == pytest.approx(1 / 3)
    assert fired["observed"] == pytest.approx(0.1)


# --------------------------------------------------------------------------
# 4. What a stop costs, and what it leaves behind
# --------------------------------------------------------------------------


def test_the_false_stop_rate_is_measured_and_not_assumed() -> None:
    """The multiplicity cost, simulated rather than asserted.

    The rule is checked after every call, so an arm answering at exactly the
    requirement gets many chances to dip below it. That is a real cost and it
    is large -- about one run in seven. It is acceptable only because a stop
    spends less money than planned rather than producing a conclusion, and
    because an arm answering at 1/3 is already at the edge of a design that
    needs 1/3. Well above the requirement it vanishes.

    Seeded, and small enough to run in the suite.
    """
    def false_stop_rate(true_rate: float, trials: int, calls: int) -> float:
        rng = random.Random(20260908)
        stops = 0
        for _ in range(trials):
            answered = 0
            for n in range(1, calls + 1):
                if rng.random() < true_rate:
                    answered += 1
                if n < 10:
                    continue
                p = probe._binomial_at_most(answered, n, probe.MIN_RESPONSE_RATE)
                if p <= 0.05:
                    stops += 1
                    break
        return stops / trials

    at_the_edge = false_stop_rate(1 / 3, 2000, 60)
    comfortable = false_stop_rate(0.5, 2000, 60)
    healthy = false_stop_rate(0.9833, 2000, 60)

    assert 0.10 < at_the_edge < 0.20
    assert comfortable < 0.02
    assert healthy == 0.0


def test_a_stopped_run_reports_what_it_left_unpaired() -> None:
    """The stop lands mid-claim and the record says so.

    The partner call is not bought to tidy the arms up -- that would spend
    money after the decision to stop spending it -- so every downstream
    analysis that assumes paired arms is told, by claim id, which claims are
    not paired.
    """
    calls = []
    for index in range(30):
        calls.append(_arm_calls([True], arm="production", start=index)[0])
        calls.append(
            _arm_calls([index % 10 == 0], arm="observation", start=index)[0]
        )

    seen = []
    for call in calls:
        seen.append(call)
        if probe._stop_reason(
            probe.SPEECH_STOP_RULES, calls=seen, elapsed_s=1.0
        ) is not None:
            break

    # The stop lands on the observation call of claim c16, so both arms have
    # been asked about it and nothing is half-done.
    assert seen[-1]["arm"] == "observation"
    assert seen[-1]["claim_id"] == "c16"
    census = probe._stop_census(seen, ["production", "observation"])
    assert census["claims_missing_an_arm_entirely"] == []
    assert census["claims_with_unequal_calls_across_arms"] == []

    # Drop the last call, as a stop landing one call earlier would. Now the
    # production call for c16 is paid for and its partner never was.
    census = probe._stop_census(seen[:-1], ["production", "observation"])
    assert census["claims_missing_an_arm_entirely"] == ["c16"]
    assert census["claims_with_unequal_calls_across_arms"] == ["c16"]


def test_the_census_forbids_a_p_value_over_the_survivors() -> None:
    """The one sentence that has to be attached to every stopped run.

    Stopping makes n depend on the data, so the pre-registered tests are no
    longer the tests that were registered. Collecting the pairs that survived
    and reporting significance over them is the specific mistake, and the
    artifact says so where the numbers are, not only in a document.
    """
    calls, _ = _log({"c0": ["pass"], "c1": ["pass"]})
    note = probe._stop_census(calls, ["production"])["inference"]
    assert "p-value" in note
    assert "not missing at random" in note


def test_the_stopped_block_carries_the_census_with_it() -> None:
    """Reached through ``run_measurement``, not by calling the helper."""
    claims = _claims(20)

    class _Verdict:
        def __init__(self, verdict: str) -> None:
            self.verdict = verdict
            self.judge_error = (
                "format_error:unparseable_json"
                if verdict == "judge_error"
                else None
            )
            self.confidence = None
            self.evidence = None
            self.api_call_count = 1
            self.input_tokens = 100
            self.output_tokens = 20
            self.latency_ms = 1.0
            self.usage_complete = True

    class _Wire:
        """Only the two members ``run_measurement`` touches.

        The real client rewrites the prompt for the treatment arm and records
        what went out. Nothing here sends a request, so the stub records a
        well-formed delivery per call -- otherwise the undelivered-audio rule
        fires on call one and this test stops measuring what it is for.
        """

        def __init__(self) -> None:
            self.arm = "production"
            self.records: list[dict[str, Any]] = []

        def sent(self) -> None:
            self.records.append(
                {
                    "audio_part_present": True,
                    "audio_sha256": "sha-mock",
                    "audio_format": "wav",
                    "audio_tokens": 185,
                    "response_model": "mock",
                    "sent_wav": {
                        "bytes": 1000,
                        "sample_rate_hz": 24000,
                        "channels": 1,
                        "duration_s": 1.0,
                    },
                }
            )

    wire = _Wire()

    class _Perception:
        def __init__(self) -> None:
            self.calls = 0

        def reset(self) -> None:
            pass

        def judge(self, *, criterion: str, audio_path: str) -> Any:
            self.calls += 1
            wire.sent()
            # Arms alternate, so every second call is the failing arm.
            if self.calls % 2 == 0:
                return _Verdict("judge_error")
            return _Verdict("pass")

    class _Prerendered:
        def __init__(self) -> None:
            self.digests = {c.clip_id: f"sha-{c.clip_id}" for c in claims}
            self.paths = {
                c.clip_id: Path("/nonexistent") / f"{c.clip_id}.wav"
                for c in claims
            }

    result = probe.run_measurement(
        perception=_Perception(),
        clip_dir=Path("/nonexistent"),
        repeats=3,
        claims=claims,
        arms=("production", "observation"),
        wire=wire,
        prerendered=_Prerendered(),
        stop_rules=probe.SPEECH_STOP_RULES,
        clock=lambda: 0.0,
    )

    stopped = result["stopped"]
    assert stopped is not None
    assert stopped["rule"] == "zero_response_after"
    assert stopped["arm"] == "observation"
    assert "left_behind" in stopped
    assert "p-value" in stopped["left_behind"]["inference"]
    # The run stopped, so it did not buy all sixty.
    assert len(result["calls"]) < result["planned_calls"]


# --------------------------------------------------------------------------
# 5. Resume, and the published files
# --------------------------------------------------------------------------


def test_the_rule_reads_the_whole_arm_not_the_calls_since_a_restart() -> None:
    """Accumulated state, which is the shape a resumed run has.

    A resumed run hands the rule the calls it already paid for plus the new
    ones. Fifteen prior failures and five new ones is a twenty-call arm, and
    it has to be judged as one -- a rule that looked only at the new calls
    would let a resume launder an arm's history, and a resume is exactly when
    someone is most tempted to keep going.
    """
    prior = _arm_calls([False] * 15, arm="production")
    resumed = prior + _arm_calls(
        [True, False, False, False, False], arm="production", start=15
    )
    assert len(resumed) == 20

    fired = _fire(resumed)
    assert fired is not None
    assert fired["rule"] == "min_response_rate"
    assert fired["after_calls_in_arm"] == 20
    assert fired["answered_in_arm"] == 1

    # And the same twenty calls, judged as five, do not fire.
    assert _fire(resumed[15:]) is None


def test_a_resume_that_recovers_is_allowed_to_continue() -> None:
    """The counterpart. A bad start that turns around is not stopped.

    Nine failures then a steady arm: by call thirty the evidence no longer
    clears alpha, and nothing fires. A rule that latched on the worst window
    it ever saw would kill a run that had recovered.
    """
    calls = _arm_calls(
        [False] * 9 + [True] * 21, arm="production"
    )
    assert _fire(calls) is None


def test_334_is_not_rewritten_by_any_of_this() -> None:
    """The published numbers stay where they are.

    336 changes how the figure is computed from here on. It does not reach
    back into a file whose numbers were reported, and the re-analysis lives
    under its own name. This asserts the 334 artifact still holds the values
    334 published, including the wrong one it flagged in its own section 7.
    """
    source = TASKS / "334-audio-accuracy-measured.json"
    data = json.loads(source.read_text(encoding="utf-8"))

    observation = data["arms"]["observation"]["stability"]
    assert observation["identical_across_repeats"] == 13
    assert observation["repeat_flips"]["claims_that_ever_flipped"] == 0
    assert observation["repeat_flips"]["comparable_pairs"] == 2

    control = data["accuracy"]["stability"]
    assert control["identical_across_repeats"] == 15
    assert data["stopped"] is None
    assert len(data["calls"]) == 120


def test_the_reanalysis_is_a_separate_file_with_its_own_fingerprint() -> None:
    """A corrected number needs a new name, or it is an overwrite.

    The re-analysis records which file it read and the digest it read, so a
    reader can check that the source has not moved underneath it.
    """
    path = TASKS / "336-334-stability-reanalysed.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    source = TASKS / "334-audio-accuracy-measured.json"
    assert data["source"]["file"] == "334-audio-accuracy-measured.json"
    assert data["source"]["sha256"] == hashlib.sha256(
        source.read_bytes()
    ).hexdigest()
    assert data["arms"]["observation"]["after"]["identical_across_repeats"] == 2
    assert data["arms"]["observation"]["before"]["identical_across_repeats"] == 13
    assert data["arms"]["production"]["before"]["identical_across_repeats"] == 15
    assert data["arms"]["production"]["after"]["identical_across_repeats"] == 16
    assert data["primary_metric_changed"] is False


def test_the_corrected_count_holds_none_of_the_claims_the_old_one_held() -> None:
    """13 did not become 2 by losing eleven claims.

    Counted straight off 334's recorded call log, not off either summary, so
    a bug shared by both readings cannot hide here. Every one of the thirteen
    the old rule called identical was a claim that answered nothing three
    times; both of the two the new rule calls identical are claims the old
    rule called *not* identical. The two sets are disjoint, which is why 336
    changes the meaning of the key rather than the value of a number -- and
    why a reader comparing the two runs on this field is comparing different
    claims, not a claim count that moved.
    """
    data = json.loads(
        (TASKS / "334-audio-accuracy-measured.json").read_text(encoding="utf-8")
    )
    verdicts: dict[str, list[str]] = {}
    for call in data["calls"]:
        if call["arm"] == "observation":
            verdicts.setdefault(call["claim_id"], []).append(call["verdict"])

    old_identical = {c for c, v in verdicts.items() if len(set(v)) == 1}
    answered = {c: [v for v in vs if v != "judge_error"] for c, vs in verdicts.items()}
    new_identical = {
        c for c, v in answered.items() if len(v) >= 2 and len(set(v)) == 1
    }

    assert len(old_identical) == 13
    assert len(new_identical) == 2
    assert not (old_identical & new_identical)
    assert all(set(verdicts[c]) == {"judge_error"} for c in old_identical)
    assert new_identical == {"meeting_to_tuesday", "valve_wait"}
    # None of the thirteen moved to "differed"; they all left the comparison.
    assert not any(len(answered[c]) >= 2 for c in old_identical)


def test_the_counterfactual_is_labelled_as_computed_after_the_pinning() -> None:
    """Order of operations, stated where the number is.

    The threshold came from the corpus and the 334 replay came afterwards. A
    reader has no way to tell those apart from the number alone, so the file
    says which came first rather than leaving it to be trusted.
    """
    data = json.loads(
        (TASKS / "336-334-stability-reanalysed.json").read_text(
            encoding="utf-8"
        )
    )
    counterfactual = data["stop_rule_counterfactual"]
    assert counterfactual["arm"] == "observation"
    assert counterfactual["would_have_stopped_after_calls"] == 26
    assert counterfactual["calls_bought"] == 120
    assert "after" in counterfactual["pinned_before_this_was_computed"].lower()
