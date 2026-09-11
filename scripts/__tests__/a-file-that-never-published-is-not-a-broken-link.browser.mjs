/**
 * Deliverable file links on a run that never uploaded, checked in a browser.
 *
 * The task modal has always rendered every deliverable as a green "↓ Open"
 * pointing at `HyeonSang/<experiment_id>/resolve/main/<path>`. That dataset is
 * created by step 7, and a `dry_run` dispatch skips step 7 — so for such a run
 * the dataset does not exist and every one of those links is a 404. Measured
 * against the real hub before this file was written:
 *
 *   404  HyeonSang/exp034_codex_foundry_trial30/resolve/main/deliverable_files/…/soap_note_cs_2024-03-01.md
 *   404  HyeonSang/exp034_codex_foundry_trial30/resolve/main/self_report.json
 *
 * exp034 lists 107 of them across 22 of its 30 tasks. The self-report half of
 * that was fixed by serving the payload from this build; the files cannot be —
 * they are megabytes of .wav and .pdf living only in the workflow artifact, and
 * committing them is not a route. So the fix is to stop claiming a route
 * exists. A dead download link reads as "this run produced nothing"; the files
 * were produced, and the page has to say which of those two it means.
 *
 * Three states, and this file exists to keep them apart:
 *
 *   step7_upload_requested   a link. The dataset was asked for.
 *   dry_run_no_step7         a filename and a note. No dataset, no URL.
 *   (field absent)           a link. The v1 reports fetched from the hub
 *                            predate the field — "does not say" is not
 *                            "did not publish", and 26 published runs are in
 *                            exactly that state.
 *
 * Every payload here is synthetic and served by route interception, so no
 * request leaves for HuggingFace and no model is called.
 */

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)

/** Must match DELIVERABLES_NOT_PUBLISHED_NOTE in src/pages/ExperimentDetail.tsx. */
const NOT_PUBLISHED_NOTE =
  '이 실행은 허브에 올리지 않았습니다 — 파일은 실행 아티팩트에 있고 내려받을 주소가 없습니다'
/** Must match HF_BASE in src/hooks/useReports.ts. */
const HF_BASE = 'https://huggingface.co/datasets/HyeonSang'

const SHORT_ID = 'exp027'
const REPORTS_INDEX_GLOB = '**/generated/reports-index.json*'
const REPORT_GLOB = '**/resolve/main/self_report.json*'
const GRADES_GLOB = '**/generated/grades-index.json*'

/**
 * Nested, spaced, and extensioned on purpose.
 *
 * The unlinked branch has to reduce a path to a filename the same way the link
 * branch does — `relPath.split('/').pop()` — and a flat `a.xlsx` fixture would
 * pass whether it did or not. These are the shapes exp034 actually recorded.
 */
const FILES = [
  'deliverable_files/t-files/ECID Board Meeting Talking Points.pdf',
  'deliverable_files/t-files/stems/Deja Vu - Bass Stem.wav',
  'deliverable_files/t-files/generate_ecid_pdfs.py',
]
const FILENAMES = FILES.map((path) => path.split('/').pop())

/** A reference file is hosted by the base dataset, which exists either way. */
const REFERENCE_URL =
  'https://huggingface.co/datasets/openai/gdpval/resolve/main/reference_files/brief.pdf'

const task = (taskId, { deliverables, references = [] }) => ({
  task_id: taskId,
  sector: 'Finance',
  occupation: 'Accountant',
  status: 'success',
  success: true,
  retried: false,
  files_count: deliverables.length,
  qa_score: 9,
  qa_passed: true,
  qa_issues: [],
  qa_suggestion: '',
  latency_ms: 42_000,
  instruction: `${taskId} instruction`,
  deliverable_files: deliverables,
  reference_file_urls: references,
})

const payload = () => ({
  short_id: SHORT_ID,
  task_results: [
    task('t-files', { deliverables: FILES, references: [REFERENCE_URL] }),
    task('t-nofiles', { deliverables: [] }),
  ],
})

// ── Assertions ──────────────────────────────────────────────────────────────

const section = (page) => page.locator('[data-testid="deliverable-files"]')

