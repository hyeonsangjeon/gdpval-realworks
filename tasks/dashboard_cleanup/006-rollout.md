# 006 — Rollout Plan

## PR 분할 (확정)

### Track 1 (별도 핫픽스 PR, 본 spec 외)

**브랜치**: `fix/grade-inference-model-and-token-budget`

| 파일 | 변경 |
|---|---|
| `batch-runner/grading_configs/default_gpt5pro.yaml` | `grader.per_item_max_output_tokens: 800 → 1600` |
| `batch-runner/step8_grade.py` | inference yaml 에서 `condition_a.model.deployment` 읽어 `inference_model` 채우기 |
| `batch-runner/scripts/download_inference_from_hf.py` | (선택) parquet reconstruct 경로에서도 model 채우기 시도 |

**검증**:
```bash
# config 변경 적용 확인
cd batch-runner && python step8_grade.py exp998_smoke_baseline_sample \
  --config grading_configs/default_gpt5pro.yaml --force

# 결과 grade JSON에서 inference_model 채워졌는지
jq '.inference_model, .judge.model, .summary.wow.judge_error_rate' \
  data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json
# 기대: "gpt-5.2-chat", "gpt-5.4-pro", < 0.05
```

**합격 기준**:
- [ ] `inference_model` 이 정확한 deployment 이름으로 채워짐
- [ ] `judge_error_rate < 0.05`
- [ ] Schema validation 통과 (`tests/test_grade_schema.py`)

### PR #1 (본 spec, 001~005 일괄)

**브랜치**: `feat/dashboard-cleanup`

| 파일 | 변경 |
|---|---|
| `scripts/aggregate-grades.mjs` | 001 D1 + 002 D1 (`grade_status` 필드, fallback 제거) |
| `src/hooks/useGrades.ts` | 001 D2 + 002 타입 추가 |
| `src/pages/GradeDetail.tsx` | 001 D3 + 003 D2 (HealthRow 삽입) |
| `src/components/GradesSummary.tsx` | 001 D4 + 002 D3 |
| `src/components/dashboard/GradingAnalysisView.tsx` | 001 D5 + 002 D2 + 003 D3 + 004 D1 |
| `src/components/ScopeBadge.tsx` | 002 D4 |
| `src/components/wow/HealthRow.tsx` | NEW (003 D1) |
| `src/lib/format.ts` | 003 fmtPct / fmtLatency 헬퍼 (위치 협의 가능) |
| `src/data/tooltipTexts.ts` | 003 D4 + 004 D2 + 005 카피 |

**검증**:
```bash
npm run aggregate
node -e 'const d=require("./public/generated/grades-index.json"); console.log(d.map(g=>({id:g.id, status:g.grade_status, inf:g.inference_model, judge:g.judge_model})))'
# 기대:
# [
#   {id:"dummy_gpt5_baseline", status:"legacy_dummy", inf:"<dummy meta.model>", judge:null},
#   {id:"exp998_smoke...", status:"graded_v1", inf:"gpt-5.2-chat" (Track1 후), judge:"gpt-5.4-pro"}
# ]

npm run build
# 기대: tsc + vite build 통과

npm run dev
# 시각 회귀:
#   1. /grades/exp998_... → header에 "Inference gpt-5.2-chat · Graded by gpt-5.4-pro · 3 tasks"
#   2. /grades/exp998_... → HealthRow 5 카드, judge_error_rate Track 1 후 5% 이하
#   3. / (Dashboard) → Grading Analysis 탭, mixed banner blue, dummy 카드 톤다운,
#                       Grader Disagreement 섹션 사라짐
```

**합격 기준**:
- [ ] `npm run build` 무에러
- [ ] `grade_status` 필드가 v1.0/legacy/no_grade 정확히 분기
- [ ] 시각 회귀 3 항목 통과
- [ ] tooltipTexts 신규 키 (`health.*`) 가 모두 사용됨 (orphan 없음)

## 검증 시퀀스 (S2 = Track1 먼저, OK면 PR #1)

### Stage 1 — Track 1 핫픽스 (시간: ~15분 코드 + ~5분 smoke)

1. Track 1 PR 작성 → 머지 (smoke ok 확인 후)
2. `grade-run.yml` workflow_dispatch (exp998, 3 tasks)
3. `judge_error_rate < 0.05` 확인
4. ✅ 통과 → PR #1 시작

### Stage 2 — PR #1 (Dashboard cleanup)

1. `feat/dashboard-cleanup` 브랜치 생성
2. spec 001~005 일괄 구현 (구현 순서는 §"구현 권장 순서" 참조)
3. **HARD GATE — aggregator unit test** (`scripts/__tests__/aggregate-grades.test.mjs`):
   - fixture A: minimal v1 grade with `inference_model: ""` → 출력
     `inference_model: null` (never falls back to judge.model)
   - fixture B: `schema_version: '1.0'` → `grade_status: 'graded_v1'`
   - fixture C: `_meta.is_dummy: true` → `grade_status: 'legacy_dummy'`
