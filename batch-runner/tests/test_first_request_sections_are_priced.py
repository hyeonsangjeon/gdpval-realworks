"""The container's first request carries three sections the render cannot see.

``SandboxRunner._run_attempt`` calls ``_augment_prompt`` first and hands **its
output** to ``render_prompt`` as the task. So a deliverable contract, a
dependency hint and a skills manual ride inside the very argument
``fixed_prompt_characters`` replaces with a one-character stand-in, and a cost
ceiling built from the render alone charged nothing for any of them. The
container's demand was the render — 5,020 characters — when its first request is
7,307. Understating a per-call figure understates the running half of the bill
once per call, for as long as the plan stands.

``core/first_request_sections.py`` closes that, and this file is what holds it
closed. Nothing here writes down a length: every figure is built through the
same builders a real attempt builds with — ``infer_deliverable_contract``,
``dependency_resolver.resolve``, ``SkillsRegistry.render_manual`` — laid out
through the same ``assemble_sections``, in the order the run's own prompt spec
gives. Add a word to a committed table and the figures here move with it; that
is proved below rather than asserted.

What is deliberately *not* measured here is measured somewhere else in the same
sum: the task's own words, per task from the catalogue, and the reference files,
per file at ``REFERENCE_FILE_CHARACTER_CAP``. ``SECTIONS_PRICED_SOMEWHERE_ELSE``
names each of them and says where, and asking this module to price one is an
error rather than an extra charge.

**Two worlds, and both are tested.** Since 2026-09-06 the comparison's own three
settings files set ``execution.shared_first_request: true``, and on that path the
container sends ``prompts/execution_envelope_shared.yaml`` — whose ``sections:``
list asks for none of the three its runner can build, so all three are priced at
nothing and ``budget.silent`` says why. That is the last section of this file.
Every other test here reaches for :func:`_settings_off_the_shared_request`,
because the pricing rule it holds is not the comparison's: it governs the 34
committed experiments that never opted in, where ``_augment_prompt`` really does
build a contract, a dependency hint and a skills manual before the render. A
rule tested only in the configuration that switches it off is a rule nothing
holds.

Nothing here calls a model, runs a container, or spends anything.
"""

from __future__ import annotations

import ast
import copy
import inspect
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

import core.deliverable_contract as deliverable_contract  # noqa: E402
import core.first_request_sections as first_request_sections  # noqa: E402
import core.prompt_sections as prompt_sections  # noqa: E402
from core.code_interpreter import CodeInterpreterRunner  # noqa: E402
from core.dependency_resolver import (  # noqa: E402
    EXT_PACKAGES,
    KEYWORD_PACKAGES,
    resolve,
)
from core.execution_envelope_cost import CostAssumptions  # noqa: E402
from core.execution_envelope_preflight import (  # noqa: E402
    _check_instruction_length,
    _prompt_files_a_run_place_might_send,
    _runner_first_request_extra_sections,
    conditions_from_plan,
    load_plan,
)
from core.execution_environment_readiness import (  # noqa: E402
    RUNNER_CLASS_BY_ENVIRONMENT,
)
from core.execution_envelope_tasks import (  # noqa: E402
    load_task_catalog,
    widest_occupation,
)
from core.first_request_sections import (  # noqa: E402
    SECTIONS_PRICED_SOMEWHERE_ELSE,
    SECTIONS_THIS_MODULE_PRICES,
    classify_every_section,
    first_request_section_budget,
    widest_reference_file_names,
    widest_task_words,
)
from core.prompt_loader import fixed_prompt_characters, load_prompt  # noqa: E402
from core.prompt_sections import (  # noqa: E402
    SectionContext,
    assemble_sections,
)
from core.sandbox_runner import SandboxRunner  # noqa: E402
from core.shared_first_request import SHARED_PROMPT_NAME  # noqa: E402
from core.skills_registry import SkillsRegistry  # noqa: E402
from core.subprocess_runner import SubprocessRunner  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
CATALOG = load_task_catalog()
WIDEST_OCCUPATION = widest_occupation(CATALOG)

THE_CONTAINER = "docker_container"
THE_TWO_THAT_ADD_NOTHING = ("host_python_process", "azure_code_interpreter")


# ── Reading the committed plan the way the rule reads it ──────────────────────


