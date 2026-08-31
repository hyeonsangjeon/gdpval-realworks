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

/**
 * One receipt line in the shape batch-runner/core/cost_receipts.py writes it.
 *
 * Note what is *not* here: no `estimated_cost_usd`. The producer puts an
 * estimate on the receipt and nowhere else, so a line only ever reports what
 * was confirmed.
 */
function component(overrides = {}) {
  return {
    name: 'generation',
    stage: 'generation',
    retry_kind: 'none',
    status: 'complete',
    known_cost_usd: 0.25,
    model_calls: 3,
    usage: { input_tokens: 1200 },
    missing_reasons: [],
    ...overrides,
  };
}

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
    components: [component()],
    price_table_sha256: 'a'.repeat(64),
    missing_reasons: [],
    ...overrides,
  };
}

/**
 * A receipt with no amount, in the shape the producer actually writes.
 *
 * cost_receipts.py fills every money field on every status, so an
 * `unavailable` receipt arrives carrying `0.0` rather than `null`. A test that
 * passed `null` here would go green against a payload that never occurs, and
 * the placeholder zero would reach the screen as `$0.0000`.
 */
function unmeasured(status, overrides = {}) {
  return receipt({
    status,
    estimated_cost_usd: null,
    known_cost_usd: 0,
    model_cost_usd: 0,
    runtime_cost_usd: 0,
    components: [],
    missing_reasons: status === 'not_run' ? [] : ['usage_absent'],
    ...overrides,
  });
}

function row(projected, { succeeded = true } = {}) {
  return { receipt: projected, succeeded };
}

// ── Receipt projection ────────────────────────────────────────────────────

test('an absent receipt projects to null, never to zero', () => {
  assert.equal(projectCostReceipt(null), null);
  assert.equal(projectCostReceipt(undefined), null);
});

test('a complete receipt round-trips without inventing fields', () => {
  const projected = projectCostReceipt(receipt());
  assert.equal(projected.status, 'complete');
  assert.equal(projected.known_cost_usd, 0.25);
  // The producer's schema is closed (`additionalProperties: false`), so the
  // estimate-basis disclaimer rides on the summary this module builds, never on
  // a receipt this module merely relays.
  assert.equal('estimate_basis' in projected, false);
});

