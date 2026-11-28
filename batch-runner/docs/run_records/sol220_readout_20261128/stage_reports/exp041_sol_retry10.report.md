# Experiment Report: Codex command-line tool against Foundry — GPT-5.6 Sol, exp039's and exp040's ten Azure-side failures, solved again

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp041_sol_retry10` |
| **Condition** | Codex command-line tool, Foundry deployment |
| **Model** | gpt-5.6-sol |
| **Execution Mode** | codex_foundry |
| **Date** | 2026-11-27 |
| **Duration** | 122m 18s |
| **Generated At** | 2026-11-27T09:18:56.124211+00:00 |
| 🤗 HF Target | [HyeonSang/exp041_sol_retry10](https://huggingface.co/datasets/HyeonSang/exp041_sol_retry10) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 10 / 10 tasks (100.0%) |
| Priced | 0 / 10 receipts |
| Receipt status | partial — the figures below are a floor |
| Recorded so far | no record |
| Average per task | no record |
| Median | no record |
| P95 | no record |
| Max | no record |
| Per successful deliverable | no record |
| Failed tasks | 0 ($0.0000) |
| Not priced | call_reachability_unknown, price_missing, usage_partial |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `1659e9f4205e…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This experiment ran gpt-5.6-sol through the Codex command-line tool against a Foundry deployment in codex_foundry mode. It re-executed ten tasks associated with prior Azure-side failures. All 10 tasks completed successfully, yielding a 100% task completion rate with zero execution errors and zero within-run retries.

Self-QA confidence was not measured: no task produced a Self-QA value, so the average, minimum, and maximum are absent rather than zero. Consequently, LLM-evaluated quality cannot be inferred from this run despite complete task execution.

Mean latency was 733,850 ms per task, approximately 12.2 minutes. Every sector achieved full completion. The summary does not include file-level generation or validation results, so successful task status establishes workflow completion but does not independently establish deliverable file quality.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 10 |
| Success | 10 (100.0%) |
| Errors | 0 |
| Retried Tasks | 0 |
| Avg QA Score | - |
| Min QA Score | - |
| Max QA Score | - |
| Avg Latency | 733,850ms |
| Max Latency | 1,095,441ms |
| Total LLM Time | 7338s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 9 |
| Successfully generated | 9 (100.0%) |
| Failed (empty outputs preserved) | 0 |

## Quality Analysis

There is no Self-QA score distribution to analyze because none of the ten tasks emitted a score. No claims about self-assessed confidence, score consistency, or LLM-evaluated quality are supported by the available measurements.

Sector completion was uniformly successful: Finance and Insurance, Manufacturing, and Real Estate and Rental and Leasing each completed 2/2 tasks, while the other four sectors completed 1/1. Sector-level Self-QA comparisons are unavailable because every sector lacks QA measurements.

Latency varied substantially by sector. Wholesale Trade had the lowest average at 379,862 ms, followed by Health Care and Social Assistance at 570,858 ms. Real Estate and Rental and Leasing had the highest average at 920,325 ms, narrowly above Manufacturing at 919,042 ms; the observed sector-average range was 540,463 ms.

No occupation-level breakdown or per-deliverable evidence was supplied, so occupation-specific performance and file-generation quality cannot be characterized. Because Self-QA is absent, no latency-to-quality correlation can be evaluated; the data support only latency and completion comparisons.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Finance and Insurance | 2 | 2 | 100.0% | - | 623,787ms |
| Government | 1 | 1 | 100.0% | - | 628,311ms |
| Health Care and Social Assistance | 1 | 1 | 100.0% | - | 570,858ms |
| Manufacturing | 2 | 2 | 100.0% | - | 919,042ms |
| Real Estate and Rental and Leasing | 2 | 2 | 100.0% | - | 920,325ms |
| Retail Trade | 1 | 1 | 100.0% | - | 833,159ms |
| Wholesale Trade | 1 | 1 | 100.0% | - | 379,862ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `2fa8e956…` | Real Estate and Rental | Concierges | ✅ success | - | 2 | - | 826698ms |
| 2 | `46b34f78…` | Finance and Insurance | Financial and Inve | ✅ success | - | 1 | - | 1026186ms |
| 3 | `4c18ebae…` | Government | Compliance Officer | ✅ success | - | 2 | - | 628311ms |
| 4 | `5a2d70da…` | Manufacturing | Mechanical Enginee | ✅ success | - | 2 | - | 1095441ms |
| 5 | `efca245f…` | Manufacturing | First-Line Supervi | ✅ success | - | 3 | - | 742643ms |
| 6 | `f1be6436…` | Health Care and Social | Medical Secretarie | ✅ success | - | 8 | - | 570858ms |
| 7 | `f2986c1f…` | Retail Trade | Pharmacists | ✅ success | - | 1 | - | 833159ms |
| 8 | `f3351922…` | Finance and Insurance | Customer Service R | ✅ success | - | 1 | - | 221388ms |
| 9 | `f5d428fd…` | Real Estate and Rental | Concierges | ✅ success | - | 1 | - | 1013952ms |
| 10 | `f841ddcf…` | Wholesale Trade | Order Clerks | ✅ success | - | 1 | - | 379862ms |

