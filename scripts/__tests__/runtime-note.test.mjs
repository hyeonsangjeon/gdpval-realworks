import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

import { buildRuntimeNoteData } from '../aggregate-runtime-note.mjs'

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

async function loadRuntimeFixture() {
  const [selector, reportsIndex, workflow, incidents] = await Promise.all([
    importTypeScriptModule('src/lib/runtimeNoteBenchmark.ts'),
    readRepoFile('public/generated/reports-index.json').then(JSON.parse),
    readRepoFile('.github/workflows/batch-run.yml'),
    readRepoFile('data/notes/runtime-incidents.yaml'),
  ])
  const runtimeNote = {
    ...buildRuntimeNoteData(workflow, incidents),
    _generated: '2026-07-18T00:00:00.000Z',
  }
  return { ...selector, reports: reportsIndex.reports, runtimeNote }
}

test('runtime note selector joins report recovery with workflow policy', async () => {
  const { selectRuntimeNoteBenchmark, reports, runtimeNote } = await loadRuntimeFixture()
  const selection = selectRuntimeNoteBenchmark(reports, runtimeNote)

  assert.equal(selection.status, 'ready')
  assert.deepEqual(selection.rows.map((row) => ({
    id: row.shortId,
    mode: row.executionMode,
    duration: row.duration,
    success: `${row.successCount}/${row.totalTasks}`,
    errors: row.errorCount,
    retried: row.retriedCount,
  })), [
    { id: 'exp008', mode: 'subprocess', duration: '149m 7s', success: '215/220', errors: 5, retried: 26 },
    { id: 'exp010', mode: 'code_interpreter', duration: '183m 22s', success: '219/220', errors: 1, retried: 21 },
    { id: 'exp025', mode: 'subprocess', duration: '501m 32s', success: '181/220', errors: 17, retried: 66 },
    { id: 'exp026', mode: 'sandbox', duration: '5171m 24s', success: '200/220', errors: 6, retried: 105 },
  ])
  assert.deepEqual(selection.exp026.recoveryRounds, [
    { round: 1, attempted: 78, recovered: 78, stillFailed: 0 },
    { round: 2, attempted: 27, recovered: 7, stillFailed: 20 },
  ])
  assert.deepEqual(selection.currentPolicy, {
    scope: 'condition_a',
    watchdog_minutes: 290,
    step_timeout_minutes: 350,
    job_timeout_minutes: 360,
    step_timeout_headroom_minutes: 60,
  })
  assert.equal(selection.incident.approx_minute, 330)
  assert.equal(selection.incident.policy.step_timeout_minutes, 330)
  assert.equal(selection.incident.fix.step_timeout_after_minutes, 350)
  assert.equal(selection.incident.workflow_commit, '36b0e5bed5e9be2622e505f68d3746eec1b6cc12')
})

test('runtime note selector reports missing and duplicate reports', async () => {
  const { selectRuntimeNoteBenchmark, reports, runtimeNote } = await loadRuntimeFixture()
  const matching = reports.filter((report) => ['exp008', 'exp010', 'exp025', 'exp026'].includes(report.short_id))

  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching.filter((report) => report.short_id !== 'exp008'), runtimeNote),
    { status: 'missing', missingIds: ['exp008'] },
  )
  assert.deepEqual(
    selectRuntimeNoteBenchmark([...matching, matching.find((report) => report.short_id === 'exp026')], runtimeNote),
    { status: 'invalid', invalidSources: ['exp026'] },
  )
})

