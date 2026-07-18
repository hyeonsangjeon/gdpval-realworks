export const INTEGRITY_REPORT_IDS = ['exp013', 'exp025'] as const

export type IntegrityReportId = (typeof INTEGRITY_REPORT_IDS)[number]

const expectedReportById: Record<IntegrityReportId, { experimentId: string; date: string }> = {
  exp013: { experimentId: 'exp013_GPT54_reasoning_high', date: '2026-03-27' },
  exp025: { experimentId: 'exp025_GPT54_high_postfix', date: '2026-05-20' },
}
const EXPECTED_COMPARED_FIELDS = ['data.filter', 'condition_a', 'execution']
const EXPECTED_MISSING_EXECUTION_IDENTITIES = [
  'execution_git_sha',
  'input_dataset_revision',
  'azure_model_revision',
  'runner_environment_identity',
]

export interface IntegrityNoteData {
  comparison: {
    before: { short_id: 'exp013'; experiment_id: string; report_date: string }
    after: { short_id: 'exp025'; experiment_id: string; report_date: string }
    expected_condition: string
    expected_model: 'gpt-5.4'
    expected_mode: 'subprocess'
    expected_task_count: 220
    expected_report_scope: 'self_assessed_pre_grading'
    checked_in_config_equal: true
    compared_fields: string[]
  }
  history: {
    parent_commit: string
    core_fix_commit: string
    followup_commit: string
    merge_commit: string
    applied_at: string
    fixes: Record<string, unknown>
  }
  interpretation: {
    causal_attribution: false
    observed_claim: string
    measurement_claim: string
    missing_execution_identities: string[]
    report_snapshot: string
  }
  sources: {
    integrity: string
    before_config: string
    after_config: string
  }
  _generated: string
}

export interface IntegrityBenchmarkRow {
  shortId: IntegrityReportId
  experimentId: string
  date: string
  condition: string
  model: string
  executionMode: string
  totalTasks: number
  successCount: number
  successRatePct: number
  errorCount: number
  retriedCount: number
  avgQaScore: number
  residualCount: number
}

