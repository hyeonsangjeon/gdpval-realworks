"""The speech verification set: is it balanced, is it pinned, does it leak.

The tone corpus this repository already has can show that a verdict depends on
the audio. It cannot show that the judge hears *words*, and every one of the 31
graded audio deliverables is words. This set is the preparation for measuring
that, and these tests are what make it a fixture rather than ten WAV files.

None of them synthesise anything. eSpeak NG cannot be installed on the NAS
(kernel 3.10.102), so the build runs in CI -- and the half that needs human
judgement, which is whether the corpus is fair and whether it leaks its own
answers, is exactly the half that does not need the synthesiser. That
separation is deliberate: a corpus nobody can review until CI runs is a corpus
nobody reviews.
"""

from __future__ import annotations

import hashlib
import json
import sys
import wave
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_speech_verification_set as speech  # noqa: E402


# ── The corpus is a fair test ────────────────────────────────────────


def test_guessing_scores_exactly_half() -> None:
    """Ten true, ten false, and every pair split one-one.

    Balance at the corpus level is not enough: if a pair were true/true, a
    model that answered ``pass`` to that clip would be right twice for one
    act of hearing, and the pairing that the analysis leans on would be
    measuring nothing.
    """
    assert sum(1 for c in speech.CLAIMS if c.holds) == 10
    assert sum(1 for c in speech.CLAIMS if not c.holds) == 10

    by_pair: dict[str, list[bool]] = {}
    for claim in speech.CLAIMS:
        by_pair.setdefault(claim.pair_id, []).append(claim.holds)
    assert len(by_pair) == 10
    for pair_id, holds in by_pair.items():
        assert sorted(holds) == [False, True], f"{pair_id} is not a matched pair"


def test_a_pair_asks_about_one_clip_in_one_family() -> None:
    """Otherwise the pair is not a controlled comparison.

    Two claims about two different clips differ in the audio as well as the
    question, and a difference in the answers cannot be attributed to either.
    """
    for pair_id in {c.pair_id for c in speech.CLAIMS}:
        members = [c for c in speech.CLAIMS if c.pair_id == pair_id]
        assert len({m.clip_id for m in members}) == 1, pair_id
        assert len({m.family for m in members}) == 1, pair_id


def test_every_claim_points_at_a_clip_that_exists() -> None:
    clip_ids = {clip.clip_id for clip in speech.CLIPS}
    for claim in speech.CLAIMS:
        assert claim.clip_id in clip_ids, claim.claim_id


def test_nothing_is_named_twice() -> None:
    assert len({c.clip_id for c in speech.CLIPS}) == len(speech.CLIPS)
    assert len({c.claim_id for c in speech.CLAIMS}) == len(speech.CLAIMS)


def test_every_clip_is_actually_asked_about() -> None:
    """A clip nobody asks about is a clip that costs a synthesis and measures
    nothing -- and, more usefully, is a sign the corpus and the claims have
    drifted apart."""
    asked = {c.clip_id for c in speech.CLAIMS}
    assert asked == {c.clip_id for c in speech.CLIPS}


# ── The corpus does not hand over its answers ────────────────────────


def test_no_criterion_quotes_the_sentence_it_is_about() -> None:
    """The model is shown the criterion and nothing else.

    If a criterion contained the transcript, a model that heard silence could
    still answer it. This is the leak that would make the whole measurement
    worthless, and it is cheap to check mechanically.
    """
    transcripts = {c.clip_id: c.transcript for c in speech.CLIPS}
    for claim in speech.CLAIMS:
        sentence = transcripts[claim.clip_id].rstrip(".").lower()
        assert sentence not in claim.criterion.lower(), claim.claim_id


def test_the_two_halves_of_a_pair_are_hard_to_tell_apart_on_paper() -> None:
    """A pair has to differ in the audio, not in how plausible it reads.

    If the false member were obviously absurd -- "the speaker says the crate
    holds a thousand million bolts" -- a model could reject it from world
    knowledge without hearing anything, and the pair would measure prior
    plausibility. Requiring the two to share most of their words is a coarse
    proxy for that, but it catches the failure that matters.
    """
    for pair_id in {c.pair_id for c in speech.CLAIMS}:
        true_claim, false_claim = sorted(
            (c for c in speech.CLAIMS if c.pair_id == pair_id),
            key=lambda c: not c.holds,
        )
        true_words = set(true_claim.criterion.lower().rstrip(".").split())
        false_words = set(false_claim.criterion.lower().rstrip(".").split())
        shared = len(true_words & false_words) / len(true_words | false_words)
        assert shared >= 0.6, (
            f"{pair_id}: the two claims share only {shared:.0%} of their "
            f"words, so the false one may be rejectable without listening"
        )


