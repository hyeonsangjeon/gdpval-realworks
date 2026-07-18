#!/usr/bin/env python3
"""Step 2: Run Inference — Call LLM for each task, save results incrementally.

Resume behavior:
  - Find error/qa_failed tasks in step2_inference_progress.json and retry
  - Repeat up to resume_max_rounds times (YAML execution.resume_max_rounds)
  - Update successful tasks directly in progress.json (object replacement)
  - After all rounds complete, save final results to step2_inference_results.json

Input:
  - workspace/step1_tasks_prepared.json  (from Step 1)
  - workspace/step0_needs_files_manifest.json (from Step 0)

Output:
  - workspace/step2_inference_results.json   (final)
  - workspace/step2_inference_progress.json  (incremental, for resume)
  - workspace/upload/deliverable_files/<task_id>/  (generated files)

Usage:
    python step2_run_inference.py --condition condition_a
    python step2_run_inference.py --condition condition_a --no-resume
    python step2_run_inference.py --condition condition_a --mode subprocess  # CLI override
"""

import argparse
import gc
import hashlib
import json
import os
import psutil
import re
import stat
import sys
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from core.config import (
    BATCH_OUTPUT_DIR,
    WORKSPACE_DIR,
    UPLOAD_DIR,
    DELIVERABLE_DIR,
    DEFAULT_LOCAL_PATH,
    DEFAULT_TOKENS,
)
from core.agentic_authorization import task_request_sha256
from core.executor import TaskExecutor
from core.agentic_experiments import (
    AGENTIC_BASELINE_ID,
    AGENTIC_EXPERIMENT_IDS,
    agentic_condition_identity,
    validate_agentic_budget_for_experiment,
    validate_agentic_experiment_identity,
)
from core.execution_metrics import (
    add_counts,
    add_durations_ms,
    bounded_count,
    bounded_duration_ms,
)
from core.file_preview import generate_all_previews
from core.llm_client import create_provider_client, complete
from core.needs_files import NeedsFilesManifest
from core.audio_analyzer import analyze_audio_files, filter_audio_files
from core.video_analyzer import (
    analyze_video_files,
    filter_video_files,
    frame_backend_available,
)


# ── Constants ──────────────────────────────────────────────────────────────

RETRIABLE_STATUSES = {"error", "qa_failed", "pending"}

# Exit code convention
EXIT_CHECKPOINT = 42  # checkpoint saved, relay retrigger needed

# Cache of models that don't support temperature=0 (learned at runtime, reused in session)
_MODELS_NO_TEMPERATURE: set = set()

_METRIC_DURATION_FIELDS = (
    "task_wall_time_ms",
    "model_time_ms",
    "tool_time_ms",
    "verification_time_ms",
    "dependency_time_ms",
    "self_qa_time_ms",
    "orchestration_time_ms",
)
_METRIC_COUNT_FIELDS = (
    "execution_attempt_count",
    "sandbox_attempt_count",
    "tool_call_count",
    "self_qa_call_count",
    "job_run_count",
)


def _load_private_agentic_config(prepared: dict) -> dict:
    config_path = Path(prepared.get("config_path", "")).resolve()
    experiments_root = (Path(__file__).resolve().parent / "experiments").resolve()
    try:
        config_path.relative_to(experiments_root)
    except ValueError as exc:
        raise ValueError(
            "hardened execution requires a checked-in experiments/*.yaml config"
        ) from exc
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    raw_agentic = (raw_config.get("execution") or {}).get("agentic")
    if not isinstance(raw_agentic, dict):
        raise ValueError("execution.agentic must be present for hardened execution")
    return raw_agentic


# ── Preprocessor helper ───────────────────────────────────────────────────

def _run_preprocessors(
    condition: dict,
    abs_ref_files: list[str] | None,
    task_instruction: str,
    observations: Optional[list[dict]] = None,
) -> str:
    """Run preprocessors defined in condition YAML (e.g. audio_analyzer).

    Returns a prefix string to prepend to the task prompt.
    If no preprocessors are configured or none triggered, returns "".
    Preprocessor failure is non-fatal — returns "" so main execution continues.
    """
    preprocessors = condition.get("preprocessors", [])
    if not preprocessors:
        return ""

    results: list[str] = []

    for pp_cfg in preprocessors:
        pp_type = pp_cfg.get("type", "")
        trigger = pp_cfg.get("trigger", "")
        observation = {
            "type": pp_type or "unknown",
            "trigger": trigger or None,
            "status": "configured",
            "matched_file_count": 0,
            "matched_extensions": [],
        }

        if pp_type == "audio_analyzer":
            # Check trigger condition
            if trigger == "has_audio_files":
                audio_files = filter_audio_files(abs_ref_files)
                if not audio_files:
                    observation["status"] = "skipped_no_matching_files"
                    if observations is not None:
                        observations.append(observation)
                    continue
            else:
                audio_files = filter_audio_files(abs_ref_files)
                if not audio_files:
                    observation["status"] = "skipped_no_matching_files"
                    if observations is not None:
                        observations.append(observation)
                    continue
            observation["matched_file_count"] = len(audio_files)
            observation["matched_extensions"] = sorted({
                Path(path).suffix.lower() for path in audio_files
            })

            # Create a separate client for the preprocessor model
            pp_model = pp_cfg.get("model", {})
            pp_provider = pp_model.get("provider", "azure")
            pp_deployment = pp_model.get("deployment", "gpt-audio-1.5")
            pp_system = pp_cfg.get("system", "You are an audio analysis agent.")
            include_task = pp_cfg.get("include_task_instruction", False)
            observation["provider"] = pp_provider
            observation["model"] = pp_deployment

            try:
                pp_client = create_provider_client(pp_provider)
                analysis = analyze_audio_files(
                    client=pp_client,
                    model_deployment=pp_deployment,
                    system_prompt=pp_system,
                    audio_paths=audio_files,
                    task_instruction=task_instruction if include_task else None,
                )
                if analysis:
                    results.append(analysis)
                    observation.update({
                        "status": "success",
                        "analysis_chars": len(analysis),
                        "analysis_sha256": hashlib.sha256(
                            analysis.encode("utf-8")
                        ).hexdigest(),
                    })
                else:
                    observation["status"] = "empty_result"
            except Exception as exc:
                print(
                    f"      ⚠️  Preprocessor '{pp_type}' error (non-fatal): "
                    f"{type(exc).__name__}"
                )
                observation.update({
                    "status": "error",
                    "error_type": type(exc).__name__,
                })
            if observations is not None:
                observations.append(observation)
        elif pp_type == "video_analyzer":
            # Trigger: only run when video reference files are present.
            video_files = filter_video_files(abs_ref_files)
            if not video_files:
                observation["status"] = "skipped_no_matching_files"
                if observations is not None:
                    observations.append(observation)
                continue
            observation["matched_file_count"] = len(video_files)
            observation["matched_extensions"] = sorted({
                Path(path).suffix.lower() for path in video_files
            })

            pp_model = pp_cfg.get("model", {})
            pp_provider = pp_model.get("provider", "azure")
            pp_deployment = pp_model.get("deployment", "gpt-5.2")
            pp_system = pp_cfg.get("system", "You are a video analysis agent.")
            include_task = pp_cfg.get("include_task_instruction", False)
            observation["provider"] = pp_provider
            observation["model"] = pp_deployment

            # Optional frame-sampling overrides from YAML.
            frames_per_video = pp_cfg.get("frames_per_video", 8)
            max_total_frames = pp_cfg.get("max_total_frames", 24)
            frame_max_width = pp_cfg.get("frame_max_width", 768)
            frame_detail = pp_cfg.get("frame_detail", "auto")

            try:
                pp_client = create_provider_client(pp_provider)
                analysis = analyze_video_files(
                    client=pp_client,
                    model_deployment=pp_deployment,
                    system_prompt=pp_system,
                    video_paths=video_files,
                    task_instruction=task_instruction if include_task else None,
                    frames_per_video=frames_per_video,
                    max_total_frames=max_total_frames,
                    frame_max_width=frame_max_width,
                    frame_detail=frame_detail,
                )
                if analysis:
                    results.append(analysis)
                    observation.update({
                        "status": "success",
                        "analysis_chars": len(analysis),
                        "analysis_sha256": hashlib.sha256(
                            analysis.encode("utf-8")
                        ).hexdigest(),
                    })
                else:
                    observation["status"] = "empty_result"
            except Exception as exc:
                print(
                    f"      ⚠️  Preprocessor '{pp_type}' error (non-fatal): "
                    f"{type(exc).__name__}"
                )
                observation.update({
                    "status": "error",
                    "error_type": type(exc).__name__,
                })
            if observations is not None:
                observations.append(observation)
        else:
            print(f"      ⚠️  Unknown preprocessor type: '{pp_type}' — skipping")
            observation["status"] = "skipped_unknown_type"
            if observations is not None:
                observations.append(observation)

    return "\n\n".join(results)


def _build_execution_observability(
    result: Optional[dict],
    preprocessor_observations: list[dict],
) -> dict:
    """Build compact task provenance without duplicating heavy QA reports."""
    observability = {"preprocessors": preprocessor_observations}
    execution_metrics = _bounded_execution_metrics(
        (result or {}).get("execution_metrics")
    )
    if execution_metrics:
        observability["execution_metrics"] = execution_metrics
    agentic_metrics = _bounded_agentic_metrics((result or {}).get("agentic_metrics"))
    if agentic_metrics:
        observability["agentic_metrics"] = agentic_metrics
    budget_metrics = _bounded_budget_metrics((result or {}).get("budget_metrics"))
    if budget_metrics:
        observability["budget_metrics"] = budget_metrics
    substrate = _bounded_substrate_manifest(
        (result or {}).get("substrate_manifest")
    )
    if substrate:
        observability["substrate"] = substrate
    manifest = (result or {}).get("sandbox_manifest") or {}
    if manifest:
        attempts = []
        for attempt in manifest.get("attempts") or []:
            preflight = attempt.get("preflight")
            bounded_preflight = None
            if isinstance(preflight, dict):
                bounded_preflight = {
                    "ok": preflight.get("ok"),
                    "stage": preflight.get("stage"),
                    "error_type": preflight.get("error_type"),
                    "line": preflight.get("line"),
                    "offset": preflight.get("offset"),
                    "target_python": preflight.get("target_python"),
                }
            attempts.append({
                "attempt": attempt.get("attempt"),
                "status": attempt.get("status"),
                "executor": attempt.get("executor"),
                "prompt_sha256": attempt.get("prompt_sha256"),
                "code_sha256": attempt.get("code_sha256"),
                "llm_latency_ms": attempt.get("llm_latency_ms"),
                "usage": attempt.get("usage"),
                "blocking_error_count": attempt.get("blocking_error_count", 0),
                "blocking_error_categories": (
                    attempt.get("blocking_error_categories") or []
                ),
                "generated_artifact_count": len(
                    attempt.get("generated_artifacts") or []
                ),
                "stdout": attempt.get("stdout"),
                "stderr": attempt.get("stderr"),
                "response": attempt.get("response"),
                "preflight": bounded_preflight,
                "error_category": attempt.get("error_category"),
            })
        observability["sandbox"] = {
            "schema_version": manifest.get("schema_version"),
            "backend": manifest.get("sandbox_backend"),
            "image": manifest.get("sandbox_image"),
            "run_context": manifest.get("run_context") or {},
            "selected_skills": manifest.get("selected_skills_detail") or [],
            "attempts": attempts,
            "best_attempt": manifest.get("best_attempt"),
            "final_status": manifest.get("final_status"),
        }
    return observability


