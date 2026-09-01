// Read side of the per-task cost receipt contract (`cost-receipt-v1`).
//
// This is the JavaScript mirror of batch-runner/core/cost_projection.py. The
// Python side carries problem-solving receipts from Step 3 into
// self_report.json; this side reads the grading receipts that arrive in the
// grade JSON. Same schema, same four statuses, same refusal to invent a
// number.
//
// Two properties are the whole point:
//
//   * A run that carries no receipts summarises to `null`. Every experiment
//     graded before the instrumentation existed keeps reading as "no record"
//     — never as a run that cost nothing.
//   * `unavailable` (the step ran and recorded nothing), `not_run` (the step
//     never ran), `partial` (priced in part) and a real $0 under `complete`
//     are four different findings, so they stay four different states all the
//     way to the screen.
//
// Every amount is a usage-based estimate. ESTIMATE_BASIS travels with each
// summary so no consumer can present one of these figures as a cloud invoice.

export const COST_RECEIPT_SCHEMA_VERSION = 'cost-receipt-v1';
export const COST_CURRENCY = 'USD';
export const ESTIMATE_BASIS = 'usage_estimate_not_azure_invoice';

/**
 * `complete` — a figure we stand behind, including a genuine $0.
 * `partial`  — priced in part; known_cost_usd is a lower bound.
 * `unavailable` — the step ran and recorded nothing.
 * `not_run`  — the step never ran, so there is nothing to record.
 */
export const COST_STATUSES = ['complete', 'partial', 'unavailable', 'not_run'];

/** Statuses that contribute a number to the run-level totals. */
const MEASURED_STATUSES = ['complete', 'partial'];

export const COST_FIELDS = ['problem_solving_cost', 'grading_cost'];

/**
 * The closed vocabulary the producer publishes for `components[].name`
 * (batch-runner/core/cost_receipts.py: COMPONENT_NAMES). Recorded here for
 * readers, not enforced here: the grade schema is the gate, and a second copy
 * that disagreed would reject a receipt the producer considers valid.
 *
 * There is deliberately no `runtime` entry. Runtime fees are not model calls
 * and arrive as `runtime_cost_usd`; a component line carrying them would be
 * counted twice by any reader that sums the lines and then adds the runtime
 * total.
 */
export const COST_COMPONENT_NAMES = [
  'preprocessing',
  'generation',
  'self_qa',
  'grading',
  'perception',
  'retry',
];

/** What a component line carries when it was not a first attempt. */
const RETRY_NONE = 'none';

// Slugs, not prose. Reason codes and component names are published to a
// public dashboard, and a free-text field on a published payload is a
// prompt-leak waiting to happen.
const SLUG = /^[a-z][a-z0-9_]{0,47}$/;
const REASON_CODE = /^[a-z][a-z0-9_.:-]{0,63}$/;
const SHA256 = /^[0-9a-f]{64}$/;
const LEDGER_PATH = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}(\/[A-Za-z0-9][A-Za-z0-9._-]{0,127})*$/;

const MAX_COMPONENTS = 32;
const MAX_USAGE_KEYS = 32;
const MAX_MISSING_REASONS = 32;

/**
 * Whose calls one receipt line is, in the order a reader scans: provider, then
 * the route, then the two model names, then the contract.
 *
 * Together these are what lets a price table be looked up without guessing.
 * `requested_model` alone is a deployment alias on Azure and a model name
 * elsewhere, and nothing in the string says which.
 */
const COMPONENT_IDENTITY = [
  'provider',
  'deployment',
  'requested_model',
  'resolved_model',
  'api_version',
];

// Not slug-checked: these are the provider's vocabulary, not ours, and a
// pattern tight enough to be worth having would reject the next new deployment
// name. Bounded instead, because the only real risk on a published payload is
// something long enough to be prose.
const MAX_IDENTITY_LENGTH = 128;

// Micro-dollars. Fine enough for a single cheap call, coarse enough that
// float noise never reaches the screen.
const MONEY_DIGITS = 6;
const MAX_COST_USD = 1_000_000;

