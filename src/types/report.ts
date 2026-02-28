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

export interface ReportsIndex {
  reports: ReportData[]
  cross_experiment: CrossExperimentAnalysis
  _generated: string
}
