# Experiment Report: Codex command-line tool against Foundry — thirty tasks

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp034_codex_foundry_trial30` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.4 |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-09-10 |
| **Duration** | 186m 28s |
| **Generated At** | 2026-09-11T02:11:31.330920+00:00 |
| 🤗 HF Target (bootstrap) | [HyeonSang/exp034_codex_foundry_trial30](https://huggingface.co/datasets/HyeonSang/exp034_codex_foundry_trial30) |
| 📊 Self-Report | Local artifact only (dry run; not published) |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 30 / 30 tasks (100.0%) |
| Priced | 0 / 30 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 8 (no record) |
| Not priced | call_reachability_unknown |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `544c96b9e186…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This run evaluated the Codex command-line tool against a Foundry deployment of gpt-5.4 across 30 tasks spanning nine sectors. It completed 22 tasks successfully, for a 73.3% task completion rate, while eight tasks ended in errors. No retries were attempted, so the results reflect first-attempt execution only.

Self-QA confidence was not measured: no task produced a Self-QA score, including the 22 successful tasks. Consequently, there is no distribution of self-assessed confidence or LLM-evaluated quality to analyze. The missing measurement must not be interpreted as either low or high quality.

Completion was strongest in Information, Manufacturing, and Retail Trade, each at 3/3. Real Estate and Rental and Leasing had the lowest completion rate at 1/3, followed by Government at 2/4. Finance and Insurance and Health Care and Social Assistance each completed 3/4 tasks.

Mean latency was 176,887 ms, approximately 177 seconds per task. Professional, Scientific, and Technical Services had the highest sector average at 392,939 ms, while Real Estate and Rental and Leasing had the lowest at 85,442 ms. Successful status indicates execution completion, but no file-level validation data were supplied to establish the correctness, integrity, or usability of generated deliverables.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 30 |
| Success | 22 (73.3%) |
| Errors | 8 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 176,887ms |
| Max Latency | 971,902ms |
| Total LLM Time | 5306s |

## Quality Analysis

A Self-QA score distribution cannot be reported because every QA field is absent. There are therefore no minima, maxima, averages, confidence bands, or outliers for self-assessed confidence. The eight execution errors explain missing outputs for failed tasks, but they do not explain the run-wide absence of LLM-evaluated quality measurements because the 22 completed tasks also produced no QA scores.

Sector completion rates varied substantially despite the small sample sizes. Information, Manufacturing, and Retail Trade achieved 100% completion; Finance and Insurance and Health Care and Social Assistance achieved 75%; Professional, Scientific, and Technical Services and Wholesale Trade achieved 66.7%; Government achieved 50%; and Real Estate and Rental and Leasing achieved 33.3%.

Reported latency does not show a simple relationship with completion. Information and Retail Trade combined relatively high average latencies of 277,818 ms and 226,474 ms with full completion, while Professional, Scientific, and Technical Services had the highest latency and completed 2/3 tasks. Conversely, Real Estate and Rental and Leasing had the lowest latency but the weakest completion rate. A latency-to-quality correlation cannot be calculated because Self-QA measurements are absent.

