// Fail-closed contract for scripts/aggregate-reports.mjs.
//
// Three faces of one quiet lie, all of which ended with a green build:
//
//   1. A report that failed to load was pushed onto an `errors` array, printed
//      as a console.warn, and dropped. `✓ Found N reports` then put a checkmark
//      beside a number that had silently shrunk, the index was written, and the
//      build exited 0. Only 7 of the 23 short_ids are pinned by a note
//      benchmark; the other 16 could vanish from the leaderboard, the trend view
//      and the sector matrix with nothing to show for it.
//   2. A bare `catch {}` collapsed ENOENT with a parse error, so a local report
//      that was PRESENT BUT CORRUPT was quietly replaced by whatever the remote
//      copy said — and the log reported `local: not found` about a file that was
//      sitting right there.
//   3. The short_id collision guard ran over the directories that had loaded, so
//      a dropped report took one side of its own collision away with it and the
//      guard passed. The check the file is proudest of was disarmed by the
//      swallow eight lines above it.
//
// Fixing (1) alone would have turned a documented, recurring HuggingFace 429
// into a red deploy — every one of the 23 fetches is unauthenticated, because
// there is no hub token anywhere in the Pages build. So the retry rule is pinned
// here too: a hole in the index and a hiccup on the wire are different failures.
//
// Run:
//   node --test scripts/__tests__/aggregate-reports-fail-closed.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, mkdir, readFile, writeFile, rm, copyFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

import {
  TRANSIENT_HTTP_STATUS,
  fetchHuggingFaceReport,
  fetchReportData,
} from '../aggregate-reports.mjs';

const execFileAsync = promisify(execFile);
const SCRIPTS_DIR = join(dirname(fileURLToPath(import.meta.url)), '..');

function reportFixture(overrides = {}) {
  return {
    meta: {
      date: '2026-01-01',
      model: 'gpt-5.4',
      condition_name: 'condition_a',
      experiment_name: 'fixture',
      execution_mode: 'subprocess',
      duration: '1m',
    },
    summary: {
      success_rate_pct: 90,
      avg_qa_score: 7.5,
      total_tasks: 10,
      success_count: 9,
      retried_count: 0,
    },
    sector_breakdown: [
      { sector: 'Retail', success_rate_pct: 90, avg_qa_score: 7.5, success: 9, total: 10 },
    ],
    task_results: [{ task_id: 't1', qa_score: 7.5 }],
    ...overrides,
  };
}

// A fetch stub that records every call, so a test can assert the network was
// never reached — which is the whole point of the local/remote separation.
function recordingFetch(responses) {
  const calls = [];
  const queue = [...responses];
  const impl = async (url) => {
    calls.push(url);
    const next = queue.length > 1 ? queue.shift() : queue[0];
    if (next instanceof Error) throw next;
    return next;
  };
  impl.calls = calls;
  return impl;
}

function httpResponse(status, { body = {}, retryAfter = null } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => (name.toLowerCase() === 'retry-after' ? retryAfter : null) },
    json: async () => {
      if (body instanceof Error) throw body;
      return body;
    },
  };
}

async function localTree(name, content) {
  const root = await mkdtemp(join(tmpdir(), 'report-local-'));
  const path = join(root, name);
  if (content !== null) await writeFile(path, content, 'utf-8');
  return { root, path };
}

// ── 1. a broken local file is never papered over by the network ───────────

