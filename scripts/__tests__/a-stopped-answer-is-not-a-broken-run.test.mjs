/**
 * A stopped answer is not a broken run.
 *
 * exp034 finished with eight failed tasks. Five recorded `rate_limited` — the
 * run could not get a call through to the deployment. Three recorded
 * `content_filtered` — the model was asked a real question and the provider
 * refused what it produced. Those are opposite findings: the first is a defect
 * in the run place, the second is a benchmark result.
 *
 * The dashboard showed neither. The only failure panel on the page is gated on
 * `task.error`, and the merge that would fill it reads `error_tasks[].error`,
 * a key none of the eight has — they carry `error_code` and `error_type`, which
 * name the exception class. So every one of the eight rendered as a red cross
 * with no reason, and a run whose calls were being throttled looked exactly
 * like a model that could not do the work.
 *
 * The 220-task run relays through the same path, so whatever it fails on lands
 * in the same silence unless the recorded category is read.
 *
 * What this pins:
 *   - the category is read from `observability.error_category`, checked rather
 *     than assumed, against the real exp034 corpus and not only fixtures;
 *   - `content_filtered` is called a benchmark result and `rate_limited` is
 *     not, which is the distinction `core/execution_errors.py` states;
 *   - nothing else is bucketed, because that file's vocabulary is open;
 *   - an absent category reads as "not recorded", never as a clean task;
 *   - an absent `task_results` array produces no count at all, rather than
 *     answering "0 failures" to a report whose detail never loaded;
 *   - a rate refusal shows which of the two limits it hit, from the closed set
 *     `core/codex_runner.py` is allowed to publish — the two have opposite
 *     fixes, so `rate_limited` alone does not say which knob to turn.
 */

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const readSource = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

/** Same helper as cost-read-layer.test.mjs: transpile a `.ts` and import it. */
async function importTypeScriptModule(path) {
  const source = await readSource(path)
  const result = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 },
    reportDiagnostics: true,
  })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

const {
  CONTENT_FILTERED,
  NO_REASON_RECORDED,
  RATE_LIMITED,
  RATE_LIMIT_KINDS,
  RATE_LIMIT_KIND_LABELS,
  isBenchmarkOutcome,
  readFailureCategory,
  readRateLimitKind,
  summariseFailures,
} = await importTypeScriptModule('src/lib/failureReason.ts')

const EXP034 = 'batch-runner/results/exp034_codex_foundry_trial30/report/report_data.json'

const task = (overrides = {}) => ({
  task_id: 't',
  status: 'error',
  ...overrides,
})
const failedWith = (category) => task({ observability: { error_category: category } })

// ── The recorded word ───────────────────────────────────────────────────────

test('the category comes off observability, where the backends put it', () => {
  assert.equal(readFailureCategory(failedWith('rate_limited')), 'rate_limited')
  assert.equal(readFailureCategory(failedWith(CONTENT_FILTERED)), CONTENT_FILTERED)
})

test('a category the report does not carry is null, not a guess', () => {
  assert.equal(readFailureCategory(task()), null)
  assert.equal(readFailureCategory(task({ observability: {} })), null)
  assert.equal(readFailureCategory(task({ observability: { error_category: null } })), null)
})

test('a field that exists and says nothing is the same as absent', () => {
  // A reader gains nothing from a blank, and rendering one would look like a
  // reason was shown when none was.
  assert.equal(readFailureCategory(failedWith('')), null)
  assert.equal(readFailureCategory(failedWith('   ')), null)
  assert.equal(readFailureCategory(failedWith('  timeout  ')), 'timeout')
})

test('a category of the wrong type is refused rather than stringified', () => {
  // `observability` is indexed as `unknown` and arrives from whatever the hub
  // returns. `String(42)` would render "42" as a cause.
  for (const wrong of [42, true, ['rate_limited'], { category: 'rate_limited' }]) {
    assert.equal(readFailureCategory(failedWith(wrong)), null)
  }
})

// ── The one claim ───────────────────────────────────────────────────────────

