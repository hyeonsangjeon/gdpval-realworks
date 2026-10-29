"""Convert five empty dry captures to a Step8 layout, never run a grader.

Use the unchanged Step8 reader/validators. Empty captures cannot supply actual
answers, rubric bytes or a source inference revision, and never become scores.
The CLI is hosted-Ubuntu-24.04 only; local tests use synthetic host metadata.
"""

from __future__ import annotations

import argparse
import builtins
import hashlib
import json
import os
import re
import stat
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest.mock import patch

import yaml

import ghcp_sol_actions_gate as capture
import ghcp_sol_runner_environment as environment
import ghcp_vm_gate_preflight as contract

ROOT = Path(__file__).resolve().parents[1]
REPORT = "grader-contract.json"
MANIFEST = "workspace/step2_inference_results.json"
MAX_CAPTURE_BYTES = 65_536
INPUT_CONTRACT_SHA256 = "4187bdbf45c3bb1d9cd8059c499cfd8e6c0440795395b5f2d044528e67e1fc92"
_ACTIVE = 0


class Refused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class EffectsRefused(BaseException):
    """A model/data/auth effect cannot be swallowed as an optional import."""


def _deny(*args, **kwargs):
    raise EffectsRefused("model_free_grader_effect_refused")


def _audit(event, arguments):
    if not _ACTIVE:
        return
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "subprocess.Popen",
                 "os.system", "os.exec", "os.posix_spawn", "os.fork"}:
        _deny()
    if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
        path = Path(os.fsdecode(arguments[0]))
        if path.name in {".env", "auth.json", "hosts.yml", "credentials", "token", "stored_tokens"}:
            _deny()


sys.addaudithook(_audit)


@contextmanager
def _no_effects():
    global _ACTIVE
    original = builtins.__import__
    def importing(name, *args, **kwargs):
        if name.split(".")[0] in {"azure", "openai", "anthropic", "copilot", "openai_codex"}:
            _deny()
        return original(name, *args, **kwargs)
    _ACTIVE += 1
    try:
        with patch.object(builtins, "__import__", importing):
            yield
    finally:
        _ACTIVE -= 1


def _require(value, code):
    if not value:
        raise Refused(code)


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _path(path):
    _require(isinstance(path, Path) and path.is_absolute() and ".." not in path.parts,
             "grader_path_refused")
    _require(not any(item.is_symlink() for item in (path, *path.parents)), "grader_path_refused")
    return path


def _read(path, maximum=MAX_CAPTURE_BYTES):
    _path(path)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        before = os.fstat(stream.fileno())
        _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum,
                 "grader_file_refused")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    _require(len(raw) <= maximum and all(getattr(before, key) == getattr(after, key) for key in fields),
             "grader_file_changed")
    return raw


def _json(raw):
    return json.loads(raw, object_pairs_hook=capture._unique_object, parse_constant=capture._invalid_constant)


def _safe_text(value):
    return type(value) is str and bool(re.fullmatch(r"[A-Za-z0-9 _./:+-]{1,128}", value))


def _check_capture(value, task_id):
    expected = capture.capture_envelope(task_id)
    dynamic = {"versions", "runner_identity"}
    _require(type(value) is dict and value.keys() == expected.keys(), "dry_capture_format_mismatch")
    _require(_bytes({key: value[key] for key in value if key not in dynamic})
             == _bytes({key: expected[key] for key in expected if key not in dynamic}),
             "dry_capture_contract_mismatch")
    versions = value["versions"]
    _require(type(versions) is dict and versions.keys() == expected["versions"].keys()
             and all(_safe_text(item) for item in versions.values())
             and versions["os"] == "Linux"
             and all(versions[key] == "not available" for key in ("ghcp_cli", "codex_cli", "codex_sdk")),
             "dry_capture_versions_unverified")
    runner = value["runner_identity"]
    _require(type(runner) is dict and runner.keys() == expected["runner_identity"].keys(),
             "dry_capture_runner_unverified")
    mutable = {"runner_name", "image_version"}
    _require(_bytes({key: runner[key] for key in runner if key not in mutable})
             == _bytes({key: expected["runner_identity"][key] for key in runner if key not in mutable})
             and runner["eligible_for_execution"] is True and _safe_text(runner["runner_name"])
             and _safe_text(runner["image_version"])
             and re.fullmatch(r"[0-9]{8}\.[0-9]+(?:\.[0-9]+)?", runner["image_version"]),
             "dry_capture_runner_unverified")


