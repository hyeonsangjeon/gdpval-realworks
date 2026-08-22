"""Independent verification of ``step9_merge_shards.py`` against the
field-by-field merge table in ``tasks/shard_merge_task/000-OVERVIEW.md`` §D.

Scope
-----
These tests were written WITHOUT permission to modify the implementation.
Every assertion below states what §C/§D require; where the implementation
disagrees the test is left failing on purpose.

Fixture provenance
------------------
The corpus is the real 220-task grade artifact::

    data/grades/exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json

That artifact is ``schema_version: "1.0"`` and predates the lifecycle /
provenance fields the merge contract is written against. Two deliberate,
documented normalisations turn it into a schema-1.3 corpus:

1. ``judge_error`` items are forced to ``score_excluded: true``. Schema 1.3
   *defines* that as the only legal representation (``core.grade_payload``
   raises "schema 1.3 judge_error must be score_excluded"), so this is the
   unique valid migration, not a guess. 20 of 275 judge_error items in the
   1.0 artifact needed it. It does not touch ``task["pct"]`` and therefore
   cannot move ``avg_score_pct``.
2. The lifecycle / provenance fields absent from 1.0 (``run_status``,
   ``expected_task_count``, ``expected_ordered_task_ids_sha256``,
   ``grader_source_hash``, ``anchor_projection``, ``renderer_fingerprint``,
   ``azure_ai_routes``, ``azure_ai_runtime_fingerprint``,
   ``source_inference_*``) are copied from the real 4-task anchor
   diagnostic run rather than invented, so every shape is one the pipeline
   actually emitted.

What "the original" means for the round-trip assertions
------------------------------------------------------
The 1.0 artifact's *stored* ``summary.openai_compat.avg_score_pct`` is
53.3, but recomputing it from those same 220 tasks with the current
``step8_grade._compute_summary`` yields 54.54 (the stored value divided by
the full corpus, 220, instead of by the graded corpus, 215 --
54.54 * 215 / 220 == 53.30). That is pre-existing drift between a legacy
artifact and current summary code; it has nothing to do with sharding.

The round-trip comparator is therefore the **serial recomputation over the
same corpus** -- literally what §F kill criterion 6 names ("동일 코퍼스
직렬 실행"). ``serial_reference_payload`` is that payload.
"""

from __future__ import annotations

import copy
import json
import math
import random
from pathlib import Path

import pytest

import step9_merge_shards as s9
from core.grade_payload import canonical_rate, validate_grade_payload
from step8_grade import (
    SCHEMA_VERSION,
    _compute_summary,
    _ordered_task_ids_sha256,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = (
    REPO_ROOT
    / "data"
    / "grades"
    / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools.json"
)
ANCHOR_GLOB = "data/grades/_diagnostic/*/*sol_max_anchor4*.json"

#: Both fingerprints below are real values observed in the 4-task anchor run.
FP_PRIMARY = "4883551d5001c23b50b24d0f2290fc01a6febacf73374667fce8a0c7111de517"
FP_SECOND = "5df8d48b6568d7a6ae41c99f61044cdab00e6cdee4cbc1ac4960efcf3881e5e7"

#: The judge in the corpus artifact declares no perception sub-judges, so
#: ``core.grade_payload`` requires exactly ``{judge.model}`` here.
UNPRICED_MODELS = ["gpt-5.4"]

#: Task count used by the invariant / task-set cases. The full 220-task
#: corpus is reserved for the round-trip and aggregate assertions; every
#: check exercised on this subset is task-count independent, and using a
#: subset keeps ~30 jsonschema validations off the critical path.
SMALL_TASK_COUNT = 24


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def grade_schema() -> dict:
    path = REPO_ROOT / "batch-runner" / "schemas" / "grade.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def raw_corpus() -> dict:
    """The real 13.9MB grade artifact, parsed exactly once."""
    assert CORPUS_PATH.is_file(), f"corpus fixture missing: {CORPUS_PATH}"
    return json.loads(CORPUS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def anchor_provenance() -> dict:
    """Real lifecycle/provenance field values from the 4-task anchor run."""
    matches = sorted(REPO_ROOT.glob(ANCHOR_GLOB))
    assert matches, f"anchor diagnostic fixture missing: {ANCHOR_GLOB}"
    anchor = json.loads(matches[0].read_text(encoding="utf-8"))
    return {
        "anchor_projection": anchor["anchor_projection"],
        "renderer_fingerprint": anchor["renderer_fingerprint"],
        "grader_source_hash": anchor["grader_source_hash"],
        "source_inference_repo_id": anchor["source_inference_repo_id"],
        "source_inference_revision": anchor["source_inference_revision"],
        "source_azure_ai_provenance_status": anchor[
            "source_azure_ai_provenance_status"
        ],
    }


def _normalised_tasks(raw_corpus: dict, limit: int | None = None) -> list[dict]:
    """Deep-copied corpus tasks migrated to the schema-1.3 item contract."""
    tasks = copy.deepcopy(raw_corpus["tasks"])
    if limit is not None:
        tasks = tasks[:limit]
    for task in tasks:
        for item in task["items"]:
            if item.get("verdict") == "judge_error":
                item["score_excluded"] = True
    return tasks


def _build_reference(
    raw_corpus: dict, anchor_provenance: dict, tasks: list[dict]
) -> dict:
    """Return the ``final`` payload a single serial run would have produced."""
    task_ids = [task["task_id"] for task in tasks]
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": raw_corpus["experiment_id"],
        "experiment_yaml_name": raw_corpus["experiment_yaml_name"],
        "source_inference_experiment_id": raw_corpus[
            "source_inference_experiment_id"
        ],
        "source_inference_run_dir": raw_corpus["source_inference_run_dir"],
        "source_inference_repo_id": anchor_provenance["source_inference_repo_id"],
        "source_inference_revision": anchor_provenance["source_inference_revision"],
        "source_azure_ai_provenance_status": anchor_provenance[
            "source_azure_ai_provenance_status"
        ],
        "inference_model": raw_corpus["inference_model"],
        "inference_completed_at": raw_corpus["inference_completed_at"],
        "judge": copy.deepcopy(raw_corpus["judge"]),
        "rubric": copy.deepcopy(raw_corpus["rubric"]),
        "prompt": copy.deepcopy(raw_corpus["prompt"]),
        "grader_source_hash": anchor_provenance["grader_source_hash"],
        "anchor_projection": copy.deepcopy(
            anchor_provenance["anchor_projection"]
        ),
        "renderer_fingerprint": copy.deepcopy(
            anchor_provenance["renderer_fingerprint"]
        ),
        "azure_ai_routes": [
            {
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": FP_PRIMARY,
                "workload": "grader",
            }
        ],
        "azure_ai_runtime_fingerprint": FP_PRIMARY,
        "run_status": "final",
        "expected_task_count": len(task_ids),
        "expected_ordered_task_ids_sha256": _ordered_task_ids_sha256(task_ids),
        "graded_at": raw_corpus["graded_at"],
        "graded_by": raw_corpus["graded_by"],
        "graded_by_version": raw_corpus["graded_by_version"],
        "tasks": tasks,
        "summary": _compute_summary(tasks, unpriced_models=UNPRICED_MODELS),
    }


@pytest.fixture(scope="session")
def serial_reference_payload(raw_corpus: dict, anchor_provenance: dict) -> dict:
    """220-task ``final`` payload == the serial-run comparator."""
    return _build_reference(
        raw_corpus, anchor_provenance, _normalised_tasks(raw_corpus)
    )


@pytest.fixture(scope="session")
def small_reference_payload(raw_corpus: dict, anchor_provenance: dict) -> dict:
    """24-task ``final`` payload for the fast invariant / task-set cases."""
    return _build_reference(
        raw_corpus,
        anchor_provenance,
        _normalised_tasks(raw_corpus, limit=SMALL_TASK_COUNT),
    )


def _graded_at(index: int) -> str:
    return f"2026-06-{10 + index:02d}T00:00:{index:02d}Z"


def make_shards(reference: dict, count: int, *, mode: str = "stride") -> list[dict]:
    """Split ``reference`` into ``count`` deep-copied ``partial`` shards.

    ``stride`` mirrors the adopted design (``tasks[shard_index::shard_count]``
    per §C); ``block`` is a contiguous split used to probe the layout
    reconstruction path.
    """
    tasks = reference["tasks"]
    identity = {
        key: value
        for key, value in reference.items()
        if key not in {"tasks", "summary"}
    }
    shards: list[dict] = []
    for index in range(count):
        if mode == "stride":
            subset = copy.deepcopy(tasks[index::count])
        elif mode == "block":
            per = (len(tasks) + count - 1) // count
            subset = copy.deepcopy(tasks[index * per : (index + 1) * per])
        else:  # pragma: no cover - guards test authoring mistakes
            raise AssertionError(f"unknown split mode: {mode}")
        shard = copy.deepcopy(identity)
        shard["run_status"] = "partial"
        shard["tasks"] = subset
        shard["summary"] = _compute_summary(
            subset, unpriced_models=UNPRICED_MODELS
        )
        shard["graded_at"] = _graded_at(index)
        shards.append(shard)
    return shards


def merge(shards: list[dict], **kwargs) -> dict:
    """Merge with warnings captured so stderr stays clean during tests."""
    kwargs.setdefault("warn", lambda _message: None)
    return s9.merge_shard_payloads(shards, **kwargs)


# ---------------------------------------------------------------------------
# fixture-integrity guards
#
# If these fail, every later assertion is meaningless -- the corpus is not
# what the merge contract assumes.
# ---------------------------------------------------------------------------


def test_corpus_fixture_is_the_expected_220_task_artifact(raw_corpus: dict) -> None:
    assert len(raw_corpus["tasks"]) == 220
    assert len({task["task_id"] for task in raw_corpus["tasks"]}) == 220
    assert raw_corpus["schema_version"] == "1.0"


def test_serial_reference_is_a_valid_final_payload(
    serial_reference_payload: dict, grade_schema: dict
) -> None:
    validate_grade_payload(serial_reference_payload, grade_schema)
    assert serial_reference_payload["run_status"] == "final"
    assert serial_reference_payload["expected_task_count"] == 220


def test_legacy_stored_average_differs_from_serial_recomputation(
    raw_corpus: dict, serial_reference_payload: dict
) -> None:
    """Pin the legacy-vs-current drift so it is never mistaken for a merge bug.

    The 1.0 artifact averaged over all 220 tasks; ``_compute_summary``
    averages over the 215 non-error tasks.
    """
    stored = raw_corpus["summary"]["openai_compat"]["avg_score_pct"]
    serial = serial_reference_payload["summary"]["openai_compat"][
        "avg_score_pct"
    ]
    assert stored == 53.3
    assert serial == 54.54
    assert round(serial * 215 / 220, 2) == stored


# ---------------------------------------------------------------------------
# §4 case 1 + 2 -- round-trip identity, N in {2, 3, 9}
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [2, 3, 9])
def test_roundtrip_restores_canonical_task_order(
    serial_reference_payload: dict, count: int
) -> None:
    merged = merge(make_shards(serial_reference_payload, count))
    assert [task["task_id"] for task in merged["tasks"]] == [
        task["task_id"] for task in serial_reference_payload["tasks"]
    ]


