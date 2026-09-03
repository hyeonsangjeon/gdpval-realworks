// How much of a published average rests on a sub-judge that does not work.
//
// The audio sub-judge was run against synthetic clips whose answers were known.
// It scored 48.6% — a coin — with a discrimination of exactly 0.00 by item
// majority, an 83.3% false-negative rate on true claims, higher confidence when
// it was wrong than when it was right, and 11 of 12 items answered identically
// across three repeats, so repeating a run can never surface the error. None of
// that is visible in a score. Nothing on the board said how much of any average
// passed through that route.
//
// `step8_grade._routing_stats` computes exactly this and post-dates every
// published payload, so the aggregator recomputes it from the same items by the
// same rule — which that function's own docstring licenses: "a payload
// published before this field existed reports the same numbers when it is
// re-summarised."
//
// The one thing this must not do is invent the answer. Eleven of the nineteen
// grade files on the board carry `routing_modality: null` on every item. Zero
// filling those into `audio: 0` would turn "never asked" into "asked and found
// none" — the same class of mistake as publishing `0.0%` for a rate that
// counted nothing. So this file holds four things in place:
//
//   A. the two languages name the same routes, so neither can drift;
//   B. the recomputation follows the producer's predicate exactly;
//   C. never-recorded, measured-zero, and non-zero stay three distinct states,
//      on the real published files as well as on fixtures;
//   D. what the counts structurally cannot see is stated rather than hidden.
//
// (C) and (D) execute the real decision function rather than pattern-matching
// the JSX around it: `src/components/wow/routeExposure.ts` is import-free
// precisely so esbuild — already installed, as vite depends on it — can hand it
// to node.
//
// Run:
//   node --test scripts/__tests__/route-exposure.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { processGradesFile } from '../aggregate-grades.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const READING_FILE = join(ROOT, 'src', 'components', 'wow', 'routeExposure.ts');
const GRADES_DIR = join(ROOT, 'data', 'grades');
const STEP8_PY = join(ROOT, 'batch-runner', 'step8_grade.py');

/**
 * The reading rule, type annotations stripped and nothing else touched.
 *
 * A failure to load is a real failure and is left to throw. Skipping would
 * leave the suite green while the only executable assertions in it quietly
 * stopped running.
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

// ── fixtures ──────────────────────────────────────────────────────────────

/** One rubric item. `route` of null is an item that recorded none. */
function item(maxScore, awarded, route, { verdict = 'pass', children } = {}) {
  return {
    rubric_item_id: `i-${route ?? 'none'}-${maxScore}-${verdict}`,
    max_score: maxScore,
    awarded_score: awarded,
    verdict,
    decided_by: 'judge',
    score_excluded: verdict === 'judge_error',
    ...(route === null ? {} : { routing_modality: route }),
    ...(children ? { child_grades: children } : {}),
  };
}

function task(taskId, items, { error = null } = {}) {
  const read = items.filter((i) => i.verdict !== 'judge_error');
  const awarded = read.reduce((t, i) => t + i.awarded_score, 0);
  const readMax = read.reduce((t, i) => t + i.max_score, 0);
  return {
    task_id: taskId,
    sector: 'test',
    occupation: 'test',
    items,
    total_awarded: Number(awarded.toFixed(4)),
    total_max: readMax,
    pct: readMax > 0 ? Number(((awarded / readMax) * 100).toFixed(2)) : 0,
    critical_fail: false,
    error,
  };
}

