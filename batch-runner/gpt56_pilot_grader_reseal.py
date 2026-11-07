"""The selector-fix successor of the #794 grader seal; never a waiver of it.

Owner decision 1 (2026-11-06) approved fixing the deliverable selector and
resealing. It does not change the experiment, tariff, USD ceilings, unknown
usage handling or launch rights. No credential or provider is used.

The 20261030 record and its reader stay byte-identical. This reader holds that
record by SHA-256, requires the new record's ``previous`` closure to be exactly
the one 20261030 sealed, and admits exactly the reviewed delta below.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

import gpt56_pilot_grader_seal as sealed
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes


ENVELOPE = sealed.ENVELOPE
RECORD = ENVELOPE + "gpt56_sol_grader_seal_20261106.json"
RECORD_SHA256 = "bf4b38105c6b9bb5deb380f0faf53cafa58efd9d58e3f08b43be55cd5c65b19c"
PREVIOUS_RECORD = sealed.RECORD
PREVIOUS_RECORD_SHA256 = sealed.RECORD_SHA256
PREVIOUS_SOURCE = sealed.REVIEWED_BASE
PREVIOUS_HASH = sealed.GRADER_HASH
REVIEWED_BASE = "788fdfcc51099d7082d79a0e86328a4bb3a6756c"
GRADER_HASH = "7a9aa01048b874c09642ee8cd73493cbe81065bb8d5c02ed52057c00ac78048c"
TEMPLATE = sealed.TEMPLATE
#: The exact reviewed delta. Any other closure change refuses until resealed.
CHANGED_FILES = frozenset({
    "batch-runner/core/deliverable_selector.py",
    "batch-runner/core/tools/read_deliverable.py",
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