def test_the_hardest_families_are_present() -> None:
    """Three families cannot be passed by spotting a keyword.

    ``order``, ``binding`` and ``negation`` all put every content word of the
    true claim into the clip; only the arrangement differs. Without them the
    set would be satisfiable by a transcriber that returns a bag of words, and
    "it heard the word seventeen" is a much weaker finding than "it heard what
    the sentence said".
    """
    families = {c.family for c in speech.CLAIMS}
    assert {"order", "binding", "negation"} <= families


def test_the_ground_truth_is_kept_out_of_the_model_facing_field() -> None:
    """``because`` explains the answer and is for a human auditing the corpus.

    It sits next to ``criterion`` in the same dataclass, which is exactly the
    arrangement that invites someone to send the whole object one day. The
    test says out loud which field is the model's.
    """
    for claim in speech.CLAIMS:
        assert claim.because, f"{claim.claim_id} has no stated reason"
        assert claim.because.lower() not in claim.criterion.lower()


# ── Privacy ──────────────────────────────────────────────────────────


def test_no_sentence_carries_personal_data() -> None:
    """No recorded audio, no cloned voice, and nothing about a person.

    The sentences are about crates and valves on purpose. Digits are the
    checkable part: an address, a phone number, a date or an identifier all
    need them, and spelling numbers out is required for the synthesiser to be
    deterministic anyway, so the two constraints agree.
    """
    for clip in speech.CLIPS:
        assert not any(ch.isdigit() for ch in clip.transcript), clip.clip_id
        for marker in ("@", "http", "http://", "www."):
            assert marker not in clip.transcript.lower(), clip.clip_id


# ── The pins ─────────────────────────────────────────────────────────


def test_the_command_fixes_every_knob_that_changes_the_waveform() -> None:
    """Voice, rate, pitch and amplitude are all passed explicitly.

    Any of them left to the tool's default makes the fixture depend on the
    runner image: the same command line on a different host would then
    produce a different digest, and the mismatch would be read as a corrupted
    build rather than an unpinned argument.
    """
    argv = speech.espeak_argv("hello", Path("/tmp/x.wav"))
    assert argv[0] == speech.ESPEAK_BINARY
    for flag, value in (
        ("-v", speech.ESPEAK_VOICE),
        ("-s", str(speech.ESPEAK_WORDS_PER_MINUTE)),
        ("-p", str(speech.ESPEAK_PITCH)),
        ("-a", str(speech.ESPEAK_AMPLITUDE)),
        ("-w", "/tmp/x.wav"),
    ):
        assert flag in argv, flag
        assert argv[argv.index(flag) + 1] == value, flag
    assert argv[-1] == "hello", "the text is the last argument"


def test_the_pinned_rate_is_the_graders_and_not_a_second_opinion() -> None:
    """16 kHz, read from the grading path rather than restated here.

    The clips are *not* authored at this rate -- eSpeak NG has no sample-rate
    option and ``en-us`` renders at 22050 Hz. This is the rate they arrive at,
    after :func:`_trim_audio_bytes` re-encodes them, which is the only rate the
    model ever hears. Restating ``16000`` as a literal would let the two drift
    apart silently and leave the manifest pinning a file nobody sends.
    """
    from core.perception.audio import AUDIO_SAMPLE_RATE_HZ

    assert speech.SPEECH_SAMPLE_RATE_HZ == AUDIO_SAMPLE_RATE_HZ


def test_a_missing_synthesiser_says_where_to_build_instead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The NAS case, which is the normal case for this repository.

    Kernel 3.10.102 cannot run a current espeak-ng build. The error has to
    route a reader to CI rather than read as "install this", because
    installing it here does not work.
    """
    monkeypatch.setattr(speech.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError) as caught:
        speech.espeak_provenance()
    assert "speech-verification-set.yml" in str(caught.value)


def _write_wav(path: Path, *, rate: int, seconds: float = 0.25) -> None:
    """A quiet mono WAV at ``rate``, written with the standard library.

    Stands in for eSpeak's output so the conversion below can be exercised on
    a host that cannot install eSpeak. What matters to the code under test is
    the container's sample rate, not what the samples contain.
    """
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * frames)


def test_the_clip_is_pinned_at_both_ends_of_the_conversion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The real 22050 -> 16000 step, run for real, on a host without eSpeak.

    This is the case that broke the first build: eSpeak NG has no sample-rate
    flag and ``en-us`` renders at 22050 Hz, so a fixture pinned only at the
    synthesiser describes a file that is re-encoded before anyone hears it.
    Both ends are recorded instead -- and the conversion is done by the
    grading path's own function, so no second encoder has to be trusted.

    Only ``_run`` is stubbed. The WAV is a real 22050 Hz container and the
    re-encode is the real one.
    """
    pytest.importorskip("av")
    clip = speech.CLIPS[0]
    source = tmp_path / f"{clip.clip_id}.source.wav"
    _write_wav(source, rate=22_050)
    monkeypatch.setattr(
        speech, "_run",
        lambda argv: __import__("subprocess").CompletedProcess(argv, 0, "", ""),
    )

    entry = speech.synthesise(clip, tmp_path)

    assert entry["source"]["sample_rate_hz"] == 22_050, "eSpeak's own rate"
    assert entry["sent"]["sample_rate_hz"] == speech.SPEECH_SAMPLE_RATE_HZ
    assert entry["sent"]["channels"] == 1
    # Two different files, and the manifest says which is which. A single
    # `sha256` field would have left a reader to assume the wrong one.
    assert entry["source"]["sha256"] != entry["sent"]["sha256"]
    assert (tmp_path / entry["source"]["file"]).is_file()
    sent_path = tmp_path / entry["sent"]["file"]
    assert sent_path.is_file()
    assert (hashlib.sha256(sent_path.read_bytes()).hexdigest()
            == entry["sent"]["sha256"]), "the digest names the file beside it"


