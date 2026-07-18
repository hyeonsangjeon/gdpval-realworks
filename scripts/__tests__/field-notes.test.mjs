import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const readSource = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

async function importTypeScriptModule(path) {
  const source = await readSource(path)
  const result = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 },
    reportDiagnostics: true,
  })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

test('prompt-complexity selector reads the report index used by experiment details', async () => {
  const [{ selectPromptComplexityBenchmark }, reportsIndex] = await Promise.all([
    importTypeScriptModule('src/lib/promptComplexityBenchmark.ts'),
    readSource('public/generated/reports-index.json').then(JSON.parse),
  ])

  const selection = selectPromptComplexityBenchmark(reportsIndex.reports)
  assert.equal(selection.status, 'ready')
  assert.deepEqual(
    selection.rows.map((row) => ({
      shortId: row.shortId,
      condition: row.condition,
      mode: row.executionMode,
      success: `${row.successCount}/${row.totalTasks}`,
      completion: row.successRatePct,
      qa: row.avgQaScore,
    })),
    [
      { shortId: 'exp003', condition: 'Baseline', mode: 'subprocess', success: '211/220', completion: 95.9, qa: 6.18 },
      { shortId: 'exp004', condition: 'Elicit', mode: 'subprocess', success: '200/220', completion: 90.9, qa: 5.87 },
      { shortId: 'exp005', condition: 'Elicit v2', mode: 'subprocess', success: '199/220', completion: 90.5, qa: 6.16 },
    ],
  )
  assert.equal(selection.completionDeltaPctPoints, -5.5)
})

test('prompt-complexity selector reports missing benchmark rows', async () => {
  const { selectPromptComplexityBenchmark } = await importTypeScriptModule('src/lib/promptComplexityBenchmark.ts')
  const selection = selectPromptComplexityBenchmark([])

  assert.deepEqual(selection, {
    status: 'missing',
    missingIds: ['exp003', 'exp004', 'exp005'],
  })
})

test('prompt-complexity selector rejects duplicate and invalid benchmark rows', async () => {
  const [{ selectPromptComplexityBenchmark }, reportsIndex] = await Promise.all([
    importTypeScriptModule('src/lib/promptComplexityBenchmark.ts'),
    readSource('public/generated/reports-index.json').then(JSON.parse),
  ])
  const reports = reportsIndex.reports.filter((report) => ['exp003', 'exp004', 'exp005'].includes(report.short_id))

  const duplicate = selectPromptComplexityBenchmark([...reports, reports.find((report) => report.short_id === 'exp003')])
  assert.deepEqual(duplicate, { status: 'invalid', invalidIds: ['exp003'] })

  const cases = [
    ['non-string condition', (report) => { report.meta.condition_name = 42 }],
    ['wrong condition', (report) => { report.meta.condition_name = 'Elicit' }],
    ['non-string execution mode', (report) => { report.meta.execution_mode = 42 }],
    ['wrong execution mode', (report) => { report.meta.execution_mode = 'code_interpreter' }],
    ['zero total tasks', (report) => { report.summary.total_tasks = 0 }],
    ['non-integer total tasks', (report) => { report.summary.total_tasks = 220.5 }],
    ['negative success count', (report) => { report.summary.success_count = -1 }],
    ['success count over total', (report) => { report.summary.success_count = 221 }],
    ['non-integer success count', (report) => { report.summary.success_count = 210.5 }],
    ['non-finite success rate', (report) => { report.summary.success_rate_pct = Number.NaN }],
    ['negative success rate', (report) => { report.summary.success_rate_pct = -1 }],
    ['success rate over 100', (report) => { report.summary.success_rate_pct = 101 }],
    ['success rate inconsistent with counts', (report) => { report.summary.success_rate_pct = 95.8 }],
    ['non-finite QA score', (report) => { report.summary.avg_qa_score = Number.NaN }],
    ['negative QA score', (report) => { report.summary.avg_qa_score = -1 }],
    ['QA score over 10', (report) => { report.summary.avg_qa_score = 11 }],
  ]

  for (const [name, mutate] of cases) {
    const invalid = structuredClone(reports)
    mutate(invalid.find((report) => report.short_id === 'exp003'))
    assert.deepEqual(
      selectPromptComplexityBenchmark(invalid),
      { status: 'invalid', invalidIds: ['exp003'] },
      name,
    )
  }
})