export type IntegrityNoteSelection =
  | {
      status: 'ready'
      before: IntegrityBenchmarkRow
      after: IntegrityBenchmarkRow
      rows: IntegrityBenchmarkRow[]
      observedGapPctPoints: number
      successDifference: number
      history: IntegrityNoteData['history']
      interpretation: IntegrityNoteData['interpretation']
      sources: IntegrityNoteData['sources']
      generated: string
    }
  | { status: 'missing'; missingIds: IntegrityReportId[] }
  | { status: 'invalid'; invalidSources: string[] }

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isString = (value: unknown): value is string => typeof value === 'string'
const isSha = (value: unknown): value is string => isString(value) && /^[0-9a-f]{40}$/.test(value)
const isNonNegativeInteger = (value: unknown): value is number => Number.isInteger(value) && Number(value) >= 0
const isFiniteInRange = (value: unknown, min: number, max: number): value is number => typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
const roundToOneDecimal = (value: number) => Math.round(value * 10) / 10
const isValidIso = (value: unknown): value is string => {
  if (!isString(value)) return false
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) && new Date(timestamp).toISOString() === value
}
const isValidDate = (value: unknown): value is string => {
  if (!isString(value) || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const timestamp = `${value}T00:00:00.000Z`
  const milliseconds = Date.parse(timestamp)
  return Number.isFinite(milliseconds) && new Date(milliseconds).toISOString() === timestamp
}

function parseReport(shortId: IntegrityReportId, value: unknown): IntegrityBenchmarkRow | null {
  if (!isRecord(value) || !isRecord(value.meta) || !isRecord(value.summary)) return null
  const expected = expectedReportById[shortId]
  const meta = value.meta
  const summary = value.summary
  if (value.short_id !== shortId || meta.experiment_id !== expected.experimentId || meta.date !== expected.date) return null
  if (meta.condition_name !== 'GPT-5.4 reasoning=high + gpt-audio-1.5 preprocessor') return null
  if (meta.model !== 'gpt-5.4' || meta.execution_mode !== 'subprocess' || meta.report_scope !== 'self_assessed_pre_grading') return null
  if (summary.total_tasks !== 220) return null
  if (!isNonNegativeInteger(summary.success_count) || summary.success_count > 220) return null
  if (!isNonNegativeInteger(summary.error_count) || summary.success_count + summary.error_count > 220) return null
  if (!isNonNegativeInteger(summary.retried_count) || summary.retried_count > 220) return null
  if (!isFiniteInRange(summary.success_rate_pct, 0, 100)) return null
  if (Math.abs(summary.success_rate_pct - roundToOneDecimal((summary.success_count / 220) * 100)) >= 0.05) return null
  if (!isFiniteInRange(summary.avg_qa_score, 0, 10)) return null
  return {
    shortId,
    experimentId: expected.experimentId,
    date: expected.date,
    condition: meta.condition_name,
    model: meta.model,
    executionMode: meta.execution_mode,
    totalTasks: 220,
    successCount: summary.success_count,
    successRatePct: summary.success_rate_pct,
    errorCount: summary.error_count,
    retriedCount: summary.retried_count,
    avgQaScore: summary.avg_qa_score,
    residualCount: 220 - summary.success_count - summary.error_count,
  }
}

function parseIntegrityNote(value: unknown): IntegrityNoteData | null {
  if (!isRecord(value) || !isRecord(value.comparison) || !isRecord(value.history) || !isRecord(value.interpretation) || !isRecord(value.sources)) return null
  const comparison = value.comparison
  const history = value.history
  const interpretation = value.interpretation
  if (!isRecord(comparison.before) || !isRecord(comparison.after)) return null
  if (comparison.before.short_id !== 'exp013' || comparison.after.short_id !== 'exp025') return null
  if (comparison.before.experiment_id !== expectedReportById.exp013.experimentId || comparison.after.experiment_id !== expectedReportById.exp025.experimentId) return null
  if (comparison.before.report_date !== expectedReportById.exp013.date || comparison.after.report_date !== expectedReportById.exp025.date) return null
  if (comparison.expected_condition !== 'GPT-5.4 reasoning=high + gpt-audio-1.5 preprocessor') return null
  if (comparison.expected_model !== 'gpt-5.4' || comparison.expected_mode !== 'subprocess' || comparison.expected_task_count !== 220 || comparison.expected_report_scope !== 'self_assessed_pre_grading') return null
  if (comparison.checked_in_config_equal !== true || !Array.isArray(comparison.compared_fields)) return null
  if (JSON.stringify(comparison.compared_fields) !== JSON.stringify(EXPECTED_COMPARED_FIELDS)) return null
  if (!isSha(history.parent_commit) || !isSha(history.core_fix_commit) || !isSha(history.followup_commit) || !isSha(history.merge_commit)) return null
  if (history.parent_commit !== '2b41c06fd0647c900520009f30cb26d3a5bd772e' || history.core_fix_commit !== '4e0e43d23fe2d829ec8e7469e1fc0ffd9aab75ff') return null
  if (history.followup_commit !== '645758e0ebfdf5985748f31756de45f1b619ee1d' || history.merge_commit !== '4ba399f9f9528ab355b2c8fc6d703aa14b310414') return null
  if (history.applied_at !== '2026-05-17' || !isValidDate(history.applied_at) || !isRecord(history.fixes)) return null
  const fixes = history.fixes
  if (!isRecord(fixes.available_files) || !isRecord(fixes.qa_failed) || !isRecord(fixes.anthropic_content)) return null
  if (fixes.available_files.path !== 'batch-runner/core/subprocess_runner.py') return null
  if (fixes.available_files.before !== 'header_changed_in_memory_after_script_write' || fixes.available_files.after !== 'header_persisted_before_subprocess_execution' || fixes.available_files.causal_direction !== 'unknown') return null
  if (fixes.qa_failed.path !== 'batch-runner/step2_run_inference.py') return null
  if (fixes.qa_failed.before !== 'determined_qa_failure_could_remain_success' || fixes.qa_failed.after !== 'determined_qa_failure_recorded_as_qa_failed' || fixes.qa_failed.undetermined_remains_success !== true) return null
  if (fixes.anthropic_content.applicable_to_comparison !== false || fixes.anthropic_content.reason !== 'both_runs_use_azure') return null
  if (interpretation.causal_attribution !== false || !Array.isArray(interpretation.missing_execution_identities)) return null
  if (JSON.stringify(interpretation.missing_execution_identities) !== JSON.stringify(EXPECTED_MISSING_EXECUTION_IDENTITIES)) return null
  if (!isString(interpretation.observed_claim) || !isString(interpretation.measurement_claim) || !isString(interpretation.report_snapshot)) return null
  if (value.sources.integrity !== 'data/notes/integrity-incidents.yaml') return null
  if (value.sources.before_config !== 'batch-runner/experiments/exp013_GPT54_reasoning_high.yaml' || value.sources.after_config !== 'batch-runner/experiments/exp025_GPT54_high_postfix.yaml') return null
  if (!isValidIso(value._generated)) return null
  return value as unknown as IntegrityNoteData
}

export function selectIntegrityNoteBenchmark(reports: unknown, integrityNote: unknown): IntegrityNoteSelection {
  if (!Array.isArray(reports)) return { status: 'invalid', invalidSources: ['reports-index.json'] }
  const matches = new Map(INTEGRITY_REPORT_IDS.map((shortId) => [shortId, reports.filter((report) => isRecord(report) && report.short_id === shortId)]))
  const missingIds = INTEGRITY_REPORT_IDS.filter((shortId) => matches.get(shortId)?.length === 0)
  if (missingIds.length > 0) return { status: 'missing', missingIds }

  const invalidSources: string[] = []
  const rows = INTEGRITY_REPORT_IDS.map((shortId) => {
    const candidates = matches.get(shortId) ?? []
    if (candidates.length !== 1) {
      invalidSources.push(shortId)
      return null
    }
    const row = parseReport(shortId, candidates[0])
    if (!row) invalidSources.push(shortId)
    return row
  })
  const source = parseIntegrityNote(integrityNote)
  if (!source) invalidSources.push('integrity-note.json')
  if (invalidSources.length > 0) return { status: 'invalid', invalidSources }

  const [before, after] = rows as IntegrityBenchmarkRow[]
  return {
    status: 'ready',
    before,
    after,
    rows: [before, after],
    observedGapPctPoints: roundToOneDecimal(((after.successCount / 220) - (before.successCount / 220)) * 100),
    successDifference: after.successCount - before.successCount,
    history: source!.history,
    interpretation: source!.interpretation,
    sources: source!.sources,
    generated: source!._generated,
  }
}
