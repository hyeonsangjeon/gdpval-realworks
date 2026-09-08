"""A listening call that went wrong still costs what it cost.

``test_a_perception_read_reaches_the_receipt`` established that the grader
hands its audio reader a *metered* client, so a successful listen lands on the
receipt under ``perception``. It checks the path that works. This file checks
the paths that do not, because those are the ones where money goes missing.

The reason they are separate files is that the failure modes here are not
failures of the ledger. They are failures of the *thing being metered*: the
model answers with prose instead of JSON, or answers with valid JSON that
declines to judge, or answers with no usage block, or the provider refuses the
request outright. In every one of those cases the grading run carries on and
the criterion comes back ``judge_error`` — and in most of them the request was
still sent, the tokens were still spent, and somebody is still going to be
billed for them. A receipt that reported those calls as absent, or as ``$0``,
would be understating a real bill in exactly the situations where the run
looks worst and the reader is most likely to be checking.

What made this worth writing rather than assuming: the audio adapter parses
the reply *after* the metered wrapper has already settled the call, so usage
survives a parse failure by construction — but nothing anywhere drove a real
``Grader``'s audio reader into a real ledger with a reply it could not parse,
so "by construction" was a reading of the code, not a measurement of it. The
same held for the reply with no usage, for the provider refusal, and for the
resume. Each test below was written after running the case and recording what
actually came out; where the measured behaviour is arguably wrong rather than
merely surprising — the provider refusal in
``test_a_refused_request_is_recorded_as_unknown_not_as_free`` — the test
records what is true today and the argument for changing it lives in
``tasks/rebuilding_grading_task/340-the-cost-of-a-call-that-failed.md``,
because the change would be to shared metering code this file does not own.

The audio model is deliberately absent from the committed price table
(``models_deliberately_not_priced['azure:gpt-audio-1.5']``, re-verified
2026-09-07: no Azure meter exists for it). So the amounts here come from a
fixture table, and one test below exists purely to keep the two reasons a
price can be missing from collapsing into each other. No provider is
contacted.
"""

from __future__ import annotations

import json
import struct
import wave
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from core.cost_metering import CostRecorder, open_cost_recorder
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_CALL_REFUSED_UNPRICED,
    REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    CallUsage,
    CostReceiptLedger,
    LedgerIntegrityError,
    load_receipt_price_table,
)
from core.grader import Grader

#: The settings a real marking run loads, read rather than restated so that
#: renaming the deployment moves these tests instead of quietly unpricing them.
CONFIG_PATH = Path("grading_configs/default_v2.yaml")

#: One call's usage, with an audio share inside it. The numbers are round and
#: far apart so that a wrong arithmetic shows up as a wrong amount rather than
#: as a number that still looks plausible.
INPUT_TOKENS = 1_000
OUTPUT_TOKENS = 200
AUDIO_INPUT_TOKENS = 30
AUDIO_OUTPUT_TOKENS = 10

TEXT_RATE_IN = Decimal("40")
TEXT_RATE_OUT = Decimal("80")
AUDIO_RATE_IN = Decimal("100")
AUDIO_RATE_OUT = Decimal("200")

#: What the call costs when the audio counts are read as a *share* of the
#: reported input and output, which is what they are. Spelled as the sum rather
#: than as a literal so the test states the rule and not just its answer.
CONTAINED_USD = (
    Decimal(INPUT_TOKENS - AUDIO_INPUT_TOKENS) * TEXT_RATE_IN
    + Decimal(AUDIO_INPUT_TOKENS) * AUDIO_RATE_IN
    + Decimal(OUTPUT_TOKENS - AUDIO_OUTPUT_TOKENS) * TEXT_RATE_OUT
    + Decimal(AUDIO_OUTPUT_TOKENS) * AUDIO_RATE_OUT
) / Decimal(1_000_000)

#: What it would cost if the audio counts were charged *on top of* the reported
#: input and output instead of inside them. Never asserted as an expectation —
#: only as the thing the real amount must not equal.
DOUBLE_COUNTED_USD = (
    Decimal(INPUT_TOKENS) * TEXT_RATE_IN
    + Decimal(AUDIO_INPUT_TOKENS) * AUDIO_RATE_IN
    + Decimal(OUTPUT_TOKENS) * TEXT_RATE_OUT
    + Decimal(AUDIO_OUTPUT_TOKENS) * AUDIO_RATE_OUT
) / Decimal(1_000_000)

