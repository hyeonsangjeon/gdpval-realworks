#!/usr/bin/env python3
"""Step 8: Grade inference outputs with rubric-based judge.

Usage:
    python step8_grade.py exp998_smoke_baseline_sample \
    --config grading_configs/default_v2_sol_max.yaml \
      --dry-run --limit 3
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import math
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import SchemaError, ValidationError

from core.azure_ai_clients import (
    canonical_deployment,
    grader_route_workloads,
    preflight_routes,
)
from core.experiment_config import ExperimentConfig
from core.grader import (
    Grader,
    _is_critical_item,
    grader_transport_options,
    resolve_tool_prompt_path,
)
from core.grade_payload import canonical_rate, validate_grade_payload
from core.inference_manifest import (
    canonical_task_id,
    canonicalize_inference_payload,
    task_deliverable_dir,
    validate_local_deliverables,
)
from core.public_error import public_provider_error_text
from core.rubric_loader import RubricLoader
from core.tools import ReadDeliverableError, get_renderer_fingerprint

SCHEMA_VERSION = "1.3"
GRADED_BY_VERSION = "0.1.0"
FULL_HF_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _ordered_task_ids_sha256(task_ids: list[str]) -> str:
    encoded = json.dumps(
        task_ids,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def hash_config(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _batch_runner_root() -> Path:
    cwd = Path.cwd().resolve()
    if (cwd / "step8_grade.py").is_file():
        return cwd
    nested = cwd / "batch-runner"
    if (nested / "step8_grade.py").is_file():
        return nested.resolve()
    return cwd


def _checked_grader_source_file(batch_root: Path, path: Path) -> tuple[str, Path]:
    candidate = path if path.is_absolute() else batch_root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(batch_root)
    except ValueError as exc:
        raise ValueError(f"grader source path is outside batch-runner: {path}") from exc

    current = batch_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"grader source path must not be a symlink: {relative}")
    if not candidate.is_file():
        raise ValueError(f"grader source file is missing: {relative}")
    if candidate.resolve() != candidate:
        raise ValueError(f"grader source path must not traverse a symlink: {relative}")
    return f"batch-runner/{relative.as_posix()}", candidate


def _checked_repository_config_file(
    batch_root: Path, path: Path
) -> tuple[str, Path]:
    repo_root = batch_root.parent
    candidate = path if path.is_absolute() else batch_root / path
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(
            f"grading config path is outside the repository: {path}"
        ) from exc

    current = repo_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(
                f"grading config path must not be a symlink: {relative}"
            )
    if not candidate.is_file():
        raise ValueError(f"grading config file is missing: {relative}")
    if candidate.resolve() != candidate:
        raise ValueError(
            f"grading config path must not traverse a symlink: {relative}"
        )
    return relative.as_posix(), candidate


def compute_grader_source_hash(config_path: str | Path, config: dict) -> str:
    batch_root = _batch_runner_root()
    core_root = batch_root / "core"
    if core_root.is_symlink() or not core_root.is_dir():
        raise ValueError("grader source directory is missing or symlinked: core")

    core_python_files: list[Path] = []
    for candidate in core_root.rglob("*"):
        if candidate.is_symlink():
            raise ValueError(
                f"grader source path must not be a symlink: {candidate.relative_to(batch_root)}"
            )
        if candidate.is_file() and candidate.suffix == ".py":
            core_python_files.append(candidate)
    if not core_python_files:
        raise ValueError("grader source directory contains no Python files: core")

    source_paths = [
        batch_root / "step8_grade.py",
        *core_python_files,
        batch_root / "schemas" / "grade.schema.json",
        batch_root / "requirements.txt",
        batch_root / "scripts" / "download_inference_from_hf.py",
        Path(config["prompt"]["template"]),
    ]
    if config.get("prompt", {}).get("tool_template") or (
        (config.get("judge") or {}).get("tools", {}).get("read_deliverable")
    ):
        source_paths.append(resolve_tool_prompt_path(config))

    checked: dict[str, Path] = {}
    for source_path in source_paths:
        relative, candidate = _checked_grader_source_file(batch_root, source_path)
        if relative in checked:
            raise ValueError(f"duplicate grader source path: {relative}")
        checked[relative] = candidate
    config_relative, config_candidate = _checked_repository_config_file(
        batch_root, Path(config_path)
    )
    if config_relative in checked:
        raise ValueError(f"duplicate grader source path: {config_relative}")
    checked[config_relative] = config_candidate

    digest = hashlib.sha256()
    digest.update(b"gdpval-grader-source-v1\x00")
    for relative, candidate in sorted(checked.items()):
        relative_bytes = relative.encode("utf-8")
        content = candidate.read_bytes()
        digest.update(len(relative_bytes).to_bytes(8, "big"))
        digest.update(relative_bytes)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _config_name_slug(config_name: Any) -> str:
    if not isinstance(config_name, str) or not config_name.strip():
        raise ValueError("config_name must be a non-empty string")
    if any(char in config_name for char in ("\r", "\n", "/", "\\")):
        raise ValueError("config_name must not contain newlines or path separators")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", config_name.strip())
    slug = slug.strip("._-")
    if not slug:
        raise ValueError("config_name has no filesystem-safe characters")
    return slug


def resolve_grade_output_path(
    config: dict,
    *,
    experiment_id: str,
    judge_slug: str,
    config_hash: str,
    rubric_sha: str,
    rubric_short_sha: str,
    prompt_version: str,
    inference_sha: str | None = None,
    grader_source_hash: str | None = None,
    diagnostic_task_scope_sha: str | None = None,
) -> Path:
    if not FULL_HF_SHA_RE.fullmatch(rubric_sha):
        raise ValueError(
            "rubric_sha must be a full 40-character lowercase HF commit SHA"
        )
    if not isinstance(inference_sha, str) or not FULL_HF_SHA_RE.fullmatch(
        inference_sha
    ):
        raise ValueError(
            "inference_sha must be a full 40-character lowercase HF commit SHA"
        )
    if not isinstance(grader_source_hash, str) or not FULL_SHA256_RE.fullmatch(
        grader_source_hash
    ):
        raise ValueError(
            "grader_source_hash must be a full 64-character lowercase SHA-256"
        )
    if (
        diagnostic_task_scope_sha is not None
        and not FULL_SHA256_RE.fullmatch(diagnostic_task_scope_sha)
    ):
        raise ValueError(
            "diagnostic_task_scope_sha must be a full lowercase SHA-256"
        )
    out_name = config["output"]["filename_template"].format(
        exp_id=experiment_id,
        judge_slug=judge_slug,
        config_name=_config_name_slug(config.get("config_name")),
        config_hash=config_hash,
        rubric_sha=rubric_sha,
        rubric_short_sha=rubric_short_sha,
        prompt_v=prompt_version,
        inference_sha=inference_sha or "",
        inference_short_sha=(inference_sha or "")[:7],
        grader_source_hash=grader_source_hash or "",
        grader_source_hash_short=(grader_source_hash or "")[:16],
    )
    if any(char in out_name for char in ("\r", "\n")) or Path(out_name).name != out_name:
        raise ValueError("formatted grade filename must be a single safe path component")
    output_root = Path(config["output"]["directory"])
    if diagnostic_task_scope_sha is not None:
        return (
            output_root
            / "_diagnostic"
            / diagnostic_task_scope_sha
            / out_name
        )
    return output_root / out_name


def _repo_relative_grade_file(out_path: Path) -> str:
    cwd = Path.cwd().resolve()
    repo_root = cwd.parent if cwd.name == "batch-runner" else cwd
    try:
        relative = out_path.resolve().relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("grade output path must remain inside the repository") from exc
    value = relative.as_posix()
    if not value or any(char in value for char in ("\r", "\n")):
        raise ValueError("grade output path is not safe for GITHUB_OUTPUT")
    return value


def _write_github_output(name: str, value: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("invalid GitHub output name")
    if any(char in value for char in ("\r", "\n")):
        raise ValueError("GitHub output value must be a single line")
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"{name}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rubric-based grading for one experiment")
    parser.add_argument("experiment_yaml_name", help="Experiment YAML name without .yaml")
    parser.add_argument("--config", required=True, help="Grading config path")
    parser.add_argument("--force", action="store_true", help="Overwrite if cache-key output exists")
    parser.add_argument("--dry-run", action="store_true", help="Only classify precheck vs judge")
    parser.add_argument("--tasks", help="Comma-separated task ids")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks")
    parser.add_argument("--source", choices=["local", "hf"], default="local")
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume an in-progress grade run. Reads any existing grade JSON at "
            "the templated output path, skips tasks whose task_id is already "
            "graded, and continues. Combined with the time guard (env "
            "GRADER_TIME_BUDGET_SEC, default 14400 = 4h), this lets a long "
            "grade run chunk itself across multiple GH Actions invocations. "
            "Exit code 7 is returned when the time budget is hit BEFORE "
            "completing all tasks; the caller (workflow) should re-invoke "
            "with --resume to continue from the partial."
        ),
    )
    parser.add_argument(
        "--source-experiment-id",
        default=None,
        help=(
            "Phase 2 source linkage: experiment_id of the inference run that "
            "produced the deliverables being graded. Defaults to "
            "experiment_yaml_name. Useful when the grade exp name diverges "
            "from the inference run directory (e.g. re-grading a renamed run)."
        ),
    )
    return parser.parse_args()


def validate_grading_config(config: dict) -> None:
    # PR2 task 208 — accept both schema 1.0 (legacy v1, text-extract path)
    # and 2.0 (v2 tool-calling path). The validator branches on the
    # presence of judge.tools.read_deliverable, not on the literal
    # version string, so user-authored v1 configs that forget to bump
    # schema_version still validate correctly.
    schema_version = config.get("schema_version")
    if schema_version not in ("1.0", "2.0"):
        raise ValueError("grading config schema_version must be '1.0' or '2.0'")

    required = [
        "schema_version",
        "config_name",
        "judge",
        "rubric",
        "prompt",
        "output",
    ]
    for key in required:
        if key not in config:
            raise ValueError(f"missing config key: {key}")

    judge = config.get("judge", {})
    for key in ["provider", "api", "model", "deployment"]:
        if key not in judge:
            raise ValueError(f"missing config key: judge.{key}")
    if "endpoint_env" in judge:
        raise ValueError(
            "judge.endpoint_env is deprecated; use typed Azure AI runtime env"
        )
    if judge["model"] != judge["deployment"]:
        raise ValueError("judge.model and judge.deployment must match")
    allowed_reasoning_efforts = {
        "none", "low", "medium", "high", "xhigh", "max"
    }
    reasoning = judge.get("reasoning", {})
    if not isinstance(reasoning, dict):
        raise ValueError("judge.reasoning must be an object")
    if (
        "effort" in reasoning
        and reasoning["effort"] not in allowed_reasoning_efforts
    ):
        raise ValueError("judge.reasoning.effort is invalid")
    generation = judge.get("generation", {})
    if not isinstance(generation, dict):
        raise ValueError("judge.generation must be an object")
    if (
        "finalization_reasoning_effort" in generation
        and generation["finalization_reasoning_effort"]
        not in allowed_reasoning_efforts
    ):
        raise ValueError(
            "judge.generation.finalization_reasoning_effort is invalid"
        )
    grader_route_workloads(config)

    # --- v2 tool-calling block (optional) ------------------------------
    tools = (judge.get("tools") or {})
    if tools:
        rd = tools.get("read_deliverable")
        if rd is None:
            raise ValueError(
                "judge.tools present but missing read_deliverable block"
            )
        ops = rd.get("ops")
        if not isinstance(ops, list) or not ops:
            raise ValueError(
                "judge.tools.read_deliverable.ops must be a non-empty list"
            )
        allowed_ops = {"inspect_structure", "read_content",
                       "inspect_formatting", "probe_audio", "probe_video"}
        if "render_to_image" in ops:
            raise ValueError(
                "judge.tools.read_deliverable.ops must not expose "
                "render_to_image; visual rendering is harness-owned"
            )
        bad = [op for op in ops if op not in allowed_ops]
        if bad:
            raise ValueError(
                f"judge.tools.read_deliverable.ops contains unknown ops: {bad}"
            )

    # --- v2 perception block (optional) --------------------------------
    perception = judge.get("perception", {})
    if not isinstance(perception, dict):
        raise ValueError("judge.perception must be an object")
    if perception:
        for sub in ("visual", "audio"):
            sub_cfg = perception.get(sub)
            if sub_cfg is None:
                continue
            if not isinstance(sub_cfg, dict):
                raise ValueError(
                    f"judge.perception.{sub} must be an object"
                )
            if not any(key in sub_cfg for key in ("model", "deployment")):
                raise ValueError(
                    f"judge.perception.{sub} present but missing model/deployment"
                )
        visual = perception.get("visual")
        if (
            isinstance(visual, dict)
            and "reasoning_effort" in visual
            and visual["reasoning_effort"] not in allowed_reasoning_efforts
        ):
            raise ValueError(
                "judge.perception.visual.reasoning_effort is invalid"
            )

    # --- v2 critical block (optional) ----------------------------------
    critical = (judge.get("critical") or {})
    if critical:
        rule = critical.get("rule")
        if rule not in (None, "abs_max_score_threshold"):
            raise ValueError(
                f"judge.critical.rule unknown: {rule!r}; "
                "expected 'abs_max_score_threshold'"
            )

    rubric = config.get("rubric", {})
    for key in ["repo_id", "revision", "cache_dir"]:
        if key not in rubric:
            raise ValueError(f"missing config key: rubric.{key}")

    prompt = config.get("prompt", {})
    if "template" not in prompt or "version" not in prompt:
        raise ValueError("missing config key: prompt.template/prompt.version")
    if not Path(prompt["template"]).exists():
        raise ValueError(f"prompt template not found: {prompt['template']}")
    # v2 configs MAY also set prompt.tool_template; if set, must exist.
    if "tool_template" in prompt and not Path(prompt["tool_template"]).exists():
        raise ValueError(
            f"prompt.tool_template not found: {prompt['tool_template']}"
        )

    output = config.get("output", {})
    if "directory" not in output or "filename_template" not in output:
        raise ValueError("missing config key: output.directory/output.filename_template")

    repo_id = str(rubric.get("repo_id", ""))
    if "/" not in repo_id:
        raise ValueError("rubric.repo_id must be owner/name format")

    if int(config.get("tpm_guard", {}).get("max_concurrent", 1)) < 1:
        raise ValueError("tpm_guard.max_concurrent must be >= 1")

    rerun_identity = config.get("rerun_identity")
    if rerun_identity is not None:
        if schema_version != "2.0" or not isinstance(rerun_identity, dict):
            raise ValueError("rerun_identity requires a schema 2.0 object")
        required_identity_fields = {
            "experiment_id",
            "expected_task_count",
            "rubric_commit_sha",
            "inference_revision",
        }
        if set(rerun_identity) != required_identity_fields:
            raise ValueError(
                "rerun_identity must contain exactly experiment_id, "
                "expected_task_count, rubric_commit_sha, and inference_revision"
            )
        experiment_id = rerun_identity["experiment_id"]
        if not isinstance(experiment_id, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", experiment_id
        ):
            raise ValueError("rerun_identity.experiment_id is invalid")
        expected_task_count = rerun_identity["expected_task_count"]
        if (
            type(expected_task_count) is not int
            or expected_task_count < 1
            or expected_task_count > 220
        ):
            raise ValueError("rerun_identity.expected_task_count is invalid")
        for field_name in ("rubric_commit_sha", "inference_revision"):
            value = rerun_identity[field_name]
            if not isinstance(value, str) or not FULL_HF_SHA_RE.fullmatch(value):
                raise ValueError(f"rerun_identity.{field_name} is invalid")
        if rubric["revision"] != rerun_identity["rubric_commit_sha"]:
            raise ValueError(
                "rubric.revision must match rerun_identity.rubric_commit_sha"
            )


def requires_track2_office_renderer(config: dict) -> bool:
    if config.get("schema_version") != "2.0":
        return False
    judge = config.get("judge")
    if not isinstance(judge, dict):
        return False
    tools = judge.get("tools")
    read_tool = tools.get("read_deliverable") if isinstance(tools, dict) else None
    perception = judge.get("perception")
    visual = perception.get("visual") if isinstance(perception, dict) else None
    visual_deployment = (
        canonical_deployment(visual, "judge.perception.visual")
        if isinstance(visual, dict)
        else None
    )
    return (
        isinstance(read_tool, dict)
        and isinstance(read_tool.get("ops"), list)
        and bool(read_tool["ops"])
        and isinstance(visual, dict)
        and bool(visual_deployment)
    )


def source_inference_repo_id(inference_results: dict, schema_version: str) -> str | None:
    value = inference_results.get("source_repo_id")
    if value is None and schema_version != "2.0":
        value = inference_results.get("source")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def source_inference_revision(inference_results: dict) -> str | None:
    value = inference_results.get("source_revision")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def resolve_source_inference_identity(
    inference_results: dict, schema_version: str
) -> tuple[str | None, str | None]:
    repo_id = source_inference_repo_id(inference_results, schema_version)
    revision = source_inference_revision(inference_results)
    if schema_version == "2.0":
        if repo_id is None or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*",
            repo_id,
        ):
            raise ValueError(
                "Track 2 source_repo_id must be a canonical owner/name"
            )
        if revision is None or not FULL_HF_SHA_RE.fullmatch(revision):
            raise ValueError(
                "Track 2 source_revision must be a full 40-character lowercase HF commit SHA"
            )
    return repo_id, revision


def _validate_grade_resume_identity(
    existing: dict,
    *,
    experiment_id: str,
    rubric_commit_sha: str,
    prompt_version: str,
    config_hash: str,
    source_inference_repo_id: str,
    source_inference_revision: str,
    grader_source_hash: str,
    renderer_fingerprint: dict[str, str] | None,
) -> None:
    checks = (
        ("schema_version", existing.get("schema_version"), SCHEMA_VERSION),
        ("experiment_id", existing.get("experiment_id"), experiment_id),
        (
            "rubric.commit_sha",
            (existing.get("rubric") or {}).get("commit_sha")
            if isinstance(existing.get("rubric"), dict) else None,
            rubric_commit_sha,
        ),
        (
            "prompt.version",
            (existing.get("prompt") or {}).get("version")
            if isinstance(existing.get("prompt"), dict) else None,
            prompt_version,
        ),
        (
            "judge.config_hash",
            (existing.get("judge") or {}).get("config_hash")
            if isinstance(existing.get("judge"), dict) else None,
            config_hash,
        ),
        (
            "source_inference_repo_id",
            existing.get("source_inference_repo_id"),
            source_inference_repo_id,
        ),
        (
            "source_inference_revision",
            existing.get("source_inference_revision"),
            source_inference_revision,
        ),
        (
            "grader_source_hash",
            existing.get("grader_source_hash"),
            grader_source_hash,
        ),
    )
    if renderer_fingerprint is not None:
        checks += ((
            "renderer_fingerprint",
            existing.get("renderer_fingerprint"),
            renderer_fingerprint,
        ),)
    for field_name, actual, expected in checks:
        if actual != expected:
            state = "missing" if actual is None else "mismatch"
            raise ValueError(
                f"Grade resume identity {state} for {field_name}: "
                f"existing={actual!r}, current={expected!r}"
            )


def _validate_pinned_rerun_identity(
    config: dict,
    *,
    experiment_id: str,
    task_count: int,
    rubric_commit_sha: str,
    inference_revision: str | None,
) -> None:
    identity = config.get("rerun_identity")
    if identity is None:
        return
    checks = (
        ("experiment_id", experiment_id, identity["experiment_id"]),
        ("task_count", task_count, identity["expected_task_count"]),
        (
            "rubric_commit_sha",
            rubric_commit_sha,
            identity["rubric_commit_sha"],
        ),
        (
            "inference_revision",
            inference_revision,
            identity["inference_revision"],
        ),
    )
    for field_name, actual, expected in checks:
        if actual != expected:
            raise ValueError(
                f"pinned rerun identity mismatch for {field_name}: "
                f"actual={actual!r}, expected={expected!r}"
            )


def _validate_azure_ai_resume_identity(
    existing: dict,
    azure_ai_routes: list[dict[str, str]],
    primary_runtime_fingerprint: str,
) -> None:
    actual = existing.get("azure_ai_routes")
    if actual != azure_ai_routes:
        state = "missing" if actual is None else "mismatch"
        raise ValueError(
            "Azure AI resume identity "
            f"{state} for azure_ai_routes: existing={actual!r}, "
            f"current={azure_ai_routes!r}"
        )
    actual_fingerprint = existing.get("azure_ai_runtime_fingerprint")
    if actual_fingerprint != primary_runtime_fingerprint:
        state = "missing" if actual_fingerprint is None else "mismatch"
        raise ValueError(
            "Azure AI resume identity "
            f"{state} for azure_ai_runtime_fingerprint: "
            f"existing={actual_fingerprint!r}, "
            f"current={primary_runtime_fingerprint!r}"
        )


def _load_existing_grade(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            existing = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not load existing grade JSON: {exc}") from exc
    if not isinstance(existing, dict):
        raise ValueError("top-level JSON must be an object")
    if not isinstance(existing.get("tasks"), list):
        raise ValueError("top-level tasks must be an array")
    return existing


def _task_ids(rows: list[dict], *, label: str) -> list[str]:
    task_ids: list[str] = []
    seen: set[str] = set()
    duplicates: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{label} task at index {index} must be an object")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(
                f"{label} task at index {index} has no non-empty task_id"
            )
        if task_id in seen:
            duplicates.add(task_id)
        seen.add(task_id)
        task_ids.append(task_id)
    if duplicates:
        raise ValueError(
            f"{label} contains duplicate task_ids: {sorted(duplicates)}"
        )
    return task_ids


def _validate_grade_task_set(
    existing: dict,
    expected_tasks: list[dict],
    *,
    require_complete: bool,
    complete_status: str = "final",
) -> set[str]:
    try:
        _validate_schema(existing)
    except (SchemaError, ValidationError) as exc:
        raise ValueError(
            f"existing grade schema validation failed: {exc.message}"
        ) from exc

    expected_ids = _task_ids(expected_tasks, label="current inference")
    existing_ids = _task_ids(existing["tasks"], label="existing grade")
    if complete_status not in {"final", "diagnostic"}:
        raise ValueError("complete grade status is invalid")
    expected_status = complete_status if require_complete else "partial"
    if existing.get("run_status") != expected_status:
        raise ValueError(
            f"existing grade run_status must be {expected_status!r}"
        )
    if existing.get("expected_task_count") != len(expected_ids):
        raise ValueError("existing grade expected task count mismatch")
    if existing.get("expected_ordered_task_ids_sha256") != (
        _ordered_task_ids_sha256(expected_ids)
    ):
        raise ValueError("existing grade expected task order mismatch")
    if require_complete:
        if existing_ids != expected_ids:
            raise ValueError("existing final grade task order is incomplete or mismatched")
    elif existing_ids != expected_ids[: len(existing_ids)]:
        raise ValueError("existing partial grade tasks are not an ordered prefix")
    runtime_errors = [
        (task["task_id"], error)
        for task in existing["tasks"]
        if (error := _track2_task_runtime_error(task)) is not None
    ]
    if runtime_errors:
        raise ValueError(
            f"existing grade contains runtime failures: {runtime_errors}"
        )
    if existing["summary"]["cost"].get("usage_complete") is not True:
        raise ValueError("existing grade has incomplete aggregate usage")
    return set(existing_ids)


def load_experiment_yaml(experiment_yaml_name: str) -> ExperimentConfig:
    path = Path("experiments") / f"{experiment_yaml_name}.yaml"
    return ExperimentConfig.from_yaml(str(path))


def load_local_inference_results() -> dict:
    path = Path("workspace") / "step2_inference_results.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    with open(path, "r", encoding="utf-8") as f:
        return canonicalize_inference_payload(json.load(f))


def filter_tasks(inference_results: dict, tasks_csv: str | None, limit: int) -> list[dict]:
    raw_tasks = inference_results.get("results")
    if not isinstance(raw_tasks, list):
        raise ValueError("inference results must contain a results array")
    source_ids = _task_ids(raw_tasks, label="inference results")
    if not source_ids:
        raise ValueError("inference results contain no tasks")
    if limit < 0:
        raise ValueError("--limit must be >= 0")

    tasks = list(raw_tasks)
    if tasks_csv is not None:
        requested = [part.strip() for part in tasks_csv.split(",") if part.strip()]
        if not requested:
            raise ValueError("--tasks must include at least one task_id")
        duplicate_requests = sorted({
            task_id for task_id in requested if requested.count(task_id) > 1
        })
        if duplicate_requests:
            raise ValueError(
                f"--tasks contains duplicate task_ids: {duplicate_requests}"
            )
        source_set = set(source_ids)
        missing = sorted(set(requested) - source_set)
        if missing:
            raise ValueError(f"--tasks requested unknown task_ids: {missing}")
        wanted = set(requested)
        tasks = [task for task in tasks if task["task_id"] in wanted]
    if limit > 0:
        tasks = tasks[:limit]
    return tasks


def _track2_task_runtime_error(task: dict) -> str | None:
    existing_error = task.get("error")
    if existing_error and existing_error not in {
        "all_items_score_excluded",
        "no_deliverables",
        "selection_error",
    }:
        return str(existing_error)

    items = task.get("items")
    if not isinstance(items, list):
        return "invalid_items"
    for item in items:
        if not isinstance(item, dict):
            return "invalid_item"
        if (
            item.get("verdict") == "judge_error"
            and item.get("score_excluded") is not True
        ):
            return "invalid_score_exclusion"

    if task.get("usage_complete") is not True:
        return "usage_incomplete"
    if any(item.get("usage_complete") is not True for item in items):
        return "usage_incomplete"
    return None


def resolve_deliverable_dir(task_result: dict) -> str:
    task_id = canonical_task_id(task_result.get("task_id"))
    return str(Path(os.path.abspath(
        task_deliverable_dir(Path("workspace") / "upload", task_id)
    )))


def _judge_slug(model: str) -> str:
    return model.replace(".", "_")


def _read_schema() -> dict:
    path = Path("schemas") / "grade.schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    temp_identity = hashlib.sha256(os.fsencode(path.name)).hexdigest()[:16]
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".grade-{temp_identity}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _ci_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(var)
    return 1.96 * std / math.sqrt(n)


def _task_to_dict(
    task_grade,
    *,
    grading_wall_time_ms: float | None = None,
) -> dict:
    data = asdict(task_grade)
    if grading_wall_time_ms is not None:
        if not math.isfinite(grading_wall_time_ms) or grading_wall_time_ms < 0:
            raise ValueError("grading wall time must be finite and nonnegative")
        data["grading_wall_time_ms"] = round(grading_wall_time_ms, 2)
    data["graded_at"] = _now_iso()
    return data


def _unpriced_models(config: dict) -> list[str]:
    judge = config["judge"]
    models = [canonical_deployment(judge, "judge")]
    perception = judge.get("perception", {}) or {}
    for modality_name, modality in perception.items():
        if isinstance(modality, dict):
            models.append(canonical_deployment(
                modality,
                f"judge.perception.{modality_name}",
            ))
    return sorted(set(models))


def _compute_summary(
    task_dicts: list[dict],
    *,
    unpriced_models: list[str] | None = None,
) -> dict:
    total = len(task_dicts)
    scored_tasks = [task for task in task_dicts if not task.get("error")]
    graded_tasks = len(scored_tasks)
    error_tasks = total - graded_tasks
    pcts = [float(task["pct"]) for task in scored_tasks]
    avg_pct = (sum(pcts) / len(pcts)) if pcts else None

    perfect = sum(1 for x in pcts if x >= 99.0)
    zero = sum(1 for x in pcts if x <= 1.0)
    partial = graded_tasks - perfect - zero

    pre_items = 0
    pre_pass = 0
    judge_items = 0
    judge_pass = 0
    judge_errors = 0
    critical_items = 0
    critical_pass = 0
    all_items = 0
    all_pass = 0

    main_calls = 0
    main_in_tok = 0
    main_out_tok = 0
    main_cached_tok = 0
    main_latency_ms = 0.0
    perception_calls = 0
    perception_in_tok = 0
    perception_out_tok = 0
    perception_cached_tok = 0
    perception_latency_ms = 0.0
    render_calls = 0
    render_latency_ms = 0.0
    usage_complete = True

    for task in task_dicts:
        main_calls += int(task.get("judge_call_count", 0))
        main_in_tok += int(task.get("judge_input_tokens", 0))
        main_out_tok += int(task.get("judge_output_tokens", 0))
        main_cached_tok += int(task.get("judge_cached_tokens", 0))
        main_latency_ms += float(task.get("judge_total_latency_ms", 0.0))
        perception_calls += int(task.get("perception_call_count", 0))
        perception_in_tok += int(task.get("perception_input_tokens", 0))
        perception_out_tok += int(task.get("perception_output_tokens", 0))
        perception_cached_tok += int(task.get("perception_cached_tokens", 0))
        perception_latency_ms += float(
            task.get("perception_total_latency_ms", 0.0)
        )
        render_calls += int(task.get("render_call_count", 0))
        render_latency_ms += float(task.get("render_total_latency_ms", 0.0))
        usage_complete = usage_complete and bool(
            task.get("usage_complete", True)
        )

        for item in task.get("items", []):
            score_excluded = bool(item.get("score_excluded", False))
            if not score_excluded:
                all_items += 1
                if item.get("verdict") == "pass":
                    all_pass += 1
            if item.get("decided_by") == "precheck":
                if not score_excluded:
                    pre_items += 1
                    if item.get("verdict") == "pass":
                        pre_pass += 1
            if item.get("decided_by") == "judge":
                judge_items += 1
                if item.get("verdict") == "pass" and not score_excluded:
                    judge_pass += 1
                if item.get("verdict") == "judge_error":
                    judge_errors += 1
            # PR1 task 101 — critical_item_pass_rate uses sign-aware
            # MAGNITUDE_THRESHOLD (|max_score| >= 4) and ItemGrade
            # .model_did_right (filled by core.grader._aggregate in
            # PR1 task 100), NOT raw `verdict == 'pass'`.
            #
            # The legacy `(max_score or 0) >= 3` here was both
            # wrong-threshold (project convention is 4) and wrong-sign
            # (negative penalty items were excluded entirely, and
            # 'pass' on a negative item meant the model violated).
            # See data/grades/_validation/SCORE_MATH_AUDIT.md.
            if (
                not score_excluded
                and _is_critical_item(item.get("max_score"))
            ):
                critical_items += 1
                if bool(item.get("model_did_right", False)):
                    critical_pass += 1

    return {
        "total_tasks": total,
        "graded_tasks": graded_tasks,
        "error_tasks": error_tasks,
        "openai_compat": {
            "avg_score_pct": round(avg_pct, 2) if avg_pct is not None else None,
            "ci_pct": round(_ci_pct(pcts), 2) if pcts else None,
            "perfect_count": perfect,
            "zero_count": zero,
            "partial_count": partial,
            "inconsistent_count": 0,
        },
        "wow": {
            "rubric_item_coverage_avg": round((all_pass / all_items) if all_items else 0.0, 4),
            "critical_item_pass_rate": round((critical_pass / critical_items) if critical_items else 0.0, 4),
            "precheck_pass_rate": round((pre_pass / pre_items) if pre_items else 0.0, 4),
            "judge_pass_rate": round((judge_pass / judge_items) if judge_items else 0.0, 4),
            "judge_error_rate": canonical_rate(judge_errors, judge_items),
            "by_sector": {},
            "by_rubric_category": {},
            "score_density_histogram": [],
            "rubric_severity_curve": [],
        },
        "cost": {
            "total_judge_calls": main_calls + perception_calls,
            "total_main_judge_calls": main_calls,
            "total_perception_calls": perception_calls,
            "total_input_tokens": main_in_tok + perception_in_tok,
            "total_output_tokens": main_out_tok + perception_out_tok,
            "total_cached_tokens": main_cached_tok + perception_cached_tok,
            "main_input_tokens": main_in_tok,
            "main_output_tokens": main_out_tok,
            "main_cached_tokens": main_cached_tok,
            "perception_input_tokens": perception_in_tok,
            "perception_output_tokens": perception_out_tok,
            "perception_cached_tokens": perception_cached_tok,
            "estimated_cost_usd": None,
            "pricing_complete": False,
            "unpriced_models": sorted(set(unpriced_models or [])),
            "total_judge_latency_sec": round(
                (main_latency_ms + perception_latency_ms) / 1000.0, 2
            ),
            "total_main_judge_latency_sec": round(
                main_latency_ms / 1000.0, 2
            ),
            "total_perception_latency_sec": round(
                perception_latency_ms / 1000.0, 2
            ),
            "total_render_calls": render_calls,
            "total_render_latency_sec": round(render_latency_ms / 1000.0, 2),
            "usage_complete": usage_complete,
        },
    }


def _resolve_inference_model(
    inf_results: dict, exp_config: ExperimentConfig | None
) -> str:
    """Return the deployment that actually produced the inference output.

    Priority:
      1. inf_results['model']  — what step2 (or HF reconstruct) recorded
      2. exp_config.condition_a.model.deployment — fallback to the
         experiment yaml (source of truth for the inference run)
      3. '' — defensive default

    Inference vs judge are different pipelines. Never fall back to
    config['judge']['model'] here — that would silently mislead the UI.
    """
    candidate = (inf_results.get("model") or "").strip()
    if candidate:
        return candidate
    if exp_config is not None:
        deployment = getattr(getattr(exp_config.condition_a, "model", None), "deployment", "")
        if deployment and str(deployment).strip():
            return str(deployment).strip()
    return ""


def _resolve_source_inference_run_dir(source_id: str) -> str | None:
    """Best-effort: return repo-relative path to the inference run directory.

    Returns ``"batch-runner/results/<source_id>"`` if that directory exists
    (relative to the current working directory of step8, which is the
    repo-root or batch-runner/). Otherwise None (debug-only field per spec).
    """
    if not source_id:
        return None
    candidate = Path("results") / source_id
    if candidate.exists():
        # step8 is invoked from inside batch-runner/, so prefix that segment
        # to produce a repo-root-relative path consistent with the spec.
        return f"batch-runner/results/{source_id}"
    return None


def _build_grade_payload(
    exp_name: str,
    inf_results: dict,
    config: dict,
    config_hash: str,
    loader: RubricLoader,
    prompt_version: str,
    task_dicts: list[dict],
    grader_source_hash: str,
    source_inference_repo_id: str | None,
    source_inference_revision: str | None,
    azure_ai_runtime_fingerprint: str,
    azure_ai_routes: list[dict[str, str]],
    run_status: str = "final",
    expected_task_ids: list[str] | None = None,
    exp_config: ExperimentConfig | None = None,
    source_experiment_id: str | None = None,
    renderer_fingerprint: dict[str, str] | None = None,
) -> dict:
    if run_status not in {"partial", "final", "diagnostic"}:
        raise ValueError("grade run_status is invalid")
    expected_ids = list(expected_task_ids or [row["task_id"] for row in task_dicts])
    expected_ids = [canonical_task_id(value) for value in expected_ids]
    if len(expected_ids) != len(set(expected_ids)):
        raise ValueError("expected grade task IDs must be unique")
    if re.fullmatch(r"[0-9a-f]{64}", azure_ai_runtime_fingerprint) is None:
        raise ValueError("primary grader runtime fingerprint is invalid")
    if (
        not azure_ai_routes
        or azure_ai_routes[0].get("workload") != "grader"
        or azure_ai_routes[0].get("runtime_fingerprint")
        != azure_ai_runtime_fingerprint
    ):
        raise ValueError("primary grader route identity is invalid")
    src_id = (source_experiment_id or exp_name or "").strip() or exp_name
    return {
        "schema_version": SCHEMA_VERSION,
        "run_status": run_status,
        "expected_task_count": len(expected_ids),
        "expected_ordered_task_ids_sha256": _ordered_task_ids_sha256(expected_ids),
        "experiment_id": exp_name,
        "experiment_yaml_name": exp_name,
        "source_inference_experiment_id": src_id,
        "source_inference_run_dir": _resolve_source_inference_run_dir(src_id),
        "source_inference_repo_id": source_inference_repo_id,
        "source_inference_revision": source_inference_revision,
        "source_azure_ai_routes": inf_results.get("azure_ai_routes", []),
        "source_azure_ai_provenance_status": inf_results.get(
            "azure_ai_provenance_status", "local-runtime"
        ),
        "azure_ai_routes": list(azure_ai_routes),
        "azure_ai_runtime_fingerprint": azure_ai_runtime_fingerprint,
        "grader_source_hash": grader_source_hash,
        "renderer_fingerprint": renderer_fingerprint,
        "inference_model": _resolve_inference_model(inf_results, exp_config),
        "inference_completed_at": inf_results.get("completed_at"),
        "judge": {
            "provider": config["judge"]["provider"],
            "api": config["judge"]["api"],
            "model": config["judge"]["model"],
            "deployment": config["judge"].get("deployment", config["judge"]["model"]),
            "api_version": config["judge"].get("api_version", ""),
            "reasoning_effort": config.get("judge", {}).get("reasoning", {}).get("effort", "high"),
            "temperature": config.get("judge", {}).get("generation", {}).get("temperature", 0),
            "seed": config.get("judge", {}).get("generation", {}).get("seed", 42),
            "perception": config.get("judge", {}).get("perception", {}),
            "config_name": config.get("config_name", "unknown"),
            "config_hash": config_hash,
        },
        "rubric": {
            "source": config.get("rubric", {}).get("source", "huggingface"),
            "repo_id": config["rubric"]["repo_id"],
            "revision": config["rubric"]["revision"],
            "commit_sha": loader.rubric_sha,
            "short_sha": loader.rubric_short_sha,
        },
        "prompt": {
            "template": config["prompt"]["template"],
            "version": prompt_version,
        },
        "graded_at": _now_iso(),
        "graded_by": "step8_grade.py",
        "graded_by_version": GRADED_BY_VERSION,
        "tasks": task_dicts,
        "summary": _compute_summary(
            task_dicts,
            unpriced_models=_unpriced_models(config),
        ),
    }


def _validate_schema(payload: dict) -> None:
    schema = _read_schema()
    validate_grade_payload(payload, schema)


def _print_dry_run_stats(tasks: list[dict], loader: RubricLoader) -> None:
    precheck = 0
    judge = 0
    for t in tasks:
        rubric = loader.load(t["task_id"])
        for item in rubric.rubric_items:
            mode, _ = Grader._classify(item)
            if mode == "precheck":
                precheck += 1
            else:
                judge += 1
    total = precheck + judge
    print(f"Dry-run tasks={len(tasks)} items={total} precheck={precheck} judge={judge}")


def main() -> int:
    args = parse_args()

    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_grading_config(config)
    config_hash = hash_config(str(config_path))

    try:
        exp_config = load_experiment_yaml(args.experiment_yaml_name)
    except Exception as exc:
        print(f"ERROR: experiment yaml load failed: {exc}", file=sys.stderr)
        return 1

    if args.source == "local":
        try:
            inf_results = load_local_inference_results()
        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: inference results unavailable or invalid: {exc}", file=sys.stderr)
            return 2
    else:
        print("ERROR: --source hf is not implemented in Phase A. Use scripts/download_inference_from_hf.py first.", file=sys.stderr)
        return 2

    try:
        inference_repo_id, inference_revision = resolve_source_inference_identity(
            inf_results, str(config.get("schema_version", ""))
        )
    except ValueError as exc:
        print(f"ERROR: inference identity validation failed: {exc}", file=sys.stderr)
        return 1

    try:
        grader_source_hash = compute_grader_source_hash(config_path, config)
    except (KeyError, OSError, ValueError) as exc:
        print(f"ERROR: grader source hash failed: {exc}", file=sys.stderr)
        return 1

    try:
        loader = RubricLoader(
            repo_id=config["rubric"]["repo_id"],
            revision=config["rubric"]["revision"],
            cache_dir=config["rubric"]["cache_dir"],
        )
        rubric_sha = loader.rubric_sha
        rubric_short_sha = loader.rubric_short_sha
    except Exception as exc:
        print(f"ERROR: rubric loader init failed: {exc}", file=sys.stderr)
        return 3

    judge_slug = _judge_slug(config["judge"]["model"])
    prompt_v = config["prompt"]["version"]
    try:
        tasks = filter_tasks(inf_results, args.tasks, args.limit)
    except ValueError as exc:
        print(f"ERROR: invalid grading task selection: {exc}", file=sys.stderr)
        return 1

    try:
        _validate_pinned_rerun_identity(
            config,
            experiment_id=args.experiment_yaml_name,
            task_count=len(tasks),
            rubric_commit_sha=rubric_sha,
            inference_revision=inference_revision,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    expected_task_ids = [task["task_id"] for task in tasks]
    source_provenance_status = inf_results.get(
        "azure_ai_provenance_status", "local-runtime"
    )
    diagnostic_run = (
        args.tasks is not None
        or args.limit > 0
        or source_provenance_status == "legacy-missing"
    )
    completed_run_status = "diagnostic" if diagnostic_run else "final"
    diagnostic_task_scope_sha = (
        _ordered_task_ids_sha256(expected_task_ids)
        if diagnostic_run
        else None
    )
    try:
        out_path = resolve_grade_output_path(
            config,
            experiment_id=args.experiment_yaml_name,
            judge_slug=judge_slug,
            config_hash=config_hash,
            rubric_sha=rubric_sha,
            rubric_short_sha=rubric_short_sha,
            prompt_version=prompt_v,
            inference_sha=inference_revision,
            grader_source_hash=grader_source_hash,
            diagnostic_task_scope_sha=diagnostic_task_scope_sha,
        )
        _write_github_output("grade_file", _repo_relative_grade_file(out_path))
        _write_github_output("grade_status", completed_run_status)
    except (KeyError, ValueError) as exc:
        print(f"ERROR: grade output path resolution failed: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        _print_dry_run_stats(tasks, loader)
        return 0

    try:
        azure_ai_routes = preflight_routes(
            grader_route_workloads(config),
            **grader_transport_options(config),
        )
        primary_runtime_fingerprint = azure_ai_routes[0][
            "runtime_fingerprint"
        ]
    except ValueError as exc:
        print(f"ERROR: Azure AI route validation failed: {exc}", file=sys.stderr)
        return 1
    try:
        tasks = validate_local_deliverables(
            tasks, Path("workspace") / "upload"
        )
    except ValueError as exc:
        print(f"ERROR: deliverable tree validation failed: {exc}", file=sys.stderr)
        return 1

    renderer_fingerprint: dict[str, str] | None = None
    renderer_required = requires_track2_office_renderer(config)
    if renderer_required:
        try:
            renderer_fingerprint = get_renderer_fingerprint()
        except ReadDeliverableError as exc:
            print(
                f"ERROR: Track 2 renderer fingerprint failed: {exc}",
                file=sys.stderr,
            )
            return 1

    if out_path.exists() and not args.force and not args.resume:
        try:
            existing = _load_existing_grade(out_path)
            _validate_azure_ai_resume_identity(
                existing,
                azure_ai_routes,
                primary_runtime_fingerprint,
            )
            _validate_grade_resume_identity(
                existing,
                experiment_id=args.experiment_yaml_name,
                rubric_commit_sha=rubric_sha,
                prompt_version=prompt_v,
                config_hash=config_hash,
                source_inference_repo_id=inference_repo_id,
                source_inference_revision=inference_revision,
                grader_source_hash=grader_source_hash,
                renderer_fingerprint=(
                    renderer_fingerprint if renderer_required else None
                ),
            )
            _validate_grade_task_set(
                existing,
                tasks,
                require_complete=True,
                complete_status=completed_run_status,
            )
        except ValueError as exc:
            print(f"ERROR: grade cache identity validation failed: {exc}", file=sys.stderr)
            return 1
        print(
            f"SKIP - exists: {out_path}. "
            "Use --force to overwrite or --resume to continue."
        )
        return 0

    if args.resume and not out_path.exists():
        print(
            f"ERROR: --resume partial not found at {out_path}; "
            "refusing to start a fresh paid run",
            file=sys.stderr,
        )
        return 1

    task_payloads: list[dict] = []
    completed_task_ids: set[str] = set()

    if args.resume and out_path.exists():
        try:
            existing = _load_existing_grade(out_path)
            existing_tasks = existing["tasks"]
            _validate_azure_ai_resume_identity(
                existing,
                azure_ai_routes,
                primary_runtime_fingerprint,
            )
        except ValueError as exc:
            print(
                f"ERROR: --resume could not load existing partial "
                f"{out_path}: {exc}",
                file=sys.stderr,
            )
            return 1

        try:
            _validate_grade_resume_identity(
                existing,
                experiment_id=args.experiment_yaml_name,
                rubric_commit_sha=loader.rubric_sha,
                prompt_version=prompt_v,
                config_hash=config_hash,
                source_inference_repo_id=inference_repo_id,
                source_inference_revision=inference_revision,
                grader_source_hash=grader_source_hash,
                renderer_fingerprint=(
                    renderer_fingerprint if renderer_required else None
                ),
            )
            completed_task_ids = _validate_grade_task_set(
                existing, tasks, require_complete=False
            )
        except ValueError as exc:
            print(f"ERROR: --resume {exc}", file=sys.stderr)
            return 1

        task_payloads = list(existing_tasks)
        print(
            f"[resume] loaded {len(completed_task_ids)} previously graded "
            f"tasks from {out_path}",
            file=sys.stderr,
        )

    try:
        config["_runtime"] = {
            "experiment_id": args.experiment_yaml_name,
            "rubric_sha": loader.rubric_sha,
            "azure_ai_runtime_fingerprint": primary_runtime_fingerprint,
        }
        grader = Grader(config=config, rubric_loader=loader)
    except BaseException as exc:
        print(
            "ERROR: judge initialization failed: "
            f"{public_provider_error_text(exc)}",
            file=sys.stderr,
        )
        return 4

    def close_grader() -> None:
        nonlocal grader
        active_grader = grader
        grader = None
        try:
            close = getattr(active_grader, "close", None)
            if callable(close):
                close()
        except BaseException as exc:
            print(
                "ERROR: judge cleanup failed: "
                f"{public_provider_error_text(exc)}",
                file=sys.stderr,
            )

    grader_exit_cleanup = atexit.register(close_grader)

    try:
        azure_ai_runtime_fingerprint = getattr(
            grader,
            "runtime_fingerprint",
            None,
        )
    except BaseException as exc:
        print(
            "ERROR: grader route verification failed: "
            f"{public_provider_error_text(exc)}",
            file=sys.stderr,
        )
        try:
            close_grader()
        finally:
            atexit.unregister(grader_exit_cleanup)
        return 4
    if azure_ai_runtime_fingerprint != primary_runtime_fingerprint:
        print(
            "ERROR: grader client route differs from preflight provenance",
            file=sys.stderr,
        )
        try:
            close_grader()
        finally:
            atexit.unregister(grader_exit_cleanup)
        return 4

    partial_every = int(config.get("output", {}).get("partial_save_every_n_tasks", 10))
    initial_completed_count = len(task_payloads)

    # Time guard: pre-empt GH Actions hard 6h limit. Default 4h (14400s)
    # leaves ~80 min for the workflow's retrigger + setup overhead and the
    # final partial save. Caller can override via env (e.g. shorter budgets
    # for tighter chunks, or longer for self-hosted runners).
    time_budget_sec = int(os.getenv("GRADER_TIME_BUDGET_SEC", "14400"))
    grade_loop_start = time.monotonic()
    GRADE_EXIT_RESUME = 7  # contract with grade-run.yml's auto-trigger step
    GRADE_EXIT_PERSISTENCE_FAILURE = 5
    GRADE_EXIT_RUNTIME_FAILURE = 6

    def finish(code: int) -> int:
        try:
            close_grader()
        finally:
            atexit.unregister(grader_exit_cleanup)
        return code

    for idx, task_result in enumerate(tasks, start=1):
        # Resume skip
        if task_result["task_id"] in completed_task_ids:
            continue

        # Time-budget pre-check (before starting an expensive judge call)
        elapsed_sec = time.monotonic() - grade_loop_start
        if time_budget_sec > 0 and elapsed_sec > time_budget_sec:
            graded_count = len(task_payloads)
            remaining = len(tasks) - graded_count
            if graded_count <= initial_completed_count:
                print(
                    "[time-guard] no new task completed in this chunk; "
                    "refusing to request another paid resume",
                    file=sys.stderr,
                )
                return finish(GRADE_EXIT_PERSISTENCE_FAILURE)
            print(
                f"\n[time-guard] elapsed {elapsed_sec/60:.1f}min > budget "
                f"{time_budget_sec/60:.0f}min; graded={graded_count}/{len(tasks)} "
                f"remaining={remaining}. Saving partial and requesting resume.",
                file=sys.stderr,
            )
            try:
                partial = _build_grade_payload(
                    args.experiment_yaml_name,
                    inf_results,
                    config,
                    config_hash,
                    loader,
                    grader.prompt_version,
                    task_payloads,
                    grader_source_hash,
                    inference_repo_id,
                    inference_revision,
                    azure_ai_runtime_fingerprint=azure_ai_runtime_fingerprint,
                    azure_ai_routes=azure_ai_routes,
                    run_status="partial",
                    expected_task_ids=expected_task_ids,
                    exp_config=exp_config,
                    source_experiment_id=args.source_experiment_id,
                    renderer_fingerprint=renderer_fingerprint,
                )
                _validate_schema(partial)
                _save_json(out_path, partial)
                persisted = _load_existing_grade(out_path)
                _validate_schema(persisted)
                if persisted != partial:
                    raise ValueError("persisted partial does not match payload")
                print(f"[time-guard] partial saved → {out_path}", file=sys.stderr)
            except Exception as save_exc:
                import traceback
                print(f"[time-guard] partial save FAILED: {save_exc}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                return finish(GRADE_EXIT_PERSISTENCE_FAILURE)
            return finish(GRADE_EXIT_RESUME)

        task = loader.load(task_result["task_id"])
        deliverable_dir = resolve_deliverable_dir(task_result)
        task_started = time.perf_counter()
        grade = grader.grade_task(task, deliverable_dir)
        grading_wall_time_ms = (time.perf_counter() - task_started) * 1000.0
        row = _task_to_dict(
            grade,
            grading_wall_time_ms=grading_wall_time_ms,
        )
        runtime_error = None
        if config.get("schema_version") == "2.0":
            runtime_error = _track2_task_runtime_error(row)
            if runtime_error is not None and not row.get("error"):
                row["error"] = runtime_error
        task_payloads.append(row)

        print(
            f"[{idx}/{len(tasks)}] {task.task_id[:8]} -> {grade.pct:.1f}% "
            f"({grade.total_awarded:.1f}/{grade.total_max})"
        )

        if runtime_error is not None:
            try:
                diagnostic = _build_grade_payload(
                    args.experiment_yaml_name,
                    inf_results,
                    config,
                    config_hash,
                    loader,
                    grader.prompt_version,
                    task_payloads,
                    grader_source_hash,
                    inference_repo_id,
                    inference_revision,
                    azure_ai_runtime_fingerprint=azure_ai_runtime_fingerprint,
                    azure_ai_routes=azure_ai_routes,
                    run_status="diagnostic",
                    expected_task_ids=expected_task_ids,
                    exp_config=exp_config,
                    source_experiment_id=args.source_experiment_id,
                    renderer_fingerprint=renderer_fingerprint,
                )
                _validate_schema(diagnostic)
                _save_json(out_path, diagnostic)
                persisted = _load_existing_grade(out_path)
                _validate_schema(persisted)
                if persisted != diagnostic:
                    raise ValueError("persisted diagnostic does not match payload")
            except Exception as save_exc:
                print(
                    f"ERROR: Track 2 runtime diagnostic save failed: {save_exc}",
                    file=sys.stderr,
                )
                return finish(GRADE_EXIT_PERSISTENCE_FAILURE)
            print(
                "ERROR: Track 2 grading stopped after runtime failure "
                f"for {task.task_id}: {runtime_error}",
                file=sys.stderr,
            )
            return finish(GRADE_EXIT_RUNTIME_FAILURE)

        if partial_every > 0 and idx % partial_every == 0:
            try:
                partial = _build_grade_payload(
                    args.experiment_yaml_name,
                    inf_results,
                    config,
                    config_hash,
                    loader,
                    grader.prompt_version,
                    task_payloads,
                    grader_source_hash,
                    inference_repo_id,
                    inference_revision,
                    azure_ai_runtime_fingerprint=azure_ai_runtime_fingerprint,
                    azure_ai_routes=azure_ai_routes,
                    run_status="partial",
                    expected_task_ids=expected_task_ids,
                    exp_config=exp_config,
                    source_experiment_id=args.source_experiment_id,
                    renderer_fingerprint=renderer_fingerprint,
                )
                _validate_schema(partial)
                _save_json(out_path, partial)
            except Exception as save_exc:
                import traceback
                print(
                    f"\n!! PARTIAL SAVE FAILED at idx={idx} task={task.task_id[:8]} !!",
                    file=sys.stderr,
                )
                print(
                    f"   Exception: {type(save_exc).__name__}: {save_exc}",
                    file=sys.stderr,
                )
                traceback.print_exc(file=sys.stderr)
                raise

    final = _build_grade_payload(
        args.experiment_yaml_name,
        inf_results,
        config,
        config_hash,
        loader,
        grader.prompt_version,
        task_payloads,
        grader_source_hash,
        inference_repo_id,
        inference_revision,
        azure_ai_runtime_fingerprint=azure_ai_runtime_fingerprint,
        azure_ai_routes=azure_ai_routes,
        run_status=completed_run_status,
        expected_task_ids=expected_task_ids,
        exp_config=exp_config,
        source_experiment_id=args.source_experiment_id,
        renderer_fingerprint=renderer_fingerprint,
    )
    _validate_schema(final)
    _save_json(out_path, final)

    avg = final["summary"]["openai_compat"]["avg_score_pct"]
    avg_text = "unscored" if avg is None else f"{avg:.2f}"
    print(
        f"Completed grading: tasks={len(task_payloads)}, "
        f"avg_pct={avg_text}, out={out_path}"
    )
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
