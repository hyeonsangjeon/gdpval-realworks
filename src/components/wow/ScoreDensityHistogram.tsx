import { motion } from 'framer-motion'
import { BarChart3, Sparkles } from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import type { WowSummary, ScoreDensityBucket } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'

interface Props {
  wow: WowSummary
  fallbackPcts?: number[]
  delay?: number
}

const BUCKETS = [
  '0-10%', '10-20%', '20-30%', '30-40%', '40-50%',
  '50-60%', '60-70%', '70-80%', '80-90%', '90-100%',
]

function bucketFromPct(pct: number): string {
  if (pct >= 100) return '90-100%'
  if (pct < 0) return '0-10%'
  const idx = Math.min(9, Math.floor(pct / 10))
  return BUCKETS[idx]
}

function colorForBucket(label: string): string {
  // Match green gradient up the buckets
  const idx = BUCKETS.indexOf(label)
  if (idx < 0) return 'hsl(220, 10%, 50%)'
  const hue = 0 + (idx / (BUCKETS.length - 1)) * 130
  return `hsl(${hue}, 70%, 50%)`
}

export default function ScoreDensityHistogram({ wow, fallbackPcts, delay = 0 }: Props) {
  let buckets: ScoreDensityBucket[] = wow.score_density_histogram ?? []
  if (buckets.length === 0 && fallbackPcts && fallbackPcts.length > 0) {
    const counts: Record<string, number> = Object.fromEntries(BUCKETS.map((b) => [b, 0]))
    for (const p of fallbackPcts) counts[bucketFromPct(p)] = (counts[bucketFromPct(p)] ?? 0) + 1
    buckets = BUCKETS.map((b) => ({ bucket: b, count: counts[b] ?? 0 }))
  }
  const hasData = buckets.length > 0 && buckets.some((b) => b.count > 0)

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
              <BarChart3 className="w-4 h-4 text-violet-400" />
              <span className="text-xs font-semibold tracking-wide text-foreground">
                Score Density (10 buckets)
              </span>
              <InfoTooltip content={tooltipTexts.wow.scoreDensity} position="top" />
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
                Histogram populates once tasks are graded.
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={buckets} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="bucket"
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                />
                <YAxis
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'hsl(var(--card))',
                    border: '1px solid hsl(var(--border))',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: 'hsl(var(--foreground))' }}
                  cursor={{ fill: 'hsl(var(--muted))' }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {buckets.map((b) => (
                    <Cell key={b.bucket} fill={colorForBucket(b.bucket)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
