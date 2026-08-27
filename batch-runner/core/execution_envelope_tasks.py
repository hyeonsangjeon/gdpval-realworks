"""Pick the fixed task list for the run-place comparison, before any spending.

The comparison asks whether one GPT model scores differently when the place it
runs in changes. That question is only answerable if the task list is settled
*before* anybody sees a score. This module settles it.

Two properties matter more than anything else here:

**The choice cannot follow the scores.** Everything this module reads comes from
a catalogue built from the benchmark dataset itself: the task number, the
industry, the job, the file types the human expert handed in, and how many
reference files the task ships with. :func:`check_catalog_carries_no_scores`
holds that shape to the file: every field name in it, at any depth, must be one
the schema below describes, and no number may be a fraction and no value true or
false, because every number the schema holds is a count. So a result cannot
arrive as a new field under any name, and cannot take over an existing one. What
that cannot prove is a score hidden inside text a field is allowed to hold — an
occupation written as ``"Nurse (0.87)"`` — and it is worth saying so rather than
claiming the file is proven clean.

**The choice can be re-derived by anyone.** The catalogue records which dataset
revision it came from and the content fingerprint of that revision's data file.
The catalogue has a fingerprint of its own. Re-running the selection on the same
catalogue always returns the same task numbers in the same order.

**The counts have to be capable of being true.** The catalogue's numbers are what
the cost ceiling is worked out from, and the way they go wrong is not by being
absurd — it is by being zero. :func:`catalog_number_problems` refuses the zeros
that cannot be true: a task nobody marks, and a task with no wording. It does not
refuse a task shipping no reference files, because 95 of the 220 really ship
none. Only the direction that makes the work look smaller is refused; a count
that is too large would only overstate what a run might cost.

**The inputs are checked by reading them.** :func:`verify_input_file_versions`
hashes each file the chosen tasks ship with and compares all 64 characters of
the result against what the plan wrote down. It only ever reads a copy already
on this machine; it never downloads anything. When no copy is there, that is
reported as a file whose fingerprint *could not be checked*, which is not the
same answer as a file that matched — see :data:`INPUT_FILE_READ`,
:data:`INPUT_FILE_FOLDER_NAME_ONLY` and :data:`INPUT_FILE_NOT_CHECKED`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

# ── Where the committed catalogue lives ────────────────────────────────────

CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "execution_envelope"
    / "gdpval_task_catalog.json"
)

CATALOG_SCHEMA_VERSION = "gdpval-task-catalog-v2"

# The benchmark dataset revision every part of this comparison is pinned to.
# The same revision already backs this repository's published grades, so a
# comparison run against it can be lined up with work that came before.
DATASET_REPO_ID = "openai/gdpval"
DATASET_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"

FULL_RUN_TASK_COUNT = 220
TRIAL_RUN_TASK_COUNT = 30
ADVANCE_CHECK_TASK_COUNT = 5

# ── Which deliverable format a task asks for ───────────────────────────────
# Read from the file types of the human expert's own answer, which the dataset
# ships alongside the task. Nothing here looks at what a model produced.

FORMAT_SPREADSHEET = "spreadsheet"
FORMAT_DOCUMENT = "document"
FORMAT_PRESENTATION = "presentation"
FORMAT_IMAGE = "image"
FORMAT_TEXT_ONLY = "text_only"

DELIVERABLE_FORMAT_EXTENSIONS: Mapping[str, frozenset[str]] = {
    FORMAT_SPREADSHEET: frozenset({".xlsx", ".xlsm", ".xls", ".csv"}),
    FORMAT_DOCUMENT: frozenset({".docx", ".doc", ".pdf"}),
    FORMAT_PRESENTATION: frozenset({".pptx", ".ppt"}),
    FORMAT_IMAGE: frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".tif", ".tiff"}),
}

# The order the five slots are filled in. Fixed here, in code, so it cannot be
# re-ordered later to reach a different set of tasks.
ADVANCE_CHECK_FORMAT_ORDER: tuple[str, ...] = (
    FORMAT_SPREADSHEET,
    FORMAT_DOCUMENT,
    FORMAT_PRESENTATION,
    FORMAT_IMAGE,
    FORMAT_TEXT_ONLY,
)

# Keys the catalogue is allowed to carry that hold no data — only prose that
# says where the file came from and how to read it. Every other allowed name is
# derived from the schema below rather than written here, so a field added to
# the schema is allowed without anyone editing this, and a field added to the
# *file* is refused without anyone remembering to.
_PROSE_ONLY_CATALOG_KEYS = frozenset(
    {
        "written_by",
        "holds_no_scores",
        "reference_file_path_note",
    }
)


@dataclass(frozen=True)
class CatalogTask:
    """One benchmark task, described without any reference to how it scored."""

    task_id: str
    sector: str
    occupation: str
    deliverable_file_extensions: tuple[str, ...]
    reference_file_count: int
    reference_file_extensions: tuple[str, ...]
    reference_file_paths: tuple[str, ...]
    prompt_sha256: str
    prompt_character_count: int
    rubric_item_count: int
    widest_rubric_criterion_characters: int
    """How long this task's longest scoring line is, in characters.

    Every marking call carries the scoring line it is judging, so this is part
    of what a marking call costs and not only a description of the task. It is
    recorded here — a length, never the wording itself — because the advance
    check used to print a marking total it called the largest possible bill and
    say in the same breath that this part of it was capped by nothing, and both
    cannot be true at once.
    """

    @property
    def deliverable_formats(self) -> tuple[str, ...]:
        """Every format family the expert's own answer files belong to."""
        present = set(self.deliverable_file_extensions)
        found = [
            name
            for name, extensions in DELIVERABLE_FORMAT_EXTENSIONS.items()
            if present & extensions
        ]
        if not self.deliverable_file_extensions:
            found.append(FORMAT_TEXT_ONLY)
        return tuple(sorted(found))

    def only_format_is(self, format_name: str) -> bool:
        """True when every answer file belongs to this one format family."""
        if format_name == FORMAT_TEXT_ONLY:
            return not self.deliverable_file_extensions
        extensions = DELIVERABLE_FORMAT_EXTENSIONS[format_name]
        return bool(self.deliverable_file_extensions) and set(
            self.deliverable_file_extensions
        ) <= set(extensions)

    def any_format_is(self, format_name: str) -> bool:
        """True when at least one answer file belongs to this format family."""
        if format_name == FORMAT_TEXT_ONLY:
            return not self.deliverable_file_extensions
        return bool(
            set(self.deliverable_file_extensions)
            & set(DELIVERABLE_FORMAT_EXTENSIONS[format_name])
        )


