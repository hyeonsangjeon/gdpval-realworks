"""Assemble the record a finished run is required to leave behind.

``execution_environment_readiness`` has said since it was written that a run
must write down nineteen things -- ``REQUIRED_RUN_RECORD_FIELDS`` -- and
``check_run_record_fields`` checks that they are there. Nothing built one. The
only thing ever handed to that check is a dictionary the tests assemble from
the list it is checked against, ``{name: "recorded" for name in
REQUIRED_RUN_RECORD_FIELDS}``, with one key overwritten by a real-shaped
value.

That one key is the exception worth being exact about, because the check is
not quite the tautology it looks like. For eighteen of the nineteen fields it
asks only whether the key exists, so the literal string ``"recorded"``
satisfies it. For ``retry_counts_by_reason`` it asks more -- that the value be
a mapping counting all three of ``RETRY_REASONS`` separately -- which is why
the test helper has to special-case it. So one field of nineteen was being
checked for content, and eighteen were being checked for spelling.

This module builds the record from what a run actually leaves on disk. The
shape of the problem is not the one the missing producer suggests, and that is
worth stating because it changes what had to be written. Grepping the nineteen
names through the code finds eleven with no producer anywhere, which reads as
"the pipeline records almost nothing". Opening a real finished run says
otherwise. Taking run ``34528903950`` -- exp033, five tasks, two succeeded --
its four artifacts between them hold the deployment, the route fingerprint,
the system instruction, every task instruction, the dataset revision the inputs
came from, both timestamps, a per-call cost ledger with token counts and a
retry kind on every row, and a sha256 and byte size for every file the model
produced. What was missing was not the measurements. It was anything that
gathered them into the record the repository says it requires.

So most of what follows is arithmetic and lookup rather than instrumentation,
and the fields that genuinely cannot be filled are the interesting output. They
are not left out -- a missing key would read as an oversight -- and they are
not filled with a plausible-looking default, which is worse: they carry
``not_recorded(reason)``, and ``unrecorded_fields`` lists them. Two of the
three have nothing to do with each other and must not be read the same way:

``external_grade`` is absent **on purpose**. Marking is a separate step with
its own model calls and its own money, and a solving record that carried a
grade would invite exactly the mixture the benchmark has to avoid. Its reason
says so, and no future change should "fix" it here.

``tool_run_count`` is absent because of *when* this run happened.
``CodexRunner`` counts the items a turn produces and has always counted them,
but ``step2_run_inference`` only began forwarding ``items_seen`` into the
result after exp033 ran. Runs from exp034 on carry it and this field fills
itself with no change here -- though not for every task even then, because a
turn that died before its stream opened carries the field's default rather
than a count, and the two are not added together.

``executed_code_version`` is absent unless the caller supplies it. Nothing in
the workspace names the commit that ran, and inferring it from the checkout
this analysis happens to run in would be a guess wearing a sha's clothing. In
CI the caller has ``GITHUB_SHA`` and passes it; read off a downloaded artifact
months later, nobody does, and the record should say that rather than lie.

A last word on ``model_cost``, which is the field most likely to be misread.
It is copied from the receipt the run wrote, including ``status: "partial"``,
``estimated_cost_usd: null`` and the ``missing_reasons`` that explain it. It is
never collapsed to a number. A receipt that says it does not know what was
spent is a different statement from one that says nothing was spent, and this
module keeps them different.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Mapping, Sequence

from core.execution_environment_readiness import (
    REQUIRED_RUN_RECORD_FIELDS,
    retry_counts_by_reason,
)

__all__ = [
    "RUN_RECORD_SCHEMA",
    "build_run_record",
    "is_recorded",
    "not_recorded",
    "unrecorded_fields",
]

RUN_RECORD_SCHEMA = "gdpval-run-record-v1"

#: Outcomes where the turn never opened, so ``items_seen`` is the dataclass
#: default rather than a count.
#:
#: ``core/codex_runner.py`` builds these four outcomes without passing
#: ``items_seen`` at all, and the field defaults to 0. Every path that reached
#: a stream -- success, timeout, turn failure -- passes ``observed.items_seen``.
#: Counting the defaults would pull the total toward "these turns produced
#: nothing", which is a claim about the model when the truth is that nobody
#: measured. They are excluded from the total and reported separately.
#:
#: Only these four are named because only these four are enumerable: what a
#: started turn reports comes from ``classify_execution_error``, whose
#: vocabulary is open, so the complement cannot be written down.
#:
#: ``scripts/analyze_codex_run.py`` keeps its own copy of this set for the
#: same reason. ``test_run_record.py`` pins the two equal, so a change to
#: either shows up rather than drifting.
PRE_STREAM_FAILURE_CATEGORIES = frozenset(
    {
        "runtime_unavailable",
        "runtime_start_failed",
        "session_start_failed",
        "turn_start_failed",
    }
)

#: What ``produced_file_check_results`` is allowed to claim.
#:
#: The pipeline hashes and sizes every deliverable as it collects it. That
#: proves the file existed and could be read at collection time; it does not
#: inspect the contents, and calling it a content check would be the kind of
#: overclaim this record exists to prevent. The list is written into the record
#: beside the results so a reader is told the scope rather than left to assume
#: one.
FILE_CHECKS_PERFORMED = ("exists_at_collection", "sha256_computed", "size_recorded")


# ── the marker for something the run did not write down ────────────────────


def not_recorded(reason: str) -> dict[str, Any]:
    """A field that is present, empty, and says why.

    ``check_run_record_fields`` tests eighteen of the nineteen fields for the
    key alone, so a marker satisfies it. That is deliberate and it is also why
    ``unrecorded_fields`` exists: the first question is whether the record has
    a place for the measurement, and the second is whether the measurement was
    taken. Answering only the first is how a record full of markers passes.
    """
    if not reason or not reason.strip():
        raise ValueError("a not-recorded field has to give its reason")
    return {"recorded": False, "reason": reason.strip()}


def is_recorded(value: Any) -> bool:
    """Whether a field carries a measurement rather than a marker."""
    return not (isinstance(value, Mapping) and value.get("recorded") is False)


def unrecorded_fields(record: Mapping[str, Any]) -> list[str]:
    """The required fields this record has a place for but no value in.

    Sorted, so a caller can pin the list and see it shrink.
    """
    return sorted(
        name
        for name in REQUIRED_RUN_RECORD_FIELDS
        if name in record and not is_recorded(record[name])
    )


# ── reading the four artifacts a run leaves ────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _elapsed_seconds(started: Any, finished: Any) -> float | None:
    """Seconds between two ISO timestamps, or None if either is unusable.

    Returns None rather than 0 on a bad timestamp. Zero is a duration and this
    is the absence of one.
    """
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    try:
        first = datetime.fromisoformat(started)
        last = datetime.fromisoformat(finished)
    except ValueError:
        return None
    return (last - first).total_seconds()


def _instruction_digests(prepared: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """One entry per task: the hash of its instruction and its length.

    The instruction itself is not copied in. At five tasks that would have been
    harmless; the run this record is being built for has two hundred and
    twenty, and a record nobody opens because of its size records nothing. A
    hash is what re-checking actually needs -- the instructions are in the
    prepared file beside this one, and either they hash to these values or the
    record is of a different run.
    """
    digests: dict[str, dict[str, Any]] = {}
    for task in prepared.get("tasks") or []:
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("task_id")
        instruction = task.get("instruction")
        if not isinstance(task_id, str) or not isinstance(instruction, str):
            continue
        digests[task_id] = {
            "sha256": _sha256(instruction),
            "characters": len(instruction),
        }
    return digests


def _model_and_deployment(
    results: Mapping[str, Any],
    prepared: Mapping[str, Any],
    ledger_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """What was asked for, and what the provider said answered.

    Both, separately. The requested deployment comes from the prepared
    experiment and the resolved model comes off the ledger rows, and a run
    where they differ is a run that has to be readable as such -- this is the
    repository's standing rule that a cost figure is counted by
    ``resolved_model`` rather than by the model somebody asked for.
    """
    condition = prepared.get("condition_a")
    model_block = condition.get("model") if isinstance(condition, Mapping) else None
    resolved = sorted(
        {
            row.get("resolved_model")
            for row in ledger_rows
            if isinstance(row, Mapping) and isinstance(row.get("resolved_model"), str)
        }
    )
    api_versions = sorted(
        {
            row.get("api_version")
            for row in ledger_rows
            if isinstance(row, Mapping) and isinstance(row.get("api_version"), str)
        }
    )
    return {
        "requested": dict(model_block) if isinstance(model_block, Mapping) else None,
        "reported_by_run": results.get("model"),
        "resolved_by_provider": resolved,
        "api_versions": api_versions,
        "execution_mode": results.get("execution_mode"),
        "azure_ai_routes": results.get("azure_ai_routes"),
    }


def _model_call_count(
    results: Mapping[str, Any], ledger_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Two counts of the same thing, kept apart.

    The receipt totals the calls it priced; the ledger has one row per call.
    They agree on a healthy run and the record says so rather than picking one,
    because a disagreement means a call was made and not receipted, and that is
    a cost finding rather than a rounding difference.
    """
    summary = results.get("summary")
    receipt = summary.get("problem_solving_cost") if isinstance(summary, Mapping) else None
    from_receipt = receipt.get("model_calls") if isinstance(receipt, Mapping) else None
    from_ledger = sum(
        1
        for row in ledger_rows
        if isinstance(row, Mapping) and row.get("record_type") == "call"
    )
    return {
        "from_cost_receipt": from_receipt,
        "from_cost_ledger": from_ledger,
        "agree": from_receipt == from_ledger,
    }


