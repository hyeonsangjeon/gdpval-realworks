// An error rate nobody measured is not an error rate of zero.
//
// `summary.wow.judge_error_rate` was the last of the five `wow` rates with no
// reader, and the only one a surface *coloured*. `GradingAnalysisView` asked:
//
//     className={(wow.judge_error_rate ?? 0) > 0.05 ? red : emerald}
//
// so a run that published no rate scored `0`, failed the comparison, and was
// painted the emerald this dashboard uses for a healthy run — sitting between
// two neighbours that correctly printed `—` for the very same absence.
//
// The polarity is what makes this different from #398 and #148. For a pass
// rate, absence and zero both mean "no percentage to show", so rounding one
// into the other omits a finding. For an error rate zero is the *good* news,
// so the same rounding does not omit a finding — it asserts the opposite one.
//
// The state is reachable, and test A below reaches it through the real
// aggregator rather than describing it: schema 1.0–1.2 is checked by
// `validateHistoricalHeadline`, which reads six `openai_compat` keys and never
// looks at `wow` at all, and `aggregate-grades.mjs` then publishes
// `summary.wow || {}`. Sixteen of the nineteen published grade files are 1.0 or
// 1.1. All sixteen carry a numeric rate today, so no page renders the green
// pill right now — this is latent, in the way #104 and #150 were latent, and
// the guard that keeps it that way did not exist for that tier.
//
// This file holds six things in place:
//
//   A. the aggregator really does emit `wow: {}` for a file it accepts;
//   B. the expression that was there reads that emission as healthy;
//   C. the four standings of `readJudgeErrorRate`, run for real, with `alert`
//      and `reassuring` both false whenever nothing was measured;
//   D. a rate that really was measured reads exactly as it did before;
//   E. no surface under src/ reads the rate without going through the reader;
//   F. `WowSummary` stops declaring the five rates as always present.
//
// (B) and (E) are the guards that fail on the code this replaced.
//
// Run:
//   node --test scripts/__tests__/an-unmeasured-error-rate-is-not-a-clean-run.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import { processGradesFile } from '../aggregate-grades.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const READING_FILE = join(SRC_DIR, 'components', 'wow', 'rateReading.ts');
const GRADE_TYPES = join(SRC_DIR, 'types', 'grade.ts');

/** The five `wow` rates, all of which the producer may omit. */
const WOW_RATES = [
  'rubric_item_coverage_avg',
  'critical_item_pass_rate',
  'precheck_pass_rate',
  'judge_pass_rate',
  'judge_error_rate',
];

/**
 * A grade file in the tier nothing checks `wow` for, otherwise entirely valid.
 *
 * Schema 1.1 rather than 1.3: `validateScoreExcludedGrade` guards 1.3 and 1.4
 * and would refuse this file outright, which is the stronger answer and is left
 * exactly as it is. This is the tier that holds sixteen of the nineteen
 * published files and has no such guard.
 */
function historicalGradeWithoutWow() {
  return {
    schema_version: '1.1',
    experiment_id: 'no-wow-block',
    summary: {
      total_tasks: 2,
      graded_tasks: 2,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 50,
        ci_pct: 1,
        perfect_count: 1,
        partial_count: 1,
        zero_count: 0,
        inconsistent_count: 0,
      },
      // and no `wow` key at all
    },
    tasks: [
      { task_id: 't1', pct: 100, grade_status: 'graded_v1' },
      { task_id: 't2', pct: 0, grade_status: 'graded_v1' },
    ],
  };
}

/**
 * The reading rule, type annotations stripped and nothing else touched.
 *
 * A failure to load is a real failure and is left to throw, for the reason the
 * sibling suite gives: skipping would leave this file green while every
 * executable assertion in it quietly stopped running.
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

/** A file with its comments gone: what the code actually does. */
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

// ── A. The aggregator really does publish the empty block ─────────────────