@dataclass(frozen=True)
class TaskCatalog:
    """Every benchmark task, plus where the description came from."""

    schema_version: str
    dataset_repo_id: str
    dataset_revision: str
    dataset_file_sha256: str
    tasks: tuple[CatalogTask, ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "TaskCatalog":
        missing = sorted(
            {
                "schema_version",
                "dataset_repo_id",
                "dataset_revision",
                "dataset_file_sha256",
                "tasks",
            }
            - set(raw)
        )
        if missing:
            raise ValueError(
                "the task catalogue is missing: " + ", ".join(missing)
            )
        if raw["schema_version"] != CATALOG_SCHEMA_VERSION:
            raise ValueError(
                "the task catalogue was written for "
                f"{raw['schema_version']!r}, but this code reads "
                f"{CATALOG_SCHEMA_VERSION!r}"
            )
        tasks = tuple(
            CatalogTask(
                task_id=str(entry["task_id"]),
                sector=str(entry["sector"]),
                occupation=str(entry["occupation"]),
                deliverable_file_extensions=tuple(
                    str(value) for value in entry["deliverable_file_extensions"]
                ),
                reference_file_count=int(entry["reference_file_count"]),
                reference_file_extensions=tuple(
                    str(value) for value in entry["reference_file_extensions"]
                ),
                reference_file_paths=tuple(
                    str(value) for value in entry["reference_file_paths"]
                ),
                prompt_sha256=str(entry["prompt_sha256"]),
                prompt_character_count=int(entry["prompt_character_count"]),
                rubric_item_count=int(entry["rubric_item_count"]),
                widest_rubric_criterion_characters=int(
                    entry["widest_rubric_criterion_characters"]
                ),
            )
            for entry in raw["tasks"]
        )
        return cls(
            schema_version=str(raw["schema_version"]),
            dataset_repo_id=str(raw["dataset_repo_id"]),
            dataset_revision=str(raw["dataset_revision"]),
            dataset_file_sha256=str(raw["dataset_file_sha256"]),
            tasks=tasks,
        )

    def by_task_id(self) -> dict[str, CatalogTask]:
        return {task.task_id: task for task in self.tasks}

    def sorted_tasks(self) -> tuple[CatalogTask, ...]:
        """Every task in one fixed order that no score can influence."""
        return tuple(sorted(self.tasks, key=lambda task: task.task_id))


def catalog_sha256(path: str | Path | None = None) -> str:
    """The content fingerprint of the committed catalogue file."""
    target = Path(path) if path is not None else CATALOG_PATH
    return hashlib.sha256(target.read_bytes()).hexdigest()


def load_task_catalog(path: str | Path | None = None) -> TaskCatalog:
    """Read the committed catalogue and check it describes the pinned dataset."""
    target = Path(path) if path is not None else CATALOG_PATH
    if not target.is_file():
        raise ValueError(f"the task catalogue is missing at {target}")
    raw = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("the task catalogue must hold a mapping at the top level")
    catalog = TaskCatalog.from_mapping(raw)
    if catalog.dataset_repo_id != DATASET_REPO_ID:
        raise ValueError(
            f"the task catalogue describes {catalog.dataset_repo_id!r}, but the "
            f"comparison is pinned to {DATASET_REPO_ID!r}"
        )
    if catalog.dataset_revision != DATASET_REVISION:
        raise ValueError(
            f"the task catalogue describes revision "
            f"{catalog.dataset_revision!r}, but the comparison is pinned to "
            f"{DATASET_REVISION!r}"
        )
    if len(catalog.tasks) != FULL_RUN_TASK_COUNT:
        raise ValueError(
            f"the task catalogue holds {len(catalog.tasks)} tasks but the "
            f"benchmark has {FULL_RUN_TASK_COUNT}"
        )
    seen = {task.task_id for task in catalog.tasks}
    if len(seen) != len(catalog.tasks):
        raise ValueError("the task catalogue lists the same task twice")
    return catalog


def _allowed_catalog_field_names() -> frozenset[str]:
    """Every field name the catalogue is allowed to carry.

    Read from the two dataclasses the loader actually fills, so the permitted
    set and the schema cannot drift apart. Adding a field to the schema permits
    it here; adding one to the file does not.
    """
    return frozenset(
        {field.name for field in dataclasses.fields(TaskCatalog)}
        | {field.name for field in dataclasses.fields(CatalogTask)}
        | _PROSE_ONLY_CATALOG_KEYS
    )


def check_catalog_carries_no_scores(
    path: str | Path | None = None,
) -> list[str]:
    """Refuse any field the schema does not describe, and any fraction.

    The selection must be defensible as having been made before results were
    seen, so the file it reads is not allowed to carry results at all.

    This asks the question the other way round from how it was first written.
    It used to hold a list of fourteen field names somebody had typed out —
    ``score``, ``verdict``, ``grade`` and eleven more — and report a leak only
    when one of those names appeared. That list was never compared against the
    names this repository's own grading pipeline writes. Injecting each of the
    forty-five result-carrying names found in the committed grade files, it
    caught eight and missed thirty-seven: a grade arriving as ``avg_score``,
    ``scores``, ``pass_rate``, ``graded_by`` or ``child_grades`` passed this
    check with a clean report.

    A list of names to refuse can only ever be as good as whoever last thought
    about it. The catalogue's shape, on the other hand, is small, fixed and
    already written down as two dataclasses, so the question worth asking is
    "is this field one the schema describes?" — which needs no foresight about
    what a future field might be called.

    Two things are checked, and it is worth being exact about which:

    - **Every field name, at any depth, must be one the schema describes.** A
      result cannot arrive as a new field under any name at all.
    - **No number may be fractional, and no value may be true or false.** Every
      number the schema holds is a count, and every score this repository
      produces is a fraction or a flag, so a result cannot arrive by taking
      over a field that is allowed.

    What this does *not* prove: a result smuggled into the text of a field that
    is allowed to hold text — an occupation written as ``"Nurse (0.87)"``, say
    — is not caught by either rule. Saying so plainly is the point; the sentence
    this function replaced claimed more than it did.
    """
    target = Path(path) if path is not None else CATALOG_PATH
    return catalog_score_problems(json.loads(target.read_text(encoding="utf-8")))


def catalog_score_problems(raw: Any) -> list[str]:
    """The same question, asked of a catalogue already in memory.

    Separate from :func:`check_catalog_carries_no_scores` so the builder can
    ask it about what it is *about* to write. A file that has already been
    committed is a worse place to find this out.
    """
    allowed = _allowed_catalog_field_names()
    unknown: set[str] = set()
    fractions: set[str] = set()

    def walk(node: Any, where: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                name = str(key)
                if name not in allowed:
                    unknown.add(name)
                walk(value, name)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, where)
        elif isinstance(node, (bool, float)):
            # True and False are named here on purpose. Python counts them as
            # whole numbers, so a pass/fail flag would otherwise slip through
            # as if it were one of the schema's counts.
            fractions.add(where)

    walk(raw, "the top level")
    problems: list[str] = []
    if unknown:
        problems.append(
            "the task catalogue carries fields the schema does not describe, "
            "so the task choice cannot be shown to predate the scores: "
            + ", ".join(sorted(unknown))
        )
    if fractions:
        problems.append(
            "the task catalogue holds a fraction or a true/false value, and "
            "every number in its schema is a count, so one of these fields is "
            "not holding what it should: " + ", ".join(sorted(fractions))
        )
    return problems


# ── Could the counts be true at all? ───────────────────────────────────────

#: The fingerprint of an empty piece of text. Worked out rather than typed: a
#: single wrong character in a 64-character constant would switch the rule that
#: uses it off, and nothing would say so.
SHA256_OF_NOTHING = hashlib.sha256(b"").hexdigest()

#: How many task numbers a refusal names before it starts counting instead. A
#: refusal listing all 220 does not get read; one naming none cannot be acted
#: on.
_TASKS_NAMED_IN_A_REFUSAL = 5


def _name_a_few(task_ids: Sequence[str]) -> str:
    ordered = sorted(str(value) for value in task_ids)
    shown = ordered[:_TASKS_NAMED_IN_A_REFUSAL]
    remaining = len(ordered) - len(shown)
    return ", ".join(shown) + (f" and {remaining} more" if remaining else "")


def catalog_number_problems(catalog: TaskCatalog) -> list[str]:
    """Refuse counts that cannot be true, in the direction that under-charges.

    Every number in the catalogue is read straight out of a dataset column, and
    the way those numbers go wrong is not by being absurd. It is by being zero.
    A column that gets renamed upstream, or arrives empty, or holds text that
    will not parse, used to become an empty list or an empty string, and an
    empty value is not read further down as *unknown*. It is read as a real,
    small measurement, and a real small measurement is exactly what nothing
    complains about.

    What that costs is worth writing down. Set every ``rubric_item_count`` in
    the committed catalogue to zero and the ceiling for the planned comparison
    falls from 363.59 to 93.75 United States dollars — 269.84 of it gone, about
    three quarters — because marking is charged per scoring line and a task with
    no scoring lines is marked for free. Nothing noticed: the loader takes any
    whole number, :func:`catalog_score_problems` is asked a different question
    and answers it correctly, and the builder's ``--check`` cannot help because
    it rebuilds with the same code and so reproduces the same zeros.

    Four things are refused, and the reason each one cannot be true is a fact
    about this benchmark rather than a preference:

    - **A task nobody marks.** Every task in the benchmark is marked against a
      written rubric; the committed catalogue runs from 14 scoring lines to 137.
      Zero says marking that task costs nothing.
    - **A task with no wording.** The wording is the task. The committed
      catalogue runs from 617 characters to 6,618. This also refuses a wording
      fingerprint that is the fingerprint of nothing, which catches a length
      corrected by hand without the fingerprint being corrected with it.
    - **A task whose longest scoring line is empty.** Every marking call carries
      the scoring line it is judging, so a zero prices that wording at nothing.
      No scoring line in this benchmark is blank: across all 10,453 of them the
      per-task longest runs from 94 characters to 1,203.
    - **A reference-file count that disagrees with the paths listed beside
      it.** Both are written from the same list, so they cannot honestly
      differ. This one is here because a count of zero reference files is
      entirely ordinary — 95 of the 220 tasks ship none — so the zero rule the
      other two use would be wrong for this column, and without this it would
      have no guard at all.

    What this does *not* do: it catches a count of zero, not a count that is
    merely too small. If a rubric column were replaced by one holding a single
    scoring line per task, every number here would be positive and this would
    report nothing. The builder is the place that problem has to be caught, and
    :mod:`scripts.build_gdpval_task_catalog` refuses a missing column by name
    rather than filling it in.
    """
    problems: list[str] = []

    unmarked = [task.task_id for task in catalog.tasks if task.rubric_item_count <= 0]
    if unmarked:
        problems.append(
            "the task catalogue says these tasks have no marking rubric at "
            "all, and marking is charged per scoring line, so the cost "
            "ceiling would leave out what it costs to mark them: "
            + _name_a_few(unmarked)
        )

    wordless = [
        task.task_id
        for task in catalog.tasks
        if task.prompt_character_count <= 0
        or task.prompt_sha256.strip().lower() == SHA256_OF_NOTHING
    ]
    if wordless:
        problems.append(
            "the task catalogue says these tasks have no wording, which no "
            "task in this benchmark does, so the column it was read from was "
            "probably renamed or empty rather than the tasks being blank: "
            + _name_a_few(wordless)
        )

    unworded_scoring_lines = [
        task.task_id
        for task in catalog.tasks
        if task.widest_rubric_criterion_characters <= 0
    ]
    if unworded_scoring_lines:
        problems.append(
            "the task catalogue says the longest scoring line of these tasks "
            "is empty, and every marking call carries the scoring line it is "
            "judging, so the cost ceiling would price that wording at nothing: "
            + _name_a_few(unworded_scoring_lines)
        )

    miscounted = [
        task.task_id
        for task in catalog.tasks
        if task.reference_file_count != len(task.reference_file_paths)
    ]
    if miscounted:
        problems.append(
            "the task catalogue counts a different number of reference files "
            "than it lists paths for, and both are written from the same "
            "list, so one of the two is wrong: " + _name_a_few(miscounted)
        )

    return problems


def widest_scoring_line_characters(catalog: TaskCatalog) -> int:
    """The longest scoring line anywhere in the catalogue, in characters.

    This is the figure the marking half of the cost ceiling needs. Every
    marking call carries the scoring line it is judging, so a call about the
    widest line in the benchmark is the largest a call's opening can be, and a
    figure that does not reach it is not a ceiling.

    It is taken across the whole catalogue rather than across whichever tasks a
    plan happens to select. A plan running five tasks is then held to the width
    of all 220, which overstates that plan's opening slightly — and overstating
    is the direction a ceiling is allowed to be wrong in. The alternative,
    measuring only the selected tasks, would make the demanded figure move
    whenever the selection moved, which is exactly the sort of quiet change
    that has hidden an understatement before.

    Raises :class:`ValueError` on an empty catalogue rather than returning
    zero, because zero here reads as marking that costs nothing.
    """
    if not catalog.tasks:
        raise ValueError(
            "the task catalogue holds no tasks, so the widest scoring line "
            "cannot be measured — and zero would be read as marking that "
            "costs nothing"
        )
    return max(task.widest_rubric_criterion_characters for task in catalog.tasks)


@dataclass(frozen=True)
class AdvanceCheckSelection:
    """The five tasks for the advance check, and why each one was picked."""

    task_ids: tuple[str, ...]
    reasons: tuple[tuple[str, str, str], ...]
    catalog_sha256: str
    dataset_revision: str
    dataset_file_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_ids": list(self.task_ids),
            "reasons": [
                {
                    "deliverable_format": deliverable_format,
                    "task_id": task_id,
                    "why_this_task": why,
                }
                for deliverable_format, task_id, why in self.reasons
            ],
            "catalog_sha256": self.catalog_sha256,
            "dataset_revision": self.dataset_revision,
            "dataset_file_sha256": self.dataset_file_sha256,
        }


