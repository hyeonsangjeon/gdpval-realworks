# 302 — Cost Budget Re-estimation

> PR3 / 3 of 4. SPEC §9 / §7 implicit.

## 목적

v2 grader (tool-calling + vision + audio)의 실제 비용 측정. $2,400/월 예산 안에 들어오는지 확인.

## 작업

1. exp003 v2 채점 시 토큰/시간 추적 (`scripts/analyze_grade_run.py`가 자동 수집)
2. 220 task 환산 비용 계산:
   - 메인 judge (gpt-5.4 medium) input/output 토큰
   - tool 호출 횟수 평균
   - vision 호출 횟수 (per task cap 5 적용 시)
   - audio 호출 횟수
3. 월 capacity 계산: $2,400 / per-run cost
4. 보고서 `tasks/rebuilding_grading_task/PR3_COST_BUDGET.md`

## Acceptance

- per-run cost < $50 (이전 mini $18 대비 3× 이내)
- 월 capacity ≥ 30 runs
- 만약 초과 시:
  - vision/audio cap 강화
  - 또는 routing pattern 좁히기 (예: vision은 명시적 visual 키워드 있는 항목만)
