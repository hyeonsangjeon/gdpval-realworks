# TASK_GRADE_DETAIL_SELF_QA_CALIBRATION — Self-QA vs Rubric calibration view on GradeDetail page

## TL;DR
Grade detail 페이지의 **Task Details 테이블**에 Self-QA(인퍼런스 자기평가)와 Rubric judge(외부 채점)
두 점수를 같이 보여 모델 **calibration**(자기 인식 정확도) 분석을 가능하게 한다.
빌드 타임에 `aggregate-reports.mjs`가 per-task `qa_score`를 reports-index에 enrich하고, `aggregate-grades.mjs`가
**experiment_id 기준 strict join**으로 grade에 qa_score를 결합한다. 매칭 실패는 unmatched로 정직하게 표시.

**Phase 1 (이번 PR)**: Strict matching. 매칭 안 되는 grade는 `Self-QA matched: 0/N tasks`로 표시.
**Phase 2 (별도 PR)**: `step8_grade.py`가 grade JSON에 `source_inference_experiment_id` 명시적 기록 — 별도 task로 분리 (`tasks/0523_saturday/TASK_GRADE_SOURCE_LINKAGE_BACKEND.md`).

---

## Background & Motivation

### 현재 상태
GradeDetail 페이지의 Task Details 테이블은 **Rubric judge 점수만** 보여준다:

```
#  Task ID    Scores    Avg    Status
1  a328fe…    [0/0/0]   88%    Partial
2  dfb4e0…    [0/0/0]   67%    Partial
3  0419f1…    [0/0/0]   78%    Partial
```

한편 ExperimentDetail 페이지에는 **Self-QA score**(0-10)가 task별로 따로 표시된다.
두 점수를 같은 화면에서 못 보기 때문에 **모델 자기 평가의 정확도(calibration)** 라는 가장 중요한 메타 신호가 가려져 있다.

### 왜 가치 있는가
LLM benchmarking에서 핵심 질문 중 하나는 *"모델이 자기 결과의 품질을 알아채는가?"* 이다.
두 점수를 나란히 보면 4가지 패턴이 즉시 분류된다:

| Self-QA | Rubric | 해석 |
|---|---|---|
| 9/10 | 0% | **과대평가** — 모델이 실패를 인식 못 함 (위험) |
| 9/10 | 100% | **잘 알고 잘 함** — 신뢰 가능 |
| 4/10 | 80% | 과소평가 — 보수적, 능력 발휘 가능 |
| 4/10 | 20% | 자기 인식 정확 — 실패 알아챔 (안전) |

→ 이 신호는 **모델 선택, 프롬프트 설계, 자기검증 전략**의 핵심 근거가 된다.

---

## Goal

GradeDetail 페이지에서 모든 task에 대해:
1. Self-QA score를 함께 보여준다 (0-10 원본 + % 정규화)
2. 두 점수 차이(Δ Gap)와 calibration 상태(Aligned/Over/Under)를 시각적으로 강조한다
3. 새 필터(Calibrated, Overconfident, Underconfident)로 패턴 필터링한다
4. 전체 실험의 **Calibration MAE**(Mean Absolute Error)를 Health Strip에 추가한다

