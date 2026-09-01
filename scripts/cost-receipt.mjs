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

// How long one path component may be. Not a taste decision: 255 bytes is
// `NAME_MAX` on every filesystem this runs on, so a longer component cannot
// name a file that exists, and a bound below it would reject real names. The
// names here are run identities — experiment, judge, config hash, rubric SHA,
// inference SHA, grader source hash — and the longest under `data/grades`
// today is 254 bytes. The 128 this used to be excluded seven of them.
//
// Kept in step with `_MAX_LEDGER_NAME` / `_MAX_LEDGER_PATH_LENGTH` in
// `core/cost_projection.py`: the two validators read the same published files,
// so a payload either side refuses is a payload neither may publish.
const MAX_LEDGER_NAME = 255;

// And how long the whole path may be, which the per-component bound does not
// imply: nesting is what grows it. A published ledger sits under
// `data/grades`, up to five directories down for a repeat of a shard of a
// diagnostic run; the longest that exists today is 348 bytes.
const MAX_LEDGER_PATH_LENGTH = 512;

// The leading character is narrower than the rest so that `..` and a segment
// that could be read as a command-line option are both out. It admits `_`
// because the directories these paths run through are `_shards`, `_repeats`
// and `_diagnostic` — which never came up while the field held a bare
// filename, and is most of what it holds now.
const LEDGER_SEGMENT = `[A-Za-z0-9_][A-Za-z0-9._-]{0,${MAX_LEDGER_NAME - 1}}`;
const LEDGER_PATH = new RegExp(`^${LEDGER_SEGMENT}(/${LEDGER_SEGMENT})*$`);

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
 * Normalise a payload's `components` list.
 *
 * A line is identified by the pair *and* by whose call it was. Generation that
 * had to be redone and Self-QA that had to be redone both display as 재시도,
 * and rejecting the second as a duplicate would throw away a real charge. So
 * would rejecting the second of two models read under one perception stage —
 * which is why identity is part of the key rather than decoration on it. Two
 * lines that agree on all seven really are one line the producer failed to add
 * up.
 *
 * Keyed by `summaryComponentKey`, the same function the run summariser folds
 * its rows under, so a list this refuses and a list that summariser would
 * silently merge cannot be different lists.
 */
