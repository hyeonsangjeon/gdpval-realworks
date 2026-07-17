import type { ReportData, ReportIndexEntry } from '../types/report'

export function applyReportIndexSnapshot(
  report: ReportData,
  entry: ReportIndexEntry,
  shortId: string,
): ReportData {
  return {
    ...report,
    ...entry,
    short_id: shortId,
    task_results: report.task_results,
  }
}