def select_advance_check_tasks(
    catalog: TaskCatalog, *, catalog_fingerprint: str | None = None
) -> AdvanceCheckSelection:
    """Choose the five advance-check tasks by a rule fixed ahead of any run.

    The written specification asks for five tasks whose deliverable formats
    differ, so a format-specific problem shows up straight away. The rule is:

    1. Work through the five formats in the order set by
       :data:`ADVANCE_CHECK_FORMAT_ORDER`.
    2. For each format, prefer a task whose answer files *all* belong to that
       format. Only if the benchmark contains no such task, accept a task where
       at least one answer file does. That fallback is needed because no task in
       this benchmark hands in a picture on its own; the two that hand in a
       picture at all also hand in a document.
    3. Among the candidates, take the smallest task number. Task numbers are
       fixed identifiers in the dataset and carry no result.
    4. Never pick a task already taken, and never pick a second task from a job
       already represented, so the five cover five different jobs.
    """
    remaining_ids: set[str] = set()
    used_occupations: set[str] = set()
    chosen: list[str] = []
    reasons: list[tuple[str, str, str]] = []
    ordered = catalog.sorted_tasks()

    for deliverable_format in ADVANCE_CHECK_FORMAT_ORDER:
        available = [
            task
            for task in ordered
            if task.task_id not in remaining_ids
            and task.occupation not in used_occupations
        ]
        exact = [
            task for task in available if task.only_format_is(deliverable_format)
        ]
        partial = [
            task for task in available if task.any_format_is(deliverable_format)
        ]
        pool = exact or partial
        if not pool:
            raise ValueError(
                "the benchmark holds no task that hands in a "
                f"{deliverable_format} once the tasks already chosen and the "
                "jobs already represented are set aside"
            )
        pick = pool[0]
        remaining_ids.add(pick.task_id)
        used_occupations.add(pick.occupation)
        chosen.append(pick.task_id)
        handed_in = (
            "a text answer with no file"
            if not pick.deliverable_file_extensions
            else "answer files ending " + ", ".join(pick.deliverable_file_extensions)
        )
        exactness = (
            "every answer file is this format"
            if exact
            else "the benchmark has no task that hands in only this format, so "
            "the smallest-numbered task that hands in one at all was taken"
        )
        reasons.append(
            (
                deliverable_format,
                pick.task_id,
                f"{exactness}; the expert handed in {handed_in}; "
                f"job: {pick.occupation}; industry: {pick.sector}",
            )
        )

    return AdvanceCheckSelection(
        task_ids=tuple(chosen),
        reasons=tuple(reasons),
        catalog_sha256=catalog_fingerprint or catalog_sha256(),
        dataset_revision=catalog.dataset_revision,
        dataset_file_sha256=catalog.dataset_file_sha256,
    )


