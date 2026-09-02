// A score computed out of less rubric than the task was set has to say so.
//
// When the judge cannot read a rubric item the grader drops it from the
// numerator AND from the denominator, so the task is scored out of what was
// read rather than out of what it was worth, and the published percentage
// rises. Task f1be6436 of the sol regrade earned 24 points, had 45 points of
// rubric read and 29 further points across 17 items the judge never reached,
// and is on the dashboard as 54%. Out of the whole 74-point rubric the same
// 24 points is 32.97%.
//
// That is the mirror of the headline defect next door. An item the grader
// could not read leaves the denominator, so the score goes up. A task it
// could not grade stays in the denominator as a zero, so the score goes down.
//
// The owner's decision is that both ends travel to the screen and stand side
// by side, and that it applies to the runs already published rather than only
// to future ones. So this file's job is two-sided: the second number has to
// appear wherever the denominator moved, and the FIRST number has to be
// byte-identical to what it was, because restating a published score is a
// decision about the benchmark and not one to make in an aggregator.
//
// Run:
//   node --test scripts/__tests__/aggregate-grades-score-exclusion.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { processGradesFile, isPublishableGrade } from '../aggregate-grades.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GRADES_DIR = join(ROOT, 'data', 'grades');

// 1.3 and 1.4 are held to `judge_error` <=> `score_excluded === true` by the
// strict validator, so their fixtures must set both. Below 1.3 the flag may
// simply be absent, which is the whole reason the projection reads the verdict.
const STRICT_VERSIONS = ['1.3', '1.4'];
const HISTORICAL_VERSIONS = ['1.0', '1.1', '1.2'];
const ALL_VERSIONS = [...HISTORICAL_VERSIONS, ...STRICT_VERSIONS];

/** One rubric item. `judge_error` sets both spellings so 1.3/1.4 validate. */
function item(maxScore, awarded, verdict = 'pass') {
  return {
    rubric_item_id: `i${maxScore}-${verdict}`,
    max_score: maxScore,
    awarded_score: awarded,
    verdict,
    decided_by: 'judge',
    score_excluded: verdict === 'judge_error',
  };
}

/**
 * A task row carrying the totals the projection recomputes from.
 *
 * `total_max` is the READ maximum, exactly as the grader writes it: the
 * excluded items have already left it. That is the shape of the defect.
 */
function task(taskId, items, { error = null, extra = {} } = {}) {
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
    ...extra,
  };
}

/** A payload whose counts and item invariants are all already correct. */
function grade(version, tasks) {
  const graded = tasks.filter((t) => !t.error);
  const pcts = graded.map((t) => t.pct);
  const avg = pcts.length
    ? Number((pcts.reduce((a, b) => a + b, 0) / pcts.length).toFixed(2))
    : null;
  const judgeItems = tasks.flatMap((t) => t.items)
    .filter((i) => i.decided_by === 'judge');
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
    },
  };
}

/** The projected exclusion for one task, as the dashboard receives it. */
function exclusionOf(raw, taskId = 't1') {
  const record = processGradesFile('g.json', raw);
  const row = record.tasks.find((t) => t.task_id === taskId);
  assert.ok(row, `task ${taskId} did not reach the dashboard at all`);
  return row.score_exclusion;
}

/** Twenty points of rubric read at half marks, ten points never reached. */
function halfReadHalfLost(taskId = 't1') {
  return task(taskId, [
    item(10, 5, 'partial'),
    item(10, 5, 'partial'),
    item(10, 0, 'judge_error'),
  ]);
}

/**
 * The same shape with a fifth of the rubric unread instead of a third.
 *
 * Ten points earned out of the twenty read is 50%; out of the whole 25 it is
 * exactly 40%. Both ends land on two decimals with nothing left over, which is
 * what lets the run-level means below be written as the integers they are
 * rather than as whatever a float happened to round to.
 */
function fifthOfTheRubricUnread(taskId = 't1') {
  return task(taskId, [
    item(10, 5, 'partial'),
    item(10, 5, 'partial'),
    item(5, 0, 'judge_error'),
  ]);
}