## Recommendations

Preserve the current deployment configuration as an execution baseline because it achieved 10/10 completion without retries, but make QA telemetry mandatory. Each task should emit a structured record containing expected and produced files, hashes, openability checks, requirement-level pass/fail results, a non-null Self-QA score, identified issues, and remediation suggestions. Treat missing QA as a distinct QA-unavailable state rather than as either success or a zero score; all 10 task_ids demonstrate the need for this separation.

Add artifact-specific acceptance checks directly to prompts and execute them before reporting completion. For 2fa8e956-7b35-4c13-95dc-027f02be318b and f5d428fd-b38e-41f0-8783-35423dab80f6, verify rendered page counts, typography, hyperlinks, image presence, and attribution. For spreadsheet tasks 5a2d70da-0a42-4a6b-a3ca-763e03f070a5, efca245f-c24f-4f75-a9d5-59201330ab7a, f2986c1f-2bbf-4b83-bc93-624a9d617f45, and f841ddcf-2a28-4f6d-bac3-61b607219d3e, open each workbook in a calculation-capable engine and check required sheets, formulas, totals, data types, broken references, and recalculation results. Add domain-specific factual or compliance review for the finance memo 46b34f78-6c06-4416-87e2-77b6d8b20ce9, SAR task 4c18ebae-dfaa-4b76-b10c-61fcdf26734c, and medication task f2986c1f-2bbf-4b83-bc93-624a9d617f45; reconcile shared values across the eight files from f1be6436-ffff-4fee-9e66-d550291a1735.

Instrument phase-level latency for research, generation, file conversion, rendering, and validation. The observed maximum was approximately 18.3 minutes for 5a2d70da-0a42-4a6b-a3ca-763e03f070a5, with 46b34f78-6c06-4416-87e2-77b6d8b20ce9 and f5d428fd-b38e-41f0-8783-35423dab80f6 also above 16.8 minutes; if an external timeout is required, use at least a 25-minute budget while collecting better phase data. Cache reusable official sources and templates, and parallelize independent validation where safe. Do not allocate runtime solely by file count, because f1be6436-ffff-4fee-9e66-d550291a1735 produced eight files faster than several one-file tasks.

Do not tune a quality-score threshold until non-null scores exist and are calibrated against independent artifact checks. First enforce 100% QA coverage: a null score should trigger one bounded QA-only evaluation rather than regenerating an already completed deliverable. Reserve full-task retries for transient tool, network, conversion, or file-open failures, and log whether the targeted retry corrected the specific defect. After enough validated samples are collected, calibrate separate thresholds by deliverable type—documents, PDFs, spreadsheets, and regulated-domain content—rather than applying one global threshold across these heterogeneous tasks.

## Deliverable Files

- `2fa8e956…` (Real Estate and Rental and Leasing): 2 file(s)
- `46b34f78…` (Finance and Insurance): 1 file(s)
- `4c18ebae…` (Government): 2 file(s)
- `5a2d70da…` (Manufacturing): 2 file(s)
- `efca245f…` (Manufacturing): 3 file(s)
- `f1be6436…` (Health Care and Social Assistance): 8 file(s)
- `f2986c1f…` (Retail Trade): 1 file(s)
- `f3351922…` (Finance and Insurance): 1 file(s)
- `f5d428fd…` (Real Estate and Rental and Leasing): 1 file(s)
- `f841ddcf…` (Wholesale Trade): 1 file(s)
