"""The format check has to be able to fail, or it is decoration.

`verify_format_pilot_run.py` judges 344 §6. It was written before the run it
will judge, which is the only way the bar is the plan's rather than the
result's -- and it means nothing has ever made it say no. A checker that has
only ever passed is indistinguishable from a checker that cannot fail.

So this file starts from **337's real committed report**, relabels it as the
V3 pilot, and confirms the checker reads the numbers that are actually in it
as ``format_lost``. 337's observation arm came back 1 of 5 readable; a checker
that calls that anything else would have passed the run 344 exists because of.

Then it breaks a working run in each way 344 §6 names, and one way it does
not name but that would quietly destroy the comparison:

* the candidate misses by one -- 4 of 5, the number most likely to be argued
  into a pass;
* the control arm collapses, which makes the run say nothing in either
  direction rather than making the candidate look good;
* fewer than ten requests go out;
* a call retries, so the two arms were not asked the same number of times;
* the header registered in the document is not the one the run sent;
* the grader moved between registration and dispatch;
* a paid run reports its cost as exactly ``0``.

Each break has to be caught by the condition that claims to cover it, not
merely by *some* condition -- a candidate miss reported as "the run stopped
early" sends the reader to the wrong file and leaves the candidate open.

Everything here runs offline against committed artifacts. No model is called
and nothing goes to the network.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = REPO_ROOT / "batch-runner"
SCRIPTS = BATCH_RUNNER / "scripts"
for entry in (str(BATCH_RUNNER), str(SCRIPTS)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

SCRIPT_PATH = SCRIPTS / "verify_format_pilot_run.py"

#: 337's own artifact, committed. Starting from a real report rather than a
#: hand-built one is deliberate: a fixture written by the same person as the
#: checker agrees with the checker by construction, and the field this whole
#: experiment turns on -- ``unanswered_kind`` -- is one nobody would think to
#: put in a mock at the right rate.
REAL_337 = (
    REPO_ROOT / "tasks" / "rebuilding_grading_task"
    / "337-audio-accuracy-measured.json"
)

PREREG = (
    REPO_ROOT / "tasks" / "rebuilding_grading_task"
    / "344-the-order-with-no-destination.md"
)


def _load_checker():
    """Import the script by path -- ``scripts/`` is not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "verify_format_pilot_run", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


@pytest.fixture(scope="module")
def real_337() -> dict[str, Any]:
    return json.loads(REAL_337.read_text(encoding="utf-8"))


def _relabel_as_v3(report: dict[str, Any]) -> dict[str, Any]:
    """337's report, wearing V3's pins and a ledger, and nothing else changed.

    The verdicts, the ``unanswered_kind`` values and the arm membership are
    337's measured ones. Only the identity the checker keys on is moved, so
    what is being tested is how the checker reads *real* numbers.
    """
    out = copy.deepcopy(report)
    out["pins"]["observation_header_name"] = checker.CANDIDATE_HEADER_NAME
    out["pins"]["observation_header_sha256"] = checker.candidate_pin(PREREG)
    out["pins"]["grader_source_sha256"] = checker.grader_pin(PREREG)
    cost = dict(out.get("cost") or {})
    cost["ledger"] = {"path": "format-pilot-v3-measured.sqlite3", "rows": 10}
    cost["receipt"] = {"status": "partial"}
    cost["estimated_cost_usd"] = None
    out["cost"] = cost
    for call in out["calls"]:
        call["wire"] = {"requests": 1}
    return out


def _make_readable(report: dict[str, Any], arm: str, count: int) -> None:
    """Set exactly ``count`` of ``arm``'s calls to a readable envelope."""
    calls = [c for c in report["calls"] if c["arm"] == arm]
    for index, call in enumerate(calls):
        if index < count:
            call["unanswered_kind"] = None
            call["verdict"] = "fail"
        else:
            call["unanswered_kind"] = "read_failure"
            call["verdict"] = "judge_error"


@pytest.fixture
def held(real_337: dict[str, Any]) -> dict[str, Any]:
    """A run that should pass: both arms readable 5 of 5, ten requests."""
    report = _relabel_as_v3(real_337)
    _make_readable(report, checker.CONTROL_ARM, 5)
    _make_readable(report, checker.CANDIDATE_ARM, 5)
    return report


def _check(tmp_path: Path, report: dict[str, Any]) -> dict[str, Any]:
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return checker.check(path, PREREG)


