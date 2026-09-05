// One grader asked once is not two graders who agreed.
//
// `GradeDetail` published a panel headed *Grader Consistency — agreement across
// multiple graders*, and built its agree count like this:
//
//   const graded = grade.tasks.filter((t) => !t.error && t.scores.length > 0)
//   const agree  = graded.filter((t) => new Set(t.scores).size === 1).length
//
// A set built from a one-element array always has size 1. On a run where every
// task was judged exactly once, every graded task therefore landed in `agree`,
// and the panel announced **100.0% Agree / 0.0% Disagree** — unanimity among
// graders who were never asked the same question.
//
// Measured against this repository's own published grades: **18 of 19 runs**
// print `100.0%` today, and in all 18 not one task carries a second score. The
// producer says as much itself — `scripts/aggregate-grades.mjs` writes
// `num_grades: 1, scores: [avgScore]` for every scored task and documents
// `inconsistent_grades` as *"Always 0 for single-judge runs (Phase A)"*.
//
// The 19th run is `dummy_gpt5_baseline` — legacy demo data, flagged `is_dummy`
// by the aggregator. It printed **75.8%** because one of its 219 graded tasks
// carries a single score, its second grader having recorded `Responses API did
// not complete within 3600.0 seconds`. A task whose second grader timed out was
// counted as a task whose graders agreed. Over the 218 tasks that really were
// judged twice or more, the figure is **75.7%**.
//
// The percentages were then divided by `agree + disagree || 1`, so an empty
// denominator printed `0.0%` — a disagreement rate of zero, for a comparison
// that did not happen.
//
// `src/components/grades/consistencyReading.ts` is where the reading now
// happens, and it is import-free so esbuild — already installed, as vite
// depends on it — can hand the real decision to node. This file holds five
// things in place:
//
//   A. the root cause, stated as an executable fact about Set;
//   B. the three standings a consistency panel can be in, run for real;
//   C. the denominator is never substituted, and a measured run is untouched;
//   D. every published grade payload, read through the real rule;
//   E. no surface under src/ fabricates a denominator, publishes an agreement
//      figure it worked out itself, or counts a lone score as an agreement.
//
// The first two guards in (E) fail on the code this replaces. The third is
// file-scoped and would not have: `GradeDetail` held the defective count and a
// correct `scores.length > 1` in the same file, twenty-two lines apart. It is
// kept as a forward guard against a new surface that has no notion of length
// at all, and it says so rather than claiming more than it can see.
//
// Run:
//   node --test scripts/__tests__/a-single-judgement-is-not-graders-agreeing.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const READING_FILE = join(SRC_DIR, 'components', 'grades', 'consistencyReading.ts');
const GRADES_DIR = join(ROOT, 'public', 'generated', 'grades');

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
 * Scanning raw text would count the paragraph above a guard — the
 * documentation that keeps this from being undone — as a violation of it.
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

