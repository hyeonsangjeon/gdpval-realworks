import { useState, useEffect } from 'react'

export interface PromptSource { source: string; content: string }

export interface PromptArchitecture {
  system: PromptSource & { experiment_system: string | null }
  user_prompt: {
    prefix: string | null
    body: string | null
    codegen_core: PromptSource
    suffix: PromptSource | null
  }
  qa_prompt: { enabled: boolean; min_score?: number; max_retries?: number; content: string | null }
  execution_config: {
    mode: string
    tokens: Record<string, number> | null
    timeout: number | null
    resume_max_rounds: number | null
    max_retries: number
    install_libreoffice: boolean
    metrics?: { enabled?: boolean }
  }
}

interface Entry { exp_id: string; short_id: string; description: string; prompt_architecture: PromptArchitecture }
interface Index { experiments: Entry[]; _generated: string }

let cached: Index | null = null

export function useExperimentPrompt(shortId: string | undefined) {
  const [prompt, setPrompt] = useState<PromptArchitecture | null>(null)
  const [description, setDescription] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!shortId) { setLoading(false); return }
    if (cached) {
      const entry = cached.experiments.find(e => e.short_id === shortId)
      setPrompt(entry?.prompt_architecture ?? null)
      setDescription(entry?.description ?? '')
      setLoading(false)
      return
    }
    fetch(`${import.meta.env.BASE_URL}generated/prompt-architecture.json?t=${Date.now()}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() as Promise<Index> })
      .then(data => {
        cached = data
        const entry = data.experiments.find(e => e.short_id === shortId)
        setPrompt(entry?.prompt_architecture ?? null)
        setDescription(entry?.description ?? '')
        setLoading(false)
      })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [shortId])

  return { prompt, description, loading, error }
}
