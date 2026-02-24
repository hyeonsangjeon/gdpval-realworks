# exp999_smoke_baseline_sample: Smoke Baseline Run (Sample)

- **Condition**: Baseline
- **Model**: gpt-5.2-chat
- **Mode**: code_interpreter
- **Date**: 2026-02-24
- **Duration**: 7m 9s

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 3 |
| Success | 3 (100%) |
| Error | 0 |
| QA failed | 0 |
| Retried tasks | 0 |
| Resume rounds used | 0 |
| Avg latency | 135,629ms |
| Max latency | 288,879ms |
| Total LLM time | 406s |

## QA Statistics

| Metric | Value |
|--------|-------|
| Avg score | 8.33 / 10 |
| Min score | 7 / 10 |
| Max score | 9 / 10 |
| Passed | 3 |
| Failed | 0 |

## Results by Task

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA | Time |
|---|---------|--------|------------|--------|-------|-------|----|------|
| 1 | `0419f1c3…` | Real Estate and Rent | Property, Real  | ✅ success | - | 1 | 7/10 | 88873ms |
| 2 | `dfb4e0cd…` | Government | Compliance Offi | ✅ success | - | 1 | 9/10 | 288879ms |
| 3 | `a328feea…` | Government | Administrative  | ✅ success | - | 1 | 9/10 | 29134ms |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Government | 2 | 2 | 100% | 9.0/10 | 159,007ms |
| Real Estate and Rental and Leasing | 1 | 1 | 100% | 7.0/10 | 88,873ms |

## QA Issues

### ✅ `0419f1c3…` — score 7/10
- Summary lacks quantified analysis of 4-hour acknowledgement compliance.
- Task volume metrics from the Work Order Log are not explicitly analyzed.
  > 💡 Add quantified acknowledgement and task volume metrics to strengthen data-driven justification.

### ✅ `a328feea…` — score 9/10
- No alternate contact is specified if the supervisor or team lead is unreachable.
- The procedure does not state consequences for non-compliance.
  > 💡 Add an alternate contact protocol and brief non-compliance consequences to strengthen clarity and enforcement.


## Deliverable Files

- `0419f1c3-d669-45d0-81cd-f4d5923b06a5`: deliverable_files/0419f1c3-d669-45d0-81cd-f4d5923b06a5/John_Miller_PIP_July_2025.docx
- `dfb4e0cd-a0b7-454e-b943-0dd586c2764c`: deliverable_files/dfb4e0cd-a0b7-454e-b943-0dd586c2764c/Spending_Rate_Compliance_Analysis.xlsx
- `a328feea-47db-4856-b4be-2bdc63dd88fb`: deliverable_files/a328feea-47db-4856-b4be-2bdc63dd88fb/Reporting_of_Unscheduled_Absence_or_Lateness_Procedure.docx