// A file-generation rate divided by nothing must not be shown as a rate of
// nothing.
//
// `step5_validate` counts the tasks a run owed a file for and writes the count
// to `validate_stats.json`; `step6_report` copies it into `file_generation`,
// and the dashboard divides by it. Every reader wrote the division the same
// way —
//
//   needs_files_total > 0 ? ((files_succeeded / needs_files_total) * 100) : 0
//
// — and that `: 0` is the same glyph, on the same axis, as the value a run
// earns by failing every file it was asked for.
//
// Measured against this repository's published reports, all 26 of them:
//
//   * **4 runs publish `needs_files_total: 0`** — `exp013`, `exp014`, `exp025`
//     and `exp026`. Every one is a **full 220-task run**, and every one is
//     rendered today as a **0.0% file generation rate**. Their committed
//     `report.md` files carry the row verbatim: `| Successfully generated | 0
//     (0.0%) |`. Not one of them generated a file badly; none was asked for a
//     file at all.
//   * **1 run publishes `needs_files_total: null`** — `exp026c`, a 1-task
//     smoke whose `validate_stats.json` was never read. It carries no record
//     of a denominator, which is not the same as recording that there was
//     none, and `src/types/report.ts` declared the field non-null so no reader
//     had to consider it.
//   * **21 runs publish a positive denominator**, from `exp003`'s 185 down to
//     `exp030`'s 4. Those rates are measurements and must keep printing —
//     including any genuine `0.0%`.
//
// `src/components/dashboard/fileGenerationReading.ts` is where the reading now
// happens, and it is import-free so esbuild — already installed, as vite
// depends on it — can hand the real decision to node. This file holds six
// things in place:
//
//   A. the producer's field names and the reader's lookups are the same names,
//      so a rename cannot silently return every rate to "not recorded";
//   B. the four standings a published figure can be in, run for real, plus the
//      two that must still print: a true 0% over a real denominator, and 100%;
//   C. the published corpus read through both the old rule and the new one, so
//      the four affected runs are named by the test rather than by a comment;
//   D. a figure that stands on nothing is not comparable to one that does;
//   E. no surface under `src/` divides by `needs_files_total` itself;
//   F. the TypeScript contract admits the `null` `exp026c` actually contains.
//
// (E) is the guard that fails on the code this replaces.
//
// Run:
//   node --test scripts/__tests__/file-generation-denominator.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const READING_FILE = join(SRC_DIR, 'components', 'dashboard', 'fileGenerationReading.ts');
const REPORT_TYPES = join(SRC_DIR, 'types', 'report.ts');
const STEP5_PY = join(ROOT, 'batch-runner', 'step5_validate.py');
const REPORTS_INDEX = join(ROOT, 'public', 'generated', 'reports-index.json');

/** Everything `step5_validate` writes into `validate_stats.json`. */
const PRODUCER_KEYS = [
  'absent_task_ids',
  'dummy_files_created',
  'dummy_task_ids',
  'files_absent',
  'files_failed',
  'files_succeeded',
  'needs_files_total',
  // Not a count: the name of a non-baseline `active_policy`, or null. It is
  // here so a rename of it is caught by the same guard as the counts.
  'policy_caveat',
];

/** The subset `src/types/report.ts` declares and the dashboard reads. */
const CONTRACT_KEYS = [
  'absent_task_ids',
  'dummy_files_created',
  'dummy_task_ids',
  'files_absent',
  'files_failed',
  'files_succeeded',
  'needs_files_total',
];

// ── Loading the decision under test ───────────────────────────────────────

/**
 * The reading rule, type annotations stripped and nothing else touched.
 *
 * A failure to load is a real failure and is left to throw. Skipping would
 * leave the suite green while every executable assertion below quietly stopped
 * running — the same shape of mistake as the bug itself.
 */
async function loadReading() {
  const require = createRequire(join(ROOT, 'package.json'));
  const esbuild = require('esbuild');
  const source = await readFile(READING_FILE, 'utf8');
  const { code } = await esbuild.transform(source, {
    loader: 'ts',
    format: 'esm',
    target: 'node18',
  });
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}

/** Every source file under src/, so a new surface cannot dodge the scan. */
async function sourceFiles(dir = SRC_DIR, acc = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) await sourceFiles(full, acc);
    else if (['.ts', '.tsx', '.js', '.jsx'].includes(extname(entry.name))) acc.push(full);
  }
  return acc;
}

/**
 * A file with its comments gone: what the code actually does.
 *
 * Scanning raw text would count the division named in a comment explaining why
 * it was removed — the documentation that keeps this from being undone — as a
 * use of it. esbuild drops comments and leaves the property accesses, which is
 * exactly the difference that matters here.
 */
