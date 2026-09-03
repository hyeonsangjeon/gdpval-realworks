/**
 * How to read one `summary.wow` pass rate without inventing a measurement.
 *
 * Kept apart from the cards that render it, and deliberately free of imports,
 * so `scripts/__tests__/wow-rate-denominator.test.mjs` can execute the decision
 * itself rather than pattern-match the JSX around it. A rule about when *not*
 * to print a percentage is only worth having if something checks it.
 *
 * `readHighMagnitudeRate` in `./highMagnitudeReading` is the same rule written
 * for one specific rate, with the wording a whole headline card can afford.
 * This is its plain-clothes sibling for the other three, and it adds the one
 * thing a single card never needed: whether two rates may be *compared*.
 *
 * `readJudgeErrorRate` at the foot of the file is the fifth and last `wow`
 * rate, kept separate because its polarity is inverted: for a pass rate an
 * absence and a zero both mean "nothing to show", and for an error rate a zero
 * is the good news, so the two must not share a code path.
 */

/**
 * What the published number is actually standing on.
 *
 * The producer's `_rate()` returns `0.0` for an empty denominator, which is the
 * same value — the same glyph — as "every item failed". `_wow_item_counts`
 * publishes the denominators so the two can be told apart; these are the states
 * that telling-apart yields.
 */
export type RateStanding =
  /** A denominator was recorded and it is non-zero. The rate means what it says. */
  | 'measured'
  /** A denominator was recorded and it is zero. Nothing was rated. */
  | 'none-counted'
  /** No denominator was recorded, so which of the two above this is, is unknown. */
  | 'denominator-unknown'
  /** The run published no such rate at all. */
  | 'absent'

export interface RateReading {
  standing: RateStanding
  /** What goes in the value slot. A percentage only when one was measured. */
  value: string
  /** The bar length, or `null` when there is nothing to draw. */
  fraction: number | null
  /**
   * Whether this rate may be set against another one.
   *
   * Only `measured` may. A gap taken against a rate that stands on nothing is
   * not a small gap or an uncertain one — one of its two terms does not exist.
   */
  comparable: boolean
  /** Why the number is not a pass or a failure, when it is not. */
  caveat?: string
}

/**
 * Read a published rate against the denominator it was divided by.
 *
 * `itemsDescribed` completes the phrase "no item was …" and "over N item(s) …",
 * so it is a participle: `'decided by a deterministic precheck'`.
 *
 * An absent denominator is not a zero one, and it is not a measured one either.
 * `item_counts` was added after most payloads were written and #393 recovered
 * it for only some of them, so `denominator-unknown` is the common case today
 * and is stated rather than quietly rounded into either neighbour.
 */
export function readWowRate(
  rate: number | null | undefined,
  counted: number | null | undefined,
  itemsDescribed: string,
): RateReading {
  const hasRate = typeof rate === 'number' && Number.isFinite(rate)
  const hasCount = typeof counted === 'number' && Number.isFinite(counted)

  if (hasCount && counted === 0) {
    // Not `0.0%`, and not a zero-length bar either: a bar drawn at zero is read
    // off the chart as the worst possible result, which is the one thing this
    // run did not measure.
    return {
      standing: 'none-counted',
      value: 'not recorded',
      fraction: null,
      comparable: false,
      caveat:
        `Not recorded: no item in this run was ${itemsDescribed}, ` +
        'so this is not a 0% pass rate.',
    }
  }
  if (!hasRate) {
    return {
      standing: 'absent',
      value: 'not recorded',
      fraction: null,
      comparable: false,
      caveat: 'This run did not publish the rate.',
    }
  }

  const value = `${(rate * 100).toFixed(1)}%`
  if (!hasCount) {
    return {
      standing: 'denominator-unknown',
      value,
      fraction: rate,
      comparable: false,
      caveat:
        'Denominator not recorded by this run, so a rate of 0% cannot be ' +
        'told apart from one that had nothing to rate.',
    }
  }
  return {
    standing: 'measured',
    value,
    fraction: rate,
    comparable: true,
    caveat: undefined,
  }
}

/** The participles the three rates below are read with, in one place. */
export const PRECHECK_ITEMS_DESCRIBED = 'decided by a deterministic precheck'
export const JUDGE_ITEMS_DESCRIBED = 'decided by the LLM judge'
export const RUBRIC_ITEMS_DESCRIBED = 'scored against the rubric'

/**
 * Which of structure and reasoning this run was stronger on, or `null` when
 * that question cannot be answered from what it published.
 *
 * The old form subtracted the two rates unconditionally. Measured across this
 * repository's own grades that produced a finding out of an absence: of the
 * published rows carrying a recorded precheck denominator and a rate of 0.0,
 * **twenty of twenty run-level rows and fifty-nine of fifty-nine sector rows
 * had no precheck items at all, and not one was a run where prechecks ran and
 * failed**. Every one of them subtracted a zero that stood for nothing and
 * announced "Strong on reasoning, weak on structure" — a finding about a check
 * that never ran, on a public page.
 *
 * That pair read fifteen and thirty-five when this was written, because only
 * that many zeros had a denominator to check against. #393 and then #399
 * recovered the rest of the published side, and every newly checkable zero
 * said the same thing the first fifteen did.
 */
