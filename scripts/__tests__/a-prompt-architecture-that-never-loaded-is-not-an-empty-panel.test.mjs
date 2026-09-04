// An index that never arrived is not an experiment that ran without prompts.
//
// `ExperimentDetail.tsx` draws a full-width button reading "View Prompt
// Architecture / System · User Prompt · QA · Execution Config", and gated the
// body behind it on `showPromptArch && promptArch`. With no architecture to
// show, pressing it turned the chevron down, flipped the label to "Hide", and
// drew nothing at all — the same blank an experiment with no system message, no
// user prompt, no Self-QA and no execution config would draw.
//
// Three of the twenty-six routable experiments are in that state on the
// committed corpus (exp026c, exp030, exp031), for two producer reasons in
// `scripts/aggregate-experiments.mjs`: `!f.includes('smoke')` at :94 excludes
// exp026c although its results are published, and the `readdir` at :93 does not
// recurse into `experiments/execution_envelope/`, where exp030 and exp031 live.
// A failed fetch of `generated/prompt-architecture.json` puts all twenty-six
// there at once.
//
// `useExperimentPrompt` already separated the reasons — it tracks `loading` and
// sets `error` from the failed request — and both were discarded at the
// destructure. So the panel had the facts and threw them away.
//
// The fix names which of the four states holds. This file executes that
// decision rather than pattern-matching the JSX around it:
// `src/components/dashboard/promptArchitectureReading.ts` is import-free
// precisely so esbuild — already installed, as vite depends on it — can hand it
// to node.
//
// The producer's two file-discovery gaps are deliberately NOT fixed here.
// Adding entries is a judgement about what belongs on the dashboard; what is
// wrong today is the claim the panel makes when an entry is absent. The corpus
// test below is written so it keeps passing either way: it derives the gap from
// the two generated indexes instead of hard-coding the three ids.
//
// Run:
//   node --test scripts/__tests__/a-prompt-architecture-that-never-loaded-is-not-an-empty-panel.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const SRC_DIR = join(ROOT, 'src');
const READING_FILE = join(SRC_DIR, 'components', 'dashboard', 'promptArchitectureReading.ts');
const PANEL_FILE = join(SRC_DIR, 'components', 'dashboard', 'PromptArchitectureView.tsx');
const PAGE_FILE = join(SRC_DIR, 'pages', 'ExperimentDetail.tsx');
const HOOK_FILE = join(SRC_DIR, 'hooks', 'useExperimentPrompt.ts');
const REPORTS_INDEX = join(ROOT, 'public', 'generated', 'reports-index.json');
const PROMPT_INDEX = join(ROOT, 'public', 'generated', 'prompt-architecture.json');

// ── Loading the decision under test ───────────────────────────────────────

/**
 * The reading rule, type annotations stripped and nothing else touched.
 *
 * A failure to load is a real failure and is left to throw. Skipping would
 * leave the suite green while the executable assertions quietly stopped
 * running, which is the same class of mistake this whole change is about.
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

/**
 * A file with its comments gone: what the code actually does.
 *
 * Scanning the raw text would trip on the comments that quote the old gate in
 * order to explain why it was wrong, which is the documentation that keeps this
 * from being undone. esbuild drops comments and turns JSX text into string
 * arguments, and `transform` does not rename locals, so identifiers survive.
 */
async function renderedText(file) {
  const require = createRequire(join(ROOT, 'package.json'));
  const raw = await readFile(file, 'utf8');
  const { code } = await require('esbuild').transform(raw, {
    loader: { '.tsx': 'tsx', '.ts': 'ts', '.jsx': 'jsx', '.js': 'js' }[extname(file)],
    format: 'esm',
    target: 'node18',
  });
  return code;
}

/** Every state the reading can be in, so nothing below tests only one branch. */
const ALL_STATES = ['recorded', 'loading', 'unreadable', 'not_recorded'];

// ── A. The four states are told apart ─────────────────────────────────────

test('an architecture that loaded is simply drawn, with no notice in the way', async () => {
  const { readPromptArchitecture } = await loadReading();
  const reading = readPromptArchitecture({
    hasPrompt: true, loading: false, error: null, shortId: 'exp017',
  });
  assert.equal(reading.state, 'recorded');
  assert.equal(reading.title, '');
  assert.equal(reading.detail, '');
});

test('an index still in flight says nothing is known yet', async () => {
  const { readPromptArchitecture } = await loadReading();
  const reading = readPromptArchitecture({
    hasPrompt: false, loading: true, error: null, shortId: 'exp030',
  });
  assert.equal(reading.state, 'loading');
  assert.match(reading.title, /Loading/i);
  assert.match(reading.detail, /not come back yet/i);
});