async function renderedText(file) {
  const raw = await readFile(file, 'utf8');
  if (file.endsWith('.d.ts')) return raw;
  const require = createRequire(join(ROOT, 'package.json'));
  const ext = extname(file);
  const { code } = await require('esbuild').transform(raw, {
    loader: { '.tsx': 'tsx', '.ts': 'ts', '.jsx': 'jsx', '.js': 'js' }[ext],
    format: 'esm',
    target: 'node18',
  });
  return code;
}

/** The published reports, exactly as the dashboard fetches them. */
async function publishedReports() {
  const index = JSON.parse(await readFile(REPORTS_INDEX, 'utf8'));
  assert.ok(Array.isArray(index.reports), 'reports-index.json carries no reports array');
  return index.reports;
}

/**
 * The rule this replaces, kept runnable so the corpus comparison below is a
 * real comparison and not a remembered one.
 */
const oldRule = (fg) =>
  `${fg.needs_files_total > 0
    ? ((fg.files_succeeded / fg.needs_files_total) * 100).toFixed(1)
    : 0}%`;

// ── A. Producer and reader name the same fields ───────────────────────────

test('the reader looks up the keys step5_validate actually writes', async () => {
  // A rename on either side would fail nothing else: every lookup would come
  // back undefined, every figure would read `not-recorded`, and the dashboard
  // would stop showing rates it can stand behind — quietly, everywhere at once.
  const py = await readFile(STEP5_PY, 'utf8');
  const at = py.indexOf('file_gen_stats = {');
  assert.ok(at >= 0, 'file_gen_stats is gone from step5_validate.py');
  const literal = py.slice(at, py.indexOf('\n    }', at));
  const declared = [...literal.matchAll(/"([a-z_]+)":/g)].map((m) => m[1]);
  // Assignments after the literal count too -- `files_absent` is set there.
  const assigned = [...py.matchAll(/file_gen_stats\["([a-z_]+)"\]/g)].map((m) => m[1]);
  const published = [...new Set([...declared, ...assigned])].sort();
  assert.deepEqual(published, PRODUCER_KEYS, 'the fields step5_validate writes have changed');

  // The TypeScript shape the cards read them through.
  const ts = await readFile(REPORT_TYPES, 'utf8');
  const start = ts.indexOf('export interface FileGeneration {');
  assert.ok(start >= 0, 'FileGeneration is gone from src/types/report.ts');
  const iface = ts.slice(start, ts.indexOf('\n}', start));
  for (const key of CONTRACT_KEYS) {
    assert.ok(iface.includes(`${key}`), `FileGeneration no longer declares ${key}`);
  }

  // And the reader's own field map, so the three names it divides with are the
  // producer's names and not a drifted copy.
  const reading = await readFile(READING_FILE, 'utf8');
  for (const key of ['needs_files_total', 'files_succeeded', 'files_failed']) {
    assert.ok(reading.includes(key), `the reading rule no longer mentions ${key}`);
  }
});

// ── B. The standings, run for real ────────────────────────────────────────

test('0 file-required tasks reads as "none required", not as 0%', async () => {
  // THE DEFECT, in one assertion. This is `exp013`, `exp014`, `exp025` and
  // `exp026` — four full 220-task runs.
  const { readFileGenerationRate } = await loadReading();
  const fg = { needs_files_total: 0, files_succeeded: 0, files_failed: 0 };

  for (const outcome of ['succeeded', 'failed']) {
    const r = readFileGenerationRate(fg, outcome);
    assert.equal(r.standing, 'none-required');
    assert.equal(r.value, 'n/a');
    assert.equal(r.fraction, null, 'a zero-length bar reads as the worst result on the chart');
    assert.equal(r.comparable, false);
    assert.match(r.caveat, /not\s+measured/);
    // The sentence must deny the reading the old code produced, in words.
    assert.match(r.caveat, /not a 0%/);
    assert.notEqual(r.value, '0.0%');
  }

  // And the old rule, run, to show what the four runs publish today. The two
  // producers spelled the same mistake differently -- the dashboard's ternary
  // fell through to a bare `0`, while step6's markdown used `0.0`, so the same
  // payload reads `0 (0%)` on the page and `0 (0.0%)` in the report file. Both
  // are a rate; neither was measured.
  assert.equal(oldRule(fg), '0%');
  assert.equal(`${(0.0).toFixed(1)}%`, '0.0%');
});

test('a null denominator reads as "not recorded", not as 0% and not as none required', async () => {
  // This is `exp026c`: `step6_report` writes the all-null block when
  // `validate_stats.json` could not be read. Not knowing the denominator is a
  // third state, distinct from knowing it was zero.
  const { readFileGenerationRate } = await loadReading();
  const fg = {
    needs_files_total: null,
    files_succeeded: null,
    files_failed: null,
    files_absent: null,
  };

  const r = readFileGenerationRate(fg, 'succeeded');
  assert.equal(r.standing, 'not-recorded');
  assert.equal(r.value, 'not recorded');
  assert.equal(r.fraction, null);
  assert.equal(r.comparable, false);
  assert.notEqual(r.standing, 'none-required', 'no record is not a recorded zero');

  // The old rule turned this one into a rate as well: `null > 0` is false.
  assert.equal(oldRule(fg), '0%');
});

