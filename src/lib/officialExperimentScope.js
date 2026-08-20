/** Canonical GDPVal benchmark size used by the official dashboard view. */
export const OFFICIAL_TASK_COUNT = 220

/** Curated diagnostic reports excluded from the default cross-run dashboard. */
export const HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS = new Set([
  'exp027',
  'exp028', // Agentic Sandbox canary
  'exp029', // Hardened current-sandbox baseline
  'exp030', // Agentic Sandbox treatment
])

/** Match a short id or a derived full experiment/grade id. */
export function isHiddenDiagnosticExperimentId(value) {
  if (!value) return false
  return (
    Array.from(HIDDEN_DIAGNOSTIC_EXPERIMENT_IDS).some((shortId) => (
      value === shortId || value.startsWith(`${shortId}_`)
    ))
  )
}

/** Smoke/test identifier shared by report and grade display filters. */
export function isSmokeExperimentId(value) {
  if (!value) return false
  return /(^|[_-])exp99\d/i.test(value) || /smoke/i.test(value)
}

/**
 * A grading run that covered only part of the inference corpus it graded —
 * a preflight or cohort trial, not a result. `coverage` is computed in
 * aggregate-grades.mjs against the inference run's own published task count.
 *
 * Unknown coverage is never treated as partial: a grade whose experiment has
 * no report yields `corpus_tasks: null`, and staying visible on ignorance is
 * the safer failure. A small experiment graded end to end (17 of 17) is
 * complete, so this rule cannot mistake "small" for "unfinished".
 */
export function isPartialCorpusGrade(grade) {
  return grade?.coverage?.is_partial_corpus === true
}

// ── curated baselines ───────────────────────────────────────────────────────
// The two sets below are hand-picked, not patterns. Every other rule in this
// file decides from measured properties; which finished run represents the
// benchmark is a publication decision and has to be written down by a person.

/**
 * Grade ids published as official baselines — badged, and never hidden by any
 * rule. Add an id here when a run is promoted.
 */
export const OFFICIAL_GRADE_IDS = new Set([
  // gpt-5.6-sol judge, 220 tasks — current primary result
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_6-sol__regrade_exp003_v2_sol_max_score_excluded__cfg_71c325eee0e48c13__rubric_11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_1c967673eb8081a6__v2.2',
  // gpt-5.4 judge, 220 tasks — retained A/B comparator for the run above
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4__rubric_v2_tools',
])

/**
 * Full-corpus runs retired in favour of a newer judge. Their numbers are
 * sound — this is not the partial-corpus rule — but a results page that keeps
 * every generation of judge becomes a changelog, and readers compare whatever
 * is on screen. The dashboard therefore shows the current result plus exactly
 * one older run as an A/B comparator, and retires the rest.
 *
 * `gpt-5.4-mini` is the one retired: against a `gpt-5.6-sol` judge it varies
 * in both judge size and judge version at once, so a gap measured across it
 * cannot be attributed to either. The full-size `gpt-5.4` run is the
 * like-for-like comparator and stays.
 *
 * Retirement is display-only. The grade JSON is untouched, the card is one
 * `?debug=1` away, and its own page still resolves by direct URL.
 */
export const SUPERSEDED_GRADE_IDS = new Set([
  // gpt-5.4-mini judge, 220 tasks — superseded; see above for why this one
  'exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini',
])

/** Curated official baseline: badged, and exempt from every hide rule. */
export function isOfficialGradeId(id) {
  return typeof id === 'string' && OFFICIAL_GRADE_IDS.has(id)
}

/** Curated retirement: a complete run kept out of the default comparison set. */
export function isSupersededGradeId(id) {
  return typeof id === 'string' && SUPERSEDED_GRADE_IDS.has(id)
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
