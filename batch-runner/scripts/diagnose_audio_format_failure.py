#!/usr/bin/env python3
"""Why did 51 of 60 observation-arm replies fail to parse as JSON?

``334-the-arm-that-broke-the-format.md`` reports the fact and cannot explain
it, for one reason: **the run stored no response bodies.** Every reply was
classified by ``core.perception.audio`` into ``format_error:unparseable_json``
and then discarded. What was actually wrong with those replies is therefore
not in the artifact, and no amount of re-reading it will put it there.

This module is the smallest thing that can put it there. It is a
**diagnostic**, not a measurement:

* It reproduces a *known* failure on an outcome-selected sample. That is a
  legitimate way to see a defect and an illegitimate way to estimate a rate.
  Nothing here reports a rate, and :data:`SAMPLE_IS_OUTCOME_SELECTED` says so
  in the artifact so a later reader cannot mistake three calls for a survey.
* It is capped at :data:`MAX_MODEL_REQUESTS` requests **including retries**.
  The cap is enforced in the client wrapper, before the call, so it binds
  whatever the caller does.
* It does not change ``core/``. The interception point is the client the
  grader was already handed, so the production request assembly, the
  production prompt and the production parse all run untouched -- and the
  grader source fingerprint another running job is pinned to does not move.

What it collects and what it refuses to collect
-----------------------------------------------

Collected by default: **structural metadata only.** ``finish_reason``, whether
a refusal field is present and how long it is, the Python type of the content,
text length and digest, code-fence facts, brace counts, the
``json.JSONDecodeError`` message and position, which of the five contract keys
are present and what JSON type each holds, and the token counts.

Never collected, at any setting: the model's reasoning or thinking blocks.
:func:`collect_response_facts` reads ``message.content`` and
``message.audio.transcript`` and nothing else; a reasoning block contributes
one boolean, ``reasoning_present``, and its content is never touched.

Collected only when asked for, and only then: a **masked, length-limited
excerpt** of the reply text. Off unless ``--excerpt-chars`` is passed. Bounded
by :data:`EXCERPT_HARD_LIMIT`. Masked by :func:`mask_text` before it is
truncated, never after, so a truncation can never cut a mask in half and spill
what the mask was covering. It is permissible here for one narrow reason: the
inputs are fixed synthetic eSpeak clips with no personal content, so the
model's reply is about a sentence this repository wrote. It would not be
permissible on a real deliverable.

The output token count is not evidence about truncation
-------------------------------------------------------

334 §3 argued the failing replies were not truncated because they were
*shorter* than the passing ones. That is an inference from a proxy, and this
module deliberately does not repeat it: ``finish_reason`` is the field the
provider uses to say a reply was cut off, and it is recorded here as the only
thing allowed to settle that question. A short reply with
``finish_reason="length"`` is a truncated reply.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.cost_metering import read_reported_usage, resolved_model_of  # noqa: E402
from core.perception.audio import (  # noqa: E402
    AUDIO_VERDICT_VOCABULARY,
    AudioEnvelopeError,
    AudioPerception,
    _parse_json_envelope,
    _validated_audio_envelope,
)

import measure_audio_grading_accuracy as probe  # noqa: E402


# --------------------------------------------------------------------------
# What this run is allowed to do, fixed before it runs
# --------------------------------------------------------------------------

#: Total model requests this diagnostic may place, **retries included**.
#:
#: Not a spend limit -- a reproduction limit. Eight calls is enough to see a
#: failure that reproduced 51 times out of 60 and not enough to go looking for
#: a different one if it does not. If the failure does not appear in the fixed
#: sample, the honest report is "did not reproduce", not a ninth call.
MAX_MODEL_REQUESTS = 8

#: What a pre-registration has to call itself before this run will use it,
#: read out of the document's own table by
#: ``probe.diagnostic_kind_stated_in``. Same mechanism the A/B used: pointing
#: a command line at a file does not make that file a pre-registration.
DIAGNOSTIC_KIND = "audio-format-failure"

#: The claims this diagnostic replays, hard-coded so the sample cannot drift
#: toward whichever call happened to be interesting.
#:
#: Derived once, by a stated rule, from ``334-audio-accuracy-measured.json``:
#: observation-arm claims that were ``unanswered/read_failure`` in **all three**
#: repeats -- 13 of the 20 qualify -- then the first three by sorted
#: ``claim_id``, at most one per clip so three different voices are heard.
#: ``test_the_fixed_sample_is_what_the_rule_selects`` re-derives it from the
#: artifact and fails if this tuple stops matching.
FIXED_SAMPLE = ("boxes_four_blue", "column_second", "crate_seventeen")

#: Stamped into the artifact next to every count.
#:
#: These three claims were chosen *because* they failed. Any statistic
#: computed over them describes the selection, not the arm, and a reader three
#: months from now will not remember that unless the file says so.
SAMPLE_IS_OUTCOME_SELECTED = (
    "These claims were selected because they failed in run 334, so counts "
    "over them measure the selection and not the arm. This diagnostic "
    "reproduces a known failure in order to see it. It does not estimate how "
    "often it happens; 334 already did that on a pre-registered sample."
)

#: The hardest cap on a published excerpt. ``--excerpt-chars`` may ask for
#: less and may not ask for more.
EXCERPT_HARD_LIMIT = 240

#: The five keys the response contract demands. Their presence and JSON type
#: are structural facts about the reply; their *values* are not collected.
CONTRACT_KEYS = ("verdict", "partial_score", "evidence", "confidence", "reasoning")

#: Response-object attributes that hold model reasoning under one name or
#: another. This module records that they exist and never reads them.
REASONING_ATTRS = ("reasoning", "reasoning_content", "thinking", "thought")

#: A ``finish_reason`` is a short provider token. Anything that is not one is
#: reported as its shape rather than echoed, so a provider that returned prose
#: in that field cannot use it as a channel into the artifact.
_FINISH_REASON = re.compile(r"^[a-z_][a-z0-9_]{0,31}$")


class DiagnosticBudgetExceeded(RuntimeError):
    """Raised instead of placing request :data:`MAX_MODEL_REQUESTS` + 1."""


# --------------------------------------------------------------------------
# Masking
# --------------------------------------------------------------------------

#: Ordered, and the order is the point. Emails before URLs, because an email
#: inside a ``mailto:`` should not be half-covered by the URL rule; long
#: opaque runs last, so a key that also looks like a hex blob is already gone.
_MASKS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    (re.compile(r"\b(?:https?|ftp|file)://\S+", re.IGNORECASE), "<url>"),
    (re.compile(r"\bwww\.[A-Za-z0-9.-]+\.[A-Za-z]{2,}\S*"), "<url>"),
    (re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}"), "<secret>"),
    (re.compile(r"\b(?:AKIA|ASIA|ghp|gho|ghs|ghu|github_pat)[A-Za-z0-9_]{8,}"),
     "<secret>"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.?[A-Za-z0-9_-]*"),
     "<secret>"),
    (re.compile(r"\+?\d[\d ()-]{8,}\d"), "<digits>"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "<opaque>"),
    (re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"), "<opaque>"),
    (re.compile(r"\d{7,}"), "<digits>"),
)


def mask_text(value: Any) -> str:
    """Cover anything that looks like an identifier, a secret or a contact.

    Type-tolerant on purpose. A provider SDK that returns a ``dict`` or a
    model object where a string was expected must not reach the artifact by
    way of ``str()`` on an object whose ``__repr__`` embeds the payload, so
    anything that is not already a ``str`` is reduced to its type name and
    stops there.
    """
    if isinstance(value, str):
        text = value
    elif value is None:
        return "<none>"
    else:
        return f"<{type(value).__name__}>"
    for pattern, replacement in _MASKS:
        text = pattern.sub(replacement, text)
    return text


def masked_excerpt(value: Any, limit: int) -> str | None:
    """A masked head of ``value``, or ``None`` when excerpts are off.

    Masked first and truncated second. The other order is the bug: cutting a
    24-character key at character 12 leaves 12 characters of key in the file,
    and the mask that would have covered it never matched because the pattern
    needed the tail.
    """
    if limit <= 0:
        return None
    if limit > EXCERPT_HARD_LIMIT:
        raise ValueError(
            f"excerpt limit {limit} exceeds the hard limit "
            f"{EXCERPT_HARD_LIMIT}; the spec fixes this bound before the run "
            f"and a command line does not get to raise it"
        )
    text = mask_text(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"…(+{len(text) - limit} chars)"


# --------------------------------------------------------------------------
# Reading a response without reading the model's mind
# --------------------------------------------------------------------------


def _attr(obj: Any, name: str) -> Any:
    """``getattr`` that also works on the dict form some SDKs return."""
    value = getattr(obj, name, None)
    if value is None and isinstance(obj, Mapping):
        value = obj.get(name)
    return value


def _finish_reason_token(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return f"<{type(value).__name__}>"
    lowered = value.strip().lower()
    return lowered if _FINISH_REASON.match(lowered) else "<non-token>"


def _fence_facts(text: str) -> dict[str, Any]:
    """What a code fence, if any, did to the reply.

    Worth measuring because ``core._parse_json_envelope`` already strips a
    leading fence, so "the model wrapped it in ```json" is **not** on its own
    an explanation for ``unparseable_json``. Prose *before* a fence is,
    because the strip is anchored at the start of the text. These fields let
    the artifact tell those two apart instead of leaving a reader to assume.
    """
    stripped = text.strip()
    first = stripped.find("```")
    tag = None
    if first >= 0:
        line_end = stripped.find("\n", first)
        candidate = stripped[first + 3: line_end if line_end >= 0 else len(stripped)]
        candidate = candidate.strip()
        tag = candidate[:16] if candidate else ""
        if tag and not re.match(r"^[A-Za-z0-9_+-]{0,16}$", tag):
            tag = "<non-token>"
    return {
        "starts_with_fence": stripped.startswith("```"),
        "fence_markers": stripped.count("```"),
        "first_fence_offset": first if first >= 0 else None,
        "fence_language_tag": tag,
        "chars_before_first_fence": first if first > 0 else (0 if first == 0 else None),
    }


def _shape_facts(text: str) -> dict[str, Any]:
    stripped = text.strip()
    first_brace = stripped.find("{")
    return {
        "first_non_ws_char": _safe_char(stripped[:1]),
        "last_non_ws_char": _safe_char(stripped[-1:]),
        "brace_open": stripped.count("{"),
        "brace_close": stripped.count("}"),
        "braces_balanced": stripped.count("{") == stripped.count("}"),
        "first_brace_offset": first_brace if first_brace >= 0 else None,
        "chars_before_first_brace": first_brace if first_brace > 0 else (
            0 if first_brace == 0 else None
        ),
    }


def _safe_char(char: str) -> str | None:
    """One character of the reply, only when it is punctuation or a letter.

    A single character is a shape fact, not content -- but only if it cannot
    be a whole answer. Letters and digits pass as themselves because ``{`` vs
    ``I`` vs ``"`` is exactly the distinction being drawn; anything outside
    printable ASCII is reported by codepoint so an unusual byte is visible
    without being reproduced.
    """
    if not char:
        return None
    if " " <= char <= "~":
        return char
    return f"U+{ord(char):04X}"


def _json_error_facts(text: str) -> dict[str, Any]:
    """The decoder's own account of what went wrong and where.

    ``core`` catches ``json.JSONDecodeError`` and re-raises
    ``AudioEnvelopeError("unparseable_json")``, dropping ``.msg``, ``.pos``,
    ``.lineno`` and ``.colno`` on the floor. Those four fields are the
    difference between "the reply was not JSON" and "the reply was JSON that
    stopped at character 51 of line 1" -- which is to say, the difference
    between no diagnosis and a diagnosis.

    The same fence-stripping ``core`` performs is applied first, so this is
    the error ``core`` saw and not a different one from a different input.
    """
    out: dict[str, Any] = {
        "json_parsed": False,
        "json_error_type": None,
        "json_error_msg": None,
        "json_error_pos": None,
        "json_error_lineno": None,
        "json_error_colno": None,
        "json_error_chars_remaining": None,
    }
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()
    try:
        json.loads(candidate)
    except json.JSONDecodeError as exc:
        out.update(
            json_error_type="JSONDecodeError",
            # ``.msg`` is decoder text ("Expecting ',' delimiter"), not model
            # text. It names a class of syntax error and quotes nothing.
            json_error_msg=str(exc.msg)[:120],
            json_error_pos=exc.pos,
            json_error_lineno=exc.lineno,
            json_error_colno=exc.colno,
            json_error_chars_remaining=max(len(candidate) - exc.pos, 0),
        )
    except ValueError as exc:  # pragma: no cover - json raises the subclass
        out.update(json_error_type=type(exc).__name__)
    else:
        out["json_parsed"] = True
    return out


def _contract_key_facts(payload: Any) -> dict[str, Any]:
    """Which required keys arrived and what JSON type each carried.

    Types, not values -- with one exception. ``verdict`` is checked for
    *membership* in the fixed four-word vocabulary and reported as a boolean,
    because "the model said a word that is not one of the four" is the single
    most likely shape of this defect and a boolean answers it without
    publishing the word. When the word itself is needed, ``core``'s own
    ``AudioEnvelopeError.detail`` already carries it through
    ``_offending_token``, which bounds it to a safe token or ``<non-token>``.
    """
    if not isinstance(payload, Mapping):
        return {
            "payload_type": type(payload).__name__,
            "keys_present": [],
            "keys_missing": list(CONTRACT_KEYS),
            "key_types": {},
            "extra_key_count": 0,
            "verdict_in_vocabulary": None,
        }
    present = [key for key in CONTRACT_KEYS if key in payload]
    verdict = payload.get("verdict")
    return {
        "payload_type": "dict",
        "keys_present": present,
        "keys_missing": [key for key in CONTRACT_KEYS if key not in payload],
        "key_types": {key: type(payload[key]).__name__ for key in present},
        "extra_key_count": sum(1 for key in payload if key not in CONTRACT_KEYS),
        "verdict_in_vocabulary": (
            verdict.strip().lower() in AUDIO_VERDICT_VOCABULARY
            if isinstance(verdict, str)
            else False
        ),
    }


def _text_and_source(message: Any) -> tuple[str, str]:
    """The assistant text ``core`` would read, and which field it came from.

    Deliberately the same two fields ``core._first_choice_text`` reads, in the
    same order, and no third one. Reading somewhere ``core`` does not look
    would produce a diagnosis of a reply the grader never saw.
    """
    content = _attr(message, "content")
    if content:
        return str(content), "content"
    audio = _attr(message, "audio")
    if audio is not None:
        transcript = _attr(audio, "transcript")
        if transcript:
            return str(transcript), "audio_transcript"
    return "", "none"


def collect_response_facts(
    response: Any, *, excerpt_chars: int = 0
) -> dict[str, Any]:
    """Everything structural about one reply, and nothing about its meaning.

    Total-function by construction: every branch of a malformed response ends
    in a recorded field rather than an exception. A diagnostic that crashes on
    the defect it was written to describe has described nothing.
    """
    facts: dict[str, Any] = {"excerpts_enabled": excerpt_chars > 0}

    choices = _attr(response, "choices") or []
    facts["choice_count"] = len(choices)
    if not choices:
        facts.update(
            finish_reason=None,
            refusal_present=False,
            text_source="none",
            text_chars=0,
            core_kind="empty_text",
        )
        return facts

    choice = choices[0]
    facts["finish_reason"] = _finish_reason_token(_attr(choice, "finish_reason"))
    facts["content_filter_present"] = _attr(choice, "content_filter_results") is not None

    message = _attr(choice, "message")
    if message is None:
        facts.update(
            refusal_present=False,
            text_source="none",
            text_chars=0,
            core_kind="empty_text",
        )
        return facts

    # A refusal is a *different* defect from an unparseable reply, and the two
    # cannot be confused after the fact: ``core._first_choice_text`` returns
    # "" for a refusal, so a refused call is classified ``empty_text``. That
    # this run's 51 failures were ``unparseable_json`` already rules refusal
    # out on paper; recording the field turns "on paper" into "measured".
    refusal = _attr(message, "refusal")
    facts["refusal_present"] = bool(refusal)
    facts["refusal_chars"] = len(str(refusal)) if refusal else 0

    content = _attr(message, "content")
    facts["content_present"] = content is not None
    facts["content_type"] = type(content).__name__ if content is not None else None
    audio = _attr(message, "audio")
    facts["audio_field_present"] = audio is not None
    facts["audio_transcript_present"] = bool(
        _attr(audio, "transcript") if audio is not None else None
    )

    # Presence only. The block is never read, never hashed, never excerpted.
    facts["reasoning_present"] = any(
        _attr(message, name) is not None for name in REASONING_ATTRS
    )

    text, source = _text_and_source(message)
    facts["text_source"] = source
    facts["text_chars"] = len(text)
    facts["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    facts.update(_fence_facts(text))
    facts.update(_shape_facts(text))
    facts.update(_json_error_facts(text))

    # ``core``'s own verdict on the same string, so the artifact reports what
    # the grader decided rather than a second opinion that could disagree
    # with it. The detail field is ``core``'s, already bounded by
    # ``_offending_token``.
    payload: Any = None
    try:
        payload = _parse_json_envelope(text)
    except AudioEnvelopeError as exc:
        facts["core_kind"] = exc.kind
        facts["core_detail"] = exc.detail
    else:
        try:
            _validated_audio_envelope(payload)
        except AudioEnvelopeError as exc:
            facts["core_kind"] = exc.kind
            facts["core_detail"] = exc.detail
        else:
            facts["core_kind"] = None
            facts["core_detail"] = None
    facts.update(_contract_key_facts(payload))

    # The self-check. This module re-runs ``json.loads`` to get the decoder
    # detail ``core`` discards; if that second parse ever disagreed with
    # ``core``'s about *whether* the text is JSON, the detail would be
    # describing a different string and every conclusion drawn from it would
    # be wrong. Recorded per call rather than asserted, because the finding
    # "the diagnostic disagrees with the grader" is itself worth seeing.
    facts["agrees_with_core"] = facts["json_parsed"] == (
        facts["core_kind"] not in ("unparseable_json", "empty_text")
    )

    usage = read_reported_usage(response)
    facts.update(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cached_tokens=usage.cached_tokens,
        usage_complete=usage.usage_complete,
    )
    facts.update(probe._audio_usage_facts(response))

    excerpt = masked_excerpt(text, excerpt_chars)
    if excerpt is not None:
        facts["text_excerpt_masked"] = excerpt
    return facts


# --------------------------------------------------------------------------
# The client wrapper: budget, arm, response_format, collection
# --------------------------------------------------------------------------


class DiagnosticClient:
    """Sits between ``AudioPerception`` and the provider and watches.

    One wrapper rather than four, because they all need the same single
    interception point: the arm swap has to happen where the recorder can see
    it, the ``response_format`` injection has to happen after the arm swap,
    and the budget has to be decremented before either. Split them and the
    artifact could no longer say what any individual request carried.

    ``core`` is not touched. ``AudioPerception`` is handed this object as its
    ``client`` and calls ``self.client.chat.completions.create(**kwargs)``
    exactly as it always does.
    """

    def __init__(
        self,
        inner: Any,
        *,
        max_requests: int = MAX_MODEL_REQUESTS,
        excerpt_chars: int = 0,
    ) -> None:
        self._inner = inner
        self._max_requests = int(max_requests)
        self._excerpt_chars = int(excerpt_chars)
        self.requests_used = 0
        self.records: list[dict[str, Any]] = []
        #: Set per probe by :meth:`configure`, never by the caller mid-flight.
        self.arm = "production"
        self.observation_header = probe.SPEECH_OBSERVATION_HEADER
        self.response_format: Any = None
        self.probe_label = "unlabelled"
        self.chat = type("_Chat", (), {"completions": self})()

    # -- probe setup -------------------------------------------------------

    def configure(
        self,
        *,
        label: str,
        arm: str = "production",
        response_format: Any = None,
    ) -> None:
        if arm not in probe.PROMPT_ARMS:
            raise ValueError(f"unknown prompt arm: {arm}")
        self.probe_label = label
        self.arm = arm
        self.response_format = response_format

    @property
    def requests_remaining(self) -> int:
        return max(self._max_requests - self.requests_used, 0)

    # -- the wire ----------------------------------------------------------

    def create(self, **kwargs: Any) -> Any:
        # Counted before the call and never given back. "Including retries"
        # is only true if a request that failed still counts, and a request
        # that timed out may well have run.
        if self.requests_used >= self._max_requests:
            raise DiagnosticBudgetExceeded(
                f"this diagnostic is capped at {self._max_requests} model "
                f"requests including retries and has used all of them; "
                f"probe '{self.probe_label}' is not being sent. A failure "
                f"that did not reproduce inside the cap is reported as not "
                f"reproduced, not chased with a ninth call."
            )
        self.requests_used += 1

        sent = probe.apply_arm(
            kwargs, self.arm, observation_header=self.observation_header
        )
        if self.response_format is not None:
            # Injected here, and *named* in the record. This is a diagnostic
            # adding a parameter the grader does not send -- which is the
            # whole point of the compatibility probe -- and the artifact has
            # to make that visible rather than let it read as production
            # behaviour.
            sent = {**sent, "response_format": self.response_format}

        record: dict[str, Any] = {
            "probe": self.probe_label,
            "arm": self.arm,
            "request_index": self.requests_used,
            "response_format_sent": _describe_response_format(self.response_format),
        }
        record.update(probe.WireClient._inspect(sent))
        for message in sent["messages"]:
            for part in message["content"]:
                if part.get("type") == "text":
                    record["prompt_chars"] = len(part["text"])
                    record["prompt_sha256"] = hashlib.sha256(
                        part["text"].encode("utf-8")
                    ).hexdigest()
        record["requested_model"] = sent.get("model")

        started = time.perf_counter()
        try:
            response = self._inner.chat.completions.create(**sent)
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            record["latency_ms"] = (time.perf_counter() - started) * 1000.0
            record["transport_error"] = type(exc).__name__
            record["transport_status"] = _status_code_of(exc)
            # The provider's own words about *which parameter* it rejected are
            # the finding a compatibility probe exists to produce, so the
            # message is kept -- masked, bounded, and only ever from an error
            # object. It is not model output.
            record["transport_detail"] = masked_excerpt(str(exc), 200)
            self.records.append(record)
            raise
        record["latency_ms"] = (time.perf_counter() - started) * 1000.0
        record["response_model"] = resolved_model_of(
            response, str(sent.get("model") or "")
        )
        record.update(
            collect_response_facts(response, excerpt_chars=self._excerpt_chars)
        )
        self.records.append(record)
        return response


def _describe_response_format(value: Any) -> Any:
    """What was asked for, without copying a whole schema into the artifact."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        described: dict[str, Any] = {"type": value.get("type")}
        schema = value.get("json_schema")
        if isinstance(schema, Mapping):
            described["json_schema_name"] = schema.get("name")
            described["json_schema_strict"] = schema.get("strict")
        return described
    return f"<{type(value).__name__}>"


def _status_code_of(exc: Exception) -> int | None:
    for name in ("status_code", "http_status", "code"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) else None


# --------------------------------------------------------------------------
# The probe plan, fixed before the run
# --------------------------------------------------------------------------

#: A schema tight enough to be worth asking for and loose enough that the
#: model failing it would be a real finding rather than a technicality. The
#: five keys the response contract already demands, no more.
COMPATIBILITY_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "audio_verdict",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": list(CONTRACT_KEYS),
            "properties": {
                "verdict": {"type": "string", "enum": sorted(AUDIO_VERDICT_VOCABULARY)},
                "partial_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "evidence": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "reasoning": {"type": "string"},
            },
        },
    },
}


