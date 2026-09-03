import { useState, useEffect } from 'react'
import type {
  GradeSummaryV1,
  TaskGradeV1,
  JudgeProvenance,
  RubricProvenance,
  GradePromptInfo,
  CalibrationCounts,
  SelectionOutcome,
  ScoreExclusion,
  ScoreExclusionLift,
  HeadlineSupport,
} from '../types/grade'
import type {
  CostLedgerReference,
  CostReceipt,
  CostSummaries,
} from '../types/cost'

export interface TaskGrade {
  task_id: string
  num_grades: number
  scores: number[]
  avg_score: number | null
  /**
   * The score this task actually got, when `avg_score` no longer says it.
   *
   * The aggregator snaps `avg_score` to a flat 1.0/0.0 once a task crosses the
   * `openai_compat` band boundaries (>= 99% / <= 1%) so the Status badges agree
   * with the published counts. That makes `avg_score` a band, not a score, on
   * those rows. `pct_exact` carries the unsnapped percentage and is present on
   * exactly the rows the snap moved — a task that genuinely scored 100 keeps
   * the key absent, so a row that was already right renders unchanged.
   */
  pct_exact?: number
  error: boolean
  error_messages: string[]
  /** Inference-time Self-QA score (0–10). Enriched from reports-index task_qa map. */
  qa_score?: number | null
  /**
   * Why this task landed where it did. Derived in the aggregator; absent for
   * grades written before the selector recorded its reasoning, in which case
   * the row renders exactly as it always has.
   */
  outcome?: SelectionOutcome
  outcome_detail?: string
  /** False when no deliverable reached a judge — the zero is plumbing, not a verdict. */
  reached_judge?: boolean
  /** What grading this task cost. Schema 1.4 only; absent means no record. */
  grading_cost?: CostReceipt | null
  /**
   * The second end of this task's score, when a judge-failed item took part of
   * the denominator with it. Absent when the denominator held, which is what
   * lets the row show one number where there is only one.
   */
  score_exclusion?: ScoreExclusion
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
  /**
   * What rubric the judge never read is worth to this run's average, or absent
   * when it read everything. Present only on item-level grades, which is every
   * real run on the board.
   */
  score_exclusion_lift?: ScoreExclusionLift | null
  /**
   * Whether the published headline matches the mean of its own rows. Read
   * alongside `score_exclusion_lift`, never subtracted from it: the two
   * measure different defects and move the average in opposite directions.
   */
  headline_support?: HeadlineSupport | null
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

  /** How the scored inference run proved its Azure AI routes. `legacy-missing`
   *  means the run predates `inference_provenance.json`, so the routes cannot
   *  be verified even though the corpus was graded complete — the dashboard
   *  badges it rather than publishing it silently. `null` for every grade
   *  produced before the field existed. See `src/lib/gradeProvenance.js`. */
  source_azure_ai_provenance_status?: string | null

  /** How much of the inference corpus this grading run covered, measured in
   *  aggregate-grades.mjs against the inference run's own published task count.
   *  `corpus_tasks` is null when the source experiment has no report, in which
   *  case coverage is unknown and `is_partial_corpus` stays false. Partial runs
   *  are preflights and are hidden from the default dashboard view. */
  coverage?: {
    grade_tasks: number
    corpus_tasks: number | null
    is_partial_corpus: boolean
  }

  // ── Item-level grade schema additions ──
  schema_version?: '1.0' | '1.1' | '1.2' | '1.3' | '1.4' | null
  judge?: JudgeProvenance
  rubric?: RubricProvenance
  prompt?: GradePromptInfo
  graded_at?: string
  summary_v1?: GradeSummaryV1
  tasks_v1?: TaskGradeV1[]
  /**
   * Run totals for the cost fields this grade recorded. Only 1.4 grade files
   * carry receipts, so this stays absent on every earlier run — which is what
   * the dashboard reads as "no record".
   */
  cost_summary?: CostSummaries
  /** Pointer to the grading run's per-call audit sidecar, when one exists. */
  cost_ledger?: CostLedgerReference
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
