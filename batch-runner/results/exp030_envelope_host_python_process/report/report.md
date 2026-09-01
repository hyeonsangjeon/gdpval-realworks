# Experiment Report: Run-place comparison — a separate Python process on the server (5 tasks)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp030_envelope_host_python_process` |
| **Condition** | Separate Python process on the server |
| **Model** | gpt-5.4 |
| **Execution Mode** | subprocess |
| **Date** | 2026-09-01 |
| **Duration** | 3m 5s |
| **Generated At** | 2026-09-01T02:50:18.433587+00:00 |
| 🤗 HF Target | [HyeonSang/exp030_envelope_host_python_process](https://huggingface.co/datasets/HyeonSang/exp030_envelope_host_python_process) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 5 / 5 tasks (100.0%) |
| Receipt status | complete |
| Total | $0.2783 |
| Average per task | $0.0557 |
| Median | $0.0632 |
| P95 | $0.0857 |
| Max | $0.0898 |
| Per successful deliverable | $0.0928 |
| Failed tasks | 2 ($0.1530) |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `976198a70bc3…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This experiment executed five tasks in a separate Python subprocess on the server. Three tasks completed successfully, producing a 60.0% task completion rate, while two ended in errors. No tasks were retried, so both execution failures remained unresolved.

Self-QA results were uniformly 0/10, with an average, minimum, and maximum of 0. This indicates no positive self-assessed confidence or LLM-evaluated quality signal, including for the three tasks recorded as successfully completed. Execution success therefore did not correspond to validated output quality.

Average latency was 37,017 ms, with substantial sector variation. Information completed fastest at 18,624 ms, while Real Estate and Rental and Leasing took 59,861 ms and failed. The summary provides no file-level existence, format, or content-validation results, so deliverable file generation quality cannot be confirmed from successful task status alone.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 5 |
| Success | 3 (60.0%) |
| Errors | 2 |
| Retried Tasks | 0 |
| Avg QA Score | 0.0/10 |
| Min QA Score | 0/10 |
| Max QA Score | 0/10 |
| Avg Latency | 37,017ms |
| Max Latency | 59,861ms |
| Total LLM Time | 185s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 4 |
| Successfully generated | 3 (75.0%) |
| Failed (empty outputs preserved) | 1 |

## Quality Analysis

The Self-QA score distribution had no variation: every evaluated result was 0/10. This prevents differentiation among completed tasks and indicates that none received positive LLM-evaluated quality validation. The uniform floor score also makes latency-versus-quality analysis inconclusive.

Health Care and Social Assistance and Information each completed their single task, at 26,444 ms and 18,624 ms respectively, but both retained 0/10 Self-QA. Professional, Scientific, and Technical Services completed one of two tasks, with a sector-average latency of 40,079 ms and 0/10 Self-QA. Real Estate and Rental and Leasing failed its only task and had the highest latency at 59,861 ms.

The results suggest that slower sectors had more execution failures: the fastest two sectors completed their tasks, the mid-to-high-latency professional services sector was partially successful, and the slowest sector failed. However, quality correlation cannot be established because all Self-QA scores were identical. No occupation-level labels or file-validation diagnostics were supplied, so occupation-specific behavior and deliverable integrity cannot be assessed.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Health Care and Social Assistance | 1 | 1 | 100.0% | 0.0/10 | 26,444ms |
| Information | 1 | 1 | 100.0% | 0.0/10 | 18,624ms |
| Professional, Scientific, and Technical  | 2 | 1 | 50.0% | 0.0/10 | 40,079ms |
| Real Estate and Rental and Leasing | 1 | 0 | 0.0% | 0.0/10 | 59,861ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `02aa1805…` | Professional, Scientif | Project Management | ❌ error | - | 0 | - | 39880ms |
| 2 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 26444ms |
| 3 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 5 | - | 40278ms |
| 4 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 2 | - | 18624ms |
| 5 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ❌ error | - | 0 | - | 59861ms |

## Failure Analysis

Two of the five tasks failed, and both had the same execution signature: task_execution_error with a ValueError, zero generated files, and no retry. These were the Project Management Specialists task 02aa1805-c658-4069-8a6a-02dec146063a and the Real Estate Brokers task 0818571f-5ff7-4d39-9d2c-ced5ae44299e. The shared exception type and absence of files suggest a deterministic validation, data-conversion, or artifact-construction failure before output commit, although the missing exception messages and stack traces prevent identification of the precise stage. In contrast, the Nurse Practitioners task 0112fc9b-c3b2-4084-8993-5a4abb1f54f1, IT Managers task 2ea2e5b5-257f-42e6-a7dc-93763f28b19d, and Journalists task 3baa0009-5a60-4ae8-ae99-4955cb328ff3 completed with two, five, and two files respectively.

The failures do not form a purely sector-level cluster. Professional, Scientific, and Technical Services split evenly: the project-management screening task failed, while the IT presentation task succeeded. Real Estate and Rental and Leasing failed its only task, whereas Health Care and Social Assistance and Information each succeeded. A stronger pattern appears in the work type: both failed tasks describe source-dependent screening or acquisition packages that likely require attachment inspection, filtering, structured tables, and possibly spreadsheet generation. The successful health-care and journalism tasks emphasize narrative Word deliverables, while the IT task produced a presentation. This points more strongly toward input-schema or structured-workbook risk than a general inability to create Office files, although the truncated summaries and absent stage diagnostics make that conclusion provisional.

Latency was associated with failure at the aggregate level but was not independently predictive. Failed tasks averaged 49,870.52 ms, compared with 28,448.56 ms for successful tasks, and the Real Estate task was both the slowest task at 59,860.96 ms and a failure. However, task 02aa1805-c658-4069-8a6a-02dec146063a failed at 39,880.08 ms while task 2ea2e5b5-257f-42e6-a7dc-93763f28b19d succeeded at a nearly identical 40,278.19 ms. Longer execution may reflect greater source-processing complexity or a late validation failure, but there is no evidence of a timeout. All five records have retried=false, so there are no retried-but-not-improved cases to evaluate; both initial failures simply remained unresolved.

The Self-QA data indicates a separate observability or validation failure. The aggregate analysis treats every result as 0/10, but every task record contains qa_score=null, an empty issue list, and no suggestion. Missing QA results may therefore have been coerced to zero rather than produced by an actual evaluation. Consequently, the three successful statuses do not establish deliverable quality: file counts confirm only that artifacts were recorded, not that they open, match the requested formats, contain correct content, or represent the expected output set. For example, the five-file count for task 2ea2e5b5-257f-42e6-a7dc-93763f28b19d should be reconciled with its summary naming a single five-slide presentation.

## Recommendations

For structured screening tasks, use a more deterministic model configuration for planning, code, and tool calls, such as temperature 0 to 0.2 with schema-constrained outputs. Prompts for tasks like 02aa1805-c658-4069-8a6a-02dec146063a and 0818571f-5ff7-4d39-9d2c-ced5ae44299e should require an explicit preflight phase listing available attachments, required fields, column mappings, missing-data rules, filters, assumptions, and an expected file manifest. Separate source extraction, normalization, calculations, and document rendering, and persist a simple intermediate CSV or JSON dataset before attempting a workbook or acquisition package. This will localize malformed-input failures and reduce the chance that one rendering exception destroys the entire result.

Instrument the subprocess to retain the full ValueError message, traceback, failing phase, sanitized input schema, output path, and per-phase timing. Preserve partial artifacts in a quarantine directory rather than deleting everything when a later step fails. Pin and smoke-test the relevant spreadsheet, document, presentation, PDF, and attachment-parsing dependencies; verify template compatibility, writable temporary directories, path lengths, free disk space, and serialization of null, date, currency, and numeric values before each run. These checks are particularly important because both failed tasks produced zero files, while Word- and presentation-oriented tasks succeeded.

Introduce exception-aware retries rather than blind repetition. A schema or conversion ValueError should receive one repair attempt after input normalization, with the prior error and sanitized schema supplied to the repair step; transient filesystem, network, or service errors should use bounded exponential backoff. Repeating an unchanged deterministic ValueError should be avoided. Profile the 59,860.96 ms Real Estate run by phase and add targeted timeout headroom only if traces show legitimate processing near a limit; the similar latencies but different outcomes of tasks 02aa1805-c658-4069-8a6a-02dec146063a and 2ea2e5b5-257f-42e6-a7dc-93763f28b19d show that a global timeout increase alone is unlikely to resolve the failure pattern.

Repair the QA pipeline before using its scores for release decisions: preserve null as unavailable rather than converting it to 0, require every execution-success task to receive a completed QA result, and treat QA unavailability as a pipeline error. After calibrating the rubric against manually reviewed outputs, start with a provisional release threshold such as 7/10 and tune it from observed false accepts and false rejects. Add hard file-level gates independent of the score: confirm expected file count and names, open each artifact with the target library, verify required sheets or sections, confirm the IT task has the intended slide structure, check the SOAP note for required clinical sections, and validate the news article's dates, figures, and cited sources. A task should be marked successful only after its output manifest, format checks, content checks, and non-null QA result all pass.

## Deliverable Files

- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 5 file(s)
- `3baa0009…` (Information): 2 file(s)
