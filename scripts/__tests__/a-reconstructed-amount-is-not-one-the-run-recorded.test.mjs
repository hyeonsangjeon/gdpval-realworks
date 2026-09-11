// The 220-task relay run cannot publish what it spent.
//
// `#537` fixed the defect that empties a Codex run's dollar column, but run
// 34603033098 pins `batch-runner` to sha `2f2fda4`, which predates it. It will
// finish and report `$0` for the same reason `exp034_codex_foundry_trial30`
// reports `$0` on the dashboard right now:
//
//   partial · $0 · measured 0 of 30 · missing_reasons ['call_reachability_unknown']
//
// That run's own sqlite ledger still holds every token it used, and
// `batch-runner/derive_run_cost.py` (#536) prices them back. Run against
// exp034's committed rows it returns $12.2683 over 59 calls — the same figure
// `test_the_fix_makes_the_price_of_the_discarded_work_computable` pins. Until
// now nothing read that output, so the number existed and no screen showed it.
//
// This file guards the bridge that shows it, and the one distinction the
// bridge exists to preserve: a figure the run settled and a figure someone
// computed afterwards are not the same claim, and must never share a field.
//
//   cost_summary.known_cost_usd  — the run stood behind this
//   derived_cost.derived_total_usd — someone priced the run's tokens later
//
// `projectDerivedCost` therefore refuses rather than flattens. Three things in
// particular, each of which turns a cautious figure into an overclaim:
//
//   * a block calling itself provider-billed. The producer hard-codes that
//     false; anything else is a derived estimate wearing an invoice's clothes.
//   * a floor flag that disagrees with the unmeasured count. At the producer
//     those are one fact stated twice. They are what makes the screen say `≥`
//     instead of `≈`, so a file where they diverge is unreadable, not
//     half-readable.
//   * counts that cannot have come from the same ledger.
//
// And one thing the display layer refuses: a derivation over zero priced calls
// sums to 0.0 and arrives as a perfectly well-formed block. `≈ $0.0000` on
// screen would say a run nobody could price was free — the exact sentence this
// path was built to stop. It renders 되짚지 못함 instead.
//
// The numbers below are not invented. They are what
// `derive_run_cost.py --ledger` returned against exp034's own rows.

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import ts from 'typescript'

import { projectDerivedCost } from '../cost-receipt.mjs'

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

const { derivedTotalCell } = await importTypeScriptModule('src/lib/cost.ts')

const PRICE_TABLE_SHA = 'b01b384c532b1457804e3a77713d2b079b06b363a5ff3b8b939fe65a4cb30b4e'

/**
 * What `derive_run_cost.py --json` wrote for exp034, minus `per_task`, which
 * the aggregator does not carry into the index.
 */
const derived = (overrides = {}) => ({
  method:
    'core.cost_receipts.price_call over the run ledger cost_calls table, priced with '
    + `the committed receipt price table (sha256 ${PRICE_TABLE_SHA}); the same `
    + 'fingerprint the run itself recorded',
  price_table_sha256: PRICE_TABLE_SHA,
  calls_total: 59,
  calls_measured: 53,
  calls_unmeasured: 6,
  tasks_with_a_call: 30,
  derived_total_usd: 12.268258,
  derived_total_is_a_floor: true,
  derived_total_is_provider_billed: false,
  pricer_refusals: {},
  ...overrides,
})

test('a run with no sidecar is absent, which is not a run that cost nothing', () => {
  assert.equal(projectDerivedCost(null), null)
  assert.equal(projectDerivedCost(undefined), null)
})

test("the tool's real output over exp034's ledger projects intact", () => {
  const projected = projectDerivedCost(derived())
  assert.equal(projected.derived_total_usd, 12.268258)
  assert.equal(projected.derived_total_is_a_floor, true)
  assert.equal(projected.calls_total, 59)
  assert.equal(projected.calls_measured, 53)
  assert.equal(projected.calls_unmeasured, 6)
  assert.equal(projected.tasks_with_a_call, 30)
  assert.equal(projected.price_table_sha256, PRICE_TABLE_SHA)
  // Carried so a reader can see it is an estimate without being told twice.
  assert.equal(projected.estimate_basis, 'usage_estimate_not_azure_invoice')
})

test('a derived amount never claims to be what the provider billed', () => {
  assert.throws(
    () => projectDerivedCost(derived({ derived_total_is_provider_billed: true })),
    /provider_billed/,
  )
  // Nor by omission: a missing flag is not a false one.
  const withoutFlag = derived()
  delete withoutFlag.derived_total_is_provider_billed
  assert.throws(() => projectDerivedCost(withoutFlag), /provider_billed/)
  // The projector pins it rather than echoing it, so a `false` that arrived as
  // a string could never be re-serialised as truthy.
  assert.equal(projectDerivedCost(derived()).derived_total_is_provider_billed, false)
})

