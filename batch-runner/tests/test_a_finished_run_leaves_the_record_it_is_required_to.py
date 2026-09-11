"""The record a run is required to leave, checked against a run that happened.

``REQUIRED_RUN_RECORD_FIELDS`` has named nineteen things since it was written,
and ``check_run_record_fields`` has verified them. What it verified was key
presence, and the only thing ever handed to it was
``{name: "recorded" for name in REQUIRED_RUN_RECORD_FIELDS}`` -- a dictionary
built from the list it is checked against, which cannot fail. The requirement
was real; the test of it was a tautology.

These tests are built on an artifact instead. ``tests/fixtures/run_record/``
holds four files from run ``34528903950`` (exp033, five tasks, two succeeded,
three failed), trimmed of the model's prose and of the reference-file payloads
but otherwise verbatim: the ledger's nine rows are the nine rows that were
written, the timestamps are the timestamps, and the hashes are of the text
that actually went to the model. A record assembled from invented inputs would
pass any assertion written about invented inputs.

The central test here pins *how many* of the nineteen a real run can fill.
That number is the gap stated as a measurement rather than a claim, and it is
meant to move: when ``items_seen`` starts arriving it goes up by one, and the
test says so out loud rather than silently passing on a better run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution_environment_readiness import (
    REQUIRED_RUN_RECORD_FIELDS,
    check_run_record_fields,
)
from core.run_record import (
    FILE_CHECKS_PERFORMED,
    PRE_STREAM_FAILURE_CATEGORIES,
    RUN_RECORD_SCHEMA,
    build_run_record,
    is_recorded,
    not_recorded,
    unrecorded_fields,
)

FIXTURE = Path(__file__).parent / "fixtures" / "run_record"

#: What run 34528903950 could and could not write down.
#:
#: Not a target and not a score. A run where every task fails can fill all
#: nineteen and a run that goes perfectly can fill few; this counts
#: instrumentation, not outcome. Two of the three absences are expected to
#: outlive this file -- see the individual tests -- and one is expected to go
#: away on its own.
RECORDED_FOR_THIS_RUN = 16
UNRECORDED_FOR_THIS_RUN = [
    "executed_code_version",
    "external_grade",
    "tool_run_count",
]


def _load(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def _ledger() -> list[dict]:
    text = (FIXTURE / "cost_ledger_condition_a.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@pytest.fixture
def artifact() -> dict:
    return {
        "results": _load("step2_inference_results.json"),
        "prepared": _load("step1_tasks_prepared.json"),
        "manifest": _load("step0_needs_files_manifest.json"),
        "ledger_rows": _ledger(),
    }


@pytest.fixture
def record(artifact) -> dict:
    return build_run_record(**artifact)


# ── the fixture is the run it claims to be ─────────────────────────────────


def test_the_fixture_is_a_real_run_not_a_sketch(artifact):
    """If this drifts into invented data, every test below is worthless."""
    results = artifact["results"]
    assert results["experiment_id"] == "exp033_codex_foundry_fixed5"
    assert results["run_id"] == "exp033_codex_foundry_fixed5:34528903950:1"
    assert len(results["ordered_task_ids"]) == 5
    assert len(artifact["prepared"]["tasks"]) == 5
    assert len(artifact["ledger_rows"]) == 9
    assert (
        artifact["manifest"]["_source_revision"]
        == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    )


# ── the measured gap ───────────────────────────────────────────────────────


def test_every_required_field_has_a_place_in_the_record(record):
    assert [name for name in REQUIRED_RUN_RECORD_FIELDS if name not in record] == []
    assert check_run_record_fields(record) == []


def test_how_much_of_the_required_record_a_real_run_can_fill(record):
    """The gap as a number, so it can be watched rather than asserted about.

    Raising ``RECORDED_FOR_THIS_RUN`` is the visible decision this pin asks
    for. A change that makes a field fillable should move it here in the same
    commit and say which field and why.
    """
    assert unrecorded_fields(record) == UNRECORDED_FOR_THIS_RUN
    recorded = sum(1 for name in REQUIRED_RUN_RECORD_FIELDS if is_recorded(record[name]))
    assert recorded == RECORDED_FOR_THIS_RUN
    assert recorded + len(UNRECORDED_FOR_THIS_RUN) == len(REQUIRED_RUN_RECORD_FIELDS)


def test_presence_alone_is_not_evidence_for_eighteen_of_the_nineteen(record):
    """How far the existing check gets on a record that measured nothing.

    A record where every field is an empty marker is caught for exactly one
    field out of nineteen. ``check_run_record_fields`` asks
    ``retry_counts_by_reason`` to be a mapping counting all three reasons, and
    a marker is not; for the other eighteen it asks only whether the key
    exists, which a marker -- or the literal string ``"recorded"`` -- answers.

    So the check is not useless and it is not sufficient, and the ratio is the
    point. ``unrecorded_fields`` is the complement: it finds all nineteen.
    """
    hollow = {
        name: not_recorded("nothing was measured") for name in REQUIRED_RUN_RECORD_FIELDS
    }
    caught = check_run_record_fields(hollow)
    assert len(caught) == 1
    assert "retry reasons" in caught[0]

    assert unrecorded_fields(hollow) == sorted(REQUIRED_RUN_RECORD_FIELDS)
    assert unrecorded_fields(record) != sorted(REQUIRED_RUN_RECORD_FIELDS)


def test_the_string_recorded_still_passes_the_existing_check(record):
    """The shape the old callers used, kept visible.

    Nothing is wrong with this check; it was simply never given a real record
    to check. Written down so that a future reader can see what "the record
    passes" used to be worth on its own.
    """
    nominal = {name: "recorded" for name in REQUIRED_RUN_RECORD_FIELDS}
    nominal["retry_counts_by_reason"] = {
        "infrastructure_error": 0,
        "model_self_review": 0,
        "tool_loop_internal_recovery": 0,
    }
    assert check_run_record_fields(nominal) == []
    assert check_run_record_fields(record) == []


def test_a_field_cannot_be_left_empty_without_saying_why():
    with pytest.raises(ValueError):
        not_recorded("")
    with pytest.raises(ValueError):
        not_recorded("   ")


# ── cost: the field most likely to be misread ──────────────────────────────


def test_an_unknown_cost_is_never_reported_as_zero(record):
    """The receipt said ``partial``. The record says ``partial``.

    This run's ``known_cost_usd`` is 0.0 -- the sum of the calls that could be
    priced, of which there were none, because the deployment is absent from
    the price table. Collapsing the field to that number would turn "nobody
    knows what this cost" into "this cost nothing", which is the single most
    expensive misreading available here.
    """
    cost = record["model_cost"]
    assert cost["status"] == "partial"
    assert cost["estimated_cost_usd"] is None
    assert cost["missing_reasons"] == ["call_reachability_unknown"]
    assert cost["known_cost_usd"] == 0.0
    assert cost["model_calls"] == 9


def test_the_cost_receipt_is_copied_rather_than_recomputed(record, artifact):
    """No arithmetic between the run's receipt and the record.

    A total recomputed here could disagree with the one the run wrote, and
    then two documents about the same money would say different things.
    """
    assert record["model_cost"] == artifact["results"]["summary"]["problem_solving_cost"]


def test_cost_and_completion_are_separate_fields(record):
    """A run can cost money and finish nothing; the record keeps them apart."""
    assert record["task_completed"]["counts_by_status"] == {"error": 3, "success": 2}
    assert "status" not in record["task_completed"]
    assert "task_completed" not in record["model_cost"]


# ── grading stays out ──────────────────────────────────────────────────────


def test_the_solving_record_carries_no_grade_and_says_that_is_on_purpose(record):
    """The absence that must not be "fixed".

    Marking is its own run with its own model calls and its own money. A grade
    stored in the solving record is how the two costs end up added together by
    somebody reading in good faith a year from now.
    """
    grade = record["external_grade"]
    assert is_recorded(grade) is False
    assert "separate" in grade["reason"]
    flat = json.dumps(record).lower()
    for word in ("grade_score", "rubric", "judge_model", "grading_cost"):
        assert word not in flat


# ── what the file checks are allowed to claim ──────────────────────────────


def test_the_file_checks_claim_only_what_collection_proved(record):
    """Existence, a hash and a size. Not that the file is any good."""
    results = record["produced_file_check_results"]
    assert results["checks_performed"] == list(FILE_CHECKS_PERFORMED)
    assert results["files_with_every_check"] == 3
    assert results["files_missing_a_check"] == []
    vocabulary = " ".join(FILE_CHECKS_PERFORMED).lower()
    for overclaim in ("valid", "correct", "content", "opens", "renders", "schema"):
        assert overclaim not in vocabulary


def test_produced_files_shows_the_tasks_that_made_nothing(record):
    """Three files from two tasks; the other three produced nothing at all."""
    produced = record["produced_files"]
    assert produced["file_count"] == 3
    assert len(produced["tasks_with_no_file"]) == 3
    for task_id in produced["tasks_with_no_file"]:
        assert record["task_completed"]["by_task"][task_id] == "error"
    for files in produced["by_task"].values():
        for item in files:
            assert isinstance(item["sha256"], str) and len(item["sha256"]) == 64
            assert isinstance(item["size"], int) and item["size"] > 0


# ── the model that answered, versus the model that was asked for ───────────


def test_the_record_keeps_the_requested_and_the_resolved_model_apart(record):
    """Counted by what answered, never by what was asked for.

    They agree on this run. The field is shaped so that a run where they
    disagree is readable as such, because a silent substitution is a cost and
    a result finding at once.
    """
    model = record["model_and_deployment"]
    assert model["requested"]["deployment"] == "gpt-5.4"
    assert model["requested"]["provider"] == "azure"
    assert model["resolved_by_provider"] == ["gpt-5.4"]
    assert model["execution_mode"] == "codex_foundry"
    assert model["api_versions"] == ["v1"]


def test_a_call_that_was_made_and_not_receipted_is_visible(artifact):
    """Two counts of the same thing, and a flag when they differ."""
    honest = build_run_record(**artifact)
    assert honest["model_call_count"] == {
        "from_cost_receipt": 9,
        "from_cost_ledger": 9,
        "agree": True,
    }

    artifact["ledger_rows"] = artifact["ledger_rows"] + [
        {"record_type": "call", "task_id": "unreceipted", "state": "settled"}
    ]
    divergent = build_run_record(**artifact)
    assert divergent["model_call_count"]["from_cost_ledger"] == 10
    assert divergent["model_call_count"]["from_cost_receipt"] == 9
    assert divergent["model_call_count"]["agree"] is False


# ── the prompts, by hash ───────────────────────────────────────────────────


def test_the_instructions_are_pinned_by_hash_that_rehashes_to_the_same_value(
    record, artifact
):
    """The record hashes; the prepared file beside it holds the text.

    At 220 tasks the text itself would make the record unopenable. A hash is
    what re-checking needs, and this test does the re-check.
    """
    import hashlib

    digests = record["task_instruction"]
    assert len(digests) == 5
    for task in artifact["prepared"]["tasks"]:
        expected = hashlib.sha256(task["instruction"].encode("utf-8")).hexdigest()
        assert digests[task["task_id"]]["sha256"] == expected
        assert digests[task["task_id"]]["characters"] == len(task["instruction"])

    system = record["system_instruction"]
    assert system["sha256"] == hashlib.sha256(
        artifact["prepared"]["condition_a"]["prompt"]["system"].encode("utf-8")
    ).hexdigest()
    assert system["characters"] == len(system["text"])


def test_the_task_list_and_the_dataset_revision_are_both_recorded(record, artifact):
    assert record["task_ids"] == artifact["results"]["ordered_task_ids"]
    inputs = record["input_file_versions"]
    assert inputs["dataset"] == "openai/gdpval"
    assert inputs["dataset_revision"] == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert len(inputs["ordered_task_ids_sha256"]) == 64
    assert set(inputs["reference_files_by_task"]) == set(record["task_ids"])


# ── time ───────────────────────────────────────────────────────────────────


def test_the_duration_comes_from_the_two_timestamps(record):
    assert record["started_at"] == "2026-09-10T20:56:03.051760+00:00"
    assert record["finished_at"] == "2026-09-10T21:10:24.116173+00:00"
    assert record["total_seconds"] == pytest.approx(861.06, abs=0.01)


def test_an_unusable_timestamp_gives_no_duration_rather_than_zero(artifact):
    """Zero is a duration. The absence of one is not.

    A run recorded as having taken no time would pass a "did we record it"
    check and then poison every rate computed from it.
    """
    artifact["results"] = dict(artifact["results"], completed_at="not a timestamp")
    record = build_run_record(**artifact)
    assert is_recorded(record["total_seconds"]) is False
    assert record["total_seconds"] != 0


# ── retries, by the reason they happened ───────────────────────────────────


def test_retries_are_counted_by_reason_and_match_the_ledger(record, artifact):
    counts = record["retry_counts_by_reason"]
    assert counts["infrastructure_error"] == 4
    assert counts["model_self_review"] == 0
    assert counts["tool_loop_internal_recovery"] == 0
    assert counts["unmapped_retry_kinds"] == {}

    hand_counted = sum(
        1
        for row in artifact["ledger_rows"]
        if row.get("retry_kind") not in (None, "", "none")
    )
    assert counts["infrastructure_error"] == hand_counted


# ── items_seen, and the zeroes that are not counts ─────────────────────────


def test_this_run_predates_items_seen_and_says_so_rather_than_reporting_zero(record):
    seen = record["tool_run_count"]
    assert is_recorded(seen) is False
    assert "absent rather than zero" in seen["reason"]


def test_a_turn_that_never_opened_is_not_counted_as_having_produced_nothing(artifact):
    """The dataclass default, told apart from a measurement.

    ``codex_runner`` builds four outcomes without passing ``items_seen``, and
    the field defaults to 0. Summing those zeroes in would drag the total
    toward "these turns produced nothing" on the strength of a value nobody
    took.
    """
    results = dict(artifact["results"])
    tasks = [dict(task) for task in results["results"]]
    tasks[0]["items_seen"] = 0
    tasks[0]["status"] = "error"
    tasks[0]["observability"] = {"error_category": "runtime_unavailable"}
    tasks[1]["items_seen"] = 42
    tasks[1]["status"] = "success"
    results["results"] = tasks
    artifact["results"] = results

    seen = build_run_record(**artifact)["tool_run_count"]
    assert seen["total"] == 42
    assert tasks[0]["task_id"] in seen["tasks_whose_turn_never_opened"]
    assert tasks[0]["task_id"] not in seen["by_task"]


def test_a_run_where_no_turn_ever_opened_records_nothing_rather_than_zero(artifact):
    results = dict(artifact["results"])
    results["results"] = [
        dict(
            task,
            items_seen=0,
            status="error",
            observability={"error_category": "session_start_failed"},
        )
        for task in results["results"]
    ]
    artifact["results"] = results

    seen = build_run_record(**artifact)["tool_run_count"]
    assert is_recorded(seen) is False
    assert "default rather than a count" in seen["reason"]


def test_the_two_copies_of_the_pre_stream_set_have_not_drifted():
    """``scripts/analyze_codex_run.py`` keeps its own copy of this set.

    Two lists of the same four strings in two files is how a fifth category
    gets added to one of them. This fails when they diverge.
    """
    import importlib.util

    script = Path(__file__).parents[1] / "scripts" / "analyze_codex_run.py"
    spec = importlib.util.spec_from_file_location("_analyze_codex_run", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PRE_STREAM_FAILURE_CATEGORIES == PRE_STREAM_FAILURE_CATEGORIES


# ── the commit that ran ────────────────────────────────────────────────────


def test_the_code_version_is_supplied_or_explicitly_unknown(artifact):
    """Never inferred from whichever checkout this happens to run in.

    That inference would produce a forty-character hex string in a field
    called ``executed_code_version`` that names a commit the run never saw.
    """
    without = build_run_record(**artifact)
    assert is_recorded(without["executed_code_version"]) is False

    with_sha = build_run_record(**artifact, code_version="e0caa9e" + "0" * 33)
    assert with_sha["executed_code_version"] == "e0caa9e" + "0" * 33
    assert "executed_code_version" not in unrecorded_fields(with_sha)


# ── failure, kept separable from defect ────────────────────────────────────


def test_each_unfinished_task_keeps_the_provider_category_beside_the_error(record):
    """The pipeline's error does not distinguish these three. The category does.

    All three failures in this run carry the identical error string,
    ``task_execution_error:TaskExecutionError``. On that alone the run looks
    like three of the same thing. The categories say otherwise: two turns
    failed and one was rate-limited, and those are not the same finding. A
    rate limit is our run place failing to reach the model -- a defect to fix.
    A failed turn is the model's own attempt not working -- a benchmark
    result, to be preserved rather than engineered away.

    Storing only the error would have made that distinction unrecoverable
    without re-running, which at these prices means never.
    """
    failures = record["failure_stage_and_reason"]
    assert failures["unfinished_task_count"] == 3
    for task_id, detail in failures["by_task"].items():
        assert record["task_completed"]["by_task"][task_id] != "success"
        assert set(detail) >= {
            "status",
            "error",
            "error_category",
            "failure_evidence",
            "ledger_states",
        }

    assert {d["error"] for d in failures["by_task"].values()} == {
        "task_execution_error:TaskExecutionError"
    }
    categories = sorted(d["error_category"] for d in failures["by_task"].values())
    assert categories == ["rate_limited", "turn_failed", "turn_failed"]


def test_successful_tasks_are_not_listed_as_failures(record):
    failures = set(record["failure_stage_and_reason"]["by_task"])
    succeeded = {
        task_id
        for task_id, status in record["task_completed"]["by_task"].items()
        if status == "success"
    }
    assert failures & succeeded == set()


# ── isolation: an honest partial ───────────────────────────────────────────


def test_the_isolation_field_claims_only_what_the_artifact_proves(record):
    """The run place's real isolation is not written into any artifact.

    Rewritten ``HOME``, named-only environment inheritance and a per-task
    working directory are all real and none of them appear in a result file.
    Claiming them from configuration would be describing intent as evidence.
    """
    isolation = record["isolation_and_security"]
    assert isolation["execution_mode"] == "codex_foundry"
    assert isolation["route_profiles"] == ["direct-v1"]
    assert isolation["per_turn_timeout_seconds"] == 1800
    assert "not written into any artifact" in isolation["evidence_note"]


# ── shape ──────────────────────────────────────────────────────────────────


def test_the_record_names_its_schema_and_the_run_it_describes(record):
    assert record["schema_version"] == RUN_RECORD_SCHEMA
    assert record["experiment_id"] == "exp033_codex_foundry_fixed5"
    assert record["run_id"] == "exp033_codex_foundry_fixed5:34528903950:1"


def test_the_record_round_trips_through_json(record):
    """It is written to a file; anything unserialisable fails there, not here."""
    assert json.loads(json.dumps(record, ensure_ascii=False)) == record


# ── the command that produces it ───────────────────────────────────────────
#
# `batch-runner/scripts/*` is ignored and each script is re-admitted by name,
# so a new one is invisible to git until a line is added for it. A CLI that is
# on disk, hand-verified and absent from the repository looks exactly like a
# CLI that works. These drive the script itself, so its disappearance is a
# failure rather than a silence.


def _cli():
    """Import ``scripts/build_run_record.py`` as a module."""
    import importlib.util

    script = Path(__file__).parents[1] / "scripts" / "build_run_record.py"
    assert script.is_file(), f"the CLI is missing from the repository: {script}"
    spec = importlib.util.spec_from_file_location("_build_run_record_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_command_reads_the_same_run_the_library_was_given(record):
    """The fixture directory is shaped like an unpacked artifact; use it as one.

    If the finder resolved a different file than the one the library tests are
    written against, every assertion above would still pass and the command
    would still be wrong.
    """
    assert _cli().record_from_artifact(FIXTURE) == record


def test_the_command_stops_rather_than_recording_an_absence_it_invented(tmp_path):
    """Three files present and one missing is not a run that recorded less.

    Defaulting the fourth to empty would turn "this script did not look hard
    enough" into "the run did not write this down", which is the one confusion
    the whole record exists to prevent.
    """
    for name in (
        "step2_inference_results.json",
        "step1_tasks_prepared.json",
        "step0_needs_files_manifest.json",
    ):
        (tmp_path / name).write_bytes((FIXTURE / name).read_bytes())

    with pytest.raises(SystemExit) as raised:
        _cli().record_from_artifact(tmp_path)
    assert "cost_ledger" in str(raised.value)


def test_a_run_with_both_ledgers_is_recorded_from_the_condition_it_ran(tmp_path):
    """A multi-condition run leaves ``cost_ledger.jsonl`` beside the suffixed one.

    Preferring the bare file would silently record condition A's tasks against
    whatever the combined ledger holds. The order in ``ARTIFACT_NAMES`` is the
    only thing deciding that, and order is easy to tidy away.
    """
    for name in (
        "step2_inference_results.json",
        "step1_tasks_prepared.json",
        "step0_needs_files_manifest.json",
        "cost_ledger_condition_a.jsonl",
    ):
        (tmp_path / name).write_bytes((FIXTURE / name).read_bytes())
    (tmp_path / "cost_ledger.jsonl").write_text("", encoding="utf-8")

    cli = _cli()
    assert cli.ARTIFACT_NAMES["ledger"][0] == "cost_ledger_condition_a.jsonl"
    from_artifact = cli.record_from_artifact(tmp_path)
    assert is_recorded(from_artifact["model_call_count"])
    assert from_artifact["model_call_count"]["from_cost_ledger"] == 9


def test_supplying_the_commit_is_what_turns_that_field_into_a_measurement(tmp_path):
    """``executed_code_version`` is unrecorded because nothing on disk holds it.

    Not because it is unrecordable. The caller who knows the sha passes it and
    the count goes up by one; that is the difference between a gap and a
    limitation.
    """
    cli = _cli()
    without = cli.record_from_artifact(FIXTURE)
    with_sha = cli.record_from_artifact(FIXTURE, code_version="e0caa9e")

    assert "executed_code_version" in unrecorded_fields(without)
    assert "executed_code_version" not in unrecorded_fields(with_sha)
    assert len(unrecorded_fields(with_sha)) == len(UNRECORDED_FOR_THIS_RUN) - 1


def test_the_summary_never_prints_an_undetermined_cost_as_zero(record, capsys):
    """A dollar figure nobody could compute is not a dollar figure of nothing."""
    record = dict(record)
    record["model_cost"] = {
        "status": "partial",
        "estimated_cost_usd": None,
        "missing_reasons": ["deployment absent from the price table"],
    }
    _cli().summarise(record)

    out = capsys.readouterr().out
    assert "estimated_usd=None" in out
    assert "estimated_usd=0" not in out
    assert "UNDETERMINED" in out
    assert "That is not zero." in out
    assert "deployment absent from the price table" in out


def test_the_summary_says_the_record_covers_solving_only(record, capsys):
    """Solving cost and grading cost are never added together."""
    _cli().summarise(record)
    out = capsys.readouterr().out
    assert "covers solving only" in out
    assert "never added together" in out


def test_the_command_writes_the_record_where_it_says_it_will(tmp_path, record):
    for name in (
        "step2_inference_results.json",
        "step1_tasks_prepared.json",
        "step0_needs_files_manifest.json",
        "cost_ledger_condition_a.jsonl",
    ):
        (tmp_path / name).write_bytes((FIXTURE / name).read_bytes())

    output = tmp_path / "run_record.json"
    assert _cli().main([str(tmp_path)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == record


def test_the_commit_the_caller_passes_reaches_the_file_that_is_written(tmp_path):
    """CI passes ``--code-version $GITHUB_SHA``; nothing else ever will.

    Checking only that ``record_from_artifact`` honours the argument leaves
    the wiring between the flag and that call untested, and a record written
    in CI would then say "no artifact records the commit" on every run while
    the workflow believed it was supplying one.
    """
    for name in (
        "step2_inference_results.json",
        "step1_tasks_prepared.json",
        "step0_needs_files_manifest.json",
        "cost_ledger_condition_a.jsonl",
    ):
        (tmp_path / name).write_bytes((FIXTURE / name).read_bytes())

    output = tmp_path / "elsewhere.json"
    assert (
        _cli().main([str(tmp_path), "--code-version", "e0caa9e", "--output", str(output)])
        == 0
    )
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["executed_code_version"] == "e0caa9e"
    assert "executed_code_version" not in unrecorded_fields(written)
