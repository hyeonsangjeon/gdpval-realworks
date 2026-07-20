import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFile, readdir } from 'node:fs/promises'
import test from 'node:test'
import YAML from 'yaml'

import { buildSuccessNoteData } from '../aggregate-success-note.mjs'
import { gradeIdentityFromRaw } from '../grade-identity.mjs'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

async function loadFixture() {
  const [source, report, entries] = await Promise.all([
    readRepoFile('data/notes/success-layers.yaml'),
    readRepoFile('batch-runner/results/exp026_sandbox_skills_multimodal/report/report.md'),
    readdir(new URL('../../data/grades/', import.meta.url), { withFileTypes: true }),
  ])
  const grades = []
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith('.json')) continue
    const data = JSON.parse(await readRepoFile(`data/grades/${entry.name}`))
    grades.push({ path: entry.name, ...gradeIdentityFromRaw(entry.name, data) })
  }
  return { source, report, grades }
}

test('success source joins report rows, pinned artifact inspection, and grade absence', async () => {
  const { source, report, grades } = await loadFixture()
  const data = buildSuccessNoteData(source, report, grades)
  assert.deepEqual(data.experiment.summary, { total_tasks: 220, success_count: 200, success_rate_pct: 90.9, retried_count: 105, avg_qa_score: 6.24 })
  assert.deepEqual(data.tasks.workbook.observed, { status: 'qa_failed', self_qa_score: 2, qa_passed: false, retried: true, latency_ms: 96784, files_count: 2 })
  assert.equal(data.tasks.workbook.inspection.company_rows, 35)
  assert.equal(data.tasks.workbook.request.expected_company_count, 500)
  assert.deepEqual(data.tasks.briefing.observed, { status: 'success', self_qa_score: 9, qa_passed: true, retried: true, latency_ms: 114997, files_count: 3 })
  assert.equal(data.tasks.briefing.inspection.slide_count, 32)
  assert.equal(data.tasks.briefing.inspection.page_count, 32)
  assert.equal(data.grade_inventory.external_grade_matches, 0)
  assert.equal(data.interpretation.external_grade_available, false)
})

test('success source rejects report, artifact, layer, and interpretation drift', async () => {
  const { source, report, grades } = await loadFixture()
  assert.throws(() => buildSuccessNoteData(source, report.replace('2/10 | 96784ms', '3/10 | 96784ms'), grades), /workbook report row changed/)
  assert.throws(() => buildSuccessNoteData(source.replace('company_rows: 35', 'company_rows: 36'), report, grades), /workbook inspection changed/)
  assert.throws(() => buildSuccessNoteData(source.replace('slide_count: 32', 'slide_count: 31'), report, grades), /briefing inspection changed/)
  assert.throws(() => buildSuccessNoteData(source.replace('id: fidelity', 'id: convenience'), report, grades), /success layers changed/)
  assert.throws(() => buildSuccessNoteData(source.replace('external_grade_available: false', 'external_grade_available: true'), report, grades), /must remain false/)
  const invalidStatus = report.replace('qa_failed | Yes | 2 | 2/10 | 96784ms', 'not_success | Yes | 2 | 2/10 | 96784ms')
  assert.notEqual(invalidStatus, report)
  assert.throws(() => buildSuccessNoteData(source, invalidStatus, grades), /report row values are invalid/)
})