test('the floor flag and the unmeasured count are one fact, so they must agree', () => {
  // Understating: unpriced calls exist but the block calls the total exact.
  assert.throws(
    () => projectDerivedCost(derived({ derived_total_is_a_floor: false })),
    /disagrees with itself/,
  )
  // Overstating, the other way: nothing went unpriced, yet it hedges anyway.
  assert.throws(
    () => projectDerivedCost(derived({ calls_unmeasured: 0 })),
    /disagrees with itself/,
  )
  // And agreeing at zero is fine — that is an exact derivation.
  const exact = projectDerivedCost(
    derived({ calls_unmeasured: 0, calls_measured: 59, derived_total_is_a_floor: false }),
  )
  assert.equal(exact.derived_total_is_a_floor, false)
})

test('counts that cannot have come from one ledger are refused', () => {
  assert.throws(
    () => projectDerivedCost(derived({ calls_measured: 60 })),
    /smaller than the calls attributed to tasks/,
  )
  assert.throws(
    () => projectDerivedCost(derived({ tasks_with_a_call: 60 })),
    /exceeds the calls it was counted from/,
  )
  // But rows belonging to no task are legitimate — the sum is a bound, not an
  // identity, and a ledger with orphan rows still projects.
  const orphans = projectDerivedCost(derived({ calls_total: 70 }))
  assert.equal(orphans.calls_total, 70)
})

test('a figure that will not say how it was arrived at is not shown', () => {
  const noMethod = derived()
  delete noMethod.method
  assert.throws(() => projectDerivedCost(noMethod), /how the figure was arrived at/)
  assert.throws(() => projectDerivedCost(derived({ method: '' })), /how the figure/)
  const total = derived()
  delete total.derived_total_usd
  assert.throws(() => projectDerivedCost(total), /must carry a derived total/)
})

test('a call refused for two reasons at once arrives as one comma-joined key', () => {
  // `derive_run_cost.py` keys this map on `",".join(priced.missing_reasons)`.
  // Validating it against the single-code pattern would reject the whole file
  // exactly when the pricer had the most to report about it.
  const projected = projectDerivedCost(
    derived({ pricer_refusals: { 'usage_absent,price_missing': 4, usage_absent: 2 } }),
  )
  assert.equal(projected.pricer_refusals['usage_absent,price_missing'], 4)
  assert.equal(projected.pricer_refusals.usage_absent, 2)
  // Prose in the key position is still refused: these are codes, not sentences.
  assert.throws(
    () => projectDerivedCost(derived({ pricer_refusals: { 'no price for this model': 1 } })),
    /unreadable reason code/,
  )
})

test('a derivation over zero priced calls does not render as a free run', () => {
  // An empty or unreadable ledger yields a valid block summing to $0. The
  // projector takes it — it is well-formed — and the cell refuses to put a
  // dollar figure on screen for it.
  const empty = projectDerivedCost(
    derived({
      calls_total: 0,
      calls_measured: 0,
      calls_unmeasured: 0,
      tasks_with_a_call: 0,
      derived_total_usd: 0,
      derived_total_is_a_floor: false,
    }),
  )
  assert.equal(empty.derived_total_usd, 0)

  const cell = derivedTotalCell(empty)
  assert.equal(cell.isAmount, false)
  assert.equal(cell.text, '되짚지 못함')
  assert.match(cell.title, /비용이 0이라는 뜻이 아니라/)
  assert.doesNotMatch(cell.text, /\$/)
})

test('a floor reads as at least, and an exact derivation as about', () => {
  const floor = derivedTotalCell(projectDerivedCost(derived()))
  assert.equal(floor.state, 'derived')
  assert.match(floor.text, /^≥ /)
  assert.match(floor.text, /12\.2683/)
  // The tooltip has to say whose number it is, in words a reader can check.
  assert.match(floor.title, /실행이 스스로 남긴 금액이 아닙니다/)
  assert.match(floor.title, /6건은 값을 매길 수 없어/)

  const exact = derivedTotalCell(
    projectDerivedCost(
      derived({ calls_unmeasured: 0, calls_measured: 59, derived_total_is_a_floor: false }),
    ),
  )
  assert.match(exact.text, /^≈ /)
  assert.doesNotMatch(exact.text, /≥/)
})
