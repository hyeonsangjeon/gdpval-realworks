import assert from 'node:assert/strict'
import { readFile, readdir } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

import {
  buildPerceptionNoteData,
  skillDirectoryNames,
} from '../aggregate-perception-note.mjs'

const readRepoFile = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

async function importTypeScriptModule(path) {
  const source = await readRepoFile(path)
  const result = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 }, reportDiagnostics: true })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

async function loadFixture() {
  const [selector, reportsIndex, source, exp011, exp012, exp026, skillEntries] = await Promise.all([
    importTypeScriptModule('src/lib/perceptionNoteBenchmark.ts'),
    readRepoFile('public/generated/reports-index.json').then(JSON.parse),
    readRepoFile('data/notes/perception-pipeline.yaml'),
    readRepoFile('batch-runner/experiments/exp011_GPT52Chat_domain_packages.yaml'),
    readRepoFile('batch-runner/experiments/exp012_GPT52Chat_audio_multiagent.yaml'),
    readRepoFile('batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml'),
    readdir(new URL('../../batch-runner/skills/', import.meta.url), { withFileTypes: true }),
  ])
  const skills = skillDirectoryNames(skillEntries)
  const note = { ...buildPerceptionNoteData(source, { exp011, exp012, exp026 }, skills), _generated: '2026-07-18T00:00:00.000Z' }
  return { ...selector, reports: reportsIndex.reports, note }
}

test('perception selector joins three Information rows without inferring analyzer invocation', async () => {
  const { selectPerceptionBenchmark, reports, note } = await loadFixture()
  const selection = selectPerceptionBenchmark(reports, note)
  assert.equal(selection.status, 'ready')
  assert.deepEqual(selection.rows.map((row) => ({
    id: row.shortId,
    mode: row.mode,
    information: `${row.information.success}/${row.information.total}`,
    completion: row.information.successRatePct,
    qa: row.information.avgQaScore,
    latency: row.information.avgLatencyMs,
    paths: row.perceptionPaths,
  })), [
    { id: 'exp011', mode: 'subprocess', information: '25/25', completion: 100, qa: 5.8, latency: 30059, paths: [] },
    { id: 'exp012', mode: 'subprocess', information: '24/25', completion: 96, qa: 5.79, latency: 25553, paths: ['audio'] },
    { id: 'exp026', mode: 'sandbox', information: '23/25', completion: 92, qa: 6, latency: 144147, paths: ['audio', 'video'] },
  ])
  assert.equal(selection.interpretation.invocation_count_known, false)
  assert.equal(selection.interpretation.causal_attribution, false)
})

test('perception selector fails closed for missing, duplicate, malformed report, and malformed source', async () => {
  const { selectPerceptionBenchmark, reports, note } = await loadFixture()
  const matching = reports.filter((report) => ['exp011', 'exp012', 'exp026'].includes(report.short_id))
  assert.deepEqual(selectPerceptionBenchmark(matching.filter((report) => report.short_id !== 'exp012'), note), { status: 'missing', missingIds: ['exp012'] })
  assert.deepEqual(selectPerceptionBenchmark([...matching, matching.find((report) => report.short_id === 'exp026')], note), { status: 'invalid', invalidSources: ['exp026'] })
  const badSector = structuredClone(matching)
  badSector.find((report) => report.short_id === 'exp012').sector_breakdown[0].total = 17
  assert.deepEqual(selectPerceptionBenchmark(badSector, note), { status: 'invalid', invalidSources: ['exp012'] })
  const duplicateSector = structuredClone(matching)
  duplicateSector.find((report) => report.short_id === 'exp012').sector_breakdown.push({
    ...duplicateSector.find((report) => report.short_id === 'exp012').sector_breakdown[0],
    success: 23,
    success_rate_pct: 92,
  })
  assert.deepEqual(selectPerceptionBenchmark(duplicateSector, note), { status: 'invalid', invalidSources: ['exp012'] })
  const badSource = structuredClone(note)
  badSource.interpretation.causal_attribution = true
  assert.deepEqual(selectPerceptionBenchmark(matching, badSource), { status: 'invalid', invalidSources: ['perception-note.json'] })
  const badDate = structuredClone(note)
  badDate._generated = '2026-02-30T00:00:00.000Z'
  assert.deepEqual(selectPerceptionBenchmark(matching, badDate), { status: 'invalid', invalidSources: ['perception-note.json'] })
})