def _settings(environment: str) -> dict:
    relative = load_plan(PLAN_PATH)["experiment_files"][environment]
    return yaml.safe_load((BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"))


def _settings_off_the_shared_request(environment: str) -> dict:
    """The same committed file with the shared first request turned back off.

    Removing the key rather than writing ``false`` is the point: absence is the
    state every experiment outside this comparison is in, and the parse reads
    the setting with ``is True``, so absence and ``false`` take the same branch
    but only absence is the shape 34 committed files actually have.

    The assertion is what keeps this honest. If a settings file stops opting in,
    this helper stops being a copy of anything and starts being the committed
    file under a misleading name — so it fails here instead, next to the reason.
    """
    settings = copy.deepcopy(_settings(environment))
    turned_off = settings["execution"].pop("shared_first_request", None)
    assert turned_off is True, (
        f"{environment} was expected to set shared_first_request: true; "
        f"found {turned_off!r}"
    )
    return settings


def _sandbox(settings: dict) -> dict:
    return (settings.get("execution") or {}).get("sandbox") or {}


def _prompt_name(environment: str, settings: dict | None = None) -> str:
    settings = _settings_off_the_shared_request(environment) if settings is None else settings
    names = _prompt_files_a_run_place_might_send(environment, settings)
    assert names, environment
    return names[0]


def _budget(environment: str, settings: dict | None = None, **overrides):
    """The rule's own measurement, for one run place on its runner's own prompt."""
    settings = _settings_off_the_shared_request(environment) if settings is None else settings
    sandbox = _sandbox(settings)
    declared = _runner_first_request_extra_sections(environment)
    assert declared is not None, environment
    call = dict(
        prompt_name=_prompt_name(environment, settings),
        max_skills=sandbox.get("max_skills", 5),
        contract_config=sandbox.get("contract"),
    )
    call.update(overrides)
    return first_request_section_budget(declared, **call)


def _renders_to(environment: str, settings: dict | None = None) -> int:
    """What this run place's prompt file renders to, the task and sections aside."""
    settings = _settings_off_the_shared_request(environment) if settings is None else settings
    return sum(
        fixed_prompt_characters(
            load_prompt(_prompt_name(environment, settings)),
            experiment_prompt=(settings.get("condition_a") or {}).get("prompt"),
            occupation=WIDEST_OCCUPATION,
        ).values()
    )


def _priced_at(characters: int) -> dict:
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"]["instruction_character_count"] = characters
    return plan


def _problems_for(
    environment: str, plan: dict, *, root: Path = BATCH_RUNNER_ROOT
) -> list[str]:
    """The rule, asked about one run place, so the other two cannot answer."""
    conditions = conditions_from_plan(load_plan(PLAN_PATH))
    return _check_instruction_length(
        {environment: conditions[THE_CONTAINER]},
        CostAssumptions.from_mapping(plan["cost"]["assumptions"]),
        plan=plan,
        root=root,
        catalog=CATALOG,
    )


def _plan_naming(environment: str, settings: dict, tmp_path: Path, charged: int):
    """A plan whose one run place reads a settings file written for the test."""
    (tmp_path / "experiments").mkdir(exist_ok=True)
    relative = "experiments/for_this_test.yaml"
    (tmp_path / relative).write_text(yaml.safe_dump(settings), encoding="utf-8")
    plan = _priced_at(charged)
    plan["experiment_files"] = {environment: relative}
    return plan


def _plan_off_the_shared_request(environment: str, tmp_path: Path, charged: int):
    """The committed plan, priced at ``charged``, reading the not-opted-in copy.

    The rule resolves a run place's sections from its settings file, and on the
    shared first request that answer is *none of them* whatever the runner class
    says. So a test about what the container's runner builds has to hand the
    rule a settings file where the container's runner is the thing building.
    """
    return _plan_naming(
        environment, _settings_off_the_shared_request(environment), tmp_path, charged
    )


# ── What each runner declares ─────────────────────────────────────────────────


def test_the_container_declares_the_three_sections_augment_prompt_builds():
    """And every one of them is a section this module knows how to price."""
    declared = set(SandboxRunner.FIRST_REQUEST_EXTRA_SECTIONS)
    assert declared == {"contract", "deps_hint", "skills_manual"}
    assert declared <= SECTIONS_THIS_MODULE_PRICES


@pytest.mark.parametrize("runner", (CodeInterpreterRunner, SubprocessRunner))
def test_the_other_two_runners_declare_that_they_add_none_of_them(runner):
    """An empty tuple is a claim — and a true one: neither calls _augment_prompt."""
    assert runner.FIRST_REQUEST_EXTRA_SECTIONS == ()
    assert not hasattr(runner, "_augment_prompt")


@pytest.mark.parametrize("environment", sorted(load_plan(PLAN_PATH)["experiment_files"]))
def test_every_run_place_this_plan_prices_says_what_it_adds(environment):
    declared = _runner_first_request_extra_sections(environment)
    assert declared is not None, "silence is refused, not charged at nothing"
    assert set(declared) <= SECTIONS_THIS_MODULE_PRICES


@pytest.mark.parametrize(
    "environment",
    sorted(set(RUNNER_CLASS_BY_ENVIRONMENT) - set(load_plan(PLAN_PATH)["experiment_files"])),
)
def test_a_run_place_outside_this_plan_is_refused_rather_than_charged_nothing(
    environment, tmp_path
):
    """The other five entries in the map are not prompt-building run places.

    Four of them have no runner class at all, and the fifth,
    ``agentic_sandbox_v2``, is served by a runner that builds no request from a
    committed prompt file. None of them declares what it adds to a first
    request, and none of them may therefore be charged nothing: put one in a
    plan and the rule refuses it, whatever the plan charges. Charging a figure
    no length could exceed is what makes the refusal below a refusal and not a
    complaint about the figure.
    """
    plan = _plan_naming(
        environment, copy.deepcopy(_settings(THE_CONTAINER)), tmp_path, 10**6
    )
    problems = _problems_for(environment, plan, root=tmp_path)
    assert len(problems) == 1
    assert problems[0].startswith(f"{environment}'s cost is charged")
    assert "cannot be priced" in problems[0]


def test_a_run_place_no_runner_serves_declares_nothing_at_all():
    assert _runner_first_request_extra_sections("somewhere_nobody_wired_up") is None


# ── What the measurement comes to ─────────────────────────────────────────────


def test_the_containers_runner_adds_more_than_nothing_to_its_first_request():
    budget = _budget(THE_CONTAINER)
    assert budget.characters > 0
    assert set(budget.per_section) == {"contract", "deps_hint"}
    assert budget.characters == sum(budget.per_section.values())


@pytest.mark.parametrize("environment", THE_TWO_THAT_ADD_NOTHING)
def test_a_run_place_that_declares_none_of_them_is_charged_nothing_extra(environment):
    budget = _budget(environment)
    assert budget.characters == 0
    assert budget.per_section == {}
    assert budget.silent == {}


def test_the_figure_is_a_layout_and_not_a_tally_of_written_down_lengths():
    """Worked out a second way here, so the module cannot mark its own homework."""
    settings = _settings_off_the_shared_request(THE_CONTAINER)
    order = load_prompt(_prompt_name(THE_CONTAINER, settings)).get("sections")
    registry = SkillsRegistry()
    names = widest_reference_file_names(registry)
    words = widest_task_words(registry)
    nothing_resolved = resolve(reference_files=[], task_text="", base_packages=set())

    def laid_out(*, manifest, contract) -> int:
        return len(
            assemble_sections(
                order,
                SectionContext(
                    task_prompt="t",
                    ref_files=[],
                    skills=[],
                    manifest=manifest,
                    contract=contract,
                    reflection=None,
                    registry=registry,
                    perception_text=None,
                    host_reference_access=True,
                ),
            )
        )

    bare = laid_out(manifest=nothing_resolved, contract=None)
    both = laid_out(
        manifest=resolve(
            reference_files=names, task_text=words, base_packages=set()
        ),
        contract=deliverable_contract.infer_deliverable_contract(
            words, names, dict(_sandbox(settings).get("contract") or {})
        ),
    )
    assert _budget(THE_CONTAINER).characters == both - bare


def test_the_reference_files_are_left_out_of_the_layout_that_is_measured():
    """They are charged per file elsewhere; laying them out here would bill twice."""
    context = first_request_sections._context(
        registry=SkillsRegistry(),
        skills=[],
        manifest=resolve(reference_files=[], task_text="", base_packages=set()),
        contract=None,
    )
    assert context.ref_files == []
    assert context.reflection is None
    assert context.perception_text is None
    assert len(context.task_prompt) == 1


# ── Mutation proof: the bill is read from the tables ──────────────────────────


def test_a_word_added_to_the_contracts_tables_moves_the_bill(monkeypatch):
    before = _budget(THE_CONTAINER).per_section["contract"]
    monkeypatch.setattr(
        deliverable_contract,
        "_DELIVERABLE_NOUN_RULES",
        deliverable_contract._DELIVERABLE_NOUN_RULES
        + [
            (
                (".xyz",),
                ("a noun no committed table holds",),
                "A deliverable kind invented by this test",
            )
        ],
    )
    assert _budget(THE_CONTAINER).per_section["contract"] > before


def test_a_package_added_to_the_dependency_tables_moves_the_bill(monkeypatch):
    before = _budget(THE_CONTAINER).per_section["deps_hint"]
    monkeypatch.setitem(
        KEYWORD_PACKAGES, "a keyword no committed table holds", ["a-package-name"]
    )
    assert _budget(THE_CONTAINER).per_section["deps_hint"] > before


def test_an_extension_added_to_the_dependency_tables_moves_the_bill(monkeypatch):
    before = _budget(THE_CONTAINER).characters
    monkeypatch.setitem(EXT_PACKAGES, ".xyzzy", ["another-package-name"])
    assert _budget(THE_CONTAINER).characters > before


def test_a_word_pinned_by_a_run_places_contract_settings_moves_the_bill():
    """``execution.sandbox.contract`` is read, not just carried past.

    ``required_keywords`` is one of the keys ``infer_deliverable_contract``
    takes from the settings, and ``to_prompt_section`` writes it into a line
    the container's committed settings do not currently produce at all. Pinning
    one has to make the contract wider, or the settings are reaching the bill
    through nothing but their own absence.
    """
    settings = _settings_off_the_shared_request(THE_CONTAINER)
    before = _budget(THE_CONTAINER, settings).per_section["contract"]
    contract = dict(_sandbox(settings).get("contract") or {})
    contract["required_keywords"] = list(contract.get("required_keywords") or []) + [
        "quarterly-close-workbook"
    ]
    settings["execution"]["sandbox"]["contract"] = contract
    assert _budget(THE_CONTAINER, settings).per_section["contract"] > before


# ── Conditional fragments ─────────────────────────────────────────────────────


def test_the_committed_container_settings_switch_the_skills_manual_off():
    assert _sandbox(_settings(THE_CONTAINER)).get("max_skills") == 0


def test_a_section_the_settings_switch_off_is_priced_at_nothing_and_says_why():
    budget = _budget(THE_CONTAINER)
    assert "skills_manual" not in budget.per_section
    assert "0 skills" in budget.silent["skills_manual"]
    assert "Raising max_skills puts it back" in budget.silent["skills_manual"]


def test_raising_max_skills_puts_the_manual_back_and_it_is_not_small():
    off = _budget(THE_CONTAINER)
    on = _budget(THE_CONTAINER, max_skills=5)
    assert "skills_manual" in on.per_section
    assert on.characters == off.characters + on.per_section["skills_manual"]
    assert on.silent == {}


def test_one_more_skill_allowed_is_one_more_manual_charged():
    """The boundary of the switch, taken from the registry rather than typed."""
    available = len(SkillsRegistry().skills)
    assert available >= 2, "this proof needs the committed packs to exist"
    one = _budget(THE_CONTAINER, max_skills=1).per_section["skills_manual"]
    two = _budget(THE_CONTAINER, max_skills=2).per_section["skills_manual"]
    assert 0 < one < two


def test_a_prompt_spec_that_drops_a_section_prices_it_at_nothing_and_says_why(
    tmp_path,
):
    """An edit to the committed spec, made on a real copy of the real file."""
    real = load_prompt(_prompt_name(THE_CONTAINER))
    edited = copy.deepcopy(real)
    edited["sections"] = [
        entry
        for entry in real["sections"]
        if (entry.get("id") if isinstance(entry, dict) else entry) != "contract"
    ]
    assert len(edited["sections"]) == len(real["sections"]) - 1
    (tmp_path / "edited.yaml").write_text(yaml.safe_dump(edited), encoding="utf-8")

    budget = first_request_section_budget(
        SandboxRunner.FIRST_REQUEST_EXTRA_SECTIONS,
        prompt_name="edited",
        prompts_dir=tmp_path,
        max_skills=5,
        contract_config=_sandbox(_settings(THE_CONTAINER)).get("contract"),
    )
    assert "contract" not in budget.per_section
    assert "does not ask for it" in budget.silent["contract"]
    assert budget.characters == sum(budget.per_section.values())


# ── Fail closed rather than read a missing input as a zero ────────────────────


def test_a_skills_directory_that_is_not_there_is_refused_rather_than_measured(
    tmp_path,
):
    with pytest.raises(ValueError) as refused:
        _budget(THE_CONTAINER, skills_dir=tmp_path / "no_such_directory")
    assert "no skill pack was read" in str(refused.value)
    assert "no_such_directory" in str(refused.value)


def test_a_skills_directory_that_is_there_but_empty_is_refused_too(tmp_path):
    """``SkillsRegistry._load`` returns quietly either way, so both are refused."""
    empty = tmp_path / "skills"
    empty.mkdir()
    assert SkillsRegistry(empty).skills == {}
    with pytest.raises(ValueError, match="no skill pack was read"):
        _budget(THE_CONTAINER, skills_dir=empty)


def test_a_prompt_file_that_is_not_there_is_raised_rather_than_guessed_at():
    with pytest.raises(FileNotFoundError):
        first_request_section_budget(
            SandboxRunner.FIRST_REQUEST_EXTRA_SECTIONS,
            prompt_name="no_committed_file_has_this_name",
            max_skills=5,
        )


def test_a_runner_that_stops_declaring_is_refused_by_the_rule(monkeypatch, tmp_path):
    """The regression this whole change is: silence must not price at nothing.

    Asked of a not-opted-in settings file on purpose. On the shared first
    request the runner class is not the authority — ``prompts/
    execution_envelope_shared.yaml``'s own ``sections:`` list is, and
    ``core/shared_first_request.py`` refuses that list to name any of the three
    — so deleting the attribute there changes no answer and would prove
    nothing about this rule.
    """
    monkeypatch.delattr(SandboxRunner, "FIRST_REQUEST_EXTRA_SECTIONS")
    assert _runner_first_request_extra_sections(THE_CONTAINER) is None

    plan = _plan_off_the_shared_request(THE_CONTAINER, tmp_path, 1_000_000)
    refusals = _problems_for(THE_CONTAINER, plan, root=tmp_path)
    assert len(refusals) == 1
    assert "does not declare FIRST_REQUEST_EXTRA_SECTIONS" in refusals[0]
    assert "a figure nothing checked is not a figure that holds" in refusals[0]


@pytest.mark.parametrize("asked_for", ("lots", True, 2.5, None))
def test_a_max_skills_that_is_not_a_whole_number_is_refused(asked_for, tmp_path):
    settings = copy.deepcopy(_settings(THE_CONTAINER))
    settings["execution"]["sandbox"]["max_skills"] = asked_for
    plan = _plan_naming(THE_CONTAINER, settings, tmp_path, charged=1_000_000)

    refusals = _problems_for(THE_CONTAINER, plan, root=tmp_path)
    assert len(refusals) == 1
    assert "max_skills" in refusals[0]
    assert "not a whole number of skills" in refusals[0]


def test_settings_that_leave_max_skills_out_are_charged_for_the_manual(tmp_path):
    """``executor.py`` passes ``opts.get("max_skills", 5)``, so absent means on."""
    settings = _settings_off_the_shared_request(THE_CONTAINER)
    del settings["execution"]["sandbox"]["max_skills"]
    with_the_manual = _budget(THE_CONTAINER, settings).characters
    assert with_the_manual > _budget(THE_CONTAINER).characters

    charged = _renders_to(THE_CONTAINER) + _budget(THE_CONTAINER).characters
    plan = _plan_naming(THE_CONTAINER, settings, tmp_path, charged=charged)
    refusals = _problems_for(THE_CONTAINER, plan, root=tmp_path)
    assert len(refusals) == 1, "leaving the key out puts the manual back in the bill"
    assert f"come to {_renders_to(THE_CONTAINER) + with_the_manual} " in refusals[0]


# ── Nothing charged twice ─────────────────────────────────────────────────────


@pytest.mark.parametrize("elsewhere", sorted(SECTIONS_PRICED_SOMEWHERE_ELSE))
def test_a_section_charged_elsewhere_cannot_be_priced_here(elsewhere):
    with pytest.raises(KeyError):
        first_request_section_budget(
            [elsewhere],
            prompt_name=_prompt_name(THE_CONTAINER),
            max_skills=5,
        )


def test_the_two_lists_do_not_overlap():
    assert not (SECTIONS_THIS_MODULE_PRICES & set(SECTIONS_PRICED_SOMEWHERE_ELSE))


def test_every_section_the_repository_can_send_is_accounted_for():
    classify_every_section()


def test_a_new_section_nobody_priced_is_refused(monkeypatch):
    # ``first_request_sections`` holds the same dict object, so putting a new id
    # in it is the same edit adding a provider would be.
    monkeypatch.setitem(
        prompt_sections.SECTION_PROVIDERS, "something_new", lambda ctx: "x"
    )
    with pytest.raises(ValueError) as refused:
        classify_every_section()
    assert "something_new" in str(refused.value)
    assert "Pricing it at nothing would lower the ceiling" in str(refused.value)


def test_budgeting_for_a_section_that_cannot_be_sent_is_refused(monkeypatch):
    monkeypatch.setattr(
        first_request_sections,
        "SECTIONS_THIS_MODULE_PRICES",
        SECTIONS_THIS_MODULE_PRICES | {"a_section_prompt_sections_cannot_send"},
    )
    with pytest.raises(ValueError) as refused:
        classify_every_section()
    assert "a_section_prompt_sections_cannot_send" in str(refused.value)
    assert "one of the two is out of date" in str(refused.value)


def test_the_measurement_is_not_given_the_task_or_its_reference_files():
    """It cannot bill either, because neither is a thing it can be handed."""
    taken = set(inspect.signature(first_request_section_budget).parameters)
    assert taken == {
        "sections",
        "prompt_name",
        "max_skills",
        "contract_config",
        "prompts_dir",
        "skills_dir",
    }


# ── The undercount this replaces ──────────────────────────────────────────────


def test_charging_only_what_the_container_renders_to_is_refused(tmp_path):
    """The old figure exactly: the render, with the runner's sections left out."""
    renders_to = _renders_to(THE_CONTAINER)
    plan = _plan_off_the_shared_request(THE_CONTAINER, tmp_path, renders_to)
    refusals = _problems_for(THE_CONTAINER, plan, root=tmp_path)
    assert len(refusals) == 1
    short_by = int(refusals[0].split(" characters short")[0].split("— ")[-1])
    assert short_by == _budget(THE_CONTAINER).characters


def test_one_character_below_the_whole_first_request_is_refused(tmp_path):
    """The boundary, taken from the measurement rather than from a number typed."""
    sends = _renders_to(THE_CONTAINER) + _budget(THE_CONTAINER).characters
    exact = _plan_off_the_shared_request(THE_CONTAINER, tmp_path, sends)
    assert _problems_for(THE_CONTAINER, exact, root=tmp_path) == []

    one_short = _plan_off_the_shared_request(THE_CONTAINER, tmp_path, sends - 1)
    refusals = _problems_for(THE_CONTAINER, one_short, root=tmp_path)
    assert len(refusals) == 1
    assert f"come to {sends} characters" in refusals[0]
    assert "1 characters short" in refusals[0]


def test_the_committed_plan_charges_the_render_and_the_sections_together():
    charged = load_plan(PLAN_PATH)["cost"]["assumptions"][
        "instruction_character_count"
    ]
    assert charged >= _renders_to(THE_CONTAINER) + _budget(THE_CONTAINER).characters


def test_a_refusal_names_each_section_the_runner_built_and_what_stayed_silent(tmp_path):
    plan = _plan_off_the_shared_request(THE_CONTAINER, tmp_path, 1)
    refusals = _problems_for(THE_CONTAINER, plan, root=tmp_path)
    assert len(refusals) == 1
    said = refusals[0]
    assert "contract built by the runner before the render" in said
    assert "deps_hint built by the runner before the render" in said
    assert "skills_manual adds nothing because" in said
    # What is charged per task and per file elsewhere is not listed as though
    # this figure carried it.
    assert "previews" not in said
    assert "available_files" not in said


# ── What the comparison's own settings come to now ────────────────────────────


def test_the_three_comparison_settings_all_opt_in_to_the_shared_request():
    """The premise every test below rests on, checked rather than assumed."""
    for environment in sorted(load_plan(PLAN_PATH)["experiment_files"]):
        execution = _settings(environment)["execution"]
        assert execution.get("shared_first_request") is True, environment


def test_the_shared_prompt_asks_for_none_of_the_three_so_all_are_priced_at_nothing():
    """The container's own settings, unedited — the state the comparison runs in.

    Not a weaker version of the tests above: it is the other half of the same
    rule. ``first_request_section_budget`` prices a section the run place's own
    prompt spec asks for, and prices at nothing — saying so, by name — one it
    does not. Turning the shared first request on changed which spec is read,
    and this is what that change comes to.
    """
    budget = _budget(THE_CONTAINER, _settings(THE_CONTAINER))
    assert budget.characters == 0
    assert budget.per_section == {}
    assert set(budget.silent) == set(SandboxRunner.FIRST_REQUEST_EXTRA_SECTIONS)
    for section, why in budget.silent.items():
        assert SHARED_PROMPT_NAME in why, (section, why)
        assert "does not ask for it" in why, (section, why)


def test_the_rule_charges_the_comparisons_container_the_render_alone():
    """So the plan's figure is held to the shared render, sections and all.

    The refusal below is the same one the tests above raise; what differs is
    what it comes to. Charging one character under what the shared prompt
    renders to is still refused, and the shortfall is exactly the render —
    nothing added before it, because on this path nothing is.
    """
    settings = _settings(THE_CONTAINER)
    sends = _renders_to(THE_CONTAINER, settings)
    assert _budget(THE_CONTAINER, settings).characters == 0

    refusals = _problems_for(THE_CONTAINER, _priced_at(sends - 1))
    assert len(refusals) == 1
    assert f"prompts/{SHARED_PROMPT_NAME}.yaml" in refusals[0]
    assert f"come to {sends} characters" in refusals[0]
    assert _problems_for(THE_CONTAINER, _priced_at(sends)) == []


def test_the_shared_request_is_narrower_than_the_containers_old_one():
    """Which is why the committed ceiling now over-charges, and says it does.

    ``instruction_character_count`` was set to the widest first request this
    comparison had ever sent. It is kept there deliberately — a ceiling may be
    more careful than the thing it bounds, and lowering it would spend the
    headroom that catches a run place drifting back to that width. What must
    not happen quietly is the opposite, so the direction is asserted here.
    """
    old = _renders_to(THE_CONTAINER) + _budget(THE_CONTAINER).characters
    now = _renders_to(THE_CONTAINER, _settings(THE_CONTAINER))
    assert now < old

    charged = load_plan(PLAN_PATH)["cost"]["assumptions"][
        "instruction_character_count"
    ]
    assert charged >= old > now


# ── The method stays the one this measurement is valid for ────────────────────


def test_augment_prompt_still_only_builds_a_context_and_delegates():
    """Wording added straight into it would ride free of every figure above."""
    source = inspect.getsource(SandboxRunner._augment_prompt)
    assert "SectionContext(" in source
    assert "assemble_sections(section_order, ctx)" in source
    assert 'self.prompt_data.get("sections") or DEFAULT_SECTIONS' in source

    # Every way out of the method has to be a call to something that lays
    # sections out, never an expression that builds wording here. Counting the
    # returns instead would have said the same thing while there was one; it
    # stopped saying it when the shared first request added a second way out
    # that delegates just as strictly, to core/shared_first_request.py's
    # build_shared_task_text — which is itself assemble_sections over a section
    # list read from a committed prompt file.
    lays_sections_out = {"assemble_sections", "build_shared_task_text"}
    method = ast.parse(textwrap.dedent(source)).body[0]
    returned = [
        node.value
        for node in ast.walk(method)
        if isinstance(node, ast.Return) and node.value is not None
    ]
    assert returned, "_augment_prompt returns nothing at all"
    for value in returned:
        assert isinstance(value, ast.Call), ast.dump(value)
        assert isinstance(value.func, ast.Name), ast.dump(value.func)
        assert value.func.id in lays_sections_out, value.func.id


def test_the_runner_hands_that_output_to_render_prompt_as_the_task():
    """Which is why ``fixed_prompt_characters`` could not see any of it."""
    source = inspect.getsource(SandboxRunner._run_attempt)
    assert "augmented = self._augment_prompt(" in source
    assert "task_prompt=augmented," in source
