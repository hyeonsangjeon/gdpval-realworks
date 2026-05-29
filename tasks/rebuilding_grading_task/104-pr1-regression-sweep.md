# 104 — PR1 Regression Sweep + Report

> PR1 / 5 of 5. Final task before PR1 closes.

## 목적

100-103 변경이 published 헤드라인을 어떻게 바꿨는지 명시적으로 문서화. PR2(tool-calling rebuild)를 시작하기 전 PR1만으로 어디까지 신뢰가 회복됐는지 baseline 확립.

## 작업

1. **단위 회귀**: batch-runner 전체 pytest 통과 (>=470 passed / 0 failed). scripts/__tests__/ 통과.
2. **데이터 일관성**: 
   - exp003 v2sm 파일 vs `STRATIFY_v2_exp003_critical_gap.md` 헤드라인 일치 확인
   - exp998 smoke 2개 v2sm 파일이 schema v1.1 통과
3. **변화 보고서 `PR1_REPORT.md` 작성**:
   - exp003 hybrid: 기존 critical_pass 0.421 → 새 0.468 (sign-aware), 변동 폭
   - exp003 mini:   기존 critical_pass 0.518 → 새 0.596
   - 두 v2sm 격차: 0.596 - 0.468 = 0.128 (이전 0.097보다 큼) — 100/101로 더 정직해진 신호
   - 4개 nonpositive total_max task의 `pct_raw` (음수일 수도 있음) 기록
   - dashboard 영향 (`npm run aggregate` 정상 작동만 확인, UI는 PR2/3)
4. **CHANGELOG.md Unreleased 블록에 PR1 entry 추가**
5. **000-OVERVIEW.md task status 5개 ☐ → ✅ 일괄 업데이트**

## Acceptance

- pytest 전체 green
- PR1_REPORT.md commit
- CHANGELOG entry commit
- main에 새 v2sm 파일 4개 visible

## Next session handoff

PR1 종료 시 새 세션이 PR2를 시작하려면 다음만 알면 됨:
- `tasks/rebuilding_grading_task/PR1_REPORT.md` (PR1 결과)
- `tasks/rebuilding_grading_task/200~208-*.md` (PR2 spec, 이번에 작성됨)
- `tasks/rebuilding_grading_task/SPEC_GRADING_PIPELINE_V2.md` (전체 SPEC)
- `tasks/rebuilding_grading_task/000-OVERVIEW.md` (status board)

새 세션 prompt 예: "tasks/rebuilding_grading_task/200번부터 PR2 진행해줘. SPEC + OVERVIEW + PR1_REPORT.md 컨텍스트로 사용."
