"""Outcome-free deterministic selector for agentic canary/diagnostic tasks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SEED = "20260717"
TABULAR = {"csv", "tsv", "xls", "xlsx", "xlsm", "ods", "parquet"}
DOCUMENT = {"pdf", "doc", "docx", "ppt", "pptx", "txt", "md", "rtf"}
MEDIA = {
    "png", "jpg", "jpeg", "gif", "webp", "tif", "tiff", "bmp", "svg",
    "wav", "mp3", "m4a", "flac", "ogg", "mp4", "mov", "avi", "mkv",
    "webm",
}
FORBIDDEN_OUTCOME_PATHS = (
    "data/grades",
    "batch-runner/results",
    "batch-runner/workspace",
    "batch-output",
    "run-logs",
    "logs",
    ".cache/huggingface",
)
MAX_INPUT_FILES = 256
MAX_INPUT_TOTAL = 2 * 1024 * 1024 * 1024
MAX_INPUT_SINGLE = 512 * 1024 * 1024
FULL_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}/"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}$"
)


@dataclass(frozen=True)
class EligibleTask:
    task_id: str
    sector: str
    occupation: str
    input_class: str
    reference_paths: tuple[str, ...]
    reference_suffixes: tuple[str, ...]
    reference_sizes: tuple[int, ...]
    positive_rubric_max: float

    @property
    def stratum(self) -> tuple[str, str]:
        return self.sector, self.input_class


def select_agentic_tasks(
    records: Sequence[Mapping[str, Any]],
    rubrics: Mapping[str, Any],
    *,
    dataset_sha: str,
    seed: str = SEED,
) -> dict:
    """Return exact ordered canary/diagnostic IDs and selection provenance."""
    if seed != SEED:
        raise ValueError(f"selector seed must be the preregistered literal {SEED}")
    if not isinstance(dataset_sha, str) or FULL_COMMIT_RE.fullmatch(
        dataset_sha
    ) is None:
        raise ValueError("full immutable dataset revision is required")
    eligible = _eligible_frame(records, rubrics)
    if len(eligible) < 25:
        raise ValueError("eligible frame must contain at least 25 tasks")

    by_stratum: dict[tuple[str, str], list[EligibleTask]] = {}
    for task in eligible:
        by_stratum.setdefault(task.stratum, []).append(task)
    counts = {stratum: len(tasks) for stratum, tasks in by_stratum.items()}
    seats = _largest_remainder(counts, 25)

    selected_by_stratum: dict[tuple[str, str], list[EligibleTask]] = {}
    for stratum, tasks in by_stratum.items():
        ordered = sorted(
            tasks,
            key=lambda task: (
                _digest("agentic-select-v1", seed, dataset_sha, task.task_id),
                task.task_id.encode("utf-8"),
            ),
        )
        selected_by_stratum[stratum] = ordered[:seats[stratum]]

    canary_seats = _largest_remainder(seats, 5, denominator=25)
    canary: list[EligibleTask] = []
    diagnostic: list[EligibleTask] = []
    for stratum, tasks in selected_by_stratum.items():
        canary_count = canary_seats[stratum]
        stratum_canary_ids = {
            task.task_id
            for task in sorted(
                tasks,
                key=lambda task: (
                    _digest(
                        "agentic-canary-v1", seed, dataset_sha, task.task_id
                    ),
                    task.task_id.encode("utf-8"),
                ),
            )[:canary_count]
        }
        for task in tasks:
            (
                canary
                if task.task_id in stratum_canary_ids
                else diagnostic
            ).append(task)

    canary = _ordered(
        canary, "agentic-order-canary-v1", seed, dataset_sha
    )
    diagnostic = _ordered(
        diagnostic, "agentic-order-diagnostic-v1", seed, dataset_sha
    )
    canary_ids = [task.task_id for task in canary]
    diagnostic_ids = [task.task_id for task in diagnostic]
    if len(canary_ids) != 5 or len(diagnostic_ids) != 20:
        raise AssertionError("selector did not produce exact 5/20 cohorts")
    if set(canary_ids) & set(diagnostic_ids):
        raise AssertionError("canary and diagnostic cohorts overlap")
    selected = canary + diagnostic
    if any(task.positive_rubric_max <= 0 for task in selected):
        raise ValueError("selected task has zero positive rubric denominator")

    return {
        "schema_version": "agentic-task-subset-v1",
        "seed": seed,
        "eligible_frame_count": len(eligible),
        "strata": [
            {
                "sector": stratum[0],
                "input_class": stratum[1],
                "eligible_count": counts[stratum],
                "selected_quota": seats[stratum],
                "canary_quota": canary_seats[stratum],
            }
            for stratum in sorted(counts, key=_stratum_sort_key)
        ],
        "canary_task_ids": canary_ids,
        "diagnostic_task_ids": diagnostic_ids,
        "selected_tasks": [
            {
                "task_id": task.task_id,
                "sector": task.sector,
                "occupation": task.occupation,
                "input_class": task.input_class,
                "reference_paths": list(task.reference_paths),
                "reference_suffixes": list(task.reference_suffixes),
                "reference_sizes": list(task.reference_sizes),
                "positive_rubric_max": task.positive_rubric_max,
            }
            for task in selected
        ],
        "selection_domains": {
            "select": "agentic-select-v1",
            "canary": "agentic-canary-v1",
            "order_canary": "agentic-order-canary-v1",
            "order_diagnostic": "agentic-order-diagnostic-v1",
        },
        "tie_break": "ascending UTF-8 bytes",
        "selected_before_outcomes": True,
    }


def build_selection_manifest(
    selection: Mapping[str, Any],
    *,
    dataset_repo: str,
    dataset_sha: str,
    rubric_repo: str,
    rubric_sha: str,
    dataset_path: str | Path,
    rubric_path: str | Path,
    selector_path: str | Path,
    repository_root: str | Path,
    source_commit: str,
) -> dict:
    for label, repository in (
        ("dataset", dataset_repo), ("rubric", rubric_repo)
    ):
        if not isinstance(repository, str) or REPOSITORY_RE.fullmatch(
            repository
        ) is None:
            raise ValueError(f"{label} repository identity is invalid")
    for label, revision in (
        ("dataset", dataset_sha), ("rubric", rubric_sha),
        ("selector source", source_commit),
    ):
        if not isinstance(revision, str) or FULL_COMMIT_RE.fullmatch(
            revision
        ) is None:
            raise ValueError(f"{label} revision must be a full commit SHA")
    root = Path(repository_root).resolve()
    dataset_source = resolve_outcome_free_file(
        root, dataset_path, "dataset JSON"
    )
    rubric_source = resolve_outcome_free_file(
        root, rubric_path, "rubric JSON"
    )
    selector = resolve_outcome_free_file(root, selector_path, "selector source")
    actual_commit = _git_output(root, "rev-parse", "HEAD")
    if source_commit != actual_commit:
        raise ValueError("selector source commit differs from clean checkout")
    selector_relative = selector.relative_to(root).as_posix()
    manifest = dict(selection)
    manifest.update({
        "dataset": {
            "repository": dataset_repo,
            "revision": dataset_sha,
            "source_path": dataset_source.relative_to(root).as_posix(),
            "sha256": _sha256_file(dataset_source),
        },
        "rubric": {
            "repository": rubric_repo,
            "revision": rubric_sha,
            "source_path": rubric_source.relative_to(root).as_posix(),
            "sha256": _sha256_file(rubric_source),
        },
        "selector": {
            "path": selector_relative,
            "source_commit": source_commit,
            "sha256": _sha256_file(selector),
        },
        "inclusion_validation": "all structural checks passed",
        "exclusion_validation": "outcome fields were not accepted by selector",
    })
    manifest["recomputation_sha256"] = hashlib.sha256(
        json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    return manifest


def assert_outcome_free_checkout(root: str | Path) -> str:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("outcome-free root is missing")
    present = [path for path in FORBIDDEN_OUTCOME_PATHS if (root / path).exists()]
    if present:
        raise ValueError(
            "selector checkout can read forbidden outcome paths: "
            + ", ".join(present)
        )
    if Path(_git_output(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("outcome-free root differs from Git top level")
    status_output = _git_output(
        root, "status", "--porcelain=v1", "--untracked-files=all"
    )
    if status_output:
        raise ValueError("outcome-free selector requires a clean checkout")
    commit = _git_output(root, "rev-parse", "HEAD")
    if len(commit) != 40:
        raise ValueError("outcome-free source commit is invalid")
    return commit


def resolve_outcome_free_file(
    root: str | Path, value: str | Path, label: str
) -> Path:
    root = Path(root).resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    absolute = candidate.absolute()
    try:
        relative = absolute.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes outcome-free root") from exc
    current = root
    for part in relative.parts:
        current /= part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ValueError(f"{label} is missing") from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"{label} contains a symlink")
    metadata = absolute.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise ValueError(f"{label} must be a single-link regular file")
    return absolute


def _git_output(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("outcome-free Git identity is unavailable") from exc
    return result.stdout.strip()


def _eligible_frame(
    records: Sequence[Mapping[str, Any]], rubrics: Mapping[str, Any]
) -> list[EligibleTask]:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise ValueError("dataset records must be a sequence")
    seen: set[str] = set()
    output = []
    forbidden_fields = {
        "grade", "grades", "score", "completion", "retry", "cost",
        "human_label", "prior_run", "outcome",
    }
    for raw in records:
        if not isinstance(raw, Mapping):
            raise ValueError("every dataset record must be an object")
        if forbidden_fields & set(raw):
            raise ValueError("dataset record contains forbidden outcome field")
        task_id = _required_text(raw, "task_id")
        if task_id in seen:
            raise ValueError(f"duplicate task_id: {task_id}")
        seen.add(task_id)
        sector = _required_text(raw, "sector")
        occupation = _required_text(raw, "occupation")
        _required_text(raw, "prompt")
        references = _reference_metadata(raw.get("reference_files", []))
        if task_id not in rubrics:
            raise ValueError(f"missing rubric for task: {task_id}")
        positive_max = _positive_rubric_max(rubrics[task_id])
        paths = tuple(reference[0] for reference in references)
        suffixes = tuple(reference[1] for reference in references)
        sizes = tuple(reference[2] for reference in references)
        output.append(EligibleTask(
            task_id=task_id,
            sector=sector,
            occupation=occupation,
            input_class=_input_class(suffixes),
            reference_paths=paths,
            reference_suffixes=suffixes,
            reference_sizes=sizes,
            positive_rubric_max=positive_max,
        ))
    return output


def _reference_metadata(value: Any) -> list[tuple[str, str, int]]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ValueError("reference_files must be a list")
    if len(value) > MAX_INPUT_FILES:
        raise ValueError("reference file count exceeds agentic input limit")
    records = []
    total = 0
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("reference metadata must contain path and size")
        path = item.get("path") or item.get("name")
        size = item.get("size_bytes")
        if not isinstance(path, str) or not path or Path(path).is_absolute():
            raise ValueError("reference path must be non-empty and relative")
        if ".." in Path(path).parts:
            raise ValueError("reference path traversal is forbidden")
        if type(size) is not int or size < 0 or size > MAX_INPUT_SINGLE:
            raise ValueError("reference size exceeds agentic input limit")
        total += size
        if total > MAX_INPUT_TOTAL:
            raise ValueError("reference total exceeds agentic input limit")
        suffix = Path(path).suffix.lower().lstrip(".")
        records.append((Path(path).as_posix(), suffix, size))
    return records


def _positive_rubric_max(value: Any) -> float:
    items = value.get("rubric_items") if isinstance(value, Mapping) else value
    if not isinstance(items, list):
        raise ValueError("rubric must be a list or contain rubric_items")
    total = 0.0
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("rubric item must be an object")
        maximum = item.get("max_score", item.get("score"))
        if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
            raise ValueError("rubric maximum must be numeric")
        if maximum > 0:
            total += float(maximum)
    return total


def _input_class(suffixes: tuple[str, ...]) -> str:
    if not suffixes:
        return "none"
    values = set(suffixes)
    if values <= TABULAR:
        return "tabular"
    if values <= DOCUMENT:
        return "document"
    if values <= MEDIA:
        return "media"
    return "mixed_or_other"


def _largest_remainder(
    counts: Mapping[tuple[str, str], int],
    total_seats: int,
    *,
    denominator: int | None = None,
) -> dict[tuple[str, str], int]:
    denominator = denominator or sum(counts.values())
    if total_seats <= 0 or denominator <= 0:
        raise ValueError("largest-remainder inputs must be positive")
    exact = {
        key: Fraction(total_seats * value, denominator)
        for key, value in counts.items()
    }
    seats = {key: int(value) for key, value in exact.items()}
    remaining = total_seats - sum(seats.values())
    ranked = sorted(
        counts,
        key=lambda key: (
            -(exact[key] - seats[key]),
            _stratum_sort_key(key),
        ),
    )
    for key in ranked[:remaining]:
        seats[key] += 1
    if sum(seats.values()) != total_seats:
        raise AssertionError("largest-remainder allocation failed")
    return seats


def _ordered(
    tasks: Iterable[EligibleTask], domain: str, seed: str, dataset_sha: str
) -> list[EligibleTask]:
    return sorted(
        tasks,
        key=lambda task: (
            _digest(domain, seed, dataset_sha, task.task_id),
            task.task_id.encode("utf-8"),
        ),
    )


def _digest(domain: str, seed: str, dataset_sha: str, task_id: str) -> bytes:
    preimage = (
        domain + "\0" + seed + "\0" + dataset_sha + "\0" + task_id
    ).encode("utf-8")
    return hashlib.sha256(preimage).digest()


def _stratum_sort_key(stratum: tuple[str, str]) -> bytes:
    output = bytearray()
    for value in stratum:
        encoded = value.encode("utf-8")
        output.extend(len(encoded).to_bytes(4, "big"))
        output.extend(encoded)
    return bytes(output)


def _required_text(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()