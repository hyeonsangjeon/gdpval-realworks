const EXPERIMENT_ID = 'exp026_sandbox_skills_multimodal'
const WORKBOOK_ID = '8079e27d-b6f3-4f75-a9b5-db27903c798d'
const BRIEFING_ID = '9e8607e7-a38a-491f-ace1-e5ea7dc477cb'
const HF_REVISION = '47aed3c0b13eaa90eb02803bec9d5c75e559f416'
const EXPECTED_CAVEATS = [
  'report_file_generation_aggregate_is_inconsistent_with_task_artifacts',
  'retried_is_boolean_and_does_not_reveal_attempt_count',
  'artifact_inspection_is_structural_not_expert_financial_review',
  'huggingface_main_is_mutable_so_revision_and_hashes_are_pinned',
  'checked_in_grade_files_do_not_contain_an_exp026_external_grade',
]

interface SuccessTaskBase {
  task_id: string
  occupation: string
  observed: {
    status: 'success' | 'qa_failed'
    self_qa_score: number
    qa_passed: boolean
    retried: true
    latency_ms: number
    files_count: number
  }
}

export interface SuccessWorkbookEvidence extends SuccessTaskBase {
  observed: SuccessTaskBase['observed'] & { status: 'qa_failed'; self_qa_score: 2; qa_passed: false; latency_ms: 96784; files_count: 2 }
  request: { deliverable: 'sortable_sp500_workbook'; expected_company_count: 500; as_of_date: '2025-04-11'; requires_public_web_data: true; self_report_json_pointer: '/task_results/135'; instruction_sha256: string }
  artifact_set: {
    directory_file_count: 5
    selected_primary_count: 1
    support_file_count: 1
    selected_primary: { path: string; size_bytes: 19751; sha256: string }
    support: { path: string; sha256: string }
  }
  inspection: {
    parser_opened: true
    sheet_count: 5
    sheet_names: string[]
    company_rows: 35
    unique_tickers: 35
    formula_count: 0
    index_weight_total: 1
    auto_filter: 'A1:P36'
    freeze_panes: 'A2'
    public_market_data_verified: false
  }
}

export interface SuccessBriefingEvidence extends SuccessTaskBase {
  observed: SuccessTaskBase['observed'] & { status: 'success'; self_qa_score: 9; qa_passed: true; latency_ms: 114997; files_count: 3 }
  request: { deliverable: 'latam_fintech_client_briefing'; approximate_slide_count: 30; requires_pptx: true; requires_pdf: true; self_report_json_pointer: '/task_results/137'; instruction_sha256: string }
  artifact_set: {
    directory_file_count: 3
    selected_primary_count: 2
    support_file_count: 1
    selected_primary: Array<{ path: string; size_bytes: number; sha256: string }>
    support: { path: string; sha256: string }
  }
  inspection: {
    pptx_opened: true
    pdf_opened: true
    slide_count: 32
    page_count: 32
    blank_pages: 0
    source_citations_verified: false
    country_prioritization_verified: false
  }
}

export interface SuccessInterpretation {
  expected_claim: 'success_status_would_approximate_handoff_ready_work'
  observed_claim: 'execution_and_integrity_can_pass_while_fidelity_fails'
  external_grade_available: false
  self_qa_is_external_grade: false
  artifact_financial_accuracy_verified: false
  causal_attribution: false
  caveats: string[]
}

export interface SuccessBenchmarkReady {
  status: 'ready'
  report: {
    shortId: 'exp026'
    totalTasks: 220
    successCount: 200
    successRatePct: 90.9
    retriedCount: 105
    avgQaScore: 6.24
  }
  workbook: SuccessWorkbookEvidence
  briefing: SuccessBriefingEvidence
  layers: Array<{ id: 'execution' | 'integrity' | 'fidelity' | 'quality'; question: string }>
  huggingface: { repository: string; revision: string; self_report_sha256: string }
  interpretation: SuccessInterpretation
  gradeInventory: { checked_files: number; external_grade_matches: 0; non_dummy_experiment_ids: string[] }
  sources: Record<string, string>
}

export type SuccessBenchmarkSelection =
  | SuccessBenchmarkReady
  | { status: 'missing'; missingIds: ['exp026'] }
  | { status: 'invalid'; invalidSources: string[] }

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value)
const isString = (value: unknown): value is string => typeof value === 'string'
const isInt = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0
const isFiniteRange = (value: unknown, min: number, max: number): value is number => typeof value === 'number' && Number.isFinite(value) && value >= min && value <= max
const isSha = (value: unknown, length: number): value is string => isString(value) && new RegExp(`^[0-9a-f]{${length}}$`).test(value)
const deepEqual = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right)
const isIsoTimestamp = (value: unknown): value is string => {
  if (!isString(value)) return false
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) && new Date(parsed).toISOString() === value
}

