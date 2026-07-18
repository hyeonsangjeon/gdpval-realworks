import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

import { buildIntegrityNoteData } from '../aggregate-integrity-note.mjs'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

async function importTypeScriptModule(path) {
  const source = await readRepoFile(path)
  const result = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 },
    reportDiagnostics: true,
  })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

async function loadFixture() {
  const [selector, reportsIndex, source, beforeConfig, afterConfig] = await Promise.all([
    importTypeScriptModule('src/lib/integrityNoteBenchmark.ts'),
    readRepoFile('public/generated/reports-index.json').then(JSON.parse),
    readRepoFile('data/notes/integrity-incidents.yaml'),
    readRepoFile('batch-runner/experiments/exp013_GPT54_reasoning_high.yaml'),
    readRepoFile('batch-runner/experiments/exp025_GPT54_high_postfix.yaml'),
  ])
  return {
    ...selector,
    reports: reportsIndex.reports,
    note: { ...buildIntegrityNoteData(source, beforeConfig, afterConfig), _generated: '2026-07-18T00:00:00.000Z' },
  }
}

test('integrity selector joins exp013 and exp025 report observations without causal attribution', async () => {
  const { selectIntegrityNoteBenchmark, reports, note } = await loadFixture()
  const selection = selectIntegrityNoteBenchmark(reports, note)
  assert.equal(selection.status, 'ready')
  assert.deepEqual(selection.rows.map((row) => ({
    id: row.shortId,
    success: `${row.successCount}/${row.totalTasks}`,
    completion: row.successRatePct,
    errors: row.errorCount,
    retries: row.retriedCount,
    qa: row.avgQaScore,
    residual: row.residualCount,
  })), [
    { id: 'exp013', success: '211/220', completion: 95.9, errors: 9, retries: 54, qa: 6.07, residual: 0 },
    { id: 'exp025', success: '181/220', completion: 82.3, errors: 17, retries: 66, qa: 6.47, residual: 22 },
  ])
  assert.equal(selection.observedGapPctPoints, -13.6)
  assert.equal(selection.successDifference, -30)
  assert.equal(selection.interpretation.causal_attribution, false)
})

test('integrity selector reports missing, duplicate, malformed report, and malformed source', async () => {
  const { selectIntegrityNoteBenchmark, reports, note } = await loadFixture()
  const matching = reports.filter((report) => ['exp013', 'exp025'].includes(report.short_id))
  assert.deepEqual(selectIntegrityNoteBenchmark(matching.filter((report) => report.short_id !== 'exp013'), note), { status: 'missing', missingIds: ['exp013'] })
  assert.deepEqual(
    selectIntegrityNoteBenchmark([...matching, matching.find((report) => report.short_id === 'exp013')], note),
    { status: 'invalid', invalidSources: ['exp013'] },
  )

  const invalidReport = structuredClone(matching)
  invalidReport.find((report) => report.short_id === 'exp025').summary.success_rate_pct = 82.4
  assert.deepEqual(selectIntegrityNoteBenchmark(invalidReport, note), { status: 'invalid', invalidSources: ['exp025'] })
  assert.deepEqual(selectIntegrityNoteBenchmark(matching, null), { status: 'invalid', invalidSources: ['integrity-note.json'] })

  const invalidSource = structuredClone(note)
  invalidSource.interpretation.causal_attribution = true
  assert.deepEqual(selectIntegrityNoteBenchmark(matching, invalidSource), { status: 'invalid', invalidSources: ['integrity-note.json'] })
})

