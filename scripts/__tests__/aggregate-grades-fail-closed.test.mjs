// Fail-closed contract for scripts/aggregate-grades.mjs.
//
// Two halves of one quiet lie:
//
//   1. validateHistoricalHeadline rejected an explicit `null` headline but let
//      an ABSENT one through, and the projection turned absence into
//      `avg_score_pct: 0`. A run whose headline never arrived was published as
//      a run that scored zero — beside a `graded_tasks` that said otherwise.
//   2. Every validator throw was caught inside main()'s loop, logged, and
//      dropped. The file vanished from grades-index.json, the aggregation
//      printed a success line, and the build exited 0.
//
// Tightening (1) alone would have turned "published as a false zero" into
// "silently vanished" — a different lie, not a fix — so both are pinned here.
//
// Run:
//   node --test scripts/__tests__/aggregate-grades-fail-closed.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, rm, copyFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { promisify } from 'node:util';

import {
  collectGrades,
  isPublishableGrade,
  processGradesFile,
} from '../aggregate-grades.mjs';

const execFileAsync = promisify(execFile);
const SCRIPTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');

const HEADLINE_FIELDS = [
  'avg_score_pct',
  'ci_pct',
  'perfect_count',
  'partial_count',
  'zero_count',
  'inconsistent_count',
];

// The three versions validateHistoricalHeadline owns. Every assertion below
// runs against all of them, because 1.1 and 1.2 joined the loose path one at a
// time and each arrival is a chance to be forgotten.
const HISTORICAL_VERSIONS = ['1.0', '1.1', '1.2'];

function historicalGrade(version, headline) {
  return {
    schema_version: version,
    experiment_id: `exp-${version}`,
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: headline,
      wow: {},
    },
    tasks: [{ task_id: 't1', pct: 50, error: null }],
  };
}

const FULL_HEADLINE = {
  avg_score_pct: 61.5,
  ci_pct: 3.1,
  perfect_count: 0,
  partial_count: 1,
  zero_count: 0,
  inconsistent_count: 0,
};

// ── 1. an absent headline is refused, not scored ──────────────────────────

test('an entirely absent headline is refused on every pre-1.3 version', () => {
  for (const version of HISTORICAL_VERSIONS) {
    const raw = historicalGrade(version, FULL_HEADLINE);
    delete raw.summary.openai_compat;
    assert.throws(
      () => processGradesFile(`absent-${version}.json`, raw),
      new RegExp(`schema ${version} headline summary is missing or invalid`),
      `schema ${version} published an absent headline`,
    );
  }
});

test('each individual headline field is refused when absent', () => {
  for (const version of HISTORICAL_VERSIONS) {
    for (const field of HEADLINE_FIELDS) {
      const headline = { ...FULL_HEADLINE };
      delete headline[field];
      assert.throws(
        () => processGradesFile(`absent-field.json`, historicalGrade(version, headline)),
        new RegExp(`schema ${version} headline ${field} is missing`),
        `schema ${version} published with ${field} absent`,
      );
    }
  }
});

test('a headline that is not an object is refused', () => {
  for (const headline of [null, [], 'nope', 42]) {
    assert.throws(
      () => processGradesFile('bad-shape.json', historicalGrade('1.0', headline)),
      /schema 1.0 headline summary is missing or invalid/,
    );
  }
});

test('a present but non-numeric headline is refused', () => {
  for (const field of ['avg_score_pct', 'ci_pct']) {
    for (const value of ['61.5', NaN, Infinity, undefined]) {
      const headline = { ...FULL_HEADLINE, [field]: value };
      assert.throws(
        () => processGradesFile('non-numeric.json', historicalGrade('1.0', headline)),
        /schema 1.0/,
        `${field}=${String(value)} was accepted`,
      );
    }
  }
});

