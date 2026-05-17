# TASK_PR38_FOLLOWUP — extreme-reasoner CONDITION + MINOR 정리 (CLAUDE.md 제외)

PR #38(silent corruption fixes) 머지 전 보강. CLAUDE.md 트리거 정정은 gitignore라 로컬 only.

## 처리 항목 (3개)

### 1. CHANGELOG.md 엔트리 (CONDITION 2)
`CHANGELOG.md` 신규 생성 (없으면) 또는 `[Unreleased]` 섹션 추가. 커버:
- `qa_failed` 동작 변경 (이전 dead invariant)
- pre/post `qa_failed_count` 비교 불가
- compact-mode parquet 행 수 감소 가능 (`status=="success"` 필터)
- `resume_rounds_used` QA-enabled run에서 비0
- Cost guardrail 메모: 프로덕션 YAML(exp001~024) 전부 worst-case ≤6×, smoke YAMLs(exp997/998/999) 12~16× 이나 sample_size 2~3으로 실효 영향 미미
- 3 silent corruption fix 요약

### 2. step2_run_inference.py:1003-1005 docstring 정정 (MINOR 1)
Fix 3 적용 후 docstring과 실제 동작 일치.

### 3. subprocess_runner.py redundant write 제거 (MINOR 2)
Fix 1로 두 번째 write가 추가됐으니 첫 번째 write(line 248 부근)는 redundant. 동작 동일 보장하면서 제거.

## Out of Scope
- CLAUDE.md 트리거 정정 (gitignore라 PR 불가, 로컬 적용 완료)
- 3 silent corruption fix 본체 (4e0e43d, 이미 reviewed/locked)
- CONDITION 3 (post-merge 운영 관측)

## Acceptance
- 위 3 항목 변경
- V2 + silent-corruption 전 테스트 통과 (회귀 0)
- secrets 0
