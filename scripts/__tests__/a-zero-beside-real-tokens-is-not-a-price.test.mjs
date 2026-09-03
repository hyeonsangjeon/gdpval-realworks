// The published grades index carried an amount nobody ever measured.
//
//   "summary_v1": { "cost": { "estimated_cost_usd": 0 } }
//
// Sixteen of the nineteen rows said it, and every one of them said it beside
// real tokens. The largest sits next to 130,092,056 input and 5,523,697 output
// tokens across 8,904 judge calls. Those runs did not cost nothing; nobody
// could price them, because the judge they used is deliberately absent from
// this repository's price table.
//
// One line put it there:
//
//   scripts/aggregate-grades.mjs   summary_v1: { ...summary, ... }
//
// Two lines below that spread, the receipt path already gets this right —
// "Only on a run that recorded something. Absent here is what the dashboard
// reads as 'no record' — never as $0." The spread above it carried a legacy
// payload's zero straight through without ever asking the question.
//
// It is the same defect as `a-row-with-no-score-is-not-a-zero`, one field over:
// there, an absent score published as 0; here, an unpriceable run publishes as
// $0. `#403` fixed the score half of it in this same function and left the
// money half standing.
//
// Nothing renders it today — `summaryTotalCell` in src/lib/cost.ts eats the
// schema-1.4 `cost_summary`, and no index row has one. That is why this was
// filed as a trap rather than a bug: the value sits in published JSON waiting
// for the first screen that reads it.
//
// What this file holds:
//
//   1. the sixteen are gone, measured on the real data/grades corpus rather
//      than on a fixture, and no row publishes a numeric amount there at all;
//   2. a genuine $0 survives — the one real zero the contract admits is a path
//      that never contacted a provider, and normalising it away would be the
//      opposite lie;
//   3. the evidence for that exemption has to be present, not merely
//      unfalsified: a missing counter is not a counter that read nothing;
//   4. the record beside the amount does not move. The tokens are what makes
//      the zero a lie, so a fix that edited them would be worthless;
//   5. `null` is what an unrecorded amount becomes, not absence — absence is a
//      documented crash in this repository, not a tidier answer;
//   6. the payload's own run-level `grading_cost` cannot ride the same spread
//      into the record. It is derived here from the per-task receipts or it is
//      not published.
//
// Run:
//   node --test scripts/__tests__/a-zero-beside-real-tokens-is-not-a-price.test.mjs

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { processGradesFile } from '../aggregate-grades.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GRADES_DIR = join(ROOT, 'data', 'grades');

// ── Fixtures ──────────────────────────────────────────────────────────────

/** One scored task row, which is all these assertions need underneath. */
function row(taskId = 't-1') {
  return {
    task_id: taskId,
    sector: 'test',
    occupation: 'test',
    items: [{
      rubric_item_id: 'i-1',
      max_score: 10,
      awarded_score: 5,
      verdict: 'partial',
      decided_by: 'judge',
      score_excluded: false,
    }],
    total_awarded: 5,
    total_max: 10,
    pct: 50,
    critical_fail: false,
    error: null,
  };
}

/**
 * The legacy cost block in the shape the pre-receipt summariser wrote it:
 * every field filled on every path, including the amount it could not compute.
 */
function legacyCost(over = {}) {
  return {
    total_judge_calls: 8904,
    total_input_tokens: 130092056,
    total_output_tokens: 5523697,
    total_judge_latency_sec: 41233.7,
    estimated_cost_usd: 0.0,
    ...over,
  };
}

/** A per-task cost receipt. `null` is the live case: priced by nobody. */
function receipt(amount) {
  const measured = amount !== null;
  return {
    schema_version: 'cost-receipt-v1',
    currency: 'USD',
    status: measured ? 'complete' : 'partial',
    estimated_cost_usd: measured ? amount : null,
    known_cost_usd: measured ? amount : 0,
    model_cost_usd: measured ? amount : 0,
    runtime_cost_usd: 0,
    model_calls: 107,
    usage: { input_tokens: 255254, output_tokens: 19355 },
    components: [],
    missing_reasons: measured ? [] : ['price_missing'],
  };
}