@pytest.mark.parametrize("count", [2, 3, 9])
def test_roundtrip_restores_full_task_set(
    serial_reference_payload: dict, count: int
) -> None:
    merged = merge(make_shards(serial_reference_payload, count))
    assert len(merged["tasks"]) == 220
    assert {task["task_id"] for task in merged["tasks"]} == {
        task["task_id"] for task in serial_reference_payload["tasks"]
    }


@pytest.mark.parametrize("count", [2, 3, 9])
def test_roundtrip_preserves_per_task_scores(
    serial_reference_payload: dict, count: int
) -> None:
    merged = merge(make_shards(serial_reference_payload, count))
    expected = {
        task["task_id"]: (task["pct"], task["total_awarded"], task["total_max"])
        for task in serial_reference_payload["tasks"]
    }
    actual = {
        task["task_id"]: (task["pct"], task["total_awarded"], task["total_max"])
        for task in merged["tasks"]
    }
    assert actual == expected


@pytest.mark.parametrize("count", [2, 3, 9])
def test_roundtrip_avg_score_pct_is_exactly_serial(
    serial_reference_payload: dict, count: int
) -> None:
    """§E completion criterion: exact equality, never approximate."""
    merged = merge(make_shards(serial_reference_payload, count))
    assert (
        merged["summary"]["openai_compat"]["avg_score_pct"]
        == serial_reference_payload["summary"]["openai_compat"]["avg_score_pct"]
    )


@pytest.mark.parametrize("count", [2, 3, 9])
def test_roundtrip_summary_is_identical_to_serial(
    serial_reference_payload: dict, count: int
) -> None:
    """§D: every recomputed aggregate matches a serial run over the corpus."""
    merged = merge(make_shards(serial_reference_payload, count))
    assert merged["summary"] == serial_reference_payload["summary"]


@pytest.mark.parametrize("count", [2, 3, 9])
def test_merged_payload_passes_validate_grade_payload(
    serial_reference_payload: dict, grade_schema: dict, count: int
) -> None:
    """§E completion criterion, asserted independently of the merge's own
    internal validation call."""
    merged = merge(make_shards(serial_reference_payload, count))
    validate_grade_payload(merged, grade_schema)


@pytest.mark.parametrize("count", [2, 3, 9])
def test_merged_run_status_is_final(
    serial_reference_payload: dict, count: int
) -> None:
    merged = merge(make_shards(serial_reference_payload, count))
    assert merged["run_status"] == "final"


def test_nine_way_split_is_uneven_as_the_spec_requires(
    serial_reference_payload: dict,
) -> None:
    """220 % 9 == 4: four shards of 25 and five of 24."""
    shards = make_shards(serial_reference_payload, 9)
    sizes = sorted(len(shard["tasks"]) for shard in shards)
    assert sizes == [24] * 5 + [25] * 4
    assert sum(sizes) == 220


