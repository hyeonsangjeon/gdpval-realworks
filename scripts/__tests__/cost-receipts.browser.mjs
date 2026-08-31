/**
 * Per-task cost receipts, checked in a real browser.
 *
 * The five states this suite exists to keep apart:
 *
 *   $0.0400    a recorded amount. Priced, complete, and that is the figure.
 *   $0.0000    a recorded zero. Priced, complete, and free.
 *   기록 없음   no receipt. Nobody knows what it cost. NOT zero.
 *   미확정      a receipt that could not be priced, or only partly priced.
 *   미채점      the work never happened, so there is nothing to price. The
 *              solve side spells the same state 미실행.
 *
 * The first two are one state in the code and two different claims on the
 * page, so both are asserted: "it was free" and "it cost this much" are not
 * interchangeable, and neither may drift into 기록 없음.
 *
 * Every fixture here is synthetic and every summary is computed by the real
 * `summarizeCostReceipts`, so the run also proves the aggregator and the
 * dashboard agree on the same numbers. Both payload routes are installed
 * before the first navigation: no request ever leaves for HuggingFace, and no
 * model or judge is called.
 */

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'
import { preview } from 'vite'

import {
  COST_CURRENCY,
  COST_RECEIPT_SCHEMA_VERSION,
  projectCostReceipt,
  summarizeCostReceipts,
} from '../cost-receipt.mjs'

const ROOT = fileURLToPath(new URL('../..', import.meta.url))
const reportsPath = new URL('../../public/generated/reports-index.json', import.meta.url)

/** Must match COST_ESTIMATE_NOTE in src/lib/cost.ts. */
const ESTIMATE_NOTE = '사용량 기준 예상 비용이며 Azure 청구서 금액이 아님'
const SHORT_ID = 'exp027'
const GRADES_GLOB = '**/generated/grades-index.json*'
const REPORT_GLOB = '**/resolve/main/self_report.json*'
const PRICE_TABLE_SHA = '9f'.repeat(32)
const LEDGER_SHA = 'ab'.repeat(32)

const usd = (value) => `$${value.toFixed(4)}`
const literal = (value) => new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
/** Micro-dollars, so 0.25 − 0.01 never reaches an assertion as 0.24000000000000002. */
const money = (value) => Number(value.toFixed(6))

// ── Fixture builders ────────────────────────────────────────────────────────
//
// Everything below is in the shape batch-runner/core/cost_receipts.py writes,
// not the shape the dashboard reads. The two differ, and the difference is the
// point: the producer fills every money field on every status, so a step that
// recorded nothing still emits `0.0`. `scenario()` runs these through the real
// projector, which is what turns that placeholder into "no record" — a fixture
// pre-written in the read shape would skip the conversion it exists to prove.

/**
 * One receipt line: what one stage, at one retry kind, cost.
 *
 * There is no per-line estimate. The producer puts an estimate on the receipt
 * and nowhere else, so a line only ever reports what was confirmed.
 */
function component(stage, amount, { status = 'complete', retryKind = 'none' } = {}) {
  const measured = status === 'complete' || status === 'partial'
  return {
    // Derived at the producer: first work carries its stage's name, anything
    // that had to be done again is `retry`. The stage travels beside it, which
    // is what keeps two stages that each retried from reading as one line.
    name: retryKind === 'none' ? stage : 'retry',
    stage,
    retry_kind: retryKind,
    status,
    known_cost_usd: amount ?? 0,
    model_calls: measured ? 1 : 0,
    usage: measured ? { input_tokens: 1200, output_tokens: 340 } : {},
    missing_reasons: measured || status === 'not_run' ? [] : ['usage_absent'],
  }
}

