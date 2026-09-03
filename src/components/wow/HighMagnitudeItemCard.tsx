import { motion } from 'framer-motion'
import { ShieldAlert } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import type { WowSummary } from '../../types/grade'
import { tooltipTexts } from '../../data/tooltipTexts'
import {
  HIGH_MAGNITUDE_MIN_ABS_SCORE,
  readHighMagnitudeRate,
} from './highMagnitudeReading'

// The reading rule lives in `./highMagnitudeReading` — no imports, so a node
// test can run it — and is re-exported here so every existing importer of this
// card keeps its path.
export {
  HIGH_MAGNITUDE_MIN_ABS_SCORE,
  MIN_READABLE_HIGH_MAGNITUDE_ITEMS,
  readHighMagnitudeRate,
} from './highMagnitudeReading'
export type { HighMagnitudeReading } from './highMagnitudeReading'

interface Props {
  wow: WowSummary
  delay?: number
}

/**
 * A diagnostic, deliberately not shaped like the headline cards beside it.
 *
 * No WOW badge and no place in the top row: this number decided nothing, and
 * anything that looks like a headline gets read as one no matter what the
 * caption says. Owner decision of 2026-09-03, recorded in
 * `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`.
 */
export default function HighMagnitudeItemCard({ wow, delay = 0 }: Props) {
  const reading = readHighMagnitudeRate(
    wow.critical_item_pass_rate,
    wow.item_counts?.critical_items,
  )
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <Card className="bg-card/30 backdrop-blur border-border border-dashed h-full">
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <ShieldAlert className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs font-semibold tracking-wide text-foreground">
              High-magnitude item pass rate (|max score| ≥{' '}
              {HIGH_MAGNITUDE_MIN_ABS_SCORE})
            </span>
            <InfoTooltip content={tooltipTexts.wow.highMagnitudeItems} position="top" />
            <span className="px-1.5 py-0.5 rounded-md bg-muted/60 border border-border text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Diagnostic
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground/80 mb-3">
            Measured, but it decides nothing — not a pass gate, and not part of
            the score.
          </p>
          <p className="text-2xl font-bold text-foreground leading-none">
            {reading.value}
          </p>
          <p className="text-xs text-muted-foreground mt-2 leading-relaxed">
            {reading.denominator}
          </p>
          {reading.caveat && (
            <p className="text-xs text-amber-400/90 mt-1 leading-relaxed">
              {reading.caveat}
            </p>
          )}
          <p className="text-[11px] text-muted-foreground/70 mt-3 leading-relaxed">
            The rubric carries a <code>required</code> field and it is null on
            every item, so score magnitude stands in for necessity. These are
            the highest-scoring rubric items, not the required ones.
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}