VERDICT = json.dumps({
    "verdict": "pass",
    "partial_score": 1.0,
    "evidence": "the narration says it",
    "confidence": 0.9,
    "reasoning": "heard directly",
})

#: Valid JSON in the shape the reader accepts, in which the model declines to
#: judge. Distinct from unparseable prose: the envelope was read, and what was
#: inside it was a refusal. One of the ten calls in ``337`` came back like this
#: while four came back as prose, and collapsing the two loses the difference.
DECLINED = json.dumps({
    "verdict": "judge_error",
    "partial_score": 0.0,
    "evidence": "",
    "confidence": 0.0,
    "reasoning": "the clip is too quiet to call",
})


class _ProviderRefused(Exception):
    """A provider error carrying a status, in the shape the adapter reads."""

    def __init__(self, status: int) -> None:
        super().__init__(f"the provider answered {status}")
        self.status_code = status


class _Completions:
    """The Chat Completions surface, answering from a script.

    Spelled in this shape and not the Responses one for the reason
    ``test_a_failed_audio_call_does_not_cost_the_task_its_turn`` gives: a
    double that answered both would let a move back to the endpoint that
    cannot accept audio keep passing here.
    """

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        step = self._script[min(len(self.calls) - 1, len(self._script) - 1)]
        if isinstance(step, Exception):
            raise step
        return step


class _Responses:
    """The vision surface, which no test here is allowed to reach."""

    def create(self, **kwargs):  # pragma: no cover - a tripwire, not a path
        raise AssertionError("the audio tests must not spend a vision call")


class _Client:
    """One connection offering both surfaces, the way the real one does."""

    def __init__(self, script: list) -> None:
        self.chat = SimpleNamespace(completions=_Completions(script))
        self.responses = _Responses()


def _usage(
    *,
    input_tokens: int | None = INPUT_TOKENS,
    output_tokens: int | None = OUTPUT_TOKENS,
    audio_input: int | None = AUDIO_INPUT_TOKENS,
    audio_output: int | None = AUDIO_OUTPUT_TOKENS,
    cached: int = 0,
):
    return SimpleNamespace(
        prompt_tokens=input_tokens,
        completion_tokens=output_tokens,
        prompt_tokens_details=SimpleNamespace(
            cached_tokens=cached, audio_tokens=audio_input
        ),
        completion_tokens_details=SimpleNamespace(
            reasoning_tokens=0, audio_tokens=audio_output
        ),
    )


def _reply(text: str = VERDICT, usage=...):
    """A reply the adapter will try to read, carrying usage unless told not to."""
    return SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content=text, audio=None))],
        usage=_usage() if usage is ... else usage,
        model="gpt-audio-1.5",
    )


def _entry(*, prices_audio: bool) -> dict:
    entry = {
        "input_usd_per_million": str(TEXT_RATE_IN),
        "cached_input_usd_per_million": str(TEXT_RATE_IN),
        "output_usd_per_million": str(TEXT_RATE_OUT),
        "reasoning_billed_as": "output",
        "source": "fixture",
        "last_reviewed": "2026-09-02",
        "currency": "USD",
        "unit": "per 1,000,000 tokens",
    }
    if prices_audio:
        entry["audio_billed_as"] = "separate"
        entry["audio_input_usd_per_million"] = str(AUDIO_RATE_IN)
        entry["audio_output_usd_per_million"] = str(AUDIO_RATE_OUT)
    return entry


@pytest.fixture
def document() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def audio_deployment(document) -> str:
    audio = document["judge"]["perception"]["audio"]
    return audio.get("deployment") or audio["model"]


@pytest.fixture
def wav_file(tmp_path) -> Path:
    """A second of tone, because the reader opens the file for real."""
    path = tmp_path / "clip.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(
            b"".join(struct.pack("<h", (i % 50) * 300) for i in range(8000))
        )
    return path


def _price_file(tmp_path, deployment: str, *, prices_audio=True, named=True) -> Path:
    providers = (
        {f"azure:{deployment}": _entry(prices_audio=prices_audio)} if named else {}
    )
    path = tmp_path / f"prices-{'named' if named else 'absent'}-{prices_audio}.json"
    path.write_text(
        json.dumps({
            "cost_receipt_schema_version": "cost-receipt-price-table-v1",
            "providers": providers,
            "runtime": {},
        }),
        encoding="utf-8",
    )
    return path


def _ledger(tmp_path, prices: Path, name: str = "cost") -> CostReceiptLedger:
    return CostReceiptLedger(
        tmp_path / f"{name}.sqlite3",
        run_id="run-1",
        price_table=load_receipt_price_table(prices),
    )


