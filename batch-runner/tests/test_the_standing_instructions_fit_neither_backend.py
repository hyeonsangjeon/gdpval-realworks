"""The instruction text is wrong about both backends, in opposite directions.

The design document's first ordered step is "settle `browser_run`", on the
reading that what is wrong is the instruction text rather than the harness --
"the cheapest thing in the area to correct". That reading is right about where
the defect is and wrong about how cheap it is, and this file is what changed my
mind.

The plan's `instructions:` block is a hand-written paragraph naming three tools
that refuse. Measured against the two backends that exist:

* on the **fixture**, `exec_run` is named as refusing and is half open -- one
  argv really works. `browser_run` is *not* named and half of it refuses, and a
  refusal ends the task, so the tool the text is silent about is the one that
  ended twelve of trial_30's thirty.
* on the **microvm**, it is the other way round. `browser_run` refuses *every*
  operation including `open_local`, which the fixture serves; and `exec_run`,
  named as refusing "every time", boots a machine and runs the command.

So there is no wording that is true of both. Editing the paragraph fixes the
fixture run and breaks the run it is a rehearsal for. The correction that holds
is to derive the refusal list from whichever backend is mounted -- which is a
change to how the prompt is built, not a change to a paragraph.

There is a fourth thing the text gets wrong, and it is the one that costs
tasks. It says a repeated refusal is wasteful:

    Calling them again will not change the answer, and the calls are counted
    against you.

The run does not count a refusal against you. It ends on it --
`agentic_v2_runner.py` raises `_EndTheRun` for *any* result that is not
`ok: true`. A model reading that sentence would believe a refused call costs
one of its nine and that it may go on; what actually happens is that the task
is over. None of that is visible from inside the room: `capabilities_query`
answers about commands, runtimes, packages, formats and budgets, and has no
`tools` kind (pinned in `test_the_browser_tool_is_half_open.py`).

**Nothing here changes a condition.** Fixing any of it means a new plan file
and a new run id, and trial_30 keeps the instructions it ran under. This file
only pins what the current text claims against what the two backends do, so
that a change to either side has to be deliberate.

Offline: a fixture backend in a temp directory and a paragraph of text. No
model call, no network, no spend.
"""
from __future__ import annotations

import pytest

from core.agentic_v2_contract import AgenticV2Profile
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend
from core.agentic_v2_stage_one_budget import (
    STAGE_ONE_PLAN_PATH,
    load_stage_one_plan,
)

#: The tools the paragraph names as refusing "every time".
NAMED_AS_REFUSING = ("exec_run", "environment_resolve", "environment_activate")

#: The one argv the fixture's `exec_run` really serves.
THE_COMMAND_THAT_WORKS = ["fixture-upper", "a.txt", "b.txt"]


@pytest.fixture(scope="module")
def instructions() -> str:
    """The paragraph the model is actually shown, from the plan the run reads.

    Whitespace is collapsed to single spaces. Where the lines happen to wrap is
    not part of what this file pins, and leaving the wrapping in place makes
    every check below silently sensitive to a re-flow of the paragraph.
    """
    text = str(load_stage_one_plan(STAGE_ONE_PLAN_PATH).get("instructions") or "")
    assert text.strip(), "the plan carries no instruction text to check"
    return " ".join(text.split())


