# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **subprocess_runner: `_AVAILABLE_FILES` hint now actually executed.**
  In `core/subprocess_runner.py::_execute_safely`, the `files_header`
  (`_AVAILABLE_FILES = [...]`) prepended to the generated `code` string was
  never persisted back to the executed script path, so the subprocess ran the
  raw user code without the guarded hint. The header-prepended `code` is now
  written to `code_path` end-to-end. The earlier redundant pre-prepend write
  was removed; the file is written exactly once after the header is applied.

- **llm_client (Anthropic): tolerant content parsing + `finish_reason`
  surfaced.** `core/llm_client.py::AnthropicClient.chat_complete` previously
  assumed `response.content[0].text`, which crashed when the first block was
  a `thinking` or `tool_use` block. The parser now walks all content blocks
  and concatenates only `type == "text"` segments. `response.stop_reason` is
  mapped to an OpenAI-compatible `finish_reason` (`max_tokens` → `length`;
  `end_turn` / `stop_sequence` / `tool_use` passed through) and exposed on
  `_Choice` / `NormalizedResponse`, so the existing
  `finish_reason == "length"` truncation guard in
  `step2_run_inference.py:436` actually fires for Anthropic.

- **step2_run_inference: `qa_failed` is now set on genuine Self-QA
  failures.** Previously, when Self-QA scored `< min_score` and retries were
  exhausted, the best result was returned with `status == "success"`, which
  meant the `RETRIABLE_STATUSES` retry plumbing (resume rounds), the
  `_print_status` `qa_failed` branch, and the summary counters at
  `step2_run_inference.py:1419` / `1448` were all dead code paths.
  `_run_task_with_qa` now sets `best_result["status"] = "qa_failed"` on
  genuine quality failures, re-enabling auto-retry / resume.
  The `undetermined` branch is intentionally left as `success` — it only
  marks QA parse / API failures, not quality failures, and is not a retry
  target.

### Changed

- **`qa_failed` semantics (BREAKING for comparability).** As a consequence
  of the fix above, the dashboard / aggregated metric `qa_failed_count` is
  no longer comparable across the boundary: pre-fix runs report
  `qa_failed_count == 0` (the flag was never set even when QA genuinely
  failed); post-fix runs report the true count. Treat pre/post
  `qa_failed_count` as different metrics.

- **`compact` mode parquet may now contain fewer rows.** When
  `result_collector` is configured in compact mode it filters
  `status == "success"`. Because genuine QA failures now flip to
  `qa_failed`, those rows are excluded from the compact parquet that were
  previously silently retained as `success`. The non-compact / per-task
  JSON output is unaffected and remains the source of truth for QA failure
  counts.

- **`resume_rounds_used` will be non-zero on QA-enabled runs.** The same
  fix re-enables the resume / retry loop for `qa_failed` tasks via
  `RETRIABLE_STATUSES`, so QA-enabled runs that previously reported
  `resume_rounds_used == 0` may now legitimately consume one or more
  resume rounds. Worst-case per-task cost is capped by the existing
  `qa_max_retries` × `resume_rounds` × infra-retry budget.

### Notes

- **Cost guardrail (re-validated post-fix).** Production experiment YAMLs
  (`exp001`–`exp024`) keep worst-case per-task LLM call multiplier at ≤6×
  (infra retries × QA retries × resume rounds, within previous SLOs).
  Smoke YAMLs (`exp997` / `exp998` / `exp999`) sit higher at 12×–16× in the
  worst case, but their `sample_size` of 2–3 tasks bounds total wall-clock
  / spend impact to negligible levels. No YAML changes are required.

