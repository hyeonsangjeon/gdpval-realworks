"""What a reference file costs is read off the module that really sends it.

``core/execution_envelope_cost.py`` bills every reference file a task ships
with at ``REFERENCE_FILE_CHARACTER_CAP``, 50,000 characters, on every call of
every attempt in every run place. Until this file, the only thing standing
behind that figure was the comment beside it, and the comment was wrong. It
said ``core/file_reader.py`` cuts each file off there before it reaches the
model.

That cut is real, and it is unreachable. ``read_all_references`` is called from
exactly one place — ``PromptBuilder.build`` — and ``PromptBuilder`` is built
nowhere the pipeline runs. The one test that constructs it patches
``main.PromptBuilder.from_preset`` against a ``main.py`` this repository does
not contain. A justification pointing at dead code is worse than no
justification: a reader who went to check would have found a real cap at a real
number, in a module with a plausible name, and stopped looking.

What the model is really told about a reference file is built in
``core/file_preview.py``, and how much of it depends on the run place:

* the host process builds all three sections inline —
  ``build_file_structure_info``, ``generate_all_previews``, and the "Files
  available in current directory" line;
* the container reaches the same three by name, through the prompt spec's
  ``sections:`` list and ``core/prompt_sections.py``'s providers;
* Azure sends the structure summary only. Its reference files go up as
  container attachments and the model reads them by running code, so their
  bytes come back as tool results inside the request rather than as prompt
  text — already priced by ``max_tool_result_tokens_per_turn`` and the
  carried-forward input assumption.

So each runner declares ``REFERENCE_FILE_PROMPT_SECTIONS``, the preflight reads
it, and ``core/file_preview.py`` adds up what those sections may contribute
from the caps sitting beside the code that applies them.

Only one direction is refused, as everywhere else in that module. The constant
is 13 times the widest readable budget, so today it over-charges, and a ceiling
is allowed to be more careful than the thing it bounds. What is refused is the
constant falling *below* what a file can readably add. Raising
``MAX_PREVIEW_CHARS_PER_FILE`` from 3,000 to 60,000 would do exactly that, in
one line, in a module nobody would think to re-price — and every reference file
of every task would then be billed at less than it sends.

Two things here have no number in this repository, and the tests below say so
rather than inventing one. ``build_file_structure_info`` prints every column
header of every sheet with no character limit at all, and a workbook may carry
any number of columns. The preview headers put the file name outside the cut;
that one is allowed for at ``MAX_FILE_NAME_CHARACTERS``, the column headers
cannot be. The gap between the readable caps and the constant is what covers
them, which is why the constant is not lowered to fit and why the check guards
that gap from below.

Nothing here calls a model, opens a container, reaches Azure, or spends
anything. Every provider call is made with a mock in place of the client.
"""

from __future__ import annotations

import csv
import sys
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

