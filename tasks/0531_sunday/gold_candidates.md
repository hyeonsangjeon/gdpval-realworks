# Gold candidates — owner hand-grading list (Phase 1)

GDPVal's `rubric_json` provides only `score` + `criterion` + optional `gold_deliverable_files` — **no per-item expected verdict** (pass/partial/fail) exists. Therefore the thesis (Phase 4) cannot be judged against dataset gold. This file lists the rubric items the owner must hand-grade to produce a gold set.

Total candidates: **19** (by modality: {'formatting': 6, 'audio': 1, 'visual': 12})

Selection rules:
- (1) every `visual` / `audio` criterion in the 10 shared exp003 tasks — perception's direct target
- (2) `critical_regression` (|max_score| >= 4 and v1-mini > v2-mini verdict)
- (3) `flip_nontext` (mini > standard verdict on non-text modality)

Hand-grading guide:
- Open the deliverable at `batch-runner/results/exp003*/<task>/...` (or HF parquet if not local).
- Decide the verdict **only** from the criterion text + the deliverable, without looking at any judge's verdict/evidence.
- Allowed verdicts: `pass`, `partial`, `fail`, or `unsure` (`unsure` is dropped from the gold set, not counted as judge_error).
- Record verdicts in a sibling file `gold_verdicts.json` keyed by `(task, rid)`.

## Candidates

| task | rid | modality | max | v_v1 | v_std | v_mini | reasons | criterion |
|---|---|---|---:|---|---|---|---|---|
| 7b08cd4d | cb62f0d1 | audio | 1 | pass | fail | fail | modality:audio | Band and Crew (Fees & Per Diem) includes Sound Technician: 8,256 USD, attributed to the t… |
| 27e8912c | 8e5445d2 | formatting | 5 | pass | partial | partial | critical_regression | Overall formatting and style of the deliverable |
| 7b08cd4d | ce2a2c8c | formatting | 5 | pass | partial | partial | critical_regression | Overall formatting and style of the deliverable |
| 7d7fc9a7 | d326173f | formatting | 2 | partial | fail | pass | flip_nontext:fail->pass | Delivers a single Excel workbook file in .xlsx format. |
| 7d7fc9a7 | 52b999af | formatting | 5 | partial | partial | fail | critical_regression | Overall formatting and style of the deliverable |
| 83d10b06 | a64588ed | formatting | 5 | pass | fail | partial | critical_regression,flip_nontext:fail->partial | Overall formatting and style of the deliverable |
| ee09d943 | 6f341d03 | formatting | 1 | partial | partial | pass | flip_nontext:partial->pass | The workbook uses March's template styling and tab sequence for shared tabs (e.g., consis… |
| 7d7fc9a7 | f01cd901 | visual | 1 | pass | pass | pass | modality:visual | Prepaid Summary presents totals for both accounts using a description-and-amount layout (… |
| 7d7fc9a7 | 7097fd4e | visual | 1 | pass | pass | pass | modality:visual | Expense classification uses chart-of-accounts numbers consistent with COA.xlsx (e.g., app… |
| c44e9b62 | e6238e73 | visual | 3 | pass | partial | partial | modality:visual | Mentions the revised organizational chart is targeting Administrative Support Services Br… |
| c44e9b62 | ec243233 | visual | 5 | pass | pass | pass | modality:visual | Includes both reduced FTEs and unfluctuating FTEs in the revised organizational chart. |
| c44e9b62 | c051b2a0 | visual | 5 | pass | pass | pass | modality:visual | Provides a revised organizational chart for the Administrative Support Services Branch as… |
| c44e9b62 | 3dbde6fa | visual | 10 | pass | pass | pass | modality:visual | Adopts Organizational Chart - Administrative Support Services Branch.pdf to mark the revi… |
| c44e9b62 | e88c958e | visual | 5 | pass | pass | pass | modality:visual | Highlights reductions consistently on the org chart with a legend or notation. |
| c44e9b62 | 0f98d9af | visual | 1 | pass | fail | pass | flip_nontext:fail->pass,modality:visual | Assumes each box in the organizational chart equals one FTE unless a number in parenthese… |
| c44e9b62 | 8e4bd2f6 | visual | 2 | fail | fail | fail | modality:visual | Matches reduced FTE numbers and titles of positions in the organizational chart as the on… |
| c44e9b62 | 7464e9eb | visual | 1 | pass | fail | pass | flip_nontext:fail->pass,modality:visual | Matches the FTE report’s Branch totals (Current and Planned) with the headcounts depicted… |
| c44e9b62 | 784c95fb | visual | 5 | partial | fail | partial | flip_nontext:fail->partial,modality:visual | Adopts the layout style of the reference chart sufficiently to allow a like-for-like comp… |
| c44e9b62 | 5c9e9ec0 | visual | 3 | pass | pass | pass | modality:visual | Reflects reduced FTEs where applicable (e.g., numbers in parentheses) on the revised orga… |
