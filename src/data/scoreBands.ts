/**
 * The score bands the dashboard prints, and the thresholds they are counted at.
 *
 * `summary.openai_compat.perfect_count` and `zero_count` come from the grading
 * backend, which counts them at **>= 99%** and **<= 1%** — not at 100% and 0%.
 * The field names are kept for compatibility with the OpenAI-shaped fields they
 * mirror; the thresholds are the ones below. PR #371 corrected the backend's
 * wording to say so rather than moving the boundary, because the counts are
 * already published and moving a threshold would change every run on the board.
 * That PR deliberately left the dashboard alone. This module is the dashboard's
 * half of the same correction, kept in one place so the five components that
 * print these counts cannot drift apart again.
 *
 * Two rows on the board today are the reason this is not hypothetical: one task
 * scored 99.77% and one scored 0.9%, and both were published under a label that
 * asserted an exact figure neither of them had.
 *
 * `NEAR_PERFECT_MIN_PCT` / `NEAR_ZERO_MAX_PCT` must stay equal to the constants
 * of the same name in `scripts/aggregate-grades.mjs`, which is what actually
 * sorts the rows into bands. `scripts/__tests__/near-perfect-labels.test.mjs`
 * fails if the two files drift.
 */
export const NEAR_PERFECT_MIN_PCT = 99
export const NEAR_ZERO_MAX_PCT = 1

/** Long forms, for labels that previously carried a `(100%)` / `(0%)` suffix. */
export const NEAR_PERFECT_LABEL = `Near-perfect (≥${NEAR_PERFECT_MIN_PCT}%)`
export const NEAR_ZERO_LABEL = `Near-zero (≤${NEAR_ZERO_MAX_PCT}%)`

/** Short forms, for chips, badges and the tight stat grids. */
export const NEAR_PERFECT_SHORT = 'Near-perfect'
export const NEAR_ZERO_SHORT = 'Near-zero'
export const PARTIAL_SHORT = 'Partial'

/**
 * Band definitions, written so that a reader who trusts the label is not misled
 * by it. Each one states the threshold and, where the name oversells, says so.
 */
export const NEAR_PERFECT_DEF =
  `Tasks scored ${NEAR_PERFECT_MIN_PCT}% or above by the LLM-judge — near-perfect, not necessarily full marks. ` +
  'A task that dropped a fraction of a point is counted here, so read this as an upper bound on how many scored exactly 100%.'
export const PARTIAL_DEF =
  `Tasks scored above ${NEAR_ZERO_MAX_PCT}% and below ${NEAR_PERFECT_MIN_PCT}% by the LLM-judge. ` +
  'The output met some but not all rubric criteria.'
export const NEAR_ZERO_DEF =
  `Tasks scored ${NEAR_ZERO_MAX_PCT}% or below by the LLM-judge — near-zero, not necessarily exactly zero. ` +
  'A task that earned a fraction of a percent is counted here.'

/** One-line summary of all three bands, for section hints. */
export const SCORE_BANDS_HINT =
  `Scores: ${NEAR_PERFECT_LABEL}, Partial (in between), ${NEAR_ZERO_LABEL}. ` +
  'The band names are thresholds, not exact figures.'

/**
 * The percentage to print for one task row.
 *
 * `avg_score` is snapped to a flat 1.0/0.0 once a task crosses a band boundary
 * so that the Status badges agree with the summary counts, which means it can
 * no longer state the score it came from. The aggregator carries the unsnapped
 * figure as `pct_exact` on exactly the rows the snap moved, so prefer it when
 * it is there and fall back to `avg_score` — which is the true score — when it
 * is not. One decimal place on a snapped row, none otherwise: the decimal is
 * the whole point of printing it, and adding one everywhere would restyle 218
 * rows that were already correct.
 */
export function formatTaskScorePct(task: {
  avg_score?: number | null
  pct_exact?: number
}): string | null {
  if (typeof task.pct_exact === 'number') return `${task.pct_exact.toFixed(1)}%`
  if (typeof task.avg_score !== 'number') return null
  return `${(task.avg_score * 100).toFixed(0)}%`
}
