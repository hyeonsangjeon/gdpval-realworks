# 100 — Sign-Aware Aggregate

> PR1 / 1 of 5. Sequenced before 101 because critical redefinition (101)
> depends on the sign-normalized `model_did_right` flag introduced here.

## 목적

채점 verdict를 부호 시멘틱 무관하게 통합 플래그 `model_did_right`로 정규화한다. 현재 `core/grader.py::_aggregate`와 그 호출자들이 `verdict == "pass"`를 모든 item에 일률 적용하는데, GDPVal rubric의 negative-magnitude penalty item에서는 `pass` = "위반 발생(점수 차감 적용)"이라 의미가 반대다.

## 결정 (자율)

- ItemGrade에 derived field `model_did_right: bool` 추가 (서버 저장; client는 raw verdict + score sign 보면 재계산 가능하지만 명시 저장이 forward compat에 좋음).
- 정규화 규칙: `did_right = verdict == "pass"` if `max_score >= 0` else `verdict != "pass"` (단, `judge_error`는 항상 `did_right = False` — 보수적).
- `_aggregate`는 task-level `model_did_right_rate`를 별도로 emit하지 않음 — 그건 critical 한정으로 101에서 계산.
- 이 task는 `did_right` 한 컬럼만 추가하고 기존 verdict/awarded_score 시멘틱은 건드리지 않음 — 회귀 최소화.

## 영향 파일

- `batch-runner/core/grader.py` — `ItemGrade` dataclass에 `model_did_right: bool` 필드, `_aggregate`에서 채움
- `batch-runner/schemas/grade.schema.json` — `tasks[].items[].model_did_right` (optional → required in PR3)
- `batch-runner/tests/test_grader.py` — 양수/음수 item에 대한 normalization 단위 테스트

## Acceptance

- 모든 기존 테스트 green
- 새 테스트: 양수 pass=True, 양수 fail=False, 음수 pass=False, 음수 fail=True, judge_error=False 4 케이스
- 기존 grade JSON 4개 (main에 있는 v1)는 건드리지 않음 — back-fill은 103에서

## Out of scope

- critical 재정의 → 101
- `total_max ≤ 0` 처리 → 102
- backfill → 103