test('runtime note selector rejects invalid report and policy invariants independently', async () => {
  const { selectRuntimeNoteBenchmark, reports, runtimeNote } = await loadRuntimeFixture()
  const matching = reports.filter((report) => ['exp008', 'exp010', 'exp025', 'exp026'].includes(report.short_id))
  const cases = [
    ['wrong experiment ID', (report) => { report.meta.experiment_id = 'exp026_wrong' }],
    ['wrong condition', (report) => { report.meta.condition_name = 'wrong condition' }],
    ['wrong execution mode', (report) => { report.meta.execution_mode = 'subprocess' }],
    ['wrong report scope', (report) => { report.meta.report_scope = 'graded' }],
    ['invalid duration', (report) => { report.meta.duration = 'unknown' }],
    ['non-benchmark total', (report) => { report.summary.total_tasks = 50 }],
    ['invalid success count', (report) => { report.summary.success_count = 221 }],
    ['invalid success rate', (report) => { report.summary.success_rate_pct = 90.8 }],
    ['invalid error count', (report) => { report.summary.error_count = -1 }],
    ['success and error exceed total', (report) => { report.summary.error_count = 21 }],
    ['retried over total', (report) => { report.summary.retried_count = 221 }],
    ['invalid QA', (report) => { report.summary.avg_qa_score = Number.NaN }],
    ['round sum mismatch', (report) => { report.recovery_stats.resume_rounds.per_round['2'].still_failed = 19 }],
    ['retried count mismatch', (report) => { report.summary.retried_count = 104 }],
    ['null round', (report) => { report.recovery_stats.resume_rounds.per_round['1'] = null }],
    ['missing round', (report) => { delete report.recovery_stats.resume_rounds.per_round['2'] }],
    ['wrong round count', (report) => { report.recovery_stats.resume_rounds.rounds_used = 1 }],
  ]

  for (const [name, mutate] of cases) {
    const invalid = structuredClone(matching)
    mutate(invalid.find((report) => report.short_id === 'exp026'))
    assert.deepEqual(
      selectRuntimeNoteBenchmark(invalid, runtimeNote),
      { status: 'invalid', invalidSources: ['exp026'] },
      name,
    )
  }

  const invalidPolicy = structuredClone(runtimeNote)
  invalidPolicy.current_policy.step_timeout_minutes = 280
  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching, invalidPolicy),
    { status: 'invalid', invalidSources: ['runtime-note.json'] },
  )
  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching, null),
    { status: 'invalid', invalidSources: ['runtime-note.json'] },
  )
  const invalidHistory = structuredClone(runtimeNote)
  invalidHistory.incident.policy.step_timeout_minutes = 350
  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching, invalidHistory),
    { status: 'invalid', invalidSources: ['runtime-note.json'] },
  )
  const impossibleDate = structuredClone(runtimeNote)
  impossibleDate.incident.started_at = '2026-02-30T07:02:37Z'
  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching, impossibleDate),
    { status: 'invalid', invalidSources: ['runtime-note.json'] },
  )
  const reversedDates = structuredClone(runtimeNote)
  reversedDates.incident.started_at = '2026-05-18T13:02:37Z'
  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching, reversedDates),
    { status: 'invalid', invalidSources: ['runtime-note.json'] },
  )
  const invalidGenerated = structuredClone(runtimeNote)
  invalidGenerated._generated = '2026-02-30T00:00:00.000Z'
  assert.deepEqual(
    selectRuntimeNoteBenchmark(matching, invalidGenerated),
    { status: 'invalid', invalidSources: ['runtime-note.json'] },
  )
})

