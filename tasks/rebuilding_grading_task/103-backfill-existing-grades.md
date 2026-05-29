# 103 — Backfill Existing Grades

> PR1 / 4 of 5. Depends on 100/101/102.

## 목적

100-102 변경은 schema에 새 optional 필드를 추가하고 `critical_item_pass_rate` 집계 의미를 바꾼다. main에 이미 commit된 grade JSON 4개는 그 새 시멘틱을 모르기 때문에 published 헤드라인이 v1-시멘틱으로 멈춰 있다. **v1 파일은 보존**하고 **v2 명명으로 재계산본 추가**해서 v1/v2 직접 비교 가능 (back-fill 정책 (c) 합의).

## 결정 (자율)

- 신규 스크립트 `scripts/backfill_sign_aware.py`:
  - 입력: 기존 grade JSON 경로 (또는 디렉토리 glob)
  - 출력: 같은 디렉토리에 `<basename>__v2sm.json` (sm = sign-aware math) — v1 옆에 공존
  - 동작: per-item `model_did_right` 채움, `critical_item_pass_rate`/`avg_score_pct` 재집계, `pct_raw` per-task 채움, `schema_version: "1.1"`로 bump (`grade.schema.json` minor)
- schema v1.1: v1.0 superset (모든 v1 필드 그대로 + 100/102가 추가한 optional 필드)
- 새 파일은 같은 commit에 묶음 — v1 cache key 깨지 않음
- 4개 대상 파일:
  - `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-hybrid__11e7900__v1.json`
  - `data/grades/exp003_GPT52Chat_baseline_runner_exec__gpt-5_4-mini__11e7900__v1.json`
  - `data/grades/exp998_smoke_baseline_sample__gpt-5_4-mini__11e7900__v1.json`
  - `data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json`
- `dummy_gpt5_baseline.json`은 legacy demo data로 backfill 안 함

## 영향 파일

- `scripts/backfill_sign_aware.py` (new)
- `batch-runner/schemas/grade.schema.json` — `schema_version: "1.1"` 추가 허용
- `data/grades/exp003_*__v2sm.json` x 2 (new files)
- `data/grades/exp998_*__v2sm.json` x 2 (new files)
- `src/types/grade.ts` — `model_did_right?: boolean`, `pct_raw?: number` 필드 추가 (다음 PR2에서 UI 노출)
- `scripts/aggregate-grades.mjs` — `__v2sm.json` glob 인식

## Acceptance

- 4개 `__v2sm.json` 생성, schema v1.1 통과
- exp003 hybrid v2sm critical_item_pass_rate 새 값이 STRATIFY_v2 보고서의 `overall_hybrid_right_rate = 0.468`과 ±0.005 일치
- exp003 mini v2sm critical_item_pass_rate가 `overall_mini_right_rate = 0.596`과 ±0.005 일치
- 새 backfilled v2sm 파일과 기존 v1 파일이 같은 디렉토리에 공존, dashboard aggregate 깨지지 않음 (`npm run aggregate` 통과)

## Out of scope

- v1 파일 삭제 / 덮어쓰기 (절대 안 함)
- HF Hub re-upload (별도 step7 작업)