No occupation-level breakdown or task-level deliverable inspection results were provided, so occupation-specific quality patterns cannot be evaluated. Likewise, completion counts alone do not demonstrate deliverable file quality; assessing generation quality would require file-existence checks, format validation, content verification, or successful downstream use.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 4 | 3 | 75.0% | - | 181,835ms |
| Government | 4 | 2 | 50.0% | - | 107,010ms |
| Health Care and Social Assistance | 4 | 3 | 75.0% | - | 118,469ms |
| Information | 3 | 3 | 100.0% | - | 277,818ms |
| Manufacturing | 3 | 3 | 100.0% | - | 118,208ms |
| Professional, Scientific, and Technical  | 3 | 2 | 66.7% | - | 392,939ms |
| Real Estate and Rental and Leasing | 3 | 1 | 33.3% | - | 85,442ms |
| Retail Trade | 3 | 3 | 100.0% | - | 226,474ms |
| Wholesale Trade | 3 | 2 | 66.7% | - | 124,904ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `0ed38524…` | Finance and Insurance | Customer Service R | ✅ success | - | 3 | - | 93104ms |
| 2 | `01d7e53e…` | Government | Recreation Workers | ✅ success | - | 3 | - | 217307ms |
| 3 | `0112fc9b…` | Health Care and Social | Nurse Practitioner | ✅ success | - | 1 | - | 30415ms |
| 4 | `38889c3b…` | Information | Audio and Video Te | ✅ success | - | 8 | - | 311524ms |
| 5 | `05389f78…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | - | 133086ms |
| 6 | `02aa1805…` | Professional, Scientif | Project Management | ❌ error | - | 0 | - | 73416ms |
| 7 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 2 | - | 95352ms |
| 8 | `105f8ad0…` | Wholesale Trade | Sales Representati | ❌ error | - | 0 | - | 127836ms |
| 9 | `02314fc6…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 155073ms |
| 10 | `1d4672c8…` | Finance and Insurance | Securities, Commod | ❌ error | - | 0 | - | 51738ms |
| 11 | `11e1b169…` | Government | First-Line Supervi | ❌ error | - | 0 | - | 15212ms |
| 12 | `0353ee0c…` | Health Care and Social | First-Line Supervi | ❌ error | - | 0 | - | 64033ms |
| 13 | `3a4c347c…` | Information | Editors | ✅ success | - | 2 | - | 293363ms |
| 14 | `11dcc268…` | Manufacturing | Shipping, Receivin | ✅ success | - | 2 | - | 82581ms |
| 15 | `0e386e32…` | Professional, Scientif | Software Developer | ✅ success | - | 44 | - | 971902ms |
| 16 | `0818571f…` | Real Estate and Rental | Real Estate Broker | ❌ error | - | 0 | - | 54721ms |
| 17 | `1137e2bb…` | Wholesale Trade | Order Clerks | ✅ success | - | 3 | - | 115370ms |
| 18 | `045aba2e…` | Retail Trade | Pharmacists | ✅ success | - | 7 | - | 373503ms |
| 19 | `3600de06…` | Finance and Insurance | Personal Financial | ✅ success | - | 3 | - | 249407ms |
| 20 | `17111c03…` | Government | Administrative Ser | ✅ success | - | 3 | - | 119217ms |
| 21 | `0ec25916…` | Health Care and Social | Registered Nurses | ✅ success | - | 3 | - | 200019ms |
| 22 | `3baa0009…` | Information | News Analysts, Rep | ✅ success | - | 3 | - | 228568ms |
| 23 | `15ddd28d…` | Manufacturing | Buyers and Purchas | ✅ success | - | 3 | - | 138958ms |
| 24 | `2c249e0f…` | Professional, Scientif | Software Developer | ✅ success | - | 2 | - | 133499ms |
| 25 | `0e4fe8cd…` | Real Estate and Rental | Concierges | ❌ error | - | 0 | - | 106252ms |
| 26 | `15d37511…` | Wholesale Trade | Sales Representati | ✅ success | - | 4 | - | 131506ms |
| 27 | `0fad6023…` | Retail Trade | General and Operat | ✅ success | - | 2 | - | 150846ms |
| 28 | `4520f882…` | Finance and Insurance | Financial Managers | ✅ success | - | 2 | - | 333092ms |
| 29 | `1bff4551…` | Government | Recreation Workers | ❌ error | - | 0 | - | 76302ms |
| 30 | `116e791e…` | Health Care and Social | Registered Nurses | ✅ success | - | 2 | - | 179411ms |

## Failure Analysis

Across all 30 tasks, the eight failures share one operational signature: task_execution_error or TaskExecutionError, zero files, and an empty deliverable summary. The error records provide no subprocess exit code, model termination reason, stderr, or failed tool step, so they cannot be divided reliably into timeout, dependency, filesystem, input, or model-generation failures. Failed tasks averaged 71,189 ms, versus 215,323 ms for successful tasks, and every failure ended between 15,212 and 127,836 ms. This indicates early termination rather than excessive runtime: the 44-file software task 0e386e32-df20-4d1f-b536-7159bc409ad5 completed successfully in 971,902 ms. Latency is therefore more plausibly an effect of failure than a causal risk indicator.

Failures are concentrated by sector. Real Estate and Rental and Leasing failed 2 of 3 tasks, specifically 0818571f-5ff7-4d39-9d2c-ced5ae44299e and 0e4fe8cd-16d0-4f41-8247-6385b4762582. Government failed 2 of 4, specifically 11e1b169-5fb6-4d79-8a83-82ddf4987a85 and 1bff4551-1d54-4e37-b2e0-d5c3f2ea4a45. Those two sectors account for half of all errors despite representing only 7 of 30 tasks. Professional Services, Wholesale Trade, Finance, and Health Care each contributed one failure, while all Information, Manufacturing, and Retail Trade tasks completed. The sector samples are small, so this is a prioritization signal rather than evidence of an inherent sector limitation.

There is no consistent occupation or deliverable-complexity failure pattern. Recreation Workers produced both a success, 01d7e53e-0513-4109-a242-8ccaf442cd21, and a failure, 1bff4551-1d54-4e37-b2e0-d5c3f2ea4a45, suggesting task-specific inputs or execution variance rather than occupation alone. Repeated Software Developer, Buyers and Purchasing Agents, Registered Nurse, and Retail General and Operations Manager tasks all succeeded. Successful tasks also covered PDF, DOCX, XLSX, PPTX, Markdown, YAML, media/archive, and multi-file code outputs, including 2c249e0f-4a8c-4f8e-b4f4-6508ba29b34f and 0e386e32-df20-4d1f-b536-7159bc409ad5. Because failed tasks produced neither artifacts nor summaries, the supplied records do not support attributing failures to a particular file format.

