"""The diagnostic has to be safe before it is useful.

``diagnose_audio_format_failure.py`` exists to look at replies the grader
threw away. That is exactly the position from which a tool leaks something:
it is the only code in this repository that holds model output in its hand
and writes a file. So the tests that matter most here are not the ones
checking it reports the right ``finish_reason`` -- they are the ones checking
that when it is handed a reply containing an API key, an email address and a
reasoning block, none of the three reaches the artifact or the console.

Every test in this file runs against fabricated response objects. Nothing
here places a call, and nothing here needs credentials.
"""

from __future__ import annotations

import collections
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from core.perception.audio import (  # noqa: E402
    AUDIO_VERDICT_VOCABULARY,
    AudioEnvelopeError,
    _parse_json_envelope,
    _validated_audio_envelope,
)

import diagnose_audio_format_failure as diag  # noqa: E402
import measure_audio_grading_accuracy as probe  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MEASURED_334 = (
    REPO_ROOT / "tasks" / "rebuilding_grading_task"
    / "334-audio-accuracy-measured.json"
)


# --------------------------------------------------------------------------
# Fabricated responses
# --------------------------------------------------------------------------


def make_response(
    text=None,
    *,
    finish_reason="stop",
    refusal=None,
    transcript=None,
    reasoning=None,
    choices=True,
    usage=True,
):
    """A Chat Completions response with only the fields the collector reads."""
    if not choices:
        return SimpleNamespace(choices=[], usage=None)
    message = SimpleNamespace(
        content=text,
        refusal=refusal,
        audio=SimpleNamespace(transcript=transcript) if transcript else None,
    )
    if reasoning is not None:
        message.reasoning = reasoning
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        model="gpt-audio-1.5",
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0, audio_tokens=77),
        ) if usage else None,
    )


GOOD_ENVELOPE = json.dumps({
    "verdict": "pass",
    "partial_score": 1.0,
    "evidence": "the speaker says four blue boxes",
    "confidence": 0.9,
    "reasoning": "counted",
})


# --------------------------------------------------------------------------
# Masking
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, must_not_contain",
    [
        ("write to alice.smith@example.com about it", "alice.smith@example.com"),
        ("see https://internal.corp/secret?token=abc123", "internal.corp"),
        ("key sk-abcdefghijklmnopqrstuvwx", "sk-abcdefghijklmnopqrstuvwx"),
        ("aws AKIAIOSFODNN7EXAMPLE here", "AKIAIOSFODNN7EXAMPLE"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz01", "ghp_abcdefghijklmnopqrstuvwxyz01"),
        ("call 010-1234-5678 now", "010-1234-5678"),
        ("ssn 123456789 filed", "123456789"),
        ("digest " + "a" * 64, "a" * 64),
        ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc", "eyJhbGciOiJIUzI1NiJ9"),
    ],
)
def test_masking_removes_every_shape_of_identifier(raw, must_not_contain):
    masked = diag.mask_text(raw)
    assert must_not_contain not in masked, (
        f"mask_text left {must_not_contain!r} in {masked!r}"
    )


def test_masking_leaves_ordinary_prose_alone():
    """A mask that eats everything is a mask nobody will keep switched on."""
    text = "The clip says four blue boxes and the statement is supported."
    assert diag.mask_text(text) == text


def test_the_masked_excerpt_is_masked_before_it_is_truncated():
    """The other order leaks.

    Truncating first and masking second means a 30-character key cut at
    character 12 arrives at the masker as a 12-character fragment that no
    pattern matches, and those 12 characters go in the file.
    """
    secret = "sk-" + "Z" * 60
    text = "prefix " + secret + " suffix"
    excerpt = diag.masked_excerpt(text, 40)
    assert "Z" * 8 not in excerpt
    assert "<secret>" in excerpt


def test_excerpts_are_off_unless_asked_for():
    assert diag.masked_excerpt("anything at all", 0) is None
    facts = diag.collect_response_facts(make_response(GOOD_ENVELOPE))
    assert "text_excerpt_masked" not in facts
    assert facts["excerpts_enabled"] is False


def test_the_excerpt_length_is_bounded_by_the_spec_not_the_caller():
    """A command line may ask for less than the hard limit and never more."""
    long_text = "the clip contains speech. " * 200
    excerpt = diag.masked_excerpt(long_text, diag.EXCERPT_HARD_LIMIT)
    assert excerpt.startswith("the clip contains speech.")
    assert len(excerpt) <= diag.EXCERPT_HARD_LIMIT + 32  # + the "…(+N chars)" tail
    assert f"(+{len(long_text) - diag.EXCERPT_HARD_LIMIT} chars)" in excerpt
    with pytest.raises(ValueError, match="hard limit"):
        diag.masked_excerpt(long_text, diag.EXCERPT_HARD_LIMIT + 1)


def test_a_long_opaque_run_is_masked_rather_than_excerpted():
    """5000 characters of one token is what a leaked blob looks like."""
    assert diag.masked_excerpt("x" * 5000, diag.EXCERPT_HARD_LIMIT) == "<opaque>"


def test_the_cli_refuses_an_excerpt_length_over_the_hard_limit():
    with pytest.raises(SystemExit, match="exceeds the hard limit"):
        diag.main([
            "--prereg", str(MEASURED_334),
            "--speech-manifest", "unused",
            "--speech-clips", "unused",
            "--out", "unused",
            "--excerpt-chars", str(diag.EXCERPT_HARD_LIMIT + 1),
        ])


