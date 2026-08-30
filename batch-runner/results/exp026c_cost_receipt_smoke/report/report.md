# Experiment Report: problem_solving_cost receipt smoke (GPT-5.4 low, 1 task)

| Field | Value |
|-------|-------|
| **Experiment ID** | `exp026c_cost_receipt_smoke` |
| **Condition** | GPT-5.4 low + sandbox + skills + audio/video perception |
| **Model** | gpt-5.4 |
| **Execution Mode** | sandbox |
| **Date** | 2026-08-30 |
| **Duration** | 2m 47s |
| **Generated At** | 2026-08-30T11:14:07.740818+00:00 |
| 🤗 HF Target | [HyeonSang/exp026c_cost_receipt_smoke](https://huggingface.co/datasets/HyeonSang/exp026c_cost_receipt_smoke) |
| 📊 Self-Report | Prepared locally; Step 7 upload requested but not verified by this report |
| 📊 Grading | ⏳ Awaiting external grading |

## Problem-Solving Cost

> Usage-based estimate, not an Azure invoice amount.

| Metric | Value |
|--------|-------|
| Coverage | 1 / 1 tasks (100.0%) |
| Receipt status | complete |
| Total | $0.2855 |
| Average per task | $0.2855 |
| Median | $0.2855 |
| P95 | $0.2855 |
| Max | $0.2855 |
| Per successful deliverable | no record |
| Failed tasks | 1 ($0.2855) |

- 🧾 Cost ledger: `cost_ledger.jsonl` (sha256 `de78e70a37c3…`)

## Execution Summary *(Self-Assessed, Pre-Grading)*

> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA) during task execution — not on external grading results. Actual grading scores are not yet available.

This smoke experiment ran one problem-solving cost-receipt task using GPT-5.4 low in sandbox execution mode with skills and audio/video perception enabled. The task belonged to the Professional, Scientific, and Technical Services sector.

The recorded task completion rate was 0%: the single task was not successful, although no execution error was reported. It required one retry, so the retry rate was 100%. This indicates that the unsuccessful result was not classified as a runtime failure.

Self-assessed confidence, represented by the Self-QA score, was 4.0/10. The run therefore showed limited LLM-evaluated quality despite completing without a reported error. No deliverable-file details were provided, so file generation, formatting, and usability cannot be assessed directly.

## Key Metrics

| Metric | Value |
|--------|-------|
| Total Tasks | 1 |
| Success | 0 (0.0%) |
| Errors | 0 |
| Retried Tasks | 1 |
| Avg QA Score | 4.0/10 |
| Min QA Score | 4/10 |
| Max QA Score | 4/10 |
| Avg Latency | 52,911ms |
| Max Latency | 52,911ms |
| Total LLM Time | 52s |

### Resume Rounds

| Round | Attempted | Recovered | Still Failed |
|-------|-----------|-----------|--------------|
| 2 | 1 | 0 | 1 |

## Quality Analysis

The Self-QA distribution contains only one observation: 4.0/10, with identical minimum, maximum, and average values. This is insufficient to evaluate score variance or consistency across tasks, but the available result reflects low-to-moderate self-assessed confidence.

Professional, Scientific, and Technical Services recorded 0/1 successful tasks, an average Self-QA score of 4.0/10, and average latency of 52,911 ms. Because this was the only represented sector, no sector-level comparison is possible. No occupation-level information was supplied, so occupation-specific patterns cannot be identified.

The sole task took approximately 52.9 seconds and required a retry. With only one observation, no latency-quality correlation can be established; the run only shows that this relatively long, retried execution still produced a 4.0/10 LLM-evaluated quality result and did not satisfy the success criterion.

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Professional, Scientific, and Technical  | 1 | 0 | 0.0% | 4.0/10 | 52,911ms |

## Task Results

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |
|---|---------|--------|------------|--------|-------|-------|----------|---------|
| 1 | `83d10b06…` | Professional, Scientif | Accountants and Au | ⚠️ qa_failed | Yes | 2 | 4/10 | 52911ms |

## QA Issues

### ❌ `83d10b06…` — score 4/10
- Sheet names do not match required titles.
- Selected sample tab is not copied from original Population sheet.
- Required entities and metrics coverage is not evidenced.
  > 💡 Rename tabs exactly and preserve original Population structure while proving all selection criteria coverage.

## Recommendations

Increase reasoning effort from the low setting for spreadsheet-based audit tasks and reserve a dedicated verification pass after workbook generation. For task 83d10b06-26d1-4636-a32c-23f92c57f30b, the model should have reopened the generated workbook, compared it with the source Population workbook, and validated exact worksheet names, header structure, selected-row provenance, formulas, and coverage before submission. A lower-variance configuration can also help prevent deviations from literal naming and formatting requirements.

## Deliverable Files

- `83d10b06…` (Professional, Scientific, and Technical Services): 2 file(s)