test('a component keeps its stage and retry kind', () => {
  const projected = projectCostReceipt(receipt({
    components: [component({ name: 'retry', stage: 'self_qa', retry_kind: 'semantic' })],
  }));
  // Which stage a retry belonged to is what makes the charge readable. The
  // displayed label collapses it; the record must not.
  assert.deepEqual(projected.components[0], {
    name: 'retry',
    stage: 'self_qa',
    retry_kind: 'semantic',
    status: 'complete',
    known_cost_usd: 0.25,
    model_calls: 3,
    usage: { input_tokens: 1200 },
    missing_reasons: [],
  });
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

test('the placeholder zero of an unmeasured receipt becomes no record', () => {
  for (const status of ['unavailable', 'not_run']) {
    const projected = projectCostReceipt(unmeasured(status));
    assert.equal(projected.status, status);
    // Every money field arrived as 0. None of them survives as a number: a
    // receipt that recorded nothing must not read as a run that cost nothing.
    assert.equal(projected.known_cost_usd, null);
    assert.equal(projected.model_cost_usd, null);
    assert.equal(projected.runtime_cost_usd, null);
    assert.equal(projected.estimated_cost_usd, null);
  }
});

test('a partial receipt that confirmed nothing reports no floor', () => {
  const projected = projectCostReceipt(receipt({
    status: 'partial',
    estimated_cost_usd: null,
    known_cost_usd: 0,
    model_cost_usd: 0,
    runtime_cost_usd: 0,
    components: [component({ status: 'partial', known_cost_usd: 0 })],
    missing_reasons: ['price_missing'],
  }));
  // "At least $0" is true of every run ever made and tells the reader nothing.
  assert.equal(projected.known_cost_usd, null);
  assert.equal(projected.components[0].known_cost_usd, null);
});

test('a partial receipt keeps the part it did confirm', () => {
  const projected = projectCostReceipt(receipt({
    status: 'partial',
    estimated_cost_usd: null,
    known_cost_usd: 0.12,
    model_cost_usd: 0.12,
    runtime_cost_usd: 0,
    components: [component({ status: 'partial', known_cost_usd: 0.12 })],
    missing_reasons: ['runtime_cost_unpriced'],
  }));
  assert.equal(projected.known_cost_usd, 0.12);
  assert.equal(projected.runtime_cost_usd, null);
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
      { status: 'complete', missing_reasons: ['price_missing'] },
      /reports missing components/,
    ],
    [
      {
        status: 'partial',
        estimated_cost_usd: null,
        known_cost_usd: 0.1,
        missing_reasons: [],
      },
      /partial without a reason code/,
    ],
    [
      {
        status: 'unavailable',
        estimated_cost_usd: null,
        known_cost_usd: 0,
        model_cost_usd: 0,
        runtime_cost_usd: 0,
        components: [],
        missing_reasons: [],
      },
      /unavailable without a reason code/,
    ],
    // An estimate is the one thing only a complete receipt may name.
    [
      { status: 'partial', missing_reasons: ['price_missing'] },
      /partial but carries an estimate/,
    ],
    [
      {
        status: 'not_run',
        known_cost_usd: null,
        model_cost_usd: null,
        runtime_cost_usd: null,
        components: [],
        missing_reasons: [],
      },
      /not_run but carries an estimate/,
    ],
    // …and a non-zero amount under a status that recorded nothing is not a
    // placeholder, it is a receipt contradicting itself.
    [
      {
        status: 'not_run',
        estimated_cost_usd: null,
        known_cost_usd: 0.4,
        components: [],
        missing_reasons: [],
      },
      /is not_run but carries an amount/,
    ],
    [{ known_cost_usd: 0.9 }, /complete but its known amount differs/],
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

// ── Two bounds, because they are two quantities ───────────────────────────
test('an honest token total is not out of range', () => {
  // 21,688,749 input tokens across 2,337 marking calls is what one published
  // shard recorded — about nine thousand tokens of rubric and deliverable per
  // call. Both readers refused that figure while the calls behind it used two
  // hundredths of a percent of the same allowance, because one constant
  // bounded both fields and it had been sized for the smaller one.
  const projected = projectCostReceipt(receipt({
    model_calls: 2337,
    usage: { input_tokens: 21_688_749, output_tokens: 400 },
    components: [component({ model_calls: 2337, usage: { input_tokens: 21_688_749 } })],
  }));
  assert.equal(projected.model_calls, 2337);
  assert.equal(projected.usage.input_tokens, 21_688_749);
  assert.equal(projected.components[0].usage.input_tokens, 21_688_749);
});

test('the calls bound did not move when the token bound did', () => {
  // The half that could have gone unnoticed. Raising one shared constant would
  // have taken model_calls with it, and no published payload would have shown
  // it: real call counts are four thousand times under the bound either way.
  assert.doesNotThrow(() => projectCostReceipt(receipt({ model_calls: 10_000_000 })));
  assert.throws(
    () => projectCostReceipt(receipt({ model_calls: 10_000_001 })),
    /model_calls is out of range/,
  );
  assert.throws(
    () => projectCostReceipt(receipt({ model_calls: Number.MAX_SAFE_INTEGER })),
    /model_calls is out of range/,
  );
});

test('the token bound is where this reader stops agreeing with the file', () => {
  // Not a guess about how large a run gets — a property of the format. Above
  // MAX_SAFE_INTEGER a JSON integer does not survive JSON.parse: the file says
  // one number and this reader holds another, with Number.isInteger satisfied
  // the whole way, so nothing downstream would notice. The bound is the last
  // integer both sides still read the same, and cost_projection.py is pinned
  // to it for that reason.
  const parsed = JSON.parse('{"n":9007199254740993}');
  assert.equal(String(parsed.n), '9007199254740992');  // the file said ...93
  assert.equal(Number.isInteger(parsed.n), true);      // and the guard says yes

  const exact = Number.MAX_SAFE_INTEGER;
  assert.equal(JSON.parse(`{"n":${exact}}`).n, exact);
  assert.doesNotThrow(
    () => projectCostReceipt(receipt({ usage: { input_tokens: exact } })),
  );
  assert.throws(
    () => projectCostReceipt(receipt({ usage: { input_tokens: exact + 1 } })),
    /usage.input_tokens is out of range/,
  );
});

test('two retries from different stages are two lines', () => {
  // Both derive the name `retry` from the producer. Rejecting the second as a
  // duplicate would drop a call that really was billed.
  const projected = projectCostReceipt(receipt({
    estimated_cost_usd: 0.2,
    known_cost_usd: 0.2,
    model_cost_usd: 0.2,
    runtime_cost_usd: null,
    components: [
      component({
        name: 'retry', stage: 'generation', retry_kind: 'infrastructure',
        known_cost_usd: 0.1, model_calls: 1,
      }),
      component({
        name: 'retry', stage: 'self_qa', retry_kind: 'semantic',
        known_cost_usd: 0.1, model_calls: 1,
      }),
    ],
  }));
  assert.deepEqual(projected.components.map((line) => line.stage), ['generation', 'self_qa']);
});

test('the same stage and retry kind twice is rejected', () => {
  const line = component({ known_cost_usd: 0.1, model_calls: 1 });
  assert.throws(
    () => projectCostReceipt(receipt({
      estimated_cost_usd: 0.2,
      known_cost_usd: 0.2,
      model_cost_usd: 0.2,
      runtime_cost_usd: null,
      components: [line, { ...line }],
    })),
    /duplicate component keys/,
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
  // The disclaimer lives on the summary, which is the payload a reader sees a
  // headline number in. It is not a field of the receipt itself.
  assert.equal(summary.estimate_basis, ESTIMATE_BASIS);
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
        missing_reasons: ['runtime_cost_unpriced'],
      }))),
    ],
    { successfulDeliverables: 2 },
  );

  assert.equal(summary.status, 'partial');
  assert.equal(summary.known_cost_usd, 0.35);
  // A floor is not a total, and it is not divided into a per-unit headline.
  assert.equal(summary.estimated_cost_usd, null);
  assert.equal(summary.cost_per_successful_deliverable_usd, null);
  assert.deepEqual(summary.missing_reasons, ['runtime_cost_unpriced']);
});

