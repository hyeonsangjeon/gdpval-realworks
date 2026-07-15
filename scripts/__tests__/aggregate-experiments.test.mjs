import assert from 'node:assert/strict'
import test from 'node:test'

import { normalizeExecutionMetrics } from '../aggregate-experiments.mjs'


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