function parseTask(value: unknown, kind: 'workbook'): SuccessWorkbookEvidence | null
function parseTask(value: unknown, kind: 'briefing'): SuccessBriefingEvidence | null
function parseTask(value: unknown, kind: 'workbook' | 'briefing'): SuccessWorkbookEvidence | SuccessBriefingEvidence | null {
  if (!isRecord(value) || !isRecord(value.observed) || !isRecord(value.request) || !isRecord(value.artifact_set) || !isRecord(value.inspection)) return null
  const observed = value.observed
  const expected = kind === 'workbook'
    ? { id: WORKBOOK_ID, status: 'qa_failed', score: 2, qaPassed: false, latency: 96784, files: 2 }
    : { id: BRIEFING_ID, status: 'success', score: 9, qaPassed: true, latency: 114997, files: 3 }
  if (value.task_id !== expected.id || value.occupation !== 'Financial and Investment Analysts') return null
  if (observed.status !== expected.status || observed.self_qa_score !== expected.score || observed.qa_passed !== expected.qaPassed || observed.retried !== true || observed.latency_ms !== expected.latency || observed.files_count !== expected.files) return null

  if (kind === 'workbook') {
    if (!deepEqual(value.request, {
      deliverable: 'sortable_sp500_workbook', expected_company_count: 500, as_of_date: '2025-04-11', requires_public_web_data: true,
      self_report_json_pointer: '/task_results/135', instruction_sha256: '20b003ca6515d99b493f381c053f8e51f820c68e652ba99ccfd416792330f4b5',
    })) return null
    if (value.artifact_set.directory_file_count !== 5 || value.artifact_set.selected_primary_count !== 1 || value.artifact_set.support_file_count !== 1) return null
    const primary = value.artifact_set.selected_primary
    const support = value.artifact_set.support
    if (!isRecord(primary) || !isRecord(support) || primary.size_bytes !== 19751 || primary.sha256 !== 'fb26bf7ba2e16ac147d5918c99bfeabd887f779aa9cdcde9dbc73589078b6c73' || support.sha256 !== 'b7462b84ac3cb1f56ff53fec0471091e923bbaf59725c9c06e1dcae1a211812e') return null
    if (!deepEqual(value.inspection, {
      parser_opened: true,
      sheet_count: 5,
      sheet_names: ['Read Me', 'Company Detail', 'Sub-sector Summary', 'Sector Summary', 'Data Provenance'],
      company_rows: 35,
      unique_tickers: 35,
      formula_count: 0,
      index_weight_total: 1,
      auto_filter: 'A1:P36',
      freeze_panes: 'A2',
      public_market_data_verified: false,
    })) return null
  } else {
    if (!deepEqual(value.request, {
      deliverable: 'latam_fintech_client_briefing', approximate_slide_count: 30, requires_pptx: true, requires_pdf: true,
      self_report_json_pointer: '/task_results/137', instruction_sha256: '1adc6c94ad5f706c7934b79a8dfe938eb82f4fb2711ceda98233dce4e00c862f',
    })) return null
    if (value.artifact_set.directory_file_count !== 3 || value.artifact_set.selected_primary_count !== 2 || value.artifact_set.support_file_count !== 1) return null
    const primary = value.artifact_set.selected_primary
    const support = value.artifact_set.support
    if (!Array.isArray(primary) || primary.length !== 2 || !isRecord(primary[0]) || !isRecord(primary[1]) || !isRecord(support)) return null
    if (primary[0].size_bytes !== 79257 || primary[0].sha256 !== 'f74aede2e3ac34118554a5eb113cd75d4d1fb49031d0b8c06bf648dafe36d7f0') return null
    if (primary[1].size_bytes !== 114751 || primary[1].sha256 !== '1ddd01654bea34ab58d0426db1a15b5eeb4636a7ae38a1069d188523f5a2a278' || support.sha256 !== '8de01ba8b43e33130168f074bdc054d4a69d3b3139bac3dae09225d671f7b5f2') return null
    if (!deepEqual(value.inspection, { pptx_opened: true, pdf_opened: true, slide_count: 32, page_count: 32, blank_pages: 0, source_citations_verified: false, country_prioritization_verified: false })) return null
  }
  return value as unknown as SuccessWorkbookEvidence | SuccessBriefingEvidence
}

