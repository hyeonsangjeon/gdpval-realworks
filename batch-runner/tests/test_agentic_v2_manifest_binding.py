"""Whether a cohort can be bound to prompts without changing the experiment.

The positive path uses a catalogue this file builds, because the committed one
pins ``prompt_sha256`` for prompts that live in a dataset snapshot nobody here
has — ``data/gdpval-local`` in this checkout holds no parquet. That is stated
rather than worked around: these tests prove the check bites, and no run in this
repository has yet bound the real 220 against the real dataset.

What *is* checked against the committed catalogue is everything that does not
need the prompts: that stage five really is five tasks, that its ids are the
ones the selection rule gives, and that a prompt which is not the pinned one is
refused.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace

import pytest

from core.agentic_v2_manifest_binding import (
    ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL,
    BINDING_SCHEMA_VERSION,
    STAGE_FIVE,
    STAGE_THIRTY,
    STAGE_TWO_TWENTY,
    ManifestRefused,
    bind_stage,
    binding_record,
    unmet_needs,
)
from core.agentic_v2_preregistration import STAGE_SIZES
from core.agentic_v2_run_driver import TaskToRun
from core.execution_envelope_tasks import (
    CatalogTask,
    TaskCatalog,
    catalog_sha256,
    load_task_catalog,
    select_advance_check_tasks,
)


DIGEST = "e" * 64


@dataclass
class Row:
    """A dataset row, shaped like ``prepare_dataset.GDPValTask``."""

    task_id: str
    prompt: str
    sector: str
    occupation: str
    reference_files: tuple[str, ...] = ()
    # The expert's own answer travels on the real row too. Present here so a
    # test can prove it is not read.
    deliverable_text: str = "the expert's answer, which must not travel"
    deliverable_files: tuple[str, ...] = ("expert_answer.xlsx",)


#: One task per format family the advance-check rule walks, in its order:
#: spreadsheet, document, presentation, image, then the text-only slot.
_SHAPES = (
    ((".xlsx",), "Analyst", "Finance"),
    ((".docx",), "Writer", "Media"),
    ((".pptx",), "Consultant", "Services"),
    ((".png",), "Designer", "Manufacturing"),
    ((), "Advisor", "Retail"),
)


def _catalog_task(index, extensions, occupation, sector, prompt, references=()):
    return CatalogTask(
        task_id=f"task-{index:04d}",
        sector=sector,
        occupation=occupation,
        deliverable_file_extensions=tuple(extensions),
        reference_file_count=len(references),
        reference_file_extensions=tuple(
            sorted({"." + name.rsplit(".", 1)[-1] for name in references})
        ),
        reference_file_paths=tuple(sorted(references)),
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        prompt_character_count=len(prompt),
        rubric_item_count=4,
        widest_rubric_criterion_characters=120,
    )


def _prompt_for(index):
    return f"Prompt number {index}. Do the work and hand in the file."


@pytest.fixture
def bench():
    """A five-task catalogue and the dataset rows that match it exactly."""
    tasks = []
    rows = []
    for index, (extensions, occupation, sector) in enumerate(_SHAPES, start=1):
        prompt = _prompt_for(index)
        references = ("Costs.xlsx",) if index == 1 else ()
        tasks.append(
            _catalog_task(index, extensions, occupation, sector, prompt, references)
        )
        rows.append(
            Row(
                task_id=f"task-{index:04d}",
                prompt=prompt,
                sector=sector,
                occupation=occupation,
                reference_files=references,
            )
        )
    catalog = TaskCatalog(
        schema_version="gdpval-task-catalog-v1",
        dataset_repo_id="example/benchmark",
        dataset_revision="d" * 40,
        dataset_file_sha256="f" * 64,
        tasks=tuple(tasks),
    )
    return catalog, rows


def _bind(bench, **kwargs):
    catalog, rows = bench
    kwargs.setdefault("dataset_tasks", rows)
    kwargs.setdefault("catalog", catalog)
    kwargs.setdefault("catalog_digest", DIGEST)
    return bind_stage(kwargs.pop("stage", STAGE_FIVE), **kwargs)


# ── the answer never travels ─────────────────────────────────────────────


def test_a_bound_task_has_nowhere_to_put_the_expert_s_answer():
    carried = {field for field in TaskToRun.__dataclass_fields__}
    assert carried & set(ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL) == set()


def test_the_answer_on_the_row_is_not_read(bench):
    bound = _bind(bench)
    everything = repr(bound.as_dict()) + repr(bound.tasks)
    assert "must not travel" not in everything
    assert "expert_answer.xlsx" not in everything


# ── binding ──────────────────────────────────────────────────────────────


def test_five_tasks_bind_with_their_prompts(bench):
    bound = _bind(bench)
    assert len(bound.tasks) == STAGE_SIZES[STAGE_FIVE]
    assert bound.tasks[0].prompt == _prompt_for(1)
    assert bound.stage == STAGE_FIVE
    assert bound.catalog_sha256 == DIGEST
    assert bound.dataset_revision == "d" * 40


def test_the_bound_ids_are_the_selection_rule_s(bench):
    catalog, _ = bench
    bound = _bind(bench)
    assert bound.task_ids == select_advance_check_tasks(
        catalog, catalog_fingerprint=DIGEST
    ).task_ids


def test_occupation_and_sector_come_from_the_pinned_catalogue(bench):
    bound = _bind(bench)
    assert {task.occupation for task in bound.tasks} == {
        occupation for _, occupation, _ in _SHAPES
    }


def test_the_prompt_digests_are_recorded_per_task(bench):
    bound = _bind(bench)
    digests = dict(bound.prompt_digests)
    assert len(digests) == 5
    assert digests["task-0001"] == hashlib.sha256(
        _prompt_for(1).encode("utf-8")
    ).hexdigest()


# ── drift ────────────────────────────────────────────────────────────────


def test_a_changed_prompt_is_refused(bench):
    catalog, rows = bench
    rows[0] = replace(rows[0], prompt=_prompt_for(1) + " Also, be brief.")
    with pytest.raises(ManifestRefused, match="different prompt"):
        _bind((catalog, rows))


def test_a_prompt_of_the_same_length_is_still_refused(bench):
    """A length check would pass this; a digest does not."""
    catalog, rows = bench
    original = _prompt_for(1)
    swapped = original[:-1] + ("?" if original[-1] != "?" else ".")
    assert len(swapped) == len(original)
    rows[0] = replace(rows[0], prompt=swapped)
    with pytest.raises(ManifestRefused, match="different prompt"):
        _bind((catalog, rows))


def test_a_changed_occupation_is_refused(bench):
    catalog, rows = bench
    rows[0] = replace(rows[0], occupation="Someone Else")
    with pytest.raises(ManifestRefused, match="occupation"):
        _bind((catalog, rows))


def test_a_changed_reference_file_list_is_refused(bench):
    catalog, rows = bench
    rows[0] = replace(rows[0], reference_files=("Costs.xlsx", "Extra.docx"))
    with pytest.raises(ManifestRefused, match="reference files"):
        _bind((catalog, rows))


def test_reference_files_in_another_order_are_accepted(bench):
    """The catalogue sorted them; the dataset need not have."""
    catalog, rows = bench
    tasks = list(catalog.tasks)
    tasks[0] = replace(
        tasks[0], reference_file_paths=("Costs.xlsx", "Notes.docx")
    )
    rows[0] = replace(rows[0], reference_files=("Notes.docx", "Costs.xlsx"))
    bound = _bind((replace(catalog, tasks=tuple(tasks)), rows))
    assert bound.tasks[0].reference_files == ("Costs.xlsx", "Notes.docx")


def test_a_missing_task_is_refused(bench):
    catalog, rows = bench
    with pytest.raises(ManifestRefused, match="not in the dataset"):
        _bind((catalog, rows[:-1]))


def test_a_duplicated_dataset_row_is_refused(bench):
    catalog, rows = bench
    with pytest.raises(ManifestRefused, match="twice"):
        _bind((catalog, rows + [rows[0]]))


def test_every_drifted_task_is_named_not_just_the_first(bench):
    catalog, rows = bench
    rows[0] = replace(rows[0], prompt="something else entirely")
    rows[1] = replace(rows[1], occupation="Someone Else")
    with pytest.raises(ManifestRefused) as raised:
        _bind((catalog, rows))
    assert "task-0001" in str(raised.value)
    assert "task-0002" in str(raised.value)


# ── provenance the binding refuses to invent ─────────────────────────────


def test_a_supplied_catalogue_without_its_digest_is_refused(bench):
    catalog, rows = bench
    with pytest.raises(ManifestRefused, match="without its digest"):
        bind_stage(STAGE_FIVE, dataset_tasks=rows, catalog=catalog)


def test_a_digest_without_a_catalogue_is_refused(bench):
    _, rows = bench
    with pytest.raises(ManifestRefused, match="without a catalogue"):
        bind_stage(STAGE_FIVE, dataset_tasks=rows, catalog_digest=DIGEST)


def test_an_unknown_stage_is_refused(bench):
    with pytest.raises(ManifestRefused, match="not a registered stage"):
        _bind(bench, stage="a_quick_one")


def test_a_catalogue_too_small_for_the_escalation_records_no_seal(bench):
    """Five tasks cannot produce the thirty-task cohort, so there is no seal."""
    bound = _bind(bench)
    assert bound.preregistration_seal is None


def test_a_seal_that_cannot_be_computed_is_an_error_when_one_was_given(bench):
    with pytest.raises(ManifestRefused, match="cannot"):
        _bind(bench, expected_seal="a" * 64)


def test_the_binding_seal_changes_when_a_prompt_does(bench):
    catalog, rows = bench
    before = _bind((catalog, list(rows))).binding_seal()

    tasks = list(catalog.tasks)
    changed = _prompt_for(1) + " Be brief."
    tasks[0] = replace(
        tasks[0],
        prompt_sha256=hashlib.sha256(changed.encode("utf-8")).hexdigest(),
        prompt_character_count=len(changed),
    )
    rows[0] = replace(rows[0], prompt=changed)
    after = _bind((replace(catalog, tasks=tuple(tasks)), rows)).binding_seal()
    assert before != after


def test_the_record_carries_the_schema_and_both_seals(bench):
    record = binding_record(_bind(bench))
    assert record["schema_version"] == BINDING_SCHEMA_VERSION
    assert len(record["binding_seal"]) == 64
    assert record["preregistration_seal"] is None
    assert record["stage"] == STAGE_FIVE


# ── what is still missing ────────────────────────────────────────────────


def test_the_binding_says_which_tasks_lack_their_input_files(bench):
    needs = unmet_needs(_bind(bench))
    assert needs["tasks_needing_reference_files"] == ["task-0001"]
    assert needs["reference_file_bytes_are_in_the_guest"] is False
    assert "not evidence about the model" in needs["what_that_means"]


def test_a_task_with_no_reference_files_is_not_counted_as_handicapped(bench):
    needs = unmet_needs(_bind(bench))
    assert needs["tasks_needing_reference_files_count"] == 1


# ── against the catalogue that is actually committed ─────────────────────


def test_the_committed_catalogue_still_gives_five_and_thirty_and_220():
    catalog = load_task_catalog()
    assert len(select_advance_check_tasks(catalog).task_ids) == STAGE_SIZES[STAGE_FIVE]
    assert len(catalog.tasks) == STAGE_SIZES[STAGE_TWO_TWENTY]


def test_the_committed_catalogue_refuses_prompts_nobody_here_has():
    """The snapshot in this checkout holds no parquet, so this must not pass."""
    catalog = load_task_catalog()
    wanted = select_advance_check_tasks(catalog).task_ids
    pinned = catalog.by_task_id()
    invented = [
        Row(
            task_id=task_id,
            prompt="a prompt this repository does not have",
            sector=pinned[task_id].sector,
            occupation=pinned[task_id].occupation,
            reference_files=pinned[task_id].reference_file_paths,
        )
        for task_id in wanted
    ]
    with pytest.raises(ManifestRefused, match="different prompt"):
        bind_stage(
            STAGE_FIVE,
            dataset_tasks=invented,
            catalog=catalog,
            catalog_digest=catalog_sha256(),
        )


def test_the_thirty_stage_binds_from_the_committed_catalogue_shape():
    """Only the shape: the ids are real, the prompts are still not here."""
    catalog = load_task_catalog()
    pinned = catalog.by_task_id()
    from core.execution_envelope_tasks import select_trial_run_tasks

    wanted = select_trial_run_tasks(catalog)
    assert len(wanted) == STAGE_SIZES[STAGE_THIRTY]
    assert all(task_id in pinned for task_id in wanted)
