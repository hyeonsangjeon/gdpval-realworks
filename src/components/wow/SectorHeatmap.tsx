import { motion } from 'framer-motion'
import { Grid3x3, Sparkles } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import type {
  WowSummary,
  RubricCategoryMetric,
  SectorWowMetric,
} from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'

interface Props {
  wow: WowSummary
  delay?: number
}

function colorFor(rate: number): string {
  // 0% red → 100% green via amber midpoint
  const clamped = Math.max(0, Math.min(1, rate))
  const hue = clamped * 130 // 0=red 130=green
  return `hsl(${hue}, 70%, 45%)`
}

type Row = { name: string; values: { key: string; rate: number; label?: string }[] }

function buildRubricCategoryRows(
  bySector: Record<string, SectorWowMetric>,
  byCategory: Record<string, RubricCategoryMetric>,
): Row[] | null {
  // Spec asks 11 sector × 3 category. We do not have per-sector
  // breakdown by category in the schema, only global. If we have neither
  // sector breakdown nor category breakdown, give up.
  const sectorKeys = Object.keys(bySector)
  const categoryKeys = Object.keys(byCategory)
  if (sectorKeys.length === 0 && categoryKeys.length === 0) return null
  return null
}

function buildSectorFallbackRows(
  bySector: Record<string, SectorWowMetric>,
): Row[] {
  return Object.entries(bySector).map(([name, m]) => ({
    name,
    values: [
      { key: 'precheck', rate: m.precheck_pass_rate, label: 'Precheck' },
      { key: 'judge', rate: m.judge_pass_rate, label: 'Judge' },
      { key: 'critical', rate: m.critical_item_pass_rate, label: 'Critical' },
    ],
  }))
}

export default function SectorHeatmap({ wow, delay = 0 }: Props) {
  const bySector = wow.by_sector || {}
  const byCategory = wow.by_rubric_category || {}

  // Prefer sector × category, else sector × {precheck, judge, critical}
  const categoryRows = buildRubricCategoryRows(bySector, byCategory)
  const rows: Row[] = categoryRows ?? buildSectorFallbackRows(bySector)
  const hasData = rows.length > 0

  const header = !categoryRows ? ['Precheck', 'Judge', 'Critical ≥3'] : []

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
              <Grid3x3 className="w-4 h-4 text-teal-400" />
              <span className="text-xs font-semibold tracking-wide text-foreground">
                Sector × Rubric Heatmap
              </span>
              <InfoTooltip content={tooltipTexts.wow.sectorHeatmap} position="top" />
            </div>
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-gradient-to-r from-fuchsia-500/15 to-violet-500/15 border border-fuchsia-400/30 text-[10px] font-bold uppercase tracking-wider text-fuchsia-400">
              <Sparkles className="w-2.5 h-2.5" />
              WOW
            </span>
          </div>

          {!hasData ? (
            <div className="py-6 text-center">
              <p className="text-sm text-muted-foreground italic">
                Data not available
              </p>
              <p className="text-[11px] text-muted-foreground/70 mt-1">
                Per-sector breakdown populates after a full-scale grading run.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr>
                    <th className="text-left text-muted-foreground font-normal pb-2">Sector</th>
                    {header.map((h) => (
                      <th key={h} className="text-center text-muted-foreground font-normal pb-2">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.name} className="border-t border-border/40">
                      <td className="py-1.5 pr-3 text-foreground truncate max-w-[200px]" title={row.name}>
                        {row.name}
                      </td>
                      {row.values.map((v) => (
                        <td key={v.key} className="py-1.5 px-1">
                          <div
                            className="rounded text-center font-mono text-[11px] font-semibold text-white py-1"
                            style={{ backgroundColor: colorFor(v.rate) }}
                            title={`${v.label ?? v.key}: ${(v.rate * 100).toFixed(1)}%`}
                          >
                            {(v.rate * 100).toFixed(0)}%
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