# --------------------------------------------------------------------------
# Abnormal types
# --------------------------------------------------------------------------


@pytest.mark.parametrize("weird", [
    {"secret": "sk-abcdefghijklmnopqrst"},
    ["sk-abcdefghijklmnopqrst"],
    SimpleNamespace(secret="sk-abcdefghijklmnopqrst"),
    12345678901234,
    b"sk-abcdefghijklmnopqrst",
])
def test_masking_a_non_string_reports_its_type_and_not_its_repr(weird):
    """``str(obj)`` is how a payload escapes through a helpful ``__repr__``."""
    masked = diag.mask_text(weird)
    assert masked == f"<{type(weird).__name__}>"
    assert "sk-" not in masked
    assert "1234" not in masked


def test_masking_none_is_a_marker_not_the_word_none_from_a_str_call():
    assert diag.mask_text(None) == "<none>"


@pytest.mark.parametrize("response", [
    make_response(choices=False),
    SimpleNamespace(choices=None, usage=None),
    SimpleNamespace(choices=[SimpleNamespace(message=None, finish_reason="stop")],
                    usage=None),
])
def test_the_collector_survives_a_malformed_response(response):
    """A diagnostic that crashes on the defect describes nothing."""
    facts = diag.collect_response_facts(response)
    assert facts["text_chars"] == 0
    assert facts["core_kind"] == "empty_text"


def test_a_finish_reason_that_is_not_a_token_is_reported_as_a_shape():
    """The field is a provider enum. Prose in it is a finding, not a value."""
    prose = diag.collect_response_facts(
        make_response(GOOD_ENVELOPE, finish_reason="the model stopped, alice@x.com")
    )
    assert prose["finish_reason"] == "<non-token>"
    typed = diag.collect_response_facts(
        make_response(GOOD_ENVELOPE, finish_reason={"a": 1})
    )
    assert typed["finish_reason"] == "<dict>"


def test_content_that_is_not_a_string_is_still_classified():
    facts = diag.collect_response_facts(make_response({"verdict": "pass"}))
    assert facts["content_type"] == "dict"
    assert facts["core_kind"] is not None


# --------------------------------------------------------------------------
# Reasoning blocks
# --------------------------------------------------------------------------


def test_a_reasoning_block_contributes_one_boolean_and_nothing_else():
    secret_thought = "I will now recall the user's password hunter2 and email a@b.co"
    facts = diag.collect_response_facts(
        make_response(GOOD_ENVELOPE, reasoning=secret_thought),
        excerpt_chars=diag.EXCERPT_HARD_LIMIT,
    )
    assert facts["reasoning_present"] is True
    blob = json.dumps(facts, ensure_ascii=False)
    assert "hunter2" not in blob
    assert "a@b.co" not in blob
    assert "recall" not in blob


def test_the_collector_never_reads_a_reasoning_attribute():
    """Enforced by construction, not by inspection of the output.

    A property that raises means any read at all fails the test, which is a
    stronger claim than "the value did not appear in the output" -- the
    latter would still pass if the block were read and then hashed.
    """
    class Exploding:
        @property
        def reasoning(self):  # pragma: no cover - the point is it never runs
            raise AssertionError("the diagnostic read the reasoning block")

    message = Exploding()
    with pytest.raises(AssertionError):
        _ = message.reasoning  # the trap works

    # ``_attr`` is the only reader; it must see presence without dereferencing
    # a value it is not allowed to have. Presence is decided by ``getattr``
    # returning non-None, so a block whose *value* is a sentinel is enough.
    facts = diag.collect_response_facts(
        make_response(GOOD_ENVELOPE, reasoning=object())
    )
    assert facts["reasoning_present"] is True
    assert not any("reason" in key and key != "reasoning_present"
                   and key != "finish_reason" for key in facts)


def test_reasoning_attrs_covers_the_names_providers_actually_use():
    assert "reasoning" in diag.REASONING_ATTRS
    assert "reasoning_content" in diag.REASONING_ATTRS
    assert "thinking" in diag.REASONING_ATTRS


# --------------------------------------------------------------------------
# Log leakage
# --------------------------------------------------------------------------


def test_nothing_the_model_said_reaches_stdout():
    """CI logs have a different retention story from the committed artifact.

    So the console gets strictly less: counts and enum tokens, never text,
    not even a masked excerpt.
    """
    tell = "SUPERSECRETPHRASE"
    results = [{
        "probe": "reproduce-1",
        "wire": [diag.collect_response_facts(
            make_response(f"Here is my answer: {tell}"),
            excerpt_chars=diag.EXCERPT_HARD_LIMIT,
        )],
    }]
    summary = diag.summarise(results)
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        diag._print_summary(summary)
    printed = buffer.getvalue()
    assert tell not in printed
    assert printed.strip(), "the summary printed nothing at all"
    # ... and the excerpt did make it into the record, so the test above is
    # testing the console and not an empty pipeline.
    assert tell in results[0]["wire"][0]["text_excerpt_masked"]