// How many times a run called a model. Thousands, by construction — tasks
// times stages times the retries a run is allowed. The largest published to
// date is 2,346, which is 0.02% of this.
const MAX_MODEL_CALLS = 10_000_000;

// How many tokens those calls carried, which is neither the same quantity nor
// the same scale: the 2,346 calls above carried 21,688,749 input tokens
// between them.
//
// This is the bound the mirror side actually motivates. Above Number
// .MAX_SAFE_INTEGER a JSON integer does not survive JSON.parse — the file can
// say 9007199254740993 and this reader will hold 9007199254740992, with
// Number.isInteger saying yes to it the whole way. So the ceiling is where
// this reader stops agreeing with the file about what the file says, and the
// Python side is pinned to the same 2**53 - 1 for that reason.
const MAX_TOKENS = Number.MAX_SAFE_INTEGER;

function fail(field, detail) {
  throw new Error(`${field} ${detail}`);
}

function round(value, digits) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

/** A non-negative finite amount, or null when absent. */
function costAmount(value, field) {
  if (value === null || value === undefined) return null;
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    fail(field, 'must be a finite number');
  }
  if (value < 0 || value > MAX_COST_USD) fail(field, 'is out of range');
  return round(value, MONEY_DIGITS);
}

/**
 * A non-negative integer within `limit`, or null when absent.
 *
 * The bound is a parameter because a run's calls and the tokens those calls
 * carried are four orders of magnitude apart, and one bound covering both is
 * the smaller one under a general name.
 */
function costCount(value, field, limit) {
  if (value === null || value === undefined) return null;
  if (!Number.isInteger(value)) fail(field, 'must be an integer');
  if (value < 0 || value > limit) fail(field, 'is out of range');
  return value;
}

function costUsage(value, field) {
  if (value === null || value === undefined) return {};
  if (!isPlainObject(value)) fail(field, 'must be an object');
  const keys = Object.keys(value);
  if (keys.length > MAX_USAGE_KEYS) fail(field, 'carries too many keys');
  const usage = {};
  for (const key of keys.sort()) {
    if (!SLUG.test(key)) fail(field, 'carries an invalid key');
    usage[key] = costCount(value[key], `${field}.${key}`, MAX_TOKENS);
  }
  return usage;
}

function missingReasons(value, field) {
  if (value === null || value === undefined) return [];
  if (!Array.isArray(value)) fail(field, 'must be a list');
  if (value.length > MAX_MISSING_REASONS) fail(field, 'carries too many entries');
  for (const reason of value) {
    if (typeof reason !== 'string' || !REASON_CODE.test(reason)) {
      fail(field, 'must contain reason codes only');
    }
  }
  return [...new Set(value)].sort();
}

function priceTableSha256(value, field) {
  if (value === null || value === undefined) return null;
  if (typeof value !== 'string' || !SHA256.test(value)) {
    fail(field, 'must be a sha256 digest');
  }
  return value;
}

function costStatus(value, field) {
  if (!COST_STATUSES.includes(value)) {
    fail(field, `must be one of ${COST_STATUSES.join(', ')}`);
  }
  return value;
}

/**
 * Drop the zero a non-`complete` line carries as a placeholder.
 *
 * The producer fills every money field on every status, so an `unavailable`
 * receipt — one that recorded nothing at all — still reaches here as
 * `known_cost_usd: 0.0`. Passed through, that zero renders as `$0.0000`, which
 * is the exact reading the four statuses exist to prevent: "no record" turning
 * into "it was free".
 *
 * So a zero is a measurement under `complete` and nowhere else. That is not a
 * convention chosen here; it is the one real $0 the contract admits — a
 * rule-based path that never called a model. Under `partial` a zero means
 * nothing was confirmed yet, which is absence, not a floor of zero.
 *
 * A non-zero amount under `unavailable` or `not_run` is neither: the receipt
 * claims to know an amount and to have recorded nothing, and a receipt that
 * contradicts itself is not one this module will render.
 */
function measuredAmount(amount, status, field) {
  if (status === 'complete' || amount === null) return amount;
  if (amount === 0) return null;
  if (status === 'partial') return amount;
  return fail(field, `is ${status} but carries an amount`);
}

