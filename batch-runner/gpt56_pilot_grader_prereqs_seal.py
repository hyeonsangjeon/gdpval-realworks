"""Reviewed exp038 prerequisite successor; no spending or launch authority.

The predecessor records/readers and the verification algorithm are unchanged.
Only the reviewed source, hashes and exact change-set data advance.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

import gpt56_pilot_grader_reseal as sealed
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes


ENVELOPE = sealed.ENVELOPE
RECORD = ENVELOPE + "gpt56_sol_grader_seal_20261113_exp038_prereqs.json"
RECORD_SHA256 = "dd65cccca34a96abc437ddd45a9ce2083f6c52cc71bfb97fdcb2f18ff6729d5b"
PREVIOUS_RECORD = sealed.RECORD
PREVIOUS_RECORD_SHA256 = sealed.RECORD_SHA256
PREVIOUS_SOURCE = sealed.REVIEWED_BASE
PREVIOUS_HASH = sealed.GRADER_HASH
REVIEWED_BASE = "f423114e0122d75ed07a9d57a3dac5cee64c08fd"
GRADER_HASH = "54eccf8de3d2f0bcb96de6fb4f9dc527520ca3d72b39090a410ff71d0b45f7c0"
TEMPLATE = sealed.TEMPLATE
#: The exact reviewed delta; the closure enumeration and verifier are unchanged.
CHANGED_FILES = frozenset({
    "batch-runner/core/grader.py",
    "batch-runner/core/grading_retry.py",
    "batch-runner/core/perception/audio.py",
    "batch-runner/core/perception/vision.py",
    "batch-runner/core/tool_calling_judge.py",
    "batch-runner/requirements-renderer.txt",
    "batch-runner/step8_grade.py",
})

GraderSealRefused = sealed.GraderSealRefused
source_files = sealed.source_files


def verify(root: Path) -> tuple[dict, dict[str, str]]:
    """Verify the chained record and every closure byte; a new/removed file refuses."""
    try:
        record_data = _read_bytes(_path(root, RECORD), sha256=RECORD_SHA256)
        previous_data = _read_bytes(_path(root, PREVIOUS_RECORD), sha256=PREVIOUS_RECORD_SHA256)
        record = json.loads(record_data, object_pairs_hook=_object)
        previous = json.loads(previous_data, object_pairs_hook=_object)
        if (record["schema_version"] != "gpt56-grader-successor-seal-v1"
                or record["predecessor_seal"] != {"path": PREVIOUS_RECORD, "sha256": PREVIOUS_RECORD_SHA256}
                or record["previous"]["source_sha"] != PREVIOUS_SOURCE
                or record["previous"]["grader_source_hash"] != PREVIOUS_HASH
                or previous["grader_source_hash"] != PREVIOUS_HASH
                or record["previous"]["files"] != previous["files"]
                or record["preserved_conditions"] != previous["preserved_conditions"]
                or record["reviewed_source_sha"] != REVIEWED_BASE
                or record["grader_source_hash"] != GRADER_HASH
                or record["template"] != TEMPLATE
                or record["launch_authority"] is not False):
            raise ValueError()
        before, after = record["previous"]["files"], record["files"]
        changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
        if changed != set(record["changes"]) or changed != CHANGED_FILES:
            raise ValueError()
        for name, delta in record["changes"].items():
            if delta["before"] != before.get(name) or delta["after"] != after.get(name):
                raise ValueError()
        sources = source_files(root)
        if set(sources) != set(after):
            raise ValueError()
        held_roles = tuple(sorted({*sources, RECORD, PREVIOUS_RECORD}))
        with _held_parents(root, held_roles) as check:
            held = {name: _read_bytes(path, sha256=after[name]) for name, path in sources.items()}
            import step8_grade as step8
            config = yaml.safe_load(held[TEMPLATE])
            actual = step8.compute_grader_source_hash(sources[TEMPLATE], config,
                                                     batch_root=root / "batch-runner")
            if actual != GRADER_HASH:
                raise ValueError()
            for name, data in held.items():
                if _read_bytes(sources[name], sha256=after[name], size=len(data)) != data:
                    raise ValueError()
            if (_read_bytes(_path(root, RECORD), sha256=RECORD_SHA256) != record_data
                    or _read_bytes(_path(root, PREVIOUS_RECORD), sha256=PREVIOUS_RECORD_SHA256) != previous_data):
                raise ValueError()
            if set(source_files(root)) != set(after):
                raise ValueError()
            check()
        return {
            "status": "reviewed_successor_seal_verified",
            "record": RECORD, "record_sha256": RECORD_SHA256,
            "predecessor_record": PREVIOUS_RECORD, "predecessor_record_sha256": PREVIOUS_RECORD_SHA256,
            "previous_source_sha": PREVIOUS_SOURCE, "previous_grader_source_hash": PREVIOUS_HASH,
            "reviewed_source_sha": REVIEWED_BASE, "grader_source_hash": actual,
            "changed_files": sorted(changed),
            "equivalence_boundary": "selector_replay_and_unit_fixtures_not_real_task_scores",
            "launch_authority": False,
        }, {**after, RECORD: RECORD_SHA256, PREVIOUS_RECORD: PREVIOUS_RECORD_SHA256}
    except Exception:
        raise GraderSealRefused("grader_successor_seal_refused") from None
