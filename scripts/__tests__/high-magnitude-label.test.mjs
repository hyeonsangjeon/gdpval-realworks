// A metric that decides nothing must not be labelled like one, and a rate over
// no items must not print as `0.0%`.
//
// `summary.wow.critical_item_pass_rate` was published under "Critical Items
// (weight ≥ 3)" and described as the "must-have" requirements. Three separate
// things in that sentence are false:
//
//   1. the rubric's own `required` field is null on all 10,453 items across all
//      220 tasks, so nothing marks these items must-have — `core/grader.py`
//      substitutes `abs(max_score) >= MAGNITUDE_THRESHOLD`;
//   2. the threshold is 4, not 3, and it reads the score magnitude rather than
//      any weight field;
//   3. it was a pass gate in `scripts/analyze_gold_ceiling.py` and a headline
//      card on the dashboard, so a heuristic decided verdicts.
//
// The owner's decision of 2026-09-03 (recorded in
// `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`) kept the threshold and
// the published JSON keys exactly where they were, and changed the name, the
// standing, and what happens when the denominator is empty. This file holds all
// four halves of that decision in place:
//
//   A. the two languages agree on the two numbers, so neither can drift;
//   B. the Python side really has stopped gating on it;
//   C. no dashboard surface still claims "required", "must-have", or "≥ 3";
//   D. an unrecorded or empty denominator reads as "not recorded", never `0%`.
//
// (D) runs the real decision function rather than pattern-matching the JSX
// around it: `src/components/wow/highMagnitudeReading.ts` is import-free
// precisely so esbuild — already installed, as vite depends on it — can hand it
// to node.
//
// Run:
//   node --test scripts/__tests__/high-magnitude-label.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const READING_FILE = join(SRC_DIR, 'components', 'wow', 'highMagnitudeReading.ts');
const GRADER_PY = join(ROOT, 'batch-runner', 'core', 'grader.py');
const CEILING_PY = join(ROOT, 'batch-runner', 'scripts', 'analyze_gold_ceiling.py');

// ── Loading the decision under test ───────────────────────────────────────

/**
 * The reading rule, type annotations stripped and nothing else touched.
 *
 * A failure to load is a real failure and is left to throw. Skipping here
 * would leave the suite green while the only executable assertions in it —
 * (D) below — quietly stopped running, which is the same class of mistake the
 * whole change is about.
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
 * A file with its comments gone: what the reader can actually be shown.
 *
 * Scanning the raw text would ban the comments that quote the old label in
 * order to explain why it was wrong, which is the documentation that keeps this
 * from being undone. esbuild drops comments and turns JSX text into string
 * arguments, so what survives is the copy and nothing else.
 *
 * `.d.ts` files are the exception: they emit no runtime code, so there is
 * nothing to transform and they are scanned whole. That errs toward checking
 * more than necessary rather than less.
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

/** A module-level Python assignment, read out of the file rather than guessed. */
function pyConstant(source, name, file) {
  const m = source.match(new RegExp(`^${name}(?:\\s*:\\s*\\w+)?\\s*=\\s*([^\\n#]+)`, 'm'));
  assert.ok(m, `${name} is not assigned at module level in ${file}`);
  return m[1].trim();
}

// ── A. The two languages name the same two numbers ────────────────────────

test('HIGH_MAGNITUDE_MIN_ABS_SCORE equals the grader’s MAGNITUDE_THRESHOLD', async () => {
  // The label said "weight ≥ 3" while the grader thresholded at 4. Nothing
  // caught it because no test read both files. This one does.
  const { HIGH_MAGNITUDE_MIN_ABS_SCORE } = await loadReading();
  const declared = Number(
    pyConstant(await readFile(GRADER_PY, 'utf8'), 'MAGNITUDE_THRESHOLD', 'core/grader.py'),
  );
  assert.equal(
    HIGH_MAGNITUDE_MIN_ABS_SCORE, declared,
    'the dashboard and core/grader.py disagree about which items are high-magnitude',
  );
});