async function openTask(page, taskId) {
  // The modal's own backdrop covers the table, so a second open on the same
  // page load would time out clicking through it rather than reporting
  // anything about deliverables.
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

/** Every file is named, whichever branch rendered it. Nothing may be hidden. */
async function assertAllFilesNamed(page, label) {
  const text = await section(page).innerText()
  // Case-insensitive: the header carries `uppercase`, so `innerText` reads it
  // back as the browser paints it, not as the source spells it.
  assert.match(text, /📦 Deliverable Files \(3\)/i, label)
  for (const filename of FILENAMES) {
    assert.ok(text.includes(filename), `${label}: ${filename} is not on screen`)
  }
}

async function assertLinked(page, experimentId, label) {
  await assertAllFilesNamed(page, label)

  const links = section(page).locator('a')
  assert.equal(await links.count(), FILES.length, `${label}: wrong link count`)
  const hrefs = await links.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('href')))
  assert.deepEqual(
    hrefs,
    FILES.map((path) => `${HF_BASE}/${experimentId}/resolve/main/${path}`),
    `${label}: link targets`,
  )

  assert.equal(
    await page.locator('[data-testid="deliverables-not-published"]').count(),
    0,
    `${label}: a run that uploaded must not carry the "not published" note`,
  )
  assert.doesNotMatch(await section(page).innerText(), /기록됨/, label)
}

async function assertUnlinked(page, label) {
  await assertAllFilesNamed(page, label)

  // The whole point: not one anchor in this section, so nothing offers a
  // download that would 404.
  assert.equal(
    await section(page).locator('a').count(),
    0,
    `${label}: a run that never uploaded must offer no download link`,
  )
  assert.equal(
    await section(page).locator('[href]').count(),
    0,
    `${label}: no element in the section may carry an href`,
  )

  const unlinked = section(page).locator('[data-deliverable-unlinked]')
  assert.equal(await unlinked.count(), FILES.length, `${label}: wrong row count`)
  assert.deepEqual(
    await unlinked.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute('data-deliverable-unlinked')),
    ),
    FILENAMES,
    `${label}: rows must name the file, not the path`,
  )

  const note = page.locator('[data-testid="deliverables-not-published"]')
  assert.equal(await note.count(), 1, `${label}: missing the note`)
  assert.equal((await note.innerText()).trim(), NOT_PUBLISHED_NOTE, `${label}: note text`)
}

/**
 * The reference files are a different dataset — `openai/gdpval` — and it is
 * there whether or not this run published. Withdrawing those links too would
 * be the same mistake in the other direction.
 */
async function assertReferenceLinksSurvive(page, label) {
  const reference = page.locator(`a[href="${REFERENCE_URL}"]`)
  assert.equal(await reference.count(), 1, `${label}: the reference file link was withdrawn`)
}

/** A task with no deliverables renders no section at all, as it always has. */
async function assertNoSectionWithoutFiles(page, label) {
  assert.equal(await section(page).count(), 0, `${label}: empty list must render nothing`)
}

// ── Run ─────────────────────────────────────────────────────────────────────

async function main() {
  const reportsIndex = JSON.parse(await readFile(reportsPath, 'utf8'))
  const entry = reportsIndex.reports.find((report) => report.short_id === SHORT_ID)
  if (!entry) throw new Error(`reports-index.json has no ${SHORT_ID} entry`)
  const experimentId = entry.meta.experiment_id

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

  // `publication_plan` reaches the page on the *index entry*, not the fetched
  // payload: `applyReportIndexSnapshot` spreads the entry over the report and
  // the entry wins on every key it carries, `meta` included. Serving it only on
  // the fetch would test a path production never takes.
  const served = { plan: undefined }
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
    if (served.plan === undefined) delete target.meta.publication_plan
    else target.meta.publication_plan = served.plan
    route.fulfill({ json: index })
  })

  const load = async (plan) => {
    served.plan = plan
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
  }

  try {
    await load('step7_upload_requested')
    await openTask(page, 't-files')
    await assertLinked(page, experimentId, 'step7_upload_requested')
    await assertReferenceLinksSurvive(page, 'step7_upload_requested')

    await load('dry_run_no_step7')
    await openTask(page, 't-files')
    await assertUnlinked(page, 'dry_run_no_step7')
    await assertReferenceLinksSurvive(page, 'dry_run_no_step7')

    await openTask(page, 't-nofiles')
    await assertNoSectionWithoutFiles(page, 'dry_run_no_step7, no deliverables')

    await load(undefined)
    await openTask(page, 't-files')
    await assertLinked(page, experimentId, 'no publication_plan (v1 report)')

    assert.deepEqual(consoleErrors, [], 'the page logged errors')
  } finally {
    await context.close()
    await browser.close()
    await server.close()
  }

  console.log('✓ a file that never published is not a broken link')
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
