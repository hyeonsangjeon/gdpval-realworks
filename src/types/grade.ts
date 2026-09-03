// Grade v1.0 schema types (matches tasks/grading_task/007-grade-schema.md)

import type { CostReceipt, CostSummary } from './cost'
// The route-composition shape is declared beside the rule that reads it, in a
// module kept free of imports so `scripts/__tests__/route-exposure.test.mjs`
// can execute that rule directly. Type-only, so nothing crosses at runtime.
import type { RouteComposition } from '../components/wow/routeExposure'

export type { RouteComposition }

export type Verdict = 'pass' | 'partial' | 'fail' | 'judge_error'
export type DecidedBy = 'precheck' | 'judge'

export interface ItemGrade {
  rubric_item_id: string
  criterion: string
  max_score: number
  awarded_score: number
  verdict: Verdict
  decided_by: DecidedBy
  required: boolean | null
  evidence: string
  judge_confidence: number | null
  judge_latency_ms: number | null
  precheck_pattern_id: string | null
  judge_raw_response?: string | null
}

/**
 * What a task's judge-failed items did to its denominator.
 *
 * A rubric item the judge could not read leaves the numerator and the
 * denominator together, so the task is scored out of less than its rubric is
 * worth and the published percentage rises. Both ends travel so the screen can
 * show both: `pct_published` assumes an unread item would have scored like the
 * read ones, `pct_full_denominator` assumes it would have scored nothing, and
 * the truth is somewhere between.
 *
 * Absent on any task whose denominator held, which is most of them. Absent is
 * not zero — it means there is one number here, not two.
 */
export interface ScoreExclusion {
  /** How many rubric items the judge failed to read. */
  items: number
  /** Points of rubric those items were worth. */
  excluded_max: number
  /** Points of rubric that were actually read and scored. */
  read_max: number
  /** The percentage the run publishes, out of what was read. */
  pct_published: number
  /** The same points out of the whole rubric, unread items included. */
  pct_full_denominator: number
}

/**
 * The published headline measured against the mean of the rows beneath it.
 *
 * `supported` is three-valued on purpose: `null` means the comparison could not
 * be made — no scored rows, or no numeric headline — which is not the same
 * claim as `true`. Four published runs on the board disagree with their own
 * rows, because a task the grader could not grade at all stays in the
 * denominator as a zero. That gap is a different defect from the one
 * `ScoreExclusionLift` measures and moves the average the other way, so the two
 * are reported separately and never subtracted across.
 */
export interface HeadlineSupport {
  /** Mean of the scored task percentages. null when there were none. */
  avg_score_pct_from_rows: number | null
  /** Published headline minus that mean. null when either side is missing. */
  delta_pct: number | null
  /** Scored rows the mean was taken over. */
  rows_counted: number
  /** Whether the two agree to rounding, or null when they could not be compared. */
  supported: boolean | null
}

/**
 * The same measurement as `ScoreExclusion`, taken over a whole run.
 *
 * Both percentages are means over one row set — the scored rows — so their
 * difference is the excluded items and nothing else. Neither is the published
 * headline: on four of the runs on the board the published figure disagrees
 * with its own rows for an unrelated reason, and pairing it with a
 * full-denominator mean would report the two defects added together.
 * `HeadlineSupport` carries that other gap.
 */
export interface ScoreExclusionLift {
  /** Scored tasks whose denominator moved. Never 0 — the whole object is null then. */
  tasks_affected: number
  /** Scored tasks the two averages are taken over. */
  tasks_counted: number
  /** Rubric items the judge failed to read, across those tasks. */
  excluded_items: number
  /** Points of rubric those items were worth. */
  excluded_max: number
  /** Mean of the published task percentages, each out of what was read. */
  avg_score_pct_from_rows: number
  /** Mean of the same tasks scored out of their whole rubrics. */
  avg_score_pct_full_denominator: number
  /** The first minus the second: what unread rubric adds to this run's average. */
  lift_pct: number
  /**
   * Whether the payload's own run-level figure agrees with this one, or null
   * when the payload made no claim. Null is not the same statement as true.
   */
  payload_agrees: boolean | null
}