핵심 불변식:
- Self-QA가 없는 task는 calibration 컬럼에 `—`만 보여주고 에러 없음
- 기존 컬럼(#, Task ID, Scores, Avg, Status) 픽셀 변화 0
- 기존 필터(All/Perfect/Partial/Zero/Error/Inconsistent) 동작 변화 0
- v1 grade 파일(qa_score 없음)에서도 정상 렌더

---

## Scope

**수정/신규**:
- `scripts/aggregate-reports.mjs` — 각 report에 compact `task_qa: { task_id: qa_score }` map 추가 (task_results strip 직전)
- `scripts/aggregate-grades.mjs` — reports-index의 `task_qa`를 experiment_id 기준 strict join, dummy/unmatched 처리, summary에 `calibration_mae`, `calibration_counts` 추가
- `package.json` — aggregate 스크립트 순서: `reports`를 `grades` 전에 실행
- `src/types/grade.ts` — `TaskGradeV1.qa_score?`, `GradeSummary.calibration_mae?`, `GradeSummary.calibration_counts?` 추가
- `src/types/report.ts` — `ReportData.task_qa?: Record<string, number>` 추가
- `src/data/tooltipTexts.ts` — 4개 신규 툴팁 추가
- `src/components/wow/HealthStrip.tsx` — Calibration MAE Pill 추가
- `src/pages/GradeDetail.tsx` — 컬럼 3개 추가(Self-QA, Δ Gap, Calibration), 필터 3개 추가
- `scripts/__tests__/aggregate-grades.test.mjs` — 매칭 케이스 (matched/unmatched/dummy/mixed) 테스트 추가

**손대지 않을 곳 (Phase 1)**:
- `batch-runner/` (Phase 2에서 별도 처리)
- ExperimentDetail 페이지 (자기 자체로 완결됨)
- 기존 Health Strip 메트릭 5종 (err / judge / precheck / calls / latency) 동작
- 기존 grade JSON 파일 (마이그레이션 없음)

---

## Design

### 1a. Reports-index enrichment: `scripts/aggregate-reports.mjs`

현재 aggregate-reports.mjs는 `task_results` array를 **strip**하여 final reports-index에 포함시키지 않는다.
Grade calibration을 위해 **compact task_qa map**을 각 report에 추가한다:

```js
// Before stripping task_results, extract compact qa map
const taskQa = {};
for (const t of (report.task_results ?? [])) {
  if (t.task_id && t.qa_score != null) taskQa[t.task_id] = t.qa_score;
}
report.task_qa = taskQa;  // small payload: ~220 * (UUID + int) ≈ 12KB per report
delete report.task_results;  // continue stripping the large field
```

결과: 각 report에 `task_qa: { "<task_id>": <qa_score 0-10>, ... }` 추가. 다른 필드는 그대로.

### 1b. Build-time join: `scripts/aggregate-grades.mjs`

**Strict per-experiment matching**. global map은 GDPVal task_id 공유로 잘못된 매칭을 만들기 때문에
**grade.experiment_id ↔ report.meta.experiment_id**로만 매칭한다.

```js
// 1) Build experiment_id → task_qa lookup from reports-index
const reportsIndex = safeReadJson('public/generated/reports-index.json');
const taskQaByExperiment = new Map();
for (const report of reportsIndex?.reports ?? []) {
  const expId = report?.meta?.experiment_id;
  if (expId && report.task_qa) taskQaByExperiment.set(expId, report.task_qa);
}

// 2) For each grade, look up that experiment's qa map (NOT global)
function decorateGradeTasks(grade, tasks) {
  if (grade.is_dummy) {
    // Dummy grades have synthetic scores, no real inference run → leave unmatched
    return tasks.map(t => ({ ...t, qa_score: null }));
  }
  const qaMap = taskQaByExperiment.get(grade.experiment_id) ?? null;
  return tasks.map(t => ({
    ...t,
    qa_score: qaMap?.[t.task_id] ?? null,
  }));
}

// 3) Compute calibration MAE & counts (unchanged from before)
function buildCalibration(tasks) {
  const samples = [];
  let unmatched = 0;
  for (const t of tasks) {
    if (t.error) continue;
    if (t.qa_score == null) { unmatched++; continue; }
    if (t.avg_score == null) continue;
    samples.push((t.avg_score * 100) - (t.qa_score * 10));
  }
  const mae = samples.length > 0
    ? Number((samples.reduce((s, d) => s + Math.abs(d), 0) / samples.length).toFixed(2))
    : null;
  return {
    calibration_mae: mae,
    calibration_counts: {
      calibrated:     samples.filter(d => Math.abs(d) <= 10).length,
      overconfident:  samples.filter(d => d < -10).length,
      underconfident: samples.filter(d => d > 10).length,
      unmatched,
    },
  };
}
```

**Pipeline ordering**: `aggregate-reports.mjs` MUST run before `aggregate-grades.mjs`.
`package.json` `aggregate` script 순서를 확인하고, 필요하면 `reports → grades` 순으로 변경.
현재 순서: `tests → grades → reports → experiments` → **`tests → reports → grades → experiments`**로 변경 필요.

**Known Phase 1 limitation**: exp998 grade는 reports-index에 매칭되는 report가 없음 (HF fetch 실패).
따라서 모든 3 task가 `unmatched`로 표시됨. 이는 의도된 동작이며 "데이터 정합성이 깨졌다"는 정직한 신호.
Phase 2(별도 PR)에서 batch-runner step8_grade가 `source_inference_experiment_id`를 grade JSON에 직접 기록하도록 변경하여 영구 해결.

### 2. Types: `src/types/grade.ts`

```ts
export interface TaskGradeV1 {
  task_id: string
  // ... 기존 필드
  qa_score?: number | null  // 0-10, from inference self-QA
}

export interface GradeSummary {
  // ... 기존
  calibration_mae?: number | null  // mean |Rubric% - SelfQA%|
  calibration_counts?: {
    calibrated: number
    overconfident: number
    underconfident: number
    unmatched: number
  } | null
}
```

### 3. Tooltips: `src/data/tooltipTexts.ts`

`health` 객체에 추가:
```ts
calibrationMae:
  'Mean Absolute Error of Self-QA vs Rubric across all tasks. Lower = better model self-awareness. <10pp is well-calibrated.',
```

새 객체 `calibration`:
```ts
calibration: {
  selfQa: 'Self-rated quality score during inference (0-10). The inference model evaluates its own output. Distinct from external rubric judge.',
  rubric: 'Independent rubric-based score by external judge LLM. Objective and decoupled from the inference model.',
  gap: 'Rubric − Self-QA. Negative = model overconfident (risk). Positive = model underconfident. |Δ| ≤ 10pp is well-calibrated.',
  status: 'Aligned (|Δ|≤10): well-calibrated. Overconfident (Δ<-10): model overestimates its own work. Underconfident (Δ>10): model underestimates.',
}
```

### 4. Health Strip: `src/components/wow/HealthStrip.tsx`

기존 5개 Pill 뒤에 추가:
```tsx
<NeutralPill
  label="MAE"
  value={summaryV1.calibration_mae != null ? `${summaryV1.calibration_mae.toFixed(1)}pp` : '—'}
  tooltip={tooltipTexts.health.calibrationMae}
/>
```

`pp` = percentage points.

### 5. Task Details Table: `src/pages/GradeDetail.tsx`

#### 컬럼 구조 변경
기존: `# | Task ID | Scores | Avg | Status`
신규: `# | Task ID | Scores | Avg | Self-QA | Δ Gap | Calib. | Status`

#### Self-QA 컬럼 렌더
```tsx
<td className="py-2 px-3 text-center">
  {task.qa_score != null ? (
    <div className="flex flex-col items-center leading-tight">
      <span className="font-semibold">{Math.round(task.qa_score * 10)}%</span>
      <span className="text-xs text-muted-foreground">{task.qa_score.toFixed(1)}/10</span>
    </div>
  ) : (
    <span className="text-muted-foreground">—</span>
  )}
</td>
```

#### Δ Gap 컬럼 렌더
```tsx
function gapColor(delta: number): { color: string; bg: string } {
  const abs = Math.abs(delta)
  if (abs <= 10) return { color: 'text-muted-foreground', bg: 'bg-muted/30' }
  if (abs <= 30) return { color: 'text-amber-500', bg: 'bg-amber-500/10' }
  return { color: 'text-red-500', bg: 'bg-red-500/10' }
}

// computed once: const delta = (task.avg_score * 100) - (task.qa_score * 10)
```

표시:
```tsx
<td className="py-2 px-3 text-center">
  {delta != null ? (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono ${color} ${bg}`}>
      {delta > 0 ? '▲' : delta < 0 ? '▼' : '─'}
      {delta > 0 ? '+' : ''}{Math.round(delta)}
      {Math.abs(delta) > 30 && <AlertTriangle className="h-3 w-3" />}
    </span>
  ) : (
    <span className="text-muted-foreground">—</span>
  )}