/** A payload the aggregator accepts, with an optional `summary.routing` claim. */
function grade(version, tasks, { routing } = {}) {
  const graded = tasks.filter((t) => !t.error);
  const pcts = graded.map((t) => t.pct);
  const avg = pcts.length
    ? Number((pcts.reduce((a, b) => a + b, 0) / pcts.length).toFixed(2))
    : null;
  const judgeItems = tasks.flatMap((t) => t.items).filter((i) => i.decided_by === 'judge');
  const judgeErrors = judgeItems.filter((i) => i.verdict === 'judge_error').length;
  return {
    schema_version: version,
    experiment_id: `exp-${version}`,
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    tasks,
    summary: {
      total_tasks: tasks.length,
      graded_tasks: graded.length,
      error_tasks: tasks.length - graded.length,
      openai_compat: {
        avg_score_pct: avg,
        ci_pct: pcts.length ? 1.5 : null,
        perfect_count: pcts.filter((p) => p >= 99).length,
        zero_count: pcts.filter((p) => p <= 1).length,
        partial_count: pcts.filter((p) => p > 1 && p < 99).length,
        inconsistent_count: 0,
      },
      wow: {
        judge_error_rate: judgeItems.length
          ? Math.floor((2 * judgeErrors * 10_000 + judgeItems.length)
            / (2 * judgeItems.length)) / 10_000
          : 0,
      },
      ...(routing ? { routing } : {}),
    },
  };
}

/** The composition as the dashboard receives it. */
function compositionOf(raw) {
  return processGradesFile('g.json', raw).summary_v1.route_composition;
}

// ── A. The two languages name the same routes ─────────────────────────────

test('ROUTE_NAMES is the producer’s _ROUTING_MODALITIES, not a second list', async () => {
  const source = await readFile(STEP8_PY, 'utf8');
  const m = source.match(/^_ROUTING_MODALITIES\s*=\s*\(([^)]*)\)/m);
  assert.ok(m, '_ROUTING_MODALITIES is not assigned at module level in step8_grade.py');
  const declared = [...m[1].matchAll(/"([^"]+)"/g)].map((x) => x[1]).sort();
  assert.ok(declared.includes('audio'), 'the producer stopped naming the audio route');

  // Read out of the aggregator rather than restated here, so a divergence is
  // a failure rather than something this file quietly agrees with.
  const js = await readFile(join(ROOT, 'scripts', 'aggregate-grades.mjs'), 'utf8');
  const jsMatch = js.match(/^const ROUTE_NAMES = \[([^\]]*)\]/m);
  assert.ok(jsMatch, 'ROUTE_NAMES is no longer a module-level literal');
  const jsNames = [...jsMatch[1].matchAll(/'([^']+)'/g)].map((x) => x[1]);

  assert.deepEqual(
    jsNames, declared,
    'the dashboard and step8_grade.py disagree about which routes exist',
  );
  assert.deepEqual(jsNames, [...jsNames].sort(), 'ROUTE_NAMES is not in sorted order');
});

// ── B. The recomputation follows the producer’s predicate ─────────────────

test('a route the run recorded is counted three ways, and the ways differ', () => {
  const got = compositionOf(grade('1.4', [
    task('t1', [item(4, 4, 'audio'), item(6, 3, 'text', { verdict: 'partial' })]),
    task('t2', [item(4, 0, 'audio', { verdict: 'fail' })]),
  ]));

  assert.equal(got.recorded, true);
  // `items` is the population; `tasks` counts tasks touching the route at
  // least once, so one item in each of two tasks is distinguishable from two
  // in one.
  assert.equal(got.items.audio, 2);
  assert.equal(got.tasks.audio, 2);
  assert.equal(got.items.text, 1);
  assert.equal(got.tasks.text, 1);
  assert.equal(got.scored_max_score.audio, 8);
  assert.equal(got.scored_max_score_total, 14);
  assert.equal(got.total_items, 3);
});

test('an errored task’s items are population, not score — the producer’s scope', () => {
  const got = compositionOf(grade('1.4', [
    task('t1', [item(5, 5, 'audio')]),
    task('t2', [item(5, 0, 'audio')], { error: 'grading failed' }),
  ]));

  assert.equal(got.items.audio, 2, 'an errored task’s item left the population');
  assert.equal(got.tasks.audio, 2, 'an errored task stopped counting as touching the route');
  assert.equal(got.scored_items.audio, 1, 'an errored task’s item was counted as scored');
  assert.equal(got.scored_max_score.audio, 5, 'an errored task’s weight entered the share');
});