import core.file_preview as file_preview  # noqa: E402
from core.code_interpreter import CodeInterpreterRunner  # noqa: E402
from core.execution_envelope_cost import (  # noqa: E402
    REFERENCE_FILE_CHARACTER_CAP,
)
from core.execution_envelope_preflight import (  # noqa: E402
    _check_the_plan_prices_what_the_files_add_to_the_prompt,
    _runner_reference_file_prompt_sections,
    check_experiment_files_match_conditions,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.execution_environment_readiness import (  # noqa: E402
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    RUNNER_CLASS_BY_ENVIRONMENT,
)
from core.file_preview import (  # noqa: E402
    MAX_FILE_NAME_CHARACTERS,
    MAX_PREVIEW_CHARS_PER_FILE,
    PREVIEW_BLOCK_WRAPPER_CHARACTERS,
    SECTIONS_THIS_MODULE_FILLS,
    reference_file_prompt_budget,
)
from core.prompt_sections import (  # noqa: E402
    DEFAULT_SECTIONS,
    SECTION_PROVIDERS,
    SectionContext,
    assemble_sections,
)
from core.sandbox_runner import SandboxRunner  # noqa: E402
from core.subprocess_runner import SubprocessRunner  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

THE_THREE_RUN_PLACES = {
    ENVIRONMENT_HOST_PYTHON_PROCESS: {},
    ENVIRONMENT_DOCKER_CONTAINER: {},
    ENVIRONMENT_AZURE_CODE_INTERPRETER: {},
}

REFUSAL_OPENING = "the cost sum bills every"

ALL_THREE_SECTIONS = ("file_structure", "previews", "available_files")

# Markers the three sections leave in a prompt, so a test can say which of them
# a run place really sent instead of trusting the declaration under test.
STRUCTURE_MARKER = "Reference File Structure"
PREVIEW_MARKER = "REFERENCE FILES PREVIEW"
AVAILABLE_MARKER = "Files available in"


@pytest.fixture
def reference_file(tmp_path: Path) -> Path:
    """One small real reference file, so the previews have something to read."""
    path = tmp_path / "budget_lines.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["region", "amount"])
        writer.writerow(["north", "12"])
    return path


class _EchoesWhatItIsGiven:
    """A stand-in for the registry and manifest the container prompt needs.

    Both are real objects behind a container image and a resolved dependency
    set, and neither is needed to answer the question these tests ask. They
    echo their arguments rather than returning a constant so that a provider
    that started handing reference files to one of them would change its
    section's text, and be caught below instead of hidden.
    """

    def render_manual(self, *args: object, **kwargs: object) -> str:
        return f"manual{args}{sorted(kwargs)}"

    def to_prompt_hint(self, *args: object, **kwargs: object) -> str:
        return f"deps{args}{sorted(kwargs)}"


def _section_context(ref_files: list[str]) -> SectionContext:
    return SectionContext(
        task_prompt="Summarise the regional totals",
        ref_files=ref_files,
        skills=None,
        manifest=_EchoesWhatItIsGiven(),
        contract=None,
        reflection=None,
        registry=_EchoesWhatItIsGiven(),
    )


def _azure_client() -> SimpleNamespace:
    """A stand-in Azure client that records the request instead of sending it."""
    response = SimpleNamespace(
        output=[],
        output_text="injected result",
        usage=SimpleNamespace(total_tokens=10, input_tokens=5, output_tokens=5),
    )
    return SimpleNamespace(
        responses=SimpleNamespace(create=Mock(return_value=response)),
        files=SimpleNamespace(
            create=Mock(return_value=SimpleNamespace(id="file-1")),
            delete=Mock(),
            content=Mock(),
        ),
        containers=SimpleNamespace(
            create=Mock(),
            files=SimpleNamespace(
                list=Mock(), content=SimpleNamespace(retrieve=Mock())
            ),
        ),
        close=Mock(),
    )


# ── What each run place really puts in the prompt ────────────────────────────


def test_the_host_process_sends_all_three_sections(reference_file: Path):
    response = Mock()
    response.choices = [Mock(message=Mock(content="```python\nprint(1)\n```"))]
    response.usage = Mock(total_tokens=10)

    with patch("core.subprocess_runner.complete") as complete:
        complete.return_value = (response, 10)
        SubprocessRunner(Mock()).run(
            task_prompt="Summarise the regional totals",
            model="m",
            reference_files=[str(reference_file)],
        )

    sent = "\n".join(
        str(message) for message in complete.call_args.kwargs["messages"]
    )
    assert STRUCTURE_MARKER in sent
    assert PREVIEW_MARKER in sent
    assert AVAILABLE_MARKER in sent
    assert reference_file.name in sent


def test_azure_sends_the_structure_summary_and_uploads_the_file(
    reference_file: Path,
):
    client = _azure_client()

    CodeInterpreterRunner(client=client).run(
        task_prompt="Summarise the regional totals",
        model="m",
        reference_files=[str(reference_file)],
    )

    request = client.responses.create.call_args.kwargs
    sent = str(request["input"]) + str(request.get("instructions"))
    assert STRUCTURE_MARKER in sent
    # The two the host sends and Azure does not. Its file goes up separately.
    assert PREVIEW_MARKER not in sent
    assert AVAILABLE_MARKER not in sent
    assert client.files.create.call_count == 1
    assert request["tools"][0]["container"]["file_ids"] == ["file-1"]


def test_the_container_sends_all_three_sections(reference_file: Path):
    assembled = assemble_sections(
        list(SandboxRunner.REFERENCE_FILE_PROMPT_SECTIONS),
        _section_context([str(reference_file)]),
    )

    assert STRUCTURE_MARKER in assembled
    assert PREVIEW_MARKER in assembled
    assert AVAILABLE_MARKER in assembled


def test_no_other_section_of_the_container_prompt_reads_a_reference_file(
    reference_file: Path,
):
    """The declaration has to be complete, not merely true as far as it goes.

    Asked of the code rather than of a list: every section provider is run
    twice, once with a reference file and once without, and the ones whose text
    moves are the ones a reference file is billed for. A section that started
    reading the files would show up here as a fourth name.
    """
    with_file = _section_context([str(reference_file)])
    without_file = _section_context([])

    moved = {
        section
        for section in SECTION_PROVIDERS
        if SECTION_PROVIDERS[section](with_file)
        != SECTION_PROVIDERS[section](without_file)
    }

    assert moved == set(ALL_THREE_SECTIONS)


def test_the_container_can_reach_every_section_it_declares():
    """Both routes to the container prompt: the committed spec and the fallback."""
    spec = yaml.safe_load(
        (BATCH_RUNNER_ROOT / "prompts" / "sandbox_occupation_codegen.yaml")
        .read_text(encoding="utf-8")
    )
    spec_ids = {
        entry["id"] if isinstance(entry, dict) else entry
        for entry in spec["sections"]
    }
    declared = set(SandboxRunner.REFERENCE_FILE_PROMPT_SECTIONS)

    assert declared <= spec_ids
    assert declared <= set(DEFAULT_SECTIONS)


# ── The runners say so, and the preflight reads it off them ──────────────────


@pytest.mark.parametrize("runner", [SubprocessRunner, SandboxRunner])
def test_the_two_local_places_declare_all_three_sections(runner):
    assert runner.REFERENCE_FILE_PROMPT_SECTIONS == ALL_THREE_SECTIONS


def test_azure_declares_the_structure_summary_alone():
    assert CodeInterpreterRunner.REFERENCE_FILE_PROMPT_SECTIONS == (
        "file_structure",
    )


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        (ENVIRONMENT_HOST_PYTHON_PROCESS, ALL_THREE_SECTIONS),
        (ENVIRONMENT_DOCKER_CONTAINER, ALL_THREE_SECTIONS),
        (ENVIRONMENT_AZURE_CODE_INTERPRETER, ("file_structure",)),
    ],
)
def test_the_preflight_reads_the_sections_off_the_registered_runner(
    environment, expected
):
    assert _runner_reference_file_prompt_sections(environment) == expected