/**
 * Normalise one receipt line.
 *
 * The producer's line is `(stage, retry_kind)` — a retry belongs to the stage
 * that retried — with `name` derived from the pair for readers that show one
 * label per row. All three travel: the derived name is what a reader displays,
 * and the pair is what identifies the row, because two stages that each had to
 * retry both derive the name `retry` and are not the same line.
 *
 * Call identity travels beside them, unvalidated beyond being a bounded
 * non-empty string, because it names things this repository does not own: a
 * deployment alias and an API version are the provider's vocabulary, and a
 * reader that insisted on a known shape would reject the first new one. Absent
 * stays `null`, which reads as "this run did not record it" — the state every
 * receipt published before this change is honestly in.
 */
function identityText(value, field) {
  if (value === null || value === undefined) return null;
  if (typeof value !== 'string') fail(field, 'must be a string');
  const text = value.trim();
  if (text.length > MAX_IDENTITY_LENGTH) fail(field, 'is too long to be an identifier');
  return text || null;
}

function projectComponent(value, field) {
  if (!isPlainObject(value)) fail(field, 'must be an object');
  if (typeof value.name !== 'string' || !SLUG.test(value.name)) {
    fail(field, 'requires a slug name');
  }
  // Defaulted the way the producer defaults them when reading a receipt back,
  // so a line written by an older build still identifies itself.
  const stage = value.stage || value.name;
  if (typeof stage !== 'string' || !SLUG.test(stage)) {
    fail(field, 'requires a slug stage');
  }
  const retryKind = value.retry_kind || RETRY_NONE;
  if (typeof retryKind !== 'string' || !SLUG.test(retryKind)) {
    fail(field, 'requires a slug retry_kind');
  }
  const status = costStatus(value.status, `${field}.status`);
  const known = measuredAmount(
    costAmount(value.known_cost_usd, `${field}.known_cost_usd`),
    status,
    `${field}.known_cost_usd`,
  );
  const projected = {
    name: value.name,
    stage,
    retry_kind: retryKind,
    status,
    known_cost_usd: known,
    model_calls: costCount(value.model_calls, `${field}.model_calls`, MAX_MODEL_CALLS),
    usage: costUsage(value.usage, `${field}.usage`),
    missing_reasons: missingReasons(value.missing_reasons, `${field}.missing_reasons`),
  };
  for (const column of COMPONENT_IDENTITY) {
    projected[column] = identityText(value[column], `${field}.${column}`);
  }
  return projected;
}

/**
 * Normalise one `cost-receipt-v1` receipt.
 *
 * null/undefined in, null out — an absent receipt is a legitimate state and
 * stays absent rather than becoming a zero. Anything present but malformed
 * throws: a receipt the dashboard cannot read must not be rendered as if it
 * were sound.
 */
