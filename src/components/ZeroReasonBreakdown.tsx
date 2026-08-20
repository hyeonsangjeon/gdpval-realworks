import { motion } from 'framer-motion'
import { Gavel, FileWarning, Ban, PackageX, HelpCircle, ShieldQuestion } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from './ui/card'
import InfoTooltip from './common/InfoTooltip'
import type { SelectionOutcome, SelectionSummary, ZeroReason } from '../types/grade'

// A zero on this benchmark can mean two very different things, and until now
// the dashboard rendered both in the same red. Either a judge read the work and
// awarded nothing, or nothing gradeable ever reached a judge and the pipeline
// recorded the absence as a score. The first is a result. The second is a bug
// report wearing a result's clothing.
//
// A third case is not a zero at all: the selector refused to pick a primary
// deliverable and the task was dropped from the average. Those are kept in a
// separate block below, because folding them into the zero count would put a
// number on screen that contradicts the published zero_score right above it.
//
// This card restates no published figure. The headline average, the zero count
// and the error count all still come from the grade JSON untouched; this only
// says what they were made of.

interface ReasonStyle {
  icon: typeof Gavel
  accent: string
  bar: string
  blurb: string
}

const REASON_STYLES: Record<SelectionOutcome, ReasonStyle> = {
  content_zero: {
    icon: Gavel,
    accent: 'text-red-500',
    bar: 'bg-red-500',
    blurb: 'A judge read the deliverable and awarded no credit. This one is a verdict on the work.',
  },
  format_unmet: {
    icon: FileWarning,
    accent: 'text-amber-500',
    bar: 'bg-amber-500',
    blurb: 'Real files were produced, but none in the format the task asked for, so there was no primary deliverable to grade.',
  },
  inference_failed: {
    icon: PackageX,
    accent: 'text-orange-500',
    bar: 'bg-orange-500',
    blurb: 'Inference never produced a file. Only the failed_to_generate placeholder reached grading.',
  },
  no_deliverable: {
    icon: Ban,
    accent: 'text-orange-400',
    bar: 'bg-orange-400',
    blurb: 'Nothing was left once the task’s own reference files were subtracted from the output.',
  },
  unclassified: {
    icon: HelpCircle,
    accent: 'text-muted-foreground',
    bar: 'bg-muted-foreground',
    blurb: 'This task predates selection reporting, so the reason was never recorded.',
  },
  not_selected: {
    icon: ShieldQuestion,
    accent: 'text-violet-400',
    bar: 'bg-violet-400',
    blurb: 'Valid candidates existed, but the selector would not pick a primary one without guessing, so it declined rather than grade an arbitrary file.',
  },
  grading_error: {
    icon: HelpCircle,
    accent: 'text-orange-500',
    bar: 'bg-orange-500',
    blurb: 'Grading raised an error before a verdict was reached.',
  },
  scored: { icon: Gavel, accent: '', bar: '', blurb: '' },
}

// Which reasons landed a zero in the average, and which took the task out of it
// entirely. `error !== null` in the grade JSON is what excludes a task, and
// those are exactly the two outcomes below.
const EXCLUDED_OUTCOMES: SelectionOutcome[] = ['not_selected', 'grading_error']

function ReasonRow({ reason, denominator }: { reason: ZeroReason; denominator: number }) {
  const style = REASON_STYLES[reason.outcome] ?? REASON_STYLES.unclassified
  const Icon = style.icon
  const share = denominator > 0 ? Math.min(100, (reason.count / denominator) * 100) : 0
  return (
    <div className="flex items-start gap-3">
      <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${style.accent}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-medium text-foreground">{reason.label}</span>
          <span className={`text-sm font-mono tabular-nums ${style.accent}`}>{reason.count}</span>
        </div>
        <div className="h-1.5 rounded-full bg-muted/40 mt-1.5 mb-1.5 overflow-hidden">
          <div className={`h-full rounded-full ${style.bar}`} style={{ width: `${share}%` }} />
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed">{style.blurb}</p>
      </div>
    </div>
  )
}

