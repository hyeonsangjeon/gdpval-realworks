"""Turning a sealed cohort into tasks the driver can run — or refusing to.

:mod:`core.agentic_v2_preregistration` fixes *which* tasks a stage runs: a list
of task ids, pinned to a catalogue digest and a dataset revision, sealed before
anything starts. :mod:`core.agentic_v2_run_driver` runs
:class:`~core.agentic_v2_run_driver.TaskToRun` objects, which carry prompts.
Nothing joined the two, and the join is not a lookup — it is the point at which
"the manifest was fixed in advance" stops being a claim and becomes something a
reader can check.

**What is actually verified.** The committed catalogue records
``prompt_sha256`` for every task, built as ``sha256(str(row["prompt"]).encode(
"utf-8"))``. The dataset loader builds its prompt the same way, from the same
column. So the two hashes are comparable exactly, and a prompt that differs by
one character from the one the seal was computed over stops the run. This is a
real check and not a length comparison; ``prompt_character_count`` is also
pinned but is not what is compared, because two different prompts of the same
length are easy and two different prompts with the same digest are not.

Sector, occupation and the sorted reference-file paths are checked the same way.
A cohort whose size no longer matches :data:`STAGE_SIZES` is refused before any
of that, because a five-task stage that binds four tasks is not a smaller stage
five, it is a different experiment.

**What is deliberately not carried.** Every dataset row holds
``deliverable_text`` and ``deliverable_files`` — the expert's own answer, which
is what the run is scored against. A task handed to a model with its answer
attached would score well and mean nothing. Those fields are never read here,
and :data:`ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL` is checked against
``TaskToRun``'s own fields at import, so a later widening of that dataclass to
carry an answer fails on import rather than in a result.

**What is still missing, stated plainly.** ``TaskToRun.reference_files`` carries
the *names* the dataset lists, because that is what the dataset gives and what
:meth:`core.agentic_v2_runner.AgenticV2ScriptedRunner.run` accepts — it takes
the list and passes it into the worker unchanged. Nothing yet copies those files
into the guest's workspace as bytes. A bound task is therefore a task whose
reference files are *named* and not *present*, and a task needing one of them to
be opened will fail on its merits. That is a gap in the environment, not in this
module, and :func:`unmet_needs` reports it per task so a stage-five result can
be read knowing which tasks were asked to work without their inputs.

Nothing here calls a model, opens a guest, or spends anything.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from typing import Any, Iterable, Mapping, Sequence

from core.agentic_v2_preregistration import (
    ESCALATION,
    STAGE_FIVE,
    STAGE_SIZES,
    STAGE_THIRTY,
    STAGE_TWO_TWENTY,
    manifest,
    seal,
)
from core.agentic_v2_run_driver import TaskToRun
from core.execution_envelope_tasks import (
    CatalogTask,
    TaskCatalog,
    catalog_sha256,
    full_run_tasks,
    load_task_catalog,
    select_advance_check_tasks,
    select_trial_run_tasks,
)


BINDING_SCHEMA_VERSION = "agentic-v2-manifest-binding-v1"

#: Dataset columns holding the expert's own answer.
#:
#: Named so that "the model was not shown the answer" is a checked property of
#: this module rather than a habit of whoever wrote the loop.
ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL = (
    "deliverable_text",
    "deliverable_files",
    "rubric_pretty",
    "rubric_json",
)

_CARRIED = frozenset(field.name for field in fields(TaskToRun))

_LEAKED = _CARRIED & set(ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL)
if _LEAKED:  # pragma: no cover - import guard
    raise RuntimeError(
        "TaskToRun now carries a field that holds the expert's own answer: "
        f"{sorted(_LEAKED)}. A task handed to a model with its answer attached "
        "scores well and means nothing."
    )


class ManifestRefused(RuntimeError):
    """The cohort was not bound, because running it would not be the run that
    was registered."""


@dataclass(frozen=True)
class BoundManifest:
    """A stage's tasks, and the evidence that they are the registered ones."""

    stage: str
    tasks: tuple[TaskToRun, ...]
    catalog_sha256: str
    dataset_repo_id: str
    dataset_revision: str
    dataset_file_sha256: str
    prompt_digests: tuple[tuple[str, str], ...]
    preregistration_seal: str | None

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(task.task_id for task in self.tasks)

    def binding_seal(self) -> str:
        """A digest over what was bound, for the run record to carry.

        Distinct from :attr:`preregistration_seal`, which covers the plan. This
        one covers the plan *and* the prompts that were found on disk for it, so
        two runs of the same stage that read different data are distinguishable
        even though their plans are identical.
        """
        return hashlib.sha256(
            json.dumps(
                self.as_dict(), sort_keys=True, ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BINDING_SCHEMA_VERSION,
            "stage": self.stage,
            "task_ids": list(self.task_ids),
            "catalog_sha256": self.catalog_sha256,
            "dataset_repo_id": self.dataset_repo_id,
            "dataset_revision": self.dataset_revision,
            "dataset_file_sha256": self.dataset_file_sha256,
            "prompt_digests": {
                task_id: digest for task_id, digest in self.prompt_digests
            },
            "preregistration_seal": self.preregistration_seal,
        }


def _prompt_digest(prompt: str) -> str:
    """Hashed the way the committed catalogue hashed it, or the check is void."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _drift(pinned: CatalogTask, row: Any) -> list[str]:
    """Every way this dataset row is not the task the seal was computed over."""
    problems: list[str] = []

    digest = _prompt_digest(str(getattr(row, "prompt", "")))
    if digest != pinned.prompt_sha256:
        problems.append(
            f"the prompt hashes to {digest} and the catalogue pinned "
            f"{pinned.prompt_sha256}; this is a different prompt, so a run of "
            "it is not the run that was registered"
        )
    for name in ("sector", "occupation"):
        found = str(getattr(row, name, ""))
        expected = getattr(pinned, name)
        if found != expected:
            problems.append(f"{name} is {found!r} and the catalogue pinned {expected!r}")

    found_files = tuple(sorted(str(name) for name in getattr(row, "reference_files", ())))
    if found_files != tuple(pinned.reference_file_paths):
        problems.append(
            f"the reference files are {list(found_files)} and the catalogue "
            f"pinned {list(pinned.reference_file_paths)}"
        )
    return problems


def _cohort_for(stage: str, catalog: TaskCatalog) -> tuple[str, ...]:
    """Just this stage's task ids.

    :func:`~core.agentic_v2_preregistration.cohorts` derives all three at once,
    which means binding stage five would fail on a catalogue too small for the
    thirty-task rule. The stages are run one at a time and a binding should
    depend only on the one being bound.
    """
    if stage == STAGE_FIVE:
        return select_advance_check_tasks(catalog).task_ids
    if stage == STAGE_THIRTY:
        return select_trial_run_tasks(catalog)
    return full_run_tasks(catalog)


def bind_stage(
    stage: str,
    *,
    dataset_tasks: Iterable[Any],
    catalog: TaskCatalog | None = None,
    catalog_digest: str | None = None,
    expected_seal: str | None = None,
) -> BoundManifest:
    """The tasks of one stage, checked against what was sealed before the run.

    ``dataset_tasks`` is any iterable of rows carrying ``task_id``, ``prompt``,
    ``sector``, ``occupation`` and ``reference_files`` —
    :class:`prepare_dataset.GDPValTask` is one. It is a parameter rather than a
    load so that this module holds no opinion about where the data came from and
    a test needs no parquet.

    ``catalog_digest`` is required whenever ``catalog`` is supplied.
    :func:`~core.execution_envelope_tasks.catalog_sha256` hashes the *committed*
    catalogue file regardless of what object is in hand, so recording its return
    value beside a caller-supplied catalogue would label one catalogue with
    another's fingerprint. Demanding the digest is how the binding avoids
    claiming a provenance it cannot compute.

    ``expected_seal``, when given, is compared against the pre-registration's
    own seal. Passing it is how a run says *this* plan and not merely *a* plan.
    """
    if stage not in STAGE_SIZES:
        raise ManifestRefused(
            f"{stage!r} is not a registered stage; the escalation is "
            f"{list(ESCALATION)}"
        )
    if catalog is None:
        if catalog_digest is not None:
            raise ManifestRefused(
                "a catalogue digest was given without a catalogue; the "
                "committed catalogue fingerprints itself"
            )
        catalog = load_task_catalog()
        catalog_digest = catalog_sha256()
    elif catalog_digest is None:
        raise ManifestRefused(
            "a catalogue was supplied without its digest, and the digest of a "
            "supplied catalogue cannot be computed from the committed file; "
            "pass catalog_digest or pass neither"
        )
    wanted = _cohort_for(stage, catalog)
    expected_size = STAGE_SIZES[stage]
    if len(wanted) != expected_size:
        raise ManifestRefused(
            f"stage {stage!r} selected {len(wanted)} tasks and the registration "
            f"fixes {expected_size}; a stage of a different size is a different "
            "experiment, not a smaller one"
        )

    # The seal covers the whole escalation, so computing it needs a catalogue
    # every stage's rule can run against. A catalogue that cannot produce one
    # has no plan seal, and that is recorded as ``None`` rather than invented —
    # unless the caller named a seal to check, in which case being unable to
    # compute one is the failure.
    plan_seal: str | None = None
    try:
        plan_seal = seal(manifest(catalog))
    except ValueError as error:
        if expected_seal is not None:
            raise ManifestRefused(
                f"a seal was given to check against, and this catalogue cannot "
                f"produce the escalation the seal covers: {error}"
            ) from error
    if expected_seal is not None and plan_seal != expected_seal:
        raise ManifestRefused(
            f"the manifest now seals to {plan_seal} and the run was registered "
            f"against {expected_seal}; something that was fixed has moved"
        )

    rows: dict[str, Any] = {}
    for row in dataset_tasks:
        task_id = str(getattr(row, "task_id", ""))
        if task_id in rows:
            raise ManifestRefused(
                f"the dataset carries {task_id!r} twice, so there is no single "
                "prompt to bind"
            )
        rows[task_id] = row

    missing = [task_id for task_id in wanted if task_id not in rows]
    if missing:
        raise ManifestRefused(
            f"{len(missing)} registered task(s) are not in the dataset: "
            f"{missing[:5]}"
        )

    pinned_by_id = catalog.by_task_id()
    problems: list[str] = []
    tasks: list[TaskToRun] = []
    digests: list[tuple[str, str]] = []
    for task_id in wanted:
        row = rows[task_id]
        pinned = pinned_by_id.get(task_id)
        if pinned is None:
            problems.append(f"{task_id}: chosen for the run but not in the catalogue")
            continue
        drifted = _drift(pinned, row)
        if drifted:
            problems.extend(f"{task_id}: {reason}" for reason in drifted)
            continue
        prompt = str(row.prompt)
        digests.append((task_id, _prompt_digest(prompt)))
        tasks.append(
            TaskToRun(
                task_id=task_id,
                prompt=prompt,
                occupation=pinned.occupation,
                sector=pinned.sector,
                # Names, not bytes. See the module docstring: nothing copies
                # these into the guest yet, and ``unmet_needs`` says which tasks
                # that costs.
                reference_files=tuple(pinned.reference_file_paths),
            )
        )

    if problems:
        raise ManifestRefused(
            "the dataset on disk is not the one the manifest was sealed "
            "against:\n  " + "\n  ".join(problems[:10])
        )

    return BoundManifest(
        stage=stage,
        tasks=tuple(tasks),
        catalog_sha256=str(catalog_digest),
        dataset_repo_id=catalog.dataset_repo_id,
        dataset_revision=catalog.dataset_revision,
        dataset_file_sha256=catalog.dataset_file_sha256,
        prompt_digests=tuple(digests),
        preregistration_seal=plan_seal,
    )


def unmet_needs(bound: BoundManifest) -> dict[str, Any]:
    """Which bound tasks are being asked to work without their inputs.

    A task with reference files whose bytes are not in the guest can still be
    attempted, and may still fail on its merits — but a reader comparing stages
    needs to know which failures had that handicap. Reporting it is not the same
    as fixing it, and this does not fix it.
    """
    needing = [task.task_id for task in bound.tasks if task.reference_files]
    return {
        "stage": bound.stage,
        "tasks_needing_reference_files": needing,
        "tasks_needing_reference_files_count": len(needing),
        "reference_file_bytes_are_in_the_guest": False,
        "what_that_means": (
            f"{len(needing)} of {len(bound.tasks)} bound tasks name reference "
            "files that nothing copies into the workspace, so those tasks run "
            "with the file names in their prompt and not the files. A failure "
            "on one of them is not evidence about the model."
        ),
    }


def dataset_tasks_from_snapshot(local_path: str | None = None) -> Sequence[Any]:
    """The dataset rows, loaded the way the rest of the pipeline loads them.

    Imported inside the function because :mod:`prepare_dataset` puts the
    repository root on ``sys.path`` at import and pulls in pandas; a module that
    only needs to *check* a manifest should not pay for that.
    """
    from core.data_loader import GDPValDataset  # noqa: PLC0415

    dataset = GDPValDataset(local_path=local_path, auto_download=False)
    return dataset.load()


def binding_record(bound: BoundManifest) -> dict[str, Any]:
    """What the run record should carry about which tasks it ran."""
    record: dict[str, Any] = dict(bound.as_dict())
    record["binding_seal"] = bound.binding_seal()
    record["unmet_needs"] = unmet_needs(bound)
    return record


__all__ = [
    "ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL",
    "BINDING_SCHEMA_VERSION",
    "BoundManifest",
    "ManifestRefused",
    "STAGE_FIVE",
    "STAGE_THIRTY",
    "STAGE_TWO_TWENTY",
    "bind_stage",
    "binding_record",
    "dataset_tasks_from_snapshot",
    "unmet_needs",
]
