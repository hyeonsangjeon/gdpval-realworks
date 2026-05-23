# 001 — Inference vs Judge 모델 분리 표시

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
  model: string             // legacy: inference 모델 (없으면 '')
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

## D3 — GradeDetail.tsx 헤더

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
<div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
  {grade.inference_model ? (
    <span className="font-mono">
      <span className="text-foreground/60">Inference</span>{' '}
      <span className="text-foreground font-medium">{grade.inference_model}</span>
    </span>
  ) : (
    <span className="font-mono text-amber-500/80">Inference model unknown</span>
  )}
  <span>•</span>
  {grade.judge_model ? (
    <span className="font-mono">
      <span className="text-foreground/60">Graded by</span>{' '}
      <span className="text-foreground font-medium">{grade.judge_model}</span>
    </span>
  ) : (
    <span className="font-mono text-amber-500/80">Judge model unknown (legacy)</span>
  )}
  <span>•</span>
  <span>{grade.summary.total_tasks} tasks</span>
</div>
```

Tooltip 추가 (i 풍선): "Inference model produced the deliverable. Judge
model scored it against open-sourced GDPval rubrics. These are separate
pipelines."

## D4 — GradesSummary.tsx 카드 헤더

기존 `<p>{grade.model}</p>` 한 줄을 다음 2줄로:

```tsx
<div className="text-xs text-muted-foreground space-y-0.5">
  <div>
    Inference:{' '}
    {grade.inference_model
      ? <span className="font-mono text-foreground">{grade.inference_model}</span>
      : <span className="italic">unknown</span>}
  </div>
  <div>
    Judge:{' '}
    {grade.judge_model
      ? <span className="font-mono text-foreground">{grade.judge_model}</span>
      : <span className="italic">—</span>}
  </div>
</div>
```

## D5 — GradingAnalysisView.tsx GradeOverviewCard

GradeOverviewCard 내부 모델 표시도 동일 패턴으로.

## 테스트

| 시나리오 | 기대 결과 |
|---|---|
| inference_model="" + judge.model="gpt-5.4-pro" (현재 smoke) | header: "Inference model unknown · Graded by gpt-5.4-pro · 3 tasks" |
| inference_model="gpt-5.2-chat" + judge.model="gpt-5.4-pro" (Track 1 후) | header: "Inference gpt-5.2-chat · Graded by gpt-5.4-pro · 3 tasks" |
| dummy 파일 (meta.model="gpt-5") | header: "Inference gpt-5 · Judge model unknown (legacy) · 220 tasks" |

수동 회귀: `npm run dev` 후 `/grades/dummy_gpt5_baseline` 페이지가 깨지지
않는지 확인.

## 비고

- "Inference model unknown" 은 Track 1 핫픽스로 사라질 예정. 그래도
  defensive 하게 처리.
- 추후 Phase B에서 같은 experiment에 judge 가 여러 개 있을 때 selector
  추가 — 이 spec 1차에선 미구현, 데이터 모델만 준비.
