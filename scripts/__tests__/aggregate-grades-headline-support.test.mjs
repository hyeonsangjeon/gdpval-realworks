// A headline the task rows do not add up to has to say so.
//
// `summary.openai_compat.avg_score_pct` is the number the dashboard prints as
// an experiment's score. Every count around it is validated — total/graded/
// error, perfect/zero/partial, judge_error_rate is recomputed from the items
// and compared — and the average itself was taken on trust.
//
// Four of the nineteen grade files the aggregator reads publish an average
// their own rows do not produce. All four are schema 1.0 `exp003` runs that
// divided by all 220 tasks rather than the 215 or 219 that were graded, so
// every ungraded task was counted as a zero:
//
//     published   rows mean   graded   corpus
//       54.10       55.355     215      220
//       53.30       54.537     215      220
//       51.47       51.709     219      220
//       49.25       49.477     219      220
//
// That is the mirror of the excluded-item defect. An item the grader could
// not read leaves the denominator, so the score goes up. A task it could not
// grade stays in the denominator as a zero, so the score goes down. Both
// published a number nobody measured and neither said a word about it.
//
// Run:
//   node --test scripts/__tests__/aggregate-grades-headline-support.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { processGradesFile } from '../aggregate-grades.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GRADES_DIR = join(ROOT, 'data', 'grades');

// The versions today's writer produces. Both are held to the arithmetic; the
// pair is asserted separately every time so that a version joining the strict
// list without joining this check cannot pass unnoticed.
const STRICT_VERSIONS = ['1.3', '1.4'];
const HISTORICAL_VERSIONS = ['1.0', '1.1', '1.2'];

/** One task row, in the shape the strict validator demands of it. */
function row(taskId, pct, { error = null, items = null } = {}) {
  return {
    task_id: taskId,
    pct,
    error,
    items: items ?? [
      { max_score: 10, score_excluded: false, verdict: 'pass', decided_by: 'judge' },
    ],
  };
}

