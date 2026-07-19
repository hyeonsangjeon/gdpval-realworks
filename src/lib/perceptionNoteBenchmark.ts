export const PERCEPTION_REPORT_IDS = ['exp011', 'exp012', 'exp026'] as const
export type PerceptionReportId = (typeof PERCEPTION_REPORT_IDS)[number]

const expected = {
  exp011: { experimentId: 'exp011_GPT52Chat_domain_packages', date: '2026-03-05', condition: 'Elicit v2 16k + domain packages', model: 'gpt-5.2-chat', mode: 'subprocess', total: 220, scope: 'full_220', paths: [] },
  exp012: { experimentId: 'exp012_GPT52Chat_audio_multiagent', date: '2026-03-08', condition: 'Multi-Agent: task-aware audio analysis + code', model: 'gpt-5.2-chat', mode: 'subprocess', total: 25, scope: 'information_25', paths: ['audio'] },
  exp026: { experimentId: 'exp026_sandbox_skills_multimodal', date: '2026-07-10', condition: 'GPT-5.4 low + sandbox + skills + audio/video perception', model: 'gpt-5.4', mode: 'sandbox', total: 220, scope: 'full_220', paths: ['audio', 'video'] },
} as const
const expectedHistory = {
  audio_preprocessor_commit: 'dfc29e43598a3feda54ae5127912b7b0ec3299bd',
  sandbox_multimodal_commit: 'eaa2789081ba7b81901ba977006f9bfd6534a0c1',
  docker_always_commit: '6ac8a830a325eb95aec5fb89f38a5e9312ea1b2a',
  audio_applied_at: '2026-03-09',
  sandbox_applied_at: '2026-07-07',
  docker_always_applied_at: '2026-07-09',
} as const
const expectedMissingIdentities = ['execution_git_sha', 'input_dataset_revision', 'azure_model_revision', 'runner_environment_identity']
const expectedCaveats = [
  'exp011_is_full_benchmark_while_exp012_is_information_only',
  'exp012_audio_analyzer_is_triggered_only_for_tasks_with_audio_files',
  'exp012_yaml_comment_says_17_audio_heavy_tasks_but_report_has_25_information_tasks',
  'exp012_yaml_created_at_differs_from_report_date',
  'exp026_changes_model_reasoning_runner_skills_audio_and_video_together',
  'report_snapshot_is_resolved_at_deployment_not_execution',
]
const expectedSources = {
  perception: 'data/notes/perception-pipeline.yaml',
  exp011_config: 'batch-runner/experiments/exp011_GPT52Chat_domain_packages.yaml',
  exp012_config: 'batch-runner/experiments/exp012_GPT52Chat_audio_multiagent.yaml',
  exp026_config: 'batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml',
}

export interface PerceptionRow {
  shortId: PerceptionReportId
  experimentId: string
  date: string
  condition: string
  model: string
  mode: string
  totalTasks: number
  successCount: number
  errorCount: number
  retriedCount: number
  avgQaScore: number
  information: { total: 25; success: number; successRatePct: number; avgQaScore: number; avgLatencyMs: number }
  perceptionPaths: string[]
}

export interface PerceptionPreprocessor {
  type: 'audio_analyzer' | 'video_analyzer'
  deployment: string
  trigger: 'has_audio_files' | 'has_video_files'
  inject_as: 'prompt_prefix'
  include_task_instruction: true
  frames_per_video: number | null
  max_total_frames: number | null
}

export interface PerceptionArchitecture {
  exp011: { preprocessors: []; package_notice: true }
  exp012: { preprocessors: [PerceptionPreprocessor]; config_created_at: '2026-03-09'; header_declared_audio_heavy_tasks: 17 }
  exp026: { preprocessors: [PerceptionPreprocessor, PerceptionPreprocessor]; use_docker: 'always'; max_skills: 5; skill_catalog: string[] }
}

