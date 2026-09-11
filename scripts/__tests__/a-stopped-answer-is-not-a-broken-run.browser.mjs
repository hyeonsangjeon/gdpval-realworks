/**
 * A failed task's reason, checked in a browser.
 *
 * The page had one failure panel and it was gated on `task.error`, a free-text
 * string merged in from `error_tasks[].error`. exp034's eight failed tasks have
 * no such key — they carry `error_code: "task_execution_error"` and
 * `error_type: "TaskExecutionError"` — so the gate was false, the panel never
 * mounted, and all eight rendered as a red cross with zero files and nothing
 * else. Five of them had recorded `rate_limited` and three `content_filtered`.
 *
 * A unit test would not have found that: the reading logic was never wrong,
 * there simply was no path from the recorded value to the screen. So this runs
 * the real page.
 *
 * What it holds:
 *   - a failed task always shows a reason panel, even when the run recorded no
 *     category — "not recorded" is a state, and silence is not;
 *   - `content_filtered` is marked as a benchmark result, because the model was
 *     asked a real question and what it produced was refused;
 *   - `rate_limited` is not marked that way, because nothing about the model was
 *     learned from a call that never landed;
 *   - a refusal that recorded which of the two limits it hit says so, and one
 *     that did not stays blank rather than borrowing an answer;
 *   - a successful task grows no panel;
 *   - the run-level row counts by the recorded word and keeps uncategorised
 *     failures visible, so the chips plus the unrecorded count reconcile to the
 *     failure total.
 *
 * Every payload is synthetic and served by route interception: no request
 * leaves for HuggingFace and no model is called.
 */

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)

/** All three must match src/lib/failureReason.ts. */
const CONTENT_FILTERED_NOTE =
  '제공자가 모델이 낸 답을 내용 때문에 막았습니다. 벤치마크 결과이며 실행 환경 결함이 아닙니다.'
const NO_REASON_RECORDED = '이 실행은 실패 원인을 기록하지 않았습니다'
const REASON_IS_VERBATIM_NOTE = '실행이 기록한 값 그대로입니다'

const SHORT_ID = 'exp027'
const REPORTS_INDEX_GLOB = '**/generated/reports-index.json*'
const REPORT_GLOB = '**/resolve/main/self_report.json*'
const GRADES_GLOB = '**/generated/grades-index.json*'

const task = (taskId, { status, category, error, kind } = {}) => ({
  task_id: taskId,
  sector: 'Finance',
  occupation: 'Accountant',
  status,
  retried: false,
  files_count: 0,
  qa_score: status === 'success' ? 9 : null,
  qa_passed: status === 'success' ? true : null,
  qa_issues: [],
  qa_suggestion: '',
  latency_ms: 42_000,
  instruction: `${taskId} instruction`,
  deliverable_files: [],
  reference_file_urls: [],
  ...(error ? { error } : {}),
  // Exactly where the backends put it, and exactly the shape exp034 has: a
  // sibling of `codex`, not a top-level task field. `rate_limit_kind` goes
  // one level deeper, inside `codex`, where step 2 projects it.
  ...(category
    ? {
        observability: {
          codex: { items_seen: 7, ...(kind ? { rate_limit_kind: kind } : {}) },
          error_category: category,
        },
      }
    : {}),
})

/**
 * Two `rate_limited` so the counting is a count and not a relabelling, one
 * `content_filtered` so the two classes appear together, and one failure with
 * no `observability` at all — the state every v1 report's failures are in.
 *
 * The two refusals differ in one thing only: `t-rate-one` records which limit
 * it hit and `t-rate-two` does not. That is the difference between a run after
 * PR #533 and exp034, and both have to render correctly on the same page.
 */
