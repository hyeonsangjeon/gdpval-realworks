# Experiment Report: Codex command-line tool against Foundry — GPT-5.6 Sol, five tasks

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp036_sol_fixed5` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.6-sol |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-11-05 |
| **Duration** | 32m 30s |
| **Generated At** | 2026-11-05T13:11:36.621859+00:00 |
| 🤗 HF Target | [HyeonSang/exp036_sol_fixed5](https://huggingface.co/datasets/HyeonSang/exp036_sol_fixed5) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 5 / 5 tasks (100.0%) |
| Priced | 0 / 5 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 1 (no record) |
| Not priced | call_reachability_unknown, price_missing, usage_partial |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `d26d00beb64c…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This experiment ran five tasks with the Codex command-line tool against a Foundry deployment of gpt-5.6-sol. Four tasks completed successfully and one ended in error, yielding an 80.0% task completion rate. No tasks were retried.

Self-QA measurements were absent for all tasks, including the four successful runs. Consequently, no self-assessed confidence distribution or LLM-evaluated quality result is available; operational success should not be interpreted as evidence of deliverable quality.

The overall average latency was 390034 ms. Information completed fastest at 121718 ms, followed by Health Care and Social Assistance at 228208 ms. Professional, Scientific, and Technical Services completed both tasks but had the highest sector-average latency at 619210 ms, while the Real Estate and Rental and Leasing task failed after 361825 ms.

The supplied metrics do not report deliverable-file presence, validity, naming, or content integrity. Deliverable file generation quality therefore cannot be assessed independently from task completion status.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 5 |
| Success | 4 (80.0%) |
| Errors | 1 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 390,034ms |
| Max Latency | 864,702ms |
| Total LLM Time | 1950s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 4 |
| Successfully generated | 4 (100.0%) |
| Failed (empty outputs preserved) | 0 |

## Quality Analysis

There is no QA score distribution to analyze because no task produced a Self-QA measurement. Minimum, maximum, and average self-assessed confidence are all unmeasured rather than zero, so comparisons of LLM-evaluated quality across tasks or sectors are not possible.

Sector outcomes differ operationally: Health Care and Social Assistance and Information each completed 1/1 task, Professional, Scientific, and Technical Services completed 2/2, and Real Estate and Rental and Leasing completed 0/1. The available data identify the error concentration by sector but do not establish a corresponding quality difference because sector-level Self-QA is absent.

Latency did not prevent successful completion in the slowest sector: Professional, Scientific, and Technical Services averaged 619210 ms and still completed both tasks. Conversely, the Real Estate task failed at 361825 ms. Without Self-QA values, no relationship between latency and self-assessed quality can be evaluated.

No occupation-level labels or deliverable inspection results were provided. Occupation-specific quality observations and file-generation assessments are therefore unavailable beyond the reported sector-level execution outcomes.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Health Care and Social Assistance | 1 | 1 | 100.0% | - | 228,208ms |
| Information | 1 | 1 | 100.0% | - | 121,718ms |
| Professional, Scientific, and Technical  | 2 | 2 | 100.0% | - | 619,210ms |
| Real Estate and Rental and Leasing | 1 | 0 | 0.0% | - | 361,825ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | - | 864702ms |
| 2 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 228208ms |
| 3 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 2 | - | 373718ms |
| 4 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | - | 121718ms |
| 5 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ❌ error | - | 0 | - | 361825ms |

## Failure Analysis

Execution failure is concentrated in one sector and occupation: task 0818571f-5ff7-4d39-9d2c-ced5ae44299e, for Real Estate Brokers in Real Estate and Rental and Leasing, ended with TaskExecutionError and produced zero files. The other four tasks succeeded across three sectors: 02aa1805-c658-4069-8a6a-02dec146063a and 2ea2e5b5-257f-42e6-a7dc-93763f28b19d in Professional, Scientific, and Technical Services, 0112fc9b-c3b2-4084-8993-5a4abb1f54f1 in Health Care and Social Assistance, and 3baa0009-5a60-4ae8-ae99-4955cb328ff3 in Information. Because the failed sector has only one task, this is an observed concentration rather than evidence of a general sector or occupation weakness.

