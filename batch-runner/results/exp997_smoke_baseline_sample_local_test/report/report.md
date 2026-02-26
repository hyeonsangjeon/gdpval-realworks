# Experiment Report: Smoke Baseline Run (Sample)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp997_smoke_baseline_sample_local_test` |
| **Condition** | Baseline |
| **Model** | gpt-5.2-chat |
| **Execution Mode** | subprocess |
| **Date** | 2026-02-26 |
| **Duration** | 1m 1s |
| **Generated At** | 2026-02-26T07:14:47.691902+00:00 |

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores from evaluators are not yet available at this stage.

The Smoke Baseline Run (Sample) experiment executed two tasks under the Baseline condition using the gpt-5.2-chat model in subprocess mode. All tasks completed successfully, yielding a 100% task completion rate with no execution errors or retries. The experiment served as a lightweight validation of end-to-end task handling, latency capture, and self-assessment reporting.

Based on the LLM’s self-assessed confidence during execution, overall task quality was high, with an average self-QA score of 8.5/10. Scores ranged narrowly between 8 and 9, suggesting consistent internal confidence across tasks. Average latency was 24.9 seconds, with noticeable variance between tasks, highlighting early signals about execution time sensitivity by sector rather than instability or failure.

Key highlights include clean task completion across both tested sectors and successful generation of expected deliverables without retries, indicating that the baseline configuration is functionally sound for small-scale validation runs.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 2 |
| Success | 2 (100.0%) |
| Errors | 0 |
| Retried Tasks | 0 |
| Avg QA Score | 8.5/10 |
| Min QA Score | 8/10 |
| Max QA Score | 9/10 |
| Avg Latency | 24,870ms |
| Max Latency | 34,852ms |
| Total LLM Time | 49s |

## File Generation

| Metric | Value |
|--------|-------|
| Tasks requiring files | 185 |
| Successfully generated | 2 (1.1%) |
| Failed → dummy created | 0 |

## Quality Analysis

Self-QA scores indicate generally strong LLM-evaluated quality, with the Government sector task receiving a higher self-assessed confidence (9.0/10) than the Real Estate and Rental and Leasing task (8.0/10). This may reflect differences in task structure, prompt clarity, or domain familiarity rather than any correctness gap, as both tasks were completed without issue.

Latency showed a clear sector-level divergence: the Government task completed significantly faster (14.9s) than the Real Estate task (34.9s). This suggests that task complexity or output length in the Real Estate domain may be driving longer execution times. Despite this, there was no apparent degradation in self-assessed quality associated with higher latency.

Deliverable generation quality appears stable for this sample size, with no indications of partial outputs, truncation, or format issues reported. Given the limited scope, these results primarily validate baseline operability rather than robustness under varied or complex workloads.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Government | 1 | 1 | 100.0% | 9.0/10 | 14,888ms |
| Real Estate and Rental and Leasing | 1 | 1 | 100.0% | 8.0/10 | 34,852ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `0419f1c3…` | Real Estate and Rental | Property, Real Est | ✅ success | - | 3 | 8/10 | 34852ms |
| 2 | `dfb4e0cd…` | Government | Compliance Officer | ✅ success | - | 2 | 9/10 | 14888ms |

## QA Issues

### ✅ `0419f1c3…` — score 8/10
- Summary lacks quantified analysis of acknowledgement-time compliance against the 4-hour standard.
  > 💡 Add a clear acknowledgement-time KPI analysis using work order timestamps to strengthen data-driven justification.

## Recommendations

Increase task count and sector diversity in the next run to validate whether observed latency differences persist and to better characterize variability in self-assessed quality.

Instrument more granular timing metrics (e.g., prompt processing vs. generation time) to help attribute latency differences to specific execution phases.

Introduce slightly more complex or longer-form tasks to stress-test deliverable generation quality and observe how self-QA confidence scales with increased task difficulty.

## Deliverable Files

- `0419f1c3…` (Real Estate and Rental and Leasing): 3 file(s)
- `dfb4e0cd…` (Government): 2 file(s)
