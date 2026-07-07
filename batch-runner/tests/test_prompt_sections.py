"""Unit tests for the spec-driven section engine (core/prompt_sections.py).

Complements the byte-identity goldens in test_sandbox_prompt_golden.py: those prove
the *default* output is unchanged; these prove the engine is actually spec-driven —
reordering/toggling entries changes the output and bad specs fail loudly.
"""

from types import SimpleNamespace

import pytest

from core.prompt_sections import (
    DEFAULT_SECTIONS,
    SectionContext,
    assemble_sections,
)


def _ctx(reflection=None, contract=None, ref_files=None):
    """Context with marker-returning fakes so section ordering is observable."""
    return SectionContext(
        task_prompt="TASK_BODY",
        ref_files=ref_files or [],
        skills=[],
        manifest=SimpleNamespace(to_prompt_hint=lambda: "DEPS_HINT"),
        contract=contract,
        reflection=reflection,
        registry=SimpleNamespace(render_manual=lambda skills: "SKILLS_MANUAL"),
    )


def test_default_order_matches_hardcoded_layout():
    ctx = _ctx(reflection="REFL", contract=SimpleNamespace(to_prompt_section=lambda: "CONTRACT"))
    out = assemble_sections(DEFAULT_SECTIONS, ctx)
    # file_structure/previews/available_files skip on empty ref_files.
    assert out == "REFL\n\nSKILLS_MANUAL\n\nDEPS_HINT\n\nCONTRACT\n\nTASK_BODY"


def test_reordering_entries_reorders_output():
    ctx = _ctx()
    assert assemble_sections(["task", "deps_hint"], ctx) == "TASK_BODY\n\nDEPS_HINT"
    assert assemble_sections(["deps_hint", "task"], ctx) == "DEPS_HINT\n\nTASK_BODY"


def test_unknown_section_id_raises():
    with pytest.raises(ValueError, match="unknown prompt section id"):
        assemble_sections(["task", "does_not_exist"], _ctx())


def test_enabled_false_drops_the_section():
    ctx = _ctx()
    out = assemble_sections([{"id": "deps_hint", "enabled": False}, {"id": "task"}], ctx)
    assert out == "TASK_BODY"


def test_dict_entry_requires_id():
    with pytest.raises(ValueError, match="missing 'id'"):
        assemble_sections([{"enabled": True}], _ctx())


def test_invalid_entry_type_raises():
    with pytest.raises(ValueError, match="invalid prompt section entry"):
        assemble_sections([123], _ctx())


def test_none_and_empty_blocks_are_omitted():
    # reflection/contract None + empty ref_files → only skills/deps/task survive.
    out = assemble_sections(DEFAULT_SECTIONS, _ctx())
    assert out == "SKILLS_MANUAL\n\nDEPS_HINT\n\nTASK_BODY"


def test_available_files_emits_basenames_only():
    ctx = _ctx(ref_files=["/abs/secret/dir/quarterly_ledger.csv"])
    out = assemble_sections(["available_files"], ctx)
    assert "quarterly_ledger.csv" in out
    assert "/abs/secret" not in out


def test_string_and_dict_entries_interoperate():
    ctx = _ctx()
    out = assemble_sections(["deps_hint", {"id": "task"}], ctx)
    assert out == "DEPS_HINT\n\nTASK_BODY"
