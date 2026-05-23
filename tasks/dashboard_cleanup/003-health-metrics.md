# 003 — Health 메트릭을 dashboard 1차 시민으로

> **Amendments (post ui-designer review)**:
> - 5 카드 row → **단일 컨테이너 카드 안의 inline pill strip**.
>   diagnostic chrome 으로 시각 weight 낮춤. WOW W1-W6 가 hero 가 되도록
>   visual hierarchy 유지.
> - judge_error_rate > 5% 일 때만 *해당 pill* 이 red 알림 모드로 전환,
>   strip 좌측에 `AlertTriangle` 아이콘 등장. healthy 상태에선 calm chrome.

## 목적

`judge_error_rate=23.81%` 같은 운영성 핵심 지표가 dashboard 어디에도
없어, 사용자가 unhealthy run 으로 Stage 2 trigger 할 위험. inline pill
strip 으로 visual quiet 하게 노출.

## 노출할 메트릭 (5개, pill 표시)

| Pill | 출처 | 표기 | 알림 |
|---|---|---|---|
| err | `summary_v1.wow.judge_error_rate` | `err N.N%` | > 5% red border |
| judge | `summary_v1.wow.judge_pass_rate` | `judge N.N%` | — |
| precheck | `summary_v1.wow.precheck_pass_rate` | `precheck N.N%` | — |
| calls | `summary_v1.cost.total_judge_calls` | `calls N` | — |
| latency | `summary_v1.cost.total_judge_latency_sec` | `latency Xs` 또는 `Xm` | — |

## 변경 파일

| 파일 | 변경 |
|---|---|
| `src/components/wow/HealthStrip.tsx` | NEW (5 inline pill, single Card) |
| `src/pages/GradeDetail.tsx` | Overview Stats 와 WowSection 사이 삽입 |
| `src/components/dashboard/GradingAnalysisView.tsx` | per-experiment summary card에 mini-health (3 핵심 메트릭만, font-mono) |
| `src/data/tooltipTexts.ts` | health 카드 5 tooltip |
| `src/lib/format.ts` | NEW — `fmtPct`, `fmtLatency` 헬퍼 |

## D1 — HealthStrip.tsx (NEW)

```tsx
import { motion } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import { tooltipTexts } from '../../data/tooltipTexts'
import { fmtPct, fmtLatency } from '../../lib/format'
import type { GradeSummaryV1 } from '../../types/grade'

interface Props {
  summaryV1: GradeSummaryV1
  delay?: number
}

export default function HealthStrip({ summaryV1, delay = 0 }: Props) {
  const wow = summaryV1.wow
  const cost = summaryV1.cost
  const errRate = wow.judge_error_rate ?? 0
  const errAlert = errRate > 0.05

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
      className="mb-6"
    >
      <Card className="bg-card/30 backdrop-blur border-border">
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-2 mb-2">
            {errAlert && <AlertTriangle className="h-3.5 w-3.5 text-red-400" />}
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Run Health
            </span>
            <InfoTooltip content={tooltipTexts.health.row} />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-xs">
            <Pill
              label="err"
              value={fmtPct(errRate)}
              alert={errAlert}
              tooltip={tooltipTexts.health.judgeErrorRate}
            />
            <NeutralPill label="judge" value={fmtPct(wow.judge_pass_rate)} tooltip={tooltipTexts.health.judgePassRate} />
            <NeutralPill label="precheck" value={fmtPct(wow.precheck_pass_rate)} tooltip={tooltipTexts.health.precheckPassRate} />
            <NeutralPill label="calls" value={String(cost?.total_judge_calls ?? '—')} tooltip={tooltipTexts.health.judgeCalls} />
            <NeutralPill label="latency" value={fmtLatency(cost?.total_judge_latency_sec)} tooltip={tooltipTexts.health.judgeLatency} />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function Pill({ label, value, alert, tooltip }: {label:string;value:string;alert?:boolean;tooltip?:string}) {
  return (
    <span
      className={
        'inline-flex items-center gap-1.5 px-2 py-1 rounded-md border ' +
        (alert
          ? 'border-red-500/50 bg-red-500/10 text-red-400'
          : 'border-border/50 bg-background/30 text-foreground')
      }
      title={tooltip}
    >
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  )
}

function NeutralPill(props: {label:string;value:string;tooltip?:string}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground" title={props.tooltip}>
      <span>{props.label}</span>
      <span className="text-foreground font-semibold">{props.value}</span>
    </span>
  )
}
```

## D2 — GradeDetail.tsx 위치

```tsx
{grade.schema_version === '1.0' && grade.summary_v1 ? (
  <>
    <HealthStrip summaryV1={grade.summary_v1} delay={0.2} />
    <WowSection summary={grade.summary_v1} tasksV1={grade.tasks_v1 ?? []} />
  </>
) : null}
```

## D3 — GradingAnalysisView.tsx mini-health (per-card)

GradeOverviewCard 안에 작은 한 줄 (3 메트릭만, font-mono):

```tsx
{g.grade_status === 'graded_v1' && g.summary_v1?.wow && (
  <div className="flex items-center gap-2 text-[10px] mt-2 font-mono">
    <span className={(g.summary_v1.wow.judge_error_rate ?? 0) > 0.05
      ? 'text-red-400 font-semibold'
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
  row:
    "Run-quality diagnostics: judge call success rate, pass rates by decision type, and cost/latency totals. Distinct from the score itself.",
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
// src/lib/format.ts (NEW)
export function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  const num = v <= 1 ? v * 100 : v
  return `${num.toFixed(1)}%`
}

export function fmtLatency(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec) || sec <= 0) return '—'
  if (sec < 60) return `${sec.toFixed(0)}s`
  return `${(sec / 60).toFixed(1)}m`
}
```

## 테스트

| 시나리오 | 기대 |
|---|---|
| 현재 smoke (judge_error_rate=0.2381, Track 1 전) | err pill red, AlertTriangle 좌측 등장, 나머지 4개 calm |
| Track 1 후 (error_rate < 5%) | 모든 pill calm chrome |
| dummy 파일 (no wow) | HealthStrip 미렌더링 (graded_v1 가드) |

## 의존성

- 001 (inference/judge 분리) — 같은 PR
- 002 (`grade_status`) — `graded_v1` 가드

## 비고

- HealthStrip 은 Overview Stats 아래, WOW 위에 배치 — visual weight 는
  WOW < HealthStrip < Overview (3단계 hierarchy 보존).
- Phase B alert threshold 외부화는 별도 spec (grading_config 에서 읽기).

