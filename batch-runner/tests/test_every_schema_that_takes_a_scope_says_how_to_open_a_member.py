"""A way in that only one of two schemas mentions is a way in by luck.

PR3 follow-up 4. A stage-1 gold answer -- five WAV stems inside one ``.zip`` --
scored 2 of 62 because thirty-four rubric items were answered "binary or
unsupported" about files nothing had opened. The member scope existed by then;
it was written down in exactly one place, a ``note`` returned by
``inspect_formatting`` on an archive. The re-run recovered 39.8 points because
the judge read that note and worked the rest out. PR3 recorded the outcome and
the caveat together: *"이번엔 채점기가 스스로 찾아냈으므로 결함 수정이 아니라
재현성 개선으로 다룬다"* -- it worked, but nothing made it work, and the run
that measures how much a judge's choices wobble is the next one.

The fix for that is to say it where the judge is looking, and the archive work
did say it -- in the structure listing, in the text read, and in the schema the
judge is handed. What it did not do is say it in the *other* schema. This file
holds ``scope`` twice: ``MODEL_READ_DELIVERABLE_TOOL_SCHEMA`` for the judge and
``READ_DELIVERABLE_TOOL_SCHEMA``, exported from ``core.tools`` and offered by
the CHANGELOG as "ready to drop into Responses API ``tools=[...]``". Only the
first carried the contract. A caller who took the CHANGELOG at its word got a
model that could reach every member and was told about none of them -- the
2-of-62 answer, reintroduced one export over.

So the tests here are not about a sentence being present. They are about there
being one statement rather than several: the schemas are found by shape, not by
name, so a third one added later is held to the same contract instead of
quietly becoming the next place it is missing.
"""

from __future__ import annotations

import ast
import importlib
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

from core.tool_calling_judge import ToolCallingJudge
from core.tools import (
    MODEL_READ_DELIVERABLE_TOOL_SCHEMA,
    READ_DELIVERABLE_TOOL_SCHEMA,
    read_deliverable,
)

read_deliverable_module = importlib.import_module("core.tools.read_deliverable")

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "grader_judge_v2.md"


def _tool_schemas_with_a_scope() -> List[Tuple[str, Dict[str, Any]]]:
    """Every tool schema in the module that takes a ``scope``, found by shape.

    By shape and not by name on purpose. Naming the two that exist today would
    make this file a list of the schemas someone remembered, which is the same
    failure one level up: the defect was a second description nobody thought to
    update, so the test has to find descriptions it was not told about.
    """
    found: List[Tuple[str, Dict[str, Any]]] = []
    for name, value in vars(read_deliverable_module).items():
        if not isinstance(value, dict) or value.get("type") != "function":
            continue
        properties = value.get("parameters", {}).get("properties", {})
        if "scope" in properties:
            found.append((name, value))
    return found


def _scope_description(schema: Dict[str, Any]) -> str:
    return schema["parameters"]["properties"]["scope"]["description"]


def _dict_value(node: ast.Dict, key: str) -> Optional[ast.expr]:
    for written_key, value in zip(node.keys, node.values):
        if isinstance(written_key, ast.Constant) and written_key.value == key:
            return value
    return None


def _scope_description_source(schema_name: str) -> ast.expr:
    """The expression the module *writes* to build one schema's description.

    Read from source rather than from the built dict because the two are not
    the same question. At runtime a hand-written copy of the contract and a
    reference to it are indistinguishable -- identical bytes -- and it is
    precisely the hand-written copy that drifted.
    """
    tree = ast.parse(
        Path(read_deliverable_module.__file__).read_text(encoding="utf-8")
    )
    for node in tree.body:
        targets = (
            [node.target]
            if isinstance(node, ast.AnnAssign)
            else node.targets
            if isinstance(node, ast.Assign)
            else []
        )
        if not any(
            isinstance(t, ast.Name) and t.id == schema_name for t in targets
        ):
            continue
        for candidate in ast.walk(node):
            if not isinstance(candidate, ast.Dict):
                continue
            scope = _dict_value(candidate, "scope")
            if isinstance(scope, ast.Dict):
                description = _dict_value(scope, "description")
                if description is not None:
                    return description
    raise AssertionError(f"no scope description found in the source of {schema_name}")


# ── 1. Every schema that takes a scope says how to use it on an archive ──


def test_both_schemas_are_found_by_shape():
    """The sweep has to actually reach the two that exist.

    A `_tool_schemas_with_a_scope` that silently matched nothing would make
    every other test in this file pass over an empty list.
    """
    names = {name for name, _ in _tool_schemas_with_a_scope()}

    assert names == {
        "READ_DELIVERABLE_TOOL_SCHEMA",
        "MODEL_READ_DELIVERABLE_TOOL_SCHEMA",
    }


def test_every_schema_that_takes_a_scope_states_the_member_contract():
    schemas = _tool_schemas_with_a_scope()
    assert schemas, "no tool schema with a scope was found"

    for name, schema in schemas:
        description = _scope_description(schema)
        assert "member" in description, f"{name} never mentions a member"
        assert ".zip" in description, f"{name} never says what a member is in"
        assert "probe_audio" in description and "read_content" in description, (
            f"{name} names no op to open a member with, so knowing the key "
            "exists does not tell the reader what to do with it"
        )


