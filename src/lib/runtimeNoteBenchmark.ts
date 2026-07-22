export const RUNTIME_REPORT_IDS = ['exp008', 'exp010', 'exp025', 'exp026'] as const

export type RuntimeReportId = (typeof RUNTIME_REPORT_IDS)[number]

const expectedReportById: Record<RuntimeReportId, { experimentId: string; condition: string; mode: string }> = {
  exp008: {
    experimentId: 'exp008_GPT52Chat_resume2_elicit_v2',
    condition: 'Elicit v2 16k + resume_rounds 2',
    mode: 'subprocess',
  },
  exp010: {
    experimentId: 'exp010_GPT52Chat_resume2_elicit_v2',
    condition: 'Elicit v2 16k + code_interpreter',
    mode: 'code_interpreter',
  },
  exp025: {
    experimentId: 'exp025_GPT54_high_postfix',
    condition: 'GPT-5.4 reasoning=high + gpt-audio-1.5 preprocessor',
    mode: 'subprocess',
  },
  exp026: {
    experimentId: 'exp026_sandbox_skills_multimodal',
    condition: 'GPT-5.4 low + sandbox + skills + audio/video perception',
    mode: 'sandbox',
  },
}

export interface RuntimeNoteData {
  current_policy: {
    scope: 'condition_a'
    watchdog_minutes: number
    step_timeout_minutes: number
    job_timeout_minutes: number
    step_timeout_headroom_minutes: number
  }
  incident: {
    experiment_id: string
    condition: 'condition_a'
    action_run_id: string
    approx_minute: number
    event: string
    started_at: string
    completed_at: string
    workflow_commit: string
    policy: {
      scope: 'condition_a'
      step_timeout_minutes: number
      job_timeout_minutes: number
      resume_watchdog_enabled: false
    }
    source_record_commit: string
    fix: {
      commit: string
      applied_at: string
      step_timeout_before_minutes: number
      step_timeout_after_minutes: number
      resume_watchdog_enabled: true
    }
  }
  sources: {
    workflow: string
    incidents: string
  }
  _generated: string
}

export interface RuntimeRecoveryRound {
  round: number
  attempted: number
  recovered: number
  stillFailed: number
}

export interface RuntimeBenchmarkRow {
  shortId: RuntimeReportId
  condition: string
  executionMode: string
  duration: string
  totalTasks: number
  successCount: number
  errorCount: number
  retriedCount: number
  avgQaScore: number
  recoveryRounds: RuntimeRecoveryRound[]
}

export type RuntimeNoteBenchmarkSelection =
  | {
      status: 'ready'
      rows: RuntimeBenchmarkRow[]
      exp025: RuntimeBenchmarkRow
      exp026: RuntimeBenchmarkRow
      currentPolicy: RuntimeNoteData['current_policy']
      incident: RuntimeNoteData['incident']
      sources: RuntimeNoteData['sources']
      generated: string
    }
  | { status: 'missing'; missingIds: RuntimeReportId[] }
  | { status: 'invalid'; invalidSources: string[] }