test('perception selector rejects report identity and source-contract drift independently', async () => {
  const { selectPerceptionBenchmark, reports, note } = await loadFixture()
  const matching = reports.filter((report) => ['exp011', 'exp012', 'exp026'].includes(report.short_id))
  const reportCases = [
    ['experiment', (report) => { report.meta.experiment_id = 'wrong' }],
    ['date', (report) => { report.meta.date = '2026-03-09' }],
    ['condition', (report) => { report.meta.condition_name = 'wrong' }],
    ['model', (report) => { report.meta.model = 'wrong' }],
    ['mode', (report) => { report.meta.execution_mode = 'code_interpreter' }],
    ['scope', (report) => { report.meta.report_scope = 'graded' }],
    ['success rate', (report) => { report.summary.success_rate_pct = 95.9 }],
    ['Information QA', (report) => { report.sector_breakdown[0].avg_qa_score = 11 }],
    ['Information latency', (report) => { report.sector_breakdown[0].avg_latency_ms = -1 }],
  ]
  for (const [name, mutate] of reportCases) {
    const invalid = structuredClone(matching)
    mutate(invalid.find((report) => report.short_id === 'exp012'))
    assert.deepEqual(selectPerceptionBenchmark(invalid, note), { status: 'invalid', invalidSources: ['exp012'] }, name)
  }
  const sourceCases = [
    ['path', (source) => { source.comparison.exp012.perception_paths = [] }],
    ['history', (source) => { source.history.audio_preprocessor_commit = '0'.repeat(40) }],
    ['skill catalog', (source) => { source.architecture.exp026.skill_catalog.pop() }],
    ['identity', (source) => { source.interpretation.missing_execution_identities[0] = 'unknown' }],
    ['metadata caveat', (source) => { source.interpretation.caveats.splice(2, 1) }],
  ]
  for (const [name, mutate] of sourceCases) {
    const invalid = structuredClone(note)
    mutate(invalid)
    assert.deepEqual(selectPerceptionBenchmark(matching, invalid), { status: 'invalid', invalidSources: ['perception-note.json'] }, name)
  }
})

test('perception article resolves observations from evidence without static outcome values', async () => {
  const [journal, page, hero] = await Promise.all([
    readRepoFile('src/data/journal.ts'),
    readRepoFile('src/pages/JournalArticle.tsx'),
    readRepoFile('src/components/notes/NoteHeroVisual.tsx'),
  ])
  const start = journal.indexOf("...journalCatalog['from-audio-to-multimodal-sandbox']")
  const end = journal.indexOf("...journalCatalog['what-does-success-mean']")
  const article = journal.slice(start, end)
  const perceptionHero = hero.slice(hero.indexOf('function PerceptionVisual'), hero.indexOf('function TaskContrastVisual'))

  assert.match(article, /benchmark: \{ kind: 'perception' \}/)
  assert.match(article, /readingStyle: 'reflective'/)
  assert.match(article, /metrics: \[\]/)
  assert.match(article, /data: \[\]/)
  for (const narrative of ['baseline', 'audio', 'sandbox', 'results', 'failure', 'decision']) {
    assert.match(article, new RegExp(`benchmarkNarrative: 'perception-${narrative}'`))
  }
  assert.doesNotMatch(article, /25\/25|24\/25|23\/25|96\.0|92\.0|144\.1초/)
  assert.match(page, /usePerceptionNote\(usesPerceptionBenchmark\)/)
  assert.match(page, /selectPerceptionBenchmark\(reports, perceptionNote\)/)
  assert.match(page, /resolvePerceptionArticle\(article, readyPerceptionBenchmark\)/)
  assert.match(page, /generated\/perception-note\.json/)
  assert.match(page, /row\.information\.success/)
  assert.match(perceptionHero, /stage\.row\.information\.success/)
  assert.match(perceptionHero, /stage\.row\.information\.avgQaScore/)
  assert.doesNotMatch(perceptionHero, />25 \/ 25<|>24 \/ 25<|>23 \/ 25</)
})