test('a historical grade file with no wow block is accepted and published as {}', () => {
  const out = processGradesFile('no-wow-block.json', historicalGradeWithoutWow());

  assert.ok(out, 'the file was dropped instead of published');
  assert.deepEqual(
    out.summary_v1.wow, {},
    'the emitted wow block is no longer the empty object this defect rides on',
  );
  assert.equal(
    out.summary_v1.wow.judge_error_rate, undefined,
    'the rate arrived from somewhere — the premise of this file has changed',
  );
});

test('the stricter tier still refuses the same file outright', () => {
  // Not a fix this change makes, and deliberately not weakened by it: 1.3 and
  // 1.4 reject a missing health summary, which is the better answer. The point
  // is that 1.0-1.2 does not, and that is where the published corpus lives.
  const raw = { ...historicalGradeWithoutWow(), schema_version: '1.3' };
  assert.throws(
    () => processGradesFile('no-wow-block.json', raw),
    /health summary is missing or invalid/,
  );
});

// ── B. What the expression that was there did with it ─────────────────────

test('the replaced comparison reads the empty block as healthy', () => {
  // The line this change removes, run against the value test A just measured.
  // It is kept executable rather than described so the claim in the commit
  // message is checkable, and so re-introducing the form fails here.
  const emitted = processGradesFile('no-wow-block.json', historicalGradeWithoutWow());
  const rate = emitted.summary_v1.wow.judge_error_rate;

  assert.equal(
    (rate ?? 0) > 0.05, false,
    'the old expression no longer treats an absent rate as under the threshold',
  );
  // Which is the same answer it gives for a run measured at a genuine 0%.
  assert.equal((0 ?? 0) > 0.05, false);
});

// ── C. The four standings, run for real ───────────────────────────────────

test('an absent rate is neither an alarm nor a clean bill of health', async () => {
  const { readJudgeErrorRate } = await loadReading();
  for (const absent of [null, undefined, Number.NaN]) {
    const reading = readJudgeErrorRate(absent, undefined);
    assert.equal(reading.standing, 'absent', `${String(absent)} did not read as absent`);
    assert.equal(reading.value, '—', 'a percentage was printed for a rate nobody published');
    assert.equal(reading.alert, false);
    assert.equal(
      reading.reassuring, false,
      'a run that published no error rate was shown as a run that had no errors',
    );
    assert.match(reading.caveat, /unmeasured/);
  }
});

test('a rate over an empty denominator is not a run the judge got through', async () => {
  const { readJudgeErrorRate } = await loadReading();
  const reading = readJudgeErrorRate(0.0, 0);
  assert.equal(reading.standing, 'none-counted');
  assert.equal(reading.value, '—');
  assert.equal(reading.alert, false);
  assert.equal(reading.reassuring, false, 'nothing was judged, and it was called clean');
  assert.match(reading.caveat, /no item in this run/);
});

test('alert and reassuring are never both true, and never both silent about why', async () => {
  const { readJudgeErrorRate } = await loadReading();
  const states = [
    [0.0, 0], [0.0, 8816], [null, null], [undefined, 12], [Number.NaN, 4],
    [0.0319, 5153], [0.0319, undefined], [0.06, 900], [1.0, 4], [0.05, 100],
  ];
  for (const [rate, counted] of states) {
    const r = readJudgeErrorRate(rate, counted);
    assert.ok(
      !(r.alert && r.reassuring),
      `readJudgeErrorRate(${String(rate)}, ${String(counted)}) is both alarming and reassuring`,
    );
    assert.equal(
      r.value.includes('%'), r.standing === 'measured' || r.standing === 'denominator-unknown',
      `readJudgeErrorRate(${String(rate)}, ${String(counted)}) prints ${r.value} for a ${r.standing} rate`,
    );
    if (r.standing !== 'measured') {
      assert.ok(r.caveat, `the ${r.standing} state was published with nothing said about it`);
    }
    if (!r.alert && !r.reassuring) {
      assert.ok(
        !r.value.includes('%'),
        'a percentage was shown with neither reading attached to it',
      );
    }
  }
});