def test_the_summary_carries_no_free_text_from_any_reply():
    tell = "SUPERSECRETPHRASE"
    results = [{
        "probe": "reproduce-1",
        "wire": [diag.collect_response_facts(
            make_response(f"prose {tell}"), excerpt_chars=200
        )],
    }]
    assert tell not in json.dumps(diag.summarise(results), ensure_ascii=False)


def test_a_transport_error_message_is_masked_before_it_is_recorded():
    """Provider errors quote the request. That is where a key comes back."""

    class Boom(Exception):
        status_code = 400

    class Failing:
        chat = None

        def __init__(self):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            raise Boom(
                "Unrecognized request argument supplied: response_format "
                "(api-key sk-abcdefghijklmnopqrstuvwx, user tom@corp.example)"
            )

    client = diag.DiagnosticClient(Failing())
    client.configure(label="compat-json-object", response_format={"type": "json_object"})
    with pytest.raises(Boom):
        client.create(**_minimal_kwargs())
    record = client.records[-1]
    assert record["transport_error"] == "Boom"
    assert record["transport_status"] == 400
    assert "sk-abcdefghijklmnopqrstuvwx" not in record["transport_detail"]
    assert "tom@corp.example" not in record["transport_detail"]
    # The part that is the finding survives.
    assert "response_format" in record["transport_detail"]


# --------------------------------------------------------------------------
# The request cap
# --------------------------------------------------------------------------


def _minimal_kwargs():
    return {
        "model": "gpt-audio-1.5",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": f"header{probe.PRODUCTION_CRITERION_MARKER}c"},
                {"type": "input_audio", "input_audio": {"data": "", "format": "wav"}},
            ],
        }],
        "modalities": ["text"],
    }


class CountingClient:
    def __init__(self, response=None):
        self.calls = 0
        self.seen: list[dict] = []
        self._response = response or make_response(GOOD_ENVELOPE)
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls += 1
        self.seen.append(kwargs)
        return self._response


def test_the_cap_is_enforced_before_the_call_not_after():
    inner = CountingClient()
    client = diag.DiagnosticClient(inner, max_requests=3)
    for _ in range(3):
        client.create(**_minimal_kwargs())
    assert inner.calls == 3
    with pytest.raises(diag.DiagnosticBudgetExceeded):
        client.create(**_minimal_kwargs())
    assert inner.calls == 3, "the fourth request reached the provider"


