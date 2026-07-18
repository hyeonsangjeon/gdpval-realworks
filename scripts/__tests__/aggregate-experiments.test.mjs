import assert from 'node:assert/strict';
import test from 'node:test';

import {
  normalizeAgenticConfig,
  normalizeExecutionMetrics,
} from '../aggregate-experiments.mjs';


test('legacy execution config omits optional agentic config', () => {
  assert.equal(normalizeAgenticConfig(undefined), null);
});


test('agentic config uses a public allowlist', () => {
  const normalized = normalizeAgenticConfig({
    compute_transport: 'remote',
    image: `image@sha256:${'a'.repeat(64)}`,
    verifier_image: `verifier@sha256:${'b'.repeat(64)}`,
    memory_gb: 8,
    cpus: 2,
    limits: {
      max_model_iterations: 6,
      max_tool_calls: 8,
      secret_limit: 99,
    },
    pricing_table: {
      path: '/private/pricing.json',
      sha256: 'c'.repeat(64),
    },
    authorization: {
      signed_envelope_path: '/private/approval.json',
      owner_public_key_path: '/private/owner.pem',
    },
    budget_ledger_path: '/private/budget.sqlite3',
    seccomp_profile: '/private/seccomp.json',
  });

  assert.deepEqual(normalized, {
    compute_transport: 'remote',
    image: `image@sha256:${'a'.repeat(64)}`,
    verifier_image: `verifier@sha256:${'b'.repeat(64)}`,
    memory_gb: 8,
    cpus: 2,
    limits: {
      max_model_iterations: 6,
      max_tool_calls: 8,
    },
    pricing_table: { sha256: 'c'.repeat(64) },
  });
  assert.equal(JSON.stringify(normalized).includes('/private/'), false);
});


test('execution metrics require literal boolean true', () => {
  assert.equal(normalizeExecutionMetrics(undefined), null)
  assert.equal(normalizeExecutionMetrics(null), null)
  assert.equal(normalizeExecutionMetrics({}), null)
  assert.equal(normalizeExecutionMetrics({ enabled: false }), null)
  assert.equal(normalizeExecutionMetrics({ enabled: 'false' }), null)
  assert.equal(normalizeExecutionMetrics({ enabled: 1 }), null)
})


test('execution metrics discard undeclared fields when enabled', () => {
  assert.deepEqual(
    normalizeExecutionMetrics({ enabled: true, raw_output: 'must-not-leak' }),
    { enabled: true },
  )
})