/** A 1.0 payload — the tier sixteen of the published files are on. */
function grade(cost, summaryOver = {}) {
  return {
    schema_version: '1.0',
    experiment_id: 'exp-zero-price',
    inference_model: 'gpt-5.2-chat',
    judge: { model: 'gpt-5.4-mini' },
    tasks: [row()],
    summary: {
      total_tasks: 1,
      graded_tasks: 1,
      error_tasks: 0,
      openai_compat: {
        avg_score_pct: 50,
        ci_pct: 1.5,
        perfect_count: 0,
        partial_count: 1,
        zero_count: 0,
        inconsistent_count: 0,
      },
      wow: { judge_error_rate: 0 },
      ...(cost === undefined ? {} : { cost }),
      ...summaryOver,
    },
  };
}

/** The `cost` block as it reaches the published record. */
function publishedCost(raw) {
  const record = processGradesFile('g.json', raw);
  assert.ok(record, 'the fixture did not survive the aggregator at all');
  return record.summary_v1.cost;
}

// ── 1. The sixteen are gone, on the real corpus ───────────────────────────

test('no published grade republishes an amount it never measured', async () => {
  const names = (await readdir(GRADES_DIR)).filter((n) => n.endsWith('.json'));
  assert.ok(names.length >= 19, `expected the published corpus, found ${names.length} files`);

  const offenders = [];
  let withABlock = 0;
  for (const name of names) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    const cost = processGradesFile(join(GRADES_DIR, name), raw)?.summary_v1?.cost;
    if (!cost) continue;
    withABlock += 1;
    if (typeof cost.estimated_cost_usd === 'number') {
      offenders.push(`${name}: ${cost.estimated_cost_usd}`);
    }
  }

  // Every one of the eighteen blocks records tokens, so on this corpus there
  // is no row the exemption in test 2 could apply to. If a future run really
  // does spend nothing, it will fail here and the fix is to say so in the
  // assertion — not to relax the rule.
  assert.equal(withABlock, 18, 'the corpus moved; recount before trusting the rest');
  assert.deepEqual(offenders, [], 'a published row still carries an amount beside real tokens');
});

test('the payload on disk still says zero — this is a projection, not an edit', async () => {
  // The rule this repository holds published data to is that nothing is
  // removed. The zeros stay exactly where they were written; what changed is
  // what the aggregator is willing to republish from them.
  const names = (await readdir(GRADES_DIR)).filter((n) => n.endsWith('.json'));
  let zerosOnDisk = 0;
  for (const name of names) {
    const raw = JSON.parse(await readFile(join(GRADES_DIR, name), 'utf8'));
    if (raw?.summary?.cost?.estimated_cost_usd === 0) zerosOnDisk += 1;
  }
  assert.equal(zerosOnDisk, 16, 'the published payloads must not have been rewritten');
});

// ── 2. A genuine zero survives ────────────────────────────────────────────

test('a run that contacted nobody keeps its zero', () => {
  // core/cost_receipts.py: "The only real $0 is a path that never contacted a
  // provider at all." Nulling this one would invent a missing record where
  // there is a complete one.
  const cost = publishedCost(grade(legacyCost({
    total_judge_calls: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
  })));
  assert.equal(cost.estimated_cost_usd, 0, 'a measured zero is a measurement');
});

test('any single counter is enough to make the zero a claim', () => {
  // One call with no tokens recorded, or tokens with no call counted, is still
  // a run that reached a provider. Each counter is checked on its own so no
  // one of them can be the loophole.
  for (const field of ['total_judge_calls', 'total_input_tokens', 'total_output_tokens']) {
    const cost = publishedCost(grade(legacyCost({
      total_judge_calls: 0,
      total_input_tokens: 0,
      total_output_tokens: 0,
      [field]: 1,
    })));
    assert.equal(cost.estimated_cost_usd, null, `${field} alone must defeat the exemption`);
  }
});