export interface TaskGradeV1 {
  task_id: string
  sector: string
  occupation: string
  items: ItemGrade[]
  total_awarded: number
  total_max: number
  pct: number
  critical_fail: boolean
  gold_referenced?: boolean
  judge_call_count?: number
  precheck_count?: number
  judge_total_latency_ms?: number
  judge_input_tokens?: number
  judge_output_tokens?: number
  error: string | null
  graded_at?: string
  /** Inference-time Self-QA score (0–10). Phase 1: enriched from reports-index task_qa map. */
  qa_score?: number | null
  /** Raw selector verdict: 'ok' | 'wrong_format_primary' | 'no_generated_candidate' | 'selection_error'. */
  selection_status?: string | null
  /** Human-readable reason the selector gave up, straight from the grader. */
  selection_error?: string | null
  /** Which cascade branch decided this task, e.g. 'set_diff_single'. */
  selection_rule?: string
  /** Full selector payload: primary targets, support artifacts, excluded references. */
  selected_deliverables?: DeliverableSelection | null
  reference_files_excluded?: string[]
  /** ── Derived by scripts/selection-outcome.mjs, not present in the grade JSON ── */
  outcome?: SelectionOutcome
  outcome_detail?: string
  /** False when no deliverable ever reached a judge — the zero is plumbing, not a verdict. */
  reached_judge?: boolean
  /** Extensions the task demanded, parsed from the selector's message. */
  required_formats?: string[]
  format_demand?: 'unproducible_media' | 'producible' | null
  candidate_files?: string[]
  /**
   * What grading this task cost. Read from schema 1.4 grade files only;
   * absent on 1.0–1.3, where it means "no record" rather than free.
   */
  grading_cost?: CostReceipt | null
  /**
   * What this task's judge-failed items did to its denominator. Projected by
   * the aggregator from `items`, so it reaches grades published long before
   * the grader learned to report it. Absent when the denominator held.
   */
  score_exclusion?: ScoreExclusion
}

export interface DeliverableTarget {
  target_id?: string | null
  paths: string[]
  kind?: string
  role?: string
  evidence_rule?: string
}

export interface DeliverableSelection {
  selection_status: string
  task_id?: string
  task_class?: string
  primary_targets?: DeliverableTarget[]
  support_artifacts?: string[]
  reference_files_excluded?: string[]
  selection_rule?: string
  selection_error?: string | null
}

/**
 * Where a task landed, and whether a judge was ever in a position to say so.
 *
 * `content_zero` is the only zero that is a verdict on the work. The rest are
 * recorded as zero because nothing gradeable reached the judge, which is a
 * different finding and belongs in a different bucket on screen.
 */
export type SelectionOutcome =
  | 'scored'
  | 'content_zero'
  | 'inference_failed'
  | 'format_unmet'
  | 'no_deliverable'
  | 'not_selected'
  | 'grading_error'
  | 'unclassified'

export interface ZeroReason {
  outcome: SelectionOutcome
  label: string
  count: number
  reached_judge: boolean
}

export interface SelectionSummary {
  /** False when this grade carries no selector metadata; the UI must stay hidden. */
  covered: boolean
  covered_tasks: number
  total_tasks: number
  outcomes: Record<SelectionOutcome, number>
  zero_reasons: ZeroReason[]
  /** Zeros a judge handed down after reading a deliverable. */
  judged_zero: number
  /** Zeros recorded because no deliverable reached a judge. */
  unjudged_zero: number
}

export interface CalibrationCounts {
  /** |Rubric% − SelfQA%| ≤ 10 */
  calibrated: number
  /** Rubric% − SelfQA% < -10 (model overestimates its own work) */
  overconfident: number
  /** Rubric% − SelfQA% > 10 (model underestimates its own work) */
  underconfident: number
  /** Task has no qa_score (excluding errors) */
  unmatched: number
}

export interface OpenAICompatSummary {
  avg_score_pct: number | null
  ci_pct: number | null
  perfect_count: number
  zero_count: number
  partial_count: number
  inconsistent_count: number
}

/**
 * The denominators the `wow` rates were divided by.
 *
 * Every rate above is a fraction whose denominator used to be thrown away, and
 * the fallback for an empty one is `0.0` — the same value as "every single item
 * failed". `step8_grade._wow_item_counts` publishes the counts so the two can
 * be told apart. Optional because grades written before it existed carry none,
 * and an absent count is not a zero one.
 */
export interface WowItemCounts {
  rubric_items?: number
  critical_items?: number
  precheck_items?: number
  judge_items?: number
}

export interface SectorWowMetric {
  task_count: number
  avg_pct: number
  critical_item_pass_rate: number
  precheck_pass_rate: number
  judge_pass_rate: number
  item_counts?: WowItemCounts
}

