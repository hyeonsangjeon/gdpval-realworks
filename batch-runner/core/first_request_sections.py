"""What a run place puts in its first request past the prompt and the files.

``core/prompt_loader.py``'s :func:`fixed_prompt_characters` measures what a
committed prompt file and a run's own settings wrap every task in. It renders
with a one-character stand-in where the task goes, on purpose, so the task's own
words are not charged twice — they are billed per task from the catalogue.

The container's first request carries more than that, and the stand-in is
exactly why it went unseen. ``SandboxRunner._run_attempt`` calls
``_augment_prompt`` first and hands **its output** to ``render_prompt`` as the
task. So the deliverable contract, the dependency hint and the skills manual
ride inside the argument the stand-in replaces, and a figure built from
``fixed_prompt_characters`` alone leaves every one of them out. The container's
demand was therefore smaller than its real first request — the one direction a
cost ceiling is not allowed to be wrong in.

This module closes that. It does not hold a length for any of the three. It
builds them through the same functions a real attempt builds them with —
:func:`core.deliverable_contract.infer_deliverable_contract`,
:func:`core.dependency_resolver.resolve`,
:meth:`core.skills_registry.SkillsRegistry.render_manual` — and lays them out
through the same :func:`core.prompt_sections.assemble_sections` that lays out
the real request, in the order the run's own prompt spec gives. Editing a
fragment moves the figure; nothing here is copied from anything.

**How wide.** Two of the three read the task's own words, and the catalogue this
plan runs from records a task's length and its digest but not its text. Guessing
"no words matched" would be reading a missing input as a zero, which is the
failure this whole check exists to stop. So they are driven to the widest their
own committed tables can produce: every word
:func:`core.deliverable_contract.detection_vocabulary` can match, every key of
``KEYWORD_PACKAGES``, one file name per extension in ``EXT_PACKAGES``, and every
extension and keyword the committed skill packs declare. The dependency hint is
resolved against an **empty** base image, because the hint's warning line names
the packages the image does not carry and is longest when it names all of them.

That over-charges — the widest real task reaches nowhere near it — and it is
allowed to, on the rule the rest of this preflight already runs on: a ceiling
may be more careful than the thing it bounds, and only the cheap direction is
refused. What it buys is that no wording added to those tables can escape the
bill, because the bill is read from the tables.

**What is not counted here, and where it is counted instead.** Every id in
``core/prompt_sections.py``'s ``SECTION_PROVIDERS`` is in exactly one of
:data:`SECTIONS_THIS_MODULE_PRICES` or :data:`SECTIONS_PRICED_SOMEWHERE_ELSE`,
and :func:`classify_every_section` refuses when one is in neither. A section
added to that table without a decision about its cost is a section that would
otherwise ride free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from core.deliverable_contract import (
    detection_vocabulary,
    infer_deliverable_contract,
)
from core.dependency_resolver import EXT_PACKAGES, KEYWORD_PACKAGES, resolve
from core.prompt_loader import load_prompt
from core.prompt_sections import (
    DEFAULT_SECTIONS,
    SECTION_PROVIDERS,
    SectionContext,
    assemble_sections,
    enabled_section_ids,
)
from core.skills_registry import SkillsRegistry

#: Sections whose characters this module works out. All three are built by
#: ``SandboxRunner._augment_prompt`` and none of them is charged anywhere else.
SECTIONS_THIS_MODULE_PRICES: frozenset[str] = frozenset(
    {"contract", "deps_hint", "skills_manual"}
)

#: Sections a first request may carry that are charged elsewhere, and where.
#: Read by :func:`classify_every_section`; the reasons are the record of why
#: adding them here would bill the same characters twice.
SECTIONS_PRICED_SOMEWHERE_ELSE: Mapping[str, str] = {
    "task": (
        "the task's own words, billed per task from the catalogue's "
        "prompt_character_count by core/execution_envelope_cost.py's "
        "max_input_tokens_per_call"
    ),
    "file_structure": (
        "built from the reference files, billed per file at "
        "REFERENCE_FILE_CHARACTER_CAP and held against core/file_preview.py's "
        "own caps by _check_the_plan_prices_what_the_files_add_to_the_prompt"
    ),
    "previews": (
        "built from the reference files, billed per file at "
        "REFERENCE_FILE_CHARACTER_CAP — same rule as file_structure"
    ),
    "available_files": (
        "built from the reference files, billed per file at "
        "REFERENCE_FILE_CHARACTER_CAP — same rule as file_structure"
    ),
    "reflection": (
        "no first request carries it: SandboxRunner.run opens with "
        "reflection = None and only fills it from a finished attempt, so it "
        "belongs to the repair rounds the plan's own attempt count covers"
    ),
    "perception_analysis": (
        "filled only from a preprocessor's output, which step2_run_inference.py "
        "passes through when one is configured; none of the three settings "
        "files in this plan configures one, and the plan's grading_perception "
        "block is what prices a perception call when one is made"
    ),
}


def classify_every_section() -> None:
    """Refuse if any known section id is neither priced here nor accounted for.

    ``SECTION_PROVIDERS`` is the list of everything a request can carry. A new
    id joining it is a new thing sent to the model, and the only two honest
    answers are "this module works out what it costs" or "it is charged here
    instead, for this reason". Silence is the third answer, and it is the one
    that lowers a bill without anyone deciding to.

    Raises:
        ValueError: naming the unclassified ids.
    """
    known = set(SECTION_PROVIDERS)
    classified = SECTIONS_THIS_MODULE_PRICES | set(SECTIONS_PRICED_SOMEWHERE_ELSE)
    unclassified = sorted(known - classified)
    if unclassified:
        raise ValueError(
            "core/prompt_sections.py can send "
            f"{', '.join(unclassified)}, and core/first_request_sections.py "
            "neither works out what that costs nor says where it is charged "
            "instead. Pricing it at nothing would lower the ceiling by "
            "whatever it really sends"
        )
    stray = sorted(classified - known)
    if stray:
        raise ValueError(
            f"core/first_request_sections.py accounts for {', '.join(stray)}, "
            "which core/prompt_sections.py cannot send. A section that is not "
            "sent is being budgeted for, so one of the two is out of date"
        )


@dataclass(frozen=True)
class FirstRequestSectionBudget:
    """What the declared sections add to one first request, and what stayed out.

    Attributes:
        per_section: section id -> characters it adds, separator included.
        characters: the total, measured in one pass and checked against the sum.
        silent: section id -> why it adds nothing under these settings.
    """

    per_section: Mapping[str, int]
    characters: int
    silent: Mapping[str, str]


_TASK_STAND_IN = "t"


def widest_reference_file_names(registry: SkillsRegistry) -> List[str]:
    """One file name per extension anything in the first request reacts to.

    Read from ``EXT_PACKAGES`` and from the committed skill packs' own
    ``file_extensions``, so an extension added to either moves this.
    """
    extensions = set(EXT_PACKAGES)
    for skill in registry.skills.values():
        extensions.update(skill.file_extensions)
    return [f"w{index}{ext}" for index, ext in enumerate(sorted(extensions))]


def widest_task_words(registry: SkillsRegistry) -> str:
    """Every word the first request's builders can match, in one string.

    Read from ``KEYWORD_PACKAGES``, from
    :func:`core.deliverable_contract.detection_vocabulary`, and from the
    committed skill packs' own ``keywords``. Phrases stay contiguous, and the
    builders match on word boundaries, so joining them with spaces is enough for
    every one of them to be found.
    """
    words: List[str] = list(KEYWORD_PACKAGES)
    words.extend(detection_vocabulary())
    for skill in registry.skills.values():
        words.extend(skill.keywords)
    ordered: List[str] = []
    seen: set[str] = set()
    for word in words:
        if word not in seen:
            seen.add(word)
            ordered.append(word)
    return " ".join(ordered)


def _context(
    *,
    registry: SkillsRegistry,
    skills: Sequence[Any],
    manifest: Any,
    contract: Any,
) -> SectionContext:
    """A first-request context with no reference files and no earlier attempt.

    The reference files are left out because their sections are charged per
    file elsewhere; the reflection because no first request has one.
    """
    return SectionContext(
        task_prompt=_TASK_STAND_IN,
        ref_files=[],
        skills=list(skills),
        manifest=manifest,
        contract=contract,
        reflection=None,
        registry=registry,
        perception_text=None,
        host_reference_access=True,
    )


def first_request_section_budget(
    sections: Iterable[str],
    *,
    prompt_name: str,
    max_skills: int,
    contract_config: Optional[Mapping[str, Any]] = None,
    prompts_dir: Optional[str | Path] = None,
    skills_dir: Optional[str | Path] = None,
) -> FirstRequestSectionBudget:
    """Work out what the sections named add to one first request.

    Args:
        sections: prompt section ids, as the runner class declares them.
        prompt_name: the prompt spec the run place sends; its ``sections:``
            list decides the order and which of them are switched off.
        max_skills: what the settings ask ``SkillsRegistry.select`` for. The
            executor's own default is 5, so a settings file that leaves it out
            has the skills manual **on**, and the caller must pass 5 rather
            than nothing.
        contract_config: ``execution.sandbox.contract`` from the settings, which
            can pin the expected types and add a note.
        prompts_dir: overrides the committed prompts directory (tests only).
        skills_dir: overrides the committed skills directory (tests only).

    Raises:
        KeyError: for a section this module does not price. Guessing zero for
                  one would quietly lower a cost ceiling.
        ValueError: when an input needed to measure could not be read — a
                  missing skills directory while the settings ask for skills,
                  or a layout whose parts do not add up to its whole.
    """
    unknown = sorted(set(sections) - SECTIONS_THIS_MODULE_PRICES)
    if unknown:
        raise KeyError(unknown[0])

    wanted = sorted(set(sections))
    if not wanted:
        # A run place that declares it adds none of these adds nothing, and
        # nothing is what it is charged. This is not the same as a run place
        # that declares nothing at all: that one has no claim to measure, and
        # the caller refuses it rather than reaching this function.
        return FirstRequestSectionBudget(per_section={}, characters=0, silent={})

    prompt_data = load_prompt(
        prompt_name, prompts_dir=Path(prompts_dir) if prompts_dir else None
    )
    section_order: List[Any] = list(prompt_data.get("sections") or DEFAULT_SECTIONS)
    enabled = set(enabled_section_ids(section_order))

    registry = SkillsRegistry(skills_dir)
    if not registry.skills:
        # ``SkillsRegistry._load`` returns quietly when its directory is not
        # there, so an empty registry cannot be told apart from a directory
        # that was never read. Either way the packs' own extensions and
        # keywords are missing from the widest wording below, and every
        # fragment measured from that wording comes out at most as long as it
        # should be — the one direction a ceiling may not be wrong in. So it is
        # refused rather than measured against whatever did load.
        raise ValueError(
            f"no skill pack was read from {registry.skills_dir}, and the "
            "widest wording a first request can be built from is partly read "
            "from the packs' own file_extensions and keywords. Measuring "
            "without them would hand back a figure at most as large as the "
            "real one, so it is refused until the directory can be read"
        )
    reference_names = widest_reference_file_names(registry)
    task_words = widest_task_words(registry)

    per_section: Dict[str, int] = {}
    silent: Dict[str, str] = {}

    # The widest each fragment can be built, through the builders a real
    # attempt uses. Nothing below is a length; every one of them is rendered.
    widest_contract = infer_deliverable_contract(
        task_words, reference_names, dict(contract_config or {})
    )
    # An empty base image is deliberate, not a failed read: the hint's second
    # line names the packages the image does not carry, so it is longest when
    # it names every one of them.
    widest_manifest = resolve(
        reference_files=reference_names, task_text=task_words, base_packages=set()
    )
    empty_manifest = resolve(reference_files=[], task_text="", base_packages=set())

    widest_skills: List[Any] = []
    if max_skills > 0:
        widest_skills = registry.select(
            reference_names, task_words, max_skills=max_skills
        )

    populated: Dict[str, Dict[str, Any]] = {
        "contract": {"contract": widest_contract},
        "deps_hint": {"manifest": widest_manifest},
        "skills_manual": {"skills": widest_skills},
    }
    bare: Dict[str, Any] = {
        "skills": [],
        "manifest": empty_manifest,
        "contract": None,
    }

    baseline = len(assemble_sections(section_order, _context(registry=registry, **bare)))

    # ``wanted`` was fixed before anything was read, so ``sections`` is walked
    # exactly once and may be a generator.
    for section in wanted:
        if section not in enabled:
            silent[section] = (
                f"the prompt spec {prompt_name} does not ask for it, so "
                "assemble_sections never lays it out"
            )
            continue
        if section == "skills_manual" and max_skills <= 0:
            silent[section] = (
                f"the settings ask for {max_skills} skills, so "
                "SkillsRegistry.select returns none and render_manual returns "
                "nothing. Raising max_skills puts it back"
            )
            continue
        one = dict(bare)
        one.update(populated[section])
        added = (
            len(assemble_sections(section_order, _context(registry=registry, **one)))
            - baseline
        )
        if added <= 0:
            silent[section] = (
                "its builders produce nothing from the widest wording the "
                "committed tables hold"
            )
            continue
        per_section[section] = added

    together = dict(bare)
    for section in per_section:
        together.update(populated[section])
    measured = (
        len(assemble_sections(section_order, _context(registry=registry, **together)))
        - baseline
    )
    if measured != sum(per_section.values()):
        raise ValueError(
            "the first-request sections measured one at a time come to "
            f"{sum(per_section.values()):,} characters and measured together to "
            f"{measured:,}. core/prompt_sections.py has been given a section "
            "whose length depends on which others are present, so neither "
            "figure can be trusted as the bill"
        )

    return FirstRequestSectionBudget(
        per_section=dict(per_section),
        characters=measured,
        silent=dict(silent),
    )