export interface PerceptionInterpretation {
  causal_attribution: false
  observed_claim: string
  architecture_claim: string
  invocation_count_known: false
  external_quality_known: false
  missing_execution_identities: string[]
  caveats: string[]
}

export type PerceptionSelection =
  | { status: 'ready'; rows: PerceptionRow[]; exp011: PerceptionRow; exp012: PerceptionRow; exp026: PerceptionRow; architecture: PerceptionArchitecture; history: Record<string, string>; interpretation: PerceptionInterpretation; sources: Record<string, string> }
  | { status: 'missing'; missingIds: PerceptionReportId[] }
  | { status: 'invalid'; invalidSources: string[] }

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isString = (value: unknown): value is string => typeof value === 'string'
const isInt = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0
const isFiniteRange = (value: unknown, min: number, max: number): value is number => typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
const roundOne = (value: number) => Math.round(value * 10) / 10
const deepEqual = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right)
const isIsoTimestamp = (value: unknown): value is string => {
  if (!isString(value)) return false
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value
}

function parseRow(shortId: PerceptionReportId, value: unknown, paths: unknown): PerceptionRow | null {
  if (!isRecord(value) || !isRecord(value.meta) || !isRecord(value.summary) || !Array.isArray(value.sector_breakdown) || !Array.isArray(paths)) return null
  const contract = expected[shortId]
  const meta = value.meta
  const summary = value.summary
  const condition = meta.condition_name
  const model = meta.model
  const totalTasks = summary.total_tasks
  const successCount = summary.success_count
  const errorCount = summary.error_count
  const retriedCount = summary.retried_count
  const avgQaScore = summary.avg_qa_score
  if (value.short_id !== shortId || meta.experiment_id !== contract.experimentId || meta.date !== contract.date || meta.execution_mode !== contract.mode) return null
  if (meta.report_scope !== 'self_assessed_pre_grading' || totalTasks !== contract.total) return null
  if (!isString(condition) || !isString(model) || condition !== contract.condition || model !== contract.model) return null
  if (!isInt(totalTasks) || !isInt(successCount) || !isInt(errorCount) || !isInt(retriedCount)) return null
  if (successCount + errorCount > totalTasks || retriedCount > totalTasks) return null
  if (!isFiniteRange(summary.success_rate_pct, 0, 100) || Math.abs(summary.success_rate_pct - roundOne((successCount / totalTasks) * 100)) >= 0.05) return null
  if (!isFiniteRange(avgQaScore, 0, 10)) return null
  const informationRows = value.sector_breakdown.filter((entry) => isRecord(entry) && entry.sector === 'Information')
  if (informationRows.length !== 1) return null
  const sector = informationRows[0]
  if (!isRecord(sector) || sector.total !== 25 || !isInt(sector.success) || sector.success > 25) return null
  if (!isFiniteRange(sector.success_rate_pct, 0, 100) || Math.abs(sector.success_rate_pct - roundOne((sector.success / 25) * 100)) >= 0.05) return null
  if (!isFiniteRange(sector.avg_qa_score, 0, 10) || !isInt(sector.avg_latency_ms)) return null
  if (shortId === 'exp012' && (totalTasks !== sector.total || successCount !== sector.success)) return null
  return {
    shortId,
    experimentId: contract.experimentId,
    date: contract.date,
    condition,
    model,
    mode: contract.mode,
    totalTasks,
    successCount,
    errorCount,
    retriedCount,
    avgQaScore,
    information: { total: 25, success: sector.success, successRatePct: sector.success_rate_pct, avgQaScore: sector.avg_qa_score, avgLatencyMs: sector.avg_latency_ms },
    perceptionPaths: paths.map(String),
  }
}

