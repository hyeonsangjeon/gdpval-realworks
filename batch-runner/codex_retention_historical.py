"""Fixed historical input/metadata commands, never a historical runtime.

The archived compiler describes the last old producer. It does not approve the
current retention source. Only the existing four-original importer, config/input
materializers and offline Step1 serializer may run here. Step2 is not an option.
"""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile

import yaml

import codex_budget_pilot as pilot
import codex_retention_prepare_packet as preparation
from ghcp_vm_input_bundle import _publication_parents, _write_no_clobber
from gpt54_codex_input_capture import CAPTURE_PATH, CONFIG_PATH, DATASET_ROOT, MANIFEST_PATH, PREPARED_PATH
from gpt54_run_config_bundle import COMBINED_PLAN_PATH, READY_PATH as CONFIG_READY_PATH
from gpt54_run_input_bundle import PARQUET_PATH, READY_PATH as INPUT_READY_PATH, RESERVATION_PATH, STEP0_MANIFEST_PATH

SOURCE = "8ac891e3e0e4752fe15a00139a2691ddf9df7dce"
PRODUCER = "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e"
FINAL_CELL = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_A_r2"
FINAL_RUN = "36277325255"
FORMAT = "retention-historical-input-observer-v1"
ROOT = preparation.ROOT
# This is an offline serialization identity, not a cell admission/generation.
# Both same-run jobs must reconstruct identical five-task prepared bytes.
INPUT_LINEAGE = "retention_bundle_diagnostic_20260929:historical-inputs:" + SOURCE

SAFE_ERROR = r'''
import json, sys
def metadata_error(kind, error, traceback):
    while traceback.tb_next is not None:
        traceback = traceback.tb_next
    print(json.dumps({"metadata_error": {"type": kind.__name__,
        "symbol": traceback.tb_frame.f_code.co_name, "line": traceback.tb_lineno}}))
sys.excepthook = metadata_error
'''

# Run with cwd set to the verified archive's batch-runner, not by changing any
# compiler global or pin. The result contains metadata, never private task text.
OBSERVE = r'''
import json, sys
from pathlib import Path
import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
plan, parent, _ = pilot.compile_pilot(ci.CAMPAIGN, "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e")
plan["ci"] = {"registration_sha256": pilot._identity(ci._registration_bytes())["sha256"],
              "selected_cell_id": plan["order"][-1], "host": {"workflow": ci.WORKFLOW}}
sources = pilot.InputSources(*(Path(value) for value in sys.argv[1:]))
inputs = ci._inputs(parent, sources, pilot.LocalTransport())
print(pilot._canonical_json({"format": "retention-historical-input-observer-v1",
    "observer_source_sha": "8ac891e3e0e4752fe15a00139a2691ddf9df7dce",
    "producer_source_sha": "78089c2fea3b6dd230a5b62e0e5a3f0a9b7a803e", "plan": plan, "inputs": inputs}))
'''

MATERIALIZE = r'''
import contextlib, io, json, sys
from pathlib import Path
from gpt54_comparison_preflight import ROOT, compile_grading_plan, load_plan
from gpt54_run_config_bundle import materialize_run_config_bundle
from gpt54_run_input_bundle import materialize_run_input_bundle, verify_run_input_bundle
from step1_prepare_tasks import prepare_tasks
manifest = load_plan()
plan = compile_grading_plan(manifest)
index, = [i for i, run in enumerate(plan.dispatch.runs) if run.condition == "codex" and run.repeat == 1]
run, grading = plan.dispatch.runs[index], plan.runs[index]
materialize_run_config_bundle(run, grading, manifest=manifest, combined_plan=plan.as_dict(), checkout=ROOT)
materialize_run_input_bundle(run, manifest=manifest, combined_plan=plan.as_dict(), checkout=ROOT,
    dataset_parquet=Path(sys.argv[1]), reference_root=Path(sys.argv[2]), step0_manifest=Path(sys.argv[3]))
with contextlib.redirect_stdout(io.StringIO()):
    prepared = prepare_tasks("comparison-run.json")
verify_run_input_bundle(checkout=ROOT, run_id=run.run_id, condition="codex")
print(json.dumps({"original_five_prepared": len(prepared["tasks"]) == 5,
                  "prepared_fingerprint": prepared["prepared_fingerprint"]}))
'''


