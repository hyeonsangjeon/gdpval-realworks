"""A task that does not fit in one chunk must not restart at item one.

``--resume`` harvests completed ``task_id``s, so the unit of recovery is a
whole task. That bound is deliberate and it holds until a task is longer than
a chunk. ``9e39df84`` is: fifty-seven items, four paid attempts that stopped at
45, 54, 54 and 55 of them, each one beginning again at item one. The shard
could not finish at any budget, because raising the budget only moves where
the money is lost to inside the task.

``core/task_checkpoint.py`` lets the dropped task leave its finished items
behind. What is tested here is mostly the ways that can go wrong, because the
happy path is one line and the traps are four (``305`` §B):

* **fairness** — the perception caps are per *task*. A task resumed twice must
  not get its looking back twice, or the same rubric is marked with a
  different instrument than its neighbour's;
* **provenance** — items graded at two different grader fingerprints inside
  one task would emerge wearing only the second, and the merge contract, which
  checks shards, would pass it quietly;
* **not a score** — half a rubric aggregated is a plausible-looking wrong
  number, so a checkpoint must be structurally unable to carry one;
* **cost** — a task spanning chunks leaves more than one run of ledger rows,
  and the receipt has to sum them.

Nothing here calls a model. The grader tests drive a real ``Grader`` with a
scripted client; the ``step8_grade`` driver is reached by lifting its local
functions out of the syntax tree and running them against fakes, because the
loop around them needs a graded corpus and a live endpoint.
"""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, fields
from pathlib import Path
from types import SimpleNamespace

import pytest

import step8_grade as s8
from core.grader import Grader, GradingDeadlineExceeded, ItemGrade, TaskGrade
from core.perception.audio import AudioPerception
from core.perception.vision import VisionPerception
from core.rubric_loader import RubricItem, TaskRubric
from core.task_checkpoint import (
    CHECKPOINT_FORMAT,
    CheckpointRejected,
    TaskProgress,
    TaskProgressDraft,
    build_progress,
    checkpoint_path,
    discard_checkpoint,
    load_checkpoint,
    load_checkpoint as _load_checkpoint,
    rubric_order_fingerprint,
    write_checkpoint,
)

STEP8 = Path(s8.__file__).resolve()

HASH_A = "a" * 64
HASH_B = "b" * 64
TASK_ID = "9e39df84-ac57-4c9b-a2e3-12b8abf2c797"
TASK_GRADE_SCORE_FIELDS = frozenset(f.name for f in fields(TaskGrade))


# ── fixtures ─────────────────────────────────────────────────────────────


def _verdict(evidence: str) -> str:
    return json.dumps({
        "verdict": "pass", "partial_score": 1.0, "evidence": evidence,
        "confidence": 0.9, "reasoning": "ok", "tool_calls_made": 0,
    })


def _response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        output=[{"type": "message",
                 "content": [{"type": "output_text", "text": text}]}],
        output_text="",
        usage=SimpleNamespace(
            input_tokens=80, output_tokens=20,
            input_tokens_details=SimpleNamespace(cached_tokens=5),
        ),
        incomplete_details=None,
        status=None,
    )