</td>
```

#### Calibration 컬럼 (lucide 아이콘 + 텍스트)
```tsx
import { Target, TrendingDown, TrendingUp } from 'lucide-react'

function calibStatus(delta: number | null) {
  if (delta == null) return { icon: null, label: '—', color: 'text-muted-foreground' }
  if (Math.abs(delta) <= 10) return { icon: Target, label: 'Aligned', color: 'text-muted-foreground' }
  if (delta < -10) return { icon: TrendingDown, label: 'Over', color: 'text-red-500' }
  return { icon: TrendingUp, label: 'Under', color: 'text-amber-500' }
}
```

#### 필터 확장
기존 `TaskFilter`:
```ts
type TaskFilter = 'all' | 'perfect' | 'partial' | 'zero' | 'error' | 'inconsistent'
```
→ 신규:
```ts
type TaskFilter = 'all' | 'perfect' | 'partial' | 'zero' | 'error' | 'inconsistent'
                | 'calibrated' | 'overconfident' | 'underconfident'
```

필터 버튼 UI: 기존 6개 뒤에 `|` divider, 그 다음 3개 calibration 필터.

#### 푸터에 매칭률 표시
```tsx
{summary.calibration_counts && (
  <p className="text-xs text-muted-foreground mt-3 py-2 text-center">
    Self-QA matched: {totalTasks - unmatched}/{totalTasks} tasks
    {unmatched > 0 && ` (${unmatched} unmatched)`}
  </p>
)}
```

---

## Color & UX Rules

| 임계값 (\|Δ\|) | 색상 | 라벨 | 의미 |
|---|---|---|---|
| ≤ 10pp | 회색 (muted) | Aligned | 잘 캘리브레이션됨 |
| 11–30pp | 노란색 (amber-500) | Over/Under (mild) | 주의 |
| > 30pp | 빨간색 (red-500) + ⚠️ | Over/Under (severe) | 심각한 miscalibration |

**부호 규칙**:
- `+` Δ = Rubric > Self-QA = 모델이 자신을 **과소평가** (보수적)
- `−` Δ = Rubric < Self-QA = 모델이 **과대평가** (위험)

---

## Edge Cases

| 케이스 | 처리 |
|---|---|
| reports-index에 task_id 없음 | task.qa_score = null, calibration 컬럼 `—`, calibration_counts.unmatched++ |
| reports-index 자체가 없음 (fresh repo) | qaScoreByTaskId가 빈 맵, 모든 task `—`, MAE = null |
| qa_score = 0 | 유효한 값으로 처리 (0%로 표시) |
| qa_score = null in report | 그 task만 unmatched 취급 |
| Δ Gap 정확히 ±10 | Aligned로 분류 (≤ 사용) |
| 모든 task가 unmatched | MAE = null → Health Strip `—` 표시 |
| Inconsistent task (multi-grader) | avg_score 그대로 사용 (현재 동작 유지) |

---

## Verification

### Acceptance
1. exp998 grade 페이지에서 (현재 데이터 상태 = unmatched 케이스):
   - Task Details 테이블에 Self-QA / Δ Gap / Calib. 컬럼이 보임
   - 모든 3 task에 `—` 표시 (reports-index에 exp998 report 없음 → unmatched)
   - Health Strip의 `MAE` Pill은 `—`로 표시
   - 푸터: `Self-QA matched: 0/3 tasks (3 unmatched)`
2. Self-QA 없는 dummy grade(`dummy_gpt5_baseline`)에서:
   - 새 컬럼들 모두 `—`로 표시, 에러 없음
   - 푸터: `Self-QA matched: 0/220 tasks (220 unmatched)`
3. **매칭되는 케이스 (현재 데이터엔 없지만 로직 검증용 — 테스트로 커버)**:
   - 가짜 reports-index에 exp998 entry + 정확한 task_qa map을 추가하고 빌드 → exp998 grade가 정상 매칭됨
   - 또는 새 grade가 매칭되는 report와 함께 생성될 때 자동 calibration
4. 새 필터 클릭 시 (매칭된 task가 있을 때):
   - Calibrated: |Δ|≤10 task만 보임
   - Overconfident: Δ < -10 task만 보임
   - Underconfident: Δ > 10 task만 보임
5. 기존 필터(Perfect/Partial/Zero/Error/Inconsistent) 동작 변화 없음
6. 헤더 호버 시 4개 신규 툴팁이 모두 표시

### Tests
- `scripts/__tests__/aggregate-grades.test.mjs`에 케이스 추가:
  - reports에 일치하는 task_id 있을 때 qa_score 결합
  - reports에 없는 task_id는 null 유지
  - calibration_mae 계산 (수식 검증: 알려진 값 입력 후 결과 확인)
  - calibration_counts 분류 (4가지 카테고리 카운트)
- `npm run build` 성공
- 빌드 후 `dist/generated/grades-index.json`에 `qa_score`, `calibration_mae`, `calibration_counts` 존재

---

## Risks & Mitigations

| 리스크 | 완화 |
|---|---|
| aggregate 순서 의존성(reports → grades) | package.json `aggregate` 스크립트 순서 확인. test에서 reports-index 없을 때 graceful fallback 검증 |
| ExperimentDetail에서 qa_score 의미와 그래도 일관성 | 같은 정의 사용. `qa_score`는 0-10 원본 스케일 유지 (×10 정규화는 GradeDetail만의 표시 결정) |
| Task table 너비 폭주(8 컬럼) | `overflow-x-auto` 이미 존재. 모바일에서 가로 스크롤 허용 |
| 220 task 전체 채점본에서 렌더 성능 | 이미 `.slice(0, 50)` 적용 중 → 영향 없음 |
| Dummy grade에서 잘못된 MAE | qa_score = null이면 calibrationSamples에서 제외. MAE = null → Health Strip `—` |

---

## Out of Scope (Future)

- **Phase 2 (별도 PR)**: `step8_grade.py`가 grade JSON에 `source_inference_experiment_id` 명시적 기록 → `experiment_id`가 변형되어도 강건한 매칭. 명세는 `tasks/0523_saturday/TASK_GRADE_SOURCE_LINKAGE_BACKEND.md` 참조.
- Calibration scatter plot (Self-QA vs Rubric per task) — 시각화 추가
- Sector별 Calibration breakdown
- Leaderboard에 experiment 단위 Calibration MAE 컬럼 추가
- 시간/실험 간 calibration trend 차트
- Per-judge calibration (multi-judge grading 시 grader별 비교)

---

## Implementation Order (Subagent Dispatch Plan)

1. **coder #1**: `scripts/aggregate-reports.mjs` 수정 (compact task_qa map 추가) + `scripts/aggregate-grades.mjs` 수정 (per-experiment strict join + dummy/unmatched 처리) + `package.json` aggregate 순서 변경 + 테스트 추가
   - 검증: `npm run aggregate` 후 `public/generated/reports-index.json`에 `task_qa` 존재, `grades-index.json`에 `qa_score`/`calibration_*` 존재, exp998은 unmatched로 표시
2. **coder #2**: `src/types/grade.ts` + `src/types/report.ts` + `src/data/tooltipTexts.ts` 업데이트
3. **coder #3**: `src/components/wow/HealthStrip.tsx`에 MAE Pill 추가
4. **coder #4**: `src/pages/GradeDetail.tsx` 컬럼 3개 + 필터 3개 + 푸터 추가
5. **orchestrator (this agent)**: `npm run build` + 빌드 산출물 검증 + 로컬 dev preview 스크린샷 검증
6. **first-reviewer**: 전체 diff 리뷰 (correctness, types, fallback 처리)
7. **git-committer**: Conventional commit + push to feature branch + PR draft

---

## Branch & PR
- Branch: `feat/grade-detail-self-qa-calibration`
- PR title: `feat(dashboard): show Self-QA vs Rubric calibration on GradeDetail`
- PR description: 이 문서 TL;DR 섹션 사용