test('only a stopped answer is called a benchmark result', () => {
  assert.equal(isBenchmarkOutcome(CONTENT_FILTERED), true)
  // The whole point of the distinction: a throttled call is the run's defect,
  // and calling it a benchmark result would credit the benchmark with a
  // failure the model never had a chance to produce.
  assert.equal(isBenchmarkOutcome('rate_limited'), false)
  assert.equal(isBenchmarkOutcome(null), false)
})

test('no other category is sorted into a bucket', () => {
  // `classify_execution_error` has an open vocabulary, so a closed table here
  // would file every future category under whichever side was the default.
  const categories = [
    'timeout',
    'transport_error',
    'runtime_unavailable',
    'syntax_error',
    'out_of_memory',
    'execution_error',
    'a_category_invented_next_quarter',
  ]
  for (const category of categories) {
    assert.equal(isBenchmarkOutcome(category), false, category)
    // …and it still reads back verbatim, so it is shown rather than dropped.
    assert.equal(readFailureCategory(failedWith(category)), category)
  }
})

test('the category this page singles out is one the pipeline emits', () => {
  // Cross-language pin. If `core/execution_errors.py` renames the category, the
  // page would silently stop recognising the one failure it is required to
  // tell apart, and every content stop would read as an ordinary defect.
  return readSource('batch-runner/core/execution_errors.py').then((source) => {
    assert.ok(
      source.includes(`return "${CONTENT_FILTERED}"`),
      `core/execution_errors.py no longer returns "${CONTENT_FILTERED}"`,
    )
  })
})

// ── Counting ────────────────────────────────────────────────────────────────

test('a report with no task array is not a report with no failures', () => {
  // The index strips `task_results`, so this is the ordinary state of a report
  // whose per-task detail has not loaded yet.
  assert.equal(summariseFailures(undefined), null)
  assert.equal(summariseFailures(null), null)
  assert.equal(summariseFailures([]), null)
})

test('a loaded run with nothing failed counts zero, which is a measurement', () => {
  assert.deepEqual(summariseFailures([task({ status: 'success' })]), {
    failed: 0,
    byCategory: [],
    uncategorised: 0,
  })
})

test('failures are counted by the word the run used, commonest first', () => {
  const breakdown = summariseFailures([
    task({ status: 'success' }),
    failedWith('rate_limited'),
    failedWith(CONTENT_FILTERED),
    failedWith('rate_limited'),
    failedWith('timeout'),
    failedWith('rate_limited'),
    failedWith(CONTENT_FILTERED),
  ])
  assert.equal(breakdown.failed, 6)
  assert.deepEqual(breakdown.byCategory, [
    { category: 'rate_limited', count: 3 },
    { category: CONTENT_FILTERED, count: 2 },
    { category: 'timeout', count: 1 },
  ])
  assert.equal(breakdown.uncategorised, 0)
})

test('equal counts are ordered by name, so the row does not reshuffle', () => {
  const breakdown = summariseFailures([failedWith('timeout'), failedWith('rate_limited')])
  assert.deepEqual(breakdown.byCategory.map((row) => row.category), [
    'rate_limited',
    'timeout',
  ])
})

test('a failure with no category is counted apart, not dropped', () => {
  // Dropping it would make the categories sum to fewer than the failures, and
  // a reader who adds them up would conclude tasks went missing.
  const breakdown = summariseFailures([failedWith('rate_limited'), task(), task()])
  assert.equal(breakdown.failed, 3)
  assert.deepEqual(breakdown.byCategory, [{ category: 'rate_limited', count: 1 }])
  assert.equal(breakdown.uncategorised, 2)
  assert.equal(
    breakdown.byCategory.reduce((sum, row) => sum + row.count, 0) + breakdown.uncategorised,
    breakdown.failed,
  )
})

// ── Which of the two rate refusals ──────────────────────────────────────────

const refusedWith = (kind) =>
  task({ observability: { error_category: RATE_LIMITED, codex: { rate_limit_kind: kind } } })

test('the kind comes off observability.codex, where step 2 projects it', () => {
  assert.equal(readRateLimitKind(refusedWith('token')), 'token')
  assert.equal(readRateLimitKind(refusedWith('request')), 'request')
  assert.equal(readRateLimitKind(refusedWith('unattributed')), 'unattributed')
})