test('a negative or fractional count is refused', () => {
  for (const field of ['perfect_count', 'partial_count', 'zero_count', 'inconsistent_count']) {
    for (const value of [-1, 1.5, '1']) {
      assert.throws(
        () => processGradesFile('bad-count.json', historicalGrade('1.0', { ...FULL_HEADLINE, [field]: value })),
        new RegExp(`schema 1.0 ${field} is invalid`),
        `${field}=${String(value)} was accepted`,
      );
    }
  }
});

// The pre-existing rule, unchanged. It is pinned here as well as in
// aggregate-grades.test.mjs because the absence checks above sit directly
// above it and share its message space.
test('an explicit null headline still fails with the message it has always used', () => {
  assert.throws(
    () => processGradesFile('null.json', historicalGrade('1.2', { ...FULL_HEADLINE, avg_score_pct: null })),
    /schema 1.0-1.2 headline must remain numeric/,
  );
});

// ── 2. NEGATIVE CONTROLS — a real number is still published ───────────────

test('a run that genuinely scored zero still publishes as zero, not as absent', () => {
  const zeroed = {
    avg_score_pct: 0,
    ci_pct: 0,
    perfect_count: 0,
    partial_count: 0,
    zero_count: 1,
    inconsistent_count: 0,
  };
  for (const version of HISTORICAL_VERSIONS) {
    const out = processGradesFile(`zero-${version}.json`, historicalGrade(version, zeroed));
    assert.equal(out.summary.avg_score_pct, 0, `schema ${version} swallowed a real zero`);
    assert.equal(out.summary.ci_pct, 0);
    assert.equal(out.summary.zero_score, 1);
    assert.equal(isPublishableGrade(out), true);
  }
});

// The one payload that reaches the projection with no number in it. Schema 1.3
// *requires* both headline fields to be null when graded_tasks is 0, so this is
// the shape the `: null` fall-through actually exists for -- and both fields
// need pinning, not just avg_score_pct. A mutation that turned ci_pct's
// fall-through back into `?? 0` survived the whole suite until this test was
// written: the existing all-excluded test asserts on the score and says nothing
// about the interval.
test('a schema 1.3 run that graded nothing keeps both headline fields absent', () => {
  const raw = {
    schema_version: '1.3',
    experiment_id: 'exp-nothing-graded',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4' },
    summary: {
      total_tasks: 1,
      graded_tasks: 0,
      error_tasks: 1,
      openai_compat: {
        avg_score_pct: null,
        ci_pct: null,
        perfect_count: 0,
        partial_count: 0,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 1 },
    },
    tasks: [{
      task_id: 't1',
      pct: 0,
      error: 'all_items_score_excluded',
      items: [{ verdict: 'judge_error', decided_by: 'judge', score_excluded: true }],
    }],
  };

  const out = processGradesFile('nothing-graded.json', raw);
  assert.equal(out.summary.avg_score_pct, null, 'an ungraded run is not a run that scored 0');
  assert.equal(out.summary.ci_pct, null, 'and its interval is not 0 either');
});

// The looseness of the pre-1.3 path is deliberate and load-bearing. Six of the
// eighteen item-level grade files published today have
// perfect + partial + zero != graded_tasks (220 vs 219, 220 vs 215); schema 1.3
// added the sum check, and every 1.3 file holds. Extending that check backwards
// would reject six real experiments, so this pins the fact that the historical
// validator asks only whether the keys are there.
test('a pre-1.3 headline whose counts do not sum to graded_tasks is still published', () => {
  const raw = historicalGrade('1.0', {
    ...FULL_HEADLINE,
    perfect_count: 100,
    partial_count: 99,
    zero_count: 20,
    inconsistent_count: 0,
  });
  raw.summary.total_tasks = 220;
  raw.summary.graded_tasks = 220;

  const out = processGradesFile('inconsistent-sum.json', raw);
  assert.equal(isPublishableGrade(out), true, 'six published experiments look like this');
  assert.equal(out.summary.avg_score_pct, 61.5);
});

test('an ordinary scored run is untouched', () => {
  const out = processGradesFile('ok.json', historicalGrade('1.0', FULL_HEADLINE));
  assert.equal(out.summary.avg_score_pct, 61.5);
  assert.equal(out.summary.ci_pct, 3.1);
  assert.equal(out.summary.partial_score, 1);
  assert.equal(isPublishableGrade(out), true);
});

