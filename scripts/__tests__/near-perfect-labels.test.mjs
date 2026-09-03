// A band named after an exact figure has to be counted at that figure, or
// renamed.
//
// `summary.openai_compat.perfect_count` and `zero_count` are counted by the
// grading backend at **>= 99%** and **<= 1%**. The dashboard printed them under
// "Perfect (100%)" and "Zero (0%)", and defined those terms as "Score = 100%"
// and "Score = 0%". Two rows published today are why that is not a quibble: one
// task scored 99.77% and one scored 0.9%, and the aggregator snaps a row's
// `avg_score` to a flat 1.0/0.0 once it crosses a band boundary so the Status
// badge agrees with the count — which left the 99.77 rendering as "100%" in its
// own score column, under a "Perfect" badge, inside a "Perfect (100%)" total.
//
// PR #371 fixed the backend's wording and deliberately did NOT move the
// threshold, because the counts are already published and moving a boundary
// would restate every run on the board. This file holds the dashboard to the
// same two decisions:
//
//   1. the boundary does not move, and the two files that name it agree;
//   2. no published count changes — the snap is untouched, so the recount of
//      snapped rows still equals `perfect_count` / `zero_count` exactly;
//   3. the row can still state its own score, via `pct_exact`, which is present
//      on exactly the rows the snap moved and absent everywhere else so that a
//      row which was already correct renders byte-identically to before.
//
// Run:
//   node --test scripts/__tests__/near-perfect-labels.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  processGradesFile,
  NEAR_PERFECT_MIN_PCT,
  NEAR_ZERO_MAX_PCT,
} from '../aggregate-grades.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const GRADES_DIR = join(ROOT, 'data', 'grades');
const BANDS_FILE = join(SRC_DIR, 'data', 'scoreBands.ts');

// ── Fixtures ──────────────────────────────────────────────────────────────

/** One rubric item, in the shape the strict validator accepts. */
function item(maxScore, awarded) {
  return {
    rubric_item_id: `i-${maxScore}-${awarded}`,
    max_score: maxScore,
    awarded_score: awarded,
    verdict: awarded >= maxScore ? 'pass' : awarded > 0 ? 'partial' : 'fail',
    decided_by: 'judge',
    score_excluded: false,
  };
}

/**
 * A task worth `maxScore` that earned `awarded`, so its `pct` is whatever the
 * two make it. Written this way rather than by setting `pct` directly so the
 * row's own totals agree with its percentage, as a real grade file's do.
 */
function task(taskId, maxScore, awarded) {
  const items = [item(maxScore, awarded)];
  return {
    task_id: taskId,
    sector: 'test',
    occupation: 'test',
    items,
    total_awarded: Number(awarded.toFixed(4)),
    total_max: maxScore,
    pct: Number(((awarded / maxScore) * 100).toFixed(2)),
    critical_fail: false,
    error: null,
  };
}

/** A payload whose published counts are computed at the real thresholds. */
function grade(tasks) {
  const pcts = tasks.map((t) => t.pct);
  const avg = pcts.length
    ? Number((pcts.reduce((a, b) => a + b, 0) / pcts.length).toFixed(2))
    : null;
  return {
    schema_version: '1.2',
    experiment_id: 'exp-bands',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    tasks,
    summary: {
      total_tasks: tasks.length,
      graded_tasks: tasks.length,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: avg,
        ci_pct: 1.5,
        perfect_count: pcts.filter((p) => p >= NEAR_PERFECT_MIN_PCT).length,
        zero_count: pcts.filter((p) => p <= NEAR_ZERO_MAX_PCT).length,
        partial_count: pcts.filter(
          (p) => p > NEAR_ZERO_MAX_PCT && p < NEAR_PERFECT_MIN_PCT,
        ).length,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 0 },
    },
  };
}

/**
 * One task per interesting position relative to the two boundaries.
 *
 * The two "near" rows are the real published figures, not invented ones: 99.77
 * and 0.9 are the scores of the two rows this whole change exists for.
 */
const EXACT_FULL = 'a-exact-100';
const NEAR_FULL = 'b-near-99';
const MIDDLE = 'c-middle-50';
const NEAR_NONE = 'd-near-0';
const EXACT_NONE = 'e-exact-0';

