import type { ReportIndexEntry } from '../types/report'

export const PROMPT_COMPLEXITY_REPORT_IDS = ['exp003', 'exp004', 'exp005'] as const

export type PromptComplexityReportId = (typeof PROMPT_COMPLEXITY_REPORT_IDS)[number]

interface PromptComplexityPresentation {
  mode: string
  mobileMode: string
  steps: string[]
  color: string
}

interface PromptComplexityDefinition extends PromptComplexityPresentation {
  expectedCondition: string
  expectedExecutionMode: string
}

const presentationById: Record<PromptComplexityReportId, PromptComplexityDefinition> = {
  exp003: {
    expectedCondition: 'Baseline',
    expectedExecutionMode: 'subprocess',
    mode: 'BASIC OUTPUT CONTRACT',
    mobileMode: '기본 계약',
    steps: ['CREATE FILE', 'INSPECT INPUT', 'TEXT SUMMARY'],
    color: '#2563eb',
  },
  exp004: {
    expectedCondition: 'Elicit',
    expectedExecutionMode: 'subprocess',
    mode: 'FIVE MANDATORY STEPS',
    mobileMode: '5단계 검사',
    steps: ['1 · RENDER TO PNG', '2 · DISPLAY PNG', '3 · PROGRAM CHECK', '4 · MATCH REQUEST', '5 · FINAL FILE CHECK'],
    color: '#b45309',
  },
  exp005: {
    expectedCondition: 'Elicit v2',
    expectedExecutionMode: 'subprocess',
    mode: 'SAME FIVE STEPS · NEW STEP 2',
    mobileMode: 'STEP 2 교체',
    steps: ['1 · RENDER TO PNG', '2 · PILLOW CHECK', '3 · PROGRAM CHECK', '4 · MATCH REQUEST', '5 · FINAL FILE CHECK'],
    color: '#be123c',
  },
}

export interface PromptComplexityBenchmarkRow extends PromptComplexityPresentation {
  shortId: PromptComplexityReportId
  condition: string
  executionMode: string
  successCount: number
  totalTasks: number
  successRatePct: number
  avgQaScore: number
}

export type PromptComplexityBenchmarkSelection =
  | {
      status: 'ready'
      rows: PromptComplexityBenchmarkRow[]
      completionDeltaPctPoints: number
    }
  | {
      status: 'missing'
      missingIds: PromptComplexityReportId[]
    }
  | {
      status: 'invalid'
      invalidIds: PromptComplexityReportId[]
    }

const roundToOneDecimal = (value: number) => Math.round(value * 10) / 10

/**
 * A report that has been through {@link isValidBenchmarkReport} — in particular
 * one whose `avg_qa_score` was actually measured.
 *
 * `summary.avg_qa_score` is `number | null` in general, because a run whose
 * tasks all errored has no average to report. The rows below read it as a plain
 * number, and this type is what makes that safe rather than lucky: such a run
 * fails the guard, lands in `invalidIds`, and never reaches the row builder.
 */
type ValidatedBenchmarkReport = ReportIndexEntry & {
  summary: ReportIndexEntry['summary'] & { avg_qa_score: number }
}

function isValidBenchmarkReport(
  shortId: PromptComplexityReportId,
  report: ReportIndexEntry,
): report is ValidatedBenchmarkReport {
  const { meta, summary } = report
  if (!meta || !summary) return false
  if (typeof meta.condition_name !== 'string' || typeof meta.execution_mode !== 'string') return false

  const presentation = presentationById[shortId]
  if (meta.condition_name !== presentation.expectedCondition) return false
  if (meta.execution_mode !== presentation.expectedExecutionMode) return false

  const { total_tasks: totalTasks, success_count: successCount, success_rate_pct: successRate, avg_qa_score: avgQaScore } = summary
  if (!Number.isInteger(totalTasks) || totalTasks <= 0) return false
  if (!Number.isInteger(successCount) || successCount < 0 || successCount > totalTasks) return false
  if (!Number.isFinite(successRate) || successRate < 0 || successRate > 100) return false
  // Number.isFinite(null) is already false, so an unmeasured score has always
  // been rejected here. Spelling the null out keeps that deliberate.
  if (avgQaScore == null || !Number.isFinite(avgQaScore) || avgQaScore < 0 || avgQaScore > 10) return false

  return Math.abs(successRate - roundToOneDecimal((successCount / totalTasks) * 100)) < 0.05
}

export function selectPromptComplexityBenchmark(
  reports: ReportIndexEntry[],
): PromptComplexityBenchmarkSelection {
  const matchingReports = new Map(
    PROMPT_COMPLEXITY_REPORT_IDS.map((shortId) => [
      shortId,
      reports.filter((report) => report.short_id === shortId),
    ]),
  )
  const missingIds = PROMPT_COMPLEXITY_REPORT_IDS.filter((shortId) => matchingReports.get(shortId)?.length === 0)

  if (missingIds.length > 0) return { status: 'missing', missingIds }

  // Kept as it validates, so the row builder below reads the same object the
  // guard just approved instead of looking it up again and losing what the
  // guard proved about it.
  const validated = new Map<PromptComplexityReportId, ValidatedBenchmarkReport>()
  const invalidIds = PROMPT_COMPLEXITY_REPORT_IDS.filter((shortId) => {
    const matches = matchingReports.get(shortId) ?? []
    if (matches.length !== 1) return true
    const report = matches[0]
    if (!isValidBenchmarkReport(shortId, report)) return true
    validated.set(shortId, report)
    return false
  })

  if (invalidIds.length > 0) return { status: 'invalid', invalidIds }

  const rows = PROMPT_COMPLEXITY_REPORT_IDS.map((shortId) => {
    const report = validated.get(shortId)!
    return {
      shortId,
      condition: report.meta.condition_name,
      executionMode: report.meta.execution_mode,
      successCount: report.summary.success_count,
      totalTasks: report.summary.total_tasks,
      successRatePct: report.summary.success_rate_pct,
      avgQaScore: report.summary.avg_qa_score,
      mode: presentationById[shortId].mode,
      mobileMode: presentationById[shortId].mobileMode,
      steps: presentationById[shortId].steps,
      color: presentationById[shortId].color,
    }
  })

  const baseline = rows[0]
  const headless = rows[rows.length - 1]
  const completionDeltaPctPoints = roundToOneDecimal(
    ((headless.successCount / headless.totalTasks) - (baseline.successCount / baseline.totalTasks)) * 100,
  )

  return { status: 'ready', rows, completionDeltaPctPoints }
}