function parseSource(value: unknown) {
  if (!isRecord(value) || !isRecord(value.experiment) || !isRecord(value.huggingface) || !isRecord(value.tasks) || !Array.isArray(value.success_layers) || !isRecord(value.interpretation) || !isRecord(value.grade_inventory) || !isRecord(value.sources)) return null
  if (!deepEqual(value.experiment, {
    short_id: 'exp026',
    experiment_id: EXPERIMENT_ID,
    report_date: '2026-07-10',
    report_scope: 'self_assessed_pre_grading',
    summary: { total_tasks: 220, success_count: 200, success_rate_pct: 90.9, retried_count: 105, avg_qa_score: 6.24 },
  })) return null
  if (value.huggingface.repository !== 'HyeonSang/exp026_sandbox_skills_multimodal' || value.huggingface.revision !== HF_REVISION || !isSha(value.huggingface.revision, 40) || value.huggingface.self_report_sha256 !== 'ec93ad9ae193734bfc7cb78c1879328ef8a1ff6777af80dcd57b38acc5a0fa3a') return null
  const workbook = parseTask(value.tasks.workbook, 'workbook')
  const briefing = parseTask(value.tasks.briefing, 'briefing')
  if (!workbook || !briefing) return null
  if (!deepEqual(value.success_layers, [
    { id: 'execution', question: 'did_the_process_finish' },
    { id: 'integrity', question: 'do_the_selected_files_exist_and_open' },
    { id: 'fidelity', question: 'does_the_output_meet_scope_data_and_format_requirements' },
    { id: 'quality', question: 'is_the_output_accurate_and_useful_to_an_expert' },
  ])) return null
  if (value.interpretation.expected_claim !== 'success_status_would_approximate_handoff_ready_work' || value.interpretation.observed_claim !== 'execution_and_integrity_can_pass_while_fidelity_fails') return null
  for (const field of ['external_grade_available', 'self_qa_is_external_grade', 'artifact_financial_accuracy_verified', 'causal_attribution']) {
    if (value.interpretation[field] !== false) return null
  }
  if (!deepEqual(value.interpretation.caveats, EXPECTED_CAVEATS)) return null
  if (!isInt(value.grade_inventory.checked_files) || value.grade_inventory.checked_files < 1 || value.grade_inventory.external_grade_matches !== 0 || !Array.isArray(value.grade_inventory.non_dummy_experiment_ids) || value.grade_inventory.non_dummy_experiment_ids.some((id) => !isString(id) || id === EXPERIMENT_ID)) return null
  if (!deepEqual(value.sources, { success: 'data/notes/success-layers.yaml', report: 'batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md', grades: 'data/grades' })) return null
  if (!isIsoTimestamp(value._generated)) return null
  return { workbook, briefing, layers: value.success_layers, huggingface: value.huggingface, interpretation: value.interpretation, gradeInventory: value.grade_inventory, sources: value.sources }
}

function parseReport(value: unknown) {
  if (!isRecord(value) || !isRecord(value.meta) || !isRecord(value.summary) || !isRecord(value.task_qa)) return null
  const meta = value.meta
  const summary = value.summary
  if (value.short_id !== 'exp026' || meta.experiment_id !== EXPERIMENT_ID || meta.condition_name !== 'GPT-5.4 low + sandbox + skills + audio/video perception' || meta.model !== 'gpt-5.4' || meta.execution_mode !== 'sandbox' || meta.date !== '2026-07-10' || meta.report_scope !== 'self_assessed_pre_grading') return null
  if (summary.total_tasks !== 220 || summary.success_count !== 200 || summary.success_rate_pct !== 90.9 || summary.retried_count !== 105 || summary.avg_qa_score !== 6.24) return null
  if (!isInt(summary.error_count) || summary.error_count !== 6 || !isFiniteRange(summary.avg_qa_score, 0, 10)) return null
  if (value.task_qa[WORKBOOK_ID] !== 2 || value.task_qa[BRIEFING_ID] !== 9) return null
  return { shortId: 'exp026' as const, totalTasks: 220 as const, successCount: 200 as const, successRatePct: 90.9 as const, retriedCount: 105 as const, avgQaScore: 6.24 as const }
}

export function selectSuccessNoteBenchmark(reports: unknown, sourceValue: unknown): SuccessBenchmarkSelection {
  if (!Array.isArray(reports)) return { status: 'invalid', invalidSources: ['reports-index.json'] }
  const source = parseSource(sourceValue)
  if (!source) return { status: 'invalid', invalidSources: ['success-note.json'] }
  const matches = reports.filter((report) => isRecord(report) && report.short_id === 'exp026')
  if (matches.length === 0) return { status: 'missing', missingIds: ['exp026'] }
  if (matches.length !== 1) return { status: 'invalid', invalidSources: ['exp026'] }
  const report = parseReport(matches[0])
  if (!report) return { status: 'invalid', invalidSources: ['exp026'] }
  return {
    status: 'ready',
    report,
    workbook: source.workbook,
    briefing: source.briefing,
    layers: source.layers as SuccessBenchmarkReady['layers'],
    huggingface: source.huggingface as SuccessBenchmarkReady['huggingface'],
    interpretation: source.interpretation as unknown as SuccessInterpretation,
    gradeInventory: source.gradeInventory as SuccessBenchmarkReady['gradeInventory'],
    sources: source.sources as Record<string, string>,
  }
}
