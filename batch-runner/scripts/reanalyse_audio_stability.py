#!/usr/bin/env python3
"""Recompute 334's stability figures under 336's rule, into a new file.

334 section 7 flagged a number in its own artifact and deliberately left it
alone:

    관찰 갈래의 ``stability.identical_across_repeats``가 13으로 찍혀 있는데,
    이건 세 번 다 안 읽힌 13문항을 "반복끼리 같았다"로 센 것이다. (...)
    결과를 본 뒤에 계산을 고치지 않기 위해 이번엔 안 고치고 여기 적어만 둔다.

336 fixes the calculation, which raises the question of what to do with a
published run whose figure was computed the old way. Three options, and only
one of them is honest:

* recompute in place -- an overwrite of a reported number, forbidden;
* leave it and say nothing -- leaves a known-wrong figure as the only figure;
* recompute under a new name, next to the old one, with both shown.

This is the third. It reads ``334-audio-accuracy-measured.json`` read-only,
records the digest it read so a reader can confirm the source has not moved,
and writes ``336-334-stability-reanalysed.json``. It never writes to any 33x
file other than its own output.

The counterfactual at the end -- where 336's stop rule would have landed on
334's call log -- is included because it is the only honest way to state what
the rule costs and saves. It was computed *after* the threshold was pinned,
and the file says so in the field itself rather than asking to be trusted on
the ordering.

Usage:
  python scripts/reanalyse_audio_stability.py
  python scripts/reanalyse_audio_stability.py --check   # CI: no write, diff
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import measure_audio_grading_accuracy as probe  # noqa: E402

TASKS = Path(__file__).resolve().parents[2] / "tasks" / "rebuilding_grading_task"
SOURCE = TASKS / "334-audio-accuracy-measured.json"
OUTPUT = TASKS / "336-334-stability-reanalysed.json"


def _claims(records: list[dict[str, Any]]) -> tuple[probe.Claim, ...]:
    """Rebuild the corpus from the log rather than from today's constants.

    The claim list is stored in the artifact, so the re-analysis uses the
    corpus that actually ran. Importing the current speech set instead would
    silently re-key the per-claim table if the corpus were ever edited, and
    every per-claim figure would come back empty while the per-call ones
    looked fine -- the failure ``summarise``'s own docstring warns about.
    """
    return tuple(
        probe.Claim(
            claim_id=record["claim_id"],
            clip_id=record["clip_id"],
            family=record["family"],
            criterion=record["criterion"],
            holds=record["holds"],
            because=record["because"],
            explicit_pair_id=record["pair_id"],
        )
        for record in records
    )


def _before(block: dict[str, Any]) -> dict[str, Any]:
    """The published figures, copied out of the source without touching it."""
    flips = block["repeat_flips"]
    return {
        "claims": block["claims"],
        "identical_across_repeats": block["identical_across_repeats"],
        "no_majority": block["no_majority"],
        "comparable_pairs": flips["comparable_pairs"],
        "pairs_dropped_for_a_missing_answer": flips[
            "pairs_dropped_for_a_missing_answer"
        ],
        "flips": flips["flips"],
        "flip_rate_pct": flips["flip_rate_pct"],
        "claims_that_ever_flipped": flips["claims_that_ever_flipped"],
        "how_it_was_counted": (
            "A claim counted as identical when its three verdicts formed a "
            "one-element set, and judge_error was an element like any other. "
            "claims_that_ever_flipped counted every claim, including claims "
            "with no comparable pair, as not having flipped."
        ),
    }


def _after(block: dict[str, Any]) -> dict[str, Any]:
    flips = block["repeat_flips"]
    return {
        "claims": block["claims"],
        "claims_with_two_or_more_answers": block[
            "claims_with_two_or_more_answers"
        ],
        "identical_across_repeats": block["identical_across_repeats"],
        "differed_across_repeats": block["differed_across_repeats"],
        "claims_without_two_answers": block["claims_without_two_answers"],
        "identical_share_of_comparable": block["identical_share_of_comparable"],
        "no_majority": block["no_majority"],
        "comparable_pairs": flips["comparable_pairs"],
        "pairs_dropped_for_a_missing_answer": flips[
            "pairs_dropped_for_a_missing_answer"
        ],
        "flips": flips["flips"],
        "flip_rate_pct": flips["flip_rate_pct"],
        "claims_compared": flips["claims_compared"],
        "claims_with_no_comparable_pair": flips[
            "claims_with_no_comparable_pair"
        ],
        "claims_that_ever_flipped": flips["claims_that_ever_flipped"],
        "how_it_is_counted": (
            "judge_error is dropped before the comparison. A claim with fewer "
            "than two answered repeats is neither identical nor differing; it "
            "is counted separately and is in no share's denominator."
        ),
    }


def _counterfactual(calls: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay the log through 336's rule, checking after every call."""
    seen: list[dict[str, Any]] = []
    fired: Optional[dict[str, Any]] = None
    for call in calls:
        seen.append(call)
        fired = probe._stop_reason(
            probe.SPEECH_STOP_RULES, calls=seen, elapsed_s=0.0
        )
        if fired is not None:
            break

    pinned = (
        "The threshold was derived from the corpus -- 20 claims, 3 repeats, "
        "a claim needs two answered repeats, five settled claims is the "
        "smallest corpus that can reach alpha -- and pinned at 1/3 before "
        "this replay was run. This number was computed after that. Stated "
        "here because a reader cannot tell the order from the figure alone."
    )
    if fired is None:
        return {
            "would_have_stopped": False,
            "calls_bought": len(calls),
            "pinned_before_this_was_computed": pinned,
        }
    return {
        "would_have_stopped": True,
        "arm": fired["arm"],
        "rule": fired["rule"],
        "would_have_stopped_after_calls": fired["after_calls"],
        "would_have_stopped_after_calls_in_arm": fired["after_calls_in_arm"],
        "answered_in_arm_at_that_point": fired["answered_in_arm"],
        "p_if_the_arm_met_the_limit": fired["p_if_the_arm_met_the_limit"],
        "calls_bought": len(calls),
        "calls_not_bought": len(calls) - fired["after_calls"],
        "pinned_before_this_was_computed": pinned,
        "reading": (
            "334 was not re-run and is not being re-run. This says what the "
            "rule would have done, so that the rule's cost and reach are on "
            "the record as a number rather than as a claim. It is not a "
            "finding about gpt-audio-1.5."
        ),
    }