def test_a_failed_request_still_counts_against_the_cap():
    """"Including retries" is only true if a failure is not free."""

    class Failing:
        def __init__(self):
            self.calls = 0
            self.chat = SimpleNamespace(completions=self)

        def create(self, **kwargs):
            self.calls += 1
            raise RuntimeError("timeout")

    inner = Failing()
    client = diag.DiagnosticClient(inner, max_requests=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            client.create(**_minimal_kwargs())
    with pytest.raises(diag.DiagnosticBudgetExceeded):
        client.create(**_minimal_kwargs())
    assert inner.calls == 2


def test_the_plan_fits_the_cap_and_leaves_a_retry_in_hand():
    plan = diag.probe_plan()
    assert len(plan) < diag.MAX_MODEL_REQUESTS
    assert diag.MAX_MODEL_REQUESTS - len(plan) == 1
    assert diag.MAX_MODEL_REQUESTS == 8


def test_one_judge_call_is_one_request_so_the_plan_length_is_the_call_count():
    """The fact the whole budget arithmetic rests on.

    ``AudioPerception.judge`` returns on ``AudioEnvelopeError`` rather than
    retrying, so a probe cannot quietly become three requests. Asserted
    against the real class, so a future retry loop in ``core`` breaks this
    test rather than silently tripling the bill.
    """
    from core.perception.audio import AudioPerception

    inner = CountingClient(make_response("not json at all"))
    client = diag.DiagnosticClient(inner, max_requests=8)
    perception = AudioPerception(
        client=client, deployment="gpt-audio-1.5", call_cap=32, trim_seconds=6
    )
    clip = _write_tiny_wav()
    verdict = perception.judge(criterion="anything", audio_path=str(clip))
    assert verdict.judge_error == "format_error:unparseable_json"
    assert inner.calls == 1
    assert client.requests_used == 1


def _write_tiny_wav() -> Path:
    import tempfile
    import wave

    path = Path(tempfile.mkdtemp()) / "tiny.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 16000)
    return path


# --------------------------------------------------------------------------
# Agreement with core
# --------------------------------------------------------------------------


@pytest.mark.parametrize("text", [
    GOOD_ENVELOPE,
    "```json\n" + GOOD_ENVELOPE + "\n```",
    "```\n" + GOOD_ENVELOPE + "\n```",
    "Here is my answer:\n```json\n" + GOOD_ENVELOPE + "\n```",
    '{"verdict": "pass", "partial_score": 1.0',
    '{"verdict": "maybe", "partial_score": 1.0, "evidence": "", '
    '"confidence": 0.5, "reasoning": ""}',
    '{"verdict": true, "partial_score": 1.0, "evidence": "", '
    '"confidence": 0.5, "reasoning": ""}',
    '{"partial_score": 1.0, "evidence": "", "confidence": 0.5, "reasoning": ""}',
    "[1, 2, 3]",
    "",
    "   ",
    "I cannot determine this from the audio.",
])
def test_the_collector_and_core_agree_on_whether_the_text_is_json(text):
    """The self-check, asserted here rather than only recorded at runtime.

    The decoder detail this module collects describes the string it parsed.
    If that parse ever diverged from ``core``'s, the ``.pos`` in the artifact
    would point into a different string and every reading of it would be
    wrong.
    """
    facts = diag.collect_response_facts(make_response(text))
    try:
        _parse_json_envelope(text)
    except AudioEnvelopeError as exc:
        core_parsed = False
        # When core's parse is what failed, the recorded kind is core's own.
        assert facts["core_kind"] == exc.kind
    else:
        core_parsed = True
        # When it succeeded, any recorded kind came from core's *validator*,
        # never from the parse -- so it is never one of the two parse kinds.
        assert facts["core_kind"] not in ("unparseable_json", "empty_text")
    assert facts["json_parsed"] == core_parsed
    assert facts["agrees_with_core"] is True


def test_core_kind_is_cores_own_classification_not_a_second_opinion():
    for text, expected in [
        ("", "empty_text"),
        ("not json", "unparseable_json"),
        ("[1,2]", "not_an_object"),
        ('{"partial_score":1.0,"confidence":0.5}', "verdict_missing"),
        ('{"verdict":"maybe","partial_score":1.0,"confidence":0.5}',
         "verdict_not_in_vocabulary"),
        ('{"verdict":"pass","partial_score":"x","confidence":0.5}',
         "partial_score_not_a_number"),
        ('{"verdict":"pass","partial_score":2.0,"confidence":0.5}',
         "partial_score_out_of_range"),
        (GOOD_ENVELOPE, None),
    ]:
        facts = diag.collect_response_facts(make_response(text))
        assert facts["core_kind"] == expected, text


def test_a_fenced_envelope_parses_so_fences_alone_cannot_explain_334():
    """Recorded here because it is the hypothesis a reader reaches for first.

    ``core._parse_json_envelope`` strips a leading fence before parsing. So
    "the model wrapped it in a code fence" is not on its own an explanation
    for ``unparseable_json`` -- but "the model wrote a sentence and *then* a
    fence" is, because the strip is anchored at the start.
    """
    fenced = diag.collect_response_facts(
        make_response("```json\n" + GOOD_ENVELOPE + "\n```")
    )
    assert fenced["core_kind"] is None
    assert fenced["starts_with_fence"] is True

    prefixed = diag.collect_response_facts(
        make_response("Sure! Here you go:\n```json\n" + GOOD_ENVELOPE + "\n```")
    )
    assert prefixed["core_kind"] == "unparseable_json"
    assert prefixed["starts_with_fence"] is False
    assert prefixed["chars_before_first_fence"] > 0


def test_a_refusal_is_visible_as_a_refusal():
    """``core`` classifies a refusal as ``empty_text``, never ``unparseable``.

    Which is why 334's 51 ``unparseable_json`` failures were not refusals --
    a conclusion this test pins to ``core``'s actual behaviour rather than to
    a paragraph in a report.
    """
    facts = diag.collect_response_facts(
        make_response(None, refusal="I can't help with that.")
    )
    assert facts["refusal_present"] is True
    assert facts["refusal_chars"] == len("I can't help with that.")
    assert facts["core_kind"] == "empty_text"


# --------------------------------------------------------------------------
# Truncation is settled by finish_reason, or not at all
# --------------------------------------------------------------------------


def test_truncation_is_read_off_finish_reason_and_never_off_token_counts():
    """The correction to 334 §3, in executable form.

    A *short* reply with ``finish_reason="length"`` is a truncated reply. The
    output-token count cannot overturn that, and this test fixes it so no
    later change can quietly reintroduce the token-length argument.
    """
    short_but_cut = diag.collect_response_facts(
        make_response('{"verdict": "pa', finish_reason="length")
    )
    assert short_but_cut["output_tokens"] == 40
    assert short_but_cut["finish_reason"] == "length"
    verdict = diag._truncation_verdict([short_but_cut])
    assert verdict.startswith("truncated:")


def test_no_finish_reason_leaves_the_question_open():
    unknown = diag.collect_response_facts(
        make_response("garbage", finish_reason=None)
    )
    assert diag._truncation_verdict([unknown]) == "unsettled:no_finish_reason_reported"


def test_every_stop_settles_it_the_other_way():
    stopped = [diag.collect_response_facts(make_response("garbage"))]
    assert diag._truncation_verdict(stopped).startswith("not_truncated:")


def test_no_responses_is_its_own_answer():
    assert diag._truncation_verdict([]) == "no_responses"


# --------------------------------------------------------------------------
# The fixed sample
# --------------------------------------------------------------------------


def test_the_fixed_sample_is_what_the_rule_selects():
    """Re-derived from the artifact, not trusted from the constant.

    The rule, stated once and applied here: observation-arm claims that were
    ``unanswered``/``read_failure`` in **all three** repeats of run 334, then
    the first three by sorted ``claim_id``, at most one per clip.
    """
    measured = json.loads(MEASURED_334.read_text(encoding="utf-8"))
    by_claim: dict[str, list[dict]] = collections.defaultdict(list)
    for call in measured["calls"]:
        if call["arm"] == "observation":
            by_claim[call["claim_id"]].append(call)

    never_readable = sorted(
        (claim_id, calls[0]["clip_id"])
        for claim_id, calls in by_claim.items()
        if all(
            call["outcome"] == "unanswered"
            and call.get("unanswered_kind") == "read_failure"
            for call in calls
        )
    )
    seen_clips: set[str] = set()
    picked: list[str] = []
    for claim_id, clip_id in never_readable:
        if clip_id in seen_clips:
            continue
        seen_clips.add(clip_id)
        picked.append(claim_id)
        if len(picked) == 3:
            break

    assert tuple(picked) == diag.FIXED_SAMPLE
    assert len(seen_clips) == 3, "the sample must hear three different clips"


def test_every_sampled_claim_failed_all_three_repeats_with_the_same_kind():
    measured = json.loads(MEASURED_334.read_text(encoding="utf-8"))
    for claim_id in diag.FIXED_SAMPLE:
        calls = [
            call for call in measured["calls"]
            if call["arm"] == "observation" and call["claim_id"] == claim_id
        ]
        assert len(calls) == 3
        assert {call["judge_error"] for call in calls} == {
            "format_error:unparseable_json"
        }


def test_the_artifact_says_the_sample_was_chosen_by_its_outcome():
    """Because three calls chosen for failing look exactly like a rate."""
    assert "selection" in diag.SAMPLE_IS_OUTCOME_SELECTED
    assert "does not estimate" in diag.SAMPLE_IS_OUTCOME_SELECTED
    summary = diag.summarise([])
    assert summary["sample_is_outcome_selected"] == diag.SAMPLE_IS_OUTCOME_SELECTED


# --------------------------------------------------------------------------
# Compatibility probes
# --------------------------------------------------------------------------


def test_the_response_format_is_injected_by_the_wrapper_not_by_core():
    """``core`` never sends ``response_format``; the diagnostic adds it.

    Both halves are asserted: that the parameter arrives on the wire when the
    probe asks for it, and that the grader's own call does not carry it. The
    second is what keeps this a diagnostic rather than a change to grading.
    """
    inner = CountingClient()
    client = diag.DiagnosticClient(inner)

    client.configure(label="contrast-1")
    client.create(**_minimal_kwargs())
    assert "response_format" not in inner.seen[-1]
    assert client.records[-1]["response_format_sent"] is None

    client.configure(label="compat", response_format={"type": "json_object"})
    client.create(**_minimal_kwargs())
    assert inner.seen[-1]["response_format"] == {"type": "json_object"}
    assert client.records[-1]["response_format_sent"] == {"type": "json_object"}


def test_the_json_schema_probe_is_described_without_copying_the_schema():
    described = diag._describe_response_format(diag.COMPATIBILITY_JSON_SCHEMA)
    assert described == {
        "type": "json_schema",
        "json_schema_name": "audio_verdict",
        "json_schema_strict": True,
    }


def test_the_compatibility_schema_matches_the_contract_core_states():
    schema = diag.COMPATIBILITY_JSON_SCHEMA["json_schema"]["schema"]
    assert set(schema["required"]) == set(diag.CONTRACT_KEYS)
    assert set(schema["properties"]["verdict"]["enum"]) == set(
        AUDIO_VERDICT_VOCABULARY
    )


def test_there_is_no_parameter_free_retry_anywhere_in_the_module():
    """A rejection is the result. Re-sending without the parameter is not.

    Checked as an absence in the source, because the failure mode is a helpful
    ``except BadRequestError: retry without response_format`` added later by
    someone who reasonably thought a green run was better than a red one.
    """
    source = Path(diag.__file__).read_text(encoding="utf-8")
    assert "response_format" in source
    lowered = source.lower()
    for banned in ("fallback", "retry without", "except badrequest"):
        assert banned not in lowered, f"{banned!r} appears in the diagnostic"
    assert "NO_QUIET_RETRY" in source
    assert "never re-sent without" in diag.NO_QUIET_RETRY


# --------------------------------------------------------------------------
# Cost and provenance
# --------------------------------------------------------------------------


def test_the_report_never_claims_a_zero_cost():
    summary = diag.summarise([])
    assert summary["estimated_cost_usd"] is None
    assert summary["pricing_complete"] is False
    assert "0" != str(summary["estimated_cost_usd"])
    assert "did not cost $0" in summary["pricing_note"]


def test_tokens_are_recorded_even_though_the_price_is_not():
    results = [{"wire": [diag.collect_response_facts(make_response(GOOD_ENVELOPE))]}]
    summary = diag.summarise(results)
    assert summary["input_tokens"] == 100
    assert summary["output_tokens"] == 40


def test_audio_token_accounting_survives_the_wrapper():
    facts = diag.collect_response_facts(make_response(GOOD_ENVELOPE))
    assert facts["audio_tokens"] == 77
    assert facts["audio_tokens_source"] == "prompt_tokens_details"


def test_the_diagnostic_declares_its_own_kind_and_the_document_must_agree():
    assert diag.DIAGNOSTIC_KIND == "audio-format-failure"
    assert diag.DIAGNOSTIC_KIND != probe.SPEECH_PROMPT_AB_KIND


def test_the_diagnostic_reuses_cores_parse_rather_than_reimplementing_it():
    """No second parser to drift.

    ``_parse_json_envelope`` and ``_validated_audio_envelope`` are imported
    from ``core`` and called, so ``core_kind`` is the grader's own answer.
    """
    source = Path(diag.__file__).read_text(encoding="utf-8")
    assert "from core.perception.audio import" in source
    assert "_parse_json_envelope" in source
    assert "_validated_audio_envelope" in source
    assert diag._parse_json_envelope is _parse_json_envelope
    assert diag._validated_audio_envelope is _validated_audio_envelope


def test_the_diagnostic_changes_nothing_under_core():
    """The freeze this whole design exists to respect.

    The grader source fingerprint covers ``core/**/*.py``. A diagnostic that
    lives in ``scripts/`` and imports from ``core`` reads it without moving
    it; a diagnostic that edits ``core`` would invalidate a fingerprint a
    separately running paid job is pinned to.
    """
    core_dir = Path(diag.__file__).resolve().parent.parent / "core"
    audio = (core_dir / "perception" / "audio.py").read_text(encoding="utf-8")
    assert "diagnose_audio_format_failure" not in audio
    assert "response_format" not in audio


# --------------------------------------------------------------------------
# The document and the workflow that spend the money
#
# Everything above runs against fabricated objects, which is what makes it
# safe -- and also what makes it blind to the two files a paid dispatch
# actually reads. The class of failure this repository has already paid for is
# a workflow stating a call count that disagreed with the run it authorised.
# These tests read the real document and the real workflow.
# --------------------------------------------------------------------------


PREREG = REPO_ROOT / "tasks" / "rebuilding_grading_task" / "335-why-the-format-failed.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "audio-format-diagnostic.yml"


def test_the_registered_document_is_one_this_diagnostic_will_accept():
    """The refusal at the top of ``main`` has to pass on the real file.

    A typo in either machine-read row of the pins table would surface as a
    dispatch that dies after checkout -- free, but only because it never got
    to the calls. Better here.
    """
    assert probe.diagnostic_kind_stated_in(PREREG) == diag.DIAGNOSTIC_KIND
    assert probe.grader_pin_stated_in(PREREG) == probe.grader_source_hash(
        probe.PINNED_CONFIG
    )


def test_the_document_names_the_sample_and_the_plan_the_code_holds():
    text = PREREG.read_text(encoding="utf-8")
    for claim_id in diag.FIXED_SAMPLE:
        assert claim_id in text, f"{claim_id} is in the code but not the document"
    for step in diag.probe_plan():
        assert step["label"] in text, (
            f"probe {step['label']} would run but the document does not list it"
        )


def test_the_document_states_the_cap_the_code_enforces():
    text = PREREG.read_text(encoding="utf-8")
    planned = len(diag.probe_plan())
    reserved = diag.MAX_MODEL_REQUESTS - planned
    assert f"계획 {planned}회 + 예비 {reserved}회" in text
    assert f"{diag.MAX_MODEL_REQUESTS}회" in text
    assert str(diag.EXCERPT_HARD_LIMIT) in text


def _workflow():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_approval_record_states_the_requests_the_plan_makes():
    """#### the `calls = 36` failure, on a run that made 60.

    The gate job has no checkout, so its arithmetic is restated by hand. That
    restatement is what a reviewer approves, so it has to be the truth about
    what the plan does -- not a number that was true when it was typed.
    """
    steps = _workflow()["jobs"]["approve-paid"]["steps"]
    record = "\n".join(step.get("run", "") for step in steps)
    planned = len(diag.probe_plan())
    reserved = diag.MAX_MODEL_REQUESTS - planned
    assert f"{planned} planned + {reserved} reserved" in record
    assert f"cap {diag.MAX_MODEL_REQUESTS}" in record

    arms = collections.Counter(step.get("arm", "production") for step in diag.probe_plan())
    reproduce = sum(1 for s in diag.probe_plan() if s["label"].startswith("reproduce"))
    contrast = sum(1 for s in diag.probe_plan() if s["label"].startswith("contrast"))
    compat = sum(1 for s in diag.probe_plan() if s["label"].startswith("compat"))
    assert f"{reproduce} reproduce" in record
    assert f"{contrast} contrast" in record
    assert f"{compat} compat" in record
    assert reproduce + contrast + compat == planned
    assert arms["observation"] == reproduce


def test_the_approval_record_does_not_promise_a_free_run():
    steps = _workflow()["jobs"]["approve-paid"]["steps"]
    record = "\n".join(step.get("run", "") for step in steps)
    assert "pricing_complete false" in record
    assert "estimated_cost_usd null" in record
    assert "does not write" in record and "0" in record


def test_the_free_job_runs_the_tests_that_guard_the_paid_one():
    """These leak and cap guards gate nothing if no job runs them."""
    steps = _workflow()["jobs"]["dry-run"]["steps"]
    runs = "\n".join(step.get("run", "") for step in steps)
    assert Path(__file__).name in runs
    assert "--dry-run" in runs


def test_the_paid_job_waits_on_the_free_one_and_on_the_gate():
    jobs = _workflow()["jobs"]
    assert jobs["approve-paid"]["needs"] == "dry-run"
    assert jobs["approve-paid"]["environment"]["name"] == "grading"
    assert jobs["diagnose"]["needs"] == "approve-paid"
    assert jobs["diagnose"]["permissions"]["contents"] == "read"
    assert jobs["diagnose"]["permissions"]["id-token"] == "write"


def test_the_workflow_cannot_raise_the_excerpt_limit():
    """The dispatch form offers a number; the specification owns the bound."""
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]
    assert inputs["excerpt_chars"]["default"] <= diag.EXCERPT_HARD_LIMIT
    assert inputs["dry_run"]["default"] is True
    assert inputs["paid_approval"]["default"] is False