def probe_plan() -> tuple[dict[str, Any], ...]:
    """Seven requests, named in advance, plus one held back.

    The three reproduction probes come first so that a budget spent on a
    transport failure is spent on the question this diagnostic is for.
    Two production probes on the same claims are the contrast arm: they show
    the collector reporting a clean parse on a reply that parses, which is
    what stops "the collector manufactures failures" from being an available
    reading. Two compatibility probes answer a separate question --
    ``334`` §10 item 3 -- and are last because they are the least load-bearing.

    The eighth request is reserved for exactly one retry of exactly one probe
    that failed **at the transport**, i.e. produced no response body to read.
    It is not available for a probe that answered in a way that was not
    interesting.
    """
    return (
        {"label": "reproduce-1", "claim_id": FIXED_SAMPLE[0], "arm": "observation"},
        {"label": "reproduce-2", "claim_id": FIXED_SAMPLE[1], "arm": "observation"},
        {"label": "reproduce-3", "claim_id": FIXED_SAMPLE[2], "arm": "observation"},
        {"label": "contrast-1", "claim_id": FIXED_SAMPLE[0], "arm": "production"},
        {"label": "contrast-2", "claim_id": FIXED_SAMPLE[1], "arm": "production"},
        {
            "label": "compat-json-object",
            "claim_id": FIXED_SAMPLE[0],
            "arm": "production",
            "response_format": {"type": "json_object"},
        },
        {
            "label": "compat-json-schema",
            "claim_id": FIXED_SAMPLE[0],
            "arm": "production",
            "response_format": COMPATIBILITY_JSON_SCHEMA,
        },
    )


