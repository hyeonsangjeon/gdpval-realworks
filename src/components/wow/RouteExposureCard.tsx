import { motion } from 'framer-motion'
import { AudioLines } from 'lucide-react'
import { Card, CardContent } from '../ui/card'
import InfoTooltip from '../common/InfoTooltip'
import { tooltipTexts } from '../../data/tooltipTexts'
import { readRouteExposure, formatRouteShare, AUDIO_ROUTE, type RouteComposition } from './routeExposure'

// The reading rule lives in `./routeExposure` — no imports, so a node test can
// run it — and is re-exported here so importers of this card keep one path.
export { readRouteExposure, AUDIO_ROUTE, formatRouteShare } from './routeExposure'
export type {
  RouteComposition,
  RouteExposureReading,
  RouteExposureState,
  RouteRow,
} from './routeExposure'

interface Props {
  composition?: RouteComposition | null
  delay?: number
}

/**
 * How much of the score rests on the sub-judge that does not work.
 *
 * A diagnostic, shaped like the high-magnitude card beside it rather than like
 * the headline cards above: it reports what was graded, not how well. The
 * audio sub-judge's own measurement — 0.00 discrimination against clips whose
 * answers were known — is the reason this is worth a card at all, and the
 * reason a run that recorded no route says so instead of showing a zero.
 */
export default function RouteExposureCard({ composition, delay = 0 }: Props) {
  const reading = readRouteExposure(composition)
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay }}
    >
      <Card className="bg-card/30 backdrop-blur border-border border-dashed h-full">
        <CardContent className="p-5">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <AudioLines className="w-4 h-4 text-muted-foreground" />
            <span className="text-xs font-semibold tracking-wide text-foreground">
              Weight decided by the audio sub-judge
            </span>
            <InfoTooltip content={tooltipTexts.wow.routeExposure} position="top" />
            <span className="px-1.5 py-0.5 rounded-md bg-muted/60 border border-border text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              Diagnostic
            </span>
          </div>
          <p className="text-[11px] text-muted-foreground/80 mb-3">
            Measured against clips whose answers were known, it scored a
            discrimination of 0.00 — a coin, and more confident when wrong.
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
          {reading.rows.length > 0 && (
            <div className="mt-4">
              <p className="text-[11px] text-muted-foreground/70 mb-1.5">
                Every route, by share of scored rubric weight:
              </p>
              <div className="space-y-1">
                {reading.rows.map((row) => (
                  <div
                    key={row.route}
                    className="flex items-baseline justify-between gap-3 text-[11px]"
                  >
                    <span
                      className={
                        row.route === AUDIO_ROUTE
                          ? 'font-semibold text-amber-400/90'
                          : 'text-muted-foreground'
                      }
                    >
                      {row.route}
                    </span>
                    <span className="text-muted-foreground/70 tabular-nums">
                      {formatRouteShare(row.scoredMaxShare)} · {row.items} item(s) ·{' '}
                      {row.tasks} task(s)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <p className="text-[11px] text-muted-foreground/70 mt-3 leading-relaxed">
            Recomputed from each item's recorded route, not from a summary
            field. It changes no score and decides nothing — how the audio-graded
            items should ultimately be treated is still an open decision.
          </p>
        </CardContent>
      </Card>
    </motion.div>
  )
}