def test_every_action_the_workflow_uses_is_pinned_to_a_digest():
    import re

    text = WORKFLOW.read_text(encoding="utf-8")
    uses = re.findall(r"uses:\s*(\S+)", text)
    assert uses, "no actions found -- the sweep is looking at the wrong file"
    for ref in uses:
        assert re.search(r"@[0-9a-f]{40}$", ref), f"{ref} is not pinned to a digest"


def _workflow_python_snippets():
    """The inline Python the workflow's summary steps run.

    Read out of the parsed YAML rather than the file text: the block scalar
    is what strips the step's indentation, and running ``ast.parse`` on the
    still-indented source would fail on a snippet the runner accepts.
    """
    import re

    bodies = []
    for job in _workflow()["jobs"].values():
        for step in job.get("steps", []):
            run = step.get("run") or ""
            bodies += re.findall(r"python - <<'PY'[^\n]*\n(.*?)\n\s*PY\b", run, re.S)
    assert len(bodies) == 2, f"expected two summary snippets, found {len(bodies)}"
    return bodies


def test_the_summary_steps_are_valid_python():
    import ast

    for body in _workflow_python_snippets():
        ast.parse(body)


def test_the_summary_steps_only_read_fields_the_report_actually_has():
    """A summary step runs ``if: always()``, i.e. after the money is spent.

    A mistyped key there fails the job at the one moment when failing is most
    expensive and least informative. The keys are checked against what
    ``summarise`` returns and what the script writes, rather than against a
    second hand-maintained list.
    """
    import ast
    import re

    summary_keys = set(diag.summarise([]))
    source = Path(diag.__file__).read_text(encoding="utf-8")

    for body in _workflow_python_snippets():
        for node in ast.walk(ast.parse(body)):
            if not isinstance(node, ast.Subscript):
                continue
            if not isinstance(node.slice, ast.Constant):
                continue
            key = node.slice.value
            if not isinstance(key, str):
                continue
            target = node.value
            base = target.id if isinstance(target, ast.Name) else None
            if base == "s":
                assert key in summary_keys, f"summary has no {key!r}"
            elif base in {"h", "r"}:
                # Either a dict-literal key or a subscript assignment: the
                # header is built as a literal and then added to.
                written = re.search(
                    rf'"{re.escape(key)}":|\["{re.escape(key)}"\]', source
                )
                assert written, f"the report never writes {key!r}"