function parseSource(value: unknown) {
  if (!isRecord(value) || !isRecord(value.comparison) || !isRecord(value.architecture) || !isRecord(value.history) || !isRecord(value.interpretation) || !isRecord(value.sources)) return null
  const comparison = value.comparison
  const architecture = value.architecture
  const history = value.history
  const interpretation = value.interpretation
  const sources = value.sources
  for (const shortId of PERCEPTION_REPORT_IDS) {
    if (!isRecord(comparison[shortId])) return null
    const contract = comparison[shortId]
    if (contract.short_id !== shortId || contract.experiment_id !== expected[shortId].experimentId || contract.report_date !== expected[shortId].date || contract.expected_mode !== expected[shortId].mode || contract.expected_scope !== expected[shortId].scope || !deepEqual(contract.perception_paths, expected[shortId].paths)) return null
  }
  if (!deepEqual(architecture, {
    exp011: { preprocessors: [], package_notice: true },
    exp012: {
      preprocessors: [{ type: 'audio_analyzer', deployment: 'gpt-audio-1.5', trigger: 'has_audio_files', inject_as: 'prompt_prefix', include_task_instruction: true, frames_per_video: null, max_total_frames: null }],
      config_created_at: '2026-03-09',
      header_declared_audio_heavy_tasks: 17,
    },
    exp026: {
      preprocessors: [
        { type: 'audio_analyzer', deployment: 'gpt-audio-1.5', trigger: 'has_audio_files', inject_as: 'prompt_prefix', include_task_instruction: true, frames_per_video: null, max_total_frames: null },
        { type: 'video_analyzer', deployment: 'gpt-5.4', trigger: 'has_video_files', inject_as: 'prompt_prefix', include_task_instruction: true, frames_per_video: 8, max_total_frames: 24 },
      ],
      use_docker: 'always',
      max_skills: 5,
      skill_catalog: ['audio', 'video', 'document', 'image', 'data'],
    },
  })) return null
  if (!deepEqual(history, expectedHistory)) return null
  if (interpretation.causal_attribution !== false || interpretation.invocation_count_known !== false || interpretation.external_quality_known !== false) return null
  if (interpretation.observed_claim !== 'information_sector_success_and_self_qa_differ_across_three_runs') return null
  if (interpretation.architecture_claim !== 'configured_path_expanded_from_packages_to_audio_to_audio_video_skills_sandbox') return null
  if (!deepEqual(interpretation.missing_execution_identities, expectedMissingIdentities)) return null
  if (!deepEqual(interpretation.caveats, expectedCaveats)) return null
  if (!deepEqual(sources, expectedSources) || !isIsoTimestamp(value._generated)) return null
  return { comparison, architecture, history, interpretation, sources }
}

export function selectPerceptionBenchmark(reports: unknown, sourceValue: unknown): PerceptionSelection {
  if (!Array.isArray(reports)) return { status: 'invalid', invalidSources: ['reports-index.json'] }
  const source = parseSource(sourceValue)
  if (!source) return { status: 'invalid', invalidSources: ['perception-note.json'] }
  const missingIds = PERCEPTION_REPORT_IDS.filter((id) => !reports.some((report) => isRecord(report) && report.short_id === id))
  if (missingIds.length) return { status: 'missing', missingIds }
  const invalidSources: string[] = []
  const rows = PERCEPTION_REPORT_IDS.map((id) => {
    const matches = reports.filter((report) => isRecord(report) && report.short_id === id)
    if (matches.length !== 1) { invalidSources.push(id); return null }
    const row = parseRow(id, matches[0], (source.comparison[id] as Record<string, unknown>).perception_paths)
    if (!row) invalidSources.push(id)
    return row
  })
  if (invalidSources.length) return { status: 'invalid', invalidSources }
  const valid = rows as PerceptionRow[]
  return { status: 'ready', rows: valid, exp011: valid[0], exp012: valid[1], exp026: valid[2], architecture: source.architecture as unknown as PerceptionArchitecture, history: source.history as Record<string, string>, interpretation: source.interpretation as unknown as PerceptionInterpretation, sources: source.sources as Record<string, string> }
}
