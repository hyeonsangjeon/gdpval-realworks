/**
 * Per-task cost receipts, schema `cost-receipt-v1`.
 *
 * These types are the read side of one fixed contract with three producers:
 * `batch-runner/core/cost_projection.py` (Python), `scripts/cost-receipt.mjs`
 * (the aggregator's mirror of it), and this file. Every amount here is derived
 * from recorded usage against a pinned price table. None of it is an invoice.
 *
 * The distinction the whole shape exists to protect: an absent receipt is
 * `null`, never `0`. A run that predates cost instrumentation has no record of
 * what it cost, which is a different statement from having cost nothing.
 */

export const COST_RECEIPT_SCHEMA_VERSION = 'cost-receipt-v1'
export const COST_CURRENCY = 'USD'
export const ESTIMATE_BASIS = 'usage_estimate_not_azure_invoice'

/**
 * - `complete`    — every component priced; the amount is the amount.
 * - `partial`     — something priced, something missing; the amount is a floor.
 * - `unavailable` — nothing could be priced, and `missing_reasons` says why.
 * - `not_run`     — this work never happened, so there is nothing to price.
 */
export type CostStatus = 'complete' | 'partial' | 'unavailable' | 'not_run'

/** The two cost fields a task can carry. */
export type CostField = 'problem_solving_cost' | 'grading_cost'

/**
 * The stage a charge belongs to. `preprocessing`, `generation` and `self_qa`
 * flow into `problem_solving_cost`; `grading` and `perception` flow into
 * `grading_cost`. The mapping itself lives once, at the producer.
 */
export type CostStage =
  | 'preprocessing'
  | 'generation'
  | 'self_qa'
  | 'grading'
  | 'perception'

/**
 * The closed vocabulary for `components[].name`: the five stages plus `retry`,
 * which is what any stage's line is called when it was not a first attempt.
 *
 * There is deliberately no `runtime` member. Runtime fees are not model calls
 * and arrive as `runtime_cost_usd`; a component line carrying them would be
 * counted twice by any reader that sums the lines and then adds the runtime
 * total.
 */
export type CostComponentName = CostStage | 'retry'

/** Token/second counters, keyed by producer-defined snake_case slugs. */
export type CostUsage = Record<string, number>

export interface CostComponent {
  /** What the row is called on screen. See `componentLabel()`. */
  name: CostComponentName | string
  /** Which stage the charge belongs to — a retry keeps its stage. */
  stage: CostStage | string
  /** `none` on a first attempt; otherwise why it had to be repeated. */
  retry_kind: string
  status: CostStatus
  /** What was priced on this line. `null` unless something was measured. */
  known_cost_usd: number | null
  model_calls: number | null
  usage: CostUsage | null
  /** Reason codes, never prose. Empty unless something went unpriced. */
  missing_reasons: string[]
}

export interface CostReceipt {
  schema_version: typeof COST_RECEIPT_SCHEMA_VERSION
  currency: typeof COST_CURRENCY
  status: CostStatus
  /** The full amount. Non-null only when nothing is missing. */
  estimated_cost_usd: number | null
  /** What was actually priced. A floor when `status` is `partial`. */
  known_cost_usd: number | null
  model_cost_usd: number | null
  runtime_cost_usd: number | null
  model_calls: number | null
  usage: CostUsage | null
  components: CostComponent[]
  price_table_sha256: string | null
  /** Reason codes, never prose. Empty unless something went unpriced. */
  missing_reasons: string[]
}

export interface CostComponentTotal {
  name: string
  tasks: number
  known_cost_usd: number
  complete_tasks: number
  model_calls: number
  status: 'complete' | 'partial'
}

/**
 * One cost field aggregated across a run. `null` in place of this object is
 * the run-level "no record" — it is never replaced by a zeroed summary.
 */
export interface CostSummary {
  schema_version: typeof COST_RECEIPT_SCHEMA_VERSION
  currency: typeof COST_CURRENCY
  estimate_basis: typeof ESTIMATE_BASIS
  status: CostStatus
  total_tasks: number
  /** Tasks carrying any receipt at all. */
  receipt_tasks: number
  /** Tasks whose receipt carried an amount. */
  measured_tasks: number
  coverage_pct: number
  complete_tasks: number
  partial_tasks: number
  unavailable_tasks: number
  not_run_tasks: number
  known_cost_usd: number
  /** Non-null only when every receipt is complete; otherwise the total is a floor. */
  estimated_cost_usd: number | null
  avg_cost_usd: number | null
  median_cost_usd: number | null
  p95_cost_usd: number | null
  max_cost_usd: number | null
  successful_deliverables: number | null
  cost_per_successful_deliverable_usd: number | null
  /** Failed work costs money. Reported beside the total, never netted out of it. */
  failed_task_count: number
  failed_task_cost_usd: number
  components: CostComponentTotal[]
  price_table_sha256: string | null
  missing_reasons: string[]
}

export type CostSummaries = Partial<Record<CostField, CostSummary>>

/** Pointer to the published per-call audit sidecar. */
export interface CostLedgerReference {
  path: string
  sha256: string
}