function bandSpread() {
  return grade([
    task(EXACT_FULL, 10, 10),      // 100.00 — genuinely full marks
    task(NEAR_FULL, 1, 0.9977),    //  99.77 — counted perfect, is not
    task(MIDDLE, 10, 5),           //  50.00 — untouched by either boundary
    task(NEAR_NONE, 1, 0.009),     //   0.90 — counted zero, is not
    task(EXACT_NONE, 10, 0),       //   0.00 — genuinely nothing
  ]);
}

/** Rows keyed by task_id, as the dashboard receives them. */
function rowsOf(raw, filename = 'g.json') {
  const record = processGradesFile(filename, raw);
  assert.ok(record, 'the fixture did not survive the aggregator at all');
  return new Map(record.tasks.map((t) => [t.task_id, t]));
}

/** Every .ts/.tsx file under src/, so a new surface cannot dodge the scan. */
async function sourceFiles(dir = SRC_DIR, acc = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) await sourceFiles(full, acc);
    else if (['.ts', '.tsx'].includes(extname(entry.name))) acc.push(full);
  }
  return acc;
}

// ── 1. The boundary is named in two files and they must agree ─────────────

test('scoreBands.ts and the aggregator name the same two thresholds', async () => {
  const src = await readFile(BANDS_FILE, 'utf8');
  const declared = (name) => {
    const m = src.match(new RegExp(`export const ${name} = (\\d+(?:\\.\\d+)?)\\b`));
    assert.ok(m, `${name} is not exported from src/data/scoreBands.ts`);
    return Number(m[1]);
  };
  assert.equal(
    declared('NEAR_PERFECT_MIN_PCT'), NEAR_PERFECT_MIN_PCT,
    'the dashboard and the aggregator disagree about where "near-perfect" starts',
  );
  assert.equal(
    declared('NEAR_ZERO_MAX_PCT'), NEAR_ZERO_MAX_PCT,
    'the dashboard and the aggregator disagree about where "near-zero" ends',
  );
});

test('every band label interpolates its threshold instead of restating it', async () => {
  const src = await readFile(BANDS_FILE, 'utf8');
  // A label that spells the number out is a label that stops being true the
  // day the constant moves, which is the failure this module was made to end.
  const mustInterpolate = {
    NEAR_PERFECT_LABEL: ['NEAR_PERFECT_MIN_PCT'],
    NEAR_ZERO_LABEL: ['NEAR_ZERO_MAX_PCT'],
    NEAR_PERFECT_DEF: ['NEAR_PERFECT_MIN_PCT'],
    NEAR_ZERO_DEF: ['NEAR_ZERO_MAX_PCT'],
    PARTIAL_DEF: ['NEAR_ZERO_MAX_PCT', 'NEAR_PERFECT_MIN_PCT'],
  };
  for (const [name, needed] of Object.entries(mustInterpolate)) {
    const start = src.indexOf(`export const ${name} =`);
    assert.ok(start >= 0, `${name} is not exported from src/data/scoreBands.ts`);
    const next = src.indexOf('\nexport ', start + 1);
    const decl = src.slice(start, next === -1 ? src.length : next);
    for (const constant of needed) {
      assert.ok(
        decl.includes('${' + constant + '}'),
        `${name} states its threshold as a literal instead of interpolating ${constant}`,
      );
    }
  }
});

// ── 2. The snap is untouched, so no published count moves ─────────────────

test('the snap still puts every row in the band its count was taken from', () => {
  const raw = bandSpread();
  const rows = rowsOf(raw);
  const compat = raw.summary.openai_compat;

  const snappedFull = [...rows.values()].filter((t) => t.avg_score === 1).length;
  const snappedNone = [...rows.values()].filter((t) => t.avg_score === 0).length;

  assert.equal(snappedFull, compat.perfect_count, 'the perfect count moved');
  assert.equal(snappedNone, compat.zero_count, 'the zero count moved');
  assert.equal(snappedFull, 2, 'the near-perfect row left the perfect band');
  assert.equal(snappedNone, 2, 'the near-zero row left the zero band');
});

// ── 3. The row can state its own score again ──────────────────────────────

