---
name: audio
title: Audio Perception & Synthesis
description: >-
  Hearing for the sandbox. Use for any task with audio reference files
  (.wav/.mp3/.flac/.ogg/.m4a/.aac/.aiff) or that asks to analyze, transcribe,
  measure, mix, master, or generate sound. Provides FFT / spectral-peak
  analysis, mel-spectrogram rendering, waveform sampling/decimation, integrated
  loudness (LUFS), tempo/BPM detection, resampling, and tone/clip synthesis.
modalities: [audio]
file_extensions: [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff"]
keywords:
  [audio, sound, music, voice, speech, spectrogram, fft, frequency, spectral,
   waveform, sample rate, sampling, resample, loudness, lufs, decibel, db,
   tempo, bpm, beat, pitch, mix, master, mono, stereo, transcribe, podcast]
requires: [librosa, soundfile, numpy, scipy, pyloudnorm]
version: 1.0.0
---

# Audio Skill — give the sandbox *ears*

Use this skill whenever the task involves listening to or producing sound.
Prefer these helpers over hand-rolled DSP: they wrap **librosa**, **soundfile**,
**scipy**, and **pyloudnorm** with safe defaults.

A typical "audio problem" workflow:

1. `info = audio.audio_info(path)` — duration, sample rate, channels.
2. `peaks = audio.fft_summary(path)` — dominant frequencies ("what is in it").
3. `audio.spectrogram_png(path, "spectrogram.png")` — a visual you can ship.
4. Decide / transform (resample, normalise loudness, mix, synthesise).
5. Save deliverables with `audio.save_wav(...)`.

## Toolkit API

```python
from skills import audio

audio.audio_info(path) -> dict
    # {sample_rate, duration_sec, channels, n_samples, frames, format}

audio.load_audio(path, sr=None, mono=True) -> (numpy.ndarray, int)
    # waveform y in [-1, 1], native sample rate unless sr given

audio.fft_summary(path, top_k=8, sr=22050) -> dict
    # rFFT magnitude spectrum -> {dominant_hz:[...], magnitudes:[...],
    #                             spectral_centroid_hz, rms, peak_hz}

audio.sample_waveform(path, n=2000) -> list[float]
    # amplitude envelope decimated to n points (cheap "shape" of the signal)

audio.spectrogram_png(path, out="spectrogram.png", n_mels=128) -> str
    # render a mel-spectrogram PNG; returns the output path

audio.loudness_lufs(path) -> float
    # ITU-R BS.1770 integrated loudness via pyloudnorm

audio.tempo_bpm(path) -> float
    # estimated tempo (beats per minute)

audio.resample(path, target_sr, out) -> str
    # write a resampled copy

audio.synth_tone(freq_hz, seconds, sr=44100, amp=0.5) -> (numpy.ndarray, int)
audio.save_wav(y, sr, out) -> str
```

Notes:
- `fft_summary` loads at 22.05 kHz mono by default for speed; pass `sr=None` to
  use the file's native rate.
- All functions accept absolute or relative paths (reference files are copied
  into the working directory).
