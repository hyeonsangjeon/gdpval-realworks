#!/usr/bin/env python3
"""Freeze what Stage 3 actually bought, so the 174 can never be mistaken for 185.

Stage 3 pinned 185 gold tasks across 11 stride shards. Ten shards finished
their slice. Shard 4 stopped after 6 of 17 because one task -- ``9e39df84``,
57 rubric items -- cannot be graded inside a single GitHub-hosted chunk at any
budget the 360 min runner kill allows (four attempts; see
``tests/test_a_task_longer_than_a_chunk_can_never_be_graded.py``).

That leaves 174 graded tasks on disk and no merged final payload, which is an
awkward state to leave lying around: the shard files look like results, the
scores look quotable, and nothing in a directory listing says eleven tasks are
missing or which eleven. This module writes that down as data rather than
prose -- one JSON document naming every run, digest and task id, and
re-deriving the coverage gap from the pinned config instead of quoting it.

What it does NOT do
-------------------
It does not merge, does not relax ``expected_task_count``, and does not write
anything into ``data/grades``. The refusal in ``step9_merge_shards`` is the
protection here; this is a record of the state that refusal preserves.

Offline: reads committed JSON and JSONL, computes SHA-256, writes one file.
No network, no model call. The GitHub run and artifact facts are external, so
they are pinned as literals in :data:`SHARD4_ATTEMPTS` and cross-checkable
with ``gh api repos/<repo>/actions/runs/<id>/artifacts``.

    python scripts/stage3_partial_inventory.py \
        -o ../tasks/rebuilding_grading_task/stage3_partial_inventory.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BATCH_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BATCH_ROOT.parent

# So ``python scripts/stage3_partial_inventory.py`` works from batch-runner as
# the report documents it, not only under pytest, whose rootdir is already here.
if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

CONFIG_PATH = BATCH_ROOT / "grading_configs/gold_ceiling_185_v2_sol_max.yaml"

#: The output directory is named after the ordered-task-ids digest, so the
#: corpus identity is in the path rather than only in the payloads.
#:
#: Every hash spelled out below is a *historical* one: this is where the 174
#: already-graded shards sit on disk, and that path can never change again.
#: Two of its fields have since moved in the working tree — ``cfg_`` because
#: the audio call cap went from 3 to 32, and ``src_`` because the listening
#: call was repaired — so recomputing either from the current files would
#: point this script at a directory that does not exist. Anyone tempted to
#: replace these literals with a call to ``hash_config`` or
#: ``compute_grader_source_hash`` is looking at the one place in this
#: repository where a stale hash is the correct hash.
CORPUS_DIGEST = "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
SHARD_DIR = (
    REPO_ROOT
    / "data/grades/_diagnostic"
    / CORPUS_DIGEST
    / "_shards"
    / (
        "exp_gold_baseline__judge_gpt-5_6-sol__gold_ceiling_185_v2_sol_max"
        "__cfg_b3609ec13f8fa51e"
        "__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf"
        "__inference_11e7900cdcac61bc4daf59e65feb238acda98fbf"
        "__src_955be41edc4aff19__v2.2"
    )
)

#: The grader fingerprint this measurement belongs to. Shards under the same
#: corpus digest carrying any other value were graded by different code and
#: are not comparable at the item level; see :func:`_superseded_shard_dirs`.
PINNED_SOURCE_HASH = (
    "955be41edc4aff191952123e37538266aa28508786aa82693055269538d8b67a"
)

MANIFEST_PATH = (
    BATCH_ROOT / "experiments/gold_corpus/gold_deliverable_manifest.json"
)

SHARD_COUNT = 11
EXPECTED_TASK_COUNT = 185
STALLED_TASK_ID = "9e39df84-ac57-4c9b-a2e3-12b8abf2c797"
STALLED_TASK_SHARD_INDEX = 4

#: The five input limits published in ``304-full-gold-corpus.md`` *before* the
#: paid run, on the rule that a limit predicted in advance is worth more as
#: evidence than one found afterwards. All five were expected to pull the
#: ceiling down, so which of them landed in the graded set decides the
#: direction of the bias in any average taken over less than 185.
KNOWN_INPUT_LIMITS: dict[str, str] = {
    # Kept as published, with what has since been learned appended rather than
    # substituted. Both audio entries were pre-registered as *input* limits --
    # properties of the deliverable the grader could not help -- and both turned
    # out to be grader defects instead. The cap has been raised to 32 and the
    # listening call now goes to the endpoint that accepts audio, so neither
    # should reappear in a run made after that fix; a pre-registration is
    # evidence about what was expected, so it is annotated, not rewritten.
    "38889c3b": (
        "10 listening criteria vs AUDIO_CALL_CAP=3 (gold is one .zip); "
        "cap since raised to 32"
    ),
    "a73fbc98": "102 render targets vs a cap of 72",
    "e222075d": "required_visual_render_target_unavailable",
    "75401f7c": "required_visual_render_target_unavailable",
    "7de33b48": "required_visual_render_target_unavailable",
}

#: Every paid attempt on shard 4, innermost facts first. ``items_done`` and
#: ``stopped_starting`` come from the time-guard line in each run's grading
#: log; the artifact digests come from the Actions API and are what makes
#: "the ledger survived" checkable rather than asserted.
SHARD4_ATTEMPTS: tuple[dict[str, Any], ...] = (
    {
        "attempt": 1,
        "run_id": 33273207562,
        "head_sha": "81923238",
        "budget_minutes": 240,
        "grading_minutes": 261.3,
        "items_done": 45,
        "stopped_starting_item": 46,
        "exit_code": 5,
        "grade_artifact": {
            "id": 9723977397,
            "bytes": 45713,
            "sha256": "3c8f6d6d708d15b8155f7acab7fcc393d5f99eb03d446e5c0c2b48c9dcce065a",
        },
        "cost_ledger_artifact": {
            "id": 9723977244,
            "bytes": 1251769,
            "sha256": "d1604262fe017aedbb9c22aa3fb2021938c0a1b7bd569c881bd4b99d4ec8175b",
        },
    },
    {
        "attempt": 2,
        "run_id": 33286656393,
        "head_sha": "58746336",
        "budget_minutes": 300,
        "grading_minutes": 310.4,
        "items_done": 54,
        "stopped_starting_item": 55,
        "exit_code": 5,
        "grade_artifact": {
            "id": 9728162524,
            "bytes": 45713,
            "sha256": "ece78e0d1575af74b69a9cc99cf8ef84f1d67cb9187dbfd4cb408606f76e0579",
        },
        "cost_ledger_artifact": {
            "id": 9728162271,
            "bytes": 1293205,
            "sha256": "bf3feb918380ec0cde49d7236b7a5b3585a30367d69addfc5421811f016e75d3",
        },
    },
    {
        "attempt": 3,
        "run_id": 33301041542,
        "head_sha": "e0009577",
        "budget_minutes": 336,
        "grading_minutes": 348.0,
        "items_done": 54,
        "stopped_starting_item": 55,
        "exit_code": 5,
        "grade_artifact": {
            "id": 9733433886,
            "bytes": 45713,
            "sha256": "325216149defc336579e3c29d9c0d23bf70a69e9b0ac94902da897059faf2fe2",
        },
        "cost_ledger_artifact": {
            "id": 9733433692,
            "bytes": 1292266,
            "sha256": "2468cc88d620e984d20c8c93549e6db146a7c398f75b950eaadcd50d6c4490f1",
        },
    },
    {
        "attempt": 4,
        "run_id": 33316285562,
        "head_sha": "8c968526",
        "budget_minutes": 338,
        "grading_minutes": 346.0,
        "items_done": 55,
        "stopped_starting_item": 56,
        "exit_code": 5,
        "grade_artifact": {
            "id": 9738079160,
            "bytes": 45713,
            "sha256": "196f0c99d5a05a9fbc66c4093c31264a3fa8cef393656153d1f0bbb40d75b14b",
        },
        "cost_ledger_artifact": {
            "id": 9738078986,
            "bytes": 1294161,
            "sha256": "1230417baab109f2f6fdc8cc7a7158188c15332a39ed829f326e725a1620d26a",
        },
    },
)

#: Identity fields every shard must agree on. A shard that disagrees on any of
#: these is not part of this measurement, whatever its filename says.
IDENTITY_FIELDS = (
    "experiment_id",
    "schema_version",
    "expected_task_count",
    "expected_ordered_task_ids_sha256",
    "grader_source_hash",
    "source_inference_revision",
    "source_inference_repo_id",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _pinned_task_ids() -> list[str]:
    import yaml

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return list(config["rerun_identity"]["task_ids"])


def _stride(task_ids: list[str], index: int) -> list[str]:
    """The slice shard ``index`` owns, re-derived rather than quoted.

    ``step8_grade._shard_slice`` cuts by stride so a shard is not a run of
    adjacent rows sharing an occupation. The same arithmetic here is what
    makes "shard 4 owns 17 and delivered 6" a derivation instead of a claim.
    """
    return task_ids[index::SHARD_COUNT]


def _superseded_shard_dirs() -> list[dict[str, Any]]:
    """Sibling shard directories graded by a *different* grader fingerprint.

    An earlier pass over this same corpus ran before the cost-receipt work
    landed, which touched ``core/`` and so moved the grader source hash. Its
    shards were committed and are still on disk, under the same corpus digest,
    one directory across. They are not deleted -- they are paid evidence of
    what the grader did before the change -- but they are not part of this
    measurement, and a glob over ``_shards/*/shard-*.json`` would sweep them
    in. Naming them here is what stops that being discovered by accident.

    ``step9_merge_shards`` already refuses the mix: ``grader_source_hash`` is a
    contract identity field, so a cross-hash merge fails outright rather than
    producing a blended payload.
    """
    parent = SHARD_DIR.parent
    found: list[dict[str, Any]] = []
    for candidate in sorted(parent.iterdir()):
        if not candidate.is_dir() or candidate == SHARD_DIR:
            continue
        payloads = sorted(candidate.glob("shard-*.json"))
        hashes = {
            json.loads(path.read_text(encoding="utf-8")).get(
                "grader_source_hash"
            )
            for path in payloads
        }
        found.append(
            {
                "dir": str(candidate.relative_to(REPO_ROOT)),
                "grader_source_hash": sorted(h for h in hashes if h),
                "shard_files": len(payloads),
                "cost_ledgers": len(
                    list(candidate.glob("shard-*.cost_ledger.jsonl"))
                ),
                "in_scope": False,
                "why": (
                    "graded at a superseded grader source hash; not "
                    "comparable at item level and refused by "
                    "step9_merge_shards as a contract identity mismatch"
                ),
            }
        )
    return found


def _score_facts(manifest_tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """What the 174 actually say, with the caveats attached to the numbers.

    Two means are reported rather than one. A task whose judge errored has no
    score, and the choice between dropping it and counting it as zero moves
    the headline by 0.46pp -- small, but it is the difference between two
    defensible figures, so both are written down instead of one being picked.
    """
    pcts: list[float] = []
    errors: list[dict[str, str]] = []
    critical_fail = 0
    awarded = 0.0
    maximum = 0.0
    items = 0
    perception_calls = 0
    usage_incomplete: list[str] = []
    sectors: set[str] = set()
    occupations: set[str] = set()

    for index in range(SHARD_COUNT):
        path = SHARD_DIR / f"shard-{index:03d}-of-{SHARD_COUNT:03d}.json"
        if not path.exists():
            continue
        for task in json.loads(path.read_text(encoding="utf-8"))["tasks"]:
            if task.get("error"):
                errors.append(
                    {"task_id": task["task_id"], "error": task["error"]}
                )
                continue
            pcts.append(task["pct"])
            critical_fail += 1 if task.get("critical_fail") else 0
            awarded += task["total_awarded"]
            maximum += task["total_max"]
            items += len(task.get("items", []))
            perception_calls += task.get("perception_call_count", 0)
            if not task.get("usage_complete", True):
                usage_incomplete.append(task["task_id"])
            sectors.add(task["sector"])
            occupations.add(task["occupation"])

    graded_entries = len(pcts) + len(errors)
    gold = [task for task in manifest_tasks.values() if task["files"]]

    return {
        "graded_entries": graded_entries,
        "scored_tasks": len(pcts),
        "judge_errors": errors,
        "mean_pct_over_scored": round(sum(pcts) / len(pcts), 2),
        "mean_pct_counting_errors_as_zero": round(
            sum(pcts) / graded_entries, 2
        ),
        "median_pct": round(sorted(pcts)[len(pcts) // 2], 2),
        "min_pct": round(min(pcts), 2),
        "max_pct": round(max(pcts), 2),
        "points_awarded": round(awarded, 1),
        "points_available": round(maximum, 1),
        "rubric_items_scored": items,
        "critical_fail_tasks": critical_fail,
        "critical_fail_means": (
            "at least one item of |max_score| >= 4 where the model did not do "
            "the right thing -- not a count of severe failures"
        ),
        "judge_error_rate_pct": round(100 * len(errors) / graded_entries, 2),
        "perception_calls": perception_calls,
        "usage_incomplete_tasks": usage_incomplete,
        "breadth": {
            "sectors_graded": len(sectors),
            "sectors_in_corpus": len({task["sector"] for task in gold}),
            "occupations_graded": len(occupations),
            "occupations_in_corpus": len(
                {task["occupation"] for task in gold}
            ),
        },
    }


#: Container extensions that hold a video stream. Disjoint from the grader's
#: audio extensions, which is the whole of the defect below.
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")


def _items_scored_without_listening() -> list[dict[str, Any]]:
    """Items about sound that a judge answered without hearing anything.

    ``has_audio_content`` returned ``False`` for every video container, and
    ``False`` is a positive claim that the file was examined and holds no
    audio, so ``resolve_runtime_routing`` demoted the criterion to TEXT. A
    demoted item is still scored -- demotion is not exclusion -- so "we did
    not listen" was recorded as "the work is bad".

    The signature is taken from the payloads: a video in ``selected_paths``,
    ``routing_modality`` of ``text``, and a criterion the router itself still
    classifies as AUDIO. That last clause is a live call rather than a frozen
    keyword list, deliberately: if the classifier changes, this count changes
    with it and the rebuild-and-diff test says so, which is the behaviour
    wanted from a record that is supposed to track the code.

    Fixed by PR #276 -- which moves the grader fingerprint, so these two tasks
    stay wrong in this measurement and can only be corrected by a re-run.
    """
    from core.grader_routing import Modality, classify_criterion

    affected: list[dict[str, Any]] = []
    for index in range(SHARD_COUNT):
        path = SHARD_DIR / f"shard-{index:03d}-of-{SHARD_COUNT:03d}.json"
        if not path.exists():
            continue
        for task in json.loads(path.read_text(encoding="utf-8"))["tasks"]:
            demoted = [
                item
                for item in task.get("items", [])
                if any(
                    str(p).lower().endswith(VIDEO_EXTENSIONS)
                    for p in (item.get("selected_paths") or [])
                )
                and item.get("routing_modality") == "text"
                and classify_criterion(item["criterion"]).modality
                is Modality.AUDIO
            ]
            if not demoted:
                continue
            affected.append(
                {
                    "task_id": task["task_id"],
                    "shard_index": index,
                    "occupation": task.get("occupation"),
                    "pct_as_recorded": task.get("pct"),
                    "items_demoted": len(demoted),
                    "points_not_awarded": round(
                        sum(
                            (item.get("max_score") or 0)
                            - (item.get("awarded_score") or 0)
                            for item in demoted
                        ),
                        2,
                    ),
                    "total_max": task.get("total_max"),
                    "rubric_item_ids": [
                        item["rubric_item_id"] for item in demoted
                    ],
                }
            )
    return sorted(affected, key=lambda entry: entry["task_id"])


def _collect_shards(task_ids: list[str]) -> list[dict[str, Any]]:
    shards: list[dict[str, Any]] = []
    for index in range(SHARD_COUNT):
        stem = f"shard-{index:03d}-of-{SHARD_COUNT:03d}"
        grade_path = SHARD_DIR / f"{stem}.json"
        ledger_path = SHARD_DIR / f"{stem}.cost_ledger.jsonl"
        owned = _stride(task_ids, index)

        if not grade_path.exists():
            shards.append(
                {
                    "shard_index": index,
                    "state": "ABSENT",
                    "owned_tasks": len(owned),
                    "present_tasks": 0,
                    "missing_task_ids": owned,
                }
            )
            continue

        payload = json.loads(grade_path.read_text(encoding="utf-8"))
        present = [task["task_id"] for task in payload["tasks"]]
        missing = [task_id for task_id in owned if task_id not in set(present)]
        errored = [
            task["task_id"] for task in payload["tasks"] if task.get("error")
        ]

        ledger_rows = 0
        ledger_run_ids: set[str] = set()
        if ledger_path.exists():
            with ledger_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    ledger_rows += 1
                    ledger_run_ids.add(json.loads(line).get("run_id"))

        declared = (payload.get("cost_ledger") or {}).get("sha256")
        actual = _sha256_file(ledger_path) if ledger_path.exists() else None

        shards.append(
            {
                "shard_index": index,
                "state": "COMPLETE" if not missing else "SHORT",
                "owned_tasks": len(owned),
                "present_tasks": len(present),
                "graded_tasks": payload["summary"]["graded_tasks"],
                "error_tasks": payload["summary"]["error_tasks"],
                "error_task_ids": errored,
                "missing_task_ids": missing,
                "run_status": payload.get("run_status"),
                "identity": {
                    field: payload.get(field) for field in IDENTITY_FIELDS
                },
                "grade_file": {
                    "path": str(grade_path.relative_to(REPO_ROOT)),
                    "bytes": grade_path.stat().st_size,
                    "sha256": _sha256_file(grade_path),
                    "committed_in": _git(
                        "log", "--format=%H", "-1", "--", str(grade_path)
                    ),
                },
                "cost_ledger": {
                    "path": str(ledger_path.relative_to(REPO_ROOT)),
                    "rows": ledger_rows,
                    "declared_sha256": declared,
                    "actual_sha256": actual,
                    "sha256_agrees": declared == actual,
                    "ledger_run_ids": sorted(
                        rid for rid in ledger_run_ids if rid
                    ),
                },
            }
        )
    return shards


def build_inventory() -> dict[str, Any]:
    task_ids = _pinned_task_ids()
    if len(task_ids) != EXPECTED_TASK_COUNT:
        raise SystemExit(
            f"pinned config carries {len(task_ids)} task ids, "
            f"expected {EXPECTED_TASK_COUNT}"
        )

    shards = _collect_shards(task_ids)
    graded_ids = {
        task_id
        for shard in shards
        for task_id in _stride(task_ids, shard["shard_index"])
        if task_id not in set(shard.get("missing_task_ids", []))
    }
    missing_ids = [task_id for task_id in task_ids if task_id not in graded_ids]

    run_ids = sorted(
        {
            rid
            for shard in shards
            for rid in shard.get("cost_ledger", {}).get("ledger_run_ids", [])
        }
    )

    identities = {
        field: sorted(
            {
                json.dumps(shard["identity"][field], sort_keys=True)
                for shard in shards
                if "identity" in shard
            }
        )
        for field in IDENTITY_FIELDS
    }

    stalled_shard = _stride(task_ids, STALLED_TASK_SHARD_INDEX)
    stalled_position = stalled_shard.index(STALLED_TASK_ID)

    manifest = {
        task["task_id"]: task
        for task in json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))[
            "tasks"
        ]
    }
    missing = [
        {
            "task_id": task_id,
            "sector": manifest[task_id]["sector"],
            "occupation": manifest[task_id]["occupation"],
            "known_input_limit": KNOWN_INPUT_LIMITS.get(task_id[:8]),
            "cause": (
                "the task the chunk cannot finish"
                if task_id == STALLED_TASK_ID
                else "queued behind the stalled task; never started"
            ),
        }
        for task_id in missing_ids
    ]
    facts = _score_facts(manifest)

    return {
        "document": "stage3-partial-inventory",
        "status": "BLOCKED_PARTIAL",
        "not_a_final_result": (
            "174 of 185 tasks are graded. No merged final payload exists and "
            "none may be produced: step9_merge_shards refuses a short union "
            "and --force does not override it. Any average quoted from this "
            "inventory describes 174 tasks, not the gold corpus."
        ),
        "corpus": {
            "config": str(CONFIG_PATH.relative_to(REPO_ROOT)),
            "expected_task_count": EXPECTED_TASK_COUNT,
            "ordered_task_ids_sha256": CORPUS_DIGEST,
            "shard_count": SHARD_COUNT,
            "shard_dir": str(SHARD_DIR.relative_to(REPO_ROOT)),
            "grader_source_hash": PINNED_SOURCE_HASH,
        },
        "identity_agreement": {
            "fields": identities,
            "all_shards_agree": all(
                len(values) == 1 for values in identities.values()
            ),
            "ledger_run_ids": run_ids,
            "single_run_ordinal": len(run_ids) == 1,
        },
        "coverage": {
            "graded": len(graded_ids),
            "expected": EXPECTED_TASK_COUNT,
            "missing": len(missing_ids),
            "missing_task_ids": missing_ids,
            "missing_tasks": missing,
            "duplicate_task_ids": [],
        },
        "shards": shards,
        "superseded_sibling_dirs": _superseded_shard_dirs(),
        "blocking_task": {
            "task_id": STALLED_TASK_ID,
            "shard_index": STALLED_TASK_SHARD_INDEX,
            "position_in_shard": stalled_position + 1,
            "shard_size": len(stalled_shard),
            "stranded_behind_it": len(stalled_shard) - stalled_position - 1,
            "attempts": list(SHARD4_ATTEMPTS),
        },
        "what_the_174_say": facts,
        "known_grading_defects": {
            "audio_criteria_scored_without_listening": {
                "tasks": _items_scored_without_listening(),
                "fixed_by": "PR #276",
                "correctable_here": False,
                "note": (
                    "A video container was read as proof of silence, so "
                    "criteria about sound were demoted to TEXT and answered "
                    "by a judge that could not hear. Demotion is not "
                    "exclusion: these items were scored, not withheld, so "
                    "the affected tasks read lower than they were measured "
                    "to be. The fix touches core/ and moves the grader "
                    "fingerprint, which is why it cannot be applied to this "
                    "measurement -- only a re-run corrects it."
                ),
            }
        },
        "interpretation_limits": [
            "The 11 missing tasks are not a random sample. They are one "
            "stalled task plus the ten queued behind it in a single stride "
            "shard, so the gap is structural rather than statistical.",
            "a73fbc98 is one of the five input limits published before the "
            "run as expected to pull the ceiling down, and it is among the "
            "missing. Any mean over the 174 is therefore biased upward "
            "relative to the 185 it stands in for.",
            "One task carries a judge error (all_items_score_excluded) and "
            "has no score, so 174 entries yield 173 scores. Both means are "
            "reported; neither is the corpus figure.",
            "No sector and no occupation is lost entirely -- the 174 still "
            "span 9 of 9 and 44 of 44. That bounds the damage; it does not "
            "make the set complete, since eleven occupations each lost a "
            "task.",
            "known_usd is null because gpt-5.6-sol has no published price. "
            "Absent price is not zero cost.",
            "Two of the 174 were graded with a known defect: criteria about "
            "sound on a video deliverable were routed to a judge that could "
            "not hear, and scored rather than excluded. Their recorded "
            "percentages are floors, not measurements. See "
            "known_grading_defects.",
        ],
        "cost": {
            "settlement": "partial",
            "known_usd": None,
            "reason": (
                "gpt-5.6-sol has no published price; every judge call is "
                "recorded with usage but no USD. Absent price is not zero "
                "cost -- do not render this as $0."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", type=Path, required=True)
    args = parser.parse_args(argv)

    inventory = build_inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    coverage = inventory["coverage"]
    print(
        f"{inventory['status']}: {coverage['graded']}/{coverage['expected']} "
        f"graded, {coverage['missing']} missing -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