4. **HARD GATE — grep audit** (005-copy-pass2 정의):
   ```bash
   rg -i "self-?QA|self-?assess|LLM-?judge|external grad|grading pipeline|pre-?grad|Awaiting" \
      src/ scripts/aggregate-grades.mjs
   ```
   결과를 PR description 표에 첨부, EDIT/DELETE 행 모두 처리.
5. `npm run aggregate && npm run build` 통과
6. **HARD GATE — 시각 회귀** (3 항목):
   - `/grades/dummy_gpt5_baseline` 페이지 정상 렌더링, DEMO badge + dashed border, opacity 사용 안 함
   - `/grades/exp998_smoke_baseline_sample__...` 헤더 "Inference / Graded by" 두 줄, HealthStrip pill row (err pill calm 또는 red), WowSection
   - Dashboard → Grading Analysis 탭: mixed banner sky tone (graded_v1 + dummy 혼재), Disagreement 섹션 사라짐
7. PR open

**합격 기준**:
- [ ] `npm run build` 무에러
- [ ] aggregator unit test 3 fixture 통과
- [ ] grep audit 결과 첨부 + 모든 EDIT/DELETE 처리
- [ ] 시각 회귀 3 항목 통과
- [ ] tooltipTexts 신규 키 (`health.*`, `grading.judgeVsInference`) orphan 없음

### 구현 권장 순서 (extreme-reasoner)

5 spec이 3개 파일 (aggregate-grades.mjs, useGrades.ts,
GradingAnalysisView.tsx) overlap. 권장:

1. **First (foundational, serial)**:
   - 001 D1 + 002 D1 (aggregator + grade_status + experiment_id + unit test) — 하나의 commit
   - 001 D2 + 002 type addition (`useGrades.ts`) — typing only
2. **Second (parallelizable)**:
   - 001 D3 + 003 D1/D2 (`GradeDetail.tsx`, `HealthStrip.tsx`, `format.ts`)
   - 001 D4 + 002 D3 + 004 D2 (`GradesSummary.tsx`) — DEMO badge + per-card Disagreement guard
   - 001 D5 + 002 D2 + 003 D3 + 004 D1 (`GradingAnalysisView.tsx`) — 4 spec touchpoint 동시
3. **Third (low risk, last)**:
   - 002 D4 (`ScopeBadge.tsx` + `ExperimentDetail.tsx`)
   - 005 copy pass — last, UI 확정 후

### Stage 3 — exp025 실 채점 (별도, 본 spec 외)

PR #1 머지 후 진행:
1. `grade-run.yml` workflow_dispatch (exp025, 220 tasks, ~$70)
2. Stage 1 smoke 데이터 기준 8h 이내 완료 예상
3. Dashboard 시각 확인 (HealthStrip alert 없음, WOW 카드 풍부함)

## 운영 정책 (PR #1 머지 후)

### 신규 실험 channel
1. inference: batch-run.yml workflow_dispatch (수동)
2. grading: grade-run.yml workflow_dispatch (수동)
3. dashboard: GitHub Pages 자동 빌드

### 기존 실험 백필 (Track 1 + PR #1 머지 후)
- 1개씩 수동 trigger, dashboard에서 HealthRow 확인하며 진행
- `judge_error_rate > 5%` 시 즉시 중단 → config 재튜닝

## 롤백 절차

### Track 1 롤백
- `git revert <Track1_commit>` → config / step8 원복

### PR #1 롤백
- `git revert <PR1_commit>` — frontend only, 데이터/스키마 변경 없음
- backward compat: dummy 표시 보존, useGrades 타입은 additive only

## 위험 / 가드

| 위험 | 가드 |
|---|---|
| Track 1 변경이 schema test 깸 | `tests/test_grade_schema.py` 가 `inference_model` 빈 문자열 허용 — pass |
| PR #1 후 dummy 표시 깨짐 | `legacy_dummy` 경로 명시적 테스트 |
| 사용자가 grade_status 필드 무시 (구버전 캐시) | grades-index.json 새 파일이므로 브라우저 강제 리로드만 필요 |

## 의사결정 박제

본 rollout plan 은 Track 1 + PR #1 머지 전까지 frozen. 변경 필요 시
amendment + 사용자 승인.

## 다음 actionable

1. ✅ 본 spec 패키지 박제 (이 작업 완료 시)
2. ⏭ Track 1 핫픽스 PR 작성 → smoke 재검증
3. ⏭ PR #1 (dashboard cleanup) 작성 → 머지
4. ⏭ exp025 실 채점 (Stage 3)
5. ⏭ Phase B spec 작성 (별도 패키지)