/** A task the judge read end to end, at full marks. */
function readInFull(taskId = 't2') {
  return task(taskId, [item(10, 10), item(10, 10)]);
}

/** The run-level lift, as the dashboard receives it. */
function liftOf(raw) {
  return processGradesFile('g.json', raw).summary.score_exclusion_lift;
}

/**
 * `avg_score` as the aggregator has always derived it from `pct`.
 *
 * It snaps: 99 and above is exactly 1, 1 and below is exactly 0, so that
 * `perfect_count` and `zero_count` can be taken by equality. Long-standing
 * behaviour, restated here because the checks below compare against the
 * published score and would otherwise report the snap as a defect of this
 * change.
 */
function snap(pct) {
  if (pct >= 99) return 1.0;
  if (pct <= 1) return 0.0;
  return pct / 100;
}

// -- the defect, in the arithmetic that published it -----------------------

test('a task whose judge failed on part of the rubric carries both ends', () => {
  for (const version of ALL_VERSIONS) {
    // 10 points earned. Out of the 20 read that is 50%; out of the whole 30
    // it is 33.33%. The published figure is the one the grader wrote.
    const got = exclusionOf(grade(version, [halfReadHalfLost()]));
    assert.deepEqual(got, {
      items: 1,
      excluded_max: 10,
      read_max: 20,
      pct_published: 50,
      pct_full_denominator: 33.33,
    }, `schema ${version} did not project the second denominator`);
  }
});

test('the published score is byte-identical with the feature and without it', () => {
  // The owner asked for a second number beside the first, not for the first
  // to be restated. If this ever stops holding, every score on the board has
  // silently moved.
  const raw = grade('1.4', [halfReadHalfLost('t1'), halfReadHalfLost('t2')]);
  const record = processGradesFile('g.json', raw);

  for (const row of record.tasks) {
    assert.equal(row.avg_score, 0.5, 'a task score moved');
    assert.ok(row.score_exclusion, 'the second number is missing');
  }
  assert.equal(record.summary.avg_score_pct, 50);
  assert.equal(record.summary_v1.openai_compat.avg_score_pct, 50);
  // And the run headline still passes its own arithmetic check, which is
  // taken over `pct` and must not have learned about the full denominator.
  assert.equal(record.summary.headline_support.supported, true);
  assert.equal(record.summary.headline_support.avg_score_pct_from_rows, 50);
});

test('the same projection reaches tasks_v1, not only the compat rows', () => {
  // ExperimentDetail reads one list and GradeDetail the other. A number that
  // appears on one screen and not the other is worse than one that appears
  // on neither, because the two disagree in front of the reader.
  const record = processGradesFile('g.json', grade('1.4', [halfReadHalfLost()]));
  const v1 = record.tasks_v1.find((t) => t.task_id === 't1');
  assert.deepEqual(v1.score_exclusion, record.tasks[0].score_exclusion);
  assert.equal(v1.pct, 50, 'tasks_v1 published a different first number');
});

// -- absent stays absent ---------------------------------------------------

test('a task whose denominator held gains no key at all', () => {
  // The #70/#115 convention: absent means "there is one number here", which
  // is a different statement from "the second number is zero". A row that
  // always carried the key would make every task look qualified.
  for (const version of ALL_VERSIONS) {
    const raw = grade(version, [task('t1', [item(10, 7, 'partial'), item(10, 10)])]);
    const record = processGradesFile('g.json', raw);
    assert.equal(record.tasks[0].score_exclusion, undefined);
    assert.equal('score_exclusion' in record.tasks[0], false,
      `schema ${version} put an empty key on an intact task`);
    assert.equal('score_exclusion' in record.tasks_v1[0], false);
  }
});

