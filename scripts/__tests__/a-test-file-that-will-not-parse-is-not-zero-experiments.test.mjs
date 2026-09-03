// Fail-closed contract for scripts/aggregate-tests.mjs.
//
// This is the first script in `prebuild`, `predev` and `aggregate`, and it is
// the one that writes public/generated/experiments-index.json — the file the
// dashboard reads to know which experiments exist at all.
//
// It read each data/tests/*.yaml outside a try, so an unreadable file ended the
// build, and parsed each one inside a try that only logged:
//
//     } catch (err) {
//       console.error(`⚠️  ${file} 파싱 실패:`, err.message);
//     }
//
// So a file that was PRESENT BUT MALFORMED was dropped, `Found N experiments`
// printed a number that had silently shrunk beside a checkmark, the index was
// written, and the process exited 0. data/tests/ holds exactly one file, so one
// bad byte published `{"experiments": []}` and a llm-context.md reading
// `총 실험 수: 0` / `평균 Delta: +NaN%p`, with a green build and a green deploy.
//
// aggregate-reports.mjs already draws this line for the same job in the same
// directory — ENOENT returns null, anything else throws "present but is not
// valid JSON" — and scripts/__tests__/aggregate-reports-fail-closed.test.mjs
// was written for this exact shape. aggregate-tests.mjs was never revisited
// after the bootstrap commit.
//
// The empty-file case is here because without it the throw is trivially
// bypassed: an empty .yaml parses to null, `{ ...null }` is `{}`, and that
// id-less row reaches experiments-index.json — which is written before the
// markdown pass dies on it — so the index lands wrong and the failure names no
// file.
//
// Run:
//   node --test scripts/__tests__/a-test-file-that-will-not-parse-is-not-zero-experiments.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { loadAllTests } from '../aggregate-tests.mjs';

const VALID_YAML = [
  'id: exp900',
  'name: fixture',
  'model: gpt-5.4',
  'tasks: 2',
  'delta: 4',
  'condition_a:',
  '  name: A',
  '  prompt: a',
  '  win_rate: 50',
  'condition_b:',
  '  name: B',
  '  prompt: b',
  '  win_rate: 54',
  '',
].join('\n');

async function withTestsDir(files, run) {
  const dir = await mkdtemp(join(tmpdir(), 'gdpval-aggregate-tests-'));
  try {
    for (const [name, body] of Object.entries(files)) {
      await writeFile(join(dir, name), body);
    }
    return await run(dir);
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}

test('a valid test file still loads, and carries its source file name', async () => {
  await withTestsDir({ 'exp900.yaml': VALID_YAML }, async (dir) => {
    const experiments = await loadAllTests(dir);
    assert.equal(experiments.length, 1);
    assert.equal(experiments[0].id, 'exp900');
    assert.equal(experiments[0]._sourceFile, 'exp900.yaml');
  });
});

test('a malformed test file ends the run instead of shrinking the index', async () => {
  await withTestsDir(
    { 'exp900.yaml': `${VALID_YAML}analysis: broken: nested: mapping\n` },
    async (dir) => {
      await assert.rejects(
        () => loadAllTests(dir),
        (err) => {
          assert.match(err.message, /exp900\.yaml is present but is not valid YAML/);
          return true;
        },
      );
    },
  );
});

test('one unparseable file does not quietly leave the others as the whole corpus', async () => {
  // The failure mode this file exists for: the good file loads, the bad one is
  // dropped, and a shortened list is published as if it were complete.
  await withTestsDir(
    {
      'exp900.yaml': VALID_YAML,
      'exp901.yaml': 'a: b: c\n',
    },
    async (dir) => {
      await assert.rejects(() => loadAllTests(dir), /exp901\.yaml is present but is not valid YAML/);
    },
  );
});

test('an empty test file is refused rather than becoming an id-less row', async () => {
  await withTestsDir({ 'empty.yaml': '' }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /empty\.yaml is present but does not hold an experiment: parsed as nothing/,
    );
  });
});

test('a test file holding a list, or a bare scalar, is refused', async () => {
  await withTestsDir({ 'list.yaml': '- one\n- two\n' }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /list\.yaml is present but does not hold an experiment: parsed as a list/,
    );
  });
  await withTestsDir({ 'scalar.yaml': 'just a string\n' }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /scalar\.yaml is present but does not hold an experiment: parsed as string/,
    );
  });
});

test('a directory holding no yaml at all is not silently an empty corpus', async () => {
  // Not a throw: an empty directory is a real, readable state, unlike a file
  // that is there and cannot be used. Pinned so the difference stays visible.
  await withTestsDir({ 'notes.md': '# not a test file\n' }, async (dir) => {
    assert.deepEqual(await loadAllTests(dir), []);
  });
});

test('importing the module does not run the aggregation', () => {
  // If main() still ran at import time, loading this test file would rewrite
  // public/generated/ from the real data/tests/ as a side effect.
  assert.equal(typeof loadAllTests, 'function');
});
