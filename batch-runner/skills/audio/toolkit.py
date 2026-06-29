"""Audio skill toolkit — FFT / sampling / spectrogram / loudness / tempo.

Hearing for the sandbox. Heavy libraries (librosa, soundfile, scipy,
pyloudnorm) are imported lazily so importing this module never fails.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import List, Tuple

from skills import _require

__all__ = [
    "audio_info",
    "load_audio",
    "fft_summary",
    "sample_waveform",
    "spectrogram_png",
    "loudness_lufs",
    "tempo_bpm",
    "resample",
    "synth_tone",
    "save_wav",
]


def audio_info(path: str) -> dict:
    """Return basic metadata without a heavy decode when possible.

    Falls back to soundfile for non-WAV containers.
    """
    p = str(path)
    suffix = Path(p).suffix.lower()
    if suffix == ".wav":
        try:
            with wave.open(p, "rb") as wf:
                sr = wf.getframerate()
                n = wf.getnframes()
                ch = wf.getnchannels()
                return {
                    "sample_rate": sr,
                    "duration_sec": (n / sr) if sr else 0.0,
                    "channels": ch,
                    "n_samples": n,
                    "frames": n,
                    "format": "wav",
                }
        except Exception:
            pass
    sf = _require("soundfile", "soundfile")
    info = sf.info(p)
    return {
        "sample_rate": info.samplerate,
        "duration_sec": float(info.duration),
        "channels": info.channels,
        "n_samples": int(info.frames),
        "frames": int(info.frames),
        "format": info.format,
    }


def load_audio(path: str, sr: int | None = None, mono: bool = True) -> Tuple["object", int]:
    """Load a waveform as a float32 numpy array in [-1, 1] plus its sample rate."""
    librosa = _require("librosa", "librosa")
    y, out_sr = librosa.load(str(path), sr=sr, mono=mono)
    return y, int(out_sr)


def fft_summary(path: str, top_k: int = 8, sr: int | None = 22050) -> dict:
    """Dominant frequencies and spectral statistics via a real FFT."""
    np = _require("numpy", "numpy")
    librosa = _require("librosa", "librosa")
    y, out_sr = librosa.load(str(path), sr=sr, mono=True)
    if y.size == 0:
        return {"dominant_hz": [], "magnitudes": [], "spectral_centroid_hz": 0.0,
                "rms": 0.0, "peak_hz": 0.0, "sample_rate": out_sr}
    spectrum = np.abs(np.fft.rfft(y))
    freqs = np.fft.rfftfreq(y.size, d=1.0 / out_sr)
    k = int(max(1, min(top_k, spectrum.size)))
    top_idx = np.argsort(spectrum)[::-1][:k]
    top_idx = top_idx[np.argsort(freqs[top_idx])]
    centroid = float((freqs * spectrum).sum() / spectrum.sum()) if spectrum.sum() else 0.0
    return {
        "dominant_hz": [round(float(f), 2) for f in freqs[top_idx]],
        "magnitudes": [round(float(m), 4) for m in spectrum[top_idx]],
        "spectral_centroid_hz": round(centroid, 2),
        "rms": round(float(np.sqrt(np.mean(y ** 2))), 6),
        "peak_hz": round(float(freqs[int(np.argmax(spectrum))]), 2),
        "sample_rate": out_sr,
    }


def sample_waveform(path: str, n: int = 2000) -> List[float]:
    """Decimate the absolute amplitude envelope to ``n`` points."""
    np = _require("numpy", "numpy")
    librosa = _require("librosa", "librosa")
    y, _ = librosa.load(str(path), sr=None, mono=True)
    if y.size == 0:
        return []
    env = np.abs(y)
    if env.size <= n:
        return [round(float(v), 5) for v in env]
    step = env.size / n
    out = [round(float(env[min(env.size - 1, int(i * step))]), 5) for i in range(n)]
    return out


def spectrogram_png(path: str, out: str = "spectrogram.png", n_mels: int = 128) -> str:
    """Render a mel-spectrogram PNG and return its path."""
    np = _require("numpy", "numpy")
    librosa = _require("librosa", "librosa")
    _require("matplotlib", "matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    y, sr = librosa.load(str(path), sr=None, mono=True)
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_mels)
    mel_db = librosa.power_to_db(mel, ref=np.max)
    fig, ax = plt.subplots(figsize=(10, 4))
    img = librosa.display.specshow(mel_db, sr=sr, x_axis="time", y_axis="mel", ax=ax)
    fig.colorbar(img, ax=ax, format="%+2.0f dB")
    ax.set_title(f"Mel spectrogram — {Path(path).name}")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def loudness_lufs(path: str) -> float:
    """Integrated loudness (LUFS) per ITU-R BS.1770 via pyloudnorm."""
    sf = _require("soundfile", "soundfile")
    pyln = _require("pyloudnorm", "pyloudnorm")
    data, rate = sf.read(str(path))
    meter = pyln.Meter(rate)
    return float(meter.integrated_loudness(data))


def tempo_bpm(path: str) -> float:
    """Estimate tempo (beats per minute)."""
    librosa = _require("librosa", "librosa")
    y, sr = librosa.load(str(path), sr=None, mono=True)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    try:
        return round(float(tempo), 2)
    except TypeError:  # numpy array
        return round(float(tempo[0]), 2)


def resample(path: str, target_sr: int, out: str) -> str:
    """Write a resampled copy at ``target_sr`` and return its path."""
    librosa = _require("librosa", "librosa")
    sf = _require("soundfile", "soundfile")
    y, _ = librosa.load(str(path), sr=target_sr, mono=False)
    sf.write(out, y.T if getattr(y, "ndim", 1) > 1 else y, target_sr)
    return out


def synth_tone(freq_hz: float, seconds: float, sr: int = 44100, amp: float = 0.5):
    """Synthesise a sine tone. Returns ``(y, sr)``."""
    np = _require("numpy", "numpy")
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = (amp * np.sin(2 * np.pi * freq_hz * t)).astype("float32")
    return y, sr


def save_wav(y, sr: int, out: str) -> str:
    """Write a waveform to a WAV file and return its path."""
    sf = _require("soundfile", "soundfile")
    sf.write(out, y, sr)
    return out
