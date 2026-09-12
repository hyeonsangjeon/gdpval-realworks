"""`browser_run` is half open, and the half that is shut ends the run.

The stage one instructions name three tools that refuse -- `exec_run`,
`environment_resolve`, `environment_activate` -- and an earlier draft named
`browser_run` alongside them. That draft was corrected after a probe showed
`browser_run` answering ``ok: True``, and the correction is recorded in
`test_agentic_stage_one_budget.py` as *"telling a model a working tool is shut
costs it the tool"*.

The probe was right about the call it made and wrong about the tool. The
contract gives `browser_run` five operations across three argument shapes. The
fixture backend serves the three that take a `path` and refuses the two that
reach the network, so a probe that passes a `path` sees a working tool and a
model that passes a `query` does not.

What that cost is measured. In trial_30 (run 34671538199, 2026-09-12) the
thirty tasks made **zero** calls to the three tools the instructions name --
the model obeyed exactly -- and twelve of them ended on a single `browser_run`
that reached the network: eight a `search`, four an `open_url`. Each had used
2-5 of the 9 calls it was allowed, and none was retried. The runner ends a task
on any tool result that is not ``ok: True``, so a refusal here is terminal
rather than something to work around.

The half that is open here is shut on the backend this is all waiting for.
``AgenticV2MicroVMBackend.browser_run`` refuses every operation including
``open_local``, for a stated reason -- nothing drives chromium or bounds it --
and ``test_agentic_v2_microvm_backend.py`` pins that. So the shape below is the
fixture's, not the destination's, and a task that leans on a local browser read
is failing later rather than not at all.

This file pins both halves so the next probe cannot see only one. It asserts
what the backend does and says nothing about what the instructions should say:
the instruction text is a pinned run condition, and changing it is an
intervention that needs its own record. See
`tasks/0822_saturday/TURN_LIMIT_COMPARISON_DESIGN.md`.
"""
from __future__ import annotations

import pytest

from core.agentic_v2_contract import (
    TOOL_SCHEMAS,
    AgenticV2Profile,
    validate_tool_arguments,
)
from core.agentic_v2_provenance import foundation_fixture_identity
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend

#: The operations the fixture backend serves, and the argument each one takes.
SERVED = ("open_local", "snapshot", "screenshot")

#: The operations it refuses. Both reach outside the workspace.
REFUSED = (("search", "query", "quarterly revenue by segment"),
           ("open_url", "url", "https://example.org/a"))


@pytest.fixture
def backend(tmp_path):
    made = AgenticV2FixtureBackend(
        root=tmp_path / "task",
        profile=AgenticV2Profile(
            tool_contract_version="2.0",
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
    )
    # The backend reads relative to `root/work`, which it creates itself, so
    # the file has to be laid down after it is built rather than before.
    inputs = made.work / "inputs"
    inputs.mkdir()
    (inputs / "notes.md").write_text("a local file\n", encoding="utf-8")
    return made


@pytest.mark.parametrize("operation", SERVED)
def test_the_operations_that_take_a_path_are_served(backend, operation):
    answer = backend.browser_run({"operation": operation, "path": "inputs/notes.md"})
    assert answer["ok"] is True
    assert answer["data"]["path"] == "inputs/notes.md"


@pytest.mark.parametrize("operation,key,value", REFUSED)
def test_the_operations_that_reach_the_network_refuse(backend, operation, key, value):
    answer = backend.browser_run({"operation": operation, key: value})
    assert answer["ok"] is False
    assert answer["error_type"] == "capability_unavailable"


def test_every_operation_the_contract_offers_is_covered_here():
    """A sixth operation added later would otherwise go unprobed.

    Which is how the first probe went wrong: it covered the shape it happened
    to pass and reported on the tool.
    """
    offered = {
        value
        for branch in TOOL_SCHEMAS["browser_run"]["oneOf"]
        for value in (
            branch["properties"]["operation"].get("enum")
            or [branch["properties"]["operation"]["const"]]
        )
    }
    assert offered == set(SERVED) | {operation for operation, _, _ in REFUSED}


@pytest.mark.parametrize("operation,key,value", REFUSED)
def test_the_refused_operations_are_valid_calls_not_malformed_ones(
    operation, key, value
):
    """The refusal is the backend's answer, not the schema rejecting the call.

    It matters which: a schema rejection would never have been billed, and the
    twelve tasks were billed for the turn that ended them.
    """
    assert validate_tool_arguments(
        "browser_run", {"operation": operation, key: value}
    ) == {"operation": operation, key: value}


def test_the_model_cannot_ask_which_tools_work():
    """There is no route from inside the loop to the fact above.

    `capabilities_query` is the tool for asking what the environment has, and
    the five things it will answer about are commands, runtimes, packages,
    formats and budgets. None of them is *tools*. A model that suspected
    `browser_run` was restricted had nothing to query, so the instruction text
    is the only account of which tools refuse -- and it names three, omitting
    this one.

    The backend does know. It records the browser as `fixture-local-only-v1`,
    which is the whole answer in one string, and then hashes it into
    `browser_build_sha256` where nothing can read it.

    If a `tools` kind is added later this test fails, which is the right time
    to revisit whether the instructions still need to carry the list alone.
    """
    assert set(TOOL_SCHEMAS["capabilities_query"]["properties"]["kind"]["enum"]) == {
        "commands",
        "runtimes",
        "packages",
        "formats",
        "budgets",
    }
    identity = foundation_fixture_identity(
        "offline-full-v1", {"tool_calls": 8, "wall_seconds": 600}
    )
    assert "tools" not in identity["capabilities"]
    assert "fixture-local-only-v1" not in repr(identity["capabilities"])
