// The numbers in a report are checked before the dashboard renders them.
//
// `scripts/aggregate-reports.mjs` writes `public/generated/reports-index.json`,
// which is where the leaderboard, the trend view and the sector matrix get every
// figure they draw. On a real build all 26 of those reports arrive over an
// unauthenticated HuggingFace fetch, are spread into the index verbatim, and are
// rendered as percentages, scores and task counts.
//
// `src/types/report.ts` describes that payload precisely -- five counters that
// are always measured, six figures where `null` means "never measured, not
// measured at zero" -- and nothing enforced a word of it. An interface says what
// a value will be once it arrives. It cannot say what arrives.
//
// The instance that made the gap visible was one line:
//
//     retried_count: r.summary.retried_count || 0
//
// A report that never recorded a retry count was published as one that retried
// nothing. `||` cannot tell those apart, and they are not the same fact.
//
// Run:
//   node --test scripts/__tests__/aggregate-reports-summary-contract.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, rm, copyFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import { validateReportSummary } from '../aggregate-reports.mjs';

const execFileAsync = promisify(execFile);
const SCRIPTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');

// The shape a real report has. Every field here is present and numeric on all
// 26 published reports and all 208 sector rows -- measured before the check was
// written, which is why adding it moves no figure on the dashboard.
function summaryFixture(overrides = {}) {
  return {
    total_tasks: 10,
    success_count: 9,
    error_count: 1,
    retried_count: 2,
    success_rate_pct: 90,
    avg_qa_score: 7.5,
    min_qa_score: 5,
    max_qa_score: 9,
    avg_latency_ms: 1200,
    max_latency_ms: 3000,
    total_latency_ms: 12000,
    ...overrides,
  };
}

function sectorFixture(overrides = {}) {
  return {
    sector: 'Retail',
    total: 10,
    success: 9,
    success_rate_pct: 90,
    avg_qa_score: 7.5,
    avg_latency_ms: 1200,
    ...overrides,
  };
}

function reportFixture({ summary = {}, sectors = [sectorFixture()], ...rest } = {}) {
  return {
    meta: {
      date: '2026-01-01',
      model: 'gpt-5.4',
      condition_name: 'condition_a',
      experiment_name: 'fixture',
      execution_mode: 'subprocess',
      duration: '1m',
      report_scope: 'self_assessed_pre_grading',
    },
    summary: summaryFixture(summary),
    sector_breakdown: sectors,
    task_results: [{ task_id: 't1', qa_score: 7.5 }],
    ...rest,
  };
}

// Drop a key rather than set it to undefined: `'x' in obj` is the check under
// test, and an explicit `undefined` would still satisfy it. The fixture helpers
// merge, so an absence has to be made on the built object, not asked for.
function without(object, field) {
  const copy = { ...object };
  delete copy[field];
  return copy;
}

function reportMissing(path, field) {
  const report = reportFixture();
  if (path === 'summary') delete report.summary[field];
  else delete report.sector_breakdown[0][field];
  return report;
}

// ── the counters that are always measured ─────────────────────────────────

const COUNTERS = ['total_tasks', 'success_count', 'error_count', 'retried_count'];

test('a report matching the published contract passes', () => {
  assert.doesNotThrow(() => validateReportSummary(reportFixture()));
});

test('a counter that was never recorded is refused, not read as zero', () => {
  for (const field of COUNTERS) {
    assert.throws(
      () => validateReportSummary(reportMissing('summary', field)),
      new RegExp(`summary\\.${field} must be a whole count, not undefined`),
      `${field} absent must fail`,
    );
  }
});

test('a counter written as null is refused too', () => {
  // null is the honest word for "never measured" on the six below. It is not
  // one of the words these four are allowed to say, because a run always knows
  // how many tasks it ran.
  for (const field of COUNTERS) {
    assert.throws(
      () => validateReportSummary(reportFixture({ summary: { [field]: null } })),
      new RegExp(`summary\\.${field} must be a whole count, not null`),
    );
  }
});