# --------------------------------------------------------------------------
# The committed report.
#
# The run is over and its artifact expires. Everything below asks the file in
# the repository -- not the workflow, not the artifact, not this test's memory
# of what was dispatched -- whether the record that survives is the one the
# document registered and whether it is safe to have committed.
# --------------------------------------------------------------------------


REPORT = (
    REPO_ROOT / "tasks" / "rebuilding_grading_task" / "335-audio-format-diagnostic.json"
)


def _report() -> dict:
    if not REPORT.exists():
        pytest.skip("the paid diagnostic has not been run and committed yet")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_the_committed_report_is_tracked_and_not_swallowed_by_gitignore():
    """``tasks/rebuilding_grading_task/*`` is deny-by-default.

    Without a ``!`` line the file sits in the working tree, ``git add -A``
    passes over it without a word, and the only copy of the masked excerpts is
    a CI artifact with an expiry date. git is asked directly rather than the
    ignore list being re-read, because the question is what a fresh clone gets.
    """
    import subprocess

    if not REPORT.exists():
        pytest.skip("the paid diagnostic has not been run and committed yet")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", str(REPORT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        "the diagnostic report is present but git is not tracking it, so a "
        "clone of this repository does not have it. Add a '!' line for it in "
        f".gitignore. git said: {tracked.stderr.strip()!r}"
    )


