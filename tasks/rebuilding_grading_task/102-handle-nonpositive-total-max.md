# 102 — Non-Positive total_max Handling

> PR1 / 3 of 5. Independent of 100/101 ordering but shipped after for
> cleaner regression bisect.

## 목적

`TaskRubric.max_score = sum(it.score for it in rubric_items)` 이 양수+음수 산술 합산이라 4개 exp003 task에서 `total_max <= 0`. 현재 `pct = max(0, min(100, total_awarded / total_max * 100))` clamp가 수학적으로 무의미한 값을 가리고 있다. SCORE_MATH_AUDIT.md 참조.

## 결정 (자율)

SCORE_MATH_AUDIT의 3가지 옵션 중 **Option 1 (positive-only denominator)** 채택. 이유:
- single-line change
- 시멘틱 명확 ("최대 획득 가능 점수" = positive only)
- negative penalty는 `total_awarded`에서만 차감 (현 동작 그대로)
- pct는 [floor, 100] 범위 — floor는 catastrophic violation을 정직하게 음수로 표현
- 후속 옵션 2 (별도 critical_violations 필드) / 옵션 3 (sign-aware 전면)는 v2 schema에서 추가 여지

구현:
- `TaskRubric.max_score` property 변경: `sum(max(0, it.score) for it in rubric_items)`. 양수-only 분모.
- `_aggregate`의 pct 계산은 그대로 (`pct = total_awarded / total_max * 100`). `total_max=0`은 task에 양수 item이 하나도 없는 edge case — pct=0 처리 + 경고 로그.
- clamp `max(0, min(100, pct))` 유지 (schema v1.0 [0,100] 호환). 단 clamp 이전 raw pct를 `pct_raw` 필드로 추가 emit하여 음수 floor가 보이도록 함.

## 영향 파일

- `batch-runner/core/rubric_loader.py` — `TaskRubric.max_score` property 수정 + docstring update
- `batch-runner/core/grader.py` — `_aggregate`에서 `pct_raw` 새 필드 채움 (`pct` 변경 없음)
- `batch-runner/schemas/grade.schema.json` — `tasks[].pct_raw` (optional number; can be < 0)
- `batch-runner/tests/test_rubric_loader.py` — 양수-only 합산 검증
- `batch-runner/tests/test_grader.py` — `total_max=0` edge case, 음수 `pct_raw` 보존, clamp된 `pct` 동작

## Acceptance

- exp003 4개 문제 task (`6074bba3-7e3`, `e222075d-5d6`, `c94452e4-39c`, `ff85ee58-bc9`) 재집계 시 `total_max > 0` 보장
- `pct_raw`가 음수일 수 있으나 schema-valid `pct`는 항상 [0,100]
- 220 task 중 hybrid run의 18개 negative-impacted task에서 `pct_raw <= pct` (음수 penalty가 진실되게 표현됨)
- 기존 schema 호환 — `pct_raw`는 optional이라 v1 grade JSON 로딩 안 깨짐

## Out of scope

- summary-level `avg_score_pct` 재정의 (clamp된 pct 평균 그대로 유지) — published 헤드라인 안정성 위해 PR3에서 재고
- `pct_raw`의 대시보드 노출은 PR2/3 dashboard task에서