test('a word outside the closed set is dropped, not shown', () => {
  // The Python writer allow-lists this field precisely so the provider's
  // sentence — which names the deployment — cannot travel in it. Re-checking
  // on read means a value that somehow got past the writer is still not
  // rendered.
  for (const wrong of ['Your requests to gpt-5.4 have exceeded', 'tokens', '', 42, null, {}]) {
    assert.equal(readRateLimitKind(refusedWith(wrong)), null, String(wrong))
  }
})

test('a run from before the field has no kind, and that is not a guess', () => {
  // exp034's five refusals are exactly this state.
  assert.equal(readRateLimitKind(task({ observability: { error_category: RATE_LIMITED } })), null)
  assert.equal(readRateLimitKind(task({ observability: { codex: {} } })), null)
  assert.equal(readRateLimitKind(task()), null)
})

test('the three kinds match the closed set the runner may publish', async () => {
  // Cross-language pin. If the Python tuple gains a word, this page would drop
  // it as unrecognised and silently show nothing for a refusal it was told the
  // cause of.
  const source = await readSource('batch-runner/core/codex_runner.py')
  const match = source.match(/RATE_LIMIT_KINDS = \(([^)]*)\)/)
  assert.ok(match, 'core/codex_runner.py no longer declares RATE_LIMIT_KINDS')
  const python = [...match[1].matchAll(/"([^"]+)"/g)].map((entry) => entry[1])
  assert.deepEqual([...RATE_LIMIT_KINDS], python)
})

test('every kind has a label, including the one that names no limit', () => {
  // `unattributed` is a finding about the markers, not an empty slot, so it
  // gets a sentence rather than being left to render as a bare word.
  for (const kind of RATE_LIMIT_KINDS) {
    assert.equal(typeof RATE_LIMIT_KIND_LABELS[kind], 'string', kind)
    assert.ok(RATE_LIMIT_KIND_LABELS[kind].length > 0, kind)
  }
  assert.equal(Object.keys(RATE_LIMIT_KIND_LABELS).length, RATE_LIMIT_KINDS.length)
})

test('the two readable kinds point at opposite fixes', () => {
  // The distinction is only worth carrying if the words differ in what to do.
  assert.notEqual(RATE_LIMIT_KIND_LABELS.token, RATE_LIMIT_KIND_LABELS.request)
  assert.match(RATE_LIMIT_KIND_LABELS.token, /토큰/)
  assert.match(RATE_LIMIT_KIND_LABELS.request, /자주|드물게/)
})

// ── The corpus this was found in ────────────────────────────────────────────

test('exp034 reads back as five throttled calls and three stopped answers', async () => {
  const report = JSON.parse(await readSource(EXP034))
  const breakdown = summariseFailures(report.task_results)

  assert.equal(report.task_results.length, 30)
  assert.equal(breakdown.failed, 8)
  assert.deepEqual(breakdown.byCategory, [
    { category: 'rate_limited', count: 5 },
    { category: CONTENT_FILTERED, count: 3 },
  ])
  assert.equal(breakdown.uncategorised, 0)

  // The gate that kept all eight off the page: not one carries the free-text
  // `error` the old panel required, so the reason had to come from elsewhere.
  const failed = report.task_results.filter((entry) => entry.status === 'error')
  assert.equal(failed.length, 8)
  assert.deepEqual(failed.filter((entry) => entry.error).map((entry) => entry.task_id), [])
  for (const entry of failed) {
    assert.notEqual(readFailureCategory(entry), null, entry.task_id)
  }

  // And what exp034 still cannot say. Its five refusals ran before
  // `rate_limit_kind` existed, through an error identity documented to carry no
  // message, so which of the two limits was hit is not recoverable from this
  // artifact at any price. The next run records it; this one is pinned as
  // absent so a later reader does not mistake the blank for a bug in the page.
  const refused = failed.filter((entry) => readFailureCategory(entry) === RATE_LIMITED)
  assert.equal(refused.length, 5)
  for (const entry of refused) {
    assert.equal(readRateLimitKind(entry), null, entry.task_id)
  }
})

test('the note for an unrecorded reason says unrecorded, not unknown', () => {
  // "알 수 없음" would read as a run that looked and could not tell. Nothing
  // looked.
  assert.match(NO_REASON_RECORDED, /기록/)
})
