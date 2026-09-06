#!/usr/bin/env python3
"""Build a pinned, privacy-free speech set for checking whether the judge hears words.

Why this exists
---------------
Everything measured about ``gpt-audio-1.5`` so far has been measured on tones,
clicks and beeps -- clips synthesised from ``wave`` and ``math`` whose ground
truth is arithmetic. That corpus can answer "does the verdict depend on the
audio at all", and on 2026-09-06 it did. It cannot answer the question the
graded corpus actually turns on, because none of the 31 audio deliverables is a
sine wave: **can it hear speech?**

Those are different capabilities and a model can have one without the other. A
system that counts three beeps correctly has demonstrated that sound reached it
and that its verdict tracks the sound. It has demonstrated nothing about
phoneme discrimination, and "the audio was delivered" is evidence of delivery,
not of understanding.

What is pinned, and why each pin is here
----------------------------------------
The clips must be reproducible by someone who does not trust this file, so the
whole chain is recorded rather than described:

* **tool + version** -- eSpeak NG, read from ``espeak-ng --version`` at build
  time and never hardcoded. Two versions produce different waveforms; a
  hardcoded version silently becomes a lie the first time a runner image moves.
* **distribution source** -- the exact package and repository the binary came
  from, read from the package manager rather than assumed.
* **licence** -- eSpeak NG is GPL-3.0-or-later. Nothing of eSpeak's is
  redistributed here: no source, no binary, no dictionary, and no generated
  clip. The clips are build artifacts, produced in CI and uploaded as
  artifacts, and the repository holds only their digests. The licence is
  recorded because "we used a tool and did not write down which" is how an
  audit becomes impossible later, not because a digest needs one.
* **binary SHA-256** -- of the executable actually invoked, resolved through
  symlinks. The version string is what the tool says about itself; this is
  what it is.
* **clip SHA-256** -- of each WAV as written. This is what makes the set a
  *fixture*: a later run that produces different bytes has changed something,
  and the manifest says so before any model is asked anything.
* **generation command** -- the full argv, so the clip can be rebuilt without
  reading this file's source.

Synthetic speech, and what that costs
-------------------------------------
eSpeak NG is a formant synthesiser. It is robotic, and that cuts both ways:

* It is *deterministic and offline*, which a neural voice is not. The same
  version and the same argv give the same bytes, on any machine, forever, with
  no model download and no network. That is what a fixture needs.
* It is *harder to understand than a human voice*. So a failure here does not
  establish that the judge cannot hear people. It establishes that the judge
  cannot hear eSpeak, which is a weaker claim and has to be reported as one.

A pass, on the other hand, is strong: a system that transcribes formant-
synthesised speech correctly is very unlikely to be unable to hear a human
reading the same sentence. **This set can confirm the capability and cannot
refute it**, and the manifest says so in a field rather than leaving it to a
reader's charity.

Privacy
-------
No recorded audio and no cloned voice. Every clip is synthesised from a
sentence written for this file. The sentences name no person, no place, no
organisation, no date and no identifier -- they are about crates, dials and
valves, and they were chosen to be about nothing.

Not leaking the answer
----------------------
The manifest holds the transcript and the ground truth. **It is never sent to
the model.** The judging path is given one criterion at a time, and the
criteria are built so that neither member of a pair reveals which is true:
``the speaker states a quantity of seventeen`` and ``... of seventy`` are the
same question asked twice, and a model that cannot hear the difference has to
guess. Ten pairs, one true and one false each, so guessing scores 50% and a
model that answers ``pass`` to everything scores 50%.

Usage::

    # In CI, where espeak-ng can be installed:
    python scripts/build_speech_verification_set.py --out-dir speech-set

    # Verify a rebuild against a previously published manifest:
    python scripts/build_speech_verification_set.py --out-dir speech-set \\
        --expect-manifest speech-set/manifest.json

    # Inspect the corpus without synthesising anything:
    python scripts/build_speech_verification_set.py --describe
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Optional, Sequence

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

from core.perception.audio import (  # noqa: E402
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_TRIM_SECONDS,
    _trim_audio_bytes,
)

#: The synthesiser. Named once.
ESPEAK_BINARY = "espeak-ng"

#: What we believe about its licence, recorded so the belief is auditable.
#: Nothing of eSpeak NG is redistributed by this repository -- see the module
#: docstring -- so this is provenance, not a distribution obligation.
ESPEAK_LICENSE = "GPL-3.0-or-later"
ESPEAK_HOMEPAGE = "https://github.com/espeak-ng/espeak-ng"

#: Voice and prosody, fixed. Every one of these changes the waveform, so they
#: are arguments to the build rather than defaults left to the tool: a runner
#: whose espeak-ng defaults differ would otherwise produce a different fixture
#: from the same command line.
ESPEAK_VOICE = "en-us"
ESPEAK_WORDS_PER_MINUTE = 150
ESPEAK_PITCH = 50
ESPEAK_AMPLITUDE = 100

#: 16 kHz mono: the rate the grading path delivers at, read from that path
#: rather than restated.
#:
#: This is deliberately *not* the rate the WAVs are authored at. eSpeak NG has
#: no sample-rate option -- the rate is a property of the voice data, and
#: ``en-us`` renders at 22050 Hz -- so an earlier draft of this file refused to
#: build at all, on the reasoning that resampling would put a digest in the
#: manifest for a file nobody sends. The reasoning was right and the conclusion
#: was wrong: the conversion is not optional and not ours to skip, because
#: :func:`_trim_audio_bytes` re-encodes every clip on the way out regardless of
#: what rate it arrives at. So the build performs that same conversion, with
#: that same function, and pins both ends -- what eSpeak wrote, and what the
#: model hears. Adding ffmpeg or sox here would have meant a second tool to
#: pin; using the grader's own encoder means there is nothing extra to trust.
SPEECH_SAMPLE_RATE_HZ = AUDIO_SAMPLE_RATE_HZ


@dataclass(frozen=True)
class SpeechClip:
    """One synthesised sentence."""

    clip_id: str
    #: The words spoken. Ground truth: never sent to the model.
    transcript: str


@dataclass(frozen=True)
class SpeechClaim:
    """One statement about one clip, with its fixed answer."""

    claim_id: str
    #: Pairs a true claim with the false one it is matched against. The two
    #: differ by as little as possible, so the pair isolates hearing rather
    #: than reasoning.
    pair_id: str
    clip_id: str
    #: What kind of hearing the pair tests. Reported separately, because
    #: "cannot tell fifteen from fifty" and "cannot tell left from right" are
    #: different failures with different consequences for a rubric.
    family: str
    #: The text the model is shown. This is the whole of what it is shown.
    criterion: str
    holds: bool
    #: Why the answer is what it is. For a human auditing the corpus; never
    #: sent anywhere.
    because: str


#: Ten sentences. Deliberately dull, deliberately about objects.
CLIPS: tuple[SpeechClip, ...] = (
    SpeechClip("crate", "The blue crate holds seventeen bolts."),
    SpeechClip("shelf", "The second shelf is fifteen centimetres deep."),
    SpeechClip("dial", "Turn the dial to the left before closing the panel."),
    SpeechClip("column", "The report lists thirty items in the second column."),
    SpeechClip("lamp", "The green lamp switches off when the door opens."),
    SpeechClip("powder", "Pour the water before you add the powder."),
    SpeechClip("meeting", "The workshop moved from Tuesday to Thursday."),
    SpeechClip("boxes", "There are four red boxes and nine blue ones."),
    SpeechClip("engine", "The engine runs quietly at low speed."),
    SpeechClip("valve", "Do not open the valve until the pressure drops."),
)

#: Twenty claims, ten true and ten false, in ten matched pairs.
#:
#: The families are chosen so a failure says something specific:
#:
#: * ``confusable_number`` -- seventeen/seventy, fifteen/fifty. The classic
#:   English minimal pair, and the one that matters most for a rubric: audio
#:   deliverables are full of quantities.
#: * ``direction`` / ``polarity`` -- left/right, off/on, quiet/loud. Single
#:   short words carrying the entire meaning.
#: * ``ordinal`` -- second/third.
#: * ``order`` -- which of two named things came first. Cannot be answered by
#:   spotting a word; both words are present.
#: * ``binding`` -- which number attaches to which colour. Same.
#: * ``negation`` -- whether an instruction was a prohibition.
#:
#: The last three are the ones a keyword-spotter fails and a listener passes.
CLAIMS: tuple[SpeechClaim, ...] = (
    SpeechClaim(
        "crate_seventeen", "crate_number", "crate", "confusable_number",
        "The speaker states a quantity of seventeen.", True,
        "the sentence is 'seventeen bolts'",
    ),
    SpeechClaim(
        "crate_seventy", "crate_number", "crate", "confusable_number",
        "The speaker states a quantity of seventy.", False,
        "seventeen, not seventy -- the pair this corpus exists for",
    ),
    SpeechClaim(
        "shelf_fifteen", "shelf_number", "shelf", "confusable_number",
        "The speaker gives a measurement of fifteen centimetres.", True,
        "the sentence is 'fifteen centimetres deep'",
    ),
    SpeechClaim(
        "shelf_fifty", "shelf_number", "shelf", "confusable_number",
        "The speaker gives a measurement of fifty centimetres.", False,
        "fifteen, not fifty",
    ),
    SpeechClaim(
        "dial_left", "dial_direction", "dial", "direction",
        "The speaker says to turn the dial to the left.", True,
        "the sentence is 'turn the dial to the left'",
    ),
    SpeechClaim(
        "dial_right", "dial_direction", "dial", "direction",
        "The speaker says to turn the dial to the right.", False,
        "left, not right",
    ),
    SpeechClaim(
        "column_second", "column_ordinal", "column", "ordinal",
        "The speaker refers to the second column.", True,
        "the sentence is 'in the second column'",
    ),
    SpeechClaim(
        "column_third", "column_ordinal", "column", "ordinal",
        "The speaker refers to the third column.", False,
        "second, not third",
    ),
    SpeechClaim(
        "lamp_off", "lamp_polarity", "lamp", "polarity",
        "The speaker says the lamp switches off.", True,
        "the sentence is 'switches off when the door opens'",
    ),
    SpeechClaim(
        "lamp_on", "lamp_polarity", "lamp", "polarity",
        "The speaker says the lamp switches on.", False,
        "off, not on",
    ),
    SpeechClaim(
        "powder_water_first", "powder_order", "powder", "order",
        "The speaker says the water goes in before the powder.", True,
        "'pour the water before you add the powder'",
    ),
    SpeechClaim(
        "powder_powder_first", "powder_order", "powder", "order",
        "The speaker says the powder goes in before the water.", False,
        "the order is reversed; both words are present, so spotting them "
        "is not enough",
    ),
    SpeechClaim(
        "meeting_to_thursday", "meeting_order", "meeting", "order",
        "The speaker says the workshop was moved to Thursday.", True,
        "'moved from Tuesday to Thursday'",
    ),
    SpeechClaim(
        "meeting_to_tuesday", "meeting_order", "meeting", "order",
        "The speaker says the workshop was moved to Tuesday.", False,
        "Tuesday is the day it moved FROM; the word is in the clip",
    ),
    SpeechClaim(
        "boxes_nine_blue", "boxes_binding", "boxes", "binding",
        "The speaker says there are nine blue boxes.", True,
        "'four red boxes and nine blue ones'",
    ),
    SpeechClaim(
        "boxes_four_blue", "boxes_binding", "boxes", "binding",
        "The speaker says there are four blue boxes.", False,
        "four belongs to red; both numbers are in the clip",
    ),
    SpeechClaim(
        "engine_quiet", "engine_polarity", "engine", "polarity",
        "The speaker says the engine runs quietly.", True,
        "'the engine runs quietly at low speed'",
    ),
    SpeechClaim(
        "engine_loud", "engine_polarity", "engine", "polarity",
        "The speaker says the engine runs loudly.", False,
        "quietly, not loudly",
    ),
    SpeechClaim(
        "valve_wait", "valve_negation", "valve", "negation",
        "The speaker says to wait until the pressure drops before opening "
        "the valve.", True,
        "'do not open the valve until the pressure drops'",
    ),
    SpeechClaim(
        "valve_open_now", "valve_negation", "valve", "negation",
        "The speaker says to open the valve before the pressure drops.", False,
        "the instruction is a prohibition, and this reverses it while keeping "
        "every content word, so only the 'do not ... until' can separate them",
    ),
)


def espeak_argv(text: str, out_path: Path) -> list[str]:
    """The exact command used to synthesise one clip.

    Built in one place and recorded in the manifest, so a reader rebuilding a
    clip runs what was run rather than what the prose says was run.
    """
    return [
        ESPEAK_BINARY,
        "-v", ESPEAK_VOICE,
        "-s", str(ESPEAK_WORDS_PER_MINUTE),
        "-p", str(ESPEAK_PITCH),
        "-a", str(ESPEAK_AMPLITUDE),
        "-w", str(out_path),
        text,
    ]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(argv: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(argv), capture_output=True, text=True, timeout=120, check=False
    )


def espeak_provenance() -> dict[str, Any]:
    """Everything knowable about the synthesiser on this machine.

    Raises if it is absent. The caller is expected to let that propagate: a
    fixture built by a *different* tool than the one recorded is worse than no
    fixture, because it looks like one.
    """
    resolved = shutil.which(ESPEAK_BINARY)
    if not resolved:
        raise FileNotFoundError(
            f"{ESPEAK_BINARY} is not on PATH. This host cannot build the "
            f"speech set; build it in CI (see "
            f".github/workflows/speech-verification-set.yml) and download the "
            f"artifact."
        )
    binary = Path(resolved).resolve()

    version = _run([ESPEAK_BINARY, "--version"])
    # espeak-ng prints its version to stdout; some builds use stderr.
    version_text = (version.stdout or version.stderr or "").strip()

    # Where the binary came from, asked of the package manager rather than
    # assumed. Absent on a host without dpkg, which is a fact about the host
    # and is recorded as null rather than guessed at.
    package: dict[str, Any] = {
        "manager": None, "name": None, "version": None, "source": None,
    }
    if shutil.which("dpkg-query"):
        owner = _run(["dpkg-query", "-S", str(binary)])
        if owner.returncode == 0 and ":" in owner.stdout:
            name = owner.stdout.split(":", 1)[0].strip()
            info = _run(["dpkg-query", "-W", "-f=${Version}\t${Homepage}", name])
            fields = info.stdout.split("\t") if info.returncode == 0 else []
            package = {
                "manager": "dpkg",
                "name": name,
                "version": fields[0].strip() if fields else None,
                "source": (fields[1].strip() if len(fields) > 1 else None) or None,
            }

    return {
        "tool": ESPEAK_BINARY,
        "version_string": version_text,
        "binary_path": str(binary),
        "binary_sha256": _sha256_file(binary),
        "package": package,
        "license": ESPEAK_LICENSE,
        "homepage": ESPEAK_HOMEPAGE,
        "redistributed_here": False,
        "license_note": (
            "eSpeak NG is GPL-3.0-or-later. This repository redistributes none "
            "of it -- no source, no binary, no dictionary, and no generated "
            "clip. The synthesiser is installed in CI, the clips are uploaded "
            "as build artifacts, and only digests are committed."
        ),
        "voice": ESPEAK_VOICE,
        "words_per_minute": ESPEAK_WORDS_PER_MINUTE,
        "pitch": ESPEAK_PITCH,
        "amplitude": ESPEAK_AMPLITUDE,
    }


def encoder_provenance() -> dict[str, Any]:
    """What re-encoded the clips on the way to the model.

    Separate from :func:`espeak_provenance` because it is a separate claim.
    The source digests reproduce from eSpeak NG alone; the sent digests need
    this too, and a rebuild that matches one but not the other is telling you
    which half moved.

    This is not an extra dependency taken on for the fixture -- it is the
    library the grading path already decodes and re-encodes with. Recording it
    is how the ``sent`` digests stay checkable.
    """
    try:
        import av  # type: ignore
    except ImportError:
        return {
            "library": None,
            "note": (
                "PyAV is absent, so the grading path could not re-encode and "
                "no `sent` digest was produced."
            ),
        }

    versions = getattr(av, "library_versions", None) or {}
    return {
        "library": "PyAV",
        "version": getattr(av, "__version__", None),
        "ffmpeg_libraries": {
            name: ".".join(str(part) for part in value)
            for name, value in sorted(versions.items())
        },
        "function": "core.perception.audio._trim_audio_bytes",
        "target": f"{SPEECH_SAMPLE_RATE_HZ} Hz mono s16",
        "note": (
            "The `sent` bytes are what this function returns for the `source` "
            "file at the default window, which is the call a real grading run "
            "makes. A `sent` digest that differs while `source` matches means "
            "this encoder moved, not the synthesiser."
        ),
    }


def _wav_facts(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as handle:
        return _wav_facts_from_handle(handle)


def _wav_facts_from_bytes(data: bytes) -> dict[str, Any]:
    """The same facts, for audio that exists only in memory.

    What :func:`_trim_audio_bytes` returns never touches the disk on a real
    grading call, and the check that matters is about those bytes.
    """
    with wave.open(io.BytesIO(data), "rb") as handle:
        return _wav_facts_from_handle(handle)


def _wav_facts_from_handle(handle: wave.Wave_read) -> dict[str, Any]:
    frames = handle.getnframes()
    rate = handle.getframerate()
    return {
        "channels": handle.getnchannels(),
        "sample_width_bytes": handle.getsampwidth(),
        "sample_rate_hz": rate,
        "frames": frames,
        "seconds": round(frames / rate, 4) if rate else None,
    }


def synthesise(clip: SpeechClip, out_dir: Path) -> dict[str, Any]:
    """Render one clip, then pin both what was written and what gets sent.

    Two files come out of this, and the distinction is the point. eSpeak NG
    writes at its voice's own rate; the grading path re-encodes whatever it is
    given to 16 kHz mono before the model hears any of it. Pinning only the
    first would describe a file that is never transmitted, and pinning only the
    second would leave the synthesis unreproducible. So both are written, both
    are hashed, and the conversion between them is done by the grader's own
    :func:`_trim_audio_bytes` rather than by a second encoder that would need
    its own version pinned to mean anything.
    """
    source_path = out_dir / f"{clip.clip_id}.source.wav"
    argv = espeak_argv(clip.transcript, source_path)
    result = _run(argv)
    if result.returncode != 0 or not source_path.is_file():
        raise RuntimeError(
            f"espeak-ng failed for {clip.clip_id}: rc={result.returncode} "
            f"{(result.stderr or '').strip()[:300]}"
        )

    source_facts = _wav_facts(source_path)

    # The clips are seconds long and the trim window is tens of seconds, so
    # this cuts nothing; it is called at its defaults precisely so that it is
    # the same call the grading path makes. Passing a narrower window here
    # would pin bytes that a real call would not produce.
    sent_bytes, sent_format = _trim_audio_bytes(
        str(source_path), AUDIO_TRIM_SECONDS, 0.0
    )
    sent_facts = _wav_facts_from_bytes(sent_bytes)
    if sent_facts["sample_rate_hz"] != SPEECH_SAMPLE_RATE_HZ:
        # Still not resampled by hand. If the grading path stops delivering at
        # the rate this file expects, that is a change in what the model hears
        # and the fixture has to be rebuilt knowing it -- not quietly patched
        # up here so the digests keep matching.
        raise RuntimeError(
            f"{clip.clip_id}: the grading path delivered "
            f"{sent_facts['sample_rate_hz']} Hz, but this set is pinned "
            f"against {SPEECH_SAMPLE_RATE_HZ} Hz. Refusing to resample: the "
            f"manifest must pin the bytes that are actually sent."
        )
    if sent_facts["channels"] != 1:
        raise RuntimeError(
            f"{clip.clip_id}: the grading path delivered "
            f"{sent_facts['channels']} channels, expected mono."
        )

    sent_path = out_dir / f"{clip.clip_id}.sent.{sent_format}"
    sent_path.write_bytes(sent_bytes)

    return {
        "clip_id": clip.clip_id,
        "command": argv,
        # What eSpeak NG produced. Reproducible from `command` given the same
        # version, and that is what a rebuild check compares first.
        "source": {
            "file": source_path.name,
            "sha256": _sha256_file(source_path),
            "bytes": source_path.stat().st_size,
            **source_facts,
        },
        # What the model actually receives. Reproducing this additionally
        # requires the same PyAV/ffmpeg, which is why `encoder` is recorded.
        "sent": {
            "file": sent_path.name,
            "sha256": hashlib.sha256(sent_bytes).hexdigest(),
            "bytes": len(sent_bytes),
            "format": sent_format,
            **sent_facts,
        },
    }


def build(out_dir: Path) -> dict[str, Any]:
    """Synthesise the whole set and return its manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    provenance = espeak_provenance()
    encoder = encoder_provenance()
    clips = [synthesise(clip, out_dir) for clip in CLIPS]

    true_claims = sum(1 for c in CLAIMS if c.holds)
    return {
        "what_this_is": (
            "A pinned, privacy-free speech set for checking whether the audio "
            "sub-judge hears words. Synthetic speech, so a pass is strong "
            "evidence and a failure is weak: see limits.reading."
        ),
        "provenance": provenance,
        "encoder": encoder,
        "clips": clips,
        # Ground truth. Never sent to the model -- the judging path reads
        # `criterion` alone, one at a time.
        "claims": [asdict(claim) for claim in CLAIMS],
        "corpus": {
            "clips": len(CLIPS),
            "claims": len(CLAIMS),
            "true_claims": true_claims,
            "false_claims": len(CLAIMS) - true_claims,
            "pairs": len({c.pair_id for c in CLAIMS}),
            "families": sorted({c.family for c in CLAIMS}),
        },
        "limits": {
            "voice": "synthetic formant synthesis, not a human speaker",
            "reading": (
                "A pass confirms the judge can hear speech. A failure does NOT "
                "show it cannot hear people -- only that it cannot hear "
                "eSpeak, which is harder to understand than a human voice. "
                "This set can confirm the capability; it cannot refute it."
            ),
            "language": "en-us only",
            "not_measured": [
                "human speech", "accented speech", "overlapping speakers",
                "background noise", "languages other than English",
            ],
            "delivery_is_not_understanding": (
                "Audio token usage shows the sound was delivered and billed. "
                "It is not evidence that anything was understood; that is what "
                "the paired claims are for."
            ),
        },
        "privacy": {
            "recorded_audio": False,
            "cloned_voice": False,
            "personal_data": False,
            "note": (
                "Every sentence was written for this file and names no person, "
                "place, organisation, date or identifier."
            ),
        },
    }