test('an excluded item worth nothing moves no denominator and is not reported', () => {
  // A zero-weight item leaving takes zero points with it, so both ends are
  // the same number. Badging that would put a warning on a task whose score
  // did not shift by so much as a rounding step.
  const raw = grade('1.4', [task('t1', [
    item(10, 5, 'partial'), item(10, 5, 'partial'), item(0, 0, 'judge_error'),
  ])]);
  assert.equal(exclusionOf(raw), undefined);
});

test('a penalty item the judge could not read is not reported either', () => {
  // Penalty criteria carry a negative max_score. One of those leaving the
  // rubric makes the denominator LARGER, not smaller, so the published score
  // was never inflated by it and there is nothing to disclose.
  const raw = grade('1.4', [task('t1', [
    item(10, 5, 'partial'), item(10, 5, 'partial'), item(-6, 0, 'judge_error'),
  ])]);
  assert.equal(exclusionOf(raw), undefined);
});

test('a rubric whose penalties outweigh it is left alone rather than divided by', () => {
  // Task c94452e4 on the board today: a -60 penalty item drives `total_max`
  // to -10, and it is published at 0%. Adding back the 6 points of unread
  // rubric still leaves -4. Dividing 34.72 by that yields -868%, so the
  // guard returns nothing and the row keeps showing one number.
  const raw = grade('1.0', [task('t1', [
    item(50, 34.72, 'partial'), item(-60, 0, 'fail'), item(6, 0, 'judge_error'),
  ])]);
  assert.equal(raw.tasks[0].total_max, -10);
  assert.equal(exclusionOf(raw), undefined);
});

test('a task nobody scored gets no second number, because it has no first one', () => {  // When every item fails the grader leaves the task unscored and the
  // dashboard already prints a dash. A percentage standing beside a dash
  // would be the only number on the row, and it would look like a score.
  const raw = grade('1.3', [
    task('t1', [item(10, 0, 'judge_error'), item(10, 0, 'judge_error')],
      { error: 'judge_unavailable', extra: { pct: null } }),
    task('t2', [item(10, 9, 'partial')]),
  ]);
  const record = processGradesFile('g.json', raw);
  const dead = record.tasks.find((t) => t.task_id === 't1');
  assert.equal(dead.avg_score, null);
  assert.equal(dead.error, true);
  assert.equal('score_exclusion' in dead, false);
});

test('a task that scored zero has both ends at zero and is left as one number', () => {
  // 66 of the 303 rows the denominator moved on are this: no points earned,
  // so 0 out of 45 and 0 out of 74 are the same 0%. The items did go missing,
  // but they inflated nothing, and "somewhere between 0% and 0%" is not a
  // disclosure. That the rubric went unread is on the record either way, in
  // `summary.wow.judge_error_rate`.
  const raw = grade('1.4', [task('t1', [
    item(10, 0, 'fail'), item(10, 0, 'fail'), item(10, 0, 'judge_error'),
  ])]);
  assert.equal(raw.tasks[0].pct, 0);
  assert.equal(exclusionOf(raw), undefined);
});

test('a task awarded more than its rubric allows stays at one clamped 100%', () => {
  // Task 61f546a8 of the exp003 baseline: 65.5 points awarded against 29
  // points of read rubric, which the grader publishes as a clamped 100%.
  // Adding the 4 unread points back still leaves 198%, so the second number
  // clamps to 100 as well and the two ends meet. The row keeps one number.
  //
  // The bad arithmetic upstream is not this projection's to fix, and it must
  // not be laundered into a range either — "100% ~ 198%" would read as a
  // score, and "100% ~ 100%" as a bug.
  const raw = grade('1.4', [task('t1', [
    item(29, 65.5, 'partial'), item(4, 0, 'judge_error'),
  ], { extra: { pct: 100 } })]);
  assert.equal(raw.tasks[0].total_awarded, 65.5);
  assert.equal(raw.tasks[0].total_max, 29);
  assert.equal(exclusionOf(raw), undefined);
});

