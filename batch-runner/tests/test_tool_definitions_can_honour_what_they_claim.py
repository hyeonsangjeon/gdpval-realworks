"""A tool definition may not claim more than its schema can honour.

The first paid dispatch of the agentic v2 stage A probe, on 2026-09-10, was
refused with ``400`` before the model was asked. Nothing ran and nothing was
charged, and the record it produced said only ``BadRequestError``. The cause
was in the request, and it had been in the repository, unexercised, the whole
time: every tool was offered with ``strict: true``, and the schemas behind
several of them are outside the subset ``strict`` promises.

``strict`` is not a dial for how carefully arguments get checked. It is a
declaration that the schema fits a narrow subset the service will enforce on
the model's behalf, and the service validates that declaration when the
request arrives. An overclaim does not quietly degrade to ordinary validation
— it makes the entire call impossible, before any inference, in a way no unit
test that only reads the definitions back could notice.

So this module reads the definitions the way the service does. It takes the
part of the subset that is beyond argument, and asserts that nothing claims
``strict`` while breaking it:

* the root of a function's parameters is an object, so a ``oneOf`` or an
  ``anyOf`` at the root is out;
* ``oneOf`` does not appear anywhere;
* every object sets ``additionalProperties: false``;
* every property of every object is listed in that object's ``required``.

Both the v1 and the v2 tool sets are checked, because both build Responses
definitions and both reach a paid model. Only v2 is fixed here. The same
overclaim is in v1's ``run_ffmpeg``, but v1's tool JSON is hashed into
``V1_TOOLS_SHA256`` in ``test_agentic_v2_compatibility``, which pins v1 as the
fixed baseline that v2 is measured against — changing it is a decision about
that baseline and about every v1 result already recorded under it, not a
one-word fix to smuggle into a v2 change. So it is written down in
``KNOWN_OVERCLAIMS`` instead, where it is asserted to *still* be broken: the
day somebody fixes it this test fails and points at the frozen hash that has
to be re-cut in the same breath.

The schemas themselves are deliberately not narrowed to fit — they are the
real contract, and ``validate_tool_arguments`` and ``ToolDispatch`` enforce
them in full. What is dropped is only the promise that could not be kept.

If a schema is ever brought inside the subset and ``strict`` turned back on
for it, this test keeps passing and nothing else has to change. If one drifts
back out while still claiming it, this fails here, offline, for free.
"""

from __future__ import annotations

from typing import Any, Iterator

import pytest

from core.agentic_tools import responses_tool_definitions as v1_definitions
from core.agentic_v2_contract import responses_tool_definitions as v2_definitions

#: Combining keywords the strict subset does not accept anywhere in a schema.
FORBIDDEN_ANYWHERE = ("oneOf",)

#: Definitions that overclaim today, on purpose, with the reason each is not
#: simply fixed. Being listed here is not permission — it is a record that the
#: call would be refused, kept next to the reason it has not been repaired.
#: Each entry is asserted to still be broken, so removing the overclaim
#: without removing the entry fails this file and puts the frozen hash in
#: front of whoever did it.
KNOWN_OVERCLAIMS = {
    "v1:run_ffmpeg": (
        "v1's tool JSON is hashed into V1_TOOLS_SHA256 in "
        "test_agentic_v2_compatibility, which freezes v1 as the baseline v2 "
        "is compared against. Dropping strict here changes that identity and "
        "the identity of every v1 agentic result recorded under it, so it is "
        "a decision for the v1 baseline and not a side effect of a v2 fix. "
        "Until then an agentic_sandbox run that offers run_ffmpeg is refused "
        "with 400 before the model is asked."
    ),
}


def _objects_in(schema: Any, path: str = "") -> Iterator[tuple[str, dict]]:
    """Every subschema in ``schema``, with a readable path to each."""
    if not isinstance(schema, dict):
        return
    yield path or "<root>", schema
    for key in ("properties", "patternProperties", "$defs", "definitions"):
        for name, child in (schema.get(key) or {}).items():
            yield from _objects_in(child, f"{path}.{name}" if path else name)
    for key in ("oneOf", "anyOf", "allOf"):
        for index, child in enumerate(schema.get(key) or []):
            label = f"{key}[{index}]"
            yield from _objects_in(child, f"{path}.{label}" if path else label)
    for key in ("items", "not", "additionalProperties"):
        child = schema.get(key)
        if isinstance(child, dict):
            yield from _objects_in(child, f"{path}.{key}" if path else key)


def _breaks_the_strict_subset(schema: Any) -> list[str]:
    """Say every way ``schema`` falls outside the subset, or nothing."""
    faults: list[str] = []

    if not isinstance(schema, dict) or schema.get("type") != "object":
        faults.append("<root>: the parameters are not an object schema")

    for path, node in _objects_in(schema):
        for keyword in FORBIDDEN_ANYWHERE:
            if keyword in node:
                faults.append(f"{path}: {keyword} is not permitted")
        properties = node.get("properties")
        if not isinstance(properties, dict):
            continue
        if node.get("additionalProperties") is not False:
            faults.append(f"{path}: additionalProperties is not false")
        optional = sorted(set(properties) - set(node.get("required") or []))
        if optional:
            faults.append(f"{path}: not required: {', '.join(optional)}")

    return faults


def _every_definition() -> list[tuple[str, dict]]:
    return [
        (f"{label}:{definition['name']}", definition)
        for label, build in (("v1", v1_definitions), ("v2", v2_definitions))
        for definition in build()
    ]


@pytest.mark.parametrize(
    "label,definition", _every_definition(), ids=lambda value: value
)
def test_tool_definitions_can_honour_what_they_claim(label, definition):
    if not definition.get("strict"):
        assert label not in KNOWN_OVERCLAIMS, (
            f"{label} no longer overclaims, which is the fix — now remove its "
            f"entry from KNOWN_OVERCLAIMS. Read the entry first: "
            f"{KNOWN_OVERCLAIMS.get(label)}"
        )
        return

    faults = _breaks_the_strict_subset(definition.get("parameters"))

    if label in KNOWN_OVERCLAIMS:
        assert faults, (
            f"{label} is listed in KNOWN_OVERCLAIMS but its schema is now "
            f"inside the subset, so the claim is honest and the entry is "
            f"stale. Remove it."
        )
        return

    assert not faults, (
        f"{label} is offered with strict: true, but the service will refuse "
        f"the whole request before asking the model because "
        f"{'; '.join(faults)}. Either bring the schema inside the subset or "
        f"stop claiming strict for it."
    )


def test_the_guard_would_have_caught_the_dispatch_that_was_refused():
    """The check has to fail on what actually happened, or it proves nothing.

    This is the shape the v2 ``workspace_apply`` tool was offered in on
    2026-09-10 — the real schema, with the flag it really carried.
    """
    as_it_was = dict(
        next(item for item in v2_definitions() if item["name"] == "workspace_apply"),
        strict=True,
    )

    with pytest.raises(AssertionError) as refused:
        test_tool_definitions_can_honour_what_they_claim("v2:workspace_apply", as_it_was)

    assert "oneOf is not permitted" in str(refused.value)
    assert "not an object schema" in str(refused.value)


def test_a_schema_inside_the_subset_is_left_alone():
    """A definition that can honour the claim keeps it, and passes."""
    honest = {
        "type": "function",
        "name": "honest",
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    }

    test_tool_definitions_can_honour_what_they_claim("made-up:honest", honest)