test('success source fails when a non-dummy exp026 external grade appears', async () => {
  const { source, report, grades } = await loadFixture()
  const cases = [
    ['top-level', 'future.json', { experiment_id: 'exp026_sandbox_skills_multimodal' }],
    ['legacy meta', 'legacy.json', { _meta: { experiment_id: 'exp026_sandbox_skills_multimodal' } }],
    ['filename fallback', 'exp026_sandbox_skills_multimodal__judge__rubric__v1.json', {}],
    ['source pointer', 'renamed.json', { experiment_id: 'renamed', source_inference_experiment_id: 'exp026_sandbox_skills_multimodal' }],
  ]
  for (const [name, path, raw] of cases) {
    const identity = { path, ...gradeIdentityFromRaw(path, raw) }
    assert.throws(() => buildSuccessNoteData(source, report, [...grades, identity]), /external grade availability changed/, name)
  }
  const dummy = { path: 'dummy.json', ...gradeIdentityFromRaw('dummy.json', { _meta: { is_dummy: true, experiment_id: 'exp026_sandbox_skills_multimodal' } }) }
  assert.doesNotThrow(() => buildSuccessNoteData(source, report, [...grades, dummy]))
})

test('pinned HF artifacts match recorded hashes and selected manifest structure', { timeout: 30_000 }, async () => {
  const revision = '47aed3c0b13eaa90eb02803bec9d5c75e559f416'
  const root = `https://huggingface.co/datasets/HyeonSang/exp026_sandbox_skills_multimodal/resolve/${revision}`
  const paths = {
    selfReport: 'self_report.json',
    workbookManifest: 'deliverable_files/8079e27d-b6f3-4f75-a9b5-db27903c798d/manifest.json',
    workbook: 'deliverable_files/8079e27d-b6f3-4f75-a9b5-db27903c798d/sp500_pe_deep_dive.xlsx',
    briefingManifest: 'deliverable_files/9e8607e7-a38a-491f-ace1-e5ea7dc477cb/manifest.json',
    pptx: 'deliverable_files/9e8607e7-a38a-491f-ace1-e5ea7dc477cb/latam_fintech_strategy_briefing.pptx',
    pdf: 'deliverable_files/9e8607e7-a38a-491f-ace1-e5ea7dc477cb/latam_fintech_strategy_briefing.pdf',
  }
  const contracts = {
    selfReport: { sha256: 'ec93ad9ae193734bfc7cb78c1879328ef8a1ff6777af80dcd57b38acc5a0fa3a', maxBytes: 2 * 1024 * 1024, expectedBytes: 857559, collect: true },
    workbookManifest: { sha256: 'b7462b84ac3cb1f56ff53fec0471091e923bbaf59725c9c06e1dcae1a211812e', maxBytes: 64 * 1024, expectedBytes: 3195, collect: true },
    workbook: { sha256: 'fb26bf7ba2e16ac147d5918c99bfeabd887f779aa9cdcde9dbc73589078b6c73', maxBytes: 64 * 1024, expectedBytes: 19751, collect: false },
    briefingManifest: { sha256: '8de01ba8b43e33130168f074bdc054d4a69d3b3139bac3dae09225d671f7b5f2', maxBytes: 64 * 1024, expectedBytes: 3955, collect: true },
    pptx: { sha256: 'f74aede2e3ac34118554a5eb113cd75d4d1fb49031d0b8c06bf648dafe36d7f0', maxBytes: 128 * 1024, expectedBytes: 79257, collect: false },
    pdf: { sha256: '1ddd01654bea34ab58d0426db1a15b5eeb4636a7ae38a1069d188523f5a2a278', maxBytes: 192 * 1024, expectedBytes: 114751, collect: false },
  }
  const entries = await Promise.all(Object.entries(paths).map(async ([name, path]) => {
    const contract = contracts[name]
    const response = await fetch(`${root}/${path}`, { signal: AbortSignal.timeout(10_000) })
    assert.equal(response.status, 200, name)
    const declaredBytes = Number(response.headers.get('content-length'))
    if (Number.isFinite(declaredBytes)) assert.ok(declaredBytes <= contract.maxBytes, `${name} content-length cap`)
    assert.ok(response.body, `${name} response body`)
    const reader = response.body.getReader()
    const hash = createHash('sha256')
    const chunks = []
    let totalBytes = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      totalBytes += value.byteLength
      assert.ok(totalBytes <= contract.maxBytes, `${name} streaming byte cap`)
      hash.update(value)
      if (contract.collect) chunks.push(Buffer.from(value))
    }
    if (contract.expectedBytes != null) assert.equal(totalBytes, contract.expectedBytes, `${name} byte length`)
    assert.equal(hash.digest('hex'), contract.sha256, name)
    return [name, contract.collect ? Buffer.concat(chunks) : null]
  }))
  const downloaded = Object.fromEntries(entries)
  const selfReport = JSON.parse(downloaded.selfReport.toString('utf8'))
  const workbookManifest = JSON.parse(downloaded.workbookManifest.toString('utf8'))
  const briefingManifest = JSON.parse(downloaded.briefingManifest.toString('utf8'))
  const source = YAML.parse(await readRepoFile('data/notes/success-layers.yaml'))
  const expectedTasks = [
    {
      kind: 'workbook',
      id: '8079e27d-b6f3-4f75-a9b5-db27903c798d',
      pointer: '/task_results/135',
      status: 'qa_failed',
      qa: 2,
      files: source.tasks.workbook.artifact_set.selected_primary.path,
      phrases: ['April 11, 2025', 'all 500 companies', 'publicly available data on the open web', 'detailed Excel output', 'easily sortable Excel file'],
    },
    {
      kind: 'briefing',
      id: '9e8607e7-a38a-491f-ace1-e5ea7dc477cb',
      pointer: '/task_results/137',
      status: 'success',
      qa: 9,
      files: source.tasks.briefing.artifact_set.selected_primary.map((artifact) => artifact.path),
      phrases: ['PowerPoint presentation (exported as PDF format)', 'Latin America Macro Overview', 'State of LatAm Technology and Venture Markets', 'Latin America Fintech Landscape', 'roughly ~30 slides'],
    },
  ]
  for (const expected of expectedTasks) {
    const matches = selfReport.task_results.filter((task) => task.task_id === expected.id)
    assert.equal(matches.length, 1, `${expected.kind} unique task`)
    const task = matches[0]
    const index = selfReport.task_results.indexOf(task)
    assert.equal(`/task_results/${index}`, expected.pointer)
    assert.equal(expected.pointer, source.tasks[expected.kind].request.self_report_json_pointer)
    assert.equal(createHash('sha256').update(task.instruction, 'utf8').digest('hex'), source.tasks[expected.kind].request.instruction_sha256)
    assert.equal(task.status, expected.status)
    assert.equal(task.qa_score, expected.qa)
    assert.equal(task.retried, true)
    assert.equal(task.reference_file_urls.length, 0)
    const expectedPrimary = Array.isArray(expected.files) ? expected.files : [expected.files]
    assert.deepEqual(task.deliverable_files.filter((path) => !path.endsWith('/manifest.json')).sort(), [...expectedPrimary].sort())
    for (const phrase of expected.phrases) assert.match(task.instruction, new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')), `${expected.kind}: ${phrase}`)
  }
  assert.deepEqual(workbookManifest.selected_primary_artifacts, ['sp500_pe_deep_dive.xlsx'])
  assert.equal(workbookManifest.final_status, 'ok')
  assert.deepEqual(workbookManifest.verification_report.artifacts[0].metadata.sheet_names, ['Read Me', 'Company Detail', 'Sub-sector Summary', 'Sector Summary', 'Data Provenance'])
  assert.deepEqual(briefingManifest.selected_primary_artifacts, ['latam_fintech_strategy_briefing.pdf', 'latam_fintech_strategy_briefing.pptx'])
  assert.equal(briefingManifest.final_status, 'ok')
  assert.deepEqual(briefingManifest.verification_report.artifacts.map((artifact) => artifact.metadata), [{ page_count: 32 }, { slide_count: 32 }])
  assert.deepEqual(briefingManifest.render_report.map((artifact) => artifact.blank_pages), [[], []])
})