test('the pair is withheld only when the two ends are equal, not merely close', () => {
  // Exact equality at the two decimals both ends carry, and no wider. A gap
  // of a single hundredth is still a gap; the dashboard adds decimals for
  // those rather than dropping one of the two numbers.
  const raw = grade('1.4', [task('t1', [
    item(1000, 700, 'partial'), item(1, 0, 'judge_error'),
  ])]);
  const got = exclusionOf(raw);
  assert.equal(got.pct_published, 70);
  assert.equal(got.pct_full_denominator, 69.93);
});

// -- which source the second number comes from ------------------------------

test('a payload that reports its own full denominator is believed, not recomputed', () => {
  // The grader learned to write `pct_full_denominator` in PR #362. Where it
  // is present it is the producer's own arithmetic over its own items, and
  // recomputing it here would mean the dashboard and the artefact could
  // disagree without either being wrong.
  const raw = grade('1.4', [halfReadHalfLost()]);
  raw.tasks[0].pct_full_denominator = 31.5; // deliberately not 33.33
  assert.equal(exclusionOf(raw).pct_full_denominator, 31.5);
});

test('a pre-1.3 item carrying no score_excluded flag still projects from its verdict', () => {
  // This is the path that reaches the runs already published. None of them
  // were written by a grader that knew about this field, so a projection
  // gated on the flag would find nothing and the board would not change.
  for (const version of HISTORICAL_VERSIONS) {
    const raw = grade(version, [halfReadHalfLost()]);
    for (const i of raw.tasks[0].items) delete i.score_excluded;
    assert.equal(exclusionOf(raw).pct_full_denominator, 33.33,
      `schema ${version} lost its historical projection`);
  }
});

test('a schema the projection has never validated is left untouched', () => {
  // Gated on the version list rather than sniffed for an `items` key, so a
  // payload shape nobody has checked cannot acquire a second headline number
  // on the strength of a field that happens to be spelled the same.
  const raw = grade('1.4', [halfReadHalfLost()]);
  raw.schema_version = '2.0';
  const record = processGradesFile('g.json', raw);
  assert.equal(record.schema_version, null, 'the fixture stopped being unknown');
  for (const row of record.tasks) {
    assert.equal('score_exclusion' in row, false);
  }
});

// -- the corpus itself -----------------------------------------------------

test('the published corpus carries the second number, and it is never the higher one', async () => {
  // The natural negative control: real data, where the only way to pass is
  // for the recomputation to hold on every row that has one.
  const files = (await readdir(GRADES_DIR))
    .filter((name) => name.endsWith('.json'))
    .sort();

  let rowsWithSecondNumber = 0;
  let filesTouched = 0;
  let worst = 0;
  for (const name of files) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    const record = processGradesFile(join(GRADES_DIR, name), raw);
    if (!isPublishableGrade(record)) continue;
    let touched = false;
    for (const row of record.tasks) {
      const got = row.score_exclusion;
      if (!got) continue;
      touched = true;
      rowsWithSecondNumber += 1;

      assert.ok(got.items >= 1, `${name}/${row.task_id}: reported zero items`);
      assert.ok(got.excluded_max > 0, `${name}/${row.task_id}: reported no lost points`);
      assert.ok(got.pct_full_denominator >= 0 && got.pct_full_denominator <= 100,
        `${name}/${row.task_id}: ${got.pct_full_denominator} is not a percentage`);
      // The whole point: dividing by MORE rubric cannot raise the score.
      assert.ok(got.pct_full_denominator <= got.pct_published + 1e-9,
        `${name}/${row.task_id}: the fuller denominator scored higher`);
      // And the first number is still the one the row publishes.
      assert.equal(row.avg_score, snap(got.pct_published),
        `${name}/${row.task_id}: the two numbers describe different rows`);

      worst = Math.max(worst, got.pct_published - got.pct_full_denominator);
    }
    if (touched) filesTouched += 1;
  }

  assert.ok(rowsWithSecondNumber >= 200,
    `expected the published corpus to be affected, found ${rowsWithSecondNumber} rows`);
  assert.ok(filesTouched >= 10, `only ${filesTouched} published files were touched`);
  // f1be6436 at 54.22 against 32.97. If this ever drops it is because the
  // corpus changed, and the number on the card is stale.
  assert.ok(worst >= 21, `the widest published gap fell to ${worst.toFixed(2)} points`);
});