The failed task reports only the generic task_execution_error code, an empty deliverable summary, and zero files. This combination suggests failure occurred before artifact persistence or finalization, but the supplied data cannot distinguish model failure, tool failure, invalid input, export failure, or an execution-environment problem. In contrast, every successful task reports two or more files, so artifact creation cleanly separates the lone operational failure from the successes in this sample.

There is no simple latency-to-failure relationship. The failed task ran for 361825 ms, while 02aa1805-c658-4069-8a6a-02dec146063a successfully completed a spreadsheet-oriented package after 864702 ms, and 2ea2e5b5-257f-42e6-a7dc-93763f28b19d completed a presentation after 373718 ms. The fastest task, 3baa0009-5a60-4ae8-ae99-4955cb328ff3, produced three reported files in 121718 ms. Successful outputs span spreadsheet, document, presentation, Markdown, and image artifacts, so neither elapsed time nor multi-file deliverable complexity explains the Real Estate failure from the available evidence.

Retry effectiveness cannot be evaluated because none of the five tasks was retried; specifically, 0818571f-5ff7-4d39-9d2c-ced5ae44299e was not given a recovery attempt. A separate systematic gap affects every task: all qa_score values are null, including the four successes. Empty qa_issues and qa_suggestion fields therefore do not demonstrate defect-free outputs; they indicate that no usable Self-QA result was recorded. Operational completion and file counts cannot establish content quality, validity, or compliance.

## Recommendations

Add phase-level diagnostics and bounded recovery for task_execution_error. For 0818571f-5ff7-4d39-9d2c-ced5ae44299e, retain stderr, stack trace, exit code, last successful tool call, resource usage, and whether failure occurred during generation, file conversion, validation, or upload. Retry once or twice only for classified transient failures, using a clean workspace while preserving checkpoints; deterministic input or validation failures should instead return a specific error. Do not impose a global timeout below the approximately 865-second duration of successful task 02aa1805-c658-4069-8a6a-02dec146063a; use phase-specific watchdogs to detect stalls without terminating legitimately long artifact work.

Strengthen prompts around staged execution and artifact persistence. Require each task to declare expected filenames and formats, write an intermediate result before expensive conversion, validate each artifact locally, and emit a machine-readable final manifest. For the Real Estate workflow, separate source processing, analysis, document assembly, and export so a failure in the final phase does not leave zero recoverable files. This pattern should also be applied to the successful spreadsheet, Word, PowerPoint, and article/image workflows represented by tasks 02aa1805-c658-4069-8a6a-02dec146063a, 0112fc9b-c3b2-4084-8993-5a4abb1f54f1, 2ea2e5b5-257f-42e6-a7dc-93763f28b19d, and 3baa0009-5a60-4ae8-ae99-4955cb328ff3.

Introduce an execution-environment artifact gate before assigning success. Verify that every declared file exists, is nonempty, has the expected extension, opens with an appropriate parser, and is referenced by a complete canonical path. Add format-specific checks such as workbook readability, DOCX package integrity, PowerPoint slide count, image decoding, and Markdown/link validation. Preserve partial artifacts and validation reports on failure, which would make a future zero-file result distinguishable from a reporting or upload defect.

Make Self-QA mandatory and treat null as “QA unavailable,” not as a passing or zero score. Block final acceptance or route to review whenever qa_score is missing, while running task-specific checks for factual completeness, requested structure, and artifact validity. Numeric thresholds should be calibrated only after collecting scored examples on a known scale; below-threshold outputs should enter a targeted repair pass, while missing-QA outputs should trigger the QA stage itself. Since all five tasks lack Self-QA, instrumentation repair and QA-result persistence should precede any attempt to tune sector-specific thresholds.

## Deliverable Files

- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 2 file(s)
- `3baa0009…` (Information): 3 file(s)
