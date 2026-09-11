import type { TaskResult } from '../types/report'

/**
 * Why a task did not finish, as the run itself recorded it.
 *
 * The pipeline has always written this down. `core/execution_errors.py` maps a
 * provider's own words to a fixed category, the backends attach it at
 * `observability.error_category`, and `core/run_record.py` keeps it beside the
 * pipeline's error for a stated reason:
 *
 *   "A model that was stopped for content and a run place that could not reach
 *    the deployment both leave a task unfinished, and only the first is a
 *    benchmark result."
 *
 * Nothing on the dashboard read it. The one panel that claimed to show a
 * failure is gated on `task.error`, a free-text string, and the merge that
 * would populate it reads `error_tasks[].error` — a key exp034's eight failed
 * tasks do not have. They carry `error_code: "task_execution_error"` and
 * `error_type: "TaskExecutionError"`, which name the exception class and not
 * the cause. So the gate is false, the panel does not render, and a failed task
 * shows a red cross, zero files, and no reason at all.
 *
 * exp034's eight are five `rate_limited` and three `content_filtered`. Those
 * are opposite findings — one says the run could not get a call through, the
 * other says the model was asked a real question and what it produced was
 * refused — and the page painted them identically.
 *
 * ## Why this names one category and buckets nothing
 *
 * The obvious next move is a table sorting every category into "the model's
 * doing" and "the run place's doing". `run_record.py` says why that cannot be
 * written:
 *
 *   "Only these four are named because only these four are enumerable: what a
 *    started turn reports comes from `classify_execution_error`, whose
 *    vocabulary is open, so the complement cannot be written down."
 *
 * A closed table over an open vocabulary would quietly file every category
 * added later under whichever side was the default. So this module makes
 * exactly one claim — the one the pipeline states in its own source — and
 * otherwise repeats the recorded word without interpreting it.
 */

/**
 * The single category the pipeline declares a benchmark result.
 *
 * `_CONTENT_FILTER_MARKERS` in `core/execution_errors.py`: "This is a benchmark
 * result, not a fault of the run: the model was asked a real question and what
 * it produced was refused. It must not read as an infrastructure failure, and
 * it must not be retried -- retrying it until something gets through is how a
 * filtered task turns into a scored one."
 */
export const CONTENT_FILTERED = 'content_filtered'

/** Shown beside a `content_filtered` task, so it is not read as a run defect. */
export const CONTENT_FILTERED_NOTE =
  '제공자가 모델이 낸 답을 내용 때문에 막았습니다. 벤치마크 결과이며 실행 환경 결함이 아닙니다.'

/**
 * Shown when a failed task carries no category.
 *
 * Not "unknown error": the difference between "the run looked and found this"
 * and "the run never wrote anything down" is the difference between a result
 * and a recording gap, and only the second is something to go fix.
 */
export const NO_REASON_RECORDED = '이 실행은 실패 원인을 기록하지 않았습니다'

/** Reminds the reader that the word below is the run's, not this page's. */
export const REASON_IS_VERBATIM_NOTE = '실행이 기록한 값 그대로입니다'

/**
 * The category this task recorded, or `null` if it recorded none.
 *
 * `observability` is indexed as `unknown`, and a report fetched at read time is
 * whatever the hub returns, so the type is checked rather than asserted. A
 * blank string is treated as absent — it is a field that exists and says
 * nothing, which is the same state for a reader.
 */
export function readFailureCategory(task: TaskResult): string | null {
  const category = task.observability?.error_category
  if (typeof category !== 'string') return null
  const trimmed = category.trim()
  return trimmed ? trimmed : null
}

/** Whether this failure is a benchmark outcome rather than a run defect. */
export function isBenchmarkOutcome(category: string | null): boolean {
  return category === CONTENT_FILTERED
}

/** The failure a `rate_limit_kind` accompanies. Read from nothing else. */
export const RATE_LIMITED = 'rate_limited'