function receipt({ status, known = 0, runtime = 0, components = [], missing = [] }) {
  return {
    schema_version: COST_RECEIPT_SCHEMA_VERSION,
    currency: COST_CURRENCY,
    status,
    // Derived from status at the producer, never stored: only a complete
    // receipt names a total, and there it equals known_cost_usd exactly.
    estimated_cost_usd: status === 'complete' ? money(known) : null,
    known_cost_usd: money(known),
    model_cost_usd: money(known - runtime),
    // A Decimal that starts at zero and sums the sandbox rows, so a task that
    // never opened one reports 0 rather than absence.
    runtime_cost_usd: money(runtime),
    model_calls: components.reduce((sum, line) => sum + line.model_calls, 0),
    usage: {},
    components,
    price_table_sha256: PRICE_TABLE_SHA,
    missing_reasons: missing,
  }
}

/** A complete receipt for a single amount, priced entirely as generation. */
const flat = (amount) =>
  receipt({
    status: 'complete',
    known: amount,
    components: [component('generation', amount)],
  })

function task(taskId, { sector, occupation, status = 'success', cost = null }) {
  return {
    task_id: taskId,
    sector,
    occupation,
    status,
    success: status === 'success',
    retried: false,
    files_count: status === 'success' ? 1 : 0,
    qa_score: status === 'success' ? 9 : null,
    qa_passed: status === 'success',
    qa_issues: [],
    qa_suggestion: '',
    latency_ms: 42_000,
    instruction: `${taskId} instruction`,
    deliverable_files: status === 'success' ? [`${taskId}.xlsx`] : [],
    ...(cost === null ? {} : { problem_solving_cost: cost }),
  }
}

/**
 * Build the pair of payloads one page load needs.
 *
 * Rows carry both receipts side by side so the fixture reads like the thing
 * being tested: what a task cost to solve, and what it cost to grade. A row
 * with `graded: false` is left out of the grade payload entirely — that is the
 * difference between 미채점 and 기록 없음, and it only exists in this shape.
 */
function scenario(rows, { experimentId, successfulDeliverables }) {
  const succeeded = (row) => (row.status ?? 'success') === 'success'

  // Both payloads are written by a projector in production — step 6 on the
  // Python side, aggregate-grades.mjs on this one — so the fixtures go through
  // the same one here. What the page receives is then exactly what it receives
  // in a real run, with the producer's placeholder zeros already resolved.
  const priced = rows.map((row) => ({
    ...row,
    solve: projectCostReceipt(row.solve ?? null, `${row.id} problem_solving_cost`),
    grade: projectCostReceipt(row.grade ?? null, `${row.id} grading_cost`),
  }))

  const solveSummary = summarizeCostReceipts(
    priced.map((row) => ({ receipt: row.solve, succeeded: succeeded(row) })),
    { successfulDeliverables },
  )
  const gradedRows = priced.filter((row) => row.graded !== false)
  const gradeSummary = summarizeCostReceipts(
    gradedRows.map((row) => ({ receipt: row.grade, succeeded: succeeded(row) })),
    { successfulDeliverables },
  )

  const report = {
    short_id: SHORT_ID,
    task_results: priced.map((row) =>
      task(row.id, {
        sector: row.sector,
        occupation: row.occupation,
        status: row.status ?? 'success',
        cost: row.solve,
      }),
    ),
    ...(solveSummary
      ? {
          cost_summary: { problem_solving_cost: solveSummary },
          cost_ledger: { path: 'cost_ledger.jsonl', sha256: LEDGER_SHA },
        }
      : {}),
  }

  const grade = {
    id: `${experimentId}__cost_fixture`,
    experiment_id: experimentId,
    grade_status: 'graded_v1',
    schema_version: '1.4',
    is_dummy: false,
    label: 'cost fixture',
    model: 'fixture-model',
    inference_model: 'fixture-model',
    judge_model: 'fixture-judge',
    dataset_url: null,
    summary: {
      total_tasks: gradedRows.length,
      graded_tasks: gradedRows.length,
      error_tasks: 0,
      avg_score_pct: 70,
      ci_pct: null,
      perfect_score: 0,
      partial_score: gradedRows.length,
      zero_score: 0,
      inconsistent_grades: 0,
    },
    coverage: { grade_tasks: gradedRows.length, corpus_tasks: rows.length, is_partial_corpus: false },
    tasks: gradedRows.map((row) => ({
      task_id: row.id,
      num_grades: 1,
      scores: [7],
      avg_score: 7,
      error: false,
      error_messages: [],
      ...(row.grade ? { grading_cost: row.grade } : {}),
    })),
    ...(gradeSummary
      ? {
          cost_summary: { grading_cost: gradeSummary },
          cost_ledger: { path: 'grading_cost_ledger.jsonl', sha256: LEDGER_SHA },
        }
      : {}),
  }

  return { report, grade, solveSummary, gradeSummary }
}