/** A grade payload whose counts and item invariants are all already correct. */
function grade(version, tasks, headline = {}) {
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
        ci_pct: 1.5,
        perfect_count: pcts.filter((p) => p >= 99).length,
        zero_count: pcts.filter((p) => p <= 1).length,
        partial_count: pcts.filter((p) => p > 1 && p < 99).length,
        inconsistent_count: 0,
        ...headline,
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

const support = (raw) => processGradesFile('g.json', raw).summary.headline_support;

// ── the defect, in the arithmetic that published it ───────────────────────

test('a headline that divided by the whole corpus is refused on 1.3 and 1.4', () => {
  for (const version of STRICT_VERSIONS) {
    // 215 graded at 55.355 average, 5 ungraded. Divide by 220 and you get
    // 54.10, which is what the real files published.
    const tasks = [row('a', 80), row('b', 30.71), row('c', null, { error: 'x' })];
    const raw = grade(version, tasks);
    assert.equal(raw.summary.openai_compat.avg_score_pct, 55.36);

    // The same points over the whole corpus instead of the graded part.
    raw.summary.openai_compat.avg_score_pct = Number(((80 + 30.71) / 3).toFixed(2));
    assert.throws(
      () => processGradesFile('g.json', raw),
      /is not the average of its 2 scored task rows/,
      `schema ${version} accepted an average taken over the ungraded tasks`,
    );
  }
});

test('the refusal names both numbers and the gap between them', () => {
  // A message that says only "inconsistent" leaves the reader to recompute
  // 220 rows by hand to find out which way and by how much.
  const raw = grade('1.4', [row('a', 60), row('b', 40)]);
  raw.summary.openai_compat.avg_score_pct = 44.5;
  assert.throws(
    () => processGradesFile('g.json', raw),
    /headline 44\.5 is not the average of its 2 scored task rows \(50, off by -5\.5\)/,
  );
});

test('a correct headline passes and says the rows back it', () => {
  for (const version of STRICT_VERSIONS) {
    const got = support(grade(version, [row('a', 60), row('b', 41)]));
    assert.deepEqual(got, {
      avg_score_pct_from_rows: 50.5,
      delta_pct: 0,
      rows_counted: 2,
      supported: true,
    });
  }
});

// ── the width of the tolerance ────────────────────────────────────────────

test('two-decimal rounding is inside the tolerance, the smallest real defect is not', () => {
  // Three rows of 33.33 mean 33.33; a writer publishing 33.34 has rounded,
  // not miscounted. The tolerance has to admit that and nothing wider.
  const rounded = grade('1.4', [row('a', 33.33), row('b', 33.33), row('c', 33.33)]);
  rounded.summary.openai_compat.avg_score_pct = 33.34;
  assert.equal(support(rounded).supported, true);
  assert.equal(support(rounded).delta_pct, 0.01);

  // 1.24 points is the smallest of the four real disagreements. Nothing
  // between 0.01 and 1.24 is a rounding artefact of a two-decimal number.
  const defect = grade('1.4', [row('a', 33.33), row('b', 33.33), row('c', 33.33)]);
  defect.summary.openai_compat.avg_score_pct = 32.09;
  assert.throws(() => processGradesFile('g.json', defect), /off by -1\.24/);
});

test('a headline off by more than the tolerance is refused however small the run', () => {
  // The four real files are 215- and 219-row runs, but a one-task diagnostic
  // grade goes through the same reader, and a wrong headline on one row is
  // the easiest of all to publish.
  const raw = grade('1.4', [row('only', 72.5)]);
  raw.summary.openai_compat.avg_score_pct = 72.44;
  assert.throws(() => processGradesFile('g.json', raw), /off by -0\.06/);
});

// ── what an average is taken over ─────────────────────────────────────────

test('a scored task with no pct is refused rather than quietly left out', () => {
  // Dropping it would take the mean over a subset, and then a headline that
  // was right for the full set would be reported as the defect. The missing
  // pct is the defect.
  for (const version of STRICT_VERSIONS) {
    const raw = grade(version, [row('a', 60), row('b', 40)]);
    delete raw.tasks[1].pct;
    assert.throws(
      () => processGradesFile('g.json', raw),
      new RegExp(`schema ${version} scored task pct is missing or invalid`),
    );
  }
});

test('an out-of-range pct is refused', () => {
  const raw = grade('1.4', [row('a', 60), row('b', 40)]);
  raw.tasks[1].pct = 140;
  assert.throws(
    () => processGradesFile('g.json', raw),
    /scored task pct is missing or invalid/,
  );
});

test('an ungraded task is not a zero in the average', () => {
  // This is the defect stated as a positive requirement. Two tasks at 80 and
  // one that never got graded average 80, not 53.33.
  const got = support(grade('1.4', [
    row('a', 80), row('b', 80), row('c', null, { error: 'judge_unavailable' }),
  ]));
  assert.equal(got.avg_score_pct_from_rows, 80);
  assert.equal(got.rows_counted, 2);
  assert.equal(got.supported, true);
});

test('a task whose error is an empty string counts as graded, as it does everywhere else', () => {
  // The projection treats `''` as success. If this reader disagreed, the row
  // set it measures would differ from the one `graded_tasks` counts and the
  // check would fire on a correct file.
  const raw = grade('1.4', [row('a', 60, { error: '' }), row('b', 40)]);
  assert.equal(raw.summary.graded_tasks, 2);
  assert.equal(support(raw).rows_counted, 2);
  assert.equal(support(raw).supported, true);
});

test('a run that graded nothing is not asked to support a headline', () => {
  // `graded_tasks === 0` already requires a null headline, and null is not a
  // claim about anything. Reporting `supported: false` here would flag every
  // fully-failed run as an arithmetic defect.
  const raw = grade('1.4', [row('a', null, { error: 'x' })]);
  raw.summary.openai_compat.avg_score_pct = null;
  raw.summary.openai_compat.ci_pct = null;
  raw.summary.openai_compat.partial_count = 0;
  const got = support(raw);
  assert.equal(got.supported, null);
  assert.equal(got.avg_score_pct_from_rows, null);
  assert.equal(got.delta_pct, null);
  assert.equal(got.rows_counted, 0);
});

test('unmeasurable is null, never true', () => {
  // Reachable on the historical tier only, and reachable there for real: the
  // per-row `pct` requirement above is part of the strict check, so a 1.0-1.2
  // file whose rows carry no percentage at all validates and projects. There
  // is then nothing to compare the headline against, and `supported: true`
  // would be a claim that the rows were checked and agreed — the same class
  // of lie as rendering a missing headline as a score of 0.
  const raw = grade('1.1', [row('a', 60)]);
  delete raw.tasks[0].pct;
  const got = support(raw);
  assert.equal(got.supported, null);
  assert.equal(got.rows_counted, 0);
  assert.equal(got.avg_score_pct_from_rows, null);
  assert.equal(got.delta_pct, null);
  // And the headline it could not check is still published as written.
  assert.equal(processGradesFile('g.json', raw).summary.avg_score_pct, 60);
});

// ── the historical tier: measured, not rejected ───────────────────────────

test('a 1.0-1.2 headline the rows contradict is recorded, not thrown', () => {
  // Rejecting would take the dashboard build down on four real published
  // experiments. The build has to keep working and the disagreement has to
  // be on the record; those are not in tension, they are two different jobs.
  for (const version of HISTORICAL_VERSIONS) {
    const raw = grade(version, [row('a', 80), row('b', 30.71),
      row('c', null, { error: 'x' })]);
    raw.summary.openai_compat.avg_score_pct = 36.9; // divided by 3, not by 2
    const got = support(raw);
    assert.equal(got.supported, false, `schema ${version} did not flag it`);
    assert.equal(got.avg_score_pct_from_rows, 55.36);
    assert.equal(got.delta_pct, -18.46);
    assert.equal(got.rows_counted, 2);
  }
});

test('the published headline is passed through untouched when the rows disagree', () => {
  // Which number is the experiment's score is a decision about the
  // benchmark. Silently substituting the recomputed one here would be the
  // same failure in the other direction: a figure on the dashboard that no
  // published artefact contains.
  const raw = grade('1.0', [row('a', 80), row('b', 30.71),
    row('c', null, { error: 'x' })]);
  raw.summary.openai_compat.avg_score_pct = 36.9;
  const record = processGradesFile('g.json', raw);
  assert.equal(record.summary.avg_score_pct, 36.9);
  assert.equal(record.summary_v1.openai_compat.avg_score_pct, 36.9);
  assert.equal(record.summary.headline_support.avg_score_pct_from_rows, 55.36);
});

// ── the corpus itself ─────────────────────────────────────────────────────

test('every grade file the aggregator reads is measured, and exactly four disagree', async () => {
  // The natural negative control: four known positives against fourteen
  // known negatives, on the real published data rather than on fixtures.
  const files = (await readdir(GRADES_DIR))
    .filter((name) => name.endsWith('.json'))
    .sort();
  assert.ok(files.length >= 19, `expected the published corpus, found ${files.length}`);

  const flagged = [];
  let measured = 0;
  for (const name of files) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    const record = processGradesFile(join(GRADES_DIR, name), raw);
    const got = record.summary?.headline_support;
    if (!got) continue; // the pre-1.x legacy dummy, projected by another path
    measured += 1;
    if (got.supported === false) flagged.push([record.schema_version, got.delta_pct]);
  }

  assert.equal(measured, 18, 'an item-level grade went unmeasured');
  assert.equal(flagged.length, 4, `expected the four known files, got ${flagged.length}`);
  // All four are 1.0, and all four are published LOW: the ungraded tasks were
  // counted as zeros, so the recomputed mean is above the headline every time.
  for (const [version, delta] of flagged) {
    assert.equal(version, '1.0');
    assert.ok(delta < 0, `a flagged file was published high, not low: ${delta}`);
  }
  assert.deepEqual(
    flagged.map(([, d]) => d).sort((a, b) => a - b),
    [-1.26, -1.24, -0.24, -0.23],
  );
});

