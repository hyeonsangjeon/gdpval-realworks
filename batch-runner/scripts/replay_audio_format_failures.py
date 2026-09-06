#!/usr/bin/env python3
"""Re-read the 120 stored audio replies under the new response contract.

Run 34008840627 (the 2026-09-06 prompt A/B) bought 120 audio calls and wrote
every outcome to ``tasks/rebuilding_grading_task/328-audio-accuracy-measured.
json``. This script reads that file and reports what the same 120 replies would
have been called under the contract added in
``core/perception/audio.py`` -- the vocabulary check, and the split between a
reply the model shaped wrongly and a call the provider failed.

**No API calls.** Everything here is arithmetic over a file that is already in
the repository, which is the point: the question "how much of that arm's
failure was format?" was answerable without buying anything, and buying a
second A/B before answering it would have repeated the same mistake.

**What this cannot do.** The raw reply text was never stored -- deliberately,
so model output does not sit in the repository -- so nothing here re-parses
JSON. It replays the *recorded* outcome of each call: the verdict string the
sub-judge returned, and the ``judge_error`` the old code assigned. For the 43
unparseable replies that means the classification is taken from the recorded
reason rather than re-derived; for the 17 that parsed, the verdict string is
in the record and the new validator's answer is computed from it directly.

Usage::

    python scripts/replay_audio_format_failures.py \\
        --measured tasks/rebuilding_grading_task/328-audio-accuracy-measured.json \\
        [--json out.json]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from math import comb
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

from core.perception.audio import (  # noqa: E402
    AUDIO_VERDICT_VOCABULARY,
    AudioEnvelopeError,
    _validated_audio_envelope,
)

#: How the old code recorded a reply it could not parse. Matched exactly rather
#: than by prefix: ``provider_error:`` also carries genuine outages, and the
#: whole point of this replay is that those two were indistinguishable.
_OLD_PARSE_FAILURE = "provider_error:JSONDecodeError"

# The three outcomes the owner's brief asks to be told apart, which the old
# record could not separate because all three arrived as ``judge_error``.
KIND_DECLINED = "declined_to_judge"        # the model said "I could not hear"
KIND_FORMAT = "format_error"              # the model answered in the wrong shape
KIND_PROVIDER = "provider_error"          # the call itself failed
KIND_JUDGED = "judged"                    # a usable verdict


def classify_recorded_call(call: Mapping[str, Any]) -> Dict[str, Any]:
    """What the new contract calls one stored reply.

    Returns the kind, the specific reason, and -- when the model produced a
    usable verdict -- that verdict. The old ``judge_error`` value is carried
    through so a reader can see both readings side by side.
    """
    verdict = str(call.get("verdict", ""))
    old_reason = call.get("judge_error") or ""

    if verdict == "judge_error":
        # Under the old code every one of these was a provider exception,
        # because a model-shaped ``judge_error`` was passed straight through
        # as a verdict and never landed here.
        if old_reason == _OLD_PARSE_FAILURE:
            return {
                "kind": KIND_FORMAT,
                "reason": "format_error:unparseable_json",
                "old_reason": old_reason,
                "verdict": None,
            }
        # A record written by the *new* code, where the model itself answered
        # ``judge_error``. Nothing in the 2026-09-06 file looks like this --
        # the marker did not exist yet -- but a later run replayed through
        # here will, and calling a refusal a provider outage is the exact
        # conflation this script was written to undo.
        if old_reason == "sub_judge_declined":
            return {
                "kind": KIND_DECLINED,
                "reason": "sub_judge_declined",
                "old_reason": old_reason,
                "verdict": "judge_error",
            }
        if old_reason.startswith("format_error:"):
            return {
                "kind": KIND_FORMAT,
                "reason": old_reason,
                "old_reason": old_reason,
                "verdict": None,
            }
        return {
            "kind": KIND_PROVIDER,
            "reason": old_reason or "provider_error:unknown",
            "old_reason": old_reason,
            "verdict": None,
        }

    # The reply parsed. Ask the new validator what it makes of the values.
    # ``partial_score`` was not stored per call, so the envelope is rebuilt
    # from the fields that were: a validator run on a partial record could
    # only ever report a missing-field error that the real reply may not have
    # had, so the numbers are filled with in-range placeholders and the check
    # is confined to the one field this replay can honestly speak for.
    envelope = {
        "verdict": verdict,
        "partial_score": 1.0 if verdict == "pass" else 0.0,
        "confidence": float(call.get("confidence") or 0.0),
    }
    try:
        checked, _, _ = _validated_audio_envelope(envelope)
    except AudioEnvelopeError as exc:
        return {
            "kind": KIND_FORMAT,
            "reason": f"format_error:{exc.kind}",
            "detail": exc.detail,
            "old_reason": old_reason,
            "verdict": None,
        }
    if checked == "judge_error":
        return {
            "kind": KIND_DECLINED,
            "reason": "sub_judge_declined",
            "old_reason": old_reason,
            "verdict": checked,
        }
    return {
        "kind": KIND_JUDGED,
        "reason": None,
        "old_reason": old_reason,
        "verdict": checked,
    }


def _exact_mcnemar(b: int, c: int) -> Optional[float]:
    """Two-sided exact binomial McNemar, ``None`` at zero discordance.

    ``None`` rather than 1.0: with no discordant pairs there is no test, and
    reporting a p of 1.0 would read as "measured, and no difference" when the
    truth is "nothing to measure".
    """
    n = b + c
    if n == 0:
        return None
    tail = sum(comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2.0 * tail / (2 ** n))


def _rate(numerator: int, denominator: int) -> Optional[float]:
    return None if denominator == 0 else numerator / denominator


def replay(measured: Mapping[str, Any]) -> Dict[str, Any]:
    calls = list(measured.get("calls") or [])
    holds = {c["claim_id"]: bool(c["holds"]) for c in measured.get("claims", [])}
    arms = sorted({str(c.get("arm")) for c in calls})

    per_arm: Dict[str, Dict[str, Any]] = {}
    replayed: List[Dict[str, Any]] = []

    for call in calls:
        verdict_now = classify_recorded_call(call)
        replayed.append({**{k: call.get(k) for k in
                            ("arm", "claim_id", "repeat", "verdict")},
                         "now": verdict_now})

    for arm in arms:
        rows = [r for r in replayed if r["arm"] == arm]
        kinds = collections.Counter(r["now"]["kind"] for r in rows)
        reasons = collections.Counter(
            r["now"]["reason"] for r in rows if r["now"]["reason"]
        )
        judged = [r for r in rows if r["now"]["kind"] == KIND_JUDGED]
        correct = sum(
            1 for r in judged
            if (r["now"]["verdict"] == "pass") == holds[r["claim_id"]]
        )
        attempts = len(rows)
        per_arm[arm] = {
            "attempts": attempts,
            # The brief asks for both, together: an arm that answers three
            # times out of sixty can post a fine accuracy on those three.
            "usable_verdicts": len(judged),
            "response_rate_over_all_attempts": _rate(len(judged), attempts),
            "accuracy_over_usable": _rate(correct, len(judged)),
            "kinds": dict(kinds),
            "reasons": dict(reasons),
            # The three the old record could not separate.
            "declined_to_judge": kinds.get(KIND_DECLINED, 0),
            "read_failures": kinds.get(KIND_FORMAT, 0),
            "provider_failures": kinds.get(KIND_PROVIDER, 0),
            "genuine_negative_verdicts": sum(
                1 for r in judged if r["now"]["verdict"] in ("fail", "partial")
            ),
        }

    # What the old code called these same replies, for the side-by-side.
    old_unanswered = collections.Counter(
        (str(c.get("arm")), str(c.get("judge_error") or ""))
        for c in calls if c.get("verdict") == "judge_error"
    )

    # The out-of-vocabulary strings, counted. These are the ones that used to
    # travel downstream as verdicts.
    out_of_vocab = collections.Counter(
        str(c.get("verdict")) for c in calls
        if str(c.get("verdict")) not in AUDIO_VERDICT_VOCABULARY
    )

    return {
        "what_this_is": (
            "The 120 stored replies of run 34008840627, re-read under the "
            "response contract in core/perception/audio.py. No API calls; the "
            "raw reply text was never stored, so recorded outcomes are "
            "reclassified rather than re-parsed."
        ),
        "source_pins": dict(measured.get("pins") or {}),
        "calls_replayed": len(calls),
        "arms": per_arm,
        "verdict_strings_now_rejected": dict(out_of_vocab),
        "old_unanswered_reasons": {
            f"{arm}|{reason}": n for (arm, reason), n in old_unanswered.items()
        },
        "note_on_interpretation": (
            "A read failure is a prompt defect and a provider failure is an "
            "outage. Both used to be published as provider_error, so the A/B "
            "could not tell which it had bought."
        ),
    }


def render(report: Mapping[str, Any]) -> str:
    out: List[str] = []
    pins = report.get("source_pins") or {}
    out.append(f"replayed {report['calls_replayed']} stored calls  "
               f"(no API calls)")
    out.append(f"  model={pins.get('audio_model')}  "
               f"config={pins.get('config')}  "
               f"repeats={pins.get('repeats')}  claims={pins.get('claims')}")
    out.append("")
    header = (f"{'arm':<14}{'attempts':>9}{'usable':>8}{'resp.rate':>11}"
              f"{'accuracy':>10}{'read.fail':>11}{'provider':>10}{'declined':>10}")
    out.append(header)
    out.append("-" * len(header))
    for arm, s in report["arms"].items():
        rr = s["response_rate_over_all_attempts"]
        acc = s["accuracy_over_usable"]
        out.append(
            f"{arm:<14}{s['attempts']:>9}{s['usable_verdicts']:>8}"
            f"{('%.3f' % rr) if rr is not None else '  n/a':>11}"
            f"{('%.3f' % acc) if acc is not None else '  n/a':>10}"
            f"{s['read_failures']:>11}{s['provider_failures']:>10}"
            f"{s['declined_to_judge']:>10}"
        )
    out.append("")
    out.append("verdict strings the contract now rejects "
               "(these used to travel downstream as verdicts):")
    for value, n in sorted(report["verdict_strings_now_rejected"].items(),
                           key=lambda kv: -kv[1]):
        out.append(f"    {value:<20} {n:>3}")
    if not report["verdict_strings_now_rejected"]:
        out.append("    (none)")
    out.append("")
    out.append("per-arm reason breakdown:")
    for arm, s in report["arms"].items():
        out.append(f"  {arm}")
        for reason, n in sorted(s["reasons"].items(), key=lambda kv: -kv[1]):
            out.append(f"    {reason:<42} {n:>3}")
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--measured",
        default="tasks/rebuilding_grading_task/328-audio-accuracy-measured.json",
        help="the stored probe result to replay (read-only)",
    )
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the report as JSON here")
    args = ap.parse_args(argv)

    path = Path(args.measured)
    if not path.is_file():
        print(f"error: no such file: {path}", file=sys.stderr)
        return 2
    measured = json.loads(path.read_text(encoding="utf-8"))
    report = replay(measured)
    print(render(report))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
