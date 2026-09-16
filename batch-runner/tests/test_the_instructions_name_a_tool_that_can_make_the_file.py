"""The file-route paragraphs, held against the contract and the backends.

``core/agentic_v2_tool_availability.py`` grew a second and third paragraph, and
they make claims a reader cannot check by reading them: that a
``workspace_apply`` write cannot carry the bytes of a spreadsheet, that
``exec_run`` can, and that which of those is true depends on the backend. This
file is what stops those claims drifting from the code they describe.

The defect they repair was real and would have cost a paid run. The corrected
plan fixed the *tool list* -- which tools refuse -- and left two sentences
underneath it telling the model to write its deliverables with
``workspace_apply`` and that it might have to write files by hand rather than
run code. Both were written against the fixture, where nothing runs. Four of the
five deliverables in ``advance_check_5`` are ``.xlsx``, ``.pdf``, ``.pptx`` and
an image, and a model following those sentences could not have produced any of
them: the contract types ``content`` as ``string``. The run would have come back
with ``exec_run`` never called, which reads as a model that did not try.

So the claims are checked the same way the refusal list is:

* the **contract** is read for what ``workspace_apply`` will accept, rather than
  the number being copied into prose that goes stale silently;
* the **fixture**'s write is called for real with the first bytes of a real
  ``.xlsx``, and the file that lands is compared against them;
* the **fixture**'s ``exec_run`` is called for real with an arbitrary argv, to
  hold the "nothing here runs a program you wrote" branch;
* the **microVM**'s route is checked against the same declaration table the
  refusal list is built from, and that table is already held against the real
  methods by ``test_the_declared_refusals_match_what_the_backends_do.py``;
* and the **cohort** is read from ``core/execution_envelope_tasks.py``, so that
  "four of five are binary" is a fact about the run rather than a memory of one.

Also pinned: the no-op property, again. Three placeholders now exist and any of
them could have been spelt into a plan that was already run. Every plan in the
repository is rendered on both backends and every one but the corrected plan is
asserted to come back byte for byte.

Offline. No model call, no network, no machine, no spend.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_contract import TOOL_SCHEMAS, AgenticV2Profile  # noqa: E402
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend  # noqa: E402
from core.agentic_v2_instructions import resolve_instructions  # noqa: E402
from core.agentic_v2_tool_availability import (  # noqa: E402
    A_FILE_THAT_CANNOT_BE_MADE,
    FILE_ROUTE_PLACEHOLDER,
    PLACEHOLDER,
    READ_ROUTE_PLACEHOLDER,
    SUBSTITUTIONS,
    _content_is_a_string,
    _runs_a_command_of_your_choosing,
    _write_content_ceiling,
    apply_tool_availability,
    how_files_get_made,
    named_placeholders,
    reading_what_is_not_text,
)

MICROVM = "AgenticV2MicroVMBackend"
FIXTURE = "AgenticV2FixtureBackend"

CORRECTED_PLAN = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "agentic_corrected_harness_plan.yaml"
)

#: The first four bytes of every ``.xlsx``, ``.pptx`` and ``.docx``: a zip local
#: file header. ``\x03`` and ``\x04`` are control characters and the bytes that
#: follow in a real file are arbitrary, which is the whole difficulty -- there is
#: no text that encodes to them.
ZIP_MAGIC = b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00\x21\x00\xde\xad\xbe\xef"


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
    (made.work / "a.txt").write_text("hello\n", encoding="utf-8")
    return made


# ---------------------------------------------------------------------------
# What the contract will accept
# ---------------------------------------------------------------------------


def test_the_write_operation_takes_a_string_and_nothing_else():
    """The claim the whole paragraph rests on, read off the contract.

    Not "the backend encodes it as UTF-8" -- that is downstream. The model
    never gets as far as the backend, because the tool schema types ``content``
    as ``string`` and a call carrying bytes does not validate. If a
    ``content_base64`` is ever added, this fails and the paragraph is wrong.
    """
    branch = None
    for candidate in TOOL_SCHEMAS["workspace_apply"]["oneOf"]:
        if "write" in candidate["properties"].get("operation", {}).get("enum", ()):
            branch = candidate
    assert branch is not None, "workspace_apply has no write branch"
    assert branch["properties"]["content"]["type"] == "string"
    assert not set(branch["properties"]) & {"content_base64", "encoding", "bytes"}
    assert _content_is_a_string() is True


def test_the_ceiling_in_the_paragraph_is_the_ceiling_in_the_contract():
    """A number in front of the model, and the number its call is checked at.

    Two copies of ``1048576`` would agree today and diverge the first time one
    of them moved, and the one that moved silently would be the prose.
    """
    branch = next(
        candidate
        for candidate in TOOL_SCHEMAS["workspace_apply"]["oneOf"]
        if "write" in candidate["properties"].get("operation", {}).get("enum", ())
    )
    assert _write_content_ceiling() == branch["properties"]["content"]["maxLength"]
    assert f"{_write_content_ceiling():,}" in how_files_get_made(MICROVM)


def test_exec_run_really_offers_the_interpreter_form_the_paragraph_names():
    """The paragraph tells the model to pass an ``interpreter`` and a ``script``.

    That is one of two branches in ``exec_run``'s schema, and it is the one
    worth naming: the other needs an ``argv``, which means the model must first
    write the script to a file with the tool that cannot write bytes. Naming a
    form the contract does not accept would be the same defect in a new place.
    """
    forms = TOOL_SCHEMAS["exec_run"]["oneOf"]
    script_form = [f for f in forms if "interpreter" in f["properties"]]
    assert len(script_form) == 1, "exec_run no longer takes an interpreter and script"
    assert "python" in script_form[0]["properties"]["interpreter"]["enum"]
    paragraph = how_files_get_made(MICROVM)
    assert "interpreter" in paragraph and "script" in paragraph


# ---------------------------------------------------------------------------
# What the backends really do
# ---------------------------------------------------------------------------


def test_a_write_cannot_put_the_bytes_of_a_spreadsheet_on_disk(fixture_backend):
    """Called for real, with the bytes that begin every ``.xlsx``.

    The model's only channel is a ``str``, so the strongest form of the claim
    is this: take the bytes of a real file, hand them over the only way the
    schema allows, and compare what lands. It does not match, and it cannot --
    the round trip goes through ``str(...).encode("utf-8")``, which is not an
    identity on arbitrary bytes.
    """
    smuggled = ZIP_MAGIC.decode("latin-1")
    result = fixture_backend.workspace_apply(
        {"operation": "write", "path": "book.xlsx", "content": smuggled}
    )
    assert result.get("ok") is not False

    landed = (fixture_backend.work / "book.xlsx").read_bytes()
    assert landed != ZIP_MAGIC, (
        "a workspace_apply write reproduced arbitrary bytes exactly. If that is "
        "now true, how_files_get_made is telling the model to take a longer "
        "route than it needs"
    )
    assert landed == smuggled.encode("utf-8")
    assert not landed.startswith(b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00\x21\x00\xde")


def test_the_fixture_refuses_a_command_of_the_models_choosing(fixture_backend):
    """The branch that says a binary deliverable cannot be made here.

    Held by calling, not by reading the table: the fixture's ``exec_run`` serves
    one fixed argv, so a model on it has no way to run code that writes a file.
    """
    refused = fixture_backend.exec_run(
        {
            "argv": ["python3", "-c", "open('book.xlsx','wb').write(b'PK')"],
            "cwd": ".",
            "timeout_seconds": 5,
        }
    )
    assert refused.get("ok") is False
    assert _runs_a_command_of_your_choosing(FIXTURE) is False
    assert _runs_a_command_of_your_choosing(MICROVM) is True


def test_each_backend_is_told_the_route_that_exists_on_it():
    """The two paragraphs differ, and each says the true thing for its backend."""
    on_microvm = how_files_get_made(MICROVM)
    on_fixture = how_files_get_made(FIXTURE)
    assert on_microvm != on_fixture

    assert "exec_run" in on_microvm
    assert "capabilities_query" in on_microvm, (
        "the paragraph must point at the tool that answers what the image has, "
        "rather than naming libraries here and going stale with the image"
    )

    assert "exec_run" not in on_fixture
    assert "cannot be produced in this run" in on_fixture
    for library in ("openpyxl", "reportlab", "python-pptx", "pptx", "matplotlib"):
        assert library not in on_microvm and library not in on_fixture


def test_neither_backend_is_left_free_to_hand_in_a_mislabelled_text_file():
    """The one instruction that belongs on both, and was on one.

    The fixture branch had it because there the reasoning is unavoidable:
    nothing runs, so the binary cannot be made, so say so rather than faking
    it. On the microVM the same end is reached one step further along -- the
    model is told to ask ``capabilities_query`` before depending on a library,
    and a no there leaves it at exactly the same place with nothing said about
    it. That branch is the one the paid cohort runs on.

    Forward-looking rather than observed: all five tasks in run 35111267647
    finished with ``deliverable_files_count: 0``, so no mislabelled file was
    handed in. Nothing was handed in at all.
    """
    for backend in (MICROVM, FIXTURE):
        paragraph = how_files_get_made(backend)
        assert A_FILE_THAT_CANNOT_BE_MADE in paragraph, (
            f"{backend} is told how to make the file and not what to do when "
            "it cannot be made. A text file under a binary's name counts as a "
            "deliverable produced and grades as an attempt"
        )
        assert paragraph.rstrip().endswith(A_FILE_THAT_CANNOT_BE_MADE), (
            f"{backend} carries the instruction somewhere other than after the "
            "route it is the fallback from"
        )

    # Written once, so the two cannot drift into saying different things about
    # the same file. Read out of the module rather than spelled here, because a
    # copy in the test is the drift it exists to stop.
    assert A_FILE_THAT_CANNOT_BE_MADE.count("named as though it were") == 1


def test_the_reading_paragraph_is_never_empty_and_never_the_same_twice():
    """A placeholder that resolves to nothing leaves a hole that reads as a bug."""
    on_microvm = reading_what_is_not_text(MICROVM)
    on_fixture = reading_what_is_not_text(FIXTURE)
    assert on_microvm.strip() and on_fixture.strip()
    assert on_microvm != on_fixture
    assert "exec_run" in on_microvm
    assert "exec_run" not in on_fixture


def test_an_unknown_backend_is_refused_by_both_new_paragraphs():
    """Same rule as the list. A guess is the failure the module exists to stop."""
    for build in (how_files_get_made, reading_what_is_not_text):
        with pytest.raises(KeyError):
            build("AgenticV2SomethingNobodyHasChecked")


# ---------------------------------------------------------------------------
# The cohort this was written for
# ---------------------------------------------------------------------------


def test_most_of_the_advance_check_cohort_hands_in_something_not_text():
    """Why the paragraph is load-bearing rather than tidy-minded.

    Read from the selector rather than remembered. If the cohort ever becomes
    all-text, this fails and the paragraph can be reconsidered -- which is the
    point: the reason is checked, not just the conclusion.
    """
    from core.execution_envelope_tasks import (
        load_task_catalog,
        select_advance_check_tasks,
    )

    chosen = select_advance_check_tasks(load_task_catalog())
    # ``reasons`` is a tuple of (format, task_id, why) triples, one per task.
    formats = [str(entry[0]) for entry in chosen.reasons]
    assert len(formats) == 5

    typeable = [f for f in formats if f == "text_only"]
    assert len(typeable) == 1, (
        f"formats {formats}: if most of this cohort became typeable, the route "
        "paragraph is no longer the thing standing between it and a deliverable"
    )

    # And the four that are not are not typeable in the specific way that
    # matters: the expert's own answer files are zip and PDF containers.
    why = " ".join(str(entry[2]) for entry in chosen.reasons)
    for extension in (".xlsx", ".pdf", ".pptx", ".jpg"):
        assert extension in why, (
            f"{extension} is no longer among this cohort's answer formats; "
            "re-read which of them a workspace_apply write could produce"
        )


# ---------------------------------------------------------------------------
# The plan, and every plan that did not ask
# ---------------------------------------------------------------------------


def test_the_corrected_plan_no_longer_hand_writes_the_route():
    """The two sentences are gone, and the placeholders are in their place."""
    raw = CORRECTED_PLAN.read_text(encoding="utf-8")
    instructions = yaml.safe_load(raw)["instructions"]

    for placeholder in (PLACEHOLDER, FILE_ROUTE_PLACEHOLDER, READ_ROUTE_PLACEHOLDER):
        assert placeholder in instructions

    assert "Write deliverables with workspace_apply" not in instructions
    assert "you may have to do by" not in instructions
    assert "writing the file yourself" not in instructions


def test_the_resolved_plan_tells_the_model_the_truth_on_both_backends():
    """End to end, through the function the runner calls."""
    plan = yaml.safe_load(CORRECTED_PLAN.read_text(encoding="utf-8"))

    on_microvm = resolve_instructions(plan, MICROVM)
    assert on_microvm.derived is True
    assert len(on_microvm.asked_for) == 3
    assert "{{" not in on_microvm.text, "a placeholder went out unsubstituted"
    assert "exec_run, with an `interpreter` and a `script`" in on_microvm.text

    on_fixture = resolve_instructions(plan, FIXTURE)
    assert "{{" not in on_fixture.text
    assert on_fixture.sha256 != on_microvm.sha256
    assert on_fixture.asked_for == on_microvm.asked_for


def test_the_resolved_plan_still_fits_the_width_it_was_priced_at():
    """Three paragraphs are longer than three placeholders.

    ``resolve_instructions`` refuses text wider than the cost figures were
    worked out at, which would turn this repair into a dispatch that stops
    before it starts. Checked here so that is found now rather than at dispatch.
    """
    import importlib.util

    plan = yaml.safe_load(CORRECTED_PLAN.read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location(
        "_stage_runner", BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"
    )
    runner = importlib.util.module_from_spec(spec)
    sys.modules["_stage_runner"] = runner
    spec.loader.exec_module(runner)

    priced = runner.shared_assumptions(plan).instruction_character_count
    for backend in (MICROVM, FIXTURE):
        resolved = resolve_instructions(plan, backend, priced_characters=priced)
        assert resolved.characters < priced


def test_every_other_plan_comes_back_byte_for_byte():
    """The property the pinned instructions of an already-run stage rely on.

    Three placeholders now, so three chances that a plan written before them
    happened to contain one. Checked over every plan in the repository rather
    than over the ones that came to mind.
    """
    unchanged = 0
    for path in sorted((BATCH_RUNNER_ROOT / "experiments").rglob("*.yaml")):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(document, dict):
            continue
        raw = document.get("instructions")
        if not isinstance(raw, str):
            continue
        for backend in (MICROVM, FIXTURE):
            rendered = apply_tool_availability(raw, backend)
            if path == CORRECTED_PLAN:
                assert rendered != raw
                continue
            assert rendered == raw, f"{path.name} changed under {backend}"
            unchanged += 1
    assert unchanged, "no plan was checked; the search found nothing to hold"


def test_every_placeholder_is_registered_and_substituted():
    """A placeholder defined and left out of the table is a hole that goes out.

    ``apply_tool_availability`` iterates ``SUBSTITUTIONS``. A fourth constant
    added beside the three without an entry would be spelt into a plan, match
    nothing, and reach the model as literal braces.
    """
    declared = {PLACEHOLDER, FILE_ROUTE_PLACEHOLDER, READ_ROUTE_PLACEHOLDER}
    assert set(SUBSTITUTIONS) == declared
    for name, (_, build) in SUBSTITUTIONS.items():
        rendered = apply_tool_availability(f"before {name} after", MICROVM)
        assert name not in rendered
        assert build(MICROVM) in rendered


def test_the_width_refusal_names_the_paragraphs_an_operator_would_look_for():
    """The operator-facing half of the table, held with the builders.

    A refusal about width is read in a hurry by someone deciding whether to
    shorten the plan or re-price it, and ``{{READING_WHAT_IS_NOT_TEXT}}`` is
    what to grep for rather than what it is. The name is checked here because
    it is the only part of ``SUBSTITUTIONS`` a test would otherwise never read.
    """
    assert named_placeholders([PLACEHOLDER]) == "the tool list"
    assert named_placeholders([]) == ""

    both = named_placeholders([PLACEHOLDER, FILE_ROUTE_PLACEHOLDER])
    assert both == "the tool list and the file route"

    all_three = named_placeholders(
        [PLACEHOLDER, FILE_ROUTE_PLACEHOLDER, READ_ROUTE_PLACEHOLDER]
    )
    assert all_three == "the tool list, the file route and the reading route"
    for name, (said, _) in SUBSTITUTIONS.items():
        assert said and "{{" not in said, f"{name} has no operator-facing name"