export interface RubricCategoryMetric {
  items: number
  pass_rate: number
}

export interface ScoreDensityBucket {
  bucket: string
  count: number
}

export interface RubricSeverityPoint {
  weight: number
  n_items: number
  pass_rate: number
}

export interface WowSummary {
  rubric_item_coverage_avg: number
  /**
   * Pass rate over rubric items whose `|max_score|` reaches the grader's
   * magnitude threshold — *not* over items the rubric marks required. The
   * rubric's own `required` field is null on all 10,453 items, so the grader
   * substitutes score magnitude for necessity. Read it as a diagnostic and
   * never as a verdict; see `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`.
   * The key keeps its published name so past payloads stay readable.
   */
  critical_item_pass_rate: number
  precheck_pass_rate: number
  judge_pass_rate: number
  judge_error_rate: number
  item_counts?: WowItemCounts
  by_sector?: Record<string, SectorWowMetric>
  by_rubric_category?: Record<string, RubricCategoryMetric>
  score_density_histogram?: ScoreDensityBucket[]
  rubric_severity_curve?: RubricSeverityPoint[]
}

export interface GradeCostSummary {
  total_judge_calls?: number
  total_input_tokens?: number
  total_output_tokens?: number
  estimated_cost_usd?: number | null
  pricing_complete?: boolean
  unpriced_models?: string[]
  total_judge_latency_sec?: number
}

export interface CurrentGradeCostSummary extends GradeCostSummary {
  estimated_cost_usd: null
  pricing_complete: false
  unpriced_models: string[]
}

export interface GradeSummaryV1 {
  total_tasks: number
  graded_tasks: number
  error_tasks: number
  openai_compat: OpenAICompatSummary
  wow: WowSummary
  cost?: GradeCostSummary
  /** Mean |Rubric% − SelfQA%| across matched tasks. null when no samples. */
  calibration_mae?: number | null
  /** Distribution of calibration categories. null when no samples. */
  calibration_counts?: CalibrationCounts | null
  /**
   * Why the zeros are zeros. Derived by scripts/selection-outcome.mjs from the
   * selector metadata the grader already writes; it never restates a published
   * count. Absent on grade files written before the selector recorded its
   * reasoning — check `covered` before rendering.
   */
  selection?: SelectionSummary
  /**
   * Grading cost across the run, derived in scripts/aggregate-grades.mjs from
   * the per-task receipts so the headline always adds up to the rows. Absent
   * unless the grade file is schema 1.4 and recorded receipts.
   */
  grading_cost?: CostSummary
  /**
   * Which sub-judge decided how much of the run, recomputed in
   * scripts/aggregate-grades.mjs from each item's `routing_modality` by the
   * same rule as `step8_grade._routing_stats`.
   *
   * Not to be confused with `JudgeProvenance.routing` below, which is a
   * tier-routing block naming models on hybrid configs — a different thing at
   * a different path.
   *
   * Present on every item-level payload, including as `recorded: false`. That
   * value is the answer to "did the audio sub-judge touch this number", not
   * the absence of one: eleven of the eighteen item-level grades published
   * today predate routing and carry `routing_modality: null` on every item,
   * and reading those as `audio: 0` would turn never-asked into
   * asked-and-found-none.
   */
  route_composition?: RouteComposition | null
}

export interface JudgeTierConfig {
  model?: string
  deployment?: string
  reasoning_effort?: string
  max_output_tokens?: number
}

/**
 * Tier-routing block emitted by hybrid grading configs (see
 * the archived v1 validation configs). Present only when a historical grade
 * JSON was produced by a tiered judge config; absent for current single-model
 * runs such as `default_v2_sol_max`.
 */
export interface JudgeRouting {
  tier_pro?: JudgeTierConfig
  tier_standard?: JudgeTierConfig
  tier_mini?: JudgeTierConfig
}

export interface JudgeProvenance {
  provider: string
  api: string
  model: string
  deployment?: string
  api_version?: string
  reasoning_effort: string
  temperature: number
  seed?: number
  /** Grading config name (e.g. 'default_v2_sol_max'). */
  config_name?: string
  /** Stable 16-char hash of the config used as part of the cache key. */
  config_hash?: string
  /** Tier-routing block, present only on hybrid runs. */
  routing?: JudgeRouting
}

export interface RubricProvenance {
  source: string
  repo_id: string
  revision: string
  commit_sha: string
  short_sha: string
}

export interface GradePromptInfo {
  template: string
  version: string
}
