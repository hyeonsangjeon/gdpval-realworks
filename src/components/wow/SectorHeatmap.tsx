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
import {
  HIGH_MAGNITUDE_MIN_ABS_SCORE,
  MIN_READABLE_HIGH_MAGNITUDE_ITEMS,
} from './highMagnitudeReading'
import {
  JUDGE_ITEMS_DESCRIBED,
  PRECHECK_ITEMS_DESCRIBED,
  readWowRate,
} from './rateReading'

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

/**
 * A cell whose rate cannot be read as a verdict, so it is not painted like one.
 *
 * Colour is the whole claim of a heatmap: red says the model failed here. A
 * column earns that only when items were counted for it. Across the 447 sector
 * rows published so far, 385 record no denominator at all; of the 62 that do,
 * **35 rows rate no precheck items whatever and every one of them publishes
 * `precheck_pass_rate: 0.0`, while not one is a sector where prechecks ran and
 * failed**. Painted, all 35 read as a total structural failure.
 */
const UNREADABLE_CELL = 'hsl(220, 8%, 28%)'

type CellValue = {
  key: string
  rate: number
  label?: string
  /** Why this cell is not a verdict; renders muted, with the reason on hover. */
  unreadable?: string
  /**
   * Nothing was rated in this cell, so it has no percentage to show.
   *
   * Distinct from `unreadable` alone: a cell whose denominator merely went
   * unrecorded still holds a real rate and shows it greyed, whereas this one
   * would be printing the `0%` that the empty denominator invented.
   */
  notCounted?: boolean
}

type Row = { name: string; values: CellValue[] }

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

/**
 * Why this sector's high-magnitude rate is not a verdict, or `undefined` if it
 * is. Mirrors `readHighMagnitudeRate`, minus the wording a whole card can
 * afford: a heatmap cell has a tooltip and nothing else.
 */
function highMagnitudeCaveat(m: SectorWowMetric): string | undefined {
  const counted = m.item_counts?.critical_items
  if (typeof counted !== 'number' || !Number.isFinite(counted)) {
    return 'Denominator not recorded by this run, so this rate cannot be read as a pass or a failure.'
  }
  if (counted === 0) {
    return `Not recorded: no item in this sector scored |max| ≥ ${HIGH_MAGNITUDE_MIN_ABS_SCORE}, so this is not a 0% pass rate.`
  }
  if (counted < MIN_READABLE_HIGH_MAGNITUDE_ITEMS) {
    return `Over ${counted} item(s) only — under the ${MIN_READABLE_HIGH_MAGNITUDE_ITEMS} this rate needs before it reads as one.`
  }
  return undefined
}

function buildSectorFallbackRows(
  bySector: Record<string, SectorWowMetric>,
): Row[] {
  return Object.entries(bySector).map(([name, m]) => {
    const precheck = readWowRate(
      m.precheck_pass_rate,
      m.item_counts?.precheck_items,
      PRECHECK_ITEMS_DESCRIBED,
    )
    const judge = readWowRate(
      m.judge_pass_rate,
      m.item_counts?.judge_items,
      JUDGE_ITEMS_DESCRIBED,
    )
    return {
      name,
      values: [
        {
          key: 'precheck',
          rate: m.precheck_pass_rate,
          label: 'Precheck',
          unreadable: precheck.caveat,
          notCounted: precheck.standing === 'none-counted',
        },
        {
          key: 'judge',
          rate: m.judge_pass_rate,
          label: 'Judge',
          unreadable: judge.caveat,
          notCounted: judge.standing === 'none-counted',
        },
        {
          key: 'critical',
          rate: m.critical_item_pass_rate,
          label: `High-magnitude (|max| ≥ ${HIGH_MAGNITUDE_MIN_ABS_SCORE}, diagnostic)`,
          unreadable: highMagnitudeCaveat(m),
          notCounted: m.item_counts?.critical_items === 0,
        },
      ],
    }
  })
}

export default function SectorHeatmap({ wow, delay = 0 }: Props) {
  const bySector = wow.by_sector || {}
  const byCategory = wow.by_rubric_category || {}

  // Prefer sector × category, else sector × {precheck, judge, critical}
  const categoryRows = buildRubricCategoryRows(bySector, byCategory)
  const rows: Row[] = categoryRows ?? buildSectorFallbackRows(bySector)
  const hasData = rows.length > 0
  const hasUnreadable = rows.some((row) => row.values.some((v) => v.unreadable))

  const header = !categoryRows
    ? ['Precheck', 'Judge', `High-mag ≥${HIGH_MAGNITUDE_MIN_ABS_SCORE}`]
    : []

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
                            className={
                              v.unreadable
                                ? 'rounded text-center font-mono text-[11px] font-semibold text-muted-foreground py-1 border border-dashed border-border'
                                : 'rounded text-center font-mono text-[11px] font-semibold text-white py-1'
                            }
                            style={{
                              backgroundColor: v.unreadable
                                ? UNREADABLE_CELL
                                : colorFor(v.rate),
                            }}
                            title={
                              v.unreadable
                                ? `${v.label ?? v.key}: ${
                                    v.notCounted
                                      ? 'not recorded'
                                      : `${(v.rate * 100).toFixed(1)}%`
                                  } — ${v.unreadable}`
                                : `${v.label ?? v.key}: ${(v.rate * 100).toFixed(1)}%`
                            }
                          >
                            {v.notCounted ? '—' : `${(v.rate * 100).toFixed(0)}%`}
                            {v.unreadable ? '*' : ''}
                          </div>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {hasUnreadable && (
                <p className="text-[11px] text-muted-foreground/80 mt-3 leading-relaxed">
                  * Greyed cells are not verdicts. A cell is greyed when the run
                  recorded no denominator for it, when it rated no items at all
                  (shown <span className="font-mono">—</span>, never 0%), or —
                  for the high-magnitude column — when it counted fewer than{' '}
                  {MIN_READABLE_HIGH_MAGNITUDE_ITEMS} items. That column is a
                  diagnostic over items scoring |max| ≥{' '}
                  {HIGH_MAGNITUDE_MIN_ABS_SCORE} — not over items the rubric
                  marks required, since its <code>required</code> field is null
                  everywhere. Hover for the reason.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