def test_the_contract_is_one_string_and_not_two_that_happen_to_agree():
    """Both descriptions must *contain the constant*, not merely say the same.

    Two hand-written sentences that agree today are the state this defect was
    in before the archive work -- they agree until one is edited.
    """
    contract = read_deliverable_module._SCOPE_MEMBER_CONTRACT

    for name, schema in _tool_schemas_with_a_scope():
        assert contract in _scope_description(schema), (
            f"{name} states the member scope in its own words; edit one and "
            "the other keeps the old contract"
        )


def test_the_source_builds_both_descriptions_from_the_constant():
    """The half of that claim a string comparison cannot make.

    The check above reads the built dict, where a description that references
    the constant and one that repeats its bytes are the same object. Paste the
    contract back into a schema by hand and it still passes -- which is the
    defect restored, waiting for the next edit to only reach one of them. So
    this one reads the source and asks for the *reference*.

    Neither check subsumes the other: this one is satisfied by a schema that
    mentions the name while shipping something else (a slice, a summary), and
    that one is satisfied by an exact copy. A schema needs both.
    """
    for name, _ in _tool_schemas_with_a_scope():
        expression = _scope_description_source(name)
        referenced = {
            node.id for node in ast.walk(expression) if isinstance(node, ast.Name)
        }
        assert "_SCOPE_MEMBER_CONTRACT" in referenced, (
            f"{name} spells the member contract out instead of referring to "
            "it; the copies agree only until someone edits one"
        )


def test_each_schema_keeps_its_own_lead_in():
    """Sharing the contract must not have flattened the two descriptions.

    They describe different tools -- the exported one still has to name the
    page and sheet scopes its six ops take.
    """
    exported = _scope_description(READ_DELIVERABLE_TOOL_SCHEMA)
    model = _scope_description(MODEL_READ_DELIVERABLE_TOOL_SCHEMA)

    assert "workbook_page" in exported and "page_start" in exported
    assert exported != model


# ── 2. The copy the judge is actually handed ─────────────────────────


def test_the_schema_the_judge_is_handed_still_carries_the_contract():
    """`_build_tools_for` deep-copies the schema and rewrites the op enum.

    The description is what the judge reads; a copy step that dropped or
    rewrote it would leave the constant correct and the prompt wrong.
    """
    judge = ToolCallingJudge(
        client=None,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_PATH.read_text(encoding="utf-8"),
    )

    for modality in ("text", "visual", "audio"):
        tools = judge._build_tools_for(modality)
        read_tool = next(t for t in tools if t["name"] == "read_deliverable")
        description = read_tool["parameters"]["properties"]["scope"]["description"]

        assert read_deliverable_module._SCOPE_MEMBER_CONTRACT in description, (
            f"the {modality} judge is handed a scope description without the "
            "member contract"
        )


def test_the_ops_the_contract_names_are_ops_the_judge_may_call():
    """Naming an op the model cannot call is advice it cannot take."""
    judge = ToolCallingJudge(
        client=None,
        model="gpt-5.4-mini",
        prompt_template=PROMPT_PATH.read_text(encoding="utf-8"),
    )
    tools = judge._build_tools_for("audio")
    read_tool = next(t for t in tools if t["name"] == "read_deliverable")
    allowed = set(read_tool["parameters"]["properties"]["op"]["enum"])

    contract = read_deliverable_module._SCOPE_MEMBER_CONTRACT
    for op in ("probe_audio", "read_content"):
        assert op in contract
        assert op in allowed, f"the contract points at {op}, which is not offered"


# ── 3. The runtime half says the same thing ──────────────────────────


@pytest.fixture
def archive(tmp_path: Path) -> Path:
    p = tmp_path / "STEMS.zip"
    with zipfile.ZipFile(p, "w") as writing:
        writing.writestr("STEMS/MASTER.wav", b"RIFF\x00\x00\x00\x00WAVEfmt ")
        writing.writestr("STEMS/notes.txt", "mixed at 48k, 24-bit\n")
    return p


def test_the_listing_and_the_text_agree_with_the_schemas(tmp_path, archive):
    """Three surfaces, one fact.

    The runtime hint is worded for a line inside a listing rather than for a
    parameter description, so it is not the same string -- but it has to name
    the same key and the same ops, or a judge that read one and then the other
    has been told two different things.
    """
    hint = read_deliverable_module._ZIP_MEMBER_HINT
    contract = read_deliverable_module._SCOPE_MEMBER_CONTRACT

    structure = read_deliverable(
        "inspect_structure", archive.name, base_dir=str(tmp_path)
    )
    content = read_deliverable("read_content", archive.name, base_dir=str(tmp_path))

    assert hint in structure["data"]["note"]
    assert hint in content["data"]["text"]

    for token in ("member", "probe_audio", "read_content"):
        assert token in hint, f"the runtime hint drops {token}"
        assert token in contract, f"the schema contract drops {token}"


def test_the_listing_comes_before_the_way_to_open_it(tmp_path, archive):
    """The hint is added to the listing, never in place of it.

    "Does it contain a Bass stem in WAV format" is answerable from names alone,
    and a judge that never learns the member scope still has to be able to
    answer it.
    """
    text = read_deliverable("read_content", archive.name, base_dir=str(tmp_path))[
        "data"
    ]["text"]

    assert "STEMS/MASTER.wav" in text
    assert text.index("STEMS/MASTER.wav") < text.index(
        read_deliverable_module._ZIP_MEMBER_HINT
    )
