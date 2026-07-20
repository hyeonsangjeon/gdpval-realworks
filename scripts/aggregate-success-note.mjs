#!/usr/bin/env node

import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import YAML from 'yaml'
import { gradeIdentityFromRaw } from './grade-identity.mjs'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SOURCE_PATH = join(ROOT, 'data', 'notes', 'success-layers.yaml')
const REPORT_PATH = join(ROOT, 'batch-runner', 'results', 'exp026_sandbox_skills_multimodal', 'report', 'report.md')
const GRADES_PATH = join(ROOT, 'data', 'grades')
const OUTPUT_PATH = join(ROOT, 'public', 'generated', 'success-note.json')

const EXPERIMENT_ID = 'exp026_sandbox_skills_multimodal'
const HF_REVISION = '47aed3c0b13eaa90eb02803bec9d5c75e559f416'
const SELF_REPORT_SHA256 = 'ec93ad9ae193734bfc7cb78c1879328ef8a1ff6777af80dcd57b38acc5a0fa3a'
const TASK_IDS = {
  workbook: '8079e27d-b6f3-4f75-a9b5-db27903c798d',
  briefing: '9e8607e7-a38a-491f-ace1-e5ea7dc477cb',
}
const ARTIFACT_SHA256 = {
  workbook: 'fb26bf7ba2e16ac147d5918c99bfeabd887f779aa9cdcde9dbc73589078b6c73',
  workbookManifest: 'b7462b84ac3cb1f56ff53fec0471091e923bbaf59725c9c06e1dcae1a211812e',
  pptx: 'f74aede2e3ac34118554a5eb113cd75d4d1fb49031d0b8c06bf648dafe36d7f0',
  pdf: '1ddd01654bea34ab58d0426db1a15b5eeb4636a7ae38a1069d188523f5a2a278',
  briefingManifest: '8de01ba8b43e33130168f074bdc054d4a69d3b3139bac3dae09225d671f7b5f2',
}
const EXPECTED_LAYERS = [
  { id: 'execution', question: 'did_the_process_finish' },
  { id: 'integrity', question: 'do_the_selected_files_exist_and_open' },
  { id: 'fidelity', question: 'does_the_output_meet_scope_data_and_format_requirements' },
  { id: 'quality', question: 'is_the_output_accurate_and_useful_to_an_expert' },
]
const EXPECTED_CAVEATS = [
  'report_file_generation_aggregate_is_inconsistent_with_task_artifacts',
  'retried_is_boolean_and_does_not_reveal_attempt_count',
  'artifact_inspection_is_structural_not_expert_financial_review',
  'huggingface_main_is_mutable_so_revision_and_hashes_are_pinned',
  'checked_in_grade_files_do_not_contain_an_exp026_external_grade',
]

const deepEqual = (left, right) => JSON.stringify(left) === JSON.stringify(right)
const require = (condition, message) => { if (!condition) throw new Error(message) }
const isSha = (value, length) => typeof value === 'string' && new RegExp(`^[0-9a-f]{${length}}$`).test(value)
const isInt = (value) => Number.isInteger(value) && value >= 0

function parseTaskRow(reportText, taskId) {
  const prefix = taskId.slice(0, 8)
  const rowPattern = new RegExp(`^\\|\\s*\\d+\\s*\\|\\s*\\\`${prefix}…\\\`\\s*\\|`)
  const matches = reportText.split('\n').filter((line) => rowPattern.test(line))
  require(matches.length === 1, `${prefix} report row must appear exactly once`)
  const cells = matches[0].split('|').slice(1, -1).map((cell) => cell.trim())
  require(cells.length === 9, `${prefix} report row has an invalid shape`)
  const status = cells[4] === '⚠️ qa_failed' ? 'qa_failed' : cells[4] === '✅ success' ? 'success' : null
  const qaMatch = cells[7].match(/^(\d+)\/10$/)
  const latencyMatch = cells[8].match(/^(\d+)ms$/)
  require(status && qaMatch && latencyMatch, `${prefix} report row values are invalid`)
  return {
    status,
    retried: cells[5] === 'Yes',
    files_count: Number(cells[6]),
    self_qa_score: Number(qaMatch[1]),
    latency_ms: Number(latencyMatch[1]),
  }
}

