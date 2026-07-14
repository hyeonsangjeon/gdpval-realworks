/** Canonical GDPVal benchmark size used by the official dashboard view. */
export const OFFICIAL_TASK_COUNT = 220

/** Curated diagnostic reports excluded from the default cross-run dashboard. */
export const HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS = new Set(['exp027'])

/** Match a short id or a derived full experiment/grade id. */
export function isHiddenDiagnosticExperimentId(value) {
  if (!value) return false
  return Array.from(HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS).some((shortId) => (
    value === shortId || value.startsWith(`${shortId}_`)
  ))
}

/** Smoke/test identifier shared by report and grade display filters. */
export function isSmokeExperimentId(value) {
  if (!value) return false
  return /(^|[_-])exp99\d/i.test(value) || /smoke/i.test(value)
}

/** Default dashboard exclusion rule for inference reports. */
export function isHiddenOfficialExperiment(experiment) {
  return (
    isSmokeExperimentId(experiment.short_id) ||
    isSmokeExperimentId(experiment.experiment_name) ||
    isHiddenDiagnosticExperimentId(experiment.short_id)
  )
}

/** Apply the dashboard's demo/debug scope without mutating source data. */
export function filterDashboardExperiments(experiments, options = {}) {
  const { debug = false, demoMode = false } = options
  let filtered = demoMode
    ? experiments.filter((experiment) => (
        experiment.report_scope === 'self_assessed_pre_grading'
      ))
    : [...experiments]
  if (!debug) {
    filtered = filtered.filter((experiment) => !isHiddenOfficialExperiment(experiment))
  }
  return filtered
}

/** Keep report narratives/errors aligned with the displayed experiments. */
export function filterDashboardReports(reports, visibleExperimentIds) {
  const visibleIds = new Set(visibleExperimentIds)
  return reports.filter((report) => visibleIds.has(report.short_id))
}

/** Build the aligned experiment/report scope consumed by Dashboard. */
export function getDashboardDisplayData(experiments, reports, options = {}) {
  const visibleExperiments = filterDashboardExperiments(experiments, options)
  const visibleReports = filterDashboardReports(
    reports,
    visibleExperiments.map((experiment) => experiment.short_id),
  )
  return { experiments: visibleExperiments, reports: visibleReports }
}