export default function ZeroReasonBreakdown({
  selection,
  delay = 0,
}: {
  selection?: SelectionSummary
  delay?: number
}) {
  // Grades written before the selector recorded its reasoning carry no
  // metadata to decompose. Rendering an empty or guessed breakdown for them
  // would put invented structure on old experiments, so the card stays away.
  if (!selection?.covered) return null

  const reasons = selection.zero_reasons ?? []
  if (reasons.length === 0) return null

  const zeroRows = reasons.filter((r) => !EXCLUDED_OUTCOMES.includes(r.outcome))
  const excludedRows = reasons.filter((r) => EXCLUDED_OUTCOMES.includes(r.outcome))

  const zeroTotal = zeroRows.reduce((acc, r) => acc + r.count, 0)
  const excludedTotal = excludedRows.reduce((acc, r) => acc + r.count, 0)
  if (zeroTotal === 0 && excludedTotal === 0) return null

  // judged + unjudged are the zeros whose cause the selector recorded. An
  // `unclassified` zero on a partially-covered grade is deliberately outside
  // both, so the sentence below never claims to know what it does not.
  const judged = selection.judged_zero
  const unjudged = selection.unjudged_zero
  const accounted = judged + unjudged
  const barDenominator = Math.max(zeroTotal, excludedTotal, 1)

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="mb-8"
    >
      <Card className="bg-card/50 backdrop-blur border-border">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Gavel className="h-5 w-5 text-primary" />
            Where the unscored tasks went
            <InfoTooltip
              content="Derived from the selector metadata the grader already writes. It explains the published zero and error counts; it does not change them."
              position="top"
            />
          </CardTitle>
          {accounted > 0 && (
            <p className="text-sm text-muted-foreground mt-1">
              {judged === 0 ? (
                <>
                  None of the <strong className="text-foreground">{accounted}</strong> zeros here is a
                  judge&rsquo;s verdict &mdash; in every one, no gradeable deliverable reached a judge.
                </>
              ) : (
                <>
                  <strong className="text-foreground">{judged}</strong> of{' '}
                  <strong className="text-foreground">{accounted}</strong>{' '}
                  {accounted === 1 ? 'zero' : 'zeros'} {judged === 1 ? 'is' : 'are'} a
                  judge&rsquo;s verdict on the work. The other{' '}
                  <strong className="text-foreground">{unjudged}</strong> never had a
                  deliverable in front of one.
                </>
              )}
            </p>
          )}
        </CardHeader>
        <CardContent>
          {zeroRows.length > 0 && (
            <>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Scored zero &mdash; counts toward the average
              </h4>
              <div className="space-y-3">
                {zeroRows.map((reason) => (
                  <ReasonRow key={reason.outcome} reason={reason} denominator={barDenominator} />
                ))}
              </div>
            </>
          )}

          {excludedRows.length > 0 && (
            <>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-6 mb-3 pt-5 border-t border-border/60">
                Excluded from the average &mdash; not scored at all
              </h4>
              <div className="space-y-3">
                {excludedRows.map((reason) => (
                  <ReasonRow key={reason.outcome} reason={reason} denominator={barDenominator} />
                ))}
              </div>
            </>
          )}

          {(unjudged > 0 || excludedTotal > 0) && (
            <p className="text-xs text-muted-foreground leading-relaxed mt-5 pt-4 border-t border-border/60">
              {unjudged > 0 && (
                <>
                  <strong className="text-foreground">{unjudged}</strong>{' '}
                  {unjudged === 1 ? 'task counts' : 'tasks count'} toward the headline average as a
                  zero without a judge having assessed anything.{' '}
                </>
              )}
              {excludedTotal > 0 && (
                <>
                  A further <strong className="text-foreground">{excludedTotal}</strong>{' '}
                  {excludedTotal === 1 ? 'is' : 'are'} left out of the average entirely.{' '}
                </>
              )}
              Reading the score as a measure of the model alone overstates what the number covers.
            </p>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