// ── DOM readers ─────────────────────────────────────────────────────────────

async function readCell(locator) {
  return {
    text: (await locator.innerText()).trim(),
    state: await locator.getAttribute('data-cost-state'),
    title: await locator.getAttribute('title'),
  }
}

/** The task table is the only one carrying cost cells; the page has four. */
const taskRow = (page, taskId) =>
  page
    .locator('tbody tr')
    .filter({ has: page.locator('td[data-cost-field]') })
    .filter({ hasText: taskId })

const tableCell = (page, taskId, field) =>
  taskRow(page, taskId).locator(`td[data-cost-field="${field}"]`)

const summaryColumn = (page, field) => page.locator(`[data-cost-summary-field="${field}"]`)

const summaryStat = (page, field, label) =>
  summaryColumn(page, field).locator(`[data-cost-stat="${label}"]`)

/** Component rows are addressed per field: one slug can appear under both. */
const modalComponent = (modal, field, slug) =>
  modal.locator(`[data-cost-components="${field}"] [data-cost-component="${slug}"]`)

async function openTask(page, taskId) {
  await taskRow(page, taskId).click()
  const modal = page.locator('[data-testid="task-cost"]')
  await modal.waitFor()
  return modal
}

// ── Scenarios ───────────────────────────────────────────────────────────────

/**
 * Every solving cost priced: a real zero, a failed task that still cost money.
 *
 * The grading half is deliberately not: `t-zero` was graded and the judge
 * recorded nothing, which is the only way to test 기록 없음 against 미채점. So
 * this scenario also carries the contrast between a field whose every row has
 * a receipt and a field with a hole in it.
 */
const fullyPricedRows = () => [
  {
    id: 't-complete',
    sector: 'Finance',
    occupation: 'Accountant',
    solve: receipt({
      status: 'complete',
      known: 0.25,
      // Charged for the sandbox, and charged once. It is not among the
      // component lines below — those are model calls — so it is the one
      // amount the breakdown would otherwise fail to account for.
      runtime: 0.01,
      components: [
        component('generation', 0.2),
        component('self_qa', 0.03),
        // A retry belongs to the stage that retried. It displays as 재시도;
        // the stage is what says which one.
        component('generation', 0.01, { retryKind: 'semantic' }),
      ],
    }),
    grade: receipt({
      status: 'complete',
      known: 0.12,
      components: [component('grading', 0.1), component('perception', 0.02)],
    }),
  },
  // Graded, but the judge recorded no cost: 기록 없음, not $0.
  { id: 't-zero', sector: 'Health', occupation: 'Nurse', solve: flat(0) },
  // Never graded at all: 미채점.
  { id: 't-cheap', sector: 'Retail', occupation: 'Buyer', solve: flat(0.05), graded: false },
  // Failed work still costs money and still shows up.
  {
    id: 't-failed',
    sector: 'Legal',
    occupation: 'Paralegal',
    status: 'error',
    solve: flat(0.04),
    grade: flat(0.01),
  },
]