# ---------------------------------------------------------------------------
# §4 strong assertions -- identity, rates, cost sums, graded_at
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("count", [2, 3, 9])
def test_merged_identity_fields_are_adopted_from_shards(
    serial_reference_payload: dict, count: int
) -> None:
    """§D 'verify then adopt' rows survive the merge unchanged."""
    merged = merge(make_shards(serial_reference_payload, count))
    for field in (
        "schema_version",
        "experiment_id",
        "inference_model",
        "grader_source_hash",
        "renderer_fingerprint",
        "anchor_projection",
        "source_inference_repo_id",
        "source_inference_revision",
        "expected_task_count",
        "expected_ordered_task_ids_sha256",
        "graded_by",
        "graded_by_version",
        "judge",
        "rubric",
        "prompt",
    ):
        assert merged[field] == serial_reference_payload[field], field


@pytest.mark.parametrize("count", [2, 3, 9])
def test_judge_error_rate_matches_canonical_rate(
    serial_reference_payload: dict, count: int
) -> None:
    """§D: judge_error_rate == canonical_rate(judge_errors, judge_items)."""
    merged = merge(make_shards(serial_reference_payload, count))
    judge_items = 0
    judge_errors = 0
    for task in merged["tasks"]:
        for item in task["items"]:
            if item.get("decided_by") == "judge":
                judge_items += 1
                if item.get("verdict") == "judge_error":
                    judge_errors += 1
    assert judge_items > 0
    assert judge_errors > 0
    assert merged["summary"]["wow"]["judge_error_rate"] == canonical_rate(
        judge_errors, judge_items
    )


@pytest.mark.parametrize("count", [2, 3, 9])
def test_integer_cost_counters_equal_the_shard_sum(
    serial_reference_payload: dict, count: int
) -> None:
    """§D: token / call counters are summed across shards."""
    shards = make_shards(serial_reference_payload, count)
    merged = merge(copy.deepcopy(shards))
    for field in s9.SUMMABLE_COST_FIELDS:
        expected = sum(shard["summary"]["cost"][field] for shard in shards)
        assert merged["summary"]["cost"][field] == expected, field


@pytest.mark.parametrize("count", [2, 3, 9])
def test_cost_pricing_fields_are_pinned(
    serial_reference_payload: dict, count: int
) -> None:
    """§D: estimated_cost_usd None, pricing_complete False, unpriced adopted."""
    merged = merge(make_shards(serial_reference_payload, count))
    cost = merged["summary"]["cost"]
    assert cost["estimated_cost_usd"] is None
    assert cost["pricing_complete"] is False
    assert cost["unpriced_models"] == UNPRICED_MODELS


@pytest.mark.parametrize("count", [2, 3, 9])
def test_summary_task_counts_are_recomputed_from_merged_tasks(
    serial_reference_payload: dict, count: int
) -> None:
    """§D: summary.total/graded/error_tasks recomputed, not summed blindly."""
    merged = merge(make_shards(serial_reference_payload, count))
    summary = merged["summary"]
    graded = sum(1 for task in merged["tasks"] if not task.get("error"))
    assert summary["total_tasks"] == len(merged["tasks"]) == 220
    assert summary["graded_tasks"] == graded
    assert summary["error_tasks"] == 220 - graded


def test_graded_at_is_the_maximum_shard_timestamp(
    small_reference_payload: dict,
) -> None:
    """§D: graded_at is the completion moment == max over shards.

    The maximum is deliberately placed on the middle shard so that a
    "take the first"/"take the last" implementation cannot pass.
    """
    shards = make_shards(small_reference_payload, 3)
    shards[0]["graded_at"] = "2026-06-10T00:00:00Z"
    shards[1]["graded_at"] = "2026-07-01T12:00:00Z"
    shards[2]["graded_at"] = "2026-06-11T00:00:00Z"
    merged = merge(shards)
    assert merged["graded_at"] == "2026-07-01T12:00:00Z"


def test_graded_at_max_compares_instants_not_strings(
    small_reference_payload: dict,
) -> None:
    """'2026-07-01T20:00:00+09:00' sorts above 'T12:00:00Z' as a string but
    is 11:00Z, i.e. one hour EARLIER. The instant must win."""
    shards = make_shards(small_reference_payload, 2)
    shards[0]["graded_at"] = "2026-07-01T12:00:00Z"
    shards[1]["graded_at"] = "2026-07-01T20:00:00+09:00"
    merged = merge(shards)
    assert merged["graded_at"] == "2026-07-01T12:00:00Z"


def test_per_task_graded_at_is_preserved(serial_reference_payload: dict) -> None:
    """§D: task-level graded_at survives even though the top level is a max."""
    merged = merge(make_shards(serial_reference_payload, 3))
    expected = {
        task["task_id"]: task["graded_at"]
        for task in serial_reference_payload["tasks"]
    }
    actual = {task["task_id"]: task["graded_at"] for task in merged["tasks"]}
    assert actual == expected


# ---------------------------------------------------------------------------
# §4 case 3 -- the twelve §C invariants, violated individually
# ---------------------------------------------------------------------------


def _set_nested(payload: dict, path: tuple[str, ...], value) -> None:
    node = payload
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


#: (reported field name, dotted path, replacement value). Invariants 1-10 of
#: §C -- the fields ``_validate_grade_resume_identity`` pins.
CONTRACT_INVARIANT_CASES = [
    ("schema_version", ("schema_version",), "1.2"),
    ("experiment_id", ("experiment_id",), "exp999_other_experiment"),
    ("rubric.commit_sha", ("rubric", "commit_sha"), "0" * 40),
    ("prompt.version", ("prompt", "version"), "v9"),
    ("judge.config_hash", ("judge", "config_hash"), "deadbeefdeadbeef"),
    (
        "source_inference_repo_id",
        ("source_inference_repo_id",),
        "SomeoneElse/other-run",
    ),
    ("source_inference_revision", ("source_inference_revision",), "b" * 40),
    ("grader_source_hash", ("grader_source_hash",), "c" * 64),
    ("anchor_projection", ("anchor_projection",), None),
    ("renderer_fingerprint", ("renderer_fingerprint",), None),
]


@pytest.mark.parametrize(
    "field_name,path,replacement",
    CONTRACT_INVARIANT_CASES,
    ids=[case[0] for case in CONTRACT_INVARIANT_CASES],
)
def test_contract_invariant_violation_fails_naming_the_field(
    small_reference_payload: dict, field_name: str, path: tuple, replacement
) -> None:
    """§E-3: any of the ten identity invariants disagreeing must fail, with a
    message that names the offending field.

    Asserting on the field name matters: several of these replacements are
    also schema-invalid, so a bare ``pytest.raises(ShardMergeError)`` could
    pass because the *payload validation* fired instead of the *invariant
    check*. The field name proves which one ran.
    """
    shards = make_shards(small_reference_payload, 3)
    _set_nested(shards[1], path, replacement)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert field_name in str(excinfo.value)


def test_every_contract_identity_field_is_covered(small_reference_payload) -> None:
    """Guard: the parametrised list must track ``CONTRACT_IDENTITY_FIELDS``."""
    covered = {case[0] for case in CONTRACT_INVARIANT_CASES}
    declared = {name for name, _path in s9.CONTRACT_IDENTITY_FIELDS}
    assert covered == declared


