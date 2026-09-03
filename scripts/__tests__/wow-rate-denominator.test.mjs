// A pass rate divided by nothing must not be shown as a pass rate of nothing.
//
// `step8_grade._rate` returns `0.0` for an empty denominator, on purpose and
// with the hazard written into its own docstring: `0.0` is also the *worst
// possible score*, so the two cases are the same glyph on the wire. The
// producer's answer was `_wow_item_counts`, which publishes the denominators
// beside the rates — and its docstring names the reader that had not yet used
// them:
//
//   "the dashboard's *Structure vs Reasoning* card turns the same gap into
//    'Strong on reasoning, weak on structure' -- a finding about a check that
//    never ran, in a paid report and on a public page."
//
// Measured against this repository's published grades: 20 of the 33 published
// run-level payloads carry `precheck_pass_rate: 0.0`, and **all 20 counted no
// precheck items**. Per sector, 59 of 86 rows publish `0.0` and **all 59
// counted nothing**. Not one row in either set is a run where prechecks ran and
// failed. The 61 shard payloads and their 364 sector rows are published nowhere
// and record no denominator at all; this comment first added them in and gave
// the pair as 81 of 94 and 420 of 447, which is the conflation `CHANGELOG.md`
// corrects under #398. The published side then moved again under #399, which
// recovered `item_counts` across the corpus — which is why every zero above can
// now be checked, where before only the 15 and 35 with a recorded denominator
// could be.
//
// `src/components/wow/rateReading.ts` is where the reading now happens, and it
// is import-free so esbuild — already installed, as vite depends on it — can
// hand the real decision to node. This file holds five things in place:
//
//   A. the producer's denominator keys and the reader's lookups are the same
//      names, so a rename cannot silently return every rate to "unknown";
//   B. the four standings a published rate can be in, run for real;
//   C. two rates are compared only when both were measured;
//   D. what is said instead of a comparison names the side that is missing;
//   E. no surface under src/ reads one of these three rates without it.
//
// (E) is the guard that fails on the code this replaced.
//
// Run:
//   node --test scripts/__tests__/wow-rate-denominator.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const READING_FILE = join(SRC_DIR, 'components', 'wow', 'rateReading.ts');
const GRADE_TYPES = join(SRC_DIR, 'types', 'grade.ts');
const STEP8_PY = join(ROOT, 'batch-runner', 'step8_grade.py');