class ScriptedResponses:
    """Runs out loudly, which is how a test proves an item never started."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("ScriptedResponses ran out of responses")
        return self.script.pop(0)


def _grader(client, **kwargs) -> Grader:
    import core.grader as grader_mod

    prompt = (Path(grader_mod.__file__).resolve().parent.parent
              / "prompts" / "grader_judge.md")
    config = {
        "judge": {
            "provider": "azure_openai",
            "api_version": "2025-04-01-preview",
            "model": "gpt-5.4",
            "reasoning": {"effort": "medium"},
            "generation": {"max_output_tokens": 2400},
            "tools": {"read_deliverable": {
                "ops": ["inspect_structure", "read_content", "inspect_formatting"],
                "per_item_call_cap": 8, "max_iterations": 6}},
        },
        "prompt": {"template": str(prompt)},
        "grader": {"evidence_max_chars": 200},
        "tpm_guard": {},
    }
    return Grader(config, rubric_loader=None, client=client, **kwargs)


def _task(*criteria: str) -> TaskRubric:
    return TaskRubric(
        task_id=TASK_ID,
        sector="Information",
        occupation="Analyst",
        prompt="Write the report.",
        rubric_items=[
            RubricItem(f"r{n}", criterion, 5, None)
            for n, criterion in enumerate(criteria, start=1)
        ],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


def _item(rubric_item_id: str, **overrides) -> dict:
    """A finished item, as it would be serialized into a checkpoint.

    Carries its own usage numbers because that is where a resumed task's
    history actually lives: ``Grader._aggregate_tool_instrumentation`` sums
    the task's judge calls, tokens and latency from the items rather than
    from a running total, so restoring the items restores the arithmetic.
    """
    grade = ItemGrade(
        rubric_item_id=rubric_item_id,
        criterion=f"criterion for {rubric_item_id}",
        max_score=5,
        awarded_score=5.0,
        verdict="pass",
        decided_by="judge",
        required=None,
        evidence="seen in the report",
        judge_latency_ms=250.0,
        judge_call_count=1,
        judge_input_tokens=100,
        judge_output_tokens=40,
        judge_cached_tokens=10,
    )
    return {**asdict(grade), **overrides}


def _progress(**overrides) -> TaskProgress:
    base = dict(
        task_id=TASK_ID,
        grader_source_hash=HASH_A,
        rubric_fingerprint=rubric_order_fingerprint(["r1", "r2", "r3"]),
        completed_items=[_item("r1"), _item("r2")],
        perception_spent={"vision": 2, "audio": 1, "audio_failures": 1},
        precheck_count=1,
    )
    base.update(overrides)
    return TaskProgress(**base)


@pytest.fixture
def partial(tmp_path: Path) -> Path:
    """Where a shard's partial grade lives; the checkpoint hangs off it."""
    directory = tmp_path / "data" / "grades" / "_shards" / "gold_185"
    directory.mkdir(parents=True)
    return directory / "shard-004-of-011.json"


@pytest.fixture
def deliverable(tmp_path: Path) -> Path:
    directory = tmp_path / "task"
    directory.mkdir()
    (directory / "report.txt").write_text(
        "Total revenue 42. Prepared by the analyst on 3 March.",
        encoding="utf-8",
    )
    return directory


# ── a checkpoint is not a score (trap B-3) ───────────────────────────────


#: The fields that make a ``TaskGrade`` a mark rather than a record of work.
#: Named from the real type, so adding a score field there and copying it here
#: trips this rather than passing quietly.
SCORE_FIELDS = frozenset({
    "total_awarded", "total_max", "pct", "pct_raw", "critical_fail",
    "gold_referenced",
})


@pytest.mark.parametrize("holder", [TaskProgress, TaskProgressDraft])
def test_a_checkpoint_has_nowhere_to_put_a_score(holder):
    """Structural, not a convention.

    Half a rubric aggregated gives a number that looks like a mark and is not
    one — the items never reached would read as failures. The defence is that
    there is no field to put it in, so a later edit that wants to "just cache
    the running total" has to change the type and trip this.
    """
    present = {f.name for f in fields(holder)}
    assert not present & SCORE_FIELDS, (
        f"{holder.__name__} gained {present & SCORE_FIELDS}; a checkpoint "
        "shaped like a TaskGrade eventually gets read as one"
    )
    assert TASK_GRADE_SCORE_FIELDS >= SCORE_FIELDS, (
        "TaskGrade's scoring fields were renamed; this guard is now checking "
        "for fields that no longer exist"
    )


def test_the_shape_on_disk_carries_no_score_either(partial):
    """The type could stay clean while ``to_dict`` added a courtesy total."""
    written = json.loads(
        write_checkpoint(partial, _progress()).read_text(encoding="utf-8")
    )
    assert not set(written) & SCORE_FIELDS


def test_a_checkpoint_claiming_every_item_is_refused(partial):
    """Negative control for the guard above, from the reading side.

    A full item list is a *finished* task, and a finished task belongs in the
    partial as a grade. Accepting one here would mean a task graded twice —
    once as progress and once as a grade — or, worse, never graded at all
    because resume starts past its last item.
    """
    write_checkpoint(
        partial, _progress(completed_items=[_item("r1"), _item("r2"), _item("r3")])
    )
    with pytest.raises(CheckpointRejected, match="claims every item"):
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
        )


# ── a checkpoint names the grader that wrote it (trap B-2) ───────────────


