# Experiment Report: Codex command-line tool against Foundry — GPT-5.6 Sol, first 25 of 220

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp037_sol_first25` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.6-sol |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-11-10 |
| **Duration** | 309m 1s |
| **Generated At** | 2026-11-10T15:17:11.677283+00:00 |
| 🤗 HF Target | [HyeonSang/exp037_sol_first25](https://huggingface.co/datasets/HyeonSang/exp037_sol_first25) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 25 / 25 tasks (100.0%) |
| Priced | 0 / 25 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 1 (no record) |
| Not priced | call_reachability_unknown, price_missing, usage_partial |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `f2e54fbaef57…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This experiment ran the first 25 of 220 tasks using the Codex command-line tool against a Foundry deployment of gpt-5.6-sol. The run achieved a 96.0% task completion rate: 24 tasks succeeded, one ended in error, and no tasks were retried.

The reported average latency was 625,162 ms per task. Eight of nine sectors completed all assigned tasks; Government completed two of three and contained the run’s only error. Professional, Scientific, and Technical Services and Real Estate and Rental and Leasing had the highest reported sector-average latencies.

Self-QA measurements are absent because no task produced a Self-QA value; consequently, self-assessed confidence and LLM-evaluated quality cannot be quantified. Successful status indicates that 24 executions completed the expected workflow, but no artifact-level inspection data were provided to assess deliverable-file correctness, completeness, or formatting quality.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 25 |
| Success | 24 (96.0%) |
| Errors | 1 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 625,162ms |
| Max Latency | 1,590,554ms |
| Total LLM Time | 15629s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 23 |
| Successfully generated | 22 (95.7%) |
| Failed (empty outputs preserved) | 1 |

## Quality Analysis

There is no Self-QA score distribution to analyze: average, minimum, and maximum values were never measured because no task produced a score. The execution results therefore support analysis of completion and latency only, not conclusions about self-assessed confidence or LLM-evaluated quality.

Sector completion was consistent outside Government. Finance and Insurance, Health Care and Social Assistance, Information, Manufacturing, Professional, Scientific, and Technical Services, Real Estate and Rental and Leasing, Retail Trade, and Wholesale Trade all had 100% completion. Government recorded two successes in three tasks and accounted for the sole error.

Reported sector-average latency varied substantially. Professional, Scientific, and Technical Services was highest at 1,096,220 ms, followed by Real Estate and Rental and Leasing at 904,372 ms. Government was lowest at 387,485 ms, closely followed by Information at 397,467 ms; however, the Government average should be interpreted cautiously because that sector included the failed execution. Without Self-QA values, no latency-to-quality correlation can be calculated.