test('runtime article keeps reflective chapter rhythm without static chart values', async () => {
  const journal = await readRepoFile('src/data/journal.ts')
  const start = journal.indexOf("...journalCatalog['360-minute-experiment']")
  const end = journal.indexOf("...journalCatalog['honest-pipeline-lower-score']")
  const article = journal.slice(start, end)

  assert.match(article, /benchmark: \{ kind: 'runtime' \}/)
  assert.match(article, /readingStyle: 'reflective'/)
  assert.match(article, /metrics: \[\]/)
  assert.match(article, /data: \[\]/)
  assert.match(article, /label: '사건'[\s\S]*heading: '같은 220개, 서로 다른 시간'/)
  assert.match(article, /label: '편향'[\s\S]*heading: '빠른 작업만 남는 편향'/)
  assert.match(article, /label: '대응'[\s\S]*heading: 'Checkpoint, watchdog, relay'/)
  assert.match(article, /label: '결과'[\s\S]*heading: '복구가 만든 새로운 경계'/)
  assert.match(article, /label: '결정'[\s\S]*heading: '시간 제한도 실험 조건이다'/)
  assert.match(article, /benchmarkNarrative: 'runtime-incident'/)
  assert.match(article, /benchmarkNarrative: 'runtime-policy'/)
  assert.match(article, /benchmarkNarrative: 'runtime-results'/)
  assert.doesNotMatch(article, /primary: 78|secondary: 20|value: '360분'|value: '약 330분'/)

  const timelineEvent = journal.slice(
    journal.indexOf("title: '장시간 resume가 약 330분에 종료'") - 80,
    journal.indexOf("title: '장시간 resume가 약 330분에 종료'") + 180,
  )
  assert.match(timelineEvent, /date: '2026-05-18'/)
  assert.doesNotMatch(timelineEvent, /2026-05-17/)
})

test('runtime hero and article resolve visuals and prose from source data', async () => {
  const [hero, page] = await Promise.all([
    readRepoFile('src/components/notes/NoteHeroVisual.tsx'),
    readRepoFile('src/pages/JournalArticle.tsx'),
  ])
  const runtimeHero = hero.slice(hero.indexOf('function RuntimeVisual'), hero.indexOf('function IntegrityVisual'))

  assert.match(runtimeHero, /MAY 18 · INCIDENT/)
  assert.match(runtimeHero, /AFTER MAY 20 FIX/)
  assert.match(runtimeHero, /scaleX\(currentPolicy\.watchdog_minutes\)/)
  assert.match(runtimeHero, /incident\.approx_minute/)
  assert.match(runtimeHero, /incident\.policy\.step_timeout_minutes/)
  assert.match(runtimeHero, /currentPolicy\.step_timeout_minutes/)
  assert.match(runtimeHero, /currentPolicy\.job_timeout_minutes/)
  assert.doesNotMatch(runtimeHero, /value: '290'|value: '330'|value: '350'|value: '360'/)
  assert.match(page, /useRuntimeNote\(usesRuntimeBenchmark\)/)
  assert.match(page, /selectRuntimeNoteBenchmark\(reports, runtimeNote\)/)
  assert.match(page, /resolveRuntimeArticle\(article, readyRuntimeBenchmark\)/)
  assert.match(page, /usesRuntimeBenchmark && !readyRuntimeBenchmark[\s\S]*\? \[\]/)
  assert.match(page, /generated\/runtime-note\.json/)
  assert.match(page, /actions\/runs\/\$\{benchmark\.incident\.action_run_id\}/)
  assert.match(page, /blob\/\$\{benchmark\.incident\.workflow_commit\}/)
  assert.match(page, /commit\/\$\{benchmark\.incident\.fix\.commit\}/)
  assert.match(page, /blob\/\$\{benchmark\.incident\.source_record_commit\}\/CHANGELOG\.md/)
  assert.match(page, /space-y-20 md:space-y-28/)
  assert.match(page, /text-\[16px\]\/\[2\.05\]/)
  assert.match(page, /현재 workflow의 condition_a 경로/)
  assert.match(page, /exp008과 exp010은 이 수정 전에 실행됐으므로/)
  assert.match(page, /relay가 이어진 exp025·exp026에서는 한 job의 실행 시간과 같지 않다/)
})

test('exp026 requires Docker and never advertises local fallback', async () => {
  const config = await readRepoFile('batch-runner/experiments/exp026_sandbox_skills_multimodal.yaml')

  assert.match(config, /use_docker: "always"/)
  assert.match(config, /fails loudly if[\s\S]*container execution becomes unavailable/)
  assert.match(config, /does not fall back to local[\s\S]*subprocess execution/)
  assert.doesNotMatch(config, /graceful local fallback|gracefully falls back/)
})