// ── 3. The exemption needs evidence, not silence ──────────────────────────

test('a missing counter is not a counter that read nothing', () => {
  // The block with no counters at all is the one that most looks like a free
  // run and least proves it. Fail closed: no record of contact is not a record
  // of no contact.
  const cost = publishedCost(grade({ estimated_cost_usd: 0.0 }));
  assert.equal(cost.estimated_cost_usd, null);

  // And two-thirds of the evidence is not the evidence.
  const partial = publishedCost(grade({
    total_judge_calls: 0,
    total_input_tokens: 0,
    estimated_cost_usd: 0.0,
  }));
  assert.equal(partial.estimated_cost_usd, null, 'total_output_tokens was never recorded');
});

// ── 4. The record beside the amount does not move ─────────────────────────

test('the tokens, calls and latency pass through untouched', () => {
  const raw = grade(legacyCost());
  const cost = publishedCost(raw);

  for (const [field, value] of Object.entries(raw.summary.cost)) {
    if (field === 'estimated_cost_usd') continue;
    assert.equal(cost[field], value, `${field} is the record and must not move`);
  }
  // Key order too, so a regenerated index differs only where a value does.
  assert.deepEqual(Object.keys(cost), Object.keys(raw.summary.cost));
});

test('every other summary field is passed through exactly as before', () => {
  const raw = grade(legacyCost());
  const record = processGradesFile('g.json', raw);

  assert.equal(record.summary_v1.total_tasks, raw.summary.total_tasks);
  assert.equal(record.summary_v1.graded_tasks, raw.summary.graded_tasks);
  assert.equal(record.summary_v1.error_tasks, raw.summary.error_tasks);
  assert.deepEqual(record.summary_v1.openai_compat, raw.summary.openai_compat);
  // The headline the dashboard actually renders is derived elsewhere and must
  // be untouched by anything here.
  assert.equal(record.summary.avg_score_pct, raw.summary.openai_compat.avg_score_pct);
});

// ── 5. null, not absent ───────────────────────────────────────────────────

test('an unrecorded amount is null and the key stays', () => {
  const cost = publishedCost(grade(legacyCost()));
  assert.ok(
    Object.prototype.hasOwnProperty.call(cost, 'estimated_cost_usd'),
    'dropping the key is the shape cost-receipt.mjs:711-716 documents as a crash: '
    + '`undefined !== null` is true, so a reader guarding on null reaches .toFixed on undefined',
  );
  assert.equal(cost.estimated_cost_usd, null);
});

test('a payload that already says null, and one with no block at all, are left alone', () => {
  // The two schema-1.3 rows and the dummy. Both already say "no record" in the
  // vocabulary the current writer uses; neither needs this code to intervene.
  assert.equal(publishedCost(grade(legacyCost({ estimated_cost_usd: null }))).estimated_cost_usd, null);

  const record = processGradesFile('g.json', grade(undefined));
  assert.equal(record.summary_v1.cost, undefined);
  assert.ok(
    !Object.prototype.hasOwnProperty.call(record.summary_v1, 'cost'),
    'a payload with no cost block must not gain one',
  );
});

test('a real amount is republished untouched', () => {
  // Nothing here is a campaign against numbers. A run that was priced keeps
  // its price, and so does a hypothetical negative correction.
  assert.equal(publishedCost(grade(legacyCost({ estimated_cost_usd: 411.8 }))).estimated_cost_usd, 411.8);
  assert.equal(publishedCost(grade(legacyCost({ estimated_cost_usd: 0.0001 }))).estimated_cost_usd, 0.0001);
});

// ── 6. The run summary is derived, never copied ───────────────────────────

