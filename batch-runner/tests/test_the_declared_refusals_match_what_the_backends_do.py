"""The declared refusal lists, held against what the backends really do.

`core/agentic_v2_tool_availability.py` writes down what each backend serves and
refuses, so that the model can be told something true of the backend it is
actually on rather than one paragraph that is false of both. A written-down list
drifts from the code unless something stops it, and this file is that something.

Each list is checked the strongest way that costs nothing:

* the **fixture**'s tools are called for real, in a temp directory -- the ones
  declared as working, the exact call declared as served on each half-open tool,
  and the exact call declared as refused;
* the **microVM**'s four working tools are checked to be *the same function
  objects* as the fixture's, which they are because it subclasses it -- so
  calling the fixture's really did exercise the machine's;
* the microVM's three refusing tools drop their arguments and return, so they
  can be asked without a machine, a manifest or a host;
* and its ``exec_run``, the one call that would boot something, is checked by
  asking whether the class overrides it rather than by running it.

Also pinned here: adding the substitution to the stage runner must not change a
single byte of what an already-run stage sent. Every plan in the repository is
put through :func:`apply_tool_availability` and asserted to come back identical,
because none of them asks for a derived list.

Offline. No model call, no network, no machine, no spend.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.agentic_v2_contract import TOOL_NAMES, AgenticV2Profile
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend
from core.agentic_v2_tool_availability import (
    AVAILABILITY_BY_BACKEND,
    PLACEHOLDER,
    ToolAvailability,
    apply_tool_availability,
    availability_for,
    tool_availability_paragraph,
)

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]

#: The one argv the fixture's `exec_run` serves, per its declared note.
THE_COMMAND_THAT_WORKS = ["fixture-upper", "a.txt", "b.txt"]

#: Every operation `browser_run` accepts, from the contract's two schemas.
BROWSER_OPERATIONS = ("open_local", "snapshot", "screenshot", "open_url", "search")


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


def _declared(backend, tool: str) -> ToolAvailability:
    for entry in availability_for(backend):
        if entry.tool == tool:
            return entry
    raise AssertionError(f"{tool} is not declared for {backend}")


# ---------------------------------------------------------------------------
# Every tool is accounted for, on every backend
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_name", sorted(AVAILABILITY_BY_BACKEND))
def test_no_tool_is_left_out_of_a_list(backend_name):
    """Omission is the defect this module exists to stop, so check for it.

    The paragraph in the plan is wrong about `browser_run` by *not mentioning
    it*, and that silence ended twelve of trial_30's thirty tasks. A list that
    is allowed to be short can make the same mistake quietly.
    """
    declared = availability_for(backend_name)
    assert tuple(sorted(entry.tool for entry in declared)) == tuple(sorted(TOOL_NAMES))
    assert len({entry.tool for entry in declared}) == len(declared), "a tool twice"


@pytest.mark.parametrize("backend_name", sorted(AVAILABILITY_BY_BACKEND))
def test_every_declared_tool_exists_on_the_backend(backend_name):
    classes = {
        "AgenticV2FixtureBackend": AgenticV2FixtureBackend,
        "AgenticV2MicroVMBackend": AgenticV2MicroVMBackend,
    }
    backend = classes[backend_name]
    for entry in availability_for(backend_name):
        assert callable(getattr(backend, entry.tool, None)), (
            f"{backend_name} has no {entry.tool} to be right or wrong about"
        )


def test_an_unknown_backend_raises_rather_than_guessing():
    with pytest.raises(KeyError, match="no refusal list has been written"):
        availability_for("AgenticV2SomethingElseBackend")


# ---------------------------------------------------------------------------
# The fixture, called for real
# ---------------------------------------------------------------------------


def test_the_fixture_serves_everything_declared_as_working(fixture_backend):
    fixture_backend.work.joinpath("out").mkdir()
    served = {
        "capabilities_query": lambda: fixture_backend.capabilities_query(
            {"kind": "commands"}
        ),
        "workspace_apply": lambda: fixture_backend.workspace_apply(
            {"operation": "list", "path": "inputs"}
        ),
        "verify_public": lambda: fixture_backend.verify_public({"deliverables": []}),
        "finalize": lambda: fixture_backend.finalize(
            {"deliverables": [], "summary": "done"}
        ),
    }
    for entry in availability_for(AgenticV2FixtureBackend):
        if entry.verdict != "works":
            continue
        assert entry.tool in served, (
            f"{entry.tool} is declared as working and this test does not call "
            "it -- add a call rather than trusting the declaration"
        )
        assert served[entry.tool]()["ok"] is True, f"{entry.tool} did not serve"


def test_the_fixture_exec_run_is_open_exactly_as_declared(fixture_backend):
    """One argv works and another does not, which is what `partly` means."""
    assert _declared(AgenticV2FixtureBackend, "exec_run").verdict == "partly"

    served = fixture_backend.exec_run(
        {"argv": list(THE_COMMAND_THAT_WORKS), "cwd": ".", "timeout_seconds": 30}
    )
    assert served["ok"] is True
    assert (fixture_backend.work / "b.txt").read_text(encoding="utf-8") == "HELLO\n"

    refused = fixture_backend.exec_run(
        {"argv": ["python3", "-c", "print(1)"], "cwd": ".", "timeout_seconds": 30}
    )
    assert refused == {"ok": False, "error_type": "capability_unavailable"}


@pytest.mark.parametrize("operation", ["open_local", "snapshot", "screenshot"])
def test_the_fixture_browser_serves_the_three_local_operations(
    fixture_backend, operation
):
    assert _declared(AgenticV2FixtureBackend, "browser_run").verdict == "partly"
    answer = fixture_backend.browser_run(
        {"operation": operation, "path": "inputs/notes.md"}
    )
    assert answer["ok"] is True


@pytest.mark.parametrize("operation", ["search", "open_url"])
def test_the_fixture_browser_refuses_the_two_network_operations(
    fixture_backend, operation
):
    answer = fixture_backend.browser_run(
        {"operation": operation, "query": "anything", "url": "https://example.com"}
    )
    assert answer == {"ok": False, "error_type": "capability_unavailable"}


@pytest.mark.parametrize("tool", ["environment_resolve", "environment_activate"])
def test_the_fixture_refuses_what_it_is_declared_to_refuse(fixture_backend, tool):
    assert _declared(AgenticV2FixtureBackend, tool).verdict == "refuses"
    answer = getattr(fixture_backend, tool)({"packages": ["numpy"]})
    assert answer["ok"] is False
    assert answer["error_type"] == "capability_unavailable"


# ---------------------------------------------------------------------------
# The microVM, without booting one
# ---------------------------------------------------------------------------


#: Tools the machine implements itself, so the fixture's run does not stand in
#: for them. Each needs its own test, named here so that the claim is checkable
#: rather than an exemption.
COVERED_SEPARATELY = {
    "exec_run": "test_the_machine_implements_exec_run_rather_than_refusing_it",
}


def test_the_machines_working_tools_are_the_fixtures_own_functions():
    """It subclasses the fixture, so the calls above really did exercise these.

    This is the whole reason the machine's half of the list can be checked at
    all offline: the four inherited tools are not merely similar to the ones
    called for real above, they are the same function objects.

    ``exec_run`` is the exception and is listed as one. If another tool is ever
    overridden, this fails -- and the fix is to write a test for the override
    and name it in :data:`COVERED_SEPARATELY`, not to widen the exemption.
    """
    for entry in availability_for(AgenticV2MicroVMBackend):
        if entry.verdict != "works":
            continue
        if entry.tool in COVERED_SEPARATELY:
            covering = COVERED_SEPARATELY[entry.tool]
            assert covering in globals(), (
                f"{entry.tool} is exempted on the grounds that {covering} "
                "covers it, and no such test exists in this file"
            )
            continue
        assert getattr(AgenticV2MicroVMBackend, entry.tool) is getattr(
            AgenticV2FixtureBackend, entry.tool
        ), (
            f"{entry.tool} is overridden on the machine, so calling the "
            "fixture's no longer says anything about it. Write a test for the "
            "override and add it to COVERED_SEPARATELY"
        )


@pytest.mark.parametrize("operation", BROWSER_OPERATIONS)
def test_the_machine_browser_refuses_every_operation(operation):
    assert _declared(AgenticV2MicroVMBackend, "browser_run").verdict == "refuses"
    assert AgenticV2MicroVMBackend.browser_run(
        None, {"operation": operation, "path": "page.html"}
    ) == {"ok": False, "error_type": "capability_unavailable"}


@pytest.mark.parametrize("tool", ["environment_resolve", "environment_activate"])
def test_the_machine_refuses_the_environment_pair(tool):
    assert _declared(AgenticV2MicroVMBackend, tool).verdict == "refuses"
    assert getattr(AgenticV2MicroVMBackend, tool)(None, {"packages": ["numpy"]}) == {
        "ok": False,
        "error_type": "capability_unavailable",
    }


def test_the_machine_implements_exec_run_rather_than_refusing_it():
    """Checked by asking whether the class overrides it, not by running it.

    Running it boots a machine, which is exactly what this suite must not do.
    """
    assert _declared(AgenticV2MicroVMBackend, "exec_run").verdict == "works"
    assert AgenticV2MicroVMBackend.exec_run is not AgenticV2FixtureBackend.exec_run
    assert "boot" in (AgenticV2MicroVMBackend.exec_run.__doc__ or "").lower()


# ---------------------------------------------------------------------------
# What the model would be shown, and what the pinned plans keep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("backend_name", sorted(AVAILABILITY_BY_BACKEND))
def test_the_paragraph_says_a_refusal_ends_the_task(backend_name):
    """The correction that costs the most, and it is true of both backends."""
    paragraph = tool_availability_paragraph(backend_name)
    assert "A refused call ends your task" in paragraph
    assert "counted against you" not in paragraph, (
        "the sentence that told the model a refusal was survivable has come "
        "back; the runner still ends the task on the first one"
    )
    for entry in availability_for(backend_name):
        assert entry.tool in paragraph


def test_the_two_paragraphs_disagree_about_the_two_tools_that_matter():
    """Which is the fact that makes one hand-written paragraph impossible."""
    on_the_fixture = tool_availability_paragraph(AgenticV2FixtureBackend)
    on_the_machine = tool_availability_paragraph(AgenticV2MicroVMBackend)
    assert on_the_fixture != on_the_machine
    assert "exec_run is open in part" in on_the_fixture
    assert "browser_run refuses" in on_the_machine
    assert "browser_run refuses" not in on_the_fixture


def test_the_stage_runner_derives_for_the_backend_it_actually_builds():
    """Three places in the stage runner name a backend. They must agree.

    The instructions are derived for one class, the factory constructs one, and
    the run record writes one down. A run that told the model about the fixture
    while building the machine would be the exact failure this module exists to
    prevent, and it would look fine in every other check.

    Read out of the source rather than by running the stage: constructing it
    needs a staged dataset, an Azure client and an approved amount, none of
    which belong in an offline suite.
    """
    source = (BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py").read_text(
        encoding="utf-8"
    )
    assert (
        "apply_tool_availability(\n"
        '                    str(plan.get("instructions") or ""), '
        "AgenticV2FixtureBackend\n"
        "                )" in source
    ), "the instructions are no longer derived for AgenticV2FixtureBackend"
    assert "return AgenticV2FixtureBackend(root=task_root" in source, (
        "the factory builds something other than the backend the instructions "
        "are derived for"
    )
    assert '"backend": "AgenticV2FixtureBackend"' in source, (
        "the run record names a backend other than the one built"
    )
    assert "AgenticV2FixtureBackend" in AVAILABILITY_BY_BACKEND


def test_text_without_the_placeholder_comes_back_identical():
    untouched = "Three of them refuse in this run: exec_run, environment_resolve."
    assert apply_tool_availability(untouched, AgenticV2FixtureBackend) is untouched


def test_no_plan_in_the_repository_asks_for_a_derived_list_yet():
    """So wiring the substitution in cannot alter any stage that has run.

    The instruction text is a pinned condition. When a plan does opt in, it is
    a new plan file with its own run id, and this test is what will say so --
    it fails, and the fix is to name the new plan here rather than to delete
    the assertion.
    """
    plans = sorted((BATCH_RUNNER_ROOT / "experiments").rglob("*.yaml"))
    assert plans, "no experiment files found -- the glob is wrong, not the repo"

    asking = []
    for path in plans:
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(loaded, dict):
            continue
        text = str(loaded.get("instructions") or "")
        if PLACEHOLDER in text:
            asking.append(path.relative_to(BATCH_RUNNER_ROOT))
        assert apply_tool_availability(text, AgenticV2FixtureBackend) == text or asking

    assert asking == [], f"these plans now ask for a derived list: {asking}"
