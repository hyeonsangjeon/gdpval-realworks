import { useState, useEffect } from 'react'
import type {
  GradeSummaryV1,
  TaskGradeV1,
  JudgeProvenance,
  RubricProvenance,
  GradePromptInfo,
  CalibrationCounts,
} from '../types/grade'

export interface TaskGrade {
  task_id: string
  num_grades: number
  scores: number[]
  avg_score: number | null
  error: boolean
  error_messages: string[]
  /** Inference-time Self-QA score (0–10). Enriched from reports-index task_qa map. */
  qa_score?: number | null
}

export interface GradeSummary {
  total_tasks: number
  graded_tasks: number
  error_tasks: number
  avg_score_pct: number | null
  ci_pct: number | null
  perfect_score: number
  partial_score: number
  zero_score: number
  inconsistent_grades: number
  /** Mean |Rubric% − SelfQA%| across matched tasks. null when no samples. */
  calibration_mae?: number | null
  /** Distribution of calibration categories. null when no samples. */
  calibration_counts?: CalibrationCounts | null
}

export interface GradeResult {
  id: string
  /** Stable experiment identifier (e.g. "exp998_smoke_baseline_sample").
   *  Promoted to a 1st-class field by dashboard_cleanup PR #1 so
   *  ScopeBadge / ExperimentDetail can match grade rows by exact equality
   *  rather than startsWith heuristics. */
  experiment_id: string
  /** Grade lifecycle state, derived in aggregate-grades.mjs.
   *  - `graded_v1`   — v1.0 schema (rubric-based LLM-judge result)
   *  - `legacy_dummy`— dummy_gpt5_baseline.json demo data
   *  - `no_grade`    — present for completeness; aggregator currently never
   *                    emits this (only files in data/grades/ are read).
   */
  grade_status: 'graded_v1' | 'legacy_dummy' | 'no_grade'
  is_dummy: boolean
  label: string
  /**
   * @deprecated since dashboard_cleanup PR #1.
   * Use `inference_model` instead. Retained for legacy callers; equals
   * `inference_model || ''` and never silently falls back to the judge model.
   */
  model: string
  /** Model that produced the inference output. `null` when missing/empty —
   *  the UI renders "unknown" in that case (no silent judge fallback). */
  inference_model: string | null
  /** LLM-judge model that scored the outputs. `null` for legacy dummies. */
  judge_model: string | null
  dataset_url: string | null
  experiment_type?: 'ab' | 'single'
  summary: GradeSummary
  tasks: TaskGrade[]

  // ── Item-level grade schema additions ──
  schema_version?: '1.0' | '1.1' | '1.2' | '1.3' | null
  judge?: JudgeProvenance
  rubric?: RubricProvenance
  prompt?: GradePromptInfo
  graded_at?: string
  summary_v1?: GradeSummaryV1
  tasks_v1?: TaskGradeV1[]
}

export function useGrades() {
  const [grades, setGrades] = useState<GradeResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}generated/grades-index.json?t=${Date.now()}`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch grades: ${res.status}`)
        return res.json() as Promise<GradeResult[]>
      })
      .then((data) => {
        setGrades(data)
        setLoading(false)
      })
      .catch(() => {
        // grades-index.json이 없으면 조용히 빈 배열
        setGrades([])
        setError(null)
        setLoading(false)
      })
  }, [])

  return { grades, loading, error }
}
