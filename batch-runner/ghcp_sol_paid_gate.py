"""Explicit Actions-dispatch fixed-five route; never a default or local runner.

Preparation fetches only publicly pinned input bytes, without authentication.
Execution uses the existing supervisor/metadata gate and one selected secret.
Publication excludes auth state and refuses detected credential output.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import urllib.parse
import urllib.request
from pathlib import Path

import ghcp_sol_actions_gate as gate
import ghcp_sol_execution_adapter as adapter
import ghcp_sol_runner_environment as environment
import ghcp_vm_gate_preflight as frozen
import ghcp_vm_input_bundle as inputs

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_EXPORT_BYTES = 128 * 1024 * 1024


def require_dispatch():
    if (os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GHCP_PAID_EXECUTION") != "true"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise adapter._Stop("paid_dispatch_required")
    if not environment.observe()["eligible_for_execution"]:
        raise adapter._Stop(environment.REFUSAL)


def _plan():
    plan = frozen.load_plan(frozen.ROOT / frozen.SOURCE_PROFILE_PATH)
    report = frozen.inspect_plan(plan)
    if report["configuration_valid"] is not True or report["task_ids"] != list(gate.TASK_IDS):
        raise adapter._Stop("paid_input_contract_refused")
    return plan, report


def _download(url, destination, digest):
    # No netrc, inherited token, login or user-controlled URL. Hash before use.
    with urllib.request.urlopen(url, timeout=90) as response:
        raw = response.read(inputs.MAX_INPUT_BYTES + 1)
    if len(raw) > inputs.MAX_INPUT_BYTES or hashlib.sha256(raw).hexdigest() != digest:
        raise adapter._Stop("paid_input_hash_mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with destination.open("xb") as stream:
        stream.write(raw)


def prepare_inputs(root):
    require_dispatch()
    if not root.is_absolute() or root.exists() or any(p.is_symlink() for p in (root, *root.parents)):
        raise adapter._Stop("paid_input_destination_refused")
    plan, report = _plan()
    root.mkdir(mode=0o700)
    source = root / "source"
    source.mkdir(mode=0o700)
    dataset = plan["dataset"]
    base = f"https://huggingface.co/datasets/{dataset['repo_id']}/resolve/{dataset['revision']}/"
    versions = dict(report["input_file_versions"])
    versions.pop(dataset["repo_id"] + "@" + dataset["revision"])
    versions[inputs.PARQUET_PATH] = dataset["parquet_sha256"]
    for role, digest in versions.items():
        if role != inputs.PARQUET_PATH:
            inputs.validate_reference_relative_path(role)
        _download(base + urllib.parse.quote(role, safe="/"), source / role, digest)
    inputs.materialize_ghcp_input_bundle(
        plan, reviewed_plan_sha256=report["plan_sha256"],
        dataset_parquet=source / inputs.PARQUET_PATH, reference_root=source, destination=root / "bundle")


def task_materials(bundle, task_id):
    if task_id not in gate.fixed_task_ids():
        raise adapter._Stop("execution_task_refused")
    plan, report = _plan()
    verified = inputs.verify_ghcp_input_bundle(plan, reviewed_plan_sha256=report["plan_sha256"],
                                              bundle_root=bundle)
    files = dict(verified.files)
    import pyarrow.parquet as parquet
    rows = parquet.read_table(io.BytesIO(files[inputs.PARQUET_PATH]),
                              columns=["task_id", "prompt"], filters=[("task_id", "=", task_id)],
                              use_threads=False).to_pylist()
    if len(rows) != 1 or not isinstance(rows[0]["prompt"], str) or not rows[0]["prompt"]:
        raise adapter._Stop("paid_input_contract_refused")
    record = next(row for row in report["tasks"] if row["task_id"] == task_id)
    references = {role: files[role] for role in record["reference_file_paths"]}
    developer = files[inputs.INSTRUCTIONS_PATH]
    return {
        "prompt": developer.decode("utf-8") + "\n" + rows[0]["prompt"],
        "references": references,
        "identity": {"plan_sha256": report["plan_sha256"], "bundle_sha256": verified.sha256,
                     "task_id": task_id, "prompt_sha256": record["prompt_sha256"],
                     "developer_instructions_sha256": hashlib.sha256(developer).hexdigest(),
                     "prompt_delivery": "exact_developer_then_newline_then_exact_original_prompt",
                     "reference_sha256": {role: hashlib.sha256(raw).hexdigest()
                                          for role, raw in references.items()}},
    }


def stage_task(work, materials):
    for role, raw in materials["references"].items():
        inputs.validate_reference_relative_path(role)
        target = work / role
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as stream:
            stream.write(raw)


def task_command(binary, config, usage_file, prompt):
    # Tool/path/URL approval is not inherited from a NAS login or configuration.
    # No all-paths/all-URLs flag; the five-task work directory is the CLI scope.
    return [str(binary), "--no-auto-update", "--disable-client-telemetry", "--config-dir", str(config),
            "--no-custom-instructions", "--disable-builtin-mcps", "--allow-all-tools",
            "--disallow-temp-dir", "--secret-env-vars=" + ",".join(adapter.AUTH_ENV_NAMES),
            "-p", prompt, "--model", gate.SOL_MODEL, "--reasoning-effort", "max",
            "--context", "long_context", "--output-format", "json", "--stream", "on",
            "--usage-output-file", str(usage_file)]


def _read(path, guard=None, maximum=MAX_FILE_BYTES):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise adapter._Stop("paid_capture_path_refused")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > maximum:
            raise adapter._Stop("paid_capture_file_refused")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        if len(raw) != info.st_size or any(getattr(after, key) != getattr(info, key) for key in
                                         ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
            raise adapter._Stop("paid_capture_file_changed")
    if guard:
        guard.check(raw)
    return raw


def _identity(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def publish_capture(receipt, state, destination, guard):
    """Copy only validated deliverables and supervised JSONL, never HOME/config."""
    record = {"schema_version": "ghcp-paid-capture-v1", "task_id": receipt["task_id"],
              "execution_receipt": receipt, "output_files": [], "transcript": None,
              "deliverable_text": None, "ready_for_contract": False, "judge_calls": 0}
    if receipt["exit_status"] != 0 or receipt.get("metadata_gate_passed") is not True:
        return record
    task_root = state / receipt["task_id"] / "private"
    transcript = _read(task_root / "transcript.jsonl", guard, gate.MAX_EVENT_BYTES)
    text = None
    for line in transcript.splitlines():
        event = json.loads(line, object_pairs_hook=gate._unique_object, parse_constant=gate._invalid_constant)
        if event.get("type") == "assistant.message":
            content = event.get("data", {}).get("content")
            if isinstance(content, str) and content:
                text = content
    originals = receipt["input_binding"]["reference_sha256"]
    outputs = []
    total = len(transcript)
    work = task_root / "files"
    for path in sorted(work.rglob("*")):
        relative = path.relative_to(work)
        if path.is_symlink() or any(part.startswith(".") for part in relative.parts):
            raise adapter._Stop("paid_capture_path_refused")
        if path.is_dir():
            continue
        guard.check(relative.as_posix().encode())
        raw = _read(path, guard)
        if originals.get(relative.as_posix()) == hashlib.sha256(raw).hexdigest():
            continue
        total += len(raw)
        if total > MAX_EXPORT_BYTES or len(outputs) >= 256:
            raise adapter._Stop("paid_capture_size_refused")
        outputs.append((relative.as_posix(), raw))
    if not outputs and not text:
        raise adapter._Stop("paid_deliverable_missing")
    # Validate the entire export before making any artifact-visible private copy.
    record.update(transcript=_identity(transcript), deliverable_text=text, ready_for_contract=True,
                  output_files=[{"path": role, **_identity(raw)} for role, raw in outputs])
    guard.check(json.dumps(record, allow_nan=False).encode())
    (destination / "transcript.jsonl").write_bytes(transcript)
    for role, raw in outputs:
        target = destination / "files" / role
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as stream:
            stream.write(raw)
    return record


def execute_task(task_id, binary, bundle, state, output, *, execution_adapter="copilot-cli"):
    # Only this function consumes the opted-in environment value at runtime.
    # CI calls it with synthetic values only; push never enters the paid job.
    record = {"schema_version": "ghcp-paid-capture-v1", "task_id": task_id if task_id in gate.TASK_IDS else None,
              "ready_for_contract": False, "reason_codes": [], "judge_calls": 0}
    guard = None
    owned = False
    try:
        require_dispatch()
        if execution_adapter not in {"copilot-cli", "ahp-draft"}:
            raise adapter._Stop("execution_adapter_refused")
        if task_id not in gate.fixed_task_ids():
            raise adapter._Stop("execution_task_refused")
        if (not output.is_absolute() or output.exists()
                or any(p.is_symlink() for p in (output, *output.parents))
                or output.is_relative_to(state) or state.is_relative_to(output)):
            raise adapter._Stop("paid_capture_destination_refused")
        output.mkdir(mode=0o700)
        owned = True
        authentication = adapter._selected_auth_environment("COPILOT_GITHUB_TOKEN", state_root=state)
        guard = adapter._CredentialGuard(authentication["COPILOT_GITHUB_TOKEN"])
        if execution_adapter == "ahp-draft":
            # Auth alone cannot prove server-internal hard caps or Sol/Max/1M.
            # Do not launch a host, send authenticate/prompt, or fall back to CLI.
            from ghcp_ahp_client import draft_receipt
            record["execution_receipt"] = draft_receipt()
            raise adapter._Stop("ahp_paid_contract_unverified")
        receipt = adapter.run_task(task_id, [], state, execution_enabled=True,
            execution_config={"tool_calls_per_task": 32}, copilot_cli=binary,
            auth_source="COPILOT_GITHUB_TOKEN", task_bundle=bundle)
        record = publish_capture(receipt, state, output, guard)
    except adapter._Stop as error:
        record["reason_codes"] = [error.code]
    except Exception:
        record["reason_codes"] = ["paid_task_refused"]
    if guard:
        try:
            guard.check(json.dumps(record, allow_nan=False).encode())
        except adapter._Stop:
            record = {"schema_version": "ghcp-paid-capture-v1", "ready_for_contract": False,
                      "reason_codes": ["authentication_secret_exposure_refused"]}
    # Pre-auth refusals have no task state; the caller gets a static report only.
    if owned:
        with (output / "capture.json").open("x", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True, allow_nan=False)
    return record


def main(argv=None):
    parser = adapter._Parser(description=__doc__)
    parser.add_argument("--prepare-inputs", type=Path)
    parser.add_argument("--task-id", choices=gate.TASK_IDS)
    parser.add_argument("--copilot-bin", type=Path)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--adapter", choices=("copilot-cli", "ahp-draft"), default="copilot-cli")
    args = parser.parse_args(argv)
    if args.prepare_inputs:
        try:
            prepare_inputs(args.prepare_inputs)
        except Exception:
            print('{"reason_codes":["paid_input_preparation_refused"]}')
            return 2
        print('{"input_bundle_verified":true,"model_calls":0}')
        return 0
    if any(value is None for value in (args.task_id, args.copilot_bin, args.bundle, args.state_root, args.output)):
        parser.error("missing arguments")
    result = execute_task(args.task_id, args.copilot_bin, args.bundle, args.state_root, args.output,
                          execution_adapter=args.adapter)
    # Never print task text, raw transcripts, paths, or credentials to Actions logs.
    print(json.dumps({"ready_for_contract": result.get("ready_for_contract", False),
                      "reason_codes": result.get("reason_codes", result.get("execution_receipt", {}).get("reason_codes", []))}))
    return 0 if result.get("ready_for_contract") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
