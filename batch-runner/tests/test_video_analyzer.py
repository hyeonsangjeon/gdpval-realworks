"""Tests for core/video_analyzer.py

No real video decoding is required: frame extraction is patched so the tests
run without cv2/av installed.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

import core.video_analyzer as va
from core.video_analyzer import (
    analyze_video_files,
    filter_video_files,
    _target_times,
)


# ── filter ───────────────────────────────────────────────────────────────

def test_filter_video_files():
    files = ["/a.mp4", "/b.MOV", "/c.txt", "/d.wav", "/e.webm"]
    out = filter_video_files(files)
    assert out == ["/a.mp4", "/b.MOV", "/e.webm"]


def test_filter_video_files_empty():
    assert filter_video_files(None) == []
    assert filter_video_files([]) == []


# ── target times ─────────────────────────────────────────────────────────

def test_target_times_even_spacing():
    ts = _target_times(10.0, 5)
    assert len(ts) == 5
    assert ts[0] == 0.0
    assert all(0 <= t < 10.0 for t in ts)
    assert ts == sorted(ts)


def test_target_times_single_frame_midpoint():
    assert _target_times(10.0, 1) == [5.0]


def test_target_times_zero_duration():
    assert _target_times(0.0, 5) == []


# ── analyze with no backend ──────────────────────────────────────────────

def test_analyze_no_backend_returns_empty():
    with patch.object(va, "_select_backend", return_value=None):
        out = analyze_video_files(
            client=object(),
            model_deployment="m",
            system_prompt="sys",
            video_paths=["/x.mp4"],
        )
    assert out == ""


def test_analyze_empty_paths():
    assert analyze_video_files(object(), "m", "sys", []) == ""


# ── analyze with patched frame extraction + fake vision client ───────────

class _FakeVisionClient:
    """Mimics client.chat.completions.create returning JSON content."""

    def __init__(self, content):
        self._content = content
        self.calls = []

        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                msg = SimpleNamespace(content=outer._content)
                choice = SimpleNamespace(message=msg)
                usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)
                return SimpleNamespace(choices=[choice], usage=usage)

        self.chat = SimpleNamespace(completions=_Completions())


def _fake_frames(*_args, **_kwargs):
    info = {"fps": 30.0, "frame_count": 300, "duration_sec": 10.0, "resolution": "640x480"}
    frames = [(0.0, b"\xff\xd8jpeg0"), (5.0, b"\xff\xd8jpeg1")]
    return info, frames


def test_analyze_single_video_json(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    client = _FakeVisionClient('{"summary": "a person waves", "scenes": 2}')
    with patch.object(va, "_select_backend", return_value="cv2"), \
         patch.object(va, "extract_keyframes", _fake_frames):
        out = analyze_video_files(
            client=client,
            model_deployment="gpt-5.4",
            system_prompt="You are a video agent",
            video_paths=[str(clip)],
            task_instruction="describe it",
        )
    assert out.startswith("[VIDEO ANALYSIS]")
    assert out.endswith("[/VIDEO ANALYSIS]")
    assert "a person waves" in out
    # One API call, and the payload carried image_url parts for the 2 frames.
    assert len(client.calls) == 1
    content = client.calls[0]["messages"][0]["content"]
    image_parts = [p for p in content if p.get("type") == "image_url"]
    assert len(image_parts) == 2
    assert image_parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_analyze_strips_markdown_fence(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    client = _FakeVisionClient('```json\n{"k": 1}\n```')
    with patch.object(va, "_select_backend", return_value="cv2"), \
         patch.object(va, "extract_keyframes", _fake_frames):
        out = analyze_video_files(client, "m", "sys", [str(clip)])
    assert '"k": 1' in out
    assert "```" not in out


def test_analyze_multiple_videos_keyed_by_filename(tmp_path):
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mov"
    a.write_bytes(b"fake")
    b.write_bytes(b"fake")
    client = _FakeVisionClient('{"ok": true}')
    with patch.object(va, "_select_backend", return_value="cv2"), \
         patch.object(va, "extract_keyframes", _fake_frames):
        out = analyze_video_files(client, "m", "sys", [str(a), str(b)])
    assert "a.mp4" in out
    assert "b.mov" in out


def test_analyze_api_error_is_non_fatal(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")

    class _Boom:
        def __init__(self):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=self._raise
                )
            )

        def _raise(self, **kwargs):
            raise RuntimeError("api down")

    with patch.object(va, "_select_backend", return_value="cv2"), \
         patch.object(va, "extract_keyframes", _fake_frames):
        out = analyze_video_files(_Boom(), "m", "sys", [str(clip)])
    assert out == ""


def test_analyze_no_frames_extracted(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"fake")
    client = _FakeVisionClient('{"x": 1}')
    with patch.object(va, "_select_backend", return_value="cv2"), \
         patch.object(va, "extract_keyframes", lambda *a, **k: ({}, [])):
        out = analyze_video_files(client, "m", "sys", [str(clip)])
    assert out == ""


# ── public host-backend probe (PR #57 preflight) ────────────────────────

def test_frame_backend_available_aliases_select_backend():
    from core.video_analyzer import frame_backend_available
    # Mirrors _select_backend exactly (may be None when cv2/av absent).
    with patch.object(va, "_select_backend", return_value="cv2"):
        assert frame_backend_available() == "cv2"
    with patch.object(va, "_select_backend", return_value="av"):
        assert frame_backend_available() == "av"
    with patch.object(va, "_select_backend", return_value=None):
        assert frame_backend_available() is None


def test_frame_backend_available_real_returns_str_or_none():
    from core.video_analyzer import frame_backend_available
    assert frame_backend_available() in (None, "cv2", "av")