test('a failed fetch is reported as a failed fetch, and carries its reason', async () => {
  const { readPromptArchitecture } = await loadReading();
  const reading = readPromptArchitecture({
    hasPrompt: false, loading: false, error: 'HTTP 404', shortId: 'exp017',
  });
  assert.equal(reading.state, 'unreadable');
  assert.match(reading.detail, /HTTP 404/, 'the reader is not told why it failed');
  assert.match(reading.detail, /prompt-architecture\.json/, 'the file that failed is not named');
});

test('an index that loaded without this experiment names the producer', async () => {
  const { readPromptArchitecture, PROMPT_ARCHITECTURE_SOURCE } = await loadReading();
  const reading = readPromptArchitecture({
    hasPrompt: false, loading: false, error: null, shortId: 'exp030',
  });
  assert.equal(reading.state, 'not_recorded');
  assert.ok(
    reading.detail.includes(PROMPT_ARCHITECTURE_SOURCE),
    'the reader is not told which script would have published the entry',
  );
});

test('the named producer is a file that exists', async () => {
  // A pointer the reader cannot follow is worse than none: it reads as a fact.
  const { PROMPT_ARCHITECTURE_SOURCE } = await loadReading();
  await access(join(ROOT, PROMPT_ARCHITECTURE_SOURCE));
});

// ── B. The distinction the whole change is about ──────────────────────────

test('neither empty is stated as an experiment that ran without prompt settings', async () => {
  const { readPromptArchitecture } = await loadReading();
  const unreadable = readPromptArchitecture({
    hasPrompt: false, loading: false, error: 'Failed to fetch', shortId: 'exp017',
  });
  const absent = readPromptArchitecture({
    hasPrompt: false, loading: false, error: null, shortId: 'exp017',
  });

  // Said out loud, not merely implied by omission.
  assert.match(
    unreadable.detail, /not a record that .* ran without prompt settings/,
    'a failed fetch does not disclaim the reading a blank panel invites',
  );
  assert.match(
    absent.detail, /not the same as this run having had none/,
    'a missing entry does not disclaim the reading a blank panel invites',
  );

  // And the two are not the same sentence with a different heading.
  assert.notEqual(unreadable.title, absent.title);
  assert.notEqual(unreadable.detail, absent.detail);
});

test('no state the panel can reach draws a blank', async () => {
  // The defect was a panel with nothing in it. Every empty state must have
  // something to say, or the fix has a hole in exactly the old shape.
  const { readPromptArchitecture } = await loadReading();
  const seen = new Set();
  const inputs = [
    { hasPrompt: true, loading: false, error: null, shortId: 'exp017' },
    { hasPrompt: false, loading: true, error: null, shortId: 'exp017' },
    { hasPrompt: false, loading: false, error: 'boom', shortId: 'exp017' },
    { hasPrompt: false, loading: false, error: null, shortId: 'exp017' },
    { hasPrompt: false, loading: true, error: 'boom', shortId: null },
    { hasPrompt: false, loading: false, error: '', shortId: undefined },
  ];
  for (const input of inputs) {
    const reading = readPromptArchitecture(input);
    seen.add(reading.state);
    assert.ok(ALL_STATES.includes(reading.state), `unknown state ${reading.state}`);
    if (reading.state === 'recorded') continue;
    assert.ok(reading.title.trim().length > 0, `${reading.state} has no heading`);
    assert.ok(reading.detail.trim().length > 0, `${reading.state} has no explanation`);
  }
  assert.deepEqual([...seen].sort(), [...ALL_STATES].sort(), 'a state was never reached');
});

test('an architecture that arrived wins over a stale error', async () => {
  // `useExperimentPrompt` keeps the last error string; if a later attempt
  // succeeds there is an architecture to draw and no reason to apologise.
  const { readPromptArchitecture } = await loadReading();
  const reading = readPromptArchitecture({
    hasPrompt: true, loading: true, error: 'HTTP 500', shortId: 'exp017',
  });
  assert.equal(reading.state, 'recorded');
});

test('an unreadable index is not misreported as still loading', async () => {
  // The hook sets `error` and clears `loading` in the same catch, but a render
  // between the two must not tell the reader to keep waiting for a request
  // that already failed.
  const { readPromptArchitecture } = await loadReading();
  const reading = readPromptArchitecture({
    hasPrompt: false, loading: true, error: 'HTTP 404', shortId: 'exp017',
  });
  assert.equal(reading.state, 'unreadable');
});

// ── C. The experiment is named, or honestly not named ─────────────────────