/** The three rates that are divided by a `_wow_item_counts` denominator. */
const RATE_KEYS = [
  'precheck_pass_rate',
  'judge_pass_rate',
  'rubric_item_coverage_avg',
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
 * A file with its comments gone: what the reader can actually be shown, and
 * what the code actually does.
 *
 * Scanning raw text would count a rate named in a comment explaining why it
 * needs a denominator — the documentation that keeps this from being undone —
 * as a use of that rate. esbuild drops comments and leaves the property
 * accesses, which is exactly the difference that matters here.
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

// ── A. Producer and reader name the same denominators ─────────────────────

test('the reader looks up the keys _wow_item_counts actually publishes', async () => {
  // A rename on either side would not fail anything else: every lookup would
  // just come back undefined, every rate would read `denominator-unknown`, and
  // the dashboard would go back to showing rates it cannot stand behind —
  // quietly, and everywhere at once.
  const py = await readFile(STEP8_PY, 'utf8');
  const at = py.indexOf('def _wow_item_counts(');
  assert.ok(at >= 0, '_wow_item_counts is gone from step8_grade.py');
  const body = py.slice(py.indexOf('return {', at), py.indexOf('\n    }', at));
  const published = [...body.matchAll(/"([a-z_]+)":/g)].map((m) => m[1]).sort();
  assert.deepEqual(
    published,
    ['critical_items', 'judge_items', 'precheck_items', 'rubric_items'],
    'the denominators step8_grade publishes have changed',
  );

  // The TypeScript shape the cards read them through.
  const ts = await readFile(GRADE_TYPES, 'utf8');
  const iface = ts.slice(
    ts.indexOf('export interface WowItemCounts {'),
    ts.indexOf('}', ts.indexOf('export interface WowItemCounts {')),
  );
  assert.ok(iface.length > 0, 'WowItemCounts is gone from src/types/grade.ts');
  for (const key of published) {
    assert.ok(iface.includes(`${key}?:`), `WowItemCounts does not declare ${key}`);
  }

  // And the three the cards pass to `readWowRate`, named where they are used.
  const users = ['components/wow/StructureVsReasoning.tsx', 'components/wow/HealthStrip.tsx',
    'components/wow/RubricCoverageCard.tsx', 'components/dashboard/GradingAnalysisView.tsx'];
  for (const rel of users) {
    const text = await renderedText(join(SRC_DIR, ...rel.split('/')));
    assert.ok(
      /item_counts/.test(text),
      `${rel} publishes a wow rate without reaching for its denominator`,
    );
  }
});

// ── B. The four standings, run for real ───────────────────────────────────

test('a rate over an empty denominator is not a 0% pass rate', async () => {
  const { readWowRate, PRECHECK_ITEMS_DESCRIBED } = await loadReading();
  // The exact pair 15 of 15 recorded run-level zeros carry today.
  const reading = readWowRate(0.0, 0, PRECHECK_ITEMS_DESCRIBED);
  assert.equal(reading.standing, 'none-counted');
  assert.equal(reading.value, 'not recorded');
  assert.ok(!reading.value.includes('%'), 'a percentage was printed over an empty denominator');
  assert.equal(reading.fraction, null, 'a bar would still be drawn, at the length of total failure');
  assert.equal(reading.comparable, false);
  assert.match(reading.caveat, /not a 0% pass rate/);
  assert.match(reading.caveat, new RegExp(PRECHECK_ITEMS_DESCRIBED));
});

test('a rate with no denominator recorded is shown, and the gap is stated', async () => {
  // Still a live state, not a legacy branch: 6 published run-level payloads
  // predate `item_counts`, and so do all 61 shard payloads and their 364 rows,
  // which a merge reads. (#393 then #399 recovered the published sector rows.)
  const { readWowRate, JUDGE_ITEMS_DESCRIBED } = await loadReading();
  const reading = readWowRate(0.8123, undefined, JUDGE_ITEMS_DESCRIBED);
  assert.equal(reading.standing, 'denominator-unknown');
  assert.equal(reading.value, '81.2%');
  assert.equal(reading.fraction, 0.8123);
  assert.equal(reading.comparable, false, 'an unbacked rate was allowed into a comparison');
  assert.match(reading.caveat, /[Dd]enominator not recorded/);
});

test('a run that published no rate at all says so', async () => {
  const { readWowRate, RUBRIC_ITEMS_DESCRIBED } = await loadReading();
  for (const absent of [null, undefined, Number.NaN]) {
    const reading = readWowRate(absent, undefined, RUBRIC_ITEMS_DESCRIBED);
    assert.equal(reading.standing, 'absent', `${String(absent)} did not read as absent`);
    assert.equal(reading.value, 'not recorded');
    assert.equal(reading.fraction, null);
    assert.equal(reading.comparable, false);
  }
});

test('a measured rate reads exactly as it did before, and carries no caveat', async () => {
  // The regression guard. A new rule must not move a run that really was
  // measured: same percentage, same bar, nothing added underneath it.
  const { readWowRate, PRECHECK_ITEMS_DESCRIBED, JUDGE_ITEMS_DESCRIBED } = await loadReading();
  const precheck = readWowRate(0.5714, 35, PRECHECK_ITEMS_DESCRIBED);
  assert.equal(precheck.standing, 'measured');
  assert.equal(precheck.value, '57.1%');
  assert.equal(precheck.fraction, 0.5714);
  assert.equal(precheck.comparable, true);
  assert.equal(precheck.caveat, undefined, 'a fully measured rate was caveated anyway');

  // Including a genuine total failure: prechecks ran, and every one of them
  // failed. That is a finding, and it must still be shown as one.
  const failed = readWowRate(0.0, 12, JUDGE_ITEMS_DESCRIBED);
  assert.equal(failed.standing, 'measured');
  assert.equal(failed.value, '0.0%');
  assert.equal(failed.fraction, 0, 'a real zero lost its bar');
  assert.equal(failed.caveat, undefined, 'a real zero was explained away as unmeasured');
});

test('a percentage is printed exactly when there is a fraction to draw', async () => {
  const { readWowRate, PRECHECK_ITEMS_DESCRIBED } = await loadReading();
  const states = [
    [0.0, 0], [1.0, 0], [null, null], [undefined, undefined], [Number.NaN, 4],
    [0.0, 12], [0.5714, undefined], [0.5714, 35], [1.0, 1],
  ];
  for (const [rate, counted] of states) {
    const r = readWowRate(rate, counted, PRECHECK_ITEMS_DESCRIBED);
    assert.equal(
      r.value.includes('%'), r.fraction !== null,
      `readWowRate(${String(rate)}, ${String(counted)}) prints ${r.value} but draws ${String(r.fraction)}`,
    );
    if (r.standing !== 'measured') {
      assert.ok(r.caveat, `the ${r.standing} state was published with nothing said about it`);
      assert.equal(r.comparable, false, `${r.standing} was allowed into a comparison`);
    }
  }
});

// ── C. Comparison needs both sides measured ───────────────────────────────

test('the structure-vs-reasoning verdict is withheld unless both sides were measured', async () => {
  const {
    readWowRate, structureVsReasoningInsight,
    PRECHECK_ITEMS_DESCRIBED, JUDGE_ITEMS_DESCRIBED,
  } = await loadReading();

  // The published shape of the 185-task gold-ceiling run: 8,816 judged items,
  // zero prechecked ones. Subtracting gave "Strong on reasoning, weak on
  // structure" for a check that never ran.
  const noPrecheck = readWowRate(0.0, 0, PRECHECK_ITEMS_DESCRIBED);
  const judged = readWowRate(0.81, 8816, JUDGE_ITEMS_DESCRIBED);
  assert.equal(
    structureVsReasoningInsight(noPrecheck, judged), null,
    'a run that never prechecked is still being called weak on structure',
  );

  // An unrecorded denominator is not a licence either.
  assert.equal(
    structureVsReasoningInsight(
      readWowRate(0.0, undefined, PRECHECK_ITEMS_DESCRIBED), judged,
    ),
    null,
    'a rate with no denominator behind it was compared anyway',
  );
});

test('two measured rates still produce the verdict they always did', async () => {
  // The other half of the regression guard: the wording of every band is
  // unchanged, so a run that really was measured reads identically.
  const { readWowRate, structureVsReasoningInsight,
    PRECHECK_ITEMS_DESCRIBED, JUDGE_ITEMS_DESCRIBED } = await loadReading();
  const pre = (r) => readWowRate(r, 40, PRECHECK_ITEMS_DESCRIBED);
  const jud = (r) => readWowRate(r, 40, JUDGE_ITEMS_DESCRIBED);
  const cases = [
    [0.80, 0.79, 'Balanced structure and reasoning'],
    [0.90, 0.60, 'Strong on structure, weak on reasoning'],
    [0.55, 0.90, 'Strong on reasoning, weak on structure'],
    [0.90, 0.80, 'Slightly stronger on structure'],
    [0.80, 0.90, 'Slightly stronger on reasoning'],
  ];
  for (const [p, j, expected] of cases) {
    assert.equal(
      structureVsReasoningInsight(pre(p), jud(j)), expected,
      `precheck ${p} vs judge ${j} no longer reads as "${expected}"`,
    );
  }
});

// ── D. What is said instead names the missing side ────────────────────────

test('the absence is stated as a finding, not as a glitch', async () => {
  const {
    readWowRate, structureVsReasoningAbsence,
    PRECHECK_ITEMS_DESCRIBED, JUDGE_ITEMS_DESCRIBED,
  } = await loadReading();

  const noPrecheck = structureVsReasoningAbsence(
    readWowRate(0.0, 0, PRECHECK_ITEMS_DESCRIBED),
    readWowRate(0.81, 8816, JUDGE_ITEMS_DESCRIBED),
  );
  assert.match(noPrecheck, /rated no items/, 'an empty denominator was not named as such');
  assert.match(noPrecheck, /precheck/, 'the sentence does not say which side is missing');
  assert.ok(!/LLM judge/.test(noPrecheck), 'the measured side was blamed too');

  const unknown = structureVsReasoningAbsence(
    readWowRate(0.0, undefined, PRECHECK_ITEMS_DESCRIBED),
    readWowRate(0.81, undefined, JUDGE_ITEMS_DESCRIBED),
  );
  assert.match(unknown, /not recorded/, 'an unrecorded denominator reads as a zero one');
  assert.match(unknown, /precheck and LLM judge/, 'both missing sides are not both named');

  // And the two states are not collapsed into one sentence.
  assert.notEqual(noPrecheck, unknown);
});

// ── E. No surface reads these rates without the denominator ───────────────

test('every src/ surface that reads one of these rates goes through readWowRate', async () => {
  // The guard that fails on the code this replaced: `HealthStrip`,
  // `StructureVsReasoning`, `SectorHeatmap`, `RubricCoverageCard` and
  // `GradingAnalysisView` all formatted these rates straight into the page.
  // Comments are stripped first, so a file may still explain the hazard.
  const offenders = [];
  for (const file of await sourceFiles()) {
    const rel = relative(ROOT, file);
    if (rel.endsWith('rateReading.ts') || rel.startsWith(join('src', 'types'))) continue;
    const text = await renderedText(file);
    const used = RATE_KEYS.filter((key) => text.includes(key));
    if (used.length > 0 && !text.includes('readWowRate')) {
      offenders.push(`${rel}: ${used.join(', ')}`);
    }
  }
  assert.deepEqual(
    offenders, [],
    'a dashboard surface prints a wow pass rate without checking what it was divided by',
  );
});