def compare_to_expected(
    manifest: dict[str, Any], expected: dict[str, Any]
) -> list[str]:
    """Differences that matter, as human sentences. Empty means reproduced.

    Compares digests and corpus shape, not the whole document: the provenance
    block legitimately differs between hosts (paths, package versions), and
    demanding byte-equality there would make the check fail for reasons that
    say nothing about the audio.

    Both digests are compared, and they fail with different sentences on
    purpose. A ``source`` mismatch means a different synthesiser; a ``sent``
    mismatch with a matching ``source`` means the same speech re-encoded by a
    different ffmpeg. Reporting one number for both would leave a reader
    guessing which half of the chain moved.
    """
    problems: list[str] = []

    def _digests(doc: dict[str, Any], part: str) -> dict[str, str]:
        found = {}
        for clip in doc.get("clips", []):
            digest = (clip.get(part) or {}).get("sha256")
            if digest:
                found[clip["clip_id"]] = digest
        return found

    got_ids = {c["clip_id"] for c in manifest.get("clips", [])}
    want_ids = {c["clip_id"] for c in expected.get("clips", [])}
    for clip_id in sorted(want_ids - got_ids):
        problems.append(f"{clip_id}: expected but not built")
    for clip_id in sorted(got_ids - want_ids):
        problems.append(f"{clip_id}: built but not in the expected manifest")

    shared = sorted(got_ids & want_ids)
    for part, cause in (
        ("source", "a different espeak-ng version is the usual cause; "
                   "compare provenance.version_string"),
        ("sent", "the synthesised audio matched, so this is the re-encoder; "
                 "compare encoder.ffmpeg_libraries"),
    ):
        got = _digests(manifest, part)
        want = _digests(expected, part)
        for clip_id in shared:
            if clip_id not in got or clip_id not in want:
                # An older manifest may predate one of the two digests. Say so
                # rather than reporting a mismatch that was never measured.
                if clip_id in got or clip_id in want:
                    problems.append(
                        f"{clip_id}: {part} sha256 is present on one side and "
                        f"missing on the other, so the two cannot be compared"
                    )
                continue
            if got[clip_id] != want[clip_id]:
                problems.append(
                    f"{clip_id}: {part} sha256 {got[clip_id][:16]}... != "
                    f"expected {want[clip_id][:16]}... ({cause})"
                )

    got_corpus = manifest["corpus"]
    want_corpus = expected.get("corpus", {})
    for key in ("clips", "claims", "true_claims", "false_claims", "pairs"):
        if key in want_corpus and got_corpus.get(key) != want_corpus[key]:
            problems.append(
                f"corpus.{key}: {got_corpus.get(key)} != expected "
                f"{want_corpus[key]}"
            )
    return problems


