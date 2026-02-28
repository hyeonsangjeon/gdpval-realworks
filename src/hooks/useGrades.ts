import { useState, useEffect } from 'react'

export interface TaskGrade {
  task_id: string
  num_grades: number
  scores: number[]
  avg_score: number | null
  error: boolean
  error_messages: string[]
}

export interface GradeSummary {
  total_tasks: number
  graded_tasks: number
  error_tasks: number
  avg_score_pct: number
  ci_pct: number | null
  perfect_score: number
  partial_score: number
  zero_score: number
  inconsistent_grades: number
}

export interface GradeResult {
  id: string
  is_dummy: boolean
  label: string
  model: string
  dataset_url: string | null
  experiment_type?: 'ab' | 'single'
  summary: GradeSummary
  tasks: TaskGrade[]
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