class HistoricalSourceRefused(ValueError):
    """Closed categories; no path, input, provider body or credential text."""


def _require(condition, reason):
    if not condition:
        raise HistoricalSourceRefused(reason)


def _members(data: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
        _require(archive.pax_headers.get("comment") == SOURCE, "historical_archive_commit_mismatch")
        result = {}
        for member in archive.getmembers():
            path = Path(member.name)
            _require(not path.is_absolute() and ".." not in path.parts
                     and path.parts[0] in {"batch-runner", ".github"}
                     and (member.isdir() or member.isfile()), "historical_archive_member_refused")
            if member.isfile():
                _require(member.name not in result, "historical_archive_duplicate")
                with archive.extractfile(member) as stream:
                    result[member.name] = stream.read()
        return result


def archive_bytes() -> bytes:
    # _git uses an explicit, credential-free Git environment and no lazy fetch.
    return pilot._git(ROOT, "archive", "--format=tar", SOURCE, "batch-runner", ".github/workflows").stdout


def materialize_archive(destination: Path) -> dict:
    destination = preparation._path(destination)
    _require(not destination.is_relative_to(ROOT) and not ROOT.is_relative_to(destination),
             "historical_archive_must_be_separate")
    _require(not os.path.lexists(destination), "historical_archive_collision")
    members = _members(archive_bytes())
    # The real existing held-FD writer also covers this metadata-only tree.
    with _publication_parents(destination.parent) as (check_parent, mkdir, _):
        mkdir(destination)
        with _publication_parents(destination) as (check, mkdir, directory_fd):
            directories = {parent for name in members for parent in (destination / name).parents
                           if parent.is_relative_to(destination) and parent != destination}
            for directory in sorted(directories, key=lambda path: (len(path.parts), str(path))):
                mkdir(directory)
            for name, data in members.items():
                check_parent()
                check()
                _write_no_clobber(destination / name, data, parent_fd=directory_fd((destination / name).parent))
            os.fsync(directory_fd(destination))
            check_parent()
            check()
    return verify_archive(destination)


def verify_archive(root: Path) -> dict:
    root = preparation._path(root)
    _require(root != ROOT and not root.is_relative_to(ROOT), "historical_archive_must_be_separate")
    members = _members(archive_bytes())
    # Exact inert output roles of the unchanged Codex-r1 materializers. No
    # extra source, bytecode, package directory or import-shadowing file may be
    # present when a Python metadata command starts in this archived tree.
    manifest = yaml.safe_load(members[MANIFEST_PATH])
    run, = [row for row in manifest["runs"] if row["condition"] == "codex" and row["repeat"] == 1]
    outputs = {
        COMBINED_PLAN_PATH, CONFIG_PATH, CONFIG_READY_PATH, INPUT_READY_PATH, RESERVATION_PATH,
        "batch-runner/comparison-grading.json",
        "batch-runner/experiments/execution_envelope/" + run["run_id"] + ".yaml",
        PARQUET_PATH, STEP0_MANIFEST_PATH, PREPARED_PATH, CAPTURE_PATH,
        *(DATASET_ROOT + "/" + name for name in manifest["shared"]["dataset"]["input_file_versions"]
          if name.startswith("reference_files/")),
    }
    files = set(members) | outputs
    directories = {str(parent) for name in files for parent in Path(name).parents if str(parent) != "."}
    for parent, subdirectories, filenames in os.walk(root, followlinks=False):
        for name in subdirectories + filenames:
            path = Path(parent) / name
            role, metadata = path.relative_to(root).as_posix(), path.lstat()
            _require((role in directories and stat.S_ISDIR(metadata.st_mode))
                     or (role in files and stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1),
                     "historical_unexpected_member_refused")
    for name, data in members.items():
        _require(preparation._read(root / name, "historical_source") == data, "historical_source_bytes_changed")
    return {"source_sha": SOURCE, "files_sha256": pilot._digest({
        name: pilot._identity(data) for name, data in members.items()})}


def _command(root: Path, sources: preparation.PreparedInputs, script: str) -> dict:
    verify_archive(root)
    # Deliberately no provider, GitHub, HF, Python-path or native-state env.
    _require(script in (OBSERVE, MATERIALIZE), "historical_command_refused")
    environment = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "GDPVAL_RELAY_LINEAGE_ID": INPUT_LINEAGE}
    try:
        result = subprocess.run([sys.executable, "-c", SAFE_ERROR + script, str(sources.dataset_parquet),
            str(sources.reference_root), str(sources.step0_manifest)], cwd=root / "batch-runner",
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise HistoricalSourceRefused("historical_metadata_process_unresolved") from None
    _require(len(result.stdout) <= 256 * 1024, "historical_metadata_response_too_large")
    if result.returncode != 0:
        reason = "historical_input_compilation_refused"
        # A fixed script's exception hook emits only structural metadata. Never
        # forward stderr, exception messages, private paths or task contents.
        try:
            diagnostic = preparation._json_object(result.stdout)["metadata_error"]
            if (set(diagnostic) == {"type", "symbol", "line"}
                    and type(diagnostic["type"]) is str
                    and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]{0,100}", diagnostic["type"])
                    and type(diagnostic["symbol"]) is str
                    and (diagnostic["symbol"] == "<module>" or re.fullmatch(
                        r"[A-Za-z_][A-Za-z_0-9]{0,100}", diagnostic["symbol"]))
                    and type(diagnostic["line"]) is int and diagnostic["line"] > 0):
                reason += ":{type}:{symbol}:{line}".format(**diagnostic)
        except (ValueError, KeyError, TypeError):
            pass
        raise HistoricalSourceRefused(reason)
    verify_archive(root)
    return preparation._json_object(result.stdout)