// ── D. A measured rate reads exactly as it did before ─────────────────────

test('a measured rate keeps its number, its threshold and its silence', async () => {
  const { readJudgeErrorRate, JUDGE_ERROR_ALERT_THRESHOLD } = await loadReading();
  assert.equal(JUDGE_ERROR_ALERT_THRESHOLD, 0.05, 'the published threshold moved');

  // The rate the sol-220 run published, and the shape of the twelve payloads
  // that record a judge denominator — none of which is zero, so this change
  // moves no published row.
  const healthy = readJudgeErrorRate(0.0319, 5153);
  assert.equal(healthy.standing, 'measured');
  assert.equal(healthy.value, '3.2%');
  assert.equal(healthy.alert, false);
  assert.equal(healthy.reassuring, true, 'a measured, low error rate lost its green');
  assert.equal(healthy.caveat, undefined, 'a fully measured rate was caveated anyway');

  // A genuine zero is a finding, and stays one.
  const clean = readJudgeErrorRate(0.0, 8816);
  assert.equal(clean.standing, 'measured');
  assert.equal(clean.value, '0.0%');
  assert.equal(clean.reassuring, true, 'a real clean run lost its green');

  // And the alarm still fires where it always did.
  const faulty = readJudgeErrorRate(0.0595, 1200);
  assert.equal(faulty.alert, true, 'a rate over the threshold stopped alarming');
  assert.equal(faulty.reassuring, false);
  assert.equal(readJudgeErrorRate(0.05, 1200).alert, false, 'the threshold became inclusive');
});

test('a rate published without its denominator is still shown, and said to be', async () => {
  // Six of the eighteen run-level payloads carrying `wow` record no judge
  // denominator. The run did publish the number, so it is not withheld — but
  // it cannot be checked against what it was divided by, and that is stated.
  const { readJudgeErrorRate } = await loadReading();
  const reading = readJudgeErrorRate(0.0036, undefined);
  assert.equal(reading.standing, 'denominator-unknown');
  assert.equal(reading.value, '0.4%');
  assert.equal(reading.alert, false);
  assert.equal(reading.reassuring, true, 'a published low rate was withdrawn, not just caveated');
  assert.match(reading.caveat, /[Dd]enominator not recorded/);
});

// ── E. No surface reads the rate without the reader ───────────────────────

test('every src/ surface that reads judge_error_rate goes through readJudgeErrorRate', async () => {
  // The guard that fails on the code this replaced. Comments are stripped
  // first, so a file may still explain the hazard without tripping it.
  const offenders = [];
  for (const file of await sourceFiles()) {
    const rel = relative(ROOT, file);
    if (rel.endsWith('rateReading.ts') || rel.startsWith(join('src', 'types'))) continue;
    const text = await renderedText(file);
    if (text.includes('judge_error_rate') && !text.includes('readJudgeErrorRate')) {
      offenders.push(rel);
    }
  }
  assert.deepEqual(
    offenders, [],
    'a dashboard surface colours the judge error rate without checking it was measured',
  );
});

// ── F. The type stops claiming the rates are always there ─────────────────

test('WowSummary declares every rate as one the producer may omit', async () => {
  // Declaring these `number` is how the unguarded read type-checked. It does
  // not catch the `?? 0` form — that is what the reader above is for — but a
  // bare `wow.judge_error_rate > 0.05` is now a compile error rather than a
  // green pill, and the declaration no longer promises what `summary.wow || {}`
  // cannot deliver.
  const ts = await readFile(GRADE_TYPES, 'utf8');
  const start = ts.indexOf('export interface WowSummary {');
  assert.ok(start >= 0, 'WowSummary is gone from src/types/grade.ts');
  const iface = ts.slice(start, ts.indexOf('\n}', start));
  for (const rate of WOW_RATES) {
    assert.ok(
      iface.includes(`${rate}?:`),
      `WowSummary still declares ${rate} as always present`,
    );
  }
});