/** A run where something went unpriced, so no headline can be a total. */
const mixedRows = () => [
  {
    id: 't-complete',
    sector: 'Finance',
    occupation: 'Accountant',
    solve: flat(0.25),
    grade: receipt({ status: 'unavailable', missing: ['judge_usage_missing'] }),
  },
  {
    id: 't-partial',
    sector: 'Health',
    occupation: 'Nurse',
    // A sandbox ran and could not be priced. Nothing was charged for it, so
    // there is no runtime amount — the receipt says so as `partial` plus a
    // reason code, which is a different claim from "the sandbox was free".
    solve: receipt({
      status: 'partial',
      known: 0.1,
      missing: ['runtime_cost_unpriced'],
      components: [
        component('generation', 0.1),
        component('self_qa', null, { status: 'not_run' }),
      ],
    }),
    grade: receipt({
      status: 'complete',
      known: 0.02,
      runtime: 0.005,
      components: [component('grading', 0.015)],
    }),
  },
  {
    id: 't-unpriced',
    sector: 'Retail',
    occupation: 'Buyer',
    solve: receipt({ status: 'unavailable', missing: ['price_missing'] }),
  },
]

/**
 * The shape the exp026c cost smoke produced: paid work nobody could price.
 *
 * Run 33302056462 made two paid model calls against `gpt-5.4-2026-03-05`, a
 * snapshot the price table has no entry for. Every amount came back a
 * placeholder zero and the projector nulled all of them, exactly as it should.
 * A run in that state has spent money and knows it; what it does not know is
 * how much. Beside it sits a task that never started, which is the one thing
 * here that genuinely cost nothing.
 *
 * No other scenario reaches this state. `mixedRows` has an unpriced receipt,
 * but an amount still survives elsewhere in the run, so the run headline stays
 * a number. Here nothing survives, and that is the case where a summariser
 * reading its state off the amounts instead of the receipts gets it wrong.
 */
const ranButUnpricedRows = () => [
  {
    id: 't-paid-unpriced',
    sector: 'Finance',
    occupation: 'Accountant',
    solve: receipt({
      status: 'partial',
      missing: ['price_missing'],
      components: [
        component('generation', 0, { status: 'partial' }),
        component('self_qa', 0, { status: 'partial' }),
      ],
    }),
  },
  {
    id: 't-never-started',
    sector: 'Health',
    occupation: 'Nurse',
    status: 'error',
    solve: receipt({ status: 'not_run' }),
  },
]

/** A run from before cost instrumentation existed. exp003 looks like this. */
const legacyRows = () => [
  { id: 't-complete', sector: 'Finance', occupation: 'Accountant' },
  { id: 't-zero', sector: 'Health', occupation: 'Nurse' },
]

// ── Assertions ──────────────────────────────────────────────────────────────

async function assertColumnsAndNote(page) {
  for (const label of ['문제 풀이 비용', '채점 비용']) {
    const header = page.locator('thead th').filter({ hasText: label })
    assert.equal(await header.count(), 1, `missing column header: ${label}`)
    assert.equal(await header.getAttribute('title'), ESTIMATE_NOTE)
  }
  // Goal 9: no amount may read as a billed figure, anywhere it is shown.
  assert.equal(
    (await page.locator('[data-testid="cost-estimate-note"]').innerText()).trim(),
    ESTIMATE_NOTE,
  )
}