No occupation-level breakdown or individual deliverable validation results were supplied, so occupation-specific behavior and file-generation quality cannot be differentiated. The available evidence establishes successful execution for 24 tasks but does not establish the quality of their generated files.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 3 | 3 | 100.0% | - | 634,878ms |
| Government | 3 | 2 | 66.7% | - | 387,485ms |
| Health Care and Social Assistance | 3 | 3 | 100.0% | - | 452,312ms |
| Information | 3 | 3 | 100.0% | - | 397,467ms |
| Manufacturing | 3 | 3 | 100.0% | - | 575,171ms |
| Professional, Scientific, and Technical  | 3 | 3 | 100.0% | - | 1,096,220ms |
| Real Estate and Rental and Leasing | 3 | 3 | 100.0% | - | 904,372ms |
| Retail Trade | 2 | 2 | 100.0% | - | 507,425ms |
| Wholesale Trade | 2 | 2 | 100.0% | - | 635,244ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | - | 239396ms |
| 2 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 1 | - | 701185ms |
| 3 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 2 | - | 276384ms |
| 4 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 11 | - | 586656ms |
| 5 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | - | 940015ms |
| 6 | `02aa1805…` | Professional, Scientif | Project Management | ✅ success | - | 2 | - | 1015911ms |
| 7 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 1 | - | 1317985ms |
| 8 | `105f8ad0…` | Wholesale Trade | Sales Representati | ✅ success | - | 2 | - | 870184ms |
| 9 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 608338ms |
| 10 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ✅ success | - | 2 | - | 871044ms |
| 11 | `11e1b169…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 101256ms |
| 12 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ✅ success | - | 1 | - | 931397ms |
| 13 | `3a4c347c…` | Information | Editors | ✅ success | - | 1 | - | 483006ms |
| 14 | `11dcc268…` | Manufacturing | Shipping, Receivin | ✅ success | - | 1 | - | 243744ms |
| 15 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 93 | - | 1590554ms |
| 16 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ✅ success | - | 3 | - | 790214ms |
| 17 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 2 | - | 400304ms |
| 18 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 3 | - | 406512ms |
| 19 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 4 | - | 794194ms |
| 20 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 2 | - | 360014ms |
| 21 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 149153ms |
| 22 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | - | 122739ms |
| 23 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 2 | - | 541754ms |
| 24 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | - | 682193ms |
| 25 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | - | 604918ms |

## Failure Analysis

Across all 25 tasks, the only hard failure was task 11e1b169-5fb6-4d79-8a83-82ddf4987a85, which ended with a generic task_execution_error after 101,256 ms, produced zero files, and had an empty deliverable summary. It was the shortest execution in the sample; every successful task produced at least one file. This points to an execution-stage abort before artifact registration rather than a demonstrated deliverable-format defect, although the generic error and missing trace prevent a definitive root-cause determination.

The failure is sector-concentrated only in the limited descriptive sense that Government completed two of three tasks, while all other sectors completed every assigned task. The two other Government tasks—01d7e53e-0513-4109-a242-8ccaf442cd21 and 17111c03-aac7-45c2-857d-c06d8223d6ad—successfully produced one and two files, respectively, so the evidence does not support a broad Government-sector failure mode. The failed occupation, First-Line Supervisors of Police and Detectives, appears only once. Repeated occupations did not reveal instability: both Buyers and Purchasing Agents tasks, 05389f78-589a-473c-a4ae-67c61050bfca and 15ddd28d-8445-4baa-ac7f-f41372e1344e, succeeded, as did both Software Developers tasks, 0e386e32-df20-4d1f-b536-7159bc409ad5 and 2c249e0f-4a8c-4f8e-b4f4-6508ba29b34f.

There were no retried-but-not-improved tasks because retried was false for all 25 executions. Consequently, retry effectiveness cannot be assessed, and the sole error received no automated recovery attempt. Self-QA is also missing for every task: all qa_score values are null, while empty qa_issues arrays and blank suggestions indicate absent measurement rather than evidence of issue-free output. No low-Self-QA cluster or latency-to-Self-QA relationship can therefore be identified.

Complexity and long latency were not associated with the observed failure. Task 0e386e32-df20-4d1f-b536-7159bc409ad5 successfully created 93 files in 1,590,554 ms; 0419f1c3-d669-45d0-81cd-f4d5923b06a5 completed a one-file deliverable in 1,317,985 ms; and 02aa1805-c658-4069-8a6a-02dec146063a completed two files in 1,015,911 ms. The two slowest sectors, Professional, Scientific, and Technical Services and Real Estate and Rental and Leasing, had complete execution success. Successful outputs also covered documents, spreadsheets, PDFs, presentations, audio packages, ZIP archives, APIs, and software repositories, leaving no observed deliverable-type failure cluster. However, status success confirms workflow completion only; it does not establish artifact correctness.

## Recommendations

First, improve error observability and recovery around generic TaskExecutionError events. For each run, retain the CLI exit code, stderr, model/tool trace, last completed phase, resource usage, token and tool-call limits, and artifact-write events. Re-execute 11e1b169-5fb6-4d79-8a83-82ddf4987a85 in a clean workspace with identical configuration to determine whether the error is reproducible. Add one or two idempotent retries with backoff for classified transient failures such as process crashes, service errors, or temporary tool failures; deterministic policy, prompt, or validation failures should instead be surfaced without repeated blind retries.

Use task-aware execution budgets rather than a restrictive global timeout. Successful tasks required as much as 1,590,554 ms, while the only failure stopped after 101,256 ms, so the evidence does not implicate excessive runtime. Instrument separate inference, research, rendering, validation, and packaging phases to explain the high latencies in tasks such as 0e386e32-df20-4d1f-b536-7159bc409ad5 and 0419f1c3-d669-45d0-81cd-f4d5923b06a5. Allocate larger tool-call and runtime budgets to software, analytical workbook, and document-rendering tasks, while using templates, cached dependencies, and bounded validation commands to reduce avoidable overhead.

Strengthen prompts with an explicit deliverable contract: required filenames, formats, output directory, minimum content, validation steps, and a final artifact manifest. Require a preflight plan before tool execution and an atomic write-then-validate workflow so that partial artifacts are distinguishable from an execution abort. For the failed police-supervisor task, run an A/B diagnosis using the original prompt and a decomposed version that separates content generation from file rendering; this can isolate whether the failure arose from prompt handling, a particular tool, or the packaging stage without assuming a sector-wide problem.

Restore Self-QA as a required, schema-validated pipeline output before tuning any QA threshold. A missing score should be recorded as qa_missing and should not be interpreted as either a pass or a low score. Pair Self-QA with deterministic artifact checks: file existence and nonzero size, Office/PDF parseability, page or slide counts, spreadsheet formula checks, ZIP integrity, OpenAPI linting, and automated tests for code repositories. Keep execution success separate from artifact-validation success, then calibrate retry or review thresholds only after a representative set of actual Self-QA measurements and validator outcomes has been collected.

## Deliverable Files

- `0ed38524…` (Finance and Insurance): 3 file(s)
- `01d7e53e…` (Government): 1 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 2 file(s)
- `38889c3b…` (Information): 11 file(s)
- `05389f78…` (Manufacturing): 2 file(s)
- `02aa1805…` (Professional, Scientific, and Technical Services): 2 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 1 file(s)
- `105f8ad0…` (Wholesale Trade): 2 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `1d4672c8…` (Finance and Insurance): 2 file(s)
- `0353ee0c…` (Health Care and Social Assistance): 1 file(s)
- `3a4c347c…` (Information): 1 file(s)
- `11dcc268…` (Manufacturing): 1 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 93 file(s)
- `0818571f…` (Real Estate and Rental and Leasing): 3 file(s)
- `1137e2bb…` (Wholesale Trade): 2 file(s)
- `045aba2e…` (Retail Trade): 3 file(s)
- `3600de06…` (Finance and Insurance): 4 file(s)
- `17111c03…` (Government): 2 file(s)
- `0ec25916…` (Health Care and Social Assistance): 2 file(s)
- `3baa0009…` (Information): 3 file(s)
- `15ddd28d…` (Manufacturing): 2 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
- `0e4fe8cd…` (Real Estate and Rental and Leasing): 1 file(s)