def _produced_files(results: Mapping[str, Any]) -> dict[str, Any]:
    """Every file the run collected, by task, with its hash and size."""
    by_task: dict[str, list[dict[str, Any]]] = {}
    for task in results.get("results") or []:
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("task_id")
        if not isinstance(task_id, str):
            continue
        records = task.get("deliverable_file_records") or []
        by_task[task_id] = [dict(item) for item in records if isinstance(item, Mapping)]
    return {
        "by_task": by_task,
        "file_count": sum(len(files) for files in by_task.values()),
        "tasks_with_no_file": sorted(
            task_id for task_id, files in by_task.items() if not files
        ),
    }


def _file_check_results(produced: Mapping[str, Any]) -> dict[str, Any]:
    """What the collection step proved about each file, and nothing more."""
    complete, incomplete = 0, []
    for task_id, files in (produced.get("by_task") or {}).items():
        for item in files:
            size = item.get("size")
            if isinstance(item.get("sha256"), str) and isinstance(size, int):
                complete += 1
            else:
                incomplete.append({"task_id": task_id, "path": item.get("path")})
    return {
        "checks_performed": list(FILE_CHECKS_PERFORMED),
        "files_with_every_check": complete,
        "files_missing_a_check": incomplete,
    }


def _task_completed(results: Mapping[str, Any]) -> dict[str, Any]:
    by_task = {}
    for task in results.get("results") or []:
        if isinstance(task, Mapping) and isinstance(task.get("task_id"), str):
            by_task[task["task_id"]] = task.get("status")
    counts: dict[str, int] = {}
    for status in by_task.values():
        counts[str(status)] = counts.get(str(status), 0) + 1
    return {"by_task": by_task, "counts_by_status": counts}