test('a score_excluded item is population, not score', () => {
  const got = compositionOf(grade('1.4', [
    task('t1', [item(5, 5, 'audio'), item(7, 0, 'audio', { verdict: 'judge_error' })]),
  ]));
  assert.equal(got.items.audio, 2);
  assert.equal(got.scored_items.audio, 1);
  assert.equal(got.scored_max_score.audio, 5, 'unread rubric weight entered the share');
});

test('a penalty item’s negative weight is clamped, not subtracted', () => {
  // `scored_max_score` sums positive weight only, the same convention as
  // `excluded_max_score`: a penalty is not weight that would leave a
  // denominator, and letting it net off would shrink a route’s share.
  const got = compositionOf(grade('1.4', [
    task('t1', [item(-4, -4, 'audio', { verdict: 'fail' }), item(6, 6, 'text')]),
  ]));
  assert.equal(got.scored_max_score.audio, 0);
  assert.equal(got.scored_items.audio, 1, 'the item itself stopped being counted');
  assert.equal(got.scored_max_score_total, 6);
});

test('a route nobody has heard of is counted under its own name', () => {
  // So a modality introduced upstream shows up here before anything
  // downstream has been taught the word.
  const got = compositionOf(grade('1.4', [task('t1', [item(3, 3, 'holography')])]));
  assert.equal(got.items.holography, 1);
  assert.equal(got.items.audio, 0, 'the known routes stopped being listed');
  assert.deepEqual(
    Object.keys(got.items),
    ['audio', 'formatting', 'holography', 'mixed', 'text', 'visual'],
    'the key order left the producer’s sorted union',
  );
});

test('payload_agrees is three-valued, exactly like score_exclusion_lift', () => {
  const tasks = [task('t1', [item(4, 4, 'audio'), item(6, 6, 'text')])];

  // No claim. Not the same statement as agreement — and the state every
  // published file is in today.
  assert.equal(compositionOf(grade('1.4', tasks)).payload_agrees, null);

  const truth = compositionOf(grade('1.4', tasks));
  assert.equal(
    compositionOf(grade('1.4', tasks, {
      routing: { recorded: true, items: truth.items, unrecorded_items: 0 },
    })).payload_agrees,
    true,
  );
  assert.equal(
    compositionOf(grade('1.4', tasks, {
      routing: { recorded: true, items: { ...truth.items, audio: 99 }, unrecorded_items: 0 },
    })).payload_agrees,
    false,
    'a payload claiming a different composition was recorded as agreeing',
  );
});

// ── C. Three states, and never a manufactured zero ────────────────────────

test('a run that recorded no route gets empty maps, not zeroed ones', () => {
  const got = compositionOf(grade('1.4', [
    task('t1', [item(5, 5, null), item(5, 0, null, { verdict: 'fail' })]),
  ]));

  assert.equal(got.recorded, false);
  assert.deepEqual(got.items, {}, 'a run that recorded nothing was zero-filled');
  assert.deepEqual(got.scored_items, {});
  assert.deepEqual(got.tasks, {});
  assert.equal('audio' in got.items, false, 'the audio route was invented for a silent run');
  assert.equal(got.total_items, 2, 'the items themselves stopped being counted');
  assert.equal(got.unrecorded_items, 2);
});

test('a route absent from a recorded run is a measured zero, and reads as one', async () => {
  const { readRouteExposure } = await loadReading();
  const got = compositionOf(grade('1.4', [task('t1', [item(5, 5, 'text')])]));

  assert.equal(got.recorded, true);
  assert.equal(got.items.audio, 0, 'a recorded run stopped listing the routes it did not use');

  const reading = readRouteExposure(got);
  assert.equal(reading.state, 'measured');
  assert.equal(reading.value, 'none');
  assert.notEqual(reading.value, 'not recorded', 'a measured zero was reported as unmeasured');
});

