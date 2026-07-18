"""Derive immutable live identities from checked-out bytes, not YAML claims."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Mapping


PLAN_MERGE_SHA = "b6408bc5e393748475d28beb1ca472eff75bf547"


def derive_runtime_identity(
    *,
    repository_root: str | Path,
    workflow_path: str | Path,
    workflow_inputs: Mapping[str, Any],
) -> dict:
    root = Path(repository_root).resolve()
    workflow = (root / workflow_path).resolve()
    try:
        workflow.relative_to(root)
    except ValueError as exc:
        raise ValueError("workflow path escapes repository") from exc
    if not workflow.is_file():
        raise ValueError("workflow source is missing")
    git_environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    top_level = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        env=git_environment,
    ).stdout.strip()
    if Path(top_level).resolve() != root:
        raise ValueError("repository root differs from Git top level")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        env=git_environment,
    ).stdout
    if status.strip():
        raise ValueError("live agentic execution requires a clean checkout")
    implementation_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        env=git_environment,
    ).stdout.strip()
    if len(implementation_sha) != 40:
        raise ValueError("implementation Git identity is invalid")
    canonical_inputs = json.dumps(
        dict(workflow_inputs),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return {
        "plan_sha": PLAN_MERGE_SHA,
        "implementation_sha": implementation_sha,
        "workflow_sha": hashlib.sha256(workflow.read_bytes()).hexdigest(),
        "workflow_inputs_sha256": hashlib.sha256(canonical_inputs).hexdigest(),
    }


def derive_runtime_identity_from_environment(
    repository_root: str | Path,
) -> dict:
    workflow_path = os.getenv("AGENTIC_WORKFLOW_PATH")
    raw_inputs = os.getenv("AGENTIC_WORKFLOW_INPUTS_JSON")
    if not workflow_path or not raw_inputs:
        raise ValueError("agentic workflow identity environment is incomplete")
    try:
        workflow_inputs = json.loads(raw_inputs)
    except json.JSONDecodeError as exc:
        raise ValueError("agentic workflow inputs are invalid JSON") from exc
    if not isinstance(workflow_inputs, dict):
        raise ValueError("agentic workflow inputs must be a JSON object")
    return derive_runtime_identity(
        repository_root=repository_root,
        workflow_path=workflow_path,
        workflow_inputs=workflow_inputs,
    )