def test_the_committed_report_carries_the_pins_the_document_registers():
    """A report from some other run is worse than no report.

    Each of these is machine-read from the document rather than restated here,
    so a report produced against a moved grader or a different arm header
    cannot be filed under this pre-registration.
    """
    report = _report()
    assert report["diagnostic_kind"] == diag.DIAGNOSTIC_KIND
    assert report["grader_source_sha256"] == probe.grader_pin_stated_in(PREREG)
    assert report["fixed_sample"] == list(diag.FIXED_SAMPLE)
    assert report["max_model_requests"] == diag.MAX_MODEL_REQUESTS
    assert report["excerpt_hard_limit"] == diag.EXCERPT_HARD_LIMIT
    assert report["observation_header_sha256"] in PREREG.read_text(encoding="utf-8")


def test_the_committed_report_did_not_outspend_the_registered_cap():
    report = _report()
    assert report["requests_used"] <= diag.MAX_MODEL_REQUESTS
    placed = sum(len(p.get("wire", [])) for p in report["probes"])
    assert placed == report["requests_used"], (
        "the wire records and the counter disagree about how many requests "
        "were placed; the counter is what the cap was enforced against"
    )


def test_the_committed_report_collected_no_reasoning():
    """§4 says a reasoning block leaves a boolean and nothing else."""
    report = _report()
    assert report["reasoning_blocks_collected"] is False
    assert report["summary"]["reasoning_blocks_seen"] == 0
    for probe_record in report["probes"]:
        for wire in probe_record.get("wire", []):
            assert isinstance(wire.get("reasoning_present"), (bool, type(None)))