def _failure_stage_and_reason(
    results: Mapping[str, Any], ledger_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Why each unfinished task is unfinished, from every place that said so.

    A model that was stopped for content and a run place that could not reach
    the deployment both leave a task unfinished, and only the first is a
    benchmark result. Keeping the provider's own category beside the
    pipeline's error is what lets the two be told apart later without
    re-running anything.
    """
    ledger_states: dict[str, list[Any]] = {}
    for row in ledger_rows:
        if isinstance(row, Mapping) and isinstance(row.get("task_id"), str):
            ledger_states.setdefault(row["task_id"], []).append(row.get("state"))

    by_task = {}
    for task in results.get("results") or []:
        if not isinstance(task, Mapping) or task.get("status") == "success":
            continue
        task_id = task.get("task_id")
        if not isinstance(task_id, str):
            continue
        observability = task.get("observability")
        by_task[task_id] = {
            "status": task.get("status"),
            "error": task.get("error"),
            "error_category": (
                observability.get("error_category")
                if isinstance(observability, Mapping)
                else None
            ),
            "failure_evidence": task.get("failure_evidence"),
            "ledger_states": ledger_states.get(task_id, []),
        }
    return {"by_task": by_task, "unfinished_task_count": len(by_task)}


def _isolation_and_security(prepared: Mapping[str, Any], results: Mapping[str, Any]):
    """What the artifacts prove about where the work ran.

    This is the field where an honest answer is most obviously smaller than the
    question. The run place has real isolation -- a rewritten ``HOME``, a
    named-only environment inheritance, a working directory per task -- and
    none of that is written into any artifact, so none of it is claimed here.
    What the artifacts do prove is the declared execution mode, whether a
    sandbox was configured, and which route profile carried the traffic.
    """
    execution = prepared.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    routes = results.get("azure_ai_routes") or []
    return {
        "execution_mode": execution.get("mode"),
        "sandbox": execution.get("sandbox"),
        "route_profiles": sorted(
            {
                route.get("profile")
                for route in routes
                if isinstance(route, Mapping) and isinstance(route.get("profile"), str)
            }
        ),
        "per_turn_timeout_seconds": execution.get("timeout"),
        "attempts_allowed_per_task": execution.get("max_retries"),
        "resume_rounds_allowed": execution.get("resume_max_rounds"),
        "evidence_note": (
            "declared configuration and route profile only; the run place's "
            "process isolation is not written into any artifact and is not "
            "claimed here"
        ),
    }


def _tool_run_count(results: Mapping[str, Any]) -> Any:
    """``items_seen`` per task, counting only the turns that opened.

    A turn that failed before its stream opened carries the field's default,
    not a measurement, and the two have to be told apart -- see
    ``PRE_STREAM_FAILURE_CATEGORIES``. Those tasks are listed rather than
    summed, so the total is a count of items actually observed and the reader
    can still see how many turns never got that far.
    """
    measured: dict[str, int] = {}
    never_opened: list[str] = []
    for task in results.get("results") or []:
        if not isinstance(task, Mapping):
            continue
        task_id = task.get("task_id")
        seen = task.get("items_seen")
        if not isinstance(task_id, str) or not isinstance(seen, int):
            continue
        observability = task.get("observability")
        category = (
            observability.get("error_category")
            if isinstance(observability, Mapping)
            else None
        )
        if task.get("status") != "success" and str(category) in PRE_STREAM_FAILURE_CATEGORIES:
            never_opened.append(task_id)
        else:
            measured[task_id] = seen

    if not measured and not never_opened:
        return not_recorded(
            "no task in this run carries items_seen; CodexRunner counts the "
            "items a turn produces but step2_run_inference began forwarding "
            "the count only after this run, so it is absent rather than zero"
        )
    if not measured:
        return not_recorded(
            "every turn in this run failed before its stream opened, so each "
            f"items_seen is the field's default rather than a count "
            f"({len(never_opened)} tasks)"
        )
    return {
        "by_task": measured,
        "total": sum(measured.values()),
        "tasks_whose_turn_never_opened": sorted(never_opened),
    }


# ── the record ─────────────────────────────────────────────────────────────


def build_run_record(
    *,
    results: Mapping[str, Any],
    prepared: Mapping[str, Any],
    manifest: Mapping[str, Any],
    ledger_rows: Sequence[Mapping[str, Any]],
    code_version: str | None = None,
) -> dict[str, Any]:
    """Gather one finished run's artifacts into the required record.

    ``results`` is ``step2_inference_results.json``, ``prepared`` is
    ``step1_tasks_prepared.json``, ``manifest`` is
    ``step0_needs_files_manifest.json`` and ``ledger_rows`` are the parsed
    lines of the condition's cost ledger. ``code_version`` is the commit the
    pipeline ran, which no artifact holds; a caller that knows it passes it.

    Every key in ``REQUIRED_RUN_RECORD_FIELDS`` is present in the result.
    """
    condition = prepared.get("condition_a")
    prompt = condition.get("prompt") if isinstance(condition, Mapping) else None
    system = prompt.get("system") if isinstance(prompt, Mapping) else None

    summary = results.get("summary")
    receipt = summary.get("problem_solving_cost") if isinstance(summary, Mapping) else None

    produced = _produced_files(results)
    started, finished = results.get("started_at"), results.get("completed_at")
    elapsed = _elapsed_seconds(started, finished)

    record: dict[str, Any] = {
        "schema_version": RUN_RECORD_SCHEMA,
        "experiment_id": results.get("experiment_id"),
        "run_id": results.get("run_id"),
        "condition": results.get("condition_identity"),
        "model_and_deployment": _model_and_deployment(results, prepared, ledger_rows),
        "system_instruction": (
            {"text": system, "sha256": _sha256(system), "characters": len(system)}
            if isinstance(system, str)
            else not_recorded("the prepared experiment carries no system prompt")
        ),
        "task_instruction": _instruction_digests(prepared)
        or not_recorded("the prepared experiment carries no task instructions"),
        "task_ids": results.get("ordered_task_ids")
        or not_recorded("the run wrote no ordered task list"),
        "input_file_versions": {
            "dataset": manifest.get("_source"),
            "dataset_revision": manifest.get("_source_revision"),
            "ordered_task_ids_sha256": manifest.get("_ordered_task_ids_sha256"),
            "source_projection_sha256": manifest.get("_source_projection_sha256"),
            "prepared_fingerprint": results.get("prepared_fingerprint"),
            "reference_files_by_task": {
                task["task_id"]: task.get("reference_file_records") or []
                for task in (prepared.get("tasks") or [])
                if isinstance(task, Mapping) and isinstance(task.get("task_id"), str)
            },
        },
        "executed_code_version": code_version
        or not_recorded(
            "no artifact names the commit the pipeline ran; a caller that "
            "knows it, such as a workflow holding GITHUB_SHA, supplies it"
        ),
        "started_at": started or not_recorded("the run wrote no start time"),
        "finished_at": finished or not_recorded("the run wrote no finish time"),
        "total_seconds": (
            elapsed
            if elapsed is not None
            else not_recorded("the run's two timestamps do not give a duration")
        ),
        "model_call_count": _model_call_count(results, ledger_rows),
        "tool_run_count": _tool_run_count(results),
        "retry_counts_by_reason": retry_counts_by_reason(ledger_rows),
        "produced_files": produced,
        "produced_file_check_results": _file_check_results(produced),
        "task_completed": _task_completed(results),
        "external_grade": not_recorded(
            "marking is a separate step with its own model calls and its own "
            "money; a grade inside the solving record is the mixture this "
            "benchmark has to avoid, so this absence is deliberate"
        ),
        "model_cost": (
            dict(receipt)
            if isinstance(receipt, Mapping)
            else not_recorded("the run wrote no cost receipt")
        ),
        "isolation_and_security": _isolation_and_security(prepared, results),
        "failure_stage_and_reason": _failure_stage_and_reason(results, ledger_rows),
    }

    missing = [name for name in REQUIRED_RUN_RECORD_FIELDS if name not in record]
    if missing:  # pragma: no cover - a programming error in this module
        raise AssertionError(f"build_run_record left out: {sorted(missing)}")
    return record
