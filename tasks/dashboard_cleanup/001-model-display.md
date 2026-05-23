# 001 — Inference vs Judge 모델 분리 표시

> **Amendments (post extreme-reasoner / ui-designer review)**:
> - Legacy `model` 필드는 `@deprecated` 로 마킹. 구현 시 grep으로 잔존 사용처 0건 확인.
> - 단일 라인 헤더 → **두 줄 stacked + 라벨 + 모노스페이스 pill chip** 패턴.
> - Inference pill = neutral palette, Judge pill = subtle fuchsia tint
>   (WOW 시그널과 시각적 연결). InfoTooltip 으로 "별개 파이프라인" 명시.

## 목적

Dashboard 어디서든 `gpt-5.4-pro` 같은 단일 모델명만 보이면 사용자는 그
모델이 "문제를 푼" 모델이라고 오해한다. Inference 와 grading 은 분리
파이프라인이므로 **두 모델을 명시적으로 분리해서 노출** 한다.

## 변경 파일

| 파일 | 변경 |
|---|---|
| `scripts/aggregate-grades.mjs` | `inference_model` fallback 제거, 빈 값은 빈 값으로 보존 |
| `src/hooks/useGrades.ts` | `inference_model: string \| null`, `judge_model: string \| null`, `model` (legacy) 유지하되 의미 명확화 |
| `src/pages/GradeDetail.tsx` | 헤더 텍스트 재구성 |
| `src/components/GradesSummary.tsx` | 카드 헤더 재구성 |
| `src/components/dashboard/GradingAnalysisView.tsx` | summary 카드 모델 라벨 분리 |

## D1 — aggregate-grades.mjs

### 기존 (잘못된 fallback)

```js
const model = raw.inference_model || (raw.judge && raw.judge.model) || 'Unknown';
```

### 변경

```js
const inference_model = raw.inference_model && raw.inference_model.trim()
  ? raw.inference_model
  : null;
const judge_model = raw.judge && raw.judge.model ? raw.judge.model : null;

// `model` legacy 필드는 inference만 우선, 없으면 빈 문자열 (judge로 fallback X)
const model = inference_model || '';

return {
  // … 기존 필드 …
  model,              // legacy compat. inference_model 없으면 ''
  inference_model,    // 명확한 inference 모델
  judge_model,        // 명확한 judge 모델
  // … 나머지 v1 passthrough …
};
```

Legacy dummy 경로:

```js
// dummy_gpt5_baseline.json 의 meta.model 은 inference 모델 의미.
const inference_model = meta.model || null;
const judge_model = null;     // legacy 더미는 judge 메타 없음
const model = inference_model || 'Unknown';
```

## D2 — useGrades.ts 타입

```ts
export interface GradeResult {
  // ─ 기존 필드 보존 ─
  id: string
  is_dummy: boolean
  label: string
  /**
   * @deprecated since dashboard_cleanup PR #1.
   * Use `inference_model` instead. Retained for legacy callers; equals
   * `inference_model || ''` and never silently falls back to judge model.
   */
  model: string
  dataset_url: string | null

  // ─ 신규/명확화 ─
  inference_model: string | null
  judge_model: string | null

  // (007 v1 passthrough — 002 spec과 동일)
  schema_version?: '1.0' | null
  judge?: JudgeProvenance
  rubric?: RubricProvenance
  prompt?: GradePromptInfo
  graded_at?: string
  summary_v1?: GradeSummaryV1
  tasks_v1?: TaskGradeV1[]

  summary: GradeSummary
  tasks: TaskGrade[]
}
```

**Implementation gate**: 구현 시 `rg "grade\.model|grades?\.\.\.model" src/` 로
잔존 사용처를 0건으로 만든 뒤 머지. 잔존이 있으면 `inference_model` 또는
`judge_model` 로 치환.

## D3 — GradeDetail.tsx 헤더 (ui-designer Layout A)

### 기존
```tsx
<h1>{grade.label}</h1>
<p className="text-sm text-muted-foreground">
  {grade.model} · {grade.summary.total_tasks} tasks
</p>
```