def test_the_declaration_lives_on_the_class_the_registry_names():
    """Not on some other class with the same name in the same module."""
    for environment, expected in (
        (ENVIRONMENT_HOST_PYTHON_PROCESS, SubprocessRunner),
        (ENVIRONMENT_DOCKER_CONTAINER, SandboxRunner),
        (ENVIRONMENT_AZURE_CODE_INTERPRETER, CodeInterpreterRunner),
    ):
        module_name, class_name = RUNNER_CLASS_BY_ENVIRONMENT[environment]
        assert class_name == expected.__name__
        assert module_name.endswith(expected.__module__.rsplit(".", 1)[-1])


def test_a_run_place_with_no_runner_is_not_read_as_sending_nothing():
    assert _runner_reference_file_prompt_sections("codex_cloud") is None
    assert _runner_reference_file_prompt_sections("no_such_place") is None


def test_a_runner_that_does_not_declare_reads_as_unknown():
    """Two ways a runner can fail to say, and neither reads as "sends nothing"."""
    silent = type("RunnerThatDoesNotSay", (), {})

    with patch(
        "core.execution_envelope_preflight.import_module",
        return_value=SimpleNamespace(SandboxRunner=silent),
    ):
        assert (
            _runner_reference_file_prompt_sections(ENVIRONMENT_DOCKER_CONTAINER)
            is None
        )

    with patch(
        "core.execution_envelope_preflight.import_module",
        side_effect=ImportError("no container library on this machine"),
    ):
        assert (
            _runner_reference_file_prompt_sections(ENVIRONMENT_DOCKER_CONTAINER)
            is None
        )