def test_invariant_11_route_drift_fails_under_strict_routes(
    small_reference_payload: dict,
) -> None:
    """§C invariant 11 (``azure_ai_routes``) under the literal reading."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["azure_ai_routes"] = shards[1]["azure_ai_routes"] + [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": FP_SECOND,
            "workload": "grader",
        }
    ]
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards, strict_routes=True)
    assert "azure_ai_routes" in str(excinfo.value)


def test_invariant_12_fingerprint_drift_fails_under_strict_routes(
    small_reference_payload: dict,
) -> None:
    """§C invariant 12 (``azure_ai_runtime_fingerprint``).

    Note the structural coupling: ``azure_ai_routes[0].runtime_fingerprint``
    must equal ``azure_ai_runtime_fingerprint`` within a shard, so a
    fingerprint that differs across shards necessarily makes the route lists
    differ too. Invariant 12 is therefore not independently reachable; the
    merge reports it against ``azure_ai_routes``.
    """
    shards = make_shards(small_reference_payload, 3)
    shards[1]["azure_ai_routes"] = [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": FP_SECOND,
            "workload": "grader",
        }
    ]
    shards[1]["azure_ai_runtime_fingerprint"] = FP_SECOND
    with pytest.raises(s9.ShardMergeError):
        merge(shards, strict_routes=True)


def test_fingerprint_must_match_its_own_primary_route(
    small_reference_payload: dict,
) -> None:
    """Structural half of invariant 12, reachable in both modes."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["azure_ai_runtime_fingerprint"] = FP_SECOND
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "primary grader route fingerprint mismatch" in str(excinfo.value)


def test_default_mode_unions_routes_instead_of_rejecting_drift(
    small_reference_payload: dict,
) -> None:
    """§D: order-preserving union deduplicated by runtime_fingerprint, and
    the fingerprint is taken from the canonically-first shard.

    In the DEFAULT (non-strict) mode invariants 11-12 do NOT hard-fail --
    drift is downgraded to a warning, so only 10 of the 12 §C invariants are
    enforced by default. Per F-2 that relaxation must be *auditable*: the
    merge is additionally required to record each shard's own fingerprint in
    ``shard_provenance``, so "not enforced" never means "not recorded".
    """
    shards = make_shards(small_reference_payload, 3)
    shards[1]["azure_ai_routes"] = [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": FP_SECOND,
            "workload": "grader",
        }
    ]
    shards[1]["azure_ai_runtime_fingerprint"] = FP_SECOND
    warnings: list[str] = []
    merged = s9.merge_shard_payloads(shards, warn=warnings.append)
    assert [
        route["runtime_fingerprint"] for route in merged["azure_ai_routes"]
    ] == [FP_PRIMARY, FP_SECOND]
    assert merged["azure_ai_runtime_fingerprint"] == FP_PRIMARY
    assert merged["azure_ai_routes"][0]["runtime_fingerprint"] == FP_PRIMARY
    assert any("azure_ai_runtime_fingerprint" in note for note in warnings)
    assert [
        entry["azure_ai_runtime_fingerprint"]
        for entry in merged["shard_provenance"]
    ] == [FP_PRIMARY, FP_SECOND, FP_PRIMARY]


def test_unpriced_models_mismatch_fails(small_reference_payload: dict) -> None:
    """§F kill criterion 2 / §D: unpriced_models must agree across shards."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"]["unpriced_models"] = ["gpt-5.4", "gpt-audio-1.5"]
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "unpriced_models" in str(excinfo.value)


def test_expected_task_count_mismatch_fails(small_reference_payload: dict) -> None:
    shards = make_shards(small_reference_payload, 3)
    shards[1]["expected_task_count"] = SMALL_TASK_COUNT + 1
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "expected_task_count" in str(excinfo.value)


def test_expected_ordered_task_ids_sha256_mismatch_fails(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    shards[1]["expected_ordered_task_ids_sha256"] = "d" * 64
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "expected_ordered_task_ids_sha256" in str(excinfo.value)


def test_non_partial_shard_is_rejected(small_reference_payload: dict) -> None:
    """Guards against merging an already-final payload a second time."""
    shards = make_shards(small_reference_payload, 3)
    shards[2]["run_status"] = "final"
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "partial" in str(excinfo.value)


# ---------------------------------------------------------------------------
# §4 case 4 + 5 -- task-set defects
# ---------------------------------------------------------------------------


def test_duplicate_task_across_shards_fails(small_reference_payload: dict) -> None:
    """§D: shards must be disjoint."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["tasks"][0] = copy.deepcopy(shards[0]["tasks"][0])
    shards[1]["summary"] = _compute_summary(
        shards[1]["tasks"], unpriced_models=UNPRICED_MODELS
    )
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    message = str(excinfo.value)
    assert "not disjoint" in message
    assert shards[0]["tasks"][0]["task_id"] in message


def test_duplicate_task_within_one_shard_fails(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    shards[0]["tasks"].append(copy.deepcopy(shards[0]["tasks"][0]))
    shards[0]["summary"] = _compute_summary(
        shards[0]["tasks"], unpriced_models=UNPRICED_MODELS
    )
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "duplicate task_ids" in str(excinfo.value)


def test_missing_task_refuses_final_promotion(
    small_reference_payload: dict,
) -> None:
    """§E-6: an incomplete union is a hard failure, never a quiet partial."""
    shards = make_shards(small_reference_payload, 3)
    shards[2]["tasks"] = shards[2]["tasks"][:-1]
    shards[2]["summary"] = _compute_summary(
        shards[2]["tasks"], unpriced_models=UNPRICED_MODELS
    )
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    message = str(excinfo.value)
    assert "incomplete" in message
    assert str(SMALL_TASK_COUNT - 1) in message


def test_missing_shard_entirely_refuses_final_promotion(
    small_reference_payload: dict,
) -> None:
    """A whole shard lost to a failed relay must not silently publish."""
    shards = make_shards(small_reference_payload, 3)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards[:2])
    assert "incomplete" in str(excinfo.value)


def test_extra_unknown_task_fails(small_reference_payload: dict) -> None:
    """A task outside the declared corpus must not be absorbed."""
    shards = make_shards(small_reference_payload, 3)
    intruder = copy.deepcopy(shards[2]["tasks"][0])
    intruder["task_id"] = "ffffffff-0000-0000-0000-000000000000"
    shards[2]["tasks"].append(intruder)
    shards[2]["summary"] = _compute_summary(
        shards[2]["tasks"], unpriced_models=UNPRICED_MODELS
    )
    with pytest.raises(s9.ShardMergeError):
        merge(shards)


# ---------------------------------------------------------------------------
# §4 case 6 -- input order independence
# ---------------------------------------------------------------------------


def test_shuffled_input_order_normalises_to_canonical_order(
    serial_reference_payload: dict,
) -> None:
    shards = make_shards(serial_reference_payload, 9)
    random.Random(20260814).shuffle(shards)
    merged = merge(shards)
    assert [task["task_id"] for task in merged["tasks"]] == [
        task["task_id"] for task in serial_reference_payload["tasks"]
    ]


