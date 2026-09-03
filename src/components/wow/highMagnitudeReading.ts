/**
 * How to read `summary.wow.critical_item_pass_rate` without overclaiming it.
 *
 * Kept apart from the card that renders it, and deliberately free of imports,
 * so `scripts/__tests__/high-magnitude-label.test.mjs` can execute the decision
 * itself rather than pattern-match the JSX around it. A rule about when *not*
 * to print a percentage is only worth having if something checks it.
 */

/**
 * The magnitude the grader treats as high-stakes: `core/grader.py`'s
 * `MAGNITUDE_THRESHOLD`, applied as `abs(max_score) >= 4`.
 *
 * The card used to say "weight ≥ 3" and call the items `"must-have"
 * requirements`. Both were wrong. The threshold is 4, it is read off the score
 * magnitude rather than any weight field, and nothing in the rubric marks these
 * items as required — the `required` field exists and is null on all 10,453
 * items across all 220 tasks, so magnitude stands in for necessity.
 */
export const HIGH_MAGNITUDE_MIN_ABS_SCORE = 4

/**
 * Fewer counted items than this and the rate is shown with a warning rather
 * than read as one.
 *
 * Derived, not chosen, from the 0.95 the specification wrote as the reference:
 * `Math.ceil(1 / (1 - 0.95))`. Under that many items a single failing item
 * moves the rate further than the whole distance between the reference and a
 * clean sweep, so the number says more about the denominator than the model.
 * `MIN_USABLE_REQUIRED_ITEMS` in `batch-runner/scripts/analyze_gold_ceiling.py`
 * derives the same value the same way.
 */
export const MIN_READABLE_HIGH_MAGNITUDE_ITEMS = 20

export interface HighMagnitudeReading {
  /** What goes in the big slot. Never a bare percentage. */
  value: string
  /** What the number is a rate of, or why it is not one. */
  denominator: string
  /** Present only when the rate is shown but cannot carry weight. */
  caveat?: string
}

/**
 * Turn the published rate and its denominator into something a reader can act
 * on, without ever printing `0.0%` for a run that counted nothing.
 *
 * An absent denominator is not a zero one. `item_counts.critical_items` was
 * added after most payloads were written, and #393 recovered it for only some
 * of them — 22 of the 33 published payloads and 62 of their 83 sector rows
 * carry it today, and not one of the 61 shard payloads does — so a real rate
 * with nothing behind it is still the common case, and that is stated rather
 * than hidden.
 */
export function readHighMagnitudeRate(
  rate: number | null | undefined,
  counted: number | null | undefined,
): HighMagnitudeReading {
  const hasRate = typeof rate === 'number' && Number.isFinite(rate)
  const hasCount = typeof counted === 'number' && Number.isFinite(counted)

  if (hasCount && counted === 0) {
    // Not `0.0%`. Nothing was counted, so there is nothing for the rate to be
    // a rate of, and a zero here is the same glyph a total failure would print.
    return {
      value: 'not recorded',
      denominator: `No item in this run scored |max| ≥ ${HIGH_MAGNITUDE_MIN_ABS_SCORE}.`,
    }
  }
  if (!hasRate) {
    return {
      value: 'not recorded',
      denominator: 'This run did not publish the rate.',
    }
  }

  const pct = `${(rate * 100).toFixed(1)}%`
  if (!hasCount) {
    return {
      value: pct,
      denominator:
        'Denominator not recorded by this run, so this cannot be told apart ' +
        'from a rate counted over a handful of items.',
    }
  }
  const reading: HighMagnitudeReading = {
    value: pct,
    denominator: `Over ${counted} item(s) scoring |max| ≥ ${HIGH_MAGNITUDE_MIN_ABS_SCORE}.`,
  }
  if (counted < MIN_READABLE_HIGH_MAGNITUDE_ITEMS) {
    reading.caveat =
      `${counted} item(s) is under the ${MIN_READABLE_HIGH_MAGNITUDE_ITEMS} ` +
      'this rate needs before it reads as one — a single item moves it ' +
      'further than the whole distance from 0.95 to a clean sweep.'
  }
  return reading
}