#: Said in the artifact, because it is the rule most easily broken by a
#: helpful reflex. A provider that rejects ``response_format`` alongside
#: ``input_audio`` has answered the compatibility question -- with "no". A
#: re-run without the parameter would succeed and would be evidence of
#: nothing except that the parameter was removed.
NO_QUIET_RETRY = (
    "A compatibility probe that is rejected is never re-sent without the "
    "parameter that was rejected. The rejection is the result. Reporting a "
    "parameter-free retry as 'supported' would be a fabrication."
)


def run_probes(
    plan: Sequence[Mapping[str, Any]],
    *,
    client: DiagnosticClient,
    perception_for: Any,
    claims_by_id: Mapping[str, Any],
    clip_paths: Mapping[str, Path],
) -> list[dict[str, Any]]:
    """Execute the plan through ``core``'s own judge, one request each.

    ``AudioPerception.judge`` places exactly one request per call -- it
    returns on ``AudioEnvelopeError`` rather than retrying -- so the plan's
    length is the request count, and the wrapper's counter proves it rather
    than this docstring.

    ``perception_for`` builds a fresh ``AudioPerception`` per probe. A reused
    one carries ``_calls_used`` and ``_blocked_reason`` between probes, which
    would let probe 3 be refused locally because probe 2 saw a 400 -- a
    result about this loop rather than about the model.
    """
    results: list[dict[str, Any]] = []
    for step in plan:
        claim = claims_by_id[step["claim_id"]]
        client.configure(
            label=step["label"],
            arm=step.get("arm", "production"),
            response_format=step.get("response_format"),
        )
        before = len(client.records)
        outcome: dict[str, Any] = {
            "probe": step["label"],
            "claim_id": claim.claim_id,
            "clip_id": claim.clip_id,
            "family": claim.family,
            "claim_holds": bool(claim.holds),
            "arm": step.get("arm", "production"),
            "response_format_requested": _describe_response_format(
                step.get("response_format")
            ),
        }
        perception = perception_for()
        try:
            verdict = perception.judge(
                criterion=claim.criterion,
                audio_path=str(clip_paths[claim.clip_id]),
            )
        except DiagnosticBudgetExceeded as exc:
            outcome["skipped"] = "budget_exhausted"
            outcome["skipped_detail"] = str(exc)
            results.append(outcome)
            continue
        except Exception as exc:  # noqa: BLE001
            # ``judge`` catches provider errors itself, so reaching here means
            # something outside the call failed. Recorded, not swallowed.
            outcome["harness_error"] = type(exc).__name__
            results.append(outcome)
            continue
        outcome["core_verdict"] = verdict.verdict
        outcome["core_judge_error"] = verdict.judge_error
        outcome["core_api_calls"] = verdict.api_call_count
        outcome["core_usage_complete"] = verdict.usage_complete
        outcome["wire"] = client.records[before:]
        results.append(outcome)
    return results


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

