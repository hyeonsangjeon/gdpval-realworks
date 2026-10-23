"""Model-free Actions plan/capture rehearsal; no GHCP, Codex or grader client."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

from core.execution_envelope_tasks import (
    CATALOG_PATH,
    TaskCatalog,
    select_advance_check_tasks,
)

CATALOG_SHA256 = "5f1eca853979b2b4efe6c6ba656545c3a416da920e3faf067d52f5d8ac4ae0eb"
TASK_IDS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",
)
REQUESTED = {
    "provider": "GitHub Copilot",
    "model": "GPT-5.6 Sol",
    "harness": "Codex agent",
    "reasoning": "Max",
    "context": "1M",
    "context_tokens": 1_000_000,
}
PRIVATE_PATHS = {
    "transcript": "private/transcript.jsonl",
    "tool_calls": "private/tool-calls.jsonl",
    "commands": "private/commands.jsonl",
    "input_file_hashes": "private/input-file-hashes.json",
    "output_file_hashes": "private/output-file-hashes.json",
    "exit_status": "private/exit-status.json",
    "files": "private/files",
}


def fixed_task_ids() -> tuple[str, ...]:
    """Re-derive the cohort from the pinned score-free public catalogue."""
    data = CATALOG_PATH.read_bytes()
    if hashlib.sha256(data).hexdigest() != CATALOG_SHA256:
        raise ValueError("public_catalog_identity_refused")
    catalog = TaskCatalog.from_mapping(json.loads(data))
    selected = select_advance_check_tasks(catalog, catalog_fingerprint=CATALOG_SHA256)
    if selected.task_ids != TASK_IDS:
        raise ValueError("fixed_cohort_refused")
    return selected.task_ids


def capture_envelope(task_id: str) -> dict:
    """Construct public metadata from constants, not raw captures or environment."""
    return {
        "schema_version": "ghcp-sol-actions-dry-capture-v1",
        "task_id": task_id,
        "cohort": "advance_check_5",
        "catalog_sha256": CATALOG_SHA256,
        "status": "dry_run_only",
        "paid_execution_allowed": False,
        "model_calls": 0,
        "grader_calls": 0,
        "requested": dict(REQUESTED),
        "actual_served": {key: "not available" for key in REQUESTED},
        "versions": {
            "python": platform.python_version(),
            "os": platform.system(),
            "kernel": platform.release(),
            "ghcp_cli": "not available",
            "codex_cli": "not available",
            "codex_sdk": "not available",
        },
        "execution_target": "GitHub Actions standard runner ubuntu-24.04",
        "target_observed": False,
        "limits": {
            "proposed_paid_timeout_seconds_per_task": 1200,
            "proposed_paid_max_turns_per_task": 64,
            "proposed_paid_retries": 0,
            "paid_limits_approved_or_verified": False,
            "workflow_dry_run_process_timeout_seconds": 60,
            "workflow_dry_run_job_timeout_minutes": 5,
            "dry_run_max_model_turns": 0,
        },
        "capture": {
            "private_task_relative_paths": dict(PRIVATE_PATHS),
            "path_semantics": "relative_to_task_state_not_host_paths",
            "raw_capture_status": "empty_dry_run_placeholders_not_model_evidence",
            "private_inputs_read": False,
            "files_captured": 0,
            "artifact_allowlist": ["capture.json"],
            "private_capture_upload_allowed": False,
            "log_policy": "static_status_only_no_inputs_environment_or_raw_streams",
        },
        "exit_status": 0,
        "usage": None,
        "cost": None,
        "grade": None,
        "evidence_boundary": "local_plan_and_empty_capture_wiring_not_hosted_or_paid_execution",
    }


def dry_capture(task_id: str, state_root: Path) -> None:
    if task_id not in fixed_task_ids():
        raise ValueError("fixed_task_refused")
    if not state_root.is_absolute() or state_root.is_symlink():
        raise ValueError("state_root_refused")
    state_root.mkdir(mode=0o700, exist_ok=True)
    task_root = state_root / task_id
    # Refuse reuse, including symlinks; never adopt a previous conversation.
    task_root.mkdir(mode=0o700)
    private = task_root / "private"
    private.mkdir(mode=0o700)
    (private / "files").mkdir(mode=0o700)
    for name, relative in PRIVATE_PATHS.items():
        if name == "files":
            continue
        contents = ""
        if name.endswith("file_hashes"):
            contents = "[]\n"
        elif name == "exit_status":
            contents = '{"dry_run": true, "model_started": false, "exit_status": 0}\n'
        with (task_root / relative).open("x", encoding="utf-8") as stream:
            stream.write(contents)
    with (task_root / "capture.json").open("x", encoding="utf-8") as stream:
        json.dump(capture_envelope(task_id), stream, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--dry-run", choices=("true", "false"), default="true")
    parser.add_argument("--task-id", choices=TASK_IDS)
    parser.add_argument("--state-root", type=Path)
    args = parser.parse_args(argv)
    if args.dry_run != "true":
        parser.error("paid_execution_not_implemented_or_approved")
    if args.matrix:
        if args.task_id is not None or args.state_root is not None:
            parser.error("matrix_does_not_accept_capture_arguments")
        print(json.dumps({"task_id": fixed_task_ids()}, separators=(",", ":")))
        return 0
    if args.task_id is None or args.state_root is None:
        parser.error("capture_requires_task_id_and_state_root")
    try:
        dry_capture(args.task_id, args.state_root)
    except (OSError, ValueError):
        # Paths and exception strings may contain private data. Emit a fixed error.
        parser.exit(2, "ghcp_sol_dry_capture_refused\n")
    print("ghcp_sol_dry_capture_complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