test('no published task row loses its score to this projection', async () => {
  // The strongest form of "the first number did not move": every published
  // `avg_score` is still what `pct` has always produced, on every row of
  // every file, whether or not this projection had anything to say about it.
  const files = (await readdir(GRADES_DIR)).filter((n) => n.endsWith('.json'));
  let checked = 0;
  for (const name of files) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    const record = processGradesFile(join(GRADES_DIR, name), raw);
    if (!record.tasks_v1) continue;
    const byId = new Map(record.tasks_v1.map((t) => [t.task_id, t]));
    for (const row of record.tasks) {
      const source = byId.get(row.task_id);
      if (!source || row.error || !Number.isFinite(source.pct)) continue;
      assert.equal(row.avg_score, snap(source.pct),
        `${name}/${row.task_id}: the published score was rewritten`);
      checked += 1;
    }
  }
  assert.ok(checked >= 500, `expected the whole corpus, checked ${checked} rows`);
});

// -- the same measurement, taken over the whole run -------------------------
//
// The pair above reaches the screen one task at a time, inside a table that
// shows fifty rows at most. Nothing said what the headline — the one number an
// experiment is remembered by — owed to the same effect, so a reader comparing
// two experiments could not see it at all.

test('the run carries the same measurement its rows do', () => {
  // One task of two loses a fifth of its rubric. The rows average 75%; the
  // same two tasks out of their whole rubrics average 70%. Five points of this
  // run's headline are rubric nobody read.
  const got = liftOf(grade('1.4', [fifthOfTheRubricUnread('t1'), readInFull('t2')]));
  assert.deepEqual(got, {
    tasks_affected: 1,
    tasks_counted: 2,
    excluded_items: 1,
    excluded_max: 5,
    avg_score_pct_from_rows: 75,
    avg_score_pct_full_denominator: 70,
    lift_pct: 5,
    payload_agrees: null,
  });
});

test('a run whose judge read every rubric item reports nothing rather than a zero', () => {
  // A `lift_pct: 0` on every run would put the caveat on the whole board and
  // invite a reader to compare zeros that mean different things. Same
  // convention as the per-task pair, for the same reason.
  for (const version of ALL_VERSIONS) {
    const raw = grade(version, [task('t1', [item(10, 7, 'partial'), item(10, 10)])]);
    assert.equal(liftOf(raw), null, `schema ${version} invented a lift`);
  }
});

test('the lift is measured against the rows, not against a headline that disagrees with them', () => {
  // The shape of the four published 1.0 files on the board. A task the grader
  // could not grade at all stays in the denominator as a zero, so the headline
  // sits BELOW the mean of its own rows — while unread rubric lifts those rows
  // above what the whole rubrics would give. The two defects are independent
  // and pull opposite ways, so subtracting a full-denominator mean from the
  // published headline reports their sum and here flips the sign outright:
  // 65 − 70 is −5 where the answer is +5.
  const raw = grade('1.0', [fifthOfTheRubricUnread('t1'), readInFull('t2')]);
  raw.summary.openai_compat.avg_score_pct = 65;
  const record = processGradesFile('g.json', raw);

  // The published figure is still the published figure. Restating a benchmark
  // score is not a decision for an aggregator, here or anywhere else in this
  // file.
  assert.equal(record.summary.avg_score_pct, 65);
  assert.equal(record.summary.headline_support.supported, false);
  assert.equal(record.summary.headline_support.delta_pct, -10);

  const got = record.summary.score_exclusion_lift;
  assert.equal(got.avg_score_pct_from_rows, 75);
  assert.equal(got.avg_score_pct_full_denominator, 70);
  assert.equal(got.lift_pct, 5, 'the headline gap leaked into the lift');
  assert.equal(
    record.summary.avg_score_pct - got.avg_score_pct_full_denominator,
    -5,
    'the fixture stopped demonstrating the sign flip',
  );
});

