"""339 — what the ten calls bought, and what they refuse to buy next.

337 registered a ten-call format pilot: does a candidate observation header
come back as readable JSON? §5 fixed the bar before any money moved --
**5/5 for the candidate, 4/5 or better for the production control** -- and
named what each outcome does next. The candidate returned readable JSON on
one call of five. The control returned five of five, so the run is valid and
what failed is the candidate. 338's 120 calls are therefore not bought.

That last sentence is the reason this file exists. A pilot that fails its own
bar is worth exactly as much as the discipline that holds the bar afterwards,
and the pressure at that moment is to round 1/5 up, to blame the deployment,
or to merge the pilot's ten calls into the comparison and call it 130. Each
of those is a line in the document, and each has a test here.

Everything reads committed files read-only. Nothing here calls a model, and
none of 331/334/335/336's published numbers are recomputed or overwritten --
the two that are touched at all are asserted to be *unchanged*.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_audio_grading_accuracy as probe  # noqa: E402


TASKS = (
    Path(__file__).resolve().parents[2] / "tasks" / "rebuilding_grading_task"
)

_REPORT = TASKS / "339-the-sentence-that-changed-nothing.md"
_PILOT = TASKS / "337-format-safe-observation-pilot.md"
_MAIN = TASKS / "338-format-safe-observation-ab.md"
_MEASURED = TASKS / "337-audio-accuracy-measured.json"
_DELIVERY = TASKS / "337-audio-accuracy-measured-delivery.json"


def _artifact() -> dict:
    return json.loads(_MEASURED.read_text(encoding="utf-8"))


def _delivery() -> dict:
    return json.loads(_DELIVERY.read_text(encoding="utf-8"))


def _report() -> str:
    return _REPORT.read_text(encoding="utf-8")


def _readable(call: dict) -> bool:
    """Did a JSON envelope come back from this call?

    Not "was it a usable verdict". ``sub_judge_declined`` is set only after
    the envelope has been parsed and its five keys validated, so a declining
    reply is one that arrived in the required format and said no inside it.
    A call whose ``judge_error`` is ``format_error:unparseable_json`` never
    got that far. §5 counts the envelope, so this counts the envelope.

    Read off ``judge_error`` rather than ``outcome``: ``outcome`` scores the
    verdict against the manifest, and both of these land in its ``unanswered``
    bucket together.
    """
    return call["judge_error"] != "format_error:unparseable_json"


# --------------------------------------------------------------------------
# The artifact is the one the report read.
# --------------------------------------------------------------------------


def test_the_report_reads_the_artifact_the_paid_run_wrote() -> None:
    """A number in prose that no file backs is a number nobody can check.

    The pilot is not run again -- 337 §7 -- and the CI artifact expires, so
    these two files are the only surviving record of ten paid calls. If they
    are ever regenerated or hand-edited, every figure below detaches from
    what was bought, and this is where that shows up.
    """
    assert _MEASURED.exists() and _DELIVERY.exists()

    artifact = _artifact()
    assert artifact["measured"] is True, "a dry run cannot report a verdict"
    assert artifact["corpus"] == "speech"
    assert artifact["calls_planned"] == 10
    assert len(artifact["calls"]) == 10
    assert artifact["stopped"] is None, (
        "a stopped run's surviving pairs are an order-filtered sample; 337 §5 "
        "forbids reading a verdict off one"
    )

    # The report names both files, so a reader can get from the prose to the
    # bytes without being told where to look.
    text = _report()
    assert "337-audio-accuracy-measured.json" in text
    assert "337-audio-accuracy-measured-delivery.json" in text


def test_the_pins_are_the_ones_the_pre_registration_fixed() -> None:
    """What ran has to be what 337 §2 said would run.

    The document is read at dispatch time, so these were checked before the
    calls went out. Checking them again here is not redundant: it is the only
    check that survives the workflow run, and it is what makes the artifact
    quotable as evidence for *that* pre-registration rather than some run.
    """
    pins = _artifact()["pins"]

    assert pins["audio_model"] == "gpt-audio-1.5"
    assert pins["audio_deployment"] == "gpt-audio-1.5"
    assert pins["provider"] == "azure_openai"
    assert pins["config"] == "gold_audio_repeat_v2_sol_max.yaml"
    assert pins["repeats"] == 1, "337 §2 fixes one repeat; three is 338's plan"
    assert sorted(pins["prompt_arms"]) == ["observation", "production"]
    assert pins["claims"] == 5
    assert (pins["true_claims"], pins["false_claims"]) == (3, 2)
    assert pins["clips"] == 5

    # The candidate header, by name and by content.
    assert pins["observation_header_name"] == "SPEECH_OBSERVATION_HEADER_V2"
    assert pins["observation_header_sha256"] == hashlib.sha256(
        probe.SPEECH_OBSERVATION_HEADER_V2.encode("utf-8")
    ).hexdigest()

    # And the grader fingerprint the run recomputed before calling the model.
    assert pins["grader_source_sha256"] == probe.grader_pin_stated_in(_PILOT)


def test_the_run_stayed_inside_the_ceiling_it_registered() -> None:
    """Ten calls planned, ten placed, twelve allowed.

    337 §5 says an eleventh request means the plan or the repeat path is
    wrong -- and that the answer to that is to stop and re-plan, not to raise
    the ceiling. So the interesting assertion is not ``<= 12``; it is ``==
    10``, which is the number that would have caught it.
    """
    artifact = _artifact()
    calls = artifact["calls"]

    requests = sum(call["api_call_count"] for call in calls)
    assert requests == 10 == artifact["calls_planned"]
    assert requests < probe.SPEECH_REQUEST_CAPS[probe.SPEECH_FORMAT_PILOT_KIND]

    # One create per call, which is what makes the ceiling mean anything.
    assert {call["api_call_count"] for call in calls} == {1}

    # Five claims, two arms, one repeat each -- recomputed, not quoted.
    assert len({call["claim_id"] for call in calls}) == 5
    assert {call["arm"] for call in calls} == {"production", "observation"}
    assert {call["repeat"] for call in calls} == {1}
    assert len({(c["arm"], c["claim_id"]) for c in calls}) == 10


# --------------------------------------------------------------------------
# The verdict on §5, recomputed from the calls.
# --------------------------------------------------------------------------


def test_the_candidate_missed_the_bar_and_the_control_cleared_it() -> None:
    """The whole decision, recomputed from per-call outcomes.

    Both halves matter and they are not the same claim. The candidate's 1/5
    is the failure. The control's 5/5 is what makes it *the candidate's*
    failure rather than a broken deployment -- 337 §5 calls that second row a
    validity check on the run, not a bar for the candidate, and without it
    this run would say nothing at all.
    """
    by_arm: dict[str, list[dict]] = {"production": [], "observation": []}
    for call in _artifact()["calls"]:
        by_arm[call["arm"]].append(call)

    production = sum(_readable(c) for c in by_arm["production"])
    observation = sum(_readable(c) for c in by_arm["observation"])

    assert (production, observation) == (5, 1)

    # §5's two rows, as the document states them.
    assert production >= 4, "the control failed; this run would be invalid"
    assert observation < 5, (
        "the candidate cleared the bar -- then 338 is the next document and "
        "339 is the wrong report entirely"
    )

    text = _report()
    assert "**1/5**" in text and "**5/5**" in text


def test_readable_json_and_a_usable_verdict_are_counted_separately() -> None:
    """One reply parsed. Zero replies answered. The report says both.

    Collapsing them is tempting in either direction -- 0/5 reads worse and
    1/5 reads more careful -- and either collapse loses the distinction that
    ``sub_judge_declined`` exists to record. §5 counts envelopes, so 1/5 is
    the number the bar is judged against, and 0/5 is the number that says
    what the run learned about verdicts. The report carries both.
    """
    observation = [
        call for call in _artifact()["calls"] if call["arm"] == "observation"
    ]

    unparseable = [
        c
        for c in observation
        if c["judge_error"] == "format_error:unparseable_json"
    ]
    declined = [
        c for c in observation if c["judge_error"] == "sub_judge_declined"
    ]

    assert len(unparseable) == 4
    assert len(declined) == 1
    assert declined[0]["claim_id"] == "column_third"

    # Both land in the same `unanswered` bucket, which is exactly why the
    # distinction has to be read off `judge_error` and stated in the report.
    assert {c["outcome"] for c in observation} == {"unanswered"}
    assert declined[0]["unanswered_kind"] == "declined_to_judge"
    assert {c["unanswered_kind"] for c in unparseable} == {"read_failure"}

    # Not one observation call produced a pass/fail. The verdict slot is
    # filled with the literal `judge_error` rather than left empty -- and
    # `judge_error` is itself a member of the vocabulary, so an emptiness
    # test would have passed on any string and a membership test would have
    # passed on this one. What has to be absent is a *scoring* verdict.
    assert {c["verdict"] for c in observation} == {"judge_error"}
    scoring = set(probe.AUDIO_VERDICT_VOCABULARY) - {"judge_error"}
    assert scoring == {"pass", "fail", "partial"}
    assert not scoring & {c["verdict"] for c in observation}

    text = _report()
    assert "**1 / 5**" in text, "the envelope count, which §5 judges"
    assert "**0 / 5**" in text, "the verdict count, which is what it bought"


def test_the_candidate_sentence_was_actually_delivered() -> None:
    """The first thing to suspect is that the header never went out.

    It went out. The artifact keeps prompt hashes rather than prompt bodies,
    so the evidence is length: every observation prompt is exactly 898
    characters longer than its production twin, and 898 - 739 is the 159 the
    candidate sentence adds to the header 334 bought. Five pairs, no
    exceptions -- a call that missed the header would show 739.
    """
    by_key: dict[tuple[str, str], dict] = {
        (call["arm"], call["claim_id"]): call for call in _artifact()["calls"]
    }
    claims = {claim for _, claim in by_key}

    deltas = {
        by_key[("observation", claim)]["wire"]["prompt_chars"]
        - by_key[("production", claim)]["wire"]["prompt_chars"]
        for claim in claims
    }
    assert deltas == {898}

    # 159 of those 898 are the candidate; the rest is the header 334 bought.
    candidate = len(probe.SPEECH_OBSERVATION_HEADER_V2) - len(
        probe.SPEECH_OBSERVATION_HEADER
    )
    assert candidate == 159
    assert 898 - candidate == 739, "334 §1's figure, which this builds on"

    # Every prompt distinct: no call reused another's text.
    assert len({c["wire"]["prompt_sha256"] for c in by_key.values()}) == 10


def test_the_audio_left_this_process_and_both_arms_got_the_same_bytes() -> None:
    """A failing arm makes it easy to assume the sound never went.

    If the observation arm had been sent different audio -- or none -- its
    failure would say nothing about the header. One digest per clip across
    both arms is what rules that out, and it is a separate file from the
    verdicts because it answers a separate question.
    """
    delivery = _delivery()["delivery"]

    assert delivery["measured"] is True
    assert delivery["calls_inspected"] == 10
    assert delivery["calls_carrying_audio"] == 10
    assert delivery["calls_without_audio"] == []
    assert delivery["clips_with_more_than_one_digest"] == []
    assert delivery["clips_whose_sent_duration_differs"] == []

    # One digest per clip, five clips, ten calls: the arms shared bytes.
    assert len(delivery["digests_per_clip"]) == 5
    assert all(len(v) == 1 for v in delivery["digests_per_clip"].values())

    # 330's format, unchanged.
    assert delivery["sent_formats"] == ["wav"]
    assert delivery["sent_sample_rates_hz"] == [16000]
    assert delivery["sent_channels"] == [1]
    assert delivery["response_models"] == ["gpt-audio-1.5"]
    assert delivery["audio_tokens_total"] == 320


def test_the_report_does_not_lean_on_the_uninformative_correlation() -> None:
    """The artifact prints a Pearson r that this run cannot support.

    Five clips inside half a second of each other have almost no variance to
    correlate against, so r = 0.02 is not evidence that audio was sent and
    not evidence that it was not. The report has to say so where it quotes
    it, because the number is sitting right there in the file looking like a
    finding.
    """
    correlation = _delivery()["delivery"]["prompt_token_vs_clip_seconds"]
    assert correlation["n"] == 10
    assert abs(correlation["pearson_r"]) < 0.1

    text = _report()
    assert "아무 뜻도 없다" in text
    assert "오디오 토큰" in text, "the evidence it points to instead"


# --------------------------------------------------------------------------
# What the run is not allowed to conclude.
# --------------------------------------------------------------------------


def test_the_content_accuracy_is_recorded_and_not_concluded_from() -> None:
    """Two of five, from a judge that answered ``fail`` five times.

    337 §6 fixed this before the run: accuracy is printed and used for
    nothing. The trap is that 2/5 looks like a result. It is what a machine
    that says ``fail`` to everything scores on three true claims and two
    false ones -- which is what J = 0 records -- and at n = 5 the smallest
    attainable p is 0.031, so no outcome of this size could have been
    significant either way.
    """
    artifact = _artifact()
    overall = artifact["arms"]["production"]["overall"]

    assert (overall["calls"], overall["answered"]) == (5, 5)
    assert overall["correct"] == 2
    assert overall["accuracy"] == pytest.approx(0.4)
    assert artifact["arms"]["production"]["on_true_claims"]["correct"] == 0
    assert artifact["arms"]["production"]["on_false_claims"]["correct"] == 2

    # Every production verdict was `fail`, which is why 2/5 is not a skill.
    production = [c for c in artifact["calls"] if c["arm"] == "production"]
    assert {c["verdict"] for c in production} == {"fail"}

    comparison = artifact["arm_comparison"]
    assert comparison["per_claim_majority"]["production"]["discrimination_j"] == 0.0
    assert comparison["per_claim_majority"]["constant_fail_baseline"][
        "correct"
    ] == 2

    binomial = artifact["accuracy"]["pre_registered_binomial"]
    assert binomial["n"] == 5 and binomial["correct"] == 2
    assert binomial["p_one_sided"] == pytest.approx(0.8125)
    assert binomial["smallest_attainable_p"] == pytest.approx(0.03125)

    text = _report()
    assert "기록**이지 결과가 아니다" in text
    assert "0.03125" in text, "the floor that makes n = 5 unable to conclude"


def test_the_arm_comparison_is_not_read_as_a_result() -> None:
    """There is a McNemar p in the file. It measures delivery, not judgement.

    This is 334's mistake with a smaller n: an arm that answered nothing
    contributes five discordant pairs, and a p computed over them is a
    statement about envelopes. 337 §6 says the pilot concludes nothing about
    content, so the report must not quote this number as a finding.
    """
    comparison = _artifact()["arm_comparison"]

    assert comparison["pairs"] == 5
    assert comparison["discordant"]["treatment_only_correct"] == 0
    assert comparison["discordant"]["control_only_correct"] == 2
    assert comparison["per_claim_majority"]["observation"][
        "discrimination_j"
    ] is None, "an arm with no verdicts has no discrimination"

    text = _report()
    assert "mcnemar" not in text.lower(), (
        "339 quotes a p-value the pilot was pre-registered not to interpret"
    )


def test_the_cost_is_unknown_rather_than_zero() -> None:
    """Ten paid calls with no price in the table.

    Writing $0 for a run that spent money is worse than writing nothing,
    because a zero is a figure someone can add up. The usage is recorded in
    full so the number can be computed the day the price lands.
    """
    cost = _artifact()["cost"]

    assert cost["model_calls"] == 10
    assert cost["billable_calls"] == 10
    assert cost["pricing_complete"] is False
    assert cost["unpriced_models"] == ["gpt-audio-1.5"]
    assert cost["estimated_cost_usd"] is None

    # Usage complete on every call, which is what makes the null recoverable.
    assert all(call["usage_complete"] for call in _artifact()["calls"])

    text = _report()
    assert "`null`이지 `$0`이 아니다" in text
    assert "$0" not in text.replace("`$0`이 아니다", ""), (
        "a dollar figure appeared for a run whose price is not registered"
    )


def test_no_response_body_or_credential_was_stored() -> None:
    """The artifact keeps outcomes and usage. Not replies, not audio, not keys.

    337 §3 put this in writing before the run, and it is load-bearing twice
    over: the candidate instructs the model to write a transcript into
    ``reasoning``, so a stored body would carry clip content, and 339 §5's
    comparison against 334 is deliberately limited to reply *length* because
    of it. A later run that starts storing bodies would quietly turn that
    limit into a lie.
    """
    blob = _MEASURED.read_text(encoding="utf-8")
    artifact = _artifact()

    for call in artifact["calls"]:
        assert "reasoning" not in call
        assert set(call["wire"]) & {"prompt", "prompt_text", "response"} == set()

    # No base64 audio payload rode along in the record.
    assert "data:audio" not in blob
    assert "input_audio" not in blob
    assert not re.search(r"\bsk-[A-Za-z0-9]{16,}", blob)
    assert "api_key" not in blob.lower()
    assert "AZURE_OPENAI" not in blob


# --------------------------------------------------------------------------
# What the pilot refuses to buy next.
# --------------------------------------------------------------------------


def test_the_main_comparison_is_closed_and_still_unbought() -> None:
    """338 stays shut, and its §0 first row stays unticked.

    ③'s rule is that a failed pilot stops there. The failure modes this
    guards are ordinary ones: tick the box because the pilot "basically
    worked", or leave the document looking dispatchable so a later reader
    runs it. Neither is a code change, which is why a test has to read the
    prose.
    """
    main = _MAIN.read_text(encoding="utf-8")

    assert "**상태: 안 샀다. 그리고 안 산다.**" in main
    assert "| **`337`이 §5의 두 기준을 다 통과함** | ⬜ |" in main, (
        "338 §0's first condition was ticked for a pilot that failed it"
    )
    assert main.count("| ⬜ |") == 5, "338 §0's conditions were quietly resolved"

    # The bar it was gated on is quoted, unchanged, in both documents.
    assert "후보 5/5" in main
    assert "**5/5** 읽힘" in _PILOT.read_text(encoding="utf-8")

    # And 339 says out loud that the 120 calls are not bought.
    text = _report()
    assert "120회는 **안 산다" in text


def test_the_pilot_calls_are_not_folded_into_the_comparison() -> None:
    """Ten plus one hundred and twenty is an experiment nobody registered.

    337 §6 and §7 both say this, from opposite directions, because it is the
    cheapest way to make a failed pilot look like data.
    """
    text = _report()
    assert "| 이 10회를 `338`에 합치기 | 130회짜리 실험은 아무도 등록한 적이 없다" in text


def test_the_bar_was_not_moved_after_the_result_came_back() -> None:
    """§5's two thresholds are byte-identical to what was registered.

    A pre-registration only constrains anything if the thresholds survive
    contact with the numbers. These two lines are the ones that would have
    to change for 1/5 to pass, so they are read out of the pilot document
    after the fact and compared against what 339 reports them to be.
    """
    pilot = _PILOT.read_text(encoding="utf-8")

    assert "| **observation (후보)** | **5/5** 읽힘 |" in pilot
    assert "| **production (대조)** | **4/5 이상** 읽힘 |" in pilot

    # 337's status line says it ran, and says where the result is.
    assert "**상태: 실행 완료 (2026-09-08)" in pilot
    assert "339-the-sentence-that-changed-nothing.md" in pilot

    text = _report()
    assert "읽을 수 있는 JSON **5/5**" in text
    assert "읽을 수 있는 JSON **4/5 이상**" in text


# --------------------------------------------------------------------------
# The published record this does not touch.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, checks",
    [
        (
            "331-audio-accuracy-measured.json",
            {"calls_planned": 60, "answered": 59, "correct": 36},
        ),
        (
            "334-audio-accuracy-measured.json",
            {"calls_planned": 120, "answered": 59, "correct": 37},
        ),
    ],
)
def test_the_earlier_runs_are_left_exactly_as_published(
    name: str, checks: dict
) -> None:
    """339 adds a document. It does not restate an older run's figures.

    331 and 334 were bought under their own pre-registrations and their
    numbers are published. This run is a third experiment, not a correction
    of either, and the standing instruction is that their figures are not
    overwritten. Reading them here and asserting they are untouched is the
    cheap version of that promise.

    ``accuracy`` is the control arm, not the run: in a two-arm artifact it
    mirrors ``arms.production``. Quoting it as a run-wide figure would blend
    an arm that answered 15% of the time into one that answered 98%, which
    is the arithmetic 334 §2 exists to refuse.
    """
    artifact = json.loads((TASKS / name).read_text(encoding="utf-8"))
    assert artifact["calls_planned"] == checks["calls_planned"]
    assert artifact["accuracy"]["overall"]["answered"] == checks["answered"]
    assert artifact["accuracy"]["overall"]["correct"] == checks["correct"]

    # And 334's headline failure count, which 339 §5 compares lengths against.
    if name.startswith("334"):
        unreadable = [
            call
            for call in artifact["calls"]
            if call["arm"] == "observation"
            and call["judge_error"] == "format_error:unparseable_json"
        ]
        assert len(unreadable) == 51
        assert artifact["arms"]["observation"]["overall"][
            "response_rate"
        ] == pytest.approx(0.15)

        tokens = sorted(call["output_tokens"] for call in unreadable)
        assert (tokens[0], tokens[-1]) == (18, 68)
        assert tokens[len(tokens) // 2] == 32

        text = _report()
        assert "18 ~ 68 (중앙값 32)" in text


def test_the_comparison_with_334_is_limited_to_reply_length() -> None:
    """Same neighbourhood is not same failure, and the report says which.

    335 bought three response bodies and found the model wrote no JSON at
    all. This run stored none, so the most it can say is that four replies
    are the same length as replies that did that. Claiming the mechanism
    without the bodies would be inventing the part that cost money to learn.
    """
    observation = [
        call
        for call in _artifact()["calls"]
        if call["arm"] == "observation"
        and call["judge_error"] == "format_error:unparseable_json"
    ]
    assert sorted(call["output_tokens"] for call in observation) == [
        22,
        23,
        24,
        29,
    ]

    text = _report()
    assert "길이가 같은 자리에 있다" in text
    # The negation, not the phrase. Asserting only that the words appear
    # would pass on a report that dropped the "는 아니다" and claimed the
    # mechanism outright, which is the sentence this is meant to stop.
    assert '*"글자까지 같은 실패다"*는 아니다' in text


def test_the_report_states_the_limits_that_outlive_it() -> None:
    """Five calls, one synthetic voice, one candidate, no V1 control.

    Each of these is a sentence someone will otherwise supply for us: that
    the failure rate rose from 15% to 20%, that the candidate sentence is
    what failed, that this says something about human speech. None of them
    follows from ten calls, and §9 is where the report refuses them.
    """
    text = _report()

    assert "## 9. 이 실행이 못 말하는 것" in text
    assert "실패율의 표본이 아니다" in text
    assert "V1을 이번에 같이 안 돌렸다" in text
    assert "사람 목소리가 아니다" in text
    assert "재시도를 시사하는 흔적이 없다" in text, (
        "the SDK's own retries sit below the counter; §9 has to say so"
    )


def test_the_gap_to_the_fingerprint_move_adds_up_and_agrees_across_documents(
) -> None:
    """The margin is the claim, so the arithmetic has to be checkable.

    §10's whole point is that A's merge landed *after* the paid job, and the
    only thing separating "did not overlap" from "overlapped" is a couple of
    minutes. A number that is copied rather than computed drifts by a second
    and then nobody can tell which end it was measured from, so this recomputes
    it from the timestamps the report itself prints and requires 337 to state
    the same figure against the same anchor.
    """
    text = _report()

    job_end = re.search(
        r"유료 job은 \d{2}:\d{2}:\d{2}Z → (\d{2}):(\d{2}):(\d{2})Z", text
    )
    assert job_end, "§1 has to print when the paid job ended"

    stated = re.search(
        r"(\d{2}):(\d{2}):(\d{2})Z 병합 —"
        r" \*\*유료 job이 끝난 (\d{2}):(\d{2}):(\d{2})Z에서"
        r" (\d+)분 (\d+)초 뒤\*\*",
        text,
    )
    assert stated, "§10 has to name both ends of the gap it claims"

    def _seconds(groups: tuple[str, ...]) -> int:
        h, m, s = (int(part) for part in groups)
        return h * 3600 + m * 60 + s

    merged = _seconds(stated.groups()[:3])
    anchor = _seconds(stated.groups()[3:6])
    assert anchor == _seconds(job_end.groups()), (
        "§10 must measure from the same job end §1 records, not the run's"
    )

    minutes, seconds = (int(part) for part in stated.groups()[6:8])
    assert merged - anchor == minutes * 60 + seconds
    assert merged > anchor, "the merge landed after the job, which is the claim"

    # 337 §11 tells the same story from the other side. One of them being a
    # second off is how a reader ends up unable to tell whether the window
    # overlapped at all.
    assert f"{minutes}분 {seconds}초 뒤" in _PILOT.read_text(encoding="utf-8")