def _bounded_agentic_metrics(raw: Optional[dict]) -> Optional[dict]:
    """Allow only bounded aggregate tool-loop metrics into persisted output."""
    if not isinstance(raw, dict):
        return None
    output = {
        "schema_version": "1.0",
        "ledger_cumulative": raw.get("ledger_cumulative") is True,
        "model_api_calls": bounded_count(raw.get("model_api_calls")),
        "model_iterations": bounded_count(raw.get("model_iterations")),
        "tool_calls": bounded_count(raw.get("tool_calls")),
        "tool_errors": bounded_count(raw.get("tool_errors")),
        "model_time_ms": bounded_duration_ms(raw.get("model_time_ms")),
        "tool_time_ms": bounded_duration_ms(raw.get("tool_time_ms")),
        "task_wall_time_ms": bounded_duration_ms(raw.get("task_wall_time_ms")),
        "time_to_valid_artifact_ms": bounded_duration_ms(
            raw.get("time_to_valid_artifact_ms")
        ),
        "finalize_required_corrections": bounded_count(
            raw.get("finalize_required_corrections")
        ),
        "finalize_attempts": bounded_count(raw.get("finalize_attempts")),
        "capability_misses": bounded_count(raw.get("capability_misses")),
        "recovered_after_tool_error": raw.get("recovered_after_tool_error") is True,
        "input_tokens": bounded_count(raw.get("input_tokens")),
        "output_tokens": bounded_count(raw.get("output_tokens")),
        "cached_tokens": bounded_count(raw.get("cached_tokens")),
        "usage_complete": raw.get("usage_complete") is True,
        "terminal_error_category": (
            str(raw.get("terminal_error_category"))[:80]
            if raw.get("terminal_error_category")
            else None
        ),
    }
    calls_by_name = raw.get("tool_calls_by_name")
    if isinstance(calls_by_name, dict):
        output["tool_calls_by_name"] = {
            name: bounded_count(calls_by_name.get(name))
            for name in (
                "inspect_workspace", "inspect_environment", "run_python",
                "run_ffmpeg", "inspect_artifacts", "finalize",
            )
            if bounded_count(calls_by_name.get(name)) is not None
        }
    try:
        cost = float(raw.get("conservative_cost_usd", 0))
    except (TypeError, ValueError):
        cost = -1
    if 0 <= cost < float("inf"):
        output["conservative_cost_usd"] = round(cost, 8)
    bounded = {key: value for key, value in output.items() if value is not None}
    bounded["terminal_error_category"] = output["terminal_error_category"]
    return bounded


def _bounded_budget_metrics(raw: Optional[dict]) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    output = {
        "schema_version": "1.0",
        "model_api_calls": bounded_count(raw.get("model_api_calls")),
        "input_tokens": bounded_count(raw.get("input_tokens")),
        "output_tokens": bounded_count(raw.get("output_tokens")),
        "cached_tokens": bounded_count(raw.get("cached_tokens")),
        "usage_complete": raw.get("usage_complete") is True,
        "time_to_valid_artifact_ms": bounded_duration_ms(
            raw.get("time_to_valid_artifact_ms")
        ),
    }
    try:
        cost = float(raw.get("conservative_cost_usd", 0))
    except (TypeError, ValueError):
        return None
    if not 0 <= cost < float("inf"):
        return None
    output["conservative_cost_usd"] = round(cost, 8)
    return {
        key: value for key, value in output.items() if value is not None
    }


def _bounded_substrate_manifest(raw: Optional[dict]) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    hash_pattern = re.compile(r"^[0-9a-f]{64}$")
    if hash_pattern.fullmatch(str(raw.get("sha256", ""))) is None:
        return None
    component_names = (
        "python_launcher", "ffmpeg_mapper", "verifier", "outer_seccomp",
        "capabilities", "core_tree",
    )
    raw_components = raw.get("component_sha256")
    if not isinstance(raw_components, dict):
        return None
    components = {
        name: value
        for name in component_names
        if isinstance((value := raw_components.get(name)), str)
        and hash_pattern.fullmatch(value)
    }
    if set(components) != set(component_names):
        return None
    output = {
        "schema_version": "1.0",
        "sha256": raw["sha256"],
        "task_image": str(raw.get("task_image", ""))[:300],
        "task_image_id": str(raw.get("task_image_id", ""))[:100],
        "verifier_image": str(raw.get("verifier_image", ""))[:300],
        "verifier_image_id": str(raw.get("verifier_image_id", ""))[:100],
        "component_sha256": components,
        "sbom_sha256": str(raw.get("sbom_sha256", ""))[:64],
        "uid": bounded_count(raw.get("uid")),
        "gid": bounded_count(raw.get("gid")),
        "network": raw.get("network"),
        "ipc": raw.get("ipc"),
        "pid_namespace": raw.get("pid_namespace"),
        "read_only_rootfs": raw.get("read_only_rootfs") is True,
        "cap_drop": ["ALL"] if raw.get("cap_drop") == ["ALL"] else [],
        "no_new_privileges": raw.get("no_new_privileges") is True,
        "selected_transfer_bytes": _bounded_resource_integer(
            raw.get("selected_transfer_bytes"), 512 * 1024 * 1024
        ),
        "memory_bytes": _bounded_resource_integer(
            raw.get("memory_bytes"), 16 * 1024 * 1024 * 1024
        ),
        "memory_swap_bytes": _bounded_resource_integer(
            raw.get("memory_swap_bytes"), 16 * 1024 * 1024 * 1024
        ),
        "pids": bounded_count(raw.get("pids")),
        "nofile": bounded_count(raw.get("nofile")),
        "apparmor_profile": str(raw.get("apparmor_profile", ""))[:100],
    }
    cpus = raw.get("cpus")
    if isinstance(cpus, (int, float)) and not isinstance(cpus, bool) and 0 < cpus <= 2:
        output["cpus"] = float(cpus)
    work = raw.get("work_tmpfs")
    if isinstance(work, dict):
        output["work_tmpfs"] = {
            "size_bytes": _bounded_resource_integer(
                work.get("size_bytes"), 2 * 1024 * 1024 * 1024
            ),
            "nr_inodes": bounded_count(work.get("nr_inodes")),
            "nosuid": work.get("nosuid") is True,
            "nodev": work.get("nodev") is True,
            "noexec": work.get("noexec") is True,
        }
    return output


def _bounded_resource_integer(value, maximum: int) -> Optional[int]:
    if type(value) is not int or not 0 <= value <= maximum:
        return None
    return value


def _merge_agentic_metrics(
    previous: Optional[dict], current: Optional[dict]
) -> Optional[dict]:
    previous = _bounded_agentic_metrics(previous)
    current = _bounded_agentic_metrics(current)
    if not previous:
        return current
    if not current:
        return previous
    ledger_cumulative = current.get("ledger_cumulative") is True
    merged = {
        "schema_version": "1.0",
        "ledger_cumulative": ledger_cumulative,
    }
    for key in ("model_api_calls", "input_tokens", "output_tokens"):
        if ledger_cumulative:
            merged[key] = max(
                previous.get(key, 0) or 0,
                current.get(key, 0) or 0,
            )
        else:
            combined = add_counts(
                previous.get(key, 0) or 0,
                current.get(key, 0) or 0,
            )
            if combined is None:
                return current
            merged[key] = combined
    for key in (
        "model_iterations", "tool_calls", "tool_errors",
        "finalize_required_corrections", "finalize_attempts",
        "capability_misses", "cached_tokens",
    ):
        combined = add_counts(
            previous.get(key, 0) or 0,
            current.get(key, 0) or 0,
        )
        if combined is None:
            return current
        merged[key] = combined
    for key in ("model_time_ms", "tool_time_ms", "task_wall_time_ms"):
        combined = add_durations_ms(
            previous.get(key, 0) or 0,
            current.get(key, 0) or 0,
        )
        if combined is None:
            return current
        merged[key] = combined
    merged["time_to_valid_artifact_ms"] = (
        previous.get("time_to_valid_artifact_ms")
        if previous.get("time_to_valid_artifact_ms") is not None
        else current.get("time_to_valid_artifact_ms")
    )
    tool_names = (
        "inspect_workspace", "inspect_environment", "run_python",
        "run_ffmpeg", "inspect_artifacts", "finalize",
    )
    previous_calls = previous.get("tool_calls_by_name") or {}
    current_calls = current.get("tool_calls_by_name") or {}
    merged["tool_calls_by_name"] = {}
    for name in tool_names:
        combined = add_counts(
            previous_calls.get(name, 0) or 0,
            current_calls.get(name, 0) or 0,
        )
        if combined:
            merged["tool_calls_by_name"][name] = combined
    merged["usage_complete"] = (
        previous.get("usage_complete") is True
        and current.get("usage_complete") is True
    )
    merged["recovered_after_tool_error"] = (
        previous.get("recovered_after_tool_error") is True
        or current.get("recovered_after_tool_error") is True
        or (
            (previous.get("tool_errors", 0) or 0) > 0
            and not current.get("terminal_error_category")
        )
    )
    merged["terminal_error_category"] = current.get(
        "terminal_error_category"
    )
    merged["conservative_cost_usd"] = max(
        float(previous.get("conservative_cost_usd", 0) or 0),
        float(current.get("conservative_cost_usd", 0) or 0),
    )
    return _bounded_agentic_metrics(merged) or current


def _bounded_execution_metrics(raw: Optional[dict]) -> Optional[dict]:
    """Keep only finite, non-negative execution metrics and stable counters."""
    if not isinstance(raw, dict):
        return None

    bounded = {"schema_version": "1.0"}
    for key in (*_METRIC_DURATION_FIELDS, "time_to_valid_artifact_ms"):
        value = raw.get(key)
        if value is None and key == "time_to_valid_artifact_ms":
            bounded[key] = None
            continue
        parsed = bounded_duration_ms(value)
        if parsed is not None:
            bounded[key] = parsed

    for key in (*_METRIC_COUNT_FIELDS, "attempt_count"):
        parsed = bounded_count(raw.get(key))
        if parsed is not None:
            bounded[key] = parsed

    validated_artifact_count = bounded_count(raw.get("validated_artifact_count"))
    if validated_artifact_count is not None:
        bounded["validated_artifact_count"] = validated_artifact_count

    wall_time = bounded.get("task_wall_time_ms")
    if wall_time is None:
        return None
    valid_time = bounded.get("time_to_valid_artifact_ms")
    if valid_time is not None and valid_time > wall_time:
        bounded["time_to_valid_artifact_ms"] = None

    return bounded if len(bounded) > 1 else None


def _merge_execution_metrics(previous: Optional[dict], current: Optional[dict]) -> Optional[dict]:
    """Combine opt-in metrics when a resume round replaces an earlier result."""
    previous = _bounded_execution_metrics(previous)
    current = _bounded_execution_metrics(current)
    if not previous:
        return current
    if not current:
        return previous

    merged = {
        "schema_version": current.get("schema_version", previous["schema_version"]),
    }
    for key in _METRIC_DURATION_FIELDS:
        combined = add_durations_ms(
            previous.get(key, 0) or 0,
            current.get(key, 0) or 0,
        )
        if combined is None:
            return current
        merged[key] = combined
    for key in _METRIC_COUNT_FIELDS:
        combined = add_counts(
            previous.get(key, 0) or 0,
            current.get(key, 0) or 0,
        )
        if combined is None:
            return current
        merged[key] = combined

    merged["validated_artifact_count"] = max(
        previous.get("validated_artifact_count", 0) or 0,
        current.get("validated_artifact_count", 0) or 0,
    )

    previous_valid = previous.get("time_to_valid_artifact_ms")
    current_valid = current.get("time_to_valid_artifact_ms")
    if previous_valid is not None:
        merged["time_to_valid_artifact_ms"] = previous_valid
    elif current_valid is not None:
        merged_valid = add_durations_ms(
            previous.get("task_wall_time_ms", 0) or 0,
            current_valid,
        )
        if merged_valid is None:
            return current
        merged["time_to_valid_artifact_ms"] = merged_valid
    else:
        merged["time_to_valid_artifact_ms"] = None
    return _bounded_execution_metrics(merged) or current


