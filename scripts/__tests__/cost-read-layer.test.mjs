/**
 * The cost payload nothing has checked.
 *
 * Two cost payloads on the experiment page are validated before they are
 * rendered, and one is not:
 *
 * - grading receipts go through `projectCostReceipt` in `aggregate-grades.mjs`
 *   at build time;
 * - run summaries go through `projectCostSummary` in `aggregate-reports.mjs`,
 *   also at build time;
 * - per-task **solving** receipts go through neither. `aggregate-reports.mjs`
 *   strips `task_results` from the index (`const { task_results: _ignored,
 *   ...indexEntry } = data`), so the detail page fetches that array from
 *   HuggingFace at read time and hands it straight to `src/lib/cost.ts`.
 *
 * The two halves sit on the same displayed row. One is checked and one is
 * hoped for.
 *
 * It does not fail small. A receipt whose amount arrives as the string
 * `"0.04"` reaches `formatCostUsd`, `.toFixed` is not a function, and the error
 * boundary in `src/App.tsx` replaces the whole experiment page with "Something
 * went wrong" — every task, every score, every summary gone over one field on
 * one receipt. Confirmed in a real headless browser across eleven shapes; the
 * browser half of this lives in `cost-receipts.browser.mjs`.
 *
 * The fix is a read layer, not a validator. At build time fail-closed means
 * "stop and name the directory"; at read time it has to mean "do not show a
 * number nobody can stand behind", because killing the page is not an
 * improvement on rendering 미확정.
 *
 * So every test below has a negative control beside it. A guard that turns
 * every receipt into 미확정 would satisfy the first half of this file and fail
 * the second, which is the half that says real receipts still show their real
 * amounts — including the two amounts easiest to lose: a recorded `$0.0000`
 * and a `0` on a component line.
 */

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

const readSource = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

/** Same helper as field-notes.test.mjs: transpile a `.ts` and import it. */
async function importTypeScriptModule(path) {
  const source = await readSource(path)
  const result = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2020 },
    reportDiagnostics: true,
  })
  assert.equal(result.diagnostics?.length ?? 0, 0)
  return import(`data:text/javascript;base64,${Buffer.from(result.outputText).toString('base64')}`)
}

const cost = await importTypeScriptModule('src/lib/cost.ts')
const { applyReportIndexSnapshot } = await importTypeScriptModule('src/lib/reportIndexSnapshot.ts')

/** A well-formed component line, in the shape the page reads. */
const component = (overrides = {}) => ({
  name: 'generation',
  stage: 'generation',
  retry_kind: 'none',
  status: 'complete',
  known_cost_usd: 0.04,
  model_calls: 1,
  usage: {},
  missing_reasons: [],
  ...overrides,
})

/** A well-formed complete receipt, in the shape the page reads. */
const receipt = (overrides = {}) => ({
  schema_version: 'cost-receipt-v1',
  currency: 'USD',
  status: 'complete',
  estimated_cost_usd: 0.04,
  known_cost_usd: 0.04,
  model_cost_usd: 0.04,
  runtime_cost_usd: 0,
  model_calls: 1,
  usage: {},
  components: [component()],
  price_table_sha256: '9f'.repeat(32),
  missing_reasons: [],
  ...overrides,
})

/**
 * The values a JSON payload can carry where a number belongs. `"0.04"` is the
 * one actually seen — a producer that stringified a Decimal — and the rest are
 * the neighbouring ways the same field goes wrong.
 */
const NOT_NUMBERS = ['0.04', '', true, {}, [], Number.NaN, Number.POSITIVE_INFINITY]

/** And where a list belongs. */
const NOT_LISTS = [null, undefined, 'nope', 0, {}, true]

// ── Amounts ─────────────────────────────────────────────────────────────────

test('an amount that is not a number is read as no amount', () => {
  for (const value of NOT_NUMBERS) {
    assert.equal(
      cost.receiptAmount(receipt({ estimated_cost_usd: value, known_cost_usd: value })),
      null,
      `estimated/known = ${JSON.stringify(value)}`,
    )
  }
})

test('a broken amount is not stepped over to reach the other one', () => {
  // `receiptAmount` prefers `estimated_cost_usd` and falls back to
  // `known_cost_usd`. Reading the fallback here would publish a figure off a
  // receipt that has already shown its money fields cannot be read — the
  // fallback is for a receipt that omits the estimate, not for one that got it
  // wrong. Checked in both directions.
  assert.equal(cost.receiptAmount(receipt({ estimated_cost_usd: '0.04' })), null)
  assert.equal(
    cost.receiptAmount(receipt({ estimated_cost_usd: null, known_cost_usd: '0.04', status: 'partial' })),
    null,
  )
  assert.equal(cost.receiptAmount(receipt({ known_cost_usd: '0.04' })), null)
})

