// Grade v1.0 schema types (matches tasks/grading_task/007-grade-schema.md)

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
}

export interface OpenAICompatSummary {
  avg_score_pct: number
  ci_pct: number
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
  judge_error_rate?: number
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
  total_judge_latency_sec?: number
}

export interface GradeSummaryV1 {
  total_tasks: number
  graded_tasks: number
  error_tasks: number
  openai_compat: OpenAICompatSummary
  wow: WowSummary
  cost?: GradeCostSummary
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
