"""What each backend refuses, written beside each backend rather than once.

The plan carries a hand-written paragraph telling the model which tools refuse.
It names three, and it is wrong about both backends that exist -- in opposite
directions, so no edit to it can be right. On the fixture, ``exec_run`` is named
as refusing and one argv really works, while ``browser_run`` is not named at all
and its network half refuses. On the microVM it is the other way round:
``browser_run`` refuses every operation including ``open_local``, and
``exec_run`` boots a machine and runs the command. A paragraph true of one is
false of the other, and the run it would be false of is the real one.
``tests/test_the_standing_instructions_fit_neither_backend.py`` holds both sides
of that against the code.

So the list is kept per backend and rendered at the point the prompt is built.

**Declared here, checked against behaviour by a test.** The alternative was to
find out by asking: call each tool once at the start of a run and see what comes
back. That is more honest in principle and wrong in practice, because those
calls are tool events like any other and would land in the trace, be counted,
and change the workspace. A declaration that a test proves against the real
methods buys the same guarantee without putting anything in the record --
``tests/test_the_declared_refusals_match_what_the_backends_do.py`` calls the
fixture's tools for real and asks the microVM's the way it can be asked without
a machine.

**Read by the stage runner, and only where a plan asks.** The instruction text
is a pinned condition of trial_30, and changing it means a new plan file and a
new run id rather than an edit in place. :func:`apply_tool_availability` is
therefore a no-op on any instruction string that does not ask for it: a plan
opts in by putting :data:`PLACEHOLDER` in its text, so every plan written
before this one passes through byte for byte.
:mod:`core.agentic_v2_instructions` is what the runner actually calls; it wraps
this and names the exact bytes that went to the model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

#: A plan asks for a derived list by putting this in its instruction text.
#: Absent, the text is returned unchanged -- which is what keeps the pinned
#: instructions of an already-run stage exactly as they were.
PLACEHOLDER = "{{TOOL_AVAILABILITY}}"

#: True of both backends, because it is not a property of either. Any result
#: that is not ``ok: true`` raises ``_EndTheRun`` in ``agentic_v2_runner.py``,
#: one layer above the backend. The paragraph the plan carries today says the
#: opposite -- "the calls are counted against you" -- which describes a refusal
#: as costing one turn of nine rather than as ending the task.
A_REFUSAL_ENDS_THE_TASK = (
    "A refused call ends your task. It is not a turn spent and recovered "
    "from: there is no turn after it. Do not call a tool listed below as "
    "refusing, and do not call one in a way this list says it will not serve."
)


#: How a verdict below was established. ``executed`` means a test really calls
#: the method and observes the answer. ``asserted`` means the verdict was read
#: out of the class -- it overrides the inherited method, its docstring says
#: what it does -- and the method has never been run here.
#:
#: The distinction is not pedantry. ``AgenticV2MicroVMBackend.exec_run`` is
#: declared ``works`` and boots a guest to do it, and per
#: ``tasks/0822_saturday/HOST_PERMISSIONS.md`` **nobody has measured that a
#: machine in this subscription boots a guest at all**. Both facts are true at
#: once and a single word cannot carry them, so the word for "we checked it
#: runs" and the word for "we checked the code is there" are kept apart.
EVIDENCE_KINDS = ("executed", "asserted")


@dataclass(frozen=True)
class ToolAvailability:
    """One tool, on one backend, in the terms the model needs.

    ``verdict`` is one of ``works``, ``partly`` or ``refuses``. ``partly`` is
    the one that matters and the one a yes/no list cannot hold: both backends
    have a tool that serves some arguments and refuses others, and on both of
    them it is the tool the current paragraph gets wrong.

    ``evidence`` says how the verdict was established and is not shown to the
    model -- it is for whoever is about to spend money on a run. See
    :data:`EVIDENCE_KINDS`.
    """

    tool: str
    verdict: str
    note: str
    evidence: str = "executed"

    def __post_init__(self) -> None:
        if self.verdict not in {"works", "partly", "refuses"}:
            raise ValueError(f"{self.tool}: unknown verdict {self.verdict!r}")
        if self.evidence not in EVIDENCE_KINDS:
            raise ValueError(f"{self.tool}: unknown evidence {self.evidence!r}")
        if self.verdict != "works" and not self.note.strip():
            raise ValueError(
                f"{self.tool}: a tool that does not simply work needs a note "
                "saying what it will and will not serve. A bare 'refuses' is "
                "what the current paragraph already tells the model, and it "
                "is not enough to act on"
            )


_FIXTURE: tuple[ToolAvailability, ...] = (
    ToolAvailability("workspace_apply", "works", ""),
    ToolAvailability("verify_public", "works", ""),
    ToolAvailability("capabilities_query", "works", ""),
    ToolAvailability("finalize", "works", ""),
    ToolAvailability(
        "exec_run",
        "partly",
        "serves exactly one command, `fixture-upper SOURCE DESTINATION`, "
        "which writes SOURCE upper-cased to DESTINATION. Every other argv "
        "refuses.",
    ),
    ToolAvailability(
        "browser_run",
        "partly",
        "serves `open_local`, `snapshot` and `screenshot`, each of which "
        "takes a path inside your workspace. `search` and `open_url` refuse: "
        "there is no network here.",
    ),
    ToolAvailability(
        "environment_resolve",
        "refuses",
        "there is no index to resolve against.",
    ),
    ToolAvailability(
        "environment_activate",
        "refuses",
        "there is nothing to activate, because nothing can be resolved.",
    ),
)

_MICROVM: tuple[ToolAvailability, ...] = (
    ToolAvailability("workspace_apply", "works", ""),
    ToolAvailability("verify_public", "works", ""),
    ToolAvailability("capabilities_query", "works", ""),
    ToolAvailability("finalize", "works", ""),
    ToolAvailability(
        "exec_run",
        "works",
        "runs your command in a machine of its own. One boot per call, so "
        "prefer one command that does the work to several that build up to it.",
        evidence="asserted",
    ),
    ToolAvailability(
        "browser_run",
        "refuses",
        "every operation, `open_local` included. The machine has no route out "
        "for `search` and `open_url`, and nothing here drives a browser for "
        "the three that need no network.",
    ),
    ToolAvailability(
        "environment_resolve",
        "refuses",
        "the machine's only network interface is the loopback, so there is "
        "nothing to resolve against.",
    ),
    ToolAvailability(
        "environment_activate",
        "refuses",
        "there is no lock to activate, because none can be made.",
    ),
)

#: Keyed by class name rather than by the class, so that reading this table
#: does not import a backend. ``run_agentic_v2_stage.py`` already writes the
#: same string into its run record as ``backend``.
AVAILABILITY_BY_BACKEND: Mapping[str, tuple[ToolAvailability, ...]] = {
    "AgenticV2FixtureBackend": _FIXTURE,
    "AgenticV2MicroVMBackend": _MICROVM,
}


def backend_name(backend: Any) -> str:
    """The class name, whether given the class, an instance, or the name."""
    if isinstance(backend, str):
        return backend
    if isinstance(backend, type):
        return backend.__name__
    return type(backend).__name__


def availability_for(backend: Any) -> tuple[ToolAvailability, ...]:
    """What `backend` serves and refuses.

    Raises rather than guessing. A backend nobody has written a list for is a
    backend whose refusals nobody has checked, and telling the model a list
    that was inferred from a similar-looking class is the failure this module
    exists to stop.
    """
    name = backend_name(backend)
    try:
        return AVAILABILITY_BY_BACKEND[name]
    except KeyError:
        raise KeyError(
            f"no refusal list has been written for {name}. Add one to "
            "AVAILABILITY_BY_BACKEND and a case to "
            "test_the_declared_refusals_match_what_the_backends_do.py, which "
            "will hold it against what the backend really does"
        ) from None


def tool_availability_paragraph(backend: Any) -> str:
    """The list as the model should read it, longest-lived facts first.

    Says nothing about :attr:`ToolAvailability.evidence`. How we came to know a
    tool works is an operator's question, and the model cannot act on it: it
    would read "declared to work, never run here" as a reason to avoid a tool
    that is in fact its only way to run a command.
    """
    entries = availability_for(backend)
    lines = [A_REFUSAL_ENDS_THE_TASK, ""]

    works = [entry.tool for entry in entries if entry.verdict == "works"]
    if works:
        lines.append(f"These serve any call the schema accepts: {', '.join(works)}.")

    for entry in entries:
        if entry.verdict == "partly":
            lines.append(f"{entry.tool} is open in part — it {entry.note}")
    for entry in entries:
        if entry.verdict == "refuses":
            lines.append(f"{entry.tool} refuses: {entry.note}")

    return "\n".join(lines)


def unverified_claims(backend: Any) -> tuple[ToolAvailability, ...]:
    """The tools `backend` is declared to serve that nobody here has run.

    Empty on the fixture: every one of its eight is called for real in
    ``tests/test_the_declared_refusals_match_what_the_backends_do.py``.

    One entry on the microVM -- ``exec_run`` -- and that entry is the whole
    reason this function exists. It is the only tool on that backend that runs
    anything, it is declared ``works`` on the strength of the class overriding
    the fixture's method, and the host it would boot on has not been granted
    the roles to boot anything (``tasks/0822_saturday/HOST_PERMISSIONS.md``).
    A run on that backend should say so out loud before it spends, rather than
    discovering it once per task.

    Refusals are not included. A tool declared to refuse and checked by calling
    it has been established the strongest way available, and one that turned
    out to work anyway would be a pleasant surprise rather than a run whose
    results were produced by something other than what was described.
    """
    return tuple(
        entry
        for entry in availability_for(backend)
        if entry.verdict != "refuses" and entry.evidence != "executed"
    )


def apply_tool_availability(instructions: str, backend: Any) -> str:
    """Substitute the derived list into `instructions`, if it asks for one.

    A string without :data:`PLACEHOLDER` comes back identical, which is the
    property the pinned plans rely on: adding this call to the stage runner
    must not change a single byte of what an already-run stage sent.
    """
    if PLACEHOLDER not in instructions:
        return instructions
    return instructions.replace(PLACEHOLDER, tool_availability_paragraph(backend))
