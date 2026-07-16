import { useState, useEffect } from 'react'
import { ReportData, ReportIndexEntry, ReportsIndex, ExperimentEntry, SectorMatrix } from '../types/report'
import { applyReportIndexSnapshot } from '../lib/reportIndexSnapshot'

export const HF_BASE = 'https://huggingface.co/datasets/HyeonSang'

/**
 * Fetch all reports (lightweight index — no task_results) from the aggregated index.
 * Built at deploy time via aggregate-reports.mjs, which falls back to HuggingFace
 * when local report_data.json is absent.
 */
export function useReports(enabled = true) {
  const [reports, setReports] = useState<ReportIndexEntry[]>([])
  const [experiments, setExperiments] = useState<ExperimentEntry[]>([])
  const [sectorMatrix, setSectorMatrix] = useState<SectorMatrix>({})
  const [generated, setGenerated] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled) {
      setReports([])
      setExperiments([])
      setSectorMatrix({})
      setGenerated('')
      setError(null)
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setReports([])
    setExperiments([])
    setSectorMatrix({})
    setGenerated('')
    setLoading(true)
    setError(null)
    fetch(`${import.meta.env.BASE_URL}generated/reports-index.json?t=${Date.now()}`, { signal: controller.signal })
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
        if (err.name === 'AbortError') return
        setError(err.message)
        setLoading(false)
      })

    return () => controller.abort()
  }, [enabled])

  return { reports, experiments, sectorMatrix, generated, loading, error }
}

/**
 * Fetch a single full report (with task_results) from HuggingFace by short_id.
 * The index entry provides the experiment_id needed for the HF URL.
 */
export function useReport(shortId: string | undefined) {
  const { reports: indexReports, loading: indexLoading } = useReports()
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (indexLoading || !shortId) return

    const entry = indexReports.find((r) => r.short_id === shortId)
    if (!entry) {
      setError(`Report ${shortId} not found`)
      setLoading(false)
      return
    }

    setLoading(true)
    setError(null)

    const url = `${HF_BASE}/${entry.meta.experiment_id}/resolve/main/self_report.json`
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load report: ${res.status}`)
        return res.json() as Promise<ReportData>
      })
      .then((data) => {
        const reportWithIndexSnapshot = applyReportIndexSnapshot(data, entry, shortId)
        // Merge error messages from error_tasks into task_results
        if (reportWithIndexSnapshot.error_tasks?.length && reportWithIndexSnapshot.task_results) {
          const errorMap = new Map(reportWithIndexSnapshot.error_tasks.map((et) => [et.task_id, et.error]))
          for (const task of reportWithIndexSnapshot.task_results) {
            if (errorMap.has(task.task_id)) task.error = errorMap.get(task.task_id)
          }
        }
        setReport(reportWithIndexSnapshot)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [shortId, indexLoading, indexReports])

  return { report, loading, error }
}
