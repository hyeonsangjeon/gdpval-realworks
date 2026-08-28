// Unit tests for scripts/cost-receipt.mjs
//
// This module is a mirror of batch-runner/core/cost_projection.py, so the
// cases below deliberately use the same amounts as tests/test_cost_projection.py:
// if the two implementations ever drift, one of these numbers moves and the
// other does not.
//
// Run:
//   node --test scripts/__tests__/cost-receipt.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  COST_RECEIPT_SCHEMA_VERSION,
  ESTIMATE_BASIS,
  projectCostLedgerReference,
  projectCostReceipt,
  summarizeCostReceipts,
} from '../cost-receipt.mjs';

function receipt(overrides = {}) {
  return {
    schema_version: COST_RECEIPT_SCHEMA_VERSION,
    currency: 'USD',
    status: 'complete',
    estimated_cost_usd: 0.25,
    known_cost_usd: 0.25,
    model_cost_usd: 0.2,
    runtime_cost_usd: 0.05,
    model_calls: 3,
    usage: { input_tokens: 1200, output_tokens: 400 },
    components: [
      {
        name: 'generation',
        status: 'complete',
        estimated_cost_usd: 0.25,
        known_cost_usd: 0.25,
        model_calls: 3,
        usage: { input_tokens: 1200 },
      },
    ],
    price_table_sha256: 'a'.repeat(64),
    missing_reasons: [],
    ...overrides,
  };
}

function row(projected, { succeeded = true } = {}) {
  return { receipt: projected, succeeded };
}

// ── Receipt projection ────────────────────────────────────────────────────

test('an absent receipt projects to null, never to zero', () => {
  assert.equal(projectCostReceipt(null), null);
  assert.equal(projectCostReceipt(undefined), null);
});

test('a complete receipt round-trips carrying the estimate basis', () => {
  const projected = projectCostReceipt(receipt());
  assert.equal(projected.status, 'complete');
  assert.equal(projected.known_cost_usd, 0.25);
  assert.equal(projected.estimate_basis, ESTIMATE_BASIS);
});

test('a genuine zero is a complete receipt, not a missing one', () => {
  const projected = projectCostReceipt(receipt({
    estimated_cost_usd: 0,
    known_cost_usd: 0,
    model_cost_usd: 0,
    runtime_cost_usd: 0,
    components: [],
  }));
  assert.equal(projected.status, 'complete');
  assert.equal(projected.known_cost_usd, 0);
});

test('malformed receipts throw rather than reach the dashboard', () => {
  const cases = [
    [{ schema_version: 'cost-receipt-v2' }, /schema_version/],
    [{ currency: 'KRW' }, /denominated/],
    [{ status: 'unknown' }, /must be one of/],
    [
      { status: 'complete', estimated_cost_usd: null, known_cost_usd: null },
      /complete without an amount/,
    ],
    [
      { status: 'complete', missing_reasons: ['price_table_missing'] },
      /reports missing components/,
    ],
    [
      { status: 'partial', known_cost_usd: 0.1, missing_reasons: [] },
      /partial without a reason code/,
    ],
    [
      {
        status: 'unavailable',
        estimated_cost_usd: null,
        known_cost_usd: null,
        model_cost_usd: null,
        runtime_cost_usd: null,
        components: [],
        missing_reasons: [],
      },
      /unavailable without a reason code/,
    ],
    [
      { status: 'not_run', components: [], missing_reasons: [] },
      /carries an amount/,
    ],
    [{ known_cost_usd: 0.9 }, /complete but its known amount differs/],
    [
      {
        status: 'partial',
        estimated_cost_usd: 0.25,
        known_cost_usd: 0.9,
        model_cost_usd: null,
        runtime_cost_usd: null,
        components: [],
        missing_reasons: ['runtime_price_missing'],
      },
      /known amount exceeds its estimate/,
    ],
    [{ estimated_cost_usd: Infinity }, /finite/],
    [{ estimated_cost_usd: -1 }, /out of range/],
    [{ model_cost_usd: 0.9 }, /exceeds the known amount/],
    [{ missing_reasons: ['the price table was not loaded'] }, /reason codes only/],
    [{ usage: { 'Input Tokens': 5 } }, /invalid key/],
    [{ price_table_sha256: 'not-a-digest' }, /sha256/],
  ];
  for (const [overrides, message] of cases) {
    assert.throws(() => projectCostReceipt(receipt(overrides)), message);
  }
});

test('duplicate component names are rejected', () => {
  const component = {
    name: 'generation',
    status: 'complete',
    estimated_cost_usd: 0.1,
    known_cost_usd: 0.1,
  };
  assert.throws(
    () => projectCostReceipt(receipt({
      estimated_cost_usd: 0.2,
      known_cost_usd: 0.2,
      model_cost_usd: 0.2,
      runtime_cost_usd: null,
      components: [component, { ...component }],
    })),
    /duplicate component names/,
  );
});