// ── 3. every accepted version is claimed by a validator ───────────────────

// The guard is an import-time assertion, so the only honest way to test it is
// to import a module that violates it. The copy rewrites its own relative
// specifiers to absolute file URLs, which lets it live outside scripts/ and
// leaves nothing behind in the repository.
test('a version added to the reader but to no validator fails at import', async () => {
  const source = await readFile(join(SCRIPTS_DIR, 'aggregate-grades.mjs'), 'utf-8');

  const before = "const ITEM_LEVEL_VERSIONS = ['1.0', '1.1', '1.2', '1.3', '1.4'];";
  assert.equal(source.split(before).length - 1, 1, 'ITEM_LEVEL_VERSIONS moved; update this test');

  let probe = source.replace(
    before,
    "const ITEM_LEVEL_VERSIONS = ['1.0', '1.1', '1.2', '1.3', '1.4', '1.5'];",
  );
  probe = probe.replace(
    /from '\.\/([\w-]+\.mjs)'/g,
    (_m, name) => `from '${pathToFileURL(join(SCRIPTS_DIR, name)).href}'`,
  );

  const dir = await mkdtemp(join(tmpdir(), 'grade-version-probe-'));
  try {
    const probePath = join(dir, 'probe.mjs');
    await writeFile(probePath, probe, 'utf-8');
    await assert.rejects(
      import(pathToFileURL(probePath).href),
      /1\.5 .*validated by neither/s,
    );
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});

// ── 4. a rejected file is reported, not dropped ───────────────────────────

function entry(file, raw) {
  return { file, content: JSON.stringify(raw) };
}

test('collectGrades keeps good files and reports the bad one', () => {
  const broken = historicalGrade('1.0', FULL_HEADLINE);
  delete broken.summary.openai_compat;

  const { results, failures, excluded } = collectGrades([
    entry('good.json', historicalGrade('1.0', FULL_HEADLINE)),
    entry('broken.json', broken),
  ]);

  assert.equal(results.length, 1);
  assert.equal(results[0].id, 'good', 'id is the file stem, as it is in data/grades/');
  assert.equal(results[0].experiment_id, 'exp-1.0');
  assert.equal(excluded.length, 0);
  assert.deepEqual(failures.map((f) => f.file), ['broken.json']);
  assert.match(failures[0].message, /headline summary is missing or invalid/);
});

test('collectGrades reports every bad file, not just the first', () => {
  const absentHeadline = historicalGrade('1.1', FULL_HEADLINE);
  delete absentHeadline.summary.openai_compat;

  const { results, failures } = collectGrades([
    entry('a-broken.json', absentHeadline),
    { file: 'b-truncated.json', content: '{"schema_version": "1.0", "summ' },
    entry('c-null.json', historicalGrade('1.2', { ...FULL_HEADLINE, ci_pct: null })),
    entry('d-good.json', historicalGrade('1.0', FULL_HEADLINE)),
  ]);

  assert.deepEqual(
    failures.map((f) => f.file),
    ['a-broken.json', 'b-truncated.json', 'c-null.json'],
    'one run has to name every broken file, or fixing them takes one build each',
  );
  assert.equal(results.length, 1);
});

test('collectGrades records unparseable JSON as a failure rather than throwing', () => {
  const { results, failures } = collectGrades([
    { file: 'garbage.json', content: 'not json at all' },
  ]);
  assert.equal(results.length, 0);
  assert.equal(failures.length, 1);
  assert.equal(failures[0].file, 'garbage.json');
});

// A run the grader itself labelled not-for-publication is a decision, and it
// has to stay one. If this ever lands in `failures`, every partial grade in
// data/grades/ starts failing the build.
test('collectGrades separates a deliberate exclusion from a failure', () => {
  const entries = [];
  for (const runStatus of ['partial', 'diagnostic']) {
    const raw = historicalGrade('1.0', FULL_HEADLINE);
    raw.run_status = runStatus;
    raw.experiment_id = `exp-${runStatus}`;
    entries.push(entry(`${runStatus}.json`, raw));
  }
  entries.push(entry('final.json', historicalGrade('1.0', FULL_HEADLINE)));

  const { results, failures, excluded } = collectGrades(entries);

  assert.equal(failures.length, 0, 'an excluded run is not a broken file');
  assert.deepEqual(excluded.map((e) => e.file), ['partial.json', 'diagnostic.json']);
  assert.deepEqual(excluded.map((e) => e.status), ['grading_partial', 'grading_diagnostic']);
  assert.deepEqual(results.map((r) => r.experiment_id), ['exp-1.0']);
});

// ── 5. the exit code actually changes ─────────────────────────────────────

// Everything above calls the module directly. The defect was that main() threw
// nothing, so a green build was the only symptom anyone would ever see. These
// two run the real script end to end.
//
// The script resolves its own root from import.meta.url, so a scratch tree with
// the four modules copied into scripts/ is the production path, not a mock.
const SCRIPT_MODULES = [
  'aggregate-grades.mjs',
  'grade-identity.mjs',
  'selection-outcome.mjs',
  'cost-receipt.mjs',
];

async function scratchTree(files) {
  const root = await mkdtemp(join(tmpdir(), 'grade-aggregate-'));
  await mkdir(join(root, 'scripts'), { recursive: true });
  await mkdir(join(root, 'data', 'grades'), { recursive: true });
  for (const name of SCRIPT_MODULES) {
    await copyFile(join(SCRIPTS_DIR, name), join(root, 'scripts', name));
  }
  for (const [name, raw] of Object.entries(files)) {
    await writeFile(
      join(root, 'data', 'grades', name),
      typeof raw === 'string' ? raw : JSON.stringify(raw),
      'utf-8',
    );
  }
  return root;
}

async function runAggregate(root) {
  try {
    const { stdout, stderr } = await execFileAsync(
      process.execPath,
      [join(root, 'scripts', 'aggregate-grades.mjs')],
      { cwd: root },
    );
    return { code: 0, stdout, stderr };
  } catch (err) {
    return { code: err.code ?? 1, stdout: err.stdout ?? '', stderr: err.stderr ?? '' };
  }
}

test('the real script exits non-zero and writes no index when a file is refused', async () => {
  const broken = historicalGrade('1.0', FULL_HEADLINE);
  broken.experiment_id = 'exp-broken';
  delete broken.summary.openai_compat;

  const root = await scratchTree({
    'a-good.json': historicalGrade('1.0', FULL_HEADLINE),
    'b-broken.json': broken,
  });
  try {
    const { code, stderr } = await runAggregate(root);
    assert.equal(code, 1, 'a refused grade file must fail the build');
    assert.match(stderr, /b-broken\.json/);
    assert.match(stderr, /1 of 2 grade file\(s\) could not be read/);
    assert.equal(
      existsSync(join(root, 'public', 'generated', 'grades-index.json')),
      false,
      'a partial index must not be written',
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('the real script still exits 0 and publishes when every file is readable', async () => {
  const second = historicalGrade('1.1', FULL_HEADLINE);
  second.experiment_id = 'exp-second';

  const root = await scratchTree({
    'a-good.json': historicalGrade('1.0', FULL_HEADLINE),
    'b-good.json': second,
  });
  try {
    const { code, stdout } = await runAggregate(root);
    assert.equal(code, 0, stdout);
    assert.match(stdout, /Aggregated 2 grade file\(s\)/);
    const index = JSON.parse(
      await readFile(join(root, 'public', 'generated', 'grades-index.json'), 'utf-8'),
    );
    assert.deepEqual(
      index.map((r) => r.experiment_id).sort(),
      ['exp-1.0', 'exp-second'],
    );
    assert.deepEqual(index.map((r) => r.summary.avg_score_pct), [61.5, 61.5]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