async function assertFullyPriced(page, solveSummary, gradeSummary) {
  await assertColumnsAndNote(page)

  // A recorded zero is money. It must not degrade into 기록 없음.
  const zero = await readCell(tableCell(page, 't-zero', 'problem_solving_cost'))
  assert.equal(zero.text, '$0.0000')
  assert.equal(zero.state, 'recorded')
  assert.match(zero.title, literal(ESTIMATE_NOTE))

  // Graded with no receipt → 기록 없음. Never graded → 미채점. Different findings.
  const zeroGrade = await readCell(tableCell(page, 't-zero', 'grading_cost'))
  assert.equal(zeroGrade.text, '기록 없음')
  assert.equal(zeroGrade.state, 'absent')
  assert.match(zeroGrade.title, /\$0이 아니라/)

  const ungraded = await readCell(tableCell(page, 't-cheap', 'grading_cost'))
  assert.equal(ungraded.text, '미채점')
  assert.equal(ungraded.state, 'never_ran')

  const failed = await readCell(tableCell(page, 't-failed', 'problem_solving_cost'))
  assert.equal(failed.text, '$0.0400')
  assert.equal(failed.state, 'recorded')

  // Goal 7: both totals plus the spread, and they must equal what the
  // aggregator computed — not a number the page derived on its own.
  assert.equal(solveSummary.estimated_cost_usd, 0.34)
  const solveTotal = await readCell(summaryStat(page, 'problem_solving_cost', '총액'))
  assert.equal(solveTotal.text, usd(solveSummary.estimated_cost_usd))
  assert.equal(solveTotal.state, 'recorded')

  for (const [label, value] of [
    ['평균', solveSummary.avg_cost_usd],
    ['중앙값', solveSummary.median_cost_usd],
    ['P95', solveSummary.p95_cost_usd],
    ['최대', solveSummary.max_cost_usd],
    ['성공 결과물 1건당', solveSummary.cost_per_successful_deliverable_usd],
  ]) {
    const cell = await readCell(summaryStat(page, 'problem_solving_cost', label))
    assert.equal(cell.text, usd(value), `summary stat mismatch: ${label}`)
    assert.equal(cell.state, 'recorded')
  }

  // The grading half of this scenario is not fully recorded, and the page now
  // says so. `t-zero` was graded and the judge wrote no cost for it, which is
  // the 기록 없음 cell asserted above -- so $0.1300 covers two of the three
  // graded tasks and is a floor, not a total. It read `$0.1300 · 총액` until
  // the summariser stopped judging completeness against only the receipts it
  // kept; the cell right beside it said the third task's cost was unknown.
  assert.equal(gradeSummary.total_tasks, 3)
  assert.equal(gradeSummary.receipt_tasks, 2)
  assert.equal(gradeSummary.status, 'partial')
  assert.equal(gradeSummary.estimated_cost_usd, null)
  assert.equal(gradeSummary.known_cost_usd, 0.13)
  const gradeTotal = await readCell(summaryStat(page, 'grading_cost', '총액'))
  assert.equal(gradeTotal.text, `≥ ${usd(gradeSummary.known_cost_usd)}`)
  assert.equal(gradeTotal.state, 'floor')
  assert.match(gradeTotal.title, /3건 중 2건만 가격이 계산되어/)

  // The problem-solving half has a receipt on every row, so it is untouched:
  // still a total, still `recorded`. That contrast is the point -- one payload,
  // two fields, and only the one with a hole in it is downgraded.
  assert.equal(solveSummary.status, 'complete')
  assert.equal(solveSummary.receipt_tasks, solveSummary.total_tasks)

  // Goal 8: the failed task's cost is stated beside the total, not netted out.
  assert.equal(solveSummary.failed_task_count, 1)
  assert.equal(solveSummary.failed_task_cost_usd, 0.04)
  // Every failure on this run was priced, so the amount is the amount and the
  // row reads exactly as it did before the measured-failure count existed.
  assert.equal(solveSummary.failed_measured_tasks, 1)
  const failedCost = await readCell(
    summaryStat(page, 'problem_solving_cost', '실패 작업 비용'),
  )
  assert.equal(failedCost.text, '1건 · $0.0400')
  assert.equal(failedCost.state, 'recorded')

  // The audit sidecar is named on screen with a truncated digest.
  assert.match(
    await summaryColumn(page, 'problem_solving_cost').innerText(),
    literal(`cost_ledger.jsonl · sha256 ${LEDGER_SHA.slice(0, 12)}`),
  )

  // Goal 5: generation / Self-QA / retry / grading / perception, the sandbox
  // fee on its own line, then a total that is only a total because both halves
  // are complete.
  const modal = await openTask(page, 't-complete')
  assert.equal(
    (await modal.locator('[data-cost-field="problem_solving_cost"]').innerText()).trim(),
    '$0.2500',
  )
  for (const [slug, label, amount, field] of [
    ['generation', '생성', '$0.2000', 'problem_solving_cost'],
    ['self_qa', 'Self-QA', '$0.0300', 'problem_solving_cost'],
    ['retry', '재시도', '$0.0100', 'problem_solving_cost'],
    ['grading', '주 채점', '$0.1000', 'grading_cost'],
    ['perception', '판독', '$0.0200', 'grading_cost'],
  ]) {
    const row = modalComponent(modal, field, slug)
    assert.equal(await row.count(), 1, `missing component row: ${field}/${slug}`)
    const text = await row.innerText()
    assert.match(text, literal(label), `component label mismatch: ${slug}`)
    assert.match(text, literal(amount), `component amount mismatch: ${slug}`)
  }

  // A retry keeps the stage it belonged to. The row reads 재시도; the hover is
  // what says which 재시도, and without it two stages that each had to repeat
  // work would be two identical-looking lines.
  assert.equal(
    await modalComponent(modal, 'problem_solving_cost', 'retry')
      .locator('span')
      .first()
      .getAttribute('title'),
    '생성 · 품질 재시도',
  )

  // The sandbox fee is not a model call and gets no component line. It is
  // shown once, beside them, which is what makes 0.20 + 0.03 + 0.01 + 0.01
  // reconcile with the $0.2500 above without the fee being counted twice.
  const runtime = modal.locator('[data-cost-runtime="problem_solving_cost"]')
  assert.equal(await runtime.count(), 1, 'the sandbox fee has no line of its own')
  assert.match(await runtime.innerText(), literal('$0.0100'))
  // The grading half never opened a sandbox. The producer still writes 0 there,
  // so a line gated on presence rather than on money would appear here reading
  // 실행 환경 $0.0000 — on this task and on every other one in the dashboard.
  assert.equal(await modal.locator('[data-cost-runtime="grading_cost"]').count(), 0)

  const combined = await readCell(modal.locator('[data-cost-field="combined"]'))
  assert.equal(combined.text, '$0.3700')
  assert.equal(combined.state, 'recorded')
  assert.match(await modal.innerText(), literal(ESTIMATE_NOTE))
}