# ── The arithmetic is read from the caps, not copied ─────────────────────────


def test_the_budget_adds_up_only_what_the_module_really_caps():
    budget = reference_file_prompt_budget(ALL_THREE_SECTIONS)

    assert budget.capped_characters == (
        MAX_PREVIEW_CHARS_PER_FILE
        + MAX_FILE_NAME_CHARACTERS
        + PREVIEW_BLOCK_WRAPPER_CHARACTERS
        + MAX_FILE_NAME_CHARACTERS
        + len("', '")
    )
    assert budget.uncapped_sections == ("file_structure",)
    assert budget.is_fully_capped is False


def test_the_uncapped_section_is_named_rather_than_counted_as_nothing():
    """No number is the honest answer for the structure summary, so none is given.

    ``build_file_structure_info`` prints every column header of every sheet and
    nothing cuts it off. Pricing it at zero would be a lie in the cheap
    direction; inventing a figure would be a guess dressed as a reading.
    """
    only_structure = reference_file_prompt_budget(("file_structure",))

    assert only_structure.capped_characters == 0
    assert only_structure.uncapped_sections == ("file_structure",)
    assert only_structure.is_fully_capped is False


def test_raising_a_cap_moves_the_budget():
    """The figure is worked out each call, so a stale copy cannot survive here."""
    before = reference_file_prompt_budget(("previews",)).capped_characters

    with patch.object(file_preview, "MAX_PREVIEW_CHARS_PER_FILE", 60_000):
        after = reference_file_prompt_budget(("previews",)).capped_characters

    assert after - before == 60_000 - MAX_PREVIEW_CHARS_PER_FILE


def test_a_section_this_module_does_not_fill_is_refused_not_priced_at_zero():
    with pytest.raises(KeyError):
        reference_file_prompt_budget(("skills_manual",))

    assert "skills_manual" not in SECTIONS_THIS_MODULE_FILLS
    assert SECTIONS_THIS_MODULE_FILLS == set(ALL_THREE_SECTIONS)


def test_the_budget_is_frozen_so_a_caller_cannot_edit_the_answer():
    budget = reference_file_prompt_budget(ALL_THREE_SECTIONS)

    with pytest.raises(FrozenInstanceError):
        budget.capped_characters = 1  # type: ignore[misc]


# ── The check refuses the cheap direction, and only that one ─────────────────


def test_the_check_is_silent_while_the_constant_covers_what_is_sent():
    assert _check_the_plan_prices_what_the_files_add_to_the_prompt(
        THE_THREE_RUN_PLACES
    ) == []


def test_raising_the_per_file_cap_past_the_constant_is_refused():
    """The one-line change in another module that this check exists to catch."""
    with patch.object(file_preview, "MAX_PREVIEW_CHARS_PER_FILE", 60_000):
        raised = reference_file_prompt_budget(
            ALL_THREE_SECTIONS
        ).capped_characters
        problems = _check_the_plan_prices_what_the_files_add_to_the_prompt(
            THE_THREE_RUN_PLACES
        )

    assert raised > REFERENCE_FILE_CHARACTER_CAP
    assert len(problems) == 2  # the host and the container; Azure sends no preview
    for problem in problems:
        assert REFUSAL_OPENING in problem
        assert f"{REFERENCE_FILE_CHARACTER_CAP:,}" in problem
        assert f"{raised:,}" in problem
        assert "core/file_preview.py" in problem
    assert any(ENVIRONMENT_HOST_PYTHON_PROCESS in p for p in problems)
    assert any(ENVIRONMENT_DOCKER_CONTAINER in p for p in problems)
    assert not any(ENVIRONMENT_AZURE_CODE_INTERPRETER in p for p in problems)


