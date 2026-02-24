import { useState, useEffect } from 'react'

export interface Experiment {
  id: string
  name: string
  model: string
  tasks: number
  condition_a: {
    name: string
    prompt: string
    win_rate: number
  }
  condition_b: {
    name: string
    prompt: string
    win_rate: number
  }
  delta: number
  changed_variable?: string
  industry_breakdown: Record<string, number>
  analysis: string
}

interface ExperimentsData {
  experiments: Experiment[]
  _generated?: string
}

export function useExperiments() {
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}generated/experiments-index.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch experiments: ${res.status}`)
        return res.json() as Promise<ExperimentsData>
      })
      .then((data) => {
        setExperiments(data.experiments)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return { experiments, loading, error }
}
