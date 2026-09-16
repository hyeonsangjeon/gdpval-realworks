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

**Two questions, two paragraphs.** The list answers "which tools refuse". It
does not answer "which of the ones that do not refuse can produce the file the
task asked for", and that second question has its own wrong answer sitting in
the plans: ``workspace_apply`` is declared ``works`` on both backends, and its
``content`` is typed ``string`` by the contract, so it cannot write a ``.xlsx``,
a ``.pdf``, a ``.pptx`` or an image. Four of the five deliverables in
``advance_check_5`` are exactly those. :func:`how_files_get_made` is the second
paragraph and :data:`FILE_ROUTE_PLACEHOLDER` is how a plan asks for it.

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
from typing import Any, Callable, Mapping, Sequence

from core.agentic_v2_contract import TOOL_SCHEMAS

#: A plan asks for a derived list by putting this in its instruction text.
#: Absent, the text is returned unchanged -- which is what keeps the pinned
#: instructions of an already-run stage exactly as they were.
PLACEHOLDER = "{{TOOL_AVAILABILITY}}"

#: A plan asks for the route to a file by putting this in its instruction text.
#: Same opt-in rule as :data:`PLACEHOLDER`, and separate from it because the two
#: answer different questions. The list says which tools refuse; this says which
#: of the ones that do not refuse can produce the deliverable the task asked
#: for, which is not derivable from the list alone -- ``workspace_apply`` is
#: declared ``works`` on both backends and is the tool that cannot write four of
#: the five formats ``advance_check_5`` hands in.
FILE_ROUTE_PLACEHOLDER = "{{HOW_FILES_GET_MADE}}"

#: A plan asks what is left of an input it cannot decode. Same opt-in rule
#: again. Separate from the two above because it is about the files the model
#: was given rather than the ones it produces, and it belongs in a different
#: part of the prompt.
READ_ROUTE_PLACEHOLDER = "{{READING_WHAT_IS_NOT_TEXT}}"

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