def test_a_checkpoint_from_a_different_grader_is_refused(partial):
    """The guard the shard-level merge contract cannot provide.

    Between two chunks ``core/`` can change. A mismatched *shard* is caught by
    the merge and fails noisily. Items 1-30 graded at fingerprint X and 31-57
    at Y inside one task would emerge wearing only Y and the merge would pass
    it — the failure that succeeds quietly. So the task is re-marked whole.
    """
    write_checkpoint(partial, _progress(grader_source_hash=HASH_B))

    with pytest.raises(CheckpointRejected) as refused:
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
        )
    reason = refused.value.reason
    assert HASH_B[:16] in reason and HASH_A[:16] in reason, (
        "the log has to name both fingerprints; this refusal costs a "
        "full-price re-grade and someone will want to know why"
    )


def test_the_matching_fingerprint_is_what_makes_it_usable(partial):
    """Negative control: the same file, the only difference being the hash."""
    write_checkpoint(partial, _progress(grader_source_hash=HASH_A))
    resumed = load_checkpoint(
        partial, task_id=TASK_ID, grader_source_hash=HASH_A,
        rubric_item_ids=["r1", "r2", "r3"],
    )
    assert resumed is not None
    assert resumed.completed_item_ids == ["r1", "r2"]


def test_a_reordered_rubric_is_refused(partial):
    """Resume trusts a prefix, and a prefix of the old order is a scattering
    of the new one."""
    write_checkpoint(partial, _progress())
    with pytest.raises(CheckpointRejected, match="order changed"):
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r2", "r1", "r3"],
        )


def test_items_that_skip_one_are_refused(partial):
    """A skipped item resumed past is an item scored as never attempted."""
    write_checkpoint(
        partial,
        _progress(
            completed_items=[_item("r1"), _item("r3")],
            rubric_fingerprint=rubric_order_fingerprint(["r1", "r2", "r3"]),
        ),
    )
    with pytest.raises(CheckpointRejected, match="prefix"):
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
        )


def test_a_checkpoint_whose_body_names_another_task_is_refused(partial):
    """The filename says one task and the contents say another.

    Reachable because the filename is a *sanitised* task id: every character
    that is not alphanumeric becomes an underscore, so two ids can share a
    path. The guard is cheap and the failure it prevents is a task graded
    against another task's finished items, with matching rubric ids and a
    different deliverable.
    """
    path = checkpoint_path(partial, TASK_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_progress(task_id="some-other-task").to_dict()),
        encoding="utf-8",
    )

    with pytest.raises(CheckpointRejected, match="belongs to"):
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
        )


def test_an_older_format_is_refused_rather_than_migrated(partial):
    """Re-grading costs time and is always right; a migration guess is not."""
    path = write_checkpoint(partial, _progress())
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["format"] = "task-progress-v0"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(CheckpointRejected, match=CHECKPOINT_FORMAT):
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
        )