async function assertMixed(page, solveSummary) {
  // A partial receipt is a floor, and says so with ≥.
  const partial = await readCell(tableCell(page, 't-partial', 'problem_solving_cost'))
  assert.equal(partial.text, '≥ $0.1000')
  assert.equal(partial.state, 'floor')
  // The reason is shown in the same language as the rest of the row. The raw
  // slug must not reach the screen; if the label map ever loses this entry, the
  // fallback prints `runtime_cost_unpriced` and this assertion catches it.
  assert.match(partial.title, /실행 환경 단가 없음/)
  assert.doesNotMatch(partial.title, /runtime_cost_unpriced/)

  const unpriced = await readCell(tableCell(page, 't-unpriced', 'problem_solving_cost'))
  assert.equal(unpriced.text, '미확정')
  assert.equal(unpriced.state, 'unpriced')
  assert.match(unpriced.title, /가격표에 없는 모델/)

  const unpricedGrade = await readCell(tableCell(page, 't-complete', 'grading_cost'))
  assert.equal(unpricedGrade.text, '미확정')
  assert.equal(unpricedGrade.state, 'unpriced')

  // One unpriced receipt is enough to demote the run headline to a floor.
  assert.equal(solveSummary.estimated_cost_usd, null)
  assert.equal(solveSummary.known_cost_usd, 0.35)
  const total = await readCell(summaryStat(page, 'problem_solving_cost', '총액'))
  assert.equal(total.text, '≥ $0.3500')
  assert.equal(total.state, 'floor')

  // …and the per-deliverable figure refuses to exist rather than mislead.
  const perDeliverable = await readCell(
    summaryStat(page, 'problem_solving_cost', '성공 결과물 1건당'),
  )
  assert.equal(perDeliverable.text, '미확정')
  assert.equal(perDeliverable.state, 'unpriced')

  const column = await summaryColumn(page, 'problem_solving_cost').innerText()
  // Order follows the summariser, which sorts the slugs before they are
  // translated — so the reading order is the slug order, not the Korean one.
  assert.match(column, /미가격 사유: 가격표에 없는 모델, 실행 환경 단가 없음/)
  assert.match(column, /일부 기록됨/)

  const modal = await openTask(page, 't-partial')
  for (const [field, slug, text] of [
    ['problem_solving_cost', 'generation', '$0.1000'],
    ['problem_solving_cost', 'self_qa', '미수행'],
    ['grading_cost', 'grading', '$0.0150'],
  ]) {
    const row = modalComponent(modal, field, slug)
    assert.equal(await row.count(), 1, `missing component row: ${field}/${slug}`)
    assert.match(await row.innerText(), literal(text), `component readout mismatch: ${field}/${slug}`)
  }

  // The solve half ran a sandbox it could not price, so nothing was charged
  // and there is no line. `실행 환경 $0.0000` here would say the sandbox was
  // free, which is the opposite of what the ≥ and the reason code report.
  assert.equal(await modal.locator('[data-cost-runtime="problem_solving_cost"]').count(), 0)
  // The grading half did open one, and its $0.0050 is what makes the lines add
  // up to the $0.0200 shown above them.
  const runtime = modal.locator('[data-cost-runtime="grading_cost"]')
  assert.equal(await runtime.count(), 1, 'a priced sandbox fee must be visible')
  assert.match(await runtime.innerText(), literal('$0.0050'))

  // 0.10 solved + 0.02 graded, but the solve half is partial, so ≥.
  const combined = await readCell(modal.locator('[data-cost-field="combined"]'))
  assert.equal(combined.text, '≥ $0.1200')
  assert.equal(combined.state, 'floor')
}

