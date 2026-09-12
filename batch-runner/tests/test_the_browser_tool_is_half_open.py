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
on any tool result that is not ``ok: True`` -- not as a policy choice but
because the trace schema refuses a record in which a tool event follows a
failed one -- so a refusal here is terminal rather than something to work
around.

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

`exec_run` has the same shape and is pinned here too, at the bottom. It is
named in the instructions as refusing "every time", and one command really
runs. Nothing in trial_30 reached it, so this is exposure rather than a
finding about that run -- but it is the same trapdoor, and the environment
advertises it where the instructions deny it.
"""
from __future__ import annotations

import pytest

from core.agentic_v2_contract import (
    TOOL_SCHEMAS,
    AgenticV2Profile,
    validate_tool_arguments,
)
from core.agentic_v2_conversation import _ENDS_THE_RUN, StopReason
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


def test_the_loop_that_would_survive_a_refusal_never_gets_to_run():
    """The refusal is survivable one layer down, and that layer is never reached.

    `_ENDS_THE_RUN` is the conversation's table of tool failures that stop a
    run, and `capability_unavailable` is deliberately not in it: everything
    absent is handed back to the model, because "a loop that gave up at the
    first refusal would measure nothing". That is the loop the stage one
    instructions describe.

    `agentic_v2_runner.py:772` raises before the table is consulted, on any
    result that is not ``ok: True``. Its docstring gives the reason and it is
    not a preference -- `verify_agentic_v2_result` rejects a trace in which a
    tool event follows an ``ok: False`` one, so a run that continued past a
    refusal could not produce a verifiable record of itself. That half is
    pinned by ``test_trace_pair_rejects_tool_after_exact_error``, which uses
    this very tool and this very error.

    Neither file is wrong about itself, which is why this is worth a test of
    its own: the trap is in the join. A reader who deletes the raise to "let
    the documented loop run" gets an unverifiable trace, and a reader who
    trusts this table alone mis-predicts what twelve of trial_30's thirty tasks
    did.
    """
    assert "capability_unavailable" not in _ENDS_THE_RUN
    # What the model meets instead. Both halves of the join have to move
    # together, so the ceiling errors are named here as the contrast: these
    # *are* in the table, and they are the ones a task survives into a retry.
    assert _ENDS_THE_RUN["tool_budget_exhausted"] is StopReason.TOOL_CALL_LIMIT_REACHED


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


# ---------------------------------------------------------------------------
# The second tool with this shape
# ---------------------------------------------------------------------------


def _exec(argv):
    """A schema-valid `exec_run` call, so the probe matches what a model sends."""
    call = {"argv": list(argv), "cwd": ".", "timeout_seconds": 30}
    assert validate_tool_arguments("exec_run", call) == call
    return call


def test_exec_run_serves_exactly_one_command(backend):
    """The instructions say no commands run here. One does.

    `fixture-upper` with a source and a destination is served and really does
    the work -- the file comes back uppercased, with `returncode: 0`. Every
    other argv, including the same command with the wrong number of arguments,
    answers `capability_unavailable`, which ends the task.

    So `exec_run` is half open in the same way `browser_run` is, and described
    the opposite way round: `browser_run` is presented as available and is
    partly shut, `exec_run` is presented as shut "every time" and is partly
    open.
    """
    (backend.work / "a.txt").write_text("hello\n", encoding="utf-8")
    # `timeout_seconds` is required by the contract even though the fixture
    # ignores it, so these are calls a model could actually make: a call
    # missing it never reaches the backend at all.
    served = backend.exec_run(_exec(["fixture-upper", "a.txt", "b.txt"]))
    assert served["ok"] is True
    assert served["data"]["returncode"] == 0
    assert (backend.work / "b.txt").read_text(encoding="utf-8") == "HELLO\n"

    for argv in (["fixture-upper", "a.txt"], ["fixture-upper"], ["ls"],
                 ["sh", "-c", "echo hi"]):
        answer = backend.exec_run(_exec(argv))
        assert answer["ok"] is False, argv
        assert answer["error_type"] == "capability_unavailable", argv


def test_the_environment_advertises_the_command_the_instructions_deny(backend):
    """`capabilities_query` names it, so a model could go looking.

    This is the asymmetry that makes the `browser_run` gap load-bearing rather
    than untidy. Of the three things a model might want to know about this
    room, two are answerable from inside it and the third is not:

    * **commands** -- answered, and the answer is `fixture-upper`, which
      contradicts "no commands run here" in the instruction text
    * **budgets** -- answered, and it states the turn limit outright
    * **which tools refuse** -- not answerable at all; there is no `tools` kind

    A model that trusted the environment over the instructions and called
    `exec_run` would find the command real, and would end its task on the first
    argv it got wrong. Nothing in trial_30 did: all thirty obeyed the
    instruction and never called it. The exposure is what is pinned here.
    """
    commands = backend.capabilities_query({"kind": "commands"})
    assert commands["ok"] is True
    assert commands["data"]["items"] == ["fixture-upper"]

    budgets = backend.capabilities_query({"kind": "budgets"})
    assert budgets["ok"] is True
    # The number is whatever this backend was built with, not trial_30's 8.
    # What is being pinned is that the limit is answerable at all.
    assert any(item.startswith("tool_calls=") for item in budgets["data"]["items"])


# ---------------------------------------------------------------------------
# The general form of the mistake
# ---------------------------------------------------------------------------


#: One call per tool, chosen to be the best case that tool allows: if this
#: tool works at all, this is a call that works. Validated against the
#: contract below, so none of them is a lucky shape.
A_CALL_THAT_SHOULD_WORK = {
    "capabilities_query": {"kind": "commands"},
    "workspace_apply": {"operation": "read", "path": "inputs/notes.md"},
    "exec_run": {"argv": ["fixture-upper", "inputs/notes.md", "out.txt"],
                 "cwd": ".", "timeout_seconds": 30},
    "environment_resolve": {"ecosystem": "python", "requirements": ["nothing"]},
    "environment_activate": {"lock_digest": "0" * 64},
    "browser_run": {"operation": "open_local", "path": "inputs/notes.md"},
    "verify_public": {"deliverables": ["inputs/notes.md"]},
    "finalize": {"deliverables": ["inputs/notes.md"], "summary": "done"},
}

#: The tools with no working call at all under `offline-full-v1`. Two, not the
#: three the instructions name.
NO_CALL_WORKS = {"environment_resolve", "environment_activate"}


def test_every_call_in_the_sweep_is_a_legal_one():
    """Otherwise the sweep below would be measuring the schema, not the backend."""
    for name, arguments in A_CALL_THAT_SHOULD_WORK.items():
        assert validate_tool_arguments(name, arguments) == arguments, name


def test_exactly_two_tools_have_no_working_call(backend):
    """The instructions name three. Two is the answer.

    This is the general form of what this file is about, and the reason it is
    a sweep rather than two more named tests: it fails if *any* tool changes
    which side it is on, including one added later. A tool that starts
    refusing without being named is the `browser_run` mistake happening again;
    a tool that stops refusing while still being named is the opposite one,
    recorded in `test_agentic_stage_one_budget.py` as "telling a model a
    working tool is shut costs it the tool".

    Six of the eight have a call that works -- `exec_run` and `browser_run`
    among them. Only the two package tools are shut outright, and they are shut
    because the policy profile is `offline-full-v1`.
    """
    assert set(A_CALL_THAT_SHOULD_WORK) == set(TOOL_SCHEMAS)

    refused = set()
    for name in sorted(TOOL_SCHEMAS):
        answer = getattr(backend, name)(A_CALL_THAT_SHOULD_WORK[name])
        if answer.get("ok") is not True:
            assert answer["error_type"] == "capability_unavailable", name
            refused.add(name)
    assert refused == NO_CALL_WORKS
