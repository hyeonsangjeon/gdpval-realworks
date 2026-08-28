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

// Micro-dollars. Fine enough for a single cheap call, coarse enough that
// float noise never reaches the screen.
const MONEY_DIGITS = 6;
const MAX_COST_USD = 1_000_000;
const MAX_COUNT = 10_000_000;

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

/** A non-negative bounded integer, or null when absent. */
function costCount(value, field) {
  if (value === null || value === undefined) return null;
  if (!Number.isInteger(value)) fail(field, 'must be an integer');
  if (value < 0 || value > MAX_COUNT) fail(field, 'is out of range');
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
    usage[key] = costCount(value[key], `${field}.${key}`);
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

function projectComponent(value, field) {
  if (!isPlainObject(value)) fail(field, 'must be an object');
  if (typeof value.name !== 'string' || !SLUG.test(value.name)) {
    fail(field, 'requires a slug name');
  }
  const status = costStatus(value.status, `${field}.status`);
  const estimated = costAmount(value.estimated_cost_usd, `${field}.estimated_cost_usd`);
  let known = costAmount(value.known_cost_usd, `${field}.known_cost_usd`);
  if (status === 'complete') {
    if (estimated === null) fail(field, 'is complete without an amount');
    if (known === null) known = estimated;
  } else if (status === 'partial') {
    if (known === null) fail(field, 'is partial without a known amount');
  } else if (estimated !== null || known !== null) {
    fail(field, `is ${status} but carries an amount`);
  }
  if (estimated !== null && known !== null && known > estimated) {
    fail(field, 'known amount exceeds its estimate');
  }
  return {
    name: value.name,
    status,
    estimated_cost_usd: estimated,
    known_cost_usd: known,
    model_calls: costCount(value.model_calls, `${field}.model_calls`),
    usage: costUsage(value.usage, `${field}.usage`),
  };
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
  let known = costAmount(value.known_cost_usd, `${field}.known_cost_usd`);
  const modelCost = costAmount(value.model_cost_usd, `${field}.model_cost_usd`);
  const runtimeCost = costAmount(value.runtime_cost_usd, `${field}.runtime_cost_usd`);
  const reasons = missingReasons(value.missing_reasons, `${field}.missing_reasons`);

  const rawComponents = value.components ?? [];
  if (!Array.isArray(rawComponents)) fail(field, 'components must be a list');
  if (rawComponents.length > MAX_COMPONENTS) fail(field, 'carries too many components');
  const components = rawComponents.map(
    (item, index) => projectComponent(item, `${field}.components[${index}]`),
  );
  const names = components.map((component) => component.name);
  if (names.length !== new Set(names).size) {
    fail(field, 'carries duplicate component names');
  }

  if (status === 'complete') {
    if (estimated === null) fail(field, 'is complete without an amount');
    if (known === null) known = estimated;
    if (known !== estimated) fail(field, 'is complete but its known amount differs');
    if (reasons.length) fail(field, 'is complete but reports missing components');
  } else if (status === 'partial') {
    if (known === null) fail(field, 'is partial without a known amount');
    if (!reasons.length) fail(field, 'is partial without a reason code');
  } else {
    if (estimated !== null || known !== null) {
      fail(field, `is ${status} but carries an amount`);
    }
    if (status === 'unavailable' && !reasons.length) {
      fail(field, 'is unavailable without a reason code');
    }
  }
  if (estimated !== null && known !== null && known > estimated) {
    fail(field, 'known amount exceeds its estimate');
  }
  for (const [amount, part] of [[modelCost, 'model_cost_usd'], [runtimeCost, 'runtime_cost_usd']]) {
    if (amount !== null && known !== null && amount > known) {
      fail(`${field}.${part}`, 'exceeds the known amount');
    }
  }

  return {
    schema_version: COST_RECEIPT_SCHEMA_VERSION,
    currency: COST_CURRENCY,
    status,
    estimate_basis: ESTIMATE_BASIS,
    estimated_cost_usd: estimated,
    known_cost_usd: known,
    model_cost_usd: modelCost,
    runtime_cost_usd: runtimeCost,
    model_calls: costCount(value.model_calls, `${field}.model_calls`),
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
    for (const component of receipt.components) {
      if (!totals.has(component.name)) {
        totals.set(component.name, {
          name: component.name,
          tasks: 0,
          known_cost_usd: 0,
          complete_tasks: 0,
          model_calls: 0,
        });
      }
      const bucket = totals.get(component.name);
      bucket.tasks += 1;
      if (component.status === 'complete') bucket.complete_tasks += 1;
      const amount = component.known_cost_usd ?? component.estimated_cost_usd;
      if (amount !== null) bucket.known_cost_usd += amount;
      if (component.model_calls) bucket.model_calls += component.model_calls;
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
  for (const row of rows) {
    const receipt = row?.receipt;
    if (!isPlainObject(receipt)) continue;
    receipts.push(receipt);
    if (!row.succeeded) {
      failedCount += 1;
      const amount = receiptAmount(receipt);
      if (amount !== null) failedAmount += amount;
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

  // The run total is only a total when every receipt is complete. One partial
  // or unavailable receipt makes it a floor, and it is labelled as one rather
  // than quietly rounded up into a headline number.
  const completeRun = counts.complete === receipts.length;
  let status;
  if (completeRun) status = 'complete';
  else if (amounts.length) status = 'partial';
  else if (counts.unavailable) status = 'unavailable';
  else status = 'not_run';

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
    failed_task_cost_usd: round(failedAmount, MONEY_DIGITS),
    components: aggregateComponents(receipts),
    price_table_sha256: priceTables.length === 1 ? priceTables[0] : null,
    missing_reasons: reasons,
  };
}