test('a missing field and a missing block are both "not recorded", never 0', async () => {
  const { readFileGenerationRate, readFileGenerationCount } = await loadReading();

  // `undefined === null` is false, so a field that is simply gone slips past a
  // null check and reaches every reader that treats the two alike.
  for (const fg of [{}, { files_succeeded: 3 }]) {
    const r = readFileGenerationRate(fg, 'succeeded');
    assert.equal(r.standing, 'not-recorded', JSON.stringify(fg));
    assert.equal(r.fraction, null);
  }

  // A denominator with no outcome beside it is not zero successes.
  const halfRecorded = readFileGenerationRate({ needs_files_total: 185 }, 'succeeded');
  assert.equal(halfRecorded.standing, 'not-recorded');
  assert.match(halfRecorded.caveat, /185 tasks/);

  // No block at all.
  for (const missing of [null, undefined]) {
    const r = readFileGenerationRate(missing, 'succeeded');
    assert.equal(r.standing, 'absent');
    assert.equal(r.fraction, null);
    assert.equal(r.comparable, false);
  }

  // The counts beside the rate must not become zeros either: `{fg.files_failed}`
  // on a null renders as an empty cell that reads as one more 0.
  assert.equal(readFileGenerationCount(null), 'not recorded');
  assert.equal(readFileGenerationCount(undefined), 'not recorded');
  assert.equal(readFileGenerationCount(0), '0');
});

test('a real 0% over a real denominator still prints as 0.0%', async () => {
  // The negative control, and the reason this rule could not be "hide every
  // zero". A run that was asked for 185 files and produced none has failed
  // exactly as badly as 0.0% suggests, and must keep saying so.
  const { readFileGenerationRate } = await loadReading();
  const fg = { needs_files_total: 185, files_succeeded: 0, files_failed: 185 };

  const succeeded = readFileGenerationRate(fg, 'succeeded');
  assert.equal(succeeded.standing, 'measured');
  assert.equal(succeeded.value, '0.0%');
  assert.equal(succeeded.fraction, 0);
  assert.equal(succeeded.comparable, true);
  assert.equal(succeeded.caveat, undefined);

  // The same payload from the other side is a total failure, and reads as one.
  const failed = readFileGenerationRate(fg, 'failed');
  assert.equal(failed.standing, 'measured');
  assert.equal(failed.value, '100.0%');
  assert.equal(failed.fraction, 1);

  // The glyph the zero-denominator case must never produce is the one this
  // case does produce, which is the whole reason the two are told apart.
  const empty = readFileGenerationRate({ needs_files_total: 0, files_succeeded: 0 }, 'succeeded');
  assert.notEqual(empty.value, succeeded.value);
});

test('a real 100% prints as 100.0%', async () => {
  const { readFileGenerationRate } = await loadReading();
  const fg = { needs_files_total: 4, files_succeeded: 4, files_failed: 0 };

  const succeeded = readFileGenerationRate(fg, 'succeeded');
  assert.equal(succeeded.standing, 'measured');
  assert.equal(succeeded.value, '100.0%');
  assert.equal(succeeded.fraction, 1);
  assert.equal(succeeded.comparable, true);

  // And a genuine zero failure rate, which is good news and must print.
  const failed = readFileGenerationRate(fg, 'failed');
  assert.equal(failed.standing, 'measured');
  assert.equal(failed.value, '0.0%');
  assert.equal(failed.fraction, 0);

  // `exp003`, the largest measured run in the corpus, to the tenth.
  const real = readFileGenerationRate(
    { needs_files_total: 185, files_succeeded: 177, files_failed: 8 },
    'succeeded',
  );
  assert.equal(real.value, '95.7%');
});

// ── C. The published corpus, read through both rules ──────────────────────