def test_lowering_the_constant_below_what_is_sent_is_refused():
    with patch(
        "core.execution_envelope_preflight.REFERENCE_FILE_CHARACTER_CAP", 1_000
    ):
        problems = _check_the_plan_prices_what_the_files_add_to_the_prompt(
            THE_THREE_RUN_PLACES
        )

    assert len(problems) == 2
    assert all("1,000" in problem for problem in problems)


def test_a_constant_far_above_what_is_sent_is_not_refused():
    """Over-charging is the safe direction and a ceiling may be careful."""
    with patch(
        "core.execution_envelope_preflight.REFERENCE_FILE_CHARACTER_CAP",
        5_000_000,
    ):
        assert _check_the_plan_prices_what_the_files_add_to_the_prompt(
            THE_THREE_RUN_PLACES
        ) == []


def test_a_constant_exactly_equal_to_what_is_sent_is_not_refused():
    widest = reference_file_prompt_budget(ALL_THREE_SECTIONS).capped_characters

    with patch(
        "core.execution_envelope_preflight.REFERENCE_FILE_CHARACTER_CAP", widest
    ):
        assert _check_the_plan_prices_what_the_files_add_to_the_prompt(
            THE_THREE_RUN_PLACES
        ) == []

    with patch(
        "core.execution_envelope_preflight.REFERENCE_FILE_CHARACTER_CAP",
        widest - 1,
    ):
        assert (
            len(
                _check_the_plan_prices_what_the_files_add_to_the_prompt(
                    THE_THREE_RUN_PLACES
                )
            )
            == 2
        )


def test_a_run_place_whose_runner_says_nothing_is_refused():
    problems = _check_the_plan_prices_what_the_files_add_to_the_prompt(
        {"codex_cloud": {}}
    )

    assert len(problems) == 1
    assert "REFERENCE_FILE_PROMPT_SECTIONS" in problems[0]
    assert "nothing checked is not a figure that holds" in problems[0]


def test_a_runner_naming_a_section_the_budget_does_not_know_is_refused():
    with patch.object(
        SubprocessRunner,
        "REFERENCE_FILE_PROMPT_SECTIONS",
        ("file_structure", "a_section_invented_later"),
    ):
        problems = _check_the_plan_prices_what_the_files_add_to_the_prompt(
            {ENVIRONMENT_HOST_PYTHON_PROCESS: {}}
        )

    assert len(problems) == 1
    assert "a_section_invented_later" in problems[0]
    assert "Pricing it at nothing would lower the bill" in problems[0]


def test_dropping_a_section_from_a_declaration_lowers_what_must_be_covered():
    """Which is why the declaration is held against the code, two tests above.

    Trimming the tuple makes this check ask for less, quietly. Nothing here can
    stop that on its own — what stops it is
    ``test_the_host_process_sends_all_three_sections``, which drives the runner
    and reads the prompt it built.
    """
    with patch.object(
        SubprocessRunner, "REFERENCE_FILE_PROMPT_SECTIONS", ("available_files",)
    ):
        with patch.object(file_preview, "MAX_PREVIEW_CHARS_PER_FILE", 60_000):
            problems = _check_the_plan_prices_what_the_files_add_to_the_prompt(
                {ENVIRONMENT_HOST_PYTHON_PROCESS: {}}
            )

    assert problems == []


# ── It is wired into the check that actually runs ────────────────────────────


