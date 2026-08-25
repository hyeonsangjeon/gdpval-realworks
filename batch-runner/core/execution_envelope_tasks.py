"""Pick the fixed task list for the run-place comparison, before any spending.

The comparison asks whether one GPT model scores differently when the place it
runs in changes. That question is only answerable if the task list is settled
*before* anybody sees a score. This module settles it.

Two properties matter more than anything else here:

**The choice cannot follow the scores.** Everything this module reads comes from
a catalogue built from the benchmark dataset itself: the task number, the
industry, the job, the file types the human expert handed in, and how many
reference files the task ships with. No score, no grade, and no verdict is
present, and :func:`check_catalog_carries_no_scores` proves it by looking.

**The choice can be re-derived by anyone.** The catalogue records which dataset
revision it came from and the content fingerprint of that revision's data file.
The catalogue has a fingerprint of its own. Re-running the selection on the same
catalogue always returns the same task numbers in the same order.
"""

from __future__ import annotations

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

CATALOG_SCHEMA_VERSION = "gdpval-task-catalog-v1"

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

# Field names that would mean a score leaked into the catalogue.
_SCORE_LIKE_FIELD_NAMES = frozenset(
    {
        "awarded_score",
        "score",
        "max_score",
        "pct",
        "pct_raw",
        "verdict",
        "passed",
        "grade",
        "external_grade",
        "summary",
        "judge",
        "judge_confidence",
        "total_awarded",
        "rank",
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


def check_catalog_carries_no_scores(
    path: str | Path | None = None,
) -> list[str]:
    """Look for any score, grade, or verdict that leaked into the catalogue.

    The selection must be defensible as having been made before results were
    seen, so the file it reads is not allowed to carry results at all.
    """
    target = Path(path) if path is not None else CATALOG_PATH
    raw = json.loads(target.read_text(encoding="utf-8"))
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if str(key).lower() in _SCORE_LIKE_FIELD_NAMES:
                    found.add(str(key))
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    walk(raw)
    if found:
        return [
            "the task catalogue carries fields that could hold a result, so "
            "the task choice cannot be shown to predate the scores: "
            + ", ".join(sorted(found))
        ]
    return []


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


def describe_selection_rule() -> str:
    """One paragraph a reader can check the chosen five against by hand."""
    return (
        "Sort every task in the benchmark by its task number. Then fill five "
        "slots in this order: spreadsheet, document, presentation, picture, "
        "text answer only. For each slot take the smallest-numbered task that "
        "has not been taken, whose job is not already represented, and all of "
        "whose expert answer files belong to that format; if the benchmark "
        "holds no such task, take the smallest-numbered one where at least one "
        "answer file does. The rule reads only task numbers, industries, jobs, "
        "and expert answer file types, so no score can move it."
    )


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
# 32 hexadecimal characters of that file's SHA-256 fingerprint. That makes a
# written fingerprint checkable without downloading the file.
REFERENCE_PATH_FINGERPRINT_LENGTH = 32


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


def check_input_file_versions(
    input_file_versions: Mapping[str, str],
    task_ids: Sequence[str],
    catalog: TaskCatalog,
) -> list[str]:
    """Confirm the written input fingerprints cover, and match, the real inputs.

    Two things are checked, both without any download:

    * every reference file the chosen tasks ship with has a fingerprint written
      down, and nothing extra is written down;
    * each written fingerprint agrees with the folder the dataset keeps that
      file in, which is named after the start of the file's own fingerprint.
    """
    problems: list[str] = []
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
        fingerprint = file_entries[path].strip().lower()
        if len(fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in fingerprint
        ):
            problems.append(
                f"the fingerprint written for {path} is not a SHA-256 value"
            )
            continue
        folder = Path(path).parent.name.lower()
        if len(folder) == REFERENCE_PATH_FINGERPRINT_LENGTH and not (
            fingerprint.startswith(folder)
        ):
            problems.append(
                f"the fingerprint written for {path} does not match the folder "
                "the dataset keeps that file in, so the written value describes "
                "some other file"
            )
    return problems