def build() -> dict[str, Any]:
    raw = SOURCE.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    claims = _claims(data["claims"])
    calls = data["calls"]

    arms: dict[str, Any] = {}
    for arm in sorted({call["arm"] for call in calls}):
        published = (
            data["accuracy"]["stability"]
            if arm == "production"
            else data["arms"][arm]["stability"]
        )
        recomputed = probe.summarise(
            [c for c in calls if c["arm"] == arm], claims=claims
        )["stability"]
        arms[arm] = {"before": _before(published), "after": _after(recomputed)}

    return {
        "what_this_is": (
            "334's stability figures recomputed under 336's rule. A separate "
            "file under a separate name: 334's artifact is unchanged and its "
            "published numbers stand as published. Where the two disagree, "
            "336's is the one to use going forward and 334's is what was "
            "reported at the time."
        ),
        "source": {
            "file": SOURCE.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "written_by": "334, unmodified. This script opens it read-only.",
        },
        "produced_by": {
            "script": "batch-runner/scripts/reanalyse_audio_stability.py",
            "measure_script_sha256": hashlib.sha256(
                Path(probe.__file__).read_bytes()
            ).hexdigest(),
        },
        "what_changed": (
            "judge_error used to be a verdict like any other when asking "
            "whether the repeats agreed. Three non-answers were one distinct "
            "value and counted as agreement; one non-answer beside two equal "
            "answers was a second distinct value and counted as "
            "disagreement. Silence was being read as evidence in whichever "
            "direction it happened to fall."
        ),
        "primary_metric_changed": False,
        "primary_metric_note": (
            "334's primary metric is the per-claim majority vote and its "
            "exact McNemar p of 0.0654. Neither reads the stability block, "
            "so no headline figure in 334 moves. The corrected figures below "
            "are secondary, which is why fixing them now is a repair and not "
            "a re-analysis of a result."
        ),
        "arms": arms,
        "stop_rule_counterfactual": _counterfactual(calls),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Recompute and compare with the committed file; write nothing.",
    )
    args = parser.parse_args()

    payload = json.dumps(build(), indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not OUTPUT.exists():
            print(f"missing: {OUTPUT}", file=sys.stderr)
            return 1
        if OUTPUT.read_text(encoding="utf-8") != payload:
            print(
                f"{OUTPUT.name} is not what this script produces. "
                "Re-run without --check.",
                file=sys.stderr,
            )
            return 1
        print(f"{OUTPUT.name} matches.")
        return 0

    OUTPUT.write_text(payload, encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