test('perception article maps detailed inline evidence and pinned source links', async () => {
  const journal = await readRepoFile('src/data/journal.ts')
  const start = journal.indexOf("...journalCatalog['from-audio-to-multimodal-sandbox']")
  const end = journal.indexOf("...journalCatalog['what-does-success-mean']")
  const article = journal.slice(start, end)
  const evidenceStart = article.indexOf('\n    evidence: [')
  const citations = article.slice(0, evidenceStart)
  const evidence = article.slice(evidenceStart)
  const evidenceIds = [...evidence.matchAll(/\bid: '([^']+)'/g)].map((match) => match[1])
  const expectedIds = [
    'exp011-report', 'exp012-report', 'exp026-report', 'exp011-config',
    'exp012-config', 'exp026-config', 'exp026-runner', 'exp026-failure',
    'audio-history', 'sandbox-history', 'docker-history', 'perception-contract',
  ]
  const citationIds = [...citations.matchAll(new RegExp(`'(${expectedIds.join('|')})'`, 'g'))].map((match) => match[1])

  assert.equal(evidenceIds.length, 12)
  assert.equal(new Set(evidenceIds).size, 12)
  assert.deepEqual([...evidenceIds].sort(), [...expectedIds].sort())
  assert.equal(citationIds.length, 34)
  assert.deepEqual([...new Set(citationIds)].sort(), [...expectedIds].sort())
  assert.match(citations, /benchmarkNarrative: 'perception-failure'[\s\S]*paragraphCitations: \[\['exp026-report', 'exp026-failure'\], \['exp026-report', 'exp026-config', 'perception-contract'\]\]/)
  assert.match(article, /report\.md@\$\{PERCEPTION_SOURCE_SHA\.slice\(0, 7\)\} · L1-L72/)
  assert.equal((article.match(/report\.md@\$\{PERCEPTION_SOURCE_SHA\.slice\(0, 7\)\} · L1-L75/g) ?? []).length, 2)
  assert.match(article, /exp011_GPT52Chat_domain_packages\.yaml@\$\{PERCEPTION_SOURCE_SHA\.slice\(0, 7\)\} · L1-L180/)
  assert.match(article, /sandbox_runner\.py@\$\{PERCEPTION_SOURCE_SHA\.slice\(0, 7\)\} · L1034-L1053/)
  assert.match(article, /exp026_sandbox_skills_multimodal\.yaml@\$\{PERCEPTION_SOURCE_SHA\.slice\(0, 7\)\} · L50-L270/)
  assert.match(article, /commit\/\$\{AUDIO_PREPROCESSOR_COMMIT\}/)
  assert.match(article, /commit\/\$\{SANDBOX_MULTIMODAL_COMMIT\}/)
  assert.match(article, /commit\/\$\{DOCKER_ALWAYS_COMMIT\}/)
})

test('perception inputs and browser suite are wired into the Pages gate', async () => {
  const [packageJson, deploy] = await Promise.all([
    readRepoFile('package.json').then(JSON.parse),
    readRepoFile('.github/workflows/deploy.yml'),
  ])
  assert.match(packageJson.scripts.aggregate, /aggregate-perception-note\.mjs/)
  assert.match(packageJson.scripts.prebuild, /aggregate-perception-note\.mjs/)
  assert.match(packageJson.scripts['test:aggregate:prepared'], /aggregate-perception-note\.test\.mjs/)
  assert.match(packageJson.scripts['test:aggregate:prepared'], /perception-note\.test\.mjs/)
  assert.match(packageJson.scripts['test:notes-browser:dist'], /test:perception-browser:dist/)
  for (const path of [
    "batch-runner/skills/**",
    'package.json',
    'package-lock.json',
    '.github/workflows/deploy.yml',
    'data/notes/perception-pipeline.yaml',
  ]) {
    assert.match(deploy, new RegExp(`- '${path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}'`))
  }
  assert.match(deploy, /Build[\s\S]*Verify aggregate contracts and pinned history[\s\S]*Verify Field Notes in browser[\s\S]*Upload Pages artifact/)
})