def describe() -> str:
    """The corpus, without synthesising anything.

    Runs on this NAS, where espeak-ng cannot be installed. The point is that
    the corpus can be reviewed -- which is the part that needs human judgement
    -- on a machine that cannot build it.
    """
    out: list[str] = []
    out.append(f"{len(CLIPS)} clips, {len(CLAIMS)} claims, "
               f"{len({c.pair_id for c in CLAIMS})} matched pairs "
               f"({sum(1 for c in CLAIMS if c.holds)} true / "
               f"{sum(1 for c in CLAIMS if not c.holds)} false)")
    out.append("")
    by_clip = {clip.clip_id: clip for clip in CLIPS}
    for pair_id in dict.fromkeys(c.pair_id for c in CLAIMS):
        members = [c for c in CLAIMS if c.pair_id == pair_id]
        clip = by_clip[members[0].clip_id]
        out.append(f"  [{members[0].family}] {clip.clip_id}: "
                   f"“{clip.transcript}”")
        for claim in members:
            mark = "T" if claim.holds else "F"
            out.append(f"      ({mark}) {claim.criterion}")
        out.append("")
    out.append("The transcripts above are ground truth and are never sent to "
               "the model; only the criteria are.")
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default="speech-verification-set",
                    help="where the WAVs and manifest.json are written")
    ap.add_argument("--expect-manifest", default=None,
                    help="a previously published manifest to reproduce; "
                         "any digest mismatch is an error")
    ap.add_argument("--describe", action="store_true",
                    help="print the corpus and exit, synthesising nothing")
    args = ap.parse_args(argv)

    if args.describe:
        print(describe())
        return 0

    out_dir = Path(args.out_dir)
    manifest = build(out_dir)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    prov = manifest["provenance"]
    encoder = manifest["encoder"]
    print(f"built {len(manifest['clips'])} clips in {out_dir}")
    print(f"  tool    : {prov['version_string']}")
    print(f"  package : {prov['package']['name']} "
          f"{prov['package']['version']} ({prov['package']['manager']})")
    print(f"  licence : {prov['license']} (redistributed here: "
          f"{prov['redistributed_here']})")
    print(f"  binary  : sha256 {prov['binary_sha256']}")
    print(f"  encoder : {encoder.get('library')} {encoder.get('version')} "
          f"-> {encoder.get('target')}")
    print(f"  manifest: {manifest_path}")
    # Both digests, labelled. The synthesised file is not the one that is
    # sent, and a single unlabelled column would invite reading either as the
    # other.
    for clip in manifest["clips"]:
        source, sent = clip["source"], clip["sent"]
        print(f"    {clip['clip_id']:<10} {sent['seconds']:>6.2f}s")
        print(f"      synthesised ({source['sample_rate_hz']} Hz): "
              f"{source['sha256']}")
        print(f"      delivered   ({sent['sample_rate_hz']} Hz): "
              f"{sent['sha256']}")

    if args.expect_manifest:
        expected = json.loads(
            Path(args.expect_manifest).read_text(encoding="utf-8")
        )
        problems = compare_to_expected(manifest, expected)
        if problems:
            print("\nthis build does NOT reproduce the expected manifest:",
                  file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        print("\nreproduces the expected manifest exactly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