def select_trial_run_tasks(catalog: TaskCatalog) -> tuple[str, ...]:
    """Choose the thirty tasks for the trial stage, keeping industry shares.

    The written specification asks that the thirty keep the industry mix of the
    full benchmark. Rather than draw at random and then have to remember a seed,
    this walks the industries from the largest share down and takes the
    smallest-numbered task not yet taken from each in turn, until thirty are
    held. The result depends only on the catalogue, so it can be re-derived.
    """
    ordered = catalog.sorted_tasks()
    by_sector: dict[str, list[CatalogTask]] = {}
    for task in ordered:
        by_sector.setdefault(task.sector, []).append(task)

    # Largest industry first, ties broken by name, so the order never wobbles.
    sector_order = sorted(
        by_sector, key=lambda name: (-len(by_sector[name]), name)
    )
    chosen: list[str] = []
    round_index = 0
    while len(chosen) < TRIAL_RUN_TASK_COUNT:
        progressed = False
        for sector in sector_order:
            if len(chosen) >= TRIAL_RUN_TASK_COUNT:
                break
            tasks = by_sector[sector]
            if round_index < len(tasks):
                chosen.append(tasks[round_index].task_id)
                progressed = True
        if not progressed:
            raise ValueError(
                "the benchmark does not hold enough tasks to fill the trial "
                "stage"
            )
        round_index += 1
    return tuple(chosen)