def _captures(directory):
    _require(_path(directory).is_dir(), "dry_capture_bundle_missing")
    ids = capture.fixed_task_ids()
    names = {"ghcp-sol-dry-capture-" + task_id for task_id in ids}
    _require({item.name for item in directory.iterdir()} == names, "dry_capture_set_mismatch")
    records = []
    for task_id in ids:
        folder = _path(directory / ("ghcp-sol-dry-capture-" + task_id))
        _require(folder.is_dir() and {item.name for item in folder.iterdir()} == {"capture.json"},
                 "dry_capture_artifact_shape_mismatch")
        path = folder / "capture.json"
        raw = _read(path)
        _check_capture(_json(raw), task_id)
        records.append((task_id, path, raw))
    return records


@contextmanager
def _cwd(path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _step8_checks(output, payload):
    plan = contract.load_plan(contract.ROOT / contract.SOURCE_PROFILE_PATH)
    checked = contract.inspect_plan(plan)
    _require(checked["configuration_valid"] is True, "pinned_grader_contract_refused")
    batch = ROOT / "batch-runner"
    source = batch / "step8_grade.py"
    template = ROOT / plan["grading"]["template"]
    template_bytes = _read(template)
    _require(hashlib.sha256(template_bytes).hexdigest() == plan["source_pins"][plan["grading"]["template"]],
             "grader_template_drift")
    manifest_bytes = _read(batch / "core/inference_manifest.py", 1_048_576)
    _require(hashlib.sha256(manifest_bytes).hexdigest() == INPUT_CONTRACT_SHA256, "step8_input_contract_drift")
    import step8_grade as step8
    _require(Path(step8.__file__).resolve() == source.resolve(), "step8_module_identity_refused")
    _require(Path(sys.modules["core.inference_manifest"].__file__).resolve()
             == (batch / "core/inference_manifest.py").resolve(), "step8_module_identity_refused")
    config = yaml.safe_load(template_bytes)
    with ExitStack() as blocked:
        for owner, name in ((step8.Grader, "__init__"), (step8.RubricLoader, "__init__"),
                            (step8, "main"), (step8, "preflight_routes")):
            blocked.enter_context(patch.object(owner, name, _deny))
        with _cwd(batch):
            step8.validate_grading_config(config)
        with _cwd(output):
            loaded = step8.load_local_inference_results()
            _require(_bytes(loaded) == _bytes(payload), "step8_manifest_roundtrip_mismatch")
            rows = step8.filter_tasks(loaded, None, 0)
            _require([row["task_id"] for row in rows] == list(capture.TASK_IDS), "step8_task_set_mismatch")
            normalized = step8.validate_local_deliverables(rows, output / "workspace/upload")
            _require(_bytes(normalized) == _bytes(rows), "step8_deliverable_tree_mismatch")
            for row in rows:
                directory = Path(step8.resolve_deliverable_dir(row))
                _require(directory == output / "workspace/upload/deliverable_files" / row["task_id"]
                         and directory.is_dir(), "step8_deliverable_tree_mismatch")
                if payload["model_free"]:
                    _require(not list(directory.iterdir()), "step8_deliverable_tree_mismatch")
            # These are expected refusals of LIVE grading, not a fabricated
            # inference SHA, a changed full-220 identity, or a passed grade.
            try:
                step8.resolve_source_inference_identity(loaded, config["schema_version"])
            except ValueError:
                pass
            else:
                raise Refused("dry_capture_must_not_have_live_inference_identity")
            try:
                step8._validate_pinned_rerun_identity(config, experiment_id=payload["experiment_id"],
                    task_ids=list(capture.TASK_IDS), rubric_commit_sha=config["rubric"]["revision"], inference_revision=None)
            except ValueError:
                pass
            else:
                raise Refused("full220_grader_identity_must_not_admit_dry_capture")
    _require(_read(template) == template_bytes and _read(batch / "core/inference_manifest.py", 1_048_576)
             == manifest_bytes, "grader_contract_changed")
    _require(contract.inspect_plan(plan)["configuration_valid"] is True, "pinned_grader_contract_refused")
    return {
        "template": plan["grading"]["template"], "template_sha256": hashlib.sha256(template_bytes).hexdigest(),
        "step8_sha256": plan["source_pins"]["batch-runner/step8_grade.py"],
        "input_contract_sha256": INPUT_CONTRACT_SHA256,
        "passed": ["pinned_ghcp_policy", "validate_grading_config", "load_local_inference_results",
                   "filter_tasks", "validate_local_deliverables", "resolve_deliverable_dir"],
        "live_refusals_observed": ["source_inference_identity_missing", "full220_rerun_identity_not_reusable"],
    }


def _paid_captures(directory):
    from ghcp_sol_paid_gate import _read as read_paid, _identity, MAX_EXPORT_BYTES
    _require(_path(directory).is_dir(), "paid_capture_bundle_missing")
    _require({item.name for item in directory.iterdir()}
             == {"ghcp-sol-paid-capture-" + task for task in capture.fixed_task_ids()}, "paid_capture_set_mismatch")
    records, values, exported = [], {}, {}
    for task_id in capture.TASK_IDS:
        folder = _path(directory / ("ghcp-sol-paid-capture-" + task_id))
        path = folder / "capture.json"
        raw = _read(path, 8 * 1024 * 1024)
        value = _json(raw)
        receipt = value["execution_receipt"]
        _require(value["schema_version"] == "ghcp-paid-capture-v1" and value["task_id"] == task_id
                 and value["ready_for_contract"] is True and value["judge_calls"] == 0
                 and receipt["task_id"] == task_id and receipt["exit_status"] == 0
                 and receipt["settings_verification"] == "verified" and receipt["metadata_gate_passed"] is True
                 and not receipt["reason_codes"] and receipt["subprocess_returncode"] == 0
                 and receipt["runner_identity"]["eligible_for_execution"] is True,
                 "paid_capture_unverified")
        transcript = read_paid(folder / "transcript.jsonl", maximum=capture.MAX_EVENT_BYTES)
        _require(_identity(transcript) == value["transcript"], "paid_capture_hash_mismatch")
        events = [_json(line) for line in transcript.splitlines()]
        projection = capture.collect_session_events(
            (event for event in events if isinstance(event.get("data"), dict)), runtime_projection=True)
        _require(projection["calls"] and not projection["reason_codes"]
                 and all(call["verification"] == "verified" for call in projection["calls"]),
                 "paid_capture_settings_unverified")
        expected = {"capture.json", "transcript.jsonl"}
        files, total = {}, len(transcript)
        _require(type(value["output_files"]) is list and len(value["output_files"]) <= 256,
                 "paid_capture_format_mismatch")
        for item in value["output_files"]:
            role = item["path"]
            _require(type(role) is str and role and not Path(role).is_absolute()
                     and all(part not in {"", ".", ".."} and not part.startswith(".")
                             for part in role.split("/")) and role not in files, "paid_capture_path_refused")
            data = read_paid(folder / "files" / role)
            _require(_identity(data) == {key: item[key] for key in ("sha256", "size")}, "paid_capture_hash_mismatch")
            total += len(data)
            _require(total <= MAX_EXPORT_BYTES, "paid_capture_size_refused")
            files[role] = data
            expected.add("files/" + role)
        _require({p.relative_to(folder).as_posix() for p in folder.rglob("*") if not p.is_dir()} == expected
                 and not any(p.is_symlink() for p in folder.rglob("*")), "paid_capture_artifact_shape_mismatch")
        _require(files or isinstance(value["deliverable_text"], str) and bool(value["deliverable_text"]),
                 "paid_deliverable_missing")
        records.append((task_id, path, raw))
        values[task_id], exported[task_id] = value, files
    return records, values, exported


def convert_and_validate(captures: Path, output: Path, *, mode="dry"):
    report = {
        "schema_version": "ghcp-step8-model-free-contract-v1", "status": "refused", "exit_status": 2,
        "reason_codes": [], "runner_identity": environment.observe(), "capture_inputs": [],
        "step8_layout_valid": False, "grader_policy_valid": False, "ready_for_grading": False,
        "gate5_passed": False, "paid_execution_allowed": False, "model_calls": 0, "judge_calls": 0,
        "grade": None, "usage": None, "usage_status": "not available", "cost": None,
        "cost_status": "not available", "rubric_bytes_loaded": False, "renderer_executed": False,
        "evidence_boundary": "empty_capture_step8_layout_and_policy_not_real_grade_or_launch_approval",
    }
    owned = False
    try:
        _require(mode in {"dry", "paid"}, "grader_capture_mode_refused")
        _require(report["runner_identity"]["eligible_for_execution"], environment.REFUSAL)
        _path(captures)
        _path(output)
        _require(not output.exists() and not output.is_relative_to(captures)
                 and not captures.is_relative_to(output), "grader_output_reuse_refused")
        output.mkdir(mode=0o700)
        owned = True
        with _no_effects():
            values, exported = {}, {}
            if mode == "paid":
                records, values, exported = _paid_captures(captures)
            else:
                records = _captures(captures)
            report["capture_inputs"] = [{"task_id": task_id, "sha256": hashlib.sha256(raw).hexdigest()}
                                        for task_id, _, raw in records]
            payload = {
                "record_version": "ghcp-step8-model-free-input-v1", "experiment_id": "ghcp_sol_model_free_contract",
                "model_free": True, "inference_performed": False, "grading_allowed": False,
                "source_repo_id": None, "source_revision": None,
                "results": [{"task_id": task_id, "status": "pending", "content": None,
                             "deliverable_text": "", "deliverable_files": [], "usage": None,
                             "dry_capture_sha256": hashlib.sha256(raw).hexdigest()} for task_id, _, raw in records],
            }
            for task_id, _, _ in records:
                (output / "workspace/upload/deliverable_files" / task_id).mkdir(parents=True, mode=0o700)
            if mode == "paid":
                payload.update(record_version="ghcp-step8-paid-input-v1", experiment_id="ghcp_sol_paid_input_contract",
                               model_free=False, inference_performed=True)
                for row in payload["results"]:
                    task_id = row["task_id"]
                    row.update(status="success", content=values[task_id]["deliverable_text"],
                               deliverable_text=values[task_id]["deliverable_text"] or "",
                               usage=values[task_id]["execution_receipt"]["usage"])
                    for role, data in exported[task_id].items():
                        name = f"deliverable_files/{task_id}/{role}"
                        destination = output / "workspace/upload" / name
                        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        with destination.open("xb") as stream:
                            stream.write(data)
                        row["deliverable_files"].append(name)
                    row["paid_capture_sha256"] = row.pop("dry_capture_sha256")
            with (output / MANIFEST).open("xb") as stream:
                stream.write(_bytes(payload) + b"\n")
            report["contract_checks"] = _step8_checks(output, payload)
            for _, path, raw in records:
                _require(_read(path) == raw, "dry_capture_changed")
            manifest = _read(output / MANIFEST)
            _require(manifest == _bytes(payload) + b"\n", "step8_manifest_changed")
            _require(environment.observe() == report["runner_identity"], "execution_environment_changed")
            if mode == "paid":
                _require(_paid_captures(captures) == (records, values, exported), "paid_capture_changed")
            report.update(status="model_free_layout_verified", exit_status=0, step8_layout_valid=True,
                          grader_policy_valid=True, task_count=5, manifest=MANIFEST,
                          manifest_sha256=hashlib.sha256(manifest).hexdigest(),
                          live_blockers=["real_answers_and_rubric_not_captured", "source_inference_identity_missing",
                                         "five_task_grading_identity_not_materialized"])
            if mode == "paid":
                report.update(status="paid_capture_layout_verified", capture_mode="paid",
                    evidence_boundary="observed_capture_layout_and_policy_not_actual_grading",
                    live_blockers=["rubric_bytes_not_loaded", "source_inference_identity_missing",
                                   "five_task_grading_identity_not_materialized"])
    except Refused as error:
        report["reason_codes"] = [error.code]
    except EffectsRefused:
        report["reason_codes"] = ["model_free_grader_effect_refused"]
    except Exception:
        report["reason_codes"] = ["grader_contract_validation_refused"]
    if owned:
        try:
            with (output / REPORT).open("x", encoding="utf-8") as stream:
                json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
        except OSError:
            report.update(status="refused", exit_status=2, reason_codes=["grader_contract_receipt_write_failed"])
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "ghcp_grader_contract_arguments_refused\n")


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("dry", "paid"), default="dry")
    args = parser.parse_args(argv)
    report = convert_and_validate(args.captures, args.output, mode=args.mode)
    print(json.dumps(report, sort_keys=True, allow_nan=False))
    return report["exit_status"]


if __name__ == "__main__":
    raise SystemExit(main())
