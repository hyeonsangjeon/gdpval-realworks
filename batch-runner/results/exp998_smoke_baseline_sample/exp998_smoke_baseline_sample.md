# exp998_smoke_baseline_sample: Smoke Baseline Run (Sample)

- **Condition**: Baseline
- **Model**: gpt-5.2-chat
- **Mode**: code_interpreter
- **Date**: 2026-02-24
- **Duration**: 22m 39s

## Summary

| Metric | Value |
|--------|-------|
| Total tasks | 3 |
| Success | 3 (100%) |
| Error | 0 |
| QA failed | 0 |
| Retried tasks | 0 |
| Resume rounds used | 0 |
| Avg latency | 444,459ms |
| Max latency | 670,899ms |
| Total LLM time | 1333s |

## QA Statistics

| Metric | Value |
|--------|-------|
| Avg score | 8.67 / 10 |
| Min score | 8 / 10 |
| Max score | 9 / 10 |
| Passed | 3 |
| Failed | 0 |

## Results by Task

| # | Task ID | Sector | Occupation | Status | Retry | Files | QA | Time |
|---|---------|--------|------------|--------|-------|-------|----|------|
| 1 | `0419f1c3…` | Real Estate and Rent | Property, Real  | ✅ success | - | 1 | 8/10 | 670899ms |
| 2 | `dfb4e0cd…` | Government | Compliance Offi | ✅ success | - | 1 | 9/10 | 61181ms |
| 3 | `a328feea…` | Government | Administrative  | ✅ success | - | 1 | 9/10 | 601296ms |

## Sector Breakdown

| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |
|--------|-------|---------|----------|--------|-------------|
| Government | 2 | 2 | 100% | 9.0/10 | 331,239ms |
| Real Estate and Rental and Leasing | 1 | 1 | 100% | 8.0/10 | 670,899ms |

## QA Issues

### ✅ `0419f1c3…` — score 8/10
- Training modules lack explicit written justification linking each to specific performance gaps.
- Task volume is mentioned but not clearly analyzed as a performance gap.
- Text response summarizes deliverable rather than restating key findings.
  > 💡 Add brief justifications for each training and clarify whether task volume requires improvement.

### ✅ `a328feea…` — score 9/10
- Procedure does not specify alternate contact if Supervisor or Team Lead is unreachable.
  > 💡 Add a clear secondary contact process when the primary supervisor cannot be reached.


## Deliverable Files

- `0419f1c3-d669-45d0-81cd-f4d5923b06a5`: deliverable_files/0419f1c3-d669-45d0-81cd-f4d5923b06a5/Performance_Improvement_Plan_John_Miller.docx
- `dfb4e0cd-a0b7-454e-b943-0dd586c2764c`: deliverable_files/dfb4e0cd-a0b7-454e-b943-0dd586c2764c/Spending_Rate_Compliance_Analysis_As_of_2025-03-31.xlsx
- `a328feea-47db-4856-b4be-2bdc63dd88fb`: deliverable_files/a328feea-47db-4856-b4be-2bdc63dd88fb/Reporting_of_Unscheduled_Absence_or_Lateness_Policy.docx