def test_a_truncated_checkpoint_is_refused_not_raised_through(partial):
    """The one failure the atomic write exists to avoid, met anyway."""
    path = checkpoint_path(partial, TASK_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"format": "task-progress-v1", "comple', encoding="utf-8")

    with pytest.raises(CheckpointRejected, match="unreadable"):
        load_checkpoint(
            partial, task_id=TASK_ID, grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
        )


def test_no_checkpoint_is_not_a_refusal(partial):
    """The ordinary first chunk. ``None`` and "I refused one" must not look
    the same to the driver: only the second is worth a line in the log."""
    assert load_checkpoint(
        partial, task_id=TASK_ID, grader_source_hash=HASH_A,
        rubric_item_ids=["r1", "r2", "r3"],
    ) is None


# ── where it lives, and what it does not contain ─────────────────────────


def test_two_shards_cannot_read_each_others_progress(tmp_path):
    """The path is derived from the partial, which already encodes the shard.

    Eleven shards grade disjoint slices concurrently. A shared progress
    directory would let one shard resume from another's items — same rubric
    ids, different deliverable — and nothing downstream would notice.
    """
    root = tmp_path / "data" / "grades" / "_shards" / "gold_185"
    root.mkdir(parents=True)
    four = checkpoint_path(root / "shard-004-of-011.json", TASK_ID)
    five = checkpoint_path(root / "shard-005-of-011.json", TASK_ID)
    assert four != five
    assert four.parent == five.parent == root / "_progress"


def test_a_task_id_cannot_escape_its_directory(tmp_path):
    """Task ids come from a pinned manifest, but they name a file here."""
    root = tmp_path / "grades"
    root.mkdir()
    path = checkpoint_path(root / "shard.json", "../../etc/passwd")
    assert path.parent == root / "_progress"
    assert ".." not in path.name


def test_the_judges_own_words_never_reach_disk(partial):
    """A checkpoint is written on the failure path and committed by CI.

    ``save_raw_responses`` already defaults false, which is exactly why this
    matters: the failure path is where a debugging flag is most likely to
    have been left switched on, and the artifact outlives the process.
    """
    path = write_checkpoint(
        partial,
        build_progress(
            task_id=TASK_ID,
            grader_source_hash=HASH_A,
            rubric_item_ids=["r1", "r2", "r3"],
            draft=TaskProgressDraft(
                completed_items=(
                    _item("r1", judge_raw_response="the model's reasoning"),
                ),
            ),
        ),
    )
    text = path.read_text(encoding="utf-8")
    assert "the model's reasoning" not in text
    assert json.loads(text)["completed_items"][0]["judge_raw_response"] is None


def test_the_write_leaves_no_half_file_behind(partial):
    write_checkpoint(partial, _progress())
    assert list(checkpoint_path(partial, TASK_ID).parent.glob("*.tmp")) == []


def test_a_graded_task_takes_its_checkpoint_with_it(partial):
    path = write_checkpoint(partial, _progress())
    assert path.exists()
    discard_checkpoint(partial, TASK_ID)
    assert not path.exists()
    discard_checkpoint(partial, TASK_ID)  # absent is not an error


def test_what_survives_the_round_trip_is_the_items_and_the_spend(partial):
    """And the prechecks, which are the one tally nothing else carries.

    A resumed task's judge calls, tokens and latency are not stored as totals
    — ``_aggregate_tool_instrumentation`` recomputes them from the items — so
    what has to survive is the per-item instrumentation, and it rides inside
    ``completed_items``. A precheck resolves an item without a judge call and
    is counted nowhere per-item, which is why it is here on its own.
    """
    write_checkpoint(partial, _progress())
    resumed = load_checkpoint(
        partial, task_id=TASK_ID, grader_source_hash=HASH_A,
        rubric_item_ids=["r1", "r2", "r3"],
    )
    assert resumed.precheck_count == 1
    assert resumed.perception_spent == {
        "vision": 2, "audio": 1, "audio_failures": 1
    }
    assert [item["judge_call_count"] for item in resumed.completed_items] == [1, 1]
    assert [item["judge_input_tokens"] for item in resumed.completed_items] == [100, 100]
    assert [item["judge_latency_ms"] for item in resumed.completed_items] == [250.0, 250.0]


# ── the caps are per task, not per attempt (trap B-1) ────────────────────


def test_a_resumed_task_does_not_get_its_looking_back():
    """Three resumes would otherwise buy nine images where a neighbour got
    three, and the two rubrics are then marked with different instruments."""
    vision = VisionPerception(client=object(), call_cap=3)
    vision._calls_used = 2

    vision.reset()                 # the task boundary, which a resume crosses
    assert vision.remaining_calls == 3
    vision.restore_spend(2)        # ... and what has to survive it
    assert vision.calls_used == 2
    assert vision.remaining_calls == 1


def test_a_resumed_task_does_not_get_its_listening_back():
    audio = AudioPerception(client=object(), call_cap=3, failure_budget=3)
    audio._calls_used = 2
    audio._failures_used = 1

    audio.reset()
    audio.restore_spend(2, failures_used=1)
    assert audio.calls_used == 2
    assert audio.failures_used == 1


def test_a_resumed_task_does_not_get_a_fresh_failure_budget():
    """Negative control for the second argument.

    Restoring only the calls hands every chunk a new failure budget, so a file
    the model keeps rejecting is retried three times per chunk forever instead
    of three times per task.
    """
    audio = AudioPerception(client=object(), call_cap=8, failure_budget=3)
    audio.restore_spend(2)
    assert audio.failures_used == 0, "the default must not invent spend"

    audio.reset()
    audio.restore_spend(2, failures_used=3)
    assert audio.failures_used == 3


@pytest.mark.parametrize("restored,expected", [(999, 3), (-4, 0)])
def test_restore_cannot_be_used_to_move_a_cap(restored, expected):
    """A checkpoint is a file on disk. It may not raise a budget, and it may
    not hand back calls by going negative."""
    vision = VisionPerception(client=object(), call_cap=3)
    vision.restore_spend(restored)
    assert vision.calls_used == expected

    audio = AudioPerception(client=object(), call_cap=3, failure_budget=3)
    audio.restore_spend(restored, failures_used=restored)
    assert audio.calls_used == expected
    assert audio.failures_used == expected


def test_the_judge_reports_both_caps_and_puts_them_back(tmp_path, deliverable):
    grader = _grader(SimpleNamespace(responses=ScriptedResponses([])))
    judge = grader._tool_judge
    judge.vision_perception = VisionPerception(client=object(), call_cap=8)
    judge.audio_perception = AudioPerception(
        client=object(), call_cap=8, failure_budget=3
    )
    judge.vision_perception._calls_used = 5
    judge.audio_perception._calls_used = 4
    judge.audio_perception._failures_used = 2

    spent = judge.perception_spend()
    assert spent == {"vision": 5, "audio": 4, "audio_failures": 2}

    judge.reset_perception()
    judge.restore_perception_spend(spent)
    assert judge.vision_perception.calls_used == 5
    assert judge.audio_perception.calls_used == 4
    assert judge.audio_perception.failures_used == 2


def test_an_absent_key_leaves_a_counter_alone(tmp_path):
    """A checkpoint written when audio was unwired must not silently zero the
    audio counter of a run that has it."""
    grader = _grader(SimpleNamespace(responses=ScriptedResponses([])))
    judge = grader._tool_judge
    judge.audio_perception = AudioPerception(client=object(), call_cap=8)
    judge.audio_perception._calls_used = 3

    judge.restore_perception_spend({"vision": 1})
    assert judge.audio_perception.calls_used == 3


def test_a_judge_with_no_sub_judges_reports_nothing(tmp_path):
    grader = _grader(SimpleNamespace(responses=ScriptedResponses([])))
    grader._tool_judge.vision_perception = None
    grader._tool_judge.audio_perception = None
    assert grader._tool_judge.perception_spend() == {}
    grader._tool_judge.restore_perception_spend({"vision": 4})  # no raise


# ── the grader: stopping, and starting again where it stopped ────────────


def test_the_deadline_hands_back_what_the_task_finished(deliverable):
    """Previously the exception carried nothing, so the items were lost."""
    responses = ScriptedResponses([_response(_verdict("revenue 42 present"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: len(responses.calls) >= 1

    with pytest.raises(GradingDeadlineExceeded) as expired:
        grader.grade_task(
            _task("The report states total revenue of 42",
                  "The report names the analyst",
                  "The report gives a date"),
            str(deliverable),
        )

    draft = expired.value.progress
    assert draft is not None, "an exception with no items is the old behaviour"
    assert [i["rubric_item_id"] for i in draft.completed_items] == ["r1"]
    kept = draft.completed_items[0]
    assert kept["judge_call_count"] == 1
    assert kept["judge_input_tokens"] == 80
    assert kept["judge_output_tokens"] == 20


def test_a_resumed_task_only_pays_for_the_items_it_has_left(deliverable):
    """One response for a three-item rubric.

    If the resumed run started at item one the scripted client would run out
    and raise, so "it skipped the finished items" is an assertion about
    behaviour rather than about a counter the test set itself.
    """
    responses = ScriptedResponses([_response(_verdict("dated 3 March"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: False

    grade = grader.grade_task(
        _task("The report states total revenue of 42",
              "The report names the analyst",
              "The report gives a date"),
        str(deliverable),
        resume_from=_progress(),
    )

    assert len(responses.calls) == 1
    assert [item.rubric_item_id for item in grade.items] == ["r1", "r2", "r3"]


def test_a_resumed_task_reports_the_whole_tasks_usage(deliverable):
    """The receipt is per task, so the numbers on the grade have to be too.

    Two items came back from the checkpoint carrying one judge call each and
    one more was marked here, so the task reports three — not the one this
    chunk paid for. Nothing adds a stored total: the arithmetic is redone
    over the items, which is why restoring the items is enough.
    """
    responses = ScriptedResponses([_response(_verdict("dated 3 March"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: False

    grade = grader.grade_task(
        _task("a", "b", "c"), str(deliverable), resume_from=_progress()
    )

    assert grade.judge_call_count == 3
    assert grade.judge_input_tokens == 100 + 100 + 80
    assert grade.judge_output_tokens == 40 + 40 + 20
    assert grade.judge_total_latency_ms >= 500.0, (
        "the two restored items' latency must still be in the total; the "
        "item marked here took a scripted client no measurable time"
    )
    assert grade.precheck_count == 1, (
        "prechecks are counted nowhere per-item, so the checkpoint is the "
        "only thing that can carry them across a chunk"
    )


def test_a_resumed_task_does_not_refill_its_perception_caps(deliverable):
    """The whole of trap B-1, through the public entry point.

    ``reset_perception`` still runs — the sub-judges cache images and
    transcripts per task and must not carry a previous task's into this one.
    What must survive it is the spend.
    """
    responses = ScriptedResponses([_response(_verdict("dated 3 March"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: False
    judge = grader._tool_judge
    judge.vision_perception = VisionPerception(client=object(), call_cap=8)
    judge.audio_perception = AudioPerception(
        client=object(), call_cap=8, failure_budget=3
    )

    grader.grade_task(
        _task("a", "b", "c"), str(deliverable), resume_from=_progress()
    )

    assert judge.vision_perception.calls_used == 2
    assert judge.audio_perception.calls_used == 1
    assert judge.audio_perception.failures_used == 1


def test_an_item_that_no_longer_fits_is_refused_by_name(deliverable):
    """Rather than a ``TypeError`` from a dataclass constructor forty frames
    from anything that explains it."""
    responses = ScriptedResponses([])
    grader = _grader(SimpleNamespace(responses=responses))

    with pytest.raises(CheckpointRejected, match="does not fit"):
        grader.grade_task(
            _task("a", "b", "c"),
            str(deliverable),
            resume_from=_progress(
                completed_items=[_item("r1", field_from_a_future_version=1)]
            ),
        )
    assert responses.calls == [], "nothing should have been paid for"


def test_the_draft_does_not_outlive_its_task(deliverable):
    """It closes over one task's items. Left installed, the next task's
    deadline would hand back the previous task's work."""
    responses = ScriptedResponses([_response(_verdict("revenue 42 present"))])
    grader = _grader(SimpleNamespace(responses=responses))
    grader.should_stop = lambda: False

    grader.grade_task(_task("The report states total revenue of 42"),
                      str(deliverable))
    assert grader._progress_draft is None

    responses.script.append(_response(_verdict("analyst named")))
    grader.should_stop = lambda: True
    with pytest.raises(GradingDeadlineExceeded) as expired:
        grader.grade_task(_task("The report names the analyst"),
                          str(deliverable))
    assert expired.value.progress.completed_items == ()
    assert grader._progress_draft is None


def test_grading_without_a_checkpoint_is_unchanged(deliverable):
    """Every other caller — the preflight, the analysis scripts, the tests —
    passes no ``resume_from`` and must keep marking from item one."""
    responses = ScriptedResponses([
        _response(_verdict("revenue 42 present")),
        _response(_verdict("analyst named")),
    ])
    grader = _grader(SimpleNamespace(responses=responses))

    grade = grader.grade_task(_task("a", "b"), str(deliverable))
    assert len(responses.calls) == 2
    assert len(grade.items) == 2


# ── the driver ───────────────────────────────────────────────────────────


def _main_body() -> list[ast.stmt]:
    tree = ast.parse(STEP8.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node.body
    raise AssertionError("step8_grade has no main")


def _local_node(name: str) -> ast.FunctionDef:
    for node in _main_body():
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"main has no local function {name!r}")


def _grade_loop() -> ast.For:
    for node in _main_body():
        if isinstance(node, ast.For) and "grade_task" in ast.unparse(node):
            return node
    raise AssertionError("main has no per-task grading loop")


def _lift(name: str, **environment):
    """Compile one of ``main``'s local functions on its own, against fakes.

    ``record_task_progress`` closes over the run's identity — the partial
    path, the grader fingerprint — so reaching it in place would mean standing
    up the whole driver, which needs a graded corpus and a live endpoint.
    Lifting the definition out of the syntax tree and giving it those names as
    globals runs the real body against fakes, which is the difference between
    testing what it does and testing that a string appears in it.
    """
    import hashlib
    import os
    import sys as _sys

    from core.task_checkpoint import build_progress as _build

    namespace = {
        "hashlib": hashlib, "os": os, "sys": _sys,
        "build_progress": _build, "write_checkpoint": write_checkpoint,
        "load_checkpoint": _load_checkpoint,
        "_write_github_output": lambda *_a, **_k: None,
        "_repo_relative_grade_file": lambda path: f"data/grades/{path.name}",
    }
    namespace.update(environment)
    module = ast.Module(body=[_local_node(name)], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), STEP8.name, "exec"),
         namespace)
    return namespace[name]


def _recorder(partial: Path, **environment):
    return _lift(
        "record_task_progress",
        out_path=partial, grader_source_hash=HASH_A, **environment
    )


def test_the_driver_files_the_items_a_cut_short_task_finished(partial):
    record = _recorder(partial)
    advanced = record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2", "r3"],
        TaskProgressDraft(completed_items=(_item("r1"), _item("r2"))), 0,
    )

    assert advanced == 2
    stored = json.loads(
        checkpoint_path(partial, TASK_ID).read_text(encoding="utf-8")
    )
    assert stored["grader_source_hash"] == HASH_A
    assert [i["rubric_item_id"] for i in stored["completed_items"]] == ["r1", "r2"]


def test_a_chunk_that_re_read_the_same_items_has_not_moved(partial):
    """Negative control for the resume arithmetic.

    A chunk that resumed at item 30 and stopped at item 30 finished nothing.
    Writing the same file again and calling it progress would let the shard
    buy chunk after chunk on the strength of work an earlier one paid for.
    """
    record = _recorder(partial)
    advanced = record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2", "r3"],
        TaskProgressDraft(completed_items=(_item("r1"), _item("r2"))), 2,
    )
    assert advanced == 0
    assert not checkpoint_path(partial, TASK_ID).exists()


def test_the_driver_refuses_to_file_a_complete_rubric(partial, capsys):
    """Trap B-3 from the writing side. ``load_checkpoint`` refuses one too;
    refusing here means the contradiction never reaches disk."""
    record = _recorder(partial)
    advanced = record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2"],
        TaskProgressDraft(completed_items=(_item("r1"), _item("r2"))), 0,
    )
    assert advanced == 0
    assert not checkpoint_path(partial, TASK_ID).exists()
    assert "refusing to file a complete rubric" in capsys.readouterr().err


def test_a_deadline_with_no_draft_is_the_old_behaviour(partial):
    """A grader that hands back nothing must not become an error path."""
    record = _recorder(partial)
    assert record(SimpleNamespace(task_id=TASK_ID), ["r1"], None, 0) == 0


def test_a_progress_write_that_fails_does_not_lose_the_partial(partial, capsys):
    """The partial is the artifact that has to persist, and it already has.

    Losing a chunk's finished *tasks* to a full disk in the progress directory
    would be a strictly worse outcome than losing its finished items.
    """
    def _explode(*_a, **_k):
        raise OSError("no space left on device")

    record = _recorder(partial, write_checkpoint=_explode)
    advanced = record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2", "r3"],
        TaskProgressDraft(completed_items=(_item("r1"),)), 0,
    )
    assert advanced == 0
    assert "could not save progress" in capsys.readouterr().err


def test_progress_that_cannot_be_committed_does_not_count_as_movement(
    partial, monkeypatch, capsys
):
    """Under a workflow, an unpublished pointer means an uncommitted file.

    The next chunk gets a fresh runner and will not find it. Asking for a paid
    resume on the strength of progress that will not be there is the
    dishonest half of this feature.
    """
    monkeypatch.setenv("GITHUB_OUTPUT", "/tmp/github-output")

    def _outside_the_repo(_path):
        raise ValueError("grade output path must remain inside the repository")

    record = _recorder(partial, _repo_relative_grade_file=_outside_the_repo)
    advanced = record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2", "r3"],
        TaskProgressDraft(completed_items=(_item("r1"),)), 0,
    )
    assert advanced == 0
    assert "does not count as having moved" in capsys.readouterr().err


def test_the_same_failure_outside_a_workflow_still_counts(
    partial, monkeypatch, capsys
):
    """Negative control. Locally there is no ``GITHUB_OUTPUT`` and no commit
    step, the file is on disk in the same working tree the next chunk reads,
    and denying credit would strand a local resume for no reason."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

    def _outside_the_repo(_path):
        raise ValueError("grade output path must remain inside the repository")

    record = _recorder(partial, _repo_relative_grade_file=_outside_the_repo)
    advanced = record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2", "r3"],
        TaskProgressDraft(completed_items=(_item("r1"),)), 0,
    )
    assert advanced == 1
    assert checkpoint_path(partial, TASK_ID).exists()


def test_the_pointer_is_published_so_the_workflow_can_commit_it(partial):
    """A file the commit step never adds is a file the next chunk never sees —
    the exact way every shard's cost ledger was silently dropped."""
    published = {}
    record = _recorder(
        partial,
        _write_github_output=lambda name, value: published.__setitem__(name, value),
    )
    record(
        SimpleNamespace(task_id=TASK_ID), ["r1", "r2", "r3"],
        TaskProgressDraft(completed_items=(_item("r1"),)), 0,
    )

    assert set(published) == {"grade_progress_file", "grade_progress_sha256"}
    import hashlib
    assert published["grade_progress_sha256"] == hashlib.sha256(
        checkpoint_path(partial, TASK_ID).read_bytes()
    ).hexdigest()


def test_a_chunk_that_advanced_items_may_buy_another_one():
    """The change that makes the rest of this feature reachable.

    ``out_of_time_exit`` refused to request a paid resume unless a whole
    *task* completed. For ``9e39df84`` a chunk that advances items 1→30
    completes zero tasks, so without this the checkpoint would be written
    perfectly and the shard would still die in the same place.
    """
    body = ast.unparse(_local_node("out_of_time_exit"))
    assert "items_advanced" in body
    assert "graded_count <= initial_completed_count and items_advanced <= 0" in body
    assert "GRADE_EXIT_PERSISTENCE_FAILURE" in body, (
        "a chunk that moved neither a task nor an item still must not ask "
        "for another one"
    )


def test_the_loop_loads_resumes_records_and_discards():
    loop = ast.unparse(_grade_loop())
    assert "load_checkpoint" in loop
    assert "resume_from=resume_progress" in loop
    assert "record_task_progress" in loop
    assert "items_advanced=advanced" in loop
    assert "discard_checkpoint" in loop


def test_a_cut_short_task_is_still_never_filed_as_a_grade():
    """Unchanged, and the reason the checkpoint had to exist separately: a
    half-marked task scored on what it reached reads as failing the rest."""
    handler = next(
        h for h in ast.walk(_grade_loop())
        if isinstance(h, ast.ExceptHandler)
        and "GradingDeadlineExceeded" in ast.unparse(h.type or ast.Constant(None))
    )
    body = ast.unparse(handler)
    assert "task_payloads.append" not in body
    assert "out_of_time_exit" in body


def test_a_refused_checkpoint_is_said_out_loud():
    """It means a fingerprint or a rubric moved under a paid run, and the task
    is about to be re-marked from item one at full price."""
    loop = ast.unparse(_grade_loop())
    assert "except CheckpointRejected" in loop
    handler = next(
        h for h in ast.walk(_grade_loop())
        if isinstance(h, ast.ExceptHandler)
        and "CheckpointRejected" in ast.unparse(h.type or ast.Constant(None))
    )
    assert "print" in ast.unparse(handler)


def test_the_workflow_commits_the_progress_file():
    """Written by the driver, read by nobody, is the shape of this bug.

    Each chunk gets a fresh runner. A checkpoint left in the workspace is gone
    before the next chunk looks for it, so the commit step has to add it by
    name — and verify the digest step8 published, like it does for the ledger.
    """
    workflow = (STEP8.parent.parent / ".github" / "workflows" / "grade-run.yml")
    text = workflow.read_text(encoding="utf-8")
    assert "GRADE_PROGRESS_FILE: ${{ steps.grade.outputs.grade_progress_file }}" in text
    assert 'git add -- "$GRADE_PROGRESS_FILE"' in text
    assert '"$PROGRESS_BLOB_SHA" != "$GRADE_PROGRESS_SHA256"' in text
