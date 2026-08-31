"""Fifteen refused listening calls, and two sentences between them.

The audio smoke on run ``33374220483`` produced no listening verdicts at all.
Every item that routed to the listening model came back an error, and the
whole of what the artifact said about why was this::

    audio_perception_failed:audio_unavailable:provider_400        x13
    audio_perception_failed:provider_error:BadRequestError         x2
    provider_error:InternalServerError                            x11

An item carries 37 fields and not one of them says what was wrong with the
request. ``judge_raw_response`` is null, because there was no judge response.
There is no ``reasoning`` field on a published item, because a sub-judge's
prose is model output and is not published. So the next step after reading
that artifact is to buy another run and hope it says more, which is the cost
this module exists to remove.

Widening ``judge_error`` to say more would have been the wrong repair. It is
a small controlled vocabulary and its value is that a corpus of 185 tasks can
be grouped by it; put a byte count in it and two clean groups become fifteen
singletons that ``uniq -c`` can tell you nothing about. So the kind of
failure stays where it is and the cause travels beside it, in
``AudioVerdict.failure_detail`` and then ``ItemGrade.perception_error_detail``.

What that field may contain is the constraint that shapes everything here.
``core/public_error.py`` returns ``provider_error:<ExceptionType>`` and
deliberately never the message body or the endpoint, because grades are
committed to a public repository. A detail field that quoted the provider
would undo that in the same payload. So every character of it is built by
this harness out of its own measurements -- the exception's type name, the
status it carried, the format the request claimed, the source file's suffix,
and the two byte counts -- and ``test_the_detail_never_repeats_the_provider_s
_own_words`` is the check that keeps it that way.

Nothing here calls a model.

Spec: tasks/rebuilding_grading_task/307-audio-smoke-result.md
"""

from __future__ import annotations

import re
import struct
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.grader import ItemGrade  # noqa: E402
from core.perception.audio import AudioPerception  # noqa: E402
from core.tool_calling_judge import (  # noqa: E402
    _unanswerable_audio_detail,
    _unanswerable_audio_reason,
)


class ChattyBadRequest(Exception):
    """A 400 whose message is the shape the provider really sends.

    The published ``judge_error`` has always been safe from this because
    ``public_provider_error_text`` reads only the type name. The new field is
    the second thing in the same payload that could leak it, so it is worth a
    double that actually carries something worth not leaking.

    The class name deliberately does not end in ``Error``: that is the shape
    ``public_task_error`` insists on before it will publish a type name at
    all, and a name it refuses is exactly the case where the two fields could
    have disagreed about what is publishable.
    """

    MESSAGE = (
        "Error code: 400 - {'error': {'message': \"Invalid value for "
        "'audio.data': the request sent to "
        "https://gdpval-eastus2.openai.azure.com/openai/deployments/"
        "gpt-audio-1.5/chat/completions?api-version=2025-04-01-preview"
        " could not be decoded\", 'type': 'invalid_request_error'}}"
    )

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)
        self.status_code = 400


class BadRequestError(ChattyBadRequest):
    """The same 400, under the name the SDK really raises it with.

    Named so ``public_task_error`` will publish it, which is what the smoke
    saw: ``provider_error:BadRequestError`` fifteen times and nothing else.
    """


def _reply():
    body = (
        '{"verdict": "pass", "partial_score": 1.0, "evidence": "clear",'
        ' "confidence": 0.9, "reasoning": "audible"}'
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=body, audio=None))],
        usage=None,
    )


class _Completions:
    def __init__(self, *, ok: bool = False, error_factory=ChattyBadRequest) -> None:
        self.calls: list[dict] = []
        self._ok = ok
        self._error_factory = error_factory

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._ok:
            return _reply()
        raise self._error_factory()


