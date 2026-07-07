---
name: video
title: Video Perception (frame-by-frame vision)
description: >-
  Vision for the sandbox. Use for any task with video reference files
  (.mp4/.mov/.avi/.mkv/.webm/.m4v) or that asks to watch, summarize, caption,
  storyboard, extract clips/frames, or analyze footage. Reads video
  frame-by-frame: metadata (fps/resolution/duration), uniform keyframe
  sampling, per-second frame extraction, scene-change detection, audio-track
  extraction, and contact-sheet montage rendering.
modalities: [video]
file_extensions: [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".mpg", ".mpeg"]
keywords:
  [video, footage, clip, movie, film, frame, frames, frame-by-frame, keyframe,
   scene, shot, storyboard, caption, subtitle, fps, resolution, timeline,
   montage, thumbnail, screencast, recording]
requires: [opencv-python, av, moviepy, numpy, Pillow]
version: 1.0.0
---

# Video Skill — give the sandbox *eyes*

Use this skill whenever the task involves watching or producing video. The
helpers wrap **opencv-python** (cv2), **PyAV**, **moviepy**, and **Pillow** so
you can look at footage *frame by frame* instead of guessing.

A typical "video problem" workflow:

1. `info = video.video_info(path)` — fps, frame count, duration, resolution.
2. `frames = video.keyframes(path, max_frames=8)` — evenly spaced stills to
   "see" the whole clip.
3. (optional) `cuts = video.scene_changes(path)` — where the content jumps.
4. (optional) `video.extract_audio(path, "audio.wav")` then use the `audio` skill.
5. Build the deliverable (storyboard PNG via `montage`, captions, summary doc).

## Toolkit API

```python
from skills import video

video.video_info(path) -> dict
    # {fps, frame_count, duration_sec, width, height, codec}

video.extract_frames(path, every_sec=1.0, out_dir="frames", limit=None) -> list[str]
    # save one frame per `every_sec`; returns saved PNG paths

video.keyframes(path, max_frames=8, out_dir="keyframes") -> list[str]
    # uniformly sample `max_frames` stills across the whole clip

video.frame_at(path, t_sec, out=None) -> str
    # extract a single frame at timestamp t_sec

video.scene_changes(path, threshold=0.45, max_samples=300) -> list[float]
    # timestamps (sec) where consecutive frames differ strongly (HSV histogram)

video.extract_audio(path, out="audio.wav") -> str
    # pull the audio track to WAV (then feed it to the `audio` skill)

video.montage(frame_paths, out="storyboard.png", cols=4, thumb_w=320) -> str
    # contact-sheet / storyboard grid from frame images
```

Notes:
- Frame extraction uses cv2 when available and falls back to PyAV.
- `keyframes` is the cheapest way to perceive a clip; prefer it before dense
  per-second extraction on long videos.
