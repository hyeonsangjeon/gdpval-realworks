import { motion } from 'framer-motion'
import { AlertTriangle } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import { tooltipTexts } from '../../data/tooltipTexts'
import { fmtPct, fmtLatency } from '../../lib/format'
import type { GradeSummaryV1 } from '../../types/grade'
import {
  JUDGE_ITEMS_DESCRIBED,
  PRECHECK_ITEMS_DESCRIBED,
  readJudgeErrorRate,
  readWowRate,
} from './rateReading'

interface Props {
  summaryV1: GradeSummaryV1
  delay?: number
}

interface PillProps {
  label: string
  value: string
  alert?: boolean
  tooltip?: string
}

function Pill({ label, value, alert, tooltip }: PillProps) {
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

function NeutralPill({ label, value, tooltip }: { label: string; value: string; tooltip?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground" title={tooltip}>
      <span>{label}</span>
      <span className="text-foreground font-semibold">{value}</span>
    </span>
  )
}

export default function HealthStrip({ summaryV1, delay = 0 }: Props) {
  const wow = summaryV1.wow ?? null
  const cost = summaryV1.cost ?? null
  // The alert already refused to fire on an absent rate; this reads it through
  // the shared rule so the one surface that got it wrong and the one that got
  // it right cannot drift apart again, and so the tooltip says which it is.
  const err = readJudgeErrorRate(wow?.judge_error_rate, wow?.item_counts?.judge_items)
  // `fmtPct` cannot tell a measured 0% from a rate divided by nothing, and
  // these two pills are the ones that get divided by nothing: 20 of the 33
  // published grades carry `precheck_pass_rate: 0.0`, and now that #393 and
  // #399 have recovered `item_counts` all 20 can be checked — all 20 counted
  // no precheck items, and not one is a run where prechecks ran and failed.
  // (This first read 81 of 94, which folded in the 61 `_shards/` payloads;
  // those are published nowhere and record no denominator at all.)
  const precheck = readWowRate(
    wow?.precheck_pass_rate,
    wow?.item_counts?.precheck_items,
    PRECHECK_ITEMS_DESCRIBED,
  )
  const judge = readWowRate(
    wow?.judge_pass_rate,
    wow?.item_counts?.judge_items,
    JUDGE_ITEMS_DESCRIBED,
  )

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
            {err.alert && <AlertTriangle className="h-3.5 w-3.5 text-red-400" />}
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Run Health
            </span>
            <InfoTooltip content={tooltipTexts.health.row} />
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-xs">
            <Pill
              label="err"
              value={err.value}
              alert={err.alert}
              tooltip={
                err.caveat
                  ? `${tooltipTexts.health.judgeErrorRate} — ${err.caveat}`
                  : tooltipTexts.health.judgeErrorRate
              }
            />
            <NeutralPill
              label="judge"
              value={judge.fraction === null ? '—' : fmtPct(judge.fraction)}
              tooltip={
                judge.caveat
                  ? `${tooltipTexts.health.judgePassRate} — ${judge.caveat}`
                  : tooltipTexts.health.judgePassRate
              }
            />
            <NeutralPill
              label="precheck"
              value={precheck.fraction === null ? '—' : fmtPct(precheck.fraction)}
              tooltip={
                precheck.caveat
                  ? `${tooltipTexts.health.precheckPassRate} — ${precheck.caveat}`
                  : tooltipTexts.health.precheckPassRate
              }
            />
            <NeutralPill
              label="calls"
              value={cost?.total_judge_calls != null ? String(cost.total_judge_calls) : '—'}
              tooltip={tooltipTexts.health.judgeCalls}
            />
            <NeutralPill
              label="latency"
              value={fmtLatency(cost?.total_judge_latency_sec)}
              tooltip={tooltipTexts.health.judgeLatency}
            />
            <NeutralPill
              label="MAE"
              value={summaryV1.calibration_mae != null
                ? `${summaryV1.calibration_mae.toFixed(1)}pp`
                : '—'}
              tooltip={tooltipTexts.health.calibrationMae}
            />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
