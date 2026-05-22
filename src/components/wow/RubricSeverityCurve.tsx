import { motion } from 'framer-motion'
import { TrendingDown, Sparkles } from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'

interface Props {
  wow: WowSummary
  delay?: number
}

export default function RubricSeverityCurve({ wow, delay = 0 }: Props) {
  const points = (wow.rubric_severity_curve ?? []).map((p) => ({
    weight: p.weight,
    pass_rate_pct: Math.round(p.pass_rate * 1000) / 10,
    n_items: p.n_items,
  }))
  const hasData = points.length > 0

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
              <TrendingDown className="w-4 h-4 text-rose-400" />
              <span className="text-xs font-semibold tracking-wide text-foreground">
                Rubric Severity Curve
              </span>
              <InfoTooltip content={tooltipTexts.wow.rubricSeverity} position="top" />
            </div>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-gradient-to-r from-fuchsia-500/15 to-violet-500/15 border border-fuchsia-400/30 text-[10px] font-bold uppercase tracking-wider text-fuchsia-400">
              <Sparkles className="w-2.5 h-2.5" />
              WOW
            </span>
          </div>

          {!hasData ? (
            <div className="py-6 text-center">
              <p className="text-sm text-muted-foreground italic">Data not available</p>
              <p className="text-[11px] text-muted-foreground/70 mt-1">
                Severity curve populates after a full-scale grading run.
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={points} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="weight"
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  label={{ value: 'Item weight', position: 'insideBottom', offset: -2, fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                />
                <YAxis
                  stroke="hsl(var(--muted-foreground))"
                  domain={[0, 100]}
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 11 }}
                  label={{ value: 'Pass %', angle: -90, position: 'insideLeft', fontSize: 10, fill: 'hsl(var(--muted-foreground))' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="pass_rate_pct"
                  stroke="hsl(340, 80%, 60%)"
                  strokeWidth={2}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