test('pct_exact is present on exactly the rows the snap moved', () => {
  const rows = rowsOf(bandSpread());

  assert.equal(rows.get(NEAR_FULL).pct_exact, 99.77);
  assert.equal(rows.get(NEAR_NONE).pct_exact, 0.9);

  for (const id of [EXACT_FULL, MIDDLE, EXACT_NONE]) {
    assert.ok(
      !Object.prototype.hasOwnProperty.call(rows.get(id), 'pct_exact'),
      `${id} gained pct_exact although the snap never moved it — a row that was `
      + 'already correct must render byte-identically to before',
    );
  }
});

test('a row the snap moved keeps the band it was counted in', () => {
  const rows = rowsOf(bandSpread());
  // The point of `pct_exact` is to say the score without changing the verdict.
  assert.equal(rows.get(NEAR_FULL).avg_score, 1);
  assert.equal(rows.get(NEAR_NONE).avg_score, 0);
});

// ── 4. The same two invariants, on the grades actually published ──────────

// The published-count reconciliation is asserted on the fixture above rather
// than here, because a real file can miss it for a reason that predates this
// change and is not the dashboard's to fix: exp003's `zero_count` is 4 while
// only 3 rows score zero, the fourth being a task that errored with
// `no_deliverables` and which the dashboard already renders as an error rather
// than as a verdict of zero. What IS this change's to answer for is where
// `pct_exact` lands on real rows, and that is what this checks — against each
// file's own raw percentages, so a regression that dropped the key, or carried
// it onto a row that never needed it, fails here on published data.
test('published rows carry pct_exact on exactly the percentages that need it', async () => {
  const files = (await readdir(GRADES_DIR))
    .filter((f) => extname(f) === '.json')
    .sort();
  assert.ok(files.length > 0, 'no grade files to check');

  let checked = 0;
  let carried = 0;
  for (const f of files) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, f), 'utf8'));
    const record = processGradesFile(f, raw);
    if (!record) continue;

    const rawPct = new Map(
      (raw.tasks ?? [])
        .filter((t) => t?.task_id && typeof t.pct === 'number')
        .map((t) => [t.task_id, t.pct]),
    );

    for (const row of record.tasks) {
      const pct = rawPct.get(row.task_id);
      if (pct === undefined || row.avg_score === null) continue;
      checked += 1;

      // The snap moved this row exactly when the band it fell into is named
      // after a figure the row did not have.
      const moved = (pct >= NEAR_PERFECT_MIN_PCT && pct !== 100)
        || (pct <= NEAR_ZERO_MAX_PCT && pct !== 0);
      const has = Object.prototype.hasOwnProperty.call(row, 'pct_exact');
      assert.equal(
        has, moved,
        `${f}: ${row.task_id} scored ${pct}% and ${has ? 'carries' : 'lacks'} `
        + `pct_exact, but the snap ${moved ? 'did' : 'did not'} move it`,
      );
      if (!has) continue;

      carried += 1;
      assert.equal(row.pct_exact, pct, `${f}: ${row.task_id} pct_exact drifted`);
      // Saying the score must not change the verdict.
      assert.equal(
        row.avg_score, pct >= NEAR_PERFECT_MIN_PCT ? 1 : 0,
        `${f}: ${row.task_id} left the band it was counted in`,
      );
    }
  }
  assert.ok(checked > 0, 'no published row was actually compared');
  // The two rows this change exists for: 99.77% and 0.9%, one per published
  // run. If this ever reads 0 the key has stopped being emitted at all and
  // the presence check above would pass vacuously.
  assert.ok(carried > 0, 'no published row carries pct_exact — the key is dead');
});

// ── 5. No surface still asserts an exact figure it cannot support ─────────

test('no dashboard surface claims the bands are exactly 100% and 0%', async () => {
  // Each of these was live on the board and each named a figure the count does
  // not check for. `content_zero` is deliberately not here: that badge branches
  // on the raw `pct === 0` in selection-outcome.mjs, so its "Zero" is exact.
  const banned = [
    'Perfect (100%)',
    'Zero (0%)',
    'Score = 100%',
    'Score = 0%',
    'Tasks scored 100%',
    'scored full marks',
    'got zero',
  ];
  const offenders = [];
  for (const file of await sourceFiles()) {
    const text = await readFile(file, 'utf8');
    for (const phrase of banned) {
      if (text.includes(phrase)) {
        offenders.push(`${relative(ROOT, file)}: ${phrase}`);
      }
    }
  }
  assert.deepEqual(
    offenders, [],
    'a band label or definition names an exact score the count does not require',
  );
});