def _listen(document, client, recorder, wav_file, criteria=("the narration is audible",)):
    """Drive the reader the grader really built, inside a marking scope."""
    grader = Grader(
        document, rubric_loader=None, client=client, cost_recorder=recorder
    )
    reader = grader._tool_judge.audio_perception
    assert reader is not None, "the committed settings built no audio reader"
    verdicts = []
    with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
        for criterion in criteria:
            verdicts.append(reader.judge(criterion=criterion, audio_path=str(wav_file)))
    return reader, verdicts


def _rows(ledger) -> list[dict]:
    return ledger.calls_for("task-a")


# ── the reply arrived and could not be used ──────────────────────────────


@pytest.mark.parametrize(
    "text, expected_error",
    [
        ("I could hear a bell ringing, but I am not sure.", "format_error:unparseable_json"),
        (DECLINED, "sub_judge_declined"),
    ],
    ids=["unparseable_prose", "declined_in_valid_json"],
)
def test_a_reply_the_judge_could_not_use_is_still_a_reply_that_was_paid_for(
    tmp_path, document, audio_deployment, wav_file, text, expected_error
):
    """A criterion that failed still bought the tokens it bought.

    Both halves of ``337``'s unanswered five are here. Four of them came back
    as prose the envelope reader could not parse; one came back as valid JSON
    in which the model declined. They fail differently and they are reported
    differently — but neither is free, and the receipt has to say so with the
    real numbers rather than with an absence.

    The mutation this rules out is settling *after* the parse instead of
    before it. Move ``ledger.settle`` behind the envelope check and both cases
    below leave a reservation that never closes, so a run whose audio replies
    are all malformed — which is the run ``334``, ``335`` and ``337`` actually
    bought — reports its entire audio spend as unknown.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_reply(text)])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _, verdicts = _listen(document, client, recorder, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        rows = _rows(ledger)

    # The criterion did fail, in the way this case fails.
    assert verdicts[0].verdict == "judge_error"
    assert verdicts[0].judge_error == expected_error

    # ...and the call it failed on is on the receipt at its real price.
    assert len(rows) == 1
    assert rows[0]["state"] == "settled"
    assert rows[0]["input_tokens"] == INPUT_TOKENS
    assert rows[0]["output_tokens"] == OUTPUT_TOKENS
    assert rows[0]["audio_input_tokens"] == AUDIO_INPUT_TOKENS
    assert rows[0]["audio_output_tokens"] == AUDIO_OUTPUT_TOKENS

    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 1
    assert receipt.known_cost_usd == CONTAINED_USD


def test_a_reply_with_no_usage_block_is_a_call_without_a_number(
    tmp_path, document, audio_deployment, wav_file
):
    """No usage is not no call, and it is not no money either.

    The verdict here is a *good* one — the model answered and the answer
    parsed. Only the accounting is missing. So the failure this rules out is
    the quiet one: dropping the row because there was nothing to put in it,
    which would make the task look like it listened for free rather than like
    it listened and the provider did not say what that cost.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_reply(usage=None)])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _, verdicts = _listen(document, client, recorder, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        rows = _rows(ledger)

    assert verdicts[0].verdict == "pass"
    assert verdicts[0].usage_complete is False

    assert len(rows) == 1
    assert rows[0]["state"] == "settled"
    assert rows[0]["input_tokens"] is None

    assert receipt.model_calls == 1
    assert receipt.status == STATUS_PARTIAL
    assert REASON_USAGE_ABSENT in receipt.missing_reasons
    # Unknown, and specifically not zero.
    assert receipt.known_cost_usd == Decimal("0")
    assert REASON_PRICE_MISSING not in receipt.missing_reasons


# ── nothing was ever sent ────────────────────────────────────────────────


def test_a_read_that_failed_before_the_wire_files_no_call(
    tmp_path, document, audio_deployment, wav_file
):
    """A clip that could not be opened costs nothing, and says nothing.

    The counterpart to every test above: where the tokens really were not
    spent, the receipt must not carry a line for them. Otherwise the guard
    against understating the bill turns into a habit of overstating it, and a
    task that failed to find its audio file reads as a task that paid to
    listen to it.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_reply()])
    missing = wav_file.parent / "not-here.wav"

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        grader = Grader(
            document, rubric_loader=None, client=client, cost_recorder=recorder
        )
        with recorder.attributed(task_id="task-a", stage=STAGE_GRADING):
            verdict = grader._tool_judge.audio_perception.judge(
                criterion="the narration is audible", audio_path=str(missing)
            )
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        rows = _rows(ledger)

    assert verdict.verdict == "judge_error"
    assert verdict.api_call_count == 0
    assert client.chat.completions.calls == []
    assert rows == []
    assert receipt.status == STATUS_NOT_RUN
    assert receipt.model_calls == 0


def test_criteria_refused_by_name_after_a_refusal_file_no_calls(
    tmp_path, document, audio_deployment, wav_file
):
    """The criteria the adapter stops sending are not billed for being stopped.

    A deterministic refusal (``400``) makes the reader refuse the rest of the
    task's criteria by name instead of bouncing them off the provider one at a
    time. Measured: three criteria, one request, and the two that never went
    out leave no row. What the one that *did* go out leaves is the subject of
    the next test.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_ProviderRefused(400)])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        reader, verdicts = _listen(
            document, client, recorder, wav_file, criteria=("a", "b", "c")
        )
        rows = _rows(ledger)

    assert len(client.chat.completions.calls) == 1
    assert [v.api_call_count for v in verdicts] == [1, 0, 0]
    assert [v.judge_error for v in verdicts][1:] == [
        "audio_unavailable:provider_400",
        "audio_unavailable:provider_400",
    ]
    # The refusal also gives the criterion's turn back, so a task is not
    # silently shortened by a provider that never ran the model.
    assert reader.calls_used == 0
    assert len(rows) == 1


