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
import json
import os
import psutil
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from core.config import (
    WORKSPACE_DIR,
    UPLOAD_DIR,
    DELIVERABLE_DIR,
    DEFAULT_LOCAL_PATH,
    DEFAULT_TOKENS,
)
from core.data_loader import GDPValTask
from core.executor import TaskExecutor
from core.file_preview import generate_all_previews
from core.llm_client import create_client, create_provider_client, complete
from core.needs_files import NeedsFilesManifest
from core.prompt_builder import PromptBuilder, PromptConfig as BuilderPromptConfig
from core.audio_analyzer import analyze_audio_files, filter_audio_files


# ── Constants ──────────────────────────────────────────────────────────────

RETRIABLE_STATUSES = {"error", "qa_failed", "pending"}

# Exit code convention
EXIT_CHECKPOINT = 42  # checkpoint saved, relay retrigger needed

# Cache of models that don't support temperature=0 (learned at runtime, reused in session)
_MODELS_NO_TEMPERATURE: set = set()


# ── Preprocessor helper ───────────────────────────────────────────────────

def _run_preprocessors(
    condition: dict,
    abs_ref_files: list[str] | None,
    task_instruction: str,
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

        if pp_type == "audio_analyzer":
            # Check trigger condition
            if trigger == "has_audio_files":
                audio_files = filter_audio_files(abs_ref_files)
                if not audio_files:
                    continue
            else:
                audio_files = filter_audio_files(abs_ref_files)
                if not audio_files:
                    continue

            # Create a separate client for the preprocessor model
            pp_model = pp_cfg.get("model", {})
            pp_provider = pp_model.get("provider", "azure")
            pp_deployment = pp_model.get("deployment", "gpt-audio-1.5")
            pp_system = pp_cfg.get("system", "You are an audio analysis agent.")
            include_task = pp_cfg.get("include_task_instruction", False)

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
            except Exception as exc:
                print(f"      ⚠️  Preprocessor '{pp_type}' error (non-fatal): {exc}")
                continue
        else:
            print(f"      ⚠️  Unknown preprocessor type: '{pp_type}' — skipping")

    return "\n\n".join(results)


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
            print(f"  ⚠️  QA response truncated (finish_reason=length)")

        raw = (response.choices[0].message.content or "").strip()
        if not raw:
            print(f"  ⚠️  QA returned empty response")
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

    output_dir = DELIVERABLE_DIR / task_id
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = []
    for file_data in files:
        filename = file_data["filename"]
        content = file_data["content"]
        filepath = output_dir / filename

        if isinstance(content, bytes):
            filepath.write_bytes(content)
        else:
            filepath.write_bytes(content.encode("utf-8"))

        try:
            rel_path = filepath.relative_to(UPLOAD_DIR)
            saved_paths.append(str(rel_path))
        except ValueError:
            saved_paths.append(str(filepath))

    return saved_paths


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
    if ref_files:
        abs_ref_files = []
        for ref_path in ref_files:
            abs_path = DEFAULT_LOCAL_PATH / ref_path
            if abs_path.exists():
                abs_ref_files.append(str(abs_path))
            else:
                print(f"      ⚠️  Reference file not found: {abs_path}")
        if not abs_ref_files:
            abs_ref_files = None  # all missing → treat as no files

    # ── Preprocessor: enrich prompt with audio analysis (if configured) ──
    preprocessor_prefix = _run_preprocessors(condition, abs_ref_files, instruction)
    if preprocessor_prefix:
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
                "latency_ms": round(latency_ms, 2),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "task_id": task_id,
                "status": "error",
                "error": result.get("error", "Unknown error"),
                "content": result.get("text"),
                "deliverable_text": result.get("deliverable_text"),
                "deliverable_files": [],
                "model": model,
                "usage": None,
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
) -> None:
    """Atomic incremental save."""
    success = sum(1 for r in results if r.get("status") == "success")
    error = sum(1 for r in results if r.get("status") == "error")

    data = {
        "experiment_id": experiment_id,
        "condition": condition_name,
        "execution_mode": execution_mode,
        "started_at": started_at,
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
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    tmp_path.rename(path)


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
    model = condition["model"]["deployment"]
    condition_name = condition["name"]

    # Resolve settings: CLI override > YAML execution block > defaults
    execution_cfg = prepared.get("execution", {})
    timeout = execution_cfg.get("timeout")  # None = config.py 기본값 사용
    if execution_mode is None:
        execution_mode = execution_cfg.get("mode", prepared.get("execution_mode", "subprocess"))
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

    print(f"\n{'='*60}")
    print(f"🚀 Step 2: Run Inference")
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
    reasoning_effort_display = condition.get("model", {}).get("reasoning_effort")
    if reasoning_effort_display:
        print(f"   Reasoning effort:   {reasoning_effort_display}")

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

    # 2. Create LLM client (provider-aware)
    provider = condition.get("model", {}).get("provider", "azure")

    if provider in ("azure", "azure_openai"):
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
        print(f"   Client:             OpenAI (native)")

    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("❌ Missing Anthropic credentials. Set ANTHROPIC_API_KEY")
            sys.exit(1)
        client = create_provider_client("anthropic", api_key=api_key)
        print(f"   Client:             Anthropic")

    else:
        print(f"❌ Unsupported provider: '{provider}'. Use: azure, openai, anthropic")
        sys.exit(1)

    # 3. Initialize executor (no silent fallback — fail loudly)
    reasoning_effort = condition.get("model", {}).get("reasoning_effort")
    try:
        executor = TaskExecutor(
            mode=execution_mode, llm_client=client, tokens=tokens_cfg,
            timeout=timeout, reasoning_effort=reasoning_effort,
        )
    except Exception as e:
        print(f"❌ Executor init failed for mode '{execution_mode}': {e}")
        print(f"   Fix the issue or change execution.mode in your YAML config.")
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
    total = len(tasks)
    progress_path = WORKSPACE_DIR / "step2_inference_progress.json"
    started_at = datetime.now(timezone.utc).isoformat()

    # ── Helper: execute one task with QA loop ──

    def _run_task_with_qa(task: dict, error_context: str = None) -> dict:
        """Execute one task with infra retries + Self-QA retry loop.

        QA status handling:
        - passed=True  → success (QA 통과)
        - passed=False → success (파일 생성 = LLM 성능, QA 점수만 낮음)
        - undetermined → 재시도 후 마지막이면 success (score=None)

        Best-swap: QA 재시도 시 이전 best 파일을 백업.
        새 결과가 더 좋으면 백업 삭제, 더 나쁘면 백업에서 복원.
        """
        import shutil
        import tempfile

        task_id = task["task_id"]
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
                )

                # If execution failed, return best if available
                if result["status"] != "success":
                    if best_result is not None:
                        _restore_best_files()
                        _cleanup_backup()
                        print(f"\n      ⚠️  Re-execution failed, "
                              f"keeping best result (score={best_score})",
                              end=" ", flush=True)
                        return best_result
                    break

                if not qa_enabled:
                    break

                # Run Self-QA (파일이 workspace에 저장된 상태 → file_preview로 실제 내용 확인)
                qa_result_info = _run_self_qa(
                    task, condition,
                    result.get("deliverable_text", ""),
                    result.get("deliverable_files", []),
                    client,
                    qa_max_tokens=qa_max_tokens,
                )
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
                        print(f"\n      ⚠️  QA undetermined on final attempt — "
                              f"saving as success (undetermined)",
                              end=" ", flush=True)
                        break
                    print(f"\n      ⚠️  QA undetermined, "
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
            return best_result
        result["reflection_history"] = reflection_history
        result["reflection_attempts"] = len(reflection_history)
        if len(reflection_history) > 0 and result.get("status") == "success":
            result["reflection_final_score"] = best_score if best_score >= 0 else None
        return result

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
        with open(progress_path, "r", encoding="utf-8") as f:
            progress = json.load(f)

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
            # Remove pending entries — they'll be re-executed below
            progress["results"] = [
                r for r in progress["results"] if r.get("status") != "pending"
            ]
            remaining_tasks = [t for t in tasks if t["task_id"] in pending_task_ids]

            print(f"\n── Relay Run: {len(remaining_tasks)} pending tasks ──")
            done_count = len(progress["results"])

            for i, task in enumerate(remaining_tasks):
                # ── Watchdog: wall-clock timeout check ──
                if wall_deadline and time.time() >= wall_deadline:
                    still_remaining = remaining_tasks[i:]
                    print(f"\n⏰ Wall timeout reached again ({wall_timeout}min). "
                          f"Saving checkpoint ({i} more completed, "
                          f"{len(still_remaining)} still pending)...")
                    for rt in still_remaining:
                        progress["results"].append({
                            "task_id": rt["task_id"],
                            "status": "pending",
                            "error": "wall_timeout",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                    _save_progress(
                        experiment_id, condition_name, execution_mode,
                        total, progress["results"], started_at, progress_path,
                    )
                    print(f"   💾 Checkpoint saved to {progress_path}")
                    sys.exit(EXIT_CHECKPOINT)

                task_id = task["task_id"]
                print(f"   [{done_count + i + 1}/{total}] {task_id} "
                      f"({task['sector']}/{task['occupation']})...",
                      end=" ", flush=True)

                result = _run_task_with_qa(task)
                progress["results"].append(result)
                _print_status(result)

                if (i + 1) % 20 == 0:
                    gc.collect()

                _save_progress(
                    experiment_id, condition_name, execution_mode,
                    total, progress["results"], started_at, progress_path,
                )

            # After relay, set progress so we skip to resume rounds
            # (progress is now not None, so initial run block is skipped)

    if progress is None:
        # === INITIAL RUN: 모든 태스크 실행 ===
        print(f"\n── Round 0: Initial Run ({total} tasks) ──")
        progress = {
            "experiment_id": experiment_id,
            "condition": condition_name,
            "execution_mode": execution_mode,
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
                _save_progress(
                    experiment_id, condition_name, execution_mode,
                    total, progress["results"], started_at, progress_path,
                )
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
            _save_progress(
                experiment_id, condition_name, execution_mode,
                total, progress["results"], started_at, progress_path,
            )

    # ══════════════════════════════════════════════════════════════════════
    # 7. Resume rounds: progress.json의 error 태스크를 자동 재실행
    # ══════════════════════════════════════════════════════════════════════

    for round_num in range(1, resume_max_rounds + 1):
        failed = _get_failed_task_ids(progress)

        if not failed:
            print(f"\n✅ No failed tasks — skipping resume rounds")
            break

        print(f"\n── Resume Round {round_num}/{resume_max_rounds}: "
              f"{len(failed)} failed tasks ──")

        recovered = 0
        for fi, fail_info in enumerate(failed, 1):
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
            _save_progress(
                experiment_id, condition_name, execution_mode,
                total, progress["results"], started_at, progress_path,
            )

            if result["status"] == "success":
                recovered += 1

        still_failed = _get_failed_task_ids(progress)
        print(f"\n   Round {round_num} summary: "
              f"{recovered}/{len(failed)} recovered, "
              f"{len(still_failed)} still failing")

        if not still_failed:
            print(f"   🎉 All tasks recovered!")
            break

    # ══════════════════════════════════════════════════════════════════════
    # 8. Final summary & save
    # ══════════════════════════════════════════════════════════════════════

    results = progress.get("results", [])
    success = sum(1 for r in results if r["status"] == "success")
    errors = sum(1 for r in results if r["status"] == "error")
    qa_failed = sum(1 for r in results if r.get("status") == "qa_failed")

    final_output = {
        "experiment_id": experiment_id,
        "experiment_name": prepared.get("experiment_name", ""),
        "source": prepared.get("source", ""),
        "condition": condition_name,
        "execution_mode": execution_mode,
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
        json.dump(final_output, f, indent=2, ensure_ascii=False, default=str)

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