def test_shuffled_input_produces_a_byte_identical_payload(
    serial_reference_payload: dict,
) -> None:
    """§E-1 determinism: command-line order must not perturb ANY field,
    including key order and shard_provenance."""
    ordered = merge(make_shards(serial_reference_payload, 9))
    shuffled_input = make_shards(serial_reference_payload, 9)
    random.Random(4242).shuffle(shuffled_input)
    shuffled = merge(shuffled_input)
    assert json.dumps(shuffled, sort_keys=True) == json.dumps(
        ordered, sort_keys=True
    )
    assert list(shuffled.keys()) == list(ordered.keys())


def test_merge_is_repeatable(small_reference_payload: dict) -> None:
    first = merge(make_shards(small_reference_payload, 3))
    second = merge(make_shards(small_reference_payload, 3))
    assert first == second


def test_merge_does_not_mutate_the_input_shards(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    before = json.dumps(shards, sort_keys=True)
    merge(copy.deepcopy(shards))
    assert json.dumps(shards, sort_keys=True) == before


# ---------------------------------------------------------------------------
# §4 case 7 -- usage_complete
# ---------------------------------------------------------------------------


def test_usage_complete_false_in_any_shard_makes_merge_false(
    small_reference_payload: dict,
) -> None:
    """§D: true only when EVERY shard is true."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"]["usage_complete"] = False
    warnings: list[str] = []
    merged = s9.merge_shard_payloads(shards, warn=warnings.append)
    assert merged["summary"]["cost"]["usage_complete"] is False
    assert any("usage_complete" in note for note in warnings)


def test_usage_complete_true_when_all_shards_true(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    assert all(
        shard["summary"]["cost"]["usage_complete"] is True for shard in shards
    )
    merged = merge(shards)
    assert merged["summary"]["cost"]["usage_complete"] is True


def test_non_boolean_usage_complete_is_rejected(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"]["usage_complete"] = "yes"
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "usage_complete" in str(excinfo.value)


# ---------------------------------------------------------------------------
# §4 case 8 -- boundaries
# ---------------------------------------------------------------------------


def test_empty_input_fails(small_reference_payload: dict) -> None:
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge([])
    assert "no shard payloads" in str(excinfo.value)


def test_single_shard_holding_the_whole_corpus_is_promoted(
    small_reference_payload: dict, grade_schema: dict
) -> None:
    """Degenerate 1-way shard: a complete partial becomes final."""
    shards = make_shards(small_reference_payload, 1)
    assert len(shards) == 1
    assert len(shards[0]["tasks"]) == SMALL_TASK_COUNT
    merged = merge(shards)
    validate_grade_payload(merged, grade_schema)
    assert merged["run_status"] == "final"
    assert merged["summary"] == small_reference_payload["summary"]


def test_shard_with_zero_tasks_fails(small_reference_payload: dict) -> None:
    """A shard that graded nothing must not be silently absorbed.

    The shard summary is recomputed alongside the emptied task list so the
    payload stays internally consistent -- otherwise the per-shard
    ``validate_grade_payload`` call fires first and this test would pass for
    the wrong reason (see the companion test below).
    """
    shards = make_shards(small_reference_payload, 3)
    shards[1]["tasks"] = []
    shards[1]["summary"] = _compute_summary([], unpriced_models=UNPRICED_MODELS)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "zero graded tasks" in str(excinfo.value)


def test_each_shard_is_validated_before_merging(
    small_reference_payload: dict,
) -> None:
    """A shard whose own summary disagrees with its tasks is rejected by
    ``validate_grade_payload`` before any merging happens."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["tasks"] = []
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    message = str(excinfo.value)
    assert "shard[1]" in message
    assert "not a valid grade payload" in message


def test_non_dict_shard_is_rejected(small_reference_payload: dict) -> None:
    shards = make_shards(small_reference_payload, 2)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge([shards[0], ["not", "an", "object"]])
    assert "must be an object" in str(excinfo.value)


# ---------------------------------------------------------------------------
# shard_provenance (§D recommended field)
# ---------------------------------------------------------------------------


def test_shard_provenance_records_every_shard_in_canonical_order(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    merged = merge(copy.deepcopy(shards))
    provenance = merged["shard_provenance"]
    assert len(provenance) == 3
    assert [entry["index"] for entry in provenance] == [0, 1, 2]
    assert {entry["count"] for entry in provenance} == {3}
    assert [entry["graded_at"] for entry in provenance] == [
        shard["graded_at"] for shard in shards
    ]
    for entry in provenance:
        assert entry["config_hash"] == small_reference_payload["judge"][
            "config_hash"
        ]
        assert len(entry["grade_file_sha256"]) == 64


def test_shard_provenance_entry_shape_is_exact(
    small_reference_payload: dict,
) -> None:
    """Pin the entry key set exactly.

    ``shard_provenance`` is absent from ``grade.schema.json`` and the
    top-level ``additionalProperties`` is ``true``, so
    ``validate_grade_payload`` neither requires nor rejects any of these
    keys -- deleting ``azure_ai_runtime_fingerprint`` would still validate.
    This assertion is therefore the only thing holding the F-2 record in
    place, so it is exact rather than a containment check.
    """
    merged = merge(make_shards(small_reference_payload, 3))
    for entry in merged["shard_provenance"]:
        assert set(entry) == {
            "index",
            "count",
            "config_hash",
            "grade_file_sha256",
            "graded_at",
            "azure_ai_runtime_fingerprint",
        }


def test_shard_provenance_records_fingerprint_drift_without_failing(
    small_reference_payload: dict, grade_schema: dict
) -> None:
    """F-2 core: drifting shards still merge, and BOTH observed fingerprints
    survive in ``shard_provenance`` while the top level keeps shard 0's.

    An auditor holding only the merged file must be able to see that the
    shards disagreed. Before F-2 that fact existed solely as a stderr
    warning and the artifact showed a single uniform fingerprint.
    """
    shards = make_shards(small_reference_payload, 3)
    for index in (1, 2):
        shards[index]["azure_ai_routes"] = [
            {
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": FP_SECOND,
                "workload": "grader",
            }
        ]
        shards[index]["azure_ai_runtime_fingerprint"] = FP_SECOND
    warnings: list[str] = []
    merged = s9.merge_shard_payloads(shards, warn=warnings.append)

    validate_grade_payload(merged, grade_schema)
    assert merged["run_status"] == "final"
    recorded = [
        entry["azure_ai_runtime_fingerprint"]
        for entry in merged["shard_provenance"]
    ]
    assert recorded == [FP_PRIMARY, FP_SECOND, FP_SECOND]
    assert set(recorded) == {FP_PRIMARY, FP_SECOND}
    assert merged["azure_ai_runtime_fingerprint"] == FP_PRIMARY
    assert [
        route["runtime_fingerprint"] for route in merged["azure_ai_routes"]
    ] == [FP_PRIMARY, FP_SECOND]
    assert any("azure_ai_runtime_fingerprint" in note for note in warnings)


def test_shard_provenance_fingerprint_matches_the_shard_that_carried_it(
    small_reference_payload: dict,
) -> None:
    """F-2: the recorded value is the shard's own, not shard 0's copied N
    times. The drift is placed on the LAST shard so an implementation that
    broadcast the primary fingerprint cannot pass."""
    shards = make_shards(small_reference_payload, 3)
    shards[2]["azure_ai_routes"] = [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": FP_SECOND,
            "workload": "grader",
        }
    ]
    shards[2]["azure_ai_runtime_fingerprint"] = FP_SECOND
    merged = s9.merge_shard_payloads(shards, warn=lambda _message: None)
    assert [
        entry["azure_ai_runtime_fingerprint"]
        for entry in merged["shard_provenance"]
    ] == [FP_PRIMARY, FP_PRIMARY, FP_SECOND]


def test_shard_provenance_fingerprints_are_uniform_without_drift(
    small_reference_payload: dict,
) -> None:
    """F-2: with no drift every entry carries the same fingerprint, which is
    also the merged top-level value."""
    merged = merge(make_shards(small_reference_payload, 3))
    assert [
        entry["azure_ai_runtime_fingerprint"]
        for entry in merged["shard_provenance"]
    ] == [FP_PRIMARY] * 3
    assert merged["azure_ai_runtime_fingerprint"] == FP_PRIMARY


def test_shard_provenance_fingerprints_survive_the_cli_round_trip(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    """F-2: the record reaches disk, not just the in-memory dict."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["azure_ai_routes"] = [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": FP_SECOND,
            "workload": "grader",
        }
    ]
    shards[1]["azure_ai_runtime_fingerprint"] = FP_SECOND
    paths = _write_shards(tmp_path, shards)
    out = tmp_path / "merged.json"
    assert s9.main([*[str(p) for p in paths], "--output", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert [
        entry["azure_ai_runtime_fingerprint"]
        for entry in written["shard_provenance"]
    ] == [FP_PRIMARY, FP_SECOND, FP_PRIMARY]
    assert written["azure_ai_runtime_fingerprint"] == FP_PRIMARY


def test_strict_routes_still_rejects_the_drift_that_provenance_records(
    small_reference_payload: dict,
) -> None:
    """F-2 changes recording only: the same shard set that merges (and is
    recorded) by default must still hard-fail under ``--strict-routes``."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["azure_ai_routes"] = [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": FP_SECOND,
            "workload": "grader",
        }
    ]
    shards[1]["azure_ai_runtime_fingerprint"] = FP_SECOND
    assert (
        s9.merge_shard_payloads(
            copy.deepcopy(shards), warn=lambda _message: None
        )["shard_provenance"][1]["azure_ai_runtime_fingerprint"]
        == FP_SECOND
    )
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards, strict_routes=True)
    assert "azure_ai_routes" in str(excinfo.value)