def _condition(outcome: dict[str, Any], number: int) -> dict[str, Any]:
    for entry in outcome["conditions"]:
        if entry["condition"] == number:
            return entry
    raise AssertionError(f"condition {number} is not in the outcome")


# ── the baseline: it can say yes ─────────────────────────────────────────


def test_a_clean_run_is_format_held(tmp_path: Path, held: dict[str, Any]) -> None:
    outcome = _check(tmp_path, held)
    assert outcome["verdict"] == checker.VERDICT_FORMAT_HELD
    assert outcome["counts"]["failed"] == 0
    assert outcome["counts"]["unanswerable"] == 0
    assert outcome["arms"][checker.CANDIDATE_ARM]["readable"] == 5


def test_the_exit_status_follows_the_verdict(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """0 for held and rehearsal, 1 for lost and inconclusive, 2 for refused."""
    path = tmp_path / "held.json"
    path.write_text(json.dumps(held), encoding="utf-8")
    assert checker.main([str(path), "--prereg", str(PREREG)]) == 0

    lost = copy.deepcopy(held)
    _make_readable(lost, checker.CANDIDATE_ARM, 4)
    lost_path = tmp_path / "lost.json"
    lost_path.write_text(json.dumps(lost), encoding="utf-8")
    assert checker.main([str(lost_path), "--prereg", str(PREREG)]) == 1

    dry = copy.deepcopy(held)
    dry["measured"] = False
    dry_path = tmp_path / "dry.json"
    dry_path.write_text(json.dumps(dry), encoding="utf-8")
    assert checker.main([str(dry_path), "--prereg", str(PREREG)]) == 0


# ── 337's real numbers ───────────────────────────────────────────────────


def test_337s_own_arm_counts_read_as_format_lost(
    tmp_path: Path, real_337: dict[str, Any]
) -> None:
    """The measured 1-of-5 that started all of this is a loss, not a near miss."""
    outcome = _check(tmp_path, _relabel_as_v3(real_337))

    assert outcome["arms"][checker.CANDIDATE_ARM]["readable"] == 1
    assert outcome["arms"][checker.CONTROL_ARM]["readable"] == 5
    assert outcome["verdict"] == checker.VERDICT_FORMAT_LOST
    assert _condition(outcome, 6)["result"] == checker.RESULT_FAIL

    # And the usable count is reported without being gated on: 337's
    # observation arm produced no verdict at all.
    assert outcome["arms"][checker.CANDIDATE_ARM][
        "usable_reported_not_gated"
    ] == 0


def test_337s_report_is_refused_rather_than_judged() -> None:
    """Unrelabelled, 337's file is another experiment and is not scored."""
    with pytest.raises(checker.ReportUnreadable) as caught:
        checker.check(REAL_337, PREREG)
    assert "SPEECH_OBSERVATION_HEADER_V2" in str(caught.value)


# ── the ways it must say no ──────────────────────────────────────────────


def test_a_candidate_that_misses_by_one_is_lost(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """4 of 5 is the number most likely to be argued into a pass. It is not."""
    _make_readable(held, checker.CANDIDATE_ARM, 4)
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_FORMAT_LOST
    entry = _condition(outcome, 6)
    assert entry["result"] == checker.RESULT_FAIL
    assert entry["data"]["readable"] == 4
    assert entry["data"]["required"] == 5


def test_a_declined_envelope_still_counts_as_readable(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """The gate is the envelope, not the answer inside it.

    A judge that returns well-formed JSON saying it will not judge has kept
    the format contract. Scoring that as a format failure would have made
    337's observation arm 0 of 5 rather than the 1 of 5 it measured, and would
    close a candidate that never broke an envelope.
    """
    for call in held["calls"]:
        if call["arm"] == checker.CANDIDATE_ARM:
            call["unanswered_kind"] = "declined_to_judge"
            call["verdict"] = "judge_error"
    outcome = _check(tmp_path, held)

    assert outcome["arms"][checker.CANDIDATE_ARM]["readable"] == 5
    assert outcome["arms"][checker.CANDIDATE_ARM][
        "usable_reported_not_gated"
    ] == 0
    assert outcome["verdict"] == checker.VERDICT_FORMAT_HELD


def test_a_collapsed_control_arm_is_inconclusive_not_a_win(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """A broken control must not launder a perfect candidate into a pass."""
    _make_readable(held, checker.CONTROL_ARM, 2)
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert _condition(outcome, 5)["result"] == checker.RESULT_FAIL
    # The candidate's own number is recorded, and explicitly not read.
    candidate = _condition(outcome, 6)
    assert candidate["result"] == checker.RESULT_UNANSWERABLE
    assert candidate["unanswerable_because"] == (
        checker.UNANSWERABLE_CONTROL_COLLAPSED
    )
    assert candidate["data"]["readable"] == 5


def test_a_collapsed_control_arm_is_inconclusive_even_when_the_candidate_lost(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """Closing the candidate needs a working comparison, not just a bad count."""
    _make_readable(held, checker.CONTROL_ARM, 1)
    _make_readable(held, checker.CANDIDATE_ARM, 1)
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert outcome["verdict"] != checker.VERDICT_FORMAT_LOST


def test_a_short_run_is_inconclusive(tmp_path: Path, held: dict[str, Any]) -> None:
    """Eight requests out of ten is not eight tenths of an answer."""
    held["calls"] = held["calls"][:8]
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    entry = _condition(outcome, 3)
    assert entry["result"] == checker.RESULT_FAIL
    assert entry["data"]["requests_sent"] == 8


def test_an_early_stop_is_inconclusive(tmp_path: Path, held: dict[str, Any]) -> None:
    held["stopped"] = "wall_clock"
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert _condition(outcome, 3)["result"] == checker.RESULT_FAIL


def test_a_retried_call_is_caught_by_the_request_condition(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """SDK retries are pinned to 0, so two requests on one call is a breach.

    It also silently doubles what one arm was asked, which is the part that
    would survive into the numbers if nothing looked.
    """
    held["calls"][0]["wire"] = {"requests": 2}
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    entry = _condition(outcome, 3)
    assert entry["result"] == checker.RESULT_FAIL
    assert entry["data"]["calls_that_retried"][0]["requests"] == 2
    assert "retries" in entry["detail"]


def test_a_missing_wire_record_is_not_read_as_ten_requests(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """No record of what went out is not a record of ten going out."""
    for call in held["calls"]:
        call.pop("wire", None)
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert _condition(outcome, 3)["data"]["requests_sent"] is None


def test_a_substituted_header_is_caught(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """The name can say V3 while the string that went out is something else."""
    held["pins"]["observation_header_sha256"] = "0" * 64
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert _condition(outcome, 1)["result"] == checker.RESULT_FAIL


def test_a_grader_that_moved_is_caught(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """core/ moving between registration and dispatch invalidates the run.

    This is not hypothetical: #467 moved the grader fingerprint while 344 was
    being written, which is why §2 carries the value it does.
    """
    held["pins"]["grader_source_sha256"] = "1" * 64
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    entry = _condition(outcome, 2)
    assert entry["result"] == checker.RESULT_FAIL
    assert entry["data"]["prereg"] == checker.grader_pin(PREREG)


def test_the_arms_have_to_have_run_the_same_claims(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    for call in held["calls"]:
        if call["arm"] == checker.CANDIDATE_ARM:
            call["claim_id"] = "something_else"
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert _condition(outcome, 4)["result"] == checker.RESULT_FAIL


def test_a_missing_ledger_is_caught(tmp_path: Path, held: dict[str, Any]) -> None:
    """344 §2 makes --cost-ledger required; a run without one is not it."""
    held["cost"]["ledger"] = None
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert _condition(outcome, 7)["result"] == checker.RESULT_FAIL


def test_a_paid_run_reporting_zero_dollars_is_caught(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """gpt-audio-1.5 is unpriced, so the honest amount is null and never 0."""
    held["cost"]["estimated_cost_usd"] = 0
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    entry = _condition(outcome, 7)
    assert entry["result"] == checker.RESULT_FAIL
    assert "0" in entry["detail"]


# ── the rehearsal must not be able to answer ─────────────────────────────


def test_a_rehearsal_cannot_report_format_held(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """The stub's canned replies are not evidence about gpt-audio-1.5.

    This is the substitution that would make the whole pre-registration
    pointless: run it free, get five clean envelopes from the stub, and
    report that the candidate held.
    """
    held["measured"] = False
    outcome = _check(tmp_path, held)

    assert outcome["verdict"] == checker.VERDICT_REHEARSAL_OK
    assert outcome["verdict"] != checker.VERDICT_FORMAT_HELD
    for number in (5, 6):
        entry = _condition(outcome, number)
        assert entry["result"] == checker.RESULT_UNANSWERABLE
        assert entry["unanswerable_because"] == checker.UNANSWERABLE_REHEARSAL


def test_a_rehearsal_that_broke_is_not_rehearsal_ok(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """Free does not mean waved through -- clearing a dispatch is the whole job.

    ``rehearsal_ok`` is the word §0 ticks a precondition on. A rehearsal that
    sent three requests for one call has shown the request discipline does not
    hold, which is the opposite of cleared, so it must not be able to hand
    that word back.
    """
    held["measured"] = False
    held["calls"][0]["wire"] = {"requests": 3}
    outcome = _check(tmp_path, held)

    assert _condition(outcome, 3)["result"] == checker.RESULT_FAIL
    assert outcome["verdict"] == checker.VERDICT_INCONCLUSIVE
    assert outcome["verdict"] != checker.VERDICT_REHEARSAL_OK


def test_a_broken_rehearsal_says_free_rather_than_spent(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """Inconclusive reads two ways and only one of them is true here."""
    held["measured"] = False
    held["calls"] = held["calls"][:6]
    text = checker.render(_check(tmp_path, held))

    assert "Nothing was spent" in text
    assert "spent money" not in text


def test_a_rehearsal_that_broke_does_not_exit_zero_quietly(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """A red condition has to reach the shell, or CI will not see it."""
    held["measured"] = False
    held["calls"] = held["calls"][:4]
    path = tmp_path / "broken-rehearsal.json"
    path.write_text(json.dumps(held), encoding="utf-8")

    assert checker.main([str(path), "--prereg", str(PREREG)]) == 1


# ── the bar itself ───────────────────────────────────────────────────────


def test_the_thresholds_are_the_documents(tmp_path: Path) -> None:
    """5 and 4, read out of 344 §6 rather than out of this file's memory."""
    text = PREREG.read_text(encoding="utf-8")
    assert "`format_held`" in text
    assert "`format_lost`" in text
    assert checker.CANDIDATE_READABLE_REQUIRED == 5
    assert checker.CONTROL_READABLE_REQUIRED == 4
    assert checker.PLANNED_CALLS == 10
    assert checker.PLANNED_ITEMS == 5
    # No knob turns a miss into a pass.
    assert "--bar" not in checker.__doc__
    assert not any(
        name.lower().startswith(("allow_", "tolerate_", "min_readable_pct"))
        for name in dir(checker)
    )


def test_declined_is_deliberately_not_an_unreadable_kind() -> None:
    assert checker.UNREADABLE_KINDS == ("read_failure", "provider_failure")
    assert "declined_to_judge" not in checker.UNREADABLE_KINDS


def test_the_checker_makes_no_network_call(monkeypatch, tmp_path, held) -> None:
    """It reads two files. Anything else would make it part of the run."""
    import socket

    def _refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the format checker tried to open a socket")

    monkeypatch.setattr(socket, "socket", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    outcome = _check(tmp_path, held)
    assert outcome["verdict"] == checker.VERDICT_FORMAT_HELD


def test_a_prereg_with_no_candidate_row_is_refused_not_compared(
    tmp_path: Path, held: dict[str, Any]
) -> None:
    """337's own document has no candidate row, and is not 344.

    Reading an absent pin as ``None`` and comparing would report "condition 1
    failed", which sends the reader to the run when the mistake was the file
    on the command line.
    """
    report = tmp_path / "report.json"
    report.write_text(json.dumps(held), encoding="utf-8")
    old_doc = (
        REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "337-format-safe-observation-pilot.md"
    )
    assert old_doc.exists(), "337's pre-registration moved; update this path"

    with pytest.raises(checker.ReportUnreadable, match="pins no candidate"):
        checker.check(report, old_doc)
    assert checker.main([str(report), "--prereg", str(old_doc)]) == 2


def test_the_checker_is_a_file_this_repository_carries() -> None:
    """344 §0 ticks a precondition on this script having been merged.

    ``.gitignore`` ignores all of ``batch-runner/scripts/`` and re-admits
    files one ``!`` line at a time, so a new one is invisible by default:
    ``git add -A`` skips it without a word and the branch looks complete.
    Here that failure has a specific shape -- the gate that stands between a
    plan and a paid dispatch would be ticked on a file only this working copy
    has, and nobody reviewing the run could re-derive its verdict.

    Asks git what is tracked rather than reading the allowlist, because the
    allowlist is the thing that goes stale.
    """
    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        "verify_format_pilot_run.py is not tracked, so a clone of this "
        "repository cannot re-run 344's verdict. Add a '!' line for it in "
        f".gitignore. git said: {tracked.stderr.strip()!r}"
    )