export function projectCostReceipt(value, field = 'cost receipt') {
  if (value === null || value === undefined) return null;
  if (!isPlainObject(value)) fail(field, 'must be an object');
  if (value.schema_version !== COST_RECEIPT_SCHEMA_VERSION) {
    fail(field, `must declare schema_version ${COST_RECEIPT_SCHEMA_VERSION}`);
  }
  if (value.currency !== COST_CURRENCY) {
    fail(field, `must be denominated in ${COST_CURRENCY}`);
  }

  const status = costStatus(value.status, `${field}.status`);
  const estimated = costAmount(value.estimated_cost_usd, `${field}.estimated_cost_usd`);
  let known = measuredAmount(
    costAmount(value.known_cost_usd, `${field}.known_cost_usd`),
    status,
    `${field}.known_cost_usd`,
  );
  const modelCost = measuredAmount(
    costAmount(value.model_cost_usd, `${field}.model_cost_usd`),
    status,
    `${field}.model_cost_usd`,
  );
  const runtimeCost = measuredAmount(
    costAmount(value.runtime_cost_usd, `${field}.runtime_cost_usd`),
    status,
    `${field}.runtime_cost_usd`,
  );
  const reasons = missingReasons(value.missing_reasons, `${field}.missing_reasons`);

  const rawComponents = value.components ?? [];
  if (!Array.isArray(rawComponents)) fail(field, 'components must be a list');
  if (rawComponents.length > MAX_COMPONENTS) fail(field, 'carries too many components');
  const components = rawComponents.map(
    (item, index) => projectComponent(item, `${field}.components[${index}]`),
  );
  // A line is identified by the pair *and* by whose call it was. Generation
  // that had to be redone and Self-QA that had to be redone both display as
  // 재시도, and rejecting the second as a duplicate would throw away a real
  // charge. So would rejecting the second of two models read under one
  // perception stage — which is why identity is part of the key rather than
  // decoration on it. Two lines that agree on all seven really are one line
  // the producer failed to add up.
  //
  // Serialised as JSON rather than joined on a separator: identity fields are
  // free text from the provider, not slugs, so no chosen byte is guaranteed
  // absent from them — and `null` must not key the same as the four-letter
  // string, since one means unrecorded and the other is a name.
  const keys = components.map((component) =>
    JSON.stringify([
      component.stage,
      component.retry_kind,
      ...COMPONENT_IDENTITY.map((column) => component[column] ?? null),
    ]),
  );
  if (keys.length !== new Set(keys).size) {
    fail(field, 'carries duplicate component keys');
  }

  if (status === 'complete') {
    if (estimated === null) fail(field, 'is complete without an amount');
    if (known === null) known = estimated;
    if (known !== estimated) fail(field, 'is complete but its known amount differs');
    if (reasons.length) fail(field, 'is complete but reports missing components');
  } else {
    // Only a complete receipt names a figure. Anything else offers at most a
    // floor, and an estimate riding on it would be the floor promoted to a
    // total by whoever reads it next.
    if (estimated !== null) fail(field, `is ${status} but carries an estimate`);
    if ((status === 'partial' || status === 'unavailable') && !reasons.length) {
      fail(field, `is ${status} without a reason code`);
    }
  }
  // `model_cost_usd + runtime_cost_usd === known_cost_usd` holds at the
  // producer, which sums in Decimal; each field is rounded independently on the
  // way out, so it is checked as a bound rather than an identity.
  for (const [amount, part] of [[modelCost, 'model_cost_usd'], [runtimeCost, 'runtime_cost_usd']]) {
    if (amount !== null && known !== null && amount > known) {
      fail(`${field}.${part}`, 'exceeds the known amount');
    }
  }

  return {
    schema_version: COST_RECEIPT_SCHEMA_VERSION,
    currency: COST_CURRENCY,
    status,
    estimated_cost_usd: estimated,
    known_cost_usd: known,
    model_cost_usd: modelCost,
    runtime_cost_usd: runtimeCost,
    model_calls: costCount(value.model_calls, `${field}.model_calls`, MAX_MODEL_CALLS),
    usage: costUsage(value.usage, `${field}.usage`),
    components,
    price_table_sha256: priceTableSha256(value.price_table_sha256, `${field}.price_table_sha256`),
    missing_reasons: reasons,
  };
}

/** Normalise the `{path, sha256}` pointer to the audit JSONL sidecar. */
export function projectCostLedgerReference(value, field = 'cost_ledger') {
  if (value === null || value === undefined) return null;
  if (!isPlainObject(value)) fail(field, 'must be an object');
  const { path, sha256 } = value;
  if (typeof path !== 'string' || !LEDGER_PATH.test(path)) {
    fail(field, 'path must be a relative repository path');
  }
  if (path.split('/').includes('..')) fail(field, 'path must not traverse parents');
  if (typeof sha256 !== 'string' || !SHA256.test(sha256)) {
    fail(field, 'sha256 must be a sha256 digest');
  }
  return { path, sha256 };
}

/** Linearly interpolated percentile over a non-empty sample. */
function percentile(values, fraction) {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  if (ordered.length === 1) return round(ordered[0], MONEY_DIGITS);
  const position = (ordered.length - 1) * fraction;
  const lower = Math.floor(position);
  const upper = Math.min(lower + 1, ordered.length - 1);
  const weight = position - lower;
  return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, MONEY_DIGITS);
}

