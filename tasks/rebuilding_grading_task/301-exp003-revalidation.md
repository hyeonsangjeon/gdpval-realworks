# 301 — exp003 Re-grading + Formatting Gap Collapse + Bare-CSV Disambiguation

> PR3 / 2 of 4. SPEC §7-2, §7-3 합침.

## 목적

기존 hybrid vs mini 격차의 핵심이었던 formatting 항목이 v2 grader에서 실제로 해소되는지 검증. + bare CSV vs 진짜 xlsx 구분이 evidence에 명시되는지.

## 작업

1. exp003 220 task를 v2 grader로 재채점 → `exp003_*__gpt-5_4-v2sm__<rubric>__v2.json`
2. `scripts/stratify_critical_gap_v2.py`로 v1 mini vs v2 비교
   - 기대: formatting bucket 격차 -25.5pp → 거의 0 (또는 양수)
   - 기대: 잘 만든 deliverable의 "Overall formatting and style" 항목 점수 회복
3. bare CSV vs xlsx 구분: hybrid 샘플에서 거론된 task 5개 (`27e8912c`, `43dc9778`, `7b08cd4d`, `7d7fc9a7`, `83d10b06`) 정성 검토
   - evidence에 "openpyxl loaded, has cell formatting"  vs "openpyxl failed, file is plain CSV" 등이 구분되어 있는지

## Acceptance

- formatting bucket 격차 절댓값 < 5pp (붕괴)
- 5개 sample task의 evidence가 file type 명시 (xlsx/csv 구분)
- 보고서 `tasks/rebuilding_grading_task/PR3_EXP003_REVALIDATION.md`