test('a payload cannot publish its own run-level grading cost through the spread', () => {
  // Same spread, second money shape. `summarizeCostReceipts` returns null the
  // moment no task carries a receipt, so on a payload like this the override
  // below the spread does not fire and the payload's own figure was the one
  // that reached the record — a run total with no rows underneath it.
  const raw = grade(legacyCost(), {
    grading_cost: {
      schema_version: '1.0',
      currency: 'USD',
      status: 'complete',
      known_cost_usd: 999.99,
      estimated_cost_usd: 999.99,
    },
  });
  const record = processGradesFile('g.json', raw);
  assert.equal(record.summary_v1.grading_cost, undefined);
  assert.ok(!Object.prototype.hasOwnProperty.call(record.summary_v1, 'grading_cost'));
  // And it is not smuggled in under the 1.4 key either.
  assert.equal(record.cost_summary, undefined);
});

test('the derived summary is published, and it beats the payload’s own figure', () => {
  // The drop above must not take the real feature with it. On a schema-1.4
  // payload the per-task receipts add up to a run total, and that is the one
  // published — not the number the payload wrote at the top of itself.
  const raw = grade(legacyCost(), {
    grading_cost: {
      schema_version: 'cost-receipt-v1',
      currency: 'USD',
      status: 'complete',
      known_cost_usd: 999.99,
      estimated_cost_usd: 999.99,
      missing_reasons: [],
    },
  });
  raw.schema_version = '1.4';
  raw.tasks = [
    { ...row('t-1'), grading_cost: receipt(1.25) },
    { ...row('t-2'), grading_cost: receipt(0.75) },
  ];
  raw.summary.total_tasks = 2;
  raw.summary.graded_tasks = 2;
  raw.summary.openai_compat.partial_count = 2;

  const record = processGradesFile('g.json', raw);
  const derived = record.summary_v1.grading_cost;
  assert.ok(derived, 'the derived run cost was dropped along with the payload’s');
  assert.equal(derived.schema_version, 'cost-receipt-v1');
  assert.equal(derived.status, 'complete');
  assert.equal(derived.known_cost_usd, 2, 'the total must come from the rows');
  assert.equal(derived.estimated_cost_usd, 2);
  assert.equal(derived.receipt_tasks, 2);
  // And the same figure under the 1.4 key the dashboard reads.
  assert.equal(record.cost_summary.grading_cost.known_cost_usd, 2);
});

test('an unpriceable run derives a floor, never a total', () => {
  // The live case: the Stage 3 judge is deliberately absent from the price
  // table, so every receipt comes back partial with a $0 floor. The run total
  // must say partial and null, not $0.
  const raw = grade(legacyCost());
  raw.schema_version = '1.4';
  raw.tasks = [{ ...row('t-1'), grading_cost: receipt(null) }];

  const derived = processGradesFile('g.json', raw).summary_v1.grading_cost;
  assert.equal(derived.status, 'partial');
  assert.equal(derived.estimated_cost_usd, null, 'a floor must not be published as a total');
  assert.equal(derived.known_cost_usd, 0, 'the confirmed part is still zero, and is reported');
  assert.equal(derived.measured_tasks, 0);
});

// ── The two halves of the same rule, in the same function ─────────────────

test('the aggregator asks about contact, and asks it of the block itself', async () => {
  const source = await readFile(join(ROOT, 'scripts', 'aggregate-grades.mjs'), 'utf8');
  // The spread is the whole defect; if it comes back unfiltered, so does the
  // zero, and every assertion above would still pass on a fixture that never
  // reached it.
  assert.ok(
    !/summary_v1:\s*\{\s*(\/\/[^\n]*\n\s*)*\.\.\.summary,/.test(source),
    'summary_v1 spreads the payload summary unfiltered again',
  );
  assert.match(source, /\.\.\.projectLegacySummary\(summary\)/);
  // The exemption is the contract's, not a local convention: contact is read
  // off the counters, and all of them must be present and zero.
  assert.match(source, /LEGACY_CONTACT_COUNTERS\.every\(\(field\) => cost\[field\] === 0\)/);
});