test('unavailable receipts are counted but never priced', () => {
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(unmeasured('unavailable'))),
  ]);

  assert.equal(summary.status, 'unavailable');
  assert.equal(summary.measured_tasks, 0);
  assert.equal(summary.unavailable_tasks, 1);
  assert.equal(summary.avg_cost_usd, null);
  assert.equal(summary.known_cost_usd, 0);
});

test('a run against a model with no published price stays partial, not not_run', () => {
  // The shape Stage 3 actually produced. `azure:gpt-5.6-sol` is absent from
  // experiments/execution_envelope/model_price_table.json, so every judge call
  // settles `price_missing` and the receipt's known floor is $0 — the contract
  // working, since the calls and their tokens are kept and only the USD is
  // refused. `measuredAmount` then nulls that floor so no reader takes it for
  // "so far it has cost nothing", which leaves the run with nothing measured.
  //
  // Nothing measured is not nothing done. Deciding the run's state from the
  // amounts sent this past `partial` to `not_run`, which renders as 미채점
  // beside 17 graded tasks and 1784 calls.
  const unpriced = projectCostReceipt(unmeasured('partial', {
    model_calls: 114,
    usage: { input_tokens: 3142728, output_tokens: 46245 },
    missing_reasons: ['price_missing'],
    components: [
      component({
        name: 'grading',
        stage: 'grading',
        status: 'partial',
        known_cost_usd: 0,
        model_calls: 113,
        missing_reasons: ['price_missing'],
      }),
    ],
  }));

  const summary = summarizeCostReceipts([row(unpriced), row(unpriced)]);

  assert.equal(summary.status, 'partial');
  assert.equal(summary.partial_tasks, 2);
  assert.equal(summary.not_run_tasks, 0);
  assert.equal(summary.measured_tasks, 0);
  // No figure was measured, so none is offered. The run is still not erased.
  assert.equal(summary.estimated_cost_usd, null);
  assert.deepEqual(summary.missing_reasons, ['price_missing']);
});

test('work that never ran does not stop the rest being a total', () => {
  // cost_receipts.py drops not_run receipts before deciding the summary's
  // status, so a run where one task was skipped and the rest priced cleanly is
  // complete. Agreeing with it matters more than either answer alone: the
  // dashboard reads this summariser and the report reads that one, off the
  // same file.
  const summary = summarizeCostReceipts(
    [
      row(projectCostReceipt(receipt())),
      row(projectCostReceipt(unmeasured('not_run'))),
    ],
    { successfulDeliverables: 1 },
  );

  assert.equal(summary.status, 'complete');
  assert.equal(summary.not_run_tasks, 1);
  assert.equal(summary.known_cost_usd, 0.25);
  assert.equal(summary.estimated_cost_usd, 0.25);
  assert.equal(summary.cost_per_successful_deliverable_usd, 0.25);
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
  // Every failure here was priced, so the amount is the amount.
  assert.equal(summary.failed_measured_tasks, 1);
  assert.equal(summary.successful_deliverables, 1);
});