def test_the_public_entry_carries_the_rule():
    plan = load_plan(PLAN_PATH)
    conditions = conditions_from_plan(plan)

    with patch.object(file_preview, "MAX_PREVIEW_CHARS_PER_FILE", 60_000):
        problems = check_experiment_files_match_conditions(
            plan, conditions, root=BATCH_RUNNER_ROOT
        )

    assert any(REFUSAL_OPENING in problem for problem in problems)


def test_the_whole_free_check_carries_the_rule():
    plan = load_plan(PLAN_PATH)

    with patch.object(file_preview, "MAX_PREVIEW_CHARS_PER_FILE", 60_000):
        result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    assert any(REFUSAL_OPENING in problem for problem in result.all_problems)
    assert result.may_start is False


def test_the_free_check_reports_exactly_what_it_would_without_this_rule():
    """This rule is dormant today; it must not move the standing report.

    Held against the same check with the rule switched off rather than against
    a problem count typed in here, for the reason given in the file next to
    this one: how many problems the free check finds depends on the machine it
    runs on, and a fixed number would fail on a build server for reasons that
    have nothing to do with what is being checked.
    """
    plan = load_plan(PLAN_PATH)
    with_rule = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)
    with patch(
        "core.execution_envelope_preflight."
        "_check_the_plan_prices_what_the_files_add_to_the_prompt",
        return_value=[],
    ):
        without_rule = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    assert with_rule.all_problems == without_rule.all_problems
    assert with_rule.may_start is without_rule.may_start is False


def test_the_ceiling_is_unchanged_because_the_constant_did_not_move():
    """Only the justification and the check around it changed, not the figure."""
    result = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)

    assert result.cost is not None
    assert result.cost.total_usd == Decimal("363.58481250")


# ── The justification that was wrong, and why it stayed wrong ────────────────


def test_the_constant_no_longer_credits_the_module_that_does_not_run():
    source = (
        BATCH_RUNNER_ROOT / "core" / "execution_envelope_cost.py"
    ).read_text(encoding="utf-8")

    assert "core/file_preview.py, which every run place goes through" in source
    assert "not core/file_reader.py" in source
    assert "core/file_reader.py cuts every reference file off" not in source


def test_the_cut_the_old_comment_pointed_at_is_still_unreachable():
    """If this ever fails, the 50,000 needs re-deriving, not re-explaining.

    ``read_all_references`` applies a real 50,000-character cut. Wiring it back
    into a run would put a second, different limit on the same cost line, and
    the constant would have to be worked out again from both.
    """
    callers = sorted(
        path.relative_to(BATCH_RUNNER_ROOT).as_posix()
        for path in BATCH_RUNNER_ROOT.rglob("*.py")
        if "tests" not in path.parts
        and ".git" not in path.parts
        and "read_all_references(" in path.read_text(encoding="utf-8")
    )

    assert callers == ["core/file_reader.py", "core/prompt_builder.py"]
    assert not (BATCH_RUNNER_ROOT / "main.py").exists()


def test_no_step_of_the_pipeline_builds_the_prompt_builder():
    builders = sorted(
        path.name
        for path in BATCH_RUNNER_ROOT.glob("step*.py")
        if "PromptBuilder" in path.read_text(encoding="utf-8")
    )

    assert builders == []


def test_the_constant_sits_above_every_readable_budget_with_room_to_spare():
    """The room is not decoration — it is what covers the uncapped sections.

    Stated as an inequality against the widest budget any run place can reach,
    not as a margin figure, so it stays true as the caps move and only fails
    when the headroom is actually gone.
    """
    widest = max(
        reference_file_prompt_budget(sections).capped_characters
        for sections in (
            SubprocessRunner.REFERENCE_FILE_PROMPT_SECTIONS,
            SandboxRunner.REFERENCE_FILE_PROMPT_SECTIONS,
            CodeInterpreterRunner.REFERENCE_FILE_PROMPT_SECTIONS,
        )
    )

    assert REFERENCE_FILE_CHARACTER_CAP > widest * 2
