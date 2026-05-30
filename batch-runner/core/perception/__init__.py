"""Perception sub-judges for the v2 tool-calling grader.

Two thin wrappers around Azure OpenAI Responses API:

  - ``VisionPerception``  (task 205) — gpt-5.4 vision input, used when
    the routing classifier marks a rubric item as ``VISUAL``.
  - ``AudioPerception``   (task 206) — gpt-audio-1.5, used when the
    routing classifier marks a rubric item as ``AUDIO``.

Both classes accept an injected ``client`` so unit tests can pass a
fake. Both enforce per-task call caps to bound cost (SPEC §4.3 and
§9: vision/audio escalation must stay narrow).
"""

from .vision import VisionPerception, VisionVerdict, VISION_CALL_CAP
from .audio import AudioPerception, AudioVerdict, AUDIO_CALL_CAP

__all__ = [
    "VisionPerception",
    "VisionVerdict",
    "VISION_CALL_CAP",
    "AudioPerception",
    "AudioVerdict",
    "AUDIO_CALL_CAP",
]
