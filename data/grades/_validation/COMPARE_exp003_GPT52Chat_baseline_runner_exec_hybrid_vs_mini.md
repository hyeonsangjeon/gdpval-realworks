# Hybrid vs Mini Default — Pair-wise Validation (C′)

- hybrid_json: `exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-hybrid__11e7900__v1.json`
- mini_json  : `exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json`
- task pairs : 12

## Decision
- **PROCEED**
- rule  : ratio = hybrid/mini critical_pass; threshold = 0.7
- ratio : **0.778**
- hybrid critical_pass 0.400 / mini critical_pass 0.514 = 0.78 ≥ 0.7. Hybrid stays within tolerance; full run carries usable signal.

## Aggregate
| metric | hybrid | mini | Δ |
|---|--:|--:|--:|
| critical_item_pass_rate | 0.400 | 0.514 | -0.114 |
| avg_score_pct | 44.12 | 55.78 | -11.66 |
| hybrid stricter than mini on critical (tasks) | 1/12 (8.3%) |  |  |
| both flagged critical fails (agreement) | 10/12 (83.3%) |  |  |

## Per-task
| task_id | hybrid pct | mini pct | Δ | hybrid crit pass | mini crit pass |
|---|--:|--:|--:|--:|--:|
| `17111c03-aac7-45c2…` | 85.57 | 87.54 | -2.0 | None | None |
| `27e8912c-8bd5-44ba…` | 84.34 | 83.21 | +1.1 | 0.5 | 0.0 |
| `43dc9778-450b-4b46…` | 12.21 | 18.6 | -6.4 | 0.0 | 0.0 |
| `7b08cd4d-df60-41ae…` | 45.33 | 28.33 | +17.0 | 0.0 | 0.0 |
| `7d7fc9a7-21a7-4b83…` | 31.21 | 36.84 | -5.6 | 0.0 | 0.0 |
| `83d10b06-26d1-4636…` | 31.27 | 38.1 | -6.8 | 0.0 | 1.0 |
| `99ac6944-4ec6-4848…` | 42.56 | 51.83 | -9.3 | 1.0 | 1.0 |
| `a328feea-47db-4856…` | 80.83 | 82.08 | -1.2 | None | None |
| `c44e9b62-7cd8-4f72…` | 59.31 | 63.77 | -4.5 | 0.6666666666666666 | 0.6666666666666666 |
| `ee09d943-5a11-430a…` | 39.24 | 44.92 | -5.7 | 0.0 | 0.0 |
| `f84ea6ac-8f9f-428c…` | 76.98 | 75.96 | +1.0 | 0.6666666666666666 | 0.6666666666666666 |
| `f9a1c16c-53fd-4c8f…` | 50.0 | 58.18 | -8.2 | 0.0 | 0.0 |

## Sample hybrid critical FAILs (top 3 per task, first 5 tasks)

### task `27e8912c-8bd5-44ba-ad87-…`  (mini_crit_pass=0.0)
- **partial** (judge, 1.0/4) `The Word document contains all items, including all columns with details corresponding to each item, listed in the check` — evidence: _Employee Name | Department | Email | Date Identified | Issue Identified | Organizational Action Item | Responsible Party | Status / Comments | Resolved By / Date
 |  |  |  |  |  |  |  |_

### task `43dc9778-450b-4b46-b77e-…`  (mini_crit_pass=0.0)
- **partial** (judge, 3.5/5) `Overall formatting and style of the deliverable` — evidence: _Payments, Adjustments, and Credits Considered - Federal income tax withheld per Wn2s - 2024 estimated tax payments totaling $13,685_

### task `7b08cd4d-df60-41ae-9102-…`  (mini_crit_pass=0.0)
- **partial** (judge, 4.0/5) `Overall formatting and style of the deliverable` — evidence: _2024 Fall Music Tour – Profit & Loss,,,,,,
As of 12/31/2024,,,,,,
Revenue,,,,,,
Date,City,Country,Gross Revenue USD,Withholding Rate,Withholding Tax USD,Net Revenue USD_

### task `7d7fc9a7-21a7-4b83-906f-…`  (mini_crit_pass=0.0)
- **partial** (judge, 3.75/5) `Overall formatting and style of the deliverable` — evidence: _[Sheet: Prepaid Summary]
Category,Amount
Total Prepaid Expenses,2567099.4
Total Prepaid Insurance,2835817.68
YTD Amortization – Expenses,145176.46
YTD Amortization – Insurance,78772.71999999999_

### task `83d10b06-26d1-4636-a32c-…`  (mini_crit_pass=1.0)
- **partial** (judge, 4.0/5) `Overall formatting and style of the deliverable` — evidence: _No,Division,Sub-Division,Country,Legal Entity,KRIs,Q3 2024 KRI,Q2 2024 KRI,QoQ Variance %,Sample Selected_
