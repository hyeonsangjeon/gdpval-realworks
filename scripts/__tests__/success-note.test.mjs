import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

import { buildSuccessNoteData } from '../aggregate-success-note.mjs'
import { gradeIdentityFromRaw } from '../grade-identity.mjs'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

async function importTypeScriptModule(path) {
  const source = await readRepoFile(path)
  const result = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

async function loadFixture() {
  const [selector, reportsIndex, source, report, entries] = await Promise.all([
    importTypeScriptModule('src/lib/successNoteBenchmark.ts'),
    readRepoFile('public/generated/reports-index.json').then(JSON.parse),
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
  const note = { ...buildSuccessNoteData(source, report, grades), _generated: '2026-07-20T00:00:00.000Z' }
  return { ...selector, reports: reportsIndex.reports, note }
}

test('success selector joins exp026 summary, task QA, and pinned artifact facts', async () => {
  const { selectSuccessNoteBenchmark, reports, note } = await loadFixture()
  const selection = selectSuccessNoteBenchmark(reports, note)
  assert.equal(selection.status, 'ready')
  assert.deepEqual(selection.report, { shortId: 'exp026', totalTasks: 220, successCount: 200, successRatePct: 90.9, retriedCount: 105, avgQaScore: 6.24 })
  assert.equal(selection.workbook.observed.status, 'qa_failed')
  assert.equal(selection.workbook.observed.self_qa_score, 2)
  assert.equal(selection.workbook.inspection.company_rows, 35)
  assert.equal(selection.briefing.observed.status, 'success')
  assert.equal(selection.briefing.observed.self_qa_score, 9)
  assert.equal(selection.briefing.inspection.slide_count, 32)
  assert.equal(selection.interpretation.external_grade_available, false)
})

test('success selector fails closed for missing, duplicate, malformed report, and malformed source', async () => {
  const { selectSuccessNoteBenchmark, reports, note } = await loadFixture()
  const exp026 = reports.find((report) => report.short_id === 'exp026')
  assert.deepEqual(selectSuccessNoteBenchmark(reports.filter((report) => report.short_id !== 'exp026'), note), { status: 'missing', missingIds: ['exp026'] })
  assert.deepEqual(selectSuccessNoteBenchmark([...reports, exp026], note), { status: 'invalid', invalidSources: ['exp026'] })
  const badReport = structuredClone(reports)
  badReport.find((report) => report.short_id === 'exp026').task_qa['8079e27d-b6f3-4f75-a9b5-db27903c798d'] = 3
  assert.deepEqual(selectSuccessNoteBenchmark(badReport, note), { status: 'invalid', invalidSources: ['exp026'] })
  const badSource = structuredClone(note)
  badSource.tasks.workbook.inspection.company_rows = 36
  assert.deepEqual(selectSuccessNoteBenchmark(reports, badSource), { status: 'invalid', invalidSources: ['success-note.json'] })
  assert.deepEqual(selectSuccessNoteBenchmark(reports, null), { status: 'invalid', invalidSources: ['success-note.json'] })
})

test('success selector rejects identity, artifact hash, grade, and interpretation drift independently', async () => {
  const { selectSuccessNoteBenchmark, reports, note } = await loadFixture()
  const sourceCases = [
    ['HF revision', (source) => { source.huggingface.revision = '0'.repeat(40) }],
    ['workbook hash', (source) => { source.tasks.workbook.artifact_set.selected_primary.sha256 = '0'.repeat(64) }],
    ['briefing pages', (source) => { source.tasks.briefing.inspection.page_count = 31 }],
    ['quality claim', (source) => { source.interpretation.artifact_financial_accuracy_verified = true }],
    ['external grade', (source) => { source.grade_inventory.external_grade_matches = 1 }],
    ['caveat', (source) => { source.interpretation.caveats.pop() }],
  ]
  for (const [name, mutate] of sourceCases) {
    const invalid = structuredClone(note)
    mutate(invalid)
    assert.deepEqual(selectSuccessNoteBenchmark(reports, invalid), { status: 'invalid', invalidSources: ['success-note.json'] }, name)
  }
})

test('success article resolves all observations from evidence without static measurements', async () => {
  const [journal, page, hero] = await Promise.all([
    readRepoFile('src/data/journal.ts'),
    readRepoFile('src/pages/JournalArticle.tsx'),
    readRepoFile('src/components/notes/NoteHeroVisual.tsx'),
  ])
  const start = journal.indexOf("...journalCatalog['what-does-success-mean']")
  const end = journal.indexOf("...journalCatalog['why-build-a-sandbox']")
  const article = journal.slice(start, end)
  const taskHero = hero.slice(hero.indexOf('function TaskContrastVisual'), hero.indexOf('function SandboxVisual'))

  assert.match(article, /benchmark: \{ kind: 'success' \}/)
  assert.match(article, /readingStyle: 'reflective'/)
  assert.match(article, /metrics: \[\]/)
  assert.match(article, /data: \[\]/)
  for (const narrative of ['expectation', 'status', 'workbook', 'briefing', 'interpretation', 'decision']) {
    assert.match(article, new RegExp(`benchmarkNarrative: 'success-${narrative}'`))
  }
  assert.doesNotMatch(article, /value: '90\.9%'|value: '105'|value: '6\.24'|35\/500|2\/10|9\/10|32장 briefing/)
  assert.match(page, /useSuccessNote\(usesSuccessBenchmark\)/)
  assert.match(page, /selectSuccessNoteBenchmark\(reports, successNote\)/)
  assert.match(page, /resolveSuccessArticle\(article, readySuccessBenchmark\)/)
  assert.match(page, /generated\/success-note\.json/)
  assert.match(taskHero, /workbook\.inspection\.company_rows/)
  assert.match(taskHero, /briefing\.inspection\.slide_count/)
  assert.doesNotMatch(taskHero, />2\/10<|>9\/10<|>35 \/ 500 companies</)
})

test('success article maps every reflective claim to pinned detailed evidence', async () => {
  const journal = await readRepoFile('src/data/journal.ts')
  const start = journal.indexOf("...journalCatalog['what-does-success-mean']")
  const end = journal.indexOf("...journalCatalog['why-build-a-sandbox']")
  const article = journal.slice(start, end)
  const evidenceStart = article.indexOf('\n    evidence: [')
  const citations = article.slice(0, evidenceStart)
  const evidence = article.slice(evidenceStart)
  const evidenceIds = [...evidence.matchAll(/\bid: '([^']+)'/g)].map((match) => match[1])
  const expectedIds = [
    'exp026-summary', 'workbook-row', 'workbook-qa', 'workbook-prompt', 'workbook-artifact',
    'briefing-row', 'briefing-prompt', 'briefing-artifacts', 'grade-inventory', 'success-contract',
  ]
  const citationIds = [...citations.matchAll(new RegExp(`'(${expectedIds.join('|')})'`, 'g'))].map((match) => match[1])
  assert.equal(evidenceIds.length, 10)
  assert.equal(new Set(evidenceIds).size, 10)
  assert.deepEqual([...evidenceIds].sort(), [...expectedIds].sort())
  assert.equal(citationIds.length, 30)
  assert.deepEqual([...new Set(citationIds)].sort(), [...expectedIds].sort())
  assert.match(article, /report\.md@\$\{SUCCESS_SOURCE_SHA\.slice\(0, 7\)\} · L1-L56/)
  assert.match(article, /report\.md@\$\{SUCCESS_SOURCE_SHA\.slice\(0, 7\)\} · L1073-L1077/)
  assert.match(article, /self_report\.json@\$\{SUCCESS_HF_REVISION\.slice\(0, 7\)\} · task_results\[135\] · L5883-L5921 · sha256 ec93ad9a…/)
  assert.match(article, /self_report\.json@\$\{SUCCESS_HF_REVISION\.slice\(0, 7\)\} · task_results\[137\] · L5963-L5999 · sha256 ec93ad9a…/)
  assert.match(article, /sp500_pe_deep_dive\.xlsx@\$\{SUCCESS_HF_REVISION\.slice\(0, 7\)\} · sha256 fb26bf7b…/)
  assert.match(article, /tree\/\$\{SUCCESS_SOURCE_SHA\}\/data\/grades/)
})

test('success source and browser suite are wired into the Pages gate', async () => {
  const [packageJson, deploy] = await Promise.all([
    readRepoFile('package.json').then(JSON.parse),
    readRepoFile('.github/workflows/deploy.yml'),
  ])
  assert.match(packageJson.scripts.aggregate, /aggregate-success-note\.mjs/)
  assert.match(packageJson.scripts.prebuild, /aggregate-success-note\.mjs/)
  assert.match(packageJson.scripts['test:aggregate'], /aggregate-success-note\.test\.mjs/)
  assert.match(packageJson.scripts['test:aggregate'], /success-note\.test\.mjs/)
  assert.match(packageJson.scripts['test:notes-browser:dist'], /test:success-browser:dist/)
  assert.match(deploy, /- 'data\/notes\/success-layers\.yaml'/)
  assert.match(deploy, /Build[\s\S]*Verify aggregate contracts and pinned history[\s\S]*Verify Field Notes in browser[\s\S]*Upload Pages artifact/)
})
