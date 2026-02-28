import { useState, useEffect } from 'react'
import { ReportData, ReportsIndex, ExperimentEntry, SectorMatrix } from '../types/report'

/**
 * Fetch all reports from the aggregated index
 */
export function useReports() {
  const [reports, setReports] = useState<ReportData[]>([])
  const [experiments, setExperiments] = useState<ExperimentEntry[]>([])
  const [sectorMatrix, setSectorMatrix] = useState<SectorMatrix>({})
  const [generated, setGenerated] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}generated/reports-index.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch reports: ${res.status}`)
        return res.json() as Promise<ReportsIndex>
      })
      .then((data) => {
        setReports(data.reports)
        setExperiments(data.cross_experiment.experiments)
        setSectorMatrix(data.cross_experiment.sector_matrix ?? {})
        setGenerated(data._generated)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return { reports, experiments, sectorMatrix, generated, loading, error }
}

/**
 * Fetch a single report by short_id (e.g., "exp003")
 */
export function useReport(shortId: string | undefined) {
  const { reports, loading: indexLoading, error: indexError } = useReports()
  const [loading, setLoading] = useState(!shortId || indexLoading)
  const [error, setError] = useState<string | null>(indexError)

  const report = reports.find((r) => r.short_id === shortId) ?? null

  useEffect(() => {
    setLoading(indexLoading)
    setError(indexError)
    if (!shortId && reports.length === 0 && !indexLoading) {
      setError(`Report ${shortId} not found`)
    }
  }, [shortId, reports, indexLoading, indexError])

  return { report, loading, error }
}