test('a failure billed against an unpriced model is not counted as measured', () => {
  // Mirrors test_a_failure_billed_against_an_unpriced_model_is_not_counted_as_measured.
  //
  // Two failures against a model the price table has no entry for contribute
  // nothing to the sum, and the sum they never joined stays 0 — the same
  // number two free failures leave behind. Only the count separates them.
  const unpriced = () =>
    row(projectCostReceipt(unmeasured('partial', { missing_reasons: ['price_missing'] })), {
      succeeded: false,
    });
  const summary = summarizeCostReceipts([unpriced(), unpriced()]);

  assert.equal(summary.failed_task_count, 2);
  assert.equal(summary.failed_measured_tasks, 0);
  assert.equal(summary.failed_task_cost_usd, 0);
});

test('a genuinely free failure stays apart from one that was never priced', () => {
  // The discrimination the count exists for, asserted as a pair. Both report
  // failed_task_cost_usd === 0; if failed_measured_tasks ever stops telling
  // them apart, a paid failure reads as a free one.
  const free = summarizeCostReceipts([
    row(
      projectCostReceipt(receipt({
        estimated_cost_usd: 0,
        known_cost_usd: 0,
        model_cost_usd: 0,
        runtime_cost_usd: 0,
        model_calls: 0,
        components: [],
      })),
      { succeeded: false },
    ),
  ]);
  const neverPriced = summarizeCostReceipts([
    row(projectCostReceipt(unmeasured('partial', { missing_reasons: ['price_missing'] })), {
      succeeded: false,
    }),
  ]);

  assert.equal(free.failed_task_cost_usd, 0);
  assert.equal(neverPriced.failed_task_cost_usd, 0);
  assert.equal(free.failed_task_count, 1);
  assert.equal(neverPriced.failed_task_count, 1);
  assert.equal(free.failed_measured_tasks, 1);
  assert.equal(neverPriced.failed_measured_tasks, 0);
});