/** The number this receipt contributes to a total, or null. */
function receiptAmount(receipt) {
  if (!MEASURED_STATUSES.includes(receipt.status)) return null;
  return receipt.known_cost_usd !== null
    ? receipt.known_cost_usd
    : receipt.estimated_cost_usd;
}

function aggregateComponents(receipts) {
  const totals = new Map();
  for (const receipt of receipts) {
    // Roll one receipt's lines up by displayed name before touching the run
    // totals. A task whose generation and Self-QA both had to be redone carries
    // two 재시도 lines but is still one task, and counting it twice would make
    // the coverage figure beside the row a fiction.
    const rolled = new Map();
    for (const component of receipt.components) {
      if (!rolled.has(component.name)) {
        rolled.set(component.name, { known_cost_usd: 0, model_calls: 0, complete: true });
      }
      const entry = rolled.get(component.name);
      if (component.known_cost_usd !== null) entry.known_cost_usd += component.known_cost_usd;
      if (component.model_calls) entry.model_calls += component.model_calls;
      if (component.status !== 'complete') entry.complete = false;
    }
    for (const [name, entry] of rolled) {
      if (!totals.has(name)) {
        totals.set(name, {
          name,
          tasks: 0,
          known_cost_usd: 0,
          complete_tasks: 0,
          model_calls: 0,
        });
      }
      const bucket = totals.get(name);
      bucket.tasks += 1;
      if (entry.complete) bucket.complete_tasks += 1;
      bucket.known_cost_usd += entry.known_cost_usd;
      bucket.model_calls += entry.model_calls;
    }
  }
  return [...totals.values()]
    .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))
    .map((bucket) => ({
      ...bucket,
      known_cost_usd: round(bucket.known_cost_usd, MONEY_DIGITS),
      status: bucket.complete_tasks === bucket.tasks ? 'complete' : 'partial',
    }));
}

/**
 * Aggregate one cost field across a run.
 *
 * Returns null when not a single row carries a receipt, which is what keeps
 * experiments graded before the instrumentation reading as "no record".
 *
 * Rows are `{ receipt, succeeded, deliverable }` triples so the caller — not
 * this module — decides what "succeeded" means for its own payload shape.
 */