export function structureVsReasoningInsight(
  precheck: RateReading,
  judge: RateReading,
): string | null {
  if (!precheck.comparable || !judge.comparable) return null
  const gap = (precheck.fraction as number) - (judge.fraction as number)
  if (Math.abs(gap) < 0.05) return 'Balanced structure and reasoning'
  if (gap > 0.15) return 'Strong on structure, weak on reasoning'
  if (gap < -0.15) return 'Strong on reasoning, weak on structure'
  return gap > 0 ? 'Slightly stronger on structure' : 'Slightly stronger on reasoning'
}

/**
 * What to say instead of a comparison, naming the side that is missing.
 *
 * "Cannot be compared" on its own invites a reader to assume a glitch. Saying
 * which half never happened is the finding — that this run did no deterministic
 * checking at all is worth knowing, and it is the opposite of weak structure.
 */
export function structureVsReasoningAbsence(
  precheck: RateReading,
  judge: RateReading,
): string {
  const unusable = [
    precheck.standing === 'measured' ? null : 'precheck',
    judge.standing === 'measured' ? null : 'LLM judge',
  ].filter((side): side is string => side !== null)
  const none = [
    precheck.standing === 'none-counted' ? 'precheck' : null,
    judge.standing === 'none-counted' ? 'LLM judge' : null,
  ].filter((side): side is string => side !== null)
  if (none.length > 0) {
    return `No comparison: this run rated no items by ${none.join(' or ')}.`
  }
  return `No comparison: the ${unusable.join(' and ')} denominator is not recorded by this run.`
}

/** Above this share of judged items erroring, a run is called out. */
export const JUDGE_ERROR_ALERT_THRESHOLD = 0.05

export interface ErrorRateReading {
  standing: RateStanding
  /** What goes in the value slot. A percentage only when one was published. */
  value: string
  /**
   * Whether to raise the alarm. Only ever true for a number the run published:
   * silence is not a clean bill of health.
   */
  alert: boolean
  /**
   * Whether the run is entitled to be shown as healthy — the other half of
   * `alert`, and not its negation. A rate that was never published is neither
   * over the threshold nor under it.
   */
  reassuring: boolean
  /** Why the number is neither a clean run nor a faulty one, when it is not. */
  caveat?: string
}

/**
 * Read `summary.wow.judge_error_rate` the way its four siblings are read.
 *
 * It was the last of the five `wow` rates with no reader, and the only one a
 * surface *coloured*: `GradingAnalysisView` asked `(rate ?? 0) > 0.05`, so a run
 * that published no rate scored `0`, failed the comparison, and was painted the
 * emerald this dashboard uses for a healthy run — beside two neighbours that
 * correctly printed `—`. The aggregator does emit that state: schema 1.0–1.2 is
 * checked by `validateHistoricalHeadline`, which reads six `openai_compat` keys
 * and never looks at `wow` at all, and `aggregate-grades.mjs` then publishes
 * `summary.wow || {}`. Sixteen of the nineteen published grade files are 1.0 or
 * 1.1. All sixteen carry a numeric rate today, so no page renders the green
 * pill right now; the guard that keeps it that way did not exist for them.
 *
 * An error rate inverts the polarity that makes `readWowRate` safe to reuse.
 * There, absence and zero both mean "no percentage to show". Here, zero is the
 * *good* result, so folding absence into it does not merely omit a finding —
 * it asserts the opposite one. Hence `reassuring` as a separate field: a caller
 * cannot get the green by writing `!alert`.
 */
export function readJudgeErrorRate(
  rate: number | null | undefined,
  counted: number | null | undefined,
): ErrorRateReading {
  const hasRate = typeof rate === 'number' && Number.isFinite(rate)
  const hasCount = typeof counted === 'number' && Number.isFinite(counted)

  if (hasCount && counted === 0) {
    return {
      standing: 'none-counted',
      value: '—',
      alert: false,
      reassuring: false,
      caveat:
        `Not recorded: no item in this run was ${JUDGE_ITEMS_DESCRIBED}, ` +
        'so this is not a run the judge got through without erroring.',
    }
  }
  if (!hasRate) {
    return {
      standing: 'absent',
      value: '—',
      alert: false,
      reassuring: false,
      caveat:
        'This run did not publish a judge error rate, so it is neither a ' +
        'clean run nor a faulty one — it is an unmeasured one.',
    }
  }

  const value = `${(rate * 100).toFixed(1)}%`
  const alert = rate > JUDGE_ERROR_ALERT_THRESHOLD
  if (!hasCount) {
    return {
      standing: 'denominator-unknown',
      value,
      alert,
      reassuring: !alert,
      caveat:
        'Denominator not recorded by this run, so the rate is shown as ' +
        'published and cannot be checked against the items it was divided by.',
    }
  }
  return { standing: 'measured', value, alert, reassuring: !alert }
}
