"""Tests for the v2 tool-aware judge prompt (PR2 task 202)."""

from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def test_v2_prompt_exists_and_has_version_tag():
    text = _read("grader_judge_v2.md")
    assert "prompt_version: v2.2" in text


def test_v2_prompt_lists_only_model_callable_ops():
    text = _read("grader_judge_v2.md")
    for op in ("inspect_structure", "read_content", "inspect_formatting",
               "probe_audio", "probe_video"):
        assert op in text, f"op {op} missing from v2 prompt"
    assert "| `render_to_image` |" not in text


def test_v2_prompt_describes_harness_owned_trusted_visual_evidence():
    text = _read("grader_judge_v2.md")
    assert "TRUSTED_VISUAL_EVIDENCE_BEGIN" in text
    assert "TRUSTED_VISUAL_EVIDENCE_END" in text
    assert "harness-owned" in text
    assert "never receive" in text.lower()
    assert "image bytes" in text.lower()


def test_v2_prompt_drops_inline_extract_block():
    """v2 must NOT contain the v1 'extracted_content_or_summary_truncated_4000'
    handlebars placeholder — that's the pre-extraction the rebuild deletes."""
    text = _read("grader_judge_v2.md")
    assert "extracted_content_or_summary_truncated" not in text
    assert "deliverable_extract_max_chars" not in text


def test_v2_prompt_demands_tool_grounded_evidence():
    text = _read("grader_judge_v2.md")
    # Must mention that evidence has to come from a tool response, not
    # from fabricated content.
    assert "Grounded evidence" in text
    assert "trusted visual evidence" in text.lower()


def test_v2_prompt_has_routing_hint_placeholders():
    text = _read("grader_judge_v2.md")
    assert "{{routing_modality}}" in text
    assert "{{routing_preferred_op}}" in text


def test_v2_prompt_includes_tool_calls_made_in_schema():
    text = _read("grader_judge_v2.md")
    assert '"tool_calls_made"' in text


def test_v1_archive_preserved():
    text = _read("grader_judge_v1_archive.md")
    assert "prompt_version: v1" in text
    # Sanity: the archive really is the v1 prompt, not the v2.
    assert "extracted_content_or_summary_truncated" in text


def test_v1_active_unchanged():
    """While PR2 is in progress, grader_judge.md MUST still be the v1
    prompt so the existing Judge class keeps producing identical grades
    for legacy configs. Task 207 will swap it for v2."""
    text = _read("grader_judge.md")
    assert "prompt_version: v1" in text