export function summarizeCostReceipts(rows, { successfulDeliverables = null } = {}) {
  const receipts = [];
  let failedAmount = 0;
  let failedCount = 0;
  let failedMeasured = 0;
  let rowsWithoutAReceipt = 0;
  for (const row of rows) {
    const failed = !row?.succeeded;
    const receipt = row?.receipt;
    if (!isPlainObject(receipt)) {
      // No receipt at all is a hole in the record, not a task that cost
      // nothing -- and if that task also failed, it is still a failure.
      // `costReceiptsByTask` in scripts/aggregate-grades.mjs hands this
      // function a null receipt for every graded task the payload has no
      // `grading_cost` for, so this is the ordinary shape, not an edge case.
      // Skipping the row outright counted it in `total_tasks` and in the
      // coverage denominator while subtracting it from the failure count.
      // Mirrors `summarize_cost_receipts` in
      // batch-runner/core/cost_projection.py.
      rowsWithoutAReceipt += 1;
      if (failed) failedCount += 1;
      continue;
    }
    receipts.push(receipt);
    if (failed) {
      failedCount += 1;
      const amount = receiptAmount(receipt);
      if (amount !== null) {
        // Counted, not just added. Two failures against a model the price
        // table has no entry for contribute nothing here, and the sum they
        // leave behind is 0 -- the same number a failure that genuinely made
        // no model call leaves behind. The amount alone cannot tell those
        // apart, so the count of failures that could be priced is published
        // beside it. Mirrors `summarize_cost_receipts` in
        // batch-runner/core/cost_projection.py.
        failedMeasured += 1;
        failedAmount += amount;
      }
    }
  }
  if (!receipts.length) return null;

  const counts = Object.fromEntries(COST_STATUSES.map((status) => [status, 0]));
  for (const receipt of receipts) counts[receipt.status] += 1;

  const amounts = receipts
    .map(receiptAmount)
    .filter((amount) => amount !== null);
  const knownTotal = amounts.length
    ? round(amounts.reduce((sum, amount) => sum + amount, 0), MONEY_DIGITS)
    : 0;

  // The run's state comes from the receipts' own states, not from whether a
  // number fell out of them. `amounts` is empty whenever every measurable
  // receipt has a $0 floor — which `measuredAmount` nulls on purpose, and which
  // is the ordinary case when the model that was called is absent from the
  // price table, as the Stage 3 judge is. Reading the state off `amounts` made
  // such a run fall past `partial` all the way to `not_run`, telling the reader
  // that a run of 17 graded tasks and 1784 calls had never happened.
  //
  // Work that genuinely never ran is not a hole in the run: it contributed
  // nothing, so it neither drags the state down nor stops a total being a
  // total. This mirrors `_summary_status` in
  // batch-runner/core/cost_receipts.py, so the two summarisers cannot give
  // different answers about the same receipts.
  const ran = receipts.filter((entry) => entry.status !== 'not_run');
  let status;
  if (!ran.length) status = 'not_run';
  else if (ran.every((entry) => entry.status === 'complete')) status = 'complete';
  else if (ran.every((entry) => entry.status === 'unavailable')) status = 'unavailable';
  else status = 'partial';
  if (rowsWithoutAReceipt && status === 'complete') {
    // Every receipt the run does carry is whole, but the run is not: some
    // task's cost was never recorded at all. Judging completeness against the
    // receipts alone asks only "is what I kept consistent?", which the rows
    // that were dropped can never answer.
    //
    // Only `complete` moves. A run already reading partial, unavailable or
    // not_run is already not claiming to be whole, and a run where every row
    // carries a receipt reaches none of this, so no published experiment
    // changes what the dashboard says about it.
    status = 'partial';
  }

  // The run total is only a total when everything that ran is complete. One
  // partial or unavailable receipt makes it a floor, and it is labelled as one
  // rather than quietly rounded up into a headline number.
  const completeRun = status === 'complete';

  const reasons = [...new Set(receipts.flatMap((r) => r.missing_reasons))].sort();
  const priceTables = [...new Set(
    receipts.map((r) => r.price_table_sha256).filter(Boolean),
  )].sort();

  return {
    schema_version: COST_RECEIPT_SCHEMA_VERSION,
    currency: COST_CURRENCY,
    estimate_basis: ESTIMATE_BASIS,
    status,
    total_tasks: rows.length,
    receipt_tasks: receipts.length,
    measured_tasks: amounts.length,
    coverage_pct: rows.length ? round((receipts.length / rows.length) * 100, 1) : 0,
    complete_tasks: counts.complete,
    partial_tasks: counts.partial,
    unavailable_tasks: counts.unavailable,
    not_run_tasks: counts.not_run,
    known_cost_usd: knownTotal,
    estimated_cost_usd: completeRun ? knownTotal : null,
    avg_cost_usd: amounts.length
      ? round(amounts.reduce((sum, amount) => sum + amount, 0) / amounts.length, MONEY_DIGITS)
      : null,
    median_cost_usd: percentile(amounts, 0.5),
    p95_cost_usd: percentile(amounts, 0.95),
    max_cost_usd: amounts.length ? round(Math.max(...amounts), MONEY_DIGITS) : null,
    successful_deliverables: successfulDeliverables,
    cost_per_successful_deliverable_usd: completeRun && successfulDeliverables
      ? round(knownTotal / successfulDeliverables, MONEY_DIGITS)
      : null,
    // Failed work costs real money. It is reported beside the total, not
    // netted out of it.
    failed_task_count: failedCount,
    // How many of those failures could be priced at all. Without it the amount
    // below is unreadable: $0 means "these failures were free" and "these
    // failures were never priced" at the same time.
    failed_measured_tasks: failedMeasured,
    failed_task_cost_usd: round(failedAmount, MONEY_DIGITS),
    components: aggregateComponents(receipts),
    price_table_sha256: priceTables.length === 1 ? priceTables[0] : null,
    missing_reasons: reasons,
  };
}