const payload = () => ({
  short_id: SHORT_ID,
  task_results: [
    task('t-ok', { status: 'success' }),
    task('t-filtered', { status: 'error', category: 'content_filtered' }),
    task('t-rate-one', { status: 'error', category: 'rate_limited', kind: 'token' }),
    task('t-rate-two', { status: 'error', category: 'rate_limited' }),
    task('t-silent', { status: 'error' }),
    // A category *and* free text. The old panel's content must survive beside
    // the new one rather than be replaced by it.
    task('t-verbose', {
      status: 'error',
      category: 'timeout',
      error: 'TimeoutError: turn exceeded 900s',
    }),
  ],
})

// ── Assertions ──────────────────────────────────────────────────────────────

const panel = (page) => page.locator('[data-testid="failure-reason"]')

async function openTask(page, taskId) {
  // An open modal's backdrop covers the table, so a second open on the same
  // page load would time out clicking through it.
  const close = page.locator('[data-testid="task-modal-close"]')
  if (await close.count()) {
    await close.click()
    await close.waitFor({ state: 'detached' })
  }
  await page
    .locator('tbody tr')
    .filter({ has: page.locator('td[data-cost-field]') })
    .filter({ hasText: taskId })
    .first()
    .click()
  await page.locator('[data-testid="task-cost"]').waitFor()
}

async function assertReason(page, taskId, { category, benchmarkOutcome, kind = null }) {
  await openTask(page, taskId)
  await panel(page).waitFor()

  assert.equal(
    await panel(page).getAttribute('data-failure-category'),
    category ?? '',
    `${taskId}: recorded category`,
  )

  const text = await panel(page).innerText()
  if (category) {
    assert.ok(text.includes(category), `${taskId}: "${category}" is not on screen`)
    assert.ok(!text.includes(NO_REASON_RECORDED), `${taskId}: claimed nothing was recorded`)
  } else {
    assert.ok(text.includes(NO_REASON_RECORDED), `${taskId}: missing the unrecorded note`)
    assert.equal(
      await page.locator('[data-testid="failure-reason-unrecorded"]').count(),
      1,
      `${taskId}: unrecorded marker`,
    )
  }

  // Which limit was hit, when the run got far enough to be told.
  const kindNode = page.locator('[data-testid="rate-limit-kind"]')
  assert.equal(await kindNode.count(), kind ? 1 : 0, `${taskId}: rate-limit kind presence`)
  if (kind) {
    assert.equal(await kindNode.getAttribute('data-rate-limit-kind'), kind, `${taskId}: kind`)
    const kindText = await kindNode.innerText()
    assert.ok(kindText.includes(kind), `${taskId}: the recorded word is not shown`)
    // The label has to say what to do about it, or the word alone is no more
    // actionable than `rate_limited` was.
    assert.ok(kindText.length > kind.length + 4, `${taskId}: kind shown without its meaning`)
  }

  const benchmarkNote = page.locator('[data-testid="failure-is-benchmark-outcome"]')
  assert.equal(
    await benchmarkNote.count(),
    benchmarkOutcome ? 1 : 0,
    `${taskId}: benchmark-result note should${benchmarkOutcome ? '' : ' not'} be there`,
  )
  if (benchmarkOutcome) {
    assert.equal((await benchmarkNote.innerText()).trim(), CONTENT_FILTERED_NOTE, `${taskId}: note`)
  } else if (category) {
    assert.ok(text.includes(REASON_IS_VERBATIM_NOTE), `${taskId}: missing the verbatim note`)
  }
}

async function assertNoPanel(page, taskId) {
  await openTask(page, taskId)
  await page.locator('[data-testid="task-cost"]').waitFor()
  assert.equal(await panel(page).count(), 0, `${taskId}: a finished task has no failure panel`)
}