test('a run-level claim in the payload is reported three-valued, never assumed', () => {
  // The grader learned to write this figure in #362 and none of the nineteen
  // files the aggregator reads carries it — though one further down
  // `data/grades` already does, so the case below is a payload that exists.
  // `null` has to keep meaning "the payload said nothing", which is a
  // different statement from "the payload agrees" — the same three-valued rule
  // `headline_support.supported` follows.
  const build = () => grade('1.4', [fifthOfTheRubricUnread('t1'), readInFull('t2')]);

  assert.equal(liftOf(build()).payload_agrees, null, 'silence was read as agreement');

  const agreeing = build();
  agreeing.summary.score_exclusions = { avg_score_pct_full_denominator: 70.02 };
  assert.equal(liftOf(agreeing).payload_agrees, true, 'a two-decimal rounding step was called a conflict');

  const disagreeing = build();
  disagreeing.summary.score_exclusions = { avg_score_pct_full_denominator: 68 };
  assert.equal(liftOf(disagreeing).payload_agrees, false, 'a real disagreement went unreported');
});

test('a schema the projection has never validated gets no run-level lift either', () => {
  // An unrecognised version does not reach the item-level summary at all, so
  // the key is absent rather than null. Both readings are "no claim" to the
  // dashboard, which tests the value for truthiness; the distinction is
  // written down here so a later change that starts emitting `null` on this
  // path is visible as a change rather than as a wash.
  const raw = grade('1.4', [fifthOfTheRubricUnread('t1'), readInFull('t2')]);
  raw.schema_version = '2.0';
  const record = processGradesFile('g.json', raw);
  assert.equal(record.schema_version, null, 'the fixture stopped being unknown');
  assert.equal('score_exclusion_lift' in record.summary, false);
  assert.ok(!record.summary.score_exclusion_lift);
});

test('twelve of the nineteen published files owe part of their headline to unread rubric', async () => {
  // Twelve known positives against seven known negatives, on the real data.
  // An equality rather than a floor: a corpus that changes this should make
  // somebody look at it, the same way the headline-support corpus check does.
  const files = (await readdir(GRADES_DIR))
    .filter((name) => name.endsWith('.json'))
    .sort();
  assert.ok(files.length >= 19, `expected the published corpus, found ${files.length}`);

  let withLift = 0;
  let worst = 0;
  for (const name of files) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    const record = processGradesFile(join(GRADES_DIR, name), raw);
    const got = record.summary?.score_exclusion_lift;
    if (!got) continue;
    withLift += 1;

    // Dividing by MORE rubric cannot raise a run's average any more than it
    // can raise a task's.
    assert.ok(got.lift_pct >= 0, `${name}: the fuller denominator averaged higher`);
    assert.ok(got.tasks_affected >= 1 && got.tasks_affected <= got.tasks_counted,
      `${name}: ${got.tasks_affected} affected of ${got.tasks_counted} counted`);
    assert.ok(got.excluded_items >= got.tasks_affected,
      `${name}: fewer unread items than affected tasks`);
    assert.ok(got.excluded_max > 0, `${name}: reported no lost points`);
    // Both run-level readers take their published-side mean over the same
    // rows. If these ever drift, the two numbers on the page are describing
    // different runs.
    assert.equal(got.avg_score_pct_from_rows,
      record.summary.headline_support.avg_score_pct_from_rows,
      `${name}: the run-level readers disagree about which rows they read`);
    assert.equal(got.payload_agrees, null,
      `${name}: a published payload started claiming its own figure`);

    worst = Math.max(worst, got.lift_pct);
  }

  assert.equal(withLift, 12, `expected twelve affected files, found ${withLift}`);
  // exp998's three-task pro smoke: one task of three, 3.53 points of headline.
  // The 215-220 task runs move 0.14 to 0.53.
  assert.ok(worst >= 3.5, `the widest published run-level lift fell to ${worst}`);
});