function validateSource(source) {
  require(source?.experiment?.short_id === 'exp026', 'success source experiment short ID changed')
  require(source.experiment.experiment_id === EXPERIMENT_ID, 'success source experiment identity changed')
  require(source.experiment.report_date === '2026-07-10', 'success source report date changed')
  require(source.experiment.report_scope === 'self_assessed_pre_grading', 'success source report scope changed')
  require(deepEqual(source.experiment.summary, {
    total_tasks: 220,
    success_count: 200,
    success_rate_pct: 90.9,
    retried_count: 105,
    avg_qa_score: 6.24,
  }), 'success source summary changed')
  require(source?.huggingface?.repository === 'HyeonSang/exp026_sandbox_skills_multimodal', 'HF repository changed')
  require(source.huggingface.revision === HF_REVISION && isSha(source.huggingface.revision, 40), 'HF revision changed')
  require(source.huggingface.self_report_sha256 === SELF_REPORT_SHA256 && isSha(source.huggingface.self_report_sha256, 64), 'self-report hash changed')

  const workbook = source?.tasks?.workbook
  const briefing = source?.tasks?.briefing
  require(workbook?.task_id === TASK_IDS.workbook && briefing?.task_id === TASK_IDS.briefing, 'success task identity changed')
  require(workbook.occupation === briefing.occupation && workbook.occupation === 'Financial and Investment Analysts', 'task occupation changed')
  require(deepEqual(workbook.observed, { status: 'qa_failed', self_qa_score: 2, qa_passed: false, retried: true, latency_ms: 96784 }), 'workbook observation changed')
  require(deepEqual(briefing.observed, { status: 'success', self_qa_score: 9, qa_passed: true, retried: true, latency_ms: 114997 }), 'briefing observation changed')
  require(deepEqual(workbook.request, {
    deliverable: 'sortable_sp500_workbook',
    expected_company_count: 500,
    as_of_date: '2025-04-11',
    requires_public_web_data: true,
    self_report_json_pointer: '/task_results/135',
    instruction_sha256: '20b003ca6515d99b493f381c053f8e51f820c68e652ba99ccfd416792330f4b5',
  }), 'workbook request changed')
  require(deepEqual(briefing.request, {
    deliverable: 'latam_fintech_client_briefing',
    approximate_slide_count: 30,
    requires_pptx: true,
    requires_pdf: true,
    self_report_json_pointer: '/task_results/137',
    instruction_sha256: '1adc6c94ad5f706c7934b79a8dfe938eb82f4fb2711ceda98233dce4e00c862f',
  }), 'briefing request changed')

  require(workbook.artifact_set.directory_file_count === 5 && workbook.artifact_set.selected_primary_count === 1 && workbook.artifact_set.support_file_count === 1, 'workbook artifact counts changed')
  require(workbook.artifact_set.selected_primary.sha256 === ARTIFACT_SHA256.workbook && workbook.artifact_set.selected_primary.size_bytes === 19751, 'workbook artifact identity changed')
  require(workbook.artifact_set.support.sha256 === ARTIFACT_SHA256.workbookManifest, 'workbook manifest identity changed')
  require(deepEqual(workbook.inspection, {
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
  }), 'workbook inspection changed')

  require(briefing.artifact_set.directory_file_count === 3 && briefing.artifact_set.selected_primary_count === 2 && briefing.artifact_set.support_file_count === 1, 'briefing artifact counts changed')
  require(Array.isArray(briefing.artifact_set.selected_primary) && briefing.artifact_set.selected_primary.length === 2, 'briefing primary artifacts changed')
  require(briefing.artifact_set.selected_primary[0].sha256 === ARTIFACT_SHA256.pptx && briefing.artifact_set.selected_primary[0].size_bytes === 79257, 'briefing PPTX identity changed')
  require(briefing.artifact_set.selected_primary[1].sha256 === ARTIFACT_SHA256.pdf && briefing.artifact_set.selected_primary[1].size_bytes === 114751, 'briefing PDF identity changed')
  require(briefing.artifact_set.support.sha256 === ARTIFACT_SHA256.briefingManifest, 'briefing manifest identity changed')
  require(deepEqual(briefing.inspection, {
    pptx_opened: true,
    pdf_opened: true,
    slide_count: 32,
    page_count: 32,
    blank_pages: 0,
    source_citations_verified: false,
    country_prioritization_verified: false,
  }), 'briefing inspection changed')

  require(deepEqual(source.success_layers, EXPECTED_LAYERS), 'success layers changed')
  require(source?.interpretation?.expected_claim === 'success_status_would_approximate_handoff_ready_work', 'expected claim changed')
  require(source.interpretation.observed_claim === 'execution_and_integrity_can_pass_while_fidelity_fails', 'observed claim changed')
  for (const field of ['external_grade_available', 'self_qa_is_external_grade', 'artifact_financial_accuracy_verified', 'causal_attribution']) {
    require(source.interpretation[field] === false, `${field} must remain false`)
  }
  require(deepEqual(source.interpretation.caveats, EXPECTED_CAVEATS), 'success caveats changed')
  return source
}