def test_a_rate_the_grader_does_not_deliver_is_refused_rather_than_resampled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the grading path stops delivering 16 kHz, the fixture stops too.

    Patching it up here so the digests keep matching would hide a change in
    what the model actually hears behind a green build.
    """
    clip = speech.CLIPS[0]
    _write_wav(tmp_path / f"{clip.clip_id}.source.wav", rate=22_050)
    monkeypatch.setattr(
        speech, "_run",
        lambda argv: __import__("subprocess").CompletedProcess(argv, 0, "", ""),
    )
    monkeypatch.setattr(
        speech, "_trim_audio_bytes", lambda *_a, **_k: (b"stub", "wav")
    )
    monkeypatch.setattr(
        speech, "_wav_facts_from_bytes",
        lambda _b: {"channels": 1, "sample_width_bytes": 2,
                    "sample_rate_hz": 22_050, "frames": 100, "seconds": 0.005},
    )
    with pytest.raises(RuntimeError) as caught:
        speech.synthesise(clip, tmp_path)
    assert "Refusing to resample" in str(caught.value)


def test_the_re_encoder_is_recorded_because_the_sent_digest_depends_on_it(
) -> None:
    """A ``sent`` digest reproduces only against the same ffmpeg.

    Recording the synthesiser alone would make a mismatch unattributable: the
    reader could not tell whether the speech changed or only the encoding did.
    """
    pytest.importorskip("av")
    encoder = speech.encoder_provenance()
    assert encoder["library"] == "PyAV"
    assert encoder["version"]
    assert encoder["ffmpeg_libraries"]
    assert encoder["function"].endswith("_trim_audio_bytes")


# ── Reproducing a published set ──────────────────────────────────────


def _manifest(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "clips": [
            {
                "clip_id": clip.clip_id,
                "source": {"sha256": f"{i:064d}"},
                "sent": {"sha256": f"{i + 100:064d}"},
            }
            for i, clip in enumerate(speech.CLIPS)
        ],
        "corpus": {
            "clips": len(speech.CLIPS),
            "claims": len(speech.CLAIMS),
            "true_claims": 10,
            "false_claims": 10,
            "pairs": 10,
        },
    }
    base.update(over)
    return base


def test_an_identical_rebuild_reports_no_problems() -> None:
    assert speech.compare_to_expected(_manifest(), _manifest()) == []


def test_a_changed_synthesis_is_caught_and_says_the_likely_cause() -> None:
    """The expected failure, and the one a reader will hit.

    A different espeak-ng version is overwhelmingly the reason a rebuild
    differs, so the message says to compare version strings instead of leaving
    someone to suspect the audio pipeline.
    """
    built = _manifest()
    built["clips"][0] = {
        **built["clips"][0], "source": {"sha256": "f" * 64},
    }
    problems = speech.compare_to_expected(built, _manifest())
    assert len(problems) == 1
    assert speech.CLIPS[0].clip_id in problems[0]
    assert "espeak-ng version" in problems[0]


def test_the_same_speech_encoded_differently_blames_the_encoder() -> None:
    """Source matched, sent did not: that is ffmpeg, not the synthesiser.

    Collapsing both digests into one number would report this as "the audio
    changed" and send a reader to check the wrong tool.
    """
    built = _manifest()
    built["clips"][0] = {**built["clips"][0], "sent": {"sha256": "f" * 64}}
    problems = speech.compare_to_expected(built, _manifest())
    assert len(problems) == 1
    assert "encoder.ffmpeg_libraries" in problems[0]
    assert "espeak-ng" not in problems[0]


def test_a_manifest_missing_one_of_the_two_digests_is_not_called_a_match() -> None:
    """An older manifest predates the ``sent`` digest.

    Silently skipping the comparison would report a clean reproduction of
    something that was never checked.
    """
    old = _manifest()
    old["clips"] = [{"clip_id": c["clip_id"], "source": c["source"]}
                    for c in old["clips"]]
    problems = speech.compare_to_expected(_manifest(), old)
    assert any("cannot be compared" in p for p in problems)


def test_a_missing_or_extra_clip_is_caught() -> None:
    short = _manifest()
    short["clips"] = short["clips"][:-1]
    assert any("expected but not built" in p
               for p in speech.compare_to_expected(short, _manifest()))
    assert any("built but not in the expected manifest" in p
               for p in speech.compare_to_expected(_manifest(), short))


def test_a_corpus_that_grew_without_a_new_manifest_is_caught() -> None:
    """Adding a claim changes what the set measures.

    Reusing an old manifest against a bigger corpus would report a clean
    reproduction of a set that no longer exists.
    """
    stale = _manifest()
    stale["corpus"] = {**stale["corpus"], "claims": 18, "true_claims": 9}
    problems = speech.compare_to_expected(_manifest(), stale)
    assert any("corpus.claims" in p for p in problems)


# ── What the manifest promises about itself ──────────────────────────


def _stub_clip_entry(clip: Any) -> dict[str, Any]:
    """A clip entry of the real shape, without running a synthesiser.

    Shaped like the real thing rather than minimal, so that the JSON
    round-trip below is exercised against what a build actually emits.
    """
    return {
        "clip_id": clip.clip_id,
        "command": [speech.ESPEAK_BINARY, "-v", speech.ESPEAK_VOICE],
        "source": {"file": f"{clip.clip_id}.source.wav", "sha256": "0" * 64,
                   "bytes": 1, "sample_rate_hz": 22_050, "seconds": 1.0},
        "sent": {"file": f"{clip.clip_id}.sent.wav", "sha256": "1" * 64,
                 "bytes": 1, "format": "wav",
                 "sample_rate_hz": speech.SPEECH_SAMPLE_RATE_HZ,
                 "seconds": 1.0},
    }


def test_the_manifest_states_the_asymmetry_between_pass_and_fail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Synthetic speech confirms the capability; it cannot refute it.

    Reporting a failure on eSpeak as "the judge cannot hear speech" would be
    the same overreach as reporting audio token usage as comprehension. The
    limit is a field in the output, not a caveat in a document nobody opens
    beside the number.
    """
    monkeypatch.setattr(speech, "espeak_provenance", lambda: {"tool": "stub"})
    monkeypatch.setattr(
        speech, "synthesise",
        lambda clip, _out: _stub_clip_entry(clip),
    )
    manifest = speech.build(tmp_path)

    limits = manifest["limits"]
    assert "cannot refute" in limits["reading"]
    assert manifest["privacy"]["recorded_audio"] is False
    assert manifest["privacy"]["cloned_voice"] is False
    assert "delivery_is_not_understanding" in limits
    assert manifest["corpus"]["true_claims"] == 10
    assert manifest["corpus"]["false_claims"] == 10


