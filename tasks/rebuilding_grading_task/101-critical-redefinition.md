# 101 — Critical Redefinition

> PR1 / 2 of 5. Depends on 100 (`model_did_right`).

## 목적

기존 `critical = required is True OR (max_score >= 4)` 정의를 폐기하고 `critical = abs(max_score) >= MAGNITUDE_THRESHOLD`로 재정의. `required` 필드는 220 task 10,453 item 전부 `null`로 확인되어 dead code (SCORE_MATH_AUDIT 참조).

또 `critical_item_pass_rate` 집계를 raw `verdict == "pass"` 대신 `model_did_right`(100에서 추가)로 전환.

## 결정 (자율)

- `MAGNITUDE_THRESHOLD = 4` 상수, `core/grader.py` 상단에 분리.
- 컨벤션 명시 주석: "GDPVal `required` field is null across all observed rubrics; we use weight-magnitude as a project-level proxy for criticality."
- `required is True` 분기 자체는 코드에서 제거 (dead — 향후 GDPVal upstream이 채우면 그때 재도입).
- `critical_fail` (task-level) 계산도 `model_did_right`로 통일.
- `critical_item_pass_rate` (summary-level) = critical 집합 안에서 `model_did_right` 평균.

## 영향 파일

- `batch-runner/core/grader.py` — `MAGNITUDE_THRESHOLD` 상수, `_aggregate`에서 critical 마스크 적용, `critical_fail` 재계산
- `batch-runner/step8_grade.py` — `_build_grade_payload`에서 `summary.wow.critical_item_pass_rate` 계산 로직 update
- `batch-runner/tests/test_grader.py` — critical 정의 변경 회귀 테스트 (397→483 magnitude 합 검증; per-item critical bool)
- `batch-runner/tests/test_step8_grade.py` — summary critical_item_pass_rate 계산 검증

## Acceptance

- 새 critical 정의로 exp003 hybrid grade JSON 재집계 시 critical pair count가 397 → 483 (positive 397 + negative 86) 일치 (SCORE_MATH_AUDIT 수치와 매치)
- 기존 ITEM-level verdict/awarded_score 값 변화 없음 (정의만 바뀜)
- legacy `required is True` 참조 코드 0건 (grep으로 확인)

## Out of scope

- `total_max` 계산 결함 → 102
- summary 외 다른 metric 변경 안 함 (`avg_score_pct`는 102에서)