#: Pricing for the audio deployment is not registered in this repository's
#: price table. A cost of zero would be a false statement about a run that
#: placed paid calls, so the artifact reports the tokens it measured and
#: declines to convert them.
PRICING_NOTE = (
    "The audio deployment has no registered price in this repository, so no "
    "USD figure is computed. Tokens are recorded in full. A run that placed "
    "paid calls did not cost $0, and reporting $0 would be worse than "
    "reporting nothing."
)


def summarise(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The structural digest a reader looks at first.

    Every count here is over an outcome-selected sample of three claims and
    is therefore a description of what was reproduced, not a rate.
    """
    wire = [record for row in results for record in row.get("wire", [])]
    answered = [w for w in wire if "transport_error" not in w]
    reasons: dict[str, int] = {}
    kinds: dict[str, int] = {}
    for record in answered:
        reason = str(record.get("finish_reason"))
        reasons[reason] = reasons.get(reason, 0) + 1
        kind = str(record.get("core_kind"))
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "sample_is_outcome_selected": SAMPLE_IS_OUTCOME_SELECTED,
        "no_quiet_retry": NO_QUIET_RETRY,
        "probes_planned": len(results),
        "requests_placed": len(wire),
        "requests_with_a_response": len(answered),
        "requests_with_transport_error": len(wire) - len(answered),
        "finish_reason_counts": reasons,
        "core_kind_counts": kinds,
        "refusals": sum(1 for w in answered if w.get("refusal_present")),
        "reasoning_blocks_seen": sum(
            1 for w in answered if w.get("reasoning_present")
        ),
        "collector_disagreed_with_core": sum(
            1 for w in answered if w.get("agrees_with_core") is False
        ),
        "truncation_evidence": _truncation_verdict(answered),
        "pricing_complete": False,
        "estimated_cost_usd": None,
        "pricing_note": PRICING_NOTE,
        "input_tokens": sum(int(w.get("input_tokens") or 0) for w in answered),
        "output_tokens": sum(int(w.get("output_tokens") or 0) for w in answered),
    }


def _truncation_verdict(records: Sequence[Mapping[str, Any]]) -> str:
    """Settled by ``finish_reason`` alone, or left unsettled.

    334 §3 settled it with output-token counts. This does not, in either
    direction: a reply with no ``finish_reason`` at all leaves the question
    open, and saying so is the honest answer.
    """
    reasons = [r.get("finish_reason") for r in records]
    if not reasons:
        return "no_responses"
    if any(reason == "length" for reason in reasons):
        cut = sum(1 for reason in reasons if reason == "length")
        return f"truncated:{cut}_of_{len(reasons)}_finish_reason_length"
    if all(reason is None for reason in reasons):
        return "unsettled:no_finish_reason_reported"
    if all(reason == "stop" for reason in reasons):
        return "not_truncated:every_finish_reason_is_stop"
    return "mixed:see_finish_reason_counts"


def _print_summary(summary: Mapping[str, Any]) -> None:
    """Structural fields only. No reply text reaches stdout, ever.

    CI logs are public artifacts with a different retention story from the
    committed JSON, so the console gets strictly less than the file does --
    never an excerpt, masked or otherwise.
    """
    print("audio format-failure diagnostic")
    for key in (
        "probes_planned",
        "requests_placed",
        "requests_with_a_response",
        "requests_with_transport_error",
        "finish_reason_counts",
        "core_kind_counts",
        "refusals",
        "reasoning_blocks_seen",
        "collector_disagreed_with_core",
        "truncation_evidence",
        "input_tokens",
        "output_tokens",
    ):
        print(f"  {key}: {summary[key]}")
    print(f"  estimated_cost_usd: {summary['estimated_cost_usd']} (pricing_complete="
          f"{summary['pricing_complete']})")


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prereg", type=Path, required=True,
                        help="the diagnostic's pre-registration; must declare "
                             f"진단 종류 `{DIAGNOSTIC_KIND}`")
    parser.add_argument("--speech-manifest", type=Path, required=True)
    parser.add_argument("--speech-clips", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=probe.PINNED_CONFIG)
    parser.add_argument(
        "--excerpt-chars", type=int, default=0,
        help=f"masked excerpt length, 0 (default) disables excerpts entirely; "
             f"hard maximum {EXCERPT_HARD_LIMIT}",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="resolve the plan, the sample and the pins, place no calls",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Argument validation first, before anything is read from disk. The
    # excerpt bound is the one setting that decides whether model text can
    # reach a file at all, so it is checked without depending on a document
    # being present, parseable, or the right one.
    if args.excerpt_chars > EXCERPT_HARD_LIMIT:
        raise SystemExit(
            f"--excerpt-chars {args.excerpt_chars} exceeds the hard limit "
            f"{EXCERPT_HARD_LIMIT}"
        )
    if args.excerpt_chars < 0:
        raise SystemExit("--excerpt-chars cannot be negative")

    kind = probe.diagnostic_kind_stated_in(args.prereg)
    if kind != DIAGNOSTIC_KIND:
        raise SystemExit(
            f"{args.prereg} registers '{kind}', not '{DIAGNOSTIC_KIND}'. This "
            f"run is not the one that document agreed to."
        )

    identity = probe.pinned_identity(args.config)
    stated = probe.grader_pin_stated_in(args.prereg)
    actual = probe.grader_source_hash(args.config)
    if stated != actual:
        raise SystemExit(
            f"{args.prereg} pins grader {stated[:16]}... and this checkout is "
            f"{actual[:16]}.... The document describes a different grader "
            f"than the one that would run."
        )

    corpus = probe.load_speech_corpus(args.speech_manifest, args.speech_clips)
    claims_by_id = {claim.claim_id: claim for claim in corpus.claims}
    missing = [cid for cid in FIXED_SAMPLE if cid not in claims_by_id]
    if missing:
        raise SystemExit(
            f"the fixed sample names claims the pinned manifest does not "
            f"carry: {missing}"
        )
    clip_paths = {clip.clip_id: clip.path for clip in corpus.clips}

    plan = probe_plan()
    header: dict[str, Any] = {
        "diagnostic_kind": DIAGNOSTIC_KIND,
        "prereg": args.prereg.name,
        "grader_source_sha256": actual,
        "identity": identity,
        "max_model_requests": MAX_MODEL_REQUESTS,
        "requests_planned": len(plan),
        "requests_reserved_for_transport_retry": MAX_MODEL_REQUESTS - len(plan),
        "fixed_sample": list(FIXED_SAMPLE),
        "sample_is_outcome_selected": SAMPLE_IS_OUTCOME_SELECTED,
        "no_quiet_retry": NO_QUIET_RETRY,
        "excerpt_chars": args.excerpt_chars,
        "excerpt_hard_limit": EXCERPT_HARD_LIMIT,
        "reasoning_blocks_collected": False,
        "observation_header_sha256": hashlib.sha256(
            probe.SPEECH_OBSERVATION_HEADER.encode("utf-8")
        ).hexdigest(),
        "clip_sha256": {clip.clip_id: clip.sha256 for clip in corpus.clips
                        if clip.clip_id in {claims_by_id[c].clip_id
                                            for c in FIXED_SAMPLE}},
        "plan": [
            {
                "label": step["label"],
                "claim_id": step["claim_id"],
                "arm": step.get("arm", "production"),
                "response_format": _describe_response_format(
                    step.get("response_format")
                ),
            }
            for step in plan
        ],
    }

    if args.dry_run:
        header["dry_run"] = True
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(header, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"dry run: plan resolved, no calls placed -> {args.out}")
        for step in header["plan"]:
            print(f"  {step['label']}: {step['claim_id']} arm={step['arm']} "
                  f"response_format={step['response_format']}")
        return 0

    from core.azure_ai_clients import AzureAIWorkload
    from core.llm_client import create_typed_azure_client

    managed = create_typed_azure_client(
        AzureAIWorkload.GRADER, identity["audio_deployment"]
    )
    client = DiagnosticClient(
        managed.client, excerpt_chars=args.excerpt_chars
    )

    def perception_for() -> AudioPerception:
        return AudioPerception(
            client=client,
            deployment=identity["audio_deployment"],
            call_cap=identity["audio_call_cap_per_task"],
            trim_seconds=identity["audio_clip_seconds"],
        )

    results = run_probes(
        plan,
        client=client,
        perception_for=perception_for,
        claims_by_id=claims_by_id,
        clip_paths=clip_paths,
    )
    header["requests_used"] = client.requests_used
    header["requests_remaining"] = client.requests_remaining
    payload = {
        **header,
        "summary": summarise(results),
        "probes": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    _print_summary(payload["summary"])
    print(f"  requests_used: {client.requests_used}/{MAX_MODEL_REQUESTS}")
    print(f"written: {args.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
