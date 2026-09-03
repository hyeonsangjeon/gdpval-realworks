// A task that never recorded a score was published as having scored zero.
//
// Two lines cooperated to produce one row that said two untrue things at once:
//
//   scripts/aggregate-grades.mjs   `const pct = typeof t.pct === 'number' ? t.pct : 0`
//   scripts/selection-outcome.mjs  `pct === 0 ? CONTENT_ZERO : SCORED`, with `pct` null
//
// The first read an absent score as the number 0, then handed it to the
// near-zero snap. The snap records `pct_exact` on exactly the rows it moved, and
// 0 was already 0, so it recorded nothing — the invented figure arrived at the
// dashboard with no mark on it saying it was invented, as `avg_score: 0.0`,
// `num_grades: 1`, `scores: [0]`. The second compared a null `pct` against 0,
// which is false, and returned `SCORED`. So the row rendered under a "Scored"
// label carrying a zero it was never given.
//
// Which files this can reach:
//
//   1.3 / 1.4  validateScoreExcludedGrade already throws on a scored task with
//              no finite pct. That is the stronger answer and this PR leaves it
//              alone — the file is refused, not rendered.
//   1.0 – 1.2  validateHistoricalHeadline checks that the headline KEYS are
//              present and nothing else. No check on that tier looks at a
//              task's own pct, so the row goes straight through.
//   legacy     processLegacyGradesFile keys on avg_score, not pct, and already
//              treats null as ungraded.
//
// Every published file carries a pct on every task, so this has never fired.
// It is fixed for the same reason #104 was: the check exists for the file that
// does not.
//
// What this file holds:
//
//   1. an absent score publishes as no score — null, nothing counted, and the
//      new `score_not_recorded` outcome rather than "Scored";
//   2. a real zero is untouched, so nothing already on the board moves;
//   3. no run-level count moves either — the payload's own summary numbers are
//      passed through exactly as before. Measured on the 19 real grade files
//      rather than asserted: re-running the aggregator over data/grades with
//      and without this change produces 36 field differences across the 20
//      generated files, and every one of them is the same thing — the new
//      member appearing in the `selection.outcomes` map as a 0. No existing
//      value changes, none is removed, no type moves. That map already
//      publishes seven zero-valued members on a typical file, because
//      summarizeOutcomes seeds every outcome at 0 by construction, and the one
//      src/ reader of it (GradeDetail:618) looks up a single named key rather
//      than iterating, so the added zero reaches no screen;
//   4. the new outcome is not a zero: not in the zero breakdown, not counted
//      as having reached a judge;
//   5. every frontend surface that must name it, names it — including the
//      badge, without which the row falls through to the "Partial" default.
//
// Run:
//   node --test scripts/__tests__/a-row-with-no-score-is-not-a-zero.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { processGradesFile } from '../aggregate-grades.mjs';
import {
  SELECTION_OUTCOME,
  OUTCOME_LABELS,
  ZERO_OUTCOME_ORDER,
  classifyTaskOutcome,
  summarizeOutcomes,
} from '../selection-outcome.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

// ── Fixtures ──────────────────────────────────────────────────────────────

/** A task row in the shape data/grades/*.json writes, scored at `pct`. */
function row(taskId, pct, over = {}) {
  return {
    task_id: taskId,
    sector: 'test',
    occupation: 'test',
    items: [{
      rubric_item_id: 'i-1',
      max_score: 10,
      awarded_score: (pct / 100) * 10,
      verdict: pct >= 100 ? 'pass' : pct > 0 ? 'partial' : 'fail',
      decided_by: 'judge',
      score_excluded: false,
    }],
    total_awarded: (pct / 100) * 10,
    total_max: 10,
    pct,
    critical_fail: false,
    error: null,
    selection_status: 'ok',
    selection_error: null,
    selected_deliverables: {
      selection_status: 'ok',
      primary_targets: [{ target_id: 'a', paths: ['Report.xlsx'], kind: 'xlsx' }],
      support_artifacts: [],
      reference_files_excluded: [],
    },
    ...over,
  };
}

/** The same row with its score removed, which is the whole subject here. */
function rowWithNoScore(taskId, over = {}) {
  const t = row(taskId, 0, over);
  delete t.pct;
  return t;
}

/**
 * A 1.2 payload. The summary is written by hand rather than derived from the
 * rows, because the point of assertion 3 is that these numbers survive the
 * projection untouched — deriving them here would prove nothing.
 */
function grade(tasks, summaryOver = {}) {
  return {
    schema_version: '1.2',
    experiment_id: 'exp-no-score',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    tasks,
    summary: {
      total_tasks: tasks.length,
      graded_tasks: tasks.length,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 50,
        ci_pct: 1.5,
        perfect_count: 0,
        partial_count: 1,
        zero_count: 1,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 0 },
      ...summaryOver,
    },
  };
}