// ── Run summaries ─────────────────────────────────────────────────────────

test('a run with no receipts summarizes to null', () => {
  assert.equal(summarizeCostReceipts([row(null), row(null)]), null);
  assert.equal(summarizeCostReceipts([]), null);
});

test('a complete run reports a total and a per-deliverable figure', () => {
  const summary = summarizeCostReceipts(
    [
      row(projectCostReceipt(receipt())),
      row(projectCostReceipt(receipt({
        estimated_cost_usd: 0.75,
        known_cost_usd: 0.75,
        model_cost_usd: 0.75,
        runtime_cost_usd: null,
        components: [],
      }))),
    ],
    { successfulDeliverables: 2 },
  );

  assert.equal(summary.status, 'complete');
  assert.equal(summary.known_cost_usd, 1.0);
  assert.equal(summary.estimated_cost_usd, 1.0);
  assert.equal(summary.avg_cost_usd, 0.5);
  assert.equal(summary.median_cost_usd, 0.5);
  assert.equal(summary.max_cost_usd, 0.75);
  assert.equal(summary.cost_per_successful_deliverable_usd, 0.5);
  assert.equal(summary.coverage_pct, 100);
});

test('one partial receipt makes the run total a floor', () => {
  const summary = summarizeCostReceipts(
    [
      row(projectCostReceipt(receipt())),
      row(projectCostReceipt(receipt({
        status: 'partial',
        estimated_cost_usd: null,
        known_cost_usd: 0.1,
        model_cost_usd: 0.1,
        runtime_cost_usd: null,
        components: [],
        missing_reasons: ['runtime_price_missing'],
      }))),
    ],
    { successfulDeliverables: 2 },
  );

  assert.equal(summary.status, 'partial');
  assert.equal(summary.known_cost_usd, 0.35);
  // A floor is not a total, and it is not divided into a per-unit headline.
  assert.equal(summary.estimated_cost_usd, null);
  assert.equal(summary.cost_per_successful_deliverable_usd, null);
  assert.deepEqual(summary.missing_reasons, ['runtime_price_missing']);
});

test('unavailable receipts are counted but never priced', () => {
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(receipt({
      status: 'unavailable',
      estimated_cost_usd: null,
      known_cost_usd: null,
      model_cost_usd: null,
      runtime_cost_usd: null,
      components: [],
      missing_reasons: ['usage_not_recorded'],
    }))),
  ]);

  assert.equal(summary.status, 'unavailable');
  assert.equal(summary.measured_tasks, 0);
  assert.equal(summary.unavailable_tasks, 1);
  assert.equal(summary.avg_cost_usd, null);
  assert.equal(summary.known_cost_usd, 0);
});

test('failed-task cost is reported beside the total, not removed from it', () => {
  const summary = summarizeCostReceipts(
    [
      row(projectCostReceipt(receipt())),
      row(
        projectCostReceipt(receipt({
          estimated_cost_usd: 0.4,
          known_cost_usd: 0.4,
          model_cost_usd: 0.4,
          runtime_cost_usd: null,
          components: [],
        })),
        { succeeded: false },
      ),
    ],
    { successfulDeliverables: 1 },
  );

  assert.equal(summary.known_cost_usd, 0.65);
  assert.equal(summary.failed_task_count, 1);
  assert.equal(summary.failed_task_cost_usd, 0.4);
  assert.equal(summary.successful_deliverables, 1);
});

test('components aggregate across tasks', () => {
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(receipt())),
    row(projectCostReceipt(receipt())),
  ]);

  assert.deepEqual(summary.components, [
    {
      name: 'generation',
      tasks: 2,
      known_cost_usd: 0.5,
      complete_tasks: 2,
      model_calls: 6,
      status: 'complete',
    },
  ]);
});

test('coverage reports the rows that carry no receipt at all', () => {
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(receipt())),
    row(null),
    row(null),
    row(null),
  ]);

  assert.equal(summary.total_tasks, 4);
  assert.equal(summary.receipt_tasks, 1);
  assert.equal(summary.coverage_pct, 25);
});

// ── Ledger reference ──────────────────────────────────────────────────────

test('the ledger reference normalises to path and digest', () => {
  assert.deepEqual(
    projectCostLedgerReference({ path: 'cost_ledger.jsonl', sha256: 'b'.repeat(64) }),
    { path: 'cost_ledger.jsonl', sha256: 'b'.repeat(64) },
  );
  assert.equal(projectCostLedgerReference(null), null);
});

test('unusable ledger pointers are rejected', () => {
  for (const value of [
    { path: '../secrets.jsonl', sha256: 'b'.repeat(64) },
    { path: '/etc/passwd', sha256: 'b'.repeat(64) },
    { path: 'cost_ledger.jsonl', sha256: 'short' },
    { sha256: 'b'.repeat(64) },
  ]) {
    assert.throws(() => projectCostLedgerReference(value), /cost_ledger/);
  }
});