test('every published report reads as a rate only where one was measured', async () => {
  const { readFileGenerationRate } = await loadReading();
  const reports = await publishedReports();
  assert.ok(reports.length >= 20, `only ${reports.length} published reports were read`);

  const byStanding = { measured: [], 'none-required': [], 'not-recorded': [], absent: [] };
  for (const report of reports) {
    const r = readFileGenerationRate(report.file_generation, 'succeeded');
    byStanding[r.standing].push(report.short_id);
  }

  // The four runs this change exists for, named by reading the corpus.
  assert.deepEqual(
    byStanding['none-required'].slice().sort(),
    ['exp013', 'exp014', 'exp025', 'exp026'],
    'the set of runs with a zero denominator has changed',
  );
  assert.deepEqual(byStanding['not-recorded'].slice().sort(), ['exp026c']);

  // Teeth. If the corpus ever held only unmeasured runs this test would pass
  // while proving nothing, which is the shape of the bug it is guarding.
  assert.ok(
    byStanding.measured.length >= 20,
    `only ${byStanding.measured.length} runs were measured; this test would be hollow`,
  );

  // Each affected run is a full 220-task run, so "no file was required" is a
  // statement about the manifest and not about a small sample.
  for (const shortId of byStanding['none-required']) {
    const report = reports.find((r) => r.short_id === shortId);
    assert.equal(report.summary.total_tasks, 220, `${shortId} is not a full run`);
  }

  // And what those five publish today, under the rule being replaced.
  for (const shortId of [...byStanding['none-required'], ...byStanding['not-recorded']]) {
    const fg = reports.find((r) => r.short_id === shortId).file_generation;
    assert.match(oldRule(fg), /^0(\.0)?%$/, `${shortId} did not previously render as zero`);
  }
});

// ── D. What may be set against what ───────────────────────────────────────

test('a figure that stands on nothing is not comparable to one that does', async () => {
  const { readFileGenerationRate } = await loadReading();

  const measured = readFileGenerationRate(
    { needs_files_total: 185, files_succeeded: 177, files_failed: 8 },
    'succeeded',
  );
  const noneRequired = readFileGenerationRate(
    { needs_files_total: 0, files_succeeded: 0, files_failed: 0 },
    'succeeded',
  );
  const notRecorded = readFileGenerationRate({ needs_files_total: null }, 'succeeded');

  assert.equal(measured.comparable, true);
  for (const other of [noneRequired, notRecorded]) {
    assert.equal(other.comparable, false);
    // A gap taken against a figure that stands on nothing is not a large gap.
    // One of its two terms does not exist.
    assert.equal(
      measured.comparable && other.comparable,
      false,
      'a pair may be compared only when both sides were measured',
    );
  }
});

// ── E. No surface divides by the denominator itself ───────────────────────

test('no file under src/ computes a file-generation rate of its own', async () => {
  // The guard that fails on the code this replaces. Both surfaces carried the
  // same expression: the detail page at `src/pages/ExperimentDetail.tsx` and
  // the cross-run card at `src/components/dashboard/ErrorAnalysisView.tsx`.
  const offenders = [];
  const readers = [];
  for (const file of await sourceFiles()) {
    const rel = relative(ROOT, file);
    if (file === READING_FILE || file === REPORT_TYPES) continue;
    const code = await renderedText(file);
    if (!code.includes('needs_files_total')) continue;
    readers.push(rel);
    // Any arithmetic on the denominator, in any of the forms the two surfaces
    // used: a division, or a `> 0` guard standing in for one.
    if (/needs_files_total\s*[)\]]*\s*(\*|-|>|<|>=|<=)/.test(code)
      || /\/\s*[A-Za-z_$][\w$.?[\]]*needs_files_total/.test(code)
      || /needs_files_total[\w$.?[\]]*\s*\)?\s*\)?\s*\*\s*100/.test(code)) {
      offenders.push(rel);
    }
    if (!code.includes('readFileGenerationRate') && !code.includes('readFileGenerationCount')) {
      offenders.push(`${rel} (reads the field without the reading rule)`);
    }
  }

  assert.deepEqual(offenders, [], 'these surfaces read the denominator themselves');
  // Teeth again: if every reader were deleted or renamed, the loop above would
  // find nothing and pass.
  assert.ok(
    readers.length >= 2,
    `only ${readers.length} surface(s) read file_generation; the scan found nothing to check`,
  );
});

// ── F. The contract admits what the payload contains ──────────────────────

test('FileGeneration declares the null exp026c actually publishes', async () => {
  // The type said `needs_files_total: number`, so no reader had to consider the
  // null, and `strictNullChecks` could not point at the branch that was missing.
  const ts = await readFile(REPORT_TYPES, 'utf8');
  const start = ts.indexOf('export interface FileGeneration {');
  const iface = ts.slice(start, ts.indexOf('\n}', start));

  for (const key of ['needs_files_total', 'files_succeeded', 'files_failed', 'dummy_files_created']) {
    const declared = new RegExp(`${key}\\??:\\s*([^\\n]+)`).exec(iface);
    assert.ok(declared, `FileGeneration no longer declares ${key}`);
    assert.match(
      declared[1],
      /null/,
      `FileGeneration.${key} must admit null -- exp026c publishes one`,
    );
  }

  // And the corpus proves the null is real rather than defensive.
  const reports = await publishedReports();
  const nulls = reports.filter((r) => r.file_generation && r.file_generation.needs_files_total === null);
  assert.ok(nulls.length >= 1, 'no published report carries a null denominator any more');
});
