"""Tests for core/skills_registry.py"""

from pathlib import Path

import pytest

from core.skills_registry import (
    Skill,
    SkillsRegistry,
    _extract_api_section,
    _parse_front_matter,
)


@pytest.fixture(scope="module")
def registry():
    return SkillsRegistry()


def test_discovers_builtin_skills(registry):
    """The five shipped skills should be discovered from batch-runner/skills."""
    names = set(registry.skills.keys())
    for expected in {"audio", "video", "document", "image", "data"}:
        assert expected in names, f"missing skill: {expected}"


def test_each_skill_has_metadata_and_api(registry):
    for name, skill in registry.skills.items():
        assert skill.title, f"{name} missing title"
        assert skill.file_extensions or skill.keywords, f"{name} has no triggers"
        # Toolkit API section is what gets injected into the prompt.
        assert skill.api, f"{name} missing '## Toolkit API' section"


def test_parse_front_matter_roundtrip():
    text = (
        "---\n"
        "name: demo\n"
        "title: Demo Skill\n"
        "file_extensions: [.foo]\n"
        "---\n"
        "# Body\n## Toolkit API\nfoo()\n"
    )
    meta, body = _parse_front_matter(text)
    assert meta["name"] == "demo"
    assert meta["file_extensions"] == [".foo"]
    assert body.startswith("# Body")
    assert _extract_api_section(body).startswith("## Toolkit API")


def test_select_by_extension_video(registry):
    selected = registry.select(reference_files=["/data/clip.mp4"], task_text="")
    names = [s.name for s in selected]
    assert "video" in names
    top = selected[0]
    assert ".mp4" in top.matched_extensions
    assert top.score >= 10  # one extension match = _EXT_WEIGHT


def test_select_by_extension_audio(registry):
    selected = registry.select(reference_files=["/data/track.wav"], task_text="")
    assert "audio" in [s.name for s in selected]


def test_select_by_keyword_only(registry):
    selected = registry.select(reference_files=[], task_text="please draw a spectrogram")
    assert "audio" in [s.name for s in selected]
    audio = next(s for s in selected if s.name == "audio")
    assert "spectrogram" in audio.matched_keywords


def test_select_empty_returns_nothing(registry):
    assert registry.select(reference_files=[], task_text="hello world") == []


def test_select_respects_max_skills(registry):
    selected = registry.select(
        reference_files=["/a.mp4", "/b.wav", "/c.pdf", "/d.png", "/e.csv"],
        task_text="spectrogram regression ocr chart map",
        max_skills=2,
    )
    assert len(selected) <= 2


def test_select_orders_by_score(registry):
    # Two video files + a video keyword should outrank a single pdf.
    selected = registry.select(
        reference_files=["/a.mp4", "/b.mov", "/c.pdf"],
        task_text="keyframe storyboard",
    )
    assert selected[0].name == "video"
    scores = [s.score for s in selected]
    assert scores == sorted(scores, reverse=True)


def test_render_manual_contains_api(registry):
    selected = registry.select(reference_files=["/data/clip.mp4"], task_text="")
    manual = registry.render_manual(selected)
    assert "AVAILABLE SKILLS" in manual
    assert "from skills import" in manual
    assert "Toolkit API" in manual


def test_render_manual_empty():
    assert SkillsRegistry().render_manual([]) == ""


def test_render_manual_truncates(registry):
    selected = registry.select(reference_files=["/data/clip.mp4"], task_text="")
    manual = registry.render_manual(selected, max_chars=50)
    assert len(manual) <= 80  # 50 + truncation marker
    assert "truncated" in manual


def test_all_required_packages(registry):
    pkgs = registry.all_required_packages()
    assert isinstance(pkgs, list)
    # de-duplicated
    assert len(pkgs) == len(set(pkgs))


def test_missing_skills_dir_is_safe(tmp_path):
    reg = SkillsRegistry(skills_dir=tmp_path / "does_not_exist")
    assert reg.skills == {}
    assert reg.select(["/a.mp4"], "spectrogram") == []