test('a counter that is not a whole count is refused', () => {
  for (const [value, shown] of [[-1, '-1'], [2.5, '2\\.5'], ['9', '"9"'], [NaN, 'NaN']]) {
    assert.throws(
      () => validateReportSummary(reportFixture({ summary: { error_count: value } })),
      new RegExp(`summary\\.error_count must be a whole count, not ${shown}`),
    );
  }
});

// NaN and Infinity both serialise to `null`, and `null` is the one word this
// check exists to keep honest. A message naming a value the payload does not
// hold would send a reader looking for the wrong thing.
test('an unrepresentable number is named for what it is, not as null', () => {
  assert.throws(
    () => validateReportSummary(reportFixture({ summary: { avg_qa_score: Infinity } })),
    /avg_qa_score must be a number, or null for never measured, not Infinity/,
  );
});

// ── the six where null means never measured ───────────────────────────────

const MEASURED_OR_NULL = [
  'avg_qa_score',
  'min_qa_score',
  'max_qa_score',
  'avg_latency_ms',
  'max_latency_ms',
  'total_latency_ms',
];

test('an absent measurement is refused rather than folded into null', () => {
  // `undefined === null` is false, so a field that is simply gone slips past
  // every null check downstream and reaches the readers that turn absence into
  // the bottom of the scale. Absent and null must be told apart here, once.
  for (const field of MEASURED_OR_NULL) {
    assert.throws(
      () => validateReportSummary(reportMissing('summary', field)),
      new RegExp(`summary\\.${field} is absent -- write null`),
      `${field} absent must fail`,
    );
  }
});

test('null is accepted on every one of the six, and is not turned into a number', () => {
  const allNull = Object.fromEntries(MEASURED_OR_NULL.map((field) => [field, null]));
  assert.doesNotThrow(() => validateReportSummary(reportFixture({ summary: allNull })));
});

test('a measurement that is not a number and not null is refused', () => {
  for (const [value, shown] of [['7.5', '"7\\.5"'], [NaN, 'NaN'], [true, 'true']]) {
    assert.throws(
      () => validateReportSummary(reportFixture({ summary: { min_qa_score: value } })),
      new RegExp(`summary\\.min_qa_score must be a number, or null .*, not ${shown}`),
    );
  }
});

// ── the rate, and the one piece of arithmetic ─────────────────────────────

test('a success rate outside 0-100 is refused', () => {
  for (const value of [-0.1, 100.1, 1000, NaN, null, undefined, '90']) {
    assert.throws(
      () => validateReportSummary(reportFixture({ summary: { success_rate_pct: value } })),
      /summary\.success_rate_pct must be a percentage from 0 to 100/,
      `success_rate_pct ${String(value)} must fail`,
    );
  }
});

test('the two ends of the rate are inside the contract, not outside it', () => {
  for (const value of [0, 100]) {
    assert.doesNotThrow(
      () => validateReportSummary(reportFixture({ summary: { success_rate_pct: value } })),
    );
  }
});

test('a run cannot succeed at more tasks than it ran', () => {
  assert.throws(
    () => validateReportSummary(
      reportFixture({ summary: { total_tasks: 10, success_count: 12 } }),
    ),
    /summary\.success_count \(12\) is above summary\.total_tasks \(10\)/,
  );
});

// ── the sector rows behind the matrix ─────────────────────────────────────

test('a sector breakdown that is not a list of sectors is refused', () => {
  const absent = reportFixture();
  delete absent.sector_breakdown;
  assert.throws(
    () => validateReportSummary(absent),
    /sector_breakdown must be an array of sectors, not undefined/,
  );
  for (const [value, shown] of [[null, 'null'], [{}, '{}'], ['Retail', '"Retail"']]) {
    assert.throws(
      () => validateReportSummary(reportFixture({ sectors: value })),
      new RegExp(`sector_breakdown must be an array of sectors, not ${shown}`),
    );
  }
});