test('integrity selector rejects identity, scope, count, and history drift independently', async () => {
  const { selectIntegrityNoteBenchmark, reports, note } = await loadFixture()
  const matching = reports.filter((report) => ['exp013', 'exp025'].includes(report.short_id))
  const cases = [
    ['experiment identity', (report) => { report.meta.experiment_id = 'wrong' }],
    ['date', (report) => { report.meta.date = '2026-05-21' }],
    ['condition', (report) => { report.meta.condition_name = 'wrong' }],
    ['model', (report) => { report.meta.model = 'wrong' }],
    ['mode', (report) => { report.meta.execution_mode = 'code_interpreter' }],
    ['scope', (report) => { report.meta.report_scope = 'graded' }],
    ['task count', (report) => { report.summary.total_tasks = 50 }],
    ['success count', (report) => { report.summary.success_count = 221 }],
    ['error count', (report) => { report.summary.error_count = 50 }],
    ['retry count', (report) => { report.summary.retried_count = 221 }],
    ['QA', (report) => { report.summary.avg_qa_score = Number.NaN }],
  ]
  for (const [name, mutate] of cases) {
    const invalid = structuredClone(matching)
    mutate(invalid.find((report) => report.short_id === 'exp025'))
    assert.deepEqual(selectIntegrityNoteBenchmark(invalid, note), { status: 'invalid', invalidSources: ['exp025'] }, name)
  }

  const badHistory = structuredClone(note)
  badHistory.history.core_fix_commit = '0'.repeat(40)
  assert.deepEqual(selectIntegrityNoteBenchmark(matching, badHistory), { status: 'invalid', invalidSources: ['integrity-note.json'] })

  const sourceCases = [
    ['compared field type', (source) => { source.comparison.compared_fields[0] = null }],
    ['compared field duplicate', (source) => { source.comparison.compared_fields[2] = 'condition_a' }],
    ['compared field replacement', (source) => { source.comparison.compared_fields[1] = 'condition_b' }],
    ['compared field addition', (source) => { source.comparison.compared_fields.push('extra') }],
    ['identity type', (source) => { source.interpretation.missing_execution_identities[0] = null }],
    ['identity duplicate', (source) => { source.interpretation.missing_execution_identities[3] = 'execution_git_sha' }],
    ['identity replacement', (source) => { source.interpretation.missing_execution_identities[1] = 'unrelated_identity' }],
    ['identity addition', (source) => { source.interpretation.missing_execution_identities.push('extra_identity') }],
  ]
  for (const [name, mutate] of sourceCases) {
    const invalid = structuredClone(note)
    mutate(invalid)
    assert.deepEqual(
      selectIntegrityNoteBenchmark(matching, invalid),
      { status: 'invalid', invalidSources: ['integrity-note.json'] },
      name,
    )
  }
})

test('integrity article and hero resolve from evidence without static measurement values', async () => {
  const [journal, hero, page] = await Promise.all([
    readRepoFile('src/data/journal.ts'),
    readRepoFile('src/components/notes/NoteHeroVisual.tsx'),
    readRepoFile('src/pages/JournalArticle.tsx'),
  ])
  const articleStart = journal.indexOf("...journalCatalog['honest-pipeline-lower-score']")
  const articleEnd = journal.indexOf("...journalCatalog['from-audio-to-multimodal-sandbox']")
  const article = journal.slice(articleStart, articleEnd)
  const heroStart = hero.indexOf('function IntegrityVisual')
  const heroEnd = hero.indexOf('function PerceptionVisual')
  const integrityHero = hero.slice(heroStart, heroEnd)

  assert.match(article, /benchmark: \{ kind: 'integrity' \}/)
  assert.match(article, /readingStyle: 'reflective'/)
  assert.match(article, /metrics: \[\]/)
  assert.match(article, /data: \[\]/)
  assert.doesNotMatch(article, /95\.9|82\.3|211\/220|181\/220|13\.6|value: '66'/)
  assert.match(integrityHero, /before\.successRatePct/)
  assert.match(integrityHero, /after\.successRatePct/)
  assert.match(integrityHero, /observedGapPctPoints/)
  assert.doesNotMatch(integrityHero, />95\.9%<|>82\.3%<|-13\.6%p/)
  assert.match(page, /useIntegrityNote\(usesIntegrityBenchmark\)/)
  assert.match(page, /selectIntegrityNoteBenchmark\(reports, integrityNote\)/)
  assert.match(page, /resolveIntegrityArticle\(article, readyIntegrityBenchmark\)/)
  assert.match(page, /generated\/integrity-note\.json/)
})

test('integrity source changes trigger the combined Field Notes browser gate', async () => {
  const deploy = await readRepoFile('.github/workflows/deploy.yml')
  assert.match(deploy, /- 'data\/notes\/integrity-incidents\.yaml'/)
  assert.match(deploy, /Verify Field Notes in browser[\s\S]*npm run test:notes-browser:dist/)
})