/** Rows keyed by task_id, as the dashboard receives them. */
function rowsOf(raw, filename = 'g.json') {
  const record = processGradesFile(filename, raw);
  assert.ok(record, 'the fixture did not survive the aggregator at all');
  return new Map(record.tasks.map((t) => [t.task_id, t]));
}

// ── 1. An absent score publishes as no score ──────────────────────────────

test('a row with no pct publishes no score, not a zero', () => {
  const rows = rowsOf(grade([row('scored', 50), rowWithNoScore('missing')]));
  const missing = rows.get('missing');

  assert.equal(missing.avg_score, null, 'an absent score must stay absent');
  assert.equal(missing.num_grades, 0, 'nothing was graded, so nothing is counted');
  assert.deepEqual(missing.scores, [], 'there is no score to list');

  // Not an error: nothing went wrong that anyone recorded. Saying "error" here
  // would be the same overclaim in the other direction.
  assert.equal(missing.error, false);
  assert.deepEqual(missing.error_messages, []);

  // And no invented figure smuggled in under the breadcrumb key either.
  assert.equal(missing.pct_exact, undefined);
});

test('the row says which of the two it is, and is not called Scored', () => {
  const rows = rowsOf(grade([row('scored', 50), rowWithNoScore('missing')]));

  assert.equal(rows.get('missing').outcome, SELECTION_OUTCOME.SCORE_NOT_RECORDED);
  assert.equal(rows.get('scored').outcome, SELECTION_OUTCOME.SCORED);

  // The label a reader actually sees has to say the same thing.
  assert.equal(OUTCOME_LABELS[SELECTION_OUTCOME.SCORE_NOT_RECORDED], 'Score not recorded');
  assert.match(rows.get('missing').outcome_detail, /no score/i);
});

test('classifyTaskOutcome answers the absence directly, at every pct-like shape', () => {
  // The four ways a score can fail to be a number, including the two JSON
  // cannot carry but an in-memory caller can.
  for (const absent of [undefined, null, '50', Number.NaN]) {
    const task = absent === undefined
      ? rowWithNoScore('t')
      : row('t', 0, { pct: absent });
    assert.equal(
      classifyTaskOutcome(task).outcome,
      SELECTION_OUTCOME.SCORE_NOT_RECORDED,
      `pct ${String(absent)} is not a score and must not classify as one`,
    );
  }
});

// ── 2. A real zero is untouched ───────────────────────────────────────────

test('a genuine zero still publishes as a zero', () => {
  const rows = rowsOf(grade([row('zero', 0), rowWithNoScore('missing')]));
  const zero = rows.get('zero');

  assert.equal(zero.avg_score, 0, 'a task that scored nothing still scored nothing');
  assert.equal(zero.num_grades, 1);
  assert.deepEqual(zero.scores, [0]);
  assert.equal(zero.error, false);
  // A judge read it and awarded nothing: that is a verdict, and stays one.
  assert.equal(zero.outcome, SELECTION_OUTCOME.CONTENT_ZERO);
});

test('every scored row is byte-identical to what it was before', () => {
  // The snap either moves a row or leaves it alone, and this covers both ends
  // plus the middle. None of them touch the new branch.
  const raw = grade([row('full', 100), row('near', 99.77), row('mid', 50), row('low', 0.9)]);
  const rows = rowsOf(raw);

  assert.deepEqual(
    [rows.get('full').avg_score, rows.get('mid').avg_score],
    [1, 0.5],
  );
  // The snapped pair keeps both the snapped band and the figure it came from.
  assert.equal(rows.get('near').avg_score, 1);
  assert.equal(rows.get('near').pct_exact, 99.77);
  assert.equal(rows.get('low').avg_score, 0);
  assert.equal(rows.get('low').pct_exact, 0.9);
});

// ── 3. No run-level count moves ───────────────────────────────────────────

test('the payload\'s own summary numbers are passed through untouched', () => {
  const raw = grade([row('scored', 50), rowWithNoScore('missing')]);
  const record = processGradesFile('g.json', raw);

  // Every one of these is the grade JSON's own figure. A per-row fix that
  // moved any of them would be restating a published experiment, which is
  // exactly what this change must not do.
  assert.equal(record.summary.total_tasks, raw.summary.total_tasks);
  assert.equal(record.summary.graded_tasks, raw.summary.graded_tasks);
  assert.equal(record.summary.error_tasks, raw.summary.error_tasks);
  assert.equal(record.summary.avg_score_pct, raw.summary.openai_compat.avg_score_pct);
  assert.equal(record.summary.perfect_score, raw.summary.openai_compat.perfect_count);
  assert.equal(record.summary.partial_score, raw.summary.openai_compat.partial_count);
  assert.equal(record.summary.zero_score, raw.summary.openai_compat.zero_count);
});