async function assertRanButUnpriced(page, solveSummary) {
  await assertColumnsAndNote(page)

  // Money was spent on this row and the amount is unknown.
  const unpriced = await readCell(tableCell(page, 't-paid-unpriced', 'problem_solving_cost'))
  assert.equal(unpriced.text, '미확정')
  assert.equal(unpriced.state, 'unpriced')
  assert.match(unpriced.title, /가격표에 없는 모델/)

  // Nothing was spent on this one, and that is a different sentence. The two
  // sit in the same column of the same table, so a reader who cannot tell them
  // apart cannot tell an unpriced bill from no bill. This is also the only
  // place a `not_run` receipt reaches the page: everywhere else 미채점 comes
  // from a missing receipt, which is a different code path.
  const never = await readCell(tableCell(page, 't-never-started', 'problem_solving_cost'))
  assert.equal(never.text, '미실행')
  assert.equal(never.state, 'never_ran')

  // The regression this scenario exists for. Every amount here is null, so a
  // summariser that reads the run's state off the amounts rather than off the
  // receipts calls the whole run `not_run` — 미수행 — and a run that paid for
  // two model calls reads as a run that never happened. The one receipt that
  // truly did not run must abstain from that vote, not cast it.
  assert.equal(solveSummary.status, 'partial')
  assert.equal(solveSummary.measured_tasks, 0)
  assert.equal(solveSummary.known_cost_usd, 0)
  assert.equal(solveSummary.estimated_cost_usd, null)

  const column = await summaryColumn(page, 'problem_solving_cost').innerText()
  assert.match(column, /일부 기록됨/)
  assert.doesNotMatch(column, /미수행/)
  assert.match(column, /미가격 사유: 가격표에 없는 모델/)

  // Nothing was priced, so the headline is not a floor either. `≥ $0.0000`
  // would be a number, and there is no number to show.
  const total = await readCell(summaryStat(page, 'problem_solving_cost', '총액'))
  assert.equal(total.text, '미확정')
  assert.equal(total.state, 'unpriced')

  // The failed-task row, under the same rule as the headline above it.
  // `t-never-started` failed carrying a `not_run` receipt, whose money fields
  // arrive as 0.0 like every other status. Summed on its own that reads as a
  // failure that cost nothing, and this row printed `1건 · $0.0000` — the
  // producer's own docstring for that receipt is "Not free — it did not
  // happen." An amount is shown only when the failures behind it were priced.
  assert.equal(solveSummary.failed_task_count, 1)
  assert.equal(solveSummary.failed_measured_tasks, 0)
  const failedCost = await readCell(
    summaryStat(page, 'problem_solving_cost', '실패 작업 비용'),
  )
  assert.equal(failedCost.text, '1건 · 미확정')
  assert.equal(failedCost.state, 'unpriced')
  assert.doesNotMatch(failedCost.text, /\$0\.0000/)
}