test('a partly priced set of failures reports how much of it was priced', () => {
  const summary = summarizeCostReceipts([
    row(
      projectCostReceipt(receipt({
        estimated_cost_usd: 0.4,
        known_cost_usd: 0.4,
        model_cost_usd: 0.4,
      })),
      { succeeded: false },
    ),
    row(projectCostReceipt(unmeasured('partial', { missing_reasons: ['price_missing'] })), {
      succeeded: false,
    }),
  ]);

  assert.equal(summary.failed_task_count, 2);
  assert.equal(summary.failed_measured_tasks, 1);
  assert.equal(summary.failed_task_cost_usd, 0.4);
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

test('two retries in one task are one task in the component total', () => {
  // `tasks` sits beside the amount as "how many tasks paid this". A task that
  // retried twice paid it once; counting the lines would make that column
  // exceed the number of tasks in the run.
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(receipt({
      estimated_cost_usd: 0.2,
      known_cost_usd: 0.2,
      model_cost_usd: 0.2,
      runtime_cost_usd: null,
      components: [
        component({
          name: 'retry', stage: 'generation', retry_kind: 'infrastructure',
          known_cost_usd: 0.15, model_calls: 2, usage: {},
        }),
        component({
          name: 'retry', stage: 'self_qa', retry_kind: 'semantic',
          known_cost_usd: 0.05, model_calls: 1, usage: {},
        }),
      ],
    }))),
  ]);

  assert.deepEqual(summary.components, [
    {
      name: 'retry',
      tasks: 1,
      known_cost_usd: 0.2,
      complete_tasks: 1,
      model_calls: 3,
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

// ── A row with no receipt is a hole, not a task that cost zero ────────────
//
// `costReceiptsByTask` in scripts/aggregate-grades.mjs only records a task
// whose `grading_cost` projects non-null, then `gradingCostSummary` maps over
// *every* raw task. A graded run where some tasks carry a cost and others do
// not is therefore the ordinary shape here, not an edge case — and every such
// task that also errored was subtracted from the failure count while still
// counting in `total_tasks`.

test('a failed row with no receipt is still counted as a failure', () => {
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(receipt())),
    row(null, { succeeded: false }),
  ]);

  assert.equal(summary.failed_task_count, 1);
  // Nothing is invented about what it cost: it joins neither the amount nor
  // the count of failures that could be priced.
  assert.equal(summary.failed_measured_tasks, 0);
  assert.equal(summary.failed_task_cost_usd, 0);
});

test('a successful row with no receipt is not counted as a failure', () => {
  // The negative control. A missing cost record says nothing about whether the
  // work succeeded, so the branch that rescues the failing row must not
  // conjure a failure out of the quiet one.
  const summary = summarizeCostReceipts([
    row(projectCostReceipt(receipt())),
    row(null),
  ]);

  assert.equal(summary.failed_task_count, 0);
  assert.equal(summary.total_tasks, 2);
  assert.equal(summary.receipt_tasks, 1);
});

test('a row with no receipt stops the run reading as complete', () => {
  const summary = summarizeCostReceipts(
    [row(projectCostReceipt(receipt())), row(null, { succeeded: false })],
    { successfulDeliverables: 1 },
  );

  assert.equal(summary.status, 'partial');
  // A floor is published as a floor: the recorded amount stays, the headline
  // total and the per-unit figure do not.
  assert.equal(summary.known_cost_usd, 0.25);
  assert.equal(summary.estimated_cost_usd, null);
  assert.equal(summary.cost_per_successful_deliverable_usd, null);
});

test('only a complete run is downgraded by a missing receipt', () => {
  // partial, unavailable and not_run already decline to claim the run is
  // whole, so the downgrade has nothing to add to them. Pinning each one keeps
  // a later edit from widening the branch into runs it never meant to touch.
  const cases = [
    ['partial', unmeasured('partial', { known_cost_usd: 0.1 })],
    ['unavailable', unmeasured('unavailable')],
    ['not_run', unmeasured('not_run')],
  ];
  for (const [expected, projected] of cases) {
    const summary = summarizeCostReceipts([
      row(projectCostReceipt(projected)),
      row(null, { succeeded: false }),
    ]);
    assert.equal(summary.status, expected);
  }
});

test('a run where every row carries a receipt is unchanged', () => {
  // The published-experiment guarantee: with no hole the branch is
  // unreachable, so a fully recorded run keeps its total and its per-unit
  // figure.
  const summary = summarizeCostReceipts(
    [row(projectCostReceipt(receipt())), row(projectCostReceipt(receipt()))],
    { successfulDeliverables: 2 },
  );

  assert.equal(summary.status, 'complete');
  assert.equal(summary.estimated_cost_usd, 0.5);
  assert.equal(summary.cost_per_successful_deliverable_usd, 0.25);
  assert.equal(summary.failed_task_count, 0);
});

test('a run where no row carries a receipt is still no record', () => {
  // Already asserted above for the summary as a whole; repeated here as the
  // boundary of this change, because a run of nothing but holes must keep
  // rendering as "no record" rather than as a partial run that cost nothing.
  assert.equal(
    summarizeCostReceipts([row(null), row(null, { succeeded: false })]),
    null,
  );
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

// ── Reason vocabulary ─────────────────────────────────────────────────────

/**
 * `missing_reasons` is a closed enum. The grade schema enforces it on the way
 * in, the producer defines it, and the dashboard translates it — three copies
 * of one list, which is exactly the shape that drifts.
 *
 * The dashboard's copy is TypeScript, so it is read as text rather than
 * imported. That is uglier than an import and worth it: a ninth reason added
 * to the schema fails here, at `node --test`, instead of reaching the screen
 * as an untranslated slug next to Korean.
 */
test('every reason the schema allows has a Korean label', async () => {
  const { readFile } = await import('node:fs/promises');
  const root = new URL('../../', import.meta.url);

  const schema = JSON.parse(
    await readFile(new URL('batch-runner/schemas/grade.schema.json', root), 'utf8'),
  );
  const allowed = schema.$defs.costMissingReason.enum;
  assert.ok(allowed.length >= 8, 'the schema should still constrain the reasons');

  const source = await readFile(new URL('src/lib/cost.ts', root), 'utf8');
  const block = source.match(
    /const MISSING_REASON_LABELS: Record<string, string> = \{([^}]*)\}/,
  );
  assert.ok(block, 'src/lib/cost.ts should still declare MISSING_REASON_LABELS');
  const labelled = [...block[1].matchAll(/^\s{2}(\w+):/gm)].map((m) => m[1]);

  assert.deepEqual([...labelled].sort(), [...allowed].sort());
});
