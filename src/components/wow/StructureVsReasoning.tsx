import { motion } from 'framer-motion'
import { Sparkles, GitCompare } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'

interface Props {
  wow: WowSummary
  delay?: number
}

function pctFmt(v: number): string {
  return `${(v * 100).toFixed(1)}%`
}

function insightLabel(precheck: number, judge: number): string {
  const gap = precheck - judge
  if (Math.abs(gap) < 0.05) return 'Balanced structure and reasoning'
  if (gap > 0.15) return 'Strong on structure, weak on reasoning'
  if (gap < -0.15) return 'Strong on reasoning, weak on structure'
  return gap > 0 ? 'Slightly stronger on structure' : 'Slightly stronger on reasoning'
}

export default function StructureVsReasoning({ wow, delay = 0 }: Props) {
  const precheck = wow.precheck_pass_rate
  const judge = wow.judge_pass_rate
  const insight = insightLabel(precheck, judge)
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
            <BarRow label="Precheck (deterministic)" value={precheck} color="bg-emerald-500" />
            <BarRow label="LLM Judge (reasoning)" value={judge} color="bg-sky-500" />
          </div>

          <p className="text-xs text-muted-foreground mt-4 italic">
            {insight}
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function BarRow({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.max(0, Math.min(100, value * 100))
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
        <span>{label}</span>
        <span className="font-mono text-foreground">{pctFmt(value)}</span>
      </div>
      <div className="h-2.5 w-full rounded-full overflow-hidden bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className={`${color} h-full`}
        />
      </div>
    </div>
  )
}