def test_shard_provenance_uses_supplied_digests(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 2)
    merged = merge(
        shards, source_digests=["a" * 64, "b" * 64], source_labels=["s0", "s1"]
    )
    assert [entry["grade_file_sha256"] for entry in merged["shard_provenance"]] == [
        "a" * 64,
        "b" * 64,
    ]


def test_shard_provenance_does_not_break_schema_validation(
    small_reference_payload: dict, grade_schema: dict
) -> None:
    """§D: the schema's top-level additionalProperties:true absorbs it."""
    merged = merge(make_shards(small_reference_payload, 3))
    assert "shard_provenance" in merged
    validate_grade_payload(merged, grade_schema)


# ---------------------------------------------------------------------------
# corpus-order reconstruction
# ---------------------------------------------------------------------------


def test_block_split_cannot_be_reconstructed_without_explicit_ids(
    serial_reference_payload: dict,
) -> None:
    """Only the adopted stride layout is auto-reconstructible.

    A contiguous-block shard layout is rejected with an actionable message
    rather than silently reordered.
    """
    shards = make_shards(serial_reference_payload, 3, mode="block")
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    message = str(excinfo.value)
    assert "canonical corpus order could not be reconstructed" in message
    assert "--expected-task-ids" in message


def test_block_split_merges_when_canonical_ids_are_supplied(
    serial_reference_payload: dict,
) -> None:
    task_ids = [task["task_id"] for task in serial_reference_payload["tasks"]]
    shards = make_shards(serial_reference_payload, 3, mode="block")
    merged = merge(shards, expected_task_ids=task_ids)
    assert [task["task_id"] for task in merged["tasks"]] == task_ids
    assert (
        merged["summary"]["openai_compat"]["avg_score_pct"]
        == serial_reference_payload["summary"]["openai_compat"]["avg_score_pct"]
    )


def test_explicit_ids_that_disagree_with_the_declared_hash_fail(
    small_reference_payload: dict,
) -> None:
    task_ids = [task["task_id"] for task in small_reference_payload["tasks"]]
    reordered = list(reversed(task_ids))
    shards = make_shards(small_reference_payload, 3)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards, expected_task_ids=reordered)
    assert "expected_ordered_task_ids_sha256" in str(excinfo.value)


def test_explicit_ids_with_wrong_count_fail(
    small_reference_payload: dict,
) -> None:
    task_ids = [task["task_id"] for task in small_reference_payload["tasks"]]
    shards = make_shards(small_reference_payload, 3)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards, expected_task_ids=task_ids[:-1])
    assert "count does not match" in str(excinfo.value)


# ---------------------------------------------------------------------------
# latency semantics (§D 'sum' row vs the module's serial-identity guarantee)
# ---------------------------------------------------------------------------


def test_latency_totals_are_serial_identical(
    serial_reference_payload: dict,
) -> None:
    """The merged latency equals a serial run's latency exactly."""
    for count in (2, 3, 9):
        merged = merge(make_shards(serial_reference_payload, count))
        for field in (
            "total_judge_latency_sec",
            "total_main_judge_latency_sec",
            "total_perception_latency_sec",
            "total_render_latency_sec",
        ):
            assert (
                merged["summary"]["cost"][field]
                == serial_reference_payload["summary"]["cost"][field]
            ), (count, field)


def test_latency_total_can_differ_from_the_shard_sum(
    serial_reference_payload: dict,
) -> None:
    """Characterisation of a real divergence from the §D 'sum' row.

    Each shard rounds its own latency to 2dp, so summing shard-reported
    latencies is NOT the same number as recomputing from merged tasks. At
    N=3 the two differ by 0.01s. ``SUMMABLE_COST_FIELDS`` still covers only
    the 13 integer counters -- the float fields are cross-checked separately
    by ``_check_latency_sums``, within a tolerance wide enough to absorb
    exactly this rounding drift.

    The recomputed value is the serial-run value, so the OUTPUT is correct;
    what this pins is that "summed" and "recomputed" are not interchangeable
    for the float fields, and that the 0.01s divergence stays legal.
    """
    shards = make_shards(serial_reference_payload, 3)
    merged = merge(copy.deepcopy(shards))
    shard_sum = round(
        sum(shard["summary"]["cost"]["total_judge_latency_sec"] for shard in shards),
        2,
    )
    merged_value = merged["summary"]["cost"]["total_judge_latency_sec"]
    assert merged_value != shard_sum
    assert abs(merged_value - shard_sum) < 0.02
    assert "total_judge_latency_sec" not in s9.SUMMABLE_COST_FIELDS