class _Client:
    def __init__(self, completions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def _write_wav(path: Path) -> Path:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(
            b"".join(struct.pack("<h", (i % 50) * 300) for i in range(8000))
        )
    return path


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    return _write_wav(tmp_path / "stem.wav")


# ── the sub-judge writes down what it sent ───────────────────────────


def test_a_refused_call_records_what_was_sent(wav_file):
    """The headline. Every one of these was unknowable from the smoke.

    Byte counts are matched by shape rather than by value: a ``.wav`` is
    re-encoded to 16 kHz mono when PyAV is importable and passed through when
    it is not, so the numbers differ between environments. What is being
    pinned is that the run records them, not what this particular run
    measured.
    """
    completions = _Completions(error_factory=BadRequestError)
    perception = AudioPerception(client=_Client(completions))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    detail = verdict.failure_detail
    assert detail is not None
    assert "BadRequestError" in detail, "which exception"
    assert "status=400" in detail, "which status"
    assert "format=wav" in detail, "what the request claimed the bytes were"
    assert "source_suffix=.wav" in detail, "what the file was called"
    assert re.search(r"\bbytes=\d+", detail), "how much was sent"
    assert re.search(r"\bb64_bytes=\d+", detail), "and how much after encoding"


def test_the_two_published_fields_agree_on_what_a_type_name_may_be(wav_file):
    """One projection, so there is only one thing to get right.

    ``public_task_error`` publishes a class name only when it is shaped like
    an exception's and substitutes ``TaskExecutionError`` when it is not --
    the guard against a dynamically built type carrying a value out in its
    name. The detail is built from that same projection rather than from
    ``type(exc).__name__``, so it can never become a second, laxer route to
    the same payload.
    """
    perception = AudioPerception(client=_Client(_Completions()))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    assert verdict.judge_error == "provider_error:TaskExecutionError"
    assert "TaskExecutionError" in verdict.failure_detail
    assert "ChattyBadRequest" not in verdict.failure_detail, (
        "a name judge_error refused to publish must not appear beside it"
    )


def test_the_detail_never_repeats_the_provider_s_own_words(wav_file):
    """The rule that decides what this field is allowed to be.

    Grades are committed to a public repository, and
    ``public_provider_error_text`` keeps the endpoint and the message body out
    of ``judge_error`` for that reason. A second field in the same payload
    that quoted the exception would give all of it back.
    """
    completions = _Completions()
    perception = AudioPerception(client=_Client(completions))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    published = f"{verdict.failure_detail} {verdict.judge_error}"
    for secret in (
        "gdpval-eastus2",
        "openai.azure.com",
        "api-version",
        "chat/completions",
        "invalid_request_error",
        "could not be decoded",
    ):
        assert secret not in published, f"{secret!r} reached a published field"
    assert ChattyBadRequest.MESSAGE not in published


def test_a_call_that_was_answered_carries_no_detail(wav_file):
    """The field means "this failed, here is why", so a verdict has none.

    Left unset rather than filled with a success message, because a reader
    grouping a corpus by "did this item have a perception failure" should be
    able to ask this field and not a sentence.
    """
    perception = AudioPerception(client=_Client(_Completions(ok=True)))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    assert verdict.verdict == "pass"
    assert verdict.failure_detail is None


def test_a_short_circuited_criterion_explains_itself_too(wav_file):
    """The other thirteen items in the smoke, which never reached the wire.

    After the first 400 the task is blocked and the rest are refused by name.
    Those refusals are written by this module out of its own counters, so the
    sentence that explains one in a log is the one the payload can carry.
    """
    perception = AudioPerception(client=_Client(_Completions()))

    first = perception.judge(criterion="c1", audio_path=str(wav_file))
    second = perception.judge(criterion="c2", audio_path=str(wav_file))

    assert second.judge_error == "audio_unavailable:provider_400"
    assert second.failure_detail == second.reasoning
    assert "provider_400" in second.failure_detail
    assert first.failure_detail != second.failure_detail, (
        "the call that was refused and the calls that were never made are "
        "two different facts"
    )


def test_a_file_with_no_extension_is_visible_in_the_detail(tmp_path):
    """The case the detail exists to make visible rather than to describe.

    ``_guess_format`` falls back to ``"wav"`` for a file with no suffix, and
    the format gate only checks that label. So a suffix-less file of any
    container at all goes out claiming to be a WAV, and a 400 is exactly what
    a provider should answer with. ``source_suffix=none`` beside
    ``format=wav`` is enough to spot that from the artifact; the two fields
    are separate so the reader draws that conclusion from facts rather than
    trusting this module to have drawn it for them.
    """
    unnamed = _write_wav(tmp_path / "_tmp.wav").rename(tmp_path / "stem")
    perception = AudioPerception(client=_Client(_Completions()))

    verdict = perception.judge(criterion="c", audio_path=str(unnamed))

    assert "source_suffix=none" in verdict.failure_detail
    assert "format=wav" in verdict.failure_detail


def test_a_file_that_cannot_be_prepared_says_so_before_any_call(tmp_path):
    """The failure that happens on this side of the wire has a detail too.

    There is no status and no byte count to report, so it reports what there
    is. An empty detail here would send a reader looking for a provider
    problem that never existed.
    """
    completions = _Completions()
    perception = AudioPerception(client=_Client(completions))
    missing = tmp_path / "never_written.wav"

    verdict = perception.judge(criterion="c", audio_path=str(missing))

    assert verdict.verdict == "judge_error"
    assert "audio preparation failed" in verdict.failure_detail
    assert "suffix=.wav" in verdict.failure_detail
    assert completions.calls == [], "nothing was sent"


def test_the_detail_is_published_alongside_the_verdict(wav_file):
    """``to_dict`` is what the tool hands back to the judge.

    A field the dataclass carries and the dict drops would pass every test
    above and reach nothing.
    """
    perception = AudioPerception(client=_Client(_Completions(
        error_factory=BadRequestError
    )))

    payload = perception.judge(criterion="c", audio_path=str(wav_file)).to_dict()

    assert payload["failure_detail"]
    assert payload["judge_error"] == "provider_error:BadRequestError"


# ── the judge reads it, and knows when there is nothing to read ──────


def _tool_result(**data) -> dict:
    return {"ok": False, "error_type": "perception", "data": data}


def test_the_judge_carries_the_sub_judge_s_account_through():
    result = _tool_result(
        judge_error="provider_error:BadRequestError",
        failure_detail="audio call failed: BadRequestError (status=400, ...)",
    )

    assert _unanswerable_audio_reason(result) == (
        "audio_perception_failed:provider_error:BadRequestError"
    )
    assert _unanswerable_audio_detail(result) == (
        "audio call failed: BadRequestError (status=400, ...)"
    )


def test_a_mistake_the_judge_can_correct_has_no_detail_to_carry():
    """The gating is shared with the reason, so the two cannot disagree.

    A bad path is the judge's to fix and does not end the item, so nothing
    about it belongs in a field that describes why an item ended.
    """
    for error_type in ("bad_path", "bad_args", "bad_scope"):
        result = {
            "ok": False,
            "error_type": error_type,
            "data": {"failure_detail": "should not be read"},
        }
        assert _unanswerable_audio_reason(result) is None
        assert _unanswerable_audio_detail(result) is None


def test_a_call_that_succeeded_has_no_detail():
    result = {"ok": True, "data": {"failure_detail": "stale"}}

    assert _unanswerable_audio_detail(result) is None


def test_a_failure_with_no_sub_judge_behind_it_admits_it_has_nothing():
    """``no_audio_judge`` needs no elaboration, and inventing one would lie.

    The reason already is the whole story wherever the sub-judge never ran,
    so ``None`` is the honest answer rather than a restatement.
    """
    result = {"ok": False, "error_type": "no_audio_judge"}

    assert _unanswerable_audio_reason(result) == (
        "audio_perception_failed:no_audio_judge"
    )
    assert _unanswerable_audio_detail(result) is None


def test_an_older_payload_without_the_field_is_read_without_complaint():
    """Resumes replay tool results recorded before this field existed."""
    result = _tool_result(judge_error="provider_error:BadRequestError")

    assert _unanswerable_audio_detail(result) is None


@pytest.mark.parametrize("value", [None, "", "   ", 400, {"nested": "no"}])
def test_only_a_real_sentence_is_carried(value):
    """Anything else would put a type the schema forbids into a grade."""
    result = _tool_result(
        judge_error="provider_error:BadRequestError", failure_detail=value
    )

    assert _unanswerable_audio_detail(result) is None


# ── and it reaches the grade ─────────────────────────────────────────


def test_the_grade_row_has_somewhere_to_put_it():
    """The end of the chain, and the reason the whole chain exists.

    ``evidence`` is capped at ``grader.evidence_max_chars`` and holds the
    kind of failure; this holds the cause, uncapped, on the same row.
    """
    grade = ItemGrade(
        rubric_item_id="audio-1",
        criterion="The Master track contains no vocals.",
        max_score=2,
        awarded_score=0.0,
        verdict="judge_error",
        decided_by="judge",
        required=None,
        evidence="audio_perception_failed:provider_error:BadRequestError",
        perception_error_detail=(
            "audio call failed: BadRequestError (status=400, format=wav,"
            " source_suffix=none, bytes=961324, b64_bytes=1281766)"
        ),
    )

    assert "source_suffix=none" in grade.perception_error_detail


def test_an_ordinary_grade_row_leaves_it_empty():
    """Default ``None``, so 184 clean tasks gain nothing but a null."""
    grade = ItemGrade(
        rubric_item_id="r1",
        criterion="c",
        max_score=2,
        awarded_score=2.0,
        verdict="pass",
        decided_by="judge",
        required=None,
        evidence="the figure is on page 3",
    )

    assert grade.perception_error_detail is None
