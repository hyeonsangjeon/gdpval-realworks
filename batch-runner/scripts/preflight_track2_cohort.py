#!/usr/bin/env python3
"""Emit an exact model-free Track 2 cohort plan from local deliverables."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.grader_preflight import plan_task_runtime, summarize_cohort
from core.inference_manifest import (
    canonicalize_inference_payload,
    task_deliverable_dir,
    validate_local_deliverables,
)
from core.rubric_loader import RubricLoader
from step8_grade import (
    compute_grader_source_hash,
    hash_config,
    resolve_source_inference_identity,
    validate_grading_config,
)


PLANNER_CONTRACT = "track2-selection-ok-v1"


def _planner_source_hash() -> str:
    digest = hashlib.sha256()
    for path in (
        Path(__file__).resolve(),
        BATCH_RUNNER_ROOT / "core" / "grader_preflight.py",
    ):
        relative = path.relative_to(BATCH_RUNNER_ROOT.parent).as_posix()
        content = path.read_bytes()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(content + b"\0")
    return digest.hexdigest()


def _repository_commit() -> str:
    head = subprocess.check_output(
        ["git", "-C", str(BATCH_RUNNER_ROOT.parent), "rev-parse", "HEAD"],
        text=True,
    ).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("repository commit must be a full lowercase SHA")
    github_sha = os.environ.get("GITHUB_SHA", "").strip().lower()
    if github_sha:
        if not re.fullmatch(r"[0-9a-f]{40}", github_sha):
            raise ValueError("GITHUB_SHA must be a full lowercase SHA")
        if github_sha != head:
            raise ValueError(
                f"GITHUB_SHA does not match HEAD: github={github_sha}, head={head}"
            )
    return head


def _worktree_status() -> str:
    return subprocess.check_output(
        [
            "git",
            "-C",
            str(BATCH_RUNNER_ROOT.parent),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ],
        text=True,
    ).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--inference", required=True)
    parser.add_argument("--upload-root", required=True)
    parser.add_argument("--limit", type=int, required=True)
    parser.add_argument("--expected-source-repo", required=True)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--expected-repository-commit", required=True)
    parser.add_argument("--expected-planner-source-hash", required=True)
    parser.add_argument("--expected-config-hash", required=True)
    parser.add_argument("--expected-grader-source-hash", required=True)
    parser.add_argument("--expected-rubric-sha", required=True)
    parser.add_argument(
        "--expected-task-id", action="append", required=True
    )
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")

    config_path = Path(args.config)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_grading_config(config)
    if config.get("schema_version") != "2.0":
        raise SystemExit("cohort preflight requires schema_version 2.0")
    if not (
        ((config.get("judge") or {}).get("tools") or {}).get(
            "read_deliverable"
        )
    ):
        raise SystemExit("cohort preflight requires Track 2 tool calling")
    worktree_status = _worktree_status()
    if worktree_status:
        raise SystemExit("repository worktree must be clean")
    planner_source_hash = _planner_source_hash()
    if planner_source_hash != args.expected_planner_source_hash:
        raise SystemExit(
            "planner source hash mismatch: "
            f"expected={args.expected_planner_source_hash}, "
            f"actual={planner_source_hash}"
        )
    repository_commit = _repository_commit()
    if repository_commit != args.expected_repository_commit:
        raise SystemExit(
            "repository commit mismatch: "
            f"expected={args.expected_repository_commit}, "
            f"actual={repository_commit}"
        )
    config_hash = hash_config(str(config_path))
    if config_hash != args.expected_config_hash:
        raise SystemExit(
            "config hash mismatch: "
            f"expected={args.expected_config_hash}, actual={config_hash}"
        )
    grader_source_hash = compute_grader_source_hash(config_path, config)
    if grader_source_hash != args.expected_grader_source_hash:
        raise SystemExit(
            "grader source hash mismatch: "
            f"expected={args.expected_grader_source_hash}, "
            f"actual={grader_source_hash}"
        )
    inference = canonicalize_inference_payload(
        json.loads(Path(args.inference).read_text(encoding="utf-8"))
    )
    source_repo_id, source_revision = resolve_source_inference_identity(
        inference, "2.0"
    )
    if source_repo_id != args.expected_source_repo:
        raise SystemExit(
            "source repo mismatch: "
            f"expected={args.expected_source_repo}, actual={source_repo_id}"
        )
    if source_revision != args.expected_source_revision:
        raise SystemExit(
            "source revision mismatch: "
            f"expected={args.expected_source_revision}, actual={source_revision}"
        )
    if len(args.expected_task_id) != args.limit:
        raise SystemExit(
            "expected task ID count must equal --limit: "
            f"expected_ids={len(args.expected_task_id)}, limit={args.limit}"
        )
    if len(inference["results"]) < args.limit:
        raise SystemExit(
            f"inference has {len(inference['results'])} rows, below limit {args.limit}"
        )
    tasks = inference["results"][: args.limit]
    if len(tasks) != args.limit:
        raise SystemExit("selected task count does not match --limit")
    actual_task_ids = [task["task_id"] for task in tasks]
    if actual_task_ids != args.expected_task_id:
        raise SystemExit(
            "ordered task IDs mismatch: "
            f"expected={args.expected_task_id}, actual={actual_task_ids}"
        )
    loader = RubricLoader(
        repo_id=config["rubric"]["repo_id"],
        revision=config["rubric"]["revision"],
        cache_dir=config["rubric"]["cache_dir"],
    )
    rubric_sha = loader.rubric_sha
    if rubric_sha != args.expected_rubric_sha:
        raise SystemExit(
            "rubric SHA mismatch: "
            f"expected={args.expected_rubric_sha}, actual={rubric_sha}"
        )
    upload_root = Path(args.upload_root)
    validate_local_deliverables(tasks, upload_root)

    plans = [
        plan_task_runtime(
            config,
            loader.load(task["task_id"]),
            task_deliverable_dir(upload_root, task["task_id"]),
        )
        for task in tasks
    ]
    payload = summarize_cohort(plans)
    payload.update({
        "planner_contract": PLANNER_CONTRACT,
        "planner_source_hash": planner_source_hash,
        "repository_commit": repository_commit,
        "source_repo_id": source_repo_id,
        "source_revision": source_revision,
        "config_name": config["config_name"],
        "config_hash": config_hash,
        "grader_source_hash": grader_source_hash,
        "rubric_sha": rubric_sha,
    })
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: payload[key]
        for key in (
            "task_count",
            "ordered_task_ids",
            "rubric_items",
            "precheck_candidates",
            "precheck_resolved",
            "precheck_fallbacks",
            "judge_routes",
            "planned_render_calls",
            "planned_perception_calls",
            "errors",
        )
    }, ensure_ascii=False))
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())