test('the unscored row is left out of calibration rather than dragging it', () => {
  // qa_score arrives from a separate map keyed by experiment; without one the
  // row counts as unmatched, which is the honest bucket for it.
  const raw = grade([row('scored', 50), rowWithNoScore('missing')]);
  const record = processGradesFile('g.json', raw);
  assert.equal(record.summary.calibration_counts.calibrated, 0);
  assert.equal(record.summary.calibration_counts.overconfident, 0);
  assert.equal(record.summary.calibration_counts.underconfident, 0);
});

test('on a grade with no unscored row, the new member is a zero and nothing else', () => {
  // This is the whole footprint the change leaves on the 19 published grade
  // files. Running the aggregator over data/grades with and without it yields
  // 36 field differences and every one is this: `score_not_recorded` present
  // and 0. Pinned here so that a later change which makes the outcome actually
  // fire on real data shows up as a failing test rather than as a number
  // quietly moving on the dashboard.
  const before = {
    scored: 1, content_zero: 1, inference_failed: 0, format_unmet: 0,
    no_deliverable: 0, not_selected: 0, grading_error: 0, unclassified: 0,
  };
  const { outcomes } = summarizeOutcomes([row('a', 90), row('b', 0)]);

  assert.equal(outcomes.score_not_recorded, 0, 'no row here lacks a score, so the count is 0');
  for (const [key, count] of Object.entries(before)) {
    assert.equal(outcomes[key], count, `${key} must be exactly what it was before`);
  }
  // Present, not merely zero: summarizeOutcomes seeds every member, which is
  // why the key appears in the generated JSON at all.
  assert.ok(Object.prototype.hasOwnProperty.call(outcomes, 'score_not_recorded'));
});

// ── 4. The new outcome is not a zero ──────────────────────────────────────


test('score_not_recorded is not a reason for a zero and did not reach a judge', () => {
  assert.ok(
    !ZERO_OUTCOME_ORDER.includes(SELECTION_OUTCOME.SCORE_NOT_RECORDED),
    'an absent score listed among the zero reasons would reintroduce the bug',
  );
  assert.equal(classifyTaskOutcome(rowWithNoScore('t')).reached_judge, false);
});

test('summarizeOutcomes counts it separately and folds it into no total', () => {
  const tasks = [row('a', 90), row('b', 0), rowWithNoScore('c')];
  const s = summarizeOutcomes(tasks);

  assert.equal(Object.values(s.outcomes).reduce((a, b) => a + b, 0), tasks.length);
  assert.equal(s.outcomes.score_not_recorded, 1);
  assert.equal(s.outcomes.scored, 1);
  assert.equal(s.outcomes.content_zero, 1);
  // Neither kind of zero grew by it.
  assert.equal(s.judged_zero, 1);
  assert.equal(s.unjudged_zero, 0);
  assert.deepEqual(s.zero_reasons.map((r) => r.outcome), ['content_zero']);
});

// ── 5. The frontend surfaces name it ──────────────────────────────────────

test('every frontend surface that must name the outcome, names it', async () => {
  const types = await readFile(join(ROOT, 'src', 'types', 'grade.ts'), 'utf8');
  assert.match(
    types,
    /\|\s*'score_not_recorded'/,
    'src/types/grade.ts must carry the member or the aggregator emits a value the UI cannot type',
  );

  // Without a badge the row falls past every branch of getStatusBadge — not an
  // error, not a 1, not a 0 — and lands on the "Partial" default, which is the
  // one thing a row with no score definitely is not.
  const detail = await readFile(join(ROOT, 'src', 'pages', 'GradeDetail.tsx'), 'utf8');
  assert.match(
    detail,
    /score_not_recorded:\s*\{\s*text:/,
    'OUTCOME_BADGES must name it, or the row renders as "Partial"',
  );

  // REASON_STYLES is total over the union, so a missing entry is a type error
  // rather than a silent gap — asserted anyway so the reason is written down.
  const breakdown = await readFile(join(ROOT, 'src', 'components', 'ZeroReasonBreakdown.tsx'), 'utf8');
  assert.match(breakdown, /score_not_recorded:\s*\{/);
});

test('the two modules agree on what counts as a score', async () => {
  // aggregate-grades decides whether to project a score, selection-outcome
  // decides what to call the row. If they used different tests a row could be
  // labelled "Scored" beside an empty score column.
  const aggregate = await readFile(join(ROOT, 'scripts', 'aggregate-grades.mjs'), 'utf8');
  const selection = await readFile(join(ROOT, 'scripts', 'selection-outcome.mjs'), 'utf8');
  assert.match(aggregate, /if \(!Number\.isFinite\(t\.pct\)\)/);
  assert.match(selection, /Number\.isFinite\(task\?\.pct\)/);
});
