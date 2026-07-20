import { useEffect, useState } from 'react'

export function useSuccessNote(enabled: boolean) {
  const [data, setData] = useState<unknown>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (!enabled) { setData(null); setLoading(false); setError(null); return }
    const controller = new AbortController()
    setData(null); setLoading(true); setError(null)
    fetch(`${import.meta.env.BASE_URL}generated/success-note.json?t=${Date.now()}`, { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error(`Failed to fetch success note: ${response.status}`); return response.json() as Promise<unknown> })
      .then((note) => { setData(note); setLoading(false) })
      .catch((fetchError) => { if (fetchError.name === 'AbortError') return; setError(fetchError.message); setLoading(false) })
    return () => controller.abort()
  }, [enabled])
  return { data, loading, error }
}
