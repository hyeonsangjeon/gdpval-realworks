// Absence contract for scripts/aggregate-experiments.mjs.
//
// The script writes public/generated/prompt-architecture.json, the file behind
// the dashboard's "Execution Config" and "Self-QA" panels. It filled in three
// settings with `||` defaults:
//
//     min_score:   qa.min_score || 5
//     max_retries: qa.max_retries || 1
//     max_retries: execution.max_retries || 5
//
// batch-runner/core/experiment_config.py is what actually runs these files, and
// where a key is absent it supplies 6 (:359), 2 (:357) and 3 (:291). So each
// default published a number that appeared in neither the file nor the run.
//
// Live on the committed corpus for execution.max_retries:
// exp002_single_baseline.yaml carries no `execution:` block at all, and its
// entry read "max_retries": 5 while the run used 3. The two QA defaults are
// latent — all 27 qa-enabled files state both keys — and are closed here
// because they are the same expression in the same object with the same
// disagreement.
//
// resume_max_rounds, one line above, already said `?? null` for the same file
// and PromptArchitectureView.tsx already rendered it as "—". The fix is to make
// the neighbours agree with it, not to invent a new rule.
//
// Scope boundary, pinned below: `mode` and `install_libreoffice` keep their
// defaults. Those agree with experiment_config.py (:289, :293), so a reader is
// told the truth about the run.
//
// Run:
//   node --test scripts/__tests__/a-setting-the-file-never-states-is-not-a-published-number.test.mjs

import assert from 'node:assert/strict';
import test from 'node:test';

import { buildExecutionConfig, buildQaPrompt } from '../aggregate-experiments.mjs';

test('an experiment file with no execution block publishes no retry count', () => {
  // exp002_single_baseline.yaml, exactly: no `execution:` key anywhere.
  const config = buildExecutionConfig(undefined);
  assert.equal(config.max_retries, null, 'must not publish 5; the run used 3');
  assert.equal(config.resume_max_rounds, null);
});

test('a retry count the file does state is published as stated', () => {
  assert.equal(buildExecutionConfig({ max_retries: 5 }).max_retries, 5);
  assert.equal(buildExecutionConfig({ max_retries: 1 }).max_retries, 1);
});

test('a stated zero is a stated zero, not the missing-key default', () => {
  // The `||` form could not tell "no retries" from "no answer".
  assert.equal(buildExecutionConfig({ max_retries: 0 }).max_retries, 0);
  assert.equal(buildExecutionConfig({ resume_max_rounds: 0 }).resume_max_rounds, 0);
});

test('mode and libreoffice keep their defaults, which match what the run does', () => {
  // Deliberately unchanged: experiment_config.py falls back to the same two
  // values, so publishing them does not misreport the run.
  const config = buildExecutionConfig({});
  assert.equal(config.mode, 'subprocess');
  assert.equal(config.install_libreoffice, false);
  assert.equal(buildExecutionConfig({ mode: 'code_interpreter' }).mode, 'code_interpreter');
});

test('metrics and agentic still reach the published config', () => {
  const config = buildExecutionConfig({
    metrics: { enabled: true },
    agentic: { compute_transport: 'remote' },
  });
  assert.deepEqual(config.metrics, { enabled: true });
  assert.deepEqual(config.agentic, { compute_transport: 'remote' });

  assert.equal('metrics' in buildExecutionConfig({ metrics: { enabled: false } }), false);
  assert.equal('agentic' in buildExecutionConfig({}), false);
});

test('a Self-QA block that omits its thresholds publishes no thresholds', () => {
  const qa = buildQaPrompt({ enabled: true, prompt: 'inspect the deliverable' });
  assert.equal(qa.enabled, true);
  assert.equal(qa.min_score, null, 'must not publish 5; the run used 6');
  assert.equal(qa.max_retries, null, 'must not publish 1; the run used 2');
  assert.equal(qa.content, 'inspect the deliverable');
});

test('stated Self-QA thresholds pass through, including a stated zero', () => {
  const stated = buildQaPrompt({ enabled: true, min_score: 5, max_retries: 1, prompt: 'x' });
  assert.equal(stated.min_score, 5);
  assert.equal(stated.max_retries, 1);
  assert.equal(buildQaPrompt({ enabled: true, min_score: 0 }).min_score, 0);
});

test('Self-QA that is off still publishes only the off state', () => {
  // Unchanged shape: no thresholds are claimed for a step that did not run.
  assert.deepEqual(buildQaPrompt({ enabled: false, min_score: 5 }), { enabled: false, content: null });
  assert.deepEqual(buildQaPrompt(undefined), { enabled: false, content: null });
});