# ── JSON extraction helper ─────────────────────────────────────────────────


def _resolve_token_limit(tokens_cfg: dict, key: str, default: int) -> int:
    """Get positive int token limit from config with safe fallback."""
    if not isinstance(tokens_cfg, dict):
        return default
    value = tokens_cfg.get(key)
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _extract_json_from_response(raw: str) -> dict:
    """Extract JSON from LLM response with multiple fallback strategies.

    Tries:
      0. Strip <think>...</think> tags (reasoning models)
      1. Direct JSON parse
      2. ```json ... ``` code fence extraction
      3. First balanced { ... } block extraction
      4. Truncated JSON repair (close open strings/brackets/braces)
      5. Regex extraction of essential fields (score, passed)

    Raises:
        ValueError: if all strategies fail
    """
    if not raw or not raw.strip():
        raise ValueError("Empty response")

    text = raw.strip()

    # Strategy 0: Remove <think>...</think> tags (reasoning models like o1, gpt-5)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: ```json code fence
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if json_match:
        candidate = json_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            repaired = _try_repair_truncated_json(candidate)
            if repaired is not None:
                return repaired

    # Strategy 3: First balanced { ... } block (brace-depth matching)
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = None  # try next { block

    # Strategy 4: Truncated JSON repair
    brace_start = text.find('{')
    if brace_start >= 0:
        repaired = _try_repair_truncated_json(text[brace_start:])
        if repaired is not None:
            return repaired

    # Strategy 5: Regex extraction of essential fields
    essential = _extract_essential_fields(text)
    if essential is not None:
        return essential

    raise ValueError(f"No JSON found in response: {text[:100]}")


