# 303 — Variance + Bootstrap CI + judge_error Rate

> PR3 / 4 of 4. SPEC §7-4, §7-5.

## 목적

v2 grader의 통계적 신뢰도 검증.

## 작업

1. exp003 부분집합 (예: 첫 30 task) 3회 채점
2. per-task pct 분산 계산, bootstrap 95% CI
3. judge_error_rate < 2% 확인 (tool 경로 신뢰도)
4. judge_error_rate가 임계값 초과 시:
   - reasoning_effort medium → high 상향 후 재시도 (모델 교체보다 우선)
   - 그래도 안 되면 tool 호출 cap 조정
5. 보고서 `tasks/rebuilding_grading_task/PR3_VARIANCE.md`
6. 최종 `PR3_REPORT.md`로 PR3 종합

## Acceptance

- task-level pct 표준편차 ≤ 5pp (3 runs)
- judge_error_rate < 2%
- CI 95% 폭 < 10pp

## PR3 종료 = 전체 rebuild 종료

- 000-OVERVIEW.md task status 17개 모두 ✅
- CHANGELOG.md에 v2 grader rebuild 종합 entry
- main에 v2 grade JSON, v2 config, v2 prompt, v2 grader 코드 모두 commit
- 새 default = `default_v2.yaml`
- v1 grade JSON 4개는 history로 보존
