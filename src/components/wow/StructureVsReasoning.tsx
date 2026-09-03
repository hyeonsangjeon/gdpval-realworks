import { motion } from 'framer-motion'
import { Sparkles, GitCompare } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'
import {
  JUDGE_ITEMS_DESCRIBED,
  PRECHECK_ITEMS_DESCRIBED,
  readWowRate,
  structureVsReasoningAbsence,
  structureVsReasoningInsight,
  type RateReading,
} from './rateReading'

interface Props {
  wow: WowSummary
  delay?: number
}

export default function StructureVsReasoning({ wow, delay = 0 }: Props) {
  const precheck = readWowRate(
    wow.precheck_pass_rate,
    wow.item_counts?.precheck_items,
    PRECHECK_ITEMS_DESCRIBED,
  )
  const judge = readWowRate(
    wow.judge_pass_rate,
    wow.item_counts?.judge_items,
    JUDGE_ITEMS_DESCRIBED,
  )
  const insight = structureVsReasoningInsight(precheck, judge)
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <Card className="bg-card/50 backdrop-blur border-border h-full">
        <CardContent className="p-5">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-sky-400" />
              <span className="text-xs font-semibold tracking-wide text-foreground">
                Structure vs Reasoning
              </span>
              <InfoTooltip content={tooltipTexts.wow.structureVsReasoning} position="top" />
            </div>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-gradient-to-r from-fuchsia-500/15 to-violet-500/15 border border-fuchsia-400/30 text-[10px] font-bold uppercase tracking-wider text-fuchsia-400">
              <Sparkles className="w-2.5 h-2.5" />
              WOW
            </span>
          </div>

          <div className="space-y-3 mt-3">
            <BarRow label="Precheck (deterministic)" reading={precheck} color="bg-emerald-500" />
            <BarRow label="LLM Judge (reasoning)" reading={judge} color="bg-sky-500" />
          </div>

          <p className="text-xs text-muted-foreground mt-4 italic">
            {insight ?? structureVsReasoningAbsence(precheck, judge)}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function BarRow({
  label,
  reading,
  color,
}: {
  label: string
  reading: RateReading
  color: string
}) {
  // No bar at all when there is no rate to draw. A bar at zero length is the
  // picture of total failure, and here it would be drawn out of an empty
  // denominator — the one thing the run did not measure.
  const pct =
    reading.fraction === null
      ? null
      : Math.max(0, Math.min(100, reading.fraction * 100))
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
        <span>{label}</span>
        <span
          className={
            reading.standing === 'measured'
              ? 'font-mono text-foreground'
              : 'font-mono text-muted-foreground'
          }
        >
          {reading.value}
        </span>
      </div>
      <div className="h-2.5 w-full rounded-full overflow-hidden bg-muted">
        {pct !== null && (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
            className={`${color} h-full`}
          />
        )}
      </div>
      {reading.caveat && (
        <p className="text-[10px] text-muted-foreground/80 mt-1 leading-relaxed">
          {reading.caveat}
        </p>
      )}
    </div>
  )
}