/** Every published grade payload the dashboard can open. */
async function publishedGrades() {
  const names = (await readdir(GRADES_DIR)).filter((n) => n.endsWith('.json'));
  const out = [];
  for (const name of names) {
    out.push({ name, payload: JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8')) });
  }
  return out;
}

/** The rule this replaces, kept runnable so the corpus comparison is real. */
function theRuleThisReplaces(tasks) {
  const graded = tasks.filter((t) => !t.error && t.scores.length > 0);
  const agree = graded.filter((t) => new Set(t.scores).size === 1).length;
  const disagree = graded.length - agree;
  return `${((agree / (agree + disagree || 1)) * 100).toFixed(1)}%`;
}

// ── A. The root cause, as an executable fact ──────────────────────────────

test('a set built from one score has size 1 whatever the score is', () => {
  // The old predicate was `new Set(t.scores).size === 1`, read as "the graders
  // returned one distinct score, so they agreed". For a one-element array it is
  // true by construction — of a perfect score, of a zero, of anything. It was
  // never a fact about graders.
  for (const score of [0, 1, 5.5, 10, -3]) {
    assert.equal(new Set([score]).size, 1, `a lone ${score} did not read as unanimous`);
  }

  // Which is why the old rule called a whole single-judged run unanimous.
  const singleJudged = Array.from({ length: 219 }, (_, i) => ({
    error: false,
    scores: [i % 11],
  }));
  assert.equal(
    theRuleThisReplaces(singleJudged), '100.0%',
    'the rule under repair no longer reproduces the figure it published',
  );
});

// ── B. The three standings, run for real ──────────────────────────────────

test('a run where every task was judged once is not recorded, not 100%', async () => {
  const { readGraderConsistency } = await loadReading();

  const reading = readGraderConsistency([
    { error: false, scores: [8] },
    { error: false, scores: [3] },
    { error: true, scores: [] },
  ]);

  assert.equal(reading.standing, 'single-judgement');
  assert.equal(reading.compared, 0, 'a task judged once entered the denominator');
  assert.equal(reading.agree, 0, 'a task judged once was counted as an agreement');
  assert.equal(reading.disagree, 0);
  assert.equal(reading.judgedOnce, 2, 'the tasks that were judged once are not counted anywhere');
  assert.equal(reading.agreeFraction, null, 'a bar was drawn for a comparison that did not happen');
  assert.equal(reading.disagreeFraction, null);
  assert.equal(reading.agreeValue, 'not recorded');
  assert.equal(reading.disagreeValue, 'not recorded');
  assert.doesNotMatch(reading.agreeValue, /%/, 'a percentage survived into an unmeasured run');
  assert.doesNotMatch(reading.disagreeValue, /%/);

  // And the page says why, in words, including the reading it rules out.
  assert.match(reading.caveat, /judged once/);
  assert.match(reading.caveat, /not 100% agreement/i);
});

test('a run where nothing carries a score is a third state of its own', async () => {
  const { readGraderConsistency } = await loadReading();

  const nothingScored = readGraderConsistency([
    { error: true, scores: [] },
    { error: false, scores: [] },
  ]);
  assert.equal(nothingScored.standing, 'none-graded');
  assert.equal(nothingScored.judgedOnce, 0);
  assert.equal(nothingScored.agreeValue, 'not recorded');

  // Not the same sentence as a run that was graded once per task: one says no
  // second opinion was sought, the other says no opinion was recorded at all.
  const judgedOnce = readGraderConsistency([{ error: false, scores: [8] }]);
  assert.notEqual(nothingScored.caveat, judgedOnce.caveat);

  // Nothing at all, and a malformed payload, are read the same safe way.
  for (const input of [[], null, undefined]) {
    const empty = readGraderConsistency(input);
    assert.equal(empty.standing, 'none-graded');
    assert.equal(empty.agreeFraction, null);
  }
});

test('a genuinely multi-judged run still reports its percentage', async () => {
  const { readGraderConsistency } = await loadReading();

  // The negative control. Four tasks judged twice, three of them unanimous.
  const reading = readGraderConsistency([
    { error: false, scores: [8, 8] },
    { error: false, scores: [5, 5] },
    { error: false, scores: [9, 9] },
    { error: false, scores: [4, 7] },
    { error: true, scores: [] },
  ]);

  assert.equal(reading.standing, 'measured');
  assert.equal(reading.compared, 4);
  assert.equal(reading.agree, 3);
  assert.equal(reading.disagree, 1);
  assert.equal(reading.judgedOnce, 0);
  assert.equal(reading.agreeValue, '75.0%');
  assert.equal(reading.disagreeValue, '25.0%');
  assert.equal(reading.agreeFraction, 0.75);
  assert.equal(reading.caveat, undefined, 'a fully compared run was given a caveat it does not need');

  // A run where the graders really did agree everywhere still says 100%.
  const unanimous = readGraderConsistency([
    { error: false, scores: [8, 8] },
    { error: false, scores: [5, 5] },
  ]);
  assert.equal(unanimous.standing, 'measured');
  assert.equal(unanimous.agreeValue, '100.0%');
  assert.equal(unanimous.disagreeValue, '0.0%');
});

// ── C. The denominator is never substituted ───────────────────────────────

test('the denominator is what was compared, and single judgements are named apart', async () => {
  const { readGraderConsistency } = await loadReading();

  // A mixed run: two tasks judged twice, three judged once. The three are not
  // evidence either way, so they are excluded from the rate and reported as
  // themselves — which is exactly the move that takes dummy_gpt5_baseline from
  // 75.8% to 75.7%, its excluded task being one whose second grader timed out.
  const tasks = [
    { error: false, scores: [8, 8] },
    { error: false, scores: [4, 7] },
    { error: false, scores: [9] },
    { error: false, scores: [2] },
    { error: false, scores: [6] },
  ];
  const reading = readGraderConsistency(tasks);

  assert.equal(reading.compared, 2, 'the denominator is not the tasks that were compared');
  assert.equal(reading.judgedOnce, 3);
  assert.equal(reading.agreeValue, '50.0%');
  assert.match(reading.caveat, /3 further graded tasks were judged once/);

  // The old rule would have called this run 80% agreement, on a denominator of
  // five, three of which were never compared with anything.
  assert.equal(theRuleThisReplaces(tasks), '80.0%');
  assert.notEqual(reading.agreeValue, theRuleThisReplaces(tasks));

  // And an empty denominator produces no number at all, rather than the `0.0%`
  // that `agree + disagree || 1` produced by dividing zero by a fabricated one.
  const none = readGraderConsistency([{ error: false, scores: [8] }]);
  assert.equal(none.compared, 0);
  assert.equal(none.disagreeValue, 'not recorded');
  assert.notEqual(none.disagreeValue, '0.0%');
});

// ── D. Every published grade payload, read for real ───────────────────────

test('no published run is called unanimous on tasks that were judged once', async () => {
  const { readGraderConsistency } = await loadReading();
  const grades = await publishedGrades();
  assert.ok(grades.length > 0, 'no grade payload was aggregated — run npm run aggregate');

  let singleJudgement = 0;
  let measured = 0;

  for (const { name, payload } of grades) {
    const tasks = payload.tasks ?? [];
    const reading = readGraderConsistency(tasks);
    const comparable = tasks.filter((t) => !t.error && (t.scores?.length ?? 0) > 1).length;

    // The standing follows the data, on every payload, with no exceptions.
    assert.equal(
      reading.standing === 'measured', comparable > 0,
      `${name}: the standing does not match what the payload actually carries`,
    );
    assert.equal(reading.compared, comparable, `${name}: wrong denominator`);

    if (reading.standing === 'measured') {
      measured += 1;
      assert.match(reading.agreeValue, /%$/, `${name}: a measured run printed no percentage`);
      // Excluding the uncompared tasks can only shrink the denominator, and
      // where it does, the published figure is not the one the old rule gave.
      if (reading.judgedOnce > 0) {
        assert.ok(
          reading.compared < reading.compared + reading.judgedOnce,
          `${name}: single judgements were left in the denominator`,
        );
        assert.notEqual(
          reading.agreeValue, theRuleThisReplaces(tasks),
          `${name}: the figure did not move even though uncompared tasks were dropped`,
        );
      }
    } else {
      singleJudgement += 1;
      assert.equal(reading.agreeValue, 'not recorded', `${name}: printed a rate over nothing`);
      assert.equal(reading.disagreeValue, 'not recorded');
      assert.equal(reading.agreeFraction, null);
      // This is the number the page used to show for these runs.
      assert.equal(
        theRuleThisReplaces(tasks), '100.0%',
        `${name}: expected the old rule to have claimed unanimity here`,
      );
    }
  }

  // Teeth. If the corpus ever held only measured runs this test would pass
  // while proving nothing — the vacuous-guard failure this whole file is about.
  assert.ok(
    singleJudgement > 0,
    'no published run is single-judged, so the guard proves nothing',
  );
  assert.ok(measured > 0, 'no published run is multi-judged, so the measured path is unexercised');
});

// ── E. No src/ surface fabricates a denominator or a unanimity ────────────

test('no surface under src/ divides by a substituted denominator', async () => {
  // `|| 1` in a divisor turns "nothing was compared" into "compared once and
  // they agreed". The four occurrences it had were the four this PR removes.
  const offenders = [];
  const files = await sourceFiles();
  assert.ok(files.length > 0, 'the scan found no source files');

  for (const file of files) {
    const text = await renderedText(file);
    if (/\|\|\s*1\s*\)/.test(text)) offenders.push(relative(ROOT, file));
  }
  assert.deepEqual(
    offenders, [],
    'a dashboard surface substitutes 1 for a denominator it does not have',
  );
});

test('the page that publishes a grader-agreement figure gets it from the reading', async () => {
  // The guard that fails on the code this replaced. `GradeDetail` worked the
  // figure out inline, in a memo of its own, and published it under a heading
  // promising agreement across multiple graders. Anything carrying that heading
  // has to take its numbers from the one place that knows when there are none.
  const offenders = [];
  let carriers = 0;

  for (const file of await sourceFiles()) {
    const rel = relative(ROOT, file);
    if (rel === relative(ROOT, READING_FILE)) continue;
    const text = await renderedText(file);
    if (!text.includes('Grader Consistency')) continue;
    carriers += 1;
    if (!text.includes('readGraderConsistency')) offenders.push(rel);
  }

  assert.deepEqual(
    offenders, [],
    'a page publishes a grader-agreement figure it worked out itself',
  );
  assert.ok(carriers > 0, 'nothing under src/ shows the panel, so this guard is vacuous');
});

test('every src/ surface counting distinct scores requires more than one score', async () => {
  // A forward guard, and file-scoped: it asks whether a surface that counts
  // distinct scores knows that a count of one might mean one score. It would
  // not have caught the original, which held both readings in one file — see
  // the guard above for the one that does.
  const offenders = [];
  let counted = 0;

  for (const file of await sourceFiles()) {
    const text = await renderedText(file);
    const usesScoreSet = [...text.matchAll(/new Set\(([^)]*)\)/g)].some((m) =>
      m[1].includes('scores'),
    );
    if (!usesScoreSet) continue;
    counted += 1;
    if (!/\.length\s*>\s*1/.test(text)) offenders.push(relative(ROOT, file));
  }

  assert.deepEqual(
    offenders, [],
    'a surface reads a lone score as graders who returned the same answer',
  );
  assert.ok(counted > 0, 'nothing under src/ counts distinct scores, so this guard is vacuous');
});
