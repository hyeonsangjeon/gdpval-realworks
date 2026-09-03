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
 * rows carrying a recorded precheck denominator and a rate of 0.0, **fifteen of
 * fifteen run-level rows and thirty-five of thirty-five sector rows had no
 * precheck items at all, and not one was a run where prechecks ran and
 * failed**. Every one of them subtracted a zero that stood for nothing and
 * announced "Strong on reasoning, weak on structure" — a finding about a check
 * that never ran, on a public page.
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