def observe(root: Path, sources: preparation.PreparedInputs) -> dict:
    value = _command(root, sources, OBSERVE)
    _require(set(value) == {"format", "observer_source_sha", "producer_source_sha", "plan", "inputs"}
             and value["format"] == FORMAT and value["observer_source_sha"] == SOURCE
             and value["producer_source_sha"] == PRODUCER, "historical_observer_identity_mismatch")
    plan = value["plan"]
    _require(plan["reviewed_source_sha"] == PRODUCER and plan["run_id"] == "budget_pilot_ci_20260925_04"
             and len(plan["cells"]) == len(plan["order"]) == 30 and plan["order"][-1] == FINAL_CELL
             and plan["cells"][-1]["cell_id"] == FINAL_CELL and plan["cells"][-1]["index"] == 29
             and plan["launch_authorized_by_plan"] is False, "historical_final_cell_contract_mismatch")
    _require(set(value["inputs"]) == {"files_sha256", "source_projection_sha256"}
             and value["inputs"]["files_sha256"] == preparation.ORIGINAL_INPUT_ROLES_SHA256
             and all(type(item) is str and len(item) == 64 for item in value["inputs"].values()),
             "historical_input_roles_mismatch")
    return value


def materialize_originals(root: Path, sources: preparation.PreparedInputs) -> dict:
    result = _command(root, sources, MATERIALIZE)
    _require(result.get("original_five_prepared") is True, "historical_original_five_required")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("archive", "verify-archive", "materialize"))
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--original-root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.mode in {"archive", "verify-archive"}:
            value = (materialize_archive if args.mode == "archive" else verify_archive)(args.historical_root)
        else:
            _require(args.original_root is not None, "explicit_original_root_required")
            original = preparation._path(args.original_root)
            value = materialize_originals(args.historical_root, preparation.PreparedInputs(
                args.historical_root, original / "original.parquet", original / "reference-only",
                original / "step0-manifest.json"))
        print(pilot._canonical_json(value))
        return 0
    except (OSError, ValueError, KeyError, TypeError, tarfile.TarError) as error:
        print(pilot._canonical_json({"reason": str(error) if isinstance(error, HistoricalSourceRefused)
                                    else "historical_metadata_refused"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
