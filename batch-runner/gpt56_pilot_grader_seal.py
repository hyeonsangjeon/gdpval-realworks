"""An opt-in successor grader identity; never a waiver of historical seals.

The owner approved review/resealing, not a change to the experiment, tariff,
unknown-usage refusals, or launch rights. No credential or provider is used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from gpt54_run_config_bundle import _held_parents, _path
from gpt54_v2_grading_input import _object, _read_bytes


ENVELOPE = "batch-runner/experiments/execution_envelope/"
RECORD = ENVELOPE + "gpt56_sol_grader_seal_20261030.json"
RECORD_SHA256 = "1a5841eed8f7acbdbfdc71d2810b5e6acc5d3b4f87edae8d88cb4bc420150915"
HISTORICAL_SOURCE = "8ac891e3e0e4752fe15a00139a2691ddf9df7dce"
HISTORICAL_HASH = "47effd1db4c1de5ff7cf0473a034ece7748312e682597fb06ee480678e000fcf"
REVIEWED_BASE = "0140b4c125093dc04de9ca0814387c140a929a59"
GRADER_HASH = "099755b009e7563e5b3824ac34c1ab2cf5c83b3cdf4aba7886b50e1c28003fd7"
TEMPLATE = "batch-runner/grading_configs/exp035_codex_foundry_full220_v2_sol_max.yaml"


class GraderSealRefused(ValueError):
    """Closed reason only, including failures while reading or hashing files."""


def source_files(root: Path) -> dict[str, Path]:
    """Enumerate the same template closure as Step8, including new core files."""
    import step8_grade as step8

    batch = root / "batch-runner"
    if Path(os.path.abspath(step8.__file__)) != batch / "step8_grade.py":
        raise GraderSealRefused("grader_successor_seal_refused")
    config_path = _path(root, TEMPLATE)
    config = yaml.safe_load(_read_bytes(config_path))
    paths = [batch / "step8_grade.py", *sorted((batch / "core").rglob("*.py")),
             batch / "schemas/grade.schema.json",
             *step8._requirements_closure(batch, batch / "requirements.txt"),
             batch / "scripts/download_inference_from_hf.py",
             Path(config["prompt"]["template"]), step8.resolve_tool_prompt_path(config)]
    checked = dict(step8._checked_grader_source_file(batch, path) for path in paths)
    checked[TEMPLATE] = config_path
    return checked


def verify(root: Path) -> tuple[dict, dict[str, str]]:
    """Verify a closed manifest and every byte; a new/removed core file refuses.

    The registration proof additionally holds these files against the supplied
    reviewed Git commit. The predecessor manifest/delta is checked against the
    immutable Git source by offline tests; it cannot be edited without changing
    this reader's own reviewed hash.
    """
    try:
        record_data = _read_bytes(_path(root, RECORD), sha256=RECORD_SHA256)
        record = json.loads(record_data, object_pairs_hook=_object)
        if (record["schema_version"] != "gpt56-grader-successor-seal-v1"
                or record["previous"]["source_sha"] != HISTORICAL_SOURCE
                or record["previous"]["grader_source_hash"] != HISTORICAL_HASH
                or record["reviewed_source_sha"] != REVIEWED_BASE
                or record["grader_source_hash"] != GRADER_HASH
                or record["template"] != TEMPLATE):
            raise ValueError()
        before, after = record["previous"]["files"], record["files"]
        changed = {name for name in set(before) | set(after) if before.get(name) != after.get(name)}
        if changed != set(record["changes"]):
            raise ValueError()
        for name, delta in record["changes"].items():
            if delta["before"] != before.get(name) or delta["after"] != after.get(name):
                raise ValueError()
        sources = source_files(root)
        if set(sources) != set(after):
            raise ValueError()
        with _held_parents(root, tuple(sorted({*sources, RECORD}))) as check:
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
            if _read_bytes(_path(root, RECORD), sha256=RECORD_SHA256) != record_data:
                raise ValueError()
            if set(source_files(root)) != set(after):
                raise ValueError()
            check()
        return {
            "status": "reviewed_successor_seal_verified",
            "record": RECORD, "record_sha256": RECORD_SHA256,
            "previous_source_sha": HISTORICAL_SOURCE, "previous_grader_source_hash": HISTORICAL_HASH,
            "reviewed_source_sha": REVIEWED_BASE, "grader_source_hash": actual,
            "changed_files": sorted(changed),
            "equivalence_boundary": "admitted_synthetic_fixture_not_real_five_task_scores",
            "launch_authority": False,
        }, {**after, RECORD: RECORD_SHA256}
    except Exception:
        raise GraderSealRefused("grader_successor_seal_refused") from None
