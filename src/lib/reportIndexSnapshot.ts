import type { ReportData, ReportIndexEntry } from '../types/report'

export function applyReportIndexSnapshot(
  report: ReportData,
  entry: ReportIndexEntry,
  shortId: string,
): ReportData {
  return {
    ...report,
    short_id: shortId,
    meta: entry.meta,
    summary: entry.summary,
  }
}