# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Phase A grading infrastructure.** Added rubric-based grading pipeline
  components: `batch-runner/core/rubric_loader.py`,
  `batch-runner/core/grader.py`, `batch-runner/prompts/grader_judge.md`,
  `batch-runner/step8_grade.py`,
  `batch-runner/grading_configs/default_gpt5pro.yaml`,
  `batch-runner/schemas/grade.schema.json`,
  `.github/workflows/grade-run.yml`,
  `batch-runner/scripts/download_inference_from_hf.py`, and
  `.github/agents/grading-engineer.md`.

### Removed

- **`core/evals_submitter.py` dead code.** Removed deprecated placeholder
  hosted-grading submitter and its test file
  (`tests/test_evals_submitter.py`) in favor of the new self-grading flow.

### Fixed

- **step2_run_inference: wall-timeout watchdog now also fires inside Resume
  Rounds (silent relay-bypass fix).** Previously the `wall_deadline` check
  existed only in the Round 0 (initial run) and Relay-run continuation
  loops in `batch-runner/step2_run_inference.py`. When Round 0 completed
  within `wall_timeout`, control fell through to the Resume Round loop
  (around L1370) which had no deadline check. Heavy resume retries
  (Self-QA, audio preprocessor, video composition) then silently exceeded
  the GitHub Actions step hard timeout — on SIGKILL the run could not
  save a checkpoint or mark `pending` tasks, so the workflow saw
  `pending=0, needs_relay=false` and skipped the HF checkpoint upload +
  self-retrigger, forcing a full re-run from scratch
  (observed in run 26018603400 / exp025: Round 0 finished ~250min,
  Resume Round 1 SIGKILLed at ~330min with no relay). The Resume Round
  loop now mirrors the existing watchdog: unfinished retriable tasks are
  marked `pending(error=wall_timeout)`, `_save_progress()` is called, and
  the process exits with `EXIT_CHECKPOINT(42)` so the workflow uploads
  the checkpoint and self-retriggers. Backward compatible — `wall_timeout
  = 0` (no timeout) short-circuits the guard as before.
  (PR #41)

- **batch-run workflow: Step 2a/2b `timeout-minutes` widened 330 → 350.**
  After `wall_timeout` (default 290min) fires, the run still needs time to
  save the progress checkpoint, upload it to HuggingFace, and dispatch
  the relay re-trigger. The previous 330min hard step timeout left only
  ~40min for this handoff, which proved insufficient in practice. The new
  350min ceiling gives a 60min margin while still staying well under the
  6h job-level cap. (PR #41)

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