const isNonNegativeInteger = (value: unknown): value is number => Number.isInteger(value) && Number(value) >= 0
const isPositiveInteger = (value: unknown): value is number => Number.isInteger(value) && Number(value) > 0
const isFiniteInRange = (value: unknown, min: number, max: number): value is number => (
  typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
)

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === 'object' && value !== null && !Array.isArray(value)
)
const isString = (value: unknown): value is string => typeof value === 'string'
const isSha = (value: unknown): value is string => isString(value) && /^[0-9a-f]{40}$/.test(value)
const parseUtcSecond = (value: unknown) => {
  if (!isString(value) || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return null
  const milliseconds = Date.parse(value)
  if (!Number.isFinite(milliseconds) || new Date(milliseconds).toISOString() !== value.replace('Z', '.000Z')) return null
  return milliseconds
}
const isCalendarDate = (value: unknown): value is string => {
  if (!isString(value) || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const timestamp = `${value}T00:00:00.000Z`
  const milliseconds = Date.parse(timestamp)
  return Number.isFinite(milliseconds) && new Date(milliseconds).toISOString() === timestamp
}
const roundToOneDecimal = (value: number) => Math.round(value * 10) / 10

function parseRecoveryRounds(report: Record<string, unknown>, retriedCount: number): RuntimeRecoveryRound[] | null {
  const recoveryStats = report.recovery_stats
  if (!isRecord(recoveryStats) || !isRecord(recoveryStats.resume_rounds)) return null
  const resume = recoveryStats.resume_rounds
  if (resume.rounds_used !== 2 || !isRecord(resume.per_round)) return null
  const perRound = resume.per_round
  if (Object.keys(perRound).sort().join(',') !== '1,2') return null

  const rounds = ['1', '2'].map((key) => {
    const stats = perRound[key]
    if (!isRecord(stats)) return null
    if (!isNonNegativeInteger(stats.attempted) || !isNonNegativeInteger(stats.recovered) || !isNonNegativeInteger(stats.still_failed)) return null
    if (stats.recovered + stats.still_failed !== stats.attempted) return null
    return {
      round: Number(key),
      attempted: stats.attempted,
      recovered: stats.recovered,
      stillFailed: stats.still_failed,
    }
  })
  if (rounds.some((round) => round === null)) return null

  const validRounds = rounds as RuntimeRecoveryRound[]
  const totalAttempted = validRounds.reduce((total, round) => total + round.attempted, 0)
  if (totalAttempted !== retriedCount) return null
  return validRounds
}

function parseRuntimeReport(shortId: RuntimeReportId, value: unknown): RuntimeBenchmarkRow | null {
  if (!isRecord(value) || !isRecord(value.meta) || !isRecord(value.summary)) return null
  const meta = value.meta
  const summary = value.summary
  const expected = expectedReportById[shortId]
  if (value.short_id !== shortId) return null
  if (meta.experiment_id !== expected.experimentId || meta.condition_name !== expected.condition || meta.execution_mode !== expected.mode) return null
  if (meta.report_scope !== 'self_assessed_pre_grading') return null
  if (!isString(meta.duration) || !/^\d+m \d+s$/.test(meta.duration)) return null
  if (summary.total_tasks !== 220) return null
  if (!isNonNegativeInteger(summary.success_count) || summary.success_count > summary.total_tasks) return null
  if (!isFiniteInRange(summary.success_rate_pct, 0, 100)) return null
  if (Math.abs(summary.success_rate_pct - roundToOneDecimal((summary.success_count / summary.total_tasks) * 100)) >= 0.05) return null
  if (!isNonNegativeInteger(summary.error_count) || summary.error_count > summary.total_tasks) return null
  if (summary.success_count + summary.error_count > summary.total_tasks) return null
  if (!isNonNegativeInteger(summary.retried_count) || summary.retried_count > summary.total_tasks) return null
  if (!isFiniteInRange(summary.avg_qa_score, 0, 10)) return null

  const recoveryRounds = parseRecoveryRounds(value, summary.retried_count)
  if (!recoveryRounds) return null

  return {
    shortId,
    condition: expected.condition,
    executionMode: expected.mode,
    duration: meta.duration,
    totalTasks: summary.total_tasks,
    successCount: summary.success_count,
    errorCount: summary.error_count,
    retriedCount: summary.retried_count,
    avgQaScore: summary.avg_qa_score,
    recoveryRounds,
  }
}

function parseRuntimeNote(value: unknown): RuntimeNoteData | null {
  if (!isRecord(value) || !isRecord(value.current_policy) || !isRecord(value.incident) || !isRecord(value.sources)) return null
  const currentPolicy = value.current_policy
  const incident = value.incident
  const sources = value.sources
  if (!isRecord(incident.policy) || !isRecord(incident.fix)) return null
  const incidentPolicy = incident.policy
  const fix = incident.fix
  const watchdogMinutes = currentPolicy.watchdog_minutes
  const stepTimeoutMinutes = currentPolicy.step_timeout_minutes
  const jobTimeoutMinutes = currentPolicy.job_timeout_minutes
  const stepTimeoutHeadroomMinutes = currentPolicy.step_timeout_headroom_minutes

  if (currentPolicy.scope !== 'condition_a') return null
  if (!isPositiveInteger(watchdogMinutes) || !isPositiveInteger(stepTimeoutMinutes) || !isPositiveInteger(jobTimeoutMinutes) || !isPositiveInteger(stepTimeoutHeadroomMinutes)) return null
  if (!(watchdogMinutes < stepTimeoutMinutes && stepTimeoutMinutes < jobTimeoutMinutes)) return null
  if (stepTimeoutHeadroomMinutes !== stepTimeoutMinutes - watchdogMinutes) return null
  if (incident.experiment_id !== 'exp025' || incident.condition !== 'condition_a' || incident.action_run_id !== '26018603400' || incident.event !== 'SIGKILL' || incident.approx_minute !== 330) return null
  const startedAt = parseUtcSecond(incident.started_at)
  const completedAt = parseUtcSecond(incident.completed_at)
  if (startedAt === null || completedAt === null || startedAt >= completedAt) return null
  if (incident.workflow_commit !== '36b0e5bed5e9be2622e505f68d3746eec1b6cc12') return null
  if (incidentPolicy.scope !== 'condition_a' || incidentPolicy.step_timeout_minutes !== 330 || incidentPolicy.job_timeout_minutes !== 360 || incidentPolicy.resume_watchdog_enabled !== false) return null
  if (incident.approx_minute !== incidentPolicy.step_timeout_minutes) return null
  if (incident.source_record_commit !== '6e0001503ad4f3760c007dc1981d3bdc53dd785d') return null
  if (fix.commit !== '62471a4a682b2f2439bba81a7eb24335a8f4931f' || fix.applied_at !== '2026-05-20' || !isCalendarDate(fix.applied_at)) return null
  if (fix.step_timeout_before_minutes !== incidentPolicy.step_timeout_minutes || fix.step_timeout_after_minutes !== stepTimeoutMinutes || fix.resume_watchdog_enabled !== true) return null
  if (incidentPolicy.job_timeout_minutes !== jobTimeoutMinutes) return null
  if (!isString(value._generated)) return null
  const generatedAt = Date.parse(value._generated)
  if (!Number.isFinite(generatedAt) || new Date(generatedAt).toISOString() !== value._generated) return null
  if (sources.workflow !== '.github/workflows/batch-run.yml' || sources.incidents !== 'data/notes/runtime-incidents.yaml') return null
  if (!isSha(incident.workflow_commit) || !isSha(incident.source_record_commit) || !isSha(fix.commit)) return null
  return value as unknown as RuntimeNoteData
}

export function selectRuntimeNoteBenchmark(
  reports: unknown,
  runtimeNote: unknown,
): RuntimeNoteBenchmarkSelection {
  if (!Array.isArray(reports)) return { status: 'invalid', invalidSources: ['reports-index.json'] }
  const matchesById = new Map(
    RUNTIME_REPORT_IDS.map((shortId) => [shortId, reports.filter((report) => isRecord(report) && report.short_id === shortId)]),
  )
  const missingIds = RUNTIME_REPORT_IDS.filter((shortId) => matchesById.get(shortId)?.length === 0)
  if (missingIds.length > 0) return { status: 'missing', missingIds }

  const invalidSources: string[] = []
  const rows = RUNTIME_REPORT_IDS.map((shortId) => {
    const matches = matchesById.get(shortId) ?? []
    if (matches.length !== 1) {
      invalidSources.push(shortId)
      return null
    }
    const row = parseRuntimeReport(shortId, matches[0])
    if (!row) invalidSources.push(shortId)
    return row
  })

  const validRuntimeNote = parseRuntimeNote(runtimeNote)
  if (!validRuntimeNote) invalidSources.push('runtime-note.json')
  if (invalidSources.length > 0) return { status: 'invalid', invalidSources }

  const validRows = rows as RuntimeBenchmarkRow[]
  return {
    status: 'ready',
    rows: validRows,
    exp025: validRows[2],
    exp026: validRows[3],
    currentPolicy: validRuntimeNote!.current_policy,
    incident: validRuntimeNote!.incident,
    sources: validRuntimeNote!.sources,
    generated: validRuntimeNote!._generated,
  }
}
