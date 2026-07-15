/**
 * Report data types for GDPVal Dashboard v2
 * Sourced from batch-runner/results/(experiment_id)/report/report_data.json
 */

export interface TaskResult {
  task_id: string
  sector: string
  occupation: string
  status: 'success' | 'error'
  success?: boolean
  retried: boolean
  files_count: number
  qa_score: number | null
  qa_passed: boolean | null
  qa_issues: string[]
  qa_suggestion: string
  deliverable_summary?: string
  latency_ms: number
  error?: string
  grading_score?: number | null
  grading_feedback?: string | null
  // task context fields (for detail modal)
  instruction?: string
  reference_file_urls?: string[]
  deliverable_files?: string[]
  // v2 manifest fields (optional — v1 self_reports do not include these)
  prompt_classification?: PromptClassification | null
  policy_results?: Record<string, boolean> | null
  has_deliverable_files?: boolean | null
  observability?: {
    execution_metrics?: TaskExecutionMetrics
    [key: string]: unknown
  }
}

export interface TaskExecutionMetrics {
  schema_version: string
  task_wall_time_ms: number
  time_to_valid_artifact_ms: number | null
  model_time_ms: number
  tool_time_ms: number
  verification_time_ms: number
  dependency_time_ms: number
  self_qa_time_ms: number
  orchestration_time_ms: number
  execution_attempt_count: number
  sandbox_attempt_count: number
  tool_call_count: number
  self_qa_call_count: number
  job_run_count: number
  validated_artifact_count: number
}

export interface ExecutionMetricsSummary {
  schema_version: string
  measured_tasks: number
  total_tasks: number
  coverage_pct: number
  avg_task_wall_time_ms: number
  p50_task_wall_time_ms: number
  p95_task_wall_time_ms: number
  max_task_wall_time_ms: number
  avg_successful_task_wall_time_ms: number | null
  avg_failed_task_wall_time_ms: number | null
  measured_time_to_valid_artifact_tasks: number
  avg_time_to_valid_artifact_ms: number | null
  p50_time_to_valid_artifact_ms: number | null
  p95_time_to_valid_artifact_ms: number | null
  total_model_time_ms: number
  total_tool_time_ms: number
  total_verification_time_ms: number
  total_dependency_time_ms: number
  total_self_qa_time_ms: number
  total_orchestration_time_ms: number
  total_execution_attempts: number
  total_sandbox_attempts: number
  total_tool_calls: number
  total_self_qa_calls: number
  total_job_runs: number
}

export interface PromptClassification {
  requires_file: boolean
  explicit_exts: string[]
  inferred_exts: string[]
  confidence: 'explicit' | 'inferred' | 'ambiguous' | 'text_only'
}

export interface SectorBreakdown {
  sector: string
  total: number
  success: number
  success_rate_pct: number
  avg_qa_score: number
  avg_latency_ms: number
}

export interface ResumeRound {
  attempted: number
  recovered: number
  still_failed: number
}

export interface RecoveryStats {
  reflection: {
    tasks_with_reflection: number
    avg_attempts: number
    per_attempt_avg_score: Record<string, number>
    improved: number
    no_change: number
    degraded: number
  }
  resume_rounds: {
    rounds_used: number
    per_round: Record<string, ResumeRound>
  }
}

export interface ReportMeta {
  experiment_id: string
  experiment_name: string
  condition_name: string
  model: string
  execution_mode: string
  date: string
  duration: string
  report_scope: 'self_assessed_pre_grading' | 'graded'
}

export interface ReportSummary {
  total_tasks: number
  success_count: number
  success_rate_pct: number
  error_count: number
  retried_count: number
  avg_qa_score: number
  min_qa_score: number
  max_qa_score: number
  avg_latency_ms: number
  max_latency_ms: number
  total_latency_ms: number
  // v2 manifest fields (optional — v1 self_reports do not include these)
  active_policy?: string | null
  policy_counts?: Record<string, number> | null
  confidence_distribution?: Record<string, number> | null
}

export interface Narrative {
  overview: string
  quality_analysis: string
  failure_patterns: string
  recommendations: string
}

export interface FileGeneration {
  needs_files_total: number
  files_succeeded: number
  files_failed: number
  dummy_files_created: number
  dummy_task_ids: string[]
}

export interface ErrorTask {
  task_id: string
  sector: string
  occupation: string
  error: string
}

export interface ReportData {
  short_id: string
  meta: ReportMeta
  summary: ReportSummary
  sector_breakdown: SectorBreakdown[]
  task_results: TaskResult[]
  error_tasks: ErrorTask[]
  narrative: Narrative
  recovery_stats: RecoveryStats
  file_generation?: FileGeneration
  execution_metrics?: ExecutionMetricsSummary
  /** task_id → Self-QA score (0–10). Enriched in scripts/aggregate-reports.mjs for Phase 1 calibration. */
  task_qa?: Record<string, number>
}

export interface ExperimentEntry {
  short_id: string
  experiment_name: string
  model: string
  execution_mode: string
  condition: string
  success_rate_pct: number
  avg_qa_score: number
  total_tasks: number
  success_count: number
  retried_count?: number
  date: string
  duration: string
  report_scope: 'self_assessed_pre_grading' | 'graded'
}

export interface SectorMatrix {
  [sector: string]: {
    [short_id: string]: {
      success_rate_pct: number
      avg_qa_score: number
      success: number
      total: number
    }
  }
}

export interface CrossExperimentAnalysis {
  experiments: ExperimentEntry[]
  sector_matrix: SectorMatrix
}

/**
 * Lightweight index entry — task_results excluded (lazy-loaded from HuggingFace on detail page)
 */
export type ReportIndexEntry = Omit<ReportData, 'task_results'>

export interface ReportsIndex {
  reports: ReportIndexEntry[]
  cross_experiment: CrossExperimentAnalysis
  _generated: string
}
