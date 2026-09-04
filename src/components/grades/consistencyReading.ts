/**
 * How to read grader agreement without counting a single judgement as a
 * unanimous one.
 *
 * `GradeDetail` published a panel headed *Grader Consistency — agreement across
 * multiple graders* whose agree count was built like this:
 *
 * ```ts
 * const graded = grade.tasks.filter((t) => !t.error && t.scores.length > 0)
 * const agree = graded.filter((t) => new Set(t.scores).size === 1).length
 * ```
 *
 * A set built from a one-element array always has size 1. So on a run where
 * every task was judged exactly once, every graded task landed in `agree` and
 * the panel announced **100.0% Agree / 0.0% Disagree** — a unanimity among
 * graders who were never asked the same question. Measured over this
 * repository's own published grades: **eighteen of nineteen runs** print
 * `100.0%` today, and in all eighteen not one task carries a second score.
 *
 * The producer says so itself. `scripts/aggregate-grades.mjs` writes
 * `num_grades: 1, scores: [avgScore]` for every scored task, and documents
 * `inconsistent_grades` as *"Always 0 for single-judge runs (Phase A).
 * Populated by Phase B multi-judge aggregator."* No multi-judge producer exists
 * in this repository yet.
 *
 * Three sibling surfaces already got this right — `GradingAnalysisView` and
 * `GradesSummary` were guarded behind `inconsistent_grades > 0` by an earlier
 * change that `CHANGELOG.md` records as *"(i.e., Phase B multi-judge runs)"*,
 * and `GradeDetail` itself requires `scores.length > 1` in both its task filter
 * and its per-row badge. This panel, twenty-two lines above the first of those,
 * was the one place the guard was not applied.
 *
 * Kept apart from the card that renders it, and deliberately free of imports,
 * so `scripts/__tests__/a-single-judgement-is-not-graders-agreeing.test.mjs`
 * can execute the decision rather than pattern-match the JSX around it — the
 * same arrangement as `../wow/rateReading`, and for the same reason: a rule
 * about when *not* to print a percentage is only worth having if something
 * checks it.
 */

/** What an agreement figure is actually standing on. */
export type ConsistencyStanding =
  /** At least one task carries more than one score. Agreement was observable. */
  | 'measured'
  /** Tasks were graded, but never more than once each. Nothing was compared. */
  | 'single-judgement'
  /** No task carries a score at all. */
  | 'none-graded'

/** The fields of a task row this reading needs. */
export interface ConsistencyTask {
  error?: boolean
  scores?: readonly number[] | null
}

export interface ConsistencyReading {
  standing: ConsistencyStanding
  /**
   * Tasks whose scores could be set against each other.
   *
   * This is the denominator, and it is never substituted. The code this
   * replaces divided by `agree + disagree || 1`, which turns an empty
   * denominator into `0.0%` — a disagreement rate of zero, reported for a
   * comparison that did not happen.
   */
  compared: number
  /** Of `compared`, the tasks whose graders returned one distinct score. */
  agree: number
  /** Of `compared`, the tasks whose graders returned more than one. */
  disagree: number
  /**
   * Graded tasks carrying exactly one score.
   *
   * Counted separately and named on the page rather than folded into `agree`.
   * That a run asked one grader per task is worth knowing; it is not the same
   * finding as graders who were asked and concurred.
   */
  judgedOnce: number
  /** The agree bar length, or `null` when there is nothing to draw. */
  agreeFraction: number | null
  /** The disagree bar length, or `null` when there is nothing to draw. */
  disagreeFraction: number | null
  /** What goes in the agree slot. A percentage only when one was measured. */
  agreeValue: string
  /** What goes in the disagree slot. A percentage only when one was measured. */
  disagreeValue: string
  /** Why the panel is not an agreement rate, when it is not. */
  caveat?: string
}

const NOT_RECORDED = 'not recorded'

/**
 * Read grader agreement over the tasks that carried more than one score.
 *
 * A task judged once is not evidence of agreement and not evidence of
 * disagreement. It is excluded from the denominator and reported as
 * `judgedOnce`, which is the only honest place for it.
 *
 * That exclusion moves exactly one figure in this repository's published
 * grades, and moving it is the point: `dummy_gpt5_baseline` — legacy demo data,
 * flagged `is_dummy` by the aggregator — printed **75.8%** because one of its
 * 219 graded tasks carries a single score, the second grader having recorded
 * `Responses API did not complete within 3600.0 seconds`. A task whose second
 * grader timed out was counted as a task whose graders agreed. Over the 218
 * tasks that really were judged twice or more, the figure is **75.7%**.
 */
export function readGraderConsistency(
  tasks: readonly ConsistencyTask[] | null | undefined,
): ConsistencyReading {
  const graded = (Array.isArray(tasks) ? tasks : []).filter(
    (t) => !t?.error && Array.isArray(t?.scores) && t.scores.length > 0,
  )
  const compared = graded.filter((t) => (t.scores as readonly number[]).length > 1)
  const judgedOnce = graded.length - compared.length
  const agree = compared.filter(
    (t) => new Set(t.scores as readonly number[]).size === 1,
  ).length
  const disagree = compared.length - agree

  if (compared.length === 0) {
    const standing: ConsistencyStanding =
      graded.length > 0 ? 'single-judgement' : 'none-graded'
    return {
      standing,
      compared: 0,
      agree: 0,
      disagree: 0,
      judgedOnce,
      agreeFraction: null,
      disagreeFraction: null,
      agreeValue: NOT_RECORDED,
      disagreeValue: NOT_RECORDED,
      caveat:
        standing === 'single-judgement'
          ? `Not recorded: each of the ${judgedOnce} graded task${
              judgedOnce === 1 ? '' : 's'
            } in this run was judged once, so there was no second opinion to ` +
            'agree or disagree with. This is not 100% agreement.'
          : 'Not recorded: no task in this run carries a score.',
    }
  }

  const agreeFraction = agree / compared.length
  const disagreeFraction = disagree / compared.length
  return {
    standing: 'measured',
    compared: compared.length,
    agree,
    disagree,
    judgedOnce,
    agreeFraction,
    disagreeFraction,
    agreeValue: `${(agreeFraction * 100).toFixed(1)}%`,
    disagreeValue: `${(disagreeFraction * 100).toFixed(1)}%`,
    caveat:
      judgedOnce > 0
        ? `Over the ${compared.length} task${
            compared.length === 1 ? '' : 's'
          } judged more than once. ${judgedOnce} further graded task${
            judgedOnce === 1 ? ' was' : 's were'
          } judged once and cannot show agreement either way.`
        : undefined,
  }
}
