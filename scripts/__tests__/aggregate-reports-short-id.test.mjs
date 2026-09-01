import assert from 'node:assert/strict';
import test from 'node:test';
import { readdir, readFile } from 'node:fs/promises';

import { extractShortId, findShortIdCollisions } from '../aggregate-reports.mjs';

const REPO_ROOT = new URL('../../', import.meta.url);

async function resultDirNames() {
  const entries = await readdir(new URL('batch-runner/results/', REPO_ROOT), {
    withFileTypes: true,
  });
  return entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
}

async function pinnedRuntimeIds() {
  const source = await readFile(new URL('src/lib/runtimeNoteBenchmark.ts', REPO_ROOT), 'utf-8');
  const line = source.match(/export const RUNTIME_REPORT_IDS = \[(.*?)\]/s);
  assert.ok(line, 'RUNTIME_REPORT_IDS must be declared as a literal array');
  return [...line[1].matchAll(/'([^']+)'/g)].map((match) => match[1]);
}

test('a variant suffix stays part of the short_id', () => {
  assert.equal(extractShortId('exp003_GPT52Chat_baseline_runner_exec'), 'exp003');
  assert.equal(extractShortId('exp026_sandbox_skills_multimodal'), 'exp026');
  assert.equal(extractShortId('exp026c_cost_receipt_smoke'), 'exp026c');
  assert.equal(extractShortId('exp026s_sandbox_ci_smoke'), 'exp026s');
  assert.equal(extractShortId('not-an-experiment'), null);
});

test('a variant directory does not collapse onto its base experiment', () => {
  // Before this rule, every one of these resolved to `exp026`, so the last one
  // processed overwrote the real exp026's cells in the sector matrix and the
  // runtime note degraded to `invalid`.
  assert.deepEqual(
    findShortIdCollisions([
      'exp026_sandbox_skills_multimodal',
      'exp026c_cost_receipt_smoke',
      'exp026s_sandbox_ci_smoke',
    ]),
    [],
  );

  // The comparison the next roadmap phase wants: one experiment, three runtimes.
  assert.deepEqual(
    findShortIdCollisions([
      'exp028a_sandbox',
      'exp028b_subprocess',
      'exp028c_code_interpreter',
    ]),
    [],
  );
});

test('two directories sharing a short_id are still reported', () => {
  assert.deepEqual(
    findShortIdCollisions(['exp030_first_attempt', 'exp030_second_attempt']),
    [['exp030', ['exp030_first_attempt', 'exp030_second_attempt']]],
  );
});

test('no committed result directory collides with another', async () => {
  const dirs = await resultDirNames();
  assert.ok(dirs.length > 0, 'expected at least one result directory');
  assert.deepEqual(findShortIdCollisions(dirs), []);
});

test('every pinned runtime id resolves from exactly one result directory', async () => {
  const [dirs, pinned] = await Promise.all([resultDirNames(), pinnedRuntimeIds()]);
  assert.ok(pinned.length > 0, 'expected RUNTIME_REPORT_IDS to be non-empty');

  for (const shortId of pinned) {
    const matches = dirs.filter((dirName) => extractShortId(dirName) === shortId);
    assert.equal(
      matches.length,
      1,
      `${shortId} must resolve from exactly one directory, got ${matches.length}: ${matches.join(', ')}`,
    );
  }
});