test('a sector row is held to the same contract as the summary', () => {
  const cases = [
    [{ sector: '   ' }, /sector_breakdown\[0\]\.sector must name a sector, not "   "/],
    [{ total: undefined }, /sector_breakdown\[0\]\.total must be a whole count, not undefined/],
    [{ success: -1 }, /sector_breakdown\[0\]\.success must be a whole count, not -1/],
    [{ success_rate_pct: 101 }, /sector_breakdown\[0\]\.success_rate_pct must be a percentage/],
  ];
  for (const [overrides, expected] of cases) {
    assert.throws(
      () => validateReportSummary(reportFixture({ sectors: [sectorFixture(overrides)] })),
      expected,
    );
  }
});

test('a sector that recorded no score must say null, not leave the field out', () => {
  // A sector whose every task errored has no average. The type says so in as
  // many words: "not a sector that scored zero".
  for (const field of ['avg_qa_score', 'avg_latency_ms']) {
    assert.throws(
      () => validateReportSummary(
        reportFixture({ sectors: [without(sectorFixture(), field)] }),
      ),
      new RegExp(`sector_breakdown\\[0\\]\\.${field} is absent -- write null`),
    );
    assert.doesNotThrow(
      () => validateReportSummary(
        reportFixture({ sectors: [sectorFixture({ [field]: null })] }),
      ),
    );
  }
});

test('the row that is wrong is the row that is named', () => {
  assert.throws(
    () => validateReportSummary(reportFixture({
      sectors: [sectorFixture(), sectorFixture({ sector: 'Health Care', total: null })],
    })),
    /sector_breakdown\[1\]\.total/,
  );
});

// NEGATIVE CONTROL. An experiment with no sector rows at all is empty, not
// broken -- `[]` is a list of sectors that happens to hold none.
test('a report with no sector rows still passes', () => {
  assert.doesNotThrow(() => validateReportSummary(reportFixture({ sectors: [] })));
});

// ── what the message has to be good enough to do ──────────────────────────

test('a summary that is missing entirely says so before anything else', () => {
  for (const summary of [undefined, null, 'nine', []]) {
    assert.throws(
      () => validateReportSummary({ summary, sector_breakdown: [] }),
      /report summary is missing or is not an object/,
    );
  }
});

test('every problem in one report is listed at once, not one per build', () => {
  const report = reportFixture({ sectors: [sectorFixture({ total: -3 })] });
  report.summary.retried_count = null;
  delete report.summary.avg_qa_score;

  let caught;
  try {
    validateReportSummary(report);
  } catch (err) {
    caught = err;
  }
  assert.ok(caught, 'a report with three problems must not pass');
  assert.match(caught.message, /src\/types\/report\.ts/);
  assert.match(caught.message, /summary\.retried_count/);
  assert.match(caught.message, /summary\.avg_qa_score/);
  assert.match(caught.message, /sector_breakdown\[0\]\.total/);
});

// ── the exit code, and the number that used to be invented ────────────────
//
// Everything above calls the module directly. The defect was that a wrong
// number reached the dashboard, so these run the real script end to end. Each
// directory gets a local report file, which keeps the group hermetic: no
// network, no retries, no wall-clock.

async function scratchTree(dirs) {
  const root = await mkdtemp(join(tmpdir(), 'report-contract-'));
  await mkdir(join(root, 'scripts'), { recursive: true });
  for (const name of ['aggregate-reports.mjs', 'cost-receipt.mjs']) {
    await copyFile(join(SCRIPTS_DIR, name), join(root, 'scripts', name));
  }
  for (const [dirName, content] of Object.entries(dirs)) {
    const reportDir = join(root, 'batch-runner', 'results', dirName, 'report');
    await mkdir(reportDir, { recursive: true });
    await writeFile(join(reportDir, 'report_data.json'), JSON.stringify(content), 'utf-8');
  }
  return root;
}

