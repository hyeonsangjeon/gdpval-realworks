"""The stored A/B, re-read under the new contract, still says what it said.

``scripts/replay_audio_format_failures.py`` answers a question that cost 120
paid calls to raise and nothing to settle: of the 52 replies run 34008840627
published as ``provider_error:JSONDecodeError``, how many were the provider's
fault? The answer is none, and it was derivable from a file already in the
repository.

These tests pin the arithmetic against that file, so the claim in
``tasks/rebuilding_grading_task/`` cannot drift away from the code that
produced it. They are also the reason the next A/B does not need to buy this
answer again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from scripts.replay_audio_format_failures import (
    KIND_DECLINED,
    KIND_FORMAT,
    KIND_JUDGED,
    KIND_PROVIDER,
    classify_recorded_call,
    replay,
)

_MEASURED = (
    Path(__file__).resolve().parents[2]
    / "tasks"
    / "rebuilding_grading_task"
    / "328-audio-accuracy-measured.json"
)


@pytest.fixture(scope="module")
def measured() -> Dict[str, Any]:
    if not _MEASURED.is_file():
        pytest.skip(f"stored probe result not present: {_MEASURED}")
    return json.loads(_MEASURED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report(measured: Dict[str, Any]) -> Dict[str, Any]:
    return replay(measured)


# ── The classifier, on the shapes the run actually produced ──────────


def test_a_parse_failure_is_no_longer_blamed_on_the_provider() -> None:
    got = classify_recorded_call(
        {"verdict": "judge_error",
         "judge_error": "provider_error:JSONDecodeError"}
    )
    assert got["kind"] == KIND_FORMAT
    assert got["reason"] == "format_error:unparseable_json"
    # The old reading is kept beside the new one rather than overwritten:
    # this file is a re-reading of a published result, not a correction of it.
    assert got["old_reason"] == "provider_error:JSONDecodeError"


def test_a_real_provider_failure_is_still_the_providers() -> None:
    got = classify_recorded_call(
        {"verdict": "judge_error",
         "judge_error": "provider_error:APIConnectionError"}
    )
    assert got["kind"] == KIND_PROVIDER


@pytest.mark.parametrize("bad", ["true", "false", "no", "refuse",
                                 "analyze_audio"])
def test_the_five_out_of_vocabulary_strings_become_read_failures(
    bad: str,
) -> None:
    got = classify_recorded_call({"verdict": bad, "confidence": 0.9})
    assert got["kind"] == KIND_FORMAT
    assert got["reason"] == "format_error:verdict_not_in_vocabulary"
    assert got["verdict"] is None, "a rejected reply carries no verdict"


@pytest.mark.parametrize("good", ["pass", "fail", "partial"])
def test_a_usable_verdict_stays_usable(good: str) -> None:
    got = classify_recorded_call({"verdict": good, "confidence": 0.9})
    assert got["kind"] == KIND_JUDGED
    assert got["verdict"] == good


def test_a_model_shaped_judge_error_is_a_refusal_not_a_read_failure() -> None:
    """The third category, and the reason there are three.

    A sub-judge that answers ``judge_error`` has followed the contract and
    told us it could not hear enough. That is not the same event as a reply
    nobody could parse, and grouping them -- as ``unanswered`` did -- hides
    the only one of the two that says something about the audio.
    """
    got = classify_recorded_call({"verdict": "judge_error",
                                  "judge_error": "sub_judge_declined"})
    assert got["kind"] == KIND_DECLINED


# ── The whole file ───────────────────────────────────────────────────


def test_all_one_hundred_and_twenty_calls_are_accounted_for(
    report: Dict[str, Any],
) -> None:
    assert report["calls_replayed"] == 120
    total = sum(a["attempts"] for a in report["arms"].values())
    assert total == 120
    for arm in report["arms"].values():
        assert (
            arm["usable_verdicts"]
            + arm["read_failures"]
            + arm["provider_failures"]
            + arm["declined_to_judge"]
        ) == arm["attempts"], "every attempt lands in exactly one bucket"


def test_not_one_of_the_fifty_two_failures_was_the_providers(
    report: Dict[str, Any],
) -> None:
    """The finding. Published as ``provider_error`` 52 times; zero were.

    This is what makes the next step a prompt change rather than an
    infrastructure investigation, and it is why the A/B has to be re-bought
    rather than re-analysed.
    """
    assert sum(a["provider_failures"] for a in report["arms"].values()) == 0
    assert sum(a["read_failures"] for a in report["arms"].values()) == 70


def test_the_treatment_arm_never_once_met_the_contract(
    report: Dict[str, Any],
) -> None:
    """60 attempts, 0 usable verdicts, response rate exactly 0.

    The pre-registered analysis reported this arm's accuracy as 47.06% over
    17 "answers". Under the contract those 17 are not answers: 13 said
    ``true``, 2 ``false``, and one each ``refuse`` and ``analyze_audio``. An
    accuracy computed over them was measuring the scorer's ``verdict ==
    "pass"`` rule, not the model's hearing.
    """
    obs = report["arms"]["observation"]
    assert obs["attempts"] == 60
    assert obs["usable_verdicts"] == 0
    assert obs["response_rate_over_all_attempts"] == 0.0
    assert obs["accuracy_over_usable"] is None, (
        "with no usable verdicts there is no accuracy -- not a zero, "
        "and not a 47%"
    )
    assert obs["reasons"] == {
        "format_error:unparseable_json": 43,
        "format_error:verdict_not_in_vocabulary": 17,
    }


def test_the_control_arm_loses_exactly_one_reply_to_the_new_rule(
    report: Dict[str, Any],
) -> None:
    """51 answered becomes 50 usable, because one of them said ``no``.

    Worth pinning because it moves a published figure: control accuracy was
    reported as 54.90% over 51, and over the 50 that meet the contract it is
    56.0%. The old number is not withdrawn -- it was computed correctly under
    the rule in force at the time -- but the two must not be quoted as if
    they were the same measurement.
    """
    ctl = report["arms"]["production"]
    assert ctl["attempts"] == 60
    assert ctl["usable_verdicts"] == 50
    assert ctl["read_failures"] == 10
    assert ctl["response_rate_over_all_attempts"] == pytest.approx(
        50 / 60, abs=1e-9
    )
    assert ctl["accuracy_over_usable"] == pytest.approx(0.56, abs=1e-9)
    assert ctl["reasons"]["format_error:verdict_not_in_vocabulary"] == 1


def test_the_rejected_verdict_strings_are_counted_exactly(
    report: Dict[str, Any],
) -> None:
    assert report["verdict_strings_now_rejected"] == {
        "true": 13,
        "false": 2,
        "no": 1,
        "refuse": 1,
        "analyze_audio": 1,
    }


def test_response_rate_and_accuracy_are_always_reported_together(
    report: Dict[str, Any],
) -> None:
    """The brief's rule, held by the shape of the output.

    An accuracy without its denominator is how an arm that answered 17 times
    out of 60 came to be described as 47% accurate. Both keys are present for
    every arm, and the rate is always over *all attempts*.
    """
    for arm in report["arms"].values():
        assert "response_rate_over_all_attempts" in arm
        assert "accuracy_over_usable" in arm
        assert arm["response_rate_over_all_attempts"] == pytest.approx(
            arm["usable_verdicts"] / arm["attempts"], abs=1e-9
        )


def test_the_replay_does_not_touch_the_stored_result(
    measured: Dict[str, Any],
) -> None:
    """The source JSON is evidence and stays byte-identical.

    Re-reading a published result must not become re-writing one; the 185-task
    run's 31 audio items and every score already published depend on nobody
    doing that.
    """
    before = _MEASURED.read_bytes()
    replay(measured)
    assert _MEASURED.read_bytes() == before


def test_the_replay_makes_no_network_call(
    monkeypatch: pytest.MonkeyPatch, measured: Dict[str, Any]
) -> None:
    """Held mechanically, not by reading the source.

    The brief forbids spending new calls on a question the stored replies
    already answer. A socket opened anywhere under ``replay`` fails here.
    """
    import socket

    def _forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("replay attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)
    assert replay(measured)["calls_replayed"] == 120