test('no 1.3 or 1.4 file on disk fails the check the aggregator now enforces', async () => {
  // The strict tier is only free if it is free across everything a publish
  // can be copied from, not just the two such files at the top level today.
  // The shard, repeat and superseded grades nest several levels deep, so the
  // walk has to be recursive or it silently checks almost nothing.
  async function* walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const path = join(dir, entry.name);
      if (entry.isDirectory()) yield* walk(path);
      else if (entry.name.endsWith('.json')) yield path;
    }
  }

  let checked = 0;
  let worst = 0;
  const otherFailures = new Set();
  for await (const path of walk(GRADES_DIR)) {
    const raw = JSON.parse(await readFile(path, 'utf8'));
    if (!STRICT_VERSIONS.includes(raw.schema_version)) continue;
    checked += 1;
    let record;
    try {
      record = processGradesFile(path, raw);
    } catch (err) {
      // Nothing in the corpus reaches this today. Seven of these files used to,
      // on an unrelated pre-existing check — their `cost_ledger.path` is a
      // run-identity filename longer than the 128-character segment cap that
      // used to be in cost-receipt.mjs, which is now the 255 of NAME_MAX — and
      // they only reach a validator at all because this test walks the
      // diagnostic and shard directories the aggregator itself never reads.
      // The branch stays so that a file that starts failing names itself.
      assert.doesNotMatch(err.message, /is not the average of its/, path);
      assert.doesNotMatch(err.message, /scored task pct is missing or invalid/, path);
      otherFailures.add(`${path}: ${err.message}`);
      continue;
    }
    const got = record.summary.headline_support;
    if (got?.delta_pct !== null) worst = Math.max(worst, Math.abs(got.delta_pct));
  }
  assert.ok(checked >= 75, `expected the 1.3/1.4 corpus, checked ${checked}`);
  assert.deepEqual(
    [...otherFailures],
    [],
    'a strict-tier grade stopped projecting',
  );
  // Two-decimal rounding and nothing else, which is why the tolerance can sit
  // five times above it and still be twenty-five times below the defect.
  assert.ok(worst <= 0.005, `a real 1.3/1.4 file drifts by ${worst}`);
});
