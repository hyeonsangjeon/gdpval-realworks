"""Video Analyzer — vision preprocessor for the multi-agent pipeline.

This is the *seeing* counterpart of :mod:`core.audio_analyzer`. It gives the
solving pipeline **vision** for video reference files:

1. Sample keyframes from each video frame-by-frame (evenly spaced across the
   timeline) using OpenCV (``cv2``) or PyAV (``av``) — whichever is available.
2. Send the frames (as base64 JPEG images) together with per-video metadata and
   the task instruction to a vision-capable model.
3. Return a task-aware JSON analysis that is injected into the prompt *before*
   the main executor runs, so the code-generating model can "watch" the video
   instead of coding blind.

Like the audio analyzer, every failure path is **non-fatal**: if no frame
backend is installed, a file can't be decoded, or the API call errors, the
function returns ``""`` and the main pipeline proceeds unaffected.

Usage (called by step2_run_inference._run_preprocessors):

    from core.video_analyzer import analyze_video_files, filter_video_files

    result = analyze_video_files(
        client=azure_client,
        model_deployment="gpt-5.2",
        system_prompt="You are a video analysis agent...",
        video_paths=["/data/ref/clip.mp4"],
        task_instruction="Summarize the on-screen actions...",
    )
    # result: "[VIDEO ANALYSIS]\n{...json...}\n[/VIDEO ANALYSIS]"
"""

from __future__ import annotations

import base64
import io
import json
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v",
    ".mpeg", ".mpg", ".wmv", ".flv", ".3gp", ".ogv",
}

# Sampling / payload defaults (overridable via preprocessor YAML).
DEFAULT_FRAMES_PER_VIDEO = 8
DEFAULT_MAX_TOTAL_FRAMES = 24
DEFAULT_FRAME_MAX_WIDTH = 768   # px; keeps vision token cost reasonable
DEFAULT_FRAME_DETAIL = "auto"   # "low" | "high" | "auto"
JPEG_QUALITY = 80


# ── modality filter ─────────────────────────────────────────────────────────

def filter_video_files(file_paths: List[str] | None) -> List[str]:
    """Return only paths whose extension is a known video format."""
    if not file_paths:
        return []
    return [p for p in file_paths if Path(p).suffix.lower() in VIDEO_EXTENSIONS]


# ── frame-extraction backends (lazy, optional) ──────────────────────────────

def _select_backend() -> Optional[str]:
    """Return an available frame-extraction backend name, or None."""
    try:
        import cv2  # noqa: F401
        return "cv2"
    except Exception:
        pass
    try:
        import av  # noqa: F401
        return "av"
    except Exception:
        pass
    return None