def _try_repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair a truncated JSON string.

    Common case: LLM QA response cut off mid-JSON due to max_tokens.
    Returns parsed dict on success, None on failure.
    """
    if not text or '{' not in text:
        return None

    # Already valid?
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy A: Track state and truncate at last safe comma
    in_string = False
    escape = False
    last_comma = -1
    depth_brace = 0
    depth_bracket = 0

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            depth_brace += 1
        elif ch == '}':
            depth_brace -= 1
        elif ch == '[':
            depth_bracket += 1
        elif ch == ']':
            depth_bracket -= 1
        elif ch == ',':
            last_comma = i

    # If all brackets are balanced, try closing open strings
    if depth_brace == 0 and depth_bracket == 0:
        attempt = text
        if attempt.count('"') % 2 == 1:
            attempt += '"'
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            pass

    # Truncate at last comma (removes incomplete trailing value)
    if last_comma > 0:
        truncated = text[:last_comma]
        # Recount open structures after truncation
        ob = truncated.count('[') - truncated.count(']')
        oc = truncated.count('{') - truncated.count('}')
        truncated += ']' * max(0, ob) + '}' * max(0, oc)
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    # Strategy B: Brute-force close from end
    attempt = text
    if attempt.count('"') % 2 == 1:
        attempt += '"'
    attempt += ']' * max(0, attempt.count('[') - attempt.count(']'))
    attempt += '}' * max(0, attempt.count('{') - attempt.count('}'))
    try:
        result = json.loads(attempt)
        result.setdefault("passed", result.get("score", 0) >= 6)
        result.setdefault("score", 5)
        result.setdefault("issues", [])
        result.setdefault("suggestion", "")
        return result
    except json.JSONDecodeError:
        pass

    # Strategy C: Regex fallback
    return _extract_essential_fields(text)


def _extract_essential_fields(text: str) -> dict | None:
    """Fallback to extract only essential fields via regex when JSON parsing completely fails."""
    score_match = re.search(r'"score"\s*:\s*(\d+)', text)
    passed_match = re.search(r'"passed"\s*:\s*(true|false)', text, re.IGNORECASE)

    if score_match:
        score = int(score_match.group(1))
        if passed_match:
            passed = passed_match.group(1).lower() == "true"
        else:
            passed = score >= 6

        # Attempt to extract issues field
        issues = []
        issues_match = re.search(r'"issues"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if issues_match:
            issues = re.findall(r'"([^"]+)"', issues_match.group(1))

        return {
            "passed": passed,
            "score": score,
            "issues": issues,
            "suggestion": "",
        }

    return None


# ── Self-QA: LLM inspects its own output ────────────────────────────────────


def _run_self_qa(
    task_info: dict,
    condition: dict,
    deliverable_text: str,
    deliverable_files: list,
    client,
    qa_max_tokens: int = DEFAULT_TOKENS["qa_check"],
) -> dict:
    """
    LLM acts as QA inspector and evaluates the output.

    Returns:
        {
            "passed": bool | None,  # None = undetermined (parse/API failure)
            "score": int | None,    # None = undetermined
            "issues": [...],
            "suggestion": str,
            "undetermined": bool,   # True = QA verdict undetermined
        }
    """
    qa_cfg = condition.get("qa", {})
    if not qa_cfg.get("enabled", False):
        return {"passed": True, "score": 10, "issues": [], "suggestion": "", "undetermined": False}

    qa_prompt_template = qa_cfg.get("prompt", "")
    if not qa_prompt_template:
        return {"passed": True, "score": 10, "issues": [], "suggestion": "", "undetermined": False}

    # Build QA prompt from template
    # Generate actual file previews from deliverable_files paths
    file_preview_text = ""
    if deliverable_files:
        try:
            abs_paths = []
            for fp in deliverable_files:
                abs_path = UPLOAD_DIR / fp
                if abs_path.exists():
                    abs_paths.append(str(abs_path))
            if abs_paths:
                preview = generate_all_previews(abs_paths)
                if preview:
                    # Limit file preview to 3000 chars (prevent QA context bloat)
                    if len(preview) > 3000:
                        preview = preview[:3000] + "\n... (truncated)"
                    file_preview_text = (
                        "\n\n## Actual File Content Preview\n"
                        "(Generated from the real files on disk)\n"
                        f"{preview}"
                    )
        except Exception as e:
            print(f"  ⚠️  File preview for QA failed: {e}")

    qa_prompt = qa_prompt_template.format(
        instruction=task_info.get("instruction", "")[:3000],
        deliverable_text=(deliverable_text or "")[:2000],
        deliverable_files=json.dumps(deliverable_files),
    )
    # Append file preview after the template-formatted prompt
    qa_prompt += file_preview_text

    model_cfg = condition["model"]
    qa_model = qa_cfg.get("model") or model_cfg["deployment"]
    min_score = qa_cfg.get("min_score", 6)

    qa_messages = [
        {"role": "system", "content": (
            "You are a strict QA inspector for professional deliverables.\n"
            "You MUST respond with ONLY a valid JSON object.\n"
            "No markdown, no code fences, no explanation before or after.\n"
            "No <think> tags. No reasoning. ONLY the JSON.\n"
            "Do NOT wrap your response in ```json``` blocks.\n"
            "\n"
            "IMPORTANT: Keep your response SHORT to avoid truncation.\n"
            "Each issue should be ONE brief sentence (max 15 words).\n"
            "Maximum 3 issues. Suggestion should be ONE sentence.\n"
            "\n"
            "Required format (exactly this structure):\n"
            '{"passed": true, "score": 8, "issues": [], "suggestion": ""}\n'
            "\n"
            "score: integer 1-10\n"
            "issues: list of max 3 short strings\n"
            "suggestion: one short string"
        )},
        {"role": "user", "content": qa_prompt},
    ]

    try:
        # Check temperature=0 support via cache (prevents repeated exceptions)
        if qa_model in _MODELS_NO_TEMPERATURE:
            response, _ = complete(client, qa_model, qa_messages,
                                   max_completion_tokens=qa_max_tokens)
        else:
            try:
                response, _ = complete(client, qa_model, qa_messages,
                                       temperature=0,
                                       max_completion_tokens=qa_max_tokens)
            except Exception as temp_err:
                if "temperature" in str(temp_err).lower():
                    _MODELS_NO_TEMPERATURE.add(qa_model)
                    print(f"  ℹ️  {qa_model} doesn't support temperature=0 (cached for session)")
                    response, _ = complete(client, qa_model, qa_messages,
                                           max_completion_tokens=qa_max_tokens)
                else:
                    raise

        # Check finish_reason — detect truncated responses
        finish_reason = getattr(response.choices[0], "finish_reason", None)
        if finish_reason == "length":
            print("  ⚠️  QA response truncated (finish_reason=length)")

        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            print("  ⚠️  QA returned empty response")
            return {
                "passed": None, "score": None,
                "issues": ["QA returned empty response"],
                "suggestion": "", "undetermined": True,
            }

        try:
            result = _extract_json_from_response(raw)
        except (json.JSONDecodeError, ValueError) as parse_err:
            print(f"  ⚠️  QA JSON parse failed: {parse_err}")
            print(f"     Raw response ({len(raw)} chars): {repr(raw[:300])}")
            return {
                "passed": None, "score": None,
                "issues": [f"QA parse error: {str(parse_err)}"],
                "suggestion": "", "undetermined": True,
                "raw_response": raw[:500],
            }

        score = result.get("score", 10)
        llm_passed = result.get("passed", True)
        passed = score >= min_score

        return {
            "passed": passed,
            "score": score,
            "llm_passed": llm_passed,
            "issues": result.get("issues", []),
            "suggestion": result.get("suggestion", ""),
            "undetermined": False,
        }

    except Exception as e:
        print(f"  ⚠️  QA API call failed: {e}")
        return {
            "passed": None, "score": None,
            "issues": [f"QA API error: {str(e)}"],
            "suggestion": "", "undetermined": True,
        }


# ── File saving (matches main.py _save_files) ─────────────────────────────


def _save_files(files: List[dict], task_id: str) -> List[str]:
    """Save generated files to workspace/upload/deliverable_files/<task_id>/."""
    if not files:
        return []
    if (
        not isinstance(task_id, str)
        or not task_id
        or task_id in {".", ".."}
        or task_id.startswith(".")
        or "/" in task_id
        or "\\" in task_id
        or len(task_id.encode("utf-8")) > 240
    ):
        raise ValueError("deliverable task ID is invalid")

    DELIVERABLE_DIR.mkdir(parents=True, exist_ok=True)
    root_metadata = DELIVERABLE_DIR.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("deliverable root is not a directory")
    output_dir = DELIVERABLE_DIR / task_id
    output_dir.mkdir(mode=0o700, exist_ok=True)
    output_metadata = output_dir.lstat()
    if not stat.S_ISDIR(output_metadata.st_mode):
        raise ValueError("deliverable task path is not a directory")

    prepared = []
    seen: set[str] = set()
    for file_data in files:
        if not isinstance(file_data, dict) or set(file_data) != {"filename", "content"}:
            raise ValueError("deliverable file record is invalid")
        filename = file_data["filename"]
        if not isinstance(filename, str) or "\\" in filename:
            raise ValueError("deliverable filename is invalid")
        relative = Path(filename)
        canonical = relative.as_posix()
        if (
            relative.is_absolute()
            or not relative.parts
            or canonical != filename
            or ".." in relative.parts
            or any(part.startswith(".") for part in relative.parts)
            or len(relative.parts) > 16
            or len(canonical.encode("utf-8")) > 240
            or canonical in seen
        ):
            raise ValueError("deliverable filename is invalid or duplicated")
        content = file_data["content"]
        if isinstance(content, str):
            encoded = content.encode("utf-8")
        elif isinstance(content, bytes):
            encoded = content
        else:
            raise ValueError("deliverable content must be bytes or text")
        seen.add(canonical)
        prepared.append((relative, encoded))

    saved_paths = []
    for relative, content in prepared:
        parent = output_dir
        for part in relative.parts[:-1]:
            parent /= part
            parent.mkdir(mode=0o700, exist_ok=True)
            metadata = parent.lstat()
            if not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("deliverable parent is not a directory")
        filepath = output_dir / relative
        if filepath.exists() or filepath.is_symlink():
            metadata = filepath.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError("deliverable target is not a single-link file")
        descriptor = os.open(
            filepath,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)

        try:
            rel_path = filepath.relative_to(UPLOAD_DIR)
            saved_paths.append(str(rel_path))
        except ValueError:
            saved_paths.append(str(filepath))

    return saved_paths


def _save_hardened_failure_evidence(
    files: List[dict],
    *,
    experiment_id: str,
    run_id: str,
    condition_identity: str,
    task_id: str,
) -> dict:
    import shutil
    import tempfile

    if not files or not all(
        isinstance(value, str) and value
        for value in (experiment_id, run_id, condition_identity, task_id)
    ):
        raise ValueError("failure evidence identity is invalid")
    for value in (experiment_id, condition_identity):
        if (
            value in {".", ".."}
            or value.startswith(".")
            or "/" in value
            or "\\" in value
            or any(ord(character) < 32 for character in value)
        ):
            raise ValueError("failure evidence identity is not canonical")
    run_component = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    task_component = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
    parent = (
        BATCH_OUTPUT_DIR
        / "agentic-sandbox"
        / experiment_id
        / run_component
        / condition_identity
        / "failed-evidence"
    )
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = parent / task_component
    if destination.exists() or destination.is_symlink():
        raise ValueError("failure evidence already exists")
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=parent))
    records = []
    try:
        seen = set()
        for file_data in files:
            if (
                not isinstance(file_data, dict)
                or set(file_data) != {"filename", "content"}
            ):
                raise ValueError("failure evidence file record is invalid")
            filename = file_data["filename"]
            relative = Path(filename) if isinstance(filename, str) else Path()
            if (
                not isinstance(filename, str)
                or "\\" in filename
                or relative.is_absolute()
                or not relative.parts
                or relative.as_posix() != filename
                or ".." in relative.parts
                or any(part.startswith(".") for part in relative.parts)
                or len(relative.parts) > 16
                or len(filename.encode("utf-8")) > 240
                or filename in seen
            ):
                raise ValueError("failure evidence filename is invalid")
            content = file_data["content"]
            if isinstance(content, str):
                content = content.encode("utf-8")
            if not isinstance(content, bytes):
                raise ValueError("failure evidence content is invalid")
            seen.add(filename)
            target = staging / "artifacts" / relative
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.write_bytes(content)
            target.chmod(0o600)
            records.append({
                "path": filename,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
        records.sort(key=lambda item: item["path"].encode("utf-8"))
        evidence_sha256 = hashlib.sha256(json.dumps(
            records, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")).hexdigest()
        manifest = {
            "schema_version": "agentic-failure-evidence-v1",
            "experiment_id": experiment_id,
            "run_id_sha256": run_component,
            "condition_identity": condition_identity,
            "task_id_sha256": task_component,
            "artifact_count": len(records),
            "artifacts": records,
            "sha256": evidence_sha256,
        }
        metadata_dir = staging / ".evidence"
        metadata_dir.mkdir(mode=0o700)
        (metadata_dir / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for record in records:
            persisted = staging / "artifacts" / record["path"]
            if (
                persisted.stat().st_size != record["size_bytes"]
                or hashlib.sha256(persisted.read_bytes()).hexdigest()
                != record["sha256"]
            ):
                raise ValueError("failure evidence persistence hash mismatch")
        os.replace(staging, destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "schema_version": "agentic-failure-evidence-v1",
        "artifact_count": len(records),
        "sha256": evidence_sha256,
        "root": destination.relative_to(BATCH_OUTPUT_DIR.parent).as_posix(),
    }


# ── Reflection prompt builder ─────────────────────────────────────────────


def _build_reflection_prompt(
    attempt_num: int,
    qa_score: int,
    qa_issues: list,
    qa_suggestion: str,
    previous_deliverable_text: str,
    min_score: int,
) -> str:
    """Build a structured reflection prompt for QA retry.

    Transforms raw QA feedback into an actionable critique the LLM
    can use to genuinely improve its next attempt.

    Args:
        attempt_num: Current attempt number (1-based, so 2 = first retry)
        qa_score: QA score from previous attempt (0-10)
        qa_issues: List of specific issues identified by QA
        qa_suggestion: Improvement suggestion from QA
        previous_deliverable_text: Summary of what the previous attempt produced
                                   (first 500 chars of deliverable_text)
        min_score: Minimum passing score threshold

    Returns:
        Structured reflection context string to prepend to the retry instruction
    """
    issues_formatted = "\n".join(
        f"  {i+1}. {issue}" for i, issue in enumerate(qa_issues)
    ) if qa_issues else "  (No specific issues recorded)"

    prev_summary = (previous_deliverable_text or "")[:500].strip()
    if len(previous_deliverable_text or "") > 500:
        prev_summary += "... (truncated)"

    return (
        f"[REFLECTION — Attempt {attempt_num} | Previous score: {qa_score}/10 "
        f"(target: {min_score}/10)]\n"
        f"\n"
        f"Your previous attempt was reviewed by a QA inspector. "
        f"Here is the structured critique:\n"
        f"\n"
        f"## What you produced (previous attempt)\n"
        f"{prev_summary}\n"
        f"\n"
        f"## Issues identified\n"
        f"{issues_formatted}\n"
        f"\n"
        f"## Improvement suggestion\n"
        f"  {qa_suggestion or 'Address the issues listed above.'}\n"
        f"\n"
        f"## Your task for this attempt\n"
        f"Carefully review each issue above and produce an improved version "
        f"that directly addresses all identified weaknesses. "
        f"Do not simply regenerate the same output — make targeted, specific improvements.\n"
        f"\n"
        f"{'='*60}\n"
        f"ORIGINAL TASK:\n"
    )


# ── Single task execution ──────────────────────────────────────────────────


def _execute_single_task(
    task_info: dict,
    condition: dict,
    executor,
    execution_mode: str,
    client,
    model: str,
    manifest: Optional[NeedsFilesManifest] = None,
    error_context: Optional[str] = None,
    verbose: bool = False,
    run_id: Optional[str] = None,
    condition_name: Optional[str] = None,
    strict_inputs: bool = False,
    experiment_id: Optional[str] = None,
) -> dict:
    """Execute a single task and return result dict."""
    task_id = task_info["task_id"]

    # Build prompt
    instruction = task_info["instruction"]
    prompt_cfg = condition["prompt"]
    # system_prompt: only used directly by legacy mode.
    # For code_interpreter/subprocess, codegen YAML's occupation persona takes priority
    # (experiment_prompt["system"] is ignored by render_prompt when codegen YAML has system_message).
    system_prompt = prompt_cfg.get("system", "You are a helpful assistant.")

    experiment_prompt = {
        "system": system_prompt,  # ignored by render_prompt when codegen YAML has system_message
        "prefix": prompt_cfg.get("prefix"),
        "body": prompt_cfg.get("body"),
        "suffix": prompt_cfg.get("suffix"),
    }

    if execution_mode in ("legacy",):
        # Legacy mode doesn't use render_prompt(), so assemble instruction here
        if prompt_cfg.get("prefix"):
            instruction = prompt_cfg["prefix"] + "\n" + instruction
        if prompt_cfg.get("body"):
            instruction = instruction + "\n" + prompt_cfg["body"]
        if prompt_cfg.get("suffix"):
            instruction = instruction + "\n" + prompt_cfg["suffix"]

    # Inject error context for retry
    if error_context:
        if "no deliverable files" in error_context.lower():
            # Keep existing no-files feedback unchanged
            instruction += (
                "\n\n[RETRY - PREVIOUS ATTEMPT FAILED]\n"
                "Your previous attempt did NOT produce any downloadable files.\n"
                "The task requires actual file deliverables, not just a text description.\n"
                "You MUST execute Python code to create and save the required file(s)\n"
                "(e.g., use python-docx for .docx, openpyxl for .xlsx, "
                "reportlab for .pdf, python-pptx for .pptx).\n"
                "Do NOT just describe the deliverable — actually generate the file."
            )
        elif error_context.startswith("[REFLECTION"):
            # Reflection retry: structured critique — prepend before instruction
            # (the reflection prompt already ends with "ORIGINAL TASK:\n")
            instruction = error_context + instruction
        else:
            # Infrastructure error retry: append error details after instruction
            instruction += (
                "\n\n[RETRY - PREVIOUS ATTEMPT FAILED]\n"
                "The previous code generation produced the following error:\n"
                "---\n"
                f"{error_context}\n"
                "---\n"
                "Please analyze the error above and generate corrected code "
                "that avoids this issue."
            )

    # Resolve reference file paths to absolute + validate existence
    abs_ref_files = None
    ref_files = task_info.get("reference_files", [])
    missing_ref_files = []
    if ref_files:
        if strict_inputs:
            abs_ref_files = list(ref_files)
        else:
            abs_ref_files = []
            for ref_path in ref_files:
                abs_path = DEFAULT_LOCAL_PATH / ref_path
                if abs_path.exists():
                    abs_ref_files.append(str(abs_path))
                else:
                    missing_ref_files.append(ref_path)
                    print(f"      ⚠️  Reference file not found: {abs_path}")
            if not abs_ref_files:
                abs_ref_files = None  # all missing → treat as no files
    if strict_inputs and missing_ref_files:
        return {
            "task_id": task_id,
            "status": "error",
            "error": "approved_reference_input_missing",
            "content": None,
            "deliverable_text": None,
            "deliverable_files": [],
            "model": model,
            "usage": None,
            "observability": _build_execution_observability(None, []),
            "latency_ms": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Preprocessor: enrich prompt with audio/video analysis (if configured) ──
    preprocessor_observations: list[dict] = []
    preprocessor_prefix = _run_preprocessors(
        condition,
        abs_ref_files,
        instruction,
        observations=preprocessor_observations,
    )
    perception_text = None
    if preprocessor_prefix:
        if execution_mode in {"sandbox", "agentic_sandbox"}:
            # Sandbox owns perception PLACEMENT via its `perception_analysis` spec
            # section (prompts/sandbox_occupation_codegen.yaml), so pass the block
            # through rather than prepending it here. This is byte-equivalent to the
            # prepend (perception is the outermost prefix before the task either way)
            # while making the section spec-controllable.
            perception_text = preprocessor_prefix
        else:
            instruction = preprocessor_prefix + "\n\n" + instruction
        print(f"      🎵 Preprocessor injected {len(preprocessor_prefix)} chars into prompt")

    try:
        start = time.time()

        if execution_mode == "legacy":
            response, latency_ms = complete(
                client,
                model,
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": instruction},
                ],
            )
            content = response.choices[0].message.content
            return {
                "task_id": task_id,
                "status": "success",
                "content": content,
                "deliverable_text": content,
                "deliverable_files": [],
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                "observability": _build_execution_observability(
                    None, preprocessor_observations
                ),
                "latency_ms": round(latency_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Executor mode (code_interpreter / subprocess / json_renderer)
        result = executor.execute(
            task_prompt=instruction,
            model=model,
            reference_files=abs_ref_files,
            occupation=task_info.get("occupation", "professional"),
            experiment_prompt=experiment_prompt,
            verbose=verbose,
            perception_text=perception_text,
            run_id=run_id,
            condition_name=condition_name,
            task_id=task_id,
        )
        latency_ms = (time.time() - start) * 1000

        if result["success"]:
            deliverable_text = (
                result.get("deliverable_text", "") or result.get("text", "")
            )
            deliverable_files = _save_files(
                result.get("files", []), task_id
            )

            # needs_files gate
            needs_files = task_info.get("needs_files", False)
            if manifest:
                needs_files = manifest.needs_files(task_id)

            if needs_files and not deliverable_files:
                return {
                    "task_id": task_id,
                    "status": "error",
                    "error": "needs_files=True but no deliverable files produced",
                    "content": result.get("text"),
                    "deliverable_text": deliverable_text,
                    "deliverable_files": [],
                    "model": model,
                    "usage": None,
                    "observability": _build_execution_observability(
                        result, preprocessor_observations
                    ),
                    "latency_ms": round(latency_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            return {
                "task_id": task_id,
                "status": "success",
                "content": result["text"],
                "deliverable_text": deliverable_text,
                "deliverable_files": deliverable_files,
                "model": model,
                "usage": None,
                "observability": _build_execution_observability(
                    result, preprocessor_observations
                ),
                "latency_ms": round(latency_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            failure_evidence = None
            if strict_inputs and result.get("files"):
                try:
                    failure_evidence = _save_hardened_failure_evidence(
                        result["files"],
                        experiment_id=experiment_id or "",
                        run_id=run_id or "",
                        condition_identity=condition_name or "",
                        task_id=task_id,
                    )
                except Exception as exc:
                    return {
                        "task_id": task_id,
                        "status": "error",
                        "error": f"failed_evidence_persistence_failed:{exc}",
                        "content": result.get("text"),
                        "deliverable_text": result.get("deliverable_text"),
                        "deliverable_files": [],
                        "model": model,
                        "usage": None,
                        "observability": _build_execution_observability(
                            result, preprocessor_observations
                        ),
                        "latency_ms": round(latency_ms, 2),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            return {
                "task_id": task_id,
                "status": "error",
                "error": result.get("error", "Unknown error"),
                "content": result.get("text"),
                "deliverable_text": result.get("deliverable_text"),
                "deliverable_files": [],
                "failure_evidence": failure_evidence,
                "model": model,
                "usage": None,
                "observability": _build_execution_observability(
                    result, preprocessor_observations
                ),
                "latency_ms": round(latency_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        return {
            "task_id": task_id,
            "status": "error",
            "error": str(e),
            "content": None,
            "deliverable_text": None,
            "deliverable_files": [],
            "model": model,
            "usage": None,
            "observability": _build_execution_observability(
                None, preprocessor_observations
            ),
            "latency_ms": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── Incremental save ──────────────────────────────────────────────────────


def _save_progress(
    experiment_id: str,
    condition_name: str,
    execution_mode: str,
    total_tasks: int,
    results: List[dict],
    started_at: str,
    path: Path,
    *,
    run_id: str,
    condition_identity: str,
    ordered_task_ids: List[str],
    resume_round: int = 0,
) -> None:
    """Atomic incremental save."""
    _validate_result_task_set(
        results, ordered_task_ids, allow_missing=True
    )
    success = sum(1 for r in results if r.get("status") == "success")
    error = sum(1 for r in results if r.get("status") == "error")

    data = {
        "schema_version": "step2-progress-v2",
        "experiment_id": experiment_id,
        "condition": condition_name,
        "condition_identity": condition_identity,
        "run_id": run_id,
        "execution_mode": execution_mode,
        "ordered_task_ids": ordered_task_ids,
        "total_tasks": total_tasks,
        "started_at": started_at,
        "resume_round": resume_round,
        "summary": {
            "total": total_tasks,
            "completed": len(results),
            "success": success,
            "error": error,
        },
        "results": results,
    }

    tmp_path = path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
        )
    tmp_path.rename(path)


def _load_and_validate_progress(
    path: Path,
    *,
    experiment_id: str,
    condition_name: str,
    condition_identity: str,
    run_id: str,
    execution_mode: str,
    ordered_task_ids: List[str],
) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        progress = json.load(stream)
    if not isinstance(progress, dict):
        raise ValueError("progress checkpoint must be an object")
    expected_identity = {
        "schema_version": "step2-progress-v2",
        "experiment_id": experiment_id,
        "condition": condition_name,
        "condition_identity": condition_identity,
        "run_id": run_id,
        "execution_mode": execution_mode,
        "ordered_task_ids": ordered_task_ids,
        "total_tasks": len(ordered_task_ids),
    }
    if any(progress.get(key) != value for key, value in expected_identity.items()):
        raise ValueError("progress checkpoint identity mismatch")
    results = progress.get("results")
    if not isinstance(results, list):
        raise ValueError("progress checkpoint results must be a list")
    _validate_result_task_set(results, ordered_task_ids, allow_missing=True)
    indexed = {result["task_id"]: result for result in results}
    timestamp = datetime.now(timezone.utc).isoformat()
    progress["results"] = [
        indexed.get(task_id, {
            "task_id": task_id,
            "status": "pending",
            "error": "checkpoint_missing_task",
            "timestamp": timestamp,
        })
        for task_id in ordered_task_ids
    ]
    return progress


def _validate_result_task_set(
    results: List[dict],
    ordered_task_ids: List[str],
    *,
    allow_missing: bool,
) -> None:
    if (
        not ordered_task_ids
        or len(ordered_task_ids) != len(set(ordered_task_ids))
        or any(not isinstance(task_id, str) or not task_id for task_id in ordered_task_ids)
    ):
        raise ValueError("ordered task identity is invalid")
    result_ids = []
    for result in results:
        if not isinstance(result, dict) or not isinstance(result.get("task_id"), str):
            raise ValueError("progress result task identity is invalid")
        result_ids.append(result["task_id"])
    if len(result_ids) != len(set(result_ids)):
        raise ValueError("progress checkpoint contains duplicate task IDs")
    if not set(result_ids) <= set(ordered_task_ids):
        raise ValueError("progress checkpoint contains unexpected task IDs")
    if not allow_missing and result_ids != ordered_task_ids:
        raise ValueError("final result task IDs differ from ordered task set")


# ── Progress helpers ───────────────────────────────────────────────────────


def _get_failed_task_ids(progress: dict) -> list:
    """progress.json에서 retriable status 태스크 추출."""
    failed = []
    for r in progress.get("results", []):
        if r.get("status") in RETRIABLE_STATUSES:
            failed.append({
                "task_id": r["task_id"],
                "status": r["status"],
                "error": r.get("error", ""),
            })
    return failed


def _update_progress_result(progress: dict, new_result: dict) -> dict:
    """progress.json results에서 task_id 일치하는 오브젝트를 교체."""
    updated = []
    replaced = False
    for r in progress.get("results", []):
        if r["task_id"] == new_result["task_id"]:
            previous_metrics = (r.get("observability") or {}).get("execution_metrics")
            current_metrics = (new_result.get("observability") or {}).get("execution_metrics")
            merged_metrics = _merge_execution_metrics(previous_metrics, current_metrics)
            if merged_metrics:
                new_result.setdefault("observability", {})["execution_metrics"] = merged_metrics
            previous_agentic = (r.get("observability") or {}).get(
                "agentic_metrics"
            )
            current_agentic = (new_result.get("observability") or {}).get(
                "agentic_metrics"
            )
            merged_agentic = _merge_agentic_metrics(
                previous_agentic, current_agentic
            )
            if merged_agentic:
                new_result.setdefault("observability", {})[
                    "agentic_metrics"
                ] = merged_agentic
            updated.append(new_result)
            replaced = True
        else:
            updated.append(r)
    if not replaced:
        updated.append(new_result)
    progress["results"] = updated
    return progress


# ── Main inference loop ───────────────────────────────────────────────────


def run_inference(
    execution_mode: str = None,
    max_retries: int = None,
    resume: bool = True,
    condition_key: str = "condition_a",
    resume_max_rounds: int = None,
    verbose: bool = False,
    wall_timeout: int = None,
):
    """Run inference for all prepared tasks with multi-round resume.

    Args:
        wall_timeout: Wall-clock timeout in minutes. When reached, remaining
            tasks are saved as 'pending' and the process exits with code 42
            for relay retrigger. None or 0 = no timeout.

    Resume rounds automatically re-execute failed tasks from progress.json,
    replacing the error objects in-place on success.
    """

    # 1. Load prepared tasks
    prepared_path = WORKSPACE_DIR / "step1_tasks_prepared.json"
    if not prepared_path.exists():
        print(f"❌ {prepared_path} not found. Run step1_prepare_tasks.sh first.")
        sys.exit(1)

    with open(prepared_path, "r", encoding="utf-8") as f:
        prepared = json.load(f)

    tasks = prepared["tasks"]
    condition = prepared[condition_key]
    if condition is None:
        print(f"❌ {condition_key} not found in config")
        sys.exit(1)

    experiment_id = prepared["experiment_id"]
    ordered_task_ids = [task["task_id"] for task in tasks]
    if (
        any(not isinstance(task_id, str) or not task_id for task_id in ordered_task_ids)
        or len(ordered_task_ids) != len(set(ordered_task_ids))
    ):
        print("❌ prepared task set contains invalid or duplicate task IDs")
        sys.exit(1)
    model = condition["model"]["deployment"]
    condition_name = condition["name"]

    # Resolve settings: CLI override > YAML execution block > defaults
    execution_cfg = prepared.get("execution", {})
    timeout = execution_cfg.get("timeout")  # None = config.py 기본값 사용
    configured_execution_mode = execution_cfg.get(
        "mode", prepared.get("execution_mode", "subprocess")
    )
    if execution_mode is None:
        execution_mode = configured_execution_mode
    if max_retries is None:
        max_retries = execution_cfg.get("max_retries", prepared.get("max_retries", 3))
    if resume_max_rounds is None:
        resume_max_rounds = execution_cfg.get("resume_max_rounds", 3)
    tokens_cfg_raw = execution_cfg.get("tokens", {})
    tokens_cfg = {
        "code_generation": _resolve_token_limit(
            tokens_cfg_raw, "code_generation", DEFAULT_TOKENS["code_generation"]
        ),
        "qa_check": _resolve_token_limit(
            tokens_cfg_raw, "qa_check", DEFAULT_TOKENS["qa_check"]
        ),
        "json_render": _resolve_token_limit(
            tokens_cfg_raw, "json_render", DEFAULT_TOKENS["json_render"]
        ),
    }
    # Sandbox-mode settings (execution.sandbox block in the experiment YAML).
    sandbox_options = execution_cfg.get("sandbox", {}) or {}
    agentic_options = execution_cfg.get("agentic", {}) or {}
    hardened_requested = (
        execution_mode == "agentic_sandbox"
        or (
            execution_mode == "sandbox"
            and sandbox_options.get("hardened_substrate") is True
        )
    )
    if experiment_id in AGENTIC_EXPERIMENT_IDS:
        expected_mode = (
            "sandbox" if experiment_id == AGENTIC_BASELINE_ID
            else "agentic_sandbox"
        )
        expected_hardened = experiment_id == AGENTIC_BASELINE_ID
        if (
            configured_execution_mode != expected_mode
            or execution_mode != expected_mode
            or (
                expected_hardened
                and sandbox_options.get("hardened_substrate") is not True
            )
            or (
                not expected_hardened
                and sandbox_options.get("hardened_substrate") is True
            )
        ):
            print("❌ reserved agentic experiment mode cannot be overridden")
            sys.exit(1)
    if hardened_requested:
        try:
            validate_agentic_experiment_identity(
                experiment_id,
                execution_mode,
                hardened_baseline=(
                    execution_mode == "sandbox"
                    and sandbox_options.get("hardened_substrate") is True
                ),
            )
            agentic_options = _load_private_agentic_config(prepared)
            validate_agentic_budget_for_experiment(
                experiment_id, agentic_options.get("budget")
            )
            if condition_key != "condition_a" or prepared.get("condition_b") is not None:
                raise ValueError(
                    "reserved hardened experiments require exactly condition_a"
                )
            prompt_config = condition.get("prompt") or {}
            if prompt_config.get("prefix") or prompt_config.get("body"):
                raise ValueError(
                    "hardened paired execution does not support prompt prefix/body"
                )
        except Exception as exc:
            print("❌ failed to reload hardened execution config")
            print(f"   {exc}")
            sys.exit(1)
        if max_retries != 0 or resume_max_rounds != 0:
            print(
                "❌ hardened execution fixes max_retries=0 and "
                "resume_max_rounds=0 until all task resource caps are durable"
            )
            sys.exit(1)
    execution_condition = (
        agentic_condition_identity(experiment_id)
        if hardened_requested
        else condition_key
    )
    metrics_cfg_raw = execution_cfg.get("metrics")
    metrics_cfg = metrics_cfg_raw if isinstance(metrics_cfg_raw, dict) else {}
    metrics_enabled = metrics_cfg.get("enabled") is True

    print(f"\n{'='*60}")
    print("🚀 Step 2: Run Inference")
    print(f"{'='*60}")
    print(f"   Experiment:         {experiment_id}")
    print(f"   Condition:          {condition_name}")
    print(f"   Model:              {model}")
    print(f"   Mode:               {execution_mode}")
    print(f"   Tasks:              {len(tasks)}")
    print(f"   Max retries:        {max_retries} (per task, infra)")
    print(f"   Resume max rounds:  {resume_max_rounds} (re-run failed tasks)")
    print(f"   Tokens:             code={tokens_cfg['code_generation']}, "
          f"qa={tokens_cfg['qa_check']}, render={tokens_cfg['json_render']}")
    if timeout:
        print(f"   Timeout:            {timeout}s (YAML override)")
    if metrics_enabled:
        print("   Job metrics:        enabled (optional execution_metrics v1.0)")
    reasoning_effort_display = condition.get("model", {}).get("reasoning_effort")
    if reasoning_effort_display:
        print(f"   Reasoning effort:   {reasoning_effort_display}")

    # Preflight: if a video_analyzer preprocessor is configured but the host has
    # no frame backend (cv2/av), video preprocessing will silently no-op for the
    # whole run. Surface that ONCE here so a hybrid run's "video perception" is
    # never assumed to have happened when it did not. (Docker task execution is
    # unaffected; this is about the host-side preprocessor only.)
    _preprocs = condition.get("preprocessors", []) or []
    _has_video_pp = any(
        (pp or {}).get("type") == "video_analyzer" for pp in _preprocs
    )
    if _has_video_pp:
        _backend = frame_backend_available()
        if _backend:
            print(f"   Video preproc:      host frame backend '{_backend}' available")
        else:
            print(
                "   Video preproc:      ⚠️  configured but NO host frame backend "
                "(cv2/av) — video preprocessing will be SKIPPED (no-op). Install "
                "the host perception deps (opencv-python / av are pinned in "
                "batch-runner/requirements.txt) to enable it."
            )

    # Wall-clock deadline for relay runs
    wall_deadline = None
    if wall_timeout and wall_timeout > 0:
        wall_deadline = time.time() + (wall_timeout * 60)
        print(f"   Wall timeout:       {wall_timeout}min (relay mode)")

    # QA config
    qa_cfg = condition.get("qa", {})
    qa_enabled = qa_cfg.get("enabled", False)
    qa_max_retries = qa_cfg.get("max_retries", 2) if qa_enabled else 0
    qa_max_tokens = tokens_cfg["qa_check"]
    if qa_enabled:
        qa_model = qa_cfg.get("model") or model
        print(f"   Self-QA:            enabled (min_score={qa_cfg.get('min_score', 6)}, "
              f"max_retries={qa_max_retries}, model={qa_model}, "
              f"max_tokens={qa_max_tokens})")

    # 2. Create LLM client (provider-aware). Agentic mode defers construction
    # until its compute preflight and signed approval gate pass.
    provider = condition.get("model", {}).get("provider", "azure")
    validation_provider = "azure" if provider == "azure_openai" else provider
    if (
        (
            execution_mode == "agentic_sandbox"
            or (
                execution_mode == "sandbox"
                and sandbox_options.get("hardened_substrate") is True
            )
        )
        and validation_provider not in {"azure", "openai"}
    ):
        print(
            "❌ agentic_sandbox mode requires OpenAI/Azure OpenAI, "
            f"got {provider}"
        )
        sys.exit(1)

    client_factory = None
    hardened_baseline = (
        execution_mode == "sandbox"
        and sandbox_options.get("hardened_substrate") is True
    )

    if execution_mode == "agentic_sandbox" or hardened_baseline:
        if condition.get("qa", {}).get("enabled"):
            print("❌ paired hardened modes disable Self-QA until it shares the signed budget ledger")
            sys.exit(1)
        if condition.get("preprocessors"):
            print("❌ paired hardened modes disable preprocessors until they share the signed budget ledger")
            sys.exit(1)

        authorization_config = agentic_options.get("authorization") or {}
        approved_api_version = authorization_config.get("api_version")
        if provider in ("azure", "azure_openai"):
            approved_endpoint = (
                os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
            )
            def client_factory():
                if not approved_endpoint:
                    raise RuntimeError("Missing AZURE_OPENAI_ENDPOINT")
                return create_provider_client(
                    "azure",
                    endpoint=approved_endpoint,
                    api_version=approved_api_version,
                    max_retries=0,
                )
        elif provider == "openai":
            approved_endpoint = "https://api.openai.com/v1"
            def client_factory():
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError("Missing OPENAI_API_KEY")
                return create_provider_client(
                    "openai",
                    endpoint=approved_endpoint,
                    api_key=api_key,
                    max_retries=0,
                )
        else:
            print(f"❌ paired hardened modes do not support provider '{provider}'")
            sys.exit(1)
        client = None
        print("   Client:             deferred until signed hardened preflight")

    elif provider in ("azure", "azure_openai"):
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
        if not endpoint:
            print("❌ Missing AZURE_OPENAI_ENDPOINT. Set AZURE_OPENAI_ENDPOINT env var.")
            sys.exit(1)
        client = create_provider_client("azure", endpoint=endpoint)
        print(f"   Client:             Azure @ {endpoint}")

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ Missing OpenAI credentials. Set OPENAI_API_KEY")
            sys.exit(1)
        client = create_provider_client("openai", api_key=api_key)
        print("   Client:             OpenAI (native)")

    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ Missing Anthropic credentials. Set ANTHROPIC_API_KEY")
            sys.exit(1)
        client = create_provider_client("anthropic", api_key=api_key)
        print("   Client:             Anthropic")

    else:
        print(f"❌ Unsupported provider: '{provider}'. Use: azure, openai, anthropic")
        sys.exit(1)

    # 3. Initialize executor (no silent fallback — fail loudly)
    reasoning_effort = condition.get("model", {}).get("reasoning_effort")
    agentic_task_requests = None
    if hardened_requested:
        prompt_cfg = condition["prompt"]
        experiment_prompt = {
            "system": prompt_cfg.get("system", "You are a helpful assistant."),
            "prefix": prompt_cfg.get("prefix"),
            "body": prompt_cfg.get("body"),
            "suffix": prompt_cfg.get("suffix"),
        }
        agentic_task_requests = {
            task["task_id"]: task_request_sha256(
                task_prompt=task["instruction"],
                occupation=task.get("occupation", "professional"),
                experiment_prompt=experiment_prompt,
            )
            for task in tasks
        }
        aggregate_budget = agentic_options.get("budget")
        run_identity = (
            aggregate_budget.get("paired_run_id")
            if isinstance(aggregate_budget, dict)
            else None
        )
        if not isinstance(run_identity, str) or not run_identity:
            print("❌ hardened execution requires budget.paired_run_id")
            sys.exit(1)
        workflow_audit = (
            f"{os.getenv('GITHUB_RUN_ID', 'local')}:"
            f"{os.getenv('GITHUB_RUN_ATTEMPT', '1')}"
        )
        print(f"   Paired run:         {run_identity}")
        print(f"   Workflow audit:     {workflow_audit}")
    else:
        github_run = os.getenv("GITHUB_RUN_ID", "local")
        github_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "1")
        run_identity = f"{experiment_id}:{github_run}:{github_attempt}"
    try:
        executor = TaskExecutor(
            mode=execution_mode, llm_client=client, tokens=tokens_cfg,
            timeout=timeout, reasoning_effort=reasoning_effort,
            sandbox_options=sandbox_options,
            metrics_options=metrics_cfg,
            provider=provider,
            client_factory=client_factory,
            agentic_options=agentic_options,
            agentic_endpoint=(approved_endpoint if hardened_requested else None),
            agentic_ordered_task_ids=(
                ordered_task_ids if hardened_requested else None
            ),
            agentic_task_request_sha256=agentic_task_requests,
            run_id=run_identity,
            condition_name=execution_condition,
            model_name=model,
        )
    except Exception as e:
        print(f"❌ Executor init failed for mode '{execution_mode}': {e}")
        print("   Fix the issue or change execution.mode in your YAML config.")
        sys.exit(1)

    # 4. Load manifest
    manifest = None
    try:
        manifest = NeedsFilesManifest.load()
        print(f"   Manifest:           {manifest}")
    except FileNotFoundError:
        print("   ⚠️  Manifest not found — skipping file checks")

    # 5. Build task lookup
    task_map = {t["task_id"]: t for t in tasks}
    if len(task_map) != len(tasks):
        raise AssertionError("prepared task map identity drift")
    total = len(tasks)
    progress_path = WORKSPACE_DIR / "step2_inference_progress.json"
    started_at = datetime.now(timezone.utc).isoformat()

    def _persist_progress(current: dict) -> None:
        _save_progress(
            experiment_id,
            condition_name,
            execution_mode,
            total,
            current["results"],
            started_at,
            progress_path,
            run_id=run_identity,
            condition_identity=execution_condition,
            ordered_task_ids=ordered_task_ids,
            resume_round=int(current.get("resume_round", 0) or 0),
        )

    # ── Helper: execute one task with QA loop ──

    def _run_task_with_qa(task: dict, error_context: str = None) -> dict:
        """Execute one task with infra retries + Self-QA retry loop.

        QA status handling:
        - passed=True  → success (QA 통과)
        - passed=False → 재시도 후에도 score < min_score 면 qa_failed
          (genuine 품질 실패. RETRIABLE_STATUSES 에 포함되어 있어
          resume rounds / 자동 retry 가 다시 동작함)
        - undetermined → 재시도 후 마지막이면 success (score=None,
          QA parse/API 실패만 표시. 품질 실패가 아니므로 retry 대상 아님)

        Best-swap: QA 재시도 시 이전 best 파일을 백업.
        새 결과가 더 좋으면 백업 삭제, 더 나쁘면 백업에서 복원.
        """
        import shutil
        import tempfile

        task_id = task["task_id"]
        job_started = time.perf_counter()
        execution_attempt_count = 0
        sandbox_attempt_count = 0
        tool_call_count = 0
        validated_artifact_count = 0
        self_qa_call_count = 0
        self_qa_time_ms = 0.0
        phase_totals = {
            "model_time_ms": 0.0,
            "tool_time_ms": 0.0,
            "verification_time_ms": 0.0,
            "dependency_time_ms": 0.0,
        }
        time_to_valid_artifact_ms = None
        qa_attempts = 0
        last_qa_feedback = error_context
        reflection_history = []

        # ── best-swap state ──
        best_result = None
        best_score = -1
        best_qa = None
        backup_dir = None  # best 파일 백업 경로

        def _backup_best_files():
            """현재 upload의 deliverable_files를 백업."""
            nonlocal backup_dir
            task_dir = DELIVERABLE_DIR / task_id
            if task_dir.exists() and any(task_dir.iterdir()):
                backup_dir = tempfile.mkdtemp(prefix=f"qa_best_{task_id}_")
                shutil.copytree(task_dir, Path(backup_dir) / "files", dirs_exist_ok=True)

        def _restore_best_files():
            """백업에서 best 파일을 upload로 복원."""
            nonlocal backup_dir
            if backup_dir:
                task_dir = DELIVERABLE_DIR / task_id
                if task_dir.exists():
                    shutil.rmtree(task_dir, ignore_errors=True)
                shutil.copytree(Path(backup_dir) / "files", task_dir)

        def _cleanup_backup():
            """백업 임시 디렉토리 삭제."""
            nonlocal backup_dir
            if backup_dir:
                shutil.rmtree(backup_dir, ignore_errors=True)
                backup_dir = None

        def _record_execution_metrics(task_result: dict) -> None:
            nonlocal execution_attempt_count, sandbox_attempt_count
            nonlocal tool_call_count, validated_artifact_count
            nonlocal time_to_valid_artifact_ms
            execution_attempt_count += 1
            task_observability = task_result.get("observability") or {}
            raw = _bounded_execution_metrics(
                task_observability.get("execution_metrics")
            ) or {}
            agentic = _bounded_agentic_metrics(
                task_observability.get("agentic_metrics")
            ) or {}
            budget = _bounded_budget_metrics(
                task_observability.get("budget_metrics")
            ) or {}
            if agentic and not raw:
                raw = {
                    "model_time_ms": agentic.get("model_time_ms", 0),
                    "tool_time_ms": agentic.get("tool_time_ms", 0),
                    "tool_call_count": agentic.get("tool_calls", 0),
                    "time_to_valid_artifact_ms": agentic.get(
                        "time_to_valid_artifact_ms"
                    ),
                    "validated_artifact_count": (
                        1
                        if (
                            task_result.get("status") == "success"
                            and task_result.get("deliverable_files")
                            and agentic.get("terminal_error_category") is None
                            and (agentic.get("finalize_attempts", 0) or 0) > 0
                        )
                        else 0
                    ),
                }
            if budget.get("time_to_valid_artifact_ms") is not None:
                raw["time_to_valid_artifact_ms"] = budget[
                    "time_to_valid_artifact_ms"
                ]
            sandbox_attempt_count += int(
                raw.get("sandbox_attempt_count", raw.get("attempt_count", 0)) or 0
            )
            tool_call_count += int(raw.get("tool_call_count", 0) or 0)
            validated_artifact_count = max(
                validated_artifact_count,
                int(raw.get("validated_artifact_count", 0) or 0),
            )
            for key in phase_totals:
                phase_totals[key] += float(raw.get(key, 0) or 0)
            measured_valid_time = raw.get("time_to_valid_artifact_ms")
            if (
                time_to_valid_artifact_ms is None
                and measured_valid_time is not None
            ):
                time_to_valid_artifact_ms = float(measured_valid_time)
            sandbox_observability = task_observability.get("sandbox")
            sandbox_valid = (
                isinstance(sandbox_observability, dict)
                and sandbox_observability.get("final_status") in {"ok", "repaired_ok"}
                and int(raw.get("validated_artifact_count", 0) or 0) > 0
            )
            agentic_valid = (
                bool(agentic)
                and agentic.get("terminal_error_category") is None
                and (agentic.get("finalize_attempts", 0) or 0) > 0
                and int(raw.get("validated_artifact_count", 0) or 0) > 0
            )
            if (
                time_to_valid_artifact_ms is None
                and task_result.get("status") == "success"
                and task_result.get("deliverable_files")
                and (sandbox_valid or agentic_valid)
            ):
                time_to_valid_artifact_ms = round(
                    (time.perf_counter() - job_started) * 1000,
                    2,
                )

        def _attach_job_metrics(task_result: dict) -> dict:
            if not metrics_enabled:
                return task_result
            task_wall_time_ms = round(
                (time.perf_counter() - job_started) * 1000,
                2,
            )
            measured_phase_time_ms = (
                sum(phase_totals.values()) + self_qa_time_ms
            )
            metrics = {
                "schema_version": "1.0",
                "task_wall_time_ms": task_wall_time_ms,
                "time_to_valid_artifact_ms": time_to_valid_artifact_ms,
                **{key: round(value, 2) for key, value in phase_totals.items()},
                "self_qa_time_ms": round(self_qa_time_ms, 2),
                "orchestration_time_ms": round(
                    max(0.0, task_wall_time_ms - measured_phase_time_ms),
                    2,
                ),
                "execution_attempt_count": execution_attempt_count,
                "sandbox_attempt_count": sandbox_attempt_count,
                "tool_call_count": tool_call_count,
                "self_qa_call_count": self_qa_call_count,
                "job_run_count": 1,
                "validated_artifact_count": validated_artifact_count,
            }
            bounded_metrics = _bounded_execution_metrics(metrics)
            if bounded_metrics:
                task_result.setdefault("observability", {})[
                    "execution_metrics"
                ] = bounded_metrics
            return task_result

        try:
            while True:
                if qa_attempts > 0:
                    print(f"\n      🔄 Re-executing task "
                          f"(QA attempt {qa_attempts + 1}/{qa_max_retries + 1})...",
                          end=" ", flush=True)

                    # 재실행 전: 현재 best 파일 백업 후 task_dir 비우기
                    _cleanup_backup()  # 이전 백업 정리
                    _backup_best_files()

                    # task_dir 비우기 — 이전 파일이 남아 있으면 LLM이 다른 이름으로
                    # 파일을 생성했을 때 구/신 파일이 공존하게 됨
                    task_dir = DELIVERABLE_DIR / task_id
                    if task_dir.exists():
                        shutil.rmtree(task_dir, ignore_errors=True)

                result = _execute_single_task(
                    task, condition, executor, execution_mode,
                    client, model, manifest,
                    error_context=last_qa_feedback,
                    verbose=verbose,
                    run_id=run_identity,
                    condition_name=execution_condition,
                    strict_inputs=hardened_requested,
                    experiment_id=experiment_id,
                )
                if metrics_enabled:
                    _record_execution_metrics(result)

                # If execution failed, return best if available
                if result["status"] != "success":
                    if best_result is not None:
                        _restore_best_files()
                        _cleanup_backup()
                        print(f"\n      ⚠️  Re-execution failed, "
                              f"keeping best result (score={best_score})",
                              end=" ", flush=True)
                        return _attach_job_metrics(best_result)
                    break

                if not qa_enabled:
                    break

                # Run Self-QA (파일이 workspace에 저장된 상태 → file_preview로 실제 내용 확인)
                qa_started = time.perf_counter()
                qa_result_info = _run_self_qa(
                    task, condition,
                    result.get("deliverable_text", ""),
                    result.get("deliverable_files", []),
                    client,
                    qa_max_tokens=qa_max_tokens,
                )
                if metrics_enabled:
                    self_qa_call_count += 1
                    self_qa_time_ms += (time.perf_counter() - qa_started) * 1000
                result["qa"] = qa_result_info

                # Record this QA attempt in history
                reflection_history.append({
                    "attempt": qa_attempts + 1,          # 1-based
                    "score": qa_result_info.get("score"),
                    "passed": qa_result_info.get("passed"),
                    "undetermined": qa_result_info.get("undetermined", False),
                })

                # ── best-swap: 점수 비교 ──
                current_score = qa_result_info.get("score")
                if current_score is None:
                    current_score = -1  # undetermined

                if current_score > best_score:
                    # 새 결과가 더 좋음 → 백업 삭제, 새 결과를 best로
                    _cleanup_backup()
                    best_score = current_score
                    best_qa = qa_result_info
                    best_result = result
                    if qa_attempts > 0:
                        print(f"\n      📈 New best score: {best_score}",
                              end=" ", flush=True)
                else:
                    # 새 결과가 더 나쁨 → 백업에서 best 파일 복원
                    if backup_dir:
                        _restore_best_files()
                        _cleanup_backup()
                    print(f"\n      📉 Score {current_score} ≤ best {best_score}, "
                          f"keeping previous best",
                          end=" ", flush=True)
                    # best_result의 deliverable_files 경로는 그대로 유효 (restore됨)

                # ── Handle undetermined ──
                if qa_result_info.get("undetermined"):
                    qa_attempts += 1
                    if qa_attempts >= qa_max_retries:
                        if best_qa:
                            best_qa["passed"] = True
                        if best_result:
                            best_result["qa"] = best_qa
                        print("\n      ⚠️  QA undetermined on final attempt — "
                            "saving as success (undetermined)",
                              end=" ", flush=True)
                        break
                    print("\n      ⚠️  QA undetermined, "
                          f"retrying ({qa_attempts}/{qa_max_retries})...",
                          end=" ", flush=True)
                    last_qa_feedback = None
                    continue

                # ── QA 통과 ──
                if qa_result_info["passed"]:
                    break

                # ── QA 실패 (score < min_score) ──
                qa_attempts += 1
                if qa_attempts >= qa_max_retries:
                    print(f"\n      ⚠️  QA max retries reached "
                          f"(best score={best_score}) — "
                          f"saving as success",
                          end=" ", flush=True)
                    # Genuine QA fail (determined, score < min_score, retries
                    # exhausted): mark the best result as qa_failed so the
                    # RETRIABLE_STATUSES retry plumbing (resume rounds) +
                    # _print_status + summary counters fire. The undetermined
                    # branch above is intentionally left as "success" — it
                    # only marks QA parse/API failures, not genuine quality
                    # failures.
                    if best_result is not None:
                        best_result["status"] = "qa_failed"
                    break

                # Build structured reflection prompt for retry
                last_qa_feedback = _build_reflection_prompt(
                    attempt_num=qa_attempts + 1,
                    qa_score=qa_result_info["score"],
                    qa_issues=qa_result_info.get("issues", []),
                    qa_suggestion=qa_result_info.get("suggestion", ""),
                    previous_deliverable_text=result.get("deliverable_text", ""),
                    min_score=qa_cfg.get("min_score", 6),
                )
                print(f"\n      🔍 QA: score={qa_result_info['score']}, "
                      f"retrying ({qa_attempts}/{qa_max_retries})...",
                      end=" ", flush=True)

        finally:
            _cleanup_backup()  # 항상 백업 정리

        if best_result is not None:
            best_result["reflection_history"] = reflection_history
            best_result["reflection_attempts"] = len(reflection_history)
            if len(reflection_history) > 0:
                best_result["reflection_final_score"] = best_score
            return _attach_job_metrics(best_result)
        result["reflection_history"] = reflection_history
        result["reflection_attempts"] = len(reflection_history)
        if len(reflection_history) > 0 and result.get("status") == "success":
            result["reflection_final_score"] = best_score if best_score >= 0 else None
        return _attach_job_metrics(result)

    # ── Helper: print result status ──

    def _print_status(result: dict):
        # 메모리 사용량 측정
        try:
            proc = psutil.Process(os.getpid())
            mem_mb = proc.memory_info().rss / 1024 / 1024
            mem_str = f", mem={mem_mb:.0f}MB"
        except Exception:
            mem_str = ""

        if result["status"] == "success":
            file_count = len(result.get("deliverable_files", []))
            latency = result.get("latency_ms", 0) or 0
            qa_info = ""
            if result.get("qa"):
                qa_info = f", QA={result['qa']['score']}"
            reflection_info = ""
            if result.get("reflection_attempts", 0) > 0:
                reflection_info = f", reflect×{result['reflection_attempts']}"
            print(f"✓ ({latency:.0f}ms, {file_count} files{qa_info}{reflection_info}{mem_str})")
        elif result["status"] == "qa_failed":
            qa = result.get("qa", {})
            print(f"✗ QA failed (score={qa.get('score', '?')}{mem_str})")
        else:
            print(f"✗ {result.get('error', 'Unknown')}{mem_str}")

    # ══════════════════════════════════════════════════════════════════════
    # 6. Initial run OR load existing progress
    # ══════════════════════════════════════════════════════════════════════

    progress = None
    if resume and progress_path.exists():
        try:
            progress = _load_and_validate_progress(
                progress_path,
                experiment_id=experiment_id,
                condition_name=condition_name,
                condition_identity=execution_condition,
                run_id=run_identity,
                execution_mode=execution_mode,
                ordered_task_ids=ordered_task_ids,
            )
        except Exception as exc:
            print(f"❌ progress checkpoint rejected: {exc}")
            sys.exit(1)
        if hardened_requested:
            unsafe_resume = [
                result.get("task_id")
                for result in progress["results"]
                if (
                    result.get("status") in {"error", "qa_failed"}
                    or (
                        result.get("status") == "pending"
                        and (
                            result.get("error") not in {
                                "wall_timeout", "checkpoint_missing_task"
                            }
                            or bool(result.get("observability"))
                        )
                    )
                )
            ]
            if unsafe_resume:
                print(
                    "❌ hardened failed tasks cannot be resumed: "
                    + ", ".join(str(task_id) for task_id in unsafe_resume)
                )
                sys.exit(1)

        # Relay duration fix: preserve original started_at from first run
        if "started_at" in progress:
            started_at = progress["started_at"]

        completed_count = sum(1 for r in progress.get("results", [])
                              if r.get("status") == "success")
        pending_count = sum(1 for r in progress.get("results", [])
                            if r.get("status") == "pending")
        failed_count = sum(1 for r in progress.get("results", [])
                           if r.get("status") in RETRIABLE_STATUSES)
        print(f"\n   ♻️  Loaded progress: {completed_count} succeeded, "
              f"{failed_count} retriable"
              f"{f' ({pending_count} pending)' if pending_count else ''}, "
              f"round {progress.get('resume_round', 0)}")

        # ── Relay mode: pending tasks from wall-timeout checkpoint ──
        if pending_count > 0:
            pending_task_ids = {
                r["task_id"] for r in progress.get("results", [])
                if r.get("status") == "pending"
            }
            remaining_tasks = [t for t in tasks if t["task_id"] in pending_task_ids]

            print(f"\n── Relay Run: {len(remaining_tasks)} pending tasks ──")
            done_count = len(progress["results"]) - pending_count

            for i, task in enumerate(remaining_tasks):
                # ── Watchdog: wall-clock timeout check ──
                if wall_deadline and time.time() >= wall_deadline:
                    still_remaining = remaining_tasks[i:]
                    print(f"\n⏰ Wall timeout reached again ({wall_timeout}min). "
                          f"Saving checkpoint ({i} more completed, "
                          f"{len(still_remaining)} still pending)...")
                    pending_timestamp = datetime.now(timezone.utc).isoformat()
                    still_remaining_ids = {rt["task_id"] for rt in still_remaining}
                    for existing in progress["results"]:
                        if existing["task_id"] in still_remaining_ids:
                            existing["status"] = "pending"
                            existing["error"] = "wall_timeout"
                            existing["timestamp"] = pending_timestamp
                    _persist_progress(progress)
                    print(f"   💾 Checkpoint saved to {progress_path}")
                    sys.exit(EXIT_CHECKPOINT)

                task_id = task["task_id"]
                print(f"   [{done_count + i + 1}/{total}] {task_id} "
                      f"({task['sector']}/{task['occupation']})...",
                      end=" ", flush=True)

                result = _run_task_with_qa(task)
                progress = _update_progress_result(progress, result)
                _print_status(result)

                if (i + 1) % 20 == 0:
                    gc.collect()

                _persist_progress(progress)

            # After relay, set progress so we skip to resume rounds
            # (progress is now not None, so initial run block is skipped)

    if progress is None:
        # === INITIAL RUN: 모든 태스크 실행 ===
        print(f"\n── Round 0: Initial Run ({total} tasks) ──")
        progress = {
            "schema_version": "step2-progress-v2",
            "experiment_id": experiment_id,
            "condition": condition_name,
            "condition_identity": execution_condition,
            "run_id": run_identity,
            "execution_mode": execution_mode,
            "ordered_task_ids": ordered_task_ids,
            "total_tasks": total,
            "started_at": started_at,
            "resume_round": 0,
            "results": [],
        }

        for i, task in enumerate(tasks):
            # ── Watchdog: wall-clock timeout check ──
            if wall_deadline and time.time() >= wall_deadline:
                remaining = tasks[i:]
                print(f"\n⏰ Wall timeout reached ({wall_timeout}min). "
                      f"Saving checkpoint ({i}/{total} completed, "
                      f"{len(remaining)} pending)...")
                for remaining_task in remaining:
                    progress["results"].append({
                        "task_id": remaining_task["task_id"],
                        "status": "pending",
                        "error": "wall_timeout",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                _persist_progress(progress)
                print(f"   💾 Checkpoint saved to {progress_path}")
                sys.exit(EXIT_CHECKPOINT)

            task_id = task["task_id"]
            print(f"   [{i+1}/{total}] {task_id} "
                  f"({task['sector']}/{task['occupation']})...",
                  end=" ", flush=True)

            result = _run_task_with_qa(task)
            progress["results"].append(result)
            _print_status(result)

            # Periodic GC to prevent memory buildup over long batch runs
            if (i + 1) % 20 == 0:
                gc.collect()

            # Incremental save
            _persist_progress(progress)

    # ══════════════════════════════════════════════════════════════════════
    # 7. Resume rounds: progress.json의 error 태스크를 자동 재실행
    # ══════════════════════════════════════════════════════════════════════

    for round_num in range(1, resume_max_rounds + 1):
        failed = _get_failed_task_ids(progress)

        if not failed:
            print("\n✅ No failed tasks — skipping resume rounds")
            break

        print(f"\n── Resume Round {round_num}/{resume_max_rounds}: "
              f"{len(failed)} failed tasks ──")

        recovered = 0
        for fi, fail_info in enumerate(failed, 1):
            # ── Watchdog: wall-clock timeout check (resume round) ──
            # Without this, a long Round 0 followed by heavy resume retries
            # silently exceeds the GitHub Actions step timeout — preventing
            # the relay handoff and forcing a full re-run from scratch.
            if wall_deadline and time.time() >= wall_deadline:
                still_remaining = failed[fi - 1:]
                print(f"\n⏰ Wall timeout reached in Resume Round {round_num} "
                      f"({wall_timeout}min). Saving checkpoint "
                      f"({fi - 1}/{len(failed)} retried, "
                      f"{len(still_remaining)} deferred to relay)...")
                # Mark unfinished retriable tasks as pending → next relay picks them up
                still_remaining_ids = {f["task_id"] for f in still_remaining}
                for r in progress["results"]:
                    if r["task_id"] in still_remaining_ids:
                        r["status"] = "pending"
                        r["error"] = "wall_timeout"
                        r["timestamp"] = datetime.now(timezone.utc).isoformat()
                progress["resume_round"] = round_num
                _persist_progress(progress)
                print(f"   💾 Checkpoint saved to {progress_path}")
                sys.exit(EXIT_CHECKPOINT)

            task_id = fail_info["task_id"]
            task = task_map.get(task_id)
            if task is None:
                print(f"   ⚠️ {task_id} not in task_map, skipping")
                continue

            print(f"   [{fi}/{len(failed)}] 🔄 {task_id} "
                  f"(prev: {fail_info['status']})...",
                  end=" ", flush=True)

            result = _run_task_with_qa(task, error_context=fail_info.get("error"))
            result["resume_round"] = round_num

            # progress.json에서 해당 task_id 오브젝트를 직접 교체
            progress = _update_progress_result(progress, result)
            progress["resume_round"] = round_num
            _print_status(result)

            # Periodic GC during resume rounds
            if fi % 20 == 0:
                gc.collect()

            # Incremental save
            _persist_progress(progress)

            if result["status"] == "success":
                recovered += 1

        still_failed = _get_failed_task_ids(progress)
        print(f"\n   Round {round_num} summary: "
              f"{recovered}/{len(failed)} recovered, "
              f"{len(still_failed)} still failing")

        if not still_failed:
            print("   🎉 All tasks recovered!")
            break

    # ══════════════════════════════════════════════════════════════════════
    # 8. Final summary & save
    # ══════════════════════════════════════════════════════════════════════

    results = progress.get("results", [])
    _validate_result_task_set(
        results, ordered_task_ids, allow_missing=False
    )
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    qa_failed = sum(1 for r in results if r.get("status") == "qa_failed")

    final_output = {
        "experiment_id": experiment_id,
        "experiment_name": prepared.get("experiment_name", ""),
        "source": prepared.get("source", ""),
        "condition": condition_name,
        "condition_identity": execution_condition,
        "run_id": run_identity,
        "execution_mode": execution_mode,
        "ordered_task_ids": ordered_task_ids,
        "model": model,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "resume_rounds_used": progress.get("resume_round", 0),
        "summary": {
            "total": len(results),
            "success": success,
            "error": errors,
            "qa_failed": qa_failed,
        },
        "results": results,
    }

    output_path = WORKSPACE_DIR / "step2_inference_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            final_output,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
        )

    print(f"\n{'='*60}")
    print(f"✅ Step 2 complete: {output_path}")
    print(f"   Success:            {success}/{len(results)}")
    print(f"   Error:              {errors}/{len(results)}")
    if qa_failed:
        print(f"   QA failed:          {qa_failed}/{len(results)}")
    print(f"   Resume rounds used: {progress.get('resume_round', 0)}/{resume_max_rounds}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Step 2: Run inference")
    parser.add_argument(
        "--mode",
        default=None,
        choices=["code_interpreter", "subprocess", "json_renderer"],
        help="Execution mode (overrides YAML execution.mode)",
    )
    parser.add_argument(
        "--max-retries", type=int, default=None,
        help="Infra retries per task (overrides YAML execution.max_retries)",
    )
    parser.add_argument(
        "--resume-max-rounds", type=int, default=None,
        help="Max resume rounds for failed tasks (overrides YAML execution.resume_max_rounds)",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Start fresh (ignore previous progress)",
    )
    parser.add_argument(
        "--condition",
        default="condition_a",
        choices=["condition_a", "condition_b"],
        help="Which condition to run",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed debug info about API response structure (code_interpreter mode)",
    )
    parser.add_argument(
        "--wall-timeout", type=int, default=None,
        help="Wall-clock timeout in minutes. When reached, save checkpoint and "
             "exit with code 42 for relay retrigger. (default: None = no timeout)",
    )
    args = parser.parse_args()

    run_inference(
        execution_mode=args.mode,
        max_retries=args.max_retries,
        resume=not args.no_resume,
        condition_key=args.condition,
        resume_max_rounds=args.resume_max_rounds,
        verbose=args.verbose,
        wall_timeout=args.wall_timeout,
    )


if __name__ == "__main__":
    main()