def full_run_tasks(catalog: TaskCatalog) -> tuple[str, ...]:
    """Every task, in the one fixed order used for the full comparison."""
    return tuple(task.task_id for task in catalog.sorted_tasks())


def selection_matches(
    task_ids: Sequence[str], selection: AdvanceCheckSelection
) -> list[str]:
    """Report any difference between a written task list and the rule's answer."""
    written = tuple(str(value) for value in task_ids)
    if written == selection.task_ids:
        return []
    return [
        "the advance-check task list written down does not match the list the "
        "fixed selection rule produces; written: "
        + ", ".join(written)
        + "; rule: "
        + ", ".join(selection.task_ids)
    ]


# Each reference file in this dataset lives in a folder named after the first
# 32 hexadecimal characters of that file's SHA-256 fingerprint. That folder name
# is worth something when no copy of the file can be read — but it is only half
# the fingerprint, so on its own it leaves the other half unchecked.
REFERENCE_PATH_FINGERPRINT_LENGTH = 32

# The one data file the pinned dataset revision ships its tasks in.
DATASET_DATA_FILE = "data/train-00000-of-00001.parquet"

# How thoroughly one written fingerprint was checked.
#: The real file was read and all 64 characters agreed.
INPUT_FILE_READ = "read the file"
#: No copy of the file was reachable, so only the 32 characters the folder name
#: repeats could be compared. The other 32 stand unchecked.
INPUT_FILE_FOLDER_NAME_ONLY = "folder name only"
#: Nothing was compared. This is not the same answer as "it matched".
INPUT_FILE_NOT_CHECKED = "not checked"