#: Also true of both backends, and for two different reasons, which is why it
#: is written once rather than on the branch where the reason is obvious.
#:
#: Where nothing runs, the format cannot be made at all. Where a command runs,
#: it can still be that the image does not carry what the format needs -- and
#: that second case is reachable only on the backend the paid cohort uses. A
#: model is told there to ask ``capabilities_query`` before depending on a
#: library; it was not told what to do when the answer is no.
#:
#: A deliverable named ``.xlsx`` that holds text is worse than a missing one.
#: A missing file is visible in the file count; a mislabelled one is counted as
#: a file produced, reaches a grader as an attempt, and the run reads as having
#: done work it did not do.
A_FILE_THAT_CANNOT_BE_MADE = (
    "If the format cannot be made, hand in what you can type and say in it "
    "which part was asked for and could not be made. Do not hand in a text "
    "file named as though it were the format that was asked for."
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


#: The one backend whose refusals a plan is allowed to describe in its own
#: words. Not a preference between the two, and not a statement that the
#: fixture matters more.
#:
#: A plan that carries :data:`PLACEHOLDER` is safe on any backend, because the
#: list is then built from :data:`AVAILABILITY_BY_BACKEND` for whichever one is
#: mounted. A plan that writes the paragraph by hand is making an unverifiable
#: claim, and the only hand-written paragraph in this repository was measured
#: against the fixture -- ``tests/test_the_standing_instructions_fit_neither_
#: backend.py`` holds every sentence of it against both backends and finds it
#: wrong about each, in opposite directions.
#:
#: On the microVM the error runs the expensive way. The paragraph names
#: ``exec_run`` among three tools that "refuse in this run, every time", and
#: adds "No commands run here. There is no shell, no Python". On that backend
#: ``exec_run`` boots a machine and runs the command. A model told there is no
#: shell does not ask for one, so a cohort would be paid for in full, come back
#: with every task done the way a model does work when it cannot run anything,
#: and read as a result about the isolated backend. Nothing in the record would
#: contradict it.
#:
#: Adding a name here is not a formality. It says someone held that backend's
#: real methods against the words in the plan, the way that test file does.
DESCRIBED_BY_HAND_AND_CHECKED = frozenset({"AgenticV2FixtureBackend"})

#: How a plan says, in prose, that a tool will not serve.
#:
#: Used only to quote the offending sentence back in a refusal that has already
#: been decided on other grounds. Deliberately not the thing that decides:
#: prose is not a reliable input, a wording nobody anticipated would slip past
#: this tuple, and a check that can be got round by rephrasing is worse than no
#: check because it reads like one.
#:
#: Every marker here is about the environment. Modals of inability -- ``cannot``,
#: ``will not`` -- are deliberately absent, and not because they are rare. These
#: paragraphs are addressed to the model in the second person, so those words
#: attach to the reader at least as often as to a tool: the stage-one plan's
#: "If you cannot do the task, say why in the summary and call finalize anyway"
#: names a tool and denies nothing about it. Quoting that sentence under the
#: heading "what this backend does" would be worse than quoting nothing, because
#: an operator checking it would find the check wrong rather than the plan. The
#: cost of leaving them out is a refusal that carries no examples, which still
#: refuses.
_REFUSAL_IN_PROSE = (
    "refuse",
    "unavailable",
    "no commands run",
    "there is no shell",
)


def contradicted_sentences(instructions: str, backend: Any) -> tuple[str, ...]:
    """Sentences of `instructions` that call a tool `backend` serves refused.

    Best-effort and says so. Whitespace is flattened first because the claim
    this was written for straddles a line break in the plan file -- the tool
    names are on the line after the word ``capability_unavailable`` -- so
    anything matching line by line finds nothing at all.

    Returns the sentences rather than the tool names: an operator about to
    spend money is better served by the words that would have gone to the model
    than by a list of identifiers they then have to go and find.
    """
    serves = {
        entry.tool for entry in availability_for(backend) if entry.verdict != "refuses"
    }
    flat = " ".join(instructions.split())
    found = []
    for sentence in flat.split(". "):
        lowered = sentence.lower()
        if not any(marker in lowered for marker in _REFUSAL_IN_PROSE):
            continue
        named = sorted(tool for tool in serves if tool in sentence)
        if named:
            found.append(sentence.strip().rstrip(".") + ".")
    return tuple(found)


def _write_content_ceiling() -> int:
    """The byte width the contract puts on a ``workspace_apply`` write.

    Read out of :data:`core.agentic_v2_contract.TOOL_SCHEMAS` rather than
    written here, so the number in front of the model is the number its call is
    validated against. A second copy of ``1048576`` in a docstring is a number
    that goes stale silently.
    """
    for branch in TOOL_SCHEMAS["workspace_apply"]["oneOf"]:
        properties = branch.get("properties", {})
        operation = properties.get("operation", {})
        if "write" in operation.get("enum", ()):
            return int(properties["content"]["maxLength"])
    raise LookupError(
        "workspace_apply has no write branch in TOOL_SCHEMAS. The paragraph "
        "below describes a call that the contract no longer accepts"
    )


def _content_is_a_string() -> bool:
    """Whether a write can carry anything but text.

    The decisive fact, and the reason this module has a second paragraph. The
    contract types ``content`` as ``string``; there is no ``content_base64``,
    no encoding argument, and the backend's write ends in
    ``str(arguments["content"]).encode("utf-8")``. So a write cannot carry the
    bytes of a ``.xlsx``, and a model told to produce one with it is being told
    to do something the schema will not let it do.
    """
    for branch in TOOL_SCHEMAS["workspace_apply"]["oneOf"]:
        properties = branch.get("properties", {})
        if "write" in properties.get("operation", {}).get("enum", ()):
            fields = set(properties)
            return properties["content"].get("type") == "string" and not (
                fields & {"content_base64", "encoding", "bytes"}
            )
    return False


def _runs_a_command_of_your_choosing(backend: Any) -> bool:
    """Whether `backend` will run something the model wrote.

    Keyed off the same table the refusal list is built from, and therefore off
    the same test that holds that table against the real methods. ``partly`` is
    not enough: on the fixture ``exec_run`` serves one fixed argv, which runs a
    command but not one the model chose.
    """
    for entry in availability_for(backend):
        if entry.tool == "exec_run":
            return entry.verdict == "works"
    return False


def how_files_get_made(backend: Any) -> str:
    """Which tool can produce the deliverable, on this backend.

    The tool list says what refuses. It does not say that the one tool declared
    to work everywhere -- ``workspace_apply`` -- writes text and only text, and
    a model reading the list alone has no reason to think otherwise. Four of the
    five formats in ``advance_check_5`` are binary, so on that cohort the
    difference between this paragraph and no paragraph is four deliverables.

    Derived, not written: the ceiling and the string-typing come from
    :data:`core.agentic_v2_contract.TOOL_SCHEMAS`, and whether a command can be
    run comes from the refusal table. Nothing here names a library or an
    interpreter. What the image carries is the image's fact, the model has
    ``capabilities_query`` to ask it, and a list hard-coded here would be the
    same kind of claim as the hand-written paragraph this module replaced --
    true of the image it was written against and silently false of the next one.

    The branches differ in the route and end the same way, on
    :data:`A_FILE_THAT_CANNOT_BE_MADE`. Having that only where nothing runs is
    the reading of "cannot" a backend with a real interpreter invites and the
    one it cannot afford: ``capabilities_query`` answering no is exactly the
    moment a model needs to be told not to write the text under the binary's
    name, and it is reachable only there.
    """
    ceiling = _write_content_ceiling()
    lines = [
        "Deliverables are real files in your working directory. Which tool "
        "makes one depends on the format.",
        "",
    ]

    if _content_is_a_string():
        lines.append(
            f"workspace_apply, operation write, takes `content` as a string -- "
            f"up to {ceiling:,} bytes, and there is no argument on it that "
            "carries bytes. So it writes what can be typed: Markdown, CSV, "
            "HTML, JSON, source code."
        )
    else:
        lines.append(
            "workspace_apply, operation write, carries something other than "
            "text; check its schema before assuming what it will take."
        )

    if _runs_a_command_of_your_choosing(backend):
        lines.append(
            "A spreadsheet, a PDF, a slide deck or an image cannot be typed, "
            "so they are not made that way. They are made by a program: "
            "exec_run, with an `interpreter` and a `script`, writing the file "
            "into your working directory. Files a command leaves there are the "
            "same files finalize collects."
        )
        lines.append(
            "Ask capabilities_query what this machine has before you depend on "
            "a library being in it."
        )
    else:
        lines.append(
            "Nothing here runs a program you wrote, so a format that cannot be "
            "typed cannot be produced in this run."
        )

    # Last on both branches, because it is what to do when the route above ran
    # out -- and on the microVM the route runs out one step further along, at
    # an image that does not carry the library rather than at a backend that
    # runs nothing.
    lines.append(A_FILE_THAT_CANNOT_BE_MADE)

    return "\n".join(lines)


def reading_what_is_not_text(backend: Any) -> str:
    """Whether the original of a non-text input is reachable, on this backend.

    The plan's input section is right that ``workspace_apply(read)`` decodes
    UTF-8 and fails on a spreadsheet, and right to say so -- without it a model
    retries the same call. What it cannot say on its own is what follows from
    that, because what follows differs: where a command can run, the original is
    still reachable and the converter's text version is a fallback rather than
    the only way in; where none can, the text version is the whole of it.

    One sentence either way, and never empty. A placeholder that resolves to
    nothing leaves a blank line where a paragraph was, and the blank line is
    indistinguishable from a plan that forgot to say anything.
    """
    if _runs_a_command_of_your_choosing(backend):
        return (
            "The original is still reachable, though: a program can open what "
            "the reader cannot. If the work needs what the converter dropped, "
            "read the file in inputs/ with exec_run rather than settling for "
            "the text version."
        )
    return (
        "Nothing here runs a program over it either, so where a text version "
        "exists it is the whole of what you can see of that file."
    )


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


#: Every placeholder a plan may opt into: what an operator would call it, and
#: what fills it. Iterated rather than chained by hand so that adding a fourth
#: is one entry and not a branch some caller forgets.
#:
#: The name sits beside its builder rather than in a second table. A refusal
#: about width has to say which paragraph made the text wider, and two tables
#: keyed the same way drift in exactly the way that answer must not.
SUBSTITUTIONS: Mapping[str, tuple[str, Callable[[Any], str]]] = {
    PLACEHOLDER: ("the tool list", tool_availability_paragraph),
    FILE_ROUTE_PLACEHOLDER: ("the file route", how_files_get_made),
    READ_ROUTE_PLACEHOLDER: ("the reading route", reading_what_is_not_text),
}


def placeholders_in(instructions: str) -> tuple[str, ...]:
    """Which placeholders `instructions` asks to have filled, in a fixed order.

    Separate from the substitution so a caller can record what a plan asked for
    without rendering it -- the run record wants the names, not the prose.
    """
    return tuple(name for name in SUBSTITUTIONS if name in instructions)


def named_placeholders(names: Sequence[str]) -> str:
    """`names` as an operator would say them, for a message about them.

    ``{{TOOL_AVAILABILITY}}`` is what to search the plan file for and "the tool
    list" is what it is; a refusal that has to be read quickly wants the second.
    The placeholder itself is not lost -- the run record carries it verbatim
    under ``substituted``.
    """
    said = [SUBSTITUTIONS[name][0] for name in names]
    if len(said) <= 1:
        return "".join(said)
    return ", ".join(said[:-1]) + " and " + said[-1]


def apply_tool_availability(instructions: str, backend: Any) -> str:
    """Substitute the derived paragraphs into `instructions`, where it asks.

    A string with no placeholder in it comes back identical, which is the
    property the pinned plans rely on: adding this call to the stage runner
    must not change a single byte of what an already-run stage sent. Each
    placeholder is independent, so a plan that asks for the tool list and not
    the file route gets exactly what it asked for.

    The backend is resolved once per placeholder present and not at all when
    none is, so a plan that opts out of both is never asked which backend it is
    on. :func:`core.agentic_v2_instructions.resolve_instructions` looks that up
    separately and on every path, which is where an unknown backend is refused.
    """
    for name in placeholders_in(instructions):
        _, build = SUBSTITUTIONS[name]
        instructions = instructions.replace(name, build(backend))
    return instructions