async function runAggregate(root) {
  try {
    const { stdout, stderr } = await execFileAsync(
      process.execPath,
      [join(root, 'scripts', 'aggregate-reports.mjs')],
      { cwd: root },
    );
    return { code: 0, stdout, stderr };
  } catch (err) {
    return { code: err.code ?? 1, stdout: err.stdout ?? '', stderr: err.stderr ?? '' };
  }
}

const INDEX_PATH = ['public', 'generated', 'reports-index.json'];

// THE DEFECT. `retried_count || 0` published "nothing was retried" for a report
// that had never counted. It exited 0, wrote the index, and put the invented
// number on the leaderboard beside the real ones.
test('a report that never counted its retries fails the build instead of publishing 0', async () => {
  const silent = reportFixture();
  delete silent.summary.retried_count;

  const root = await scratchTree({ exp901_good: reportFixture(), exp902_silent: silent });
  try {
    const { code, stderr } = await runAggregate(root);
    assert.equal(code, 1, 'this used to exit 0 with an invented 0 on the leaderboard');
    assert.match(stderr, /1 of 2 report\(s\) could not be loaded/);
    assert.match(stderr, /exp902_silent/);
    assert.match(stderr, /summary\.retried_count must be a whole count, not undefined/);
    assert.doesNotMatch(stderr, /exp901_good/);
    assert.equal(existsSync(join(root, ...INDEX_PATH)), false, 'no half-index is published');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// NEGATIVE CONTROL, and the reason the fallback had to go rather than stay as
// belt and braces. A run that genuinely retried nothing still publishes its 0 --
// the number that is now on the leaderboard is one a report actually recorded.
test('a run that really did retry nothing publishes its own zero', async () => {
  const root = await scratchTree({
    exp901_zero: reportFixture({ summary: { retried_count: 0 } }),
  });
  try {
    const { code, stdout } = await runAggregate(root);
    assert.equal(code, 0, stdout);
    const index = JSON.parse(await readFile(join(root, ...INDEX_PATH), 'utf-8'));
    assert.equal(index.cross_experiment.experiments[0].retried_count, 0);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// A run whose tasks all errored has nothing to average. It must reach the
// leaderboard as null and be drawn as an em dash, not as the bottom of the
// scale -- which is what the type has always said and nothing checked.
test('a run that measured no score publishes null, not the bottom of the scale', async () => {
  const nothingMeasured = reportFixture({
    summary: Object.fromEntries([
      ...MEASURED_OR_NULL.map((field) => [field, null]),
      ['success_count', 0],
      ['error_count', 10],
      ['success_rate_pct', 0],
    ]),
    sectors: [sectorFixture({ success: 0, success_rate_pct: 0, avg_qa_score: null, avg_latency_ms: null })],
  });
  const root = await scratchTree({ exp901_all_errored: nothingMeasured });
  try {
    const { code, stdout } = await runAggregate(root);
    assert.equal(code, 0, stdout);
    const index = JSON.parse(await readFile(join(root, ...INDEX_PATH), 'utf-8'));
    const entry = index.cross_experiment.experiments[0];
    assert.equal(entry.avg_qa_score, null);
    assert.equal(entry.success_rate_pct, 0, 'a rate over 10 tasks was measured, and it is 0');
    assert.equal(index.cross_experiment.sector_matrix.Retail.exp901.avg_qa_score, null);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('a sector row nobody could stand behind stops the build and names its report', async () => {
  const root = await scratchTree({
    exp901_good: reportFixture(),
    exp903_sector: reportFixture({ sectors: [sectorFixture({ success_rate_pct: 900 })] }),
  });
  try {
    const { code, stderr } = await runAggregate(root);
    assert.notEqual(code, 0);
    assert.match(stderr, /exp903_sector/);
    assert.match(stderr, /sector_breakdown\[0\]\.success_rate_pct must be a percentage/);
    assert.equal(existsSync(join(root, ...INDEX_PATH)), false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
