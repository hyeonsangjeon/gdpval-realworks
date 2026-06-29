"""Video skill toolkit — frame-by-frame perception.

Vision for the sandbox. Heavy libraries (cv2, av, moviepy, PIL) are imported
lazily so importing this module never fails. Frame I/O prefers OpenCV and
falls back to PyAV.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from skills import _require

__all__ = [
    "video_info",
    "extract_frames",
    "keyframes",
    "frame_at",
    "scene_changes",
    "extract_audio",
    "montage",
]


def _cv2():
    return _require("cv2", "opencv-python")


def video_info(path: str) -> dict:
    """Return fps, frame_count, duration, width, height, codec."""
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join([chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)]).strip("\x00")
        return {
            "fps": round(fps, 3),
            "frame_count": frame_count,
            "duration_sec": round(frame_count / fps, 3) if fps else 0.0,
            "width": width,
            "height": height,
            "codec": codec,
        }
    finally:
        cap.release()


def extract_frames(path: str, every_sec: float = 1.0, out_dir: str = "frames",
                   limit: Optional[int] = None) -> List[str]:
    """Save one frame per ``every_sec`` seconds; return saved PNG paths."""
    cv2 = _cv2()
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(str(path))
    saved: List[str] = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        stride = max(1, int(round(fps * every_sec)))
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0:
                t = idx / fps
                out = os.path.join(out_dir, f"frame_{t:07.2f}s.png")
                cv2.imwrite(out, frame)
                saved.append(out)
                if limit and len(saved) >= limit:
                    break
            idx += 1
    finally:
        cap.release()
    return saved


def keyframes(path: str, max_frames: int = 8, out_dir: str = "keyframes") -> List[str]:
    """Uniformly sample ``max_frames`` stills across the whole clip."""
    cv2 = _cv2()
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(str(path))
    saved: List[str] = []
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        if frame_count <= 0:
            # Unknown length: read sequentially, keep every Nth up to max_frames.
            frames = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame)
                if len(frames) > 5000:
                    break
            if not frames:
                return []
            picks = [int(i * (len(frames) - 1) / max(1, max_frames - 1))
                     for i in range(max_frames)]
            for n, i in enumerate(sorted(set(picks))):
                out = os.path.join(out_dir, f"keyframe_{n:02d}.png")
                cv2.imwrite(out, frames[i])
                saved.append(out)
            return saved
        picks = [int(i * (frame_count - 1) / max(1, max_frames - 1))
                 for i in range(max_frames)]
        for n, fno in enumerate(sorted(set(picks))):
            cap.set(cv2.CAP_PROP_POS_FRAMES, fno)
            ok, frame = cap.read()
            if not ok:
                continue
            t = fno / fps
            out = os.path.join(out_dir, f"keyframe_{n:02d}_{t:07.2f}s.png")
            cv2.imwrite(out, frame)
            saved.append(out)
    finally:
        cap.release()
    return saved


def frame_at(path: str, t_sec: float, out: Optional[str] = None) -> str:
    """Extract a single frame at timestamp ``t_sec``."""
    cv2 = _cv2()
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"could not read frame at {t_sec}s from {path}")
        out = out or f"frame_{t_sec:07.2f}s.png"
        cv2.imwrite(out, frame)
        return out
    finally:
        cap.release()


def scene_changes(path: str, threshold: float = 0.45, max_samples: int = 300) -> List[float]:
    """Detect shot boundaries via HSV-histogram correlation between frames.

    Returns a list of timestamps (seconds) where the content jumps.
    """
    cv2 = _cv2()
    np = _require("numpy", "numpy")
    cap = cv2.VideoCapture(str(path))
    cuts: List[float] = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        stride = max(1, frame_count // max_samples) if frame_count else 1
        prev_hist = None
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % stride == 0:
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
                cv2.normalize(hist, hist)
                if prev_hist is not None:
                    corr = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL)
                    if corr < (1.0 - threshold):
                        cuts.append(round(idx / fps, 2))
                prev_hist = hist
            idx += 1
    finally:
        cap.release()
    return cuts


def extract_audio(path: str, out: str = "audio.wav") -> str:
    """Extract the audio track to WAV (feed the result to the ``audio`` skill)."""
    try:
        moviepy = _require("moviepy.editor", "moviepy")
        clip = moviepy.VideoFileClip(str(path))
        if clip.audio is None:
            clip.close()
            raise ValueError(f"{path} has no audio track")
        clip.audio.write_audiofile(out, logger=None)
        clip.close()
        return out
    except Exception:
        # Fall back to PyAV remux if moviepy/ffmpeg wrapper is unavailable.
        av = _require("av", "av")
        import fractions  # noqa: F401
        container = av.open(str(path))
        try:
            astream = container.streams.audio[0]
        except (IndexError, KeyError):
            container.close()
            raise ValueError(f"{path} has no audio track")
        out_container = av.open(out, mode="w")
        out_stream = out_container.add_stream("pcm_s16le", rate=astream.rate)
        for frame in container.decode(audio=0):
            for packet in out_stream.encode(frame):
                out_container.mux(packet)
        for packet in out_stream.encode():
            out_container.mux(packet)
        out_container.close()
        container.close()
        return out


def montage(frame_paths: List[str], out: str = "storyboard.png", cols: int = 4,
            thumb_w: int = 320) -> str:
    """Build a contact-sheet / storyboard grid from frame images."""
    Image = _require("PIL.Image", "Pillow")
    if not frame_paths:
        raise ValueError("montage requires at least one frame path")
    thumbs = []
    for fp in frame_paths:
        im = Image.open(fp).convert("RGB")
        ratio = thumb_w / im.width
        thumbs.append(im.resize((thumb_w, max(1, int(im.height * ratio)))))
    thumb_h = max(t.height for t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * thumb_h), (16, 16, 16))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (c * thumb_w, r * thumb_h))
    sheet.save(out)
    return out
