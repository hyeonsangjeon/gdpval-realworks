#!/usr/bin/env python3
"""Step 9: merge N partial shard grade payloads into one final grade payload.

Why this exists
---------------
The 220-task grade run projects to ~71.6h of judge latency while a single
GitHub Actions relay envelope is 44h (``GRADER_TIME_BUDGET_SEC`` 4h x 10
resume chunks). Sharding the corpus across N parallel relays is the only
remaining lever that does not change the reproducibility contract (judge
model / reasoning effort / prompt / rubric all stay pinned). Each shard
produces a ``run_status: "partial"`` grade payload that declares the FULL
corpus identity (``expected_task_count`` = 220 and
``expected_ordered_task_ids_sha256`` = the full ordered-id hash) while
carrying only its own slice of ``tasks``. This module folds those N
partials back into one ``run_status: "final"`` payload.

Guarantees
----------
* **Pure offline.** Zero LLM calls, zero Azure calls, zero network access.
  Reads JSON, writes JSON.
* **Deterministic.** Same inputs produce a byte-identical output (modulo
  nothing -- the merged payload is a pure function of the shard payloads).
  Input *order on the command line does not matter*: shards are normalised
  into canonical corpus order before anything is computed.
* **Serial-identical.** Every recomputed aggregate is produced by calling
  :func:`step8_grade._compute_summary` over the merged task list, i.e. the
  exact function a single serial run would have called over the exact same
  list in the exact same order. Rounding is never reimplemented here:
  ``judge_error_rate`` comes from :func:`core.grade_payload.canonical_rate`
  (half-up at 4dp) via ``_compute_summary``, and float summation order is
  preserved by canonical task ordering.
* **No silent partial publication.** A merge whose task union is smaller
  than ``expected_task_count`` is a hard failure. It never degrades to
  emitting a partial.

Latency semantics (read this before wiring a dashboard)
-------------------------------------------------------
``summary.cost.total_judge_latency_sec`` (and its ``main`` / ``perception``
/ ``render`` siblings) in the merged payload is **total judge work**, not
**elapsed wall-clock time**. N shards run concurrently, so the merged
latency total is the sum of N parallel timelines. Displaying it as "how
long the run took" overstates elapsed time by roughly a factor of N.

The emitted value is *recomputed* from the merged task list rather than
summed from the shard summaries, because only the recomputed value is
identical to a serial run (each shard rounds to 2dp, so
``sum(round(...)) != round(sum(...))``). The shard-reported latencies are
still cross-checked against that recomputation within a rounding tolerance
of ``0.01s x shard count`` -- see :func:`_check_latency_sums` -- so a
hand-edited shard latency is rejected instead of being silently ignored.

Route provenance
----------------
``azure_ai_routes`` is an order-preserving union across shards, deduplicated
by ``runtime_fingerprint``, and ``azure_ai_runtime_fingerprint`` is taken
from shard index 0 (the shard holding the canonically-first task). This
follows the merge table in the shard-merge spec section D. It is a
DELIBERATE relaxation of the sequential-resume invariant enforced by
``step8_grade._validate_azure_ai_resume_identity``, which demands the two
fields be byte-identical across accumulated payloads. Even a 4-task anchor
run already observed two distinct grader fingerprints, so a 9-way run is
expected to observe more. Pass ``--strict-routes`` to enforce the literal
sequential invariant instead. Whichever mode is used, per-shard route
identity is preserved in ``shard_provenance`` -- each entry records the
fingerprint that shard actually carried, so drift is readable from the
merged artifact alone rather than only from a stderr warning -- and every
observed fingerprint survives in the merged ``azure_ai_routes`` list.

Usage
-----
    python step9_merge_shards.py shard0.json shard1.json ... \
        --output data/grades/merged.json

    # explicit canonical order (e.g. from workspace/step1_tasks_prepared.json)
    python step9_merge_shards.py shard*.json \
        --expected-task-ids workspace/step2_inference_results.json \
        --output merged.json
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from core.grade_payload import canonical_rate, validate_grade_payload
from step8_grade import (
    SCHEMA_VERSION,
    _batch_runner_root,
    _compute_summary,
    _ordered_task_ids_sha256,
    _save_json,
)

FULL_SHA256_RE_TEXT = "^[0-9a-f]{64}$"

#: Upper bound on stride-layout candidates explored when reconstructing the
#: canonical corpus order without an explicit ``--expected-task-ids`` source.
#: A 9-way stride split of 220 tasks yields 4! * 5! = 2880 candidates.
MAX_CANDIDATE_LAYOUTS = 200_000

#: Sentinel distinguishing "key absent" from "key present with value None".
_MISSING = object()

#: Exit code for "the union is short, so a sibling shard is still working and
#: will merge later". Distinct from 1 so the caller can tell "stand down" from
#: "this merge is broken". 75 is EX_TEMPFAIL: try again later, nothing wrong.
DEFER_EXIT_CODE = 75

#: Shard-merge spec section C invariants 1-10: the fields
#: ``step8_grade._validate_grade_resume_identity`` requires to be identical
#: when two grade payloads are accumulated. Order here is the order reported.
CONTRACT_IDENTITY_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("schema_version", ("schema_version",)),
    ("experiment_id", ("experiment_id",)),
    ("rubric.commit_sha", ("rubric", "commit_sha")),
    ("prompt.version", ("prompt", "version")),
    ("judge.config_hash", ("judge", "config_hash")),
    ("source_inference_repo_id", ("source_inference_repo_id",)),
    ("source_inference_revision", ("source_inference_revision",)),
    ("grader_source_hash", ("grader_source_hash",)),
    ("anchor_projection", ("anchor_projection",)),
    ("renderer_fingerprint", ("renderer_fingerprint",)),
)

#: Spec section D "verify then adopt" fields that are not part of the ten
#: sequential-resume invariants. ``summary.cost.unpriced_models`` is checked
#: first so that a judge-model / perception-model divergence is reported
#: against the field the kill criterion names (kill criterion 2).
ADOPTED_IDENTITY_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("summary.cost.unpriced_models", ("summary", "cost", "unpriced_models")),
    ("expected_task_count", ("expected_task_count",)),
    (
        "expected_ordered_task_ids_sha256",
        ("expected_ordered_task_ids_sha256",),
    ),
    ("inference_model", ("inference_model",)),
    ("judge", ("judge",)),
    ("rubric", ("rubric",)),
    ("prompt", ("prompt",)),
    ("graded_by", ("graded_by",)),
    ("graded_by_version", ("graded_by_version",)),
    ("experiment_yaml_name", ("experiment_yaml_name",)),
    ("source_inference_experiment_id", ("source_inference_experiment_id",)),
    ("source_azure_ai_routes", ("source_azure_ai_routes",)),
    (
        "source_azure_ai_provenance_status",
        ("source_azure_ai_provenance_status",),
    ),
    ("inference_completed_at", ("inference_completed_at",)),
)

#: Best-effort debug-only field (``step8_grade._resolve_source_inference_run_dir``
#: probes the local filesystem, so two runners can legitimately disagree).
#: Adopted from shard 0 without an equality requirement.
NON_IDENTITY_ADOPTED_FIELDS: tuple[str, ...] = ("source_inference_run_dir",)

#: Integer cost counters that must sum exactly. Recomputation from the merged
#: task list is the source of truth; this check proves each shard's own
#: summary agreed with its own tasks, i.e. that no shard was hand-edited.
SUMMABLE_COST_FIELDS: tuple[str, ...] = (
    "total_judge_calls",
    "total_main_judge_calls",
    "total_perception_calls",
    "total_input_tokens",
    "total_output_tokens",
    "total_cached_tokens",
    "main_input_tokens",
    "main_output_tokens",
    "main_cached_tokens",
    "perception_input_tokens",
    "perception_output_tokens",
    "perception_cached_tokens",
    "total_render_calls",
)

#: Float latency counters. Unlike :data:`SUMMABLE_COST_FIELDS` these are NOT
#: summed into the merged payload: the merged value is recomputed from the
#: merged task list, because only the recomputed value is identical to what a
#: serial run over the same corpus would have emitted (spec section F kill
#: criterion 6). Each shard rounds its own latency to 2dp, so
#: ``sum(round(...)) != round(sum(...))`` and the shard sum is the serial value
#: plus rounding drift.
#:
#: That makes each shard's own ``summary.cost.*_latency_sec`` a spectator
#: field, which is the hole :func:`_check_latency_sums` closes.
LATENCY_COST_FIELDS: tuple[str, ...] = (
    "total_judge_latency_sec",
    "total_main_judge_latency_sec",
    "total_perception_latency_sec",
    "total_render_latency_sec",
)

#: Per-shard tolerance, in seconds, for the latency cross-check.
#:
#: ``_compute_summary`` rounds every latency to 2dp, so one shard's reported
#: value can sit at most 0.005s from its own exact value, and the merged
#: recomputation contributes one further 0.005s. The largest legitimate gap
#: across n shards is therefore ``0.005 * (n + 1)``, and ``0.01 * n`` bounds it
#: for every ``n >= 1`` (``0.01n >= 0.005n + 0.005`` iff ``n >= 1``) with a
#: factor-of-two margin. Measured worst case on the 220-task corpus is 0.01s at
#: n=3 against a 0.03s budget. Widening this constant re-opens the tampering
#: hole it exists to close.
LATENCY_TOLERANCE_SEC_PER_SHARD = 0.01


class ShardMergeError(ValueError):
    """A shard set cannot be merged into a single final grade payload."""


class ShardMergeIncomplete(ShardMergeError):
    """The shard union does not yet cover the corpus.

    Split out from its parent because under ``resume`` this is the normal
    intermediate state, not a defect. Shards publish their slice after every
    chunk, so a file on disk means "this shard has graded *something*", not
    "this shard is done". Every shard that finishes a chunk then pulls, sees
    N files, and tries to merge -- and all but the last one legitimately find
    a short union.

    Treated as a hard error, that turns a healthy sharded run into a wall of
    red: the sol-220 run merged correctly and published 220 tasks, yet three
    of its shards reported failure for observing a state that was true and
    temporary. Worse than the noise, it left a real stall indistinguishable
    from a routine one.

    ``--defer-if-incomplete`` lets the caller say it is one of several racing
    mergers and should stand down rather than fail. Nothing else is relaxed:
    a union that is complete but unmergeable still raises ShardMergeError.
    """

    def __init__(
        self, message: str, *, union_size: int, expected_count: int
    ) -> None:
        super().__init__(message)
        self.union_size = union_size
        self.expected_count = expected_count


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _get_path(payload: dict, path: Sequence[str]) -> Any:
    """Return the value at ``path`` or :data:`_MISSING` when absent."""
    node: Any = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return _MISSING
        node = node[key]
    return node


def _describe(value: Any) -> str:
    if value is _MISSING:
        return "<missing>"
    return repr(value)


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _payload_digest(payload: dict) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def _read_grade_schema() -> dict:
    path = _batch_runner_root() / "schemas" / "grade.schema.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ShardMergeError(f"could not read grade schema: {exc}") from exc


def _parse_graded_at(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ShardMergeError(
            f"{label} has no usable graded_at timestamp: {_describe(value)}"
        )
    text = value.strip()
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ShardMergeError(
            f"{label} graded_at is not ISO-8601: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _shard_task_ids(payload: dict, label: str) -> list[str]:
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise ShardMergeError(f"{label} has no tasks array")
    if not tasks:
        raise ShardMergeError(f"{label} contains zero graded tasks")
    task_ids: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for index, row in enumerate(tasks):
        if not isinstance(row, dict):
            raise ShardMergeError(
                f"{label} task at index {index} is not an object"
            )
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ShardMergeError(
                f"{label} task at index {index} has no non-empty task_id"
            )
        if task_id in seen:
            duplicates.add(task_id)
        seen.add(task_id)
        task_ids.append(task_id)
    if duplicates:
        raise ShardMergeError(
            f"{label} contains duplicate task_ids: {sorted(duplicates)}"
        )
    return task_ids


# --------------------------------------------------------------------------
# invariant checks
# --------------------------------------------------------------------------


def _check_identity_fields(
    shards: Sequence[dict],
    labels: Sequence[str],
    fields: Sequence[tuple[str, tuple[str, ...]]],
    *,
    contract: bool,
) -> None:
    """Fail loudly if any shard disagrees on a verify-then-adopt field."""
    reference = shards[0]
    reference_label = labels[0]
    kind = "shard merge identity" if contract else "shard merge field"
    for field_name, path in fields:
        expected = _get_path(reference, path)
        for shard, label in zip(shards[1:], labels[1:]):
            actual = _get_path(shard, path)
            if actual != expected:
                state = "missing" if actual is _MISSING else "mismatch"
                raise ShardMergeError(
                    f"{kind} {state} for {field_name}: "
                    f"{reference_label}={_describe(expected)}, "
                    f"{label}={_describe(actual)}"
                )


def _check_schema_version(shards: Sequence[dict], labels: Sequence[str]) -> None:
    for shard, label in zip(shards, labels):
        version = shard.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ShardMergeError(
                "shard merge identity mismatch for schema_version: "
                f"{label}={_describe(version)}, "
                f"current contract={SCHEMA_VERSION!r}"
            )


def _check_partial_status(shards: Sequence[dict], labels: Sequence[str]) -> None:
    for shard, label in zip(shards, labels):
        status = shard.get("run_status")
        if status != "partial":
            raise ShardMergeError(
                f"{label} run_status must be 'partial' to be merged, "
                f"got {_describe(status)}"
            )


def _check_route_identity(
    shards: Sequence[dict],
    labels: Sequence[str],
    *,
    strict: bool,
    warn: Callable[[str], None],
) -> None:
    """Verify section C invariants 11-12 (``azure_ai_*``) per shard.

    Structural verification is unconditional: each shard must carry a
    non-empty grader route list whose first entry matches the shard's own
    primary ``azure_ai_runtime_fingerprint``. Cross-shard byte equality is
    only demanded under ``strict``; otherwise drift is surfaced as a warning
    and resolved by the section D union / shard-0 rules.
    """
    for shard, label in zip(shards, labels):
        routes = shard.get("azure_ai_routes")
        fingerprint = shard.get("azure_ai_runtime_fingerprint")
        if not isinstance(routes, list) or not routes:
            raise ShardMergeError(f"{label} has no azure_ai_routes")
        for index, route in enumerate(routes):
            if not isinstance(route, dict):
                raise ShardMergeError(
                    f"{label} azure_ai_routes[{index}] is not an object"
                )
            if route.get("workload") != "grader":
                raise ShardMergeError(
                    f"{label} azure_ai_routes[{index}] is not a grader "
                    f"route: workload={_describe(route.get('workload'))}"
                )
        if not isinstance(fingerprint, str) or not _is_sha256(fingerprint):
            raise ShardMergeError(
                f"{label} azure_ai_runtime_fingerprint is invalid: "
                f"{_describe(fingerprint)}"
            )
        primary = routes[0].get("runtime_fingerprint")
        if primary != fingerprint:
            raise ShardMergeError(
                f"{label} primary grader route fingerprint mismatch: "
                f"azure_ai_routes[0]={_describe(primary)}, "
                f"azure_ai_runtime_fingerprint={fingerprint!r}"
            )

    if strict:
        _check_identity_fields(
            shards,
            labels,
            (
                ("azure_ai_routes", ("azure_ai_routes",)),
                (
                    "azure_ai_runtime_fingerprint",
                    ("azure_ai_runtime_fingerprint",),
                ),
            ),
            contract=True,
        )
        return

    fingerprints = {shard["azure_ai_runtime_fingerprint"] for shard in shards}
    if len(fingerprints) > 1:
        warn(
            "azure_ai_runtime_fingerprint differs across shards "
            f"({len(fingerprints)} distinct values); merged payload adopts "
            "shard 0's fingerprint and unions every observed route. Re-run "
            "with --strict-routes to reject route drift instead."
        )


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _check_cost_sums(
    shards: Sequence[dict],
    labels: Sequence[str],
    merged_cost: dict,
) -> None:
    """Prove each shard's own cost counters agreed with its own tasks.

    The merged counters are recomputed from the merged task list (that is
    what makes them serial-identical). Summing the shard-reported counters
    must reproduce the same integers; if it does not, at least one shard
    payload was edited after it was written and must not be merged.
    """
    for field in SUMMABLE_COST_FIELDS:
        total = 0
        for shard, label in zip(shards, labels):
            value = _get_path(shard, ("summary", "cost", field))
            if type(value) is not int:
                raise ShardMergeError(
                    f"{label} summary.cost.{field} must be an integer, "
                    f"got {_describe(value)}"
                )
            total += value
        if merged_cost.get(field) != total:
            raise ShardMergeError(
                f"merged summary.cost.{field} does not equal the shard sum: "
                f"recomputed={_describe(merged_cost.get(field))}, "
                f"shard_sum={total}"
            )


def _check_latency_sums(
    shards: Sequence[dict],
    labels: Sequence[str],
    merged_cost: dict,
) -> None:
    """Bound the recomputed latency totals by the shard-reported sum.

    The merged latency stays *recomputed*, never summed -- that is the whole
    point of the field (see :data:`LATENCY_COST_FIELDS`). This check does not
    touch the emitted value; it only refuses to merge when the recomputation
    and the shard sum disagree by more than 2dp rounding can account for.

    Without it the shards' own latency fields are read by nobody: adding
    10000s to one shard's ``total_judge_latency_sec`` changed no output and
    the merge succeeded silently.

    Missing / non-numeric handling: a shard that omits a latency field is a
    hard failure, matching how :func:`_check_cost_sums` already treats a
    missing integer counter. The grade schema constrains ``summary.cost`` only
    as ``{"type": "object"}``, so per-shard ``validate_grade_payload`` does not
    require these fields; "absent" is therefore indistinguishable from
    "deleted", and skipping the field would restore exactly the hole this
    function closes.
    """
    tolerance = LATENCY_TOLERANCE_SEC_PER_SHARD * len(shards)
    for field in LATENCY_COST_FIELDS:
        values: list[float] = []
        for shard, label in zip(shards, labels):
            value = _get_path(shard, ("summary", "cost", field))
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ShardMergeError(
                    f"{label} summary.cost.{field} must be a number, "
                    f"got {_describe(value)}"
                )
            values.append(float(value))
        # fsum is exactly rounded, so the verdict cannot depend on the order
        # the shards happened to be listed in.
        shard_sum = math.fsum(values)
        recomputed = merged_cost.get(field, _MISSING)
        if isinstance(recomputed, bool) or not isinstance(
            recomputed, (int, float)
        ):
            raise ShardMergeError(
                f"merged summary.cost.{field} is not a number: "
                f"{_describe(recomputed)}"
            )
        difference = abs(float(recomputed) - shard_sum)
        if difference > tolerance:
            raise ShardMergeError(
                f"merged summary.cost.{field} differs from the shard sum by "
                "more than 2dp rounding can explain: "
                f"recomputed={recomputed!r}, shard_sum={shard_sum:.6f}, "
                f"difference={difference:.6f}, tolerance={tolerance:.6f} "
                f"({LATENCY_TOLERANCE_SEC_PER_SHARD} x {len(shards)} shard(s))"
                ". At least one shard's reported latency was edited after it "
                "was written."
            )


# --------------------------------------------------------------------------
# canonical corpus order
# --------------------------------------------------------------------------


def _stride_sizes(total: int, shard_count: int) -> list[int]:
    """Return the task count each stride shard index must hold.

    Mirrors the adopted shard design ``tasks[shard_index::shard_count]``.
    """
    return [len(range(index, total, shard_count)) for index in range(shard_count)]


def _stride_layout_candidates(
    shard_task_ids: Sequence[Sequence[str]],
    total: int,
) -> Iterable[tuple[int, ...]]:
    """Yield candidate assignments of input position -> stride shard index.

    Only assignments consistent with the stride size profile are produced,
    which keeps a 9-way 220-task merge at 4! * 5! = 2880 candidates instead
    of 9! = 362880.
    """
    shard_count = len(shard_task_ids)
    required = _stride_sizes(total, shard_count)
    actual = [len(ids) for ids in shard_task_ids]
    if sorted(actual) != sorted(required):
        return

    indices_by_size: dict[int, list[int]] = {}
    for shard_index, size in enumerate(required):
        indices_by_size.setdefault(size, []).append(shard_index)
    inputs_by_size: dict[int, list[int]] = {}
    for input_index, size in enumerate(actual):
        inputs_by_size.setdefault(size, []).append(input_index)

    sizes = sorted(indices_by_size)
    total_candidates = 1
    for size in sizes:
        group = len(indices_by_size[size])
        for factor in range(2, group + 1):
            total_candidates *= factor
    if total_candidates > MAX_CANDIDATE_LAYOUTS:
        raise ShardMergeError(
            "canonical corpus order cannot be reconstructed: "
            f"{total_candidates} candidate stride layouts exceeds the "
            f"{MAX_CANDIDATE_LAYOUTS} cap. Pass --expected-task-ids with "
            "the canonical ordered task id list."
        )

    per_size_permutations = [
        list(itertools.permutations(inputs_by_size[size])) for size in sizes
    ]
    for combination in itertools.product(*per_size_permutations):
        assignment = [-1] * shard_count
        for size, ordered_inputs in zip(sizes, combination):
            for shard_index, input_index in zip(
                indices_by_size[size], ordered_inputs
            ):
                assignment[shard_index] = input_index
        yield tuple(assignment)


def _order_from_stride_assignment(
    shard_task_ids: Sequence[Sequence[str]],
    assignment: Sequence[int],
    total: int,
) -> list[str]:
    shard_count = len(assignment)
    order: list[str | None] = [None] * total
    for shard_index, input_index in enumerate(assignment):
        ids = shard_task_ids[input_index]
        for offset, task_id in enumerate(ids):
            position = shard_index + offset * shard_count
            if position >= total:
                return []
            order[position] = task_id
    if any(value is None for value in order):
        return []
    return [value for value in order if value is not None]


def _load_expected_task_ids(source: Any, label: str) -> list[str]:
    """Accept the several shapes that carry a canonical ordered id list."""
    candidate: Any = source
    if isinstance(source, dict):
        for key in ("task_ids", "expected_ordered_task_ids"):
            if isinstance(source.get(key), list):
                candidate = source[key]
                break
        else:
            for key in ("tasks", "results"):
                rows = source.get(key)
                if isinstance(rows, list):
                    candidate = [
                        row.get("task_id") if isinstance(row, dict) else row
                        for row in rows
                    ]
                    break
    if not isinstance(candidate, list) or not candidate:
        raise ShardMergeError(
            f"{label} does not contain a non-empty ordered task id list"
        )
    if any(not isinstance(value, str) or not value.strip() for value in candidate):
        raise ShardMergeError(f"{label} contains a non-string task id")
    return [str(value) for value in candidate]


def _resolve_canonical_order(
    shard_task_ids: Sequence[Sequence[str]],
    *,
    expected_count: int,
    expected_hash: str,
    union: set[str],
    explicit: Sequence[str] | None,
) -> list[str]:
    """Return the canonical ordered corpus task id list.

    The order is never guessed: whichever source supplies it, the result is
    verified against ``expected_ordered_task_ids_sha256`` before use, so a
    wrong reconstruction fails loudly instead of silently emitting a payload
    whose ``tasks`` order contradicts its own declared identity.
    """
    if explicit is not None:
        order = list(explicit)
        if len(order) != expected_count:
            raise ShardMergeError(
                "explicit expected task ids count does not match shard "
                f"expected_task_count: got {len(order)}, "
                f"expected {expected_count}"
            )
        if len(set(order)) != len(order):
            raise ShardMergeError(
                "explicit expected task ids contain duplicates"
            )
        if set(order) != union:
            missing = sorted(union - set(order))
            unexpected = sorted(set(order) - union)
            raise ShardMergeError(
                "explicit expected task ids do not match the merged task "
                f"set: missing_from_explicit={missing[:5]}, "
                f"absent_from_shards={unexpected[:5]}"
            )
        actual_hash = _ordered_task_ids_sha256(order)
        if actual_hash != expected_hash:
            raise ShardMergeError(
                "explicit expected task ids do not hash to the shard "
                f"declared expected_ordered_task_ids_sha256: "
                f"explicit={actual_hash}, shards={expected_hash}"
            )
        return order

    for assignment in _stride_layout_candidates(shard_task_ids, expected_count):
        order = _order_from_stride_assignment(
            shard_task_ids, assignment, expected_count
        )
        if not order:
            continue
        if _ordered_task_ids_sha256(order) == expected_hash:
            return order

    raise ShardMergeError(
        "canonical corpus order could not be reconstructed from the shard "
        "layout (no stride assignment reproduces "
        f"expected_ordered_task_ids_sha256={expected_hash}). Pass "
        "--expected-task-ids with the canonical ordered task id list."
    )


# --------------------------------------------------------------------------
# merge
# --------------------------------------------------------------------------


def merge_shard_payloads(
    shards: Sequence[dict],
    *,
    source_labels: Sequence[str] | None = None,
    source_digests: Sequence[str] | None = None,
    expected_task_ids: Sequence[str] | None = None,
    strict_routes: bool = False,
    warn: Callable[[str], None] | None = None,
) -> dict:
    """Merge N partial shard payloads into one final grade payload.

    This is a pure function: no network, no filesystem writes, no clock
    reads. ``graded_at`` is the maximum of the shard timestamps (the moment
    the last shard finished), never ``now()``.

    Raises:
        ShardMergeError: on any invariant violation, task-set defect, or
            output schema failure. The message always names the field or
            shard at fault.
    """
    emit_warning = warn if warn is not None else (
        lambda message: print(f"WARNING: {message}", file=sys.stderr)
    )

    if not shards:
        raise ShardMergeError("no shard payloads supplied")
    labels = (
        list(source_labels)
        if source_labels is not None
        else [f"shard[{index}]" for index in range(len(shards))]
    )
    if len(labels) != len(shards):
        raise ShardMergeError("shard label count does not match shard count")
    for shard, label in zip(shards, labels):
        if not isinstance(shard, dict):
            raise ShardMergeError(f"{label} top-level JSON must be an object")

    digests = (
        list(source_digests)
        if source_digests is not None
        else [_payload_digest(shard) for shard in shards]
    )
    if len(digests) != len(shards):
        raise ShardMergeError("shard digest count does not match shard count")

    # --- section C invariants -------------------------------------------
    _check_schema_version(shards, labels)
    _check_partial_status(shards, labels)
    _check_identity_fields(
        shards, labels, CONTRACT_IDENTITY_FIELDS, contract=True
    )
    _check_route_identity(
        shards, labels, strict=strict_routes, warn=emit_warning
    )
    _check_identity_fields(
        shards, labels, ADOPTED_IDENTITY_FIELDS, contract=False
    )

    reference = shards[0]
    schema = _read_grade_schema()
    for shard, label in zip(shards, labels):
        try:
            validate_grade_payload(shard, schema)
        # Broad on purpose: the validator's exception type is not part of its
        # contract, and every failure mode means the same thing here. Re-raised
        # with the shard label so the message names the file at fault.
        except Exception as exc:
            raise ShardMergeError(
                f"{label} is not a valid grade payload: {exc}"
            ) from exc

    expected_count = reference.get("expected_task_count")
    if type(expected_count) is not int or expected_count < 1:
        raise ShardMergeError(
            f"shard expected_task_count is invalid: {_describe(expected_count)}"
        )
    expected_hash = reference.get("expected_ordered_task_ids_sha256")
    if not isinstance(expected_hash, str) or not _is_sha256(expected_hash):
        raise ShardMergeError(
            "shard expected_ordered_task_ids_sha256 is invalid: "
            f"{_describe(expected_hash)}"
        )

    # --- task set: disjoint, complete ------------------------------------
    shard_task_ids = [
        _shard_task_ids(shard, label) for shard, label in zip(shards, labels)
    ]
    owner: dict[str, str] = {}
    collisions: dict[str, list[str]] = {}
    for ids, label in zip(shard_task_ids, labels):
        for task_id in ids:
            if task_id in owner:
                collisions.setdefault(task_id, [owner[task_id]]).append(label)
            else:
                owner[task_id] = label
    if collisions:
        detail = ", ".join(
            f"{task_id} in {sorted(set(where))}"
            for task_id, where in sorted(collisions.items())[:5]
        )
        raise ShardMergeError(
            f"shards are not disjoint: {len(collisions)} duplicated task_id(s); "
            f"{detail}"
        )

    union = set(owner)
    if len(union) != expected_count:
        missing = expected_count - len(union)
        raise ShardMergeIncomplete(
            "merged task set is incomplete: union has "
            f"{len(union)} task(s) but expected_task_count is "
            f"{expected_count} ({missing} missing). Refusing to promote an "
            "incomplete merge to run_status='final'.",
            union_size=len(union),
            expected_count=expected_count,
        )

    canonical_order = _resolve_canonical_order(
        shard_task_ids,
        expected_count=expected_count,
        expected_hash=expected_hash,
        union=union,
        explicit=expected_task_ids,
    )
    position = {task_id: index for index, task_id in enumerate(canonical_order)}

    # --- deterministic shard ordering (shard 0 holds canonical task 0) ---
    shard_order = sorted(
        range(len(shards)), key=lambda index: position[shard_task_ids[index][0]]
    )

    # --- tasks: canonical reorder-concatenate ----------------------------
    merged_tasks: list[dict] = []
    for shard in shards:
        merged_tasks.extend(shard["tasks"])
    merged_tasks.sort(key=lambda task: position[task["task_id"]])
    if [task["task_id"] for task in merged_tasks] != canonical_order:
        raise ShardMergeError(
            "merged task order does not match the canonical corpus order"
        )

    # --- azure route provenance ------------------------------------------
    merged_routes: list[dict] = []
    seen_fingerprints: set[str] = set()
    for index in shard_order:
        for route in shards[index]["azure_ai_routes"]:
            fingerprint = route.get("runtime_fingerprint")
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            merged_routes.append(dict(route))
    primary_fingerprint = shards[shard_order[0]]["azure_ai_runtime_fingerprint"]
    if merged_routes[0].get("runtime_fingerprint") != primary_fingerprint:
        raise ShardMergeError(
            "merged primary grader route does not match shard 0's "
            f"azure_ai_runtime_fingerprint: routes[0]="
            f"{_describe(merged_routes[0].get('runtime_fingerprint'))}, "
            f"shard0={primary_fingerprint!r}"
        )

    # --- summary: recompute, never re-derive rounding --------------------
    unpriced_models = _get_path(
        reference, ("summary", "cost", "unpriced_models")
    )
    if not isinstance(unpriced_models, list) or not unpriced_models:
        raise ShardMergeError(
            "shard summary.cost.unpriced_models is missing or empty: "
            f"{_describe(unpriced_models)}"
        )
    summary = _compute_summary(merged_tasks, unpriced_models=unpriced_models)
    _check_cost_sums(shards, labels, summary["cost"])
    _check_latency_sums(shards, labels, summary["cost"])

    shard_usage_complete = True
    for shard, label in zip(shards, labels):
        value = _get_path(shard, ("summary", "cost", "usage_complete"))
        if type(value) is not bool:
            raise ShardMergeError(
                f"{label} summary.cost.usage_complete must be a boolean, "
                f"got {_describe(value)}"
            )
        shard_usage_complete = shard_usage_complete and value
    merged_usage_complete = (
        bool(summary["cost"]["usage_complete"]) and shard_usage_complete
    )
    if not merged_usage_complete:
        emit_warning(
            "merged summary.cost.usage_complete is false; at least one shard "
            "reported incomplete aggregate usage."
        )
    summary["cost"]["usage_complete"] = merged_usage_complete

    # Defensive: judge_error_rate must be canonical_rate half-up at 4dp.
    # validate_grade_payload recomputes exactly this and rejects drift, so a
    # mismatch here means _compute_summary and the validator disagree.
    judge_items = 0
    judge_errors = 0
    for task in merged_tasks:
        for item in task.get("items", []) or []:
            if isinstance(item, dict) and item.get("decided_by") == "judge":
                judge_items += 1
                if item.get("verdict") == "judge_error":
                    judge_errors += 1
    expected_error_rate = canonical_rate(judge_errors, judge_items)
    if summary["wow"]["judge_error_rate"] != expected_error_rate:
        raise ShardMergeError(
            "merged summary.wow.judge_error_rate does not match "
            f"canonical_rate({judge_errors}, {judge_items}): "
            f"computed={summary['wow']['judge_error_rate']}, "
            f"canonical={expected_error_rate}"
        )

    # --- graded_at: completion moment of the last shard ------------------
    graded_at_pairs = [
        (_parse_graded_at(shard.get("graded_at"), label), str(shard["graded_at"]))
        for shard, label in zip(shards, labels)
    ]
    merged_graded_at = max(graded_at_pairs)[1]

    # --- assemble ---------------------------------------------------------
    merged: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_status": "final",
    }
    for field_name, path in ADOPTED_IDENTITY_FIELDS:
        if len(path) != 1:
            continue
        value = _get_path(reference, path)
        if value is not _MISSING:
            merged[path[0]] = value
    for field_name, path in CONTRACT_IDENTITY_FIELDS:
        if len(path) != 1 or path[0] in merged:
            continue
        value = _get_path(reference, path)
        if value is not _MISSING:
            merged[path[0]] = value
    for field_name in NON_IDENTITY_ADOPTED_FIELDS:
        if field_name in reference:
            merged[field_name] = reference[field_name]

    merged["azure_ai_routes"] = merged_routes
    merged["azure_ai_runtime_fingerprint"] = primary_fingerprint
    merged["graded_at"] = merged_graded_at
    merged["tasks"] = merged_tasks
    merged["summary"] = summary
    merged["shard_provenance"] = [
        {
            "index": rank,
            "count": len(shards),
            "config_hash": _get_path(
                shards[input_index], ("judge", "config_hash")
            ),
            "grade_file_sha256": digests[input_index],
            "graded_at": shards[input_index].get("graded_at"),
            # The merged payload can carry only ONE scalar
            # azure_ai_runtime_fingerprint, because core.grade_payload
            # structurally requires it to equal azure_ai_routes[0]
            # .runtime_fingerprint. In the default mode shard 0's value wins
            # and the others survive only as extra entries in
            # azure_ai_routes, with the drift itself announced once on
            # stderr and then gone. Recording each shard's own fingerprint
            # here makes route drift auditable from the merged artifact
            # alone -- who drifted, not merely that something did.
            # _check_route_identity has already proved this value equals
            # this shard's own azure_ai_routes[0].runtime_fingerprint, so it
            # is a faithful record of what the shard carried.
            "azure_ai_runtime_fingerprint": shards[input_index][
                "azure_ai_runtime_fingerprint"
            ],
        }
        for rank, input_index in enumerate(shard_order)
    ]

    # Preserve field ordering close to step8's payload for readable diffs.
    merged = _ordered_payload(merged, reference)

    if len(merged["tasks"]) != merged.get("expected_task_count"):
        raise ShardMergeError(
            "merged task count does not match expected_task_count; refusing "
            "to emit a final payload"
        )
    try:
        validate_grade_payload(merged, schema)
    # Broad on purpose, as above: re-raised as a merge failure so a schema
    # regression surfaces as "this merge is unpublishable", not a stack trace.
    except Exception as exc:
        raise ShardMergeError(
            f"merged payload failed grade schema validation: {exc}"
        ) from exc
    return merged


def _ordered_payload(merged: dict, reference: dict) -> dict:
    """Return ``merged`` with keys ordered like the shard payloads."""
    ordered: dict[str, Any] = {}
    for key in reference:
        if key in merged:
            ordered[key] = merged[key]
    for key in merged:
        if key not in ordered:
            ordered[key] = merged[key]
    return ordered


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def load_shard_file(path: Path) -> tuple[dict, str]:
    """Return ``(payload, sha256_of_file_bytes)`` for one shard file."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ShardMergeError(f"could not read shard {path}: {exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ShardMergeError(f"could not parse shard {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ShardMergeError(f"shard {path} top-level JSON must be an object")
    return payload, hashlib.sha256(raw).hexdigest()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge N partial shard grade payloads into one final grade "
            "payload. Fully offline and deterministic."
        )
    )
    parser.add_argument(
        "shards",
        nargs="+",
        help="Partial grade JSON paths (command-line order does not matter)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Destination path for the merged final grade JSON",
    )
    parser.add_argument(
        "--expected-task-ids",
        default=None,
        help=(
            "Optional JSON file carrying the canonical ordered task id list "
            "(a bare array, or an object with task_ids / tasks / results). "
            "Required when the shard layout is not a stride split."
        ),
    )
    parser.add_argument(
        "--strict-routes",
        action="store_true",
        help=(
            "Require azure_ai_routes and azure_ai_runtime_fingerprint to be "
            "identical across all shards (the literal sequential-resume "
            "invariant) instead of unioning routes."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite --output if it already exists",
    )
    parser.add_argument(
        "--defer-if-incomplete",
        action="store_true",
        help=(
            "Exit "
            f"{DEFER_EXIT_CODE} instead of 1 when the shard union does not "
            "yet cover expected_task_count. For concurrent shard mergers: "
            "all but the last legitimately observe a short union, and only "
            "the last should merge. Every other failure still exits 1."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    out_path = Path(args.output)
    if out_path.exists() and not args.force:
        print(
            f"ERROR: output already exists: {out_path}. Use --force to "
            "overwrite.",
            file=sys.stderr,
        )
        return 1

    shard_paths = [Path(value) for value in args.shards]
    duplicate_paths = sorted(
        {
            str(path)
            for path in shard_paths
            if shard_paths.count(path) > 1
        }
    )
    if duplicate_paths:
        print(
            f"ERROR: shard paths repeated on the command line: {duplicate_paths}",
            file=sys.stderr,
        )
        return 1

    try:
        loaded = [load_shard_file(path) for path in shard_paths]
        explicit_ids: list[str] | None = None
        if args.expected_task_ids:
            source_path = Path(args.expected_task_ids)
            try:
                source = json.loads(source_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ShardMergeError(
                    f"could not read --expected-task-ids {source_path}: {exc}"
                ) from exc
            explicit_ids = _load_expected_task_ids(source, str(source_path))

        merged = merge_shard_payloads(
            [payload for payload, _ in loaded],
            source_labels=[str(path) for path in shard_paths],
            source_digests=[digest for _, digest in loaded],
            expected_task_ids=explicit_ids,
            strict_routes=args.strict_routes,
        )
    except ShardMergeIncomplete as exc:
        if args.defer_if_incomplete:
            print(
                f"[merge] deferring: {exc.union_size} of "
                f"{exc.expected_count} task(s) graded so far; a sibling shard "
                "is still working and will merge once the corpus is complete.",
                file=sys.stderr,
            )
            return DEFER_EXIT_CODE
        print(f"ERROR: shard merge failed: {exc}", file=sys.stderr)
        return 1
    except ShardMergeError as exc:
        print(f"ERROR: shard merge failed: {exc}", file=sys.stderr)
        return 1

    _save_json(out_path, merged)
    avg = merged["summary"]["openai_compat"]["avg_score_pct"]
    avg_text = "unscored" if avg is None else f"{avg:.2f}"
    print(
        f"Merged {len(loaded)} shard(s): tasks={len(merged['tasks'])}, "
        f"avg_pct={avg_text}, out={out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