test('a valid local report is used and the network is never touched', async () => {
  const { root, path } = await localTree('report_data.json', JSON.stringify(reportFixture()));
  const fetchImpl = recordingFetch([httpResponse(200, { body: { meta: { date: 'remote' } } })]);
  try {
    const { data, source } = await fetchReportData('exp901_x', path, { fetch: fetchImpl });
    assert.equal(source, 'local');
    assert.equal(data.meta.date, '2026-01-01');
    assert.deepEqual(fetchImpl.calls, [], 'a readable local report must not be fetched again');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('an absent local report falls through to HuggingFace', async () => {
  const { root, path } = await localTree('report_data.json', null);
  const fetchImpl = recordingFetch([httpResponse(200, { body: reportFixture() })]);
  try {
    const { data, source } = await fetchReportData('exp901_x', path, { fetch: fetchImpl });
    assert.equal(source, 'hf', 'ENOENT is the one case the fallback exists for');
    assert.equal(data.meta.model, 'gpt-5.4');
    assert.equal(fetchImpl.calls.length, 1);
    assert.match(fetchImpl.calls[0], /datasets\/HyeonSang\/exp901_x\/resolve\/main\/self_report\.json$/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// The substitution. A corrupt local file used to be indistinguishable from an
// absent one, so the remote copy stood in for it silently -- and a remote copy
// can say something different from the local one it replaced.
test('a corrupt local report fails instead of being replaced by the remote copy', async () => {
  const { root, path } = await localTree('report_data.json', '{"meta": {"date": "2026-01-02", "trunc');
  const fetchImpl = recordingFetch([httpResponse(200, { body: reportFixture() })]);
  try {
    await assert.rejects(
      fetchReportData('exp902_x', path, { fetch: fetchImpl }),
      /present but is not valid JSON/,
    );
    assert.deepEqual(
      fetchImpl.calls,
      [],
      'a broken local file must not be quietly swapped for a remote one',
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('a local report path that is not a file fails instead of falling through', async () => {
  const root = await mkdtemp(join(tmpdir(), 'report-local-'));
  const path = join(root, 'report_data.json');
  await mkdir(path); // EISDIR, not ENOENT
  const fetchImpl = recordingFetch([httpResponse(200, { body: reportFixture() })]);
  try {
    await assert.rejects(
      fetchReportData('exp903_x', path, { fetch: fetchImpl }),
      /could not be read/,
    );
    assert.deepEqual(fetchImpl.calls, [], 'only ENOENT means "publishes from HuggingFace"');
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// ── 2. a hiccup on the wire is retried; a hole is not ─────────────────────

const noSleep = async () => {};

test('a rate-limited fetch is retried and a later success is used', async () => {
  const fetchImpl = recordingFetch([
    httpResponse(429),
    httpResponse(200, { body: reportFixture() }),
  ]);
  const data = await fetchHuggingFaceReport('exp901_x', { fetch: fetchImpl, sleep: noSleep });
  assert.equal(data.meta.model, 'gpt-5.4');
  assert.equal(fetchImpl.calls.length, 2);
});

test('every status in the transient set is retried', async () => {
  for (const status of TRANSIENT_HTTP_STATUS) {
    const fetchImpl = recordingFetch([
      httpResponse(status),
      httpResponse(200, { body: reportFixture() }),
    ]);
    await fetchHuggingFaceReport('exp901_x', { fetch: fetchImpl, sleep: noSleep });
    assert.equal(fetchImpl.calls.length, 2, `HTTP ${status} was not retried`);
  }
});

// NEGATIVE CONTROL. A missing dataset is not a hiccup, and retrying it three
// times would just make a wrong directory name take three times as long to say
// so. 401 is what the hub actually answers for a dataset that is not there.
test('a permanent failure is not retried', async () => {
  for (const status of [400, 401, 403, 404, 410]) {
    const fetchImpl = recordingFetch([httpResponse(status)]);
    await assert.rejects(
      fetchHuggingFaceReport('exp901_x', { fetch: fetchImpl, sleep: noSleep }),
      new RegExp(`HuggingFace answered HTTP ${status}`),
    );
    assert.equal(fetchImpl.calls.length, 1, `HTTP ${status} should not be retried`);
  }
  assert.equal(TRANSIENT_HTTP_STATUS.has(404), false);
  assert.equal(TRANSIENT_HTTP_STATUS.has(401), false);
});

test('a run of transient answers is given up on and the last one is named', async () => {
  const fetchImpl = recordingFetch([httpResponse(429)]);
  await assert.rejects(
    fetchHuggingFaceReport('exp901_x', { fetch: fetchImpl, sleep: noSleep }),
    /no local report_data\.json, and HuggingFace answered HTTP 429/,
  );
  assert.equal(fetchImpl.calls.length, 3, 'three attempts, then the build hears about it');
});

test('a network error is retried and then reported', async () => {
  const fetchImpl = recordingFetch([new Error('ECONNRESET')]);
  await assert.rejects(
    fetchHuggingFaceReport('exp901_x', { fetch: fetchImpl, sleep: noSleep }),
    /network error: ECONNRESET/,
  );
  assert.equal(fetchImpl.calls.length, 3);
});

test('a 200 carrying a body that is not JSON is named, not retried', async () => {
  const fetchImpl = recordingFetch([
    httpResponse(200, { body: new SyntaxError('Unexpected token <') }),
  ]);
  await assert.rejects(
    fetchHuggingFaceReport('exp901_x', { fetch: fetchImpl, sleep: noSleep }),
    /HuggingFace body is not valid JSON/,
  );
  assert.equal(fetchImpl.calls.length, 1);
});

test('Retry-After is honoured, and capped so a deploy cannot be parked', async () => {
  const waits = [];
  const sleep = async (ms) => { waits.push(ms); };

  await assert.rejects(
    fetchHuggingFaceReport('exp901_x', {
      fetch: recordingFetch([httpResponse(429, { retryAfter: '5' })]),
      sleep,
    }),
    /HTTP 429/,
  );
  assert.deepEqual(waits, [5000, 5000], 'the hub asked for 5s and got 5s');

  waits.length = 0;
  await assert.rejects(
    fetchHuggingFaceReport('exp901_x', {
      fetch: recordingFetch([httpResponse(503, { retryAfter: '86400' })]),
      sleep,
    }),
    /HTTP 503/,
  );
  assert.deepEqual(waits, [20000, 20000], 'a day-long Retry-After must fail the build, not hang it');
});

test('backoff grows when the hub advises nothing', async () => {
  const waits = [];
  await assert.rejects(
    fetchHuggingFaceReport('exp901_x', {
      fetch: recordingFetch([httpResponse(502)]),
      sleep: async (ms) => { waits.push(ms); },
    }),
    /HTTP 502/,
  );
  assert.deepEqual(waits, [1000, 2000]);
});

// ── 3. the exit code actually changes ─────────────────────────────────────

// Everything above calls the module directly. The defect was that the build
// stayed green, so these run the real script end to end. Each directory gets a
// local report file, which keeps the whole group hermetic: no network, no
// retries, no wall-clock.
async function scratchTree(dirs) {
  const root = await mkdtemp(join(tmpdir(), 'report-aggregate-'));
  await mkdir(join(root, 'scripts'), { recursive: true });
  await copyFile(
    join(SCRIPTS_DIR, 'aggregate-reports.mjs'),
    join(root, 'scripts', 'aggregate-reports.mjs'),
  );
  for (const [dirName, content] of Object.entries(dirs)) {
    const reportDir = join(root, 'batch-runner', 'results', dirName, 'report');
    await mkdir(reportDir, { recursive: true });
    if (content !== null) {
      await writeFile(
        join(reportDir, 'report_data.json'),
        typeof content === 'string' ? content : JSON.stringify(content),
        'utf-8',
      );
    }
  }
  return root;
}

async function runAggregate(root) {
  try {
    const { stdout, stderr } = await execFileAsync(
      process.execPath,
      [join(root, 'scripts', 'aggregate-reports.mjs')],
      { cwd: root },
    );
    return { code: 0, stdout, stderr };
  } catch (err) {
    return { code: err.code ?? 1, stdout: err.stdout ?? '', stderr: err.stderr ?? '' };
  }
}

const INDEX_PATH = ['public', 'generated', 'reports-index.json'];

test('a report that cannot be loaded fails the build and writes no index', async () => {
  const root = await scratchTree({
    exp901_good: reportFixture(),
    exp902_corrupt: '{"meta": {"date": "2026-01-02", "trunc',
  });
  try {
    const { code, stderr } = await runAggregate(root);
    assert.equal(code, 1, 'a report that vanished used to leave the build green');
    assert.match(stderr, /1 of 2 report\(s\) could not be loaded/);
    assert.match(stderr, /exp902_corrupt/);
    assert.match(stderr, /leaderboard, the trend view/);
    assert.equal(
      existsSync(join(root, ...INDEX_PATH)),
      false,
      'a short index must not be published',
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test('every report readable publishes all of them and exits 0', async () => {
  const second = reportFixture();
  second.meta.date = '2026-02-01';
  second.sector_breakdown = [
    { sector: 'Health Care', success_rate_pct: 50, avg_qa_score: 5, success: 5, total: 10 },
  ];

  const root = await scratchTree({ exp901_good: reportFixture(), exp902_good: second });
  try {
    const { code, stdout } = await runAggregate(root);
    assert.equal(code, 0, stdout);
    assert.match(stdout, /Found 2 reports/);
    const index = JSON.parse(await readFile(join(root, ...INDEX_PATH), 'utf-8'));
    assert.deepEqual(
      index.reports.map((r) => r.short_id),
      ['exp902', 'exp901'],
      'newest first, as before',
    );
    assert.deepEqual(Object.keys(index.cross_experiment.sector_matrix), ['Health Care', 'Retail']);
    // task_results is stripped, task_qa keeps the compact map -- unchanged behaviour.
    assert.equal(index.reports[0].task_results, undefined);
    assert.deepEqual(index.reports[0].task_qa, { t1: 7.5 });
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// The disarm. The collision guard used to run over the reports that loaded, so
// dropping one side of a collision made the collision disappear with it.
test('a short_id collision is caught even when one side cannot be loaded', async () => {
  const root = await scratchTree({
    exp904_first: reportFixture(),
    exp904_second: '{"broken',
  });
  try {
    const { code, stderr } = await runAggregate(root);
    assert.equal(code, 1);
    assert.match(stderr, /duplicate short_id across batch-runner\/results directories/);
    assert.match(stderr, /exp904 <- exp904_first , exp904_second/);
    assert.equal(existsSync(join(root, ...INDEX_PATH)), false);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// NEGATIVE CONTROL. A directory that is not an experiment was skipped before
// and must still be skipped -- it must not become a report that "failed to
// load" and start failing the build.
test('a directory that is not an experiment is ignored, not counted as a failure', async () => {
  const root = await scratchTree({
    exp901_good: reportFixture(),
    'not-an-experiment': null,
    _scratch: '{"broken',
  });
  try {
    const { code, stdout } = await runAggregate(root);
    assert.equal(code, 0, stdout);
    assert.match(stdout, /Found 1 reports/);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

// NEGATIVE CONTROL. A report with no task_results is normal, not broken.
test('a report carrying no task_results still publishes', async () => {
  const bare = reportFixture();
  delete bare.task_results;
  const root = await scratchTree({ exp901_good: bare });
  try {
    const { code, stdout } = await runAggregate(root);
    assert.equal(code, 0, stdout);
    const index = JSON.parse(await readFile(join(root, ...INDEX_PATH), 'utf-8'));
    assert.deepEqual(index.reports[0].task_qa, {});
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