@pytest.fixture
def fixture_backend(tmp_path):
    made = AgenticV2FixtureBackend(
        root=tmp_path / "task",
        profile=AgenticV2Profile(
            tool_contract_version="2.0",
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
    )
    (made.work / "inputs").mkdir()
    (made.work / "inputs" / "notes.md").write_text("a local file\n", encoding="utf-8")
    (made.work / "a.txt").write_text("hello\n", encoding="utf-8")
    return made


def _microvm_browser(operation: str):
    """What `AgenticV2MicroVMBackend.browser_run` answers, without a machine.

    The method refuses before it looks at anything: it reads `operation`, drops
    it, and returns. So it can be asked without a built backend, a manifest or
    a host, which is the only reason this comparison can be made offline at
    all. If it ever grows a branch that needs `self`, this raises instead of
    asserting -- and that would itself be the news, because the docstring's
    claim is that both branches refuse.
    """
    return AgenticV2MicroVMBackend.browser_run(
        None, {"operation": operation, "path": "page.html"}
    )


# ---------------------------------------------------------------------------
# What the paragraph claims
# ---------------------------------------------------------------------------


def test_the_text_names_three_tools_and_not_the_browser(instructions):
    """The list is the thing under test, so read it rather than assume it."""
    for tool in NAMED_AS_REFUSING:
        assert tool in instructions, f"{tool} is no longer named as refusing"
    assert "Three of them refuse in this run" in instructions

    head, _, _ = instructions.partition("YOUR INPUT FILES")
    assert "browser_run" not in head.split("Three of them refuse")[1], (
        "browser_run has been added to the refusal paragraph -- if that is "
        "deliberate, this file's premise has changed and the rest of it needs "
        "rewriting rather than re-running"
    )


def test_the_text_tells_the_model_a_refusal_is_survivable(instructions):
    """"counted against you" describes a cost. The run ends instead.

    This is the sentence that matters most, because a model that believed it
    would spend a call finding out and then discover the task was already over.
    """
    assert "the calls are counted against you" in instructions
    for ending in ("ends the task", "ends your task", "the task is over",
                   "you will not get another turn"):
        assert ending not in instructions, (
            "the text now warns that a refusal is terminal, which is the fix "
            "this file exists to argue for -- update the file, not the assert"
        )


# ---------------------------------------------------------------------------
# What the fixture backend does
# ---------------------------------------------------------------------------


def test_on_the_fixture_a_named_tool_is_half_open(fixture_backend):
    """`exec_run` is named as refusing every time. One argv really works."""
    served = fixture_backend.exec_run(
        {"argv": list(THE_COMMAND_THAT_WORKS), "cwd": ".", "timeout_seconds": 30}
    )
    assert served["ok"] is True
    assert (fixture_backend.work / "b.txt").read_text(encoding="utf-8") == "HELLO\n"


def test_on_the_fixture_the_unnamed_tool_is_the_one_that_refuses(fixture_backend):
    """`browser_run` is silent in the text and shut on the network half."""
    refused = fixture_backend.browser_run(
        {"operation": "search", "query": "quarterly revenue by segment"}
    )
    assert refused["ok"] is False
    assert refused["error_type"] == "capability_unavailable"

    served = fixture_backend.browser_run(
        {"operation": "open_local", "path": "inputs/notes.md"}
    )
    assert served["ok"] is True


# ---------------------------------------------------------------------------
# The two backends, side by side
# ---------------------------------------------------------------------------


def test_the_same_sentence_cannot_be_true_of_both_backends(fixture_backend):
    """`open_local` is served by one and refused by the other.

    This is the whole argument for deriving the text instead of writing it.
    Whatever a hand-written paragraph says about `browser_run`, it is wrong on
    one of the two runs, and the one it would be wrong on after an edit is the
    real backend.
    """
    on_the_fixture = fixture_backend.browser_run(
        {"operation": "open_local", "path": "inputs/notes.md"}
    )
    on_the_machine = _microvm_browser("open_local")

    assert on_the_fixture["ok"] is True
    assert on_the_machine["ok"] is False
    assert on_the_machine["error_type"] == "capability_unavailable"


@pytest.mark.parametrize("operation", ["search", "open_url", "open_local"])
def test_the_machine_refuses_the_browser_outright(operation):
    """Including the local one, which needs no network. By design."""
    assert _microvm_browser(operation) == {
        "ok": False,
        "error_type": "capability_unavailable",
    }


def test_the_machine_implements_the_command_tool_the_text_denies():
    """`exec_run` is real on the microvm; the text says it refuses every time.

    Checked by asking whether the class overrides it, rather than by running
    it: running it boots a machine, which is exactly what this suite must not
    do. The fixture's version and the machine's version being different
    functions is the fact worth holding.
    """
    assert (
        AgenticV2MicroVMBackend.exec_run is not AgenticV2FixtureBackend.exec_run
    )
    assert "boot" in (AgenticV2MicroVMBackend.exec_run.__doc__ or "").lower()