export function buildSuccessNoteData(sourceText, reportText, gradeIdentities) {
  const source = validateSource(YAML.parse(sourceText))
  require(reportText.includes('| **Experiment ID** | `exp026_sandbox_skills_multimodal` |'), 'exp026 report identity changed')
  require(reportText.includes('| **Execution Mode** | sandbox |'), 'exp026 report mode changed')
  require(reportText.includes('| **Date** | 2026-07-10 |'), 'exp026 report date changed')
  require(reportText.includes('## Execution Summary *(Self-Assessed, Pre-Grading)*'), 'exp026 report scope changed')
  require(reportText.includes('| Total Tasks | 220 |') && reportText.includes('| Success | 200 (90.9%) |'), 'exp026 report completion changed')
  require(reportText.includes('| Retried Tasks | 105 |') && reportText.includes('| Avg QA Score | 6.24/10 |'), 'exp026 report QA summary changed')

  const workbookRow = parseTaskRow(reportText, TASK_IDS.workbook)
  const briefingRow = parseTaskRow(reportText, TASK_IDS.briefing)
  require(deepEqual(workbookRow, { status: 'qa_failed', retried: true, files_count: 2, self_qa_score: 2, latency_ms: 96784 }), 'workbook report row changed')
  require(deepEqual(briefingRow, { status: 'success', retried: true, files_count: 3, self_qa_score: 9, latency_ms: 114997 }), 'briefing report row changed')
  require(reportText.includes('Workbook has 35 companies, not all 500 S&P constituents.'), 'workbook company-count issue missing')
  require(reportText.includes('Output uses placeholder/local data instead of public web-sourced market data.'), 'workbook source issue missing')

  require(Array.isArray(gradeIdentities) && gradeIdentities.length > 0, 'grade inventory is empty')
  const externalMatches = gradeIdentities.filter((grade) => !grade.is_dummy && (
    grade.experiment_id === EXPERIMENT_ID || grade.source_inference_experiment_id === EXPERIMENT_ID
  ))
  require(source.interpretation.external_grade_available === false && externalMatches.length === 0, 'exp026 external grade availability changed')
  const nonDummyExperimentIds = [...new Set(gradeIdentities
    .filter((grade) => !grade.is_dummy)
    .flatMap((grade) => [grade.experiment_id, grade.source_inference_experiment_id])
    .filter((value) => typeof value === 'string'))].sort()

  return {
    experiment: source.experiment,
    huggingface: source.huggingface,
    tasks: {
      workbook: { ...source.tasks.workbook, observed: { ...source.tasks.workbook.observed, files_count: workbookRow.files_count } },
      briefing: { ...source.tasks.briefing, observed: { ...source.tasks.briefing.observed, files_count: briefingRow.files_count } },
    },
    success_layers: source.success_layers,
    interpretation: source.interpretation,
    grade_inventory: {
      checked_files: gradeIdentities.length,
      external_grade_matches: 0,
      non_dummy_experiment_ids: nonDummyExperimentIds,
    },
    sources: {
      success: 'data/notes/success-layers.yaml',
      report: 'batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md',
      grades: 'data/grades',
    },
  }
}

async function loadGradeIdentities() {
  const entries = await readdir(GRADES_PATH, { withFileTypes: true })
  const identities = []
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.json')) continue
    const data = JSON.parse(await readFile(join(GRADES_PATH, entry.name), 'utf8'))
    const identity = gradeIdentityFromRaw(entry.name, data)
    identities.push({
      path: `data/grades/${entry.name}`,
      ...identity,
    })
  }
  return identities
}

export async function aggregateSuccessNote() {
  const [sourceText, reportText, gradeIdentities] = await Promise.all([
    readFile(SOURCE_PATH, 'utf8'),
    readFile(REPORT_PATH, 'utf8'),
    loadGradeIdentities(),
  ])
  const data = { ...buildSuccessNoteData(sourceText, reportText, gradeIdentities), _generated: new Date().toISOString() }
  await mkdir(dirname(OUTPUT_PATH), { recursive: true })
  await writeFile(OUTPUT_PATH, `${JSON.stringify(data, null, 2)}\n`)
  console.log(`✅ ${OUTPUT_PATH}`)
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  aggregateSuccessNote().catch((error) => {
    console.error(error)
    process.exitCode = 1
  })
}