### 변경

```tsx
<h1>{grade.label}</h1>
<div className="flex flex-col gap-1 text-sm mt-2">
  <div className="flex flex-wrap items-center gap-2">
    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
      Inference
    </span>
    {grade.inference_model ? (
      <span className="px-2 py-0.5 rounded bg-foreground/5 border border-border
                       font-mono text-xs text-foreground">
        {grade.inference_model}
      </span>
    ) : (
      <span className="font-mono text-xs italic text-amber-500/80">unknown</span>
    )}
    <span className="text-muted-foreground">· {grade.summary.total_tasks} tasks</span>
  </div>
  <div className="flex flex-wrap items-center gap-2">
    <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
      Graded by
    </span>
    {grade.judge_model ? (
      <span className="px-2 py-0.5 rounded bg-fuchsia-500/10 border border-fuchsia-400/20
                       font-mono text-xs text-fuchsia-300">
        {grade.judge_model}
      </span>
    ) : (
      <span className="font-mono text-xs italic text-muted-foreground">— (legacy)</span>
    )}
    <InfoTooltip content={tooltipTexts.grading.judgeVsInference} />
  </div>
</div>
```

라벨로 시각적 separator 역할 → 좁은 화면에서도 의미 보존 (wrap 가능).
Inference pill = neutral palette (subject), Judge pill = subtle fuchsia
(WOW palette 와 연결, anti-conflation).

InfoTooltip 신규 키: `tooltipTexts.grading.judgeVsInference`:
> "LLM-judge model evaluates outputs against the rubric. Distinct from
> the inference model that produced them."

## D4 — GradesSummary.tsx 카드 헤더

기존 `<p>{grade.model}</p>` 한 줄을 다음 2줄로:

```tsx
<div className="text-xs text-muted-foreground space-y-0.5">
  <div className="flex items-center gap-1">
    <span className="text-[10px] uppercase tracking-wider opacity-70">Inference</span>
    {grade.inference_model
      ? <span className="font-mono text-foreground">{grade.inference_model}</span>
      : <span className="italic">unknown</span>}
  </div>
  <div className="flex items-center gap-1">
    <span className="text-[10px] uppercase tracking-wider opacity-70">Judge</span>
    {grade.judge_model
      ? <span className="font-mono text-fuchsia-300/80">{grade.judge_model}</span>
      : <span className="italic">—</span>}
  </div>
</div>
```

## D5 — GradingAnalysisView.tsx GradeOverviewCard

GradeOverviewCard 내부 모델 표시도 동일 패턴으로.

## 테스트

| 시나리오 | 기대 결과 |
|---|---|
| inference_model="" + judge.model="gpt-5.4-pro" (Track 1 머지 전 grade) | Inference: unknown / Graded by gpt-5.4-pro |
| inference_model="gpt-5.2-chat" + judge.model="gpt-5.4-pro" (Track 1 후) | Inference: gpt-5.2-chat / Graded by gpt-5.4-pro |
| dummy 파일 (meta.model="gpt-5") | Inference: gpt-5 / Graded by — (legacy) |

수동 회귀: `npm run dev` 후 `/grades/dummy_gpt5_baseline` 페이지가 깨지지
않는지 확인.

## Aggregator unit test (T1, 003-rollout §gate)

`scripts/__tests__/aggregate-grades.test.mjs` (또는 동등) 신설:
- fixture: minimal v1 grade with `inference_model: ""` → 출력 `inference_model: null`
- fixture: schema_version="1.0" → `grade_status: 'graded_v1'`
- fixture: `_meta.is_dummy: true` → `grade_status: 'legacy_dummy'`

## 비고

- 추후 Phase B에서 같은 experiment에 judge 가 여러 개 있을 때 selector
  추가 — 이 spec 1차에선 미구현, 데이터 모델만 준비.
- `judge_model: string | null` (singular) — Phase B multi-judge 시 별도
  필드 (`other_judges: string[]`) 추가 검토.

