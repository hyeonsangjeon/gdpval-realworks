"""Audio Analyzer — gpt-audio-1.5 preprocessor for multi-agent pipeline.

Reads reference audio files, sends them (base64) along with the task
instruction to gpt-audio-1.5, and returns a task-aware JSON analysis.

The analysis is injected into the prompt *before* the main executor runs,
so GPT-5.2 can generate informed code instead of coding blind.

Usage (called by step2_run_inference._run_preprocessors):
    from core.audio_analyzer import analyze_audio_files

    result = analyze_audio_files(
        client=azure_client,
        model_deployment="gpt-audio-1.5",
        system_prompt="You are an audio analysis agent...",
        audio_paths=["/data/ref/track.wav"],
        task_instruction="Mix the saxophone into the backing track...",
    )
    # result: "[AUDIO ANALYSIS]\n{...json...}\n[/AUDIO ANALYSIS]"
"""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import List, Optional

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".aiff"}

# Size limits for audio API calls (base64-encoded MB)
MAX_TOTAL_BASE64_MB = 50   # batch all files if total ≤ this
MAX_SINGLE_FILE_MB = 50    # skip individual files exceeding this


def _audio_format(path: str) -> str:
    """Map file extension to API-accepted format string."""
    ext = Path(path).suffix.lower()
    return {
        ".wav": "wav",
        ".mp3": "mp3",
        ".flac": "flac",
        ".ogg": "ogg",
        ".m4a": "m4a",
        ".aac": "aac",
        ".aiff": "aiff",
    }.get(ext, "wav")


def filter_audio_files(file_paths: List[str] | None) -> List[str]:
    """Return only paths whose extension is a known audio format."""
    if not file_paths:
        return []
    return [p for p in file_paths if Path(p).suffix.lower() in AUDIO_EXTENSIONS]


def _analyze_batch(
    client,
    model_deployment: str,
    system_prompt: str,
    audio_paths: List[str],
    task_instruction: Optional[str] = None,
    max_completion_tokens: int = 4096,
    redact_provider_errors: bool = False,
) -> str:
    """Send one or more audio files in a single API call and return analysis.

    Returns "[AUDIO ANALYSIS]\\n<json>\\n[/AUDIO ANALYSIS]" or "" on failure.
    """
    text_content = system_prompt
    if task_instruction:
        text_content += f"\n\n[TASK]\n{task_instruction}\n[/TASK]"

    content_parts: list[dict] = [{"type": "text", "text": text_content}]

    for audio_path in audio_paths:
        try:
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")
            fmt = _audio_format(audio_path)
            filename = Path(audio_path).name
            size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            print(f"      🎵 Audio preprocessor: encoding {filename} ({size_mb:.1f} MB, {fmt})")
            content_parts.append({
                "type": "input_audio",
                "input_audio": {
                    "data": audio_b64,
                    "format": fmt,
                },
            })
        except Exception as exc:
            print(f"      ⚠️  Audio preprocessor: failed to read {audio_path}: {exc}")
            continue

    if len(content_parts) < 2:
        return ""

    messages = [{"role": "user", "content": content_parts}]

    try:
        start = time.time()
        response = client.chat.completions.create(
            model=model_deployment,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            # Note: gpt-audio-1.5 does not support response_format json_object.
            # JSON output is enforced via system prompt ("Respond with JSON only").
        )
        latency_ms = (time.time() - start) * 1000
        raw_content = response.choices[0].message.content or ""
        # Strip markdown code fences if present (no response_format enforcement)
        analysis_json = raw_content
        if "```json" in analysis_json:
            analysis_json = analysis_json.split("```json")[1].split("```")[0].strip()
        elif "```" in analysis_json:
            analysis_json = analysis_json.split("```")[1].split("```")[0].strip()

        tokens = response.usage
        print(
            f"      🎵 Audio analysis complete: {latency_ms:.0f}ms "
            f"(prompt={tokens.prompt_tokens}, completion={tokens.completion_tokens})"
        )

        if analysis_json.strip():
            return f"[AUDIO ANALYSIS]\n{analysis_json.strip()}\n[/AUDIO ANALYSIS]"
        return ""

    except Exception as exc:
        if redact_provider_errors:
            print(
                "      ⚠️  Audio preprocessor API error (non-fatal) "
                f"({type(exc).__name__})"
            )
        else:
            print(f"      ⚠️  Audio preprocessor API error (non-fatal): {exc}")
        return ""


def analyze_audio_files(
    client,
    model_deployment: str,
    system_prompt: str,
    audio_paths: List[str],
    task_instruction: Optional[str] = None,
    max_completion_tokens: int = 4096,
    redact_provider_errors: bool = False,
) -> str:
    """Send audio files + task instruction to gpt-audio-1.5 for analysis.

    Handles large multi-file payloads by splitting into per-file API calls
    when total base64 size exceeds MAX_TOTAL_BASE64_MB.

    Args:
        client:           AzureOpenAI (or OpenAI) client instance.
        model_deployment:  Deployment name, e.g. "gpt-audio-1.5".
        system_prompt:     System prompt from YAML preprocessor config.
        audio_paths:       List of absolute paths to audio files.
        task_instruction:  The task prompt (injected when include_task_instruction=true).
        max_completion_tokens: Max tokens for the analysis response.

    Returns:
        "[AUDIO ANALYSIS]\\n<json>\\n[/AUDIO ANALYSIS]" on success,
        empty string on failure (preprocessor errors must not block main execution).
    """
    if not audio_paths:
        return ""

    # Pre-filter by individual file size
    eligible: list[tuple[str, float]] = []
    for audio_path in audio_paths:
        try:
            size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        except OSError:
            print(f"      ⚠️  Audio preprocessor: cannot stat {audio_path}")
            continue
        b64_size_mb = size_mb * 4 / 3  # base64 overhead ~33%
        if b64_size_mb > MAX_SINGLE_FILE_MB:
            print(
                f"      ⚠️  Skipping {Path(audio_path).name}: "
                f"{b64_size_mb:.0f}MB exceeds {MAX_SINGLE_FILE_MB}MB limit"
            )
            continue
        eligible.append((audio_path, b64_size_mb))

    if not eligible:
        return ""

    total_b64_mb = sum(s for _, s in eligible)
    paths = [p for p, _ in eligible]

    # ── Small enough → single batch call ──
    if total_b64_mb <= MAX_TOTAL_BASE64_MB:
        return _analyze_batch(
            client, model_deployment, system_prompt,
            paths, task_instruction, max_completion_tokens,
            redact_provider_errors,
        )

    # ── Too large → per-file individual calls, merge results ──
    print(
        f"      🎵 Total audio {total_b64_mb:.0f}MB > {MAX_TOTAL_BASE64_MB}MB, "
        f"analyzing {len(paths)} files individually"
    )
    all_analyses: dict = {}
    for audio_path in paths:
        result = _analyze_batch(
            client, model_deployment, system_prompt,
            [audio_path], task_instruction, max_completion_tokens,
            redact_provider_errors,
        )
        if result:
            inner = (
                result
                .replace("[AUDIO ANALYSIS]\n", "")
                .replace("\n[/AUDIO ANALYSIS]", "")
            )
            try:
                parsed = json.loads(inner)
                all_analyses[Path(audio_path).name] = parsed
            except json.JSONDecodeError:
                all_analyses[Path(audio_path).name] = inner

    if all_analyses:
        combined = json.dumps(all_analyses, indent=2, ensure_ascii=False)
        return f"[AUDIO ANALYSIS]\n{combined}\n[/AUDIO ANALYSIS]"
    return ""