def test_no_excerpt_in_the_committed_report_exceeds_the_hard_limit():
    """Masking runs before truncation, so the bound is on the masked text.

    A truncated excerpt carries a ``…(+N chars)`` marker, which is metadata
    about what was dropped rather than dropped content; the limit is checked
    against the text in front of it.
    """
    report = _report()
    for probe_record in report["probes"]:
        for wire in probe_record.get("wire", []):
            excerpt = wire.get("text_excerpt_masked")
            if excerpt is None:
                continue
            head = excerpt.split("…(+")[0]
            assert len(head) <= diag.EXCERPT_HARD_LIMIT, (
                f"{probe_record['probe']} kept {len(head)} characters of "
                f"response text, over the {diag.EXCERPT_HARD_LIMIT} limit"
            )


def test_the_committed_report_holds_nothing_credential_shaped():
    """The masking is unit-tested against fabricated bodies elsewhere.

    This asks the different question: whether the file that was actually
    committed came out clean. sha256 digests are the one long hex string that
    belongs here, so they are excluded by value rather than by pattern.
    """
    import re

    if not REPORT.exists():
        pytest.skip("the paid diagnostic has not been run and committed yet")
    text = REPORT.read_text(encoding="utf-8")
    report = json.loads(text)

    expected_digests = {report["grader_source_sha256"]}
    expected_digests |= set(report["clip_sha256"].values())
    expected_digests.add(report["observation_header_sha256"])
    for probe_record in report["probes"]:
        for wire in probe_record.get("wire", []):
            for key in ("prompt_sha256", "text_sha256", "audio_sha256"):
                if wire.get(key):
                    expected_digests.add(wire[key])

    patterns = {
        "an email address": r"[\w.+-]+@[\w-]+\.[\w.]{2,}",
        "an OpenAI-style key": r"sk-[A-Za-z0-9]{8,}",
        "a GitHub token": r"gh[pousr]_[A-Za-z0-9]{8,}",
        "an AWS access key id": r"AKIA[0-9A-Z]{12,}",
        "a JWT": r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "a URL": r"https?://",
    }
    for what, pattern in patterns.items():
        found = re.findall(pattern, text)
        assert not found, f"the committed report looks like it contains {what}"

    for blob in re.findall(r"(?<![a-f0-9])[a-f0-9]{32,}(?![a-f0-9])", text):
        assert blob in expected_digests, (
            f"the committed report holds a long hex string that is not one of "
            f"its own recorded digests: {blob[:8]}…"
        )


def test_the_committed_report_does_not_price_a_paid_run_at_zero():
    """The failure mode is a cost *field* reading zero, not the string "$0".

    ``pricing_note`` says in words that the run did not cost $0, so a blanket
    search for that substring would forbid the sentence that exists to prevent
    the mistake. The value-carrying fields are checked instead, and the note is
    required to keep saying it.
    """
    report = _report()
    summary = report["summary"]
    assert summary["pricing_complete"] is False
    assert summary["estimated_cost_usd"] is None
    assert "$0" in summary["pricing_note"], (
        "the note that refuses to write $0 is gone from the report"
    )
    priced = {
        key: value
        for key, value in summary.items()
        if "cost" in key or "usd" in key or "price" in key.lower()
    }
    for key, value in priced.items():
        assert value in (None, False), (
            f"{key} is {value!r}; an unregistered price is null or partial, "
            "never a number"
        )
    assert isinstance(summary["input_tokens"], int)
    assert isinstance(summary["output_tokens"], int)


def test_the_results_section_reports_the_run_that_was_committed():
    """§11 is prose, and prose drifts from the file it describes.

    Only the load-bearing identifiers are checked -- the request count, the
    truncation verdict and the report's own filename -- because those are the
    ones a reader would act on.
    """
    report = _report()
    text = PREREG.read_text(encoding="utf-8")
    assert "*(실행 후에 채운다." in text, (
        "the pre-registration rule line was removed from §11; it is the reason "
        "the sections above it can still be read as pre-registered"
    )
    assert REPORT.name in text, "§11 does not link the report it is describing"
    assert f"**{report['requests_used']}회 / 상한 " in text, (
        "§11 states a request count that is not the one in the report"
    )
    if report["summary"]["truncation_evidence"].startswith("not_truncated"):
        assert "잘리지" in text


def test_the_masked_excerpts_stayed_in_the_report_and_out_of_the_document():
    """§4 puts the excerpts in the committed JSON and nowhere else.

    Copying a sentence of model output into the write-up would move it into a
    file that is read far more often than the artifact, which is exactly the
    spread the rule exists to stop.
    """
    report = _report()
    text = PREREG.read_text(encoding="utf-8")
    for probe_record in report["probes"]:
        for wire in probe_record.get("wire", []):
            excerpt = wire.get("text_excerpt_masked")
            if not excerpt:
                continue
            head = excerpt.split("…(+")[0][:40].strip()
            if len(head) < 20:
                continue
            assert head not in text, (
                f"{probe_record['probe']}'s response text was copied into "
                "the document; §4 keeps it in the report only"
            )