# How to get the missing bytes, free and once. Named in the report so a person
# reading it knows what to do rather than being told only that they failed.
HOW_TO_GET_THE_FILES = (
    "download the pinned revision once with "
    f"`huggingface-cli download {DATASET_REPO_ID} --repo-type dataset "
    f"--revision {DATASET_REVISION}` (no charge), or point the check at a copy "
    "you already have with --dataset-root"
)


def sha256_of_file(path: Path) -> str:
    """The SHA-256 fingerprint of a file's contents, read in blocks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class InputFileCheck:
    """What was actually done about one written fingerprint."""

    path: str
    written: str
    state: str
    characters_compared: int
    note: str = ""

    @property
    def fully_checked(self) -> bool:
        return self.state == INPUT_FILE_READ

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "written": self.written,
            "state": self.state,
            "characters_compared": self.characters_compared,
            "note": self.note,
        }


@dataclass(frozen=True)
class InputFileVerification:
    """The outcome of checking every written input fingerprint."""

    checks: tuple[InputFileCheck, ...]
    problems: tuple[str, ...]
    """Ways the written fingerprints and the real files disagree.

    A defect in the plan. It says the same thing on every machine, because it
    is about what was written down, not about what happens to be lying around.
    """
    missing_copies: tuple[str, ...] = ()
    """Files no copy of which is on this machine, so nothing could be read.

    Kept apart from :attr:`problems` because it answers a different question.
    A disagreement means the written value is wrong. A missing copy means this
    machine cannot tell whether it is right or wrong, which is neither a pass
    nor an accusation — and, unlike a disagreement, it can be cleared by
    fetching the pinned revision for nothing. Both still stop a run: an
    unchecked fingerprint is not evidence. Only this one changes from machine
    to machine, which is why anything asserting "and nothing else is wrong"
    has to name it rather than trip over it.
    """

    @property
    def all_notes(self) -> tuple[str, ...]:
        """Every reason the written fingerprints are not proven right."""
        return self.problems + self.missing_copies

    @property
    def fully_checked(self) -> tuple[InputFileCheck, ...]:
        return tuple(check for check in self.checks if check.fully_checked)

    @property
    def not_fully_checked(self) -> tuple[InputFileCheck, ...]:
        return tuple(check for check in self.checks if not check.fully_checked)

    @property
    def everything_was_read(self) -> bool:
        return bool(self.checks) and not self.not_fully_checked

    def as_dict(self) -> dict[str, Any]:
        return {
            "checks": [check.as_dict() for check in self.checks],
            "problems": list(self.problems),
            "missing_copies": list(self.missing_copies),
            "everything_was_read": self.everything_was_read,
        }


def reference_files_for(
    task_ids: Sequence[str], catalog: TaskCatalog
) -> tuple[str, ...]:
    """Every reference file the given tasks ship with, in one fixed order."""
    by_id = catalog.by_task_id()
    paths: list[str] = []
    for task_id in task_ids:
        task = by_id.get(str(task_id))
        if task is None:
            continue
        paths.extend(task.reference_file_paths)
    return tuple(sorted(set(paths)))


def _is_hexadecimal(value: str) -> bool:
    return bool(value) and all(
        character in "0123456789abcdef" for character in value
    )


def path_carries_its_own_fingerprint(path: str) -> bool:
    """Whether this file's own folder name is the start of its fingerprint.

    The dataset files under ``reference_files/`` are kept in a folder named
    after the first 32 characters of the file's fingerprint, so a copy found at
    such a path can only be the file the plan means. Paths of any other shape
    carry no such promise, and a copy found at one of them may belong to some
    other revision of the dataset.
    """
    folder = Path(path).parent.name.lower()
    return (
        len(folder) == REFERENCE_PATH_FINGERPRINT_LENGTH
        and _is_hexadecimal(folder)
    )


def _copy_in_the_download_cache(
    repo_id: str, revision: str, path: str
) -> Path | None:
    """A copy of ``path`` at exactly ``revision``, if one is already on disk.

    This never downloads. It asks the Hugging Face download cache whether that
    one revision of that one file has been fetched before, and returns where it
    was put if so.
    """
    try:
        from huggingface_hub import try_to_load_from_cache
    except Exception:  # pragma: no cover - the library is a normal dependency
        return None
    try:
        found = try_to_load_from_cache(
            repo_id=repo_id,
            filename=path,
            repo_type="dataset",
            revision=revision,
        )
    except Exception:  # pragma: no cover - a damaged cache must not stop us
        return None
    # A miss is None; a file the cache knows the revision does not contain is a
    # sentinel object rather than a path. Only a real string is a copy.
    if not isinstance(found, str):
        return None
    candidate = Path(found)
    return candidate if candidate.is_file() else None


def _locate_with_provenance(
    path: str,
    catalog: TaskCatalog,
    dataset_root: Path | None,
) -> tuple[Path, bool] | None:
    """A readable copy of one pinned input file, and whether it is pinned.

    Nothing is downloaded. A folder named by the person running the check is
    preferred over the download cache, because it was named on purpose. The
    second value says whether the copy is the pinned revision's *by
    construction*: true for a copy the download cache holds under that exact
    revision, and true for a file whose own path repeats the first half of its
    fingerprint. False for a copy found in a named folder that could hold any
    revision — such a copy is still worth reading, but a fingerprint that
    disagrees with it means something weaker.
    """
    if dataset_root is not None:
        candidate = Path(dataset_root) / path
        if candidate.is_file():
            return candidate, path_carries_its_own_fingerprint(path)
    cached = _copy_in_the_download_cache(
        catalog.dataset_repo_id, catalog.dataset_revision, path
    )
    if cached is not None:
        return cached, True
    return None


def locate_input_file(
    path: str,
    catalog: TaskCatalog,
    dataset_root: Path | None = None,
) -> Path | None:
    """Where a readable copy of one pinned input file is, or None."""
    found = _locate_with_provenance(path, catalog, dataset_root)
    return None if found is None else found[0]


def _check_one_written_fingerprint(
    path: str,
    written: str,
    catalog: TaskCatalog,
    dataset_root: Path | None,
    problems: list[str],
    missing_copies: list[str],
    *,
    what_it_is: str,
) -> InputFileCheck:
    fingerprint = written.strip().lower()
    if len(fingerprint) != 64 or not _is_hexadecimal(fingerprint):
        problems.append(
            f"the fingerprint written for {path} is not a SHA-256 value"
        )
        return InputFileCheck(
            path=path,
            written=written,
            state=INPUT_FILE_NOT_CHECKED,
            characters_compared=0,
            note="the written value is not a fingerprint at all",
        )

    found = _locate_with_provenance(path, catalog, dataset_root)
    if found is not None:
        copy, pinned_by_construction = found
        real = sha256_of_file(copy)
        if real != fingerprint and pinned_by_construction:
            problems.append(
                f"the fingerprint written for {path} is {fingerprint}, but the "
                f"copy of that {what_it_is} on this machine is {real}, so the "
                "written value describes some other file"
            )
        elif real != fingerprint:
            # The copy was found where somebody pointed, and nothing about that
            # folder promises which revision it holds. Saying which of the two
            # is wrong would be guessing; saying they disagree is not.
            problems.append(
                f"the fingerprint written for {path} is {fingerprint}, but the "
                f"copy in the folder this check was pointed at is {real}. "
                "Either that folder holds a different revision of the benchmark "
                "or the written fingerprint is wrong; either way the two do "
                "not describe the same file"
            )
        return InputFileCheck(
            path=path,
            written=fingerprint,
            state=INPUT_FILE_READ,
            characters_compared=64,
            note=f"read from {copy}",
        )

    folder = Path(path).parent.name.lower()
    if path_carries_its_own_fingerprint(path):
        if not fingerprint.startswith(folder):
            problems.append(
                f"the fingerprint written for {path} does not match the folder "
                "the dataset keeps that file in, so the written value describes "
                "some other file"
            )
        missing_copies.append(
            f"no copy of {path} at the pinned revision is on this machine, so "
            f"only {REFERENCE_PATH_FINGERPRINT_LENGTH} of its 64 fingerprint "
            "characters could be checked against the file itself; "
            f"{HOW_TO_GET_THE_FILES}"
        )
        return InputFileCheck(
            path=path,
            written=fingerprint,
            state=INPUT_FILE_FOLDER_NAME_ONLY,
            characters_compared=REFERENCE_PATH_FINGERPRINT_LENGTH,
            note="the folder name repeats the first half of the fingerprint",
        )

    missing_copies.append(
        f"no copy of {path} at the pinned revision is on this machine, and its "
        "path says nothing about its contents, so none of its 64 fingerprint "
        f"characters could be checked; {HOW_TO_GET_THE_FILES}"
    )
    return InputFileCheck(
        path=path,
        written=fingerprint,
        state=INPUT_FILE_NOT_CHECKED,
        characters_compared=0,
        note="nothing on this machine could be compared against",
    )


def verify_input_file_versions(
    input_file_versions: Mapping[str, str],
    task_ids: Sequence[str],
    catalog: TaskCatalog,
    dataset_root: Path | None = None,
) -> InputFileVerification:
    """Check the written input fingerprints against the real inputs.

    Three things are checked, none of which downloads anything:

    * every reference file the chosen tasks ship with has a fingerprint written
      down, and nothing extra is written down;
    * the dataset itself is pinned, to the revision and content the catalogue
      was built from;
    * each written fingerprint is compared, all 64 characters of it, against a
      copy of that exact file already on this machine.

    When no copy is reachable the fingerprint is **not** treated as correct. It
    is reported under :attr:`InputFileVerification.missing_copies`, saying how
    much of it went unchecked and how to get the missing bytes for nothing. A
    fingerprint nobody compared is not evidence, and a check that stayed quiet
    about it would be claiming to have done work it did not do. That answer is
    kept apart from a disagreement, which is a different finding: one says the
    plan is wrong, the other says this machine cannot tell.
    """
    problems: list[str] = []
    missing_copies: list[str] = []
    checks: list[InputFileCheck] = []
    expected = set(reference_files_for(task_ids, catalog))
    written = {str(key): str(value) for key, value in input_file_versions.items()}

    dataset_key = f"{catalog.dataset_repo_id}@{catalog.dataset_revision}"
    if dataset_key not in written:
        problems.append(
            "the input file versions do not pin the dataset itself; add an "
            f"entry for {dataset_key} holding the fingerprint of its data file"
        )
    elif written[dataset_key] != catalog.dataset_file_sha256:
        problems.append(
            f"the input file versions pin {dataset_key} to "
            f"{written[dataset_key]}, but the catalogue was built from "
            f"{catalog.dataset_file_sha256}"
        )
    else:
        checks.append(
            _check_one_written_fingerprint(
                DATASET_DATA_FILE,
                written[dataset_key],
                catalog,
                dataset_root,
                problems,
                missing_copies,
                what_it_is="dataset file",
            )
        )

    file_entries = {
        key: value for key, value in written.items() if key != dataset_key
    }
    missing = sorted(expected - set(file_entries))
    if missing:
        problems.append(
            "these reference files are used by the chosen tasks but have no "
            "written fingerprint: " + ", ".join(missing)
        )
    extra = sorted(set(file_entries) - expected)
    if extra:
        problems.append(
            "these files have a written fingerprint but are not used by any "
            "chosen task: " + ", ".join(extra)
        )
    for path in sorted(expected & set(file_entries)):
        checks.append(
            _check_one_written_fingerprint(
                path,
                file_entries[path],
                catalog,
                dataset_root,
                problems,
                missing_copies,
                what_it_is="file",
            )
        )

    return InputFileVerification(
        checks=tuple(checks),
        problems=tuple(problems),
        missing_copies=tuple(missing_copies),
    )


def check_input_file_versions(
    input_file_versions: Mapping[str, str],
    task_ids: Sequence[str],
    catalog: TaskCatalog,
    dataset_root: Path | None = None,
) -> list[str]:
    """Every reason the written input fingerprints are not proven right.

    Both kinds: the ones saying a written value and its file disagree, and the
    ones saying no copy of the file was here to compare against. A caller that
    needs to tell them apart wants :func:`verify_input_file_versions`.
    """
    return list(
        verify_input_file_versions(
            input_file_versions, task_ids, catalog, dataset_root
        ).all_notes
    )