test('MIN_READABLE_HIGH_MAGNITUDE_ITEMS is derived from the same floor the analyzer uses', async () => {
  const { MIN_READABLE_HIGH_MAGNITUDE_ITEMS } = await loadReading();
  const ceiling = await readFile(CEILING_PY, 'utf8');
  const floor = Number(
    pyConstant(ceiling, 'CRITICAL_ITEM_PASS_FLOOR', 'scripts/analyze_gold_ceiling.py'),
  );
  assert.ok(floor > 0 && floor < 1, `CRITICAL_ITEM_PASS_FLOOR is not a rate: ${floor}`);

  // Derived, not chosen. Below `ceil(1 / (1 - floor))` items a single failure
  // costs more than the whole distance from the floor to a clean sweep.
  assert.equal(
    MIN_READABLE_HIGH_MAGNITUDE_ITEMS, Math.ceil(1 / (1 - floor)),
    'the dashboard’s readability floor no longer follows from CRITICAL_ITEM_PASS_FLOOR',
  );

  // And the Python side must still derive it rather than hard-code the answer,
  // or the two agree today by coincidence.
  assert.match(
    pyConstant(ceiling, 'MIN_USABLE_REQUIRED_ITEMS', 'scripts/analyze_gold_ceiling.py'),
    /math\.ceil\(\s*1\.0\s*\/\s*\(\s*1\.0\s*-\s*CRITICAL_ITEM_PASS_FLOOR\s*\)\s*\)/,
    'MIN_USABLE_REQUIRED_ITEMS stopped deriving itself from CRITICAL_ITEM_PASS_FLOOR',
  );
});

// ── B. It really has stopped deciding the stage ───────────────────────────

test('the gold-ceiling analyzer gates on two things, and this is not one of them', async () => {
  const source = await readFile(CEILING_PY, 'utf8');

  assert.equal(
    pyConstant(source, 'CRITICAL_ITEM_PASS_DECIDES_VERDICT', 'scripts/analyze_gold_ceiling.py'),
    'False',
    'the high-magnitude heuristic is back to deciding the gold-ceiling verdict',
  );

  // `all_gates_met` is what the exit code and every reader key off, so the
  // check that matters is membership of `gates`, not the presence of a flag.
  const start = source.indexOf('\n    gates = {');
  assert.ok(start >= 0, 'the gates dict is no longer built where this test looks');
  const end = source.indexOf('\n    }\n', start);
  const gates = source.slice(start, end);
  assert.ok(gates.includes('"mean_score_pct"'), 'the mean-score gate disappeared');
  assert.ok(gates.includes('"judge_error_rate"'), 'the judge-error gate disappeared');
  assert.ok(
    !gates.includes('critical'),
    'a critical/high-magnitude key is back inside `gates`, so it decides the exit code again',
  );
});

// ── C. No surface still claims these items are required ───────────────────

test('no dashboard surface calls the high-magnitude items required', async () => {
  // Each phrase below was live on the board. `required` on its own is not
  // banned — the card copy needs the word to explain that the rubric's field is
  // null. Comments are exempt, because the ones that quote the old label are
  // there to say it was wrong; see `renderedText`.
  const banned = [
    'weight ≥ 3',
    'weight >= 3',
    'Critical ≥3',
    'Critical Items',
    'must-have',
    'highest-stakes',
  ];
  const offenders = [];
  for (const file of await sourceFiles()) {
    const text = await renderedText(file);
    for (const phrase of banned) {
      if (text.includes(phrase)) offenders.push(`${relative(ROOT, file)}: ${phrase}`);
    }
  }
  assert.deepEqual(
    offenders, [],
    'a dashboard label still presents the |max score| >= 4 heuristic as a requirement',
  );
});

test('the tooltip states the substitution instead of hiding it', async () => {
  const text = await readFile(join(SRC_DIR, 'data', 'tooltipTexts.ts'), 'utf8');
  const start = text.indexOf('highMagnitudeItems:');
  assert.ok(start >= 0, 'the high-magnitude tooltip is gone');
  const tip = text.slice(start, text.indexOf('\n    ', text.indexOf('",', start)));

  assert.ok(tip.includes('`required`'), 'the tooltip does not mention the rubric’s required field');
  assert.ok(/null/.test(tip), 'the tooltip does not say the required field is null');
  assert.ok(
    /not a pass gate/i.test(tip),
    'the tooltip no longer says this is not a pass gate',
  );
});