def test_tampered_shard_integer_counter_is_detected(
    small_reference_payload: dict,
) -> None:
    """``_check_cost_sums`` catches a hand-edited integer counter."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"]["total_input_tokens"] += 1
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "total_input_tokens" in str(excinfo.value)


def test_tampered_shard_latency_is_detected(
    small_reference_payload: dict,
) -> None:
    """F-1: +10000s on one shard's reported latency now fails the merge.

    Inverted from ``test_tampered_shard_latency_is_not_detected``, which
    documented the pre-F-1 gap: the float latency fields sit outside
    ``SUMMABLE_COST_FIELDS``, so nothing read them and the tampering passed
    silently. The message must name the field and show both sides plus the
    tolerance, so an operator can tell tampering from rounding.
    """
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"]["total_judge_latency_sec"] += 10_000.0
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    message = str(excinfo.value)
    assert "total_judge_latency_sec" in message
    assert "recomputed=" in message
    assert "shard_sum=" in message
    assert "tolerance=" in message


def _shard_latency_sum(shards: list[dict], field: str) -> float:
    """Shard-reported latency sum, computed the way the merge computes it."""
    return math.fsum(shard["summary"]["cost"][field] for shard in shards)


def _skew_shard_latency(
    shards: list[dict], reference: dict, field: str, target_gap: float
) -> float:
    """Edit one shard so ``|recomputed - shard_sum|`` becomes ``target_gap``.

    Returns the gap actually achieved so the caller can prove the boundary
    was hit rather than approached.
    """
    recomputed = reference["summary"]["cost"][field]
    gap = recomputed - _shard_latency_sum(shards, field)
    shards[1]["summary"]["cost"][field] += gap - target_gap
    return abs(recomputed - _shard_latency_sum(shards, field))


def test_latency_gap_just_inside_the_tolerance_is_accepted(
    small_reference_payload: dict,
) -> None:
    """F-1 boundary: a gap 0.001s INSIDE ``0.01 x n`` merges, and the emitted
    latency is still the recomputed serial value, not the skewed shard sum."""
    field = "total_judge_latency_sec"
    count = 3
    tolerance = s9.LATENCY_TOLERANCE_SEC_PER_SHARD * count
    shards = make_shards(small_reference_payload, count)
    achieved = _skew_shard_latency(
        shards, small_reference_payload, field, tolerance - 0.001
    )
    assert tolerance - 0.002 < achieved < tolerance
    merged = merge(shards)
    assert (
        merged["summary"]["cost"][field]
        == small_reference_payload["summary"]["cost"][field]
    )


def test_latency_gap_just_outside_the_tolerance_is_rejected(
    small_reference_payload: dict,
) -> None:
    """F-1 boundary: a gap 0.001s OUTSIDE ``0.01 x n`` is a hard failure."""
    field = "total_judge_latency_sec"
    count = 3
    tolerance = s9.LATENCY_TOLERANCE_SEC_PER_SHARD * count
    shards = make_shards(small_reference_payload, count)
    achieved = _skew_shard_latency(
        shards, small_reference_payload, field, tolerance + 0.001
    )
    assert tolerance < achieved < tolerance + 0.002
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert field in str(excinfo.value)


def test_latency_tolerance_scales_with_the_shard_count(
    small_reference_payload: dict,
) -> None:
    """F-1: the budget is per shard, so a gap legal at n=9 is illegal at n=2.

    0.05s sits inside ``0.01 x 9`` but outside ``0.01 x 2``. This is what
    stops the tolerance from being a flat constant that a 2-way merge would
    treat as nine shards' worth of slack.
    """
    field = "total_judge_latency_sec"
    nine = make_shards(small_reference_payload, 9)
    assert (
        _skew_shard_latency(nine, small_reference_payload, field, 0.05) < 0.09
    )
    assert merge(nine)["summary"]["cost"][field] == small_reference_payload[
        "summary"
    ]["cost"][field]

    two = make_shards(small_reference_payload, 2)
    _skew_shard_latency(two, small_reference_payload, field, 0.05)
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(two)
    assert field in str(excinfo.value)


@pytest.mark.parametrize("field", list(s9.LATENCY_COST_FIELDS))
def test_every_latency_field_is_cross_checked(
    small_reference_payload: dict, field: str
) -> None:
    """F-1 covers all four float latency fields, not just the headline total."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"][field] += 10_000.0
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert field in str(excinfo.value)


def test_latency_field_list_matches_compute_summary_output(
    small_reference_payload: dict,
) -> None:
    """Guard: ``LATENCY_COST_FIELDS`` must be exactly the float cost fields
    ``_compute_summary`` emits, and must not overlap the integer list."""
    cost = small_reference_payload["summary"]["cost"]
    floats = {
        key
        for key, value in cost.items()
        if isinstance(value, float) and not isinstance(value, bool)
    }
    assert set(s9.LATENCY_COST_FIELDS) == floats
    assert not set(s9.LATENCY_COST_FIELDS) & set(s9.SUMMABLE_COST_FIELDS)


def test_missing_shard_latency_field_is_rejected(
    small_reference_payload: dict,
) -> None:
    """F-1: the schema types ``summary.cost`` as a bare object, so a shard may
    legally omit a latency field. The merge refuses it rather than skipping
    the check -- skipping would reopen the hole F-1 closes."""
    shards = make_shards(small_reference_payload, 3)
    del shards[1]["summary"]["cost"]["total_judge_latency_sec"]
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    message = str(excinfo.value)
    assert "total_judge_latency_sec" in message
    assert "<missing>" in message