async function assertLegacy(page) {
  // Goal 8: a run from before instrumentation still shows a cost card. Hiding
  // it and zeroing it are equally easy to misread as "this was free".
  assert.equal(await page.locator('[data-testid="cost-summary"]').count(), 1)
  await assertColumnsAndNote(page)

  for (const taskId of ['t-complete', 't-zero']) {
    const solve = await readCell(tableCell(page, taskId, 'problem_solving_cost'))
    assert.equal(solve.text, '기록 없음')
    assert.equal(solve.state, 'absent')
    const grade = await readCell(tableCell(page, taskId, 'grading_cost'))
    assert.equal(grade.text, '미채점')
    assert.equal(grade.state, 'never_ran')
  }

  for (const field of ['problem_solving_cost', 'grading_cost']) {
    const absent = summaryColumn(page, field).locator('[data-cost-state="absent"]')
    assert.equal(await absent.count(), 1, `missing 기록 없음 column: ${field}`)
    const text = await absent.innerText()
    assert.match(text, /^기록 없음/)
    assert.match(text, /\$0이 아니라/)
  }

  // Nothing in the card may render as an amount.
  assert.equal(
    await page.locator('[data-testid="cost-summary"] [data-cost-stat]').count(),
    0,
  )
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
  if (!address || typeof address === 'string') throw new Error('Vite preview did not expose a TCP port')
  const base = `http://127.0.0.1:${address.port}/gdpval-realworks`

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  })
  const page = await context.newPage()

  // Installed once, before the first navigation, so the HuggingFace request is
  // never actually made. `served` is swapped between loads.
  const served = { report: null, grade: null, graded: true }
  await page.route(REPORT_GLOB, (route) =>
    route.fulfill({
      status: 200,
      // A fulfilled cross-origin response still faces the browser's CORS check.
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
      body: JSON.stringify(served.report),
    }),
  )
  await page.route(GRADES_GLOB, (route) =>
    route.fulfill({ json: served.graded ? [served.grade] : [] }),
  )

  const load = async ({ report, grade }, { graded = true } = {}) => {
    Object.assign(served, { report, grade, graded })
    await page.goto(`${base}/experiments/${SHORT_ID}`)
    await page.locator('[data-testid="cost-summary"]').waitFor()
  }

  try {
    const priced = scenario(fullyPricedRows(), { experimentId, successfulDeliverables: 3 })
    await load(priced)
    await assertFullyPriced(page, priced.solveSummary, priced.gradeSummary)

    const mixed = scenario(mixedRows(), { experimentId, successfulDeliverables: 3 })
    await load(mixed)
    await assertMixed(page, mixed.solveSummary)

    const ranUnpriced = scenario(ranButUnpricedRows(), {
      experimentId,
      successfulDeliverables: 1,
    })
    await load(ranUnpriced, { graded: false })
    await assertRanButUnpriced(page, ranUnpriced.solveSummary)

    const legacy = scenario(legacyRows(), { experimentId, successfulDeliverables: 2 })
    assert.equal(legacy.solveSummary, null, 'a run with no receipts must summarise to null')
    await load(legacy, { graded: false })
    await assertLegacy(page)
  } finally {
    await context.close()
    await browser.close()
    await server.close()
  }
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