No task was retried, so there are no retried-but-not-improved cases and retry effectiveness cannot be assessed. All eight errors are unrecovered first-attempt failures. Separately, Self-QA is missing for all 30 tasks, including all 22 completed tasks, which indicates a run-wide measurement or evaluator integration failure rather than a property of only the failed executions. Consequently, there are no low-Self-QA cases or latency-to-Self-QA relationships to compare. Files_count confirms artifact creation for completed tasks but does not establish that those artifacts are correct, parseable, complete, or usable.

## Recommendations

Replace the generic TaskExecutionError boundary with structured failure telemetry. Record the failing stage, last model or tool action, command and exit code, stdout and stderr tails, model finish reason, token and tool-call limits, elapsed idle time, resource usage, dependency versions, and whether any temporary artifact existed. Classify failures into transient service, command, dependency, permission, missing-input, context-limit, and timeout categories. This is especially important for the short failures 11e1b169-5fb6-4d79-8a83-82ddf4987a85 and 1d4672c8-b0a7-488f-905f-9ab4e25a19f7, which ended in 15 and 52 seconds but currently look identical to the 128-second failure 105f8ad0-8dd2-422f-9e88-2be5fbd2b215.

Add controlled recovery rather than a blanket timeout increase. Retry transient service, network, or tool-launch failures once with the same configuration and, if still transient, once with a clean workspace and exponential backoff; preserve both first-attempt and final outcomes. Use checkpointing and idempotent writes so a retry cannot corrupt prior artifacts. Do not derive the overall timeout from the 177-second mean, because task 0e386e32-df20-4d1f-b536-7159bc409ad5 legitimately required about 972 seconds. Instead, configure task-specific wall-clock and model/tool-call budgets, pair them with a shorter no-progress watchdog, and expose whether a limit caused termination. Keep model sampling and deployment settings fixed during diagnostic reruns, using lower-variance tool planning if supported, so infrastructure failures can be distinguished from execution variability.

Strengthen prompts and the execution environment around staged artifact production. Require the agent to inspect inputs and dependencies first, emit an explicit deliverable plan and expected filenames, create a minimal valid artifact early, enrich it incrementally, and finish with a manifest plus validation results. Preflight workspace permissions, disk space, required templates, renderers, office libraries, media tools, and network access before invoking the model. Apply format-specific checks such as opening DOCX, PPTX, XLSX, and ZIP files; parsing PDFs and YAML; validating OpenAPI documents; running code tests; and probing media files. The mixed Recreation Workers outcomes 01d7e53e-0513-4109-a242-8ccaf442cd21 and 1bff4551-1d54-4e37-b2e0-d5c3f2ea4a45 should be rerun with this identical scaffold to isolate prompt or input differences.

Restore Self-QA before tuning any numerical threshold. Make the evaluator a separately monitored step with schema validation requiring a score, issues list, and suggestion for every completed task; retry evaluator failures independently of task execution. Treat a missing Self-QA value as indeterminate rather than as a pass or a low score, and route it for re-evaluation. Until calibrated Self-QA data exist, use hard release gates: required artifacts must exist, expected extensions and counts must match, files must parse, and task-specific structural checks must pass. After collecting sufficient validated examples, choose thresholds using observed false-accept and false-reject rates and stratify by deliverable type where justified; the current sector samples are too small to support sector-specific thresholds.

## Deliverable Files

- `0ed38524…` (Finance and Insurance): 3 file(s)
- `01d7e53e…` (Government): 3 file(s)
- `0112fc9b…` (Health Care and Social Assistance): 1 file(s)
- `38889c3b…` (Information): 8 file(s)
- `05389f78…` (Manufacturing): 3 file(s)
- `0419f1c3…` (Real Estate and Rental and Leasing): 2 file(s)
- `02314fc6…` (Retail Trade): 2 file(s)
- `3a4c347c…` (Information): 2 file(s)
- `11dcc268…` (Manufacturing): 2 file(s)
- `0e386e32…` (Professional, Scientific, and Technical Services): 44 file(s)
- `1137e2bb…` (Wholesale Trade): 3 file(s)
- `045aba2e…` (Retail Trade): 7 file(s)
- `3600de06…` (Finance and Insurance): 3 file(s)
- `17111c03…` (Government): 3 file(s)
- `0ec25916…` (Health Care and Social Assistance): 3 file(s)
- `3baa0009…` (Information): 3 file(s)
- `15ddd28d…` (Manufacturing): 3 file(s)
- `2c249e0f…` (Professional, Scientific, and Technical Services): 2 file(s)
- `15d37511…` (Wholesale Trade): 4 file(s)
- `0fad6023…` (Retail Trade): 2 file(s)
- `4520f882…` (Finance and Insurance): 2 file(s)
- `116e791e…` (Health Care and Social Assistance): 2 file(s)