# ── the provider refused, or broke ───────────────────────────────────────


@pytest.mark.parametrize(
    "status,expected_state,expected_reason",
    [
        (400, "refused", REASON_CALL_REFUSED_UNPRICED),
        (500, "reserved", REASON_CALL_REACHABILITY_UNKNOWN),
    ],
    ids=["refused", "broke"],
)
def test_a_refused_request_is_recorded_as_unknown_not_as_free(
    tmp_path,
    document,
    audio_deployment,
    wav_file,
    status,
    expected_state,
    expected_reason,
):
    """A call that raised is on the ledger, and *why* it raised decides how.

    The two statuses used to land in the same place and that was the defect
    this test was written to pin. The metered wrapper reserves before the
    request and settles after it, so an exception in between left the row
    ``reserved`` and the receipt ``partial`` with
    ``call_reachability_unknown`` — for both.

    For the ``500`` that is still the right answer. The request went out, no
    usable answer came back, and whether the provider billed it is exactly
    what nobody knows.

    For the ``400`` the amount was right and the *reason* was wrong. §6.2 of
    ``TASK_PER_TASK_COST_RECEIPTS.md`` defines that reason as「API 도달 여부
    불명확」— whether the call reached the API is unclear. A ``400`` is a
    status, and a status is an answer: the request demonstrably reached the
    provider and the provider demonstrably declined it before running any
    model. Reachability is the one thing that is *not* unknown there. The
    adapter already acted on that knowledge — ``_UNBILLED_STATUS`` hands the
    criterion's turn back because nothing was spent — while the ledger was
    never told, so the receipt published doubt about a fact the process next
    to it was certain of.

    ``abandon`` was not the answer either: §6.2 reserves it for a call that
    「나가지 않았음이 확실할 때」, and this one went out. An abandoned row is
    dropped from the receipt, which would have turned a refusal into a
    *complete* receipt of $0 — the one reading worse than doubt.

    The argument and the proposed change were written up in
    ``tasks/rebuilding_grading_task/341-what-a-refused-call-costs.md`` and
    implemented in shared metering code, so a definitive refusal is now its
    own state. Both endings are asserted here by name rather than by "either
    of the two", because a test that accepted both would pass again on the
    day the distinction is lost.

    What has not changed, and is asserted for both: the row exists, it claims
    no amount, and the receipt refuses to call the task complete.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_ProviderRefused(status)])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _, verdicts = _listen(document, client, recorder, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        rows = _rows(ledger)

    assert verdicts[0].verdict == "judge_error"
    assert str(verdicts[0].judge_error).startswith("provider_error")

    assert len(rows) == 1
    assert rows[0]["state"] == expected_state
    assert rows[0]["model_cost_usd"] is None

    assert receipt.status == STATUS_PARTIAL
    assert expected_reason in receipt.missing_reasons
    # The states are told apart, so the reasons must be too: a refusal that
    # still published doubt about reachability would be the old behaviour
    # wearing a new name.
    assert set(receipt.missing_reasons) & {
        REASON_CALL_REFUSED_UNPRICED,
        REASON_CALL_REACHABILITY_UNKNOWN,
    } == {expected_reason}
    # Unknown is not zero, and neither is unbilled: the receipt claims no
    # amount for this call at all, and it is still counted as a call.
    assert receipt.known_cost_usd == Decimal("0")
    assert receipt.model_calls == 1


def test_one_unknown_call_does_not_erase_the_known_ones_beside_it(
    tmp_path, document, audio_deployment, wav_file
):
    """A transient failure costs its own line, not the task's whole total.

    ``335`` placed seven requests and two of them failed in transport. If a
    single unclosed reservation reduced the receipt to "unknown", five paid
    calls would vanish behind the two that broke. Measured here with one
    failure and two successes: the receipt is ``partial``, it says why, and it
    still reports the two amounts it does know.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_ProviderRefused(500), _reply(), _reply()])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, client, recorder, wav_file, criteria=("a", "b", "c"))
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        states = [row["state"] for row in _rows(ledger)]

    assert sorted(states) == ["reserved", "settled", "settled"]
    assert receipt.status == STATUS_PARTIAL
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
    assert receipt.model_calls == 3
    assert receipt.known_cost_usd == CONTAINED_USD * 2