test('experiment detail summary uses the same report index snapshot as notes', async () => {
  const [{ applyReportIndexSnapshot }, reportsIndex, hook] = await Promise.all([
    importTypeScriptModule('src/lib/reportIndexSnapshot.ts'),
    readSource('public/generated/reports-index.json').then(JSON.parse),
    readSource('src/hooks/useReports.ts'),
  ])
  const entry = reportsIndex.reports.find((report) => report.short_id === 'exp003')
  const fullReport = {
    ...structuredClone(entry),
    short_id: 'stale',
    meta: { ...entry.meta, condition_name: 'stale condition' },
    summary: { ...entry.summary, success_count: 0, success_rate_pct: 0, avg_qa_score: 0 },
    task_results: [],
  }

  const merged = applyReportIndexSnapshot(fullReport, entry, 'exp003')
  assert.equal(merged.short_id, 'exp003')
  assert.deepEqual(merged.meta, entry.meta)
  assert.deepEqual(merged.summary, entry.summary)
  assert.deepEqual(merged.recovery_stats, entry.recovery_stats)
  assert.deepEqual(merged.narrative, entry.narrative)
  assert.deepEqual(merged.task_results, [])
  assert.match(hook, /applyReportIndexSnapshot\(data, entry, shortId\)/)
})

test('prompt-complexity note keeps its experiment and navigation contracts', async () => {
  const [journal, catalog] = await Promise.all([
    readSource('src/data/journal.ts'),
    readSource('src/data/journalLinks.ts'),
  ])

  assert.match(catalog, /'when-more-prompt-is-less':[\s\S]*relatedExperiments: \['exp003', 'exp004', 'exp005'\]/)
  assert.match(journal, /articleSlug: 'when-more-prompt-is-less'/)
  assert.match(journal, /articleSlugs: \['when-more-prompt-is-less', 'why-build-a-sandbox'\]/)
  assert.match(journal, /benchmark: \{ kind: 'prompt-complexity' \}/)
  assert.match(journal, /benchmarkNarrative: 'prompt-complexity-results'/)
  assert.doesNotMatch(journal, /\{ label: 'exp003 Baseline', primary:/)
  assert.match(journal, /Elicit은 별도 모델이나 서비스가 아니라[\s\S]*GDPVal 연구의 프롬프트 전략이다/)
  assert.match(journal, /https:\/\/arxiv\.org\/pdf\/2510\.04374#page=37/)
})

test('prompt-complexity hero reflects the source five-step design', async () => {
  const [hero, benchmark] = await Promise.all([
    readSource('src/components/notes/NoteHeroVisual.tsx'),
    readSource('src/lib/promptComplexityBenchmark.ts'),
  ])
  const promptSummary = hero.slice(
    hero.indexOf("if (variant === 'prompt-complexity')"),
    hero.indexOf("if (variant === 'runtime')"),
  )

  assert.match(benchmark, /mode: 'FIVE MANDATORY STEPS'/)
  assert.match(benchmark, /'2 · DISPLAY PNG'/)
  assert.match(benchmark, /mode: 'SAME FIVE STEPS · NEW STEP 2'/)
  assert.match(benchmark, /'2 · PILLOW CHECK'/)
  assert.match(hero, /promptBenchmark\.map/)
  assert.match(hero, /getExperimentHref\(row\.shortId\)/)
  assert.match(promptSummary, /aria-label="프롬프트 전략별 실험 상세"/)
  assert.doesNotMatch(promptSummary, /role="img"/)
  assert.doesNotMatch(hero, /success: '211 \/ 220'|\['Baseline', '기본 계약', '95\.9%'/)
  assert.doesNotMatch(hero, /checks: [367]/)
  assert.doesNotMatch(hero, /MORE CHECKS · FEWER FINISHES/)
})

test('journal article resolves visuals from reports and links to source details', async () => {
  const [article, reportsHook] = await Promise.all([
    readSource('src/pages/JournalArticle.tsx'),
    readSource('src/hooks/useReports.ts'),
  ])

  assert.match(article, /selectPromptComplexityBenchmark\(reports\)/)
  assert.match(article, /useReports\(usesReportBenchmark\)/)
  assert.match(article, /<JournalArticleContent key=\{slug \?\? 'missing'\} slug=\{slug\} \/>/)
  assert.match(article, /generated\/reports-index\.json/)
  assert.match(article, /getExperimentHref\(row\.shortId\)/)
  assert.match(article, /promptBenchmark=\{readyPromptBenchmark\?\.rows\}/)
  assert.match(article, /promptBenchmark\?\.status === 'invalid'/)
  assert.match(reportsHook, /new AbortController\(\)/)
  assert.match(reportsHook, /signal: controller\.signal/)
  assert.match(reportsHook, /return \(\) => controller\.abort\(\)/)
  assert.match(reportsHook, /if \(err\.name === 'AbortError'\) return/)
})

test('comparison chart preserves mobile labels and reduced-motion behavior', async () => {
  const chart = await readSource('src/components/notes/NoteComparisonChart.tsx')

  assert.match(chart, /interval=\{chart\.kind === 'dual' \? 0 : undefined\}/)
  assert.match(chart, /const reduceMotion = useReducedMotion\(\)/)
  assert.equal(chart.match(/isAnimationActive=\{!reduceMotion\}/g)?.length, 4)
})