test('a receipt with a broken amount reads as 미확정, not as $0 and not as a crash', () => {
  const cell = cost.costCell(receipt({ estimated_cost_usd: '0.04', known_cost_usd: '0.04' }), 'problem_solving_cost')
  assert.equal(cell.text, '미확정')
  assert.equal(cell.state, 'unpriced')
  assert.doesNotMatch(cell.text, /\$/)
})

test('negative control: a real recorded amount is still the amount', () => {
  const cell = cost.costCell(receipt(), 'problem_solving_cost')
  assert.equal(cell.text, '$0.0400')
  assert.equal(cell.state, 'recorded')
  assert.equal(cost.receiptAmount(receipt()), 0.04)
})

test('negative control: a recorded zero is still $0.0000, not 미확정', () => {
  // The one honest $0 the contract admits. A guard that treated falsy as
  // absent would turn "this really was free" into "nobody knows", which is the
  // exact confusion the four states exist to prevent.
  const free = receipt({ estimated_cost_usd: 0, known_cost_usd: 0, model_cost_usd: 0 })
  assert.equal(cost.receiptAmount(free), 0)
  const cell = cost.costCell(free, 'problem_solving_cost')
  assert.equal(cell.text, '$0.0000')
  assert.equal(cell.state, 'recorded')
})

test('a partial receipt with one readable amount is still a floor', () => {
  const cell = cost.costCell(
    receipt({ status: 'partial', estimated_cost_usd: null, known_cost_usd: 0.04 }),
    'problem_solving_cost',
  )
  assert.equal(cell.text, '≥ $0.0400')
  assert.equal(cell.state, 'floor')
})

test('a status nobody publishes is 미확정 rather than an amount', () => {
  const cell = cost.costCell(receipt({ status: 'weird' }), 'problem_solving_cost')
  assert.equal(cell.text, '미확정')
  assert.equal(cell.state, 'unpriced')
})

test('a broken amount cannot poison the combined total', () => {
  // Two failures live here, and the second is the worse one.
  //
  // The first: a broken figure reaching the sum makes it NaN, and
  // `NaN.toFixed(4)` is the string "NaN", so the row renders `$NaN`.
  //
  // The second: the sum drops the unreadable half, but "is this a total or a
  // floor" was decided from the receipts' *statuses*, and a receipt claiming
  // `complete` with an unreadable amount still voted "whole". So the pair
  // printed `$0.0200` — one half, labelled as the total, for a pair worth at
  // least $0.0600. That is the one outcome worse than the blank page: it looks
  // like an answer.
  const combined = cost.combinedTaskCost(
    receipt({ estimated_cost_usd: '0.04', known_cost_usd: '0.04' }),
    receipt({ estimated_cost_usd: 0.02, known_cost_usd: 0.02 }),
  )
  assert.doesNotMatch(combined.text, /NaN/)
  assert.equal(combined.text, '≥ $0.0200')
  assert.equal(combined.state, 'floor')
})

test('negative control: a task that never ran still leaves the pair exact', () => {
  // The tightening above must not catch the receipt that legitimately
  // contributes no amount. Work that did not happen is not a hole in the sum.
  const combined = cost.combinedTaskCost(
    receipt(),
    receipt({ status: 'not_run', estimated_cost_usd: null, known_cost_usd: 0, components: [] }),
  )
  assert.equal(combined.text, '$0.0400')
  assert.equal(combined.state, 'recorded')
})

test('negative control: two whole receipts still add to an exact total', () => {
  const combined = cost.combinedTaskCost(
    receipt(),
    receipt({ estimated_cost_usd: 0.02, known_cost_usd: 0.02 }),
  )
  assert.equal(combined.text, '$0.0600')
  assert.equal(combined.state, 'recorded')
})

// ── The runtime line ────────────────────────────────────────────────────────

test('a runtime fee that is not a number shows no runtime line', () => {
  for (const value of NOT_NUMBERS) {
    assert.equal(
      cost.runtimeLineAmount(receipt({ runtime_cost_usd: value })),
      null,
      `runtime_cost_usd = ${JSON.stringify(value)}`,
    )
  }
})

test('negative control: a charged sandbox still gets its line, and a free one still does not', () => {
  assert.equal(cost.runtimeLineAmount(receipt({ runtime_cost_usd: 0.005 })), 0.005)
  // Every receipt carries this field, so gating on presence would put
  // `실행 환경 $0.0000` on every task in the dashboard.
  assert.equal(cost.runtimeLineAmount(receipt({ runtime_cost_usd: 0 })), null)
})

