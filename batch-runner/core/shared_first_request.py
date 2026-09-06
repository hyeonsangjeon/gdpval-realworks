"""One first request, built once, sent by every run place that opts in.

Why this exists
---------------
``comparison: same_generated_code_rerun`` says the run place is the only thing
that differs, and reads any difference in the answers as a difference the run
place made. Until this module, that was not true of the wording. Each of the
three run places sent the prompt file its own runner class declares — three
differently named files, 3,533 / 3,867 / 7,307 characters — because
``core/executor.py`` never had a ``prompt_name`` to pass and every runner fell
back to its own ``DEFAULT_PROMPT``. The container added three more sections on
top from ``_augment_prompt``.

The fix is not to rename the comparison. It is to give the three one wording and
one section list, defined here once, and to check at the wire that what left the
process really was the same.

What this does **not** claim
----------------------------
Equal wording is not a pure run-place comparison, and this module says so out
loud rather than letting a caller assume it. :data:`UNCONTROLLED_DIFFERENCES`
names what stays different after the text is equal — a different API family, a
tool declaration only one place sends, a different way the reference files
arrive, and isolation that is not weakened to make strings match. A caller that
wants to publish a run-place effect has to read that list and say what it did
about each entry. :func:`residual_differences_for` returns the entries that
apply to a given set of run places, so a report states them instead of implying
they were handled.

Opting in
---------
Off unless an experiment sets ``execution.shared_first_request: true``. Every
experiment that does not set it builds its first request exactly as before,
through the code path it always used, from the prompt file its runner always
loaded. ``tests/test_shared_first_request_defaults_unchanged.py`` holds that.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence

from core.prompt_loader import load_prompt
from core.prompt_sections import SECTION_PROVIDERS, SectionContext, assemble_sections


#: The one committed prompt file every opted-in run place loads. Named rather
#: than derived, because a name that is looked up the same way from three call
#: sites is the thing that makes the three requests one request.
SHARED_PROMPT_NAME = "execution_envelope_shared"


#: Section ids the shared list is allowed to name.
#:
#: The rule is not "these are the useful ones". It is that each of these reads
#: only what all three run places have: the task's own words, and the reference
#: files as they sit on the host before the run place is chosen. The four left
#: out — ``skills_manual``, ``deps_hint``, ``contract``, ``reflection`` — are
#: each built from something only the container has, so naming one would put a
#: block in the container's request that the other two places cannot produce.
#: That is the asymmetry this module exists to remove, so it is refused at the
#: point where it would be reintroduced rather than found later in a result.
SECTIONS_EVERY_RUN_PLACE_CAN_BUILD = frozenset(
    {
        "file_structure",
        "task",
        "previews",
        "available_files_any_run_place",
    }
)


@dataclass(frozen=True)
class UncontrolledDifference:
    """Something that stays different after the wording is made the same."""

    what: str
    why_it_stays: str
    what_it_could_do_to_a_result: str
    run_places: tuple[str, ...]


#: What equal wording does not equalise.
#:
#: Written down because a comparison that has been made honest about one thing
#: is the easiest place to start assuming it is honest about everything. Each
#: entry names the run places it applies to, so a run of two places that share
#: an API family is not charged for a difference that is not between them.
UNCONTROLLED_DIFFERENCES: tuple[UncontrolledDifference, ...] = (
    UncontrolledDifference(
        what="the API the request is sent on",
        why_it_stays=(
            "the host process and the container send chat completions, with a "
            "system message and a user message; the Azure code interpreter "
            "sends the Responses API, with instructions and an input. This "
            "module makes the two texts identical, and nothing it can do makes "
            "the two envelopes identical, because they are different products"
        ),
        what_it_could_do_to_a_result=(
            "the two APIs may weight a standing instruction differently, so a "
            "gap between Azure and the other two is a gap between the two "
            "products as much as between the two run places"
        ),
        run_places=("azure_code_interpreter",),
    ),
    UncontrolledDifference(
        what="a tool declaration only one run place sends",
        why_it_stays=(
            "the Azure call carries tools=[{'type': 'code_interpreter'}], which "
            "is how that run place runs code at all. The provider turns that "
            "into instructions of its own that are never shown to the caller, "
            "so their wording cannot be read, matched, or measured from here"
        ),
        what_it_could_do_to_a_result=(
            "Azure's model is told how to run code by text this repository "
            "cannot see, while the other two are told by the shared prompt. The "
            "widths reported for Azure are therefore a floor, not a total"
        ),
        run_places=("azure_code_interpreter",),
    ),
    UncontrolledDifference(
        what="how the reference files arrive",
        why_it_stays=(
            "the host process and the container get the files copied onto a "
            "working directory they can open; Azure gets them uploaded to the "
            "provider and referenced by file id. The file bytes are the same "
            "and are checked to be the same; the way the model reaches them is "
            "the run place's own and cannot be swapped"
        ),
        what_it_could_do_to_a_result=(
            "a task that fails on reading its inputs may be failing on the "
            "delivery route rather than on the run place's ability to compute"
        ),
        run_places=("azure_code_interpreter",),
    ),
    UncontrolledDifference(
        what="isolation and the limits that come with it",
        why_it_stays=(
            "the container runs with no network, a memory cap and a cpu cap; "
            "the host process runs with the runner's own timeout and the "
            "server's own limits. These are not wording and are not relaxed to "
            "make two columns comparable — a run place stripped of its "
            "isolation is not the run place the comparison is about"
        ),
        what_it_could_do_to_a_result=(
            "a task needing more memory than the container's cap, or a network "
            "call, fails in the container and can succeed on the host. That is "
            "a real property of the run place and belongs in the result, but it "
            "is not the model performing differently"
        ),
        run_places=("docker_container", "host_python_process"),
    ),
    UncontrolledDifference(
        what="what happens to the answer after the model returns it",
        why_it_stays=(
            "the container checks its output against a deliverable contract and "
            "records the verdict; the other two places have no such check. The "
            "contract's text is kept out of the shared prompt, so it no longer "
            "reaches the model — but the check itself still runs, because "
            "removing it would change what the container is rather than what it "
            "is told"
        ),
        what_it_could_do_to_a_result=(
            "reported per-task detail is richer for the container. It does not "
            "change what the model was asked, and must not be read as the "
            "container having been guided"
        ),
        run_places=("docker_container",),
    ),
    UncontrolledDifference(
        what="the per-task time limit",
        why_it_stays=(
            "the host process and the container are both given the experiment "
            "file's timeout, and it is checked to be the same number in both. "
            "Azure's code interpreter is given none, because there is nowhere "
            "to give it one: the service creates and reclaims the container "
            "itself and documents that an idle one goes after about twenty "
            "minutes. Writing the experiment's 1200 into Azure's record would "
            "make the three columns agree on a limit that was never sent"
        ),
        what_it_could_do_to_a_result=(
            "a task slow enough to be cut off on the host or in the container "
            "may be allowed to finish by Azure, or may be cut off by the "
            "service at a moment this repository neither set nor can read. A "
            "timing difference between Azure and the other two is not evidence "
            "either way about the run place"
        ),
        run_places=("azure_code_interpreter",),
    ),
)


def residual_differences_for(
    run_places: Sequence[str],
) -> tuple[UncontrolledDifference, ...]:
    """The entries that apply to these run places, in the order written above.

    A comparison of the host process and the container alone does not carry the
    three Azure entries, and saying it does would be as wrong as saying it
    carries none. Nothing here is filtered by whether it is convenient.
    """
    wanted = set(run_places)
    return tuple(
        entry
        for entry in UNCONTROLLED_DIFFERENCES
        if wanted.intersection(entry.run_places)
    )


def shared_prompt_data(prompts_dir=None) -> dict:
    """The committed shared prompt file, loaded.

    Raises whatever :func:`core.prompt_loader.load_prompt` raises. A run place
    that cannot read the shared file must not fall back to its own — that is
    exactly the state this module was written to end — so nothing is caught.
    """
    return load_prompt(SHARED_PROMPT_NAME, prompts_dir=prompts_dir)


def shared_section_order(prompt_data: Optional[Mapping[str, Any]] = None) -> List[str]:
    """The section list every opted-in run place assembles, from the file.

    Read from ``sections:`` in the committed prompt rather than written here, so
    the file is the one place the list lives and a test that renders the file
    moves when the file does.

    Raises ``ValueError`` when the file names no sections, or names one that is
    not in :data:`SECTIONS_EVERY_RUN_PLACE_CAN_BUILD`. Both are refusals rather
    than repairs: a shared list quietly narrowed to what a place can manage is
    no longer shared, and a list carrying a container-only block is the original
    defect with a new name.
    """
    data = dict(prompt_data) if prompt_data is not None else shared_prompt_data()
    declared = data.get("sections")
    if not declared:
        raise ValueError(
            f"prompts/{SHARED_PROMPT_NAME}.yaml names no sections. The shared "
            "first request is the section list plus the wording; a file with "
            "only the wording does not define one"
        )
    order: List[str] = []
    for entry in declared:
        section_id = entry if isinstance(entry, str) else (entry or {}).get("id")
        if not isinstance(section_id, str):
            raise ValueError(
                f"prompts/{SHARED_PROMPT_NAME}.yaml has a sections entry that "
                f"names no id: {entry!r}"
            )
        if section_id not in SECTIONS_EVERY_RUN_PLACE_CAN_BUILD:
            raise ValueError(
                f"prompts/{SHARED_PROMPT_NAME}.yaml names section "
                f"{section_id!r}, which not every run place can build. The "
                "shared list may only name "
                f"{sorted(SECTIONS_EVERY_RUN_PLACE_CAN_BUILD)}; the rest are "
                "built from something only one run place has, and putting one "
                "in this list would give that place a block the others cannot "
                "produce"
            )
        if section_id not in SECTION_PROVIDERS:
            raise ValueError(
                f"prompts/{SHARED_PROMPT_NAME}.yaml names section "
                f"{section_id!r}, which no provider builds"
            )
        order.append(section_id)
    return order


def build_shared_task_text(
    *,
    task_prompt: str,
    reference_files: Optional[List[str]] = None,
    host_reference_access: bool = True,
    prompt_data: Optional[Mapping[str, Any]] = None,
) -> str:
    """The task text every opted-in run place puts in its first request.

    One function, three callers. The three run places differ in what they do
    with the text afterwards and in nothing about how it is made.

    ``host_reference_access`` is passed through rather than assumed: a run place
    that cannot open the reference files on the host must not have a structure
    summary or a preview built from files it cannot read. When it is False those
    two blocks are omitted by the providers themselves, and the omission is a
    difference a caller can see in the returned text rather than a silent one.
    """
    data = dict(prompt_data) if prompt_data is not None else shared_prompt_data()
    order = shared_section_order(data)
    context = SectionContext(
        task_prompt=task_prompt,
        ref_files=list(reference_files or []),
        # None, not an empty registry or an empty manifest. The shared list
        # cannot name a section that would read these — ``shared_section_order``
        # refuses one — so a None here turns a list that somehow did into an
        # error at the moment it is used, rather than into a quietly empty
        # block that looks like agreement.
        skills=None,
        manifest=None,
        contract=None,
        reflection=None,
        registry=None,
        perception_text=None,
        host_reference_access=host_reference_access,
    )
    return assemble_sections(order, context)


def first_request_fingerprint(system_message: str, user_prompt: str) -> str:
    """A short digest of the two texts a run place really sent.

    Recorded per run place so the claim "the three were asked the same thing" is
    checkable afterwards from the run's own record, rather than only before the
    run by a check that reads the same files the run reads. The separator is a
    byte no rendered prompt produces, so two different splits of the same
    concatenation cannot collide.
    """
    joined = f"{system_message}\x00{user_prompt}".encode("utf-8")
    return hashlib.sha256(joined).hexdigest()[:16]