test('the experiment is named so the reader can go and look', async () => {
  const { readPromptArchitecture } = await loadReading();
  for (const error of [null, 'HTTP 404']) {
    const reading = readPromptArchitecture({
      hasPrompt: false, loading: false, error, shortId: 'exp026c',
    });
    assert.match(reading.detail, /exp026c/, `${String(error)} state did not name the experiment`);
  }
});

test('a missing or blank id falls back to a phrase, never to an empty gap', async () => {
  const { readPromptArchitecture } = await loadReading();
  for (const shortId of [null, undefined, '', '   ']) {
    const reading = readPromptArchitecture({
      hasPrompt: false, loading: false, error: null, shortId,
    });
    assert.match(
      reading.detail, /this experiment/,
      `shortId ${JSON.stringify(shortId)} left a hole in the sentence`,
    );
    assert.ok(!/ {2}/.test(reading.detail), 'a blank id was interpolated verbatim');
  }
  assert.match(
    readPromptArchitecture({
      hasPrompt: false, loading: false, error: null, shortId: '  exp031  ',
    }).detail,
    /exp031/,
  );
});

// ── D. The real corpus, both indexes ──────────────────────────────────────

test('every routable experiment reaches a state, and the gap is not a blank', async () => {
  const [reportsRaw, promptRaw] = await Promise.all([
    readFile(REPORTS_INDEX, 'utf8'),
    readFile(PROMPT_INDEX, 'utf8'),
  ]);
  const routable = JSON.parse(reportsRaw).reports.map((r) => r.short_id);
  const published = new Set(JSON.parse(promptRaw).experiments.map((e) => e.short_id));
  assert.ok(routable.length > 0, 'reports-index.json published no routable experiment');

  const { readPromptArchitecture } = await loadReading();
  const gaps = [];
  for (const shortId of routable) {
    const hasPrompt = published.has(shortId);
    const reading = readPromptArchitecture({ hasPrompt, loading: false, error: null, shortId });
    if (hasPrompt) {
      assert.equal(reading.state, 'recorded', `${shortId} has an entry but reads as empty`);
      continue;
    }
    gaps.push(shortId);
    assert.equal(reading.state, 'not_recorded');
    assert.match(reading.detail, new RegExp(shortId));
  }

  // Not asserted to be exactly three: the producer's file discovery may be
  // widened later, and this test is about what the panel says, not about how
  // many gaps there are. Zero gaps is a pass.
  assert.ok(gaps.length <= routable.length);
});

test('a failed fetch would put every routable experiment in the same stated state', async () => {
  const routable = JSON.parse(await readFile(REPORTS_INDEX, 'utf8')).reports.map((r) => r.short_id);
  const { readPromptArchitecture } = await loadReading();
  for (const shortId of routable) {
    const reading = readPromptArchitecture({
      hasPrompt: false, loading: false, error: 'HTTP 500', shortId,
    });
    assert.equal(reading.state, 'unreadable', `${shortId} did not read as unreadable`);
    assert.match(reading.detail, new RegExp(shortId));
  }
});

// ── E. The page and the panel are actually wired to it ────────────────────

test('the page routes the empty case through the reading instead of drawing nothing', async () => {
  const code = await renderedText(PAGE_FILE);

  assert.match(code, /readPromptArchitecture\(/, 'the page never calls the reading');
  assert.match(code, /PromptArchitectureNotice/, 'the page never renders the notice');

  // The old gate, in any spacing. Comments are already gone; see renderedText.
  assert.ok(
    !/showPromptArch\s*&&\s*promptArch\b/.test(code),
    'the panel body is gated on the architecture again, so an absent one draws a blank',
  );
  // The button must still toggle the panel.
  assert.match(code, /showPromptArch\s*&&/, 'the panel no longer responds to the button');
});

test('the page keeps both reasons the hook measured', async () => {
  const code = await renderedText(PAGE_FILE);
  for (const field of ['loading: promptLoading', 'error: promptError']) {
    assert.ok(code.includes(field), `the page discarded ${field} again`);
  }
});

test('the hook still separates the two reasons the reading depends on', async () => {
  // If `useExperimentPrompt` stopped reporting either one, the reading would
  // silently collapse two states into one and this file would still pass.
  const code = await renderedText(HOOK_FILE);
  assert.match(code, /setError\(/, 'the hook no longer records why a fetch failed');
  assert.match(code, /setLoading\(/, 'the hook no longer records that a fetch is in flight');
});

test('the notice shows both halves of the reading', async () => {
  const code = await renderedText(PANEL_FILE);
  const at = code.indexOf('PromptArchitectureNotice');
  assert.ok(at >= 0, 'the notice component is gone');
  const body = code.slice(at);
  assert.match(body, /reading\.title/, 'the notice drops the heading');
  assert.match(body, /reading\.detail/, 'the notice drops the explanation — a blank again');
});
