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
import { mkdtemp, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { loadAllTests, main } from '../aggregate-tests.mjs';

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

// ── The markdown pass reads more than the loader used to promise ────────────
//
// Everything above is about a file that cannot be parsed. These are about one
// that parses into an object and is still missing something the second half of
// the script dereferences without a guard:
//
//     `${exp.condition_b.name} (${exp.condition_b.win_rate}%) | `
//     experiments.reduce((s, e) => s + e.delta, 0)
//
// Reproduced before it was fixed: with a second file holding no condition_b,
// the run printed `Found 2 experiments`, wrote experiments-index.json with
// both, and then exited 1 with `Cannot read properties of undefined (reading
// 'name')` at aggregate-tests.mjs:108 — a line number, naming no file, with
// the index already on disk and llm-context.md left as whatever the previous
// build had put there.

const WITHOUT = (field) =>
  VALID_YAML.split('\n')
    .reduce(
      (acc, line) => {
        if (/^\S/.test(line)) acc.skipping = line.startsWith(`${field}:`);
        if (!acc.skipping) acc.kept.push(line);
        return acc;
      },
      { kept: [], skipping: false },
    )
    .kept.join('\n')
    // condition_b is the last block, so dropping it takes the trailing blank
    // line with it and the next appended field lands on the previous line.
    .replace(/\n*$/, '\n');

test('a file holding only one condition names itself instead of dying at a line number', async () => {
  await withTestsDir({ 'exp900.yaml': WITHOUT('condition_b') }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /exp900\.yaml is present but holds no condition_b/,
    );
  });
  await withTestsDir({ 'exp900.yaml': WITHOUT('condition_a') }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /exp900\.yaml is present but holds no condition_a/,
    );
  });
});

test('a condition that is a scalar or a list is refused like a missing one', async () => {
  // `typeof null === 'object'`, and a list would index as one too, so both are
  // named explicitly rather than left to a truthiness check.
  for (const body of ['condition_b: just a name\n', 'condition_b:\n', 'condition_b:\n  - B\n']) {
    await withTestsDir({ 'exp900.yaml': WITHOUT('condition_b') + body }, async (dir) => {
      await assert.rejects(
        () => loadAllTests(dir),
        /exp900\.yaml is present but holds no condition_b/,
      );
    });
  }
});

test('a delta that is not a number is refused before it becomes +NaN%p', async () => {
  // This one never threw on its own. `s + e.delta` over a missing delta is
  // NaN, and the run completed, exited 0, and published `평균 Delta: +NaN%p`
  // into the document handed to an LLM as the whole truth about the corpus —
  // the same silent-wrong outcome as the empty file above, one field deeper.
  await withTestsDir({ 'exp900.yaml': WITHOUT('delta') }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /exp900\.yaml is present but its delta is not a number: undefined/,
    );
  });
  await withTestsDir({ 'exp900.yaml': `${WITHOUT('delta')}delta: "4"\n` }, async (dir) => {
    await assert.rejects(
      () => loadAllTests(dir),
      /exp900\.yaml is present but its delta is not a number: "4"/,
    );
  });
});

test('a corpus the markdown cannot render leaves no index behind', async () => {
  // The ordering guarantee, tested rather than asserted in a comment: main()
  // renders both documents before writing either, so a failure anywhere in the
  // second one cannot leave the first published. Checked against the real
  // failure — two files, one of them unrenderable — because the risk was never
  // a single bad file on its own but a good one carrying a bad one into a
  // half-written directory.
  await withTestsDir(
    { 'exp900.yaml': VALID_YAML, 'exp901.yaml': WITHOUT('condition_b') },
    async (dir) => {
      const out = await mkdtemp(join(tmpdir(), 'gdpval-aggregate-out-'));
      try {
        await assert.rejects(() => main(dir, out), /exp901\.yaml/);
        assert.deepEqual(
          await readdir(out).catch(() => []),
          [],
          'the index was written before the markdown pass failed',
        );
      } finally {
        await rm(out, { recursive: true, force: true });
      }
    },
  );
});

test('a corpus that renders writes both documents', async () => {
  // Teeth for the test above: if main() wrote nothing at all, an empty output
  // directory would prove nothing.
  await withTestsDir({ 'exp900.yaml': VALID_YAML }, async (dir) => {
    const out = await mkdtemp(join(tmpdir(), 'gdpval-aggregate-out-'));
    try {
      await main(dir, out);
      assert.deepEqual((await readdir(out)).sort(), [
        'experiments-index.json',
        'llm-context.md',
      ]);
    } finally {
      await rm(out, { recursive: true, force: true });
    }
  });
});