test('a run that recorded nothing never prints a percentage', async () => {
  const { readRouteExposure } = await loadReading();
  const got = compositionOf(grade('1.4', [task('t1', [item(5, 5, null)])]));

  const reading = readRouteExposure(got);
  assert.equal(reading.state, 'not-recorded');
  assert.equal(reading.value, 'not recorded');
  assert.ok(!reading.value.includes('%'), 'a share was printed for a run with no routes');
  assert.match(reading.denominator, /not the same as having used none/);
  assert.deepEqual(reading.rows, [], 'rows were built for a run with nothing to put in them');
});

test('an absent composition is the same state as one that recorded nothing', async () => {
  const { readRouteExposure } = await loadReading();
  for (const absent of [null, undefined, {}]) {
    const reading = readRouteExposure(absent);
    assert.equal(reading.state, 'not-recorded', `${JSON.stringify(absent)} did not read as absent`);
    assert.ok(!reading.value.includes('%'));
  }
});

test('a run that did use the route reports its share of scored weight', async () => {
  const { readRouteExposure } = await loadReading();
  const got = compositionOf(grade('1.4', [
    task('t1', [item(4, 4, 'audio'), item(16, 16, 'text')]),
  ]));

  const reading = readRouteExposure(got);
  assert.equal(reading.state, 'measured');
  assert.equal(reading.value, '20.00%');
  assert.match(reading.denominator, /1 scored item\(s\) across 1 task\(s\)/);
  assert.equal(reading.caveat, undefined, 'a complete run was qualified anyway');

  // Rows are ordered by what they decided, so the biggest share reads first.
  assert.deepEqual(reading.rows.map((r) => r.route).slice(0, 2), ['text', 'audio']);
});

test('the unrouted remainder is stated, and named as failures when it is failures', async () => {
  const { readRouteExposure } = await loadReading();
  // The shape of the official 220-task grade: every unrouted item is one the
  // judge failed or errored on, so the routed population is missing failures
  // and a share taken over it reads lower than the truth.
  const got = compositionOf(grade('1.4', [
    task('t1', [
      item(4, 4, 'audio'),
      item(16, 16, 'text'),
      item(5, 0, null, { verdict: 'fail' }),
      item(5, 0, null, { verdict: 'judge_error' }),
    ]),
  ]));

  assert.equal(got.unrecorded_items, 2);
  assert.equal(got.unrecorded_failing_items, 2);
  const reading = readRouteExposure(got);
  assert.match(reading.caveat, /2 item\(s\).*recorded no route/);
  assert.match(reading.caveat, /not a random sample/);
});

test('a mixed remainder is described as mixed, not as all failures', async () => {
  const { readRouteExposure } = await loadReading();
  const got = compositionOf(grade('1.4', [
    task('t1', [
      item(4, 4, 'audio'),
      item(5, 0, null, { verdict: 'fail' }),
      item(5, 5, null),
    ]),
  ]));

  assert.equal(got.unrecorded_failing_items, 1);
  const reading = readRouteExposure(got);
  assert.match(reading.caveat, /leans towards failures/);
  assert.ok(
    !/not a random sample — it is failures/.test(reading.caveat),
    'a partly-failing remainder was reported as entirely failures',
  );
});

// ── D. What the counts cannot see is said, not hidden ─────────────────────

test('an audio child inside a mixed item is disclosed instead of vanishing', async () => {
  const { readRouteExposure } = await loadReading();
  // Both this rule and the producer count a `mixed` item once, under `mixed`.
  // Its children carry routes of their own, so an audio child is audio-decided
  // weight the audio row does not cover. 0 on every published grade today —
  // which is exactly why the day it is not 0 has to be visible.
  const got = compositionOf(grade('1.4', [
    task('t1', [
      item(10, 10, 'mixed', {
        children: [{ routing_modality: 'audio' }, { routing_modality: 'visual' }],
      }),
      item(10, 10, 'text'),
    ]),
  ]));

  assert.equal(got.items.audio, 0, 'an audio child was folded into the audio row');
  assert.equal(got.items.mixed, 1);
  assert.equal(got.audio_in_mixed_items, 1);

  const reading = readRouteExposure(got);
  assert.equal(reading.value, 'none directly', 'a part-audio run was reported as flatly none');
  assert.match(reading.caveat, /part-decided by an audio child/);
});