def test_non_numeric_shard_latency_is_rejected(
    small_reference_payload: dict,
) -> None:
    """F-1: a string in a latency field is refused, not coerced."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["summary"]["cost"]["total_judge_latency_sec"] = "11206.15"
    with pytest.raises(s9.ShardMergeError) as excinfo:
        merge(shards)
    assert "must be a number" in str(excinfo.value)


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def _write_shards(tmp_path: Path, shards: list[dict]) -> list[Path]:
    paths = []
    for index, shard in enumerate(shards):
        path = tmp_path / f"shard_{index}.json"
        path.write_text(json.dumps(shard), encoding="utf-8")
        paths.append(path)
    return paths


def test_cli_round_trip_writes_a_valid_final_payload(
    small_reference_payload: dict, grade_schema: dict, tmp_path: Path
) -> None:
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 3))
    out = tmp_path / "merged.json"
    code = s9.main([*[str(p) for p in paths], "--output", str(out)])
    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    validate_grade_payload(written, grade_schema)
    assert written["run_status"] == "final"
    assert len(written["tasks"]) == SMALL_TASK_COUNT
    assert (
        written["summary"]["openai_compat"]["avg_score_pct"]
        == small_reference_payload["summary"]["openai_compat"]["avg_score_pct"]
    )


def test_cli_records_file_digests_in_provenance(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    import hashlib

    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 2))
    out = tmp_path / "merged.json"
    assert s9.main([*[str(p) for p in paths], "--output", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    expected = {
        hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    assert {
        entry["grade_file_sha256"] for entry in written["shard_provenance"]
    } == expected


def test_cli_refuses_to_overwrite_without_force(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 2))
    out = tmp_path / "merged.json"
    out.write_text("{}", encoding="utf-8")
    code = s9.main([*[str(p) for p in paths], "--output", str(out)])
    assert code == 1
    assert out.read_text(encoding="utf-8") == "{}"


def test_cli_overwrites_with_force(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 2))
    out = tmp_path / "merged.json"
    out.write_text("{}", encoding="utf-8")
    code = s9.main([*[str(p) for p in paths], "--output", str(out), "--force"])
    assert code == 0
    assert json.loads(out.read_text(encoding="utf-8"))["run_status"] == "final"


def test_cli_rejects_repeated_shard_paths(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 2))
    out = tmp_path / "merged.json"
    code = s9.main(
        [str(paths[0]), str(paths[0]), str(paths[1]), "--output", str(out)]
    )
    assert code == 1
    assert not out.exists()


def test_cli_returns_nonzero_and_writes_nothing_on_merge_failure(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    """§E-6: a failed merge must not leave a partial artifact behind."""
    shards = make_shards(small_reference_payload, 3)
    shards[1]["judge"]["config_hash"] = "deadbeefdeadbeef"
    paths = _write_shards(tmp_path, shards)
    out = tmp_path / "merged.json"
    code = s9.main([*[str(p) for p in paths], "--output", str(out)])
    assert code == 1
    assert not out.exists()


def test_cli_rejects_an_incomplete_shard_set(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    shards = make_shards(small_reference_payload, 3)
    paths = _write_shards(tmp_path, shards[:2])
    out = tmp_path / "merged.json"
    assert s9.main([*[str(p) for p in paths], "--output", str(out)]) == 1
    assert not out.exists()


def test_load_shard_file_returns_payload_and_file_digest(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    import hashlib

    shard = make_shards(small_reference_payload, 2)[0]
    path = tmp_path / "one.json"
    path.write_text(json.dumps(shard), encoding="utf-8")
    payload, digest = s9.load_shard_file(path)
    assert payload["run_status"] == "partial"
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


def test_load_shard_file_reports_unparseable_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(s9.ShardMergeError) as excinfo:
        s9.load_shard_file(path)
    assert "could not parse" in str(excinfo.value)


def test_parse_args_requires_output() -> None:
    with pytest.raises(SystemExit):
        s9.parse_args(["shard0.json"])


def test_parse_args_accepts_the_documented_flags() -> None:
    args = s9.parse_args(
        ["a.json", "b.json", "--output", "out.json", "--strict-routes", "--force"]
    )
    assert args.shards == ["a.json", "b.json"]
    assert args.output == "out.json"
    assert args.strict_routes is True
    assert args.force is True
    assert args.defer_if_incomplete is False


def test_parse_args_accepts_defer_if_incomplete() -> None:
    args = s9.parse_args(
        ["a.json", "--output", "out.json", "--defer-if-incomplete"]
    )
    assert args.defer_if_incomplete is True


# ---------------------------------------------------------------------------
# concurrent mergers: an incomplete union is routine, not a fault
#
# Under ``resume`` a shard republishes its slice after every chunk, so all N
# shard files exist long before all N slices are complete. Every shard that
# finishes a chunk then pulls, sees N files, and arrives at the merge. All but
# the last legitimately observe a short union. Failing them turns a healthy
# run red and hides a real stall among the noise.
# ---------------------------------------------------------------------------


def test_defer_exit_code_is_distinguishable_from_success_and_failure() -> None:
    """The caller must be able to tell "stand down" from "this is broken"."""
    assert s9.DEFER_EXIT_CODE not in {0, 1}


def test_incomplete_is_a_shard_merge_error(small_reference_payload: dict) -> None:
    """Callers catching the parent must keep catching the short union."""
    assert issubclass(s9.ShardMergeIncomplete, s9.ShardMergeError)
    with pytest.raises(s9.ShardMergeError):
        merge(make_shards(small_reference_payload, 3)[:2])


def test_incomplete_carries_the_counts_the_caller_reports(
    small_reference_payload: dict,
) -> None:
    shards = make_shards(small_reference_payload, 3)
    with pytest.raises(s9.ShardMergeIncomplete) as excinfo:
        merge(shards[:2])
    assert excinfo.value.expected_count == SMALL_TASK_COUNT
    assert excinfo.value.union_size == sum(
        len(shard["tasks"]) for shard in shards[:2]
    )


def test_cli_defers_on_an_incomplete_union(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    """The case that painted three healthy shards red on the sol-220 run."""
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 3)[:2])
    out = tmp_path / "merged.json"

    code = s9.main(
        [*[str(p) for p in paths], "--output", str(out), "--defer-if-incomplete"]
    )

    assert code == s9.DEFER_EXIT_CODE
    assert not out.exists()


def test_cli_still_fails_on_an_incomplete_union_by_default(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    """§E-6 stands: without an explicit opt-in a short union is an error."""
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 3)[:2])
    out = tmp_path / "merged.json"

    assert s9.main([*[str(p) for p in paths], "--output", str(out)]) == 1
    assert not out.exists()


def test_deferral_does_not_soften_a_complete_but_unmergeable_union(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    """The corpus is all there, so nobody is coming to merge it later.

    A contract-identity violation here means the shards disagree about what
    run they belong to. Deferring would leave that unreported forever.
    """
    shards = make_shards(small_reference_payload, 3)
    shards[1]["grader_source_hash"] = "src_0000000000000000"
    paths = _write_shards(tmp_path, shards)
    out = tmp_path / "merged.json"

    code = s9.main(
        [*[str(p) for p in paths], "--output", str(out), "--defer-if-incomplete"]
    )

    assert code == 1
    assert not out.exists()


def test_deferral_does_not_suppress_a_duplicated_task(
    small_reference_payload: dict, tmp_path: Path
) -> None:
    """Overlapping slices are a slicing bug, and the union check runs after."""
    shards = make_shards(small_reference_payload, 3)
    shards[0]["tasks"].append(copy.deepcopy(shards[1]["tasks"][0]))
    shards[0]["summary"] = _compute_summary(
        shards[0]["tasks"], unpriced_models=UNPRICED_MODELS
    )
    paths = _write_shards(tmp_path, shards)
    out = tmp_path / "merged.json"

    code = s9.main(
        [*[str(p) for p in paths], "--output", str(out), "--defer-if-incomplete"]
    )

    assert code == 1


def test_the_last_merger_still_publishes_with_the_flag_set(
    small_reference_payload: dict, grade_schema: dict, tmp_path: Path
) -> None:
    """Deferral must not become a way for a run to never publish at all."""
    paths = _write_shards(tmp_path, make_shards(small_reference_payload, 3))
    out = tmp_path / "merged.json"

    code = s9.main(
        [*[str(p) for p in paths], "--output", str(out), "--defer-if-incomplete"]
    )

    assert code == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    validate_grade_payload(written, grade_schema)
    assert written["run_status"] == "final"
    assert len(written["tasks"]) == SMALL_TASK_COUNT


def test_deferral_reports_progress_rather_than_an_error(
    small_reference_payload: dict, tmp_path: Path, capsys
) -> None:
    """An operator reading the log should see how far along the run is."""
    shards = make_shards(small_reference_payload, 3)
    paths = _write_shards(tmp_path, shards[:2])
    graded = sum(len(shard["tasks"]) for shard in shards[:2])

    s9.main(
        [*[str(p) for p in paths], "--output", str(tmp_path / "m.json"),
         "--defer-if-incomplete"]
    )

    message = capsys.readouterr().err
    assert "ERROR" not in message
    assert f"{graded} of {SMALL_TASK_COUNT}" in message
