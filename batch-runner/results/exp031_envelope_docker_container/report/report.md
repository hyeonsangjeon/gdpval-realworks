# Experiment Report: Run-place comparison — a Docker container (5 tasks)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp031_envelope_docker_container` |
| **Condition** | Docker container |
| **Model** | gpt-5.4 |
| **Execution Mode** | sandbox |
| **Date** | 2026-09-01 |
| **Duration** | 3m 57s |
| **Generated At** | 2026-09-01T03:04:58.041418+00:00 |
| 🤗 HF Target | [HyeonSang/exp031_envelope_docker_container](https://huggingface.co/datasets/HyeonSang/exp031_envelope_docker_container) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 5 / 5 tasks (100.0%) |
| Receipt status | complete |
| Total | $0.3740 |
| Average per task | $0.0748 |
| Median | $0.0677 |
| P95 | $0.1272 |
| Max | $0.1360 |
| Per successful deliverable | $0.0935 |
| Failed tasks | 1 ($0.0372) |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `8dd544bae244…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This experiment ran five tasks in a Docker container using sandbox execution. Four tasks completed successfully and one ended in error, yielding an 80.0% task completion rate. No tasks were retried.

Self-QA was uniformly 0.0/10, with both the minimum and maximum equal to zero. Consequently, the 80% execution success should not be interpreted as evidence of validated output quality or strong self-assessed confidence.

The Information and Real Estate and Rental and Leasing tasks completed successfully, as did both Professional, Scientific, and Technical Services tasks. The sole Health Care and Social Assistance task failed.

Average latency was 47,421 ms. Four successful statuses indicate that most workflows reached completion, but no file-level validation or inspection results were supplied; deliverable generation quality therefore cannot be confirmed beyond execution status.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 5 |
| Success | 4 (80.0%) |
| Errors | 1 |
| Retried Tasks | 0 |
| Avg QA Score | 0.0/10 |
| Min QA Score | 0/10 |
| Max QA Score | 0/10 |
| Avg Latency | 47,421ms |
| Max Latency | 87,114ms |
| Total LLM Time | 237s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 4 |
| Successfully generated | 3 (75.0%) |
| Failed (empty outputs preserved) | 1 |

## Quality Analysis

The Self-QA distribution had no variation: every task received 0.0/10 LLM-evaluated quality. This prevents differentiation among successful tasks and indicates that none of the outputs received positive self-assessed confidence, despite four workflows completing.

Sector completion differed: Professional, Scientific, and Technical Services completed 2/2 tasks, while Information and Real Estate and Rental and Leasing each completed 1/1. Health Care and Social Assistance completed 0/1. All sectors nevertheless had an average Self-QA score of 0.0/10.

No occupation-level labels or per-task deliverable details were provided, so occupation-specific performance and file-generation characteristics cannot be assessed. In particular, successful execution does not establish that generated files were complete, correctly formatted, or usable, while the failed task may not have produced a final deliverable.

Latency did not show an assessable relationship with LLM-evaluated quality because all Self-QA scores were identical. Professional, Scientific, and Technical Services had the highest average latency at 70,906 ms while completing both tasks; Real Estate averaged 42,674 ms and Information 29,881 ms. The failed Health Care task averaged 22,742 ms, which may reflect earlier termination, but the available metrics do not identify the error stage.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Health Care and Social Assistance | 1 | 0 | 0.0% | 0.0/10 | 22,742ms |
| Information | 1 | 1 | 100.0% | 0.0/10 | 29,881ms |
| Professional, Scientific, and Technical  | 2 | 2 | 100.0% | 0.0/10 | 70,906ms |
| Real Estate and Rental and Leasing | 1 | 1 | 100.0% | 0.0/10 | 42,674ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 3 | - | 54698ms |
| 2 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ❌ error | - | 0 | - | 22742ms |
| 3 | `2ea2e5b5…` | Professional, Scientif | Computer and Infor | ✅ success | - | 7 | - | 87114ms |
| 4 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | - | 29881ms |
| 5 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 2 | - | 42674ms |

## Failure Analysis

The only execution failure was task 0112fc9b-c3b2-4084-8993-5a4abb1f54f1, the Nurse Practitioners task, which terminated with a task_execution_error caused by TypeError and produced zero files. Its 22,742 ms latency was lower than every successful task, suggesting failure during an intermediate processing or document-generation stage rather than a timeout. In contrast, the four successful tasks produced between two and seven files and ran for 29,881–87,114 ms.

The failure is nominally concentrated in Health Care and Social Assistance, which completed 0/1 tasks. Professional, Scientific, and Technical Services completed both task 02aa1805-c658-4069-8a6a-02dec146063a and task 2ea2e5b5-257f-42e6-a7dc-93763f28b19d, while Information task 3baa0009-5a60-4ae8-ae99-4955cb328ff3 and Real Estate task 0818571f-5ff7-4d39-9d2c-ced5ae44299e also succeeded. Because each occupation appears only once and the failed sector has only one observation, this is insufficient evidence of a general healthcare or Nurse Practitioner cluster; it is more consistent with a task-specific code or input-type defect.

Task complexity and artifact count did not predict execution failure. The longest task, 2ea2e5b5-257f-42e6-a7dc-93763f28b19d, completed in 87,114 ms and produced seven files, while the failed task planned a single formatted SOAP-note DOCX and produced none. Other successful tasks exercised XLSX, DOCX, image, and PDF workflows, so the evidence does not indicate a broad office-document generation failure. The failed clinical workflow may instead contain a specific unsupported value, null field, or incompatible object passed into its DOCX-generation path.

No task was retried, so retry effectiveness and retried-but-not-improved behavior cannot be assessed. Quality signals are also non-discriminating: the aggregate analysis treats every Self-QA result as 0.0/10, while the task-level qa_score fields are null and contain no issues or suggestions. This may mean missing evaluations were converted to zero. Consequently, successful execution for tasks 02aa1805-c658-4069-8a6a-02dec146063a, 2ea2e5b5-257f-42e6-a7dc-93763f28b19d, 3baa0009-5a60-4ae8-ae99-4955cb328ff3, and 0818571f-5ff7-4d39-9d2c-ced5ae44299e does not establish file correctness, and latency cannot be correlated with quality because the QA signal has no usable variation.

## Recommendations

Instrument and reproduce task 0112fc9b-c3b2-4084-8993-5a4abb1f54f1 with the full TypeError traceback, failing line, input types, dependency versions, and stage-level timestamps. Add explicit normalization for null, scalar, list, dictionary, date, and numeric values before populating the SOAP-note template, and validate every value passed to the DOCX library. Save artifacts atomically and emit a stage manifest so future failures can be localized to extraction, composition, formatting, validation, or file writing.

Introduce one bounded retry with a clean process and workspace after recording the original exception, but classify errors before retrying. A raw TypeError is likely deterministic, so an identical retry is unlikely to help; the retry should first apply schema normalization or switch to a simpler document-writing fallback. Do not address this case merely by increasing the timeout, because the failed task ended earlier than all four successful tasks, including the 87,114 ms multi-file task 2ea2e5b5-257f-42e6-a7dc-93763f28b19d. Pin and smoke-test document-generation dependencies in the container to prevent type-contract changes across runs.

Strengthen prompts with a structured execution contract: enumerate required artifacts, define source-field schemas, specify handling for missing clinical information, and require the model to reopen and inspect each generated file before declaring completion. For the SOAP-note workflow, instruct the model to use explicit placeholders such as “not provided” rather than passing null objects or inventing details. Apply the same manifest-and-validation process to the successful XLSX, DOCX, image, and PDF tasks, since their positive statuses and file counts do not confirm that their contents are complete or usable.

Repair the QA pipeline before using Self-QA operationally. Preserve null as “not evaluated” rather than silently treating it as 0.0, require a non-null score plus populated issue diagnostics, and route both missing evaluations and genuine zero scores to remediation or review. An initial release gate could require a Self-QA score of at least 7/10 together with format-specific checks: files exist, expected counts match, documents reopen successfully, spreadsheets contain required sheets, images decode, PDFs have nonempty pages, and key requested sections are present. Track these checks separately from execution status so the current 4/5 completion result is not mistaken for validated deliverable quality.

## Deliverable Files

- `02aa1805…` (Professional, Scientific, and Technical Services): 3 file(s)
- `2ea2e5b5…` (Professional, Scientific, and Technical Services): 7 file(s)
- `3baa0009…` (Information): 3 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 2 file(s)