// ── Component lines ─────────────────────────────────────────────────────────

test('a components field that is not a list draws no rows', () => {
  for (const value of NOT_LISTS) {
    assert.deepEqual(
      cost.receiptComponents(receipt({ components: value })),
      [],
      `components = ${JSON.stringify(value)}`,
    )
  }
})

test('negative control: a real breakdown still draws every row it has', () => {
  const lines = [component(), component({ stage: 'self_qa', name: 'self_qa' })]
  assert.deepEqual(cost.receiptComponents(receipt({ components: lines })), lines)
})

test('a component amount that is not a number reads as 미확정', () => {
  for (const value of NOT_NUMBERS) {
    assert.equal(
      cost.componentAmountText(component({ known_cost_usd: value })),
      '미확정',
      `known_cost_usd = ${JSON.stringify(value)}`,
    )
  }
  const { known_cost_usd: _absent, ...withoutAmount } = component()
  assert.equal(cost.componentAmountText(withoutAmount), '미확정')
})

test('negative control: a priced component line still shows its amount, zero included', () => {
  assert.equal(cost.componentAmountText(component()), '$0.0400')
  assert.equal(cost.componentAmountText(component({ known_cost_usd: 0 })), '$0.0000')
  assert.equal(cost.componentAmountText(component({ status: 'not_run' })), '미수행')
})

test('a component name that is not a name degrades to ? rather than throwing', () => {
  // `componentLabel` split the slug on `_`. On a number that is a TypeError,
  // and the TypeError lands in the same error boundary as a bad amount.
  for (const value of [42, null, undefined, {}, [], '', true]) {
    assert.equal(cost.componentLabel(value), '?', `name = ${JSON.stringify(value)}`)
  }
})

test('negative control: known and unknown slugs are labelled exactly as before', () => {
  assert.equal(cost.componentLabel('generation'), '생성')
  assert.equal(cost.componentLabel('grading'), '주 채점')
  assert.equal(cost.componentLabel('perception'), '판독')
  // An unknown slug is still shown as it arrived, spaced. Printing it raw is
  // the honest failure: it is ugly enough to get fixed.
  assert.equal(cost.componentLabel('some_new_stage'), 'some new stage')
})

test('a malformed component detail never renders as [object Object]', () => {
  const detail = cost.componentDetail(
    component({ stage: {}, retry_kind: {}, resolved_model: 42 }),
  )
  assert.doesNotMatch(detail, /\[object Object\]/)
  assert.equal(detail, '?')
})

test('negative control: a real detail still names stage, retry reason and model', () => {
  assert.equal(
    cost.componentDetail(
      component({ stage: 'perception', retry_kind: 'semantic', resolved_model: 'gpt-5-mini' }),
    ),
    '판독 · 품질 재시도 · gpt-5-mini',
  )
  assert.equal(cost.componentDetail(component()), '생성')
})

// ── Missing reasons ─────────────────────────────────────────────────────────

test('a missing_reasons field that is not a list reads as no reasons', () => {
  for (const value of NOT_LISTS) {
    assert.equal(cost.missingReasonText(value), '', `missing_reasons = ${JSON.stringify(value)}`)
  }
})

test('an unpriced receipt with no readable reasons still says it is unpriced', () => {
  const cell = cost.costCell(
    receipt({ status: 'unavailable', estimated_cost_usd: null, known_cost_usd: null, missing_reasons: null }),
    'problem_solving_cost',
  )
  assert.equal(cell.text, '미확정')
  assert.match(cell.title, /가격을 계산할 수 없음/)
})

test('negative control: real reasons are still translated, deduplicated and joined', () => {
  assert.equal(cost.missingReasonText(['price_missing']), '가격표에 없는 모델')
  assert.equal(cost.missingReasonText(['price_missing', 'price_missing']), '가격표에 없는 모델')
  assert.equal(
    cost.missingReasonText(['price_missing', 'usage_absent']),
    '가격표에 없는 모델, 응답에 사용량 없음',
  )
  // A ninth reason the label map has not heard of is shown as it arrived.
  assert.equal(cost.missingReasonText(['brand_new_reason']), 'brand_new_reason')
})

// ── The run-level half: a spread cannot overwrite a key the entry lacks ──────