/**
 * The only three words `rate_limit_kind` may hold.
 *
 * Mirrors `RATE_LIMIT_KINDS` in `core/codex_runner.py`. Closed on the Python
 * side for a reason that applies here too: the word is read out of a provider
 * sentence that names the deployment, and membership of a fixed set is what
 * stops that sentence following it into an artifact. Re-checking it on read
 * costs nothing and means a value that somehow got past the writer does not
 * get rendered.
 */
export const RATE_LIMIT_KINDS = ['token', 'request', 'unattributed'] as const

export type RateLimitKind = (typeof RATE_LIMIT_KINDS)[number]

/**
 * What each kind means, and what it implies about the fix.
 *
 * `core/codex_runner.py` states why the distinction is worth carrying: "Azure
 * returns the same `429` for both and separates them in one word of prose --
 * yet they have opposite fixes. A token refusal is answered by asking for less
 * in a turn; a call refusal by asking less often. Acting on the wrong one costs
 * a run and changes nothing."
 *
 * `unattributed` is not a gap in the record. It says the run *was* refused for
 * rate and the refusal was worded in a way the markers do not cover — which is
 * a finding about the markers, not about the deployment.
 */
export const RATE_LIMIT_KIND_LABELS: Record<RateLimitKind, string> = {
  token: '한 번의 호출이 예약한 토큰이 한도를 넘었습니다 (한 번에 더 적게 요청해야 합니다)',
  request: '호출이 너무 자주 도착했습니다 (더 드물게 호출해야 합니다)',
  unattributed: '한도 초과로 거절됐지만 어느 한도인지는 응답 문구에서 읽어내지 못했습니다',
}

/**
 * Which of the provider's two rate refusals this was, or `null`.
 *
 * `null` covers two different states and deliberately does not distinguish
 * them here: a failure that was not a rate refusal at all, and a rate refusal
 * from a run that predates the field. exp034 is the second — its five
 * `rate_limited` tasks were recorded before `rate_limit_kind` existed, through
 * a message-free error identity, so the sentence that would have settled it did
 * not survive. Neither state has a word to show, and inventing one for either
 * would be a claim the record does not support.
 */
export function readRateLimitKind(task: TaskResult): RateLimitKind | null {
  // `observability` is an index signature of `unknown`, so `codex` is whatever
  // the hub returned. Narrow it rather than assert it.
  const codex = task.observability?.codex
  if (typeof codex !== 'object' || codex === null) return null
  const kind = (codex as Record<string, unknown>).rate_limit_kind
  if (typeof kind !== 'string') return null
  return (RATE_LIMIT_KINDS as readonly string[]).includes(kind)
    ? (kind as RateLimitKind)
    : null
}

export interface FailureBreakdown {
  /** Tasks whose status is `error`. */
  failed: number
  /** Recorded categories, most frequent first, then alphabetically. */
  byCategory: { category: string; count: number }[]
  /** Failed tasks that recorded no category at all. */
  uncategorised: number
}

/**
 * What this run's failures were, counted by the word the run used.
 *
 * `null` when there are no task results to count — an absent array is a report
 * whose per-task detail was never loaded, and answering "0 failures" to that
 * would turn a missing record into a clean run. A loaded array with no failures
 * returns a breakdown of zero, which is a measurement.
 */
export function summariseFailures(
  tasks: TaskResult[] | undefined | null,
): FailureBreakdown | null {
  if (!Array.isArray(tasks) || tasks.length === 0) return null

  const counts = new Map<string, number>()
  let failed = 0
  let uncategorised = 0
  for (const task of tasks) {
    if (task?.status !== 'error') continue
    failed += 1
    const category = readFailureCategory(task)
    if (category === null) uncategorised += 1
    else counts.set(category, (counts.get(category) ?? 0) + 1)
  }

  const byCategory = [...counts.entries()]
    .map(([category, count]) => ({ category, count }))
    .sort((a, b) => b.count - a.count || a.category.localeCompare(b.category))

  return { failed, byCategory, uncategorised }
}