def _encode_jpeg_from_bgr(frame, max_width: int) -> Optional[bytes]:
    """Resize a cv2 BGR frame and JPEG-encode it. Returns bytes or None."""
    import cv2

    h, w = frame.shape[:2]
    if w > max_width:
        new_h = int(h * (max_width / float(w)))
        frame = cv2.resize(frame, (max_width, new_h), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        return None
    return buf.tobytes()


def _extract_frames_cv2(
    video_path: str, max_frames: int, max_width: int
) -> Tuple[dict, List[Tuple[float, bytes]]]:
    """Extract evenly spaced keyframes with OpenCV."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {}, []
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = (frame_count / fps) if fps else 0.0

        info = {
            "fps": round(fps, 3),
            "frame_count": frame_count,
            "duration_sec": round(duration, 3),
            "resolution": f"{width}x{height}" if width and height else None,
        }

        if frame_count <= 0:
            # Fall back to sequential read when frame count is unknown.
            frames = _sequential_read_cv2(cap, max_frames, max_width, fps)
            return info, frames

        n = min(max_frames, frame_count)
        if n <= 0:
            return info, []
        indices = [int(round(i * (frame_count - 1) / max(n - 1, 1))) for i in range(n)]

        frames: List[Tuple[float, bytes]] = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            jpeg = _encode_jpeg_from_bgr(frame, max_width)
            if jpeg is None:
                continue
            ts = (idx / fps) if fps else 0.0
            frames.append((round(ts, 3), jpeg))
        return info, frames
    finally:
        cap.release()


def _sequential_read_cv2(cap, max_frames, max_width, fps) -> List[Tuple[float, bytes]]:
    """Sample frames by stepping through the stream (unknown frame count)."""
    import cv2

    frames: List[Tuple[float, bytes]] = []
    step = 30  # grab roughly 1 frame/sec at 30fps
    i = 0
    while len(frames) < max_frames:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        if i % step == 0:
            jpeg = _encode_jpeg_from_bgr(frame, max_width)
            if jpeg is not None:
                ts = (i / fps) if fps else 0.0
                frames.append((round(ts, 3), jpeg))
        i += 1
    return frames


def _extract_frames_av(
    video_path: str, max_frames: int, max_width: int
) -> Tuple[dict, List[Tuple[float, bytes]]]:
    """Extract evenly spaced keyframes with PyAV (+ Pillow for JPEG encode)."""
    import av

    container = av.open(video_path)
    try:
        stream = container.streams.video[0]
        time_base = stream.time_base
        fps = float(stream.average_rate) if stream.average_rate else 0.0
        frame_count = stream.frames or 0
        duration = 0.0
        if stream.duration and time_base:
            duration = float(stream.duration * time_base)
        elif container.duration:
            duration = container.duration / 1_000_000.0

        info = {
            "fps": round(fps, 3),
            "frame_count": frame_count,
            "duration_sec": round(duration, 3),
            "resolution": (
                f"{stream.codec_context.width}x{stream.codec_context.height}"
                if stream.codec_context.width else None
            ),
        }

        target_times = _target_times(duration, max_frames)
        frames: List[Tuple[float, bytes]] = []

        if target_times and duration > 0:
            for t in target_times:
                try:
                    container.seek(int(t / time_base), stream=stream)
                except Exception:
                    pass
                grabbed = False
                for frame in container.decode(video=0):
                    jpeg = _av_frame_to_jpeg(frame, max_width)
                    if jpeg is not None:
                        ts = float(frame.pts * time_base) if frame.pts is not None else t
                        frames.append((round(ts, 3), jpeg))
                        grabbed = True
                    break
                if len(frames) >= max_frames:
                    break
        else:
            # No duration → decode sequentially, sample every Nth frame.
            step = max(1, (frame_count // max_frames) if frame_count else 30)
            for i, frame in enumerate(container.decode(video=0)):
                if i % step == 0:
                    jpeg = _av_frame_to_jpeg(frame, max_width)
                    if jpeg is not None:
                        ts = float(frame.pts * time_base) if frame.pts is not None else 0.0
                        frames.append((round(ts, 3), jpeg))
                if len(frames) >= max_frames:
                    break

        return info, frames
    finally:
        container.close()


def _av_frame_to_jpeg(frame, max_width: int) -> Optional[bytes]:
    """Convert a PyAV video frame to resized JPEG bytes via Pillow."""
    try:
        img = frame.to_image()  # PIL.Image
    except Exception:
        return None
    if img.width > max_width:
        new_h = int(img.height * (max_width / float(img.width)))
        img = img.resize((max_width, new_h))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _target_times(duration: float, max_frames: int) -> List[float]:
    """Evenly spaced timestamps across the clip (excludes exact end)."""
    if duration <= 0 or max_frames <= 0:
        return []
    if max_frames == 1:
        return [duration / 2.0]
    return [i * duration / max_frames for i in range(max_frames)]


def extract_keyframes(
    video_path: str,
    max_frames: int = DEFAULT_FRAMES_PER_VIDEO,
    max_width: int = DEFAULT_FRAME_MAX_WIDTH,
) -> Tuple[dict, List[Tuple[float, bytes]]]:
    """Extract up to ``max_frames`` keyframes; returns (info, [(ts, jpeg)...]).

    Returns ({}, []) when no backend is available or the file can't be read.
    """
    backend = _select_backend()
    if backend is None:
        return {}, []
    try:
        if backend == "cv2":
            return _extract_frames_cv2(video_path, max_frames, max_width)
        return _extract_frames_av(video_path, max_frames, max_width)
    except Exception as exc:  # pragma: no cover - backend-specific
        print(f"      ⚠️  Video preprocessor: frame extraction failed for "
              f"{Path(video_path).name}: {exc}")
        return {}, []


# ── analysis API ────────────────────────────────────────────────────────────

def _analyze_one(
    client,
    model_deployment: str,
    system_prompt: str,
    video_path: str,
    task_instruction: Optional[str],
    frames_per_video: int,
    frame_max_width: int,
    frame_detail: str,
    max_completion_tokens: int,
) -> Tuple[str, object]:
    """Analyze a single video; returns (filename, parsed_json_or_text|None)."""
    filename = Path(video_path).name
    info, frames = extract_keyframes(video_path, frames_per_video, frame_max_width)
    if not frames:
        print(f"      ⚠️  Video preprocessor: no frames extracted from {filename}")
        return filename, None

    print(f"      🎬 Video preprocessor: {filename} → {len(frames)} frames "
          f"({info.get('duration_sec', '?')}s, {info.get('resolution', '?')})")

    text_content = system_prompt
    if task_instruction:
        text_content += f"\n\n[TASK]\n{task_instruction}\n[/TASK]"
    text_content += (
        f"\n\n[VIDEO METADATA]\nfile: {filename}\n"
        f"duration_sec: {info.get('duration_sec')}\n"
        f"fps: {info.get('fps')}\nframe_count: {info.get('frame_count')}\n"
        f"resolution: {info.get('resolution')}\n"
        f"sampled_frames: {len(frames)} (timestamps in seconds shown per image)\n"
        f"[/VIDEO METADATA]"
    )

    content_parts: list[dict] = [{"type": "text", "text": text_content}]
    for ts, jpeg in frames:
        content_parts.append({"type": "text", "text": f"frame @ {ts}s:"})
        b64 = base64.b64encode(jpeg).decode("utf-8")
        content_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": frame_detail,
            },
        })

    messages = [{"role": "user", "content": content_parts}]
    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model_deployment,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        )
        latency_ms = (time.time() - start) * 1000
        raw = response.choices[0].message.content or ""
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        usage = getattr(response, "usage", None)
        if usage is not None:
            print(f"      🎬 Video analysis complete: {latency_ms:.0f}ms "
                  f"(prompt={usage.prompt_tokens}, completion={usage.completion_tokens})")
        else:
            print(f"      🎬 Video analysis complete: {latency_ms:.0f}ms")

        raw = raw.strip()
        if not raw:
            return filename, None
        try:
            return filename, json.loads(raw)
        except json.JSONDecodeError:
            return filename, raw
    except Exception as exc:
        print(f"      ⚠️  Video preprocessor API error (non-fatal): {exc}")
        return filename, None


def analyze_video_files(
    client,
    model_deployment: str,
    system_prompt: str,
    video_paths: List[str],
    task_instruction: Optional[str] = None,
    max_completion_tokens: int = 4096,
    frames_per_video: int = DEFAULT_FRAMES_PER_VIDEO,
    max_total_frames: int = DEFAULT_MAX_TOTAL_FRAMES,
    frame_max_width: int = DEFAULT_FRAME_MAX_WIDTH,
    frame_detail: str = DEFAULT_FRAME_DETAIL,
) -> str:
    """Sample keyframes from video files and send them to a vision model.

    Args:
        client:            AzureOpenAI (or OpenAI) client instance.
        model_deployment:  Vision-capable deployment name (e.g. "gpt-5.2").
        system_prompt:     System prompt from YAML preprocessor config.
        video_paths:       Absolute paths to video files.
        task_instruction:  Task prompt (injected when include_task_instruction=true).
        max_completion_tokens: Max tokens for the analysis response.
        frames_per_video:  Keyframes to sample per video.
        max_total_frames:  Global cap across all videos (rebalances per-video count).
        frame_max_width:   Max frame width in px before JPEG encoding.
        frame_detail:      Vision ``detail`` hint ("low" | "high" | "auto").

    Returns:
        "[VIDEO ANALYSIS]\\n<json>\\n[/VIDEO ANALYSIS]" on success,
        empty string on any failure (must not block main execution).
    """
    if not video_paths:
        return ""

    if _select_backend() is None:
        print("      ⚠️  Video preprocessor: no frame backend (cv2/av) installed — skipping")
        return ""

    # Rebalance per-video frame budget so the total stays within max_total_frames.
    n_videos = len(video_paths)
    per_video = max(1, min(frames_per_video, max_total_frames // n_videos)) if n_videos else frames_per_video

    analyses: dict = {}
    for video_path in video_paths:
        if not os.path.exists(video_path):
            print(f"      ⚠️  Video preprocessor: missing file {video_path}")
            continue
        filename, parsed = _analyze_one(
            client=client,
            model_deployment=model_deployment,
            system_prompt=system_prompt,
            video_path=video_path,
            task_instruction=task_instruction,
            frames_per_video=per_video,
            frame_max_width=frame_max_width,
            frame_detail=frame_detail,
            max_completion_tokens=max_completion_tokens,
        )
        if parsed is not None:
            analyses[filename] = parsed

    if not analyses:
        return ""

    # Single video → emit its analysis directly; multiple → keyed by filename.
    if len(analyses) == 1:
        only = next(iter(analyses.values()))
        body = json.dumps(only, indent=2, ensure_ascii=False) if not isinstance(only, str) else only
    else:
        body = json.dumps(analyses, indent=2, ensure_ascii=False)

    return f"[VIDEO ANALYSIS]\n{body}\n[/VIDEO ANALYSIS]"