async function assertBreakdown(page) {
  const row = page.locator('[data-testid="failure-breakdown"]')
  await row.waitFor()

  const text = await row.innerText()
  assert.ok(text.includes('실패 5건'), `breakdown counts wrong: ${text}`)

  const chips = row.locator('[data-failure-category]')
  assert.deepEqual(
    await chips.evaluateAll((nodes) =>
      nodes.map((node) => [
        node.getAttribute('data-failure-category'),
        Number(node.getAttribute('data-failure-count')),
      ]),
    ),
    // Commonest first, then by name — a stable order, so the row does not
    // reshuffle between two runs that failed the same way.
    [
      ['rate_limited', 2],
      ['content_filtered', 1],
      ['timeout', 1],
    ],
    'breakdown chips',
  )

  const unrecorded = row.locator('[data-failure-uncategorised]')
  assert.equal(await unrecorded.count(), 1, 'the uncategorised failure must stay visible')
  assert.equal(await unrecorded.getAttribute('data-failure-uncategorised'), '1')

  // The chips and the unrecorded count must reconcile to the total, or a reader
  // adding them up concludes tasks went missing.
  const counted = await chips.evaluateAll((nodes) =>
    nodes.reduce((sum, node) => sum + Number(node.getAttribute('data-failure-count')), 0),
  )
  assert.equal(counted + 1, 5, 'categories plus unrecorded must equal the failure count')
}

// ── Run ─────────────────────────────────────────────────────────────────────

async function main() {
  const reportsIndex = JSON.parse(await readFile(reportsPath, 'utf8'))
  if (!reportsIndex.reports.some((report) => report.short_id === SHORT_ID)) {
    throw new Error(`reports-index.json has no ${SHORT_ID} entry`)
  }

  const server = await preview({
    root: ROOT,
    preview: { host: '127.0.0.1', port: 0 },
    logLevel: 'silent',
  })
  const address = server.httpServer.address()
  if (!address || typeof address === 'string') {
    throw new Error('Vite preview did not expose a TCP port')
  }
  const base = `http://127.0.0.1:${address.port}/gdpval-realworks`

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  })
  const page = await context.newPage()

  const consoleErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await page.route(REPORT_GLOB, (route) =>
    route.fulfill({
      status: 200,
      // A fulfilled cross-origin response still faces the browser's CORS check.
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
      body: JSON.stringify(payload()),
    }),
  )
  await page.route(GRADES_GLOB, (route) => route.fulfill({ json: [] }))
  await page.route(REPORTS_INDEX_GLOB, (route) => {
    const index = JSON.parse(JSON.stringify(reportsIndex))
    const target = index.reports.find((report) => report.short_id === SHORT_ID)
    delete target.served_locally
    route.fulfill({ json: index })
  })

  try {
    await page.goto(`${base}/experiments/${SHORT_ID}`)
    const boundary = page.locator('[data-testid="error-boundary"]')
    const quiet = (promise) => promise.catch(() => {})
    await Promise.race([
      quiet(page.locator('[data-testid="cost-summary"]').waitFor()),
      quiet(boundary.waitFor()),
    ])
    if (await boundary.count()) {
      throw new Error(`the error boundary replaced the page: ${await boundary.innerText()}`)
    }
    await page.locator('[data-testid="cost-summary"]').waitFor()

    await assertBreakdown(page)

    await assertReason(page, 't-filtered', {
      category: 'content_filtered',
      benchmarkOutcome: true,
    })
    await assertReason(page, 't-rate-one', {
      category: 'rate_limited',
      benchmarkOutcome: false,
      kind: 'token',
    })
    // Same category, no kind: a refusal from before the field existed must not
    // borrow the previous task's answer or invent one.
    await assertReason(page, 't-rate-two', { category: 'rate_limited', benchmarkOutcome: false })
    await assertReason(page, 't-silent', { category: null, benchmarkOutcome: false })

    await assertReason(page, 't-verbose', { category: 'timeout', benchmarkOutcome: false })
    assert.ok(
      (await panel(page).innerText()).includes('TimeoutError: turn exceeded 900s'),
      'the free-text error must survive beside the recorded category',
    )

    await assertNoPanel(page, 't-ok')

    assert.deepEqual(consoleErrors, [], 'the page logged errors')
  } finally {
    await context.close()
    await browser.close()
    await server.close()
  }

  console.log('✓ a stopped answer is not a broken run')
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