def test_the_manifest_carries_the_ground_truth_and_the_workflow_does_not_ship_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The manifest is the answer key, so where it goes matters.

    It has to hold the transcripts -- that is what makes the set checkable --
    which is exactly why the judging path must read ``criterion`` and nothing
    else. This test records that the key exists and is complete; the leak
    check above records that the criteria do not contain it.
    """
    monkeypatch.setattr(speech, "espeak_provenance", lambda: {"tool": "stub"})
    monkeypatch.setattr(
        speech, "synthesise",
        lambda clip, _out: _stub_clip_entry(clip),
    )
    manifest = speech.build(tmp_path)
    assert len(manifest["claims"]) == 20
    assert all("holds" in claim for claim in manifest["claims"])
    # Round-trips as JSON: the manifest is uploaded as an artifact, and a
    # dataclass that does not serialise would fail at the end of the build.
    json.dumps(manifest, ensure_ascii=False)


def test_the_licence_is_recorded_with_what_is_and_is_not_redistributed() -> None:
    """GPL-3.0-or-later, and nothing of eSpeak's ships from this repository.

    The clips are build artifacts and only their digests are committed. That
    distinction is the whole of the licence position, so it is stated where an
    auditor reads it rather than left to be reconstructed.
    """
    assert speech.ESPEAK_LICENSE == "GPL-3.0-or-later"
    assert speech.ESPEAK_HOMEPAGE.startswith("https://")
