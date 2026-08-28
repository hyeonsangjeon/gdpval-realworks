// Grade v1.0 schema types (matches tasks/grading_task/007-grade-schema.md)

import type { CostReceipt, CostSummary } from './cost'

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

export interface SectorWowMetric {
  task_count: number
  avg_pct: number
  critical_item_pass_rate: number
  precheck_pass_rate: number
  judge_pass_rate: number
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
  critical_item_pass_rate: number
  precheck_pass_rate: number
  judge_pass_rate: number
  judge_error_rate: number
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