function projectComponents(value, field) {
  const raw = value ?? [];
  if (!Array.isArray(raw)) fail(field, 'components must be a list');
  if (raw.length > MAX_COMPONENTS) fail(field, 'carries too many components');
  const components = raw.map(
    (item, index) => projectComponent(item, `${field}.components[${index}]`),
  );
  const keys = components.map(summaryComponentKey);
  if (keys.length !== new Set(keys).size) fail(field, 'carries duplicate component keys');
  return components;
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

  const components = projectComponents(value.components, field);

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
  if (typeof path !== 'string' || !LEDGER_PATH.test(path)
      || path.length > MAX_LEDGER_PATH_LENGTH) {
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

/**
 * The identity two run-summary lines must share before they may be added up.
 *
 * The same seven fields `projectCostReceipt` rejects duplicates of and
 * `core.cost_receipts._component_key` groups a task's own lines under, so that
 * the producer, this reader and the Python summariser all land on the same
 * rows. Not `name`: `name` is *derived* from the first two — every retry at
 * every stage derives `retry`, and both a visual reader and an audio reader
 * derive `perception` — so it cannot tell those rows apart by construction.
 *
 * Serialised as JSON rather than joined on a separator: identity fields are
 * free text from the provider, not slugs, so no chosen byte is guaranteed
 * absent from them — and `null` must not key the same as the four-letter
 * string, since one means unrecorded and the other is a name.
 */
function summaryComponentKey(component) {
  return JSON.stringify([
    component.stage,
    component.retry_kind,
    ...COMPONENT_IDENTITY.map((column) => component[column] ?? null),
  ]);
}

function aggregateComponents(receipts) {
  const totals = new Map();
  for (const receipt of receipts) {
    // Roll one receipt's lines up before touching the run totals. A task whose
    // generation and Self-QA both had to be redone carries two 재시도 lines but
    // is still one task, and counting it twice would make the coverage figure
    // beside the row a fiction.
    //
    // Rolled by the line's own seven-field identity, not by the label it
    // displays under. Folding by `name` was that same double-count guard turned
    // into a merge: generation's retry and Self-QA's retry both display as
    // 재시도, so one run published a single $0.190047 / 4-call 재시도 row over a
    // $0.178985 / 2-call generation retry and a $0.011062 / 2-call Self-QA
    // retry. Under `perception` it is worse than untidy — a visual reader and
    // an audio reader carry different rates, and their summed tokens are a row
    // no price table can reproduce and no reader can take apart again.
    //
    // Mirrors `summarize_cost_receipts` in batch-runner/core/cost_projection.py.
    const rolled = new Map();
    for (const component of receipt.components) {
      const key = summaryComponentKey(component);
      if (!rolled.has(key)) {
        rolled.set(key, {
          // Carried, not re-derived: the label is the producer's to choose,
          // and this reader only displays it.
          name: component.name,
          known_cost_usd: 0,
          model_calls: 0,
          missing_reasons: new Set(),
          complete: true,
        });
      }
      const entry = rolled.get(key);
      if (component.known_cost_usd !== null) entry.known_cost_usd += component.known_cost_usd;
      if (component.model_calls) entry.model_calls += component.model_calls;
      for (const reason of component.missing_reasons) entry.missing_reasons.add(reason);
      if (component.status !== 'complete') entry.complete = false;
    }
    for (const [key, entry] of rolled) {
      if (!totals.has(key)) {
        const [stage, retryKind, ...identity] = JSON.parse(key);
        totals.set(key, {
          name: entry.name,
          stage,
          retry_kind: retryKind,
          ...Object.fromEntries(COMPONENT_IDENTITY.map((column, index) => [
            column,
            identity[index],
          ])),
          tasks: 0,
          known_cost_usd: 0,
          complete_tasks: 0,
          model_calls: 0,
          // Why a row could not be priced belongs beside the row. Kept only at
          // the run level, "no rate published for this model" arrived detached
          // from which model, which is the one thing a reader needs to act on
          // it.
          missing_reasons: new Set(),
        });
      }
      const bucket = totals.get(key);
      bucket.tasks += 1;
      if (entry.complete) bucket.complete_tasks += 1;
      bucket.known_cost_usd += entry.known_cost_usd;
      bucket.model_calls += entry.model_calls;
      for (const reason of entry.missing_reasons) bucket.missing_reasons.add(reason);
    }
  }
  // Unrecorded identity sorts first, which is the state every receipt
  // published before call identity existed is honestly in.
  const order = (bucket) => JSON.stringify([
    bucket.stage,
    bucket.retry_kind,
    ...COMPONENT_IDENTITY.map((column) => bucket[column] ?? ''),
  ]);
  return [...totals.values()]
    .sort((a, b) => (order(a) < order(b) ? -1 : order(a) > order(b) ? 1 : 0))
    .map((bucket) => ({
      ...bucket,
      known_cost_usd: round(bucket.known_cost_usd, MONEY_DIGITS),
      missing_reasons: [...bucket.missing_reasons].sort(),
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

// ── the gate on a summary this build did not compute ─────────────────────
//
// Everything `summarizeCostReceipts` returns is sound by construction, because
// it did the arithmetic. The other producer of the same shape is
// `build_cost_summaries` in batch-runner/core/cost_projection.py, and its
// output travels inside `report_data.json` — which reaches the build over an
// unauthenticated fetch from HuggingFace for every experiment, since no results
// directory carries a local copy. Between that fetch and `summaryTotalCell` in
// src/lib/cost.ts there was nothing at all: `scripts/aggregate-reports.mjs`
// spread the object into the published index verbatim and the dashboard
// rendered it as money.
//
// Two ways that ends badly, both reproduced before this was written:
//
//   * `status: "partial"` beside a non-null `estimated_cost_usd` renders as a
//     settled `$0.5000`. The corner of the card says 일부 기록됨 and the middle
//     says a firm figure, and the figure is the part people read.
//   * `estimated_cost_usd` absent renders nothing at all: `undefined !== null`
//     is true, so `formatCostUsd(undefined)` reaches `undefined.toFixed` and
//     takes the experiment page down with a TypeError.
//
// So the rule both producers already obey is enforced here on the way in.

// A summary counts tasks, and a run of this benchmark has 220 of them. Bounded
// four orders of magnitude above that rather than pinned to it: a corpus this
// repository has not defined yet is not the thing worth refusing.
const MAX_SUMMARY_TASKS = 1_000_000;

/** A count the summary must carry; absent is a malformed summary, not a zero. */
function summaryCount(value, field) {
  const count = costCount(value, field, MAX_SUMMARY_TASKS);
  if (count === null) fail(field, 'is required');
  return count;
}

/** An amount the summary must carry, for the same reason. */
function summaryAmount(value, field) {
  const amount = costAmount(value, field);
  if (amount === null) fail(field, 'is required');
  return amount;
}

/**
 * Normalise one run summary that arrived from somewhere else.
 *
 * null/undefined in, null out — an experiment that ran before receipts existed
 * carries no summary, and that absence is what makes the dashboard say 기록
 * 없음 rather than $0. Anything present but malformed throws, and the caller
 * turns that into a named build failure.
 */
export function projectCostSummary(value, field = 'cost summary') {
  if (value === null || value === undefined) return null;
  if (!isPlainObject(value)) fail(field, 'must be an object');
  if (value.schema_version !== COST_RECEIPT_SCHEMA_VERSION) {
    fail(field, `must declare schema_version ${COST_RECEIPT_SCHEMA_VERSION}`);
  }
  if (value.currency !== COST_CURRENCY) {
    fail(field, `must be denominated in ${COST_CURRENCY}`);
  }

  const status = costStatus(value.status, `${field}.status`);
  const known = summaryAmount(value.known_cost_usd, `${field}.known_cost_usd`);
  const estimated = costAmount(value.estimated_cost_usd, `${field}.estimated_cost_usd`);

  // The biconditional both summarisers hold to: `estimated_cost_usd` is
  // `known_total if complete_run else None`, and `complete_run` is exactly
  // `status === 'complete'`. Checked in both directions, because each one is a
  // different lie. A complete run withholding its total understates what was
  // spent; an incomplete run naming one promotes a floor to a headline.
  if (status === 'complete') {
    if (estimated === null) fail(field, 'is complete without a total');
    if (estimated !== known) {
      fail(field, 'is complete but its total is not what it knows');
    }
  } else if (estimated !== null) {
    fail(field, `is ${status} but carries a total`);
  }

  const totalTasks = summaryCount(value.total_tasks, `${field}.total_tasks`);
  const receiptTasks = summaryCount(value.receipt_tasks, `${field}.receipt_tasks`);
  const measuredTasks = summaryCount(value.measured_tasks, `${field}.measured_tasks`);
  if (receiptTasks > totalTasks) fail(field, 'holds more receipts than it has tasks');
  if (measuredTasks > receiptTasks) {
    fail(field, 'prices more tasks than it holds receipts for');
  }

  // Each receipt lands in exactly one bucket, so the buckets are the receipts
  // counted a second way. A payload where the two disagree has been rewritten
  // by something that did not know that, and the disagreement is the only
  // evidence of it there will ever be.
  const buckets = {};
  let bucketed = 0;
  for (const name of COST_STATUSES) {
    const count = summaryCount(value[`${name}_tasks`], `${field}.${name}_tasks`);
    buckets[`${name}_tasks`] = count;
    bucketed += count;
  }
  if (bucketed !== receiptTasks) {
    fail(field, 'sorts its receipts into buckets that do not add up');
  }

  const coverage = value.coverage_pct;
  if (typeof coverage !== 'number' || !Number.isFinite(coverage)
      || coverage < 0 || coverage > 100) {
    fail(`${field}.coverage_pct`, 'must be a percentage');
  }

  const failedCount = summaryCount(value.failed_task_count, `${field}.failed_task_count`);
  if (failedCount > totalTasks) fail(field, 'counts more failures than it has tasks');
  // Optional, and only optional: reports published before this count existed do
  // not carry it, and src/types/cost.ts marks it so. Absent stays absent, which
  // is what makes `failedTaskCostCell` fall back to its older inference instead
  // of trusting a zero this reader invented.
  const failedMeasured = costCount(
    value.failed_measured_tasks, `${field}.failed_measured_tasks`, MAX_SUMMARY_TASKS,
  );
  if (failedMeasured !== null && failedMeasured > failedCount) {
    fail(field, 'prices more failures than it counted');
  }

  return {
    schema_version: COST_RECEIPT_SCHEMA_VERSION,
    currency: COST_CURRENCY,
    estimate_basis: ESTIMATE_BASIS,
    status,
    total_tasks: totalTasks,
    receipt_tasks: receiptTasks,
    measured_tasks: measuredTasks,
    coverage_pct: round(coverage, 1),
    ...buckets,
    known_cost_usd: known,
    estimated_cost_usd: estimated,
    avg_cost_usd: costAmount(value.avg_cost_usd, `${field}.avg_cost_usd`),
    median_cost_usd: costAmount(value.median_cost_usd, `${field}.median_cost_usd`),
    p95_cost_usd: costAmount(value.p95_cost_usd, `${field}.p95_cost_usd`),
    max_cost_usd: costAmount(value.max_cost_usd, `${field}.max_cost_usd`),
    successful_deliverables: costCount(
      value.successful_deliverables, `${field}.successful_deliverables`, MAX_SUMMARY_TASKS,
    ),
    cost_per_successful_deliverable_usd: costAmount(
      value.cost_per_successful_deliverable_usd,
      `${field}.cost_per_successful_deliverable_usd`,
    ),
    failed_task_count: failedCount,
    ...(failedMeasured === null ? {} : { failed_measured_tasks: failedMeasured }),
    failed_task_cost_usd: summaryAmount(
      value.failed_task_cost_usd, `${field}.failed_task_cost_usd`,
    ),
    components: projectComponents(value.components, field),
    price_table_sha256: priceTableSha256(
      value.price_table_sha256, `${field}.price_table_sha256`,
    ),
    missing_reasons: missingReasons(value.missing_reasons, `${field}.missing_reasons`),
  };
}

/**
 * Normalise the `{problem_solving_cost, grading_cost}` wrapper.
 *
 * Returns only the fields that projected to something, and null when none did,
 * so a wrapper that survived a producer change with nothing left in it reads as
 * no record rather than as an empty card.
 */
export function projectCostSummaries(value, field = 'cost_summary') {
  if (value === null || value === undefined) return null;
  if (!isPlainObject(value)) fail(field, 'must be an object');
  // An unknown key here is a field the dashboard will not render and nobody
  // will notice is missing. Named rather than dropped, because the two ways a
  // cost stops being shown — never recorded, and recorded under a name no
  // reader knows — look identical on screen.
  const unknown = Object.keys(value).filter((key) => !COST_FIELDS.includes(key));
  if (unknown.length) fail(field, `carries an unknown cost field: ${unknown.sort().join(', ')}`);

  const projected = {};
  for (const key of COST_FIELDS) {
    const summary = projectCostSummary(value[key], `${field}.${key}`);
    if (summary !== null) projected[key] = summary;
  }
  return Object.keys(projected).length ? projected : null;
}

