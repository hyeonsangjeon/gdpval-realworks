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
  const errRate = wow?.judge_error_rate
  const errAlert = typeof errRate === 'number' && errRate > 0.05

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
            <NeutralPill
              label="judge"
              value={fmtPct(wow?.judge_pass_rate)}
              tooltip={tooltipTexts.health.judgePassRate}
            />
            <NeutralPill
              label="precheck"
              value={fmtPct(wow?.precheck_pass_rate)}
              tooltip={tooltipTexts.health.precheckPassRate}
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
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}
