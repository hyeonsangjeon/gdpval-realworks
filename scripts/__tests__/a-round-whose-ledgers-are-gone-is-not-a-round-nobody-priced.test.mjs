// The round's ledgers are gone. That is not the same as nobody having priced it.
//
// `derive_run_cost.py` prices a run's tokens back out of that run's own sqlite
// ledger and writes `results/<exp>/report/derived_cost.json`, which the
// aggregator reads and the detail page renders. exp034 has one. It works.
//
// exp035 cannot have one. It ran as six legs across two lineages, and its six
// ledgers lived under `/tmp/relay/...` and `/tmp/leg7_artifact/...` on runners
// that no longer exist. There is no second chance to run the tool.
//
// But the derivation was performed while they did exist. `roll_up_round.py
// --ledger` read all six, priced them against the committed table, and
// cross-checked the result against the per-task records; the answer is
// committed in `docs/run_records/round_state.json` under
// `cost.ledger_cross_check`. So the largest measured-token evidence this
// project holds was sitting in the repository showing nothing on screen, while
// a 30-task trial showed $12.2683. The probe found no file, ENOENT read as
// absent, and absent is the correct reading of an absent file — the defect was
// upstream of it, in nothing ever writing one.
//
// `derive_round_cost_sidecar.py` writes it, copying rather than re-deriving.
// This file checks the copy arrives, and three things about what it says:
//
//   * the published figure is the LEDGER total, 112.773814, not the per-task
//     records' 112.773878. The counts belong to the ledger pass, and a total
//     from one derivation beside counts from another describes something
//     nobody measured. The two differ by rounding; tidying them to match would
//     hide which pass produced the number.
//   * the scope is the whole round, both lineages. The superseded lineage's
//     $14.386586 bought work a later lineage replaced, and it was still spent.
//     A figure covering only the surviving lineage would call that part zero.
//   * it is a floor and says so: 56 of 510 calls reported no usage at all. The
//     screen must read `≥`, never `≈`.
//
// And the seam this bridge exists to hold: a figure the run settled and a
// figure someone priced afterwards are different claims. `derived_cost` sits
// beside `cost_summary` in the index, never inside it.
//
// Run:
//   node --test scripts/__tests__/a-round-whose-ledgers-are-gone-is-not-a-round-nobody-priced.test.mjs

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { execFile } from 'node:child_process'
import { mkdtemp, mkdir, readFile, writeFile, rm, copyFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import ts from 'typescript'

import { projectDerivedCost } from '../cost-receipt.mjs'

const execFileAsync = promisify(execFile)
const SCRIPTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..')
const REPO_ROOT = join(SCRIPTS_DIR, '..')

/** The directory the round published under, and the name the aggregator scans. */
const EXPERIMENT_DIR = 'exp035_codex_foundry_full220'

/**
 * The exact path the aggregator probes. Written out here rather than imported
 * because the defect was the file not being at this path: a test that asks the
 * aggregator where it looks would move with it and check nothing.
 */
const SIDECAR_PATH = join(
  REPO_ROOT, 'batch-runner', 'results', EXPERIMENT_DIR, 'report', 'derived_cost.json',
)
const ROUND_STATE_PATH = join(
  REPO_ROOT, 'batch-runner', 'docs', 'run_records', 'round_state.json',
)

const readJson = async (path) => JSON.parse(await readFile(path, 'utf8'))

const readSource = (path) => readFile(new URL(`../../${path}`, import.meta.url), 'utf8')

/** Same helper as the sibling derived-cost test: transpile a `.ts` and import it. */
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

// ── 1. the file is where the probe looks, and says what the record says ────

test('the round publishes a sidecar at the path the aggregator probes', async () => {
  // ENOENT here is the whole defect, so it is checked before anything reads
  // the contents. An absent file is a legible claim — "nobody priced this" —
  // and it was the wrong one.
  const sidecar = await readJson(SIDECAR_PATH)
  assert.equal(sidecar.derived_total_is_provider_billed, false)
  assert.equal(sidecar.derived_total_is_a_floor, true)
})

test('the sidecar carries the ledger pass, not the per-task records', async () => {
  const sidecar = await readJson(SIDECAR_PATH)
  const check = (await readJson(ROUND_STATE_PATH)).cost.ledger_cross_check

  assert.equal(sidecar.derived_total_usd, check.derived_total_usd)
  assert.equal(sidecar.calls_total, check.calls_total)
  assert.equal(sidecar.calls_measured, check.calls_measured)
  assert.equal(sidecar.calls_unmeasured, check.calls_unmeasured)
  assert.equal(sidecar.tasks_with_a_call, check.tasks_with_a_call)
  assert.equal(sidecar.price_table_sha256, check.price_table_sha256)

  // The counts above came from the ledger pass, so the total has to as well.
  // The records' own total is kept, in its own field, precisely so the two are
  // never silently reconciled into one.
  const records = (await readJson(ROUND_STATE_PATH)).cost.round_total_usd
  assert.notEqual(sidecar.derived_total_usd, records)
  assert.equal(sidecar.source.round_total_usd_from_the_task_records, records)
  assert.ok(
    Math.abs(sidecar.derived_total_usd - records) < 0.01,
    'a gap this size is the per-task rounding; anything larger is a disagreement',
  )
})

test('the published figure covers the superseded lineage too', async () => {
  const sidecar = await readJson(SIDECAR_PATH)
  const cost = (await readJson(ROUND_STATE_PATH)).cost
  const lineages = Object.values(cost.per_lineage).map((l) => l.derived_cost_usd)
  const survivor = Math.max(...lineages)

  // A task two lineages both solved is one task of coverage and two payments
  // of cost. Publishing only the surviving lineage would report the round as
  // cheaper than it was by exactly the amount of the work that was thrown away.
  assert.ok(
    sidecar.derived_total_usd > survivor,
    'the round total must exceed any one lineage, or superseded spend was dropped',
  )
  assert.equal(sidecar.source.spent_on_work_that_was_superseded_usd,
    cost.spent_on_work_that_was_superseded_usd)
})

test('every ledger the cross-check read is named, and none of them twice', async () => {
  const sidecar = await readJson(SIDECAR_PATH)
  const check = (await readJson(ROUND_STATE_PATH)).cost.ledger_cross_check
  const fromRecord = check.ledgers.map((l) => l.sha256)

  assert.deepEqual(sidecar.source.ledger_sha256, fromRecord)
  // The same ledger listed twice would sum one leg's calls twice, and the
  // total would look like a larger round rather than a broken one.
  assert.equal(new Set(sidecar.source.ledger_sha256).size, sidecar.source.ledger_sha256.length)
})

// ── 2. the real projection and the real cell ──────────────────────────────

test("the committed sidecar projects intact through the display contract", async () => {
  const projected = projectDerivedCost(await readJson(SIDECAR_PATH))
  assert.equal(projected.derived_total_usd, 112.773814)
  assert.equal(projected.calls_total, 510)
  assert.equal(projected.calls_measured, 454)
  assert.equal(projected.calls_unmeasured, 56)
  assert.equal(projected.tasks_with_a_call, 220)
  assert.equal(projected.derived_total_is_a_floor, true)
  assert.equal(projected.derived_total_is_provider_billed, false)
  assert.equal(projected.estimate_basis, 'usage_estimate_not_azure_invoice')
})

test('an absent refusal map is not a claim that nothing was refused', async () => {
  const sidecar = await readJson(SIDECAR_PATH)
  // The record keeps no per-reason breakdown of the 56, so the producer writes
  // null rather than inventing reason codes. The contract accepts that and
  // normalises it to an empty map, which nothing renders — what the screen
  // states about the unpriced calls is the count, below, and that is measured.
  assert.equal(sidecar.pricer_refusals, null)
  assert.deepEqual(projectDerivedCost(sidecar).pricer_refusals, {})
})

test('the screen reads at least, not about, and says how many it could not price', async () => {
  const cell = derivedTotalCell(projectDerivedCost(await readJson(SIDECAR_PATH)))
  assert.equal(cell.state, 'derived')
  assert.match(cell.text, /^≥ \$112\.7738$/)
  assert.doesNotMatch(cell.text, /≈/)
  // The unmeasured calls are stated on screen, so a reader is never left to
  // read a floor as a total.
  assert.match(cell.title, /510/)
  assert.match(cell.title, /56/)
})

// ── 3. the real aggregator, end to end ────────────────────────────────────

// Everything above reads the file and calls the modules. The defect was that
// nothing carried the figure into the index, so these run the real script.

/**
 * A stand-in for the round's `report_data.json`.
 *
 * It has to be a stand-in: that file is deliberately gitignored and arrives
 * over the HuggingFace fetch at build time, so no test can hold the real one.
 * Only the sidecar beside it is committed, and the sidecar is what these two
 * tests vary. The figures below are placeholders and describe nothing.
 *
 * The receipt is `partial` because that is the state a Codex round leaves it
 * in and it is the interesting one: the run settled no amount, so the card
 * reads 기록 없음. Whether the round nonetheless has a priced floor to show is
 * decided entirely by the file next to it.
 */
function reportFixture() {
  return {
    meta: {
      date: '2026-09-12',
      model: 'gpt-5.4',
      condition_name: 'condition_a',
      experiment_name: 'exp035',
      execution_mode: 'subprocess',
      duration: '1m',
    },
    summary: {
      success_rate_pct: 50,
      avg_qa_score: 7.5,
      total_tasks: 220,
      success_count: 110,
      retried_count: 0,
      error_count: 110,
      min_qa_score: 5,
      max_qa_score: 9,
      avg_latency_ms: 1200,
      max_latency_ms: 3000,
      total_latency_ms: 264000,
    },
    sector_breakdown: [
      {
        sector: 'Retail',
        success_rate_pct: 50,
        avg_qa_score: 7.5,
        avg_latency_ms: 1200,
        success: 110,
        total: 220,
      },
    ],
    task_results: [{ task_id: 't1', qa_score: 7.5 }],
    cost_summary: {
      problem_solving_cost: {
        schema_version: 'cost-receipt-v1',
        currency: 'USD',
        status: 'partial',
        total_tasks: 220,
        receipt_tasks: 220,
        measured_tasks: 0,
        coverage_pct: 0,
        complete_tasks: 0,
        partial_tasks: 220,
        unavailable_tasks: 0,
        not_run_tasks: 0,
        known_cost_usd: 0,
        estimated_cost_usd: null,
        avg_cost_usd: null,
        median_cost_usd: null,
        p95_cost_usd: null,
        max_cost_usd: null,
        successful_deliverables: null,
        cost_per_successful_deliverable_usd: null,
        failed_task_count: 0,
        failed_task_cost_usd: 0,
        components: [],
        price_table_sha256: null,
        missing_reasons: ['call_reachability_unknown'],
      },
    },
  }
}

/**
 * A hermetic copy of the repo layout the aggregator walks. `withSidecar`
 * decides whether the real committed file is copied in, which is the only
 * difference between the two runs below.
 */
async function scratchTree({ withSidecar }) {
  const root = await mkdtemp(join(tmpdir(), 'round-sidecar-'))
  await mkdir(join(root, 'scripts'), { recursive: true })
  for (const name of ['aggregate-reports.mjs', 'cost-receipt.mjs']) {
    await copyFile(join(SCRIPTS_DIR, name), join(root, 'scripts', name))
  }
  const reportDir = join(root, 'batch-runner', 'results', EXPERIMENT_DIR, 'report')
  await mkdir(reportDir, { recursive: true })
  await writeFile(join(reportDir, 'report_data.json'), JSON.stringify(reportFixture()), 'utf-8')
  if (withSidecar) await copyFile(SIDECAR_PATH, join(reportDir, 'derived_cost.json'))
  return root
}

async function runAggregate(root) {
  try {
    const { stdout, stderr } = await execFileAsync(
      process.execPath, [join(root, 'scripts', 'aggregate-reports.mjs')], { cwd: root },
    )
    return { code: 0, stdout, stderr }
  } catch (err) {
    return { code: err.code ?? 1, stdout: err.stdout ?? '', stderr: err.stderr ?? '' }
  }
}

const INDEX_PATH = ['public', 'generated', 'reports-index.json']

test('the real aggregator carries the round floor into the index', async () => {
  const root = await scratchTree({ withSidecar: true })
  try {
    const { code, stderr } = await runAggregate(root)
    assert.equal(code, 0, stderr)
    const index = await readJson(join(root, ...INDEX_PATH))
    const entry = index.reports.find((r) => r.short_id === 'exp035')
    assert.ok(entry, 'the round must be in the index at all')

    assert.equal(entry.derived_cost.derived_total_usd, 112.773814)
    assert.equal(entry.derived_cost.calls_unmeasured, 56)
    assert.equal(entry.derived_cost.derived_total_is_a_floor, true)
    assert.equal(entry.derived_cost.derived_total_is_provider_billed, false)

    // Beside, never inside. A receipt says the run stood behind a figure; this
    // says someone priced its tokens afterwards. Sharing a field would let one
    // be read as the other, so the receipt must come through untouched: still
    // partial, still naming no total, while the floor sits at the same level
    // of the entry under its own name.
    const receipt = entry.cost_summary.problem_solving_cost
    assert.equal(receipt.status, 'partial')
    assert.equal(receipt.estimated_cost_usd, null)
    for (const leaked of ['derived_total_usd', 'derived_total_is_a_floor', 'calls_unmeasured']) {
      assert.equal(leaked in receipt, false, `${leaked} must not be inside the receipt`)
    }
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})

test('the same round without the sidecar publishes no amount at all', async () => {
  const root = await scratchTree({ withSidecar: false })
  try {
    const { code, stderr } = await runAggregate(root)
    // This is the state the round was in: the build is green, the report
    // publishes, and the money is simply not there. Absent, not zero — the
    // index must carry no derived figure rather than a nought.
    assert.equal(code, 0, stderr)
    const index = await readJson(join(root, ...INDEX_PATH))
    const entry = index.reports.find((r) => r.short_id === 'exp035')
    assert.ok(entry)
    assert.equal('derived_cost' in entry, false)
    // And the receipt beside it is unchanged either way, which is the point:
    // the two are separate claims and the absence of one says nothing about
    // the other.
    assert.equal(entry.cost_summary.problem_solving_cost.status, 'partial')
  } finally {
    await rm(root, { recursive: true, force: true })
  }
})
