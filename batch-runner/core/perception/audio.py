"""Audio perception sub-judge — task 206.

Used when ``core.grader_routing.classify_criterion`` returns
``Modality.AUDIO``. The main tool-calling judge calls
``AudioPerception.judge(criterion, audio_bytes, ...)`` after invoking
``read_deliverable(op='probe_audio', ...)``.

Design notes (task 206):

* Model: ``gpt-audio-1.5`` deployed on Azure OpenAI. The deployment
  must exist in the same resource group as the main judge endpoint;
  see ``tasks/rebuilding_grading_task/PR2_ENV_AUDIT.md`` for the
  deferred verification (we check on first call rather than at import
  time so missing-deployment failures are isolated to audio items).
* The client is injected from the typed grader route like in
    ``VisionPerception`` — no endpoint lookup or client construction occurs
    inside this class.
* Endpoint: **Chat Completions**, not Responses. Audio is the one modality
  the two endpoints disagree about. ``ResponseInputContentParam`` is a union
  of text, image and file only, so a Responses request carrying audio is
  refused with a 400 before any model hears it; the audio content part
  belongs to ``ChatCompletionContentPartParam``. See
  ``tests/test_audio_goes_to_the_endpoint_that_accepts_it.py``.
* Duration trim: 30 seconds of the file are sent per call, re-encoded to
  16 kHz mono. Which 30 seconds follows the criterion -- a question about
  1:22 is sent 1:22, not the opening -- and whichever window goes out is the
  window the system prompt names. See :func:`criterion_listen_start` for why
  a fixed head slice cost task ``38889c3b`` six points on the gold run. The
  main judge still has access to full-clip statistics via
  ``read_deliverable(op='probe_audio', ...)``.
* Per-task call cap = 32, which is the most listening criteria any one task
  in the gold corpus carries. The cap counts *listens*, not attempts: a
  request the provider refused before running the model gives its slot back,
  because the cap bounds what a task spends and a refused request spent
  nothing. A separate failure budget is what keeps that refund from turning
  a bad endpoint into one doomed request per criterion. See
  ``tests/test_a_failed_audio_call_does_not_cost_the_task_its_turn.py``
  for why the distinction is load-bearing -- the paid smoke on run
  ``33363059548`` reported ``cap_exceeded`` on tasks that had never
  successfully listened to anything, because every request was going to an
  endpoint that could not accept one.
* Graceful fallback: missing deployment, decode error, or provider
  exception all return ``judge_error`` rather than raising.
* No sampling parameters. Neither the main judge nor ``VisionPerception``
  sends ``temperature`` or ``seed``, and this module no longer does either.
  Chat Completions would accept ``temperature``, so this is a consistency
  choice rather than a constraint -- but it is also the smallest request
  that can do the job, which is what a path with no successful call in its
  history should be sending.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from core.cost_metering import read_reported_usage
from core.public_error import (
    public_provider_error_text,
    public_task_error,
    public_task_error_text,
)

#: The largest number of listening criteria any one task in the gold corpus
#: carries, so that the cap is a backstop against a runaway rather than a
#: silent truncation of the marking. Counted by classifying all 8,816 rubric
#: criteria through :func:`core.grader_routing.classify_criterion`: 29 of the
#: 220 tasks ask to be listened to at all, 150 criteria in total, and the
#: worst single task (``ff85ee58``) asks 32 times.
#:
#: It used to be 3, on the stated grounds that "audio items are rarer than
#: visual". That was measured and is wrong: 3 covers the median task but
#: starves 11 tasks outright, and the shortfall was already recorded against
#: one of them in ``scripts/stage3_partial_inventory.py`` ("10 listening
#: criteria vs AUDIO_CALL_CAP=3"). An item over the cap never places a call,
#: so it is scored ``judge_error`` on a deliverable that may well satisfy it.
#:
#: Not a hard ceiling: ``call_cap_per_task`` under ``judge.perception.audio``
#: replaces it, and the grader passes whatever it finds there on every
#: construction. The free cost check reads it from here too, so moving it
#: moves the ceiling with it.
AUDIO_CALL_CAP = 32

#: Seconds of audio sent to the model per call when the marking settings name
#: no ``trim_seconds`` of their own. A longer clip costs more to send, so this
#: is a price as much as a limit, and the grader reads it from here rather
#: than keeping a second copy.
AUDIO_TRIM_SECONDS = 30

#: Patterns for reading a listening window out of a criterion's own words.
#:
#: The clip has always been the *first* ``AUDIO_TRIM_SECONDS`` of the
#: deliverable, and the sub-judge has always been told so. That is fine for
#: "is there music", "is the voiceover audible", "does it clip" -- properties
#: a head slice carries. It is not fine for a criterion that names a region:
#: on the 185-task gold run, task ``38889c3b`` was asked about 1:22-1:49,
#: about 1:49-to-the-end, and about the stretch through 1:22 of a two-minute
#: master. All three were answered ``fail``, 0/2, for six points; one of them
#: says why in its own evidence -- *"The clip only includes the first 30s,
#: ending well before 1:49."*
#:
#: That is the failure this module exists to avoid, wearing the one disguise
#: it is hardest to see: the model listened, reported honestly what it heard,
#: and the harness recorded "the deliverable does not do this" from a clip in
#: which the deliverable was never given the chance to. Absence of observation
#: is not observation of absence.
#:
#: So the window follows the question. ``M:SS`` only, seconds bounded at 59,
#: and not when a clock-time suffix follows -- "9:00 AM" is a meeting, "2:1"
#: is a ratio and cannot match at all. A stated tolerance ("+/- 10 s") is read
#: from the text rather than guessed at, and the window opens that much early.
_AUDIO_TIMESTAMP_RE = re.compile(
    r"\b(\d{1,3}):([0-5]\d)\b(?!\s*(?:[ap]\.?\s?m\.?\b|:?\d))",
    flags=re.IGNORECASE,
)
#: Words that put the asked-about region at the top of the file no matter what
#: else the criterion names. "From the beginning of the Master track through
#: 1:22" names 1:22 and wants 0:00. Seeking to 1:22 for it would take a clip
#: that overlaps the question and replace it with one that does not, so any of
#: these words means: leave the head slice alone. A word matched here by
#: accident costs nothing -- it restores exactly today's behaviour.
_AUDIO_HEAD_ANCHOR_RE = re.compile(
    r"\b(beginning|begins?|start|starts|starting|opening|opens|intro"
    r"|introduction|outset|onset|first|initial|top)\b",
    flags=re.IGNORECASE,
)
_AUDIO_TOLERANCE_RE = re.compile(
    r"(?:±|\+\s*/\s*-|\+-)\s*(\d{1,3})\s*(?:s\b|sec|second)",
    flags=re.IGNORECASE,
)


def criterion_listen_start(
    criterion: str,
    *,
    trim_seconds: int = AUDIO_TRIM_SECONDS,
) -> Optional[float]:
    """Where in the deliverable this criterion needs the clip to start.

    Returns ``None`` -- meaning "the head, as always" -- unless the criterion
    names a region that the head slice provably cannot contain. That is a
    deliberately narrow trigger, and it is the whole safety argument for this
    function: the only items whose clip can move are the ones asking about a
    stretch of audio that starts *after* everything we send today ends. Those
    items cannot currently be answered from evidence. Nothing that is
    answerable today changes.

    The tolerance a criterion states about its own timestamp is honoured, so
    "1:22 (+/- 10 s)" opens the window at 1:12 rather than at 1:22 and does
    not miss the very thing it was sent to hear.
    """
    text = criterion or ""
    if not text or _AUDIO_HEAD_ANCHOR_RE.search(text):
        return None
    stamps = [
        minutes * 60 + seconds
        for minutes, seconds in (
            (int(m.group(1)), int(m.group(2)))
            for m in _AUDIO_TIMESTAMP_RE.finditer(text)
        )
    ]
    if not stamps:
        return None
    tolerances = [int(m.group(1)) for m in _AUDIO_TOLERANCE_RE.finditer(text)]
    start = min(stamps) - (max(tolerances) if tolerances else 0)
    if start <= trim_seconds:
        # The head already overlaps what is being asked about. Sending a
        # second, later clip would answer a question nobody asked.
        return None
    return float(start)


#: What the head slice is re-encoded to. The source is whatever the
#: deliverable happens to carry — the two video deliverables in this corpus
#: are 48 kHz stereo — and the encoder used to preserve that, which made a
#: 30-second clip 5.76 MB of PCM and 7.68 MB once base64'd, per call.
#:
#: Nothing any criterion in this corpus asks about survives only above 8 kHz
#: or only in the stereo difference. They ask whether a voiceover is audible,
#: whether music is present and in what style, whether a named sound effect
#: lands on a named shot, and whether cuts fall on downbeats. 16 kHz mono
#: carries all of that and is 6x smaller to send, which is what makes raising
#: ``AUDIO_CALL_CAP`` from 3 to 32 affordable: the worst task's traffic goes
#: to 41 MB rather than 246 MB.
AUDIO_SAMPLE_RATE_HZ = 16_000
AUDIO_LAYOUT = "mono"

#: The only container formats an ``input_audio`` content part accepts
#: (``openai.types.chat.chat_completion_content_part_input_audio_param``
#: types ``format`` as ``Literal["wav", "mp3"]``). Anything else is rejected
#: with a 400 before the model is reached, so a clip that cannot be presented
#: as one of these is refused here rather than paid for and bounced.
SUPPORTED_AUDIO_FORMATS = ("mp3", "wav")

#: Of those, the ones already compressed. A short clip in one of these is
#: sent untouched: re-encoding it to 16 kHz PCM would make it *larger*, since
#: 30 s of mp3 is a few hundred KB and the same 30 s of PCM is 960 KB. A
#: short ``.wav`` gets no such exemption — it is exactly the case the downmix
#: is for, and a 30-second 48 kHz stereo deliverable would otherwise slip
#: through the shortcut at 5.76 MB a call.
COMPRESSED_AUDIO_FORMATS = ("mp3",)

#: Largest base64 payload this class will put on the wire.
#:
#: Not the reason the paid smoke on run ``33363059548`` saw a 400 on every
#: request. That was the endpoint: audio was going to Responses, whose content
#: union has no audio member, so the request was malformed at any size. Size
#: was one of two candidates standing at the time, and it is now ruled out
#: rather than guarded against — 30 s at 16 kHz mono is 960 KB raw and
#: ~1.28 MB base64, two orders below this limit, and even the pre-downmix
#: 48 kHz stereo payload was 7.68 MB.
#:
#: It stays because it is cheap and it names itself. A clip that somehow
#: arrives near 20 MB is anomalous whatever produced it, and a request that
#: will bounce still costs the wall-clock of bouncing. What it must not be
#: read as is a diagnosis: if this ever fires, it says the clip was huge, not
#: that size was ever what broke the listening path.
AUDIO_MAX_REQUEST_BYTES = 20 * 1024 * 1024

#: How many failed attempts one task will make before it stops trying.
#:
#: Separate from ``call_cap`` because the two bound different things. The call
#: cap bounds *spend*, and a request the provider rejected without running the
#: model did not spend anything. This bounds *wall-clock*, which a refunded
#: call would otherwise leave unbounded: without it, a task with 32 audio
#: criteria facing a flaky endpoint makes 32 doomed requests instead of three.
#: Raising the cap to 32 is what makes this the load-bearing one of the pair.
#:
#: In practice this is only ever reached by 429s. Every other rejection is
#: deterministic for the task -- same clip, same request shape, same answer --
#: and short-circuits on the first one.
AUDIO_FAILURE_BUDGET = 3

#: Provider rejections that happened before the model ran, and so were not
#: billed. Only these give a call slot back; anything else -- a timeout, a
#: 5xx, a dropped connection -- may have been billed for work we never saw,
#: and is counted as spent. The asymmetry is deliberate and points the safe
#: way: over-counting a call costs one criterion, under-counting it costs
#: money the ledger never learns about.
_UNBILLED_STATUS = frozenset({400, 401, 403, 404, 413, 415, 422, 429})

#: Rejections that will recur identically for every remaining criterion on
#: this task. The clip is the same file and the request is the same shape, so
#: a malformed request stays malformed and a missing deployment stays missing.
#: Retrying buys another identical bounce; 429 is the one that is worth
#: waiting out, which is why it is in the set above and not this one.
#:
#: Worth reading beside the defect that motivated it: a wrong *endpoint* is
#: deterministic for every task, not just this one, so this short-circuit
#: would have turned 21 refusals into 2 and saved nothing else. It bounds the
#: damage of a bad call; it cannot tell you the call was bad.
_DETERMINISTIC_STATUS = frozenset({400, 401, 403, 404, 413, 415, 422})


def _provider_status_code(exc: object) -> Optional[int]:
    """HTTP status behind a provider exception, or ``None`` if it is not one.

    Read defensively rather than by catching a typed exception: this module
    takes its client by injection and must not assume which SDK built it.
    """
    for probe in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        if isinstance(probe, int):
            return probe
    return None


@dataclass(frozen=True)
class AudioVerdict:
    verdict: str
    partial_score: float
    evidence: str
    confidence: float
    reasoning: str
    judge_error: Optional[str] = None
    #: Why the call could not be answered, in enough detail to act on, and
    #: built only from what this module itself computed -- the exception's
    #: type name, the status the provider returned, and the shape of what was
    #: sent. Never the provider's message body and never the endpoint, so it
    #: is publishable under the same rule as ``judge_error``; and never the
    #: sub-judge's prose, which lives in ``reasoning`` and is not published.
    #: ``None`` on a verdict that was actually reached.
    failure_detail: Optional[str] = None
    api_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: float = 0.0
    usage_complete: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "partial_score": self.partial_score,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "judge_error": self.judge_error,
            "failure_detail": self.failure_detail,
            "api_call_count": self.api_call_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "latency_ms": self.latency_ms,
            "usage_complete": self.usage_complete,
        }


def _mmss(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def _audio_prompt_header(
    *,
    start_seconds: float = 0.0,
    trim_seconds: int = AUDIO_TRIM_SECONDS,
    window_note: Optional[str] = None,
) -> str:
    """The system prompt, stating the window this call actually carries.

    This used to be a constant reading "a head-only slice (first 30s)", which
    was true of the bytes but became false as soon as marking settings named a
    different ``trim_seconds``, and false in a more expensive way once the
    clip could start anywhere. What the sub-judge is told it is hearing has to
    be what it is hearing: its evidence is quoted in the grade, and evidence
    timed against the wrong origin is worse than none.
    """
    if start_seconds > 0:
        span = (
            f"the segment from {_mmss(start_seconds)} to "
            f"{_mmss(start_seconds + trim_seconds)} of"
        )
    else:
        span = f"a head-only slice (first {int(trim_seconds)}s) of"
    parts = [
        "You are an audio sub-judge for the GDPval grading pipeline. The "
        f"clip is {span} the LLM-under-test's audio deliverable."
    ]
    if window_note:
        parts.append(window_note)
    parts.append(
        "Grade ONE rubric criterion against what you HEAR. Return the same "
        "JSON envelope as the main judge: {verdict, partial_score, evidence, "
        "confidence, reasoning}. The evidence MUST describe an audible "
        "feature; do not invent. Keep evidence <= 200 chars. Return JSON only."
    )
    return " ".join(parts)


#: Told to the sub-judge when the criterion named a region and the clip could
#: not be cut to it for a reason that is about this machine rather than about
#: the deliverable. Not having listened is not having heard nothing, and the
#: envelope already has a value for "no verdict was reached".
_AUDIO_WINDOW_UNCUT_NOTE = (
    "The criterion names a part of the deliverable that this clip does not "
    "contain, and it could not be extracted, so you have NOT observed it. Do "
    "not treat that as evidence the deliverable lacks it: return verdict "
    "\"judge_error\" and say in the evidence which part went unheard."
)

#: Told to the sub-judge when the region is missing because the deliverable
#: stops before it. That is a fact about the work under test, so it is
#: gradeable, and the sub-judge is left to grade it.
_AUDIO_REGION_ABSENT_NOTE = (
    "Note: the criterion names a timestamp beyond the end of this "
    "deliverable, which runs out before that point."
)


def _parse_json_envelope(text: str) -> Dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    return json.loads(t)


def _first_choice_text(response: Any) -> str:
    """Pull the assistant text out of a Chat Completions response.

    The Responses API offers a flattened ``output_text``; Chat Completions
    does not, and an audio-capable deployment may answer either in
    ``message.content`` or — when it has been asked for spoken output — in
    ``message.audio.transcript``. We ask for ``modalities=["text"]`` so the
    first is what should arrive, but reading both means a deployment
    configured otherwise degrades to a parse failure rather than a silent
    empty verdict.
    """
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content:
        return str(content)
    audio = getattr(message, "audio", None)
    return str(getattr(audio, "transcript", "") or "") if audio else ""


class AudioWindowUnavailable(Exception):
    """A requested listening window could not be cut from the file.

    Raised only for a window that was actually asked for -- either the file
    ends before it, or nothing here can decode it. The caller's answer is to
    fall back to the head slice *and say so in the prompt*, never to present a
    head slice as if it were the segment the criterion named.

    ``region_absent`` separates the two, because they deserve opposite
    verdicts. A deliverable that ends at 0:30 really does not have the bridge
    the rubric asks for at 1:22, and failing it is correct. A file this
    machine could not decode tells us nothing about the deliverable at all,
    and failing *that* is the very mistake this class was added to stop.
    """

    def __init__(self, message: str, *, region_absent: bool = False) -> None:
        super().__init__(message)
        self.region_absent = region_absent


def _trim_audio_bytes(path: str, max_seconds: int = AUDIO_TRIM_SECONDS,
                      start_seconds: float = 0.0,
                      ) -> Tuple[bytes, str]:
    """Read a file and return ``(bytes, format)`` trimmed to ``max_seconds``.

    Uses PyAV (wheel bundles ffmpeg per env audit). Falls back to
    sending the raw file if PyAV cannot decode (e.g. exotic codec).

    The file is only handed over untouched when it is *known* to be short
    enough and already carries a compressed format the API accepts. A clip
    whose duration the container does not report is re-encoded rather than
    sent whole: "no duration" is not "short", and a studio stem that declines
    to say how long it is would otherwise go out at its full size. Nor does a
    short ``.wav`` qualify — see ``COMPRESSED_AUDIO_FORMATS``.

    ``start_seconds`` moves the slice off the head, for a criterion that named
    a region the head cannot contain (see :func:`criterion_listen_start`). At
    the default of ``0.0`` every path below is exactly what it was. Above it,
    the two shortcuts that would send bytes other than the requested window --
    the raw hand-over and the whole-file fallback — are closed, because a clip
    that does not match what the prompt claims about it is worse than no clip.
    The slice is cut by decoding forward and dropping what precedes the window
    rather than by seeking: a container seek lands on the keyframe at or
    before the target, and the window promised to the sub-judge has to be the
    window it actually hears.
    """
    fmt = _guess_format(path)
    wants_window = start_seconds > 0

    def raw() -> Tuple[bytes, str]:
        with open(path, "rb") as fh:
            return fh.read(), fmt

    try:
        import av  # type: ignore
    except ImportError:
        if wants_window:
            raise AudioWindowUnavailable("no decoder available to cut a window")
        return raw()

    try:
        container = av.open(path)
        try:
            # Existence probe: a container with no audio stream raises
            # IndexError here and falls through to sending the file whole.
            container.streams.audio[0]
            duration_s = (float(container.duration) / 1_000_000.0
                          if container.duration else None)
            if wants_window and duration_s is not None and duration_s <= start_seconds:
                raise AudioWindowUnavailable(
                    f"deliverable is {duration_s:.0f}s long and the criterion "
                    f"asks about {start_seconds:.0f}s",
                    region_absent=True,
                )
            if (
                not wants_window
                and duration_s is not None
                and duration_s <= max_seconds
                and fmt in COMPRESSED_AUDIO_FORMATS
            ):
                return raw()
            # Re-encode head slice to WAV in memory, downmixed to 16 kHz mono
            # rather than kept at whatever the source carried. See
            # AUDIO_SAMPLE_RATE_HZ for why that loses nothing this corpus asks
            # about and why it is what makes a cap of 32 affordable.
            import io
            buf = io.BytesIO()
            out = av.open(buf, mode="w", format="wav")
            out_stream = out.add_stream("pcm_s16le", rate=AUDIO_SAMPLE_RATE_HZ)
            out_stream.layout = AUDIO_LAYOUT
            resampler = av.AudioResampler(
                format="s16", layout=AUDIO_LAYOUT, rate=AUDIO_SAMPLE_RATE_HZ,
            )
            window_end = start_seconds + max_seconds
            heard_anything = False
            furthest = 0.0
            for frame in container.decode(audio=0):
                t = float(frame.pts * frame.time_base) if frame.pts else 0.0
                furthest = max(furthest, t)
                if t > window_end:
                    break
                if t < start_seconds:
                    continue
                heard_anything = True
                for resampled in resampler.resample(frame):
                    for packet in out_stream.encode(resampled):
                        out.mux(packet)
            if wants_window and not heard_anything:
                # Two different things end up here and only one of them is
                # the deliverable's fault. A file whose frames carried real,
                # advancing timestamps and still had nothing at the window
                # really is shorter than the criterion assumes. A file whose
                # timestamps never moved off zero told us nothing at all, and
                # blaming it for stopping early would put a sentence in the
                # prompt that no evidence supports.
                timestamps_moved = furthest > 0.0
                raise AudioWindowUnavailable(
                    f"no audio at {start_seconds:.0f}s in this deliverable"
                    if timestamps_moved
                    else "frame timestamps unusable; cannot cut a window",
                    region_absent=timestamps_moved,
                )
            # Drain the resampler before the encoder: PyAV buffers whole
            # output frames, so the tail of the slice is still inside it.
            for resampled in resampler.resample(None):
                for packet in out_stream.encode(resampled):
                    out.mux(packet)
            for packet in out_stream.encode():
                out.mux(packet)
            out.close()
            return buf.getvalue(), "wav"
        finally:
            container.close()
    except AudioWindowUnavailable:
        # The one failure the whole-file fallback must not paper over.
        raise
    except Exception:
        if wants_window:
            raise AudioWindowUnavailable("could not decode a window from this file")
        return raw()


def _guess_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return ext or "wav"


@dataclass
class AudioPerception:
    client: Any
    deployment: str = "gpt-audio-1.5"
    call_cap: int = AUDIO_CALL_CAP
    trim_seconds: int = AUDIO_TRIM_SECONDS
    #: Zero-argument rate-limit guard, invoked immediately before every
    #: request. The grader passes its own TPM spacer here, the same one the
    #: main judge and the vision sub-judge get. Audio went without it for as
    #: long as this class has existed, which was invisible because a mistyped
    #: content part meant no audio request ever reached a model to be
    #: throttled; with the shape corrected, an unguarded reader is a reader
    #: that can spend a shard's remaining budget on 429s.
    before_upstream_call: Optional[Callable[[], None]] = None

    #: Attempts, not measurements. See :data:`AUDIO_FAILURE_BUDGET`.
    failure_budget: int = AUDIO_FAILURE_BUDGET

    _calls_used: int = field(default=0, init=False)
    _failures_used: int = field(default=0, init=False)
    #: Set when a rejection tells us every later criterion on this task will
    #: get the same one. Cleared at the task boundary with everything else.
    _blocked_reason: Optional[str] = field(default=None, init=False)

    @property
    def calls_used(self) -> int:
        return self._calls_used

    @property
    def failures_used(self) -> int:
        """Attempts this task has already burned on rejected calls."""
        return self._failures_used

    def reset(self) -> None:
        self._calls_used = 0
        self._failures_used = 0
        self._blocked_reason = None

    def restore_spend(self, calls_used: int, *, failures_used: int = 0) -> None:
        """Re-charge a resumed task for what an earlier chunk already spent.

        Both counters, for the same reason: they are per *task*, and a task
        long enough to span chunks crosses the ``reset`` boundary mid-rubric.
        Restoring only the calls would hand a resumed task a fresh failure
        budget on every attempt, so a file the model keeps rejecting gets
        retried three times per chunk forever instead of three times per task.

        ``_blocked_reason`` is deliberately *not* restored. It is a sentence,
        and the checkpoint holds only numbers -- see ``305``'s rule that
        nothing on disk should read like a finding. The cost of leaving it out
        is bounded and visible: a deterministic rejection re-latches on the
        first criterion of the new chunk, from one call that is never billed.
        """
        self._calls_used = max(0, min(int(calls_used), self.call_cap))
        self._failures_used = max(
            0, min(int(failures_used), self.failure_budget)
        )

    def _refuse(self, reason: str, judge_error: str) -> "AudioVerdict":
        """A verdict for a criterion no call was made for.

        Every early return in :meth:`judge` goes through here so they cannot
        drift apart: nothing was sent, so nothing is billed, and the usage
        this reports -- zero -- is complete rather than merely unknown.
        """
        return AudioVerdict(
            verdict="judge_error",
            partial_score=0.0,
            evidence="",
            confidence=0.0,
            reasoning=reason,
            judge_error=judge_error,
            # Every ``reason`` reaching here is written by this module out of
            # its own counters, so the same sentence that explains the refusal
            # in a log is the one the payload can carry.
            failure_detail=reason,
        )

    def _preparation_error(self, exc: Exception, audio_path: str) -> "AudioVerdict":
        """A verdict for a clip that could not be built at all.

        Shared by the plain path and by the fall-back after a window could not
        be cut, so that failing to prepare a head slice reads the same however
        the caller arrived at it.
        """
        detail = (
            f"audio preparation failed:"
            f" {public_task_error(exc)['error_type']}"
            f" (suffix={os.path.splitext(audio_path)[1].lower() or 'none'})"
        )
        return AudioVerdict(
            verdict="judge_error",
            partial_score=0.0,
            evidence="",
            confidence=0.0,
            reasoning=detail,
            judge_error=public_task_error_text(exc),
            failure_detail=detail,
        )

    def judge(
        self,
        *,
        criterion: str,
        audio_path: str,
    ) -> AudioVerdict:
        if self._blocked_reason is not None:
            # Distinct from ``cap_exceeded`` on purpose. That one means the
            # task listened its three times; this one means the task never
            # got to listen at all. The paid smoke reported the first while
            # the second was true, and the difference is the whole reading of
            # the artifact: a budget spent, or a model that was never usable.
            return self._refuse(
                f"audio unavailable for this task: {self._blocked_reason}",
                f"audio_unavailable:{self._blocked_reason}",
            )
        if self._calls_used >= self.call_cap:
            return self._refuse(
                f"audio call cap {self.call_cap} exceeded",
                "cap_exceeded",
            )
        if self._failures_used >= self.failure_budget:
            return self._refuse(
                f"audio failure budget {self.failure_budget} exhausted",
                "audio_unavailable:repeated_failure",
            )
        listen_start = criterion_listen_start(
            criterion, trim_seconds=self.trim_seconds
        )
        window_note: Optional[str] = None
        try:
            data, fmt = _trim_audio_bytes(
                audio_path, self.trim_seconds, listen_start or 0.0
            )
        except AudioWindowUnavailable as window_exc:
            # A window was asked for and could not be cut. Fall back to the
            # head slice -- but never silently. What the prompt says about the
            # clip has to stay true, and *why* the region went unheard is what
            # decides whether failing the criterion would be honest.
            window_note = (
                _AUDIO_REGION_ABSENT_NOTE if window_exc.region_absent
                else _AUDIO_WINDOW_UNCUT_NOTE
            )
            listen_start = None
            try:
                data, fmt = _trim_audio_bytes(audio_path, self.trim_seconds)
            except Exception as exc:  # noqa: BLE001
                return self._preparation_error(exc, audio_path)
        except Exception as exc:  # noqa: BLE001
            return self._preparation_error(exc, audio_path)
        if fmt not in SUPPORTED_AUDIO_FORMATS:
            # Refused before the call, not after it. The API rejects an
            # unsupported container outright, so sending it spends a slot from
            # ``call_cap`` and buys a 400. No call goes out, so nothing is
            # billed and the usage this verdict reports — zero — is complete.
            return self._refuse(
                f"unsupported audio format: {fmt}",
                "unsupported_audio_format",
            )
        b64 = base64.b64encode(data).decode("ascii")
        header = _audio_prompt_header(
            start_seconds=listen_start or 0.0,
            trim_seconds=self.trim_seconds,
            window_note=window_note,
        )
        if len(b64) > AUDIO_MAX_REQUEST_BYTES:
            # The size candidate, named rather than guessed at. This is the
            # one shape of 400 the class can recognise on its own side of the
            # wire, so it says so instead of letting the provider say
            # ``BadRequestError`` and leaving the reader to pick between two
            # explanations. Deterministic for the task -- every criterion gets
            # the same length of clip at the same encoding, whichever part of
            # the file it is cut from -- so it blocks the rest rather than
            # re-measuring the same file thirteen more times.
            self._blocked_reason = "payload_too_large"
            return self._refuse(
                f"audio payload {len(b64)} bytes exceeds "
                f"{AUDIO_MAX_REQUEST_BYTES}",
                "audio_payload_too_large",
            )
        if self.before_upstream_call is not None:
            self.before_upstream_call()
        # Counted before the call and given back only for rejections that
        # provably predate inference. A call that vanished into a timeout is
        # counted as spent because it may well have been.
        self._calls_used += 1
        call_started = time.perf_counter()
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        usage_complete = False
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text",
                             "text": f"{header}\n\nCriterion:\n{criterion}"},
                            {"type": "input_audio",
                             "input_audio": {"data": b64, "format": fmt}},
                        ],
                    }
                ],
                modalities=["text"],
            )
            latency_ms = (time.perf_counter() - call_started) * 1000.0
            reported = read_reported_usage(response)
            input_tokens = reported.input_tokens
            output_tokens = reported.output_tokens
            cached_tokens = reported.cached_tokens
            usage_complete = reported.usage_complete
            text = _first_choice_text(response)
            payload = _parse_json_envelope(text)
            return AudioVerdict(
                verdict=str(payload.get("verdict", "fail")),
                partial_score=float(payload.get("partial_score", 0.0)),
                evidence=str(payload.get("evidence", ""))[:200],
                confidence=float(payload.get("confidence", 0.0)),
                reasoning=str(payload.get("reasoning", ""))[:300],
                api_call_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - call_started) * 1000.0
            status = _provider_status_code(exc)
            if status in _UNBILLED_STATUS:
                # Give the slot back. ``call_cap`` is there to bound what a
                # task spends and to make every task spend it on the same
                # scale; a request the provider refused before running the
                # model spent nothing and measured nothing, so charging it
                # does neither job. It only takes the criterion's turn away.
                self._calls_used -= 1
                self._failures_used += 1
            if status in _DETERMINISTIC_STATUS:
                # The rest of this task's criteria would send the same clip in
                # the same shape and get the same answer. Recorded once, and
                # the remainder refused honestly by name rather than after two
                # more identical bounces.
                self._blocked_reason = f"provider_{status}"
            # Facts, not an inference. ``format`` is what the request claimed
            # and ``source_suffix`` is what the file was called, so a reader
            # can see for themselves whether the bytes were re-encoded on the
            # way out -- and can see the case that needs seeing, a file with
            # no extension going out labelled ``wav`` because
            # ``_guess_format`` defaults to it. Both byte counts are here
            # because a 413 is about the encoded one and a malformed
            # container is about the other.
            #
            # The type name comes through ``public_task_error`` rather than
            # from ``type(exc)`` directly, so it is the same string
            # ``judge_error`` beside it is allowed to publish and cannot be a
            # second, laxer route to the same field. That projection drops any
            # class not named like an exception, which is what stops a
            # dynamically built type from carrying a value out in its name.
            detail = (
                f"audio call failed: {public_task_error(exc)['error_type']}"
                f" (status={status}, format={fmt},"
                f" source_suffix={os.path.splitext(audio_path)[1].lower() or 'none'},"
                f" bytes={len(data)}, b64_bytes={len(b64)})"
            )
            return AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=detail,
                judge_error=public_provider_error_text(exc),
                failure_detail=detail,
                api_call_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