test('the card is not in the headline row it was demoted out of', async () => {
  const page = await readFile(join(SRC_DIR, 'pages', 'GradeDetail.tsx'), 'utf8');
  const marker = '<HighMagnitudeItemCard';
  const at = page.indexOf(marker);
  assert.ok(at >= 0, 'the high-magnitude card is not rendered at all');

  // The headline cards live in the first grid; this one has to come after the
  // heatmap, which is the last of them.
  const heatmap = page.indexOf('<SectorHeatmap');
  assert.ok(heatmap >= 0, 'the sector heatmap is gone');
  assert.ok(
    at > heatmap,
    'the high-magnitude card is back above the headline cards, where it reads as one',
  );
});

// ── D. An empty denominator is a state, not a zero ────────────────────────

test('a run that counted nothing is not reported as a 0% pass rate', async () => {
  const { readHighMagnitudeRate } = await loadReading();
  // `step8_grade._rate` returns 0.0 on an empty denominator, so this is the
  // exact pair 5 rows in the published corpus carry today — 4 sector rows and
  // 1 run-level payload, out of 86 and 33 that carry the rate. (An earlier
  // version of this line said 45 of 447 published sector rows; 447 folds in the
  // 364 rows inside the `_shards/` payloads, which are published nowhere and
  // record no denominator at all, so none of them is in *this* state.)
  const reading = readHighMagnitudeRate(0.0, 0);
  assert.equal(reading.value, 'not recorded');
  assert.ok(!reading.value.includes('%'), 'a percentage was printed for an empty denominator');
  assert.match(reading.denominator, /No item in this run scored/);
});

test('a run that published no rate at all says so', async () => {
  const { readHighMagnitudeRate } = await loadReading();
  for (const absent of [null, undefined, Number.NaN]) {
    const reading = readHighMagnitudeRate(absent, undefined);
    assert.equal(reading.value, 'not recorded', `${String(absent)} did not read as absent`);
  }
});

test('a rate with no denominator behind it is shown, and the gap is stated', async () => {
  // Once the common case, and still a live one: `item_counts` was added after
  // most payloads were written, and #393 then #399 recovered it across the
  // published side — 6 of the 33 published run-level payloads still record no
  // count, and none of their 86 sector rows. All 61 shard payloads and all 364
  // of their rows do, and a merge reads shards.
  const { readHighMagnitudeRate } = await loadReading();
  const reading = readHighMagnitudeRate(0.5714, undefined);
  assert.equal(reading.value, '57.1%');
  assert.match(reading.denominator, /not recorded/i);
  assert.equal(reading.caveat, undefined, 'an unknown count cannot support a specific caveat');
});

test('a denominator too thin to read carries the warning, and a full one does not', async () => {
  const { readHighMagnitudeRate, MIN_READABLE_HIGH_MAGNITUDE_ITEMS } = await loadReading();

  const thin = readHighMagnitudeRate(0.5714, 35 - (35 - 1)); // 1 item
  assert.equal(thin.value, '57.1%');
  assert.match(thin.denominator, /Over 1 item\(s\)/);
  assert.ok(thin.caveat, 'a single-item rate was published with no warning');

  const edge = readHighMagnitudeRate(0.95, MIN_READABLE_HIGH_MAGNITUDE_ITEMS - 1);
  assert.ok(edge.caveat, `${MIN_READABLE_HIGH_MAGNITUDE_ITEMS - 1} items should still warn`);

  // Stage 1's real denominator: 35 items, above the floor.
  const readable = readHighMagnitudeRate(0.5714, 35);
  assert.equal(readable.value, '57.1%');
  assert.match(readable.denominator, /Over 35 item\(s\)/);
  assert.equal(readable.caveat, undefined, '35 items was warned about anyway');
});

test('every reading names its denominator, whatever state it is in', async () => {
  const { readHighMagnitudeRate } = await loadReading();
  const states = [
    [0.0, 0], [null, null], [undefined, undefined], [0.5714, undefined],
    [0.5714, 1], [0.5714, 35], [1.0, 0], [0.0, 355],
  ];
  for (const [rate, counted] of states) {
    const reading = readHighMagnitudeRate(rate, counted);
    assert.ok(
      reading.denominator && reading.denominator.length > 0,
      `readHighMagnitudeRate(${String(rate)}, ${String(counted)}) printed a bare number`,
    );
  }
});
