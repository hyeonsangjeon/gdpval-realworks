/**
 * Report data types for GDPVal Dashboard v2
 * Sourced from batch-runner/results/(experiment_id)/report/report_data.json
 */

import type { CostLedgerReference, CostReceipt, CostSummaries } from './cost'

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
  /**
   * How long this task took. `null` on a task that failed before anything was
   * timed — never measured, not measured at zero. Both task tables already
   * render a falsy value as an em dash, so the honest value renders honestly.
   */
  latency_ms: number | null
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
  /**
   * What generating this deliverable cost. Absent on every run that predates
   * cost instrumentation — absent means "no record", never $0.
   */
  problem_solving_cost?: CostReceipt | null
  observability?: {
    execution_metrics?: TaskExecutionMetrics
    agentic_metrics?: TaskAgenticMetrics
    budget_metrics?: TaskBudgetMetrics
    substrate?: TaskSubstrateManifest
    [key: string]: unknown
  }
}

export interface TaskSubstrateManifest {
  schema_version: string
  sha256: string
  task_image: string
  task_image_id: string
  verifier_image: string
  verifier_image_id: string
  component_sha256: Record<string, string>
  sbom_sha256: string
  uid: number
  gid: number
  network: string
  ipc: string
  pid_namespace: string
  read_only_rootfs: boolean
  cap_drop: string[]
  no_new_privileges: boolean
  selected_transfer_bytes: number
  memory_bytes: number
  memory_swap_bytes: number
  cpus: number
  pids: number
  nofile: number
  apparmor_profile: string
  work_tmpfs: {
    size_bytes: number
    nr_inodes: number
    nosuid: boolean
    nodev: boolean
    noexec: boolean
  }
}

export interface TaskBudgetMetrics {
  schema_version: string
  model_api_calls: number
  input_tokens: number
  output_tokens: number
  cached_tokens: number
  conservative_cost_usd: number
  usage_complete: boolean
  time_to_valid_artifact_ms?: number | null
}

export interface TaskAgenticMetrics {
  schema_version: string
  ledger_cumulative?: boolean
  model_api_calls: number
  model_iterations: number
  tool_calls: number
  tool_errors: number
  tool_calls_by_name: Partial<Record<AgenticToolName, number>>
  model_time_ms: number
  tool_time_ms: number
  task_wall_time_ms: number
  time_to_valid_artifact_ms?: number | null
  finalize_attempts: number
  finalize_required_corrections: number
  capability_misses: number
  recovered_after_tool_error: boolean
  input_tokens: number
  output_tokens: number
  cached_tokens: number
  conservative_cost_usd: number
  usage_complete: boolean
  terminal_error_category: string | null
}

export type AgenticToolName =
  | 'inspect_workspace'
  | 'inspect_environment'
  | 'run_python'
  | 'run_ffmpeg'
  | 'inspect_artifacts'
  | 'finalize'

export interface AgenticMetricsSummary {
  schema_version: string
  measured_tasks: number
  total_tasks: number
  coverage_pct: number
  total_model_api_calls: number
  total_model_iterations: number
  total_tool_calls: number
  total_tool_errors: number
  tool_error_rate_pct: number
  tasks_with_tool_errors: number
  recovered_tasks: number
  recovery_rate_pct: number
  total_finalize_attempts: number
  total_finalize_required_corrections: number
  total_capability_misses: number
  p50_tool_time_ms: number | null
  p95_tool_time_ms: number | null
  total_input_tokens: number
  total_output_tokens: number
  total_cached_tokens: number
  usage_complete_tasks: number
  usage_coverage_pct: number
  conservative_cost_usd: number
  tool_calls_by_name: Record<AgenticToolName, number>
  terminal_error_categories: Record<string, number>
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
  /**
   * null when this sector produced no scored task at all — every one of its
   * tasks errored. That is not a sector that scored zero, and rendering it as
   * 0 says the model failed every rubric item here.
   */
  avg_qa_score: number | null
  /** null when nothing in this sector recorded a latency. Not a 0ms sector. */
  avg_latency_ms: number | null
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
  narrative_model?: string | null
  narrative_reasoning_effort?: string | null
  narrative_runtime_fingerprint?: string | null
}

export interface ReportSummary {
  total_tasks: number
  success_count: number
  /**
   * Kept non-null on purpose. Its 0 fallback fires only when total_tasks is 0,
   * which is printed right beside it, so a reader can see there was nothing to
   * divide. The six below are the ones a reader cannot check that way.
   */
  success_rate_pct: number
  error_count: number
  retried_count: number
  // null means never measured, not measured at zero. A run whose tasks all
  // errored has no average to report; step 6 writes null and every surface
  // renders an em dash rather than the bottom of the scale.
  avg_qa_score: number | null
  min_qa_score: number | null
  max_qa_score: number | null
  avg_latency_ms: number | null
  max_latency_ms: number | null
  total_latency_ms: number | null
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
  /**
   * File-required tasks the submission carries no row for, so their
   * deliverables were never looked at. Neither a success nor a failure: folding
   * them into either would make that count a count of something nobody checked.
   * Absent on reports written before step5 counted them, where it means no
   * record rather than none — so read it as a number only when it is one.
   */
  files_absent?: number | null
  absent_task_ids?: string[]
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
  agentic_metrics?: AgenticMetricsSummary
  /** task_id → Self-QA score (0–10). Enriched in scripts/aggregate-reports.mjs for Phase 1 calibration. */
  task_qa?: Record<string, number>
  /**
   * Run totals for whichever cost fields this run recorded. Absent, rather
   * than zeroed, on an uninstrumented run.
   */
  cost_summary?: CostSummaries
  /** Pointer to the published per-call audit sidecar, when one exists. */
  cost_ledger?: CostLedgerReference
}

export interface ExperimentEntry {
  short_id: string
  experiment_name: string
  model: string
  execution_mode: string
  condition: string
  success_rate_pct: number
  /** null when the run measured no score at all — see ReportSummary. */
  avg_qa_score: number | null
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
      /** null when the sector ran but scored nothing. */
      avg_qa_score: number | null
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