test('a run summary the build never validated does not survive the merge', async () => {
  // `aggregate-reports.mjs` runs `cost_summary` through `projectCostSummary`
  // and omits it when there is nothing to write. The merge was
  // `{...report, ...entry}`, which only overwrites keys the entry has, so for
  // a report with no validated summary the object fetched from HuggingFace
  // came through unchecked. 23 of the 26 published reports are in that state.
  const merged = applyReportIndexSnapshot(
    { short_id: 'stale', cost_summary: { problem_solving_cost: { known_cost_usd: '0.04' } }, task_results: [1] },
    { short_id: 'exp027' },
    'exp027',
  )
  assert.equal('cost_summary' in merged, false)
  assert.equal('cost_ledger' in merged, false)
})

test('the validated copy wins when the entry carries one', async () => {
  const entry = { short_id: 'exp030', cost_summary: { problem_solving_cost: { known_cost_usd: 0.5 } } }
  const merged = applyReportIndexSnapshot(
    { short_id: 'stale', cost_summary: { problem_solving_cost: { known_cost_usd: '0.04' } }, task_results: [] },
    entry,
    'exp030',
  )
  assert.deepEqual(merged.cost_summary, entry.cost_summary)
})

test('negative control: everything else still merges the way it always did', () => {
  const merged = applyReportIndexSnapshot(
    { short_id: 'stale', summary: { total_tasks: 0 }, only_on_report: 'kept', task_results: [1, 2] },
    { short_id: 'exp027', summary: { total_tasks: 220 }, only_on_entry: 'added' },
    'exp027',
  )
  assert.equal(merged.short_id, 'exp027')
  assert.deepEqual(merged.summary, { total_tasks: 220 })
  // A key the index does not carry is still the report's. Only the two cost
  // keys are dropped, and only because the build validates exactly those.
  assert.equal(merged.only_on_report, 'kept')
  assert.equal(merged.only_on_entry, 'added')
  // `task_results` is stripped from the index and fetched live, so it comes
  // from the report or nowhere.
  assert.deepEqual(merged.task_results, [1, 2])
})

test('the published index is still read the way it is written', async () => {
  // Measured rather than asserted, on the file the page actually loads: three
  // of the 26 entries carry a validated summary and keep it, and the other 23
  // carry none — so for those the merge now drops any unvalidated copy the
  // fetch returns. None of the 26 is in that state today (index and payload
  // agree on all 26, and no report has a local `report_data.json` for them to
  // disagree through), which is the point: the rule is what keeps that true.
  // If the aggregator starts writing summaries for every report, this number
  // moves and the sentence above stops being true.
  const index = JSON.parse(await readSource('public/generated/reports-index.json'))
  const withSummary = index.reports.filter((entry) => 'cost_summary' in entry)
  assert.ok(withSummary.length > 0, 'expected at least one validated run summary in the index')
  assert.ok(
    withSummary.length < index.reports.length,
    'expected the index to still contain reports with no validated summary',
  )

  for (const entry of index.reports) {
    const fetched = { short_id: 'stale', cost_summary: { forged: true }, task_results: [] }
    const merged = applyReportIndexSnapshot(fetched, entry, entry.short_id)
    assert.equal('cost_summary' in merged, 'cost_summary' in entry, entry.short_id)
    if ('cost_summary' in entry) assert.deepEqual(merged.cost_summary, entry.cost_summary, entry.short_id)
  }
})

// ── The corpus this is safe on ──────────────────────────────────────────────

test('every real published receipt still reads as the amount it recorded', async () => {
  // The blast radius, taken on the payloads that are actually served. Each of
  // these was fetched from HuggingFace and checked against `projectCostReceipt`
  // while this was being written: 11 receipts across the 26 published reports,
  // 11 pass, 0 fail. The 23 reports with no receipts render 기록 없음 either
  // way. So the read layer changes nothing about what a reader sees today —
  // it only decides what happens the first time a receipt arrives malformed.
  //
  // The committed sample stands in for that fetch here, because a unit test
  // must not reach the network.
  const index = JSON.parse(await readSource('public/generated/reports-index.json'))
  let checked = 0
  for (const entry of index.reports) {
    const summaries = entry.cost_summary
    if (!summaries) continue
    for (const [field, summary] of Object.entries(summaries)) {
      checked += 1
      const total = cost.summaryTotalCell(summary, field)
      assert.notEqual(total.text, 'NaN', `${entry.short_id}/${field}`)
      assert.doesNotMatch(total.text, /NaN|undefined/, `${entry.short_id}/${field}`)
      assert.ok(
        ['recorded', 'floor', 'unpriced'].includes(total.state),
        `${entry.short_id}/${field} state ${total.state}`,
      )
      // The reasons list on a real summary is a list, so it prints.
      assert.equal(typeof cost.missingReasonText(summary.missing_reasons), 'string')
    }
  }
  assert.ok(checked > 0, 'expected the published index to still carry run summaries')
})