test('a mixed item with no audio child adds nothing and says nothing', async () => {
  const { readRouteExposure } = await loadReading();
  // The real shape on the board: 23 mixed items, 72 children, all formatting
  // or visual.
  const got = compositionOf(grade('1.4', [
    task('t1', [
      item(10, 10, 'mixed', {
        children: [{ routing_modality: 'formatting' }, { routing_modality: 'visual' }],
      }),
    ]),
  ]));

  assert.equal(got.audio_in_mixed_items, 0);
  const reading = readRouteExposure(got);
  assert.equal(reading.value, 'none');
  assert.equal(reading.caveat, undefined, 'a run with nothing to qualify was qualified');
});

test('every state names its denominator, whatever it is', async () => {
  const { readRouteExposure } = await loadReading();
  const states = [
    null,
    undefined,
    compositionOf(grade('1.4', [task('t1', [item(5, 5, null)])])),
    compositionOf(grade('1.4', [task('t1', [item(5, 5, 'text')])])),
    compositionOf(grade('1.4', [task('t1', [item(5, 5, 'audio')])])),
    // A run whose only routed item is a penalty: routed, scored, no positive
    // weight anywhere, so there is no share to take.
    compositionOf(grade('1.4', [task('t1', [item(-5, -5, 'audio', { verdict: 'fail' })])])),
  ];
  for (const [i, composition] of states.entries()) {
    const reading = readRouteExposure(composition);
    assert.ok(
      reading.denominator && reading.denominator.length > 0,
      `state ${i} printed a bare value with nothing behind it`,
    );
    assert.ok(!/^0(\.0+)?%$/.test(reading.value), `state ${i} printed a bare zero percentage`);
  }
});

test('a share too small to round is never printed as a flat zero', async () => {
  const { formatRouteShare } = await loadReading();
  // The same mistake this card exists to stop, one step smaller: a route that
  // decided something, shown as having decided nothing.
  assert.equal(formatRouteShare(0.0001), '<0.01%');
  assert.equal(formatRouteShare(0.64), '0.64%');
  assert.equal(formatRouteShare(0), '0.00%', 'a measured zero stopped reading as zero');
  assert.equal(formatRouteShare(null), '—', 'a share that does not exist was printed as one');
  assert.equal(formatRouteShare(undefined), '—');
});

// ── The published files, not only the fixtures ────────────────────────────

test('every published item-level grade carries a composition, and none is invented', async () => {
  const { readRouteExposure } = await loadReading();
  const files = (await readdir(GRADES_DIR)).filter((n) => n.endsWith('.json'));
  assert.ok(files.length > 0, 'no grade files were read at all');

  let recorded = 0;
  let silent = 0;
  for (const name of files) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    const record = processGradesFile(join(GRADES_DIR, name), raw);
    if (!record?.summary_v1) continue;
    const got = record.summary_v1.route_composition;
    assert.ok(got, `${name} reached the dashboard with no composition at all`);

    const reading = readRouteExposure(got);
    if (got.recorded) {
      recorded += 1;
      // A recorded run lists every route the producer knows about, including
      // the ones it did not use — those zeros were measured.
      assert.ok('audio' in got.items, `${name} recorded routing but dropped the audio row`);
      assert.equal(reading.state, 'measured');
    } else {
      silent += 1;
      assert.deepEqual(got.items, {}, `${name} recorded no route but was zero-filled`);
      assert.equal(reading.state, 'not-recorded');
      assert.equal(reading.value, 'not recorded');
      assert.ok(
        !reading.value.includes('%'),
        `${name} recorded no route and was published with a share anyway`,
      );
    }
  }

  // Both states are actually present on the board, so neither branch above is
  // passing by never running.
  assert.ok(recorded > 0, 'no published grade records routing — the recorded branch is untested');
  assert.ok(silent > 0, 'no published grade is silent — the never-asked branch is untested');
});
