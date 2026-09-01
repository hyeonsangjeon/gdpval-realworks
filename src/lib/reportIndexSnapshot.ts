import type { ReportData, ReportIndexEntry } from '../types/report'

/**
 * The run-level cost fields the build validates.
 *
 * `aggregate-reports.mjs` puts each of these through the shared reader
 * (`projectCostSummary`, `projectCostLedgerReference`) before writing the
 * index, so the copy sitting on the index entry is the checked one.
 */
const VALIDATED_RUN_COST_KEYS = ['cost_summary', 'cost_ledger'] as const

/**
 * Merge the built index entry over the report fetched at read time.
 *
 * The entry wins on every key it carries — it is the copy the build validated.
 * `task_results` is the one exception, because the index does not carry it at
 * all: `aggregate-reports.mjs` strips the array and the detail page fetches it
 * live from HuggingFace.
 *
 * The spread on its own was not enough to say "run-level cost is the validated
 * copy". A spread only overwrites keys the entry actually has, and 23 of the 26
 * published reports carry no `cost_summary` in the index — so for those there
 * was nothing to overwrite with, and whatever HuggingFace returned went through
 * unchecked to `summaryTotalCell`. A total arriving as the string `"0.04"`
 * reached `formatCostUsd`, `.toFixed` was not a function, and the error
 * boundary in `App.tsx` replaced the whole experiment page with "Something went
 * wrong".
 *
 * Today no published report is actually in that divergent state: none of the 26
 * has a local `report_data.json`, so the build fetches `self_report.json` from
 * the same URL the page does, and index and payload agree on the presence of a
 * summary for all 26. The rule below is what keeps that true rather than
 * something the corpus happens to be. It only bites where the build's picture
 * and HuggingFace's disagree — a stale committed result directory, or a payload
 * republished after the deploy — and disagreement is exactly the case where the
 * unvalidated number is the one not to show.
 *
 * So these keys come from the entry or they do not come at all. A report with
 * no validated cost summary shows no cost summary, which is what "nothing
 * checked this" should look like — not a number nobody stands behind.
 */
export function applyReportIndexSnapshot(
  report: ReportData,
  entry: ReportIndexEntry,
  shortId: string,
): ReportData {
  const merged: ReportData = {
    ...report,
    ...entry,
    short_id: shortId,
    task_results: report.task_results,
  }
  for (const key of VALIDATED_RUN_COST_KEYS) {
    if (!(key in entry)) delete merged[key]
  }
  return merged
}
