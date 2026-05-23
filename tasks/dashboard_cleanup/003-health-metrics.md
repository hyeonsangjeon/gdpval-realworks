# 003 — Health 메트릭을 dashboard 1차 시민으로

## 목적

`judge_error_rate=23.81%` 같은 운영성 핵심 지표가 dashboard 어디에도
없어, 사용자가 unhealthy run 으로 Stage 2 trigger 할 위험. 새 Health
row 추가로 한눈에 파악.

## 노출할 메트릭

| Card | 출처 | 표시 |
|---|---|---|
| Judge Error Rate | `summary_v1.wow.judge_error_rate` | %, 임계 5% (>5% 빨강) |
| Judge Pass Rate | `summary_v1.wow.judge_pass_rate` | % |
| Precheck Pass Rate | `summary_v1.wow.precheck_pass_rate` | % |
| Judge Calls | `summary_v1.cost.total_judge_calls` | 정수 |
| Judge Latency | `summary_v1.cost.total_judge_latency_sec` | "Xs total / Yms avg" |

## 변경 파일

| 파일 | 변경 |
|---|---|
| `src/components/wow/HealthRow.tsx` | NEW — 5 카드 row |
| `src/pages/GradeDetail.tsx` | WOW section 위 Health row 삽입 |
| `src/components/dashboard/GradingAnalysisView.tsx` | per-experiment summary card에 mini-health |
| `src/data/tooltipTexts.ts` | health 카드 5 tooltip |

## D1 — HealthRow.tsx (NEW)

```tsx
interface HealthRowProps {
  summaryV1: GradeSummaryV1
}

export default function HealthRow({ summaryV1 }: HealthRowProps) {
  const wow = summaryV1.wow
  const cost = summaryV1.cost
  const errRate = wow.judge_error_rate ?? 0
  const errAlert = errRate > 0.05

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
      <HealthCard
        label="Judge Error Rate"
        value={fmtPct(errRate)}
        alert={errAlert}
        tooltip={tooltipTexts.health.judgeErrorRate}
      />
      <HealthCard
        label="Judge Pass Rate"
        value={fmtPct(wow.judge_pass_rate)}
        tooltip={tooltipTexts.health.judgePassRate}
      />
      <HealthCard
        label="Precheck Pass Rate"
        value={fmtPct(wow.precheck_pass_rate)}
        tooltip={tooltipTexts.health.precheckPassRate}
      />
      <HealthCard
        label="Judge Calls"
        value={String(cost?.total_judge_calls ?? '—')}
        tooltip={tooltipTexts.health.judgeCalls}
      />
      <HealthCard
        label="Judge Latency"
        value={fmtLatency(cost?.total_judge_latency_sec)}
        tooltip={tooltipTexts.health.judgeLatency}
      />
    </div>
  )
}
```

`HealthCard` 는 작은 inline 컴포넌트. 빨강 alert 상태일 때 border red-500.

## D2 — GradeDetail.tsx 위치

```tsx
{grade.schema_version === '1.0' && grade.summary_v1 ? (
  <>
    <HealthRow summaryV1={grade.summary_v1} />
    <WowSection summary={grade.summary_v1} tasksV1={grade.tasks_v1 ?? []} />
  </>
) : null}
```

## D3 — GradingAnalysisView.tsx mini-health

GradeOverviewCard 안에 작은 한 줄:

```tsx
{g.grade_status === 'graded_v1' && g.summary_v1?.wow && (
  <div className="flex items-center gap-2 text-[10px] mt-2 font-mono">
    <span className={g.summary_v1.wow.judge_error_rate! > 0.05
      ? 'text-red-400'
      : 'text-emerald-400'}>
      err {fmtPct(g.summary_v1.wow.judge_error_rate)}
    </span>
    <span className="text-muted-foreground">judge {fmtPct(g.summary_v1.wow.judge_pass_rate)}</span>
    <span className="text-muted-foreground">precheck {fmtPct(g.summary_v1.wow.precheck_pass_rate)}</span>
  </div>
)}
```

## D4 — tooltipTexts.health 신규 블록

```ts
health: {
  judgeErrorRate:
    "Percentage of judge calls that failed (timeout, parse error, or hit token limit). Alert threshold > 5% — unreliable run.",
  judgePassRate:
    "Pass rate among LLM-judge-decided rubric items (content-quality criteria). Distinct from precheck (deterministic structural checks).",
  precheckPassRate:
    "Pass rate among deterministically checked items (filename, sheet name, format).",
  judgeCalls:
    "Total number of LLM-judge API calls used during grading. Per-experiment cost proxy.",
  judgeLatency:
    "Total wall-clock seconds spent inside the judge LLM during this grading run.",
},
```

## 헬퍼

```ts
// src/lib/format.ts (또는 위치 협의)
export function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  const num = v <= 1 ? v * 100 : v
  return `${num.toFixed(1)}%`
}

export function fmtLatency(sec: number | null | undefined): string {
  if (!sec) return '—'
  if (sec < 60) return `${sec.toFixed(0)}s`
  return `${(sec / 60).toFixed(1)}m`
}
```

## 테스트

| 시나리오 | 기대 |
|---|---|
| 현재 smoke (judge_error_rate=0.2381) | "Judge Error Rate 23.8%" 빨강 alert border |
| Track 1 후 (error_rate < 5%) | 일반 카드 색상 |
| dummy 파일 (no wow) | HealthRow 미렌더링 (graded_v1 가드) |

## 의존성

- 001 (inference/judge 분리) — `judge_model` 사용 가능 가정
- 002 (`grade_status`) — `graded_v1` 가드

## 비고

- HealthRow 는 WOW section 위에 배치 — sequence: Overview tiles →
  HealthRow → WOW W1-W6.
- 추후 Phase B에서 alert threshold 를 grading config 파일로 외부화
  검토.