# ── the audio share is a share ───────────────────────────────────────────


def test_the_audio_share_is_charged_once_not_added_on_top(
    tmp_path, document, audio_deployment, wav_file
):
    """Audio tokens are inside the reported counts, so they price once.

    The arithmetic is the whole test. Charging the reported input at the text
    rate *and* the audio count at the audio rate bills the audio tokens twice,
    and the result is a number that still looks like a price. Both figures are
    computed at the top of this file; the assertion is that the receipt equals
    the containing one and specifically not the other.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_reply()])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, client, recorder, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert receipt.known_cost_usd == CONTAINED_USD
    assert receipt.known_cost_usd != DOUBLE_COUNTED_USD


def test_an_audio_count_bigger_than_the_call_is_doubted_not_priced(
    tmp_path, document, audio_deployment, wav_file
):
    """A share larger than the whole is a contradiction, and says so.

    The reason this is ``usage_partial`` and not ``price_missing`` is the
    point: the price is right there in the table. What is wrong is the
    provider's own numbers, and the receipt has to name the thing that is
    actually broken or the next reader goes looking for a missing rate.
    """
    prices = _price_file(tmp_path, audio_deployment)
    client = _Client([_reply(usage=_usage(audio_input=INPUT_TOKENS * 2))])

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, client, recorder, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert receipt.status == STATUS_PARTIAL
    assert REASON_USAGE_PARTIAL in receipt.missing_reasons
    assert REASON_PRICE_MISSING not in receipt.missing_reasons
    assert receipt.known_cost_usd == Decimal("0")


def test_a_table_that_prices_the_model_but_not_its_speech_still_refuses(
    tmp_path, document, audio_deployment, wav_file
):
    """The second way a price goes missing, which looks like the first.

    ``test_an_unpriced_reader_does_not_take_the_other_one_down_with_it``
    covers the model being absent from the table. This covers the model being
    *present* and priced for text while the call carried speech — the case the
    committed table would land in the day somebody adds a text rate for
    ``gpt-audio-1.5`` without an audio one. Both come back
    ``price_missing``, and the negative control below is what proves the
    refusal is about the speech and not about the entry: the same table prices
    the same call once the audio share is zero.
    """
    prices = _price_file(tmp_path, audio_deployment, prices_audio=False)

    with _ledger(tmp_path, prices, name="spoken") as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, _Client([_reply()]), recorder, wav_file)
        spoken = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert spoken.status == STATUS_PARTIAL
    assert REASON_PRICE_MISSING in spoken.missing_reasons
    assert spoken.known_cost_usd == Decimal("0")

    silent_reply = _reply(usage=_usage(audio_input=0, audio_output=0))
    with _ledger(tmp_path, prices, name="silent") as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, _Client([silent_reply]), recorder, wav_file)
        silent = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert silent.status == STATUS_COMPLETE
    assert silent.known_cost_usd == (
        Decimal(INPUT_TOKENS) * TEXT_RATE_IN
        + Decimal(OUTPUT_TOKENS) * TEXT_RATE_OUT
    ) / Decimal(1_000_000)


# ── where the money is filed, and what a resume does to it ───────────────


def test_listening_is_grading_money_and_never_the_task_s_own(
    tmp_path, document, audio_deployment, wav_file
):
    """A perception read is the marker's cost, not the worker's.

    The two buckets answer two different questions — what did the model spend
    doing the work, and what did it spend marking it — and a perception call
    landing in the first would inflate a figure this benchmark publishes about
    the model under test using money spent by the model judging it.
    """
    prices = _price_file(tmp_path, audio_deployment)

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, _Client([_reply()]), recorder, wav_file)
        grading = recorder.receipt_for("task-a", BUCKET_GRADING)
        solving = recorder.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)
        stages = {row["stage"] for row in _rows(ledger)}

    assert stages == {STAGE_PERCEPTION}
    assert grading.model_calls == 1
    assert solving.status == STATUS_NOT_RUN
    assert solving.model_calls == 0
    assert solving.known_cost_usd == Decimal("0")


def test_a_resumed_run_adds_its_listening_to_the_ledger_it_reopened(
    tmp_path, document, audio_deployment, wav_file
):
    """Two rounds are two calls, at twice the money, under one task.

    Call identifiers are derived from position rather than content, so the
    second round's first listen would be named exactly like the first round's
    without something to separate them. ``open_cost_recorder`` supplies it —
    ``continue_rounds=True`` reads the round number off the ledger's own size,
    which is how ``step8_grade`` opens it after importing a previous chunk's
    export.

    Both failure modes are ruled out at once. Identical usage under a colliding
    identifier settles as a duplicate and the second round's money disappears;
    different usage raises and the run dies. This test uses *identical* replies
    on purpose, because that is the half that fails silently.
    """
    prices = _price_file(tmp_path, audio_deployment)
    ledger_path = tmp_path / "resumed.sqlite3"
    seen: list[tuple[int, int, Decimal]] = []

    for _round in range(2):
        recorder, note = open_cost_recorder(
            ledger_path,
            run_id="run-1",
            continue_rounds=True,
            price_table_path=prices,
        )
        assert recorder is not None and note is None
        _listen(document, _Client([_reply()]), recorder, wav_file)
        receipt = recorder.receipt_for("task-a", BUCKET_GRADING)
        seen.append((
            recorder.round_index,
            receipt.model_calls,
            receipt.known_cost_usd,
        ))
        identifiers = {row["call_id"] for row in _rows(recorder.ledger)}
        recorder.ledger.close()

    assert seen == [
        (0, 1, CONTAINED_USD),
        (1, 2, CONTAINED_USD * 2),
    ]
    assert len(identifiers) == 2, "the resumed round reused the first round's row"


def test_settling_the_same_listen_twice_never_changes_what_it_cost(
    tmp_path, document, audio_deployment, wav_file
):
    """Replaying a settlement is harmless; contradicting one is not.

    A merge or a retried export can hand the ledger a settlement it already
    holds. Repeating it with the same numbers has to be a no-op, or a shard
    merged twice doubles the bill. Repeating it with *different* numbers is a
    different event entirely — one of the two is wrong — and the ledger refuses
    rather than picking.
    """
    prices = _price_file(tmp_path, audio_deployment)

    with _ledger(tmp_path, prices) as ledger:
        recorder = CostRecorder(ledger)
        _listen(document, _Client([_reply()]), recorder, wav_file)
        call_id = _rows(ledger)[0]["call_id"]

        same = CallUsage(
            input_tokens=INPUT_TOKENS,
            output_tokens=OUTPUT_TOKENS,
            cached_input_tokens=0,
            reasoning_tokens=0,
            audio_input_tokens=AUDIO_INPUT_TOKENS,
            audio_output_tokens=AUDIO_OUTPUT_TOKENS,
        )
        ledger.settle(call_id, usage=same, resolved_model="gpt-audio-1.5")
        replayed = recorder.receipt_for("task-a", BUCKET_GRADING)

        contradiction = CallUsage(
            input_tokens=INPUT_TOKENS * 9,
            output_tokens=OUTPUT_TOKENS,
            cached_input_tokens=0,
            reasoning_tokens=0,
            audio_input_tokens=AUDIO_INPUT_TOKENS,
            audio_output_tokens=AUDIO_OUTPUT_TOKENS,
        )
        with pytest.raises(LedgerIntegrityError):
            ledger.settle(call_id, usage=contradiction, resolved_model="gpt-audio-1.5")

        after = recorder.receipt_for("task-a", BUCKET_GRADING)

    assert replayed.model_calls == 1
    assert replayed.known_cost_usd == CONTAINED_USD
    # The refusal left the recorded cost exactly as it was.
    assert after.known_cost_usd == CONTAINED_USD
